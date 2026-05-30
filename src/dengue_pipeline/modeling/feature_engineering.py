import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import TransformedTargetRegressor

from dengue_pipeline.shared_kernel import padronizar_regioes_administrativas, carregar_historico_populacao
from dengue_pipeline.etl import ingestar_dados_saude_local, mascaras_target, carregar_cache_climatico
from dengue_pipeline.config import CAMINHO_DATASET_PARQUET
def construir_dataset_consolidado(target_name: str = "familia_dengue") -> pd.DataFrame:
    """
    Constrói o dataset consolidado agregando dados de casos, históricos de população e clima.
    Gera lags temporais de 1 a 4 semanas para casos/incidência, lags de 2 a 8 semanas para variáveis
    climáticas, e engenharia de variáveis sazonais cíclicas (seno/cosseno).
    
    Parâmetros:
        target_name (str): Configuração de máscara do target epidemiológico. Default: 'familia_dengue'.
        
    Retorna:
        pd.DataFrame: Dataset final processado pronto para treinamento e modelagem.
        
    Premissas críticas:
        Assume que os dados de casos e climáticos são carregáveis via ETL.
        Salva o resultado final processado no formato Parquet na raiz do projeto.
    """
    df = ingestar_dados_saude_local()
    pop = carregar_historico_populacao()
    lookup = pop["RA"].unique()  # As RAs canônicas normalizadas
    lookup_dict = {padronizar_regioes_administrativas(r): r for r in lookup}
    masks = mascaras_target(df)
    
    if target_name not in masks:
        raise ValueError(f"Filtro de target epidemiológico desconhecido: {target_name}")
        
    df = df.loc[masks[target_name]].copy()
    df = df[df["uf_norm"].eq("DF")].copy()
    df["RA"] = df["i_desc_radf_res"].map(lambda x: padronizar_regioes_administrativas(x, lookup_dict))
    df = df[df["RA"].notna() & df["epi_sunday"].notna()].copy()
    
    cases = df.groupby(["epi_sunday", "RA"]).size().reset_index(name="cases")
    
    valid_ras = sorted(list(set(lookup)))
    start = pd.Timestamp("2017-01-01")
    end = max(cases["epi_sunday"].max(), pd.Timestamp.today().normalize())
    all_sundays = pd.date_range(start=start, end=end, freq="W-SUN")
    grid = pd.MultiIndex.from_product([all_sundays, valid_ras], names=["epi_sunday", "RA"]).to_frame(index=False)
    
    dataset = grid.merge(cases, on=["epi_sunday", "RA"], how="left")
    dataset["cases"] = dataset["cases"].fillna(0).astype(float)
    dataset["ano"] = dataset["epi_sunday"].dt.year.astype(int)
    
    # Merge com histórico de população
    dataset = dataset.merge(pop[["RA", "ano", "populacao"]], on=["RA", "ano"], how="inner")
    dataset["incidencia_100k"] = dataset["cases"] / dataset["populacao"] * 100000
    
    # Merge com clima (otimizado: lags calculados no clima consolidado pré-merge)
    climate = carregar_cache_climatico().sort_values("epi_sunday").reset_index(drop=True)
    for col in ["precip_sum", "temp_mean", "umidmed"]:
        for lag in range(2, 9):
            climate[f"{col}_lag_{lag}"] = climate[col].shift(lag)
            
    dataset = dataset.merge(climate, on="epi_sunday", how="left")
    dataset = dataset.sort_values(["RA", "epi_sunday"]).reset_index(drop=True)
    
    # Engenharia de Lags de Casos (1 a 4 semanas)
    for col in ["cases", "incidencia_100k"]:
        for lag in [1, 2, 3, 4]:
            dataset[f"{col}_lag_{lag}"] = dataset.groupby("RA")[col].shift(lag)
            
    # Features de Tendência de Curto Prazo (Anti-Bias Sazonal)
    # Fornece ao modelo o sinal de aceleração/desaceleração do surto,
    # permitindo que árvores detectem a curvatura da série — crucial para
    # evitar a subestimação de picos epidêmicos e a superestimação da calmaria.
    dataset["cases_delta_1"] = dataset["cases_lag_1"] - dataset["cases_lag_2"]
    dataset["cases_delta_2"] = dataset["cases_lag_2"] - dataset["cases_lag_3"]
    # Taxa de crescimento semanal (análoga ao Rt efetivo por RA)
    # +1 no denominador para evitar divisão por zero em semanas sem casos
    dataset["cases_growth_rate"] = (dataset["cases_lag_1"] + 1) / (dataset["cases_lag_2"] + 1)
            
    # Os lags climáticos foram calculados acima de forma otimizada pré-merge
    # para evitar sobrecarga computacional de groupby e propagação inútil de NaNs.
            
    # Variáveis sazonais cíclicas
    week = dataset["epi_sunday"].dt.isocalendar().week.astype(int)
    month = dataset["epi_sunday"].dt.month.astype(int)
    dataset["week_of_year"] = week
    dataset["month"] = month
    dataset["sin_week"] = np.sin(2 * np.pi * week / 53)
    dataset["cos_week"] = np.cos(2 * np.pi * week / 53)
    dataset["sin_month"] = np.sin(2 * np.pi * month / 12)
    dataset["cos_month"] = np.cos(2 * np.pi * month / 12)
    
    # Persiste o dataset processado
    dataset.to_parquet(CAMINHO_DATASET_PARQUET, index=False)
    
    return dataset

def obter_configuracao_features(config: str) -> dict:
    """
    Retorna o dicionário de especificação das features a serem utilizadas de acordo com a configuração.
    
    Parâmetros:
        config (str): Configuração desejada (ex: 'lag-only', 'lag+clima', 'lag+clima+RA', etc).
        
    Retorna:
        dict: Dicionário contendo as especificações do target e das features de entrada do modelo.
    """
    climate = [
        f"{col}_lag_{lag}"
        for col in ["precip_sum", "temp_mean", "umidmed"]
        for lag in range(2, 9)
    ]
    cyclic = ["sin_week", "cos_week", "sin_month", "cos_month"]
    case_lags = [f"cases_lag_{lag}" for lag in [1, 2, 3, 4]]
    incid_lags = [f"incidencia_100k_lag_{lag}" for lag in [1, 2, 3, 4]]
    # Features de tendência de curto prazo para corrigir bias sazonal de picos
    trend_features = ["cases_delta_1", "cases_delta_2", "cases_growth_rate"]
    
    if config == "lag-only":
        return {"target": "cases", "base": case_lags + trend_features, "ra": False, "population": False}
    if config == "lag+clima":
        return {"target": "cases", "base": case_lags + trend_features + climate + cyclic, "ra": False, "population": False}
    if config == "lag+clima+RA":
        return {"target": "cases", "base": case_lags + trend_features + climate + cyclic, "ra": True, "population": False}
    if config == "lag+clima+RA+incid-target":
        return {"target": "incidencia_100k", "base": incid_lags + trend_features + climate + cyclic, "ra": True, "population": True}
        
    raise ValueError(f"Configuração de features desconhecida: {config}")

def preparar_matriz_design(df: pd.DataFrame, config: str, dummy_columns: list[str] | None = None):
    """
    Prepara a matriz de design (X) e a variável resposta transformada (y = log1p(target)).
    
    Parâmetros:
        df (pd.DataFrame): DataFrame completo de dados.
        config (str): Configuração da especificação das features.
        dummy_columns (list[str], opcional): Lista com colunas dummies pré-calculadas (para alinhar treino/teste).
        
    Retorna:
        tuple: (X, y, df_filtrado, features, spec)
    """
    spec = obter_configuracao_features(config)
    frame = df.copy()
    features = list(spec["base"])
    
    if spec["population"]:
        features.append("populacao")
        
    if spec["ra"]:
        dummies = pd.get_dummies(frame["RA"], prefix="RA", dtype=float)
        if dummy_columns is not None:
            dummies = dummies.reindex(columns=dummy_columns, fill_value=0.0)
        frame = pd.concat([frame.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
        features.extend(dummies.columns.tolist())
        
    mask_cols = features + [spec["target"], "cases", "populacao", "epi_sunday", "RA"]
    frame = frame.dropna(subset=[c for c in mask_cols if c in frame.columns]).copy()
    X = frame[features].astype(float)
    target_raw = frame[spec["target"]].astype(float)
    y = np.log1p(target_raw)
    
    return X, y, frame, features, spec


def construir_pipeline_features(config: str) -> tuple[ColumnTransformer, list[str]]:
    """
    Constrói um ColumnTransformer que encapsula o pré-processamento de features
    de forma isolada por fold, eliminando vazamento de dados (schema leakage).

    O pipeline aplica:
      - OneHotEncoder(handle_unknown='ignore') para a coluna 'RA' (quando spec["ra"]=True)
      - Passthrough para todas as features numéricas base

    Parâmetros:
        config (str): Configuração de features (e.g. 'lag+clima+RA').

    Retorna:
        tuple: (column_transformer, lista_features_numericas)
    """
    spec = obter_configuracao_features(config)
    features_numericas = list(spec["base"])

    if spec["population"]:
        features_numericas.append("populacao")

    transformers = [
        ("num", "passthrough", features_numericas),
    ]

    if spec["ra"]:
        transformers.append(
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=float),
                ["RA"],
            )
        )

    ct = ColumnTransformer(transformers=transformers, remainder="drop")
    return ct, features_numericas


def construir_pipeline_modelo(config: str, modelo) -> Pipeline:
    """
    Constrói um Pipeline scikit-learn completo que encadeia:
      1. Pré-processamento (ColumnTransformer com OHE isolado)
      2. Regressão com transformação automática do target (log1p / expm1)

    O TransformedTargetRegressor garante que a transformação logarítmica do target
    e sua inversão são acopladas nativamente ao ciclo fit/predict, eliminando
    a necessidade de desfazer manualmente a escala via np.expm1.

    Parâmetros:
        config (str): Configuração de features (e.g. 'lag+clima+RA').
        modelo: Instância de regressor compatível com scikit-learn (e.g. RandomForestRegressor).

    Retorna:
        Pipeline: Pipeline completo pronto para fit/predict.
    """
    ct, _ = construir_pipeline_features(config)

    # TransformedTargetRegressor: automatiza log1p no fit e expm1 no predict
    regressor_transformado = TransformedTargetRegressor(
        regressor=modelo,
        func=np.log1p,
        inverse_func=np.expm1,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", ct),
            ("regressor", regressor_transformado),
        ]
    )
    return pipeline


def obter_colunas_entrada_pipeline(config: str) -> list[str]:
    """
    Retorna a lista de colunas que o DataFrame de entrada deve conter
    para ser processado pelo pipeline construído para a config dada.

    Útil para filtrar o DataFrame antes de passar ao pipeline.fit() / .predict().

    Parâmetros:
        config (str): Configuração de features.

    Retorna:
        list[str]: Lista de nomes de colunas necessárias.
    """
    spec = obter_configuracao_features(config)
    colunas = list(spec["base"])
    if spec["population"]:
        colunas.append("populacao")
    if spec["ra"]:
        colunas.append("RA")
    return colunas
