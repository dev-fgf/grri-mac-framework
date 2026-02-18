"""
Upload all local data to Azure.

Blob Storage (raw + cleaned) AND Table Storage.

This is the single entry point for seeding Azure
with everything we have locally:

  Blob Storage (mac-raw-data):
    Raw source files exactly as downloaded — CSVs, XLS/XLSX, JSON, pickle

  Blob Storage (mac-cleaned-data):
    Standardised Parquet DataFrames — date-indexed, NaN-dropped, typed

  Table Storage (existing tables):
    Queryable series via the MACDatabase API (fredseries, backtesthistory, …)

Usage:
    python upload_to_blob.py                          # Upload everything
    python upload_to_blob.py --raw-only               # Only raw files → Blob
    python upload_to_blob.py --cleaned-only   # Cleaned
    python upload_to_blob.py --table-only      # Table Storage
    python upload_to_blob.py --dry-run                 # Preview only
    python upload_to_blob.py --verify                  # Check what's in Azure
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from grri_mac.data.blob_store import (  # noqa: E402
    BlobStore, DataTier,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
FRED_CACHE = DATA_DIR / "fred_cache" / "fred_series_cache.pkl"
HISTORICAL_DIR = DATA_DIR / "historical"
BACKTEST_DIR = DATA_DIR / "backtest_results"

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────────────────────
# Registry: every local file we know about
# ─────────────────────────────────────────────────────────────────────────────

# NBER series: (csv filename without ext, date_col, value_col, description)
NBER_SERIES: Dict[str, Tuple[str, str, str]] = {
    "m13001": ("date", "value", "Call Money Rate NYC"),
    "m13002": ("date", "value", "Commercial Paper Rate NYC"),
    "m13009": ("date", "value", "Fed Discount Rate NY"),
    "m13019": ("date", "value", "Railroad Bond Yield High Grade"),
    "m13020": ("date", "value", "Railroad Bond Yield Low Grade"),
    "m13022": ("date", "value", "Railroad Bond Yield 2nd Grade"),
    "m13024": ("date", "value", "High Grade Railroad Bonds"),
    "m13026": ("date", "value", "Industrial Bonds Aaa"),
    "m13028": ("date", "value", "Industrial Bonds Baa"),
    "m13029a": ("date", "value", "Corporate Bond Yield Seasoned"),
    "m13033": ("date", "value", "Long-Term US Govt Bond Yield"),
    "m13033a": ("date", "value", "US Govt Bond Yield Short-Term"),
    "m13033b": ("date", "value", "US Govt Bond Yield Medium-Term"),
    "m13034": ("date", "value", "Treasury Bill Rate"),
    "m13035": ("date", "value", "Corporate Bonds Highest Rating"),
    "m13036": ("date", "value", "Corporate Bonds Lowest Rating"),
    "m13039": ("date", "value", "Stock Prices General"),
    "m13041": ("date", "value", "Stock Prices Industrial"),
    "m14076": ("date", "value", "US Monetary Gold Stock"),
    "m14076a": ("date", "value", "US Gold Stock Sub-series A"),
    "m14076b": ("date", "value", "US Gold Stock Sub-series B"),
    "m14076c": ("date", "value", "US Gold Stock Sub-series C"),
}

# Other historical CSVs:
# (source, series_id, rel_path, date_col, value_col, desc)
OTHER_HISTORICAL = [
    (
        "schwert", "volatility",
        "schwert/schwert_volatility.csv",
        "date", "volatility",
        "Schwert Realized Volatility",
    ),
    (
        "boe", "gbpusd",
        "boe/boe_gbpusd.csv",
        "date", "rate",
        "GBP/USD Exchange Rate",
    ),
    (
        "boe", "bankrate",
        "boe/boe_bankrate.csv",
        "date", "rate",
        "BoE Official Bank Rate",
    ),
    (
        "measuringworth", "us_gdp",
        "measuringworth/us_gdp.csv",
        "year", "gdp",
        "US Nominal GDP",
    ),
    (
        "finra", "margin_debt",
        "finra/margin_debt.csv",
        "date", "margin_debt",
        "NYSE Margin Debt",
    ),
]

# Large raw-only files (not easily converted to clean time series)
RAW_BINARY_FILES = [
    (
        "boe", "millennium",
        "boe/boe_millennium.xlsx",
        ".xlsx", "BoE Millennium Dataset",
    ),
    (
        "shiller", "ie_data",
        "shiller/ie_data.xls",
        ".xls", "Shiller Irrational Exuberance",
    ),
]

# Root-level data files
ROOT_DATA_FILES = [
    (
        "gpr", "gpr_data",
        "gpr_data.xls", ".xls",
        "Geopolitical Risk Index",
    ),
    (
        "reference", "competitor_indices",
        "competitor_indices.json", ".json",
        "Competitor Indices",
    ),
    (
        "reference", "grs_data_sources",
        "grs_data_sources.json", ".json",
        "GRS Data Sources",
    ),
    (
        "reference", "private_credit_analysis",
        "private_credit_analysis.json", ".json",
        "Private Credit Analysis",
    ),
    (
        "reference", "historical_indicators",
        "historical_indicators.json", ".json",
        "Historical Indicators",
    ),
    (
        "reference", "historical_mac_results",
        "historical_mac_results.json", ".json",
        "Historical MAC Results",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  \u2713 {msg}")


def _skip(msg: str) -> None:
    print(f"  - {msg}")


def _fail(msg: str) -> None:
    print(f"  \u2717 {msg}")


def _dry(msg: str) -> None:
    print(f"  [DRY] {msg}")


def _clean_series(dates, values) -> Optional[pd.DataFrame]:
    """Convert parallel date/value lists into a clean DataFrame."""
    try:
        idx = pd.to_datetime(dates, errors="coerce")
        sr = pd.Series(values, index=idx, name="value", dtype=float)
        sr = sr.dropna()
        if sr.empty:
            return None
        df = sr.to_frame()
        df.index.name = "date"
        return df.sort_index()
    except Exception:
        return None


def _read_historical_csv(
    path: Path, date_col: str, val_col: str,
) -> Optional[pd.DataFrame]:
    """Read a historical CSV into a clean DataFrame."""
    if not path.exists():
        return None
    df = pd.read_csv(path)
    # Handle year-only columns (e.g. MeasuringWorth GDP)
    if date_col == "year" and "year" in df.columns:
        df["date"] = df["year"].astype(str) + "-01-01"
        date_col = "date"
    if date_col not in df.columns or val_col not in df.columns:
        return None
    return _clean_series(df[date_col].values, df[val_col].values)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. RAW TIER — upload source files as-received
# ═══════════════════════════════════════════════════════════════════════════════

def upload_raw(store: BlobStore, dry_run: bool = False) -> int:
    """Upload every local data file to the raw Blob Storage tier."""
    total = 0

    # ── 1a. FRED series (from pickle → individual JSON blobs) ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: FRED series (pickle → JSON)")
    print(f"{'=' * 60}")
    if FRED_CACHE.exists():
        with open(FRED_CACHE, "rb") as f:
            cache = pickle.load(f)
        for sid, data in sorted(cache.items()):
            if not isinstance(data, pd.Series) or len(data) == 0:
                continue
            obj = {
                "dates": [
                    d.strftime("%Y-%m-%d")
                    if hasattr(d, "strftime")
                    else str(d)
                    for d in data.index
                ],
                "values": [
                    None if (
                        v is None
                        or (isinstance(v, float)
                            and np.isnan(v))
                    ) else float(v)
                    for v in data.values
                ],
            }
            if dry_run:
                _dry(f"fred/{sid}: {len(data)} pts")
            else:
                ok = store.upload_raw_json("fred", sid, obj, date_str=TODAY)
                (_ok if ok else _fail)(f"fred/{sid}: {len(data)} pts")
            total += 1
        # Also upload the raw pickle itself
        if not dry_run:
            ok = store.upload_raw_bytes(
                "fred", "_cache_pickle",
                FRED_CACHE.read_bytes(),
                ".pkl", date_str=TODAY,
            )
            (_ok if ok else _fail)("fred/_cache_pickle (raw pickle)")
        else:
            _dry("fred/_cache_pickle (raw pickle)")
        total += 1
    else:
        _skip("FRED cache not found")

    # ── 1b. NBER CSVs ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: NBER historical CSVs")
    print(f"{'=' * 60}")
    for sid, (date_col, val_col, desc) in NBER_SERIES.items():
        csv_path = HISTORICAL_DIR / "nber" / f"{sid}.csv"
        if not csv_path.exists():
            _skip(f"nber/{sid}: file not found")
            continue
        raw_bytes = csv_path.read_bytes()
        if dry_run:
            _dry(f"nber/{sid}: {len(raw_bytes)} bytes — {desc}")
        else:
            ok = store.upload_raw_bytes(
                "nber", sid, raw_bytes,
                ".csv", date_str=TODAY,
            )
            msg = (
                f"nber/{sid}: {len(raw_bytes)}"
                f" bytes — {desc}"
            )
            (_ok if ok else _fail)(msg)
        total += 1

    # ── 1c. Other historical CSVs ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: Other historical CSVs")
    print(f"{'=' * 60}")
    for source, sid, rel_path, date_col, val_col, desc in OTHER_HISTORICAL:
        csv_path = HISTORICAL_DIR / rel_path
        if not csv_path.exists():
            _skip(f"{source}/{sid}: file not found")
            continue
        raw_bytes = csv_path.read_bytes()
        if dry_run:
            _dry(f"{source}/{sid}: {len(raw_bytes)} bytes — {desc}")
        else:
            ok = store.upload_raw_bytes(
                source, sid, raw_bytes,
                ".csv", date_str=TODAY,
            )
            msg = (
                f"{source}/{sid}: "
                f"{len(raw_bytes)} bytes — {desc}"
            )
            (_ok if ok else _fail)(msg)
        total += 1

    # ── 1d. Large binary files (xlsx, xls) from historical/ ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: Large binary files")
    print(f"{'=' * 60}")
    for source, sid, rel_path, ext, desc in RAW_BINARY_FILES:
        file_path = HISTORICAL_DIR / rel_path
        if not file_path.exists():
            _skip(f"{source}/{sid}: file not found")
            continue
        file_bytes = file_path.read_bytes()
        sz_mb = len(file_bytes) / (1024 * 1024)
        if dry_run:
            _dry(f"{source}/{sid}: {sz_mb:.1f} MB — {desc}")
        else:
            ok = store.upload_raw_bytes(
                source, sid, file_bytes,
                ext, date_str=TODAY,
            )
            msg = (
                f"{source}/{sid}: "
                f"{sz_mb:.1f} MB — {desc}"
            )
            (_ok if ok else _fail)(msg)
        total += 1

    # ── 1e. Root-level data files ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: Root data files (GPR, reference JSON)")
    print(f"{'=' * 60}")
    for source, sid, filename, ext, desc in ROOT_DATA_FILES:
        file_path = DATA_DIR / filename
        if not file_path.exists():
            _skip(f"{source}/{sid}: file not found")
            continue
        file_bytes = file_path.read_bytes()
        sz_kb = len(file_bytes) / 1024
        if dry_run:
            _dry(f"{source}/{sid}: {sz_kb:.1f} KB — {desc}")
        else:
            ok = store.upload_raw_bytes(
                source, sid, file_bytes,
                ext, date_str=TODAY,
            )
            msg = (
                f"{source}/{sid}: "
                f"{sz_kb:.1f} KB — {desc}"
            )
            (_ok if ok else _fail)(msg)
        total += 1

    # ── 1f. Backtest results ──
    print(f"\n{'=' * 60}")
    print("RAW TIER: Backtest results")
    print(f"{'=' * 60}")
    if BACKTEST_DIR.exists():
        for fp in sorted(BACKTEST_DIR.iterdir()):
            if not fp.is_file():
                continue
            ext = fp.suffix
            sid = fp.stem
            file_bytes = fp.read_bytes()
            sz_kb = len(file_bytes) / 1024
            if dry_run:
                _dry(f"backtest/{sid}: {sz_kb:.1f} KB")
            else:
                ok = store.upload_raw_bytes(
                    "backtest", sid, file_bytes,
                    ext, date_str=TODAY,
                )
                (_ok if ok else _fail)(f"backtest/{sid}: {sz_kb:.1f} KB")
            total += 1
    else:
        _skip("Backtest directory not found")

    return total


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CLEANED TIER — standardised Parquet DataFrames
# ═══════════════════════════════════════════════════════════════════════════════

def upload_cleaned(store: BlobStore, dry_run: bool = False) -> int:
    """Upload cleaned Parquet DataFrames to the cleaned Blob Storage tier."""
    total = 0

    # ── 2a. FRED series → Parquet ──
    print(f"\n{'=' * 60}")
    print("CLEANED TIER: FRED series (Parquet)")
    print(f"{'=' * 60}")
    if FRED_CACHE.exists():
        with open(FRED_CACHE, "rb") as f:
            cache = pickle.load(f)
        for sid, data in sorted(cache.items()):
            if not isinstance(data, pd.Series) or len(data) == 0:
                continue
            df = _clean_series(
                [
                    d.strftime("%Y-%m-%d")
                    if hasattr(d, "strftime")
                    else str(d)
                    for d in data.index
                ],
                [
                    None if (
                        v is None
                        or (isinstance(v, float)
                            and np.isnan(v))
                    ) else float(v)
                    for v in data.values
                ],
            )
            if df is None or df.empty:
                _skip(f"fred/{sid}: no valid data after cleaning")
                continue
            if dry_run:
                rng = (
                    f"{df.index.min().date()}"
                    f" \u2192 {df.index.max().date()}"
                )
                _dry(
                    f"fred/{sid}: {len(df)}"
                    f" rows ({rng})"
                )
            else:
                ok = store.upload_dataframe("fred", sid, df, date_str=TODAY)
                rng = f"({df.index.min().date()} → {df.index.max().date()})"
                (_ok if ok else _fail)(f"fred/{sid}: {len(df)} rows {rng}")
            total += 1
    else:
        _skip("FRED cache not found")

    # ── 2b. NBER series → Parquet ──
    print(f"\n{'=' * 60}")
    print("CLEANED TIER: NBER series (Parquet)")
    print(f"{'=' * 60}")
    for sid, (date_col, val_col, desc) in NBER_SERIES.items():
        csv_path = HISTORICAL_DIR / "nber" / f"{sid}.csv"
        df = _read_historical_csv(csv_path, date_col, val_col)
        if df is None:
            _skip(f"nber/{sid}: no valid data — {desc}")
            continue
        if dry_run:
            _dry(f"nber/{sid}: {len(df)} rows — {desc}")
        else:
            ok = store.upload_dataframe("nber", sid, df, date_str=TODAY)
            (_ok if ok else _fail)(f"nber/{sid}: {len(df)} rows — {desc}")
        total += 1

    # ── 2c. Other historical CSVs → Parquet ──
    print(f"\n{'=' * 60}")
    print("CLEANED TIER: Other historical series (Parquet)")
    print(f"{'=' * 60}")
    for source, sid, rel_path, date_col, val_col, desc in OTHER_HISTORICAL:
        csv_path = HISTORICAL_DIR / rel_path
        df = _read_historical_csv(csv_path, date_col, val_col)
        if df is None:
            _skip(f"{source}/{sid}: no valid data — {desc}")
            continue
        if dry_run:
            _dry(f"{source}/{sid}: {len(df)} rows — {desc}")
        else:
            ok = store.upload_dataframe(source, sid, df, date_str=TODAY)
            (_ok if ok else _fail)(f"{source}/{sid}: {len(df)} rows — {desc}")
        total += 1

    # ── 2d. Backtest CSVs → Parquet ──
    print(f"\n{'=' * 60}")
    print("CLEANED TIER: Backtest results (Parquet)")
    print(f"{'=' * 60}")
    for csv_name in ["backtest_full_1971_2025", "backtest_improved"]:
        csv_path = BACKTEST_DIR / f"{csv_name}.csv"
        if not csv_path.exists():
            _skip(f"backtest/{csv_name}: file not found")
            continue
        df = pd.read_csv(csv_path)
        # Try to set date index
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).set_index("date").sort_index()
        if dry_run:
            _dry(f"backtest/{csv_name}: {len(df)} rows")
        else:
            ok = store.upload_dataframe(
                "backtest", csv_name, df,
                date_str=TODAY,
            )
            (_ok if ok else _fail)(f"backtest/{csv_name}: {len(df)} rows")
        total += 1

    # ── 2e. SQLite indicator_values → Parquet ──
    print(f"\n{'=' * 60}")
    print("CLEANED TIER: SQLite indicator_values (Parquet)")
    print(f"{'=' * 60}")
    db_path = DATA_DIR / "mac.db"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query(
            "SELECT timestamp, indicator_name,"
            " value, source, series_id"
            " FROM indicator_values"
            " ORDER BY timestamp",
            conn,
        )
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(
                subset=["timestamp"]
            ).set_index("timestamp").sort_index()
            if dry_run:
                _dry(f"sqlite/indicator_values: {len(df)} rows")
            else:
                ok = store.upload_dataframe(
                    "sqlite", "indicator_values",
                    df, date_str=TODAY,
                )
                msg = (
                    "sqlite/indicator_values:"
                    f" {len(df)} rows"
                )
                (_ok if ok else _fail)(msg)
            total += 1
        else:
            _skip("sqlite/indicator_values: empty table")
    else:
        _skip("mac.db not found")

    return total


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TABLE STORAGE — queryable via MACDatabase API
# ═══════════════════════════════════════════════════════════════════════════════

def upload_table_storage(dry_run: bool = False) -> int:
    """Upload series to Azure Table Storage via MACDatabase.

    Covers everything the original upload_all_to_azure.py did, plus
    the NBER series it was missing.
    """
    from shared.database import get_database  # type: ignore

    db = get_database()
    if not db.connected and not dry_run:
        print("  Table Storage not connected — skipping")
        return 0

    total = 0

    def _series_to_upload(dates, values):
        clean_d, clean_v = [], []
        for d, v in zip(dates, values):
            d_str = (
                d.strftime("%Y-%m-%d")
                if hasattr(d, "strftime")
                else str(d)
            )
            clean_d.append(d_str)
            is_nan = (
                v is None
                or (isinstance(v, float)
                    and np.isnan(v))
            )
            clean_v.append(
                None if is_nan else float(v)
            )
        return {"dates": clean_d, "values": clean_v}

    # ── 3a. FRED series ──
    print(f"\n{'=' * 60}")
    print("TABLE STORAGE: FRED series → fredseries table")
    print(f"{'=' * 60}")
    if FRED_CACHE.exists():
        with open(FRED_CACHE, "rb") as f:
            cache = pickle.load(f)
        for sid, data in sorted(cache.items()):
            if not isinstance(data, pd.Series) or len(data) == 0:
                continue
            upload = _series_to_upload(data.index, data.values)
            start = data.index.min().strftime("%Y-%m-%d")
            end = data.index.max().strftime("%Y-%m-%d")
            if dry_run:
                _dry(f"{sid}: {len(data)} pts ({start} → {end})")
            else:
                ok = db.save_fred_series(sid, upload)
                (_ok if ok else _fail)(f"{sid}: {len(data)} pts ({start} → {end})")
            total += 1

    # ── 3b. ALL NBER CSVs (expanded set) ──
    print(f"\n{'=' * 60}")
    print("TABLE STORAGE: NBER + historical CSVs → fredseries table")
    print(f"{'=' * 60}")
    # NBER
    for sid, (date_col, val_col, desc) in NBER_SERIES.items():
        csv_path = HISTORICAL_DIR / "nber" / f"{sid}.csv"
        if not csv_path.exists():
            _skip(f"NBER_{sid}: file not found")
            continue
        df = pd.read_csv(csv_path)
        if date_col not in df.columns or val_col not in df.columns:
            _skip(f"NBER_{sid}: missing columns")
            continue
        upload = _series_to_upload(df[date_col].values, df[val_col].values)
        non_null = sum(1 for v in upload["values"] if v is not None)
        series_key = f"NBER_{sid.upper()}"
        if dry_run:
            _dry(f"{series_key}: {non_null} pts — {desc}")
        else:
            ok = db.save_fred_series(series_key, upload)
            (_ok if ok else _fail)(f"{series_key}: {non_null} pts — {desc}")
        total += 1

    # Other historical
    TABLE_HISTORICAL = {
        "SCHWERT_VOL": (
            "schwert/schwert_volatility.csv",
            "date", "volatility",
            "Schwert Realized Volatility",
        ),
        "BOE_GBPUSD": (
            "boe/boe_gbpusd.csv",
            "date", "rate",
            "GBP/USD Exchange Rate",
        ),
        "BOE_BANKRATE": (
            "boe/boe_bankrate.csv",
            "date", "rate",
            "BoE Official Bank Rate",
        ),
        "MW_GDP": (
            "measuringworth/us_gdp.csv",
            "year", "gdp",
            "US Nominal GDP",
        ),
        "FINRA_MARGIN_DEBT": (
            "finra/margin_debt.csv",
            "date", "margin_debt",
            "NYSE Margin Debt",
        ),
    }
    for series_key, (rel_path, date_col, val_col, desc) in TABLE_HISTORICAL.items():
        csv_path = HISTORICAL_DIR / rel_path
        if not csv_path.exists():
            _skip(f"{series_key}: file not found")
            continue
        df = pd.read_csv(csv_path)
        if date_col == "year" and "year" in df.columns:
            df["date"] = df["year"].astype(str) + "-01-01"
            date_col = "date"
        if date_col not in df.columns or val_col not in df.columns:
            _skip(f"{series_key}: missing columns")
            continue
        upload = _series_to_upload(df[date_col].values, df[val_col].values)
        non_null = sum(1 for v in upload["values"] if v is not None)
        if dry_run:
            _dry(f"{series_key}: {non_null} pts — {desc}")
        else:
            ok = db.save_fred_series(series_key, upload)
            (_ok if ok else _fail)(f"{series_key}: {non_null} pts — {desc}")
        total += 1

    # ── 3c. Backtest results ──
    print(f"\n{'=' * 60}")
    print("TABLE STORAGE: Backtest results → backtesthistory table")
    print(f"{'=' * 60}")
    backtest_csv = BACKTEST_DIR / "backtest_full_1971_2025.csv"
    if backtest_csv.exists():
        df = pd.read_csv(backtest_csv)
        if dry_run:
            rng = (
                f"{df['date'].min()}"
                f" \u2192 {df['date'].max()}"
            )
            _dry(
                f"backtest: {len(df)}"
                f" records ({rng})"
            )
            total += len(df)
        else:
            results = df.to_dict("records")
            batch_size = 100
            uploaded = 0
            for i in range(0, len(results), batch_size):
                batch = results[i:i + batch_size]
                saved = db.save_backtest_results_batch(batch)
                uploaded += saved
            _ok(f"backtest: {uploaded}/{len(df)} records")
            total += uploaded

            # Also save the chunked cache for the API
            _upload_backtest_cache(db, df)
    else:
        _skip("backtest_full_1971_2025.csv not found")

    return total


def _upload_backtest_cache(db, df: pd.DataFrame) -> None:
    """Build and upload the pre-computed backtest API cache."""
    time_series = []
    for _, row in df.iterrows():
        point = {
            "date": row["date"],
            "mac_score": row["mac_score"],
            "pillar_scores": {
                "liquidity": row.get("liquidity", 0),
                "valuation": row.get("valuation", 0),
                "positioning": row.get("positioning", 0),
                "volatility": row.get("volatility", 0),
                "policy": row.get("policy", 0),
                "contagion": row.get("contagion", 0),
                "private_credit": row.get("private_credit", 0),
            },
            "interpretation": row.get("interpretation", ""),
            "crisis_event": row.get("crisis_event", ""),
            "data_quality": row.get("data_quality", ""),
        }
        time_series.append(point)

    validation_path = BACKTEST_DIR / "backtest_full_1971_2025.validation.json"
    validation = {}
    if validation_path.exists():
        try:
            validation = json.loads(validation_path.read_text())
        except Exception:
            pass

    backtest_response = {
        "status": "success",
        "data_source": "Pre-computed (Azure Table Cache)",
        "parameters": {
            "start_date": df["date"].min(),
            "end_date": df["date"].max(),
            "data_points": len(df),
        },
        "statistics": {
            "min_mac": float(df["mac_score"].min()),
            "max_mac": float(df["mac_score"].max()),
            "mean_mac": float(df["mac_score"].mean()),
            "std_mac": float(df["mac_score"].std()),
        },
        "crisis_detection": validation.get("crisis_detection", {}),
        "time_series": time_series,
    }

    if db.save_backtest_cache_chunked(backtest_response):
        _ok("Backtest API cache saved")
    else:
        _fail("Backtest API cache FAILED")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Verify
# ═══════════════════════════════════════════════════════════════════════════════

def verify_blob(store: BlobStore) -> None:
    """Report what's in Blob Storage."""
    print(f"\n{'=' * 60}")
    print(f"BLOB STORAGE: {'Azure' if store.connected else 'Local'}")
    print(f"{'=' * 60}")

    for tier in (DataTier.RAW, DataTier.CLEANED):
        blobs = store.list_blobs(tier=tier)
        total_size = sum(b.get("size", 0) for b in blobs)

        # Group by source
        sources: Dict[str, int] = {}
        for b in blobs:
            src = b["name"].split("/")[0] if "/" in b["name"] else "root"
            sources[src] = sources.get(src, 0) + 1

        tier_label = "mac-raw-data" if tier == DataTier.RAW else "mac-cleaned-data"
        print(f"\n  {tier_label}: {len(blobs)} blobs ({total_size / 1024:.1f} KB)")
        for src, count in sorted(sources.items()):
            print(f"    {src}: {count} blobs")


def verify_table() -> None:
    """Report what's in Table Storage."""
    from shared.database import get_database  # type: ignore
    db = get_database()

    print(f"\n{'=' * 60}")
    print("TABLE STORAGE")
    print(f"{'=' * 60}")
    if not db.connected:
        print("  Not connected")
        return

    fred_count = db.get_fred_series_count()
    print(f"  FRED/Historical series: {fred_count}")
    if fred_count > 0:
        series_list = db.list_fred_series()
        for s in series_list[:10]:
            sid = s['series_id']
            pts = s['total_points']
            start = s['start_date']
            end = s['end_date']
            print(
                f"    {sid:25s}"
                f" {pts:>6d} pts"
                f"  ({start} \u2192 {end})"
            )
        if len(series_list) > 10:
            print(f"    ... and {len(series_list) - 10} more")

    backtest_count = db.get_backtest_count()
    print(f"  Backtest records: {backtest_count}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload all local data to Azure (Blob Storage + Table Storage)"
    )
    parser.add_argument(
        "--raw-only", action="store_true",
        help="Only raw files -> Blob Storage",
    )
    parser.add_argument(
        "--cleaned-only", action="store_true",
        help="Only cleaned Parquet -> Blob Storage",
    )
    parser.add_argument(
        "--table-only", action="store_true",
        help="Only Table Storage (series + backtest)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview only, no uploads",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Report current Azure contents",
    )
    args = parser.parse_args()

    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    print("=" * 60)
    print("UPLOAD ALL DATA TO AZURE")
    print("=" * 60)
    print(f"  Azure connection: {'Set' if conn_str else 'NOT SET (local fallback)'}")
    print(f"  Date stamp: {TODAY}")

    store = BlobStore()
    print(f"  Blob backend: {'Azure' if store.connected else 'Local filesystem'}")

    if args.dry_run:
        print("\n  *** DRY RUN — no data will be uploaded ***")

    if args.verify:
        verify_blob(store)
        verify_table()
        return 0

    do_all = not (args.raw_only or args.cleaned_only or args.table_only)
    grand_total = 0

    if args.raw_only or do_all:
        grand_total += upload_raw(store, args.dry_run)

    if args.cleaned_only or do_all:
        grand_total += upload_cleaned(store, args.dry_run)

    if args.table_only or do_all:
        grand_total += upload_table_storage(args.dry_run)

    if not args.dry_run:
        verify_blob(store)

    print(f"\n{'=' * 60}")
    print(f"  COMPLETE — {grand_total} items processed")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
