"""Historical data sources for extending GRRI coverage back to 1870+.

Mirrors the approach used in ``grri_mac.data.historical_sources`` for the MAC
pillars but targets the four GRRI resilience pillars:

    Political  — Polity5 (1800+), V-Dem (1789+), COW (1816+)
    Economic   — Maddison Project (1820+), MeasuringWorth (1790+, US),
                 Reinhart-Rogoff crises database (1800+), Shiller CPI (1871+)
    Social     — Historical HDI proxies (1870+), V-Dem suffrage (1789+),
                 ILO unemployment (1919+), Shiller CPI for real-wages
    Environmental — EM-DAT natural disasters (1900+),
                    HadCRUT temperature anomaly (1850+)

Data files are expected in ``data/historical/grri/`` sub-directories.
Run ``download_grri_historical_data.py`` to fetch publicly available datasets.

Coverage Summary
================
+----------------+---------------+-----------------+
| Pillar         | Modern Start  | With Proxies    |
+================+===============+=================+
| Political      | 1996 (WGI)    | 1800 (Polity5)  |
+----------------+---------------+-----------------+
| Economic       | 1980 (IMF)    | 1820 (Maddison) |
+----------------+---------------+-----------------+
| Social         | 1990 (HDI)    | 1870 (proxies)  |
+----------------+---------------+-----------------+
| Environmental  | 2012 (INFORM) | 1900 (EM-DAT)   |
+----------------+---------------+-----------------+
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base directory for GRRI historical data files
GRRI_HISTORICAL_DIR = (
    Path(__file__).parent.parent.parent / "data" / "historical" / "grri"
)

# Also re-use data already fetched for MAC
MAC_HISTORICAL_DIR = Path(__file__).parent.parent.parent / "data" / "historical"


# =============================================================================
# Polity5 Project — Centre for Systemic Peace
# Composite indicator of regime type: −10 (full autocracy) to +10 (full democracy)
# URL: https://www.systemicpeace.org/inscrdata.html
# Coverage: 1800–2018 for 167 countries
# =============================================================================

POLITY5_COLUMNS = {
    "country": "Country name",
    "ccode": "Numeric country code",
    "year": "Observation year",
    "polity2": "Revised combined polity score (-10 to +10)",
    "democ": "Institutionalised democracy score (0-10)",
    "autoc": "Institutionalised autocracy score (0-10)",
    "xconst": "Executive constraints (1-7)",
    "polcomp": "Political competition (1-10)",
}


def load_polity5(country_code: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Load Polity5 regime scores.

    Expected file: data/historical/grri/polity5/p5v2018.csv
    (or the Excel version p5v2018.xls from systemicpeace.org)

    The Polity2 variable is the standard composite:
        polity2 = democ − autoc  (range −10 to +10)

    Args:
        country_code: ISO-3 or Polity numeric code to filter. None = all.

    Returns:
        DataFrame indexed by (country, year) with polity scores.
    """
    polity_dir = GRRI_HISTORICAL_DIR / "polity5"
    csv_path = polity_dir / "p5v2018.csv"
    xls_path = polity_dir / "p5v2018.xls"

    if csv_path.exists():
        filepath = csv_path
    elif xls_path.exists():
        filepath = xls_path
    else:
        logger.warning(f"Polity5 data not found in {polity_dir}")
        return None

    try:
        if filepath.suffix == ".xls":
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath, encoding="latin-1")

        # Standardise column names
        df.columns = [c.strip().lower() for c in df.columns]

        # Filter to numeric polity2 (drop special codes: -66, -77, -88)
        if "polity2" in df.columns:
            df = df[~df["polity2"].isin([-66, -77, -88])]

        if country_code is not None:
            # Try matching on scode (3-letter) or country name
            mask = pd.Series([False] * len(df))
            if "scode" in df.columns:
                mask |= df["scode"].str.upper() == country_code.upper()
            if "country" in df.columns:
                mask |= df["country"].str.upper() == country_code.upper()
            if "ccode" in df.columns and country_code.isdigit():
                mask |= df["ccode"] == int(country_code)
            df = df[mask]

        logger.info(f"Loaded Polity5: {len(df)} obs, "
                     f"{df['year'].min()}-{df['year'].max()}")
        return df

    except Exception as e:
        logger.error(f"Error loading Polity5: {e}")
        return None


def get_polity2_series(country_code: str) -> Optional[pd.Series]:
    """Get annual Polity2 score for a country (−10 to +10)."""
    df = load_polity5(country_code)
    if df is not None and "polity2" in df.columns and "year" in df.columns:
        dates = [datetime(int(y), 7, 1) for y in df["year"]]
        series = pd.Series(df["polity2"].values, index=dates, dtype=float)
        return series.dropna().sort_index()
    return None


# =============================================================================
# V-Dem (Varieties of Democracy) — University of Gothenburg
# Multiple democracy indices on continuous 0–1 scales from 1789
# URL: https://v-dem.net/ (or Our World in Data mirrors)
# Coverage: 1789–present, 202 countries
# =============================================================================

VDEM_INDICATORS = {
    "v2x_polyarchy": "Electoral democracy index (0-1)",
    "v2x_libdem": "Liberal democracy index (0-1)",
    "v2x_partipdem": "Participatory democracy index (0-1)",
    "v2x_civlib": "Civil liberties index (0-1)",
    "v2x_freexp": "Freedom of expression index (0-1)",
    "v2x_suffr": "Share of population with suffrage (0-1)",
    "v2cseeorgs": "CSO entry and exit (freedom of association)",
    "v2x_rule": "Rule of law index (0-1)",
}


def load_vdem(
    indicators: Optional[List[str]] = None,
    country_code: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Load V-Dem democracy indicators.

    Expected file: data/historical/grri/vdem/vdem_core.csv
    (Subset of V-Dem Country-Year Core dataset, pre-filtered to
    G20 countries and key indicators to keep file size manageable.)

    A full V-Dem CSV is ~100 MB.  For production use, download via
    ``GRRIDataAggregator`` and cache locally.

    Args:
        indicators: List of V-Dem variable codes to load.
                    None = all available.
        country_code: ISO-3 code to filter.  None = all countries.

    Returns:
        DataFrame with MultiIndex (country, year) and indicator columns.
    """
    vdem_dir = GRRI_HISTORICAL_DIR / "vdem"
    filepath = vdem_dir / "vdem_core.csv"

    if not filepath.exists():
        logger.warning(f"V-Dem data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, low_memory=False)
        df.columns = [c.strip().lower() for c in df.columns]

        if country_code is not None:
            for col in ("country_text_id", "country_id", "country_name"):
                if col in df.columns:
                    mask = df[col].astype(str).str.upper() == country_code.upper()
                    if mask.any():
                        df = df[mask]
                        break

        if indicators:
            keep = [c for c in indicators if c in df.columns]
            meta = [c for c in ("country_text_id", "country_name", "year")
                    if c in df.columns]
            df = df[meta + keep]

        logger.info(f"Loaded V-Dem: {len(df)} obs")
        return df

    except Exception as e:
        logger.error(f"Error loading V-Dem: {e}")
        return None


def get_vdem_series(
    country_code: str,
    indicator: str = "v2x_polyarchy",
) -> Optional[pd.Series]:
    """Get annual V-Dem score for a country on a specific indicator."""
    df = load_vdem(indicators=[indicator], country_code=country_code)
    if df is not None and indicator in df.columns and "year" in df.columns:
        dates = [datetime(int(y), 7, 1) for y in df["year"]]
        series = pd.Series(df[indicator].values, index=dates, dtype=float)
        return series.dropna().sort_index()
    return None


# =============================================================================
# Correlates of War (COW) — Interstate/Civil War Dataset
# War participation as a political-risk indicator
# URL: https://correlatesofwar.org/data-sets/
# Coverage: 1816–present
# =============================================================================

def load_cow_wars() -> Optional[pd.DataFrame]:
    """
    Load Correlates of War interstate/civil war dataset.

    Expected file: data/historical/grri/cow/wars.csv
    Key columns: warnum, warname, year, state_participant, side, batdeath

    Returns:
        DataFrame with war participation records.
    """
    cow_dir = GRRI_HISTORICAL_DIR / "cow"
    filepath = cow_dir / "wars.csv"

    if not filepath.exists():
        logger.warning(f"COW wars data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded COW wars: {len(df)} records")
        return df
    except Exception as e:
        logger.error(f"Error loading COW data: {e}")
        return None


def get_conflict_intensity(country_code: str, year: int) -> Optional[float]:
    """
    Get a 0–1 conflict intensity score from COW data.

    0.0 = no active participation in war
    0.5 = minor conflict / low battle-deaths
    1.0 = major interstate war participant

    Uses logarithmic scaling of battle deaths relative to population.
    """
    df = load_cow_wars()
    if df is None:
        return None

    # Filter to country and year
    mask = pd.Series([False] * len(df))
    for col in ("ccode", "state_participant", "statea"):
        if col in df.columns:
            mask |= df[col].astype(str).str.upper() == country_code.upper()

    year_mask = pd.Series([False] * len(df))
    for col in ("year", "startyear1"):
        if col in df.columns:
            year_mask |= df[col] == year
    # Also capture multi-year wars
    if "startyear1" in df.columns and "endyear1" in df.columns:
        year_mask |= (df["startyear1"] <= year) & (df["endyear1"] >= year)

    filtered = df[mask & year_mask]
    if filtered.empty:
        return 0.0

    # Log-scale battle deaths for intensity
    if "batdeath" in filtered.columns:
        max_deaths = filtered["batdeath"].max()
        if pd.notna(max_deaths) and max_deaths > 0:
            return min(1.0, np.log10(max_deaths + 1) / 6.0)  # 1M deaths → 1.0

    return 0.3  # Default: active participation but unknown intensity


# =============================================================================
# Maddison Project — Historical GDP Per Capita
# University of Groningen / GGDC
# URL: https://www.rug.nl/ggdc/historicaldevelopment/maddison/
# Coverage: 1820–present, 169 countries (2020 release)
# =============================================================================

def load_maddison_gdp() -> Optional[pd.DataFrame]:
    """
    Load Maddison Project Database GDP per capita.

    Expected file: data/historical/grri/maddison/mpd2020.csv
    (Exported from the Maddison Project Database 2020 Excel workbook)

    Key columns: country, countrycode, year, gdppc (2011 int'l $),
                 pop (thousands)

    Returns:
        DataFrame with country-year GDP per capita and population.
    """
    maddison_dir = GRRI_HISTORICAL_DIR / "maddison"

    for fname in ("mpd2020.csv", "mpd2020.xlsx"):
        filepath = maddison_dir / fname
        if filepath.exists():
            break
    else:
        logger.warning(f"Maddison data not found in {maddison_dir}")
        return None

    try:
        if filepath.suffix == ".xlsx":
            df = pd.read_excel(filepath, sheet_name="Full data")
        else:
            df = pd.read_csv(filepath)

        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded Maddison: {len(df)} obs, "
                     f"{df['year'].min()}-{df['year'].max()}")
        return df
    except Exception as e:
        logger.error(f"Error loading Maddison data: {e}")
        return None


def get_maddison_gdppc(country_code: str) -> Optional[pd.Series]:
    """Get annual GDP per capita series for a country (2011 int'l $)."""
    df = load_maddison_gdp()
    if df is None:
        return None

    mask = pd.Series([False] * len(df))
    for col in ("countrycode", "country"):
        if col in df.columns:
            mask |= df[col].astype(str).str.upper() == country_code.upper()

    filtered = df[mask]
    gdp_col = next((c for c in ("gdppc", "cgdppc", "rgdpnapc") if c in filtered.columns), None)
    if gdp_col is None or filtered.empty:
        return None

    dates = [datetime(int(y), 7, 1) for y in filtered["year"]]
    series = pd.Series(filtered[gdp_col].values, index=dates, dtype=float)
    return series.dropna().sort_index()


# =============================================================================
# Reinhart-Rogoff Crisis Database
# Banking crises, currency crises, sovereign default, inflation crises
# Source: "This Time Is Different" (2009), updated datasets
# URL: https://www.carmenreinhart.com/data
# Coverage: 1800–present, 70 countries
# =============================================================================

REINHART_ROGOFF_CRISIS_TYPES = {
    "banking": "Systemic banking crisis (0/1)",
    "currency": "Currency crisis — 15%+ depreciation (0/1)",
    "sovereign_external": "External sovereign default (0/1)",
    "sovereign_domestic": "Domestic sovereign default (0/1)",
    "inflation": "Inflation crisis — >20% annual CPI (0/1)",
    "stock_market": "Stock market crash — 25%+ decline (0/1)",
}


def load_reinhart_rogoff() -> Optional[pd.DataFrame]:
    """
    Load Reinhart-Rogoff crisis indicator panel.

    Expected file: data/historical/grri/reinhart_rogoff/crises.csv
    Format: CSV with columns country, year, banking, currency,
            sovereign_external, sovereign_domestic, inflation, stock_market

    Returns:
        DataFrame with country-year crisis indicators (0/1 dummies).
    """
    rr_dir = GRRI_HISTORICAL_DIR / "reinhart_rogoff"
    filepath = rr_dir / "crises.csv"

    if not filepath.exists():
        logger.warning(f"Reinhart-Rogoff data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded Reinhart-Rogoff: {len(df)} obs")
        return df
    except Exception as e:
        logger.error(f"Error loading Reinhart-Rogoff: {e}")
        return None


def get_crisis_count(country_code: str, year: int, window: int = 5) -> int:
    """
    Count number of active crises for a country in 'year' ± 'window'.

    Useful as economic fragility indicator: countries in the midst of
    multiple overlapping crises (banking + currency + default) have
    much lower resilience.

    Returns:
        Total crisis-type-years in the window. 0 = no crises.
    """
    df = load_reinhart_rogoff()
    if df is None:
        return 0

    mask = pd.Series([False] * len(df))
    for col in ("country", "countrycode"):
        if col in df.columns:
            mask |= df[col].astype(str).str.upper() == country_code.upper()

    if "year" in df.columns:
        mask &= (df["year"] >= year - window) & (df["year"] <= year + window)

    filtered = df[mask]
    if filtered.empty:
        return 0

    crisis_cols = [c for c in REINHART_ROGOFF_CRISIS_TYPES if c in filtered.columns]
    return int(filtered[crisis_cols].sum().sum())


# =============================================================================
# EM-DAT International Disaster Database — CRED, UCLouvain
# Natural and technological disasters, 1900–present
# URL: https://www.emdat.be/
# Coverage: 1900–present, global
# =============================================================================

def load_emdat() -> Optional[pd.DataFrame]:
    """
    Load EM-DAT disaster records.

    Expected file: data/historical/grri/emdat/emdat_public.csv
    Key columns: Year, ISO, Disaster_Type, Total_Deaths, Total_Affected,
                 Total_Damages_USD

    Returns:
        DataFrame of disaster events.
    """
    emdat_dir = GRRI_HISTORICAL_DIR / "emdat"
    filepath = emdat_dir / "emdat_public.csv"

    if not filepath.exists():
        logger.warning(f"EM-DAT data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, low_memory=False)
        df.columns = [c.strip().lower().replace(" ", "_").replace("'", "") for c in df.columns]
        logger.info(f"Loaded EM-DAT: {len(df)} disasters")
        return df
    except Exception as e:
        logger.error(f"Error loading EM-DAT: {e}")
        return None


def get_disaster_severity(
    country_code: str,
    year: int,
    window: int = 5,
) -> Optional[float]:
    """
    Compute normalised disaster severity for a country over a window.

    Uses log-scaled total deaths to produce 0–1 severity index.
    Window is used because disaster impacts persist.

    Returns:
        0.0 (no/minor disasters) to 1.0 (catastrophic).
    """
    df = load_emdat()
    if df is None:
        return None

    mask = pd.Series([False] * len(df))
    for col in ("iso", "country"):
        if col in df.columns:
            mask |= df[col].astype(str).str.upper() == country_code.upper()

    year_col = next((c for c in ("year", "start_year") if c in df.columns), None)
    if year_col:
        mask &= (df[year_col] >= year - window) & (df[year_col] <= year)

    filtered = df[mask]
    if filtered.empty:
        return 0.0

    death_col = next(
        (c for c in ("total_deaths", "deaths", "no_killed") if c in filtered.columns),
        None,
    )
    if death_col is None:
        return min(1.0, len(filtered) / 50.0)  # Fallback: event count

    total_deaths = pd.to_numeric(filtered[death_col], errors="coerce").sum()
    if pd.isna(total_deaths) or total_deaths <= 0:
        return min(1.0, len(filtered) / 50.0)

    # Log-scale: 10 deaths → 0.17, 1000 → 0.5, 100000 → 0.83
    return min(1.0, np.log10(total_deaths + 1) / 6.0)


# =============================================================================
# HadCRUT Temperature Anomaly — UK Met Office / CRU
# Global mean surface temperature anomaly (°C vs 1961-1990 baseline)
# URL: https://www.metoffice.gov.uk/hadobs/hadcrut5/
# Coverage: 1850–present (annual / monthly)
# =============================================================================

def load_hadcrut() -> Optional[pd.Series]:
    """
    Load HadCRUT5 global mean temperature anomaly (annual).

    Expected file: data/historical/grri/hadcrut/hadcrut5_annual.csv
    Format: CSV with columns 'year' and 'anomaly' (°C)

    Returns:
        Series of annual temperature anomalies.
    """
    hadcrut_dir = GRRI_HISTORICAL_DIR / "hadcrut"
    filepath = hadcrut_dir / "hadcrut5_annual.csv"

    if not filepath.exists():
        logger.warning(f"HadCRUT data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip().lower() for c in df.columns]

        year_col = next((c for c in ("year", "time") if c in df.columns), None)
        anom_col = next(
            (c for c in ("anomaly", "anomaly_(deg_c)", "median") if c in df.columns),
            None,
        )
        if year_col is None or anom_col is None:
            logger.warning("HadCRUT CSV missing expected columns")
            return None

        dates = [datetime(int(y), 7, 1) for y in df[year_col]]
        series = pd.Series(df[anom_col].values, index=dates, dtype=float)
        series = series.dropna().sort_index()
        logger.info(f"Loaded HadCRUT: {len(series)} years, "
                     f"{series.index[0].year}-{series.index[-1].year}")
        return series
    except Exception as e:
        logger.error(f"Error loading HadCRUT: {e}")
        return None


# =============================================================================
# ILO / Historical Unemployment
# Mitchell's "International Historical Statistics" has pre-WW2 data
# URL: https://ilostat.ilo.org/ (modern), Mitchell (historical)
# Coverage: ~1919+ for major economies, spotty before that
# =============================================================================

def load_historical_unemployment(country_code: str) -> Optional[pd.Series]:
    """
    Load historical unemployment rate for a country.

    Expected file: data/historical/grri/unemployment/{country_code}.csv
    Format: CSV with columns 'year' and 'unemployment_rate' (%)

    For pre-1960 data, uses Mitchell's *International Historical Statistics*
    or national statistical office archives.

    Returns:
        Annual unemployment rate series.
    """
    unemp_dir = GRRI_HISTORICAL_DIR / "unemployment"
    filepath = unemp_dir / f"{country_code.lower()}.csv"

    if not filepath.exists():
        logger.warning(f"Unemployment data not found for {country_code}")
        return None

    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip().lower() for c in df.columns]

        rate_col = next(
            (c for c in ("unemployment_rate", "rate", "unemp") if c in df.columns),
            None,
        )
        if rate_col is None:
            return None

        year_col = "year" if "year" in df.columns else df.columns[0]
        dates = [datetime(int(y), 7, 1) for y in df[year_col]]
        series = pd.Series(df[rate_col].values, index=dates, dtype=float)
        return series.dropna().sort_index()
    except Exception as e:
        logger.error(f"Error loading unemployment for {country_code}: {e}")
        return None


# =============================================================================
# Garriga Central Bank Independence Index
# URL: https://sites.google.com/site/carogarriga/cbi-data-1
# Coverage: 1970–2017, 182 countries
# =============================================================================

def load_cbi_index() -> Optional[pd.DataFrame]:
    """
    Load Garriga Central Bank Independence index.

    Expected file: data/historical/grri/garriga/cbi_index.csv
    Format: CSV with columns 'country', 'year', 'cbi' (0-1)

    Returns:
        DataFrame with country-year CBI scores.
    """
    garriga_dir = GRRI_HISTORICAL_DIR / "garriga"
    filepath = garriga_dir / "cbi_index.csv"

    if not filepath.exists():
        logger.warning(f"Garriga CBI data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded Garriga CBI: {len(df)} obs")
        return df
    except Exception as e:
        logger.error(f"Error loading Garriga CBI: {e}")
        return None


def get_cbi_score(country_code: str, year: int) -> Optional[float]:
    """Get CBI score for a country and year (0-1)."""
    df = load_cbi_index()
    if df is None:
        return None

    mask = pd.Series([False] * len(df))
    for col in ("country", "countrycode", "ccode"):
        if col in df.columns:
            mask |= df[col].astype(str).str.upper() == country_code.upper()

    if "year" in df.columns:
        mask &= df["year"] == year

    filtered = df[mask]
    if filtered.empty:
        # Try nearest year within 3 years
        for col in ("country", "countrycode", "ccode"):
            if col in df.columns:
                country_mask = df[col].astype(str).str.upper() == country_code.upper()
                if country_mask.any():
                    country_data = df[country_mask].copy()
                    country_data["year_diff"] = abs(country_data["year"] - year)
                    closest = country_data.loc[country_data["year_diff"].idxmin()]
                    if closest["year_diff"] <= 3 and "cbi" in country_data.columns:
                        return float(closest["cbi"])
                    break
        return None

    cbi_col = next((c for c in ("cbi", "lvaw", "lvau") if c in filtered.columns), None)
    if cbi_col:
        return float(filtered[cbi_col].iloc[0])
    return None


# =============================================================================
# Harvard Global Sanctions Database (GSDB)
# URL: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/SVR5W7
# Coverage: 1950–2022
# =============================================================================

def load_sanctions_database() -> Optional[pd.DataFrame]:
    """
    Load GSDB sanctions episodes.

    Expected file: data/historical/grri/gsdb/sanctions.csv
    Key columns: target_country, sender_country, start_year, end_year,
                 sanction_type, objective

    Returns:
        DataFrame of sanctions episodes.
    """
    gsdb_dir = GRRI_HISTORICAL_DIR / "gsdb"
    filepath = gsdb_dir / "sanctions.csv"

    if not filepath.exists():
        logger.warning(f"GSDB sanctions data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, low_memory=False)
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded GSDB: {len(df)} sanctions episodes")
        return df
    except Exception as e:
        logger.error(f"Error loading GSDB: {e}")
        return None


def get_sanctions_count(
    country_code: str, year: int, role: str = "target"
) -> int:
    """
    Count active sanctions affecting a country in a given year.

    Args:
        country_code: ISO-3 country code.
        year: Year to check.
        role: 'target' (sanctions against) or 'sender' (sanctions imposed by).

    Returns:
        Number of active sanctions episodes.
    """
    df = load_sanctions_database()
    if df is None:
        return 0

    col = "target_country" if role == "target" else "sender_country"
    if col not in df.columns:
        return 0

    mask = df[col].astype(str).str.upper() == country_code.upper()
    if "start_year" in df.columns and "end_year" in df.columns:
        mask &= (df["start_year"] <= year) & (
            df["end_year"].fillna(year + 1) >= year
        )
    elif "year" in df.columns:
        mask &= df["year"] == year

    return int(mask.sum())


# =============================================================================
# UCDP (Uppsala Conflict Data Programme)
# URL: https://ucdp.uu.se/downloads/
# Coverage: 1946–present
# =============================================================================

def load_ucdp_conflicts() -> Optional[pd.DataFrame]:
    """
    Load UCDP battle-related deaths dataset.

    Expected file: data/historical/grri/ucdp/ucdp_brd.csv
    Key columns: year, location, side_a, best (battle-deaths best estimate)

    Returns:
        DataFrame of conflict-year records.
    """
    ucdp_dir = GRRI_HISTORICAL_DIR / "ucdp"
    filepath = ucdp_dir / "ucdp_brd.csv"

    if not filepath.exists():
        logger.warning(f"UCDP data not found at {filepath}")
        return None

    try:
        df = pd.read_csv(filepath, low_memory=False)
        df.columns = [c.strip().lower() for c in df.columns]
        logger.info(f"Loaded UCDP: {len(df)} records")
        return df
    except Exception as e:
        logger.error(f"Error loading UCDP data: {e}")
        return None


# =============================================================================
# Composite Historical GRRI Provider
# Unified interface mirroring HistoricalDataProvider from
# grri_mac.data.historical_sources
# =============================================================================

class GRRIHistoricalProvider:
    """
    Unified provider for historical GRRI pillar data.

    Loads and caches data from Polity5, V-Dem, COW, Maddison,
    Reinhart-Rogoff, EM-DAT, HadCRUT, ILO, Garriga, GSDB, and
    UCDP sources.

    Provides proxy chain resolution for each GRRI pillar:

    **Political Pillar**
        Primary: WGI (1996+) → Polity5 (1800+) → V-Dem polyarchy (1789+)
        Conflict: UCDP (1946+) → COW (1816+)

    **Economic Pillar**
        GDP: IMF WEO (1980+) → Maddison (1820+) → MeasuringWorth US (1790+)
        CBI: Garriga (1970-2017)
        Crises: Reinhart-Rogoff (1800+)
        CPI: FRED (1947+) → Shiller CPI (1871+)

    **Social Pillar**
        HDI: UNDP (1990+) → historical proxy from Maddison GDP + V-Dem suffrage
        Suffrage: V-Dem (1789+)
        Unemployment: ILO / Mitchell (1919+)

    **Environmental Pillar**
        Climate Risk: INFORM (2012+)
        Disasters: EM-DAT (1900+)
        Temperature: HadCRUT5 (1850+)
    """

    def __init__(self):
        """Initialize with lazy-loading caches."""
        self._cache: Dict[str, Any] = {}

    def _get_or_load(self, key: str, loader):
        """Cache-aware loader."""
        if key not in self._cache:
            result = loader()
            if result is not None:
                self._cache[key] = result
        return self._cache.get(key)

    # ── Political Pillar ──────────────────────────────────────────────────

    def get_governance_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get governance / rule-of-law score (normalised 0–1).

        Proxy chain:
            1. WGI rule_of_law (1996+): rescale from [−2.5, 2.5] to [0, 1]
            2. Polity5 polity2 (1800+): rescale from [−10, 10] to [0, 1]
            3. V-Dem v2x_rule (1789+): already on 0–1 scale

        Returns:
            Governance score 0 (worst) to 1 (best), or None.
        """
        # Try Polity5 first for historical (most authoritative for regimes)
        polity = self._get_or_load(
            f"polity5_{country_code}",
            lambda: get_polity2_series(country_code),
        )
        if polity is not None:
            val = self._lookup_annual(polity, year)
            if val is not None:
                # Rescale −10..+10 → 0..1
                return (val + 10) / 20.0

        # Fallback: V-Dem rule of law
        vdem = self._get_or_load(
            f"vdem_rule_{country_code}",
            lambda: get_vdem_series(country_code, "v2x_rule"),
        )
        if vdem is not None:
            val = self._lookup_annual(vdem, year)
            if val is not None:
                return float(val)

        return None

    def get_democracy_index(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get electoral democracy score (0–1).

        Proxy chain:
            1. V-Dem polyarchy (1789+): already on 0–1 scale
            2. Polity5 democ / 10 (1800+): rescale 0–10 → 0–1
        """
        vdem = self._get_or_load(
            f"vdem_polyarchy_{country_code}",
            lambda: get_vdem_series(country_code, "v2x_polyarchy"),
        )
        if vdem is not None:
            val = self._lookup_annual(vdem, year)
            if val is not None:
                return float(val)

        polity = self._get_or_load(
            f"polity5_{country_code}",
            lambda: get_polity2_series(country_code),
        )
        if polity is not None:
            val = self._lookup_annual(polity, year)
            if val is not None:
                return max(0.0, (val + 10) / 20.0)

        return None

    def get_civil_liberties(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """Get civil liberties index (0–1) from V-Dem (1789+)."""
        vdem = self._get_or_load(
            f"vdem_civlib_{country_code}",
            lambda: get_vdem_series(country_code, "v2x_civlib"),
        )
        if vdem is not None:
            return self._lookup_annual(vdem, year)
        return None

    def get_conflict_risk(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get conflict risk score (0–1), inverted so 1 = highest risk.

        Uses COW (1816+) and UCDP (1946+) for battle-death intensity.
        """
        intensity = get_conflict_intensity(country_code, year)
        if intensity is not None:
            return intensity
        return None

    def get_political_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Composite political pillar score (0–1, higher = more resilient).

        Components (equal weight):
            - Governance / rule of law
            - Democracy index
            - Civil liberties
            - Inverse conflict risk
        """
        components = []

        governance = self.get_governance_score(country_code, year)
        if governance is not None:
            components.append(governance)

        democracy = self.get_democracy_index(country_code, year)
        if democracy is not None:
            components.append(democracy)

        civlib = self.get_civil_liberties(country_code, year)
        if civlib is not None:
            components.append(civlib)

        conflict = self.get_conflict_risk(country_code, year)
        if conflict is not None:
            components.append(1.0 - conflict)  # Invert: low conflict = high score

        if not components:
            return None

        return float(np.mean(components))

    # ── Economic Pillar ──────────────────────────────────────────────────

    def get_gdp_growth_proxy(
        self, country_code: str, year: int, window: int = 5
    ) -> Optional[float]:
        """
        Get annualised real GDP growth from Maddison PPP data (1820+).

        Uses compound annual growth rate over `window` years.
        Normalised to 0–1 where 0 = severe contraction, 1 = strong growth.

        Returns:
            Normalised GDP growth score (0–1).
        """
        gdppc = self._get_or_load(
            f"maddison_{country_code}",
            lambda: get_maddison_gdppc(country_code),
        )
        if gdppc is None:
            return None

        current = self._lookup_annual(gdppc, year)
        past = self._lookup_annual(gdppc, year - window)

        if current is not None and past is not None and past > 0:
            cagr = (current / past) ** (1.0 / window) - 1.0
            # Normalise: −10% → 0.0, 0% → 0.5, +10% → 1.0
            return max(0.0, min(1.0, (cagr + 0.10) / 0.20))

        return None

    def get_economic_diversity_proxy(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get economic diversity/complexity proxy.

        For historical periods (pre-1995), uses GDP per capita relative
        to global leader as a rough proxy for economic sophistication.

        Returns:
            0–1 score where 1 = highest complexity/diversity.
        """
        gdppc = self._get_or_load(
            f"maddison_{country_code}",
            lambda: get_maddison_gdppc(country_code),
        )
        if gdppc is None:
            return None

        val = self._lookup_annual(gdppc, year)
        if val is None:
            return None

        # Use log GDP per capita, ceiling at ~$50K (2011 int'l $)
        # Log(50000) ≈ 10.8; Log(500) ≈ 6.2
        log_val = np.log(max(val, 100))
        return max(0.0, min(1.0, (log_val - 5.0) / 6.0))

    def get_crisis_fragility(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get economic crisis fragility from Reinhart-Rogoff (0–1).

        0 = no recent crises → high resilience
        1 = multiple overlapping crises → extreme fragility
        """
        count = get_crisis_count(country_code, year, window=5)
        # Normalise: 0 crises → 0, 5+ → 1
        return min(1.0, count / 5.0)

    def get_cbi_proxy(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get central bank independence (0–1, Garriga 1970–2017).

        For pre-1970 periods, returns heuristic estimates based on
        whether central bank existed + gold standard constraints.
        """
        score = get_cbi_score(country_code, year)
        if score is not None:
            return score

        # Heuristic for pre-1970:
        # Under gold standard, CB independence was structurally constrained
        if year < 1914:
            known_cbs = {"USA": 0.0, "GBR": 0.5, "FRA": 0.4, "DEU": 0.5}
            # US had no central bank before 1913
            return known_cbs.get(country_code.upper(), 0.3)
        elif year < 1945:
            return 0.3  # Most CBs under government direction during wars
        elif year < 1970:
            return 0.4  # Post-war: moderate independence in advanced economies

        return None

    def get_fiscal_space_proxy(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get fiscal space proxy from crisis history and GDP trajectory.

        Countries with high GDP growth + few crises ≈ stronger fiscal space.
        A crude but defensible approximation for historical periods.

        Returns:
            0–1 score, higher = more fiscal space.
        """
        growth = self.get_gdp_growth_proxy(country_code, year)
        crisis = self.get_crisis_fragility(country_code, year)

        if growth is not None and crisis is not None:
            return growth * 0.6 + (1.0 - crisis) * 0.4
        elif growth is not None:
            return growth
        elif crisis is not None:
            return 1.0 - crisis

        return None

    def get_economic_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Composite economic pillar score (0–1, higher = more resilient).

        Components:
            - GDP growth trajectory (Maddison)
            - Economic diversity (GDP per capita proxy)
            - Central bank independence (Garriga + heuristics)
            - Fiscal space (composite)
            - Inverse crisis fragility (Reinhart-Rogoff)
        """
        components = []
        weights = []

        growth = self.get_gdp_growth_proxy(country_code, year)
        if growth is not None:
            components.append(growth)
            weights.append(0.20)

        diversity = self.get_economic_diversity_proxy(country_code, year)
        if diversity is not None:
            components.append(diversity)
            weights.append(0.20)

        cbi = self.get_cbi_proxy(country_code, year)
        if cbi is not None:
            components.append(cbi)
            weights.append(0.20)

        fiscal = self.get_fiscal_space_proxy(country_code, year)
        if fiscal is not None:
            components.append(fiscal)
            weights.append(0.20)

        crisis = self.get_crisis_fragility(country_code, year)
        if crisis is not None:
            components.append(1.0 - crisis)
            weights.append(0.20)

        if not components:
            return None

        # Renormalise weights
        total_w = sum(weights)
        return float(sum(c * w / total_w for c, w in zip(components, weights)))

    # ── Social Pillar ─────────────────────────────────────────────────────

    def get_hdi_proxy(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get HDI proxy for pre-1990 periods (0–1).

        Uses Crafts (1997) approach: composite of GDP per capita (income),
        V-Dem suffrage (education proxy), and life expectancy proxy
        from Maddison + disaster severity.

        For post-1990, defer to UNDP official HDI.

        Returns:
            0–1 score approximating HDI.
        """
        # GDP per capita component (income dimension)
        income = self.get_economic_diversity_proxy(country_code, year)

        # Suffrage as education/empowerment proxy
        suffrage = self._get_or_load(
            f"vdem_suffrage_{country_code}",
            lambda: get_vdem_series(country_code, "v2x_suffr"),
        )
        suffrage_val = self._lookup_annual(suffrage, year) if suffrage is not None else None

        components = [c for c in [income, suffrage_val] if c is not None]
        if not components:
            return None

        return float(np.mean(components))

    def get_suffrage_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """Get suffrage score from V-Dem (0–1, 1789+)."""
        vdem = self._get_or_load(
            f"vdem_suffrage_{country_code}",
            lambda: get_vdem_series(country_code, "v2x_suffr"),
        )
        if vdem is not None:
            return self._lookup_annual(vdem, year)
        return None

    def get_unemployment_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get unemployment-based social stress score (0–1, inverted).

        0 = very high unemployment (>20%) → low resilience
        1 = low unemployment (<3%) → high resilience

        Uses historical datasets or Mitchell's statistics.
        """
        series = self._get_or_load(
            f"unemp_{country_code}",
            lambda: load_historical_unemployment(country_code),
        )
        if series is not None:
            val = self._lookup_annual(series, year)
            if val is not None:
                # Normalise: 20%+ → 0, 3% → 1
                return max(0.0, min(1.0, 1.0 - (val - 3.0) / 17.0))
        return None

    def get_social_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Composite social pillar score (0–1, higher = more resilient).

        Components:
            - HDI proxy (income + education + health)
            - Suffrage (political participation → social capital)
            - Inverse unemployment stress
            - Civil liberties (cross-cuts social and political)
        """
        components = []
        weights = []

        hdi = self.get_hdi_proxy(country_code, year)
        if hdi is not None:
            components.append(hdi)
            weights.append(0.30)

        suffrage = self.get_suffrage_score(country_code, year)
        if suffrage is not None:
            components.append(suffrage)
            weights.append(0.25)

        unemp = self.get_unemployment_score(country_code, year)
        if unemp is not None:
            components.append(unemp)
            weights.append(0.25)

        civlib = self.get_civil_liberties(country_code, year)
        if civlib is not None:
            components.append(civlib)
            weights.append(0.20)

        if not components:
            return None

        total_w = sum(weights)
        return float(sum(c * w / total_w for c, w in zip(components, weights)))

    # ── Environmental Pillar ──────────────────────────────────────────────

    def get_disaster_risk(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Get disaster risk from EM-DAT (1900+).

        Returns:
            0–1 severity score (0 = no disasters, 1 = catastrophic).
        """
        return get_disaster_severity(country_code, year, window=5)

    def get_climate_anomaly_score(self, year: int) -> Optional[float]:
        """
        Get climate change exposure score from HadCRUT5 (1850+).

        Uses rate of temperature change over 30 years as risk indicator.
        Returns 0–1 where 1 = rapid warming (climate instability).
        """
        hadcrut = self._get_or_load("hadcrut", load_hadcrut)
        if hadcrut is None:
            return None

        current = self._lookup_annual(hadcrut, year)
        baseline = self._lookup_annual(hadcrut, year - 30)

        if current is not None and baseline is not None:
            # Rate of change: 0°C/30yr → 0.0, 1°C/30yr → 0.5, 2°C/30yr → 1.0
            delta = current - baseline
            return max(0.0, min(1.0, delta / 2.0))

        return None

    def get_environmental_score(
        self, country_code: str, year: int
    ) -> Optional[float]:
        """
        Composite environmental pillar score (0–1, higher = more resilient).

        Components:
            - Inverse disaster severity (EM-DAT)
            - Inverse climate anomaly rate (HadCRUT5)

        Note: For pre-2012 periods, this is necessarily thinner than the
        modern INFORM-based assessment.  The disaster history provides a
        reasonable risk proxy, while the climate anomaly captures the
        macro trend that increasingly correlates with physical risk.
        """
        components = []
        weights = []

        disaster = self.get_disaster_risk(country_code, year)
        if disaster is not None:
            components.append(1.0 - disaster)
            weights.append(0.60)

        climate = self.get_climate_anomaly_score(year)
        if climate is not None:
            components.append(1.0 - climate)
            weights.append(0.40)

        if not components:
            return None

        total_w = sum(weights)
        return float(sum(c * w / total_w for c, w in zip(components, weights)))

    # ── Composite GRRI ────────────────────────────────────────────────────

    def get_historical_grri(
        self,
        country_code: str,
        year: int,
        weights: Optional[Dict[str, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute historical GRRI resilience score for a country-year.

        Mirrors the ``calculate_grri()`` function in
        ``grri_mac.grri.modifier`` but uses historical proxy data.

        Args:
            country_code: ISO-3 country code (e.g. 'USA', 'GBR', 'DEU').
            year: Calendar year.
            weights: Optional pillar weights (default equal 0.25 each).

        Returns:
            Dict with 'resilience', 'modifier', pillar scores, and
            data provenance metadata.  None if insufficient data.
        """
        if weights is None:
            weights = {
                "political": 0.25,
                "economic": 0.25,
                "social": 0.25,
                "environmental": 0.25,
            }

        scores: Dict[str, Optional[float]] = {}
        provenance: Dict[str, List[str]] = {}

        # Political
        scores["political"] = self.get_political_score(country_code, year)
        provenance["political"] = self._get_provenance("political", country_code, year)

        # Economic
        scores["economic"] = self.get_economic_score(country_code, year)
        provenance["economic"] = self._get_provenance("economic", country_code, year)

        # Social
        scores["social"] = self.get_social_score(country_code, year)
        provenance["social"] = self._get_provenance("social", country_code, year)

        # Environmental
        scores["environmental"] = self.get_environmental_score(country_code, year)
        provenance["environmental"] = self._get_provenance("environmental", country_code, year)

        # Need at least 2 pillars with data
        available = {k: v for k, v in scores.items() if v is not None}
        if len(available) < 2:
            logger.warning(
                f"Insufficient data for GRRI {country_code} {year}: "
                f"only {list(available.keys())} available"
            )
            return None

        # Compute weighted resilience (re-normalise weights for available pillars)
        avail_weights = {k: weights.get(k, 0.25) for k in available}
        total_w = sum(avail_weights.values())
        resilience = sum(
            available[k] * avail_weights[k] / total_w for k in available
        )

        # Import modifier calculation from grri_mac.grri.modifier
        from grri_mac.grri.modifier import grri_to_modifier

        modifier = grri_to_modifier(resilience)

        # Interpretation
        if modifier < 0.7:
            interp = f"HIGH RESILIENCE ({modifier:.2f}x)"
        elif modifier < 1.0:
            interp = f"MODERATE RESILIENCE ({modifier:.2f}x)"
        elif modifier < 1.3:
            interp = f"NEUTRAL ({modifier:.2f}x)"
        elif modifier < 1.7:
            interp = f"LOW RESILIENCE ({modifier:.2f}x)"
        else:
            interp = f"FRAGILE ({modifier:.2f}x)"

        return {
            "country": country_code,
            "year": year,
            "resilience": round(resilience, 4),
            "modifier": round(modifier, 4),
            "pillar_scores": {
                k: round(v, 4) if v is not None else None
                for k, v in scores.items()
            },
            "interpretation": interp,
            "pillars_available": list(available.keys()),
            "pillars_missing": [k for k in scores if scores[k] is None],
            "provenance": provenance,
        }

    def get_historical_grri_timeseries(
        self,
        country_code: str,
        start_year: int = 1870,
        end_year: int = 2020,
        weights: Optional[Dict[str, float]] = None,
    ) -> pd.DataFrame:
        """
        Generate annual GRRI time series for a country.

        Returns:
            DataFrame with columns: year, resilience, modifier,
            political, economic, social, environmental.
        """
        records = []
        for year in range(start_year, end_year + 1):
            result = self.get_historical_grri(country_code, year, weights)
            if result is not None:
                records.append({
                    "year": year,
                    "resilience": result["resilience"],
                    "modifier": result["modifier"],
                    **result["pillar_scores"],
                })

        if not records:
            logger.warning(
                f"No GRRI data for {country_code} in {start_year}-{end_year}"
            )
            return pd.DataFrame()

        df = pd.DataFrame(records)
        logger.info(
            f"Generated GRRI series for {country_code}: "
            f"{len(df)} years ({df['year'].min()}-{df['year'].max()})"
        )
        return df

    # ── Data Availability Report ──────────────────────────────────────────

    def get_data_availability_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Report which historical GRRI data sources exist on disk.

        Mirrors ``HistoricalDataProvider.get_data_availability_summary()``
        from ``grri_mac.data.historical_sources``.
        """
        summary: Dict[str, Dict[str, Any]] = {}

        # Polity5
        polity_dir = GRRI_HISTORICAL_DIR / "polity5"
        summary["polity5"] = {
            "available": any(
                (polity_dir / f).exists()
                for f in ("p5v2018.csv", "p5v2018.xls")
            ),
            "path": str(polity_dir),
            "coverage": "1800-2018",
            "pillar": "political",
        }

        # V-Dem
        vdem_dir = GRRI_HISTORICAL_DIR / "vdem"
        summary["vdem"] = {
            "available": (vdem_dir / "vdem_core.csv").exists(),
            "path": str(vdem_dir),
            "coverage": "1789-present",
            "pillar": "political, social",
        }

        # COW
        cow_dir = GRRI_HISTORICAL_DIR / "cow"
        summary["cow"] = {
            "available": (cow_dir / "wars.csv").exists(),
            "path": str(cow_dir),
            "coverage": "1816-present",
            "pillar": "political",
        }

        # Maddison
        maddison_dir = GRRI_HISTORICAL_DIR / "maddison"
        summary["maddison"] = {
            "available": any(
                (maddison_dir / f).exists()
                for f in ("mpd2020.csv", "mpd2020.xlsx")
            ),
            "path": str(maddison_dir),
            "coverage": "1820-present",
            "pillar": "economic, social",
        }

        # Reinhart-Rogoff
        rr_dir = GRRI_HISTORICAL_DIR / "reinhart_rogoff"
        summary["reinhart_rogoff"] = {
            "available": (rr_dir / "crises.csv").exists(),
            "path": str(rr_dir),
            "coverage": "1800-present",
            "pillar": "economic",
        }

        # EM-DAT
        emdat_dir = GRRI_HISTORICAL_DIR / "emdat"
        summary["emdat"] = {
            "available": (emdat_dir / "emdat_public.csv").exists(),
            "path": str(emdat_dir),
            "coverage": "1900-present",
            "pillar": "environmental",
        }

        # HadCRUT
        hadcrut_dir = GRRI_HISTORICAL_DIR / "hadcrut"
        summary["hadcrut"] = {
            "available": (hadcrut_dir / "hadcrut5_annual.csv").exists(),
            "path": str(hadcrut_dir),
            "coverage": "1850-present",
            "pillar": "environmental",
        }

        # Garriga CBI
        garriga_dir = GRRI_HISTORICAL_DIR / "garriga"
        summary["garriga_cbi"] = {
            "available": (garriga_dir / "cbi_index.csv").exists(),
            "path": str(garriga_dir),
            "coverage": "1970-2017",
            "pillar": "economic",
        }

        # GSDB Sanctions
        gsdb_dir = GRRI_HISTORICAL_DIR / "gsdb"
        summary["gsdb"] = {
            "available": (gsdb_dir / "sanctions.csv").exists(),
            "path": str(gsdb_dir),
            "coverage": "1950-2022",
            "pillar": "economic",
        }

        # UCDP
        ucdp_dir = GRRI_HISTORICAL_DIR / "ucdp"
        summary["ucdp"] = {
            "available": (ucdp_dir / "ucdp_brd.csv").exists(),
            "path": str(ucdp_dir),
            "coverage": "1946-present",
            "pillar": "political",
        }

        # Unemployment
        unemp_dir = GRRI_HISTORICAL_DIR / "unemployment"
        summary["historical_unemployment"] = {
            "available": unemp_dir.exists() and any(unemp_dir.glob("*.csv")),
            "path": str(unemp_dir),
            "coverage": "1919-present (varies by country)",
            "pillar": "social",
        }

        return summary

    # ── Helper Methods ────────────────────────────────────────────────────

    def _lookup_annual(
        self,
        series: Optional[pd.Series],
        year: int,
        max_gap: int = 3,
    ) -> Optional[float]:
        """
        Look up a value for a given year in an annual-indexed series.

        Allows forward-fill up to `max_gap` years to handle data gaps.
        """
        if series is None or len(series) == 0:
            return None

        target = datetime(year, 7, 1)
        start = datetime(year - max_gap, 1, 1)
        mask = (series.index >= start) & (series.index <= target)
        filtered = series[mask]

        if filtered.empty:
            return None

        return float(filtered.iloc[-1])

    def _get_provenance(
        self, pillar: str, country_code: str, year: int
    ) -> List[str]:
        """List which data sources contributed to a pillar score."""
        sources: List[str] = []

        if pillar == "political":
            if f"polity5_{country_code}" in self._cache:
                sources.append(f"Polity5 (1800-2018)")
            if f"vdem_rule_{country_code}" in self._cache:
                sources.append("V-Dem rule_of_law (1789+)")
            if f"vdem_polyarchy_{country_code}" in self._cache:
                sources.append("V-Dem polyarchy (1789+)")
            if f"vdem_civlib_{country_code}" in self._cache:
                sources.append("V-Dem civil_liberties (1789+)")
            # COW is loaded globally
            try:
                if load_cow_wars() is not None:
                    sources.append("COW wars (1816+)")
            except Exception:
                pass

        elif pillar == "economic":
            if f"maddison_{country_code}" in self._cache:
                sources.append("Maddison Project GDP (1820+)")
            if load_reinhart_rogoff() is not None:
                sources.append("Reinhart-Rogoff crises (1800+)")
            if load_cbi_index() is not None:
                sources.append("Garriga CBI (1970-2017)")
            elif year < 1970:
                sources.append("CBI heuristic (pre-1970)")

        elif pillar == "social":
            if f"vdem_suffrage_{country_code}" in self._cache:
                sources.append("V-Dem suffrage (1789+)")
            if f"unemp_{country_code}" in self._cache:
                sources.append("Historical unemployment")

        elif pillar == "environmental":
            if "hadcrut" in self._cache:
                sources.append("HadCRUT5 temp anomaly (1850+)")
            if load_emdat() is not None:
                sources.append("EM-DAT disasters (1900+)")

        return sources
