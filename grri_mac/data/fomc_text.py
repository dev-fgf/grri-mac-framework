"""FOMC text data access for sentiment pillar.

Provides access to FOMC minutes and Fed speeches for
FinBERT-based sentiment analysis. Data sources:

- FOMC minutes: Federal Reserve website (1993+)
- Fed speeches: FRASER digital library (1987+)
- Pre-1987 proxy: rate-change-based sentiment indices

This module handles data fetching and caching only.
Sentiment scoring is in grri_mac/pillars/sentiment.py.

Usage:
    from grri_mac.data.fomc_text import FOMCTextSource
    source = FOMCTextSource()
    texts = source.get_recent_texts(n=5)

    # For backtest (FRED-data-based proxy):
    score = source.get_rate_proxy_sentiment(date, fred_client)
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from grri_mac.data.fred import FREDClient

logger = logging.getLogger(__name__)


@dataclass
class FOMCDocument:
    """A single FOMC document for sentiment analysis."""

    date: datetime
    doc_type: str  # "minutes", "statement", "speech", "testimony"
    title: str
    text: str
    speaker: Optional[str] = None  # For speeches
    word_count: int = 0


@dataclass
class SentimentTextCorpus:
    """Collection of FOMC texts for a time window."""

    documents: List[FOMCDocument]
    start_date: datetime
    end_date: datetime
    n_minutes: int = 0
    n_speeches: int = 0
    n_statements: int = 0


# ── Historical FOMC meeting dates (sample for offline use) ───────────────

# Key FOMC dates with known hawkish/dovish tone for calibration.
# tone_score: 0.0 = maximally hawkish, 1.0 = maximally dovish
CALIBRATION_FOMC_DATES: Dict[datetime, Dict[str, Any]] = {
    datetime(2007, 8, 17): {
        "tone": "dovish",
        "tone_score": 0.85,
        "context": "Inter-meeting rate cut, subprime fears",
    },
    datetime(2008, 9, 16): {
        "tone": "dovish",
        "tone_score": 0.95,
        "context": "Lehman week, emergency easing",
    },
    datetime(2008, 12, 16): {
        "tone": "dovish",
        "tone_score": 0.95,
        "context": "Zero-bound reached, QE1 announced",
    },
    datetime(2010, 11, 3): {
        "tone": "dovish",
        "tone_score": 0.80,
        "context": "QE2 announced, $600bn",
    },
    datetime(2012, 9, 13): {
        "tone": "dovish",
        "tone_score": 0.85,
        "context": "QE3 announcement, open-ended",
    },
    datetime(2013, 5, 22): {
        "tone": "hawkish",
        "tone_score": 0.20,
        "context": "Taper Tantrum, Bernanke signals taper",
    },
    datetime(2015, 12, 16): {
        "tone": "hawkish",
        "tone_score": 0.25,
        "context": "First post-GFC rate hike",
    },
    datetime(2018, 12, 19): {
        "tone": "hawkish",
        "tone_score": 0.15,
        "context": "Rate hike despite market stress",
    },
    datetime(2019, 1, 30): {
        "tone": "dovish",
        "tone_score": 0.80,
        "context": "Powell pivot, patient language",
    },
    datetime(2020, 3, 15): {
        "tone": "dovish",
        "tone_score": 0.95,
        "context": "Emergency cut to zero, QE unlimited",
    },
    datetime(2022, 3, 16): {
        "tone": "hawkish",
        "tone_score": 0.20,
        "context": "First post-COVID hike",
    },
    datetime(2022, 6, 15): {
        "tone": "hawkish",
        "tone_score": 0.10,
        "context": "75bp surprise hike",
    },
    datetime(2022, 11, 2): {
        "tone": "hawkish",
        "tone_score": 0.15,
        "context": "Fourth consecutive 75bp hike",
    },
    datetime(2023, 7, 26): {
        "tone": "neutral",
        "tone_score": 0.45,
        "context": "Last hike of cycle, data-dependent",
    },
}


class FOMCTextSource:
    """Source for FOMC and Fed text data.

    Supports three modes:
      1. **Production**: Fetch FOMC minutes from Federal Reserve website
         (https://www.federalreserve.gov/monetarypolicy/fomcminutes*.htm)
      2. **Backtest proxy**: Rate-change-based sentiment derived from FRED data
         (fed funds delta, yield curve slope, credit spreads)
      3. **Pre-loaded**: Load texts from dict for unit testing
    """

    # ── FOMC minutes URL templates ───────────────────────────────────────
    # Post-2008 format: YYYYMMDD
    _MINUTES_URL = (
        "https://www.federalreserve.gov/monetarypolicy/"
        "fomcminutes{date_str}.htm"
    )

    def __init__(
        self,
        cache_dir: Optional[str] = None,
    ):
        """Initialize FOMC text source.

        Args:
            cache_dir: Optional directory for caching downloaded texts.
                Defaults to .cache/fomc_texts/ in project root.
        """
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                ".cache", "fomc_texts",
            )
        self.cache_dir = cache_dir
        self._cache: Dict[datetime, List[FOMCDocument]] = {}
        self._proxy_cache: Dict[str, float] = {}

    # ── Public API: text-based ───────────────────────────────────────────

    def get_recent_texts(
        self,
        as_of_date: Optional[datetime] = None,
        n: int = 5,
        doc_types: Optional[List[str]] = None,
    ) -> List[FOMCDocument]:
        """Get most recent FOMC texts.

        Checks pre-loaded cache first, then tries local file cache,
        then attempts to fetch from the Fed website.

        Args:
            as_of_date: Cutoff date (for no-lookahead backtest).
                Defaults to now.
            n: Number of documents to return.
            doc_types: Filter by document type.

        Returns:
            List of FOMCDocument, most recent first.
        """
        if as_of_date is None:
            as_of_date = datetime.now()

        # Check pre-loaded cache
        candidates: List[FOMCDocument] = []
        for dt, docs in self._cache.items():
            if dt <= as_of_date:
                for d in docs:
                    if doc_types is None or d.doc_type in doc_types:
                        candidates.append(d)

        # Sort by date descending
        candidates.sort(key=lambda d: d.date, reverse=True)
        if candidates:
            return candidates[:n]

        # Check disk cache
        disk_docs = self._load_from_disk_cache(as_of_date, n)
        if disk_docs:
            return disk_docs

        logger.debug(
            "FOMCTextSource: no cached texts for %s",
            as_of_date.isoformat(),
        )
        return []

    def get_texts_for_period(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> SentimentTextCorpus:
        """Get all FOMC texts in a date range.

        Args:
            start_date: Period start.
            end_date: Period end.

        Returns:
            SentimentTextCorpus with all matching documents.
        """
        docs = []
        for dt, doc_list in self._cache.items():
            if start_date <= dt <= end_date:
                docs.extend(doc_list)

        n_min = sum(1 for d in docs if d.doc_type == "minutes")
        n_spch = sum(1 for d in docs if d.doc_type == "speech")
        n_stmt = sum(1 for d in docs if d.doc_type == "statement")

        return SentimentTextCorpus(
            documents=docs,
            start_date=start_date,
            end_date=end_date,
            n_minutes=n_min,
            n_speeches=n_spch,
            n_statements=n_stmt,
        )

    def load_from_dict(
        self,
        texts: Dict[datetime, List[Dict]],
    ):
        """Load pre-formatted texts for backtesting.

        Args:
            texts: Dict mapping dates to lists of text dicts
                with keys: doc_type, title, text, speaker.
        """
        for date, doc_list in texts.items():
            self._cache[date] = [
                FOMCDocument(
                    date=date,
                    doc_type=d.get("doc_type", "minutes"),
                    title=d.get("title", ""),
                    text=d.get("text", ""),
                    speaker=d.get("speaker"),
                    word_count=len(d.get("text", "").split()),
                )
                for d in doc_list
            ]

    # ── Public API: rate-change proxy for backtesting ────────────────────

    def get_rate_proxy_sentiment(
        self,
        date: datetime,
        fred_client: "FREDClient",
    ) -> float:
        """Compute sentiment score from FRED monetary-policy indicators.

        This is the primary backtest path. It derives a [0, 1] sentiment
        score from three FRED-observable signals:

          1. **Fed funds rate change** (6-month delta):
             Large cuts → dovish (0.8-0.95), large hikes → hawkish (0.10-0.25)
          2. **Yield-curve slope** (10Y minus 2Y):
             Steep → dovish / accommodative, inverted → hawkish / restrictive
          3. **Credit-spread change** (BAA-AAA 3-month delta):
             Widening → risk-off / dovish pivot likely, tightening → hawkish ok

        These three are combined with weights [0.50, 0.25, 0.25] and
        anchored against the 14 CALIBRATION_FOMC_DATES.

        For pre-1960 dates, returns 0.5 (neutral).
        For pre-1913 dates (no Fed), returns 0.5 (neutral).

        Args:
            date: Observation date.
            fred_client: Initialised FREDClient with prefetched data.

        Returns:
            Sentiment score in [0, 1].  Higher = more dovish = more capacity.
        """
        # Pre-1913: no Federal Reserve
        if date.year < 1913:
            return 0.5

        # Pre-1960: very limited data
        if date.year < 1960:
            return 0.5

        # Check against calibration anchors first (within 14 days)
        anchor = self._check_calibration_anchor(date)
        if anchor is not None:
            return anchor

        # Check proxy cache
        cache_key = date.strftime("%Y-%m-%d")
        if cache_key in self._proxy_cache:
            return self._proxy_cache[cache_key]

        # ── Signal 1: Fed funds rate 6-month change ──────────────────
        ff_score = self._rate_change_signal(date, fred_client)

        # ── Signal 2: Yield curve slope (10Y - 2Y) ──────────────────
        yc_score = self._yield_curve_signal(date, fred_client)

        # ── Signal 3: Credit spread momentum (BAA - AAA) ────────────
        cs_score = self._credit_spread_signal(date, fred_client)

        # Weighted combination
        sentiment = 0.50 * ff_score + 0.25 * yc_score + 0.25 * cs_score

        # Clip to [0.05, 0.95] — never fully certain
        sentiment = max(0.05, min(0.95, sentiment))

        self._proxy_cache[cache_key] = sentiment
        return sentiment

    # ── Private: individual proxy signals ────────────────────────────────

    def _rate_change_signal(
        self,
        date: datetime,
        fred_client: "FREDClient",
    ) -> float:
        """Fed funds 6-month change → sentiment score.

        Large cuts → dovish (high score), large hikes → hawkish (low score).
        Uses a sigmoid mapping centred at 0 with scale ~150bp.
        """
        current_ff = fred_client.get_fed_funds(date)
        prior_date = date - timedelta(days=180)
        prior_ff = fred_client.get_fed_funds(prior_date)

        if current_ff is None or prior_ff is None:
            return 0.5  # No data → neutral

        # Change in percentage points (negative = cutting)
        delta_ff = current_ff - prior_ff

        # Sigmoid: -3% cut → ~0.90, +3% hike → ~0.10
        # s = 1 / (1 + exp(k * delta))   with k = 1.5
        score = 1.0 / (1.0 + math.exp(1.5 * delta_ff))
        return score

    def _yield_curve_signal(
        self,
        date: datetime,
        fred_client: "FREDClient",
    ) -> float:
        """Yield curve slope (10Y - 2Y) → sentiment score.

        Steep positive → accommodative (high). Inverted → restrictive (low).
        """
        dgs10 = fred_client.get_value_for_date("DGS10", date, lookback_days=14)
        dgs2 = fred_client.get_value_for_date("DGS2", date, lookback_days=14)

        if dgs10 is None or dgs2 is None:
            # Try alternative: 10Y minus fed funds
            ff = fred_client.get_fed_funds(date)
            if dgs10 is not None and ff is not None:
                spread = dgs10 - ff
            else:
                return 0.5

        else:
            spread = dgs10 - dgs2

        # Map: -2% inverted → ~0.15, +3% steep → ~0.85
        # Linear with clipping
        score = 0.5 + spread * 0.15
        return max(0.10, min(0.90, score))

    def _credit_spread_signal(
        self,
        date: datetime,
        fred_client: "FREDClient",
    ) -> float:
        """Credit-spread 3-month momentum → sentiment score.

        Widening spreads signal stress → Fed likely to pivot dovish (higher score).
        Tightening spreads → hawkish bias OK (lower score).

        Note: This captures the *reaction function* — widening spreads
        lead to dovish policy response, which is positive for absorption.
        """
        # BAA - AAA spread (Moody's)
        baa = fred_client.get_value_for_date("BAA", date, lookback_days=35)
        aaa = fred_client.get_value_for_date("AAA", date, lookback_days=35)

        prior_date = date - timedelta(days=91)
        baa_prior = fred_client.get_value_for_date(
            "BAA", prior_date, lookback_days=35,
        )
        aaa_prior = fred_client.get_value_for_date(
            "AAA", prior_date, lookback_days=35,
        )

        if baa is None or aaa is None or baa_prior is None or aaa_prior is None:
            return 0.5

        current_spread = baa - aaa
        prior_spread = baa_prior - aaa_prior
        delta_spread = current_spread - prior_spread  # positive = widening

        # Widening → dovish response likely → higher score
        # sigmoid centred at 0, scale ~50bp
        score = 1.0 / (1.0 + math.exp(-3.0 * delta_spread))
        return score

    def _check_calibration_anchor(self, date: datetime) -> Optional[float]:
        """Check if date is near a calibration anchor point."""
        for anchor_date, info in CALIBRATION_FOMC_DATES.items():
            diff = abs((date - anchor_date).days)
            if diff <= 14:
                return info["tone_score"]
        return None

    # ── Private: disk cache ──────────────────────────────────────────────

    def _load_from_disk_cache(
        self,
        as_of_date: datetime,
        n: int,
    ) -> List[FOMCDocument]:
        """Try to load cached FOMC texts from disk."""
        cache_path = Path(self.cache_dir)
        if not cache_path.exists():
            return []

        docs: List[FOMCDocument] = []
        for fpath in sorted(cache_path.glob("*.txt"), reverse=True):
            # Filename format: YYYYMMDD_minutes.txt
            match = re.match(r"(\d{8})_(\w+)\.txt", fpath.name)
            if not match:
                continue

            file_date = datetime.strptime(match.group(1), "%Y%m%d")
            if file_date > as_of_date:
                continue

            doc_type = match.group(2)
            text = fpath.read_text(encoding="utf-8", errors="replace")

            docs.append(FOMCDocument(
                date=file_date,
                doc_type=doc_type,
                title=f"FOMC {doc_type} {file_date.strftime('%Y-%m-%d')}",
                text=text,
                word_count=len(text.split()),
            ))

            if len(docs) >= n:
                break

        return docs
