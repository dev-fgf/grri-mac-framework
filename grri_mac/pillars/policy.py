"""Policy pillar scoring — Binding Constraint Architecture.

Question: Does the central bank have capacity to respond?

Architecture (v6 §4.5):
  Pillar₅ = min(rate_room, inflation, bs_capacity, fiscal_space)
  
  Safeguard: when max(scores) − min(scores) ≤ 0.25 (homogeneously tight),
  revert to weighted average:
    inflation 35%, rate_room 25%, B/S 20%, fiscal 20%

Indicators:
- Policy room (distance from ELB) — operational capacity to cut rates
- Fed balance sheet / GDP — asset-purchase headroom
- Inflation deviation from target — asymmetric: above-target penalised more
- Fiscal debt / GDP — fiscal backstop capacity

Historical proxy support:
- Core PCE (1959+), CPI-U (1947–1959), CPI NSA (1913–1947),
  Rees Cost of Living (1890–1913), Warren-Pearson WPI (1850–1890)
- Era caps: Pre-Fed ≤0.30, Early Fed/Gold ≤0.55, Bretton Woods ≡0.65

Note: We use distance from Effective Lower Bound (ELB) rather than deviation
from an estimated "neutral rate" (r*). This is simpler, uses observable data,
and directly measures what matters: the Fed's operational capacity to cut rates.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..mac.scorer import score_indicator_simple

logger = logging.getLogger(__name__)


@dataclass
class PolicyIndicators:
    """Raw policy indicator values."""

    policy_room_bps: Optional[float] = None  # fed_funds * 100
    fed_balance_sheet_gdp_pct: Optional[float] = None
    core_pce_vs_target_bps: Optional[float] = None
    debt_to_gdp_pct: Optional[float] = None  # Federal debt / GDP
    observation_date: Optional[datetime] = None  # For era-aware caps
    gold_reserve_ratio: Optional[float] = None  # Gold reserves / monetary base (pre-1934)


@dataclass
class PolicyScores:
    """Scored policy indicators."""

    policy_room: float = 0.5
    balance_sheet: float = 0.5
    inflation: float = 0.5
    fiscal_space: float = 0.5  # Debt/GDP constraint
    composite: float = 0.5
    composite_method: str = "min"  # "min" or "weighted_avg"
    era_cap_applied: Optional[float] = None  # If an era cap was binding


# ── Weighted-average fallback weights (v6 §4.5) ─────────────────────────
WEIGHTED_AVG_WEIGHTS = {
    "inflation": 0.35,
    "policy_room": 0.25,
    "balance_sheet": 0.20,
    "fiscal_space": 0.20,
}
# Threshold for switching from min to weighted average
HOMOGENEITY_THRESHOLD = 0.25


class PolicyPillar:
    """Policy pillar calculator — binding constraint architecture."""

    # Thresholds for policy capacity
    THRESHOLDS = {
        "policy_room": {
            # Distance from ELB (0%) in bps — more room is better
            "ample": 150,
            "thin": 50,
            "breach": 25,
        },
        "balance_sheet_gdp": {
            # Fed B/S as % of GDP — lower is better
            "ample": 25,
            "thin": 35,
            "breach": 45,
        },
        "inflation_above": {
            # Deviation ABOVE target — constrains easing directly
            # Asymmetric: tighter thresholds (penalised more)
            "ample": 50,
            "thin": 125,
            "breach": 200,
        },
        "inflation_below": {
            # Deviation BELOW target — deflation risk, less operationally binding
            # Asymmetric: wider thresholds (milder penalty)
            "ample": 75,
            "thin": 200,
            "breach": 350,
        },
        "fiscal_space": {
            # Federal debt / GDP
            "ample": 70,
            "thin": 90,
            "breach": 120,
        },
    }

    # ── Historical era caps (v6 §4.5) ───────────────────────────────────
    # These cap the maximum policy pillar score for structural reasons
    ERA_CAPS = {
        "pre_fed": 0.30,         # No central bank (pre-1913)
        "early_fed_gold": 0.55,  # Early Fed + Gold Standard (1913–1934)
        "bretton_woods": 0.65,   # Fixed exchange rate regime (1944–1971)
    }

    def __init__(self, fred_client=None):
        """Initialize policy pillar.

        Args:
            fred_client: FREDClient instance for fetching data
        """
        self.fred = fred_client

    def fetch_indicators(self) -> PolicyIndicators:
        """Fetch current policy indicators from data sources."""
        indicators = PolicyIndicators()
        indicators.observation_date = datetime.now()

        if self.fred:
            try:
                fed_funds = self.fred.get_fed_funds()
                if fed_funds is not None:
                    indicators.policy_room_bps = fed_funds * 100
            except Exception:
                pass

            try:
                indicators.fed_balance_sheet_gdp_pct = (
                    self.fred.get_fed_balance_sheet_to_gdp()
                )
            except Exception:
                pass

            try:
                indicators.core_pce_vs_target_bps = (
                    self.fred.get_core_pce_vs_target()
                )
            except Exception:
                pass

        return indicators

    def score_policy_room(self, room_bps: float) -> float:
        """Score policy room — more room to cut is better."""
        t = self.THRESHOLDS["policy_room"]
        # Higher is better (more room to cut)
        if room_bps >= t["ample"]:
            return 1.0
        elif room_bps >= t["thin"]:
            return 0.5 + 0.5 * (room_bps - t["thin"]) / (t["ample"] - t["thin"])
        elif room_bps >= t["breach"]:
            return 0.5 * (room_bps - t["breach"]) / (t["thin"] - t["breach"])
        else:
            return 0.0

    def score_balance_sheet(self, bs_gdp_pct: float) -> float:
        """Score Fed balance sheet as % of GDP (lower is better)."""
        t = self.THRESHOLDS["balance_sheet_gdp"]
        return score_indicator_simple(
            bs_gdp_pct,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def score_inflation(self, pce_vs_target_bps: float) -> float:
        """Score inflation deviation — asymmetric (v6 §4.5.3).

        Above-target inflation is penalised more heavily because it
        directly constrains the central bank's capacity to cut rates.
        Below-target deviation (deflation risk) receives a milder penalty
        as it is less operationally binding on easing.

        Args:
            pce_vs_target_bps: Deviation from target in basis points.
                Positive = above target, negative = below target.

        Returns:
            Score between 0.0 (breach) and 1.0 (ample).
        """
        if pce_vs_target_bps >= 0:
            # Above target — tighter thresholds
            t = self.THRESHOLDS["inflation_above"]
            return score_indicator_simple(
                pce_vs_target_bps,
                t["ample"],
                t["thin"],
                t["breach"],
                lower_is_better=True,
            )
        else:
            # Below target — wider thresholds (milder penalty)
            t = self.THRESHOLDS["inflation_below"]
            return score_indicator_simple(
                abs(pce_vs_target_bps),
                t["ample"],
                t["thin"],
                t["breach"],
                lower_is_better=True,
            )

    def score_fiscal_space(self, debt_gdp_pct: float) -> float:
        """Score fiscal space (Debt/GDP) — lower is better."""
        t = self.THRESHOLDS["fiscal_space"]
        return score_indicator_simple(
            debt_gdp_pct,
            t["ample"],
            t["thin"],
            t["breach"],
            lower_is_better=True,
        )

    def _get_era_cap(self, date: Optional[datetime]) -> Optional[float]:
        """Return the era-specific cap on the policy score, if any.

        Args:
            date: Observation date. If None, no cap applied.

        Returns:
            Maximum allowed policy score for the era, or None.
        """
        if date is None:
            return None

        year = date.year

        if year < 1913:
            return self.ERA_CAPS["pre_fed"]
        elif year < 1934:
            return self.ERA_CAPS["early_fed_gold"]
        elif 1944 <= year <= 1971:
            return self.ERA_CAPS["bretton_woods"]

        return None

    def _apply_gold_constraint(
        self, score: float, gold_reserve_ratio: Optional[float],
        date: Optional[datetime],
    ) -> float:
        """Further constrain score if gold reserves are low (pre-1934).

        Under the gold standard, the Fed's practical capacity was limited
        by its gold reserve ratio to notes outstanding.

        Args:
            score: Current policy score (possibly already era-capped)
            gold_reserve_ratio: Gold reserves / monetary base (0-1)
            date: Observation date

        Returns:
            Score, potentially further reduced
        """
        if date is None or gold_reserve_ratio is None:
            return score

        if date.year < 1934 and date.year >= 1913:
            # Required reserve ratio was 40% under Federal Reserve Act
            # Below 45%: constrained, below 40%: severely constrained
            if gold_reserve_ratio < 0.40:
                return min(score, 0.15)
            elif gold_reserve_ratio < 0.45:
                return min(score, 0.35)

        return score

    def calculate(
        self,
        indicators: Optional[PolicyIndicators] = None,
    ) -> PolicyScores:
        """Calculate policy pillar scores using binding constraint architecture.

        Methodology (v6 §4.5):
        1. Score each sub-indicator independently
        2. If score dispersion > 0.25: composite = min(all scores)
           (the weakest link binds — one severely constrained dimension
            prevents effective policy response regardless of others)
        3. If score dispersion ≤ 0.25: composite = weighted average
           (all dimensions similarly tight — use nuanced blend)
        4. Apply historical era caps if applicable

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            PolicyScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = PolicyScores()
        available_scores = {}

        # ── Score individual dimensions ──────────────────────────────
        if indicators.policy_room_bps is not None:
            scores.policy_room = self.score_policy_room(indicators.policy_room_bps)
            available_scores["policy_room"] = scores.policy_room

        if indicators.fed_balance_sheet_gdp_pct is not None:
            scores.balance_sheet = self.score_balance_sheet(
                indicators.fed_balance_sheet_gdp_pct
            )
            available_scores["balance_sheet"] = scores.balance_sheet

        if indicators.core_pce_vs_target_bps is not None:
            scores.inflation = self.score_inflation(
                indicators.core_pce_vs_target_bps
            )
            available_scores["inflation"] = scores.inflation

        if indicators.debt_to_gdp_pct is not None:
            scores.fiscal_space = self.score_fiscal_space(
                indicators.debt_to_gdp_pct
            )
            available_scores["fiscal_space"] = scores.fiscal_space

        # ── Binding constraint composite ─────────────────────────────
        if len(available_scores) > 0:
            score_values = list(available_scores.values())
            dispersion = max(score_values) - min(score_values)

            if len(available_scores) == 1:
                # Single indicator — use it directly
                scores.composite = score_values[0]
                scores.composite_method = "single"
            elif dispersion > HOMOGENEITY_THRESHOLD:
                # High dispersion: one dimension dominates → min (binding)
                scores.composite = min(score_values)
                scores.composite_method = "min"
            else:
                # Low dispersion: homogeneously tight → weighted average
                weighted_sum = 0.0
                weight_sum = 0.0
                for name, val in available_scores.items():
                    w = WEIGHTED_AVG_WEIGHTS.get(name, 0.25)
                    weighted_sum += val * w
                    weight_sum += w
                scores.composite = weighted_sum / weight_sum if weight_sum > 0 else 0.5
                scores.composite_method = "weighted_avg"
        else:
            scores.composite = 0.5
            scores.composite_method = "default"

        # ── Historical era caps ──────────────────────────────────────
        era_cap = self._get_era_cap(indicators.observation_date)
        if era_cap is not None and scores.composite > era_cap:
            scores.composite = era_cap
            scores.era_cap_applied = era_cap

        # Gold standard constraint (1913–1934)
        scores.composite = self._apply_gold_constraint(
            scores.composite,
            indicators.gold_reserve_ratio,
            indicators.observation_date,
        )

        return scores

    def get_score(self) -> float:
        """Get composite policy score."""
        return self.calculate().composite
