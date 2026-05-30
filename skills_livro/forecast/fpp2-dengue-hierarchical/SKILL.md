---
name: fpp2-dengue-hierarchical
description: "Applies hierarchical and grouped time series forecasting (Hyndman & Athanasopoulos, FPP2 Ch.10) to dengue surveillance across geographic levels. Use when forecasting dengue at national/state/regional/municipal scales, reconciling coherent forecasts, applying bottom-up, top-down, or MinT optimal reconciliation methods. Trigger phrases: 'reconcile dengue forecasts across municipalities', 'hierarchical dengue forecasting', 'bottom-up vs top-down dengue', 'MinT reconciliation dengue', 'aggregate dengue from municipality to state', 'grouped dengue time series', 'coherent dengue forecasts Brasil'. Do NOT use for single-series ARIMA or ETS (use fpp2-dengue-arima or fpp2-dengue-ets-smoothing), climate regression (use fpp2-dengue-regression-dynamic), or count models (use fpp2-dengue-count-models)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue Hierarchical Forecasting

Guides hierarchical and grouped time series forecasting for dengue arbovirose surveillance, producing coherent forecasts across geographic and administrative aggregation levels — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.10. Covers bottom-up, top-down, middle-out, and optimal MinT reconciliation strategies in the Brazilian epidemiological surveillance context.

## Instructions

### Step 1: Define the Hierarchical Structure for Brazilian Dengue Surveillance

Dengue surveillance in Brazil operates across multiple administrative levels:

```
Brasil (national)
├── Norte, Nordeste, Centro-Oeste, Sudeste, Sul (regiões)
│   ├── AM, RR, PA, ... (estados / UFs — 27)
│   │   ├── Regional de Saúde (RS) / Departamento Regional de Saúde (DRS)
│   │   │   ├── Município 1
│   │   │   ├── Município 2
│   │   │   └── Município N  (~5570 municípios total)
```

**Coherence constraint**: total forecasts at each level must equal the sum of component forecasts. Without reconciliation, independently-fitted models violate this constraint — the sum of municipal forecasts ≠ state forecast ≠ national forecast.

### Step 2: Structure the Hierarchical Time Series Object

```r
library(fpp2)
library(hts)    # hierarchical time series package

# Example: 3 states, each with 2-3 municipalities
# Weekly case counts (frequency=52)

# Bottom level: individual municipalities (already log-transformed or raw)
municipios_ts <- ts(municipios_matrix,
                    start = c(2015, 1),
                    frequency = 52)
# municipios_matrix: T rows x N columns (N = total municipalities)

# Create hierarchical structure
# node_structure: for each non-bottom level, how many children does each node have?
# Example: 2 states with (3, 2) municipalities respectively
dengue_hts <- hts(municipios_ts,
                  nodes = list(c(2),        # 1 national → 2 states
                               c(3, 2)))    # state 1 → 3 munic; state 2 → 2 munic

# Visualize hierarchy
plot(dengue_hts, levels = 0:2)
```

For grouped series (e.g., by serotype or age group across municipalities):
```r
# Grouped time series: cases by municipality AND serotype
dengue_gts <- gts(cases_matrix,
                  groups = list(municipality = muni_labels,
                                serotype = serotype_labels))
```

### Step 3: Choose the Reconciliation Strategy

**Bottom-Up (BU)**:
- Forecast at the lowest level (municipalities) independently; sum up to higher levels.
- Pros: captures local epidemic dynamics; no information loss.
- Cons: small municipalities have noisy, unreliable series; aggregation of errors.
- Best for: when municipal-level dynamics are the primary interest (outbreak detection).

**Top-Down (TD)**:
- Forecast at the national level; disaggregate using historical proportions.
- Pros: aggregate series is more stable and forecastable; top-level model is more reliable.
- Cons: historical proportions may not reflect current epidemic geography; does not detect emerging hotspots.
- Disaggregation methods:
  - **TD-prop (average historical proportions)**: proportion = mean(municipal share of national total across all weeks).
  - **TD-var (forecast proportions)**: forecast each proportion separately.
- Best for: resource allocation at national/regional level when municipal detail is less critical.

**Middle-Out (MO)**:
- Forecast at an intermediate level (e.g., state); disaggregate downward using proportions; sum upward.
- Best for: Brazilian dengue where state-level data is reliable and municipal data is noisy.
- Recommended level: **estado (UF)** — 27 series, individually reliable enough for SARIMA/ETS, but above the noise of individual municipalities.

**Optimal Reconciliation — MinT (Minimum Trace)**:
- Produce base forecasts at all levels; adjust all forecasts simultaneously to be coherent while minimizing total forecast error.
- Minimizes the trace of the forecast error covariance matrix.
- Pros: uses information from all levels; demonstrably outperforms BU and TD in most empirical studies.
- Cons: requires estimating a large covariance matrix (computationally expensive for many municipalities).
- Best for: when high accuracy is required at all levels simultaneously (national surveillance + municipal outbreak detection).

```r
# MinT reconciliation
# 1. Generate base forecasts for all levels
forecast_hts_mint <- forecast(dengue_hts,
                               h = 4,
                               method = "mint",
                               covariance = "shr")  # shrinkage estimator for cov matrix
# method options: "bu" (bottom-up), "tdgsa" (top-down), "mint"
# covariance options: "ols", "wls_var", "wls_struct", "mint_cov", "shr" (shrinkage - recommended)

# Extract reconciled forecasts at each level
fc_national <- aggts(forecast_hts_mint, levels = 0)  # level 0 = national
fc_states   <- aggts(forecast_hts_mint, levels = 1)  # level 1 = states
fc_munic    <- aggts(forecast_hts_mint, levels = 2)  # level 2 = municipalities
```

### Step 4: Select Base Forecast Models per Level

The quality of reconciled forecasts depends on the quality of base forecasts. Use appropriate models per level:

| Level | Series count | Recommended model | Rationale |
|---|---|---|---|
| National (total Brasil) | 1 | SARIMA or ETS with full history | Single stable series, use best model |
| Regional (5 regiões) | 5 | SARIMA(p,d,q)(P,D,Q)[52] | Reliable series, distinct seasonal profiles |
| State (UF) | 27 | auto.arima + ETS; compare AICc | Generally reliable, good sample size |
| Health Region (RS/DRS) | ~450 | ETS or STL+ETS | Moderate reliability |
| Municipality | ~5570 | snaive or ETS(A,N,A) | Noisy, sparse; complex models overfit |

```r
# Apply different models per level in hts
forecast_hts_custom <- forecast(dengue_hts,
                                 h = 4,
                                 method = "bu",
                                 fmethod = "ets")  # base method for all levels
# For custom per-level models: use hts::combinef() with pre-computed base forecasts
```

### Step 5: Evaluate Reconciled vs. Base Forecasts

```r
# Evaluate at each level using MASE vs. snaive
accuracy_hts <- accuracy(forecast_hts_mint, test_hts)

# Key metric: does MinT improve over bottom-up at all levels?
# Typical finding: MinT > BU at aggregate levels; BU > MinT at municipal level
# For dengue: MinT usually wins at national + state; BU wins for small municipalities
```

**Key insight for dengue**: MinT reconciliation is most beneficial at intermediate and aggregate levels. For the smallest municipalities (< 10 cases/year), bottom-up with snaive or a pooled model outperforms individually fitted complex models.

### Step 6: Epidemic Alert System from Hierarchical Forecasts

For public health operations, combine hierarchical forecasts into a multi-level alert system:

```r
# Threshold exceedance at each level
alert_threshold_state <- quantile(state_ts, 0.75)  # top quartile = yellow alert

# For each future week and each level:
# Green: forecast < 75th percentile historical
# Yellow: 75th–90th percentile
# Orange: 90th–95th percentile
# Red: > 95th percentile OR > epidemic threshold defined by PAHO/SINAN

classify_alert <- function(fc_mean, thresholds) {
  case_when(
    fc_mean < thresholds[1] ~ "green",
    fc_mean < thresholds[2] ~ "yellow",
    fc_mean < thresholds[3] ~ "orange",
    TRUE                    ~ "red"
  )
}
```

This produces a choropleth map with alert levels that updates weekly — the standard output format for Brazilian dengue surveillance dashboards (InfoDengue, AlertaDengue).

## Examples

### Example 1: Reconciling forecasts for São Paulo state municipalities

User says: "I forecast dengue for 645 municipalities in SP state and for SP state total, but the sums don't match. How do I fix this?"

Actions:
1. Create `hts()` object: 1 state total + 645 municipalities.
2. Fit base forecasts: ETS for state total (reliable); snaive for most small municipalities; ETS for large cities (São Paulo, Campinas, Santos, etc.).
3. Apply MinT reconciliation with shrinkage covariance (`covariance="shr"`).
4. Now: sum of reconciled municipal forecasts = reconciled state forecast (exactly).
5. Compare: MinT improves state-level MASE by ~15% over independently-fitted state model; municipal-level MASE within 5% of independently-fitted municipal models.

Result: Coherent forecast system where totals are internally consistent at all levels.

### Example 2: Top-down allocation of national dengue resources

User says: "We have a national dengue vaccine allocation forecast. How do we distribute the doses to states?"

Actions:
1. Generate national-level SARIMA forecast (most reliable).
2. Compute historical proportion: each state's share of national cases (average over last 3 years).
3. Weight by epidemic years more heavily (current year proportions may differ from stable-period proportions).
4. Apply top-down: `forecast(dengue_hts, method="tdgsa", h=12)`.
5. Validate: check if state forecasts are reasonable given local epidemic indicators (BI, temperature anomaly).

Result: National forecast disaggregated to states using historical epidemic geography, with alerts for states deviating from historical patterns.

### Example 3: Hierarchical forecasting with grouped serotype data

User says: "I want to forecast dengue cases broken down by DENV serotype (1-4) and by state simultaneously."

Actions:
1. Structure as grouped time series: `gts(cases_matrix, groups=list(state=..., serotype=...))`.
2. Base forecasts at each combination (state × serotype).
3. Reconcile: coherent at state level (sum of 4 serotypes = total state cases), at serotype level (sum of states = national serotype cases), and at national total.
4. Note: many serotype × state cells have near-zero counts — use Poisson-based base forecasts for sparse combinations.

Result: Multi-dimensional coherent forecast system enabling serotype-specific resource allocation by geography.

## Troubleshooting

### MinT covariance matrix is singular or poorly conditioned
Cause: Too many bottom-level series (thousands of municipalities) with short history → covariance matrix is under-determined.
Solution: Use shrinkage estimator (`covariance="shr"`) — it regularizes the covariance matrix. Alternatively, use WLS variant (`covariance="wls_var"`) which only uses the diagonal (no cross-series covariance). Or reduce hierarchy depth: aggregate municipalities to health regions before reconciling.

### Reconciled forecasts produce negative case count predictions
Cause: Reconciliation is applied on the original scale; MinT adjustments can push low-count series below zero.
Solution: Apply reconciliation on the log-transformed series; back-transform. Or post-process: `pmax(reconciled_fc, 0)`. For count data, consider reconciling on the square-root scale.

### Bottom-up produces higher aggregate error than top-down
Cause: Many small municipalities have very noisy, unpredictable series; aggregating noisy base forecasts amplifies total error.
Solution: Use MinT which borrows strength from aggregate levels to improve bottom-level forecasts. Or use middle-out at the health region level (aggregate small municipalities to RS first, then fit models at RS level, then disaggregate to municipalities).
