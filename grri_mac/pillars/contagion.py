"""International Contagion pillar scoring.

Question: Are cross-border transmission channels stable?

Sub-indicators:
- Cross-currency basis (EUR/USD, JPY/USD, GBP/USD)
- TARGET2 imbalances (Eurozone only)
- EM reserve coverage (Guidotti-Greenspan rule)
- Cross-border banking flows (BIS locational banking stats)
"""

from dataclasses import dataclass
from typing import Optional

from ..mac.scorer import score_indicator_simple


@dataclass
class ContagionIndicators:
    """Raw international contagion indicator values."""

    # Cross-currency basis (in basis points, negative = dollar funding stress)
    eur_usd_basis_bps: Optional[float] = None
    jpy_usd_basis_bps: Optional[float] = None
    gbp_usd_basis_bps: Optional[float] = None

    # TARGET2 imbalances (Eurozone only)
    target2_imbalance_eur_billions: Optional[float] = None
    eurozone_gdp_eur_trillions: Optional[float] = None

    # EM reserve coverage
    fx_reserves_usd_billions: Optional[float] = None
    short_term_external_debt_usd_billions: Optional[float] = None

    # Cross-border banking flows
    cross_border_flow_change_billions: Optional[float] = None
    world_gdp_trillions: Optional[float] = None


@dataclass
class ContagionScores:
    """Scored international contagion indicators."""

    cross_currency_basis: float = 0.5
    target2: float = 0.5
    reserve_coverage: float = 0.5
    cross_border_flows: float = 0.5
    composite: float = 0.5


class ContagionPillar:
    """International Contagion pillar calculator."""

    # Thresholds from specification
    THRESHOLDS = {
        "cross_currency_basis": {
            # Absolute deviation from zero (symmetric around 0)
            "ample": 15,    # < 15 bps absolute
            "thin": 30,     # 15-30 bps
            "stretched": 60,  # 30-60 bps
            "critical": 100,  # > 60 bps
        },
        "target2_pct_gdp": {
            # TARGET2 imbalances as % of Eurozone GDP
            "ample": 5,      # < 5% (normal)
            "thin": 10,      # 5-10%
            "stretched": 20,  # 10-20%
            "critical": 30,   # > 20%
        },
        "reserve_coverage_ratio": {
            # FX reserves / short-term external debt (%)
            "ample": 150,    # > 150% (comfortable buffer)
            "thin": 125,     # 125-150%
            "stretched": 100,  # 100-125% (meets Guidotti-Greenspan)
            "critical": 75,   # < 100% (vulnerable)
        },
        "cross_border_flow_pct_gdp": {
            # Quarterly flow change as % of GDP
            # Negative = outflows (sudden stop), positive = inflows
            "ample_low": -0.5,   # Minor outflows ok
            "ample_high": 1.5,   # Normal inflows
            "thin_low": -1.0,
            "thin_high": 3.0,
            "stretched_low": -2.0,  # Credit crunch
            "stretched_high": 5.0,  # Boom-bust risk
            "critical_low": -4.0,   # Sudden stop
            "critical_high": 7.0,   # Unsustainable inflows
        },
    }

    def __init__(self, bis_client=None, imf_client=None, ecb_client=None):
        """
        Initialize contagion pillar.

        Args:
            bis_client: BIS client for cross-border flows
            imf_client: IMF client for reserve/debt data
            ecb_client: ECB client for TARGET2 data
        """
        self.bis = bis_client
        self.imf = imf_client
        self.ecb = ecb_client

    def fetch_indicators(self) -> ContagionIndicators:
        """Fetch current contagion indicators from data sources."""
        indicators = ContagionIndicators()

        # Cross-currency basis (would come from Polygon.io or BIS quarterly)
        # For now, these are placeholders - will be implemented with data clients

        # TARGET2 (from ECB)
        if self.ecb:
            try:
                target2_data = self.ecb.get_target2_balances()
                indicators.target2_imbalance_eur_billions = sum(
                    abs(balance) for balance in target2_data.values()
                )
                indicators.eurozone_gdp_eur_trillions = self.ecb.get_eurozone_gdp()
            except Exception:
                pass

        # Reserve coverage (from IMF)
        if self.imf:
            try:
                # Aggregate for G20 EMs
                indicators.fx_reserves_usd_billions = self.imf.get_em_reserves()
                indicators.short_term_external_debt_usd_billions = self.imf.get_em_debt()
            except Exception:
                pass

        # Cross-border flows (from BIS)
        if self.bis:
            try:
                indicators.cross_border_flow_change_billions = self.bis.get_flow_change()
                indicators.world_gdp_trillions = self.bis.get_world_gdp()
            except Exception:
                pass

        return indicators

    def score_cross_currency_basis(self, basis_bps_list: list[float]) -> float:
        """
        Score cross-currency basis (average absolute deviation).

        Args:
            basis_bps_list: List of basis values in bps (negative = stress)

        Returns:
            Score 0-1 (higher = more stress)
        """
        if not basis_bps_list:
            return 0.5  # Neutral if no data

        # Calculate average absolute deviation from zero
        avg_abs_basis = sum(abs(b) for b in basis_bps_list) / len(basis_bps_list)

        t = self.THRESHOLDS["cross_currency_basis"]

        if avg_abs_basis < t["ample"]:
            # Ample: 0-15 bps → score 0.0-0.2
            return 0.2 * (avg_abs_basis / t["ample"])
        elif avg_abs_basis < t["thin"]:
            # Thin: 15-30 bps → score 0.2-0.35
            frac = (avg_abs_basis - t["ample"]) / (t["thin"] - t["ample"])
            return 0.2 + 0.15 * frac
        elif avg_abs_basis < t["stretched"]:
            # Stretched: 30-60 bps → score 0.35-0.65
            frac = (avg_abs_basis - t["thin"]) / (t["stretched"] - t["thin"])
            return 0.35 + 0.30 * frac
        elif avg_abs_basis < t["critical"]:
            # Critical approach: 60-100 bps → score 0.65-1.0
            frac = (avg_abs_basis - t["stretched"]) / (t["critical"] - t["stretched"])
            return 0.65 + 0.35 * frac
        else:
            # Beyond critical: > 100 bps → score 1.0
            return 1.0

    def score_target2(self, imbalance_pct_gdp: float) -> float:
        """
        Score TARGET2 imbalances as % of Eurozone GDP.

        Args:
            imbalance_pct_gdp: Gross imbalances as % of GDP

        Returns:
            Score 0-1 (higher = more fragmentation)
        """
        t = self.THRESHOLDS["target2_pct_gdp"]
        return score_indicator_simple(
            imbalance_pct_gdp,
            t["ample"],
            t["thin"],
            t["stretched"],
            lower_is_better=True,
        )

    def score_reserve_coverage(self, coverage_ratio: float) -> float:
        """
        Score EM reserve coverage ratio (reserves / short-term debt).

        Args:
            coverage_ratio: Reserves / debt as percentage

        Returns:
            Score 0-1 (higher = more vulnerable, so inverted)
        """
        t = self.THRESHOLDS["reserve_coverage_ratio"]

        # Higher coverage is better, so invert the scoring
        if coverage_ratio >= t["ample"]:
            # Ample: > 150% → score 0.0-0.2
            # More reserves is better, but cap at 0.0
            return max(0.0, 0.2 - 0.001 * (coverage_ratio - t["ample"]))
        elif coverage_ratio >= t["thin"]:
            # Thin: 125-150% → score 0.2-0.35
            frac = (t["ample"] - coverage_ratio) / (t["ample"] - t["thin"])
            return 0.2 + 0.15 * frac
        elif coverage_ratio >= t["stretched"]:
            # Stretched: 100-125% → score 0.35-0.65
            frac = (t["thin"] - coverage_ratio) / (t["thin"] - t["stretched"])
            return 0.35 + 0.30 * frac
        elif coverage_ratio >= t["critical"]:
            # Critical approach: 75-100% → score 0.65-1.0
            frac = (t["stretched"] - coverage_ratio) / (t["stretched"] - t["critical"])
            return 0.65 + 0.35 * frac
        else:
            # Beyond critical: < 75% → score 1.0
            return 1.0

    def score_cross_border_flows(self, flow_pct_gdp: float) -> float:
        """
        Score cross-border banking flow changes (quarterly % of GDP).

        Asymmetric: sharp outflows worse than rapid inflows.

        Args:
            flow_pct_gdp: Quarterly change as % of GDP (negative = outflow)

        Returns:
            Score 0-1 (higher = more stress)
        """
        t = self.THRESHOLDS["cross_border_flow_pct_gdp"]

        # Ample range: -0.5% to +1.5%
        if t["ample_low"] <= flow_pct_gdp <= t["ample_high"]:
            return 0.2  # Normal flows

        # Handle outflows (negative values)
        if flow_pct_gdp < 0:
            if flow_pct_gdp >= t["thin_low"]:
                # Thin: -0.5% to -1.0% → score 0.2-0.35
                frac = (t["ample_low"] - flow_pct_gdp) / (t["ample_low"] - t["thin_low"])
                return 0.2 + 0.15 * frac
            elif flow_pct_gdp >= t["stretched_low"]:
                # Stretched: -1.0% to -2.0% → score 0.35-0.65
                frac = (t["thin_low"] - flow_pct_gdp) / (t["thin_low"] - t["stretched_low"])
                return 0.35 + 0.30 * frac
            elif flow_pct_gdp >= t["critical_low"]:
                # Critical: -2.0% to -4.0% → score 0.65-1.0
                frac = (t["stretched_low"] - flow_pct_gdp) / (t["stretched_low"] - t["critical_low"])
                return 0.65 + 0.35 * frac
            else:
                # Sudden stop: < -4.0% → score 1.0
                return 1.0

        # Handle inflows (positive values)
        else:
            if flow_pct_gdp <= t["thin_high"]:
                # Thin: +1.5% to +3.0% → score 0.2-0.35
                frac = (flow_pct_gdp - t["ample_high"]) / (t["thin_high"] - t["ample_high"])
                return 0.2 + 0.15 * frac
            elif flow_pct_gdp <= t["stretched_high"]:
                # Stretched: +3.0% to +5.0% → score 0.35-0.65
                frac = (flow_pct_gdp - t["thin_high"]) / (t["stretched_high"] - t["thin_high"])
                return 0.35 + 0.30 * frac
            elif flow_pct_gdp <= t["critical_high"]:
                # Critical: +5.0% to +7.0% → score 0.65-1.0
                frac = (flow_pct_gdp - t["stretched_high"]) / (t["critical_high"] - t["stretched_high"])
                return 0.65 + 0.35 * frac
            else:
                # Unsustainable boom: > +7.0% → score 1.0
                return 1.0

    def calculate(
        self,
        indicators: Optional[ContagionIndicators] = None,
    ) -> ContagionScores:
        """
        Calculate contagion pillar scores.

        Args:
            indicators: Optional pre-fetched indicators. If None, will fetch.

        Returns:
            ContagionScores with individual and composite scores
        """
        if indicators is None:
            indicators = self.fetch_indicators()

        scores = ContagionScores()
        scored_count = 0

        # Score cross-currency basis
        basis_list = []
        if indicators.eur_usd_basis_bps is not None:
            basis_list.append(indicators.eur_usd_basis_bps)
        if indicators.jpy_usd_basis_bps is not None:
            basis_list.append(indicators.jpy_usd_basis_bps)
        if indicators.gbp_usd_basis_bps is not None:
            basis_list.append(indicators.gbp_usd_basis_bps)

        if basis_list:
            scores.cross_currency_basis = self.score_cross_currency_basis(basis_list)
            scored_count += 1

        # Score TARGET2
        if (indicators.target2_imbalance_eur_billions is not None and
                indicators.eurozone_gdp_eur_trillions is not None):
            imbalance_pct = (indicators.target2_imbalance_eur_billions /
                           (indicators.eurozone_gdp_eur_trillions * 1000) * 100)
            scores.target2 = self.score_target2(imbalance_pct)
            scored_count += 1

        # Score reserve coverage
        if (indicators.fx_reserves_usd_billions is not None and
                indicators.short_term_external_debt_usd_billions is not None and
                indicators.short_term_external_debt_usd_billions > 0):
            coverage_ratio = (indicators.fx_reserves_usd_billions /
                            indicators.short_term_external_debt_usd_billions * 100)
            scores.reserve_coverage = self.score_reserve_coverage(coverage_ratio)
            scored_count += 1

        # Score cross-border flows
        if (indicators.cross_border_flow_change_billions is not None and
                indicators.world_gdp_trillions is not None and
                indicators.world_gdp_trillions > 0):
            flow_pct = (indicators.cross_border_flow_change_billions /
                       (indicators.world_gdp_trillions * 1000) * 100)
            scores.cross_border_flows = self.score_cross_border_flows(flow_pct)
            scored_count += 1

        # Calculate composite (average of available scores)
        if scored_count > 0:
            total = 0.0
            if basis_list:
                total += scores.cross_currency_basis
            if (indicators.target2_imbalance_eur_billions is not None and
                    indicators.eurozone_gdp_eur_trillions is not None):
                total += scores.target2
            if (indicators.fx_reserves_usd_billions is not None and
                    indicators.short_term_external_debt_usd_billions is not None):
                total += scores.reserve_coverage
            if (indicators.cross_border_flow_change_billions is not None and
                    indicators.world_gdp_trillions is not None):
                total += scores.cross_border_flows
            scores.composite = total / scored_count
        else:
            scores.composite = 0.5  # Default neutral

        return scores

    def get_score(self) -> float:
        """Get composite contagion score."""
        return self.calculate().composite
