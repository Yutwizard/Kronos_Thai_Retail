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

Defined in `kth/data/universe.py`. 51 tickers across 9 asset classes:

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

- ✅ **Data layer** (`kth/data/`): universe, yfinance loader, Kronos-format conversion, caching, quality checks. Verified end-to-end on synthetic data; Colab notebook ready to verify against real Yahoo Finance.
- ⬜ Zero-shot Kronos inference (notebook 02)
- ⬜ Walk-forward backtester with Thai-retail frictions (notebook 03)
- ⬜ Fine-tuning Kronos-small on Colab T4 (notebook 04)
- ⬜ Daily decision report (notebook 05)

## Quick start

### Local

```bash
pip install -r requirements.txt
python verify_data_layer.py     # runs offline synthetic tests
```

### Colab

1. Open `notebooks/01_data_layer.ipynb` in Colab
2. Upload the `kth/` folder next to it
3. Run all cells

The notebook downloads ~10 years of daily OHLCV for all 51 tickers (~5–10 min total) and caches to `./data/raw/*.parquet`. Persist to Google Drive if you want it to survive runtime shutdown.

## Project layout

```
kronos-th/
├── kth/
│   └── data/
│       ├── universe.py      # 51-ticker universe + per-class FRICTION costs
│       └── loader.py        # yfinance → Kronos schema, caching, quality checks
├── notebooks/
│   └── 01_data_layer.ipynb  # Colab: verify real yfinance access
├── data/
│   ├── raw/                 # cached parquet files (one per ticker)
│   └── processed/           # train/val/test splits (later)
├── configs/                 # YAML configs for fine-tuning (later)
├── verify_data_layer.py     # offline test runner
└── requirements.txt
```

## Honest caveats

1. **Kronos is a forecasting model, not an alpha machine.** The Kronos authors state explicitly: raw signals aren't a strategy. We add strategy + risk layers on top.
2. **Thai stocks may be out-of-distribution.** Kronos was pre-trained on 45 global exchanges. It probably saw some Thai data, but mid-cap SET stocks are less represented than US mega-caps. Fine-tuning on the Thai universe (notebook 04) is meant to close this gap.
3. **Backtests lie.** Even with realistic frictions baked in, survivorship bias, look-ahead, and regime shifts are everywhere. Treat backtest numbers as a sanity floor, not a forecast of future returns.
4. **Free data has limits.** yfinance is wonderful and free but rate-limited; intraday is restricted to last 60 days (which is why this project is daily-only — see earlier conversation). For production-grade Thai equity data you'd need a paid source like SET SMART or EOD Historical.

## License

MIT, same as Kronos.
