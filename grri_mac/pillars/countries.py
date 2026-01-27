"""Country-specific MAC threshold configurations.

This module provides calibrated thresholds for non-US markets, enabling
cross-country MAC comparisons. Each country profile adapts the 6-pillar
framework to local market characteristics and data sources.

Supported Countries:
- US: United States (baseline, from calibrated.py)
- EU: Eurozone (ECB data)
- JP: Japan (BOJ data)
- UK: United Kingdom (BOE data)

Note: China (CN) excluded due to capital controls and managed markets
which make MAC framework assumptions (free capital flows, market-based
pricing) less applicable.

Data Sources by Region:
- Eurozone: ECB SDW, Eurostat, Bloomberg Euro indices
- Japan: BOJ, FRED (for some JGB data)
- UK: BOE, FRED (for some Gilt data)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CountryProfile:
    """Configuration for a country's MAC thresholds."""

    code: str
    name: str
    currency: str
    central_bank: str
    liquidity_thresholds: dict
    valuation_thresholds: dict
    positioning_thresholds: dict
    volatility_thresholds: dict
    policy_thresholds: dict
    contagion_thresholds: dict
    data_sources: dict
    notes: list[str]


# =============================================================================
# EUROZONE (EU) - ECB Data
# =============================================================================

EU_LIQUIDITY_THRESHOLDS = {
    # €STR-DFR spread (€STR = Euro Short-Term Rate, DFR = Deposit Facility Rate)
    # Source: ECB SDW
    # Equivalent to SOFR-IORB for US
    "estr_dfr_spread_bps": {
        "ample": 5,       # ECB corridor is wider than Fed
        "thin": 20,
        "breach": 40,
    },
    # Euro CP-Bund spread
    # Source: ECB, Bloomberg
    "cp_bund_spread_bps": {
        "ample": 20,
        "thin": 50,
        "breach": 80,
    },
    # EUR/USD cross-currency basis
    # Source: Bloomberg, Refinitiv
    # Negative = dollar funding stress for Euro banks
    "eur_usd_basis_bps": {
        "ample": -15,
        "thin": -40,
        "breach": -70,
    },
    # Bund bid-ask spread (10Y)
    # Source: Bloomberg
    "bund_bid_ask_bps": {
        "ample": 0.3,
        "thin": 1.0,
        "breach": 2.0,
    },
}

EU_VALUATION_THRESHOLDS = {
    # Bund term premium (10Y)
    # Source: ECB estimates
    "bund_term_premium_bps": {
        "ample_low": 20,      # Lower normal range than US (structurally lower yields)
        "ample_high": 100,
        "thin_low": -20,
        "thin_high": 160,
        "breach_low": -70,    # Negative term premium common in EU
        "breach_high": 220,
    },
    # Euro IG OAS
    # Source: ICE BofA Euro Corporate Index
    "euro_ig_oas_bps": {
        "ample_low": 80,      # Tighter than US
        "ample_high": 150,
        "thin_low": 60,
        "thin_high": 240,
        "breach_low": 45,
        "breach_high": 350,
    },
    # Euro HY OAS
    # Source: ICE BofA Euro High Yield Index
    "euro_hy_oas_bps": {
        "ample_low": 300,
        "ample_high": 480,
        "thin_low": 240,
        "thin_high": 700,
        "breach_low": 180,
        "breach_high": 900,
    },
}

EU_POSITIONING_THRESHOLDS = {
    # Bund futures spec net (% of open interest)
    # Source: Eurex CoT-equivalent data
    "bund_spec_net_percentile": {
        "ample_low": 30,
        "ample_high": 70,
        "thin_low": 15,
        "thin_high": 85,
        "breach_low": 5,
        "breach_high": 95,
    },
    # TARGET2 imbalances (€ billions)
    # Source: ECB
    # Large imbalances indicate capital flight within Eurozone
    "target2_imbalance_bn": {
        "ample": 400,
        "thin": 800,
        "breach": 1200,
    },
}

EU_VOLATILITY_THRESHOLDS = {
    # VSTOXX (Euro STOXX 50 volatility index)
    # Source: STOXX, Refinitiv
    "vstoxx_level": {
        "ample_low": 15,
        "ample_high": 22,
        "thin_low": 12,
        "thin_high": 32,
        "breach_low": 10,
        "breach_high": 45,
    },
    # VSTOXX term structure
    "vstoxx_term_structure": {
        "ample_low": 0.98,
        "ample_high": 1.05,
        "thin_low": 0.90,
        "thin_high": 1.08,
        "breach_low": 0.85,
        "breach_high": 1.12,
    },
}

EU_POLICY_THRESHOLDS = {
    # ECB deposit rate vs neutral
    # Source: ECB
    "ecb_rate_vs_neutral_bps": {
        "ample": 100,
        "thin": 175,
        "breach": 250,
    },
    # ECB balance sheet to GDP
    # Source: ECB, Eurostat
    # EU has larger BS/GDP than US historically
    "ecb_balance_sheet_gdp_pct": {
        "ample": 35,       # Higher normal for EU
        "thin": 50,
        "breach": 65,
    },
    # Euro area HICP vs target
    # Source: Eurostat
    "hicp_vs_target_bps": {
        "ample": 50,
        "thin": 150,
        "breach": 250,
    },
}

EU_CONTAGION_THRESHOLDS = {
    # Intra-EU sovereign spread (Italy-Germany 10Y)
    # Source: Bloomberg, Refinitiv
    # Key Eurozone fragmentation indicator
    "btp_bund_spread_bps": {
        "ample": 150,
        "thin": 250,
        "breach": 400,
    },
    # Euro bank CDS (average major EU banks)
    # Source: Bloomberg, Markit
    "eu_bank_cds_bps": {
        "ample": 70,
        "thin": 140,
        "breach": 220,
    },
    # EUR 3M change vs USD
    "eur_usd_3m_change_pct": {
        "ample_low": -4,
        "ample_high": 4,
        "thin_low": -8,
        "thin_high": 8,
        "breach_low": -12,
        "breach_high": 12,
    },
}

EUROZONE_PROFILE = CountryProfile(
    code="EU",
    name="Eurozone",
    currency="EUR",
    central_bank="ECB",
    liquidity_thresholds=EU_LIQUIDITY_THRESHOLDS,
    valuation_thresholds=EU_VALUATION_THRESHOLDS,
    positioning_thresholds=EU_POSITIONING_THRESHOLDS,
    volatility_thresholds=EU_VOLATILITY_THRESHOLDS,
    policy_thresholds=EU_POLICY_THRESHOLDS,
    contagion_thresholds=EU_CONTAGION_THRESHOLDS,
    data_sources={
        "liquidity": "ECB SDW (€STR), Bloomberg (basis)",
        "valuation": "ICE BofA Euro indices via FRED/Bloomberg",
        "positioning": "Eurex (Bund futures), ECB (TARGET2)",
        "volatility": "STOXX (VSTOXX)",
        "policy": "ECB, Eurostat",
        "contagion": "Bloomberg (BTP-Bund), ECB",
    },
    notes=[
        "Wider ECB corridor than Fed (€STR-DFR thresholds adjusted)",
        "TARGET2 imbalances key fragmentation indicator",
        "BTP-Bund spread critical for sovereign stress",
        "VSTOXX typically higher than VIX by ~2-3 points",
    ],
)


# =============================================================================
# JAPAN (JP) - BOJ Data
# =============================================================================

JP_LIQUIDITY_THRESHOLDS = {
    # TONAR-BOJ rate spread (TONAR = Tokyo Overnight Average Rate)
    # Source: BOJ
    "tonar_boj_spread_bps": {
        "ample": 2,        # Very tight due to YCC
        "thin": 8,
        "breach": 15,
    },
    # JGB repo rate
    # Source: JSCC
    "jgb_repo_spread_bps": {
        "ample": 5,
        "thin": 15,
        "breach": 30,
    },
    # USD/JPY basis
    # Source: Bloomberg
    "usd_jpy_basis_bps": {
        "ample": -25,
        "thin": -60,
        "breach": -100,
    },
}

JP_VALUATION_THRESHOLDS = {
    # JGB 10Y vs BOJ target (YCC band)
    # Source: BOJ
    "jgb_10y_vs_target_bps": {
        "ample_low": -25,
        "ample_high": 25,
        "thin_low": -40,
        "thin_high": 40,
        "breach_low": -50,
        "breach_high": 50,   # YCC band edge
    },
    # Japan IG spread
    # Source: Nomura BPI
    "japan_ig_spread_bps": {
        "ample_low": 30,
        "ample_high": 60,
        "thin_low": 20,
        "thin_high": 90,
        "breach_low": 15,
        "breach_high": 130,
    },
}

JP_VOLATILITY_THRESHOLDS = {
    # Nikkei VI
    # Source: Nikkei, JPX
    "nikkei_vi": {
        "ample_low": 16,
        "ample_high": 24,
        "thin_low": 13,
        "thin_high": 32,
        "breach_low": 11,
        "breach_high": 45,
    },
}

JP_POLICY_THRESHOLDS = {
    # BOJ policy rate vs neutral
    "boj_rate_vs_neutral_bps": {
        "ample": 25,       # Very limited room
        "thin": 50,
        "breach": 100,
    },
    # BOJ balance sheet to GDP
    # Source: BOJ
    # Japan has largest central bank BS/GDP
    "boj_balance_sheet_gdp_pct": {
        "ample": 100,      # Japan's normal is extreme by other standards
        "thin": 130,
        "breach": 150,
    },
}

JP_CONTAGION_THRESHOLDS = {
    # JPY 3M change vs USD
    "jpy_3m_change_pct": {
        "ample_low": -5,
        "ample_high": 5,
        "thin_low": -10,
        "thin_high": 10,
        "breach_low": -15,
        "breach_high": 15,
    },
    # Japan bank CDS
    "japan_bank_cds_bps": {
        "ample": 40,
        "thin": 80,
        "breach": 130,
    },
}

JAPAN_PROFILE = CountryProfile(
    code="JP",
    name="Japan",
    currency="JPY",
    central_bank="BOJ",
    liquidity_thresholds=JP_LIQUIDITY_THRESHOLDS,
    valuation_thresholds=JP_VALUATION_THRESHOLDS,
    positioning_thresholds={},  # Limited public data
    volatility_thresholds=JP_VOLATILITY_THRESHOLDS,
    policy_thresholds=JP_POLICY_THRESHOLDS,
    contagion_thresholds=JP_CONTAGION_THRESHOLDS,
    data_sources={
        "liquidity": "BOJ (TONAR), JSCC (repo)",
        "valuation": "BOJ, Nomura BPI",
        "positioning": "Limited public data",
        "volatility": "JPX (Nikkei VI)",
        "policy": "BOJ",
        "contagion": "Bloomberg",
    },
    notes=[
        "YCC policy creates unique JGB dynamics",
        "Massive BOJ balance sheet distorts normal ranges",
        "JPY carry trade unwinds can cause global vol",
        "Limited positioning data publicly available",
    ],
)


# =============================================================================
# UNITED KINGDOM (UK) - BOE Data
# =============================================================================

UK_LIQUIDITY_THRESHOLDS = {
    # SONIA-Bank Rate spread
    # Source: BOE
    "sonia_bank_rate_spread_bps": {
        "ample": 5,
        "thin": 18,
        "breach": 35,
    },
    # GBP/USD basis
    "gbp_usd_basis_bps": {
        "ample": -20,
        "thin": -50,
        "breach": -85,
    },
    # Gilt bid-ask
    "gilt_bid_ask_bps": {
        "ample": 0.4,
        "thin": 1.2,
        "breach": 2.5,
    },
}

UK_VALUATION_THRESHOLDS = {
    # Gilt term premium
    "gilt_term_premium_bps": {
        "ample_low": 30,
        "ample_high": 100,
        "thin_low": 0,
        "thin_high": 160,
        "breach_low": -40,
        "breach_high": 220,
    },
    # UK IG spread
    "uk_ig_spread_bps": {
        "ample_low": 90,
        "ample_high": 160,
        "thin_low": 70,
        "thin_high": 250,
        "breach_low": 55,
        "breach_high": 380,
    },
}

UK_VOLATILITY_THRESHOLDS = {
    # FTSE implied vol
    "vftse_level": {
        "ample_low": 14,
        "ample_high": 20,
        "thin_low": 11,
        "thin_high": 30,
        "breach_low": 9,
        "breach_high": 42,
    },
}

UK_POLICY_THRESHOLDS = {
    # BOE rate vs neutral
    "boe_rate_vs_neutral_bps": {
        "ample": 100,
        "thin": 200,
        "breach": 300,
    },
    # BOE balance sheet to GDP
    "boe_balance_sheet_gdp_pct": {
        "ample": 30,
        "thin": 45,
        "breach": 55,
    },
}

UK_CONTAGION_THRESHOLDS = {
    # GBP 3M change
    "gbp_3m_change_pct": {
        "ample_low": -4,
        "ample_high": 4,
        "thin_low": -8,
        "thin_high": 8,
        "breach_low": -12,
        "breach_high": 12,
    },
    # UK bank CDS
    "uk_bank_cds_bps": {
        "ample": 55,
        "thin": 110,
        "breach": 175,
    },
}

UK_PROFILE = CountryProfile(
    code="UK",
    name="United Kingdom",
    currency="GBP",
    central_bank="BOE",
    liquidity_thresholds=UK_LIQUIDITY_THRESHOLDS,
    valuation_thresholds=UK_VALUATION_THRESHOLDS,
    positioning_thresholds={},
    volatility_thresholds=UK_VOLATILITY_THRESHOLDS,
    policy_thresholds=UK_POLICY_THRESHOLDS,
    contagion_thresholds=UK_CONTAGION_THRESHOLDS,
    data_sources={
        "liquidity": "BOE (SONIA), Bloomberg",
        "valuation": "ICE BofA UK indices",
        "positioning": "Limited public data",
        "volatility": "FTSE (VFTSE)",
        "policy": "BOE",
        "contagion": "Bloomberg",
    },
    notes=[
        "2022 Gilt crisis showed LDI pension vulnerabilities",
        "GBP often acts as risk sentiment barometer",
        "Smaller market than US/EU but globally connected",
    ],
)


# =============================================================================
# PROFILE REGISTRY
# =============================================================================

COUNTRY_PROFILES = {
    "US": None,  # Use calibrated.py thresholds
    "EU": EUROZONE_PROFILE,
    "JP": JAPAN_PROFILE,
    "UK": UK_PROFILE,
}


def get_country_profile(code: str) -> Optional[CountryProfile]:
    """Get country profile by ISO code."""
    return COUNTRY_PROFILES.get(code.upper())


def list_supported_countries() -> list[str]:
    """List supported country codes."""
    return list(COUNTRY_PROFILES.keys())


def get_threshold_comparison(pillar: str) -> dict:
    """
    Compare thresholds across countries for a given pillar.

    Args:
        pillar: Pillar name (liquidity, valuation, etc.)

    Returns:
        Dict mapping country codes to their thresholds
    """
    from .calibrated import get_calibrated_thresholds

    comparison = {}

    # US from calibrated.py
    us_thresholds = get_calibrated_thresholds()
    comparison["US"] = us_thresholds.get(pillar, {})

    # Other countries
    for code, profile in COUNTRY_PROFILES.items():
        if profile is not None:
            threshold_attr = f"{pillar}_thresholds"
            comparison[code] = getattr(profile, threshold_attr, {})

    return comparison
