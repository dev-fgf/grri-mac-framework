"""GRRI Data Client for fetching Global Risk and Resilience Index indicators."""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# G20 country codes (ISO 3166-1 alpha-3)
G20_COUNTRIES = {
    "ARG": "Argentina",
    "AUS": "Australia",
    "BRA": "Brazil",
    "CAN": "Canada",
    "CHN": "China",
    "FRA": "France",
    "DEU": "Germany",
    "IND": "India",
    "IDN": "Indonesia",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "South Korea",
    "MEX": "Mexico",
    "RUS": "Russia",
    "SAU": "Saudi Arabia",
    "ZAF": "South Africa",
    "TUR": "Turkey",
    "GBR": "United Kingdom",
    "USA": "United States",
    "EUU": "European Union",  # EU as entity
}

# World Bank API indicator codes
WB_INDICATORS = {
    # Political Pillar
    "rule_of_law": "RL.EST",  # Rule of Law Estimate
    "gov_effectiveness": "GE.EST",  # Government Effectiveness Estimate
    "regulatory_quality": "RQ.EST",  # Regulatory Quality Estimate
    "control_corruption": "CC.EST",  # Control of Corruption Estimate
    "voice_accountability": "VA.EST",  # Voice and Accountability
    "political_stability": "PV.EST",  # Political Stability

    # Economic Pillar
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",  # GDP growth (annual %)
    "inflation": "FP.CPI.TOTL.ZG",  # Inflation, consumer prices (annual %)
    "current_account": "BN.CAB.XOKA.GD.ZS",  # Current account balance (% of GDP)
    "gross_debt": "GC.DOD.TOTL.GD.ZS",  # Central govt debt (% of GDP)
    "unemployment": "SL.UEM.TOTL.ZS",  # Unemployment (% of labor force)
    "education_spending": "SE.XPD.TOTL.GD.ZS",  # Education spending (% of GDP)

    # Social Pillar
    "gini_index": "SI.POV.GINI",  # Gini index
    "hdi": "HD.HCI.OVRL",  # Human Capital Index (proxy for HDI)
    "life_expectancy": "SP.DYN.LE00.IN",  # Life expectancy at birth
    "poverty_ratio": "SI.POV.DDAY",  # Poverty headcount ratio

    # Environmental Pillar
    "co2_emissions": "EN.ATM.CO2E.PC",  # CO2 emissions (metric tons per capita)
    "renewable_energy": "EG.FEC.RNEW.ZS",  # Renewable energy (% of total)
    "forest_area": "AG.LND.FRST.ZS",  # Forest area (% of land area)
}

# GRRI Pillar structure
GRRI_PILLARS = {
    "political": {
        "name": "Political",
        "weight": 0.25,
        "indicators": [
            "rule_of_law",
            "gov_effectiveness",
            "regulatory_quality",
            "control_corruption",
            "voice_accountability",
            "political_stability",
        ],
    },
    "economic": {
        "name": "Economic",
        "weight": 0.25,
        "indicators": [
            "gdp_growth",
            "inflation",
            "current_account",
            "gross_debt",
            "unemployment",
            "education_spending",
        ],
    },
    "social": {
        "name": "Social",
        "weight": 0.25,
        "indicators": [
            "gini_index",
            "life_expectancy",
            "poverty_ratio",
        ],
    },
    "environmental": {
        "name": "Environmental",
        "weight": 0.25,
        "indicators": [
            "co2_emissions",
            "renewable_energy",
            "forest_area",
        ],
    },
}


class GRRIClient:
    """Client for fetching GRRI indicator data from World Bank and other sources."""

    WB_API_BASE = "https://api.worldbank.org/v2"

    def __init__(self):
        self.cache = {}

    def fetch_wb_indicator(
        self,
        indicator: str,
        countries: list = None,
        start_year: int = 2015,
        end_year: int = 2025,
    ) -> dict:
        """Fetch indicator data from World Bank API."""
        if countries is None:
            countries = list(G20_COUNTRIES.keys())

        # Remove EU from World Bank queries (not a country)
        countries = [c for c in countries if c != "EUU"]
        country_str = ";".join(countries)

        url = (
            f"{self.WB_API_BASE}/country/{country_str}/indicator/{indicator}"
            f"?format=json&date={start_year}:{end_year}&per_page=1000"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2 or data[1] is None:
                logger.warning(f"No data for indicator {indicator}")
                return {}

            # Parse results into country -> year -> value format
            results = {}
            for entry in data[1]:
                country = entry.get("countryiso3code") or entry.get("country", {}).get("id")
                year = entry.get("date")
                value = entry.get("value")

                if country and year and value is not None:
                    if country not in results:
                        results[country] = {}
                    results[country][year] = value

            return results

        except Exception as e:
            logger.error(f"World Bank API error for {indicator}: {e}")
            return {}

    def fetch_all_indicators(
        self,
        start_year: int = 2015,
        end_year: int = 2025,
    ) -> dict:
        """Fetch all GRRI indicators from World Bank."""
        all_data = {}

        for indicator_name, wb_code in WB_INDICATORS.items():
            logger.info(f"Fetching {indicator_name} ({wb_code})")
            data = self.fetch_wb_indicator(wb_code, start_year=start_year, end_year=end_year)
            all_data[indicator_name] = data

        return all_data

    def normalize_indicator(
        self,
        value: float,
        indicator_name: str,
        all_values: list,
    ) -> float:
        """
        Normalize indicator to 0-1 scale using robust scaling.
        Higher = better resilience (polarity adjustment applied).
        """
        if not all_values or value is None:
            return None

        # Remove None values
        valid_values = [v for v in all_values if v is not None]
        if not valid_values:
            return None

        # Calculate percentiles for winsorization
        sorted_vals = sorted(valid_values)
        n = len(sorted_vals)
        p1_idx = max(0, int(n * 0.01))
        p99_idx = min(n - 1, int(n * 0.99))
        p1 = sorted_vals[p1_idx]
        p99 = sorted_vals[p99_idx]

        # Winsorize
        winsorized = max(p1, min(p99, value))

        # Scale to 0-1
        if p99 == p1:
            normalized = 0.5
        else:
            normalized = (winsorized - p1) / (p99 - p1)

        # Apply polarity (some indicators are "lower is better")
        # Invert these so higher = better resilience
        invert_indicators = [
            "inflation",
            "gross_debt",
            "unemployment",
            "gini_index",
            "poverty_ratio",
            "co2_emissions",
        ]

        if indicator_name in invert_indicators:
            normalized = 1 - normalized

        return round(normalized, 4)

    def calculate_pillar_scores(
        self,
        country: str,
        year: str,
        raw_data: dict,
    ) -> dict:
        """Calculate pillar scores for a country-year."""
        pillar_scores = {}

        for pillar_key, pillar_info in GRRI_PILLARS.items():
            indicator_scores = []

            for indicator_name in pillar_info["indicators"]:
                if indicator_name not in raw_data:
                    continue

                indicator_data = raw_data[indicator_name]
                if country not in indicator_data:
                    continue
                if year not in indicator_data[country]:
                    continue

                value = indicator_data[country][year]

                # Collect all values across countries for normalization
                all_values = []
                for c_data in indicator_data.values():
                    if year in c_data and c_data[year] is not None:
                        all_values.append(c_data[year])

                normalized = self.normalize_indicator(value, indicator_name, all_values)
                if normalized is not None:
                    indicator_scores.append(normalized)

            # Calculate pillar score as average of indicator scores
            if indicator_scores:
                pillar_scores[pillar_key] = round(
                    sum(indicator_scores) / len(indicator_scores), 4
                )
            else:
                pillar_scores[pillar_key] = None

        return pillar_scores

    def calculate_composite_score(self, pillar_scores: dict) -> Optional[float]:
        """Calculate composite GRRI score from pillar scores."""
        valid_scores = [
            (score, GRRI_PILLARS[pillar]["weight"])
            for pillar, score in pillar_scores.items()
            if score is not None
        ]

        if not valid_scores:
            return None

        # Weighted average
        total_weight = sum(w for _, w in valid_scores)
        weighted_sum = sum(s * w for s, w in valid_scores)

        return round(weighted_sum / total_weight, 4)

    def build_grri_dataset(
        self,
        start_year: int = 2015,
        end_year: int = 2025,
    ) -> list:
        """Build complete GRRI dataset for all G20 countries and years."""
        logger.info(f"Building GRRI dataset for {start_year}-{end_year}")

        # Fetch all raw indicator data
        raw_data = self.fetch_all_indicators(start_year, end_year)

        dataset = []

        for country_code, country_name in G20_COUNTRIES.items():
            for year in range(start_year, end_year + 1):
                year_str = str(year)

                pillar_scores = self.calculate_pillar_scores(
                    country_code, year_str, raw_data
                )

                composite = self.calculate_composite_score(pillar_scores)

                # Only include if we have data
                if composite is not None:
                    dataset.append({
                        "country_code": country_code,
                        "country_name": country_name,
                        "year": year,
                        "quarter": "Q4",  # Annual data defaults to Q4
                        "composite_score": composite,
                        "political_score": pillar_scores.get("political"),
                        "economic_score": pillar_scores.get("economic"),
                        "social_score": pillar_scores.get("social"),
                        "environmental_score": pillar_scores.get("environmental"),
                        "data_source": "World Bank",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

        logger.info(f"Built dataset with {len(dataset)} records")
        return dataset


# Singleton instance
_grri_client = None


def get_grri_client() -> GRRIClient:
    """Get GRRI client singleton."""
    global _grri_client
    if _grri_client is None:
        _grri_client = GRRIClient()
    return _grri_client
