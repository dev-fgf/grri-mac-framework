# Running the MAC Framework Backtest

This guide explains how to run the **117-year extended historical backtest (1907-2025)** to generate empirical results for the academic paper.

## Prerequisites

1. **Python 3.8+** installed
2. **FRED API Key** (free from Federal Reserve)
   - Get yours at: https://fred.stlouisfed.org/docs/api/api_key.html
   - Set environment variable:
     ```bash
     # Windows (Command Prompt)
     set FRED_API_KEY=your_api_key_here

     # Windows (PowerShell)
     $env:FRED_API_KEY="your_api_key_here"

     # Linux/Mac
     export FRED_API_KEY=your_api_key_here
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Validate Cached Data First (Recommended)

Before running a backtest, validate your cached data:

```bash
python run_backtest.py --validate
```

### Run Standard Backtest (1971-2025)

```bash
python run_backtest.py --frequency weekly
```

### Run Extended Backtest (1907-2025)

```bash
python run_backtest.py --extended --era-weights --frequency weekly --output backtest_extended.csv
```

The `--extended` flag sets the start date to 1907-01-01 and activates historical proxy chains (NBER, Schwert, Shiller, BoE, FINRA). The `--era-weights` flag uses era-specific pillar weights instead of equal weights for pre-1971 periods.

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--start DATE` | Start date (YYYY-MM-DD) | 1971-02-05 |
| `--end DATE` | End date (YYYY-MM-DD) | 2024-12-31 |
| `--extended` | Run from 1907 with historical proxies | off |
| `--era-weights` | Use era-specific pillar weights (pre-1971) | off |
| `--frequency` | daily, weekly, or monthly | weekly |
| `--output FILE` | Output CSV filename | backtest_results.csv |
| `--validate` | Validate cached data and exit | - |
| `--fresh` | Clear cache and fetch fresh data | - |

## Backtest Modes

| Mode | Period | Crises | Data Sources |
|------|--------|--------|--------------|
| Standard | 1971-2025 | ~27 | FRED only |
| Historical | 1962-2025 | ~32 | FRED + Moody's proxies |
| Extended | 1907-2025 | 41 | FRED + NBER + Schwert + Shiller + BoE + FINRA |

### Specific Period Backtests

```bash
# Panic of 1907 and Pre-Fed era
python run_backtest.py --start 1907-01-01 --end 1914-12-31 --era-weights

# Great Depression
python run_backtest.py --start 1929-01-01 --end 1934-12-31 --era-weights

# Global Financial Crisis
python run_backtest.py --start 2007-01-01 --end 2009-12-31

# COVID-19 period
python run_backtest.py --start 2020-01-01 --end 2020-06-30
```

## Methodology Summary

### Seven Pillars

| Pillar | Indicators | Data Source |
|--------|-----------|-------------|
| Liquidity | SOFR-IORB spread, CP-Treasury spread | FRED |
| Valuation | Term premium, IG OAS, HY OAS (range-based) | FRED |
| Volatility | VIX / VXO / NASDAQ realised vol / Schwert vol | FRED |
| Policy | Policy room (distance from ELB) | FRED |
| Positioning | Basis trade size, spec net percentile, SVXY AUM | CFTC, yfinance |
| Contagion | BAA10Y spread (financial stress proxy) | FRED |
| Private Credit | SLOOS lending standards, BDC data | FRED, yfinance |

### Weight Selection

| Era | Weights | Method |
|-----|---------|--------|
| 2006-present | ML-optimized | Gradient boosting on 14 scenarios |
| Pre-1971 (with `--era-weights`) | Era-specific | Custom per-era overrides |
| Default | Equal (1/N) | Uniform across active pillars |

### Calibration Factor (Era-Aware)

| Era | Factor | Rationale |
|-----|--------|-----------|
| 2006+ | 0.78 | Calibrated on modern scenarios |
| 1971-2006 | 0.90 | Milder; proxy data already compressed |
| Pre-1971 | 1.00 | Structural differences sufficient |

### Scoring

- **One-sided** (`score_indicator_simple`): Liquidity, volatility, positioning
- **Two-sided** (`score_indicator_range`): Valuation (both compressed AND wide spreads = bad)

## Output Files

All results are saved to `data/backtest_results/`.

### CSV Columns

| Column | Description |
|--------|-------------|
| `date` | Date of calculation |
| `mac_score` | Composite MAC score (0-1, calibrated) |
| `liquidity` through `private_credit` | Individual pillar scores |
| `interpretation` | Human-readable status |
| `crisis_event` | Crisis name if date falls in crisis period |
| `data_quality` | excellent / good / fair / poor |
| `momentum_1w`, `momentum_4w` | Rate of change over 1 and 4 weeks |
| `trend_direction` | improving / stable / declining / rapidly_declining |
| `mac_status` | COMFORTABLE / CAUTIOUS / DETERIORATING / STRETCHED / CRITICAL |
| `is_deteriorating` | Boolean flag for rapid decline |

## Estimated Runtime

| Mode | Data Points | Runtime |
|------|-------------|---------|
| Weekly (1971-2025) | ~2,800 | ~1 min (cached) |
| Weekly (1907-2025) | ~6,200 | ~2 min (cached) |
| Daily (1971-2025) | ~14,000 | ~6-8 hours (first run) |

First run fetches data from FRED API (rate limited). Subsequent runs use cached data.

## Troubleshooting

### Unicode errors on Windows
Set encoding before running:
```bash
set PYTHONIOENCODING=utf-8
python run_backtest.py --extended
```

### Missing historical data files
The `--extended` mode requires historical data files in `data/historical/`. Run `download_historical_data.py` to fetch them.

### "No data available for date X"
Some series have limited coverage. Pre-1971 data relies on monthly proxies interpolated to weekly. Check `data_quality` column for quality tier.

## Generating Validation Metrics

After running the backtest:

```bash
python generate_validation_metrics.py
```

This produces:
- `tables/crisis_warnings.csv` — Per-crisis detection results
- `tables/validation_summary.csv` — Summary metrics
- `tables/validation_latex.txt` — LaTeX table for paper

## Documentation

- [Section 5: Empirical Validation](docs/Section_5_Validation_Results.md) — Full methodology and results writeup
- [Data Continuity Specification](docs/Data_Continuity_Specification.md) — Historical proxy chain documentation
- [Era Configurations](grri_mac/backtest/era_configs.py) — Era boundaries, pillar availability, threshold overrides
