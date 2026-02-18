"""Data source health monitoring registry.

Validates external data source responses against expected schemas and
value ranges. Detects format changes, missing indicators, and staleness
before they silently degrade the dashboard.

Health state is persisted to Azure Table Storage (or in-memory fallback)
and surfaced via /api/health and the frontend admin banner.

Three indices are monitored:
- MAC (Market Absorption Capacity) — 7 live sources
- GRRI (Global Risk Rating Index) — 2 live sources (World Bank, IMF)
- MRFI (Market Resilience Financialization Index) — inventory only
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# === MAC Source Specifications ===

MAC_SOURCE_SPECS = {
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

# === GRRI Source Specifications ===

GRRI_SOURCE_SPECS = {
    "WORLD_BANK": {
        "display_name": "World Bank WGI + Development",
        "update_frequency": "annual",
        "max_staleness_hours": 8760,  # 365 days
        "expected_indicators": [
            "rule_of_law",
            "gov_effectiveness",
            "regulatory_quality",
            "gdp_growth",
            "inflation",
            "unemployment",
        ],
        "value_ranges": {
            "rule_of_law": (-2.5, 2.5),
            "gov_effectiveness": (-2.5, 2.5),
            "regulatory_quality": (-2.5, 2.5),
            "gdp_growth": (-25, 25),
            "inflation": (-5, 1000),
            "unemployment": (0, 60),
        },
    },
    "IMF_WEO": {
        "display_name": "IMF World Economic Outlook",
        "update_frequency": "semi-annual",
        "max_staleness_hours": 4320,  # 180 days
        "expected_indicators": [
            "weo_inflation",
            "weo_fiscal_balance",
            "weo_gdp_growth",
        ],
        "value_ranges": {
            "weo_inflation": (-5, 1000),
            "weo_fiscal_balance": (-30, 30),
            "weo_gdp_growth": (-25, 25),
        },
    },
}

# === MRFI Source Inventory (not yet integrated) ===

MRFI_SOURCE_INVENTORY = {
    "FRED_MRFI": {
        "display_name": "FRED API (MRFI series)",
        "series_count": 20,
        "shared_with_mac": True,
        "status": "not_monitored",
        "note": "Shared ~60% with MAC FRED sources",
    },
    "YFINANCE": {
        "display_name": "Yahoo Finance (equities/ETFs)",
        "series_count": 18,
        "shared_with_mac": False,
        "status": "not_monitored",
        "note": "SPY, QQQ, TLT, HYG, SVXY, BDCs, PE managers",
    },
    "CFTC_MRFI": {
        "display_name": "CFTC CoT (Treasury/VIX positioning)",
        "series_count": 2,
        "shared_with_mac": True,
        "status": "not_monitored",
        "note": "Weekly bulk ZIP + Socrata API",
    },
    "BIS_MRFI": {
        "display_name": "BIS (OTC derivs + credit gap)",
        "series_count": 2,
        "shared_with_mac": True,
        "status": "not_monitored",
        "note": "Semi-annual bulk CSV",
    },
    "FINRA": {
        "display_name": "FINRA Margin Statistics",
        "series_count": 1,
        "shared_with_mac": False,
        "status": "not_monitored",
        "note": "Monthly Excel download",
    },
    "FED_Z1": {
        "display_name": "Fed Z.1 Financial Accounts",
        "series_count": 1,
        "shared_with_mac": False,
        "status": "not_monitored",
        "note": "Quarterly — broker-dealer leverage",
    },
}

# Combined specs for backward compat (used by validate_source)
SOURCE_SPECS = {**MAC_SOURCE_SPECS, **GRRI_SOURCE_SPECS}


def validate_source(source_name: str, returned_indicators: dict) -> dict:
    """Validate a source's response against its spec.

    Args:
        source_name: Key into SOURCE_SPECS (e.g. "FRED", "CBOE")
        returned_indicators: Dict of indicator_name -> value returned

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

    for ind in spec["expected_indicators"]:
        if ind not in returned_indicators:
            missing.append(ind)

    for ind, value in returned_indicators.items():
        if ind in spec.get("value_ranges", {}):
            lo, hi = spec["value_ranges"][ind]
            if value is not None and not (lo <= value <= hi):
                range_violations.append({
                    "indicator": ind,
                    "value": value,
                    "expected_range": [lo, hi],
                })

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

    if returned_indicators:
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
        "indicators_expected": SOURCE_SPECS.get(
            source_name, {}
        ).get("expected_indicators", []),
        "missing_indicators": SOURCE_SPECS.get(
            source_name, {}
        ).get("expected_indicators", []),
        "range_violations": [],
    }


def record_health(db, source_name: str, report: dict):
    """Persist health report to database. Never raises."""
    try:
        db.save_health_report(source_name, report)
    except Exception as e:
        logger.debug("Health recording failed for %s: %s", source_name, e)


def get_health_summary(db) -> dict:
    """Build aggregate health summary for the frontend banner.

    Only checks MAC sources (the ones that affect the live dashboard).
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

    for source_name in MAC_SOURCE_SPECS:
        report = reports.get(source_name)
        if not report:
            continue

        status = report.get("status", "unknown")
        spec = MAC_SOURCE_SPECS[source_name]
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


def _build_source_details(specs, reports, now):
    """Build per-source detail dicts for a set of source specs."""
    sources = {}
    counts = {
        "healthy": 0, "degraded": 0,
        "stale": 0, "down": 0, "unknown": 0,
    }

    for source_name, spec in specs.items():
        report = reports.get(source_name)

        if not report:
            sources[source_name] = {
                "display_name": spec["display_name"],
                "status": "unknown",
                "note": "No data fetched yet",
                "update_frequency": spec.get(
                    "update_frequency", "unknown"
                ),
            }
            counts["unknown"] += 1
            continue

        status = report.get("status", "unknown")
        last_success = report.get("last_success")
        staleness_note = None

        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success)
                hours_since = (
                    (now - last_dt).total_seconds() / 3600
                )
                max_hours = spec.get("max_staleness_hours", 24)
                if hours_since > max_hours:
                    status = "stale"
                    days = int(hours_since / 24)
                    staleness_note = (
                        f"{days}d since last update "
                        f"(max: {int(max_hours / 24)}d)"
                    )
            except (ValueError, TypeError):
                pass

        n_returned = len(
            report.get("indicators_returned", [])
        )
        n_expected = len(spec["expected_indicators"])

        detail = {
            "display_name": spec["display_name"],
            "status": status,
            "update_frequency": spec.get(
                "update_frequency", "unknown"
            ),
            "last_success": last_success,
            "last_attempt": report.get("last_attempt"),
            "indicators": f"{n_returned}/{n_expected}",
            "missing_indicators": report.get(
                "missing_indicators", []
            ),
            "range_violations": report.get(
                "range_violations", []
            ),
        }

        if report.get("error"):
            detail["error"] = report["error"]
        if report.get("latency_ms"):
            detail["latency_ms"] = report["latency_ms"]
        if staleness_note:
            detail["staleness_note"] = staleness_note

        sources[source_name] = detail
        counts[status] = counts.get(status, 0) + 1

    if counts.get("down", 0) > 0:
        overall = "down"
    elif (counts.get("degraded", 0) > 0
          or counts.get("stale", 0) > 0):
        overall = "degraded"
    elif counts.get("unknown", 0) == len(specs):
        overall = "unknown"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "summary": {"total_sources": len(specs), **counts},
        "sources": sources,
    }


def get_grri_completeness(db) -> dict:
    """Check GRRI data completeness from stored GRRI records."""
    pillars = {
        "political": {"implemented": True, "countries": 0},
        "economic": {"implemented": True, "countries": 0},
        "social": {"implemented": False, "countries": 0},
        "environmental": {"implemented": False, "countries": 0},
    }

    try:
        grri_data = db.get_grri_latest()
        if grri_data:
            for country in grri_data:
                scores = country if isinstance(country, dict) else {}
                if scores.get("political_score") is not None:
                    pillars["political"]["countries"] += 1
                if scores.get("economic_score") is not None:
                    pillars["economic"]["countries"] += 1
                if scores.get("social_score") is not None:
                    pillars["social"]["countries"] += 1
                    pillars["social"]["implemented"] = True
                if scores.get("environmental_score") is not None:
                    pillars["environmental"]["countries"] += 1
                    pillars["environmental"]["implemented"] = True
    except Exception:
        pass

    return pillars


def get_detailed_health(db) -> dict:
    """Build full 3-section health report for /api/health."""
    try:
        reports = db.get_all_health_reports()
    except Exception:
        reports = {}

    now = datetime.utcnow()

    # MAC section
    mac_health = _build_source_details(
        MAC_SOURCE_SPECS, reports, now
    )

    # GRRI section
    grri_health = _build_source_details(
        GRRI_SOURCE_SPECS, reports, now
    )
    grri_health["completeness"] = get_grri_completeness(db)

    # MRFI section (inventory only)
    mrfi_health = {
        "status": "not_integrated",
        "note": (
            "MRFI repo not yet merged. "
            "Showing source inventory only."
        ),
        "sources": MRFI_SOURCE_INVENTORY,
    }

    # Overall status (driven by MAC — it's the live dashboard)
    overall = mac_health["status"]

    return {
        "status": overall,
        "timestamp": now.isoformat(),
        "mac": mac_health,
        "grri": grri_health,
        "mrfi": mrfi_health,
    }
