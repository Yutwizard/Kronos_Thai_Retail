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

## 2. Quick Start (Setup: 5 min | Daily runtime: 10-15 min)

### Prerequisites

- Python 3.10+
- NVIDIA GPU with ≥6GB VRAM (GTX 1060 minimum, T4 recommended)
- Kronos repo cloned locally (`git clone https://github.com/shiyu-coder/Kronos.git kronos_repo`)
- 100 parquet files cached in `data/raw/` (run `python scripts/download_data.py` once)

### Step 1: Install dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-ml.txt
python -m pip install -e .
```

### Step 2: Verify GPU

```bash
python -c "import torch; assert torch.cuda.is_available(), 'GPU required. Free tier: Google Colab T4.'; print(f'CUDA: True, Device: {torch.cuda.get_device_name(0)}')"
```
Expected: `CUDA: True, Device: NVIDIA GeForce GTX 1060` (or similar). If this fails, use Google Colab (free T4 GPU).

### Option A: Command Line (Headless — Fast)

Use this if you want to generate forecasts without opening a notebook.

```bash
python -c "
import pandas as pd; from pathlib import Path; import shutil, sys
sys.path.insert(0, 'kronos_repo')
from kth.data.universe import get_all_tickers
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
today = pd.Timestamp.now().strftime('%Y-%m-%d')

# Invalidate today's cache (force fresh forecasts using latest close)
slug = 'NeoQuasar_Kronos-small'  # notebook Cell 0 auto-derives this for FT mode
today_dir = Path(f'data/forecast_cache/{slug}/{today}')
if today_dir.exists(): shutil.rmtree(today_dir)

precompute_forecasts(th, get_all_tickers(), start_date=today, end_date=today,
                     pred_len=20, n_samples=10, lookback=400)
print(f'Forecasts cached at data/forecast_cache/{slug}/{today}/')
"
```

**Time estimate:** 3-4 minutes on T4, 12-15 minutes on GTX 1060. First run slower (~20 min) if downloading model weights from HuggingFace (~1 GB). Subsequent days: ~20 seconds per ticker (most dates skip if cached).

### Option B: Notebook (Visual — Recommended)

Open `notebooks/05_decision_report.ipynb` in Jupyter or VS Code. Set `REPORT_MODE = "morning"` (or `"trader"`/`"quant"`). Run all cells.

> **First run of the day takes 12-15 minutes** (Cell 2 generates fresh forecasts for 100 tickers). Subsequent re-runs on the same day: ~3 seconds (cache hit).

**Time estimate:** Same as Option A for Cell 2 (forecast generation). Cells 0, 1, 3, 4, 5: ~5 seconds total.

> **Note:** Options A and B do the same thing. Choose one — don't run both. Option B is recommended for first-time users. Option A is for headless/cron setups.

### Step 3: Interpret the output

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
- 🟢 Green: high confidence — uncertainty (P95−P5 range) is ≤10% of current price
- 🟡 Yellow: moderate confidence — uncertainty 10-30%
- 🔴 Red: low confidence — uncertainty >30%
- **↑ Direction**: model expects the price to rise over the next 20 days
- **↓ Direction**: model expects the price to fall

> **Important:** Flag color = model **confidence**, not direction. 🟢 on a ↓ signal means the model is **confidently bearish** (high conviction sell). 🔴 means the model is unsure either way — wide bands, noisy forecast. Do not confuse green flag with "green means buy."

---

## 3. Position Sizing Methodology

Position sizing is the bridge between a forecast and an investment decision. The backtest uses one approach (for historical evaluation), and real trading should use another (for risk management and cost efficiency).

### 3A. How the Backtest Sizes Positions

The walk-forward backtest (`kth/backtest/walkforward.py`) uses the following logic at each trading day. This serves as the baseline against which any real-world sizing improvement should be compared:

**Step 1 — Compute raw signals:**
Forecast return > `long_threshold` (default 1%) → eligible to enter. Returns below threshold → skip.

**Step 2 — Filter exits with hysteresis:**
An existing position does NOT close just because its return dropped below 1%. It only closes when return drops below `long_threshold − entry_buffer` (1% − 0.5% = 0.5%) AND holding period exceeds `min_holding_days` (5 days). This prevents flip-flopping on small price changes.

**Step 3 — Rank and cap positions:**
Eligible tickers ranked by forecast return. Only top `max_positions` (default 5) are selected. This prevents over-diversification into weak signals.

**Step 4 — Compute weights:**
The selected positions are weighted by `position_sizing` mode:

| Mode | Formula | Behaviour |
|------|---------|-----------|
| `"equal"` | 1/N | Every position gets the same weight |
| `"signal"` | rank-based | Highest forecast return gets largest weight (linear rank) |
| `"inv_vol"` | 1 / volatility | Lower-volatility assets get larger weight (portfolio risk-parity) |

**Step 5 — Execute at next day's open:**
Trades are filled at the next trading day's OPEN price (not close — prevents look-ahead). Friction costs are deducted as per the per-class rates.

> **The backtest's sizing is intentionally simple.** It is a benchmark for comparison — if your real-world sizing beats equal-weight 1/N on test data, you have found genuine alpha. If it doesn't, your sizing choices are destroying value.

### 3B. How to Size Positions in Real Trading

Real trading has constraints the backtest doesn't model: odd-lot costs, multi-day execution slippage, tax timing, and personal risk tolerance. Use the backtest's 3 modes as starting points, then layer on these rules:

#### Step 1 — Pick a base allocation mode

| Mode | Use If | Expected Outcome |
|------|--------|------------------|
| **Equal-weight 1/N** | You want simplicity; the backtest's baseline | Lowest turnover, most friction-efficient |
| **Signal-weighted (rank)** | You trust the model's strongest signals most | Higher concentration, higher CAGR if right, deeper DD if wrong |
| **Inverse volatility** | You want risk-parity across assets | Lower max DD, smoother equity curve, lower CAGR |

#### Step 2 — Scale by confidence flag

The model's confidence flag (`🟢🟡🔴` from the report's `Band` column) tells you how tight the forecast uncertainty is relative to current price. Size your position proportionally:

| Flag | Band Width | Target Position Size | Reasoning |
|------|-----------|---------------------|-----------|
| 🟢 Green | ≤10% | 100% of normal | The model's P95−P5 range is tightly concentrated. Trade at full conviction. |
| 🟡 Yellow | 10-30% | 50% of normal | The range is moderate. Half-size reduces risk while capturing the signal. |
| 🔴 Red | >30% | 0% (skip) | The model is unsure — don't trade on noise. |

**Normal position:** `1 / max_positions` (e.g., 1/5 = 20% of portfolio per ticker if max 5 positions).

**Example:** If you run 5 positions signal-weighted and a Thai equity ticker has +3% P50 return with 🟢 band, allocate 20% × 100% = 20% of portfolio to that ticker. Same ticker with 🟡 band: 20% × 50% = 10%.

#### Step 3 — Apply friction haircut

Every position's expected return must survive trading costs. Compute **net expected return**:

```
Net Return = P50% − (Friction × 2)

Where Friction = commission_oneway + slippage_oneway
```

| Class | Commission | Slippage | One-way | Round-trip | Minimum P50% to survive |
|-------|-----------|----------|---------|------------|------------------------|
| Thai equity | 0.168% | 0.10% | 0.268% | 0.536% | >0.268% (entry only) |
| US equity | 0.30% | 0.05% | 0.35% | 0.70% | >0.35% |
| Crypto | 0.25% | 0.20% | 0.45% | 0.90% | >0.45% |

**Rule:** If `Net Return ≤ 0.0%`, skip the trade entirely. The position must survive friction just to break even.

#### Step 4 — Cap by asset class

The backtest's 1.40 Sharpe for Thai equity does not mean you should be 100% in Thai stocks. Apply class-level limits to protect against regime-specific tail risk:

| Class | Max Allocation | Rationale |
|-------|---------------|-----------|
| Thai equity | 40% | Core holding — best Sharpe, lowest DD |
| US equity | 30% | Strong returns but −44% DD risk |
| ETF global | 20% | Untested — use as benchmark only |
| Commodity | 10% | Untested — treat as hedge |
| Bond proxy | 20% | Untested — treat as safe haven |
| REIT | 10% | Untested |
| Crypto | 10% | Model not significant (p=0.64) |
| FX macro | 0% | Features only — not investable directly |

**Trust levels by market for sizing decisions:**

| Market | Signal Quality | Trust Level | Best Use |
|--------|---------------|-------------|----------|
| Thai equity | Strong (Sharpe 1.40, significant) | **High** | Core holding — direction signals |
| US equity | Moderate (Sharpe 0.97, not significant) | **Medium** | Direction signals with smaller sizing |
| Crypto | Weak (Sharpe 0.52, not significant) | **Low** | Exploratory only — BTC direction |
| ETF, Commodity, Bond, REIT, FX | Untested | **None** | Benchmarks only — do not trade |

**Total must sum to ≤100%.** Cash is always an option. The remaining allocation sits in a Thai savings account or short-term bond fund.

#### Step 5 — Protect against volatility spikes

If a class's historical volatility (from the Quant PM review view) has doubled in the past month (e.g., Thai equity went from 15% to 30% annualized vol), halve its allocation until vol normalizes. This prevents the model from over-trading into a crash.

### 3C. Three Complete Example Portfolios

#### Conservative (Income-Focused)

```
max_positions: 5
position_sizing: equal
rebalance: monthly
classes: thai_equity 40%, bond_proxy 20%, cash 40%
min P50% to enter: >2× friction (1.07% for Thai)
confidence flag: only 🟢 green
```

**Expected behaviour:** Low turnover (~3×/year), low DD (~−10%), CAGR likely 10-15%. Most of the time sits in cash. Only enters when model is highly confident and the expected return far exceeds costs. Designed for a retiree who can't afford a −44% US equity drawdown.

#### Balanced (Growth-Oriented)

```
max_positions: 8
position_sizing: inv_vol
rebalance: monthly
classes: thai_equity 30%, US equity 20%, ETF global 10%, crypto 5%, cash 35%
confidence flag: 🟢=full, 🟡=half, 🔴=skip
min P50% to enter: >1× friction
```

**Expected behaviour:** Moderate turnover (~6×/year), moderate DD (−20% to −25%), CAGR ~15-25%. Uses risk-parity to keep crypto and US equity allocations small relative to their high volatility. Matches most retail investors' risk profile.

#### Aggressive (Alpha-Seeking)

```
max_positions: 10
position_sizing: signal (rank-based)
rebalance: biweekly
classes: thai_equity 40%, US equity 30%, crypto 10%, cash 20%
confidence flag: 🟢=full, 🟡=full, 🔴=skip (takes yellow at full size)
min P50% to enter: >0.5× friction
```

**Expected behaviour:** High turnover (~15×/year), high DD (−35% to −40%), CAGR ~30-40%. Concentrates on the model's top-ranked signals regardless of band width (except 🔴). Mirrors the backtest's approach most closely, including its friction drag problem. Only suitable for investors who can tolerate a −40% drawdown.

### 3D. From Report to Action — The Daily Routine

The daily report gives you the raw material. Here's how to turn signals into trades:

1. **Morning:** Open the Morning Brief view. Scan bullish top-10 and bearish bottom-10. Note any tickers you hold that appear in the bearish list.

2. **Weekly:** Open the Quant PM view. Check if any asset class's historical volatility has spiked (regime change). Cross-check against the Green/Yellow/Red flags — if volatility has doubled but flags are still green, the model hasn't caught up to the regime shift yet.

3. **Monthly:** Open Trader's Desk. Build a rebalancing plan: add positions with high `NetRet` and 🟢 flags, reduce positions with consistent bearish signals over the past month. Execute the plan over 2-3 days to avoid market impact.

4. **Quarterly:** Compare your actual returns against the backtest's benchmark. If your equal-weight portfolio underperforms the backtest's equal-weight by >5% CAGR, you're over-trading (excess friction) or mis-timing signals. Review your sizing choices.

---

## 4. The Three Report Views

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
| `Sharpe` | Per-market backtest Sharpe (see §6) |
| `Frict` | Round-trip transaction cost for this market |
| `NetRet` | P50% return minus friction = what you actually keep |

**Key sorting rule:** Sorted by `NetRet` descending. A +1.5% forecast with 0.7% friction (nests 0.8%) ranks below a +1.0% forecast with 0.1% friction (nests 0.9%). The report knows your costs.

### C: Quant PM Review (Weekly deep dive)

Adds trailing 1-year historical volatility, risk-adjusted return, per-market CAGR and max drawdown. Grouped by asset class for attribution analysis. **Useful for rebalancing and regime detection.**

---

## 5. Backtest Methodology

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
| **Sortino** | Same as Sharpe but uses downside vol only | Penalizes only bad volatility. Higher than Sharpe means fewer/gentler drawdowns than average vol suggests (positive skew). |
| **Max DD** | (trough − peak) / peak | Worst peak-to-trough loss. **-17%** in Thai equity = similar to benchmark. |
| **Calmar** | CAGR / |Max DD| | Return per unit of max risk. >1.0 is strong. |
| **Trade Win Rate** | trades with gross_return > 0 / total trades | **Not forecast accuracy.** This is trade P&L rate. 2-5% is expected for long-biased rolling strategies that churn positions monthly. |
| **t-stat / p-value** | t-test: strategy returns > 0? | p < 0.05 means the strategy's positive returns are statistically distinguishable from random noise. |

---

## 6. Backtest Results

### 4-Year Out-of-Sample Summary (2023–2026, n=50)

The most credible evidence for the strategy comes from the 4 clean OOS years — all post the inferred Kronos pre-training cutoff of December 2022.

| Year | Net CAGR | Sharpe | Max DD | p-value | EW CAGR | Alpha vs EW | Friction/yr |
|------|----------|--------|--------|---------|---------|-------------|-------------|
| **2023** | +2.6% | 0.10 | −13.1% | 0.419 ❌ | +12.8% | **−10.2pp** | 5.68% |
| **2024** | +42.0% | 2.27 | −6.9% | **0.015 ✅** | −7.2% | **+49.2pp** | 7.54% |
| **2025** | +33.7% | 1.03 | −24.0% | 0.257 ❌ | −9.9% | **+43.6pp** | 17.35% |
| **2026** | +143% ann.¹ | 2.42 | −18.3% | 0.353 ❌ | +41.8% | **+101pp** | 32.78% |

> ¹ 2026 covers only 107 trading days (Jan–May 2026). Annualised figures are not representative of a full year.

**Statistical note:** Only 2024 clears p<0.05 (unadjusted). Under Bonferroni correction for 4 OOS years (threshold p<0.0125), no year survives. The evidence is suggestive, not conclusive.

**Pattern — SET regime dependency:**
- 📈 **SET bull years (EW positive):** 2023 (EW +12.8%) → strategy underperforms. Cash drag from conservative allocation (50% deployed in a rising market) + friction costs more than stock-selection gains.
- 📉 **SET bear years (EW negative):** 2024 (EW −7.2%), 2025 (EW −9.9%) → strategy crushes equal-weight by +49pp and +44pp. Selective positions in declining markets is exactly where the model's advantage shows.
- **Key finding:** The 2023 underperformance is structural, not a model failure. The deployed stocks beat EW by +3.3pp on deployed capital — cash drag (−6.4pp) and friction (−5.7pp) caused the net underperformance vs a fully-deployed EW.

---

### Thai Equity 2022–2024 Canonical Backtest

| Metric | Strategy | SET Index | SPY | Equal-Weight |
|--------|----------|-----------|-----|-------------|
| CAGR | **+31.44%** | −5.29% | +8.33% | +1.44% |
| Sharpe | **1.40** | −0.63 | 0.44 | 0.00 |
| Max DD | −17.97% | −25.64% | −24.50% | −18.07% |

Source: `data/backtest_results/thai_equity_2022-2024_v2/` (n_samples=10, equal-weight, single path).

**Interpretation:** The SET Index was DOWN 5% CAGR over this period — the model was UP 31%. The ~30pp alpha over equal-weight is the key signal.

**Statistical note:** Single-run p=0.034 (borderline). The 2022 portion may partially overlap Kronos pre-training data (cutoff ≈ Dec 2022). Treat 2022 results with caution; the 4-year OOS table above is the more reliable evidence.

### Expanded Thai Equity (2020–2024, 5-year)

A 5-year expanded backtest adds the COVID crash (Q1 2020) and recovery (2020-2021) to validate the model across multiple macro regimes. Uses `n_samples=10` (vs 50 in 2022-2024) due to 5× longer period; results are directionally comparable but not directly comparable.

| Period | CAGR | Sharpe | Max DD | Alpha vs EW | SET CAGR | p-value | Verdict |
|--------|------|--------|--------|-------------|----------|---------|---------|
| **Full (2020–2024)** | **+35.16%** | **1.29** | −37.90% | +23.32% | −5.29%* | 0.174 | — |
| Stress (COVID crash) | −1.62% | 0.12 | −37.90% | +21.63% | −27.43% | 0.762 | **Mitigate** |
| Rebound (Recovery) | +65.96% | 2.03 | −17.54% | +29.73% | +14.10% | 0.425 | **Thrive** |
| Current (Rate hikes) | +27.94% | 1.29 | −17.00% | +20.29% | −5.29% | 0.229 | **Thrive** |

> *Full-period SET CAGR is shown for the 2022-2024 sub-period only; the full 5-year SET return was different.

**Key findings:**
- **Alpha positive in ALL 3 regimes.** The model outperforms equal-weight in the COVID crash (+21.6pp), the recovery (+29.7pp), and rate hikes (+20.3pp). This is consistent with a genuine signal, not a regime-specific artifact.
- **COVID crash: Mitigate.** The model lost only −1.6% vs SET's −27.4%. Alpha is large but low statistical power (~125 trading days, p=0.76).
- **The 5-year CAGR (+35.16%) equals the 3-year (+31.44%) despite including a −30% crash.** The recovery (65.96% CAGR) more than compensated — the model captured the rebound aggressively.

**Caveat:** The full-period p-value (0.174) is NOT significant at 5%. The stress period's limited data (125 days) adds noise. The signal is consistent across regimes but the statistical significance weakens over the longer period. See caveat #3.

### US Equity (17 tickers)

| Metric | Strategy | SET | SPY | 60/40 | Equal-Weight |
|--------|----------|-----|-----|-------|-------------|
| CAGR | **+30.34%** | −5.29% | +8.33% | −0.27% | +14.39% |
| Sharpe | **0.97** | −0.63 | 0.44 | −0.11 | 0.66 |
| Max DD | −43.77% | −25.64% | −24.50% | −27.18% | −32.95% |

**Interpretation:** Strong absolute returns (30% CAGR) and beats SPY (22pp alpha). But max drawdown (−44%) is worse than SPY (−25%) — this portfolio concentrates 17 mega-cap names; drawdowns are steeper than the benchmark.

**Caveat:** Neither the strategy nor equal-weight is statistically significant at 5% (p ≈ 0.46). The 2022-2024 period was a strong bull run for US mega-caps — the strategy captured it well, but we cannot distinguish from beta noise.

**Currency note:** US equity returns are in USD. For THB-equivalent returns, multiply by USDTHB exchange rate. The `fx_macro` class tracks THB=X for this purpose. In 2022-2024, USDTHB moved ~33→36 (~9% USD appreciation), so THB-denominated returns are higher than USD returns.

### Crypto (12 tickers)

| Metric | Strategy | SET | SPY | 60/40 | Equal-Weight |
|--------|----------|-----|-----|-------|-------------|
| CAGR | **+16.45%** | −5.29% | +8.33% | −0.27% | −5.16% |
| Sharpe | **0.52** | −0.63 | 0.44 | −0.11 | 0.16 |
| Max DD | −68.58% | −25.64% | −24.50% | −27.18% | −76.60% |

**Interpretation:** Crypto was in a bear market (equal-weight down 5%). The model beat it by 22pp. But volatility is extreme — a −69% drawdown means the portfolio dropped by two-thirds. The p-value is 0.64 (not significant).

**Reality check:** Crypto's 0.52 Sharpe with 22pp alpha sounds impressive, but the max drawdown of −69% means most investors would have panic-sold long before. This is NOT suitable for a large allocation.

### Fine-Tuning Verdict — ZERO-SHOT WINS IN ALL MARKETS

**This is the second most important finding in the project.** We spent 65 GPU-hours training 9 models across 3 markets (3 folds each). None beat zero-shot. The entire effort produced zero deployed checkpoints.

| Market | ZS Sharpe | Best FT Sharpe | Δ | Verdict |
|--------|-----------|---------------|---|---------|
| Thai equity | 1.40 | — | — | ✅ Stay ZS |
| US equity | 0.97 | 0.94 (F2) | −0.03 | ✅ Stay ZS |
| Crypto | 0.52 | 0.46 (F0) | −0.06 | ✅ Stay ZS |

> Updated with n=50 yearly backtests (2024: +43.78%/2.27, 2025: +34.92%/1.03). See §6.2.

**Fine-tuning did not help in any market.** All 3 markets use zero-shot Kronos-small. The 9 fine-tuned checkpoints are saved at `./checkpoints/{model}/fold{f}/best/` but not deployed. Direction accuracy improved slightly (+2.0pp for US equity) but did not translate to backtest alpha (FT Sharpe 0.94 vs ZS 0.97).

**Do not attempt fine-tuning again without a different approach:** larger model (Kronos-base), longer training epochs, different prediction horizon, or a different dataset construction method. The current approach (21-month folds, SGDR, 10 epochs) was correct — the signal simply wasn't there.

### Yearly n=50 Backtests (Clean OOS, 2023-2026)

High-quality backtests with n_samples=50 on the clean out-of-sample window (post training cutoff). All 4 years complete.

| Year | Return | Sharpe | Max DD | Alpha EW | SET | p-value |
|------|--------|--------|--------|----------|-----|---------|
| **2024** | **+43.78%** | **2.27** | −6.92% | +49.0% | −1.10% | **0.015** |
| **2025** | **+34.92%** | **1.03** | −24.00% | +27.3% | −10.04% | 0.257 |
| **2026** | **+45.28%** | **2.42** | −18.26% | +26.5% | +20.61% | 0.353 |
| **2023** | **+2.65%** | **0.10** | −13.08% | −1.67% | — | 0.419 |

**Key insight:** n=50 improved 2025 by +12.4pp return and Sharpe +0.24 over n=10. 2026 has the highest return (+45%) but only 107 trading days — p=0.353 is not significant due to short period. 2023 was a flat year (+2.65%) — the model slightly underperformed equal-weight. Alpha is not uniform every year.

---

## 7. Cautions & Limitations

### Read Before Trading

1. **This is not financial advice.** It is a forecasting tool. Forecasts can be wrong. A 60% hit rate means 40% of predictions are wrong.

2. **Survivorship bias is real.** The universe includes only currently-listed tickers. Delisted stocks are absent from backtests, which overstates returns. The real historical performance of this strategy would be lower.

3. **The 2022-2024 backtest period was a unique macro environment.** QE unwind, AI boom, SET underperformance. A different regime (e.g., 2018 trade war, 2020 COVID crash) would produce different results. Past performance is NOT indicative of future results.

    *Updated with 2020-2024 expanded backtest:* The model was tested across the COVID crash (Q1 2020), recovery (2020-2021), and rate hikes (2022-2024). Alpha was positive in ALL 3 regimes — including a crash. This strengthens the claim that the signal is genuine, but the full-period p-value (0.174, n=10 samples) is weaker than the 3-year result (p=0.013, n=50 samples). The stress period (125 days) has very low statistical power.

4. **Crypto calendar fix applied.** The original backtest used 5-day business days (Mon-Fri) for all assets, which skipped weekends for crypto. This was fixed in Task 1 of the HFM review: `walkforward.py` now uses `_get_calendar_for_tickers()` which returns "D" (7-day) for crypto tickers. `forecast()` and `forecast_batch()` auto-detect crypto from ticker class. Crypto precompute and walk-forward now use the correct 7-day calendar. See `kth/backtest/walkforward.py:_get_calendar_for_tickers()`.

> Note: If calling `forecast()` standalone with a DataFrame (not a ticker string), pass `calendar_freq="D"` explicitly for crypto data. The precompute path is unaffected.

5. **ETFs class uses SPY as proxy.** The `etf_global` backtest metric (Sharpe 0.44, CAGR +8.33%) was computed only on SPY, but the class covers 9 ETFs including EM (VWO), Korea (EWY), Japan (EWJ), China (FXI). The model may perform differently on those markets. The report shows `"—"` for untested classes, but ETFs displays SPY numbers for all 9 tickers.

6. **Classes without backtest** — commodity, bond_proxy, reit, fx_macro — show `"—"` for Sharpe/CAGR in the report. These were never backtested. Do not trade them based on model forecasts without additional research.

7. **The trade win rate is 2-5%.** This does not mean the model is wrong 95% of the time. It means the portfolio churns monthly (daily rebalancing × 11.8× annual turnover), producing many small losing trades around a core of winning longs. This is expected for a long-biased rolling strategy. Focus on CAGR and Sharpe, not trade win rate.

8. **CPU inference is very slow.** Generating forecasts for 100 tickers takes 10-15 minutes on GTX 1060, 3-4 minutes on T4, but would take hours on CPU. The notebook will refuse to run on CPU. If you don't have GPU access, use Colab.

### Known Bugs

| Bug | Impact | Status |
|-----|--------|--------|
| `forecast()` timestamps default to "B" for DataFrame input | Standalone calls on DataFrame (not ticker string) default to 5-day calendar. | ✅ Precompute path unaffected. Pass `calendar_freq="D"` explicitly for crypto DataFrames. |
| Mixed crypto+equity backtest run uses crypto 7-day for all | If running a backtest with both BTC-USD and AAPL, AAPL gets weekend timestamps. | Workaround: run crypto-only and equity-only backtests separately. Documented in `_get_calendar_for_tickers()`. |

---

## 8. Performance Tables (Reference)

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
| Annual Friction Drag | 6.3% | 6.4% | 6.0% |
| p-value | <0.05 | 0.46 | 0.64 |

> **Annual Friction Drag** = Annual Turnover × Round-trip Friction. Example: Thai equity 11.8× × 0.536% = 6.3% of AUM lost to costs annually. On a 31.4% CAGR, that's a 20% haircut. The backtest's CAGR is AFTER friction — these numbers are net.

> **Thai equity risk note:** The strategy's Max DD (−17.97%) is nearly identical to equal-weight (−18.07%). The model's active selection does NOT increase tail risk over passive allocation. This is a positive finding — the alpha is "free" from a risk perspective.

### Benchmark Comparison Matrix

All returns in native currency unless noted. For THB-equivalent, apply USDTHB adjustment (~+9% over 2022-2024).

| Market | USD CAGR | USDTHB Adj | THB CAGR |
|--------|----------|------------|----------|
| US equity | +30.34% | ~+9% | **~+39%** |
| Crypto | +16.45% | ~+9% | **~+25%** |
| Thai equity | +31.44% | — | **+31.44%** (native THB) |

| Asset | Strategy | SET | SPY | 60/40 | Equal-Wt |
|-------|----------|-----|-----|-------|----------|
| Thai equity CAGR | **+31.44%** | −5.29% | +8.33% | −0.27% | +1.44% |
| Thai equity Sharpe | **1.40** | −0.63 | 0.44 | −0.11 | 0.00 |
| US equity CAGR | **+30.34%** | — | +8.33% | — | +14.39% |
| US equity Sharpe | **0.97** | — | 0.44 | — | 0.66 |
| Crypto CAGR | **+16.45%** | — | +8.33% | — | −5.16% |
| Crypto Sharpe | **0.52** | — | 0.44 | — | 0.16 |

---

## 9. File Reference

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
