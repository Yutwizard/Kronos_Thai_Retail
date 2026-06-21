# Kronos-TH — Project Structure & Design Review

> **Single-document review of the Kronos-TH project.**
> Read this top-to-bottom before writing any more code. The goal is to confirm scope, design choices, and tradeoffs so we don't build the wrong thing.

> **Layer 5: Two dashboards available** — Google Suite (Kaggle primary / Colab backup + Sheets + Apps Script, zero-cost, no local GPU required) and Flask (`scripts/dashboard.py`, requires local GPU). Kaggle scheduled pipeline (`kth/pipeline/daily.py`, `kaggle/`) is the primary unattended runtime. Google Suite reached feature parity with Flask on 2026-06-06. Both are fully functional; users can choose based on environment.
> See [Google Suite spec](docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md) +
> [parity fix spec](docs/superpowers/specs/2026-06-06-google-suite-dashboard-parity-fixes-design.md) +
> [Kaggle pipeline spec](docs/superpowers/specs/2026-06-18-kaggle-scheduled-pipeline-design.md) +
> [Kaggle pipeline plan](docs/superpowers/plans/2026-06-18-kaggle-scheduled-pipeline.md) +
> [Flask spec](docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md).

---

## Table of contents

1. [Project goal](#1-project-goal)
2. [Scope decisions (locked in)](#2-scope-decisions-locked-in)
3. [Investable universe](#3-investable-universe)
4. [Data sources & honest limits](#4-data-sources--honest-limits)
5. [Hardware budget](#5-hardware-budget)
6. [System architecture](#6-system-architecture)
7. [Directory layout](#7-directory-layout)
8. [Notebook roadmap (5 notebooks)](#8-notebook-roadmap-5-notebooks)
9. [Module-by-module spec](#9-module-by-module-spec)
10. [Cost & friction model](#10-cost--friction-model)
11. [Evaluation methodology](#11-evaluation-methodology)
12. [What we will NOT build (and why)](#12-what-we-will-not-build-and-why)
13. [Open questions for review](#13-open-questions-for-review)
14. [Current status](#14-current-status)

---

## 1. Project goal

Build a **research-first, Colab-based forecasting and decision-support system** for a Thai retail investor, using the [Kronos](https://github.com/shiyu-coder/Kronos) foundation model.

The output is not orders. The output is a daily report answering: *"Given everything Kronos has learned about global financial K-lines, and given a fine-tune on the assets I can actually buy in Thailand, what does the model expect over the next 5–20 trading days, and how confident is it?"*

A Thai retail investor reading the report should be able to:

- See per-asset forecasts with **probabilistic uncertainty** (not a single point prediction).
- See backtested performance with **Thai-retail-realistic costs** baked in (not paper alpha).
- Understand which asset classes the model is good at vs. bad at, so they don't trust it blindly.

What this is **not**:

- An autotrader. We do not place orders via Settrade or any broker.
- A licensed financial advisor product.
- A high-frequency or intraday system.
- A claim that AI predicts markets. It's a forecasting tool, full stop.

---

## 2. Scope decisions (locked in)

These were debated and chosen earlier:

| Decision | Choice | Why |
|---|---|---|
| **Asset universe** | Broad — everything a Thai retail investor can actually buy | Most realistic use case; not just SET |
| **Time frequency** | Daily | Free data only. Intraday from yfinance is 60-day rolling — useless for training |
| **Hardware** | Google Colab / Kaggle free tier (T4 16GB) | Fits Kronos-small (24.7M params) and Kronos-base (102.3M) with care |
| **Delivery format** | Jupyter/Colab notebooks only | Research-first; no UI; reproducible |
| **Build order** | Data layer first, verify, then model | Avoid building 4 layers on top of broken data |

---

## 3. Investable universe

**100 tickers across 9 asset classes.** Defined in `kth/data/universe.py`.

| Asset class | # | Example tickers | Why included |
|---|---|---|---|
| `thai_equity` | 50 | PTT.BK, KBANK.BK, ... (50 SET stocks, 8 sectors) | Expanded from 15 |
| `thai_index` | 1 | ^SET.BK | Benchmark for Thai equity strategies |
| `us_equity` | 17 | AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, BRK-B, JPM, V, COST, WMT, NFLX, AMD, DIS, KO, PEP | Expanded from 10 |
| `etf_global` | 9 | SPY, QQQ, VTI, VWO, VEA, IEMG, EWY, EWJ, FXI | Same brokers as US stocks; global/regional exposure |
| `commodity` | 4 | GLD, GC=F, SLV, USO | Gold is huge in Thai retail; GLD is the cleanest daily price; GC=F is futures backup |
| `crypto` | 12 | BTC-USD, ETH-USD, SOL-USD, ADA-USD, AVAX-USD, LINK-USD, DOGE-USD, DOT-USD, LTC-USD, NEAR-USD, VET-USD, MATIC-USD | Trimmed from 5 (BNB, XRP dropped) |
| `bond_proxy` | 3 | TLT, IEF, HYG | Duration risk + credit risk benchmarks |
| `reit` | 2 | VNQ, CPNREIT.BK | Property exposure (US + Thai) |
| `fx_macro` | 2 | THB=X, DX-Y.NYB | Features only, not investable directly |

**Explicitly excluded** (with reasons):

- **Thai mutual funds**: most popular retail vehicle BUT no clean free API; NAV updates are daily-lagged and scattered across AMC websites. Workaround: use the underlying global benchmark as a proxy (e.g. for "global gold equity fund" → use GDX or GLD signal).
- **TFEX derivatives**: outside retail forecasting scope; leverage changes the math.
- **Individual bonds**: thin retail secondary market in Thailand; irregular prices.
- **Real estate / private equity**: not in scope for a K-line model.

---

## 4. Data sources & honest limits

### Primary: `yfinance`

| Asset class | yfinance coverage | History depth | Notes |
|---|---|---|---|
| Thai stocks `.BK` | ✅ Full | ~20+ years for blue chips | Some mid-caps shorter (recent IPOs) |
| US stocks | ✅ Full | 20+ years | Best-covered class |
| Global ETFs | ✅ Full | Since ETF launch | SPY: since 1993; QQQ: since 1999 |
| Gold (GLD) | ✅ Full | Since 2004 | Cleanest gold daily price; GC=F futures as backup |
| Crypto | ✅ Full | BTC since 2014, ETH since 2017 | 7-day trading week (no business-day gaps) |
| FX | ✅ Full | Decades | THB=X = USDTHB |
| SET Index | ⚠️ Quirky | Recent only via `^SET.BK` | May need alternative symbol; tested in Notebook 01 |

### Hard limits of free data

1. **Intraday is rolling 60 days only.** Confirmed from yfinance docs: `intervals <1d` cap at 60 days back; `1m` capped at 7 days. → That's why we are daily-only.
2. **Yahoo throttles aggressively.** We use 0.5s pauses between downloads and exponential backoff retry.
3. **Adjusted vs unadjusted.** We use `auto_adjust=True` so splits and dividends are baked into the price series.
4. **Survivorship bias.** Yahoo doesn't list delisted Thai stocks. Backtests will overstate returns. We disclose this in every backtest report.

### Auxiliary (free, not yet integrated)

- **Bank of Thailand API** — FX, policy rate, bond yields. Useful as macro features in fine-tuning. Free, public.
- **SET official website** — corporate actions, sector classifications. Scrape-only, no API.

---

## 5. Hardware budget

**Target environment**: Google Colab free tier with T4 GPU.

| Resource | Available | Used by |
|---|---|---|
| GPU | NVIDIA T4 (16GB VRAM, ~15GB usable) | Kronos inference + fine-tuning |
| RAM | 12.7 GB | Pandas/Numpy preprocessing |
| Disk | ~110 GB temp (evaporates on shutdown) | Parquet cache (~50MB total for our universe) |
| Session | 8-hour cap (free) | Each fine-tuning run must fit |

**Kronos model sizes vs. T4 capacity:**

| Model | Params | Context | Inference VRAM | Full fine-tune | LoRA fine-tune |
|---|---|---|---|---|---|
| Kronos-mini | 4.1M | 2048 | <1 GB | ✅ trivial | ✅ |
| **Kronos-small** | 24.7M | 512 | ~1 GB | ✅ comfortable batch_size=32 | ✅ |
| **Kronos-base** | 102.3M | 512 | ~2 GB | ✅ batch_size=8 + grad accumulation | ✅ |
| Kronos-large | 499.2M | 512 | tight | ❌ not released anyway | n/a |

**Default plan**: Kronos-small for iteration speed; Kronos-base for the final fine-tune.

**Persistence**: cache to Google Drive (`/content/drive/MyDrive/kronos-th/`) so we don't redownload 10 years of data every session.

---

## 6. System architecture

```
┌────────────────────────────────────────────────────────────────┐
│  LAYER 5: Decision report (notebook 05)                        │
│    For each ticker today: median forecast, P5/P95 band,        │
│    simple signal, model-confidence flag                        │
├────────────────────────────────────────────────────────────────┤
│  LAYER 4: Strategy & evaluation (notebook 03)                  │
│    Walk-forward backtest, Thai-retail FRICTION, drawdown,      │
│    Sharpe vs SET/SPY benchmarks                                │
├────────────────────────────────────────────────────────────────┤
│  LAYER 3: Kronos model (notebooks 02, 04)                      │
│    Zero-shot KronosPredictor + fine-tuned variant on our       │
│    universe. Probabilistic sampling (sample_count > 1).        │
├────────────────────────────────────────────────────────────────┤
│  LAYER 2: Feature pipeline (kth/data/loader.py)                │
│    yfinance → Kronos schema (open/high/low/close/volume/       │
│    amount + timestamps). Quality checks. Parquet cache.        │
├────────────────────────────────────────────────────────────────┤
│  LAYER 1: Universe definition (kth/data/universe.py)           │
│    100 tickers, 9 asset classes, FRICTION per class            │
└────────────────────────────────────────────────────────────────┘
```

LAYER 5: Dashboard / Report   google_suite/                          ✅ built (Google Suite dashboard)
                                 scripts/dashboard.py                    ✅ built (Flask dashboard — local GPU option)
                                 scripts/start_dashboard.sh              ✅ built (one-command launcher: venv + data + pipeline + serve)
                                 kth/trading/portfolio.py                ✅ built
                                 kth/trading/trade_gen.py                ✅ built
                                 kth/trading/sheets.py                   ✅ built
                                 kth/pipeline/daily.py                   ✅ built (Kaggle unattended orchestration)
                                 kth/io/kaggle_runtime.py                ✅ built (SA auth, injectable)
                                 kaggle/build_kaggle_notebook.py         ✅ built (≤5-cell Kaggle notebook)
                                 scripts/cron_pipeline.sh                ✅ built
                                 notebooks/05_decision_report.ipynb      ✅ built (Colab version)
LAYER 4: Backtest             kth/backtest/walkforward.py            ✅ built
                                kth/backtest/strategy.py               ✅ built
                                kth/backtest/metrics.py                 ✅ built
                                scripts/compare_finetune.py            ✅ built
LAYER 3: Kronos model         kth/models/kronos_wrapper.py           ✅ built
                                kth/models/finetune.py                  ✅ built
                                kth/models/_kronos_bridge.py            ✅ built
                                scripts/train_per_market.py             ✅ built (SGDR)
                                scripts/eval_holdout.py                 ✅ built
                                checkpoints/{model}/fold{f}/best/       ✅ 9 trained
LAYER 2: Feature pipeline     kth/data/loader.py                       ✅ done
LAYER 1: Universe definition  kth/data/universe.py                     ✅ done (100 tickers)

---

## 7. Directory layout

```
kronos-th/
├── README.md                       Project overview + caveats
├── requirements.txt                Pinned dependencies
├── verify_data_layer.py            Offline test runner (5 tests, all pass)
│
├── kth/                            The reusable Python package
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── universe.py             ✅ 100-ticker universe + FRICTION costs
│   │   └── loader.py               ✅ yfinance → Kronos schema + caching
│   ├── io/                         ✅ built (2026-06-21)
│   │   ├── __init__.py
│   │   └── kaggle_runtime.py       ✅ SA auth, RuntimeConfig, injectable getter
│   ├── models/                     ✅ built
│   │   ├── __init__.py
│   │   ├── kronos_wrapper.py       ✅ KronosTH zero-shot wrapper
│   │   ├── finetune.py             ✅ Fine-tune loop (ZS wins, FT not deployed)
│   │   └── _kronos_bridge.py       ✅ Import bridge for local Kronos repo
│   ├── backtest/                   ✅ built
│   │   ├── __init__.py
│   │   ├── walkforward.py          ✅ Walk-forward eval driver
│   │   ├── strategy.py             ✅ Signal → position translation
│   │   └── metrics.py              ✅ Sharpe, MaxDD, Calmar, VaR, attribution
│   ├── pipeline/                   ✅ built (2026-06-21)
│   │   ├── __init__.py
│   │   └── daily.py                ✅ run_daily_pipeline() — 6 injectable seams
│   ├── trading/                    ✅ built (2026-06-02)
│   │   ├── __init__.py
│   │   ├── portfolio.py            ✅ Paper/live position tracking, P&L, trade log
│   │   ├── trade_gen.py            ✅ Trade ticket generation, 3-filter rule
│   │   ├── sheets.py               ✅ Staging + promotion + position rows
│   │   └── sheets_config.py        ✅ Sheet tab names + header schemas
│   ├── testing/                    ✅ built (2026-06-21)
│   │   ├── __init__.py
│   │   └── synthetic.py            ✅ Shared synthetic OHLCV generator
│   └── utils/                      ✅ built
│       ├── __init__.py
│       ├── plot.py                 ✅ Standard chart styles
│       └── report.py               ✅ Daily decision report renderer
│
├── kaggle/                           ✅ Kaggle scheduled pipeline (2026-06-21)
│   ├── build_kaggle_notebook.py      ✅ Generates kronos_kaggle_pipeline.ipynb
│   └── kronos_kaggle_pipeline.ipynb  ✅ 5-cell thin wrapper (no business logic)
│
├── notebooks/
│   ├── 01_data_layer.ipynb         ✅ Verify yfinance access (Colab-ready)
│   ├── 02_kronos_zero_shot.ipynb   ✅ Superseded by walkforward.py + scripts
│   ├── 03_walkforward_backtest.ipynb  ✅ Superseded by scripts/run_*.py
│   ├── 04_finetune_per_market.ipynb   ✅ Per-market training (Colab T4)
│   └── 05_decision_report.ipynb       ✅ Daily decision report (3 views)
│
├── data/
│   ├── raw/                        Cached parquet (one per ticker)
│   ├── processed/                  Train/val/test splits for fine-tune
│   └── backtest_results/           Walk-forward results per run
│       └── MANIFEST.md             ✅ Authoritative vs stale runs (2026-06-21)
│
└── configs/                        YAML configs for fine-tune experiments
```

**Convention**: Anything in `kth/` is library code (tested, reused across notebooks). Anything in `notebooks/` is the actual research narrative — exploratory, with plots and commentary.

---

## 8. Notebook roadmap (5 notebooks)

### Notebook 01 — Data layer verification ✅

**Built. Tested offline. Ready to run on Colab.**

Cells:
1. Install yfinance + pyarrow; import the `kth` package
2. Reachability smoke test (download AAPL last 5 days)
3. Probe each asset class with a few tickers
4. Visual sanity check (plot 6 representative tickers)
5. Download full 100-ticker universe to cache
6. Persist to Google Drive (optional)
7. Quality report by asset class
8. Confirm one ticker loads into Kronos-expected schema

### Notebook 02 — Kronos zero-shot inference ✅ (superseded)

**Superseded by** `scripts/run_backtest.py` and `kth/backtest/walkforward.py`. Zero-shot inference is run at scale via the walkforward pipeline, not interactively in a notebook. Backtest results (2022–2026) are in `docs/user-manual.md §6`.

### Notebook 03 — Walk-forward backtest ✅ (superseded)

**Superseded by** `scripts/run_*.py` family (`run_2023_n50.py`, `run_2025_n50.py`, `run_2026_n50.py`, `run_expanded_backtest.py`). The notebook approach was replaced by parameterised scripts that can run headlessly and resume from checkpoints.

### Notebook 04 — Fine-tune Kronos-small on Colab T4 ✅

**Built.** `notebooks/04_finetune_per_market.ipynb`. Also available as `scripts/train_per_market.py` for local/non-Colab runs. 9 checkpoints trained (3 markets × 3 folds). Verdict: zero-shot beats fine-tuning in all 3 markets. Checkpoints saved but not deployed.

### Notebook 05 — Daily decision report ✅

**Built.** `notebooks/05_decision_report.ipynb` (Colab version, 3 views). For daily use, the two dashboard options are: the Google Suite dashboard (`google_suite/`, zero-cost, no local GPU) and the local Flask dashboard (`scripts/dashboard.py`, requires local GPU + cron). Both are fully functional. The Flask dashboard can also be launched with one command via `scripts/start_dashboard.sh` (idempotent venv + data + pipeline + serve).

---

## 9. Module-by-module spec

### `kth/data/universe.py` ✅ built

**Public API:**
```python
UNIVERSE: dict[str, list[tuple[ticker, name, note]]]
FRICTION: dict[str, dict[str, float]]
get_all_tickers() -> list[str]
get_ticker_class(ticker) -> str
get_display_name(ticker) -> str
```

**Design choices:**
- Hardcoded list, not a CSV. The universe is small and stable; adding a ticker is a code change so we get version control on it.
- `FRICTION` is per-class, not per-ticker. Within a class, transaction costs are similar enough.
- Display names included so plots and reports look human-readable.

### `kth/data/loader.py` ✅ built

**Public API:**
```python
download_universe(tickers, period, cache_dir, pause_between) -> pd.DataFrame  # quality report
load_cached(ticker, cache_dir) -> pd.DataFrame                                # Kronos-format
list_cached(cache_dir) -> list[str]
to_kronos_format(yf_df, ticker) -> pd.DataFrame
quality_report(df, ticker) -> dict
```

**Design choices:**
- Parquet, not CSV. Smaller and faster, important when we have 100 files × ~3000 rows each.
- One file per ticker, not one big merged file. Different tickers have different date ranges; merging would force NaN-padding and break the model.
- We compute `amount = close × volume` ourselves because Yahoo doesn't expose it. Kronos's tokenizer uses it as a "turnover" channel; using close×volume is what the original Kronos repo also does for markets that don't publish turnover.
- Exponential backoff (3 tries, 2s/4s/8s) for individual ticker failures — Yahoo's rate limit is unpredictable.

### `kth/models/kronos_wrapper.py` ✅ built

**Public API:**
```python
class KronosTH:
    def __init__(self, model_name="NeoQuasar/Kronos-small", device="auto")
    def forecast(self, ticker, lookback=400, pred_len=20, n_samples=20) -> pd.DataFrame
    def forecast_batch(self, tickers, ...) -> dict[ticker, pd.DataFrame]
```

**As built:** Wraps `KronosPredictor` via `_kronos_bridge.py`. Always probabilistic, returns P5/P50/P95 bands. Model cached at module level. Zero-shot only in production (fine-tuning did not beat ZS).

### `kth/models/finetune.py` ✅ built

**Public API:**
```python
def prepare_dataset(cache_dir, train_end, val_end, lookback, pred_len) -> dict
def finetune_tokenizer(dataset, output_dir, **hparams)
def finetune_predictor(dataset, tokenizer_path, output_dir, **hparams)
def evaluate_model(model, dataset) -> dict
```

**As built:** 9 checkpoints trained (3 markets × 3 folds). Verdict: zero-shot beats fine-tuning everywhere. Checkpoints exist at `./checkpoints/{model}/fold{f}/best/` but are not deployed.

### `kth/backtest/walkforward.py` ✅ built

**Public API:**
```python
@dataclass
class BacktestConfig:
    start_date: str
    end_date: str
    lookback: int = 400
    pred_len: int = 20
    refit_every: int = 0  # 0 = zero-shot, no refit
    max_positions: int = 5

def run_walkforward(config, predictor, universe_subset) -> BacktestResult
def precompute_forecasts(config, predictor, tickers) -> None
```

**As built:** Strict no-look-ahead. Forecasts cached per (date, ticker) to avoid re-running. Hysteresis buffer prevents whipsaw. 4 benchmarks computed: SET, SPY, 60/40, equal-weight.

### `kth/backtest/metrics.py` ✅ built

**Implemented metrics:**
- CAGR, Sharpe (annualised, rf=2%), Sortino, Calmar, Omega
- Max drawdown, avg drawdown, Ulcer Index, max/avg duration
- Historical VaR (95%, 99%), CVaR
- Trade win rate, payoff ratio, profit factor
- OLS alpha, beta, t-stat vs benchmark
- Per-asset-class attribution
- **Planned additions (Phase 3–4):** IR, batting average, calibration check, drawdown velocity, bootstrap p-value

---

## 10. Cost & friction model

Encoded in `FRICTION` dict in `universe.py`. Values are **one-way** percentages.

| Asset class | Commission one-way | Slippage one-way | Round-trip total | Rationale |
|---|---|---|---|---|
| `thai_equity` | 0.168% | 0.10% | 0.536% | 0.157% online commission + 7% VAT on commission (= 0.168%) + 0.001% SET fee. Slippage modest because we focus on liquid stocks |
| `thai_index` | 0.168% | 0.10% | 0.536% | Treated as if traded via TDEX ETF; same as equity |
| `reit` | 0.168% | 0.15% | 0.636% | Same commission, slightly higher slippage due to thinner books |
| `us_equity` | 0.30% | 0.05% | 0.70% | Thai brokers charge ~0.20–0.30% for US stocks + FX spread; we use 0.30% conservatively |
| `etf_global` | 0.30% | 0.05% | 0.70% | Same as US equity |
| `bond_proxy` | 0.30% | 0.05% | 0.70% | Same as US equity (these are ETFs) |
| `commodity` | 0.30% | 0.10% | 0.80% | ETF route via Thai broker |
| `crypto` | 0.25% | 0.20% | 0.90% | Bitkub maker/taker is 0.25%; slippage on smaller-cap alts can be real. **Cap gains tax-exempt 2025–2029** for licensed-exchange trades |
| `fx_macro` | 0% | 0% | 0% | Not actually traded; used as feature/benchmark only |

**These values matter.** A strategy that looks like it earns 8% annualized with paper costs may earn 2% or be negative after frictions. We will show **gross vs. net** in every backtest.

---

## 11. Evaluation methodology

### Prediction-level metrics (Notebook 02)

For each ticker, for the held-out test period:
- **MAE / RMSE** of forecasted close vs. actual close
- **Directional hit-rate**: % of forecasts where sign(predicted return) == sign(actual return)
- **Correlation**: Pearson between forecast return and actual return
- **Calibration**: when the model says "P95 = X", how often does actual exceed X?

### Strategy-level metrics (Notebook 03)

- Equity curve, gross and **net of frictions**
- CAGR, Sharpe (annualized, rf=2% as Thai 1Y govt bond proxy), Sortino, Calmar
- Max drawdown + drawdown duration
- Hit-rate, win/loss ratio
- Per-asset-class attribution

### Honest benchmarks

Every strategy result must be compared to:
1. **Buy-and-hold SET Index** — the do-nothing Thai option
2. **Buy-and-hold SPY** — the do-nothing US option
3. **60/40 SPY/TLT** — classic balanced portfolio
4. **Equal-weight on the same universe** — the "no model" portfolio

If our strategy doesn't beat all four after frictions, we say so plainly.

---

## 12. What we will NOT build (and why)

| Thing | Reason |
|---|---|
| Live order execution via Settrade | Out of scope; requires real brokerage account; risk of catastrophic bugs |
| Real-time streaming data | Free data doesn't support it for Thai stocks |
| Intraday strategies | yfinance free intraday is 60-day rolling — not enough history to train or backtest |
| Options pricing / Greeks | Different model class; not what Kronos is for |
| News sentiment / fundamental data | Kronos is K-line only by design; adding news = different project |
| A web UI | You chose notebooks-only |
| Portfolio optimization (Markowitz, risk parity, factor models) | Adds complexity without changing core question. Could be Notebook 06 later if useful |
| Tax optimization | Country-specific, advice-adjacent, out of scope |

---

## 13. Open questions — RESOLVED (2026-05-21)

1. **Model size** → **Kronos-small (24.7M).** Confirmed by 65 hrs of training across 3 markets on GTX 1060 6GB. Kronos-base would require T4 or A100.

2. **Pred horizon** → **20 days.** Longer = more useful signal. 5-day too noisy for daily-bar data. Confirmed by holdout evaluation showing 56-65% direction accuracy at 20-day horizon.

3. **Forecast samples** → **10.** Fits 6GB VRAM. 20+ causes OOM on GTX 1060. 50 samples would require T4 16GB.

4. **Strategy aggressiveness** → **Long-only.** Short selling not realistic for Thai retail (can't short SET stocks). US equities: possible via inverse ETFs (SH, SQQQ) — not yet implemented.

5. **Universe trim** → **100 tickers, no trim.** Small-data tickers (GULF.BK with 268 rows, SCB.BK with 984 rows) are filtered at precompute time by walkforward.py's viable-check (minimum LOOKBACK rows required).

6. **Benchmarks** → **4 benchmarks already computed** in walkforward.py (`_compute_benchmarks`): SET Index, SPY, 60/40 SPY/TLT, equal-weight. FX-adjusted returns: THB=X available — compute USD returns × THB=X for Thai investor P&L.

---

## 14. Current status (2026-05-21)

### ✅ Built and tested

- `kth/data/universe.py` — 100-ticker universe (50 Thai, 17 US, 12 crypto, rest unchanged), FRICTION dict, SECTOR mapping, O(1) reverse-lookup dict
- `kth/data/loader.py` — yfinance loader, Kronos-format conversion, parquet cache, quality checks
- `verify_data_layer.py` — 5 offline tests, all pass against synthetic data
- `verify_fixes.py` — 17 regression tests for stats fixes (PSR, alignment, bootstrap, cash guard, etc.) — all pass
- `verify_kaggle_runtime.py` — 19 tests for Kaggle auth + pipeline orchestration (idempotency, capital reset, trade edits, BKK clock, failure path) — all pass
- `notebooks/01_data_layer.ipynb` — Colab notebook for verifying real yfinance access
- `kth/models/kronos_wrapper.py` — KronosTH wrapper (zero-shot inference)
- `kth/models/finetune.py` — Dataset preparation, tokenizer caching, evaluate_model
- `kth/models/_kronos_bridge.py` — Import bridge for local Kronos repo
- `kth/backtest/walkforward.py` — Walk-forward backtest with benchmark comparison, equity curve indexed by mark-day (2026-06-21 fix), blended entry price on rebalance
- `kth/backtest/strategy.py` — Signal → position translation, dead-code cleanup (2026-06-21)
- `kth/backtest/metrics.py` — Sharpe, MaxDD, Calmar, hit-rate, attribution. PSR uses per-period SR (2026-06-21 fix), stationary block bootstrap for Sharpe CI, t-test uses ddof=1
- `kth/pipeline/daily.py` — `run_daily_pipeline()` with 6 injectable seams, Risk Metrics upsert-by-date, Calibration idempotency, col>26 fix (2026-06-21)
- `kth/io/kaggle_runtime.py` — SA auth, RuntimeConfig, load_secrets(), make_sheets_client()
- `kaggle/build_kaggle_notebook.py` — Generates ≤5-cell Kaggle scheduled notebook
- `run_pipeline.py` — Thin entrypoint, `--dry-run` for offline smoke tests
- `kth/testing/synthetic.py` — Shared synthetic OHLCV generator for offline tests
- `data/backtest_results/MANIFEST.md` — Marks authoritative (n50) vs stale (pre-n50, invvol) runs
- `scripts/train_per_market.py` — SGDR fine-tuning (3 markets × 3 folds)
- `scripts/eval_holdout.py` — Holdout evaluation on 2025 data
- `scripts/compare_finetune.py` — Fine-tuned vs zero-shot backtest comparison
- `README.md` — project overview
- `requirements.txt` — minimal pinned deps
- `docs/user-manual.md` — full user manual with methodology, backtest results, and usage instructions
- `docs/user-manual.html` — HTML version with 7 embedded data visualization charts
- `docs/operations-manual.html` — styled HTML operations manual
- `docs/monthly-walkthrough.html` — 21-day simulated month with timeline and allocation graphics
- `docs/backtest-methodology.html` — styled HTML with 4 charts, Gantt timeline, and "What This Means" section
- `docs/superpowers/specs/2026-05-24-expanded-backtest-design.md` — design spec for 2020-2024 Thai equity expansion
- `docs/superpowers/plans/2026-05-24-expanded-backtest.md` — implementation plan (~10.5 hrs GPU, regime decomposition)

### Backtest Results (2022-2024, 3 markets × 4 benchmarks)

| Market | Strategy CAGR | Sharpe | Max DD | Alpha over equal-wt | Verdict |
|--------|--------------|--------|--------|---------------------|---------|
| Thai equity (49 tkrs) | +31.44% | 1.40 | −17.97% | **+30pp** | ✅ ZS Deploy |
| US equity (17 tkrs) | +30.34% | 0.97 | −43.77% | +16pp | ✅ ZS Deploy |
| Crypto (12 tkrs) | +16.45% | 0.52 | −68.58% | +22pp | ✅ ZS Deploy |

**Zero-shot beats fine-tuning in all 3 markets.** The 9 fine-tuned checkpoints are saved but not deployed.

See full results in `docs/user-manual.md` §6.

### Known unknowns — RESOLVED

- ✅ Backtest results for fine-tuned models — completed. ZS wins everywhere.
- ✅ Calendar compatibility (crypto 7-day vs equity 5-day) — fixed (Task 1).
- ✅ Hit-rate metric confusion (trade P&L vs forecast accuracy) — renamed to trade_win_rate.
- ✅ Stale PROJECT_STRUCTURE.md — updated now.
- Whether `^SET.BK` works on Yahoo (we have a backup plan: scrape from SET website if needed)
- How well Kronos generalizes zero-shot to Thai mid-caps — this is the real research question

### QFM Enhancement Plan ✅ COMPLETE (2026-06-03)

4-phase, 15-item improvement plan — all shipped. Plan files archived.

**Statistical questions — resolved:**
- Historical backtest p-values (p=0.015/0.257/0.353) use a **t-test** in `compute_metrics()` — unchanged. 2024 is significant; 2025/2026 are not.
- Live dashboard now tracks `compute_bootstrap_pvalue()` (centered bootstrap resampling, n=1000) in `/api/risk` — will accumulate significance as paper trading equity curve grows.
- P5/P95 calibration check: `compute_calibration()` added to `metrics.py`, wired to `/api/risk`, reports `insufficient_data` until ≥10 historical forecast dates accumulate.
- Survivorship bias: formal disclosure added to `docs/backtest-methodology.html` (~+28–30% CAGR adjusted estimate).

**Bootstrap p-value clarification (bug fixed `df80804`):**
Permutation preserves the mean exactly → always non-significant. Fixed to centered bootstrap resampling: center active returns under H0 (subtract observed mean), resample with replacement, count fraction ≥ observed mean. Verified: consistent +1%/day → p=0.0; random → p≈0.5.

**Resilience issues — all fixed:**
- `trade_gen.py`: friction from FRICTION dict (not hardcoded 0.00268); INITIAL_CAPITAL from portfolio.py; sector guard (max 2/sector); T+2 warning; per-ticker friction in cash flow.
- `portfolio.py`: atomic JSON write via os.replace(); model_version + forecast_date in trade log.
- `dashboard.py`: forecast recovery (skip completed tickers); POST /api/trades validation; sanity failures surfaced in /api/health.
- `download_data.py`: price sanity filter (>30% move → exclude from forecast, write to sanity log).
- `cron_pipeline.sh`: LINE Notify on failure via $LINE_NOTIFY_TOKEN.
- `metrics.py`: IR, batting average, calibration, drawdown velocity, bootstrap p-value.

### 4-Year OOS Results (2023–2026, n=50)

| Year | Net CAGR | Sharpe | Max DD | p-value | Friction/yr | EW CAGR | Alpha vs EW |
|------|----------|--------|--------|---------|-------------|---------|-------------|
| **2023** | +2.6% | 0.10 | −13.1% | 0.419 ❌ | 5.68% | +12.8% | **−10.2pp** |
| **2024** | +42.0% | 2.27 | −6.9% | 0.015 ✅ | 7.54% | −7.2% | **+49.2pp** |
| **2025** | +33.7% | 1.03 | −24.0% | 0.257 ❌ | 17.35% | −9.9% | **+43.6pp** |
| **2026** | +143% ann. | 2.42 | −18.3% | 0.353 ❌ | 32.78% | +41.8% | **+101pp** |

**Decision gate triggered: 🔴 MODEL REVIEW** (2023 Sharpe=0.10 < 0.5).

**2023 root cause — NOT model failure. Cash drag + friction:**
- Deployed stocks actually beat EW by +3.3pp on deployed capital — model predictions were correct
- Cash drag: NEUTRAL band (50% deployed) in a +12.8% EW bull market costs −6.4pp
- Friction: −5.68%/yr
- Total underperformance = cash drag + friction − small stock-selection gain

**Pattern: strategy underperforms EW in bull markets because it holds cash (by design)**. In bear markets (2024: EW −7.2%, 2025: EW −9.9%), holding selective positions instead of equal-weight is exactly the right strategy.

**Bonferroni (4 OOS years, threshold p<0.0125):** No year survives. 2024 p=0.015 is the closest.

### Open questions from QFM review (2026-06-03)

Post-review data analysis surfaced the following — pending 2023 backtest before full resolution:

**Confirmed (do not re-investigate):**
- `inv_vol` position sizing was backtested in `thai_equity_2022-2024_invvol/`: CAGR 13.29%, Sharpe 0.84, p=0.732. **Equal-weight is conclusively better.** inv_vol allocates more to low-signal, low-vol stocks. Do not use.
- Canonical 2022-2024 result is `thai_equity_2022-2024_v2/` (CAGR 31.44%, Sharpe 1.40, p=0.034). The original `thai_equity_2022-2024/` run (CAGR 25.03%, Sharpe 1.29) used different data — v2 is the one in AGENTS.md.
- Bonferroni correction (9 tests, threshold p<0.0056): no year survives. 2024 p=0.015 is the closest. Statistical evidence is suggestive, not conclusive.

**Open — investigate after 2023 backtest completes:**
- **2025 friction drain (17.35%/yr vs 7.54% in 2024):** 2.3× more friction despite only 8% more trades. Likely cause: larger average position sizes in high-volatility 2025 regime (more capital deployed per trade). If structural, may need higher entry threshold to reduce turnover in volatile regimes.
- **Kronos pre-training cutoff:** Unverified. If training data overlaps 2022–2024, the canonical backtest is not out-of-sample. Check Kronos paper/model card.
- **Factor attribution:** Is the alpha genuinely predictive or a dressed momentum factor? Regress daily returns on SET 12-1 momentum factor.
- **2023 n=50 result:** The most credible OOS year. p-value here determines whether the strategy has demonstrated statistically robust edge.

### Layer 5 — Google Suite Dashboard (2026-06-04) ✅ AVAILABLE + Flask parity (2026-06-06)

A second dashboard option, in addition to the Flask dashboard. Zero-cost, browser-based, no local GPU required:

| Component | Role | Status |
|---|---|---|
| `google_suite/kronos_daily_pipeline.ipynb` | 44-cell Colab notebook — daily compute + forecast + ticket | ✅ Built (generated from `build_notebook.py`) |
| `google_suite/apps_script/Code.gs` | Apps Script backend — reads Sheets, computes metrics (15 functions, 60s cache) | ✅ Built |
| `google_suite/apps_script/Index.html` | 5-tab web app SPA — Dashboard, Trade Ticket, Portfolio, History, Risk (Flask-parity) | ✅ Built |

**Architecture:** Colab → Google Sheets (fills input + data store) → Apps Script web app. JSON-bridge: `os.chdir(KTH_REPO)` makes all `Path("data/...")` calls resolve against Drive. Existing `kth.*` functions unchanged.

**Spec:** `docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md` + `docs/superpowers/specs/2026-06-06-google-suite-dashboard-parity-fixes-design.md`
**Plan:** `docs/superpowers/plans/2026-06-04-google-suite-implementation-plan.md` + `docs/superpowers/plans/2026-06-06-google-suite-dashboard-parity-fixes.md`

### Paper Trading — Live Since 2026-06-04

Portfolio initialised 2026-06-04 with 500,000 THB. Currently:
- 8 trades recorded (CPF.BK, BCH.BK, HMPRO.BK)
- 3 open positions: CPF.BK (500sh), BCH.BK (1,000sh), HMPRO.BK (1,700sh)
- 94% cash (BEAR allocation — SET bull market regime)
- Allocation band: NEUTRAL (bootstrap, <20 closed trades)

Both dashboards are available for daily use. Choose based on environment:
- **Google Suite** (`google_suite/`) — zero-cost, browser-based, no local GPU, includes Reset Capital, Signal Health Banner, Trade Log edit/delete, 60s auto-refresh
- **Flask** (`scripts/dashboard.py`) — local Python + GPU, Run Pipeline button, fill-price modal, trade history inline edit, historical backfill

Flask dashboard improvements shipped 2026-06-04 (still functional):
- Fill-price confirmation modal with editable shares + price per trade
- Partial fill / no-fill support (0 shares = skip)
- Trade history panel with inline edit (shares + price) and delete
- Friction breakdown in modal (Gross | Friction | Cash Impact per row)
- Per-class friction corrected in `execute_trade()` (was hardcoded 0.00268)
- Initial capital setup banner (first-day only)
- Run Pipeline button (one-click morning routine from browser)

---

*Document version: 2026-06-06. Updated: Google Suite dashboard reached Flask parity, both dashboards documented as available options.*
