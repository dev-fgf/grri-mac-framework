# GRRI-MAC Framework: Technical Specification

## Overview

This project implements a geopolitical transmission framework with two components:
- **GRRI (Global Risk and Resilience Index)**: Country-level absorption capacity
- **MAC (Market Absorption Capacity)**: Market-level absorption capacity

The core equation: `Market Impact = Shock × GRRI Modifier × MAC Multiplier`

---

## MAC Framework

### The Five Pillars

Each pillar scores 0-1 (1 = ample buffer, 0 = breached).

#### 1. Liquidity
**Question**: Can markets transact without disorderly price impact?

| Indicator | Source | Ample | Thin | Breaching |
|-----------|--------|-------|------|-----------|
| SOFR-IORB spread | FRED: SOFR, IORB | < 5 bps | 5-25 bps | > 25 bps |
| CP-Treasury spread | FRED: DCPF3M, DGS3MO | < 20 bps | 20-50 bps | > 50 bps |
| Cross-currency basis (EUR/USD) | Bloomberg | > -30 bps | -30 to -75 bps | < -75 bps |
| Treasury bid-ask | Bloomberg | < 1/32 | 1-2/32 | > 2/32 |

#### 2. Valuation
**Question**: Are risk premia adequate buffers?

| Indicator | Source | Ample | Thin | Breaching |
|-----------|--------|-------|------|-----------|
| 10Y term premium | FRED: THREEFYTP10 (ACM) | > 100 bps | 0-100 bps | < 0 bps |
| IG OAS | FRED: BAMLC0A0CM | > 150 bps | 80-150 bps | < 80 bps |
| HY OAS | FRED: BAMLH0A0HYM2 | > 450 bps | 300-450 bps | < 300 bps |

#### 3. Positioning
**Question**: Is leverage manageable and positioning diverse?

| Indicator | Source | Ample | Thin | Breaching |
|-----------|--------|-------|------|-----------|
| Basis trade size | Fed estimates, proxy | < $400B | $400-700B | > $700B |
| Treasury spec net (%-ile) | CFTC COT | 25th-75th | 10th-90th | < 5th or > 95th |
| SVXY AUM | ETF data | < $500M | $500M-1B | > $1B |

#### 4. Volatility
**Question**: Is the vol regime stable?

| Indicator | Source | Ample | Thin | Breaching |
|-----------|--------|-------|------|-----------|
| VIX level | FRED: VIXCLS | 15-20 | < 12 or 20-35 | < 10 or > 35 |
| VIX term structure (M2/M1) | CBOE | 1.00-1.05 | < 0.95 or > 1.08 | < 0.90 or > 1.10 |
| Realized vs implied | Calculate | RV within 20% of IV | 20-40% gap | > 40% gap |

#### 5. Policy
**Question**: Does the central bank have capacity to respond?

| Indicator | Source | Ample | Thin | Breaching |
|-----------|--------|-------|------|-----------|
| Fed funds vs neutral | FRED: DFEDTARU, estimate neutral ~2.5% | Within 100 bps | 100-200 bps | > 200 bps or at ELB |
| Fed balance sheet / GDP | FRED: WALCL, GDP | < 25% | 25-35% | > 35% |
| Core PCE vs target | FRED: PCEPILFE | Within 50 bps of 2% | 50-150 bps | > 150 bps |

---

### Pillar Scoring Logic

```python
def score_indicator(value, ample_range, thin_range, breach_threshold):
    """
    Returns 0-1 score where:
    - 1.0 = ample (full buffer)
    - 0.5 = thin (buffer depleted)
    - 0.0 = breaching (buffer gone)
    
    Interpolate linearly between thresholds.
    """
    pass

def score_pillar(indicators: dict) -> float:
    """
    Average indicator scores within pillar.
    Return both composite and individual scores.
    """
    pass
```

### MAC Composite

```python
def calculate_mac(pillars: dict, weights: dict = None) -> float:
    """
    Weighted average of pillar scores.
    Default: equal weights (0.2 each).
    
    Returns:
    - mac_score: 0-1 composite
    - pillar_scores: dict of individual scores
    - breach_flags: list of pillars < 0.2
    """
    if weights is None:
        weights = {p: 0.2 for p in pillars}
    
    mac = sum(pillars[p] * weights[p] for p in pillars)
    breach_flags = [p for p, score in pillars.items() if score < 0.2]
    
    return mac, pillars, breach_flags
```

### MAC Multiplier

```python
def mac_to_multiplier(mac: float, alpha: float = 2.0, beta: float = 1.5) -> float:
    """
    Convert MAC score to transmission multiplier.
    
    Formula: 1 + alpha * (1 - mac)^beta
    
    Examples:
    - MAC 1.0 → 1.0× (ample)
    - MAC 0.5 → 1.6× (thin)
    - MAC 0.3 → 2.3× (stretched)
    - MAC < 0.2 → return None, flag regime break
    """
    if mac < 0.2:
        return None  # Regime break - don't trust point estimates
    
    return 1 + alpha * ((1 - mac) ** beta)
```

---

## GRRI Framework

Four pillars measuring country resilience:
- **Political**: Rule of law, governance quality, institutional strength
- **Economic**: GDP diversity, CB independence, fiscal space
- **Social**: HDI, inequality, social cohesion
- **Environmental**: Climate risk exposure, green transition progress

GRRI Modifier formula:
```python
def grri_to_modifier(resilience: float) -> float:
    """
    Logistic transformation.
    - resilience > 0.5 → modifier < 1 (compressed transmission)
    - resilience < 0.5 → modifier > 1 (amplified transmission)
    """
    return 2 / (1 + math.exp(4 * (resilience - 0.5)))
```

---

## China Integration

### China Leverage Activation Score

Track five vectors (each 0-1, composite is average):

| Vector | Latent (0) | Elevated (0.5) | Activated (1.0) |
|--------|------------|----------------|-----------------|
| Treasury holdings | Stable | Flat | Declining > $50B/qtr |
| Rare earth policy | Open | Licensing required | Quantity restrictions |
| Tariff level | < 10% | 10-25% | > 25% |
| Taiwan tension | Baseline | Elevated rhetoric | Military exercises |
| CIPS growth | < 20% YoY | 20-50% YoY | > 50% YoY |

### MAC Adjustment for China

```python
def adjust_mac_for_china(raw_mac: float, china_activation: float) -> float:
    """
    China activation pre-depletes MAC.
    
    Adjustment: MAC × (1 - 0.3 × activation)
    
    At activation 0.7: MAC reduced by 21%
    At activation 1.0: MAC reduced by 30%
    """
    return raw_mac * (1 - 0.3 * china_activation)
```

---

## Data Architecture

### Primary Data Sources

**FRED (free, reliable)**:
- Treasury yields: DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS5, DGS10, DGS30
- Credit spreads: BAMLC0A0CM (IG), BAMLH0A0HYM2 (HY)
- Funding: SOFR, IORB, EFFR, DCPF3M
- Vol: VIXCLS
- Term premium: THREEFYTP10
- Macro: GDP, PCEPILFE, WALCL

**CFTC (weekly)**:
- Commitments of Traders for Treasury futures positioning

**ETF Proxies (daily)**:
- Volatility positioning: SVXY, UVXY AUM/flows
- Leveraged equity: TQQQ, SQQQ
- Credit: LQD, HYG flows

### Update Frequency

| Data | Frequency | Source |
|------|-----------|--------|
| Yields, spreads, VIX | Daily | FRED |
| ETF flows | Daily | Yahoo Finance / provider |
| COT positioning | Weekly (Tuesday data, Friday release) | CFTC |
| Term premium | Monthly | FRED |
| Balance sheet | Weekly | FRED |
| Basis trade estimate | Quarterly (interpolate) | Fed research |

---

## Key Outputs

### Daily Dashboard
- MAC composite score (0-1)
- Individual pillar scores
- Breach flags (any pillar < 0.2)
- Transmission multiplier
- China activation score (if tracking)

### Alerts
- Any pillar crosses from Ample → Thin
- Any pillar crosses from Thin → Breaching
- MAC composite < 0.4
- MAC composite < 0.2 (regime break warning)

### Historical Context
- Current MAC vs. historical distribution
- Percentile ranking
- Comparison to key episodes (Feb 2018, Mar 2020, Apr 2025)

---

## Historical Reference Points

| Event | Date | MAC | Key Breach | Treasury Hedge |
|-------|------|-----|------------|----------------|
| Volmageddon | Feb 2018 | 0.35 | Volatility, Positioning | Worked |
| Repo spike | Sep 2019 | 0.55 | Liquidity | Worked |
| COVID crash | Mar 2020 | 0.18 | Liquidity, Positioning, Volatility | **Failed** |
| Ukraine invasion | Feb 2022 | 0.62 | None | Worked |
| April tariffs | Apr 2025 | 0.35 | Positioning | **Failed** |

**Key insight**: Every time Treasuries failed as a hedge, Positioning pillar was breaching.

---

## File Structure Suggestion

```
grri-mac/
├── data/
│   ├── fred.py          # FRED API wrapper
│   ├── cftc.py          # COT data parser
│   ├── etf.py           # ETF data (Yahoo/other)
│   └── cache/           # Local data cache
├── pillars/
│   ├── liquidity.py
│   ├── valuation.py
│   ├── positioning.py
│   ├── volatility.py
│   └── policy.py
├── mac/
│   ├── scorer.py        # Pillar scoring logic
│   ├── composite.py     # MAC calculation
│   └── multiplier.py    # Transmission multiplier
├── china/
│   ├── activation.py    # China leverage score
│   └── adjustment.py    # MAC adjustment
├── grri/
│   └── modifier.py      # GRRI → modifier transformation
├── dashboard/
│   ├── daily.py         # Daily MAC report
│   └── alerts.py        # Threshold alerts
└── tests/
    └── historical.py    # Backtest against known events
```

---

## Testing Against History

Critical validation: run framework against known events and verify:

1. **March 2020**: MAC should show < 0.2, multiple breach flags
2. **February 2022**: MAC should show > 0.5, no breach flags  
3. **April 2025**: MAC should show ~0.35, Positioning breach flag

If framework doesn't flag these correctly, calibration is wrong.
