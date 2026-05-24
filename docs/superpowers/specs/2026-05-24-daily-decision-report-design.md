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
  Cell 3: Build report DataFrame (22 columns, all tickers)
  Cell 4: Filter + sort + display per REPORT_MODE
  Cell 5: Disclaimers
```

No new files in `kth/`. No new scripts. All dependencies exist: `KronosTH`, `ForecastResult`, `UNIVERSE`, `FRICTION`, `BacktestResult`.

---

## 2. Cells

### Cell 0: Config

```python
import pandas as pd
from pathlib import Path
import shutil

REPORT_MODE = "morning"   # "morning" | "trader" | "quant"
MODEL_TYPE  = "zero-shot" # "zero-shot" | "fine-tuned"
REPORT_DATE = pd.Timestamp.now().strftime("%Y-%m-%d")

# Compute model slug once (used by Cells 2 and 3)
if MODEL_TYPE == "zero-shot":
    CACHE_SLUG = "NeoQuasar_Kronos-small"
else:
    CACHE_SLUG = "./checkpoints/us_equity/fold2/best".replace("/","_")
```

### Cell 1: Load Model

```python
if MODEL_TYPE == "zero-shot":
    th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
else:
    # FT mode: only forecast tickers the checkpoint was trained on
    # Per deployment decisions: us_equity fold 2 is the only FT candidate
    from kth.models.finetune import load_finetuned_checkpoint
    th = load_finetuned_checkpoint("./checkpoints/us_equity/fold2/best", device="cuda")
    FT_ONLY_CLASS = "us_equity"  # restricts ticker list in Cell 2
```

### Cell 2: Generate Forecasts

```python
today_dir = Path(f"data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}")
if today_dir.exists():
    shutil.rmtree(today_dir)

tickers = get_all_tickers()
if MODEL_TYPE == "fine-tuned":
    tickers = [t for t in tickers if get_ticker_class(t) == FT_ONLY_CLASS]
    print(f"FT mode: restricted to {FT_ONLY_CLASS} ({len(tickers)} tickers)")

precompute_forecasts(th, tickers,
    start_date=REPORT_DATE, end_date=REPORT_DATE,
    pred_len=20, n_samples=10, lookback=400)
print(f"Forecasts generated. Cache: data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}/")
```

### Cell 3: Build DataFrame

For each ticker with a cached forecast for `REPORT_DATE`:

```python
cache_dir = Path(f"data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}")

rows = []
skipped = []
for ticker in tickers:
    parquet_file = cache_dir / f"{ticker.replace('^','_').replace('=','_')}.parquet"
    if not parquet_file.exists():
        skipped.append(ticker)
        continue
    fc = pd.read_parquet(parquet_file)
    # fc columns: timestamps, p5, p25, p50, p75, p95, mean

    ticker_data = load_cached(ticker)  # load once, reuse
    current_close = float(ticker_data["close"].iloc[-1])
    hist_vol = float(ticker_data["close"].pct_change().tail(252).std())
    cls = get_ticker_class(ticker)
    bm = BACKTEST_METRICS.get(cls, {})
    frac = FRICTION.get(cls, {"commission_oneway":0,"slippage_oneway":0})
    friction_rt = frac["commission_oneway"]*2 + frac["slippage_oneway"]*2

    p50_close = float(fc["p50"].iloc[-1])
    p5_close  = float(fc["p5"].iloc[-1])
    p95_close = float(fc["p95"].iloc[-1])
    mean_close = float(fc["mean"].iloc[-1])

    exp_return = (p50_close - current_close) / current_close
    band_width = (p95_close - p5_close) / current_close

    rows.append({
        "ticker": ticker,
        "name": get_display_name(ticker),
        "class": cls,
        "current_close": current_close,
        "p5_close": p5_close,
        "p25_close": float(fc["p25"].iloc[-1]),
        "p50_close": p50_close,
        "p75_close": float(fc["p75"].iloc[-1]),
        "p95_close": p95_close,
        "mean_close": mean_close,
        "expected_return_p50": exp_return,
        "expected_return_mean": (mean_close - current_close) / current_close,
        "band_width": band_width,
        "confidence": "green" if band_width <= 0.10 else ("yellow" if band_width <= 0.30 else "red"),
        "direction": "up" if exp_return > 0 else "down",
        "hist_vol_1y": hist_vol,
        "risk_adj_return": exp_return / (hist_vol + 1e-6),
        "rank_score": exp_return / max(band_width, 0.001),
        "market_sharpe": bm.get("sharpe"),
        "market_cagr": bm.get("cagr"),
        "market_max_dd": bm.get("max_dd"),
        "friction_rt": friction_rt,
        "net_return": exp_return - friction_rt,
        "report_date": REPORT_DATE,
        "model": MODEL_TYPE,
    })

df = pd.DataFrame(rows)
print(f"{len(df)}/{len(tickers)} tickers forecasted, {len(skipped)} skipped")
if skipped:
    print(f"  Skipped: {skipped}")
```

### Cell 4: Display per Mode

Each mode selects a column subset and sort order from the same DataFrame:

| Mode | Columns | Sort | Filter |
|------|---------|------|--------|
| Morning | ticker, current_close, P50%, band, flag, rank, direction | rank_score desc (top 10) + rank_score asc (bottom 10) | Top/bottom 10 |
| Trader | +P95/P5%, market_sharpe, friction, net_return | net_return desc | All, grouped by class |
| Quant | +mean_return%, market_cagr, market_maxdd, hist_vol | class, risk_adj_return desc | All |

Confidence flags:
- 🟢 Green: band width ≤ 10%
- 🟡 Yellow: 10% < band width ≤ 30%
- 🔴 Red: band width > 30%

> Thresholds are initial first-pass calibration based on backtest band width distribution. Future: tie to per-class friction costs (green < 2× friction, yellow 2-5×, red >5×).

Rank score: `expected_return_p50 / max(band_width, 0.001)` — higher return with tighter bands ranks higher.

**All-red day fallback:** If median band_width > 30% (market turmoil — every ticker is uncertain), sort by `abs(expected_return_p50)` descending with a warning banner: `"High uncertainty day — sorting by return magnitude only."`

### Cell 5: Disclaimers

```
This is research output, not financial advice.
Kronos is a forecasting model — past performance is not indicative of future results.
All backtest metrics are from walk-forward evaluation on 2022-2024 data.
Survivorship bias: the universe includes only currently-listed tickers.
Forecasts generated at {REPORT_DATE} using {MODEL_TYPE} Kronos-small.
```

---

## 3. Review Fixes Incorporated (v2)

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | FT model loads single checkpoint, used on all tickers | Critical | FT mode restricted to trained class only (us_equity); per-market FT if needed later |
| 2 | Consensus column uncomputable from summary cache | Critical | Dropped from v1; doc notes sample paths not cached |
| 3 | Trail hit-rate needs mini-backtest infrastructure | Medium | Dropped from v1; doc notes as future enhancement |
| 4 | Rank score ÷ 0 when band_width = 0 | Critical | `max(band_width, 0.001)` guard |
| 5 | Morning view: long-only, no exit signals | Critical | Top 10 bullish + bottom 10 bearish |
| 6 | 0.0 ≠ N/A for untested backtest classes | Critical | Use `None`, display as `"—"` |
| 7 | All-red day degrades sort to random | Medium | Fallback: sort by abs(return), show warning banner |
| 8 | Cache directory path not explicit in Cell 3 | Medium | Build path from model slug; try/except for skipped tickers |
| 9 | P&L tracking from prior signals | Medium | Dropped from v1; doc notes as future enhancement |

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
    "thai_index":  {"sharpe": -0.63,"cagr": -0.0529,"max_dd": -0.2564},  # SET benchmark
    "etf_global":  {"sharpe": 0.44, "cagr": 0.0833, "max_dd": -0.2450},   # SPY proxy
    # Classes NOT yet backtested — show "—" in report
    "commodity":   {"sharpe": None, "cagr": None, "max_dd": None},
    "bond_proxy":  {"sharpe": None, "cagr": None, "max_dd": None},
    "reit":        {"sharpe": None, "cagr": None, "max_dd": None},
    "fx_macro":    {"sharpe": None, "cagr": None, "max_dd": None},
}
```

Classes with no backtest display metrics as `"—"` in the report (not `0.0`, which means "breakeven Sharpe").

---

## 5. Derived Fields (22 Columns)

| # | Column | Formula |
|---|--------|---------|
| 1-3 | Ticker, Name, Class | Universe lookup |
| 4 | Current Close | Load from parquet |
| 5-10 | P5/P25/P50/P75/P95/Mean close | Forecast cache |
| 11 | Expected Return (P50) | (P50_close − current_close) / current_close |
| 12 | Expected Return (Mean) | (mean_close − current_close) / current_close |
| 13 | Band Width | (P95_close − P5_close) / current_close |
| 14 | Confidence Flag | green ≤10%, yellow 10-30%, red >30% |
| 15 | Direction | ↑ if P50 > close, ↓ otherwise |
| 16 | Hist Vol (1Y) | rolling 252-day std of daily log returns |
| 17 | Risk-Adj Return | Expected Return / (Hist Vol + 1e-6) |
| 18 | Rank Score | Expected Return / max(Band Width, 0.001) |
| 19-21 | Market Sharpe/CAGR/MaxDD | From BACKTEST_METRICS |
| 22 | Friction (RT%) | From FRICTION: commission_oneway×2 + slippage_oneway×2 |
| 23 | Net Return | Expected Return − Friction |
| 24 | Report Date | REPORT_DATE |
| 25 | Model | MODEL_TYPE |

**Dropped from v1 (cache dependency):**
- Consensus (% of sample paths agreeing) — requires saving individual sample paths to cache
- Trail Hit-Rate (10-day direction accuracy) — requires mini-backtest infrastructure
- P&L tracking (prior signal returns) — requires historical forecast tracking

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
- `data/forecast_cache/{slug}/{date}/` — per-model forecast cache
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
