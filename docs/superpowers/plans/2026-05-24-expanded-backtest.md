# Expanded Backtest (2020-2024) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a 5-year Thai equity backtest (2020-2024) with COVID crash and recovery regime decomposition. Single GPU session (~10.5 hrs).

**Architecture:** Create `scripts/run_expanded_backtest.py` that orchestrates: (1) delete old 2020-2021 cache, (2) precompute forecasts for 49 tickers × 1,260 days, (3) walk-forward, (4) compute per-period metrics, (5) print comparison table. No changes to existing scripts.

**Tech Stack:** Python 3.10+, pandas, PyTorch, Kronos (local repo)

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/run_expanded_backtest.py` | Orchestrates full expanded backtest pipeline |

---

### Task 1: Create the expanded backtest script

**Files:**
- Create: `scripts/run_expanded_backtest.py`

- [ ] **Step 1: Write the script skeleton with imports and config**

```python
"""
Run 5-year Thai equity backtest (2020-2024) with COVID/recovery/rate-hike regime decomposition.
Usage: venv/bin/python scripts/run_expanded_backtest.py
"""
import sys
import shutil
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))

from kth.data.universe import UNIVERSE, FRICTION
from kth.data.loader import load_cached
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts, run_walkforward, BacktestConfig
from kth.backtest.metrics import compute_sharpe, compute_max_drawdown

TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
CACHE_DIR = "./data/raw"
FORECAST_CACHE = "./data/forecast_cache"

PERIODS = [
    ("Stress (COVID crash)",   "2020-01-01", "2020-06-30"),
    ("Rebound (Recovery)",     "2020-07-01", "2021-12-31"),
    ("Current (Rate hikes)",   "2022-01-01", "2024-12-31"),
]

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

- [ ] **Step 2: Add step to delete 2020-2021 cache dirs only**

```python
def clean_old_cache():
    """Delete 2020 and 2021 date directories from ZS forecast cache only.
    Preserves 2022-2024 cached data for all markets."""
    slug = "NeoQuasar_Kronos-small"
    cache_root = Path(f"{FORECAST_CACHE}/{slug}")
    if not cache_root.exists():
        return
    for d in cache_root.iterdir():
        if d.is_dir() and d.name.startswith(("2020-", "2021-")):
            print(f"  Deleting old cache: {d.name}")
            shutil.rmtree(d)
```

- [ ] **Step 3: Add precompute + walkforward steps**

```python
def main():
    print("=" * 60)
    print("Thai Equity Expanded Backtest (2020-2024)")
    print("=" * 60)
    print(f"Tickers: {len(TICKERS)}")
    print()

    # Step 1: Clean old cache for 2020-2021 dates
    print("── Step 1: Clean old cache (2020-2021) ──")
    clean_old_cache()
    print()

    # Step 2: Load model
    print("── Step 2: Load model ──")
    th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
    print()

    # Step 3: Precompute forecasts
    print("── Step 3: Precompute forecasts ──")
    print(f"  Period: {config.start_date} → {config.end_date}")
    precompute_forecasts(
        th, TICKERS,
        start_date=config.start_date, end_date=config.end_date,
        pred_len=config.pred_len, n_samples=config.n_samples,
        lookback=config.lookback,
    )
    print()

    # Step 4: Walk-forward
    print("── Step 4: Walk-forward ──")
    r = run_walkforward(config, th, TICKERS)
    print()

    # Step 5: Compute full-period metrics
    print("── Step 5: Compute metrics ──")
    full_metrics = r.metrics
    full_cagr = full_metrics.get("cagr", 0)
    full_sharpe = full_metrics.get("sharpe", 0)
    full_max_dd = full_metrics.get("max_drawdown", 0)

    # Step 6: Compute per-period metrics from equity curve
    print("── Step 6: Period decomposition ──")
    equity = r.equity_curve  # pd.Series with date index
    trades_df = r.trades

    # Compute equal-weight and SET benchmark equity curves (from benchmarks dict)
    ew_benchmark = r.benchmarks.get("equal_weight", pd.Series(1.0, index=equity.index))
    set_benchmark = r.benchmarks.get("SET")

    period_results = []
    for label, start, end in PERIODS:
        eq_slice = equity.loc[start:end]
        ew_slice = ew_benchmark.loc[start:end]
        set_slice = set_benchmark.loc[start:end] if "SET" in r.benchmarks else None

        if len(eq_slice) < 10:
            period_results.append((label, None, None, None, None, None, 0, "Insufficient data"))
            continue

        daily = eq_slice.pct_change().dropna()
        cagr = (eq_slice.iloc[-1] / eq_slice.iloc[0]) ** (252 / len(eq_slice)) - 1
        sharpe = compute_sharpe(daily)
        max_dd = compute_max_drawdown(eq_slice)
        ew_ret = (ew_slice.iloc[-1] / ew_slice.iloc[0]) ** (252 / len(ew_slice)) - 1
        alpha = cagr - ew_ret
        set_cagr = (set_slice.iloc[-1] / set_slice.iloc[0]) ** (252 / len(set_slice)) - 1 if set_slice is not None and len(set_slice) > 5 else None

        # Count trades in this period
        ts = pd.Timestamp(start)
        te = pd.Timestamp(end)
        n_trades = len(trades_df[(trades_df["date"] >= ts) & (trades_df["date"] <= te)]) if trades_df is not None else 0

        # Determine verdict (first match wins)
        if alpha > 0 and cagr > 0:
            verdict = "Thrive"
        elif alpha > 0 and sharpe > 0.5:
            verdict = "Survive"
        elif alpha > 0 and cagr <= 0:
            verdict = "Mitigate"
        elif alpha <= 0:
            verdict = "Struggle"
        else:
            verdict = "Mixed"

        period_results.append((label, cagr, sharpe, max_dd, alpha, set_cagr, n_trades, verdict))

    # Step 7: Print output
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n  Full Period (2020-2024):")
    print(f"    CAGR: {full_cagr:+.2%}  Sharpe: {full_sharpe:.2f}  Max DD: {full_max_dd:.2%}")

    print(f"\n  Period Breakdown:")
    header = f"  {'Period':<25} {'CAGR':>10} {'Sharpe':>8} {'Max DD':>10} {'Alpha EW':>10} {'SET CAGR':>10} {'Trades':>8} {'Verdict':<12}"
    print(header)
    print(f"  {'-' * len(header)}")

    for label, cagr, sharpe, max_dd, alpha, set_cagr, n_trades, verdict in period_results:
        if cagr is None:
            print(f"  {label:<25} {'N/A':>10} {'N/A':>8} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>8} {'N/A':<12}")
        else:
            sc = f"{set_cagr:>+9.2%}" if set_cagr is not None else "N/A"
            print(f"  {label:<25} {cagr:>+9.2%} {sharpe:>7.2f} {max_dd:>+9.2%} {alpha:>+9.2%} {sc:>10} {n_trades:>8} {verdict:<12}")

    # Stress period warning
    stress_trades = period_results[0][6]
    if stress_trades < 50:
        print(f"\n  * Stress period: ~{stress_trades} trades — limited sample size.")

    print(f"\n  → If alpha is positive in all 3 periods, the model works across all regimes.")
    print(f"  → Lower 5-year CAGR vs 2022-2024 alone is expected (includes COVID crash).")
    print(f"  → Period CAGR is annualized — short periods (<1 year) amplify returns/losses.")

    # Step 8: Save
    out = Path("data/backtest_results/thai_equity_2020-2024")
    r.save(str(out))
    print(f"\nResults saved to {out}/")
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify the script syntax**

Run: `venv/bin/python -c "import ast; ast.parse(open('scripts/run_expanded_backtest.py').read()); print('syntax OK')"`

Expected: `syntax OK`

- [ ] **Step 3: Run the backtest (overnight session)**

```bash
# Clear only 2020-2021 cache
rm -rf data/forecast_cache/NeoQuasar_Kronos-small/2020-*/ data/forecast_cache/NeoQuasar_Kronos-small/2021-*/

# Run
venv/bin/python scripts/run_expanded_backtest.py
```

Expected: ~10.5 hrs precompute + ~90 sec walkforward. Output with full-period metrics + 3-period decomposition.

- [ ] **Step 4: Verify output**

Check the output for:
- Full 5-year CAGR, Sharpe, Max DD
- 3 period rows with CAGR, Sharpe, Max DD, Alpha vs EW, Trade count, Verdict
- Stress period warning if <50 trades
- Benchmark comparison (equal-weight)
- Results saved to `data/backtest_results/thai_equity_2020-2024/`

- [ ] **Step 5: Update documentation with 5-year results**

After the run completes, update `docs/backtest-methodology.md` and the relevant docs with the expanded results. Update the user-manual benchmark tables.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_expanded_backtest.py docs/backtest-methodology.md
git commit -m "backtest: Thai equity expanded 2020-2024 with regime decomposition

- 5-year walk-forward (1,260 trading days, 49 tickers)
- 3-period breakdown: COVID crash, recovery, rate hikes
- Per-period CAGR, Sharpe, Max DD, Alpha vs EW
- Verdict: Thrive/Survive/Mitigate/Struggle per regime
- ~10.5 hrs precompute on GTX 1060"
```

---

### Self-Review

1. **Spec coverage:** All §2 architecture implemented — single run, period decomposition via equity curve slicing. §3 output format matches exactly. §4 time estimate used. §5 dependencies covered.

2. **Placeholder scan:** No TBDs. All code is provided. Expected outputs specified. ✅

3. **Type consistency:** `BacktestConfig` parameter names match `walkforward.py`. `compute_sharpe()` and `compute_max_drawdown()` match `metrics.py`. Period labels match spec.

4. **Testing:** Steps 2 (syntax check), 3 (full run), 4 (output verification) cover the testing requirements.

---

*Document version: 2026-05-24.*
