# RFC-05: Gerenciamento de Configuração de Caminhos (Eliminação de `parents[3]` Hardcoded)

| Campo            | Valor                                                                |
|------------------|----------------------------------------------------------------------|
| **Impacto**      | MEDIUM — falha silenciosa ao mover arquivos ou alterar estrutura    |
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
Quatro módulos independentes calculam `BASE_DIR` usando uma âncora frágil baseada na posição do arquivo no sistema de arquivos:

```python
# conformal_prediction.py — linha 19
# train_tuning.py          — linha 12
# evaluation.py            — linha 8
# feature_engineering.py   — linha 8
BASE_DIR = Path(__file__).resolve().parents[3]
```

O valor `parents[3]` é um número mágico que assume: **o arquivo está exatamente 3 níveis abaixo da raiz do projeto**. Mover qualquer um desses arquivos para um subdiretório diferente quebra silenciosamente toda a lógica de persistência (CSVs, JSONs, modelos .joblib).

**Problema:**
1. **Frágil:** Mover `train_tuning.py` para `modeling/tuning/train_tuning.py` faria `parents[3]` apontar para o diretório errado sem nenhum erro explícito — apenas arquivos gravados no lugar errado
2. **Duplicação:** Lógica idêntica repetida em 4 arquivos — viola DRY (Don't Repeat Yourself)
3. **Não injetável:** Impossível substituir `BASE_DIR` em testes unitários sem monkey-patching

**Por que agora:**
A refatoração arquitetural planejada (RFC-03: desacoplamento, RFC-07: sklearn Pipeline) provavelmente moverá arquivos de diretório. Corrigir os caminhos agora evita que a refatoração futura quebre o pipeline de persistência silenciosamente.

**Consequência de não agir:**
- Qualquer reorganização de diretórios quebra persistência sem avisos
- Impossível rodar o pipeline com raiz diferente (ex: ambiente Docker, CI/CD, cluster)

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | O pipeline pode ser configurado via variável de ambiente sem afetar o fluxo principal | Alto | Dependência em PATH hardcoded em outros módulos |
| 2 | Um módulo centralizado `config.py` pode ser criado sem conflicts | Alto | Nome `config` já usado em outro módulo |
| 3 | Testes unitários necessitam injetar `BASE_DIR` alternativo | Médio | Testes não forem escritos para módulos de persistência |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Falha explícita (não silenciosa) quando `BASE_DIR` não existir | Must-have |
| 2 | Configurável via variável de ambiente para CI/CD e Docker | Alto |
| 3 | DRY — lógica centralizada em um único lugar | Alto |
| 4 | Retrocompatibilidade — sem breaking changes para o fluxo atual | Médio |

---

## Dados Relevantes

- **Arquivos afetados:** 4 módulos com `BASE_DIR = Path(__file__).resolve().parents[3]`
- **Caminhos derivados:** `resultados_modelagem/`, `dados_processados/`, `resultados_graficos/`, `resultados_modelagem/conformal_calibration.json`
- **Padrão alternativo disponível:** `os.getenv("PIPELINE_ROOT")` com fallback para `parents[N]`

---

## Opções Consideradas

### Opção 1: Módulo centralizado `config.py` com fallback ⭐ (Recomendada)

**Descrição:**
Criar `src/dengue_pipeline/config.py` como fonte única de verdade para todos os caminhos do projeto. Suporta variável de ambiente `PIPELINE_ROOT` com fallback para a detecção atual via `__file__`.

```python
# src/dengue_pipeline/config.py
import os
from pathlib import Path

def _resolve_base_dir() -> Path:
    env_root = os.getenv("PIPELINE_ROOT")
    if env_root:
        base = Path(env_root).resolve()
        if not base.exists():
            raise RuntimeError(f"PIPELINE_ROOT='{env_root}' não existe.")
        return base
    # Fallback: detectar a partir de config.py (1 nível abaixo de dengue_pipeline)
    return Path(__file__).resolve().parents[2]

BASE_DIR = _resolve_base_dir()
MODELOS_DIR         = BASE_DIR / "resultados_modelagem"
DADOS_PROCESSADOS   = BASE_DIR / "dados_processados"
GRAFICOS_DIR        = BASE_DIR / "resultados_graficos"
CONFORMAL_JSON      = MODELOS_DIR / "conformal_calibration.json"
```

Cada módulo passa a importar de `config`:
```python
from dengue_pipeline.config import BASE_DIR, MODELOS_DIR
```

**Prós:**
- Fonte única de verdade para todos os caminhos
- Injetável via env var para Docker, CI/CD, testes
- Falha explícita se `PIPELINE_ROOT` apontar para diretório inexistente
- Elimina duplicação nos 4 módulos

**Contras:**
- Pequeno breaking change: substituir imports nos 4 módulos
- Adiciona dependência de `config.py` a todos os módulos de modeling

**Custo estimado:** PEQUENO — ~2 horas

---

### Opção 2: Função utilitária em `shared_kernel`

**Descrição:**
Adicionar `get_base_dir()` em `shared_kernel/paths.py` com a mesma lógica, sem criar `config.py` separado.

**Prós:**
- Aproveita `shared_kernel` já existente
- Sem novo módulo

**Contras:**
- `shared_kernel` já tem responsabilidades (RAs, população) — misturar configuração de paths é code smell
- Semânticamente menos claro que um `config.py` dedicado

**Custo estimado:** PEQUENO — ~2 horas (similar à Opção 1)

---

### Opção 3: Do Nothing

**Prós:** Sem custo imediato. Funciona enquanto a estrutura de diretórios não mudar.

**Contras:**
- Silently breaks ao refatorar diretórios (planejado em RFC-03)
- 4 cópias da mesma lógica frágil

**Custo estimado:** NULO agora / MÉDIO no futuro (debug de arquivo gravado no lugar errado)

---

## Comparativo

| Critério | Opção 1 (config.py) | Opção 2 (shared_kernel) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Fonte única de verdade | ✅ | ✅ | ❌ |
| Injetável via env var | ✅ | ✅ | ❌ |
| Falha explícita | ✅ | ✅ | ❌ |
| Clareza semântica | Alta | Média | — |

**Recomendação:** Opção 1 — criar `config.py` dedicado antes da refatoração arquitetural.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
|   Criar `src/dengue_pipeline/config.py` com `BASE_DIR` e todos os subcaminhos | @roger | TBD | NOT STARTED |
|   Substituir `BASE_DIR = Path(__file__).resolve().parents[3]` nos 4 módulos | @roger | TBD | NOT STARTED |
|   Testar pipeline completo após substituição | @roger | TBD | NOT STARTED |
|   Documentar variável `PIPELINE_ROOT` no `README.md` | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 1: Módulo centralizado `config.py` com fallback

**Data:** 2026-05-27

**Rationale:** A manutenção de caminhos fixos (`parents[3]`) em múltiplos módulos é uma prática frágil que levará a erros silenciosos durante refatorações futuras. A criação de um módulo `config.py` dedicado oferece fonte única de verdade, suporte a ambientes múltiplos via variável de ambiente e falha explícita em caso de raiz mal configurada, alinhando-se com os princípios DRY e de robustez arquitetural.

**Follow-up:**
- [ ] Adicionar validação de `BASE_DIR` no início de `__main__.py`
- [ ] Criar variável `PIPELINE_ROOT` no `.env.example` se adotado
