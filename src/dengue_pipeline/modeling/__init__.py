# -*- coding: utf-8 -*-
"""
Pacote de Modelagem e Avaliação Preditiva.

Exporta as interfaces públicas para engenharia de features, treinamento,
orquestração experimental, avaliação e estimativa de incerteza conformal.
"""

from dengue_pipeline.modeling.feature_engineering import (
    construir_dataset_consolidado,
    obter_configuracao_features,
    preparar_matriz_design,
    construir_pipeline_features,
    construir_pipeline_modelo,
    obter_colunas_entrada_pipeline,
)
from dengue_pipeline.modeling.train_tuning import (
    dividir_treino_teste_temporal,
    fabrica_modelos,
    prever_casos_recursivo,
    executar_ajuste_previsao,
    cv_score_parametros,
    otimizar_hiperparametros,
)
from dengue_pipeline.modeling.evaluation import (
    calcular_r2_robusto,
    calcular_erro_quadratico_medio,
    avaliar_cobertura_intervalo,
    calcular_cobertura_intervalo,
    calcular_wis,
    calcular_calibration_error,
    consolidar_metricas_performance,
)
from dengue_pipeline.modeling.orchestration import (
    executar_estudo_ablacao,
    executar_validacao_temporal,
)
from dengue_pipeline.modeling.conformal_prediction import (
    calibrar_intervalos_confianca,
    aplicar_limites_confianca,
    salvar_calibracao,
    carregar_calibracao,
)
from dengue_pipeline.modeling.types import (
    TuningResult,
    AblationResult,
)

# Aliases para retrocompatibilidade
construir_dataset_processado = construir_dataset_consolidado
especificacao_features = obter_configuracao_features
preparar_design = preparar_matriz_design
separar_treino_teste = dividir_treino_teste_temporal
fabrica_modelo = fabrica_modelos
prever_casos = prever_casos_recursivo
ajustar_prever_config = executar_ajuste_previsao
tunar_modelos = otimizar_hiperparametros
executar_validacao_rolling = executar_validacao_temporal
r2_seguro = calcular_r2_robusto
rmse = calcular_erro_quadratico_medio
cobertura_intervalo = avaliar_cobertura_intervalo
agregar_metricas = consolidar_metricas_performance
executar_testes_ablacao = executar_estudo_ablacao
calibrar_conformal = calibrar_intervalos_confianca
aplicar_intervalos = aplicar_limites_confianca
