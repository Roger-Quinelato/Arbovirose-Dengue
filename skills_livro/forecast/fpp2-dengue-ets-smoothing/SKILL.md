---
name: fpp2-dengue-ets-smoothing
description: "Applies exponential smoothing state space models (ETS) and decomposition methods from Forecasting Principles and Practice (Hyndman & Athanasopoulos, Ch.6-7) to dengue arbovirose forecasting. Use when fitting ETS, Holt-Winters, Simple Exponential Smoothing, STL decomposition, or state-space smoothing models to dengue case series. Trigger phrases: 'fit ETS to dengue cases', 'Holt-Winters for dengue', 'exponential smoothing dengue forecast', 'STL decomposition dengue', 'state space model for epidemic seasonality', 'smooth dengue series', 'ETS model selection', 'additive vs multiplicative seasonality dengue'. Do NOT use for ARIMA modeling (use fpp2-dengue-arima), regression with climate covariates (use fpp2-dengue-regression-dynamic), accuracy evaluation (use fpp2-dengue-accuracy-benchmarks), or count-specific models (use fpp2-dengue-count-models)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# FPP2 Dengue ETS and Exponential Smoothing

Guides fitting and interpretation of Exponential Smoothing State Space (ETS) models and decomposition methods for dengue arbovirose forecasting — based on Forecasting Principles and Practice (Hyndman & Athanasopoulos) Ch.6-7. Covers the full ETS taxonomy, Holt-Winters, STL decomposition, and practical dengue-specific configurations.

## Instructions

### Step 1: Choose Decomposition vs. Direct Smoothing

Two strategies for dengue modeling with ETS:

**Strategy A — Direct ETS**: fit a single ETS model that handles trend + seasonality internally. Appropriate when the goal is automated forecasting across many municipalities.

**Strategy B — Decompose then Forecast**: use STL or classical decomposition to separate the series into trend, seasonal, and remainder components; model/forecast each separately; recombine. Recommended for exploratory work or when seasonal patterns are highly irregular across years.

For dengue, **Strategy B (STL + ETS)** is often preferred because:
- Dengue seasonality is highly heterogeneous between epidemic and non-epidemic years.
- STL is robust to outliers (epidemic peaks) — it uses LOESS smoothing which is resistant to extreme values.
- STL allows the seasonal component to change over time (adaptive seasonality), unlike classical decomposition.

### Step 2: Apply STL Decomposition for Dengue

```r
library(fpp2)

# STL decomposition of weekly dengue series
dengue_stl <- stl(log1p(dengue_ts),
                  s.window = "periodic",  # fixed seasonal pattern
                  # OR: s.window = 13    # slowly-evolving seasonal window
                  robust = TRUE)          # robust to epidemic outliers

autoplot(dengue_stl) +
  ggtitle("STL Decomposition: Dengue Cases (log scale)")
```

STL parameters for dengue:
- `s.window = "periodic"`: forces fixed seasonal shape (safe default, recommended first).
- `s.window = 13` or larger odd number: allows gradual change in seasonal pattern over ~13/2 years. Use if serotype-driven seasonal shifts are suspected.
- `robust = TRUE`: downweights extreme observations (epidemic peaks) when estimating trend and seasonal components. **Always use `robust=TRUE` for dengue** — epidemic peaks would otherwise distort the estimated baseline trend.
- `t.window`: controls smoothness of the trend estimate. Default is fine; increase for smoother trend.

**Interpret the STL decomposition**:
- **Trend component**: captures the multi-year rising baseline from urbanization and serotype expansion.
- **Seasonal component**: the typical within-year epidemic curve (peak SE 8-12 in SE Brazil).
- **Remainder**: residuals after removing trend and seasonal components. Epidemic surges beyond the expected seasonal pattern appear here — this is epidemiologically meaningful (it shows extraordinary epidemic activity).

### Step 3: Forecast Using STL + ETS

The cleanest way to forecast after STL decomposition:

```r
# STL + ETS: decompose, forecast remainder, recombine
dengue_stlf <- stlf(log1p(dengue_ts),
                    method = "ets",    # model the remainder with ETS
                    h = 12,            # 12 weeks ahead
                    s.window = "periodic",
                    robust = TRUE,
                    lambda = NULL)     # already log-transformed

# Back-transform forecasts to original scale
fc_dengue <- forecast(dengue_stlf)
fc_original <- expm1(fc_dengue$mean)  # reverse log1p
```

### Step 4: Select the ETS Model Class

ETS models are parameterized as ETS(E, T, S) where:
- **E** (Error): A (Additive) or M (Multiplicative)
- **T** (Trend): N (None), A (Additive), Ad (Additive Damped)
- **S** (Seasonal): N (None), A (Additive), M (Multiplicative)

**For dengue case counts** (after log transformation):

| Pattern observed | Recommended ETS | Rationale |
|---|---|---|
| Seasonal, no trend | ETS(A,N,A) | Seasonal with additive errors |
| Seasonal + trend | ETS(A,A,A) — Holt-Winters Additive | Trend + seasonality on log scale |
| Fading epidemic momentum | ETS(A,Ad,A) — Damped Holt-Winters | Damped trend prevents explosion |
| Heterogeneous seasonality | STL + ETS(A,N,N) | Let STL handle seasonality; SES for remainder |

**Automatic ETS selection**:
```r
# Let the algorithm select the best ETS specification
model_ets <- ets(log1p(dengue_ts))
summary(model_ets)  # shows chosen E, T, S; AICc for comparison
```

AICc (corrected AIC) is used for model selection. The `ets()` function tries all valid combinations and returns the best.

**Why damped trend (Ad) for dengue?** During epidemic growth phases, an undamped trend will extrapolate linearly into the future even after the outbreak peak. The damped trend automatically attenuates the trend as the horizon grows, which is more realistic for epidemic dynamics.

### Step 5: Holt-Winters for Dengue — Manual Configuration

When you want explicit control over the smoothing parameters:

```r
# Holt-Winters Additive (after log transformation)
model_hw <- hw(log1p(dengue_ts),
               seasonal = "additive",    # additive seasonality on log scale
               h = 12,
               damped = TRUE,            # damped trend
               level = c(80, 95))        # 80% and 95% prediction intervals

# Check parameter estimates
model_hw$model$par
# alpha: level smoothing (0=very smooth, 1=very reactive)
# beta: trend smoothing
# gamma: seasonal smoothing
```

**Interpreting smoothing parameters for dengue**:
- **alpha (level)**: typically 0.3-0.7 for dengue. Higher alpha = model reacts faster to new case counts = good during outbreak onset; worse during noise periods.
- **beta (trend)**: typically small (0.01-0.1). Trend in dengue changes slowly between years.
- **gamma (seasonal)**: typically 0.1-0.3. Controls how fast the seasonal pattern adapts between years.

### Step 6: Generate and Interpret Prediction Intervals

```r
# Generate probabilistic forecasts
fc <- forecast(model_ets, h=12, level=c(50, 80, 90, 95))

# Back-transform
fc_original <- fc
fc_original$mean <- expm1(fc$mean)
fc_original$lower <- expm1(fc$lower)
fc_original$upper <- expm1(fc$upper)

autoplot(fc_original) +
  ggtitle("ETS Dengue Forecast: 12 weeks ahead") +
  xlab("Epidemiological Week") + ylab("Estimated Cases")
```

**Interpretation for public health**:
- The 80% interval is the standard for dengue early warning: "we expect cases to be in this range with 80% confidence."
- Wide intervals during inter-epidemic periods indicate high uncertainty — appropriate for dengue given multi-year epidemic cycles.
- Narrow intervals during epidemic peak: the model is more confident about near-term trajectory once the outbreak is underway.

## Examples

### Example 1: Weekly dengue forecasting with STL + ETS

User says: "I need 4-week-ahead dengue forecasts for 100 municipalities automatically."

Actions:
1. Create a list of 100 `ts` objects (weekly, frequency=52).
2. For each: `stlf(log1p(ts_i), method="ets", h=4, s.window="periodic", robust=TRUE)`.
3. Back-transform: `expm1()` on forecasts and intervals.
4. Evaluate: `accuracy(fc, test_window)` — compute MASE for each municipality.
5. Flag municipalities where MASE > 1 (model worse than snaive) for manual review.

Result: Automated pipeline producing 4-week probabilistic forecasts for 100 municipalities with performance flags.

### Example 2: Identifying serotype-driven seasonal change

User says: "Our dengue peak has shifted from February to March in recent years. Does STL capture this?"

Actions:
1. Use `s.window=13` (evolving seasonality) instead of `"periodic"`.
2. Extract the seasonal component: `dengue_stl$time.series[,"seasonal"]`.
3. Plot seasonal component over time — check if peak SE drifts from SE 8 to SE 12 over years.
4. If drift is confirmed, `s.window=13` is appropriate; if seasonal pattern is stable, use `"periodic"` for better statistical efficiency.

Result: STL with evolving seasonal window detects and adapts to serotype-driven seasonal shift.

### Example 3: Comparing ETS(A,N,A) vs. ETS(A,Ad,A)

User says: "My ETS model predicts cases will keep rising for 8 weeks after the peak. Is that right?"

Actions:
1. Check `model_ets$components` — if trend=A (additive), the model extrapolates the trend linearly.
2. Re-fit with `damped=TRUE` or manually force `ETS(A,Ad,A)`.
3. Compare AICc: damped model likely has lower AICc (more parsimonious, avoids over-extrapolation).
4. Biologically: dengue outbreaks have natural immune depletion limits — the damped trend better captures epidemic plateau and decline dynamics.

Result: Damped-trend ETS adopted for more realistic multi-week forecasting beyond the epidemic peak.

## Troubleshooting

### ETS chooses ETS(M,N,M) with negative case count predictions
Cause: Multiplicative errors/seasonality on the original (non-log) scale can produce negative predictions if the series has near-zero periods.
Solution: Apply `log1p()` transformation first; on the log scale, use additive ETS. Multiplicative ETS on the original scale is not appropriate for count data with zeros.

### STL produces a flat seasonal component
Cause: `s.window="periodic"` forces the seasonal pattern to be identical across all years, but dengue has enormous inter-annual variability.
Solution: The flat component is actually correct — it shows the average seasonal pattern. The inter-annual epidemic variability should appear in the remainder component (not the seasonal). If you need year-specific seasonality, use `s.window` with a smaller value (e.g., 7 to allow fast adaptation).

### Prediction intervals are too wide to be actionable
Cause: High uncertainty inherent to dengue forecasting, especially for horizons > 4 weeks or in early epidemic detection.
Solution: Accept that wide intervals reflect genuine uncertainty — do not artificially narrow them. Use the central forecast for resource planning with stated uncertainty. Consider shorter horizons (1-2 weeks) for operational decisions where narrow intervals are more achievable.
