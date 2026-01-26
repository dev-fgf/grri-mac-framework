# Backtest Analysis Guide

This guide explains how to analyze the backtest results and generate all figures/tables for the academic paper.

## Prerequisites

1. Completed backtest with `backtest_results.csv` file
2. Python packages: pandas, matplotlib, scipy, numpy

```bash
pip install pandas matplotlib scipy numpy
```

## Quick Start: Run All Analysis

The simplest approach is to run everything at once:

```bash
python run_all_analysis.py
```

This will generate all figures and tables needed for Section 5 of the academic paper.

## Individual Analysis Scripts

You can also run each analysis separately:

### 1. Basic Analysis and Figures

```bash
python analyze_backtest_results.py
```

**Generates:**
- `figures/mac_timeseries.png` - MAC score over 20 years with crisis annotations
- `figures/gfc_pillars.png` - Pillar decomposition during 2008-2009 GFC
- `figures/crisis_comparison.png` - Box plots of MAC scores during different crises
- `tables/summary_statistics.csv` - Overall backtest statistics
- `tables/crisis_analysis.csv` - Per-crisis MAC score breakdown
- `tables/pillar_statistics.csv` - Statistics for each pillar
- `tables/regime_distribution.csv` - Time spent in each MAC regime

**Use in paper:** Section 5.2 (Results) - Figures 1-3, Tables 1-4

### 2. Validation Metrics

```bash
python generate_validation_metrics.py
```

**Generates:**
- `tables/crisis_warnings.csv` - Crisis-by-crisis warning analysis
- `tables/validation_summary.csv` - True positive rate, false positive rate, lead time
- `tables/validation_latex.txt` - LaTeX table ready for copy/paste into paper

**Use in paper:** Section 5.2 (Results) - Table 5, discussion of predictive performance

**Key Metrics:**
- **True Positive Rate**: % of crises correctly predicted with warning
- **Lead Time**: Average days of warning before crisis onset
- **False Positive Rate**: % of warnings not followed by crisis within 90 days

### 3. Comparison to Alternatives

```bash
python compare_to_alternatives.py
```

**Generates:**
- `figures/mac_vs_vix.png` - MAC compared to VIX (volatility-only approach)
- `figures/mac_vs_credit.png` - MAC compared to credit spreads
- `figures/pillar_correlation.png` - Correlation matrix showing pillars capture different dimensions
- `tables/pillar_correlation.csv` - Correlation coefficients
- `tables/incremental_value.csv` - Separation power of MAC vs individual indicators

**Use in paper:** Section 5.4 (Comparison to Alternative Indices) - Figures 4-6, Tables 7-8

**Shows:**
- MAC provides information beyond any single indicator
- Pillars have low correlation (capturing independent dimensions)
- MAC has better crisis/non-crisis separation than individual components

## Checking Backtest Progress

While the backtest is running:

```bash
python check_backtest_progress.py
```

Shows how many data points have been processed.

## Output Structure

After running all analysis, your directory will look like:

```
grri-mac-framework/
├── backtest_results.csv          # Raw backtest output
├── figures/                      # All figures for paper
│   ├── mac_timeseries.png
│   ├── mac_timeseries.pdf
│   ├── gfc_pillars.png
│   ├── gfc_pillars.pdf
│   ├── crisis_comparison.png
│   ├── crisis_comparison.pdf
│   ├── mac_vs_vix.png
│   ├── mac_vs_credit.png
│   └── pillar_correlation.png
└── tables/                       # All tables for paper
    ├── summary_statistics.csv
    ├── crisis_analysis.csv
    ├── pillar_statistics.csv
    ├── regime_distribution.csv
    ├── crisis_warnings.csv
    ├── validation_summary.csv
    ├── validation_latex.txt      # Ready for paper
    ├── pillar_correlation.csv
    └── incremental_value.csv
```

## Using Outputs in Academic Paper

### Section 5.1: Data and Methodology

Include:
- Backtest period (from `summary_statistics.csv`)
- Data quality breakdown
- Number of crisis events evaluated

### Section 5.2: Results

Include:
- **Figure 1**: MAC time series (`mac_timeseries.png`)
- **Figure 2**: GFC pillar decomposition (`gfc_pillars.png`)
- **Figure 3**: Crisis comparison (`crisis_comparison.png`)
- **Table 1**: Summary statistics (`summary_statistics.csv`)
- **Table 2**: Crisis-by-crisis analysis (`crisis_analysis.csv`)
- **Table 5**: Crisis warnings (copy from `validation_latex.txt`)

**Key findings to discuss:**
```
The MAC framework correctly identified X of Y crises (Z% true positive rate)
with an average lead time of N days. During crisis periods, the average
MAC score was 0.XXX compared to 0.XXX during non-crisis periods, representing
a statistically significant separation.
```

### Section 5.3: Crisis Case Studies

Use data from `crisis_analysis.csv` to discuss:
- 2008 GFC: Minimum MAC score, pillar breakdown
- 2020 COVID-19: Speed of deterioration, recovery pattern
- 2023 SVB Crisis: Regional vs systemic stress differentiation

### Section 5.4: Comparison to Alternative Indices

Include:
- **Figure 4**: MAC vs VIX (`mac_vs_vix.png`)
- **Figure 5**: MAC vs credit spreads (`mac_vs_credit.png`)
- **Figure 6**: Pillar correlation matrix (`pillar_correlation.png`)
- **Table 7**: Pillar correlations (`pillar_correlation.csv`)
- **Table 8**: Incremental value analysis (`incremental_value.csv`)

**Key findings:**
```
The low inter-pillar correlations (average 0.XX) demonstrate that each pillar
captures independent dimensions of market stress. The MAC composite shows
superior crisis/non-crisis separation (0.XXX) compared to individual
indicators (VIX: 0.XXX, Credit spreads: 0.XXX).
```

### Section 5.5: Discussion

Discuss:
- False positive rate and practical implications
- Data quality differences across time periods
- Limitations (placeholder pillars, synthetic positioning data)
- Future enhancements (real CFTC data, BIS cross-border flows)

## Customizing Analysis

### Change Warning Threshold

Edit `generate_validation_metrics.py`:

```python
# Line ~50
warning_threshold = 0.5  # Change to 0.4, 0.6, etc.
```

### Change Warning Window

```python
# Line ~50
warning_window_days = 90  # Change to 60, 120, etc.
```

### Add Custom Crisis Events

Edit `grri_mac/backtest/crisis_events.py` to add events, then re-run analysis.

### Change Figure Styling

Edit the plot functions in `analyze_backtest_results.py`:
- Color schemes
- Figure sizes
- Font sizes
- Grid styles

## Troubleshooting

### "backtest_results.csv not found"

Run the backtest first:
```bash
python run_backtest.py --start 2004-01-01 --end 2024-12-31 --frequency weekly
```

### "No module named 'matplotlib'"

Install required packages:
```bash
pip install pandas matplotlib scipy numpy
```

### Figures look wrong

- Check that `backtest_results.csv` has expected columns
- Verify date range covers crisis periods
- Check for NaN values in pillar columns

### LaTeX table formatting issues

Edit `generate_validation_metrics.py` line ~200+ to adjust table format.

## Performance Notes

- Analysis scripts run quickly (~10-30 seconds total)
- Figure generation is the slowest part (~5-10 seconds per figure)
- All scripts can be run multiple times without issues

## Next Steps

After generating all outputs:

1. **Review figures visually** - Ensure they look publication-ready
2. **Check tables** - Verify numbers make sense
3. **Copy to paper directory** - Move figures to `docs/figures/`
4. **Write Section 5** - Use metrics to complete empirical validation
5. **Create LaTeX tables** - Use `validation_latex.txt` as starting point
6. **Proofread** - Ensure paper text matches table/figure values

## Citation

When using these results in publications, cite:

```bibtex
@article{grri_mac_2026,
  title={A Six-Pillar Framework for Measuring Market Absorption Capacity:
         Theory, Methodology, and International Application},
  author={[Your Name]},
  journal={Working Paper},
  year={2026}
}
```
