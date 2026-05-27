# DocML — Notebook de Inteligência do Projeto

Projeto de modelagem preditiva de **arbovirose da dengue no Distrito Federal (DF)**, usando séries temporais epidemiológicas cruzadas com dados climáticos e demográficos por Região Administrativa.

## Entradas do Notebook

| Arquivo | Tags | Resumo |
|---|---|---|
| [repo-overview.md](repo-overview.md) | `estrutura`, `visão-geral`, `scripts` | Mapa geral do repositório: scripts, dados, saídas |
| [pipeline-radf.md](pipeline-radf.md) | `pipeline`, `dengue_radf.py`, `features`, `modelos` | Pipeline completo de dengue_radf.py: fluxo de dados e features |
| [bases-de-dados.md](bases-de-dados.md) | `dados`, `info-saude`, `dados-gov`, `colunas` | Estrutura e conteúdo das bases epidemiológicas |
| [literatura-algoritmos.md](literatura-algoritmos.md) | `artigos`, `algoritmos`, `variáveis`, `literatura` | Síntese dos artigos: melhores algoritmos e variáveis preditoras |
| [ambiente-dependencias.md](ambiente-dependencias.md) | `venv`, `requirements`, `setup` | Configuração do ambiente virtual e dependências |
| [infodengue.md](infodengue.md) | `dados`, `infodengue`, `fiocruz`, `clima`, `alertas` | Dados semanais oficiais do InfoDengue (Fiocruz/FGV) para Brasília |
| [rfc-002-pipeline-dados-modelagem.md](rfc-002-pipeline-dados-modelagem.md) | `pipeline`, `proposta`, `notebook`, `lags` | RFC-002: Proposta de pipeline estruturado interativo no Jupyter |
| [adr-002-uso-populacao-historica.md](adr-002-uso-populacao-historica.md) | `decisão`, `adr`, `demografia`, `métricas` | ADR-002: Decisão de usar a base de dados populacao_historica.csv |
| [tdd-notebook-limpeza-modelagem.md](tdd-notebook-limpeza-modelagem.md) | `tdd`, `arquitetura`, `notebook`, `limpeza` | TDD: Especificação técnica da limpeza de dados e modelagem |
| [revisao-plano-repositorio-2026-05-24.md](revisao-plano-repositorio-2026-05-24.md) | `review`, `plano`, `riscos`, `validacao` | Revisao critica do plano, riscos de validacao, target e prioridades |
| [target-formalizacao.md](target-formalizacao.md) | `target`, `p0`, `filtros` | Decisao documentada do target epidemiologico usado na modelagem |
| [relatorio-final-plano-prompts-opus.md](relatorio-final-plano-prompts-opus.md) | `relatorio`, `ablation`, `modelagem` | Resultado final da execucao P0/P1 do plano revisado |
| [validacao-sinan-infosaude.md](validacao-sinan-infosaude.md) | `sinan`, `validacao`, `p2` | Validacao de compatibilidade entre SINAN 2017 e info-saude |
| [plano_refatoracao_modular.md](plano_refatoracao_modular.md) | `refatoração`, `modularidade`, `prompts` | Plano cronológico com prompts de implementação e loops auto-corretivos para refatorar o pipeline |


## Contexto Rápido

- **Script principal de execução:** `dengue_radf.py` — Pipeline completo RF + XGBoost por RA
- **Script de séries hierárquicas:** `dengue.py` — AutoARIMA + AutoTheta + AutoETS + XGBoost com reconciliação
- **Dados epidemiológicos locais:** `info-saude/` (2017-2026, por RA do DF, semicolon-separated)
- **Dados nacionais SINAN:** `dados-gov/` (2001-2017, 107 colunas clínicas, filtrar `SG_UF == '53'` para DF)
- **Dados InfoDengue Fiocruz:** `InfoDengue/` (2006-2026, série integrada oficial com umidade e níveis de alerta)
- **Clima:** `dados_clima_cache.csv` (Open-Meteo, Brasília, semanal, desde 2016)
- **Ambiente virtual:** `.venv/` (Python 3.10, criado via `python -m venv .venv`)
