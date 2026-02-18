"""Crisis Severity Rubric (CSR) — v6 §13.2.

The CSR provides an **independently derived** expected MAC score for each
historical scenario, eliminating the circularity of setting targets by
observing MAC output and reasoning backwards from severity.

Five dimensions are scored on a 0–1 scale (0 = most severe, 1 = minimal
stress).  All dimensions use data available at or shortly after the crisis
date — none require MAC framework output.

Dimensions:
  1. Drawdown Magnitude      — S&P 500 peak-to-trough within 90 days
  2. Market Functioning      — Operational market disruption (categorical)
  3. Policy Response          — Official-sector response intensity
  4. Contagion Breadth       — Cross-segment / cross-geography propagation
  5. Duration of Acute Stress — Trading days until VIX normalises

The composite CSR is the equally-weighted average of the five sub-scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Enums for categorical dimensions
# ---------------------------------------------------------------------------

class MarketDysfunction(Enum):
    """Market functioning disruption levels (§13.2.2 Dimension 2)."""
    NONE = "none"           # Orderly repricing
    MODERATE = "moderate"   # Elevated bid-ask, ETF dislocations
    SEVERE = "severe"       # Circuit breakers, repo seizure
    EXTREME = "extreme"     # Market closure, LOLR facilities


class PolicyResponse(Enum):
    """Policy response intensity levels (§13.2.2 Dimension 3)."""
    NONE = "none"                   # None or routine
    VERBAL = "verbal"               # Verbal guidance
    EMERGENCY_TARGETED = "targeted"  # Emergency cut
    EMERGENCY_BROAD = "broad"       # Multiple emergency cuts
    UNLIMITED = "unlimited"         # Unlimited QE


class ContagionBreadth(Enum):
    """Contagion breadth levels (§13.2.2 Dimension 4)."""
    SINGLE = "single"        # One asset class or sector
    TWO_THREE = "two_three"  # 2–3 segments
    BROAD_DOMESTIC = "broad"  # Most domestic asset classes
    GLOBAL_SYSTEMIC = "global"  # International, >3 markets


# ---------------------------------------------------------------------------
# Scoring tables (§13.2.2)
# ---------------------------------------------------------------------------

# Dimension 1: Drawdown magnitude → sub-score
DRAWDOWN_BRACKETS: list[tuple[float, float]] = [
    # (max_drawdown_pct, sub_score)
    (5.0, 0.90),
    (10.0, 0.70),
    (20.0, 0.45),
    (35.0, 0.25),
    (float("inf"), 0.10),
]

# Dimension 2: Market dysfunction → sub-score
DYSFUNCTION_SCORES: dict[MarketDysfunction, float] = {
    MarketDysfunction.NONE: 0.90,
    MarketDysfunction.MODERATE: 0.55,
    MarketDysfunction.SEVERE: 0.25,
    MarketDysfunction.EXTREME: 0.10,
}

# Dimension 3: Policy response → sub-score
POLICY_SCORES: dict[PolicyResponse, float] = {
    PolicyResponse.NONE: 0.90,
    PolicyResponse.VERBAL: 0.70,
    PolicyResponse.EMERGENCY_TARGETED: 0.40,
    PolicyResponse.EMERGENCY_BROAD: 0.20,
    PolicyResponse.UNLIMITED: 0.10,
}

# Dimension 4: Contagion breadth → sub-score
CONTAGION_SCORES: dict[ContagionBreadth, float] = {
    ContagionBreadth.SINGLE: 0.85,
    ContagionBreadth.TWO_THREE: 0.55,
    ContagionBreadth.BROAD_DOMESTIC: 0.30,
    ContagionBreadth.GLOBAL_SYSTEMIC: 0.10,
}

# Dimension 5: Duration of acute stress (trading days) → sub-score
DURATION_BRACKETS: list[tuple[float, float]] = [
    # (max_trading_days, sub_score)
    (5.0, 0.85),
    (15.0, 0.60),
    (40.0, 0.40),
    (90.0, 0.20),
    (float("inf"), 0.10),
]


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_drawdown(drawdown_pct: float) -> float:
    """Score S&P 500 peak-to-trough drawdown within 90 days.

    Args:
        drawdown_pct: Absolute drawdown percentage (e.g. 15.0 for a 15% drop).
                      Should be positive.

    Returns:
        Sub-score on [0.10, 0.90] where lower = more severe.
    """
    drawdown_pct = abs(drawdown_pct)
    for threshold, score in DRAWDOWN_BRACKETS:
        if drawdown_pct < threshold:
            return score
    return 0.10  # pragma: no cover — unreachable with inf sentinel


def score_market_dysfunction(level: MarketDysfunction) -> float:
    """Score market functioning disruption (categorical)."""
    return DYSFUNCTION_SCORES[level]


def score_policy_response(level: PolicyResponse) -> float:
    """Score policy response intensity (categorical)."""
    return POLICY_SCORES[level]


def score_contagion_breadth(level: ContagionBreadth) -> float:
    """Score contagion breadth (categorical)."""
    return CONTAGION_SCORES[level]


def score_duration(trading_days: float) -> float:
    """Score duration of acute VIX stress phase.

    Args:
        trading_days: Number of trading days from event until VIX returns
                      to within 1.5σ of its 6-month pre-event mean.

    Returns:
        Sub-score on [0.10, 0.85] where lower = more severe.
    """
    for threshold, score in DURATION_BRACKETS:
        if trading_days < threshold:
            return score
    return 0.10  # pragma: no cover


@dataclass
class CSRInput:
    """Raw inputs for CSR calculation."""
    drawdown_pct: float
    dysfunction: MarketDysfunction
    policy: PolicyResponse
    contagion: ContagionBreadth
    duration_trading_days: float


@dataclass
class CSRResult:
    """Full CSR calculation result with per-dimension breakdown."""
    drawdown_score: float
    dysfunction_score: float
    policy_score: float
    contagion_score: float
    duration_score: float

    @property
    def composite(self) -> float:
        """Equally-weighted average of five dimensions (§13.2.3)."""
        return (
            self.drawdown_score
            + self.dysfunction_score
            + self.policy_score
            + self.contagion_score
            + self.duration_score
        ) / 5.0

    @property
    def expected_mac_range(self) -> tuple[float, float]:
        """CSR composite ± 0.10 (§13.2.3)."""
        c = self.composite
        return (max(0.0, c - 0.10), min(1.0, c + 0.10))

    @property
    def severity_label(self) -> str:
        """Legacy severity label (§13.2.5).

        | Label    | CSR Range  |
        |----------|-----------|
        | Moderate | 0.55–0.80 |
        | High     | 0.40–0.57 |
        | Extreme  | < 0.40    |
        """
        c = self.composite
        if c < 0.40:
            return "Extreme"
        elif c < 0.57:
            return "High"
        else:
            return "Moderate"


def calculate_csr(inputs: CSRInput) -> CSRResult:
    """Calculate full CSR from raw inputs.

    Example:
        >>> inp = CSRInput(
        ...     drawdown_pct=35.0,
        ...     dysfunction=MarketDysfunction.EXTREME,
        ...     policy=PolicyResponse.UNLIMITED,
        ...     contagion=ContagionBreadth.GLOBAL_SYSTEMIC,
        ...     duration_trading_days=120,
        ... )
        >>> result = calculate_csr(inp)
        >>> result.composite  # 0.10 — systemic event
        0.1
    """
    return CSRResult(
        drawdown_score=score_drawdown(inputs.drawdown_pct),
        dysfunction_score=score_market_dysfunction(inputs.dysfunction),
        policy_score=score_policy_response(inputs.policy),
        contagion_score=score_contagion_breadth(inputs.contagion),
        duration_score=score_duration(inputs.duration_trading_days),
    )


# ---------------------------------------------------------------------------
# Legacy-label mapping (§13.2.5)
# ---------------------------------------------------------------------------

SEVERITY_CSR_RANGES: dict[str, tuple[float, float]] = {
    "Moderate": (0.55, 0.80),
    "High": (0.40, 0.57),
    "Extreme": (0.08, 0.40),
}


def validate_csr_independence() -> dict:
    """Return a summary documenting CSR independence from MAC output.

    This is a documentation/audit helper — it enumerates data sources for
    each dimension and confirms none depend on MAC framework computation.

    Returns:
        Dict with dimension names as keys, source descriptions as values.
    """
    return {
        "drawdown": (
            "S&P 500 daily close (FRED SP500 or Shiller composite pre-1957). "
            "Peak-to-trough within 90 calendar days of event."
        ),
        "market_dysfunction": (
            "NYSE circuit breaker records, Fed §13(3) invocations, "
            "FINRA TRACE bid-ask data, primary dealer fails-to-deliver."
        ),
        "policy_response": (
            "Federal Reserve press releases, FOMC minutes, "
            "Treasury announcements, CBO fiscal response estimates."
        ),
        "contagion_breadth": (
            "Bloomberg cross-asset correlations, "
            "BIS cross-border banking flows, "
            "EMBI spreads, cross-currency basis."
        ),
        "duration": (
            "VIXCLS daily (FRED), VXO daily (FRED), "
            "Schwert (1989) monthly estimates pre-1990."
        ),
        "independence_statement": (
            "All five CSR dimensions are derived "
            "entirely from market price data, "
            "observable microstructure events, "
            "public policy announcements, and "
            "cross-asset correlation data. None "
            "require computation of the MAC "
            "score, knowledge of pillar scores, "
            "or any output from the MAC "
            "framework."
        ),
    }
