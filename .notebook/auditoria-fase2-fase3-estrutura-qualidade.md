# Auditoria Fase 2 e 3 — Estrutura, Duplicações e Qualidade de Código

**Tags:** `auditoria`, `duplicação`, `qualidade`, `imports-circulares`, `estrutura`
**Data:** 2026-05-27

---

## Fase 2A — Component Flattening Analysis (Arquivos Fora do Lugar)

### Hierarquia de Namespace: `src/dengue_pipeline/`

```
dengue_pipeline/             ← Namespace raiz (tem sub-pacotes)
├── __init__.py              ← Vazio ✅
├── etl/                     ← Leaf node ✅
├── modeling/                ← Leaf node ✅
├── reporting/               ← Leaf node ✅
├── shared_kernel/           ← Leaf node ✅
└── utils/                   ← Leaf node ✅
```

**Veredito:** Estrutura `src/` não tem arquivos "órfãos" no namespace raiz. O `__init__.py` do pacote principal está correto e vazio. A hierarquia de diretórios é adequada — cada subpacote é folha e contém apenas arquivos de seu domínio.

### Arquivos Fora do Lugar na Raiz do Projeto (Root-Level Orphans)

| Arquivo | Tipo | Onde Deveria Estar | Severidade |
|---|---|---|---|
| `dengue_radf.py` | Pipeline legado | `scripts/` ou deprecado | 🟡 |
| `plano_prompts_opus.md` | Documento de planejamento | `.notebook/` | 🟢 |
| `dataset_processado.parquet` | Artefato de dados | `dados_processados/` | 🟡 |
| `predicoes_ablation.csv` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `predicoes_modelos_finais.csv` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `predicoes_modelos_finais_LEAKY.csv` | Artefato LEAKY obsoleto | Deletar | 🔴 |
| `resultados_ablation.csv` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `resultados_ablation_LEAKY.csv` | Artefato LEAKY obsoleto | Deletar | 🔴 |
| `resultados_ablation_por_ra.csv` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `resultados_ablation_winner.json` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `resultados_ablation_winner_LEAKY.json` | Artefato LEAKY obsoleto | Deletar | 🔴 |
| `resultados_tuning.csv` | Artefato de modelagem | `resultados_modelagem/` | 🟡 |
| `resultados_tuning_LEAKY.csv` | Artefato LEAKY obsoleto | Deletar | 🔴 |
| `scripts/modelo_rf_tunado.joblib` | Modelo serializado | `resultados_modelagem/` | 🔴 |
| `scripts/modelo_rf_tunado_LEAKY.joblib` | Modelo LEAKY obsoleto | Deletar | 🔴 |
| `scripts/modelo_xgb_tunado.joblib` | Modelo serializado | `resultados_modelagem/` | 🔴 |
| `scripts/modelo_xgb_tunado_LEAKY.joblib` | Modelo LEAKY obsoleto | Deletar | 🔴 |

---

## Fase 2B — Common Domain Detection (Duplicação de Lógica de Negócio)

### Domínio 1: Normalização de RA (DUPLICAÇÃO DIRETA)

Duas implementações independentes da mesma lógica de mapeamento de nomes de RAs:

| Implementação | Arquivo | Linhas |
|---|---|---|
| `normalize_ra()` (legado) | `dengue_radf.py:L17-43` | Dicionário hardcoded de 13 aliases |
| `normalizar_ra()` (modular) | `shared_kernel/ra_registry.py:L95-113` | Usa lookup dinâmico + aliases |

**Risco:** Os dois dicionários de aliases têm entradas diferentes. Exemplo: `dengue_radf.py` mapeia `'SAO SEBASTIAO': 'SÃO SEBASTIÃO'` (com acento no canônico), enquanto `ra_registry.py` opera sem acentos. Se `dengue_radf.py` for mantido em produção, um mesmo registro pode ser normalizado para nomes diferentes dependendo do pipeline usado.

### Domínio 2: Cálculo de `epi_sunday` (DUPLICAÇÃO DIRETA)

| Implementação | Arquivo | Linhas |
|---|---|---|
| Inline em `carregar_e_limpar_dados()` | `dengue_radf.py:L72-74` | `date - pd.to_timedelta((weekday+1)%7)` |
| `domingo_epidemiologico()` | `shared_kernel/epi_calendar.py` | Função reutilizável |

**Risco:** Qualquer correção no cálculo precisa ser feita em dois lugares.

### Domínio 3: Carregamento de Dados Climáticos (DIVERGÊNCIA DE IMPLEMENTAÇÃO)

| Implementação | Arquivo | Fonte |
|---|---|---|
| `obter_dados_climaticos()` | `dengue_radf.py:L94-146` | Open-Meteo via HTTP |
| `carregar_clima()` | `etl/weather_ingestion.py:L6-56` | Cache local + merge InfoDengue (umidade) |

**Divergência crítica:** `dengue_radf.py` não inclui umidade (umidmed, umidmin, umidmax) no dataset. `weather_ingestion.py` inclui. Rodar `dengue_radf.py` produz um dataset com menos features, gerando modelos diferentes e incomparáveis com os do pipeline modular.

### Domínio 4: Lag Climático (INCONSISTÊNCIA SEMÂNTICA)

| Implementação | Arquivo | Método |
|---|---|---|
| Lag global (correto) | `dengue_radf.py:L177-181` | `.shift(lag)` direto na tabela de clima |
| Lag por RA (incorreto) | `feature_engineering.py:L80` | `groupby("RA")[col].shift(lag)` |

**Impacto:** Na implementação modular, os primeiros 8 lags de cada RA têm NaN desnecessário. Para RAs com poucos registros iniciais, isso pode descartar semanas válidas via `dropna()`.

### Domínio 5: Métricas de Avaliação (IMPORT CIRCULAR LATENTE)

`evaluation.py:L8` importa `ajustar_prever_config` de `train_tuning.py`.
`train_tuning.py:L106,142,248` faz imports locais (dentro da função) de `agregar_metricas` e `rmse` de `evaluation.py`.

**Padrão:** Import circular resolvido com imports tardios (dentro de funções). Funciona em runtime, mas é um sinal de design problem — `evaluation.py` e `train_tuning.py` têm dependência mútua. A separação de responsabilidades está comprometida: `evaluation.py` chama o treinador para executar ablação.

---

## Fase 3 — Coding Guidelines (Qualidade do Código)

### G1 — `iterrows()` em contextos desnecessários

| Localização | Uso | Impacto | Alternativa |
|---|---|---|---|
| `gerar_populacao_historica.py:L30` | Loop sobre 33 RAs | Baixo (n=33) | `df.apply()` ou lógica vetorizada |
| `gerar_populacao_historica.py:L74` | Loop sobre 10 anos para print | Mínimo | `df.to_string()` ou f-string vetorizado |
| `report_writer.py:L40` | Formatação de tabela Markdown | Mínimo | Funciona, mas poderia usar `df.to_markdown()` |

### G2 — `except Exception` muito amplo

| Localização | Contexto | Problema |
|---|---|---|
| `train_tuning.py:L328` | Bloco de Conformal Prediction | Silencia qualquer erro — incluindo bugs de código como `TypeError`, `KeyError`. O `[AVISO]` no print não é suficiente para detectar falhas silenciosas em produção. |
| `ra_registry.py:L53` | Fallback de carregamento de população | `except Exception: pass` sem log — qualquer falha ao carregar o CSV resulta em silêncio total e fallback para lista estática, que pode estar desatualizada. |

### G3 — `print()` como sistema de logging

O módulo `src/` usa `print()` extensivamente para rastreamento de execução (14 ocorrências no `src/`). Em um pipeline de produção ou científico isso:
- Não tem níveis de severidade (INFO/WARNING/ERROR)
- Não tem timestamps
- Não pode ser redirecionado/filtrado sem capturar stdout
- Dificulta testes unitários (precisa capturar sys.stdout)

**Impacto:** Baixo para uso interativo. Médio para uso em produção ou CI.

### G4 — Lambda com efeito colateral em `map()` no rolling validation

`train_tuning.py:L271-275`:
```python
rows[f"cases_lag_{lag}"] = rows["RA"].map(
    lambda ra, lag=lag: history.get(ra, [np.nan] * lag)[-lag]
    if len(history.get(ra, [])) >= lag
    else np.nan
)
```
**Problema:** A lambda acessa `history` por closure. Em um contexto paralelo ou de re-execução parcial, isso pode introduzir comportamento inesperado. Além disso, `history.get(ra, [np.nan] * lag)` cria uma lista de NaNs descartada imediatamente — ineficiente. Deveria usar uma função nomeada com guard clause.

### G5 — Hardcoding de datas e paths

| Localização | Valor Hardcoded | Problema |
|---|---|---|
| `dengue_radf.py:L111` | `"end_date": "2026-05-24"` | Data fixa — precisa de atualização manual a cada reexecução |
| `dengue_radf.py:L225-226` | `'2025-01-01'` como corte treino/teste | Sem parâmetro, impossível mudar sem editar código |
| `feature_engineering.py:L45` | `pd.Timestamp("2026-02-22")` | Data hardcoded como fim da grade |
| `train_tuning.py:L255` | `dummy_columns` de `df["RA"]` completo | Usa `df` inteiro (inclui teste 2025) para calcular dummies — potencial vazamento de RAs do futuro |

### G6 — Ausência de testes unitários

Nenhum arquivo `test_*.py` ou `pytest` foi encontrado em nenhuma parte do repositório. O pipeline inteiro é validado apenas pela execução completa (`python -m dengue_pipeline`), sem testes granulares. Isso significa:
- Qualquer refatoração corre risco de regressão silenciosa
- Impossível testar `calibrar_conformal`, `agregar_metricas`, `normalizar_ra` isoladamente

---

## Referências de Código (Fase 2+3)

- Import circular: `evaluation.py:L8` ↔ `train_tuning.py:L106,142,248`
- Lag climático por RA: `feature_engineering.py:L77-80`
- Lambda closure rolling: `train_tuning.py:L271-275`
- `except Exception` silencioso: `ra_registry.py:L53`, `train_tuning.py:L328`
- Duplicação normalize_ra: `dengue_radf.py:L17-43` vs `ra_registry.py:L95-113`
- Dummies com `df` completo: `train_tuning.py:L255`
