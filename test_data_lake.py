"""Tests for Azure Blob Storage data lake and ingestion pipeline.

Covers:
  - BlobStore (local filesystem fallback)
  - DataPipeline (source registry, ingest, clean, retrieve)
  - Cleaning helpers
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch  # noqa: F401

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from grri_mac.data.blob_store import (
    BlobStore,
    DataTier,
    RAW_CONTAINER,
    CLEANED_CONTAINER,
    get_blob_store,
)
from grri_mac.data.pipeline import (
    BatchIngestResult,
    DataPipeline,
    IngestResult,
    SourceDescriptor,
    FRED_MAC_SERIES,
    NBER_SERIES_IDS,
    ETF_TICKERS,
    CBOE_INDICES,
    HISTORICAL_FILE_SERIES,
    CRYPTO_SYMBOLS,
    _clean_fred_series,
    _clean_time_series_csv,
    _clean_ohlcv,
    _clean_json_timeseries,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_sample_df(n: int = 50) -> pd.DataFrame:
    """Create a sample time-series DataFrame."""
    dates = pd.date_range("2020-01-01", periods=n, freq="W")
    values = np.random.default_rng(42).normal(0.5, 0.1, n)
    return pd.DataFrame({"value": values}, index=dates).rename_axis("date")


def _make_fred_json(n: int = 30) -> dict:
    """Create sample FRED-style {"dates": [...], "values": [...]}."""
    dates = pd.date_range("2022-01-01", periods=n, freq="ME")
    rng = np.random.default_rng(7)
    values = rng.normal(2.5, 0.3, n).tolist()
    # Inject a couple of NaN
    values[5] = None
    values[12] = None
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "values": values,
    }


class _TempDirMixin:
    """Mixin that creates a temp dir for each test and tears it down."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="mac_test_blob_")
        self._tmppath = Path(self._tmpdir)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# BlobStore — local fallback
# ══════════════════════════════════════════════════════════════════════════════

class TestBlobStoreInit(_TempDirMixin, unittest.TestCase):
    """BlobStore initialisation (no Azure connection)."""

    def test_defaults_to_local(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        self.assertFalse(store.connected)
        self.assertIn("Local", repr(store))

    def test_local_root_created(self):
        root = self._tmppath / "sub" / "lake"
        _store = BlobStore(  # noqa: F841
            connection_string=None,
            local_root=root,
        )
        self.assertTrue(root.exists())


class TestBlobPathHelpers(unittest.TestCase):
    """Static blob_path / metadata helpers."""

    def test_default_path(self):
        path = BlobStore.blob_path("fred", "VIXCLS", ".json", "2026-01-01")
        self.assertEqual(path, "fred/VIXCLS/2026-01-01.json")

    def test_parquet_extension(self):
        path = BlobStore.blob_path("nber", "m13001", ".parquet", "2025-06-15")
        self.assertEqual(path, "nber/m13001/2025-06-15.parquet")

    def test_default_date_is_today(self):
        path = BlobStore.blob_path("cboe", "VIX3M")
        today = datetime.utcnow().strftime("%Y-%m-%d")
        self.assertIn(today, path)


class TestBlobStoreRawBytes(_TempDirMixin, unittest.TestCase):
    """Upload / download raw bytes via local fallback."""

    def test_round_trip_json(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        payload = json.dumps({"hello": "world"}).encode()
        ok = store.upload_raw_bytes(
            "test", "s1", payload, ".json",
            date_str="2026-02-18",
        )
        self.assertTrue(ok)

        got = store.download_raw_bytes(
            "test", "s1", ".json",
            date_str="2026-02-18",
        )
        self.assertEqual(got, payload)

    def test_round_trip_csv(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        csv = b"date,value\n2020-01-01,1.5\n2020-01-08,2.0"
        store.upload_raw_bytes(
            "hist", "series1", csv, ".csv",
            date_str="2026-01-01",
        )
        got = store.download_raw_bytes(
            "hist", "series1", ".csv",
            date_str="2026-01-01",
        )
        self.assertEqual(got, csv)

    def test_missing_returns_none(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        self.assertIsNone(
            store.download_raw_bytes(
                "x", "y", ".json", "2000-01-01",
            )
        )


class TestBlobStoreRawJson(_TempDirMixin, unittest.TestCase):
    """upload_raw_json / download_raw_json convenience."""

    def test_json_round_trip(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        obj = {"dates": ["2020-01-01"], "values": [42.0]}
        store.upload_raw_json("fred", "DFF", obj, date_str="2026-02-18")
        got = store.download_raw_json("fred", "DFF", date_str="2026-02-18")
        self.assertEqual(got, obj)


class TestBlobStoreRawCsv(_TempDirMixin, unittest.TestCase):
    """upload_raw_csv with DataFrame."""

    def test_csv_upload(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        df = _make_sample_df(10)
        ok = store.upload_raw_csv("etf", "TLT", df, date_str="2026-02-18")
        self.assertTrue(ok)
        # Verify file exists on disk
        self.assertTrue(
            store.exists(
                "etf", "TLT",
                DataTier.RAW, ".csv", "2026-02-18",
            )
        )


class TestBlobStoreDataFrame(_TempDirMixin, unittest.TestCase):
    """Cleaned tier: upload / download DataFrame.

    CSV format — no pyarrow needed.
    """

    def test_round_trip_csv_format(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        df = _make_sample_df(20)
        ok = store.upload_dataframe(
            "fred", "VIX", df,
            fmt="csv", date_str="2026-02-18",
        )
        self.assertTrue(ok)

        got = store.download_dataframe(
            "fred", "VIX",
            fmt="csv", date_str="2026-02-18",
        )
        self.assertIsNotNone(got)
        self.assertEqual(len(got), 20)

    def test_missing_returns_none(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        self.assertIsNone(
            store.download_dataframe(
                "x", "y",
                fmt="csv", date_str="1999-01-01",
            )
        )


class TestBlobStoreExists(_TempDirMixin, unittest.TestCase):
    """Exists / delete."""

    def test_exists_false_initially(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        self.assertFalse(store.exists("fred", "VIXCLS"))

    def test_exists_after_upload(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        store.upload_raw_json(
            "fred", "VIXCLS", {"v": 1},
            date_str="2026-02-18",
        )
        self.assertTrue(
            store.exists(
                "fred", "VIXCLS",
                DataTier.RAW, ".json",
                "2026-02-18",
            )
        )

    def test_delete(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        store.upload_raw_json("x", "y", {"a": 1}, date_str="2026-02-18")
        self.assertTrue(
            store.delete(
                "x", "y",
                DataTier.RAW, ".json", "2026-02-18",
            )
        )
        self.assertFalse(
            store.exists(
                "x", "y",
                DataTier.RAW, ".json", "2026-02-18",
            )
        )


class TestBlobStoreListBlobs(_TempDirMixin, unittest.TestCase):
    """Listing and manifest."""

    def test_list_blobs(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        store.upload_raw_json("fred", "A", {"v": 1}, date_str="2026-01-01")
        store.upload_raw_json("fred", "B", {"v": 2}, date_str="2026-01-01")
        blobs = store.list_blobs(tier=DataTier.RAW, prefix="fred/")
        names = [b["name"] for b in blobs]
        self.assertEqual(len(names), 2)
        self.assertTrue(all("fred/" in n for n in names))

    def test_source_manifest(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        store.upload_dataframe(
            "fred", "DFF", _make_sample_df(5),
            fmt="csv", date_str="2026-01-01",
        )
        store.upload_dataframe(
            "fred", "DFF", _make_sample_df(5),
            fmt="csv", date_str="2026-01-02",
        )
        store.upload_dataframe(
            "fred", "VIX", _make_sample_df(5),
            fmt="csv", date_str="2026-01-01",
        )
        manifest = store.get_source_manifest("fred", tier=DataTier.CLEANED)
        self.assertIn("DFF", manifest)
        self.assertEqual(len(manifest["DFF"]), 2)
        self.assertIn("VIX", manifest)


# ══════════════════════════════════════════════════════════════════════════════
# Cleaning helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanFredSeries(unittest.TestCase):
    """_clean_fred_series helper."""

    def test_dict_input(self):
        raw = _make_fred_json(30)
        df = _clean_fred_series(raw, "TEST")
        # 2 of 30 were None → 28 rows
        self.assertEqual(len(df), 28)
        self.assertEqual(df.index.name, "date")
        self.assertEqual(list(df.columns), ["value"])

    def test_pandas_series_input(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="ME")
        raw = pd.Series(
            [1.0, 2.0, None, 4.0, 5.0,
             6.0, 7.0, 8.0, 9.0, 10.0],
            index=idx,
        )
        df = _clean_fred_series(raw, "X")
        self.assertEqual(len(df), 9)  # one NaN dropped

    def test_empty_dict(self):
        df = _clean_fred_series({}, "EMPTY")
        self.assertEqual(len(df), 0)


class TestCleanTimeSeriesCsv(unittest.TestCase):
    """_clean_time_series_csv helper."""

    def test_standard_csv(self):
        csv = b"date,value\n2020-01-01,1.5\n2020-01-08,2.0\n2020-01-15,3.5"
        df = _clean_time_series_csv(csv, "S1")
        self.assertEqual(len(df), 3)
        self.assertEqual(df.index.name, "date")

    def test_alternate_columns(self):
        csv = b"Date,Close\n2020-01-01,100\n2020-01-02,101"
        df = _clean_time_series_csv(csv, "S2")
        self.assertEqual(len(df), 2)

    def test_with_nan(self):
        csv = b"date,value\n2020-01-01,1.5\n2020-01-02,NA\n2020-01-03,3.0"
        df = _clean_time_series_csv(csv, "S3")
        self.assertEqual(len(df), 2)


class TestCleanOhlcv(unittest.TestCase):
    """_clean_ohlcv helper."""

    def test_standard_ohlcv(self):
        idx = pd.date_range("2020-01-01", periods=5, freq="D")
        raw = pd.DataFrame({
            "Open": [1, 2, 3, 4, 5],
            "High": [2, 3, 4, 5, 6],
            "Low": [0.5, 1.5, 2.5, 3.5, 4.5],
            "Close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "Volume": [100, 200, 300, 400, 500],
        }, index=idx)
        df = _clean_ohlcv(raw, "TLT")
        self.assertEqual(len(df), 5)
        self.assertIn("close", df.columns)

    def test_empty_input(self):
        df = _clean_ohlcv(pd.DataFrame(), "X")
        self.assertEqual(len(df), 0)

    def test_none_input(self):
        df = _clean_ohlcv(None, "X")
        self.assertEqual(len(df), 0)


class TestCleanJsonTimeseries(unittest.TestCase):
    """_clean_json_timeseries helper."""

    def test_dict_format(self):
        raw = {"dates": ["2020-01-01", "2020-02-01"], "values": [10.0, 20.0]}
        df = _clean_json_timeseries(raw, "OFR")
        self.assertEqual(len(df), 2)

    def test_list_format(self):
        raw = [
            {"date": "2020-01-01", "value": 1.0},
            {"date": "2020-02-01", "value": 2.0},
        ]
        df = _clean_json_timeseries(raw, "BIS")
        self.assertEqual(len(df), 2)


# ══════════════════════════════════════════════════════════════════════════════
# IngestResult / BatchIngestResult dataclasses
# ══════════════════════════════════════════════════════════════════════════════

class TestIngestResult(unittest.TestCase):

    def test_ok_when_no_error_and_stored(self):
        r = IngestResult(source="fred", series_id="VIX", cleaned_stored=True)
        self.assertTrue(r.ok)

    def test_not_ok_on_error(self):
        r = IngestResult(source="fred", series_id="VIX", error="timeout")
        self.assertFalse(r.ok)

    def test_not_ok_when_not_stored(self):
        r = IngestResult(source="fred", series_id="VIX", cleaned_stored=False)
        self.assertFalse(r.ok)


class TestBatchIngestResult(unittest.TestCase):

    def test_summary(self):
        batch = BatchIngestResult(source="fred")
        batch.results = [
            IngestResult(source="fred", series_id="A", cleaned_stored=True),
            IngestResult(source="fred", series_id="B", error="fail"),
        ]
        self.assertEqual(batch.total, 2)
        self.assertEqual(batch.succeeded, 1)
        self.assertEqual(batch.failed, 1)
        self.assertIn("1/2", batch.summary())


# ══════════════════════════════════════════════════════════════════════════════
# DataPipeline — registration & listing
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineRegistration(_TempDirMixin, unittest.TestCase):
    """Pipeline source registration and listing."""

    def _make_pipeline(self) -> DataPipeline:
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        return DataPipeline(store=store)

    def test_builtins_registered(self):
        p = self._make_pipeline()
        names = p.list_sources()
        expected_sources = (
            "fred", "nber", "cboe", "etf",
            "crypto", "bis", "ofr", "cftc",
            "crypto_oi", "historical",
        )
        for expected in expected_sources:
            self.assertIn(
                expected, names,
                f"Missing built-in source: {expected}",
            )

    def test_fred_series_list(self):
        p = self._make_pipeline()
        series = p.list_series("fred")
        self.assertIn("VIXCLS", series)
        self.assertIn("BAA10Y", series)
        self.assertEqual(len(series), len(FRED_MAC_SERIES))

    def test_nber_series_list(self):
        p = self._make_pipeline()
        series = p.list_series("nber")
        self.assertEqual(len(series), len(NBER_SERIES_IDS))

    def test_custom_source_registration(self):
        p = self._make_pipeline()
        desc = SourceDescriptor(
            name="custom",
            series_ids=["A", "B"],
            fetch=lambda c, s: {"dates": [], "values": []},
            clean=_clean_fred_series,
            client_factory=lambda: None,
        )
        p.register_source(desc)
        self.assertIn("custom", p.list_sources())
        self.assertEqual(p.list_series("custom"), ["A", "B"])

    def test_unknown_source_raises(self):
        p = self._make_pipeline()
        with self.assertRaises(ValueError):
            p.ingest("nonexistent_source")

    def test_repr(self):
        p = self._make_pipeline()
        r = repr(p)
        self.assertIn("DataPipeline", r)
        self.assertIn("sources=", r)


# ══════════════════════════════════════════════════════════════════════════════
# DataPipeline — ingest with mock sources
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineIngest(_TempDirMixin, unittest.TestCase):
    """End-to-end ingest using a custom source (no real network calls)."""

    def _make_pipeline_with_mock_source(self) -> DataPipeline:
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        p = DataPipeline(store=store)

        # Register a deterministic mock source
        def mock_fetch(_client, sid):
            return {
                "dates": ["2025-01-01", "2025-02-01", "2025-03-01"],
                "values": [1.0, 2.0, 3.0],
            }

        p.register_source(SourceDescriptor(
            name="mock",
            series_ids=["S1", "S2"],
            fetch=mock_fetch,
            clean=_clean_fred_series,
            client_factory=lambda: None,
            raw_ext=".json",
            description="Mock source for testing",
        ))
        return p

    def test_ingest_single_series(self):
        p = self._make_pipeline_with_mock_source()
        result = p.ingest(
            "mock", series_ids=["S1"],
            date_str="2026-02-18",
            cleaned_fmt="csv",
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.succeeded, 1)
        self.assertEqual(result.results[0].cleaned_rows, 3)

    def test_ingest_all_series_in_source(self):
        p = self._make_pipeline_with_mock_source()
        result = p.ingest("mock", date_str="2026-02-18", cleaned_fmt="csv")
        self.assertEqual(result.total, 2)
        self.assertEqual(result.succeeded, 2)

    def test_ingest_stores_raw_and_cleaned(self):
        p = self._make_pipeline_with_mock_source()
        p.ingest("mock", series_ids=["S1"], date_str="2026-02-18", cleaned_fmt="csv")

        # Raw stored
        raw = p._store.download_raw_json("mock", "S1", date_str="2026-02-18")
        self.assertIsNotNone(raw)
        self.assertEqual(raw["values"], [1.0, 2.0, 3.0])

        # Cleaned stored
        df = p.get_cleaned("mock", "S1", fmt="csv", date_str="2026-02-18")
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)

    def test_skip_existing(self):
        p = self._make_pipeline_with_mock_source()
        p.ingest("mock", series_ids=["S1"], date_str="2026-02-18", cleaned_fmt="csv")

        # Second ingest with skip_existing should still succeed
        result = p.ingest(
            "mock", series_ids=["S1"], date_str="2026-02-18",
            skip_existing=True, cleaned_fmt="csv",
        )
        self.assertEqual(result.succeeded, 1)

    def test_fetch_error_recorded(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        p = DataPipeline(store=store)

        def failing_fetch(_c, _s):
            raise ConnectionError("network down")

        p.register_source(SourceDescriptor(
            name="bad",
            series_ids=["X"],
            fetch=failing_fetch,
            clean=_clean_fred_series,
            client_factory=lambda: None,
        ))
        result = p.ingest("bad", series_ids=["X"], date_str="2026-02-18")
        self.assertEqual(result.failed, 1)
        self.assertIn("Fetch error", result.results[0].error)


class TestPipelineIngestAll(_TempDirMixin, unittest.TestCase):
    """ingest_all with subset of sources."""

    def test_ingest_all_subset(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        p = DataPipeline(store=store)

        def ok_fetch(_c, sid):
            return {"dates": ["2025-01-01"], "values": [99.0]}

        for name in ("src_a", "src_b", "src_c"):
            p.register_source(SourceDescriptor(
                name=name, series_ids=["x"],
                fetch=ok_fetch, clean=_clean_fred_series,
                client_factory=lambda: None,
            ))

        results = p.ingest_all(
            sources=["src_a", "src_c"],
            date_str="2026-02-18",
            cleaned_fmt="csv",
        )
        self.assertIn("src_a", results)
        self.assertIn("src_c", results)
        self.assertNotIn("src_b", results)


class TestPipelineManifest(_TempDirMixin, unittest.TestCase):
    """get_manifest discovery."""

    def test_manifest_after_ingest(self):
        store = BlobStore(connection_string=None, local_root=self._tmppath)
        p = DataPipeline(store=store)

        p.register_source(SourceDescriptor(
            name="m", series_ids=["A"],
            fetch=lambda c, s: {"dates": ["2025-01-01"], "values": [1]},
            clean=_clean_fred_series,
            client_factory=lambda: None,
        ))
        p.ingest("m", date_str="2026-02-18", cleaned_fmt="csv")
        manifest = p.get_manifest("m")
        self.assertIn("m", manifest)
        self.assertIn("A", manifest["m"])


# ══════════════════════════════════════════════════════════════════════════════
# Constants / registry checks
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryConstants(unittest.TestCase):
    """Verify the source registry constants are sane."""

    def test_fred_series_count(self):
        self.assertGreater(len(FRED_MAC_SERIES), 25)

    def test_nber_series_count(self):
        self.assertGreater(len(NBER_SERIES_IDS), 10)

    def test_etf_tickers_count(self):
        self.assertGreater(len(ETF_TICKERS), 10)

    def test_cboe_indices(self):
        self.assertEqual(set(CBOE_INDICES), {"VIX9D", "VIX3M", "VVIX"})

    def test_historical_file_series(self):
        self.assertIn("SCHWERT_VOL", HISTORICAL_FILE_SERIES)
        self.assertIn("BOE_BANKRATE", HISTORICAL_FILE_SERIES)

    def test_crypto_symbols(self):
        self.assertIn("BTC-USD", CRYPTO_SYMBOLS)


class TestDataTierConstants(unittest.TestCase):
    """DataTier and container names."""

    def test_raw_tier(self):
        self.assertEqual(DataTier.RAW, "raw")

    def test_cleaned_tier(self):
        self.assertEqual(DataTier.CLEANED, "cleaned")

    def test_container_names(self):
        self.assertEqual(RAW_CONTAINER, "mac-raw-data")
        self.assertEqual(CLEANED_CONTAINER, "mac-cleaned-data")


# ══════════════════════════════════════════════════════════════════════════════
# BlobStore singleton
# ══════════════════════════════════════════════════════════════════════════════

class TestGetBlobStore(unittest.TestCase):
    """Module-level singleton accessor."""

    def test_returns_blob_store(self):
        # Reset singleton for test isolation
        import grri_mac.data.blob_store as mod
        mod._store = None
        store = get_blob_store()
        self.assertIsInstance(store, BlobStore)
        # Second call returns same instance
        self.assertIs(get_blob_store(), store)
        mod._store = None  # cleanup


if __name__ == "__main__":
    unittest.main()
