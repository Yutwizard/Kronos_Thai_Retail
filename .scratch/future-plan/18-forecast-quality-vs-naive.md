# Ticket 18: are Kronos forecasts better than a naive forecast? (DRAFT, needs approval)

STATUS: DRAFT 2026-09-23 (from the 2026-09-23 review, item R1). Nothing run. Fixed design below; approve Q1-Q4 before any computation.

## Question
The project now describes itself as a forecasting/monitoring tool, not an edge (CLAUDE.md). That claim has never been tested. On the 2024 point-in-time cache, are Kronos-small's probabilistic forecasts (p5/p25/p50/p75/p95) more accurate than a naive forecast that needs no model?

## Why this is allowed
It judges forecast accuracy, not a trading rule, so it opens no Correction Family in the multiple-testing register and adopts nothing into the product. It uses only data and forecasts that already exist. CPU only, minutes.

## Fixed design
- Forecasts: `data/forecast_cache_pit/NeoQuasar_Kronos-small/`, 262 dates of 2024, the 51 frozen `thai_equity` tickers (ticket 11 list). The live folders are NOT used here: their signal quality is part of the ticket-11 review, and looking at it now would weaken that review.
- Prices: the 2026-09-23 snapshot (`~/backups/kronos-th-snapshots/2026-09-23T222128/raw`), the one closest to when the PIT cache was generated (2026-09-19..21), so forecast levels and closes share the same dividend-adjustment scale. Stated limit: any ex-dividend adjustment between generation and the snapshot shifts that ticker's level by a small factor; not corrected.
- Base close: the close at each forecast's `lookback_end`. Realised price at horizon h: the close h trading days later in the ticker's own rows. Target dates that are stub calendar dates (ticket 09 definition, at least half the tickers flat and zero-volume) are skipped, as are forecasts whose horizon runs past the data.
- Horizons: h = 1, 5, 20 trading days. **Primary: h = 20** (the horizon the trading signal uses).
- Everything is scored in log-return space: quantile q forecast = log(pq / base close).
- Baselines, all built from the same 400-row window the model saw (raw, unclean, like the model's input):
  - **B1 (primary): historical simulation.** Median 0; quantiles = empirical quantiles of the ticker's past non-overlapping h-day log returns within the window, demeaned.
  - B2: Gaussian random walk. Mean 0, standard deviation = last-60-day daily log-return std x sqrt(h).
- Metrics:
  - **Primary: mean quantile (pinball) loss over the five quantiles** (an approximation of CRPS).
  - Secondary, descriptive: p50 absolute error; 90% (p5-p95) and 50% (p25-p75) band coverage.
- Test: per date, average the loss difference (Kronos minus baseline) across tickers; stationary block bootstrap over dates (block 20, 10,000 resamples, seed 42); 95% CI of the mean difference.

## Decision rule (fixed now)
- **Kronos BETTER than B1 at h = 20:** CI of (Kronos - B1) entirely below 0.
- **Kronos WORSE:** CI entirely above 0.
- Otherwise **NO DIFFERENCE SHOWN.**
- Secondary results (B2, h = 1 and 5, coverage) are reported and not tested.
- Consequence (user decides): BETTER supports the "forecasting tool" description for 2024 only. WORSE or NO DIFFERENCE SHOWN: recommend that the docs and dashboard say the bands are not shown to beat a naive volatility band. No product change is automatic.

## Limits stated in advance
One year (2024), one model, 51 current constituents (survivorship does not bias a forecast-accuracy comparison much, but the sample is still current names only). The 2024 inputs contained stub rows (ticket 12); the baselines see the same inputs, so the comparison is like for like.

## Output
`scripts/forecast_quality_vs_naive.py` (read-only), log `data/logs/forecast_quality_vs_naive.log`, results appended here.

## Questions (recommended answers first)
- Q1: Primary baseline B1 (historical simulation), primary horizon 20, primary metric pinball loss? **Recommended: yes.**
- Q2: 2024 PIT cache only; live folders only after the 2026-12-30 review? **Recommended: yes.**
- Q3: Use the 2026-09-23 snapshot for prices? **Recommended: yes.**
- Q4: Run once after approval, no changes after seeing the result? **Recommended: yes.**
