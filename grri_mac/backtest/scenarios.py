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
    "volmageddon_2018": HistoricalScenario(
        name="Volmageddon",
        date=datetime(2018, 2, 5),
        description="VIX spiked 116%, XIV collapsed, short-vol strategies wiped out",
        expected_mac_range=(0.25, 0.45),
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
        },
        context="Short-vol ETFs like XIV collapsed. VIX futures inverted. "
                "Fed had room to cut. Treasuries rallied as flight to safety.",
    ),

    "repo_spike_2019": HistoricalScenario(
        name="Repo Market Spike",
        date=datetime(2019, 9, 17),
        description="Overnight repo rates spiked to 10%, Fed intervened with liquidity",
        expected_mac_range=(0.40, 0.60),
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
        expected_breaches=["liquidity", "positioning", "volatility"],
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
