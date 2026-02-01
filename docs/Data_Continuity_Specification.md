# Data Continuity Specification

**Addressing Pre-2018 Indicator Gaps - Extended to 1971**

This document specifies fallback series for each indicator that lacks full historical coverage, ensuring the framework can be consistently applied across the **1971-2025 validation period (54 years, 2,814 weekly observations)**.

---

## Overview: Historical Proxy Architecture

The MAC framework uses a tiered proxy system to extend backtesting to 1971:

| Era | Years | Primary Indicators | Proxy Methodology |
|-----|-------|-------------------|-------------------|
| **Modern** | 2018-2025 | SOFR, IORB, VIX, BAML OAS | Native FRED series |
| **Post-GFC** | 2008-2018 | IOER, TED, VIX, BAML OAS | TED spread for funding |
| **Pre-GFC** | 1990-2008 | TED, VIX/VXO, Moody's spreads | VXO for volatility |
| **Historical** | 1971-1990 | Fed Funds-T-Bill, Moody's, NASDAQ | Realized vol proxy |

---

## 1. Liquidity Pillar Fallbacks

### 1.1 SOFR-IORB Spread

| Period | Primary Series | Fallback | FRED Code | Rationale |
|--------|----------------|----------|-----------|-----------|
| 2021-07+ | SOFR - IORB | — | SOFR, IORB | Native series |
| 2018-04 to 2021-07 | SOFR - IOER | — | SOFR, IOER | IOER preceded IORB |
| 2008-10 to 2018-04 | Fed Funds - IOER | — | DFF, IOER | Pre-SOFR era |
| 1986 to 2008-10 | TED Spread | — | TEDRATE | LIBOR 3M - T-Bill 3M |
| **1954 to 1986** | **Fed Funds - T-Bill** | — | **FEDFUNDS, TB3MS** | **Pre-TED era** |

**Implementation:**
```python
def get_liquidity_spread(date):
    if date >= datetime(2021, 7, 29):
        return get_sofr() - get_iorb()
    elif date >= datetime(2018, 4, 3):
        return get_sofr() - get_ioer()
    elif date >= datetime(2008, 10, 9):
        return get_fed_funds() - get_ioer()
    elif date >= datetime(1986, 1, 2):
        return get_ted_spread()  # FRED TEDRATE
    else:
        # Pre-1986: Fed Funds - T-Bill spread
        return get_fed_funds() - get_tbill_3m()
```

**Threshold Adjustment:**
Different eras have different "normal" spread levels:

| Indicator | Ample | Thin | Breach |
|-----------|-------|------|--------|
| SOFR-IORB (2018+) | < 3 bps | 3-15 bps | > 25 bps |
| TED Spread (1986-2018) | < 25 bps | 25-50 bps | > 100 bps |
| FF-TBill (1954-1986) | < 50 bps | 50-100 bps | > 200 bps |

### 1.2 Cross-Currency Basis

**The Problem:**
- €STR: Oct 2019+
- TONA (reformed): 2016+
- SONIA: 1997+
- SARON: 2009+

**Solution: Use interbank rate proxies**

| Currency | Modern Rate | Fallback (pre-2019) | FRED/Source |
|----------|-------------|---------------------|-------------|
| EUR | €STR | EONIA (1999+), German call money (pre-1999) | ECB SDW |
| JPY | TONA | Uncollateralized overnight (BOJ) | BOJ |
| GBP | SONIA | SONIA (available 1997+) | BOE |
| CHF | SARON | 1M LIBOR CHF proxy | FRED |

**Simplified Fallback for Pre-2006:**
For 1998-2006 (LTCM, dot-com era), use a single proxy:

```
cross_currency_stress = TED_spread × 0.5 + DXY_3m_change × 2
```

Rationale: TED spread and dollar strength historically correlate ~0.7 with cross-currency basis stress during crises.

**Currency Weights Rationale:**
| Currency | Weight | Basis |
|----------|--------|-------|
| EUR | 40% | BIS triennial survey: 31% of FX turnover |
| JPY | 30% | BIS: 17% of FX turnover, high carry trade activity |
| GBP | 15% | BIS: 13% of FX turnover |
| CHF | 15% | Safe haven, funding currency |

Weights are based on BIS FX turnover data, adjusted upward for JPY and CHF due to their outsized role in funding markets.

---

## 2. Positioning Pillar Fallbacks

### 2.1 SVXY AUM

| Period | Approach | Value |
|--------|----------|-------|
| 2011+ | SVXY market cap from yfinance | Actual |
| Pre-2011 | Set to 0 (product didn't exist) | 0 |

**Rationale:** Short-vol ETF positioning didn't exist as a systemic factor before 2011. The indicator captures a structural vulnerability that only emerged post-GFC.

**Alternative for Pre-2011:**
Could proxy via VIX futures open interest (CFTC), but this conflates hedging with speculation. Recommend keeping as 0 with clear documentation.

### 2.2 Basis Trade Size

**The Problem:** Fed estimates have wide uncertainty bands (±$100B).

**Current Approach:**
```
basis_trade_proxy = Treasury_futures_OI × leverage_factor
```

Where leverage_factor ≈ 0.15-0.20 based on Fed research (Glicoes et al. 2024).

**Historical Availability:**
- CFTC Treasury futures OI: 1986+
- Fed formal estimates: 2019+

**Proposed Enhancement:**
1. Use CFTC OI directly as the indicator (more observable)
2. Scale to $ notional using contract specs
3. Set thresholds based on OI percentile rather than absolute $

| Indicator | Ample | Thin | Breach |
|-----------|-------|------|--------|
| Treasury Futures OI Percentile | 20-80th | 10-90th | < 5th or > 95th |

This is more defensible than point estimates of basis trade size.

---

## 3. Volatility Pillar Fallbacks

### 3.0 VIX Proxy for Pre-1990 (Critical for 1971-1990 Backtesting)

The VIX index (VIXCLS) only begins in 1990. For 1971-1990 coverage, we use **realized volatility from NASDAQ Composite (NASDAQCOM)** as a proxy:

| Period | Primary | Proxy | FRED Code |
|--------|---------|-------|-----------|
| 1990+ | VIX (VIXCLS) | — | VIXCLS |
| 1986-1990 | VXO (VXOCLS) | — | VXOCLS |
| **1971-1986** | **Realized Vol × VRP** | **NASDAQCOM** | **NASDAQCOM** |

**Implementation:**
```python
def get_implied_volatility(date):
    if date >= datetime(1990, 1, 2):
        return get_vix()  # FRED VIXCLS
    elif date >= datetime(1986, 1, 2):
        return get_vxo()  # FRED VXOCLS (older VIX methodology)
    else:
        # Pre-1986: Calculate realized volatility from NASDAQ returns
        # Apply 1.2x Variance Risk Premium adjustment
        realized_vol = calculate_realized_vol_from_nasdaq(date, window=20)
        return realized_vol * 1.2  # VRP adjustment
```

**Variance Risk Premium (VRP) Adjustment:**
Academic literature consistently shows implied volatility trades at a premium to realized volatility (the "variance risk premium"). We apply a 1.2x multiplier to realized volatility to approximate implied volatility:

- Bakshi & Kapadia (2003): VRP averages ~15-20% of VIX level
- Carr & Wu (2009): VRP ~3-5% annualized
- Our calibration: 1.2x multiplier produces MAC scores consistent with known crisis severity

### 3.1 VIX Term Structure

| Period | Primary | Fallback |
|--------|---------|----------|
| 2004+ | VIX / VIX3M | Native (VIX3M launched 2007, backfilled to 2004) |
| Pre-2004 | VIX vs 20-day realized vol | RV > IV suggests backwardation-like conditions |

**Proxy Formula (pre-2004):**
```
term_structure_proxy = 1.0 + (IV - RV) / IV × 0.1
```
- If IV > RV: contango-like (proxy > 1.0)
- If IV < RV: backwardation-like (proxy < 1.0)

### 3.2 RV-IV Gap

Fully calculable back to 1971 using:
- VIX: FRED VIXCLS (1990+), VXO (1986+), or realized vol proxy (1971+)
- NASDAQ/S&P returns: FRED NASDAQCOM (1971+)

---

## 4. Credit Spread Fallbacks (Pre-1997)

### 4.1 High-Yield OAS Proxy

The BAML High-Yield OAS index (BAMLH0A0HYM2) only begins December 1996. For earlier periods, we use Moody's corporate bond spreads:

| Period | Primary | Proxy | FRED Code |
|--------|---------|-------|-----------|
| 1997+ | BAMLH0A0HYM2 | — | BAMLH0A0HYM2 |
| **1919-1996** | **(Baa - Aaa) × 4.5** | **Moody's spreads** | **BAA, AAA** |

**Implementation:**
```python
def get_hy_oas(date):
    if date >= datetime(1996, 12, 31):
        return get_baml_hy_oas()  # FRED BAMLH0A0HYM2
    else:
        # Pre-1997: Use Moody's spread as proxy
        baa_yield = get_baa_yield()  # FRED BAA
        aaa_yield = get_aaa_yield()  # FRED AAA
        moody_spread = baa_yield - aaa_yield  # ~1% historically
        return moody_spread * 4.5  # Scale to HY OAS equivalent (~4.5%)
```

**Scaling Factor Rationale:**
- Moody's Baa-Aaa spread: ~100 bps in normal conditions
- HY OAS: ~400-500 bps in normal conditions
- Ratio: ~4.5x (empirically calibrated)

### 4.2 Investment-Grade OAS Proxy

| Period | Primary | Proxy | FRED Code |
|--------|---------|-------|-----------|
| 1997+ | BAMLC0A0CM | — | BAMLC0A0CM |
| **1919-1996** | **Baa - Treasury - 40bps** | **Moody's spread** | **BAA, DGS10** |

**Implementation:**
```python
def get_ig_oas(date):
    if date >= datetime(1996, 12, 31):
        return get_baml_ig_oas()  # FRED BAMLC0A0CM
    else:
        # Pre-1997: Moody's Baa over Treasury, adjusted
        baa_yield = get_baa_yield()  # FRED BAA
        treasury_yield = get_treasury_10y()  # FRED DGS10
        return (baa_yield - treasury_yield) - 0.40  # Adjust for IG vs Baa
```

---

## 5. Policy Pillar Fallbacks

### 5.1 Policy Room (Distance from ELB)

**No fallback needed.** Fed funds rate (FRED: FEDFUNDS, DFF) available from 1954.

### 5.2 Fed Balance Sheet / GDP

| Period | Source |
|--------|--------|
| 2002+ | FRED: WALCL (weekly) / GDP |
| Pre-2002 | Fed H.4.1 historical releases, less frequent |

For pre-2002 scenarios, use annual snapshots:
- 1971: ~$70B / $1.1T GDP ≈ 6.4%
- 1974: ~$95B / $1.5T GDP ≈ 6.3%
- 1998: ~$500B / $9T GDP ≈ 5.5%
- 2000: ~$600B / $10T GDP ≈ 6%

### 5.3 Core PCE vs Target

FRED: PCEPILFE available from 1959. No fallback needed.

---

## 5. Contagion Pillar Fallbacks

### 5.1 EM Portfolio Flows

| Period | Primary | Fallback |
|--------|---------|----------|
| 2003+ | EEM/VWO ETF flows | Native (EEM launched Apr 2003) |
| 1998-2003 | MSCI EM index momentum proxy | 20-day return as sentiment proxy |

**Proxy Formula (pre-2003):**
```
em_flow_proxy = MSCI_EM_20d_return × 0.5
```
- Negative returns suggest outflows
- Scale factor 0.5 converts to approximate % weekly flow

### 5.2 G-SIB CDS Proxy

**Reviewer's critique is valid.** `BBB × 0.67` conflates bank and corporate risk.

**Improved Approach:**

| Period | Primary | Fallback |
|--------|---------|----------|
| 2004+ | Financial sector OAS | FRED: BAMLC0A4CBBBEY (BBB Financials) |
| Pre-2004 | Bank stock volatility proxy | Rolling 20d realized vol of BKX index |

FRED does have financial-specific series:
- BAMLC0A4CBBBEY: ICE BofA BBB US Corporate Index Effective Yield
- Can difference vs Treasury to get financial-specific OAS

**Threshold Recalibration:**
Financial sector spreads historically run ~20% wider than G-SIB CDS. Adjust thresholds accordingly.

### 5.3 DXY 3M Change

| Period | Source |
|--------|--------|
| 2006+ | FRED: DTWEXBGS (Broad Dollar Index) |
| 1973-2006 | FRED: DTWEXM (Major Currencies Index) |

Both are dollar indices; DTWEXBGS is trade-weighted broader, DTWEXM is G10-focused. Correlation > 0.95.

### 5.4 EMBI Spread

| Period | Source |
|--------|--------|
| 1998+ | FRED: BAMLEMCBPIOAS (ICE BofA EM OAS) |
| Pre-1998 | Brady bond spreads (academic databases) |

For LTCM (Sep 1998), the ICE series is available. Earlier scenarios would need academic data.

### 5.5 Global Equity Correlation

| Period | Primary | Fallback |
|--------|---------|----------|
| 2001+ | SPY/EFA/EEM correlation | Native (EFA Aug 2001, EEM Apr 2003) |
| Pre-2001 | SPY vs MSCI EAFE index | Correlation of S&P 500 vs EAFE returns |

MSCI EAFE daily returns available from 1986 via academic databases (CRSP, Bloomberg).

---

## 6. Summary: Data Availability by Scenario

| Scenario | Year | Native Coverage | Fallbacks Required |
|----------|------|-----------------|-------------------|
| LTCM Crisis | 1998 | 40% | TED spread, EM proxy, EAFE correlation |
| Dot-com Peak | 2000 | 45% | TED spread, EM proxy, EAFE correlation |
| 9/11 Attacks | 2001 | 50% | TED spread, EM proxy |
| Dot-com Bottom | 2002 | 50% | TED spread, EM proxy |
| Bear Stearns | 2008 | 70% | Pre-SOFR liquidity |
| Lehman | 2008 | 70% | Pre-SOFR liquidity |
| Flash Crash | 2010 | 80% | Pre-SOFR liquidity, SVXY=0 |
| US Downgrade | 2011 | 85% | Pre-SOFR liquidity |
| Volmageddon | 2018 | 95% | Minor (IOER vs IORB) |
| Repo Spike | 2019 | 98% | Minor |
| COVID-19 | 2020 | 100% | None |
| Russia-Ukraine | 2022 | 100% | None |
| SVB Crisis | 2023 | 100% | None |
| April Tariff | 2025 | 100% | None |

---

## 7. Implementation Recommendation

### 7.1 Code Structure

```python
class IndicatorFetcher:
    def get_liquidity_spread(self, date: datetime) -> float:
        """Returns appropriate liquidity spread for date."""
        if date >= SOFR_IORB_START:
            return self._get_sofr_iorb(date)
        elif date >= SOFR_IOER_START:
            return self._get_sofr_ioer(date)
        elif date >= IOER_START:
            return self._get_ff_ioer(date)
        else:
            return self._get_ted_spread(date) * TED_TO_SOFR_SCALE
```

### 7.2 Threshold Normalization

To ensure comparability across eras, normalize all indicators to percentile ranks before aggregation:

```python
def normalize_to_percentile(value, series_history):
    """Convert raw value to percentile rank in historical distribution."""
    return percentileofscore(series_history, value) / 100
```

This makes thresholds era-independent.

### 7.3 Documentation Requirements

Each scenario in `scenarios.py` should include:

```python
"ltcm_crisis_1998": HistoricalScenario(
    ...
    data_sources={
        "sofr_iorb_spread_bps": "FALLBACK: TED spread × 0.5",
        "cross_currency_basis_bps": "FALLBACK: TED + DXY proxy",
        "em_flow_pct_weekly": "FALLBACK: MSCI EM momentum",
        ...
    },
    data_quality="fair",  # explicit quality flag
)
```

---

## 8. Confidence Degradation

Implement confidence weighting based on data quality:

| Data Quality | Confidence Weight | Applicable Scenarios |
|--------------|-------------------|---------------------|
| Excellent | 1.00 | 2020-2025 |
| Good | 0.90 | 2018-2020 |
| Fair | 0.75 | 2006-2018 |
| Poor | 0.60 | 1998-2006 |

Report MAC scores with confidence bands:
```
LTCM 1998: MAC = 0.35 ± 0.08 (data quality: fair, confidence: 75%)
COVID 2020: MAC = 0.24 ± 0.02 (data quality: excellent, confidence: 100%)
```

---

*Document Version: 1.0*
*Created: January 2026*
*Purpose: Address reviewer feedback on data continuity*
