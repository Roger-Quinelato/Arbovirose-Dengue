# DocML — Modelagem Preditiva de Dengue no Distrito Federal

Este repositório contém o ecossistema completo para a modelagem preditiva de surtos de dengue no Distrito Federal (DF). O projeto utiliza dados epidemiológicos locais e nacionais integrados a fatores climáticos históricos (temperatura, precipitação e umidade) e demográficos ajustados por Região Administrativa (RA).

---

## 🗺️ Estrutura do Repositório

O projeto segue um modelo de arquitetura de dados e de código organizado por domínio:

*   **`artigos/`**: Artigos científicos de referência que baseiam a modelagem e as abordagens de *One Health*, incluindo projeções demográficas da Codeplan.
*   **`dados-gov/`**: Dados nacionais brutos do SINAN (fichas individuais do Ministério da Saúde) contendo detalhamento clínico e exames.
*   **`info-saude/`**: Série de dados epidemiológicos locais do DF, divididos por Região Administrativa de residência.
*   **`InfoDengue/`**: Série histórica semanal oficial integrada da plataforma InfoDengue (Fiocruz/FGV) para Brasília.
*   **`dados_processados/`**: Arquivos gerados durante a ingestão e feature engineering, como caches de clima, população histórica calibrada e targets.
*   **`resultados_modelagem/`**: Saídas dos modelos preditivos, testes de ablação de features, tuning de hiperparâmetros e validação (rolling validation).
*   **`resultados_graficos/`**: Visualizações analíticas, comparativos de dispersão, métricas de importância (feature importance) e séries temporais.
*   **`src/dengue_pipeline/`**: Código-fonte modular da pipeline principal, subdividido em camadas de ETL, modelagem e relatórios.
*   **`scripts/`**: Scripts auxiliares de coleta (ex: NASA POWER), utilitários e rotinas secundárias.
*   **`.notebook/`**: Base de inteligência do projeto com registros de decisões de arquitetura (ADRs) e documentos de design.

---

## ⚙️ Arquivos e Scripts Principais

*   **`dengue_radf.py`**: Pipeline monolítico de experimentação, executando o carregamento, limpeza, engenharia de lags e treinamento (RF e XGBoost).
*   **`src/dengue_pipeline/...`**: Módulos especializados que lidam com a ingestão e transformação de casos e clima, e a validação cruzada estruturada.
*   **`scripts/gerar_populacao_historica.py`**: Gera a base demográfica calibrada pós-Censo 2022 (gravada em `dados_processados/populacao_historica.csv`).
*   **`scripts/fetch_nasa_power.py`**: Rotina para requisitar as séries diárias completas do NASA POWER para o DF.

---

## 🚀 Como Começar

### 1. Configurar o ambiente virtual
O projeto utiliza Python 3.10. Ative o ambiente virtual e instale as dependências executando:

```powershell
# PowerShell (Windows)
.venv\Scripts\Activate.ps1

# Instalação das dependências
pip install -r requirements.txt
```

### 2. Gerar a base de população histórica
Gere a base de população dinâmica executando:

```bash
python scripts/gerar_populacao_historica.py
```
*(O arquivo será salvo em `dados_processados/populacao_historica.csv`)*

### 3. Executar o pipeline
Para executar a modelagem completa e gerar os gráficos:

```bash
python dengue_radf.py
```

Os relatórios analíticos, arquivos processados e métricas serão distribuídos automaticamente entre as pastas `dados_processados/`, `resultados_modelagem/` e `resultados_graficos/`.
