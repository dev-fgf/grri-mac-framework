"""Regime Analysis - Historical market structure and regulatory changes.

This module documents the major structural shifts in US financial markets
that affect how we interpret historical MAC indicators.

Key insight: Raw indicator values are not directly comparable across eras.
A 2% margin debt ratio in 1960 means something different than in 2020.
We must normalize within regimes or use z-scores relative to regime means.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, List, Dict


@dataclass
class MarketRegime:
    """A distinct period in market structure history."""

    name: str
    start_date: datetime
    end_date: Optional[datetime]  # None = ongoing

    # Regulatory environment
    reg_t_margin: str  # Regulation T margin requirement
    market_access: str  # Who could trade

    # Structural characteristics
    description: str
    key_events: List[str]

    # Threshold adjustments (multipliers vs modern baseline)
    margin_debt_baseline: float  # Expected "normal" margin/market-cap %
    credit_spread_baseline: float  # Expected "normal" BAA-AAA spread
    vol_baseline: float  # Expected "normal" realized vol

    # Crisis events in this regime
    crises: List[Dict]


# Historical regime definitions
REGIME_PERIODS = [
    MarketRegime(
        name="Post-War Reconstruction",
        start_date=datetime(1945, 10, 1),
        end_date=datetime(1953, 12, 31),
        reg_t_margin="75-100%",  # Very restrictive post-1929 crash
        market_access="Wealthy individuals, institutions only",
        description="""
        Post-WWII period with extremely restrictive margin rules.
        Memory of 1929 crash still fresh. Market dominated by wealthy
        individuals and institutional investors. Low participation rates.
        """,
        key_events=[
            "1946: Post-war recession",
            "1949: Mild recession",
            "1950: Korean War begins",
        ],
        margin_debt_baseline=0.8,  # Very low leverage
        credit_spread_baseline=0.8,  # Tight spreads, confidence
        vol_baseline=15.0,  # Moderate volatility
        crises=[
            {"date": "1946-09", "name": "Post-War Adjustment", "severity": "moderate"},
            {"date": "1949-06", "name": "1949 Recession", "severity": "mild"},
        ]
    ),

    MarketRegime(
        name="Eisenhower Prosperity",
        start_date=datetime(1954, 1, 1),
        end_date=datetime(1962, 5, 31),
        reg_t_margin="50-70%",  # Gradually loosening
        market_access="Upper-middle class entering via mutual funds",
        description="""
        Post-Korean War expansion. Introduction of mutual funds brings
        some middle-class participation. Margin requirements still high
        but loosening. Fed funds rate established 1954.
        """,
        key_events=[
            "1954-07: Fed funds rate data begins",
            "1957-58: Recession",
            "1961: Kennedy takes office",
            "1962-05: Flash Crash (Kennedy Slide)",
        ],
        margin_debt_baseline=1.2,  # Slightly higher as restrictions ease
        credit_spread_baseline=0.7,  # Tight spreads, economic optimism
        vol_baseline=12.0,  # Low volatility era
        crises=[
            {"date": "1957-08", "name": "1957-58 Recession", "severity": "moderate"},
            {"date": "1962-05-28", "name": "Kennedy Slide (Flash Crash)", "severity": "high",
             "description": "Dow fell 5.7% in one day, 27% from December peak"},
        ]
    ),

    MarketRegime(
        name="Go-Go Years",
        start_date=datetime(1962, 6, 1),
        end_date=datetime(1970, 5, 31),
        reg_t_margin="50-70%",
        market_access="Growing retail via mutual funds, 'Nifty Fifty' era",
        description="""
        Speculative era with 'go-go' mutual funds and growth stocks.
        Vietnam War escalation. Rising inflation. Penn Central bankruptcy
        (1970) marks first major commercial paper crisis.
        """,
        key_events=[
            "1964: Tax cut stimulates economy",
            "1966: Credit Crunch",
            "1968: MLK and RFK assassinated, civil unrest",
            "1969-70: Recession begins",
            "1970-06: Penn Central bankruptcy",
        ],
        margin_debt_baseline=1.8,  # Higher speculation
        credit_spread_baseline=0.9,  # Widening with uncertainty
        vol_baseline=14.0,
        crises=[
            {"date": "1966-08", "name": "1966 Credit Crunch", "severity": "high",
             "description": "First post-war credit crisis, S&L stress"},
            {"date": "1970-06-21", "name": "Penn Central Bankruptcy", "severity": "high",
             "description": "First major commercial paper default, $200M"},
        ]
    ),

    MarketRegime(
        name="Stagflation Era",
        start_date=datetime(1970, 6, 1),
        end_date=datetime(1982, 7, 31),
        reg_t_margin="50%",  # Standardized
        market_access="Limited retail, high inflation erodes savings",
        description="""
        Nixon shock (gold window closure), OPEC oil embargo, double-digit
        inflation, Volcker rate shock. Equity markets severely depressed.
        Real returns negative for over a decade.
        """,
        key_events=[
            "1971-08-15: Nixon closes gold window",
            "1973-10: OPEC oil embargo",
            "1974-08: Nixon resigns",
            "1975-05-01: May Day - commission deregulation",
            "1979-10: Volcker becomes Fed chair",
            "1980: Inflation peaks at 14%",
            "1981-82: Deep recession, unemployment 10%+",
        ],
        margin_debt_baseline=1.0,  # Deleveraging in bear market
        credit_spread_baseline=1.5,  # Wide spreads, uncertainty
        vol_baseline=18.0,  # High volatility
        crises=[
            {"date": "1973-10-17", "name": "1973 Oil Crisis", "severity": "extreme",
             "description": "OPEC embargo, market fell 45% over 2 years"},
            {"date": "1974-10", "name": "1974 Bear Market Bottom", "severity": "extreme",
             "description": "S&P down 48% from Jan 1973 peak"},
            {"date": "1980-03", "name": "Hunt Brothers Silver Crash", "severity": "high",
             "description": "Commodities collapse, Fed emergency lending"},
            {"date": "1982-08", "name": "Mexican Debt Crisis", "severity": "high",
             "description": "Sovereign default fears, banking stress"},
        ]
    ),

    MarketRegime(
        name="Reagan Bull Market",
        start_date=datetime(1982, 8, 1),
        end_date=datetime(1987, 10, 31),
        reg_t_margin="50%",
        market_access="401(k)s created (1978), IRAs expanded (1981), growing retail",
        description="""
        Volcker tames inflation, Reagan tax cuts, deregulation.
        Start of great bull market. Program trading emerges.
        Ends with 1987 crash.
        """,
        key_events=[
            "1982-08: Bull market begins",
            "1983: 401(k) plans gain popularity",
            "1984: Continental Illinois bailout",
            "1986: Tax Reform Act",
            "1987-10-19: Black Monday crash",
        ],
        margin_debt_baseline=1.5,  # Rising with bull market
        credit_spread_baseline=1.0,  # Normalizing
        vol_baseline=15.0,  # Declining from stagflation era
        crises=[
            {"date": "1984-05", "name": "Continental Illinois Failure", "severity": "moderate",
             "description": "Largest bank failure to date, too-big-to-fail precedent"},
            {"date": "1987-10-19", "name": "Black Monday", "severity": "extreme",
             "description": "Dow fell 22.6% in one day, largest single-day drop ever"},
        ]
    ),

    MarketRegime(
        name="Early Modern Era",
        start_date=datetime(1987, 11, 1),
        end_date=datetime(1999, 12, 31),
        reg_t_margin="50%",
        market_access="Discount brokers (Schwab), online trading begins late 90s",
        description="""
        Post-crash recovery. S&L crisis. Gulf War recession.
        Greenspan put established. Internet boom. VIX created (1993).
        LTCM crisis (1998).
        """,
        key_events=[
            "1989: S&L crisis peaks",
            "1990-91: Gulf War recession",
            "1993: VIX index launched",
            "1994: Fed rate shock",
            "1995: Netscape IPO, internet boom begins",
            "1997: Asian financial crisis",
            "1998-09: LTCM collapse",
            "1999: Dot-com mania peaks",
        ],
        margin_debt_baseline=2.0,  # Higher with democratization
        credit_spread_baseline=0.8,  # Tight in expansion
        vol_baseline=16.0,  # VIX average
        crises=[
            {"date": "1989-08", "name": "S&L Crisis Peak", "severity": "high",
             "description": "1,000+ thrift failures, $160B bailout"},
            {"date": "1990-08", "name": "Gulf War Recession", "severity": "moderate"},
            {"date": "1994-02", "name": "1994 Bond Massacre", "severity": "moderate",
             "description": "Surprise Fed hikes devastate bond portfolios"},
            {"date": "1997-10", "name": "Asian Financial Crisis", "severity": "high"},
            {"date": "1998-09-23", "name": "LTCM Collapse", "severity": "high",
             "description": "Fed-orchestrated bailout of hedge fund"},
        ]
    ),

    MarketRegime(
        name="Modern Era",
        start_date=datetime(2000, 1, 1),
        end_date=None,  # Ongoing
        reg_t_margin="50%",
        market_access="Full retail access, zero commissions (2019+), mobile apps",
        description="""
        Dot-com bust, 9/11, GFC, QE era, COVID. Modern MAC framework
        designed for this period. Full data availability.
        """,
        key_events=[
            "2000-03: Dot-com bubble bursts",
            "2001-09-11: 9/11 attacks",
            "2007-08: GFC begins",
            "2008-09-15: Lehman Brothers",
            "2009-03: QE1 begins",
            "2020-03: COVID crash",
            "2022: Fed rate hiking cycle",
        ],
        margin_debt_baseline=2.5,  # High leverage normalized
        credit_spread_baseline=0.6,  # Compressed by QE
        vol_baseline=17.0,  # VIX long-term average
        crises=[
            {"date": "2000-03", "name": "Dot-Com Bust", "severity": "high"},
            {"date": "2001-09-11", "name": "9/11 Attacks", "severity": "high"},
            {"date": "2008-09-15", "name": "Lehman Brothers / GFC", "severity": "extreme"},
            {"date": "2010-05-06", "name": "Flash Crash", "severity": "moderate"},
            {"date": "2020-03-16", "name": "COVID Crash", "severity": "extreme"},
        ]
    ),
]


def get_regime_for_date(date: datetime) -> Optional[MarketRegime]:
    """Get the market regime for a specific date."""
    for regime in REGIME_PERIODS:
        if regime.start_date <= date:
            if regime.end_date is None or date <= regime.end_date:
                return regime
    return None


def get_regime_thresholds(date: datetime) -> Dict[str, float]:
    """Get era-adjusted thresholds for a specific date.

    These are multipliers to apply to modern baselines.
    """
    regime = get_regime_for_date(date)
    if not regime:
        return {
            "margin_debt_baseline": 2.5,
            "credit_spread_baseline": 0.6,
            "vol_baseline": 17.0,
        }

    return {
        "margin_debt_baseline": regime.margin_debt_baseline,
        "credit_spread_baseline": regime.credit_spread_baseline,
        "vol_baseline": regime.vol_baseline,
    }


def calculate_z_score(
    value: float,
    series: List[float],
    window: int = 52,  # ~1 year of weekly data
) -> float:
    """Calculate z-score (standard deviations from rolling mean).

    This normalizes indicators across regimes by measuring deviation
    from recent history rather than absolute levels.
    """
    if len(series) < window:
        return 0.0

    recent = series[-window:]
    mean = sum(recent) / len(recent)
    variance = sum((x - mean) ** 2 for x in recent) / len(recent)
    std = variance ** 0.5

    if std < 0.0001:  # Avoid division by zero
        return 0.0

    return (value - mean) / std


def get_crisis_events_in_range(
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Get all crisis events within a date range."""
    events = []
    for regime in REGIME_PERIODS:
        for crisis in regime.crises:
            # Parse date (handle various formats)
            date_str = crisis["date"]
            try:
                if len(date_str) == 7:  # YYYY-MM
                    crisis_date = datetime.strptime(date_str, "%Y-%m")
                elif len(date_str) == 10:  # YYYY-MM-DD
                    crisis_date = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    continue

                if start_date <= crisis_date <= end_date:
                    events.append({
                        "date": crisis_date,
                        "name": crisis["name"],
                        "severity": crisis["severity"],
                        "regime": regime.name,
                        "description": crisis.get("description", ""),
                    })
            except ValueError:
                continue

    return sorted(events, key=lambda x: x["date"])


# Regulation T Historical Changes
REG_T_HISTORY: List[Dict[str, Any]] = [
    {"date": "1934-10-01", "margin": 45, "note": "Initial Reg T"},
    {"date": "1936-04-01", "margin": 55, "note": "Increased"},
    {"date": "1937-11-01", "margin": 40, "note": "Reduced for recession"},
    {"date": "1945-02-05", "margin": 50, "note": ""},
    {"date": "1945-07-05", "margin": 75, "note": "Post-war tightening"},
    {"date": "1946-01-21", "margin": 100, "note": "Maximum restriction"},
    {"date": "1947-02-01", "margin": 75, "note": "Easing begins"},
    {"date": "1949-03-30", "margin": 50, "note": "Recession relief"},
    {"date": "1951-01-17", "margin": 75, "note": "Korean War tightening"},
    {"date": "1953-02-20", "margin": 50, "note": "Post-war normalization"},
    {"date": "1955-04-23", "margin": 60, "note": ""},
    {"date": "1955-10-16", "margin": 70, "note": "Bull market concerns"},
    {"date": "1958-01-16", "margin": 50, "note": "Recession relief"},
    {"date": "1958-08-05", "margin": 70, "note": "Recovery"},
    {"date": "1960-10-16", "margin": 70, "note": ""},
    {"date": "1962-07-10", "margin": 50, "note": "Post-Flash Crash"},
    {"date": "1963-11-06", "margin": 70, "note": "Go-go years"},
    {"date": "1968-06-08", "margin": 80, "note": "Peak speculation"},
    {"date": "1970-05-06", "margin": 65, "note": "Bear market"},
    {"date": "1971-12-06", "margin": 55, "note": ""},
    {"date": "1972-11-24", "margin": 65, "note": ""},
    {"date": "1974-01-03", "margin": 50, "note": "Bear market - current level"},
    # Margin has been 50% since 1974
]


def get_reg_t_margin_at_date(date: datetime) -> int:
    """Get the Regulation T margin requirement at a specific date."""
    margin = 50  # Default
    for change in REG_T_HISTORY:
        change_date = datetime.strptime(change["date"], "%Y-%m-%d")
        if change_date <= date:
            margin = change["margin"]
        else:
            break
    return margin
