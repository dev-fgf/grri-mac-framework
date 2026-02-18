"""Data modules for fetching market data from various sources."""

from .fred import FREDClient
from .cftc import CFTCClient
from .etf import ETFClient
from .sec import SECClient, TreasuryDataClient
from .contagion import ContagionDataClient
from .historical_proxies import (
    HistoricalProxyClient,
    ProxyConfig,
    EUROZONE_PROXIES,
    UK_PROXIES,
    JAPAN_PROXIES,
    FRED_SERIES,
    YAHOO_TICKERS,
    list_available_proxies,
    get_proxy_warnings,
)
from .blob_store import (
    BlobStore,
    DataTier,
    get_blob_store,
    RAW_CONTAINER,
    CLEANED_CONTAINER,
)
from .pipeline import (
    DataPipeline,
    IngestResult,
    BatchIngestResult,
    SourceDescriptor,
    FRED_MAC_SERIES,
)

__all__ = [
    # Core data clients
    "FREDClient",
    "CFTCClient",
    "ETFClient",
    "SECClient",
    "TreasuryDataClient",
    "ContagionDataClient",
    # Historical proxies (pre-1998 coverage)
    "HistoricalProxyClient",
    "ProxyConfig",
    "EUROZONE_PROXIES",
    "UK_PROXIES",
    "JAPAN_PROXIES",
    "FRED_SERIES",
    "YAHOO_TICKERS",
    "list_available_proxies",
    "get_proxy_warnings",
    # Azure Blob Storage data lake
    "BlobStore",
    "DataTier",
    "get_blob_store",
    "RAW_CONTAINER",
    "CLEANED_CONTAINER",
    # Ingestion pipeline
    "DataPipeline",
    "IngestResult",
    "BatchIngestResult",
    "SourceDescriptor",
    "FRED_MAC_SERIES",
]
