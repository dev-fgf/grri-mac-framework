# GRRI-MAC Framework: G20 Expansion & 6-Pillar Architecture

**Version:** 2.0
**Date:** 2026-01-26
**Status:** Design Specification

## Executive Summary

This document specifies the architectural design for expanding the GRRI-MAC Framework from US-only to G20 coverage, adding a 6th International Contagion pillar, and enabling 20-year historical backtesting (2004-2024).

**Key Goals:**
1. **G20 Coverage** - Calculate country-specific MAC scores for all G20 economies
2. **6th Pillar** - Add International Contagion pillar for cross-border transmission
3. **20-Year Backtest** - Enable pre-GFC backtesting with alternative indicators (2004-2024)
4. **Cost Efficiency** - Prioritize free APIs with deep historical data ($0-49/month budget)
5. **Production Ready** - Maintain current Azure deployment architecture

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Source Strategy](#data-source-strategy)
3. [6-Pillar Framework Design](#6-pillar-framework-design)
4. [G20 Country Configuration](#g20-country-configuration)
5. [Historical Indicator Strategy](#historical-indicator-strategy)
6. [API Client Architecture](#api-client-architecture)
7. [Database Schema Updates](#database-schema-updates)
8. [API Endpoints](#api-endpoints)
9. [Backtest Infrastructure](#backtest-infrastructure)
10. [Implementation Roadmap](#implementation-roadmap)
11. [Cost Analysis](#cost-analysis)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Azure Static Web App                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐                  ┌────────────────────┐   │
│  │  Frontend (JS)  │                  │  Azure Functions   │   │
│  │  - Dashboard    │◄────────────────►│  (Python 3.11)     │   │
│  │  - G20 Heatmap  │                  │  - MAC Calculator  │   │
│  │  - Backtest UI  │                  │  - Country APIs    │   │
│  └─────────────────┘                  │  - Backtest Runner │   │
│                                        └──────────┬─────────┘   │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    │                               │                               │
            ┌───────▼──────┐              ┌────────▼─────────┐          ┌──────────▼────────┐
            │ Data Clients │              │ MAC Scoring      │          │ Azure Table       │
            │ Layer        │              │ Engine           │          │ Storage           │
            └───────┬──────┘              └────────┬─────────┘          └──────────┬────────┘
                    │                               │                               │
    ┌───────────────┼───────────────────┐          │                               │
    │               │                   │          │                               │
┌───▼────┐  ┌──────▼──────┐  ┌────────▼──────┐   │                    ┌──────────▼────────┐
│ FRED   │  │ BIS         │  │ OECD          │   │                    │ Tables:           │
│ (Free) │  │ (Free)      │  │ (Free)        │   │                    │ - machistory      │
└────────┘  └─────────────┘  └───────────────┘   │                    │ - backtesthistory │
                                                  │                    │ - grridata        │
┌────────┐  ┌──────────────┐  ┌────────────────┐ │                    │ - g20_mac         │
│ CFTC   │  │ IMF IFS      │  │ ECB SDW        │ │                    │ - contagion       │
│ (Free) │  │ (Free)       │  │ (Free)         │ │                    └───────────────────┘
└────────┘  └──────────────┘  └────────────────┘ │
                                                  │
┌────────┐  ┌──────────────┐  ┌────────────────┐ │
│ SEC    │  │ Treasury.gov │  │ Yahoo Finance  │ │
│ (Free) │  │ (Free)       │  │ (Free)         │ │
└────────┘  └──────────────┘  └────────────────┘ │
                                                  │
┌─────────────────────────────────────────────────▼──────┐
│ Polygon.io (Optional - $49/month)                      │
│ - Real-time forex (cross-currency basis)               │
│ - International equity indices                         │
│ - Options data (VIX term structure)                    │
└────────────────────────────────────────────────────────┘
```

### 1.2 Multi-Country Data Flow

```
User Request: GET /api/mac/DEU
           │
           ▼
    ┌──────────────────┐
    │ Country Router   │ ──► Validate country code (ISO 3166-1)
    │                  │ ──► Load country config (thresholds, data sources)
    └────────┬─────────┘
             │
    ┌────────▼──────────┐
    │ Data Aggregator   │
    │ - FRED/OECD/ECB   │ ──► Fetch Germany-specific indicators
    │ - BIS/IMF         │ ──► Fetch cross-border data
    │ - CFTC (US only)  │
    └────────┬──────────┘
             │
    ┌────────▼──────────┐
    │ 6-Pillar Scorer   │
    │ 1. Liquidity      │ ──► Country-specific thresholds
    │ 2. Valuation      │ ──► Currency-specific indicators
    │ 3. Positioning    │ ──► Regional COT data
    │ 4. Volatility     │ ──► Local equity vol
    │ 5. Policy         │ ──► Central bank policy
    │ 6. Contagion      │ ──► Cross-border flows
    └────────┬──────────┘
             │
    ┌────────▼──────────┐
    │ MAC Composite     │ ──► Weighted average (equal or custom)
    │ Multiplier: f(MAC)│ ──► 1 + 2.0 × (1 - MAC)^1.5
    │ Status: Ample/... │
    └────────┬──────────┘
             │
    ┌────────▼──────────┐
    │ Database Storage  │ ──► Save to g20_mac table
    │ PartitionKey: DEU │ ──► RowKey: 2024-01-26
    └────────┬──────────┘
             │
             ▼
    JSON Response to User
```

---

## 2. Data Source Strategy

### 2.1 API Selection Criteria

| Criterion | Requirement | Rationale |
|-----------|-------------|-----------|
| **Historical Depth** | 20+ years (pre-2004) | Pre-GFC backtesting requirement |
| **Country Coverage** | G20 minimum | Multi-country MAC scoring |
| **Cost** | Free preferred, $50/month max | Budget constraint |
| **Frequency** | Daily preferred, quarterly acceptable | Real-time monitoring vs historical analysis |
| **Reliability** | Government/multilateral sources | Data quality and permanence |

### 2.2 Primary Data Sources

#### **Tier 1: Free Government/Multilateral APIs (Historical Depth 20+ years)**

| API | Coverage | Historical Start | Frequency | Key Indicators |
|-----|----------|------------------|-----------|----------------|
| **FRED** | US | 1950s-1990s | Daily | Rates, spreads, VIX, credit, policy |
| **BIS** | Global | 1977 | Quarterly | Credit gaps, cross-border flows, FX |
| **OECD** | G20 | 1990s | Monthly/Quarterly | Policy rates, credit, leading indicators |
| **IMF IFS** | Global | 1950s | Monthly/Quarterly | Reserves, debt, BoP, exchange rates |
| **ECB SDW** | Eurozone | 1999 | Daily | Yields, spreads, TARGET2, ECB policy |
| **CFTC** | US futures | 1986 | Weekly | Positioning (legacy COT 1986+) |
| **SEC EDGAR** | US | 1994 | Quarterly | 13F holdings |
| **Treasury.gov** | US | 2000s | Monthly | Foreign holdings, auctions |
| **Yahoo Finance** | Global | 10-20 years | Daily | ETF prices, equity indices |

#### **Tier 2: Optional Paid API (Real-Time Only)**

| API | Cost | Coverage | Historical Depth | Use Case |
|-----|------|----------|------------------|----------|
| **Polygon.io** | $49/month | Global forex, equities, options | 5-15 years | Real-time cross-currency basis, VIX term structure |

**Decision:** Start with Tier 1 (free), add Polygon.io only for production real-time monitoring.

### 2.3 Data Source Mapping by Pillar

#### **US Indicators (Fully Implemented)**

| Pillar | Indicator | Current Source | Historical Start | Pre-2018 Alternative |
|--------|-----------|---------------|------------------|----------------------|
| **Liquidity** |
| | SOFR-IORB spread | FRED | 2018 | ❌ Use LIBOR-OIS (2001) or TED (1986) |
| | CP-Treasury spread | FRED | 1997 | ✅ No change needed |
| **Valuation** |
| | 10Y term premium | FRED | 1961 | ✅ No change needed |
| | IG OAS | FRED | 1996 | ✅ No change needed |
| | HY OAS | FRED | 1996 | ✅ No change needed |
| **Positioning** |
| | Basis trade size | Manual | 2017 | ❌ Use Primary dealer repo (Fed H.4.1, 2002) |
| | Treasury spec net | CFTC (Nasdaq Data Link) | 2006 | ⚠️ Use legacy COT (1986) |
| | SVXY AUM | Yahoo Finance | 2011 | ❌ Use VIX futures OI (CBOE, 2004) |
| **Volatility** |
| | VIX | FRED | 1990 | ✅ No change needed |
| **Policy** |
| | Fed funds rate | FRED | 1954 | ✅ No change needed |
| | Fed balance sheet / GDP | FRED | 2002 | ✅ No change needed |
| | Core PCE vs target | FRED | 1959 | ✅ No change needed |

#### **G20 Indicators (New Implementation)**

| Country/Region | Liquidity Indicator | Valuation Indicator | Policy Rate | Source |
|----------------|---------------------|---------------------|-------------|--------|
| **USA** | SOFR-IORB / LIBOR-OIS | IG/HY OAS, 10Y term premium | Fed funds | FRED |
| **Eurozone** | EURIBOR-ECB spread | German bund term premium, iTraxx | ECB rate | ECB SDW |
| **Germany (DEU)** | EURIBOR-ECB spread | Bund-OIS spread | ECB rate | ECB SDW |
| **France (FRA)** | EURIBOR-ECB spread | OAT-Bund spread | ECB rate | ECB SDW |
| **Italy (ITA)** | EURIBOR-ECB spread | BTP-Bund spread | ECB rate | ECB SDW |
| **UK (GBR)** | SONIA-BoE spread | Gilt term premium | BoE rate | BoE API |
| **Japan (JPN)** | TONAR-BoJ spread | JGB term premium (YCC distortion) | BoJ rate | BoJ API |
| **Canada (CAN)** | CORRA-BoC spread | Canada bond spreads | BoC rate | OECD |
| **Australia (AUS)** | AONIA-RBA spread | Aussie bond spreads | RBA rate | OECD |
| **China (CHN)** | SHIBOR-PBOC spread | CGB spreads (onshore) | PBOC rate | OECD/PBOC |
| **Emerging Markets** | Money market spreads | Local bond spreads | Policy rate | IMF IFS |

#### **6th Pillar: International Contagion (New)**

| Indicator | Source | Historical Start | Frequency | Coverage |
|-----------|--------|------------------|-----------|----------|
| **Cross-Currency Basis** |
| EUR/USD 3M basis | BIS derivatives | 1998 | Quarterly | Global |
| JPY/USD 3M basis | BIS derivatives | 1998 | Quarterly | Global |
| GBP/USD 3M basis | BIS derivatives | 1998 | Quarterly | Global |
| Real-time basis (optional) | Polygon.io | 5-10 years | Daily | Premium |
| **TARGET2 Imbalances** |
| Eurozone TARGET2 balances | ECB SDW | 1999 | Monthly | Eurozone only |
| **EM Reserve Coverage** |
| FX reserves | IMF IFS | 1950s | Monthly | All G20 EMs |
| Short-term external debt | IMF IFS | 1970s | Quarterly | All G20 EMs |
| **Cross-Border Flows** |
| BIS locational banking stats | BIS | 1977 | Quarterly | Global |
| Capital account balance | IMF BoP | 1960s | Quarterly | G20 |

---

## 3. 6-Pillar Framework Design

### 3.1 Pillar Weights

**Option A: Equal Weighting (Default)**
- Each pillar: 16.67% (1/6)
- Composite MAC = mean of 6 pillar scores

**Option B: Custom Weighting by Country**
- Example: Eurozone weights International Contagion higher (TARGET2 critical)
- Example: US weights Positioning higher (deeper futures markets)

```python
# Default equal weights
WEIGHTS_DEFAULT = {
    "liquidity": 1/6,
    "valuation": 1/6,
    "positioning": 1/6,
    "volatility": 1/6,
    "policy": 1/6,
    "contagion": 1/6,
}

# Eurozone custom weights (TARGET2 critical)
WEIGHTS_EUROZONE = {
    "liquidity": 0.15,
    "valuation": 0.20,
    "positioning": 0.10,
    "volatility": 0.15,
    "policy": 0.15,
    "contagion": 0.25,  # Higher weight for fragmentation risk
}
```

### 3.2 Pillar 6: International Contagion - Detailed Design

**Question:** Are cross-border transmission channels stable?

#### 3.2.1 Sub-Indicators

**1. Cross-Currency Basis (25%)**

Measures USD funding stress globally. Negative basis = USD shortage (market pays premium for dollars).

```python
@dataclass
class CrossCurrencyBasisIndicators:
    eur_usd_basis_bps: Optional[float] = None  # EUR/USD 3M basis swap
    jpy_usd_basis_bps: Optional[float] = None  # JPY/USD 3M basis swap
    gbp_usd_basis_bps: Optional[float] = None  # GBP/USD 3M basis swap

# Scoring: Aggregate absolute deviation from zero
composite_basis = mean(abs(eur_usd_basis), abs(jpy_usd_basis), abs(gbp_usd_basis))
```

**Thresholds:**
- **Ample:** < 10 bps absolute deviation (symmetric around 0)
- **Thin:** 10-30 bps absolute deviation
- **Breach:** > 30 bps (USD funding stress)

**Historical Context:**
- GFC (Oct 2008): EUR/USD basis hit -200 bps (severe USD shortage)
- COVID-19 (Mar 2020): EUR/USD basis hit -70 bps (Fed swap lines activated)
- Normal times: -5 to +5 bps

**2. TARGET2 Imbalances (25%)**

Eurozone-specific indicator of fragmentation risk. Large imbalances = capital flight within monetary union.

```python
@dataclass
class TARGET2Indicators:
    total_imbalances_eur_billions: Optional[float] = None  # Sum of absolute balances
    eurozone_gdp_eur_trillions: Optional[float] = None

# Scoring: Imbalances as % of Eurozone GDP
imbalance_ratio = total_imbalances / (eurozone_gdp * 1000) * 100  # Convert to %
```

**Thresholds:**
- **Ample:** < 10% of Eurozone GDP
- **Thin:** 10-20% of Eurozone GDP
- **Breach:** > 20% of Eurozone GDP

**Historical Context:**
- Euro Crisis (2012): Peaked at ~25% of GDP (Germany +€700B, periphery negative)
- Post-QE (2017-2019): Declined to 15%
- COVID-19 (2021): Rose to 18% due to PEPP

**For non-Eurozone countries:** Score as neutral (0.5) or use alternative indicator (BoP sudden stop).

**3. EM Reserve Coverage (25%)**

Measures emerging market resilience to sudden stops. Guidotti-Greenspan rule: reserves > short-term external debt.

```python
@dataclass
class ReserveCoverageIndicators:
    fx_reserves_usd_billions: Optional[float] = None
    short_term_external_debt_usd_billions: Optional[float] = None

# Scoring: Coverage ratio
coverage_ratio = fx_reserves / short_term_external_debt * 100  # %
```

**Thresholds:**
- **Ample:** > 150% coverage (comfortable buffer)
- **Thin:** 100-150% coverage (meets rule)
- **Breach:** < 100% coverage (vulnerable to sudden stop)

**Application:**
- **G20 EMs:** China, India, Brazil, Mexico, Indonesia, Turkey, South Africa, Argentina, Saudi Arabia
- **Advanced economies:** Score as neutral (typically have deep capital markets)

**4. Cross-Border Banking Flows (25%)**

Measures rapid capital movements that signal risk-on/risk-off shifts.

```python
@dataclass
class CrossBorderFlowIndicators:
    quarterly_change_billions: Optional[float] = None
    gdp_billions: Optional[float] = None

# Scoring: Quarterly change as % of GDP
flow_ratio = quarterly_change_billions / (gdp_billions * 0.25) * 100  # Quarterly GDP
```

**Thresholds:**
- **Ample:** -1% to +2% per quarter (normal growth)
- **Thin:** -2% to +4% per quarter (elevated)
- **Breach:** < -2% (sudden stop) or > +4% (hot money surge, reversal risk)

**Historical Context:**
- GFC (Q4 2008): -8% sudden stop in cross-border lending
- Taper Tantrum (Q2 2013): -3% EM outflows
- Normal times: +1% quarterly growth

#### 3.2.2 Composite Scoring

```python
class ContagionPillar:
    """International Contagion pillar calculator."""

    def calculate(self, indicators: ContagionIndicators) -> ContagionScores:
        scores = ContagionScores()
        scored_count = 0

        # 1. Cross-currency basis
        if indicators.eur_usd_basis_bps is not None:
            basis_abs = (
                abs(indicators.eur_usd_basis_bps) +
                abs(indicators.jpy_usd_basis_bps or 0) +
                abs(indicators.gbp_usd_basis_bps or 0)
            ) / 3
            scores.cross_currency_basis = self.score_basis(basis_abs)
            scored_count += 1

        # 2. TARGET2 (Eurozone only)
        if indicators.target2_imbalance_pct_gdp is not None:
            scores.target2 = self.score_target2(indicators.target2_imbalance_pct_gdp)
            scored_count += 1

        # 3. EM reserve coverage
        if indicators.reserve_coverage_ratio is not None:
            scores.reserve_coverage = self.score_reserves(indicators.reserve_coverage_ratio)
            scored_count += 1

        # 4. Cross-border flows
        if indicators.cross_border_flow_pct_gdp is not None:
            scores.cross_border_flows = self.score_flows(indicators.cross_border_flow_pct_gdp)
            scored_count += 1

        # Equal-weighted composite
        if scored_count > 0:
            scores.composite = (
                scores.cross_currency_basis +
                scores.target2 +
                scores.reserve_coverage +
                scores.cross_border_flows
            ) / scored_count
        else:
            scores.composite = 0.5  # Neutral

        return scores
```

### 3.3 MAC Composite Formula (Updated)

```python
def calculate_mac_composite(pillar_scores: dict, weights: dict = None) -> float:
    """
    Calculate composite MAC score from 6 pillars.

    Args:
        pillar_scores: Dict with keys: liquidity, valuation, positioning,
                       volatility, policy, contagion
        weights: Optional custom weights dict (defaults to equal 1/6 each)

    Returns:
        Composite MAC score (0-1, higher = more capacity)
    """
    if weights is None:
        weights = {k: 1/6 for k in pillar_scores.keys()}

    # Weighted average
    mac_score = sum(pillar_scores[k] * weights[k] for k in pillar_scores.keys())

    return max(0.0, min(1.0, mac_score))  # Clamp to [0, 1]


def calculate_multiplier(mac_score: float) -> float:
    """
    Calculate transmission multiplier from MAC score.

    Formula: M = 1 + 2.0 × (1 - MAC)^1.5

    Examples:
    - MAC = 0.8 → M = 1.09x (minimal amplification)
    - MAC = 0.5 → M = 1.35x (moderate amplification)
    - MAC = 0.2 → M = 2.43x (severe amplification)
    - MAC = 0.1 → M = 3.44x (extreme amplification)
    """
    return 1.0 + 2.0 * ((1.0 - mac_score) ** 1.5)
```

---

## 4. G20 Country Configuration

### 4.1 Country Codes and Names

```python
G20_COUNTRIES = {
    # Advanced Economies
    "USA": {"name": "United States", "region": "Americas", "currency": "USD", "central_bank": "Federal Reserve"},
    "CAN": {"name": "Canada", "region": "Americas", "currency": "CAD", "central_bank": "Bank of Canada"},
    "GBR": {"name": "United Kingdom", "region": "Europe", "currency": "GBP", "central_bank": "Bank of England"},
    "DEU": {"name": "Germany", "region": "Europe", "currency": "EUR", "central_bank": "ECB"},
    "FRA": {"name": "France", "region": "Europe", "currency": "EUR", "central_bank": "ECB"},
    "ITA": {"name": "Italy", "region": "Europe", "currency": "EUR", "central_bank": "ECB"},
    "JPN": {"name": "Japan", "region": "Asia-Pacific", "currency": "JPY", "central_bank": "Bank of Japan"},
    "AUS": {"name": "Australia", "region": "Asia-Pacific", "currency": "AUD", "central_bank": "Reserve Bank of Australia"},
    "KOR": {"name": "South Korea", "region": "Asia-Pacific", "currency": "KRW", "central_bank": "Bank of Korea"},

    # Emerging Markets
    "CHN": {"name": "China", "region": "Asia-Pacific", "currency": "CNY", "central_bank": "PBOC"},
    "IND": {"name": "India", "region": "Asia-Pacific", "currency": "INR", "central_bank": "Reserve Bank of India"},
    "IDN": {"name": "Indonesia", "region": "Asia-Pacific", "currency": "IDR", "central_bank": "Bank Indonesia"},
    "BRA": {"name": "Brazil", "region": "Americas", "currency": "BRL", "central_bank": "Banco Central do Brasil"},
    "MEX": {"name": "Mexico", "region": "Americas", "currency": "MXN", "central_bank": "Banxico"},
    "ARG": {"name": "Argentina", "region": "Americas", "currency": "ARS", "central_bank": "BCRA"},
    "TUR": {"name": "Turkey", "region": "Europe/MENA", "currency": "TRY", "central_bank": "CBRT"},
    "ZAF": {"name": "South Africa", "region": "Africa", "currency": "ZAR", "central_bank": "SARB"},
    "SAU": {"name": "Saudi Arabia", "region": "MENA", "currency": "SAR", "central_bank": "SAMA"},
    "RUS": {"name": "Russia", "region": "Europe/Asia", "currency": "RUB", "central_bank": "CBR"},

    # EU represented via member states (DEU, FRA, ITA)
}
```

### 4.2 Country-Specific Threshold Configuration

Different countries have different "normal" ranges for indicators. Example:

```json
{
  "USA": {
    "liquidity": {
      "money_market_spread": {
        "ample": 5,
        "thin": 25,
        "breach": 50
      }
    },
    "valuation": {
      "ig_oas": {
        "ample": 150,
        "thin": 80,
        "breach": 50
      }
    },
    "policy": {
      "neutral_rate": 2.5,
      "balance_sheet_gdp_ample": 25,
      "balance_sheet_gdp_breach": 40
    }
  },
  "JPN": {
    "liquidity": {
      "money_market_spread": {
        "ample": 3,
        "thin": 10,
        "breach": 20
      }
    },
    "valuation": {
      "term_premium": {
        "ample": 50,
        "thin": 0,
        "breach": -100
      }
    },
    "policy": {
      "neutral_rate": 0.0,
      "balance_sheet_gdp_ample": 50,
      "balance_sheet_gdp_breach": 150
    }
  }
}
```

**Configuration file location:** `grri_mac/config/country_thresholds.json`

### 4.3 Data Source Routing by Country

```python
class CountryDataRouter:
    """Routes data requests to appropriate API based on country."""

    def get_policy_rate(self, country_code: str) -> float:
        if country_code == "USA":
            return self.fred_client.get_latest("FED_FUNDS_TARGET")
        elif country_code in ["DEU", "FRA", "ITA"]:  # Eurozone
            return self.ecb_client.get_main_refinancing_rate()
        elif country_code == "GBR":
            return self.boe_client.get_bank_rate()
        elif country_code == "JPN":
            return self.boj_client.get_policy_rate()
        else:  # Other G20
            return self.oecd_client.get_policy_rate(country_code)

    def get_credit_spread(self, country_code: str) -> float:
        if country_code == "USA":
            return self.fred_client.get_ig_oas()
        elif country_code == "DEU":
            return self.ecb_client.get_bund_oas()
        elif country_code == "GBR":
            return self.boe_client.get_gilt_spread()
        else:
            return self.bis_client.get_credit_spread(country_code)
```

---

## 5. Historical Indicator Strategy

### 5.1 Problem Statement

Several key indicators don't exist for the full 20-year backtest period (2004-2024):

| Indicator | Start Date | Gap Period | Solution |
|-----------|------------|------------|----------|
| SOFR | April 2018 | 2004-2018 | Use LIBOR-OIS or TED spread |
| SVXY AUM | 2011 | 2004-2011 | Use VIX futures open interest |
| Basis trade size | ~2017 | 2004-2017 | Use primary dealer repo (Fed H.4.1) |
| CFTC disaggregated | 2006 | 2004-2006 | Use legacy COT reports |

### 5.2 Pre-2018 Liquidity Indicators

#### 5.2.1 LIBOR-OIS Spread (2001-2023)

**The critical GFC indicator.** Measures bank counterparty risk.

```python
def get_historical_liquidity_spread(date: datetime) -> float:
    """
    Get appropriate liquidity spread indicator based on date.

    Pre-2018: LIBOR-OIS spread
    Post-2018: SOFR-IORB spread
    """
    if date < datetime(2018, 4, 3):  # SOFR launch date
        # Use USD LIBOR - Effective Fed Funds (OIS proxy)
        libor_3m = fred.get_series("USD3MTD156N", date, date).iloc[-1]
        ois_proxy = fred.get_series("EFFR", date, date).iloc[-1]
        return (libor_3m - ois_proxy) * 100  # bps
    else:
        # Use SOFR - IORB spread
        sofr = fred.get_series("SOFR", date, date).iloc[-1]
        iorb = fred.get_series("IORB", date, date).iloc[-1]
        return (sofr - iorb) * 100  # bps
```

**FRED Series:**
- `USD3MTD156N`: 3-Month USD LIBOR (2001-2023)
- `USDONTD156N`: Overnight USD LIBOR (2001-2023)
- `EFFR`: Effective Federal Funds Rate (2000-present)

**Alternative (longer history):** TED Spread
- `TEDRATE`: 3-Month LIBOR - 3-Month T-Bill (1986-2023)

**Thresholds (LIBOR-OIS):**
- **Ample:** < 10 bps
- **Thin:** 10-30 bps
- **Breach:** > 30 bps

**Historical context:**
- Normal (2003-2007): 5-10 bps
- GFC peak (Oct 2008): **364 bps** (banks wouldn't lend to each other)
- Post-GFC (2010-2015): 10-20 bps
- Pre-SOFR (2016-2018): 15-25 bps

#### 5.2.2 Implementation

```python
# grri_mac/data/fred.py

def get_liquidity_spread(self, date: Optional[datetime] = None) -> float:
    """
    Get money market liquidity spread (date-aware).

    Returns SOFR-IORB if date >= 2018-04-03, else LIBOR-OIS.
    """
    if date is None:
        date = datetime.now()

    SOFR_START_DATE = datetime(2018, 4, 3)

    if date >= SOFR_START_DATE:
        # Modern era: SOFR-IORB
        sofr_data = self.get_series("SOFR", date, date)
        iorb_data = self.get_series("IORB", date, date)
        if not sofr_data.empty and not iorb_data.empty:
            return (sofr_data.iloc[-1] - iorb_data.iloc[-1]) * 100
    else:
        # Historical era: LIBOR-OIS
        libor_data = self.get_series("USD3MTD156N", date, date)
        effr_data = self.get_series("EFFR", date, date)
        if not libor_data.empty and not effr_data.empty:
            return (libor_data.iloc[-1] - effr_data.iloc[-1]) * 100

    raise ValueError(f"Liquidity spread data not available for {date}")
```

### 5.3 Pre-2011 Positioning Indicator (SVXY Alternative)

SVXY (short VIX ETF) launched in 2011, but VIX futures existed since 2004.

**Alternative:** VIX futures open interest as proxy for short volatility exposure.

```python
def get_short_vol_exposure(date: datetime) -> float:
    """
    Get short volatility exposure indicator.

    Post-2011: SVXY AUM
    Pre-2011: VIX futures open interest
    """
    if date >= datetime(2011, 10, 3):  # SVXY inception
        # Use SVXY AUM from Yahoo Finance
        svxy = yfinance.Ticker("SVXY")
        hist = svxy.history(start=date, end=date + timedelta(days=1))
        if not hist.empty:
            volume = hist['Volume'].iloc[0]
            close = hist['Close'].iloc[0]
            aum_estimate = volume * close * 30  # Rough AUM estimate
            return aum_estimate / 1e6  # Convert to millions
    else:
        # Use VIX futures open interest (requires CBOE data or scraping)
        # This is quarterly data from CBOE Futures Exchange
        vix_futures_oi = cboe_client.get_vix_futures_oi(date)
        # Scale to comparable range (SVXY AUM in millions)
        return vix_futures_oi / 1000  # Arbitrary scaling factor
```

**Data source:** CBOE Futures Exchange historical data (may require manual download/scraping)

### 5.4 Backtesting Data Quality Tiers

| Period | Data Quality | Indicators Available | Confidence |
|--------|--------------|----------------------|------------|
| **2020-2024** | Excellent | All 6 pillars, full granularity | 95% |
| **2018-2020** | Excellent | SOFR available, SVXY active | 95% |
| **2011-2018** | Good | LIBOR-OIS, SVXY available | 90% |
| **2006-2011** | Good | LIBOR-OIS, CFTC disaggregated, VIX futures OI | 85% |
| **2004-2006** | Fair | LIBOR-OIS, Legacy COT, VIX futures OI | 75% |

---

## 6. API Client Architecture

### 6.1 Client Interface Design

All data clients implement a common interface:

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any

class DataClient(ABC):
    """Base class for all market data clients."""

    @abstractmethod
    def get_series(self, series_id: str, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> pd.Series:
        """Fetch a time series."""
        pass

    @abstractmethod
    def get_latest(self, series_id: str) -> tuple[datetime, float]:
        """Get most recent value for a series."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if API is accessible."""
        pass
```

### 6.2 New Client Implementations

#### 6.2.1 BIS Client

```python
# grri_mac/data/bis.py

class BISClient(DataClient):
    """Client for Bank for International Settlements data."""

    BASE_URL = "https://data.bis.org/api/v1"

    DATASETS = {
        "CREDIT_GAP": "WS_CREDIT_GAP",  # Credit-to-GDP gaps
        "CROSS_BORDER": "WS_LBS_D_PUB",  # Locational banking statistics
        "DERIVATIVES": "WS_DERIV_MARKET",  # Derivatives statistics
        "DEBT_SERVICE": "WS_DSR",  # Debt service ratios
        "EER": "WS_EER",  # Effective exchange rates
    }

    def __init__(self):
        self._cache = {}

    def get_credit_gap(self, country_code: str, date: Optional[datetime] = None) -> float:
        """
        Get credit-to-GDP gap for a country.

        The gap measures deviation from long-run trend. > 10pp = warning signal.
        """
        # SDMX query format
        params = {
            "format": "json",
            "startPeriod": date.strftime("%Y-Q%q") if date else None,
            "endPeriod": date.strftime("%Y-Q%q") if date else None,
        }

        response = requests.get(
            f"{self.BASE_URL}/data/{self.DATASETS['CREDIT_GAP']}/{country_code}",
            params=params
        )

        # Parse SDMX-JSON response
        data = response.json()
        # ... parse logic

        return gap_value

    def get_cross_border_flows(self, country_code: str,
                                start_date: datetime,
                                end_date: datetime) -> pd.Series:
        """Get cross-border banking flows."""
        # Implementation
        pass
```

#### 6.2.2 OECD Client

```python
# grri_mac/data/oecd.py

class OECDClient(DataClient):
    """Client for OECD data."""

    BASE_URL = "https://stats.oecd.org/restsdmx/sdmx.ashx"

    DATASETS = {
        "MEI": "MEI",  # Main Economic Indicators
        "QSA": "QSA",  # Quarterly Sector Accounts
        "KEI": "KEI",  # Key Economic Indicators
    }

    def get_policy_rate(self, country_code: str, date: Optional[datetime] = None) -> float:
        """Get central bank policy rate."""
        # MEI dataset, IRSTCI01 indicator (immediate policy rate)
        pass

    def get_credit_conditions(self, country_code: str,
                             start_date: datetime,
                             end_date: datetime) -> pd.DataFrame:
        """Get credit conditions indicators."""
        pass
```

#### 6.2.3 IMF Client

```python
# grri_mac/data/imf.py

class IMFClient(DataClient):
    """Client for IMF International Financial Statistics."""

    BASE_URL = "http://dataservices.imf.org/REST/SDMX_JSON.svc"

    def get_fx_reserves(self, country_code: str, date: Optional[datetime] = None) -> float:
        """Get foreign exchange reserves in USD billions."""
        # IFS series: RAXG_USD (Total Reserves excluding Gold)
        pass

    def get_external_debt(self, country_code: str, date: Optional[datetime] = None) -> float:
        """Get short-term external debt in USD billions."""
        # IFS series: EDTS_USD (Short-term debt)
        pass

    def get_balance_of_payments(self, country_code: str,
                                start_date: datetime,
                                end_date: datetime) -> pd.DataFrame:
        """Get balance of payments data."""
        pass
```

#### 6.2.4 ECB Client

```python
# grri_mac/data/ecb.py

class ECBClient(DataClient):
    """Client for European Central Bank data."""

    BASE_URL = "https://data.ecb.europa.eu/data-detail-api"

    def get_main_refinancing_rate(self, date: Optional[datetime] = None) -> float:
        """Get ECB main refinancing rate."""
        pass

    def get_target2_balances(self, date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Get TARGET2 balances by country.

        Returns:
            Dict mapping country code to balance in EUR billions
        """
        # Series: TGB.M.*.N.T.EUR._T.T
        pass

    def get_bund_spread(self, country_code: str, date: Optional[datetime] = None) -> float:
        """Get sovereign spread vs German bund."""
        pass
```

#### 6.2.5 Polygon Client (Optional)

```python
# grri_mac/data/polygon.py

class PolygonClient(DataClient):
    """Client for Polygon.io real-time market data."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_forex_quote(self, pair: str) -> Dict[str, float]:
        """
        Get real-time forex quote.

        Args:
            pair: Currency pair like "EUR/USD", "USD/JPY"

        Returns:
            Dict with bid, ask, mid
        """
        pass

    def get_cross_currency_basis(self, pair: str, tenor: str = "3M") -> float:
        """
        Get cross-currency basis swap spread.

        Note: Requires FX derivatives data (may not be available in basic tier)
        """
        pass

    def get_options_chain(self, symbol: str) -> pd.DataFrame:
        """Get options chain for VIX term structure calculation."""
        pass
```

### 6.3 Client Factory

```python
# grri_mac/data/factory.py

class DataClientFactory:
    """Factory for creating and managing data clients."""

    _instances = {}

    @classmethod
    def get_client(cls, client_type: str) -> DataClient:
        """Get singleton instance of a data client."""
        if client_type not in cls._instances:
            if client_type == "fred":
                cls._instances[client_type] = FREDClient()
            elif client_type == "bis":
                cls._instances[client_type] = BISClient()
            elif client_type == "oecd":
                cls._instances[client_type] = OECDClient()
            elif client_type == "imf":
                cls._instances[client_type] = IMFClient()
            elif client_type == "ecb":
                cls._instances[client_type] = ECBClient()
            elif client_type == "polygon":
                api_key = os.environ.get("POLYGON_API_KEY")
                if api_key:
                    cls._instances[client_type] = PolygonClient(api_key)
                else:
                    raise ValueError("POLYGON_API_KEY not set")
            else:
                raise ValueError(f"Unknown client type: {client_type}")

        return cls._instances[client_type]
```

---

## 7. Database Schema Updates

### 7.1 New Azure Table: `g20_mac`

**Purpose:** Store country-specific MAC calculations

```
PartitionKey: {country_code}  # e.g., "USA", "DEU", "CHN"
RowKey: {date}                # e.g., "2024-01-26"

Attributes:
- timestamp: ISO datetime
- mac_score: float
- liquidity_score: float
- valuation_score: float
- positioning_score: float
- volatility_score: float
- policy_score: float
- contagion_score: float  # NEW
- multiplier: float
- status: string  # "Ample", "Comfortable", "Thin", "Stretched", "Regime Break"
- breach_flags: JSON array
- indicators: JSON object  # Raw indicator values
- data_quality: string  # "excellent", "good", "fair"
- is_live: bool
```

### 7.2 New Azure Table: `contagion_history`

**Purpose:** Store International Contagion pillar details

```
PartitionKey: {country_code} or "GLOBAL"
RowKey: {date}

Attributes:
- timestamp: ISO datetime
- cross_currency_basis_score: float
- eur_usd_basis_bps: float
- jpy_usd_basis_bps: float
- gbp_usd_basis_bps: float
- target2_score: float  # Eurozone only
- target2_imbalance_eur_billions: float
- reserve_coverage_score: float  # EM only
- reserve_coverage_ratio: float
- cross_border_flow_score: float
- cross_border_flow_pct_gdp: float
- composite_contagion_score: float
```

### 7.3 Extend Existing `backtesthistory` Table

Add new columns:
- `contagion_score: float`
- `data_quality: string`
- `historical_indicator_substitutions: JSON`  # Track which pre-2018 indicators were used

---

## 8. API Endpoints

### 8.1 New Endpoints

#### `GET /api/mac/{country_code}`

Get current MAC score for a country.

**Example:** `GET /api/mac/DEU`

**Response:**
```json
{
  "country": {
    "code": "DEU",
    "name": "Germany",
    "region": "Europe",
    "currency": "EUR"
  },
  "timestamp": "2024-01-26T10:30:00Z",
  "mac_score": 0.72,
  "status": "Comfortable",
  "multiplier": 1.15,
  "pillar_scores": {
    "liquidity": {"score": 0.78, "status": "Ample"},
    "valuation": {"score": 0.65, "status": "Comfortable"},
    "positioning": {"score": 0.70, "status": "Comfortable"},
    "volatility": {"score": 0.75, "status": "Ample"},
    "policy": {"score": 0.68, "status": "Comfortable"},
    "contagion": {"score": 0.76, "status": "Ample"}
  },
  "breach_flags": ["Valuation: HY OAS below thin threshold"],
  "indicators": {
    "liquidity": {
      "euribor_ecb_spread_bps": 8.2,
      "cp_treasury_spread_bps": 22.1
    },
    "valuation": {
      "bund_term_premium_bps": 65.3,
      "german_ig_oas_bps": 95.2
    },
    "contagion": {
      "eur_usd_basis_bps": -12.5,
      "target2_imbalance_pct_gdp": 14.2
    }
  },
  "data_quality": "excellent",
  "is_live": true
}
```

#### `GET /api/mac/global`

Get aggregate global MAC score (G20 weighted average).

**Response:**
```json
{
  "timestamp": "2024-01-26T10:30:00Z",
  "global_mac_score": 0.68,
  "global_status": "Comfortable",
  "global_multiplier": 1.20,
  "regional_breakdown": {
    "Americas": {"mac_score": 0.71, "countries": ["USA", "CAN", "BRA", "MEX", "ARG"]},
    "Europe": {"mac_score": 0.65, "countries": ["DEU", "FRA", "ITA", "GBR", "TUR", "RUS"]},
    "Asia-Pacific": {"mac_score": 0.70, "countries": ["JPN", "CHN", "IND", "KOR", "AUS", "IDN"]},
    "MENA": {"mac_score": 0.72, "countries": ["SAU"]},
    "Africa": {"mac_score": 0.66, "countries": ["ZAF"]}
  },
  "country_scores": [
    {"code": "USA", "name": "United States", "mac_score": 0.72, "status": "Comfortable"},
    {"code": "CHN", "name": "China", "mac_score": 0.68, "status": "Comfortable"},
    // ... all G20
  ]
}
```

#### `GET /api/mac/{country_code}/history?days=90`

Get historical MAC scores for a country.

#### `POST /api/backtest/{country_code}?start_date=2004-01-01&end_date=2024-12-31`

Run backtest for a specific country.

#### `GET /api/contagion/global`

Get detailed International Contagion indicators globally.

**Response:**
```json
{
  "timestamp": "2024-01-26T10:30:00Z",
  "composite_score": 0.75,
  "status": "Ample",
  "indicators": {
    "cross_currency_basis": {
      "eur_usd_3m_bps": -12.5,
      "jpy_usd_3m_bps": -8.3,
      "gbp_usd_3m_bps": -9.7,
      "score": 0.82
    },
    "target2_imbalances": {
      "total_imbalance_eur_billions": 1450,
      "eurozone_gdp_eur_trillions": 14.5,
      "imbalance_pct_gdp": 10.0,
      "score": 0.80,
      "country_balances": {
        "DEU": 1200,
        "ITA": -550,
        "ESP": -400,
        "FRA": -250
      }
    },
    "em_reserve_coverage": {
      "score": 0.72,
      "by_country": [
        {"code": "CHN", "coverage_ratio": 180, "score": 0.90},
        {"code": "IND", "coverage_ratio": 135, "score": 0.75}
      ]
    },
    "cross_border_flows": {
      "quarterly_change_pct_global_gdp": 1.2,
      "score": 0.85
    }
  }
}
```

### 8.2 Updated Endpoints

#### `GET /api/mac/demo` → `GET /api/mac/USA`

Migrate demo endpoint to country-specific endpoint.

---

## 9. Backtest Infrastructure

### 9.1 Backtest Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Backtest Runner                                          │
│ - Date range: 2004-01-01 to 2024-12-31                   │
│ - Frequency: Daily or weekly                             │
│ - Countries: USA (first), then G20                       │
└────────────────────┬─────────────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
┌─────▼──────┐ ┌────▼──────┐ ┌────▼──────┐
│ Data Fetch │ │ Indicator │ │ MAC Score │
│ Layer      │ │ Resolver  │ │ Calculator│
│            │ │           │ │           │
│ - FRED     │ │ Pre-2018? │ │ 6 Pillars │
│ - BIS      │ │ Use LIBOR │ │ Composite │
│ - OECD     │ │ -OIS      │ │ Multiplier│
└────────────┘ └───────────┘ └─────┬─────┘
                                    │
                          ┌─────────▼─────────┐
                          │ Crisis Annotator  │
                          │ - GFC             │
                          │ - Euro Crisis     │
                          │ - Taper Tantrum   │
                          │ - COVID-19        │
                          └─────────┬─────────┘
                                    │
                          ┌─────────▼─────────┐
                          │ Database Storage  │
                          │ backtesthistory   │
                          └───────────────────┘
```

### 9.2 Historical Indicator Resolution

```python
# grri_mac/backtest/indicator_resolver.py

class HistoricalIndicatorResolver:
    """Resolves appropriate indicators based on date."""

    def resolve_liquidity_spread(self, country: str, date: datetime) -> float:
        """Get date-appropriate liquidity spread."""
        if country == "USA":
            if date >= datetime(2018, 4, 3):
                return self.fred.get_sofr_iorb_spread(date)
            else:
                return self.fred.get_libor_ois_spread(date)
        elif country in ["DEU", "FRA", "ITA"]:
            return self.ecb.get_euribor_ecb_spread(date)
        # ... other countries

    def resolve_positioning_indicator(self, country: str, date: datetime) -> float:
        """Get date-appropriate positioning indicator."""
        if country == "USA":
            if date >= datetime(2011, 10, 3):
                # SVXY available
                return self.etf.get_svxy_aum(date)
            else:
                # Use VIX futures OI
                return self.cboe.get_vix_futures_oi(date)
        # ... other countries
```

### 9.3 Crisis Event Annotations

```python
# grri_mac/backtest/crisis_events.py

CRISIS_EVENTS = [
    {
        "name": "Global Financial Crisis",
        "start_date": "2008-09-15",  # Lehman collapse
        "end_date": "2009-03-09",    # S&P 500 bottom
        "affected_countries": ["USA", "GBR", "DEU", "FRA", "ITA", "JPN"],
        "expected_pillars_in_breach": ["liquidity", "valuation", "positioning"],
        "expected_mac_range": (0.15, 0.35),
        "severity": "extreme"
    },
    {
        "name": "European Sovereign Debt Crisis",
        "start_date": "2011-07-01",
        "end_date": "2012-09-06",  # Draghi "whatever it takes"
        "affected_countries": ["DEU", "FRA", "ITA", "ESP", "GRC"],
        "expected_pillars_in_breach": ["valuation", "contagion"],
        "expected_mac_range": (0.30, 0.50),
        "severity": "high"
    },
    {
        "name": "Taper Tantrum",
        "start_date": "2013-05-22",
        "end_date": "2013-09-18",
        "affected_countries": ["BRA", "IND", "IDN", "TUR", "ZAF"],  # Fragile Five
        "expected_pillars_in_breach": ["volatility", "contagion"],
        "expected_mac_range": (0.40, 0.60),
        "severity": "moderate"
    },
    {
        "name": "Volmageddon",
        "start_date": "2018-02-05",
        "end_date": "2018-02-08",
        "affected_countries": ["USA"],
        "expected_pillars_in_breach": ["positioning", "volatility"],
        "expected_mac_range": (0.30, 0.45),
        "severity": "moderate"
    },
    {
        "name": "COVID-19 Pandemic",
        "start_date": "2020-03-09",  # Market crash begins
        "end_date": "2020-03-23",    # Fed intervenes
        "affected_countries": "all",
        "expected_pillars_in_breach": ["liquidity", "valuation", "positioning", "volatility", "contagion"],
        "expected_mac_range": (0.10, 0.25),
        "severity": "extreme"
    }
]
```

### 9.4 Backtest Validation Metrics

```python
def calculate_backtest_metrics(backtest_results: pd.DataFrame,
                               crisis_events: List[Dict]) -> Dict:
    """
    Calculate prediction accuracy metrics.

    Returns:
        Dict with:
        - true_positive_rate: % of crises predicted
        - false_positive_rate: % of warnings without crisis
        - average_warning_days: Days of advance warning
        - crisis_accuracy: MAC score accuracy during crises
    """

    metrics = {
        "total_crises": len(crisis_events),
        "crises_predicted": 0,
        "false_positives": 0,
        "warning_days": [],
        "crisis_mac_scores": []
    }

    # For each crisis, check if MAC gave advance warning
    for crisis in crisis_events:
        crisis_start = pd.to_datetime(crisis["start_date"])
        lookback_period = backtest_results[
            (backtest_results.index < crisis_start) &
            (backtest_results.index >= crisis_start - timedelta(days=90))
        ]

        # Warning = MAC < 0.4 ("Thin" or worse)
        warnings = lookback_period[lookback_period["mac_score"] < 0.4]

        if not warnings.empty:
            metrics["crises_predicted"] += 1
            days_warning = (crisis_start - warnings.index[-1]).days
            metrics["warning_days"].append(days_warning)

    metrics["true_positive_rate"] = metrics["crises_predicted"] / metrics["total_crises"]

    return metrics
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Implement core infrastructure without country expansion

- [ ] Create base `DataClient` interface
- [ ] Implement `HistoricalIndicatorResolver` for pre-2018 data
- [ ] Add LIBOR-OIS spread to FRED client
- [ ] Extend CFTC client for legacy COT reports
- [ ] Implement 6th pillar (Contagion) scoring framework
- [ ] Add `contagion` field to database schemas
- [ ] Create `country_thresholds.json` configuration file
- [ ] Update MAC composite formula to support 6 pillars

**Deliverable:** USA-only MAC with 6 pillars, 20-year backtest capability

### Phase 2: International Data Clients (Weeks 3-4)

**Goal:** Add free international data sources

- [ ] Implement `BISClient` (credit gaps, cross-border flows)
- [ ] Implement `OECDClient` (policy rates, credit conditions)
- [ ] Implement `IMFClient` (reserves, external debt)
- [ ] Implement `ECBClient` (TARGET2, Eurozone yields)
- [ ] Add unit tests for all clients
- [ ] Create `DataClientFactory` for client management

**Deliverable:** All G20 data sources integrated

### Phase 3: G20 Country Expansion (Weeks 5-6)

**Goal:** Multi-country MAC scoring

- [ ] Implement `CountryDataRouter`
- [ ] Create G20 country configuration system
- [ ] Build `g20_mac` Azure Table
- [ ] Add new API endpoints (`/api/mac/{country}`, `/api/mac/global`)
- [ ] Create G20 heatmap UI component
- [ ] Test MAC scoring for 5 pilot countries (USA, DEU, GBR, JPN, CHN)

**Deliverable:** G20 MAC dashboard with 5 countries

### Phase 4: Full Backtest (Weeks 7-8)

**Goal:** 20-year backtesting infrastructure

- [ ] Implement `BacktestRunner` with date range support
- [ ] Add crisis event annotations
- [ ] Calculate backtest validation metrics
- [ ] Store backtest results in `backtesthistory` table
- [ ] Create backtest UI with crisis overlays
- [ ] Run full 2004-2024 backtest for USA
- [ ] Validate against GFC, Euro Crisis, COVID-19

**Deliverable:** Production-ready backtest system

### Phase 5: Polish & Deploy (Weeks 9-10)

**Goal:** Production deployment

- [ ] Add remaining G20 countries (15 countries)
- [ ] Optimize database queries (PartitionKey usage)
- [ ] Add API rate limiting and caching
- [ ] Write API documentation
- [ ] Create deployment guide
- [ ] Run full G20 backtest
- [ ] (Optional) Subscribe to Polygon.io for real-time forex

**Deliverable:** Full G20 MAC framework in production

---

## 11. Cost Analysis

### 11.1 API Costs

| Service | Tier | Cost | Usage | Annual Cost |
|---------|------|------|-------|-------------|
| **FRED** | Free | $0 | Unlimited (with key) | $0 |
| **BIS** | Free | $0 | Unlimited | $0 |
| **OECD** | Free | $0 | Unlimited | $0 |
| **IMF** | Free | $0 | Unlimited | $0 |
| **ECB** | Free | $0 | Unlimited | $0 |
| **CFTC** | Free | $0 | Weekly updates | $0 |
| **SEC EDGAR** | Free | $0 | 10 req/sec limit | $0 |
| **Treasury.gov** | Free | $0 | Unlimited | $0 |
| **Yahoo Finance** | Free | $0 | Rate limited | $0 |
| **Polygon.io** | Forex & Crypto | $49/month | 5 calls/sec | **$588** |
| **TOTAL (Free Only)** | | | | **$0** |
| **TOTAL (with Polygon)** | | | | **$588** |

### 11.2 Azure Infrastructure Costs

| Service | Tier | Estimated Cost |
|---------|------|----------------|
| **Azure Static Web Apps** | Free | $0 |
| **Azure Functions** | Consumption (1M executions/month) | $0 |
| **Azure Table Storage** | Standard (10GB, 1M transactions) | ~$2-5/month |
| **TOTAL** | | **$2-5/month** |

### 11.3 Total Cost Scenarios

| Scenario | API Costs | Azure Costs | Total Monthly | Total Annual |
|----------|-----------|-------------|---------------|--------------|
| **Minimum (Free APIs only)** | $0 | $2-5 | **$2-5** | **$24-60** |
| **Recommended (+ Polygon)** | $49 | $2-5 | **$51-54** | **$612-648** |

**Recommendation:** Start with free APIs ($0-5/month), backtest thoroughly, then add Polygon.io ($49/month) only if real-time forex is critical for production monitoring.

---

## 12. Success Criteria

### 12.1 Data Quality

- [ ] All 6 pillars calculable for USA from 2004-2024 (20 years)
- [ ] At least 5 G20 countries with full 6-pillar coverage
- [ ] Data quality tier tracked for each backtest period
- [ ] Historical indicator substitutions documented

### 12.2 Backtest Validation

- [ ] GFC (2008-2009): MAC drops to < 0.30, Liquidity pillar breaches
- [ ] Euro Crisis (2011-2012): MAC 0.30-0.50, Contagion pillar breaches (TARGET2)
- [ ] COVID-19 (Mar 2020): MAC drops to < 0.25, all pillars breach
- [ ] True positive rate > 80% (4 out of 5 crises predicted)
- [ ] Average warning: 15-45 days before crisis peak

### 12.3 Performance

- [ ] API response time < 2 seconds for single country MAC
- [ ] Global G20 MAC calculation < 10 seconds
- [ ] Backtest (20 years, 1 country) < 5 minutes
- [ ] Frontend dashboard load < 3 seconds

### 12.4 Scalability

- [ ] Support all 19 G20 countries (+ EU aggregation)
- [ ] 20-year historical data (2004-2024)
- [ ] Daily MAC calculations for all countries
- [ ] Azure Table Storage < 50GB total

---

## 13. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **API rate limits** | Medium | Medium | Implement caching, daily batch jobs |
| **Historical data gaps** | High | Medium | Use alternative indicators, document substitutions |
| **Country data inconsistency** | High | High | Define minimum data quality tiers, exclude incomplete countries |
| **Backtest overfitting** | Medium | High | Validate on out-of-sample crises, avoid parameter tuning to historical events |
| **Polygon.io cost overrun** | Low | Low | Start without paid APIs, monitor free API adequacy |
| **Azure storage costs** | Low | Low | Implement data retention policies (keep 2 years, archive older) |

---

## 14. Open Questions & Decisions

### 14.1 Pillar Weighting

**Question:** Should G20 countries use custom pillar weights or equal weighting?

**Options:**
- A) Equal weighting (1/6 each) for all countries
- B) Custom weights per country (e.g., Eurozone weights Contagion higher)
- C) User-configurable weights via API parameter

**Recommendation:** Start with A (equal), add B (custom) for Eurozone/EM after validation.

### 14.2 Real-Time vs Historical Data Sources

**Question:** Should we use separate data sources for backtesting vs live monitoring?

**Options:**
- A) Use free APIs (FRED, BIS, OECD) for both backtest and live
- B) Use free APIs for backtest, Polygon.io for live real-time monitoring
- C) Use free APIs only, accept 1-2 day lag

**Recommendation:** Start with A, evaluate need for B after 3 months of production usage.

### 14.3 Country Coverage Priority

**Question:** Which G20 countries to implement first?

**Recommendation (priority order):**
1. USA (already implemented, add 6th pillar)
2. Eurozone aggregate (DEU, FRA, ITA) - TARGET2 is key
3. GBR, JPN - major advanced economies
4. CHN, IND - major EMs with data availability
5. Remaining G20 (CAN, AUS, BRA, MEX, etc.)

### 14.4 Backtest Frequency

**Question:** Daily or weekly backtest granularity?

**Trade-offs:**
- Daily: More data points (7,300+), slower computation, noisier
- Weekly: Fewer data points (1,040), faster, smoother

**Recommendation:** Weekly for initial implementation, add daily option later if needed.

---

## 15. Next Steps

1. **Review & Approve:** Stakeholder review of architecture (1 week)
2. **Phase 1 Implementation:** 6th pillar + pre-2018 indicators (2 weeks)
3. **Phase 2 Implementation:** International data clients (2 weeks)
4. **Phase 3 Implementation:** G20 expansion (2 weeks)
5. **Phase 4 Implementation:** Full backtest system (2 weeks)
6. **Testing & Validation:** Backtest validation, crisis accuracy (1 week)
7. **Production Deployment:** Deploy to Azure, monitor (1 week)

**Total timeline:** 10 weeks from approval to production

---

## Appendix A: FRED Series Reference

| Indicator | FRED Series | Historical Start | Notes |
|-----------|-------------|------------------|-------|
| SOFR | `SOFR` | 2018-04-03 | Secured Overnight Financing Rate |
| IORB | `IORB` | 2021-07-28 | Interest on Reserve Balances (replaces IOER) |
| EFFR | `EFFR` | 2000-07-03 | Effective Federal Funds Rate |
| 3M LIBOR | `USD3MTD156N` | 2001-01-02 | Discontinued 2023-06-30 |
| Overnight LIBOR | `USDONTD156N` | 2001-01-02 | Discontinued 2023-06-30 |
| TED Spread | `TEDRATE` | 1986-01-02 | LIBOR - T-Bill spread |
| 3M T-Bill | `DTB3` | 1954-01-04 | |
| 3M Commercial Paper | `DCPF3M` | 1997-01-02 | AA financial |
| 2Y Treasury | `DGS2` | 1976-06-01 | |
| 10Y Treasury | `DGS10` | 1962-01-02 | |
| 10Y Term Premium | `THREEFYTP10` | 1961-06-14 | ACM model |
| IG OAS | `BAMLC0A0CM` | 1996-12-31 | ICE BofA US Corp Master OAS |
| HY OAS | `BAMLH0A0HYM2` | 1996-12-31 | ICE BofA US HY Master II OAS |
| VIX | `VIXCLS` | 1990-01-02 | CBOE Volatility Index |
| Fed Funds Target | `DFEDTARU` | 2008-12-16 | Upper target |
| Fed Balance Sheet | `WALCL` | 2002-12-18 | Total assets |
| Core PCE | `PCEPILFE` | 1959-01-01 | Core PCE Price Index |
| GDP | `GDP` | 1947-01-01 | Quarterly |

---

## Appendix B: Country Code Mapping

| ISO 3166-1 | Country | Alternative Codes |
|------------|---------|-------------------|
| USA | United States | US, United States of America |
| CAN | Canada | CA |
| MEX | Mexico | MX |
| BRA | Brazil | BR |
| ARG | Argentina | AR |
| GBR | United Kingdom | GB, UK, United Kingdom of Great Britain and Northern Ireland |
| DEU | Germany | DE, Deutschland |
| FRA | France | FR |
| ITA | Italy | IT, Italia |
| RUS | Russia | RU, Russian Federation |
| TUR | Turkey | TR, Türkiye |
| SAU | Saudi Arabia | SA |
| ZAF | South Africa | ZA |
| JPN | Japan | JP |
| CHN | China | CN, People's Republic of China |
| IND | India | IN |
| IDN | Indonesia | ID |
| KOR | South Korea | KR, Republic of Korea |
| AUS | Australia | AU |

---

## Appendix C: References

- **BIS Credit Gap Methodology:** Basel Committee on Banking Supervision (2010), "Guidance for national authorities operating the countercyclical capital buffer"
- **Guidotti-Greenspan Rule:** Guidotti, P. (1999), "Managing Exchange Rate Crises in Emerging Markets"
- **TARGET2 Imbalances:** Sinn, H.-W. & Wollmershäuser, T. (2012), "Target loans, current account balances and capital flows: the ECB's rescue facility"
- **LIBOR-OIS Spread:** Schwarz, K. (2019), "Mind the gap: Disentangling credit and liquidity in risk spreads"
- **MAC Framework:** Original GRRI-MAC methodology paper (see `docs/MAC_Methodology_Paper.md`)

---

**End of Architecture Design Document**

Last updated: 2026-01-26
Version: 2.0
Status: Draft for Review
