# Daily Paper Trading Guide — Kronos-TH (Flask Dashboard)

> **Recommended workflow: run the pipeline in the EVENING after market closes.**
> This uses today's close prices and means tomorrow morning you just open the
> dashboard and trade — no waiting 12 minutes before market opens.
> Environment: Local GTX 1060, cron NOT configured → manual run required
>
> **Using the Google Suite dashboard instead?** See [`docs/SETUP_GUIDE.md`](SETUP_GUIDE.md) for the complete zero-to-dashboard setup (Kaggle automated + Colab backup). The decision rules are identical; only the compute environment differs.

---

## Recommended Daily Routine

### Evening (after SET closes at 17:00 BKK) — ~15 min

| Time | Action | Duration |
|---|---|---|
| 17:30 | Open http://localhost:5555 | 10 sec |
| 17:30 | Click ▶ Run Pipeline | ~12 min GPU |
| 17:45 | Review positions table — updated expected returns | 3 min |
| 17:50 | Check Trade Ticket for tomorrow | 2 min |
| 17:55 | Log notes for tomorrow | 1 min |

### Morning (before SET opens at 10:00 BKK) — ~5 min

| Time | Action | Duration |
|---|---|---|
| 09:30 | Open http://localhost:5555 | 10 sec |
| 09:30 | Check Trade Ticket (already ready from last night) | 3 min |
| 09:45 | Record paper trade if executing | 1 min |
| 09:50 | SET opens at 10:00 — place orders at broker | — |

> **If you missed the evening run:** Click ▶ Run Pipeline at 06:15 AM.
> Takes ~12 min so you'll have results by 06:30, well before the 10:00 open.

---

## Why Evening Run Is Better

| Run time | Data used | Result |
|---|---|---|
| **Evening (after 17:00)** | Today's close prices | Most accurate for tomorrow |
| Morning (before 10:00) | Yesterday's close prices | Valid but uses older data |

Running in the evening means the forecast always uses the most recent prices.
The signals in the positions table will reflect what happened today.

---

## Timeline Overview (Morning-only fallback)

SET market opens 10:00 BKK. You have until 09:30 to decide — no rush.

---

## Step 1 — Open Terminal and Activate Environment

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
source venv/bin/activate
```

Verify:
```bash
python -c "import torch; print('GPU:', torch.cuda.get_device_name(0))"
# Expected: GPU: NVIDIA GeForce GTX 1060
```

---

## Step 2 — Download Latest Data (5 min)

```bash
python scripts/download_data.py
```

**What you'll see:**
```
Downloading 100 tickers (10 years each)...
[1/100] PTT.BK... OK 2431 rows 2016-06-03..2026-06-04
...
✅ All tickers passed sanity check.
```

**If a ticker shows "⚠ SANITY FAIL":** That ticker will be excluded from today's forecast. Note it and continue — the system handles this automatically.

**If download hangs at a ticker for >30 seconds:** Press Ctrl+C and re-run. yfinance occasionally hangs; the script will skip already-completed tickers.

---

## Step 3 — Generate Forecasts (~12 min on GTX 1060)

**One command (recommended):**
```bash
./scripts/start_dashboard.sh
```
This single command sets up the venv (first run only), downloads data, generates forecasts, and starts the dashboard. Subcommands: `stop`, `restart`, `status`, `logs`, `clean`.

**Or manual (step-by-step):**
```bash
python scripts/dashboard.py --generate
```

**What you'll see:**
```
[06:20:00] STEP1: download_data.py
[06:20:01] STEP1_OK
[06:20:01] STEP2: forecast generation
[06:20:05] Eligible tickers: 49 / 50
[06:20:05] Calendar: 5-day (business)
[06:20:05] STEP2: 0 tickers already forecasted today, running 49 remaining
...
[06:32:30] STEP2_OK
[06:32:31] STEP3: trade ticket generation
[06:32:35] STEP3_OK: 0 exits, X buys
[06:32:35] PIPELINE_OK
```

**If GPU OOM error:** Edit `scripts/dashboard.py` and find `n_samples=50` → change to `n_samples=20` temporarily. This reduces forecast quality but fits 6GB VRAM.

**If "No forecast cache" error:** The `--generate` step downloads data too. Skip Step 2 and let `--generate` handle it:
```bash
python scripts/dashboard.py --generate
```

---

## Step 4 — Start the Dashboard

```bash
python scripts/dashboard.py --serve
```

**Expected output:**
```
 * Running on http://127.0.0.1:5555
```

Open your browser: **http://localhost:5555**

---

## Step 5 — Read the Risk Bar (60 seconds)

The Risk Bar is the top row of tiles. Check each in order:

| Tile | What to check | Action if bad |
|---|---|---|
| **Market State** | Should say "Normal" | If "Turmoil" → **STOP. Do not trade today.** Close dashboard and wait. |
| **Allocation** | Will say "NEUTRAL" (bootstrap: <20 trades) | This is correct for Day 1 — ignore for now |
| **Trailing Sharpe** | Will show 0 (no history yet) | Normal for Day 1 |
| **Drawdown** | Should be 0% | Normal |
| **Grind** | Should show 0% velocity | Normal |
| **P&L MTD** | 0 THB | Normal |
| **Win Rate** | 0% (no trades yet) | Normal |
| **Exposure** | 0% | Normal — you're in cash |

> **Day 1 special case:** Most Risk Bar metrics show 0 because there's no trading history. The only tile that matters today is **Market State**.

---

## Step 6 — Read the Trade Ticket (3 min)

The Trade Ticket is the hero panel. On Day 1 there are no exits (nothing held).

**Focus on the BUY list.** For each buy candidate:

| Column | What it means | Day 1 threshold |
|---|---|---|
| **Flag** | 🟢 = confident, 🟡 = moderate, 🔴 = uncertain | Only consider 🟢 |
| **Direction** | ↑ = bullish, ↓ = bearish | Only buy ↑ |
| **Exp Ret** | Model's expected 20-day return | Must be > 0% |
| **Net Ret** | After friction (0.536% round-trip) | Must be > 1.0% (2× friction) |
| **Band** | Uncertainty range | Narrow band = more confident |

**Today's decision rule (BEAR allocation — SET bull market):**

> ⚠️ We are in a SET bull market (EW returns strongly positive in 2026).  
> The strategy underperforms in broad bull markets due to cash drag.  
> **Use BEAR allocation: maximum 1 position, 5% of capital = 25,000 THB.**

| Signal condition | Action |
|---|---|
| ≥1 ticker with 🟢↑ AND net_ret > 1.0% | Buy 1 position only (25,000 THB) |
| All tickers 🔴 or ↓ | Stay cash today. Log reason. |
| Market State = Turmoil | Do NOT trade. Go to cash. |
| High uncertainty day (>30 tickers 🔴) | Stay cash. Dashboard shows banner. |

**Position size calculation for BEAR allocation:**
```
Capital:     500,000 THB
BEAR band:   5% = 25,000 THB per position
Max positions: 1 (BEAR = conservative)
Board lot:   100 shares

Shares = floor(25,000 / close_price / 100) × 100

Example: CPALL.BK close = 55.00 THB
  Shares = floor(25,000 / 55 / 100) × 100 = floor(4.54) × 100 = 400 shares
  Cost = 400 × 55.00 = 22,000 THB ✓
```

---

## Step 7 — Make the Trade Decision (2 min)

**Decision flowchart:**

```
Is Market State = Turmoil?
├── YES → Stay cash. Log "TURMOIL - no trade". Done.
└── NO ↓

Are there any 🟢↑ tickers with net_ret > 1.0%?
├── NO → Stay cash. Log "No qualifying signals". Done.
└── YES ↓

What is the top-ranked qualifying ticker?
→ Note: ticker, close, exp_ret, net_ret, band_width

Is this ticker in a sector with 0 existing positions?
(Day 1: always yes — portfolio is empty)
└── YES ↓

Calculate shares (BEAR = 25,000 THB / close, round to 100)
Set limit order at: close × (1 + exp_ret / 2)

→ Go to Step 8
```

---

## Step 8 — Record the Paper Trade (1 min)

**Option A — Dashboard button (recommended):**
1. In the Trade Ticket, click **"Record Paper Trade"**
2. Confirm the modal showing: ticker, shares, estimated THB, friction cost
3. Click **"Confirm"**

**Option B — Manual POST (if button doesn't work):**
```bash
curl -X POST http://localhost:5555/api/trades \
  -H "Content-Type: application/json" \
  -d '{
    "trades": [{
      "ticker": "CPALL.BK",
      "action": "buy",
      "shares": 400,
      "fill_price": 55.00,
      "order_type": "limit"
    }],
    "date": "2026-06-04",
    "mode": "paper"
  }'
```

**Expected response:**
```json
{"recorded": 1, "portfolio_value": 499865, "cash": 477865, "new_positions": [...]}
```

> **Note:** Paper trades are at the LIMIT price, not market price. Record the price now (pre-market). When SET opens at 10:00, check if the stock fills below your limit. If not filled by 14:30 (SET close), cancel and record "unfilled".

---

## Step 9 — Log the Session (2 min)

Open (or create) `data/positions/morning_log.md` and add:

```markdown
## 2026-06-04 — Session 1 (First Paper Trade)

**Market State:** [Normal / Elevated / Turmoil]
**Allocation:** BEAR (5%) — SET bull regime, conservative deployment
**Signals:** [How many 🟢↑ above threshold?]

**Decision:** [Traded / Stayed cash]

If traded:
- Ticker: ___
- Shares: ___ × ___ THB = ___ THB
- Expected return: ___% net
- Limit price: ___
- Rationale: ___

If stayed cash:
- Reason: [No signals / Turmoil / All red / Manual override]

**Notes:** [Anything unusual about the forecast? SET market news?]
```

---

## What to Expect — Day 1 Outcomes

| Outcome | Probability | What it means |
|---|---|---|
| No qualifying signals | ~40% | Normal. The model is selective. Stay in cash. |
| 1–3 green signals, buy 1 | ~50% | Standard day. Execute 1 position at 25K THB. |
| High uncertainty (all 🔴) | ~10% | Dashboard shows banner. Stay in cash. |
| Turmoil | Rare | Stop-loss regime. Do NOT trade. |

> **First week expectation:** Most days you may see 0–1 signals that clear the threshold. The strategy holds 50% cash by design — this is intentional, not broken. Do not force trades.

---

## Troubleshooting Quick Reference

| Problem | Fix |
|---|---|
| Dashboard shows "Forecasts stale" | Re-run `python scripts/dashboard.py --generate` |
| GPU OOM during generate | Reduce `n_samples=50` → `20` in dashboard.py line ~186 |
| Port 5555 already in use | `kill $(lsof -t -i:5555)` then re-run `--serve` |
| Trade button gives 400 error | Check shares multiple of 100, fill_price within ±20% of close |
| No tickers in trade ticket | Check forecast cache: `ls data/forecast_cache/NeoQuasar_Kronos-small/2026-06-04/` |
| Download hangs | `Ctrl+C` and re-run — already-cached tickers are skipped |

---

## Setting Up Cron (Optional — Do This Once)

To automate the pipeline every weekday at 06:30 BKK:

```bash
crontab -e
```

Add:
```cron
30 6 * * 1-5 cd /home/yut/VSCode/Kronos_Thai_Retail && bash scripts/cron_pipeline.sh
```

Also set your LINE Notify token so you get push alerts on failure:
```bash
echo 'export LINE_NOTIFY_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc
```

Get your token at: **notify.line.me/my** → Generate token → name "Kronos-TH"

---

## Phase 2 Gate — Track Progress

After each session, mentally tick off the Phase 2 gate:

| Criterion | Required | Today |
|---|---|---|
| Paper trading days | ≥ 20 days | 1st day |
| Round-trip trades | ≥ 10 | 0 |
| Win rate | ≥ 50% | N/A |
| Live Sharpe | ≥ 0.90 | N/A |
| No stop-loss trigger | ✅ | ✅ |
| Monthly rebalances | ≥ 3 | 0 |

The Phase 2 gate is checked automatically in the dashboard after 20 trading days.

---

## Key Numbers to Remember

| Parameter | Value | Why |
|---|---|---|
| Capital | 500,000 THB | Fixed starting capital |
| BEAR allocation | 5% = **25,000 THB** | SET bull market — conservative |
| NEUTRAL allocation | 10% = **50,000 THB** | Use when Sharpe > 0.5 (20+ trades) |
| BULL allocation | 15% = **75,000 THB** | Use when Sharpe > 1.0 (20+ trades) |
| Board lot | 100 shares minimum | SET rule — always round to 100 |
| Net return threshold | > 1.0% | Must clear 2× friction (0.536% round-trip) |
| Circuit breaker | −10% drawdown | Auto-freezes all positions |
| SET hours | 10:00–12:30, 14:30–17:00 BKK | Morning session + afternoon session |

---

*Created: 2026-06-03. For first paper trading session 2026-06-04.*
*Cron not configured — run Steps 2–4 manually each morning until cron is set up.*
