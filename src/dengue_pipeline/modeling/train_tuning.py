import json
import numpy as np
import pandas as pd
from pathlib import Path
from joblib import dump
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import ParameterGrid, TimeSeriesSplit
from xgboost import XGBRegressor

from dengue_pipeline.modeling.feature_engineering import (
    preparar_matriz_design,
    obter_configuracao_features,
    construir_pipeline_modelo,
    obter_colunas_entrada_pipeline,
)
from dengue_pipeline.modeling.evaluation import (
    calcular_erro_quadratico_medio,
    consolidar_metricas_performance,
)
from dengue_pipeline.modeling.types import TuningResult
from dengue_pipeline.config import BASE_DIR, MODELOS_DIR
import logging
logger = logging.getLogger(__name__)
def dividir_treino_teste_temporal(df: pd.DataFrame, ano_teste: int = 2025) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Realiza a divisão temporal entre os conjuntos de treino e teste.
    
    Parâmetros:
        df (pd.DataFrame): DataFrame completo de entrada.
        ano_teste (int): O ano inicial de corte para teste. Default: 2025.
        
    Retorna:
        tuple: (treino, teste) como DataFrames separados.
    """
    treino = df[df["epi_sunday"] < pd.Timestamp(f"{ano_teste}-01-01")].copy()
    teste = df[
        (df["epi_sunday"] >= pd.Timestamp(f"{ano_teste}-01-01"))
        & (df["epi_sunday"] < pd.Timestamp(f"{ano_teste + 1}-01-01"))
    ].copy()
    return treino, teste

def fabrica_modelos(nome_modelo: str, parametros: dict | None = None):
    """
    Fábrica de modelos que instancia Random Forest ou XGBoost com os parâmetros fornecidos.
    
    Parâmetros:
        nome_modelo (str): 'RF' para Random Forest ou 'XGB' para XGBoost.
        parametros (dict, opcional): Parâmetros adicionais para sobreposição.
        
    Retorna:
        Modelo regressor instanciado compatível com scikit-learn.
    """
    parametros = dict(parametros or {})
    if nome_modelo == "RF":
        defaults = {"n_estimators": 150, "max_depth": 15, "random_state": 42, "n_jobs": -1}
        defaults.update(parametros)
        return RandomForestRegressor(**defaults)
    if nome_modelo == "XGB":
        defaults = {
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 4,
            "random_state": 42,
            "n_jobs": -1,
            "objective": "reg:squarederror",
            "tree_method": "hist",
        }
        defaults.update(parametros)
        return XGBRegressor(**defaults)
    raise ValueError(f"Modelo desconhecido: {nome_modelo}")


def _preparar_entrada_pipeline(df: pd.DataFrame, config: str) -> pd.DataFrame:
    """
    Filtra e prepara o DataFrame para entrada no pipeline scikit-learn,
    removendo linhas com NaN nas colunas necessárias.

    Parâmetros:
        df (pd.DataFrame): DataFrame bruto.
        config (str): Configuração de features.

    Retorna:
        pd.DataFrame: DataFrame limpo pronto para pipeline.fit() ou .predict().
    """
    spec = obter_configuracao_features(config)
    colunas_pipeline = obter_colunas_entrada_pipeline(config)
    # Colunas auxiliares que precisam existir para métricas (não entram no pipeline)
    colunas_meta = ["epi_sunday", "RA", "cases", "populacao"]
    if spec["target"] == "incidencia_100k":
        colunas_meta.append("incidencia_100k")

    todas = list(set(colunas_pipeline + colunas_meta))
    existentes = [c for c in todas if c in df.columns]
    frame = df.dropna(subset=[c for c in existentes if c in df.columns]).copy()
    return frame


def _prever_com_pipeline(pipeline, frame: pd.DataFrame, config: str, spec: dict) -> np.ndarray:
    """
    Realiza a previsão usando o pipeline scikit-learn.
    O TransformedTargetRegressor já inverte a transformação log1p automaticamente,
    então a saída está na escala original do target.

    Se o target for incidência, converte para casos absolutos.

    Parâmetros:
        pipeline: Pipeline treinado.
        frame (pd.DataFrame): DataFrame de entrada com as colunas necessárias.
        config (str): Configuração de features.
        spec (dict): Especificação de features.

    Retorna:
        np.ndarray: Previsões de casos reais (absolutos) não-negativas.
    """
    colunas_pipeline = obter_colunas_entrada_pipeline(config)
    X = frame[colunas_pipeline]
    pred_target = pipeline.predict(X)
    pred_target = np.clip(pred_target, 0, None)

    if spec["target"] == "incidencia_100k":
        return pred_target * frame["populacao"].to_numpy(dtype=float) / 100000
    return pred_target


def prever_casos_recursivo(model, X: pd.DataFrame, frame: pd.DataFrame, spec: dict) -> np.ndarray:
    """
    Realiza a previsão de casos usando o modelo treinado, desfazendo a escala logarítmica
    e convertendo incidência para número de casos absolutos quando necessário.

    NOTA: Esta função é mantida para retrocompatibilidade com código legado.
    Para novos usos, preferir _prever_com_pipeline que trabalha com o Pipeline scikit-learn.
    
    Parâmetros:
        model: Modelo de regressão treinado.
        X (pd.DataFrame): Matriz de features de entrada.
        frame (pd.DataFrame): DataFrame original correspondente às linhas de X.
        spec (dict): Especificação das features contendo o tipo de target.
        
    Retorna:
        np.ndarray: Previsões de casos reais (absolutos) não-negativas.
    """
    pred_target = np.expm1(model.predict(X))
    pred_target = np.clip(pred_target, 0, None)
    if spec["target"] == "incidencia_100k":
        return pred_target * frame["populacao"].to_numpy(dtype=float) / 100000
    return pred_target


def executar_ajuste_previsao(
    df: pd.DataFrame,
    config: str,
    nome_modelo: str,
    parametros: dict | None = None,
    ano_teste: int = 2025,
) -> TuningResult:
    """
    Ajusta e prediz usando uma configuração de features e modelo específicos.
    Utiliza Pipeline scikit-learn com ColumnTransformer e TransformedTargetRegressor
    para garantir isolamento de dados e transformação automática do target.
    
    Parâmetros:
        df: DataFrame completo.
        config: Identificador da configuração de features.
        nome_modelo: Nome do algoritmo ('RF' ou 'XGB').
        parametros: Dicionário de hiperparâmetros.
        ano_teste: Ano inicial de corte.
        
    Retorna:
        TuningResult: NamedTuple contendo estimador, predições, métricas e features.
    """
    treino, teste = dividir_treino_teste_temporal(df, ano_teste)
    spec = obter_configuracao_features(config)

    # Preparar frames limpos
    treino_frame = _preparar_entrada_pipeline(treino, config)
    teste_frame = _preparar_entrada_pipeline(teste, config)

    # Construir pipeline scikit-learn (OHE isolado por fold)
    modelo = fabrica_modelos(nome_modelo, parametros)
    pipeline = construir_pipeline_modelo(config, modelo)

    # Colunas de entrada do pipeline
    colunas_pipeline = obter_colunas_entrada_pipeline(config)
    X_treino = treino_frame[colunas_pipeline]
    y_treino = treino_frame[spec["target"]].astype(float)

    # Fit (log1p do target é feito pelo TransformedTargetRegressor internamente)
    pipeline.fit(X_treino, y_treino)

    # Predict (expm1 do target é automático via TransformedTargetRegressor)
    predicoes = _prever_com_pipeline(pipeline, teste_frame, config, spec)

    pred_df = teste_frame[["epi_sunday", "RA", "cases", "incidencia_100k", "populacao"]].copy()
    pred_df["prediction"] = predicoes
    
    metricas, ra_metricas = consolidar_metricas_performance(pred_df)
    return TuningResult(
        model=pipeline,
        predictions=pred_df,
        metrics=metricas,
        ra_metrics=ra_metricas,
        features=colunas_pipeline,
    )


def cv_score_parametros(df: pd.DataFrame, config: str, nome_modelo: str, parametros: dict) -> float:
    """
    Calcula o score de validação cruzada temporal (TimeSeriesSplit) para um conjunto de parâmetros.
    Usa Pipeline scikit-learn para garantir que OneHotEncoder é fitado apenas no treino de cada fold.
    
    Parâmetros:
        df: DataFrame original.
        config: Configuração de features.
        nome_modelo: Algoritmo ('RF' ou 'XGB').
        parametros: Hiperparâmetros a serem validados.
        
    Retorna:
        float: RMSE médio da validação cruzada temporal.
    """
    treino_completo, _ = dividir_treino_teste_temporal(df, 2025)
    datas = np.array(sorted(treino_completo["epi_sunday"].unique()))
    # gap=4: exclui as 4 semanas imediatamente anteriores à validação do treino.
    # Isso simula o atraso típico de notificação epidemiológica (~4 semanas)
    # e evita que dados da borda de treino "contaminem" a validação via lags recentes.
    splitter = TimeSeriesSplit(n_splits=5, gap=4)
    spec = obter_configuracao_features(config)
    colunas_pipeline = obter_colunas_entrada_pipeline(config)

    fold_rmses = []
    for train_idx, val_idx in splitter.split(datas):
        train_dates = set(datas[train_idx])
        val_dates = set(datas[val_idx])
        fold_train = treino_completo[treino_completo["epi_sunday"].isin(train_dates)]
        fold_val = treino_completo[treino_completo["epi_sunday"].isin(val_dates)]

        # Preparar frames limpos
        fold_train_clean = _preparar_entrada_pipeline(fold_train, config)
        fold_val_clean = _preparar_entrada_pipeline(fold_val, config)

        if fold_train_clean.empty or fold_val_clean.empty:
            continue

        # Pipeline reconstruído por fold — OHE é fitado isoladamente no treino do fold
        modelo = fabrica_modelos(nome_modelo, parametros)
        pipeline = construir_pipeline_modelo(config, modelo)

        X_train = fold_train_clean[colunas_pipeline]
        y_train = fold_train_clean[spec["target"]].astype(float)

        pipeline.fit(X_train, y_train)

        preds = _prever_com_pipeline(pipeline, fold_val_clean, config, spec)
        fold_rmses.append(calcular_erro_quadratico_medio(fold_val_clean["cases"], preds))
        
    return float(np.mean(fold_rmses))

def otimizar_hiperparametros(df: pd.DataFrame, config: str, run_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executa busca de parâmetros em grade (Grid Search) usando validação cruzada temporal.
    Salva os melhores modelos serializados na pasta resultados_modelagem/ e gera as previsões finais de teste.
    
    Parâmetros:
        df: DataFrame completo.
        config: Configuração de features ideal (vencedora).
        run_dir (Path, opcional): Subdiretório versionado para salvar resultados desta execução.
        
    Retorna:
        tuple: (df_tuning_resultados, df_previsoes_finais_tunadas)
    """
    logger.info(f">>> P1: tuning RF e XGBoost na config {config}...")
    # Grid otimizado com os melhores parâmetros encontrados anteriormente para aceleração de re-execução
    param_grid_rf = {
        "n_estimators": [500],
        "max_depth": [None],
        "min_samples_leaf": [1],
        "max_features": ["sqrt"],
    }
    param_grid_xgb = {
        "n_estimators": [500],
        "max_depth": [3],
        "learning_rate": [0.1],
        "subsample": [1.0],
        "colsample_bytree": [0.8],
    }
    
    rows = []
    for model_name, grid in [("RF", param_grid_rf), ("XGB", param_grid_xgb)]:
        grid_list = list(ParameterGrid(grid))
        for i, params in enumerate(grid_list, start=1):
            logger.info(f"  - {model_name} grid {i}/{len(grid_list)}")
            score = cv_score_parametros(df, config, model_name, params)
            rows.append({"modelo": model_name, "config": config, "cv_rmse": score, "params": json.dumps(params)})
            
    tuning = pd.DataFrame(rows).sort_values(["modelo", "cv_rmse"])
    
    tuning_csv = run_dir / "resultados_otimizacao_nowcasting.csv" if run_dir else (BASE_DIR / "resultados_modelagem" / "resultados_otimizacao_nowcasting.csv")
    tuning.to_csv(tuning_csv, index=False)
    if run_dir:
        tuning.to_csv(BASE_DIR / "resultados_modelagem" / "resultados_otimizacao_nowcasting.csv", index=False)

    final_pred_rows = []
    model_output_dir = run_dir if run_dir else MODELOS_DIR
    model_output_dir.mkdir(exist_ok=True, parents=True)
    MODELOS_DIR.mkdir(exist_ok=True)
    
    for model_name in ["RF", "XGB"]:
        best = tuning[tuning["modelo"].eq(model_name)].iloc[0]
        params = json.loads(best["params"])
        pipeline, pred_df, metrics, _, features = executar_ajuste_previsao(df, config, model_name, parametros=params)
        
        joblib_name = "modelo_rf_nowcasting.joblib" if model_name == "RF" else "modelo_xgb_nowcasting.joblib"
        out_path = model_output_dir / joblib_name
        dump({"model": pipeline, "config": config, "features": features, "params": params, "metrics": metrics}, out_path)
        if run_dir:
            dump({"model": pipeline, "config": config, "features": features, "params": params, "metrics": metrics}, MODELOS_DIR / joblib_name)
        
        tmp = pred_df.copy()
        tmp["modelo"] = f"{model_name}_tunado"
        tmp["config"] = config
        final_pred_rows.append(tmp)

    final_predictions = pd.concat(final_pred_rows, ignore_index=True)
    
    final_pred_csv = run_dir / "predicoes_nowcasting_operacional.csv" if run_dir else (BASE_DIR / "resultados_modelagem" / "predicoes_nowcasting_operacional.csv")
    final_predictions.to_csv(final_pred_csv, index=False)
    if run_dir:
        final_predictions.to_csv(BASE_DIR / "resultados_modelagem" / "predicoes_nowcasting_operacional.csv", index=False)
    
    return tuning, final_predictions
