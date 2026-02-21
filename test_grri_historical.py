"""Tests for GRRI historical extension modules.

Covers:
- Data loader functions (graceful when files missing)
- GRRIHistoricalProvider proxy chains and scoring
- Proxy chain documentation completeness
- Integration with grri_mac.grri.modifier
"""

import math
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))


class TestGRRIHistoricalSourceLoaders(unittest.TestCase):
    """Test individual data loaders handle missing files gracefully."""

    def test_load_polity5_missing_file(self):
        from grri_mac.grri.historical_sources import load_polity5
        # Should return None without raising
        result = load_polity5("USA")
        # Result depends on whether data exists on disk
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_vdem_missing_file(self):
        from grri_mac.grri.historical_sources import load_vdem
        result = load_vdem(indicators=["v2x_polyarchy"], country_code="USA")
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_cow_wars_missing_file(self):
        from grri_mac.grri.historical_sources import load_cow_wars
        result = load_cow_wars()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_maddison_missing_file(self):
        from grri_mac.grri.historical_sources import load_maddison_gdp
        result = load_maddison_gdp()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_reinhart_rogoff_missing_file(self):
        from grri_mac.grri.historical_sources import load_reinhart_rogoff
        result = load_reinhart_rogoff()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_emdat_missing_file(self):
        from grri_mac.grri.historical_sources import load_emdat
        result = load_emdat()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_hadcrut_missing_file(self):
        from grri_mac.grri.historical_sources import load_hadcrut
        result = load_hadcrut()
        self.assertTrue(result is None or isinstance(result, pd.Series))

    def test_load_cbi_index_missing_file(self):
        from grri_mac.grri.historical_sources import load_cbi_index
        result = load_cbi_index()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_sanctions_missing_file(self):
        from grri_mac.grri.historical_sources import load_sanctions_database
        result = load_sanctions_database()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_ucdp_missing_file(self):
        from grri_mac.grri.historical_sources import load_ucdp_conflicts
        result = load_ucdp_conflicts()
        self.assertTrue(result is None or isinstance(result, pd.DataFrame))

    def test_load_unemployment_missing_file(self):
        from grri_mac.grri.historical_sources import load_historical_unemployment
        result = load_historical_unemployment("USA")
        self.assertTrue(result is None or isinstance(result, pd.Series))


class TestGRRIHistoricalProviderWithMockedData(unittest.TestCase):
    """Test GRRIHistoricalProvider scoring with synthetic data."""

    def _make_annual_series(self, start_year, end_year, values=None):
        """Create a pandas Series with annual dates and given/random values."""
        years = range(start_year, end_year + 1)
        dates = [datetime(y, 7, 1) for y in years]
        if values is None:
            values = np.linspace(0.3, 0.8, len(dates))
        return pd.Series(values, index=dates, dtype=float)

    def test_lookup_annual_basic(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider
        provider = GRRIHistoricalProvider()

        series = self._make_annual_series(1900, 1950, values=[float(y % 10) for y in range(1900, 1951)])
        # Look up 1925 — should find value = 5.0 (1925 % 10)
        val = provider._lookup_annual(series, 1925)
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 5.0)

    def test_lookup_annual_with_gap(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider
        provider = GRRIHistoricalProvider()

        series = self._make_annual_series(1900, 1920)
        # Look up 1922 — should forward-fill within max_gap=3
        val = provider._lookup_annual(series, 1922, max_gap=3)
        self.assertIsNotNone(val)

    def test_lookup_annual_outside_range(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider
        provider = GRRIHistoricalProvider()

        series = self._make_annual_series(1950, 1960)
        # Look up 1900 — way before data range
        val = provider._lookup_annual(series, 1900)
        self.assertIsNone(val)

    def test_governance_score_from_polity5_mock(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Mock: inject Polity5 data directly into cache
        # Polity5 score of +6 should map to (6+10)/20 = 0.8
        polity_series = self._make_annual_series(1900, 1950, values=[6.0] * 51)
        provider._cache["polity5_USA"] = polity_series

        score = provider.get_governance_score("USA", 1920)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 0.8)

    def test_governance_score_autocracy(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Polity5 score of -8 → (−8+10)/20 = 0.1
        polity_series = self._make_annual_series(1900, 1950, values=[-8.0] * 51)
        provider._cache["polity5_RUS"] = polity_series

        score = provider.get_governance_score("RUS", 1930)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 0.1)

    def test_gdp_growth_proxy(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # GDP per capita growing from 5000 to 6000 over 5 years
        # CAGR ≈ (6000/5000)^(1/5) - 1 ≈ 3.7%
        gdp_values = np.linspace(5000, 6000, 51)
        gdp_series = self._make_annual_series(1900, 1950, values=gdp_values)
        provider._cache["maddison_USA"] = gdp_series

        score = provider.get_gdp_growth_proxy("USA", 1920)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.4)  # Positive growth → above midpoint
        self.assertLess(score, 1.0)

    def test_economic_diversity_proxy(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # High GDP per capita → high complexity score
        gdp_series = self._make_annual_series(1900, 1950, values=[30000.0] * 51)
        provider._cache["maddison_USA"] = gdp_series

        score = provider.get_economic_diversity_proxy("USA", 1920)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.5)

    def test_cbi_proxy_pre_1913_us(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # US before 1913 had no central bank → CBI should be 0.0
        score = provider.get_cbi_proxy("USA", 1900)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 0.0)

    def test_cbi_proxy_pre_1913_uk(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # UK had BoE → moderate CBI
        score = provider.get_cbi_proxy("GBR", 1900)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.0)

    def test_hdi_proxy_from_mocks(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Mock GDP and suffrage
        gdp_series = self._make_annual_series(1900, 1950, values=[20000.0] * 51)
        suffrage_series = self._make_annual_series(1900, 1950, values=[0.6] * 51)

        provider._cache["maddison_USA"] = gdp_series
        provider._cache["vdem_suffrage_USA"] = suffrage_series

        score = provider.get_hdi_proxy("USA", 1920)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.3)
        self.assertLess(score, 1.0)

    def test_unemployment_score_normalisation(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # 3% unemployment → score ≈ 1.0 (high resilience)
        unemp_series = self._make_annual_series(1920, 1940, values=[3.0] * 21)
        provider._cache["unemp_USA"] = unemp_series

        score = provider.get_unemployment_score("USA", 1930)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 1.0, places=1)

        # 20% unemployment → score ≈ 0.0 (low resilience)
        unemp_high = self._make_annual_series(1920, 1940, values=[20.0] * 21)
        provider._cache["unemp_GBR"] = unemp_high

        score_low = provider.get_unemployment_score("GBR", 1930)
        self.assertIsNotNone(score_low)
        self.assertAlmostEqual(score_low, 0.0, places=1)

    def test_disaster_risk_no_data(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()
        # With no EM-DAT file, should return None
        score = provider.get_disaster_risk("USA", 1950)
        self.assertTrue(score is None or isinstance(score, float))

    def test_climate_anomaly_score_with_mock(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Linear warming: 0°C in 1900, +1°C in 1960
        temps = np.linspace(-0.5, 0.5, 61)
        hadcrut_series = self._make_annual_series(1900, 1960, values=temps)
        provider._cache["hadcrut"] = hadcrut_series

        # At 1960: current = 0.5, baseline (1930) ≈ 0.0, delta ≈ 0.5
        # Score = 0.5 / 2.0 = 0.25
        score = provider.get_climate_anomaly_score(1960)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.1)
        self.assertLess(score, 0.5)


class TestGRRIHistoricalProviderComposite(unittest.TestCase):
    """Test composite GRRI scoring."""

    def _make_annual_series(self, start_year, end_year, values=None):
        years = range(start_year, end_year + 1)
        dates = [datetime(y, 7, 1) for y in years]
        if values is None:
            values = np.linspace(0.3, 0.8, len(dates))
        return pd.Series(values, index=dates, dtype=float)

    def test_composite_grri_with_mocked_pillars(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Mock all pillars
        provider._cache["polity5_USA"] = self._make_annual_series(
            1900, 1950, values=[8.0] * 51  # Strong democracy
        )
        provider._cache["vdem_polyarchy_USA"] = self._make_annual_series(
            1900, 1950, values=[0.85] * 51
        )
        provider._cache["vdem_civlib_USA"] = self._make_annual_series(
            1900, 1950, values=[0.80] * 51
        )
        provider._cache["maddison_USA"] = self._make_annual_series(
            1900, 1950, values=np.linspace(8000, 15000, 51)
        )
        provider._cache["vdem_suffrage_USA"] = self._make_annual_series(
            1900, 1950, values=[0.5] * 51  # Pre-universal suffrage
        )
        hadcrut = self._make_annual_series(1880, 1960, values=np.linspace(-0.3, 0.3, 81))
        provider._cache["hadcrut"] = hadcrut

        result = provider.get_historical_grri("USA", 1920)
        self.assertIsNotNone(result)
        self.assertIn("resilience", result)
        self.assertIn("modifier", result)
        self.assertIn("pillar_scores", result)
        self.assertIn("provenance", result)

        # Strong democracy + growing GDP → resilience > 0.5
        self.assertGreater(result["resilience"], 0.5)
        # Which means modifier < 1.0 (shock compression)
        self.assertLess(result["modifier"], 1.0)

    def test_composite_grri_fragile_state(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Mock a fragile state
        provider._cache["polity5_ARG"] = self._make_annual_series(
            1900, 1950, values=[-5.0] * 51  # Autocratic
        )
        provider._cache["maddison_ARG"] = self._make_annual_series(
            1900, 1950, values=np.linspace(3000, 2500, 51)  # Declining
        )

        result = provider.get_historical_grri("ARG", 1930)
        self.assertIsNotNone(result)
        # Weak democracy + declining GDP → resilience < 0.5
        self.assertLess(result["resilience"], 0.5)
        # Modifier > 1.0 (shock amplification)
        self.assertGreater(result["modifier"], 1.0)

    def test_insufficient_data_returns_none(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()
        # No data at all → should return None (need at least 2 pillars)
        result = provider.get_historical_grri("ZZZ", 1850)
        self.assertIsNone(result)

    def test_timeseries_generation(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()

        # Mock minimal data
        provider._cache["polity5_GBR"] = self._make_annual_series(
            1850, 1950, values=np.linspace(4, 10, 101)
        )
        provider._cache["maddison_GBR"] = self._make_annual_series(
            1850, 1950, values=np.linspace(3000, 8000, 101)
        )

        df = provider.get_historical_grri_timeseries("GBR", 1860, 1940)
        self.assertIsInstance(df, pd.DataFrame)
        if not df.empty:
            self.assertIn("year", df.columns)
            self.assertIn("resilience", df.columns)
            self.assertIn("modifier", df.columns)

    def test_data_availability_summary(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider

        provider = GRRIHistoricalProvider()
        summary = provider.get_data_availability_summary()

        # Should report all expected sources
        expected_sources = [
            "polity5", "vdem", "cow", "maddison", "reinhart_rogoff",
            "emdat", "hadcrut", "garriga_cbi", "gsdb", "ucdp",
            "historical_unemployment",
        ]
        for source in expected_sources:
            self.assertIn(source, summary, f"Missing source: {source}")
            self.assertIn("available", summary[source])
            self.assertIn("path", summary[source])
            self.assertIn("coverage", summary[source])
            self.assertIn("pillar", summary[source])


class TestGRRIProxyChains(unittest.TestCase):
    """Test proxy chain documentation completeness."""

    def test_all_pillars_have_chains(self):
        from grri_mac.grri.historical_proxies import GRRI_PROXY_CHAINS
        for pillar in ("political", "economic", "social", "environmental"):
            self.assertIn(pillar, GRRI_PROXY_CHAINS)
            self.assertGreater(len(GRRI_PROXY_CHAINS[pillar]), 0)

    def test_proxy_configs_have_required_fields(self):
        from grri_mac.grri.historical_proxies import GRRI_PROXY_CHAINS
        for pillar, indicators in GRRI_PROXY_CHAINS.items():
            for indicator, chain in indicators.items():
                for proxy in chain:
                    self.assertTrue(proxy.target_indicator, f"Missing target: {pillar}/{indicator}")
                    self.assertTrue(proxy.proxy_series, f"Missing proxy: {pillar}/{indicator}")
                    self.assertTrue(proxy.source, f"Missing source: {pillar}/{indicator}")
                    self.assertTrue(proxy.start_date, f"Missing start: {pillar}/{indicator}")
                    self.assertGreater(proxy.correlation_estimate, 0)
                    self.assertLessEqual(proxy.correlation_estimate, 1.0)
                    self.assertTrue(proxy.academic_reference, f"Missing ref: {pillar}/{indicator}")

    def test_coverage_table_generation(self):
        from grri_mac.grri.historical_proxies import get_proxy_coverage_table
        table = get_proxy_coverage_table()
        self.assertIsInstance(table, str)
        self.assertIn("POLITICAL PILLAR", table)
        self.assertIn("ECONOMIC PILLAR", table)
        self.assertIn("SOCIAL PILLAR", table)
        self.assertIn("ENVIRONMENTAL PILLAR", table)

    def test_required_files_listing(self):
        from grri_mac.grri.historical_proxies import get_all_required_files
        files = get_all_required_files()
        self.assertIsInstance(files, dict)
        self.assertGreater(len(files), 5)
        # Each entry should have a download instruction
        for path, desc in files.items():
            self.assertIn("data/historical/grri/", path)
            self.assertGreater(len(desc), 10)


class TestGRRIModifierIntegration(unittest.TestCase):
    """Test that historical GRRI scores integrate with the modifier system."""

    def test_modifier_from_historical_score(self):
        from grri_mac.grri.modifier import grri_to_modifier

        # High resilience → low modifier
        self.assertLess(grri_to_modifier(0.8), 1.0)
        # Low resilience → high modifier
        self.assertGreater(grri_to_modifier(0.2), 1.0)
        # Midpoint → neutral
        self.assertAlmostEqual(grri_to_modifier(0.5), 1.0, places=1)

    def test_historical_grri_uses_correct_modifier(self):
        from grri_mac.grri.historical_sources import GRRIHistoricalProvider
        from grri_mac.grri.modifier import grri_to_modifier

        provider = GRRIHistoricalProvider()

        # Build mocks for high-resilience state
        years = range(1900, 1951)
        dates = [datetime(y, 7, 1) for y in years]

        provider._cache["polity5_USA"] = pd.Series(
            [10.0] * 51, index=dates, dtype=float
        )
        provider._cache["maddison_USA"] = pd.Series(
            np.linspace(8000, 15000, 51), index=dates, dtype=float
        )

        result = provider.get_historical_grri("USA", 1930)
        if result is not None:
            # Verify modifier matches what grri_to_modifier would produce
            expected_modifier = grri_to_modifier(result["resilience"])
            self.assertAlmostEqual(
                result["modifier"], round(expected_modifier, 4), places=3
            )


class TestConflictIntensity(unittest.TestCase):
    """Test conflict intensity scoring."""

    def test_no_conflicts_returns_zero(self):
        from grri_mac.grri.historical_sources import get_conflict_intensity

        # With no COW data file, should return None or 0
        result = get_conflict_intensity("CHE", 1900)  # Switzerland, neutral
        self.assertTrue(result is None or result == 0.0)

    def test_crisis_count_no_data(self):
        from grri_mac.grri.historical_sources import get_crisis_count
        count = get_crisis_count("USA", 1907, window=5)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class TestSanctionsCount(unittest.TestCase):
    """Test sanctions counting."""

    def test_no_data_returns_zero(self):
        from grri_mac.grri.historical_sources import get_sanctions_count
        count = get_sanctions_count("IRN", 2000)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
