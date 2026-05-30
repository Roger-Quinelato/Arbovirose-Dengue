# RFC-02: Prevenção de Vazamento de Dados no Pipeline de Validação

| Campo            | Valor                                                                 |
|------------------|-----------------------------------------------------------------------|
| **Impacto**      | HIGH — compromete validade de todas as métricas de CV               |
| **Status**       | NOT STARTED                                                           |
| **Driver**       | @roger-quinelato                                                      |
| **Aprovador**    | @roger-quinelato                                                      |
| **Contribuidores** | Orientador (se aplicável)                                          |
| **Informados**   | —                                                                     |
| **Prazo**        | Antes de reportar resultados de validação cruzada                    |
| **Criado em**    | 2026-05-27                                                            |
| **Atualizado**   | 2026-05-27                                                            |

---

## Background

**Estado Atual:**
Em [`train_tuning.py`](../src/dengue_pipeline/modeling/train_tuning.py), a função `cv_score_parametros` computa `dummy_columns` a partir de `treino_completo` **fora do loop** do `TimeSeriesSplit`:

```python
# linha 154 — fora do loop de folds
dummy_columns = pd.get_dummies(treino_completo["RA"], prefix="RA", dtype=float).columns.tolist()

for train_idx, val_idx in splitter.split(datas):   # loop começa aqui
    fold_train = treino_completo[...train_dates...]
    fold_val   = treino_completo[...val_dates...]
    X_train, ... = preparar_matriz_design(fold_train, config, dummy_columns)  # dummy_columns pré-calculado
```

Em [`feature_engineering.py`](../src/dengue_pipeline/modeling/feature_engineering.py), `construir_dataset_consolidado` computa lags e features sazonais sobre o dataset **completo** (incluindo dados de teste futuros) antes de qualquer split temporal.

**Problema:**

1. **Schema leakage (dimensional leakage):** O `fold_train` em folds iniciais recebe o esquema de colunas (RAs) inferido de todo `treino_completo`. Se uma RA não teve casos nas primeiras semanas, o modelo ainda assim recebe a coluna correspondente — informando a topologia futura da distribuição espacial.

2. **Leakage arquitetural em feature engineering:** Lags e features derivadas são computados sobre o dataset inteiro. Embora `shift()` seja causal por natureza, a pipeline atual não **encapsula** esse processamento dentro dos folds, criando risco de contaminação futura ao introduzir qualquer normalização, rolling window ou imputation.

**Por que agora:**
Em pesquisa aplicada séria, "schema leakage" invalida a estimativa de generalização. Métricas publicadas sem este tratamento podem estar infladas de forma imperceptível. O risco aumenta ao adicionar features como médias móveis ou scalers.

**Consequência de não agir:**
- Generalização irreal: RMSE de CV otimista vs. performance real
- Invalidação de comparações com literatura
- Retrabalho forçado ao submeter artigo ou ao ser questionado por banca

---

## Assumptions

| # | Pressuposto | Confiança | Invalidado se |
|---|-------------|-----------|---------------|
| 1 | Todas as RAs do Distrito Federal estão presentes em toda a série histórica | Alto | Criação de nova RA administrativa sem retroatividade |
| 2 | O impacto prático do schema leakage é pequeno (mesmas RAs em todos os folds) | Médio | Análise de cobertura por RA revelar bias sistemático |
| 3 | Refatoração para encapsulamento intra-fold não aumentará tempo de execução de forma proibitiva | Médio | Pipeline de CV passar de minutos para horas |

---

## Critérios de Decisão

| Prioridade | Critério | Peso |
|------------|----------|------|
| 1 | Eliminar qualquer forma de information leakage demonstrável | Must-have |
| 2 | Manter performance computacional aceitável (CV < 30 min) | Alto |
| 3 | Compatibilidade com os modelos RF e XGB atuais | Alto |
| 4 | Facilitar adição futura de novos transformadores sem risco de leakage | Médio |

---

## Dados Relevantes

- **Arquivo principal:** [`train_tuning.py`](../src/dengue_pipeline/modeling/train_tuning.py) — linha 154 (fora do loop) vs. linha 157 (início do loop)
- **Arquivo secundário:** [`feature_engineering.py`](../src/dengue_pipeline/modeling/feature_engineering.py) — função `construir_dataset_consolidado` (linhas 27–97)
- **Ferramentas disponíveis:** `sklearn.pipeline.Pipeline`, `ColumnTransformer`, `OneHotEncoder`

---

## Opções Consideradas

### Opção 1: Mover `get_dummies` para dentro do loop de folds ⭐ (Recomendada — mínima)

**Descrição:**
Mover o cálculo de `dummy_columns` para **dentro** do loop do `TimeSeriesSplit`, de modo que cada fold infira o esquema de RAs apenas a partir de seu `fold_train`.

```python
for train_idx, val_idx in splitter.split(datas):
    fold_train = treino_completo[...train_dates...]
    fold_val   = treino_completo[...val_dates...]
    # Calculado DENTRO do fold — sem leakage de topologia futura
    dummy_cols_fold = pd.get_dummies(fold_train["RA"], prefix="RA", dtype=float).columns.tolist()
    X_train, ... = preparar_matriz_design(fold_train, config, dummy_cols_fold)
    X_val,   ... = preparar_matriz_design(fold_val,   config, dummy_cols_fold)
```

**Prós:**
- Correção cirúrgica — mínima mudança de código
- Resolve o schema leakage imediatamente
- Sem impacto na interface das funções existentes

**Contras:**
- Não encapsula o problema arquiteturalmente — é uma correção pontual
- Não previne regressão se outro transformer for adicionado fora do fold

**Custo estimado:** PEQUENO — ~2 horas

---

### Opção 2: Encapsulamento completo com `sklearn.Pipeline` ⭐ (Recomendada — robusta)

**Descrição:**
Substituir o pipeline procedural por um `sklearn.Pipeline` formal que encapsula `ColumnTransformer` (com `OneHotEncoder`) e o estimador. O pipeline é `fit` apenas em `fold_train` e `transform` em `fold_val`.

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

preprocessor = ColumnTransformer([
    ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["RA"]),
    ("passthrough", "passthrough", numerical_features),
])

pipe = Pipeline([("pre", preprocessor), ("model", estimator)])
pipe.fit(fold_train_X_raw, fold_train_y)
pipe.predict(fold_val_X_raw)
```

**Prós:**
- Previne estruturalmente qualquer leakage futuro
- Serialização consistente (treino = inferência garantida)
- Compatível com `GridSearchCV` / `cross_validate` do sklearn nativamente
- Facilita testes unitários e auditoria

**Contras:**
- Refatoração maior — requer mudança na interface de `preparar_matriz_design`
- `prever_casos_recursivo` (transformação `expm1`) precisa ser integrada ao pipeline
- Custo de implementação e teste significativo

**Custo estimado:** GRANDE — ~5–7 dias

---

### Opção 3: Do Nothing

**Descrição:** Manter a estrutura atual.

**Prós:** Nenhum custo imediato.

**Contras:**
- Schema leakage documentado e não corrigido
- Métricas de CV potencialmente infladas (grau desconhecido)
- Risco aumenta com cada nova feature adicionada ao pipeline

**Custo estimado:** NULO agora / ALTO no futuro (retrabalho + questionamento de banca)

---

## Comparativo

| Critério | Opção 1 (patch) | Opção 2 (Pipeline sklearn) | Opção 3 (Do Nothing) |
|---|---|---|---|
| Elimina schema leakage | ✅ | ✅ | ❌ |
| Previne leakage futuro | Parcial | ✅ | ❌ |
| Custo | Pequeno | Grande | Nulo |
| Robustez arquitetural | Baixa | Alta | — |

**Recomendação:** Opção 1 em curto prazo (corrige o problema imediato); Opção 2 como objetivo arquitetural de médio prazo (ver RFC-07).

---

## Análise de Substituição por Bibliotecas de Prateleira

Com a aprovação da **Opção 2 (Encapsulamento Completo com sklearn.Pipeline)**, surge uma oportunidade valiosa de auditar o codebase em busca de rotinas matemáticas e lógicas customizadas (*ad-hoc*) que podem ser inteiramente delegadas a bibliotecas maduras e consolidadas no ecossistema de Data Science.

A delegação para bibliotecas padrão de mercado (como **scikit-learn** e **MAPIE**) não apenas reduz drasticamente o débito técnico e o número de linhas de código sob manutenção própria, mas também eleva substancialmente o **rigor epistemológico** e a confiabilidade estatística do projeto frente a exames acadêmicos e auditoria de P&D (adequando a engenharia de machine learning para o nível exigido em cenários operacionais de saúde pública e pesquisa de Doutorado).

Abaixo está o mapeamento detalhado das funções customizadas elegíveis para substituição:

### Tabela Comparativa de Substituições

| Função Customizada / Trecho Atual | Arquivo & Linha | Biblioteca & Função Recomendada | Complexidade de Migração | Impacto no Leakage / Pipeline |
| :--- | :--- | :--- | :--- | :--- |
| **`pd.get_dummies` + Reindex manual** | [preparar_matriz_design](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/feature_engineering.py#L150-L155) e [cv_score_parametros](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/train_tuning.py#L151-L154) | `sklearn.preprocessing.OneHotEncoder(handle_unknown='ignore', sparse_output=False)` integrado ao `ColumnTransformer` | **Média** | **Crítico:** Elimina de forma definitiva o vazamento de esquema de RAs (*schema leakage*) entre os folds. |
| **`calcular_erro_quadratico_medio`** | [evaluation.py:L32-43](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/evaluation.py#L32-L43) | `sklearn.metrics.root_mean_squared_error` | **Baixa** | **Indireto:** Padronização de métricas e eliminação de funções auxiliares triviais. |
| **MAPE customizado** em `consolidar_metricas_performance` | [evaluation.py:L63-68](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/evaluation.py#L63-L68) | `sklearn.metrics.mean_absolute_percentage_error` | **Baixa** | **Indireto:** Substitui fórmula manual por implementação padrão que possui testes de divisão por zero robustos. |
| **`cv_score_parametros`** (loop manual de folds) | [train_tuning.py:L128-175](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/train_tuning.py#L128-L175) | `sklearn.model_selection.cross_val_score` (com `TimeSeriesSplit` e custom scorer) | **Alta** | **Alto:** Delega a divisão temporal e a orquestração do ajuste ao sklearn de forma nativa e sem vazamentos temporais. |
| **`otimizar_hiperparametros`** (grid search manual) | [train_tuning.py:L177-249](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/train_tuning.py#L177-L249) | `sklearn.model_selection.GridSearchCV` acoplado ao Pipeline | **Alta** | **Alto:** Simplifica o fluxo de busca, integrando cross-validation nativa ao pipeline sem vazamento em transformações. |
| **Conformal Prediction Dinâmico** | [conformal_prediction.py:L23-104](file:///c:/arbodf/DocML/src/dengue_pipeline/modeling/conformal_prediction.py#L23-L104) | **`MAPIE` (MapieRegressor)** | **Alta** | **Crítico:** Substitui uma implementação manual suscetível a erros teóricos por uma biblioteca auditada de Split Conformal e séries temporais. |

---

### Detalhamento e Racional das Substituições Críticas

#### A. One-Hot Encoding via `ColumnTransformer` (scikit-learn)
*   **Problema Atual:** O codebase realiza `pd.get_dummies(frame["RA"], ...)` e depois tenta alinhar as colunas resultantes de treino com as de teste usando `.reindex(columns=dummy_columns, fill_value=0.0)`. Essa lógica ad-hoc é propensa a erros, especialmente quando categorias novas surgem na inferência ou quando categorias presentes no treino não aparecem na validação temporária.
*   **Solução:** Substituir pela combinação nativa do scikit-learn:
    ```python
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    
    categorical_preprocessor = ColumnTransformer(
        transformers=[
            ("ra_ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["RA"])
        ],
        remainder="passthrough"
    )
    ```
*   **Ganhos:**
    *   **Imunidade ao Leakage:** O encoder é "treinado" (fit) apenas com o conjunto de treino do fold. As colunas de RAs do teste são alinhadas automaticamente. RAs desconhecidas no teste são simplesmente ignoradas e marcadas como zero, sem estourar exceções ou requerer lógica ad-hoc.
    *   **Alinhamento Estrito:** Garante que a matriz de design `X` tenha exatamente o mesmo esquema e número de dimensões no treino e na inferência.

#### B. Busca e Validação Temporal com APIs Nativas do scikit-learn (`GridSearchCV` + `TimeSeriesSplit`)
*   **Problema Atual:** Atualmente, a busca de hiperparâmetros roda um loop explícito em `ParameterGrid` e chama a função customizada `cv_score_parametros`, que realiza divisões temporais manuais de datas via `TimeSeriesSplit`. Esse controle procedural manual aumenta consideravelmente o volume de código e a chance de bugs de contaminação futuros ao alterar a ordem dos passos de transformação.
*   **Solução:** Acoplar o pipeline pré-processador diretamente ao estimador e executar buscas padrão:
    ```python
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
    
    # Definição do Pipeline Robusto
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(random_state=42))
    ])
    
    # Validador Cruzado Temporal Consistente
    cv_splitter = TimeSeriesSplit(n_splits=5, gap=4)
    
    # Grade de Parâmetros integrada
    param_grid = {
        "regressor__n_estimators": [500],
        "regressor__max_features": ["sqrt"]
    }
    
    grid_search = GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=cv_splitter,
        scoring="neg_root_mean_squared_error",
        n_jobs=-1
    )
    ```
*   **Desafio Técnico de Migração:** O modelo epidemiológico utiliza transformação do target ($y = \log(1 + \text{target})$) para lidar com crescimento exponencial e heterocedasticidade. Logo, a previsão da árvore precisa ser revertida ($\exp(1) - 1$) para computar o RMSE real. Além disso, em alguns cenários (como previsão de incidência), é necessário multiplicar pela população.
*   **Mitigação do Desafio:** **Não é necessário alterar a matemática do modelo epidemiológico.** O ecossistema scikit-learn fornece o `sklearn.compose.TransformedTargetRegressor`, que envelopa o regressor aplicando `func=np.log1p` no treino e `inverse_func=np.expm1` na predição automaticamente. Para os cenários que prevêem incidência, basta criar um scorer customizado trivial com `make_scorer` que injeta a população na métrica final.

#### C. Incerteza Calibrada com `MAPIE` (MapieRegressor)
*   **Problema Atual:** O arquivo `conformal_prediction.py` implementa uma lógica ad-hoc baseada em scores locais $s_i = |y_i - \hat{y}_i| / (\hat{y}_i + \epsilon)$ e no cálculo empírico do quantil. Embora rigorosa sob a perspectiva de heterocedasticidade, criar e manter algoritmos de estatística conformal ad-hoc do zero é perigoso para um projeto de Doutorado, onde a revisão por pares pode exigir conformidade estrita com papers consolidados e bibliotecas amplamente aceitas pela comunidade.
*   **Solução:** Substituir a engine de incerteza pela biblioteca **MAPIE** (`MapieRegressor`), configurada para regressão conformal indutiva adaptativa (*Split Conformal* ou *CQR - Conformalized Quantile Regression*).
*   **Ganhos:**
    *   **Confiabilidade Acadêmica:** MAPIE é a referência global no ecossistema Python para conformal prediction. O uso de uma biblioteca amplamente reconhecida reduz barreiras na publicação de artigos científicos e teses.
    *   **Robustez Matemática:** A biblioteca lida nativamente com correções matemáticas finitas, otimizações vetorizadas avançadas, e calibração estrita para dados de séries temporais dependentes (através do método EnbPI - *Ensemble Batch Prediction Intervals*).
    *   **Limpeza de Código:** Substitui 130 linhas de código matemático personalizado por chamadas simples:
        ```python
        from mapie.regression import MapieRegressor
        
        mapie_model = MapieRegressor(estimator=rf_model, cv="prefit", method="naive") # Ou split conformal
        mapie_model.fit(X_cal, y_cal)
        y_pred, y_pis = mapie_model.predict(X_test, alpha=0.10)
        # y_pis possui limites inferior e superior calibrados dinamicamente
        ```

---

## Action Items

| Ação | Responsável | Prazo | Status |
|------|-------------|-------|--------|
| **[Prevenção OHE Leakage]** Substituir `pd.get_dummies` por `OneHotEncoder` e `ColumnTransformer` no `preparar_matriz_design` | @roger | TBD | NOT STARTED |
| **[Simplificação de Métricas]** Substituir RMSE e MAPE manuais pelas funções nativas do `sklearn.metrics` | @roger | TBD | NOT STARTED |
| **[Orquestração do Pipeline]** Substituir loop temporal manual em `cv_score_parametros` por `cross_val_score` + `TimeSeriesSplit` | @roger | TBD | NOT STARTED |
| **[Grid Search Nativo]** Substituir busca manual de hiperparâmetros por `GridSearchCV` acoplado ao Pipeline | @roger | TBD | NOT STARTED |
| **[Estatística Conformal]** Substituir calibração manual de incerteza no arquivo `conformal_prediction.py` pelo `MAPIE` | @roger | TBD | NOT STARTED |
| Adicionar teste de regressão: CV RMSE não deve variar entre execuções com mesmos dados | @roger | TBD | NOT STARTED |
| Documentar justificativa da mudança via comentário inline nos novos módulos | @roger | TBD | NOT STARTED |

---

## Outcome

**Decisão:** Opção 2: Encapsulamento completo com `sklearn.Pipeline` expandido com integração de bibliotecas nativas e MAPIE.

**Data:** 2026-05-27

**Rationale:** A escolha pela Opção 2, reforçada pelo mapeamento de delegação para bibliotecas de prateleira, é justificada pela **eliminação sistemática de múltiplos pontos de falha lógicos e matemáticos**. O uso combinado de `sklearn.Pipeline`, `ColumnTransformer`, `OneHotEncoder` e a engine do `MAPIE` remove a necessidade de lógicas *ad-hoc* frágeis (como reindexação de dummies manuais e loops de validação cruzada manuais), delegando a manutenção e a garantia de correto tratamento estatístico para pacotes exaustivamente testados pela comunidade científica mundial.

Esta decisão fortalece a **serialabilidade**, **reprodutibilidade operacional**, e a **elegibilidade científica** da tese de doutorado que ampara esta modelagem de saúde pública.

**Follow-up:**
- [ ] Medir diferença de RMSE antes/depois da correção (quantificar impacto real do leakage)
- [x] Procurar outras funções que podem ser substituidas por bibliotecas já existentes, de preferência que já usem sklearn. *(Concluído nesta revisão do plano)*
- [ ] Criar RFC de sklearn Pipeline encapsulamento e como próximo passo arquitetural
- [ ] Validar a compatibilidade da instalação do `MAPIE` no ambiente virtual (`requirements.txt`)
