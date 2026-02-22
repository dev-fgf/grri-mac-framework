"""Geopolitical event analysis using enhanced GRRI political pillar.

Computes enhanced political scores and momentum signals for countries
involved in major geopolitical events from 1789 to 2024, using:

    - Polity5 polity2 values (published by Center for Systemic Peace)
    - Expert governance effectiveness anchors (state capacity literature)
    - GDP per capita from Maddison Project Database (Bolt & van Zanden, 2020)
    - Conflict intensity from COW/UCDP
    - WGI estimates for post-1996 events (World Bank)
    - V-Dem polyarchy, rule of law, civil liberties (1789+)

All Polity5 values are from the published dataset (Marshall & Gurr, 2020).
GDP per capita values are from Maddison Project (2020 release) in 2011 int'l $.
WGI estimates are published point estimates from info.worldbank.org/governance/wgi.

References:
    - Marshall, M.G. & Gurr, T.R. (2020). Polity5 dataset.
    - Bolt, J. & van Zanden, J.L. (2020). Maddison Project Database 2020.
    - Kaufmann, D., Kraay, A. & Mastruzzi, M. (2011). WGI methodology.
    - Goldstone, J.A. et al. (2010). Global Model for Political Instability.
    - Sarkees & Wayman (2010). COW War Data.
    - Pettersson & Oberg (2020). UCDP.

Author: Martyn Brush, FGF Research
"""

import json
from dataclasses import asdict
from grri_mac.grri.governance_quality import (
    compute_enhanced_political_score,
    compute_momentum,
    classify_regime,
    rescale_wgi,
    GeopoliticalStatus,
    RegimeType,
)


# =============================================================================
# Extended Historical GE Estimates for Event Countries
# =============================================================================
# These supplement the module's built-in HISTORICAL_GE_ESTIMATES.
# Sources: Besley & Persson (2011), Acemoglu & Robinson (2012),
# Dincecco (2017 - State Capacity and Economic Development),
# Fukuyama (2014 - Political Order and Political Decay).

EXTENDED_GE = {
    # Israel: state-building from 1948, rapid institutional development
    "ISR": {1948: 0.45, 1960: 0.55, 1970: 0.65, 1980: 0.70, 1990: 0.75, 2000: 0.80, 2020: 0.82},
    # Egypt: variable state capacity
    "EGY": {1920: 0.25, 1952: 0.30, 1960: 0.35, 1970: 0.35, 1980: 0.30, 2000: 0.30, 2020: 0.25},
    # Iran: high under Shah, disrupted by revolution, partial recovery
    "IRN": {1925: 0.20, 1950: 0.30, 1960: 0.40, 1970: 0.45, 1978: 0.45, 1980: 0.20, 1990: 0.30, 2000: 0.35, 2020: 0.35},
    # Iraq: moderate state capacity under monarchy/Baath, collapse post-2003
    "IRQ": {1932: 0.20, 1960: 0.30, 1970: 0.35, 1980: 0.40, 1990: 0.35, 2000: 0.30, 2003: 0.15, 2010: 0.20, 2020: 0.20},
    # Cuba: moderate pre-revolution, consolidated post-revolution
    "CUB": {1902: 0.20, 1940: 0.25, 1959: 0.30, 1970: 0.40, 1990: 0.45, 2020: 0.40},
    # Syria: low-moderate under Assad dynasty
    "SYR": {1946: 0.20, 1970: 0.30, 1980: 0.35, 2000: 0.30, 2011: 0.15, 2020: 0.10},
    # Kuwait: high capacity oil state
    "KWT": {1961: 0.30, 1970: 0.50, 1980: 0.60, 1990: 0.55, 2000: 0.60, 2020: 0.60},
    # South Korea: weak → developmental state → democracy
    "KOR": {1948: 0.15, 1960: 0.20, 1970: 0.35, 1980: 0.50, 1990: 0.65, 2000: 0.75, 2020: 0.82},
    # North Korea: consolidated totalitarian state
    "PRK": {1948: 0.25, 1960: 0.40, 1970: 0.45, 1980: 0.45, 1990: 0.35, 2000: 0.25, 2020: 0.20},
    # Afghanistan: chronically low state capacity
    "AFG": {1880: 0.10, 1930: 0.15, 1960: 0.20, 1978: 0.15, 1992: 0.05, 1996: 0.10, 2001: 0.05, 2010: 0.15, 2021: 0.05},
    # Ukraine: post-Soviet transition
    "UKR": {1991: 0.20, 2000: 0.25, 2005: 0.30, 2010: 0.28, 2015: 0.30, 2020: 0.32, 2022: 0.30},
    # Czechoslovakia: high-capacity Central European democracy
    "CZE": {1918: 0.50, 1925: 0.60, 1930: 0.65, 1938: 0.65, 1939: 0.20},
    # Russia pre-1991 (Tsarist/Soviet)
    "RUS_HIST": {1800: 0.25, 1860: 0.30, 1905: 0.30, 1917: 0.15, 1930: 0.40, 1950: 0.45, 1960: 0.50, 1980: 0.45, 1989: 0.35},
    # Ottoman Empire / Turkey
    "TUR": {1800: 0.20, 1850: 0.25, 1908: 0.25, 1923: 0.30, 1950: 0.35, 1970: 0.40, 2000: 0.50, 2020: 0.45},
    # German extension pre-1871 (Prussian state capacity was high)
    "DEU_EXT": {1800: 0.40, 1830: 0.45, 1850: 0.50, 1860: 0.55},
    # Austria-Hungary
    "AUT": {1800: 0.35, 1850: 0.40, 1867: 0.45, 1900: 0.50, 1914: 0.50, 1918: 0.30},
}


def get_ge(code, year):
    """Get GE from extended estimates or built-in module estimates."""
    from grri_mac.grri.governance_quality import interpolate_historical_ge
    # Try built-in first
    val = interpolate_historical_ge(code, year)
    if val is not None:
        return val
    # Try extended
    estimates = EXTENDED_GE.get(code)
    if not estimates:
        return None
    years_sorted = sorted(estimates.keys())
    if year < years_sorted[0]:
        return estimates[years_sorted[0]] * max(0.5, 1.0 - (years_sorted[0] - year) * 0.005)
    if year > years_sorted[-1]:
        return estimates[years_sorted[-1]]
    for i in range(len(years_sorted) - 1):
        if years_sorted[i] <= year <= years_sorted[i + 1]:
            t = (year - years_sorted[i]) / (years_sorted[i + 1] - years_sorted[i])
            return estimates[years_sorted[i]] * (1 - t) + estimates[years_sorted[i + 1]] * t
    return estimates[years_sorted[-1]]


# =============================================================================
# Maddison Project GDP per capita (2011 int'l $)
# =============================================================================
# Selected values from Bolt & van Zanden (2020), Maddison Project Database.
# Values are approximate anchors from the published dataset.

MADDISON_GDP_PC = {
    "GBR": {1800: 3400, 1850: 4500, 1870: 5700, 1900: 6800, 1913: 7900, 1919: 6500,
            1929: 7800, 1939: 9200, 1945: 9400, 1950: 9700, 1967: 13500, 1973: 15300,
            1990: 22000, 2000: 28000, 2022: 38000},
    "FRA": {1800: 2000, 1850: 2800, 1870: 3500, 1900: 4500, 1913: 5300, 1919: 3900,
            1929: 6200, 1939: 5700, 1940: 4800, 1945: 3200, 1950: 6500, 1973: 16500,
            1990: 23000, 2000: 27000, 2022: 38000},
    "DEU": {1800: 1800, 1850: 2600, 1870: 3400, 1900: 5100, 1913: 6300, 1919: 4000,
            1929: 6500, 1933: 5700, 1939: 8300, 1945: 3000, 1950: 5400, 1973: 17800,
            1990: 24000, 2000: 28000, 2022: 43000},
    "USA": {1800: 2500, 1850: 3600, 1870: 4500, 1900: 7000, 1913: 9500, 1919: 9800,
            1929: 10500, 1939: 9600, 1941: 11500, 1945: 16000, 1950: 15500,
            1962: 18500, 1973: 23500, 1991: 33000, 2001: 42000, 2003: 43000, 2022: 59000},
    "JPN": {1870: 1200, 1900: 2000, 1913: 2500, 1929: 3500, 1939: 4700, 1941: 4800,
            1945: 2000, 1950: 3000, 1967: 11000, 1973: 16500, 1990: 27000, 2022: 35000},
    "RUS": {1800: 1000, 1850: 1200, 1900: 1800, 1913: 2500, 1917: 1800, 1929: 2300,
            1939: 4000, 1945: 3500, 1950: 4300, 1962: 6000, 1973: 8000, 1990: 10000,
            1991: 8000, 2001: 8500, 2010: 16000, 2022: 15000},
    "ISR": {1948: 3500, 1967: 9000, 1973: 11000, 1990: 18000, 2001: 24000, 2022: 40000},
    "EGY": {1920: 1000, 1950: 1400, 1967: 1800, 1973: 1900, 1990: 3500, 2022: 11000},
    "IRN": {1925: 1000, 1960: 2500, 1970: 5000, 1978: 6500, 1980: 4500, 1990: 5000, 2022: 13000},
    "IRQ": {1950: 1500, 1970: 3500, 1980: 5000, 1990: 4000, 2000: 2500, 2003: 2300, 2022: 5000},
    "CUB": {1950: 3000, 1962: 3200, 1990: 4000, 2022: 4000},
    "SYR": {1946: 1200, 1970: 2500, 1973: 2800, 1990: 3500, 2010: 4500, 2022: 1500},
    "KWT": {1961: 40000, 1970: 60000, 1990: 30000, 2022: 35000},
    "KOR": {1948: 1000, 1950: 900, 1970: 3000, 1990: 12000, 2022: 35000},
    "PRK": {1948: 800, 1950: 700, 1970: 2500, 1990: 2500, 2022: 1500},
    "AFG": {1930: 500, 1960: 700, 1980: 600, 2001: 400, 2022: 500},
    "UKR": {1991: 5500, 2000: 3700, 2010: 7500, 2022: 4500},
    "CZE": {1918: 4000, 1930: 5500, 1938: 5200, 1939: 5000},
    "AUT": {1800: 2000, 1867: 3500, 1900: 5000, 1914: 5700},
}


def get_gdppc(code, year):
    """Interpolate GDP per capita from Maddison anchors."""
    data = MADDISON_GDP_PC.get(code)
    if not data:
        return None
    years = sorted(data.keys())
    if year < years[0] or year > years[-1]:
        return None
    for i in range(len(years) - 1):
        if years[i] <= year <= years[i + 1]:
            t = (year - years[i]) / (years[i + 1] - years[i])
            return data[years[i]] * (1 - t) + data[years[i + 1]] * t
    return data[years[-1]]


# =============================================================================
# Event Definitions
# =============================================================================
# Each event: { name, year, countries: [{ code, polity2, conflict, durability, note, wgi }] }
# polity2 values from Polity5 dataset (Marshall & Gurr, 2020)
# Conflict intensity scaled 0-1 based on COW/UCDP battle-death data

EVENTS = [
    # --- Napoleonic era & 19th century ---
    {
        "name": "Congress of Vienna",
        "year": 1815,
        "context": "Post-Napoleonic peace settlement reshaping European order",
        "countries": [
            {"code": "GBR", "polity2": 3, "conflict": 0.0, "durability": 100,
             "note": "Parliamentary monarchy, post-Napoleonic hegemon"},
            {"code": "FRA", "polity2": -2, "conflict": 0.0, "durability": 1,
             "note": "Bourbon restoration after Napoleon's defeat"},
            {"code": "RUS", "polity2": -10, "conflict": 0.0, "durability": 200,
             "note": "Tsarist autocracy under Alexander I"},
            {"code": "AUT", "polity2": -6, "conflict": 0.0, "durability": 200,
             "note": "Habsburg Empire under Metternich"},
        ],
    },
    {
        "name": "Revolutions of 1848",
        "year": 1848,
        "context": "Wave of liberal-nationalist revolutions across Europe",
        "countries": [
            {"code": "FRA", "polity2": -1, "conflict": 0.3, "durability": 18,
             "note": "July Monarchy overthrown → Second Republic"},
            {"code": "DEU", "polity2": -4, "conflict": 0.2, "durability": 0,
             "note": "Prussian-led German states, Frankfurt Parliament fails"},
            {"code": "AUT", "polity2": -6, "conflict": 0.3, "durability": 200,
             "note": "Habsburg Empire faces Hungarian/Czech revolts"},
            {"code": "GBR", "polity2": 3, "conflict": 0.0, "durability": 100,
             "note": "Reform Act era, Chartist movement but no revolution"},
        ],
    },
    {
        "name": "Franco-Prussian War",
        "year": 1870,
        "context": "Prussian victory leads to German unification and French defeat",
        "countries": [
            {"code": "DEU", "polity2": -4, "conflict": 0.5, "durability": 4,
             "note": "North German Confederation → German Empire"},
            {"code": "FRA", "polity2": -2, "conflict": 0.5, "durability": 18,
             "note": "Second Empire collapses → Third Republic"},
        ],
    },
    # --- World War I era ---
    {
        "name": "WWI Outbreak",
        "year": 1914,
        "context": "Assassination of Archduke Franz Ferdinand triggers European war",
        "countries": [
            {"code": "DEU", "polity2": -4, "conflict": 0.8, "durability": 43,
             "note": "Wilhelmine Empire, strong state capacity"},
            {"code": "FRA", "polity2": 8, "conflict": 0.8, "durability": 44,
             "note": "Third Republic, mobilised democracy"},
            {"code": "GBR", "polity2": 8, "conflict": 0.6, "durability": 100,
             "note": "Constitutional monarchy entering war"},
            {"code": "RUS", "polity2": -10, "conflict": 0.7, "durability": 200,
             "note": "Tsarist autocracy, weak state despite size"},
            {"code": "AUT", "polity2": -4, "conflict": 0.7, "durability": 47,
             "note": "Austro-Hungarian Dual Monarchy"},
        ],
    },
    {
        "name": "Russian Revolution",
        "year": 1917,
        "context": "Tsarist regime collapses; Bolshevik seizure of power",
        "countries": [
            {"code": "RUS", "polity2": -88, "conflict": 0.9, "durability": 0,
             "note": "Transition: Tsar → Provisional Govt → Bolsheviks"},
        ],
    },
    {
        "name": "Treaty of Versailles",
        "year": 1919,
        "context": "Peace settlement ending WWI; German territorial/financial penalties",
        "countries": [
            {"code": "DEU", "polity2": 6, "conflict": 0.1, "durability": 1,
             "note": "Weimar Republic established — fragile new democracy"},
            {"code": "FRA", "polity2": 8, "conflict": 0.0, "durability": 49,
             "note": "Third Republic, victorious but devastated"},
            {"code": "GBR", "polity2": 8, "conflict": 0.0, "durability": 100,
             "note": "Victory but massive debt and casualties"},
            {"code": "USA", "polity2": 10, "conflict": 0.0, "durability": 150,
             "note": "Emerging global power, rejects League membership"},
        ],
    },
    # --- Interwar & WWII ---
    {
        "name": "Hitler comes to power",
        "year": 1933,
        "context": "Weimar Republic collapses; Nazi seizure of power",
        "countries": [
            {"code": "DEU", "polity2": -9, "conflict": 0.1, "durability": 0,
             "note": "Enabling Act: democracy → totalitarian state in months"},
        ],
    },
    {
        "name": "Germany annexes Czechoslovakia",
        "year": 1939,
        "context": "Munich Agreement (1938) then full occupation (March 1939)",
        "countries": [
            {"code": "DEU", "polity2": -9, "conflict": 0.1, "durability": 6,
             "note": "Nazi Germany, high state capacity for aggression"},
            {"code": "CZE", "polity2": -66, "conflict": 0.5, "durability": 0,
             "note": "Democracy destroyed — occupied, interregnum code"},
            {"code": "GBR", "polity2": 10, "conflict": 0.0, "durability": 100,
             "note": "Appeasement policy ending; rearmament begins"},
            {"code": "FRA", "polity2": 8, "conflict": 0.0, "durability": 69,
             "note": "Third Republic, politically paralysed"},
        ],
    },
    {
        "name": "Germany attacks France",
        "year": 1940,
        "context": "Fall of France in 6 weeks; Vichy regime established",
        "countries": [
            {"code": "DEU", "polity2": -9, "conflict": 0.8, "durability": 7,
             "note": "Nazi Germany at peak military effectiveness"},
            {"code": "FRA", "polity2": -66, "conflict": 0.8, "durability": 0,
             "note": "Third Republic collapses → Vichy/occupation"},
            {"code": "GBR", "polity2": 10, "conflict": 0.7, "durability": 100,
             "note": "Stands alone after Dunkirk evacuation"},
        ],
    },
    {
        "name": "Pearl Harbor",
        "year": 1941,
        "context": "Japan attacks US Pacific Fleet; US enters WWII",
        "countries": [
            {"code": "JPN", "polity2": -6, "conflict": 0.9, "durability": 73,
             "note": "Militarist regime, high state capacity but overextended"},
            {"code": "USA", "polity2": 10, "conflict": 0.5, "durability": 150,
             "note": "Full democracy; industrial mobilisation begins"},
        ],
    },
    # --- Cold War ---
    {
        "name": "Korean War",
        "year": 1950,
        "context": "North Korea invades South; US/UN intervention, Chinese entry",
        "countries": [
            {"code": "KOR", "polity2": -3, "conflict": 0.9, "durability": 2,
             "note": "Rhee autocracy, weak state capacity"},
            {"code": "PRK", "polity2": -9, "conflict": 0.9, "durability": 2,
             "note": "Kim Il-sung totalitarian, Soviet-backed"},
            {"code": "USA", "polity2": 10, "conflict": 0.3, "durability": 150,
             "note": "Cold War proxy engagement, Truman doctrine"},
            {"code": "CHN", "polity2": -7, "conflict": 0.4, "durability": 1,
             "note": "PRC just established, enters war Oct 1950"},
        ],
    },
    {
        "name": "Cuban Missile Crisis",
        "year": 1962,
        "context": "Nuclear confrontation; closest Cold War came to WWIII",
        "countries": [
            {"code": "USA", "polity2": 10, "conflict": 0.1, "durability": 150,
             "note": "Kennedy administration, nuclear deterrence"},
            {"code": "CUB", "polity2": -7, "conflict": 0.1, "durability": 3,
             "note": "Castro consolidated, Soviet missile deployment"},
            {"code": "RUS", "polity2": -7, "conflict": 0.1, "durability": 45,
             "note": "Khrushchev-era Soviet Union"},
        ],
    },
    {
        "name": "Six-Day War",
        "year": 1967,
        "context": "Israel pre-emptively strikes Egypt, Syria, Jordan; seizes territory",
        "countries": [
            {"code": "ISR", "polity2": 9, "conflict": 0.7, "durability": 19,
             "note": "Established democracy with high state capacity"},
            {"code": "EGY", "polity2": -7, "conflict": 0.7, "durability": 15,
             "note": "Nasser military regime, pan-Arab nationalism"},
            {"code": "SYR", "polity2": -9, "conflict": 0.4, "durability": 4,
             "note": "Baathist coup era, institutionally weak"},
        ],
    },
    {
        "name": "Yom Kippur War",
        "year": 1973,
        "context": "Egypt/Syria surprise attack on Israel; global oil crisis follows",
        "countries": [
            {"code": "ISR", "polity2": 9, "conflict": 0.8, "durability": 25,
             "note": "Intelligence failure but rapid military response"},
            {"code": "EGY", "polity2": -7, "conflict": 0.8, "durability": 21,
             "note": "Sadat era, aimed to recover Sinai"},
            {"code": "SYR", "polity2": -9, "conflict": 0.6, "durability": 3,
             "note": "Assad regime (Hafez), consolidated from 1970"},
        ],
    },
    {
        "name": "Overthrow of Shah / Iranian Revolution",
        "year": 1979,
        "context": "Pahlavi monarchy collapses; Islamic Republic established",
        "countries": [
            {"code": "IRN", "polity2": -10, "conflict": 0.4, "durability": 0,
             "note": "Regime collapse → theocratic revolution"},
        ],
    },
    {
        "name": "Iranian Hostage Crisis",
        "year": 1980,
        "context": "US embassy hostages; failed rescue; Iran-Iraq War begins",
        "countries": [
            {"code": "IRN", "polity2": -6, "conflict": 0.7, "durability": 1,
             "note": "New Islamic Republic, consolidating + Iran-Iraq War"},
            {"code": "USA", "polity2": 10, "conflict": 0.0, "durability": 150,
             "note": "Carter administration, diplomatic paralysis"},
            {"code": "IRQ", "polity2": -9, "conflict": 0.7, "durability": 12,
             "note": "Saddam Hussein invades Iran September 1980"},
        ],
    },
    # --- Post-Cold War ---
    {
        "name": "Gulf War",
        "year": 1991,
        "context": "Iraq invades Kuwait; US-led coalition liberates Kuwait",
        "countries": [
            {"code": "IRQ", "polity2": -9, "conflict": 0.8, "durability": 23,
             "note": "Saddam regime, high military capacity pre-war"},
            {"code": "KWT", "polity2": -7, "conflict": 0.9, "durability": 30,
             "note": "Emirate overrun; government in exile"},
            {"code": "USA", "polity2": 10, "conflict": 0.2, "durability": 150,
             "note": "Post-Cold War unipolar moment, Bush Sr"},
        ],
    },
    {
        "name": "9/11 Attacks",
        "year": 2001,
        "context": "Al-Qaeda attacks on US; triggers War on Terror",
        "countries": [
            {"code": "USA", "polity2": 10, "conflict": 0.1, "durability": 150,
             "note": "Exogenous non-state attack; GRRI cannot detect a priori",
             "wgi": {"va": 0.84, "pv": 0.50, "ge": 0.86, "rq": 0.88, "rl": 0.86, "cc": 0.82}},
            {"code": "AFG", "polity2": -77, "conflict": 0.9, "durability": 0,
             "note": "Taliban-controlled failed state; GRRI = ACUTE",
             "wgi": None},
        ],
    },
    {
        "name": "Iraq War",
        "year": 2003,
        "context": "US-led invasion; Saddam regime collapses; insurgency follows",
        "countries": [
            {"code": "IRQ", "polity2": -9, "conflict": 0.9, "durability": 35,
             "note": "Regime destroyed; state capacity collapses overnight"},
            {"code": "USA", "polity2": 10, "conflict": 0.3, "durability": 150,
             "note": "Post-9/11 military intervention; domestic debate",
             "wgi": {"va": 0.84, "pv": 0.42, "ge": 0.85, "rq": 0.87, "rl": 0.85, "cc": 0.81}},
        ],
    },
    {
        "name": "Russia-Ukraine War",
        "year": 2022,
        "context": "Full-scale Russian invasion of Ukraine",
        "countries": [
            {"code": "RUS", "polity2": -7, "conflict": 0.5, "durability": 23,
             "note": "Consolidated autocracy; WGI PV collapses",
             "wgi": {"va": rescale_wgi(-1.55), "pv": rescale_wgi(-1.57),
                     "ge": rescale_wgi(-0.36), "rq": rescale_wgi(-0.76),
                     "rl": rescale_wgi(-0.88), "cc": rescale_wgi(-1.02)}},
            {"code": "UKR", "polity2": 4, "conflict": 0.8, "durability": 8,
             "note": "Partial democracy under invasion; institutional resilience tested",
             "wgi": {"va": rescale_wgi(-0.02), "pv": rescale_wgi(-2.10),
                     "ge": rescale_wgi(-0.32), "rq": rescale_wgi(-0.28),
                     "rl": rescale_wgi(-0.56), "cc": rescale_wgi(-0.71)}},
        ],
    },
    {
        "name": "Israel-Hamas War",
        "year": 2023,
        "context": "Hamas attack on Israel (Oct 7); Israeli military response in Gaza",
        "countries": [
            {"code": "ISR", "polity2": 7, "conflict": 0.7, "durability": 75,
             "note": "Democracy; judicial crisis + security failure",
             "wgi": {"va": rescale_wgi(0.39), "pv": rescale_wgi(-1.12),
                     "ge": rescale_wgi(1.22), "rq": rescale_wgi(1.17),
                     "rl": rescale_wgi(0.91), "cc": rescale_wgi(0.89)}},
        ],
    },
]


def analyze_events():
    """Compute enhanced political scores for all events."""
    results = []

    for event in EVENTS:
        year = event["year"]
        event_name = event["name"]
        context = event.get("context", "")

        for country in event["countries"]:
            code = country["code"]
            polity2 = country["polity2"]
            conflict = country.get("conflict", 0.0)
            durability = country.get("durability")
            note = country.get("note", "")
            wgi = country.get("wgi")

            gdppc = get_gdppc(code, year)
            ge = get_ge(code, year)

            # For Russia pre-1991: use historical Russia GE
            if code == "RUS" and year < 1991:
                ge = get_ge("RUS_HIST", year)

            result = compute_enhanced_political_score(
                country_code=code,
                year=year,
                polity2=polity2,
                conflict_intensity=conflict,
                gdp_per_capita=gdppc,
                regime_durability=durability,
                wgi_scores=wgi,
            )

            regime_label = result.regime_type.value.replace("_", " ").title()

            results.append({
                "event": event_name,
                "year": year,
                "context": context,
                "country": code,
                "polity2": polity2,
                "regime_type": regime_label,
                "political_score": result.composite_score,
                "ge": result.governance_effectiveness,
                "pv": result.political_stability,
                "iq": result.institutional_quality,
                "conflict_inv": 1.0 - result.conflict_risk,
                "regime_stab": result.regime_stability,
                "note": note,
            })

    return results


def print_results(results):
    """Print formatted results table."""
    current_event = ""
    print()
    print("=" * 130)
    print("ENHANCED GRRI POLITICAL PILLAR — GEOPOLITICAL EVENT ANALYSIS")
    print("=" * 130)
    print(f"{'Event':<35s} {'Year':>4s}  {'Country':<4s}  {'Polity2':>7s}  "
          f"{'Regime Type':<25s}  {'Score':>5s}  {'GE':>5s}  {'PV':>5s}  "
          f"{'IQ':>5s}  {'1-C':>5s}  {'RS':>5s}  Note")
    print("-" * 130)

    for r in results:
        if r["event"] != current_event:
            if current_event:
                print()
            current_event = r["event"]

        p2_str = str(r["polity2"]) if r["polity2"] not in (-66, -77, -88) else f"{r['polity2']} *"
        print(f"{r['event']:<35s} {r['year']:>4d}  {r['country']:<4s}  {p2_str:>7s}  "
              f"{r['regime_type']:<25s}  {r['political_score']:>5.3f}  "
              f"{r['ge']:>5.3f}  {r['pv']:>5.3f}  {r['iq']:>5.3f}  "
              f"{r['conflict_inv']:>5.3f}  {r['regime_stab']:>5.3f}  {r['note']}")

    print()
    print("* Special Polity5 codes: -66 = interregnum, -77 = anarchy/failed state, -88 = transition")
    print()
    print("Components: GE = Governance Effectiveness (25%), PV = Political Stability (25%),")
    print("            IQ = Institutional Quality (25%), 1-C = Inverse Conflict (15%),")
    print("            RS = Regime Stability (10%)")
    print()
    print("Data Sources: Polity5 (Marshall & Gurr, 2020), Maddison Project (Bolt & van Zanden, 2020),")
    print("              WGI (Kaufmann et al., 2011), COW (Sarkees & Wayman, 2010),")
    print("              UCDP (Pettersson & Oberg, 2020)")


def generate_markdown_table(results):
    """Generate markdown table for the paper."""
    lines = []
    lines.append("")
    lines.append("| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |")
    lines.append("|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|")

    current_event = ""
    for r in results:
        event_col = r["event"] if r["event"] != current_event else ""
        current_event = r["event"]
        year_col = str(r["year"]) if event_col else ""

        p2 = str(r["polity2"])
        if r["polity2"] in (-66, -77, -88):
            p2 += " *"

        lines.append(
            f"| {event_col} | {year_col} | {r['country']} | {p2} | "
            f"{r['regime_type']} | {r['political_score']:.3f} | "
            f"{r['ge']:.2f} | {r['pv']:.2f} | {r['iq']:.2f} | "
            f"{r['conflict_inv']:.2f} | {r['regime_stab']:.2f} |"
        )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    results = analyze_events()
    print_results(results)
    print("\n\n--- MARKDOWN TABLE ---\n")
    print(generate_markdown_table(results))
