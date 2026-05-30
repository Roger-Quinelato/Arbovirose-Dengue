# RFC-03: Desacoplamento de Dependências Circulares e Separação de Domínios

| Campo            | Valor                                                                 |
|------------------|-----------------------------------------------------------------------|
| **Impacto**      | HIGH — impede testabilidade, extensibilidade e manutenção do código  |
| **Status**       | NOT STARTED                                                           |
| **Driver**       | @roger-quinelato                                                      |
| **Aprovador**    | @roger-quinelato                                                      |
| **Contribuidores** | —                                                                  |
| **Informados**   | —                                                                     |
| **Prazo**        | TBD                                                                   |
| **Criado em**    | 2026-05-27                                                            |
| **Atualizado**   | 2026-05-27                                                            |

---

## Background

**Estado Atual:**
O módulo [`train_tuning.py`](../src/dengue_pipeline/modeling/train_tuning.py) e [`evaluation.py`](../src/dengue_pipeline/modeling/evaluation.py) possuem dependência circular mútua:

```python
# train_tuning.py — linhas 106, 142, 264 (dentro de funções para evitar erro de import)
from dengue_pipeline.modeling.evaluation import consolidar_metricas_performance
from dengue_pipeline.modeling.evaluation import calcular_erro_quadratico_medio

# evaluation.py — linha 123 (dentro de função para evitar erro de import)
from dengue_pipeline.modeling.train_tuning import executar_ajuste_previsao
```

O uso de imports dentro de funções é o sintoma — não a solução. Ele mascara a violação de limites arquiteturais: **domínio de treinamento e domínio de avaliação estão acoplados**.

Adicionalmente, o repositório mistura responsabilidades em cada módulo:
- `feature_engineering.py`: ingestão de dados (ETL) + engenharia de features + persistência em Parquet
- `train_tuning.py`: treinamento + predição + serialização de modelos + escrita de CSVs
- `evaluation.py`: cálculo de métricas + escrita de resultados + lógica de ablação + invocação de treinamento

**Por que agora:**
A dependência circular impossibilita:
1. Importar qualquer módulo de forma isolada para testes unitários
2. Adicionar um novo avaliador sem recompilar todo o grafo de dependências
3. Rastrear erros em produção — stacktraces de imports circulares são confusas

**Consequência de não agir:**
- Codebase cresce em complexidade e se torna cada vez mais difícil de modificar
- Testes unitários são inviabilizados
- Qualquer refatoração futura é de alto risco

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | O orquestrador `__main__.py` pode assumir a responsabilidade de coordenar chamadas entre módulos | Alto | Lógica de negócio for incompatível com separação |
| 2 | A separação pode ser feita incrementalmente sem quebrar o pipeline | Alto | Acoplamento for mais profundo do que o identificado |
| 3 | Existem outros imports circulares além de `train_tuning ↔ evaluation` | Must-have | Inspeção completa revelar outros ciclos |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Eliminar dependências circulares | Must-have |
| 2 | Cada módulo deve ser importável de forma isolada | Must-have |
| 3 | Minimizar breaking changes na interface pública | Alto |
| 4 | Facilitar escrita de testes unitários isolados | Alto |
| 5 | Seguir o princípio de responsabilidade única (SRP) | Alto |

---

## Dados Relevantes

- **Ciclo confirmado:** `train_tuning.py` → `evaluation.py` → `train_tuning.py`
- **Sintoma:** imports `lazy` (dentro de funções) em 3 locais: `train_tuning.py:106`, `train_tuning.py:142`, `train_tuning.py:264`, `evaluation.py:123`
- **Princípio violado:** Dependency Inversion Principle (DIP) do SOLID

---

## Opções Consideradas

### Opção 1: Introduzir camada de orquestração e quebrar o ciclo ⭐ (Recomendada)

**Descrição:**
Extrair a lógica que cria a dependência circular para um módulo `orchestration.py` (ou expandir `__main__.py`). Os módulos `train_tuning` e `evaluation` passam a ser **puramente funcionais** — recebem dados, retornam resultados — sem invocar lógica de negócio um do outro.

**Nova estrutura proposta:**

```
modeling/
├── train_tuning.py     # Apenas: treina modelo, retorna predições (DataFrames)
├── evaluation.py       # Apenas: recebe DataFrames de predição, retorna métricas
├── orchestration.py    # NOVO: coordena treino → predição → avaliação
│                       #       elimina o ciclo mantendo ambos independentes
├── conformal_prediction.py
└── feature_engineering.py
```

**Como funciona:**
1. `train_tuning.py` retorna apenas DataFrames e modelos — sem importar `evaluation`
2. `evaluation.py` recebe apenas DataFrames — sem importar `train_tuning`
3. `orchestration.py` (ou `__main__.py`) chama `train_tuning`, pega o resultado, e passa para `evaluation`

**Prós:**
- Elimina completamente o ciclo de dependência
- Cada módulo é testável de forma isolada
- Segue DIP e SRP
- Pipeline permanece funcional

**Contras:**
- Requer criação de `orchestration.py` e refatoração das funções que cruzam os limites
- Breaking change na API interna (não na pública)

**Custo estimado:** MÉDIO — ~3–4 dias

---

### Opção 2: Mover funções de baixo nível para `shared_kernel`

**Descrição:**
Mover funções como `calcular_erro_quadratico_medio` para `shared_kernel/metrics.py`, quebrando a dependência de `train_tuning` em `evaluation` para funções utilitárias.

**Prós:**
- Correção rápida para parte do ciclo
- Sem breaking changes na estrutura de módulos

**Contras:**
- Resolve apenas metade do problema (ainda há `evaluation.py` importando `train_tuning`)
- Não melhora a separação de domínios — apenas move código

**Custo estimado:** PEQUENO — ~1 dia (mas incompleto)

---

### Opção 3: Do Nothing

**Prós:** Nenhum custo imediato. O pipeline funciona com imports `lazy`.

**Contras:**
- Imports circulares são uma dívida técnica ativa
- Testes unitários são estruturalmente impossibilitados
- Risco de `ImportError` ao mudar ordem de execução ou rodar em paralelo

**Custo estimado:** NULO agora / ALTO no futuro

---

## Comparativo

| Critério | Opção 1 (Orquestrador) | Opção 2 (shared_kernel) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Elimina ciclo completamente | ✅ | Parcial | ❌ |
| Testabilidade unitária | ✅ | Parcial | ❌ |
| Custo | Médio | Pequeno | Nulo |
| Separação de domínios | ✅ | Não | ❌ |

**Recomendação:** Opção 1 com implementação incremental — começar por quebrar `evaluation.py → train_tuning.py`, que é o acoplamento mais crítico.

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| Mapear todos os pontos de cruzamento entre `train_tuning` e `evaluation` | @roger | TBD | NOT STARTED |
| Criar `orchestration.py` com função `executar_ciclo_treino_avaliacao` | @roger | TBD | NOT STARTED |
| Remover imports `lazy` de `train_tuning.py` (linhas 106, 142, 264) | @roger | TBD | NOT STARTED |
| Remover import `lazy` de `evaluation.py` (linha 123) | @roger | TBD | NOT STARTED |
| Verificar com `python -c "import dengue_pipeline.modeling.train_tuning"` que não há erros | @roger | TBD | NOT STARTED |
| Escrever teste unitário para `evaluation.consolidar_metricas_performance` de forma isolada | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 1: Introduzir camada de orquestração e quebrar o ciclo ⭐    

**Data:** 2026-05-27

**Rationale:** A escolha pela Opção 1 é justificada pela necessidade de eliminar a dependência circular de forma definitiva, proporcionando **maior robustez, testabilidade e manutenibilidade** ao código.

Embora a Opção 2 (mover funções de baixo nível) pudesse ser uma correção mais rápida, ela não resolveria o problema fundamental do acoplamento entre os módulos de treinamento e avaliação. A Opção 1, por outro lado:

* **Elimina completamente o ciclo de dependência:** Cada módulo torna-se importável de forma isolada, facilitando testes unitários e debugging.
* **Melhora a separação de domínios:** O orquestrador assume a responsabilidade de coordenar o fluxo, seguindo o princípio de responsabilidade única (SRP).
* **Permite implementação incremental:** A quebra do ciclo pode ser feita de forma controlada, começando pelo acoplamento mais crítico.     

**Follow-up:**
- [ ] Executar `pylint --disable=all --enable=cyclic-import` para detectar outros ciclos
- [ ] Criar TDD de `orchestration.py` após aprovação
- [ ] Inspeção completa revelar outros ciclos