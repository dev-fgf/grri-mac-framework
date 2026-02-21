"""GRRI historical proxy chain definitions.

Documents each proxy substitution, its academic justification,
correlation estimate with the modern indicator, and coverage period.

Follows the same ``ProxyConfig`` pattern used in
``grri_mac.data.historical_proxies`` for the MAC framework.

Usage
-----
::

    from grri_mac.grri.historical_proxies import GRRI_PROXY_CHAINS
    chain = GRRI_PROXY_CHAINS["political"]["governance"]
    for proxy in chain:
        print(proxy.proxy_series, proxy.start_date, proxy.correlation_estimate)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GRRIProxyConfig:
    """Definition of a single historical proxy for a GRRI indicator."""

    target_indicator: str       # Modern indicator being approximated
    proxy_series: str           # Historical proxy series name
    source: str                 # Academic / data source
    start_date: str             # First year with data (YYYY)
    end_date: Optional[str]     # Last year before modern indicator takes over
    pillar: str                 # GRRI pillar: political / economic / social / environmental
    transformation: str         # How to transform proxy → target scale
    correlation_estimate: float  # Estimated correlation with modern indicator (overlap period)
    coverage_countries: str     # e.g. "G20 + 50 others" or "US only"
    academic_reference: str     # Citation for the proxy rationale
    caveats: str                # Important limitations


# =============================================================================
# Political Pillar Proxy Chains
# =============================================================================

POLITICAL_PROXIES: Dict[str, List[GRRIProxyConfig]] = {
    "governance": [
        GRRIProxyConfig(
            target_indicator="WGI Rule of Law (-2.5 to 2.5)",
            proxy_series="Polity5 polity2 (-10 to +10)",
            source="Center for Systemic Peace, Polity5 Project",
            start_date="1800",
            end_date="1995",
            pillar="political",
            transformation="linear: (polity2 + 10) / 20 → 0-1",
            correlation_estimate=0.82,
            coverage_countries="167 countries",
            academic_reference=(
                "Marshall, M.G. & Gurr, T.R. (2020). Polity5: Political Regime "
                "Characteristics and Transitions, 1800-2018."
            ),
            caveats=(
                "Polity5 measures executive constraints and political competition, "
                "not rule of law per se.  Correlation with WGI is strong for "
                "democracies but weaker for hybrid regimes."
            ),
        ),
        GRRIProxyConfig(
            target_indicator="WGI Rule of Law (-2.5 to 2.5)",
            proxy_series="V-Dem v2x_rule (0-1)",
            source="V-Dem Institute, University of Gothenburg",
            start_date="1789",
            end_date="1995",
            pillar="political",
            transformation="direct (already 0-1)",
            correlation_estimate=0.91,
            coverage_countries="202 countries",
            academic_reference=(
                "Coppedge, M. et al. (2023). V-Dem Codebook v14. "
                "Varieties of Democracy Institute."
            ),
            caveats=(
                "V-Dem scores before ~1900 rely on expert coding of historical "
                "records and should be treated as ordinal rather than cardinal "
                "measures.  Inter-coder reliability is lower for pre-1900 periods."
            ),
        ),
    ],
    "conflict": [
        GRRIProxyConfig(
            target_indicator="UCDP Battle-Related Deaths",
            proxy_series="Correlates of War (COW) war participation",
            source="Correlates of War Project, University of Michigan",
            start_date="1816",
            end_date="1945",
            pillar="political",
            transformation="log-scaled battle deaths → 0-1 intensity",
            correlation_estimate=0.85,
            coverage_countries="All state system members",
            academic_reference=(
                "Sarkees, M.R. & Wayman, F. (2010). Resort to War: 1816-2007. "
                "CQ Press."
            ),
            caveats=(
                "COW dataset covers interstate and civil wars only; sub-state "
                "violence and one-sided killings are excluded.  Battle-death "
                "estimates for pre-1900 conflicts are uncertain."
            ),
        ),
    ],
    "democracy": [
        GRRIProxyConfig(
            target_indicator="WGI Voice & Accountability",
            proxy_series="V-Dem Electoral Democracy Index v2x_polyarchy (0-1)",
            source="V-Dem Institute",
            start_date="1789",
            end_date="1995",
            pillar="political",
            transformation="direct (already 0-1)",
            correlation_estimate=0.93,
            coverage_countries="202 countries",
            academic_reference=(
                "Teorell, J. et al. (2019). Measuring Polyarchy Across the Globe. "
                "Studies in Comparative International Development, 54(1)."
            ),
            caveats=(
                "Expert-coded historical data; conceptual differences between "
                "electoral democracy and voice/accountability."
            ),
        ),
    ],
}


# =============================================================================
# Economic Pillar Proxy Chains
# =============================================================================

ECONOMIC_PROXIES: Dict[str, List[GRRIProxyConfig]] = {
    "gdp_growth": [
        GRRIProxyConfig(
            target_indicator="IMF WEO Real GDP Growth",
            proxy_series="Maddison Project Database GDP per capita (2011 int'l $)",
            source="Groningen Growth and Development Centre (GGDC)",
            start_date="1820",
            end_date="1979",
            pillar="economic",
            transformation="CAGR over 5yr window → normalised 0-1",
            correlation_estimate=0.78,
            coverage_countries="169 countries (2020 release)",
            academic_reference=(
                "Bolt, J. & van Zanden, J.L. (2020). Maddison style estimates "
                "of the evolution of the world economy.  A new 2020 update.  "
                "Maddison Project Working Paper WP-15."
            ),
            caveats=(
                "Pre-1870 estimates are benchmarked and interpolated; "
                "annual growth rates should be treated as approximate.  "
                "PPP adjustments for early periods are subject to "
                "index-number problems."
            ),
        ),
        GRRIProxyConfig(
            target_indicator="IMF WEO Real GDP Growth",
            proxy_series="MeasuringWorth US GDP (nominal, 1790+)",
            source="MeasuringWorth.com / Officer & Williamson",
            start_date="1790",
            end_date="1819",
            pillar="economic",
            transformation="deflate by CPI, compute growth → normalise 0-1",
            correlation_estimate=0.70,
            coverage_countries="US only",
            academic_reference=(
                "Johnston, L. & Williamson, S.H. (2023). What Was the U.S. GDP Then? "
                "MeasuringWorth."
            ),
            caveats="US only.  Nominal GDP needs CPI deflation; pre-1870 CPI is approximate.",
        ),
    ],
    "economic_complexity": [
        GRRIProxyConfig(
            target_indicator="Harvard Growth Lab ECI",
            proxy_series="Log GDP per capita (Maddison) as sophistication proxy",
            source="Own construction from Maddison Project",
            start_date="1820",
            end_date="1994",
            pillar="economic",
            transformation="log(gdppc) rescaled: (log(gdppc) - 5) / 6 → 0-1",
            correlation_estimate=0.72,
            coverage_countries="169 countries",
            academic_reference=(
                "Hidalgo, C.A. & Hausmann, R. (2009). The building blocks of "
                "economic complexity.  PNAS 106(26).  — Justifies GDP/capita "
                "as correlated with but not identical to export sophistication."
            ),
            caveats=(
                "GDP per capita correlates with economic complexity but does not "
                "capture export structure directly.  Resource-rich economies may "
                "have high GDP but low complexity."
            ),
        ),
    ],
    "central_bank_independence": [
        GRRIProxyConfig(
            target_indicator="Garriga CBI Index (0-1)",
            proxy_series="Garriga CBI Dataset",
            source="Garriga, A.C., George Washington University",
            start_date="1970",
            end_date="2017",
            pillar="economic",
            transformation="direct (already 0-1)",
            correlation_estimate=1.0,
            coverage_countries="182 countries",
            academic_reference=(
                "Garriga, A.C. (2016). Central Bank Independence in the World: "
                "A New Dataset.  International Interactions, 42(5)."
            ),
            caveats="Dataset ends 2017; post-2017 values must be extrapolated or updated.",
        ),
        GRRIProxyConfig(
            target_indicator="CB Independence (pre-1970)",
            proxy_series="Heuristic: gold standard constraints + CB existence",
            source="Own construction based on Friedman & Schwartz (1963)",
            start_date="1800",
            end_date="1969",
            pillar="economic",
            transformation="expert judgement → 0-1 ordinal scale",
            correlation_estimate=0.50,
            coverage_countries="Major economies only (US, UK, FR, DE)",
            academic_reference=(
                "Friedman, M. & Schwartz, A.J. (1963). A Monetary History of "
                "the United States, 1867-1960.  Princeton University Press."
            ),
            caveats=(
                "Pre-1970 CBI is a rough heuristic, not a measured index.  "
                "The gold standard created de-facto constraint on policy that "
                "is qualitatively different from modern CBI legislation."
            ),
        ),
    ],
    "crisis_history": [
        GRRIProxyConfig(
            target_indicator="Economic crisis vulnerability",
            proxy_series="Reinhart-Rogoff crisis dummy panel",
            source="Reinhart, C.M. & Rogoff, K.S.",
            start_date="1800",
            end_date="2020",
            pillar="economic",
            transformation="count of crisis types in 5yr window → 0-1",
            correlation_estimate=0.85,
            coverage_countries="70 countries",
            academic_reference=(
                "Reinhart, C.M. & Rogoff, K.S. (2009). This Time Is Different: "
                "Eight Centuries of Financial Folly.  Princeton University Press."
            ),
            caveats=(
                "Binary indicators (crisis / no crisis) lose intensity information.  "
                "Some crisis dates are debated in the literature."
            ),
        ),
    ],
    "sanctions": [
        GRRIProxyConfig(
            target_indicator="Sanctions exposure",
            proxy_series="Harvard GSDB sanctions episodes",
            source="Harvard Dataverse / Felbermayr et al.",
            start_date="1950",
            end_date="2022",
            pillar="economic",
            transformation="count of active sanctions → ordinal severity",
            correlation_estimate=0.90,
            coverage_countries="Global",
            academic_reference=(
                "Felbermayr, G. et al. (2020). The Global Sanctions Data Base. "
                "European Economic Review, 131."
            ),
            caveats="Coverage begins 1950; pre-WW2 sanctions are not coded.",
        ),
    ],
}


# =============================================================================
# Social Pillar Proxy Chains
# =============================================================================

SOCIAL_PROXIES: Dict[str, List[GRRIProxyConfig]] = {
    "hdi": [
        GRRIProxyConfig(
            target_indicator="UNDP Human Development Index (0-1)",
            proxy_series="Crafts-style HDI from GDP/capita + suffrage",
            source="Own construction from Maddison + V-Dem",
            start_date="1820",
            end_date="1989",
            pillar="social",
            transformation="average of normalised GDP/capita and V-Dem suffrage",
            correlation_estimate=0.75,
            coverage_countries="G20 countries with Maddison + V-Dem overlap",
            academic_reference=(
                "Crafts, N.F.R. (1997). The Human Development Index and "
                "Changes in Standards of Living.  European Review of Economic "
                "History, 1(3). — Proposes backward-extending HDI methodology."
            ),
            caveats=(
                "Missing life-expectancy dimension; uses suffrage as "
                "education/empowerment proxy.  Pre-1870 data very sparse."
            ),
        ),
    ],
    "suffrage": [
        GRRIProxyConfig(
            target_indicator="Social capital / political participation",
            proxy_series="V-Dem v2x_suffr (0-1)",
            source="V-Dem Institute",
            start_date="1789",
            end_date=None,
            pillar="social",
            transformation="direct (already 0-1)",
            correlation_estimate=0.95,
            coverage_countries="202 countries",
            academic_reference=(
                "Coppedge, M. et al. (2023). V-Dem Codebook v14."
            ),
            caveats="Measures legal suffrage, not effective participation.",
        ),
    ],
    "unemployment": [
        GRRIProxyConfig(
            target_indicator="ILO Unemployment Rate",
            proxy_series="Mitchell's International Historical Statistics",
            source="Mitchell, B.R.",
            start_date="1919",
            end_date="1959",
            pillar="social",
            transformation="direct (%, inverted for resilience score)",
            correlation_estimate=0.80,
            coverage_countries="Major economies",
            academic_reference=(
                "Mitchell, B.R. (2013). International Historical Statistics. "
                "Palgrave Macmillan.  7th edition."
            ),
            caveats=(
                "Pre-WW2 unemployment statistics are often based on trade-union "
                "reports or administrative data, not household surveys.  "
                "Definitions vary across countries and periods."
            ),
        ),
    ],
    "civil_liberties": [
        GRRIProxyConfig(
            target_indicator="Civil liberties / social rights",
            proxy_series="V-Dem v2x_civlib (0-1)",
            source="V-Dem Institute",
            start_date="1789",
            end_date=None,
            pillar="social",
            transformation="direct (already 0-1)",
            correlation_estimate=0.90,
            coverage_countries="202 countries",
            academic_reference="Coppedge, M. et al. (2023). V-Dem Codebook v14.",
            caveats="Expert-coded; pre-1900 reliability is lower.",
        ),
    ],
}


# =============================================================================
# Environmental Pillar Proxy Chains
# =============================================================================

ENVIRONMENTAL_PROXIES: Dict[str, List[GRRIProxyConfig]] = {
    "disaster_risk": [
        GRRIProxyConfig(
            target_indicator="INFORM Climate Risk Index",
            proxy_series="EM-DAT disaster events (deaths + affected)",
            source="Centre for Research on the Epidemiology of Disasters (CRED)",
            start_date="1900",
            end_date="2011",
            pillar="environmental",
            transformation="log-scaled 5yr death total → 0-1",
            correlation_estimate=0.65,
            coverage_countries="Global",
            academic_reference=(
                "Guha-Sapir, D. et al. (2023). EM-DAT: The International "
                "Disaster Database.  UCLouvain, Brussels."
            ),
            caveats=(
                "Pre-1960 disaster reporting is incomplete, especially for "
                "developing countries.  Under-reporting biases severity downward "
                "for historical periods."
            ),
        ),
    ],
    "climate_trend": [
        GRRIProxyConfig(
            target_indicator="Climate change exposure",
            proxy_series="HadCRUT5 temperature anomaly (°C vs 1961-1990)",
            source="UK Met Office / Climatic Research Unit",
            start_date="1850",
            end_date=None,
            pillar="environmental",
            transformation="30yr rate of change → 0-1",
            correlation_estimate=0.60,
            coverage_countries="Global mean (not country-specific)",
            academic_reference=(
                "Morice, C.P. et al. (2021). An Updated Assessment of "
                "Near-Surface Temperature Change From 1850: The HadCRUT5 "
                "Data Set.  JGR Atmospheres, 126(3)."
            ),
            caveats=(
                "Global mean temperature, not country-specific.  Relationship "
                "between temperature trend and country-level climate risk is "
                "indirect.  Mainly captures macro trend."
            ),
        ),
    ],
}


# =============================================================================
# Aggregated Dictionary
# =============================================================================

GRRI_PROXY_CHAINS: Dict[str, Dict[str, List[GRRIProxyConfig]]] = {
    "political": POLITICAL_PROXIES,
    "economic": ECONOMIC_PROXIES,
    "social": SOCIAL_PROXIES,
    "environmental": ENVIRONMENTAL_PROXIES,
}


def get_proxy_coverage_table() -> str:
    """
    Generate a human-readable coverage table for all proxy chains.

    Returns:
        Formatted string summarising proxy coverage by pillar.
    """
    lines = [
        "GRRI Historical Proxy Coverage Summary",
        "=" * 60,
        "",
    ]

    for pillar, indicators in GRRI_PROXY_CHAINS.items():
        lines.append(f"  {pillar.upper()} PILLAR")
        lines.append(f"  {'-' * 40}")
        for indicator, chain in indicators.items():
            for proxy in chain:
                end = proxy.end_date or "present"
                lines.append(
                    f"    {indicator:25s} → {proxy.proxy_series[:40]:40s} "
                    f"[{proxy.start_date}-{end}] r≈{proxy.correlation_estimate:.2f}"
                )
        lines.append("")

    return "\n".join(lines)


def get_all_required_files() -> Dict[str, str]:
    """
    List all data files needed for full historical GRRI coverage.

    Returns:
        Dict of {relative_path: description}.
    """
    return {
        "data/historical/grri/polity5/p5v2018.csv": (
            "Polity5 regime scores. Download from "
            "https://www.systemicpeace.org/inscrdata.html"
        ),
        "data/historical/grri/vdem/vdem_core.csv": (
            "V-Dem core dataset (filtered to G20 + key indicators). "
            "Download from https://v-dem.net/data/"
        ),
        "data/historical/grri/cow/wars.csv": (
            "Correlates of War war dataset. "
            "Download from https://correlatesofwar.org/data-sets/"
        ),
        "data/historical/grri/maddison/mpd2020.csv": (
            "Maddison Project Database 2020 GDP per capita. "
            "Download from https://www.rug.nl/ggdc/historicaldevelopment/maddison/"
        ),
        "data/historical/grri/reinhart_rogoff/crises.csv": (
            "Reinhart-Rogoff crisis indicator panel. "
            "Download from https://www.carmenreinhart.com/data"
        ),
        "data/historical/grri/emdat/emdat_public.csv": (
            "EM-DAT public disaster database. "
            "Register and download from https://www.emdat.be/"
        ),
        "data/historical/grri/hadcrut/hadcrut5_annual.csv": (
            "HadCRUT5 global mean temperature anomaly (annual). "
            "Download from https://www.metoffice.gov.uk/hadobs/hadcrut5/"
        ),
        "data/historical/grri/garriga/cbi_index.csv": (
            "Garriga Central Bank Independence index. "
            "Download from https://sites.google.com/site/carogarriga/cbi-data-1"
        ),
        "data/historical/grri/gsdb/sanctions.csv": (
            "Harvard Global Sanctions Database. "
            "Download from https://doi.org/10.7910/DVN/SVR5W7"
        ),
        "data/historical/grri/ucdp/ucdp_brd.csv": (
            "UCDP battle-related deaths. "
            "Download from https://ucdp.uu.se/downloads/"
        ),
        "data/historical/grri/unemployment/usa.csv": (
            "US historical unemployment rate (Mitchell / BLS). "
            "Manual compilation from BLS + Mitchell's historical statistics."
        ),
    }
