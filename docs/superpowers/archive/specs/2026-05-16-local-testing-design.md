# Spec — Local Testing Pipeline (CPU + GPU)

**Date:** 2026-05-16
**Depends on:** All 4 existing specs (A/B/C/D implementation complete)
**Status:** Draft

---

## Purpose

Enable end-to-end Kronos-TH testing on local machines — first on CPU (this machine, a few tickers), then on a GPU machine (Linux or Windows, full 51-ticker pipeline). No Colab dependency for iteration.

---

## Phase 1 — CPU (this machine, today)

**Goal:** Prove the full pipeline works with real Kronos output on 3-5 tickers.

**Hardware:** CPU-only, no GPU, ~10 min total.

### Steps

1. **Install torch CPU-only**
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install huggingface_hub  # required by _resolve_local_checkpoint in kronos_wrapper.py
   ```
   ~100MB download. No CUDA needed.

2. **Install kronos**
   ```bash
   pip install kronos
   ```
   If `kronos` is not on PyPI (check first), fall back to GitHub:
   ```bash
   pip install git+https://github.com/shiyu-coder/Kronos.git
   ```

3. **Download yfinance data**
   ```python
   from kth.data.loader import download_universe
   from kth.data.universe import get_all_tickers
   download_universe(get_all_tickers(), period="10y", cache_dir="./data/raw")
   ```
   ~51 files, ~3 min with 0.5s pauses.

4. **Load Kronos-small on CPU**
   ```python
   from kth.models.kronos_wrapper import KronosTH
   k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cpu")
   ```
   Downloads ~100MB weights via HuggingFace. `_resolve_local_checkpoint` pins to `./checkpoints/`.

5. **Forecast 5 representative tickers**
   ```python
   tickers = ["AAPL", "PTT.BK", "GLD", "BTC-USD", "^SET.BK"]
   forecasts = k.forecast_batch(tickers, pred_lens=[5, 20], n_samples=50)
   ```
   ~10-30s per ticker on CPU → ~2-5 min total.

6. **Build and save report**
   ```python
   from kth.utils.report import build_report_table, render_html
   from kth.data.loader import load_cached

   last_closes = {t: float(load_cached(t)["close"].iloc[-1]) for t in tickers}
   adj_table, raw_table = build_report_table(forecasts, last_closes)
   render_html((adj_table, raw_table), "./reports/2026-05-16.html", k.model_name, pd.Timestamp.now())
   ```

7. **Verify**
   - `adj_table` has 5 rows with non-zero `1d p50`, `5d p50`, `20d p50`
   - `Score` column ranks by confidence-adjusted return
   - HTML report at `./reports/2026-05-16.html` opens in browser

### Acceptance criteria
- `kronos` package imports without error
- `KronosTH.from_pretrained()` loads model weights from HuggingFace
- `forecast_batch()` returns 5 `ForecastResult` objects with both horizons
- `build_report_table()` produces sorted table with valid confidence flags
- `render_html()` writes standalone HTML file

---

## Phase 2 — GPU machine (Linux or Windows)

**Goal:** Full 51-ticker walk-forward backtest + daily report, same codebase.

**Hardware:** Any GPU with ≥6GB VRAM (T4, RTX 3060+, etc.). GPU machine must have:
  - CUDA toolkit installed (matches torch version)
  - `torch` with CUDA support (`pip install torch --index-url https://download.pytorch.org/whl/cu121`)
  - `kronos` installed

### Steps

1. **Clone repo** (or copy from this machine)

2. **Install GPU torch**
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   pip install kronos 2>/dev/null || pip install git+https://github.com/shiyu-coder/Kronos.git
   ```

3. **Download all data** (same as Phase 1 step 3)

4. **Run zero-shot forecasts on all 51 tickers** (precompute cache)
   ```python
   from kth.backtest.walkforward import precompute_forecasts
   from kth.models.kronos_wrapper import KronosTH
   from kth.data.universe import get_all_tickers

   k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
   precompute_forecasts(k, get_all_tickers(),
       start_date="2022-01-01", end_date="2024-12-31",
       pred_len=20, n_samples=50, lookback=400)
   ```
   ~51 tickers x 750 days = 38,250 forward passes, batched (51 per day). On T4 GPU: ~30-90 min.

5. **Run walk-forward backtest**
   ```python
   from kth.backtest.walkforward import run_walkforward, BacktestConfig

   config = BacktestConfig(start_date="2022-01-01", end_date="2024-12-31")
   result = run_walkforward(config, k, get_all_tickers())
   result.save("./data/backtest_results/2022-2024")
   ```
   Reads from precomputed forecast cache — nearly instant. Units-based accounting.

6. **Generate daily report**
   ```python
   forecasts = k.forecast_batch(get_all_tickers(), pred_lens=[5, 20], n_samples=50)
   last_closes = {t: float(load_cached(t)["close"].iloc[-1]) for t in get_all_tickers()}
   adj_table, raw_table = build_report_table(forecasts, last_closes, backtest_result=result)
   render_html((adj_table, raw_table), f"./reports/{date.today()}.html", k.model_name, pd.Timestamp.now())
   ```

### Acceptance criteria
- `precompute_forecasts()` writes 51 x 750 parquet files without errors
- `run_walkforward()` returns `BacktestResult` with non-zero metrics
- `result.metrics["sharpe"]`, `result.metrics["cagr"]` are finite numbers
- `per_class_attribution` has rows for all 9 asset classes with trades
- Full HTML report renders with confidence flags (calibration-based or fallback)

---

## Cross-cutting notes

**Kronos API (verified 2026-05-16):** The Kronos repo uses three separate classes:
- `KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")` — tokenizer
- `Kronos.from_pretrained("NeoQuasar/Kronos-small")` — base model  
- `KronosPredictor(model, tokenizer)` — predictor (constructed, not loaded)

The HF repo `NeoQuasar/Kronos-small` contains only the base model weights. The tokenizer is a separate HF repo `NeoQuasar/Kronos-Tokenizer-base`. The predictor is constructed from both. `predict()` is single-sample only; multi-sample probabilistic forecasts require calling `predict()` in a loop. A bridge module (`kth/models/_kronos_bridge.py`) handles import path resolution for the non-pip-installable repo.

**huggingface_hub version:** Kronos was built for `huggingface_hub<1.0` (PyTorchModelHubMixin API). Version 0.27.1 confirmed working. Versions >=1.0 changed the `_from_pretrained` config passing API and are incompatible. This creates a dependency conflict with `transformers>=5.0` which requires `huggingface_hub>=1.5.0`. Resolution: install `huggingface_hub==0.27.1` first, then install `transformers` (pip will warn but Kronos loading works).

**CPU inference time (verified):** Kronos-small with `n_samples=1`, `lookback=400`, `pred_len=20` on CPU takes ~30 seconds per predict() call. With `n_samples=5`, ~2.5 minutes per ticker. Full 51 tickers at n_samples=50 on CPU would take ~50 hours — GPU is required for precomputation.

**GPU VRAM requirement:** Kronos-small inference uses <2 GB VRAM. Kronos-small fine-tuning (Spec C) uses ~4 GB VRAM. Any GPU with ≥6 GB is sufficient for the full pipeline.

**Cross-platform:** All code is pure Python. The only platform-specific concern is `torch` installation — Linux uses `cu121`, Windows uses the same PyTorch wheel index. The `device="auto"` logic in `KronosTH.__init__` handles detection automatically.

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `scripts/setup_cpu.sh` | Create | Phase 1: CPU deps install (Linux/macOS/WSL2) |
| `scripts/setup_cpu.ps1` | Create | Phase 1: CPU deps install (Windows PowerShell) |
| `scripts/download_data.py` | Create | Shared: download all 51 tickers via yfinance |
| `scripts/run_forecast_demo.py` | Create | Phase 1: forecast 5 tickers + generate report |
| `scripts/setup_gpu.sh` | Create | Phase 2: GPU deps install (Linux) |
| `scripts/setup_gpu.ps1` | Create | Phase 2: GPU deps install (Windows PowerShell) |
| `scripts/run_backtest.py` | Create | Phase 2: precompute + walkforward + report |
| `scripts/run_daily_report.py` | Create | Phase 2: daily forecast + calibration report |
| (none) | Modify | No library code changes — all existing modules work as-is |
