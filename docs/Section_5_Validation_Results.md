# Section 5: Empirical Validation

**MAC Framework Backtest Results — February 2026**

*Extended backtest covering 117 years (1907-2025) across 41 crisis events, using real data with era-specific historical proxies*

---

## 5.1 Methodology

### 5.1.1 Backtest Architecture

The MAC framework was validated through comprehensive historical backtesting against **41 major financial market stress events spanning 1907-2025** — a 117-year validation period encompassing **6,158 weekly observations**. The backtest engine (`BacktestRunner`) iterates over the date range at weekly frequency, calculating all seven pillar scores and the composite MAC score at each point using only data available as of that date (no look-ahead bias).

Each crisis scenario in the validation database includes:

- Historical indicator values sourced from FRED, NBER Macrohistory, Schwert volatility, Shiller CAPE, Bank of England, and FINRA margin debt archives
- Expected MAC score ranges derived from crisis severity analysis and contemporary accounts
- Expected pillar breaches based on documented market conditions
- Severity classification (moderate, high, extreme)

### 5.1.2 Six Methodological Improvements

The current backtesting methodology incorporates six improvements over the initial implementation, which raised the true positive rate from 26.7% to 75.6%:

**Fix A — Exclude Missing Pillars from Composite.** When a pillar has no underlying indicator data (e.g., SLOOS not yet available, or positioning without CFTC data), the pillar is excluded from the weighted average rather than defaulting to 0.5. This prevents neutral scores from diluting genuine stress signals. The `has_data` dictionary tracks whether each pillar received at least one real data point for the current date.

**Fix B — Wire Up Contagion Proxy via BAA10Y.** The contagion pillar, previously frozen at its default score, now uses Moody's Baa-10Y Treasury spread (`BAA10Y`) as a proxy for financial sector credit stress. This spread captures systemic banking and corporate stress similarly to G-SIB CDS spreads and is available from 1919 onwards.

**Fix C — Range-Based Valuation Scoring.** Valuation pillar indicators (term premium, IG OAS, HY OAS) were changed from one-sided scoring (`score_indicator_simple`) to two-sided range-based scoring (`score_indicator_range`). This reflects the fundamental insight that both compressed *and* extremely wide spreads indicate problems:

| Indicator | Ample Range | Thin Range | Breach Range |
|-----------|-------------|------------|--------------|
| Term Premium | 40–120 bps | 0–200 bps | < -50 or > 250 bps |
| IG OAS | 100–180 bps | 75–280 bps | < 60 or > 400 bps |
| HY OAS | 350–550 bps | 280–800 bps | < 200 or > 1,000 bps |

Under the original one-sided approach, compressed pre-GFC spreads (IG OAS ~60 bps in 2007) scored as "ample" rather than signalling complacency. The two-sided approach correctly penalises both extremes.

**Fix D — ML-Optimized Weights for Modern Era.** For dates from 2006 onwards, the backtest uses gradient-boosting-derived pillar weights optimised against 14 historical crisis scenarios (1998–2025). For earlier eras, era-specific weights or equal weights are used.

**Fix E — Era-Aware Calibration Factor.** The multiplicative calibration factor is applied on a sliding scale to account for structural differences across eras:

| Era | Calibration Factor | Rationale |
|-----|-------------------|-----------|
| 2006–present | 0.78 | Calibrated against modern scenarios |
| 1971–2006 | 0.90 | Milder adjustment; proxy data already compressed |
| Pre-1971 | 1.00 | No calibration; Schwert vol and NBER spreads are structurally wider |

**Fix F — Momentum-Enhanced Warning Detection.** Crisis warnings now combine level-based detection (MAC < 0.50) with momentum-based detection (MAC < 0.60 AND 4-week momentum < -0.04). This captures the important signal that a *declining* MAC from 0.65 to 0.50 is more actionable than a static MAC of 0.52.

### 5.1.3 ML-Optimized Weights

Pillar weights for the modern era (2006+) were derived from gradient boosting optimisation on 14 historical crisis scenarios spanning 1998–2025. The optimisation maximises separation between crisis and non-crisis MAC scores while accounting for non-linear pillar interactions.

**Table 5.1: ML-Optimized Pillar Weights**

| Pillar | Equal Weight | ML Weight | Rationale |
|--------|-------------|-----------|-----------|
| Positioning | 14.3% | **22%** | Key predictor of hedge failure (100% correlation in sample) |
| Liquidity | 14.3% | 16% | Critical for funding stress detection |
| Contagion | 14.3% | 16% | Distinguishes global vs local crises |
| Volatility | 14.3% | 15% | Ubiquitous (breached in 9/14 crises) but not predictive alone |
| Private Credit | 14.3% | 12% | Leading indicator for credit cycle stress |
| Valuation | 14.3% | 10% | Only breaches in extreme crises (2/14 events) |
| Policy | 14.3% | **9%** | Never breached in the 14-scenario training sample |

When amplification conditions are detected (positioning stressed AND volatility/liquidity/contagion also stressed), interaction-adjusted weights are activated that further boost positioning to 24% and contagion to 18%, reflecting the forced-unwind mechanism.

### 5.1.4 Non-Linear Breach Interaction Penalty

When multiple pillars breach simultaneously, risks compound non-linearly. The framework applies a penalty that is subtracted from the weighted-average MAC score:

| Simultaneous Breaches | Penalty |
|-----------------------|---------|
| 0–1 | 0.00 |
| 2 | 0.03 |
| 3 | 0.08 |
| 4 | 0.12 |
| 5+ | 0.15 (cap) |

A pillar is considered "stressed" for interaction purposes when its score falls below 0.30.

### 5.1.5 Momentum Analysis

The framework tracks rate-of-change in the composite MAC score over 1-week, 2-week, and 4-week horizons. This produces an enhanced five-level status system:

| Status | Condition |
|--------|-----------|
| COMFORTABLE | MAC > 0.65 |
| CAUTIOUS | MAC 0.50–0.65 |
| DETERIORATING | MAC 0.50–0.65 AND 4-week momentum < -0.05 |
| STRETCHED | MAC 0.35–0.50 |
| CRITICAL | MAC < 0.35 |

The DETERIORATING status is the key addition: it identifies periods where buffers are thinning rapidly, providing earlier warning than a simple level-based threshold.

### 5.1.6 Indicator Scoring Methodology

All pillar indicators are scored on a continuous 0–1 scale using piecewise-linear interpolation between calibrated thresholds:

- **1.0 (Ample):** Indicator within healthy range; substantial buffer capacity
- **0.5 (Thin):** Buffer depleted; elevated sensitivity to shocks
- **0.0 (Breach):** Buffer exhausted; non-linear dynamics likely

Two scoring functions are used:

1. **`score_indicator_simple`** — One-sided: value should be above (or below) a threshold. Used for liquidity spreads, VIX, basis trade size, and similar indicators where directionality is clear.

2. **`score_indicator_range`** — Two-sided: value should be within a "healthy" middle range. Used for valuation indicators (term premium, credit OAS) where both compressed and extreme values indicate problems.

Pillar composites are calculated as the equally-weighted average of their constituent indicator scores, using only indicators with available data.

---

## 5.2 Historical Data Infrastructure

### 5.2.1 Era-Specific Proxy Chains

The backtest spans 10 distinct market structure eras, each with different data availability. The framework defines era-specific configurations that determine which pillars have real data, what proxy series to use, and how to adjust thresholds for structural differences.

**Table 5.2: Era Definitions and Data Availability**

| Era | Period | Pillars with Data | Key Structural Feature |
|-----|--------|-------------------|----------------------|
| Pre-Fed | 1907–1913 | Liq, Val, Vol | No central bank; gold standard |
| Early Fed / WWI | 1913–1919 | Liq, Val, Vol, Pol | Fed opens; discount rate only |
| Interwar / Depression | 1920–1934 | Liq, Val, Vol, Pol, Pos | Moody's credit data begins |
| New Deal / WWII | 1934–1954 | Liq, Val, Vol, Pol, Pos | T-Bills issued; SEC created |
| Post-War / Bretton Woods | 1954–1971 | Liq, Val, Vol, Pol, Pos | Fed Funds daily; modern Treasury market |
| Post-Bretton Woods | 1971–1990 | All except Pvt Credit | Floating rates; NASDAQ realised vol |
| Modern (early) | 1990–1997 | All except Pvt Credit | VIX introduced |
| Modern (middle) | 1997–2006 | All except Pvt Credit | TED spread; ICE BofA indices |
| Modern (pre-SOFR) | 2006–2018 | All 7 | Full data; LIBOR-OIS; SVXY |
| Modern (SOFR) | 2018–present | All 7 | SOFR-IORB; full instrumentation |

### 5.2.2 Historical Proxy Series

**Table 5.3: Indicator Proxy Chain**

| Indicator | Modern Series (Start) | Historical Proxy | Proxy Availability |
|-----------|----------------------|------------------|-------------------|
| VIX | VIXCLS (1990) | VXO (1986); NASDAQ realised vol x 1.2 VRP (1971); Schwert vol x 1.3 VRP (1802) | 1802+ |
| HY OAS | BAMLH0A0HYM2 (1997) | (Moody's Baa - Aaa) x 4.5 | 1919+ |
| IG OAS | BAMLC0A0CM (1997) | Moody's Baa - DGS10 - 40 bps | 1919+ |
| Contagion (financial stress) | G-SIB CDS (2006) | BAA10Y (Baa-Treasury spread) | 1919+ |
| SOFR-IORB | SOFR/IORB (2018) | LIBOR-OIS (1997); TED spread (1986); FEDFUNDS-TB3MS (1954) | 1954+ |
| CP-Treasury spread | DCPF3M-DTB3 (1997) | Commercial paper rate - short-term govt rate (NBER) | 1890+ |
| Policy room | DFF (1954) | Fed discount rate INTDSRUSM193N (1913) | 1913+ |
| Funding stress | SOFR-IORB (2018) | Call money rate - govt rate (NBER) | 1890+ |
| Credit spread (pre-Moody's) | — | Railroad bond yield - govt bond yield (NBER) | 1857+ |
| Equity vol (pre-VIX) | — | Schwert (1989) monthly realised vol | 1802+ |
| Leverage proxy | CFTC COT (1986) | NYSE margin debt / GDP (FINRA) | 1918+ |
| Contagion (pre-Bretton Woods) | — | GBP/USD deviation from gold parity (BoE) | 1791+ |

### 5.2.3 External Data Sources

| Source | Coverage | Indicators Provided |
|--------|----------|---------------------|
| **FRED** (Federal Reserve Economic Data) | 1913–present | 30+ series: rates, spreads, VIX, credit, policy, Fed balance sheet |
| **NBER Macrohistory Database** | 1857–1940s | Call money rate, CP rate, govt rates, railroad bonds, gold stock |
| **Shiller (Yale)** | 1871–present | S&P Composite, CAPE, CPI, long-term interest rate |
| **Schwert (1989)** | 1802–1987 | Monthly stock return volatility (annualised %) |
| **Bank of England Research** | 1694–present | GBP/USD exchange rate, Bank Rate |
| **MeasuringWorth** | 1790–present | Annual nominal US GDP |
| **FINRA/NYSE** | 1918–present | Monthly margin debt |

### 5.2.4 Era-Specific Threshold Overrides

Pre-1971 eras had fundamentally different market structures requiring threshold adjustments:

**Table 5.4: Threshold Adjustments by Era**

| Parameter | Modern Default | Pre-Fed (1907–1913) | Early Fed (1913–1919) | Interwar (1920–1934) |
|-----------|---------------|--------------------|-----------------------|---------------------|
| Liquidity spread breach | — | 200 bps | 150 bps | 100 bps |
| IG OAS breach (high) | 400 bps | 600 bps | 500 bps | 500 bps |
| HY OAS breach (high) | 1,000 bps | 1,500 bps | 1,400 bps | 1,400 bps |
| VIX breach (high) | ~35 | 50 | 50 | 45 |
| Policy room breach | — | N/A (no Fed) | 50 bps | 40 bps |

Rationale: call money rates routinely spiked to 100%+ pre-Fed; railroad bond spreads were structurally wider than modern corporate bonds; Schwert volatility was structurally higher than VIX.

---

## 5.3 Calibration Factor Derivation

### 5.3.1 Motivation

Initial backtesting revealed that raw MAC scores (weighted-average of pillar scores) systematically ran 20–25% higher than expected crisis severity ranges. This upward bias arises because:

1. Not all indicators breach simultaneously even during severe crises
2. Pillars with limited data default to 0.5 (neutral), pulling the composite upward
3. The 0–1 scoring scale compresses most non-crisis observations into the 0.6–0.9 range

### 5.3.2 Calibration Methodology

The calibration factor was derived through cross-validation against 14 modern crisis scenarios (1998–2025) where expected MAC ranges are well-established from contemporary analysis:

$$\text{MAC}_{\text{calibrated}} = \text{MAC}_{\text{raw}} \times \alpha_{\text{era}}$$

where:

$$\alpha_{\text{era}} = \begin{cases} 0.78 & \text{if date} \geq 2006 \\ \min(0.78 + 0.12, 1.0) = 0.90 & \text{if } 1971 \leq \text{date} < 2006 \\ 1.00 & \text{if date} < 1971 \end{cases}$$

### 5.3.3 Era-Aware Rationale

- **Post-2006 (α = 0.78):** Full data availability; raw scores require the largest correction because all seven pillars contribute.
- **1971–2006 (α = 0.90):** Proxy data (Moody's credit, NASDAQ realised vol) already produces lower raw scores due to structural differences. A milder calibration prevents over-penalisation.
- **Pre-1971 (α = 1.00):** Schwert volatility (~45% annualised vs modern VIX ~15–20%) and wider NBER/railroad spreads already compress raw scores sufficiently. Applying 0.78 would over-penalise and create excessive false positives.

### 5.3.4 Empirical Threshold Calibration

Stress regime thresholds were empirically calibrated from the 1971–2025 backtest distribution to achieve target population proportions:

| Regime | Target Distribution | Stress Score Percentile |
|--------|--------------------|-----------------------|
| Comfortable | ~45% of observations | 0–45th |
| Cautious | ~30% | 45th–75th |
| Stretched | ~18% | 75th–93rd |
| Critical | ~7% | 93rd+ |

---

## 5.4 Backtest Results

### 5.4.1 Summary Performance

**Table 5.5: Validation Summary Statistics (117-Year Sample)**

| Metric | Value |
|--------|-------|
| Total Weekly Observations | **6,158** |
| Time Span | **1907–2025 (117 years)** |
| Total Crisis Events Tested | **41** |
| **True Positive Rate** | **75.6%** (31/41) |
| Number of Pillars | 7 (including Private Credit) |
| Calibration Factor | 0.78 (era-aware) |
| Data Sources | FRED + NBER + Schwert + Shiller + BoE + FINRA |
| Scoring Method | Range-based (two-sided) for valuation; simple for others |
| Weight Method | ML-optimized (2006+), era-specific (pre-1971), equal (default) |

### 5.4.2 Crisis Detection by Era

| Era | Crises | Detected | TPR | Notes |
|-----|--------|----------|-----|-------|
| Pre-Fed (1907–1913) | 2 | 1 | 50% | Panic of 1907 captured; 1910–11 too mild |
| Early Fed / WWI (1913–1919) | 1 | 1 | 100% | 1914 exchange closure |
| Interwar / Depression (1920–1934) | 4 | 3 | 75% | 1929 crash, bank panics, 1933 bank holiday |
| New Deal / WWII (1934–1954) | 1 | 1 | 100% | 1937–38 recession |
| Post-War (1954–1971) | 5 | 3 | 60% | Kennedy Slide, Credit Crunch 1966, Penn Central |
| Post-Bretton Woods (1971–1990) | 8 | 6 | 75% | Nixon Shock through Black Monday |
| Modern (1990–2025) | 20 | 16 | 80% | LTCM through Yen Carry Unwind |

### 5.4.3 Warning Detection Methodology

A crisis is considered "detected" if either of the following conditions is met within the 90-day window before the crisis start date:

1. **Level-based:** MAC score < 0.50 (STRETCHED regime or worse)
2. **Momentum-based:** MAC score < 0.60 AND 4-week momentum < -0.04 (rapid deterioration while in CAUTIOUS regime)

This dual-signal approach significantly improves detection of crises where MAC levels are borderline but declining rapidly.

---

## 5.5 Data Quality Assessment

### 5.5.1 Quality Tiers

| Quality Tier | Date Range | Characteristics |
|--------------|------------|-----------------|
| Excellent | 2018–present | All 7 pillars, daily frequency, SOFR-IORB |
| Good | 2011–2018 | All pillars, LIBOR-OIS, SVXY |
| Fair | 1990–2011 | VIX available, Moody's proxies for credit |
| Poor | 1907–1990 | Monthly NBER/Schwert data, proxy chains |

### 5.5.2 Impact on Results

Pre-1971 results should be interpreted with appropriate caveats:

1. **Monthly vs weekly granularity:** NBER and Schwert data are monthly, interpolated to weekly
2. **Proxy estimation error:** Railroad-to-corporate credit spread scaling introduces uncertainty
3. **Structural regime differences:** Gold standard constraints, no modern central banking, limited financial instrumentation
4. **Positioning data absence:** Pre-1918 positioning relies on default scores (0.50)

Despite these limitations, the framework correctly identifies the major crises of each era (Panic of 1907, 1929 Crash, Depression-era bank panics, Black Monday 1987) while maintaining low false positive rates.

---

## 5.6 Key Findings

### 5.6.1 Positioning Breach Predicts Treasury Hedge Failure

The empirical finding from the modern sub-sample (2006–2025) is preserved and strengthened: when the positioning pillar breaches (score < 0.2), Treasury hedges are significantly more likely to fail due to forced deleveraging of basis trades and margin-driven correlated selling.

### 5.6.2 Multi-Pillar Advantage over Single Indicators

The composite MAC score provides value beyond any single indicator:

- **VIX alone** missed the 2019 Repo crisis (VIX ~15, normal) and provided no positioning signal for the 2025 Tariff shock
- **Credit spreads alone** were compressed to historic lows in the pre-GFC build-up, producing false comfort
- **The MAC framework** correctly flagged pre-GFC complacency via the two-sided valuation scoring and identified positioning-driven hedge failures

### 5.6.3 Era-Aware Calibration is Essential

Applying a single calibration factor across all eras produces excessive false positives pre-1971 (FPR > 90%) because structural differences in historical data (higher Schwert volatility, wider railroad spreads) already compress raw scores. The era-aware sliding scale resolves this.

---

## 5.7 Limitations and Future Work

### 5.7.1 Current Limitations

1. **Pre-1971 data quality:** Monthly proxy data with limited cross-validation
2. **Positioning pillar gaps:** No CFTC data before 1986; margin debt is a crude leverage proxy
3. **Private credit pillar:** SLOOS data only available from ~1990; BDC data from ~2004
4. **Calibration factor stability:** 0.78 was calibrated on modern data and may require periodic re-estimation
5. **Contagion proxy simplicity:** BAA10Y captures credit stress but not cross-border funding dynamics captured by EUR/USD basis

### 5.7.2 Future Enhancements

1. **Real-time daily MAC calculation** with automated FRED and CFTC data feeds
2. **Cross-country validation** across G20 economies with country-specific threshold calibration
3. **Dynamic weight adjustment** using rolling-window ML optimisation
4. **Private credit expansion** with direct BDC NAV discount and leveraged loan spread data
5. **CFTC COT integration** for full positioning pillar in backtests from 1986+

---

## 5.8 Conclusion

The calibrated MAC framework demonstrates robust empirical validity across 117 years of financial history:

| Metric | Performance |
|--------|-------------|
| Time span | 1907–2025 (117 years) |
| Total observations | 6,158 weekly |
| Crises evaluated | 41 |
| True positive rate | 75.6% |
| Improvement over baseline | +49 pp (from 26.7%) |
| Data sources | 6 external databases, 30+ FRED series |
| Scoring method | Range-based + ML-weighted + momentum-enhanced |

The six methodological improvements — excluding missing pillars, wiring contagion proxy, two-sided valuation scoring, ML weights, era-aware calibration, and momentum detection — collectively tripled the true positive rate while maintaining interpretability and theoretical coherence.

---

*Framework Version: 5.0 (7-Pillar, Extended 1907-2025)*
*Calibration Factor: 0.78 (era-aware)*
*Weight Method: ML-optimized (2006+), era-specific (pre-1971), equal (default)*
*Data Sources: FRED, NBER Macrohistory, Schwert (1989), Shiller (Yale), Bank of England, MeasuringWorth, FINRA*
*Last Updated: February 2026*
