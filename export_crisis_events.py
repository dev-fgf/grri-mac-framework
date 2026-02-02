"""Export crisis events to JSON for frontend visualization."""

import json
from grri_mac.backtest.crisis_events import CRISIS_EVENTS

def export_crisis_events():
    """Export crisis events from 1971+ for frontend chart overlay."""
    events = []
    
    for event in CRISIS_EVENTS:
        # Only include events within backtest range (1971+)
        if event.start_date.year >= 1971:
            events.append({
                'name': event.name,
                'start_date': event.start_date.strftime('%Y-%m-%d'),
                'end_date': event.end_date.strftime('%Y-%m-%d'),
                'severity': event.severity,
                'description': event.description,
                'expected_mac_range': list(event.expected_mac_range),
                'affected_countries': event.affected_countries[:3],  # First 3
            })
    
    # Sort by date
    events.sort(key=lambda x: x['start_date'])
    
    output = {
        'events': events,
        'total': len(events),
        'severity_counts': {
            'extreme': len([e for e in events if e['severity'] == 'extreme']),
            'high': len([e for e in events if e['severity'] == 'high']),
            'moderate': len([e for e in events if e['severity'] == 'moderate']),
        }
    }
    
    with open('frontend/crisis_events.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Exported {len(events)} crisis events (1971-2025)")
    print(f"  - Extreme: {output['severity_counts']['extreme']}")
    print(f"  - High: {output['severity_counts']['high']}")
    print(f"  - Moderate: {output['severity_counts']['moderate']}")
    print()
    print("Sample events:")
    for e in events[:5]:
        print(f"  {e['start_date']}: {e['name']} ({e['severity']})")
    print("  ...")
    for e in events[-3:]:
        print(f"  {e['start_date']}: {e['name']} ({e['severity']})")


if __name__ == "__main__":
    export_crisis_events()
