# Kronos-TH — Project Structure & Design Review

> **Single-document review of the Kronos-TH project.**
> Read this top-to-bottom before writing any more code. The goal is to confirm scope, design choices, and tradeoffs so we don't build the wrong thing.

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

LAYER 5: Decision report      notebooks/05_decision_report.ipynb     ⬜ planned
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
│   │   ├── universe.py             ⚙️  100-ticker universe + FRICTION costs
│   │   └── loader.py               ⚙️  yfinance → Kronos schema + caching
│   ├── models/                     [planned]
│   │   ├── __init__.py
│   │   ├── kronos_wrapper.py       Thin wrapper around KronosPredictor
│   │   └── finetune.py             Fine-tune loop adapted for T4 + our data
│   ├── backtest/                   [planned]
│   │   ├── __init__.py
│   │   ├── walkforward.py          Walk-forward eval driver
│   │   ├── strategy.py             Signal → position translation
│   │   └── metrics.py              Sharpe, MaxDD, Calmar, hit-rate
│   └── utils/                      [planned]
│       ├── __init__.py
│       ├── plot.py                 Standard chart styles
│       └── report.py               Daily decision report renderer
│
├── notebooks/
│   ├── 01_data_layer.ipynb         ✅ Verify yfinance access (Colab-ready)
│   ├── 02_kronos_zero_shot.ipynb   ⬜ Zero-shot inference on all classes
│   ├── 03_walkforward_backtest.ipynb  ⬜ Backtest with realistic costs
│   ├── 04_finetune_per_market.ipynb     ✅ Per-market training (Colab T4)
│   └── 05_decision_report.ipynb         ✅ Daily decision report (3 views)
│
├── data/
│   ├── raw/                        Cached parquet (one per ticker)
│   └── processed/                  Train/val/test splits for fine-tune
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

### Notebook 02 — Kronos zero-shot inference ⬜

Goal: see what a *pre-trained, untouched* Kronos model says about each asset class. This is the baseline before fine-tuning.

Cells:
1. Load `NeoQuasar/Kronos-Tokenizer-base` and `NeoQuasar/Kronos-small`
2. For 6 representative tickers (PTT.BK, AAPL, SPY, GLD, BTC-USD, ^SET.BK):
   - Pull last 400 days, predict next 20 days
   - Use `sample_count=20` for probabilistic forecast
   - Plot prediction band (P5, P50, P95) vs. actual
3. Compute per-asset error: MAE, directional hit-rate, correlation
4. Summary table: which asset classes Kronos handles best zero-shot

**Honest expectation**: Kronos will do best on assets most similar to its pre-training (US stocks, crypto, gold). Thai mid-caps may be weakest. We'll see.

### Notebook 03 — Walk-forward backtest ⬜

Goal: turn forecasts into a strategy, run it through history with realistic costs, measure performance.

**Strategy v1 (intentionally simple):**
- Each day, get Kronos forecast for next 5 days
- If median forecast return > threshold T_long, go long 1 unit
- If median forecast return < -T_long, exit (or short if `allow_short=True`)
- Position sizing: equal-weight across signals, capped at N positions
- Apply per-asset FRICTION costs from `universe.py`

Cells:
1. Load all cached data, split into train/test (e.g. test = last 2 years)
2. Walk-forward loop: refit-free zero-shot first; later notebook redoes this with the fine-tuned model
3. Compute portfolio P&L net of frictions
4. Plot equity curve vs. buy-and-hold benchmarks per asset class
5. Compute Sharpe, max drawdown, Calmar, hit-rate
6. Drawdown attribution: which asset class hurt us most?

### Notebook 04 — Fine-tune Kronos-small on Colab T4 ⬜

Goal: adapt Kronos to our specific universe and see if it beats zero-shot.

Cells:
1. Build train/val/test pickles from cached parquet (mimic Kronos's QlibDataset format)
2. Configure: lookback=400, pred_len=20, batch_size=8, grad_accum=4
3. Fine-tune tokenizer (1 epoch on T4 ~30 min)
4. Fine-tune predictor (3-5 epochs on T4 ~2 hours)
5. Save checkpoint to Drive
6. Re-run zero-shot evaluation from Notebook 02 with the fine-tuned model — does it improve?

**Risk**: T4 sessions cap at ~8 hours and disconnect. We'll use frequent checkpointing.

### Notebook 05 — Daily decision report ⬜

Goal: a single rendered output a user could look at each morning.

Cells:
1. Load fine-tuned model + latest data
2. For every ticker in universe: 20-step forecast with 20 samples
3. For each ticker compute:
   - Median expected return (1d, 5d, 20d)
   - P5/P95 band width (uncertainty measure)
   - Trend direction agreement across samples (consensus measure)
   - "Confidence flag": green/yellow/red based on band width & consensus
4. Render markdown table sorted by expected return × confidence
5. Disclaimers: this is research output, not advice

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

### `kth/models/kronos_wrapper.py` ⬜ planned

**Planned API:**
```python
class KronosTH:
    def __init__(self, model_name="NeoQuasar/Kronos-small", device="auto")
    def forecast(self, ticker, lookback=400, pred_len=20, n_samples=20) -> pd.DataFrame
    def forecast_batch(self, tickers, ...) -> dict[ticker, pd.DataFrame]
```

**Design choices:**
- Wraps `KronosPredictor` but always uses `predict_batch` internally for speed.
- Always probabilistic (`n_samples >= 5`), returns all sample paths so callers can compute their own bands.
- Caches the loaded model in a module-level variable to avoid reloading per call.

### `kth/models/finetune.py` ⬜ planned

**Planned API:**
```python
def prepare_dataset(cache_dir, train_end, val_end, lookback, pred_len) -> dict
def finetune_tokenizer(dataset, output_dir, **hparams)
def finetune_predictor(dataset, tokenizer_path, output_dir, **hparams)
```

**Design choices:**
- Mirrors the Kronos repo's `finetune/` structure (`train_tokenizer.py`, `train_predictor.py`) but rewritten as importable functions, not CLI scripts, so Colab cells can call them.
- Aggressive checkpointing (every N steps) to survive Colab disconnects.
- Mixed-precision (fp16) training to fit Kronos-base on T4.

### `kth/backtest/walkforward.py` ⬜ planned

**Planned API:**
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
```

**Design choices:**
- Walk-forward, not in-sample. Each prediction uses only data up to that point.
- Strict no-look-ahead: signals on day `t` use data `<= t`, trade executes at day `t+1` open (not close, which is unrealistic).
- Per-asset friction applied on every position change.

### `kth/backtest/metrics.py` ⬜ planned

**Planned metrics:**
- CAGR, Sharpe (annualized), Sortino, Calmar
- Max drawdown, average drawdown duration
- Hit rate, payoff ratio
- Per-asset-class attribution

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

- `kth/data/universe.py` — 100-ticker universe (50 Thai, 17 US, 12 crypto, rest unchanged), FRICTION dict
- `kth/data/loader.py` — yfinance loader, Kronos-format conversion, parquet cache, quality checks
- `verify_data_layer.py` — 5 offline tests, all pass against synthetic data
- `notebooks/01_data_layer.ipynb` — Colab notebook for verifying real yfinance access
- `kth/models/kronos_wrapper.py` — KronosTH wrapper (zero-shot inference)
- `kth/models/finetune.py` — Dataset preparation, tokenizer caching, evaluate_model
- `kth/models/_kronos_bridge.py` — Import bridge for local Kronos repo
- `kth/backtest/walkforward.py` — Walk-forward backtest with benchmark comparison
- `kth/backtest/strategy.py` — Signal → position translation
- `kth/backtest/metrics.py` — Sharpe, MaxDD, Calmar, hit-rate, attribution
- `scripts/train_per_market.py` — SGDR fine-tuning (3 markets × 3 folds)
- `scripts/eval_holdout.py` — Holdout evaluation on 2025 data
- `scripts/compare_finetune.py` — Fine-tuned vs zero-shot backtest comparison
- `README.md` — project overview
- `requirements.txt` — minimal pinned deps
- `docs/user-manual.md` — full user manual with methodology, backtest results, and usage instructions

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

---

*Document version: 2026-05-21. Updated: universe 100 tickers, layers 3-4 built, open questions resolved.*
