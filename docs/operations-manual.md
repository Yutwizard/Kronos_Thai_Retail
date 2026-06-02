# Kronos-TH Operations Manual

> **Reference document — decision rules and methodology.**
>
> For daily use, start here:
> - **New to Kronos?** → [Getting Started Guide](getting-started.md) (installation, paper trading, day-by-day walkthrough)
> - **Using the dashboard?** → [Dashboard User Manual](dashboard-user-manual.md) (step-by-step operating procedures)
>
> This operations manual documents the original notebook-based workflow. The dashboard automates most of these steps. The decision rules (3-filter, signal interpretation, risk controls) remain authoritative and are referenced by the dashboard.

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

## 2. Daily Evening Check (2 minutes)

### Objective
Verify that today's forecast cache was saved and is ready for tomorrow.

### Steps

```bash
ls -la data/forecast_cache/NeoQuasar_Kronos-small/$(date +%Y-%m-%d)/ | head -5
```

Expected output (example):
```
total 1234
drwxrwxr-x 100 Dec 31 23:59 .
drwxrwxr-x 100 Dec 31 23:59 ..
-rw-rw-r-- 1 user user 1234 PTT.BK.parquet
-rw-rw-r-- 1 user user 1234 KBANK.BK.parquet
```

If this directory is empty, tomorrow's morning run will regenerate forecasts (12 min delay). If the directory is missing, the morning run will create it — no problem, just 12 minutes of GPU time.

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

> **Note on cash drag:** The backtest always deploys 100% of capital (equal-weight across all positions). Confidence-based sizing in real trading leaves more cash — 50-80% deployment is normal. This is intentional: sitting in cash when conviction is low prevents you from trading on noise. The backtest's CAGR already accounts for friction, not for cash drag. Expect 1-3% of CAGR to come from cash allocation drag in real trading.

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
initial_cash = 1_000_000  # 1M THB starting portfolio

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
| Forecasts looking stale | Cache not refreshed | Delete `data/forecast_cache/NeoQuasar_Kronos-small/` and re-run |
| `pd.bdate_range` error | Old cached file | Delete `data/forecast_cache/NeoQuasar_Kronos-small/` and re-run |
| 60/40 benchmark = 0.00 | TLT.parquet not cached | Run `python -c "from kth.data.loader import download_universe; download_universe(['TLT'], period='max')"` |
| Missing tickers in Morning Brief | Ticker has <400 rows of history | Tick the "skipped" line in Cell 3 output — GULF.BK etc. need more data |
| All signals 🟡 | Typical on volatile days | Accept it. The model only produces 🟢 on ~30% of days. |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                  KRONOS-TH QUICK REFERENCE                   │
├──────────────┬──────────────────────────────────────────────┤
│ DAILY        │ 1. Open notebook, set REPORT_MODE="morning"  │
│ (~15 min)    │ 2. Run all cells, wait 12 min for forecasts  │
│              │ 3. Scan bullish top-10, bearish bottom-10    │
│              │ 4. Check holdings vs bearish list            │
│              │ 5. If you hold a bearish 🟢↓ → consider exit  │
├──────────────┼──────────────────────────────────────────────┤
│ WEEKLY       │ 1. Set REPORT_MODE="quant"                   │
│ (~15 min)    │ 2. Check HistVol for regime changes          │
│              │ 3. Note allocation drift                      │
├──────────────┼──────────────────────────────────────────────┤
│ MONTHLY      │ 1. Set REPORT_MODE="trader"                  │
│ (~30 min)    │ 2. Apply 3-filter rule per position          │
│              │ 3. Build trade list, spread over 2-3 days    │
├──────────────┼──────────────────────────────────────────────┤
│ QUARTERLY    │ 1. Compare your CAGR vs backtest benchmarks  │
│ (~30 min)    │ 2. Review position sizing compliance         │
│              │ 3. Adjust allocation targets if needed       │
└──────────────┴──────────────────────────────────────────────┘
```

---

*Document version: 2026-05-24. Any questions: open a GitHub issue.*
