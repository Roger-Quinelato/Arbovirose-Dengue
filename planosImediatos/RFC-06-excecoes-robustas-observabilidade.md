# RFC-06: Tratamento de Exceções Robusto e Observabilidade Estruturada

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | HIGH — falhas silenciosas injetam dados corrompidos no downstream   |
| **Status**       | NOT STARTED                                                          |
| **Driver**       | @roger-quinelato                                                     |
| **Aprovador**    | @roger-quinelato                                                     |
| **Contribuidores** | —                                                                 |
| **Informados**   | —                                                                    |
| **Prazo**        | TBD                                                                  |
| **Criado em**    | 2026-05-27                                                           |
| **Atualizado**   | 2026-05-27                                                           |

---

## Background

**Estado Atual — Tratamento de Exceções:**
Em [`train_tuning.py`](../src/dengue_pipeline/modeling/train_tuning.py) linhas 348–354:

```python
except Exception as e:
    import traceback
    import warnings
    warnings.warn(f"Conformal prediction falhou: {e}\n{traceback.format_exc()}")
    print(f"  [AVISO] Conformal prediction falhou: {e}. Salvando sem intervalos de confiança.")
    pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
    pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)
```

Capturar `Exception` nua mascara qualquer erro — desde um simples `KeyError` até um `MemoryError`. O pipeline continua com `lower_ci=NaN` e `upper_ci=NaN`, **sem registrar o erro em nenhum sistema de telemetria**.

**Estado Atual — Observabilidade:**
Todo o feedback de progresso usa `print()`:

```python
print(f">>> P1: tuning RF e XGBoost na config {config}...")
print(f"  - {model_name} grid {i}/{len(grid_list)}")
```

`print()` não possui: níveis de severidade, timestamps, correlação de execução (run_id), filtragem ou redirecionamento para sistemas de monitoramento.

**Por que agora:**
Em ambiente de pesquisa sério, qualquer execução deve ser **rastreável e auditável**. Se o conformal prediction falhar silenciosamente, o pesquisador não saberá que os intervalos publicados são `NaN` disfarçados. Em ambientes de produção/cloud, `print()` não aparece em logs estruturados.

**Consequência de não agir:**
- Erros numéricos (overflow, singularidade de matriz) são engolidos e propagam dados inválidos
- Execuções em cloud/container não rastreáveis
- Impossível correlacionar logs com um `run_id` específico

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | O módulo `logging` da stdlib é suficiente (sem APM externo) | Alto | Requisito de integração com Datadog/CloudWatch surgir |
| 2 | Erros de Conformal Prediction devem interromper o pipeline (Fail-Fast), não ser ignorados | Médio | Equipe decidir que CI parcial é aceitável |
| 3 | O `run_id` existente em `__main__.py` pode ser propagado aos loggers | Alto | Logging em módulos chamados antes do run_id ser criado |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Erros arquiteturais (bugs de código) NÃO podem ser silenciados | Must-have |
| 2 | Erros recuperáveis devem ser logados com contexto suficiente para diagnóstico | Must-have |
| 3 | Logs devem incluir run_id para correlação entre execuções | Alto |
| 4 | Compatibilidade futura com logging JSON estruturado para cloud | Alto |
| 5 | Sem dependências externas (stdlib apenas) | Médio |

---

## Dados Relevantes

- **Exceção crítica:** `train_tuning.py:348` — `except Exception` engole qualquer falha do conformal
- **Print count:** grep em `src/` retornou 0 ocorrências de `logging` e múltiplas de `print()`
- **run_id:** já gerado em `__main__.py:42` — `run_id = datetime.now().strftime("%Y%m%d_%H%M")`

---

## Opções Consideradas

### Opção 1: logging estruturado + exceções específicas ⭐ (Recomendada)

**Descrição:**
Adicionar `logging.getLogger(__name__)` e restringir o `except` do conformal para exceções numéricas específicas. Erros arquiteturais (não esperados) propagam normalmente (Fail-Fast).

```python
# Em cada módulo:
import logging
logger = logging.getLogger(__name__)

# Substituir print:
logger.info(">>> P1: tuning RF e XGBoost na config %s...", config)
logger.info("  - %s grid %d/%d", model_name, i, len(grid_list))

# Substituir except Exception:
except (ValueError, FloatingPointError, np.linalg.LinAlgError) as e:
    logger.warning("Conformal prediction falhou com erro numérico: %s", e, exc_info=True)
    pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
    pred_closed_ci = pred_closed.assign(lower_ci=np.nan, upper_ci=np.nan)
# Erros inesperados (ImportError, MemoryError etc.) propagam — Fail-Fast
```

Configurar logging no `__main__.py`:
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | run_id=%(run_id)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
```

**Prós:**
- Erros arquiteturais propagam (Fail-Fast) — pipeline não continua com dados inválidos
- Logs com timestamp, módulo e severidade
- Compatível com redirecionamento para arquivo ou sistema externo
- Sem dependências externas

**Contras:**
- Requer substituição de todos os `print()` em 4+ módulos
- Propagação do `run_id` para o contexto de logging requer `LoggerAdapter` ou campo extra

**Custo estimado:** MÉDIO — ~3–4 horas

---

### Opção 2: Logging mínimo + manter except amplo com re-raise

**Descrição:**
Manter `except Exception` mas adicionar `raise` condicional para erros críticos:

```python
except Exception as e:
    logger.error("Conformal falhou: %s", e, exc_info=True)
    if isinstance(e, (MemoryError, SystemError)):
        raise  # Fail-Fast para erros de sistema
    pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
```

**Prós:**
- Menor mudança de código
- Logging imediato

**Contras:**
- Ainda captura erros arquiteturais como `KeyError`, `AttributeError` silenciosamente
- Lista de exceções "críticas" é mantida manualmente e se torna stale

**Custo estimado:** PEQUENO — ~1 hora (mas incompleto)

---

### Opção 3: Do Nothing

**Prós:** Sem custo imediato.

**Contras:**
- Erros numéricos injetam NaN silenciosamente em resultados publicados
- Execuções em cloud sem rastreabilidade
- Impossível auditar execuções passadas

**Custo estimado:** NULO agora / ALTO no futuro (debug de execução silenciosa corrompida)

---

## Comparativo

| Critério | Opção 1 (logging + fail-fast) | Opção 2 (mínimo) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Fail-fast em erros arquiteturais | ✅ | Parcial | ❌ |
| Rastreabilidade de execuções | ✅ | ✅ | ❌ |
| Custo | Médio | Pequeno | Nulo |
| Compatibilidade cloud | ✅ | ✅ | ❌ |

**Recomendação:** Opção 1 — a única que garante Fail-Fast de forma estruturada.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Configurar `basicConfig` no `__main__.py` com formato incluindo timestamp e run_id | @roger | TBD | NOT STARTED |
| Adicionar `logger.info/warning/error` em `train_tuning.py` | @roger | TBD | NOT STARTED |
| Adicionar `logger.info/warning/error` em `evaluation.py` | @roger | TBD | NOT STARTED |
| Restringir `except Exception` para `except (ValueError, FloatingPointError, np.linalg.LinAlgError)` | @roger | TBD | NOT STARTED |
| Adicionar log de entrada/saída das funções críticas com duração (timing) | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 1: logging estruturado + exceções específicas

**Data:** 2026-05-27
    
**Rationale:** A Opção 1 é a única que alinha o pipeline com práticas científicas sérias: erros arquiteturais propagam (Fail-Fast), erros recuperáveis são logados com contexto e execuções são rastreáveis via `run_id`. As outras opções deixariam o pipeline vulnerável a falhas silenciosas ou limitariam a auditabilidade.

**Follow-up:**
- [ ] Decidir se logs devem ser persistidos em arquivo por `run_id`
- [ ] Avaliar `structlog` para JSON logging se integração com cloud for planejada
