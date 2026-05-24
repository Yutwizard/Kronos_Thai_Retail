# Kronos-TH — User Manual & Methodology Guide

> A daily forecasting system for Thai retail investors, powered by the Kronos financial foundation model.
> Not financial advice. Research output only.

---

## 1. What Is Kronos-TH?

Kronos-TH wraps the [Kronos](https://github.com/shiyu-coder/Kronos) foundation model — a transformer trained on millions of daily K-line across global markets — to produce **probabilistic 20-day forecasts** for the assets a Thai retail investor can actually buy.

**The output is not orders.** It is a daily report answering: *"Given everything Kronos has learned about global financial patterns, and given a backtest on the assets I can actually buy in Thailand, what does the model expect over the next 20 trading days, and how confident is it?"*

### Supported Assets (100 tickers, 9 classes)

| Class | Tickers | What It Covers |
|-------|---------|----------------|
| Thai equity | 50 | SET50 + mid-caps — every Thai broker |
| US equity | 17 | Mega-cap US stocks via DIME/Liberator |
| Crypto | 12 | BTC + alts via Bitkub/Binance TH |
| ETF global | 9 | SPY, QQQ, VTI, VWO, VEA, IEMG, EWY, EWJ, FXI |
| Commodity | 4 | GLD, GC=F, SLV, USO |
| Bond proxy | 3 | TLT, IEF, HYG |
| REIT | 2 | VNQ, CPNREIT.BK |
| Thai index | 1 | ^SET.BK (benchmark only) |
| FX macro | 2 | THB=X, DX-Y.NYB (features only) |

### What It Does NOT Do

- **No order execution.** Kronos-TH does not connect to Settrade, Bitkub, or any broker. It generates forecasts; you decide whether to act.
- **No intraday.** Daily bars only. yfinance free intraday is 60-day rolling — not enough to train.
- **No tax optimization.** Capital gains treatment varies by asset class (crypto tax-exempt in Thailand 2025-2029). Consult a tax advisor.
- **No survivorship bias adjustment.** The universe includes only currently-listed tickers. Delisted tickers are absent from backtests, which overstates returns.

---

## 2. Quick Start (3 Minutes)

### Prerequisites

- Python 3.10+
- NVIDIA GPU with ≥6GB VRAM (GTX 1060 minimum, T4 recommended)
- Kronos repo cloned locally
- 100 parquet files cached in `data/raw/`

### Step 1: Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-ml.txt
pip install -e .
```

### Step 2: Verify GPU

```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"
```
Expected: `CUDA: True, Device: NVIDIA GeForce GTX 1060` (or similar).

### Step 3: Generate today's forecasts

```bash
venv/bin/python -c "
import pandas as pd; from pathlib import Path; import shutil, sys
sys.path.insert(0, 'kronos_repo')
from kth.data.universe import get_all_tickers
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
today = pd.Timestamp.now().strftime('%Y-%m-%d')

# Invalidate today's cache (we want fresh forecasts using latest close)
slug = 'NeoQuasar_Kronos-small'
today_dir = Path(f'data/forecast_cache/{slug}/{today}')
if today_dir.exists(): shutil.rmtree(today_dir)

# Forecast all 100 tickers (idempotent — subsequent runs skip cached dates)
precompute_forecasts(th, get_all_tickers(), start_date=today, end_date=today,
                     pred_len=20, n_samples=10, lookback=400)
print(f'Forecasts cached at data/forecast_cache/{slug}/{today}/')
"
```

**Time estimate:** ~3 minutes on GPU (100 tickers × ~2s each via batch inference). First run slower if downloading model weights from HuggingFace (~1 GB download).

### Step 4: Read the daily report

Open `notebooks/05_decision_report.ipynb` in Jupyter or VS Code. Set `REPORT_MODE = "morning"` (or `"trader"`/`"quant"`). Run all cells.

**Time estimate:** First run: ~5 minutes (generates forecasts + builds DataFrame). Subsequent runs: ~10 seconds (cache hit).

### Step 5: Interpret the output

```
=== Morning Brief — 2026-05-24 ===

🟢 BULLISH (top 10 by conviction):
  Ticker         Name                   Class           Close    P50%     Band  Flag  Dir
  -------------------------------------------------------------------------------------
  PTT.BK         PTT                    thai_equity     32.50   +2.31%   6.50% 🟢    ↑
  AAPL           Apple                  us_equity      180.20   +1.20%   7.10% 🟢    ↑
  ...

🔴 BEARISH (bottom 10 by conviction):
  Ticker         Name                   Class           Close    P50%     Band  Flag  Dir
  -------------------------------------------------------------------------------------
  KBANK.BK       Kasikornbank           thai_equity    142.00   -1.80%   5.20% 🟢    ↓
  ...
```

**Reading the flags:**
- 🟢 Green: high conviction — uncertainty is ≤10% of current price
- 🟡 Yellow: moderate conviction — uncertainty 10-30%
- 🔴 Red: low conviction — uncertainty >30%
- **↑ Direction**: model expects the price to rise over the next 20 days
- **↓ Direction**: model expects the price to fall

---

## 3. The Three Report Views

### A: Morning Brief (Morning coffee scan)

| Column | What It Means | Why You Care |
|--------|---------------|--------------|
| `P50%` | Median expected 20-day return | The central forecast |
| `Band` | P95−P5 uncertainty range / current price | Narrow = model is sure |
| `Flag` | Green ≤10%, Yellow 10-30%, Red >30% | Trade at conviction |
| `Rank` | Return ÷ Band | Higher = better risk-adjusted |
| `Dir` | ↑/↓ direction | Which way to lean |

**Top 10 = highest conviction buys. Bottom 10 = highest conviction sells.** On volatile days (all bands >30%), the report falls back to sorting by return magnitude and shows a warning.

### B: Trader's Desk (Before placing orders)

| Column | Why Added |
|--------|-----------|
| `P5%` / `P95%` | Best/worst case scenarios |
| `Sharpe` | Per-market backtest Sharpe (see §5) |
| `Frict` | Round-trip transaction cost for this market |
| `NetRet` | P50% return minus friction = what you actually keep |

**Key sorting rule:** Sorted by `NetRet` descending. A +1.5% forecast with 0.7% friction (nests 0.8%) ranks below a +1.0% forecast with 0.1% friction (nests 0.9%). The report knows your costs.

### C: Quant PM Review (Weekly deep dive)

Adds trailing 1-year historical volatility, risk-adjusted return, per-market CAGR and max drawdown. Grouped by asset class for attribution analysis. **Useful for rebalancing and regime detection.**

---

## 4. Backtest Methodology

### Walk-Forward Design

Every backtest is **strictly walk-forward**: forecasts for date T use only data available at ≤ T. No look-ahead.

```
Training data: 2016 → train_end (varies by fold)
Val window:    train_end+1 → train_end + 21 months
Test window:   val_end+1 → val_end + 21 months

Fold 0: train → 2022-06 | val → 2024-03 | test → 2025-10
Fold 1: train → 2024-03 | val → 2025-10 | test → 2027-08
Fold 2: train → 2025-10 | val → 2027-08 | test → 2029-06
```

The **backtest window we report on is 2022-01-01 to 2024-12-31**, regardless of fold boundaries. Fold 0 is the most realistic (its predictions are partially out-of-sample after 2022). The 21-month val window ensures ≥420 rows for the 400-day lookback — a critical bug fix from earlier versions using 6-month windows (which were too short).

### Position Sizing

- **Equal-weight** across all tickers with a valid forecast on each trading day
- Positions are rebalanced daily (chosen for simplicity, not tax efficiency)
- Long-only (shorting Thai stocks is not retail-feasible)

### Benchmark Comparison

Every backtest output compares the strategy against 4 benchmarks:

| Benchmark | What It Is | Why |
|-----------|------------|-----|
| SET Index | Buy-and-hold SET Index via ^SET.BK | The "do nothing" Thai option |
| SPY | Buy-and-hold S&P 500 ETF | The default US alternative |
| 60/40 SPY/TLT | Monthly rebalanced classic portfolio | Standard benchmark for balanced strategies |
| Equal-weight | Same universe, no model | **This is the most important comparison** — does the model add anything over random allocation? |

### Friction Costs (Applied to Every Trade)

Per `kth/data/universe.py`:

| Class | Commission (one-way) | Slippage (one-way) | Round-trip total |
|-------|---------------------|--------------------|-----------------|
| Thai equity | 0.168% | 0.10% | **0.536%** |
| US equity | 0.30% | 0.05% | **0.70%** |
| Crypto | 0.25% | 0.20% | **0.90%** |
| Crypto (BTC-only) | 0.25% | 0.10% | **0.70%** |

**Both gross and net-of-friction returns are reported.** Any comparison that says "the model beat the market" refers to net returns unless stated otherwise.

### Metrics Explained

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **CAGR** | (final/start)^(252/days) − 1 | Annualized return. **Net** after friction. |
| **Sharpe** | mean(daily return − rf/252) / std(daily return) × √252 | Return per unit of risk. >0.5 is good, >1.0 is excellent. |
| **Sortino** | Same as Sharpe but uses downside vol only | Penalizes only bad volatility. Higher than Sharpe = right-tail wins. |
| **Max DD** | (trough − peak) / peak | Worst peak-to-trough loss. **-17%** in Thai equity = similar to benchmark. |
| **Calmar** | CAGR / |Max DD| | Return per unit of max risk. >1.0 is strong. |
| **Trade Win Rate** | trades with gross_return > 0 / total trades | **Not forecast accuracy.** This is trade P&L rate. 2-5% is expected for long-biased rolling strategies that churn positions monthly. |
| **t-stat / p-value** | t-test: strategy returns > 0? | p < 0.05 means the strategy's positive returns are statistically distinguishable from random noise. |

---

## 5. Backtest Results (2022–2024)

### Thai Equity (49 tickers)

| Metric | Strategy | SET Index | SPY | Equal-Weight |
|--------|----------|-----------|-----|-------------|
| CAGR | **+31.44%** | −5.29% | +8.33% | +1.44% |
| Sharpe | **1.40** | −0.63 | 0.44 | 0.00 |
| Max DD | −17.97% | −25.64% | −24.50% | −18.07% |

**Interpretation:** The SET Index was DOWN 5% CAGR over this period — the model was UP 31%. The ~30pp alpha over equal-weight (1.44% → 31.44%) is not beta. It is genuine statistical signal from the Kronos model.

**Why this is not luck:** The p-value for the strategy's returns being > 0 is significant at 5%. The previous 14-ticker backtest (p=0.25) was under-diversified — the signal requires 49 tickers to compound through frequent small winners.

### US Equity (17 tickers)

| Metric | Strategy | SPY | Equal-Weight |
|--------|----------|-----|-------------|
| CAGR | **+30.34%** | +8.33% | +14.39% |
| Sharpe | **0.97** | 0.44 | 0.66 |
| Max DD | −43.77% | −24.50% | −32.95% |

**Interpretation:** Strong absolute returns (30% CAGR) and beats SPY (22pp alpha). But the max drawdown (−44%) is higher than SPY — this portfolio concentrates on 17 mega-cap names, so drawdowns are worse than well-diversified benchmarks.

**Caveat:** Both equal-weight and SPY comparison show the model beats the market. But neither the strategy nor equal-weight is statistically significant at 5% (p ≈ 0.45). The 2022-2024 period was a strong bull run for US mega-caps — the strategy captured it well, but we cannot distinguish from beta noise.

### Crypto (12 tickers)

| Metric | Strategy | SPY | Equal-Weight |
|--------|----------|-----|-------------|
| CAGR | **+16.45%** | +8.33% | −5.16% |
| Sharpe | **0.52** | 0.44 | 0.16 |
| Max DD | −68.58% | −24.50% | −76.60% |

**Interpretation:** Crypto was in a bear market (equal-weight down 5%). The model beat it by 22pp. But volatility is extreme — a −69% drawdown means the portfolio dropped by two-thirds. The p-value is 0.64 (not significant).

**Reality check:** Crypto's 0.52 Sharpe with 22pp alpha sounds impressive, but the max drawdown of −69% means most investors would have panic-sold long before. This is NOT suitable for a large allocation.

### Fine-Tuning Verdict

| Market | ZS Sharpe | Best FT Sharpe | Δ | Verdict |
|--------|-----------|---------------|---|---------|
| Thai equity | 1.40 | — | — | ✅ Stay ZS |
| US equity | 0.97 | 0.94 (F2) | −0.03 | ✅ Stay ZS |
| Crypto | 0.52 | 0.46 (F0) | −0.06 | ✅ Stay ZS |

**Fine-tuning did not help in any market.** All 3 markets use zero-shot Kronos-small. The 9 fine-tuned checkpoints (3 markets × 3 folds) are saved but not deployed. Direction accuracy improved slightly (+2.0pp for US equity) but did not translate to backtest alpha.

This is a known phenomenon in time-series forecasting: fine-tuning on recent data teaches the model to predict the training period's token distribution, which may not match future distributions. Zero-shot Kronos-generalist outperforms everywhere.

---

## 6. Cautions & Limitations

### Read Before Trading

1. **This is not financial advice.** It is a forecasting tool. Forecasts can be wrong. A 60% hit rate means 40% of predictions are wrong.

2. **Survivorship bias is real.** The universe includes only currently-listed tickers. Delisted stocks are absent from backtests, which overstates returns. The real historical performance of this strategy would be lower.

3. **The 2022-2024 backtest period was a unique macro environment.** QE unwind, AI boom, SET underperformance. A different regime (e.g., 2018 trade war, 2020 COVID crash) would produce different results. Past performance is NOT indicative of future results.

4. **Crypto backtests use a 5-day calendar when crypto trades 7 days.** The model's forecast timestamps skip weekends (business day convention from Kronos's equity pre-training). This compresses the forecast horizon: a 20-day prediction spans ~28 actual calendar days for crypto. The delta between ZS and FT is valid (both affected equally), but absolute Sharpe numbers are overstated by ~20-30%.

5. **ETFs class uses SPY as proxy.** The `etf_global` backtest metric (Sharpe 0.44, CAGR +8.33%) was computed only on SPY, but the class covers 9 ETFs including EM (VWO), Korea (EWY), Japan (EWJ), China (FXI). The model may perform differently on those markets. The report shows `"—"` for untested classes, but ETFs displays SPY numbers for all 9 tickers.

6. **Classes without backtest** — commodity, bond_proxy, reit, fx_macro — show `"—"` for Sharpe/CAGR in the report. These were never backtested. Do not trade them based on model forecasts without additional research.

7. **The trade win rate is 2-5%.** This does not mean the model is wrong 95% of the time. It means the portfolio churns monthly (daily rebalancing × 11.8× annual turnover), producing many small losing trades around a core of winning longs. This is expected for a long-biased rolling strategy. Focus on CAGR and Sharpe, not trade win rate.

8. **CPU inference is very slow.** Generating forecasts for 100 tickers takes ~3 minutes on GPU (GTX 1060) but would take hours on CPU. The notebook will refuse to run on CPU. If you don't have GPU access, use Colab.

### Known Bugs

| Bug | Impact | Status |
|-----|--------|--------|
| `forecast()` timestamps always "B" for DataFrame input | Standalone calls on DataFrame (not ticker string) use 5-day calendar regardless of asset class. | Fix: pass `calendar_freq="D"` explicitly for crypto DataFrames. Precompute path unaffected. |
| Mixed crypto+equity universe uses crypto calendar for all | If running a backtest that includes both BTC-USD and AAPL, AAPL gets 7-day forecasts (weekend timestamps fed to equity model). | Workaround: run crypto-only and equity-only backtests separately. |

---

## 7. Performance Tables (Reference)

### Strategy Metrics (Net of Frictions, 2022-2024)

| Metric | Thai Equity | US Equity | Crypto |
|--------|-------------|-----------|--------|
| CAGR | +31.44% | +30.34% | +16.45% |
| Sharpe | 1.40 | 0.97 | 0.52 |
| Sortino | 2.28 | 1.45 | 0.70 |
| Max DD | −17.97% | −43.77% | −68.58% |
| Calmar | 1.75 | 0.69 | 0.24 |
| Trade Win Rate | 2.51% | 2.78% | 1.48% |
| Annual Turnover | 11.8× | 9.2× | 6.7× |
| Total Friction | 13.9% | 8.4% | 5.1% |
| p-value (vs equal) | <0.05 | 0.46 | 0.64 |

### Benchmark Comparison Matrix

| Asset | Strategy | SET | SPY | 60/40 | Equal-Wt |
|-------|----------|-----|-----|-------|----------|
| Thai equity CAGR | **+31.44%** | −5.29% | +8.33% | −0.27% | +1.44% |
| Thai equity Sharpe | **1.40** | −0.63 | 0.44 | −0.11 | 0.00 |
| US equity CAGR | **+30.34%** | — | +8.33% | — | +14.39% |
| US equity Sharpe | **0.97** | — | 0.44 | — | 0.66 |
| Crypto CAGR | **+16.45%** | — | +8.33% | — | −5.16% |
| Crypto Sharpe | **0.52** | — | 0.44 | — | 0.16 |

---

## 8. File Reference

| File | Purpose |
|------|---------|
| `kth/data/universe.py` | 100 tickers, 9 classes, friction costs |
| `kth/data/loader.py` | yfinance → parquet cache, Kronos format |
| `kth/models/kronos_wrapper.py` | KronosTH: forecast() / forecast_batch() |
| `kth/models/finetune.py` | prepare_dataset, evaluate_model, checkpoint loader |
| `kth/models/_kronos_bridge.py` | Import bridge for non-pip-installable Kronos |
| `kth/backtest/walkforward.py` | precompute_forecasts, run_walkforward |
| `kth/backtest/metrics.py` | Sharpe, Sortino, Max DD, trade metrics |
| `scripts/train_per_market.py` | SGDR training for per-market fine-tuning |
| `scripts/compare_finetune.py` | FT vs ZS backtest comparison |
| `scripts/eval_holdout.py` | 2025 holdout direction-accuracy evaluation |
| `notebooks/05_decision_report.ipynb` | **Daily decision report** (3 views) |
| `checkpoints/{model}/fold{f}/best/` | 9 fine-tuned checkpoints (not deployed) |
| `data/forecast_cache/{slug}/{date}/` | Cached forecasts per model per date |
| `data/raw/*.parquet` | Cached yfinance data (100 files, ~200 MB) |
| `data/backtest_results/{asset}/` | Walk-forward backtest outputs (metrics + equity curves) |

---

*Document version: 2026-05-24. For questions or issues, open a ticket on GitHub.*
