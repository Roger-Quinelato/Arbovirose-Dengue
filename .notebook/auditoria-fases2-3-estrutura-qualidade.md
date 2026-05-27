# Auditoria Fases 2 e 3 — Estrutura, Organização, Duplicações e Qualidade de Código

**Tags:** `auditoria`, `estrutura`, `qualidade`, `duplicação`, `iterrows`, `design-patterns`
**Data:** 2026-05-27

---

## 🗺️ Fase 2: Estrutura, Organização e Duplicações

Esta fase foi executada com base nos princípios das skills `component-flattening-analysis` e `component-common-domain-detection`, avaliando a modularidade do repositório, classes órfãs em subdomínios/root e duplicações funcionais críticas.

### 1. Mapeamento de Hierarquia de Componentes (Component Tree)

O repositório apresenta a seguinte estrutura organizacional real:

```
c:\arbodf\DocML\
├── [Orphan] dengue_radf.py                    # Classe órfã de domínio (legado ativo)
├── [Orphan] dengue_analise_modelagem.ipynb    # Classe órfã exploratória (legado)
├── [Orphan] plano_prompts_opus.md             # Documento de design órfão
├── [Orphan] dataset_processado.parquet        # Artefato de dados órfão
├── dados_processados/                         # Leaf: Armazenamento de dados estruturados
│   └── populacao_historica.csv
├── resultados_modelagem/                      # Leaf: Resultados estruturados
│   └── rolling_validation_resultados.csv
├── scripts/                                   # Root estendido / Poluição de Artefatos
│   ├── gerar_populacao_historica.py           # Script utilitário
│   ├── [Orphan] modelo_rf_tunado.joblib       # Binário pesado (>180MB) em local de script
│   └── [Orphan] modelo_rf_tunado_LEAKY.joblib # Binário pesado (>230MB) em local de script
└── src/                                       # Root (Subdomínio modular do pipeline)
    └── dengue_pipeline/
        ├── etl/                               # Leaf Component
        ├── modeling/                          # Leaf Component
        ├── reporting/                         # Leaf Component
        ├── shared_kernel/                     # Leaf Component
        └── utils/                             # Leaf Component
```

### 2. Classes Órfãs e Poluição de Namespaces

#### ⚠️ Root Namespace Poluído (`c:\arbodf\DocML/`)
*   **Problema:** Presença de arquivos de execução monolítica (`dengue_radf.py`), notebooks soltos (`dengue_analise_modelagem.ipynb`, `dengue_analise_modelagem copy.ipynb`) e arquivos temporários de planejamento (`plano_prompts_opus.md`).
*   **Princípio Violado:** Os componentes e scripts operacionais finais devem existir apenas como nós folha (*leaf nodes*) ou diretórios encapsulados. O root do repositório deve conter apenas arquivos de configuração global (`.gitignore`, `requirements.txt`, `README.md`).
*   **Recomendação (Strategy - Split Up / Isolate):**
    *   Mover `dengue_radf.py` e os notebooks exploratórios para uma pasta isolada chamada `exploracoes/` ou `legacy/`.
    *   Mover `plano_prompts_opus.md` para `.notebook/` (onde já existe o relatório final correspondente).

#### 🔴 Binários de Modelagem na Pasta `scripts/`
*   **Problema:** Arquivos `.joblib` contendo os modelos calibrados finais (`modelo_rf_tunado.joblib` com 181 MB e a versão `LEAKY` com 236 MB) estão gravados dentro do diretório `scripts/`.
*   **Princípio Violado:** A pasta `scripts/` destina-se a código utilitário de apoio (ex: rotinas ETL offline, automações cron). Binários pesados gerados pelo pipeline representam **saídas de modelagem** e devem residir exclusivamente sob controle de infraestrutura ou em pastas dedicadas a resultados (como `resultados_modelagem/`).
*   **Recomendação:** Ajustar as variáveis globais de escrita em `train_tuning.py` para redirecionar os binários serializados para `resultados_modelagem/` e removê-los de `scripts/`.

---

### 3. Duplicação de Domínio Comum (Common Domain Duplication)

O maior problema de duplicação identificado reside na concorrência entre o pipeline monolítico legado (`dengue_radf.py`) e a nova estrutura modular (`src/dengue_pipeline/`).

#### 🔴 Normalização de RAs (Regiões Administrativas)
Existe uma divergência grave e duplicação direta na normalização de nomes de RAs para mesclagem com dados populacionais e climáticos:

1.  **Mapeamento Legado (`dengue_radf.py:L26-41`):**
    Implementa um dicionário estático `mapping` dentro de `normalize_ra(ra_name)` que remove acentos e mapeia variações específicas (ex: `'SCIA (ESTRUTURAL)' -> 'SCIA'`).
2.  **Mapeamento Modular (`shared_kernel/ra_registry.py:L68-82`):**
    Implementa uma estrutura dinâmica chamada `busca_ra_canonica()` que cruza chaves com a tabela real de populações `populacao_historica.csv` e possui um dicionário `aliases` paralelo.

**Tabela Comparativa de Normalizações:**

| Caractere / Região | Implementação `dengue_radf.py` | Implementação `ra_registry.py` | Risco de Divergência |
|---|---|---|---|
| Acentuação | Substitui acentos específicos via dict mapeado | Substitui acentos dinamicamente usando `unicodedata.normalize('NFD')` | **Alto:** Se uma nova RA com acentos surgir (ex: *Arapoanga*), o script legado não tratará de forma idêntica. |
| **SOL NASCENTE E POR DO SOL** | Mapeia para `'SOL NASCENTE E POR DO SOL'` (com acento no 'O') | Mapeia para `'SOL NASCENTE E POR DO SOL'` (com fallback estático) | **Médio:** Erros de digitação nas fontes de dados podem quebrar chaves de merge. |

**Recomendação:** Eliminar a função local de `dengue_radf.py` (ou marcá-la como depreciada) e importar `normalizar_ra` diretamente de `dengue_pipeline.shared_kernel`.

---

## 🐍 Fase 3: Qualidade do Código e Boas Práticas

Análise detalhada da legibilidade, performance de algoritmos, bugs semânticos escondidos e aderência às `coding-guidelines`.

### 1. Ineficiências de Loops e Iterações com Pandas (Gotchas de Performance)

#### ⚠️ Loops usando `iterrows()`
*   **Localização 1:** `scripts/gerar_populacao_historica.py:L30`
    ```python
    for idx, row in df_base.iterrows():
        ra = row['RA']
        p_2024 = row['populacao_2024']
        ...
    ```
*   **Localização 2:** `src/dengue_pipeline/reporting/report_writer.py:L40`
    ```python
    for _, row in df.iterrows():
        ...
    ```
*   **Análise técnica:** O uso de `iterrows()` é amplamente desencorajado no ecossistema Pandas devido à sobrecarga de criar uma série do pandas para cada linha. Embora no script demográfico (n=33 a 35 RAs) o impacto de tempo seja de milissegundos, é considerado uma má prática.
*   **Alternativa Performática:** Vectorizar a retroprojeção multiplicando taxas diretamente via matrizes do Pandas, ou usar `apply` / `zip` em cenários onde a iteração em Python puro seja estritamente necessária.

---

### 2. Desalinhamentos de Design vs. Implementação (Hardcoded Paths e Parquet)

#### 🔴 Mismatch no Local de Salvamento do Dataset Processado
*   **Localização:** `src/dengue_pipeline/modeling/feature_engineering.py:L93`
    ```python
    CAMINHO_DATASET_PARQUET = BASE_DIR / "dataset_processado.parquet"
    ...
    dataset.to_parquet(CAMINHO_DATASET_PARQUET, index=False)
    ```
*   **Gotcha:** Embora o `.gitignore` esteja configurado para ignorar arquivos `.parquet`, o arquivo processado é gerado diretamente no diretório raiz do workspace, sujando o ambiente operacional.
*   **Correção Simples:** Alterar para `BASE_DIR / "dados_processados" / "dataset_processado.parquet"`.

#### 🔴 Incoerência de Configuração no Caminho de Salvamento dos Modelos (.joblib)
*   **Localização:** `src/dengue_pipeline/modeling/train_tuning.py:L13` e `L223`
    ```python
    SCRIPTS_DIR = BASE_DIR / "scripts"
    ...
    out_path = SCRIPTS_DIR / ("modelo_rf_tunado.joblib" if model_name == "RF" else "modelo_xgb_tunado.joblib")
    ```
*   **Gotcha:** Existe um diretório explícito chamado `resultados_modelagem/` projetado para abrigar saídas de treinamento. No entanto, a implementação do script de tuning usa a constante `SCRIPTS_DIR` para salvar as saídas físicas dos modelos.
*   **Correção Simples:** Alterar a constante de salvamento para apontar para `resultados_modelagem/` ao invés de `scripts/`.

---

### 3. Análise Semântica de Feature Engineering (Lag de Clima)

#### 🟡 Gotcha Semântico: Lags Climáticos Calculados "Por RA"
*   **Localização:** `src/dengue_pipeline/modeling/feature_engineering.py:L78-80`
    ```python
    for col in ["precip_sum", "temp_mean", "umidmed"]:
        for lag in range(2, 9):
            dataset[f"{col}_lag_{lag}"] = dataset.groupby("RA")[col].shift(lag)
    ```
*   **Análise Matemática:** As variáveis climáticas são capturadas a nível macro do **Distrito Federal inteiro** (dados do Open-Meteo para a coordenada central de Brasília). Elas são mescladas no dataset principal agrupado por semana, o que significa que todas as RAs compartilham exatamente a mesma temperatura e precipitação para a mesma data.
*   **Implicação do Groupby:** Calcular `groupby("RA")[col].shift(lag)` não está matematicamente incorreto em termos de séries temporais individuais (desde que a série esteja ordenada de forma contínua por RA/data), mas é computacionalmente **inútil** e **lento** (repete 35 vezes a mesma operação de deslocamento) e introduz valores NaNs nas bordas iniciais da série histórica de cada RA desnecessariamente.
*   **Solução Otimizada:** Aplicar o `shift(lag)` diretamente na tabela climática agregada (como feito originalmente no legado em `dengue_radf.py:L177-181`) *antes* de realizar o `merge` com o grid espacial de RAs. Isso poupa tempo de processamento e reduz o risco de inconsistências caso haja gaps no grid de RAs.

---

## 📋 Matriz de Planos de Ação e Refatorações

Baseado na severidade e risco dos pontos detectados, recomenda-se a seguinte sequência de intervenções:

| Prioridade | Ação de Refatoração | Arquivos Afetados | Risco de Quebra | Esboço da Solução |
|---|---|---|---|---|
| **Alta** | **Correção de Destinos de Artefatos (Qualidade/Estrutura)** | `feature_engineering.py`, `train_tuning.py` | 🟢 Baixo | Alterar caminhos hardcoded de `.parquet` para `dados_processados/` e de `.joblib` para `resultados_modelagem/`. Mudar imports de leitura correspondentes. |
| **Média** | **Despoluição do Root e de `scripts/` (Estrutura)** | Root, `scripts/` | 🟢 Baixo | Mover os binários pesados `.joblib` já gerados para `resultados_modelagem/` e migrar `dengue_radf.py` para uma pasta de suporte (ex: `legacy/`). |
| **Média** | **Otimização de Lags de Clima (Performance/Semântica)** | `feature_engineering.py` | 🟡 Médio | Criar lags diretamente na série de clima antes da junção com o grid das RAs, eliminando o groupby climatológico ineficiente. |
| **Baixa** | **Deduplicação da Normalização de RAs (Qualidade)** | `dengue_radf.py`, `ra_registry.py` | 🟢 Baixo | Depreciar a normalização local em favor da canônica de `ra_registry.py`. |
