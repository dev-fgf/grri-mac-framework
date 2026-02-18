"""Crisis event annotations for backtest validation.

This module defines major financial crisis events from 1962-2025
for validating the MAC framework's predictive power across multiple
monetary policy regimes.
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
    # ==========================================================================
    # PRE-FED ERA (1907-1913) - No Central Bank
    # No lender of last resort, gold standard constraint, J.P. Morgan era
    # Data: NBER Macrohistory, Schwert volatility, Shiller equity prices
    # ==========================================================================
    CrisisEvent(
        name="Panic of 1907",
        start_date=datetime(1907, 10, 14),
        end_date=datetime(1908, 2, 28),
        affected_countries=["USA", "GBR", "FRA", "DEU", "ITA"],
        expected_pillars_in_breach=[
            "liquidity", "volatility",
            "policy", "contagion",
        ],
        expected_mac_range=(0.15, 0.35),
        severity="extreme",
        description=(
            "Trust company runs, stock market crash "
            "(-50%), J.P. Morgan private bailout. "
            "No central bank existed. Gold reserves "
            "strained by 1906 SF earthquake."
        ),
        key_indicators={
            "call_money_rate_pct": 125,  # Spiked to 125% intraday
            "schwert_vol_pct": 45,  # ~45% annualised
            "rr_govt_spread_bps": 250,  # Railroad-govt spread
            "gold_reserve_constraint": "severe",
        }
    ),

    CrisisEvent(
        name="1910-1911 Recession / Market Decline",
        start_date=datetime(1910, 7, 1),
        end_date=datetime(1911, 1, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description=(
            "Mild recession following antitrust "
            "actions against Standard Oil. "
            "Market declined ~15%. Led to creation "
            "of Pujo Committee investigating "
            "money trusts."
        ),
        key_indicators={
            "call_money_rate_pct": 6,
            "schwert_vol_pct": 18,
        }
    ),

    # ==========================================================================
    # EARLY FED ERA (1913-1929) - New Central Bank, Gold Standard
    # Fed learning to operate, WWI financing, post-war adjustment
    # ==========================================================================
    CrisisEvent(
        name="1914 Exchange Closure / WWI Outbreak",
        start_date=datetime(1914, 7, 31),
        end_date=datetime(1914, 12, 12),
        affected_countries=["USA", "GBR", "FRA", "DEU", "AUT"],
        expected_pillars_in_breach=[
            "liquidity", "contagion", "policy",
        ],
        expected_mac_range=(0.20, 0.40),
        severity="extreme",
        description=(
            "NYSE closed for 4.5 months "
            "(Jul 31 - Dec 12). European gold "
            "demands, transatlantic cable system "
            "disrupted. Fed opened Nov 16 "
            "during crisis."
        ),
        key_indicators={
            "exchange_closed_days": 137,
            "gold_outflows": "severe",
            "gbp_usd_deviation_pct": 5,
        }
    ),

    CrisisEvent(
        name="Post-WWI Deflation / 1920-21 Depression",
        start_date=datetime(1920, 1, 1),
        end_date=datetime(1921, 7, 31),
        affected_countries=["USA", "GBR", "DEU"],
        expected_pillars_in_breach=["policy", "valuation"],
        expected_mac_range=(0.30, 0.50),
        severity="high",
        description=(
            "Sharpest deflation in US history "
            "(-18% CPI). Fed raised discount "
            "rate to 7%. DJIA fell 47%. "
            "Agricultural sector devastated. "
            "Quick V-shaped recovery."
        ),
        key_indicators={
            "fed_discount_rate_pct": 7.0,
            "cpi_change_pct": -18,
            "baa_aaa_spread_bps": 120,
        }
    ),

    CrisisEvent(
        name="1929 Stock Market Crash",
        start_date=datetime(1929, 10, 24),
        end_date=datetime(1929, 11, 13),
        affected_countries=["USA", "GBR", "DEU", "FRA", "CAN"],
        expected_pillars_in_breach=["volatility", "positioning", "liquidity"],
        expected_mac_range=(0.15, 0.35),
        severity="extreme",
        description=(
            "Black Thursday / Black Tuesday. "
            "DJIA fell 25% in 2 days. "
            "Extreme margin leverage. NYSE "
            "margin debt at record levels."
        ),
        key_indicators={
            "schwert_vol_pct": 40,
            "djia_decline_pct": -40,  # Through Nov
            "margin_debt_to_gdp_pct": 8.5,  # Historically extreme
            "call_money_rate_pct": 20,
        }
    ),

    # ==========================================================================
    # GREAT DEPRESSION / WWII ERA (1929-1945)
    # Banking panics, gold standard collapse, wartime controls
    # ==========================================================================
    CrisisEvent(
        name="Banking Panic of 1930-31",
        start_date=datetime(1930, 10, 1),
        end_date=datetime(1931, 10, 31),
        affected_countries=["USA", "GBR", "DEU", "AUT"],
        expected_pillars_in_breach=[
            "liquidity", "contagion",
            "policy", "valuation",
        ],
        expected_mac_range=(0.10, 0.25),
        severity="extreme",
        description=(
            "First wave of US bank failures. "
            "1,352 banks failed in 1930. "
            "Austrian Creditanstalt collapse "
            "(May 1931) triggered European crisis. "
            "UK abandoned gold standard (Sep 1931)."
        ),
        key_indicators={
            "bank_failures": 1352,
            "baa_aaa_spread_bps": 300,
            "gold_reserve_pressure": "severe",
        }
    ),

    CrisisEvent(
        name="1933 Bank Holiday / FDR Emergency",
        start_date=datetime(1933, 2, 14),
        end_date=datetime(1933, 4, 30),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity", "policy", "valuation"],
        expected_mac_range=(0.10, 0.25),
        severity="extreme",
        description=(
            "National bank holiday declared "
            "March 6-13. Emergency Banking Act. "
            "US left gold standard. DJIA had "
            "fallen 89% from 1929 peak. "
            "Glass-Steagall Act passed June 1933."
        ),
        key_indicators={
            "banks_closed": 4004,
            "djia_from_peak_pct": -89,
            "gold_standard": "abandoned",
        }
    ),

    CrisisEvent(
        name="1937-38 Recession / Roosevelt Recession",
        start_date=datetime(1937, 8, 1),
        end_date=datetime(1938, 6, 30),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility", "policy"],
        expected_mac_range=(0.30, 0.50),
        severity="high",
        description=(
            "DJIA fell 49%. Fed doubled reserve "
            "requirements (1936-37), fiscal "
            "tightening. Third worst recession "
            "in 20th century."
        ),
        key_indicators={
            "schwert_vol_pct": 35,
            "djia_decline_pct": -49,
            "reserve_req_doubled": True,
        }
    ),

    # ==========================================================================
    # POST-WAR ERA (1945-1962) - Bretton Woods, Fed-Treasury Accord
    # Fixed exchange rates, regulated banking, limited financial innovation
    # ==========================================================================
    CrisisEvent(
        name="1948-49 Post-War Recession",
        start_date=datetime(1948, 11, 1),
        end_date=datetime(1949, 10, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["policy"],
        expected_mac_range=(0.50, 0.65),
        severity="moderate",
        description="Post-WWII inventory adjustment. S&P fell 21%. "
                    "Transition from wartime to peacetime economy.",
        key_indicators={
            "sp500_decline_pct": -21,
            "policy_constrained": "Fed-Treasury peg",
        }
    ),

    CrisisEvent(
        name="1953 Post-Korean War Recession",
        start_date=datetime(1953, 7, 1),
        end_date=datetime(1954, 5, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["policy"],
        expected_mac_range=(0.50, 0.65),
        severity="moderate",
        description=(
            "Defense spending cuts post-Korea. "
            "Fed-Treasury Accord (1951) "
            "gave Fed independence. First "
            "post-Accord recession test."
        ),
        key_indicators={
            "sp500_decline_pct": -15,
            "fed_independent": True,
        }
    ),

    CrisisEvent(
        name="1957-58 Recession / Sputnik Shock",
        start_date=datetime(1957, 8, 1),
        end_date=datetime(1958, 4, 30),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description=(
            "Eisenhower recession. S&P fell 22%. "
            "Sputnik (Oct 57) added geopolitical "
            "anxiety. Fed cut rates from 3.5% "
            "to 1.75%."
        ),
        key_indicators={
            "sp500_decline_pct": -22,
            "fed_funds_pct": 3.5,
        }
    ),

    # ==========================================================================
    # PRE-BRETTON WOODS COLLAPSE (1962-1971) - Fixed Exchange Rates
    # Fed constrained by gold convertibility, limited tools
    # ==========================================================================
    CrisisEvent(
        name="Kennedy Slide / Flash Crash of 1962",
        start_date=datetime(1962, 5, 28),
        end_date=datetime(1962, 6, 26),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility", "positioning"],
        expected_mac_range=(0.40, 0.55),
        severity="moderate",
        description=(
            "Fastest market decline since 1929, "
            "-22.5% in 3 months. Steel price "
            "confrontation with JFK."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 74,
            "sp500_decline_pct": -22.5,
        }
    ),

    CrisisEvent(
        name="Credit Crunch of 1966",
        start_date=datetime(1966, 8, 1),
        end_date=datetime(1966, 10, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity", "policy"],
        expected_mac_range=(0.40, 0.55),
        severity="moderate",
        description=(
            "Fed's first inflation fight since "
            "WWII. Severe disintermediation, "
            "savings outflows from thrifts."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 52,
            "fed_funds_pct": 5.75,
            "savings_outflow": "severe",
        }
    ),

    CrisisEvent(
        name="Penn Central Bankruptcy",
        start_date=datetime(1970, 6, 21),
        end_date=datetime(1970, 8, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity", "contagion"],
        expected_mac_range=(0.40, 0.55),
        severity="high",
        description=(
            "Largest US bankruptcy to date ($7B). "
            "Commercial paper market freezes. "
            "Fed opens discount window."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 77,
            "cp_market": "frozen",
            "fed_response": "discount window opened",
        }
    ),

    # ==========================================================================
    # POST-BRETTON WOODS / STAGFLATION (1971-1982)
    # Fed gains flexibility but faces inflation crisis
    # ==========================================================================
    CrisisEvent(
        name="Nixon Shock / Dollar Devaluation",
        start_date=datetime(1971, 8, 15),
        end_date=datetime(1971, 12, 31),
        affected_countries=["USA", "GBR", "DEU", "JPN", "FRA"],
        expected_pillars_in_breach=["policy", "contagion"],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description=(
            "End of gold convertibility, "
            "wage-price controls, 10% import "
            "surcharge. Bretton Woods collapses."
        ),
        key_indicators={
            "gold_price_move_pct": 8.5,
            "dollar_devaluation_pct": 7.9,
        }
    ),

    CrisisEvent(
        name="1973 Oil Crisis / OPEC Embargo",
        start_date=datetime(1973, 10, 17),
        end_date=datetime(1974, 3, 18),
        affected_countries=["USA", "GBR", "DEU", "JPN", "FRA", "ITA", "CAN"],
        expected_pillars_in_breach=[
            "volatility", "contagion", "policy",
        ],
        expected_mac_range=(0.35, 0.50),
        severity="high",
        description=(
            "OPEC oil embargo quadruples prices. "
            "Stagflation begins. Market believes "
            "Fed cannot solve both inflation "
            "and recession."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 81,
            "oil_price_move_pct": 300,
            "inflation_pct": 11.0,
        }
    ),

    CrisisEvent(
        name="1974 Bear Market Bottom",
        start_date=datetime(1974, 9, 1),
        end_date=datetime(1974, 12, 6),
        affected_countries=["USA", "GBR", "DEU"],
        expected_pillars_in_breach=[
            "volatility", "liquidity", "policy",
        ],
        expected_mac_range=(0.30, 0.45),
        severity="extreme",
        description=(
            "S&P falls 48% from peak. Worst "
            "recession since Depression. Franklin "
            "National Bank fails. Faith in Fed "
            "at nadir."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 174,  # Extreme credit stress
            "sp500_decline_pct": -48,
            "franklin_national": "failed",
            "inflation_pct": 12.2,
        }
    ),

    CrisisEvent(
        name="Volcker Shock / 1980 Recession",
        start_date=datetime(1980, 1, 1),
        end_date=datetime(1980, 7, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["policy", "liquidity"],
        expected_mac_range=(0.40, 0.55),
        severity="high",
        description=(
            "Volcker raises Fed Funds to 20%. "
            "Intentional recession to break "
            "inflation. Markets question "
            "Fed resolve."
        ),
        key_indicators={
            "fed_funds_pct": 20.0,
            "prime_rate_pct": 21.5,
            "inflation_pct": 14.6,
        }
    ),

    CrisisEvent(
        name="1981-82 Double-Dip Recession",
        start_date=datetime(1981, 7, 1),
        end_date=datetime(1982, 11, 30),
        affected_countries=["USA", "CAN", "GBR", "DEU"],
        expected_pillars_in_breach=[
            "liquidity", "policy", "contagion",
        ],
        expected_mac_range=(0.35, 0.50),
        severity="high",
        description=(
            "Worst unemployment since Depression "
            "(10.8%). Penn Square Bank fails. "
            "Continental Illinois crisis begins."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 150,
            "unemployment_pct": 10.8,
            "fed_funds_pct": 14.0,
        }
    ),

    # ==========================================================================
    # GREAT MODERATION ERA (1982-2006) - Greenspan Put emerges
    # ==========================================================================
    CrisisEvent(
        name="Continental Illinois / Too Big to Fail",
        start_date=datetime(1984, 5, 9),
        end_date=datetime(1984, 7, 26),
        affected_countries=["USA"],
        expected_pillars_in_breach=["liquidity", "contagion"],
        expected_mac_range=(0.45, 0.55),
        severity="moderate",
        description=(
            "7th largest US bank fails. FDIC "
            "introduces TBTF doctrine. First "
            "modern systemic rescue."
        ),
        key_indicators={
            "baa_aaa_spread_bps": 120,
            "fdic_exposure_bn": 4.5,
        }
    ),

    CrisisEvent(
        name="Black Monday 1987",
        start_date=datetime(1987, 10, 19),
        end_date=datetime(1987, 12, 31),
        affected_countries=["USA", "GBR", "DEU", "JPN", "HKG", "AUS"],
        expected_pillars_in_breach=[
            "volatility", "liquidity", "positioning",
        ],
        expected_mac_range=(0.30, 0.45),
        severity="extreme",
        description=(
            "Largest one-day percentage decline "
            "in history (-22.6%). Greenspan "
            "provides immediate liquidity."
        ),
        key_indicators={
            "sp500_one_day_pct": -22.6,
            "vxo": 150,  # Implied volatility spike
            "fed_response": "immediate liquidity",
        }
    ),

    # ==========================================================================
    # PRE-2006 CRISES (require historical proxies)
    # ==========================================================================
    CrisisEvent(
        name="Asian Financial Crisis",
        start_date=datetime(1997, 7, 2),
        end_date=datetime(1998, 1, 31),
        affected_countries=["THA", "IDN", "KOR", "MYS", "PHL", "HKG", "SGP"],
        expected_pillars_in_breach=["contagion", "volatility"],
        expected_mac_range=(0.35, 0.55),
        severity="high",
        description=(
            "Thai baht devaluation triggers "
            "Asian currency crisis, contagion "
            "to global EM"
        ),
        key_indicators={
            "vix": 38,  # Oct 1997 peak
            "ted_spread_bps": 50,
            "em_spread_bps": 600,
        }
    ),

    CrisisEvent(
        name="Russian Default / LTCM Crisis",
        start_date=datetime(1998, 8, 17),
        end_date=datetime(1998, 10, 31),
        affected_countries=["RUS", "USA", "GBR", "DEU"],
        expected_pillars_in_breach=[
            "liquidity", "volatility",
            "contagion", "positioning",
        ],
        expected_mac_range=(0.25, 0.45),
        severity="extreme",
        description=(
            "Russian debt default triggers LTCM "
            "near-collapse, Fed orchestrates "
            "bailout"
        ),
        key_indicators={
            "vix": 45,  # Oct 8, 1998 peak
            "ted_spread_bps": 120,  # Severe funding stress
            "baa_aaa_spread_bps": 120,  # Credit stress
            "ltcm_leverage": "25:1",  # $125B assets on $4B equity
        }
    ),

    CrisisEvent(
        name="Dot-com Bubble Peak",
        start_date=datetime(2000, 3, 10),
        end_date=datetime(2000, 4, 14),
        affected_countries=["USA", "GBR", "DEU"],
        expected_pillars_in_breach=["valuation", "positioning"],
        expected_mac_range=(0.40, 0.60),
        severity="moderate",
        description="NASDAQ peaks at 5,048, tech bubble begins deflating",
        key_indicators={
            "nasdaq_pe": 200,  # Extreme valuations
            "vix": 25,
        }
    ),

    CrisisEvent(
        name="September 11 Attacks",
        start_date=datetime(2001, 9, 11),
        end_date=datetime(2001, 10, 31),
        affected_countries=["USA"],
        expected_pillars_in_breach=["volatility", "policy"],
        expected_mac_range=(0.35, 0.50),
        severity="high",
        description=(
            "Terrorist attacks close markets, "
            "Fed provides massive liquidity"
        ),
        key_indicators={
            "vix": 43,  # Sep 21 peak after reopening
            "ted_spread_bps": 65,
            "fed_cut_bps": 100,  # 100bp emergency cut
        }
    ),

    CrisisEvent(
        name="Corporate Scandals (Enron/WorldCom)",
        start_date=datetime(2002, 6, 1),
        end_date=datetime(2002, 10, 9),
        affected_countries=["USA"],
        expected_pillars_in_breach=["valuation", "volatility"],
        expected_mac_range=(0.35, 0.50),
        severity="high",
        description=(
            "Enron and WorldCom bankruptcies, "
            "market reaches post-dot-com lows"
        ),
        key_indicators={
            "vix": 45,  # July/Oct 2002 peaks
            "ig_oas": 280,
            "hy_oas": 1100,
        }
    ),

    # ==========================================================================
    # GFC ERA (2006-2009)
    # ==========================================================================
    CrisisEvent(
        name="Pre-GFC Build-up",
        start_date=datetime(2006, 1, 1),
        end_date=datetime(2007, 7, 31),
        affected_countries=["USA", "GBR", "DEU", "FRA", "ITA", "ESP"],
        expected_pillars_in_breach=["valuation", "positioning"],
        expected_mac_range=(0.50, 0.70),
        severity="moderate",
        description=(
            "Credit spreads compressed to "
            "historic lows, housing bubble peak"
        ),
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
        description=(
            "BNP Paribas freezes redemptions, "
            "subprime contagion begins"
        ),
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
        description=(
            "Bear Stearns fails, Fed facilitates "
            "JPMorgan acquisition"
        ),
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
        expected_pillars_in_breach=[
            "liquidity", "valuation",
            "positioning", "volatility",
            "contagion",
        ],
        expected_mac_range=(0.10, 0.30),
        severity="extreme",
        description=(
            "Lehman bankruptcy, systemic crisis, "
            "markets freeze globally"
        ),
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
        description=(
            "Intraday 9% S&P 500 decline, "
            "high-frequency trading breakdown"
        ),
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
        description=(
            "Periphery sovereign spreads spike, "
            "TARGET2 imbalances peak, Draghi "
            "'whatever it takes'"
        ),
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
        description=(
            "Fed signals QE tapering, EM capital "
            "flight, 'Fragile Five' under pressure"
        ),
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
        description=(
            "PBOC devalues yuan, triggers global "
            "equity selloff, commodity rout"
        ),
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
        description=(
            "Fed tightening + QT, S&P 500 down "
            "20%, Christmas Eve low, Powell pivots"
        ),
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
        affected_countries=[
            "USA", "GBR", "DEU", "FRA",
            "ITA", "JPN", "CHN", "all G20",
        ],
        expected_pillars_in_breach=[
            "liquidity", "valuation",
            "positioning", "volatility",
            "contagion",
        ],
        expected_mac_range=(0.10, 0.25),
        severity="extreme",
        description=(
            "Global pandemic, fastest bear market "
            "ever, all asset class selloff, "
            "Fed unlimited QE"
        ),
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
        description=(
            "Mini-budget chaos, gilt yields spike, "
            "BoE intervenes, LDI crisis"
        ),
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
        description=(
            "Silicon Valley Bank fails, "
            "Signature Bank fails, "
            "Credit Suisse absorbed"
        ),
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
        expected_pillars_in_breach=[
            "positioning", "volatility",
            "contagion",
        ],
        expected_mac_range=(0.45, 0.60),
        severity="moderate",
        description=(
            "BoJ hikes, yen surges 3% in days, "
            "unwinds global carry trades, "
            "Nikkei -12% single day"
        ),
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


def get_crises_in_range(
    start_date: datetime,
    end_date: datetime,
) -> List[CrisisEvent]:
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
