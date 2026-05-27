# Revisao do Plano e do Repositorio - 2026-05-24

**Tags:** `review`, `plano`, `riscos`, `modelagem`, `validacao`
**Escopo:** Analise critica do estado atual do repositorio, do RFC/TDD e do `plano_prompts_opus.md`.

## Veredito Curto

O plano esta bem estruturado como roadmap exploratorio, mas ainda e arriscado como plano executavel de ponta a ponta. A recomendacao do RFC/TDD de comecar por um notebook local `info-saude` + clima e mais forte do que migrar diretamente para o pipeline hierarquico completo.

## Achados Principais

1. **Validacao atual e mais nowcasting do que forecast 52 semanas.**
   - `dengue_radf.py` calcula `cases_lag_1..4` em toda a serie antes da avaliacao.
   - No teste de 2025/2026, cada semana pode usar casos reais de semanas anteriores do proprio periodo de teste.
   - Isso e aceitavel para rolling/nowcasting semanal, mas nao para declarar previsao fechada de 52 semanas a partir de 2024-12-31.

2. **O baseline `cases_lag_1` quase empata com os modelos.**
   - Em `previsoes_finais_radf.csv`, `cases_lag_1` teve R2 aproximado de 0.697.
   - Random Forest teve R2 aproximado de 0.703 e XGBoost 0.684.
   - Isso sugere que o ganho real das features climaticas/espaciais ainda precisa ser demonstrado com ablation tests.

3. **O target precisa ser formalizado.**
   - O TDD recomenda filtrar `i_class_final == 'Caso Provavel'` e `i_desc_classificacao == 'Dengue'`.
   - O script atual filtra apenas `i_class_final == 'Caso Provavel'`.
   - Entre registros provaveis com RA valida, ha volume relevante de `Inconclusivo` e `Nao Informado`; decidir se entram no target muda a serie alvo.

4. **A estrategia hierarquica nacional tem risco metodologico.**
   - O plano combina SINAN nacional antigo (2001-2017) com `info-saude` local por RA (2017-2026).
   - Ha diferencas de granularidade, definicao de caso, cobertura e schema.
   - Antes da reconciliacao Brasil -> Regiao -> UF -> RA, e preciso provar compatibilidade temporal e semantica das series.

5. **Reprodutibilidade ainda e fraca.**
   - O workspace nao esta inicializado como repositorio Git.
   - Nao ha testes automatizados encontrados.
   - Nao ha `.gitignore`, `pyproject.toml`, lockfile ou configuracao de qualidade.
   - A `.venv` tem os pacotes Nixtla, mas `tensorflow` nao esta instalado apesar de aparecer em `requirements.txt`.

## Priorizacao Sugerida

| Prioridade | Ponto | Justificativa |
|---|---|---|
| P0 | Formalizar target epidemiologico e filtros | Define o que o modelo esta prevendo; muda todos os resultados. |
| P0 | Separar nowcasting rolling de forecast multi-step | Evita conclusoes infladas por uso de lags reais no teste. |
| P1 | Criar baselines e ablation tests | Mostra se clima, RA e populacao agregam valor alem de `cases_lag_1`. |
| P1 | Implementar o notebook MVP do RFC/TDD antes do hierarquico | Reduz risco e valida dados locais com transparencia. |
| P1 | Validar compatibilidade SINAN nacional vs info-saude local | Necessario antes da hierarquia nacional/RA. |
| P2 | Adicionar umidade do InfoDengue/NASA | Forte suporte biologico, mas depende de tratamento de nulos. |
| P2 | Trocar populacao estatica por historica no pipeline atual | Corrige vies demografico historico por RA/ano. |
| P2 | Adicionar testes de contratos de dados | Protege contra encoding, colunas ausentes e mudancas de schema. |
| P3 | Organizar projeto como pacote Python | Melhora manutencao, mas nao bloqueia a ciencia do modelo. |

## Sequencia Recomendada

1. Congelar definicao de target e filtros.
2. Criar notebook exploratorio com contratos de limpeza e graficos de qualidade.
3. Reavaliar `dengue_radf.py` com rolling validation explicita e baselines.
4. Fazer ablation: lag-only, lag+clima, lag+clima+RA, lag+clima+RA+populacao.
5. Somente depois adaptar Nixtla/reconciliacao hierarquica.
