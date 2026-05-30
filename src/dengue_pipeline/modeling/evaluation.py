# -*- coding: utf-8 -*-
"""
Módulo de Avaliação Pura e Métricas de Performance.

Responsável estritamente pelo cálculo estatístico de métricas de performance
(R², MAE, RMSE, sMAPE, cobertura, WIS, calibration error) a partir de
estruturas de dados prontas (arrays NumPy e DataFrames Pandas).
Não realiza treinamento de modelos ou gravação física de arquivos de orquestração.

Métricas probabilísticas (TDD-08):
    - calcular_cobertura_intervalo: cobertura empírica do intervalo de confiança
    - calcular_wis: Weighted Interval Score (versão 1-intervalo; padrão CDC Forecast Hub)
    - calcular_calibration_error: diferença absoluta entre cobertura real e declarada

Limitação documentada (WIS simplificado):
    A implementação atual calcula o WIS com um único intervalo de confiança (α=0.10).
    O WIS completo do CDC Forecast Hub utiliza 23 quantis. A versão aqui é uma
    aproximação válida para validação interna e comparação relativa entre runs.
    Para submissão ao Forecast Hub, será necessário evoluir para WIS multi-quantil (V2).
"""

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Métricas Probabilísticas — TDD-08
# ---------------------------------------------------------------------------

def calcular_cobertura_intervalo(pred_df: pd.DataFrame, alpha: float = 0.10) -> float:
    """
    Calcula a cobertura empírica do intervalo de confiança.

    Proporção de observações reais (``cases``) que caem dentro do intervalo
    ``[lower_ci, upper_ci]``.  Para um intervalo declarado de (1 - alpha) × 100 %,
    o valor ideal de cobertura é ``1 - alpha``.

    Parâmetros:
        pred_df (pd.DataFrame): DataFrame com colunas ``cases``, ``lower_ci``,
            ``upper_ci``.
        alpha (float): Nível de significância do intervalo (default 0.10 → 90 % CI).

    Retorna:
        float: Proporção em [0, 1].  ``NaN`` quando as colunas de CI estão
            ausentes ou contêm apenas ``NaN``.
    """
    ci_cols = {"lower_ci", "upper_ci", "cases"}
    if not ci_cols.issubset(pred_df.columns):
        logger.warning(
            "Colunas de CI ausentes (%s); cobertura não calculada.",
            ci_cols - set(pred_df.columns),
        )
        return float("nan")

    df = pred_df.dropna(subset=["cases", "lower_ci", "upper_ci"])
    if df.empty:
        logger.warning("Todas as linhas de CI são NaN; cobertura retornando NaN.")
        return float("nan")

    dentro = (df["cases"] >= df["lower_ci"]) & (df["cases"] <= df["upper_ci"])
    return float(dentro.mean())


def calcular_wis(pred_df: pd.DataFrame, alpha: float = 0.10) -> float:
    """
    Calcula o Weighted Interval Score (WIS) simplificado com 1 intervalo.

    Decomposição (para cada observação):
        - ``spread``     = ``upper_ci - lower_ci``    (penalidade de amplitude)
        - ``undershoot`` = ``(2/α) × max(0, lower_ci - cases)``  (saída inferior)
        - ``overshoot``  = ``(2/α) × max(0, cases - upper_ci)``  (saída superior)
        - ``WIS``        = ``mean(spread + undershoot + overshoot)``

    **Limitação documentada:** esta é a versão de 1 intervalo.  O WIS completo
    do CDC Forecast Hub utiliza 23 quantis; a versão aqui é uma aproximação
    válida para validação interna.

    Parâmetros:
        pred_df (pd.DataFrame): DataFrame com colunas ``cases``, ``lower_ci``,
            ``upper_ci``.
        alpha (float): Nível de significância (default 0.10 → 90 % CI).

    Retorna:
        float: Score não-negativo (menor é melhor).  ``NaN`` quando CI ausente.
    """
    ci_cols = {"lower_ci", "upper_ci", "cases"}
    if not ci_cols.issubset(pred_df.columns):
        logger.warning(
            "Colunas de CI ausentes (%s); WIS não calculado.",
            ci_cols - set(pred_df.columns),
        )
        return float("nan")

    df = pred_df.dropna(subset=["cases", "lower_ci", "upper_ci"])
    if df.empty:
        logger.warning("Todas as linhas de CI são NaN; WIS retornando NaN.")
        return float("nan")

    cases = df["cases"].values.astype(float)
    lower = df["lower_ci"].values.astype(float)
    upper = df["upper_ci"].values.astype(float)

    spread = upper - lower
    undershoot = (2.0 / alpha) * np.maximum(0.0, lower - cases)
    overshoot = (2.0 / alpha) * np.maximum(0.0, cases - upper)

    wis = float(np.mean(spread + undershoot + overshoot))
    return wis


def calcular_calibration_error(coverage_real: float, alpha: float = 0.10) -> float:
    """
    Calcula o erro de calibração: diferença absoluta entre cobertura
    declarada ``(1 - alpha)`` e cobertura real observada.

    Parâmetros:
        coverage_real (float): Cobertura empírica calculada via
            ``calcular_cobertura_intervalo``.
        alpha (float): Nível de significância (default 0.10 → meta 90 %).

    Retorna:
        float: Erro em [0, 1]; zero é ideal.  ``NaN`` se ``coverage_real``
            for ``NaN``.
    """
    if np.isnan(coverage_real):
        return float("nan")
    return float(abs(coverage_real - (1.0 - alpha)))


# ---------------------------------------------------------------------------
# Consolidação de Métricas
# ---------------------------------------------------------------------------

def consolidar_metricas_performance(
    pred_df: pd.DataFrame,
    peak_threshold: float = 0.75,
    alpha: float = 0.10,
) -> tuple[dict, pd.DataFrame]:
    """
    Consolida métricas globais para o DF e individuais por Região Administrativa (RA).

    Calcula métricas pontuais (R², MAE, RMSE, MAPE, sMAPE, hit_rate_picos) e,
    quando colunas de intervalo de confiança (``lower_ci``, ``upper_ci``) estão
    presentes, métricas probabilísticas (coverage, WIS, calibration_error).

    Parâmetros:
        pred_df (pd.DataFrame): DataFrame contendo ``epi_sunday``, ``RA``,
            ``cases``, ``prediction``.  Opcionalmente ``lower_ci`` e ``upper_ci``.
        peak_threshold (float): Percentil para detecção de pico.
            Default ``0.75`` preserva comportamento original (P75).
        alpha (float): Nível de significância do CI para métricas probabilísticas.
            Default ``0.10`` → intervalo de 90 %.

    Retorna:
        tuple: ``(dict_metricas_globais, DataFrame_metricas_por_ra)``
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
    # Pico definido como acima do percentil configurável (default P75)
    peak_val = df_total["cases"].quantile(peak_threshold)
    is_peak_real = df_total["cases"] >= peak_val
    is_peak_pred = df_total["prediction"] >= peak_val
    hit_rate = float(
        (is_peak_real & is_peak_pred).sum() / is_peak_real.sum()
    ) if is_peak_real.sum() > 0 else float("nan")

    logger.debug("peak_threshold=%.2f (quantile=%.1f)", peak_threshold, peak_val)
    
    metrics = {
        "r2_df": r2,
        "mae_df": mae,
        "rmse_df": rmse_val,
        "mape_df": mape_val,
        "smape_df": smape_val,
        "hit_rate_picos": hit_rate,
        "peak_threshold": peak_threshold,
    }
    
    # -----------------------------------------------------------------------
    # Métricas probabilísticas — TDD-08
    # Calculadas condicionalmente quando CI está presente no DataFrame.
    # -----------------------------------------------------------------------
    ci_cols_present = {"lower_ci", "upper_ci"}.issubset(pred_df.columns)

    if ci_cols_present:
        coverage = calcular_cobertura_intervalo(pred_df, alpha=alpha)
        wis = calcular_wis(pred_df, alpha=alpha)
        cal_error = calcular_calibration_error(coverage, alpha=alpha)

        metrics["coverage_score"] = coverage
        metrics["wis"] = wis
        metrics["calibration_error"] = cal_error

        logger.info(
            "Métricas probabilísticas: coverage=%.4f, WIS=%.4f, cal_error=%.4f",
            coverage, wis, cal_error,
        )
    else:
        metrics["coverage_score"] = float("nan")
        metrics["wis"] = float("nan")
        metrics["calibration_error"] = float("nan")
        logger.info(
            "Colunas de CI ausentes; métricas probabilísticas preenchidas com NaN."
        )
    
    rows = []
    for ra, group in pred_df.groupby("RA"):
        ra_row = {
            "RA": ra,
            "r2_ra": calcular_r2_robusto(group["cases"], group["prediction"]),
            "mae_ra": float(mean_absolute_error(group["cases"], group["prediction"])),
            "rmse_ra": calcular_erro_quadratico_medio(group["cases"], group["prediction"]),
        }
        # Cobertura e WIS por RA quando disponível
        if ci_cols_present:
            ra_row["coverage_ra"] = calcular_cobertura_intervalo(group, alpha=alpha)
            ra_row["wis_ra"] = calcular_wis(group, alpha=alpha)
        rows.append(ra_row)

    ra_df = pd.DataFrame(rows)
    metrics["r2_media_ras"] = float(ra_df["r2_ra"].mean(skipna=True))
    metrics["mae_media_ras"] = float(ra_df["mae_ra"].mean(skipna=True))
    metrics["rmse_media_ras"] = float(ra_df["rmse_ra"].mean(skipna=True))
    return metrics, ra_df
