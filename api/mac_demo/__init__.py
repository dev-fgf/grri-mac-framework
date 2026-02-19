import json
import sys
import os
import time
from datetime import datetime
import azure.functions as func
import traceback

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.fred_client import FREDClient
    from shared.mac_scorer import calculate_mac
    from shared.database import get_database
    from shared.crypto_client import get_btc_spy_correlation
    from shared.crypto_oi_client import get_crypto_futures_oi
    from shared.cboe_client import get_gamma_indicators
    from shared.ofr_client import get_hf_leverage_ratio
    from shared.bis_client import get_otc_derivatives_indicators
    from shared.health_registry import (
        validate_source, make_down_report, record_health, get_health_summary,
    )
    IMPORTS_OK = True
    IMPORT_ERROR = None
except Exception as e:
    IMPORTS_OK = False
    IMPORT_ERROR = str(e)


# Demo fallback data
DEMO_INDICATORS = {
    "sofr_iorb_spread_bps": 5,
    "cp_treasury_spread_bps": 25,
    "term_premium_10y_bps": 45,
    "ig_oas_bps": 95,
    "hy_oas_bps": 320,
    "vix_level": 18.5,
    "policy_room_bps": 433,
    "fed_balance_sheet_gdp_pct": 28,
    "core_pce_vs_target_bps": 65,
    "btc_spy_correlation": 0.42,
    "crypto_futures_oi_billions": 28.5,
    "vvix": 88.0,
    "gamma_ratio": 0.95,
    "term_slope": 0.92,
    "hf_leverage_ratio": 17.5,
    "credit_deriv_notional_trillions": 0.5,
    "equity_deriv_notional_trillions": 9.0,
}


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get current MAC calculation.

    Priority:
    1. Read from Azure Table cache (fast, pre-computed)
    2. Fetch live from FRED if cache is stale (> 6 hours)
    3. Fallback to demo data if all else fails
    """

    # Check imports first
    if not IMPORTS_OK:
        return func.HttpResponse(
            json.dumps({"error": "Import failed", "details": IMPORT_ERROR}),
            status_code=500,
            mimetype="application/json"
        )

    try:
        db = get_database()
        indicators = None
        data_source = "Demo Data"
        cache_age = None

        # === PRIORITY 1: Try cached data from Azure Table ===
        if db.connected:
            cached = db.get_all_cached_indicators()
            if cached and cached.get("indicators"):
                indicators = cached["indicators"]
                data_source = "Azure Table Cache"
                # Get age of oldest source
                for source, info in cached.get("sources", {}).items():
                    age = info.get("age_seconds", 0)
                    if cache_age is None or age > cache_age:
                        cache_age = age

        # === PRIORITY 2: Fetch live if cache is stale (> 6 hours) ===
        if not indicators or (cache_age and cache_age > 6 * 3600):
            _t = time.time()
            try:
                client = FREDClient()
                live_indicators = client.get_all_indicators()

                if live_indicators:
                    indicators = live_indicators
                    data_source = "FRED API (Live)"
                    db.save_indicators(indicators, source="FRED")

                report = validate_source("FRED", live_indicators or {})
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "FRED", report)
            except Exception as e:
                try:
                    record_health(db, "FRED", make_down_report("FRED", str(e)))
                except Exception:
                    pass

        # === PRIORITY 3: Fallback to demo data ===
        if not indicators:
            indicators = DEMO_INDICATORS.copy()
            data_source = "Demo Data"

        # Enrich with non-FRED indicators (all non-critical)
        # Each source is wrapped with health validation

        # --- Yahoo Finance: BTC-SPY correlation ---
        if "btc_spy_correlation" not in indicators:
            _t = time.time()
            try:
                corr = get_btc_spy_correlation()
                src = {}
                if corr is not None:
                    src["btc_spy_correlation"] = corr
                    indicators["btc_spy_correlation"] = corr
                report = validate_source("YAHOO_CRYPTO", src)
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "YAHOO_CRYPTO", report)
            except Exception as e:
                try:
                    record_health(
                        db,
                        "YAHOO_CRYPTO",
                        make_down_report("YAHOO_CRYPTO", str(e)),
                    )
                except Exception:
                    pass

        # --- Binance: Crypto futures OI ---
        if "crypto_futures_oi_billions" not in indicators:
            _t = time.time()
            try:
                oi = get_crypto_futures_oi()
                src = {}
                if oi is not None:
                    src["crypto_futures_oi_billions"] = oi
                    indicators["crypto_futures_oi_billions"] = oi
                report = validate_source("BINANCE", src)
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "BINANCE", report)
            except Exception as e:
                try:
                    record_health(db, "BINANCE", make_down_report("BINANCE", str(e)))
                except Exception:
                    pass

        # --- CBOE: VIX term structure ---
        if "vvix" not in indicators:
            _t = time.time()
            try:
                vix_level = indicators.get("vix_level")
                gamma = get_gamma_indicators(vix_level=vix_level)
                indicators.update(gamma)
                report = validate_source("CBOE", gamma)
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "CBOE", report)
            except Exception as e:
                try:
                    record_health(db, "CBOE", make_down_report("CBOE", str(e)))
                except Exception:
                    pass

        # --- OFR: Hedge fund leverage ---
        if "hf_leverage_ratio" not in indicators:
            _t = time.time()
            try:
                lev = get_hf_leverage_ratio()
                src = {}
                if lev is not None:
                    src["hf_leverage_ratio"] = lev
                    indicators["hf_leverage_ratio"] = lev
                report = validate_source("OFR", src)
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "OFR", report)
            except Exception as e:
                try:
                    record_health(db, "OFR", make_down_report("OFR", str(e)))
                except Exception:
                    pass

        # --- BIS: OTC derivatives ---
        if "credit_deriv_notional_trillions" not in indicators:
            _t = time.time()
            try:
                bis = get_otc_derivatives_indicators()
                indicators.update(bis)
                report = validate_source("BIS", bis)
                report["latency_ms"] = int((time.time() - _t) * 1000)
                record_health(db, "BIS", report)
            except Exception as e:
                try:
                    record_health(db, "BIS", make_down_report("BIS", str(e)))
                except Exception:
                    pass

        # Calculate MAC score
        result = calculate_mac(indicators)
        result["is_live"] = data_source != "Demo Data"

        # Save MAC snapshot
        saved = db.save_snapshot(result)

        # Build health summary (never fails the response)
        try:
            data_health = get_health_summary(db)
        except Exception:
            data_health = None

        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "is_live": result["is_live"],
            "data_source": data_source,
            "cache_age_seconds": cache_age,
            "data_health": data_health,
            "saved_to_db": saved,
            "db_connected": db.connected,
            **result,
        }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "error": "Runtime error",
                "details": str(e),
                "traceback": traceback.format_exc()
            }),
            status_code=500,
            mimetype="application/json"
        )
