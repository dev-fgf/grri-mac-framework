# Positioning → Hedge Failure: Caveat on Small N

## Summary

The MAC framework's key empirical finding — that **positioning breach predicts Treasury hedge failure** — is based on a small sample (N=9 documented episodes, of which N=2 are severe + positioning-breached). This document formally documents the statistical limitations and the Bayesian approach used to handle them.

---

## The Claim

> When the positioning pillar is in breach (score < 0.20), Treasury bonds are more likely to fail as an equity hedge during a selloff.

This is the framework's most actionable signal: it tells a 60/40 portfolio manager when their "safe" allocation may not provide the expected diversification benefit.

## The Evidence

### Expanded Episode Catalogue (N=9)

| # | Date | Episode | 10Y Return | S&P Return | Pos Breach? | Basis Unwind? | Severity |
|---|------|---------|-----------|-----------|-------------|--------------|----------|
| 1 | 1994-02 | Bond Massacre | -1.8% | -2.7% | Yes | No | Moderate |
| 2 | 1999-06 | Rate Scare | -1.2% | -1.5% | No | No | Mild |
| 3 | 2003-07 | Bond Tantrum | -2.5% | -1.0% | Yes | No | Moderate |
| 4 | 2013-06 | Taper Tantrum | -2.0% | -1.4% | Yes | No | Moderate |
| 5 | 2016-11 | Trump Election | -2.2% | +1.1% | No | No | Mild |
| 6 | 2018-02 | Volmageddon | -1.0% | -2.2% | Yes | No | Mild |
| 7 | 2020-03 | COVID Dash-for-Cash | -3.0% | -9.5% | Yes | Yes | Severe |
| 8 | 2022-09 | UK LDI Spillover | -1.2% | -1.8% | No | No | Mild |
| 9 | 2025-04 | Tariff Shock | -2.5% | -4.8% | Yes | Yes | Severe |

### Pattern

- **6/9 episodes** had positioning breach
- **2/2 severe episodes** had positioning breach AND basis trade unwind
- **0/3 non-breach episodes** were severe
- Positioning breach appears **necessary but not sufficient** for severe hedge failure

## Bayesian Analysis

### Model

We use a Beta-Binomial conjugate model:
- **Prior**: Beta(1, 1) — uninformative (no strong prior belief)
- **Data**: Out of 6 positioning-breached episodes, 2 were severe
- **Posterior**: Beta(3, 5)

### Results

```
P(severe hedge failure | positioning breach) ≈ 0.375
90% Credible Interval: [0.12, 0.67]
```

### Interpretation

The posterior mean of 0.375 means that roughly 1 in 3 positioning breaches leads to severe hedge failure. The wide 90% CI (0.12 to 0.67) reflects the small sample.

## What This Means for Users

### What we CAN say:
1. Positioning breach is a **necessary condition** — all severe episodes had it
2. The directional signal is robust — positioning breach correlates with hedge failure
3. The framework correctly identified the mechanism (crowded trades + leverage)

### What we CANNOT say:
1. The exact probability of hedge failure given breach (CI is wide)
2. Whether future episodes will follow the same pattern
3. That positioning breach is the only relevant factor

## Recommendations

1. **Treat as a warning flag, not a certainty**: When positioning pillar breaches, increase monitoring and consider supplementary hedges (options, VIX calls) alongside Treasuries
2. **Watch the sub-indicators**: Basis trade size, speculative net positioning, and primary dealer leverage together matter more than any single number
3. **Update the prior**: As new episodes occur, the Bayesian posterior will tighten. The framework automatically recomputes with new data
4. **Do not over-condition on N=2**: The severe episodes (COVID 2020, Tariff 2025) may share unique features (pandemic, trade war) that don't generalise

## Code Reference

- Episode catalogue: `grri_mac/pillars/hedge_failure_analysis.py`
- Bayesian posterior: `HedgeFailureDetector.bayesian_posterior()`
- Positioning pillar scoring: `grri_mac/pillars/positioning.py`
