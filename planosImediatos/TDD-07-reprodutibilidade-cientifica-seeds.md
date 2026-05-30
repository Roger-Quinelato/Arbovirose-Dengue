# TDD-07: Reprodutibilidade Científica via Controle Centralizado de Seeds

| Campo           | Valor                        |
| --------------- | ---------------------------- |
| Tech Lead       | @roger-quinelato             |
| Team            | @roger-quinelato             |
| Epic/Ticket     | RFC-07                       |
| Status          | Approved                     |
| Created         | 2026-05-27                   |
| Last Updated    | 2026-05-27                   |

## Contexto

Em pesquisas científicas aplicadas a Machine Learning, a reprodutibilidade dos resultados numéricos é uma exigência rigorosa. Atualmente, o `dengue_pipeline` gerencia o estado aleatório de forma parcial, setando apenas o `random_state=42` nos hiperparâmetros dos modelos `RandomForest` e `XGBoost`. 

## Definição do Problema & Motivação

### Problemas que estamos resolvendo

A configuração atual não controla o não-determinismo global, incluindo:
- `numpy.random.seed()` usado em amostragens ou operações vetorizadas.
- `random.seed()` da biblioteca padrão do Python.
- Variáveis de ambiente multithreading de nível C (ex: OpenMP, MKL, OpenBLAS) que introduzem variações não determinísticas devido a *race conditions* de arredondamento em ponto flutuante, muito comuns no Scikit-Learn e XGBoost.
- O Hashing aleatório nativo das versões modernas do Python (que pode variar a ordem de chaves em dicionários caso interajam com iterações estocásticas).

Isso resulta na incapacidade de reproduzir os resultados perfeitamente, o que ameaça a confiabilidade acadêmica e impede depurações de regressão (identificar se o modelo piorou por causa de uma nova feature ou por puro ruído).

## Escopo

### ✅ No Escopo (V1 - MVP)
- Criação de uma função centralizada `seed_everything()` em `src/dengue_pipeline/config.py`.
- Adição da chamada de setup de *seed* na entrada principal do pipeline (`__main__.py`).
- Salvamento da seed adotada nos metadados de execução (junto com o `run_id`).
- Supressão de *multithreading* via variáveis de ambiente nas dependências compiladas.
- Documentação no README.md sobre a variável `PIPELINE_SEED`.

### ❌ Fora do Escopo (V1)
- Determinismo de bibliotecas focadas em GPU, como CUDA ou CuDNN (pois o projeto atual não treina redes neurais pesadas em tensores).

## Solução Técnica

### Arquitetura de Seed

A função controlará iterativamente as diferentes camadas de aleatoriedade no ambiente antes de qualquer biblioteca de processamento pesado instanciar suas *threads* padrão.

**Implementação em `config.py`**:
```python
import os
import random
import numpy as np

def seed_everything(seed: int = 42) -> None:
    """Fixa as fontes de aleatoriedade no ecossistema Python."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    
    # Suprime threads de bibliotecas matemáticas para garantir determinismo total,
    # caso o paralelismo assíncrono interno cause micro-variações no hardware atual.
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
```

**Integração no Fluxo de Orquestração** (`__main__.py`):
```python
from dengue_pipeline.config import seed_everything

# Iniciar ANTES de qualquer carregamento de modelo ou import do scikit-learn/xgboost
import os
GLOBAL_SEED = int(os.getenv("PIPELINE_SEED", "42"))
seed_everything(GLOBAL_SEED)
```

**Artefatos e Rastreabilidade**:
Ao gerar os arquivos de validação cruzada no fluxo de orquestração (via `orchestration.py`), o objeto JSON que grava os resultados globais também deve incluir a chave `"seed": GLOBAL_SEED` sob os metadados contextuais, garantindo paridade com o `run_id` especificado na RFC-06.

## Riscos

| Risco | Impacto | Probabilidade | Mitigação |
|------|--------|-------------|------------|
| Degradação de Performance de Treino | Médio | Alta | Limitar threads no OpenMP/BLAS a "1" pode lentificar o treinamento numérico. Caso os tempos de execução aumentem drasticamente, pode-se avaliar retornar `OMP_NUM_THREADS` ao padrão, desde que se observe que a instabilidade estocástica resultante não afeta as métricas em mais de `1e-5`. |
| Importação prematura desconfigurando variáveis de ambiente | Alto | Baixa | Garantir que a chamada a `seed_everything()` seja a primeira instrução real no `__main__.py`. Se algum `import` for feito antes, a JVM ou ambiente C associado pode já ter lido as variáveis `_NUM_THREADS`. |

## Plano de Implementação

| Fase | Tarefa | Descrição | Responsável | Status |
| ------------------- | ----------------- | -------------------------------------- | ------- | ------ |
| **Fase 1** | Lógica de Seed | Escrever `seed_everything()` no arquivo `config.py` (adotado na RFC-05). | @roger | TODO |
| **Fase 2** | Bootstrapping | Alterar `__main__.py` para capturar variáveis de ambiente e chamar o limitador de *seed* na primeira linha da execução. | @roger | TODO |
| **Fase 3** | Rastreabilidade | Integrar no JSON de output de resultados a chave indicando qual seed controlou o ambiente. | @roger | TODO |
| **Fase 4** | Documentação | Atualizar o README informando a variável de ambiente `PIPELINE_SEED`. | @roger | TODO |

## Estratégia de Testes

- **Testes de Integração Causal**: 
  - Executar duas passagens completas do pipeline sem alteração de dados.
  - Verificar programaticamente via script ou inspeção se o `rmse_pass_1 == rmse_pass_2` até a sexta casa decimal. Se forem divergentes, mapear que biblioteca está violando a barreira.

## Monitoramento e Observabilidade
A `seed` base da execução informada constará implicitamente em metadados de execução no topo do log (conforme o formato do `logger` sugerido na RFC-06) e servirá como elo probatório no caso de uma defesa científica, provando exata parametrização ambiental.

## Plano de Rollback
Remover a chamada à função no `__main__.py` ou retirar as travas de `_NUM_THREADS` do dicionário interno caso o determinismo em milésimos não compense a perda em horas de treinamento.
