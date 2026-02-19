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
from .sovereign_proxy import (
    BenchmarkEra,
    QuadraticCoefficients,
    SovereignSpreadObservation,
    SovereignProxyMAC,
    HistoricalStressEpisode,
    get_benchmark_era,
    compute_sovereign_spread,
    map_spread_to_mac,
    compute_proxy_mac,
    calibrate_coefficients,
    build_proxy_mac_series,
    format_proxy_mac_report,
    DEFAULT_COEFFICIENTS,
    UK_STRESS_EPISODES,
    DATA_SOURCES,
    PROXY_LIMITATIONS,
)

__all__ = [
    "FREDHistoricalClient",
    "REGIME_PERIODS",
    "get_regime_for_date",
    "MACHistorical",
    # Sovereign bond proxy (v6 §16.2)
    "BenchmarkEra",
    "QuadraticCoefficients",
    "SovereignSpreadObservation",
    "SovereignProxyMAC",
    "HistoricalStressEpisode",
    "get_benchmark_era",
    "compute_sovereign_spread",
    "map_spread_to_mac",
    "compute_proxy_mac",
    "calibrate_coefficients",
    "build_proxy_mac_series",
    "format_proxy_mac_report",
    "DEFAULT_COEFFICIENTS",
    "UK_STRESS_EPISODES",
    "DATA_SOURCES",
    "PROXY_LIMITATIONS",
]
