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
    # Term premium: both very negative AND very positive indicate stress
    "term_premium": {
        "ample_low": 40,      # Normal range: 40-120 bps
        "ample_high": 120,
        "thin_low": 0,        # Thin range: 0-40 or 120-200
        "thin_high": 200,
        "breach_low": -50,    # Breach: < -50 (inversion) or > 250 (panic steepening)
        "breach_high": 250,
    },
    # Credit spreads: both compressed AND extremely wide indicate problems
    # Compressed = complacency/repricing risk, Wide = crisis/distress
    "ig_oas": {
        "ample_low": 100,     # Normal range: 100-180 bps
        "ample_high": 180,
        "thin_low": 75,       # Thin range: 75-100 or 180-280
        "thin_high": 280,
        "breach_low": 60,     # Breach: < 60 (too tight) or > 400 (crisis)
        "breach_high": 400,
    },
    "hy_oas": {
        "ample_low": 350,     # Normal range: 350-550 bps
        "ample_high": 550,
        "thin_low": 280,      # Thin range: 280-350 or 550-800
        "thin_high": 800,
        "breach_low": 200,    # Breach: < 200 (too tight) or > 1000 (crisis)
        "breach_high": 1000,
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

# =============================================================================
# CONTAGION PILLAR - International transmission and spillover risk
#
# FREE DATA SOURCES (implemented in grri_mac/data/contagion.py):
#   - EM Flows: yfinance EEM/VWO ETF flows (1-day lag proxy)
#   - Banking Stress: FRED BAMLC0A4CBBB (BBB Corp Spread, Dec 1996+)
#   - DXY Change: FRED DTWEXBGS (Trade Weighted Dollar, 1973+)
#   - EMBI Spread: FRED BAMLEMCBPIOAS (ICE BofA EM OAS, 1998+)
#   - Global Equity Corr: Calculated from yfinance SPY/EFA/EEM
#
# PREMIUM ALTERNATIVES (for future upgrade):
#   - EM Flows: EPFR subscription (~$15K/yr) for weekly institutional flows
#   - Banking Stress: Bloomberg/Markit G-SIB CDS spreads
#   - EMBI Spread: Refinitiv/Bloomberg for actual JPMorgan EMBI+
# =============================================================================
CONTAGION_THRESHOLDS = {
    # EM Portfolio Flows (% of AUM, weekly)
    # Free: EEM/VWO ETF flows (1-day lag) | Premium: IIF/EPFR data
    # Negative = outflows (capital flight), Positive = inflows
    # Both extremes are dangerous: outflows = stress, massive inflows = bubble risk
    "em_flow_pct_weekly": {
        "ample_low": -0.5,      # Normal range: -0.5% to +0.5% weekly
        "ample_high": 0.5,
        "thin_low": -1.5,       # Thin: -1.5% to -0.5% or +0.5% to +1.5%
        "thin_high": 1.5,
        "breach_low": -3.0,     # Breach: < -3% (panic outflow) or > +3% (bubble)
        "breach_high": 3.0,
    },

    # Global Systemically Important Bank CDS (average G-SIB spread)
    # Free: FRED BAMLC0A4CBBB BBB spread (Dec 1996+) | Premium: Bloomberg/Markit CDS
    # Higher = more stress in global banking system
    "gsib_cds_avg_bps": {
        "ample": 60,            # < 60 bps - healthy banking system
        "thin": 120,            # 60-120 bps - elevated stress
        "breach": 180,          # > 180 bps - systemic banking stress
    },

    # Dollar Index 3-Month Change (%)
    # Free: FRED DTWEXBGS (1973+)
    # Strong dollar squeeze creates EM/global funding stress
    "dxy_3m_change_pct": {
        "ample_low": -3.0,      # Normal range: -3% to +3%
        "ample_high": 3.0,
        "thin_low": -6.0,       # Thin: -6% to -3% or +3% to +6%
        "thin_high": 6.0,
        "breach_low": -10.0,    # Breach: < -10% (dollar crash) or > +10% (squeeze)
        "breach_high": 10.0,
    },

    # EM Sovereign Spread (EMBI+ or similar)
    # Free: FRED BAMLEMCBPIOAS ICE BofA EM OAS (1998+) | Premium: JPMorgan EMBI
    # Both compression AND extreme widening indicate problems
    "embi_spread_bps": {
        "ample_low": 250,       # Normal range: 250-400 bps
        "ample_high": 400,
        "thin_low": 180,        # Thin: 180-250 or 400-600 bps
        "thin_high": 600,
        "breach_low": 120,      # Breach: < 120 (complacency) or > 800 (crisis)
        "breach_high": 800,
    },

    # Global Equity Correlation (30-day rolling avg)
    # Free: Calculated from yfinance SPY/EFA/EEM
    # High correlation = contagion spreading, Low = decoupling (can miss spillovers)
    "global_equity_corr": {
        "ample_low": 0.40,      # Normal range: 0.40-0.60
        "ample_high": 0.60,
        "thin_low": 0.25,       # Thin: 0.25-0.40 or 0.60-0.80
        "thin_high": 0.80,
        "breach_low": 0.15,     # Breach: < 0.15 (fragmented) or > 0.90 (panic)
        "breach_high": 0.90,
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
        "contagion": CONTAGION_THRESHOLDS,
    }
