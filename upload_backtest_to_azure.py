"""Upload local backtest_results.csv to Azure Table Storage cache."""

import csv
import json
import os
import sys
from datetime import datetime, timedelta

# Add the api/shared path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api', 'shared'))

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError

# Crisis events for annotation
CRISIS_EVENTS = {
    "2007-08-09": {"name": "BNP Paribas", "description": "Subprime contagion begins"},
    "2008-03-16": {"name": "Bear Stearns", "description": "Bear Stearns collapse/rescue"},
    "2008-09-15": {"name": "Lehman Brothers", "description": "Lehman bankruptcy, GFC peak"},
    "2010-05-06": {"name": "Flash Crash", "description": "Dow drops 1000 pts intraday"},
    "2011-08-08": {"name": "US Downgrade", "description": "S&P downgrades US debt"},
    "2015-08-24": {"name": "China Deval", "description": "Yuan devaluation, EM selloff"},
    "2018-12-24": {"name": "Fed Pivot", "description": "Q4 2018 selloff, Powell pivot"},
    "2020-03-16": {"name": "COVID-19 Peak", "description": "Pandemic selloff, VIX 82"},
    "2022-09-30": {"name": "2022 Rate Shock", "description": "Fed hikes, UK pension crisis"},
    "2023-03-10": {"name": "SVB Crisis", "description": "Regional banking stress"},
    "2024-08-05": {"name": "Yen Carry Unwind", "description": "BoJ rate hike"},
    "2025-04-07": {"name": "April 2025 Tariff", "description": "Trade war escalation"},
}


def get_status(mac_score: float) -> str:
    if mac_score >= 0.65:
        return "COMFORTABLE"
    elif mac_score >= 0.50:
        return "CAUTIOUS"
    elif mac_score >= 0.35:
        return "STRETCHED"
    else:
        return "CRITICAL"


def add_crisis_events(time_series: list) -> list:
    """Add crisis event annotations to time series data."""
    for point in time_series:
        point_date = datetime.strptime(point["date"], "%Y-%m-%d")
        for event_date, event_info in CRISIS_EVENTS.items():
            event_dt = datetime.strptime(event_date, "%Y-%m-%d")
            if abs((point_date - event_dt).days) <= 3:
                point["crisis_event"] = {
                    "name": event_info["name"],
                    "description": event_info["description"],
                    "event_date": event_date
                }
                break
    return time_series


def calculate_crisis_analysis(time_series: list, start_date, end_date) -> list:
    """Calculate crisis prediction analysis."""
    crisis_analysis = []

    for event_date, event_info in CRISIS_EVENTS.items():
        event_dt = datetime.strptime(event_date, "%Y-%m-%d")
        if event_dt < start_date or event_dt > end_date:
            continue

        pre_event_points = [
            p for p in time_series
            if datetime.strptime(p["date"], "%Y-%m-%d") <= event_dt
            and datetime.strptime(p["date"], "%Y-%m-%d") >= event_dt - timedelta(days=90)
        ]

        if pre_event_points:
            first_warning = None
            first_stretched = None
            for p in pre_event_points:
                if p["status"] != "COMFORTABLE" and first_warning is None:
                    first_warning = p
                if p["status"] in ["STRETCHED", "CRITICAL"] and first_stretched is None:
                    first_stretched = p

            event_point = pre_event_points[-1] if pre_event_points else None

            crisis_analysis.append({
                "event": event_info["name"],
                "event_date": event_date,
                "mac_at_event": event_point["mac_score"] if event_point else None,
                "status_at_event": event_point["status"] if event_point else None,
                "first_warning_date": first_warning["date"] if first_warning else None,
                "days_of_warning": (
                    event_dt - datetime.strptime(first_warning["date"], "%Y-%m-%d")
                ).days if first_warning else 0,
                "first_stretched_date": first_stretched["date"] if first_stretched else None,
                "days_stretched": (
                    event_dt - datetime.strptime(first_stretched["date"], "%Y-%m-%d")
                ).days if first_stretched else 0,
            })

    return crisis_analysis


def main():
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("ERROR: AZURE_STORAGE_CONNECTION_STRING not set")
        return
    
    # Read CSV
    csv_path = os.path.join(os.path.dirname(__file__), "backtest_results.csv")
    
    time_series = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mac_score = float(row['mac_score'])
            point = {
                "date": row['date'],
                "mac_score": round(mac_score, 4),
                "status": get_status(mac_score),
                "multiplier": 1.0 + (1 - mac_score),  # Simple multiplier calc
                "pillar_scores": {
                    "liquidity": round(float(row.get('liquidity', 0.5)), 4),
                    "valuation": round(float(row.get('valuation', 0.5)), 4),
                    "positioning": round(float(row.get('positioning', 0.5)), 4),
                    "volatility": round(float(row.get('volatility', 0.5)), 4),
                    "policy": round(float(row.get('policy', 0.5)), 4),
                    "contagion": round(float(row.get('contagion', 0.5)), 4),
                },
                "breach_flags": [],
                "indicators": {},
            }
            time_series.append(point)
    
    print(f"Loaded {len(time_series)} data points from CSV")
    
    # Sort by date
    time_series.sort(key=lambda x: x["date"])
    
    # Add crisis annotations
    time_series = add_crisis_events(time_series)
    
    # Get date range
    start_date = datetime.strptime(time_series[0]["date"], "%Y-%m-%d")
    end_date = datetime.strptime(time_series[-1]["date"], "%Y-%m-%d")
    
    # Calculate statistics
    mac_scores = [p["mac_score"] for p in time_series]
    crisis_analysis = calculate_crisis_analysis(time_series, start_date, end_date)
    
    # Calculate prediction metrics
    total_crises = len(crisis_analysis)
    crises_with_warning = sum(1 for c in crisis_analysis if c["days_of_warning"] > 0)
    crises_stretched = sum(1 for c in crisis_analysis if c["days_stretched"] > 0)
    
    avg_lead_time = sum(c["days_of_warning"] for c in crisis_analysis) / total_crises if total_crises > 0 else 0
    avg_days_stretched = sum(c["days_stretched"] for c in crisis_analysis) / total_crises if total_crises > 0 else 0
    warning_rate = (crises_with_warning / total_crises * 100) if total_crises > 0 else 0
    prediction_accuracy = (crises_stretched / total_crises * 100) if total_crises > 0 else 0
    
    print(f"Crisis analysis: {total_crises} events, {prediction_accuracy:.0f}% prediction accuracy")
    
    # Build the full response
    response = {
        "data_source": "Pre-computed (local upload)",
        "computed_at": datetime.utcnow().isoformat(),
        "parameters": {
            "start_date": time_series[0]["date"],
            "end_date": time_series[-1]["date"],
            "interval_days": 7,
            "data_points": len(time_series)
        },
        "summary": {
            "data_points": len(time_series),
            "average_lead_time_days": round(avg_lead_time, 1),
            "average_days_stretched_before_event": round(avg_days_stretched, 1),
            "warning_rate": f"{warning_rate:.0f}%",
            "prediction_accuracy": f"{prediction_accuracy:.0f}%",
            "min_mac": round(min(mac_scores), 4),
            "max_mac": round(max(mac_scores), 4),
            "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
            "current_mac": time_series[-1]["mac_score"] if time_series else None,
            "current_status": time_series[-1]["status"] if time_series else None,
            "periods_in_comfortable": sum(1 for p in time_series if p["status"] == "COMFORTABLE"),
            "periods_in_cautious": sum(1 for p in time_series if p["status"] == "CAUTIOUS"),
            "periods_in_stretched": sum(1 for p in time_series if p["status"] == "STRETCHED"),
            "periods_in_critical": sum(1 for p in time_series if p["status"] == "CRITICAL"),
        },
        "crisis_prediction_analysis": crisis_analysis,
        "time_series": time_series,
        "crisis_events": CRISIS_EVENTS,
        "interpretation_guide": {
            "status_levels": {
                "COMFORTABLE": "MAC > 0.65 - Markets can absorb shocks",
                "CAUTIOUS": "MAC 0.50-0.65 - Elevated vigilance recommended",
                "STRETCHED": "MAC 0.35-0.50 - Reduced shock absorption capacity",
                "CRITICAL": "MAC < 0.35 - High vulnerability to cascading selloffs"
            }
        }
    }
    
    # Connect to Azure Table Storage
    print("Connecting to Azure Table Storage...")
    service = TableServiceClient.from_connection_string(conn_str)
    
    table_name = "backtestcache"
    try:
        service.create_table(table_name)
        print(f"Created table: {table_name}")
    except ResourceExistsError:
        print(f"Table {table_name} already exists")
    
    table = service.get_table_client(table_name)
    
    # Azure Table has 64KB limit per property, so we need to split the data
    # Store summary separately, and time_series in chunks
    now = datetime.now()
    
    # 1. Store summary and metadata (without time_series)
    summary_response = {
        "data_source": response["data_source"],
        "computed_at": response["computed_at"],
        "parameters": response["parameters"],
        "summary": response["summary"],
        "crisis_prediction_analysis": response["crisis_prediction_analysis"],
        "crisis_events": response["crisis_events"],
        "interpretation_guide": response["interpretation_guide"],
    }
    
    summary_entity = {
        "PartitionKey": "CACHE",
        "RowKey": "summary",
        "timestamp": now.isoformat(),
        "updated_at": now.isoformat(),
        "response_json": json.dumps(summary_response),
        "data_points": len(time_series),
        "start_date": time_series[0]["date"],
        "end_date": time_series[-1]["date"],
    }
    
    table.upsert_entity(summary_entity, mode="replace")
    print(f"✓ Uploaded summary")
    
    # 2. Store time_series in chunks (100 points per chunk to stay under 64KB)
    chunk_size = 100
    chunks = [time_series[i:i+chunk_size] for i in range(0, len(time_series), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        chunk_entity = {
            "PartitionKey": "TIMESERIES",
            "RowKey": f"chunk_{i:04d}",
            "timestamp": now.isoformat(),
            "chunk_index": i,
            "chunk_count": len(chunks),
            "points_in_chunk": len(chunk),
            "start_date": chunk[0]["date"],
            "end_date": chunk[-1]["date"],
            "data_json": json.dumps(chunk),
        }
        table.upsert_entity(chunk_entity, mode="replace")
    
    print(f"✓ Uploaded {len(chunks)} time series chunks ({len(time_series)} total points)")
    
    # 3. Store a "default" pointer that has chunk count info
    default_entity = {
        "PartitionKey": "CACHE",
        "RowKey": "default",
        "timestamp": now.isoformat(),
        "updated_at": now.isoformat(),
        "data_points": len(time_series),
        "chunk_count": len(chunks),
        "start_date": time_series[0]["date"],
        "end_date": time_series[-1]["date"],
        "prediction_accuracy": f"{prediction_accuracy:.0f}%",
        "crises_analyzed": total_crises,
    }
    table.upsert_entity(default_entity, mode="replace")
    
    print(f"✓ Uploaded backtest cache")
    print(f"  Date range: {time_series[0]['date']} to {time_series[-1]['date']}")
    print(f"  Prediction accuracy: {prediction_accuracy:.0f}%")
    print(f"  Crises analyzed: {total_crises}")


if __name__ == "__main__":
    main()
