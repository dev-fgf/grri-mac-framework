"""Data modules for fetching market data from various sources."""

from .fred import FREDClient
from .cftc import CFTCClient
from .etf import ETFClient
from .sec import SECClient, TreasuryDataClient

__all__ = [
    "FREDClient",
    "CFTCClient",
    "ETFClient",
    "SECClient",
    "TreasuryDataClient",
]
