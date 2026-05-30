# RFC-04: Contratos de Interface via Dataclasses (Substituição de Tuplas Massivas)

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | MEDIUM — afeta manutenibilidade, type-safety e rastreabilidade      |
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

**Estado Atual:**
Funções centrais do pipeline retornam tuplas posicionais não tipadas:

```python
# train_tuning.py — linha 126
return modelo, pred_df, metricas, ra_metricas, features
# → chamado como: model, pred_df, metrics, _, _ = executar_ajuste_previsao(...)
# → chamado como: model, pred_df, metrics, _, features = executar_ajuste_previsao(...)
```

Em [`evaluation.py`](../src/dengue_pipeline/modeling/evaluation.py) linha 138:
```python
model, pred_df, metrics, ra_metrics, features = executar_ajuste_previsao(df, config, model_name)
```

**Problema:**
1. **Quebra silenciosa:** Se a ordem da tupla mudar, todas as chamadas falham em runtime — não há erro em tempo de análise estática
2. **`_` como descarte:** O uso de `_` para ignorar elementos da tupla oculta o que está sendo descartado, dificultando código review
3. **Rastreio impossível:** IDEs e ferramentas de type checking (mypy, pyright) não conseguem inferir o tipo de cada elemento da tupla posicional
4. **Escala mal:** A tupla `(modelo, pred_df, metricas, ra_metricas, features)` tem 5 elementos — qualquer adição requer atualizar todos os sites de chamada manualmente

**Por que agora:**
O pipeline está em fase de consolidação. Este é o momento mais barato para introduzir contratos explícitos, antes que mais chamadas dependam da tupla atual.

**Consequência de não agir:**
- Qualquer refatoração de `executar_ajuste_previsao` tem alto risco de introduzir bugs silenciosos
- mypy/pyright não podem ser ativados de forma útil sobre este módulo

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | Python ≥ 3.10 disponível no ambiente (suporta `dataclasses` com `frozen=True` e `list[str]`) | Alto | Ambiente usar Python 3.8 ou anterior |
| 2 | Todos os sites de chamada de `executar_ajuste_previsao` podem ser atualizados | Alto | Dependências externas ao repositório usarem a função diretamente |
| 3 | `frozen=True` é preferível (imutabilidade pós-construção) | Médio | Performance crítica exigir mutabilidade |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Quebras de interface detectadas em tempo de análise (não runtime) | Must-have |
| 2 | Retrocompatibilidade com sites de chamada existentes | Alto |
| 3 | Legibilidade e autodocumentação do contrato | Alto |
| 4 | Overhead mínimo (sem bibliotecas externas) | Médio |

---

## Dados Relevantes

- **Funções afetadas:** `executar_ajuste_previsao` (train_tuning.py:84), `cv_score_parametros` (retorna `float` — OK), `executar_estudo_ablacao` (evaluation.py:109 — retorna `tuple[pd.DataFrame, dict]`)
- **Sites de chamada:** pelo menos 4 locais distintos no repositório consumem `executar_ajuste_previsao`
- **Alternativas Python nativas:** `dataclass`, `TypedDict`, `NamedTuple`

---

## Opções Consideradas

### Opção 1: `@dataclass(frozen=True)` ⭐ (Recomendada)

**Descrição:**
Criar dataclasses tipadas e imutáveis para os tipos de retorno de funções chave.

```python
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class TuningResult:
    model: object
    predictions: pd.DataFrame
    metrics: dict
    ra_metrics: pd.DataFrame
    features: list[str]

# Uso:
result = executar_ajuste_previsao(df, config, nome_modelo)
print(result.metrics["rmse_df"])      # acesso por nome, não por posição
print(result.predictions.head())
```

**Prós:**
- Acesso por nome (`.predictions`, `.metrics`) — legível e refactor-safe
- `frozen=True` previne modificação acidental pós-construção
- Type hints completos para mypy/pyright
- Sem dependências externas — stdlib pura

**Contras:**
- Breaking change: todos os sites de chamada precisam ser atualizados de tupla para atributos
- `pd.DataFrame` não é hashable — `frozen=True` com DataFrame requer cuidado (não pode usar o dataclass em sets/dict keys, mas funciona normalmente como objeto)

**Custo estimado:** PEQUENO — ~4 horas de refatoração + atualização de sites de chamada

---

### Opção 2: `NamedTuple`

**Descrição:**
```python
from typing import NamedTuple
class TuningResult(NamedTuple):
    model: object
    predictions: pd.DataFrame
    metrics: dict
    ra_metrics: pd.DataFrame
    features: list[str]
```

**Prós:**
- Compatível com desempacotamento por posição existente: `model, pred, metrics, ra, feat = result`
- Retrocompatibilidade total sem mudar sites de chamada
- Type hints disponíveis

**Contras:**
- Acesso por posição ainda possível — não elimina a fragilidade posicional
- Imutável, mas sem `frozen=True` semântico explícito
- Menos expressivo que `dataclass` para adição futura de métodos

**Custo estimado:** MUITO PEQUENO — ~1 hora (retrocompatível)

---

### Opção 3: Do Nothing

**Prós:** Nenhum custo imediato. O código funciona.

**Contras:**
- Dívida técnica acumulada
- Qualquer mudança na tupla é uma bomba silenciosa
- mypy/pyright inutilizáveis sobre estes módulos

**Custo estimado:** NULO agora / MÉDIO no futuro

---

## Comparativo

| Critério | Opção 1 (dataclass) | Opção 2 (NamedTuple) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Type safety completa | ✅ | ✅ | ❌ |
| Retrocompatibilidade | ❌ (breaking) | ✅ | ✅ |
| Elimina fragilidade posicional | ✅ | Parcial | ❌ |
| Extensibilidade futura | Alta | Média | Baixa |

**Recomendação:** Opção 1 (`dataclass`) como objetivo final; Opção 2 (`NamedTuple`) como stepping stone de curto prazo se retrocompatibilidade for prioridade.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Criar `src/dengue_pipeline/modeling/types.py` com `TuningResult` e `AblationResult` | @roger | TBD | NOT STARTED |
| Refatorar `executar_ajuste_previsao` para retornar `TuningResult` | @roger | TBD | NOT STARTED |
| Atualizar todos os sites de chamada (4+ locais) | @roger | TBD | NOT STARTED |
| Ativar `mypy` sobre o módulo `modeling` e corrigir erros de tipo | @roger | TBD | NOT STARTED |
| Adicionar `py.typed` ao pacote para indicar suporte a type checking | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 2: `NamedTuple` ⭐   

**Data:** 2026-05-27

**Rationale:** A escolha pela Opção 2 é justificada pela necessidade de **minimizar o esforço de refatoração**, ao mesmo tempo que se **melhora a type safety e a legibilidade** do código.

Embora a Opção 1 (`dataclass`) ofereça uma solução tecnicamente mais robusta e expressiva, ela exigiria a atualização de todos os sites de chamada, introduzindo um risco maior de bugs silenciosos durante a transição. A Opção 2, por outro lado:

* **Mantém a compatibilidade total** com o código existente, permitindo desempacotamento por posição
* **Adiciona type hints completos** e documentação explícita
* **Reduz o custo de implementação** para cerca de 1 hora, sem impactar a performance

**Follow-up:**
- [ ] Configurar mypy no `pyproject.toml` após refatoração
- [ ] Adicionar verificação de tipos ao CI/CD se existir
