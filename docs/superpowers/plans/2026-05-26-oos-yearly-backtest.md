# Out-of-Sample Yearly Backtest (2023-2026) — Plan

**Goal:** Run a clean 4-year walk-forward backtest on the out-of-sample period where Kronos-small has no data leakage (post-2022 training cutoff). Year-by-year breakdown with full trade logs.

**Why:** 2017-2022 is contaminated by pre-training data. 2023-2026 is the only valid out-of-sample window. We already have 2023-2024 and 2026 YTD cached. Only 2025 is missing.

---

## Architecture

```
Forecast cache status:
  ├── 2023-*  (252 days)  ✅ already cached (from original backtest)
  ├── 2024-*  (252 days)  ✅ already cached (from original backtest)
  ├── 2025-*  (0 days)   ⬜ needs precompute (~252 days × ~30 sec = ~2 hrs)
  ├── 2026-*  (104 days)  ✅ already cached (from YTD run)

Then: ONE walkforward 2023-01-01 → 2026-05-26
Then: slice equity curve by year for breakdown
```

---

## Steps

### Task 1: Check existing cache and data availability

- [ ] Verify 2023-2024 dates are cached and complete
- [ ] Verify 2026 dates are cached and complete
- [ ] Count exactly how many 2025 trading days need computing

### Task 2: Precompute missing 2025 forecasts

- [ ] Run `precompute_forecasts()` for 2025-01-01 → 2025-12-31
- [ ] n_samples=10 (consistent with 2023-2024 and 2026 runs)
- [ ] Use checkpoint/resume from expanded backtest script

### Task 3: Run merged walk-forward (2023-2026)

- [ ] BacktestConfig: 2023-01-01 → 2026-05-26
- [ ] Thai equity tickers only
- [ ] Equal-weight top-5, 100-share lots, friction included
- [ ] Save to `data/backtest_results/thai_equity_2023-2026/`

### Task 4: Year-by-year decomposition

- [ ] Slice equity curve by calendar year: 2023, 2024, 2025, 2026
- [ ] Per-year: CAGR, Sharpe, Max DD, Alpha vs EW, Trades, p-value
- [ ] Compare against SET, SPY, equal-weight benchmarks

### Task 5: Generate HTML report

- [ ] Yearly comparison table
- [ ] Full trade log
- [ ] Best/worst trades per year
- [ ] Monthly breakdown within each year
- [ ] Clean OOS disclosure: "2023-2026 only, no pre-training overlap"

### Task 6: Commit

---

*Document version: 2026-05-26*
