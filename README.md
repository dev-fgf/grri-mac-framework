# GRRI-MAC Framework

**Market Absorption Capacity Analysis for Financial Stress Measurement**

A six-pillar framework for measuring financial market absorption capacity - the system's ability to absorb exogenous shocks without disorderly price adjustments, liquidity disruptions, or contagion cascades.

## Key Results

| Metric | Value |
|--------|-------|
| **MAC Range Accuracy** | 100% (14/14 events) |
| **Breach Detection** | 100% |
| **Hedge Prediction** | 78.6% |
| **Time Span** | 1998-2025 (27 years) |
| **Calibration Factor** | 0.78 |

**Key Insight:** Positioning pillar breach predicts Treasury hedge failure with **100% correlation** in historical sample.

## Installation

```bash
# Clone repository
git clone <repository-url>
cd VSC-FGF-MAC-Framework

# Install dependencies
pip install -r requirements.txt

# Optional: Set FRED API key for live data
export FRED_API_KEY=your_key_here
```

## Quick Start

```bash
# Run demo with sample data
python main.py --demo

# Run historical backtests (14 crisis events)
python main.py --backtest

# Generate visualization figures
python main.py --visualize

# Run calibration robustness analysis
python main.py --robustness
```

## The Six Pillars

| Pillar | Question | Key Indicators |
|--------|----------|----------------|
| **Liquidity** | Can markets transact without disorderly impact? | SOFR-IORB spread, CP-Treasury spread, cross-currency basis |
| **Valuation** | Are risk premia adequate? | Term premium, IG/HY OAS |
| **Positioning** | Is leverage manageable? | Basis trade size, CFTC COT percentile |
| **Volatility** | Are vol regimes stable? | VIX level, term structure, RV-IV gap |
| **Policy** | Does Fed have room to cut? | Distance from ELB, balance sheet/GDP |
| **Contagion** | Are cross-border channels stable? | EM flows, DXY change, EMBI spread, global equity correlation |

## Command Line Options

### Core Analysis
```bash
python main.py --backtest      # Run 14-event historical validation
python main.py --robustness    # Calibration cross-validation & sensitivity
python main.py --visualize     # Generate MAC vs VIX charts
python main.py --demo          # Demo with sample data
```

### Predictive Analytics (Forward-Looking)
```bash
python main.py --monte-carlo        # Regime impact simulations
python main.py --blind-test         # Real-time simulation (no lookahead)
python main.py --shock-propagation  # Cascade dynamics analysis
```

### Data Management
```bash
python main.py --import-data   # Import from FRED, CFTC, etc.
python main.py --db-demo       # Demo with database storage
python main.py --history       # Show historical data
```

## Predictive Capabilities

### Monte Carlo Regime Analysis

Same shock has vastly different impact depending on MAC regime:

| Starting Regime | MAC Change | Hedge Fail Prob | Amplification |
|-----------------|------------|-----------------|---------------|
| AMPLE (>0.65) | -0.04 | 5% | 1.0x |
| THIN (0.50-0.65) | -0.10 | 26% | 2.5x |
| STRETCHED (0.35-0.50) | -0.17 | 80% | 4.3x |
| BREACH (<0.35) | -0.14 | 80% | 3.5x |

**Finding:** Same 2-sigma shock is **3.5x worse** in breach regime.

### Blind Backtesting (No Lookahead Bias)

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

- [BACKTEST_STATUS.md](BACKTEST_STATUS.md) - Current validation results
- [docs/MAC_Framework_Complete_Paper.md](docs/MAC_Framework_Complete_Paper.md) - Academic paper

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
