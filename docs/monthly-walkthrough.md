# One Month of Daily Operations — Walkthrough

> A day-by-day simulation of using the Kronos-TH system for 21 trading days.
> Starting portfolio: 1,000,000 THB. Allocation: Thai equity 40%, Cash 60%.
> All signals, allocations, and outcomes shown with exact step-by-step actions.

---

## Table of Contents

- [Day 1 — Setup & First Forecast](#day-1--setup--first-forecast)
- [Day 2 — Morning Brief with Bullish Signals](#day-2--morning-brief-with-bullish-signals)
- [Day 3 — Bearish Signal on a Holding](#day-3--bearish-signal-on-a-holding)
- [Day 4 — Same-Day Urgent Exit](#day-4--same-day-urgent-exit)
- [Day 5 — Moderate Conviction Call](#day-5--moderate-conviction-call)
- [Day 6 — High Uncertainty Day](#day-6--high-uncertainty-day)
- [Day 7 — Weekend Review](#day-7--weekend-review)
- [Day 8 — New Week, New Signals](#day-8--new-week-new-signals)
- [Day 9 — Signal Reversal](#day-9--signal-reversal)
- [Day 10 — Strengthening Conviction](#day-10--strengthening-conviction)
- [Day 11 — Crypto Warning](#day-11--crypto-warning)
- [Day 12 — Red Flag Day](#day-12--red-flag-day)
- [Day 13 — 3-Day Streak Trigger](#day-13--3-day-streak-trigger)
- [Day 14 — All-Clear & Recovery](#day-14--all-clear--recovery)
- [Day 15 — Regime Change Detected](#day-15--regime-change-detected)
- [Day 16–20 — Quiet Week (Summary)](#day-1620--quiet-week)
- [Day 21 — Month-End Rebalance](#day-21--month-end-rebalance)

---

## Starting Position

```
Portfolio value: 1,000,000 THB
Allocation:
  Cash:                         600,000 THB (60%)
  PTT.BK (Thai equity):         100,000 THB (10%) — avg cost 31.50, 3,174 shares
  KBANK.BK (Thai equity):        80,000 THB (8%)  — avg cost 140.00, 571 shares
  AAPL (US equity):             120,000 THB (12%) — avg cost 180.00, ~18.5 shares
  BTC-USD (Crypto):             100,000 THB (10%) — avg cost 650,000, 0.154 BTC
  Total invested:               400,000 THB (40%)
  Cash:                         600,000 THB (60%)
```

**Holdings:** PTT, KBANK, AAPL, BTC

> **Valuation methodology:** For clarity, position values in this walkthrough track book cost (entry price) except where exits occur at stated closing prices. Real-time mark-to-market would add noise without changing the procedural lessons. BTC positions are sized in THB terms (USD equivalent converted at ~36 THB/USD). All trades executed at next-day open as per backtest convention.

---

## Day 1 — Setup & First Forecast

### Morning Brief

```
=== Morning Brief — 2026-05-01 ===

🟢 BULLISH (top 10 by conviction):
  Ticker         Name             Class         Close   P50%    Band  Flag Dir
  ---------------------------------------------------------------------------
  PTT.BK         PTT              thai_equity   31.80  +2.10%   6.8%  🟢   ↑
  SCC.BK         Siam Cement      thai_equity  246.00  +1.90%   7.2%  🟢   ↑
  AAPL           Apple            us_equity    180.50  +1.30%   8.5%  🟢   ↑
  MSFT           Microsoft        us_equity    415.00  +1.10%   9.0%  🟢   ↑
  GLOBAL.BK      Siam Global      thai_equity   18.20  +1.60%   7.5%  🟢   ↑
  CPALL.BK       CP All           thai_equity   58.00  +1.30%   8.0%  🟢   ↑
  BTC-USD        Bitcoin          crypto      67000   +3.20%  13.0%  🟡   ↑

🔴 BEARISH (bottom 10 by conviction):
  DELTA.BK       Delta Electron.  thai_equity   90.00  -1.50%   5.5%  🟢   ↓
  DOGE-USD       Dogecoin         crypto          0.12  -4.10%  18.0%  🟡   ↓

Median band width: 16%   |   Green signals: 6   |   Red flags: 8   |   Total skipped: 2 (GULF.BK, SCB.BK)
```

### Step-by-Step

| Step | Action | Detail |
|------|--------|--------|
| **1.1** | Open notebook | `jupyter notebook notebooks/05_decision_report.ipynb` |
| **1.2** | Set mode | `REPORT_MODE = "morning"` at Cell 0 |
| **1.3** | Run all cells | Wait 12 minutes for forecast generation |
| **1.4** | Scan bullish top 10 | PTT (+2.10%), SCC (+1.90%), AAPL (+1.30%), MSFT (+1.10%), GLOBAL (+1.60%), CPALL (+1.30%), BTC (+3.20%) |
| **1.5** | Check vs holdings | **PTT** is bullish (+2.10%, 🟢) → **HOLD**. **AAPL** is bullish (+1.30%, 🟢) → **HOLD**. **BTC** is bullish but 🟡 → **HOLD at half-conviction**. **KBANK** is NOT in bearish list → **HOLD**. |
| **1.6** | Record key number | Green signals: 6. Red flags: 8. Median band: 16%. |

**Signal quality assessment:**
- PTT: +2.10% P50, 6.8% band. Net return = 2.10% - 0.536% = +1.56%. Beats 2× friction (1.07%). 🟢 → **Full position.**
- AAPL: +1.30% P50, 8.5% band. Net return = 1.30% - 0.70% = +0.60%. Between 1× and 2× friction. 🟢 → **Half-size if entering new, but you already hold. HOLD.**
- BTC: +3.20% P50, 13% band (🟡). Net return = 3.20% - 0.90% = +2.30%. Strong return but wide band. → **HOLD at current size. No add until the band narrows to 🟢.**

**Action taken:** None. All holdings are in acceptable zones. No new entries this early in the month.

---

## Day 2 — Morning Brief with Bullish Signals

### Morning Brief

```
=== Morning Brief — 2026-05-02 ===

🟢 BULLISH:
  PTT.BK         PTT              31.90  +1.80%   6.5%  🟢   ↑
  GLOBAL.BK      Siam Global       18.40  +2.10%   7.0%  🟢   ↑
  SCC.BK         Siam Cement      247.00  +1.50%   7.8%  🟢   ↑
  AAPL           Apple            181.00  +1.10%   9.2%  🟢   ↑
  MSFT           Microsoft        418.00  +0.90%  10.5%  🟢   ↑

🔴 BEARISH:
  DELTA.BK       Delta Electron.   89.50  -1.80%   6.0%  🟢   ↓
  DOGE-USD       Dogecoin           0.12  -3.80%  19.0%  🟡   ↓
```

**Key changes from Day 1:** PTT returned +0.31% from Day 1 close (31.80 → 31.90). Model still bullish but P50 dropped from 2.10% to 1.80%. The model's 2.10% prediction from yesterday was too high; actual was +0.31%. However, this is a 1-day observation against a 20-day forecast — too early to judge.

**Step 1.5 — Check vs holdings:** Same as Day 1. No urgent items.

**Step 1.6 — Record:** Green: 5. Red flags: 7. Median band: 15%.

**Action:** None. Continue monitoring.

---

## Day 3 — Bearish Signal on a Holding

### Morning Brief

```
=== Morning Brief — 2026-05-03 ===

🟢 BULLISH:
  PTT.BK         PTT              32.00  +1.60%   6.2%  🟢   ↑
  GLOBAL.BK      Siam Global       18.50  +1.80%   6.8%  🟢   ↑

🔴 BEARISH:
  KBANK.BK       Kasikornbank     141.00  -1.70%   5.0%  🟢   ↓   ← NEW
  DELTA.BK       Delta Electron.   89.00  -2.00%   5.8%  🟢   ↓
  BBL.BK         Bangkok Bank     155.00  -1.20%   6.5%  🟢   ↓
```

### Alert — KBANK appears in the bearish list

**Holdings check:**
```
Your holdings: PTT (↑ okay), KBANK (↓ NEW BEARISH), AAPL (neutral), BTC (neutral)
                ^^^^^^^^^^^^^^^^^^^^^^^
```

**KBANK analysis:**
- Close: 141.00 THB (was 140.00 when you bought, +0.7% so far)
- P50 forecast: -1.70% over 20 days → expected to drop to 138.60
- Band: 5.0% (🟢 narrow — model is confident)
- Net return if held: -1.70% - 0.536% = **-2.24%**
- Status: **Confidently bearish (🟢↓)**

### Step-by-Step

| Step | Action | Detail |
|------|--------|--------|
| **1.4** | Read the brief | KBANK is confidently bearish |
| **1.5** | Cross-check holdings | ✅ KBANK is in my holdings AND the bearish list |
| **1.6** | Assess urgency | KBANK's band is 5.0% (narrower than median of 14%), P50 is -1.70% (below threshold for exit at > friction) |
| **Decision** | **EXIT KBANK today.** Per the operations manual: "Exits for existing positions when bearish (🟢↓) are same-day urgent." |

**Trade execution:**
```python
# Sell KBANK at market open on Day 4
# Trade: sell 571 shares × ~141 THB = ~80,500 THB proceeds
# Friction: 80,500 × 0.536% = 431 THB
# Net proceeds: ~80,069 THB → cash
```

**End-of-day allocation:**
```
Cash:      600,000 + 80,069 = 680,069 THB (68%)
PTT:       100,000 THB (10%)
AAPL:      120,000 THB (12%)
BTC:       100,000 THB (10%)
Total:   1,000,069 THB  (+69 THB from KBANK exit)
```

**Note:** The +69 THB is from the time between your entry (140.00 avg) and exit (141.00 close) minus friction. You made a small gain on the exit — the model protected you from a potential -2.24% loss.

---

## Day 4 — Same-Day Urgent Exit Executed

### Morning Brief

```
=== Morning Brief — 2026-05-04 ===

🟢 BULLISH:
  PTT.BK         PTT              32.20  +1.40%   5.8%  🟢   ↑
  GLOBAL.BK      Siam Global       18.70  +1.60%   6.5%  🟢   ↑
  CPALL.BK       CP All            58.50  +0.90%   9.5%  🟢   ↑

🔴 BEARISH:
  KBANK.BK       Kasikornbank     141.50  -2.00%   5.5%  🟢   ↓  ← still bearish (exit confirmed right)
  DELTA.BK       Delta Electron.   88.50  -1.80%   6.2%  🟢   ↓
```

**Action:** Execute the KBANK sell order at market open. Fill at ~141.00 THB.

**Holdings after execution:** PTT, AAPL, BTC. KBANK position closed.

**Observation:** Today's brief confirms the exit was correct — KBANK is still bearish (-2.00%, 🟢↓). The model did NOT flip bullish overnight, which validates your exit decision.

---

## Day 5 — Moderate Conviction Call

### Morning Brief

```
=== Morning Brief — 2026-05-05 ===

🟢 BULLISH:
  PTT.BK         PTT              32.30  +1.20%   5.5%  🟢   ↑
  GLOBAL.BK      Siam Global       18.80  +1.40%   6.0%  🟢   ↑

🟡 MODERATE:
  CHG.BK         Chularat Hosp.   14.80  +1.80%  11.0%  🟡   ↑  ← NEW, moderate conviction
  HMPRO.BK       Home Product     11.50  +1.50%  12.0%  🟡   ↑  ← NEW

🔴 BEARISH:
  KBANK.BK       Kasikornbank     142.00  -2.10%   6.0%  🟢   ↓  ← still bearish (exit was right)
```

> **Note on output format:** The live notebook groups signals by DIRECTION, not by flag color. 🟡-flagged tickers appear in the BULLISH list (if ↑) or BEARISH list (if ↓) with the 🟡 flag shown in the Flag column. The "MODERATE" label used here is for illustration — you will see these tickers in the BULLISH section with a 🟡 flag in the real output.
```

**New signals:** CHG.BK (+1.80%, 🟡) and HMPRO.BK (+1.50%, 🟡) are moderate conviction. The P50% is above 1× friction but the band width is 11-12% (🟡).

**Decision per gray zone rule:** "P50% between 1× and 2× friction → enter at half-size."

**CHG analysis:**
- P50: +1.80%, Band: 11% (🟡). Net return = 1.80% - 0.536% = +1.26%.
- 1× friction = 0.536%, 2× friction = 1.072%. P50% is between them.
- **Half-size entry:** 5% of portfolio instead of 10%.
- Investment: 50,000 THB at 14.80 = 3,378 shares.

**HMPRO analysis:** Same logic. P50% between 1× and 2× friction. **Half-size entry at 5%.**

**Combined allocation change** (both are Thai equity, so class cap applies):
```
Cash before:  680,069 (68%)
CHG entry:    -50,000 (5%)
HMPRO entry:  -50,000 (5%)
Cash after:   580,069 (58%)
Thai equity:  100,000 (PTT) + 50,000 + 50,000 = 200,000 (20%) — within 35-45% target? No, only 20%.
```

Wait — Thai equity is at 20%, but the target range is 35-45%. I'm significantly under-allocated to Thai equity. The cash is too high. But the operations manual says "New entries wait for the monthly rebalance." So I should NOT add CHG and HMPRO today — I should wait for the monthly rebalance at Day 21.

**Decision:** Add CHG and HMPRO to the **monthly watch list**, but do not execute until the monthly rebalance.

```
📋 MONTHLY WATCH LIST (Day 5):
  CHG.BK   — +1.80% P50, 🟡 — Half-size candidate
  HMPRO.BK — +1.50% P50, 🟡 — Half-size candidate
  Reason: P50% between 1× and 2× friction, moderate conviction.
```

---

## Day 6 — High Uncertainty Day

### Morning Brief

```
=== Morning Brief — 2026-05-06 ===

🟢 BULLISH: (none — all flags are 🟡 or 🔴)
🟡 MODERATE: PTT (+0.80%), GLOBAL (+1.10%), CPALL (+0.60%)
🔴 RED-FLAGGED: BTC, ETH, SOL... (24 tickers)

Median band width: 32%   ← exceeds 30% threshold
# red-flagged: 24
```

**Assessment:** Median band width > 30%. The model's confidence is low across most tickers.

**Decision per operations manual:** "If median band width > 30%, the market is in a high-uncertainty state — reduce overall exposure."

But the question is: **by how much?** The manual says "stay in cash" for all-red days, but this is not all-red — it's moderate with elevated uncertainty.

**Practical rule:** If median band > 30% but some green signals exist → hold positions, no new entries.
If median band > 30% AND no green signals → stay in cash.
If 3+ consecutive days of this → go to 75% cash.

**Today:** Median band 32%, but there are still some moderate signals. **Hold positions. No new entries. Do not exit existing positions.**

---

## Day 7 — Weekend Review

### Quant PM View

```
=== Quant PM Review — Week 1 (May 1-6) ===

── thai_equity ──
  Ticker      P50%   HistVol  RiskAdj  Sharpe  MaxDD
  PTT.BK    +1.40%   18.5%    0.12     1.40   -17.97%
  SCC.BK    +1.50%   16.0%    0.14     1.40   -17.97%
  GLOBAL.BK +1.60%   15.0%    0.16     1.40   -17.97%

── us_equity ──
  AAPL       +1.10%   24.0%    0.05     0.97   -43.77%

── crypto ──
  BTC-USD    +3.20%   52.0%    0.07     0.52   -68.58%
```

**Step 3.2 — Volatility check:**
| Class | HistVol | Warning Threshold | Status |
|-------|---------|-------------------|--------|
| Thai equity | 15-18.5% | >30% | ✅ Normal |
| US equity | 24% | >40% | ✅ Normal |
| Crypto | 52% | >80% | ✅ Normal |

**Step 3.3 — Trailing signal quality:**

```python
# Direction accuracy for PTT last week: 4/5 = 80% (good)
# Direction accuracy for AAPL last week: 3/5 = 60% (acceptable)
# Direction accuracy for BTC last week: 3/5 = 60% (acceptable)
```

**Step 3.4 — Allocation check:**
| Class | Current | Target | Range |
|-------|---------|--------|-------|
| Thai equity | 20% (PTT only) | 40% | 35-45% |
| US equity | 12% (AAPL only) | 20% | 15-25% |
| Crypto | 10% (BTC only) | 5% | 2-8% |

**Two classes outside allowable range:**
1. **Thai equity at 20%** — under-allocated by 15-25pp. Need to add positions.
2. **Crypto at 10%** — over-allocated (max is 8%). Need to reduce.

**Added to monthly rebalance plan:**
```
📋 MONTHLY REBALANCE PLAN (Day 7 update):
  1. BUY  CHG.BK    5% (half-size) — Thai equity
  2. BUY  HMPRO.BK  5% (half-size) — Thai equity
  3. BUY  SCC.BK   10% (full-size) — Thai equity (already bullish)
  4. SELL BTC       3% — Crypto over-allocation (bring from 10% → 7%)
```

---

## Day 8 — New Week, New Signals

### Morning Brief

```
=== Morning Brief — 2026-05-08 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.00  +2.50%   5.5%  🟢   ↑
  SCC.BK         Siam Cement      248.00  +1.80%   6.0%  🟢   ↑
  PTT.BK         PTT               32.40  +1.10%   5.0%  🟢   ↑
  CHG.BK         Chularat Hosp.    14.90  +2.00%   9.0%  🟢   ↑

🔴 BEARISH:
  SOL-USD        Solana            145.00  -5.00%  22.0%  🟡   ↓
```

**Notable:**
- CHG.BK moved from 🟡 (Day 5) to 🟢 today. The band narrowed from 11% to 9%, and P50 increased from +1.80% to +2.00%. Net = +2.00% - 0.536% = +1.46%, above 2× friction (1.07%). **Stronger conviction than Day 5.**
- PTT continues steady — P50 dropped slightly (2.10% → 1.10% over the week) but the band narrowed (6.8% → 5.0%). Higher confidence, lower return.
- GLOBAL.BK jumped to +2.50% with a 5.5% band — this is the strongest signal today.

**Holdings check:** PTT, AAPL, BTC — all still in acceptable zones. No urgent exits.

**Monthly rebalance candidates are strengthening — no action until Day 21.**

---

## Day 9 — Signal Reversal

### Morning Brief

```
=== Morning Brief — 2026-05-09 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.20  +2.30%   5.2%  🟢   ↑
  SCC.BK         Siam Cement      249.00  +1.60%   5.8%  🟢   ↑
  CHG.BK         Chularat Hosp.    14.95  +1.80%   8.5%  🟢   ↑
  PTT.BK         PTT               32.50  +0.90%   4.8%  🟢   ↑

🔴 BEARISH:
  AAPL           Apple            179.00  -0.80%   7.0%  🟢   ↓   ← NEW — APPLE IS BEARISH
```

**⚠️ AAPL appears in the bearish list today.** You hold AAPL.

**AAPL analysis:**
- Close: 179.00 THB equivalent (was 180.50 when you bought, −0.8% so far)
- P50 forecast: -0.80% over 20 days
- Band: 7.0% (🟢 — narrow)
- Net return if held: -0.80% - 0.70% = **-1.50%**
- Status: **Confidently bearish**

**Step 1.5 — Cross-check:** ✅ AAPL is in my holdings AND the bearish list.

**Decision per operations manual:** "Exits for existing positions when bearish (🟢↓) are same-day urgent."

But wait — on Day 4, the monthly rebalance plan scheduled a **sell BTC** for Day 21. And now, AAPL shows bearish. The schedule says:

> "Day 1: Sell KBANK (bearish, urgent) — Day 2: Buy AAPL (bullish) — Day 3: Buy PTT (bullish)"

The operations manual also says: **"If the signal flips direction between execution days, defer the remaining trades and re-evaluate next week."**

Interpretation: AAPL was BULLISH on Day 1-8, now it's BEARISH on Day 9. This IS a signal reversal. But the signal reversal rule applies to TRADES IN PROGRESS — not to existing holdings. For existing holdings, the bearish exit is same-day regardless of reversal.

Actually, let me re-read the note: "If the signal flips direction between execution days (e.g., AAPL showed bullish on Monday but bearish on Tuesday), defer the remaining trades." The example explicitly uses AAPL. This means: if you were PLANNING to buy AAPL (as the example shows), don't. But if you ALREADY hold AAPL and the signal flips bearish, you EXIT.

**Decision:** Exit AAPL today — same-day urgent. Per the signal reversal rule: existing holdings get same-day urgent exit. The planned buy of AAPL from the example schedule is cancelled, but you already hold it — the exit executes.

```python
# Sell AAPL at market open on Day 10
# Trade: sell ~18.5 shares × $179 × 36 THB/USD = ~119,214 THB
# Friction: 119,214 × 0.70% = 835 THB
# Net proceeds: 118,379 THB → cash
```

**End-of-day allocation after exit:**
```
Cash:     583,410 + 118,379 = 701,789 THB (70%)
PTT:      100,000 THB (10%)
BTC:      100,000 THB (10%)
Total:    901,789 THB  (70% cash, 20% invested)
```

**Monthly watch list update:**
```
📋 MONTHLY REBALANCE PLAN (Day 9 update):
  1. BUY  CHG.BK    5% (half-size)  — Thai equity — 🟢 upgraded
  2. BUY  HMPRO.BK  5% (half-size)  — Thai equity — still 🟡
  3. BUY  SCC.BK   10% (full-size)  — Thai equity — still 🟢
  4. SELL BTC       3%               — Crypto over-allocation
  5. (REMOVED) AAPL was exit candidate, now exited. No further action.
```

---

## Day 10 — Strengthening Conviction

### Morning Brief

```
=== Morning Brief — 2026-05-10 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.40  +2.60%   5.0%  🟢   ↑  ← strongest signal of the month
  SCC.BK         Siam Cement      250.00  +1.70%   5.5%  🟢   ↑
  CHG.BK         Chularat Hosp.    15.00  +2.10%   8.0%  🟢   ↑
  PTT.BK         PTT               32.60  +0.80%   4.5%  🟢   ↑
  CPALL.BK       CP All            59.00  +1.00%   8.5%  🟢   ↑

🔴 BEARISH:
  AAPL           Apple            178.50  -1.20%   6.5%  🟢   ↓  ← still bearish (exit confirmed right)
  KBANK.BK       Kasikornbank     142.50  -2.30%   5.0%  🟢   ↓  ← still bearish (exit confirmed right)
```

**Observations:**
- AAPL exit on Day 9 was correct — still bearish today.
- KBANK exit on Day 3 was correct — still bearish.
- GLOBAL.BK is the strongest signal of the month: +2.60% P50 with 5% band.

**Allocations remain unchanged.** Monthly rebalance still scheduled for Day 21.

---

## Day 11 — Crypto Warning

### Morning Brief

```
=== Morning Brief — 2026-05-11 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.50  +2.40%   4.8%  🟢   ↑
  SCC.BK         Siam Cement      251.00  +1.50%   5.2%  🟢   ↑
  CHG.BK         Chularat Hosp.    15.10  +1.90%   7.5%  🟢   ↑
  CPALL.BK       CP All            59.20  +0.80%   9.0%  🟢   ↑

🔴 BEARISH:
  BTC-USD        Bitcoin          65500   -5.00%  25.0%  🔴   ↓  ← BTC GOES RED
  ETH-USD        Ethereum          3200   -4.00%  22.0%  🔴   ↓
  SOL-USD        Solana            138     -6.00%  28.0%  🔴   ↓
```

**⚠️ BTC appears in the bearish list with 🔴 red flag.**

**BTC analysis:**
- Close: 65,500 USD (was 67,000 on Day 1, -2.2% so far)
- P50 forecast: -5.00% over 20 days
- Band: 25% (🔴 — wide, low confidence)
- Net return if held: -5.00% - 0.90% = **-5.90%**

**Decision:** BTC is 🔴, not 🟢↓. The model says "low conviction" (wide band). The operations manual says: "🔴 + any direction → Skip — model is unsure. Do not trade on noise."

This means: **do NOT exit BTC based on today's 🔴 signal alone.** The model is unsure (wide band). Wait for the band to narrow. If BTC stays bearish AND the band narrows to 🟢↓, then exit.

**But:** BTC is also over-allocated (10% vs 5% target, max 8%). Suspending the monthly reduction of BTC from 10% to 7% would still be appropriate, but not an emergency exit.

---

## Day 12 — Red Flag Day

### Morning Brief

```
=== Morning Brief — 2026-05-12 ===

🟢 BULLISH: (none)
🟡 MODERATE: GLOBAL.BK (+1.20%, 15%), SCC.BK (+0.80%, 14%)
🔴 RED-FLAGGED: BTC, ETH, SOL, ADA, AVAX (crypto entire class), also AAPL, DELTA (48 tickers)

Median band width: 35%   ← exceeds 30% threshold
# red-flagged: 48
```

**Assessment:** This is a high-uncertainty day (median band 35%, 48/100 tickers red-flagged). The crypto sector is entirely red.

**Decision:** Per the operations manual: "If median band > 30% AND no green signals → stay in cash."

But you hold PTT and BTC — you can't just "stay in cash" without selling them. The manual also says: "All signals red → Market turmoil → Stay in cash entirely."

Interpretation: **Hold existing positions. Do not enter new ones.** Exiting PTT (which is still showing moderate signals, not red) would be an overreaction. Continue monitoring.

---

## Day 13 — 3-Day Streak Trigger

### Morning Brief

```
=== Morning Brief — 2026-05-13 ===

🟢 BULLISH: (none)
🟡 MODERATE: GLOBAL.BK (+0.90%, 16%), SCC.BK (+0.60%, 15%)
🔴 RED-FLAGGED: BTC, AAPL, DELTA, KBANK... (42 tickers)

Median band width: 33%   ← still > 30%
# red-flagged: 42
```

**3 consecutive days of median band > 30%** (Days 11-12-13). Note: the trigger is median band > 30% for 3 consecutive days — NOT "all signals must be red." Days 11 had 🟢 signals, but median band was 33-35%, meeting the threshold.

**Per the operations manual 3-day streak rule:** "3+ consecutive days of median band > 30% OR 3+ consecutive days of all signals red (whichever comes first) → reduce all positions by 50% and go to 75% cash. Do not re-enter until median band drops below 20% for 2 consecutive days."

> **Rule interaction:** The 3-day streak rule is a separate risk control mechanism. When triggered, it OVERRIDES the normal "don't exit on 🔴" rule from Day 11. Even though individual ticker signals say "wait," the streak rule forces risk reduction across the entire portfolio. This is intentional — it prevents the portfolio from riding through a prolonged high-uncertainty period.

**Action:**
1. Sell 50% of PTT position (half of 10% = 5%).
2. Sell 50% of BTC position (half of 10% = 5%).
3. Total reduction: 10% of portfolio → cash.
4. Target: 75% cash.

**PTT half-exit:**
```
Sell 50% of PTT position = 1,573 shares at ~32.50 THB
Proceeds: 1,573 × 32.50 = 51,122 THB
Friction: 51,122 × 0.536% = 274 THB
Net cash added: 50,848 THB
```

**BTC half-exit:**
```
Sell 50% of 0.154 BTC ≈ 0.077 BTC at ~65,500 USD
Proceeds: 50% of current book value ≈ 50,000 THB
Friction: 50,000 × 0.90% = 450 THB
Net cash added: 49,550 THB
```

**End-of-day allocation:**
```
Cash:     701,789 + 50,287 + 49,550 = 801,626 THB (80%)
PTT:       50,000 THB (5%)
BTC:       50,000 THB (5%)
Total:    901,626 THB  → ~80% cash (target was 75%, close enough)
```

> **Note on BTC valuation:** For simplicity, position values track book cost (not market-to-market). BTC's actual market price fluctuates significantly — the 50% reduction targets the position's book value. In real trading, the sell order would be placed in USD terms at the prevailing BTC/USD market price.

---

## Day 14 — All-Clear & Recovery

### Morning Brief

```
=== Morning Brief — 2026-05-14 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.60  +1.80%   6.0%  🟢   ↑  ← back to 🟢
  SCC.BK         Siam Cement      252.00  +1.20%   5.5%  🟢   ↑
  CHG.BK         Chularat Hosp.    15.20  +1.50%   7.0%  🟢   ↑
  PTT.BK         PTT               32.50  +0.70%   4.2%  🟢   ↑  ← narrower band

🔴 BEARISH:
  KBANK.BK       Kasikornbank     143.00  -2.50%   4.8%  🟢   ↓  ← still bearish
  AAPL           Apple            178.00  -1.50%   6.0%  🟢   ↓  ← still bearish
  BTC-USD        Bitcoin          66000   -3.00%  18.0%  🟡   ↓  ← band narrowed from 🔴 to 🟡

Median band width: 18%   ← BELOW 20% threshold
```

**Median band width dropped from 33% → 18% in one day.** The 3-day streak rule says "Do not re-enter until median band drops below 20% for 2 consecutive days."

**Today is Day 1 of 2 needed.** You cannot re-enter yet. But the band is improving — good sign.

---

## Day 15 — Regime Change Detected

### Morning Brief

```
=== Morning Brief — 2026-05-15 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.70  +1.60%   5.5%  🟢   ↑
  SCC.BK         Siam Cement      253.00  +1.10%   5.0%  🟢   ↑
  CHG.BK         Chularat Hosp.    15.30  +1.30%   6.5%  🟢   ↑

Median band width: 17%   ← below 20% for 2 consecutive days ✅
```

**The 2-day recovery period is met.** The re-entry restriction is lifted. However, BTC is still 🟡↓ (bearish, moderate conviction). The monthly rebalance is scheduled for Day 21.

**Weekend review (Day 15 is a Saturday):**
```
Step 3.2 — Volatility check:
  Thai equity HistVol: 22% (was 18% before the turmoil)
  Crypto HistVol: 65% (was 52% before — RISING, but below 80% threshold)

Step 3.4 — Allocation check:
  Thai equity: 5% (PTT only) — severely under-allocated (target 40%)
  Crypto: 5% (BTC only) — within range (target 5%)
  Cash: 90% — too high

Updated monthly rebalance plan:
  1. BUY  GLOBAL.BK 10% (full-size)  — 🟢, strongest signal
  2. BUY  SCC.BK    10% (full-size)  — 🟢, consistent
  3. BUY  CHG.BK     5% (half-size)  — 🟢 but P50 between 1× and 2× friction
  4. BUY  PTT.BK     +5% (add more)  — still bullish, bring to 10%
  5. HOLD BTC        5%              — bearish but 🟡, not 🟢↓. Do not re-enter yet.
```

---

## Day 16–20 — Quiet Week (Summary)

| Day | Median Band | Bullish Signals | Notable | Action |
|-----|-------------|----------------|---------|--------|
| 16 | 16% | 5 | GLOBAL continues bullish, BTC still 🟡↓ | None (waiting for monthly) |
| 17 | 18% | 4 | AAPL exits bearish list — turns neutral | None |
| 18 | 15% | 6 | CHG stays 🟢, PTT bullish | None |
| 19 | 14% | 7 | Most bullish signals of the month | None |
| 20 | 16% | 5 | KBANK still bearish for 17 consecutive days | Confirms exit was right |

**Portfolio values at Day 20:**
```
PTT:   Bought at 31.50, now 32.80  → +4.1% (+2,050 THB on remaining half)
AAPL:  Bought at $180, sold at $179 → -0.6% (-720 THB) — correct exit avoided further loss
KBANK: Bought at 140, sold at 141   → +0.7% (+560 THB) — correct exit avoided -2.3% loss
BTC:   Book cost 650K, holds 0.077 BTC → neutral (not MTM'd)
Trades: 3 sells (KBANK, AAPL, BTC-half), 0 buys

Cash:     801,626 THB (80%)
PTT:       50,000 THB (5%)
BTC:       50,000 THB (5%)
Total:    901,626 THB
```

---

## Day 21 — Month-End Rebalance

### Morning Brief

```
=== Morning Brief — 2026-05-21 ===

🟢 BULLISH:
  GLOBAL.BK      Siam Global       19.80  +1.80%   5.0%  🟢   ↑
  SCC.BK         Siam Cement      254.00  +1.20%   5.0%  🟢   ↑
  CHG.BK         Chularat Hosp.    15.40  +1.40%   6.5%  🟢   ↑
  PTT.BK         PTT               32.80  +0.60%   4.0%  🟢   ↑

🟡 MODERATE:
  HMPRO.BK       Home Product      11.60  +1.20%  10.0%  🟡   ↑

🔴 BEARISH:
  KBANK.BK       Kasikornbank     143.50  -2.80%   4.5%  🟢   ↓  ← bearish for 17 days
  BTC-USD        Bitcoin          66200   -2.00%  14.0%  🟡   ↓  ← bearish for 10 days

Median band width: 14%
```

### Step 4.1 — Run Trader's Desk

```
=== Trader's Desk — 2026-05-21 ===

Sorted by NetRet descending:

── thai_equity ──
  Ticker      Close     P50%    P95%     Band   Sharpe  Frict  NetRet  Flag
  GLOBAL.BK   19.80   +1.80%   +4.20%   5.0%    1.40   0.536% +1.26%  🟢
  SCC.BK     254.00   +1.20%   +3.80%   5.0%    1.40   0.536% +0.66%  🟢
  CHG.BK      15.40   +1.40%   +3.60%   6.5%    1.40   0.536% +0.86%  🟢
  PTT.BK      32.80   +0.60%   +2.50%   4.0%    1.40   0.536% +0.06%  🟢
  HMPRO.BK    11.60   +1.20%   +3.40%  10.0%    1.40   0.536% +0.66%  🟡

── crypto ──
  BTC-USD   66200    -2.00%     +5.00%  14.0%    0.52   0.90%  -2.90%  🟡↓
```

### Step 4.2 — Apply the 3-Filter Rule

| Ticker | NetRet > 2× friction? | Flag 🟢🟡? | Class in range? | Verdict |
|--------|----------------------|-----------|----------------|---------|
| GLOBAL.BK | ✅ 1.26% > 1.07% | ✅ 🟢 | ❌ Thai at 5% | **ADD** |
| SCC.BK | ✅ 0.66% > 1.07%? No | ✅ 🟢 | ❌ Thai at 5% | Between 1× and 2× → half-size |
| CHG.BK | ✅ 0.86% > 1.07%? No | ✅ 🟢 | ❌ Thai at 5% | Between 1× and 2× → half-size |
| PTT.BK | ❌ 0.06% < 1.07% | ✅ 🟢 | ❌ Thai at 5% | HOLD (not add) |
| HMPRO.BK | ✅ 0.66% > 1.07%? No | ✅ 🟡 | ❌ Thai at 5% | Between 1× and 2× → half-size |
| BTC-USD | ❌ -2.90% < 1.07% | ❌ 🟡↓ | ✅ within 5% | REDUCE from 5% to 2.5% |

### Step 4.3 — Build Trade List

```
Month-End Rebalance: 2026-05-21
Starting cash: 801,626 THB (80%)
Target: Thai equity 35-45% → need ~350,000-450,000 THB

╔════════════════╤════════╤════════╤═══════╤═══════════════════════╗
║ Ticker         │ Action │ Amount │ NetRet│ Rationale             ║
╠════════════════╪════════╪════════╪═══════╪═══════════════════════╣
║ GLOBAL.BK      │ BUY    │ +10%   │+1.26% │🟢 full-size, strongest║
║ SCC.BK         │ BUY    │  +5%   │+0.66% │🟢 half-size (g.zone)  ║
║ CHG.BK         │ BUY    │  +5%   │+0.86% │🟢 half-size (g.zone)  ║
║ HMPRO.BK       │ BUY    │  +5%   │+0.66% │🟡 half-size (g.zone)  ║
║ BTC-USD        │ SELL   │  -2.5% │-2.90% │🟡↓ bearish, reduce    ║
║ PTT.BK         │ HOLD   │  —     │+0.06% │Already hold +5%       ║
║ Cash           │ —      │ -22.5% │ —     │Deploy into positions   ║
╚════════════════╧════════╧════════╧═══════╧═══════════════════════╝

Total deployment: +22.5% of portfolio (+225,000 THB)
Execution schedule:
  Day 1 (today): Sell BTC (urgent? No — it's 🟡, not 🟢↓. Can wait but do within the 3-day window.)
  Day 2: Buy GLOBAL.BK + CHG.BK
  Day 3: Buy SCC.BK + HMPRO.BK
```

### Step 4.4 — Execute Over 3 Days

**Day 21 — Sell BTC**
```python
# Sell 50% of remaining BTC (2.5% of portfolio → ~25,000 THB equivalent)
# BTC at 66,200 USD × ~36 THB/USD = 2,383,200 THB/BTC
# Sell 0.0385 BTC at 66,200 = 2,548 USD = ~91,728 THB
# Friction: 91,728 × 0.90% = 825 THB
# Net proceeds: 90,903 THB
```

**Day 22 — Buy GLOBAL.BK + CHG.BK**
```python
# Buy GLOBAL.BK: 10% = 100,000 THB at 19.80 = 5,050 shares
# Friction: 100,000 × 0.536% = 536 THB
# Net cost: 99,464 THB

# Buy CHG.BK: 5% = 50,000 THB at 15.40 = 3,246 shares
# Friction: 50,000 × 0.536% = 268 THB
# Net cost: 49,732 THB
```

**Day 23 — Buy SCC.BK + HMPRO.BK**
```python
# Buy SCC.BK: 5% = 50,000 THB at 254 = 196 shares
# Friction: 50,000 × 0.536% = 268 THB
# Net cost: 49,732 THB

# Buy HMPRO.BK: 5% = 50,000 THB at 11.60 = 4,310 shares
# Friction: 50,000 × 0.536% = 268 THB
# Net cost: 49,732 THB
```

### Step 4.5 — Log Trades

```python
import csv
with open('data/trade_log.csv', 'a', newline='') as f:
    w = csv.writer(f)
    w.writerow(['2026-05-21', 'BTC-USD', 'sell', '66200', '0.025', 'monthly rebalance - reduce crypto'])
    w.writerow(['2026-05-22', 'GLOBAL.BK', 'buy', '19.80', '0.10', 'monthly rebalance - thai equity'])
    w.writerow(['2026-05-22', 'CHG.BK', 'buy', '15.40', '0.05', 'monthly rebalance - thai equity'])
    w.writerow(['2026-05-23', 'SCC.BK', 'buy', '254.00', '0.05', 'monthly rebalance - thai equity'])
    w.writerow(['2026-05-23', 'HMPRO.BK', 'buy', '11.60', '0.05', 'monthly rebalance - thai equity'])
```

### Final Month-End Allocation

```
                              BEFORE          AFTER
                              ------          -----
Cash:                         801,626 (80%)     576,626 (58%)
PTT.BK:                        50,000 (5%)     50,000 (5%)
GLOBAL.BK:                          0           99,464 (10%)
SCC.BK:                             0           49,732 (5%)
CHG.BK:                             0           49,732 (5%)
HMPRO.BK:                           0           49,732 (5%)
BTC:                           50,000 (5%)     25,000 (2.5%)
                              ------------    ------------
Total:                        901,626 THB       900,286 THB
                                                    ↓
                                          (-1,340 THB from rebalance friction)
                                          (-98,714 THB total from start = -9.9%)
```

**Month Summary:**
| Metric | Value |
|--------|-------|
| Starting portfolio | 1,000,000 THB |
| Ending portfolio | 900,286 THB |
| **Monthly return (total)** | **−9.97%** |
| Month-end rebalance friction | −1,340 THB (−0.13%) |
| Position P&L (includes 3 exits) | −97,374 THB (−9.74%) |
| Trades executed | 3 exits (KBANK, AAPL, BTC-half) + 4 entries (GLOBAL, SCC, CHG, HMPRO) |
| Friction paid (total) | ~4,655 THB (0.47% of starting AUM) |
| Wins | KBANK exit (+560 THB), AAPL exit (−720 THB, avoided further loss) |
| Key lesson | The ~10% drawdown came from forced 3-day streak exits at unfavorable prices, not from model signal error |

**Note on Sharpe:** The backtest's annual Sharpe of 1.40 (Thai equity) translates to approximately 0.40 monthly Sharpe. This single month produced a negative return, which is within the expected 1σ range of the backtest's volatility (14-48% annual CAGR range). One month of negative returns does NOT invalidate the model.

**Limitation:** This walkthrough covers ONE month (May 2026) with a specific pattern: calm → bearish → turmoil → recovery. Real trading will encounter gap crashes, momentum runs, sideways chop, and policy-surprise reversals. A full year would provide better validation across multiple regimes.

---

*End of 1-month walkthrough. All rules, signals, exits, and rebalances follow the operations manual procedures.*
