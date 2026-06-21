# Kronos-TH

A Kronos-based forecasting and decision-support system for **Thai retail investors**, covering the full investable universe accessible from Thailand: SET stocks, US stocks/ETFs, crypto, gold, FX. Research-first (Colab notebooks), no UI.

Built on top of [Kronos](https://github.com/shiyu-coder/Kronos) — the open-source foundation model for financial K-line sequences.

---

## What this is, and what it isn't

**This is**:
- A pipeline for downloading **free daily OHLCV** across all asset classes a Thai retail investor can actually buy.
- A wrapper around the Kronos foundation model for zero-shot and fine-tuned forecasting on those assets.
- A backtester with **Thai-retail-realistic costs** (commissions, VAT, slippage) for every asset class.
- A research tool to ask "what does a forecasting model trained on global K-lines say about the things I can actually invest in from Thailand?"

**This is not**:
- An autotrader. We do not place orders.
- A licensed investment-advice product.
- A high-frequency anything. We are daily-bar only.
- A guaranteed money-maker. Forecast ≠ profit; raw signals always need a strategy and risk layer on top.

## The investable universe

Defined in `kth/data/universe.py`. 100 tickers across 9 asset classes:

| Class | Examples | Why included |
|---|---|---|
| `thai_equity` | PTT.BK, KBANK.BK, DELTA.BK… | Core SET holdings any Thai retail can buy |
| `thai_index` | ^SET.BK | Benchmark |
| `us_equity` | AAPL, NVDA, MSFT… | Fractional shares via DIME!, Liberator, Jitta etc. (legal since 2022) |
| `etf_global` | SPY, QQQ, VWO, VEA, FXI | Same brokers as US stocks |
| `commodity` | GLD, GC=F, SLV, USO | Gold is huge in Thai retail; GLD is cleanest daily price |
| `crypto` | BTC-USD, ETH-USD… | Bitkub/Binance TH; capital gains tax-exempt 2025–2029 |
| `bond_proxy` | TLT, IEF, HYG | Safe-haven / credit risk benchmarks |
| `reit` | VNQ, CPNREIT.BK | Property exposure |
| `fx_macro` | THB=X, DX-Y.NYB | Used as features, not investable |

**Explicitly excluded**: Thai mutual funds (no clean free API), TFEX derivatives (outside retail forecasting scope), individual bonds (illiquid retail secondary market).

## Project state

- ✅ **Data layer** (`kth/data/`): universe (100 tickers, 9 classes), yfinance loader, Kronos-format conversion, caching, quality checks.
- ✅ **Kronos model** (`kth/models/`): wrapper, bridge, finetune with SGDR training, checkpoint loader.
- ✅ **Backtest engine** (`kth/backtest/`): walk-forward with 4 benchmarks, friction costs, full metrics. PSR, equity curve alignment, and open_trades bugs fixed 2026-06-21 (stored numbers stale pending GPU re-run).
- ✅ **Backtest results**: Thai equity (CAGR +31%, Sharpe 1.40), US equity (+30%, 0.97), Crypto (+16%, 0.52).
- ✅ **Fine-tuning**: 9 models trained across 3 markets. None beat zero-shot. All deploy zero-shot.
- ✅ **Kaggle scheduled pipeline** (`kth/pipeline/`, `kth/io/`, `kaggle/`): unattended daily pipeline with 6 injectable seams, idempotent upserts, failure alerting. `run_pipeline.py --dry-run` for offline smoke tests.
- ✅ **Daily decision report** (`notebooks/05_decision_report.ipynb`): 3 toggleable views (morning/trader/quant), 22 columns, 100 tickers.
- ✅ **User manual** (`docs/user-manual.md` — text, `docs/user-manual.html` — interactive with charts): complete methodology, usage, cautions, and results.
- ✅ **Monthly walkthrough** (`docs/monthly-walkthrough.md` — text, `docs/monthly-walkthrough.html` — visual with timeline): 21-day simulation with real allocations, exits, and rebalancing.
- ✅ **Verification suite** (`verify_data_layer.py` 5 tests, `verify_fixes.py` 17 tests, `verify_kaggle_runtime.py` 19 tests): offline regression tests using synthetic data — all pass.
- ✅ **Backtest manifest** (`data/backtest_results/MANIFEST.md`): marks authoritative (n50) vs stale (pre-n50, invvol) runs.
- 🔨 **Google Suite dashboard** (`google_suite/`): Colab/Kaggle daily pipeline + Google Sheets data store + Apps Script web app. **Now with:** Trade Log inline edit/delete, Reset Capital modal, Signal Health banner, Position row colors, 60s auto-refresh. See [spec](docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md), [Kaggle pipeline spec](docs/superpowers/specs/2026-06-18-kaggle-scheduled-pipeline-design.md).

## Quick start

### Local

```bash
pip install -r requirements.txt
python verify_data_layer.py      # runs offline synthetic tests (5)
python verify_fixes.py           # review-fix regression tests (17)
python verify_kaggle_runtime.py  # Kaggle pipeline tests (19)
python run_pipeline.py --dry-run # full pipeline smoke test
```

### Colab

1. Open `notebooks/01_data_layer.ipynb` in Colab
2. Upload the `kth/` folder next to it
3. Run all cells

The notebook downloads ~10 years of daily OHLCV for all 100 tickers (~5–10 min total) and caches to `./data/raw/*.parquet`. Persist to Google Drive if you want it to survive runtime shutdown.

## Project layout

```
kronos-th/
├── kth/
│   ├── data/
│   │   ├── universe.py      # 100-ticker universe + per-class FRICTION costs
│   │   └── loader.py        # yfinance → Kronos schema, caching, quality checks
│   ├── io/                  # ✅ Kaggle runtime (2026-06-21)
│   │   └── kaggle_runtime.py  # SA auth, RuntimeConfig, injectable getter
│   ├── models/              # KronosTH wrapper + fine-tune
│   ├── backtest/            # walk-forward, metrics, strategy
│   ├── pipeline/            # ✅ Daily orchestration (2026-06-21)
│   │   └── daily.py         # run_daily_pipeline() — 6 injectable seams
│   └── trading/             # portfolio engine, trade_gen, paper trading
├── kaggle/                  # ✅ Kaggle scheduled pipeline (2026-06-21)
│   ├── build_kaggle_notebook.py  # Generates ≤5-cell notebook
│   └── kronos_kaggle_pipeline.ipynb  # Generated thin wrapper
├── google_suite/            # Google Suite dashboard (zero-cost, browser-based)
│   ├── SETUP_GUIDE.md       # click-by-step setup
│   ├── kronos_daily_pipeline.ipynb  # Colab notebook (backup runtime)
│   ├── migrate_to_sheets.py # one-time data migration
│   └── apps_script/
│       ├── Code.gs          # Apps Script backend (15 functions)
│       └── Index.html       # 5-tab web app SPA (Flask-parity)
├── scripts/
│   ├── dashboard.py         # Flask dashboard (local GPU option)
│   └── start_dashboard.sh   # one-command launcher: venv + data + pipeline + serve
├── notebooks/
│   └── 01_data_layer.ipynb  # Colab: verify real yfinance access
├── data/
│   ├── raw/                 # cached parquet files (one per ticker)
│   └── backtest_results/    # walk-forward results per run
│       └── MANIFEST.md      # authoritative vs stale runs
├── docs/
│   ├── superpowers/specs/   # approved design specs
│   └── superpowers/plans/   # implementation plans
├── verify_data_layer.py     # offline tests (5)
├── verify_fixes.py          # review-fix regression tests (17)
├── verify_kaggle_runtime.py # Kaggle pipeline tests (19)
├── run_pipeline.py          # thin entrypoint (--dry-run for offline smoke)
└── requirements.txt
```

## Honest caveats

1. **Kronos is a forecasting model, not an alpha machine.** The Kronos authors state explicitly: raw signals aren't a strategy. We add strategy + risk layers on top.
2. **Thai stocks may be out-of-distribution.** Kronos was pre-trained on 45 global exchanges. It probably saw some Thai data, but mid-cap SET stocks are less represented than US mega-caps. Fine-tuning on the Thai universe (notebook 04) is meant to close this gap.
3. **Backtests lie.** Even with realistic frictions baked in, survivorship bias, look-ahead, and regime shifts are everywhere. Treat backtest numbers as a sanity floor, not a forecast of future returns.
4. **Free data has limits.** yfinance is wonderful and free but rate-limited; intraday is restricted to last 60 days (which is why this project is daily-only — see earlier conversation). For production-grade Thai equity data you'd need a paid source like SET SMART or EOD Historical.
5. **Stored backtest numbers are stale.** The 2026-06-21 code review found critical statistical bugs (PSR formula, equity curve alignment, open_trades blending). Fixes are applied but stored `data/backtest_results/*/metrics.json` files were computed before these fixes. A GPU re-run is required. See `data/backtest_results/MANIFEST.md`.

## License

MIT, same as Kronos.
