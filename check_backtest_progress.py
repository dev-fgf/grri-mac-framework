#!/usr/bin/env python
"""Check backtest progress."""

import os
import sys

def check_progress():
    """Check if backtest results file exists and show progress."""

    output_file = "backtest_results.csv"

    if not os.path.exists(output_file):
        print("Backtest not yet completed. CSV file not found.")
        print()
        print("To monitor progress, check the background task output:")
        print("  tail -f C:\\Users\\marty\\AppData\\Local\\Temp\\claude\\c--Users-marty-OneDrive-Documents-GitHub-grri-mac-framework\\tasks\\b505ceb.output")
        return False

    # Count lines in CSV (subtract 1 for header)
    with open(output_file, 'r') as f:
        lines = len(f.readlines()) - 1

    total_expected = 1095  # Roughly 21 years * 52 weeks
    percent = (lines / total_expected) * 100

    print(f"Backtest Progress: {lines} / ~{total_expected} data points ({percent:.1f}%)")
    print(f"Output file: {output_file}")

    if lines >= total_expected * 0.95:
        print("\n[SUCCESS] Backtest appears to be complete!")
        return True
    else:
        print("\nBacktest still running...")
        return False

if __name__ == "__main__":
    success = check_progress()
    sys.exit(0 if success else 1)
