# RFC-10: Monitoramento de Drift para Manutenção da Validade do Modelo

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | HIGH — modelos sem drift monitoring envelhecem silenciosamente      |
| **Status**       | NOT STARTED                                                          |
| **Driver**       | @roger-quinelato                                                     |
| **Aprovador**    | @roger-quinelato                                                     |
| **Contribuidores** | Orientador (se aplicável)                                        |
| **Informados**   | Equipe de vigilância (se aplicável)                                 |
| **Prazo**        | TBD (antes de deploy operacional do modelo)                         |
| **Criado em**    | 2026-05-27                                                           |
| **Atualizado**   | 2026-05-27                                                           |

---

## Background

**Estado Atual:**
O pipeline não possui nenhum mecanismo de monitoramento de drift. Após o treinamento, o modelo é serializado e usado operacionalmente sem qualquer verificação de que a distribuição dos dados de entrada permanece compatível com a distribuição de treino.

**Problema:**
Arboviroses como dengue são sistemas dinâmicos sujeitos a múltiplas formas de drift:

1. **Drift climático:** Variações interanuais de temperatura, precipitação e umidade — as features climáticas centrais do modelo
2. **Drift vetorial:** Mudanças na densidade e distribuição de *Aedes aegypti* por sazonalidade, campanhas de controle ou resistência a inseticidas
3. **Drift de notificação:** Mudanças nos sistemas de vigilância epidemiológica (SINAN), sub-notificação variável, surtos que sobrecarregam o sistema
4. **Drift populacional:** Migração, crescimento e redistribuição da população pelo DF entre as RAs

**Consequências:**
- O Conformal Prediction (RFC-01) perde validade marginal quando a distribuição muda: o conjunto de calibração deixa de ser exchangeable com os dados novos
- Métricas de performance podem degradar gradualmente sem alarme
- O modelo pode ser usado operacionalmente com performance real muito inferior à reportada no treino

**Por que agora:**
O pipeline está migrando para operação contínua (via `run_id` versionado). Este é o momento de planejar monitoramento antes que o modelo comece a ser usado para tomada de decisão em vigilância.

**Consequência de não agir:**
- Modelo envelhecendo silenciosamente em produção
- Cobertura do Conformal degradando sem alerta
- Incapacidade de detectar quando retreinamento é necessário

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | Dados históricos suficientes estão disponíveis para construir distribuições de referência (PSI/KS) | Alto | Histórico < 2 anos por RA |
| 2 | O pipeline pode ser rodado em modo de "monitoramento" sem retreinamento completo | Médio | Infraestrutura não suportar execuções automáticas |
| 3 | Um limiar de alerta (ex: PSI > 0.2) pode ser definido a priori | Médio | Comportamento epidemiológico normal já produz PSI > 0.2 sazonalmente |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Detectar degradação de cobertura do Conformal (coverage drift) | Must-have |
| 2. | Detectar drift nas features de entrada (PSI ou KS) | Alto |
| 3 | Alertar quando retreinamento for necessário | Alto |
| 4 | Custo computacional aceitável para execução semanal | Médio |
| 5 | Sem infraestrutura externa (sem Evidently AI ou Great Expectations por ora) | Médio |

---

## Dados Relevantes

- **Drift sources:** clima (3 variáveis), casos (lags), população (anual), notificação (variável)
- **Drift detection sem infra externa:** PSI (Population Stability Index) e KS test são implementáveis com `scipy.stats` e `numpy`
- **Conformal coverage drift:** calculável com RFC-08 (coverage metric) em janela rolling
- **Referências:**
  - PSI: usado em credit scoring para detectar covariate shift — adaptável a series temporais
  - Gama et al. (2014) — "A Survey on Concept Drift Adaptation"

---

## Opções Consideradas

### Opção 1: Monitor de Drift mínimo com PSI + Coverage Rolling ⭐ (Recomendada)

**Descrição:**
Adicionar um módulo `monitoring.py` com duas verificações:

1. **PSI por feature:** Comparar distribuição das features de entrada nas últimas N semanas vs. distribuição de treino. Alertar se PSI > 0.2 (limiar convencional para drift moderado).

2. **Coverage rolling:** Calcular cobertura empírica dos intervalos de confiança em janela de 12 semanas. Alertar se coverage < (1-alpha - margem) = < 85% para alpha=0.10.

```python
# monitoring.py
def calcular_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index entre distribuição de referência e atual."""
    breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    expected_pct = np.histogram(expected, breakpoints)[0] / len(expected) + 1e-8
    actual_pct   = np.histogram(actual,   breakpoints)[0] / len(actual)   + 1e-8
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))

def verificar_drift_features(df_treino: pd.DataFrame, df_novo: pd.DataFrame,
                              features: list[str]) -> dict[str, float]:
    """Retorna PSI por feature. PSI > 0.2 indica drift moderado/severo."""
    return {f: calcular_psi(df_treino[f].dropna(), df_novo[f].dropna())
            for f in features if f in df_treino.columns}

def verificar_coverage_rolling(pred_df: pd.DataFrame, window_weeks: int = 12) -> float:
    """Cobertura empírica nas últimas `window_weeks` semanas."""
    recent = pred_df.sort_values("epi_sunday").tail(window_weeks * 30)  # ~30 RAs
    return calcular_cobertura_intervalo(recent)  # da RFC-08
```

Executado ao final de cada `run_id` e os resultados adicionados ao relatório.

**Prós:**
- PSI: padrão da indústria, implementável com numpy
- Coverage rolling: diretamente validável contra o alpha do Conformal
- Sem dependências externas
- Integração natural com o `run_id` existente

**Contras:**
- PSI é sensível à discretização (número de buckets)
- Não distingue drift sazonal (esperado) de drift real (problemático)
- Sem recalibração automática — apenas alerta

**Custo estimado:** MÉDIO — ~3–4 dias (implementação + integração ao pipeline)

---

### Opção 2: KS Test por feature

**Descrição:**
Usar `scipy.stats.ks_2samp` para detectar diferença de distribuição entre treino e dados recentes.

**Prós:**
- Teste estatístico formal com p-valor
- Mais robusto que PSI para distribuições com caudas longas

**Contras:**
- p-valor sensível a tamanho amostral — com muitos dados, detecta diferenças sem importância prática
- Sem magnitude de drift (PSI dá magnitude, KS apenas aceita/rejeita)

**Custo estimado:** PEQUENO — ~1 dia

---

### Opção 3: Do Nothing

**Prós:** Sem custo imediato.

**Contras:**
- Modelo envelhecendo sem alerta
- Cobertura do Conformal degradando silenciosamente
- Impossível saber quando retreinar

**Custo estimado:** NULO agora / ALTO no futuro (decisões de vigilância baseadas em modelo degradado)

---

## Comparativo

| Critério | Opção 1 (PSI + Coverage) | Opção 2 (KS Test) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Detecta covariate shift | ✅ | ✅ | ❌ |
| Detecta coverage drift | ✅ | ❌ | ❌ |
| Magnitude do drift | ✅ (PSI) | ❌ | — |
| Custo | Médio | Pequeno | Nulo |
| Cobertura do problema | Alta | Parcial | — |

**Recomendação:** Opção 1 — única que monitora tanto features quanto calibração dos intervalos.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Criar `src/dengue_pipeline/monitoring.py` com `calcular_psi` e `verificar_drift_features` | @roger | TBD | NOT STARTED |
| Implementar `verificar_coverage_rolling` usando `calcular_cobertura_intervalo` (RFC-08) | @roger | TBD | NOT STARTED |
| Integrar verificação de drift ao final de cada execução em `__main__.py` | @roger | TBD | NOT STARTED |
| Salvar relatório de drift em `run_dir/drift_report.json` | @roger | TBD | NOT STARTED |
| Definir limiares de alerta (PSI > 0.2, coverage < 85%) e documentar | @roger | TBD | NOT STARTED |
| Avaliar se alerta deve bloquear execução ou apenas emitir warning | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** _A preencher após deliberação_

**Data:** _A preencher_

**Rationale:** _A preencher_

**Follow-up:**
- [ ] Definir política de retreinamento automático vs. manual ao detectar drift
- [ ] Avaliar Evidently AI ou Great Expectations se pipeline migrar para produção cloud
- [ ] Integrar alertas de drift com sistema de notificação (email, Slack) se disponível
