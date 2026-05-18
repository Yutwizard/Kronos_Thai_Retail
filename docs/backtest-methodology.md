# Backtest Methodology — Kronos-TH

> Walk-forward backtesting framework for Thai retail investors.
> Covers the architecture, position sizing methods, friction model, benchmarks, and the Thai equity 2022–2024 run.

---

## 1. Walk-Forward Architecture

The backtest is a **strict walk-forward** simulation — every forecast on day *t* uses only data available through day *t*, and trades execute at the *t+1* open price.

```
For each trading day t in [start_date, end_date]:

  1. Load pre-computed Kronos forecasts for day t
     (skipped if forecast cached already — idempotent)

  2. Compute raw signal for each ticker:
       signal = (p50_close_predicted(t+pred_len) / close_actual(t)) - 1

  3. Apply hysteresis to reduce churn:
       - If already holding: only exit if signal < threshold - entry_buffer
       - If not holding: only enter if signal > threshold + entry_buffer

  4. Rank candidates by signal strength → select top N (max_positions=5)

  5. Compute target weights (equal / signal / inv_vol — see §2)

  6. Execute trades at t+1 open:
       - Close positions no longer in target
       - Open/adjust positions to target weights
       - Deduct friction costs per asset class

  7. Mark to market at t+1 close
```

### Key design choices

| Choice | Reason |
|--------|--------|
| **Trade at t+1 open** (not t close) | Avoids look-ahead — we cannot know the close price when we decide at open |
| **Units-based accounting** | Tracks actual shares held, not abstract weights — friction costs are realistic |
| **Min holding period** (5 days) | Prevents daily churn on small signal fluctuations |
| **Hysteresis buffer** (0.5%) | Dead zone around threshold to avoid flip-flopping |

### Precomputation

Forecasts are **pre-computed** once and cached per (date, ticker) in `data/forecast_cache/`:

```
data/forecast_cache/NeoQuasar_Kronos-small/
  ├── 2022-01-03/
  │   ├── AAPL.parquet       # summary: timestamps, p5, p25, p50, p75, p95, mean
  │   ├── AAPL_meta.json     # ticker, model_name, generated_at, lookback_end
  │   ├── MSFT.parquet
  │   └── ...
  ├── 2022-01-04/
  └── ...
```

The walk-forward loop reads from this cache — no re-forecasting needed per run. This makes parameter sweeps `O(1)` after the one-time `O(n_days × n_tickers)` precompute.

---

## 2. Position Sizing Methods

Three modes implemented in `kth/backtest/strategy.py:compute_weights()`.

### 2.1 Equal Weight (`position_sizing="equal"`)

Simple: `w_i = 1 / N` for each of the N selected tickers.

```
Example: 5 selected tickers → each gets 20%
```

- **Pro:** Diversified, no estimation error, low turnover
- **Con:** Ignores signal strength and risk differences
- **Result in Thai equity run:** CAGR +25.03%, Sharpe 1.29, Max DD -13.69%

### 2.2 Signal-Based (`position_sizing="signal"`)

Rank-weighting: highest signal gets rank N, lowest gets rank 1.

```
Example (5 selected, signals [0.03, 0.02, 0.015, 0.012, 0.01]):
  Ranks: [5, 4, 3, 2, 1], total = 15
  Weights: [33%, 27%, 20%, 13%, 7%]
```

- **Pro:** More capital to stronger signals
- **Con:** Sensitive to signal outliers; may concentrate on one ticker

### 2.3 Inverse Volatility (`position_sizing="inv_vol"`)

Weight inversely proportional to trailing 20-day close volatility:

```
w_i = (1 / σ_i) / Σ(1/σ_j)

where σ_i = std(pct_change(close_i[-20:]))
```

```
Example (std [0.01, 0.02, 0.015, 0.025, 0.03]):
  inv_vols: [100, 50, 67, 40, 33], total = 290
  Weights: [34%, 17%, 23%, 14%, 11%]
```

- **Pro:** Risk-parity — smoother equity curve, smaller drawdowns
- **Con:** Reduces returns when high-volatility assets outperform
- **Risk:** NaN-safe — if std is 0 or NaN, falls back to σ = 0.02
- **Result in Thai equity run:** CAGR +13.29%, Sharpe 0.84, Max DD **-6.25%**

### Comparison Table (Thai Equity 2022–2024)

| Metric | Equal Weight | Inv-Vol |
|--------|-------------|---------|
| **CAGR** | +25.03% | +13.29% |
| **Sharpe** | 1.29 | 0.84 |
| **Max DD** | -13.69% | **-6.25%** |
| **Sortino** | 2.06 | 1.63 |
| **Calmar** | 1.83 | 0.89 |
| **Hit Rate** | 0.95% | 0.10% |
| **Profit Factor** | 3.09 | — |
| **Annual Turnover** | 11.79x | 20.81x |
| **Total Friction** | 0.139 | 0.018 |

> Note: Low hit rate + high profit factor = few but large winning trades (trend-following behaviour typical of Kronos forecasts on Thai equities).

---

## 3. Friction Model

Defined in `kth/data/universe.py` as the `FRICTION` dict. Costs are **one-way** percentages applied on every buy and sell.

| Asset Class | Commission | Slippage | Round-Trip | Rationale |
|-------------|-----------|----------|------------|-----------|
| `thai_equity` | 0.168% | 0.10% | 0.536% | 0.157% commission + 7% VAT + 0.001% SET fee |
| `us_equity` | 0.30% | 0.05% | 0.70% | Thai broker US equity rates + FX spread |
| `etf_global` | 0.30% | 0.05% | 0.70% | Same as US equity |
| `crypto` | 0.25% | 0.20% | 0.90% | Bitkub maker/taker + slippage |
| `commodity` | 0.30% | 0.10% | 0.80% | ETF route via Thai broker |
| `fx_macro` | 0% | 0% | 0% | Features only, not traded |

Friction is tracked separately per trade and reported as **total friction paid** in the backtest output. The equity curve is shown both **gross** (before friction) and **net** (after friction).

---

## 4. Benchmarks

Every backtest report compares the strategy against 4 benchmarks:

| Benchmark | Composition | Calculation |
|-----------|------------|-------------|
| **SET** | ^SET.BK buy-and-hold | Normalized to 1.0 at start |
| **SPY** | SPY buy-and-hold | Normalized to 1.0 at start |
| **60/40** | 60% SPY + 40% TLT, monthly rebalance | Portfolio normalized to 1.0 |
| **Equal-Weight Universe** | All eligible tickers, equal-weight, no model | Normalized to 1.0 at start |

The equal-weight universe benchmark is the most relevant — it answers "did the model add value over just holding everything equally?"

---

## 5. Metrics

All metrics are computed in `kth/backtest/metrics.py`.

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| **CAGR** | `(V_end / V_start)^(1/years) - 1` | Annualised compound return |
| **Sharpe** | `(R_p - R_f) / σ_p × √252` | Risk-adjusted return (target > 0.5) |
| **Sortino** | `(R_p - R_f) / σ_d × √252` | Like Sharpe but only downside vol |
| **Max DD** | `min((V - peak) / peak)` | Worst peak-to-trough loss |
| **Calmar** | `CAGR / abs(Max DD)` | Return per unit of drawdown risk |
| **Omega** | `Σgains / abs(Σlosses)` | Total profit / total loss on daily returns |
| **Hit Rate** | `winning_trades / total_trades` | % of profitable trades |
| **Profit Factor** | `gross_profit / gross_loss` | Ratio of winning to losing trade total |
| **Alpha/Beta** | OLS regression vs equal-weight benchmark | Model's independent return vs market exposure |
| **VaR 95%** | 5th percentile of daily returns | Worst daily loss at 95% confidence |
| **t-stat** | `mean(excess) / (std(excess) / √n)` | Statistical significance vs benchmark |

---

## 6. Thai Equity Backtest (2022–2024) — Run Details

### Configuration

| Parameter | Value |
|-----------|-------|
| **Tickers** | 14 Thai equities (excl. GULF.BK — insufficient data) |
| **Period** | 2022-01-03 → 2024-12-31 (756 trading days) |
| **Lookback** | 400 days |
| **Prediction horizon** | 20 days |
| **Samples** | 10 per ticker per day |
| **Max positions** | 5 |
| **Long threshold** | 1% |
| **Entry buffer** | 0.5% |
| **Min holding days** | 5 |
| **Total forecasts** | 14 tickers × ~750 days × 10 samples = ~105,000 forward passes |
| **Compute time** | ~59 min precompute + 69 s walk-forward (GTX 1060, batched inference) |

### Eligible Tickers

| Ticker | Name | History |
|--------|------|---------|
| PTT.BK | PTT | 2016–2026 |
| KBANK.BK | Kasikornbank | 2016–2026 |
| SCB.BK | SCB X | 2022–2026 |
| BBL.BK | Bangkok Bank | 2016–2026 |
| CPALL.BK | CP All (7-Eleven) | 2016–2026 |
| DELTA.BK | Delta Electronics | 2016–2026 |
| ADVANC.BK | AIS (Telecom) | 2016–2026 |
| AOT.BK | Airports of Thailand | 2016–2026 |
| BDMS.BK | Bangkok Dusit Medical | 2016–2026 |
| PTTEP.BK | PTT Exploration | 2016–2026 |
| CPN.BK | Central Pattana | 2016–2026 |
| MINT.BK | Minor International | 2016–2026 |
| BH.BK | Bumrungrad Hospital | 2016–2026 |
| IVL.BK | Indorama Ventures | 2016–2026 |

Excluded: GULF.BK (listed 2025, only 268 rows, insufficient for lookback=400).

### Results Summary

| Metric | Equal Weight | Inv-Vol |
|--------|-------------|---------|
| CAGR | **+25.03%** | +13.29% |
| Total Return | +99.85% | +47.09% |
| Sharpe | **1.29** | 0.84 |
| Max Drawdown | -13.69% | **-6.25%** |
| Annual Turnover | 11.79x | 20.81x |
| Total Friction | 0.139 | 0.018 |
| Alpha (vs EW) | +24.18% | +17.56% |
| t-stat (vs EW) | 1.16 (p=0.25) | -0.83 (p=0.41) |

---

## 7. Known Limitations

1. **Survivorship bias.** yfinance only lists currently-traded stocks. Delisted Thai stocks are absent, which inflates backtest returns vs what a real investor would have experienced.

2. **Free data quality.** Thai stock prices on Yahoo can have stale data, corporate action gaps, and occasional bad ticks. We flag extreme moves (>30%) in the quality report but do not correct them.

3. **No capacity constraints.** The backtest assumes any position size is executable at the t+1 open price. In reality, a retail investor buying <100K THB per position will get filled at close-to-open, but very large positions would move the market.

4. **Tax not modelled.** Thai capital gains on SET stocks are personal-income-taxed (0–35% bracket). Crypto gains are tax-exempt until 2029. We do not deduct taxes from returns.

5. **Narrow universe.** 14 Thai equities is a small universe. A 5-position max means at any time, ⅓ of the universe is held. Diversification benefits are limited.

6. **Model not fine-tuned.** These results use the pre-trained Kronos-small model (NeoQuasar/Kronos-small) without any fine-tuning on Thai data. A fine-tuned model (future work, notebook 04) may show different performance.

---

*Document generated 2026-05-18. Source: `docs/backtest-methodology.md`*
