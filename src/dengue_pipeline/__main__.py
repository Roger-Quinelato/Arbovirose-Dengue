# -*- coding: utf-8 -*-
"""
Orquestrador Principal do Pipeline de Dengue no Distrito Federal.

Permite a execução completa do pipeline de dados, validação, modelagem e geração
de relatórios de forma automatizada através do comando:
    python -m dengue_pipeline
"""

import sys
import os
import json
import warnings
import shutil
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

from dengue_pipeline.config import seed_everything
GLOBAL_SEED = int(os.getenv("PIPELINE_SEED", "42"))
seed_everything(GLOBAL_SEED)

from dengue_pipeline.reporting import (
    analisar_alvo_epidemiologico,
    gerar_visualizacoes_eda,
    gerar_graficos_ablacao,
    gerar_painel_final,
    validar_consistencia_fontes
)
from dengue_pipeline.modeling import (
    construir_dataset_consolidado,
    executar_validacao_temporal,
    executar_estudo_ablacao,
    otimizar_hiperparametros
)
from dengue_pipeline.utils import (
    escrever_notebooks,
    atualizar_index_notebook
)
from dengue_pipeline.config import BASE_DIR

def main() -> None:
    """Função de entrada principal que executa todo o pipeline de ponta a ponta."""
    warnings.filterwarnings("ignore", category=UserWarning)
    
    # 0. Inicializar run_id e run_dir
    from dengue_pipeline.config import BASE_DIR, setup_logging
    base_dir = BASE_DIR
    run_id = datetime.now().strftime("%Y%m%d_%H%M")
    setup_logging(run_id)
    
    logger = logging.getLogger(__name__)
    run_dir = base_dir / "resultados_modelagem" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Garantir diretórios necessários
    (base_dir / "resultados_graficos").mkdir(exist_ok=True)
    (base_dir / "resultados_modelagem").mkdir(exist_ok=True)
    (base_dir / "dados_processados").mkdir(exist_ok=True)
    (base_dir / ".notebook").mkdir(exist_ok=True)
    (base_dir / "scripts").mkdir(exist_ok=True)
    
    logger.info("=" * 60)
    logger.info(">>> INICIANDO PIPELINE DE MODELAGEM PREDITIVA DE DENGUE (DF)")
    logger.info(f"Execução ID: {run_id}")
    logger.info(f"Diretório da Execução: {run_dir}")
    logger.info("=" * 60)
    
    # 1. Scaffold de Notebooks e Documentação
    logger.info("\n--- PASSO 1: Estruturando notebooks e documentação ---")
    escrever_notebooks()
    
    # 2. Análise de Definição do Target
    logger.info("\n--- PASSO 2: Executando análise e formalização do target ---")
    _, target_decision = analisar_alvo_epidemiologico(run_dir=run_dir)
    target_name = target_decision["target_name"]
    logger.info(f"Target selecionado: {target_name}")
    
    # 3. Processamento de Features (Engenharia de Variáveis)
    logger.info("\n--- PASSO 3: Construindo e processando o dataset consolidado ---")
    dataset = construir_dataset_consolidado(target_name)
    logger.info("Gerando gráficos exploratórios (EDA)...")
    gerar_visualizacoes_eda(dataset, run_dir=run_dir)
    logger.info(f"Dataset processado salvo em dados_processados/ com formato Parquet. Shape: {dataset.shape}")
    
    # 4. Validação em Janela Móvel (Rolling Validation)
    logger.info("\n--- PASSO 4: Executando rolling validation (nowcasting vs forecast recursivo) ---")
    rolling = executar_validacao_temporal(dataset, run_dir=run_dir)
    logger.info("\nResultados consolidados da validação rolling:")
    logger.info(rolling.to_string(index=False))
    
    # 5. Testes de Ablação de Features
    logger.info("\n--- PASSO 5: Executando testes de ablação de features ---")
    ablation, winner, _ = executar_estudo_ablacao(dataset, run_dir=run_dir)
    gerar_graficos_ablacao(ablation, run_dir=run_dir)
    logger.info("\nConfigurações de features avaliadas:")
    logger.info(ablation.to_string(index=False))
    logger.info("\nConfiguração de features vencedora:")
    logger.info(json.dumps(winner, indent=2, ensure_ascii=False))
    
    # 6. Tuning Finais de Hiperparâmetros (Grid Search)
    logger.info("\n--- PASSO 6: Executando busca em grade final (Grid Search) ---")
    tuning, final_predictions = otimizar_hiperparametros(dataset, winner["config"], run_dir=run_dir)
    logger.info("\nMelhores hiperparâmetros por algoritmo:")
    logger.info(tuning.groupby("modelo").head(1).to_string(index=False))
    
    # 7. Visualizações e Relatório Final de Modelagem
    logger.info("\n--- PASSO 7: Gerando visualizações finais e redigindo relatório ---")
    gerar_painel_final(dataset, winner, final_predictions, run_dir=run_dir)
    logger.info("Relatório final gerado sob .notebook/relatorio_final_execucao.md")
    
    # 8. Validação SINAN (Nível de Distrito Federal)
    logger.info("\n--- PASSO 8: Validando dados SINAN vs info-saude (DF 2017) ---")
    sinan_result = validar_consistencia_fontes(target_name, run_dir=run_dir)
    logger.info("\nResultados da validação SINAN:")
    logger.info(json.dumps(sinan_result, indent=2, ensure_ascii=False))
    
    # 9. Atualização do Índice do Caderno de Anotações
    logger.info("\n--- PASSO 9: Atualizando o índice do caderno de anotações (.notebook) ---")
    atualizar_index_notebook()
    
    # 10. Atualização da pasta "latest"
    logger.info("\n--- PASSO 10: Sincronizando com a pasta de resultados mais recentes ('latest') ---")
    latest_dir = base_dir / "resultados_modelagem" / "latest"
    if latest_dir.exists():
        try:
            if latest_dir.is_dir() and not latest_dir.is_symlink():
                shutil.rmtree(latest_dir)
            else:
                latest_dir.unlink()
            logger.info("Pasta 'latest' antiga removida com sucesso.")
        except Exception as e:
            logger.warning(f"[AVISO] Não foi possível remover a pasta 'latest' antiga: {e}")
            
    try:
        shutil.copytree(run_dir, latest_dir)
        logger.info(f"Nova pasta 'latest' criada com sucesso como cópia de: {run_dir}")
    except Exception as e:
        logger.error(f"[ERRO] Falha ao copiar a execução atual para 'latest': {e}")
        
    logger.info("\n" + "=" * 60)
    logger.info(">>> PIPELINE COMPLETO EXECUTADO COM SUCESSO!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
