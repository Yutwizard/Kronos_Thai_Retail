# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Kronos-TH is a **research-first, Colab-based** forecasting tool for Thai retail investors. It wraps the [Kronos](https://github.com/shiyu-coder/Kronos) financial foundation model to produce probabilistic daily-bar forecasts across the assets a Thai retail investor can actually buy (SET stocks, US stocks/ETFs, crypto, gold, FX).

**Primary runtime is Google Colab (T4 GPU).** Local scripts exist only for offline data layer verification — yfinance is often blocked in sandboxes.

## Commands

### Local (no Docker)
```bash
pip install -r requirements.txt          # data layer only
pip install -r requirements-ml.txt      # ML stack (torch etc.)
pip install -e .                         # make kth importable as a package
python verify_data_layer.py             # offline synthetic tests
```

### Docker (recommended — consistent across Windows/Linux/macOS)
```bash
make build          # build CPU image
make verify         # run offline tests inside container
make notebook       # JupyterLab at http://localhost:8888 (CPU, all platforms)
make download       # pull 100-ticker universe to ./data/raw/ (needs network)

make build-gpu      # build GPU image (Windows WSL2 / Linux only)
make notebook-gpu   # JupyterLab with CUDA (Windows WSL2 / Linux only)
```

Or directly via Docker Compose:
```bash
docker compose run --rm notebook python verify_data_layer.py
docker compose up notebook
docker compose up notebook-gpu   # GPU: requires NVIDIA Container Toolkit
```

**GPU support by platform:**
| Platform | CPU service | GPU service |
|---|---|---|
| Windows (WSL2 + NVIDIA drivers) | ✅ | ✅ |
| Linux (NVIDIA Container Toolkit) | ✅ | ✅ |
| macOS | ✅ | ❌ — use Colab for GPU work |

There is no test framework, lint config, CI, or build step. `verify_data_layer.py` is the only test runner and it uses synthetic data because yfinance is blocked in most sandboxes.

## Architecture

Five-layer pipeline (bottom-up build order):

```
Layer 5: Decision report        notebooks/05_decision_report.ipynb     ✅ built
Layer 4: Backtest               kth/backtest/walkforward.py             ✅ built
                                scripts/compare_finetune.py             ✅ built
                                scripts/eval_holdout.py                 ✅ built
Layer 3: Kronos model           kth/models/kronos_wrapper.py            ✅ built
                                notebooks/04_finetune_per_market.ipynb  ✅ built (Colab)
                                scripts/train_per_market.py             ✅ built (local)
Layer 2: Feature pipeline       kth/data/loader.py                      ✅ done
Layer 1: Universe definition    kth/data/universe.py                    ✅ done
```

**Library code** lives in `kth/` (tested, reused across notebooks). **Research narrative** lives in `notebooks/` (exploratory, with plots).

## Key conventions

### Kronos schema
`to_kronos_format()` in [kth/data/loader.py](kth/data/loader.py) converts yfinance output to this exact schema:

```
columns: timestamps, open, high, low, close, volume, amount
```

- `amount = close × volume` — computed locally because Yahoo doesn't expose turnover; this is what the upstream Kronos repo does too.
- yfinance returns `Open/High/Low/Close/Volume` with a `DatetimeIndex`; the loader lowercases and renames them.

### Caching
- One `.parquet` file per ticker in `./data/raw/` — never a merged file (date ranges differ across markets).
- Ticker sanitization for filenames: `^` → `_`, `=` → `_` (e.g. `^SET.BK` → `_SET.BK.parquet`, `THB=X` → `THB_X.parquet`).
- `auto_adjust=True` on yfinance so splits/dividends are baked in.
- Gaps are **preserved**, not forward-filled — crypto trades 7 days/week, equities don't.

### Universe
- Hardcoded 100 tickers across 9 asset classes in [kth/data/universe.py](kth/data/universe.py) — not a CSV. Adding a ticker is an intentional code change for version control.
- `FRICTION` costs are per-class, not per-ticker. `fx_macro` class has zero friction (features only, not investable).
- Key helpers: `get_all_tickers()`, `get_ticker_class(ticker)`, `get_display_name(ticker)`.

### yfinance download behavior
- `download_universe()` pauses 0.5s between tickers and retries with exponential backoff (2s / 4s / 8s, 3 attempts).
- Individual ticker failures return `None` and are logged — they don't abort the batch.

## Planned modules (not yet built)

| Module | Purpose |
|---|---|
| `kth/models/kronos_wrapper.py` | `KronosTH` class — loads Kronos-small/base, returns `ForecastResult` with P5/P50/P95 bands at 5d and 20d horizons; model weights pinned to local `./checkpoints/` after first HuggingFace download |
| `kth/models/finetune.py` | `prepare_dataset`, `finetune_tokenizer` (stub — Kronos has no `fit()`), `finetune_predictor` (stub), `evaluate_model` — actual training uses `scripts/train_per_market.py` with custom training loop (tokenizer.encode → model forward → head.compute_loss → backprop) |
| `scripts/train_per_market.py` | SGDR (CosineAnnealingWarmRestarts, 2 cycles), `fold_step_months=21` for ≥420-row val/test windows, early stopping patience=3, saves model_config.json + model.safetensors per fold |
| `scripts/eval_holdout.py` | Loads fine-tuned checkpoints via `KronosTH._predictor` swap, evaluates direction accuracy on 2025 holdout per model, per fold |
| `kth/backtest/walkforward.py` | `run_walkforward()` + `precompute_forecasts()` — forecasts cached per (date, ticker) to avoid re-running 38k forward passes; hysteresis buffer prevents whipsaw trades |
| `kth/backtest/strategy.py` | `compute_signals()`, `select_positions()`, `compute_weights()` — pure stateless signal functions |
| `kth/backtest/metrics.py` | Full professional metric set: Sharpe/Sortino/Calmar/Omega, historical VaR/CVaR, Ulcer Index, hit-rate, profit factor, t-stat, per-class attribution; gross and net side-by-side |
| `kth/utils/plot.py` | `plot_forecast_band`, `plot_equity_curve`, `plot_attribution`, `plot_drawdown` |
| `kth/utils/report.py` | `build_report_table` (dual sort: confidence-adjusted + raw), `render_markdown`, `render_html` |
| `scripts/build_usermanual_html.py` | Generates `docs/user-manual.html` with 7 embedded Matplotlib charts |
| `scripts/build_operations_html.py` | Generates `docs/operations-manual.html` |
| `scripts/build_walkthrough_html.py` | Generates `docs/monthly-walkthrough.html` with timeline visualization |

Target model sizes: **Kronos-small** (24.7M params) for iteration, **Kronos-base** (102.3M) for final fine-tune — both fit on a T4 16GB GPU.

## Known quirks

- Real yfinance access is only possible on Colab/Kaggle/local machines — `verify_data_layer.py` uses synthetic data specifically because yfinance is blocked in most sandboxes.
- For real data verification, run `notebooks/01_data_layer.ipynb` on Colab, which downloads ~10 years of daily OHLCV for all 100 tickers and caches to `./data/raw/*.parquet`.

## Hard scope limits

Do **not** add (unless explicitly asked): live order execution, intraday data, web UI, portfolio optimization (Markowitz/factor), news sentiment, `pytest`/`tox` test frameworks, or CI config — all explicitly out of scope per `PROJECT_STRUCTURE.md §12`. (`Makefile` and `docker-compose.yml` are already present for Docker workflows — do not remove them.)

## Superpowers workflow

**Invoke relevant skills BEFORE any response or action.** If there is even a 1% chance a skill applies, invoke the `Skill` tool to load it. Follow the skill's instructions exactly.

Priority order: (1) user's explicit instructions, (2) superpowers skills, (3) default system prompt.

**Skill priority:** process skills (brainstorming, systematic-debugging) before implementation skills.

**Red flags** — these thoughts mean STOP and check for skills first:
- "This is just a simple question"
- "Let me explore the codebase first"
- "This doesn't need a formal skill"

## Reading order for deeper context

1. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — authoritative design doc with module specs, friction model, evaluation methodology, and open design questions
2. [README.md](README.md) — project overview, honest caveats, quick start
3. [docs/user-manual.html](docs/user-manual.html) — styled HTML manual with 7 charts, methodology, and usage guide
4. [docs/operations-manual.html](docs/operations-manual.html) — daily/weekly/monthly step-by-step procedures
5. [docs/monthly-walkthrough.html](docs/monthly-walkthrough.html) — 21-day simulated month with real trades
5. [docs/superpowers/specs/](docs/superpowers/specs/) — approved design specs for Layers 3–5 (A: inference wrapper, B: backtest, C: fine-tune, D: report)
6. [kth/data/loader.py](kth/data/loader.py) — schema conversion and caching implementation
7. [kth/data/universe.py](kth/data/universe.py) — 100-ticker universe and `FRICTION` dict
