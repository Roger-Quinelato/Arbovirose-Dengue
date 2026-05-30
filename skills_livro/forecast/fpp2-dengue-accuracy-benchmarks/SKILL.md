---
name: fpp2-dengue-accuracy-benchmarks
description: "Applies forecast accuracy evaluation, benchmark methods, residual diagnostics, and transformation principles from Forecasting Principles and Practice (Hyndman & Athanasopoulos, Ch.3) to dengue arbovirose forecasting. Use when evaluating forecast model quality, computing accuracy metrics (MAE, RMSE, MASE, MAPE, WIS), performing residual diagnostics, selecting between benchmark and complex models, or validating dengue forecasts against held-out data. Trigger phrases: 'evaluate dengue forecast accuracy', 'which error metric for dengue cases', 'residual diagnostics for epidemiological forecast', 'compare dengue models', 'is my dengue model better than naive baseline', 'cross-validation for epidemic time series', 'MASE vs MAPE for count data', 'Box-Cox transformation for case counts'. Do NOT use for initial data exploration (use fpp2-dengue-tseries-exploration), model specification (use fpp2-dengue-ets-smoothing or fpp2-dengue-arima), or hierarchical evaluation (use fpp2-dengue-hierarchical)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue Forecast Accuracy and Benchmarks

Guides evaluation of dengue forecasting models using proper benchmark methods, accuracy metrics, residual diagnostics, and time-series cross-validation — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.3. Ensures that any proposed model demonstrably improves over naive baselines appropriate for epidemic data.

## Instructions

### Step 1: Establish the Right Benchmark

Never evaluate a model in isolation — always compare against a naive baseline. For dengue:

**Naive method**: forecast = last observed value. Appropriate for very short horizons (1-2 weeks) during stable epidemic growth.
```r
fc_naive <- naive(train_dengue, h = forecast_horizon)
```

**Seasonal Naive (snaive)**: forecast = same week last year. The natural default for dengue given strong annual seasonality. This is the minimum bar any model must beat.
```r
fc_snaive <- snaive(train_dengue, h = forecast_horizon)
```

**Mean method**: forecast = historical mean. Only relevant as a baseline for very low-incidence periods.

**Drift method**: extrapolates the trend from first to last observation. Useful benchmark for growing epidemics (rising limb of outbreak curve).
```r
fc_drift <- rwf(train_dengue, drift = TRUE, h = forecast_horizon)
```

For dengue specifically: **seasonal naive is the primary benchmark**. Any model must beat it across multiple evaluation windows to be considered useful. Many complex models fail to consistently beat snaive for dengue.

### Step 2: Apply Box-Cox Transformations

Dengue case counts are typically right-skewed with variance that grows with the mean (overdispersion). Transformation before modeling stabilizes variance and often improves forecast quality.

**Recommended transformations for dengue counts**:

| Situation | Transformation | Code |
|---|---|---|
| Counts with zeros | log(cases + 1) = log1p | `log1p(cases)` |
| Variance growing with mean | Box-Cox (lambda ≈ 0.2-0.5) | `BoxCox(dengue_ts, lambda)` |
| Incidence rate (per 100k) | sqrt or Box-Cox | `sqrt(incidence)` |
| Forecasts on original scale | Back-transform + bias correction | `InvBoxCox(fc, lambda)` |

```r
# Automatic lambda selection
lambda <- BoxCox.lambda(dengue_ts)
# Fit on transformed series, back-transform forecasts
fc_ets_bc <- forecast(ets(BoxCox(dengue_ts, lambda)), h=12, lambda=lambda, biasadj=TRUE)
```

Bias adjustment (`biasadj=TRUE`) is important for count data: back-transformed median ≠ back-transformed mean. Use the mean for aggregations across municipalities.

### Step 3: Compute Accuracy Metrics Correctly

Use a held-out **test set** (not training residuals) to compute accuracy. Rule of thumb: hold out the last 1-2 epidemic seasons.

```r
accuracy(fc_model, test_dengue)
accuracy(fc_snaive, test_dengue)
```

**Metric selection guide for dengue**:

| Metric | Formula | Use when | Caution |
|---|---|---|---|
| MAE | mean(|e_t|) | Scale-dependent; same region comparison | Dominated by epidemic peaks |
| RMSE | sqrt(mean(e_t^2)) | Penalizes large errors heavily | Very sensitive to outbreak peak misses |
| MAPE | mean(|e_t/y_t| * 100) | Scale-free percentage | UNDEFINED when y_t = 0 (inter-epidemic zeros!) |
| sMAPE | mean(|e_t|/((|y_t|+|yhat_t|)/2)) | Symmetric version | Still problematic near zero |
| MASE | MAE / MAE_snaive | Scale-free, compares to snaive | Recommended for dengue (handles zeros) |
| WIS | Weighted Interval Score | Probabilistic forecasts | Required for forecast hub submissions |

**For dengue: use MASE as the primary accuracy metric.** Avoid MAPE because inter-epidemic periods with near-zero cases cause division-by-zero. MASE < 1 means the model beats seasonal naive.

**Probabilistic accuracy** (for prediction intervals):
- **Coverage**: what fraction of true values fall within the stated interval? An 80% PI should cover 80% of true values.
- **Sharpness**: narrower intervals are better, conditional on correct coverage (sharp but miscalibrated intervals are worse than wide but calibrated ones).
- **WIS (Weighted Interval Score)**: proper scoring rule for probabilistic forecasts, required by RedeInfoDengue and Brazilian Dengue Forecast Hub.

```python
# Python: WIS calculation for probabilistic dengue forecasts
def wis(y_true, quantile_forecasts, quantile_levels, weights=None):
    """
    y_true: scalar observed value
    quantile_forecasts: array of forecasted quantiles
    quantile_levels: array of alpha levels (e.g., [0.025, 0.1, ..., 0.975])
    """
    scores = []
    for q, alpha in zip(quantile_forecasts, quantile_levels):
        indicator = float(y_true < q)
        scores.append(2 * (indicator - alpha) * (q - y_true))
    return np.mean(scores) if weights is None else np.average(scores, weights=weights)
```

### Step 4: Perform Residual Diagnostics

After fitting any model, check that residuals are well-behaved:

```r
checkresiduals(model_fit)
```

This produces automatically: time plot of residuals, ACF of residuals, histogram of residuals, and Ljung-Box test.

**Residual criteria for dengue models**:

1. **Uncorrelated residuals**: ACF of residuals should show no significant spikes. Significant spikes at lags 1-4 indicate the model is missing short-term epidemic autocorrelation. Significant spike at lag 52 indicates unmodeled annual seasonality.
2. **Zero-mean residuals**: systematic bias — model is consistently over- or under-forecasting. Often occurs at epidemic peaks (models under-predict) and troughs (models over-predict).
3. **Constant variance**: dengue residuals rarely have constant variance. Log transformation helps. If variance still grows with fitted values, consider negative binomial or Poisson-based models (see fpp2-dengue-count-models).
4. **Near-normal distribution**: residuals from log-transformed series should be approximately normal. Heavy right tail indicates remaining overdispersion.

**Ljung-Box test** for residual autocorrelation:
```r
# For non-seasonal model:
Box.test(residuals(model), lag=10, fitdf=0, type="Ljung-Box")
# For seasonal model (frequency=52):
Box.test(residuals(model), lag=2*52, fitdf=K, type="Ljung-Box")
# p > 0.05: residuals resemble white noise (good)
```

### Step 5: Apply Time-Series Cross-Validation

Simple train/test split underestimates forecast uncertainty for epidemic data. Use rolling-origin (time-series cross-validation) instead:

```r
# Rolling-origin forecast evaluation for dengue
# Minimum training size: 3 years (3 epidemic cycles)
tsCV_results <- tsCV(dengue_ts,
                     forecastfunction = function(x, h) forecast(ets(x), h=h),
                     h = 4,           # 4-week ahead forecast
                     initial = 156)   # minimum 3 years = 156 weeks training

# RMSE across all rolling origins
sqrt(mean(tsCV_results^2, na.rm=TRUE))
```

**For dengue**: rolling-origin CV reveals that model accuracy degrades significantly as the forecast horizon grows from 1 to 4+ weeks, and that accuracy is much better in inter-epidemic periods than at epidemic peaks. Report accuracy separately for: (a) epidemic periods (weekly cases > threshold), (b) inter-epidemic periods.

**Epidemic-peak-specific evaluation**: create separate accuracy metrics for weeks within epidemic peaks:
```r
peak_threshold <- quantile(as.numeric(dengue_ts), 0.75)  # top quartile = epidemic weeks
epidemic_weeks <- which(as.numeric(dengue_ts) > peak_threshold)
# Compute MASE only on epidemic weeks
```

## Examples

### Example 1: Demonstrating that snaive beats a naive model for dengue

User says: "Should I use naive or seasonal naive as my baseline for dengue forecasting?"

Actions:
1. Fit both on training data (first 5 years).
2. `accuracy(naive(train), test)` → high MASE (much worse than seasonal naive).
3. `accuracy(snaive(train), test)` → MASE ≈ 0.8-1.2 depending on year.
4. Conclusion: snaive is clearly superior. Naive is inappropriate for strongly seasonal dengue data.
5. Any proposed model must achieve MASE < MASE(snaive) to be considered useful.

Result: Seasonal naive established as the proper benchmark; minimum performance bar defined.

### Example 2: Evaluating a model that fails at epidemic peaks

User says: "My ETS model has good overall MASE but public health officials say it misses the peaks."

Actions:
1. Plot forecasts against actuals: model systematically under-predicts the 4-week rising limb of outbreaks.
2. Compute MASE separately for epidemic weeks (cases > 75th percentile) vs. non-epidemic weeks.
3. Epidemic-week MASE: 1.8 (model is worse than snaive during peaks). Non-epidemic MASE: 0.6 (very good).
4. Implication: model is calibrated for average behavior, not for outbreak warnings. Recommend supplementing with a threshold exceedance model or using SEIR-inspired covariates.

Result: Segmented accuracy evaluation reveals systematic bias during the most operationally important period.

### Example 3: Selecting lambda for Box-Cox transformation

User says: "My dengue series has very large variance during epidemic years. How do I transform it?"

Actions:
1. `BoxCox.lambda(dengue_ts)` → returns lambda ≈ 0.18 (close to log transformation).
2. Use `lambda=0` (log) for simplicity and interpretability: `log1p(dengue_ts)`.
3. Fit ETS on log scale; back-transform with `biasadj=TRUE`.
4. Compare: RMSE on original scale with/without transformation. Transformation typically reduces RMSE by 20-40% for overdispersed series.

Result: log1p transformation adopted as standard preprocessing for dengue count series.

## Troubleshooting

### MAPE returns Inf or NaN for dengue data
Cause: Near-zero or zero case counts during inter-epidemic periods cause division by zero.
Solution: Switch to MASE (primary recommendation) or sMAPE. Never use MAPE for dengue case count series with zero observations.

### Residuals show significant ACF at lag 52
Cause: Annual seasonality is not fully captured by the model.
Solution: (a) Add seasonal differencing (SARIMA approach); (b) Use ETS model with seasonal component (Holt-Winters); (c) Add Fourier terms for seasonality in a regression model. See fpp2-dengue-ets-smoothing or fpp2-dengue-arima.

### Rolling-origin CV is extremely slow for 10+ years of weekly data
Cause: Re-fitting complex models (ARIMA, ETS) at hundreds of rolling origins is computationally expensive.
Solution: Fix model parameters estimated on full training data; use rolling-origin CV only to evaluate forecast distributions (not to re-estimate parameters). Or parallelize using `future` + `furrr` packages in R.
