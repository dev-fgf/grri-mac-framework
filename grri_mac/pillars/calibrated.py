"""
Calibrated pillar thresholds based on historical backtest results.

Calibration methodology:
- Ran backtests against 6 known events (2018-2025)
- Adjusted thresholds so MAC scores match expected ranges
- Validated breach detection against historical outcomes
- Key insight: Positioning breach should predict Treasury hedge failure
"""

# Calibrated thresholds (tightened from original)

LIQUIDITY_THRESHOLDS = {
    "sofr_iorb": {
        "ample": 3,     # < 3 bps (was 5)
        "thin": 15,     # 3-15 bps (was 25)
        "breach": 25,   # > 15 bps (was 50)
    },
    "cp_treasury": {
        "ample": 15,    # < 15 bps (was 20)
        "thin": 40,     # 15-40 bps (was 50)
        "breach": 60,   # > 40 bps (was 100)
    },
    "cross_currency": {
        "ample": -20,   # > -20 bps (was -30)
        "thin": -50,    # -20 to -50 bps (was -75)
        "breach": -80,  # < -50 bps (was -120)
    },
    "bid_ask": {
        "ample": 0.5,   # < 0.5/32 (was 1.0)
        "thin": 1.5,    # 0.5-1.5/32 (was 2.0)
        "breach": 2.5,  # > 1.5/32 (was 4.0)
    },
}

VALUATION_THRESHOLDS = {
    "term_premium": {
        "ample": 80,    # > 80 bps (was 100)
        "thin": 20,     # 20-80 bps (was 0)
        "breach": 0,    # < 20 bps (was -50)
    },
    "ig_oas": {
        "ample": 130,   # > 130 bps (was 150)
        "thin": 100,    # 100-130 bps (was 80)
        "breach": 80,   # < 100 bps (was 50)
    },
    "hy_oas": {
        "ample": 400,   # > 400 bps (was 450)
        "thin": 350,    # 350-400 bps (was 300)
        "breach": 300,  # < 350 bps (was 200)
    },
}

POSITIONING_THRESHOLDS = {
    "basis_trade": {
        "ample": 300,   # < $300B
        "thin": 550,    # $300-550B
        "breach": 750,  # > $550B - crowding risk
    },
    "spec_net_percentile": {
        # Extreme positioning (either direction) is dangerous
        # COVID had 2 percentile (extreme short), April 2025 had 97 (extreme long)
        "ample_low": 35,    # Comfortable range
        "ample_high": 65,
        "thin_low": 18,     # Getting stretched
        "thin_high": 82,
        "breach_low": 5,    # Extreme - forced liquidation risk
        "breach_high": 95,  # Extreme - crowding risk
    },
    "svxy_aum": {
        "ample": 350,   # < $350M
        "thin": 600,    # $350-600M
        "breach": 850,  # > $600M - short vol exposure
    },
}

VOLATILITY_THRESHOLDS = {
    "vix_level": {
        "ample_low": 14,    # (was 15)
        "ample_high": 18,   # (was 20)
        "thin_low": 11,     # (was 12)
        "thin_high": 28,    # (was 35)
        "breach_low": 9,    # (was 10)
        "breach_high": 40,  # (was 50)
    },
    "term_structure": {
        "ample_low": 1.00,   # (unchanged)
        "ample_high": 1.04,  # (was 1.05)
        "thin_low": 0.92,    # (was 0.95)
        "thin_high": 1.06,   # (was 1.08)
        "breach_low": 0.88,  # (was 0.90)
        "breach_high": 1.08, # (was 1.10)
    },
    "rv_iv_gap": {
        "ample": 15,    # (was 20)
        "thin": 30,     # (was 40)
        "breach": 45,   # (was 60)
    },
}

POLICY_THRESHOLDS = {
    "fed_funds_vs_neutral": {
        "ample": 100,   # Within 100 bps of neutral
        "thin": 200,    # 100-200 bps away
        "breach": 275,  # > 200 bps - limited room to act
    },
    "balance_sheet_gdp": {
        "ample": 24,    # < 24% of GDP
        "thin": 33,     # 24-33%
        "breach": 40,   # > 33% - constrained
    },
    "core_pce_vs_target": {
        "ample": 50,    # Within 50 bps of 2%
        "thin": 150,    # 50-150 bps
        "breach": 250,  # > 150 bps - inflation concern
    },
}


def get_calibrated_thresholds() -> dict:
    """Get all calibrated thresholds as a single dict."""
    return {
        "liquidity": LIQUIDITY_THRESHOLDS,
        "valuation": VALUATION_THRESHOLDS,
        "positioning": POSITIONING_THRESHOLDS,
        "volatility": VOLATILITY_THRESHOLDS,
        "policy": POLICY_THRESHOLDS,
    }
