"""
Comprehensive seeding script to upload FRED data and backtest results to Azure Tables.

This script:
1. Loads the local FRED cache (24 series, 1970-2025)
2. Loads backtest results (2,814 weekly observations)
3. Uploads everything to Azure Table Storage

This ensures the Azure API functions don't need to re-fetch or re-compute data.

Usage:
    python seed_azure_tables.py                    # Seed everything
    python seed_azure_tables.py --fred-only        # Only FRED series
    python seed_azure_tables.py --backtest-only    # Only backtest results
    python seed_azure_tables.py --dry-run          # Show what would be uploaded
"""

import os
import sys
import argparse
import pickle
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

# Add api folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from shared.database import get_database


# Paths to local data
FRED_CACHE_FILE = Path(__file__).parent / "data" / "fred_cache" / "fred_series_cache.pkl"
BACKTEST_RESULTS_FILE = Path(__file__).parent / "data" / "backtest_results" / "backtest_full_1971_2025.csv"
BACKTEST_VALIDATION_FILE = Path(__file__).parent / "data" / "backtest_results" / "backtest_full_1971_2025.validation.json"


def load_fred_cache() -> dict:
    """Load the local FRED cache from pickle file."""
    if not FRED_CACHE_FILE.exists():
        print(f"ERROR: FRED cache file not found at {FRED_CACHE_FILE}")
        return {}
    
    with open(FRED_CACHE_FILE, "rb") as f:
        cache = pickle.load(f)
    
    return cache


def load_backtest_results() -> pd.DataFrame:
    """Load the backtest results CSV."""
    if not BACKTEST_RESULTS_FILE.exists():
        print(f"ERROR: Backtest results file not found at {BACKTEST_RESULTS_FILE}")
        return pd.DataFrame()
    
    return pd.read_csv(BACKTEST_RESULTS_FILE)


def convert_series_to_dict(series: pd.Series) -> dict:
    """Convert a pandas Series to a dict with dates and values lists."""
    # Handle NaN values by converting to None
    dates = [d.strftime("%Y-%m-%d") for d in series.index]
    values = [None if pd.isna(v) else float(v) for v in series.values]
    
    return {
        "dates": dates,
        "values": values,
    }


def seed_fred_series(db, dry_run: bool = False) -> int:
    """Upload all FRED series to Azure Tables.
    
    Returns count of series uploaded.
    """
    cache = load_fred_cache()
    if not cache:
        return 0
    
    print("\n" + "=" * 60)
    print("SEEDING FRED SERIES DATA")
    print("=" * 60)
    print(f"Found {len(cache)} series in local cache")
    
    if dry_run:
        print("\n[DRY RUN] Would upload the following series:")
        for series_id, data in sorted(cache.items()):
            if isinstance(data, pd.Series) and len(data) > 0:
                start = data.index.min().strftime("%Y-%m-%d")
                end = data.index.max().strftime("%Y-%m-%d")
                print(f"  {series_id}: {len(data)} observations ({start} to {end})")
        return len(cache)
    
    uploaded = 0
    for series_id, data in sorted(cache.items()):
        if isinstance(data, pd.Series) and len(data) > 0:
            series_dict = convert_series_to_dict(data)
            
            start = data.index.min().strftime("%Y-%m-%d")
            end = data.index.max().strftime("%Y-%m-%d")
            
            success = db.save_fred_series(series_id, series_dict)
            if success:
                uploaded += 1
                print(f"  ✓ {series_id}: {len(data)} observations ({start} to {end})")
            else:
                print(f"  ✗ {series_id}: FAILED")
    
    print(f"\nUploaded {uploaded}/{len(cache)} FRED series")
    return uploaded


def seed_backtest_results(db, dry_run: bool = False) -> int:
    """Upload backtest results to Azure Tables.
    
    Returns count of records uploaded.
    """
    df = load_backtest_results()
    if df.empty:
        return 0
    
    print("\n" + "=" * 60)
    print("SEEDING BACKTEST RESULTS")
    print("=" * 60)
    print(f"Found {len(df)} observations in local backtest results")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    
    if dry_run:
        print("\n[DRY RUN] Would upload:")
        print(f"  {len(df)} weekly MAC scores")
        print(f"  Years covered: {sorted(df['date'].str[:4].unique())}")
        print(f"  Columns: {list(df.columns)}")
        return len(df)
    
    # Convert DataFrame to list of dicts
    results = df.to_dict('records')
    
    print(f"\nUploading {len(results)} records...")
    
    # Upload in batches for progress reporting
    batch_size = 100
    uploaded = 0
    
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]
        saved = db.save_backtest_results_batch(batch)
        uploaded += saved
        
        if (i + batch_size) % 500 == 0 or i + batch_size >= len(results):
            pct = min(100, (i + batch_size) / len(results) * 100)
            print(f"  Progress: {uploaded} records ({pct:.1f}%)")
    
    print(f"\nUploaded {uploaded}/{len(df)} backtest records")
    return uploaded


def seed_backtest_cache(db, dry_run: bool = False) -> bool:
    """Upload the full backtest response as a chunked cache.
    
    This allows the API to return the full 54-year backtest instantly.
    """
    import json
    
    df = load_backtest_results()
    if df.empty:
        return False
    
    print("\n" + "=" * 60)
    print("SEEDING BACKTEST CACHE (API Response)")
    print("=" * 60)
    
    # Build the API response format
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
    
    # Load validation data
    try:
        with open(BACKTEST_VALIDATION_FILE) as f:
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
    
    if dry_run:
        print("\n[DRY RUN] Would upload:")
        print(f"  Full backtest cache with {len(time_series)} data points")
        print(f"  Estimated chunks: {(len(time_series) + 99) // 100}")
        return True
    
    print(f"Uploading backtest cache ({len(time_series)} points)...")
    success = db.save_backtest_cache_chunked(backtest_response)
    
    if success:
        print("  ✓ Backtest cache saved successfully")
    else:
        print("  ✗ Failed to save backtest cache")
    
    return success


def verify_uploads(db):
    """Verify uploaded data by reading back counts."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    # Check FRED series
    fred_count = db.get_fred_series_count()
    print(f"FRED series in Azure: {fred_count}")
    
    if fred_count > 0:
        series_list = db.list_fred_series()
        for series in series_list[:5]:
            print(f"  - {series['series_id']}: {series['total_points']} pts ({series['start_date']} to {series['end_date']})")
        if len(series_list) > 5:
            print(f"  ... and {len(series_list) - 5} more")
    
    # Check backtest history
    backtest_count = db.get_backtest_count()
    print(f"\nBacktest history records: {backtest_count}")
    
    # Check backtest cache
    cache = db.get_backtest_cache_chunked()
    if cache:
        ts_len = len(cache.get("time_series", []))
        print(f"Backtest cache: {ts_len} time series points")
    else:
        print("Backtest cache: Not found")


def main():
    parser = argparse.ArgumentParser(description="Seed Azure Tables with FRED data and backtest results")
    parser.add_argument("--fred-only", action="store_true", help="Only upload FRED series")
    parser.add_argument("--backtest-only", action="store_true", help="Only upload backtest results")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    parser.add_argument("--verify", action="store_true", help="Only verify existing data (no upload)")
    args = parser.parse_args()
    
    # Check environment
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    print("=" * 60)
    print("AZURE TABLES SEEDING SCRIPT")
    print("=" * 60)
    print(f"Connection string: {'✓ Set' if conn_str else '✗ NOT SET'}")
    
    if not conn_str and not args.dry_run:
        print("\nERROR: AZURE_STORAGE_CONNECTION_STRING not set")
        print("Please set it in .env file or environment")
        return 1
    
    # Get database connection
    db = get_database()
    print(f"Database connected: {'✓' if db.connected else '✗ (will use dry-run mode)'}")
    
    if args.dry_run:
        print("\n*** DRY RUN MODE - No data will be uploaded ***")
    
    if args.verify:
        verify_uploads(db)
        return 0
    
    # Run uploads
    total_uploaded = 0
    
    if not args.backtest_only:
        total_uploaded += seed_fred_series(db, dry_run=args.dry_run)
    
    if not args.fred_only:
        total_uploaded += seed_backtest_results(db, dry_run=args.dry_run)
        seed_backtest_cache(db, dry_run=args.dry_run)
    
    # Verify
    if not args.dry_run:
        verify_uploads(db)
    
    print("\n" + "=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
