# Real-Market Dashboard & Operating Process — Design Spec

> Scope: Local dashboard web app + automated daily pipeline for live Thai equity trading (paper → broker instructions). Small retail (500K THB), Thai equity only, zero-shot Kronos-small.

---

## 1. User Profile & Constraints

| Parameter | Value |
|-----------|-------|
| Capital | 500,000 THB |
| Universe | 49 Thai equity tickers (SET50 + mid-caps) |
| Model | Kronos-small, zero-shot, n_samples=50, pred_len=20, lookback=400 |
| Positions | 5 max, equal-weight (20% each when fully deployed) |
| Allocation bands | BULL 15% / NEUTRAL 10% / BEAR 5% / EXIT 0% |
| Bootstrap | Start in NEUTRAL (10%) until ≥ 20 closed trades exist, then switch to Sharpe-driven |
| Band caps | BULL max 25%, NEUTRAL min 5% (hard caps, monthly review) |
| Stop-loss | −10% portfolio drawdown → liquidate all |
| Execution | Phase 1: paper trading (UI). Phase 2: CSV export → manual broker entry |
| No broker API | System never connects to Settrade or any broker |

---

## 2. Architecture

### 2.1 Components (3 new modules)

| Module | Path | Responsibility |
|--------|------|----------------|
| Dashboard Server | `scripts/dashboard.py` | Flask app on port 5555, serves single-page HTML, 4 REST endpoints |
| Portfolio Engine | `kth/trading/portfolio.py` | Paper/live position tracking, P&L, equity curve, trade log |
| Trade Generator | `kth/trading/trade_gen.py` | Reads forecast cache + positions, applies 3-filter rule, generates trade tickets |

### 2.2 REST Endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/forecasts` | GET | Today's forecast summary: all 49 tickers, exp_ret, band, flag, net_ret, rank |
| `/api/positions` | GET | Current positions: ticker, shares, avg_cost, mark, P&L, weight, signal, action |
| `/api/risk` | GET | Allocation band, Sharpe, drawdown, P&L MTD, win rate, market state |
| `/api/trades` | GET/POST | GET: today's trade ticket. POST: execute paper trade (record fill) |
| `/api/health` | GET | Cron pipeline status, last successful forecast date, any step failures |

### 2.2a POST /api/trades Request Schema

```json
{
  "trades": [
    {
      "ticker": "KBANK.BK",
      "action": "exit",
      "shares": 3500,
      "fill_price": 142.00,
      "order_type": "market"
    },
    {
      "ticker": "CPALL.BK",
      "action": "buy",
      "shares": 800,
      "fill_price": 56.70,
      "order_type": "limit"
    }
  ],
  "date": "2026-06-02",
  "mode": "paper"
}
```

Response: `{"recorded": 2, "portfolio_value": 512300, "cash": 406250, "new_positions": [{"ticker":"CPALL.BK","shares":800,"weight":0.09}]}`

Paper and live trades use the same endpoint with different `mode` values. The portfolio engine routes to the correct storage file.

### 2.3 Data Flow

```
cron (06:30 BKK) — each step logs to data/logs/cron_{date}.log
  ├─[1] scripts/download_data.py          → data/raw/*.parquet
  │     │ 3 retries with 2min backoff on failure
  │     └─ FAIL → log "STEP1_FAILED", exit. Dashboard shows ⚠ banner.
  ├─[2] scripts/dashboard.py --generate   → data/forecast_cache/{date}/
  │     │ Deletes today's cache first (fresh forecast)
  │     │ Loads Kronos-small, runs forecast_batch(49 tickers, n_samples=50)
  │     │ 3 retries on OOM or GPU failure
  │     └─ FAIL → log "STEP2_FAILED", exit. Dashboard shows stale date + "⚠ Forecast generation failed."
  ├─[3] kth/trading/trade_gen.py          → data/positions/trade_ticket_{date}.json
  │     └─ FAIL → log "STEP3_FAILED". Dashboard shows "Trade ticket unavailable."
  └─[4] Dashboard /api/health confirms all 3 steps passed → no banner
```

Key constraint: Model runs once per day via cron. Dashboard reads cached results. No GPU dependency in the web server.

The `/api/health` endpoint returns:
```json
{
  "last_forecast_date": "2026-06-02",
  "steps": {"download": "ok", "forecast": "ok", "trade_gen": "ok"},
  "stale": false,
  "pipeline_log": "data/logs/cron_2026-06-02.log"
}
```
Dashboard polls `/api/health` on load and shows appropriate banner for any step failure.

### 2.4 Storage

| File | Format | Purpose |
|------|--------|---------|
| `data/positions/paper_portfolio.json` | JSON | Current positions, equity curve, cash balance |
| `data/positions/trade_log.csv` | CSV | Complete trade history with rationale codes |
| `data/positions/live_portfolio.json` | JSON | Phase 2 only — actual fill prices for reconciliation |
| `data/positions/trade_ticket_{date}.json` | JSON | Ephemeral — regenerated daily by trade_gen, consumed by dashboard |

### 2.5 Unchanged Modules

- `kth/data/` — loader, universe, friction. No changes.
- `kth/models/` — Kronos wrapper. Zero-shot only, no changes.
- `kth/backtest/` — walkforward backtest. No changes.
- `scripts/morning_routine.py` — deprecated, replaced by cron + dashboard.

---

## 3. Dashboard Layout

Single-page HTML, vanilla JS AJAX polling every 60 seconds (no full page reload). Data updated in-place via DOM patching. 5 zones in priority order:

### 3.0 Mode Indicator (Header)

Dashboard header displays the active trading mode prominently:

| Mode | Badge | Theme | Button Label | Favicon |
|------|-------|-------|-------------|---------|
| Phase 1 (Paper) | `📋 PAPER` — blue background | Blue (#1565C0) accents | "Record Paper Trade" | Blue circle |
| Phase 2 (Live) | `💰 LIVE` — red background | Green/red accents | "Confirm Live Trade" | Green circle |

Mode is toggled via config in dashboard.py. Only one mode active at a time. The system prevents live mode until Phase 2 gate passes (§5.1).

### 3.1 Risk Bar (Top Row, 7 tiles) — updated via AJAX, no scroll loss

| Tile | Content | Source |
|------|---------|--------|
| Market State | Normal / Elevated Vol / Turmoil | Thresholds: Normal = median band < 20% AND <15 tickers 🔴. Elevated = median band 20-30% OR 15-30 tickers 🔴. Turmoil = median band > 30% OR >30 tickers 🔴. |
| Allocation | BULL 15% / NEUTRAL 10% / BEAR 5% / EXIT 0% | Trailing Sharpe from equity curve. Bootstrap: NEUTRAL until ≥ 20 closed trades. |
| Trailing Sharpe | 12-week rolling Sharpe | Paper portfolio equity curve (Phase 2: switches to live portfolio equity curve) |
| Drawdown | Current DD % + progress bar to −10% | Paper portfolio peak-to-trough (Phase 2: switches to live portfolio) |
| P&L MTD | Month-to-date THB + % | Paper portfolio (Phase 2: switches to live portfolio) |
| Win Rate | % of closed trades with positive P&L | Trade log |
| Exposure | Total position weight as % of portfolio | Sum of position weights |

### 3.2 Trade Ticket (Hero, Full-Width)

Primary action panel. Shows:

- **Exit list** (urgent, same-day): Ticker, shares, order type (market), estimated THB, rationale
- **Reduce list**: Ticker, shares, limit price, rationale
- **Buy list** (2-day window): Ticker, shares, limit price, estimated THB, rationale
- **Cash flow summary**: Gross proceeds → Friction cost → Net proceeds
- **Buttons**: [1] "Record Paper Trade" / "Confirm Live Trade" (mode-aware, primary action), [2] "Export for Broker" (secondary, CSV download)

Limit price formula: `close × (1 + expected_return / 2)`

Board lots: 100-share increments (SET standard).

### 3.3 Current Positions (Left Column)

Table columns: Ticker, Shares, Avg Cost, Mark, P&L%, Weight%, Signal, Action (HOLD/EXIT/REDUCE).

Color coding:
- Green border: HOLD (signal agrees with position)
- Red border: EXIT (signal contradicts position)
- Yellow border: REDUCE (moderate conviction)

### 3.4 Morning Brief (Right Column)

Top 10 ranked by net return. Columns: Ticker, Close, Exp Ret, Band, Flag, Net Ret.

### 3.5 Full Ranking (Bottom, Collapsible)

All 49 tickers sorted by exp_ret descending. Searchable. Shows: #, Ticker, Name, Close, Exp Ret, Band, Flag.

### 3.6 Empty / Edge States

| State | Display |
|-------|---------|
| All-red day (>30 tickers 🔴) | Banner: "High uncertainty day — 42/49 tickers flagged red. Stay in cash." Trade ticket hidden. |
| Stop-loss triggered | Banner: "STOP-LOSS −10% TRIGGERED. Portfolio frozen. Manual review required." All trade actions disabled. |
| No forecasts yet (first use) | "No forecasts generated. Run: <code>venv/bin/python scripts/dashboard.py --generate</code>" (GPU required, ~12 min). Dashboard auto-refreshes when cache appears. |
| Stale forecasts (>24 hrs old) | Banner: "⚠ Forecasts from {date} ({hours} hrs old). Data may be stale." |
| No positions held | "No positions yet. Paper trade to start tracking." |

### 3.7 Signal Health Row (Below Risk Bar, Collapsible)

- Trailing 20-trade direction accuracy (%)
- Live Sharpe vs backtest Sharpe delta
- Warning if: accuracy < 45% for 5+ trades OR live Sharpe < 0.5 for 2+ weeks
- Warning action: "🚨 Model review recommended — halve position sizes until accuracy recovers"

---

## 4. Decision Rules

### 4.1 Daily Decision Tree

```
06:45 — Open dashboard
  │
  ├─ Market State = TURMOIL? → STAY CASH. Check tomorrow.
  ├─ Stop-loss triggered? → LIQUIDATE ALL. Manual review.
  ├─ Any 🟢↓ EXIT on held positions? → Exit SAME DAY (market order).
  ├─ Any 🟢↑ BUY with net_ret > 2× friction? → Add to buy list. Execute within 2 days.
  ├─ Any 🟡 signals? → Half-size only.
  └─ No signals / all 🔴? → Stay cash. Log note.
```

### 4.2 Weekly Checks (Sunday/Monday)

1. **Regime check:** >5 tickers with HistVol > 30% → halve allocation
2. **Signal quality:** Trailing accuracy < 40% → flag for reduced sizing
3. **Allocation drift:** Any position > 25% or < 5% → add to monthly rebalance
4. **Live vs backtest:** Live CAGR within 14-48% band? If below 2+ weeks → review execution
5. **Weekly log:** Note regime, quality, overrides, trade count
6. **Broker export:** If Phase 2, export consolidated trade CSV

### 4.3 Monthly Rebalance (Last Friday)

1. **3-filter rule** per position:
   - Net return > 2× friction? Keep.
   - Confidence 🟢 or 🟡? Keep.
   - Allocation within 15-25%? Keep.
   - 1-2 fail → halve. All 3 fail → exit.
2. **Build rebalance list** from 3-filter results
3. **Execute over 2-3 days:** Day 1 = exits, Day 2 = buys, Day 3 = adjustments
4. **Monthly snapshot:** P&L, win rate, Sharpe, drawdown vs backtest benchmarks
5. **Adjust bands (symmetric):**
   - Trailing Sharpe > 1.5 for 2 consecutive months → raise BULL to 20%, NEUTRAL to 12%
   - Trailing Sharpe < 0.5 for 2 consecutive months → revert BULL to 15%, NEUTRAL to 5%
   - Hard caps: BULL max 25%, NEUTRAL min 5%. BEAR and EXIT percentages are fixed and never change.

### 4.4 Emergency Triggers

| Trigger | Action | Re-entry |
|---------|--------|----------|
| DD crosses −10% | Liquidate ALL. Freeze. | ALL of: (a) 10 trading days since liquidation, (b) median band width < 20% for 5 consecutive days, (c) ≥ 5 tickers with 🟢 flag, (d) "Reactivate" button clicked in dashboard. No judgment calls. |
| 3 consecutive all-red days | Reduce all by 50%. 75% cash. | Median band < 20% for 2 days |
| HistVol > 30% on >10 tickers | Halve allocation. Cash. | All < 30% for 2 weeks |
| Single ticker P&L < −15% | Exit that ticker only. | 2 fresh 🟢 signals after exit |

> **Glossary:** "Allocation" = capital deployment band percentage (BULL 15%/NEUTRAL 10%/BEAR 5%/EXIT 0%). Reducing allocation cuts all positions proportionally. "Position size" = per-ticker portfolio weight (max 20%). Reducing position size cuts one ticker, others unchanged. When the spec says "halve position sizes" (§3.7) it means per-ticker. When it says "halve allocation" (§4.2 step 1) it means the band percentage.

---

## 5. Phase 2: Broker Instructions

### 5.1 Transition Gate (ALL must pass)

- [ ] Paper traded ≥ 4 weeks (20+ trading days)
- [ ] ≥ 10 round-trip trades in paper
- [ ] Win rate ≥ 50% (computed via FIFO matching: first-bought shares are first-sold)
- [ ] Live Sharpe ≥ 0.90 (within 0.5 of backtest 1.40)
- [ ] No stop-loss trigger in paper period
- [ ] ≥ 3 full monthly rebalances executed in paper

### 5.2 CSV Export Format

```csv
date,action,ticker,shares,order_type,limit_price,estimated_thb,rationale
2026-06-02,exit,KBANK.BK,3500,market,,~497000,🟢↓ bearish net_ret=-2.34%
2026-06-02,buy,CPALL.BK,800,limit,56.70,~45360,🟢↑ rank#3 net_ret=+1.01%
```

### 5.3 Live vs Paper Reconciliation

Weekly panel in dashboard comparing paper P&L vs broker-confirmed fills. Delta > 1% triggers investigation (market impact, wrong fill time, dividend adjustment).

### 5.4 Slippage Calibration

After 10 live trades, system computes median slippage per ticker. Replaces hardcoded friction with measured values for net return calculation.

---

## 6. Implementation

### 6.1 New Files

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `scripts/dashboard.py` | ~200 | Flask app + REST endpoints + `--generate` subcommand |
| `scripts/cron_pipeline.sh` | ~30 | Wrapper: retry + logging per step, calls download_data then dashboard.py --generate |
| `kth/trading/__init__.py` | 0 | Package marker |
| `kth/trading/__init__.py` | 0 | Package marker |
| `kth/trading/portfolio.py` | ~150 | Position tracking, P&L, equity curve |
| `kth/trading/trade_gen.py` | ~120 | Trade ticket generation, 3-filter logic |
| `scripts/static/dashboard.html` | ~400 | Single-page dashboard: vanilla JS AJAX polling (no full page reload), inline critical CSS, DOM-in-place updates |
| `scripts/static/style.css` | ~80 | Dashboard styles (extracted from inline for clarity) |

### 6.2 Cron Script

The `scripts/dashboard.py --generate` subcommand:
1. Sets `HF_HUB_OFFLINE=1`, inserts Kronos repo into sys.path
2. Loads Kronos-small model
3. Deletes today's forecast cache directory (fresh run)
4. Runs `forecast_batch(49 tickers, pred_len=20, n_samples=50, lookback=400)`
5. Runs `trade_gen.py` to produce today's trade ticket
6. Logs each step to `data/logs/cron_{date}.log`
7. Retries each step up to 3 times with 2-minute backoff on failure

### 6.3 Cron Pipeline Script

`scripts/cron_pipeline.sh` wraps both steps with retry logic:
```bash
#!/bin/bash
LOG="data/logs/cron_$(date +%Y-%m-%d).log"
RETRIES=3; BACKOFF=120
for step in "download_data.py" "dashboard.py --generate"; do
  for i in $(seq 1 $RETRIES); do
    venv/bin/python scripts/$step >> $LOG 2>&1 && break
    echo "[RETRY $i/$RETRIES] $step failed, waiting ${BACKOFF}s..." >> $LOG
    sleep $BACKOFF
  done || { echo "STEP_FAILED: $step" >> $LOG; exit 1; }
done
echo "PIPELINE_OK" >> $LOG
```

### 6.4 Modified Files

| File | Change |
|------|--------|
| None in `kth/` | All new code is additive |

### 6.5 Dependencies

All exist in requirements already: Flask, pandas, numpy, PyTorch, Kronos.

### 6.6 Launch Sequence

```bash
# One-time setup
mkdir -p data/positions scripts/static

# Daily cron (add to crontab)
30 6 * * 1-5 cd /path/to/kronos-th && bash scripts/cron_pipeline.sh

# Start dashboard (manual or systemd)
venv/bin/python scripts/dashboard.py --serve

# Open browser
# http://localhost:5555
```

### 6.7 Implementation Notes (Nice-to-Have)

Non-blocking enhancements to consider during or after initial build:

| # | Enhancement | Rationale | Effort |
|---|-------------|-----------|--------|
| N1 | Sector concentration warning | 5 equal-weight positions could all be in banking/energy. Detect when ≥ 3 positions share the same SET sector and show ⚠ "Sector concentration: 3/5 in Banking." | Small |
| N2 | Execution confirmation modal | Before recording a paper/live trade, show a confirmation modal summarizing: tickers, shares, estimated THB, total friction cost. Requires explicit "Confirm" click. Prevents fat-finger errors. | Medium |
| N3 | Colorblind-accessible status icons | Replace color-only borders with text labels + icons alongside border colors. Ensures ~8% of male users can read the dashboard. | Trivial |
| N4 | Mobile responsive layout declaration | Explicitly declare dashboard as "desktop-only (≥1024px)". If mobile is desired, add a single-column stacked layout at ≤768px. | Trivial (declare only) |
| N5 | Daily log search/filter | Full ranking table includes a text search box and a filter dropdown (by flag: 🟢/🟡/🔴, by direction: ↑/↓). | Small |
| N6 | Equity curve chart | Sparkline chart showing paper portfolio equity vs backtest reference equity. Gives visual intuition for drawdown progression (not just the current %). | Medium |
| N7 | Dividend adjustment prompt | Thai stocks pay dividends 1-2×/year. When a held ticker goes ex-dividend, prompt user to enter dividend amount for accurate P&L tracking. Otherwise P&L shows an artificial drop. | Small |

---

## 7. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Flask, not FastAPI | Simpler, no async needed for single-user local app |
| 2 | Polling (60s), not WebSocket | Adequate for daily-bar trading. Zero complexity. |
| 3 | Zero GPU in dashboard server | Model runs once via cron. Dashboard is read-only from cache. |
| 4 | Paper portfolio in JSON, not DB | Single-user, no concurrency. JSON is debuggable. |
| 5 | CSV trade log (append-only) | Human-readable, easy to audit, spreadsheet-compatible |
| 6 | No login/auth | Localhost only. Not exposed to network. |
| 7 | Phase 1 before Phase 2 enforced | Gate prevents premature real-money trading |
| 8 | Market order for exits, limit for buys | Exits are urgent (bearish signal = price likely dropping). Buys can wait for fill. |
| 9 | Allocation bands from backtest Sharpe | Automated risk sizing removes emotion from position decisions |
| 10 | 6-item Phase 2 transition gate | All criteria from ops manual + quant PM review feedback |

---

## 8. What This Is NOT

- Not an autotrader. Zero broker API integration.
- Not a multi-user system. Single trader, single portfolio.
- Not exposed to the internet. Localhost only.
- Not a replacement for broker statements. Always reconcile against official records.
- Not financial advice. Research tool. All backtest caveats apply.

---

*Document version: 2026-06-02. Source: brainstorming session with quant PM + UX/UI review. Supersedes sections of operations-manual.md for automated pipeline.*
