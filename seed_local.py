"""Run this locally to seed historical MAC data into Azure Table Storage."""

import os
import sys
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

# Verify env vars loaded
conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
print(f"Connection string loaded: {'Yes' if conn_str else 'No'}")
if conn_str:
    print(f"  Account: {conn_str.split(';')[1] if ';' in conn_str else 'unknown'}")

# Check if azure-data-tables is installed
try:
    print("azure-data-tables: installed")
except ImportError:
    print("azure-data-tables: NOT INSTALLED")
    print("Run: python -m pip install azure-data-tables")
    sys.exit(1)

# Add api folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database


def main():
    days = 730  # 2 years

    client = FREDClient()
    db = get_database()

    print(f"FRED API Key: {'set' if client.api_key else 'NOT SET'}")
    print(f"DB connected: {db.connected}")

    if not client.api_key:
        print("ERROR: FRED_API_KEY not set in .env")
        return

    if not db.connected:
        print("ERROR: AZURE_STORAGE_CONNECTION_STRING not set or invalid")
        return

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    print(f"Fetching FRED data from {start_date.date()} to {end_date.date()}...")
    bulk_data = client.get_all_bulk_series(start_date, end_date)

    if not bulk_data:
        print("ERROR: Failed to fetch FRED data")
        return

    print(f"Processing {days} days of data...")
    saved = 0
    skipped = 0

    for i in range(days, -1, -1):
        current_date = end_date - timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')

        indicators = client.calculate_indicators_from_bulk(bulk_data, date_str)

        if indicators and len(indicators) >= 3:
            mac_result = calculate_mac(indicators)
            pillars = mac_result.get('pillar_scores', {})

            entity = {
                'PartitionKey': date_str,
                'RowKey': current_date.strftime('%H%M%S') + '_' + str(uuid.uuid4())[:8],
                'timestamp': current_date.isoformat(),
                'mac_score': round(mac_result.get('mac_score', 0), 4),
                'liquidity_score': round(pillars.get('liquidity', {}).get('score', 0), 4),
                'valuation_score': round(pillars.get('valuation', {}).get('score', 0), 4),
                'positioning_score': round(pillars.get('positioning', {}).get('score', 0), 4),
                'volatility_score': round(pillars.get('volatility', {}).get('score', 0), 4),
                'policy_score': round(pillars.get('policy', {}).get('score', 0), 4),
                'is_live': False,
            }

            db._table_client.upsert_entity(entity)
            saved += 1

            if saved % 50 == 0:
                print(f"  Saved {saved} records... (current: {date_str})")
        else:
            skipped += 1

    print(f"\nDone! Saved {saved} records, skipped {skipped} (no data)")


if __name__ == "__main__":
    main()
