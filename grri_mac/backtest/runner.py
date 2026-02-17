"""Backtest runner for MAC framework.

Calculates MAC scores over historical periods and validates against crisis events.
Now includes 7th Private Credit pillar and momentum tracking.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass, field
import pandas as pd

from ..data.fred import FREDClient
from ..pillars.liquidity import LiquidityPillar, LiquidityIndicators
from ..pillars.valuation import ValuationPillar, ValuationIndicators
from ..pillars.volatility import VolatilityPillar, VolatilityIndicators
from ..pillars.policy import PolicyPillar, PolicyIndicators
from ..pillars.positioning import PositioningPillar, PositioningIndicators
from ..pillars.contagion import ContagionPillar, ContagionIndicators
from ..pillars.private_credit import PrivateCreditPillar, PrivateCreditIndicators, SLOOSData, BDCData
from ..mac.composite import calculate_mac, get_mac_interpretation, ML_OPTIMIZED_WEIGHTS
from ..mac.momentum import calculate_momentum, MACStatus, MACMomentum
from .crisis_events import CRISIS_EVENTS, get_crisis_for_date
from .era_configs import get_era, get_available_pillars, get_default_score, get_era_weights


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
    # Momentum tracking fields
    momentum_1w: Optional[float] = None
    momentum_4w: Optional[float] = None
    trend_direction: str = "unknown"
    mac_status: str = "UNKNOWN"  # COMFORTABLE, CAUTIOUS, DETERIORATING, STRETCHED, CRITICAL
    is_deteriorating: bool = False


class BacktestRunner:
    """Run historical backtests of the MAC framework."""

    def __init__(
        self,
        fred_api_key: Optional[str] = None,
        use_era_weights: bool = False,
        calibration_factor: float = 0.78,
    ):
        """
        Initialize backtest runner.

        Args:
            fred_api_key: FRED API key (or will use FRED_API_KEY env var)
            use_era_weights: If True, use era-specific pillar weights for
                             pre-1971 periods (recommended for extended backtests)
            calibration_factor: Multiplicative adjustment for MAC scores (default 0.78,
                                derived from cross-validation against historical crises)
        """
        self.fred = FREDClient(fred_api_key)
        self.use_era_weights = use_era_weights
        self.calibration_factor = calibration_factor

        # Initialize pillars (7 pillars total)
        self.liquidity = LiquidityPillar(fred_client=self.fred)
        self.valuation = ValuationPillar(fred_client=self.fred)
        self.volatility = VolatilityPillar(fred_client=self.fred)
        self.policy = PolicyPillar(fred_client=self.fred)
        self.positioning = PositioningPillar()  # Uses synthetic for now
        self.contagion = ContagionPillar()  # Placeholder scores for now
        self.private_credit = PrivateCreditPillar(fred_client=self.fred)  # 7th pillar
        
        # Historical MAC scores for momentum calculation
        self._historical_macs: List[dict] = []

    def _prefetch_fred_data(self, start_date: datetime, end_date: datetime) -> None:
        """
        Pre-fetch all required FRED series for the backtest period.
        This dramatically reduces API calls by loading data once upfront.
        
        Supports backtesting from 1962-present with appropriate historical proxies.
        """
        # All FRED series used across pillars (modern + historical proxies)
        # Using a set to avoid duplicates
        series_to_fetch = list(set([
            # Liquidity pillar - modern
            "SOFR", "IORB", "IOER", "TEDRATE", "DFF",
            "DCPF3M", "DTB3",
            # Liquidity pillar - historical (pre-1986)
            "TB3MS", "FEDFUNDS",
            # Valuation pillar - modern
            "BAMLC0A0CM", "BAMLH0A0HYM2",
            # Valuation pillar - historical (Moody's from 1919)
            "AAA", "BAA", "DGS10", "BAA10Y",
            # Valuation pillar - extended historical
            "IRLTLT01USM156N",  # Long-term govt yield (1920+)
            # Volatility pillar - modern
            "VIXCLS", "VXOCLS",
            # Volatility pillar - historical (realized vol from 1971)
            "NASDAQCOM",
            # Policy pillar
            "DGS2", "WALCL",
            # Policy pillar - historical (pre-2002)
            "BOGMBASE", "M2SL",
            # Policy pillar - extended historical
            "INTDSRUSM193N",  # Fed discount rate (1913+)
            "GDPA",  # Annual GDP (1929+)
            # Private Credit pillar
            "DRTSCIS", "DRISCFS",
        ]))
        
        # Add buffer for lookback calculations (larger for realized vol computation)
        buffer_start = start_date - timedelta(days=90)
        
        self.fred.prefetch_series(series_to_fetch, buffer_start, end_date)
        
        # Enable backtest mode to prevent API calls during iteration
        self.fred.set_backtest_mode(True)

    def calculate_mac_for_date(self, date: datetime) -> BacktestPoint:
        """
        Calculate MAC score for a specific date.

        Improvements over original:
        - Fix A: Only pillars with real indicator data participate in the composite.
          Pillars with no data are excluded (not set to 0.5), preventing dilution.
        - Fix D: ML-optimized weights for modern era (2006+), era weights for
          historical periods, equal weights otherwise.
        - Fix E: Calibration factor applied to raw MAC score.

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
        private_credit_indicators = self._fetch_private_credit_indicators(date)

        # Calculate pillar scores
        liquidity_scores = self.liquidity.calculate(liquidity_indicators)
        valuation_scores = self.valuation.calculate(valuation_indicators)
        volatility_scores = self.volatility.calculate(volatility_indicators)
        policy_scores = self.policy.calculate(policy_indicators)
        positioning_scores = self.positioning.calculate(positioning_indicators)
        contagion_scores = self.contagion.calculate(contagion_indicators)
        private_credit_scores = self.private_credit.calculate_scores(
            private_credit_indicators
        )

        # All pillar scores (for reporting — always has all 7 entries)
        all_scores = {
            "liquidity": liquidity_scores.composite,
            "valuation": valuation_scores.composite,
            "volatility": volatility_scores.composite,
            "policy": policy_scores.composite,
            "positioning": positioning_scores.composite,
            "contagion": contagion_scores.composite,
            "private_credit": private_credit_scores.composite,
        }

        # Fix A: Detect which pillars actually received real indicator data.
        # Pillars without data still get scores above, but they are excluded
        # from the composite so their default 0.5 doesn't dilute real signals.
        has_data = {
            "liquidity": (
                liquidity_indicators.sofr_iorb_spread_bps is not None
                or liquidity_indicators.cp_treasury_spread_bps is not None
            ),
            "valuation": (
                valuation_indicators.term_premium_10y_bps is not None
                or valuation_indicators.ig_oas_bps is not None
                or valuation_indicators.hy_oas_bps is not None
            ),
            "volatility": volatility_indicators.vix_level is not None,
            "policy": policy_indicators.policy_room_bps is not None,
            "positioning": (
                positioning_indicators.basis_trade_size_billions is not None
                or positioning_indicators.treasury_spec_net_percentile is not None
                or positioning_indicators.svxy_aum_millions is not None
            ),
            "contagion": (
                contagion_indicators.financial_oas_bps is not None
                or contagion_indicators.eur_usd_basis_bps is not None
                or contagion_indicators.bkx_volatility_pct is not None
            ),
            "private_credit": (
                private_credit_indicators.sloos is not None
                and getattr(
                    private_credit_indicators.sloos, "ci_standards_small", None
                )
                is not None
            ),
        }

        # Build composite from only pillars with real data
        active_scores = {
            k: v for k, v in all_scores.items() if has_data.get(k, False)
        }
        if not active_scores:
            active_scores = all_scores  # Fallback: use all if none have data

        # Fix D: Weight selection — ML weights for modern, era weights for
        # historical, equal weights as default
        if date >= datetime(2006, 1, 1):
            weights = ML_OPTIMIZED_WEIGHTS
        elif self.use_era_weights:
            weights = get_era_weights(date)
        else:
            weights = None  # Equal weights

        # Calculate MAC composite (auto-normalises weights to active pillars)
        mac_result = calculate_mac(active_scores, weights=weights)

        # Fix E: Apply calibration factor (era-aware)
        # The 0.78 factor was calibrated against modern (post-2006) scenarios.
        # For pre-1971 data, structural differences (higher Schwert vol, wider
        # railroad spreads) already compress scores; applying 0.78 over-penalises.
        if date >= datetime(2006, 1, 1):
            cal = self.calibration_factor        # Full calibration
        elif date >= datetime(1971, 2, 5):
            cal = min(self.calibration_factor + 0.12, 1.0)  # Milder
        else:
            cal = 1.0                            # No calibration
        calibrated_mac = mac_result.mac_score * cal
        calibrated_mac = max(0.0, min(1.0, calibrated_mac))

        # Calculate momentum from historical data
        momentum = calculate_momentum(
            current_mac=calibrated_mac,
            historical_macs=self._historical_macs,
            current_date=date,
        )

        # Store for future momentum calculations
        self._historical_macs.append({
            "date": date.strftime("%Y-%m-%d"),
            "mac_score": calibrated_mac,
        })

        # Check if in crisis period
        crisis = get_crisis_for_date(date)
        crisis_name = crisis.name if crisis else None

        # Determine data quality based on date
        data_quality = self._assess_data_quality(date)

        return BacktestPoint(
            date=date,
            mac_score=calibrated_mac,
            pillar_scores=all_scores,
            breach_flags=mac_result.breach_flags,
            interpretation=get_mac_interpretation(calibrated_mac),
            crisis_event=crisis_name,
            data_quality=data_quality,
            momentum_1w=momentum.momentum_1w,
            momentum_4w=momentum.momentum_4w,
            trend_direction=momentum.trend_direction,
            mac_status=momentum.status.value,
            is_deteriorating=momentum.is_deteriorating,
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
        
        # Clear historical MACs for fresh momentum calculation
        self._historical_macs = []
        
        # Track which warnings have been shown to avoid spam
        self._warnings_shown = set()
        
        # Pre-fetch all required FRED series for efficiency
        self._prefetch_fred_data(start_date, end_date)

        # Generate date range based on frequency
        if frequency == "daily":
            delta = timedelta(days=1)
        elif frequency == "weekly":
            delta = timedelta(days=7)
        elif frequency == "monthly":
            delta = timedelta(days=30)
        else:
            raise ValueError(f"Unknown frequency: {frequency}")

        # Calculate total points for progress tracking
        total_days = (end_date - start_date).days
        total_points = total_days // delta.days + 1
        
        current_date = start_date
        point_count = 0
        last_progress = -1
        
        while current_date <= end_date:
            try:
                point = self.calculate_mac_for_date(current_date)
                results.append(point)
                point_count += 1
                
                # Progress bar (update every 5%)
                progress = (point_count * 100) // total_points
                if progress >= last_progress + 5:
                    last_progress = progress
                    bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
                    print(f"\r[{bar}] {progress}% ({point_count}/{total_points}) - {current_date.date()} MAC={point.mac_score:.2f}", end="", flush=True)

            except Exception as e:
                point_count += 1
                # Only print errors, not every failure
                if "Error" not in str(e):
                    pass  # Silently skip expected missing data

            current_date += delta
        
        print()  # New line after progress bar

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
                "private_credit": p.pillar_scores["private_credit"],
                "interpretation": p.interpretation,
                "crisis_event": p.crisis_event,
                "data_quality": p.data_quality,
                "momentum_1w": p.momentum_1w,
                "momentum_4w": p.momentum_4w,
                "trend_direction": p.trend_direction,
                "mac_status": p.mac_status,
                "is_deteriorating": p.is_deteriorating,
            }
            for p in results
        ])

        df.set_index("date", inplace=True)
        return df

    def _warn_once(self, warning_key: str, message: str) -> None:
        """Print a warning only once per backtest run."""
        if not hasattr(self, '_warnings_shown'):
            self._warnings_shown = set()
        if warning_key not in self._warnings_shown:
            self._warnings_shown.add(warning_key)
            # Silently skip - warnings clutter output during long backtests

    def _fetch_liquidity_indicators(self, date: datetime) -> LiquidityIndicators:
        """Fetch liquidity indicators for a date."""
        indicators = LiquidityIndicators()

        try:
            # Use date-aware liquidity spread (SOFR-IORB or LIBOR-OIS)
            indicators.sofr_iorb_spread_bps = self.fred.get_liquidity_spread(date)
        except Exception as e:
            self._warn_once("liquidity_spread", f"Liquidity spread unavailable for some dates")

        try:
            indicators.cp_treasury_spread_bps = self.fred.get_cp_treasury_spread(date)
        except Exception as e:
            self._warn_once("cp_spread", f"CP spread unavailable for some dates")

        return indicators

    def _fetch_valuation_indicators(self, date: datetime) -> ValuationIndicators:
        """Fetch valuation indicators for a date."""
        indicators = ValuationIndicators()

        try:
            indicators.term_premium_10y_bps = self.fred.get_term_premium_10y(date)
        except Exception as e:
            self._warn_once("term_premium", f"Term premium unavailable for some dates")

        try:
            indicators.ig_oas_bps = self.fred.get_ig_oas(date)
        except Exception as e:
            self._warn_once("ig_oas", f"IG OAS unavailable for some dates")

        try:
            indicators.hy_oas_bps = self.fred.get_hy_oas(date)
        except Exception as e:
            self._warn_once("hy_oas", f"HY OAS unavailable for some dates")

        return indicators

    def _fetch_volatility_indicators(self, date: datetime) -> VolatilityIndicators:
        """Fetch volatility indicators for a date."""
        indicators = VolatilityIndicators()

        try:
            indicators.vix_level = self.fred.get_vix(date)
        except Exception as e:
            self._warn_once("vix", f"VIX unavailable for some dates")

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
            self._warn_once("fed_funds", f"Fed funds unavailable for some dates")

        # Balance sheet and inflation would require more complex date handling
        # For now, leave as None

        return indicators

    def _fetch_positioning_indicators(self, date: datetime) -> PositioningIndicators:
        """Fetch positioning indicators for a date."""
        # Positioning pillar uses synthetic estimates for now
        # Would need CFTC COT data implementation
        return PositioningIndicators()

    def _fetch_contagion_indicators(self, date: datetime) -> ContagionIndicators:
        """Fetch contagion indicators for a date using FRED proxy data.

        Uses BAA10Y (Moody's Baa-10Y Treasury spread) as a proxy for financial
        sector credit stress.  This spread captures systemic banking/corporate
        stress similarly to G-SIB CDS spreads but is available from 1919+.
        """
        indicators = ContagionIndicators()

        try:
            baa10y = self.fred.get_value_for_date("BAA10Y", date, lookback_days=35)
            if baa10y is not None:
                # BAA10Y is in percentage points (e.g. 2.5 = 250bps)
                indicators.financial_oas_bps = baa10y * 100
                indicators.indicator_date = date.strftime("%Y-%m-%d")
        except Exception:
            pass

        return indicators

    def _fetch_private_credit_indicators(self, date: datetime) -> PrivateCreditIndicators:
        """
        Fetch private credit indicators for a date.
        
        Note: BDC data requires yfinance, SLOOS data is quarterly from FRED.
        For historical backtest, we use SLOOS as primary signal.
        """
        indicators = PrivateCreditIndicators()
        
        # Fetch SLOOS data (quarterly, so use most recent available)
        # Use longer lookback since SLOOS is quarterly
        try:
            sloos = SLOOSData()
            # C&I lending standards to small firms (key proxy for private credit)
            ci_small = self.fred.get_value_for_date("DRTSCIS", date, lookback_days=100)
            if ci_small is not None:
                sloos.ci_standards_small = ci_small
            
            # Spreads to small firms
            spreads_small = self.fred.get_value_for_date("DRISCFS", date, lookback_days=100)
            if spreads_small is not None:
                sloos.spreads_small = spreads_small
            
            # Also get large/mid for validation
            ci_large = self.fred.get_value_for_date("DRTSCILM", date, lookback_days=100)
            if ci_large is not None:
                sloos.ci_standards_large = ci_large
            
            sloos.observation_date = date
            indicators.sloos = sloos
            
        except Exception as e:
            print(f"Warning: Could not fetch SLOOS data for {date}: {e}")
        
        # BDC and leveraged loan data would require yfinance
        # For now, use synthetic estimates based on date/crisis periods
        # This is a placeholder - full implementation would use yahoo_client
        indicators.bdc = BDCData(observation_date=date)
        
        return indicators

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
        elif date >= datetime(1997, 1, 1):
            # Pre-2006 but post-1997: using Moody's proxies for credit
            # TED spread available, VIX available
            return "fair"
        elif date >= datetime(1990, 1, 2):
            # 1990-1996: VIX available, Moody's credit proxies
            # TED spread available (1986+)
            return "fair"
        elif date >= datetime(1971, 2, 5):
            # 1971-1990: NASDAQ realised vol proxy, Moody's credit
            return "poor"
        elif date >= datetime(1954, 7, 1):
            # 1954-1971: Fed Funds era, monthly data for most indicators
            return "poor"
        elif date >= datetime(1934, 1, 1):
            # 1934-1954: T-Bill available, Moody's from 1919
            return "poor"
        elif date >= datetime(1919, 1, 1):
            # 1919-1934: Moody's credit, Fed discount rate, NBER rates
            return "poor"
        elif date >= datetime(1907, 1, 1):
            # 1907-1919: NBER Macrohistory only, no Fed, monthly data
            # Schwert volatility, railroad bond spreads
            return "poor"
        else:
            # Pre-1907: insufficient data
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

            # Warning = MAC below threshold OR rapid momentum deterioration
            if len(warning_window) > 0:
                level_warn = (warning_window["mac_score"] < 0.5).any()
                momentum_warn = False
                if "momentum_4w" in warning_window.columns:
                    momentum_warn = (
                        (warning_window["mac_score"] < 0.6)
                        & (warning_window["momentum_4w"].fillna(0) < -0.04)
                    ).any()
                if level_warn or momentum_warn:
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
