---
name: fpp2-dengue-count-models
description: "Applies advanced count time series models, forecast combination, and practical solutions from Forecasting Principles and Practice (Hyndman & Athanasopoulos, FPP2 Ch.11-12) to dengue arbovirose surveillance. Use when modeling dengue as discrete non-negative counts (Poisson, Negative Binomial, INGARCH), combining multiple dengue forecast models into an ensemble, handling zero-inflated inter-epidemic periods, applying NNAR for non-linear dynamics, or dealing with missing data and notification lags in dengue surveillance. Trigger phrases: 'Poisson model dengue', 'negative binomial dengue', 'zero-inflated dengue', 'ensemble dengue forecasts', 'combine dengue models', 'neural network dengue forecast', 'overdispersion dengue cases', 'count time series dengue', 'missing data dengue', 'nowcast correction dengue'. Do NOT use for ETS (use fpp2-dengue-ets-smoothing), ARIMA (use fpp2-dengue-arima), or hierarchical forecasting (use fpp2-dengue-hierarchical)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue Count Models and Forecast Combination

Guides advanced dengue forecasting using count-specific models, forecast ensembles, and solutions to practical data challenges — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.11-12. Covers Poisson/Negative Binomial time series, zero-inflation, neural network forecasts, ensemble methods, and practical data quality issues specific to dengue surveillance.

## Instructions

### Step 1: Diagnose Count Data Problems

Standard ARIMA and ETS are designed for continuous data. Dengue case counts are discrete, non-negative, and often overdispersed — requiring specialized treatment.

**Diagnose before modeling**:

```r
# Overdispersion test: Variance >> Mean indicates negative binomial is needed
var(dengue_cases) / mean(dengue_cases)
# Ratio >> 1: overdispersed (Negative Binomial)
# Ratio ≈ 1: equidispersed (Poisson may suffice)
# Typical dengue: ratio = 5-50x → strongly overdispersed

# Proportion of zeros (inter-epidemic periods)
mean(dengue_cases == 0)
# > 20%: consider zero-inflated models

# Plot distribution
hist(dengue_cases, breaks=50, main="Distribution of weekly dengue cases")
```

**Decision guide**:

| Observed pattern | Model family |
|---|---|
| Cases > 50/week, overdispersed | log-transformed Gaussian (ARIMA/ETS on log1p) |
| Cases 1-50/week, Poisson-like | INGARCH (Integer-valued GARCH) |
| Cases < 10/week, many zeros | Zero-inflated Poisson or NB |
| Many zero weeks + periodic outbreaks | Hurdle NB model |
| Small municipality, sparse data | Aggregation to regional level; pool with similar municipalities |

### Step 2: Fit Count Time Series Models

**INGARCH (Integer-valued Generalized ARCH)** — designed for count time series:

```r
library(tscount)

# Poisson INGARCH(1,1) — Poisson regression with lagged counts
model_ingarch <- tsglm(dengue_cases,
                       model = list(past_obs = 1, past_mean = 1),
                       distr = "poisson",
                       link = "log")

# Negative Binomial INGARCH for overdispersed dengue
model_ingarch_nb <- tsglm(dengue_cases,
                           model = list(past_obs = 1, past_mean = 1),
                           distr = "nbinom",
                           link = "log")

summary(model_ingarch_nb)
# Dispersion parameter: if size → ∞, converges to Poisson; small size → high overdispersion

# Add seasonal Fourier terms as external regressors
fourier_xreg <- fourier(ts(dengue_cases, frequency=52), K=3)
model_ingarch_seasonal <- tsglm(dengue_cases,
                                 model = list(past_obs = 1:2, past_mean = 1),
                                 distr = "nbinom",
                                 link = "log",
                                 xreg = fourier_xreg[1:length(dengue_cases), ])
```

**Zero-inflated Negative Binomial** for municipalities with inter-epidemic periods:

```r
library(pscl)

# Zero-inflated NB: mixture of zero-mass and NB count process
model_zinb <- zeroinfl(cases ~ fourier_s1 + fourier_c1 + lag_cases | 1,
                        data = dengue_df,
                        dist = "negbin")
# count model: predicts magnitude of outbreak
# zero model: predicts probability of being in a zero-endemic state
```

### Step 3: Apply Neural Network Forecasting (NNAR)

For capturing non-linear relationships in dengue dynamics (e.g., non-linear temperature-transmission relationship, immune memory effects):

```r
# Neural Network Autoregression (NNAR) from fpp2
# Inputs: lagged values of dengue + seasonal pattern
# Architecture: NNAR(p, P, k)[m] where p=non-seasonal lags, P=seasonal lags, k=hidden nodes, m=period

model_nnar <- nnetar(log1p(dengue_ts),
                     p = 4,      # 4 recent weeks
                     P = 1,      # 1 seasonal lag (52 weeks ago)
                     size = 10,  # 10 hidden nodes
                     repeats = 30) # average over 30 random initializations

fc_nnar <- forecast(model_nnar, h=4, PI=TRUE, npaths=1000)
fc_original <- expm1(fc_nnar$mean)
```

**NNAR strengths for dengue**:
- Captures non-linear lagged effects (e.g., temperature at 28°C vs. 32°C has disproportionately different effects on EIP).
- Handles multi-year epidemic cycles through multiple autoregressive lags.
- Does not require stationarity assumptions.

**NNAR weaknesses**:
- Black box — cannot interpret which drivers are most important.
- Requires more data (recommend minimum 5-7 years of weekly data).
- High variance across random initializations → use `repeats=30` and average.
- Prediction intervals via simulation (bootstrap) are expensive.

**Adding climate covariates to NNAR**:
```r
# External regressors in NNAR
xreg_matrix <- cbind(temp_lag3, rain_lag3, fourier(dengue_ts, K=2))
model_nnar_x <- nnetar(log1p(dengue_ts), xreg=xreg_matrix[train_idx,], p=4, P=1)
fc_nnar_x <- forecast(model_nnar_x,
                       xreg=xreg_matrix[test_idx,],
                       h=4, PI=TRUE, npaths=500)
```

### Step 4: Build a Forecast Ensemble

No single model consistently dominates for dengue across all municipalities, years, and horizons. Combining models (ensemble) typically reduces error:

**Simple combination methods**:

```r
# Equal-weight ensemble (often surprisingly competitive)
fc_mean <- (fc_sarima$mean + fc_ets$mean + fc_nnar$mean) / 3

# Optimal weights minimizing MSFE on validation set
# Find weights w1, w2, w3 such that MSE(w1*f1 + w2*f2 + w3*f3) is minimized
library(quadprog)

errors <- cbind(
  sarima = test_values - fc_sarima_val$mean,
  ets    = test_values - fc_ets_val$mean,
  nnar   = test_values - fc_nnar_val$mean
)
# Solve: minimize trace(W'*Sigma*W) subject to sum(W)=1, W>=0
# Use quadprog::solve.QP()
```

**Practical guidance for dengue ensemble**:

| Method | Composition | Best use |
|---|---|---|
| Equal-weight mean | SARIMA + ETS + snaive | Default; robust to individual model failures |
| Performance-weighted | Weights by inverse MASE from validation | When some models clearly dominate |
| Bayesian Model Average (BMA) | Weights by model posterior probability | When uncertainty quantification is critical |
| Stacked ensemble | Meta-model learns optimal combination | Large dataset; enough validation data |

For dengue, the **equal-weight ensemble of SARIMA + ETS + snaive** is the recommended default due to its robustness to individual model misspecification during atypical epidemic years.

```r
# Practical ensemble with prediction intervals
fc_ensemble_mean <- (fc_sarima$mean + fc_ets$mean + fc_snaive$mean) / 3

# For intervals: use the widest interval (conservative) or combine variances
fc_var_combined <- (fc_sarima$model$sigma2 + fc_ets$model$sigma2) / 2
fc_se <- sqrt(fc_var_combined)
fc_lower_80 <- fc_ensemble_mean - qnorm(0.9) * fc_se
fc_upper_80 <- fc_ensemble_mean + qnorm(0.9) * fc_se
```

### Step 5: Handle Practical Data Quality Issues

**Missing data in dengue surveillance**:

```r
library(imputeTS)

# Visualize missing pattern
ggplot_na_distribution(dengue_ts)

# Interpolation options:
# Structural missing (COVID reporting collapse 2020): treat as structural break
dengue_cleaned <- na_seadec(dengue_ts, algorithm="interpolation", find_frequency=TRUE)
# na_seadec: decomposes, imputes on deseasoned series, reseasonalizes

# For small gaps (1-3 weeks): linear interpolation is fine
dengue_interp <- na.interp(dengue_ts)
```

**Notification lag correction (nowcasting)**:

Dengue cases are notified with 1-4 week delay. The most recent weeks systematically under-report. Apply a nowcast correction before forecasting:

```r
# Simple nowcast correction: multiply recent weeks by historical correction factors
# correction_factor[lag] = mean(final_count[t] / provisional_count[t, lag])
correction_factors <- c(1.0, 1.15, 1.30, 1.45)  # for lags 0,1,2,3 weeks respectively

nowcast_corrected <- dengue_ts
nowcast_corrected[T]   <- dengue_ts[T]   * correction_factors[1]
nowcast_corrected[T-1] <- dengue_ts[T-1] * correction_factors[2]
nowcast_corrected[T-2] <- dengue_ts[T-2] * correction_factors[3]
nowcast_corrected[T-3] <- dengue_ts[T-3] * correction_factors[4]
```

**Epidemic outlier years** (2019, 2022-23 for dengue):

```r
# Outlier detection using IQR on seasonal residuals
stl_residuals <- dengue_stl$time.series[,"remainder"]
outlier_threshold <- 3 * IQR(stl_residuals)
outlier_weeks <- which(abs(stl_residuals) > outlier_threshold)

# Robust forecasting: fit model excluding outlier years; use as training set
dengue_robust <- dengue_ts
dengue_robust[outlier_weeks] <- NA  # treat as missing
model_robust <- auto.arima(dengue_robust, ...)
```

### Step 6: Practical Forecast Pipeline Summary

The complete dengue forecasting pipeline combining all skills:

```
1. [fpp2-dengue-tseries-exploration]
   → Load, clean, explore, transform (log1p), identify patterns

2. [fpp2-dengue-accuracy-benchmarks]
   → Define snaive benchmark, Box-Cox, residual diagnostic protocol, WIS metric

3. Modeling (choose ≥2, ensemble):
   → [fpp2-dengue-ets-smoothing]     STL+ETS, Holt-Winters
   → [fpp2-dengue-arima]             SARIMA auto.arima
   → [fpp2-dengue-regression-dynamic] ARIMAX with climate (rainfall, temp)
   → [fpp2-dengue-count-models]      INGARCH-NB + NNAR

4. [fpp2-dengue-count-models]
   → Combine: equal-weight ensemble of top 2-3 models

5. [fpp2-dengue-hierarchical]
   → Reconcile across municipality → state → national (MinT)

6. Evaluation:
   → [fpp2-dengue-accuracy-benchmarks]
   → MASE vs. snaive, WIS, coverage of prediction intervals
   → Report segmented: epidemic weeks vs. inter-epidemic weeks
```

## Examples

### Example 1: Negative Binomial INGARCH for a small city with sparse dengue

User says: "My municipality has weekly dengue counts ranging from 0 to 35. ETS is predicting negative values during low periods."

Actions:
1. Overdispersion ratio: `var/mean` = 18 → strongly overdispersed; Poisson inadequate.
2. Zero proportion = 35% → zero-inflated period present but not extreme; NB-INGARCH likely sufficient.
3. Fit `tsglm(cases, model=list(past_obs=1:2, past_mean=1), distr="nbinom", link="log")`.
4. Check: `plot(predict(model), cases)` — no negative predictions; zeros during inter-epidemic plausibly modeled.
5. Compare AICc to log-transformed ETS: INGARCH-NB wins for this sparse series.

Result: NB-INGARCH replaces log-normal ETS for sparse count series, eliminating negative predictions.

### Example 2: Equal-weight ensemble beats all individual models

User says: "My SARIMA gets MASE=0.72, ETS gets 0.68, snaive gets 1.00. What if I combine them?"

Actions:
1. Equal-weight ensemble: `(fc_sarima + fc_ets + fc_snaive) / 3`.
2. Evaluate: MASE = 0.61 — better than either individual model.
3. Explanation: different models capture different aspects (SARIMA: short-term autocorrelation; ETS: trend and seasonal smoothing; snaive: seasonal anchor). Errors partially cancel.
4. Add NNAR: if NNAR MASE < 0.85, include in ensemble; otherwise exclude (it would add noise not signal).

Result: 3-model ensemble with MASE=0.61 adopted as the production dengue forecasting system.

### Example 3: Handling the COVID-19 reporting collapse in dengue data

User says: "My dengue data has a huge dip in March-October 2020 that I know is a reporting artifact from COVID. How do I handle it?"

Actions:
1. Set SE 12-44 of 2020 as `NA` in the training series.
2. Use `na.interp()` with seasonal interpolation to fill the gap for model fitting purposes.
3. OR: exclude 2020 entirely from training and assess whether 2021-2024 data alone is sufficient.
4. Add `level_shift_2020 = ifelse(year==2020 & SE>=12 & SE<=44, 1, 0)` as an intervention dummy in dynamic regression.
5. Monitor: 2021 post-COVID rebound may show structural increase in cases as delayed dengue cohorts susceptibility accumulated.

Result: COVID-induced reporting artifact handled systematically; model trained on clean pre-pandemic data with appropriate 2020 exclusion.

## Troubleshooting

### INGARCH fails to converge
Cause: Sparse data or extreme values destabilize the log-link optimization.
Solution: Start with `model=list(past_obs=1)` (simpler INGARCH(1,0)); increase complexity once baseline converges. Use `init.control = list(...)` to set better starting values. Try Poisson first; if it converges, use the Poisson estimates as starting values for NB.

### NNAR forecast interval is very wide
Cause: Bootstrap simulation of NNAR prediction intervals has high variance, especially at longer horizons.
Solution: Use `npaths=1000` for more stable intervals. Alternatively, combine NNAR point forecast with SARIMA or ETS prediction intervals (use NNAR for the central forecast, SARIMA for the uncertainty bands).

### Ensemble is worse than the best individual model
Cause: One model is dramatically better than others — including weak models in the ensemble dilutes the ensemble quality.
Solution: Use performance-weighted ensemble (inverse MASE weights from validation set). Exclude any model with MASE > 1.2 from the ensemble. Only combine models that each individually beat snaive (MASE < 1.0).
