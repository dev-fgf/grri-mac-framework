# MAC Framework — Methodology Schematics

Mermaid diagram source files extracted from `docs/methodology.md`. Each `.mmd` file is a standalone Mermaid diagram that can be rendered with any Mermaid-compatible tool.

## Rendering

**VS Code:** Install the "Markdown Preview Mermaid Support" or "Mermaid Editor" extension.

**CLI (to SVG/PNG):**
```bash
npx @mermaid-js/mermaid-cli mmdc -i 01_system_pipeline.mmd -o 01_system_pipeline.svg
```

**Online:** Paste contents into https://mermaid.live/

## Diagram Index

| # | File | Section | Description |
|---|------|---------|-------------|
| 01 | `01_system_pipeline.mmd` | 2.1 | End-to-end system architecture: data layer, 8-pillar scoring, composite engine, uncertainty, and validation |
| 02 | `02_computation_flow.mmd` | 2.2 | Per-timestep MAC computation: fetch, score 8 pillars, weight, penalise, calibrate, clip |
| 03 | `03_liquidity_pillar.mmd` | 3.1 | Liquidity pillar: 4 indicators scored via piecewise-linear function |
| 04 | `04_policy_pillar.mmd` | 3.5 | Policy pillar: binding-constraint vs weighted-average logic with era caps |
| 05 | `05_private_credit_pillar.mmd` | 3.7 | Private credit pillar: public-market proxies, PCA decorrelation, stress levels |
| 06 | `06_weight_selection.mmd` | 4.2 | Weight selection: 8-pillar ML-optimised vs interaction-adjusted weights |
| 07 | `07_ml_training_pipeline.mmd` | 5.2 | ML training: augmentation, XGBoost/GBM, 14 features (8 base + 6 interactions), LOOCV |
| 08 | `08_uncertainty_sources.mmd` | 7.1 | Bootstrap CI: three uncertainty sources, proxy tiers, 1000 resamples |
| 09 | `09_backtest_loop.mmd` | 9.1 | Backtest loop: weekly iteration with 8 pillars, three modes (Standard/Extended/Full) |
| 10 | `10_walk_forward_protocol.mmd` | 9.2 | Walk-forward re-estimation: expanding window, 52-week refit cycle |
| 11 | `11_sentiment_pillar.mmd` | 3.8 | Sentiment pillar: FinBERT text path, rate-change proxy, calibration anchors |
| 12 | `12_dependence_analysis.mmd` | 18 | Cross-pillar dependence analysis: MI, HSIC, MIC → decorrelation/weight/MC decisions |
| 13 | `13_grri_proxy_chains.mmd` | GRRI §3 | GRRI historical proxy chain architecture: modern → mid-century → deep historical |
| 14 | `14_independence_metrics.mmd` | GRRI §11 | Three complementary dependence metrics: what each captures and blind spots |
| 15 | `15_grri_weighting_montecarlo.mmd` | GRRI §9–10 | GRRI adaptive weighting, Monte Carlo, and independence analysis pipeline |
| 16 | `16_decorrelation_pipeline.mmd` | 18.6 | Detect-decorrelate-validate loop for redundant pillar pairs |
