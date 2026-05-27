import json
import numpy as np
import pandas as pd
from pathlib import Path
from joblib import dump
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import ParameterGrid, TimeSeriesSplit
from xgboost import XGBRegressor

from dengue_pipeline.modeling.feature_engineering import preparar_design, especificacao_features

BASE_DIR = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = BASE_DIR / "scripts"
ROLLING_RESULTS_CSV = BASE_DIR / "resultados_modelagem" / "rolling_validation_resultados.csv"

def separar_treino_teste(df: pd.DataFrame, ano_teste: int = 2025) -> tuple[pd.DataFrame, pd.DataFrame]:
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

def fabrica_modelo(nome_modelo: str, parametros: dict | None = None):
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

def prever_casos(model, X: pd.DataFrame, frame: pd.DataFrame, spec: dict) -> np.ndarray:
    """
    Realiza a previsão de casos usando o modelo treinado, desfazendo a escala logarítmica
    e convertendo incidência para número de casos absolutos quando necessário.
    
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

def ajustar_prever_config(
    df: pd.DataFrame,
    config: str,
    nome_modelo: str,
    parametros: dict | None = None,
    ano_teste: int = 2025,
):
    """
    Ajusta e prediz usando uma configuração de features e modelo específicos.
    Auxilia no isolamento de modelagem e testes de ablação.
    
    Parâmetros:
        df: DataFrame completo.
        config: Identificador da configuração de features.
        nome_modelo: Nome do algoritmo ('RF' ou 'XGB').
        parametros: Dicionário de hiperparâmetros.
        ano_teste: Ano inicial de corte.
        
    Retorna:
        tuple: (modelo_treinado, pred_df, metricas, ra_metricas, features_list)
    """
    # Evitar import circular
    from dengue_pipeline.modeling.evaluation import agregar_metricas
    
    treino, teste = separar_treino_teste(df, ano_teste)
    spec = especificacao_features(config)
    dummy_columns = None
    if spec["ra"]:
        # Dummies derivadas exclusivamente do conjunto de treino para evitar
        # que RAs presentes apenas no teste influenciem a estrutura do modelo.
        dummy_columns = pd.get_dummies(treino["RA"], prefix="RA", dtype=float).columns.tolist()
        
    X_treino, y_treino, treino_frame, features, spec = preparar_design(treino, config, dummy_columns)
    X_teste, y_teste, teste_frame, _, spec = preparar_design(teste, config, dummy_columns)
    
    modelo = fabrica_modelo(nome_modelo, parametros)
    modelo.fit(X_treino, y_treino)
    predicoes = prever_casos(modelo, X_teste, teste_frame, spec)
    pred_df = teste_frame[["epi_sunday", "RA", "cases", "incidencia_100k", "populacao"]].copy()
    pred_df["prediction"] = predicoes
    
    metricas, ra_metricas = agregar_metricas(pred_df)
    return modelo, pred_df, metricas, ra_metricas, features

def cv_score_parametros(df: pd.DataFrame, config: str, nome_modelo: str, parametros: dict) -> float:
    """
    Calcula o score de validação cruzada temporal (TimeSeriesSplit) para um conjunto de parâmetros.
    
    Parâmetros:
        df: DataFrame original.
        config: Configuração de features.
        nome_modelo: Algoritmo ('RF' ou 'XGB').
        parametros: Hiperparâmetros a serem validados.
        
    Retorna:
        float: RMSE médio da validação cruzada temporal.
    """
    # Evitar import circular
    from dengue_pipeline.modeling.evaluation import rmse
    
    treino_completo, _ = separar_treino_teste(df, 2025)
    datas = np.array(sorted(treino_completo["epi_sunday"].unique()))
    # gap=4: exclui as 4 semanas imediatamente anteriores à validação do treino.
    # Isso simula o atraso típico de notificação epidemiológica (~4 semanas)
    # e evita que dados da borda de treino "contaminem" a validação via lags recentes.
    splitter = TimeSeriesSplit(n_splits=5, gap=4)
    spec = especificacao_features(config)
    dummy_columns = None
    if spec["ra"]:
        # Dummies calculadas sobre treino_completo (não sobre df inteiro que inclui 2025)
        dummy_columns = pd.get_dummies(treino_completo["RA"], prefix="RA", dtype=float).columns.tolist()
        
    fold_rmses = []
    for train_idx, val_idx in splitter.split(datas):
        train_dates = set(datas[train_idx])
        val_dates = set(datas[val_idx])
        fold_train = treino_completo[treino_completo["epi_sunday"].isin(train_dates)]
        fold_val = treino_completo[treino_completo["epi_sunday"].isin(val_dates)]
        
        X_train, y_train, _, _, spec = preparar_design(fold_train, config, dummy_columns)
        X_val, _, val_frame, _, spec = preparar_design(fold_val, config, dummy_columns)
        
        if X_train.empty or X_val.empty:
            continue
            
        model = fabrica_modelo(nome_modelo, parametros)
        model.fit(X_train, y_train)
        
        preds = prever_casos(model, X_val, val_frame, spec)
        fold_rmses.append(rmse(val_frame["cases"], preds))
        
    return float(np.mean(fold_rmses))

def tunar_modelos(df: pd.DataFrame, config: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executa busca de parâmetros em grade (Grid Search) usando validação cruzada temporal.
    Salva os melhores modelos serializados na pasta scripts/ e gera as previsões finais de teste.
    
    Parâmetros:
        df: DataFrame completo.
        config: Configuração de features ideal (vencedora).
        
    Retorna:
        tuple: (df_tuning_resultados, df_previsoes_finais_tunadas)
    """
    print(f">>> P1: tuning RF e XGBoost na config {config}...")
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
            print(f"  - {model_name} grid {i}/{len(grid_list)}")
            score = cv_score_parametros(df, config, model_name, params)
            rows.append({"modelo": model_name, "config": config, "cv_rmse": score, "params": json.dumps(params)})
            
    tuning = pd.DataFrame(rows).sort_values(["modelo", "cv_rmse"])
    tuning.to_csv(BASE_DIR / "resultados_tuning.csv", index=False)

    final_pred_rows = []
    SCRIPTS_DIR.mkdir(exist_ok=True)
    for model_name in ["RF", "XGB"]:
        best = tuning[tuning["modelo"].eq(model_name)].iloc[0]
        params = json.loads(best["params"])
        model, pred_df, metrics, _, features = ajustar_prever_config(df, config, model_name, parametros=params)
        
        out_path = SCRIPTS_DIR / ("modelo_rf_tunado.joblib" if model_name == "RF" else "modelo_xgb_tunado.joblib")
        dump({"model": model, "config": config, "features": features, "params": params, "metrics": metrics}, out_path)
        
        tmp = pred_df.copy()
        tmp["modelo"] = f"{model_name}_tunado"
        tmp["config"] = config
        final_pred_rows.append(tmp)

    final_predictions = pd.concat(final_pred_rows, ignore_index=True)
    final_predictions.to_csv(BASE_DIR / "predicoes_modelos_finais.csv", index=False)
    
    return tuning, final_predictions

def executar_validacao_rolling(df: pd.DataFrame) -> pd.DataFrame:
    """
    Executa a validação temporal em janela móvel (rolling validation) comparando
    o nowcasting tradicional (janela de 1 semana) com o forecast fechado recursivo (múltiplas semanas).
    
    Parâmetros:
        df: DataFrame com o dataset completo processado.
        
    Retorna:
        pd.DataFrame: Métricas resultantes consolidadas da validação rolling.
    """
    print(">>> P1: executando rolling validation nowcasting vs forecast fechado...")
    from dengue_pipeline.modeling.evaluation import agregar_metricas
    
    config = "lag+clima+RA"
    model, pred_now, now_metrics, _, _ = ajustar_prever_config(df, config, "RF", ano_teste=2025)

    train, test = separar_treino_teste(df, 2025)
    spec = especificacao_features(config)
    dummy_columns = pd.get_dummies(df["RA"], prefix="RA", dtype=float).columns.tolist()
    X_train, y_train, train_frame, features, spec = preparar_design(train, config, dummy_columns)
    
    rf = fabrica_modelo("RF")
    rf.fit(X_train, y_train)

    history = {
        ra: list(group.sort_values("epi_sunday")["cases"].astype(float).values)
        for ra, group in train.groupby("RA")
    }
    
    recursive_rows = []
    test_sorted = test.sort_values(["epi_sunday", "RA"]).copy()
    for date in sorted(test_sorted["epi_sunday"].unique()):
        rows = test_sorted[test_sorted["epi_sunday"].eq(date)].copy()
        for lag in [1, 2, 3, 4]:
            rows[f"cases_lag_{lag}"] = rows["RA"].map(
                lambda ra, lag=lag: history.get(ra, [np.nan] * lag)[-lag]
                if len(history.get(ra, [])) >= lag
                else np.nan
            )
        X_rows, _, rows_frame, _, _ = preparar_design(rows, config, dummy_columns)
        if rows_frame.empty:
            continue
        preds = prever_casos(rf, X_rows, rows_frame, spec)
        rows_frame = rows_frame[["epi_sunday", "RA", "cases", "incidencia_100k", "populacao"]].copy()
        rows_frame["prediction"] = preds
        
        for ra, pred in zip(rows_frame["RA"], preds):
            history.setdefault(ra, []).append(float(pred))
        recursive_rows.append(rows_frame)
        
    pred_closed = pd.concat(recursive_rows, ignore_index=True)
    closed_metrics, _ = agregar_metricas(pred_closed)

    # -----------------------------------------------------------------------
    # Conformal Prediction — Intervalos de Confiança Calibrados Dinâmicos (90%)
    # -----------------------------------------------------------------------
    from dengue_pipeline.modeling.conformal_prediction import (
        calibrar_conformal, aplicar_intervalos, salvar_calibracao
    )
    
    # Usar as últimas 26 semanas do treino como conjunto de calibração conformal
    # (equivalente a ~6 meses — captura padrão sazonal de alta e baixa transmissão)
    n_cal_weeks = 26
    cal_dates = sorted(train["epi_sunday"].unique())[-n_cal_weeks:]
    df_cal_raw = train[train["epi_sunday"].isin(cal_dates)].copy()
    
    # Gerar previsões para o conjunto de calibração usando o mesmo modelo
    try:
        # Filtrar apenas as semanas de calibração (as últimas do treino)
        cal_dummies = pd.get_dummies(train["RA"], prefix="RA", dtype=float).columns.tolist()
        X_cal, _, cal_frame, _, _ = preparar_design(df_cal_raw, config, cal_dummies)
        if not X_cal.empty:
            preds_cal = prever_casos(rf, X_cal, cal_frame, spec)
            df_cal = cal_frame[["epi_sunday", "RA", "cases"]].copy()
            df_cal["prediction"] = preds_cal
            
            # Calibrar os scores de não-conformidade (dinâmicos)
            calibracao = calibrar_conformal(df_cal, alpha=0.10)
            salvar_calibracao(calibracao)
            
            # Aplicar intervalos no nowcasting (horizonte k=1)
            pred_now_ci = aplicar_intervalos(pred_now, calibracao, horizonte_k=1)
            
            # Aplicar intervalos no forecast fechado com expansão pelo horizonte k (vetorizado)
            pred_closed_ci = pred_closed.copy()
            pred_closed_ci["step_k"] = pred_closed_ci.groupby("RA").cumcount() + 1
            pred_closed_ci = aplicar_intervalos(pred_closed_ci, calibracao, horizonte_k=pred_closed_ci["step_k"])
            pred_closed_ci = pred_closed_ci.drop(columns=["step_k"])
        else:
            pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
            pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)
    except Exception as e:
        print(f"  [AVISO] Conformal prediction falhou: {e}. Salvando sem intervalos de confiança.")
        pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
        pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)

    result = pd.DataFrame(
        [
            {"modo": "nowcasting_rolling", **now_metrics},
            {"modo": "forecast_fechado_recursivo", **closed_metrics},
        ]
    )
    result.to_csv(ROLLING_RESULTS_CSV, index=False)
    
    pred_now_ci.assign(modo="nowcasting_rolling").to_csv(
        BASE_DIR / "resultados_modelagem" / "predicoes_rolling_nowcasting.csv", index=False
    )
    pred_closed_ci.assign(modo="forecast_fechado_recursivo").to_csv(
        BASE_DIR / "resultados_modelagem" / "predicoes_forecast_fechado.csv", index=False
    )
    
    return result
