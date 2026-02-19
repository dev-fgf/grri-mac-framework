"""
Export GPR (Caldara-Iacoviello Geopolitical Risk Index) data to JSON for frontend.
Also prepares structure for FGF GRS (Geopolitical Risk Supercycle) tracker based on GRRI.

GRRI Data Sources (29 variables across 4 pillars):
- Political: World Bank WGI, Fragile States Index, UCDP, UMD CISSM
- Economic: IMF WEO, Harvard Growth Lab, Garriga CBI, UNESCO, WTO, Harvard GSDB
- Social: UNDP HDI, UNHCR, EC INFORM, V-Dem, Carnegie Protest Tracker
- Environmental: IMF Climate, OECD, World Risk Report, EM-DAT
"""

import pandas as pd
import json


def export_gpr_data():
    """Export GPR data to JSON format for frontend overlay."""

    # Read GPR data
    df = pd.read_excel('data/gpr_data.xls')

    # Use GPRH (Historical GPR, 1900-2019=100) for long-term consistency
    # Filter to 1971+ to match our MAC backtest period
    df['month'] = pd.to_datetime(df['month'])
    df = df[df['month'] >= '1971-01-01'].copy()

    # Prepare output data
    gpr_data = []
    for _, row in df.iterrows():
        if pd.notna(row['GPRH']):
            gpr_data.append({
                'date': row['month'].strftime('%Y-%m-%d'),
                'gpr': round(row['GPRH'], 2),  # Historical GPR (1900-2019=100)
                'gpr_threats': round(row['GPRHT'], 2) if pd.notna(row['GPRHT']) else None,
                'gpr_acts': round(row['GPRHA'], 2) if pd.notna(row['GPRHA']) else None
            })

    # Save GPR data
    with open('frontend/gpr_data.json', 'w') as f:
        json.dump(gpr_data, f, indent=2)

    print(f"Exported {len(gpr_data)} months of GPR data (1971-present)")
    print(f"Date range: {gpr_data[0]['date']} to {gpr_data[-1]['date']}")

    # Calculate some statistics for calibration reference
    gpr_values = [d['gpr'] for d in gpr_data]
    print("\nGPR Statistics (1971-present):")
    print(f"  Min: {min(gpr_values):.1f}")
    print(f"  Max: {max(gpr_values):.1f}")
    print(f"  Mean: {sum(gpr_values)/len(gpr_values):.1f}")

    # Note key historical events for reference
    print("\nKey GPR Spikes (for reference):")
    df_sorted = df.nlargest(10, 'GPRH')[['month', 'GPRH']]
    for _, row in df_sorted.iterrows():
        print(f"  {row['month'].strftime('%Y-%m')}: {row['GPRH']:.1f}")


def create_grs_placeholder():
    """
    Create structure for FGF Geopolitical Risk Supercycle (GRS) Tracker.

    The GRS tracker is based on GRRI (Global Risk Rating Index) methodology:
    - 29 variables across 4 pillars (Political, Economic, Social, Environmental)
    - Coverage: G20 + major emerging markets
    - Frequency: Annual (with quarterly estimates for select indicators)

    See docs/GRRI_Data_Sources.md for full data source documentation.
    """

    grs_structure = {
        "metadata": {
            "name": "FGF Geopolitical Risk Supercycle (GRS) Tracker",
            "version": "1.0.0",
            "status": "development",
            "description": "GRRI-based measure of country-level geopolitical and systemic risk",
            "methodology": "Global Risk Rating Index (GRRI) - 29 variables across 4 pillars",
            "coverage": "G20 + emerging markets",
            "frequency": "Annual"
        },
        "pillars": {
            "political": {
                "name": "Political Risk",
                "weight": 0.25,
                "description": "Governance quality, conflict intensity, and state stability",
                "sources": ["World Bank WGI", "Fragile States Index", "UCDP Uppsala", "UMD CISSM"],
                "variables": 7
            },
            "economic": {
                "name": "Economic Risk",
                "weight": 0.25,
                "description": (
                    "Macroeconomic stability, trade dynamics,"
                    " and institutional strength"
                ),
                "sources": [
                    "IMF WEO", "Harvard Growth Lab",
                    "Garriga CBI", "UNESCO", "WTO",
                    "Harvard GSDB"
                ],
                "variables": 9
            },
            "social": {
                "name": "Social Risk",
                "weight": 0.25,
                "description": "Human development, inequality, and social cohesion",
                "sources": ["UNDP HDI", "UNHCR", "EC INFORM", "V-Dem", "Carnegie Protest Tracker"],
                "variables": 8
            },
            "environmental": {
                "name": "Environmental Risk",
                "weight": 0.25,
                "description": "Climate vulnerability, transition risk, and disaster exposure",
                "sources": ["IMF Climate", "OECD", "World Risk Report", "EM-DAT"],
                "variables": 5
            }
        },
        "countries": {
            "g20": ["ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN",
                    "ITA", "JPN", "MEX", "RUS", "SAU", "ZAF", "KOR", "TUR", "GBR", "USA"],
            "extended": ["EGY", "NGA", "POL", "THA", "VNM", "ARE", "MYS", "PHL", "PAK", "IRN"]
        },
        "data": [],
        "last_updated": None
    }

    # Save GRS structure
    with open('frontend/grs_tracker.json', 'w') as f:
        json.dump(grs_structure, f, indent=2)

    print("\nCreated FGF GRS Tracker structure (GRRI-based)")
    print(f"Total variables: {sum(p['variables'] for p in grs_structure['pillars'].values())}")
    print("Pillars:")
    for name, details in grs_structure['pillars'].items():
        print(
            f"  - {details['name']}: {details['variables']}"
            f" variables ({details['weight']*100:.0f}% weight)"
        )


if __name__ == '__main__':
    export_gpr_data()
    create_grs_placeholder()
