# -*- coding: utf-8 -*-
"""
Módulo de Avaliação Pura e Métricas de Performance.

Responsável estritamente pelo cálculo estatístico de métricas de performance
(R², MAE, RMSE, sMAPE, cobertura) a partir de estruturas de dados prontas
(arrays NumPy e DataFrames Pandas). Não realiza treinamento de modelos ou
gravação física de arquivos de orquestração.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


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


def avaliar_cobertura_intervalo(df_avaliado: pd.DataFrame) -> float:
    """
    Calcula a cobertura empírica real (coverage_score).
    
    Verifica a proporção de amostras cujo valor real de 'cases' caiu dentro
    dos limites [lower_ci, upper_ci] das bandas conformalizadas.
    
    Parâmetros:
        df_avaliado (pd.DataFrame): DataFrame contendo 'cases', 'lower_ci' e 'upper_ci'.
        
    Retorna:
        float: Proporção de amostras cobertas (entre 0.0 e 1.0). Retorna NaN se
               não houver amostras válidas.
    """
    required = {"cases", "lower_ci", "upper_ci"}
    if not required.issubset(df_avaliado.columns):
        raise ValueError(f"DataFrame deve conter as colunas {required}. Encontradas: {set(df_avaliado.columns)}")
    
    df = df_avaliado.dropna(subset=["cases", "lower_ci", "upper_ci"])
    if df.empty:
        return float("nan")
    
    dentro = (df["cases"] >= df["lower_ci"]) & (df["cases"] <= df["upper_ci"])
    return float(dentro.mean())


def consolidar_metricas_performance(pred_df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """
    Consolida métricas globais para o DF e individuais por Região Administrativa (RA).
    Calcula R², MAE e RMSE para ambas as escalas.
    Quando colunas de intervalo de confiança ('lower_ci', 'upper_ci') estão presentes,
    calcula automaticamente a cobertura empírica via coverage_score.
    
    Parâmetros:
        pred_df (pd.DataFrame): DataFrame contendo as colunas 'epi_sunday', 'RA', 'cases' e 'prediction'.
                                Opcionalmente 'lower_ci' e 'upper_ci' para cálculo de cobertura.
        
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
    
    # Cobertura empírica — calculada automaticamente quando colunas de CI estão presentes
    ci_cols_present = {"lower_ci", "upper_ci"}.issubset(pred_df.columns)
    if ci_cols_present:
        coverage = avaliar_cobertura_intervalo(pred_df)
        metrics["coverage_score"] = coverage
    
    rows = []
    for ra, group in pred_df.groupby("RA"):
        ra_row = {
            "RA": ra,
            "r2_ra": calcular_r2_robusto(group["cases"], group["prediction"]),
            "mae_ra": float(mean_absolute_error(group["cases"], group["prediction"])),
            "rmse_ra": calcular_erro_quadratico_medio(group["cases"], group["prediction"]),
        }
        # Cobertura por RA quando disponível
        if ci_cols_present:
            ra_row["coverage_ra"] = avaliar_cobertura_intervalo(group)
        rows.append(ra_row)
    ra_df = pd.DataFrame(rows)
    metrics["r2_media_ras"] = float(ra_df["r2_ra"].mean(skipna=True))
    metrics["mae_media_ras"] = float(ra_df["mae_ra"].mean(skipna=True))
    metrics["rmse_media_ras"] = float(ra_df["rmse_ra"].mean(skipna=True))
    return metrics, ra_df
