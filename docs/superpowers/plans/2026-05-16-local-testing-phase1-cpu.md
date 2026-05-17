# Local Testing Phase 1 — CPU (5 Tickers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the full Kronos-TH pipeline works end-to-end on CPU with real Kronos output on 5 representative tickers — from `pip install` to HTML report in ~10 minutes.

**Architecture:** Install torch CPU + kronos + huggingface_hub, download yfinance data, load Kronos-small on CPU, forecast 5 tickers, build report table, save HTML. No new library code — all existing modules (`kronos_wrapper.py`, `report.py`, `loader.py`) are used as-is.

**Tech Stack:** Python 3.10+, `torch` (CPU), `kronos` (PyPI or GitHub), `huggingface_hub`, `pandas`, `numpy`, `yfinance`

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `requirements.txt` | Uncomment `huggingface_hub>=0.20` |
| Create | `scripts/setup_cpu.sh` | One-command deps install (Linux/macOS/WSL2) |
| Create | `scripts/setup_cpu.ps1` | One-command deps install (Windows PowerShell) |
| Create | `scripts/run_forecast_demo.py` | Forecast 5 tickers → HTML report |

> **HuggingFace model ID:** `"NeoQuasar/Kronos-small"` must be verified before running. Check https://huggingface.co/NeoQuasar/Kronos-small — if absent, find the correct org/repo for the Kronos-small weights and update all scripts accordingly.

---

### Task 1: Uncomment huggingface_hub in requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Enable huggingface_hub**

In `requirements.txt`, change line 10 from:
```
# huggingface_hub>=0.20
```
to:
```
huggingface_hub>=0.20
```

- [ ] **Step 2: Verify**

Run: `pip install -r requirements.txt`
Expected: installs without errors (should be no-op if already installed)

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: enable huggingface_hub in requirements for local HF model downloads"
```

---

### Task 2: Create `scripts/setup_cpu.sh`

**Files:**
- Create: `scripts/setup_cpu.sh`

- [ ] **Step 1: Write setup script**

```bash
#!/bin/bash
# Setup Kronos-TH for local CPU testing — Phase 1
# Run: bash scripts/setup_cpu.sh

set -e

echo "=== Kronos-TH Phase 1 Setup (CPU) ==="

echo "[1/4] Installing PyTorch CPU..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "[2/4] Installing huggingface_hub..."
pip install huggingface_hub>=0.20

echo "[3/4] Installing kronos..."
pip install kronos 2>/dev/null || pip install git+https://github.com/shiyu-coder/Kronos.git

echo "[4/4] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

echo ""
echo "=== Setup complete ==="
echo "Next: download data with python scripts/download_data.py"
echo "Then: python scripts/run_forecast_demo.py"
```

- [ ] **Step 2: Write Windows setup script**

```powershell
# Setup Kronos-TH for local CPU testing — Phase 1 (Windows)
# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_cpu.ps1

Write-Host "=== Kronos-TH Phase 1 Setup (CPU - Windows) ==="

Write-Host "[1/4] Installing PyTorch CPU..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

Write-Host "[2/4] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

Write-Host "[3/4] Installing kronos..."
pip install kronos 2>$null; if ($LASTEXITCODE -ne 0) { pip install git+https://github.com/shiyu-coder/Kronos.git }

Write-Host "[4/4] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

Write-Host ""
Write-Host "=== Setup complete ==="
Write-Host "Next: python scripts/download_data.py"
Write-Host "Then: python scripts/run_forecast_demo.py"
```

- [ ] **Step 3: Make Linux script executable** (Linux/macOS only — skip on Windows)

```bash
chmod +x scripts/setup_cpu.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_cpu.sh scripts/setup_cpu.ps1
git commit -m "feat: add Phase 1 CPU setup scripts (Linux + Windows)"
```

---

### Task 3: Create `scripts/download_data.py`

**Files:**
- Create: `scripts/download_data.py`

- [ ] **Step 1: Write data download script**

```python
"""
Download full 51-ticker universe data via yfinance.
Downloads all tickers (shared between Phase 1 and Phase 2).
Run once — subsequent runs skip already-cached tickers.
"""
from kth.data.loader import download_universe
from kth.data.universe import get_all_tickers

tickers = get_all_tickers()
print(f"Downloading {len(tickers)} tickers (10 years each)...")
report = download_universe(tickers, period="10y", cache_dir="./data/raw")
print("\nDownload complete.")
print(report[["ticker", "rows", "start", "end"]].to_string(index=False))
```

- [ ] **Step 2: Run**

Run: `python scripts/download_data.py`
Expected: downloads 51 parquet files to `./data/raw/` (first run ~3 min; subsequent ~3s)

- [ ] **Step 3: Commit**

```bash
git add scripts/download_data.py
git commit -m "feat: add data download script"
```

---

### Task 4: Create `scripts/run_forecast_demo.py`

**Files:**
- Create: `scripts/run_forecast_demo.py`

- [ ] **Step 1: Write forecast demo script**

```python
"""
Phase 1 end-to-end demo: forecast 5 tickers on CPU → build report → save HTML.

5 representative tickers across asset classes:
  AAPL    — US large-cap equity
  PTT.BK  — Thai blue-chip equity
  GLD     — commodity (gold ETF)
  BTC-USD — crypto
  ^SET.BK — Thai index benchmark
"""
import pandas as pd
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached
from kth.utils.report import build_report_table, render_html

TICKERS = ["AAPL", "PTT.BK", "GLD", "BTC-USD", "^SET.BK"]

def main():
    # 1. Load model (CPU) — device="cpu" required: default is "auto" which uses CUDA if present
    print("Loading Kronos-small on CPU...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cpu")
    print(f"  Model: {k.model_name}")
    print(f"  Device: {k.device}")

    # 2. Forecast batch
    print(f"\nForecasting {len(TICKERS)} tickers (n_samples=50, 5d+20d)...")
    forecasts = k.forecast_batch(TICKERS, pred_lens=[5, 20], n_samples=50)
    print(f"  Done. {len(forecasts)} tickers returned.")

    # 3. Build last_closes from cached data
    last_closes = {}
    for t in TICKERS:
        try:
            df = load_cached(t)
            last_closes[t] = float(df["close"].iloc[-1])
            print(f"  {t:10s} close: {last_closes[t]:.2f}")
        except FileNotFoundError:
            print(f"  {t:10s} WARNING: no cache — run scripts/download_data.py first")

    # 4. Build report tables
    adj_table, raw_table = build_report_table(
        forecasts, last_closes, long_threshold=0.01
    )

    print(f"\n=== Confidence-Adjusted Report ===")
    print(adj_table[["Ticker", "Class", "1d p50", "5d p50", "20d p50", "Signal", "Score"]].to_string(index=False))

    # 5. Save HTML report
    report_path = Path("./reports") / f"{pd.Timestamp.now().strftime('%Y-%m-%d')}_demo.html"
    html_path = render_html(
        (adj_table, raw_table),
        str(report_path),
        k.model_name,
        pd.Timestamp.now(),
    )
    print(f"\nHTML report saved to: {html_path}")

    # 6. Quick validation
    assert len(adj_table) == len(TICKERS), f"Expected {len(TICKERS)} rows"
    assert not (adj_table["1d p50"] == 0).all(), "1d p50 should not be all zero!"
    print("\n=== Demo PASSED ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

Run: `python scripts/run_forecast_demo.py`
Expected: prints per-ticker forecast table, saves `./reports/YYYY-MM-DD_demo.html`

- [ ] **Step 3: Commit**

```bash
git add scripts/run_forecast_demo.py
git commit -m "feat: add Phase 1 CPU forecast demo script"
```

---

### Task 5: Run full end-to-end verification

- [ ] **Step 1: Run from scratch to confirm clean path**

In a fresh terminal (or after `pip install -e .`):
```
python scripts/download_data.py
python scripts/run_forecast_demo.py
python verify_model_layer.py
```

Expected: all three commands succeed (download completes, 5 forecasts, 9 tests pass).

- [ ] **Step 2: Open HTML report**

Open `./reports/YYYY-MM-DD_demo.html` in browser. Verify:
- Title shows correct date
- Two tables: Confidence-Adjusted + Raw Forecasts
- Confidence flags shown (likely band-width fallback since no backtest)
- 5 ticker rows with non-zero 1d/5d/20d values

---

### Self-Review

- [x] Spec coverage: All Phase 1 steps covered — install, download, forecast, report, verify
- [x] Placeholder scan: No TBDs. All paths, tickers, and thresholds are explicit.
- [x] Type consistency: `last_closes` passed as dict, `render_html` receives tuple of tables.
- [x] Scope: CPU-only, 5 tickers, ~10 min. No GPU code, no 51-ticker loop.
- [x] Device: `device="cpu"` explicit — `KronosTH` default is `"auto"` (auto-detects CUDA), not CPU.
- [x] Cross-platform: Both `.sh` (Linux/macOS/WSL2) and `.ps1` (Windows) setup scripts provided.
- [x] HuggingFace model ID: `"NeoQuasar/Kronos-small"` flagged for verification before running.
