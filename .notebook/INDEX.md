# DocML — Caderno de Inteligência do Projeto

Projeto de modelagem preditiva de **arbovirose da dengue no Distrito Federal (DF)**, usando séries temporais epidemiológicas cruzadas com dados climáticos e demográficos por Região Administrativa.

## Entradas do Caderno

| Arquivo | Tags | Resumo |
|---|---|---|
| [repo-overview.md](repo-overview.md) | `estrutura`, `visão-geral`, `scripts` | Mapa geral do repositório: scripts, dados, saídas |
| [pipeline-radf.md](pipeline-radf.md) | `pipeline`, `pipeline_modelagem_dengue.py`, `features`, `modelos` | Pipeline completo de `pipeline_modelagem_dengue.py`: fluxo de dados e features |
| [bases-de-dados.md](bases-de-dados.md) | `dados`, `info-saude`, `dados-gov`, `colunas` | Estrutura e conteúdo das bases epidemiológicas |
| [literatura-algoritmos.md](literatura-algoritmos.md) | `artigos`, `algoritmos`, `variáveis`, `literatura` | Síntese dos artigos: melhores algoritmos e variáveis preditoras |
| [ambiente-dependencias.md](ambiente-dependencias.md) | `venv`, `requirements`, `setup` | Configuração do ambiente virtual e dependências |
| [infodengue.md](infodengue.md) | `dados`, `infodengue`, `fiocruz`, `clima`, `alertas` | Dados semanais oficiais do InfoDengue (Fiocruz/FGV) para Brasília |
| [rfc-002-pipeline-dados-modelagem.md](rfc-002-pipeline-dados-modelagem.md) | `pipeline`, `proposta`, `notebook`, `lags` | RFC-002: Proposta de pipeline estruturado interativo no Jupyter |
| [adr-001-modularizacao-pipeline-python.md](adr-001-modularizacao-pipeline-python.md) | `decisão`, `adr`, `arquitetura`, `modularização` | ADR-001: Decisão de migrar do pipeline monolítico para um pacote modular |
| [adr-002-uso-populacao-historica.md](adr-002-uso-populacao-historica.md) | `decisão`, `adr`, `demografia`, `métricas` | ADR-002: Decisão de usar denominators populacionais dinâmicos |
| [adr-003-conformal-prediction-dinamico.md](adr-003-conformal-prediction-dinamico.md) | `decisão`, `adr`, `incerteza`, `conformal` | ADR-003: Decisão de usar conformal prediction dinâmico para bandas de confiança |
| [adr-004-versionamento-runs-timestamp.md](adr-004-versionamento-runs-timestamp.md) | `decisão`, `adr`, `versionamento`, `reprodutibilidade` | ADR-004: Decisão de versionar execuções do pipeline com Run-ID e latest/ |
| [tdd-notebook-limpeza-modelagem.md](tdd-notebook-limpeza-modelagem.md) | `tdd`, `arquitetura`, `notebook`, `limpeza` | TDD: Especificação técnica da limpeza de dados e modelagem |
| [relatorio_revisao_arquitetura.md](relatorio_revisao_arquitetura.md) | `revisão`, `plano`, `riscos`, `validação` | Revisão crítica do plano, riscos de validação, target e prioridades |
| [target-formalizacao.md](target-formalizacao.md) | `target`, `p0`, `filtros` | Decisão documentada do target epidemiológico usado na modelagem |
| [relatorio_final_execucao.md](relatorio_final_execucao.md) | `relatório`, `ablação`, `modelagem` | Resultado final da execução P0/P1 do plano de execução do pipeline |
| [validacao_consistencia_fontes.md](validacao_consistencia_fontes.md) | `sinan`, `validação`, `p2` | Validação de compatibilidade entre SINAN 2017 e info-saude |
| [plano_modularizacao_arquitetura.md](plano_modularizacao_arquitetura.md) | `modularização`, `arquitetura`, `refatoração` | Plano de modularização da arquitetura e organização do pipeline |
| [auditoria-fase1-mapeamento-arquitetural.md](auditoria-fase1-mapeamento-arquitetural.md) | `auditoria`, `arquitetura`, `leakage`, `duplicação`, `pontos-criticos` | Mapeamento completo do fluxo de dados, pontos críticos e gotchas identificados na Fase 1 da auditoria |
| [auditoria-fases2-3-estrutura-qualidade.md](auditoria-fases2-3-estrutura-qualidade.md) | `auditoria`, `estrutura`, `qualidade`, `duplicação`, `iterrows`, `design-patterns` | Diagnóstico de duplicações, poluição de diretórios e padrões ineficientes/hardcoded avaliados nas Fases 2 e 3 |
| [stress_test_pre_mortem.md](stress_test_pre_mortem.md) | `estresse`, `devil-advocate`, `pre-mortem`, `avaliação` | Auditoria de estresse profunda e análise pre-mortem sob a postura de revisor cético |
| [relatorio_seguranca_data_leakage.md](relatorio_seguranca_data_leakage.md) | `segurança`, `data-leakage`, `data-leak`, `vulnerabilidades` | Relatório detalhado das vulnerabilidades de segurança e diagnóstico do "leaky" do repositório |
| [historico-evolucao-projeto.md](historico-evolucao-projeto.md) | `histórico`, `resultados`, `evolução` | Consolidado histórico do progresso dos modelos, métricas e justificativa de mudanças do DocML |
| [fundamentacao-matematica.md](fundamentacao-matematica.md) | `matemática`, `fórmulas`, `conformal-prediction`, `métricas` | Raciocínio matemático rigoroso, equações de conformal prediction e justificativas de métricas no DocML |


## Contexto Rápido

- **Script principal de execução:** `python -m dengue_pipeline` — Executa todo o pipeline modularizado e gera resultados versionados.
- **Script principal de modelagem legado:** `legacy/pipeline_modelagem_dengue.py` — Modelagem original RF + XGBoost por Região Administrativa.
- **Dados epidemiológicos locais:** `info-saude/` (2017-2026, por RA do DF, semicolon-separated).
- **Dados nacionais SINAN:** `dados-gov/` (2001-2017, 107 colunas clínicas, filtrar `SG_UF == '53'` para DF).
- **Dados InfoDengue Fiocruz:** `InfoDengue/` (2006-2026, série integrada oficial com umidade e níveis de alerta).
- **Clima:** `dados_clima_cache.csv` (Open-Meteo, Brasília, semanal, desde 2016).
- **Ambiente virtual:** `.venv/` (Python 3.10, criado via `python -m venv .venv`).
