#!/usr/bin/env python
"""
Run MAC framework backtest for the academic paper.

This script runs a 20-year backtest (2004-2024) and generates
empirical results for validation.
"""

import os
import sys
from datetime import datetime
import argparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed.")
    print("Install with: pip install python-dotenv")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grri_mac.backtest.runner import BacktestRunner


def main():
    """Run backtest and generate results."""
    parser = argparse.ArgumentParser(
        description="Run MAC framework backtest"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2004-01-01",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="End date (YYYY-MM-DD)"
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

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")

    print("=" * 70)
    print("MAC FRAMEWORK 20-YEAR BACKTEST")
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

    print("Initializing backtest runner...")
    runner = BacktestRunner()

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
        print(f"Average MAC (crisis):      {validation['avg_mac_during_crisis']:.3f}")
        print(f"Average MAC (non-crisis):  {validation['avg_mac_non_crisis']:.3f}")
        print()
        print(f"Crises evaluated:          {validation['crises_evaluated']}")
        print(f"Crises with warning:       {validation['crises_with_warning']}")
        print(f"True positive rate:        {validation['true_positive_rate']:.1%}")
        print()
        print(f"Min MAC score:             {validation['min_mac']:.3f}")
        print(f"Max MAC score:             {validation['max_mac']:.3f}")
        print("-" * 70)

        # Save results
        print()
        print(f"Saving results to {args.output}...")
        df.to_csv(args.output)

        print()
        print("✓ Backtest complete! Results saved successfully.")
        print()
        print("Next steps:")
        print("  1. Open", args.output, "in Excel/Python to visualize")
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
