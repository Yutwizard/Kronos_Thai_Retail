# Kronos-TH Operations Manual

> **Reference document — decision rules and methodology.**
>
> For daily use, start here:
> - **New to Kronos?** → [Getting Started Guide](getting-started.md) (installation, paper trading, day-by-day walkthrough)
> - **Flask dashboard user?** → [Dashboard User Manual](dashboard-user-manual.md) (Flask dashboard setup, requires local GPU)
> - **Google Suite dashboard user?** → [google_suite/SETUP_GUIDE.md](../google_suite/SETUP_GUIDE.md) (zero-cost, browser-based, no local GPU)
>
> This operations manual documents the decision rules (3-filter, signal interpretation, risk controls) that are common to both dashboards. The Flask dashboard commands shown in this manual are also valid; the Google Suite equivalent uses Colab cells — see the SETUP_GUIDE.md for those.

---

## Table of Contents

1. [Daily Morning Routine](#1-daily-morning-routine-12-15-minutes)
2. [Daily Evening Check](#2-daily-evening-check-2-minutes)
3. [Weekly Portfolio Review](#3-weekly-portfolio-review-15-20-minutes)
4. [Monthly Rebalancing](#4-monthly-rebalancing-30-45-minutes)
5. [Quarterly Performance Review](#5-quarterly-performance-review-30-minutes)
6. [Example Scenarios](#6-example-scenarios)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Daily Morning Routine (12-15 minutes)

> **Note:** This describes the original notebook workflow (100 tickers, all asset classes). The dashboard (see [Dashboard User Manual](dashboard-user-manual.md)) automates this for Thai equity only (49 tickers, 500K THB). The signal interpretation rules below apply to both.

### Objective
Generate fresh forecasts for all 100 tickers and identify actionable signals for the day ahead.

### Prerequisites
- GPU available (GTX 1060 or better). Without GPU, use Google Colab free T4.
- Overnight forecast cache deleted (script handles this automatically).
- `data/raw/*.parquet` files up to date (run `python scripts/download_data.py` once a week).

### Step-by-Step

#### Step 1.1 — Open the report notebook

```bash
cd /path/to/kronos-th
python -m pip install -e .
jupyter notebook notebooks/05_decision_report.ipynb
```

If you prefer command-line (no GUI), use Option A instead.

#### Step 1.2 — Set the report mode

In Cell 0 of the notebook, set:

```python
REPORT_MODE = "morning"   # <- change to "morning"
MODEL_TYPE  = "zero-shot"  # always "zero-shot" (FT did not improve backtest)
```

Do **not** use `"fine-tuned"` — all 9 fine-tuned checkpoints underperform zero-shot in backtest.

#### Step 1.3 — Run all cells (Cell 1 → Cell 4)

| Cell | What it does | Time |
|------|-------------|------|
| Cell 1 | Loads Kronos-small model into GPU memory | ~5 seconds |
| Cell 2 | Deletes yesterday's cache, generates fresh forecasts for 100 tickers | **~12 minutes on GTX 1060** (~3 min on T4) |
| Cell 3 | Builds a 25-column DataFrame from forecast cache + universe + backtest metrics | ~3 seconds |
| Cell 4 | Renders the morning brief (or trader/quant view) with disclaimers appended | ~2 seconds |

> **First run of the day:** 12-15 minutes. **Subsequent runs on the same day:** ~3 seconds (cache hit — Cell 2 skips already-cached dates).

#### Step 1.4 — Read the Morning Brief output

After Cell 4 finishes, you'll see:

```
=== Morning Brief — 2026-05-24 ===

🟢 BULLISH (top 10 by conviction):
  Ticker         Name                   Class           Close    P50%     Band  Flag  Dir
  -------------------------------------------------------------------------------------
  PTT.BK         PTT                    thai_equity     32.50   +2.31%   6.50% 🟢    ↑
  SCC.BK         Siam Cement            thai_equity    248.00   +1.80%   8.20% 🟢    ↑
  AAPL           Apple                  us_equity      180.20   +1.20%   7.10% 🟢    ↑
  BTC-USD        Bitcoin                crypto       67200.00   +3.50%  12.50% 🟡    ↑
  ...

🔴 BEARISH (bottom 10 by conviction):
  Ticker         Name                   Class           Close    P50%     Band  Flag  Dir
  -------------------------------------------------------------------------------------
  KBANK.BK       Kasikornbank           thai_equity    142.00   -1.80%   5.20% 🟢    ↓
  DELTA.BK       Delta Electronics      thai_equity     88.50   -2.10%   6.80% 🟢    ↓
  ...
```

**Interpretation:**

| Signal | Meaning | Action |
|--------|---------|--------|
| 🟢 + ↑ + P50% > 2× friction | High conviction bullish | Full position (net return safely above costs) |
| 🟢 + ↑ + P50% > 1× friction but < 2× friction | Moderate conviction bullish | Half-size — net return positive but thin |
| 🟢 + ↓ + abs(P50%) > friction | High conviction bearish | Consider exiting or reducing position |
| 🟡 + any direction | Moderate conviction | Halve position size if you enter |
| 🔴 + any direction | Low conviction | Skip — model is unsure |
| All signals 🔴 | Market turmoil | Stay in cash entirely |

**Example interpretation for the output above:**
- **PTT.BK** at 32.50 THB, model expects +2.31% over 20 days with narrow band (6.5% uncertainty). Net return after friction: 2.31% - 0.536% = **+1.77%**. This beats the "enter if > 2× friction" rule (1.07%). ✅ Consider a position.
- **KBANK.BK** at 142.00 THB, model expects -1.80% with narrow band. Net return: -1.80% - 0.536% = **-2.34%**. Confidently bearish. If you hold KBANK, **consider exiting**.
- **BTC-USD** has +3.50% P50 but 🟡 band (12.5% uncertainty). Half-size: the net return of +2.60% after friction is strong, but the band is wide. Allocate 50% of normal BTC position.

#### Step 1.5 — Check positions you already hold against the bearish list

Compare the bearish list to your current holdings. Any ticker appearing in **both** is a candidate for exit.

**Example:**
```
Your holdings: PTT, SCC, KBANK, AAPL, BTC
Bearish list:  KBANK, DELTA, BBL, ...
```
→ **KBANK** is in the bearish list. You hold it. Consider reducing or exiting.

#### Step 1.6 — Record the date's key numbers

Quick mental note (or log to a text file if you track performance):

```
Date: 2026-05-24
# bullish signals (🟢): 12
# bearish signals (🟢↓): 8
# red-flagged (🔴): 15
Median band width: 18%
```

If `# red-flagged > 30` or `median band width > 30%`, the market is in a high-uncertainty state — reduce overall exposure.

---

## 2. Daily Evening Run (15 minutes) ← MAIN PIPELINE

### Objective
Run the daily pipeline **after SET closes (17:00 BKK)** to generate tomorrow's forecast
using today's close prices. This is the recommended time — not the morning.

**Why evening?** The forecast uses the most recent close. Running after market close means:
- Tomorrow's Exp Ret is based on today's actual closing prices (most accurate)
- Tomorrow morning you just open the dashboard and trade — no 12-min GPU wait
- The positions table shows signals based on today's close (updated view)

### Steps

1. Open http://localhost:5555
2. Click **▶ Run Pipeline** in the top-right header
3. Wait ~12 min for all 3 steps to show ✅
4. Review positions table — Exp Ret and Band now use today's close prices
5. Check Trade Ticket for tomorrow's recommended trades

**Or from terminal:**
```bash
python scripts/dashboard.py --generate
```

**Or one-command (recommended for fresh setups):**
```bash
./scripts/start_dashboard.sh
```
Idempotent launcher: creates venv, installs data + ML deps, downloads data, runs pipeline, starts dashboard on port 5555. Subcommands: `stop`, `restart`, `status`, `logs`, `clean`. See `scripts/start_dashboard.sh help` for full usage.

**Verify forecasts are ready:**
```bash
ls data/forecast_cache/NeoQuasar_Kronos-small/$(date +%Y-%m-%d)/ | wc -l
# Expected: 49
```

If the directory is empty or missing, run the pipeline manually (evening or morning — either works).

---

## 3. Weekly Portfolio Review (15-20 minutes)

### Objective
Assess regime changes, model degradation, and class-level allocation exposure.

### When
Every Sunday evening or Monday morning before market open.

### Step-by-Step

#### Step 3.1 — Run the Quant PM view

Change Cell 0 in the notebook:

```python
REPORT_MODE = "quant"
```

Run all cells. The output shows per-ticker risk-adjusted metrics grouped by asset class.

#### Step 3.2 — Identify volatility spikes

Look for classes where `HistVol` (historical volatility) has doubled vs your baseline.

**Baseline volatilities (from backtest period):**

| Class | Normal Vol Range | Warning Threshold |
|-------|-----------------|-------------------|
| Thai equity | 12-20% | >30% |
| US equity | 18-28% | >40% |
| Crypto | 40-70% | >80% |

**Example output:**
```
── thai_equity ──
  Ticker      P50%   Band  HistVol  RiskAdj  Sharpe  CAGR   MaxDD   NetRet
  PTT.BK    +2.31%  6.50%   18.5%    0.12    1.40  +31.44% -17.97% +1.77%
  ...
── us_equity ──
  Ticker      P50%   Band  HistVol  RiskAdj  Sharpe  CAGR   MaxDD   NetRet
  AAPL       +1.20%  7.10%   24.0%    0.05    0.97  +30.34% -43.77% +0.50%
  ...
── crypto ──
  Ticker      P50%   Band  HistVol  RiskAdj  Sharpe  CAGR   MaxDD   NetRet
  BTC-USD    +3.50% 12.50%   52.0%    0.07    0.52  +16.45% -68.58% +2.61%
```

If `HistVol` for any asset class > warning threshold, **halve that class's allocation** until vol normalizes.

#### Step 3.3 — Check trailing signal quality

Compare the week's average P50% against the actual returns from last week's forecasts. If the model was bullish on a ticker and the ticker went down, note it. If more than 40% of last week's predictions had the wrong direction, the model may be degrading.

**Quick diagnostic — direction accuracy check:**

```bash
python -c "
import pandas as pd
from pathlib import Path

ticker = 'PTT.BK'
today = '2026-05-24'
safe = ticker.replace('^','_').replace('=','_')

hits = 0
total = 0
for i in range(5, 15):
    d = (pd.Timestamp(today) - pd.Timedelta(days=i)).strftime('%Y-%m-%d')
    f = Path(f'data/forecast_cache/NeoQuasar_Kronos-small/{d}/{safe}.parquet')
    if not f.exists():
        continue
    fc = pd.read_parquet(f)
    old_p50 = float(fc['p50'].iloc[-1])
    df = pd.read_parquet(f'data/raw/{safe}.parquet')

    # Close price 5 days before forecast date (= 400 days back, roughly)
    close_before = float(df[df['timestamps'] == d]['close'].iloc[0]) if len(df[df['timestamps'] == d]) > 0 else 0
    # Close today
    close_now = float(df['close'].iloc[-1])
    if close_before == 0 or close_now == 0:
        continue

    pred_dir = 'up' if old_p50 > close_before else 'down'
    actual_dir = 'up' if close_now > close_before else 'down'
    hit = pred_dir == actual_dir
    if hit:
        hits += 1
    total += 1
    print(f'{d}: Predicted {pred_dir} (P50={old_p50:.2f}), Actual {actual_dir} (close={close_now:.2f}) -> {\"HIT\" if hit else \"MISS\"}')

print(f'\nDirection accuracy for {ticker}: {hits}/{total} = {hits/max(total,1):.0%}')
print(f'If accuracy < 50%, the model may be degrading for this ticker.')
"
```

#### Step 3.4 — Review the allocation pie

Open the Trader's Desk view. Check if any class allocation has drifted >5% from your target.

**Target allocation (balanced profile):**
| Class | Target | Allowable Range |
|-------|--------|----------------|
| Thai equity | 40% | 35-45% |
| US equity | 20% | 15-25% |
| ETF global | 10% | 5-15% |
| Crypto | 5% | 2-8% (hard max 10%) |
| Other | 5% | 0-10% |
| Cash | 20% | 10-30% |

If any class is outside its range, add it to the monthly rebalancing plan.

---

## 4. Monthly Rebalancing (30-45 minutes)

### Objective
Realign portfolio to target allocations based on accumulated monthly signals.

### When
Last Friday of each month (or first weekend after month-end).

### Step-by-Step

#### Step 4.1 — Run Trader's Desk view

```python
REPORT_MODE = "trader"
```

Run all cells. The output shows all tickers sorted by `NetRet` descending, grouped by class, with friction costs.

#### Step 4.2 — Evaluate each position using the 3-filter rule

For each ticker you hold or are considering:

| Filter | Rule | Action |
|--------|------|--------|
| **Net Return** | NetRet > 2× friction? | Keep if yes; consider exit if no |
| **Confidence** | Flag is 🟢 or 🟡? | Keep if 🟢 or 🟡; consider exit if 🔴 |
| **Class allocation** | Within targeted range? | Adjust if outside range |

**If all 3 filters pass:** Maintain or increase position.
**If 1-2 filters fail:** Reduce position by half.
**If all 3 fail:** Exit entirely.

#### Step 4.3 — Build the rebalancing trade list

Use the example template:

```
╔═══════════════════╤════════════╤═══════╤═══════╤══════════════╗
║ Ticker            │ Action     │ Size  │ NetRet│ Rationale    ║
╠═══════════════════╪════════════╪═══════╪═══════╪══════════════╣
║ PTT.BK (hold)     │ Hold + add │ +1%   │ +1.77%│ 🟢 + NetRet  ║
║ KBANK.BK (hold)   │ Exit       │ -2%   │ -2.34%│ 🟢↓ bearish   ║
║ AAPL              │ Enter      │ +1%   │ +0.50%│ 🟢 + thin band║
║ BTC-USD (hold)    │ Reduce     │ -0.5% │ +2.61%│ 🟡 half size  ║
║ Cash              │ —          │ +2.5% │ —     │ —             ║
╚═══════════════════╧════════════╧═══════╧═══════╧══════════════╝
```

**Sizing convention:** Each full ticker = 20% of portfolio if `max_positions=5`. Adjust proportionally.

**Example sizing calculation:**
- 4 positions selected from a 5-position budget: PTT, AAPL, BTC
- Target allocation: 4 positions → 25% each (100/4)
- Confidence scaling: PTT 🟢 → 25%, AAPL 🟢 → 25%, BTC 🟡 → 12.5%
- Remaining: 100% - 25% - 25% - 12.5% = **37.5% cash**

> **Note on cash drag and regime dependency:** The 4-year OOS study (2023–2026) confirms the strategy underperforms equal-weight in SET bull markets and strongly outperforms in SET bear markets.
> - **SET bull (EW positive, e.g. 2023 EW +12.8%):** strategy holds 50% cash → costs ~6.4pp vs a fully-deployed equal-weight portfolio, even when stock picks are correct. This is intentional risk management, not model failure.
> - **SET bear (EW negative, e.g. 2024 EW −7.2%, 2025 EW −9.9%):** strategy's selective positions crush equal-weight by 43–49pp.
> - **In a strong SET bull market, use BEAR allocation (5%) or NEUTRAL (10%) to limit capital at risk.** The strategy's edge comes from stock selection in diverging markets — in a rising-tide market, concentration in 5 picks is a disadvantage vs the full 49-stock equal-weight.
> - **Signal to shift allocation up:** When the weekly Quant PM view shows >5 tickers with bullish 🟢↑ signals AND the SET index has been declining for 4+ consecutive weeks, consider moving from BEAR to NEUTRAL.

#### Step 4.4 — Execute over 2-3 days

**Do not execute all trades on one day.** Spread over 2-3 days to reduce market impact:

```python
# Day 1: Sell KBANK (bearish, urgent)
# Day 2: Buy AAPL (bullish, not urgent)
# Day 3: Buy PTT (bullish, adjust size)
```

#### Step 4.5 — Log the trades

```python
# Save to data/trade_log.csv
import csv
with open('data/trade_log.csv', 'a', newline='') as f:
    w = csv.writer(f)
    w.writerow(['2026-05-30', 'KBANK', 'sell', '142.00', '1.0', 'PTT rebalance'])
    w.writerow(['2026-06-01', 'AAPL', 'buy', '181.50', '0.5', 'monthly signal'])
```

---

## 5. Quarterly Performance Review (30 minutes)

### Objective
Compare actual portfolio performance against backtest benchmarks.

### When
End of March, June, September, December.

### Steps

#### Step 5.1 — Compute total portfolio value (MTM)

From your trading log + remaining positions:

```bash
python -c "
import pandas as pd
from pathlib import Path

# Load trades and current holdings from log
trades = pd.read_csv('data/trade_log.csv')
initial_cash = 500_000  # 500K THB starting portfolio (matches dashboard default; original notebook used 1M)

# Compute net cash from closed trades (+ sell, - buy)
cash_flow = 0
for _, row in trades.iterrows():
    sign = 1 if row['direction'] == 'sell' else -1
    cash_flow += sign * row['size'] * row['price'] * initial_cash

# Compute mark-to-market of remaining holdings
mtm_value = 0
holdings = trades[trades['direction'] == 'buy']['ticker'].unique()
for t in holdings:
    # Check if still held (no corresponding sell)
    buys = trades[(trades['ticker'] == t) & (trades['direction'] == 'buy')]
    sells = trades[(trades['ticker'] == t) & (trades['direction'] == 'sell')]
    net_units = buys['size'].sum() - sells['size'].sum()
    if net_units > 0:
        # Get current close price
        safe = t.replace('^','_').replace('=','_')
        try:
            df = pd.read_parquet(f'data/raw/{safe}.parquet')
            current_price = float(df['close'].iloc[-1])
            mtm_value += net_units * current_price * initial_cash
        except:
            pass

total = initial_cash + cash_flow + mtm_value
cagr = (total / initial_cash) ** (252 / len(trades['date'].unique())) - 1 if len(trades) > 0 else 0
print(f'Initial capital: {initial_cash:,.0f} THB')
print(f'Cash from trades: {cash_flow:+,.0f} THB')
print(f'Mark-to-market (open positions): {mtm_value:+,.0f} THB')
print(f'Total portfolio value: {total:,.0f} THB')
print(f'Estimated CAGR: {cagr:+.2%}')
"
```

#### Step 5.2 — Compare to benchmarks

| Benchmark | CAGR (backtest, 2022-2024) | CAGR (backtest, 2020-2024) | 1σ Range (2022-2024) |
|-----------|-----------------------------|-----------------------------|---------------------|
| Strategy | +31.44% | +35.16% | 14% to 48% |
| SET Index | −5.29% | — | −28% to +18% |
| SPY | +8.33% | — | −16% to +33% |
| Equal-weight | +1.44% | — | −19% to +22% |

> Ranges are backtest CAGR ± 1.5 × annualized vol. If your actual CAGR is below the range for 2 consecutive quarters, review the §5.2 checklist below.

If your actual CAGR is within the "Reasonable Range" of the strategy backtest, you're executing correctly. If it's below the range consistently for 2 quarters, review:
1. Are you over-trading? (friction > 6% of AUM/year)
2. Are you ignoring bearish signals? (holding losing positions too long)
3. Is the model underperforming? (run the weekly diagnostic from §3.3)

#### Step 5.3 — Review position sizing fidelity

Check your `trade_log.csv` for compliance with position sizing rules:

| Rule | Expected | Your Data |
|------|----------|-----------|
| Trades per month | ≤ 10 | count / 3 months |
| Average position size | ≤ 20% | mean |
| Friction per trade | 0.5-0.9% | mean |
| Win rate | 1.5-3% | — (matches backtest: Thai 2.5%, US 2.8%, Crypto 1.5%) |

---

## 6. Example Scenarios

### Scenario A: Normal Day

**Morning Brief (2026-05-24):**
```
🟢 BULLISH: PTT (+2.3%), SCC (+1.8%), AAPL (+1.2%)
🔴 BEARISH: KBANK (-1.8%), DELTA (-2.1%)
HistVol: Thai 18% (normal), BTC 52% (normal)
```

**Your holdings:** PTT (2%), KBANK (1.5%), AAPL (1%), cash (balance)

**Decision:**
- PTT: Hold. Net return +1.77% > friction. 🟢 flag.
- KBANK: **Exit.** Confidently bearish (-1.8% P50, 🟢 confidence). Reduce by 1%.
- AAPL: Hold. Net return +0.50% > US friction (0.35%). Keep.
- Cash: Slightly increase from exit proceeds.

**Trade today:** Sell 1% KBANK at market open. Exits for positions you hold are **same-day urgent** — the model is confidently bearish, don't wait for month-end new entries (PTT add, AAPL buy) wait for the monthly rebalance in §4.

---

### Scenario B: High Uncertainty Day

**Morning Brief:**
```
🟢 BULLISH: (none — all flags are 🟡 or 🔴)
Median band width: 38%
# red-flagged: 42
```

**Decision:**
- **Stay in cash.** The model's confidence is low across all 100 tickers. Trading in this environment is gambling.
- Exception: If a position you hold shows 🟢↓ (confidently bearish) with a band narrower than the median, consider reducing.
- Come back tomorrow and re-run.

**If 3+ consecutive days of all-🔴 or median band width > 30%:**
- The model has entered a regime it does not understand (earnings season, policy surprise, macro shock).
- Reduce all positions by 50% and go to 75% cash.
- Do not re-enter until median band width drops below 20% for 2 consecutive days.

---

### Scenario C: Regime Change Detected

**Weekly Quant review:**
```
── thai_equity ──
  HistVol: 35%  ← was 18% last week
  Warning: >30% threshold exceeded
```

**Decision:**
- Halve Thai equity allocation from 40% to 20%.
- Move freed capital to cash.
- Do not re-enter Thai equity until HistVol drops below 30% for 2 consecutive weeks.

---

## 7. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Notebook says "No module named kth" | kth package not installed | `python -m pip install -e .` |
| GPU out of memory | Model + batch too large | Reduce `n_samples = 5` in Cell 0 |
| Forecasts looking stale | Cache not refreshed | Delete `data/forecast_cache/NeoQuasar_Kronos-small/YYYY-MM-DD/` for today and re-run |
| `pd.bdate_range` error | Old cached file | Delete full `data/forecast_cache/NeoQuasar_Kronos-small/` and re-run |
| 60/40 benchmark = 0.00 | TLT.parquet not cached | Run `python -c "from kth.data.loader import download_universe; download_universe(['TLT'], period='max')"` |
| Missing tickers in Morning Brief | Ticker has <400 rows of history | GULF.BK etc. need more data — check `data/raw/GULF.BK.parquet` row count |
| All signals 🟡 | Typical on volatile days | Accept it. The model only produces 🟢 on ~30% of days. |
| "⚠ 1 ticker excluded — price anomaly: DELTA.BK" | Price moved >30% since last bar | Check `data/logs/sanity_YYYY-MM-DD.json`. If it's a real corporate action, wait for yfinance to adjust. If it's a data error, delete and re-download that ticker's parquet. |
| Cron failed — no LINE Notify received | `LINE_NOTIFY_TOKEN` not set | Add `export LINE_NOTIFY_TOKEN="your-token"` to `~/.bashrc` and reload shell. Get your token at notify.line.me/my. |
| Top-ranked ticker not in buy list | Sector concentration guard | System limits 2 positions per SET sector. If 2 Banking stocks are already held, no new Banking picks appear. This is intentional. |
| T+2 warning in trade ticket | Exits and buys on same day | Exit proceeds won't settle until T+2. Buy only from existing cash balance, not sale proceeds. Normal Thai equity settlement. |
| Grind tile shows red | Portfolio dropped >3% over 5 days | Reduce allocation band by one step immediately (e.g. BULL→NEUTRAL). Do not open new positions until Grind clears (5-day return > −3%). |
| Bootstrap p-value shows "—" | < 20 trading days of history | Normal. Shows after ≥ 20 paper trading days. Not related to backtest p-values. |
| Band coverage shows "—" | No historical forecast cache | Shows after 20+ forecast dates accumulate. Calibration compares P5/P95 bands to actual outcomes. |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                  KRONOS-TH QUICK REFERENCE                   │
├──────────────┬──────────────────────────────────────────────┤
│ DAILY        │ 1. Dashboard opens at http://localhost:5555  │
│ (~15 min)    │ 2. Check Risk Bar: Market / Alloc / Grind    │
│              │ 3. Grind tile RED → reduce allocation now    │
│              │ 4. Review Trade Ticket exits (urgent!)       │
│              │ 5. Note T+2 warning if exits + buys same day │
│              │ 6. Record paper trades, log note             │
├──────────────┼──────────────────────────────────────────────┤
│ WEEKLY       │ 1. Check Signal Health row (collapsible)     │
│ (~15 min)    │ 2. Band coverage < 80% → model overconfident │
│              │ 3. Bootstrap p-value trend (improving?)      │
│              │ 4. Check allocation drift (positions >25%)   │
│              │ 5. Note sector concentration — max 2/sector  │
├──────────────┼──────────────────────────────────────────────┤
│ MONTHLY      │ 1. Apply 3-filter rule per position          │
│ (~30 min)    │ 2. Compare live CAGR vs backtest 31.44%      │
│              │ 3. Build trade list, spread over 2-3 days    │
│              │ 4. Adjust allocation bands if Sharpe changed │
├──────────────┼──────────────────────────────────────────────┤
│ QUARTERLY    │ 1. Compare your CAGR vs backtest benchmarks  │
│ (~30 min)    │ 2. Review position sizing compliance         │
│              │ 3. Adjust allocation targets if needed       │
└──────────────┴──────────────────────────────────────────────┘

NEW ALERTS TO KNOW:
  🔴 GRIND    Portfolio dropped >3% over 5 days → reduce allocation
  ⚠ T+2      Exit proceeds settle T+2, buy from existing cash only
  ⚠ SANITY   Ticker excluded (>30% price move) — check sanity log
  p=0.05 ✅  Bootstrap p-value: live alpha is statistically real
  p=0.30 ❌  Bootstrap p-value: no confirmed edge yet (keep going)
```

---

*Document version: 2026-06-03. Updated: sector guard, T+2 warning, Grind tile, Signal Health, sanity filter, bootstrap p-value, LINE Notify documented. Superseded by dashboard for daily operations. Remains authoritative for decision rules.*
