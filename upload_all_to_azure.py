"""
Upload all local data to Azure Table Storage.

Uploads:
  1. FRED cache (29 series from pickle) → fredseries table
  2. NBER historical series (13 series from CSVs) → fredseries table (prefixed NBER_)
  3. Schwert volatility → fredseries table (SCHWERT_VOL)
  4. BoE GBP/USD + Bank Rate → fredseries table (BOE_GBPUSD, BOE_BANKRATE)
  5. MeasuringWorth GDP → fredseries table (MW_GDP)
  6. FINRA margin debt → fredseries table (FINRA_MARGIN_DEBT)
  7. Backtest results → backtesthistory table
  8. Backtest cache → backtestcache table

Usage:
    python upload_all_to_azure.py                     # Upload everything
    python upload_all_to_azure.py --fred-only         # Only FRED pickle
    python upload_all_to_azure.py --historical-only   # Only historical CSVs
    python upload_all_to_azure.py --backtest-only     # Only backtest results
    python upload_all_to_azure.py --dry-run            # Preview only
    python upload_all_to_azure.py --verify             # Check what's in Azure
"""

import os
import sys
import argparse
import pickle
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from shared.database import get_database

PROJECT_ROOT = Path(__file__).parent
FRED_CACHE = PROJECT_ROOT / "data" / "fred_cache" / "fred_series_cache.pkl"
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"
BACKTEST_CSV = PROJECT_ROOT / "data" / "backtest_results" / "backtest_full_1971_2025.csv"
BACKTEST_VALIDATION = PROJECT_ROOT / "data" / "backtest_results" / "backtest_full_1971_2025.validation.json"


def series_to_upload_dict(dates, values):
    """Convert dates + values to the format save_fred_series expects."""
    clean_dates = []
    clean_values = []
    for d, v in zip(dates, values):
        if isinstance(d, pd.Timestamp):
            d_str = d.strftime("%Y-%m-%d")
        else:
            d_str = str(d)
        clean_dates.append(d_str)
        clean_values.append(None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v))
    return {"dates": clean_dates, "values": clean_values}


# ─────────────────────────────────────────────────────────────────────────────
# 1. FRED Pickle Cache
# ─────────────────────────────────────────────────────────────────────────────

def upload_fred_cache(db, dry_run=False):
    """Upload FRED pickle cache to fredseries table."""
    if not FRED_CACHE.exists():
        print("  ✗ FRED cache not found")
        return 0

    with open(FRED_CACHE, "rb") as f:
        cache = pickle.load(f)

    print(f"\n{'=' * 60}")
    print("FRED SERIES (from pickle cache)")
    print(f"{'=' * 60}")
    print(f"  {len(cache)} series in cache")

    uploaded = 0
    for sid, data in sorted(cache.items()):
        if not isinstance(data, pd.Series) or len(data) == 0:
            continue
        start = data.index.min().strftime("%Y-%m-%d")
        end = data.index.max().strftime("%Y-%m-%d")

        if dry_run:
            print(f"  [DRY] {sid}: {len(data)} pts ({start} to {end})")
            uploaded += 1
            continue

        upload = series_to_upload_dict(data.index, data.values)
        if db.save_fred_series(sid, upload):
            print(f"  ✓ {sid}: {len(data)} pts ({start} to {end})")
            uploaded += 1
        else:
            print(f"  ✗ {sid}: FAILED")

    print(f"  → {uploaded}/{len(cache)} series uploaded")
    return uploaded


# ─────────────────────────────────────────────────────────────────────────────
# 2. Historical Series (NBER, Schwert, BoE, MeasuringWorth, FINRA)
# ─────────────────────────────────────────────────────────────────────────────

HISTORICAL_SERIES = {
    # NBER Macrohistory
    "NBER_M13001": ("nber/m13001.csv", "date", "value", "Call Money Rate NYC"),
    "NBER_M13002": ("nber/m13002.csv", "date", "value", "Commercial Paper Rate NYC"),
    "NBER_M13009": ("nber/m13009.csv", "date", "value", "Fed Discount Rate NY"),
    "NBER_M13019": ("nber/m13019.csv", "date", "value", "Railroad Bond Yield High Grade"),
    "NBER_M13022": ("nber/m13022.csv", "date", "value", "Railroad Bond Yield 2nd Grade"),
    "NBER_M13024": ("nber/m13024.csv", "date", "value", "High Grade Railroad Bonds"),
    "NBER_M13026": ("nber/m13026.csv", "date", "value", "Industrial Bonds Aaa"),
    "NBER_M13033": ("nber/m13033.csv", "date", "value", "Long-Term US Govt Bond Yield"),
    "NBER_M13035": ("nber/m13035.csv", "date", "value", "Corporate Bonds Highest Rating"),
    "NBER_M13036": ("nber/m13036.csv", "date", "value", "Corporate Bonds Lowest Rating"),
    "NBER_M14076": ("nber/m14076.csv", "date", "value", "US Monetary Gold Stock"),
    # Schwert
    "SCHWERT_VOL": ("schwert/schwert_volatility.csv", "date", "volatility", "Schwert Realized Volatility"),
    # BoE
    "BOE_GBPUSD": ("boe/boe_gbpusd.csv", "date", "rate", "GBP/USD Exchange Rate"),
    "BOE_BANKRATE": ("boe/boe_bankrate.csv", "date", "rate", "BoE Official Bank Rate"),
    # MeasuringWorth
    "MW_GDP": ("measuringworth/us_gdp.csv", "year", "gdp", "US Nominal GDP"),
    # FINRA
    "FINRA_MARGIN_DEBT": ("finra/margin_debt.csv", "date", "margin_debt", "NYSE Margin Debt"),
}


def upload_historical(db, dry_run=False):
    """Upload all historical CSVs to fredseries table."""
    print(f"\n{'=' * 60}")
    print("HISTORICAL SERIES (CSVs)")
    print(f"{'=' * 60}")

    uploaded = 0
    for series_id, (rel_path, date_col, val_col, desc) in HISTORICAL_SERIES.items():
        csv_path = HISTORICAL_DIR / rel_path
        if not csv_path.exists():
            print(f"  ✗ {series_id}: file not found ({rel_path})")
            continue

        df = pd.read_csv(csv_path)
        if date_col not in df.columns or val_col not in df.columns:
            # GDP has year column instead of date
            if "year" in df.columns:
                df["date"] = df["year"].astype(str) + "-01-01"
                date_col = "date"
            else:
                print(f"  ✗ {series_id}: missing columns {date_col}/{val_col}")
                continue

        dates = df[date_col].astype(str).tolist()
        values = df[val_col].tolist()
        non_null = sum(1 for v in values if v is not None and not (isinstance(v, float) and np.isnan(v)))

        if dry_run:
            print(f"  [DRY] {series_id}: {non_null} pts — {desc}")
            uploaded += 1
            continue

        upload = series_to_upload_dict(dates, values)
        if db.save_fred_series(series_id, upload):
            print(f"  ✓ {series_id}: {non_null} pts — {desc}")
            uploaded += 1
        else:
            print(f"  ✗ {series_id}: FAILED")

    print(f"  → {uploaded}/{len(HISTORICAL_SERIES)} historical series uploaded")
    return uploaded


# ─────────────────────────────────────────────────────────────────────────────
# 3. Backtest Results + Cache
# ─────────────────────────────────────────────────────────────────────────────

def upload_backtest(db, dry_run=False):
    """Upload backtest results and pre-computed API cache."""
    if not BACKTEST_CSV.exists():
        print("  ✗ Backtest results CSV not found")
        return 0

    df = pd.read_csv(BACKTEST_CSV)
    print(f"\n{'=' * 60}")
    print("BACKTEST RESULTS")
    print(f"{'=' * 60}")
    print(f"  {len(df)} observations ({df['date'].min()} to {df['date'].max()})")

    if dry_run:
        print(f"  [DRY] Would upload {len(df)} backtest records + API cache")
        return len(df)

    # Upload individual records
    results = df.to_dict("records")
    batch_size = 100
    uploaded = 0
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]
        saved = db.save_backtest_results_batch(batch)
        uploaded += saved
        if (i + batch_size) % 500 == 0 or i + batch_size >= len(results):
            pct = min(100, (i + batch_size) / len(results) * 100)
            print(f"  Progress: {uploaded} records ({pct:.1f}%)")

    print(f"  → {uploaded}/{len(df)} backtest records uploaded")

    # Upload chunked cache
    time_series = []
    for _, row in df.iterrows():
        point = {
            "date": row["date"],
            "mac_score": row["mac_score"],
            "pillar_scores": {
                "liquidity": row.get("liquidity", 0),
                "valuation": row.get("valuation", 0),
                "positioning": row.get("positioning", 0),
                "volatility": row.get("volatility", 0),
                "policy": row.get("policy", 0),
                "contagion": row.get("contagion", 0),
                "private_credit": row.get("private_credit", 0),
            },
            "interpretation": row.get("interpretation", ""),
            "crisis_event": row.get("crisis_event", ""),
            "data_quality": row.get("data_quality", ""),
        }
        time_series.append(point)

    try:
        with open(BACKTEST_VALIDATION) as f:
            validation = json.load(f)
    except Exception:
        validation = {}

    backtest_response = {
        "status": "success",
        "data_source": "Pre-computed (Azure Table Cache)",
        "parameters": {
            "start_date": df["date"].min(),
            "end_date": df["date"].max(),
            "data_points": len(df),
        },
        "statistics": {
            "min_mac": float(df["mac_score"].min()),
            "max_mac": float(df["mac_score"].max()),
            "mean_mac": float(df["mac_score"].mean()),
            "std_mac": float(df["mac_score"].std()),
        },
        "crisis_detection": validation.get("crisis_detection", {}),
        "time_series": time_series,
    }

    if db.save_backtest_cache_chunked(backtest_response):
        print("  ✓ Backtest API cache saved")
    else:
        print("  ✗ Backtest API cache FAILED")

    return uploaded


# ─────────────────────────────────────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────────────────────────────────────

def verify(db):
    """Check what's currently in Azure."""
    print(f"\n{'=' * 60}")
    print("AZURE TABLE STORAGE CONTENTS")
    print(f"{'=' * 60}")

    fred_count = db.get_fred_series_count()
    print(f"  FRED/Historical series: {fred_count}")
    if fred_count > 0:
        series_list = db.list_fred_series()
        for s in series_list[:10]:
            print(f"    {s['series_id']:25s} {s['total_points']:>6d} pts  ({s['start_date']} to {s['end_date']})")
        if len(series_list) > 10:
            print(f"    ... and {len(series_list) - 10} more")

    backtest_count = db.get_backtest_count()
    print(f"\n  Backtest records: {backtest_count}")

    cache = db.get_backtest_cache_chunked()
    if cache:
        ts = len(cache.get("time_series", []))
        print(f"  Backtest API cache: {ts} data points")
    else:
        print("  Backtest API cache: Not found")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Upload all data to Azure Table Storage")
    parser.add_argument("--fred-only", action="store_true")
    parser.add_argument("--historical-only", action="store_true")
    parser.add_argument("--backtest-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    print("=" * 60)
    print("UPLOAD ALL DATA TO AZURE TABLE STORAGE")
    print("=" * 60)
    print(f"  Connection: {'✓ Set' if conn_str else '✗ NOT SET'}")

    if not conn_str and not args.dry_run:
        print("\n  ERROR: AZURE_STORAGE_CONNECTION_STRING not set in .env")
        return 1

    db = get_database()
    print(f"  Connected: {'✓' if db.connected else '✗'}")

    if args.dry_run:
        print("\n  *** DRY RUN — no data will be uploaded ***")

    if args.verify:
        verify(db)
        return 0

    total = 0
    do_all = not (args.fred_only or args.historical_only or args.backtest_only)

    if args.fred_only or do_all:
        total += upload_fred_cache(db, args.dry_run)

    if args.historical_only or do_all:
        total += upload_historical(db, args.dry_run)

    if args.backtest_only or do_all:
        total += upload_backtest(db, args.dry_run)

    if not args.dry_run:
        verify(db)

    print(f"\n{'=' * 60}")
    print(f"  UPLOAD COMPLETE — {total} items processed")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
