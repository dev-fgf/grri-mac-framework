"""MAC scoring logic with calibrated thresholds."""

import logging

logger = logging.getLogger(__name__)

# Calibrated thresholds from backtesting
THRESHOLDS = {
    "liquidity": {
        "sofr_iorb": {"ample": 2, "thin": 8, "breach": 15},
        "cp_treasury": {"ample": 15, "thin": 40, "breach": 80},
    },
    "valuation": {
        "term_premium": {"ample": 100, "thin": 25, "breach": -50},
        "ig_oas": {"ample": 150, "thin": 90, "breach": 60},
        "hy_oas": {"ample": 500, "thin": 350, "breach": 250},
    },
    "positioning": {
        "basis_trade": {"ample": 300, "thin": 550, "breach": 750},
    },
    "volatility": {
        "vix": {
            "ample_low": 12,
            "ample_high": 18,
            "thin_high": 28,
            "breach_high": 40,
        },
    },
    "policy": {
        # Policy room = distance from ELB - more room is better
        "policy_room": {"ample": 150, "thin": 50, "breach": 25},
        "balance_sheet_gdp": {"ample": 20, "thin": 30, "breach": 38},
        "core_pce_vs_target": {"ample": 30, "thin": 80, "breach": 150},
    },
    "contagion": {
        # Cross-currency basis (absolute value in bps)
        "cross_currency_basis": {"ample": 15, "thin": 30, "breach": 60},
        # Financial sector OAS spread (G-SIB stress proxy)
        "financial_oas": {"ample": 100, "thin": 150, "breach": 250},
        # IG-HY spread differential (credit contagion)
        "ig_hy_spread_ratio": {"ample": 2.5, "thin": 3.5, "breach": 5.0},
    },
}


def score_indicator_simple(
    value: float,
    ample_threshold: float,
    thin_threshold: float,
    breach_threshold: float,
    lower_is_better: bool = True,
) -> float:
    """
    Score a single indicator on 0-1 scale.

    Args:
        value: Current indicator value
        ample_threshold: Threshold for ample (score=1)
        thin_threshold: Threshold for thin (score=0.5)
        breach_threshold: Threshold for breach (score=0)
        lower_is_better: If True, lower values are better

    Returns:
        Score between 0 and 1
    """
    if lower_is_better:
        if value <= ample_threshold:
            return 1.0
        elif value <= thin_threshold:
            # Linear interpolation between ample and thin
            range_size = thin_threshold - ample_threshold
            position = value - ample_threshold
            return 1.0 - (position / range_size) * 0.5
        elif value <= breach_threshold:
            # Linear interpolation between thin and breach
            range_size = breach_threshold - thin_threshold
            position = value - thin_threshold
            return 0.5 - (position / range_size) * 0.5
        else:
            return 0.0
    else:
        # Higher is better - flip the logic
        if value >= ample_threshold:
            return 1.0
        elif value >= thin_threshold:
            range_size = ample_threshold - thin_threshold
            position = ample_threshold - value
            return 1.0 - (position / range_size) * 0.5
        elif value >= breach_threshold:
            range_size = thin_threshold - breach_threshold
            position = thin_threshold - value
            return 0.5 - (position / range_size) * 0.5
        else:
            return 0.0


def score_indicator_range(
    value: float,
    ample_low: float,
    ample_high: float,
    thin_high: float,
    breach_high: float,
) -> float:
    """Score indicator where middle range is optimal (like VIX)."""
    if ample_low <= value <= ample_high:
        return 1.0
    elif value < ample_low:
        # Too low - unusual, score based on distance
        return max(0.5, 1.0 - (ample_low - value) / ample_low)
    elif value <= thin_high:
        range_size = thin_high - ample_high
        position = value - ample_high
        return 1.0 - (position / range_size) * 0.5
    elif value <= breach_high:
        range_size = breach_high - thin_high
        position = value - thin_high
        return 0.5 - (position / range_size) * 0.5
    else:
        return 0.0


def score_liquidity(indicators: dict) -> tuple[float, str]:
    """Score liquidity pillar from indicators."""
    scores = []

    if "sofr_iorb_spread_bps" in indicators:
        t = THRESHOLDS["liquidity"]["sofr_iorb"]
        scores.append(score_indicator_simple(
            abs(indicators["sofr_iorb_spread_bps"]),
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    if "cp_treasury_spread_bps" in indicators:
        t = THRESHOLDS["liquidity"]["cp_treasury"]
        scores.append(score_indicator_simple(
            indicators["cp_treasury_spread_bps"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def score_valuation(indicators: dict) -> tuple[float, str]:
    """Score valuation pillar from indicators."""
    scores = []

    if "term_premium_10y_bps" in indicators:
        t = THRESHOLDS["valuation"]["term_premium"]
        scores.append(score_indicator_simple(
            indicators["term_premium_10y_bps"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=False,
        ))

    if "ig_oas_bps" in indicators:
        t = THRESHOLDS["valuation"]["ig_oas"]
        scores.append(score_indicator_simple(
            indicators["ig_oas_bps"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=False,
        ))

    if "hy_oas_bps" in indicators:
        t = THRESHOLDS["valuation"]["hy_oas"]
        scores.append(score_indicator_simple(
            indicators["hy_oas_bps"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=False,
        ))

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def score_positioning(indicators: dict) -> tuple[float, str]:
    """Score positioning pillar from CFTC Commitments of Traders data."""
    score, status, _ = score_positioning_with_details(indicators)
    return score, status


def score_positioning_with_details(
    indicators: dict,
) -> tuple[float, str, dict]:
    """Score positioning pillar and return CFTC metadata for transparency."""
    try:
        # Handle both Azure Functions context and standalone execution
        try:
            from shared.cftc_client import (  # type: ignore
                get_cftc_client,
                COT_REPORTS_AVAILABLE,
            )
        except ImportError:
            from api.shared.cftc_client import (
                get_cftc_client,
                COT_REPORTS_AVAILABLE,
            )

        if not COT_REPORTS_AVAILABLE:
            # Use neutral positioning with explanation
            return 0.55, "THIN", {
                "source": "fallback",
                "reason": "cot_reports_not_installed",
                "note": "CFTC COT data requires cot-reports package"
            }

        client = get_cftc_client()

        # Get detailed positioning indicators
        positioning_data = client.get_positioning_indicators(lookback_weeks=52)

        if not positioning_data:
            # Azure Functions may have network restrictions fetching from CFTC
            # Use neutral positioning with current VIX as hint
            vix = indicators.get("vix_level", 18)
            if vix < 15:
                # Low VIX = complacent positioning likely
                score, status = 0.45, "THIN"
            elif vix > 25:
                # High VIX = some hedging likely
                score, status = 0.65, "ADEQUATE"
            else:
                score, status = 0.55, "THIN"

            return score, status, {
                "source": "vix_proxy",
                "reason": "cftc_fetch_failed",
                "note": (
                    "Using VIX as positioning proxy."
                    " CFTC COT data unavailable"
                    " in serverless environment."
                ),
                "vix_level": vix
            }

        score, status = client.get_aggregate_positioning_score(
            lookback_weeks=52,
        )

        if status == "NO_DATA":
            logger.warning("No CFTC data available, using neutral positioning")
            return 0.55, "THIN", {"source": "fallback", "reason": "no_data"}

        # Build metadata showing what data was used
        metadata = {
            "source": "CFTC_COT",
            "contracts": {},
        }

        latest_date = None
        for contract_key, data in positioning_data.items():
            metadata["contracts"][contract_key] = {
                "name": data.get("name"),
                "percentile": data.get("percentile"),
                "signal": data.get("signal"),
                "date": data.get("date"),
            }
            if data.get("date"):
                latest_date = data.get("date")

        metadata["latest_report_date"] = latest_date

        return score, status, metadata
    except Exception as e:
        logger.error(f"Failed to fetch CFTC positioning data: {e}")
        return 0.55, "THIN", {"source": "fallback", "reason": str(e)}


def score_volatility(indicators: dict) -> tuple[float, str]:
    """Score volatility pillar from indicators.

    Combines VIX level with gamma/term-structure proxies for 0DTE risk.
    """
    scores = []

    if "vix_level" in indicators:
        t = THRESHOLDS["volatility"]["vix"]
        scores.append(score_indicator_range(
            indicators["vix_level"],
            t["ample_low"], t["ample_high"],
            t["thin_high"], t["breach_high"],
        ))

    # VVIX (vol-of-vol) — high VVIX means dealers hedging gamma aggressively
    if "vvix" in indicators:
        vvix = indicators["vvix"]
        # Thresholds: <85 calm, 85-100 elevated, 100-120 stressed, >120 extreme
        if vvix <= 85:
            scores.append(1.0)
        elif vvix <= 100:
            scores.append(1.0 - (vvix - 85) / 15 * 0.5)
        elif vvix <= 120:
            scores.append(0.5 - (vvix - 100) / 20 * 0.3)
        else:
            scores.append(0.2)

    # Term structure slope (VIX/VIX3M) — backwardation = near-term stress
    if "term_slope" in indicators:
        slope = indicators["term_slope"]
        # Contango (<1.0) is normal; backwardation (>1.0) is stress
        if slope <= 0.85:
            scores.append(1.0)
        elif slope <= 1.0:
            scores.append(1.0 - (slope - 0.85) / 0.15 * 0.25)
        elif slope <= 1.15:
            scores.append(0.75 - (slope - 1.0) / 0.15 * 0.4)
        else:
            scores.append(0.2)

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def score_policy(indicators: dict) -> tuple[float, str]:
    """Score policy pillar from indicators."""
    scores = []

    if "policy_room_bps" in indicators:
        t = THRESHOLDS["policy"]["policy_room"]
        room = indicators["policy_room_bps"]
        # Higher is better (more room to cut)
        if room >= t["ample"]:
            scores.append(1.0)
        elif room >= t["thin"]:
            scores.append(0.5 + 0.5 * (room - t["thin"]) / (t["ample"] - t["thin"]))
        elif room >= t["breach"]:
            scores.append(0.5 * (room - t["breach"]) / (t["thin"] - t["breach"]))
        else:
            scores.append(0.0)

    if "fed_balance_sheet_gdp_pct" in indicators:
        t = THRESHOLDS["policy"]["balance_sheet_gdp"]
        scores.append(score_indicator_simple(
            indicators["fed_balance_sheet_gdp_pct"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    if "core_pce_vs_target_bps" in indicators:
        t = THRESHOLDS["policy"]["core_pce_vs_target"]
        scores.append(score_indicator_simple(
            abs(indicators["core_pce_vs_target_bps"]),
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def score_contagion(indicators: dict) -> tuple[float, str]:
    """Score contagion pillar from cross-border stress indicators.

    Uses:
    - Cross-currency basis (EUR/USD, JPY/USD funding stress)
    - IG-HY spread ratio (credit contagion risk)
    - Financial sector stress (G-SIB proxy)
    - BTC-SPY correlation (crypto-equity contagion channel)
    - Equity derivatives notional (BIS — TRS/hidden leverage proxy)
    - Crypto futures OI (leveraged crypto derivatives positioning)
    """
    scores = []

    # Cross-currency basis (if available)
    if "cross_currency_basis_bps" in indicators:
        t = THRESHOLDS["contagion"]["cross_currency_basis"]
        scores.append(score_indicator_simple(
            abs(indicators["cross_currency_basis_bps"]),
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    # IG-HY spread ratio (credit contagion)
    if "ig_oas_bps" in indicators and "hy_oas_bps" in indicators:
        ig_oas = indicators["ig_oas_bps"]
        hy_oas = indicators["hy_oas_bps"]
        if ig_oas > 0:
            ratio = hy_oas / ig_oas
            t = THRESHOLDS["contagion"]["ig_hy_spread_ratio"]
            # Lower ratio = tighter spreads = more complacency risk
            # Higher ratio = flight to quality = stress
            if ratio <= t["ample"]:
                scores.append(1.0)
            elif ratio <= t["thin"]:
                range_size = t["thin"] - t["ample"]
                position = ratio - t["ample"]
                scores.append(1.0 - (position / range_size) * 0.5)
            elif ratio <= t["breach"]:
                range_size = t["breach"] - t["thin"]
                position = ratio - t["thin"]
                scores.append(0.5 - (position / range_size) * 0.5)
            else:
                scores.append(0.0)

    # Financial sector OAS (G-SIB stress proxy)
    if "financial_oas_bps" in indicators:
        t = THRESHOLDS["contagion"]["financial_oas"]
        scores.append(score_indicator_simple(
            indicators["financial_oas_bps"],
            t["ample"], t["thin"], t["breach"],
            lower_is_better=True,
        ))

    # BTC-SPY correlation (crypto-equity contagion channel)
    if "btc_spy_correlation" in indicators:
        corr = indicators["btc_spy_correlation"]
        # Thresholds: <0.3 decoupled (good), 0.3-0.5 moderate, >0.7 contagion risk
        if corr <= 0.3:
            scores.append(1.0)
        elif corr <= 0.5:
            scores.append(1.0 - (corr - 0.3) / 0.2 * 0.5)
        elif corr <= 0.7:
            scores.append(0.5 - (corr - 0.5) / 0.2 * 0.3)
        else:
            scores.append(0.2)

    # Equity derivatives notional (BIS — TRS/hidden leverage proxy)
    if "equity_deriv_notional_trillions" in indicators:
        eq_deriv = indicators["equity_deriv_notional_trillions"]
        # Thresholds: <$8T normal, $8-12T elevated, $12-15T crowded, >$15T extreme
        if eq_deriv <= 8:
            scores.append(1.0)
        elif eq_deriv <= 12:
            scores.append(1.0 - (eq_deriv - 8) / 4 * 0.5)
        elif eq_deriv <= 15:
            scores.append(0.5 - (eq_deriv - 12) / 3 * 0.3)
        else:
            scores.append(0.2)

    # Crypto futures OI (leveraged positioning in crypto derivatives)
    if "crypto_futures_oi_billions" in indicators:
        oi = indicators["crypto_futures_oi_billions"]
        # Thresholds: <$20B normal, $20-35B elevated, $35-50B crowded, >$50B extreme
        if oi <= 20:
            scores.append(1.0)
        elif oi <= 35:
            scores.append(1.0 - (oi - 20) / 15 * 0.5)
        elif oi <= 50:
            scores.append(0.5 - (oi - 35) / 15 * 0.3)
        else:
            scores.append(0.2)

    # Default: derive from available spreads
    if not scores:
        # Use IG OAS as proxy for financial stress
        if "ig_oas_bps" in indicators:
            ig_oas = indicators["ig_oas_bps"]
            # Approximate financial sector stress from IG spreads
            if ig_oas <= 80:
                scores.append(1.0)
            elif ig_oas <= 120:
                scores.append(0.75)
            elif ig_oas <= 180:
                scores.append(0.5)
            elif ig_oas <= 250:
                scores.append(0.25)
            else:
                scores.append(0.0)

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def score_private_credit(indicators: dict) -> tuple[float, str]:
    """Score private credit pillar from lending conditions.

    Private credit stress is proxied by:
    - C&I lending standards (SLOOS data - DRTSCILM, DRTSCIS)
    - HY-IG spread differential (leveraged loan stress)
    - Credit conditions tightening
    - HF leverage ratio (OFR Form PF — prime brokerage channel)

    Higher tightening = more stress = lower score.
    """
    scores = []

    # C&I Lending Standards (net % tightening)
    # DRTSCILM: Large/mid firms, DRTSCIS: Small firms
    # Positive = tightening, Negative = easing
    if "ci_lending_standards" in indicators:
        tightening = indicators["ci_lending_standards"]
        # Thresholds: <0 easing (good), 0-20 normal, 20-40 tight, >40 severe
        if tightening <= 0:
            scores.append(1.0)
        elif tightening <= 20:
            scores.append(0.8 - (tightening / 20) * 0.3)
        elif tightening <= 40:
            scores.append(0.5 - ((tightening - 20) / 20) * 0.3)
        else:
            scores.append(max(0.0, 0.2 - ((tightening - 40) / 40) * 0.2))

    # HY spread as leveraged loan proxy
    if "hy_oas_bps" in indicators:
        hy_oas = indicators["hy_oas_bps"]
        # Private credit trades ~100-200bps over syndicated leveraged loans
        # HY OAS thresholds: <350 normal, 350-500 elevated, >500 stressed
        if hy_oas <= 300:
            scores.append(1.0)
        elif hy_oas <= 400:
            scores.append(0.75)
        elif hy_oas <= 500:
            scores.append(0.5)
        elif hy_oas <= 650:
            scores.append(0.25)
        else:
            scores.append(0.0)

    # IG-HY ratio as credit stress indicator
    if "ig_oas_bps" in indicators and "hy_oas_bps" in indicators:
        ig_oas = indicators["ig_oas_bps"]
        hy_oas = indicators["hy_oas_bps"]
        if ig_oas > 0:
            ratio = hy_oas / ig_oas
            # Ratio thresholds: <3 normal, 3-4 elevated, >4 stressed
            if ratio <= 2.5:
                scores.append(1.0)
            elif ratio <= 3.5:
                scores.append(0.6)
            elif ratio <= 4.5:
                scores.append(0.3)
            else:
                scores.append(0.0)

    # HF leverage ratio (OFR Form PF — prime brokerage channel)
    if "hf_leverage_ratio" in indicators:
        lev = indicators["hf_leverage_ratio"]
        # Thresholds: <12x ample, 12-18x thin, 18-25x stretched, >25x breach
        if lev <= 12:
            scores.append(1.0)
        elif lev <= 18:
            scores.append(1.0 - (lev - 12) / 6 * 0.5)
        elif lev <= 25:
            scores.append(0.5 - (lev - 18) / 7 * 0.3)
        else:
            scores.append(0.2)

    if not scores:
        return 0.5, "NO_DATA"

    score = sum(scores) / len(scores)
    return score, get_status(score)


def get_status(score: float) -> str:
    """Get status label for a score."""
    if score >= 0.8:
        return "AMPLE"
    elif score >= 0.5:
        return "THIN"
    elif score >= 0.2:
        return "STRETCHED"
    else:
        return "BREACHING"


def calculate_mac(indicators: dict) -> dict:
    """Calculate full MAC score from indicators."""
    liq_score, liq_status = score_liquidity(indicators)
    val_score, val_status = score_valuation(indicators)
    pos_score, pos_status, pos_metadata = score_positioning_with_details(indicators)
    vol_score, vol_status = score_volatility(indicators)
    pol_score, pol_status = score_policy(indicators)
    con_score, con_status = score_contagion(indicators)
    pc_score, pc_status = score_private_credit(indicators)

    pillar_scores = {
        "liquidity": {"score": round(liq_score, 3), "status": liq_status},
        "valuation": {"score": round(val_score, 3), "status": val_status},
        "positioning": {"score": round(pos_score, 3), "status": pos_status},
        "volatility": {"score": round(vol_score, 3), "status": vol_status},
        "policy": {"score": round(pol_score, 3), "status": pol_status},
        "contagion": {"score": round(con_score, 3), "status": con_status},
        "private_credit": {"score": round(pc_score, 3), "status": pc_status},
    }

    # Calculate composite (equal weighted across 7 pillars)
    all_scores = [liq_score, val_score, pos_score, vol_score,
                  pol_score, con_score, pc_score]
    mac_score = sum(all_scores) / 7

    # Identify breaches
    breach_flags = [
        name for name, data in pillar_scores.items()
        if data["score"] < 0.2
    ]

    # Calculate multiplier
    if mac_score >= 0.8:
        multiplier, tier = 1.0, "Minimal"
    elif mac_score >= 0.6:
        multiplier, tier = 1.5, "Low"
    elif mac_score >= 0.4:
        multiplier, tier = 2.0, "Elevated"
    elif mac_score >= 0.2:
        multiplier, tier = 3.0, "High"
    else:
        multiplier, tier = 5.0, "Critical"

    # Interpretation
    if mac_score >= 0.8:
        interpretation = "AMPLE - Markets have substantial buffer capacity"
    elif mac_score >= 0.6:
        interpretation = "COMFORTABLE - Markets can absorb moderate shocks"
    elif mac_score >= 0.4:
        interpretation = "THIN - Limited buffer, elevated transmission risk"
    elif mac_score >= 0.2:
        interpretation = "STRETCHED - High transmission risk, monitor closely"
    else:
        interpretation = "REGIME BREAK - Buffers exhausted, non-linear dynamics likely"

    return {
        "mac_score": round(mac_score, 3),
        "interpretation": interpretation,
        "multiplier": round(multiplier, 2),
        "multiplier_tier": tier,
        "pillar_scores": pillar_scores,
        "breach_flags": breach_flags,
        "indicators": indicators,
        "positioning_metadata": pos_metadata,
    }
