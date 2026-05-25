# Expanded Backtest — 2020–2024 Thai Equity Design

> ✅ COMPLETED 2026-05-25. Results: CAGR +35.16%, Sharpe 1.29, Max DD −37.90%. Alpha positive in all 3 regimes. See `docs/user-manual.md` §6.1 for full results.

> Scope: Extend the Thai equity backtest from 3 years (2022-2024) to 5 years (2020-2024), adding COVID crash and recovery periods. Single GPU run (~10.5 hrs, actual ~15 hrs), regime decomposition via `scripts/run_expanded_backtest.py`.

---

## 1. Why Expand

The current backtest covers 2022-2024 (rate hike / AI boom / SET underperformance). This is one macro regime. The 49-ticker result (CAGR +31.44%, Sharpe 1.40, p=0.013) is significant, but we don't know if the alpha survives:
- A **−30% crash** (COVID, Q1 2020)
- A **liquidity-driven recovery** (mid-2020 to 2021)
- A **different interest rate environment** (near-zero in 2020 vs 5% in 2023)

Expanding to 2020-2024 answers: *"Does the Kronos model add alpha across ALL market regimes, not just the 2022-2024 rate-hike cycle?"*

---

## 2. Architecture

Single GPU run, single precompute pass, single walk-forward. No changes to existing scripts. A new one-off script `scripts/run_expanded_backtest.py` handles the full pipeline: precompute + walkforward + period decomposition + output. The regime decomposition is a post-processing step that computes metrics on sub-slices of the already-computed equity curve.

```
precompute_forecasts(2020-01-01 → 2024-12-31)  ← ~7.5 hrs
    │
    ▼
run_walkforward(config)                           ← ~90 sec
    │
    ▼
BacktestResult (full 5yr equity curve)              ← one curve, 5 periods
    │
    ├── compute full-period metrics
    ├── slice equity_curve[period1] → compute metrics
    ├── slice equity_curve[period2] → compute metrics
    ├── slice equity_curve[period3] → compute metrics
    └── print comparison table
```

### Period Boundaries (Event-Based)

Using macro event dates (not arbitrary calendar splits):

| Period | Label | Start | End | Macro Context | Trading Days ~ |
|--------|-------|-------|-----|---------------|----------------|
| COVID crash | Stress | 2020-01-01 | 2020-06-30 | −30% SET crash, initial recovery | ~125 |
| Recovery | Rebound | 2020-07-01 | 2021-12-31 | Liquidity-driven bull, near-zero rates | ~375 |
| Rate hikes | Current | 2022-01-01 | 2024-12-31 | QE unwind, inflation, AI boom | ~756 |
| **Full** | All | 2020-01-01 | 2024-12-31 | Complete 5-year cycle | ~1,260 |

### Why COVID crash starts 2020-01, not 2020-03

The crash began Jan 2020 (SET started falling from ~1,580). March 2020 was the bottom. Using January captures the entire drawdown → recovery sequence. Starting March would exclude the first −15% drop, making the "crash" period look less severe than it was.

---

## 3. Output Format

### Period Breakdown Table

The new one-off script `scripts/run_expanded_backtest.py` output:

```
=== THAI EQUITY — WALK-FORWARD BACKTEST (2020-2024) ===
Tickers: 50 | Calendar: 5-day (business) | Equal weight | n_samples=10

Full Period (2020-2024):
  CAGR:   +35.16%  Sharpe:   1.29  Max DD:  -37.90%  Alpha vs EW:  +23.32%  p=0.174

Period                         CAGR  Sharpe    Max DD  Alpha EW  SET CAGR  Trades  p-value Verdict
--------------------------------------------------------------------------------------------------
Stress (COVID crash)        -1.62%   0.12  -37.90%  +21.63%   -27.43%     652   0.762 Mitigate
Rebound (Recovery)         +65.96%   2.03  -17.54%  +29.73%   +14.10%    2012   0.425 Thrive
Current (Rate hikes)       +27.94%   1.29  -17.00%  +20.29%    -5.29%    3959   0.229 Thrive

  → Universe is point-in-time (2025). Delisted/merged tickers from 2020-2022
    are excluded. COVID stress period results may be overstated.
  → Alpha per period is the relevant metric for regime analysis.
  → Lower 5-year CAGR vs 2022-2024 alone is expected (includes COVID crash).
  → Multi-period testing: 3 periods × α=0.05 → ~14% probability of ≥1 false positive.
```

### Per-Period Verdict Rules (priority order — first match wins)

| Priority | Condition | Verdict |
|----------|-----------|---------|
| 1 | Alpha > 0 AND CAGR > 0 | **Thrive** (model captures up-markets) |
| 2 | Alpha > 0 AND Sharpe > 0.5 | **Survive** (model protects in turmoil) |
| 3 | Alpha > 0 AND CAGR < 0 | **Mitigate** (model reduces losses vs equal-weight) |
| 4 | Alpha ≤ 0 | **Struggle** (model adds no value in this regime) |

### Note for Lower 5-Year CAGR

If the 5-year CAGR is lower than the current 31.44%, the output will include:

> Lower 5-year CAGR does NOT mean the model is worse. The 2020 COVID crash (−30%) is included in this run. A 3-year window that excluded that crash naturally shows higher CAGR. The relevant metric is **alpha per period** — if alpha is positive in all 3 periods, the model adds value regardless of market direction.

---

## 4. Time Estimate

| Step | Time | Notes |
|------|------|-------|
| D1: Delete 2020-2021 date dirs from cache only | 1 min | Only `2020-*` and `2021-*` subdirs; 2022-2024 cached data preserved |
| D1: ZS precompute (49 tkrs × 1,260 days) | ~10.5 hrs | ~30 sec per trading day for 49 tickers via batch inference |
| D2: Walk-forward | ~90 sec | Negligible |
| D2: Period decomposition computation | ~10 sec | Post-processing on equity curve slices |
| D2: Output + save | ~30 sec | — |
| **Total** | **~10.5 hrs** | 1 overnight session |

---

## 5. Dependencies

- NEW: `scripts/run_expanded_backtest.py` — orchestrates precompute + walkforward + period decomposition
- `kth/backtest/walkforward.py` — `precompute_forecasts()`, `run_walkforward()`, `BacktestConfig`
- `kth/backtest/metrics.py` — `compute_sharpe()`, `compute_max_drawdown()`, `compute_metrics()`
- `kth/data/universe.py` — `UNIVERSE`, `get_all_tickers()`
- `kth/data/loader.py` — `load_cached()`
- `data/forecast_cache/NeoQuasar_Kronos-small/` — ZS cache (2022-2024 preserved; 2020-2021 added)
- `data/raw/*.parquet` — 49 Thai equity tickers cached (goes back to 2016)

---

## 6. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Thai equity only | Only significant market (p=0.013). US (0.46) and crypto (0.64) are noise |
| 2 | Event-based periods | Calendar boundaries miss macro turning points |
| 3 | 3 periods, not more | Each needs enough data for meaningful metrics; 5+ periods would be under-sampled |
| 4 | Single GPU run | Precompute is the bottleneck (7.5 hrs). Walk-forward and decomposition are negligible |
| 5 | Alpha per period is the key metric | Absolute CAGR depends on market direction. Alpha controls for that |
| 6 | Stress/Thrive/Mitigate/Struggle labels | Actionable — tells a trader whether to trust the model in each regime |
| 7 | Create `scripts/run_expanded_backtest.py` | Leaves existing compare_finetune.py untouched; one-off analysis |
| 8 | 10.5 hrs estimated (not 7.5) | Measured: ~30 sec per trading day for 49 tickers via batch inference |
| 9 | Delete only 2020-2021 cache dirs | Preserves existing 2022-2024 forecasts for all markets |
| 10 | Verdict priority: Thrive first, then Survive | CAGR > 0 is always better than Sharpe > 0.5 with negative CAGR |
| 11 | Stress period warning for small sample | ~125 days / ~30 trades — limited statistical power |

---

*Document version: 2026-05-24. Reviewed: HF manager + trader.*
