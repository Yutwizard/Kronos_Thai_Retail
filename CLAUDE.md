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
Layer 5: Dashboard / Report     scripts/dashboard.py                    ✅ built (Flask, paper trading)
                                kth/trading/portfolio.py                ✅ built
                                kth/trading/trade_gen.py                ✅ built
                                scripts/cron_pipeline.sh                ✅ built
                                notebooks/05_decision_report.ipynb      ✅ built (Colab version)
Layer 4: Backtest               kth/backtest/walkforward.py             ✅ built
                                kth/backtest/strategy.py                ✅ built
                                kth/backtest/metrics.py                 ✅ built
                                scripts/compare_finetune.py             ✅ built
                                scripts/eval_holdout.py                 ✅ built
Layer 3: Kronos model           kth/models/kronos_wrapper.py            ✅ built
                                kth/models/finetune.py                  ✅ built
                                kth/models/_kronos_bridge.py            ✅ built
                                notebooks/04_finetune_per_market.ipynb  ✅ built (Colab)
                                scripts/train_per_market.py             ✅ built (local)
Layer 2: Feature pipeline       kth/data/loader.py                      ✅ done
Layer 1: Universe definition    kth/data/universe.py                    ✅ done
```

**Active work:** 4-phase QFM enhancement plan in `docs/superpowers/plans/2026-06-03-phase*.md` — start with Phase 1 (15 min bug fixes).

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
- **Phase 2 addition (planned):** `SECTOR` dict + `get_sector()` — all 50 thai_equity tickers mapped to 10 SET sectors for the sector concentration guard (max 2 positions per sector).

### yfinance download behavior
- `download_universe()` pauses 0.5s between tickers and retries with exponential backoff (2s / 4s / 8s, 3 attempts).
- Individual ticker failures return `None` and are logged — they don't abort the batch.

## Planned enhancements (4-phase QFM plan — 2026-06-03)

All core modules are ✅ built. The active work queue is a 4-phase enhancement plan. See `docs/superpowers/plans/2026-06-03-phase*.md` for full task lists.

| Phase | Module(s) | What gets added | Est. |
|---|---|---|---|
| **1 (P0)** | `trade_gen.py` | Fix hardcoded `0.00268` friction; dedup `INITIAL_CAPITAL` | 15 min |
| **2 (P1)** | `universe.py`, `trade_gen.py`, `portfolio.py`, `dashboard.py` | SECTOR dict, sector guard (max 2/sector), atomic JSON write, forecast recovery | ~2 hrs |
| **3 (P2)** | `metrics.py`, `trade_gen.py`, `portfolio.py`, `cron_pipeline.sh` | IR, batting avg, calibration check, T+2 warning, model version log, LINE Notify | ~4 hrs |
| **4 (P3/P4)** | `download_data.py`, `dashboard.py`, `metrics.py`, `backtest-methodology.html` | Price sanity, POST validation, drawdown velocity, bootstrap p-value, survivorship bias | ~6 hrs |

Target model sizes: **Kronos-small** (24.7M params) — confirmed in production. Kronos-base (102.3M) requires T4 16GB.

## Known quirks

- Real yfinance access is only possible on Colab/Kaggle/local machines — `verify_data_layer.py` uses synthetic data specifically because yfinance is blocked in most sandboxes.
- For real data verification, run `notebooks/01_data_layer.ipynb` on Colab, which downloads ~10 years of daily OHLCV for all 100 tickers and caches to `./data/raw/*.parquet`.

## Hard scope limits

Do **not** add (unless explicitly asked): live order execution, intraday data, portfolio optimization (Markowitz/factor), news sentiment, `pytest`/`tox` test frameworks, or CI config — all explicitly out of scope per `PROJECT_STRUCTURE.md §12`. (`Makefile` and `docker-compose.yml` are already present for Docker workflows — do not remove them.)

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
5. [docs/superpowers/specs/](docs/superpowers/specs/) — approved design specs (Layers 3–5). Completed/archived spec moved to [docs/superpowers/archive/](docs/superpowers/archive/)
6. [kth/data/loader.py](kth/data/loader.py) — schema conversion and caching implementation
7. [kth/data/universe.py](kth/data/universe.py) — 100-ticker universe and `FRICTION` dict
