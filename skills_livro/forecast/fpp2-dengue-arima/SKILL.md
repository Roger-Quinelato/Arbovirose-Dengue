---
name: fpp2-dengue-arima
description: "Applies ARIMA, SARIMA, and stationarity testing principles from Forecasting Principles and Practice (Hyndman & Athanasopoulos, Ch.8) to dengue arbovirose forecasting. Use when fitting ARIMA or SARIMA models to dengue case series, testing for stationarity, applying differencing, using auto.arima for model selection, or analyzing the ACF/PACF structure of epidemiological time series. Trigger phrases: 'fit ARIMA to dengue cases', 'SARIMA for seasonal dengue data', 'auto.arima dengue', 'stationarity test dengue', 'ACF PACF interpretation epidemiological', 'differencing dengue series', 'seasonal ARIMA dengue forecast', 'Box-Jenkins dengue'. Do NOT use for exponential smoothing (use fpp2-dengue-ets-smoothing), regression with climate covariates (use fpp2-dengue-regression-dynamic), count-specific models (use fpp2-dengue-count-models), or hierarchical forecasting (use fpp2-dengue-hierarchical)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue ARIMA and SARIMA Models

Guides specification, fitting, and validation of ARIMA and SARIMA models for dengue arbovirose forecasting — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.8. Covers the Box-Jenkins methodology adapted for epidemic count series, from stationarity testing to model selection and probabilistic forecast generation.

## Instructions

### Step 1: Test for Stationarity

ARIMA requires a stationary series. Dengue case series are typically non-stationary due to trend and seasonality.

```r
library(fpp2)
library(tseries)

# Visual check: ACF decays slowly → non-stationary
ggAcf(log1p(dengue_ts), lag.max = 104)

# Formal tests on log-transformed series
adf.test(log1p(dengue_ts))   # Augmented Dickey-Fuller: p < 0.05 → stationary
kpss.test(log1p(dengue_ts))  # KPSS: p > 0.05 → stationary (null = stationary)
```

**Typical findings for dengue series**:
- Raw case counts: non-stationary (ADF fails to reject unit root; KPSS rejects stationarity).
- log1p-transformed: often still non-stationary (trend remains).
- After first difference of log: often stationary for trend-stationary series.
- After first + seasonal difference (lag 52): stationary for trend+seasonal non-stationary series.

**Decision rule**:
```
ndiffs(log1p(dengue_ts))     # number of non-seasonal differences needed (typically 1)
nsdiffs(log1p(dengue_ts))    # number of seasonal differences needed (typically 0 or 1)
```

### Step 2: Apply Differencing

```r
# First difference (removes trend)
dengue_diff1 <- diff(log1p(dengue_ts), lag=1)

# Seasonal difference at lag 52 (removes annual pattern)
dengue_diff52 <- diff(log1p(dengue_ts), lag=52)

# Both: first + seasonal difference (d=1, D=1 in SARIMA)
dengue_diff_both <- diff(diff(log1p(dengue_ts), lag=52), lag=1)

# Verify stationarity after differencing
adf.test(dengue_diff_both)  # Should reject unit root now
```

**Practical advice for dengue**: avoid over-differencing. One seasonal difference (lag=52) is usually sufficient for weekly dengue data with annual seasonality. Adding a first difference too (d=1, D=1) can cause over-differencing and inflate variance. Use `ndiffs()` and `nsdiffs()` to decide.

### Step 3: Read ACF and PACF for Model Order

After achieving stationarity, plot ACF and PACF to identify SARIMA(p,d,q)(P,D,Q)[52] orders:

```r
ggtsdisplay(dengue_diff_both, lag.max=104,
            main="ACF and PACF: Differenced dengue series")
```

**Interpretation guide for dengue**:

Non-seasonal components (lags 1-4 weeks):
- ACF cuts off at lag q, PACF tails off → MA(q) for the epidemic short-term autocorrelation.
- ACF tails off, PACF cuts off at lag p → AR(p) for case-count momentum.
- Typical dengue: ARIMA(2,1,0) or ARIMA(1,1,1) captures 1-2 week epidemic momentum.

Seasonal components (lags at multiples of 52):
- Spike at lag 52 in ACF, not at 104 → SMA(1): Q=1.
- Spike at lag 52 in PACF, not at 104 → SAR(1): P=1.
- Typical dengue: SARIMA(1,1,1)(1,1,1)[52] or (2,1,0)(0,1,1)[52].

### Step 4: Fit SARIMA Using auto.arima

Automatic model selection using AICc:

```r
# auto.arima with stepwise=FALSE does exhaustive search (slower but better)
model_sarima <- auto.arima(log1p(dengue_ts),
                            seasonal = TRUE,
                            stepwise = FALSE,      # exhaustive search
                            approximation = FALSE, # exact likelihood
                            max.p = 3, max.q = 3,
                            max.P = 2, max.Q = 2,
                            max.d = 1, max.D = 1,
                            lambda = NULL)         # already log-transformed

summary(model_sarima)
# Shows: SARIMA(p,d,q)(P,D,Q)[52] specification
# AICc: information criterion for model comparison
# sigma^2: residual variance estimate
```

**Manual override when auto.arima fails**:
```r
# Force specific SARIMA order based on ACF/PACF reading
model_sarima_manual <- Arima(log1p(dengue_ts),
                              order = c(2, 1, 0),
                              seasonal = list(order = c(1, 1, 0), period = 52),
                              include.constant = FALSE)
```

### Step 5: Validate the Model

```r
# Residual diagnostics
checkresiduals(model_sarima)
# Expected: white noise residuals, no significant ACF, approximately normal histogram

# Ljung-Box on residuals (correct df = lags - p - q - P - Q)
K <- sum(arimaorder(model_sarima))  # total parameters
Box.test(residuals(model_sarima), lag=2*52, fitdf=K, type="Ljung-Box")
# p > 0.05 required

# Compare models by AICc
AIC(model_sarima, k=log(length(dengue_ts)))  # BIC
```

**Common issues with dengue SARIMA validation**:
- Remaining spike at lag 1 in residual ACF: add MA(1) term (q=1).
- Remaining spike at lag 52 in residual ACF: missing seasonal difference or Q=0 → try Q=1.
- Non-normal residuals (heavy right tail): overdispersion — consider negative binomial model (see fpp2-dengue-count-models) or increase log-transformation aggressiveness.

### Step 6: Generate Probabilistic Forecasts

```r
# Generate 12-week ahead forecast with prediction intervals
fc_sarima <- forecast(model_sarima, h=12, level=c(80, 95))

# Back-transform to original scale
fc_cases <- fc_sarima
fc_cases$mean  <- expm1(fc_sarima$mean)
fc_cases$lower <- expm1(fc_sarima$lower)
fc_cases$upper <- expm1(fc_sarima$upper)

autoplot(fc_cases) +
  ggtitle("SARIMA Dengue Forecast: 12-week horizon") +
  xlab("Epidemiological Week") + ylab("Estimated Cases")
```

**Interpreting dengue SARIMA forecasts**:
- At forecast horizon h=1: SARIMA is usually very accurate (MASE near 0.3-0.5 vs. snaive).
- At h=4 weeks: MASE rises to 0.6-0.9; still usually beats snaive.
- At h=8-12 weeks: MASE often > 1 — SARIMA struggles at longer horizons for dengue (epidemic trajectory depends on susceptible population dynamics beyond ARIMA's scope).
- **SARIMA is best for 1-4 week ahead operational forecasts**, not for seasonal or epidemic-cycle planning.

### Step 7: SARIMA vs. ETS — When to Choose Which

| Criterion | SARIMA | ETS |
|---|---|---|
| Probabilistic foundations | Strong (Gaussian likelihood) | Strong (state-space) |
| Handles non-stationarity | Yes (differencing) | Yes (trend component) |
| Seasonal adaptation | Via seasonal differencing + SAR/SMA | Via gamma parameter |
| Multi-step forecast uncertainty | Can grow too slowly (over-confident) | More honest uncertainty growth |
| Interpretability | ACF/PACF structure | Level/trend/seasonal smoothing |
| Automation across many series | `auto.arima()` (slower) | `ets()` (faster) |
| Best for dengue short-term | 1-4 weeks | 4-8 weeks |

**In practice**: run both `auto.arima()` and `ets()` and select by AICc. For dengue, ETS often outperforms SARIMA at medium horizons because the state-space form handles the non-Gaussian nature of count data more gracefully after log transformation.

## Examples

### Example 1: Fitting SARIMA to weekly dengue data step-by-step

User says: "Walk me through fitting a SARIMA model to my weekly dengue series."

Actions:
1. Transform: `log1p(dengue_ts)`.
2. `ndiffs()=1`, `nsdiffs()=1` → SARIMA with d=1, D=1 at period=52.
3. `ggtsdisplay(diff(diff(log1p(ts), 52)))` → ACF spike at lag 1 → q=1; PACF spike at lag 52 → P=1.
4. Fit: `Arima(log1p(dengue_ts), order=c(0,1,1), seasonal=c(1,1,0))`.
5. `checkresiduals()` → white noise confirmed (Ljung-Box p=0.23).
6. Forecast 8 weeks, back-transform.

Result: SARIMA(0,1,1)(1,1,0)[52] fitted and validated for weekly dengue series.

### Example 2: SARIMA for dengue nowcasting (lag-corrected data)

User says: "I'm forecasting dengue for the current week (t=0) using nowcast data. Does SARIMA work?"

Actions:
1. Confirm: nowcast-corrected series from InfoDengue uses the corrected case counts up to the current week.
2. The final period's nowcasted value is uncertain — include it but set wide uncertainty for the most recent observation.
3. Use `Arima()` with fixed parameters estimated on historical data; apply to nowcast series.
4. The 1-step-ahead SARIMA forecast is effectively nowcasting t+1.

Result: SARIMA applied to nowcast-corrected InfoDengue series with appropriate uncertainty propagation.

### Example 3: Comparing auto.arima selections across municipalities

User says: "I ran auto.arima on 50 municipalities. Some got SARIMA(2,1,2)(1,1,1)[52] and others got SARIMA(0,1,0)(0,0,0)[52]. Is this right?"

Actions:
1. Municipalities with SARIMA(0,1,0)(0,0,0) are likely small with very sparse/noisy data — auto.arima correctly identifies that no complex structure is discernible.
2. Large municipalities with consistent epidemic patterns get richer SARIMA structures.
3. Do not force the same SARIMA order on all municipalities — heterogeneity in model order is epidemiologically appropriate.
4. Consider: municipalities with SARIMA(0,1,0) may benefit more from pooling/hierarchical approaches (see fpp2-dengue-hierarchical).

Result: Heterogeneous SARIMA orders confirmed as appropriate for spatially heterogeneous dengue dynamics.

## Troubleshooting

### auto.arima takes too long for many municipalities
Cause: `stepwise=FALSE, approximation=FALSE` on weekly data with 52-period seasonality is computationally expensive.
Solution: Use `stepwise=TRUE` for initial exploration; apply `stepwise=FALSE` only for the final model. Alternatively, use `parallel=TRUE` via the `parallel` package, or switch to `ets()` which is faster.

### SARIMA residuals have large spike at lag 1
Cause: The epidemic momentum (cases at t strongly predict t+1) is not captured — p or q is too small.
Solution: Increase q (add MA term) or p (add AR term). Try `Arima(x, order=c(2,1,1), ...)`. Also check if the data has been over-differenced (d=1 and D=1 both active when only one is needed).

### Forecast explodes after epidemic peak (unbounded growth)
Cause: AR component captures epidemic growth but has no damping mechanism; long-horizon extrapolation grows without bound.
Solution: (a) Use a damped ETS model instead; (b) Shorten forecast horizon to max 4 weeks; (c) Apply post-processing: cap forecasts at 2x historical maximum for the same epidemiological week.
