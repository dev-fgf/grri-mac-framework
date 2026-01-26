#!/usr/bin/env python
"""
Master script to run all backtest analysis.

This script runs:
1. Basic statistical analysis and figures (analyze_backtest_results.py)
2. Validation metrics for academic paper (generate_validation_metrics.py)
3. Comparison to alternative indicators (compare_to_alternatives.py)

Run this after the backtest completes to generate all outputs for the paper.
"""

import subprocess
import sys
import os


def run_script(script_name, description):
    """Run a Python script and report results."""
    print("\n" + "="*80)
    print(f"Running: {description}")
    print("="*80)
    print()

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=False,
            text=True
        )
        print(f"\n[SUCCESS] {script_name} completed")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n[FAILED] {script_name} failed with error code {e.returncode}")
        return False


def check_prerequisites():
    """Check that backtest results exist."""
    if not os.path.exists("backtest_results.csv"):
        print("ERROR: backtest_results.csv not found!")
        print()
        print("Please run the backtest first:")
        print("  python run_backtest.py --start 2004-01-01 --end 2024-12-31 --frequency weekly")
        print()
        return False

    return True


def main():
    """Run all analysis scripts."""
    print("="*80)
    print("MAC FRAMEWORK - COMPLETE ANALYSIS SUITE")
    print("="*80)
    print()
    print("This will generate all figures and tables for the academic paper.")
    print()

    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Run analysis scripts
    scripts = [
        ("analyze_backtest_results.py", "Basic Analysis & Figures"),
        ("generate_validation_metrics.py", "Validation Metrics"),
        ("compare_to_alternatives.py", "Comparison to Alternatives"),
    ]

    results = []
    for script, description in scripts:
        success = run_script(script, description)
        results.append((script, success))

    # Summary
    print("\n" + "="*80)
    print("ANALYSIS SUITE COMPLETE")
    print("="*80)
    print()
    print("Results:")
    for script, success in results:
        status = "[SUCCESS]" if success else "[FAILED]"
        print(f"  {status} {script}")

    print()
    print("Generated Outputs:")
    print()
    print("  Figures/:")
    print("    - mac_timeseries.png         (Figure 1: MAC over time)")
    print("    - gfc_pillars.png            (Figure 2: GFC pillar decomposition)")
    print("    - crisis_comparison.png      (Figure 3: Crisis comparison)")
    print("    - mac_vs_vix.png            (Figure 4: MAC vs VIX)")
    print("    - mac_vs_credit.png         (Figure 5: MAC vs credit spreads)")
    print("    - pillar_correlation.png    (Figure 6: Pillar correlation matrix)")
    print()
    print("  Tables/:")
    print("    - summary_statistics.csv    (Table 1: Overall stats)")
    print("    - crisis_analysis.csv       (Table 2: Crisis breakdown)")
    print("    - pillar_statistics.csv     (Table 3: Pillar stats)")
    print("    - regime_distribution.csv   (Table 4: Time in each regime)")
    print("    - crisis_warnings.csv       (Table 5: Warning analysis)")
    print("    - validation_summary.csv    (Table 6: Validation metrics)")
    print("    - validation_latex.txt      (LaTeX code for paper)")
    print("    - pillar_correlation.csv    (Table 7: Correlations)")
    print("    - incremental_value.csv     (Table 8: Incremental value)")
    print()
    print("Next Steps:")
    print("  1. Review all figures and tables")
    print("  2. Copy figures to paper (docs/figures/)")
    print("  3. Use validation metrics to complete Section 5")
    print("  4. Include LaTeX tables in paper")
    print()

    # Check if all succeeded
    all_success = all(success for _, success in results)
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
