# Data Quality Dashboard

## Proxy Reliability Ratings by Era

The MAC framework spans 1850–2025, requiring different data sources across eras. This document catalogues the proxy reliability for each pillar by historical era.

---

## Reliability Tiers

| Tier | Label | Noise (σ) | Description |
|------|-------|-----------|-------------|
| 1 | **Native** | 0.01 | Direct observation (e.g., VIX post-1990) |
| 2 | **Computed** | 0.03 | Computed from primary data (e.g., BAA-AAA spread) |
| 3 | **Proxy (Modern)** | 0.05 | Modern proxy with strong validation |
| 4 | **Proxy (Historical)** | 0.10 | Historical proxy with limited validation |
| 5 | **Estimated** | 0.15 | Model-estimated, no direct data |

---

## Pillar-by-Era Matrix

### Liquidity

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1913 | Call money rate (NBER) | 4 | Only interbank proxy; no repo/CP market |
| 1913–1954 | Fed discount rate + bankers acceptance | 4 | Fed data starts; limited market microstructure |
| 1954–1986 | Fed Funds effective + TB spread | 3 | Modern money markets developing |
| 1986–2018 | TED spread + LIBOR-OIS | 2 | Standard liquidity indicators |
| 2018–2025 | SOFR-IORB + CP spread + xccy basis | 1 | Full indicator suite |

### Valuation

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1919 | Railroad bond-govt yield spread (NBER) | 4 | Only corporate proxy available |
| 1919–1986 | BAA-AAA spread (Moody's) | 3 | Standard credit spread |
| 1986–1996 | BAA-AAA + Merrill Lynch IG index | 2 | Broader credit market data |
| 1996–2025 | IG OAS + HY OAS + TIPS breakevens | 1 | Full valuation suite |

### Volatility

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1926 | Schwert reconstructed volatility | 5 | Model-estimated from monthly data |
| 1926–1986 | Realised vol (CRSP daily returns) | 3 | Daily data available |
| 1986–1990 | VXO (original CBOE vol index) | 2 | Options-implied vol |
| 1990–2025 | VIX + MOVE + vol-of-vol + term structure | 1 | Full volatility suite |

### Positioning

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1962 | Margin debt / GDP proxy | 5 | Very limited data |
| 1962–1986 | NYSE margin debt + COT (partial) | 4 | COT starts 1962 for some contracts |
| 1986–2006 | COT speculative positioning | 3 | Standard COT data |
| 2006–2025 | COT + basis trade size + SVXY AUM | 1–2 | Modern positioning indicators |

### Policy

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1913 | No central bank | 5 | Policy capacity is nil → hard cap at 0.30 |
| 1913–1934 | Fed discount rate + gold reserve ratio | 4 | Fed constrained by gold standard |
| 1934–1971 | Fed Funds + Bretton Woods constraints | 3 | Fixed exchange rate limits |
| 1971–2025 | Fed Funds + B/S GDP + inflation + fiscal | 1–2 | Full policy suite |

### Contagion

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1926 | UK consol-gilt spread vs US (GFD) | 5 | Very limited cross-border data |
| 1926–1990 | BAA-AAA + S&P 500 correlation | 4 | Domestic contagion proxies only |
| 1990–1998 | EMBI + cross-border flows (BIS) | 3 | EM data starts |
| 1998–2025 | EMBI + CDS + xccy basis + equity corr | 1–2 | Full contagion suite |

### Private Credit

| Era | Primary Source | Tier | Notes |
|-----|---------------|------|-------|
| 1850–1990 | Not applicable | — | Private credit market did not exist at scale |
| 1990–2004 | BDC total returns (sparse) | 4 | Limited BDC universe |
| 2004–2025 | BDC index + middle market spreads | 2–3 | Growing data availability |

---

## Uncertainty Propagation

The `ProxyUncertainty` class in `grri_mac/mac/confidence.py` uses these tiers to add appropriate noise during bootstrap CI computation. Higher-tier (noisier) proxies automatically produce wider confidence intervals, honestly reflecting data limitations.

## Key Caveats

1. **Pre-1926 data**: All pillars rely on Tier 4-5 proxies. MAC scores before 1926 should be interpreted with wide error bars.
2. **Era caps**: The policy pillar enforces hard caps (pre-Fed ≤ 0.30, gold standard ≤ 0.55) that dominate proxy uncertainty.
3. **Survivorship bias**: Historical series only include surviving entities, potentially understating true stress.
4. **Data revisions**: FRED vintage data may differ from real-time releases. Walk-forward backtest mitigates this.
