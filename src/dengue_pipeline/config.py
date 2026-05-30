# -*- coding: utf-8 -*-
"""
Módulo de Configuração Centralizada de Caminhos.

Única fonte de verdade para a resolução física de diretórios e caminhos
de dados do pipeline. Suporta injeção de base_dir via variável de ambiente
PIPELINE_ROOT e aplica validação fail-fast.
"""

import os
import sys
from pathlib import Path


def _resolve_base_dir() -> Path:
    """
    Deduz a raiz física do pipeline epidemiológico de forma fail-fast.
    
    Verifica primeiro a presença da variável de ambiente 'PIPELINE_ROOT'.
    Caso ausente, utiliza a localização física do arquivo 'config.py' 
    (esperado na pasta 'src/dengue_pipeline/') para computar 'parents[2]'.
    """
    env_root = os.getenv("PIPELINE_ROOT")
    if env_root:
        base = Path(env_root).resolve()
        if not base.exists():
            print(f"[ERRO ARQUITETURAL] PIPELINE_ROOT informada em variável de ambiente não existe: '{env_root}'", file=sys.stderr)
            raise RuntimeError(f"PIPELINE_ROOT informada não existe: '{env_root}'")
        return base
        
    # config.py reside em src/dengue_pipeline/config.py (2 níveis abaixo da raiz)
    return Path(__file__).resolve().parents[2]


# --- 1. Raiz do Projeto ---
BASE_DIR = _resolve_base_dir()

# --- 2. Diretórios Físicos Derivados ---
DADOS_PROCESSADOS_DIR = BASE_DIR / "dados_processados"
MODELOS_DIR           = BASE_DIR / "resultados_modelagem"
GRAFICOS_DIR          = BASE_DIR / "resultados_graficos"
NOTEBOOK_DIR          = BASE_DIR / ".notebook"
SCRIPTS_DIR           = BASE_DIR / "scripts"

# --- 3. Arquivos de Metadados e Modelos Críticos ---
CAMINHO_DATASET_PARQUET     = DADOS_PROCESSADOS_DIR / "dataset_processado.parquet"
CONFORMAL_CALIBRATION_JSON  = MODELOS_DIR / "conformal_calibration.json"
ROLLING_RESULTS_CSV         = MODELOS_DIR / "rolling_validation_resultados.csv"
ABLATION_CSV                = MODELOS_DIR / "resultados_ablacao_nowcasting.csv"
ABLATION_RA_CSV             = MODELOS_DIR / "resultados_ablation_por_ra.csv"
ABLATION_PRED_CSV           = MODELOS_DIR / "predicoes_ablation.csv"
WINNER_JSON                 = MODELOS_DIR / "campeao_ablacao_nowcasting.json"

import logging

def seed_everything(seed: int = 42) -> None:
    """Fixa as fontes de aleatoriedade no ecossistema Python."""
    import random
    import numpy as np
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    
    # Suprime threads de bibliotecas matemáticas para garantir determinismo total
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

def setup_logging(run_id: str) -> None:
    """Configura o logger padronizado do pipeline."""
    log_format = f"%(asctime)s | %(name)s | %(levelname)s | run_id={run_id} | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )
