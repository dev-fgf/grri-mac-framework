"""Calculate empirically-calibrated thresholds from backtest data."""
import pandas as pd  # type: ignore[import-untyped]

df = pd.read_csv('data/backtest_results/backtest_full_1971_2025.csv')
df['stress'] = 1 - df['mac_score']

# Target: ~45% comfortable, ~30% cautious, ~18% stretched, ~7% critical
p45 = df['stress'].quantile(0.45)
p75 = df['stress'].quantile(0.75)
p93 = df['stress'].quantile(0.93)

print('Empirically-Calibrated Thresholds:')
print('=' * 50)
print(f'Comfortable: 0.00 - {p45:.2f}  (bottom 45%)')
print(f'Cautious:    {p45:.2f} - {p75:.2f}  (45th-75th percentile)')
print(f'Stretched:   {p75:.2f} - {p93:.2f}  (75th-93rd percentile)')
print(f'Critical:    {p93:.2f}+        (top 7%)')
print()

# Verify distribution with new thresholds
comfortable = (df['stress'] < p45).mean() * 100
cautious = ((df['stress'] >= p45) & (df['stress'] < p75)).mean() * 100
stretched = ((df['stress'] >= p75) & (df['stress'] < p93)).mean() * 100
critical = (df['stress'] >= p93).mean() * 100

print('New Distribution:')
print(f'  Comfortable: {comfortable:.1f}%')
print(f'  Cautious:    {cautious:.1f}%')
print(f'  Stretched:   {stretched:.1f}%')
print(f'  Critical:    {critical:.1f}%')
