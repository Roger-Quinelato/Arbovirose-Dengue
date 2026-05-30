# RFC-01: Reforma Matemática do Conformal Prediction Temporal

| Campo            | Valor                                                                 |
|------------------|-----------------------------------------------------------------------|
| **Impacto**      | HIGH — afeta validade estatística dos intervalos de confiança        |
| **Status**       | NOT STARTED                                                           |
| **Driver**       | @roger-quinelato — responsável pela modelagem e pesquisa             |
| **Aprovador**    | @roger-quinelato                                                      |
| **Contribuidores** | Orientador/Banca (se aplicável)                                    |
| **Informados**   | Stakeholders do pipeline de vigilância                               |
| **Prazo**        | Antes da próxima submissão/apresentação                              |
| **Criado em**    | 2026-05-27                                                            |
| **Atualizado**   | 2026-05-27                                                            |

---

## Background

**Estado Atual:**
O módulo [`conformal_prediction.py`](../src/dengue_pipeline/modeling/conformal_prediction.py) implementa bandas de incerteza usando a fórmula:

```python
expansion_factor = np.sqrt(max(1, horizonte_k))
margin = q_conf * (prediction + epsilon) * expansion_factor
```

Adicionalmente, o score de não-conformidade proporcional `s_i = |y_i - ŷ_i| / (ŷ_i + ε)` usa `epsilon=0.01` como único fator de estabilização.

**Problema:**
Dois erros matemáticos convivem no mesmo módulo:

1. **Erro do sqrt(k):** A regra `sqrt(k)` assume que erros de previsão são i.i.d. — pressuposto do Movimento Browniano. Dinâmicas de doenças infecciosas (SEIR/SIR) são sistemas não-lineares com autocorrelação temporal, regime switching e explosões exponenciais durante surtos. Em `k > 2`, a margem subestima drasticamente a incerteza real do horizonte.

2. **Instabilidade near-zero:** Em períodos endêmicos, `ŷ ≈ 0`, logo `scale = ŷ + 0.01 ≈ 0.01`, tornando o score `s_i = |erro| / 0.01` artificialmente gigantesco. Isso gera overcoverage artificial (intervalos absurdamente largos) em baixa incidência e má calibração heteroscedástica.

**Por que agora:**
Estes erros comprometem qualquer análise de cobertura (coverage) dos intervalos e invalidam comparações com benchmarks de literatura (WIS, CRPS). Para um nível de doutorado/Applied Research Engineer, a validade marginal do conformal precisa ser demonstrável matematicamente.

**Consequência de não agir:**
- Intervalos de confiança sem validade estatística demonstrável
- Impossibilidade de publicar resultados de calibração
- Cobertura empírica (coverage) não correspondendo ao alpha declarado (90%)

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | O conjunto de calibração (26 semanas) é suficientemente representativo da distribuição de erros | Médio | Dados de um único surto atípico dominarem a calibração |
| 2 | Há dados históricos suficientes para calibração por horizonte k | Médio | Histórico < 3 anos por RA |
| 3 | Nenhuma mudança de regime epidemiológico maior durante o período de calibração | Baixo | Pandemia ou novo sorotipo dominante |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Validade estatística demonstrável (cobertura empírica ≥ 1-alpha) | Must-have |
| 2 | Compatibilidade com pipelines existentes de scoring | Alto |
| 3 | Custo computacional de re-calibração aceitável | Médio |
| 4 | Interpretabilidade dos intervalos para tomadores de decisão epidemiológicos | Médio |

---

## Dados Relevantes

- **Cobertura atual:** Não mensurada formalmente — ausência de `coverage_score` nos resultados
- **Arquivo afetado:** [`conformal_prediction.py`](../src/dengue_pipeline/modeling/conformal_prediction.py) linhas 92–103
- **Literatura de referência:**
  - EnbPI (Xu & Xie, 2021) — Conformal para séries temporais com exchangeability relaxada
  - CPTC (Rose-STL-Lab) — CP para forecasting com change points
  - Papadopoulos (2008) — fundamentação do score proporcional

---

## Opções Consideradas

### Opção 1: Calibração Horizon-Specific ⭐ (Recomendada)

**Descrição:**
Treinar um score conformal separado para cada horizonte `k ∈ {1, 2, ..., K_max}`. Para cada k, a calibração usa apenas os erros cometidos exatamente naquele horizonte.

**Como funciona:**
1. Para cada `k`, separar os erros de previsão do fold de calibração no horizonte `k`
2. Calcular `q_conf_k = quantil((n+1)(1-α)/n)` dos scores apenas em horizonte `k`
3. Aplicar `margin_k = q_conf_k * (ŷ + ε_adaptativo)` sem o fator `sqrt(k)`
4. Para `ε` adaptativo: usar `max(ε_min, percentil_10(ŷ_calibracao))` para estabilizar near-zero

**Prós:**
- Elimina completamente a heurística `sqrt(k)` e sua suposição i.i.d.
- Cobertura marginal válida por horizonte
- Compatível com o framework conformal existente (apenas múltiplos `q_conf_k`)
- Tratamento explícito de instabilidade near-zero via `ε` adaptativo

**Contras:**
- Requer mais dados de calibração (pelo menos `n_cal / K_max` amostras por horizonte)
- Aumenta complexidade do `calibrar_intervalos_confianca`

**Custo estimado:** MÉDIO — ~2–3 dias de implementação e validação de cobertura

---

### Opção 2: Block Conformal / Rolling Conformal

**Descrição:**
Usar janelas de calibração por blocos temporais, respeitando a estrutura de autocorrelação. O quantil `q_conf` é recalculado a cada passo usando apenas a janela de `W` semanas anteriores (rolling calibration).

**Prós:**
- Captura drift sazonal automaticamente
- Mais robusto a mudanças de regime

**Contras:**
- Custo computacional maior (re-calibração a cada predição)
- Implementação mais complexa que horizon-specific
- Sensível ao tamanho da janela `W`

**Custo estimado:** GRANDE — ~5–7 dias

---

### Opção 3: Manter status quo (Do Nothing)

**Descrição:** Manter `margin = q_conf * scale * sqrt(k)` e `epsilon=0.01`.

**Prós:**
- Nenhum custo imediato

**Contras:**
- Intervalos de confiança sem validade estatística formal
- Publicação de resultados de calibração inviabilizada
- Erro permanece não documentado no código

**Custo estimado:** NULO agora / ALTO futuro (retrabalho pré-publicação)

---

## Comparativo

| Critério | Opção 1 (Horizon-Specific) | Opção 2 (Block Conformal) | Opção 3 (Status Quo) |
|---|---|---|---|
| Validade estatística | ✅ Alta | ✅ Alta | ❌ Não garantida |
| Custo de implementação | Médio | Grande | Nulo |
| Compatibilidade atual | Alta | Média | — |
| Interpretabilidade | Alta | Média | Alta (porém enganosa) |

**Recomendação:** Opção 1 — eliminação cirúrgica do `sqrt(k)` com calibração por horizonte e `ε` adaptativo.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Adicionar `coverage_score` como métrica de avaliação dos CIs | @roger | TBD | NOT STARTED |
| Refatorar `calibrar_intervalos_confianca` para receber `horizonte_k` e retornar `dict[int, float]` | @roger | TBD | NOT STARTED |
| Refatorar `aplicar_limites_confianca` para lookup por horizonte | @roger | TBD | NOT STARTED |
| Substituir `epsilon=0.01` fixo por `ε` adaptativo baseado em percentil do conjunto de calibração | @roger | TBD | NOT STARTED |
| Adicionar testes unitários de cobertura empírica (assertar `coverage >= 1-alpha`) | @roger | TBD | NOT STARTED |
| Criar TDD de implementação detalhada (pós-aprovação deste RFC) | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 2: Block Conformal / Rolling Conformal

**Data:** 2026-05-27

**Rationale:** A escolha pela Opção 2, apesar do maior esforço inicial, é justificada pela **prevenção robusta de múltiplos pontos de falha** em um sistema de machine learning crítico. Diferentemente da Opção 1 (patch pontual), o uso de `sklearn.Pipeline` e `ColumnTransformer` estabelece uma barreira arquitetural definitiva contra *schema leakage* e futuros erros de engenharia de features.

O principal driver técnico é a necessidade de **garantia de serialização** — o pipeline formal garante que o mesmo objeto que aprende as transformações em `fold_train` é aquele que as aplica em `fold_val`, eliminando o risco de *data leakage* assintótico. Além disso, a Opção 2:

* **Facilita auditoria e testes:** Cada step do pipeline pode ser testado unitariamente, e a estrutura padrão do sklearn é mais fácil de inspecionar e depurar do que scripts Python ad-hoc.

* **É compatível com outils padrão:** Facilita a integração com ferramentas de automação de ML e reprodutibilidade que esperam objetos Pipeline.

* **Custo-benefício de longo prazo:** Embora o custo de implementação seja maior, o custo de retrabalho e correção de *bias* em pesquisa acadêmica ou aplicações regulatórias (como saúde pública) seria significativamente mais alto caso os problemas de *leakage* persistissem.    

**Follow-up:**
- [ ] Criar TDD de implementação após aprovação
- [ ] Atualizar documentação do módulo `conformal_prediction.py`
- [ ] Executar pipeline completo e comparar cobertura empírica antes/depois
