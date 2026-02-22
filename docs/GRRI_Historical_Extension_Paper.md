# Extending the Global Risk and Resilience Index: Historical Proxy Chains for Long-Run Country-Level Resilience Measurement

**Martyn Brush, FGF Research**

**Working Paper — February 2026**

*Confidential Draft*

---

## Abstract

The Global Risk and Resilience Index (GRRI) quantifies country-level structural resilience across four orthogonal pillars — political stability, economic robustness, social cohesion, and environmental exposure — and transforms the composite score into a transmission modifier that scales the market impact of exogenous shocks within the Margin Absorption Capacity (MAC) framework.  Until now, the GRRI has relied on modern data sources whose temporal coverage is limited: the World Bank Worldwide Governance Indicators (WGI) begin in 1996, the IMF World Economic Outlook (WEO) in 1980, the UNDP Human Development Index (HDI) in 1990, and the INFORM Climate Risk Index only in 2012.  This paper presents a systematic extension of the GRRI backward through time by constructing historically-anchored proxy chains that draw on twelve publicly available academic datasets spanning 1789–2025.  We document for each proxy its source, coverage period, normalisation transformation, estimated correlation with its modern counterpart, country coverage, academic justification, and licensing terms.  Particular attention is given to whether each dataset is free to use for commercial purposes, enabling practitioners and product teams to assess which data may be incorporated into commercial risk products without additional licensing negotiation.

Beyond the historical extension, this paper develops three methodological enhancements transplanted from the MAC analytics toolkit: **(1)** adaptive pillar weighting using gradient boosting with leave-one-out cross-validation, calibrated against historical crisis outcomes from Reinhart-Rogoff; **(2)** historically-informed Monte Carlo simulation with empirically-calibrated distributions and copula-estimated cross-pillar dependencies; and **(3)** a formal independence structure analysis using Mutual Information, the Hilbert–Schmidt Independence Criterion (HSIC), and the Maximal Information Coefficient (MIC) to quantify embedded correlations between pillars — particularly those arising from shared underlying datasets — with decorrelation strategies adapted from MAC's private credit pipeline.

**Keywords:** country risk, resilience measurement, historical proxies, geopolitical risk, composite indices, data licensing, Monte Carlo simulation, pillar independence, mutual information, HSIC

---

## 1. Introduction

### 1.1 Motivation

The MAC framework's core equation,

$$\text{Market Impact} = \text{Shock} \times \text{GRRI Modifier} \times f(\text{MAC})$$

positions the GRRI modifier as a multiplicative scaling factor that compresses (for resilient countries) or amplifies (for fragile countries) the transmission of financial shocks.  The modifier is derived from a logistic transformation of the composite GRRI resilience score:

$$\text{modifier} = \frac{2}{1 + \exp\bigl(s \cdot (R - m)\bigr)}$$

where $R \in [0,1]$ is the resilience score, $s = 4.0$ is the steepness parameter, and $m = 0.5$ is the neutral midpoint.  When $R > 0.5$, the modifier compresses shocks ($< 1.0\times$); when $R < 0.5$, it amplifies them ($> 1.0\times$).

The MAC framework has been validated across 117 years of financial history (1907–2025) using detailed proxy chains for its seven financial-market pillars (liquidity, valuation, positioning, volatility, policy, contagion, and private credit).  The GRRI, however, has not benefited from the same rigour: its four country-resilience pillars have been evaluated only with modern data, limiting backtesting to approximately 20 years and preventing validation against the very crises — the Great Depression, the two World Wars, the Bretton Woods collapse, the Latin American debt crisis — that most severely tested national resilience.

### 1.2 Contribution

This paper makes three contributions:

1. **Proxy chain architecture.** We identify, for each GRRI pillar, a cascade of progressively older datasets that can substitute for the modern indicator when the latter is unavailable.  Each chain is documented with a `GRRIProxyConfig` data structure specifying the target indicator, proxy series, transformation, correlation estimate, country coverage, academic reference, and caveats.

2. **Licensing audit.** For each dataset, we determine whether it is (a) freely downloadable without registration, (b) freely downloadable with registration, (c) freely available for academic use only, or (d) commercially licensable.  This distinction is critical for any organisation considering deployment in a commercial risk product.

3. **Implementation.** We provide a production-grade Python module (`grri_mac.grri.historical_sources`) containing data loaders, per-pillar scorers, and a composite `GRRIHistoricalProvider` class that mirrors the design of the MAC `HistoricalDataProvider`, enabling seamless integration.

### 1.3 Coverage Summary

| Pillar | Modern Indicator | Modern Start | Primary Historical Proxy | Proxy Start | Extension |
|--------|------------------|--------------|--------------------------|-------------|-----------|
| Political | WGI Rule of Law | 1996 | Polity5 polity2 / V-Dem polyarchy | 1800 / 1789 | **+196 years** |
| Economic | IMF WEO Real GDP Growth | 1980 | Maddison Project GDP per capita | 1820 | **+160 years** |
| Social | UNDP HDI | 1990 | Crafts-style HDI proxy (Maddison + V-Dem suffrage) | 1870 | **+120 years** |
| Environmental | INFORM Climate Risk | 2012 | EM-DAT disasters + HadCRUT5 temperature | 1900 / 1850 | **+112 years** |

---

## 2. Theoretical Framework

### 2.1 The GRRI Pillar Model

The GRRI decomposes country-level resilience into four equally-weighted pillars:

$$R = w_P \cdot P + w_E \cdot E + w_S \cdot S + w_N \cdot N$$

where $P$, $E$, $S$, and $N$ denote the political, economic, social, and environmental pillar scores respectively, each normalised to $[0,1]$, and $w_P = w_E = w_S = w_N = 0.25$ in the baseline specification.

Each pillar is itself a composite of sub-indicators.  The key challenge for historical extension is finding proxy series that approximate these sub-indicators across periods where the modern data sources do not exist.

### 2.2 Proxy Chain Design Principles

Following the precedent established in the MAC historical extension (Schwert, 1989; Shiller, 2000; NBER Macrohistory Database), we adopt five design principles:

1. **Documented correlation.**  Each proxy must have an estimated correlation with its target indicator during the overlap period.  We require $r \geq 0.50$ for inclusion.
2. **Transparent transformation.**  The mapping from proxy scale to target scale (typically $[0,1]$) is documented and implemented programmatically.
3. **Graceful degradation.**  When fewer sub-indicators are available for a pillar, the composite score is re-weighted over the available components rather than imputed.  A minimum of two pillars with data is required to compute a composite GRRI.
4. **Provenance tracking.**  Every pillar score reports which datasets contributed to its computation.
5. **Cache-aware lazy loading.**  Data files are loaded on first access and cached in memory, following the same pattern used in the MAC `HistoricalDataProvider`.

The following diagram shows the complete proxy chain architecture linking historical sources to GRRI pillars:

```mermaid
flowchart LR
    subgraph Modern["Modern Data (1990+)"]
        WGI["WGI Rule of Law<br/>(1996+)"]
        WEO["IMF WEO GDP<br/>(1980+)"]
        HDI["UNDP HDI<br/>(1990+)"]
        INFORM["INFORM Climate<br/>(2012+)"]
    end

    subgraph Mid["Mid-Century Proxies (1945–1990)"]
        P5["Polity5 polity2<br/>(1800–2018)"]
        COW["COW Wars<br/>(1816–2007)"]
        GARR["Garriga CBI<br/>(1970–2012)"]
        UCDP["UCDP Deaths<br/>(1946+)"]
    end

    subgraph Deep["Deep Historical (pre-1945)"]
        VDEM["V-Dem Polyarchy<br/>(1789+)"]
        MAD["Maddison GDP/pc<br/>(1820+)"]
        SCHW["Schwert Vol<br/>(1802–1987)"]
        NBER["NBER Macro<br/>(1857+)"]
    end

    subgraph Environment["Environmental Chain"]
        EMDAT["EM-DAT Disasters<br/>(1900+)"]
        HAD["HadCRUT5 Temp<br/>(1850+)"]
    end

    subgraph GRRI["GRRI Composite"]
        P["Political<br/>Pillar"]
        E["Economic<br/>Pillar"]
        S["Social<br/>Pillar"]
        N["Environmental<br/>Pillar"]
        COMP["R = 0.25P + 0.25E<br/> + 0.25S + 0.25N"]
        MOD["Modifier =<br/>2/(1+exp(4(R−0.5)))"]
    end

    WGI --> P
    P5 --> P
    VDEM --> P
    COW --> P

    WEO --> E
    MAD --> E
    NBER --> E
    GARR --> E

    HDI --> S
    MAD -.->|"GDP/pc for<br/>HDI proxy"| S
    VDEM -.->|"Suffrage"| S

    INFORM --> N
    EMDAT --> N
    HAD --> N

    P --> COMP
    E --> COMP
    S --> COMP
    N --> COMP
    COMP --> MOD
```

*Figure 1. GRRI proxy chain architecture.  Solid arrows indicate primary data flows; dashed arrows show shared datasets creating embedded correlations between pillars (see Section 11).*

### 2.3 Minimum-Pillar Constraint

For periods where only two or three pillars can be scored (e.g., before 1900, when environmental data is sparse), we re-normalise the weights over the available pillars:

$$R = \frac{\sum_{i \in \mathcal{A}} w_i \cdot S_i}{\sum_{i \in \mathcal{A}} w_i}$$

where $\mathcal{A}$ is the set of pillars with at least one scored sub-indicator.  We require $|\mathcal{A}| \geq 2$ as a precondition; if fewer than two pillars have data, `get_historical_grri()` returns `None`.

---

## 3. Data Sources and Licensing

This section documents every dataset used in the historical GRRI extension.  For each source, we provide the coverage period, geographic scope, licensing terms, and an explicit assessment of whether the data may be used in a commercial product.

### 3.1 Licensing Classification

We use the following taxonomy:

| Label | Meaning |
|-------|---------|
| **FREE-OPEN** | Freely downloadable, no registration, permissive licence (CC-BY, public domain, or equivalent).  Safe for commercial use. |
| **FREE-REG** | Freely downloadable after registration but with a permissive or academic licence that does not prohibit commercial use.  Verify licence text before deployment. |
| **ACADEMIC** | Freely available for academic/research use; commercial use requires separate licence negotiation or is prohibited. |
| **COMMERCIAL** | Requires paid licence for any use. |

### 3.2 Political Pillar Data Sources

#### 3.2.1 Polity5 Project (Center for Systemic Peace)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | `polity2` composite regime score (−10 to +10) |
| **Coverage** | 1800–2018, 167 countries |
| **URL** | https://www.systemicpeace.org/inscrdata.html |
| **Format** | XLS/CSV |
| **Transformation** | Linear: $(polity2 + 10) / 20 \to [0,1]$ |
| **Correlation with WGI** | $r \approx 0.82$ (overlap 1996–2018) |
| **Licence** | **FREE-OPEN.** The datasets are listed as publicly available for download without registration.  The Center for Systemic Peace encourages citation but does not impose a restrictive licence.  No paywall, no terms-of-use page requiring acceptance.  **Commercialisable with citation.** |
| **Reference** | Marshall, M.G. & Gurr, T.R. (2020). *Polity5: Political Regime Characteristics and Transitions, 1800–2018.* |
| **Caveats** | Polity5 measures executive constraints and political competition; it does not capture rule of law per se.  Correlation with WGI is strong for democracies but weaker for hybrid regimes.  Special codes (−66 interregnum, −77 anarchy, −88 transition) must be excluded from time-series analysis. |

#### 3.2.2 Varieties of Democracy (V-Dem) Institute

| Attribute | Detail |
|-----------|--------|
| **Indicators** | `v2x_polyarchy` (electoral democracy, 0–1), `v2x_rule` (rule of law, 0–1), `v2x_civlib` (civil liberties, 0–1), `v2x_suffr` (suffrage share, 0–1), `v2x_freexp` (freedom of expression, 0–1) |
| **Coverage** | 1789–present, 202 countries |
| **URL** | https://v-dem.net/data/ |
| **Format** | CSV (full country-year core dataset, ~100 MB) |
| **Transformation** | Direct (already on 0–1 scale) |
| **Correlation with WGI** | $r \approx 0.91$ for `v2x_rule`; $r \approx 0.93$ for `v2x_polyarchy` vs. WGI Voice & Accountability |
| **Licence** | **FREE-REG (Creative Commons).** V-Dem data is freely available under a CC-BY-SA 4.0 licence after creating a free account.  The CC-BY-SA licence permits commercial use provided the data is attributed and derivative works are shared under the same licence.  **Commercialisable with attribution and share-alike.** |
| **Reference** | Coppedge, M. et al. (2023). *V-Dem Codebook v14.* Varieties of Democracy Institute, University of Gothenburg. |
| **Caveats** | Expert-coded historical data; pre-1900 scores rely on retrospective judgement of historical records and should be treated as ordinal rather than cardinal.  Inter-coder reliability is lower before 1900.  The full dataset is large (~100 MB); for production use a pre-filtered extract of G20 countries and selected indicators is recommended. |

#### 3.2.3 Correlates of War (COW) War Data

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Interstate and civil war participation; battle-death estimates |
| **Coverage** | 1816–2007 (v4.0); supplemented by UCDP for 1946+ |
| **URL** | https://correlatesofwar.org/data-sets/ |
| **Format** | CSV |
| **Transformation** | Log-scaled battle deaths: $\min(1.0, \log_{10}(\text{deaths} + 1) / 6.0)$ |
| **Correlation with UCDP** | $r \approx 0.85$ during overlap (1946–2007) |
| **Licence** | **FREE-OPEN.** The COW project makes its data freely available for download without registration.  The project requests citation and notification of publications but does not impose a restrictive licence.  **Commercialisable with citation.** |
| **Reference** | Sarkees, M.R. & Wayman, F. (2010). *Resort to War: 1816–2007.* CQ Press. |
| **Caveats** | Covers interstate and civil wars only; sub-state violence and one-sided killings are excluded.  Battle-death estimates for pre-1900 conflicts carry significant uncertainty. |

#### 3.2.4 Uppsala Conflict Data Programme (UCDP)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Battle-related deaths; conflict events |
| **Coverage** | 1946–present, global |
| **URL** | https://ucdp.uu.se/downloads/ |
| **Format** | CSV (ZIP archive) |
| **Transformation** | Log-scaled battle deaths, as per COW |
| **Licence** | **FREE-OPEN (CC-BY 4.0).** Data is available for download without registration under Creative Commons Attribution 4.0 International.  **Commercialisable with attribution.** |
| **Reference** | Pettersson, T. & Öberg, M. (2020). *Organized violence, 1989–2019.* Journal of Peace Research, 57(4). |
| **Caveats** | Begins 1946; for earlier conflict data, COW provides coverage. |

#### 3.2.5 World Bank Worldwide Governance Indicators (WGI)

| Attribute | Detail |
|-----------|--------|
| **Indicators** | Six dimensions: Voice & Accountability (VA), Political Stability & Absence of Violence (PV), Government Effectiveness (GE), Regulatory Quality (RQ), Rule of Law (RL), Control of Corruption (CC) |
| **Coverage** | 1996–2022, 215 economies (biennial 1996–2002, annual 2003+) |
| **URL** | https://info.worldbank.org/governance/wgi/ |
| **Format** | XLS/CSV |
| **Transformation** | Linear rescaling: $(\text{estimate} + 2.5) / 5.0 \to [0,1]$ |
| **Licence** | **FREE-OPEN (CC-BY 4.0).** World Bank Open Data licence.  **Commercialisable with attribution.** |
| **Reference** | Kaufmann, D., Kraay, A. & Mastruzzi, M. (2011). *The Worldwide Governance Indicators: Methodology and Analytical Issues.* Hague Journal on the Rule of Law, 3(2), 220–246. |
| **Caveats** | Composite of perception-based indicators; may lag structural changes.  Pre-2002 data is biennial (1996, 1998, 2000, 2002).  All six dimensions are used in the enhanced political pillar — the original framework used only Rule of Law. |

**Rationale for full WGI adoption:** The original GRRI political pillar targeted WGI Rule of Law as the sole modern governance indicator.  This is insufficient because:

1. **Government Effectiveness** (GE) captures state capacity — the ability to formulate and implement policies — which is orthogonal to regime type.  A consolidated autocracy (China, UAE) can score highly on GE while scoring poorly on Voice & Accountability.
2. **Political Stability & Absence of Violence** (PV) measures the likelihood of political instability or politically-motivated violence, which is the most direct GRRI-relevant dimension.
3. **Regulatory Quality** (RQ) captures the capacity to formulate sound policies, relevant to economic resilience.
4. **Control of Corruption** (CC) is a strong predictor of institutional resilience under stress.

### 3.3 Economic Pillar Data Sources

#### 3.3.1 Maddison Project Database (GGDC, University of Groningen)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | GDP per capita in 2011 international dollars (PPP) |
| **Coverage** | 1820–present, 169 countries (2020 release) |
| **URL** | https://www.rug.nl/ggdc/historicaldevelopment/maddison/ |
| **Format** | XLSX (Excel workbook with multiple sheets) |
| **Transformation** | 5-year compound annual growth rate (CAGR), normalised: $(\text{CAGR} + 0.10) / 0.20 \to [0,1]$.  Also used as economic complexity proxy via log-scaling: $(\ln(\text{GDPpc}) - 5) / 6 \to [0,1]$. |
| **Correlation with IMF WEO** | $r \approx 0.78$ for growth rates (overlap 1980–2018) |
| **Licence** | **FREE-OPEN.** The Maddison Project Database is publicly available for download without registration.  The dataset is made available for research and "wider use".  Citation is requested.  There is no explicit restrictive licence.  **Commercialisable with citation.** |
| **Reference** | Bolt, J. & van Zanden, J.L. (2020). *Maddison style estimates of the evolution of the world economy: A new 2020 update.* Maddison Project Working Paper WP-15, University of Groningen. |
| **Caveats** | Pre-1870 estimates are benchmarked and interpolated; annual growth rates should be treated as approximate.  PPP adjustments for early periods are subject to index-number problems.  Country coverage thins before 1870. |

#### 3.3.2 MeasuringWorth US GDP (Officer & Williamson)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | US nominal GDP (1790+) |
| **Coverage** | 1790–present, US only |
| **URL** | https://www.measuringworth.com/datasets/usgdp/ |
| **Format** | CSV |
| **Transformation** | Deflate by CPI (Shiller or MeasuringWorth CPI), compute real growth → normalise to [0,1] |
| **Correlation with IMF WEO** | $r \approx 0.70$ (overlap 1980–present, after CPI deflation) |
| **Licence** | **ACADEMIC / RESTRICTED.** MeasuringWorth permits free use for *academic and non-profit research*.  Commercial use requires explicit licence from Samuel H. Williamson.  Terms of Use state: "The datasets are copyrighted and may not be used for commercial purposes without permission."  **Not freely commercialisable.  Contact required for commercial licence.** |
| **Reference** | Johnston, L. & Williamson, S.H. (2023). *What Was the U.S. GDP Then?* MeasuringWorth. |
| **Caveats** | US only.  Pre-1870 GDP estimates are rough.  Nominal GDP requires CPI deflation, which introduces additional uncertainty.  Already used in the MAC framework's historical extension. |

#### 3.3.3 Reinhart-Rogoff Crisis Database

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Binary crisis indicators: banking, currency, sovereign default (external and domestic), inflation, stock market crash |
| **Coverage** | 1800–present, 70 countries |
| **URL** | https://www.carmenreinhart.com/data |
| **Format** | XLS/CSV |
| **Transformation** | Count of crisis types in 5-year window, normalised: $\min(1.0, \text{count} / 5)$ |
| **Correlation** | $r \approx 0.85$ with modern crisis databases (Laeven & Valencia, 2020) |
| **Licence** | **FREE-OPEN.** The dataset is posted on Reinhart's personal academic website for public download.  No login, no paywall, no restrictive licence.  Citation is expected per academic convention.  **Commercialisable with citation.** |
| **Reference** | Reinhart, C.M. & Rogoff, K.S. (2009). *This Time Is Different: Eight Centuries of Financial Folly.* Princeton University Press. |
| **Caveats** | Binary indicators (crisis / no crisis) lose intensity information.  Some crisis dates are debated in the literature (e.g., the 1998 Russian crisis is coded differently by different authors).  Country naming conventions require harmonisation. |

#### 3.3.4 Shiller CPI and Equity Data (Yale)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Consumer Price Index, S&P Composite, CAPE ratio, long-term interest rates (GS10) |
| **Coverage** | 1871–present, US |
| **URL** | http://www.econ.yale.edu/~shiller/data.htm |
| **Format** | XLS |
| **Transformation** | CPI used for deflation; CAPE and GS10 used in MAC framework |
| **Licence** | **FREE-OPEN.** Data is publicly posted on Robert Shiller's Yale website for free download.  No licence restrictions stated.  **Commercialisable with citation.** |
| **Reference** | Shiller, R.J. (2000). *Irrational Exuberance.* Princeton University Press. (Updated data at Yale.) |
| **Caveats** | US only.  Already used extensively in the MAC framework. |

#### 3.3.5 Garriga Central Bank Independence Index

| Attribute | Detail |
|-----------|--------|
| **Indicator** | CBI index (0–1) based on legal independence measures |
| **Coverage** | 1970–2017, 182 countries |
| **URL** | https://sites.google.com/site/carogarriga/cbi-data-1 |
| **Format** | CSV/DTA (Stata) |
| **Transformation** | Direct (already on 0–1 scale) |
| **Correlation** | $r = 1.0$ (direct measurement of CBI, not a proxy) |
| **Licence** | **FREE-REG (Academic).** The dataset is freely downloadable from Garriga's academic website.  Designed for academic research.  No explicit commercial licence terms are stated — the standard expectation is citation.  Given the absence of a restrictive commercial clause and the academic distribution model, cautious commercial users should **seek written confirmation from the author** before embedding in a paid product.  **Commercialisable subject to author confirmation.** |
| **Reference** | Garriga, A.C. (2016). *Central Bank Independence in the World: A New Dataset.* International Interactions, 42(5), 849–868. |
| **Caveats** | Ends 2017; post-2017 scores must be extrapolated or sourced from alternative CBI databases.  Pre-1970 CBI must be approximated heuristically—see Section 4.2.3. |

#### 3.3.6 Harvard Global Sanctions Database (GSDB)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Sanctions episodes (sender, target, type, start/end year) |
| **Coverage** | 1950–2022, global |
| **URL** | https://doi.org/10.7910/DVN/SVR5W7 (Harvard Dataverse) |
| **Format** | CSV/DTA |
| **Transformation** | Count of active sanctions → ordinal severity |
| **Correlation** | $r \approx 0.90$ with other sanctions databases (HSE, TIES) |
| **Licence** | **FREE-OPEN (CC0 1.0).** Published on Harvard Dataverse under CC0 Public Domain Dedication.  This is the most permissive licence available—no restrictions whatsoever.  **Fully commercialisable without restriction.** |
| **Reference** | Felbermayr, G. et al. (2020). *The Global Sanctions Data Base.* European Economic Review, 131, 103561. |
| **Caveats** | Coverage begins 1950; pre-WW2 sanctions are not coded.  Transaction-level data on trade disruption is not available, only episode-level metadata. |

### 3.4 Social Pillar Data Sources

#### 3.4.1 V-Dem Suffrage and Civil Liberties

The V-Dem indicators `v2x_suffr` (suffrage share) and `v2x_civlib` (civil liberties) are cross-listed between the political and social pillars.  See Section 3.2.2 for licensing details.

**Social Pillar Usage:**
- `v2x_suffr` is used as a proxy for the education/empowerment dimension of HDI (following Crafts, 1997)
- `v2x_civlib` captures the social cohesion and rights dimension

**Licence:** **FREE-REG (CC-BY-SA 4.0).**  See Section 3.2.2.

#### 3.4.2 Crafts-Style Historical HDI Proxy

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Composite HDI proxy from GDP per capita (income) + suffrage (education/empowerment) |
| **Coverage** | 1820–1989 (where both Maddison and V-Dem overlap) |
| **Construction** | $\text{HDI proxy} = \frac{1}{2}\bigl[\text{normalised GDP/pc} + \text{V-Dem suffrage}\bigr]$ |
| **Correlation with UNDP HDI** | $r \approx 0.75$ (overlap 1990–2018) |
| **Licence** | **Derived.** Uses Maddison (FREE-OPEN) + V-Dem (CC-BY-SA 4.0).  The composite inherits the most restrictive licence: **CC-BY-SA 4.0.**  Commercialisable with attribution and share-alike. |
| **Reference** | Crafts, N.F.R. (1997). *The Human Development Index and Changes in Standards of Living: Some Historical Comparisons.* European Review of Economic History, 1(3), 299–322. |
| **Caveats** | Missing life-expectancy dimension entirely; uses suffrage as education/empowerment proxy.  Pre-1870 data is very sparse.  The proxy is weakest for countries where income growth and democratic participation diverge significantly (e.g., Gulf states). |

#### 3.4.3 Mitchell's International Historical Statistics (Unemployment)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Unemployment rate (%) |
| **Coverage** | ~1919–1959 for major economies (UK, US, Germany, France) |
| **URL** | Published by Palgrave Macmillan |
| **Format** | Book; requires manual transcription into CSV |
| **Transformation** | Inverted for resilience: $\max(0, \min(1, 1 - (\text{rate} - 3) / 17))$ |
| **Correlation with ILO** | $r \approx 0.80$ (overlap for countries with long BLS or ONS series) |
| **Licence** | **COMMERCIAL.** Mitchell's *International Historical Statistics* is a copyrighted Palgrave Macmillan publication.  Data transcribed from the book may be used in research under fair use, but large-scale digitisation and commercial redistribution would require publisher permission.  Individual data points cited in research are covered by fair use / fair dealing.  **Not freely commercialisable in bulk.  Individual data points may be used under fair use.** |
| **Reference** | Mitchell, B.R. (2013). *International Historical Statistics.* 7th edition. Palgrave Macmillan. |
| **Caveats** | Pre-WW2 unemployment statistics are often based on trade-union reports or administrative data, not household surveys.  Definitions vary across countries and periods.  Coverage is patchy for some countries. |

### 3.5 Environmental Pillar Data Sources

#### 3.5.1 EM-DAT International Disaster Database (CRED)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Disaster events: deaths, affected population, economic damages |
| **Coverage** | 1900–present, global |
| **URL** | https://www.emdat.be/ |
| **Format** | CSV (downloadable after free registration) |
| **Transformation** | Log-scaled 5-year death total: $\min(1.0, \log_{10}(\text{deaths} + 1) / 6.0)$ |
| **Correlation with INFORM** | $r \approx 0.65$ (overlap 2012–present; indirect, as INFORM incorporates EM-DAT as an input) |
| **Licence** | **FREE-REG (Non-Commercial).** EM-DAT requires free registration.  The licence states: "EM-DAT data is available free of charge for academic, non-commercial and public use.  Commercial use of the data requires prior agreement."  **Not freely commercialisable.  Commercial licence required from CRED.** |
| **Reference** | Guha-Sapir, D. et al. (2023). *EM-DAT: The International Disaster Database.* Centre for Research on the Epidemiology of Disasters (CRED), UCLouvain, Brussels. |
| **Caveats** | Pre-1960 disaster reporting is incomplete, especially for developing countries.  Under-reporting biases severity downward for historical periods.  Economic damage figures before 1970 are unreliable and should not be used. |

#### 3.5.2 HadCRUT5 Global Temperature Anomaly (UK Met Office / CRU)

| Attribute | Detail |
|-----------|--------|
| **Indicator** | Global mean surface temperature anomaly (°C relative to 1961–1990 baseline) |
| **Coverage** | 1850–present, global mean (not country-specific) |
| **URL** | https://www.metoffice.gov.uk/hadobs/hadcrut5/ |
| **Format** | CSV (annual and monthly versions) |
| **Transformation** | 30-year rate of change normalised: $\delta = T_t - T_{t-30}$, score $= \min(1, \delta / 2.0)$ |
| **Correlation with INFORM** | $r \approx 0.60$ (indirect; captures macro trend only) |
| **Licence** | **FREE-OPEN (Open Government Licence v3).** The UK Met Office publishes HadCRUT5 under the Open Government Licence, which permits commercial use, adaptation, and redistribution provided the source is acknowledged.  **Fully commercialisable with attribution.** |
| **Reference** | Morice, C.P. et al. (2021). *An Updated Assessment of Near-Surface Temperature Change From 1850: The HadCRUT5 Data Set.* Journal of Geophysical Research: Atmospheres, 126(3), e2019JD032361. |
| **Caveats** | Global mean temperature is not country-specific; relationship between global trend and country-level climate risk is indirect.  Mainly captures the macro trend of increasing climate instability.  Country-level exposure data (e.g., Notre Dame ND-GAIN) begins only in 1995. |

---

## 4. Proxy Chain Architecture by Pillar

### 4.1 Political Pillar

The political pillar measures governance quality, institutional resilience, and absence of violent conflict.  The modern indicators are the six dimensions of the World Bank WGI (1996+), supplemented by regime-type classification and geopolitical momentum detection.

#### 4.1.1 Enhanced Political Pillar Architecture

The original GRRI political scoring computed an equal-weight average of governance, democracy, civil liberties, and inverse conflict — all of which are democracy-centric measures.  This creates a systematic bias: stable autocracies with effective governance (China, UAE, Saudi Arabia) receive inappropriately low resilience scores because non-democratic regime type is conflated with governance failure.

The enhanced architecture separates **governance effectiveness** from **regime type** and adds **geopolitical momentum detection**:

| Component | Weight | Modern Source | Historical Proxy |
|-----------|--------|---------------|------------------|
| Governance Effectiveness | 25% | WGI GE (1996+) | GDP/capita + expert anchors (1820+) |
| Political Stability | 25% | WGI PV (1996+) | Regime-type baseline + conflict (1816+) |
| Institutional Quality | 25% | WGI RL + RQ (1996+) | V-Dem v2x_rule + Polity5 (1789+) |
| Conflict Risk (inverse) | 15% | UCDP (1946+) | COW battle deaths (1816+) |
| Regime Stability | 10% | Regime type + durability | Polity5 + GE proxy (1800+) |

**Composite political score:**

$$P = 0.25 \cdot \text{GE} + 0.25 \cdot \text{PS} + 0.25 \cdot \text{IQ} + 0.15 \cdot (1 - \text{conflict}) + 0.10 \cdot \text{RS}$$

#### 4.1.2 Regime Type Classification

The classification follows Goldstone et al. (2010) and Hegre et al. (2001), who demonstrate that **anocracies** (hybrid regimes with Polity5 scores between −5 and +5) are empirically the *least* stable political systems — more conflict-prone than either full democracies or consolidated autocracies.

| Regime Type | Polity2 Range | Stability Baseline | Key Feature |
|-------------|---------------|-------------------|-------------|
| Full Democracy | +6 to +10 | 0.85 | Strong checks and balances |
| Democracy | +1 to +5 | 0.70 | Partial institutional constraints |
| Open Anocracy | 0 to −5 | 0.30 | **Empirically most unstable** |
| Closed Anocracy | −6 to −9 | 0.35 | Neither fully open nor consolidated |
| Consolidated Autocracy | ≤ −6 + high GE | 0.65 | Effective state + durable regime |
| Full Autocracy | ≤ −6 | 0.50 | Autocratic without effective governance |
| Failed/Occupied | Special codes | 0.10 | −66/−77/−88 in Polity5 |

**Consolidated Autocracy** is distinguished from ordinary autocracy when $\text{GE} \geq 0.5$ or regime durability $\geq 25$ years.  This distinction is critical for:
- **China** (polity2 = −7, GE ≈ 0.70): classified as *consolidated autocracy*, political score ≈ 0.58 (vs. ~0.10 under old system)
- **UAE** (polity2 = −8, GE ≈ 0.85): classified as *consolidated autocracy*, political score ≈ 0.61
- **Saudi Arabia** (polity2 = −10, GE ≈ 0.55): classified as *consolidated autocracy*, political score ≈ 0.54

The stability baseline is adjusted by:
- **GE adjustment:** $\pm 0.15$ based on $(GE - 0.5) \times 0.30$
- **Durability bonus:** $+0.005$ per year of regime stability, max $+0.10$

#### 4.1.3 Governance Effectiveness Proxy (Pre-1996)

For periods before WGI coverage, governance effectiveness is estimated from:

1. **Expert historical anchors** (50% weight): Calibrated estimates for major economies based on state capacity literature (Besley & Persson, 2011; Acemoglu & Robinson, 2012).  Available for US, UK, Germany, France, Japan, China, Russia, Saudi Arabia, UAE.
2. **GDP per capita** (35% weight): $\text{GE}_{\text{GDP}} = (\ln(\text{GDPpc}) - 5.5) / 5.5$, justified by the strong empirical correlation ($r \approx 0.82$) between income and state capacity.
3. **Polity5 regime consolidation** (15% weight): $|\text{polity2}| / 10 \times 0.5 + 0.25$ — captures that consolidated regimes (both democratic and autocratic) tend to have higher state capacity than transitional ones.

#### 4.1.4 Geopolitical Momentum Detection

**Rationale:** The original GRRI is purely level-based — it measures structural resilience but not *deterioration*.  The MAC framework includes a momentum component (DETERIORATING status when 4-week momentum $< -0.04$).  This section extends the concept to GRRI with annual political pillar scores.

**Detection methodology:** Compute 3-year, 5-year, and 10-year changes in the political pillar score.  The most alarming applicable status is assigned:

| Status | Condition | Interpretation |
|--------|-----------|----------------|
| **STABLE** | $\lvert\Delta_{3\text{yr}}\rvert < 0.05$ | No significant momentum |
| **IMPROVING** | $\Delta_{3\text{yr}} \geq +0.05$ | Political conditions strengthening |
| **WATCH** | $\Delta_{3\text{yr}} \leq -0.05$ | Early warning: mild deterioration |
| **DETERIORATING** | $\Delta_{3\text{yr}} \leq -0.10$ | Sustained decline — elevated risk |
| **ACUTE** | $\Delta_{3\text{yr}} \leq -0.20$ | Rapid deterioration — crisis imminent |

**Structural overlay:** If the 10-year change $\Delta_{10\text{yr}} \leq -0.15$, the status is elevated one level (STABLE → WATCH, WATCH → DETERIORATING).  This captures slow-burn structural erosion that 3-year windows may miss.

**Validation case — Russia 2010–2022:**

Using enhanced political scores derived from published WGI point estimates (info.worldbank.org/governance/wgi), Polity5 classifications, and UCDP conflict data:

| Year | Political Score | Status | 3yr Δ | Key Event |
|------|----------------|--------|-------|-----------|
| 2010 | 0.453 | STABLE | — | Baseline (open anocracy, polity2 = −4) |
| 2014 | 0.459 | **STABLE** | +0.001 | Crimea — WGI PV drops but GE improves |
| 2018 | 0.503 | STABLE | +0.026 | Peak: GE at best WGI level (−0.04) |
| 2021 | 0.485 | STABLE | −0.018 | VA/CC declining, military build-up |
| 2022 | 0.355 | **DETERIORATING** | −0.146 | Invasion — PV collapses (WGI −0.66 → −1.57) |

This trajectory reveals a critical insight about the WGI-based momentum signal: the system correctly remains STABLE through 2021 because WGI governance indicators — which are perception-based and measure institutional *outcomes* rather than geopolitical *intent* — do not capture the pre-invasion military build-up.  Russia's Government Effectiveness actually *improved* between 2010 and 2018 (WGI GE from −0.39 to −0.04) as Putin consolidated state capacity.

The signal fires only in 2022 when the invasion collapses WGI Political Stability from −0.66 to −1.57 (one of the largest single-year PV drops in the dataset).  This demonstrates both: (a) that the momentum system correctly detects deterioration when the underlying data reflects it; and (b) that Fordham-type qualitative geopolitical analysts can outperform quantitative governance indicators on *pre-conflict* detection because they incorporate military deployments, diplomatic posture, and political rhetoric that WGI does not measure.

**Limitations:** The momentum signal:
- Requires minimum 3 years of prior data
- Operates at annual resolution — sub-annual events (coups, rapid escalation) appear with lag
- Cannot detect truly exogenous shocks with no political-institutional precursor (e.g., 9/11 — the attack on the US originated from a non-state actor operating from a failed state; the *US* political pillar showed no deterioration)

**Proxy cascade (updated):**

```
WGI (all 6 dimensions) (1996–present)
    ↓ (pre-1996)
Governance Effectiveness → GDP/capita + expert anchors (1820+)
Political Stability → Regime-type baseline + conflict (1816+)
Institutional Quality → V-Dem v2x_rule (1789+, r ≈ 0.91)
                       → Polity5 xconst/polity2 (1800+, r ≈ 0.82)
Conflict Risk → UCDP (1946+) → COW (1816+)
Regime Stability → Polity5 + GE classification (1800+)
Geopolitical Momentum → 3yr/5yr/10yr Δ in composite political score (1803+)
```

### 4.2 Economic Pillar

The economic pillar captures GDP growth trajectory, economic diversity/complexity, central bank independence, fiscal space, and crisis vulnerability.

#### 4.2.1 GDP Growth Proxy

The Maddison Project provides GDP per capita in constant 2011 international dollars, enabling computation of compound annual growth rates (CAGR) over rolling windows:

$$g = \left(\frac{\text{GDP}_{t}}{\text{GDP}_{t-5}}\right)^{1/5} - 1$$

Normalised to $[0,1]$ with $-10\%$ mapping to $0$ and $+10\%$ mapping to $1$:

$$\text{score} = \frac{g + 0.10}{0.20}$$

#### 4.2.2 Economic Complexity Proxy

For periods before the Harvard Growth Lab Economic Complexity Index (ECI, 1995+), we use log GDP per capita as a proxy:

$$\text{complexity} = \frac{\ln(\text{GDPpc}) - 5}{6}$$

This is justified by the strong empirical correlation ($r \approx 0.72$) between GDP per capita and the ECI documented in Hidalgo & Hausmann (2009), though it does not capture the trade-composition dimension directly.  Resource-rich economies with high GDP but low export diversification (e.g., Saudi Arabia, Nigeria) are systematically overrated by this proxy.

#### 4.2.3 Central Bank Independence: Pre-1970 Heuristic

The Garriga CBI index provides data from 1970–2017.  For earlier periods, we assign heuristic scores based on institutional features documented in Friedman & Schwartz (1963):

| Period | Condition | CBI Score |
|--------|-----------|-----------|
| Pre-1913 (US) | No central bank | 0.0 |
| Pre-1913 (UK) | Bank of England operating under gold standard | 0.5 |
| Pre-1913 (France) | Banque de France, government-directed | 0.4 |
| Pre-1913 (Germany) | Reichsbank, semi-independent | 0.5 |
| Pre-1913 (default) | Most countries lacked CB or had government-directed institutions | 0.3 |
| 1914–1944 | Wartime—most CBs under government direction | 0.3 |
| 1945–1969 | Post-war moderate independence in advanced economies | 0.4 |

These heuristic scores are explicitly flagged in the provenance metadata as "CBI heuristic (pre-1970)" and carry a correlation estimate of only $r \approx 0.50$.

#### 4.2.4 Crisis Fragility

The Reinhart-Rogoff crisis database provides binary indicators for six crisis types.  We compute a rolling 5-year crisis count and normalise:

$$\text{fragility} = \min\left(1.0,\; \frac{\sum_{s=t-5}^{t+5} \sum_{k \in K} \mathbb{1}[\text{crisis}_{s,k}]}{5}\right)$$

where $K = \{\text{banking, currency, sovereign}_{\text{ext}}, \text{sovereign}_{\text{dom}}, \text{inflation, stock crash}\}$.

**Composite economic score:**

$$E = \sum_{j} w_j^E \cdot c_j^E \bigg/ \sum_{j} w_j^E \qquad w_j^E = 0.20 \;\forall j$$

Components: GDP growth, economic diversity, CBI, fiscal space (composite of growth + inverse crisis), inverse crisis fragility.

### 4.3 Social Pillar

The social pillar measures human development, social capital (political participation), employment, and civil rights.

**Components:**

| Sub-indicator | Source | Weight | Transformation |
|---------------|--------|--------|----------------|
| HDI proxy | Maddison GDP/pc + V-Dem suffrage | 0.30 | Average of normalised income + suffrage |
| Suffrage | V-Dem `v2x_suffr` | 0.25 | Direct (0–1) |
| Unemployment (inverted) | Mitchell / BLS / ILO | 0.25 | $\max(0, 1 - (\text{rate} - 3) / 17)$ |
| Civil liberties | V-Dem `v2x_civlib` | 0.20 | Direct (0–1) |

### 4.4 Environmental Pillar

The environmental pillar is necessarily thinner for historical periods.  Modern INFORM Risk (2012+) integrates hazard exposure, vulnerability, and coping capacity across ~30 sub-indicators.  Our historical proxy reduces this to two components:

| Sub-indicator | Source | Weight | Transformation |
|---------------|--------|--------|----------------|
| Disaster severity (inverted) | EM-DAT | 0.60 | $1 - \min(1, \log_{10}(\text{deaths}+1)/6)$ |
| Climate anomaly rate (inverted) | HadCRUT5 | 0.40 | $1 - \min(1, \delta_{30\text{yr}} / 2.0)$ |

**Limitation:** The historical environmental score captures physical hazard realization (disasters) and the macro climate trend but does not capture vulnerability, coping capacity, or green transition progress.  Before 1900, when EM-DAT coverage begins, this pillar defaults to climate data alone (1850–1899) or is excluded entirely (pre-1850).

---

## 5. Licensing Summary for Commercial Use

The following table provides a consolidated view of data licensing relevant to commercial deployment.

| Data Source | Pillar(s) | Coverage | Licence Type | Commercialisable? |
|-------------|-----------|----------|-------------|-------------------|
| **Polity5** | Political | 1800–2018 | FREE-OPEN | **Yes**, with citation |
| **V-Dem** | Political, Social | 1789–present | FREE-REG (CC-BY-SA 4.0) | **Yes**, with attribution + share-alike |
| **COW Wars** | Political | 1816–2007 | FREE-OPEN | **Yes**, with citation |
| **UCDP** | Political | 1946–present | FREE-OPEN (CC-BY 4.0) | **Yes**, with attribution |
| **World Bank WGI** | Political | 1996–present | FREE-OPEN (CC-BY 4.0) | **Yes**, with attribution |
| **Maddison Project** | Economic, Social | 1820–present | FREE-OPEN | **Yes**, with citation |
| **MeasuringWorth** | Economic | 1790–present (US) | ACADEMIC | **No** without separate licence |
| **Reinhart-Rogoff** | Economic | 1800–present | FREE-OPEN | **Yes**, with citation |
| **Shiller (Yale)** | Economic | 1871–present (US) | FREE-OPEN | **Yes**, with citation |
| **Garriga CBI** | Economic | 1970–2017 | FREE-REG (Academic) | **Probably**, verify with author |
| **GSDB Sanctions** | Economic | 1950–2022 | FREE-OPEN (CC0 1.0) | **Yes**, unrestricted |
| **Mitchell's Stats** | Social | ~1919–1959 | COMMERCIAL | **No** without publisher licence |
| **EM-DAT** | Environmental | 1900–present | FREE-REG (Non-Commercial) | **No** without CRED licence |
| **HadCRUT5** | Environmental | 1850–present | FREE-OPEN (OGL v3) | **Yes**, with attribution |

### 5.1 Minimum Viable Commercial Configuration

For a commercial product seeking to avoid all restrictive licences, the following "fully free" subset provides coverage:

- **Political Pillar:** WGI (CC-BY 4.0) + Polity5 + V-Dem (CC-BY-SA) + COW + UCDP → 1789–present
- **Economic Pillar:** Maddison + Reinhart-Rogoff + Shiller + GSDB → 1820–present (1871 for Shiller CPI)
- **Social Pillar:** V-Dem suffrage + civil liberties (CC-BY-SA) + Maddison GDP/pc (as HDI proxy) → 1820–present
- **Environmental Pillar:** HadCRUT5 → 1850–present

This configuration omits MeasuringWorth (1790 US GDP), Mitchell (unemployment), EM-DAT (disasters), and requires caution with Garriga (CBI).  The primary sacrifice is the loss of the EM-DAT disaster component of the environmental pillar and pre-1820 US GDP data.

### 5.2 V-Dem CC-BY-SA 4.0 Implications

V-Dem is the most heavily used dataset in the GRRI extension (political governance, democracy, civil liberties, suffrage).  Its CC-BY-SA 4.0 licence requires that derivative works incorporating V-Dem data be shared under the same or a compatible licence.  For a commercial risk product, this means:

1. **Attribution** must be provided to the V-Dem Institute in documentation and disclosures.
2. **Share-alike** requires that the specific derived indicators (not the entire product) be available under CC-BY-SA terms if distributed.

In practice, most commercial implementations can satisfy share-alike by publishing the methodology and transformation of V-Dem data (as this paper does) while keeping the proprietary weighting, composite scoring, and product interface proprietary.  Legal counsel should review the specific deployment architecture.

---

## 6. Implementation Architecture

### 6.1 Module Structure

The implementation follows the design pattern established in the MAC framework's `HistoricalDataProvider`:

```
grri_mac/grri/
    __init__.py              # Module exports
    modifier.py              # GRRI → modifier logistic transformation
    data_fetchers.py         # Modern API clients (IMF, WGI, HDI, V-Dem)
    governance_quality.py    # Regime classification, WGI scoring, momentum detection
    historical_sources.py    # Historical data loaders + GRRIHistoricalProvider
    historical_proxies.py    # Proxy chain documentation (GRRIProxyConfig)
```

### 6.2 GRRIHistoricalProvider Class

The `GRRIHistoricalProvider` class is the primary interface for consumers:

```python
from grri_mac.grri.historical_sources import GRRIHistoricalProvider

provider = GRRIHistoricalProvider()

# Single country-year
result = provider.get_historical_grri("USA", 1929)
# Returns: {
#   "country": "USA",
#   "year": 1929,
#   "resilience": 0.6842,
#   "modifier": 0.6321,
#   "pillar_scores": {"political": 0.85, "economic": 0.52, ...},
#   "provenance": {"political": ["Polity5 (1800-2018)", ...], ...}
# }

# Time series
df = provider.get_historical_grri_timeseries("GBR", 1850, 1950)
# Returns DataFrame: year | resilience | modifier | political | economic | social | environmental
```

### 6.3 Data Loading Protocol

Each data loader follows a defensive pattern:

1. Check for expected file on disk; return `None` if absent.
2. Parse CSV/XLS with standardised column normalisation.
3. Filter by country code (supporting multiple naming conventions).
4. Log the number of observations loaded.
5. Cache result in the provider's `_cache` dictionary.

This enables graceful degradation: if a dataset is not downloaded, the corresponding sub-indicator is simply omitted from the composite, and the weights are re-normalised over available components.

### 6.4 Data Acquisition

A companion script, `download_grri_historical_data.py`, automates acquisition of publicly downloadable datasets:

- **Auto-download:** HadCRUT5 (Met Office CSV), Maddison (XLSX), UCDP (ZIP archive from Uppsala)
- **Manual download** (requires registration or gated access): Polity5, V-Dem, COW, Reinhart-Rogoff, EM-DAT, Garriga CBI, GSDB

The `--check` flag reports which datasets are present and which are missing; the `--manual-instructions` flag prints detailed step-by-step download instructions for gated datasets.

---

## 7. Validation Considerations

### 7.1 Overlap-Period Validation

For each proxy chain, the correlation estimate is computed during the overlap period where both the proxy and the modern indicator are available.  These correlations should be re-validated as modern data extends:

| Proxy → Target | Overlap Period | Reported $r$ | Notes |
|----------------|---------------|------------|-------|
| Polity5 → WGI | 1996–2018 | 0.82 | Cross-sectional across 167 countries |
| V-Dem rule → WGI | 1996–2023 | 0.91 | 202 countries |
| V-Dem polyarchy → WGI V&A | 1996–2023 | 0.93 | 202 countries |
| Maddison GDP growth → IMF WEO | 1980–2018 | 0.78 | 169 countries, 5yr CAGR |
| EM-DAT severity → INFORM | 2012–2023 | 0.65 | Indirect; short overlap |
| HadCRUT5 trend → INFORM | 2012–2023 | 0.60 | Very indirect |

### 7.2 Historical Stress Testing

The extended GRRI can be validated against known episodes of country-level resilience failure:

| Episode | Country | Year | Expected GRRI | Key Proxy Test |
|---------|---------|------|---------------|----------------|
| Weimar hyperinflation | DEU | 1923 | Very Low (<0.3) | R-R inflation crisis + Polity5 instability |
| Great Depression onset | USA | 1930 | Moderate → Low | Maddison GDP decline + unemployment |
| UK leaves gold standard | GBR | 1931 | Moderate | Polity5 stable democracy + economic stress |
| Argentina military coups | ARG | 1976 | Low | Polity5 −9 + R-R crises |
| Japan post-bubble | JPN | 1992 | Moderate-High | Stable Polity + declining GDP growth |
| Russian default | RUS | 1998 | Low | Polity5 transition + R-R multiple crises |

### 7.3 Known Limitations

1. **Environmental pillar is thin before 1900.**  EM-DAT starts 1900; HadCRUT5 starts 1850.  Between 1850–1899, only the climate trend component is available.  Before 1850, the environmental pillar is excluded entirely, and the GRRI is computed from three pillars.

2. **Social pillar misses health and education before 1990.**  The Crafts-style HDI proxy uses income and suffrage but lacks life expectancy and literacy data.  This is the single largest source of measurement error.

3. **Expert-coded historical data.**  Both Polity5 and V-Dem rely on expert retrospective coding for their earliest observations.  Inter-coder reliability statistics are available from V-Dem; Polity5 does not publish reliability metrics for pre-1900 periods.

4. **Pre-1870 data is very sparse.**  Before 1870, only Polity5, V-Dem, COW, and Maddison (for a handful of countries) provide data.  The GRRI for this period should be treated as indicative rather than precise.

5. **Country boundary changes.**  Historical datasets use contemporaneous country definitions, which do not always map cleanly to modern ISO-3 codes.  Germany before 1871, Austria-Hungary before 1918, and the Soviet Union require careful country-matching logic.

---

## 8. Comparison with MAC Historical Extension

The GRRI historical extension parallels the MAC framework's historical proxy chains but addresses a fundamentally different measurement domain:

| Dimension | MAC Proxies | GRRI Proxies |
|-----------|-------------|--------------|
| **Domain** | Financial-market microstructure (spreads, vol, leverage) | Country-level structural resilience |
| **Temporal granularity** | Weekly/monthly (interpolated from monthly NBER data) | Annual (matching source granularity) |
| **Primary era challenge** | Pre-Fed (before 1913): no central bank, no modern credit markets | Pre-WGI (before 1996): no governance surveys |
| **Most transformative source** | Schwert (1989) volatility, 1802–1987 | Polity5 + V-Dem, 1789–present |
| **Weakest era** | 1802–1857 (only Schwert vol + gold prices) | Pre-1870 (only political + sparse economics) |
| **Design pattern** | `HistoricalDataProvider` with `_lookup()` helper | `GRRIHistoricalProvider` with `_lookup_annual()` |

Both extensions use the same `ProxyConfig` / `GRRIProxyConfig` data structure pattern and the same cache-aware lazy-loading architecture.

---

## 9. Adaptive Pillar Weighting for GRRI

### 9.1 Motivation: Beyond Equal Weights

The baseline GRRI uses equal weights across its four pillars ($w_j = 0.25$).  This is a robust default — interpretable, unbiased, and requiring no training data.  However, MAC's experience demonstrates that ML-optimised weights can substantially improve crisis prediction.  MAC's gradient boosting weight optimisation on 14 crisis scenarios (Section 6.2 of the MAC Methodology Document) identified positioning (22%) as the dominant pillar and policy (9%) as the weakest, with LOOCV $R^2$ confirming the improvement over equal weighting.

The question is whether the same class of techniques can be applied to GRRI's four pillars — Political, Economic, Social, Environmental — given the structural differences between the two frameworks.

The following diagram provides an overview of the three methodological enhancements (Sections 9–11) and their interconnection:

```mermaid
flowchart TD
    subgraph Data["Historical Pillar Scores"]
        HS["4 GRRI Pillars<br/>1870–2025"]
        CRISIS["Crisis Labels<br/>(Reinhart-Rogoff)"]
    end

    subgraph Weighting["Adaptive Pillar Weighting (§9)"]
        AUG["Augmentation<br/>bootstrap + noise"]
        GBM["Gradient Boosting<br/>(GBM or XGBoost)"]
        FEAT["4 base features<br/>+ 3 interactions"]
        LOO["Leave-One-Out<br/>Cross-Validation"]
        WT["Optimised Weights<br/>wₚ, wₑ, wₛ, wₙ"]
    end

    subgraph MonteCarlo["Monte Carlo Simulation (§10)"]
        DIST["Per-pillar<br/>distributions<br/>(skew-t / GPD)"]
        COP["Copula<br/>(Gaussian/t)"]
        SIM["10,000 joint<br/>pillar draws"]
        GRRI_MC["GRRI(ω)<br/>distribution"]
        CI["95% CI and<br/>tail risk VaR"]
    end

    subgraph Independence["Independence Analysis (§11)"]
        MI_G["MI / NMI<br/>pairwise"]
        HSIC_G["HSIC<br/>kernel test"]
        MIC_G["MIC<br/>grid search"]
        TC_G["Total Correlation<br/>system redundancy"]
        DEC_G["Decorrelation<br/>if NMI > 0.35"]
    end

    HS --> AUG
    CRISIS --> AUG
    AUG --> GBM
    GBM --> FEAT
    FEAT --> LOO
    LOO --> WT

    HS --> DIST
    DIST --> COP
    COP --> SIM
    SIM --> GRRI_MC
    GRRI_MC --> CI

    HS --> MI_G
    HS --> HSIC_G
    HS --> MIC_G
    MI_G --> TC_G
    HSIC_G --> TC_G
    MIC_G --> TC_G
    TC_G --> DEC_G

    DEC_G -.->|"orthogonalised<br/>pillars"| GBM
    DEC_G -.->|"updated copula<br/>parameters"| COP
```

*Figure 2. Overview of the three methodological enhancements.  Dependence analysis (§11) feeds back into both adaptive weighting (§9) and Monte Carlo (§10) by providing orthogonalised pillar scores and empirically-calibrated copula parameters.*

### 9.2 MAC Weighting Methodology (Transplantable Components)

MAC's weight optimisation pipeline (`grri_mac.mac.ml_weights`, `grri_mac.mac.ml_weights_xgb`) consists of three components:

**1. Feature Interaction Encoding.**  Beyond the base pillar scores, pairwise interaction features (products of pillar pairs) are included as additional regressors.  For MAC's 7 pillars, this adds 6 theory-driven interaction pairs — e.g., `positioning × volatility` captures forced unwinding dynamics, `policy × contagion` captures constrained intervention during global crises.

For GRRI's 4 pillars, the interaction space is smaller: $\binom{4}{2} = 6$ pairs, exhaustively:

| Interaction | Hypothesised Mechanism |
|------------|----------------------|
| Political × Economic | Regime instability amplifies financial fragility (e.g., sovereign default during revolution) |
| Political × Social | Governance failure compounds social stress (e.g., authoritarian response to inequality) |
| Political × Environmental | Weak governance impairs disaster response capacity |
| Economic × Social | Poverty amplifies social fragility; inequality destabilises growth |
| Economic × Environmental | Environmental shocks compound economic weakness (e.g., agricultural failures) |
| Social × Environmental | Marginalised populations bear disproportionate environmental risk |

**2. Gradient Boosting Regressor.**  A shallow gradient boosting regressor (`max_depth=2`, `n_estimators=50`, `learning_rate=0.1`) is fit to predict a target variable (crisis severity or resilience outcome) from the feature matrix.  Feature importances are extracted and normalised to produce pillar weights.

**3. XGBoost with Bayesian Hyperparameter Search.**  The `XGBWeightOptimizer` extends this with Optuna-based hyperparameter search across learning rate, tree depth, regularisation, and subsampling parameters, using 5-fold time-series cross-validation.

**4. Leave-One-Out Cross-Validation (LOOCV).**  Given a small training set (MAC uses 14–35 crisis scenarios), LOOCV provides an honest out-of-sample performance estimate.  Each scenario is held out once, and the model is retrained on the remaining $N-1$ observations.

### 9.3 Adaptation to GRRI

Applying these techniques to GRRI requires:

**Training targets.**  While MAC targets crisis severity (a continuous 0–1 score derived from the Crisis Severity Rubric), GRRI targets must reflect how well a country's resilience profile predicted actual crisis outcomes.  Candidate targets include:

- **GDP drawdown depth** during identified crises (Maddison/Reinhart-Rogoff)
- **Regime change within $k$ years** (Polity5 transitions)
- **Conflict onset probability** (COW/UCDP)
- **Composite crisis incidence** from Reinhart-Rogoff (banking + currency + debt crises)

**Training set construction.**  The historical extension provides 155 years of annual data (1870–2025).  Known crisis events can be identified from Reinhart-Rogoff (which flags banking crises, currency crises, debt crises, and inflation crises by country-year).  For 5 major countries with full coverage, this yields approximately 30–50 crisis observations — substantially more than MAC's 14-scenario training set.

**Proposed GRRI weight optimisation pipeline:**

$$\hat{w} = \arg\min_{w} \sum_{i=1}^{N} \mathcal{L}\!\left(\text{GRRI}_{w}(i),\; \text{CrisisTarget}(i)\right)$$

where $\text{GRRI}_{w}(i) = \sum_{j=1}^{4} w_j \cdot P_j(i) + \sum_{(j,k)} w_{jk} \cdot P_j(i) \cdot P_k(i)$ and $\mathcal{L}$ is the mean squared error loss under LOOCV.

### 9.4 Bootstrap Confidence Intervals for GRRI

MAC's `bootstrap_mac_ci()` function (`grri_mac.mac.confidence`) simultaneously perturbs three uncertainty sources:

1. **Indicator measurement error** — proxy-tier-dependent Gaussian noise ($\sigma = 0.01$ for native data to $\sigma = 0.15$ for expert estimates)
2. **Weight instability** — Gaussian perturbation of ML weights ($\sigma = 0.03$)
3. **Calibration factor uncertainty** — perturbed $\alpha$ from LOOCV residual variance

For GRRI, the dominant uncertainty source is **proxy measurement error**, which is substantially larger than for MAC.  Recommended noise tiers for GRRI:

| Data Quality | $\sigma$ (noise std) | Example |
|-------------|---------------------|---------|
| Direct measurement | 0.02 | Polity5 score (1800+), Maddison GDP (1820+) |
| Derived composite | 0.05 | Economic diversity proxy, Social Development Index |
| Historical estimate | 0.10 | Pre-1900 temperature anomalies, unemployment estimates |
| Expert heuristic | 0.15 | Pre-gold-standard CB independence, pre-EM-DAT disasters |

The bootstrap for a single GRRI score would generate $B = 1000$ replicates:

$$\text{GRRI}^{(b)} = \sum_{j=1}^{4} \widetilde{w}_j^{(b)} \cdot \text{clip}\!\left(P_j + \epsilon_j^{(b)}, 0, 1\right), \quad \epsilon_j^{(b)} \sim \mathcal{N}(0, \sigma_j^2)$$

yielding 80%, 90%, and 95% confidence bands.  We expect wider bands for pre-1900 observations ($\text{CI}_{90} \approx \pm 0.12$) than for post-1970 ones ($\text{CI}_{90} \approx \pm 0.04$), reflecting the proxy chain's progressive degradation.

### 9.5 When ML Weighting Adds Value for GRRI

MAC's experience provides a calibrated expectation.  ML weights improved MAC's RMSE by ~10% over equal weights, but only in the modern era (2006+) with all 7 pillars active.  In the pre-1971 historical period, equal weights were retained because:

- Fewer active pillars reduce the degrees of freedom for optimisation
- Proxy noise swamps the signal that ML could extract
- Era-specific structural changes (gold standard, Bretton Woods) mean that weights optimised on one era may not transfer

**Recommendation for GRRI:**  Begin with equal weights as the production default.  Use ML-optimised weights only when:
1. At least 3 of 4 pillars have non-heuristic data (post-1900 for most countries)
2. The LOOCV $R^2$ exceeds 0.30 (demonstrating that the optimiser captures signal, not noise)
3. The weight deviation from equal is large enough to matter (average $|w_j - 0.25| > 0.05$)

---

## 10. Historically-Informed Monte Carlo Simulation

### 10.1 Motivation

MAC's Monte Carlo module (`grri_mac.predictive.monte_carlo`) simulates shock propagation under different regime states, demonstrating that the same exogenous shock produces qualitatively different outcomes depending on current absorption capacity.  A 2$\sigma$ liquidity shock under Ample conditions produces ~30% direct impact with minimal spillover; under Breach conditions, the same shock produces ~90% direct impact with 70% spillover, amplified 4×.

The GRRI historical extension creates a unique opportunity: with 155 years of annual pillar-level data across multiple countries, we can **calibrate Monte Carlo simulations using historically observed distributions** rather than assumed parameters.

### 10.2 Historical Distribution Calibration

The standard Monte Carlo approach uses assumed distributions for shock parameters.  The historically-informed approach replaces these with empirical distributions derived from the GRRI time series.

**Step 1: Extract pillar-level change distributions.**

For each pillar $j$ and country $c$, compute the first differences:

$$\Delta P_{j,c}(t) = P_{j,c}(t) - P_{j,c}(t-1)$$

over the full 1870–2025 period.  This yields ~155 observations per pillar per country, or ~775 pooled observations across 5 core countries (US, UK, France, Germany, Japan).

**Step 2: Fit parametric distributions.**

Annual GRRI pillar changes are expected to be:
- **Politically**: Heavy-tailed (rare regime changes produce extreme jumps).  Fit a $t$-distribution or stable distribution.
- **Economically**: Moderately fat-tailed.  Fit a normal-inverse Gaussian or skew-$t$.
- **Socially**: Approximately normal (slow-moving indices).  Fit normal with variance $\sigma^2$.
- **Environmentally**: Right-skewed (disaster years).  Fit a mixture model: normal baseline + rare Poisson-intensity shocks.

**Step 3: Estimate cross-pillar dependency structure.**

Rather than assuming independence or fixed correlations, compute the empirical copula from the multivariate $(\Delta P_1, \Delta P_2, \Delta P_3, \Delta P_4)$ vector.  A Gaussian copula provides a reasonable starting point; a $t$-copula captures tail dependence more accurately.

### 10.3 Regime-Conditional Simulation

Following MAC's regime taxonomy, define GRRI regimes:

| GRRI Level | Regime | Interpretation |
|-----------|--------|----------------|
| $\geq 0.70$ | **Resilient** | Strong institutional buffers; shocks absorbed |
| 0.50–0.70 | **Moderate** | Partial buffers; some shock amplification |
| 0.30–0.50 | **Fragile** | Weakened institutions; significant amplification |
| $< 0.30$ | **Brittle** | Institutional collapse risk; non-linear regime |

The Monte Carlo simulation then proceeds:

1. Sample initial GRRI state vector $\mathbf{P}_0 = (P_1^0, P_2^0, P_3^0, P_4^0)$
2. Determine regime from composite GRRI score
3. Apply regime-dependent transmission coefficients (analogous to MAC's `TRANSMISSION_COEFFICIENTS`):

| Regime | Direct Impact | Cross-Pillar Spillover | Amplification |
|--------|--------------|----------------------|---------------|
| Resilient | 0.25 | 0.10 | 1.0× |
| Moderate | 0.45 | 0.25 | 1.5× |
| Fragile | 0.70 | 0.50 | 2.5× |
| Brittle | 0.90 | 0.75 | 4.0× |

4. Draw shock vector $\boldsymbol{\Delta}$ from the historically-calibrated copula
5. Apply MAC's non-linear threshold effects: when any pillar breaches its critical level, transmission accelerates
6. Compute $\mathbf{P}_1 = \text{clip}(\mathbf{P}_0 + \boldsymbol{\Delta}, 0, 1)$
7. Repeat for $T$ periods to generate paths; aggregate over $B$ bootstrap iterations

### 10.4 Cross-Pillar Shock Propagation Matrix

MAC's `INTERACTION_MATRIX` (`grri_mac.predictive.shock_propagation`) defines how stress in one pillar cascades to others.  For GRRI, the propagation matrix encodes historically-observed transmission channels:

$$\mathbf{A}_{\text{GRRI}} = \begin{pmatrix}
0.00 & 0.35 & 0.40 & 0.10 \\
0.30 & 0.00 & 0.25 & 0.20 \\
0.25 & 0.30 & 0.00 & 0.15 \\
0.10 & 0.25 & 0.20 & 0.00
\end{pmatrix}$$

where rows are shock source pillars (Political, Economic, Social, Environmental) and columns are receiving pillars.  Key transmission channels:

- **Political → Social (0.40):** Regime instability erodes civil liberties, education, health spending
- **Political → Economic (0.35):** Regime change disrupts trade, investment, monetary policy
- **Economic → Political (0.30):** Economic crisis precipitates government collapse (Weimar, Argentina)
- **Economic → Social (0.30):** Recession increases unemployment, inequality, mortality
- **Social → Political (0.25):** Inequality and unrest trigger regime transitions
- **Environmental → Economic (0.25):** Natural disasters destroy capital stock, disrupt agriculture

These coefficients can be calibrated empirically from the historical time series using vector autoregression (VAR) on the annual pillar scores.

### 10.5 Validation Against Known Historical Episodes

The Monte Carlo framework can be validated by comparing simulated distributions against observed pillar trajectories during known crisis episodes:

| Episode | Year(s) | Expected Dynamics | Validation Criterion |
|---------|---------|-------------------|---------------------|
| World War I | 1914–1918 | Political → Economic → Social cascade | Simulated cascade captures GDP decline and regime transitions |
| Great Depression | 1929–1933 | Economic → Political → Social cascade | Simulated economic shock propagates to political instability (Weimar) |
| World War II | 1939–1945 | Multi-pillar simultaneous shock | Simulated extreme draws match observed ΔP magnitudes |
| Decolonisation era | 1945–1970 | Political regime changes → social transformation | Simulated political shocks produce social pillar improvements (in some cases) |
| Oil crises | 1973–1979 | Environmental/Economic → Political | Simulated energy shock cascades match observed patterns |
| Fall of USSR | 1989–1991 | Political → Economic → Social cascade | Simulated regime collapse produces economic and social deterioration |

### 10.6 Implementation Note

The proposed Monte Carlo module would extend `grri_mac.predictive.monte_carlo.MonteCarloSimulator` with:
- A `GRRIMonteCarloSimulator` subclass that uses 4 pillars instead of 6
- Historical distribution loaders from `GRRIHistoricalProvider.get_historical_grri_timeseries()`
- Copula estimation using rank-transformed empirical data
- Regime-conditional transmission using the GRRI interaction matrix

The implementation is straightforward given the existing MAC infrastructure; the primary value-add is the historical calibration rather than assumed parameters.

---

## 11. Independence Structure and Dependence Analysis

### 11.1 The Independence Assumption

Equal pillar weighting implicitly assumes that the four GRRI pillars capture **orthogonal** dimensions of resilience.  If two pillars are strongly correlated, equal weighting effectively double-counts the shared signal, biasing the composite.  MAC addresses this for its private credit pillar via explicit decorrelation (rolling OLS against equity/credit factors, `grri_mac.pillars.private_credit_decorrelation`), extracting the orthogonal residual before scoring.

For GRRI, the question is more structural: the same underlying datasets contribute to multiple pillars.  Specifically:

| Dataset | Primary Pillar | Secondary Pillar | Shared Information |
|---------|---------------|------------------|--------------------|
| Maddison GDP/capita | Economic (growth) | Social (HDI proxy) | Income level drives both economic and social scores |
| V-Dem | Political (governance, democracy) | Social (civil liberties, suffrage) | V-Dem's liberal component index spans both political rights and social participation |
| Polity5 | Political (regime type) | Social (constraints) | Executive constraints affect both governance quality and social freedom |
| HadCRUT5 | Environmental (climate) | Economic (agriculture) | Temperature anomalies affect both environmental exposure and economic output |

This creates **embedded correlations** that must be quantified before weights can be interpreted.

### 11.2 Dependence Metrics

We propose three complementary metrics, each capturing a different aspect of statistical dependence.  The following diagram summarises what each metric captures and its blind spots:

```mermaid
flowchart TD
    subgraph Metrics["Three Complementary Metrics"]
        direction TB
        MI["<b>Mutual Information</b><br/>I(X;Y) = H(X)+H(Y)−H(X,Y)<br/>• Model-free, entropy-based<br/>• Captures ALL dependence<br/>• = 0 ⟺ independence"]
        HSIC["<b>HSIC</b><br/>tr(K_X H K_Y H) / (n−1)²<br/>• Kernel-based (RKHS)<br/>• Powerful for complex shapes<br/>• Permutation p-value"]
        MIC["<b>MIC</b><br/>max I(X;Y)/log₂ min(n_x,n_y)<br/>• Equitable explorer<br/>• Same score = same noise<br/>• Detects any functional form"]
    end

    subgraph Captures["What Each Captures"]
        direction TB
        C1["MI: Total shared<br/>information (bits)"]
        C2["HSIC: Distribution-level<br/>embedding similarity"]
        C3["MIC: Functional vs<br/>random relationship"]
    end

    subgraph Blind["Blind Spots"]
        direction TB
        B1["MI: Bin-sensitive<br/>with small N"]
        B2["HSIC: Bandwidth<br/>choice matters"]
        B3["MIC: Computational<br/>cost O(n^2α)"]
    end

    MI --> C1
    HSIC --> C2
    MIC --> C3

    MI --> B1
    HSIC --> B2
    MIC --> B3

    C1 --> AGREE{"All three<br/>agree?"}
    C2 --> AGREE
    C3 --> AGREE

    AGREE -->|"Yes: high"| DEP["Strong dependence<br/>→ decorrelate"]
    AGREE -->|"Yes: low"| IND["Independent<br/>→ orthogonal ✓"]
    AGREE -->|"No"| INV["Investigate:<br/>non-linear structure"]
```

*Figure 3. Decision framework for interpreting dependence metric agreement.  When all three metrics agree, the conclusion is unambiguous; disagreement signals non-standard dependence structures requiring further investigation.*

#### 11.2.1 Mutual Information (MI)

Mutual information quantifies the total (linear + non-linear) dependence between two random variables:

$$I(X; Y) = \sum_{x \in \mathcal{X}} \sum_{y \in \mathcal{Y}} p(x, y) \log\!\frac{p(x, y)}{p(x)\, p(y)}$$

For continuous pillar scores, we discretise into $k$ equiprobable bins (recommended $k = \lceil N^{1/3} \rceil$ for $N$ observations, i.e., $k \approx 5$ for 155 years) and compute the empirical MI.  Alternatively, use a $k$-NN estimator (Kraskov et al., 2004) which avoids binning artefacts.

**Interpretation:**  $I(X; Y) = 0$ implies independence; $I(X; Y) = H(X)$ implies $X$ is fully determined by $Y$.  Normalised MI $\text{NMI} = 2I(X;Y) / (H(X) + H(Y))$ ranges from 0 to 1.

**Expected findings for GRRI:**

| Pair | Expected NMI | Rationale |
|------|-------------|-----------|
| Political–Economic | 0.15–0.30 | Moderate: regime stability correlates with growth, but not deterministically |
| Political–Social | 0.25–0.40 | High: V-Dem and Polity5 span both pillars; liberal democracy ↔ civil liberties |
| Political–Environmental | 0.05–0.10 | Low: governance and climate are largely independent |
| Economic–Social | 0.20–0.35 | Moderate-high: GDP/capita drives HDI proxy; Maddison is shared |
| Economic–Environmental | 0.08–0.15 | Low-moderate: HadCRUT affects agriculture → GDP only indirectly |
| Social–Environmental | 0.05–0.12 | Low: EM-DAT deaths correlate weakly with social development |

#### 11.2.2 HSIC (Hilbert–Schmidt Independence Criterion)

HSIC is a kernel-based measure of statistical dependence that operates in a reproducing kernel Hilbert space (RKHS).  Unlike MI, it does not require discretisation and naturally captures non-linear dependencies.

$$\text{HSIC}(X, Y) = \frac{1}{(n-1)^2} \text{tr}(\mathbf{K}_X \mathbf{H} \mathbf{K}_Y \mathbf{H})$$

where $\mathbf{K}_X$ and $\mathbf{K}_Y$ are RBF kernel matrices computed on the pillar score vectors, $\mathbf{H} = \mathbf{I} - \frac{1}{n}\mathbf{1}\mathbf{1}^\top$ is the centering matrix, and $n$ is the number of observations.

**Implementation:**  For RBF kernels $k(x, x') = \exp(-\|x - x'\|^2 / 2\sigma^2)$, the bandwidth $\sigma$ is set using the median heuristic: $\sigma = \text{median}(\|x_i - x_j\|)$.

**Permutation test:**  To assess significance, permute one pillar's scores $M = 1000$ times and recompute HSIC.  If the observed HSIC exceeds the 95th percentile of the null distribution, the pillars are significantly dependent.

**Advantages over MI:**
- No binning required
- Consistent test of independence (converges with sample size)
- Captures all orders of dependence (not just pairwise)

#### 11.2.3 MIC (Maximal Information Coefficient)

MIC (Reshef et al., 2011) is an equitability-based measure that captures a wide range of functional and non-functional associations with equal power.

$$\text{MIC}(X, Y) = \max_{|G| < B(n)} \frac{I^*(X, Y; G)}{\log \min(|G_X|, |G_Y|)}$$

where $I^*(X, Y; G)$ is the maximum MI achieved over all bivariate grids $G$ of bounded cardinality $B(n) = n^{0.6}$, and $|G_X|$, $|G_Y|$ are the grid dimensions.

**Interpretation:** MIC ∈ [0, 1].  MIC ≈ 0 implies independence; MIC ≈ 1 implies a deterministic (possibly non-linear) relationship.  The **equitability** property means that MIC assigns similar scores to relationships of similar noise level, regardless of the functional form.

**Python implementation:** Available via the `minepy` package (Albanese et al., 2013), which provides `MINE` statistics including MIC, MAS (Maximum Asymmetry Score), and MEV (Maximum Edge Value).

### 11.3 Cross-Pillar Dependence Analysis Protocol

We propose the following analysis pipeline:

**Step 1: Compute pairwise metrics.**  For each of the 6 pillar pairs and each of the 3 metrics (MI, HSIC, MIC), compute the dependence statistic on the full 1870–2025 time series, separately for:
- Pooled (all countries)
- Per-country (US, UK, France, Germany, Japan)

**Step 2: Temporal stability analysis.**  Compute rolling dependence metrics over 30-year windows to assess whether the correlation structure is stationary:

$$\text{NMI}_{30}(t) = \text{NMI}\!\left(P_j[t-30:t],\; P_k[t-30:t]\right)$$

This reveals whether, e.g., the Political–Social correlation strengthened after the UN Declaration of Human Rights (1948) or the end of the Cold War (1991).

**Step 3: Significance testing.**  For each pair, conduct a permutation test (1000 bootstraps) and report $p$-values.

**Step 4: Conditional independence.**  Test whether $P_j \perp P_k \mid P_l$ — i.e., whether the dependence between two pillars vanishes after conditioning on a third.  This distinguishes direct dependence from confounded dependence.

### 11.4 Known Embedded Correlations and Mitigation

Based on the data source analysis in Section 3, we identify three embedded correlations requiring attention:

**Correlation 1: Maddison GDP ↔ Social Development Index.**

Maddison GDP per capita appears in the Economic pillar (via `get_economic_diversity_proxy()`) and in the Social pillar (via the HDI proxy, which uses GDP/capita as one of three components).

*Mitigation options:*
- **Residual scoring:** Regress Social Development Index on GDP/capita and use the residual as the social component, analogous to MAC's private credit decorrelation
- **Component exclusion:** Remove the income component from the HDI proxy within the Social pillar, retaining only life expectancy and education metrics
- **Weight adjustment:** If MI between Economic and Social pillars exceeds a threshold (e.g., NMI > 0.35), reduce the combined weight to avoid double-counting

**Correlation 2: V-Dem Political ↔ V-Dem Social.**

V-Dem's liberal component index (`v2x_liberal`) and its civil liberties index contribute to both the Political and Social pillars.

*Mitigation options:*
- **Indicator separation:** Assign V-Dem electoral democracy (`v2x_polyarchy`) and executive constraints to the Political pillar exclusively, and civil liberties (`v2x_clpol`) and suffrage to the Social pillar exclusively
- **PCA decomposition:** Extract principal components from V-Dem indicators and assign orthogonal components to separate pillars
- **Regularisation:** Accept the overlap but apply a penalty $\pi_{\text{overlap}} = \lambda \cdot \text{NMI}(P_{\text{pol}}, P_{\text{soc}})$ to the composite score

**Correlation 3: HadCRUT5 Temperature ↔ Economic Output.**

Temperature anomalies affect agricultural output (and hence GDP) particularly in the pre-industrial era, creating a physical channel of dependence.

*Mitigation:*  This is a **causal** (not artefactual) correlation — environmental stress genuinely causes economic damage.  It should not be decorrelated, as it reflects a real-world transmission mechanism.  However, it should be **documented** so that users understand that part of the GRRI's sensitivity to environmental shocks is already captured in the economic pillar.

### 11.5 Decorrelation Framework: Transplanting MAC's Approach

MAC's private credit decorrelation pipeline (`grri_mac.pillars.private_credit_decorrelation.PrivateCreditDecorrelator`) provides a template:

1. **Rolling OLS:** Regress the dependent signal on the confounding factors
2. **Extract residual:** $\epsilon_t = y_t - \hat{y}_t$ is the orthogonal (pillar-specific) component
3. **Standardise:** $z_t = \epsilon_t / \sigma(\epsilon)_{\text{rolling}}$
4. **EWMA smooth:** Apply exponentially-weighted moving average to reduce noise

For GRRI, the analogous pipeline for the Social pillar would be:

$$\text{Social}_{\text{raw}}(t) = \beta_0 + \beta_1 \cdot \text{GDP/capita}(t) + \beta_2 \cdot \text{Polity5}(t) + \epsilon(t)$$

$$\text{Social}_{\text{orthogonal}}(t) = \sigma^{-1}(\epsilon) \cdot \epsilon(t)$$

This removes the Economic and Political components from the Social pillar score, isolating the **genuinely social** signal (health, education, civil liberties net of income and governance).

### 11.6 Entropy-Based Redundancy Analysis

Beyond pairwise dependence, we can assess the **total redundancy** in the 4-pillar system using total correlation (Watanabe, 1960):

$$C(P_1, P_2, P_3, P_4) = \sum_{j=1}^{4} H(P_j) - H(P_1, P_2, P_3, P_4)$$

where $H(\cdot)$ denotes entropy.  Total correlation $C = 0$ implies the four pillars are jointly independent; $C > 0$ quantifies the bits of shared information.

The **dual total correlation** (Han, 1975) decomposes this further:

$$D(P_1, P_2, P_3, P_4) = H(P_1, P_2, P_3, P_4) - \sum_{j=1}^{4} H(P_j \mid P_{\neg j})$$

Together, $C$ and $D$ characterise whether the redundancy is dominated by pairwise correlations (high $C$, low $D$) or synergistic interactions (high $D$).

### 11.7 Expected Outcomes and Implications

Based on the structural analysis of data sources and known overlaps, we hypothesise:

1. **Political–Social will show the highest dependence** (NMI ~ 0.30–0.40) due to shared V-Dem indicators.  This pair is the primary candidate for decorrelation.

2. **Economic–Social will show moderate dependence** (NMI ~ 0.20–0.30) due to shared Maddison GDP.  Residual scoring of the Social pillar's income component would reduce this.

3. **Environmental will be approximately independent** of other pillars (NMI < 0.10), confirming that it captures a genuinely distinct dimension.

4. **Total correlation will be modest** (estimated $C \approx 0.5$–$1.0$ bits), suggesting that the 4-pillar structure captures mostly non-redundant information despite the data overlaps.

5. **The decorrelation benefit will be moderate** — expected RMSE improvement of 3–8% on crisis prediction tasks, smaller than MAC's ML weight improvement (~10%) because GRRI's equal weights are already a reasonable approximation for a 4-pillar system.

If these hypotheses are confirmed empirically, the recommended production configuration is:

- **Default:** Equal weights (0.25 each), no decorrelation — simple, interpretable, robust
- **Research/advanced:** Decorrelated Social pillar + ML-optimised weights where LOOCV $R^2 > 0.30$
- **Always report:** Pairwise NMI and HSIC as diagnostics, flagging any pair with NMI > 0.35

---

## 12. Geopolitical Event Analysis: Historical Validation

### 12.1 Methodology

To validate the enhanced political pillar across diverse regime types, conflict intensities, and historical periods, we compute the enhanced political score for 22 major geopolitical events spanning 1815–2023.  For each event, we identify the principal countries involved and apply the `compute_enhanced_political_score()` function using:

- **Polity5 polity2** values from the published dataset (Marshall & Gurr, 2020)
- **Expert governance effectiveness** anchors calibrated from state capacity literature (Besley & Persson, 2011; Dincecco, 2017; Acemoglu & Robinson, 2012)
- **GDP per capita** from the Maddison Project Database (Bolt & van Zanden, 2020)
- **Conflict intensity** scaled 0–1 from COW interstate war data (Sarkees & Wayman, 2010) and UCDP battle-related deaths (Pettersson & Öberg, 2020)
- **Regime durability** from Polity5 `durable` field
- **WGI estimates** (World Bank published point estimates) for post-1996 events

The five-component weighted score is:
$$\text{Political Score} = 0.25 \cdot \text{GE} + 0.25 \cdot \text{PV} + 0.25 \cdot \text{IQ} + 0.15 \cdot (1 - C) + 0.10 \cdot \text{RS}$$

where GE = Governance Effectiveness, PV = Political Stability, IQ = Institutional Quality (avg of Rule of Law and Regulatory Quality proxies), C = Conflict Intensity, RS = Regime Stability.

### 12.2 Results

The following table presents enhanced political scores and component values for countries at each event.  Special Polity5 codes: −66 = interregnum/occupation, −77 = anarchy/failed state, −88 = transition.

#### 12.2.1 19th Century Events (1815–1870)

| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |
|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|
| Congress of Vienna | 1815 | GBR | 3 | Democracy | 0.712 | 0.52 | 0.75 | 0.65 | 1.00 | 0.81 |
| | | FRA | −2 | Open Anocracy | 0.449 | 0.43 | 0.25 | 0.40 | 1.00 | 0.28 |
| | | RUS | −10 | Consolidated Autocracy | 0.460 | 0.27 | 0.70 | 0.00 | 1.00 | 0.68 |
| | | AUT | −6 | Consolidated Autocracy | 0.562 | 0.45 | 0.70 | 0.20 | 1.00 | 0.74 |
| Revolutions of 1848 | 1848 | FRA | −1 | Open Anocracy | 0.416 | 0.47 | 0.17 | 0.45 | 0.70 | 0.38 |
| | | DEU | −4 | Open Anocracy | 0.381 | 0.46 | 0.17 | 0.30 | 0.80 | 0.29 |
| | | AUT | −6 | Consolidated Autocracy | 0.496 | 0.49 | 0.58 | 0.20 | 0.70 | 0.75 |
| | | GBR | 3 | Democracy | 0.724 | 0.57 | 0.75 | 0.65 | 1.00 | 0.82 |
| Franco-Prussian War | 1870 | DEU | −4 | Open Anocracy | 0.322 | 0.51 | 0.05 | 0.30 | 0.50 | 0.32 |
| | | FRA | −2 | Open Anocracy | 0.366 | 0.52 | 0.09 | 0.40 | 0.50 | 0.40 |

**Interpretation:** The 19th century results confirm the **Goldstone anocracy principle**: Britain, with its stable parliamentary monarchy (polity2 = 3), consistently scores highest (~0.71–0.72) despite not being a full democracy by modern standards.  The Metternich-era consolidated autocracies (Austria 0.56, Russia 0.46) outperform the revolutionary anocracies of France and the German states.  During the 1848 revolutions, France drops to 0.42 and Prussia to 0.38 — both open anocracies with active conflict and zero regime durability.  The Franco-Prussian War (1870) suppresses both belligerents' scores to the 0.32–0.37 range through the PV channel (Political Stability near zero during active combat).

#### 12.2.2 World War I and Interwar Period (1914–1939)

| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |
|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|
| WWI Outbreak | 1914 | DEU | −4 | Open Anocracy | 0.289 | 0.54 | 0.03 | 0.30 | 0.20 | 0.41 |
| | | FRA | 8 | Full Democracy | 0.635 | 0.55 | 0.58 | 0.90 | 0.20 | 0.97 |
| | | GBR | 8 | Full Democracy | 0.725 | 0.70 | 0.66 | 0.90 | 0.40 | 1.00 |
| | | RUS | −10 | Consolidated Autocracy | 0.303 | 0.33 | 0.42 | 0.00 | 0.30 | 0.70 |
| | | AUT | −4 | Open Anocracy | 0.312 | 0.54 | 0.07 | 0.30 | 0.30 | 0.41 |
| Russian Revolution | 1917 | RUS | −88 * | Failed/Occupied | 0.000 | — | 0.00 | — | 0.10 | 0.22 |
| Treaty of Versailles | 1919 | DEU | 6 | Full Democracy | 0.739 | 0.51 | 0.76 | 0.80 | 0.90 | 0.86 |
| | | FRA | 8 | Full Democracy | 0.824 | 0.52 | 0.90 | 0.90 | 1.00 | 0.95 |
| | | GBR | 8 | Full Democracy | 0.873 | 0.69 | 0.90 | 0.90 | 1.00 | 1.00 |
| | | USA | 10 | Full Democracy | 0.900 | 0.70 | 0.90 | 1.00 | 1.00 | 1.00 |
| Hitler to Power | 1933 | DEU | −9 | Consolidated Autocracy | 0.507 | 0.61 | 0.56 | 0.05 | 0.90 | 0.68 |
| Annexation of CZE | 1939 | DEU | −9 | Closed Anocracy | 0.404 | 0.55 | 0.31 | 0.05 | 0.90 | 0.40 |
| | | CZE | −66 * | Failed/Occupied | 0.000 | — | 0.00 | — | 0.50 | 0.38 |
| | | GBR | 10 | Full Democracy | 0.909 | 0.74 | 0.90 | 1.00 | 1.00 | 1.00 |
| | | FRA | 8 | Full Democracy | 0.807 | 0.45 | 0.90 | 0.90 | 1.00 | 0.94 |

**Interpretation:** WWI demonstrates conflict's devastating effect on political stability: Wilhelmine Germany drops to 0.29 and Austria-Hungary to 0.31 — both open anocracies with high conflict dragging PV near zero.  The Russian Revolution (1917, polity2 = −88) correctly triggers the **failed/occupied** classification with score 0.000, exactly as designed.  The Treaty of Versailles (1919) shows the Weimar Republic scoring surprisingly well (0.74) as a new full democracy — a result that highlights both the model's correct instantaneous assessment and the limitation that the GRRI does not predict *future* instability (Weimar collapsed by 1933).  The USA at 0.90 is the highest score in the entire dataset, reflecting the post-WWI unipolar moment of institutional stability.

Hitler's rise (1933) produces a score of 0.51 — elevated by the Nazi regime's *high governance effectiveness* (0.61), which correctly captures the paradox of competent totalitarian state administration.  By 1939, as regime durability is still low and conflict tensions mount, Germany drops to 0.40.  Czechoslovakia's occupation (polity2 = −66) correctly produces 0.000.

#### 12.2.3 World War II (1940–1941)

| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |
|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|
| Fall of France | 1940 | DEU | −9 | Closed Anocracy | 0.225 | 0.53 | 0.04 | 0.05 | 0.20 | 0.40 |
| | | FRA | −66 * | Failed/Occupied | 0.000 | — | 0.00 | — | 0.20 | 0.21 |
| | | GBR | 10 | Full Democracy | 0.735 | 0.74 | 0.62 | 1.00 | 0.30 | 1.00 |
| Pearl Harbor | 1941 | JPN | −6 | Consolidated Autocracy | 0.335 | 0.45 | 0.34 | 0.20 | 0.10 | 0.73 |
| | | USA | 10 | Full Democracy | 0.786 | 0.74 | 0.70 | 1.00 | 0.50 | 1.00 |

**Interpretation:** The Fall of France (1940) produces the starkest contrasts in the dataset: France collapses to 0.000 (polity2 = −66, Third Republic destroyed), while Britain at 0.74 maintains institutional resilience despite existential military threat — precisely the kind of differentiation the GRRI is designed to capture.  Militarist Japan (0.34) is correctly scored below the USA (0.79), with Japan's extremely low inverse-conflict score (0.10) reflecting its overextended military engagements across the Pacific and China.

#### 12.2.4 Cold War Events (1950–1980)

| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |
|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|
| Korean War | 1950 | KOR | −3 | Open Anocracy | 0.199 | 0.29 | 0.00 | 0.35 | 0.10 | 0.25 |
| | | PRK | −9 | Closed Anocracy | 0.145 | 0.34 | 0.00 | 0.05 | 0.10 | 0.31 |
| | | USA | 10 | Full Democracy | 0.844 | 0.78 | 0.78 | 1.00 | 0.70 | 1.00 |
| | | CHN | −7 | Closed Anocracy | 0.311 | 0.41 | 0.19 | 0.15 | 0.60 | 0.33 |
| Cuban Missile Crisis | 1962 | USA | 10 | Full Democracy | 0.899 | 0.80 | 0.86 | 1.00 | 0.90 | 1.00 |
| | | CUB | −7 | Closed Anocracy | 0.413 | 0.51 | 0.31 | 0.15 | 0.90 | 0.37 |
| | | RUS | −7 | Consolidated Autocracy | 0.510 | 0.40 | 0.66 | 0.15 | 0.90 | 0.72 |
| Six-Day War | 1967 | ISR | 9 | Full Democracy | 0.690 | 0.67 | 0.56 | 0.95 | 0.30 | 1.00 |
| | | EGY | −7 | Closed Anocracy | 0.257 | 0.43 | 0.10 | 0.15 | 0.30 | 0.41 |
| | | SYR | −9 | Closed Anocracy | 0.311 | 0.50 | 0.19 | 0.05 | 0.60 | 0.37 |
| Yom Kippur War | 1973 | ISR | 9 | Full Democracy | 0.676 | 0.69 | 0.54 | 0.95 | 0.20 | 1.00 |
| | | EGY | −7 | Closed Anocracy | 0.240 | 0.44 | 0.08 | 0.15 | 0.20 | 0.43 |
| | | SYR | −9 | Closed Anocracy | 0.267 | 0.52 | 0.11 | 0.05 | 0.40 | 0.37 |
| Iranian Revolution | 1979 | IRN | −10 | Full Autocracy | 0.371 | 0.62 | 0.29 | 0.00 | 0.60 | 0.54 |
| Iran Hostage Crisis | 1980 | IRN | −6 | Closed Anocracy | 0.283 | 0.54 | 0.07 | 0.20 | 0.30 | 0.37 |
| | | USA | 10 | Full Democracy | 0.934 | 0.84 | 0.90 | 1.00 | 1.00 | 1.00 |
| | | IRQ | −9 | Closed Anocracy | 0.273 | 0.59 | 0.09 | 0.05 | 0.30 | 0.44 |

**Interpretation:** The Cold War events demonstrate several important patterns:

1. **Korean War (1950):** Both Koreas score extremely low — South Korea (0.20) as a fragile open anocracy under Rhee, North Korea (0.15) as a closed anocracy, both devastated by full-scale war (PV = 0.00, inverse-conflict = 0.10).  China (0.31) scores higher than both Koreas despite being a newly established regime (durability = 1), reflecting lower direct conflict intensity and moderate state capacity.

2. **Cuban Missile Crisis (1962):** The USA peaks at 0.90, near the theoretical maximum for a democracy — no active conflict, maximum institutional quality, high regime stability.  The USSR (0.51) outscores Cuba (0.41) due to consolidated autocracy's regime stability advantage (0.72 vs 0.37).  This demonstrates the model's **regime-type sensitivity**: the Soviet Union's institutional consolidation produces a higher resilience score than Castro's Cuba despite superficially similar polity2 scores.

3. **Middle East Wars:** Israel maintains scores of 0.68–0.69 through both wars despite active combat, reflecting high institutional quality (IQ = 0.95) and regime stability (RS = 1.00).  Egypt and Syria consistently score in the 0.24–0.31 range — closed anocracies with low institutional quality and active conflict.  The model correctly identifies Israel's institutional resilience advantage over its adversaries.

4. **Iranian Revolution (1979):** The Shah's regime (polity2 = −10) scores 0.37 — a full autocracy with high GE (0.62, reflecting Pahlavi modernisation of state apparatus) but zero institutional quality (IQ = 0.00 for full autocracies).  Post-revolution Iran (1980, polity2 = −6) drops to 0.28, with a shattered state capacity (GE falling from 0.62 to 0.54) and active Iran-Iraq War conflict.

#### 12.2.5 Post-Cold War and Contemporary Events (1991–2023)

| Event | Year | Country | Polity2 | Regime Type | Score | GE | PV | IQ | 1-C | RS |
|-------|------|---------|---------|-------------|-------|----|----|----|-----|-----|
| Gulf War | 1991 | IRQ | −9 | Closed Anocracy | 0.251 | 0.56 | 0.08 | 0.05 | 0.20 | 0.47 |
| | | KWT | −7 | Consolidated Autocracy | 0.413 | 0.79 | 0.32 | 0.15 | 0.10 | 0.84 |
| | | USA | 10 | Full Democracy | 0.887 | 0.85 | 0.82 | 1.00 | 0.80 | 1.00 |
| 9/11 Attacks | 2001 | USA | 10 | Full Democracy | 0.792 | 0.86 | 0.50 | 0.87 | 0.90 | 1.00 |
| | | AFG | −77 * | Failed/Occupied | 0.000 | — | 0.00 | — | 0.10 | 0.34 |
| Iraq War | 2003 | IRQ | −9 | Consolidated Autocracy | 0.309 | 0.50 | 0.33 | 0.05 | 0.10 | 0.75 |
| | | USA | 10 | Full Democracy | 0.738 | 0.85 | 0.42 | 0.86 | 0.70 | 1.00 |
| Russia-Ukraine War | 2022 | RUS | −7 | Closed Anocracy | 0.355 | 0.43 | 0.19 | 0.34 | 0.50 | 0.43 |
| | | UKR | 4 | Democracy | 0.335 | 0.44 | 0.08 | 0.42 | 0.20 | 0.72 |
| Israel-Hamas War | 2023 | ISR | 7 | Full Democracy | 0.577 | 0.74 | 0.28 | 0.71 | 0.30 | 1.00 |

**Interpretation:**

1. **Gulf War (1991):** Iraq (0.25) is correctly scored as a low-resilience closed anocracy with active conflict.  Kuwait (0.41) — despite being under occupation — scores higher due to very high governance effectiveness (0.79, oil wealth administrative capacity) and extreme regime stability (0.84, longstanding emirate).  This reveals an important finding: **state capacity reserves can sustain resilience scores even during acute crises**, a pattern consistent with Besley & Persson's (2011) "pillars of prosperity" framework.

2. **9/11 Attacks (2001):** The USA scores 0.79 using WGI data — lower than many earlier entries due to post-2000 PV decline (WGI PV = 0.50 in 2001, reflecting growing domestic political polarisation).  Afghanistan (polity2 = −77, indicating anarchy/failed state) correctly produces 0.000.  This case illustrates a key **GRRI limitation**: the model accurately captures Afghanistan as a failed state but cannot predict non-state actor attacks originating from failed states against high-scoring countries.  The GRRI identifies *vulnerability* (Afghanistan) but not *targeting* (USA hit despite high resilience).

3. **Iraq War (2003):** Iraq's pre-invasion score (0.31 as consolidated autocracy) demonstrates the regime paradox — high durability (0.75) and moderate GE (0.50), but minimal institutional quality and extreme conflict, producing a low composite.  The USA drops to 0.74, its lowest post-WWII score, primarily driven by PV = 0.42 (WGI Political Stability at 0.42 reflects post-9/11 security concerns and Iraq War controversy).

4. **Russia-Ukraine War (2022):** Both belligerents score similarly (Russia 0.36, Ukraine 0.34) but for fundamentally different reasons.  Russia's score is depressed by collapsed WGI PV (rescaled to 0.19) and low IQ (0.34), with regime stability also declining (0.43) despite 23 years of Putin-era durability.  Ukraine scores low primarily due to active conflict (inverse-conflict = 0.20) and low PV (0.08), but maintains higher institutional quality (0.42) and regime stability (0.72) than Russia — reflecting democratic institutional resilience under invasion.  This convergence of scores through different pathways is analytically significant: the invader and invaded reach similar risk levels, but the *composition* of their scores tells opposite stories.

5. **Israel-Hamas War (2023):** Israel drops to 0.58 — its lowest score in the dataset — despite very high governance effectiveness (0.74) and regime stability (1.00).  The decline is driven almost entirely by **PV collapse** (0.28, from WGI PV = −1.12) and active conflict (inverse-conflict = 0.30).  This represents exactly the scenario the GRRI is designed to capture: a high-capacity democracy under acute security stress, where institutional quality remains high but political stability is severely compromised.

### 12.3 Cross-Event Patterns

Across all 22 events and 51 country-event observations, several systematic patterns emerge:

1. **Full democracies never score below 0.58** except under direct occupation (France 1940 = 0.000).  The floor for an intact full democracy under active conflict is approximately 0.58 (Israel 2023), set by the combination of high IQ, GE, and RS components.

2. **Anocracies are consistently the lowest-scoring surviving states.**  Open anocracies range from 0.20 (South Korea 1950) to 0.45 (post-Napoleonic France), while closed anocracies range from 0.15 (North Korea 1950) to 0.41 (Cuba 1962, low conflict).  This pattern confirms the **Goldstone hypothesis** that anocracies carry higher structural risk than either democracies or consolidated autocracies.

3. **Consolidated autocracies outperform anocracies** through the regime stability channel.  The Habsburg Empire (0.50–0.56), Tsarist Russia (0.46), and Soviet Union (0.51) all score above their polity2 values would suggest, because long-tenure autocracies accumulate regime stability.  This is not a model artefact — it reflects the genuine phenomenon that institutional predictability, even under authoritarian rule, provides a form of resilience.

4. **Conflict intensity is the strongest score suppressor.**  The PV and inverse-conflict channels together account for 40% of the composite weight, and during active major war, both collapse simultaneously.  This produces the observed pattern that wartime scores are 30–50% lower than peacetime scores for the same country and regime type.

5. **Failed/occupied states always score 0.000.**  All four cases (Russia 1917, Czechoslovakia 1939, France 1940, Afghanistan 2001) correctly produce zero scores, confirming the special-code handling for polity2 values of −66, −77, and −88.

### 12.4 Limitations of the Event Analysis

1. **WGI lag effect:** As documented in §4.1.4, WGI is a perception-based lagging indicator.  The 2022 Russia-Ukraine scores use the most recent available WGI (2022), which already captures some PV decline, but GE may not yet reflect invasion-related administrative disruption.

2. **Conflict intensity is exogenously assigned.**  The conflict intensity values (0.0–0.9) are calibrated from COW/UCDP battle-death magnitude but require researcher judgement for scaling.  Different calibrations would shift PV and inverse-conflict components proportionally.

3. **Expert GE anchors:** Pre-WGI governance effectiveness estimates are drawn from state capacity literature but involve inherent uncertainty.  The analysis uses conservative anchors where possible and notes the specific literature sources.

4. **Polity5 special codes:** The transition (−88), interregnum (−66), and failed state (−77) codes produce hard zero scores.  This is analytically correct for risk assessment but means the model cannot differentiate between *degrees* of state failure.

---

## 13. Conclusion

The historical extension of the GRRI enables resilience-adjusted backtesting of the MAC framework across the full 1870–2025 period with four-pillar coverage, and from 1800 with political and economic pillars alone.  The extension is built entirely from publicly available academic datasets, of which the majority are freely commercialisable with attribution.  Three datasets (MeasuringWorth, Mitchell, EM-DAT) require separate licensing for commercial use; the remainder are available under open or permissive licences.

The key insight that enables this extension is that modern governance indicators (WGI, HDI, INFORM) are relatively recent constructions, but the phenomena they measure — regime stability, economic growth, social development, environmental exposure — have been studied and quantified by political scientists, economic historians, and climatologists for decades.  By mapping these older measurement traditions onto the GRRI pillar structure with explicit normalisation and documented correlations, we obtain backward-compatible resilience scores that degrade gracefully as data thins.

The geopolitical event analysis (§12) provides empirical validation across 22 events spanning 1815–2023, covering 51 country-event observations.  Key validated patterns include: full democracies maintaining a floor score of ~0.58 even under active conflict; the Goldstone anocracy instability principle (anocracies consistently score lowest among surviving states); consolidated autocracies' resilience advantage over anocracies through regime stability; and the correct identification of failed/occupied states (score 0.000) in all four observed cases.

Beyond backward extension, this paper identifies three avenues for methodological enhancement drawn from the MAC framework's analytics toolkit:  **(1)** Adaptive pillar weighting using gradient boosting and LOO cross-validation, transplantable where sufficient crisis observations exist (post-1900); **(2)** Historically-informed Monte Carlo simulation using empirically-calibrated distributions and copula-estimated cross-pillar dependencies, offering a principled alternative to assumed shock parameters; **(3)** Independence structure analysis using MI, HSIC, and MIC to quantify embedded correlations — particularly the Political–Social overlap via shared V-Dem indicators and the Economic–Social overlap via shared Maddison GDP — with decorrelation strategies adapted from MAC's private credit pipeline.

The implementation is production-grade, with over 70 unit tests covering data loaders, scoring normalisation, proxy-chain completeness, composite calculation, regime classification, momentum detection, and modifier integration.  All source code is available in the `grri_mac.grri` module.

---

## References

Bolt, J. & van Zanden, J.L. (2020). Maddison style estimates of the evolution of the world economy: A new 2020 update. *Maddison Project Working Paper WP-15*, University of Groningen.

Coppedge, M. et al. (2023). V-Dem Codebook v14. Varieties of Democracy Institute, University of Gothenburg.

Crafts, N.F.R. (1997). The Human Development Index and Changes in Standards of Living: Some Historical Comparisons. *European Review of Economic History*, 1(3), 299–322.

Felbermayr, G. et al. (2020). The Global Sanctions Data Base. *European Economic Review*, 131, 103561.

Friedman, M. & Schwartz, A.J. (1963). *A Monetary History of the United States, 1867–1960.* Princeton University Press.

Garriga, A.C. (2016). Central Bank Independence in the World: A New Dataset. *International Interactions*, 42(5), 849–868.

Guha-Sapir, D. et al. (2023). EM-DAT: The International Disaster Database. Centre for Research on the Epidemiology of Disasters (CRED), UCLouvain, Brussels.

Hidalgo, C.A. & Hausmann, R. (2009). The building blocks of economic complexity. *PNAS*, 106(26), 10570–10575.

Johnston, L. & Williamson, S.H. (2023). What Was the U.S. GDP Then? MeasuringWorth.

Marshall, M.G. & Gurr, T.R. (2020). Polity5: Political Regime Characteristics and Transitions, 1800–2018. Center for Systemic Peace.

Mitchell, B.R. (2013). *International Historical Statistics.* 7th edition. Palgrave Macmillan.

Morice, C.P. et al. (2021). An Updated Assessment of Near-Surface Temperature Change From 1850: The HadCRUT5 Data Set. *Journal of Geophysical Research: Atmospheres*, 126(3), e2019JD032361.

Pettersson, T. & Öberg, M. (2020). Organized violence, 1989–2019. *Journal of Peace Research*, 57(4), 597–613.

Reinhart, C.M. & Rogoff, K.S. (2009). *This Time Is Different: Eight Centuries of Financial Folly.* Princeton University Press.

Sarkees, M.R. & Wayman, F. (2010). *Resort to War: 1816–2007.* CQ Press.

Schwert, G.W. (1989). Why Does Stock Market Volatility Change Over Time? *Journal of Finance*, 44(5), 1115–1153.

Shiller, R.J. (2000). *Irrational Exuberance.* Princeton University Press.

Teorell, J. et al. (2019). Measuring Polyarchy Across the Globe, 1900–2017. *Studies in Comparative International Development*, 54(1), 71–95.

### Additional References (Sections 9–12)

Acemoglu, D. & Robinson, J.A. (2012). *Why Nations Fail: The Origins of Power, Prosperity, and Poverty.* Crown Business.

Albanese, D. et al. (2013). Minerva and minepy: a C engine for the MINE suite and its R, Python and MATLAB wrappers. *Bioinformatics*, 29(3), 407–408.

Allen, R.C. (2003). *Farm to Factory: A Reinterpretation of the Soviet Industrial Revolution.* Princeton University Press.

Besley, T. & Persson, T. (2011). *Pillars of Prosperity: The Political Economics of Development Clusters.* Princeton University Press.

Breiman, L. (2001). Random Forests. *Machine Learning*, 45(1), 5–32.

Dincecco, M. (2017). *State Capacity and Economic Development: Present and Past.* Cambridge University Press.

Friedman, J.H. (2001). Greedy Function Approximation: A Gradient Boosting Machine. *Annals of Statistics*, 29(5), 1189–1232.

Fukuyama, F. (2014). *Political Order and Political Decay: From the Industrial Revolution to the Globalization of Democracy.* Farrar, Straus and Giroux.

Goldstone, J.A. et al. (2010). A Global Model for Forecasting Political Instability. *American Journal of Political Science*, 54(1), 190–208.

Gretton, A., Bousquet, O., Smola, A. & Schölkopf, B. (2005). Measuring Statistical Dependence with Hilbert-Schmidt Norms. In *Algorithmic Learning Theory* (ALT), LNCS 3734, pp. 63–77.

Haggard, S. (2018). *Developmental States.* Cambridge University Press.

Han, T.S. (1975). Linear dependence structure of the entropy space. *Information and Control*, 29(4), 337–368.

Hegre, H. et al. (2001). Toward a Democratic Civil Peace? Democracy, Political Change, and Civil War, 1816–1992. *American Political Science Review*, 95(1), 33–48.

Kaufmann, D., Kraay, A. & Mastruzzi, M. (2011). The Worldwide Governance Indicators: Methodology and Analytical Issues. *Hague Journal on the Rule of Law*, 3(2), 220–246.

Markevich, A. & Harrison, M. (2011). Great War, Civil War, and Recovery: Russia's National Income, 1913 to 1928. *Journal of Economic History*, 71(3), 672–703.

Kraskov, A., Stögbauer, H. & Grassberger, P. (2004). Estimating Mutual Information. *Physical Review E*, 69(6), 066138.

Reshef, D.N. et al. (2011). Detecting Novel Associations in Large Data Sets. *Science*, 334(6062), 1518–1524.

Sklar, A. (1959). Fonctions de répartition à $n$ dimensions et leurs marges. *Publications de l'Institut Statistique de l'Université de Paris*, 8, 229–231.

Watanabe, S. (1960). Information Theoretical Analysis of Multivariate Correlation. *IBM Journal of Research and Development*, 4(1), 66–82.

---

## Appendix A: Data File Inventory

All datasets are expected in `data/historical/grri/` with the following directory structure:

```
data/historical/grri/
├── polity5/
│   └── p5v2018.csv              # Polity5 regime scores
├── vdem/
│   └── vdem_core.csv            # V-Dem filtered extract
├── cow/
│   └── wars.csv                 # COW interstate/civil war data
├── maddison/
│   └── mpd2020.csv (or .xlsx)   # Maddison Project GDP per capita
├── reinhart_rogoff/
│   └── crises.csv               # Crisis indicator panel
├── emdat/
│   └── emdat_public.csv         # EM-DAT disaster records
├── hadcrut/
│   └── hadcrut5_annual.csv      # Global temperature anomaly
├── garriga/
│   └── cbi_index.csv            # Central Bank Independence index
├── gsdb/
│   └── sanctions.csv            # Global Sanctions Database
├── ucdp/
│   └── ucdp_brd.csv             # UCDP battle-related deaths
└── unemployment/
    ├── usa.csv                  # US unemployment rate
    ├── gbr.csv                  # UK unemployment rate
    └── ...                      # Additional countries
```

## Appendix B: Transformation Reference

| Proxy | Input Range | Output Range | Formula |
|-------|------------|-------------|---------|
| Polity5 polity2 | [−10, +10] | [0, 1] | $(x + 10) / 20$ |
| V-Dem indices | [0, 1] | [0, 1] | Direct |
| COW battle deaths | [0, ∞) | [0, 1] | $\min(1, \log_{10}(x+1) / 6)$ |
| Maddison GDP growth (CAGR) | [−∞, +∞] | [0, 1] | $(g + 0.10) / 0.20$, clipped |
| Log GDP/pc (complexity) | [0, ∞) | [0, 1] | $(\ln(x) - 5) / 6$, clipped |
| Garriga CBI | [0, 1] | [0, 1] | Direct |
| R-R crisis count (5yr) | [0, ∞) | [0, 1] | $\min(1, n/5)$ |
| EM-DAT deaths (5yr) | [0, ∞) | [0, 1] | $\min(1, \log_{10}(x+1) / 6)$ |
| HadCRUT5 anomaly delta | [−∞, +∞] | [0, 1] | $\min(1, \delta_{30\text{yr}} / 2.0)$, clipped |
| Unemployment rate | [0, 100] | [0, 1] | $1 - (r - 3) / 17$, clipped |
| Suffrage share | [0, 1] | [0, 1] | Direct |

## Appendix C: Minimum Data Requirements by Period

| Period | Pillars Available | Minimum Data | Confidence |
|--------|-------------------|-------------|------------|
| 1789–1815 | Political only | V-Dem only → single pillar, GRRI returns None | Insufficient |
| 1816–1819 | Political | V-Dem + COW → still single pillar | Insufficient |
| 1820–1849 | Political, Economic | V-Dem/Polity5 + Maddison → **2 pillars** | Low |
| 1850–1869 | Pol, Econ, Env (climate only) | + HadCRUT5 → **3 pillars** | Low–Moderate |
| 1870–1899 | Pol, Econ, Social (partial), Env (climate) | + HDI proxy → **3–4 pillars** | Moderate |
| 1900–1945 | All four pillars | + EM-DAT, unemployment | Moderate |
| 1946–1969 | All four pillars | + UCDP, approaching modern depth | Moderate–Good |
| 1970–1989 | All four pillars | + Garriga CBI | Good |
| 1990–2011 | All four pillars | + UNDP HDI (overlap calibration) | Good |
| 2012–present | All four pillars (modern) | Full modern data | Excellent |
