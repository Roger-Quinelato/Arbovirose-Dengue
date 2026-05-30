"""
Conformal Prediction Indutivo Dinâmico para Intervalos de Confiança Epidemiológicos
(Versão Reformada — TDD-01)

Este módulo implementa bandas de incerteza calibradas por horizonte de previsão
e adaptativas, corrigindo os problemas identificados na versão anterior:

  - P-01 (CORRIGIDO): Eliminação completa do fator √k que assumia passeio aleatório.
    Substituído por calibração específica por horizonte (horizon-specific quantiles).
  - P-02 (CORRIGIDO): Substituição do epsilon fixo (0.01) por epsilon adaptativo
    calculado como max(epsilon_min, percentil_10(ŷ_cal)), evitando instabilidade
    near-zero sem inflar bandas desnecessariamente.

A calibração computa quantis de não-conformidade independentes para cada horizonte
preditivo k, respeitando a heterogeneidade temporal dos erros em sistemas
epidemiológicos autocorrelacionados.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from dengue_pipeline.config import CONFORMAL_CALIBRATION_JSON

# Número mínimo de amostras por horizonte para calibração robusta.
# Horizontes com n_k < MIN_SAMPLES_PER_HORIZON são consolidados com horizontes adjacentes.
MIN_SAMPLES_PER_HORIZON = 30


def calibrar_intervalos_confianca(
    df_calibracao: pd.DataFrame,
    alpha: float = 0.10,
    epsilon_min: float = 0.10,
) -> dict[str, any]:
    """
    Calibra os scores de não-conformidade de forma horizon-specific e adaptativa.

    Para cada horizonte preditivo k, computa um quantil conformal independente
    a partir dos scores de não-conformidade proporcionais:
        s_{i,k} = |y_i - ŷ_{i,k}| / (ŷ_{i,k} + ε_adaptativo)

    O quantil crítico q_conf_k é obtido via correção empírica finita de Papadopoulos:
        q_level_k = min(1.0, ceil((n_k + 1)(1 - α)) / n_k)
        q_conf_k = Quantil(S_k, q_level_k)

    Parâmetros:
        df_calibracao (pd.DataFrame): DataFrame contendo 'cases', 'prediction' e 'horizonte_k'.
        alpha (float): Nível de significância (default 0.10 → 90% de cobertura).
        epsilon_min (float): Piso estabilizador mínimo para o denominador (default 0.10).

    Retorna:
        dict: Parâmetros de calibração contendo:
            - alpha: nível de significância usado
            - epsilon_adaptativo: epsilon dinâmico computado
            - quantiles_por_horizonte: {str(k): q_conf_k}
            - metadata: {n_total_calibration, data_calibracao}
    """
    required = {"cases", "prediction", "horizonte_k"}
    if not required.issubset(df_calibracao.columns):
        raise ValueError(
            f"DataFrame de calibração deve conter as colunas {required}. "
            f"Encontradas: {set(df_calibracao.columns)}"
        )

    df = df_calibracao.dropna(subset=["cases", "prediction", "horizonte_k"]).copy()
    if df.empty:
        raise ValueError("DataFrame de calibração está vazio após remoção de NaN.")

    # Epsilon Adaptativo: max(epsilon_min, percentil_10(ŷ_cal))
    # Evita divisões instáveis quando ŷ ≈ 0 (períodos interepidêmicos)
    # enquanto se adapta à escala da série epidemiológica
    percentil_10 = float(np.percentile(df["prediction"].values, 10))
    epsilon_adaptativo = max(epsilon_min, percentil_10)

    # Scores de não-conformidade proporcionais (vetorizado)
    df["residuo_abs"] = (df["cases"] - df["prediction"]).abs()
    df["scale"] = df["prediction"] + epsilon_adaptativo
    df["score"] = df["residuo_abs"] / df["scale"]

    # Calibração horizon-specific: quantil independente por horizonte k
    quantiles_por_horizonte = {}
    horizontes = sorted(df["horizonte_k"].unique())

    for k in horizontes:
        mask = df["horizonte_k"] == k
        scores_k = df.loc[mask, "score"].dropna().values
        n_k = len(scores_k)

        if n_k < MIN_SAMPLES_PER_HORIZON:
            # Consolidar com todos os horizontes >= k (mitigação de volatilidade)
            mask_consolidado = df["horizonte_k"] >= k
            scores_k = df.loc[mask_consolidado, "score"].dropna().values
            n_k = len(scores_k)

        if n_k == 0:
            continue

        # Correção empírica finita de Papadopoulos
        q_level = min(1.0, np.ceil((n_k + 1) * (1 - alpha)) / n_k)
        q_conf_k = float(np.quantile(scores_k, q_level))
        quantiles_por_horizonte[str(int(k))] = q_conf_k

    if not quantiles_por_horizonte:
        raise ValueError("Não foi possível computar quantis para nenhum horizonte.")

    return {
        "alpha": alpha,
        "epsilon_adaptativo": epsilon_adaptativo,
        "quantiles_por_horizonte": quantiles_por_horizonte,
        "metadata": {
            "n_total_calibration": len(df),
            "data_calibracao": datetime.now().isoformat(timespec="seconds"),
        },
    }


def aplicar_limites_confianca(
    df_forecast: pd.DataFrame,
    calibracao: dict[str, any],
) -> pd.DataFrame:
    """
    Aplica bandas conformalizadas vetorizadas utilizando lookup por horizonte preditivo.

    A margem de erro para cada amostra i com horizonte k é:
        margin_i = q_conf_k * (ŷ_i + ε_adaptativo)

    Onde q_conf_k é o quantil calibrado específico para o horizonte k,
    eliminando a heurística de expansão √k usada anteriormente.

    Parâmetros:
        df_forecast (pd.DataFrame): DataFrame contendo 'prediction' e 'horizonte_k'.
        calibracao (dict): Metadados gerados por calibrar_intervalos_confianca.

    Retorna:
        pd.DataFrame: DataFrame original acrescido de 'lower_ci' e 'upper_ci', com piso em 0.0.
    """
    required = {"prediction", "horizonte_k"}
    if not required.issubset(df_forecast.columns):
        raise ValueError(
            f"DataFrame de forecast deve conter as colunas {required}. "
            f"Encontradas: {set(df_forecast.columns)}"
        )

    df = df_forecast.copy()
    epsilon = calibracao["epsilon_adaptativo"]
    quantiles = calibracao["quantiles_por_horizonte"]

    # Construir lookup vetorizado: horizonte_k → q_conf_k
    # Para horizontes sem calibração, usar o maior horizonte calibrado (fallback conservador)
    max_calibrated_k = max(int(k) for k in quantiles.keys())
    fallback_q = quantiles[str(max_calibrated_k)]

    # Mapear cada horizonte ao seu quantil (vetorizado via Series.map)
    df["_q_conf"] = df["horizonte_k"].astype(int).astype(str).map(quantiles).fillna(fallback_q)

    # Operação matemática puramente vetorizada
    scale = df["prediction"] + epsilon
    margin = df["_q_conf"] * scale

    df["lower_ci"] = (df["prediction"] - margin).clip(lower=0.0)
    df["upper_ci"] = df["prediction"] + margin

    df = df.drop(columns=["_q_conf"])
    return df


def salvar_calibracao(calibracao: dict, run_dir: Path | None = None) -> None:
    """Persiste os parâmetros de calibração conformal em JSON para uso operacional."""
    if run_dir is not None:
        out_path = run_dir / "conformal_calibration.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(calibracao, f, indent=2, ensure_ascii=False)
    # Também salva no caminho legado fixo
    CONFORMAL_CALIBRATION_JSON.parent.mkdir(exist_ok=True)
    with open(CONFORMAL_CALIBRATION_JSON, "w", encoding="utf-8") as f:
        json.dump(calibracao, f, indent=2, ensure_ascii=False)


def carregar_calibracao(run_dir: Path | None = None) -> dict | None:
    """Carrega os parâmetros de calibração conformal salvos previamente. Retorna None se ausentes."""
    path = run_dir / "conformal_calibration.json" if run_dir else CONFORMAL_CALIBRATION_JSON
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data
