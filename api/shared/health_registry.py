"""Data source health monitoring registry.

Validates external data source responses against expected schemas and
value ranges. Detects format changes, missing indicators, and staleness
before they silently degrade the dashboard.

Health state is persisted to Azure Table Storage (or in-memory fallback)
and surfaced via /api/health and the frontend admin banner.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# === Source Specifications ===
# Each source declares what it should return and plausible value bounds.
# Ranges are deliberately wide — these are plausibility checks, not
# market-level alerts. A value outside range means the parser is likely
# reading the wrong field or the source changed units/format.

SOURCE_SPECS = {
    "FRED": {
        "display_name": "FRED API",
        "update_frequency": "daily",
        "max_staleness_hours": 24,
        "expected_indicators": [
            "sofr_iorb_spread_bps",
            "cp_treasury_spread_bps",
            "term_premium_10y_bps",
            "ig_oas_bps",
            "hy_oas_bps",
            "vix_level",
            "policy_room_bps",
        ],
        "value_ranges": {
            "sofr_iorb_spread_bps": (-200, 500),
            "cp_treasury_spread_bps": (-100, 1000),
            "term_premium_10y_bps": (-300, 500),
            "ig_oas_bps": (10, 1500),
            "hy_oas_bps": (100, 3000),
            "vix_level": (5, 90),
            "policy_room_bps": (0, 2500),
            "fed_balance_sheet_gdp_pct": (5, 60),
            "core_pce_vs_target_bps": (-500, 1000),
        },
    },
    "CBOE": {
        "display_name": "CBOE CDN (VIX Term Structure)",
        "update_frequency": "daily",
        "max_staleness_hours": 48,
        "expected_indicators": ["vix9d", "vix3m", "vvix"],
        "value_ranges": {
            "vix9d": (5, 120),
            "vix3m": (5, 80),
            "vvix": (50, 200),
            "gamma_ratio": (0.3, 3.0),
            "term_slope": (0.4, 2.5),
        },
    },
    "YAHOO_CRYPTO": {
        "display_name": "Yahoo Finance (BTC-SPY Correlation)",
        "update_frequency": "daily",
        "max_staleness_hours": 72,
        "expected_indicators": ["btc_spy_correlation"],
        "value_ranges": {
            "btc_spy_correlation": (-1.0, 1.0),
        },
    },
    "BINANCE": {
        "display_name": "Binance Futures (Crypto OI)",
        "update_frequency": "real-time",
        "max_staleness_hours": 48,
        "expected_indicators": ["crypto_futures_oi_billions"],
        "value_ranges": {
            "crypto_futures_oi_billions": (1, 500),
        },
    },
    "BIS": {
        "display_name": "BIS OTC Derivatives",
        "update_frequency": "semi-annual",
        "max_staleness_hours": 4320,  # 180 days
        "expected_indicators": [
            "credit_deriv_notional_trillions",
            "equity_deriv_notional_trillions",
        ],
        "value_ranges": {
            "credit_deriv_notional_trillions": (0.05, 20),
            "equity_deriv_notional_trillions": (1, 30),
        },
    },
    "OFR": {
        "display_name": "OFR Hedge Fund Monitor",
        "update_frequency": "quarterly",
        "max_staleness_hours": 2160,  # 90 days
        "expected_indicators": ["hf_leverage_ratio"],
        "value_ranges": {
            "hf_leverage_ratio": (3, 50),
        },
    },
    "CFTC": {
        "display_name": "CFTC COT Reports",
        "update_frequency": "weekly",
        "max_staleness_hours": 168,  # 7 days
        "expected_indicators": ["positioning_score"],
        "value_ranges": {
            "positioning_score": (0, 1),
        },
    },
}


def validate_source(source_name: str, returned_indicators: dict) -> dict:
    """Validate a source's response against its spec.

    Args:
        source_name: Key into SOURCE_SPECS (e.g. "FRED", "CBOE")
        returned_indicators: Dict of indicator_name -> value actually returned

    Returns:
        Health report dict with status, missing indicators, range violations
    """
    spec = SOURCE_SPECS.get(source_name)
    if not spec:
        return {
            "source": source_name,
            "status": "unknown",
            "last_attempt": datetime.utcnow().isoformat(),
            "error": f"No spec defined for source {source_name}",
        }

    now = datetime.utcnow().isoformat()
    missing = []
    range_violations = []

    # Schema check: are expected indicators present?
    for ind in spec["expected_indicators"]:
        if ind not in returned_indicators:
            missing.append(ind)

    # Range check: are values plausible?
    for ind, value in returned_indicators.items():
        if ind in spec.get("value_ranges", {}):
            lo, hi = spec["value_ranges"][ind]
            if value is not None and not (lo <= value <= hi):
                range_violations.append({
                    "indicator": ind,
                    "value": value,
                    "expected_range": [lo, hi],
                })

    # Determine status
    if not returned_indicators:
        status = "down"
    elif missing or range_violations:
        status = "degraded"
    else:
        status = "healthy"

    report = {
        "source": source_name,
        "status": status,
        "last_attempt": now,
        "indicators_returned": list(returned_indicators.keys()),
        "indicators_expected": spec["expected_indicators"],
        "missing_indicators": missing,
        "range_violations": range_violations,
    }

    # Only set last_success if we got data and it looks valid
    if returned_indicators and not range_violations:
        report["last_success"] = now
    elif returned_indicators:
        # Got data but with range violations — still a partial success
        report["last_success"] = now

    return report


def make_down_report(source_name: str, error: str) -> dict:
    """Create a health report for a source that raised an exception."""
    return {
        "source": source_name,
        "status": "down",
        "last_attempt": datetime.utcnow().isoformat(),
        "error": error,
        "indicators_returned": [],
        "indicators_expected": SOURCE_SPECS.get(source_name, {}).get(
            "expected_indicators", []
        ),
        "missing_indicators": SOURCE_SPECS.get(source_name, {}).get(
            "expected_indicators", []
        ),
        "range_violations": [],
    }


def record_health(db, source_name: str, report: dict):
    """Persist health report to database. Never raises."""
    try:
        db.save_health_report(source_name, report)
    except Exception as e:
        logger.debug("Health recording failed for %s: %s", source_name, e)


def get_health_summary(db) -> dict:
    """Build aggregate health summary from stored reports.

    Returns dict suitable for inclusion in API response:
    {
        "status": "healthy"|"degraded",
        "degraded_sources": ["CBOE"],
        "stale_sources": ["BIS"],
        "down_sources": [],
    }
    """
    try:
        reports = db.get_all_health_reports()
    except Exception:
        return {"status": "unknown", "error": "Health data unavailable"}

    if not reports:
        return {"status": "unknown", "note": "No health data yet"}

    degraded = []
    stale = []
    down = []
    now = datetime.utcnow()

    for source_name, report in reports.items():
        status = report.get("status", "unknown")

        # Check staleness against spec
        spec = SOURCE_SPECS.get(source_name, {})
        max_hours = spec.get("max_staleness_hours")
        last_success = report.get("last_success")

        if max_hours and last_success:
            try:
                last_dt = datetime.fromisoformat(last_success)
                hours_since = (now - last_dt).total_seconds() / 3600
                if hours_since > max_hours:
                    stale.append(source_name)
                    continue
            except (ValueError, TypeError):
                pass

        if status == "down":
            down.append(source_name)
        elif status == "degraded":
            degraded.append(source_name)

    # Aggregate status
    if down:
        overall = "down"
    elif degraded or stale:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "degraded_sources": degraded,
        "stale_sources": stale,
        "down_sources": down,
    }


def get_detailed_health(db) -> dict:
    """Build detailed per-source health report for /api/health endpoint."""
    try:
        reports = db.get_all_health_reports()
    except Exception:
        return {
            "status": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Health data unavailable",
        }

    now = datetime.utcnow()
    sources = {}
    counts = {"healthy": 0, "degraded": 0, "stale": 0, "down": 0, "unknown": 0}

    for source_name, spec in SOURCE_SPECS.items():
        report = reports.get(source_name)

        if not report:
            sources[source_name] = {
                "display_name": spec["display_name"],
                "status": "unknown",
                "note": "No data fetched yet",
                "update_frequency": spec.get("update_frequency", "unknown"),
            }
            counts["unknown"] += 1
            continue

        # Compute staleness
        status = report.get("status", "unknown")
        last_success = report.get("last_success")
        staleness_note = None

        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success)
                hours_since = (now - last_dt).total_seconds() / 3600
                max_hours = spec.get("max_staleness_hours", 24)

                if hours_since > max_hours:
                    status = "stale"
                    days = int(hours_since / 24)
                    staleness_note = f"{days} days since last update (max: {int(max_hours / 24)}d)"
            except (ValueError, TypeError):
                pass

        n_returned = len(report.get("indicators_returned", []))
        n_expected = len(spec["expected_indicators"])

        source_detail = {
            "display_name": spec["display_name"],
            "status": status,
            "update_frequency": spec.get("update_frequency", "unknown"),
            "last_success": last_success,
            "last_attempt": report.get("last_attempt"),
            "indicators": f"{n_returned}/{n_expected}",
            "missing_indicators": report.get("missing_indicators", []),
            "range_violations": report.get("range_violations", []),
        }

        if report.get("error"):
            source_detail["error"] = report["error"]
        if report.get("latency_ms"):
            source_detail["latency_ms"] = report["latency_ms"]
        if staleness_note:
            source_detail["staleness_note"] = staleness_note

        sources[source_name] = source_detail
        counts[status] = counts.get(status, 0) + 1

    # Aggregate
    if counts.get("down", 0) > 0:
        overall = "down"
    elif counts.get("degraded", 0) > 0 or counts.get("stale", 0) > 0:
        overall = "degraded"
    elif counts.get("unknown", 0) == len(SOURCE_SPECS):
        overall = "unknown"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": now.isoformat(),
        "summary": {
            "total_sources": len(SOURCE_SPECS),
            **counts,
        },
        "sources": sources,
    }
