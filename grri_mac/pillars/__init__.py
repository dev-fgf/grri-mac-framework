"""Six pillar modules for MAC scoring with multi-country support.

Core Pillars:
- Liquidity: Market liquidity and funding conditions
- Valuation: Asset price stretched metrics
- Positioning: Leverage and crowding indicators
- Volatility: Market stress and vol regime
- Policy: Central bank policy space
- Private Credit: Shadow banking stress (NEW)

The Private Credit pillar monitors the $1.7T+ opaque credit market
through indirect proxies (BDC discounts, SLOOS, leveraged loans).
"""

from .liquidity import LiquidityPillar
from .valuation import ValuationPillar
from .positioning import PositioningPillar
from .volatility import VolatilityPillar
from .policy import PolicyPillar
from .calibrated import get_calibrated_thresholds
from .countries import (
    CountryProfile,
    COUNTRY_PROFILES,
    EUROZONE_PROFILE,
    JAPAN_PROFILE,
    UK_PROFILE,
    get_country_profile,
    list_supported_countries,
    get_threshold_comparison,
)
from .private_credit import (
    PrivateCreditPillar,
    PrivateCreditIndicators,
    PrivateCreditScores,
    PrivateCreditStress,
    SLOOSData,
    BDCData,
    LeveragedLoanData,
    PEFirmData,
    analyze_private_credit_exposure,
    get_private_credit_fred_series,
    get_bdc_tickers,
    get_pe_firm_tickers,
)

__all__ = [
    # Core pillars
    "LiquidityPillar",
    "ValuationPillar",
    "PositioningPillar",
    "VolatilityPillar",
    "PolicyPillar",
    # Private Credit pillar (shadow banking)
    "PrivateCreditPillar",
    "PrivateCreditIndicators",
    "PrivateCreditScores",
    "PrivateCreditStress",
    "SLOOSData",
    "BDCData",
    "LeveragedLoanData",
    "PEFirmData",
    "analyze_private_credit_exposure",
    "get_private_credit_fred_series",
    "get_bdc_tickers",
    "get_pe_firm_tickers",
    # Calibration
    "get_calibrated_thresholds",
    # Country profiles
    "CountryProfile",
    "COUNTRY_PROFILES",
    "EUROZONE_PROFILE",
    "JAPAN_PROFILE",
    "UK_PROFILE",
    "get_country_profile",
    "list_supported_countries",
    "get_threshold_comparison",
]
