# Schema do Dataset de Treinamento — Modelagem de Dengue (DF)

> **Arquivo:** `dados_processados/dataset_processado.parquet`
> **Dimensões:** 17.185 linhas × 51 colunas
> **Granularidade:** Semana epidemiológica × Região Administrativa (RA) do Distrito Federal
> **Período:** Janeiro/2017 → presente (atualização contínua)

---

## 🔑 Identificadores e Dimensões Temporais

| Coluna | Tipo | Unidade / Formato | Fonte | Descrição |
|---|---|---|---|---|
| `epi_sunday` | `datetime64[ns]` | `YYYY-MM-DD` (domingo) | ETL casos (`info-saude/`) | Domingo da semana epidemiológica CDC |
| `RA` | `object` (string) | Nome padronizado | Shared Kernel (`ra_registry`) | Região Administrativa do DF (ex: `AGUA QUENTE`, `BRASILIA`) |
| `ano` | `int32` | Ano inteiro | Derivada de `epi_sunday` | Ano calendário — usado para merge com população |

---

## 🎯 Variáveis-Alvo (Target)

> O modelo é treinado em `log1p(target)`. A conversão para escala original usa `expm1`.

| Coluna | Tipo | Unidade | Fonte | Descrição |
|---|---|---|---|---|
| `cases` | `float64` | Nº casos absolutos | SINAN / Info-Saúde (`info-saude/*.csv`) | Casos confirmados de dengue (família: Dengue + Dengue com Sinais de Alarme + Dengue Grave) na semana e RA |
| `incidencia_100k` | `float64` | Casos / 100 mil hab. | Calculada: `cases / populacao * 100000` | Incidência normalizada pela população — target alternativo na config `lag+clima+RA+incid-target` |

---

## 👥 Dados Demográficos

| Coluna | Tipo | Unidade | Fonte | Descrição |
|---|---|---|---|---|
| `populacao` | `int64` | Habitantes | `dados_processados/populacao_historica.csv` | Estimativa populacional da RA no ano correspondente |

---

## 🌡️ Variáveis Climáticas Brutas (semana atual)

> Fonte: Open-Meteo + InfoDengue (`InfoDengue/InfoDengue_2016-2026.csv`) — Brasília/DF

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `temp_max` | `float64` | °C | Temperatura máxima semanal |
| `temp_min` | `float64` | °C | Temperatura mínima semanal |
| `temp_mean` | `float64` | °C | Temperatura média semanal |
| `precip_sum` | `float64` | mm | Precipitação total semanal acumulada |
| `umidmed` | `float64` | % | Umidade relativa média semanal |
| `umidmin` | `float64` | % | Umidade relativa mínima semanal |
| `umidmax` | `float64` | % | Umidade relativa máxima semanal |

> ⚠️ `temp_max`, `temp_min`, `umidmin`, `umidmax` ficam **fora** do conjunto de features dos modelos (não usadas no treinamento). Apenas `temp_mean`, `precip_sum` e `umidmed` e seus lags compõem as features.

---

## 🌧️ Lags Climáticos (features do modelo)

> Aplicados a `precip_sum`, `temp_mean` e `umidmed`. Lags de **2 a 8 semanas** (defasagem epidemiológica — o mosquito demora semanas para completar o ciclo após chuva/temperatura favorável).

### Precipitação (`precip_sum`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `precip_sum_lag_2` | `float64` | mm | Precipitação 2 semanas atrás |
| `precip_sum_lag_3` | `float64` | mm | Precipitação 3 semanas atrás |
| `precip_sum_lag_4` | `float64` | mm | Precipitação 4 semanas atrás |
| `precip_sum_lag_5` | `float64` | mm | Precipitação 5 semanas atrás |
| `precip_sum_lag_6` | `float64` | mm | Precipitação 6 semanas atrás |
| `precip_sum_lag_7` | `float64` | mm | Precipitação 7 semanas atrás |
| `precip_sum_lag_8` | `float64` | mm | Precipitação 8 semanas atrás |

### Temperatura Média (`temp_mean`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `temp_mean_lag_2` | `float64` | °C | Temperatura média 2 semanas atrás |
| `temp_mean_lag_3` | `float64` | °C | Temperatura média 3 semanas atrás |
| `temp_mean_lag_4` | `float64` | °C | Temperatura média 4 semanas atrás |
| `temp_mean_lag_5` | `float64` | °C | Temperatura média 5 semanas atrás |
| `temp_mean_lag_6` | `float64` | °C | Temperatura média 6 semanas atrás |
| `temp_mean_lag_7` | `float64` | °C | Temperatura média 7 semanas atrás |
| `temp_mean_lag_8` | `float64` | °C | Temperatura média 8 semanas atrás |

### Umidade Média (`umidmed`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `umidmed_lag_2` | `float64` | % | Umidade média 2 semanas atrás |
| `umidmed_lag_3` | `float64` | % | Umidade média 3 semanas atrás |
| `umidmed_lag_4` | `float64` | % | Umidade média 4 semanas atrás |
| `umidmed_lag_5` | `float64` | % | Umidade média 5 semanas atrás |
| `umidmed_lag_6` | `float64` | % | Umidade média 6 semanas atrás |
| `umidmed_lag_7` | `float64` | % | Umidade média 7 semanas atrás |
| `umidmed_lag_8` | `float64` | % | Umidade média 8 semanas atrás |

---

## 📈 Lags de Casos (features do modelo)

> Lags de **1 a 4 semanas** por RA (`groupby("RA").shift(lag)`). Capturam a autocorrelação epidemiológica da série temporal.

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `cases_lag_1` | `float64` | Nº casos | Casos da semana anterior |
| `cases_lag_2` | `float64` | Nº casos | Casos de 2 semanas atrás |
| `cases_lag_3` | `float64` | Nº casos | Casos de 3 semanas atrás |
| `cases_lag_4` | `float64` | Nº casos | Casos de 4 semanas atrás |

---

## 📉 Lags de Incidência (features alternativas — config `incid-target`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `incidencia_100k_lag_1` | `float64` | Casos/100k hab. | Incidência da semana anterior |
| `incidencia_100k_lag_2` | `float64` | Casos/100k hab. | Incidência de 2 semanas atrás |
| `incidencia_100k_lag_3` | `float64` | Casos/100k hab. | Incidência de 3 semanas atrás |
| `incidencia_100k_lag_4` | `float64` | Casos/100k hab. | Incidência de 4 semanas atrás |

---

## 🔀 Features de Tendência de Curto Prazo (Anti-Bias de Picos)

> Fornecem ao modelo o **sinal de aceleração/desaceleração** do surto. Fundamentais para que árvores detectem a curvatura da série e evitem subestimação de picos epidêmicos.

| Coluna | Tipo | Unidade | Fórmula | Descrição |
|---|---|---|---|---|
| `cases_delta_1` | `float64` | Δ casos | `cases_lag_1 - cases_lag_2` | Variação semanal recente (aceleração primária) |
| `cases_delta_2` | `float64` | Δ casos | `cases_lag_2 - cases_lag_3` | Variação semanal anterior (aceleração secundária) |
| `cases_growth_rate` | `float64` | Razão adimensional | `(cases_lag_1 + 1) / (cases_lag_2 + 1)` | Taxa de crescimento semanal — análogo ao Rₜ por RA |

---

## 🔁 Features Sazonais Cíclicas

> Representação harmônica (seno/cosseno) da sazonalidade. Evita a descontinuidade da codificação numérica da semana/mês.

| Coluna | Tipo | Unidade | Fórmula | Descrição |
|---|---|---|---|---|
| `week_of_year` | `int32` | Semana ISO (1–53) | `isocalendar().week` | Semana do ano — base para features cíclicas |
| `month` | `int32` | Mês (1–12) | `dt.month` | Mês do ano — base para features cíclicas |
| `sin_week` | `float64` | [-1, 1] | `sin(2π × week / 53)` | Componente senoidal da semana epidemiológica |
| `cos_week` | `float64` | [-1, 1] | `cos(2π × week / 53)` | Componente cossenoidal da semana epidemiológica |
| `sin_month` | `float64` | [-1, 1] | `sin(2π × month / 12)` | Componente senoidal do mês |
| `cos_month` | `float64` | [-1, 1] | `cos(2π × month / 12)` | Componente cossenoidal do mês |

---

## ⚙️ Configurações de Features dos Modelos

Os modelos são treinados em uma das 4 configurações abaixo. A configuração vencedora operacional é `lag+clima+RA`.

| Config | Target | Lags de Casos | Lags Climáticos | Sazonais | RA Dummy | População |
|---|---|---|---|---|---|---|
| `lag-only` | `cases` | ✅ (1–4) + tendência | ❌ | ❌ | ❌ | ❌ |
| `lag+clima` | `cases` | ✅ (1–4) + tendência | ✅ (2–8) | ✅ | ❌ | ❌ |
| `lag+clima+RA` ⭐ | `cases` | ✅ (1–4) + tendência | ✅ (2–8) | ✅ | ✅ | ❌ |
| `lag+clima+RA+incid-target` | `incidencia_100k` | ✅ incidência (1–4) + tendência | ✅ (2–8) | ✅ | ✅ | ✅ |

> ⭐ Configuração padrão dos modelos RF e XGBoost em produção.

---

## 📦 Resumo por Categoria

| Categoria | Nº de Colunas |
|---|---|
| Identificadores / Temporais | 3 |
| Targets (casos + incidência) | 2 |
| Demográfico (população) | 1 |
| Climatologia bruta | 7 |
| Lags climáticos (3 vars × 7 lags) | 21 |
| Lags de casos (4 lags) | 4 |
| Lags de incidência (4 lags) | 4 |
| Tendência de curto prazo | 3 |
| Sazonalidade cíclica | 6 |
| **Total** | **51** |
