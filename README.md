# GRRI-MAC Framework

**Market Absorption Capacity Analysis for Financial Stress Measurement**

A seven-pillar framework for measuring financial market absorption capacity - the system's ability to absorb exogenous shocks without disorderly price adjustments, liquidity disruptions, or contagion cascades.

## Key Results

| Metric | Value |
|--------|-------|
| **Time Span** | **1971-2025 (54 years)** |
| **Weekly Observations** | **2,814** |
| **Crisis Detection Rate** | **81.5% (22/27 events)** |
| **Hedge Failure Sensitivity** | **100%** |
| **MAC Score Range** | **0.26 - 0.79** |
| **Calibration Factor** | 0.78 |

**Key Insight:** Positioning pillar breach predicts Treasury hedge failure with **100% correlation** in historical sample. Both confirmed hedge failures (COVID-19 March 2020, April 2025 Tariffs) correctly detected.

## Installation

```bash
# Clone repository
git clone <repository-url>
cd VSC-FGF-MAC-Framework

# Install dependencies
pip install -r requirements.txt

# Set FRED API key for live data (required)
export FRED_API_KEY=your_key_here  # Linux/Mac
$env:FRED_API_KEY="your_key_here"  # Windows PowerShell
```

## Quick Start

```bash
# Run 54-year backtest (1971-2025)
python run_backtest.py --start 1971-03-01 --end 2025-01-31 --frequency weekly

# Validate cached data integrity
python run_backtest.py --validate

# Clear cache and fetch fresh data
python run_backtest.py --fresh --start 1971-03-01 --end 2025-01-31

# Run specific crisis period (e.g., 1970s Oil Crisis)
python run_backtest.py --start 1973-01-01 --end 1975-12-31 --frequency weekly

# Run demo with sample data
python main.py --demo
```

## The Seven Pillars

| Pillar | Question | Key Indicators |
|--------|----------|----------------|
| **Liquidity** | Can markets transact without disorderly impact? | SOFR-IORB spread, CP-Treasury spread, cross-currency basis |
| **Valuation** | Are risk premia adequate? | Term premium, IG/HY OAS |
| **Positioning** | Is leverage manageable? | Basis trade size, CFTC COT percentile |
| **Volatility** | Are vol regimes stable? | VIX level, term structure, RV-IV gap |
| **Policy** | Does Fed have room to cut? | Distance from ELB, balance sheet/GDP |
| **Contagion** | Are cross-border channels stable? | EM flows, DXY change, EMBI spread |
| **Private Credit** | Is stress building in opaque markets? | BDC discounts, SLOOS, leveraged loan ETF |

## Historical Proxy Methodology

The framework extends backtesting to 1971 using validated proxy series:

| Indicator | Modern Series | Historical Proxy | Availability |
|-----------|--------------|------------------|--------------|
| VIX | VIXCLS (1990+) | Realized vol × 1.2 VRP | 1971+ |
| HY OAS | BAML (1997+) | Moody's Baa-Aaa × 4.5 | 1919+ |
| TED Spread | TEDRATE (1986+) | Fed Funds - T-Bill | 1954+ |

Real-time simulation accuracy:
- MAC Regime: **100%**
- Hedge Outcome: **78.6%** (0 false negatives)
- Breach Detection: **92.9%**
- Severity: **100%**

### Cascade Dynamics

Critical threshold discovered at **MAC < 0.45**:
- MAC 0.70: 0% cascade probability
- MAC 0.55: 0% cascade probability
- MAC 0.45: 98% cascade probability
- MAC 0.35: 100% cascade probability

## Multi-Country Support

The framework supports MAC analysis for major economies:

| Region | Code | Central Bank | Data Sources |
|--------|------|--------------|--------------|
| United States | US | Fed | FRED, CFTC COT |
| Eurozone | EU | ECB | FRED (BTP-Bund, VSTOXX) |
| Japan | JP | BOJ | FRED (TONAR, Nikkei VI) |
| United Kingdom | UK | BOE | FRED (SONIA, Gilt spreads) |

Note: China excluded due to capital controls.

## Project Structure

```
grri_mac/
├── mac/                 # Core MAC calculation
│   ├── composite.py     # 6-pillar aggregation
│   ├── multiplier.py    # Transmission multiplier
│   └── multicountry.py  # Cross-country analysis
├── pillars/             # Individual pillar scoring
│   ├── liquidity.py
│   ├── valuation.py
│   ├── positioning.py
│   ├── volatility.py
│   ├── policy.py
│   ├── calibrated.py    # Calibrated thresholds
│   └── countries.py     # Country-specific thresholds
├── backtest/            # Historical validation
│   ├── calibrated_engine.py
│   ├── scenarios.py     # 14 crisis events
│   └── calibration.py   # LOOCV & sensitivity
├── predictive/          # Forward-looking analysis
│   ├── monte_carlo.py   # Regime simulations
│   ├── blind_backtest.py
│   └── shock_propagation.py
├── visualization/       # Chart generation
│   └── crisis_plots.py
├── data/                # Data fetching
│   ├── fred.py
│   ├── cftc.py
│   └── contagion.py
└── dashboard/           # Daily monitoring
```

## Documentation

- [BACKTEST_README.md](BACKTEST_README.md) - How to run historical backtests
- [DEPLOY.md](DEPLOY.md) - Azure deployment guide
- [docs/MAC_Framework_Complete_Paper.md](docs/MAC_Framework_Complete_Paper.md) - Academic paper
- [docs/G20_Architecture_Design.md](docs/G20_Architecture_Design.md) - G20 expansion design

## Data Sources (All Free, All Real Data)

| Source | Package | Coverage |
|--------|---------|----------|
| FRED | `fredapi` | VIX, credit spreads, rates, DXY, EMBI proxy (1990+) |
| CFTC COT | `cot-reports` | Treasury positioning (1986+) |
| Yahoo Finance | `yfinance` | ETF flows, FX spot/futures, equity correlations |

**Key Indicators:**
- **Policy Room**: `fed_funds × 100` (distance from Effective Lower Bound in bps)
- **Cross-Currency Basis**: CIP deviation weighted composite (EUR 40%, JPY 30%, GBP 15%, CHF 15%)
- **RV-IV Gap**: `abs(realized_vol - VIX) / VIX × 100` using SPY returns vs FRED VIXCLS
- **Global Equity Corr**: Rolling correlation of SPY/EFA/EEM from yfinance

## Version History

- **4.3** - All real data (ELB-based policy, CIP-based cross-currency basis, multi-currency weighted)
- **4.2** - Predictive analytics (Monte Carlo, blind backtest, cascade)
- **4.1** - Robustness validation, visualizations
- **4.0** - Contagion pillar, multi-country support
- **3.0** - ML-optimized weights
- **2.0** - 6-pillar calibration
- **1.0** - Initial 5-pillar framework

## Citation

```bibtex
@article{mac_framework_2026,
  title={A Six-Pillar Framework for Measuring Market Absorption Capacity},
  year={2026},
  note={Working Paper}
}
```

## License

[License details]
