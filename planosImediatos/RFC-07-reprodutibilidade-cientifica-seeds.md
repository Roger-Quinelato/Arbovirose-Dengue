# RFC-07: Reprodutibilidade Científica via Controle Centralizado de Seeds

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | HIGH — resultados irreproduzíveis invalidam auditoria científica    |
| **Status**       | NOT STARTED                                                          |
| **Driver**       | @roger-quinelato                                                     |
| **Aprovador**    | @roger-quinelato                                                     |
| **Contribuidores** | Orientador/Banca (se aplicável)                                  |
| **Informados**   | —                                                                    |
| **Prazo**        | Antes de qualquer submissão de resultados                           |
| **Criado em**    | 2026-05-27                                                           |
| **Atualizado**   | 2026-05-27                                                           |

---

## Background

**Estado Atual:**
O pipeline controla aleatoriedade apenas parcialmente via `random_state=42` nos modelos:

```python
# train_tuning.py — linha 47
defaults = {"n_estimators": 150, "max_depth": 15, "random_state": 42, "n_jobs": -1}  # RF

# train_tuning.py — linha 55
defaults = {"n_estimators": 200, "random_state": 42, ...}  # XGB
```

**Não há controle de:**
- `numpy.random.seed()` — afeta amostragem em splits e operações NumPy
- `random.seed()` (stdlib Python) — afeta seleção aleatória em Python puro
- Seeds de paralelismo (`n_jobs=-1` em RF e XGB usam threads/processos com estado interno)
- Variáveis de ambiente do BLAS/OpenMP (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`)
- Nenhuma função `seed_everything` centralizada existe no codebase

**Por que agora:**
Em pesquisa científica, a reprodutibilidade de resultados numéricos é um requisito mínimo para publicação e defesa de doutorado. Se métricas variam entre execuções, não é possível afirmar qual resultado foi reportado. Isso constitui um risco direto à integridade científica dos resultados.

**Consequência de não agir:**
- Métricas podem variar entre execuções com os mesmos dados
- Impossível auditar se um resultado publicado é reproduzível
- Grid search produz rankings de hiperparâmetros instáveis
- Testes de ablação com resultados inconsistentes

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | `random_state=42` nos modelos é necessário mas insuficiente — o estado global NumPy/Python também afeta resultados | Alto | NumPy e Python não usarem aleatoriedade em nenhum ponto do pipeline além dos modelos |
| 2 | `n_jobs=-1` com paralelismo pode introduzir não-determinismo em certas plataformas | Médio | Testes mostrarem resultados idênticos com paralelismo ativado |
| 3 | Uma seed global única (ex: 42) é suficiente para todo o pipeline | Alto | Experimentos multimodais exigirem seeds independentes por componente |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Execuções com mesmos dados e mesma seed produzem resultados bit-a-bit idênticos | Must-have |
| 2 | A seed deve ser configurável via argumento/variável de ambiente (não hardcoded) | Alto |
| 3 | A seed deve ser registrada junto com cada execução (run_id) | Alto |
| 4 | Sem impacto em performance | Médio |

---

## Dados Relevantes

- **Grep por `seed` em `src/`:** 0 ocorrências (exceto `random_state` nos modelos)
- **Grep por `numpy.random.seed`:** 0 ocorrências
- **run_id:** já salvo em `__main__.py:42`

---

## Opções Consideradas

### Opção 1: Função `seed_everything(seed)` centralizada em `config.py` ⭐ (Recomendada)

**Descrição:**
Criar uma função que controla todas as fontes de aleatoriedade do pipeline, chamada uma única vez no início de `__main__.py`.

```python
# src/dengue_pipeline/config.py
import os
import random
import numpy as np

def seed_everything(seed: int = 42) -> None:
    """Controla todas as fontes de aleatoriedade para reprodutibilidade científica."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    # Controle de paralelismo BLAS/OpenMP (reduz não-determinismo)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    # XGBoost e sklearn respeitam random_state nos modelos — já configurado
```

Chamada no início do pipeline:
```python
# __main__.py
from dengue_pipeline.config import seed_everything, BASE_DIR

GLOBAL_SEED = int(os.getenv("PIPELINE_SEED", "42"))
seed_everything(GLOBAL_SEED)
```

A seed é também salva no JSON de resultados de cada execução para rastreabilidade.

**Prós:**
- Controla todas as fontes de aleatoriedade conhecidas
- Configurável via `PIPELINE_SEED` env var
- Registrada junto ao `run_id` para auditoria
- Sem dependências externas

**Contras:**
- `OMP_NUM_THREADS=1` pode reduzir performance em algumas operações de álgebra linear
- Não garante determinismo perfeito em GPUs (não aplicável aqui)

**Custo estimado:** PEQUENO — ~2 horas

---

### Opção 2: `random_state` explícito em todos os objetos (sem seed global)

**Descrição:**
Passar `random_state` explicitamente em todos os objetos que aceitam (modelos, splitters), sem alterar o estado global NumPy.

```python
splitter = TimeSeriesSplit(n_splits=5, gap=4)  # já sem estado aleatório
model = RandomForestRegressor(random_state=SEED, ...)
```

**Prós:**
- Sem efeito colateral global
- Mais pythônico para bibliotecas

**Contras:**
- Não controla `numpy.random` usado em operações fora dos modelos
- Não documenta a seed de forma centralizada e rastreável
- Incompleto para garantia científica total

**Custo estimado:** PEQUENO — ~1 hora (mas incompleto)

---

### Opção 3: Do Nothing

**Prós:** Sem custo imediato.

**Contras:**
- Resultados potencialmente irreproduzíveis
- Impossibilidade de auditar resultados publicados
- Grid search pode retornar rankings diferentes entre execuções

**Custo estimado:** NULO agora / ALTO no futuro (questionamento de banca sobre reprodutibilidade)

---

## Comparativo

| Critério | Opção 1 (seed_everything) | Opção 2 (random_state explícito) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Reprodutibilidade global | ✅ | Parcial | ❌ |
| Configurável por execução | ✅ | Parcial | ❌ |
| Rastreável por run_id | ✅ | ❌ | ❌ |
| Custo | Pequeno | Pequeno | Nulo |

**Recomendação:** Opção 1 — único mecanismo que oferece reprodutibilidade demonstrável e auditável.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Adicionar `seed_everything(seed)` em `config.py` | @roger | TBD | NOT STARTED |
| Chamar `seed_everything(GLOBAL_SEED)` no início de `__main__.py` | @roger | TBD | NOT STARTED |
| Salvar `seed` junto ao `run_id` no JSON de resultados de cada execução | @roger | TBD | NOT STARTED |
| Documentar `PIPELINE_SEED` no `README.md` | @roger | TBD | NOT STARTED |
| Executar o pipeline 2x com mesmos dados e verificar que resultados são idênticos | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 1: Função `seed_everything(seed)` centralizada em `config.py`    

**Data:** 2026-05-27

**Rationale:** Opção 1 é a única que garante reprodutibilidade global, rastreabilidade por run_id e configurabilidade externa, alinhando o pipeline com padrões científicos. As outras opções deixariam falhas de reprodutibilidade difíceis de detectar ou resultariam em sous-ótimos incompletos.

**Follow-up:**
- [ ] Adicionar teste de regressão: "duas execuções com mesma seed produzem mesmo RMSE"
- [ ] Incluir seed no relatório final de modelagem (`.notebook/relatorio_final_execucao.md`)
