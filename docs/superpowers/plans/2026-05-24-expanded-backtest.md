# Expanded Backtest (2020-2024) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a 5-year Thai equity backtest (2020-2024) with COVID crash and recovery regime decomposition. Single GPU session (~10.5 hrs).

**Architecture:** Create `scripts/run_expanded_backtest.py` that orchestrates: (1) pre-flight data validation, (2) delete old 2020-2021 cache, (3) precompute forecasts for 49 tickers × 1,260 days with checkpoint state, (4) walk-forward, (5) compute per-period metrics with p-values, (6) print comparison table with survivorship bias disclosure. Uses `BacktestConfig` from `walkforward.py` (not hardcoded paths). No changes to existing library code.

**Design Review Applied (2026-05-24):** Fixes from code review: step ordering, error handling with resume, pre-flight validation, survivorship bias note, per-period p-values, logging to file, dry-run mode.

**Tech Stack:** Python 3.10+, pandas, PyTorch, Kronos (local repo)

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/run_expanded_backtest.py` | Orchestrates full expanded backtest pipeline |

---

### ⚠️ Pre-Implementation Notes

#### Survivorship Bias
The 49 Thai tickers in `UNIVERSE["thai_equity"]` are tickers that exist today. If any Thai companies were delisted during COVID (tourism, hospitality, airlines), they are excluded. This overstates crash-period performance. **No fix is possible** without reconstructing historical universe membership (no free data source), but the output must include a disclaimer:
> *"Universe is point-in-time (2025). Delisted/merged tickers from 2020-2022 are excluded. COVID stress period results may be overstated."*

#### Per-Period p-Values
`compute_metrics()` in `kth/backtest/metrics.py` already computes `p_value` (t-test vs benchmark). Each period's equity curve slice can be passed through `compute_metrics()` to get a period-level p-value. The stress period (~30 trades) will likely have p >> 0.3 — report as "Inconclusive" rather than assigning a verdict label.

#### Existing Code Reuse
- `walkforward.py` already has `_compute_benchmarks()` that computes SET benchmark — `r.benchmarks["SET"]` is available.
- `BacktestConfig` already has `cache_dir` and `forecast_cache_dir` parameters.
- `precompute_forecasts()` already filters non-viable tickers by history length.
- Scripts use `kth` as an installed package (`pip install -e .`), NOT `sys.path` hacks.

#### Sample Count vs Time Trade-off
The 2022-2024 backtest used `n_samples=50`. The expanded run uses `n_samples=10` due to 5x longer period (1,260 vs 750 days). Time estimate of 10.5 hrs assumes 10 samples; 50 samples would take ~52 hrs (infeasible overnight).
- Results across periods are **not directly comparable** due to different sample counts.
- The sample count trade-off is documented — do NOT change `n_samples` without updating the time estimate.

#### Alpha Metric Consistency
Two alpha definitions exist in the codebase:
- **OLS alpha** from `compute_metrics()`: regression intercept × 252 (excess return after removing beta exposure)
- **CAGR alpha**: `CAGR_strategy - CAGR_benchmark` (simple difference, includes beta)
The per-period decomposition uses CAGR alpha for interpretability. The full-period output should also display CAGR alpha (not OLS) for consistency across the table. OLS alpha is available as supplementary info.

#### GPU Memory
A 10.5-hr precompute loop may accumulate GPU memory over 1,260 days. PyTorch `.empty_cache()` is not a guarantee. The `precompute_forecasts()` function creates `kronos_th.forecast_batch()` per day — each call may hold GPU tensors until garbage collection. If OOM occurs mid-run, the `--resume` flag restarts from the last incomplete day (idempotent, skips cached dates). Consider monitoring with `nvidia-smi` during the first hour.

#### Concentration Risk
`max_positions=5` for 49 tickers means ~10% of the universe is held. In a crash, a single position in a vulnerable sector (tourism, hospitality) could dominate portfolio drawdown. The equal-weight benchmark holds all 49, so the comparison inherently tests whether the model's stock selection avoids crash victims. If the stress period shows "Struggle," concentration risk is the likely cause — document this in the post-hoc analysis.

#### p-Value Caveat
The t-test in `compute_metrics()` assumes independent daily returns. Daily returns exhibit autocorrelation, making p-values anti-conservative (too small). For the stress period (~125 days), this is a minor concern. For the full period (1,260 days), it's negligible. No fix applied — standard practice for backtest p-values.

---

### Task 1: Create the expanded backtest script

**Files:**
- Create: `scripts/run_expanded_backtest.py`

- [ ] **Step 1: Script skeleton with imports, config, logging**

```python
"""
Run 5-year Thai equity backtest (2020-2024) with COVID/recovery/rate-hike regime decomposition.

Usage:
    venv/bin/python scripts/run_expanded_backtest.py              # full run
    venv/bin/python scripts/run_expanded_backtest.py --dry-run    # pre-flight only
    venv/bin/python scripts/run_expanded_backtest.py --resume     # resume from checkpoint

Checkpoint file: data/forecast_cache/run_expanded_backtest.json
"""
import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from kth.backtest.metrics import compute_metrics
from kth.backtest.walkforward import (
    BacktestConfig, precompute_forecasts, run_walkforward,
)
from kth.data.loader import load_cached
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH

logger = logging.getLogger("expanded_backtest")

TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]

PERIODS = [
    ("Stress (COVID crash)",   "2020-01-01", "2020-06-30"),
    ("Rebound (Recovery)",     "2020-07-01", "2021-12-31"),
    ("Current (Rate hikes)",   "2022-01-01", "2024-12-31"),
]

VERDICTS = [
    ("Thrive",    lambda a, c, s: a > 0 and c > 0),
    ("Survive",   lambda a, c, s: a > 0 and s > 0.5),
    ("Mitigate",  lambda a, c, s: a > 0 and c <= 0),
    ("Struggle",  lambda a, c, s: a <= 0),
]

CHECKPOINT_PATH = Path("data/forecast_cache/run_expanded_backtest.json")
OUTPUT_DIR = Path("data/backtest_results/thai_equity_2020-2024")

# NOTE: n_samples=10 (not 50 from 2022-2024 run) due to 5x longer period.
# 50 samples would take ~52 hrs — not feasible overnight.
# Results across periods are NOT directly comparable due to sample count difference.
config = BacktestConfig(
    start_date="2020-01-01",
    end_date="2024-12-31",
    lookback=400, pred_len=20, n_samples=10,
    position_sizing="equal",
    max_positions=5,
    long_threshold=0.01,
    entry_buffer=0.005,
    min_holding_days=5,
)
```

- [ ] **Step 2: Utility functions**

```python
def _forecast_slug(model_name: str) -> str:
    """Match walkforward.py's _model_slug convention."""
    return model_name.replace("/", "_").replace("@", "-").replace("\\", "_")


def _period_trades(trades_df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Filter trades to a date window. Handles empty/None trades_df."""
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    ts, te = pd.Timestamp(start), pd.Timestamp(end)
    return trades_df[(trades_df["date"] >= ts) & (trades_df["date"] <= te)].copy()


def _cagr_alpha(strat_eq: pd.Series, bm_eq: pd.Series) -> float:
    """CAGR alpha = CAGR_strategy - CAGR_benchmark.
    Both series should share the same date index (same trading days)."""
    years_strat = len(strat_eq) / 252
    years_bm = len(bm_eq) / 252
    if years_strat <= 0 or years_bm <= 0:
        return 0.0
    strat_cagr = (strat_eq.iloc[-1] / strat_eq.iloc[0]) ** (1 / years_strat) - 1
    bm_cagr = (bm_eq.iloc[-1] / bm_eq.iloc[0]) ** (1 / years_bm) - 1
    return strat_cagr - bm_cagr
```

- [ ] **Step 3: Pre-flight validation and dry-run**

```python
def validate_data(tickers: list[str], lookback: int, start_date: str) -> list[str]:
    """Check that all tickers have enough cached OHLCV data.
    Returns viable tickers. On dry-run, prints status per ticker."""
    viable = []
    missing = []
    start_ts = pd.Timestamp(start_date)
    min_date = start_ts - pd.Timedelta(days=int(lookback * 1.5))

    for t in tickers:
        try:
            df = load_cached(t)
            if len(df) < lookback:
                missing.append((t, f"only {len(df)} rows, need {lookback}"))
                continue
            if df["timestamps"].min() > min_date:
                missing.append((t, f"earliest data {df['timestamps'].min().date()}, need {min_date.date()}"))
                continue
            viable.append(t)
        except FileNotFoundError:
            missing.append((t, "not cached"))

    if missing:
        logger.warning("Data issues for %d tickers:", len(missing))
        for t, reason in missing:
            logger.warning("  %s: %s", t, reason)
    logger.info("Viable tickers: %d / %d", len(viable), len(tickers))
    return viable


def run_dry_run():
    """Check data availability, cache state, config — no GPU needed."""
    logger.info("=== DRY RUN ===")
    logger.info("Target: %d Thai equity tickers", len(TICKERS))

    viable = validate_data(TICKERS, config.lookback, config.start_date)

    # Check what's already cached
    model_name = "NeoQuasar/Kronos-small"
    cache_root = Path(config.forecast_cache_dir) / _forecast_slug(model_name)
    cached_dates = sorted(d.name for d in cache_root.iterdir() if d.is_dir()) if cache_root.exists() else []
    logger.info("Cached dates: %d (2020-2024 range)", len(cached_dates))
    cached_2020 = [d for d in cached_dates if d.startswith("2020")]
    cached_2021 = [d for d in cached_dates if d.startswith("2021")]
    logger.info("  2020 dates: %d, 2021 dates: %d", len(cached_2020), len(cached_2021))

    n_days = len(pd.date_range(start=config.start_date, end=config.end_date, freq="B"))
    est_hrs = n_days * len(viable) * 30 / 3600  # ~30 sec per day per batch
    logger.info("Estimated precompute: %.1f hrs (%d days x %d tickers)", est_hrs, n_days, len(viable))
    logger.info("Estimated walk-forward: ~90 sec")
    logger.info("Dry run — no execution. Run without --dry-run to proceed.")
```

- [ ] **Step 4: Checkpoint save/resume and cache cleaning**

```python
def save_checkpoint(state: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2, default=str))


def load_checkpoint() -> dict | None:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return None


def clean_old_cache(model_name: str):
    """Delete 2020 and 2021 date directories from forecast cache only.
    Preserves 2022-2024 cached data for all markets.
    model_name: e.g. 'NeoQuasar/Kronos-small'"""
    slug = _forecast_slug(model_name)
    cache_root = Path(config.forecast_cache_dir) / slug
    if not cache_root.exists():
        logger.info("No cache directory found at %s", cache_root)
        return
    deleted = 0
    for d in cache_root.iterdir():
        if d.is_dir():
            try:
                pd.Timestamp(d.name)
            except (ValueError, TypeError):
                continue
            if d.name.startswith(("2020-", "2021-")):
                logger.info("Deleting old cache: %s", d.name)
                shutil.rmtree(d)
                deleted += 1
    logger.info("Deleted %d cache directories (2020-2021)", deleted)
```

- [ ] **Step 5: Period decomposition function (reusable)**

```python
def decompose_periods(
    equity_curve: pd.Series,
    trades_df: pd.DataFrame,
    ew_benchmark: pd.Series,
    set_benchmark: pd.Series | None,
) -> list[dict]:
    """Slice equity curve by period, compute metrics + verdict for each.
    Uses CAGR alpha consistently (not OLS alpha from compute_metrics).
    Filters trades per period so trade-level metrics are correct."""
    results = []
    for label, start, end in PERIODS:
        eq = equity_curve.loc[start:end]
        ew = ew_benchmark.loc[start:end]
        set_s = set_benchmark.loc[start:end] if set_benchmark is not None else None

        if len(eq) < 10:
            results.append({"period": label, "status": "Insufficient data (<10 days)"})
            continue

        daily = eq.pct_change().dropna()
        period_trades = _period_trades(trades_df, start, end)
        metrics = compute_metrics(eq, daily, period_trades, ew)

        set_cagr = None
        if set_s is not None and len(set_s) > 5:
            set_cagr = (set_s.iloc[-1] / set_s.iloc[0]) ** (252 / len(set_s)) - 1

        cagr = metrics["cagr"]
        sharpe = metrics["sharpe"]
        alpha = _cagr_alpha(eq, ew)  # CAGR alpha, consistent across all periods
        p_value = metrics["p_value"]

        verdict = "Inconclusive"
        for v_name, cond in VERDICTS:
            if cond(alpha, cagr, sharpe):
                verdict = v_name
                break

        results.append({
            "period": label, "cagr": cagr, "sharpe": sharpe,
            "max_dd": metrics["max_drawdown"], "alpha": alpha,
            "p_value": p_value, "set_cagr": set_cagr,
            "n_trades": len(period_trades),  # individual transactions (buy + sell rows)
            "verdict": verdict,
        })
    return results


def print_results(
    full_metrics: dict,
    period_results: list[dict],
):
    """Print formatted output table."""
    print("\n" + "=" * 70)
    print("THAI EQUITY — WALK-FORWARD BACKTEST (2020-2024)")
    print("=" * 70)
    print(f"Tickers: 49 | Calendar: 5-day (business) | Equal weight | n_samples={config.n_samples}")
    print()
    print(f"Full Period (2020-2024):")
    print(f"  CAGR: {full_metrics['cagr']:+9.2%}  Sharpe: {full_metrics['sharpe']:6.2f}  "
          f"Max DD: {full_metrics['max_drawdown']:+8.2%}  "
          f"Alpha vs EW: {full_metrics.get('alpha_cagr', full_metrics.get('alpha', 0)):+8.2%}  "
          f"p={full_metrics['p_value']:.3f}")
    print()
    print(f"{'Period':<25} {'CAGR':>9} {'Sharpe':>7} {'Max DD':>9} {'Alpha EW':>9} "
          f"{'SET CAGR':>9} {'Trades':>7} {'p-value':>8} {'Verdict':<12}")
    print("-" * 98)
    for p in period_results:
        if "status" in p:
            print(f"{p['period']:<25} {'N/A':>9} {'N/A':>7} {'N/A':>9} "
                  f"{'N/A':>9} {'N/A':>9} {'N/A':>7} {'N/A':>8} {p['status']:<12}")
        else:
            sc = f"{p['set_cagr']:+8.2%}" if p['set_cagr'] is not None else "N/A"
            print(f"{p['period']:<25} {p['cagr']:+8.2%} {p['sharpe']:6.2f} "
                  f"{p['max_dd']:+8.2%} {p['alpha']:+8.2%} {sc:>9} "
                  f"{p['n_trades']:>7} {p['p_value']:7.3f} {p['verdict']:<12}")

    # Caveats
    sp = next((p for p in period_results if "stress" in p["period"].lower()), None)
    if sp and "n_trades" in sp and sp["n_trades"] < 50:
        print(f"\n  * Stress period: ~{sp['n_trades']} trades (~125 days) — limited sample size. "
              f"p={sp['p_value']:.3f} indicates inconclusive.")
    print("\n  → Universe is point-in-time (2025). Delisted/merged tickers from 2020-2022")
    print("    are excluded. COVID stress period results may be overstated.")
    print("  → Alpha per period is the relevant metric for regime analysis.")
    print("  → Lower 5-year CAGR vs 2022-2024 alone is expected (includes COVID crash).")
    print("  → Multi-period testing: 3 periods × α=0.05 → ~14% probability of ≥1 false positive.")
```

- [ ] **Step 6: Main orchestration with error handling and resume**

```python
def main():
    parser = argparse.ArgumentParser(description="Expanded backtest 2020-2024")
    parser.add_argument("--dry-run", action="store_true", help="Pre-flight check only")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("data/logs/expanded_backtest.log"),
            logging.StreamHandler(),
        ],
    )
    logger.info("Thai Equity Expanded Backtest (2020-2024)")
    logger.info("Tickers: %d", len(TICKERS))

    if args.dry_run:
        run_dry_run()
        return

    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            logger.info("Resuming from checkpoint (phase=%s)", checkpoint.get("phase"))
        else:
            logger.warning("No checkpoint found — starting fresh")
            checkpoint = None
    else:
        checkpoint = None

    # Phase 1: Data validation
    if not checkpoint or checkpoint.get("phase") == "validate":
        logger.info("Phase: validate")
        viable = validate_data(TICKERS, config.lookback, config.start_date)
        if len(viable) < 40:
            logger.error("Only %d viable tickers — aborting", len(viable))
            sys.exit(1)
        save_checkpoint({"phase": "precompute", "viable": viable})
    else:
        viable = checkpoint.get("viable", TICKERS)
        logger.info("Skipping validation — %d viable from checkpoint", len(viable))

    # Phase 2: Clean 2020-2021 cache
    if not checkpoint or checkpoint.get("phase") == "precompute":
        logger.info("Phase: load model")
        th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
        logger.info("Phase: clean cache")
        clean_old_cache(th.model_name)

        # Phase 4: Precompute forecasts
        logger.info("Phase: precompute forecasts")
        logger.info("Period: %s → %s", config.start_date, config.end_date)
        t0 = time.time()
        try:
            precompute_forecasts(
                th, viable,
                start_date=config.start_date, end_date=config.end_date,
                pred_len=config.pred_len, n_samples=config.n_samples,
                lookback=config.lookback,
                cache_dir=config.forecast_cache_dir,
            )
        except Exception:
            logger.exception("Precompute failed at %.1f hrs", (time.time() - t0) / 3600)
            save_checkpoint({"phase": "precompute", "viable": viable})
            raise
        elapsed = time.time() - t0
        logger.info("Precompute done: %.1f hrs", elapsed / 3600)
        save_checkpoint({"phase": "walkforward", "viable": viable})
    else:
        th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")

    # Phase 5: Walk-forward
    logger.info("Phase: walk-forward")
    t0 = time.time()
    try:
        result = run_walkforward(config, th, viable)
    except Exception:
        logger.exception("Walk-forward failed")
        raise
    logger.info("Walk-forward done: %.1f sec", time.time() - t0)

    # Phase 6: Full-period metrics
    logger.info("Phase: metrics")
    full_metrics = result.metrics
    ew_benchmark = result.benchmarks.get("equal_weight", pd.Series(1.0, index=result.equity_curve.index))
    set_benchmark = result.benchmarks.get("SET")
    full_metrics["alpha_cagr"] = _cagr_alpha(result.equity_curve, ew_benchmark)

    # Phase 7: Period decomposition
    logger.info("Phase: period decomposition")
    period_results = decompose_periods(
        result.equity_curve, result.trades,
        ew_benchmark, set_benchmark,
    )

    # Phase 8: Output
    print_results(full_metrics, period_results)

    # Phase 9: Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.save(str(OUTPUT_DIR))
    logger.info("Results saved to %s", OUTPUT_DIR)
    logger.info("Done.")

    # Clean up checkpoint
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Verify the script syntax**

Run: `venv/bin/python -c "import ast; ast.parse(open('scripts/run_expanded_backtest.py').read()); print('syntax OK')"`

Expected: `syntax OK`

- [ ] **Step 8: Run dry-run to validate data availability**

```bash
venv/bin/python scripts/run_expanded_backtest.py --dry-run
```

Expected output: ticker data status, estimated time, no GPU activity. If <40 viable tickers, investigate data cache.

- [ ] **Step 9: Run the backtest (overnight session)**

```bash
# Ensure log directory exists
mkdir -p data/logs

# Run (with resume support — if it crashes, re-run with --resume)
venv/bin/python scripts/run_expanded_backtest.py

# If interrupted, resume:
# venv/bin/python scripts/run_expanded_backtest.py --resume
```

Expected: ~10.5 hrs precompute (n_samples=10) + ~90 sec walkforward. Output with full-period metrics + 3-period decomposition. Monitor GPU memory with `watch -n 60 nvidia-smi` during first hour.

- [ ] **Step 10: Verify output**

Check the output for:
- Full 5-year CAGR, Sharpe, Max DD with p-value
- 3 period rows with CAGR, Sharpe, Max DD, Alpha vs EW, p-value, Trade count, Verdict
- Survivorship bias disclaimer in output
- Stress period warning if <50 trades
- Log file at `data/logs/expanded_backtest.log`
- Results saved to `data/backtest_results/thai_equity_2020-2024/`

- [ ] **Step 11: Update documentation with 5-year results**

After the run completes, update `docs/backtest-methodology.md` and the relevant docs with the expanded results. Update the user-manual benchmark tables.

- [ ] **Step 12: Commit**

```bash
git add scripts/run_expanded_backtest.py docs/backtest-methodology.md
git commit -m "backtest: Thai equity expanded 2020-2024 with regime decomposition

- 5-year walk-forward (1,260 trading days, 49 tickers)
- 3-period breakdown: COVID crash, recovery, rate hikes
- Per-period CAGR, Sharpe, Max DD, Alpha vs EW, p-values
- Verdict: Thrive/Survive/Mitigate/Struggle per regime
- Checkpoint/resume, dry-run mode, file logging
- Survivorship bias disclosure for point-in-time universe
- ~10.5 hrs precompute on GTX 1060"
```

---

### Self-Review

1. **Spec coverage:** All §2 architecture implemented — single run, period decomposition via equity curve slicing. §3 output format matches. §4 time estimate used. §5 dependencies covered.

2. **Code review fixes applied (round 1):**
   - Step ordering corrected (1→12, no duplicates)
   - Error handling with try/except + checkpoint save/resume
   - Pre-flight validation with `--dry-run` mode
   - Period p-values via `compute_metrics()`
   - Survivorship bias disclosure in output
   - Logging to file via `logging` module
   - `BacktestConfig` parameters used instead of hardcoded paths
   - Period decomposition in reusable function
   - Verdict rules as declarative list

3. **Code review fixes applied (round 2):**
   - Removed `sys.path.insert` — `kth` is an installed package (`pip install -e .`)
   - Documented `n_samples=10` vs 50 trade-off with time implications
   - `clean_old_cache()` derives slug from model name, not hardcoded string
   - Switched to CAGR alpha everywhere (not OLS alpha) for consistency
   - `decompose_periods` now filters trades per period before passing to `compute_metrics`
   - Added GPU memory monitoring note
   - Added concentration risk disclosure for `max_positions=5`
   - Added p-value autocorrelation caveat

4. **Code review fixes applied (round 3):**
   - Reordered functions: `_forecast_slug` → `_period_trades` → `_cagr_alpha` defined before any callers
   - Renumbered steps 1→12 after inserting utility-function step
   - Added `n_samples` to output header so readers know sample count differs from 2022-2024 run

5. **Type consistency:** `BacktestConfig` parameter names match `walkforward.py`. `compute_metrics()` already returns all required fields. Period labels match spec.

6. **Testing:** Steps 7 (syntax), 8 (dry-run), 9 (full run), 10 (output verification) cover the testing requirements.

---

*Document version: 2026-05-24. Code review applied.*
