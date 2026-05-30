import json
from pathlib import Path

# Detecta a pasta raiz de forma dinâmica
from dengue_pipeline.config import BASE_DIR, NOTEBOOK_DIR
import logging
logger = logging.getLogger(__name__)

def celula_notebook(tipo_celula: str, codigo_fonte: str) -> dict:
    """
    Estrutura um dicionário no formato de célula Jupyter Notebook.
    
    Parâmetros:
        tipo_celula (str): 'code' ou 'markdown'.
        codigo_fonte (str): Texto contendo o conteúdo da célula.
        
    Retorna:
        dict: Dicionário formatado no padrão nbformat.
    """
    return {
        "cell_type": tipo_celula,
        "metadata": {},
        "source": codigo_fonte.splitlines(keepends=True),
        "outputs": [] if tipo_celula == "code" else None,
        "execution_count": None if tipo_celula == "code" else None,
    }

def escrever_notebook(caminho: Path, titulo: str, celulas: list[tuple[str, str]]) -> None:
    """
    Gera fisicamente um arquivo .ipynb a partir de uma lista de tuplas (tipo, fonte).
    
    Parâmetros:
        caminho (Path): Caminho completo onde o notebook será salvo.
        titulo (str): Título do notebook.
        celulas (list): Lista contendo tuplas do tipo ('markdown'|'code', texto).
    """
    nb_cells = []
    for tipo, fonte in celulas:
        cell = celula_notebook(tipo, fonte)
        if tipo == "markdown":
            cell.pop("outputs", None)
            cell.pop("execution_count", None)
        nb_cells.append(cell)
        
    notebook = {
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
            "title": titulo,
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    caminho.write_text(json.dumps(notebook, indent=2, ensure_ascii=False), encoding="utf-8")

def escrever_notebooks() -> None:
    """
    Cria os dois notebooks do projeto (modelagem e validação) de forma dinâmica,
    substituindo caminhos hardcoded por caminhos baseados em detecção relativa do repositório.
    """
    logger.info(">>> Gerando notebooks...")
    
    codigo_setup_notebook = (
        "from pathlib import Path\n"
        "import sys\n"
        "# Detecta dinamicamente a pasta raiz do projeto\n"
        "BASE = Path('.').resolve()\n"
        "sys.path.append(str(BASE))\n"
        "sys.path.append(str(BASE / 'scripts'))\n"
        "import executar_pipeline_completo as p"
    )
    
    main_cells = [
        ("markdown", "# Dengue DF - Análise e Modelagem\nNotebook gerado automaticamente pelo plano `plano_execucao_pipeline.md`."),
        ("code", codigo_setup_notebook),
        ("markdown", "## Seção 1 - Formalização do target"),
        ("code", "target_annual, target_decision = p.run_prompt1_target_analysis()\ntarget_annual"),
        ("markdown", "## Seções 2 a 5 - Limpeza, população, clima, sazonalidade e EDA"),
        ("code", "dataset = p.build_processed_dataset(target_decision['target_name'])\ndataset.head()"),
        ("markdown", "## Seção 6 - Rolling validation sem leakage"),
        ("code", "rolling = p.run_rolling_validation(dataset)\nrolling"),
        ("markdown", "## Seção 7 - Testes de ablação"),
        ("code", "ablation, winner = p.run_ablation_tests(dataset)\nablation"),
        ("markdown", "## Seção 8 - Tuning"),
        ("code", "tuning, final_predictions = p.tune_models(dataset, winner['config'])\ntuning.head()"),
        ("markdown", "## Seção 9 - Visualizações e relatório final"),
        ("code", "p.make_final_visuals(dataset, winner, final_predictions)\nprint(Path(p.FINAL_REPORT_MD).read_text(encoding='utf-8')[:3000])"),
    ]
    escrever_notebook(BASE_DIR / "legacy" / "analise_preditiva_dengue.ipynb", "Dengue DF - Análise e Modelagem", main_cells)

    sinan_cells = [
        ("markdown", "# Validação SINAN vs info-saude\nPré-requisito para hierarquia nacional futura."),
        ("code", codigo_setup_notebook),
        ("markdown", "## Validação 2017"),
        ("code", "resultado = p.validate_sinan_infosaude('familia_dengue')\nresultado"),
        ("markdown", "## Relatório"),
        ("code", "print(Path(p.SINAN_REPORT_MD).read_text(encoding='utf-8'))"),
    ]
    escrever_notebook(BASE_DIR / "legacy" / "validacao_consistencia_fontes.ipynb", "Validação SINAN vs info-saude", sinan_cells)

def atualizar_index_notebook() -> None:
    """
    Atualiza o arquivo de índice (.notebook/INDEX.md) registrando os novos artefatos
    gerados caso as entradas ainda não existam.
    """
    entry1 = "| [target-formalizacao.md](target-formalizacao.md) | `target`, `p0`, `filtros` | Decisão documentada do target epidemiológico usado na modelagem |\n"
    entry2 = "| [relatorio_final_execucao.md](relatorio_final_execucao.md) | `relatorio`, `ablation`, `modelagem` | Resultado final da execução P0/P1 do plano revisado |\n"
    entry3 = "| [validacao_consistencia_fontes.md](validacao_consistencia_fontes.md) | `sinan`, `validacao`, `p2` | Validação de compatibilidade entre SINAN 2017 e info-saude |\n"
    
    index_path = NOTEBOOK_DIR / "INDEX.md"
    if not index_path.exists():
        return
        
    text = index_path.read_text(encoding="utf-8")
    insert = ""
    for entry in [entry1, entry2, entry3]:
        if entry.split("|")[1].strip() not in text:
            insert += entry
            
    if insert:
        marker = "\n\n## Contexto"
        text = text.replace(marker, insert + marker)
        index_path.write_text(text, encoding="utf-8")
