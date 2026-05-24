# Daily Decision Report — Design Spec (Layer 5)

> Scope: `notebooks/05_decision_report.ipynb` — daily forecast + signal report for all 100 tickers with 3 toggleable views. Zero new Python modules. All data sources already exist.

---

## 1. Architecture

Single notebook, single DataFrame as data contract, three presentation views:

```
REPORT_MODE = "morning"  # "morning" | "trader" | "quant"

  Cell 0: Config (MODEL_TYPE, REPORT_MODE, DATE)
  Cell 1: Load model (ZS or FT checkpoint)
  Cell 2: forecast_batch(100 tickers) → cache (idempotent, today invalidated)
  Cell 3: Build report DataFrame (28 columns, all tickers)
  Cell 4: Filter + sort + display per REPORT_MODE
  Cell 5: Disclaimers
```

No new files in `kth/`. No new scripts. All dependencies exist: `KronosTH`, `ForecastResult`, `UNIVERSE`, `FRICTION`, `BacktestResult`.

---

## 2. Cells

### Cell 0: Config

```python
REPORT_MODE = "morning"   # "morning" | "trader" | "quant"
MODEL_TYPE  = "zero-shot" # "zero-shot" | "fine-tuned"
REPORT_DATE = pd.Timestamp.now().strftime("%Y-%m-%d")
```

### Cell 1: Load Model

```python
if MODEL_TYPE == "zero-shot":
    th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
else:
    from kth.models.finetune import load_finetuned_checkpoint
    # Per-market — pick checkpoint per asset class or single checkpoint
    th = load_finetuned_checkpoint("./checkpoints/us_equity/fold2/best", device="cuda")
```

### Cell 2: Generate Forecasts

```python
# Invalidate today's cache (forecast uses latest data for lookback)
today_dir = Path(f"data/forecast_cache/NeoQuasar_Kronos-small/{REPORT_DATE}")
if today_dir.exists():
    shutil.rmtree(today_dir)

tickers = get_all_tickers()
precompute_forecasts(th, tickers,
    start_date=REPORT_DATE, end_date=REPORT_DATE,
    pred_len=20, n_samples=10, lookback=400)
```

### Cell 3: Build DataFrame

For each ticker with a cached forecast for `REPORT_DATE`:

- Load `{ticker}.parquet` from cache → extract P5/P25/P50/P75/P95/mean close columns
- Join with `UNIVERSE` metadata (class, display name, sector, friction)
- Join with backtest metrics per market (Sharpe, CAGR, Max DD)
- Compute derived fields (expected return, band width, confidence, rank score)

Output: one DataFrame with 28 columns, one row per ticker.

### Cell 4: Display per Mode

Each mode selects a column subset and sort order from the same DataFrame:

| Mode | Columns | Sort | Filters |
|------|---------|------|---------|
| Morning | 7 cols (ticker, class, P50%, band, flag, rank, dir) | Rank score desc | Top 20 visible |
| Trader | 10 cols (+ P95/P5%, consensus, Sharpe, friction, net return) | Consensus desc, net return desc | All, grouped by class |
| Quant | 11 cols (+ mean return, CAGR, Max DD, trailing hit-rate) | Class, trailing hit-rate desc | All |

Confidence flags:
- 🟢 Green: band width ≤ 10%
- 🟡 Yellow: 10% < band width ≤ 30%
- 🔴 Red: band width > 30%

Rank score: `P50_expected_return / band_width` — higher return with tighter bands ranks higher.

### Cell 5: Disclaimers

```
This is research output, not financial advice.
Kronos is a forecasting model — past performance is not indicative of future results.
All backtest metrics are from walk-forward evaluation on 2022-2024 data.
Survivorship bias: the universe includes only currently-listed tickers.
Forecasts generated at {REPORT_DATE} using {MODEL_TYPE} Kronos-small.
```

---

## 3. SE Review Fixes Incorporated

| # | Issue | Fix |
|---|-------|-----|
| 1 | Stale cache on re-run | Delete today's cache directory before forecast_batch (Cell 2) |
| 2 | Ticker failures | forecast_batch handles insufficient-history tickers internally; log skipped count |
| 3 | Model selection | `MODEL_TYPE` variable in Cell 0 (Cell 1) |
| 4 | 4-source join | pd.merge chain + `.map()` for per-class backtest metrics (Cell 3) |
| 5 | Missing forecast summary | Print `"{N}/{100} tickers forecasted, {skipped} skipped"` (Cell 4 header) |

---

## 4. Data Sources

| Data | Source | Join Key |
|------|--------|----------|
| Forecast (P5/P50/P95) | `data/forecast_cache/NeoQuasar_Kronos-small/{date}/{ticker}.parquet` | ticker |
| Universe metadata | `kth.data.universe.UNIVERSE` | ticker |
| Friction costs | `kth.data.universe.FRICTION` | asset_class |
| Backtest Sharpe/CAGR | Hardcoded from verified results | asset_class |
| Current close price | `kth.data.loader.load_cached(ticker)` | ticker |

Backtest metrics (hardcoded — verified 2022-2024 results):
```python
BACKTEST_METRICS = {
    "thai_equity": {"sharpe": 1.40, "cagr": 0.3144, "max_dd": -0.1797},
    "crypto":      {"sharpe": 0.52, "cagr": 0.1645, "max_dd": -0.6858},
    "us_equity":   {"sharpe": 0.97, "cagr": 0.3034, "max_dd": -0.4377},
    "thai_index":  {"sharpe": -0.63,"cagr": -0.0529, "max_dd": -0.2564},
    "etf_global":  {"sharpe": 0.44, "cagr": 0.0833, "max_dd": -0.2450},  # SPY proxy
    "commodity":   {"sharpe": 0.0,  "cagr": 0.0,    "max_dd": 0.0},
    "bond_proxy":  {"sharpe": 0.0,  "cagr": 0.0,    "max_dd": 0.0},
    "reit":        {"sharpe": 0.0,  "cagr": 0.0,    "max_dd": 0.0},
    "fx_macro":    {"sharpe": 0.0,  "cagr": 0.0,    "max_dd": 0.0},
}
```

Classes with no backtest (commodity, bond_proxy, reit, fx_macro) show metrics as `"N/A"` in the report.

---

## 5. Derived Fields (28 Columns)

| # | Column | Formula |
|---|--------|---------|
| 1-3 | Ticker, Name, Class | Universe lookup |
| 4 | Current Close | Load from parquet |
| 5-10 | P5/P25/P50/P75/P95/Mean close | Forecast cache |
| 11 | Expected Return (P50) | (P50_close − current_close) / current_close |
| 12 | Expected Return (Mean) | (mean_close − current_close) / current_close |
| 13 | P5/P95 Spread | (P95_close − P5_close) / current_close |
| 14 | Band Width | P95/P95 spread |
| 15 | Confidence Flag | green ≤10%, yellow 10-30%, red >30% |
| 16 | Direction | ↑ if P50 > close, ↓ otherwise |
| 17 | Consensus | % of 10 sample paths with same direction sign |
| 18 | Hist Vol (1Y) | rolling 252-day std of daily log returns |
| 19 | Risk-Adj Return | Expected Return / Hist Vol |
| 20 | Rank Score | Expected Return / Band Width |
| 21-23 | Market Sharpe/CAGR/MaxDD | From BACKTEST_METRICS |
| 24 | Friction (RT%) | From FRICTION: commission_oneway×2 + slippage_oneway×2 |
| 25 | Net Return | Expected Return − Friction |
| 26 | Last Forecast Date | REPORT_DATE |
| 27 | Model | MODEL_TYPE |
| 28 | Trail Hit-Rate (10d) | Direction accuracy over last 10 trading days |

---

## 6. Time Estimate

| Step | Time |
|------|------|
| Write notebook (6 cells) | 1.5 hrs |
| Test morning mode on GPU | 20 min |
| Test trader/quant modes | 10 min |
| Commit | 5 min |
| **Total** | **~2 hrs** |

---

## 7. Dependencies

- `kth/models/kronos_wrapper.py` — `KronosTH.forecast_batch()`
- `kth/backtest/walkforward.py` — `precompute_forecasts()` (idempotent cache)
- `kth/data/universe.py` — `UNIVERSE`, `FRICTION`, `get_all_tickers()`
- `kth/data/loader.py` — `load_cached()`
- `data/forecast_cache/NeoQuasar_Kronos-small/` — existing ZS forecast cache
- `data/raw/*.parquet` — 100 tickers cached data

---

## 8. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Single notebook, no new modules | Everything exists — just assemble |
| 2 | One DataFrame, three views | Build once, slice three ways — clean separation |
| 3 | `REPORT_MODE` + `MODEL_TYPE` cell variables | Toggle without code changes |
| 4 | Today's cache invalidated before forecast | Forecasts must use latest available close |
| 5 | Backtest metrics hardcoded | Verified results, don't change day-to-day |
| 6 | Classes without backtest show "N/A" | Honest about what we know vs don't know |

---

*Document version: 2026-05-24. Source: Layer 5 from remaining work items.*
