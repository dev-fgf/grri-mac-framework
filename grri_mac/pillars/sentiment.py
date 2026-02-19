"""Text-based sentiment pillar (v7, optional 8th pillar).

Uses FinBERT to score FOMC minutes and Fed speeches for
hawkish/dovish tone. The sentiment pillar captures forward-
looking policy intent that isn't in the numerical indicators.

Architecture:
  1. Fetch recent FOMC texts (minutes, statements, speeches)
  2. Split into sentences, score each with FinBERT
  3. Aggregate: mean sentiment + uncertainty (std of scores)
  4. Map to 0-1 MAC scale (dovish = higher capacity = higher score)

Data coverage:
  - FOMC minutes: 1993+ (full text)
  - Fed speeches: 1987+ (FRASER)
  - Pre-1987: Falls back to proxy (newspaper sentiment indices)
  - Pre-1960: Not available → returns 0.5 (neutral)

Dependencies (all optional, lazy-loaded):
  - transformers (HuggingFace)
  - torch (PyTorch)

If dependencies are not installed, the pillar returns a neutral
0.5 score with method="unavailable".

Usage:
    from grri_mac.pillars.sentiment import SentimentPillar
    pillar = SentimentPillar()
    result = pillar.score(texts=["The Committee decided..."])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded globals
_finbert_pipeline = None
_FINBERT_AVAILABLE = None


def _check_finbert() -> bool:
    """Check if FinBERT dependencies are available."""
    global _FINBERT_AVAILABLE
    if _FINBERT_AVAILABLE is not None:
        return _FINBERT_AVAILABLE
    try:
        import torch  # noqa: F401
        from transformers import pipeline  # noqa: F401
        _FINBERT_AVAILABLE = True
    except ImportError:
        _FINBERT_AVAILABLE = False
        logger.info(
            "FinBERT unavailable (transformers/torch not installed). "
            "Sentiment pillar will return neutral scores."
        )
    return _FINBERT_AVAILABLE


def _get_finbert_pipeline():
    """Lazy-load FinBERT sentiment pipeline."""
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return _finbert_pipeline

    if not _check_finbert():
        return None

    try:
        from transformers import pipeline
        _finbert_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )
        logger.info("FinBERT pipeline loaded successfully")
    except Exception as e:
        logger.warning("Failed to load FinBERT: %s", e)
        _finbert_pipeline = None

    return _finbert_pipeline


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class SentenceSentiment:
    """Sentiment score for a single sentence."""

    text: str
    label: str  # "positive", "negative", "neutral"
    score: float  # Model confidence
    mapped_score: float  # Mapped to MAC scale


@dataclass
class SentimentResult:
    """Result of sentiment pillar scoring."""

    composite_score: float  # 0-1 MAC scale
    mean_sentiment: float  # Raw mean
    std_sentiment: float  # Uncertainty
    n_sentences: int
    n_documents: int
    hawkish_pct: float  # % of hawkish sentences
    dovish_pct: float  # % of dovish sentences
    neutral_pct: float  # % of neutral sentences
    method: str  # "finbert", "proxy", "unavailable"
    sentences: List[SentenceSentiment] = field(
        default_factory=list,
    )


# ── Sentiment pillar ─────────────────────────────────────────────────────

class SentimentPillar:
    """Text-based sentiment pillar using FinBERT.

    Scoring logic:
    - FinBERT labels: positive (dovish), negative (hawkish), neutral
    - Dovish → higher MAC score (more policy capacity to respond)
    - Hawkish → lower MAC score (policy constrained)
    - High uncertainty (high std across sentences) → slight penalty

    Thresholds:
    - > 60% dovish sentences → score 0.7-1.0
    - 40-60% mixed → score 0.4-0.7
    - > 60% hawkish → score 0.1-0.4
    """

    # Mapping from FinBERT label to MAC direction
    LABEL_MAP = {
        "positive": 0.8,   # Dovish/positive → high capacity
        "neutral": 0.5,    # Neutral
        "negative": 0.2,   # Hawkish/negative → constrained
    }

    # Uncertainty penalty (std of sentence scores)
    UNCERTAINTY_PENALTY_SCALE = 0.10

    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        max_sentences: int = 100,
    ):
        """Initialize sentiment pillar.

        Args:
            model_name: HuggingFace model name for FinBERT.
            max_sentences: Max sentences to process per scoring.
        """
        self.model_name = model_name
        self.max_sentences = max_sentences

    def score(
        self,
        texts: Optional[List[str]] = None,
        observation_date: Optional[datetime] = None,
    ) -> SentimentResult:
        """Score sentiment from FOMC/Fed texts.

        Args:
            texts: List of document texts to analyse.
            observation_date: For era-appropriate handling.

        Returns:
            SentimentResult with composite score.
        """
        # Check if before text data availability
        if observation_date and observation_date.year < 1960:
            return SentimentResult(
                composite_score=0.5,
                mean_sentiment=0.5,
                std_sentiment=0.0,
                n_sentences=0,
                n_documents=0,
                hawkish_pct=0.0,
                dovish_pct=0.0,
                neutral_pct=100.0,
                method="pre_data",
            )

        if not texts:
            return SentimentResult(
                composite_score=0.5,
                mean_sentiment=0.5,
                std_sentiment=0.0,
                n_sentences=0,
                n_documents=0,
                hawkish_pct=0.0,
                dovish_pct=0.0,
                neutral_pct=100.0,
                method="no_texts",
            )

        # Try FinBERT
        pipe = _get_finbert_pipeline()
        if pipe is not None:
            return self._score_finbert(texts, pipe)

        # Fallback: keyword-based proxy
        return self._score_keyword_proxy(texts)

    def _score_finbert(
        self,
        texts: List[str],
        pipe,
    ) -> SentimentResult:
        """Score using FinBERT model."""
        # Split texts into sentences
        sentences = []
        for text in texts:
            sents = self._split_sentences(text)
            sentences.extend(sents)

        if not sentences:
            return SentimentResult(
                composite_score=0.5,
                mean_sentiment=0.5,
                std_sentiment=0.0,
                n_sentences=0,
                n_documents=len(texts),
                hawkish_pct=0.0,
                dovish_pct=0.0,
                neutral_pct=100.0,
                method="finbert_empty",
            )

        # Limit sentences
        if len(sentences) > self.max_sentences:
            # Sample evenly across documents
            step = len(sentences) // self.max_sentences
            sentences = sentences[::max(step, 1)][
                :self.max_sentences
            ]

        # Run FinBERT
        try:
            results = pipe(sentences, batch_size=16)
        except Exception as e:
            logger.warning("FinBERT inference failed: %s", e)
            return self._score_keyword_proxy(texts)

        # Process results
        scored_sentences = []
        mapped_scores = []

        for sent_text, result in zip(sentences, results):
            label = result["label"]
            confidence = result["score"]
            mapped = self.LABEL_MAP.get(label, 0.5)

            # Weight by confidence
            weighted = mapped * confidence + 0.5 * (1 - confidence)
            mapped_scores.append(weighted)

            scored_sentences.append(SentenceSentiment(
                text=sent_text[:100],
                label=label,
                score=confidence,
                mapped_score=weighted,
            ))

        arr = np.array(mapped_scores)
        mean_sent = float(arr.mean())
        std_sent = float(arr.std())

        # Count by category
        n_hawk = sum(1 for s in scored_sentences if s.label == "negative")
        n_dove = sum(1 for s in scored_sentences if s.label == "positive")
        n_neut = sum(1 for s in scored_sentences if s.label == "neutral")
        total = len(scored_sentences)

        # Composite: mean with uncertainty penalty
        composite = mean_sent - (
            self.UNCERTAINTY_PENALTY_SCALE * std_sent
        )
        composite = float(np.clip(composite, 0.0, 1.0))

        return SentimentResult(
            composite_score=composite,
            mean_sentiment=mean_sent,
            std_sentiment=std_sent,
            n_sentences=total,
            n_documents=len(texts),
            hawkish_pct=n_hawk / total * 100 if total > 0 else 0.0,
            dovish_pct=n_dove / total * 100 if total > 0 else 0.0,
            neutral_pct=n_neut / total * 100 if total > 0 else 0.0,
            method="finbert",
            sentences=scored_sentences[:20],  # Keep top 20
        )

    def _score_keyword_proxy(
        self,
        texts: List[str],
    ) -> SentimentResult:
        """Fallback keyword-based sentiment scoring.

        Uses a simple bag-of-words approach with
        hawkish/dovish keyword dictionaries.
        """
        DOVISH = {
            "accommodate", "accommodative", "support",
            "easing", "stimulus", "recovery", "patient",
            "gradual", "downside", "risks", "weakness",
            "slack", "below target", "lower bound",
            "asset purchases", "forward guidance",
        }
        HAWKISH = {
            "tighten", "tightening", "restrictive",
            "inflation", "overheating", "strong labor",
            "above target", "normalize", "reduce purchases",
            "rate increase", "price stability", "vigilant",
            "upside risks", "balance sheet reduction",
        }

        dove_count = 0
        hawk_count = 0
        total_words = 0

        for text in texts:
            words = text.lower().split()
            total_words += len(words)
            for i, word in enumerate(words):
                # Check single words and bigrams
                if word in DOVISH:
                    dove_count += 1
                if word in HAWKISH:
                    hawk_count += 1
                if i < len(words) - 1:
                    bigram = f"{word} {words[i + 1]}"
                    if bigram in DOVISH:
                        dove_count += 1
                    if bigram in HAWKISH:
                        hawk_count += 1

        total_signals = dove_count + hawk_count
        if total_signals == 0:
            score = 0.5
        else:
            # Dovish ratio → maps to score
            dove_ratio = dove_count / total_signals
            score = 0.2 + 0.6 * dove_ratio  # Range 0.2-0.8

        return SentimentResult(
            composite_score=float(np.clip(score, 0.0, 1.0)),
            mean_sentiment=score,
            std_sentiment=0.15,  # Higher uncertainty for proxy
            n_sentences=0,
            n_documents=len(texts),
            hawkish_pct=(
                hawk_count / total_signals * 100
                if total_signals > 0 else 0.0
            ),
            dovish_pct=(
                dove_count / total_signals * 100
                if total_signals > 0 else 0.0
            ),
            neutral_pct=0.0,
            method="keyword_proxy",
        )

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Simple sentence splitting."""
        # Basic splitting on period, exclamation, question mark
        # followed by space + capital letter
        import re
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        # Filter short fragments
        return [
            s.strip() for s in sentences
            if len(s.strip()) > 20
        ]

    def score_from_proxy(
        self,
        proxy_score: float,
        observation_date: Optional[datetime] = None,
    ) -> SentimentResult:
        """Score from a pre-computed proxy (e.g. rate-change-based).

        Used during backtesting when FOMC texts are not available
        but a FRED-derived proxy sentiment score is.

        Args:
            proxy_score: Pre-computed sentiment in [0, 1].
            observation_date: For era-appropriate handling.

        Returns:
            SentimentResult with proxy-derived composite score.
        """
        if observation_date and observation_date.year < 1960:
            return SentimentResult(
                composite_score=0.5,
                mean_sentiment=0.5,
                std_sentiment=0.0,
                n_sentences=0,
                n_documents=0,
                hawkish_pct=0.0,
                dovish_pct=0.0,
                neutral_pct=100.0,
                method="pre_data",
            )

        score = float(np.clip(proxy_score, 0.0, 1.0))
        hawk_pct = max(0.0, (0.5 - score) * 200)  # 0 at 0.5, 100 at 0.0
        dove_pct = max(0.0, (score - 0.5) * 200)  # 0 at 0.5, 100 at 1.0
        neut_pct = 100.0 - hawk_pct - dove_pct

        return SentimentResult(
            composite_score=score,
            mean_sentiment=score,
            std_sentiment=0.12,  # Elevated uncertainty for proxy
            n_sentences=0,
            n_documents=0,
            hawkish_pct=hawk_pct,
            dovish_pct=dove_pct,
            neutral_pct=neut_pct,
            method="rate_proxy",
        )

    def get_score(
        self,
        texts: Optional[List[str]] = None,
    ) -> float:
        """Get composite sentiment score."""
        return self.score(texts=texts).composite_score
