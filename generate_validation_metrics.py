#!/usr/bin/env python
"""
Generate validation metrics for academic paper Section 5.

Calculates:
- True positive rate (crises correctly predicted)
- False positive rate (warnings without crises)
- Lead time (days of warning before crisis)
- Comparison to alternative stress indices
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grri_mac.backtest.crisis_events import CRISIS_EVENTS


def load_results(filename="backtest_results.csv"):
    """Load backtest results."""
    if not os.path.exists(filename):
        print(f"ERROR: {filename} not found!")
        print("Run the backtest first: python run_backtest.py")
        sys.exit(1)

    df = pd.read_csv(filename, index_col='date', parse_dates=True)
    print(f"Loaded {len(df)} data points from {df.index.min().date()} to {df.index.max().date()}")
    return df


def calculate_crisis_warnings(df, warning_threshold=0.5, warning_window_days=90):
    """
    Calculate true positive rate and lead time for crisis warnings.

    A "warning" is defined as MAC score < warning_threshold in the
    warning_window_days before a crisis starts.

    Args:
        df: Backtest results DataFrame
        warning_threshold: MAC score below which constitutes a warning (default 0.5 = THIN regime)
        warning_window_days: Days before crisis to look for warnings (default 90)

    Returns:
        Dictionary with validation metrics
    """
    results = []

    for crisis in CRISIS_EVENTS:
        # Check if crisis is in backtest range
        if crisis.start_date < df.index.min() or crisis.end_date > df.index.max():
            continue

        # Look for warnings in the window before crisis
        warning_window_start = crisis.start_date - timedelta(days=warning_window_days)
        warning_period = df[
            (df.index >= warning_window_start) &
            (df.index < crisis.start_date)
        ]

        # Check for warning signals: level-based OR momentum-based
        level_warnings = warning_period[
            warning_period['mac_score'] < warning_threshold
        ]

        # Momentum-based: MAC below relaxed threshold AND rapid deterioration
        momentum_warnings = pd.DataFrame()
        if 'momentum_4w' in warning_period.columns:
            momentum_warnings = warning_period[
                (warning_period['mac_score'] < warning_threshold + 0.1)
                & (warning_period['momentum_4w'].fillna(0) < -0.04)
            ]

        warnings = pd.concat(
            [level_warnings, momentum_warnings]
        ).drop_duplicates()

        has_warning = len(warnings) > 0

        # Calculate lead time (days from first warning to crisis)
        lead_time = None
        if has_warning:
            first_warning_date = warnings.index[0]
            lead_time = (crisis.start_date - first_warning_date).days

        # Get minimum MAC score during warning period
        min_mac_before = warning_period['mac_score'].min() if len(warning_period) > 0 else None

        # Get minimum MAC score during crisis
        crisis_period = df[
            (df.index >= crisis.start_date) &
            (df.index <= crisis.end_date)
        ]
        min_mac_during = crisis_period['mac_score'].min() if len(crisis_period) > 0 else None

        results.append({
            'crisis': crisis.name,
            'start_date': crisis.start_date.date(),
            'severity': crisis.severity,
            'warning_detected': 'Yes' if has_warning else 'No',
            'lead_time_days': lead_time if has_warning else 0,
            'min_mac_before_crisis': f"{min_mac_before:.3f}" if min_mac_before else "N/A",
            'min_mac_during_crisis': f"{min_mac_during:.3f}" if min_mac_during else "N/A",
            'warning_window_days': warning_window_days,
        })

    return pd.DataFrame(results)


def calculate_false_positives(df, warning_threshold=0.5):
    """
    Calculate false positive rate.

    A false positive is a period where MAC < threshold but no crisis occurs
    within the next 90 days.
    """
    # Get all dates where MAC < threshold
    warning_dates = df[df['mac_score'] < warning_threshold].index

    false_positives = 0
    true_positives = 0

    for date in warning_dates:
        # Check if any crisis starts within next 90 days
        has_crisis = False
        for crisis in CRISIS_EVENTS:
            if crisis.start_date >= date and crisis.start_date <= date + timedelta(days=90):
                has_crisis = True
                break

        if has_crisis:
            true_positives += 1
        else:
            false_positives += 1

    total_warnings = len(warning_dates)
    false_positive_rate = false_positives / total_warnings if total_warnings > 0 else 0

    return {
        'total_warnings': total_warnings,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_positive_rate': false_positive_rate,
    }


def generate_validation_report(df):
    """Generate comprehensive validation report."""
    print("\n" + "="*80)
    print("VALIDATION METRICS FOR ACADEMIC PAPER")
    print("="*80)
    print()

    # Crisis warning analysis
    print("Analyzing crisis prediction performance...")
    warning_df = calculate_crisis_warnings(df, warning_threshold=0.5, warning_window_days=90)

    os.makedirs("tables", exist_ok=True)
    warning_df.to_csv('tables/crisis_warnings.csv', index=False)

    print("\n" + "-"*80)
    print("CRISIS WARNING ANALYSIS")
    print("-"*80)
    print(warning_df.to_string(index=False))
    print("-"*80)
    print()

    # Calculate summary statistics
    total_crises = len(warning_df)
    crises_warned = warning_df['warning_detected'].value_counts().get('Yes', 0)
    true_positive_rate = crises_warned / total_crises if total_crises > 0 else 0

    warned_crises = warning_df[warning_df['warning_detected'] == 'Yes']
    avg_lead_time = warned_crises['lead_time_days'].mean() if len(warned_crises) > 0 else 0

    print("\nKEY METRICS:")
    print(f"  Total Crises Evaluated: {total_crises}")
    print(f"  Crises with Warning: {crises_warned}")
    print(f"  True Positive Rate: {true_positive_rate*100:.1f}%")
    print(f"  Average Lead Time: {avg_lead_time:.1f} days")
    print()

    # False positive analysis
    print("Analyzing false positive rate...")
    fp_metrics = calculate_false_positives(df, warning_threshold=0.5)

    print("\n" + "-"*80)
    print("FALSE POSITIVE ANALYSIS")
    print("-"*80)
    print(f"  Total Warnings Issued: {fp_metrics['total_warnings']}")
    print(f"  True Positives: {fp_metrics['true_positives']}")
    print(f"  False Positives: {fp_metrics['false_positives']}")
    print(f"  False Positive Rate: {fp_metrics['false_positive_rate']*100:.1f}%")
    print("-"*80)
    print()

    # Data quality breakdown
    print("\n" + "-"*80)
    print("DATA QUALITY BREAKDOWN")
    print("-"*80)
    quality_counts = df['data_quality'].value_counts()
    for quality, count in quality_counts.items():
        pct = count / len(df) * 100
        print(f"  {quality.capitalize():12s}: {count:4d} points ({pct:5.1f}%)")
    print("-"*80)
    print()

    # Generate LaTeX table for paper
    generate_latex_table(warning_df, true_positive_rate, avg_lead_time)

    # Save summary metrics
    summary = {
        'Metric': [
            'Total Crises Evaluated',
            'Crises with Warning',
            'True Positive Rate',
            'Average Lead Time (days)',
            'Total Warnings Issued',
            'False Positives',
            'False Positive Rate',
        ],
        'Value': [
            total_crises,
            crises_warned,
            f"{true_positive_rate*100:.1f}%",
            f"{avg_lead_time:.1f}",
            fp_metrics['total_warnings'],
            fp_metrics['false_positives'],
            f"{fp_metrics['false_positive_rate']*100:.1f}%",
        ]
    }

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv('tables/validation_summary.csv', index=False)

    print("\nSaved files:")
    print("  - tables/crisis_warnings.csv")
    print("  - tables/validation_summary.csv")
    print("  - tables/validation_latex.txt")
    print()


def generate_latex_table(warning_df, tpr, lead_time):
    """Generate LaTeX table for academic paper."""

    latex = r"""
\begin{table}[h]
\centering
\caption{Crisis Prediction Performance (2004-2024)}
\label{tab:crisis_prediction}
\begin{tabular}{lcccc}
\toprule
\textbf{Crisis Event} & \textbf{Date} & \textbf{Severity} & \textbf{Warning} & \textbf{Lead Time (days)} \\
\midrule
"""

    for _, row in warning_df.iterrows():
        crisis_name = row['crisis'].replace('/', r'\slash ')[:40]  # Truncate long names
        date_str = str(row['start_date'])
        severity = row['severity'].capitalize()
        warning = row['warning_detected']
        lead_time_val = row['lead_time_days'] if row['warning_detected'] == 'Yes' else '-'

        latex += f"{crisis_name} & {date_str} & {severity} & {warning} & {lead_time_val} \\\\\n"

    latex += r"""\midrule
\multicolumn{5}{l}{\textbf{Summary Statistics}} \\
\multicolumn{5}{l}{""" + f"True Positive Rate: {tpr*100:.1f}\\%" + r"""} \\
\multicolumn{5}{l}{""" + f"Average Lead Time: {lead_time:.1f} days" + r"""} \\
\bottomrule
\end{tabular}
\end{table}
"""

    with open('tables/validation_latex.txt', 'w') as f:
        f.write(latex)

    print("\nLaTeX table generated for academic paper.")


def main():
    """Main validation workflow."""
    print("="*80)
    print("MAC FRAMEWORK - VALIDATION METRICS")
    print("="*80)

    df = load_results()
    generate_validation_report(df)

    print("="*80)
    print("VALIDATION ANALYSIS COMPLETE")
    print("="*80)
    print()
    print("Use these metrics in Section 5 (Empirical Validation) of the academic paper.")
    print()


if __name__ == "__main__":
    main()
