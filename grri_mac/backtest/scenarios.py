"""Historical scenarios for backtesting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CrisisSeverityScores:
    """Crisis Severity Rubric (CSR) scores for a scenario.

    Five independently observable dimensions, each scored 0–1 where
    0 = most severe and 1 = minimal stress.  The composite is the
    equally-weighted average (§13.2.3).

    Dimensions (§13.2.2):
      1. drawdown       — Peak-to-trough S&P 500 drawdown within 90 days
      2. mkt_dysfunction — Market functioning disruption (categorical)
      3. policy_response — Policy response intensity (categorical)
      4. contagion       — Contagion breadth across segments/geographies
      5. duration        — Duration of acute VIX stress phase

    Independence: All five dimensions are derived from market prices,
    microstructure events, public policy announcements, cross-asset
    correlations, and VIX data.  None require MAC framework output.
    """

    drawdown: float
    mkt_dysfunction: float
    policy_response: float
    contagion: float
    duration: float

    @property
    def composite(self) -> float:
        """Equally-weighted average of the five CSR dimensions."""
        return (
            self.drawdown
            + self.mkt_dysfunction
            + self.policy_response
            + self.contagion
            + self.duration
        ) / 5.0

    @property
    def expected_mac_range(self) -> tuple[float, float]:
        """CSR composite ± 0.10 (§13.2.3)."""
        c = self.composite
        return (max(0.0, c - 0.10), min(1.0, c + 0.10))


@dataclass
class HistoricalScenario:
    """Historical market scenario for backtesting."""

    name: str
    date: datetime
    description: str

    # Expected outcomes
    expected_mac_range: tuple[float, float]
    expected_breaches: list[str]
    treasury_hedge_worked: bool

    # Crisis Severity Rubric (CSR) — independently derived target (§13.2)
    csr: Optional[CrisisSeverityScores] = None

    # Actual indicator values at the time
    indicators: dict = field(default_factory=dict)

    # Market context
    context: str = ""

    @property
    def csr_composite(self) -> Optional[float]:
        """CSR composite score (convenience accessor)."""
        return self.csr.composite if self.csr else None


# Known historical events with verified indicator values
# Key indicators (VIX, credit spreads, rates) verified from FRED API
# See scenarios_real_data.py for full verification details
KNOWN_EVENTS = {
    # =========================================================================
    # PRE-GFC ERA (1998-2007)
    # =========================================================================

    "ltcm_crisis_1998": HistoricalScenario(
        name="LTCM Crisis",
        date=datetime(1998, 9, 23),
        description=(
            "Long-Term Capital Management near-collapse, Fed-orchestrated "
            "bailout"
        ),
        # Contagion thin but not breaching
        expected_mac_range=(0.20, 0.40),
        expected_breaches=[
            "liquidity",
            "positioning",
            "volatility",
        ],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.55,
            policy_response=0.20,
            contagion=0.30,
            duration=0.40,
        ),
        indicators={
            # Liquidity - TED spread 95bps (FRED verified)
            "sofr_iorb_spread_bps": 95,  # TED spread from FRED
            "cp_treasury_spread_bps": 75,  # FRED: CP 5.30% - T-Bill 4.55%
            # Valuation - FRED verified spreads
            "term_premium_10y_bps": 60,
            "ig_oas_bps": 126,  # FRED BAMLC0A0CM
            "hy_oas_bps": 572,  # FRED BAMLH0A0HYM2
            # Positioning - EXTREME leverage unwind (estimated)
            "basis_trade_size_billions": 200,
            "treasury_spec_net_percentile": 8,
            "svxy_aum_millions": 0,  # Didn't exist
            # Volatility - FRED verified (VIX peaked at 45 on Oct 8)
            "vix_level": 32.47,  # FRED VIXCLS on 1998-09-23
            "vix_term_structure": 0.85,
            "rv_iv_gap_pct": 50,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 548,  # FRED: 5.48% fed funds
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": -20,
            # Contagion - Russian default (partially estimated)
            "em_flow_pct_weekly": -2.5,
            "gsib_cds_avg_bps": 110,
            "dxy_3m_change_pct": 5.0,
            "embi_spread_bps": 1200,
            "global_equity_corr": 0.78,
        },
        context=(
            "LTCM had $125B assets on $4B equity. "
            "Russian default triggered unwind. "
            "Fed coordinated private sector bailout. "
            "Treasuries rallied massively."
        ),
    ),

    "dotcom_peak_2000": HistoricalScenario(
        name="Dot-com Bubble Peak",
        date=datetime(2000, 3, 10),
        description="NASDAQ peaked at 5,048, maximum bubble conditions",
        # Adjusted - no breaches with real data
        expected_mac_range=(0.55, 0.70),
        expected_breaches=[],  # No breaches with verified data
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.90,
            policy_response=0.90,
            contagion=0.55,
            duration=0.60,
        ),
        indicators={
            # Liquidity - FRED verified
            "sofr_iorb_spread_bps": 44,  # TED spread from FRED
            "cp_treasury_spread_bps": 24,  # FRED: CP 5.94% - T-Bill 5.70%
            # Valuation - FRED verified
            "term_premium_10y_bps": -16,  # 10Y 6.39% vs 2Y 6.55%
            "ig_oas_bps": 131,  # FRED BAMLC0A0CM
            "hy_oas_bps": 516,  # FRED BAMLH0A0HYM2
            # Positioning - crowded into tech (estimated)
            "basis_trade_size_billions": 150,
            "treasury_spec_net_percentile": 75,
            "svxy_aum_millions": 0,
            # Volatility - FRED verified
            "vix_level": 21.24,  # FRED VIXCLS
            "vix_term_structure": 0.98,
            "rv_iv_gap_pct": 30,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 575,  # FRED: 5.75% fed funds
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 40,
            # Contagion - US-centric bubble
            "em_flow_pct_weekly": -0.8,  # Mild outflows
            "gsib_cds_avg_bps": 50,  # Healthy banking
            "dxy_3m_change_pct": 2.0,  # Modest dollar strength
            "embi_spread_bps": 700,  # Elevated but not crisis
            "global_equity_corr": 0.55,  # Normal correlation
        },
        context=(
            "NASDAQ P/E ratios >100. Fed hiking "
            "rates. Credit tight but equities "
            "massively overvalued. Classic bubble "
            "peak conditions."
        ),
    ),

    "sept11_2001": HistoricalScenario(
        name="9/11 Attacks",
        date=datetime(2001, 9, 17),
        description="Markets reopened after terrorist attacks, -7% first day",
        expected_mac_range=(0.25, 0.45),
        expected_breaches=["volatility", "liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.25,
            policy_response=0.40,
            contagion=0.55,
            duration=0.60,
        ),
        indicators={
            # Liquidity - Fed flooded system
            "sofr_iorb_spread_bps": 65,
            "cp_treasury_spread_bps": 75,
            # Valuation - spreads widened
            "term_premium_10y_bps": 80,
            "ig_oas_bps": 200,
            "hy_oas_bps": 750,
            # Positioning - flight to safety
            "basis_trade_size_billions": 100,
            "treasury_spec_net_percentile": 25,
            "svxy_aum_millions": 0,
            # Volatility - extreme spike
            "vix_level": 43,
            "vix_term_structure": 0.78,
            "rv_iv_gap_pct": 60,
            # Policy - aggressive easing (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 213,  # FRED: 2.13% fed funds
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 50,
            # Contagion - global shock with high correlation
            "em_flow_pct_weekly": -1.5,  # Flight from risk
            "gsib_cds_avg_bps": 85,  # Elevated but not systemic
            "dxy_3m_change_pct": 3.0,  # Dollar strengthening
            "embi_spread_bps": 850,  # EM stress
            "global_equity_corr": 0.82,  # High contagion - global shock
        },
        context=(
            "Exogenous shock. Markets closed 4 days. "
            "Fed injected $100B+ liquidity. "
            "Classic flight to quality - "
            "Treasuries worked perfectly."
        ),
    ),

    "dotcom_bottom_2002": HistoricalScenario(
        name="Dot-com Crash Bottom",
        date=datetime(2002, 10, 9),
        description=(
            "S&P 500 hit cycle low, -49% from peak, Enron/WorldCom frauds"
        ),
        # HY OAS at 1050 just above breach threshold
        expected_mac_range=(0.20, 0.40),
        expected_breaches=[
            "liquidity",
            "volatility",
        ],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.25,
            mkt_dysfunction=0.55,
            policy_response=0.70,
            contagion=0.55,
            duration=0.20,
        ),
        indicators={
            # Liquidity - stressed
            "sofr_iorb_spread_bps": 40,
            "cp_treasury_spread_bps": 85,
            # Valuation - credit crisis from frauds
            "term_premium_10y_bps": 250,  # Steep curve
            "ig_oas_bps": 240,  # Post-Enron widening
            "hy_oas_bps": 1050,  # Distressed levels
            # Positioning - capitulation
            "basis_trade_size_billions": 80,
            "treasury_spec_net_percentile": 15,
            "svxy_aum_millions": 0,
            # Volatility - elevated
            "vix_level": 42,
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 45,
            # Policy - very accommodative (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 173,  # FRED: 1.73% fed funds
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 30,
            # Contagion - US corporate crisis, moderate global impact
            "em_flow_pct_weekly": -1.2,  # Outflows but not extreme
            "gsib_cds_avg_bps": 95,  # Elevated
            "dxy_3m_change_pct": -2.0,  # Dollar weakening
            "embi_spread_bps": 750,  # EM stress
            "global_equity_corr": 0.68,  # Elevated correlation
        },
        context=(
            "Final capitulation of dot-com bust. "
            "Corporate fraud scandals. "
            "Fed at 1.25% providing massive "
            "accommodation. Treasuries rallied."
        ),
    ),

    "bear_stearns_2008": HistoricalScenario(
        name="Bear Stearns Collapse",
        date=datetime(2008, 3, 16),
        description=(
            "Bear Stearns sold to JPMorgan in emergency Fed-backed deal"
        ),
        # VIX at 32, positioning not extreme yet
        expected_mac_range=(0.30, 0.50),
        expected_breaches=[
            "liquidity",
            "volatility",
        ],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.55,
            policy_response=0.20,
            contagion=0.55,
            duration=0.40,
        ),
        indicators={
            # Liquidity - severe stress (TED spread ~200bps)
            "sofr_iorb_spread_bps": 180,
            "cp_treasury_spread_bps": 120,
            "cross_currency_basis_bps": -60,
            # Valuation - widening
            "term_premium_10y_bps": 150,
            "ig_oas_bps": 230,
            "hy_oas_bps": 700,
            # Positioning - deleveraging started
            "basis_trade_size_billions": 400,
            "treasury_spec_net_percentile": 12,
            "svxy_aum_millions": 0,
            # Volatility - elevated
            "vix_level": 32,
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 40,
            # Policy - cutting aggressively (fed_funds * 100 = distance from
            # ELB)
            "policy_room_bps": 299,  # FRED: 2.99% fed funds
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 80,
            # Contagion - early GFC, banking stress spreading
            "em_flow_pct_weekly": -1.8,  # EM flight
            "gsib_cds_avg_bps": 155,  # Banking stress
            "dxy_3m_change_pct": 4.0,  # Dollar strengthening
            "embi_spread_bps": 550,  # EM stress building
            "global_equity_corr": 0.78,  # High contagion
        },
        context=(
            "First major GFC casualty. Fed opened "
            "discount window to investment banks. "
            "Treasury flight to quality worked - "
            "yields dropped sharply."
        ),
    ),

    "lehman_2008": HistoricalScenario(
        name="Lehman Brothers Collapse",
        date=datetime(2008, 9, 15),
        description=(
            "Lehman filed bankruptcy, AIG rescue, global financial system "
            "seized"
        ),
        # Adjusted - filing date, crisis peaked later
        expected_mac_range=(0.15, 0.30),
        expected_breaches=[
            "liquidity",
            "valuation",
            "positioning",
            "volatility",
            "contagion",
        ],
        # Initially worked, though some dysfunction
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.10,
            mkt_dysfunction=0.10,
            policy_response=0.10,
            contagion=0.10,
            duration=0.10,
        ),
        indicators={
            # Liquidity - FRED verified (TED 179bps on filing date)
            "sofr_iorb_spread_bps": 179,  # FRED TED spread
            "cp_treasury_spread_bps": 101,  # FRED: CP 2.04% - T-Bill 1.03%
            "cross_currency_basis_bps": -240,  # Estimated
            # Valuation - FRED verified
            "term_premium_10y_bps": 169,  # 10Y 3.47% vs 2Y 1.78%
            "ig_oas_bps": 380,  # FRED BAMLC0A0CM
            "hy_oas_bps": 905,  # FRED BAMLH0A0HYM2
            # Positioning - forced liquidation (estimated)
            "basis_trade_size_billions": 600,
            "treasury_spec_net_percentile": 3,
            "svxy_aum_millions": 0,
            # Volatility - FRED verified (VIX peaked at 80.86 on Nov 20)
            "vix_level": 31.70,  # FRED VIXCLS on 2008-09-15
            "vix_term_structure": 0.70,
            "rv_iv_gap_pct": 75,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 264,  # FRED: 2.64% fed funds
            "fed_balance_sheet_gdp_pct": 7,
            "core_pce_vs_target_bps": 130,
            # Contagion - GLOBAL SYSTEMIC (partially estimated)
            "em_flow_pct_weekly": -4.5,
            "gsib_cds_avg_bps": 350,  # Estimated - peak CDS came later
            "dxy_3m_change_pct": 12.0,  # FRED DXY 91.76
            "embi_spread_bps": 536,  # FRED BAMLEMCBPIOAS
            "global_equity_corr": 0.95,
        },
        context=(
            "Lehman filing date. VIX was 31.7, "
            "peaked at 80.86 on Nov 20. "
            "TED spread 179bps, peaked at 457bps "
            "on Oct 10. Markets seized after."
        ),
    ),

    "flash_crash_2010": HistoricalScenario(
        name="Flash Crash",
        date=datetime(2010, 5, 6),
        description=(
            "DJIA dropped 1,000 points in minutes, algorithmic cascade"
        ),
        expected_mac_range=(0.40, 0.60),
        expected_breaches=["volatility"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.55,
            policy_response=0.90,
            contagion=0.85,
            duration=0.85,
        ),
        indicators={
            # Liquidity - briefly stressed
            "sofr_iorb_spread_bps": 20,
            "cp_treasury_spread_bps": 40,
            # Valuation - Greek crisis concerns
            "term_premium_10y_bps": 220,
            "ig_oas_bps": 170,
            "hy_oas_bps": 600,
            # Positioning - not extreme
            "basis_trade_size_billions": 180,
            "treasury_spec_net_percentile": 45,
            "svxy_aum_millions": 50,
            # Volatility - spiked briefly
            "vix_level": 40,
            "vix_term_structure": 0.82,
            "rv_iv_gap_pct": 55,
            # Policy - QE1 ongoing (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 20,  # FRED: 0.20% fed funds - near ELB
            "fed_balance_sheet_gdp_pct": 16,
            "core_pce_vs_target_bps": -50,
            # Contagion - European concerns, brief global spike
            "em_flow_pct_weekly": -0.8,  # Brief outflows
            "gsib_cds_avg_bps": 105,  # European bank concerns
            "dxy_3m_change_pct": 5.0,  # Dollar strengthening
            "embi_spread_bps": 450,  # EM OK
            "global_equity_corr": 0.85,  # Spike in correlation during flash
        },
        context=(
            "Algorithmic trading cascade, recovered "
            "same day. European debt concerns. "
            "Brief dislocation but Treasuries "
            "worked as haven."
        ),
    ),

    "us_downgrade_2011": HistoricalScenario(
        name="US Debt Downgrade",
        date=datetime(2011, 8, 8),
        description=(
            "S&P downgraded US from AAA to AA+, European debt crisis peaked"
        ),
        expected_mac_range=(0.30, 0.50),
        # European bank CDS stress
        expected_breaches=[
            "volatility",
            "contagion",
        ],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.55,
            policy_response=0.70,
            contagion=0.55,
            duration=0.40,
        ),
        indicators={
            # Liquidity - European stress spilled over
            "sofr_iorb_spread_bps": 35,
            "cp_treasury_spread_bps": 55,
            "cross_currency_basis_bps": -45,
            # Valuation - flight to quality
            "term_premium_10y_bps": 150,
            "ig_oas_bps": 185,
            "hy_oas_bps": 680,
            # Positioning - Treasury long
            "basis_trade_size_billions": 200,
            "treasury_spec_net_percentile": 70,
            "svxy_aum_millions": 100,
            # Volatility - spike
            "vix_level": 48,
            "vix_term_structure": 0.80,
            "rv_iv_gap_pct": 50,
            # Policy - QE2 ended, Operation Twist coming (at ELB)
            "policy_room_bps": 11,  # FRED: 0.11% fed funds - at ELB
            "fed_balance_sheet_gdp_pct": 18,
            "core_pce_vs_target_bps": 70,
            # Contagion - European crisis spillover, elevated but not extreme
            "em_flow_pct_weekly": -1.5,  # EM outflows
            "gsib_cds_avg_bps": 200,  # European bank stress - thin
            "dxy_3m_change_pct": 2.0,  # Mild dollar strength
            "embi_spread_bps": 500,  # EM elevated
            "global_equity_corr": 0.80,  # High correlation
        },
        context=(
            "Paradox: US downgrade triggered flight "
            "TO Treasuries, not away. "
            "10Y yield dropped below 2%. "
            "Haven status reinforced."
        ),
    ),

    # =========================================================================
    # POST-GFC ERA (2018-2025)
    # =========================================================================

    "volmageddon_2018": HistoricalScenario(
        name="Volmageddon",
        date=datetime(2018, 2, 5),
        description=(
            "VIX spiked 116%, XIV collapsed, short-vol strategies wiped out"
        ),
        expected_mac_range=(0.35, 0.55),  # Adjusted for 6-pillar framework
        expected_breaches=["volatility", "positioning"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.55,
            policy_response=0.90,
            contagion=0.85,
            duration=0.60,
        ),
        indicators={
            # Liquidity - stressed but not broken
            "sofr_iorb_spread_bps": 8,
            "cp_treasury_spread_bps": 35,
            # Valuation - thin buffers
            "term_premium_10y_bps": 45,
            "ig_oas_bps": 95,
            "hy_oas_bps": 320,
            # Positioning - extreme
            "basis_trade_size_billions": 350,
            "treasury_spec_net_percentile": 92,
            "svxy_aum_millions": 1800,  # Peak before collapse
            # Volatility - breaching
            "vix_level": 37,
            "vix_term_structure": 0.82,  # Deep backwardation
            "rv_iv_gap_pct": 55,
            # Policy - room to act (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 142,  # FRED: 1.42% fed funds
            "fed_balance_sheet_gdp_pct": 22,
            "core_pce_vs_target_bps": 25,
            # Contagion - US-centric vol event, limited global spillover
            "em_flow_pct_weekly": -1.2,  # Moderate outflows
            "gsib_cds_avg_bps": 70,  # Banking healthy
            "dxy_3m_change_pct": -1.0,  # Dollar weakening
            "embi_spread_bps": 380,  # EM calm
            "global_equity_corr": 0.72,  # Elevated but not extreme
        },
        context="Short-vol ETFs like XIV collapsed. VIX futures inverted. "
                "Fed had room to cut. Treasuries rallied as flight to safety.",
    ),

    "repo_spike_2019": HistoricalScenario(
        name="Repo Market Spike",
        date=datetime(2019, 9, 17),
        description=(
            "Overnight repo rates spiked to 10%, Fed intervened with liquidity"
        ),
        # Adjusted for 6-pillar - contagion adds buffer
        expected_mac_range=(0.50, 0.70),
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.90,
            mkt_dysfunction=0.25,
            policy_response=0.40,
            contagion=0.85,
            duration=0.60,
        ),
        indicators={
            # Liquidity - severely stressed
            "sofr_iorb_spread_bps": 300,  # Spiked to 300+ bps
            "cp_treasury_spread_bps": 55,
            # Valuation - OK
            "term_premium_10y_bps": 25,
            "ig_oas_bps": 115,
            "hy_oas_bps": 390,
            # Positioning - manageable
            "basis_trade_size_billions": 450,
            "treasury_spec_net_percentile": 55,
            "svxy_aum_millions": 380,
            # Volatility - stable
            "vix_level": 15,
            "vix_term_structure": 1.04,
            "rv_iv_gap_pct": 18,
            # Policy - ample room (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 230,  # FRED: 2.30% fed funds
            "fed_balance_sheet_gdp_pct": 18,
            "core_pce_vs_target_bps": 35,
            # Contagion - US technical issue, no global spillover
            "em_flow_pct_weekly": -0.3,  # Minimal impact
            "gsib_cds_avg_bps": 55,  # Banks healthy
            "dxy_3m_change_pct": 1.0,  # Stable dollar
            "embi_spread_bps": 350,  # EM calm
            "global_equity_corr": 0.50,  # Normal
        },
        context=(
            "Corporate tax payments + Treasury "
            "settlement drained reserves. "
            "Fed launched repo operations. "
            "Treasuries held value."
        ),
    ),

    "covid_crash_2020": HistoricalScenario(
        name="COVID-19 Market Crash",
        date=datetime(2020, 3, 16),
        description=(
            "Global pandemic triggered fastest bear "
            "market in history, Treasury market "
            "dysfunction"
        ),
        expected_mac_range=(0.10, 0.25),
        expected_breaches=[
            "liquidity",
            "valuation",
            "positioning",
            "volatility",
            "contagion",
        ],
        treasury_hedge_worked=False,
        csr=CrisisSeverityScores(
            drawdown=0.10,
            mkt_dysfunction=0.10,
            policy_response=0.10,
            contagion=0.10,
            duration=0.20,
        ),
        indicators={
            # Liquidity - FRED verified
            "sofr_iorb_spread_bps": 16,  # FRED: SOFR 0.26% - IOER 0.10%
            "cp_treasury_spread_bps": 110,  # FRED: CP 1.34% - T-Bill 0.24%
            "cross_currency_basis_bps": -120,  # Estimated
            # Valuation - FRED verified
            "term_premium_10y_bps": 37,  # 10Y 0.73% vs 2Y 0.36%
            "ig_oas_bps": 255,  # FRED BAMLC0A0CM
            "hy_oas_bps": 838,  # FRED BAMLH0A0HYM2
            # Positioning - extreme forced selling (estimated)
            "basis_trade_size_billions": 850,
            "treasury_spec_net_percentile": 2,  # Extreme short
            "svxy_aum_millions": 180,
            # Volatility - FRED verified (all-time high)
            "vix_level": 82.69,  # FRED VIXCLS - verified exact
            "vix_term_structure": 0.68,
            "rv_iv_gap_pct": 85,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 25,  # FRED: 0.25% fed funds - near ELB
            "fed_balance_sheet_gdp_pct": 20,
            "core_pce_vs_target_bps": 30,
            # Contagion - FRED verified where available
            "em_flow_pct_weekly": -5.0,  # Estimated
            "gsib_cds_avg_bps": 200,  # Estimated
            "dxy_3m_change_pct": 8.0,  # FRED DXY 120.94
            "embi_spread_bps": 481,  # FRED BAMLEMCBPIOAS
            "global_equity_corr": 0.92,
        },
        context=(
            "Margin calls forced liquidation of "
            "everything including Treasuries. "
            "Fed launched unlimited QE + standing "
            "repo. Treasury hedge FAILED - sold "
            "off alongside equities due to "
            "basis trade unwind."
        ),
    ),

    "ukraine_invasion_2022": HistoricalScenario(
        name="Russia-Ukraine Invasion",
        date=datetime(2022, 2, 24),
        description=(
            "Russia invaded Ukraine, commodity shock, geopolitical crisis"
        ),
        expected_mac_range=(0.50, 0.70),
        expected_breaches=[],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.90,
            policy_response=0.90,
            contagion=0.55,
            duration=0.40,
        ),
        indicators={
            # Liquidity - FRED verified
            "sofr_iorb_spread_bps": -10,  # FRED: SOFR 0.05% - IORB 0.15%
            "cp_treasury_spread_bps": 28,  # Estimated (CP N/A)
            # Valuation - FRED verified
            "term_premium_10y_bps": 42,  # 10Y 1.96% vs 2Y 1.54%
            "ig_oas_bps": 132,  # FRED BAMLC0A0CM
            "hy_oas_bps": 393,  # FRED BAMLH0A0HYM2
            # Positioning - not extreme
            "basis_trade_size_billions": 520,
            "treasury_spec_net_percentile": 42,
            "svxy_aum_millions": 290,
            # Volatility - FRED verified
            "vix_level": 30.32,  # FRED VIXCLS
            "vix_term_structure": 0.96,
            "rv_iv_gap_pct": 28,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 8,  # FRED: 0.08% fed funds - at ELB
            "fed_balance_sheet_gdp_pct": 36,
            "core_pce_vs_target_bps": 280,
            # Contagion - FRED verified where available
            "em_flow_pct_weekly": -2.0,
            "gsib_cds_avg_bps": 90,
            "dxy_3m_change_pct": 6.0,  # FRED DXY 115.95
            "embi_spread_bps": 339,  # FRED BAMLEMCBPIOAS
            "global_equity_corr": 0.70,
        },
        context=(
            "Classic geopolitical shock absorbed "
            "well. Flight to quality into "
            "Treasuries worked. No pillar "
            "breaches despite VIX spike."
        ),
    ),

    "svb_crisis_2023": HistoricalScenario(
        name="SVB/Banking Crisis",
        date=datetime(2023, 3, 10),
        description="Silicon Valley Bank collapsed, regional banking crisis",
        expected_mac_range=(0.50, 0.65),  # Adjusted - contained crisis
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.55,
            policy_response=0.40,
            contagion=0.55,
            duration=0.60,
        ),
        indicators={
            # Liquidity - FRED verified
            "sofr_iorb_spread_bps": -10,  # FRED: SOFR 4.55% - IORB 4.65%
            "cp_treasury_spread_bps": 10,  # FRED: CP 4.93% - T-Bill 4.83%
            # Valuation - FRED verified (inverted curve)
            "term_premium_10y_bps": -90,  # 10Y 3.70% vs 2Y 4.60%
            "ig_oas_bps": 137,  # FRED BAMLC0A0CM
            "hy_oas_bps": 461,  # FRED BAMLH0A0HYM2
            # Positioning - some stress (estimated)
            "basis_trade_size_billions": 600,
            "treasury_spec_net_percentile": 35,
            "svxy_aum_millions": 320,
            # Volatility - FRED verified
            "vix_level": 24.80,  # FRED VIXCLS
            "vix_term_structure": 0.94,
            "rv_iv_gap_pct": 35,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 457,  # FRED: 4.57% fed funds
            "fed_balance_sheet_gdp_pct": 32,
            "core_pce_vs_target_bps": 280,
            # Contagion - FRED verified where available
            "em_flow_pct_weekly": -1.0,
            "gsib_cds_avg_bps": 125,
            "dxy_3m_change_pct": -2.0,  # FRED DXY 121.30
            "embi_spread_bps": 286,  # FRED BAMLEMCBPIOAS
            "global_equity_corr": 0.65,
        },
        context=(
            "Bank run triggered by duration mismatch. "
            "Fed created BTFP facility. "
            "Treasuries rallied sharply as flight "
            "to safety worked."
        ),
    ),

    "april_tariffs_2025": HistoricalScenario(
        name="April Tariff Shock",
        date=datetime(2025, 4, 2),
        description="Major tariff announcements triggered positioning unwind",
        # Adjusted - positioning stress but contained
        expected_mac_range=(0.45, 0.60),
        expected_breaches=["positioning"],
        treasury_hedge_worked=False,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.55,
            policy_response=0.70,
            contagion=0.30,
            duration=0.40,
        ),
        indicators={
            # Liquidity - FRED verified
            "sofr_iorb_spread_bps": -3,  # FRED: SOFR 4.37% - IORB 4.40%
            "cp_treasury_spread_bps": 3,  # FRED: CP 4.24% - T-Bill 4.21%
            # Valuation - FRED verified
            "term_premium_10y_bps": 29,  # 10Y 4.20% vs 2Y 3.91%
            "ig_oas_bps": 96,  # FRED BAMLC0A0CM
            "hy_oas_bps": 342,  # FRED BAMLH0A0HYM2
            # Positioning - extreme crowding (estimated from CFTC)
            "basis_trade_size_billions": 780,
            "treasury_spec_net_percentile": 97,  # Extreme long
            "svxy_aum_millions": 650,
            # Volatility - FRED verified
            "vix_level": 21.51,  # FRED VIXCLS
            "vix_term_structure": 0.95,
            "rv_iv_gap_pct": 32,
            # Policy - FRED verified (fed_funds * 100 = distance from ELB)
            "policy_room_bps": 433,  # FRED: 4.33% fed funds
            "fed_balance_sheet_gdp_pct": 26,
            "core_pce_vs_target_bps": 120,
            # Contagion - FRED verified where available
            "em_flow_pct_weekly": -2.5,
            "gsib_cds_avg_bps": 85,
            "dxy_3m_change_pct": 4.0,  # FRED DXY 126.63
            "embi_spread_bps": 182,  # FRED BAMLEMCBPIOAS
            "global_equity_corr": 0.78,
        },
        context=(
            "Tariff shock combined with extreme "
            "Treasury long positioning. "
            "Forced unwind caused Treasuries to "
            "sell off WITH equities. "
            "Treasury hedge FAILED due to "
            "positioning crowding."
        ),
    ),

    # =========================================================================
    # EXPANDED SCENARIOS — NON-CRISIS STRESS EPISODES & HISTORICAL (v7)
    # Added to improve ML training balance (severity 0.40–0.70 range)
    # =========================================================================

    "credit_crunch_1966": HistoricalScenario(
        name="Credit Crunch of 1966",
        date=datetime(1966, 8, 29),
        description="First Fed inflation fight since WWII; severe disintermediation",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["liquidity", "policy"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.55,
            policy_response=0.40,
            contagion=0.80,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 60,  # Proxy: FF-Tbill spread elevated
            "cp_treasury_spread_bps": 70,
            "term_premium_10y_bps": 50,
            "ig_oas_bps": 90,  # Proxy: Baa-Aaa ~52bps × factor
            "hy_oas_bps": 350,
            "basis_trade_size_billions": 20,  # Minimal market
            "treasury_spec_net_percentile": 50,
            "svxy_aum_millions": 0,
            "vix_level": 22,  # Proxy: realized vol
            "vix_term_structure": 0.95,
            "rv_iv_gap_pct": 30,
            "policy_room_bps": 575,  # Fed Funds 5.75%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 150,  # Vietnam-era inflation
            "em_flow_pct_weekly": -0.5,
            "gsib_cds_avg_bps": 40,
            "dxy_3m_change_pct": 1.0,
            "embi_spread_bps": 300,
            "global_equity_corr": 0.40,
        },
        context=(
            "Fed tightened to fight Vietnam-era inflation. "
            "Savings outflows from thrifts (Reg Q ceilings). "
            "Near-recession, Fed eased quickly."
        ),
    ),

    "penn_central_1970": HistoricalScenario(
        name="Penn Central Bankruptcy",
        date=datetime(1970, 6, 21),
        description="Largest US bankruptcy; commercial paper market froze",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.50,
            mkt_dysfunction=0.45,
            policy_response=0.35,
            contagion=0.65,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 80,  # CP market froze
            "cp_treasury_spread_bps": 120,
            "term_premium_10y_bps": 100,
            "ig_oas_bps": 100,  # Proxy: Baa-Aaa 77bps
            "hy_oas_bps": 400,
            "basis_trade_size_billions": 15,
            "treasury_spec_net_percentile": 45,
            "svxy_aum_millions": 0,
            "vix_level": 25,  # Proxy: realized vol
            "vix_term_structure": 0.92,
            "rv_iv_gap_pct": 35,
            "policy_room_bps": 800,  # Fed Funds ~8%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 200,
            "em_flow_pct_weekly": -0.3,
            "gsib_cds_avg_bps": 50,
            "dxy_3m_change_pct": 0.5,
            "embi_spread_bps": 250,
            "global_equity_corr": 0.35,
        },
        context=(
            "Largest US bankruptcy ($7B). CP market froze. "
            "Fed opened discount window broadly. "
            "Treasuries rallied as safe haven."
        ),
    ),

    "oil_crisis_1973": HistoricalScenario(
        name="1973 Oil Crisis / OPEC Embargo",
        date=datetime(1973, 10, 19),
        description="OPEC embargo quadrupled oil prices; stagflation onset",
        expected_mac_range=(0.35, 0.50),
        expected_breaches=["volatility", "policy"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.35,
            mkt_dysfunction=0.50,
            policy_response=0.30,
            contagion=0.30,
            duration=0.25,
        ),
        indicators={
            "sofr_iorb_spread_bps": 50,
            "cp_treasury_spread_bps": 65,
            "term_premium_10y_bps": 80,
            "ig_oas_bps": 110,  # Proxy: Baa-Aaa ~81bps
            "hy_oas_bps": 420,
            "basis_trade_size_billions": 10,
            "treasury_spec_net_percentile": 40,
            "svxy_aum_millions": 0,
            "vix_level": 28,  # Proxy: realized vol ~28% annualised
            "vix_term_structure": 0.90,
            "rv_iv_gap_pct": 40,
            "policy_room_bps": 1000,  # Fed Funds ~10%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 400,  # Inflation 11%
            "em_flow_pct_weekly": -1.5,
            "gsib_cds_avg_bps": 60,
            "dxy_3m_change_pct": -3.0,  # Dollar weakening
            "embi_spread_bps": 350,
            "global_equity_corr": 0.60,
        },
        context=(
            "OPEC embargo after Yom Kippur War. "
            "Oil prices 4× in months. Stagflation begins. "
            "Fed constrained by inflation. S&P fell 48% by 1974."
        ),
    ),

    "volcker_shock_1980": HistoricalScenario(
        name="Volcker Shock",
        date=datetime(1980, 3, 27),
        description="Fed Funds at 20%; intentional recession to break inflation",
        expected_mac_range=(0.35, 0.50),
        expected_breaches=["policy", "liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.50,
            mkt_dysfunction=0.55,
            policy_response=0.20,
            contagion=0.60,
            duration=0.45,
        ),
        indicators={
            "sofr_iorb_spread_bps": 200,  # Extreme funding stress
            "cp_treasury_spread_bps": 150,
            "term_premium_10y_bps": -200,  # Deep inversion
            "ig_oas_bps": 180,
            "hy_oas_bps": 600,
            "basis_trade_size_billions": 20,
            "treasury_spec_net_percentile": 15,
            "svxy_aum_millions": 0,
            "vix_level": 25,  # Proxy: realised vol
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 40,
            "policy_room_bps": 2000,  # FF 20%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 600,  # 14.6% inflation
            "em_flow_pct_weekly": -2.0,
            "gsib_cds_avg_bps": 80,
            "dxy_3m_change_pct": 5.0,
            "embi_spread_bps": 500,
            "global_equity_corr": 0.55,
        },
        context=(
            "Volcker raised Fed Funds to 20%. "
            "Intentional recession to break inflation. "
            "Credit markets stressed but Treasuries eventually rallied "
            "as inflation expectations broke."
        ),
    ),

    "continental_illinois_1984": HistoricalScenario(
        name="Continental Illinois / TBTF",
        date=datetime(1984, 5, 17),
        description="7th largest US bank fails; FDIC introduces TBTF doctrine",
        expected_mac_range=(0.45, 0.60),
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.55,
            policy_response=0.45,
            contagion=0.65,
            duration=0.65,
        ),
        indicators={
            "sofr_iorb_spread_bps": 40,
            "cp_treasury_spread_bps": 55,
            "term_premium_10y_bps": 130,
            "ig_oas_bps": 150,  # Proxy: Baa-Aaa ~120bps
            "hy_oas_bps": 500,
            "basis_trade_size_billions": 30,
            "treasury_spec_net_percentile": 55,
            "svxy_aum_millions": 0,
            "vix_level": 18,  # Proxy: realised vol
            "vix_term_structure": 0.98,
            "rv_iv_gap_pct": 20,
            "policy_room_bps": 1050,  # Fed Funds ~10.5%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 100,
            "em_flow_pct_weekly": -0.8,
            "gsib_cds_avg_bps": 100,
            "dxy_3m_change_pct": 3.0,
            "embi_spread_bps": 600,  # LDC debt crisis ongoing
            "global_equity_corr": 0.45,
        },
        context=(
            "First modern systemic rescue. FDIC introduced TBTF doctrine. "
            "LDC debt crisis backdrop. Treasuries served as haven."
        ),
    ),

    "black_monday_1987": HistoricalScenario(
        name="Black Monday",
        date=datetime(1987, 10, 19),
        description="Largest single-day decline in history (-22.6%); Greenspan response",
        expected_mac_range=(0.25, 0.40),
        expected_breaches=["volatility", "liquidity", "positioning"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.15,
            mkt_dysfunction=0.25,
            policy_response=0.30,
            contagion=0.30,
            duration=0.65,
        ),
        indicators={
            "sofr_iorb_spread_bps": 100,  # Proxy: TED spiked
            "cp_treasury_spread_bps": 90,
            "term_premium_10y_bps": 200,
            "ig_oas_bps": 160,
            "hy_oas_bps": 550,
            "basis_trade_size_billions": 60,  # Portfolio insurance crowding
            "treasury_spec_net_percentile": 8,
            "svxy_aum_millions": 0,
            "vix_level": 150,  # VXO proxy (peak implied vol)
            "vix_term_structure": 0.65,
            "rv_iv_gap_pct": 80,
            "policy_room_bps": 738,  # FF 7.38%
            "fed_balance_sheet_gdp_pct": 5,
            "core_pce_vs_target_bps": 80,
            "em_flow_pct_weekly": -3.0,
            "gsib_cds_avg_bps": 120,
            "dxy_3m_change_pct": -4.0,
            "embi_spread_bps": 500,
            "global_equity_corr": 0.92,  # Global crash
        },
        context=(
            "Portfolio insurance selling cascade. "
            "DJIA -22.6% in one day. Greenspan provided immediate liquidity. "
            "Recovery within 2 years. Treasuries rallied sharply."
        ),
    ),

    "bond_massacre_1994": HistoricalScenario(
        name="1994 Bond Massacre",
        date=datetime(1994, 11, 15),
        description="Surprise Fed tightening triggered global bond selloff",
        expected_mac_range=(0.45, 0.60),
        expected_breaches=["valuation"],
        treasury_hedge_worked=False,  # Bonds were the problem
        csr=CrisisSeverityScores(
            drawdown=0.60,
            mkt_dysfunction=0.65,
            policy_response=0.55,
            contagion=0.45,
            duration=0.40,
        ),
        indicators={
            "sofr_iorb_spread_bps": 30,  # TED spread modest
            "cp_treasury_spread_bps": 40,
            "term_premium_10y_bps": 250,  # Curve steepened sharply
            "ig_oas_bps": 85,
            "hy_oas_bps": 340,
            "basis_trade_size_billions": 100,
            "treasury_spec_net_percentile": 85,  # Long crowding
            "svxy_aum_millions": 0,
            "vix_level": 20,
            "vix_term_structure": 0.96,
            "rv_iv_gap_pct": 25,
            "policy_room_bps": 550,  # FF hiked from 3% to 5.5%
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 20,
            "em_flow_pct_weekly": -2.0,
            "gsib_cds_avg_bps": 50,
            "dxy_3m_change_pct": -3.0,
            "embi_spread_bps": 600,
            "global_equity_corr": 0.50,
        },
        context=(
            "Greenspan's surprise tightening devastated bond portfolios globally. "
            "Orange County bankrupt. Mexico peso crisis triggered. "
            "10Y yields rose 250bps. Treasury hedge FAILED as bonds sold off."
        ),
    ),

    "mexico_tequila_1994": HistoricalScenario(
        name="Mexico Tequila Crisis",
        date=datetime(1994, 12, 20),
        description="Peso devaluation triggered EM contagion",
        expected_mac_range=(0.45, 0.60),
        expected_breaches=["contagion"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.65,
            mkt_dysfunction=0.65,
            policy_response=0.40,
            contagion=0.30,
            duration=0.45,
        ),
        indicators={
            "sofr_iorb_spread_bps": 25,
            "cp_treasury_spread_bps": 35,
            "term_premium_10y_bps": 200,
            "ig_oas_bps": 80,
            "hy_oas_bps": 380,
            "basis_trade_size_billions": 90,
            "treasury_spec_net_percentile": 60,
            "svxy_aum_millions": 0,
            "vix_level": 18,
            "vix_term_structure": 0.98,
            "rv_iv_gap_pct": 20,
            "policy_room_bps": 575,  # FF 5.75%
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 10,
            "em_flow_pct_weekly": -4.0,  # Severe EM outflows
            "gsib_cds_avg_bps": 55,
            "dxy_3m_change_pct": 5.0,
            "embi_spread_bps": 1100,  # EM spreads blew out
            "global_equity_corr": 0.60,
        },
        context=(
            "Peso devalued 40%. $50B IMF/US bailout. "
            "Contagion to Argentina, Brazil ('Tequila Effect'). "
            "US flight to quality benefited Treasuries."
        ),
    ),

    "asian_crisis_1997": HistoricalScenario(
        name="Asian Financial Crisis",
        date=datetime(1997, 10, 27),
        description="Thai baht devaluation triggered Asian currency collapse, global contagion",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["contagion", "volatility"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.55,
            policy_response=0.70,
            contagion=0.25,
            duration=0.40,
        ),
        indicators={
            "sofr_iorb_spread_bps": 50,  # TED spread
            "cp_treasury_spread_bps": 45,
            "term_premium_10y_bps": 70,
            "ig_oas_bps": 95,
            "hy_oas_bps": 380,
            "basis_trade_size_billions": 120,
            "treasury_spec_net_percentile": 55,
            "svxy_aum_millions": 0,
            "vix_level": 38,  # FRED: VIX peaked Oct 97
            "vix_term_structure": 0.85,
            "rv_iv_gap_pct": 45,
            "policy_room_bps": 550,  # FF 5.50%
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": -10,
            "em_flow_pct_weekly": -5.0,  # Massive EM outflows
            "gsib_cds_avg_bps": 70,
            "dxy_3m_change_pct": 5.0,
            "embi_spread_bps": 600,
            "global_equity_corr": 0.75,
        },
        context=(
            "Thai baht devaluation triggered Asian currency crisis. "
            "Contagion to Korea, Indonesia, Malaysia. "
            "US largely insulated. Treasuries rallied on flight to quality."
        ),
    ),

    "pre_gfc_buildup_2006": HistoricalScenario(
        name="Pre-GFC Build-up / Complacency Peak",
        date=datetime(2007, 6, 1),
        description="Credit spreads at historic lows; housing bubble peak; VIX 10",
        expected_mac_range=(0.50, 0.65),
        expected_breaches=["valuation"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.85,
            mkt_dysfunction=0.90,
            policy_response=0.70,
            contagion=0.60,
            duration=0.70,
        ),
        indicators={
            "sofr_iorb_spread_bps": 10,  # Tight funding
            "cp_treasury_spread_bps": 15,
            "term_premium_10y_bps": -10,  # Flat curve
            "ig_oas_bps": 60,  # Historic low — complacency
            "hy_oas_bps": 250,  # Compressed — breach zone
            "basis_trade_size_billions": 280,
            "treasury_spec_net_percentile": 70,
            "svxy_aum_millions": 0,
            "vix_level": 11,  # Historic low
            "vix_term_structure": 1.06,
            "rv_iv_gap_pct": 15,
            "policy_room_bps": 525,  # FF 5.25%
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 40,
            "em_flow_pct_weekly": 1.0,
            "gsib_cds_avg_bps": 25,  # Banks at tightest
            "dxy_3m_change_pct": -2.0,
            "embi_spread_bps": 180,  # Historic tight
            "global_equity_corr": 0.40,
        },
        context=(
            "Credit spreads at all-time lows. VIX at 10. "
            "CDO issuance at peak. Housing bubble fully inflated. "
            "Classic complacency — compressed valuations flag risk buildup."
        ),
    ),

    "bnp_paribas_2007": HistoricalScenario(
        name="BNP Paribas Freeze",
        date=datetime(2007, 8, 9),
        description="BNP froze three subprime funds; interbank market seized",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["liquidity", "valuation"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.60,
            mkt_dysfunction=0.40,
            policy_response=0.55,
            contagion=0.45,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 80,  # LIBOR-OIS spiked from 10bps
            "cp_treasury_spread_bps": 85,
            "term_premium_10y_bps": 50,
            "ig_oas_bps": 120,  # Starting to widen
            "hy_oas_bps": 450,
            "basis_trade_size_billions": 320,
            "treasury_spec_net_percentile": 30,
            "svxy_aum_millions": 0,
            "vix_level": 26,
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 40,
            "policy_room_bps": 525,  # FF 5.25%
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 60,
            "em_flow_pct_weekly": -1.5,
            "gsib_cds_avg_bps": 90,  # European bank stress
            "dxy_3m_change_pct": -1.0,
            "embi_spread_bps": 250,
            "global_equity_corr": 0.65,
        },
        context=(
            "BNP Paribas froze three subprime-linked funds. "
            "LIBOR-OIS spiked from 10bps to 80bps overnight. "
            "Subprime contagion begins. Treasuries rallied."
        ),
    ),

    "euro_sovereign_peak_2011": HistoricalScenario(
        name="European Sovereign Debt Crisis Peak",
        date=datetime(2011, 11, 23),
        description="Italian/Spanish yields at danger zone; Draghi pre-'whatever it takes'",
        expected_mac_range=(0.35, 0.50),
        expected_breaches=["contagion", "valuation"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.45,
            policy_response=0.55,
            contagion=0.25,
            duration=0.30,
        ),
        indicators={
            "sofr_iorb_spread_bps": 40,
            "cp_treasury_spread_bps": 50,
            "cross_currency_basis_bps": -110,  # EUR/USD severe
            "term_premium_10y_bps": 120,
            "ig_oas_bps": 210,
            "hy_oas_bps": 760,
            "basis_trade_size_billions": 220,
            "treasury_spec_net_percentile": 72,
            "svxy_aum_millions": 80,
            "vix_level": 35,
            "vix_term_structure": 0.86,
            "rv_iv_gap_pct": 42,
            "policy_room_bps": 10,  # At ELB
            "fed_balance_sheet_gdp_pct": 18,
            "core_pce_vs_target_bps": 80,
            "em_flow_pct_weekly": -2.0,
            "gsib_cds_avg_bps": 250,  # European bank CDS extreme
            "dxy_3m_change_pct": 4.0,
            "embi_spread_bps": 500,
            "global_equity_corr": 0.82,
        },
        context=(
            "Italian 10Y yield hit 7.5%. Spanish yields above 6.5%. "
            "TARGET2 imbalances peaked at EUR 1T. "
            "ECB had not yet launched OMT. US Treasuries massive beneficiary."
        ),
    ),

    "taper_tantrum_2013": HistoricalScenario(
        name="Taper Tantrum",
        date=datetime(2013, 6, 24),
        description="Bernanke signals QE tapering; EM 'Fragile Five' sell off",
        expected_mac_range=(0.50, 0.65),
        expected_breaches=[],
        treasury_hedge_worked=False,  # Bonds sold off on taper fears
        csr=CrisisSeverityScores(
            drawdown=0.65,
            mkt_dysfunction=0.80,
            policy_response=0.70,
            contagion=0.45,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 15,
            "cp_treasury_spread_bps": 20,
            "term_premium_10y_bps": 180,  # Surged from 100
            "ig_oas_bps": 125,
            "hy_oas_bps": 430,
            "basis_trade_size_billions": 280,
            "treasury_spec_net_percentile": 82,  # Long crowding
            "svxy_aum_millions": 200,
            "vix_level": 20,
            "vix_term_structure": 0.95,
            "rv_iv_gap_pct": 25,
            "policy_room_bps": 15,  # At ELB
            "fed_balance_sheet_gdp_pct": 22,
            "core_pce_vs_target_bps": -40,  # Below target
            "em_flow_pct_weekly": -3.5,  # Fragile Five outflows
            "gsib_cds_avg_bps": 65,
            "dxy_3m_change_pct": 3.0,
            "embi_spread_bps": 400,
            "global_equity_corr": 0.65,
        },
        context=(
            "Bernanke's May 22 testimony signaled tapering. "
            "10Y yield surged from 1.6% to 3.0%. EM currencies crashed. "
            "'Fragile Five' (BRA, IND, IDN, TUR, ZAF) under severe pressure. "
            "Treasury hedge failed as bonds were the source of stress."
        ),
    ),

    "china_devaluation_2015": HistoricalScenario(
        name="China Devaluation",
        date=datetime(2015, 8, 24),
        description="PBOC devalued yuan; global equity rout; VIX spiked to 40",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["volatility"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.60,
            policy_response=0.80,
            contagion=0.45,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 15,
            "cp_treasury_spread_bps": 25,
            "term_premium_10y_bps": 80,
            "ig_oas_bps": 155,
            "hy_oas_bps": 530,
            "basis_trade_size_billions": 350,
            "treasury_spec_net_percentile": 60,
            "svxy_aum_millions": 400,
            "vix_level": 40,  # Spiked sharply
            "vix_term_structure": 0.80,
            "rv_iv_gap_pct": 50,
            "policy_room_bps": 15,  # At ELB (pre-liftoff)
            "fed_balance_sheet_gdp_pct": 24,
            "core_pce_vs_target_bps": -30,
            "em_flow_pct_weekly": -3.0,
            "gsib_cds_avg_bps": 75,
            "dxy_3m_change_pct": 3.0,
            "embi_spread_bps": 480,
            "global_equity_corr": 0.78,
        },
        context=(
            "PBOC surprised markets with 3% yuan devaluation. "
            "S&P fell 11% in a week. VIX spiked to 40. "
            "Fed delayed Sept rate hike. Treasuries rallied as safe haven."
        ),
    ),

    "energy_credit_2015": HistoricalScenario(
        name="Energy Credit Stress / Oil Collapse",
        date=datetime(2016, 2, 11),
        description="Oil to $26; HY energy spreads blow out; recession fears",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["valuation"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.65,
            policy_response=0.70,
            contagion=0.55,
            duration=0.40,
        ),
        indicators={
            "sofr_iorb_spread_bps": 20,
            "cp_treasury_spread_bps": 35,
            "term_premium_10y_bps": 80,
            "ig_oas_bps": 180,
            "hy_oas_bps": 810,  # Near breach
            "basis_trade_size_billions": 380,
            "treasury_spec_net_percentile": 65,
            "svxy_aum_millions": 350,
            "vix_level": 28,
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 35,
            "policy_room_bps": 38,  # FF just lifted off in Dec 2015
            "fed_balance_sheet_gdp_pct": 24,
            "core_pce_vs_target_bps": -20,
            "em_flow_pct_weekly": -2.0,
            "gsib_cds_avg_bps": 100,
            "dxy_3m_change_pct": 2.0,
            "embi_spread_bps": 520,
            "global_equity_corr": 0.70,
        },
        context=(
            "Oil crashed from $100 to $26. Energy HY defaults spiked. "
            "Recession fears. Deutsche Bank CDS widened. "
            "Treasuries rallied strongly as safe haven."
        ),
    ),

    "q4_selloff_2018": HistoricalScenario(
        name="Q4 2018 Selloff / Fed Pivot",
        date=datetime(2018, 12, 24),
        description="Fed tightening + QT; S&P 500 down 20%; Christmas Eve low",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["volatility", "policy"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.45,
            mkt_dysfunction=0.70,
            policy_response=0.55,
            contagion=0.65,
            duration=0.45,
        ),
        indicators={
            "sofr_iorb_spread_bps": 10,
            "cp_treasury_spread_bps": 30,
            "term_premium_10y_bps": 15,  # Curve nearly inverted
            "ig_oas_bps": 150,
            "hy_oas_bps": 530,
            "basis_trade_size_billions": 400,
            "treasury_spec_net_percentile": 88,
            "svxy_aum_millions": 300,
            "vix_level": 36,
            "vix_term_structure": 0.82,
            "rv_iv_gap_pct": 42,
            "policy_room_bps": 240,  # FF 2.40%
            "fed_balance_sheet_gdp_pct": 20,
            "core_pce_vs_target_bps": -5,  # Near target
            "em_flow_pct_weekly": -1.5,
            "gsib_cds_avg_bps": 80,
            "dxy_3m_change_pct": 2.0,
            "embi_spread_bps": 420,
            "global_equity_corr": 0.72,
        },
        context=(
            "Powell's 'long way from neutral' + QT on autopilot. "
            "S&P 500 fell 20%. Christmas Eve low. "
            "Powell pivoted in Jan 2019. Treasuries rallied during selloff."
        ),
    ),

    "em_crisis_2018": HistoricalScenario(
        name="2018 EM Crisis (Turkey/Argentina)",
        date=datetime(2018, 8, 13),
        description="Turkish lira -40%, Argentine peso -50%; EM contagion fears",
        expected_mac_range=(0.50, 0.65),
        expected_breaches=["contagion"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.75,
            policy_response=0.80,
            contagion=0.40,
            duration=0.55,
        ),
        indicators={
            "sofr_iorb_spread_bps": 8,
            "cp_treasury_spread_bps": 20,
            "term_premium_10y_bps": 30,
            "ig_oas_bps": 110,
            "hy_oas_bps": 350,
            "basis_trade_size_billions": 380,
            "treasury_spec_net_percentile": 80,
            "svxy_aum_millions": 350,
            "vix_level": 16,
            "vix_term_structure": 1.02,
            "rv_iv_gap_pct": 18,
            "policy_room_bps": 192,  # FF 1.92%
            "fed_balance_sheet_gdp_pct": 21,
            "core_pce_vs_target_bps": 10,
            "em_flow_pct_weekly": -3.5,  # Severe EM outflows
            "gsib_cds_avg_bps": 65,
            "dxy_3m_change_pct": 6.0,  # Strong dollar crushing EM
            "embi_spread_bps": 480,
            "global_equity_corr": 0.55,
        },
        context=(
            "Turkish lira collapsed 40% (Erdogan vs central bank). "
            "Argentina peso -50%. Contagion fears to SA, Russia. "
            "US largely insulated. Treasuries benefited from flight to quality."
        ),
    ),

    "evergrande_2021": HistoricalScenario(
        name="Evergrande / China Property Crisis",
        date=datetime(2021, 9, 20),
        description="Evergrande default fears; China property sector stress",
        expected_mac_range=(0.55, 0.70),
        expected_breaches=[],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.70,
            mkt_dysfunction=0.85,
            policy_response=0.80,
            contagion=0.55,
            duration=0.65,
        ),
        indicators={
            "sofr_iorb_spread_bps": 0,
            "cp_treasury_spread_bps": 10,
            "term_premium_10y_bps": 60,
            "ig_oas_bps": 95,
            "hy_oas_bps": 310,
            "basis_trade_size_billions": 520,
            "treasury_spec_net_percentile": 50,
            "svxy_aum_millions": 420,
            "vix_level": 25,
            "vix_term_structure": 0.92,
            "rv_iv_gap_pct": 28,
            "policy_room_bps": 10,  # At ELB
            "fed_balance_sheet_gdp_pct": 36,
            "core_pce_vs_target_bps": 150,
            "em_flow_pct_weekly": -1.5,
            "gsib_cds_avg_bps": 55,
            "dxy_3m_change_pct": 1.0,
            "embi_spread_bps": 340,
            "global_equity_corr": 0.62,
        },
        context=(
            "Evergrande missed bond payments. $300B in liabilities. "
            "Fears of systemic China property meltdown. "
            "Contained — no major US transmission. Treasuries stable."
        ),
    ),

    "uk_ldi_crisis_2022": HistoricalScenario(
        name="UK LDI / Pension Crisis",
        date=datetime(2022, 9, 28),
        description="Mini-budget chaos; gilt yields spike 150bps in 3 days; BoE intervenes",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["volatility", "policy"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.35,
            policy_response=0.40,
            contagion=0.55,
            duration=0.60,
        ),
        indicators={
            "sofr_iorb_spread_bps": -5,
            "cp_treasury_spread_bps": 20,
            "cross_currency_basis_bps": -50,
            "term_premium_10y_bps": 50,
            "ig_oas_bps": 155,
            "hy_oas_bps": 520,
            "basis_trade_size_billions": 560,
            "treasury_spec_net_percentile": 40,
            "svxy_aum_millions": 280,
            "vix_level": 32,
            "vix_term_structure": 0.88,
            "rv_iv_gap_pct": 38,
            "policy_room_bps": 308,  # FF 3.08%
            "fed_balance_sheet_gdp_pct": 34,
            "core_pce_vs_target_bps": 300,  # Inflation very high
            "em_flow_pct_weekly": -1.5,
            "gsib_cds_avg_bps": 95,
            "dxy_3m_change_pct": 8.0,  # Extreme dollar strength
            "embi_spread_bps": 420,
            "global_equity_corr": 0.75,
        },
        context=(
            "Truss/Kwarteng mini-budget triggered gilt collapse. "
            "UK 30Y gilt yield spiked to 5.1%. LDI margin calls cascaded. "
            "BoE emergency bond buying. Global spillover contained. "
            "US Treasuries actually rallied as haven."
        ),
    ),

    "yen_carry_unwind_2024": HistoricalScenario(
        name="Yen Carry Trade Unwind",
        date=datetime(2024, 8, 5),
        description="BoJ hike triggered yen surge; global carry trade unwind; Nikkei -12%",
        expected_mac_range=(0.40, 0.55),
        expected_breaches=["positioning", "volatility"],
        treasury_hedge_worked=True,
        csr=CrisisSeverityScores(
            drawdown=0.55,
            mkt_dysfunction=0.55,
            policy_response=0.75,
            contagion=0.40,
            duration=0.65,
        ),
        indicators={
            "sofr_iorb_spread_bps": -5,
            "cp_treasury_spread_bps": 8,
            "term_premium_10y_bps": 15,
            "ig_oas_bps": 105,
            "hy_oas_bps": 360,
            "basis_trade_size_billions": 680,
            "treasury_spec_net_percentile": 92,  # Extreme positioning
            "svxy_aum_millions": 550,
            "vix_level": 65,  # Intraday spike
            "vix_term_structure": 0.72,
            "rv_iv_gap_pct": 55,
            "policy_room_bps": 538,  # FF 5.38%
            "fed_balance_sheet_gdp_pct": 28,
            "core_pce_vs_target_bps": 80,
            "em_flow_pct_weekly": -2.5,
            "gsib_cds_avg_bps": 70,
            "dxy_3m_change_pct": -4.0,  # Dollar weakening (yen surging)
            "embi_spread_bps": 320,
            "global_equity_corr": 0.85,
        },
        context=(
            "BoJ surprised with rate hike. Yen surged 3% in days. "
            "Global carry trades unwound simultaneously. "
            "Nikkei fell 12% in one day. VIX spiked to 65 intraday. "
            "Recovered within a week. Treasuries rallied on risk-off."
        ),
    ),
}


def get_scenario(name: str) -> Optional[HistoricalScenario]:
    """Get a historical scenario by name."""
    return KNOWN_EVENTS.get(name)


def list_scenarios() -> list[str]:
    """List available scenario names."""
    return list(KNOWN_EVENTS.keys())
