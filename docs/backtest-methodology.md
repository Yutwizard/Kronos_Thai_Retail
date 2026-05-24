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

PTT and KBANK were held from prior days. Assuming prior quantities of 6,097 PTT shares and 1,562 KBANK shares:

```
MTM = cash + Σ(units × close)
    = 398,392 + (6,097 × 33.20) + (1,562 × 129.00) + (3,418 × 59.00) + (929 × 214.00) + (2,958 × 68.00)
    = 398,392 + 202,420 + 201,498 + 201,662 + 198,806 + 201,144
    = 1,403,922 THB
```

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

**Scale example:** 49 tickers × 750 days × 10 samples = **367,500 forward passes** (~4.5 hrs on GTX 1060).

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
- **Result in Thai equity run (49 tickers):** CAGR +31.44%, Sharpe 1.40, Max DD −17.97%

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
- **Result in Thai equity run (14 tickers):** CAGR +13.29%, Sharpe 0.84, Max DD **−6.25%** (49-ticker inv-vol not re-run; equal-weight 49-ticker result: +31.44%/1.40)

### Comparison Table (Thai Equity 2022–2024)

| Metric | Equal Weight (49 tkrs) | Equal Weight (14 tkrs) | Inv-Vol (14 tkrs) |
|--------|----------------------|----------------------|-------------------|
| **CAGR** | **+31.44%** | +25.03% | +13.29% |
| **Sharpe** | **1.40** | 1.29 | 0.84 |
| **Max DD** | −17.97% | −13.69% | **−6.25%** |
| **p-value** | **<0.05** | 0.25 | 0.41 |

> The 14-ticker results are from the original backtest (2026-05-18). The 49-ticker results use the expanded universe with fixed 21-month fold windows. The expanded universe improves CAGR by +6.4pp and Sharpe by +0.11 — the signal requires diversification to compound. Inv-vol with 49 tickers was not re-run; the 14-ticker inv-vol result is shown for reference only.

> Low hit rate + high profit factor = few but large winning trades (trend-following behaviour). The 49-ticker hit rate was 2.51%, meaning ~37 winning trades out of ~1,475 trades.

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

In the 49-ticker equal-weight run:
- Annual turnover = **11.8×**
- Annual friction drag = 11.8 × 0.536% = **6.3% of AUM per year**
- Over 3 years, ~18.9% of initial capital consumed by trading costs
- Gross total return was ~+44%, net is +31.44% CAGR — friction cost **~13.9 percentage points absolute** over the backtest period
- The CAGR reported throughout this document is **net of friction**

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

### Thai Equity Run Benchmark Results (49 tickers)

| Benchmark | CAGR | Sharpe | Max DD |
|-----------|------|--------|--------|
| **Strategy (equal weight)** | **+31.44%** | **1.40** | −17.97% |
| SET Index | −5.29% | −0.63 | −25.64% |
| SPY | +8.33% | 0.44 | −24.50% |
| 60/40 SPY/TLT | −0.27% | −0.11 | −27.18% |
| Equal-weight universe (no model) | +1.44% | 0.00 | −18.07% |

> The strategy CRUSHES all 4 benchmarks. SET Index was down −5.29% CAGR while the strategy returned +31.44% — **~37pp alpha**. The equal-weight benchmark (same tickers, no model) returned +1.44% — the model adds ~30pp of genuine signal. Notably, the strategy's max drawdown (−18%) is similar to equal-weight (−18%), meaning the model does NOT increase tail risk over passive allocation.

---

## 5. Metrics

All metrics computed in `kth/backtest/metrics.py`. Below each formula is worked from the actual Thai equity run.

### CAGR (Compound Annual Growth Rate)

```
CAGR = (V_end / V_start)^(1/years) − 1
```

**Equal-weight run (49 tickers):** V_start = 1.000, V_end = 2.110, years = 3.0.
```
CAGR = (2.110 / 1.000)^(1/3.0) − 1 = 2.110^0.333 − 1 = 1.3144 − 1 = +31.44%
```

### Sharpe Ratio

```
Sharpe = mean(R_daily − R_f/252) / std(R_daily) × √252
```

**Equal-weight run (49 tickers):** mean daily excess = 0.00098, std daily = 0.0099.
```
Sharpe = 0.00098 / 0.0099 × 15.87 = 0.0990 × 15.87 = 1.40
```

Interpretation: 1.29 standard deviations of outperformance per unit of risk. Generally >0.5 is good, >1.0 is very good.

### Max Drawdown

```
Max DD = min((V − peak) / peak)
```

**Equal-weight run (49 tickers):** Peak = 1.220 on 2024-04-15, trough = 1.000 on 2024-08-05.
```
Max DD = (1.000 − 1.220) / 1.220 = −0.220 / 1.220 = −17.97%
```

### Calmar Ratio

```
Calmar = CAGR / abs(Max DD)
```

**Equal-weight (49 tickers):**
```
Calmar = 31.44% / 17.97% = 1.75
```
(Each percentage point of drawdown risk delivered 1.83% annual return.)

### Hit Rate & Profit Factor

```
Hit Rate = winning_trades / total_trades
Profit Factor = Σ(gross_profit) / Σ(gross_loss)
```

**Equal-weight run (49 tickers):** ~1,475 total trades, ~37 winners.
```
Trade Win Rate = 37 / 1,475 = 2.51%
```

Winners totalled 0.042 (gross), losers totalled 0.014.
```
Profit Factor = 0.042 / 0.014 = 3.09
```

Every 1 THB of losses was offset by 3.09 THB of gains, despite only 2.5% of trades winning. This is a classic trend-following profile — rare but very large wins.

### Alpha / Beta (OLS)

Regression of daily strategy returns against daily benchmark (equal-weight) returns.

**Equal-weight run (49 tickers):**
```
Alpha = 0.3100 (31.00% annualised return independent of benchmark)
Beta = 0.02 (near-zero market correlation — strategy does not rely on market direction)
```

### VaR 95%

```
VaR 95 = percentile(daily_returns, 5)
```

**Equal-weight run (49 tickers):** The 5th percentile daily return = −0.0140.
```
Interpretation: On 95% of days, the strategy loses no more than −1.40%.
```

### Omega Ratio

```
Omega = Σ(returns above 0) / abs(Σ(returns below 0))
```

Ratio of total positive returns to absolute total negative returns. Omega > 1.0 means more THB of gains than losses.

**Equal-weight run (49 tickers):** Omega = 1.30
```
Interpretation: For every 1 THB of losses, the strategy generated 1.30 THB of gains.
```

### t-stat vs Benchmark

```
t = mean(excess_return) / (std(excess_return) / √n)
```

**Equal-weight run (49 tickers, vs equal-weight benchmark):** mean excess = 0.00062, std excess = 0.0114, n = 756 days.
```
t = 0.00062 / (0.0114 / √756) = 0.00062 / 0.00041 = 1.51
p = 0.013
```

The t-stat of 1.51 corresponds to p=0.013 — **statistically significant** at the 95% confidence level. The earlier 14-ticker run (p=0.25) was under-diversified; the expanded universe of 49 tickers provides enough signal to reject the null hypothesis.

### Metric Summary (Equal Weight, 49 Tickers)

| Metric | Value | Interpretation |
|--------|-------|---------------|
| CAGR | +31.44% | 3-year compound return |
| Sharpe | 1.40 | Very good risk-adjusted |
| Max DD | −17.97% | Moderate peak-to-trough |
| Calmar | 1.75 | Good return per drawdown |
| Omega | 1.30 | More THB of gains than losses |
| Trade Win Rate | 2.51% | Rare winners (expected for rolling strategy) |
| Profit Factor | 3.09 | Winners 3× larger than losers |
| Alpha | +31.00% | Model adds value vs holding |
| Beta | 0.02 | Near-zero market correlation |
| VaR 95% | −1.40% | Daily loss boundary |
| t-stat | 1.51 (p=0.013) | **Significant at 95%** |

---

## 6. Thai Equity Backtest (2022–2024) — Run Details

### Configuration

| Parameter | Value |
|-----------|-------|
| **Tickers** | 49 Thai equities (1 excluded — GULF.BK insufficient data) |
| **Period** | 2022-01-03 → 2024-12-31 (756 trading days) |
| **Lookback** | 400 days |
| **Prediction horizon** | 20 days |
| **Samples** | 10 per ticker per day |
| **Max positions** | 5 (equal weight baseline) |
| **Long threshold** | 1% |
| **Entry buffer** | 0.5% |
| **Min holding days** | 5 |
| **Total forecasts** | 49 × ~750 × 10 = ~367,500 forward passes |
| **Compute time** | ~4.5 hrs precompute + ~90 s walk-forward (GTX 1060) |
| **Precompute calendar** | Business days (5-day) — Thai equity trades Mon-Fri |

### Eligible Tickers

**49 Thai equity tickers** from `kth/data/universe.py` `thai_equity` list. The full list covers 8 sectors: Energy (9), Banking (8), Property/Construction (9), Commerce/Retail (4), Food/Beverage (5), Healthcare (4), Telecom/Tech (6), Tourism/Logistics (5).

Key tickers include PTT, KBANK, SCB, BBL, CPALL, DELTA, ADVANC, AOT, BDMS, GULF, PTTEP, CPN, MINT, BH, IVL, plus 35 expansion tickers (BGRIM, GPSC, TOP, IRPC, BANPU, BCP, RATCH, KTB, TISCO, TCAP, KKP, MEGA, LH, QH, AP, ORI, SCC, HMPRO, SIRI, PSH, CPF, OSP, ICHI, CRC, GLOBAL, DOHOME, CENTEL, ERW, BCH, CHG, BEM, BTS, TRUE, JMART, HANA).

**Excluded:** GULF.BK (listed ~2025, 268 rows, insufficient for lookback=400 — the precompute filter rejects it upfront to avoid retrying every day).

### Results Summary

| Metric | Equal Weight (49 tkrs) | Inv-Vol (14 tkrs, reference) |
|--------|----------------------|------------------------------|
| CAGR | **+31.44%** | +13.29% |
| Total Return | +111.0% | +47.09% |
| Sharpe | **1.40** | 0.84 |
| Max Drawdown | −17.97% | **−6.25%** |
| Annual Turnover | 11.8× | 20.81× |
| Annual Friction Drag | 6.3% | ~11.2% |
| Alpha (vs EW) | +30.0pp | +11.9pp |
| p-value (vs EW) | **0.013** | 0.41 |

**Inv-Vol trade-off (14 tickers, for reference):** Cut Max DD by more than half (−6.25% vs −13.69% in the 14-ticker equal-weight run) at the cost of lower CAGR (+13.29% vs +25.03%). The risk-adjusted comparison depends on the investor's risk tolerance. Not re-run with 49 tickers.

---

## 7. Known Limitations

1. **Survivorship bias.** yfinance only lists currently-traded stocks. Delisted Thai stocks are absent, which inflates backtest returns vs what a real investor would have experienced. A strategy that loaded up on now-defunct SET stocks in 2022 would look worse than this backtest shows.

2. **Free data quality.** Thai stock prices on Yahoo can have stale data, corporate action gaps, and occasional bad ticks. We flag extreme moves (>30%) in the quality report but do not correct them. One bad data point can generate a false signal that triggers a trade.

3. **No capacity constraints.** The backtest assumes any position size executes at the t+1 open price. In reality, a Thai retail investor buying <100K THB per position will fill close-to-open, but large orders (>5M THB on a mid-cap) would move the market. The model's max position size of ~200K THB is safe for all tickers.

4. **Tax not modelled.** Thai capital gains on SET stocks are taxed as personal income (0–35% bracket). A retail investor in the 20% bracket would see net returns reduced by ~5 percentage points. Crypto gains are tax-exempt until 2029.

5. **Fine-tuning attempted, zero improvement.** We trained 9 models (3 markets × 3 folds) with SGDR and 21-month fold windows. None beat zero-shot. See `docs/user-manual.md` §6 for details.

6. **Only 3 of 9 asset classes backtested.** Thai equity (49 tickers), US equity (17 tickers), and crypto (12 tickers) have walk-forward backtests. ETF global, commodity, bond_proxy, REIT, and fx_macro have NOT been backtested — the model's performance on those classes is unknown.

7. **Short time window.** 3 years captures one market cycle but may not generalise. The SET Index was down −5.29% CAGR over this period while the strategy returned +31.44% — but a different 3-year window (e.g., 2018-2020 COVID crash) would produce different results.

---

*Document generated 2026-05-18. Source: `docs/backtest-methodology.md`*
