# TDD-08: Expansão do Suite de Métricas Epidemiológicas

| Campo            | Valor                                                                 |
|------------------|-----------------------------------------------------------------------|
| **Tech Lead**    | @roger-quinelato                                                      |
| **Time**         | @roger-quinelato                                                      |
| **RFC de Origem**| [RFC-08](./RFC-08-metricas-epidemiologicas.md)                        |
| **Épico/Ticket** | —                                                                     |
| **Status**       | Draft                                                                 |
| **Criado em**    | 2026-05-29                                                            |
| **Atualizado**   | 2026-05-29                                                            |
| **RFC Bloqueado**| RFC-01 (Conformal Prediction) — não verificável sem coverage metric   |

---

## Contexto

O pipeline de forecasting de dengue (`dengue_pipeline`) produz previsões pontuais e intervalos de confiança probabilísticos via Conformal Prediction. O módulo central de avaliação, [`evaluation.py`](../src/dengue_pipeline/modeling/evaluation.py), já calcula métricas de erro pontual (R², MAE, RMSE, MAPE, sMAPE) e uma métrica de detecção de pico (`hit_rate_picos`).

**Background:**
O pipeline evoluiu para gerar intervalos de confiança (`lower_ci`, `upper_ci`) como parte da reforma do Conformal Prediction (RFC-01). No entanto, esses intervalos são gerados sem que haja qualquer avaliação formal de sua qualidade: não existe cálculo de cobertura empírica, calibração ou score probabilístico. Isso cria uma lacuna crítica entre o que o modelo produz e o que pode ser validado ou comparado com a literatura científica.

**Domínio:**
Epidemiologia computacional e forecasting de doenças infecciosas. O padrão de mercado para avaliação de modelos de forecasting epidemiológico — adotado pelo CDC Forecast Hub e pelo projeto FluSight — é o **Weighted Interval Score (WIS)**, que o pipeline atual não calcula.

**Stakeholders:**
- Pesquisadores que usam o pipeline para análise epidemiológica
- Orientador epidemiológico (validação dos critérios de surto)
- Comunidade científica (benchmarking via métricas padronizadas)
- RFC-01: a reforma do Conformal Prediction não pode ser verificada sem esta suite de métricas

---

## Definição do Problema e Motivação

### Problemas que Estamos Resolvendo

- **Problema 1 — Intervalos de Confiança sem Validação de Cobertura:**
  O módulo `consolidar_metricas_performance` em `evaluation.py` não calcula a cobertura empírica dos intervalos `[lower_ci, upper_ci]`. Isso significa que é impossível saber se o intervalo de 90% declarado pelo Conformal Prediction realmente cobre 90% das observações reais.
  - **Impacto:** O RFC-01 (reforma do CP) não pode ser verificado; intervalos podem estar sistematicamente sub- ou sobre-cobrindo sem detecção.

- **Problema 2 — Ausência de Métricas Padrão da Comunidade (WIS):**
  O WIS (Weighted Interval Score) é a métrica primária do CDC Forecast Hub para comparar modelos de forecasting epidemiológico. Sem ele, o pipeline é incomparável com benchmarks da literatura científica.
  - **Impacto:** Impossibilidade de publicação e de comparação com modelos de referência.

- **Problema 3 — Threshold de Pico Fixo e Não Validável:**
  O `hit_rate_picos` atual usa percentil P75 como limiar de surto, valor fixo no código, sem configurabilidade e sem métricas complementares como lead time de antecipação de pico ou erro de magnitude.
  - **Impacto:** Métricas de pico insuficientes para aplicação em vigilância epidemiológica real.

### Por que Agora?

- O RFC-01 (Conformal Prediction) está em andamento e **não pode ser verificado** sem métricas de cobertura
- Os intervalos de confiança já são gerados — a infraestrutura existe, falta apenas a avaliação
- A publicação científica dos resultados exige WIS como métrica primária comparável

### Impacto de Não Agir

- **Científico:** Impossibilidade de comparar o modelo com benchmarks internacionais (CDC Forecast Hub, FluSight)
- **Técnico:** RFC-01 fica tecnicamente inverificável; intervalos gerados sem garantia de qualidade
- **Operacional:** Threshold de pico P75 fixo pode não corresponder ao critério epidemiológico correto

---

## Escopo

### ✅ Em Escopo (V1 — MVP)

- Implementar `calcular_cobertura_intervalo(pred_df, alpha)` — proporção de observações dentro de `[lower_ci, upper_ci]`
- Implementar `calcular_wis(pred_df, alpha)` — versão simplificada com 1 intervalo de confiança (90%)
- Implementar `calcular_calibration_error(coverage_real, alpha)` — diferença entre cobertura declarada e real
- Tornar o threshold do `hit_rate_picos` configurável (parâmetro, não mais fixo em P75)
- Integrar as novas métricas ao retorno de `consolidar_metricas_performance` de forma aditiva (backward compatible)
- Atualizar os CSVs de resultados para incluir as novas colunas de métricas

### ❌ Fora de Escopo (V1)

- WIS completo com múltiplos quantis (11 ou 23 quantis do Forecast Hub) — versão simplificada suficiente para V1
- Integração com biblioteca externa (`properscoring`, `pyforecast`) — dependência externa desnecessária para V1
- Pinball Loss por múltiplos quantis — requer multi-quantile output não disponível ainda
- Dashboard visual de calibração automático — o calibration plot é sugerido como ação futura
- CRPS (Continuous Ranked Probability Score) — requer distribuição preditiva completa

### 🔮 Considerações Futuras (V2+)

- WIS completo com 23 quantis para submissão ao Forecast Hub
- Adoção de `properscoring` caso o pipeline evolua para output multi-quantil
- Calibration plot interativo integrado ao relatório HTML do pipeline
- Pinball Loss para avaliação por faixa de quantil

---

## Solução Técnica

### Visão Geral da Arquitetura

A implementação é cirúrgica e aditiva: as novas funções são adicionadas ao módulo `evaluation.py` e chamadas condicionalmente dentro de `consolidar_metricas_performance`, apenas quando `lower_ci` e `upper_ci` estiverem disponíveis no DataFrame de predições. Não há novos módulos, não há dependências externas, e os contratos de retorno existentes são preservados.

**Componentes Principais:**

- `evaluation.py` — módulo alvo; recebe novas funções de scoring probabilístico
- `consolidar_metricas_performance` — função orquestradora que agrega todas as métricas; receberá parâmetro `peak_threshold` configurável
- CSVs de resultados — schema expandido com novas colunas (backward compatible via valores `NaN` quando CI não disponível)

### Diagrama de Fluxo de Dados

```mermaid
flowchart TD
    A[pred_df com lower_ci / upper_ci] --> B{CI disponível?}
    B -- Não --> C[Métricas pontuais apenas\nR², MAE, RMSE, MAPE, sMAPE]
    B -- Sim --> D[Métricas pontuais +\nmétricas probabilísticas]
    D --> E[calcular_cobertura_intervalo\nProporção dentro do CI]
    D --> F[calcular_wis\nWeighted Interval Score]
    E --> G[calcular_calibration_error\n|coverage_real - 1-alpha|]
    D --> H[hit_rate_picos com threshold\nconfigurável via parâmetro]
    C --> I[consolidar_metricas_performance\nRetorna dict unificado]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[CSV de resultados\ncolunas novas com NaN quando N/A]
```

### Contratos das Novas Funções

#### `calcular_cobertura_intervalo`

| Campo        | Detalhe                                                          |
|--------------|------------------------------------------------------------------|
| **Entrada**  | `pred_df: DataFrame` com colunas `cases`, `lower_ci`, `upper_ci`; `alpha: float = 0.10` |
| **Saída**    | `float` — proporção em `[0, 1]`; `NaN` se CI ausente            |
| **Semântica**| Proporção de observações reais dentro do intervalo declarado     |

**Lógica:** `mean(cases >= lower_ci AND cases <= upper_ci)`

---

#### `calcular_wis`

| Campo        | Detalhe                                                          |
|--------------|------------------------------------------------------------------|
| **Entrada**  | `pred_df: DataFrame` com `lower_ci`, `upper_ci`, `cases`; `alpha: float = 0.10` |
| **Saída**    | `float` — score não-negativo; menor é melhor; `NaN` se CI ausente |
| **Semântica**| Penaliza dispersão do intervalo + violações abaixo + violações acima |

**Decomposição:**
- `spread` = `upper_ci - lower_ci` (penalidade de amplitude)
- `undershoot` = `(2/alpha) × max(0, lower_ci - cases)` (saída inferior)
- `overshoot` = `(2/alpha) × max(0, cases - upper_ci)` (saída superior)
- `WIS` = `mean(spread + undershoot + overshoot)`

> **Nota de limitação:** Esta é a versão de 1 intervalo. O WIS completo do Forecast Hub usa 23 quantis; a versão aqui é uma aproximação válida para validação interna.

---

#### `calcular_calibration_error`

| Campo        | Detalhe                                                              |
|--------------|----------------------------------------------------------------------|
| **Entrada**  | `coverage_real: float`, `alpha: float = 0.10`                        |
| **Saída**    | `float` — erro em `[0, 1]`; zero é ideal                            |
| **Semântica**| Distância entre cobertura declarada `(1 - alpha)` e cobertura real  |

**Lógica:** `abs(coverage_real - (1 - alpha))`

---

#### Mudança em `hit_rate_picos`

| Campo        | Detalhe                                                                  |
|--------------|--------------------------------------------------------------------------|
| **Antes**    | Threshold fixo: `P75` hardcoded                                          |
| **Depois**   | Parâmetro `peak_threshold: float = 0.75` em `consolidar_metricas_performance` |
| **Compatibilidade** | Default `0.75` preserva comportamento atual; valor epidemiológico pode ser passado externamente |

---

### Schema dos CSVs de Resultados — Novas Colunas

| Coluna                | Tipo    | Disponível Quando            | Descrição                                         |
|-----------------------|---------|------------------------------|---------------------------------------------------|
| `coverage`            | float   | CI disponível                | Cobertura empírica do intervalo de confiança      |
| `wis`                 | float   | CI disponível                | Weighted Interval Score (1 intervalo, α=0.10)     |
| `calibration_error`   | float   | CI disponível                | \|coverage - 0.90\|                               |
| `peak_threshold`      | float   | Sempre                       | Percentil usado como limiar de detecção de pico   |

> Quando CI não está disponível, as colunas `coverage`, `wis` e `calibration_error` terão valor `NaN`, garantindo backward compatibility.

---

## Riscos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| WIS simplificado (1 intervalo) subestimar penalidades em cauda | Médio | Alto | Documentar limitação explicitamente; planejar WIS completo para V2; comparar com literatura ciente da simplificação |
| DataFrames de predição sem `lower_ci`/`upper_ci` causando falha silenciosa | Alto | Médio | Guards com `isna().all()` retornando `NaN`; teste unitário cobrindo o caminho sem CI |
| Threshold configurável de pico quebrando comparabilidade histórica | Médio | Baixo | Default `0.75` preserva comportamento atual; logar o valor de threshold no CSV de resultados |
| Aumento de tamanho dos CSVs de resultados | Baixo | Alto | Impacto aceitável; 4 colunas novas por run; monitorar tamanho se volume crescer |
| RFC-01 gerar CI incorretos que distorcem métricas de coverage | Alto | Baixo | Métricas de coverage são exatamente a ferramenta para detectar este problema; a suite é auto-diagnóstica |

---

## Plano de Implementação

| Fase | Tarefa | Descrição | Responsável | Status | Estimativa |
|------|--------|-----------|-------------|--------|------------|
| **Fase 1 — Funções Core** | `calcular_cobertura_intervalo` | Implementar com guard para CI ausente; retornar `NaN` graciosamente | @roger | TODO | 1h |
| | `calcular_wis` | Implementar WIS 1-intervalo; documentar limitação vs. WIS completo | @roger | TODO | 1h |
| | `calcular_calibration_error` | Implementar; recebe `coverage_real` já calculada | @roger | TODO | 30min |
| **Fase 2 — Integração** | Refatorar `consolidar_metricas_performance` | Adicionar parâmetro `peak_threshold`; chamar novas funções condicionalmente | @roger | TODO | 1h |
| | Atualizar schema CSV | Garantir novas colunas com `NaN` quando CI ausente | @roger | TODO | 30min |
| **Fase 3 — Testes** | Testes unitários das funções | Testar: CI presente, CI ausente (NaN), limiar de calibração | @roger | TODO | 1h |
| | Teste de integração no pipeline | Rodar pipeline completo e validar presença das novas métricas no CSV | @roger | TODO | 30min |
| **Fase 4 — Documentação** | Docstrings e comentários | Documentar limitações do WIS simplificado; parâmetros configuráveis | @roger | TODO | 30min |

**Estimativa Total:** ~5–6 horas  
**Sequência obrigatória:** Fase 1 → Fase 2 → Fase 3 → Fase 4

---

## Estratégia de Testes

| Tipo de Teste | Escopo | Abordagem |
|---------------|--------|-----------|
| **Unitário** | Cada função de métrica isoladamente | Fixtures com DataFrames sintéticos; casos: CI perfeito, CI ruim, CI ausente |
| **Integração** | `consolidar_metricas_performance` com e sem CI | DataFrame real ou sintético; verificar presença e validade das colunas no retorno |
| **Regressão** | Comportamento existente inalterado | Rodar suite existente de testes; verificar que métricas anteriores não mudaram |

### Cenários de Teste Críticos

**Testes Unitários — `calcular_cobertura_intervalo`:**
- ✅ Todos os valores dentro do CI → cobertura = 1.0
- ✅ Nenhum valor dentro do CI → cobertura = 0.0
- ✅ 50% dos valores dentro → cobertura ≈ 0.5
- ✅ `lower_ci` ausente (todos NaN) → retorna `NaN` sem exceção

**Testes Unitários — `calcular_wis`:**
- ✅ Previsão perfeita (cases = midpoint, CI estreito) → WIS baixo
- ✅ CI muito largo → penalidade de spread alta
- ✅ Observações abaixo do CI → undershoot penalizado
- ✅ `lower_ci` ausente → retorna `NaN`

**Testes Unitários — `calcular_calibration_error`:**
- ✅ `coverage_real = 0.90`, `alpha = 0.10` → erro = 0.0 (calibração perfeita)
- ✅ `coverage_real = 0.70`, `alpha = 0.10` → erro = 0.20 (undercoverage)
- ✅ `coverage_real = 0.98`, `alpha = 0.10` → erro = 0.08 (overcoverage)

**Testes de Integração:**
- ✅ `consolidar_metricas_performance` com DataFrame sem CI → retorna dict com `NaN` nas métricas probabilísticas
- ✅ `consolidar_metricas_performance` com CI presente → todas as novas métricas populadas com floats válidos
- ✅ `peak_threshold=0.90` produz resultado diferente de `peak_threshold=0.75`

---

## Monitoramento e Observabilidade

> Este é um módulo de análise científica off-line (não um serviço web). As métricas de "monitoramento" são as próprias métricas calculadas, registradas em CSV.

### Valores de Referência para Calibração

| Métrica | Valor Ideal | Sinal de Alerta |
|---------|-------------|-----------------|
| `coverage` | ≈ 0.90 (para α=0.10) | < 0.80 (undercoverage severo) ou > 0.98 (overcoverage) |
| `calibration_error` | ≈ 0.0 | > 0.10 (diferença de 10pp ou mais) |
| `wis` | Menor possível (comparativo) | Aumento relativo entre runs sem mudança de dados |

### Rastreabilidade

- Todas as métricas (incluindo `peak_threshold` usado) são registradas no CSV de resultados por `run_id`
- Permite comparação histórica entre runs e auditoria de qual threshold foi aplicado

### Logs Esperados

- Log de aviso quando CI ausente: indicar que métricas probabilísticas não foram calculadas
- Log do valor de `peak_threshold` efetivamente utilizado por run

---

## Plano de Rollback

### Estratégia de Deploy

As mudanças são **aditivas e backward compatible**: novas colunas no CSV com `NaN` quando CI ausente, parâmetro `peak_threshold` com default que preserva comportamento atual. Não há alteração destrutiva.

### Gatilhos de Rollback

| Gatilho | Ação |
|---------|------|
| Funções novas causam exceção em DataFrames sem CI | Reverter para versão anterior do `evaluation.py` via `git revert` |
| `consolidar_metricas_performance` quebra chamadores existentes | Reverter; investigar compatibilidade do parâmetro `peak_threshold` |
| CSVs existentes quebram importadores downstream | Reverter schema; investigar pipeline de leitura dos CSVs |

### Passos de Rollback

1. Identificar o commit da última versão estável de `evaluation.py`
2. Reverter o arquivo via controle de versão
3. Verificar que métricas pontuais continuam calculando corretamente
4. Investigar root cause antes de re-implementar

---

## Métricas de Sucesso

| Métrica | Critério de Aceitação |
|---------|----------------------|
| Cobertura calculável | `calcular_cobertura_intervalo` retorna float válido (não NaN) para DataFrames com CI |
| WIS calculável | `calcular_wis` retorna float não-negativo para DataFrames com CI |
| Calibration Error | `calcular_calibration_error` retorna `0.0` dado coverage_real = 1 - alpha (teste unitário) |
| Backward compatibility | Todos os testes existentes passam sem modificação |
| RFC-01 verificável | Coverage empírica do Conformal Prediction é mensurável após implementação |
| Threshold configurável | `hit_rate_picos` produz resultados diferentes para valores distintos de `peak_threshold` |

---

## Glossário

| Termo | Descrição |
|-------|-----------|
| **WIS** | Weighted Interval Score — métrica probabilística que penaliza amplitude do intervalo e violações; padrão do CDC Forecast Hub |
| **Coverage (Cobertura Empírica)** | Proporção de observações reais que caem dentro do intervalo de confiança previsto |
| **Calibration Error** | Diferença absoluta entre cobertura declarada (ex: 90%) e cobertura real observada |
| **Conformal Prediction** | Framework estatístico para gerar intervalos de confiança com garantias de cobertura; implementado no RFC-01 |
| **Undercoverage** | Situação em que o intervalo de 90% cobre menos de 90% das observações reais |
| **Overcoverage** | Situação em que o intervalo de 90% cobre mais de 90% das observações (intervalo muito conservador) |
| **Pinball Loss** | Métrica para avaliar calibração por quantil individual; requer output multi-quantil |
| **Hit Rate de Pico** | Proporção de picos epidêmicos reais corretamente detectados pelo modelo, dado um threshold de amplitude |
| **Lead Time de Pico** | Antecedência com que o modelo detecta um pico epidêmico antes do pico real |
| **α (alpha)** | Nível de significância do intervalo; para 90% CI, α = 0.10 |
| **`lower_ci` / `upper_ci`** | Colunas do DataFrame de predições representando o intervalo de confiança inferior e superior |
| **Forecast Hub** | Plataforma colaborativa de forecasting epidemiológico mantida pelo CDC; padrão de benchmarking para modelos de doenças infecciosas |

---

## Alternativas Consideradas

| Opção | Prós | Contras | Decisão |
|-------|------|---------|---------|
| **Opção 1 — numpy/pandas puro** ⭐ (Escolhida) | Sem dependência externa; backward compatible; implementável em 3–4h | WIS simplificado (1 intervalo); Pinball Loss não disponível | **Escolhida** — melhor custo-benefício para V1 |
| **Opção 2 — Biblioteca `properscoring`** | WIS multi-quantil completo; CRPS; implementações validadas | Desenvolvimento parado desde 2015; overhead de dependência; versão simplificada suficiente para V1 | Descartada para V1; revisitar se pipeline evoluir para multi-quantil |
| **Opção 3 — Do Nothing** | Sem custo imediato | RFC-01 não verificável; impossível benchmarking com literatura; intervalos sem validação | Descartada — custo futuro muito alto |

**Critério de Decisão Principal:** Reprodutibilidade e rastreabilidade sem dependências externas; comparabilidade futura com Forecast Hub (WIS) via implementação própria evolutiva.

---

## Questões em Aberto

| # | Questão | Contexto | Responsável | Status | Prazo Decisão |
|---|---------|----------|-------------|--------|---------------|
| 1 | Qual o threshold epidemiológico correto para detecção de surto? | P75 é estatístico; critério epidemiológico pode ser diferente (ex: 2× média histórica) | @roger + orientador | 🔴 Aberta | TBD |
| 2 | WIS completo (23 quantis) é necessário para publicação científica alvo? | Depende do journal/conferência; Forecast Hub exige | @roger | 🟡 Em análise | TBD |
| 3 | O calibration plot deve ser gerado automaticamente no relatório? | RFC menciona como ação futura mas não está no escopo V1 | @roger | ✅ Resolvido: V2 | 2026-05-27 |

**Legenda:** 🔴 Aberta — precisa de decisão · 🟡 Em análise — sendo discutida · ✅ Resolvida

---

## Roadmap / Timeline

| Fase | Entregáveis | Estimativa | Status |
|------|-------------|------------|--------|
| **Fase 1** — Funções Core | `calcular_cobertura_intervalo`, `calcular_wis`, `calcular_calibration_error` | 2.5h | ⏳ Pendente |
| **Fase 2** — Integração | Refatoração de `consolidar_metricas_performance`; schema CSV atualizado | 1.5h | ⏳ Pendente |
| **Fase 3** — Testes | Suite de testes unitários e de integração | 1.5h | ⏳ Pendente |
| **Fase 4** — Documentação | Docstrings, comentários de limitação, atualização do README de métricas | 0.5h | ⏳ Pendente |

**Estimativa Total:** ~6 horas  

**Marcos:**
- 🎯 M1: Funções core implementadas e testadas — RFC-01 pode ser verificado
- 🎯 M2: Integração completa — pipeline gera métricas probabilísticas por run
- 🎯 M3: Documentação — limitações do WIS simplificado documentadas para uso científico

**Caminho Crítico:**
Fase 1 (funções) → Fase 2 (integração) → Fase 3 (testes) → Fase 4 (docs)

**Dependência:** A verificação de RFC-01 (Conformal Prediction) aguarda o M1 deste TDD.

---

## Aprovação

| Papel | Responsável | Status | Data | Comentários |
|-------|-------------|--------|------|-------------|
| Tech Lead | @roger-quinelato | ⏳ Pendente | — | — |
| Orientador Epidemiológico | — | ⏳ Pendente | — | Validar threshold de pico (Questão Aberta #1) |

**Critérios de Aprovação:**
- ✅ Todas as seções obrigatórias presentes
- ✅ Riscos identificados com mitigações
- ✅ Backward compatibility garantida no design
- ⏳ Questão #1 (threshold epidemiológico) respondida antes da implementação final

**Próximos Passos Após Aprovação:**
1. Iniciar Fase 1 — implementar as três funções core em `evaluation.py`
2. Resolver Questão Aberta #1 com orientador antes de fixar `peak_threshold` padrão
3. Atualizar RFC-01 com referência a este TDD como pré-requisito de verificação
