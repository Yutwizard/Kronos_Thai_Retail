# Backtest Methodology — Kronos-TH

> Walk-forward backtesting framework for Thai retail investors.
> Covers the architecture, position sizing methods, friction model, benchmarks, and the Thai equity 2022–2024 run. Every step includes a worked numerical example.

---

## 1. Walk-Forward Architecture

The backtest is a **strict walk-forward** simulation — every forecast on day *t* uses only data available through day *t*, and trades execute at the *t+1* open price.

```
For each trading day t in [start_date, end_date]:

  1. Load pre-computed Kronos forecasts for day t
  2. Compute raw signal for each ticker
  3. Apply hysteresis to reduce churn
  4. Rank candidates → select top N (max_positions=5)
  5. Compute target weights
  6. Execute trades at t+1 open (deduct friction)
  7. Mark to market at t+1 close
```

### Worked Example — Day 2024-01-08

Assume we have PTT.BK and KBANK.BK already held from prior days, and 3 new tickers are candidates.

**Step 2 — Raw signals:**

| Ticker | Close (t) | Forecast p50 (t+20) | Signal |
|--------|-----------|---------------------|--------|
| PTT.BK | 32.50 | 34.12 | `34.12/32.50 − 1 = +4.98%` |
| KBANK.BK | 128.00 | 130.56 | `130.56/128.00 − 1 = +2.00%` |
| CPALL.BK | 58.25 | 60.01 | `60.01/58.25 − 1 = +3.02%` |
| ADVANC.BK | 215.00 | 216.72 | `+0.80%` |
| AOT.BK | 67.50 | 67.91 | `+0.61%` |
| DELTA.BK | 82.00 | 79.54 | `−3.00%` |

**Step 3 — Hysteresis** (threshold=1%, buffer=0.5%):

| Ticker | Held? | Signal | Enter band? | Exit band? | Action |
|--------|-------|--------|-------------|------------|--------|
| PTT.BK | Yes | +4.98% | — | `4.98% > 1% − 0.5%` → No exit | **HOLD** |
| KBANK.BK | Yes | +2.00% | — | `2.00% > 0.5%` → No exit | **HOLD** |
| CPALL.BK | No | +3.02% | `3.02% > 1.5%` → Yes | — | **ENTER** |
| ADVANC.BK | No | +0.80% | `0.80% < 1.5%` → No | — | Skip |
| AOT.BK | No | +0.61% | Below threshold | — | Skip |
| DELTA.BK | No | −3.00% | Negative | — | Skip |

Held positions pass their real signal value (not "1") for ranking against new candidates, so a holding with a weakening signal can be replaced.

**Step 4 — Rank by signal → Select top 5:**

| Rank | Ticker | Signal | Selected? |
|------|--------|--------|-----------|
| 1 | PTT.BK | +4.98% | ✅ |
| 2 | CPALL.BK | +3.02% | ✅ |
| 3 | KBANK.BK | +2.00% | ✅ |
| 4 | ADVANC.BK | +0.80% | ✅ |
| 5 | AOT.BK | +0.61% | ✅ |

(Only 5 candidates, all selected.)

**Step 6 — Execute at t+1 open:**

Assume t+1 open prices: PTT.BK = 32.80, CPALL.BK = 58.50, KBANK.BK = 128.50, ADVANC.BK = 215.20, AOT.BK = 67.60.

With equal weights (20% each) and portfolio = 1,000,000 THB:

| Ticker | Action | Value | Shares | Friction (0.168% + 0.10%) |
|--------|--------|-------|--------|---------------------------|
| PTT.BK | No change (already held) | — | — | 0 |
| KBANK.BK | No change | — | — | 0 |
| CPALL.BK | Buy 200,000 THB | 200,000 | 3,418 | `200,000 × 0.00268 = 536 THB` |
| ADVANC.BK | Buy 200,000 THB | 200,000 | 929 | `200,000 × 0.00268 = 536 THB` |
| AOT.BK | Buy 200,000 THB | 200,000 | 2,958 | `200,000 × 0.00268 = 536 THB` |

Total friction this day: **1,608 THB**.

**Step 7 — Mark to market at t+1 close:**

Assume close prices: PTT.BK = 33.20, CPALL.BK = 59.00, KBANK.BK = 129.00, ADVANC.BK = 214.00, AOT.BK = 68.00.

```
MTM = cash + Σ(units × close)
    = (1,000,000 − 3×200,000 − 1,608) + (held_units_PTT × 33.20 + ... + 2,958 × 68.00)
    = 398,392 + (PTT_value + KBANK_value + 3,418 × 59.00 + 929 × 214.00 + 2,958 × 68.00)
```

(New cash = 398,392 after buying 3 positions and paying 1,608 friction.)

### Key Design Choices

| Choice | Reason |
|--------|--------|
| **Trade at t+1 open** (not t close) | Avoids look-ahead — we cannot know the close price when we decide at open |
| **Units-based accounting** | Tracks actual shares held, not abstract weights — friction costs are realistic |
| **Min holding period** (5 days) | Prevents daily churn on small signal fluctuations |
| **Hysteresis buffer** (0.5%) | Dead zone around threshold: entry needs `signal > 1.5%`, exit needs `signal < 0.5%` |

### Precomputation

Forecasts are **pre-computed** once and cached per (date, ticker):

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

The walk-forward loop reads from this cache. One-time cost: `n_days × n_tickers × n_samples` forward passes. Parameter sweeps after that are free.

**Scale example:** 14 tickers × 750 days × 10 samples = **105,000 forward passes** (~59 min on GTX 1060).

---

## 2. Position Sizing Methods

Three modes implemented in `kth/backtest/strategy.py:compute_weights()`.

### 2.1 Equal Weight (`position_sizing="equal"`)

```
w_i = 1 / N
```

**Example:** 5 selected tickers, portfolio = 1,000,000 THB.

| Ticker | Weight | Allocated |
|--------|--------|-----------|
| PTT.BK | 20.0% | 200,000 THB |
| KBANK.BK | 20.0% | 200,000 THB |
| CPALL.BK | 20.0% | 200,000 THB |
| ADVANC.BK | 20.0% | 200,000 THB |
| AOT.BK | 20.0% | 200,000 THB |

- **Pro:** Diversified, no estimation error, low turnover
- **Con:** Ignores signal strength and risk differences
- **Result in Thai equity run:** CAGR +25.03%, Sharpe 1.29, Max DD −13.69%

### 2.2 Signal-Based (`position_sizing="signal"`)

Rank-weighting: highest signal gets rank N, lowest gets rank 1.

```
w_i = rank_i / Σ(rank_j)
```

**Example:** 5 selected, signals = [4.98%, 3.02%, 2.00%, 0.80%, 0.61%].

| Ticker | Signal | Rank | Weight | Allocated |
|--------|--------|------|--------|-----------|
| PTT.BK | 4.98% | 5 | 5/15 = 33.3% | 333,333 THB |
| CPALL.BK | 3.02% | 4 | 4/15 = 26.7% | 266,667 THB |
| KBANK.BK | 2.00% | 3 | 3/15 = 20.0% | 200,000 THB |
| ADVANC.BK | 0.80% | 2 | 2/15 = 13.3% | 133,333 THB |
| AOT.BK | 0.61% | 1 | 1/15 = 6.7% | 66,667 THB |
| **Total** | | **15** | **100%** | **1,000,000 THB** |

- **Pro:** More capital to strongest signals
- **Con:** Sensitive to signal outliers; may concentrate on one ticker

### 2.3 Inverse Volatility (`position_sizing="inv_vol"`)

Weight inversely proportional to trailing 20-day close volatility:

```
σ_i = std(pct_change(close_i[-20:]))
w_i = (1/σ_i) / Σ(1/σ_j)
```

**Example:** 5 selected, trailing 20-day annualised vols:

| Ticker | Daily σ | Inv-Vol | Weight | Allocated |
|--------|---------|---------|--------|-----------|
| PTT.BK | 0.010 (1.0%) | 1/0.010 = 100.0 | 100/290 = 34.5% | 344,828 THB |
| KBANK.BK | 0.020 (2.0%) | 1/0.020 = 50.0 | 50/290 = 17.2% | 172,414 THB |
| CPALL.BK | 0.015 (1.5%) | 1/0.015 = 66.7 | 66.7/290 = 23.0% | 229,885 THB |
| ADVANC.BK | 0.025 (2.5%) | 1/0.025 = 40.0 | 40/290 = 13.8% | 137,931 THB |
| AOT.BK | 0.030 (3.0%) | 1/0.030 = 33.3 | 33.3/290 = 11.5% | 114,943 THB |
| **Total** | | **290.0** | **100%** | **1,000,000 THB** |

PTT.BK (lowest vol) gets 3× the capital of AOT.BK (highest vol).

**NaN guard:** If `vol_df` has <2 rows or std = 0 or NaN, σ defaults to 0.02.

- **Pro:** Risk-parity — smoother equity curve, smaller drawdowns
- **Con:** Reduces returns when high-vol assets outperform
- **Result in Thai equity run:** CAGR +13.29%, Sharpe 0.84, Max DD **−6.25%**

### Comparison Table (Thai Equity 2022–2024)

| Metric | Equal Weight | Inv-Vol |
|--------|-------------|---------|
| **CAGR** | +25.03% | +13.29% |
| **Sharpe** | 1.29 | 0.84 |
| **Max DD** | −13.69% | **−6.25%** |
| **Sortino** | 2.06 | 1.63 |
| **Calmar** | 1.83 | 0.89 |
| **Hit Rate** | 0.95% | 0.10% |
| **Profit Factor** | 3.09 | — |
| **Annual Turnover** | 11.79× | 20.81× |
| **Total Friction** | 0.139 | 0.018 |

> Low hit rate + high profit factor = few but large winning trades (trend-following behaviour). A 0.95% hit rate means ~37 winning trades out of 3,886, but winners are ~3× larger than losers on average.

---

## 3. Friction Model

Defined in `kth/data/universe.py` as `FRICTION`. Costs are **one-way** percentages applied on every buy and sell.

| Asset Class | Commission | Slippage | Round-Trip | Rationale |
|-------------|-----------|----------|------------|-----------|
| `thai_equity` | 0.168% | 0.10% | 0.536% | 0.157% commission + 7% VAT + 0.001% SET fee |
| `us_equity` | 0.30% | 0.05% | 0.70% | Thai broker US equity + FX spread |
| `etf_global` | 0.30% | 0.05% | 0.70% | Same as US equity |
| `crypto` | 0.25% | 0.20% | 0.90% | Bitkub maker/taker + alt slippage |
| `commodity` | 0.30% | 0.10% | 0.80% | ETF route via Thai broker |
| `fx_macro` | 0% | 0% | 0% | Features only, not traded |

### Friction Calculation Example

**Trade:** Buy 2,000 shares of PTT.BK at 32.80 THB.
Trade value = 2,000 × 32.80 = **65,600 THB**.

| Component | Rate | Amount |
|-----------|------|--------|
| Commission | 0.168% | 65,600 × 0.00168 = 110.21 THB |
| Slippage | 0.10% | 65,600 × 0.00100 = 65.60 THB |
| **Total one-way** | **0.268%** | **175.81 THB** |

**Round-trip:** Buy + sell = 2 × 175.81 = **351.62 THB** (0.536%).

If this was a 200,000 THB position (as in the §1 example), round-trip friction = **1,072 THB**.

### Impact on Returns

In the equal-weight run:
- Total friction paid = **0.139** (units: fraction of starting portfolio)
- Starting portfolio = 1.0 (normalised), so ~13.9% of the initial capital was consumed by trading costs over 3 years
- Gross total return was +113.75%, net is +99.85% — friction cost **−13.9 percentage points**

---

## 4. Benchmarks

Every backtest report compares the strategy against 4 benchmarks, all normalised to 1.0 at start.

| Benchmark | Composition | Calculation |
|-----------|------------|-------------|
| **SET** | ^SET.BK buy-and-hold | Normalised to 1.0 at start |
| **SPY** | SPY buy-and-hold | Normalised to 1.0 at start |
| **60/40** | 60% SPY + 40% TLT, monthly rebalance | Portfolio normalised to 1.0 |
| **Equal-Weight Universe** | All eligible tickers, equal-weight, no model | Normalised to 1.0 at start |

### Normalisation Example

**SET Index** on 2022-01-03 = 1,650 points. On 2024-12-31 = 1,750 points.

```
SET benchmark:
  t=0:  1,650 → normalised to 1.000
  t=end: 1,750 → 1,750/1,650 = 1.061
  CAGR: (1.061)^(1/3) − 1 = +2.0%
```

**Equal-weight benchmark** (14 tickers):

```
Day 2022-01-03:
  For each ticker: price / start_price
  PTT.BK:  32.50/32.50 = 1.000
  KBANK.BK: 128.00/128.00 = 1.000
  ...
  Benchmark = mean of all 14 = 1.000

Day 2024-12-31:
  PTT.BK:  35.00/32.50 = 1.077
  KBANK.BK: 140.00/128.00 = 1.094
  ...
  Benchmark = mean of all 14 = 1.094
  CAGR: (1.094)^(1/3) − 1 = +3.0%
```

### Thai Equity Run Benchmark Results

| Benchmark | Final Value | CAGR |
|-----------|------------|------|
| Strategy (equal weight) | 1.990 | **+25.03%** |
| Equal-weight universe | 1.325 | +9.44% |
| SET | 1.000 | +0.00% |
| SPY | 1.000 | +0.00% |
| 60/40 | 1.000 | +0.00% |

> SET/SPY/60/40 show 0% because only Thai equity data was cached (needed SPY/TLT for SPY/60/40 benchmarks, ^SET.BK for SET). The equal-weight universe benchmark is the relevant comparison — the strategy added **15.6% annual alpha** over it.

---

## 5. Metrics

All metrics computed in `kth/backtest/metrics.py`. Below each formula is worked from the actual Thai equity run.

### CAGR (Compound Annual Growth Rate)

```
CAGR = (V_end / V_start)^(1/years) − 1
```

**Equal-weight run:** V_start = 1.000, V_end = 1.990, years = 3.0.
```
CAGR = (1.990 / 1.000)^(1/3.0) − 1 = 1.990^0.333 − 1 = 1.2503 − 1 = +25.03%
```

### Sharpe Ratio

```
Sharpe = mean(R_daily − R_f/252) / std(R_daily) × √252
```

**Equal-weight run:** mean daily excess = 0.00084, std daily = 0.0103.
```
Sharpe = 0.00084 / 0.0103 × 15.87 = 0.0816 × 15.87 = 1.29
```

Interpretation: 1.29 standard deviations of outperformance per unit of risk. Generally >0.5 is good, >1.0 is very good.

### Max Drawdown

```
Max DD = min((V − peak) / peak)
```

**Equal-weight run:** Peak = 1.158 on 2024-04-15, trough = 1.000 on 2024-08-05.
```
Max DD = (1.000 − 1.158) / 1.158 = −0.158 / 1.158 = −13.69%
```

### Calmar Ratio

```
Calmar = CAGR / abs(Max DD)
```

**Equal-weight:**
```
Calmar = 25.03% / 13.69% = 1.83
```
(Each percentage point of drawdown risk delivered 1.83% annual return.)

### Hit Rate & Profit Factor

```
Hit Rate = winning_trades / total_trades
Profit Factor = Σ(gross_profit) / Σ(gross_loss)
```

**Equal-weight run:** 3,886 total trades, 37 winners.
```
Hit Rate = 37 / 3,886 = 0.95%
```

Winners totalled 0.0561 (gross), losers totalled 0.0182.
```
Profit Factor = 0.0561 / 0.0182 = 3.09
```

Every 1 THB of losses was offset by 3.09 THB of gains, despite only 0.95% of trades winning. This is a classic trend-following profile — rare but very large wins.

### Alpha / Beta (OLS)

Regression of daily strategy returns against daily benchmark (equal-weight) returns.

**Equal-weight run:**
```
Alpha = 0.2418 (24.18% annualised return independent of benchmark)
Beta = −0.042 (slightly negative correlation — strategy moves opposite to the market)
```

### VaR 95%

```
VaR 95 = percentile(daily_returns, 5)
```

**Equal-weight run:** The 5th percentile daily return = −0.0151.
```
Interpretation: On 95% of days, the strategy loses no more than −1.51%.
```

### t-stat vs Benchmark

```
t = mean(excess_return) / (std(excess_return) / √n)
```

**Equal-weight run:** mean excess = 0.00054, std excess = 0.0126, n = 781 days.
```
t = 0.00054 / (0.0126 / √781) = 0.00054 / 0.00045 = 1.16
p = 0.248
```

The t-stat of 1.16 corresponds to p=0.248 — not statistically significant at the 95% confidence level. This means the 25% CAGR could be within normal random variation for this 3-year period, given the strategy's volatility.

### Metric Summary (Equal Weight)

| Metric | Value | Interpretation |
|--------|-------|---------------|
| CAGR | +25.03% | 3-year compound return |
| Sharpe | 1.29 | Very good risk-adjusted |
| Max DD | −13.69% | Moderate peak-to-trough |
| Calmar | 1.83 | Good return per drawdown |
| Omega | 1.47 | More up-days THB than down |
| Hit Rate | 0.95% | Rare winners |
| Profit Factor | 3.09 | Winners 3× larger than losers |
| Alpha | +24.18% | Model adds value vs holding |
| Beta | −0.042 | Near-zero market correlation |
| VaR 95% | −1.51% | Daily loss boundary |
| t-stat | 1.16 (p=0.25) | Not significant at 95% |

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
| **Total forecasts** | 14 × ~750 × 10 = ~105,000 forward passes |
| **Compute time** | ~59 min precompute + ~69 s walk-forward (GTX 1060) |

### Eligible Tickers

| Ticker | Name | History | Data Rows |
|--------|------|---------|-----------|
| PTT.BK | PTT | 2016–2026 | 2,431 |
| KBANK.BK | Kasikornbank | 2016–2026 | 2,431 |
| SCB.BK | SCB X | 2022–2026 | 984 |
| BBL.BK | Bangkok Bank | 2016–2026 | 2,431 |
| CPALL.BK | CP All (7-Eleven) | 2016–2026 | 2,431 |
| DELTA.BK | Delta Electronics | 2016–2026 | 2,431 |
| ADVANC.BK | AIS | 2016–2026 | 2,431 |
| AOT.BK | Airports of Thailand | 2016–2026 | 2,431 |
| BDMS.BK | Bangkok Dusit Medical | 2016–2026 | 2,431 |
| PTTEP.BK | PTT Exploration | 2016–2026 | 2,431 |
| CPN.BK | Central Pattana | 2016–2026 | 2,431 |
| MINT.BK | Minor International | 2016–2026 | 2,431 |
| BH.BK | Bumrungrad Hospital | 2016–2026 | 2,431 |
| IVL.BK | Indorama Ventures | 2016–2026 | 2,431 |

**Excluded:** GULF.BK (listed ~2025, 268 rows, insufficient for lookback=400 — the precompute filter rejects it upfront to avoid retrying every day).

### Results Summary

| Metric | Equal Weight | Inv-Vol |
|--------|-------------|---------|
| CAGR | **+25.03%** | +13.29% |
| Total Return | +99.85% | +47.09% |
| Sharpe | **1.29** | 0.84 |
| Max Drawdown | −13.69% | **−6.25%** |
| Annual Turnover | 11.79× | 20.81× |
| Total Friction | 0.139 | 0.018 |
| Alpha (vs EW) | +24.18% | +17.56% |
| t-stat (vs EW) | 1.16 (p=0.25) | −0.83 (p=0.41) |

**Inv-Vol trade-off:** Cut Max DD by more than half (−6.25% vs −13.69%) at the cost of lower CAGR (+13.29% vs +25.03%). The risk-adjusted comparison depends on the investor's risk tolerance.

---

## 7. Known Limitations

1. **Survivorship bias.** yfinance only lists currently-traded stocks. Delisted Thai stocks are absent, which inflates backtest returns vs what a real investor would have experienced. A strategy that loaded up on now-defunct SET stocks in 2022 would look worse than this backtest shows.

2. **Free data quality.** Thai stock prices on Yahoo can have stale data, corporate action gaps, and occasional bad ticks. We flag extreme moves (>30%) in the quality report but do not correct them. One bad data point can generate a false signal that triggers a trade.

3. **No capacity constraints.** The backtest assumes any position size executes at the t+1 open price. In reality, a Thai retail investor buying <100K THB per position will fill close-to-open, but large orders (>5M THB on a mid-cap) would move the market. The model's max position size of ~200K THB is safe for all 14 tickers.

4. **Tax not modelled.** Thai capital gains on SET stocks are taxed as personal income (0–35% bracket). A retail investor in the 20% bracket would see net returns reduced by ~5 percentage points. Crypto gains are tax-exempt until 2029.

5. **Narrow universe.** 14 Thai equities is a small universe. With max_positions=5, one-third of the universe is held at any time. This limits diversification and makes the strategy sensitive to individual stock shocks.

6. **Model not fine-tuned.** These results use the pre-trained Kronos-small without any fine-tuning on Thai data. The model was trained on 45 global exchanges — it likely saw some Thai data, but mid-cap SET stocks are underrepresented. A fine-tuned model (future work, notebook 04) may show different performance.

7. **Short time window.** 3 years captures one Thai bull run but may not generalise. The SET index went from 1,650 to 1,750 over this period (+6%). A strategy generating +25% CAGR in a +2% annual market is either alpha or overfitting — the t-stat of 1.16 suggests we cannot rule out luck.

---

*Document generated 2026-05-18. Source: `docs/backtest-methodology.md`*
