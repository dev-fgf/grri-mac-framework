#!/usr/bin/env python
"""
MAC Framework — Historical Data Download Script

Downloads publicly available datasets needed to extend the backtest to 1907.
Handles FRED API series (automatic), Shiller dataset (automatic), and prints
instructions for datasets that require manual download.

Usage:
    python download_historical_data.py              # Download all
    python download_historical_data.py --fred-only   # FRED series only
    python download_historical_data.py --check       # Verify files exist

Data Specification Reference:
    docs/Data_Continuity_Specification.md

Sources:
    1. FRED API           — 20+ series (automatic via fredapi)
    2. Shiller (Yale)     — ie_data.xls  (automatic via HTTP)
    3. NBER Macrohistory  — 8 series     (manual: NBER website)
    4. Schwert volatility — schwert.csv  (manual: academic download)
    5. Bank of England    — GBP/USD, Bank Rate (semi-auto: BoE Research DB)
    6. MeasuringWorth     — US GDP       (manual: measuringworth.com)
    7. FINRA / NYSE       — Margin Debt  (manual: FINRA website)
"""

import os
import sys
import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
HISTORICAL_DIR = DATA_DIR / "historical"

# Sub-directories
FRED_CACHE_DIR = DATA_DIR / "fred_cache"
NBER_DIR = HISTORICAL_DIR / "nber"
SHILLER_DIR = HISTORICAL_DIR / "shiller"
SCHWERT_DIR = HISTORICAL_DIR / "schwert"
BOE_DIR = HISTORICAL_DIR / "boe"
MW_DIR = HISTORICAL_DIR / "measuringworth"
FINRA_DIR = HISTORICAL_DIR / "finra"


# ─────────────────────────────────────────────────────────────────────────────
# FRED series required for the extended backtest
# ─────────────────────────────────────────────────────────────────────────────
FRED_SERIES = {
    # Liquidity pillar
    "SOFR":             "Secured Overnight Financing Rate (2018+)",
    "IORB":             "Interest on Reserve Balances (2021+)",
    "IOER":             "Interest on Excess Reserves (2008-2021)",
    "TEDRATE":          "TED Spread (1986+)",
    "DFF":              "Effective Federal Funds Rate (1954+)",
    "DCPF3M":           "3-Month AA Financial CP Rate (1997+)",
    "DTB3":             "3-Month Treasury Bill Rate (1954+)",
    "TB3MS":            "3-Month Treasury Bill Secondary Market (1934+)",
    "FEDFUNDS":         "Federal Funds Effective Rate monthly (1954+)",
    # Valuation pillar
    "BAMLC0A0CM":       "ICE BofA US Corporate OAS (1997+)",
    "BAMLH0A0HYM2":     "ICE BofA US HY OAS (1997+)",
    "AAA":              "Moody's Aaa Corporate Bond Yield (1919+)",
    "BAA":              "Moody's Baa Corporate Bond Yield (1919+)",
    "DGS10":            "10-Year Treasury Constant Maturity (1962+)",
    "BAA10Y":           "Moody's Baa - 10Y Treasury Spread (1986+)",
    "IRLTLT01USM156N":  "Long-Term Government Bond Yield (1920+)",
    # Volatility pillar
    "VIXCLS":           "CBOE VIX (1990+)",
    "VXOCLS":           "CBOE VXO (1986+)",
    "NASDAQCOM":        "NASDAQ Composite (1971+)",
    # Policy pillar
    "DGS2":             "2-Year Treasury Constant Maturity (1976+)",
    "WALCL":            "Fed Total Assets (2002+)",
    "BOGMBASE":         "Monetary Base (1959+)",
    "M2SL":             "M2 Money Supply (1959+)",
    "INTDSRUSM193N":    "Fed Discount Rate (1913+)",
    "GDPA":             "GDP Annual (1929+)",
    # Private Credit pillar
    "DRTSCIS":          "SLOOS C&I Standards Small Firms (1990+)",
    "DRISCFS":          "SLOOS Spreads Small Firms (1990+)",
    "DRTSCILM":         "SLOOS C&I Standards Large/Mid Firms (1990+)",
    # Contagion extras
    "GOLDAMGBD228NLBM": "Gold Price London Fixing (1968+)",
    "DTWEXBGS":         "Trade Weighted US Dollar Index (1973+)",
}


def download_fred_series():
    """Download all required FRED series."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("❌ FRED_API_KEY not set.  Get a free key at:")
        print("   https://fred.stlouisfed.org/docs/api/api_key.html")
        return False

    try:
        from fredapi import Fred
    except ImportError:
        print("❌ fredapi not installed.  Run: pip install fredapi")
        return False

    fred = Fred(api_key=api_key)
    FRED_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = []

    for series_id, description in FRED_SERIES.items():
        cache_file = FRED_CACHE_DIR / f"{series_id}.csv"
        if cache_file.exists():
            print(f"  ✓ {series_id:<24} — cached ({description})")
            success += 1
            continue

        try:
            data = fred.get_series(series_id)
            if data is not None and len(data) > 0:
                data.to_csv(cache_file, header=True)
                print(
                    f"  ⬇ {series_id:<24} — {len(data)} obs"
                    f" ({data.index[0].date()} to"
                    f" {data.index[-1].date()})"
                )
                success += 1
            else:
                print(f"  ⚠ {series_id:<24} — empty response")
                failed.append(series_id)
        except Exception as e:
            print(f"  ❌ {series_id:<24} — {e}")
            failed.append(series_id)

    print(f"\nFRED: {success}/{len(FRED_SERIES)} series downloaded successfully")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    return len(failed) == 0


def download_shiller_dataset():
    """Download Shiller ie_data.xls from Yale."""
    SHILLER_DIR.mkdir(parents=True, exist_ok=True)
    xls_path = SHILLER_DIR / "ie_data.xls"

    if xls_path.exists():
        print("  ✓ Shiller ie_data.xls already exists")
        return True

    url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
    print(f"  ⬇ Downloading Shiller dataset from {url} ...")

    try:
        import urllib.request
        urllib.request.urlretrieve(url, str(xls_path))
        size_kb = xls_path.stat().st_size / 1024
        print(f"  ✓ Saved ie_data.xls ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"  ❌ Failed to download Shiller dataset: {e}")
        print(f"     Manual download: {url}")
        print(f"     Save to: {xls_path}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Manual download instructions
# ─────────────────────────────────────────────────────────────────────────────

MANUAL_INSTRUCTIONS = """
══════════════════════════════════════════════════════════════════════════════
MANUAL DATA DOWNLOADS REQUIRED
══════════════════════════════════════════════════════════════════════════════

The following datasets must be downloaded manually due to website
restrictions.  Download the files and place them in the specified
directories.

──────────────────────────────────────────────────────────────────────────────
1. NBER MACROHISTORY DATABASE  (Interest Rates + Money/Banking)
──────────────────────────────────────────────────────────────────────────────
   URL:  https://www.nber.org/research/data/nber-macrohistory-database
   Navigate to:
     Chapter 13 → Interest Rates
     Chapter 14 → Money and Banking

   Download these series as CSV (date, value columns):
     m13001.csv — Call Money Rate (1890+)
     m13039.csv — Commercial Paper Rate 4-6 month (1890+)
     m13041.csv — Short-Term Government Rate (1890+)
     m13020.csv — Railroad Bond Yield High Grade (1857+)
     m13028.csv — Railroad Bond Yield Lower Grade (1857+)
     m13033.csv — US Govt Bond Yield Long-Term (1857+)
     m13034.csv — US Govt Bond Yield Short-Term (1857+)
     m14076.csv — US Gold Stock (1878+)

   Save to: {nber_dir}

──────────────────────────────────────────────────────────────────────────────
2. SCHWERT STOCK VOLATILITY (1802–1989)
──────────────────────────────────────────────────────────────────────────────
   Source: G. William Schwert, "Indexes of U.S. Stock Prices from 1802 to
           1987" (Journal of Business, 1990)
   URL:    https://schwert.simon.rochester.edu/volatility.html

   Download the monthly stock volatility series.
   Format: CSV with columns 'date' (YYYY-MM-01) and 'volatility' (annualised %)

   Save to: {schwert_dir}/schwert_volatility.csv

──────────────────────────────────────────────────────────────────────────────
3. BANK OF ENGLAND RESEARCH DATABASE
──────────────────────────────────────────────────────────────────────────────
   URL: https://www.bankofengland.co.uk/statistics/research-datasets

   Download:
     a) GBP/USD exchange rate (monthly, 1791+)
        Filename: boe_gbpusd.csv  — columns: 'date', 'rate'
     b) Bank Rate (monthly, 1694+)
        Filename: boe_bankrate.csv — columns: 'date', 'rate'

   Save to: {boe_dir}

──────────────────────────────────────────────────────────────────────────────
4. MEASURINGWORTH — US GDP
──────────────────────────────────────────────────────────────────────────────
   URL: https://www.measuringworth.com/datasets/usgdp/

   Download nominal GDP (annual, from 1790).
   Format: CSV with columns 'year' and 'gdp' (in millions USD)

   Save to: {mw_dir}/us_gdp.csv

──────────────────────────────────────────────────────────────────────────────
5. FINRA / NYSE MARGIN DEBT
──────────────────────────────────────────────────────────────────────────────
   URL: https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics

   Download monthly margin debt data (1918+).
   Format: CSV with columns 'date' (YYYY-MM-01) and 'margin_debt' (millions USD)

   Save to: {finra_dir}/margin_debt.csv

══════════════════════════════════════════════════════════════════════════════
""".strip()


def print_manual_instructions():
    """Print instructions for manually downloaded datasets."""
    print(MANUAL_INSTRUCTIONS.format(
        nber_dir=NBER_DIR,
        schwert_dir=SCHWERT_DIR,
        boe_dir=BOE_DIR,
        mw_dir=MW_DIR,
        finra_dir=FINRA_DIR,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Data verification
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_FILES = {
    "FRED cache": [
        (FRED_CACHE_DIR / f"{s}.csv", s) for s in FRED_SERIES
    ],
    "NBER Macrohistory": [
        (NBER_DIR / "m13001.csv", "Call Money Rate"),
        (NBER_DIR / "m13039.csv", "Commercial Paper Rate"),
        (NBER_DIR / "m13041.csv", "Short-Term Govt Rate"),
        (NBER_DIR / "m13020.csv", "Railroad Bond High Grade"),
        (NBER_DIR / "m13028.csv", "Railroad Bond Lower Grade"),
        (NBER_DIR / "m13033.csv", "Govt Bond Long-Term"),
        (NBER_DIR / "m13034.csv", "Govt Bond Short-Term"),
        (NBER_DIR / "m14076.csv", "US Gold Stock"),
    ],
    "Shiller": [
        (SHILLER_DIR / "ie_data.xls", "Shiller Dataset"),
    ],
    "Schwert": [
        (SCHWERT_DIR / "schwert_volatility.csv", "Schwert Volatility"),
    ],
    "Bank of England": [
        (BOE_DIR / "boe_gbpusd.csv", "GBP/USD Rate"),
        (BOE_DIR / "boe_bankrate.csv", "Bank Rate"),
    ],
    "MeasuringWorth": [
        (MW_DIR / "us_gdp.csv", "US GDP"),
    ],
    "FINRA": [
        (FINRA_DIR / "margin_debt.csv", "Margin Debt"),
    ],
}


def check_data_files():
    """Verify which data files are present."""
    print("\n📋 DATA FILE INVENTORY")
    print("=" * 70)

    total = 0
    found = 0
    missing_groups = {}

    for group, files in EXPECTED_FILES.items():
        group_found = 0
        group_total = len(files)
        group_missing = []

        for filepath, description in files:
            total += 1
            if filepath.exists():
                group_found += 1
                found += 1
            else:
                group_missing.append(description)

        status = "✓" if group_found == group_total else ("◐" if group_found > 0 else "✗")
        print(f"  {status} {group:<20} {group_found}/{group_total} files")

        if group_missing and group != "FRED cache":
            missing_groups[group] = group_missing

    print("-" * 70)
    print(f"  Total: {found}/{total} files present")

    if missing_groups:
        print("\n  Missing datasets:")
        for group, items in missing_groups.items():
            print(f"    {group}: {', '.join(items[:5])}")
            if len(items) > 5:
                print(f"      ... and {len(items)-5} more")

    # Assess backtest readiness
    print()
    fred_count = sum(1 for f, _ in EXPECTED_FILES["FRED cache"] if f.exists())
    has_shiller = (SHILLER_DIR / "ie_data.xls").exists() or (SHILLER_DIR / "ie_data.csv").exists()
    has_nber = any((NBER_DIR / f"m{s}.csv").exists() for s in ["13001", "13020", "13033"])

    if fred_count >= 20 and has_shiller and has_nber:
        print("  🟢 Ready for extended backtest (1907-2025)")
    elif fred_count >= 20 and has_shiller:
        print("  🟡 Ready for backtest (1871-2025 via Shiller + FRED)")
        print("     Download NBER data for full 1907 coverage")
    elif fred_count >= 15:
        print("  🟡 Ready for standard backtest (1971-2025)")
        print("     Download Shiller + NBER for extended coverage")
    else:
        print("  🔴 Insufficient data — run download with FRED_API_KEY set")

    return found, total


def ensure_directories():
    """Create all required data directories."""
    for d in [FRED_CACHE_DIR, NBER_DIR, SHILLER_DIR, SCHWERT_DIR,
              BOE_DIR, MW_DIR, FINRA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download historical data for MAC framework extended backtest"
    )
    parser.add_argument("--fred-only", action="store_true",
                        help="Download FRED series only")
    parser.add_argument("--check", action="store_true",
                        help="Verify data files and exit")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("MAC FRAMEWORK — HISTORICAL DATA DOWNLOAD")
    print("Extended Backtest: 1907-2025")
    print("=" * 70)
    print()

    ensure_directories()

    if args.check:
        check_data_files()
        return 0

    # Step 1: FRED series (automatic)
    print("📡 STEP 1: Downloading FRED series...")
    print("-" * 70)
    fred_ok = download_fred_series()

    if args.fred_only:
        print()
        check_data_files()
        return 0 if fred_ok else 1

    # Step 2: Shiller dataset (automatic)
    print()
    print("📡 STEP 2: Downloading Shiller dataset...")
    print("-" * 70)
    download_shiller_dataset()

    # Step 3: Manual download instructions
    print()
    print("📋 STEP 3: Manual downloads")
    print("-" * 70)
    print_manual_instructions()

    # Step 4: Verification
    check_data_files()

    return 0


if __name__ == "__main__":
    sys.exit(main())
