import json
import itertools
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = Path(__file__).resolve().parents[3]
ABLATION_CSV = BASE_DIR / "resultados_modelagem" / "resultados_ablacao_nowcasting.csv"
ABLATION_RA_CSV = BASE_DIR / "resultados_modelagem" / "resultados_ablation_por_ra.csv"
ABLATION_PRED_CSV = BASE_DIR / "resultados_modelagem" / "predicoes_ablation.csv"
WINNER_JSON = BASE_DIR / "resultados_modelagem" / "campeao_ablacao_nowcasting.json"

def calcular_r2_robusto(y_true, y_pred) -> float:
    """
    Calcula o coeficiente de determinação (R²) de forma segura, tratando casos com variância
    nula ou número insuficiente de amostras retornando NaN ao invés de erro.
    
    Parâmetros:
        y_true: Valores reais.
        y_pred: Valores previstos.
        
    Retorna:
        float: Valor de R² ou float("nan").
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) < 2 or np.isclose(np.var(y_true), 0.0):
        return float("nan")
    return float(r2_score(y_true, y_pred))

def calcular_erro_quadratico_medio(y_true, y_pred) -> float:
    """
    Calcula a raiz do erro quadrático médio (RMSE).
    
    Parâmetros:
        y_true: Valores reais.
        y_pred: Valores previstos.
        
    Retorna:
        float: RMSE.
    """
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))

def consolidar_metricas_performance(pred_df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """
    Consolida métricas globais para o DF e individuais por Região Administrativa (RA).
    Calcula R², MAE e RMSE para ambas as escalas.
    
    Parâmetros:
        pred_df (pd.DataFrame): DataFrame contendo as colunas 'epi_sunday', 'RA', 'cases' e 'prediction'.
        
    Retorna:
        tuple: (dicionario_metricas_globais, dataframe_metricas_por_ra)
    """
    df_total = pred_df.groupby("epi_sunday", as_index=False)[["cases", "prediction"]].sum()
    
    # Métricas base
    r2 = calcular_r2_robusto(df_total["cases"], df_total["prediction"])
    mae = float(mean_absolute_error(df_total["cases"], df_total["prediction"]))
    rmse_val = calcular_erro_quadratico_medio(df_total["cases"], df_total["prediction"])
    
    # MAPE — apenas para semanas com casos > 0 (evita divisão por zero)
    nonzero = df_total[df_total["cases"] > 0].copy()
    mape_val = float(
        ((nonzero["cases"] - nonzero["prediction"]).abs() / nonzero["cases"] * 100).mean()
    ) if len(nonzero) > 0 else float("nan")
    
    # sMAPE — simétrico, robusto a casos próximos de zero
    denom = df_total["cases"].abs() + df_total["prediction"].abs() + 1e-8
    smape_val = float(
        (2 * (df_total["cases"] - df_total["prediction"]).abs() / denom * 100).mean()
    )
    
    # Hit Rate de Picos — % de semanas de pico real corretamente sinalizadas
    # Pico definido como acima do percentil 75 das semanas de teste
    peak_threshold = df_total["cases"].quantile(0.75)
    is_peak_real = df_total["cases"] >= peak_threshold
    is_peak_pred = df_total["prediction"] >= peak_threshold
    hit_rate = float(
        (is_peak_real & is_peak_pred).sum() / is_peak_real.sum()
    ) if is_peak_real.sum() > 0 else float("nan")
    
    metrics = {
        "r2_df": r2,
        "mae_df": mae,
        "rmse_df": rmse_val,
        "mape_df": mape_val,
        "smape_df": smape_val,
        "hit_rate_picos": hit_rate,
    }
    
    rows = []
    for ra, group in pred_df.groupby("RA"):
        rows.append(
            {
                "RA": ra,
                "r2_ra": calcular_r2_robusto(group["cases"], group["prediction"]),
                "mae_ra": float(mean_absolute_error(group["cases"], group["prediction"])),
                "rmse_ra": calcular_erro_quadratico_medio(group["cases"], group["prediction"]),
            }
        )
    ra_df = pd.DataFrame(rows)
    metrics["r2_media_ras"] = float(ra_df["r2_ra"].mean(skipna=True))
    metrics["mae_media_ras"] = float(ra_df["mae_ra"].mean(skipna=True))
    metrics["rmse_media_ras"] = float(ra_df["rmse_ra"].mean(skipna=True))
    return metrics, ra_df

def executar_estudo_ablacao(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Executa testes de ablação sistemáticos variando a complexidade das features
    (lag-only, lag+clima, lag+clima+RA, lag+clima+RA+incid-target) e algoritmos (RF, XGB).
    Determina a configuração vencedora baseado em critérios estritos de ganho de desempenho.
    
    Parâmetros:
        df (pd.DataFrame): Dataset completo de entrada.
        
    Retorna:
        tuple: (df_resultados_ablation, dict_especificacao_vencedora)
    """
    print(">>> P1: executando ablation tests...")
    from dengue_pipeline.modeling.train_tuning import executar_ajuste_previsao
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

    for config, model_name in itertools.product(configs, models):
        print(f"  - {config} / {model_name}")
        model, pred_df, metrics, ra_metrics, features = executar_ajuste_previsao(df, config, model_name)
        key = (config, model_name)
        ra_by_key[key] = ra_metrics
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
        
    winner = {
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

    result.to_csv(ABLATION_CSV, index=False)
    ra_result.to_csv(ABLATION_RA_CSV, index=False)
    pred_result.to_csv(ABLATION_PRED_CSV, index=False)
    WINNER_JSON.write_text(json.dumps(winner, indent=2, ensure_ascii=False), encoding="utf-8")
    
    return result, winner
