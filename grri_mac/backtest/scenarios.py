"""Historical scenarios for backtesting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


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

    # Actual indicator values at the time
    indicators: dict = field(default_factory=dict)

    # Market context
    context: str = ""


# Known historical events with approximate indicator values
# These are calibrated from market data around each event
KNOWN_EVENTS = {
    # =========================================================================
    # PRE-GFC ERA (1998-2007)
    # =========================================================================

    "ltcm_crisis_1998": HistoricalScenario(
        name="LTCM Crisis",
        date=datetime(1998, 9, 23),
        description="Long-Term Capital Management near-collapse, Fed-orchestrated bailout",
        expected_mac_range=(0.20, 0.40),
        expected_breaches=["liquidity", "positioning", "volatility"],  # Contagion thin but not breaching
        treasury_hedge_worked=True,
        indicators={
            # Liquidity - stressed but manageable (TED spread ~100bps)
            "sofr_iorb_spread_bps": 45,  # Using TED spread proxy
            "cp_treasury_spread_bps": 80,
            # Valuation - flight to quality compressed spreads
            "term_premium_10y_bps": 60,
            "ig_oas_bps": 140,
            "hy_oas_bps": 550,
            # Positioning - EXTREME leverage unwind
            "basis_trade_size_billions": 200,  # Lower absolute but massive relative
            "treasury_spec_net_percentile": 8,  # Extreme positioning
            "svxy_aum_millions": 0,  # Didn't exist
            # Volatility - spiked to 45
            "vix_level": 45,
            "vix_term_structure": 0.85,
            "rv_iv_gap_pct": 50,
            # Policy - Fed had room, cut rates
            "fed_funds_vs_neutral_bps": 200,
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": -20,
            # Contagion - Russian default triggered global EM contagion
            "em_flow_pct_weekly": -2.5,  # Massive EM outflows
            "gsib_cds_avg_bps": 110,  # Banking stress
            "dxy_3m_change_pct": 5.0,  # Dollar strengthening
            "embi_spread_bps": 1200,  # Russian default drove EMBI to extremes
            "global_equity_corr": 0.78,  # High contagion
        },
        context="LTCM had $125B assets on $4B equity. Russian default triggered unwind. "
                "Fed coordinated private sector bailout. Treasuries rallied massively.",
    ),

    "dotcom_peak_2000": HistoricalScenario(
        name="Dot-com Bubble Peak",
        date=datetime(2000, 3, 10),
        description="NASDAQ peaked at 5,048, maximum bubble conditions",
        expected_mac_range=(0.40, 0.60),
        expected_breaches=["liquidity"],  # CP spreads at 50bps triggered breach
        treasury_hedge_worked=True,
        indicators={
            # Liquidity - tight but not broken
            "sofr_iorb_spread_bps": 25,
            "cp_treasury_spread_bps": 50,
            # Valuation - EXTREME compression
            "term_premium_10y_bps": -40,  # Inverted curve
            "ig_oas_bps": 85,  # Very tight
            "hy_oas_bps": 450,
            # Positioning - crowded into tech
            "basis_trade_size_billions": 150,
            "treasury_spec_net_percentile": 75,
            "svxy_aum_millions": 0,
            # Volatility - elevated but not panic
            "vix_level": 24,
            "vix_term_structure": 0.98,
            "rv_iv_gap_pct": 30,
            # Policy - hiking into bubble
            "fed_funds_vs_neutral_bps": 150,
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 40,
            # Contagion - US-centric bubble, limited EM contagion
            "em_flow_pct_weekly": -0.8,  # Mild outflows
            "gsib_cds_avg_bps": 50,  # Healthy banking
            "dxy_3m_change_pct": 2.0,  # Modest dollar strength
            "embi_spread_bps": 700,  # Elevated but not crisis
            "global_equity_corr": 0.55,  # Normal correlation
        },
        context="NASDAQ P/E ratios >100. Fed hiking rates. Credit tight but equities "
                "massively overvalued. Classic bubble peak conditions.",
    ),

    "sept11_2001": HistoricalScenario(
        name="9/11 Attacks",
        date=datetime(2001, 9, 17),
        description="Markets reopened after terrorist attacks, -7% first day",
        expected_mac_range=(0.25, 0.45),
        expected_breaches=["volatility", "liquidity"],
        treasury_hedge_worked=True,
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
            # Policy - aggressive easing
            "fed_funds_vs_neutral_bps": -100,
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 50,
            # Contagion - global shock with high correlation
            "em_flow_pct_weekly": -1.5,  # Flight from risk
            "gsib_cds_avg_bps": 85,  # Elevated but not systemic
            "dxy_3m_change_pct": 3.0,  # Dollar strengthening
            "embi_spread_bps": 850,  # EM stress
            "global_equity_corr": 0.82,  # High contagion - global shock
        },
        context="Exogenous shock. Markets closed 4 days. Fed injected $100B+ liquidity. "
                "Classic flight to quality - Treasuries worked perfectly.",
    ),

    "dotcom_bottom_2002": HistoricalScenario(
        name="Dot-com Crash Bottom",
        date=datetime(2002, 10, 9),
        description="S&P 500 hit cycle low, -49% from peak, Enron/WorldCom frauds",
        expected_mac_range=(0.20, 0.40),
        expected_breaches=["liquidity", "volatility"],  # HY OAS at 1050 just above breach threshold
        treasury_hedge_worked=True,
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
            # Policy - very accommodative
            "fed_funds_vs_neutral_bps": -175,
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 30,
            # Contagion - US corporate crisis, moderate global impact
            "em_flow_pct_weekly": -1.2,  # Outflows but not extreme
            "gsib_cds_avg_bps": 95,  # Elevated
            "dxy_3m_change_pct": -2.0,  # Dollar weakening
            "embi_spread_bps": 750,  # EM stress
            "global_equity_corr": 0.68,  # Elevated correlation
        },
        context="Final capitulation of dot-com bust. Corporate fraud scandals. "
                "Fed at 1.25% providing massive accommodation. Treasuries rallied.",
    ),

    "bear_stearns_2008": HistoricalScenario(
        name="Bear Stearns Collapse",
        date=datetime(2008, 3, 16),
        description="Bear Stearns sold to JPMorgan in emergency Fed-backed deal",
        expected_mac_range=(0.30, 0.50),
        expected_breaches=["liquidity", "volatility"],  # VIX at 32, positioning not extreme yet
        treasury_hedge_worked=True,
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
            # Policy - cutting aggressively
            "fed_funds_vs_neutral_bps": -50,
            "fed_balance_sheet_gdp_pct": 6,
            "core_pce_vs_target_bps": 80,
            # Contagion - early GFC, banking stress spreading
            "em_flow_pct_weekly": -1.8,  # EM flight
            "gsib_cds_avg_bps": 155,  # Banking stress
            "dxy_3m_change_pct": 4.0,  # Dollar strengthening
            "embi_spread_bps": 550,  # EM stress building
            "global_equity_corr": 0.78,  # High contagion
        },
        context="First major GFC casualty. Fed opened discount window to investment banks. "
                "Treasury flight to quality worked - yields dropped sharply.",
    ),

    "lehman_2008": HistoricalScenario(
        name="Lehman Brothers Collapse",
        date=datetime(2008, 9, 15),
        description="Lehman filed bankruptcy, AIG rescue, global financial system seized",
        expected_mac_range=(0.05, 0.20),
        expected_breaches=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        treasury_hedge_worked=True,  # Initially worked, though some dysfunction
        indicators={
            # Liquidity - BROKEN (TED spread 350+bps)
            "sofr_iorb_spread_bps": 350,
            "cp_treasury_spread_bps": 250,
            "cross_currency_basis_bps": -240,
            # Valuation - extreme stress
            "term_premium_10y_bps": 200,
            "ig_oas_bps": 450,
            "hy_oas_bps": 1500,
            # Positioning - forced liquidation
            "basis_trade_size_billions": 600,
            "treasury_spec_net_percentile": 3,
            "svxy_aum_millions": 0,
            # Volatility - near all-time highs
            "vix_level": 65,
            "vix_term_structure": 0.70,
            "rv_iv_gap_pct": 75,
            # Policy - emergency measures
            "fed_funds_vs_neutral_bps": -175,
            "fed_balance_sheet_gdp_pct": 7,
            "core_pce_vs_target_bps": 130,
            # Contagion - GLOBAL SYSTEMIC CRISIS - maximum contagion
            "em_flow_pct_weekly": -4.5,  # Massive capital flight
            "gsib_cds_avg_bps": 350,  # Systemic banking crisis
            "dxy_3m_change_pct": 12.0,  # Dollar squeeze - breach level
            "embi_spread_bps": 850,  # EM crisis
            "global_equity_corr": 0.95,  # Extreme panic correlation - breach
        },
        context="Peak systemic crisis. Money markets froze. Fed launched multiple facilities. "
                "Treasuries worked as haven initially, some dysfunction in off-the-run.",
    ),

    "flash_crash_2010": HistoricalScenario(
        name="Flash Crash",
        date=datetime(2010, 5, 6),
        description="DJIA dropped 1,000 points in minutes, algorithmic cascade",
        expected_mac_range=(0.40, 0.60),
        expected_breaches=["volatility"],
        treasury_hedge_worked=True,
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
            # Policy - QE1 ongoing
            "fed_funds_vs_neutral_bps": -250,
            "fed_balance_sheet_gdp_pct": 16,
            "core_pce_vs_target_bps": -50,
            # Contagion - European concerns, brief global spike
            "em_flow_pct_weekly": -0.8,  # Brief outflows
            "gsib_cds_avg_bps": 105,  # European bank concerns
            "dxy_3m_change_pct": 5.0,  # Dollar strengthening
            "embi_spread_bps": 450,  # EM OK
            "global_equity_corr": 0.85,  # Spike in correlation during flash
        },
        context="Algorithmic trading cascade, recovered same day. European debt concerns. "
                "Brief dislocation but Treasuries worked as haven.",
    ),

    "us_downgrade_2011": HistoricalScenario(
        name="US Debt Downgrade",
        date=datetime(2011, 8, 8),
        description="S&P downgraded US from AAA to AA+, European debt crisis peaked",
        expected_mac_range=(0.30, 0.50),
        expected_breaches=["volatility", "contagion"],  # European bank CDS stress
        treasury_hedge_worked=True,
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
            # Policy - QE2 ended, Operation Twist coming
            "fed_funds_vs_neutral_bps": -250,
            "fed_balance_sheet_gdp_pct": 18,
            "core_pce_vs_target_bps": 70,
            # Contagion - European crisis spillover, elevated but not extreme
            "em_flow_pct_weekly": -1.5,  # EM outflows
            "gsib_cds_avg_bps": 200,  # European bank stress - thin
            "dxy_3m_change_pct": 2.0,  # Mild dollar strength
            "embi_spread_bps": 500,  # EM elevated
            "global_equity_corr": 0.80,  # High correlation
        },
        context="Paradox: US downgrade triggered flight TO Treasuries, not away. "
                "10Y yield dropped below 2%. Haven status reinforced.",
    ),

    # =========================================================================
    # POST-GFC ERA (2018-2025)
    # =========================================================================

    "volmageddon_2018": HistoricalScenario(
        name="Volmageddon",
        date=datetime(2018, 2, 5),
        description="VIX spiked 116%, XIV collapsed, short-vol strategies wiped out",
        expected_mac_range=(0.35, 0.55),  # Adjusted for 6-pillar framework
        expected_breaches=["volatility", "positioning"],
        treasury_hedge_worked=True,
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
            # Policy - room to act
            "fed_funds_vs_neutral_bps": -75,
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
        description="Overnight repo rates spiked to 10%, Fed intervened with liquidity",
        expected_mac_range=(0.50, 0.70),  # Adjusted for 6-pillar - contagion adds buffer
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
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
            # Policy - limited room
            "fed_funds_vs_neutral_bps": 0,
            "fed_balance_sheet_gdp_pct": 18,
            "core_pce_vs_target_bps": 35,
            # Contagion - US technical issue, no global spillover
            "em_flow_pct_weekly": -0.3,  # Minimal impact
            "gsib_cds_avg_bps": 55,  # Banks healthy
            "dxy_3m_change_pct": 1.0,  # Stable dollar
            "embi_spread_bps": 350,  # EM calm
            "global_equity_corr": 0.50,  # Normal
        },
        context="Corporate tax payments + Treasury settlement drained reserves. "
                "Fed launched repo operations. Treasuries held value.",
    ),

    "covid_crash_2020": HistoricalScenario(
        name="COVID-19 Market Crash",
        date=datetime(2020, 3, 16),
        description="Global pandemic triggered fastest bear market in history, "
                    "Treasury market dysfunction",
        expected_mac_range=(0.10, 0.25),
        expected_breaches=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        treasury_hedge_worked=False,
        indicators={
            # Liquidity - broken
            "sofr_iorb_spread_bps": 85,
            "cp_treasury_spread_bps": 180,
            "cross_currency_basis_bps": -120,
            # Valuation - extremes
            "term_premium_10y_bps": -25,
            "ig_oas_bps": 375,
            "hy_oas_bps": 1100,
            # Positioning - extreme forced selling
            "basis_trade_size_billions": 850,
            "treasury_spec_net_percentile": 2,  # Extreme short
            "svxy_aum_millions": 180,
            # Volatility - record high
            "vix_level": 82.69,  # All-time high
            "vix_term_structure": 0.68,  # Extreme backwardation
            "rv_iv_gap_pct": 85,
            # Policy - at effective lower bound
            "fed_funds_vs_neutral_bps": -250,
            "fed_balance_sheet_gdp_pct": 20,
            "core_pce_vs_target_bps": 30,
            # Contagion - GLOBAL PANDEMIC - maximum contagion
            "em_flow_pct_weekly": -5.0,  # Record outflows
            "gsib_cds_avg_bps": 200,  # Banking stress
            "dxy_3m_change_pct": 8.0,  # Dollar squeeze
            "embi_spread_bps": 700,  # EM crisis
            "global_equity_corr": 0.92,  # Panic correlation - breach
        },
        context="Margin calls forced liquidation of everything including Treasuries. "
                "Fed launched unlimited QE + standing repo. Treasury hedge FAILED - "
                "sold off alongside equities due to basis trade unwind.",
    ),

    "ukraine_invasion_2022": HistoricalScenario(
        name="Russia-Ukraine Invasion",
        date=datetime(2022, 2, 24),
        description="Russia invaded Ukraine, commodity shock, geopolitical crisis",
        expected_mac_range=(0.50, 0.70),
        expected_breaches=[],
        treasury_hedge_worked=True,
        indicators={
            # Liquidity - OK
            "sofr_iorb_spread_bps": 6,
            "cp_treasury_spread_bps": 28,
            # Valuation - reasonable
            "term_premium_10y_bps": 15,
            "ig_oas_bps": 125,
            "hy_oas_bps": 420,
            # Positioning - not extreme
            "basis_trade_size_billions": 520,
            "treasury_spec_net_percentile": 42,
            "svxy_aum_millions": 290,
            # Volatility - elevated but not extreme
            "vix_level": 30,
            "vix_term_structure": 0.96,
            "rv_iv_gap_pct": 28,
            # Policy - behind the curve on inflation
            "fed_funds_vs_neutral_bps": -225,
            "fed_balance_sheet_gdp_pct": 36,
            "core_pce_vs_target_bps": 280,
            # Contagion - geopolitical but contained
            "em_flow_pct_weekly": -2.0,  # EM outflows
            "gsib_cds_avg_bps": 90,  # Mild stress
            "dxy_3m_change_pct": 6.0,  # Dollar strength
            "embi_spread_bps": 450,  # EM elevated
            "global_equity_corr": 0.70,  # Elevated
        },
        context="Classic geopolitical shock absorbed well. Flight to quality into "
                "Treasuries worked. No pillar breaches despite VIX spike.",
    ),

    "svb_crisis_2023": HistoricalScenario(
        name="SVB/Banking Crisis",
        date=datetime(2023, 3, 10),
        description="Silicon Valley Bank collapsed, regional banking crisis",
        expected_mac_range=(0.35, 0.55),
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        indicators={
            # Liquidity - stressed
            "sofr_iorb_spread_bps": 25,
            "cp_treasury_spread_bps": 65,
            # Valuation - inverted curve
            "term_premium_10y_bps": -15,
            "ig_oas_bps": 165,
            "hy_oas_bps": 520,
            # Positioning - some stress
            "basis_trade_size_billions": 600,
            "treasury_spec_net_percentile": 35,
            "svxy_aum_millions": 320,
            # Volatility - spike
            "vix_level": 26,
            "vix_term_structure": 0.94,
            "rv_iv_gap_pct": 35,
            # Policy - hiking cycle
            "fed_funds_vs_neutral_bps": 200,
            "fed_balance_sheet_gdp_pct": 32,
            "core_pce_vs_target_bps": 280,
            # Contagion - US banking, Credit Suisse spillover
            "em_flow_pct_weekly": -1.0,  # Moderate outflows
            "gsib_cds_avg_bps": 125,  # Banking stress
            "dxy_3m_change_pct": -2.0,  # Dollar weakening
            "embi_spread_bps": 420,  # EM stable
            "global_equity_corr": 0.65,  # Elevated
        },
        context="Bank run triggered by duration mismatch. Fed created BTFP facility. "
                "Treasuries rallied sharply as flight to safety worked.",
    ),

    "april_tariffs_2025": HistoricalScenario(
        name="April Tariff Shock",
        date=datetime(2025, 4, 2),
        description="Major tariff announcements triggered positioning unwind",
        expected_mac_range=(0.25, 0.45),
        expected_breaches=["positioning"],
        treasury_hedge_worked=False,
        indicators={
            # Liquidity - moderately stressed
            "sofr_iorb_spread_bps": 15,
            "cp_treasury_spread_bps": 45,
            # Valuation - thin
            "term_premium_10y_bps": 55,
            "ig_oas_bps": 90,
            "hy_oas_bps": 330,
            # Positioning - extreme crowding
            "basis_trade_size_billions": 780,
            "treasury_spec_net_percentile": 97,  # Extreme long
            "svxy_aum_millions": 650,
            # Volatility - elevated
            "vix_level": 28,
            "vix_term_structure": 0.95,
            "rv_iv_gap_pct": 32,
            # Policy - restrictive
            "fed_funds_vs_neutral_bps": 175,
            "fed_balance_sheet_gdp_pct": 26,
            "core_pce_vs_target_bps": 120,
            # Contagion - trade war spillover
            "em_flow_pct_weekly": -2.5,  # EM flight
            "gsib_cds_avg_bps": 85,  # Banks OK
            "dxy_3m_change_pct": 4.0,  # Dollar strength
            "embi_spread_bps": 480,  # EM stress
            "global_equity_corr": 0.78,  # High correlation
        },
        context="Tariff shock combined with extreme Treasury long positioning. "
                "Forced unwind caused Treasuries to sell off WITH equities. "
                "Treasury hedge FAILED due to positioning crowding.",
    ),
}


def get_scenario(name: str) -> Optional[HistoricalScenario]:
    """Get a historical scenario by name."""
    return KNOWN_EVENTS.get(name)


def list_scenarios() -> list[str]:
    """List available scenario names."""
    return list(KNOWN_EVENTS.keys())
