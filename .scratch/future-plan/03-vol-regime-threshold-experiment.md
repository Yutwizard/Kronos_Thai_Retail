# Ticket 03: Volatility-regime entry threshold experiment (CPU-only)

**Status:** Scoped, not filed. Type: research experiment. No GPU needed for
the core work.
**Source:** trimmed Task 3 of
`docs/superpowers/plans/2026-06-21-quant-review-remediation-phase2-gpu.md`.

## Why

Friction drains most of the gross return in volatile years: 16.82%/yr in 2025
and 41.57%/yr in 2026 (`docs/backtest-methodology.md` OOS table). The QFM
review (commit 778f03e) suspected a higher entry threshold in volatile
regimes could cut turnover. This is a new entry-threshold knob, the same
family as the max-holding-days cap that was rejected (see `CLAUDE.md`
Research decisions), so it follows the same test discipline.

## Why it is CPU-only

The Forecast Cache (`data/forecast_cache/NeoQuasar_Kronos-small`, ~1.5 GB,
2020-01-01 to 2026-07-25, local and git-ignored) already holds the n=50
forecasts. `scripts/run_max_holding_sweep.py` already ran a 20-run sweep off it
with a stub model and no inference; use it as the template. The plan's Task 4
(8-12 GPU-hours per year) is not needed.

## Design (fixed before running)

- Implement `compute_regime_adjusted_threshold` in `kth/backtest/strategy.py`
  and use it at the entry-threshold site in `run_walkforward`, **off by
  default** (like `max_holding_days`). Signature and logic per Phase 2 Task 3
  Step 1: raise the entry buffer when median 20-day realized vol across
  eligible tickers exceeds its 80th historical percentile.
- One configuration: vol_lookback=20, percentile=80, buffer raise as specified
  in that Step. **No grid.** If a grid is wanted later, count its size in the
  Correction Family.
- Compare against the Baseline Configuration (current production: Entry
  Threshold 2.0%, no holding cap), years 2023-2026, n=50.

## Acceptance rule (agreed 2026-09-18)

Adopt only if BOTH hold:
1. Pooled 2023-2026 paired block-bootstrap 95% CI on daily active return
   (variant minus Baseline Configuration) excludes zero on the positive side.
2. No single year shows a statistically clean loss (CI entirely below zero),
   the failure that sank the cap60 config in 2024.

Otherwise reject and record the result in `CLAUDE.md` Research decisions, with
numbers, so it is not relitigated. A null result rejects this configuration
only, not the idea. Also report per year: turnover, friction/yr, Sharpe.
Method: `scripts/analyze_cap60_significance.py`.

## Optional GPU top-up

Cache ends 2026-07-25 (2026 = 145 trading days). Regenerating forecasts from
2026-07-26 to today on a Kaggle/Colab T4 would extend 2026. Only worth it if
results through today matter; do not block the experiment on it.

## Doc updates (folded in from Phase 2 Tasks 6-8)

Once the result is known (adopt or reject): update the Research decisions in
`CLAUDE.md`, and the results paragraphs in `PROJECT_STRUCTURE.md` / `README.md`
if adopted. Do ticket 02 first to avoid double edits.

## Not in this ticket

Partial-fill model (deferred, see README) and FX adjustment (dropped).
