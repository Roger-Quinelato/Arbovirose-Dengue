"""
Conformal Prediction Indutivo Dinâmico para Intervalos de Confiança Epidemiológicos

Este módulo implementa bandas de incerteza calibradas localmente e adaptativas,
resolvendo dois problemas críticos identificados na modelagem de dengue no DF:
  - P-02: Heteroscedasticidade comprovada — o erro cresce proporcionalmente ao surto.
  - Rigor de Engenharia: Eliminação de loops e operações linha a linha (.apply),
    substituídos por operações vetorizadas de alta performance em Pandas/NumPy.

A abordagem dinâmica usa a própria predição do modelo base (ŷ) somada a um fator de
estabilidade (ε) como estimador heurístico de incerteza. Isso gera intervalos que
automaticamente se expandem nos picos epidêmicos e se estreitam nos períodos interepidérmicos.
"""

import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
CONFORMAL_CALIBRATION_JSON = BASE_DIR / "resultados_modelagem" / "conformal_calibration.json"


def calibrar_conformal(
    df_calibracao: pd.DataFrame,
    alpha: float = 0.10,
    epsilon: float = 0.01,
) -> dict:
    """
    Calibra os scores de não-conformidade usando escala dinâmica adaptativa.

    O score de não-conformidade para a amostra i é:
        s_i = |y_i - ŷ_i| / (ŷ_i + ε)

    Onde (ŷ_i + ε) age como estimador de incerteza heurístico local, penalizando
    erros proporcionalmente à magnitude do surto predito.

    Parâmetros:
        df_calibracao (pd.DataFrame): DataFrame com colunas 'cases' e 'prediction'.
        alpha (float): Nível de significância (default 0.10 -> 90% de cobertura).
        epsilon (float): Fator de estabilização para evitar divisão por zero (default 0.01).

    Retorna:
        dict: Parâmetros de calibração contendo o quantil crítico global e metadados.
    """
    df = df_calibracao.copy()
    df["residuo_abs"] = (df["cases"] - df["prediction"]).abs()

    # Escala dinâmica localmente adaptativa vetorizada
    df["scale"] = df["prediction"] + epsilon
    df["score"] = df["residuo_abs"] / df["scale"]

    # Quantil empírico com correção finita de Papadopoulos
    scores = df["score"].dropna().values
    n = len(scores)
    q_level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    q_conf = float(np.quantile(scores, q_level))

    return {
        "q_conf": q_conf,
        "alpha": alpha,
        "n_cal": n,
        "epsilon": epsilon,
    }


def aplicar_intervalos(
    df_forecast: pd.DataFrame,
    calibracao: dict,
    horizonte_k: int = 1,
) -> pd.DataFrame:
    """
    Aplica bandas de incerteza conformalizadas dinâmicas de forma 100% vetorizada.

    A margem de erro dinâmica é calculada de forma vetorizada como:
        margin = q_conf * (ŷ + ε) * sqrt(k)

    Onde sqrt(k) expande a incerteza para forecasts recursivos mais distantes no tempo.

    Parâmetros:
        df_forecast (pd.DataFrame): DataFrame com coluna 'prediction'.
        calibracao (dict): Dicionário gerado por calibrar_conformal().
        horizonte_k (int): Horizonte de previsão (1 = nowcasting, >1 = forecast fechado).

    Retorna:
        pd.DataFrame: DataFrame com as colunas 'lower_ci' e 'upper_ci' adicionadas.
    """
    df = df_forecast.copy()
    q_conf = calibracao["q_conf"]
    epsilon = calibracao.get("epsilon", 0.01)

    # Fator de expansão recursiva temporal (suporta escalar ou série/array)
    if isinstance(horizonte_k, (pd.Series, np.ndarray)):
        expansion_factor = np.sqrt(np.maximum(1, horizonte_k))
    else:
        expansion_factor = np.sqrt(max(1, horizonte_k))

    # Operação matemática puramente vetorizada (sem .apply ou loops por linha)
    scale = df["prediction"] + epsilon
    margin = q_conf * scale * expansion_factor

    df["lower_ci"] = (df["prediction"] - margin).clip(lower=0.0)
    df["upper_ci"] = df["prediction"] + margin

    return df


def salvar_calibracao(calibracao: dict) -> None:
    """Persiste os parâmetros de calibração conformal em JSON para uso operacional."""
    import json
    CONFORMAL_CALIBRATION_JSON.parent.mkdir(exist_ok=True)
    with open(CONFORMAL_CALIBRATION_JSON, "w", encoding="utf-8") as f:
        json.dump(calibracao, f, indent=2, ensure_ascii=False)


def carregar_calibracao() -> dict | None:
    """Carrega os parâmetros de calibração conformal salvos previamente. Retorna None se ausentes."""
    import json
    if not CONFORMAL_CALIBRATION_JSON.exists():
        return None
    with open(CONFORMAL_CALIBRATION_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data
