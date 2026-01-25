import sys
import os
import logging
from datetime import datetime
import azure.functions as func

# Add shared module to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.fred_client import FREDClient
from shared.mac_scorer import calculate_mac
from shared.database import get_database

logger = logging.getLogger(__name__)


def main(timer: func.TimerRequest) -> None:
    """Daily scheduled refresh of MAC data from FRED.

    Runs at 6:00 AM UTC daily to:
    1. Fetch latest indicators from FRED
    2. Calculate MAC score
    3. Save snapshot to Table Storage
    """

    timestamp = datetime.utcnow().isoformat()
    logger.info(f"Daily MAC refresh starting at {timestamp}")

    # Fetch live data from FRED
    client = FREDClient()
    indicators = client.get_all_indicators()

    is_live = bool(indicators)

    if not indicators:
        logger.warning("Could not fetch FRED data - using fallback demo values")
        # Fallback demo data (should rarely happen)
        indicators = {
            "sofr_iorb_spread_bps": 5,
            "cp_treasury_spread_bps": 25,
            "term_premium_10y_bps": 45,
            "ig_oas_bps": 95,
            "hy_oas_bps": 320,
            "vix_level": 18.5,
            "fed_funds_vs_neutral_bps": 175,
        }

    # Calculate MAC score
    result = calculate_mac(indicators)
    result["is_live"] = is_live
    result["indicators"] = indicators

    # Save to database
    db = get_database()
    saved = db.save_snapshot(result)

    mac_score = result.get("mac_score", 0)
    status = "COMFORTABLE" if mac_score >= 0.65 else "CAUTIOUS" if mac_score >= 0.50 else "STRETCHED" if mac_score >= 0.35 else "CRITICAL"

    logger.info(
        f"Daily refresh complete: MAC={mac_score:.3f} ({status}), "
        f"is_live={is_live}, saved={saved}, db_connected={db.connected}"
    )

    if timer.past_due:
        logger.info("Timer is past due - this run was delayed")
