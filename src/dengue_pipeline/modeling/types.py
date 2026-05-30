# -*- coding: utf-8 -*-
"""
Definições de Tipos e Contratos de Interface de Dados.

Contém as estruturas NamedTuple tipadas que formalizam os contratos de retorno
das principais funções de treinamento, validação e experimentos do pipeline.
"""

from typing import NamedTuple, Any
import pandas as pd


class TuningResult(NamedTuple):
    """
    Contrato de interface para o resultado de modelagem preditiva e ajuste.
    
    Atributos:
        model: Objeto do estimador ajustado compatível com a API scikit-learn (RandomForest ou XGBoost).
        predictions: DataFrame Pandas contendo predições detalhadas de incidência e casos absolutos.
        metrics: Dicionário contendo métricas de performance agregadas a nível de DF (RMSE, MAE, R2, sMAPE, Cobertura).
        ra_metrics: DataFrame contendo as métricas de performance discriminadas individualmente por RA.
        features: Lista de strings com os nomes das features (matriz de design) utilizadas para treinar o modelo.
    """
    model: Any
    predictions: pd.DataFrame
    metrics: dict[str, float]
    ra_metrics: pd.DataFrame
    features: list[str]


class AblationResult(NamedTuple):
    """
    Contrato de interface para os resultados de testes de ablação sistemática.
    
    Atributos:
        ablation_summary: DataFrame de sumário comparando o desempenho de cada configuração.
        winner_specification: Dicionário com a configuração de features e algoritmo vencedor.
        all_metrics: Dicionário detalhado mapeando cada combinação às suas métricas brutas.
    """
    ablation_summary: pd.DataFrame
    winner_specification: dict[str, Any]
    all_metrics: dict[str, dict[str, float]]


class MultiHorizonForecastResult(NamedTuple):
    """
    Contrato de interface para o resultado de um forecast direto por horizonte.

    Cada horizonte k (1 = próxima semana, 2 = duas semanas, etc.) é treinado
    com um sklearn.Pipeline independente usando como target ``y_{t+k}``,
    eliminando o exposure bias da previsão recursiva.

    Definido em conformidade com RFC-04 (contratos de interface via NamedTuple).

    Atributos:
        horizon: Horizonte k (1 = próxima semana, 2 = duas semanas, etc.).
        pipeline: sklearn.Pipeline completo (preprocessor + regressor).
        predictions: DataFrame com colunas epi_sunday, RA, cases, prediction
            (e opcionalmente lower_ci, upper_ci).
        metrics: Dicionário de métricas de avaliação deste horizonte
            (RMSE, MAE, coverage, WIS, etc.).
    """
    horizon: int
    pipeline: Any
    predictions: pd.DataFrame
    metrics: dict[str, float]
