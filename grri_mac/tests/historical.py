"""Historical backtesting against known market events.

Critical validation: run framework against known events and verify:
1. March 2020: MAC should show < 0.2, multiple breach flags
2. February 2022: MAC should show > 0.5, no breach flags
3. April 2025: MAC should show ~0.35, Positioning breach flag

Key insight: Every time Treasuries failed as a hedge, Positioning pillar was breaching.
"""

from dataclasses import dataclass

from ..mac.composite import calculate_mac, MACResult
from ..mac.multiplier import mac_to_multiplier
from ..pillars.liquidity import LiquidityIndicators
from ..pillars.valuation import ValuationIndicators
from ..pillars.positioning import PositioningIndicators
from ..pillars.volatility import VolatilityIndicators
from ..pillars.policy import PolicyIndicators


@dataclass
class HistoricalEvent:
    """Historical market event for backtesting."""

    name: str
    date: str
    expected_mac: float
    expected_mac_range: tuple[float, float]
    expected_breaches: list[str]
    treasury_hedge_worked: bool
    notes: str


@dataclass
class HistoricalSnapshot:
    """Snapshot of market conditions at a point in time."""

    liquidity: LiquidityIndicators
    valuation: ValuationIndicators
    positioning: PositioningIndicators
    volatility: VolatilityIndicators
    policy: PolicyIndicators


# Historical reference events from specification
HISTORICAL_EVENTS = {
    "volmageddon_2018": HistoricalEvent(
        name="Volmageddon",
        date="Feb 2018",
        expected_mac=0.35,
        expected_mac_range=(0.25, 0.45),
        expected_breaches=["volatility", "positioning"],
        treasury_hedge_worked=True,
        notes="VIX spike, short-vol products imploded, but Treasury hedge worked",
    ),
    "repo_spike_2019": HistoricalEvent(
        name="Repo Spike",
        date="Sep 2019",
        expected_mac=0.55,
        expected_mac_range=(0.45, 0.65),
        expected_breaches=["liquidity"],
        treasury_hedge_worked=True,
        notes="Overnight repo rates spiked, Fed intervened, Treasury hedge worked",
    ),
    "covid_crash_2020": HistoricalEvent(
        name="COVID Crash",
        date="Mar 2020",
        expected_mac=0.18,
        expected_mac_range=(0.10, 0.25),
        expected_breaches=["liquidity", "positioning", "volatility"],
        treasury_hedge_worked=False,
        notes="Multiple pillars breached, Treasury hedge FAILED",
    ),
    "ukraine_invasion_2022": HistoricalEvent(
        name="Ukraine Invasion",
        date="Feb 2022",
        expected_mac=0.62,
        expected_mac_range=(0.50, 0.75),
        expected_breaches=[],
        treasury_hedge_worked=True,
        notes="Geopolitical shock but no pillar breaches, Treasury hedge worked",
    ),
    "april_tariffs_2025": HistoricalEvent(
        name="April Tariffs",
        date="Apr 2025",
        expected_mac=0.35,
        expected_mac_range=(0.25, 0.45),
        expected_breaches=["positioning"],
        treasury_hedge_worked=False,
        notes="Positioning breach caused Treasury hedge FAILURE",
    ),
}

# Historical snapshots with approximate indicator values
HISTORICAL_SNAPSHOTS = {
    "volmageddon_2018": HistoricalSnapshot(
        liquidity=LiquidityIndicators(
            sofr_iorb_spread_bps=10,
            cp_treasury_spread_bps=30,
        ),
        valuation=ValuationIndicators(
            term_premium_10y_bps=50,
            ig_oas_bps=100,
            hy_oas_bps=350,
        ),
        positioning=PositioningIndicators(
            basis_trade_size_billions=300,
            treasury_spec_net_percentile=92,  # Extreme
            svxy_aum_millions=1200,  # High short-vol exposure
        ),
        volatility=VolatilityIndicators(
            vix_level=37,  # Spiked
            vix_term_structure=0.85,  # Inverted
        ),
        policy=PolicyIndicators(
            policy_room_bps=-50,
            fed_balance_sheet_gdp_pct=22,
        ),
    ),
    "repo_spike_2019": HistoricalSnapshot(
        liquidity=LiquidityIndicators(
            sofr_iorb_spread_bps=300,  # Extreme spike
            cp_treasury_spread_bps=40,
        ),
        valuation=ValuationIndicators(
            term_premium_10y_bps=30,
            ig_oas_bps=110,
            hy_oas_bps=380,
        ),
        positioning=PositioningIndicators(
            basis_trade_size_billions=450,
            treasury_spec_net_percentile=60,
            svxy_aum_millions=400,
        ),
        volatility=VolatilityIndicators(
            vix_level=16,
            vix_term_structure=1.03,
        ),
        policy=PolicyIndicators(
            policy_room_bps=0,
            fed_balance_sheet_gdp_pct=18,
        ),
    ),
    "covid_crash_2020": HistoricalSnapshot(
        liquidity=LiquidityIndicators(
            sofr_iorb_spread_bps=100,  # Stressed
            cp_treasury_spread_bps=150,  # Very stressed
        ),
        valuation=ValuationIndicators(
            term_premium_10y_bps=-20,  # Negative
            ig_oas_bps=300,  # Widened but ok
            hy_oas_bps=800,  # Very wide
        ),
        positioning=PositioningIndicators(
            basis_trade_size_billions=800,  # Very high
            treasury_spec_net_percentile=3,  # Extreme
            svxy_aum_millions=200,
        ),
        volatility=VolatilityIndicators(
            vix_level=82,  # Record high
            vix_term_structure=0.70,  # Deep inversion
        ),
        policy=PolicyIndicators(
            policy_room_bps=-150,  # At ELB
            fed_balance_sheet_gdp_pct=20,
        ),
    ),
    "ukraine_invasion_2022": HistoricalSnapshot(
        liquidity=LiquidityIndicators(
            sofr_iorb_spread_bps=8,
            cp_treasury_spread_bps=25,
        ),
        valuation=ValuationIndicators(
            term_premium_10y_bps=20,
            ig_oas_bps=120,
            hy_oas_bps=400,
        ),
        positioning=PositioningIndicators(
            basis_trade_size_billions=500,
            treasury_spec_net_percentile=45,
            svxy_aum_millions=300,
        ),
        volatility=VolatilityIndicators(
            vix_level=32,
            vix_term_structure=0.97,
        ),
        policy=PolicyIndicators(
            policy_room_bps=-200,
            fed_balance_sheet_gdp_pct=35,
        ),
    ),
    "april_tariffs_2025": HistoricalSnapshot(
        liquidity=LiquidityIndicators(
            sofr_iorb_spread_bps=12,
            cp_treasury_spread_bps=35,
        ),
        valuation=ValuationIndicators(
            term_premium_10y_bps=60,
            ig_oas_bps=95,
            hy_oas_bps=340,
        ),
        positioning=PositioningIndicators(
            basis_trade_size_billions=750,  # High
            treasury_spec_net_percentile=96,  # Extreme long
            svxy_aum_millions=600,
        ),
        volatility=VolatilityIndicators(
            vix_level=28,
            vix_term_structure=0.98,
        ),
        policy=PolicyIndicators(
            policy_room_bps=200,
            fed_balance_sheet_gdp_pct=28,
        ),
    ),
}


def calculate_historical_mac(snapshot: HistoricalSnapshot) -> MACResult:
    """
    Calculate MAC from historical snapshot.

    Args:
        snapshot: Historical market conditions

    Returns:
        MACResult for the snapshot
    """
    from ..pillars import (
        LiquidityPillar,
        ValuationPillar,
        PositioningPillar,
        VolatilityPillar,
        PolicyPillar,
    )

    # Calculate each pillar
    liquidity = LiquidityPillar().calculate(snapshot.liquidity)
    valuation = ValuationPillar().calculate(snapshot.valuation)
    positioning = PositioningPillar().calculate(snapshot.positioning)
    volatility = VolatilityPillar().calculate(snapshot.volatility)
    policy = PolicyPillar().calculate(snapshot.policy)

    pillars = {
        "liquidity": liquidity.composite,
        "valuation": valuation.composite,
        "positioning": positioning.composite,
        "volatility": volatility.composite,
        "policy": policy.composite,
    }

    return calculate_mac(pillars)


def run_backtest(event_key: str) -> dict:
    """
    Run backtest for a single historical event.

    Args:
        event_key: Key from HISTORICAL_EVENTS

    Returns:
        Dict with backtest results
    """
    event = HISTORICAL_EVENTS.get(event_key)
    snapshot = HISTORICAL_SNAPSHOTS.get(event_key)

    if event is None or snapshot is None:
        raise ValueError(f"Unknown event: {event_key}")

    # Calculate MAC
    mac_result = calculate_historical_mac(snapshot)
    multiplier = mac_to_multiplier(mac_result.mac_score)

    # Check if MAC is in expected range
    mac_in_range = (
        event.expected_mac_range[0]
        <= mac_result.mac_score
        <= event.expected_mac_range[1]
    )

    # Check breach flags
    expected_set = set(event.expected_breaches)
    actual_set = set(mac_result.breach_flags)
    breaches_match = expected_set == actual_set

    # Key insight check: Positioning breach should correlate with Treasury hedge failure
    positioning_breach = "positioning" in mac_result.breach_flags
    hedge_failure_predicted = positioning_breach == (not event.treasury_hedge_worked)

    return {
        "event": event.name,
        "date": event.date,
        "mac_score": mac_result.mac_score,
        "expected_mac": event.expected_mac,
        "mac_in_range": mac_in_range,
        "breach_flags": mac_result.breach_flags,
        "expected_breaches": event.expected_breaches,
        "breaches_match": breaches_match,
        "multiplier": multiplier.multiplier,
        "treasury_hedge_worked": event.treasury_hedge_worked,
        "hedge_failure_predicted": hedge_failure_predicted,
        "pillar_scores": mac_result.pillar_scores,
        "notes": event.notes,
    }


def run_all_backtests() -> list[dict]:
    """Run backtests for all historical events."""
    results = []
    for event_key in HISTORICAL_EVENTS:
        try:
            result = run_backtest(event_key)
            results.append(result)
        except Exception as e:
            results.append({
                "event": event_key,
                "error": str(e),
            })
    return results


def format_backtest_report(results: list[dict]) -> str:
    """Format backtest results as text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("MAC FRAMEWORK HISTORICAL BACKTEST REPORT")
    lines.append("=" * 70)
    lines.append("")

    passed = 0
    failed = 0

    for result in results:
        if "error" in result:
            lines.append(f"ERROR: {result['event']} - {result['error']}")
            failed += 1
            continue

        lines.append(f"EVENT: {result['event']} ({result['date']})")
        lines.append("-" * 50)

        # MAC score
        mac_status = "PASS" if result["mac_in_range"] else "FAIL"
        lines.append(
            f"MAC Score: {result['mac_score']:.3f} "
            f"(expected ~{result['expected_mac']:.2f}) [{mac_status}]"
        )

        # Breach flags
        breach_status = "PASS" if result["breaches_match"] else "FAIL"
        lines.append(
            f"Breaches: {result['breach_flags']} "
            f"(expected {result['expected_breaches']}) [{breach_status}]"
        )

        # Hedge prediction
        hedge_status = "PASS" if result["hedge_failure_predicted"] else "FAIL"
        hedge_outcome = "Worked" if result["treasury_hedge_worked"] else "FAILED"
        lines.append(
            f"Treasury Hedge: {hedge_outcome} [{hedge_status}]"
        )

        # Multiplier
        if result["multiplier"]:
            lines.append(f"Multiplier: {result['multiplier']:.2f}x")
        else:
            lines.append("Multiplier: REGIME BREAK")

        # Overall
        all_pass = (
            result["mac_in_range"]
            and result["breaches_match"]
            and result["hedge_failure_predicted"]
        )
        if all_pass:
            lines.append("OVERALL: PASS")
            passed += 1
        else:
            lines.append("OVERALL: FAIL")
            failed += 1

        lines.append("")

    lines.append("=" * 70)
    lines.append(f"SUMMARY: {passed} passed, {failed} failed out of {len(results)}")
    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    results = run_all_backtests()
    print(format_backtest_report(results))
