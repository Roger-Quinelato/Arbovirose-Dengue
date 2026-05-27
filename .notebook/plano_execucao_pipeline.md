# Plano de Execução — Pipeline de Modelagem de Dengue no DF
## Alinhado ao RFC-002 (REVISADO) e TDD `tdd-notebook-limpeza-modelagem.md`

> **Como usar**: Copie cada prompt na ordem indicada em uma sessão de trabalho com o agente.
> Cada prompt é autocontido — inclua o código gerado no prompt anterior como contexto quando necessário.
> **Execute estritamente na ordem P0 → P1 → P2.** Não pule etapas.

> **Revisão aplicada em:** 2026-05-24 — baseada em `revisao-plano-repositorio-2026-05-24.md`
> **Documentos de referência:** [RFC-002](.notebook/rfc-002-pipeline-dados-modelagem.md) · [TDD](.notebook/tdd-notebook-limpeza-modelagem.md)

---

## Por que este plano foi revisado

O plano anterior focava em uma hierarquia nacional SINAN → RA que ainda não tem compatibilidade semântica comprovada entre as fontes. A revisão crítica identificou três problemas bloqueantes:

| Problema | Impacto | Ação |
|---|---|---|
| Data leakage nos lags (calculados antes do split) | Métricas infladas, nowcasting ≠ forecast | P0 — corrigir antes de qualquer treinamento |
| Target não formalizado (`i_desc_classificacao` ignorado) | Série alvo incorreta muda todos os resultados | P0 — decidir e documentar primeiro |
| Baseline `cases_lag_1` (R²=0.697) quase empata com RF (R²=0.703) | Features climáticas/RA/população não demonstraram valor real | P1 — ablation tests obrigatórios |

---

## Visão Geral do Pipeline Revisado

```
info-saude/*.csv          populacao_historica.csv    dados_clima_cache.csv
(DF por RA, 2017–2026)    (população RA/ano)         (NASA semanal)
        │                         │                         │
        ▼                         │                         │
 [PROMPT 1]                       │                         │
 Formalizar target                │                         │
 Decidir filtros P0               │                         │
        │                         │                         │
        ▼                         ▼                         ▼
 [PROMPT 2]  ─────────────────────┴─────────────────────────┘
 Notebook EDA (qualidade, RA, população, clima)
        │
        ▼
 [PROMPT 3]
 Rolling validation sem leakage + baselines
        │
        ▼
 [PROMPT 4]
 Ablation tests (4 configs de features)
        │
        ▼
 [PROMPT 5]
 Tuning RF + XGBoost sobre melhor config
        │
        ▼
 [PROMPT 6]
 Visualizações + relatório final
        │
        ▼ (somente após P1 comprovado)
 [PROMPT 7 — P2]
 Validação compatibilidade SINAN vs info-saude
 (pré-requisito para hierarquia nacional futura)
```

---

## Bases de Dados

| Base | Caminho | Período | Granularidade |
|---|---|---|---|
| Info-Saúde DF | `info-saude/*.csv` | 2017–2026 | Por Região Administrativa |
| População histórica | `populacao_historica.csv` | 2010–2026 | Por RA, por ano |
| Clima Brasília | `dados_clima_cache.csv` | 2016–2026 | Semanal |
| InfoDengue Fiocruz | `InfoDengue/InfoDengue_2016-2026.csv` | 2016–2026 | Semanal (umidade, Rt, alertas) |
| SINAN Nacional | `dados-gov/DENGBR*.csv` | ~2001–2017 | UF (Out of Scope V1) |

---

## ⚡ P0 — PROMPT 1: Formalização do Target Epidemiológico

> **Objetivo**: Decidir e documentar os filtros exatos do target **antes de qualquer treinamento**.
> Este é o passo mais crítico do projeto. Tudo o que vier depois depende desta decisão.

```
Estou iniciando o pipeline de modelagem de dengue no DF. Antes de escrever
qualquer código de modelagem, preciso formalizar e documentar a definição
do target epidemiológico.

## Contexto

A base info-saude (c:\arbodf\DocML\info-saude\*.csv) contém notificações
de dengue do DF de 2017 a 2026. As colunas relevantes são:
- i_class_final: classificação final do caso
- i_desc_classificacao: tipo da doença
- i_desc_radf_res: Região Administrativa de residência
- i_data_prim_sintomas: data de início dos sintomas (ISO 8601)

## Questões a resolver

O pipeline atual (dengue_radf.py) filtra apenas:
  i_class_final == 'Caso Provável'

O TDD recomenda o filtro duplo:
  i_class_final == 'Caso Provável' E i_desc_classificacao == 'Dengue'

## O que quero

Inicie a construção do Jupyter Notebook `dengue_analise_modelagem.ipynb`.
Na primeira célula (ou conjunto de células), escreva o código que:

1. Carregue os arquivos info-saude/*.csv (encoding UTF-8, separador ";")
2. Exiba os valores únicos e contagens de:
   - i_class_final
   - i_desc_classificacao
   - A combinação (i_class_final, i_desc_classificacao) — top 20 por volume
3. Para os registros com i_class_final == 'Caso Provável', mostre:
   - Quantos têm i_desc_classificacao == 'Dengue'
   - Quantos têm i_desc_classificacao == 'Inconclusivo' ou 'Não Informado'
   - O impacto em volume anual (tabela: ano × filtro_simples vs filtro_duplo)
4. Gere a série temporal semanal (por epi_sunday) para AMBAS as definições
   de target e plote-as em um gráfico comparativo lado a lado
5. Ao final, imprima uma recomendação: qual filtro usar e por quê?

Caminho base: c:\arbodf\DocML\
Salvar gráfico em: c:\arbodf\DocML\resultados_graficos\target_comparativo.png
```

---

## P1 — PROMPT 2: Notebook EDA — Qualidade de Dados e Features Base

> **Objetivo**: Criar o notebook `dengue_analise_modelagem.ipynb` com as fases de limpeza,
> análise correlacional e integração de população histórica e clima.
> Pré-requisito: target formalizado no PROMPT 1.

```
Continuando o pipeline de dengue no DF.

## Decisão de target (do Prompt 1)
[COLE AQUI A DECISÃO DE FILTROS DOCUMENTADA NO PROMPT 1]

## O que quero agora

Crie o Jupyter Notebook dengue_analise_modelagem.ipynb em c:\arbodf\DocML\
com as seguintes seções:

### Seção 1 — Carga e Limpeza
- Carregar info-saude/*.csv com o filtro de target definido acima
- Aplicar normalize_ra() para padronizar nomes das RAs:
  ```python
  import unicodedata
  def normalize_ra(ra_name):
      if not isinstance(ra_name, str):
          return None
      ra_clean = ''.join(
          c for c in unicodedata.normalize('NFD', ra_name)
          if unicodedata.category(c) != 'Mn'
      ).upper().strip()
      mapping = {
          'SCIA (ESTRUTURAL)': 'SCIA',
          'SOL NASCENTE/POR DO SOL': 'SOL NASCENTE E POR DO SOL',
          'SOL NASCENTE/POR DO SOL RES': 'SOL NASCENTE E POR DO SOL',
          'SAO SEBASTIAO': 'SÃO SEBASTIÃO',
          'CEILANDIA': 'CEILÂNDIA',
          'BRAZLANDIA': 'BRAZLÂNDIA',
          'GUARA': 'GUARÁ',
          'PARANOA': 'PARANOÁ',
          'ITAPOA': 'ITAPOÃ',
          'AGUAS CLARAS': 'ÁGUAS CLARAS',
          'JARDIM BOTANICO': 'JARDIM BOTÂNICO',
          'NUCLEO BANDEIRANTE': 'NÚCLEO BANDEIRANTE',
          'CANDANGOLANDIA': 'CANDANGOLÂNDIA',
      }
      return mapping.get(ra_clean, ra_clean)
  ```
- Descartar RA == 'NAO INFORMADO' ou nula
- Descartar registros sem data válida
- Agregar por (epi_sunday, RA) → coluna `cases`
- Semana epidemiológica: epi_sunday = data - timedelta((data.weekday() + 1) % 7)

### Seção 2 — Integração de População Histórica (OBRIGATÓRIO — pré-requisito RA)
- Carregar populacao_historica.csv (colunas: RA, ano, populacao)
- Fazer JOIN por (RA, ano) com o dataset de casos
- Calcular taxa de incidência: incidencia_100k = cases / populacao * 100000
- ATENÇÃO: sem este join, qualquer feature de RA carrega viés demográfico.
  Mostre um gráfico comparando cases vs incidencia_100k para Ceilândia
  e Lago Sul para demonstrar o impacto.

### Seção 3 — Integração Climática e Análise Correlacional
- Carregar dados_clima_cache.csv (epi_sunday, temp_max, temp_min, temp_mean, precip_sum)
- Carregar InfoDengue/InfoDengue_2016-2026.csv para umidade (umidmed, umidmin, umidmax)
- Criar lags de 2 a 8 semanas de: precip_sum, temp_mean, umidmed
  ATENÇÃO: lags devem ser calculados DENTRO de cada RA (groupby RA antes do shift)
- Calcular correlação Spearman entre cada lag e incidencia_100k
- Plotar heatmap de correlações (lags × variáveis climáticas)

### Seção 4 — Codificação Cíclica Sazonal
- Adicionar ao dataset:
  sin_week = sin(2π × week_of_year / 53)
  cos_week = cos(2π × week_of_year / 53)
  sin_month = sin(2π × month / 12)
  cos_month = cos(2π × month / 12)

### Seção 5 — Gráficos de Qualidade
- Série temporal DF total (2017–2026) com anotação do pico de 2024
- Mapa de calor: semana × RA (heatmap de casos normalizados)
- Distribuição de casos por RA (top 10 por volume)

Ao final, salvar o dataset processado em:
c:\arbodf\DocML\dataset_processado.parquet
com todas as features criadas.
```

---

## P1 — PROMPT 3: Rolling Validation sem Data Leakage

> **Objetivo**: Implementar a validação temporal correta com lags calculados
> **dentro de cada fold**, separando explicitamente nowcasting de forecast fechado.

```
Continuando. Agora vou implementar a estratégia de validação temporal
correta para o pipeline de dengue.

## Problema crítico identificado

O dengue_radf.py atual calcula cases_lag_1..4 em TODA a série antes
do split treino/teste. Isso causa data leakage: no período de teste
(2025/2026), o modelo usa casos reais de semanas anteriores do
período de teste como input.

Isso é aceitável para NOWCASTING (previsão semana a semana com dados reais),
mas NÃO para forecast fechado (previsão prospectiva sem dados futuros).

## O que quero

Implemente no notebook dengue_analise_modelagem.ipynb uma nova seção:

### Seção 6 — Split e Rolling Validation Corretos

#### 6.1 — Definição dos modos de validação

Implemente as duas funções:

```python
def create_features_no_leakage(df, lag_cols, lags, group_col='RA'):
    """
    Cria lags auto-regressivos agrupados por RA, SEM leakage.
    Os lags são calculados ANTES de qualquer split.
    O split subsequente deve garantir que o período de teste
    não contenha linhas cujos lags apontam para o futuro do treino.
    """
    for col in lag_cols:
        for lag in lags:
            df[f'{col}_lag_{lag}'] = (
                df.groupby(group_col)[col].shift(lag)
            )
    return df

def rolling_forecast_split(df, date_col, train_end, test_start, test_end):
    """
    Split temporal rígido.
    - Treino: date_col <= train_end
    - Teste: test_start <= date_col <= test_end
    - NUNCA há sobreposição. Lags que cruzam a fronteira viram NaN
      e são descartados do treino (não do teste).
    """
    train = df[df[date_col] <= train_end].dropna()
    test  = df[(df[date_col] >= test_start) & (df[date_col] <= test_end)]
    return train, test
```

#### 6.2 — Dois modos de avaliação

Modo A — Nowcasting rolling (operacional):
- A cada semana T do período de teste, o modelo recebe cases_lag_1 = cases[T-1]
  (dado real da semana anterior, disponível na prática)
- Split: treino até 2024-12-31, teste semana a semana em 2025

Modo B — Forecast fechado (prospectivo):
- O modelo é treinado até 2024-12-31 e prevê 2025 inteiro SEM ver nenhum
  dado real de 2025 (os lags de casos em 2025 são previsões anteriores,
  não valores reais)
- Isso requer forecast recursivo: a previsão da semana T alimenta o lag
  para prever T+1

#### 6.3 — Resultados comparativos

Treine um modelo simples (Random Forest padrão) nos dois modos e
reporte R², MAE e RMSE separadamente para cada um.
Imprima claramente qual modo cada resultado representa.
```

---

## P1 — PROMPT 4: Ablation Tests — Demonstrando Valor das Features

> **Objetivo**: Provar (ou refutar) que features climáticas, de RA e populacionais
> agregam valor real além do baseline naive `cases_lag_1`.
> **Este é o critério de aceitação do projeto.**

```
Continuando. Agora vou executar os ablation tests para validar se
as features do modelo justificam sua complexidade.

## Contexto

A revisão crítica identificou que:
- Baseline naive cases_lag_1: R² ≈ 0.697
- Random Forest (features completas): R² ≈ 0.703
- XGBoost (features completas): R² ≈ 0.684

Uma diferença de 0.006 de R² NÃO justifica complexidade adicional.
Os ablation tests vão nos dizer onde está o ganho real, se existir.

## O que quero

Implemente no notebook a Seção 7 — Ablation Tests:

### 4 configurações de features (sequenciais e acumulativas)

Config 1 — lag-only (baseline formal):
  Features: cases_lag_1, cases_lag_2, cases_lag_3, cases_lag_4
  (agrupados por RA, sem leakage)

Config 2 — lag + clima:
  Features: Config 1 + lags de precip_sum, temp_mean, umidmed (lags 2-8)
  + sin_week, cos_week, sin_month, cos_month

Config 3 — lag + clima + RA:
  Features: Config 2 + One-Hot Encoding das Regiões Administrativas

Config 4 — lag + clima + RA + população:
  Features: Config 3 + incidencia_100k (taxa calculada com populacao_historica)
  (substitui cases como target quando disponível para testar o efeito)

### Para cada configuração, treinar

Modelos: Random Forest e XGBoost
Validação: Rolling validation do Prompt 3 (Modo A — nowcasting)
Métricas: R², MAE, RMSE (DF total e por RA — média e por RA individual)

### Output esperado

Tabela consolidada:
| Config | Modelo | R² (DF) | MAE (DF) | RMSE (DF) | R² (média RAs) |
|--------|--------|---------|----------|-----------|----------------|
| lag-only | RF | ... | ... | ... | ... |
| lag-only | XGB | ... | ... | ... | ... |
| lag+clima | RF | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

Critério de aceitação: uma config "vence" a anterior se delta R² > 0.05
OU se a melhoria de RMSE for consistente em >70% das RAs individualmente.

Salvar tabela em: c:\arbodf\DocML\resultados_ablation.csv
Salvar gráfico comparativo em: c:\arbodf\DocML\resultados_graficos\ablation_comparativo.png
```

---

## P1 — PROMPT 5: Tuning RF e XGBoost sobre a Melhor Configuração

> **Objetivo**: Otimizar hiperparâmetros apenas para a configuração de features
> que demonstrou ganho real nos ablation tests.
> Pré-requisito: resultado dos ablation tests do PROMPT 4.

```
Continuando. Os ablation tests mostraram que a melhor configuração foi:
[COLE AQUI O RESULTADO DO PROMPT 4 — CONFIG VENCEDORA]

## O que quero

Adicione uma nova seção ao notebook para realizar o tuning dos hiperparâmetros.

### Random Forest — grid de busca
```python
param_grid_rf = {
    'n_estimators': [200, 500],
    'max_depth': [5, 10, None],
    'min_samples_leaf': [1, 5, 10],
    'max_features': ['sqrt', 'log2'],
}
```

### XGBoost — grid de busca
```python
param_grid_xgb = {
    'n_estimators': [200, 500],
    'max_depth': [3, 5, 7],
    'learning_rate': [0.01, 0.05, 0.1],
    'subsample': [0.8, 1.0],
    'colsample_bytree': [0.8, 1.0],
}
```

### Validação
- Use TimeSeriesSplit (5 folds) sobre o período de treino (2017–2024)
- NUNCA use dados de 2025 no tuning
- Métrica de otimização: RMSE médio dos folds

### Avaliação final
Avalie o modelo tunado no período de teste (2025) e compare com:
- Baseline lag-only (Config 1 do Prompt 4)
- Modelo padrão (sem tuning, Config vencedora do Prompt 4)

Salvar modelos em:
c:\arbodf\DocML\scripts\modelo_rf_tunado.joblib
c:\arbodf\DocML\scripts\modelo_xgb_tunado.joblib
```

---

## P1 — PROMPT 6: Visualizações e Relatório Final

> **Objetivo**: Gerar os gráficos finais e o relatório comparativo do projeto.

```
Pipeline concluído. Gere as visualizações e o relatório final.

## Dados disponíveis
- dataset_processado.parquet: dataset completo com features
- resultados_ablation.csv: métricas por configuração
- Modelos tunados do Prompt 5

## O que quero

### Gráfico 1 — Série temporal DF total: Real vs Previsto
- Plotar: real (2017–2026), previsão Config 1 (lag-only), previsão Config vencedora
- Destacar o pico de 2024 com anotação
- Período de teste (2025) em região sombreada
- Salvar: resultados_graficos\serie_df_total.png

### Gráfico 2 — Top 6 RAs: Real vs Previsto (melhor modelo)
- 6 RAs com maior volume em 2025
- 2×3 subplots com R² individual por RA no título
- Salvar: resultados_graficos\series_top6_ra.png

### Gráfico 3 — Ablation: contribuição de cada grupo de features
- Barplot horizontal: R² por config × modelo
- Linha vertical no valor do baseline lag-only
- Destacar ganhos acima do critério de aceitação (delta > 0.05)
- Salvar: resultados_graficos\ablation_contribuicao.png

### Gráfico 4 — Mapa de incidência por RA (2025)
- Taxa média de incidência por 100k por RA em 2025
- Tabela ordenada (sem shape geográfico, só tabela visual)
- Salvar: resultados_graficos\incidencia_por_ra_2025.png

### Relatório final (imprimir no notebook)
Responda:
1. Qual config de features agregou valor real demonstrável?
2. O modelo vencedor superou o baseline lag-only pelo critério de aceitação?
3. Qual RA teve maior erro de previsão? Há hipótese explicativa?
4. O pipeline está pronto para uso em nowcasting operacional? E para forecast fechado?
5. O que ainda precisa ser feito antes de uma hierarquia nacional (SINAN)?
```

---

## P2 — PROMPT 7: Validação SINAN vs info-saude (Pré-requisito para Hierarquia Nacional)

> **Objetivo**: Provar compatibilidade temporal e semântica entre o SINAN nacional
> (dados-gov) e o info-saude local **antes** de qualquer reconciliação hierárquica.
> **Execute somente após P1 concluído e resultados satisfatórios.**

```
Agora vou validar a compatibilidade entre o SINAN nacional e o info-saude
local, como pré-requisito para a hierarquia nacional futura.

## Contexto

O SINAN (dados-gov/*.csv) cobre ~2001-2017 em nível de UF.
O info-saude cobre 2017-2026 em nível de RA do DF.
O overlap temporal é ~2017.

## Questões críticas a responder

1. No ano de 2017, os totais do DF diferem entre as fontes?
   - SINAN: SG_UF == 53, CLASSI_FIN in [1,2,3]
   - info-saude: filtro de target definido no Prompt 1
   Compare semana a semana. O delta é aceitável (<10%)?

2. A definição de "caso confirmado" é equivalente?
   - SINAN: CLASSI_FIN in [1,2,3] inclui dengue com sinais de alarme e grave
   - info-saude: 'Caso Provável' inclui dengue clínica sem confirmação laboratorial?
   Documente a equivalência ou divergência.

3. A cobertura é comparável?
   - O SINAN de 2017 cobre todas as notificações do DF
     ou há subnotificação em relação ao info-saude?

## O que quero

Crie um novo notebook separado chamado `validacao_sinan_infosaude.ipynb` (ou adicione como apêndice ao final do notebook principal) que:
1. Carrega DENGBR17.csv (SINAN 2017) e filtra DF (SG_UF == 53)
2. Carrega info-saude de 2017 com o filtro de target definido
3. Agrega ambos por epi_sunday → series semanais
4. Plota as duas séries sobrepostas com a diferença percentual
5. Calcula: correlação, diferença média percentual e pico máximo de divergência
6. Conclui: as séries são suficientemente compatíveis para splicing?

Critério de aceite: correlação ≥ 0.90 e diferença média ≤ 15%.
Se não atingir, documente por que e o que precisa ser resolvido antes
de prosseguir com a hierarquia nacional.

Salvar relatório em: c:\arbodf\DocML\.notebook\validacao-sinan-infosaude.md
```

---

## Critérios de Aceite por Fase

| Fase | Critério de Aceite | Consequência se falhar |
|---|---|---|
| P0 — Prompt 1 | Target formalizado e documentado | Não iniciar P1 |
| P1 — Prompt 3 | Lags calculados sem leakage documentado | Não prosseguir para ablation |
| P1 — Prompt 4 | Config vencedora com delta R² > 0.05 vs lag-only | Revisar features antes de tunar |
| P1 — Prompt 5 | Modelo tunado supera padrão em ≥3 folds | Revisar grid de busca |
| P2 — Prompt 7 | Correlação SINAN vs info-saude ≥ 0.90 | Não construir hierarquia nacional |

---

## Out of Scope neste plano (V1)

Os itens abaixo foram avaliados e **adiados** para V2 ou V3:

- **Hierarquia nacional Brasil→Região→UF→RA** (Prompts 2-7 do plano antigo): requer compatibilidade SINAN→info-saude comprovada (P2 acima)
- **Nixtla StatsForecast/HierarchicalForecast**: mantido como referência benchmark, não como entrega V1
- **Redes neurais LSTM/GRU**: V2 após ciclo sin/cos validado
- **Git, pyproject.toml, testes automatizados**: P2 de infraestrutura, não bloqueia a ciência

---

## Dicas de Execução

> [!IMPORTANT]
> **Ordem obrigatória P0 → P1 → P2.** Os resultados do Prompt 1 (target)
> devem ser colados como contexto nos Prompts 2 em diante.
> Os resultados do Prompt 4 (ablation) devem ser colados no Prompt 5 (tuning).

> [!WARNING]
> **Não tunar antes de ablation.** Otimizar hiperparâmetros de um modelo
> cuja config de features não demonstrou valor é desperdiçar tempo e criar
> ilusão de performance.

> [!TIP]
> **Salve o dataset processado em Parquet.** O `dataset_processado.parquet`
> do Prompt 2 é a entrada de todos os prompts subsequentes. Proteja-o.

> [!NOTE]
> **Benchmark de comparação**: qualquer modelo final será comparado contra
> `cases_lag_1` puro (R²≈0.697). Se não superar com folga, o ganho das
> features complexas não está comprovado.
