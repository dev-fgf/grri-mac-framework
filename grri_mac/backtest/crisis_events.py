"""Crisis event annotations for backtest validation.

This module defines major financial crisis events from 2004-2024
for validating the MAC framework's predictive power.
"""

from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CrisisEvent:
    """A financial crisis event with metadata."""

    name: str
    start_date: datetime
    end_date: datetime
    affected_countries: List[str]  # ISO country codes
    expected_pillars_in_breach: List[str]
    expected_mac_range: tuple[float, float]  # (min, max)
    severity: str  # "moderate", "high", "extreme"
    description: str
    key_indicators: Optional[dict] = None  # Key indicator values during crisis


# Comprehensive crisis event database
CRISIS_EVENTS = [
    CrisisEvent(
        name="Pre-GFC Build-up",
        start_date=datetime(2006, 1, 1),
        end_date=datetime(2007, 7, 31),
        affected_countries=["USA", "GBR", "DEU", "FRA", "ITA", "ESP"],
        expected_pillars_in_breach=["valuation", "positioning"],
        expected_mac_range=(0.50, 0.70),
        severity="moderate",
        description="Credit spreads compressed to historic lows, housing bubble peak",
        key_indicators={
            "ig_oas": 60,  # Historic low in 2007
            "hy_oas": 250,  # Compressed
            "vix": 11,  # Complacency
        }
    ),

    CrisisEvent(
        name="BNP Paribas Freeze",
        start_date=datetime(2007, 8, 9),
        end_date=datetime(2007, 9, 30),
        affected_countries=["USA", "GBR", "FRA"],
        expected_pillars_in_breach=["liquidity", "valuation"],
        expected_mac_range=(0.40, 0.60),
        severity="high",
        description="BNP Paribas freezes redemptions, subprime contagion begins",
        key_indicators={
            "libor_ois_spread": 80,  # Spiked from 10 bps
            "ig_oas": 120,  # Starting to widen
        }
    ),

    CrisisEvent(
        name="Bear Stearns Collapse",
        start_date=datetime(2008, 3, 16),
        end_date=datetime(2008, 4, 30),
        affected_countries=["USA", "GBR"],
        expected_pillars_in_breach=["liquidity", "valuation", "volatility"],
        expected_mac_range=(0.30, 0.50),
        severity="high",
        description="Bear Stearns fails, Fed facilitates JPMorgan acquisition",
        key_indicators={
            "libor_ois_spread": 120,
            "vix": 32,
            "ig_oas": 200,
        }
    ),

    CrisisEvent(
        name="Lehman Brothers / Global Financial Crisis Peak",
        start_date=datetime(2008, 9, 15),
        end_date=datetime(2009, 3, 9),
        affected_countries=["USA", "GBR", "DEU", "FRA", "ITA", "JPN", "CAN"],
        expected_pillars_in_breach=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        expected_mac_range=(0.10, 0.30),
        severity="extreme",
        description="Lehman bankruptcy, systemic crisis, markets freeze globally",
        key_indicators={
            "libor_ois_spread": 364,  # Peak October 2008
            "vix": 89,  # All-time high
            "ig_oas": 640,
            "hy_oas": 2200,
            "cross_currency_basis": -240,  # EUR/USD severe dollar shortage
        }
    ),

    CrisisEvent(
        name="Flash Crash",
        start_date=datetime(2010, 5, 6),
        end_date=datetime(2010, 5, 7),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility", "positioning"],
        expected_mac_range=(0.45, 0.55),
        severity="moderate",
        description="Intraday 9% S&P 500 decline, high-frequency trading breakdown",
        key_indicators={
            "vix": 40,  # Intraday spike
        }
    ),

    CrisisEvent(
        name="European Sovereign Debt Crisis",
        start_date=datetime(2011, 7, 1),
        end_date=datetime(2012, 9, 6),
        affected_countries=["DEU", "FRA", "ITA", "ESP", "GRC", "PRT"],
        expected_pillars_in_breach=["valuation", "contagion"],
        expected_mac_range=(0.35, 0.55),
        severity="high",
        description="Periphery sovereign spreads spike, TARGET2 imbalances peak, Draghi 'whatever it takes'",
        key_indicators={
            "target2_imbalances": 1000,  # EUR billions
            "italian_10y_spread": 550,  # vs Bunds
            "spanish_10y_spread": 650,
        }
    ),

    CrisisEvent(
        name="US Debt Ceiling / Downgrade",
        start_date=datetime(2011, 8, 5),
        end_date=datetime(2011, 8, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility", "valuation"],
        expected_mac_range=(0.40, 0.55),
        severity="moderate",
        description="S&P downgrades US to AA+, VIX spikes, equity selloff",
        key_indicators={
            "vix": 48,
        }
    ),

    CrisisEvent(
        name="Taper Tantrum",
        start_date=datetime(2013, 5, 22),
        end_date=datetime(2013, 9, 18),
        affected_countries=["BRA", "IND", "IDN", "TUR", "ZAF"],  # Fragile Five
        expected_pillars_in_breach=["volatility", "contagion", "policy"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description="Fed signals QE tapering, EM capital flight, 'Fragile Five' under pressure",
        key_indicators={
            "em_currency_depreciation": 15,  # Percent
            "cross_border_outflows": -110,  # Billions
        }
    ),

    CrisisEvent(
        name="China Devaluation",
        start_date=datetime(2015, 8, 11),
        end_date=datetime(2015, 9, 30),
        affected_countries=["CHN", "USA", "Emerging Markets"],
        expected_pillars_in_breach=["volatility", "positioning"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description="PBOC devalues yuan, triggers global equity selloff, commodity rout",
        key_indicators={
            "vix": 40,
            "cnh_depreciation": 3,  # Percent
        }
    ),

    CrisisEvent(
        name="Q4 2018 Selloff / Fed Pivot",
        start_date=datetime(2018, 10, 3),
        end_date=datetime(2018, 12, 26),
        affected_countries=["USA"],
        expected_pillars_in_breach=["policy", "volatility", "positioning"],
        expected_mac_range=(0.40, 0.60),
        severity="moderate",
        description="Fed tightening + QT, S&P 500 down 20%, Christmas Eve low, Powell pivots",
        key_indicators={
            "vix": 36,
            "fed_funds": 2.5,  # Peak tightening
        }
    ),

    CrisisEvent(
        name="Volmageddon",
        start_date=datetime(2018, 2, 5),
        end_date=datetime(2018, 2, 8),
        affected_countries=["USA"],
        expected_pillars_in_breach=["positioning", "volatility"],
        expected_mac_range=(0.35, 0.50),
        severity="moderate",
        description="VIX ETF implosion, short vol blowup, XIV termination",
        key_indicators={
            "vix": 50,  # Spike from 14
            "vix_one_day_change": 20,  # Points
        }
    ),

    CrisisEvent(
        name="COVID-19 Pandemic",
        start_date=datetime(2020, 3, 9),
        end_date=datetime(2020, 3, 23),
        affected_countries=["USA", "GBR", "DEU", "FRA", "ITA", "JPN", "CHN", "all G20"],
        expected_pillars_in_breach=["liquidity", "valuation", "positioning", "volatility", "contagion"],
        expected_mac_range=(0.10, 0.25),
        severity="extreme",
        description="Global pandemic, fastest bear market ever, all asset class selloff, Fed unlimited QE",
        key_indicators={
            "vix": 82,  # Second-highest ever
            "cp_spread": 120,
            "cross_currency_basis": -70,  # EUR/USD
            "sp500_drawdown": -34,  # Peak-to-trough
        }
    ),

    CrisisEvent(
        name="UK Pension Crisis / Rate Shock",
        start_date=datetime(2022, 9, 26),
        end_date=datetime(2022, 10, 14),
        affected_countries=["GBR", "USA", "Eurozone"],
        expected_pillars_in_breach=["policy", "valuation", "volatility"],
        expected_mac_range=(0.35, 0.55),
        severity="high",
        description="Mini-budget chaos, gilt yields spike, BoE intervenes, LDI crisis",
        key_indicators={
            "uk_30y_gilt_yield": 5.1,  # Spike
            "gilt_yield_one_day_change": 100,  # Basis points
        }
    ),

    CrisisEvent(
        name="SVB / Regional Banking Crisis",
        start_date=datetime(2023, 3, 10),
        end_date=datetime(2023, 3, 20),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity", "policy", "valuation"],
        expected_mac_range=(0.40, 0.55),
        severity="high",
        description="Silicon Valley Bank fails, Signature Bank fails, Credit Suisse absorbed",
        key_indicators={
            "bank_stock_decline": -30,  # Percent regional banks
            "2y_treasury": 3.8,  # Fell sharply on flight to quality
        }
    ),

    CrisisEvent(
        name="Yen Carry Trade Unwind",
        start_date=datetime(2024, 8, 5),
        end_date=datetime(2024, 8, 12),
        affected_countries=["JPN", "USA", "global"],
        expected_pillars_in_breach=["positioning", "volatility", "contagion"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description="BoJ hikes, yen surges 3% in days, unwinds global carry trades, Nikkei -12% single day",
        key_indicators={
            "vix": 65,  # Intraday spike
            "usdjpy": -3,  # Percent move
            "nikkei": -12,  # Single-day decline
        }
    ),
]


def get_crisis_for_date(date: datetime) -> Optional[CrisisEvent]:
    """
    Find if a date falls within a crisis period.

    Args:
        date: Date to check

    Returns:
        CrisisEvent if date is in crisis period, None otherwise
    """
    for crisis in CRISIS_EVENTS:
        if crisis.start_date <= date <= crisis.end_date:
            return crisis
    return None


def get_crises_in_range(start_date: datetime, end_date: datetime) -> List[CrisisEvent]:
    """
    Get all crises that overlap with a date range.

    Args:
        start_date: Range start
        end_date: Range end

    Returns:
        List of overlapping crisis events
    """
    overlapping = []
    for crisis in CRISIS_EVENTS:
        # Crisis overlaps if it starts before range ends and ends after range starts
        if crisis.start_date <= end_date and crisis.end_date >= start_date:
            overlapping.append(crisis)
    return overlapping


def get_pre_gfc_crises() -> List[CrisisEvent]:
    """Get crisis events from pre-GFC period (2004-2008)."""
    gfc_start = datetime(2008, 9, 15)
    return [c for c in CRISIS_EVENTS if c.end_date < gfc_start]


def get_major_crises() -> List[CrisisEvent]:
    """Get only 'high' and 'extreme' severity crises."""
    return [c for c in CRISIS_EVENTS if c.severity in ["high", "extreme"]]
