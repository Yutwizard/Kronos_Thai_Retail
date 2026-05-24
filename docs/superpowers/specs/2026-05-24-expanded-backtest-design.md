# Expanded Backtest — 2020–2024 Thai Equity Design

> Scope: Extend the Thai equity backtest from 3 years (2022-2024) to 5 years (2020-2024), adding COVID crash and recovery periods. Single GPU run (~7.5 hrs), regime decomposition via post-processing.

---

## 1. Why Expand

The current backtest covers 2022-2024 (rate hike / AI boom / SET underperformance). This is one macro regime. The 49-ticker result (CAGR +31.44%, Sharpe 1.40, p=0.013) is significant, but we don't know if the alpha survives:
- A **−30% crash** (COVID, Q1 2020)
- A **liquidity-driven recovery** (mid-2020 to 2021)
- A **different interest rate environment** (near-zero in 2020 vs 5% in 2023)

Expanding to 2020-2024 answers: *"Does the Kronos model add alpha across ALL market regimes, not just the 2022-2024 rate-hike cycle?"*

---

## 2. Architecture

Single GPU run, single precompute pass, single walk-forward. No changes to `walkforward.py`, `metrics.py`, or `compare_finetune.py`. The regime decomposition is a post-processing step that computes metrics on sub-slices of the already-computed equity curve.

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

The new section appended to `compare_finetune.py` output:

```
=== Thai Equity — Walk-Forward Backtest (2020-2024) ===
Tickers: 49 | Calendar: 5-day (business) | Equal weight

  Full Period (2020-2024):
    CAGR: +X.XX%  Sharpe: X.XX  Max DD: -XX.XX%  Alpha vs EW: +XX.Xpp

  Period Breakdown:
  Period               CAGR     Sharpe     Max DD     Alpha vs EW      Verdict
  -------------------------------------------------------------------------------
  Stress  (2020 H1)    +X.XX%    X.XX      -XX.XX%    +XX.Xpp          Survive/Thrive
  Rebound (2020-2021)  +X.XX%    X.XX      -XX.XX%    +XX.Xpp          Thrive/Flat
  Current (2022-2024)  +31.44%   1.40      -17.97%    +30.0pp          Already known

  → Stress period: does the model survive a -30% crash?
  → Rebound period: does the model capture the recovery?
  → Alpha positive in all 3 periods = model works everywhere.
```

### Per-Period Verdict Rules

| Condition | Verdict |
|-----------|---------|
| Alpha > 0 AND Sharpe > 0.5 | Survive |
| Alpha > 0 AND CAGR > 0 | Thrive |
| Alpha > 0 AND CAGR < 0 | Mitigate (reduces losses vs equal-weight) |
| Alpha ≤ 0 | Struggle (model adds no value in this regime) |

### Note for Lower 5-Year CAGR

If the 5-year CAGR is lower than the current 31.44%, the output will include:

> Lower 5-year CAGR does NOT mean the model is worse. The 2020 COVID crash (−30%) is included in this run. A 3-year window that excluded that crash naturally shows higher CAGR. The relevant metric is **alpha per period** — if alpha is positive in all 3 periods, the model adds value regardless of market direction.

---

## 4. Time Estimate

| Step | Time | Notes |
|------|------|-------|
| D1: Delete old forecast cache | 1 min | Cache covers 2022-2024 only; must regenerate for 2020-2024 |
| D1: ZS precompute (49 tkrs × 1,260 days) | ~7.5 hrs | Idempotent — can be stopped and resumed |
| D2: Walk-forward | ~90 sec | Negligible |
| D2: Period decomposition computation | ~10 sec | Post-processing on equity curve slices |
| D2: Output + save | ~30 sec | — |
| **Total** | **~7.5 hrs** | 1 overnight session |

---

## 5. Dependencies

- `kth/backtest/walkforward.py` — `precompute_forecasts()`, `run_walkforward()`, `BacktestConfig`
- `kth/backtest/metrics.py` — `compute_sharpe()`, `compute_max_drawdown()`, `compute_metrics()`
- `kth/data/universe.py` — `UNIVERSE`, `get_all_tickers()`
- `kth/data/loader.py` — `load_cached()`
- `data/forecast_cache/NeoQuasar_Kronos-small/` — existing ZS cache (will be rebuilt for new date range)
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

---

*Document version: 2026-05-24. Reviewed: HF manager + trader.*
