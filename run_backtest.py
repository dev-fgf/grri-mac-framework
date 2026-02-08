#!/usr/bin/env python
"""
Run MAC framework backtest for the academic paper.

This script runs historical backtests and generates empirical results
for validation.  Supports three modes:
  Standard:  1971-2025  (FRED data only)
  Extended:  1962-2025  (FRED + Moody's proxies)
  Full:      1907-2025  (FRED + NBER + Shiller + Schwert + BoE + FINRA)

All results are stored persistently in data/backtest_results/.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import argparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed.")
    print("Install with: pip install python-dotenv")

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Results directory for all backtest outputs
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"

from grri_mac.backtest.runner import BacktestRunner


def get_output_path(output_file: str) -> Path:
    """Get full output path, ensuring results directory exists."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # If output_file is just a filename, put it in results dir
    output_path = Path(output_file)
    if not output_path.is_absolute() and output_path.parent == Path('.'):
        output_path = RESULTS_DIR / output_file
    
    return output_path


def main():
    """Run backtest and generate results."""
    parser = argparse.ArgumentParser(
        description="Run MAC framework backtest"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="1971-02-05",
        help="Start date (YYYY-MM-DD).  Use 1907-01-01 for full history."
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Run extended backtest from 1907 (requires historical data downloads)"
    )
    parser.add_argument(
        "--era-weights",
        action="store_true",
        help="Use era-specific pillar weights (recommended for pre-1971 backtest)"
    )
    parser.add_argument(
        "--frequency",
        type=str,
        default="weekly",
        choices=["daily", "weekly", "monthly"],
        help="Backtest frequency"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backtest_results.csv",
        help="Output CSV file"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear cache and fetch fresh data from FRED (ensures data integrity)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate cached data coverage and exit (no backtest run)"
    )

    args = parser.parse_args()

    # Parse dates
    if args.extended:
        start_date = datetime(1907, 1, 1)
        print("Using --extended mode: backtest from 1907")
    else:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    # Determine backtest mode label
    if start_date.year < 1962:
        mode_label = f"EXTENDED ({start_date.year}-{end_date.year})"
    elif start_date.year < 1990:
        mode_label = f"HISTORICAL ({start_date.year}-{end_date.year})"
    else:
        mode_label = f"STANDARD ({start_date.year}-{end_date.year})"

    print("=" * 70)
    print(f"MAC FRAMEWORK BACKTEST — {mode_label}")
    print("=" * 70)
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Frequency: {args.frequency}")
    print(f"Output: {args.output}")
    print("=" * 70)
    print()

    # Check for FRED API key
    if not os.environ.get("FRED_API_KEY"):
        print("⚠️  WARNING: FRED_API_KEY environment variable not set!")
        print("   The backtest will fail without a valid FRED API key.")
        print("   Get your free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Exiting.")
            return 1

    # Handle --fresh flag to clear cache
    if args.fresh:
        from grri_mac.data.fred import CACHE_FILE
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            print("🗑️  Cleared FRED data cache. Will fetch fresh data.")
        else:
            print("Cache already clear.")

    # Handle --validate flag to check data integrity
    if args.validate:
        from grri_mac.data.fred import FREDClient, CACHE_FILE
        print("\n🔍 VALIDATING CACHED DATA INTEGRITY\n")
        print(f"Cache file: {CACHE_FILE}")
        
        if not CACHE_FILE.exists():
            print("❌ No cache file found. Run without --validate to build cache.")
            return 1
        
        fred = FREDClient()
        cache = fred._bulk_cache
        
        # Historical proxy information
        PROXY_INFO = {
            "VIXCLS": "Proxy: NASDAQCOM realized vol (1971+) with 1.2x VRP",
            "VXOCLS": "Proxy: NASDAQCOM realized vol (1971+) with 1.2x VRP",
            "BAMLH0A0HYM2": "Proxy: (BAA-AAA)*4.5 for HY OAS (1919+)",
            "BAMLC0A0CM": "Proxy: BAA-DGS10 - 0.4 for IG OAS (1919+)",
            "TEDRATE": "Proxy: FEDFUNDS-TB3MS (1954-1986)",
            "BAA10Y": "Proxy: BAA-DGS10 (1919+)",
        }
        
        print(f"\nCached series: {len(cache)}")
        print("-" * 75)
        print(f"{'SERIES':<20} | {'DATE RANGE':<25} | {'OBS':>6} | {'NULLS':>5} | STATUS")
        print("-" * 75)
        
        all_valid = True
        for series_id, data in sorted(cache.items()):
            if data is not None and len(data) > 0:
                min_date = data.index.min().date()
                max_date = data.index.max().date()
                obs_count = len(data)
                nulls = data.isna().sum()
                
                # Check if series covers our backtest period
                covers_1971 = min_date <= datetime(1971, 1, 1).date()
                
                if covers_1971:
                    status = "✓ Full coverage"
                elif series_id in PROXY_INFO:
                    status = "◐ Has proxy"
                else:
                    status = "⚠ Limited"
                
                print(f"{series_id:<20} | {min_date} to {max_date} | {obs_count:6} | {nulls:5} | {status}")
                
                # Show proxy info if applicable
                if series_id in PROXY_INFO and not covers_1971:
                    print(f"   └─ {PROXY_INFO[series_id]}")
                
                if nulls > obs_count * 0.1:  # More than 10% nulls is concerning
                    print(f"   ⚠️  High null rate ({nulls/obs_count*100:.1f}%)")
                    high_null_warning = True  # Warning only, not failure
            else:
                print(f"{series_id:<20} | EMPTY OR NULL")
                all_valid = False
        
        print("-" * 75)
        print("\n📋 DATA INTEGRITY SUMMARY:")
        print(f"   Core series (1970+):    {sum(1 for s, d in cache.items() if d is not None and len(d) > 0 and d.index.min().date() <= datetime(1971,1,1).date())}")
        print(f"   Series with proxies:    {sum(1 for s in cache if s in PROXY_INFO)}")
        print(f"   Limited coverage:       {len(cache) - sum(1 for s, d in cache.items() if d is not None and len(d) > 0 and d.index.min().date() <= datetime(1971,1,1).date()) - sum(1 for s in cache if s in PROXY_INFO and s not in [s2 for s2, d2 in cache.items() if d2 is not None and len(d2) > 0 and d2.index.min().date() <= datetime(1971,1,1).date()])}")
        
        if all_valid:
            print("\n✅ Cache validated successfully - safe to run backtest")
            if 'high_null_warning' in dir():
                print("   (Some series have high null rates but this is expected)")
        else:
            print("\n❌ Cache has critical issues - consider running with --fresh")
        
        return 0

    print("Initializing backtest runner...")
    use_era_weights = getattr(args, 'era_weights', False)
    runner = BacktestRunner(use_era_weights=use_era_weights)
    
    if start_date.year < 1962:
        print("⚡ Extended mode: era-specific proxy chains active")
        if use_era_weights:
            print("   Using era-specific pillar weights")
        else:
            print("   Using equal pillar weights (pass --era-weights for era-specific)")
    

    print("Starting backtest... This may take several minutes.")
    print()

    # Run backtest
    try:
        df = runner.run_backtest(
            start_date=start_date,
            end_date=end_date,
            frequency=args.frequency
        )

        print()
        print("=" * 70)
        print("BACKTEST COMPLETE")
        print("=" * 70)
        print(f"Total data points: {len(df)}")
        print(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
        print()

        # Generate validation report
        print("Generating validation report...")
        validation = runner.generate_validation_report(df)

        print()
        print("VALIDATION METRICS:")
        print("-" * 70)
        print(f"Total points analyzed:     {validation['total_points']}")
        print(f"Crisis points:             {validation['crisis_points']}")
        print(f"Non-crisis points:         {validation['non_crisis_points']}")
        print()
        print(f"Average MAC (overall):     {validation['avg_mac_overall']:.3f}")
        if validation['avg_mac_during_crisis'] is not None:
            print(f"Average MAC (crisis):      {validation['avg_mac_during_crisis']:.3f}")
        else:
            print(f"Average MAC (crisis):      N/A (no crisis points in range)")
        if validation['avg_mac_non_crisis'] is not None:
            print(f"Average MAC (non-crisis):  {validation['avg_mac_non_crisis']:.3f}")
        else:
            print(f"Average MAC (non-crisis):  N/A")
        print()
        print(f"Crises evaluated:          {validation['crises_evaluated']}")
        print(f"Crises with warning:       {validation['crises_with_warning']}")
        print(f"True positive rate:        {validation['true_positive_rate']:.1%}")
        print()
        print(f"Min MAC score:             {validation['min_mac']:.3f}")
        print(f"Max MAC score:             {validation['max_mac']:.3f}")
        print("-" * 70)

        # Save results
        output_path = get_output_path(args.output)
        print()
        print(f"Saving results to {output_path}...")
        df.to_csv(output_path)
        
        # Also save validation summary
        validation_path = output_path.with_suffix('.validation.json')
        import json
        with open(validation_path, 'w') as f:
            # Convert any non-serializable values
            validation_serializable = {
                k: (v if not isinstance(v, float) or not (v != v) else None)  # Handle NaN
                for k, v in validation.items()
            }
            json.dump(validation_serializable, f, indent=2, default=str)
        print(f"Saving validation metrics to {validation_path}...")

        print()
        print("✓ Backtest complete! Results saved successfully.")
        print(f"   Results directory: {RESULTS_DIR}")
        print()
        print("Next steps:")
        print(f"  1. Open {output_path} in Excel/Python to visualize")
        print("  2. Use results to complete academic paper validation section")
        print("  3. Generate figures for crisis periods")

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)
        print(f"Backtest failed with error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
