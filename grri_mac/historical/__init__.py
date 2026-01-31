"""Historical MAC Framework - Pre-1973 Market Stress Analysis.

This module extends the MAC framework back to 1945 using available FRED data.
Due to limited data availability, it uses a simplified 3-pillar model:
- Credit Stress (BAA-AAA spread)
- Policy Room (Fed Funds or proxy)
- Positioning (Margin Debt / Market Cap)

Volatility is calculated from realized returns where VIX is unavailable.
"""

from .fred_historical import FREDHistoricalClient
from .regime_analysis import REGIME_PERIODS, get_regime_for_date
from .mac_historical import MACHistorical

__all__ = [
    "FREDHistoricalClient",
    "REGIME_PERIODS",
    "get_regime_for_date", 
    "MACHistorical",
]
