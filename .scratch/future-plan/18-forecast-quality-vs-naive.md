# Ticket 18: are Kronos forecasts better than a naive forecast?

STATUS: APPROVED 2026-09-24 (user "agree" to Q1-Q4 as recommended). Not yet run; runs after ticket 19.

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

## Implementation notes frozen BEFORE the run (2026-09-24; nothing computed yet)
- Forecast rows: `timestamps` = step 1..20; the quantiles at step h are read from the row with `timestamps == h`.
- Input window: the ticker's own last 400 raw rows up to and including `lookback_end` (snapshot 2026-09-23T222128), exactly as the model saw them (no cleaning). Base = the close at `lookback_end`.
- Realised: the close h rows later in the ticker's own rows. Skipped if beyond the data, or if the target date is a stub calendar date (at least half of the 51 frozen tickers have a flat zero-volume row that day; the ticket-11 rule).
- B1: non-overlapping h-day log returns ending at the last window row (`log(c[j]/c[j-h])` for j = last, last-h, ...), centred on their median so that the median forecast is exactly 0 ("median 0"); quantiles by numpy's default linear interpolation. B1 is skipped if fewer than 10 returns exist (never for h <= 20 with 400 rows).
- B2: sigma = sample std (ddof 1) of the last 60 daily log returns in the window x sqrt(h); quantiles = 0, +/-0.6745 sigma, +/-1.6449 sigma.
- Pinball loss for level tau, forecast q, outcome y: max(tau(y-q), (tau-1)(y-q)); mean over tau in {0.05, 0.25, 0.5, 0.75, 0.95}.
- Per date: mean over tickers of (Kronos loss - baseline loss), only on (ticker, date) pairs where Kronos and the baseline both exist.
- Bootstrap: stationary block bootstrap over dates, geometric blocks with **mean length 20** (as fixed above; not the n^(1/3) rule of `live_track_review.mean_ci`), 10,000 resamples, seed 42, percentile 95% CI.

## Result (run 2026-09-24, `scripts/forecast_quality_vs_naive.py`, log `data/logs/forecast_quality_vs_naive.log`)
258 forecast folders; 31,250 scored (ticker, date, horizon) triples; 57 stub calendar dates skipped as targets. Run once; the self-test ran first on synthetic data only.

### Mean pinball loss (log-return space), Kronos minus baseline, block-bootstrap 95% CI over dates
| h | baseline | Kronos | baseline | diff | 95% CI | verdict |
|---|---|---|---|---|---|---|
| **20** | **B1 (primary)** | **0.0430** | **0.0210** | **+0.0219** | **[+0.0165, +0.0278]** | **WORSE** |
| 20 | B2 | 0.0430 | 0.0202 | +0.0227 | [+0.0173, +0.0286] | worse (secondary) |
| 5 | B1 / B2 | 0.0188 | 0.0097 / 0.0096 | +0.0091 / +0.0092 | both CIs above 0 | worse (secondary) |
| 1 | B1 / B2 | 0.0073 | 0.0045 / 0.0045 | +0.0027 / +0.0027 | both CIs above 0 | worse (secondary) |

### Descriptive (not tested)
| h | p50 abs log error Kronos / naive | 90% band coverage Kronos / B1 / B2 | 50% band coverage Kronos / B1 / B2 |
|---|---|---|---|
| 1 | 0.021 / 0.013 | 0.66 / 0.86 / 0.87 | 0.32 / 0.43 / 0.55 |
| 5 | 0.050 / 0.029 | 0.53 / 0.84 / 0.88 | 0.25 / 0.45 / 0.54 |
| 20 | 0.104 / 0.062 | 0.35 / 0.77 / 0.86 | 0.15 / 0.42 / 0.52 |

### Checks run after seeing the result (not part of the verdict)
- Data-scale check: the step-1 median offset log(p50/base) is -0.0005 overall, and no ticker shows a constant offset, so a price-scale mismatch between the cache and the snapshot is ruled out. The error is dispersion: per-ticker offset std up to 0.135 (DELTA.BK, whose price roughly tripled in 2024), and bands far too narrow (median step-1 p5-p95 width 3.8%).
- Without DELTA.BK: diff +0.0199 [+0.0156, +0.0247], still WORSE. 50 of 51 tickers (98%) have a higher mean h=20 loss than B1.

### Verdict by the frozen rule
**WORSE.** In 2024, Kronos-small zero-shot forecasts were less accurate than a no-model forecast at every horizon tested. The median is further from the outcome than "no change", and the p5-p95 band, nominally 90%, contained only 35% of 20-day outcomes (66% at one day).

### Consequence (recommendation; the user decides)
- The "forecasting/monitoring tool" description is not supported for 2024: the bands are overconfident and the median is worse than no change. Recommend that the README, CLAUDE.md status line and dashboard say so, and that the dashboard treat Kronos bands as model output, not as a risk range.
- The fixed `compute_calibration` (2026-09-23) will report `too_narrow` on the live folders if they behave like 2024; that is the dashboard-side check of this finding.
- Limits: one year, one model size, zero-shot, 51 current names, raw (unclean) inputs for both sides. It says nothing about Kronos-base or a fine-tuned model, and nothing about the live period, which the ticket-11 review covers.
