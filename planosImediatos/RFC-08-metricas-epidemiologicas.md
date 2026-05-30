# RFC-08: Expansão do Suite de Métricas Epidemiológicas

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | HIGH — modelo com RMSE ótimo pode falhar completamente em surtos    |
| **Status**       | NOT STARTED                                                          |
| **Driver**       | @roger-quinelato                                                     |
| **Aprovador**    | @roger-quinelato                                                     |
| **Contribuidores** | Orientador epidemiológico (se aplicável)                         |
| **Informados**   | —                                                                    |
| **Prazo**        | TBD                                                                  |
| **Criado em**    | 2026-05-27                                                           |
| **Atualizado**   | 2026-05-27                                                           |

---

## Background

**Estado Atual:**
O módulo [`evaluation.py`](../src/dengue_pipeline/modeling/evaluation.py) calcula as seguintes métricas:

```python
metrics = {
    "r2_df": ...,
    "mae_df": ...,
    "rmse_df": ...,
    "mape_df": ...,
    "smape_df": ...,
    "hit_rate_picos": ...,  # % picos reais detectados (P75)
}
```

**Problema:**
Apesar de o conjunto atual ser acima da média, faltam métricas essenciais para forecasting probabilístico e detecção de surtos epidemiológicos:

1. **Interval Coverage:** Não há cálculo de cobertura empírica dos intervalos de confiança (% observações dentro de [lower_ci, upper_ci]). Sem isso, é impossível validar o Conformal Prediction.
2. **WIS (Weighted Interval Score):** Métrica padrão da comunidade de forecasting epidemiológico (FluSight, CDC Forecast Hub). Penaliza tanto imprecisão pontual quanto má calibração de intervalos.
3. **Pinball Loss:** Permite avaliar calibração em diferentes quantis, não apenas no ponto central.
4. **Calibration Error:** Compara a cobertura declarada (90%) com a cobertura real para detectar over/undercoverage.
5. **Sensitivity de Pico:** O `hit_rate_picos` atual usa P75 — um limiar relativamente baixo. Faltam métricas como antecipação de pico (lead time) e erro de magnitude de pico.

**Por que agora:**
O pipeline já gera intervalos de confiança via Conformal Prediction, mas não os avalia. Isso significa que o RFC-01 (reforma do CP) não pode ser verificado sem esta suite de métricas.

**Consequência de não agir:**
- Intervalos de confiança gerados sem validação de cobertura
- Impossível comparar com benchmarks da literatura (WIS é o padrão do CDC Forecast Hub)
- Métricas de pico insuficientes para aplicação em vigilância epidemiológica

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | Os DataFrames de predição já contêm `lower_ci` e `upper_ci` quando disponíveis | Alto | Conformal falhar silenciosamente (mas RFC-06 trata isso) |
| 2 | WIS pode ser computado com os quantis disponíveis (intervalo único de 90%) | must-have | Literatura exigir múltiplos quantis (11 ou 23 quantis do Forecast Hub) |
| 3 | O threshold de pico pode ser configurável (não fixo em P75) | Alto | Definição epidemiológica de surto exigir critério diferente |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Cobertura empírica dos intervalos de confiança mensurável | Must-have |
| 2 | Compatibilidade com métricas do CDC Forecast Hub (WIS) | Alto |
| 3 | Métricas de pico epidêmico com threshold configurável | Alto |
| 4 | Sem dependências externas pesadas (numpy/scipy suficiente) | Médio |

---

## Dados Relevantes

- **Arquivo afetado:** [`evaluation.py`](../src/dengue_pipeline/modeling/evaluation.py) — função `consolidar_metricas_performance`
- **Métricas atuais:** R², MAE, RMSE, MAPE, sMAPE, hit_rate_picos
- **Métricas ausentes:** coverage, WIS, pinball loss, calibration error, peak lead time
- **Referência:** CDC Forecast Hub usa WIS como métrica primária para comparar modelos de forecasting epidemiológico

---

## Opções Consideradas

### Opção 1: Adicionar métricas probabilísticas e de pico ao `evaluation.py` ⭐ (Recomendada)

**Descrição:**
Expandir `consolidar_metricas_performance` com um conjunto de métricas adicionais calculadas quando `lower_ci` e `upper_ci` estiverem disponíveis.

```python
# Interval Coverage
def calcular_cobertura_intervalo(pred_df: pd.DataFrame, alpha: float = 0.10) -> float:
    """Proporção de observações dentro do intervalo de confiança declarado."""
    if "lower_ci" not in pred_df or pred_df["lower_ci"].isna().all():
        return float("nan")
    dentro = (pred_df["cases"] >= pred_df["lower_ci"]) & (pred_df["cases"] <= pred_df["upper_ci"])
    return float(dentro.mean())

# Weighted Interval Score (simplificado — 1 intervalo)
def calcular_wis(pred_df: pd.DataFrame, alpha: float = 0.10) -> float:
    """WIS para 1 intervalo de (1-alpha)% + penalidade de dispersão."""
    if pred_df["lower_ci"].isna().all():
        return float("nan")
    spread = pred_df["upper_ci"] - pred_df["lower_ci"]
    undershoot = 2/alpha * (pred_df["lower_ci"] - pred_df["cases"]).clip(lower=0)
    overshoot  = 2/alpha * (pred_df["cases"] - pred_df["upper_ci"]).clip(lower=0)
    return float((spread + undershoot + overshoot).mean())

# Calibration Error
def calcular_calibration_error(coverage_real: float, alpha: float = 0.10) -> float:
    """Diferença entre cobertura declarada e cobertura real."""
    return abs(coverage_real - (1 - alpha))
```

**Prós:**
- Cobertura: valida o RFC-01 (Conformal Prediction)
- WIS: padrão do CDC Forecast Hub — permite comparação com literatura
- Implementável com numpy/pandas puro
- Backward compatible — métricas novas são adicionais, não substituem as atuais

**Contras:**
- WIS completo exige múltiplos quantis (0.01, 0.025, ..., 0.975, 0.99) — versão simplificada tem limitações
- Aumenta o tamanho do CSV de resultados

**Custo estimado:** MÉDIO — ~3–4 horas

---

### Opção 2: Integrar biblioteca `pyforecast`

**Descrição:**
Usar biblioteca externa especializada em scoring rules probabilísticas.

**Prós:**
- CRPS, WIS multi-quantil, pinball loss prontos
- Implementações validadas e testadas

**Contras:**
- Dependência externa adicional
- `properscoring` tem desenvolvimento parado desde 2015
- Overhead para adicionar à `requirements.txt`

**Custo estimado:** PEQUENO — ~1 hora (mas adiciona dependência)

---

### Opção 3: Do Nothing

**Prós:** Sem custo imediato.

**Contras:**
- Intervalos de confiança gerados sem validação
- Impossível comparar com benchmarks da literatura
- RFC-01 não pode ser verificado sem coverage metric

**Custo estimado:** NULO agora / ALTO no futuro

---

## Comparativo

| Critério | Opção 1 (numpy puro) | Opção 2 (biblioteca) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Coverage empírica | ✅ | ✅ | ❌ |
| WIS compatível com CDC | Simplificado | ✅ completo | ❌ |
| Sem dependência externa | ✅ | ❌ | ✅ |
| Custo | Médio | Pequeno | Nulo |

**Recomendação:** Opção 1 em curto prazo; Opção 2 se o pipeline evoluir para múltiplos quantis.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Implementar `calcular_cobertura_intervalo` em `evaluation.py` | @roger | TBD | NOT STARTED |
| Implementar `calcular_wis` (versão 1-intervalo) em `evaluation.py` | @roger | TBD | NOT STARTED |
| Implementar `calcular_calibration_error` em `evaluation.py` | @roger | TBD | NOT STARTED |
| Adicionar threshold configurável ao `hit_rate_picos` (não fixo em P75) | @roger | TBD | NOT STARTED |
| Atualizar CSVs de resultados para incluir novas colunas | @roger | TBD | NOT STARTED |
| Adicionar gráfico de calibration plot (observed vs expected coverage) | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 1: Adicionar métricas probabilísticas e de pico ao `evaluation.py`   

**Data:** 27/05/2026

**Rationale:** Opção 1 é a única que garante reprodutibilidade global, rastreabilidade por run_id e configurabilidade externa, alinhando o pipeline com padrões científicos. As outras opções deixariam falhas de reprodutibilidade difíceis de detectar ou resultariam em sous-ótimos incompletos.

**Follow-up:**
- [ ] Validar cobertura empírica após RFC-01 (reforma do CP)
- [ ] Avaliar adoção do WIS completo (23 quantis) para publicação
