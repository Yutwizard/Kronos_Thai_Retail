# Kronos-TH — Local Dashboard User Manual (Flask)

> **Reference manual — detailed step-by-step procedures.**
>
> **Read this first:** [Getting Started Guide](getting-started.md) — installation, glossary, paper trading basics, day-by-day first week walkthrough.
>
> This manual assumes you've completed setup and understand the basic concepts (paper trading, confidence flags, allocation bands). It provides the full daily/weekly/monthly/quarterly operating procedures for the dashboard. If you encounter a term you don't recognize, check the [glossary](getting-started.md#5-glossary--words-you-need-to-know).
>
> Thai equity only. 500,000 THB starting capital. Not financial advice.
>
> **Alternative dashboard available:** A second dashboard option exists — the **Google Suite dashboard** (`docs/SETUP_GUIDE.md`), which is zero-cost, browser-based, and requires no local GPU. Both dashboards reached feature parity on 2026-06-06. Choose based on your environment:
> - **This Flask dashboard** — local Python + GPU, run via `scripts/dashboard.py`, requires cron or manual start
> - **Google Suite dashboard** — Kaggle (primary) / Colab (backup) + Sheets + Apps Script, runs in any browser, no local install
>
> Both are fully functional. This Flask manual remains the authoritative reference for Flask-specific features.

---

## Table of Contents

1. [What the Dashboard Does](#1-what-the-dashboard-does)
2. [Quick Start (5 minutes)](#2-quick-start-5-minutes)
3. [Daily Morning Routine (15 min)](#3-daily-morning-routine-15-min)
4. [Understanding the Dashboard](#4-understanding-the-dashboard)
5. [Weekly Review (20 min)](#5-weekly-review-20-min)
6. [Monthly Rebalance (30 min)](#6-monthly-rebalance-30-min)
7. [Emergency Protocols](#7-emergency-protocols)
8. [Phase 2: Going Live](#8-phase-2-going-live)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What the Dashboard Does

The dashboard is a **local web application** that:

1. **Generates forecasts** — Kronos-small model predicts 20-day expected returns for 49 Thai stocks
2. **Creates trade tickets** — exact share lots (100-share board lots), limit prices, buy/exit recommendations
3. **Tracks a paper portfolio** — simulated P&L with friction costs, stop-loss, and risk metrics
4. **Exports broker-ready CSV** — when you're ready for real trading, click to get instructions

**What it does NOT do:**
- Does NOT connect to your broker (Settrade, Bualuang, etc.)
- Does NOT place orders automatically
- Does NOT require internet for the dashboard (only for data download via cron)

### One-command launcher (recommended)

For a fresh Linux box, just run:
```bash
./scripts/start_dashboard.sh
```
This idempotent script creates the venv, installs both `requirements.txt` and `requirements-ml.txt`, downloads data (skips if any parquet < 24h old), runs the forecast pipeline, starts the server on port 5555, and waits for `/api/health`. Subcommands: `stop`, `restart`, `status`, `logs`, `clean`. Run `./scripts/start_dashboard.sh help` for full usage.

### Dashboard URL

```
http://localhost:5555
```

The dashboard runs on your computer only. Nobody else can access it.

---

## 2. Quick Start (5 minutes)

### Prerequisites

- [ ] Kronos-TH installed: `pip install -e .` from project root
- [ ] GPU available (GTX 1060 or better, or Google Colab T4)
- [ ] Kronos repo cloned: `git clone https://github.com/shiyu-coder/Kronos.git kronos_repo`
- [ ] 49 Thai equity parquet files in `data/raw/` (run `python scripts/download_data.py` once)

### Step 1: Generate First Forecasts

> **Recommended: run the pipeline in the EVENING after SET closes (17:00 BKK).**
> This uses today's close prices and means tomorrow morning you just open the
> dashboard and trade — no waiting 12 minutes before the market opens.
> Alternatively, run in the morning (06:15–06:30) if you prefer morning-only.

Either click **▶ Run Pipeline** in the dashboard header, or from terminal:

```bash
cd /path/to/kronos-th
venv/bin/python scripts/dashboard.py --generate
```

This takes **~12 minutes on GTX 1060** (~3 minutes on T4). It downloads latest
price data, runs Kronos-small on all 49 Thai tickers, and generates a trade ticket.

### Step 2: Start the Dashboard

```bash
venv/bin/python scripts/dashboard.py --serve
```

You'll see:
```
Kronos-TH Dashboard — PAPER mode
Open: http://localhost:5555
```

### Step 3: Open Your Browser

Go to `http://localhost:5555`. You should see the dashboard with today's forecasts.

### Step 4: Set Up Daily Automation

**Recommended: run at 17:30 BKK (after market close)** so tomorrow's forecast uses today's close prices.

> **If using Kaggle (Google Suite dashboard):** scheduling is handled on the Kaggle platform — no cron needed. See `docs/SETUP_GUIDE.md`.

```bash
crontab -e
```

Add (pick one):
```bash
# Recommended — evening run (after SET closes at 17:00)
30 17 * * 1-5 cd /path/to/kronos-th && bash scripts/cron_pipeline.sh

# Alternative — morning run (before SET opens at 10:00)
30 6 * * 1-5 cd /path/to/kronos-th && bash scripts/cron_pipeline.sh
```

The dashboard server must be kept running separately. Use `systemd` or `screen`/`tmux`:
```bash
# Option A: tmux (simple)
tmux new -s kronos
venv/bin/python scripts/dashboard.py --serve
# Ctrl+B, D to detach

# Option B: systemd (persistent across reboots)
# See Appendix A below
```

> **Note to Windows/Mac users:** `crontab` and `systemd` are Linux tools. On Windows, use Task Scheduler. On Mac, use `launchd`. Alternatively, just run the commands manually each morning — no automation required.

> **Timezone:** The crontab example uses `30 6` which means 06:30 *in your computer's local timezone*. If your machine is not set to Bangkok time (UTC+7), adjust the cron time accordingly. Thai market opens at 10:00 BKK, so any time between 06:00–09:00 BKK works.

---

## 3. Daily Routine

### Recommended: Evening Run + Morning Check

**Evening (after SET closes 17:00):** Click **▶ Run Pipeline** or run `--generate`.
Uses today's close prices. Tomorrow morning just open the dashboard and trade.

**Morning (before SET opens 10:00):** Open `http://localhost:5555`.
Trade Ticket is ready from last night's run. No waiting for GPU.

### If you use morning-only run:

Run pipeline at 06:15–06:30, wait 12 min, then follow the steps below.

### 09:30 — Open the Dashboard

Go to `http://localhost:5555`. The forecasts should already be ready.

### Step 1: Check the Risk Bar (10 seconds)

Look at the **top row of tiles**:

| Tile | What to Check | Red Flag |
|------|-------------|----------|
| **Market State** | Should say **Normal** | **Turmoil** → stay cash today |
| **Allocation** | BULL 15% / NEUTRAL 10% / BEAR 5% | **EXIT 0%** → no positions allowed |
| **Drawdown** | Should be ≥ −3% (green) | **< −7%** (red) → reduce exposure |
| **P&L MTD** | Positive is good | Large negative → review positions |

**If Market State = TURMOIL or Allocation = EXIT → STOP. Stay in cash. Check back tomorrow.**

### Step 2: Review the Trade Ticket (5 minutes)

The **Trade Ticket** panel shows what to do today:

```
▼ EXIT (same day, market order)
  KBANK.BK    3,500 shares    market    ~497,000 THB    🟢↓ bearish net_ret=−2.34%

▲ BUY (within 2 days)
  CPALL.BK      800 shares    limit 56.70    ~45,360 THB    🟢↑ rank#3 net_ret=+1.01%
  AOT.BK        800 shares    limit 59.20    ~47,360 THB    🟢↑ rank#4 net_ret=+0.88%

Cash flow: +497,000 (sells) −92,720 (buys) −1,580 (friction) = +402,700 THB net
```

**Decision rules:**

1. **Exits are URGENT.** If you see a green-flag downward-arrow (🟢↓) on a stock you hold, **exit same day with a market order.** Do not wait. The model is confidently bearish.

2. **Buys within 2 days.** Green-flag upward-arrow (🟢↑) entries can wait. Use limit orders. Spread across 1–2 days.

3. **Yellow flags = half-size.** If a held stock shows 🟡, reduce by 50%.

4. **Check the cash flow.** If net cash flow after friction is negative, skip the trade. Friction matters at small scale.

5. **T+2 warning (yellow banner).** If exits and buys appear on the same day, a banner reads: *"Exit proceeds settle [date] (T+2). Today's buys draw from existing cash only."* Thai equity settles in 2 business days — don't assume the exit cash is available for new buys on the same day. Only buy using pre-existing cash.

6. **Sector guard (silent).** The buy list never shows more than 2 picks from the same SET sector. If the top 5 ranked stocks are all Banking, only 2 will appear. This is intentional — concentrated sector exposure amplifies single-sector shocks. You'll notice it when a highly-ranked ticker is absent; this is the system protecting you.

### Step 3: Record Paper Trades (2 minutes)

Click the **"Record Paper Trade"** button. This records all exits and buys in today's ticket as simulated trades at the limit prices shown.

After clicking, you'll see a confirmation: "3 trades recorded. Portfolio value: 512,300 THB."

**Recording a trade that isn't in the ticket (manual entry):** click **"➕ Add Manual Trade"**
to record an ad-hoc buy/sell — handy on days the pipeline didn't run (no ticket) or when you
traded something off-signal. Enter ticker, action (buy / exit / reduce), shares (multiple of
100), and your fill price. It's recorded immediately and appears in Trade History; the
portfolio recalculates. A buy needs enough cash; an exit/reduce needs an existing position.

### Step 4: Review Positions (2 minutes)

Scroll to **Current Positions**. Check:

- **P&L% column** — any position down > −10%? Consider exiting regardless of signal.
- **Weight% column** — any position > 25% of portfolio? Add to monthly rebalance plan.
- **Total exposure** in the risk bar — should be < 20% (15% in BULL, 10% in NEUTRAL, 5% in BEAR).

> **Weekly vs monthly allocation checks:**
> | When | Rule | Purpose |
> |------|------|---------|
> | Weekly | Flag positions >25% or <5% weight | Catch drift early; note for rebalance plan |
> | Monthly | Enforce positions within 15-25% weight (3-filter rule §6) | Hard rebalance — exit positions outside range

### Step 5: Quick Scan — Full Ranking (1 minute)

Open the **Full Ranking (49 tickers)** panel at the bottom (click to expand). Scan for:

- How many tickers are 🟢 green? (Model is confident)
- How many tickers are 🔴 red? (>30 red = high uncertainty, reduce exposure)
- Any surprise tickers in top/bottom 5? (Sanity check)

### Step 6: Log Notes (1 minute)

Make a mental or written note:
```
Date: 2026-06-02
Buys: CPALL (800), AOT (800)
Exits: KBANK (3,500)
Market state: Normal
Allocation: NEUTRAL 10%
```

---

## 4. Understanding the Dashboard

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Kronos-TH Dashboard | 📋 PAPER | Date/Time         │
├─────────────────────────────────────────────────────────────┤
│ RISK BAR: Market | Alloc | Sharpe | Drawdown | Grind | P&L | Win | Exp │
├─────────────────────────────────────────────────────────────┤
│ TRADE TICKET (hero, full width)                             │
│  ▼ EXIT: KBANK.BK 3,500 market                              │
│  ▲ BUY:  CPALL.BK 800 limit 56.70                           │
│  [Record Paper Trade] [➕ Add Manual Trade] [Export]        │
├──────────────────────────┬──────────────────────────────────┤
│ CURRENT POSITIONS        │ MORNING BRIEF — Top 10          │
│  PTT.BK  +2.2%  HOLD     │  1. PTT.BK    +2.31%  🟢       │
│  SCC.BK  +1.2%  HOLD     │  2. SCC.BK    +1.80%  🟢       │
│  KBANK.BK −2.1%  EXIT    │  3. CPALL.BK  +1.55%  🟢       │
├──────────────────────────┴──────────────────────────────────┤
│ FULL RANKING (collapsible) — 49 tickers, searchable         │
└─────────────────────────────────────────────────────────────┘
```

### Morning Brief — Top 10 and Full Ranking

Both panels now show a **📅 Data: YYYY-MM-DD** badge in the heading showing which closing date's prices power the forecast. Hover any column header `(?)` for a plain-English definition; a legend bar below each table summarises all columns.

| Column | Meaning |
|---|---|
| **Exp Ret** | Model's predicted price change over 20 trading days |
| **Δ Prev** | Change in Exp Ret since the previous pipeline run. ▲=more bullish, ▼=less bullish |
| **Band** | Uncertainty: (P95−P5)/Close. <10%=🟢, 10–30%=🟡, >30%=🔴. Band and Flag show the same thing |
| **Flag** | Colour-coded Band. ↗ badge = confidence improved since last run; ↘ = downgraded (explains HOLD→REDUCE) |
| **Net Ret** | Expected return after round-trip friction costs |

**Full Ranking date selector** — Expand Full Ranking ▼ to see a date dropdown alongside the search box. Select any past pipeline run date to view that day's complete 49-ticker ranking with Δ vs the day before it. Useful for reviewing what signals looked like on a specific date.

**To backfill a missing date** (e.g., a holiday when the pipeline wasn't run): the system can regenerate forecasts for any historical date using the price data available on that date — ask Claude Code to run the backfill. After backfilling, the date appears in the dropdown automatically.

### Color Coding

| Color | Confidence Band | Meaning | Action |
|-------|----------------|---------|--------|
| 🟢 Green | ≤ 10% | High confidence | Full position |
| 🟡 Yellow | 10%–30% | Moderate | Half-size |
| 🔴 Red | > 30% | Low confidence | Skip / stay away |

### Risk Bar Reference

| Metric | Source | Normal Range | Action if bad |
|--------|--------|-------------|---------------|
| Market State | Median band width + red flag count | Normal | Turmoil → stay cash |
| Allocation | Trailing Sharpe (12-week) | BULL 15% to EXIT 0% | EXIT → liquidate |
| Trailing Sharpe | Paper portfolio equity curve | > 1.0 is good | < 0 → EXIT band |
| Drawdown | Peak-to-trough | > −3% is fine | −10% → circuit breaker |
| **Grind** | 5-day portfolio return | 0% (flat) | < −3% over 5 days → reduce allocation now, before −10% triggers |
| P&L MTD | Month-to-date | Positive | Negative streak → weekly review |
| Win Rate | FIFO-matched closed trades | > 50% is good | < 40% for 2 wks → half sizes |
| Exposure | Position value / total value | 5–20% typical | > 25% → concentrated |

> **Grind** is a slow-regime warning. The circuit breaker triggers at −10% drawdown; Grind triggers at −3% over 5 consecutive days — catching deterioration before it becomes a crisis. When Grind fires: reduce your allocation band by one step (e.g. BULL→NEUTRAL) and do not open new positions until the tile clears.

### Signal Health Row (collapsible, below risk bar)

Four metrics displayed inline. All show "—" until enough live trading history exists.

| Metric | What it means | Threshold |
|--------|--------------|-----------|
| Trailing accuracy | % of last 20 trades where model predicted direction correctly | < 45% → 🚨 model review |
| Live vs backtest Sharpe | Difference between your live Sharpe and backtest Sharpe (1.40) | > 0.5 gap → investigate execution |
| **Band coverage** | % of past prices that actually fell within the model's P5/P95 band | 80–95% = good; < 80% = overconfident; shows "—" until 20+ forecast dates accumulate |
| **Bootstrap p-value** | Statistical test: is your live alpha real or luck? Centered resampling, n=1,000 | p < 0.05 ✅ edge confirmed; p ≥ 0.15 ❌ no confirmed edge; "—" until ≥ 20 trading days |

> **Important:** The bootstrap p-value here is for your **live paper trading only**. The historical backtest p-values (p=0.015 in 2024 etc.) are a separate t-test and are not affected by this metric.

Alerts:
- "⚠ Forecasts from 2026-06-01 — stale" → cron failed. Run pipeline manually.
- "🚨 Model review recommended — halve position sizes" → accuracy < 45% or live Sharpe < 0.5 for 2+ weeks.

### Current Positions Table

Shows each held position enriched with the **latest forecast signal** so you can see at a glance whether to hold, reduce, or exit each position.

| Column | Meaning |
|---|---|
| **Avg Cost** | Your fill price at trade entry (fixed) |
| **Mark** | Latest closing price (updates each pipeline run) |
| **P&L%** | (Mark − Avg Cost) / Avg Cost |
| **Exp Ret** | Model's current 20-day expected return for this ticker |
| **Δ Prev** | Change in Exp Ret since previous pipeline run |
| **Band** | Uncertainty — <10%=🟢, 10–30%=🟡, >30%=🔴 |
| **Signal** | Flag + ↗↘ badge if confidence changed |

Row border colour: **green** = bullish hold (🟢↑) | **orange** = reduce signal (🟡, model uncertain) | **red** = exit signal (🟢↓).

> **Note on timing:** Exp Ret and Band reflect the **most recent pipeline run**. If you ran the pipeline in the evening, these columns show tonight's forecast (using today's close prices) — which is more relevant for tomorrow's decisions than the morning forecast that drove today's trades.

---

## 5. Weekly Review (20 min)

**When:** Sunday evening or Monday morning before market open.

### Step 1: Check for Volatility Spikes

Open the **Full Ranking** panel. Look at the "Band" column. If **>5 tickers have band > 30%**, the market is in a high-volatility regime. **Halve your allocation** (e.g., if NEUTRAL at 10%, drop to 5%).

### Step 2: Review Signal Accuracy

Check the dashboard's **Win Rate** in the risk bar. Should be ≥ 50%. If below 40% for 2+ weeks, the model may be degrading. Reduce position sizes by 50% until accuracy recovers.

### Step 3: Allocation Drift Check

In **Current Positions**, scan the **Weight%** column:
- Any position > 25% → over-concentrated, add to monthly rebalance sell list
- Any position < 5% → too small to matter, either add or exit

### Step 4: Compare Live vs Paper (Phase 2 only)

If you've entered live trades, compare your broker statement against the dashboard's P&L. Record any discrepancies > 1% and investigate (slippage, wrong fill time, dividend adjustment).

### Step 5: Export Broker CSV (Phase 2 only)

Click **"Export for Broker"** to download a CSV of the week's consolidated trade instructions.

---

## 6. Monthly Rebalance (30 min)

**When:** Last Friday of each month.

### Step 1: 3-Filter Position Review

For every stock you hold, apply these 3 filters:

| # | Filter | Rule | Action if FAIL |
|---|--------|------|----------------|
| 1 | **Net Return** | Net return > 2× friction (0.54% for Thai equity) | Consider exit |
| 2 | **Confidence** | Flag is 🟢 or 🟡 | Consider exit if 🔴 |
| 3 | **Allocation** | Position weight within 15–25% | Add to rebalance |

- **All 3 pass:** Maintain or add
- **1–2 fail:** Reduce by half
- **All 3 fail:** Exit entirely

### Step 2: Compare to Benchmarks

Check your month-end metrics against backtest benchmarks:

| Metric | Your Dashboard | Backtest (2022–2024) |
|--------|---------------|----------------------|
| CAGR | _from risk bar_ | +31.44% annualized |
| Sharpe | _from risk bar_ | 1.40 |
| Win Rate | _from risk bar_ | ~60% |
| Max DD | _from risk bar_ | −17.97% |

If your live numbers are below the backtest range for 2+ consecutive months, review your execution fidelity.

### Step 3: Adjust Allocation Bands

- Trailing Sharpe > 1.5 for 2 consecutive months → raise BULL to 20%, NEUTRAL to 12%
- Trailing Sharpe < 0.5 for 2 consecutive months → revert BULL to 15%, NEUTRAL to 5%
- **Hard caps:** BULL max 25%, NEUTRAL min 5%

### Step 4: Execute Rebalance Over 2–3 Days

- **Day 1:** Exit all positions flagged for removal
- **Day 2:** Enter new positions
- **Day 3:** Adjust existing positions (size up/down)

Never execute all trades on one day — spread to reduce market impact.

---

## 6.5 Quarterly Performance Review (15 min)

**When:** End of March, June, September, December.

### Step 1: Export Monthly Logs

Check the risk bar metrics for the past 3 months (you should have these from your daily log notes). The dashboard tracks the equity curve automatically.

### Step 2: Compare to Backtest Benchmarks

| Metric | Expected Range | Red Flag |
|--------|---------------|----------|
| CAGR (annualized) | 14% to 48% (backtest 31.44% ± 1.5σ) | Below 14% for 2 quarters |
| Sharpe | > 0.9 | Below 0.5 for 2 quarters |
| Win Rate | > 50% | Below 40% for 2 quarters |
| Max Drawdown | > −18% | Crosses −10% (emergency trigger) |

If any metric is in the red flag zone for 2 consecutive quarters, review:
1. Are you over-trading? (friction > 6% of AUM/year)
2. Are you ignoring bearish exit signals?
3. Is the model degrading? (run the [weekly signal check](#step-2-review-signal-accuracy))

### Step 3: Adjust Band Caps

- Trailing Sharpe > 1.5 for 2 consecutive quarters → raise BULL cap to max 25%
- Trailing Sharpe < 0.5 for 2 consecutive quarters → revert to default bands (BULL 15%, NEUTRAL 10%)

---

## 7. Emergency Protocols

These trigger automatically in the dashboard. The trade ticket will be hidden or show a red banner.

| Trigger | Dashboard Shows | What You Do |
|---------|----------------|-------------|
| **−10% Drawdown** | "STOP-LOSS TRIGGERED. Portfolio frozen." | All positions liquidated. Wait for re-entry checklist. |
| **3 consecutive all-red days** | Red banner, trade ticket hidden | Reduce all positions by 50%. Go to 75% cash. |
| **Market State = Turmoil** | Risk bar shows "Turmoil" in red | Stay in cash. Do not trade. Check tomorrow. |
| **>10 tickers with HistVol > 30%** | (Check Full Ranking bands) | Halve allocation. Move freed capital to cash. |
| **Single ticker P&L < −15%** | Visible in Current Positions | Exit that ticker. Do not re-enter this month. |

### Stop-Loss Re-Entry Checklist

After a −10% drawdown trigger, you must meet ALL 4 conditions before trading again:

- [ ] 10 trading days have passed since liquidation
- [ ] Median band width < 20% for 5 consecutive days
- [ ] ≥ 5 tickers showing 🟢 confidence
- [ ] Click "Reactivate" button in dashboard (appears when conditions met)

**No judgment calls. No exceptions.**

---

## 8. Phase 2: Going Live

Do NOT skip to Phase 2. The gate exists for a reason.

### Gate Requirements (ALL must pass)

- [ ] Paper traded ≥ 4 weeks (20+ trading days)
- [ ] ≥ 10 round-trip trades in paper
- [ ] Win rate ≥ 50% (FIFO-matched)
- [ ] Live Sharpe ≥ 0.90 (within 0.5 of backtest 1.40)
- [ ] No stop-loss trigger in paper period
- [ ] ≥ 3 full monthly rebalances executed in paper

### Check Gate Status

Click the **Phase 2 Gate** endpoint:
```
http://localhost:5555/api/phase2_gate
```

Returns JSON showing which checks pass/fail.

### Switching to Live Mode

When all 6 checks pass:
```bash
KRONOS_MODE=live venv/bin/python scripts/dashboard.py --serve
```

The dashboard header changes from **📋 PAPER** (blue) to **💰 LIVE** (red). The button changes from "Record Paper Trade" to "Confirm Live Trade."

### Executing Live Trades

1. Review the trade ticket in the dashboard
2. Click **"Export for Broker"** → downloads a CSV
3. Open your broker app (Settrade, Bualuang, KTB, etc.)
4. Enter orders manually using the CSV as reference
5. Record actual fill prices in `data/positions/live_portfolio.json`
6. Weekly: compare live P&L vs dashboard paper P&L

---

## 9. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Dashboard shows "No forecasts" | Cron didn't run or GPU was busy | Run `venv/bin/python scripts/dashboard.py --generate` manually |
| "⚠ Forecasts from yesterday — stale" | Cron failed | Check `data/logs/cron_{date}.log` for errors. Re-run --generate. |
| No buy signals appear | Market is uncertain or net returns are below friction | Check Full Ranking — if >30 tickers are 🔴, it's a high-uncertainty day. Stay cash. |
| "Record Paper Trade" does nothing | No trade ticket exists | First run `--generate` to produce forecasts, then refresh the dashboard — or use **➕ Add Manual Trade** to log a buy/sell without a ticket |
| Dashboard won't start (port 5555 in use) | Another instance is running | `kill $(lsof -t -i:5555)` then restart |
| All signals are 🟡 or 🔴 | Typical on volatile days | The model produces 🟢 on ~30% of days. Accept it. |
| Friction cost seems high | Thai broker fees + SET fees add up | 0.27% one-way is the hardcoded estimate. If your broker is cheaper, update `FRICTION` in `kth/data/universe.py`. |
| Dashboard shows old data | Browser cached the page | Hard refresh (Ctrl+Shift+R). The dashboard polls every 60s automatically. |

---

## Appendix A: systemd Service (Persistent Dashboard)

Create `/etc/systemd/system/kronos-dashboard.service`:

```ini
[Unit]
Description=Kronos-TH Dashboard
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/kronos-th
Environment=KRONOS_MODE=paper
ExecStart=/path/to/kronos-th/venv/bin/python scripts/dashboard.py --serve
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kronos-dashboard
sudo systemctl start kronos-dashboard
```

---

## Appendix B: Quick Reference Card

```
┌──────────────────────────────────────────────────────────────┐
│               KRONOS-TH DASHBOARD QUICK REF                   │
├──────────────────────────────────────────────────────────────┤
│ SETUP (once)                                                 │
│   pip install -e .                                           │
│   python scripts/download_data.py                            │
│   python scripts/dashboard.py --generate                     │
│   python scripts/dashboard.py --serve                        │
│   http://localhost:5555                                      │
├──────────────────────────────────────────────────────────────┤
│ DAILY (15 min, 06:45 BKK)                                    │
│   1. Check Risk Bar → Market State Normal? Allocation OK?    │
│   2. Review Trade Ticket → Exits URGENT (same day, market)   │
│   3. Click "Record Paper Trade"                              │
│   4. Scan Positions → any > −10% P&L?                        │
│   5. Expand Full Ranking → sanity check                      │
├──────────────────────────────────────────────────────────────┤
│ WEEKLY (20 min, Sunday/Monday)                               │
│   1. >5 tickers with band > 30%? → halve allocation          │
│   2. Win rate < 40% for 2 weeks? → halve position sizes      │
│   3. Any position > 25%? → add to monthly rebalance          │
├──────────────────────────────────────────────────────────────┤
│ MONTHLY (30 min, Last Friday)                                │
│   1. 3-filter rule per position (net, confidence, alloc)     │
│   2. Compare metrics vs backtest benchmarks                  │
│   3. Adjust allocation bands if Sharpe sustained high/low    │
│   4. Execute over 2-3 days (Day1=exits, Day2=buys, Day3=adj)│
├──────────────────────────────────────────────────────────────┤
│ EMERGENCY                                                    │
│   −10% DD → ALL liquidated. 4-item re-entry checklist.       │
│   Turmoil → Stay cash. Check tomorrow.                       │
│   3 all-red days → Reduce 50%. 75% cash.                     │
└──────────────────────────────────────────────────────────────┘
```

---

*Document version: 2026-06-02. Companion to operations-manual.md. See also: spec at docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md.*
