# MAC Framework v6 Implementation Plan

**Source:** `docs/new_methodology/MAC_Methodology_Document_v6.md` (2,526 lines)
**Target Codebase:** `grri_mac/` module tree
**Estimated Scope:** 12 work packages, ~3,500–5,000 new/modified lines

---

## Executive Summary

The v6 methodology document introduces **12 material changes** to the MAC framework. These range from complete module rewrites (policy pillar, private credit decorrelation) to new analytical capabilities (SVAR cascade estimation, precision-recall framework, sovereign bond proxy). The changes are grouped into three priority tiers:

- **P0 (Core Model Changes):** Changes that alter MAC score computation — must be implemented and validated together
- **P1 (Validation & Analytics):** Changes that improve validation rigour and client-facing analytics
- **P2 (Extensions):** New capabilities (multi-country, sovereign proxy) that extend the framework without changing existing scores

---

## P0 — Core Model Changes (Alters MAC Scores)

### WP-1: Policy Pillar — Binding Constraint Architecture

**v6 Reference:** §4.5
**Files to Modify:**
- `grri_mac/pillars/policy.py` — **Complete rewrite of `calculate()` method**
- `grri_mac/backtest/calibrated_engine.py` — Update `score_policy()` to use binding constraint
- `grri_mac/mac/composite.py` — Update `ML_OPTIMIZED_WEIGHTS["policy"]` from 0.09 → 0.12–0.15

**Current Implementation:**
- Equal-weighted average of 4 sub-scores: `(rate_room + balance_sheet + inflation + fiscal_space) / 4`
- Symmetric inflation scoring (abs deviation from target)

**Required Changes:**

1. **Replace weighted average with min-function:**
   ```python
   pillar_5 = min(rate_room, inflation, bs_capacity, fiscal_space)
   ```

2. **Add weighted-average fallback safeguard:**
   When `max(scores) - min(scores) ≤ 0.25`, revert to weighted average:
   - Inflation 35%, Rate room 25%, B/S 20%, Fiscal 20%

3. **Asymmetric inflation scoring:**
   - Above target: penalised more heavily (inflation above target directly constrains cutting)
   - Below target: mild penalty (deflation risk but less operationally binding)
   - New thresholds needed for asymmetric bands

4. **New inflation proxy chain** (for historical backtest):
   - Core PCE (1959+)
   - CPI-U (1947–1959)
   - CPI NSA (1913–1947)
   - Rees Cost of Living Index (1890–1913)
   - Warren-Pearson WPI × 1/1.5 (1850–1890)

5. **Historical constraint caps by era:**
   - Pre-Fed (1907–1913): cap at 0.30
   - Early Fed + Gold Standard (1913–1934): cap at 0.55, add gold reserve ratio constraint
   - Bretton Woods (1944–1971): fixed 0.65 constraint

6. **Update ML weights** for policy: 0.09 → 0.12–0.15

**Validation:** Reproduce worked examples from §4.5:
- COVID 2020 → 0.25
- SVB 2023 → 0.15
- 1929 Crash → 0.45
- Stagflation 1974 → 0.05

**Estimated Effort:** ~300 lines modified/new

---

### WP-2: Private Credit Decorrelation

**v6 Reference:** §4.7.1–4.7.8
**Files to Modify:**
- `grri_mac/pillars/private_credit.py` — Major addition: decorrelation engine
- New file: `grri_mac/pillars/private_credit_decorrelation.py` (recommended)

**Current Implementation:**
- 4 signal sources (SLOOS, BDC, leveraged loans, PE firms) with fixed-weight composite
- No decorrelation against equity/credit factors
- Thresholds in percentage points

**Required Changes:**

1. **Rolling OLS regression module:**
   - 252-day rolling window
   - Regressors: SPX returns, VIX level changes, HY OAS changes
   - Extract residual = orthogonal private-credit-specific signal

2. **EWMA smoothing:**
   - 12-week EWMA (λ = 0.154) of standardised residuals

3. **New composite weighting:**
   - 60% decorrelated market signal + 40% SLOOS

4. **New threshold scale** (σ-units, not percentage points):
   - Normal: > −0.5σ
   - Elevated: −0.5σ to −1.5σ
   - Severe: < −2.0σ

5. **Dependencies:** Requires `numpy` for OLS (already in requirements), or `statsmodels` for rolling regression

**Validation cases:**
- COVID 2020: raw −22% → decorrelated −1.3σ
- Late 2022: −8% raw → −1.8σ decorrelated
- Q4 2018: −12% raw → −0.4σ (benign — equity-driven, not private credit)

**Estimated Effort:** ~250 lines new

---

### WP-3: VRP Time-Varying Estimation

**v6 Reference:** §4.4.5
**Files to Modify:**
- `grri_mac/pillars/volatility.py` — Add time-varying VRP calculation
- `grri_mac/historical/fred_historical.py` — Ensure vol-of-vol history available
- `grri_mac/backtest/calibrated_engine.py` — Apply VRP in historical volatility scoring

**Current Implementation:**
- Fixed VRP multipliers: Schwert vol × 1.3 (pre-1990), NASDAQ RV × 1.2 (1971–1990)
- No dynamic adjustment

**Required Changes:**

1. **Time-varying VRP formula:**
   ```python
   VRP_t = 1.05 + 0.015 * std(vol_of_vol, window=52)  # 12-month rolling
   VRP_t = clip(VRP_t, 1.05, 1.55)
   ```

2. **Dual computation with quality flag:**
   - Primary: time-varying VRP
   - Robustness check: fixed VRP
   - If composite MAC differs > 0.05 between approaches, report both with quality flag

3. **Sensitivity table implementation** for documentation/dashboard:
   - Static table showing VRP impact on volatility scores across regimes

**Estimated Effort:** ~100 lines modified/new

---

### WP-4: Breach Interaction Penalty — Combinatorial Derivation

**v6 Reference:** §6.3
**Files to Modify:**
- `grri_mac/mac/composite.py` — Add derivation code alongside existing penalty table
- `grri_mac/backtest/calibration.py` — Add penalty derivation validation

**Current Implementation:**
- Fixed lookup: `{0: 0, 1: 0, 2: 0.03, 3: 0.08, 4: 0.12, 5+: 0.15}`
- No derivation trail

**Required Changes:**

1. **Add derivation function** (binomial independence model → observed excess ratio → log-ratio):
   ```python
   π(n) = min(0.15, γ * ln(f_obs(n) / f_indep(n)))
   ```
   Where `f_indep(n)` = binomial(K, n, p_hat), and `f_obs(n)` from crisis dataset

2. **Sensitivity analysis code:**
   - Perturb breach threshold (0.25, 0.30, 0.35) and pooled probability (0.10, 0.125, 0.15)
   - Confirm penalty values stable within ±0.02

3. **Result:** Same numerical penalties, now with auditable derivation

**Estimated Effort:** ~80 lines new

---

## P1 — Validation & Analytics

### WP-5: Crisis Severity Rubric (CSR)

**v6 Reference:** §13.2
**Files to Create:**
- New: `grri_mac/backtest/crisis_severity_rubric.py`
**Files to Modify:**
- `grri_mac/backtest/calibration.py` — Use CSR targets instead of legacy severity labels

**Required Implementation:**

1. **5-dimension rubric scorer:**
   - Drawdown magnitude (S&P 500)
   - Market functioning disruption (categorical)
   - Policy response intensity (categorical)
   - Contagion breadth (categorical)
   - Duration of acute stress (VIX-based)

2. **CSR data for 14 modern scenarios** (hardcoded from §13.2.4 table)

3. **Calibration factor re-derivation** using CSR targets:
   ```python
   α* = argmin_α Σ |α * MAC_raw(i) - CSR(i)| / N
   ```

4. **Independence verification documentation**

**Estimated Effort:** ~200 lines new

---

### WP-6: Thematic Holdout Validation

**v6 Reference:** §13.4
**Files to Create:**
- New: `grri_mac/backtest/thematic_holdout.py`

**Required Implementation:**

1. **5 holdout sets** (A–E) with pre-specified scenario groupings:
   - A: Positioning / Hedge Failure (Volmageddon, COVID, Apr 2025)
   - B: Systemic Credit / Banking (Bear Stearns, Lehman, SVB)
   - C: Exogenous / Geopolitical (9/11, COVID, Russia–Ukraine)
   - D: Extreme Severity (LTCM, Lehman, COVID)
   - E: Moderate / Low-Impact (Dot-com Peak, Flash Crash, Volmageddon, Russia–Ukraine)

2. **Validation protocol:**
   - Re-derive α on training set for each holdout
   - Compute OOS MAE
   - Check acceptance criteria (Δα < 0.05, OOS MAE < 0.15, α range < 0.08)

3. **Diagnostic protocol** for failures (Cases 1–3 from §13.4.8)

4. **Results reporting template** (markdown/JSON output)

**Estimated Effort:** ~250 lines new

---

### WP-7: False Positive Analysis & Precision-Recall Framework

**v6 Reference:** §15.6–15.7
**Files to Create:**
- New: `grri_mac/backtest/precision_recall.py`
**Files to Modify:**
- `grri_mac/backtest/runner.py` — Add FPR/precision/recall computation to backtest output
- `grri_mac/mac/momentum.py` — Add configurable τ parameter

**Required Implementation:**

1. **Definitions framework:**
   - Signal: MAC < τ (or momentum DETERIORATING+)
   - Crisis window: ±6 weeks around each of 41 event dates
   - Lead time allowance: 8 weeks before event = TP, not FP

2. **Precision-recall curve computation:**
   - Sweep τ from 0.10 to 0.80 (step 0.01)
   - At each τ: count TP, FP, FN
   - Compute precision, recall, F₁, F₀.₅, F₂

3. **Fβ objective with client archetype mapping:**
   - Sovereign wealth fund: β=2.0
   - Central bank: β=1.0
   - Macro hedge fund: β=0.5
   - Insurance/pension: β=1.5

4. **Client-configurable operating point:**
   ```python
   mac.set_alert_threshold(tau=0.40)  # Conservative
   mac.set_alert_threshold(tau=0.60)  # Sensitive
   ```

5. **FPR by era** (separate computation per era)

6. **False positive taxonomy** (near-miss, regime-artefact, genuine)

7. **JSON artefact output** for precision-recall curve (71 data points)

**Estimated Effort:** ~400 lines new

---

### WP-8: Positioning–Hedge Failure Statistical Reframing

**v6 Reference:** §7.4 (expanded §4.3)
**Files to Modify:**
- `grri_mac/mac/ml_weights.py` — Update documentation/comments
- `grri_mac/mac/composite.py` — Update comments from "100% correlation" to "necessary condition"
- `grri_mac/backtest/scenarios.py` — Ensure 14th scenario (April 2025 Tariffs) is present

**Required Changes:**

1. **Documentation updates:**
   - Replace "100% correlation" language with "necessary condition, N=3"
   - Add Fisher's exact test p-value (0.0027)
   - Add Bayesian posterior: Beta(4,1), mean 0.80, 90% CI [0.44, 0.98]

2. **Add monitoring hook:**
   - Flag for future update when first positioning breach without hedge failure is observed
   - Comment block with recalibration trigger specification

3. **No code logic change** — weights and override remain the same (justified even at lower bound ~0.50 probability)

**Estimated Effort:** ~50 lines of documentation updates

---

## P2 — Extensions (New Capabilities)

### WP-9: SVAR-Based Cascade Propagation

**v6 Reference:** §10.2
**Files to Create:**
- New: `grri_mac/predictive/cascade_var.py`
**Files to Modify:**
- `grri_mac/predictive/shock_propagation.py` — Replace hardcoded `INTERACTION_MATRIX` with SVAR-estimated coefficients

**Required Implementation:**

1. **SVAR estimation pipeline:**
   - Input: weekly pillar score time series (1997–2025, ~1,450 observations)
   - VAR specification on ΔP_t with BIC lag selection (L ∈ {1,2,3,4})
   - Cholesky identification with ordering: Policy → Valuation → Contagion → Liquidity → Volatility → Positioning

2. **Robustness:**
   - Test all 720 permutations of 6-pillar ordering
   - Report median IRF with 10th/90th percentile bounds
   - Compute GIRFs (Pesaran & Shin 1998) as ordering-invariant check

3. **Coefficient extraction:**
   - 4-week cumulative impulse response functions (CIRF at h=4)
   - Normalise to [−1, 1]

4. **Regime-dependent acceleration:**
   - Re-estimate SVAR on normal (MAC > 0.50) vs stress (MAC ≤ 0.50) subsamples
   - Compute acceleration factor α_ij = |Φ_stress| / |Φ_normal|
   - Apply in cascade simulation when pillar < τ_crit

5. **Validation:**
   - Scenario reproduction (14 scenarios, MAE < 0.10)
   - Granger causality tests
   - Out-of-sample (train 1997–2018, test 2019–2025)

6. **Dependencies:** `statsmodels.tsa.vector_ar`, `scipy.linalg.cholesky`
   - Add `statsmodels` to `requirements.txt` if not already present

**Estimated Effort:** ~500 lines new

---

### WP-10: Sovereign Bond Proxy Architecture (Multi-Country)

**v6 Reference:** §16.2
**Files to Create:**
- New: `grri_mac/historical/sovereign_proxy.py`
**Files to Modify:**
- `grri_mac/mac/multicountry.py` — Integrate sovereign proxy for historical periods

**Required Implementation:**

1. **Sovereign stress spread construction:**
   ```
   SS_j,t = y_gov_j,t - y_bench_t
   ```
   Era-dependent benchmark: UK Consol (1815–1913), blend (1914–1944), US 10Y (1945+)

2. **Overlap calibration (1990–2025):**
   - Quadratic mapping: MAC_proxy = a - b·SS + c·SS²
   - Per-country coefficients

3. **Data source integration:**
   - BoE Millennium of Macroeconomic Data (UK, from 1694)
   - Shiller (US, from 1871)
   - NBER Macrohistory (US/UK, from 1857)
   - Meyer-Reinhart-Trebesch (91 countries, from 1815)
   - Homer & Sylla (global, varies)

4. **Uncertainty bands:** 80% confidence from regression residual SE

5. **Country-specific modules:**
   - UK: Consols from ~1729, Bank Rate from 1694
   - Euro area: pre/post-1999 structural break handling
   - Japan: supplemental indicators post-1995 (BoJ rate, TOPIX vol, yen basis)
   - China: modern data only (post-2005), flagged as limited

**Note:** This is a research-stage extension. Data acquisition for historical sovereign bonds is non-trivial. Implementation should start with UK (deepest data) as proof of concept.

**Estimated Effort:** ~400 lines new (UK POC), ~800 for full multi-country

---

### WP-11: Backtest Enhancements

**v6 Reference:** §14, §15
**Files to Modify:**
- `grri_mac/backtest/runner.py` — Add Fixes A–F documentation, FPR reporting
- `grri_mac/backtest/scenarios.py` — Ensure April 2025 Tariffs is in KNOWN_EVENTS

**Required Changes:**

1. **Ensure all 6 methodological fixes (A–F) are documented in code:**
   - Fix A: Exclude missing pillars (check `has_data`)
   - Fix B: BAA10Y contagion proxy
   - Fix C: Range-based valuation scoring
   - Fix D: ML-optimised weights for modern era
   - Fix E: Era-aware calibration factor
   - Fix F: Momentum-enhanced warning detection

2. **Add per-era detection rate reporting** (table in §15.2)

3. **Add data quality tier labelling** (Excellent/Good/Fair/Poor per §15.5)

**Estimated Effort:** ~100 lines modified

---

### WP-12: Inflation Proxy Chain (Historical)

**v6 Reference:** §4.5.3 (within Policy pillar)
**Files to Modify:**
- `grri_mac/historical/fred_historical.py` — Add inflation proxy chain
- New: `grri_mac/data/inflation_proxies.py` (if external data files needed)

**Required Implementation:**

1. **Chain logic:**
   ```python
   def get_inflation_for_date(date):
       if date >= 1959: return core_pce(date)      # FRED PCEPILFE
       if date >= 1947: return cpi_u(date)          # FRED CPIAUCSL
       if date >= 1913: return cpi_nsa(date)        # FRED CPIAUCNS
       if date >= 1890: return rees_cost_of_living(date)  # External dataset
       if date >= 1850: return warren_pearson_wpi(date) / 1.5  # External × scale factor
   ```

2. **Data sourcing:**
   - FRED series for CPI (1913+) and Core PCE (1959+) — already available
   - Rees (1961) Cost of Living Index (1890–1914) — may need external CSV
   - Warren-Pearson Wholesale Price Index (1850–1890) — may need external CSV

3. **Integration with policy pillar** for pre-1959 backtest periods

**Estimated Effort:** ~120 lines new

---

## Dependency Graph

```
WP-12 (Inflation Proxy) ──┐
                           ├── WP-1 (Policy Rewrite) ──┐
WP-3 (VRP Time-Varying) ──┘                            │
                                                        ├── WP-5 (CSR) ──── WP-6 (Thematic Holdout)
WP-2 (Pvt Credit Decorr) ─────────────────────────────┤
                                                        ├── WP-7 (Precision-Recall)
WP-4 (Breach Penalty Derivation) ─────────────────────┤
                                                        ├── WP-11 (Backtest Enhancements)
WP-8 (Positioning Reframing) ── independent ───────────┘

WP-9 (SVAR Cascade) ──── independent (can be done in parallel)
WP-10 (Sovereign Proxy) ── independent, research-stage
```

## Recommended Implementation Order

| Phase | Work Packages | Rationale |
|-------|--------------|-----------|
| **Phase 1** | WP-8, WP-4, WP-12 | Low-risk: documentation + derivation code + data chain. No score changes yet. |
| **Phase 2** | WP-1, WP-3 | Core model changes (policy rewrite + VRP). Policy is the biggest single change. |
| **Phase 3** | WP-2 | Private credit decorrelation. Can be validated independently. |
| **Phase 4** | WP-5, WP-6 | CSR + thematic holdout. Validates the calibration factor against new targets. |
| **Phase 5** | WP-7, WP-11 | Precision-recall framework + backtest enhancements. Client-facing analytics. |
| **Phase 6** | WP-9 | SVAR cascade. Research-heavy; requires pillar time series + statsmodels. |
| **Phase 7** | WP-10 | Sovereign bond proxy. Research-stage; start with UK proof-of-concept. |

## New Dependencies

| Package | Required By | Already in requirements.txt? |
|---------|------------|------------------------------|
| `numpy` | WP-2 (OLS), WP-9 (SVAR) | Check |
| `statsmodels` | WP-9 (VAR estimation) | Check — likely needs adding |
| `scipy` | WP-9 (Cholesky), WP-4 (binomial) | Check |

## Testing Strategy

Each WP should include:
1. **Unit tests** in `grri_mac/tests/` for new functions
2. **Regression tests** — run existing backtest before/after and document score changes
3. **Worked example validation** — reproduce the specific numerical examples from the v6 document
4. **Integration test** — full 1907–2025 backtest with all changes applied

### Critical Validation Gates

| Gate | Criterion | Blocks |
|------|-----------|--------|
| Policy worked examples match | COVID=0.25, SVB=0.15, 1929=0.45, 1974=0.05 (±0.05) | Phase 2 → Phase 4 |
| Private credit validation cases match | COVID=-1.3σ, Late 2022=-1.8σ, Q4 2018=-0.4σ (±0.3σ) | Phase 3 → Phase 4 |
| CSR composite matches table | 14 scenarios within ±0.05 of §13.2.4 values | Phase 4 → Phase 5 |
| Thematic holdout passes all 4 acceptance criteria | Δα < 0.05, OOS MAE < 0.15, etc. | Phase 4 complete |
| Full backtest TPR ≥ 73% | TPR must not degrade by more than 3pp from 75.6% | All phases |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Policy min-function drops TPR for moderate crises | Medium | Weighted-average fallback (gap ≤ 0.25) preserves detection |
| Private credit decorrelation requires pandas/numpy not in Function App | Medium | These are already standard; verify Azure Functions compatibility |
| SVAR estimation on ~1,450 weekly obs may be unstable | High | Bootstrap CIs, GIRF robustness check, regularisation |
| Historical inflation data (Rees, Warren-Pearson) not in FRED | Medium | Ship as CSV in `data/`; document provenance |
| Sovereign bond data acquisition is manual/research-heavy | Low | Defer UK POC to Phase 7; not blocking core model |

---

*Plan created: based on full reading of MAC_Methodology_Document_v6.md (2,526 lines)*
*Codebase files audited: policy.py, private_credit.py, volatility.py, composite.py, calibration.py, calibrated_engine.py, shock_propagation.py, momentum.py, ml_weights.py*
