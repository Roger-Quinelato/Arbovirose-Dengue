# -*- coding: utf-8 -*-
"""
Módulo de Orquestração do Pipeline de Modelagem de Dengue.

Responsável por fluxos experimentais de alto nível que acionam simultaneamente
as etapas de treinamento (train_tuning) e de avaliação (evaluation), eliminando
dependências circulares entre os módulos.
"""

import json
import itertools
from pathlib import Path
import numpy as np
import pandas as pd

from dengue_pipeline.modeling.feature_engineering import (
    obter_configuracao_features,
    obter_colunas_entrada_pipeline,
    construir_pipeline_modelo,
)
from dengue_pipeline.modeling.train_tuning import (
    executar_ajuste_previsao,
    dividir_treino_teste_temporal,
    fabrica_modelos,
    _preparar_entrada_pipeline,
    _prever_com_pipeline,
)
from dengue_pipeline.modeling.evaluation import (
    consolidar_metricas_performance,
)
from dengue_pipeline.modeling.conformal_prediction import (
    calibrar_intervalos_confianca,
    aplicar_limites_confianca,
    salvar_calibracao,
)
from dengue_pipeline.modeling.types import AblationResult

import logging
logger = logging.getLogger(__name__)
from dengue_pipeline.config import (
    BASE_DIR,
    MODELOS_DIR,
    ABLATION_CSV,
    ABLATION_RA_CSV,
    ABLATION_PRED_CSV,
    WINNER_JSON,
    ROLLING_RESULTS_CSV,
)


def executar_estudo_ablacao(df: pd.DataFrame, run_dir: Path | None = None) -> AblationResult:
    """
    Executa testes de ablação sistemáticos variando a complexidade das features
    (lag-only, lag+clima, lag+clima+RA, lag+clima+RA+incid-target) e algoritmos (RF, XGB).
    Determina a configuração vencedora baseado em critérios estritos de ganho de desempenho.
    
    Parâmetros:
        df (pd.DataFrame): Dataset completo de entrada.
        run_dir (Path, opcional): Subdiretório versionado para salvar resultados desta execução.
        
    Retorna:
        AblationResult: NamedTuple contendo sumário do estudo de ablação, a especificação vencedora e todas as métricas brutas.
    """
    logger.info(">>> P1: executando ablation tests...")
    configs = [
        "lag-only",
        "lag+clima",
        "lag+clima+RA",
        "lag+clima+RA+incid-target",
    ]
    models = ["RF", "XGB"]
    rows = []
    ra_rows = []
    pred_rows = []
    ra_by_key = {}
    raw_metrics_dict = {}

    for config, model_name in itertools.product(configs, models):
        logger.info(f"  - {config} / {model_name}")
        model, pred_df, metrics, ra_metrics, features = executar_ajuste_previsao(df, config, model_name)
        key = (config, model_name)
        ra_by_key[key] = ra_metrics
        raw_metrics_dict[f"{config}/{model_name}"] = metrics
        rows.append(
            {
                "config": config,
                "modelo": model_name,
                "n_features": len(features),
                **metrics,
            }
        )
        tmp_ra = ra_metrics.copy()
        tmp_ra["config"] = config
        tmp_ra["modelo"] = model_name
        ra_rows.append(tmp_ra)
        
        tmp_pred = pred_df.copy()
        tmp_pred["config"] = config
        tmp_pred["modelo"] = model_name
        pred_rows.append(tmp_pred)

    result = pd.DataFrame(rows)
    ra_result = pd.concat(ra_rows, ignore_index=True)
    pred_result = pd.concat(pred_rows, ignore_index=True)

    for model_name in models:
        prev_config = None
        for config in configs:
            idx = (result["config"].eq(config)) & (result["modelo"].eq(model_name))
            if prev_config is None:
                result.loc[idx, "delta_r2_df_vs_prev"] = np.nan
                result.loc[idx, "rmse_improved_pct_vs_prev"] = np.nan
                result.loc[idx, "passes_acceptance_vs_prev"] = False
            else:
                cur = result.loc[idx].iloc[0]
                prev = result[
                    result["config"].eq(prev_config) & result["modelo"].eq(model_name)
                ].iloc[0]
                cur_ra = ra_by_key[(config, model_name)].set_index("RA")
                prev_ra = ra_by_key[(prev_config, model_name)].set_index("RA")
                aligned = cur_ra.join(prev_ra, lsuffix="_cur", rsuffix="_prev")
                improved_pct = float((aligned["rmse_ra_cur"] < aligned["rmse_ra_prev"]).mean())
                delta = float(cur["r2_df"] - prev["r2_df"])
                
                result.loc[idx, "delta_r2_df_vs_prev"] = delta
                result.loc[idx, "rmse_improved_pct_vs_prev"] = improved_pct
                result.loc[idx, "passes_acceptance_vs_prev"] = (delta > 0.05) or (improved_pct > 0.70)
            prev_config = config

    baseline_best = result[result["config"].eq("lag-only")].sort_values("r2_df", ascending=False).iloc[0]
    best_observed = result.sort_values("r2_df", ascending=False).iloc[0]
    best_ra = ra_by_key[(best_observed["config"], best_observed["modelo"])].set_index("RA")
    base_ra = ra_by_key[(baseline_best["config"], baseline_best["modelo"])].set_index("RA")
    
    aligned = best_ra.join(base_ra, lsuffix="_best", rsuffix="_base")
    best_delta = float(best_observed["r2_df"] - baseline_best["r2_df"])
    best_improved_pct = float((aligned["rmse_ra_best"] < aligned["rmse_ra_base"]).mean())
    accepted = (best_delta > 0.05) or (best_improved_pct > 0.70)
    
    if accepted:
        winner_row = best_observed
        winner_reason = "Melhor config superou o baseline pelo criterio de aceite."
    else:
        winner_row = baseline_best
        winner_reason = "Nenhuma config complexa superou o baseline; lag-only vence por conservadorismo."
        
    import os
    winner = {
        "seed": int(os.getenv("PIPELINE_SEED", "42")),
        "config": str(winner_row["config"]),
        "modelo": str(winner_row["modelo"]),
        "r2_df": float(winner_row["r2_df"]),
        "rmse_df": float(winner_row["rmse_df"]),
        "accepted_complex_gain": bool(accepted),
        "best_observed_config": str(best_observed["config"]),
        "best_observed_modelo": str(best_observed["modelo"]),
        "best_delta_r2_vs_baseline": best_delta,
        "best_rmse_improved_pct_vs_baseline": best_improved_pct,
        "reason": winner_reason,
    }

    out_ablation_csv = run_dir / "resultados_ablacao_nowcasting.csv" if run_dir else ABLATION_CSV
    out_ablation_ra_csv = run_dir / "resultados_ablation_por_ra.csv" if run_dir else ABLATION_RA_CSV
    out_ablation_pred_csv = run_dir / "predicoes_ablation.csv" if run_dir else ABLATION_PRED_CSV
    out_winner_json = run_dir / "campeao_ablacao_nowcasting.json" if run_dir else WINNER_JSON

    result.to_csv(out_ablation_csv, index=False)
    if run_dir:
        result.to_csv(ABLATION_CSV, index=False)

    ra_result.to_csv(out_ablation_ra_csv, index=False)
    if run_dir:
        ra_result.to_csv(ABLATION_RA_CSV, index=False)

    pred_result.to_csv(out_ablation_pred_csv, index=False)
    if run_dir:
        pred_result.to_csv(ABLATION_PRED_CSV, index=False)

    out_winner_json.write_text(json.dumps(winner, indent=2, ensure_ascii=False), encoding="utf-8")
    if run_dir:
        WINNER_JSON.write_text(json.dumps(winner, indent=2, ensure_ascii=False), encoding="utf-8")
    
    return AblationResult(
        ablation_summary=result,
        winner_specification=winner,
        all_metrics=raw_metrics_dict,
    )


def executar_validacao_temporal(df: pd.DataFrame, run_dir: Path | None = None) -> pd.DataFrame:
    """
    Executa a validação temporal em janela móvel (rolling validation) comparando
    o nowcasting tradicional (janela de 1 semana) com o forecast fechado recursivo (múltiplas semanas).
    
    Usa Pipeline scikit-learn para garantir isolamento de dados e aplica Conformal Prediction
    com calibração específica por horizonte (horizon-specific).
    
    Parâmetros:
        df: DataFrame com o dataset completo processado.
        run_dir (Path, opcional): Subdiretório versionado para salvar resultados desta execução.
        
    Retorna:
        pd.DataFrame: Métricas resultantes consolidadas da validação rolling.
    """
    logger.info(">>> P1: executando rolling validation nowcasting vs forecast fechado...")
    
    config = "lag+clima+RA"
    pipeline_now, pred_now, now_metrics, _, _ = executar_ajuste_previsao(df, config, "RF", ano_teste=2025)

    train, test = dividir_treino_teste_temporal(df, 2025)
    spec = obter_configuracao_features(config)
    colunas_pipeline = obter_colunas_entrada_pipeline(config)

    # Treinar pipeline para forecast fechado recursivo
    train_frame = _preparar_entrada_pipeline(train, config)
    modelo_rf = fabrica_modelos("RF")
    pipeline_rf = construir_pipeline_modelo(config, modelo_rf)

    X_train = train_frame[colunas_pipeline]
    y_train = train_frame[spec["target"]].astype(float)
    pipeline_rf.fit(X_train, y_train)

    history = {
        ra: list(group.sort_values("epi_sunday")["cases"].astype(float).values)
        for ra, group in train.groupby("RA")
    }
    
    def obter_lag_cases(ra: str, lag_val: int) -> float:
        ra_history = history.get(ra, [])
        if len(ra_history) >= lag_val:
            return ra_history[-lag_val]
        return np.nan

    recursive_rows = []
    test_sorted = test.sort_values(["epi_sunday", "RA"]).copy()
    for date in sorted(test_sorted["epi_sunday"].unique()):
        rows = test_sorted[test_sorted["epi_sunday"].eq(date)].copy()
        for lag in [1, 2, 3, 4]:
            rows[f"cases_lag_{lag}"] = rows["RA"].map(
                lambda ra, lag_val=lag: obter_lag_cases(ra, lag_val)
            )

        rows_clean = _preparar_entrada_pipeline(rows, config)
        if rows_clean.empty:
            continue
        preds = _prever_com_pipeline(pipeline_rf, rows_clean, config, spec)
        rows_frame = rows_clean[["epi_sunday", "RA", "cases", "incidencia_100k", "populacao"]].copy()
        rows_frame["prediction"] = preds
        
        for ra, pred in zip(rows_frame["RA"], preds):
            history.setdefault(ra, []).append(float(pred))
        recursive_rows.append(rows_frame)
        
    pred_closed = pd.concat(recursive_rows, ignore_index=True)
    closed_metrics, _ = consolidar_metricas_performance(pred_closed)

    # -----------------------------------------------------------------------
    # Conformal Prediction — Calibração Específica por Horizonte (TDD-01)
    # -----------------------------------------------------------------------
    
    # Usar as últimas 26 semanas do treino como conjunto de calibração conformal
    # (equivalente a ~6 meses — captura padrão sazonal de alta e baixa transmissão)
    n_cal_weeks = 26
    cal_dates = sorted(train["epi_sunday"].unique())[-n_cal_weeks:]
    df_cal_raw = train[train["epi_sunday"].isin(cal_dates)].copy()
    
    # Gerar previsões para o conjunto de calibração usando o mesmo pipeline
    try:
        cal_frame = _preparar_entrada_pipeline(df_cal_raw, config)
        if not cal_frame.empty:
            preds_cal = _prever_com_pipeline(pipeline_rf, cal_frame, config, spec)
            df_cal = cal_frame[["epi_sunday", "RA", "cases"]].copy()
            df_cal["prediction"] = preds_cal

            # Atribuir horizonte_k=1 para dados de calibração (nowcasting)
            # Para calibração multi-horizonte, idealmente os dados devem conter
            # previsões feitas em diferentes horizontes. Aqui, usamos a posição
            # temporal relativa dentro da janela de calibração como proxy.
            df_cal = df_cal.sort_values(["RA", "epi_sunday"]).copy()
            df_cal["horizonte_k"] = df_cal.groupby("RA").cumcount() + 1
            # Limitar ao número máximo de horizontes razoável (K_max = 4 semanas)
            K_MAX = 4
            df_cal["horizonte_k"] = df_cal["horizonte_k"].clip(upper=K_MAX)

            # Calibrar os scores de não-conformidade (horizon-specific + epsilon adaptativo)
            calibracao = calibrar_intervalos_confianca(df_cal, alpha=0.10, epsilon_min=0.10)
            salvar_calibracao(calibracao, run_dir=run_dir)
            
            # Aplicar intervalos no nowcasting (horizonte k=1)
            pred_now_ci = pred_now.copy()
            pred_now_ci["horizonte_k"] = 1
            pred_now_ci = aplicar_limites_confianca(pred_now_ci, calibracao)
            pred_now_ci = pred_now_ci.drop(columns=["horizonte_k"])
            
            # Aplicar intervalos no forecast fechado com horizonte k por RA (vetorizado)
            pred_closed_ci = pred_closed.copy()
            pred_closed_ci["horizonte_k"] = pred_closed_ci.groupby("RA").cumcount() + 1
            pred_closed_ci["horizonte_k"] = pred_closed_ci["horizonte_k"].clip(upper=K_MAX)
            pred_closed_ci = aplicar_limites_confianca(pred_closed_ci, calibracao)
            pred_closed_ci = pred_closed_ci.drop(columns=["horizonte_k"])
        else:
            pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
            pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as e:
        logger.warning("Conformal prediction falhou com erro numérico esperado: %s", e, exc_info=True)
        pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
        pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)

    result = pd.DataFrame(
        [
            {"modo": "nowcasting_rolling", **now_metrics},
            {"modo": "forecast_fechado_recursivo", **closed_metrics},
        ]
    )
    
    rolling_results_csv = run_dir / "rolling_validation_resultados.csv" if run_dir else ROLLING_RESULTS_CSV
    result.to_csv(rolling_results_csv, index=False)
    if run_dir:
        result.to_csv(ROLLING_RESULTS_CSV, index=False)
    
    pred_rolling_csv = run_dir / "predicoes_rolling_nowcasting.csv" if run_dir else (BASE_DIR / "resultados_modelagem" / "predicoes_rolling_nowcasting.csv")
    pred_now_ci.assign(modo="nowcasting_rolling").to_csv(pred_rolling_csv, index=False)
    if run_dir:
        pred_now_ci.assign(modo="nowcasting_rolling").to_csv(BASE_DIR / "resultados_modelagem" / "predicoes_rolling_nowcasting.csv", index=False)
        
    pred_forecast_csv = run_dir / "predicoes_forecast_fechado.csv" if run_dir else (BASE_DIR / "resultados_modelagem" / "predicoes_forecast_fechado.csv")
    pred_closed_ci.assign(modo="forecast_fechado_recursivo").to_csv(pred_forecast_csv, index=False)
    if run_dir:
        pred_closed_ci.assign(modo="forecast_fechado_recursivo").to_csv(BASE_DIR / "resultados_modelagem" / "predicoes_forecast_fechado.csv", index=False)
    
    return result
