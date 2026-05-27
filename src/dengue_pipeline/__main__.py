# -*- coding: utf-8 -*-
"""
Orquestrador Principal do Pipeline de Dengue no Distrito Federal.

Permite a execução completa do pipeline de dados, validação, modelagem e geração
de relatórios de forma automatizada através do comando:
    python -m dengue_pipeline
"""

import sys
import json
import warnings
from pathlib import Path
import pandas as pd

from dengue_pipeline.reporting import (
    executar_analise_target,
    gerar_graficos_eda,
    gerar_graficos_ablacao,
    gerar_visualizacoes_finais,
    validar_sinan_infosaude
)
from dengue_pipeline.modeling import (
    construir_dataset_processado,
    executar_validacao_rolling,
    executar_testes_ablacao,
    tunar_modelos
)
from dengue_pipeline.utils import (
    escrever_notebooks,
    atualizar_index_notebook
)

def main() -> None:
    """Função de entrada principal que executa todo o pipeline de ponta a ponta."""
    warnings.filterwarnings("ignore", category=UserWarning)
    
    # Garantir diretórios necessários
    base_dir = Path(__file__).resolve().parents[2]
    (base_dir / "resultados_graficos").mkdir(exist_ok=True)
    (base_dir / "resultados_modelagem").mkdir(exist_ok=True)
    (base_dir / "dados_processados").mkdir(exist_ok=True)
    (base_dir / ".notebook").mkdir(exist_ok=True)
    (base_dir / "scripts").mkdir(exist_ok=True)
    
    print("=" * 60)
    print(">>> INICIANDO PIPELINE DE MODELAGEM PREDITIVA DE DENGUE (DF)")
    print("=" * 60)
    
    # 1. Scaffold de Notebooks e Documentação
    print("\n--- PASSO 1: Estruturando notebooks e documentação ---")
    escrever_notebooks()
    
    # 2. Análise de Definição do Target
    print("\n--- PASSO 2: Executando análise e formalização do target ---")
    _, target_decision = executar_analise_target()
    target_name = target_decision["target_name"]
    print(f"Target selecionado: {target_name}")
    
    # 3. Processamento de Features (Engenharia de Variáveis)
    print("\n--- PASSO 3: Construindo e processando o dataset consolidado ---")
    dataset = construir_dataset_processado(target_name)
    print("Gerando gráficos exploratórios (EDA)...")
    gerar_graficos_eda(dataset)
    print(f"Dataset processado salvo em dados_processados/ com formato Parquet. Shape: {dataset.shape}")
    
    # 4. Validação em Janela Móvel (Rolling Validation)
    print("\n--- PASSO 4: Executando rolling validation (nowcasting vs forecast recursivo) ---")
    rolling = executar_validacao_rolling(dataset)
    print("\nResultados consolidados da validação rolling:")
    print(rolling.to_string(index=False))
    
    # 5. Testes de Ablação de Features
    print("\n--- PASSO 5: Executando testes de ablação de features ---")
    ablation, winner = executar_testes_ablacao(dataset)
    gerar_graficos_ablacao(ablation)
    print("\nConfigurações de features avaliadas:")
    print(ablation.to_string(index=False))
    print("\nConfiguração de features vencedora:")
    print(json.dumps(winner, indent=2, ensure_ascii=False))
    
    # 6. Tuning Finais de Hiperparâmetros (Grid Search)
    print("\n--- PASSO 6: Executando busca em grade final (Grid Search) ---")
    tuning, final_predictions = tunar_modelos(dataset, winner["config"])
    print("\nMelhores hiperparâmetros por algoritmo:")
    print(tuning.groupby("modelo").head(1).to_string(index=False))
    
    # 7. Visualizações e Relatório Final de Modelagem
    print("\n--- PASSO 7: Gerando visualizações finais e redigindo relatório ---")
    gerar_visualizacoes_finais(dataset, winner, final_predictions)
    print("Relatório final gerado sob .notebook/relatorio-final-plano-prompts-opus.md")
    
    # 8. Validação SINAN (Nível de Distrito Federal)
    print("\n--- PASSO 8: Validando dados SINAN vs info-saude (DF 2017) ---")
    sinan_result = validar_sinan_infosaude(target_name)
    print("\nResultados da validação SINAN:")
    print(json.dumps(sinan_result, indent=2, ensure_ascii=False))
    
    # 9. Atualização do Índice do Caderno de Anotações
    print("\n--- PASSO 9: Atualizando o índice do caderno de anotações (.notebook) ---")
    atualizar_index_notebook()
    
    print("\n" + "=" * 60)
    print(">>> PIPELINE COMPLETO EXECUTADO COM SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    main()
