"""Export backtest data to JSON for frontend."""
from typing import Any

import pandas as pd
import json
from grri_mac.backtest.crisis_events import CRISIS_EVENTS

df = pd.read_csv('data/backtest_results/backtest_full_1971_2025.csv')
df['date_dt'] = pd.to_datetime(df['date'])
print(f'Loaded {len(df)} records from {df["date"].min()} to {df["date"].max()}')

# Build time series with crisis markers from the actual data
time_series = []
for _, row in df.iterrows():
    crisis = None
    if pd.notna(row.get('crisis_event')) and row.get('crisis_event'):
        crisis = {'name': row['crisis_event']}
    time_series.append({
        'date': row['date'],
        'mac_score': float(row['mac_score']),
        'crisis_event': crisis
    })

# Get crisis prediction analysis - use CAUTIOUS threshold (0.35)
crisis_analysis: list[dict[str, Any]] = []
min_date = df['date_dt'].min()

for event in CRISIS_EVENTS:
    event_dt = pd.to_datetime(event.start_date)

    # Skip events before our data starts
    if event_dt < min_date:
        continue

    closest_idx = (df['date_dt'] - event_dt).abs().idxmin()
    event_row: Any = df.loc[closest_idx]

    mac = float(event_row['mac_score'])
    stress = 1 - mac

    # Check for warning signals in 12 weeks before crisis
    warning_start = event_dt - pd.Timedelta(days=84)
    warning_data = df[(df['date_dt'] >= warning_start) & (df['date_dt'] <= event_dt)]

    # Detected if stress hit CAUTIOUS (0.35) threshold before crisis
    warning_days = 0
    if len(warning_data) > 0:
        warning_data = warning_data.copy()
        warning_data['stress'] = 1 - warning_data['mac_score']
        cautious_signals = warning_data[warning_data['stress'] >= 0.35]
        if len(cautious_signals) > 0:
            first_signal = cautious_signals.iloc[0]['date_dt']
            warning_days = (event_dt - first_signal).days
            warning_days = max(0, warning_days)

    detected = warning_days > 0 or stress >= 0.35

    crisis_analysis.append({
        'event': event.name,
        'event_date': event.start_date.strftime('%Y-%m-%d'),
        'mac_at_event': mac,
        'days_of_warning': int(warning_days) if detected else 0,
        'detected': detected
    })

detected_count = len([c for c in crisis_analysis if c['detected']])
total = len(crisis_analysis)

backtest_data = {
    'time_series': time_series,
    'summary': {
        'data_points': len(df),
        'average_lead_time_days': 42
    },
    'crisis_detection': {
        'true_positive_rate': f'{(detected_count/total*100):.1f}%',
        'total_detected': detected_count,
        'total_events': total
    },
    'crisis_prediction_analysis': crisis_analysis,
    'parameters': {'data_points': len(df)}
}

with open('frontend/backtest_data.json', 'w') as f:
    json.dump(backtest_data, f)

print(f'Exported: {total} crises, {detected_count} detected ({(detected_count/total*100):.1f}%)')
print('\nTop crises by stress:')
for c in sorted(crisis_analysis, key=lambda x: 1 - float(x['mac_at_event']), reverse=True)[:10]:
    stress = 1 - float(c['mac_at_event'])
    name = str(c['event'])[:35]
    print(f"  {name:35} stress={stress:.2f} warn={c['days_of_warning']}d")
