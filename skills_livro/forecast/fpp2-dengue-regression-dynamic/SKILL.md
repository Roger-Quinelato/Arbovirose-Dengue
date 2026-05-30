---
name: fpp2-dengue-regression-dynamic
description: "Applies regression and dynamic regression principles from Forecasting Principles and Practice (Hyndman & Athanasopoulos, Ch.5 and Ch.9) to dengue arbovirose forecasting with climate and entomological covariates. Use when adding temperature, rainfall, humidity, Breteau Index, or mosquito density as predictors of dengue cases; fitting ARIMAX or dynamic regression (regression with ARIMA errors); modeling intervention effects; forecasting with lagged climate covariates. Trigger phrases: 'include rainfall as predictor for dengue', 'temperature effect on dengue cases', 'dynamic regression dengue', 'ARIMAX dengue', 'lagged climate covariates dengue forecast', 'regression with ARIMA errors for dengue', 'Fourier terms for dengue seasonality', 'how to include covariates in ARIMA dengue'. Do NOT use for pure ARIMA without covariates (use fpp2-dengue-arima), pure ETS (use fpp2-dengue-ets-smoothing), hierarchical aggregation (use fpp2-dengue-hierarchical), or count-specific GLMs (use fpp2-dengue-count-models)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue Dynamic Regression with Climate Covariates

Guides construction of dynamic regression models that combine climate and entomological covariates with ARIMA error structures for dengue arbovirose forecasting — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.5 and Ch.9. Covers covariate selection, lag structure, Fourier seasonality terms, ARIMAX formulation, and counterfactual intervention analysis.

## Instructions

### Step 1: Identify Relevant Covariates for Dengue

Dengue transmission is driven by the extrinsic incubation period (EIP) of DENV in Aedes aegypti, which depends on temperature, and by vector abundance, which depends on rainfall and standing water. Standard covariate candidates:

**Meteorological (primary)**:
- **Temperature** (Tmin, Tmean, Tmax in °C): affects EIP. EIP ≈ 4 days at 35°C, ~12 days at 25°C. Effect is non-linear — use temperature bins or polynomial terms.
- **Accumulated rainfall** (mm/week): drives mosquito breeding. Effect is lagged (2-4 weeks: rain → standing water → larval development → adult emergence → bites → disease reporting).
- **Relative humidity** (%): affects adult mosquito survival. Secondary predictor.

**Entomological**:
- **Breteau Index (BI)**: number of positive containers per 100 houses inspected. Leading indicator (3-6 weeks before cases).
- **LIRAa** (Levantamento de Índice Rápido de Aedes aegypti): Brazilian quarterly rapid survey index.
- **Mosquito trap counts** (ovitrap, BG-Sentinel): proxy for adult vector density.

**Epidemiological**:
- **Lagged case counts**: y_{t-1}, y_{t-2} — autoregressive component.
- **Incidence from neighboring municipalities**: spatial spillover effect (use with spatial lag models).
- **Serotype surveillance**: presence of new DENV serotype in circulation (binary indicator of elevated epidemic risk).

### Step 2: Establish Lag Structure

**Critical principle**: for dengue, covariates are effective predictors only with appropriate lags. Using contemporaneous (unlagged) covariates introduces data leakage in real operational forecasting (you can't know today's rainfall next week).

Standard lag relationships for weekly dengue:

| Covariate | Lag range | Biological mechanism |
|---|---|---|
| Temperature | 2-4 weeks | EIP: temperature affects virus replication rate in mosquito |
| Rainfall | 2-6 weeks | Larval development + adult emergence + EIP |
| Humidity | 1-3 weeks | Adult survival |
| Breteau Index | 3-6 weeks | Vector abundance leads cases |
| Neighboring cases | 1-2 weeks | Spatial diffusion of outbreak |

```r
# Create lagged covariate matrix
lag_matrix <- cbind(
  temp_lag2  = lag(temperature_weekly, -2),  # temp 2 weeks ago
  temp_lag3  = lag(temperature_weekly, -3),
  rain_lag3  = lag(rainfall_weekly, -3),     # rain 3 weeks ago
  rain_lag4  = lag(rainfall_weekly, -4),
  humid_lag2 = lag(humidity_weekly, -2)
)

# Remove rows with NA (first max_lag weeks)
complete_cases <- complete.cases(lag_matrix)
dengue_train_reg <- window(log1p(dengue_ts), start=...)
covariate_matrix <- lag_matrix[complete_cases, ]
```

### Step 3: Select Predictors Formally

Avoid manual predictor selection based on scatterplots — use information criteria:

```r
# Stepwise by AICc (via auto.arima with xreg)
# Test individual lags and combinations

# Option A: Use cross-correlation to identify lag peaks
ccf(log1p(dengue_ts), rainfall_weekly, lag.max=12,
    main="Cross-correlation: Dengue cases vs. Rainfall")
# Peak at lag -3 means dengue lags behind rainfall by 3 weeks

# Option B: Fit linear regression model, select by adjusted R2 or AICc
model_select <- tslm(log1p(dengue_ts) ~ rain_lag3 + temp_lag2 + humid_lag2)
summary(model_select)
```

**Watch for spurious regression**: non-stationary climate series regressed on non-stationary dengue series will show artificially high R² and significant p-values even without a causal relationship. Always check residual autocorrelation — if residuals show strong ACF, the regression is incomplete and needs ARIMA errors.

### Step 4: Fit Dynamic Regression (Regression with ARIMA Errors)

The standard FPP2 framework: fit a regression with ARIMA-structured errors. This is NOT the same as an ARIMA model with covariates added naively.

**Formulation**:
```
y_t = β₀ + β₁ x_{1,t-lag1} + β₂ x_{2,t-lag2} + η_t
η_t ~ ARIMA(p,d,q)  [error structure]
```

```r
# Dynamic regression: ARIMAX with climate covariates
model_dynreg <- auto.arima(log1p(dengue_ts),
                            xreg = covariate_matrix,
                            seasonal = TRUE,
                            stepwise = FALSE)

summary(model_dynreg)
checkresiduals(model_dynreg)
# If residuals are white noise → the model is complete
```

**To forecast h steps ahead, you need future values of covariates**: use weather forecast data (INMET, ECMWF) for 1-2 week ahead temperature/rainfall predictions, or use the climatological mean (average of same week across historical years) for longer horizons.

```r
# Future covariate matrix for h=4 week forecast
# Use ECMWF/INMET forecast for first 2 weeks; climatological mean for weeks 3-4
future_xreg <- rbind(
  ecmwf_forecast_week1,
  ecmwf_forecast_week2,
  climatological_mean_week3,
  climatological_mean_week4
)

fc_dynreg <- forecast(model_dynreg, xreg=future_xreg, h=4)
fc_original <- expm1(fc_dynreg$mean)
```

### Step 5: Use Fourier Terms for Complex Seasonality

For weekly data (frequency=52), seasonal ARIMA requires many seasonal lags. An alternative is to use Fourier terms (sine/cosine pairs) to represent seasonality in a regression:

```r
# K Fourier terms capture K harmonics of annual seasonality
# Dengue: K=2 or K=3 typically sufficient (captures the main epidemic peak + harmonic)
fourier_terms <- fourier(log1p(dengue_ts), K=3)

# Combine Fourier + climate covariates
xreg_full <- cbind(fourier_terms, covariate_matrix)

# Fit ARIMA with Fourier seasonality (non-seasonal ARIMA on the residuals)
model_fourier <- auto.arima(log1p(dengue_ts),
                             xreg = xreg_full,
                             seasonal = FALSE)  # seasonality handled by Fourier

# For forecasting:
future_fourier <- fourier(log1p(dengue_ts), K=3, h=4)
future_xreg_full <- cbind(future_fourier, future_xreg)
fc_fourier <- forecast(model_fourier, xreg=future_xreg_full, h=4)
```

**Advantages of Fourier approach for dengue**:
- More flexible seasonal shape than SARIMA (which assumes a specific lag structure).
- Works with other seasonal frequencies (e.g., 365 for daily data, or 12 for monthly).
- Easily extended with additional harmonic terms if needed.
- K can be selected by AICc: try K=1 to K=6 and pick minimum AICc.

### Step 6: Analyze Intervention Effects

Dengue control campaigns (fumigation, larval elimination) or surveillance system changes can create structural breaks. Model as dummy variables:

```r
# Campaign effect: a vector control campaign ran in SE 5-10 of 2018
intervention_dummy <- ifelse(time(dengue_ts) == 2018 + (5:10-1)/52, 1, 0)

# Sudden level shift: reporting system changed in 2020
level_shift <- ifelse(time(dengue_ts) >= 2020, 1, 0)

# Include in regression
xreg_with_intervention <- cbind(covariate_matrix, intervention_dummy, level_shift)
model_with_intervention <- auto.arima(log1p(dengue_ts), xreg=xreg_with_intervention)
```

## Examples

### Example 1: Building a 3-week-ahead dengue forecast with rainfall

User says: "I want to predict dengue cases 3 weeks ahead using weekly rainfall data."

Actions:
1. Cross-correlate: `ccf(dengue_ts, rain_weekly)` → peak at lag -3 (rain 3 weeks ago predicts cases now).
2. Create `rain_lag3 = lag(rain_weekly, -3)`.
3. Fit: `auto.arima(log1p(dengue_ts), xreg=rain_lag3)` → finds ARIMA(1,1,0) errors with β_rain = 0.12 (positive: more rain → more cases).
4. To forecast next 3 weeks: use rainfall from current week (already known, as it's the lag-3 value for 3 weeks ahead).
5. Back-transform and generate probabilistic forecast.

Result: 3-week-ahead forecast using known rainfall as a leading indicator — genuine operational forecasting without data leakage.

### Example 2: Comparing Fourier terms K=1 to K=4 for dengue seasonality

User says: "How many Fourier terms should I use for dengue weekly seasonality?"

Actions:
1. Fit ARIMA with K=1,2,3,4,5 Fourier terms (no other covariates).
2. Compare AICc: typically K=3 gives minimum AICc for dengue (captures the main epidemic peak + its harmonic structure).
3. K=1: too smooth, misses narrow epidemic peak. K=5+: overfits, especially in low-incidence years.
4. Use K=3 as default; validate with residual ACF.

Result: K=3 Fourier terms selected; AICc and residual ACF both confirm.

### Example 3: Evaluating a fumigation campaign effect on dengue

User says: "The city ran a major fumigation campaign in February-March 2019. Did it work?"

Actions:
1. Add `intervention = 1` for SE 5-14 of 2019, `0` otherwise.
2. Fit dynamic regression with intervention dummy + climate covariates.
3. Check `coef(model)["intervention"]` — if negative and significant, the campaign reduced cases beyond what the climate model would predict.
4. Counterfactual: forecast without the intervention term → compare predicted vs. actual to estimate cases prevented.

Result: Quantified intervention effect with confidence interval, controlling for climate and baseline epidemic dynamics.

## Troubleshooting

### High R² but residuals are autocorrelated
Cause: Spurious regression — both dengue and the climate covariate are trending upward, creating artificial correlation.
Solution: This is why ARIMA errors are essential. Use `auto.arima(..., xreg=...)` not `lm()`. The ARIMA error structure absorbs the remaining autocorrelation after regression.

### Future covariate values not available for forecast horizon
Cause: Trying to forecast 6 weeks ahead using rainfall, but weather forecasts are only reliable for 1-2 weeks.
Solution: (a) Limit forecast horizon to 2-3 weeks when using rainfall; (b) Use climatological rainfall average (average same week from historical years) as a proxy for weeks beyond the reliable forecast range; (c) Produce scenario forecasts: low/medium/high rainfall scenarios.

### Regression coefficient for temperature is negative (counterintuitive)
Cause: Multicollinearity between temperature and rainfall (both high in rainy season); or wrong lag chosen; or confounding by serotype cycle.
Solution: Check VIF (variance inflation factor) for multicollinearity. Try individual predictors separately. Use `car::vif(lm(...))`. If temperature and rainfall are highly correlated, consider using only one or creating a composite index.
