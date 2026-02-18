"""Data ingestion pipeline — download → store raw → clean → store cleaned.

Orchestrates all MAC framework data sources through a two-tier Azure Blob
Storage data lake (see :pymod:`grri_mac.data.blob_store`).

Example::

    from grri_mac.data.pipeline import DataPipeline

    pipeline = DataPipeline()
    result = pipeline.ingest("fred", series_ids=["VIXCLS", "BAA10Y"])
    result = pipeline.ingest_all()         # every registered source
    df     = pipeline.get_cleaned("fred", "VIXCLS")

Source Registry
---------------
Each source entry defines:
- ``client_factory`` — callable returning a client instance
- ``fetch`` — callable(client, series_id) →
  raw data (bytes / dict / DataFrame)
- ``clean``          — callable(raw_data, series_id) → cleaned pd.DataFrame
- ``series_ids``     — list of series identifiers this source provides
- ``raw_ext``        — file extension for the raw tier (``.json``, ``.csv``, …)
"""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd  # type: ignore[import-untyped]

from .blob_store import BlobStore, DataTier, get_blob_store

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    """Outcome of a single series ingestion."""

    source: str
    series_id: str
    raw_stored: bool = False
    cleaned_stored: bool = False
    raw_rows: int = 0
    cleaned_rows: int = 0
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def ok(self) -> bool:
        return self.error is None and self.cleaned_stored


@dataclass
class BatchIngestResult:
    """Aggregated result for a batch of series."""

    source: str
    results: List[IngestResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return self.total - self.succeeded

    def summary(self) -> str:
        return (
            f"{self.source}: {self.succeeded}/{self.total} series ingested"
            f" ({self.failed} failed)"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Source descriptor
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SourceDescriptor:
    """Describes how to fetch, store, and clean a data source."""

    name: str
    series_ids: List[str]
    fetch: Callable[[Any, str], Any]
    clean: Callable[[Any, str], pd.DataFrame]
    client_factory: Callable[[], Any]
    raw_ext: str = ".json"
    description: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Standard cleaning helpers
# ──────────────────────────────────────────────────────────────────────────────

def _clean_fred_series(raw: dict, series_id: str) -> pd.DataFrame:
    """Convert FRED API JSON (dates + values) into a clean DataFrame.

    Expected input format (matches both ``fred_client.py`` cache and API)::

        {"dates": ["2020-01-01", ...], "values": [1.23, None, ...]}

    Returns:
        DataFrame with ``DatetimeIndex`` named ``date`` and a single
        ``value`` column.  NaN rows are dropped.
    """
    dates = raw.get("dates", [])
    values = raw.get("values", [])

    if isinstance(raw, pd.Series):
        # Direct pandas Series (from pickle cache)
        df = raw.to_frame(name="value")
        df.index.name = "date"
        df = df.dropna()
        return df

    df = pd.DataFrame({"date": dates, "value": values})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.set_index("date").sort_index()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna()
    return df


def _clean_time_series_csv(raw: bytes, series_id: str) -> pd.DataFrame:
    """Clean a generic time-series CSV (date + value columns)."""
    df = pd.read_csv(io.BytesIO(raw))

    # Try to detect date column
    date_col = None
    for candidate in ("date", "Date", "DATE", "year", "Year"):
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None and len(df.columns) >= 1:
        date_col = df.columns[0]

    # Try to detect value column
    val_col = None
    for candidate in ("value", "Value", "close", "Close", "rate", "Rate"):
        if candidate in df.columns:
            val_col = candidate
            break
    if val_col is None and len(df.columns) >= 2:
        val_col = df.columns[1]

    if date_col and val_col:
        df = df[[date_col, val_col]].copy()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.set_index("date").sort_index()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna()

    return df


def _clean_ohlcv(raw: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Standardise an OHLCV DataFrame (from yfinance / ETF client)."""
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = raw.copy()
    # Normalise column names
    df.columns = [c.lower().strip() for c in df.columns]
    ohlcv_cols = ("open", "high", "low", "close", "volume")
    keep = [
        c for c in ohlcv_cols if c in df.columns
    ]
    df = df[keep]
    df.index.name = "date"
    return df.dropna(subset=["close"]) if "close" in df.columns else df


def _clean_json_timeseries(raw: Any, series_id: str) -> pd.DataFrame:
    """Clean JSON that is either a list of {date, value} dicts or a
    two-key dict (dates/values)."""
    if isinstance(raw, dict):
        return _clean_fred_series(raw, series_id)
    if isinstance(raw, list):
        df = pd.DataFrame(raw)
        if "date" in df.columns and "value" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).set_index("date").sort_index()
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df.dropna()
    return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# Source registry — built-in sources
# ──────────────────────────────────────────────────────────────────────────────

# FRED series used across the MAC framework
FRED_MAC_SERIES = [
    # Liquidity
    "SOFR", "IORB", "IOER", "TEDRATE", "DFF", "DCPF3M", "DTB3", "TB3MS",
    "FEDFUNDS", "EFFR",
    # Valuation
    "BAMLC0A0CM", "BAMLH0A0HYM2", "AAA", "BAA", "DGS10", "BAA10Y",
    "IRLTLT01USM156N", "BAMLC0A4CBBB", "BAMLC0A1CAAA",
    # Volatility
    "VIXCLS", "VXOCLS", "NASDAQCOM",
    # Policy
    "DGS2", "DGS30", "WALCL", "BOGMBASE", "GDP", "PCEPILFE", "CPIAUCSL",
    # Contagion
    "DTWEXBGS", "BAMLEMCBPIOAS", "BAMLEMHBHYCRPIOAS",
]

# NBER Macrohistory series
NBER_SERIES_IDS = [
    "m13001", "m13002", "m13009", "m13019", "m13022",
    "m13024", "m13026", "m13033a", "m13033b", "m13035", "m13036",
    "m13029a", "m14076",
]

# Historical file-based series
HISTORICAL_FILE_SERIES = [
    "SCHWERT_VOL", "BOE_GBPUSD", "BOE_BANKRATE", "MW_GDP", "FINRA_MARGIN_DEBT",
]

# ETF tickers for positioning / volatility
ETF_TICKERS = [
    "SVXY", "UVXY", "VXX", "TQQQ", "SQQQ", "SPXL", "SPXS",
    "LQD", "HYG", "JNK", "TLT", "IEF", "SHY",
]

# Crypto symbols
CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD"]

# CBOE volatility indices
CBOE_INDICES = ["VIX9D", "VIX3M", "VVIX"]


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────────

class DataPipeline:
    """Orchestrates data ingestion through the two-tier data lake.

    The pipeline:

    1. **Fetch** raw data from the external source.
    2. **Store raw** in the ``raw`` tier (blob storage / local).
    3. **Clean** the raw data into a standardised DataFrame.
    4. **Store cleaned** in the ``cleaned`` tier (Parquet).

    Sources are registered via :meth:`register_source` or the built-in
    registry that covers FRED, NBER, CBOE, BIS, OFR, CFTC, ETFs, and
    crypto.
    """

    def __init__(self, store: Optional[BlobStore] = None) -> None:
        self._store = store or get_blob_store()
        self._sources: Dict[str, SourceDescriptor] = {}
        self._register_builtins()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_source(self, desc: SourceDescriptor) -> None:
        """Register (or replace) a data source."""
        self._sources[desc.name] = desc

    @property
    def sources(self) -> Dict[str, SourceDescriptor]:
        """Mapping of registered source descriptors."""
        return dict(self._sources)

    def list_sources(self) -> List[str]:
        """Return sorted list of registered source names."""
        return sorted(self._sources)

    def list_series(self, source: str) -> List[str]:
        """Return series IDs for a registered source."""
        desc = self._sources.get(source)
        return list(desc.series_ids) if desc else []

    # ------------------------------------------------------------------
    # Built-in source registration
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register all built-in MAC framework data sources."""

        # ── FRED ──────────────────────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="fred",
            series_ids=FRED_MAC_SERIES,
            fetch=self._fetch_fred,
            clean=_clean_fred_series,
            client_factory=lambda: None,  # uses module-level function
            raw_ext=".json",
            description="FRED API — 30+ macro/financial time series",
        ))

        # ── NBER Macrohistory ─────────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="nber",
            series_ids=NBER_SERIES_IDS,
            fetch=self._fetch_nber,
            clean=lambda raw, sid: _clean_time_series_csv(raw, sid),
            client_factory=lambda: None,
            raw_ext=".csv",
            description="NBER Macrohistory Database — pre-1970 rates & bonds",
        ))

        # ── CBOE VIX term structure ───────────────────────────────────
        self.register_source(SourceDescriptor(
            name="cboe",
            series_ids=CBOE_INDICES,
            fetch=self._fetch_cboe,
            clean=lambda raw, sid: _clean_time_series_csv(raw, sid),
            client_factory=lambda: None,
            raw_ext=".csv",
            description="CBOE CDN — VIX9D, VIX3M, VVIX term structure",
        ))

        # ── Historical file series ────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="historical",
            series_ids=HISTORICAL_FILE_SERIES,
            fetch=self._fetch_historical_file,
            clean=lambda raw, sid: _clean_time_series_csv(raw, sid),
            client_factory=lambda: None,
            raw_ext=".csv",
            description="Schwert, BoE, MeasuringWorth, FINRA historical CSVs",
        ))

        # ── ETF positioning / volatility ──────────────────────────────
        self.register_source(SourceDescriptor(
            name="etf",
            series_ids=ETF_TICKERS,
            fetch=self._fetch_etf,
            clean=_clean_ohlcv,
            client_factory=lambda: None,
            raw_ext=".csv",
            description=(
                "yfinance ETFs — leveraged,"
                " volatility, credit, treasury"
            ),
        ))

        # ── Crypto ────────────────────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="crypto",
            series_ids=CRYPTO_SYMBOLS,
            fetch=self._fetch_crypto_prices,
            clean=_clean_ohlcv,
            client_factory=lambda: None,
            raw_ext=".csv",
            description="Yahoo Finance — BTC/ETH daily prices",
        ))

        # ── BIS OTC Derivatives ───────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="bis",
            series_ids=["credit", "equity"],
            fetch=self._fetch_bis,
            clean=_clean_json_timeseries,
            client_factory=lambda: None,
            raw_ext=".json",
            description="BIS — OTC derivatives notional outstanding",
        ))

        # ── OFR Hedge Fund Monitor ────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="ofr",
            series_ids=["hf_leverage"],
            fetch=self._fetch_ofr,
            clean=_clean_json_timeseries,
            client_factory=lambda: None,
            raw_ext=".json",
            description="OFR — QHF aggregate leverage ratio",
        ))

        # ── CFTC COT positioning ──────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="cftc",
            series_ids=["SP500", "TREASURY_10Y", "VIX", "TREASURY_2Y"],
            fetch=self._fetch_cftc,
            clean=_clean_json_timeseries,
            client_factory=lambda: None,
            raw_ext=".json",
            description=(
                "CFTC COT — speculative positioning"
                " (S&P, Treasuries, VIX)"
            ),
        ))

        # ── Crypto Futures OI ─────────────────────────────────────────
        self.register_source(SourceDescriptor(
            name="crypto_oi",
            series_ids=["aggregate_oi"],
            fetch=self._fetch_crypto_oi,
            clean=_clean_json_timeseries,
            client_factory=lambda: None,
            raw_ext=".json",
            description="Binance — BTC+ETH perpetual futures open interest",
        ))

    # ------------------------------------------------------------------
    # Fetch implementations (thin wrappers delegating to existing clients)
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_fred(_client: Any, series_id: str) -> dict:
        """Fetch a FRED series via fredapi."""
        try:
            from fredapi import Fred  # type: ignore
            import os
            api_key = os.environ.get("FRED_API_KEY")
            if not api_key:
                raise ValueError("FRED_API_KEY not set")
            fred = Fred(api_key=api_key)
            s = fred.get_series(series_id)
            dates = [d.strftime("%Y-%m-%d") for d in s.index]
            values = [
                None if (
                    v is None
                    or (isinstance(v, float)
                        and math.isnan(v))
                )
                else float(v) for v in s.values
            ]
            return {"dates": dates, "values": values}
        except Exception as exc:
            logger.warning("FRED fetch %s failed: %s", series_id, exc)
            raise

    @staticmethod
    def _fetch_nber(_client: Any, series_id: str) -> bytes:
        """Fetch an NBER .dat file and return as CSV bytes."""
        import urllib.request

        chapter = series_id[1:3]  # e.g. "m13001" → "13"
        url = (
            f"https://data.nber.org/databases/macrohistory/"
            f"rectdata/{chapter}/{series_id}.dat"
        )
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read()

        # Parse .dat to CSV
        lines = raw.decode("latin-1").strip().splitlines()
        rows = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                year, month, val = parts[0], parts[1], parts[2]
                if val != ".":
                    rows.append(f"{year}-{int(month):02d}-01,{val}")
        csv_text = "date,value\n" + "\n".join(rows)
        return csv_text.encode("utf-8")

    @staticmethod
    def _fetch_cboe(_client: Any, series_id: str) -> bytes:
        """Fetch a CBOE volatility index CSV."""
        import requests as _requests  # type: ignore

        cdn = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
        urls = {
            "VIX9D": f"{cdn}/VIX9D_History.csv",
            "VIX3M": f"{cdn}/VIX3M_History.csv",
            "VVIX":  f"{cdn}/VVIX_History.csv",
        }
        url = urls.get(series_id)
        if not url:
            raise ValueError(f"Unknown CBOE index: {series_id}")
        resp = _requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _fetch_historical_file(_client: Any, series_id: str) -> bytes:
        """Read a historical CSV from disk and return bytes."""
        from pathlib import Path

        base = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "historical"
        )
        mapping = {
            "SCHWERT_VOL":       "schwert/schwert_volatility.csv",
            "BOE_GBPUSD":        "boe/boe_gbpusd.csv",
            "BOE_BANKRATE":      "boe/boe_bankrate.csv",
            "MW_GDP":            "measuringworth/us_gdp.csv",
            "FINRA_MARGIN_DEBT": "finra/margin_debt.csv",
        }
        rel = mapping.get(series_id)
        if not rel:
            raise ValueError(f"Unknown historical series: {series_id}")
        path = base / rel
        if not path.exists():
            raise FileNotFoundError(f"Historical file not found: {path}")
        return path.read_bytes()

    @staticmethod
    def _fetch_etf(_client: Any, series_id: str) -> pd.DataFrame:
        """Fetch 5 years of OHLCV via yfinance."""
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            raise ImportError("yfinance not installed")
        ticker = yf.Ticker(series_id)
        return ticker.history(period="5y")

    @staticmethod
    def _fetch_crypto_prices(_client: Any, series_id: str) -> pd.DataFrame:
        """Fetch crypto daily OHLCV via yfinance."""
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            raise ImportError("yfinance not installed")
        ticker = yf.Ticker(series_id)
        return ticker.history(period="5y")

    @staticmethod
    def _fetch_bis(_client: Any, series_id: str) -> dict:
        """Fetch BIS OTC derivatives data point."""
        import sys
        import os
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "..", "api"
        ))
        from api.shared.bis_client import (  # type: ignore
            _fetch_bis_latest,
        )
        val = _fetch_bis_latest(series_id)
        return {
            "dates": [datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            "values": [val],
        }

    @staticmethod
    def _fetch_ofr(_client: Any, series_id: str) -> dict:
        """Fetch OFR hedge fund leverage."""
        import sys
        import os
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "..", "api"
        ))
        from api.shared.ofr_client import get_hf_leverage_ratio
        val = get_hf_leverage_ratio()
        return {
            "dates": [datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            "values": [val],
        }

    @staticmethod
    def _fetch_cftc(_client: Any, series_id: str) -> dict:
        """Fetch CFTC COT data stub — returns structure for storage."""
        # COT data requires cot-reports package; return placeholder
        return {
            "dates": [datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            "values": [None],
            "note": f"CFTC/{series_id} — requires cot-reports package",
        }

    @staticmethod
    def _fetch_crypto_oi(_client: Any, series_id: str) -> dict:
        """Fetch crypto futures OI."""
        import sys
        import os
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "..", "api"
        ))
        from api.shared.crypto_oi_client import get_crypto_futures_oi
        val = get_crypto_futures_oi()
        return {
            "dates": [datetime.now(timezone.utc).strftime("%Y-%m-%d")],
            "values": [val],
        }

    # ══════════════════════════════════════════════════════════════════════
    # Core pipeline methods
    # ══════════════════════════════════════════════════════════════════════

    def ingest(
        self,
        source: str,
        series_ids: Optional[Sequence[str]] = None,
        *,
        date_str: Optional[str] = None,
        skip_existing: bool = False,
        cleaned_fmt: str = "parquet",
    ) -> BatchIngestResult:
        """Ingest one or more series from a registered source.

        Args:
            source: Registered source name (e.g. ``"fred"``).
            series_ids: Subset of series to ingest.  ``None`` = all.
            date_str: ISO date stamp for blob naming.
            skip_existing: If ``True``, skip series where the cleaned
                blob already exists for *date_str*.
            cleaned_fmt: ``"parquet"`` (default) or ``"csv"``.

        Returns:
            BatchIngestResult with per-series outcomes.
        """
        desc = self._sources.get(source)
        if desc is None:
            raise ValueError(
                f"Unknown source '{source}'. "
                f"Registered: {', '.join(self.list_sources())}"
            )

        ids = list(series_ids) if series_ids else desc.series_ids
        batch = BatchIngestResult(source=source)

        for sid in ids:
            result = self._ingest_one(
                desc, sid, date_str,
                skip_existing, cleaned_fmt,
            )
            batch.results.append(result)

        logger.info(batch.summary())
        return batch

    def _ingest_one(
        self,
        desc: SourceDescriptor,
        series_id: str,
        date_str: Optional[str],
        skip_existing: bool,
        cleaned_fmt: str,
    ) -> IngestResult:
        """Ingest a single series: fetch → raw → clean → cleaned."""
        res = IngestResult(source=desc.name, series_id=series_id)

        ext_clean = ".parquet" if cleaned_fmt == "parquet" else ".csv"

        # Skip if already present
        if skip_existing and self._store.exists(
            desc.name, series_id, DataTier.CLEANED, ext_clean, date_str
        ):
            res.cleaned_stored = True
            return res

        # 1) Fetch raw
        try:
            client = desc.client_factory()
            raw = desc.fetch(client, series_id)
        except Exception as exc:
            res.error = f"Fetch error: {exc}"
            logger.warning("Fetch %s/%s failed: %s", desc.name, series_id, exc)
            return res

        # 2) Store raw
        try:
            if isinstance(raw, bytes):
                res.raw_stored = self._store.upload_raw_bytes(
                    desc.name, series_id, raw, ext=desc.raw_ext,
                    date_str=date_str,
                )
            elif isinstance(raw, pd.DataFrame):
                res.raw_stored = self._store.upload_raw_csv(
                    desc.name, series_id, raw, date_str=date_str,
                )
                res.raw_rows = len(raw)
            elif isinstance(raw, (dict, list)):
                res.raw_stored = self._store.upload_raw_json(
                    desc.name, series_id, raw, date_str=date_str,
                )
            else:
                # Fallback — serialise as JSON
                res.raw_stored = self._store.upload_raw_json(
                    desc.name, series_id, raw, date_str=date_str,
                )
        except Exception as exc:
            logger.warning("Raw store %s/%s: %s", desc.name, series_id, exc)

        # 3) Clean
        try:
            cleaned: pd.DataFrame = desc.clean(raw, series_id)
            res.cleaned_rows = len(cleaned)
        except Exception as exc:
            res.error = f"Clean error: {exc}"
            logger.warning("Clean %s/%s failed: %s", desc.name, series_id, exc)
            return res

        # 4) Store cleaned
        try:
            res.cleaned_stored = self._store.upload_dataframe(
                desc.name, series_id, cleaned,
                fmt=cleaned_fmt, date_str=date_str,
            )
        except Exception as exc:
            res.error = f"Store cleaned error: {exc}"
            logger.warning(
                "Cleaned store %s/%s failed: %s", desc.name, series_id, exc
            )

        return res

    def ingest_all(
        self,
        *,
        date_str: Optional[str] = None,
        skip_existing: bool = False,
        cleaned_fmt: str = "parquet",
        sources: Optional[Sequence[str]] = None,
    ) -> Dict[str, BatchIngestResult]:
        """Ingest every series from every registered source.

        Args:
            date_str: ISO date override.
            skip_existing: Skip already-stored cleaned blobs.
            cleaned_fmt: Output format.
            sources: Optional subset of source names.

        Returns:
            ``{source_name: BatchIngestResult}``
        """
        names = list(sources) if sources else self.list_sources()
        all_results: Dict[str, BatchIngestResult] = {}

        for name in names:
            try:
                all_results[name] = self.ingest(
                    name, date_str=date_str,
                    skip_existing=skip_existing, cleaned_fmt=cleaned_fmt,
                )
            except Exception as exc:
                logger.error("Source %s failed entirely: %s", name, exc)
                all_results[name] = BatchIngestResult(source=name)

        return all_results

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_cleaned(
        self,
        source: str,
        series_id: str,
        *,
        fmt: str = "parquet",
        date_str: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Retrieve a cleaned DataFrame from the data lake.

        Args:
            source: Source name.
            series_id: Series identifier.
            fmt: ``"parquet"`` or ``"csv"``.
            date_str: ISO date override.

        Returns:
            DataFrame, or ``None`` if not present.
        """
        return self._store.download_dataframe(
            source, series_id, fmt=fmt, date_str=date_str,
        )

    def get_raw_json(
        self,
        source: str,
        series_id: str,
        date_str: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve raw JSON from the data lake."""
        return self._store.download_raw_json(source, series_id, date_str)

    # ------------------------------------------------------------------
    # Manifest / discovery
    # ------------------------------------------------------------------

    def get_manifest(
        self,
        source: Optional[str] = None,
        tier: str = DataTier.CLEANED,
    ) -> Dict[str, Dict[str, List[str]]]:
        """Build manifest of stored data.

        Returns:
            ``{source: {series_id: [date1, date2, …]}}``
        """
        names = [source] if source else self.list_sources()
        manifest: Dict[str, Dict[str, List[str]]] = {}
        for name in names:
            manifest[name] = self._store.get_source_manifest(name, tier=tier)
        return manifest

    def __repr__(self) -> str:
        return (
            f"DataPipeline(sources={len(self._sources)}, "
            f"store={self._store!r})"
        )
