"""Azure Blob Storage client for MAC framework data lake.

Two-tier storage:
    mac-raw-data     — data exactly as received from external sources
    mac-cleaned-data — validated, standardised DataFrames (Parquet / CSV)

Blob naming convention::

    {source}/{series_id}/{YYYY-MM-DD}.{ext}

Example:
    raw   → fred/VIXCLS/2026-02-18.json
    clean → fred/VIXCLS/2026-02-18.parquet

Environment variables:
    AZURE_STORAGE_CONNECTION_STRING  — required for Azure
    MAC_DATALAKE_LOCAL_ROOT          — optional override for local fallback dir

When Azure is unavailable the client falls back to the local filesystem
under ``data/datalake/`` so development works without cloud credentials.
"""

from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Azure SDK (optional)
# ---------------------------------------------------------------------------
try:
    from azure.storage.blob import (
        BlobServiceClient,
        ContentSettings,
    )
    BLOB_AVAILABLE = True
except ImportError:
    BLOB_AVAILABLE = False
    logger.info("azure-storage-blob not installed — using local filesystem")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RAW_CONTAINER = "mac-raw-data"
CLEANED_CONTAINER = "mac-cleaned-data"

# Content types for metadata
CONTENT_TYPES = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".parquet": "application/octet-stream",
    ".pkl": "application/octet-stream",
    ".xlsx": (
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet"
    ),
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain",
    ".dat": "text/plain",
}

# Default local root when Azure is unavailable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_LOCAL_ROOT = _PROJECT_ROOT / "data" / "datalake"


# ──────────────────────────────────────────────────────────────────────────────
# Tier enum
# ──────────────────────────────────────────────────────────────────────────────

class DataTier:
    """Storage tier constants."""

    RAW = "raw"
    CLEANED = "cleaned"


# ──────────────────────────────────────────────────────────────────────────────
# BlobStore
# ──────────────────────────────────────────────────────────────────────────────

class BlobStore:
    """Unified interface for Azure Blob Storage with local fallback.

    Usage::

        store = BlobStore()                          # auto-detects Azure
        store.upload_dataframe("fred", "VIXCLS", df) # → cleaned container
        store.upload_raw_bytes("nber", "m13001", b)  # → raw container
        df = store.download_dataframe("fred", "VIXCLS")
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        local_root: Optional[Path] = None,
    ) -> None:
        prefer_local = local_root is not None
        self._conn_str = (
            connection_string
            if not prefer_local
            else connection_string  # ignore env when caller supplies root
        )

        if self._conn_str is None and not prefer_local:
            self._conn_str = os.environ.get(
                "AZURE_STORAGE_CONNECTION_STRING"
            )

        _root = (
            local_root
            or os.environ.get(
                "MAC_DATALAKE_LOCAL_ROOT",
                str(_DEFAULT_LOCAL_ROOT),
            )
        )
        self._local_root = Path(str(_root))
        self._service: Optional[Any] = None  # BlobServiceClient
        self._containers: Dict[str, Any] = {}
        self.connected = False

        if self._conn_str and BLOB_AVAILABLE:
            try:
                self._service = BlobServiceClient.from_connection_string(
                    self._conn_str
                )
                self._ensure_containers()
                self.connected = True
                logger.info("BlobStore connected to Azure")
            except Exception as exc:
                logger.warning(
                    "Azure Blob connection failed: "
                    "%s - using local", exc,
                )

        if not self.connected:
            self._local_root.mkdir(parents=True, exist_ok=True)
            logger.info(
                "BlobStore using local filesystem: %s",
                self._local_root,
            )

    # ------------------------------------------------------------------
    # Container management
    # ------------------------------------------------------------------

    def _ensure_containers(self) -> None:
        """Create raw + cleaned containers if they don't exist."""
        for name in (RAW_CONTAINER, CLEANED_CONTAINER):
            try:
                self._service.create_container(  # type: ignore[union-attr]
                    name,
                )
                logger.info("Created blob container: %s", name)
            except Exception:
                pass  # already exists
            self._containers[name] = (
                self._service  # type: ignore[union-attr]
                .get_container_client(name)
            )

    def _container(self, tier: str) -> Any:
        """Return the ContainerClient for a tier."""
        name = RAW_CONTAINER if tier == DataTier.RAW else CLEANED_CONTAINER
        return self._containers.get(name)

    # ------------------------------------------------------------------
    # Blob path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def blob_path(
        source: str,
        series_id: str,
        ext: str = ".parquet",
        date_str: Optional[str] = None,
    ) -> str:
        """Build the canonical blob path.

        Args:
            source: Data source key (e.g. ``fred``, ``nber``, ``cboe``).
            series_id: Series identifier (e.g. ``VIXCLS``, ``m13001``).
            ext: File extension including dot.
            date_str: ISO date stamp; defaults to today.

        Returns:
            Path string like ``fred/VIXCLS/2026-02-18.parquet``.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"{source}/{series_id}/{date_str}{ext}"

    @staticmethod
    def _metadata(
        source: str,
        series_id: str,
        *,
        row_count: Optional[int] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Build blob metadata dict."""
        meta: Dict[str, str] = {
            "source": source,
            "series_id": series_id,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        if row_count is not None:
            meta["row_count"] = str(row_count)
        if extra:
            meta.update(extra)
        return meta

    # ------------------------------------------------------------------
    # Upload — Azure
    # ------------------------------------------------------------------

    def _upload_azure(
        self,
        tier: str,
        blob_name: str,
        data: bytes,
        content_type: str,
        metadata: Dict[str, str],
    ) -> bool:
        container = self._container(tier)
        if container is None:
            return False
        try:
            container.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
                metadata=metadata,
                content_settings=ContentSettings(content_type=content_type),
            )
            logger.info("Uploaded %s → %s/%s", blob_name, tier, blob_name)
            return True
        except Exception as exc:
            logger.error("Upload failed %s: %s", blob_name, exc)
            return False

    # ------------------------------------------------------------------
    # Upload — Local filesystem
    # ------------------------------------------------------------------

    def _upload_local(
        self,
        tier: str,
        blob_name: str,
        data: bytes,
        metadata: Dict[str, str],
    ) -> bool:
        tier_dir = self._local_root / tier
        dest = tier_dir / blob_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(data)
            # Store metadata alongside
            meta_path = dest.with_suffix(dest.suffix + ".meta.json")
            meta_path.write_text(json.dumps(metadata, indent=2))
            logger.info("Saved locally %s → %s", blob_name, dest)
            return True
        except Exception as exc:
            logger.error("Local save failed %s: %s", blob_name, exc)
            return False

    # ------------------------------------------------------------------
    # Download — Azure
    # ------------------------------------------------------------------

    def _download_azure(self, tier: str, blob_name: str) -> Optional[bytes]:
        container = self._container(tier)
        if container is None:
            return None
        try:
            blob = container.download_blob(blob_name)
            return blob.readall()
        except Exception as exc:
            logger.warning("Download failed %s/%s: %s", tier, blob_name, exc)
            return None

    # ------------------------------------------------------------------
    # Download — Local filesystem
    # ------------------------------------------------------------------

    def _download_local(self, tier: str, blob_name: str) -> Optional[bytes]:
        path = self._local_root / tier / blob_name
        if path.exists():
            return path.read_bytes()
        return None

    # ══════════════════════════════════════════════════════════════════════
    # Public API — raw data
    # ══════════════════════════════════════════════════════════════════════

    def upload_raw_bytes(
        self,
        source: str,
        series_id: str,
        data: bytes,
        ext: str = ".json",
        *,
        date_str: Optional[str] = None,
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Store raw bytes to the *raw* tier.

        Args:
            source: Source key (``fred``, ``nber``, ``cboe``, …).
            series_id: Series identifier.
            data: Raw bytes as received from the source.
            ext: File extension (e.g. ``.json``, ``.csv``, ``.dat``).
            date_str: Optional ISO date override.
            extra_metadata: Additional metadata key-value pairs.

        Returns:
            ``True`` on success.
        """
        blob_name = self.blob_path(source, series_id, ext, date_str)
        ct = CONTENT_TYPES.get(ext, "application/octet-stream")
        meta = self._metadata(source, series_id, extra=extra_metadata)

        if self.connected:
            return self._upload_azure(DataTier.RAW, blob_name, data, ct, meta)
        return self._upload_local(DataTier.RAW, blob_name, data, meta)

    def upload_raw_json(
        self,
        source: str,
        series_id: str,
        obj: Any,
        *,
        date_str: Optional[str] = None,
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Serialise a Python object to JSON and store in the *raw* tier."""
        raw = json.dumps(obj, default=str, indent=2).encode("utf-8")
        return self.upload_raw_bytes(
            source, series_id, raw, ext=".json",
            date_str=date_str, extra_metadata=extra_metadata,
        )

    def upload_raw_csv(
        self,
        source: str,
        series_id: str,
        df: pd.DataFrame,
        *,
        date_str: Optional[str] = None,
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Store a DataFrame as CSV in the *raw* tier."""
        buf = df.to_csv(index=True).encode("utf-8")
        meta = extra_metadata or {}
        meta["row_count"] = str(len(df))
        return self.upload_raw_bytes(
            source, series_id, buf, ext=".csv",
            date_str=date_str, extra_metadata=meta,
        )

    def download_raw_bytes(
        self,
        source: str,
        series_id: str,
        ext: str = ".json",
        date_str: Optional[str] = None,
    ) -> Optional[bytes]:
        """Retrieve raw bytes from the *raw* tier."""
        blob_name = self.blob_path(source, series_id, ext, date_str)
        if self.connected:
            return self._download_azure(DataTier.RAW, blob_name)
        return self._download_local(DataTier.RAW, blob_name)

    def download_raw_json(
        self,
        source: str,
        series_id: str,
        date_str: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve and parse a JSON blob from the *raw* tier."""
        data = self.download_raw_bytes(source, series_id, ".json", date_str)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"))

    # ══════════════════════════════════════════════════════════════════════
    # Public API — cleaned data (DataFrames)
    # ══════════════════════════════════════════════════════════════════════

    def upload_dataframe(
        self,
        source: str,
        series_id: str,
        df: pd.DataFrame,
        *,
        fmt: str = "parquet",
        date_str: Optional[str] = None,
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Store a cleaned DataFrame in the *cleaned* tier.

        Args:
            source: Source key.
            series_id: Series identifier.
            df: Cleaned DataFrame to persist.
            fmt: ``"parquet"`` (default) or ``"csv"``.
            date_str: Optional ISO date override.
            extra_metadata: Additional metadata.

        Returns:
            ``True`` on success.
        """
        if fmt == "parquet":
            buf = io.BytesIO()
            df.to_parquet(buf, index=True, engine="pyarrow")
            raw_bytes = buf.getvalue()
            ext = ".parquet"
        else:
            raw_bytes = df.to_csv(index=True).encode("utf-8")
            ext = ".csv"

        blob_name = self.blob_path(source, series_id, ext, date_str)
        ct = CONTENT_TYPES.get(ext, "application/octet-stream")
        meta = self._metadata(
            source, series_id,
            row_count=len(df),
            extra=extra_metadata,
        )

        if self.connected:
            return self._upload_azure(
                DataTier.CLEANED, blob_name,
                raw_bytes, ct, meta,
            )
        return self._upload_local(DataTier.CLEANED, blob_name, raw_bytes, meta)

    def download_dataframe(
        self,
        source: str,
        series_id: str,
        *,
        fmt: str = "parquet",
        date_str: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Retrieve a cleaned DataFrame from the *cleaned* tier.

        Args:
            source: Source key.
            series_id: Series identifier.
            fmt: ``"parquet"`` (default) or ``"csv"``.
            date_str: ISO date override.

        Returns:
            DataFrame, or ``None`` if not found.
        """
        ext = ".parquet" if fmt == "parquet" else ".csv"
        blob_name = self.blob_path(source, series_id, ext, date_str)

        if self.connected:
            data = self._download_azure(DataTier.CLEANED, blob_name)
        else:
            data = self._download_local(DataTier.CLEANED, blob_name)

        if data is None:
            return None

        if fmt == "parquet":
            return pd.read_parquet(io.BytesIO(data))
        return pd.read_csv(io.BytesIO(data), index_col=0, parse_dates=True)

    # ══════════════════════════════════════════════════════════════════════
    # Listing / discovery
    # ══════════════════════════════════════════════════════════════════════

    def list_blobs(
        self,
        tier: str = DataTier.CLEANED,
        prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List blobs in a tier, optionally filtered by prefix.

        Args:
            tier: ``DataTier.RAW`` or ``DataTier.CLEANED``.
            prefix: Optional path prefix (e.g. ``"fred/"``).

        Returns:
            List of dicts with ``name``, ``size``, ``last_modified``,
            ``metadata`` keys.
        """
        if self.connected:
            return self._list_azure(tier, prefix)
        return self._list_local(tier, prefix)

    def _list_azure(
        self, tier: str, prefix: Optional[str]
    ) -> List[Dict[str, Any]]:
        container = self._container(tier)
        if container is None:
            return []
        try:
            blobs = container.list_blobs(name_starts_with=prefix)
            return [
                {
                    "name": b.name,
                    "size": b.size,
                    "last_modified": b.last_modified,
                    "metadata": b.metadata or {},
                }
                for b in blobs
            ]
        except Exception as exc:
            logger.warning("list_blobs failed: %s", exc)
            return []

    def _list_local(
        self, tier: str, prefix: Optional[str]
    ) -> List[Dict[str, Any]]:
        tier_dir = self._local_root / tier
        if not tier_dir.exists():
            return []
        results: List[Dict[str, Any]] = []
        for f in sorted(tier_dir.rglob("*")):
            if f.is_dir() or f.suffix == ".json" and f.stem.endswith(".meta"):
                continue
            rel = f.relative_to(tier_dir).as_posix()
            if prefix and not rel.startswith(prefix):
                continue
            # Try to load metadata sidecar
            meta_path = f.with_suffix(f.suffix + ".meta.json")
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    pass
            results.append({
                "name": rel,
                "size": f.stat().st_size,
                "last_modified": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc
                ),
                "metadata": meta,
            })
        return results

    def exists(
        self,
        source: str,
        series_id: str,
        tier: str = DataTier.CLEANED,
        ext: str = ".parquet",
        date_str: Optional[str] = None,
    ) -> bool:
        """Check whether a specific blob exists."""
        blob_name = self.blob_path(source, series_id, ext, date_str)
        if self.connected:
            container = self._container(tier)
            if container is None:
                return False
            try:
                container.get_blob_properties(blob_name)
                return True
            except Exception:
                return False
        path = self._local_root / tier / blob_name
        return path.exists()

    def delete(
        self,
        source: str,
        series_id: str,
        tier: str = DataTier.CLEANED,
        ext: str = ".parquet",
        date_str: Optional[str] = None,
    ) -> bool:
        """Delete a blob."""
        blob_name = self.blob_path(source, series_id, ext, date_str)
        if self.connected:
            container = self._container(tier)
            if container is None:
                return False
            try:
                container.delete_blob(blob_name)
                return True
            except Exception:
                return False
        path = self._local_root / tier / blob_name
        if path.exists():
            path.unlink()
            meta = path.with_suffix(path.suffix + ".meta.json")
            if meta.exists():
                meta.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # Convenience: bulk operations
    # ------------------------------------------------------------------

    def get_source_manifest(
        self,
        source: str,
        tier: str = DataTier.CLEANED,
    ) -> Dict[str, List[str]]:
        """Return ``{series_id: [date1, date2, …]}`` for a source.

        Useful for discovering which series and dates are available.
        """
        blobs = self.list_blobs(tier=tier, prefix=f"{source}/")
        manifest: Dict[str, List[str]] = {}
        for b in blobs:
            parts = b["name"].split("/")
            if len(parts) >= 3:
                sid = parts[1]
                date_part = parts[2].rsplit(".", 1)[0]  # strip extension
                manifest.setdefault(sid, []).append(date_part)
        return manifest

    def __repr__(self) -> str:
        backend = (
            "Azure Blob Storage"
            if self.connected
            else f"Local ({self._local_root})"
        )
        return f"BlobStore(backend={backend!r})"


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton accessor
# ──────────────────────────────────────────────────────────────────────────────

_store: Optional[BlobStore] = None


def get_blob_store() -> BlobStore:
    """Return (or create) the module-level BlobStore singleton."""
    global _store
    if _store is None:
        _store = BlobStore()
    return _store
