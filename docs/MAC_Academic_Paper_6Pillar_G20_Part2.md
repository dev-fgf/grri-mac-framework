# A Six-Pillar Framework for Measuring Market Absorption Capacity
## Part 2: Continuation

*This file continues from MAC_Academic_Paper_6Pillar_G20.md*

---

### 2.5 Pillar V: Policy

#### 2.5.1 Theoretical Basis

Monetary policy serves as a critical buffer against financial market stress through multiple transmission channels. The Taylor (1993) rule framework suggests central banks should adjust policy rates in response to inflation gaps and output gaps. During crisis periods, however, central banks provide extraordinary support through:

1. **Interest rate policy**: Lowering rates reduces funding costs and supports asset valuations
2. **Quantitative easing**: Asset purchases inject liquidity and compress risk premia (Krishnamurthy and Vissing-Jorgensen, 2011)
3. **Forward guidance**: Commitment to future policy paths reduces uncertainty (Campbell et al., 2012)
4. **Emergency facilities**: Targeted interventions in dysfunctional markets (Bernanke, 2020)

The Policy pillar recognizes that markets' absorption capacity depends partly on the central bank's ability to provide countercyclical support. When policy rates are already at zero, balance sheets are expanded, or inflation is well above target, the central bank's capacity to respond to new shocks is constrained.

#### 2.5.2 The "Ammunition" Concept

Stein (2014) introduces the concept of monetary "ammunition"—the degree to which the central bank can ease policy in response to adverse shocks. When policy rates are far above the effective lower bound and balance sheets are normalized, the central bank has substantial ammunition. When rates are at zero and the balance sheet is highly expanded, ammunition is depleted.

This matters for market dynamics because market participants anticipate central bank support—the "Fed put" or "central bank put" phenomenon (Cieslak and Vissing-Jorgensen, 2021). When this put is out-of-the-money (central bank cannot ease further), risk premia should theoretically be higher to compensate for reduced downside protection.

Empirical evidence supports this mechanism:

**2008-2015 Zero Lower Bound**: When Fed Funds reached zero in December 2008, equity risk premia expanded despite subsequent QE programs. The VIX averaged 20 during 2009-2011 versus a pre-crisis average of 14, suggesting markets priced in reduced policy optionality.

**2020-2021 Rapid Response**: The Federal Reserve's swift deployment of unlimited QE and emergency facilities in March 2020 contributed to the fastest bear market recovery in history. The MAC framework captures this through rapid Policy pillar improvement.

**2022-2023 Constrained by Inflation**: With inflation at 8-9%, the Federal Reserve hiked aggressively despite financial stability concerns (SVB crisis, UK pensions). The Policy pillar correctly identified depleted ammunition during this period.

#### 2.5.3 Policy Effectiveness Constraints

Several factors constrain policy effectiveness:

**Effective Lower Bound**: Nominal interest rates face a zero (or slightly negative) lower bound, limiting conventional easing (Eggertsson and Woodford, 2003). While unconventional policies (QE, forward guidance) remain available, their effectiveness is debated (Bernanke, 2020).

**Balance Sheet Constraints**: While there is no strict limit to central bank balance sheet expansion, political economy considerations and concerns about market functioning create practical constraints (Hall and Reis, 2015). The Fed's balance sheet peaked at 37% of GDP in 2020; further expansion faces diminishing returns and risks market distortions.

**Inflation Constraints**: When inflation is above target, the central bank faces a trade-off between financial stability and price stability. The 2022-2023 period illustrated this tension as central banks tightened despite financial stability concerns (Greenwood et al., 2023). Our framework captures this through the inflation gap indicator.

**Fiscal Policy Interaction**: The effectiveness of monetary policy depends on fiscal policy coordination. Large fiscal deficits may constrain monetary policy room through debt sustainability concerns (Sargent and Wallace, 1981). This interaction is particularly relevant for emerging markets with foreign-currency-denominated debt.

#### 2.5.4 Indicator Construction

We construct the Policy pillar from three indicators:

**Policy Rate vs. Neutral**: The difference between the policy rate (Fed Funds, ECB refinancing rate, BoJ policy rate, etc.) and an estimated neutral rate measures policy stance. We use country-specific neutral rate estimates:
- United States: 2.5%
- Eurozone: 1.5%
- Japan: 0.0%
- Emerging markets: Real neutral rate + inflation target

Large positive gaps indicate restrictive policy that may stress markets by tightening financial conditions.

**Balance Sheet Size**: Central bank assets relative to GDP measure the degree of unconventional policy deployment. We define thresholds relative to historical norms:
- United States: Ample <20%, Stretched >35%
- Eurozone: Ample <30%, Stretched >50%
- Japan: Ample <80%, Stretched >130% (reflecting structural QE)

Very high ratios indicate depleted capacity for additional QE and potential market distortions from central bank dominance.

**Inflation Gap**: Actual inflation minus the central bank's target measures the constraint on easing:
$$Inflation Gap = \pi_t - \pi^*$$

where $\pi_t$ is current inflation (core PCE for US, HICP for Eurozone) and $\pi^*$ is the target (typically 2%). Positive gaps constrain easing; negative gaps provide room for accommodation.

**Theoretical Justification**: These indicators directly measure the dimensions of "ammunition" discussed by Stein (2014) and capture the transmission channels emphasized by Bernanke and Blinder (1992) and Kashyap and Stein (2000). The multi-indicator approach recognizes that policy space is multidimensional: rate space, balance sheet space, and inflation tolerance.

---

### 2.6 Pillar VI: International Contagion

#### 2.6.1 Overview and Innovation

The International Contagion pillar represents the principal innovation of our six-pillar framework. While the first five pillars measure domestic market conditions, this sixth pillar explicitly captures cross-border transmission mechanisms that can propagate stress internationally.

The importance of international linkages has grown substantially since the 1990s globalization wave. International bank claims increased from 10% of world GDP in 1980 to peak at 60% in 2007 (BIS, 2019). Cross-border portfolio holdings similarly expanded. This integration brings benefits (diversification, capital allocation) but also creates contagion channels.

Three historical episodes motivate our focus on international transmission:

**Global Financial Crisis (2007-2009)**: What began as a US subprime mortgage problem became a global crisis through multiple channels: European banks' holdings of US mortgage securities, dollar funding stress transmitted via cross-currency basis, and synchronized deleveraging in international banking (Cetorelli and Goldberg, 2011).

**European Sovereign Crisis (2011-2012)**: Greek debt problems spread to Portugal, Ireland, Italy, and Spain through bank exposures, TARGET2 payment imbalances, and contagious sovereign spread widening (Acharya et al., 2014).

**COVID-19 (March 2020)**: Although the pandemic was a global shock, financial transmission occurred through specific channels: dollar funding stress (cross-currency basis), emerging market capital flight (reserve drawdowns), and correlated portfolio liquidation (Hofmann et al., 2020).

A single-country MAC score would have missed the international dimensions of these crises. Our International Contagion pillar fills this gap.

#### 2.6.2 Sub-Indicator 1: Cross-Currency Basis

**Theoretical Foundation**: Covered Interest Parity (CIP) is a fundamental no-arbitrage condition stating that currency-hedged returns should be equalized across currencies:

$$(1 + r_{domestic}) = \frac{F}{S}(1 + r_{foreign})$$

where $r$ denotes interest rates, $S$ is the spot exchange rate, and $F$ is the forward rate.

Rearranging, the cross-currency basis is defined as:

$$Basis = r_{domestic} - r_{foreign} - \frac{F-S}{S}$$

Under CIP, the basis should equal zero. Negative basis indicates that synthetic dollar borrowing (borrowing in foreign currency, converting to dollars, hedging FX risk) is more expensive than direct dollar borrowing.

**Why CIP Violations Matter**: Du et al. (2018) document persistent, large CIP violations post-2008, particularly during stress periods. They attribute violations to:

1. **Bank balance sheet costs**: Post-crisis leverage ratio regulations make CIP arbitrage unprofitable even when apparent profits exist (Cenedese et al., 2021)
2. **Dollar scarcity**: Foreign banks and corporates need dollars for funding but face constrained access, creating negative basis
3. **Limits to arbitrage**: Arbitrage capital is limited, preventing basis correction (Shleifer and Vishny, 1997)

The cross-currency basis thus measures dollar funding stress globally—a critical contagion channel because:
- Wide negative basis forces foreign institutions to deleverage dollar assets
- Deleveraging transmits to US asset markets through selling pressure
- Central bank intervention (swap lines) is required to stabilize markets

**Empirical Validation**:

**October 2008 (GFC Peak)**: EUR/USD 3-month basis reached -240 basis points, indicating extreme dollar funding stress. The Federal Reserve responded by establishing unlimited dollar swap lines with the ECB, providing over $580 billion in dollar liquidity (Goldberg et al., 2011).

**March 2020 (COVID-19)**: EUR/USD basis widened to -70 bps, JPY/USD to -90 bps, and EM currency basis to -150+ bps. The Fed again activated swap lines, injecting $449 billion. Bahaj and Reis (2020) show that swap line announcements reduced basis by 30-50 bps within hours—direct evidence of the funding stress mechanism.

**Calm Periods (2015-2019)**: Basis remained in -10 to -20 bps range, reflecting persistent but non-systemic friction. This "new normal" likely reflects regulatory constraints on arbitrage (Avdjiev et al., 2019).

**Indicator Construction**: We measure the average absolute deviation of major cross-currency bases from zero:

$$Basis Score = \frac{1}{3}(|EUR/USD_{3M}| + |JPY/USD_{3M}| + |GBP/USD_{3M}|)$$

**Thresholds** (absolute basis in bps):
- **Ample**: < 15 bps (normal post-2008 friction)
- **Comfortable**: 15-30 bps (moderate stress)
- **Thin**: 30-60 bps (elevated stress, potential intervention needed)
- **Stretched**: 60-100 bps (severe stress)
- **Critical**: > 100 bps (crisis, central bank intervention required)

**Data Sources**:
- **Real-time**: Bloomberg cross-currency basis swap spreads (via Polygon.io or similar)
- **Historical (quarterly)**: BIS derivatives statistics provide 3M basis estimates back to 1998
- **Alternative**: Infer from FX forward points and interest rate differentials using CIP formula

#### 2.6.3 Sub-Indicator 2: TARGET2 Imbalances

**Theoretical Foundation**: TARGET2 (Trans-European Automated Real-time Gross Settlement Express Transfer System) is the ECB's payment system for cross-border euro transactions within the Eurozone. It was designed for intraday liquidity provision and payments settlement.

Mechanically, when Bank A in Country 1 sends euros to Bank B in Country 2:
1. Country 1's national central bank (NCB) incurs a LIABILITY to the ECB (negative TARGET2 balance)
2. Country 2's NCB acquires a CLAIM on the ECB (positive TARGET2 balance)

In normal circumstances, these flows balance:
- Trade flows create balanced payments
- Capital inflows to some countries match outflows from others
- TARGET2 balances remain small relative to GDP

**Why Imbalances Indicate Stress**: Sinn and Wollmershäuser (2012) interpret large, persistent TARGET2 imbalances as reflecting:

1. **Capital flight**: Funds flee periphery banking systems for core (Germany, Netherlands)
2. **Loss of market access**: Periphery banks cannot raise private funding, rely on ECB liquidity
3. **Fragmentation**: Monetary union functioning breaks down; private capital flows cease

The doom loop logic (Acharya et al., 2014):
- Weak sovereigns → weak banks (holding sovereign debt)
- Weak banks → capital flight
- Capital flight → ECB liquidity via TARGET2
- Growing TARGET2 imbalances → redenomination risk fears
- Redenomination risk → sovereign spread widening → doom loop reinforces

**Empirical Validation**:

**European Sovereign Crisis (2010-2012)**:
- Germany's TARGET2 claims peaked at €750 billion (30% of German GDP) in August 2012
- Spain: -€435B, Italy: -€290B, Portugal: -€80B, Greece: -€110B
- Total gross imbalances: ~€1 trillion (10% of Eurozone GDP)

Timeline correlation with sovereign stress:
- April 2010: Greek bailout, TARGET2 imbalances begin rising
- August 2011: Italian/Spanish spreads spike, imbalances accelerate
- July 2012: Draghi "whatever it takes", imbalances peak
- 2013-2014: Spreads narrow, imbalances gradually decline

**QE Period (2015-2018)**: Imbalances rose again to €1 trillion, but interpretation differs:
- ECB asset purchases created payment flows from periphery (selling bonds) to core (reinvesting proceeds)
- NOT capital flight, but policy-induced imbalances
- Market stress (spreads) remained contained

**COVID-19 (2020-2021)**: Imbalances rose to €1.2 trillion but again reflected ECB policy (PEPP purchases) rather than fragmentation.

**Interpretation Framework**: We distinguish stress-induced imbalances from policy-induced:
- **Stress**: Rising imbalances + widening sovereign spreads + capital flight indicators
- **Policy**: Rising imbalances + stable spreads + ECB QE operations

**Indicator Construction**:

$$TARGET2 Score = \frac{\sum_{i} |Balance_i|}{Eurozone GDP} \times 100$$

where the numerator is the gross sum of absolute TARGET2 balances across all Eurozone members.

**Thresholds** (% of Eurozone GDP):
- **Ample**: < 5% (normal functioning)
- **Comfortable**: 5-10% (modest imbalances, manageable)
- **Thin**: 10-20% (elevated, fragmentation concerns)
- **Stretched**: 20-30% (severe fragmentation)
- **Critical**: > 30% (monetary union viability questions)

**Adjustment for QE periods**: During active ECB asset purchases, we apply a 50% weight discount to account for policy-induced component.

**Data Sources**:
- **Primary**: ECB Statistical Data Warehouse, series TGB (TARGET2 balances by country), monthly frequency
- **Start date**: January 1999 (euro launch)
- **Real-time**: Published with ~15-day lag

**International Application**: TARGET2 is Eurozone-specific. For non-Eurozone countries:
- **Score as neutral** (0.5) if not applicable
- **Alternative indicators**:
  - Balance of payments sudden stop indicator (capital account reversals > 5% GDP)
  - Central bank swap line usage
  - Foreign currency liquidity ratio

---

#### 2.6.4 Sub-Indicator 3: Emerging Market Reserve Coverage

**Theoretical Foundation**: The Guidotti-Greenspan rule (Guidotti, 1999; Greenspan, 1999) provides a benchmark for emerging market reserve adequacy:

$$\text{FX Reserves} \geq \text{Short-Term External Debt}$$

Or equivalently, the coverage ratio should exceed 100%:

$$Coverage Ratio = \frac{\text{FX Reserves}}{\text{Short-Term External Debt}} \times 100\%$$

This rule aims to ensure countries can service debt obligations even if capital markets close (sudden stop). The logic:
- Short-term debt must be rolled over or repaid within one year
- During sudden stops, refinancing is impossible
- Reserves provide self-insurance against this tail risk

**Extended Reserves Adequacy**: Modern frameworks extend the Guidotti-Greenspan rule to account for:
1. **Portfolio outflows**: Non-debt liabilities (equity holdings) can also flee during crises
2. **M2 coverage**: Domestic residents may convert local currency to foreign currency, requiring reserves
3. **Export coverage**: Traditional metric of reserves relative to months of imports

The IMF's Assessing Reserve Adequacy (ARA) framework (2011) provides composite metrics, but we focus on the simpler debt coverage ratio for transparency.

**Why Reserve Coverage Matters**: Empirical evidence demonstrates that reserve adequacy determines resilience to sudden stops:

**Asian Financial Crisis (1997-1998)**:
- **Thailand**: Reserves $37B vs. short-term debt $45B (82% coverage) → forced devaluation, IMF program
- **Indonesia**: Reserves $20B vs. debt $34B (59% coverage) → 80% currency depreciation, severe recession
- **Taiwan**: Reserves $84B vs. debt $21B (400% coverage) → weathered crisis with modest depreciation

Radelet and Sachs (1998) show that reserve/debt ratios predicted both crisis incidence and severity across Asian economies.

**Taper Tantrum (2013)**:
The "Fragile Five" (Brazil, India, Indonesia, Turkey, South Africa) experienced sharp currency depreciation when Fed signaled QE tapering. Reserve coverage ratios:
- **India**: 115% → 20% currency depreciation
- **Turkey**: 90% → 18% depreciation
- **South Africa**: 85% → 25% depreciation
- Versus **Korea**: 210% coverage → 8% depreciation (Eichengreen and Gupta, 2015)

**COVID-19 (March 2020)**:
EM currency index fell 15% in two weeks. Reserve drawdowns:
- Countries with coverage >150%: median 5% reserve depletion, 12% depreciation
- Countries with coverage 100-150%: median 12% depletion, 18% depreciation
- Countries with coverage <100%: median 25% depletion, 28% depreciation (Hofmann et al., 2020)

**Theoretical Channels**: Reserve inadequacy creates vulnerability through:

1. **Currency crisis**: Unable to defend exchange rate, sharp depreciation triggers balance sheet effects for dollar-denominated debt (Krugman, 1999)
2. **Forced adjustment**: Current account must improve rapidly through compression of imports/demand → recession
3. **Contagion**: EM crises tend to cluster as investors apply "guilt by association" across EMs (Kaminsky and Reinhart, 1999)
4. **Risk premium**: Even absent crisis, low reserves command higher sovereign spreads and borrowing costs (Aizenman and Marion, 2004)

**Indicator Construction**:

For each EM country $i$, we calculate:

$$Coverage_i = \frac{FX Reserves_i}{ST External Debt_i} \times 100\%$$

For G20 emerging markets, we compute a GDP-weighted average:

$$EM Coverage Score = \frac{\sum_i GDP_i \cdot Coverage_i}{\sum_i GDP_i}$$

where the sum is over G20 EMs: China, India, Indonesia, Brazil, Mexico, Argentina, Turkey, South Africa, Saudi Arabia.

**Thresholds** (coverage ratio):
- **Ample**: > 150% (comfortable buffer above Guidotti-Greenspan)
- **Comfortable**: 125-150% (adequate buffer)
- **Thin**: 100-125% (meets rule but minimal buffer)
- **Stretched**: 75-100% (below rule, vulnerable)
- **Critical**: < 75% (severe vulnerability)

**Rationale for thresholds**: Empirical studies (Aizenman and Lee, 2007) find that coverage ratios above 150% are associated with minimal crisis probability (<2%), while ratios below 100% show crisis probabilities of 10-15% within two years.

**Data Sources**:
- **FX Reserves**: IMF International Financial Statistics (IFS), series RAXG_USD (Total Reserves excluding Gold), monthly frequency
- **Short-Term External Debt**: IMF IFS, series EDTS_USD (Short-Term Debt, original maturity <1 year), quarterly frequency
- **Historical coverage**: Both series available from 1970s for most countries
- **Real-time lag**: ~2 months for reserves, ~3 months for debt

**Country-Specific Application**:
- **Advanced economies** (US, Eurozone, UK, Japan): Reserve adequacy not binding due to reserve currency status or deep capital markets → score as 1.0 (ample) or omit from scoring
- **China special case**: Official reserves $3.1T vs. external debt $2.4T (130% coverage), but capital controls reduce sudden stop risk → adjust thresholds
- **Oil exporters** (Saudi Arabia, Russia): Reserves partially reflect sovereign wealth funds rather than liquidity buffer → use only liquid reserves portion

---

#### 2.6.5 Sub-Indicator 4: Cross-Border Banking Flows

**Theoretical Foundation**: The global banking system exhibits strong procyclicality through cross-border lending dynamics (Shin, 2012; Bruno and Shin, 2015). The mechanism:

**Boom Phase** (capital inflows):
- Global banks expand cross-border lending to higher-yield jurisdictions
- Local credit growth exceeds domestic deposit growth
- Leverage and asset prices rise
- Duration/maturity mismatch increases (foreign banks provide short-term funding for long-term domestic assets)

**Bust Phase** (capital outflows):
- Global shock → risk reassessment
- Global banks reduce cross-border exposures
- Credit crunch in recipient countries
- Deleveraging, asset fire sales, currency depreciation
- Outflows typically 2-3x faster than inflows

This creates contagion: problems in one borrowing country trigger global bank retrenchment, affecting other unrelated borrowing countries.

**Empirical Evidence**:

**Global Financial Crisis (2008-2009)**:
BIS reporting banks contracted cross-border claims by $4.7 trillion (10% of outstanding claims) between Q2 2008 and Q2 2009:
- **To Europe**: -$2.4T (-12%)
- **To EMs**: -$0.4T (-8%)
- **To US**: -$0.6T (-7%)

Cetorelli and Goldberg (2011) show this transmitted US housing shock to countries with no direct subprime exposure through wholesale funding channel.

**European Sovereign Crisis (2011-2012)**:
Core European banks reduced periphery exposures by $1.1 trillion:
- **Spain**: -$230B (-18% decline)
- **Italy**: -$190B (-15%)
- **Greece**: -$85B (-38%)

Acharya and Steffen (2015) demonstrate this forced periphery bank deleveraging despite ECB liquidity provision—private cross-border credit was not replaced.

**Taper Tantrum (2013)**:
Cross-border lending to EMs declined 8% in Q2-Q3 2013 following Fed taper signals:
- **Latin America**: -$65B
- **Asia ex-Japan**: -$45B
- **EMEA**: -$30B

Avdjiev et al. (2019) link Fed monetary policy to global banking flows through dollar funding channel.

**COVID-19 (Q1 2020)**:
Cross-border claims declined $1.1 trillion globally in Q1 2020:
- **Advanced economies**: -$850B
- **EMs**: -$110B (-4%)

However, unlike prior crises, Fed swap lines and central bank interventions contained the outflow by Q2 2020.

**Theoretical Channels**: Cross-border flow disruptions transmit stress through:

1. **Credit crunch**: Firms and banks in recipient countries lose funding source → investment/consumption declines
2. **Currency pressure**: Capital outflows depreciate recipient currency → balance sheet effects for foreign currency debt
3. **Asset fire sales**: Deleveraging forces asset liquidation → declining collateral values → feedback loop (Brunnermeier and Pedersen, 2009)
4. **Risk premium**: Sudden stop episodes raise future borrowing costs (Calvo et al., 2008)

**Measurement**: The BIS Locational Banking Statistics (LBS) track gross cross-border claims/liabilities of banks by residence. We focus on quarterly flow changes:

$$Flow_{t} = \frac{Claims_t - Claims_{t-1}}{GDP_t} \times 100\%$$

where Claims represent cross-border claims on all sectors (banks, non-banks, official), adjusted for exchange rate valuation effects.

**Indicator Construction**:

We calculate global cross-border flow changes (aggregated across reporting countries):

$$Global Flow Score = \frac{\Delta Cross-Border Claims}{World GDP} \times 100\%$$

**Thresholds** (quarterly change as % of GDP):
- **Ample**: -0.5% to +1.5% (normal range: modest outflows to healthy inflows)
- **Comfortable**: +1.5% to +3.0% or -0.5% to -1.0% (elevated but orderly)
- **Thin**: +3.0% to +5.0% or -1.0% to -2.0% (rapid inflows risk reversal; outflows indicate stress)
- **Stretched**: +5.0% to +7.0% or -2.0% to -4.0% (unsustainable inflows; credit crunch outflows)
- **Critical**: > +7.0% or < -4.0% (extreme inflows signal boom-bust risk; extreme outflows signal sudden stop)

**Rationale**:
- **Rapid inflows** (>3% GDP/quarter) historically precede credit booms and subsequent reversals (Mendoza and Terrones, 2012)
- **Sharp outflows** (<-2% GDP/quarter) indicate sudden stops associated with recessions (Calvo et al., 2008)

**Asymmetric scoring**: Outflows receive higher stress scores than equivalent inflows, reflecting greater immediate damage from sudden stops versus slower-building risks from credit booms.

**Data Sources**:
- **Primary**: BIS Locational Banking Statistics (LBS), Table A6 (external positions by country and sector), quarterly frequency
- **Historical coverage**: 1977-present for major countries
- **Real-time lag**: ~6 months (Q1 data published in September)
- **Alternative high-frequency**: SWIFT financial messaging volumes (weekly) provide directional signal but lack magnitude precision

**Country-Specific Application**:
- **Global Score**: Aggregate flow across all BIS reporting countries
- **Country-Specific Score**: For individual G20 countries, calculate country-specific flows:
  $$Flow_i = \frac{Claims\_on\_Country\_i_t - Claims\_on\_Country\_i_{t-1}}{GDP_i} \times 100\%$$

---

#### 2.6.6 Composite International Contagion Score

We aggregate the four sub-indicators into a composite International Contagion pillar score:

$$Contagion = \omega_1 S_{basis} + \omega_2 S_{TARGET2} + \omega_3 S_{reserves} + \omega_4 S_{flows}$$

where $S_i \in [0,1]$ are normalized sub-indicator scores and $\omega_i$ are weights summing to 1.

**Base Weighting** (equal weights):
$$\omega_1 = \omega_2 = \omega_3 = \omega_4 = 0.25$$

**Regional Adjustments**:

| Country Group | Cross-Currency Basis | TARGET2 | Reserve Coverage | Cross-Border Flows |
|---------------|---------------------|---------|------------------|-------------------|
| **United States** | 30% | 0% | 0% | 70% |
| **Eurozone** | 25% | 35% | 0% | 40% |
| **UK, Japan, Canada, Australia** | 30% | 0% | 0% | 70% |
| **Emerging Markets** | 20% | 0% | 40% | 40% |
| **China** | 20% | 0% | 30% | 50% |

**Rationale**:
- **Eurozone**: TARGET2 is unique to monetary union; critical for fragmentation risk → higher weight
- **Advanced economies**: Reserve coverage not binding (reserve currency status, deep markets) → zero weight
- **Emerging markets**: Reserve adequacy critical for sudden stop vulnerability → higher weight
- **Cross-border flows**: Universal transmission channel → positive weight for all

**Time-Varying Weights** (optional enhancement): During QE periods, reduce TARGET2 weight by 50% to account for policy-induced imbalances.

---

### 2.7 Summary of Theoretical Foundations

The table below summarizes the theoretical basis for each pillar:

| Pillar | Core Theory | Key Mechanism | Canonical Papers |
|--------|-------------|---------------|------------------|
| **Liquidity** | Market microstructure, funding liquidity | Intermediary constraints → liquidity provision breakdown | Brunnermeier & Pedersen (2009), Duffie (2010) |
| **Valuation** | Asset pricing, time-varying risk premia | Compressed premia → repricing vulnerability | Campbell & Cochrane (1999), Gilchrist & Zakrajšek (2012) |
| **Positioning** | Financial accelerator, limits to arbitrage | Leverage concentration → amplification through forced deleveraging | Bernanke et al. (1999), Adrian & Shin (2010) |
| **Volatility** | Volatility feedback, uncertainty | VaR constraints → procyclical selling; option hedging dynamics | Campbell & Hentschel (1992), Adrian & Shin (2014) |
| **Policy** | Monetary transmission, central bank ammunition | Policy space exhaustion → reduced backstop capacity | Stein (2014), Bernanke (2020) |
| **Contagion** | International finance, sudden stops, contagion | Cross-border linkages → stress transmission across countries | Calvo (1998), Shin (2012), Acharya et al. (2014) |

Each pillar is firmly grounded in established financial economics theory and validated through historical crisis evidence. The six-pillar structure captures complementary dimensions of market fragility, providing a comprehensive view of absorption capacity.

---

## 3. Data and Implementation

### 3.1 Data Sources by Country

The framework uses publicly available data from official statistical agencies and multilateral institutions:

| Country/Region | Primary Sources | Secondary Sources | Historical Start |
|----------------|----------------|-------------------|------------------|
| **United States** | FRED | CFTC, SEC EDGAR, Treasury.gov | 1954 (rates), 1986 (COT), 1996 (spreads) |
| **Eurozone** | ECB SDW | OECD, BIS | 1999 (euro), some pre-1999 legacy |
| **United Kingdom** | Bank of England | OECD, BIS | 1970s |
| **Japan** | Bank of Japan | OECD, BIS | 1970s |
| **Other G20 Advanced** | OECD | National central banks | 1980s-1990s |
| **G20 Emerging Markets** | OECD, IMF IFS | National sources | 1990s-2000s |
| **Cross-Border** | BIS | IMF, ECB (TARGET2) | 1977 (BIS LBS), 1999 (TARGET2) |

All sources are freely accessible without subscription fees (Tier 1 sources). Optional premium data (Polygon.io, Bloomberg) can enhance real-time monitoring but are not required for framework implementation.

### 3.2 Historical Indicator Reconstruction

For backtesting 2004-2024 (20-year period including pre-GFC), several indicators require substitution:

| Modern Indicator | Historical Period | Substitute Indicator | Theoretical Equivalence |
|------------------|-------------------|----------------------|------------------------|
| SOFR-IORB spread | Pre-April 2018 | LIBOR-OIS spread | Both measure bank funding stress |
| IORB (interest on reserves) | Pre-July 2021 | IOER (interest on excess reserves) | Policy rate adjustment |
| SVXY AUM (short vol) | Pre-October 2011 | VIX futures open interest | Both proxy short vol exposure |
| CFTC disaggregated COT | Pre-2006 | Legacy COT reports | Positioning measures, different format |
| Cross-currency basis (daily) | All periods (if no subscription) | BIS quarterly estimates | Lower frequency but same construct |

**Validation**: Overlap periods (2011-2018 for SVXY vs VIX OI; 2006-2018 for COT formats) show correlations >0.80, supporting substitution validity.

### 3.3 Update Frequency

| Indicator Type | Frequency | Typical Lag | Impact on Real-Time Monitoring |
|----------------|-----------|-------------|-------------------------------|
| **Money market rates** | Daily | 1 day | Enables daily MAC updates |
| **Credit spreads** | Daily | 1 day | Enables daily MAC updates |
| **VIX** | Real-time | Intraday | Enables intraday monitoring |
| **Policy rates** | As announced | Immediate | Updated on policy dates |
| **CFTC COT** | Weekly | 3 days | Updated Fridays |
| **BIS cross-border flows** | Quarterly | 6 months | Limits backtest frequency |
| **TARGET2 balances** | Monthly | 15 days | Monthly Eurozone updates |
| **Reserve/debt data** | Monthly/Quarterly | 2-3 months | Limits EM score frequency |

**Practical implementation**: Daily MAC scores use latest available data for each indicator. Quarterly indicators (BIS flows) are held constant between updates. Confidence intervals reflect data staleness.

---

*(Continue to Part 3 for Validation, Results, and Conclusions)*
