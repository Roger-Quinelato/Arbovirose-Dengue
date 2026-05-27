from __future__ import annotations

import sys
import json
import warnings
from pathlib import Path
import pandas as pd

# Adiciona o diretório src/ ao sys.path para importação limpa do pacote dengue_pipeline
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR / "src"))

# Importação dos módulos em Português
from dengue_pipeline.reporting import (
    analisar_alvo_epidemiologico,
    gerar_visualizacoes_eda,
    gerar_graficos_ablacao,
    gerar_painel_final,
    validar_consistencia_fontes as validar_sinan_distrital
)
from dengue_pipeline.modeling import (
    construir_dataset_consolidado,
    executar_validacao_temporal,
    executar_estudo_ablacao,
    otimizar_hiperparametros as tunar_modelos_pipeline
)
from dengue_pipeline.utils import (
    escrever_notebooks as scaffold_escrever_notebooks,
    atualizar_index_notebook as scaffold_atualizar_index
)

# Definição das constantes expostas originalmente para retrocompatibilidade
NOTEBOOK_DIR = BASE_DIR / ".notebook"
FINAL_REPORT_MD = NOTEBOOK_DIR / "relatorio_final_execucao.md"
SINAN_REPORT_MD = NOTEBOOK_DIR / "validacao_consistencia_fontes.md"

def ensure_dirs() -> None:
    """Garante a existência dos diretórios necessários."""
    Path(BASE_DIR / "resultados_graficos").mkdir(exist_ok=True)
    NOTEBOOK_DIR.mkdir(exist_ok=True)
    Path(BASE_DIR / "scripts").mkdir(exist_ok=True)

def run_prompt1_target_analysis() -> tuple[pd.DataFrame, dict]:
    """Fachada inglesa para analisar_alvo_epidemiologico."""
    return analisar_alvo_epidemiologico()

def build_processed_dataset(target_name: str = "familia_dengue") -> pd.DataFrame:
    """Fachada inglesa para construir_dataset_consolidado, incluindo geração de gráficos EDA."""
    dataset = construir_dataset_consolidado(target_name)
    gerar_visualizacoes_eda(dataset)
    return dataset

def run_rolling_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Fachada inglesa para executar_validacao_temporal."""
    return executar_validacao_temporal(df)

def run_ablation_tests(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fachada inglesa para executar_estudo_ablacao, incluindo geração de gráficos de ablação."""
    result, winner = executar_estudo_ablacao(df)
    gerar_graficos_ablacao(result)
    return result, winner

def tune_models(df: pd.DataFrame, config: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fachada inglesa para otimizar_hiperparametros."""
    return tunar_modelos_pipeline(df, config)

def make_final_visuals(df: pd.DataFrame, winner: dict, final_predictions: pd.DataFrame) -> None:
    """Fachada inglesa para gerar_painel_final."""
    gerar_painel_final(df, winner, final_predictions)

def validate_sinan_infosaude(target_name: str = "familia_dengue") -> dict:
    """Fachada inglesa para validar_consistencia_fontes."""
    return validar_sinan_distrital(target_name)

def write_notebooks() -> None:
    """Fachada inglesa para escrever_notebooks."""
    scaffold_escrever_notebooks()

def update_notebook_index() -> None:
    """Fachada inglesa para atualizar_index_notebook."""
    scaffold_atualizar_index()

def main() -> None:
    """Função de entrada principal que executa todo o pipeline de ponta a ponta."""
    warnings.filterwarnings("ignore", category=UserWarning)
    ensure_dirs()
    write_notebooks()
    
    _, target_decision = run_prompt1_target_analysis()
    dataset = build_processed_dataset(target_decision["target_name"])
    
    rolling = run_rolling_validation(dataset)
    print(rolling.to_string(index=False))
    
    ablation, winner = run_ablation_tests(dataset)
    print(ablation.to_string(index=False))
    print(json.dumps(winner, indent=2, ensure_ascii=False))
    
    tuning, final_predictions = tune_models(dataset, winner["config"])
    print(tuning.groupby("modelo").head(1).to_string(index=False))
    
    make_final_visuals(dataset, winner, final_predictions)
    
    sinan_result = validate_sinan_infosaude(target_decision["target_name"])
    print(json.dumps(sinan_result, indent=2, ensure_ascii=False))
    
    update_notebook_index()
    print(">>> Plano executado com sucesso.")

if __name__ == "__main__":
    main()
