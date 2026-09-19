# Ticket 00: Historical forecast cache is not point-in-time (look-ahead)

**Status:** FOUND 2026-09-18 while starting ticket 03. Blocks 03 and casts doubt
on every backtest number in the repo. **Priority: highest.**
Type: correctness bug + re-validation. GPU needed to re-validate.

## What was found (verified)

1. The experiment's baseline run did not reproduce the stored authoritative
   2023 metrics: CAGR 10.65% now vs 9.13% stored. Not caused by BANPU.BK
   (identical with/without it) nor by code (identical on the code from 2026-07-29
   and from just before the 2026-09-14 refactor, run against current data).
2. `precompute_forecasts()` (`kth/backtest/walkforward.py`) loops over
   historical days but calls `forecast_batch()`, which does
   `load_cached(...)` then `df.tail(lookback)` (`kth/models/kronos_wrapper.py`
   lines ~150 and ~257). Nothing cuts the data off at `day`, so every day's
   forecast is conditioned on the most recent 400 rows.
3. The cache confirms it: 41 of 47 sampled folders have
   `lookback_end = 2026-05-15` in their meta regardless of the folder date
   (2020-01-01 .. 2026-05-06). Only folders from the live daily pipeline
   (2026-06-29 onward) have `lookback_end == folder date`.
4. The forecast price levels are the same for every date. ADVANC.BK's p50 at
   day 20 is about 304-317 in folders from 2020 to 2026, while its actual close
   moved 129 -> 356.
5. Median |implied 20-day return| (p50 / close on that date - 1) across the 50
   tickers: 45% (2020-06), 46% (2022-06), 33% (2023-06), 28% (2024-06),
   19% (2025-06), 11% (2026-08). A point-in-time forecast would be within
   roughly +-10%.
6. `compute_signals` uses exactly `p50 / last_close(day) - 1`, so the signal for
   a historical day compares a 2026-anchored price with that day's close.

## Not yet measured (inference)

That this materially inflates the historical results. Mechanism: the signal
favours stocks whose price on day D is far below a fixed 2026 level, which
encodes future price movement. It also explains the drift in item 1: the stored
runs used raw prices as of 2026-07-29, and re-downloaded adjusted prices rescale
the denominator against a fixed numerator.

## Sample result (2026-09-19)

Regenerated 7 trading days (every 3rd day of March 2024, 50 tickers, n=50) point-in-time
into `data/forecast_cache_pit` on the local GTX 1060 (~9.5 min per day), then
`scripts/compare_pit_sample.py` against the old cache:

| | old cache | point-in-time |
|---|---|---|
| median abs signal (p50/close - 1) | 29.8% | 3.7% |
| mean rank IC vs realized 20d return | +0.156 | +0.186 |
| mean Spearman old vs new signal | -0.09 | |
| top-5 picks in common | 0.4 of 5 | |

New folders violating point-in-time: 0 of 350. Reading: the old and new signals are
essentially unrelated and pick almost entirely different stocks, so the existing
backtests do not describe the strategy the pipeline actually runs. The IC figures
are NOT evidence either way (7 dates, overlapping 20-day windows, one month); the
point-in-time signal is at least not worse in this sample.

## Likely affected

Everything computed from this cache: the n50 results 2023-2026 and their
p-values, the 2022-2024 canonical result, the Bonferroni discussion, the
cap60 rejection, the regime-conditional-alpha retraction analysis, and the
fine-tune vs zero-shot comparisons. NOT affected: the live daily pipeline
(its folders are point-in-time), the dashboard's calibration (reads only the most
recent 60 folders), and the equal-weight/SET benchmarks.

## Proposed steps

1. **DONE 2026-09-19 (code):** `precompute_forecasts` passes frames truncated at
   `day` (test: each folder's `lookback_end` equals its date), and
   `require_point_in_time_forecast` makes `run_walkforward` refuse any cached
   forecast whose `lookback_end` is after its date or has no metadata. Verified
   on the real cache: the guard rejects `2023-01-02/PTT.BK`. The old cache is
   untouched. `scripts/backfill_forecast.py` already truncated correctly.
2. **Quantify** on a small sample (e.g. one month, 50 tickers) regenerated
   point-in-time, and compare signals and results with the old cache.
3. **Re-run** the authoritative years with point-in-time forecasts. Phase 2's
   original estimate (8-12 T4 GPU-hours per year) applies after all; the
   "CPU-only" premise for ticket 03 only holds once the cache is valid.
4. **Re-evaluate** every conclusion listed above; until then treat backtest
   numbers as unverified (decide whether to add a warning to CLAUDE.md).
