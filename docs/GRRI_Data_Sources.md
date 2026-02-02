# GRRI Data Sources Reference

## Overview

The **Global Risk Rating Index (GRRI)** provides the data foundation for the FGF Geopolitical Risk Supercycle (GRS) Tracker. It aggregates 29 variables across 4 pillars to create a comprehensive country-level risk assessment.

## Pillar Structure

| Pillar | Weight | Variables | Primary Sources |
|--------|--------|-----------|-----------------|
| Political | 25% | 7 | World Bank WGI, UCDP, FSI |
| Economic | 25% | 9 | IMF WEO, Harvard Growth Lab |
| Social | 25% | 8 | UNDP, V-Dem, UNHCR |
| Environmental | 25% | 5 | IMF Climate, EM-DAT, OECD |

---

## Political Risk Variables

| Variable | Source | URL | Frequency |
|----------|--------|-----|-----------|
| Rule of Law | World Bank WGI | [Link](https://www.worldbank.org/en/publication/worldwide-governance-indicators) | Annual |
| Government Effectiveness | World Bank WGI | [Link](https://www.worldbank.org/en/publication/worldwide-governance-indicators) | Annual |
| Regulatory Quality | World Bank WGI | [Link](https://www.worldbank.org/en/publication/worldwide-governance-indicators) | Annual |
| State Legitimacy | Fragile States Index | [Link](https://fragilestatesindex.org/excel/) | Annual |
| Political Violence | World Bank WGI | [Link](https://www.worldbank.org/en/publication/worldwide-governance-indicators) | Annual |
| Inter/Intra-state Conflict | UCDP Uppsala | [Link](https://ucdp.uu.se/exploratory) | Annual |
| Cyber Events | UMD CISSM | [Link](https://cissm.umd.edu/research-impact/publications/cyber-events-database-home) | Event-based |

### World Bank WGI Notes
- Coverage: 1996-present, 200+ countries
- Scale: -2.5 to 2.5 (higher = better governance)
- Indicators: VA, PV, GE, RQ, RL, CC

---

## Economic Risk Variables

| Variable | Source | URL | Frequency |
|----------|--------|-----|-----------|
| Economic Complexity | Harvard Growth Lab | [Link](https://atlas.hks.harvard.edu/data-downloads) | Annual |
| Inflation | IMF WEO | [Link](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)) | Semi-annual |
| Fiscal Balance | IMF WEO | [Link](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)) | Semi-annual |
| Current Account Balance | IMF WEO | [Link](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)) | Semi-annual |
| Central Bank Independence | Garriga CBI Dataset | [Link](https://sites.google.com/site/carogarriga/cbi-data-1) | Periodic |
| Real GDP Growth | IMF WEO | [Link](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)) | Semi-annual |
| Education Spending | UNESCO | [Link](https://databrowser.uis.unesco.org/view) | Annual |
| Trade Remedies | WTO | [Link](https://trade-remedies.wto.org/en) | Event-based |
| Sanctions | Harvard GSDB | [Link](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/SVR5W7) | Event-based |

### IMF WEO Indicator Codes
- `PCPIPCH` - Inflation (% change)
- `GGXCNL_NGDP` - Fiscal balance (% GDP)
- `BCA_NGDPD` - Current account (% GDP)
- `NGDP_RPCH` - Real GDP growth
- `LUR` - Unemployment rate

---

## Social Risk Variables

| Variable | Source | URL | Frequency |
|----------|--------|-----|-----------|
| Human Development Index | UNDP | [Link](https://hdr.undp.org/data-center/documentation-and-downloads) | Annual |
| Refugees | UNHCR | [Link](https://www.unhcr.org/refugee-statistics/download?url=2bxU2f) | Annual |
| Inequality | EC INFORM Risk | [Link](https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Risk/Results-and-data) | Annual |
| Participation | V-Dem | [Link](https://ourworldindata.org/grapher/freedom-of-association-index) | Annual |
| Rights | V-Dem | [Link](https://ourworldindata.org/grapher/freedom-of-association-index) | Annual |
| Social Capital | V-Dem | [Link](https://ourworldindata.org/grapher/suffrage) | Annual |
| Unemployment | IMF WEO | [Link](https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)) | Semi-annual |
| Social Unrest | Carnegie | [Link](https://carnegieendowment.org/features/global-protest-tracker) | Event-based |

---

## Environmental Risk Variables

| Variable | Source | URL | Frequency |
|----------|--------|-----|-----------|
| Climate Risk | IMF Climate Data | [Link](https://climatedata.imf.org/datasets/7cae02f84ed547fbbd6210d90da19879/about) | Annual |
| Fossil Fuel Subsidy | IMF | [Link](https://climatedata.imf.org/datasets/d48cfd2124954fb0900cef95f2db2724_0/about) | Annual |
| Env Tech Development | OECD | [Link](https://data-explorer.oecd.org/) | Annual |
| Climate Humanitarian Toll | World Risk Report | [Link](https://weltrisikobericht.de/) | Annual |
| Extreme Climate Events | EM-DAT | [Link](https://doc.emdat.be/docs/data-structure-and-content/emdat-sources/) | Event-based |

---

## Data Access Methods

### API Access
| Source | API Available | Format |
|--------|--------------|--------|
| IMF WEO | Yes (SDMX) | JSON/CSV |
| World Bank WGI | Yes | JSON/CSV |
| UNDP HDI | No | Excel/CSV |
| V-Dem | Yes | CSV |
| UCDP | Yes | CSV |
| OECD | Yes | SDMX |

### Manual Download Required
- Fragile States Index (Excel)
- Harvard Growth Lab (CSV)
- Garriga CBI Dataset (Stata/CSV)
- Carnegie Protest Tracker (Web scrape)
- World Risk Report (PDF/Excel)
- EM-DAT (Registration required)
- CISSM Cyber Events (Excel)

---

## Aggregation Methodology

1. **Normalization**: Min-max scaling to 0-100 for each variable
2. **Direction**: Align so higher = higher risk
3. **Pillar Score**: Equal-weighted average within pillar
4. **GRRI Score**: Weighted average of pillar scores (25% each)
5. **Missing Data**: Use latest available or regional median

---

## Country Coverage

**Primary**: G20 members (19 countries + EU)
- Argentina, Australia, Brazil, Canada, China, France, Germany, India, Indonesia, Italy, Japan, Mexico, Russia, Saudi Arabia, South Africa, South Korea, Turkey, UK, USA

**Extended**: Major emerging markets
- Egypt, Nigeria, Poland, Thailand, Vietnam, UAE, etc.

---

## Update Schedule

| Source | Update Month |
|--------|--------------|
| IMF WEO | April, October |
| World Bank WGI | September |
| UNDP HDI | September |
| V-Dem | March |
| Fragile States Index | May |
| UCDP | June |
| EM-DAT | Continuous |

---

## References

1. Caldara, D., & Iacoviello, M. (2022). Measuring Geopolitical Risk. *American Economic Review*.
2. Kaufmann, D., Kraay, A., & Mastruzzi, M. (2011). The Worldwide Governance Indicators. *Hague Journal on the Rule of Law*.
3. UNDP (2024). Human Development Report.
4. Garriga, A.C. (2016). Central Bank Independence in the World. *International Interactions*.
