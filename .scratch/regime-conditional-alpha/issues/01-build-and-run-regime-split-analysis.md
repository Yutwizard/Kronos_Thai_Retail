# 01 - Build and run the daily regime-split significance analysis

Type: task
Status: resolved

## Question

Build and run a script (`scripts/analyze_regime_conditional_alpha.py`,
mirroring the style of `scripts/analyze_cap60_significance.py`) that tests
whether the strategy's daily active return (strategy − equal-weight) differs
significantly between SET bull-days and bear-days.

**Regime classification:**
- Load raw SET price history via `load_cached("^SET.BK")` (has history well
  before 2023-01-01, unlike the per-year `benchmark_SET.parquet` files which
  are normalized to 1.0 at each backtest's own start date and have no
  pre-period lookback).
- For each trading day in the 2023-2026 backtest range, compute the trailing
  60-trading-day SET return ending on that day (using the raw history, so
  early-2023 days can look back into 2022 data).
- Label the day `bull` if that trailing return > 0, `bear` if ≤ 0.

**Active return:**
- For each year, load `daily_returns.parquet` (strategy) and
  `benchmark_equal_weight.parquet` from
  `data/backtest_results/thai_equity_<year>_n50/` (already saved by the
  2026-07-29 re-run — no new backtesting needed).
- `active[day] = strategy_return[day] - equal_weight_return[day]`.

**Test:**
- Reuse the stationary block bootstrap from
  `scripts/analyze_cap60_significance.py` (same block-length heuristic as
  `compute_sharpe_ci` in `kth/backtest/metrics.py`).
- Compute, per year AND pooled across all 2023-2026 trading days: mean active
  return within bull-days, mean active return within bear-days, and the
  bootstrap CI on **(bull-day mean − bear-day mean)**.
- Report bull-day count / bear-day count per year too (regime imbalance
  matters for interpreting the result).

## Answer

Built `scripts/analyze_regime_conditional_alpha.py`. Regime = trailing
60-trading-day SET return (bull if >0, bear if ≤0), reindexed from raw SET
history onto the same business-day calendar the backtest itself uses (so
early-2023 days look back into 2022). Active return = strategy daily return
− equal-weight daily return, from the already-saved 2026-07-29 re-run data.
Stationary block bootstrap (same method as `analyze_cap60_significance.py`)
on bull-day active returns, bear-day active returns, and their difference,
per year and pooled:

```
[2023] bull_days=  65 (mean_active= +2.74% ann, CI=[-35.31%,+41.29%])
       bear_days= 193 (mean_active=+21.66% ann, CI=[-11.19%,+65.62%])
       (bull - bear) diff_ann=-18.92%  95% CI=[-75.99%, +33.63%]  P(diff>=0)=0.255

[2024] bull_days=  97 (mean_active=+50.88% ann, CI=[+15.90%,+88.84%])
       bear_days= 163 (mean_active=+36.36% ann, CI=[+10.54%,+63.00%])
       (bull - bear) diff_ann=+14.52%  95% CI=[-30.33%, +59.35%]  P(diff>=0)=0.733

[2025] bull_days= 104 (mean_active=+48.56% ann, CI=[ -4.07%,+103.92%])
       bear_days= 155 (mean_active=+37.30% ann, CI=[-15.60%,+91.98%])
       (bull - bear) diff_ann=+11.26%  95% CI=[-64.95%, +86.86%]  P(diff>=0)=0.620

[2026] bull_days= 131 (mean_active=+27.81% ann, CI=[-27.20%,+84.28%])
       bear_days=  14 (mean_active=+116.24% ann, CI=[+21.26%,+205.51%])
       (bull - bear) diff_ann=-88.43%  95% CI=[-194.21%, +17.68%]  P(diff>=0)=0.052

[pooled 2023-2026] bull_days= 397 (mean_active=+34.78% ann, CI=[ +8.43%,+62.71%])
                   bear_days= 525 (mean_active=+33.36% ann, CI=[+10.65%,+57.76%])
                   (bull - bear) diff_ann= +1.42%  95% CI=[-34.31%, +37.53%]  P(diff>=0)=0.527
```

**Pooled result (largest, most credible sample — 922 trading days):** active
return is significantly **positive in both regimes** (bull: +34.78% ann,
CI excludes zero; bear: +33.36% ann, CI excludes zero) and essentially
**identical in magnitude**. The bull-minus-bear difference is +1.42%
annualized with a CI of [-34.31%, +37.53%] — nowhere close to significantly
negative, and P(diff≥0)=0.527 is a coin flip. Under the locked decision rule
(confirm only if this CI is significantly negative), this is a clean
rejection.

Per-year detail is noisier (small samples, wide CIs) and doesn't change the
picture — only 2026 leans toward the original claim's direction
(diff=-88% ann, P(diff≥0)=0.052), but that's driven by just 14 bear-tagged
days in a mostly-bull year, too small a sample to trust on its own, and
doesn't contradict that 2026 overall had the *highest* total alpha of all
four years.

Status: resolved.
