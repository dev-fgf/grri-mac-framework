"""
Weekly timer-triggered function to keep MAC data current.

Runs every Monday at 06:00 UTC:
  1. Fetches latest FRED + CFTC indicators → saves to indicator cache
  2. Scores all 7 MAC pillars using the real calculate_mac() scorer
  3. Appends the new weekly data point to the backtest cache

Cost on Azure Consumption plan:
  - 1 invocation/week × ~3s execution × 128MB = essentially free
  - Well under the 1M free executions/month
"""

import json
import sys
import os
import logging
from datetime import datetime, timedelta
import azure.functions as func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database

logger = logging.getLogger(__name__)


def main(timer: func.TimerRequest) -> None:
    """Weekly timer: refresh data → score MAC → append to cache."""
    start = datetime.utcnow()
    logger.info("Weekly MAC update triggered at %s", start.isoformat())

    db = get_database()
    if not db.connected:
        logger.error("Database not connected — skipping update")
        return

    # ─── Step 1: Fetch fresh indicators from FRED ───
    try:
        client = FREDClient()
        indicators = client.get_all_indicators()
        if indicators:
            db.save_indicators(indicators, source="FRED")
            logger.info("Refreshed %d FRED indicators", len(indicators))

            # Also update the FRED series cache (last 30 days)
            _update_fred_series(client, db)
        else:
            logger.warning("FRED returned no data — using cached indicators")
            indicators = db.get_cached_indicators() or {}
    except Exception as e:
        logger.error("FRED fetch failed: %s — falling back to cache", e)
        indicators = db.get_cached_indicators() or {}

    if not indicators:
        logger.error("No indicators available — cannot compute MAC")
        return

    # ─── Step 2: Score all 7 pillars using the real scorer ───
    try:
        mac_result = calculate_mac(indicators)
    except Exception as e:
        logger.error("MAC scoring failed: %s", e)
        return

    mac_score = mac_result["mac_score"]
    pillar_scores = {
        name: data["score"]
        for name, data in mac_result["pillar_scores"].items()
    }

    # ─── Step 3: Append to backtest cache ───
    try:
        existing = db.get_backtest_cache_chunked()
        if not existing or "time_series" not in existing:
            logger.error("No existing backtest cache — run upload script first")
            return

        # Align to nearest Thursday for weekly consistency
        today = datetime.utcnow()
        days_since_thursday = (today.weekday() - 3) % 7
        aligned = today - timedelta(days=days_since_thursday)
        date_str = aligned.strftime("%Y-%m-%d")

        # Determine status
        if mac_score >= 0.65:
            status = "COMFORTABLE"
        elif mac_score >= 0.50:
            status = "CAUTIOUS"
        elif mac_score >= 0.35:
            status = "STRETCHED"
        else:
            status = "CRITICAL"

        new_point = {
            "date": date_str,
            "mac_score": round(mac_score, 4),
            "status": status,
            "pillar_scores": {k: round(v, 4) for k, v in pillar_scores.items()},
            "breach_flags": mac_result.get("breach_flags", []),
            "data_source": "weekly_timer",
        }

        # Merge
        series = existing["time_series"]
        merged = {p["date"]: p for p in series}
        merged[date_str] = new_point
        merged_list = sorted(merged.values(), key=lambda x: x["date"])

        # Rebuild cache envelope
        mac_scores = [p["mac_score"] for p in merged_list]
        updated_cache = {
            "parameters": {
                "start_date": merged_list[0]["date"],
                "end_date": merged_list[-1]["date"],
                "interval_days": 7,
            },
            "summary": {
                "data_points": len(merged_list),
                "min_mac": round(min(mac_scores), 4),
                "max_mac": round(max(mac_scores), 4),
                "avg_mac": round(sum(mac_scores) / len(mac_scores), 4),
            },
            "time_series": merged_list,
        }

        db.save_backtest_cache_chunked(updated_cache)

        # Also save to backtesthistory for individual record queries
        record = {
            "date": date_str,
            "mac_score": new_point["mac_score"],
            "mac_status": status,
            **pillar_scores,
        }
        db.save_backtest_results_batch([record])

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "Weekly update complete: %s MAC=%.3f (%s), total=%d pts, %.1fs",
            date_str, mac_score, status, len(merged_list), elapsed
        )

    except Exception as e:
        logger.exception("Failed to append to backtest cache: %s", e)


# FRED series to keep incrementally updated
FRED_SERIES_TO_UPDATE = [
    "VIXCLS", "DGS10", "DGS2", "DTB3", "DFF", "SOFR", "IORB",
    "BAMLC0A0CM", "BAMLH0A0HYM2", "AAA", "BAA",
]


def _update_fred_series(client: FREDClient, db) -> int:
    """Append last 30 days of FRED data to cached series."""
    updated = 0
    end = datetime.utcnow()
    start = end - timedelta(days=30)

    for sid in FRED_SERIES_TO_UPDATE:
        try:
            existing = db.get_fred_series(sid)
            obs = client.get_series(sid, start_date=start, end_date=end, limit=100)
            if not obs:
                continue

            new_dates = []
            new_values = []
            for o in obs:
                if o.get("value") and o["value"] != ".":
                    new_dates.append(o["date"])
                    try:
                        new_values.append(float(o["value"]))
                    except ValueError:
                        continue

            if not new_dates:
                continue

            if existing:
                all_dates = existing.get("dates", []) + new_dates
                all_values = existing.get("values", []) + new_values
                seen = set()
                merged_d, merged_v = [], []
                for d, v in zip(all_dates, all_values):
                    if d not in seen:
                        seen.add(d)
                        merged_d.append(d)
                        merged_v.append(v)
                pairs = sorted(zip(merged_d, merged_v))
                merged_d = [p[0] for p in pairs]
                merged_v = [p[1] for p in pairs]
            else:
                merged_d, merged_v = new_dates, new_values

            if db.save_fred_series(sid, {"dates": merged_d, "values": merged_v}):
                updated += 1
        except Exception:
            continue

    logger.info("Updated %d/%d FRED series", updated, len(FRED_SERIES_TO_UPDATE))
    return updated
