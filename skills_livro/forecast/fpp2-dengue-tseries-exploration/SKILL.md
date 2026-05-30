---
name: fpp2-dengue-tseries-exploration
description: "Applies time series graphics and exploratory data analysis principles from Forecasting Principles and Practice (Hyndman & Athanasopoulos, Ch.1-2) to epidemiological dengue surveillance data. Use when starting a dengue forecasting project, exploring case series visually, identifying trend, seasonality, and cyclic patterns in epidemiological data, or preparing data for modeling. Trigger phrases: 'explore dengue time series', 'visualize dengue cases over time', 'identify seasonality in dengue data', 'what patterns exist in case counts', 'how to start a dengue forecasting project', 'plot epidemiological time series', 'decompose dengue series', 'trend vs seasonality vs cycle in dengue'. Do NOT use for model fitting or forecast generation (use fpp2-dengue-ets-smoothing or fpp2-dengue-arima), regression with climate covariates (use fpp2-dengue-regression-dynamic), or hierarchical aggregation across municipalities (use fpp2-dengue-hierarchical)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue Time Series Exploration

Guides the initial exploration and visualization of dengue arbovirose surveillance time series, based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.1-2. Establishes the foundation for any forecasting pipeline by identifying patterns, data quality issues, and appropriate modeling strategies before any model is fitted.

## Instructions

### Step 1: Define the Forecasting Problem

Before plotting anything, specify the target explicitly:

- **What**: Weekly, fortnightly, or monthly confirmed dengue case counts? Incidence rate per 100k? Hospitalizations? Deaths?
- **Where**: National aggregate, state (UF), municipality (municipio), regional health district (DRSAI)?
- **Horizon**: 1 week ahead (operational), 4-8 weeks (outbreak warning), 3-6 months (resource planning)?
- **Frequency**: Weekly data (SE = semana epidemiológica) is the standard in Brazilian SINAN/InfoDengue.

For dengue in Brazil: the standard unit is **confirmed or probable cases per epidemiological week (SE)** by municipality or regional aggregate, from SINAN or InfoDengue/Mosqitor.

### Step 2: Structure the Time Series Object

Convert raw case data into a proper time series structure before plotting:

```r
library(fpp2)

# Example: weekly dengue cases for a municipality
# data is a data frame with columns: SE (epidemiological week), cases
dengue_ts <- ts(data$cases,
                start = c(2010, 1),   # year, epidemiological week 1
                frequency = 52)        # 52 epidemiological weeks per year

# For daily data aggregated to weekly
# Note: SE follows ABNT/WHO calendar - starts Monday, ends Sunday
```

Important nuances for dengue data:
- Epidemiological week (SE) runs Monday–Sunday per ABNT NBR 7791 / WHO standard.
- Year has 52 or 53 epidemiological weeks — handle the 53rd week carefully to avoid `frequency` mismatches.
- SINAN notification delay: cases are reported with 1-4 week lag. Use InfoDengue's nowcast-corrected series when available.
- Missing data in low-incidence inter-epidemic periods: use `na.interp()` or treat as structural zeros.

### Step 3: Produce Essential Time Plots

**Primary time plot** — always first:
```r
autoplot(dengue_ts) +
  ggtitle("Dengue cases — Municipality X — Weekly") +
  xlab("Epidemiological Week") + ylab("Confirmed Cases") +
  theme_minimal()
```

What to look for in dengue series:
- **Epidemic peaks**: typically November–May in Southeast/South Brazil (summer/rainy season); February–April is the classic peak window.
- **Interannual variation**: epidemic cycles of 2-4 years driven by serotype cycling (DENV-1, 2, 3, 4) and population immunity.
- **Trend**: gradual upward trend since 2000s reflects urbanization, Aedes aegypti expansion, serotype introductions.
- **Outlier years**: 2015-16 (DENV-1 resurgence), 2019 (highest historical peak), 2022-24 (post-COVID rebound).
- **Structural breaks**: interventions (control campaigns), reporting system changes, ICD-10 code reclassifications.

### Step 4: Identify and Describe Patterns

Apply the three-pattern taxonomy:

**Trend** in dengue:
- Long-term rising baseline reflecting urbanization and Aedes expansion.
- Trend may be non-linear — fit a local linear or STL trend rather than a global linear trend.
- Consider log-transformation to stabilize variance before trend analysis: `log1p(cases)`.

**Seasonality** in dengue:
- Strongly seasonal: driven by temperature and rainfall which govern Aedes breeding and extrinsic incubation period.
- Peak aligns with rainy season (Dec-Apr in SE Brazil) with ~2-4 week lag after rainfall events.
- Seasonality is **not constant** — magnitude varies enormously between epidemic and non-epidemic years (heterogeneous seasonality). This is a key difference from typical commercial forecasting use cases.
- Use `ggseasonplot()` to overlay years and identify which years are anomalous.

**Cyclic behavior** in dengue:
- Multi-year epidemic cycles (2-5 year periodicity) linked to serotype dynamics.
- Not fixed frequency — cannot be modeled as seasonality. Needs susceptible-infectious-recovered (SIR) dynamics or multivariate time series.
- Distinguish: seasonality (fixed, yearly) vs. epidemic cycle (variable, multi-year).

### Step 5: Apply Diagnostic Plots

**Seasonal plot** — to compare year-over-year patterns:
```r
ggseasonplot(dengue_ts, year.labels = TRUE) +
  ggtitle("Seasonal plot: Dengue cases by epidemiological week")
```

**Seasonal subseries plot** — to check within-season consistency:
```r
ggsubseriesplot(dengue_ts) +
  ggtitle("Mean cases by epidemiological week across all years")
```

**ACF plot** — to quantify autocorrelation structure:
```r
ggAcf(dengue_ts, lag.max = 104) +
  ggtitle("ACF: Dengue cases — Weekly")
```

Interpret ACF for dengue:
- Strong positive autocorrelations at lags 1-4 weeks: epidemic wave momentum (once an outbreak starts, it persists).
- Seasonal autocorrelation peaks at lag ~52: annual pattern.
- Slow decay of ACF: indicates non-stationarity (trend or unit root) — differencing or transformation needed.
- Negative autocorrelation at lag ~26: trough follows peak within the year.

**Scatterplot matrix against climate covariates**:
```r
# Compare dengue to weekly temperature, rainfall, and humidity
GGally::ggpairs(data.frame(
  cases = as.numeric(dengue_ts),
  temp = temperature_series,
  rain = rainfall_series,
  humidity = humidity_series
))
```

### Step 6: Document Findings for Modeling

Before moving to a modeling skill, produce a structured summary:

| Feature | Observed? | Notes |
|---|---|---|
| Long-term trend | Yes/No | Direction, approximate slope |
| Annual seasonality | Yes/No | Peak SE, trough SE |
| Multi-year epidemic cycle | Yes/No | Approximate period |
| Structural breaks | Yes/No | Dates and likely causes |
| Missing data | Yes/No | Periods and imputation strategy |
| Variance heterogeneity | Yes/No | Transformation needed (log, sqrt) |
| Notification delay | Yes/No | Nowcast correction applied? |

This summary determines which modeling skill to use next.

## Examples

### Example 1: Exploring a municipal dengue series from InfoDengue

User says: "I have weekly dengue case counts from InfoDengue for São Paulo from 2010 to 2023. How do I start?"

Actions:
1. Convert data to `ts` object with `frequency=52`, `start=c(2010,1)`.
2. `autoplot()` → identify peaks in SE 8-12 (Feb-Mar) annually; note 2015-16 and 2019-2022 unusually high.
3. `ggseasonplot()` → confirm most years peak in SE 8-12; note 2019 and 2022 as epidemic outlier years.
4. `ggAcf(lag.max=104)` → strong ACF at lags 1-8, seasonal spike at lag 52, slow decay confirms non-stationarity.
5. Apply `log1p()` transformation → stabilizes variance; re-examine ACF.
6. Document: trend=upward, seasonality=annual SE 5-15 peak, epidemic cycles visible, log transformation recommended.

Result: Structured exploratory report ready to select between ETS (fpp2-dengue-ets-smoothing), ARIMA (fpp2-dengue-arima), or regression models.

### Example 2: Comparing dengue seasonality between two municipalities

User says: "I want to compare the seasonal pattern of dengue between Recife (tropical) and Porto Alegre (subtropical)."

Actions:
1. Create two `ts` objects aligned in time.
2. `ggseasonplot()` for each → Recife: broad peak Feb-May (tropical summer); Porto Alegre: sharp peak Dec-Mar with some years no peak.
3. `ggsubseriesplot()` → shows mean case count per SE, highlights which weeks are most dangerous.
4. Recommend: separate forecasting models per city — same model class may work, but seasonal parameters will differ substantially.

Result: Visualization-driven insight about geographic heterogeneity for multi-municipality forecasting.

### Example 3: Detecting a reporting anomaly

User says: "My dengue series has a sudden drop in cases in mid-2020. Is this real?"

Actions:
1. `autoplot()` → sharp dip in SE 15-30 of 2020.
2. Cross-reference with COVID-19 onset: reporting collapse during peak COVID period due to healthcare system overload and reduced dengue testing.
3. Flag as structural break / reporting artifact — do NOT model as true epidemic trough.
4. Apply `na.interp()` or manually set 2020 as missing for training purposes; warn forecasting model about this anomaly.

Result: Structural break identified, anomalous period flagged for exclusion from model training.

## Troubleshooting

### `ts()` object has wrong frequency
Cause: Epidemiological weeks don't align perfectly with 52/year (53rd week exists some years).
Solution: Use `zoo` or `tsibble` package for irregular time indexes; or aggregate to monthly (12 observations/year) to avoid the 52 vs 53 week issue.

### Seasonal plot shows inconsistent peaks across years
Cause: Epidemic cycles cause some years to have no outbreak; `ggseasonplot()` shows near-zero lines for off-epidemic years.
Solution: This is epidemiologically meaningful. Flag non-epidemic years separately. Consider modeling on log scale to reduce contrast. Use `ggseasonplot(polar=FALSE)` to see crossings more clearly.

### ACF does not decay — series appears non-stationary
Cause: Upward trend or unit root makes the series non-stationary.
Solution: Apply `log1p()` transformation first; then difference once (`diff(dengue_ts)`) and re-examine ACF. If seasonal differencing needed (lag 52), apply `diff(dengue_ts, lag=52)`. Proceed to fpp2-dengue-arima for formal stationarity tests.
