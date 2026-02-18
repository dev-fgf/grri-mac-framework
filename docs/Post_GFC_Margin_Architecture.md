# Post-GFC Margin & Leverage Architecture

## Motivation

Since the 2008 Global Financial Crisis, leverage has migrated from regulated banks into new channels: crypto exchanges, 0DTE options, private credit, CLOs, and prime brokerage. The MAC framework must track these non-traditional leverage channels to avoid blind spots in its systemic risk assessment.

The current positioning pillar tracks **Treasury basis trades**, **CFTC speculator positioning**, and **SVXY AUM**. This document outlines the expanded architecture for monitoring margin across the full post-GFC leverage landscape.

---

## Leverage Channel Taxonomy

### Tier 1 — Currently Tracked (Data Available)

| Channel | Indicator | Pillar | Data Source | Status |
|---------|-----------|--------|-------------|--------|
| Treasury basis trade | Estimated $B from CFTC futures | Positioning | CFTC COT | Live |
| Speculator concentration | Treasury spec net %ile | Positioning | CFTC COT | Live |
| Short-vol exposure | SVXY AUM | Positioning | ETF providers | Live |
| Crypto-equity contagion | BTC-SPY 60d correlation | Contagion | Yahoo Finance | **New** |
| Private credit stress | C&I lending standards (SLOOS) | Private Credit | FRED | Live |
| HY spread (leveraged loan proxy) | HY OAS | Private Credit | FRED | Live |

### Tier 2 — Actionable Next (Free/Public Data)

| Channel | Proposed Indicator | Pillar | Data Source | FRED Series |
|---------|-------------------|--------|-------------|-------------|
| Retail margin debt | FINRA margin debt / market cap | Positioning | FRED | `BOGZ1FL663067003Q` |
| Fed repo facility | ON RRP usage $B | Liquidity | FRED | `RRPONTSYD` |
| Leveraged ETF AUM | Total 2x/3x ETF assets | Positioning | ETF providers | Manual |
| Crypto exchange reserves | BTC held on exchanges | Contagion | Glassnode (free tier) | N/A |

### Tier 3 — Aspirational (Proprietary/Delayed Data)

| Channel | Proposed Indicator | Source | Lag |
|---------|-------------------|--------|-----|
| Prime brokerage leverage | HF gross/net leverage | Fed SHF survey | Quarterly |
| 0DTE options gamma | Net dealer gamma exposure (GEX) | CBOE / OptionMetrics | Daily (paid) |
| CLO issuance rate | BSL CLO new issuance | LCD / PitchBook | Monthly |
| Total return swap (TRS) | Equity TRS notional | OFR | Quarterly |
| Crypto futures OI | BTC/ETH perpetual futures OI | CoinGlass / Coinalyze | Daily |

---

## Architecture: How Each Channel Maps to Pillars

```
                    ┌─────────────┐
                    │  Composite   │
                    │  MAC Score   │
                    └──────┬──────┘
                           │
        ┌──────┬───────┬───┴───┬───────┬──────────┬──────────┐
        │      │       │       │       │          │          │
   Liquidity  Val  Positioning Vol  Policy  Contagion  Priv Credit
        │             │                      │          │
   ┌────┴────┐  ┌─────┴──────┐         ┌────┴────┐  ┌──┴──┐
   │ SOFR-   │  │ Basis trade│         │ XCcy    │  │SLOOS│
   │ IORB    │  │ Spec net   │         │ basis   │  │ HY  │
   │ CP-Tsy  │  │ SVXY AUM   │         │ IG-HY   │  │ OAS │
   │ ON RRP* │  │ Margin     │         │ Fin OAS │  │     │
   │         │  │ debt*      │         │ BTC-SPY │  │     │
   │         │  │ 0DTE GEX** │         │ corr    │  │     │
   │         │  │ Lev ETF*   │         │ Crypto  │  │     │
   │         │  │ PB lev**   │         │ OI**    │  │     │
   └─────────┘  └────────────┘         └─────────┘  └─────┘

   * = Tier 2 (next to implement)
  ** = Tier 3 (aspirational, proprietary data)
```

---

## Tier 2 Implementation Plan

### 1. FINRA Margin Debt (Positioning Pillar)

**Rationale**: Retail and institutional margin debt relative to equity market capitalisation is a well-studied predictor of market fragility. Sharp margin debt growth preceded the 2000 dot-com bust, 2007-08 GFC, and 2021 meme-stock correction.

**Data**: FRED series `BOGZ1FL663067003Q` — Securities margin accounts at broker-dealers (quarterly, $B). Normalise by Wilshire 5000 total market cap (FRED `WILL5000PR`).

**Thresholds**:
- AMPLE: Margin debt / market cap < 2.0%
- THIN: 2.0%–2.8%
- BREACH: > 2.8% (levels seen in Q1 2000, Q3 2007, Q4 2021)

**Scoring**: `score_indicator_simple(ratio, 2.0, 2.8, 3.5, lower_is_better=True)`

### 2. ON RRP Facility Usage (Liquidity Pillar)

**Rationale**: The Fed's Overnight Reverse Repo (ON RRP) facility acts as a liquidity sink. When ON RRP drains rapidly, reserves are flowing back into the system (easing). When it's very high, it indicates excess reserves parked unproductively. Rapid drawdown may signal funding stress migration.

**Data**: FRED `RRPONTSYD` (daily, $B).

**Thresholds**: Rate-of-change based — rapid 30-day drawdown (> $200B/month) signals liquidity regime shift.

### 3. Leveraged ETF AUM (Positioning Pillar)

**Rationale**: Aggregate 2x/3x leveraged ETF AUM (TQQQ, SOXL, SPXU, etc.) provides a real-time gauge of retail directional leverage. When combined with SVXY (inverse vol), gives a more complete picture of retail risk-seeking behaviour.

**Data**: Scrape from issuer websites or use ETF API providers. Consider tracking top-10 leveraged ETFs by AUM.

---

## BTC-SPY Correlation: Implementation Details

The BTC-SPY 60-day rolling correlation is now computed in the API as a **contagion sub-indicator**. The rationale:

1. **Pre-2020**: BTC correlation to equities was near-zero — crypto was a separate market
2. **2020-2021**: Correlation rose to 0.3-0.5 as institutional adoption grew
3. **2022**: Correlation spiked to 0.6-0.8 during the Terra/LUNA collapse and FTX contagion
4. **Post-2023**: Correlation oscillates 0.3-0.6, sensitive to risk-on/risk-off regimes

**Why contagion, not positioning**: Crypto margin itself is difficult to observe (offshore exchanges, DeFi protocols). But the *correlation* between crypto and equities is directly observable and captures the systemic risk channel — when crypto acts as a correlated risk asset, a large crypto drawdown amplifies equity selling through shared margin calls and portfolio rebalancing.

**Scoring thresholds** (from `contagion.py`):
| Correlation | Score | Interpretation |
|------------|-------|----------------|
| < 0.3 | 1.0 | Decoupled — no contagion risk |
| 0.3–0.5 | 0.75–0.50 | Moderate — some shared factor exposure |
| 0.5–0.7 | 0.50–0.20 | Elevated — crypto acts as risk asset |
| > 0.7 | 0.20 | High — contagion channel active |

---

## Quarterly Review Cadence

As new leverage channels emerge or existing ones change structure, this taxonomy should be reviewed quarterly:

1. Check whether Tier 2 data sources have become available
2. Evaluate whether any Tier 3 channels have moved to publicly available data
3. Re-calibrate thresholds against recent crisis episodes
4. Assess whether pillar assignment remains correct (e.g., does crypto OI belong in Positioning or Contagion?)

---

## References

- Baranova, Y. et al. (2023). "Margin Leverage and Vulnerabilities in US Treasury Futures." Bank of England Staff Working Paper.
- Brunnermeier, M. & Pedersen, L. (2009). "Market Liquidity and Funding Liquidity." Review of Financial Studies.
- Federal Reserve (2024). "Quantifying Treasury Cash-Futures Basis Trades." FEDS Notes.
- OFR (2021). "Hedge Funds and the Treasury Cash-Futures Disconnect." Working Paper 21-01.
- FSB (2023). "The Financial Stability Implications of Leverage in Non-Bank Financial Intermediation."
