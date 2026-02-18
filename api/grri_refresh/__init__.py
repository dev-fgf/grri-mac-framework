"""
GRRI Data Refresh Endpoint - Fetch data from external sources and store in Azure Tables.

This endpoint is called by GitHub Actions to refresh GRRI data for the GRS Tracker.
Sources include:
- IMF WEO (Economic indicators)
- World Bank WGI (Governance indicators)
- UNDP HDI (Human development)
- V-Dem (Democracy indicators)
"""

import json
import sys
import os
from datetime import datetime
import azure.functions as func
import logging

# Add shared module path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import get_database
from shared.health_registry import (
    validate_source, make_down_report, record_health,
)

logger = logging.getLogger(__name__)

# G20 countries ISO3 codes
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
    "MEX": "Mexico",
    "RUS": "Russia",
    "SAU": "Saudi Arabia",
    "ZAF": "South Africa",
    "KOR": "South Korea",
    "TUR": "Turkey",
    "GBR": "United Kingdom",
    "USA": "United States",
}

# Extended countries
EXTENDED_COUNTRIES = {
    "EGY": "Egypt",
    "NGA": "Nigeria",
    "POL": "Poland",
    "THA": "Thailand",
    "VNM": "Vietnam",
    "ARE": "UAE",
    "MYS": "Malaysia",
    "PHL": "Philippines",
    "PAK": "Pakistan",
    "IRN": "Iran",
}

# ISO3 to ISO2 mapping for World Bank API (uses 2-letter codes)
ISO3_TO_ISO2 = {
    'ARG': 'AR', 'AUS': 'AU', 'BRA': 'BR', 'CAN': 'CA', 'CHN': 'CN',
    'FRA': 'FR', 'DEU': 'DE', 'IND': 'IN', 'IDN': 'ID', 'ITA': 'IT',
    'JPN': 'JP', 'MEX': 'MX', 'RUS': 'RU', 'SAU': 'SA', 'ZAF': 'ZA',
    'KOR': 'KR', 'TUR': 'TR', 'GBR': 'GB', 'USA': 'US',
    # Extended countries
    'EGY': 'EG', 'NGA': 'NG', 'POL': 'PL', 'THA': 'TH', 'VNM': 'VN',
    'ARE': 'AE', 'MYS': 'MY', 'PHL': 'PH', 'PAK': 'PK', 'IRN': 'IR',
}
ISO2_TO_ISO3 = {v: k for k, v in ISO3_TO_ISO2.items()}


def fetch_imf_weo_data() -> dict:
    """Fetch economic indicators from IMF WEO DataMapper API."""
    import requests
    
    BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
    
    indicators = {
        "inflation": "PCPIPCH",
        "fiscal_balance": "GGXCNL_NGDP",
        "current_account": "BCA_NGDPD",
        "gdp_growth": "NGDP_RPCH",
        "unemployment": "LUR",
    }
    
    result = {
        "source": "IMF_WEO",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "success",
        "indicators": {},
        "errors": []
    }
    
    countries = list(G20_COUNTRIES.keys())
    
    for name, code in indicators.items():
        try:
            url = f"{BASE_URL}/indicators/{code}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            values_data = data.get("values", {}).get(code, {})
            
            indicator_data = {}
            for country in countries:
                if country in values_data:
                    # Get last 5 years
                    country_values = {}
                    for year, value in values_data[country].items():
                        if int(year) >= 2019 and value is not None:
                            country_values[year] = float(value)
                    if country_values:
                        indicator_data[country] = country_values
            
            result["indicators"][name] = {
                "code": code,
                "countries": len(indicator_data),
                "data": indicator_data
            }
            
        except Exception as e:
            result["errors"].append(f"{name}: {str(e)}")
            logger.warning(f"IMF WEO {name} fetch failed: {e}")
    
    if result["errors"]:
        result["status"] = "partial"
    
    return result


def fetch_world_bank_wgi_data() -> dict:
    """Fetch governance indicators from World Bank API."""
    import requests
    
    BASE_URL = "https://api.worldbank.org/v2"
    
    indicators = {
        "rule_of_law": "RL.EST",
        "government_effectiveness": "GE.EST",
        "regulatory_quality": "RQ.EST",
        "political_stability": "PV.EST",
        "control_of_corruption": "CC.EST",
        "voice_accountability": "VA.EST",
    }
    
    result = {
        "source": "World_Bank_WGI",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "success",
        "indicators": {},
        "errors": []
    }
    
    # World Bank uses ISO2 codes
    countries_iso3 = list(G20_COUNTRIES.keys())
    countries_iso2 = [ISO3_TO_ISO2.get(c, c) for c in countries_iso3]
    countries_str = ";".join(countries_iso2)
    current_year = datetime.now().year
    
    for name, code in indicators.items():
        try:
            url = f"{BASE_URL}/country/{countries_str}/indicator/{code}"
            params = {
                "format": "json",
                "per_page": 500,
                "date": f"2018:{current_year}"
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if len(data) < 2 or not data[1]:
                result["errors"].append(f"{name}: No data returned")
                continue
            
            indicator_data = {}
            for record in data[1]:
                country_iso2 = record.get("country", {}).get("id")
                # Convert back to ISO3 for consistency with IMF data
                country = ISO2_TO_ISO3.get(country_iso2, country_iso2)
                year = record.get("date")
                value = record.get("value")
                
                if country and year and value is not None:
                    if country not in indicator_data:
                        indicator_data[country] = {}
                    indicator_data[country][year] = float(value)
            
            result["indicators"][name] = {
                "code": code,
                "countries": len(indicator_data),
                "data": indicator_data
            }
            
        except Exception as e:
            result["errors"].append(f"{name}: {str(e)}")
            logger.warning(f"World Bank WGI {name} fetch failed: {e}")
    
    if result["errors"]:
        result["status"] = "partial"
    
    return result


def calculate_pillar_scores(imf_data: dict, wgi_data: dict) -> dict:
    """
    Calculate GRRI pillar scores from raw indicator data.
    
    Normalization: Min-max scaling where higher = higher risk
    """
    scores = {}
    current_year = str(datetime.now().year - 1)  # Most recent complete year
    
    for country_code, country_name in G20_COUNTRIES.items():
        country_scores = {
            "country_code": country_code,
            "country_name": country_name,
            "year": int(current_year),
            "quarter": "Q4",
            "timestamp": datetime.utcnow().isoformat(),
            "data_source": "IMF_WEO,World_Bank_WGI",
        }
        
        # === Political Pillar (from WGI) ===
        political_raw = []
        wgi_indicators = wgi_data.get("indicators", {})
        
        for ind_name in ["rule_of_law", "government_effectiveness", "regulatory_quality", 
                         "political_stability", "control_of_corruption"]:
            ind_data = wgi_indicators.get(ind_name, {}).get("data", {})
            country_ind = ind_data.get(country_code, {})
            # Get most recent year available
            for year in sorted(country_ind.keys(), reverse=True):
                if country_ind[year] is not None:
                    # WGI scale is -2.5 to 2.5, higher = better
                    # Convert to 0-100 risk scale (higher = more risk)
                    raw_value = country_ind[year]
                    # Normalize: (-2.5 to 2.5) -> (100 to 0)
                    risk_score = 50 - (raw_value * 20)  # Invert and scale
                    risk_score = max(0, min(100, risk_score))
                    political_raw.append(risk_score)
                    break
        
        if political_raw:
            country_scores["political_score"] = round(sum(political_raw) / len(political_raw), 2)
        
        # === Economic Pillar (from IMF WEO) ===
        economic_raw = []
        imf_indicators = imf_data.get("indicators", {})
        
        # Inflation risk (higher inflation = higher risk)
        inflation_data = imf_indicators.get("inflation", {}).get("data", {}).get(country_code, {})
        for year in sorted(inflation_data.keys(), reverse=True):
            if inflation_data[year] is not None:
                # Scale: 2% optimal, >10% high risk
                inf_val = inflation_data[year]
                if inf_val < 0:
                    risk = 60  # Deflation risk
                elif inf_val <= 2:
                    risk = 20
                elif inf_val <= 5:
                    risk = 30 + (inf_val - 2) * 10
                elif inf_val <= 10:
                    risk = 60 + (inf_val - 5) * 6
                else:
                    risk = min(100, 90 + inf_val - 10)
                economic_raw.append(risk)
                break
        
        # Fiscal balance risk (larger deficit = higher risk)
        fiscal_data = imf_indicators.get("fiscal_balance", {}).get("data", {}).get(country_code, {})
        for year in sorted(fiscal_data.keys(), reverse=True):
            if fiscal_data[year] is not None:
                # Scale: -3% to +3% is healthy
                fiscal_val = fiscal_data[year]
                if fiscal_val >= 0:
                    risk = 20  # Surplus is low risk
                elif fiscal_val >= -3:
                    risk = 30
                elif fiscal_val >= -6:
                    risk = 50 + abs(fiscal_val + 3) * 10
                else:
                    risk = min(100, 80 + abs(fiscal_val + 6) * 5)
                economic_raw.append(risk)
                break
        
        # GDP growth (negative growth = higher risk)
        gdp_data = imf_indicators.get("gdp_growth", {}).get("data", {}).get(country_code, {})
        for year in sorted(gdp_data.keys(), reverse=True):
            if gdp_data[year] is not None:
                gdp_val = gdp_data[year]
                if gdp_val >= 3:
                    risk = 20
                elif gdp_val >= 1:
                    risk = 40
                elif gdp_val >= 0:
                    risk = 60
                else:
                    risk = min(100, 70 + abs(gdp_val) * 10)
                economic_raw.append(risk)
                break
        
        # Unemployment (higher = higher risk)
        unemp_data = imf_indicators.get("unemployment", {}).get("data", {}).get(country_code, {})
        for year in sorted(unemp_data.keys(), reverse=True):
            if unemp_data[year] is not None:
                unemp_val = unemp_data[year]
                if unemp_val <= 4:
                    risk = 20
                elif unemp_val <= 6:
                    risk = 30
                elif unemp_val <= 10:
                    risk = 40 + (unemp_val - 6) * 10
                else:
                    risk = min(100, 80 + (unemp_val - 10) * 2)
                economic_raw.append(risk)
                break
        
        if economic_raw:
            country_scores["economic_score"] = round(sum(economic_raw) / len(economic_raw), 2)
        
        # === Social & Environmental Pillars ===
        # These require additional data sources (UNDP, EM-DAT, etc.)
        # For now, estimate from available data or set to None
        country_scores["social_score"] = None  # Requires HDI, UNHCR, V-Dem data
        country_scores["environmental_score"] = None  # Requires EM-DAT, IMF climate data
        
        # === Composite Score ===
        available_scores = [v for k, v in country_scores.items() 
                          if k.endswith("_score") and v is not None]
        if available_scores:
            country_scores["composite_score"] = round(sum(available_scores) / len(available_scores), 2)
        else:
            country_scores["composite_score"] = None
        
        scores[country_code] = country_scores
    
    return scores


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Refresh GRRI data from external sources and store in Azure Tables.
    
    Called by GitHub Actions (quarterly schedule or manual trigger).
    """
    start_time = datetime.utcnow()
    db = get_database()
    
    result = {
        "timestamp": start_time.isoformat(),
        "sources": {},
        "scores_calculated": 0,
        "scores_saved": 0,
        "success": True,
    }
    
    # === Fetch IMF WEO Data ===
    logger.info("Fetching IMF WEO data...")
    import time as _time
    _t = _time.time()
    try:
        imf_data = fetch_imf_weo_data()
        result["sources"]["IMF_WEO"] = {
            "status": imf_data.get("status"),
            "indicators": len(imf_data.get("indicators", {})),
            "errors": imf_data.get("errors", [])
        }
        imf_inds = imf_data.get("indicators", {})
        flat = {}
        for code, countries in imf_inds.items():
            if countries:
                flat[f"weo_{code}"] = len(countries)
        report = validate_source("IMF_WEO", flat)
        report["latency_ms"] = int((_time.time() - _t) * 1000)
        record_health(db, "IMF_WEO", report)
    except Exception as e:
        logger.error(f"IMF WEO fetch failed: {e}")
        imf_data = {"indicators": {}}
        result["sources"]["IMF_WEO"] = {"status": "error", "error": str(e)}
        result["success"] = False
        try:
            record_health(db, "IMF_WEO", make_down_report("IMF_WEO", str(e)))
        except Exception:
            pass

    # === Fetch World Bank WGI Data ===
    logger.info("Fetching World Bank WGI data...")
    _t = _time.time()
    try:
        wgi_data = fetch_world_bank_wgi_data()
        result["sources"]["World_Bank_WGI"] = {
            "status": wgi_data.get("status"),
            "indicators": len(wgi_data.get("indicators", {})),
            "errors": wgi_data.get("errors", [])
        }
        wgi_inds = wgi_data.get("indicators", {})
        flat = {}
        for code, countries in wgi_inds.items():
            if countries:
                flat[code] = len(countries)
        report = validate_source("WORLD_BANK", flat)
        report["latency_ms"] = int((_time.time() - _t) * 1000)
        record_health(db, "WORLD_BANK", report)
    except Exception as e:
        logger.error(f"World Bank WGI fetch failed: {e}")
        wgi_data = {"indicators": {}}
        result["sources"]["World_Bank_WGI"] = {"status": "error", "error": str(e)}
        result["success"] = False
        try:
            record_health(db, "WORLD_BANK", make_down_report("WORLD_BANK", str(e)))
        except Exception:
            pass
    
    # === Calculate GRRI Scores ===
    logger.info("Calculating GRRI scores...")
    try:
        scores = calculate_pillar_scores(imf_data, wgi_data)
        result["scores_calculated"] = len(scores)
        
        # === Save to Azure Tables ===
        if db.connected:
            saved = 0
            for country_code, country_scores in scores.items():
                if db.save_grri_record(country_scores):
                    saved += 1
            result["scores_saved"] = saved
            logger.info(f"Saved {saved} GRRI scores to Azure Tables")
        else:
            result["db_connected"] = False
            logger.warning("Database not connected - scores not persisted")
            
    except Exception as e:
        logger.error(f"Score calculation failed: {e}")
        result["calculation_error"] = str(e)
        result["success"] = False
    
    # === Summary ===
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    result["elapsed_seconds"] = round(elapsed, 2)
    
    # Include sample scores in response
    result["sample_scores"] = {
        country: scores[country] 
        for country in list(scores.keys())[:3]
    } if scores else {}
    
    status_code = 200 if result["success"] else 207
    
    return func.HttpResponse(
        json.dumps(result, indent=2),
        status_code=status_code,
        mimetype="application/json"
    )
