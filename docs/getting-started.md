# Kronos-TH — Getting Started Guide

> **You don't need to be a programmer or a professional trader to use this.**
> If you can open a web browser and copy-paste commands, you can run Kronos-TH.
> This guide assumes you've never used a terminal, Python, or an AI trading system before.

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [Installation (15–30 minutes, one-time)](#2-installation-1530-minutes-one-time)
3. [Your First Run](#3-your-first-run)
4. [Paper Trading Explained](#4-paper-trading-explained)
5. [Glossary — Words You Need to Know](#5-glossary--words-you-need-to-know)
6. [Your First Week — Day-by-Day](#6-your-first-week--day-by-day)
7. [Daily Routine (After You Know the System)](#7-daily-routine-after-you-know-the-system)
8. [What Could Go Wrong? (Honest Numbers)](#8-what-could-go-wrong-honest-numbers)
9. [Graduating to Real Money (Phase 2)](#9-graduating-to-real-money-phase-2)
10. [Where to Go Next](#10-where-to-go-next)

---

## 1. What Is This?

Kronos-TH is an **AI-powered daily report** for Thai stock investors. It:

1. Looks at 49 Thai stocks every morning
2. Predicts which ones are likely to go up or down over the next 20 trading days
3. Shows you exactly what to buy, what to sell, and how many shares — down to the exact lot size
4. Tracks your (simulated) portfolio so you can see if the strategy works before risking real money

**It does NOT:**
- Connect to your broker or place orders for you
- Guarantee profits (markets are unpredictable)
- Replace your own judgment. Think of it as a very well-informed second opinion.

**The numbers that matter:**
- Starting capital: **500,000 THB** (you choose, but this is the default)
- Stocks covered: **49 Thai stocks** (SET50 index plus mid-caps; 1 of the 50 universe tickers has insufficient price history for the model's 400-day lookback window and is skipped during forecast generation)
- Time per day: **15 minutes** (after initial setup)
- Backtest result: +31.44% per year (2022–2024), but **past performance does not guarantee future results**

---

## 2. Installation (15–30 minutes, one-time)

### Prerequisites — Do You Have These?

| Requirement | How to Check | If You Don't Have It |
|-------------|-------------|----------------------|
| **A computer** | You're reading this, so yes | Any Windows/Mac/Linux computer works |
| **NVIDIA GPU** | See step 2.1 below | Use Google Colab or Kaggle (both free, T4 GPU) — slower but works |
| **Python 3.10+** | See step 2.2 below | Download from python.org (free) |
| **Internet** | You're reading this, so yes | Need ~1 GB for initial download, then ~5 MB/day |

### Step 2.1: Check Your GPU

**Windows:** Right-click desktop → NVIDIA Control Panel → System Information. Look for "GeForce GTX ____" or "GeForce RTX ____". Any GTX 1060 or newer works. If you don't have one, skip to "Option B: Google Colab" below.

**Mac/Linux:** Open a terminal and type:
```
nvidia-smi
```
If you see a table with GPU info, you're good. If you see "command not found," you don't have an NVIDIA GPU. Use Google Colab.

### Step 2.2: Install Python (if you don't have it)

**Windows:** Download from https://python.org (click the yellow "Download Python 3.12.x" button). During installation, CHECK the box "Add Python to PATH."

**Mac:** Open Terminal and type:
```
brew install python@3.12
```
(If you don't have Homebrew, install it first from https://brew.sh)

**Ubuntu/Debian:**
```
sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip
```

Verify Python is installed:
```
python3 --version
```
You should see `Python 3.12.x` or similar.

### Step 2.3: Download Kronos-TH

Open a terminal (Command Prompt on Windows, Terminal on Mac/Linux) and type:

```bash
cd ~
git clone https://github.com/shiyu-coder/Kronos.git kronos_repo
# Then clone Kronos-TH (replace with the actual repo URL):
git clone https://github.com/Yutwizard/Kronos_Thai_Retail.git kronos-th
cd kronos-th
```

> **What is `~`?** It's your home directory. `cd ~` means "go to my home folder."
> **What is `git clone`?** It downloads a project from the internet to your computer.
> **What is `cd kronos-th`?** It enters the project folder so all commands run from the right place.

If `git clone` says "command not found", install git:
- Windows: https://git-scm.com/download
- Mac: `brew install git`
- Ubuntu: `sudo apt install git`

### Step 2.4: Set Up Python Environment

```bash
python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-ml.txt
pip install -e .
```

> **What are these commands doing?**
> - `python3 -m venv venv` — creates an isolated Python environment (so Kronos doesn't conflict with other programs on your computer)
> - `source venv/bin/activate` — enters that environment
> - `pip install -r requirements.txt` — installs the base libraries Kronos needs
> - `pip install -e .` — installs Kronos-TH itself

### Step 2.5: Download Stock Data

```bash
python scripts/download_data.py
```

This downloads price history for all 49 Thai stocks. Takes 2–5 minutes. You only need to run this once (the daily cron will keep it updated).

### Step 2.6: Verify Everything Works

```bash
python -c "from kth.trading.portfolio import init_portfolio; pf = init_portfolio('paper'); print('Cash:', pf['cash'], 'THB — setup OK!')"
```

You should see: `Cash: 500000.0 THB — setup OK!`

### Step 2.7: Set Up LINE Notify Alerts (Optional but Recommended)

If the daily pipeline fails, the dashboard shows stale data — you won't know until you open it. LINE Notify sends a push notification to your phone instead.

**One-time setup (2 minutes):**

1. Go to **notify.line.me/my** → scroll down → "Generate token" → name it "Kronos-TH" → Copy the token.

2. Add to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export LINE_NOTIFY_TOKEN="paste-your-token-here"
```

3. Reload your shell:

```bash
source ~/.bashrc   # or source ~/.zshrc
```

After this, if the `cron_pipeline.sh` fails (download or forecast step), you'll receive a push message: *"🚨 Kronos-TH STEP2 FAILED (forecast) on 2026-06-03. Check data/logs/cron_2026-06-03.log"*

> If you skip this step, the system still works — you just won't get alerts on cron failures.

---

## 3. Your First Run

Two dashboard options are available — choose based on your environment:

- **Flask dashboard** (this section) — local Python + GPU, run via `scripts/dashboard.py` or the one-command launcher `scripts/start_dashboard.sh`
- **Google Suite dashboard** (`docs/SETUP_GUIDE.md`) — zero-cost, browser-based, no local GPU required

Both reached feature parity on 2026-06-06 and are fully functional. Pick whichever fits your setup.

### Option A: Flask Dashboard (Local GPU)

**Easiest way — one command:**
```bash
./scripts/start_dashboard.sh
```
This single command creates the venv, installs dependencies (data + ML stack), downloads data (skips if fresh), runs the forecast pipeline, and starts the dashboard at **http://localhost:5555**. Subcommands: `stop`, `restart`, `status`, `logs`, `clean`. Run `./scripts/start_dashboard.sh help` for full usage.

**Manual way** (if you want step-by-step control):
```bash
python scripts/dashboard.py --generate
```

This will take **~12 minutes on GTX 1060** (~3 minutes on newer GPUs). You'll see progress messages like `STEP1_OK`, `STEP2_OK`, etc.

> **If you get an "out of memory" error on GTX 1060:** The default uses `n_samples=50` which requires ~8GB VRAM. On a 6GB GTX 1060, reduce to `n_samples=10` by editing `scripts/dashboard.py` line ~180 (change `n_samples=50` to `n_samples=10`). Forecast quality is slightly lower but the pipeline will run.

Then start the dashboard:
```bash
python scripts/dashboard.py --serve
```

Open your browser and go to: **http://localhost:5555**

### Option B: Google Suite Dashboard (Zero-Cost, Browser-Based)

See [`docs/SETUP_GUIDE.md`](SETUP_GUIDE.md) for complete setup. Summary:
- No local GPU required (runs on Colab's free T4)
- Browser-based, accessible from any device
- Includes Reset Capital, Signal Health Banner, Trade Log edit/delete, 60s auto-refresh
- 44-cell Colab notebook + 18-tab Google Sheets + 5-tab Apps Script web app

### Option C: Google Colab (Notebook Workflow, No Dashboard)

If you don't need a dashboard UI and just want a notebook workflow:

1. Go to https://colab.research.google.com
2. Upload `notebooks/01_data_layer.ipynb` and run it to download data
3. Upload `notebooks/05_decision_report.ipynb` for daily forecasts
4. Set `REPORT_MODE = "morning"` in Cell 0, run all cells

Colab gives you a **free T4 GPU**. Forecasts take ~3 minutes instead of 12.

> **If you're on Colab:** Follow the [Operations Manual](operations-manual.md) daily routine instead of the dashboard steps below. The decision rules are the same, but the interface is different.

### Option D: Kaggle Scheduled Pipeline (Unattended, Recommended)

If you want fully automated daily runs at $0 (no manual steps, no local machine):

1. See `docs/SETUP_GUIDE.md` — complete step-by-step from zero to dashboard
2. Covers Sheets creation, Apps Script deployment, GCP service account, Kaggle notebook, and scheduling
3. The pipeline runs each evening BKK time and updates the Google Suite dashboard automatically
4. To verify offline: `python run_pipeline.py --dry-run`

### What You Should See

After opening http://localhost:5555, you should see:

```
┌──────────────────────────────────────────────┐
│ Kronos-TH Dashboard    📋 PAPER    2026-06-02 │
├──────────────────────────────────────────────┤
│ Market: Normal  Alloc: NEUTRAL 10%  ...      │
├──────────────────────────────────────────────┤
│ Trade Ticket                                 │
│  ▼ EXIT: KBANK.BK  3,500 shares   market    │
│  ▲ BUY:  CPALL.BK    800 shares   limit     │
│  [Record Paper Trade] [➕ Add Manual Trade]  │
│  [Export for Broker]                         │
├─────────────────────┬────────────────────────┤
│ Current Positions   │ Morning Brief (Top 10) │
└─────────────────────┴────────────────────────┘
```

**If you don't see any trade signals:** This is normal. The model only produces buy/sell signals on ~30% of days. On quiet days, the dashboard says "No trade signals today" — staying in cash is a valid strategy.

---

## 4. Paper Trading Explained

**Paper trading = simulated trading with fake money.**

Think of it like a flight simulator. Before you fly a real plane, you practice in a simulator where crashing doesn't hurt anyone. Paper trading is the same for investing:

- You start with **500,000 THB** of simulated cash
- The dashboard shows you what to buy/sell each day
- You click "Record Paper Trade" to execute the trade in the simulator
- The system tracks your P&L (profit and loss) as if it were real
- You can see your win rate, Sharpe ratio, drawdown, and other metrics
- **No real money is at risk**

**Why paper trade first?**
The backtest says the strategy makes +31.44% per year, but:
- Backtests don't include your personal execution (did you follow signals or hesitate?)
- Markets change — what worked in 2022-2024 might not work in 2026
- You need to build trust in the system before risking real THB
- You need to learn the dashboard and the daily routine without pressure

**How long should you paper trade?** At least 20 trading days and at least 10 round-trip trades. The dashboard has a built-in gate that won't let you switch to live mode until you meet these minimums AND your paper results are good.

> **Note on trading days:** The Stock Exchange of Thailand is closed on weekends and Thai public holidays (Songkran, New Year, King's birthday, etc.). "20 trading days" means ~4-5 calendar weeks depending on holidays. The Phase 2 gate counts calendar days — holidays don't reset your progress.

---

## 5. Glossary — Words You Need to Know

**Read this section once.** You don't need to memorize it — come back when you see a term you don't understand.

### Forecast Terms

| Term | Plain English | Example |
|------|--------------|---------|
| **Expected Return (Exp Ret)** | How much the model thinks a stock will go up/down over 20 trading days | "+2.31%" means the model expects PTT to rise 2.31% in the next month |
| **Band Width** | How uncertain the model is. Narrow band = confident. Wide band = unsure. | 6.5% band = "pretty confident." 25% band = "guessing." |
| **Confidence Flag** | Color-coded version of band width | 🟢 ≤10% (confident), 🟡 10-30% (moderate), 🔴 >30% (unsure) |

### Trading Terms

| Term | Plain English | Example |
|------|--------------|---------|
| **Market Order** | "Buy/sell at whatever price the market gives me right now." Use for urgent exits. | You sell KBANK immediately at the current market price |
| **Limit Order** | "Buy/sell but only at this price or better." Use for non-urgent buys. | You set a limit to buy CPALL at 56.70 or cheaper |
| **Board Lot** | The minimum number of shares you can trade. For Thai stocks: 100 shares. | You can buy 100, 200, 300 shares — but not 50 or 150 |
| **Friction / Commission** | The fee your broker charges per trade. For Thai stocks: ~0.27% one-way (0.54% round-trip). The dashboard uses one-way friction per trade side. | Buying 50,000 THB of PTT costs ~135 THB in fees |
| **Net Return** | Expected return minus friction. What you actually keep. | +2.31% return − 0.54% friction = +1.77% net |

### Risk Terms

| Term | Plain English | Good | Bad |
|------|--------------|------|-----|
| **CAGR** | Compound Annual Growth Rate. "If I started with 500K and grew at this rate every year, here's what I'd have." Smooths out the bumps. | +20%+ | <0% |
| **Sharpe Ratio** | "How much return am I getting per unit of risk?" | >1.0 | <0.5 |
| **Drawdown** | "How much has my portfolio dropped from its peak?" | >−3% | <−10% (triggers stop-loss) |
| **Win Rate** | "What % of my closed trades made money?" | >50% | <40% |
| **Exposure** | "What % of my money is in stocks right now?" | 5–20% | 0% (all cash) or >30% (too concentrated) |

### System Terms

| Term | Plain English |
|------|--------------|
| **Allocation Band** | How much of your portfolio to deploy. BULL=15%, NEUTRAL=10%, BEAR=5%, EXIT=0%. Higher when the strategy is performing well. |
| **Market State** | Normal / Elevated / Turmoil. If Turmoil, stay in cash — the model doesn't understand what's happening. |
| **3-Filter Rule** | Monthly check: (1) Is net return good? (2) Is confidence 🟢 or 🟡? (3) Is position size within limits? |
| **Phase 2 Gate** | The checklist you must pass before switching from paper to real trading. |
| **FIFO** | First-In-First-Out. When you buy shares in multiple batches and sell some, the oldest shares are counted as sold first. Used to calculate win rate accurately. |
| **P50 / P50%** | The model's median prediction — "I think there's a 50% chance the price is above this and 50% chance below." |
| **HistVol** | Historical Volatility. How much a stock's price has jumped around over the past year. Higher = riskier. |
| **SET** | The Stock Exchange of Thailand. The main Thai stock market index. |
| **Zero-shot** | The model uses its pre-trained knowledge without additional fine-tuning. Backtests showed fine-tuning did NOT improve results for Thai equity, so the dashboard uses zero-shot only. |
| **Sector Guard** | A buy-list rule that limits picks to 2 per SET sector (Banking, Energy, Property, etc.). If the top 5 signals are all Banking stocks, only 2 appear in the buy list. Prevents sector concentration risk. |
| **T+2 Settlement** | Thai equity trades settle 2 business days after execution. When you sell on Monday, cash arrives Wednesday. The dashboard shows a yellow warning if you have exits and buys on the same day — buy from your existing cash, not from the sale proceeds. |
| **Grind** | A Risk Bar tile that turns red when the portfolio drops >3% over 5 consecutive days, even if the −10% circuit breaker hasn't triggered yet. Action: reduce allocation band by one step immediately. |
| **Band Coverage (Calibration)** | In the Signal Health row — what % of past actual stock prices fell within the model's P5/P95 forecast band. Should be 80–95%. Below 80% means the model is overconfident (bands too narrow). Shows "—" until 20+ forecast dates accumulate. |
| **Bootstrap p-value** | In the Signal Health row — a statistical test of whether your live paper trading edge is real or luck. p < 0.05 = confirmed edge. Shows "—" until ≥20 trading days. This is NOT the same as the backtest p-values shown in the user manual. |

---

## 6. Your First Week — Day-by-Day

> **Start any day.** The Monday–Friday labels are for illustration. Your "Day 1" is whenever you first run the dashboard — a Wednesday, a Thursday, any day the market is open.

### Monday — First Day

1. **Evening (previous day or end of day):** Click **▶ Run Pipeline** in the dashboard (~12 min). This generates tomorrow's forecast using today's close prices.
2. **Morning:** Open http://localhost:5555 — Trade Ticket is ready. Check the Risk Bar (Market State = Normal?).
3. **Look at:** The Trade Ticket. Are there any buy or exit signals? If yes — great. If no — also great. "No signals today" is normal.
4. **Click:** "Record Paper Trade" if you want to simulate the trades. Enter the actual fill price from your broker.
   - **No ticket today, or a trade not in it?** Click **"➕ Add Manual Trade"** to log any buy/sell yourself (ticker, action, shares, fill price).
5. **End of day:** Run pipeline again to update forecasts with today's close data.

### Tuesday — Getting Comfortable

1. **Morning:** Open http://localhost:5555. The dashboard should have refreshed automatically (if you kept it running).
2. **Try:** Expand the "Full Ranking" panel at the bottom. See all 49 stocks ranked by expected return. Click the search box and type a ticker name (e.g., "PTT").
3. **Notice:** Do the same stocks appear in the top 10 as yesterday? Some will, some won't. That's normal.
4. **If your paper portfolio shows a loss:** Don't panic. A +30% annual return doesn't mean +0.12% every day. There will be down days, down weeks, even down months. Look at the Win Rate, not the daily P&L.

### Wednesday — Understanding the Flags

1. **Focus on:** The color of the "Flag" column in the Morning Brief.
2. **🟢 Green:** The model is confident. If it says ↑ (up), that's a strong buy signal. If it says ↓ (down) and you hold that stock, that's a strong sell signal.
3. **🟡 Yellow:** Moderate confidence. Treat as half-strength signals. Buy half your normal amount. Sell half your position.
4. **🔴 Red:** The model is confused. Skip. Don't trade on red-flag signals.
5. **Count:** How many tickers are 🟢? If fewer than 10, the market is uncertain today. If more than 30 are 🔴, it's a high-uncertainty day — stay cash.

### Thursday — Exploring Risk

1. **Check:** The Drawdown tile in the Risk Bar. Is it green (>−3%), orange (−3% to −7%), or red (<−7%)?
2. **If red:** The system is telling you to reduce exposure. The Allocation tile might show BEAR (5%) or EXIT (0%).
3. **Understand:** The allocation band is automatic. The system looks at your paper portfolio's recent performance and adjusts how aggressive to be. You don't need to decide — just follow what it says.

### Friday — First Week Complete

1. **Review:** Click through all 5 panels. You should be comfortable navigating the dashboard.
2. **Check:** The P&L MTD tile. Is it positive or negative? A negative first week is normal — the strategy works over months, not days.
3. **Note:** Write down (in a notebook or text file):
   ```
   Week 1: June 2-6, 2026
   Trades executed: 3 (2 buys, 1 exit)
   P&L MTD: -1.2% (paper)
   Market State: Normal
   ```
   Keeping a simple journal helps you track your learning.

### Weekend — Reflect

- Did you follow the dashboard's signals or second-guess them?
- Did you hesitate on an exit signal? (Common newbie mistake: "but it might go back up!")
- Did you understand what the dashboard was telling you?

**Key mindset:** The dashboard is a tool, not a crystal ball. It gives you statistically-informed suggestions. Your job is to execute them consistently, not to outsmart them.

---

## 7. Daily Routine (After You Know the System)

Once you're comfortable (after 1–2 weeks), this is your 15-minute morning checklist:

| # | Step | Time | What to Do |
|---|------|------|------------|
| 1 | Check Risk Bar | 10 sec | Market State must be Normal. Allocation must not be EXIT. If either is bad → stop here, stay cash. |
| 2 | Review Trade Ticket | 5 min | Exits (same day, market order) then Buys (within 2 days, limit order). Check cash flow after friction. |
| 3 | Record Paper Trades | 1 min | Click "Record Paper Trade" |
| 4 | Scan Positions | 2 min | Any position down >−10%? Any position >25% of portfolio? |
| 5 | Expand Full Ranking | 1 min | How many 🟢 vs 🔴? Any surprises in top/bottom 5? |
| 6 | Log Notes | 1 min | Write down trades, market state, any concerns |

---

## 8. What Could Go Wrong? (Honest Numbers)

### How Much Can I Lose?

The system has a **−10% stop-loss**. On a 500,000 THB portfolio, the absolute maximum loss before the system forces you to stop trading is:

> **50,000 THB** (500,000 × 10%)

In the backtests (2022–2024), the worst drawdown was −17.97%. That happened once in 3 years, during a market-wide selloff. The system recovered to end the year positive.

**The worst-case realistic scenario:** You lose 50,000 THB (the stop-loss triggers), take a break for 2 weeks, and re-enter when markets stabilize. Over a full year, even with one stop-loss event, the backtest still showed +31.44%.

### What If the Model Stops Working?

Models degrade. Markets change. The dashboard watches for this:

- If your win rate drops below 40% for 2+ weeks → halve your position sizes
- If your live Sharpe ratio drops below 0.5 → reduce allocation
- If >30 out of 49 tickers show 🔴 for 3 consecutive days → 75% cash

These are automatic guardrails. You don't need to decide when the model is "broken" — the system tells you.

### What If I'm Scared?

Every new trader is scared. Here's what helps:

1. **Paper trade for at least 4 weeks.** Don't rush to real money.
2. **Start small if you go live.** The allocation bands already keep you at 5–15% deployed. That means at most 75,000 THB in stocks, with 425,000 THB safe in cash.
3. **Follow the system exactly.** The biggest source of losses in backtesting came from NOT the model being wrong, but from a human ignoring exit signals because "it might go back up."
4. **Remember:** The SET index lost −5.29% per year over 2022–2024. The strategy made +31.44%. Even if the strategy underperforms its backtest by half, you're still beating the market.

### Trading Psychology — Quick Tips

| Feeling | What It Is | What To Do |
|---------|-----------|------------|
| Boredom (no signals for days) | Normal — 70% of days have no trade signals | Stay in cash. Boredom is better than bad trades. |
| FOMO (a stock you sold keeps going up) | Fear Of Missing Out | Trust the model. It exited for a reason. There will be other opportunities. |
| Revenge trading (lost money, want it back) | Emotional reaction to loss | Close the dashboard. Come back tomorrow. Never trade angry. |
| Overconfidence (won 5 in a row) | Dangerous — leads to ignoring risk limits | Check the Allocation tile. If it says NEUTRAL, stay at 10%. Don't override it. |

---

## 9. Graduating to Real Money (Phase 2)

**Do not rush this.** The gate exists because most new traders lose money by trading too soon.

### The 6 Requirements

You need ALL of these before switching to live mode:

| # | Requirement | Why |
|---|-------------|-----|
| 1 | Paper traded ≥ 20 trading days | You need to experience both up weeks and down weeks |
| 2 | ≥ 10 round-trip trades | One lucky trade doesn't prove skill |
| 3 | Win rate ≥ 50% | You should win more trades than you lose |
| 4 | Sharpe ≥ 0.90 | Your risk-adjusted returns should be decent |
| 5 | No stop-loss trigger | You haven't had a −10% blow-up |
| 6 | ≥ 3 monthly rebalances | You've practiced the monthly routine |

### How to Check

Visit http://localhost:5555/api/phase2_gate — it shows which checks pass/fail.

### What Changes in Live Mode

1. Dashboard header turns **💰 LIVE (red)** instead of 📋 PAPER (blue)
2. Button changes from "Record Paper Trade" to **"Confirm Live Trade"**
3. You click **"Export for Broker"** → downloads a CSV file
4. You open your broker app and **manually enter** the orders from the CSV
5. You record actual fill prices for weekly reconciliation

**You need a real broker account** for Phase 2. Thai brokers: Settrade (most banks), Bualuang Securities, KTB Securities, etc. Opening an account requires: Thai ID card, bank account, ~15 minutes at a branch or via app.

**Friction costs with a real broker:** ~0.27% per side (commission + VAT + SET fee). On a 50,000 THB trade, that's ~135 THB. The system accounts for this in the net return calculation.

---

## 10. Where to Go Next

| If you want to... | Read this |
|-------------------|-----------|
| Learn the daily routine in detail | [Dashboard User Manual](dashboard-user-manual.md) |
| Understand the decision rules | [Operations Manual](operations-manual.md) |
| See the technical architecture | [Design Spec](superpowers/specs/2026-06-02-real-market-dashboard-design.md) |
| Understand how the backtest works | [User Manual & Methodology](user-manual.md) |
| Get help or report a bug | Open a GitHub issue at https://github.com/Yutwizard/Kronos_Thai_Retail/issues |

---

## Quick Start Card (Print This)

```
┌─────────────────────────────────────────────────────────────┐
│                    KRONOS-TH CHEAT SHEET                     │
├─────────────────────────────────────────────────────────────┤
│ SETUP (first time only, ~30 min) — see §2 for details       │
│   cd ~                                                      │
│   git clone https://github.com/shiyu-coder/Kronos.git kronos_repo│
│   git clone <kronos-th-repo-url> kronos-th                   │
│   cd kronos-th                                              │
│   python3 -m venv venv                                      │
│   source venv/bin/activate                                  │
│   pip install -r requirements.txt                           │
│   pip install -r requirements-ml.txt                        │
│   pip install -e .                                          │
│   python scripts/download_data.py                           │
├─────────────────────────────────────────────────────────────┤
│ EVERY MORNING (15 min)                                      │
│   cd ~/kronos-th                                            │
│   source venv/bin/activate                                  │
│   python scripts/dashboard.py --generate  (12 min, GPU)     │
│   python scripts/dashboard.py --serve                       │
│   Browser: http://localhost:5555                            │
│                                                             │
│   1. Risk Bar → Normal? Not EXIT?                           │
│   2. Trade Ticket → Exits SAME DAY. Buys within 2 days.     │
│   3. Click "Record Paper Trade"                             │
│   4. Scan Positions → any >−10% loss?                       │
│   5. Full Ranking → sanity check                            │
├─────────────────────────────────────────────────────────────┤
│ COLORS: 🟢=confident 🟡=moderate 🔴=unsure/skip             │
│ STOP TRADING: Market=Turmoil or Allocation=EXIT              │
│ REDUCE EXPOSURE: DD <−7% (orange/red)                       │
│ ALL LIQUIDATED: DD crosses −10% (stop-loss triggers)        │
└─────────────────────────────────────────────────────────────┘
```

---

*Document version: 2026-06-02. For absolute beginners. If anything is unclear, open a GitHub issue — it means the guide needs improving.*
