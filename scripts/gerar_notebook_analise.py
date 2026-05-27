import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE_DIR / "legacy" / "analise_preditiva_dengue.ipynb"

cells = []

def add_markdown(source_text):
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source_text.strip().split("\n")]
    })

def add_code(source_text):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source_text.splitlines()]
    })

# ----------------- TITLE -----------------
add_markdown("""
# ANÁLISE E MODELAGEM PREDITIVA DE ARBOVIROSE (DENGUE) - DF
## Target Epidemiológico, Lags Climáticos, Validação sem Leakage, Ablação e Modelagem Preditiva

Este notebook é uma versão **100% executável localmente com outputs e visualizações completas**, com estrutura e rigor estético baseados no padrão de modelagem do notebook `roger-quinelato-ciia-2026 (1).ipynb`.

O pipeline está estruturado passo a passo, cobrindo:
1. **Formalização e Análise do Target**: Comparação de filtros de sementes epidemiológicas.
2. **Engenharia de Features e Lags**: Cruzamento climáticos (temperatura, umidade, chuva) com atrasos temporais.
3. **Análise Exploratória Visual**: Séries temporais, volumetria por Região Administrativa (RA), heatmaps temporais e correlações.
4. **Validação em Janela Móvel (Rolling Validation)**: Avaliação robusta temporal sem leakage de dados futuros.
5. **Estudo de Ablação**: Teste de hipóteses estruturado avaliando o ganho marginal de cada grupo de features.
6. **Tuning de Hiperparâmetros**: Ajuste fino de modelos Random Forest e XGBoost.
7. **Validação Federal (SINAN vs info-saude)**: Validação de compatibilidade histórica (2017) para splicing futuro.
""")

# ----------------- CELL 1: SETUP -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 1: SETUP, IMPORTS E CONFIGURAÇÕES
# ==================================================================================
""")
add_code("""
# CÉLULA 1: SETUP, IMPORTS E CONFIGURAÇÕES
# ============================================================================
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from IPython.display import Image, display

# Detecta dinamicamente a pasta raiz do projeto
BASE = Path('.').resolve()
sys.path.append(str(BASE))
sys.path.append(str(BASE / 'scripts'))
import executar_pipeline_completo as p

# Configurações globais de plotagem
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (14, 6)
plt.rcParams['font.size'] = 11

print("=" * 80)
print("DENGUE DF - AMBIENTE DE ANÁLISE E MODELAGEM INICIALIZADO")
print("=" * 80)
print(f"Raiz do Projeto Detectada: {BASE.absolute()}")
print(f"Data/Hora da Execução: {pd.Timestamp.now()}\\n")
""")

# ----------------- CELL 2: TARGET ANALYSIS -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 2: ANÁLISE E FORMALIZAÇÃO DO TARGET EPIDEMIOLÓGICO
# ==================================================================================
""")
add_code("""
# CÉLULA 2: ANÁLISE E FORMALIZAÇÃO DO TARGET
# ============================================================================
print("=" * 80)
print("PASSO 1: ANÁLISE E FORMALIZAÇÃO DO TARGET EPIDEMIOLÓGICO")
print("=" * 80)

# Executar a análise de target
target_annual, target_decision = p.run_prompt1_target_analysis()

print("\\n[DECISÃO E FORMALIZAÇÃO DO TARGET]")
print("-" * 80)
print(f"• Target Selecionado: {target_decision['target_name']}")
print(f"• Filtro Aplicado: {target_decision['target_filter']}")
print(f"• Recomendação Técnica: {target_decision['recommendation']}")

print("\\n[DISTRIBUIÇÃO DE CASOS POR ANO E FILTRO]")
print("-" * 80)
display(target_annual)

print("\\n[VISUALIZAÇÃO DE COMPATIBILIDADE DOS FILTROS]")
print("-" * 80)
display(Image(filename='resultados_graficos/target_comparativo.png'))
""")

# ----------------- CELL 3: DATA PREPROCESSING -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 3: CARREGAMENTO DO DATASET INTEGRADO (CASOS, CLIMA E POPULAÇÃO)
# ==================================================================================
""")
add_code("""
# CÉLULA 3: CARREGAMENTO DO DATASET INTEGRADO
# ============================================================================
print("=" * 80)
print("PASSO 2: CARREGAMENTO DO DATASET INTEGRADO (CASOS, CLIMA E POPULAÇÃO)")
print("=" * 80)

dataset = p.build_processed_dataset(target_decision['target_name'])

print(f"\\n✓ Dataset integrado criado e carregado: {dataset.shape[0]:,} linhas, {dataset.shape[1]} colunas.")
print("\\nPrimeiros Registros do Dataset Processado:")
print("-" * 80)
display(dataset.head())
""")

# ----------------- CELL 4: DATA QUALITY -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 4: ANÁLISE DE QUALIDADE DOS DADOS (MISSING VALUES E DESCRITIVOS)
# ==================================================================================
""")
add_code("""
# CÉLULA 4: ANÁLISE DE QUALIDADE DOS DADOS
# ============================================================================
print("=" * 80)
print("PASSO 3: ANÁLISE DE QUALIDADE E DESCRITIVOS DAS FEATURES")
print("=" * 80)

# Análise de nulos
null_counts = dataset.isnull().sum()
null_pct = (null_counts / len(dataset)) * 100
quality_df = pd.DataFrame({
    'Valores Nulos': null_counts, 
    'Percentual (%)': null_pct
}).sort_values('Valores Nulos', ascending=False)

print("\\n[DADOS AUSENTES NAS FEATURES]")
print("-" * 80)
colunas_com_nulos = quality_df[quality_df['Valores Nulos'] > 0]
if len(colunas_com_nulos) > 0:
    display(colunas_com_nulos)
else:
    print("✓ Fantástico! Nenhuma coluna possui valores ausentes/nulos.")

print("\\n[ESTATÍSTICAS DESCRITIVAS GERAIS]")
print("-" * 80)
display(dataset.describe())
""")

# ----------------- CELL 5: EDA TEMPORAL -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 5: ANÁLISE EXPLORATÓRIA - SÉRIES TEMPORAIS E VOLUMETRIA
# ==================================================================================
""")
add_code("""
# CÉLULA 5: ANÁLISE EXPLORATÓRIA - SÉRIES TEMPORAIS
# ============================================================================
print("=" * 80)
print("PASSO 4: SÉRIES TEMPORAIS, OUTLIERS E COMPARAÇÕES ENTRE RAs")
print("=" * 80)

print("\\n📊 1. Série Temporal Consolidada do Distrito Federal (Picos Epidemiológicos):")
print("-" * 80)
display(Image(filename='resultados_graficos/serie_df_total_qualidade.png'))

print("\\n📊 2. Comparativo de Casos vs Incidência por 100k (Ceilândia vs Lago Sul):")
print("-" * 80)
display(Image(filename='resultados_graficos/populacao_cases_incidencia.png'))

print("\\n📊 3. Top 10 Regiões Administrativas por Volume Total de Casos:")
print("-" * 80)
display(Image(filename='resultados_graficos/top10_ra_volume.png'))
""")

# ----------------- CELL 6: EDA CORRELATIONS -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 6: CORRELAÇÕES CLIMÁTICAS (SPEARMAN) E CALOR SEMANAL
# ==================================================================================
""")
add_code("""
# CÉLULA 6: CORRELAÇÕES CLIMÁTICAS E CALOR SEMANAL
# ============================================================================
print("=" * 80)
print("PASSO 5: SPEARMAN DOS LAGS CLIMÁTICOS E CALOR TEMPORAL POR RA")
print("=" * 80)

print("\\n🔥 1. Heatmap Spearman: Correlação de Lags Climáticos vs Incidência de Dengue:")
print("-" * 80)
display(Image(filename='resultados_graficos/correlacao_lags_clima.png'))

print("\\n🔥 2. Heatmap RA vs Semana Epidemiológica (Evolução da Transmissão):")
print("-" * 80)
display(Image(filename='resultados_graficos/heatmap_ra_semana.png'))
""")

# ----------------- CELL 7: ROLLING VALIDATION -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 7: VALIDAÇÃO EM JANELA MÓVEL (ROLLING VALIDATION OPERACIONAL)
# ==================================================================================
""")
add_code("""
# CÉLULA 7: VALIDAÇÃO EM JANELA MÓVEL (ROLLING NOWCASTING)
# ============================================================================
print("=" * 80)
print("PASSO 6: VALIDAÇÃO EM JANELA MÓVEL (ROLLING NOWCASTING SEM LEAKAGE)")
print("=" * 80)

rolling_res = p.run_rolling_validation(dataset)

print("\\n[MÉTRICAS DE PERFORMANCE DA VALIDAÇÃO EM JANELA MÓVEL]")
print("-" * 80)
display(rolling_res)
""")

# ----------------- CELL 8: ABLATION TESTS -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 8: ANÁLISE DE ABLAÇÃO DE FEATURES (TESTE DE HIPÓTESES DE GANHO MARGINAL)
# ==================================================================================
""")
add_code("""
# CÉLULA 8: ANÁLISE DE ABLAÇÃO DE FEATURES
# ============================================================================
print("=" * 80)
print("PASSO 7: ANÁLISE DE ABLAÇÃO E CONTRIBUIÇÃO DE FEATURES")
print("=" * 80)

ablation_res, winner_config = p.run_ablation_tests(dataset)

print("\\n[RESULTADOS COMPARATIVOS DOS TESTES DE ABLAÇÃO]")
print("-" * 80)
display(ablation_res)

print("\\n[CONFIGURAÇÃO VENCEDORA (CRITÉRIO CONSERVADOR DELTA R² > 0.05)]")
print("-" * 80)
for k, v in winner_config.items():
    print(f"  • {k}: {v}")

print("\\n📊 1. Comparativo R² (DF) por Configuração de Features:")
print("-" * 80)
display(Image(filename='resultados_graficos/ablation_comparativo.png'))

print("\\n📊 2. Análise de Contribuição Marginal (vs Melhor Lag-Only):")
print("-" * 80)
display(Image(filename='resultados_graficos/ablation_contribuicao.png'))
""")

# ----------------- CELL 9: HYPERPARAMETER TUNING -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 9: TUNING E OTIMIZAÇÃO DE MODELOS (RF E XGBOOST)
# ==================================================================================
""")
add_code("""
# CÉLULA 9: TUNING E OTIMIZAÇÃO DOS MODELOS
# ============================================================================
print("=" * 80)
print("PASSO 8: OTIMIZAÇÃO DE HIPERPARÂMETROS DA CONFIGURAÇÃO VENCEDORA")
print("=" * 80)

tuning_res, final_predictions = p.tune_models(dataset, winner_config['config'])

print("\\n[RESULTADOS DO TUNING DE PARÂMETROS]")
print("-" * 80)
display(tuning_res)
""")

# ----------------- CELL 10: VISUALIZATIONS -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 10: IMPORTÂNCIA DE FEATURES E PREVISÕES FINAIS VS REALIDADE
# ==================================================================================
""")
add_code("""
# CÉLULA 10: IMPORTÂNCIA DE FEATURES E PREVISÕES FINAIS
# ============================================================================
print("=" * 80)
print("PASSO 9: IMPORTÂNCIA DE FEATURES E PERFORMANCE VISUAL FINAL")
print("=" * 80)

print("\\n📊 1. Importância de Features (Modelo XGBoost):")
print("-" * 80)
display(Image(filename='resultados_graficos/importancia_features_xgb.png'))

print("\\n📊 2. Previsão Final vs Casos Reais (Distrito Federal Total):")
print("-" * 80)
display(Image(filename='resultados_graficos/serie_df_total.png'))

print("\\n📊 3. Séries Temporais Detalhadas das Top 6 RAs com R² individual:")
print("-" * 80)
display(Image(filename='resultados_graficos/series_top6_ra.png'))

print("\\n📊 4. Incidência Média por Região Administrativa em 2025:")
print("-" * 80)
display(Image(filename='resultados_graficos/incidencia_por_ra_2025.png'))
""")

# ----------------- CELL 11: FEDERAL VALIDATION -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 11: VALIDAÇÃO FEDERAL (SINAN 2017 VS INFO-SAÚDE 2017)
# ==================================================================================
""")
add_code("""
# CÉLULA 11: VALIDAÇÃO FEDERAL (SINAN VS INFO-SAÚDE)
# ============================================================================
print("=" * 80)
print("PASSO 10: ALINHAMENTO HISTÓRICO SINAN vs INFO-SAÚDE (2017)")
print("=" * 80)

sinan_res = p.validate_sinan_infosaude(target_decision['target_name'])

print("\\n[MÉTRICAS DE ALINHAMENTO EPIDEMIOLÓGICO]")
print("-" * 80)
for k, v in sinan_res.items():
    if k != 'selected_codes':
        print(f"  • {k}: {v}")

print("\\n📊 Gráfico de Compatibilidade e Diferença Percentual Absoluta (Critério 15%):")
print("-" * 80)
display(Image(filename='resultados_graficos/sinan_infosaude_2017.png'))
""")

# ----------------- CELL 12: FINAL REPORT -----------------
add_markdown("""
# ==================================================================================
# CÉLULA 12: RESUMO EXECUTIVO E RELATÓRIO DO PIPELINE
# ==================================================================================
""")
add_code("""
# CÉLULA 12: RESUMO EXECUTIVO E RELATÓRIO FINAL
# ============================================================================
print("=" * 80)
print("PASSO 11: RESUMO EXECUTIVO DO RELATÓRIO FINAL")
print("=" * 80)

report_text = Path(p.FINAL_REPORT_MD).read_text(encoding='utf-8')
print(report_text)
""")

# Build Jupyter JSON structure
notebook_data = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "pygments_lexer": "ipython3"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

# Write Jupyter notebook file
NOTEBOOK_PATH.write_text(json.dumps(notebook_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Notebook '{NOTEBOOK_PATH.name}' gerado com sucesso!")
