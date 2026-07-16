# Kronos-TH

A Kronos-based forecasting and decision-support system for **Thai retail investors**, covering SET-listed Thai equities and DR (Depositary Receipts) of major foreign stocks tradable on the SET in Thai baht. Research-first (Colab notebooks), no UI.

Built on top of [Kronos](https://github.com/shiyu-coder/Kronos) — the open-source foundation model for financial K-line sequences.

---

## What this is, and what it isn't

**This is**:
- A pipeline for downloading **free daily OHLCV** for SET-listed Thai equities and DR-tracked foreign underlyings.
- A wrapper around the Kronos foundation model for zero-shot forecasting on those assets.
- A backtester with **Thai-retail-realistic costs** (commissions, VAT, slippage).
- A research tool to ask "what does a forecasting model trained on global K-lines say about the things I can actually invest in from Thailand?"

**This is not**:
- An autotrader. We do not place orders.
- A licensed investment-advice product.
- A high-frequency anything. We are daily-bar only.
- A guaranteed money-maker. Forecast ≠ profit; raw signals always need a strategy and risk layer on top.

## The investable universe

Defined in `kth/data/universe.py`. 52 tickers across 2 asset classes:

| Class | Examples | Why included |
|---|---|---|
| `thai_equity` | PTT.BK, KBANK.BK, DELTA.BK, CPNREIT.BK… | Core SET holdings any Thai retail can buy (51 tickers, incl. CPNREIT.BK) |
| `thai_index` | ^SET.BK | Benchmark |

**Plus DR (Depositary Receipts)**: `kth_dr/` is a separate plugin package extending the universe via `register_asset_class()` — SET-listed DRs of major foreign stocks (e.g. Tencent, Toyota, ASML, Alibaba), forecast on their foreign underlying but traded/priced in THB on the SET. See `data/dr/README.md` for the verification workflow and `data/dr/mapping.json` for the current list.

**Explicitly excluded**: Thai mutual funds (no clean free API), TFEX derivatives (outside retail forecasting scope), individual bonds (illiquid retail secondary market).

**Archived 2026-07-16**: the project previously covered 9 asset classes (100 tickers), including `us_equity`, `etf_global`, `commodity`, `crypto`, `bond_proxy`, and `fx_macro`. Scope was narrowed to SET + DR; the original code, cached data, and backtest results for those classes live at `archive/other-asset-classes/`.

## Project state

> **⚠️ STALE NUMBERS:** Backtest results below were computed before the
> 2026-06-21 bug fixes (PSR formula, equity curve alignment, open_trades
> blending, FIFO lot ledger). A GPU re-run is required. Do NOT cite these
> numbers until the re-run completes. See `data/backtest_results/MANIFEST.md`.
>
> **Survivorship bias:** Cited CAGRs are overstated by ~1-3pp/yr. Adjust
> mentally: "31.4% gross → ~28-30% survivorship-adjusted."

- ✅ **Data layer** (`kth/data/`): universe (52 tickers, 2 classes) + DR plugin (`kth_dr/`), yfinance loader, Kronos-format conversion, caching, quality checks.
- ✅ **Kronos model** (`kth/models/`): wrapper, bridge, finetune with SGDR training, checkpoint loader.
- ✅ **Backtest engine** (`kth/backtest/`): walk-forward with benchmarks, friction costs, full metrics. PSR, equity curve alignment, and open_trades bugs fixed 2026-06-21 (stored numbers stale pending GPU re-run).
- ✅ **Backtest results**: Thai equity (CAGR +31%, Sharpe 1.40). US equity/crypto backtests archived — see `archive/other-asset-classes/data/backtest_results/`.
- ✅ **Fine-tuning**: thai_equity fine-tuning did not beat zero-shot; deploys zero-shot. (us_equity/crypto fine-tune results archived alongside their backtests — those classes are no longer in scope, not merely "staying zero-shot".)
- ✅ **DR integration** (`kth_dr/`): plugin extending the universe via `register_asset_class()`; discovery/verification workflow in `data/dr/README.md`, current verified list in `data/dr/mapping.json`.
- ✅ **Kaggle scheduled pipeline** (`kth/pipeline/`, `kth/io/`, `kaggle/`): unattended daily pipeline with 6 injectable seams, idempotent upserts, failure alerting. `run_pipeline.py --dry-run` for offline smoke tests.
- ✅ **Daily decision report** (`notebooks/05_decision_report.ipynb`): 3 toggleable views (morning/trader/quant), 22 columns.
- ✅ **User manual** (`docs/user-manual.md` — text, `docs/user-manual.html` — interactive with charts): complete methodology, usage, cautions, and results.
- ✅ **Monthly walkthrough** (`docs/monthly-walkthrough.md` — text, `docs/monthly-walkthrough.html` — visual with timeline): 21-day simulation with real allocations, exits, and rebalancing.
- ✅ **Verification suite** (`verify_data_layer.py` 5 tests, `verify_fixes.py` 25 tests, `verify_kaggle_runtime.py` 20 tests, `verify_dr.py` 40 tests): offline regression tests using synthetic data — all pass.
- ✅ **Backtest manifest** (`data/backtest_results/MANIFEST.md`): marks authoritative (n50) vs stale (pre-n50, invvol) runs.
- 🔨 **Google Suite dashboard** (`google_suite/`): Colab/Kaggle daily pipeline + Google Sheets data store + Apps Script web app. **Now with:** Trade Log inline edit/delete, Reset Capital modal, Signal Health banner, Position row colors, 60s auto-refresh. See [spec](docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md), [Kaggle pipeline spec](docs/superpowers/specs/2026-06-18-kaggle-scheduled-pipeline-design.md).

## Quick start

### Local

```bash
pip install -r requirements.txt
pip install -e .                 # makes kth AND kth_dr importable — re-run after every pull
python verify_data_layer.py      # runs offline synthetic tests (5)
python verify_fixes.py           # review-fix regression tests (25)
python verify_kaggle_runtime.py  # Kaggle pipeline tests (20)
python verify_dr.py              # DR integration tests (40)
python run_pipeline.py --dry-run # full pipeline smoke test
```

### Colab

1. Open `notebooks/01_data_layer.ipynb` in Colab
2. Upload the `kth/` folder next to it
3. Run all cells

The notebook downloads ~10 years of daily OHLCV for all 52 universe tickers plus DR/underlying/FX tickers (~5–10 min total) and caches to `./data/raw/*.parquet`. Persist to Google Drive if you want it to survive runtime shutdown.

## Project layout

```
kronos-th/
├── kth/
│   ├── data/
│   │   ├── universe.py      # 52-ticker SET universe + per-class FRICTION costs
│   │   └── loader.py        # yfinance → Kronos schema, caching, quality checks
│   ├── io/                  # ✅ Kaggle runtime (2026-06-21)
│   │   └── kaggle_runtime.py  # SA auth, RuntimeConfig, injectable getter
│   ├── models/              # KronosTH wrapper + fine-tune
│   ├── backtest/            # walk-forward, metrics, strategy
│   ├── pipeline/            # ✅ Daily orchestration (2026-06-21)
│   │   └── daily.py         # run_daily_pipeline() — 6 injectable seams
│   └── trading/             # portfolio engine, trade_gen, paper trading
├── kth_dr/                  # ✅ DR (Depositary Receipt) plugin (2026-07-12)
│   ├── universe_dr.py       # DR_MAP loading, get_dr_underlying_tickers()
│   ├── discover_drs.py      # seed list -> mapping.json
│   └── trade_gen_dr.py      # execution-ticker/price/name resolution
├── kaggle/                  # ✅ Kaggle scheduled pipeline (2026-06-21)
│   ├── build_kaggle_notebook.py  # Generates ≤5-cell notebook
│   └── kronos_kaggle_pipeline.ipynb  # Generated thin wrapper
├── google_suite/            # Google Suite dashboard (zero-cost, browser-based)
│   ├── kronos_daily_pipeline.ipynb  # Colab notebook (backup runtime)
│   ├── migrate_to_sheets.py # one-time data migration
│   └── apps_script/
│       ├── Code.gs          # Apps Script backend (15 functions)
│       └── Index.html       # 5-tab web app SPA (Flask-parity)
├── scripts/
│   ├── dashboard.py         # Flask dashboard (local GPU option)
│   └── start_dashboard.sh   # one-command launcher: venv + serve (data/forecasts generated on demand)
├── notebooks/
│   └── 01_data_layer.ipynb  # Colab: verify real yfinance access
├── data/
│   ├── raw/                 # cached parquet files (one per ticker)
│   ├── dr/                  # DR seed list, mapping.json, README (verification workflow)
│   └── backtest_results/    # walk-forward results per run
│       └── MANIFEST.md      # authoritative vs stale runs
├── archive/other-asset-classes/  # code/data/backtests for classes descoped 2026-07-16
├── docs/
│   ├── SETUP_GUIDE.md       # ✅ complete zero-to-dashboard setup (primary)
│   ├── getting-started.md   # Quick-start + manual options
│   ├── superpowers/specs/   # approved design specs
│   └── superpowers/plans/   # implementation plans
├── verify_data_layer.py     # offline tests (5)
├── verify_fixes.py          # review-fix regression tests (25)
├── verify_kaggle_runtime.py # Kaggle pipeline tests (20)
├── verify_dr.py             # DR integration tests (40)
├── run_pipeline.py          # thin entrypoint (--dry-run for offline smoke)
└── requirements.txt
```

## Honest caveats

1. **Kronos is a forecasting model, not an alpha machine.** The Kronos authors state explicitly: raw signals aren't a strategy. We add strategy + risk layers on top.
2. **Thai stocks may be out-of-distribution.** Kronos was pre-trained on 45 global exchanges. It probably saw some Thai data, but mid-cap SET stocks are less represented than US mega-caps. Fine-tuning on the Thai universe (notebook 04) is meant to close this gap.
3. **Backtests lie.** Even with realistic frictions baked in, survivorship bias, look-ahead, and regime shifts are everywhere. Treat backtest numbers as a sanity floor, not a forecast of future returns.
4. **Alpha is regime-conditional, not year-round.** This is a defensive tilt,
   not a stock-selection edge. The strategy structurally holds cash, so it
   outperforms in bear/flat SET regimes (2024, 2025) but underperforms in broad
   bull markets (2023, 2026-to-date). In a bull regime, expect BEAR allocation
   (5% deployed) until the regime shifts. Do not expect it to beat a bull market.
5. **Free data has limits.** yfinance is wonderful and free but rate-limited; intraday is restricted to last 60 days (which is why this project is daily-only — see earlier conversation). For production-grade Thai equity data you'd need a paid source like SET SMART or EOD Historical.
6. **Stored backtest numbers are stale.** The 2026-06-21 code review found critical statistical bugs (PSR formula, equity curve alignment, open_trades blending, FIFO lot ledger). Fixes are applied but stored `data/backtest_results/*/metrics.json` files were computed before these fixes. A GPU re-run is required. See `data/backtest_results/MANIFEST.md`.

## License

MIT, same as Kronos.
