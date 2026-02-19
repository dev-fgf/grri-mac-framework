# Executive Decision Matrix

## MAC Level × Momentum → Portfolio Action

This matrix maps the MAC score and its directional momentum to recommended portfolio actions, calibrated for four client archetypes.

---

## Signal Definitions

| MAC Level | Score Range | Interpretation |
|-----------|-------------|----------------|
| **Ample** | ≥ 0.65 | Markets can absorb shocks; full risk budget available |
| **Thin** | 0.50 – 0.65 | Reduced capacity; monitor closely |
| **Stretched** | 0.35 – 0.50 | Stress building; reduce risk, consider hedges |
| **Breach** | < 0.35 | Crisis-level; maximum hedging, defensive posture |

| Momentum | Definition | Signal |
|----------|------------|--------|
| **Improving** | MAC rose > 0.02 over 4 weeks | Recovery underway |
| **Stable** | MAC changed < 0.02 over 4 weeks | No directional shift |
| **Deteriorating** | MAC fell > 0.02 over 4 weeks | Stress accelerating |

---

## Decision Matrix by Client Archetype

### Sovereign Wealth Fund (β = 2.0 — recall-biased)

| | Improving | Stable | Deteriorating |
|---|---|---|---|
| **Ample** | Full risk budget | Full risk budget | Begin monitoring; no action yet |
| **Thin** | Maintain positions | Reduce illiquid exposure 10% | Reduce risk 20%; add tail hedges |
| **Stretched** | Hold; await confirmation | Reduce risk 30%; hedge duration | Reduce risk 50%; max hedges |
| **Breach** | Begin re-risking cautiously | Defensive; 50% hedge overlay | Maximum defence; full hedge overlay |

### Central Bank / Reserve Manager (β = 1.0 — balanced)

| | Improving | Stable | Deteriorating |
|---|---|---|---|
| **Ample** | Normal operations | Normal operations | Review liquidity buffers |
| **Thin** | Normal operations | Extend liquidity buffers | Activate contingency facilities |
| **Stretched** | Monitor for reversal | Pre-position swap lines | Activate swap lines; reduce duration |
| **Breach** | Cautious normalisation | Full crisis facilities | Emergency lending; unlimited liquidity |

### Macro Hedge Fund (β = 0.5 — precision-biased)

| | Improving | Stable | Deteriorating |
|---|---|---|---|
| **Ample** | Full risk; long vol cheaply | Full risk; neutral vol | Reduce gross; watch for entry |
| **Thin** | Selective risk; long quality | Reduce gross 20% | Short credit; long vol |
| **Stretched** | Cover shorts gradually | Net short; convex hedges | Maximum short; buy tails |
| **Breach** | Begin buying dislocations | Opportunistic buying | Wait for forced sellers; dry powder |

### Insurance / Pension (β = 1.5 — slight recall bias)

| | Improving | Stable | Deteriorating |
|---|---|---|---|
| **Ample** | SAA benchmark weights | SAA benchmark weights | Review LDI hedges |
| **Thin** | SAA benchmark weights | Increase collateral buffers | Reduce credit overweight; add govt bonds |
| **Stretched** | Hold; review at next rebalance | De-risk 20%; increase govt allocation | De-risk 40%; full LDI hedge |
| **Breach** | Begin normalising cautiously | Full defensive; max govt allocation | Emergency de-risk; liability matching only |

---

## Confidence Bands

When 90% CI is wide (> 0.15), signals are less reliable:
- **Wide CI + Ample**: Treat as Thin (err on cautious side)
- **Wide CI + Breach**: Treat as confirmed Breach (err on safe side)
- **Wide CI + Thin/Stretched**: Use the lower CI bound for decisions

## HMM Regime Overlay

When P(fragile) from the HMM overlay exceeds 0.6:
- Shift one row down in the matrix (e.g., Thin → Stretched actions)
- This captures regime persistence not visible in point-in-time MAC

---

## Operating Point Selection

| Archetype | Optimal τ* | Fβ* | FP tolerance |
|-----------|-----------|------|-------------|
| SWF | 0.55 | High | Higher (better safe) |
| Central Bank | 0.50 | Balanced | Moderate |
| Hedge Fund | 0.40 | High precision | Low (avoid false signals) |
| Insurance | 0.52 | Moderate | Moderate-high |

See `precision_recall.py` for full PR curve computation.
