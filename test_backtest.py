#!/usr/bin/env python
"""
Quick test of backtest runner - tests a few key dates.

This is faster than running the full 20-year backtest.
"""

import os
import sys
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grri_mac.backtest.runner import BacktestRunner


def test_key_dates():
    """Test MAC calculation on key historical dates."""

    # Check for FRED API key
    if not os.environ.get("FRED_API_KEY"):
        print("ERROR: FRED_API_KEY environment variable not set!")
        print("Get your free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        return False

    runner = BacktestRunner()

    # Key dates to test
    test_dates = [
        ("2007-07-01", "Pre-GFC (should show moderate stress)"),
        ("2008-09-15", "Lehman Day (should show extreme stress)"),
        ("2020-03-16", "COVID-19 panic (should show extreme stress)"),
        ("2023-03-10", "SVB Crisis (should show elevated stress)"),
        ("2024-01-15", "Recent normal period (should show comfortable)"),
    ]

    print("=" * 70)
    print("MAC FRAMEWORK - QUICK TEST")
    print("=" * 70)
    print()

    all_passed = True

    for date_str, description in test_dates:
        date = datetime.strptime(date_str, "%Y-%m-%d")

        print(f"Testing: {date_str} - {description}")

        try:
            point = runner.calculate_mac_for_date(date)

            print(f"  MAC Score: {point.mac_score:.3f}")
            print(f"  Status: {point.interpretation}")
            print(f"  Pillars:")
            for pillar, score in point.pillar_scores.items():
                print(f"    {pillar:12s}: {score:.3f}")
            if point.crisis_event:
                print(f"  Crisis: {point.crisis_event}")
            print(f"  Data Quality: {point.data_quality}")
            print("  [OK] Success")

        except Exception as e:
            print(f"  [FAILED]: {e}")
            all_passed = False

        print()

    print("=" * 70)
    if all_passed:
        print("[SUCCESS] All tests passed!")
        print()
        print("Ready to run full backtest:")
        print("  python run_backtest.py --start 2004-01-01 --end 2024-12-31")
    else:
        print("[FAILED] Some tests failed. Check errors above.")

    return all_passed


if __name__ == "__main__":
    success = test_key_dates()
    sys.exit(0 if success else 1)
