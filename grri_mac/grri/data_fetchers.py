"""
GRRI Data Fetchers - Fetch data from various sources for GRS Tracker.

Sources with APIs:
- IMF WEO (SDMX JSON)
- World Bank WGI (REST API)
- World Bank Indicators (REST API)
- V-Dem (Direct CSV download)

Manual sources (Excel downloads):
- Fragile States Index
- Harvard Growth Lab
- EM-DAT
- Carnegie Protest Tracker
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

# ============================================================
# IMF World Economic Outlook (WEO) Data Fetcher
# ============================================================


class IMFWEOClient:
    """Fetch economic indicators from IMF WEO SDMX API."""

    BASE_URL = "https://www.imf.org/external/datamapper/api/v1"

    # WEO indicator codes
    INDICATORS = {
        "inflation": "PCPIPCH",        # Inflation rate (% change)
        "fiscal_balance": "GGXCNL_NGDP",  # Fiscal balance (% GDP)
        "current_account": "BCA_NGDPD",   # Current account (% GDP)
        "gdp_growth": "NGDP_RPCH",     # Real GDP growth
        "unemployment": "LUR",          # Unemployment rate
    }

    # G20 ISO3 codes
    G20_COUNTRIES = [
        "ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN",
        "ITA", "JPN", "MEX", "RUS", "SAU", "ZAF", "KOR", "TUR", "GBR", "USA"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "GRRI-MAC-Framework/1.0"
        })

    def get_indicator(self, indicator_code: str, countries: Optional[List[str]] = None,
                      start_year: int = 2000) -> Dict[str, Dict[str, float]]:
        """
        Fetch WEO indicator for specified countries.

        Returns:
            Dict of country_code -> {year: value}
        """
        if countries is None:
            countries = self.G20_COUNTRIES

        try:
            # IMF DataMapper API endpoint
            url = f"{self.BASE_URL}/indicators/{indicator_code}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            result = {}
            values_data = data.get("values", {}).get(indicator_code, {})

            for country in countries:
                if country in values_data:
                    country_data = {}
                    for year, value in values_data[country].items():
                        if int(year) >= start_year and value is not None:
                            country_data[year] = float(value)
                    if country_data:
                        result[country] = country_data

            logger.info(f"Fetched {indicator_code} for {len(result)} countries")
            return result

        except Exception as e:
            logger.error(f"IMF WEO API error for {indicator_code}: {e}")
            return {}

    def get_all_indicators(self, countries: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch all GRRI-relevant WEO indicators."""
        result: Dict[str, Any] = {
            "source": "IMF_WEO",
            "timestamp": datetime.utcnow().isoformat(),
            "indicators": {}
        }

        for name, code in self.INDICATORS.items():
            data = self.get_indicator(code, countries)
            if data:
                result["indicators"][name] = {
                    "code": code,
                    "data": data
                }

        return result


# ============================================================
# World Bank Governance Indicators (WGI) Fetcher
# ============================================================

class WorldBankWGIClient:
    """Fetch governance indicators from World Bank API."""

    BASE_URL = "https://api.worldbank.org/v2"

    # WGI indicator codes
    INDICATORS = {
        "rule_of_law": "RL.EST",
        "government_effectiveness": "GE.EST",
        "regulatory_quality": "RQ.EST",
        "political_stability": "PV.EST",  # Political Violence
        "control_of_corruption": "CC.EST",
        "voice_accountability": "VA.EST",
    }

    G20_COUNTRIES = [
        "ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN",
        "ITA", "JPN", "MEX", "RUS", "SAU", "ZAF", "KOR", "TUR", "GBR", "USA"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "GRRI-MAC-Framework/1.0"
        })

    def get_indicator(self, indicator_code: str, countries: Optional[List[str]] = None,
                      start_year: int = 2000) -> Dict[str, Dict[str, float]]:
        """
        Fetch WGI indicator for specified countries.

        Returns:
            Dict of country_code -> {year: value}
        """
        if countries is None:
            countries = self.G20_COUNTRIES

        countries_str = ";".join(countries)

        try:
            url = f"{self.BASE_URL}/country/{countries_str}/indicator/{indicator_code}"
            params = {
                "format": "json",
                "per_page": 1000,
                "date": f"{start_year}:{datetime.now().year}"
            }

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # World Bank API returns [metadata, data]
            data = response.json()
            if len(data) < 2 or not data[1]:
                return {}

            result: Dict[str, Dict[str, float]] = {}
            for record in data[1]:
                country = record.get("country", {}).get("id")
                year = record.get("date")
                value = record.get("value")

                if country and year and value is not None:
                    if country not in result:
                        result[country] = {}
                    result[country][year] = float(value)

            logger.info(f"Fetched WGI {indicator_code} for {len(result)} countries")
            return result

        except Exception as e:
            logger.error(f"World Bank API error for {indicator_code}: {e}")
            return {}

    def get_all_indicators(self, countries: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch all WGI indicators for GRRI political pillar."""
        result: Dict[str, Any] = {
            "source": "World_Bank_WGI",
            "timestamp": datetime.utcnow().isoformat(),
            "indicators": {}
        }

        for name, code in self.INDICATORS.items():
            data = self.get_indicator(code, countries)
            if data:
                result["indicators"][name] = {
                    "code": code,
                    "data": data
                }

        return result


# ============================================================
# UNDP Human Development Index Fetcher
# ============================================================

class UNDPHDIClient:
    """Fetch HDI data from UNDP API."""

    BASE_URL = "https://hdr.undp.org/sites/default/files/2024_statistical_annex"

    # HDI data is typically in Excel files, but they have a data API
    API_URL = "https://hdr.undp.org/api/v1"

    def __init__(self):
        self.session = requests.Session()

    def get_hdi_data(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch HDI values. UNDP API can be unreliable, so we also support
        cached/manual data.
        """
        # Try UNDP API first
        try:
            # Note: UNDP API structure may vary - adjust as needed
            url = f"{self.API_URL}/data/hdi"
            response = self.session.get(url, timeout=30)

            if response.ok:
                data = response.json()
                # Parse based on actual API response structure
                return self._parse_hdi_response(data)

        except Exception as e:
            logger.warning(f"UNDP API not available: {e}")

        # Return empty - will use cached/manual data
        return {}

    def _parse_hdi_response(self, data: dict) -> Dict[str, Dict[str, float]]:
        """Parse HDI API response."""
        # Placeholder - actual parsing depends on API structure
        return {}


# ============================================================
# V-Dem Democracy Indicators Fetcher
# ============================================================

class VDemClient:
    """Fetch democracy indicators from V-Dem."""

    # V-Dem provides data via direct CSV download
    DATA_URL = (  # noqa: E501
        "https://v-dem.net/static/website/files/"
        "Country_Year_V-Dem_Core_CSV_v14/"
        "V-Dem-CY-Core-v14.csv"
    )

    # Key V-Dem variables for GRRI
    INDICATORS = {
        "freedom_association": "v2cseeorgs",  # CSO entry/exit
        "freedom_expression": "v2x_freexp",   # Freedom of expression
        "suffrage": "v2x_suffr",              # Share with suffrage
        "civil_liberties": "v2x_civlib",      # Civil liberties index
    }

    def __init__(self):
        self.session = requests.Session()
        self._data_cache = None

    def download_data(self) -> bool:
        """Download V-Dem dataset (large file, ~100MB)."""
        try:
            # For efficiency, check if we have cached data
            cache_path = "data/vdem_cache.csv"
            if os.path.exists(cache_path):
                # Check if cache is recent (< 90 days)
                cache_age = datetime.now().timestamp() - os.path.getmtime(cache_path)
                if cache_age < 90 * 24 * 3600:
                    logger.info("Using cached V-Dem data")
                    return True

            logger.info("Downloading V-Dem data (this may take a while)...")
            response = self.session.get(self.DATA_URL, timeout=300, stream=True)
            response.raise_for_status()

            os.makedirs("data", exist_ok=True)
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("V-Dem data downloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download V-Dem data: {e}")
            return False


# ============================================================
# GRRI Data Aggregator
# ============================================================

class GRRIDataAggregator:
    """Aggregate data from all GRRI sources."""

    def __init__(self):
        self.imf = IMFWEOClient()
        self.wgi = WorldBankWGIClient()
        self.undp = UNDPHDIClient()
        self.vdem = VDemClient()

    def fetch_all_available(self) -> Dict[str, Any]:
        """Fetch data from all available API sources."""
        result: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "sources_fetched": [],
            "sources_failed": [],
            "data": {}
        }

        # IMF WEO (Economic pillar)
        try:
            imf_data = self.imf.get_all_indicators()
            if imf_data.get("indicators"):
                result["data"]["imf_weo"] = imf_data
                result["sources_fetched"].append("IMF_WEO")
        except Exception as e:
            logger.error(f"IMF WEO fetch failed: {e}")
            result["sources_failed"].append(("IMF_WEO", str(e)))

        # World Bank WGI (Political pillar)
        try:
            wgi_data = self.wgi.get_all_indicators()
            if wgi_data.get("indicators"):
                result["data"]["world_bank_wgi"] = wgi_data
                result["sources_fetched"].append("World_Bank_WGI")
        except Exception as e:
            logger.error(f"World Bank WGI fetch failed: {e}")
            result["sources_failed"].append(("World_Bank_WGI", str(e)))

        # UNDP HDI (Social pillar)
        try:
            hdi_data = self.undp.get_hdi_data()
            if hdi_data:
                result["data"]["undp_hdi"] = {
                    "source": "UNDP_HDI",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": hdi_data
                }
                result["sources_fetched"].append("UNDP_HDI")
        except Exception as e:
            logger.error(f"UNDP HDI fetch failed: {e}")
            result["sources_failed"].append(("UNDP_HDI", str(e)))

        result["total_sources"] = len(result["sources_fetched"])
        return result

    def calculate_grri_scores(self, raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate GRRI scores from raw indicator data.

        Returns:
            Dict of country_code -> {pillar_scores, composite_score}
        """
        # Get latest year's data for each indicator
        latest_year = str(datetime.now().year - 1)  # Usually 1 year lag

        scores = {}

        # This is a simplified scoring - real implementation would:
        # 1. Normalize each indicator (min-max scaling)
        # 2. Invert direction so higher = higher risk
        # 3. Weight and aggregate within pillars
        # 4. Average pillar scores for composite

        # For now, return placeholder structure
        for country in self.imf.G20_COUNTRIES:
            scores[country] = {
                "political": None,
                "economic": None,
                "social": None,
                "environmental": None,
                "composite": None,
                "data_year": latest_year
            }

        return scores


# ============================================================
# Main execution for testing
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Testing GRRI Data Fetchers ===\n")

    aggregator = GRRIDataAggregator()
    result = aggregator.fetch_all_available()

    print(f"Sources fetched: {result['sources_fetched']}")
    print(f"Sources failed: {result['sources_failed']}")

    # Save raw data for inspection
    with open("data/grri_raw_data.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    print("\nRaw data saved to data/grri_raw_data.json")
