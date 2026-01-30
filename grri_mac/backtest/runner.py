"""Backtest runner for MAC framework.

Calculates MAC scores over historical periods and validates against crisis events.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import pandas as pd

from ..data.fred import FREDClient
from ..pillars.liquidity import LiquidityPillar, LiquidityIndicators
from ..pillars.valuation import ValuationPillar, ValuationIndicators
from ..pillars.volatility import VolatilityPillar, VolatilityIndicators
from ..pillars.policy import PolicyPillar, PolicyIndicators
from ..pillars.positioning import PositioningPillar, PositioningIndicators
from ..pillars.contagion import ContagionPillar, ContagionIndicators
from ..mac.composite import calculate_mac, get_mac_interpretation
from .crisis_events import CRISIS_EVENTS, get_crisis_for_date


@dataclass
class BacktestPoint:
    """A single point in the backtest."""

    date: datetime
    mac_score: float
    pillar_scores: dict[str, float]
    breach_flags: List[str]
    interpretation: str
    crisis_event: Optional[str] = None  # Name of crisis if in crisis period
    data_quality: str = "excellent"  # excellent, good, fair, poor


class BacktestRunner:
    """Run historical backtests of the MAC framework."""

    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize backtest runner.

        Args:
            fred_api_key: FRED API key (or will use FRED_API_KEY env var)
        """
        self.fred = FREDClient(fred_api_key)

        # Initialize pillars
        self.liquidity = LiquidityPillar(fred_client=self.fred)
        self.valuation = ValuationPillar(fred_client=self.fred)
        self.volatility = VolatilityPillar(fred_client=self.fred)
        self.policy = PolicyPillar(fred_client=self.fred)
        self.positioning = PositioningPillar()  # Uses synthetic for now
        self.contagion = ContagionPillar()  # Placeholder scores for now

    def calculate_mac_for_date(self, date: datetime) -> BacktestPoint:
        """
        Calculate MAC score for a specific date.

        Args:
            date: Date to calculate MAC for

        Returns:
            BacktestPoint with MAC score and metadata
        """
        # Fetch indicators for this date
        liquidity_indicators = self._fetch_liquidity_indicators(date)
        valuation_indicators = self._fetch_valuation_indicators(date)
        volatility_indicators = self._fetch_volatility_indicators(date)
        policy_indicators = self._fetch_policy_indicators(date)
        positioning_indicators = self._fetch_positioning_indicators(date)
        contagion_indicators = self._fetch_contagion_indicators(date)

        # Calculate pillar scores
        liquidity_scores = self.liquidity.calculate(liquidity_indicators)
        valuation_scores = self.valuation.calculate(valuation_indicators)
        volatility_scores = self.volatility.calculate(volatility_indicators)
        policy_scores = self.policy.calculate(policy_indicators)
        positioning_scores = self.positioning.calculate(positioning_indicators)
        contagion_scores = self.contagion.calculate(contagion_indicators)

        # Aggregate into pillar dict
        pillar_scores = {
            "liquidity": liquidity_scores.composite,
            "valuation": valuation_scores.composite,
            "positioning": positioning_scores.composite,
            "volatility": volatility_scores.composite,
            "policy": policy_scores.composite,
            "contagion": contagion_scores.composite,
        }

        # Calculate MAC composite
        mac_result = calculate_mac(pillar_scores)

        # Check if in crisis period
        crisis = get_crisis_for_date(date)
        crisis_name = crisis.name if crisis else None

        # Determine data quality based on date
        data_quality = self._assess_data_quality(date)

        return BacktestPoint(
            date=date,
            mac_score=mac_result.mac_score,
            pillar_scores=pillar_scores,
            breach_flags=mac_result.breach_flags,
            interpretation=get_mac_interpretation(mac_result.mac_score),
            crisis_event=crisis_name,
            data_quality=data_quality,
        )

    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        frequency: str = "weekly"  # daily, weekly, monthly
    ) -> pd.DataFrame:
        """
        Run backtest over a date range.

        Args:
            start_date: Start date
            end_date: End date
            frequency: Calculation frequency

        Returns:
            DataFrame with backtest results
        """
        results = []

        # Generate date range based on frequency
        if frequency == "daily":
            delta = timedelta(days=1)
        elif frequency == "weekly":
            delta = timedelta(days=7)
        elif frequency == "monthly":
            delta = timedelta(days=30)
        else:
            raise ValueError(f"Unknown frequency: {frequency}")

        current_date = start_date
        while current_date <= end_date:
            try:
                point = self.calculate_mac_for_date(current_date)
                results.append(point)
                print(f"[OK] {current_date.date()}: MAC={point.mac_score:.2f} {point.interpretation}")

            except Exception as e:
                print(f"[FAILED] {current_date.date()}: Error - {str(e)}")

            current_date += delta

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "date": p.date,
                "mac_score": p.mac_score,
                "liquidity": p.pillar_scores["liquidity"],
                "valuation": p.pillar_scores["valuation"],
                "positioning": p.pillar_scores["positioning"],
                "volatility": p.pillar_scores["volatility"],
                "policy": p.pillar_scores["policy"],
                "contagion": p.pillar_scores["contagion"],
                "interpretation": p.interpretation,
                "crisis_event": p.crisis_event,
                "data_quality": p.data_quality,
            }
            for p in results
        ])

        df.set_index("date", inplace=True)
        return df

    def _fetch_liquidity_indicators(self, date: datetime) -> LiquidityIndicators:
        """Fetch liquidity indicators for a date."""
        indicators = LiquidityIndicators()

        try:
            # Use date-aware liquidity spread (SOFR-IORB or LIBOR-OIS)
            indicators.sofr_iorb_spread_bps = self.fred.get_liquidity_spread(date)
        except Exception as e:
            print(f"Warning: Could not fetch liquidity spread for {date}: {e}")

        try:
            indicators.cp_treasury_spread_bps = self.fred.get_cp_treasury_spread(date)
        except Exception as e:
            print(f"Warning: Could not fetch CP spread for {date}: {e}")

        return indicators

    def _fetch_valuation_indicators(self, date: datetime) -> ValuationIndicators:
        """Fetch valuation indicators for a date."""
        indicators = ValuationIndicators()

        try:
            indicators.term_premium_10y_bps = self.fred.get_term_premium_10y(date)
        except Exception as e:
            print(f"Warning: Could not fetch term premium for {date}: {e}")

        try:
            indicators.ig_oas_bps = self.fred.get_ig_oas(date)
        except Exception as e:
            print(f"Warning: Could not fetch IG OAS for {date}: {e}")

        try:
            indicators.hy_oas_bps = self.fred.get_hy_oas(date)
        except Exception as e:
            print(f"Warning: Could not fetch HY OAS for {date}: {e}")

        return indicators

    def _fetch_volatility_indicators(self, date: datetime) -> VolatilityIndicators:
        """Fetch volatility indicators for a date."""
        indicators = VolatilityIndicators()

        try:
            indicators.vix = self.fred.get_vix(date)
        except Exception as e:
            print(f"Warning: Could not fetch VIX for {date}: {e}")

        return indicators

    def _fetch_policy_indicators(self, date: datetime) -> PolicyIndicators:
        """Fetch policy indicators for a date."""
        indicators = PolicyIndicators()

        try:
            # Policy room = distance from ELB = fed funds * 100
            fed_funds = self.fred.get_fed_funds(date)
            if fed_funds is not None:
                indicators.policy_room_bps = fed_funds * 100
        except Exception as e:
            print(f"Warning: Could not fetch fed funds for {date}: {e}")

        # Balance sheet and inflation would require more complex date handling
        # For now, leave as None

        return indicators

    def _fetch_positioning_indicators(self, date: datetime) -> PositioningIndicators:
        """Fetch positioning indicators for a date."""
        # Positioning pillar uses synthetic estimates for now
        # Would need CFTC COT data implementation
        return PositioningIndicators()

    def _fetch_contagion_indicators(self, date: datetime) -> ContagionIndicators:
        """Fetch contagion indicators for a date."""
        # Contagion pillar placeholder - would need BIS/IMF/ECB data
        # For now, return default (neutral scores)
        return ContagionIndicators()

    def _assess_data_quality(self, date: datetime) -> str:
        """
        Assess data quality for a specific date.

        Returns:
            "excellent", "good", "fair", or "poor"
        """
        if date >= datetime(2018, 4, 3):
            # SOFR era: excellent data
            return "excellent"
        elif date >= datetime(2011, 10, 3):
            # LIBOR-OIS era, SVXY available: good
            return "good"
        elif date >= datetime(2006, 1, 1):
            # LIBOR-OIS era, synthetic positioning: fair
            return "fair"
        else:
            # Pre-2006: limited data
            return "poor"

    def generate_validation_report(self, backtest_df: pd.DataFrame) -> dict:
        """
        Generate validation metrics for backtest results.

        Args:
            backtest_df: DataFrame from run_backtest()

        Returns:
            Dict with validation metrics
        """
        # Get dates in crisis periods
        crisis_dates = backtest_df[backtest_df["crisis_event"].notna()]
        non_crisis_dates = backtest_df[backtest_df["crisis_event"].isna()]

        # Calculate average MAC during vs. outside crises
        avg_mac_crisis = crisis_dates["mac_score"].mean() if len(crisis_dates) > 0 else None
        avg_mac_non_crisis = non_crisis_dates["mac_score"].mean() if len(non_crisis_dates) > 0 else None

        # Count warnings before crises
        warnings = 0
        total_crises = 0

        for crisis in CRISIS_EVENTS:
            if crisis.start_date < backtest_df.index.min() or crisis.end_date > backtest_df.index.max():
                continue  # Crisis outside backtest range

            total_crises += 1

            # Look for warning in 90 days before crisis
            warning_window_start = crisis.start_date - timedelta(days=90)
            warning_window = backtest_df[
                (backtest_df.index >= warning_window_start) &
                (backtest_df.index < crisis.start_date)
            ]

            # Warning = MAC < 0.6
            if len(warning_window) > 0 and (warning_window["mac_score"] < 0.6).any():
                warnings += 1

        true_positive_rate = warnings / total_crises if total_crises > 0 else 0

        return {
            "total_points": len(backtest_df),
            "crisis_points": len(crisis_dates),
            "non_crisis_points": len(non_crisis_dates),
            "avg_mac_during_crisis": avg_mac_crisis,
            "avg_mac_non_crisis": avg_mac_non_crisis,
            "crises_evaluated": total_crises,
            "crises_with_warning": warnings,
            "true_positive_rate": true_positive_rate,
            "avg_mac_overall": backtest_df["mac_score"].mean(),
            "min_mac": backtest_df["mac_score"].min(),
            "max_mac": backtest_df["mac_score"].max(),
        }
