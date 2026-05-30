# TDD-06: Tratamento de Exceções Robusto e Observabilidade Estruturada

| Campo           | Valor                        |
| --------------- | ---------------------------- |
| Tech Lead       | @roger-quinelato             |
| Team            | @roger-quinelato             |
| Epic/Ticket     | RFC-06                       |
| Status          | Approved                     |
| Created         | 2026-05-27                   |
| Last Updated    | 2026-05-27                   |

## Contexto

Atualmente, o pipeline epidemiológico de modelagem em `dengue_pipeline` utiliza uma abordagem simplificada para telemetria (`print()`) e captura de erros de forma demasiadamente genérica (`except Exception`). Isso impacta a auditabilidade e confiabilidade do modelo para ambientes de pesquisa ou produção, onde execuções em nuvem e documentação de incertezas precisam ser exatas.

## Definição do Problema & Motivação

### Problemas que estamos resolvendo

- **Falhas silenciosas**: O uso de `except Exception` em seções críticas (como no Conformal Prediction em `train_tuning.py`) captura indiscriminadamente qualquer falha (desde erros numéricos esperados até erros arquiteturais graves como `KeyError` ou `MemoryError`). Isso resulta na injeção silenciosa de `NaN`s nas métricas de saída.
- **Falta de rastreabilidade (Observabilidade)**: Mensagens geradas via `print()` não possuem metadados de severidade, *timestamps* ou correlação de execução (`run_id`). Em ambientes não-interativos (cloud, containers), torna-se impossível correlacionar logs com execuções específicas.

### Por que agora?

Com as modificações estruturais recentes (RFC-01 a RFC-05) moldando o código para um padrão de qualidade de Doutorado e pesquisa reprodutível, os *silent failures* prejudicam a integridade metodológica. Garantir que a falha de um modelo "quebre rapidamente" (Fail-Fast) em caso de bug de código é uma premissa básica para validação científica.

### Impacto de NÃO resolver

- **Business/Pesquisa**: Divulgação de dados ou predições corrompidas com limites de incerteza mascarados.
- **Técnico**: Debug de execução silenciosa corrompida, dificuldade para auditar execuções passadas, e ocultamento de bugs arquiteturais graves sob a camuflagem de erros numéricos.

## Escopo

### ✅ No Escopo (V1 - MVP)
- Configuração centralizada de logs no ponto de entrada (`__main__.py`).
- Propagação do `run_id` para todos os logs via customização do logger (formatadores).
- Substituição de chamadas `print()` pelo módulo de `logging` padrão do Python (`logger.info`, `logger.warning`, etc.) em módulos principais (`train_tuning.py`, `evaluation.py`).
- Estreitamento do `except Exception` para capturar apenas exceções numéricas esperadas no cálculo do Conformal Prediction.
- Adição de logs de entrada/saída (timing) para funções críticas.

### ❌ Fora do Escopo (V1)
- Integração com sistemas externos de APM (Datadog, AWS CloudWatch, etc.).
- Persistência estruturada JSON complexa (`structlog` ou similar) nesta primeira versão (podendo ser adicionado no futuro).
- Banco de dados para salvar status e logs da execução.

## Solução Técnica

### Visão Geral da Arquitetura

O módulo nativo `logging` do Python será introduzido como o framework central de telemetria. 
Um logger configurado no `__main__.py` padronizará o output. Instâncias nomeadas `logging.getLogger(__name__)` serão utilizadas em cada arquivo. Para correlacionar eventos a uma execução unificada, usaremos a injeção do `run_id` via formato do log.

### Estrutura e Formatação dos Logs

**Configuração Base em `__main__.py`**:
```python
import logging

def setup_logging(run_id: str):
    log_format = f"%(asctime)s | %(name)s | %(levelname)s | run_id={run_id} | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            # Futuro: logging.FileHandler(...) integrado ao config.py (RFC-05)
        ]
    )
```

**Uso nos Módulos** (`train_tuning.py`):
```python
import logging
logger = logging.getLogger(__name__)

# Antes: print(f">>> P1: tuning RF e XGBoost...")
logger.info(">>> P1: tuning RF e XGBoost na config %s...", config)
```

### Refatoração de Exceções (Fail-Fast)

Em vez de mascarar erros, o código irá propagar explicitamente falhas sistêmicas e capturar apenas erros matemáticos de matrizes ou operações numéricas na parte preditiva.

**Código Refatorado em `train_tuning.py`**:
```python
try:
    # Lógica de Conformal Prediction usando MAPIE (RFC-01/02)
    ...
except (ValueError, FloatingPointError, np.linalg.LinAlgError) as e:
    logger.warning("Conformal prediction falhou com erro numérico esperado: %s", e, exc_info=True)
    # Continua apenas para falhas estritamente algorítmicas de regressão
    pred_now_ci = pred_now.assign(lower_ci=np.nan, upper_ci=np.nan)
# Ausência do "except Exception" nu permite que KeyError, TypeError, etc., quebrem o pipeline.
```

## Riscos

| Risco | Impacto | Probabilidade | Mitigação |
|------|--------|-------------|------------|
| Falhas no pipeline devido à nova política Fail-Fast | Alto | Média | Executar baterias completas de teste local (dry-run) verificando logs, corrigindo bugs latentes expostos pela mudança. |
| Perda de formatação visual atrativa no console | Baixo | Média | Manter mensagens de log limpas; uso futuro de bibliotecas ricas (ex: `rich`) pode cobrir isso. |
| Logs de dependências externas ruidosos | Baixo | Alta | Ajustar seletivamente o nível de log para bibliotecas barulhentas (ex: `logging.getLogger("mapie").setLevel(logging.WARNING)`). |

## Plano de Implementação

| Fase | Tarefa | Descrição | Responsável | Status |
| ------------------- | ----------------- | -------------------------------------- | ------- | ------ |
| **Fase 1 - Config** | `setup_logging`   | Criar a configuração base no `__main__.py` e testar saída com o `run_id`. | @roger | TODO |
| **Fase 2 - Fail-Fast** | Modificar `except` | Trocar `except Exception` genérico pela tupla de erros numéricos e adicionar `logger.warning`. | @roger | TODO |
| **Fase 3 - Telemetria** | Remoção de `print` | Varrer o código `src/` substituindo por `logger.info`, `logger.debug`. | @roger | TODO |
| **Fase 4 - Timing** | Logs de Profiling | Adicionar anotações de tempo para avaliar gargalos computacionais. | @roger | TODO |
| **Fase 5 - Validação** | Teste E2E | Rodar o pipeline completo em modo teste para garantir estabilidade e conferir rastreabilidade. | @roger | TODO |

## Estratégia de Testes

- **Testes Unitários**:
  - Simular um erro numérico previsível no fluxo do conformal (`FloatingPointError`) e checar se `lower_ci` é assinalado com `NaN` e um log emitido.
  - Simular um erro inesperado (`MemoryError`, `AttributeError`) e confirmar que o erro levanta exceção de quebra em vez de ser silenciado.
- **Integração / E2E**:
  - Validar no output padrão (`stdout`) se o `run_id` é consistentemente afixado em todas as etapas da regressão.

## Monitoramento e Observabilidade

- **Métricas Chave**: Formato estruturado assegura Severidade (INFO, WARNING, ERROR), Timestamp UTC e `run_id`.
- **Rastreabilidade**: Casos de `ERROR` ou falha devem incluir *stack trace* através do uso de `exc_info=True`.

## Plano de Rollback

Em caso de quebra sistêmica crítica durante experimentação:
1. Reverter o commit correspondente a esta tarefa (fallback).
2. Se necessário testar pontualmente sem a quebra (ex: prazo iminente de apresentação), reimplementar o `except Exception` temporariamente apenas no bloco onde a falha está concentrada, isolando-a com log nível `ERROR`.
