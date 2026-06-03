# Local Testing Phase 2 — GPU (51 Tickers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full 51-ticker walk-forward backtest + daily report pipeline on a GPU machine (Linux or Windows). Same codebase as Phase 1, just different hardware.

**Architecture:** Install torch with CUDA, run `precompute_forecasts()` for all 51 tickers over 750 trading days (~30-90 min on T4 — GPU batches 51 tickers per day, not sequential single-ticker), then `run_walkforward()` from the cache (~instant), then generate daily report with calibration-based confidence flags from backtest results. No new library code — all existing modules run as-is.

> **HuggingFace model ID:** `"NeoQuasar/Kronos-small"` must be verified before running. Check https://huggingface.co/NeoQuasar/Kronos-small — if absent, find the correct org/repo and update all scripts.
>
> **Cache path coupling:** `precompute_forecasts(cache_dir=...)` and `BacktestConfig(forecast_cache_dir=...)` must point to the same directory. Both default to `"./data/forecast_cache"` — only override if you change one, you must change both.

**Tech Stack:** Python 3.10+, `torch` (CUDA), `kronos`, `huggingface_hub`, `pandas`, `numpy`, `yfinance`

**Prerequisites:** Phase 1 must pass first (confirms kronos installs and works).

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/setup_gpu.sh` | One-command CUDA deps install + Windows equivalent |
| Create | `scripts/setup_gpu.ps1` | Windows PowerShell version |
| Create | `scripts/run_backtest.py` | Precompute forecasts → walkforward → save results |
| Create | `scripts/run_daily_report.py` | Run forecast batch → build report with calibration |

---

### Task 1: Verify GPU machine prerequisites

- [ ] **Step 1: Check CUDA**

```bash
nvidia-smi
```
Expected: shows GPU model, driver version, CUDA version.

- [ ] **Step 2: Check Python**

```bash
python --version
```
Expected: Python 3.10+

- [ ] **Step 3: Clone repo** (or copy from Phase 1 machine)

```bash
git clone <repo-url> kronos-th
cd kronos-th
```

---

### Task 2: Create `scripts/setup_gpu.sh` (Linux) and `scripts/setup_gpu.ps1` (Windows)

**Files:**
- Create: `scripts/setup_gpu.sh`
- Create: `scripts/setup_gpu.ps1`

- [ ] **Step 1: Write Linux setup script**

```bash
#!/bin/bash
# Setup Kronos-TH for GPU testing — Phase 2 (Linux)
set -e

echo "=== Kronos-TH Phase 2 Setup (GPU - Linux) ==="

echo "[1/5] Installing PyTorch with CUDA 12.1..."
pip install torch --index-url https://download.pytorch.org/whl/cu121

echo "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

echo "[3/5] Installing kronos..."
pip install kronos 2>/dev/null || pip install git+https://github.com/shiyu-coder/Kronos.git

echo "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

echo "[5/5] Verifying CUDA..."
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'CUDA OK — {torch.cuda.get_device_name(0)}')"

echo ""
echo "=== Setup complete ==="
echo "Next: python scripts/download_data.py"
echo "Then: python scripts/run_backtest.py"
```

- [ ] **Step 2: Write Windows setup script**

```powershell
# Setup Kronos-TH for GPU testing — Phase 2 (Windows)
# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_gpu.ps1

Write-Host "=== Kronos-TH Phase 2 Setup (GPU - Windows) ==="

Write-Host "[1/5] Installing PyTorch with CUDA 12.1..."
pip install torch --index-url https://download.pytorch.org/whl/cu121

Write-Host "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

Write-Host "[3/5] Installing kronos..."
pip install kronos 2>$null; if ($LASTEXITCODE -ne 0) { pip install git+https://github.com/shiyu-coder/Kronos.git }

Write-Host "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

Write-Host "[5/5] Verifying CUDA..."
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available!'; print(f'CUDA OK — {torch.cuda.get_device_name(0)}')"

Write-Host ""
Write-Host "=== Setup complete ==="
```

- [ ] **Step 3: Make Linux script executable**

```bash
chmod +x scripts/setup_gpu.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_gpu.sh scripts/setup_gpu.ps1
git commit -m "feat: add Phase 2 GPU setup scripts (Linux + Windows)"
```

---

### Task 3: Create `scripts/run_backtest.py`

**Files:**
- Create: `scripts/run_backtest.py`

- [ ] **Step 1: Write backtest script**

```python
"""
Phase 2 — Full 51-ticker walk-forward backtest on GPU.

Required: scripts/download_data.py run first.
          ~30-90 min on T4 GPU (one-time precomputation, idempotent — resumes from cache).
          Subsequent runs skip already-cached dates (~instant).
          Writes ~76,500 files: one .parquet + one _meta.json per ticker per trading day,
          organized as: ./data/forecast_cache/{model_slug}/{YYYY-MM-DD}/{ticker}.parquet
"""
import time
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import (
    BacktestConfig, precompute_forecasts, run_walkforward
)
from kth.data.universe import get_all_tickers


OUTPUT_DIR = Path("./data/backtest_results/2022-2024")


def main():
    tickers = get_all_tickers()
    print(f"Universe: {len(tickers)} tickers across 9 asset classes\n")

    # 1. Load model (GPU)
    print("Loading Kronos-small on CUDA...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
    print(f"  Model: {k.model_name}")
    print(f"  Device: {k.device}")

    # 2. Backtest config
    config = BacktestConfig(
        start_date="2022-01-01",
        end_date="2024-12-31",
        lookback=400,
        pred_len=20,
        n_samples=50,
        position_sizing="equal",
    )

    # 3. Precompute forecasts (one-time, ~30-90 min on T4 — batches all 51 tickers per day)
    print(f"\nPrecomputing forecasts for {len(tickers)} tickers x ~750 days...")
    print("(Idempotent — skips already-cached dates. Writes ~76,500 parquet+json files.)")
    t0 = time.time()
    precompute_forecasts(
        k, tickers,
        start_date=config.start_date,
        end_date=config.end_date,
        pred_len=config.pred_len,
        n_samples=config.n_samples,
        lookback=config.lookback,
    )
    elapsed = time.time() - t0
    print(f"Precomputation done in {elapsed/60:.0f} min ({elapsed/3600:.1f} hrs)")

    # 4. Run walk-forward backtest (reads from cache, ~instant)
    print("\nRunning walk-forward backtest...")
    t0 = time.time()
    result = run_walkforward(config, k, tickers)
    elapsed = time.time() - t0
    print(f"Backtest done in {elapsed:.1f}s")

    # 5. Print key metrics
    m = result.metrics
    print("\n=== KEY METRICS (net of friction) ===")
    print(f"  CAGR:              {m['cagr']:+.2%}")
    print(f"  Total Return:      {m['total_return']:+.2%}")
    print(f"  Sharpe:            {m['sharpe']:.2f}")
    print(f"  Sortino:           {m['sortino']:.2f}")
    print(f"  Max Drawdown:      {m['max_drawdown']:.2%}")
    print(f"  Calmar:            {m['calmar']:.2f}")
    print(f"  Hit Rate:          {m['hit_rate']:.2%}")
    print(f"  Profit Factor:     {m['profit_factor']:.2f}")
    print(f"  Total Friction:    {m['total_friction_paid']:.4f}")
    print(f"  Annual Turnover:   {m['annual_turnover']:.2f}")
    print(f"  VaR 95% (1d):      {m['var_95']:+.4f}")
    print(f"  Alpha (vs EW):     {m['alpha']:+.4f}")
    print(f"  Beta (vs EW):      {m['beta']:.3f}")
    print(f"  t-stat (vs EW):    {m['t_stat']:.2f} (p={m['p_value']:.3f})")

    # 6. Per-class attribution
    print("\n=== PER-CLASS ATTRIBUTION ===")
    attr = result.per_class_attribution
    if not attr.empty:
        print(attr.to_string(index=False))

    # 7. Benchmark comparison
    print("\n=== BENCHMARK COMPARISON (CAGR) ===")
    for name, curve in result.benchmarks.items():
        bench_cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / (len(curve)/252)) - 1
        print(f"  {name:15s} {bench_cagr:+.2%}")

    # 8. Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.save(str(OUTPUT_DIR))
    print(f"\nResults saved to: {OUTPUT_DIR}")

    # 9. Re-run with inv_vol sizing for comparison
    print("\n\nRe-running with inverse-volatility sizing...")
    config_invvol = BacktestConfig(
        start_date="2022-01-01",
        end_date="2024-12-31",
        lookback=400,
        pred_len=20,
        n_samples=50,
        position_sizing="inv_vol",
    )
    result_invvol = run_walkforward(config_invvol, k, tickers)
    m2 = result_invvol.metrics
    print(f"\n=== INV-VOL SIZING ===")
    print(f"  Sharpe:  {m2['sharpe']:.2f} (equal: {m['sharpe']:.2f})")
    print(f"  Max DD:  {m2['max_drawdown']:.2%} (equal: {m['max_drawdown']:.2%})")
    invvol_dir = Path("./data/backtest_results/2022-2024_invvol")
    result_invvol.save(str(invvol_dir))
    print(f"Saved to: {invvol_dir}")

    print("\n=== PHASE 2 COMPLETE ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run** (after GPU setup + data download)

Run: `python scripts/run_backtest.py`
Expected: prints metrics table, per-class attribution, benchmark comparison, saves results to `./data/backtest_results/`

- [ ] **Step 3: Commit**

```bash
git add scripts/run_backtest.py
git commit -m "feat: add Phase 2 GPU backtest script (51 tickers)"
```

---

### Task 4: Create `scripts/run_daily_report.py`

**Files:**
- Create: `scripts/run_daily_report.py`

- [ ] **Step 1: Write daily report script**

```python
"""
Phase 2 — Generate daily decision report with calibration-based confidence flags.

Requires: scripts/run_backtest.py completed (BacktestResult saved to disk).
          scripts/download_data.py run recently (data not stale).
"""
import pandas as pd
from datetime import date
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached
from kth.data.universe import get_all_tickers
from kth.backtest.walkforward import BacktestResult
from kth.utils.report import build_report_table, render_html


OUTPUT_DIR = Path("./data/backtest_results/2022-2024")


def main():
    # 1. Load model (GPU)
    print("Loading Kronos-small on CUDA...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
    print(f"  Model: {k.model_name}")

    # 2. Run forecasts on all 51 tickers (today's prices)
    tickers = get_all_tickers()
    print(f"\nForecasting {len(tickers)} tickers (n_samples=50)...")
    forecasts = k.forecast_batch(tickers, pred_lens=[5, 20], n_samples=50)
    print(f"  Done. {len(forecasts)} tickers returned.")

    # 3. Build last_closes from latest cached data
    last_closes = {}
    for t in tickers:
        try:
            df = load_cached(t)
            last_closes[t] = float(df["close"].iloc[-1])
        except FileNotFoundError:
            print(f"  WARNING: {t} not cached — skipping")

    # 4. Load backtest result for calibration-based confidence
    br = None
    if (OUTPUT_DIR / "metrics.json").exists():
        print(f"\nLoading backtest results from {OUTPUT_DIR}...")
        br = BacktestResult.load(str(OUTPUT_DIR))
        print(f"  Sharpe: {br.metrics.get('sharpe', 'N/A')}")
        print(f"  Hit rate: {br.metrics.get('hit_rate', 'N/A')}")
    else:
        print("\nNo backtest results — using band-width confidence fallback.")

    # 5. Build report tables
    adj_table, raw_table = build_report_table(
        forecasts, last_closes, backtest_result=br, long_threshold=0.01
    )

    # 6. Print top 10 by score
    print(f"\n=== TOP 10 BY CONFIDENCE-ADJUSTED SCORE ===")
    print(adj_table.head(10)[["Ticker", "Class", "20d p50", "Signal", "Confidence", "Score"]].to_string(index=False))

    # 7. Save HTML
    today = date.today().isoformat()
    html_path = render_html(
        (adj_table, raw_table),
        f"./reports/{today}.html",
        k.model_name,
        pd.Timestamp.now(),
    )
    print(f"\nHTML report saved to: {html_path}")

    print("\n=== DAILY REPORT COMPLETE ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

Run: `python scripts/run_daily_report.py`
Expected: prints top 10 tickers, saves `./reports/YYYY-MM-DD.html` with calibration-based confidence flags

- [ ] **Step 3: Commit**

```bash
git add scripts/run_daily_report.py
git commit -m "feat: add Phase 2 daily report script (calibration-based confidence)"
```

---

### Task 5: Quick-start guide — add to README or separate doc

- [ ] **Step 1: Verify the full pipeline runs in order**

```bash
# On GPU machine, after clone:
bash scripts/setup_gpu.sh        # (or powershell for Windows)
python scripts/download_data.py
python scripts/run_backtest.py   # ~30-90 min first time on T4, ~30s on rerun
python scripts/run_daily_report.py
```

- [ ] **Step 2: Open `./reports/YYYY-MM-DD.html` in browser and verify**

Expected:
- Both tables rendered (Confidence-Adjusted + Raw Forecasts)
- Per-class confidence flags with hit rates shown
- Green/yellow/red color coding matches thresholds
- Disclaimer section present

---

### Self-Review

- [x] Spec coverage: All Phase 2 steps covered — GPU setup, precomputation, walk-forward, save/load, daily report with calibration
- [x] Placeholder scan: No TBDs. All paths, dates, and thresholds explicit.
- [x] Type consistency: `BacktestResult.load()` restores full object. `render_html` accepts tuple. `build_report_table` accepts `BacktestResult`.
- [x] Scope: GPU-only, 51 tickers. Assumes Phase 1 passed. No fine-tuning (Spec C still requires Colab T4 due to 8-hour runs).
- [x] Cross-platform: Both `.sh` (Linux) and `.ps1` (Windows) setup scripts provided.
- [x] GPU time: Updated to ~30-90 min on T4 (batches 51 tickers per day, not sequential single-ticker).
- [x] File structure: ~76,500 files (.parquet + _meta.json per ticker per day) in dated subdirectories.
- [x] Cache path: Both `precompute_forecasts` and `BacktestConfig` default to `"./data/forecast_cache"` — documented coupling.
- [x] HuggingFace model ID: `"NeoQuasar/Kronos-small"` flagged for verification before running.
