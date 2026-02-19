"""Private Credit Stress Pillar.

Captures stress in the $1.7T+ private credit market that operates in opaque
structures (BDCs, direct lending funds, private CLOs) where traditional
indicators miss warning signs.

The Problem:
-----------
Private credit has grown 400%+ since 2010, now rivaling high-yield bonds.
Unlike public markets:
- No daily pricing (quarterly NAVs at best)
- No public credit ratings (or delayed downgrades)
- PIK (payment-in-kind) provisions mask cash flow problems
- Amendment/extend practices delay defaults
- Sponsor-backed companies can layer multiple tranches

Result: By the time stress is visible, it's often too late.

Our Approach - INDIRECT PROXY SIGNALS:
-------------------------------------
Since we can't observe private credit directly, we monitor:

1. PUBLICLY TRADED PROXIES
   - BDC price/NAV discounts (ARCC, MAIN, PSEC, FSK, GBDC)
   - PE firm stock prices (KKR, BX, APO, CG)
   - Leveraged loan ETFs (BKLN, SRLN)
   - CLO ETF spreads (JAAA, JBBB)

2. FED SLOOS DATA (Senior Loan Officer Survey)
   - C&I tightening to small/medium firms (private credit's bread & butter)
   - Spreads over cost of funds increasing
   - Collateral requirements increasing

3. LEVERAGED LOAN MARKET
   - FRED: Hedge funds leveraged loan holdings
   - Secondary pricing of broadly syndicated loans
   - CLO new issuance volumes

4. INDIRECT STRESS SIGNALS
   - Middle market default proxies (small-cap distress)
   - Sponsor-backed company performance
   - PE/VC valuation markdowns (quarterly, lagged)

Key Insight:
-----------
Private credit stress typically shows up in PUBLIC markets 3-6 months
before the private market acknowledges problems. BDCs trade daily and
their price/NAV discount is a real-time canary.

FRED Series Used:
----------------
- DRTSCILM: C&I lending standards to large/mid firms (quarterly)
- DRTSCIS:  C&I lending standards to small firms (quarterly)
- DRISCFLM: Spreads to large/mid firms increasing (quarterly)
- DRISCFS:  Spreads to small firms increasing (quarterly)
- BOGZ1FL623069503Q: Hedge fund leveraged loan holdings (quarterly)

Market Data Needed (external API):
---------------------------------
- BDC prices/NAVs: ARCC, MAIN, FSK, PSEC, GBDC
- Leveraged loan ETF: BKLN, SRLN prices
- PE stock prices: KKR, BX, APO, CG
"""

from dataclasses import dataclass
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime
from enum import Enum
import logging

from .private_credit_decorrelation import (
    DecorrelationResult,
    DecorrelationTimeSeries,
    PrivateCreditDecorrelator,
    blend_decorrelated_with_sloos,
)

logger = logging.getLogger(__name__)

# Try to import PCA decorrelator (v7 enhancement — 5-factor)
try:
    from .private_credit_pca import RollingPCADecorrelator
    _PCA_AVAILABLE = True
except ImportError:
    _PCA_AVAILABLE = False


class PrivateCreditStress(Enum):
    """Private credit stress levels."""

    BENIGN = "benign"           # No stress signals
    EMERGING = "emerging"       # Early warning signs
    ELEVATED = "elevated"       # Multiple signals flashing
    SEVERE = "severe"           # Broad-based stress


@dataclass
class SLOOSData:
    """Fed Senior Loan Officer Opinion Survey data."""

    # C&I Lending Standards (net % tightening)
    ci_standards_large: Optional[float] = None    # DRTSCILM
    ci_standards_small: Optional[float] = None    # DRTSCIS

    # Spreads over cost of funds (net % increasing)
    spreads_large: Optional[float] = None         # DRISCFLM
    spreads_small: Optional[float] = None         # DRISCFS

    # Collateral requirements
    collateral_large: Optional[float] = None
    collateral_small: Optional[float] = None

    # Loan demand (net % stronger)
    demand_large: Optional[float] = None
    demand_small: Optional[float] = None

    observation_date: Optional[datetime] = None


@dataclass
class BDCData:
    """Business Development Company market data."""

    # Price/NAV discounts (negative = discount, positive = premium)
    arcc_discount: Optional[float] = None   # Ares Capital
    main_discount: Optional[float] = None   # Main Street Capital
    fsk_discount: Optional[float] = None    # FS KKR Capital
    psec_discount: Optional[float] = None   # Prospect Capital
    gbdc_discount: Optional[float] = None   # Golub Capital BDC

    # Aggregate weighted discount
    weighted_discount: Optional[float] = None

    observation_date: Optional[datetime] = None


@dataclass
class LeveragedLoanData:
    """Leveraged loan market indicators."""

    # FRED data
    hedge_fund_lev_loan_holdings: Optional[float] = None  # BOGZ1FL623069503Q

    # ETF proxies
    bkln_price_change_30d: Optional[float] = None   # Invesco Senior Loan ETF
    srln_price_change_30d: Optional[float] = None   # SPDR Blackstone Senior Loan

    # CLO spreads
    clo_aaa_spread: Optional[float] = None
    clo_bbb_spread: Optional[float] = None

    observation_date: Optional[datetime] = None


@dataclass
class PEFirmData:
    """Private equity firm stock performance."""

    # Stock price changes (30-day)
    kkr_change_30d: Optional[float] = None
    bx_change_30d: Optional[float] = None    # Blackstone
    apo_change_30d: Optional[float] = None   # Apollo
    cg_change_30d: Optional[float] = None    # Carlyle

    # Aggregate
    pe_sector_change: Optional[float] = None

    observation_date: Optional[datetime] = None


@dataclass
class PrivateCreditIndicators:
    """Complete private credit stress indicators."""

    sloos: Optional[SLOOSData] = None
    bdc: Optional[BDCData] = None
    leveraged_loans: Optional[LeveragedLoanData] = None
    pe_firms: Optional[PEFirmData] = None
    decorrelation_ts: Optional[DecorrelationTimeSeries] = None  # v6 §4.7
    # v7: PCA factor time series (5-factor)
    pca_bdc_returns: Optional[List[float]] = None
    pca_spx_returns: Optional[List[float]] = None
    pca_vix_changes: Optional[List[float]] = None
    pca_hy_oas_changes: Optional[List[float]] = None
    pca_move_changes: Optional[List[float]] = None
    pca_xccy_basis_changes: Optional[List[float]] = None


@dataclass
class PrivateCreditScores:
    """Scored private credit indicators."""

    sloos_score: float = 0.5
    bdc_score: float = 0.5
    leveraged_loan_score: float = 0.5
    pe_firm_score: float = 0.5

    composite: float = 0.5
    stress_level: PrivateCreditStress = PrivateCreditStress.BENIGN

    # v6 §4.7 — Decorrelation results
    decorrelation: Optional[DecorrelationResult] = None
    composite_method: str = "fixed_weight"  # "fixed_weight" or "decorrelated_blend"

    # Narrative
    warning_signals: Optional[List[str]] = None

    def __post_init__(self):
        if self.warning_signals is None:
            self.warning_signals = []


class PrivateCreditPillar:
    """
    Private Credit Stress Pillar.

    Monitors the $1.7T+ private credit market through indirect proxies
    since direct observation is limited.
    """

    # SLOOS thresholds (net % tightening)
    SLOOS_THRESHOLDS = {
        "standards": {
            # Normal: -10 to +20 (slight tightening normal)
            # Elevated: +20 to +40 (notable tightening)
            # Severe: > +40 (crisis-level tightening)
            "normal_high": 20,
            "elevated": 40,
            "severe": 60,
        },
        "spreads": {
            # Normal: -10 to +15
            # Elevated: +15 to +30
            # Severe: > +30
            "normal_high": 15,
            "elevated": 30,
            "severe": 50,
        },
    }

    # BDC discount thresholds
    BDC_THRESHOLDS = {
        # Healthy: slight premium or small discount (-5% to +5%)
        # Stress: -5% to -15% discount
        # Severe: > -15% discount (market says NAV is overstated)
        "healthy_low": -5,
        "healthy_high": 5,
        "stress": -15,
        "severe": -25,
    }

    # Leveraged loan thresholds
    LEVERAGED_LOAN_THRESHOLDS = {
        # ETF 30-day change
        "healthy_low": -2,   # -2% is normal volatility
        "stress": -5,        # -5% indicates selling
        "severe": -10,       # -10% is distress
    }

    # PE firm stock thresholds (more volatile)
    PE_FIRM_THRESHOLDS = {
        "healthy_low": -5,
        "stress": -15,
        "severe": -25,
    }

    # Weights for composite
    WEIGHTS = {
        "sloos": 0.30,          # Leading indicator (quarterly)
        "bdc": 0.35,            # Real-time market signal
        "leveraged_loans": 0.20,  # Liquid market proxy
        "pe_firms": 0.15,       # Correlated but noisy
    }

    FRED_SERIES = {
        "ci_standards_large": "DRTSCILM",
        "ci_standards_small": "DRTSCIS",
        "spreads_large": "DRISCFLM",
        "spreads_small": "DRISCFS",
        "hedge_fund_lev_loans": "BOGZ1FL623069503Q",
    }

    def __init__(self, fred_client=None, market_data_client=None, use_pca=True):
        """
        Initialize with data clients.

        Args:
            fred_client: Client for FRED API (SLOOS data)
            market_data_client: Client for stock/ETF prices
            use_pca: Use 5-factor PCA decorrelation (v7); falls back to OLS
        """
        self.fred_client = fred_client
        self.market_data_client = market_data_client
        self._pca_decorrelator = None
        if use_pca and _PCA_AVAILABLE:
            self._pca_decorrelator = RollingPCADecorrelator()

    def score_sloos(self, data: SLOOSData) -> Tuple[float, List[str]]:
        """
        Score SLOOS lending standards data.

        Returns:
            Tuple of (score 0-1, list of warning signals)
        """
        warnings = []
        scores = []

        # Score C&I standards to small firms (key private credit proxy)
        if data.ci_standards_small is not None:
            val = data.ci_standards_small
            thresholds = self.SLOOS_THRESHOLDS["standards"]

            if val > thresholds["severe"]:
                scores.append(0.1)
                warnings.append(
                    f"SEVERE: C&I lending to small firms tightening at {val:.0f}% "
                    "(recession-level)"
                )
            elif val > thresholds["elevated"]:
                scores.append(0.3)
                warnings.append(
                    f"ELEVATED: C&I lending to small firms tightening at {val:.0f}%"
                )
            elif val > thresholds["normal_high"]:
                scores.append(0.5)
                warnings.append(
                    f"CAUTIOUS: C&I lending standards tightening ({val:.0f}%)"
                )
            else:
                scores.append(0.8)

        # Score spreads to small firms
        if data.spreads_small is not None:
            val = data.spreads_small
            thresholds = self.SLOOS_THRESHOLDS["spreads"]

            if val > thresholds["severe"]:
                scores.append(0.1)
                warnings.append(
                    f"SEVERE: Spreads to small firms widening at {val:.0f}%"
                )
            elif val > thresholds["elevated"]:
                scores.append(0.3)
                warnings.append(
                    f"ELEVATED: Spreads to small firms widening at {val:.0f}%"
                )
            elif val > thresholds["normal_high"]:
                scores.append(0.5)
            else:
                scores.append(0.8)

        # Also check large/mid (validates small firm signal)
        if data.ci_standards_large is not None:
            val = data.ci_standards_large
            thresholds = self.SLOOS_THRESHOLDS["standards"]

            if val > thresholds["elevated"]:
                scores.append(0.3)
                warnings.append(
                    f"Large/mid C&I also tightening at {val:.0f}% (broad stress)"
                )
            elif val > thresholds["normal_high"]:
                scores.append(0.5)
            else:
                scores.append(0.8)

        final_score = sum(scores) / len(scores) if scores else 0.5
        return final_score, warnings

    def score_bdc(self, data: BDCData) -> Tuple[float, List[str]]:
        """
        Score BDC price/NAV discounts.

        This is the most real-time signal for private credit stress.
        """
        warnings = []
        discounts = []

        # Collect all available discounts
        if data.arcc_discount is not None:
            discounts.append(("ARCC", data.arcc_discount, 0.25))
        if data.main_discount is not None:
            discounts.append(("MAIN", data.main_discount, 0.20))
        if data.fsk_discount is not None:
            discounts.append(("FSK", data.fsk_discount, 0.20))
        if data.psec_discount is not None:
            discounts.append(("PSEC", data.psec_discount, 0.15))
        if data.gbdc_discount is not None:
            discounts.append(("GBDC", data.gbdc_discount, 0.20))

        if not discounts:
            return 0.5, []

        # Calculate weighted average discount
        total_weight = sum(d[2] for d in discounts)
        weighted_discount = sum(d[1] * d[2] for d in discounts) / total_weight

        # Score based on discount level
        thresholds = self.BDC_THRESHOLDS

        if weighted_discount < thresholds["severe"]:
            score = 0.1
            warnings.append(
                f"SEVERE: BDC sector trading at {weighted_discount:.1f}% discount - "
                "market pricing major credit losses"
            )
        elif weighted_discount < thresholds["stress"]:
            score = 0.3
            warnings.append(
                f"ELEVATED: BDC sector at {weighted_discount:.1f}% discount - "
                "private credit stress emerging"
            )
        elif weighted_discount < thresholds["healthy_low"]:
            score = 0.5
            warnings.append(
                f"CAUTIOUS: BDC sector at {weighted_discount:.1f}% discount"
            )
        else:
            score = 0.8

        # Check for extreme individual discounts
        for name, discount, _ in discounts:
            if discount < thresholds["severe"]:
                warnings.append(
                    f"WARNING: {name} at {discount:.1f}% discount (possible distress)"
                )

        return score, warnings

    def score_leveraged_loans(self, data: LeveragedLoanData) -> Tuple[float, List[str]]:
        """Score leveraged loan market indicators."""
        warnings = []
        scores = []

        # ETF price changes
        etf_changes = []
        if data.bkln_price_change_30d is not None:
            etf_changes.append(("BKLN", data.bkln_price_change_30d))
        if data.srln_price_change_30d is not None:
            etf_changes.append(("SRLN", data.srln_price_change_30d))

        for name, change in etf_changes:
            thresholds = self.LEVERAGED_LOAN_THRESHOLDS

            if change < thresholds["severe"]:
                scores.append(0.1)
                warnings.append(
                    f"SEVERE: {name} down {abs(change):.1f}% in 30d - loan market distress"
                )
            elif change < thresholds["stress"]:
                scores.append(0.3)
                warnings.append(
                    f"ELEVATED: {name} down {abs(change):.1f}% in 30d"
                )
            elif change < thresholds["healthy_low"]:
                scores.append(0.5)
            else:
                scores.append(0.8)

        return sum(scores) / len(scores) if scores else 0.5, warnings

    def score_pe_firms(self, data: PEFirmData) -> Tuple[float, List[str]]:
        """Score PE firm stock performance."""
        warnings = []
        changes = []

        if data.kkr_change_30d is not None:
            changes.append(("KKR", data.kkr_change_30d))
        if data.bx_change_30d is not None:
            changes.append(("BX", data.bx_change_30d))
        if data.apo_change_30d is not None:
            changes.append(("APO", data.apo_change_30d))
        if data.cg_change_30d is not None:
            changes.append(("CG", data.cg_change_30d))

        if not changes:
            return 0.5, []

        # Average change
        avg_change = sum(c[1] for c in changes) / len(changes)
        thresholds = self.PE_FIRM_THRESHOLDS

        if avg_change < thresholds["severe"]:
            score = 0.2
            warnings.append(
                f"SEVERE: PE sector down {abs(avg_change):.1f}% - "
                "market pricing alt credit problems"
            )
        elif avg_change < thresholds["stress"]:
            score = 0.4
            warnings.append(
                f"ELEVATED: PE sector down {abs(avg_change):.1f}%"
            )
        elif avg_change < thresholds["healthy_low"]:
            score = 0.6
        else:
            score = 0.8

        return score, warnings

    def calculate_scores(
        self,
        indicators: PrivateCreditIndicators
    ) -> PrivateCreditScores:
        """
        Calculate comprehensive private credit stress scores.

        v6 §4.7 architecture:
        - If decorrelation time series available: composite = 60% decorrelated + 40% SLOOS
        - Otherwise: fallback to fixed-weight composite (SLOOS/BDC/LL/PE)

        Args:
            indicators: All private credit indicators

        Returns:
            PrivateCreditScores with component and composite scores
        """
        all_warnings = []

        # Score each component
        if indicators.sloos:
            sloos_score, sloos_warnings = self.score_sloos(indicators.sloos)
            all_warnings.extend(sloos_warnings)
        else:
            sloos_score = 0.5

        if indicators.bdc:
            bdc_score, bdc_warnings = self.score_bdc(indicators.bdc)
            all_warnings.extend(bdc_warnings)
        else:
            bdc_score = 0.5

        if indicators.leveraged_loans:
            ll_score, ll_warnings = self.score_leveraged_loans(indicators.leveraged_loans)
            all_warnings.extend(ll_warnings)
        else:
            ll_score = 0.5

        if indicators.pe_firms:
            pe_score, pe_warnings = self.score_pe_firms(indicators.pe_firms)
            all_warnings.extend(pe_warnings)
        else:
            pe_score = 0.5

        # ── v7: PCA decorrelation pipeline (5-factor) ────────────────
        # Try PCA first, then fall back to OLS, then to fixed weights
        decorr_result = None
        composite_method = "fixed_weight"

        if (
            self._pca_decorrelator is not None
            and indicators.pca_bdc_returns is not None
            and indicators.pca_spx_returns is not None
            and indicators.pca_vix_changes is not None
            and indicators.pca_hy_oas_changes is not None
        ):
            try:
                pca_result = self._pca_decorrelator.decorrelate(
                    bdc_returns=indicators.pca_bdc_returns,
                    spx_returns=indicators.pca_spx_returns,
                    vix_changes=indicators.pca_vix_changes,
                    hy_oas_changes=indicators.pca_hy_oas_changes,
                    move_changes=indicators.pca_move_changes,
                    xccy_basis_changes=indicators.pca_xccy_basis_changes,
                )
                if pca_result.data_quality not in ("insufficient", "failed"):
                    composite = blend_decorrelated_with_sloos(
                        pca_result.decorrelated_score,
                        sloos_score,
                        pca_result.data_quality,
                    )
                    composite_method = "pca_decorrelated_blend"
            except Exception:
                pass  # Fall through to OLS

        # v6 §4.7: OLS decorrelation fallback
        if composite_method == "fixed_weight" and indicators.decorrelation_ts is not None:
            decorrelator = PrivateCreditDecorrelator()
            decorr_result = decorrelator.decorrelate(indicators.decorrelation_ts)

            if decorr_result.data_quality != "insufficient":
                composite = blend_decorrelated_with_sloos(
                    decorr_result.decorrelated_score,
                    sloos_score,
                    decorr_result.data_quality,
                )
                composite_method = "decorrelated_blend"

                if decorr_result.ewma_z is not None and decorr_result.ewma_z < -1.5:
                    all_warnings.append(
                        f"DECORRELATED: Private credit specific stress at "
                        f"{decorr_result.ewma_z:.2f}sigma (after removing equity/credit factors)"
                    )

        # Fixed-weight fallback
        if composite_method == "fixed_weight":
            composite = (
                sloos_score * self.WEIGHTS["sloos"] +
                bdc_score * self.WEIGHTS["bdc"] +
                ll_score * self.WEIGHTS["leveraged_loans"] +
                pe_score * self.WEIGHTS["pe_firms"]
            )

        # Determine stress level
        if composite < 0.25:
            stress_level = PrivateCreditStress.SEVERE
        elif composite < 0.40:
            stress_level = PrivateCreditStress.ELEVATED
        elif composite < 0.55:
            stress_level = PrivateCreditStress.EMERGING
        else:
            stress_level = PrivateCreditStress.BENIGN

        return PrivateCreditScores(
            sloos_score=sloos_score,
            bdc_score=bdc_score,
            leveraged_loan_score=ll_score,
            pe_firm_score=pe_score,
            composite=composite,
            stress_level=stress_level,
            decorrelation=decorr_result,
            composite_method=composite_method,
            warning_signals=all_warnings,
        )

    async def fetch_fred_data(self) -> SLOOSData:
        """
        Fetch SLOOS data from FRED.

        Returns latest quarterly SLOOS survey results.
        """
        if not self.fred_client:
            return SLOOSData()

        sloos = SLOOSData()

        try:
            # Fetch each SLOOS series
            for attr, series_id in self.FRED_SERIES.items():
                if attr.startswith("ci_") or attr.startswith("spreads_"):
                    data = await self.fred_client.get_series(series_id)
                    if data and len(data) > 0:
                        setattr(sloos, attr, data[-1]["value"])
        except Exception as e:
            print(f"Error fetching SLOOS data: {e}")

        return sloos


# ============================================================================
# Analysis Functions
# ============================================================================

def analyze_private_credit_exposure() -> dict:
    """
    Document the private credit blindspot and our monitoring approach.

    Returns documentation for the methodology.
    """
    return {
        "market_size": "$1.7 trillion (2024 estimate)",
        "growth_rate": "~400% since 2010",

        "why_invisible": [
            "Quarterly NAVs instead of daily pricing",
            "No public credit ratings on most deals",
            "PIK provisions mask cash flow problems",
            "Amendment/extend delays recognition",
            "Sponsor support can defer defaults",
            "SEC Form PF aggregated with 60-day lag",
        ],

        "our_proxies": {
            "most_reliable": "BDC price/NAV discounts - daily market signal",
            "leading_indicator": "SLOOS C&I tightening - 3-6 month lead",
            "corroborating": [
                "Leveraged loan ETF prices (BKLN, SRLN)",
                "PE firm stock prices (KKR, BX, APO)",
                "CLO tranche spreads",
            ],
        },

        "historical_validation": {
            "2008_gfc": "BDCs fell 50%+ before private credit losses recognized",
            "2020_covid": "BDCs dropped 40% in March, recovered faster than private NAVs",
            "2022_rates": "BDC discounts widened 3-6 months before PC distress headlines",
        },

        "limitations": [
            "Public proxies may not capture sector-specific stress",
            "BDCs focus on middle market; mega-cap private credit less visible",
            "SLOOS quarterly frequency means 90-day data lag",
            "PE stocks affected by non-credit factors",
        ],

        "integration_with_mac": """
        Private Credit score can be integrated as a 7th pillar or as a
        sub-component of the Credit pillar. Recommended weight: 10-15%
        of total MAC score when data is available.

        Key insight: Private credit stress typically manifests 3-6 months
        BEFORE public market stress because:
        1. Private credit borrowers are weaker credits
        2. Refinancing wall hits them first
        3. Sponsors pull support before public distress
        """,
    }


def get_private_credit_fred_series() -> Dict[str, str]:
    """
    Return all FRED series IDs for private credit monitoring.
    """
    return {
        # SLOOS - Quarterly lending standards survey
        "DRTSCILM": "C&I tightening to large/mid firms",
        "DRTSCIS": "C&I tightening to small firms",
        "DRISCFLM": "Spreads increasing to large/mid",
        "DRISCFS": "Spreads increasing to small firms",

        # Leveraged loan data
        "BOGZ1FL623069503Q": "Hedge fund leveraged loan holdings",

        # Supporting credit data
        "BAMLH0A0HYM2": "ICE BofA US High Yield OAS",
        "BAMLC0A4CBBB": "ICE BofA BBB Corporate OAS",

        # Private credit to non-financial sector (broader context)
        "CRDQUSAPABIS": "Total credit to private non-financial sector",
    }


def get_bdc_tickers() -> List[Dict[str, Any]]:
    """
    Return BDC tickers for monitoring.
    """
    return [
        {"ticker": "ARCC", "name": "Ares Capital", "weight": 0.25,
         "note": "Largest BDC, diversified middle market"},
        {"ticker": "MAIN", "name": "Main Street Capital", "weight": 0.20,
         "note": "Lower middle market focus, internal management"},
        {"ticker": "FSK", "name": "FS KKR Capital", "weight": 0.20,
         "note": "KKR-managed, large cap focus"},
        {"ticker": "PSEC", "name": "Prospect Capital", "weight": 0.15,
         "note": "Higher yield, more volatile"},
        {"ticker": "GBDC", "name": "Golub Capital BDC", "weight": 0.20,
         "note": "Sponsor-backed middle market"},
    ]


def get_pe_firm_tickers() -> List[Dict[str, Any]]:
    """
    Return PE firm tickers for monitoring.
    """
    return [
        {"ticker": "BX", "name": "Blackstone",
         "note": "Largest alt asset manager, private credit focus"},
        {"ticker": "KKR", "name": "KKR & Co",
         "note": "Major private credit player via BDC"},
        {"ticker": "APO", "name": "Apollo Global",
         "note": "Insurance-backed private credit"},
        {"ticker": "CG", "name": "Carlyle Group",
         "note": "Global private credit exposure"},
    ]
