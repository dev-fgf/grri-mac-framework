#!/usr/bin/env python
"""
Analyze backtest results and generate figures/tables for academic paper.

This script processes backtest_results.csv and creates:
1. MAC score time series figure (2004-2024)
2. Pillar decomposition during GFC
3. Crisis prediction validation table
4. Summary statistics table
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# Ensure output directories exist
os.makedirs("figures", exist_ok=True)
os.makedirs("tables", exist_ok=True)


def load_results(filename="backtest_results.csv"):
    """Load backtest results."""
    if not os.path.exists(filename):
        print(f"ERROR: {filename} not found!")
        print("Run the backtest first: python run_backtest.py")
        sys.exit(1)

    df = pd.read_csv(filename, index_col='date', parse_dates=True)
    print(f"Loaded {len(df)} data points from {df.index.min().date()} to {df.index.max().date()}")
    return df


def plot_mac_timeseries(df):
    """
    Figure 1: MAC Score Over Time (2004-2024)

    Shows the complete MAC time series with crisis periods highlighted.
    """
    print("\nGenerating Figure 1: MAC Time Series...")

    fig, ax = plt.subplots(figsize=(16, 8))

    # Plot MAC score
    ax.plot(df.index, df['mac_score'], label='MAC Score',
            linewidth=1.5, color='#2E86AB', alpha=0.8)

    # Highlight crisis periods
    crisis_dates = df[df['crisis_event'].notna()]
    if len(crisis_dates) > 0:
        ax.scatter(crisis_dates.index, crisis_dates['mac_score'],
                  color='#A23B72', s=30, label='Crisis Events', zorder=5, alpha=0.7)

    # Add regime threshold lines
    ax.axhline(0.8, color='#06A77D', linestyle='--', alpha=0.4,
              linewidth=2, label='Ample (0.8)')
    ax.axhline(0.5, color='#F18F01', linestyle='--', alpha=0.4,
              linewidth=2, label='Thin (0.5)')
    ax.axhline(0.2, color='#C73E1D', linestyle='--', alpha=0.4,
              linewidth=2, label='Stretched (0.2)')

    # Formatting
    ax.set_title('MAC Score Over Time (2004-2024)',
                fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('MAC Score', fontsize=12)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.8)
    ax.legend(loc='upper right', framealpha=0.95, fontsize=10)

    # Format x-axis
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.YearLocator())

    plt.tight_layout()
    plt.savefig('figures/mac_timeseries.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/mac_timeseries.pdf', bbox_inches='tight')
    print("  Saved: figures/mac_timeseries.png")
    print("  Saved: figures/mac_timeseries.pdf")
    plt.close()


def plot_gfc_pillars(df):
    """
    Figure 2: Pillar Decomposition During Global Financial Crisis

    Shows how individual pillars evolved during 2008-2009.
    """
    print("\nGenerating Figure 2: GFC Pillar Decomposition...")

    # Focus on GFC period
    gfc_period = df.loc['2008-01-01':'2009-12-31']

    if len(gfc_period) == 0:
        print("  WARNING: No GFC data in results. Skipping.")
        return

    fig, ax = plt.subplots(figsize=(14, 7))

    # Define colors for each pillar
    colors = {
        'liquidity': '#E63946',
        'valuation': '#F77F00',
        'positioning': '#FCBF49',
        'volatility': '#06A77D',
        'policy': '#118AB2',
        'contagion': '#073B4C'
    }

    # Plot each pillar
    pillars = ['liquidity', 'valuation', 'positioning', 'volatility', 'policy', 'contagion']
    for pillar in pillars:
        if pillar in gfc_period.columns:
            ax.plot(gfc_period.index, gfc_period[pillar],
                   label=pillar.capitalize(), linewidth=2,
                   color=colors.get(pillar, 'gray'), alpha=0.8)

    # Mark Lehman collapse
    lehman_date = pd.Timestamp('2008-09-15')
    if lehman_date in gfc_period.index or (lehman_date >= gfc_period.index.min() and lehman_date <= gfc_period.index.max()):
        ax.axvline(lehman_date, color='red', linestyle='--',
                  linewidth=2, label='Lehman Collapse', alpha=0.6)

    # Formatting
    ax.set_title('Pillar Decomposition During Global Financial Crisis (2008-2009)',
                fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Pillar Score', fontsize=12)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.8)
    ax.legend(loc='best', framealpha=0.95, fontsize=10, ncol=2)

    # Format x-axis
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig('figures/gfc_pillars.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/gfc_pillars.pdf', bbox_inches='tight')
    print("  Saved: figures/gfc_pillars.png")
    print("  Saved: figures/gfc_pillars.pdf")
    plt.close()


def plot_crisis_comparison(df):
    """
    Figure 3: MAC Scores During Major Crises

    Box plot comparing MAC scores during different crises.
    """
    print("\nGenerating Figure 3: Crisis Comparison...")

    crisis_data = df[df['crisis_event'].notna()].copy()

    if len(crisis_data) == 0:
        print("  WARNING: No crisis data found. Skipping.")
        return

    # Get unique crises
    crises = crisis_data['crisis_event'].unique()

    fig, ax = plt.subplots(figsize=(12, 6))

    # Prepare data for box plot
    crisis_scores = [crisis_data[crisis_data['crisis_event'] == crisis]['mac_score']
                    for crisis in crises]

    # Create box plot
    bp = ax.boxplot(crisis_scores, labels=crises, patch_artist=True)

    # Color boxes
    for patch in bp['boxes']:
        patch.set_facecolor('#2E86AB')
        patch.set_alpha(0.6)

    # Add horizontal reference lines
    ax.axhline(0.8, color='green', linestyle='--', alpha=0.3, label='Ample')
    ax.axhline(0.5, color='orange', linestyle='--', alpha=0.3, label='Thin')
    ax.axhline(0.2, color='red', linestyle='--', alpha=0.3, label='Stretched')

    ax.set_title('MAC Scores During Major Crises', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel('MAC Score', fontsize=12)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3, axis='y')
    plt.xticks(rotation=45, ha='right')
    ax.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig('figures/crisis_comparison.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/crisis_comparison.pdf', bbox_inches='tight')
    print("  Saved: figures/crisis_comparison.png")
    print("  Saved: figures/crisis_comparison.pdf")
    plt.close()


def generate_summary_stats(df):
    """
    Table 1: Summary Statistics

    Overall statistics for the backtest period.
    """
    print("\nGenerating Table 1: Summary Statistics...")

    crisis_dates = df[df['crisis_event'].notna()]
    non_crisis_dates = df[df['crisis_event'].isna()]

    stats = {
        'Metric': [
            'Total Data Points',
            'Date Range',
            'Average MAC Score (Overall)',
            'Average MAC Score (Crisis)',
            'Average MAC Score (Non-Crisis)',
            'Minimum MAC Score',
            'Maximum MAC Score',
            'Std Dev MAC Score',
            'Crisis Points',
            'Non-Crisis Points',
            '% Time in Crisis',
        ],
        'Value': [
            f"{len(df):,}",
            f"{df.index.min().date()} to {df.index.max().date()}",
            f"{df['mac_score'].mean():.3f}",
            f"{crisis_dates['mac_score'].mean():.3f}" if len(crisis_dates) > 0 else "N/A",
            f"{non_crisis_dates['mac_score'].mean():.3f}" if len(non_crisis_dates) > 0 else "N/A",
            f"{df['mac_score'].min():.3f}",
            f"{df['mac_score'].max():.3f}",
            f"{df['mac_score'].std():.3f}",
            f"{len(crisis_dates):,}",
            f"{len(non_crisis_dates):,}",
            f"{len(crisis_dates)/len(df)*100:.1f}%",
        ]
    }

    stats_df = pd.DataFrame(stats)
    stats_df.to_csv('tables/summary_statistics.csv', index=False)

    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(stats_df.to_string(index=False))
    print("="*60)
    print("\n  Saved: tables/summary_statistics.csv")


def generate_crisis_table(df):
    """
    Table 2: Crisis Event Analysis

    MAC scores for each crisis event.
    """
    print("\nGenerating Table 2: Crisis Event Analysis...")

    crisis_data = df[df['crisis_event'].notna()].copy()

    if len(crisis_data) == 0:
        print("  WARNING: No crisis data found.")
        return

    # Group by crisis
    crisis_summary = crisis_data.groupby('crisis_event').agg({
        'mac_score': ['count', 'mean', 'min', 'max', 'std']
    }).round(3)

    crisis_summary.columns = ['Data Points', 'Avg MAC', 'Min MAC', 'Max MAC', 'Std Dev']
    crisis_summary = crisis_summary.reset_index()
    crisis_summary.columns = ['Crisis Event', 'Data Points', 'Avg MAC', 'Min MAC', 'Max MAC', 'Std Dev']

    crisis_summary.to_csv('tables/crisis_analysis.csv', index=False)

    print("\n" + "="*80)
    print("CRISIS EVENT ANALYSIS")
    print("="*80)
    print(crisis_summary.to_string(index=False))
    print("="*80)
    print("\n  Saved: tables/crisis_analysis.csv")


def generate_pillar_stats(df):
    """
    Table 3: Pillar Statistics

    Average scores for each pillar over the full period.
    """
    print("\nGenerating Table 3: Pillar Statistics...")

    pillars = ['liquidity', 'valuation', 'positioning', 'volatility', 'policy', 'contagion']

    pillar_stats = []
    for pillar in pillars:
        if pillar in df.columns:
            pillar_stats.append({
                'Pillar': pillar.capitalize(),
                'Mean': f"{df[pillar].mean():.3f}",
                'Std Dev': f"{df[pillar].std():.3f}",
                'Min': f"{df[pillar].min():.3f}",
                'Max': f"{df[pillar].max():.3f}",
                '% Below 0.2 (Breach)': f"{(df[pillar] < 0.2).sum() / len(df) * 100:.1f}%",
            })

    pillar_df = pd.DataFrame(pillar_stats)
    pillar_df.to_csv('tables/pillar_statistics.csv', index=False)

    print("\n" + "="*80)
    print("PILLAR STATISTICS")
    print("="*80)
    print(pillar_df.to_string(index=False))
    print("="*80)
    print("\n  Saved: tables/pillar_statistics.csv")


def generate_regime_distribution(df):
    """
    Table 4: Regime Distribution

    How much time was spent in each MAC regime.
    """
    print("\nGenerating Table 4: Regime Distribution...")

    # Count points in each regime
    regime_counts = df['interpretation'].value_counts()
    regime_pct = (regime_counts / len(df) * 100).round(1)

    regime_df = pd.DataFrame({
        'Regime': regime_counts.index,
        'Data Points': regime_counts.values,
        'Percentage': regime_pct.values
    })

    # Add expected order
    regime_order = {
        'AMPLE': 0,
        'COMFORTABLE': 1,
        'THIN': 2,
        'STRETCHED': 3,
        'BREACHING': 4
    }
    regime_df['Order'] = regime_df['Regime'].map(regime_order).fillna(5)
    regime_df = regime_df.sort_values('Order').drop('Order', axis=1)

    regime_df.to_csv('tables/regime_distribution.csv', index=False)

    print("\n" + "="*60)
    print("REGIME DISTRIBUTION")
    print("="*60)
    print(regime_df.to_string(index=False))
    print("="*60)
    print("\n  Saved: tables/regime_distribution.csv")


def main():
    """Main analysis workflow."""
    print("="*70)
    print("MAC FRAMEWORK - BACKTEST ANALYSIS")
    print("="*70)
    print()

    # Load results
    df = load_results()

    # Generate figures
    print("\n" + "="*70)
    print("GENERATING FIGURES")
    print("="*70)
    plot_mac_timeseries(df)
    plot_gfc_pillars(df)
    plot_crisis_comparison(df)

    # Generate tables
    print("\n" + "="*70)
    print("GENERATING TABLES")
    print("="*70)
    generate_summary_stats(df)
    generate_crisis_table(df)
    generate_pillar_stats(df)
    generate_regime_distribution(df)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nGenerated Files:")
    print("  Figures:")
    print("    - figures/mac_timeseries.png")
    print("    - figures/gfc_pillars.png")
    print("    - figures/crisis_comparison.png")
    print("  Tables:")
    print("    - tables/summary_statistics.csv")
    print("    - tables/crisis_analysis.csv")
    print("    - tables/pillar_statistics.csv")
    print("    - tables/regime_distribution.csv")
    print()
    print("These outputs are ready for inclusion in the academic paper (Section 5).")
    print()


if __name__ == "__main__":
    main()
