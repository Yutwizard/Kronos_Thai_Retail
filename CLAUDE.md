# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Kronos-TH is a **research-first, Kaggle-scheduled** forecasting tool for Thai retail investors. It wraps the [Kronos](https://github.com/shiyu-coder/Kronos) financial foundation model to produce probabilistic daily-bar forecasts for SET-listed Thai equities and DR (Depositary Receipts) of major foreign stocks tradable on the SET in Thai baht. (Scope narrowed 2026-07-16 from a broader multi-asset universe — see `archive/other-asset-classes/`.)

**Status (2026-09-24): treat this as an experimental forecasting tool with no proven edge, whose 2024 forecasts were worse than a naive baseline (ticket `18`: bands overconfident, P50 worse than no-change).** The historical backtests were look-ahead-contaminated; point-in-time evidence (2024 backtest, signal IC, entry/exit/stop variants) shows no edge over equal-weight buy-and-hold. See `.scratch/future-plan/00`, `06`. Three literature-derived long-only candidates (monthly LightGBM ranker, VP-MACD index overlay, 200-day SMA filter) were then pre-registered and tested on SET 2020-2026 (`08`, `09`, 2026-09-21): none passed the discovery bar, and a follow-up drawdown check of the 200-day filter on the untouched 2018-2019 window (`10`) also failed the Sharpe test, so don't re-test any of them without a new pre-registration. The live paper track has a pre-committed review rule (`11`, approved 2026-09-21; addenda A/B 2026-09-24): futility check 2026-12-30, edge decision 2027-06-30, 24-month continuation 2028-06-30; don't change the rule after seeing results. Forward shadow books for momentum and SMA200 (`20`) start 2026-11-02 with their own review dates (2027-05-03, 2027-11-01, 2028-11-01). Do not present it as beating the market.

**Primary runtime is Kaggle Notebooks (T4 GPU, scheduled daily).** Colab is the backup runtime. Local scripts exist for offline verification — yfinance is often blocked in sandboxes. Code review fixes applied 2026-06-21 (PSR, equity curve alignment, open_trades blending); stored backtest numbers are stale pending GPU re-run (see `data/backtest_results/MANIFEST.md`).

## Commands

### Local (no Docker)
```bash
pip install -r requirements.txt          # data layer only
pip install -r requirements-ml.txt      # ML stack (torch etc.)
pip install -e .                         # make kth AND kth_dr importable — re-run after every pull that touches either package, editable installs don't auto-pick-up new top-level packages
python verify_data_layer.py             # data layer: 5 tests
python verify_fixes.py                  # review fixes: stats + pipeline + universe (25 tests)
python verify_kaggle_runtime.py         # Kaggle pipeline: auth + orchestration (20 tests)
python verify_dr.py                     # DR integration: plugin hook, mapping, trade-gen wiring (42 tests)
python verify_clean_data.py            # clean-data loader: stub dates, break scaling, read-only (synthetic data)
python run_pipeline.py --dry-run        # full pipeline smoke test, offline
python scripts/check_data_sanity.py     # post-download sanity sweep over data/raw/ — run after every real download (see incident below)
python scripts/snapshot_live_data.py    # freeze raw/positions/live forecasts to ~/backups/kronos-th-snapshots (auto after Run Pipeline); --verify DIR, --selftest
python scripts/shadow_books.py --selftest  # ticket-20 forward shadow books (momentum, SMA200); --record runs as pipeline STEP3b; --review is date-guarded
```

### Docker (recommended — consistent across Windows/Linux/macOS)
```bash
make build          # build CPU image
make verify         # run offline tests inside container
make notebook       # JupyterLab at http://localhost:8888 (CPU, all platforms)
make download       # pull 52-ticker universe to ./data/raw/ (needs network)

make build-gpu      # build GPU image (Windows WSL2 / Linux only)
make notebook-gpu   # JupyterLab with CUDA (Windows WSL2 / Linux only)
```

Or directly via Docker Compose:
```bash
docker compose run --rm notebook python verify_data_layer.py
docker compose up notebook
docker compose up notebook-gpu   # GPU: requires NVIDIA Container Toolkit
```

**GPU support:** Windows (WSL2 + NVIDIA drivers) and Linux (NVIDIA Container Toolkit) support both CPU and GPU services. macOS is CPU-only — use Colab for GPU work.

There is no test framework, lint config, CI, or build step. `verify_data_layer.py` is the only test runner and it uses synthetic data because yfinance is blocked in most sandboxes.

## Architecture

Five-layer pipeline (bottom-up). All layers built; `kth/` holds tested library code reused across notebooks, `notebooks/` holds the exploratory research narrative.

```
Layer 5  Dashboard / Report   google_suite/ (Colab+Sheets+Apps Script, zero-cost)
                               scripts/dashboard.py + start_dashboard.sh (Flask, local GPU)
                               kth/trading/{portfolio,trade_gen,sheets,sheets_config}.py
                               kth/pipeline/daily.py (Kaggle scheduled orchestration)
                               kth/io/kaggle_runtime.py (service-account auth, injectable)
                               kaggle/build_kaggle_notebook.py (thin wrapper builder)
Layer 4  Backtest             kth/backtest/{walkforward,strategy,metrics}.py
                               scripts/{compare_finetune,eval_holdout}.py
Layer 3  Kronos model         kth/models/{kronos_wrapper,finetune,_kronos_bridge}.py
                               scripts/train_per_market.py
Layer 2  Feature pipeline     kth/data/loader.py
                               kth/testing/synthetic.py (offline test data)
Layer 1  Universe definition  kth/data/universe.py
```

**Layer 5 — two interchangeable dashboards** (choose by environment):
- **Kaggle scheduled pipeline** — primary daily runtime. GPU + Internet + Secrets. See `kaggle/` (notebook generated by `build_kaggle_notebook.py`). Idempotent by design: date-keyed upserts, trade-edit-before-fills ordering, failure-path status + notifier.
- **Google Suite** — Colab notebook + Google Sheets data store + Apps Script web app. Zero-cost, no local GPU. `google_suite/` (notebook generated by `build_notebook.py`; `apps_script/Code.gs` backend; `apps_script/Index.html` 5-tab SPA). JSON-bridge pattern: Sheets → Drive JSON → `kth` functions → Drive JSON → Sheets; `os.chdir(KTH_REPO)` in Cell 1 makes `Path("data/...")` resolve against Drive; Cell 9 (portfolio state) must run before Cell 10 (ticket).
- **Flask** — `scripts/dashboard.py`, requires local GPU. Launch with `./scripts/start_dashboard.sh` (idempotent: venv, deps, server on port 5555 — data download and forecast generation are NOT run automatically on startup; trigger them via the dashboard's "Run Pipeline" button or `venv/bin/python scripts/dashboard.py --generate`). Env: `KRONOS_PORT`, `INITIAL_CAPITAL`, `KRONOS_MODE`.

Run the pipeline in the **late evening, ~23:45 BKK** (not right after SET's 16:30 close) so tomorrow's forecast uses today's close for every ticker — the universe now includes DR underlyings on European exchanges (Hermès, L'Oréal, LVMH, Sanofi, Ferrari, Novo Nordisk) that close ~22:30–23:30 BKK, later than SET/HKEX/TSE/SGX. A run right after SET's close would silently use yesterday's European prices for those 6. See `scripts/cron_pipeline.sh`'s header comment for the full reasoning (this applies to local/cron runs; Kaggle's own schedule is configured separately via its notebook-scheduling UI, not this repo).

## Key conventions

### Kronos schema
`to_kronos_format()` in [kth/data/loader.py](kth/data/loader.py) converts yfinance output to exactly:

```
columns: timestamps, open, high, low, close, volume, amount
```

- `amount = close × volume` — computed locally because Yahoo doesn't expose turnover; matches upstream Kronos.
- yfinance returns `Open/High/Low/Close/Volume` with a `DatetimeIndex`; the loader lowercases and renames.

### Caching
- One `.parquet` file per ticker in `./data/raw/` — never a merged file (date ranges differ across markets).
- Filename sanitization: `^` → `_`, `=` → `_` (e.g. `^SET.BK` → `_SET.BK.parquet`, `THB=X` → `THB_X.parquet`).
- `auto_adjust=True` so splits/dividends are baked in.
- Gaps are **preserved**, not forward-filled — this matters for any asset class that doesn't trade on a 5-day business calendar (a holdover design decision from when the universe included crypto; no current SET/DR ticker actually needs it, but the loader stays calendar-agnostic).

### Universe
- Hardcoded 52 tickers across 2 asset classes (`thai_equity`, `thai_index`) in [kth/data/universe.py](kth/data/universe.py) — not a CSV. Adding a ticker is an intentional code change for version control. Plus a separate DR universe via the `kth_dr/` plugin (`register_asset_class()`), never a hardcoded `UNIVERSE` key. Scope narrowed 2026-07-16 from 100 tickers/9 classes — see `archive/other-asset-classes/`.
- `FRICTION` costs are per-class, not per-ticker — currently `thai_equity`/`thai_index` share one rate; DR inherits it too via `kth_dr`'s `register_asset_class()` call.
- `SECTOR` dict + `get_sector()` map all 51 thai_equity tickers (incl. `CPNREIT.BK`, folded into the existing `Property` bucket) to 10 SET sectors for the sector concentration guard (max 2 positions/sector).
- Key helpers: `get_all_tickers()`, `get_ticker_class(ticker)`, `get_display_name(ticker)`, `get_sector(ticker)`.

### yfinance download behavior
- `download_universe()` pauses 0.5s between tickers and retries with exponential backoff (2s / 4s / 8s, 3 attempts).
- Individual ticker failures return `None` and are logged — they don't abort the batch.

## Research decisions that constrain code (do not relitigate without GPU re-run)

> **2026-09-21:** the decisions below were derived from backtests on a look-ahead forecast cache (see the 2026-09-18 finding under Known quirks) and are unverified. Treat them as conservative defaults, not proven findings; the "do not relitigate" wording applies only to what a point-in-time re-run would confirm.

- **Position sizing: equal-weight only.** `inv_vol` was backtested and lost badly (it over-allocates to low-vol stocks where the Kronos signal is weakest). Do not switch to inv_vol.
- **Exit hysteresis: max-holding-days cap rejected** — `apply_hysteresis()`/`BacktestConfig` support an optional `max_holding_days`/`cooldown_days` (disabled by default; do not enable in production). Backtested thai_equity 2023-2026 (n=50, see `.scratch/optimize-entry-exit/`); a `max_holding_days=60`/`cooldown_days=5` config was initially adopted off annual point-estimates (ties-or-beats baseline in 3 of 4 years by CAGR/Sharpe/PSR), but a follow-up paired block-bootstrap on the daily active-return series (cap60 vs baseline) reversed that: 2024 (the flagship year) shows a statistically clean *loss* (95% CI entirely negative), 2023's apparent win is only marginal (CI barely excludes zero), and pooled across all four years the effect is statistically indistinguishable from noise. Do not relitigate without a fresh sweep — and if revisited, test paired significance on daily active returns from the start, not just annual point-estimates.
- **Fine-tuning: thai_equity stays zero-shot** — fine-tuning did not beat zero-shot in backtest. (crypto and us_equity fine-tuning results are archived alongside their backtests, `archive/other-asset-classes/` — those classes are no longer in scope at all, not merely "staying zero-shot".)
- **Alpha is NOT regime-conditional — claim retracted 2026-07-29.** Previously claimed the strategy crushes flat/down SET regimes but underperforms in bull markets, built on 2023 as the bull-market counter-example — but a benchmark bug (fixed 2026-07-29, see `data/backtest_results/MANIFEST.md`) had made 2023 look like a +12.8% EW bull year when it was actually down −5.7% (SET fell ~15% that year). A daily-level regime split (trailing 60-day SET return, paired block bootstrap, 922 trading days across 2023-2026, see `.scratch/regime-conditional-alpha/`) found active return significantly positive in *both* bull-days (+34.8% ann.) and bear-days (+33.4% ann.), statistically indistinguishable from each other (95% CI on the difference: [−34.3%, +37.5%]). Do not manually reduce allocation based on a perceived SET bull/bear regime — that operator guidance has been removed from the docs. Do not relitigate without a fresh regime-split sweep.
- **Bootstrap p-value distinction — do not confuse:**
  - `compute_bootstrap_pvalue()` → live dashboard `/api/risk` only, centered resampling, edge in live paper trading.
  - Historical backtest p-values → t-test in `compute_metrics()`, stored in `data/backtest_results/`, never changed.
- **Kronos pre-training cutoff ≈ Dec 2022 (inferred).** 2023-2026 OOS backtests are clean; the 2022 portion of older runs may be partially in-sample. Confirm via arXiv:2508.02739 §3 if it matters.
- Target model: **Kronos-small** (24.7M params) in production. Kronos-base (102.3M) requires T4 16GB.
- **GULF.BK** excluded from forecasts until ~Oct 2026 (only 281 rows, needs ≥400 for the Kronos lookback); auto-qualifies once history accumulates.
- **BANPU.BK** was excluded after the 2026-07-25 incident below (6 rows) but its history has since been re-downloaded — 2,381 rows as of 2026-09-18, well past the ≥400 Kronos lookback — so the lookback gate (`len(df) < lookback` in `kth/models/kronos_wrapper.py`, no ticker blocklist) no longer excludes it. Watch item: a 38-day gap in its recent data (2026-08-11 → 2026-09-18, possibly another SET halt) and the thinnest liquidity in the universe (~1.1M THB median daily value); not yet confirmed via a live forecast run.

## Known quirks

- Real yfinance access works only on Colab/Kaggle/local — `verify_data_layer.py` uses synthetic data because yfinance is blocked in most sandboxes.
- For real data, run `notebooks/01_data_layer.ipynb` on Colab (downloads ~10y daily OHLCV for all 52 universe tickers plus DR/underlying/FX tickers to `./data/raw/*.parquet`).
- **2026-07-16 incident:** `verify_data_layer.py`/`verify_model_layer.py` used to write their synthetic data straight into the real `./data/raw` cache, silently overwriting real prices with random-walk data on every test run (caught via an abnormal AP.BK price). Both now write to isolated `tempfile.mkdtemp()` dirs — safe to run anytime. Run `python scripts/check_data_sanity.py` after any real download to sanity-check the cache (flags missing files, the synthetic-data rowcount fingerprint, oversized single-day jumps, and staleness).
- **2026-07-25 incident:** Yahoo Finance started returning a thin, flat/zero-volume trading-halt stub for BANPU.BK (consistent with a SET suspension) regardless of the requested `period`, and `download_universe()` silently overwrote its cached 2433-row history with that 6-row stub — `check_data_sanity.py` didn't catch it either (no single-day jump, since the price never moved). `kth/data/loader.py`'s `download_universe()` now refuses to overwrite a cached ticker whose fresh download has under half its previously cached rows (once the cache already has ≥30 rows — see `ROWCOUNT_DROP_RATIO`/`MIN_PREV_ROWS_FOR_GUARD`), so this can't happen silently again. BANPU.BK's pre-incident history was unrecoverable locally at the time (`data/raw/*.parquet` is git-ignored, no backup), so it briefly had only 6 rows and was excluded by the lookback gate; a later re-download restored 2,381 rows (see the Research Decisions bullet above).
- **2026-09-18 finding — the historical forecast cache was not point-in-time:** `precompute_forecasts()` passed ticker names to `forecast_batch()`, which loads the full history, so every historical day's forecast was conditioned on the latest data (~2026-05-15) instead of data up to that day (41 of 47 sampled `data/forecast_cache` folders have `lookback_end=2026-05-15`; implied 20-day returns had a median of 33–46% in 2020–2023). Fixed 2026-09-19: `precompute_forecasts` now truncates at each day, and `run_walkforward` refuses any cached forecast whose `lookback_end` is after its date (`require_point_in_time_forecast`), so backtests can no longer run on the existing cache (left in place for comparison). **A point-in-time re-run of 2024 (2026-09-21) gave CAGR −26.2%, Sharpe −1.19, p=0.24, −17pp vs equal-weight (stored: +41.3%, 2.23, p=0.001), so the flagship result does not hold (but see ticket `12`, 2026-09-21: 77% of the 2024 model input windows contained stub rows, up to ~11% of rows by December; ticket `17` (CLOSED 2026-09-22): a 53-date Stage-1 sample found cleaning did NOT detectably change the signal (IC -0.109 to -0.114, paired-diff 95% CI [-0.024, +0.014]), so stub contamination is not the explanation and the 2024 loss stands as originally measured; the full-year rerun was not pursued); treat every number in `data/backtest_results/` — and the Research Decisions built on them — as invalid.** Other years were not re-run. The live daily pipeline (folders from 2026-06-29 on) is point-in-time and unaffected. Details and next steps: `.scratch/future-plan/00-forecast-cache-lookahead.md`.
- **2026-09-21 finding — Yahoo stub rows and unadjusted corporate actions in `data/raw/`:** on 57 dates (mostly 2024 from 2024-03-12) ≥25 of the 51 thai_equity tickers have a flat zero-volume stub row on real trading days (stale price carried forward; `check_data_sanity.py` now flags it, plus last-row zero volume, >10-day gaps and >15% breaks right after a stub). `TRUE.BK` has a +68.6% break on 2023-03-03 (DTAC merger, price frozen 2023-02-20..03-02) and `SCB.BK` starts at the 2022-04-27 SCB X share swap (1,074 rows). `^SET.BK` has a two-month gap after 2026-07-17 and a zero-volume stub on 2026-09-15; a fresh Yahoo request returns a single row, so it could not be repaired (`.scratch/future-plan/09` audit section). Analyses on this cache should read prices through `kth.data.clean.load_clean_closes` (drops stub dates, flags stub rows as not real, applies an explicit reviewed break table; read-only, `verify_clean_data.py`) before trusting daily-return statistics.
- **2026-09-23 finding — `data/raw/` is not a stable snapshot across calendar days:** `manifest.json`'s `written_at` and per-ticker row counts change between sessions (e.g. SCB.BK 1,074 -> 1,077 rows, PTT.BK 2,436 -> 2,435 rows, in the two days after ticket 09 ran). Confirmed cause: the dashboard's documented "Run Pipeline" action (`scripts/dashboard.py --generate`, triggered by the project owner via a long-running `--serve` process, independent of any analysis session) re-downloads the universe on demand -- not necessarily the scheduled `cron_pipeline.sh`. A byte-for-byte reimplementation of ticket 09's frozen LightGBM candidate reproduced the real script's output exactly (max diff 0.0) when both ran on the same in-memory snapshot, but could not reproduce ticket 09's own recorded number when rerun two days later -- the code and parameters were frozen, the data was not. Any exact-number comparison against a stored backtest result (tickets 06, 09, 10, 14, 17) should be treated as tied to the calendar day it was run, not as bit-reproducible later. Since 2026-09-23 every Run Pipeline also writes a read-only, hash-checked snapshot (`scripts/snapshot_live_data.py`, ticket 05); new analyses and the ticket-11 reviews should read a named snapshot (`--root <snapshot>`), not the live `data/raw`. (An initial version of this finding also flagged some `git log` commits as unexplained; investigated and retracted -- they are ordinary pre-2026-09-21 project history, see `.scratch/future-plan/15`.)
- **2026-09-24 finding — Kronos forecasts are worse than a naive forecast (2024 PIT, ticket `18`):** pre-registered comparison of Kronos-small's quantiles against historical-simulation and random-walk bands: mean pinball loss at h=20 is about 2x the naive baseline (diff +0.022, 95% CI [+0.017, +0.028], WORSE), and worse at h=1 and h=5 too; the p5-p95 band held only 35% of 20-day outcomes (66% at one day), and the p50 misses by more than "no change". 50 of 51 tickers are worse. So the bands are overconfident and must not be presented as a risk range; the "forecasting/monitoring tool" description is unsupported for 2024 (doc wording pending the owner's decision). Ticket `19` (same day): 3 of 46 live paper fills were outside the reachable range (not flagged), 2 were logged before the session they could fill in, 11 matched no trade ticket; the trade log's `forecast_date` column was just the entry date until 2026-09-24; dividend-adjustment bias in the review 0.126% of capital (below the 0.25% fix threshold).

## Hard scope limits

Do **not** add (unless explicitly asked): live order execution, broker API integration, intraday data, portfolio optimization (Markowitz/factor), news sentiment, `pytest`/`tox` test frameworks, or CI config — all out of scope per `PROJECT_STRUCTURE.md §12`. The dashboard is paper-trading + broker-ready CSV export only. `Makefile` and `docker-compose.yml` already exist for Docker workflows — do not remove them.

## Superpowers workflow

**Invoke relevant skills BEFORE any response or action.** If there is even a 1% chance a skill applies, invoke the `Skill` tool to load it. Follow the skill's instructions exactly.

Priority order: (1) user's explicit instructions, (2) superpowers skills, (3) default system prompt.

**Skill priority:** process skills (brainstorming, systematic-debugging) before implementation skills.

**Red flags** — these thoughts mean STOP and check for skills first:
- "This is just a simple question"
- "Let me explore the codebase first"
- "This doesn't need a formal skill"

## Reading order for deeper context

1. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — authoritative design doc: module specs, friction model, evaluation methodology, full backtest results, open questions
2. [README.md](README.md) — project overview, honest caveats, quick start
3. [docs/user-manual.html](docs/user-manual.html), [docs/operations-manual.html](docs/operations-manual.html), [docs/monthly-walkthrough.html](docs/monthly-walkthrough.html) — usage, daily/weekly procedures, simulated month
4. [docs/superpowers/specs/](docs/superpowers/specs/) — approved design specs (completed ones in [archive/](docs/superpowers/archive/))
5. [kth/data/loader.py](kth/data/loader.py) — schema conversion and caching
6. [kth/data/universe.py](kth/data/universe.py) — 52-ticker universe, `FRICTION`, `SECTOR`
7. [kth/pipeline/daily.py](kth/pipeline/daily.py) — daily orchestration, `run_daily_pipeline` function
8. [kth/io/kaggle_runtime.py](kth/io/kaggle_runtime.py) — Kaggle secrets auth (injectable, offline-testable)
9. [data/backtest_results/MANIFEST.md](data/backtest_results/MANIFEST.md) — which backtest runs to cite (and which are stale)

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`Yutwizard/Kronos_Thai_Retail`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
