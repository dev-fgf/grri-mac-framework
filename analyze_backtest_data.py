"""Analyze backtest results for paper update."""
import pandas as pd

df = pd.read_csv('backtest_results_7pillar.csv')

print("=" * 60)
print("BACKTEST DATA ANALYSIS FOR PAPER UPDATE")
print("=" * 60)

# Overall stats
print(f"\nTotal data points: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Mean MAC: {df['mac_score'].mean():.3f}")
print(f"Min MAC: {df['mac_score'].min():.3f}")
print(f"Max MAC: {df['mac_score'].max():.3f}")

# Crisis analysis
print("\n" + "=" * 60)
print("CRISIS EVENT ANALYSIS")
print("=" * 60)
crises = df[df['crisis_event'].notna() & (df['crisis_event'] != '')]
for name in crises['crisis_event'].unique():
    c = crises[crises['crisis_event'] == name]
    print(f"\n{name}:")
    print(f"  Points: {len(c)}")
    print(f"  MAC: mean={c['mac_score'].mean():.3f}, min={c['mac_score'].min():.3f}")
    print(f"  Private Credit: {c['private_credit'].mean():.2f}")
    print(f"  Positioning: {c['positioning'].mean():.2f}")
    print(f"  Liquidity: {c['liquidity'].mean():.2f}")
    print(f"  Volatility: {c['volatility'].mean():.2f}")
    print(f"  Deteriorating: {c['is_deteriorating'].sum()}")

# Regime distribution
print("\n" + "=" * 60)
print("REGIME DISTRIBUTION")
print("=" * 60)
print(df['mac_status'].value_counts())
print(f"\nPercentages:")
for status in df['mac_status'].unique():
    pct = len(df[df['mac_status'] == status]) / len(df) * 100
    print(f"  {status}: {pct:.1f}%")

# Deteriorating analysis
print("\n" + "=" * 60)
print("DETERIORATING PERIODS")
print("=" * 60)
det = df[df['is_deteriorating'] == True]
print(f"Total deteriorating periods: {len(det)}")

# Lead time analysis
print("\n" + "=" * 60)
print("LEAD TIME ANALYSIS")
print("=" * 60)
crisis_names = ['COVID-19 Pandemic', 'UK Pension Crisis / Rate Shock', 'SVB / Regional Banking Crisis']
for crisis_name in crisis_names:
    crisis_rows = df[df['crisis_event'] == crisis_name]
    if len(crisis_rows) > 0:
        first_crisis_idx = crisis_rows.index[0]
        # Look back for deteriorating signals
        lookback = df.iloc[max(0, first_crisis_idx - 12):first_crisis_idx]
        det_signals = lookback[lookback['is_deteriorating'] == True]
        if len(det_signals) > 0:
            first_det_date = det_signals.iloc[0]['date']
            crisis_date = crisis_rows.iloc[0]['date']
            print(f"{crisis_name}:")
            print(f"  First DETERIORATING: {first_det_date}")
            print(f"  Crisis start: {crisis_date}")
        else:
            print(f"{crisis_name}: No DETERIORATING in 12 weeks prior")

# Non-crisis vs crisis MAC
print("\n" + "=" * 60)
print("CRISIS VS NON-CRISIS")
print("=" * 60)
non_crisis = df[~(df['crisis_event'].notna() & (df['crisis_event'] != ''))]
print(f"Non-crisis average MAC: {non_crisis['mac_score'].mean():.3f}")
print(f"Crisis average MAC: {crises['mac_score'].mean():.3f}")

# Table 3 data - for paper
print("\n" + "=" * 60)
print("TABLE 3 DATA (Crisis Results)")
print("=" * 60)
print("| Crisis | MAC | Liquidity | Valuation | Position | Vol | Policy | Contagion | Private Credit | Breaches |")
print("|--------|-----|-----------|-----------|----------|-----|--------|-----------|----------------|----------|")
for name in crises['crisis_event'].unique():
    c = crises[crises['crisis_event'] == name]
    mac = c['mac_score'].mean()
    liq = c['liquidity'].mean()
    val = c['valuation'].mean()
    pos = c['positioning'].mean()
    vol = c['volatility'].mean()
    pol = c['policy'].mean()
    con = c['contagion'].mean()
    pc = c['private_credit'].mean()
    
    # Determine breaches (pillar < 0.40)
    breaches = []
    if liq < 0.40: breaches.append('liq')
    if val < 0.40: breaches.append('val')
    if pos < 0.40: breaches.append('pos')
    if vol < 0.40: breaches.append('vol')
    if pol < 0.40: breaches.append('pol')
    if con < 0.40: breaches.append('con')
    if pc < 0.40: breaches.append('pc')
    breach_str = ', '.join(breaches) if breaches else 'none'
    
    print(f"| {name[:20]} | {mac:.3f} | {liq:.2f} | {val:.2f} | {pos:.2f} | {vol:.2f} | {pol:.2f} | {con:.2f} | {pc:.2f} | {breach_str} |")
