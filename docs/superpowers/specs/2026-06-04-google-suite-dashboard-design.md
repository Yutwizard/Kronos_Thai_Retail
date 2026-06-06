# Google Suite Dashboard Design

**Date:** 2026-06-04
**Status:** Revised v5 (pre-implementation final 2026-06-04) + parity fixes shipped 2026-06-06
**Companion to:** The Flask dashboard (`scripts/dashboard.py`, `docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md`) — both are available; choose based on environment. Google Suite is zero-cost, browser-based, no local GPU; Flask is local Python + GPU.
**Implementation plan:** [docs/superpowers/plans/2026-06-04-google-suite-implementation-plan.md](../plans/2026-06-04-google-suite-implementation-plan.md)

---

## What Is This?

**Paper trading** means simulated investing with no real money at stake. You follow the same
steps as a real investor (run forecasts, place orders at a broker), but the system tracks
your hypothetical results so you can evaluate the model's performance before committing real
capital. Nothing in this system moves actual money.

This system covers **Thai retail investing**: SET-listed Thai equities, US stocks/ETFs,
crypto, gold, and FX — the 100-ticker universe a Thai retail investor can actually buy.

---

## Daily Routine

```
BEFORE market opens (~7:00–8:30 AM Bangkok time, UTC+7):
  1. Open Colab → "Run All" (takes ~20 min on first run, ~5 min after)
  2. Wait for Cell 19 summary to print — confirms pipeline completed
  3. Open dashboard URL → check Trade Ticket tab
  4. Click "Export CSV" → place orders at your broker (e.g. Settrade)
     → Orders must be multiples of 100 shares (SET board lot)

AFTER orders fill (same day or next morning):
  5. Open "Kronos-TH Portfolio" spreadsheet → Trade Ticket sheet
  6. For each ticker you traded, enter in columns 8-10:
     - filled_price   = the actual price your broker executed at
     - filled_shares  = the actual number of shares filled
     - fill_timestamp = the time of fill (e.g. "2026-06-04 10:15")
  7. If an order wasn't filled at all, leave the row blank
     (Colab will use the forecast close as an estimate next run)

ANYTIME:
  8. Visit the web app URL to monitor your portfolio
```

---

## Glossary

**Fill / fill price:** The actual price at which your broker executed your order. If you
placed a buy order for PTT.BK and it executed at ฿35.50 per share, your fill price is 35.50.
This differs from the forecast close (the model's estimated price used for planning).

**3-filter rule:** The model only recommends a trade if all three conditions are met:
1. `net_return > friction` — expected return after all costs is positive
2. `confidence != red` — the model's uncertainty band is not too wide (band_width ≤ 30%)
3. `sector limit ≤ 2` — no more than 2 open positions in the same SET sector at once

**Allocation band:** Controls per-position sizing based on trailing 12-week Sharpe ratio.
Source: `kth/trading/portfolio.py:compute_metrics()`.
- **BULL** — Sharpe > 1.0 → 15% of capital per position (up to 75% total with 5 positions)
- **NEUTRAL** — Sharpe 0.5–1.0 → 10% per position (up to 50% total)
- **BEAR** — Sharpe 0–0.5 → 5% per position (up to 25% total)
- **EXIT** — Sharpe ≤ 0 or <20 closed trades → 0%, stay in cash

The model sizes each new buy to `allocation_pct × total_equity`. You do not need to
adjust position sizing manually — just follow the Trade Ticket.

**Frozen portfolio:** If total portfolio drawdown reaches −10% from peak, the model stops
generating new buy orders. `is_frozen = true` in Risk Metrics; a red banner appears on the
Dashboard. To resume, liquidate all positions and reset the portfolio (re-run Cell 4 with
a fresh start).

**Board lot:** The minimum tradeable unit on the SET is 100 shares. All orders must be
multiples of 100. The Export CSV already rounds to the nearest board lot. If your broker
rejects an order, check that shares are a multiple of 100.

**Metrics glossary** (for Risk Metrics tab tooltips):

| Metric | Plain-English meaning |
|--------|----------------------|
| Trailing Sharpe 12w | Risk-adjusted return over the last 12 weeks. >1.0 = good, <0 = losing |
| Max Drawdown | Largest peak-to-trough loss ever recorded. −17.97% in 2022–2024 backtest. |
| MTD P&L | Profit or loss since the 1st of the current month |
| Win Rate | % of completed round-trips (buy + sell) that were profitable |
| Calmar Ratio | Annual return ÷ max drawdown. Higher = better risk-adjusted |
| Sortino Ratio | Like Sharpe but only penalises downside volatility, not upside |
| Drawdown Velocity | Speed at which drawdown is accelerating. High velocity = increasing risk |
| Bootstrap p-value | Statistical confidence that the live edge is real, not luck. <0.05 = significant |
| Friction YTD | Total trading costs (commission + slippage) accumulated this year in % and ฿ |
| Deployed % | % of total capital currently in open positions |

---

## Migration Note

This design is a **fresh start** — existing `data/positions/paper_portfolio.json` and
`data/positions/trade_log.csv` are not migrated automatically. If you have paper trading
history worth preserving, run `google_suite/migrate_to_sheets.py` (to be built) before
the first Colab run. Otherwise, initialise the spreadsheet as blank and let the first
pipeline run establish the starting state.

---

## Motivation

Replace the local Flask dashboard with a zero-cost Google-hosted alternative:
- **Google Colab** as the daily computation engine
- **Google Sheets** as the persistent data store + fill-confirmation input surface
- **Google Apps Script web app** as the dashboard UI

All accessible from any device via a URL. No server to maintain, no port forwarding, no
local uptime requirement.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Google Colab (Compute Engine)                           │
│  User opens → "Run All" → pipeline completes            │
│  Downloads OHLCV → Runs Kronos → Generates ticket       │
│  Reads prior-day fills → updates portfolio state        │
│  Validates data → writes to staging → promotes to live  │
│  Writes pipeline status + LINE Notify on failure        │
└──────────────────────┬──────────────────────────────────┘
                       │  reads fills back ↑ writes ticket ↓
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Google Sheets (Data Store + Fill Input)                 │
│  Single spreadsheet "Kronos-TH Portfolio"                │
│  9 live sheets + 5 staging sheets = 14 total tabs       │
│  Trade Ticket has user-editable fill columns            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Google Apps Script Web App (Dashboard)                  │
│  Container-bound to the spreadsheet                     │
│  SpreadsheetApp.getActiveSpreadsheet() — no ID needed   │
│  Single getAllData() call on page load                   │
│  Server-side CacheService (5 min) + read limits         │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Daily (manual):** User opens Colab notebook, clicks "Run All"
2. Colab writes `status=running` to Pipeline Status sheet
3. **Colab reads prior-day fills** from Trade Ticket sheet (`filled_price`, `filled_shares`,
   `fill_timestamp` columns). Captures fills into memory. If any fill column is blank, that
   ticker falls back to forecast close as assumed fill (warning printed).
   > ⚠️ **Workflow constraint:** enter actual fills into the Trade Ticket sheet BEFORE
   > running the next day's Colab. **Cell 6** reads and captures fills; Cell 13 then
   > overwrites the Trade Ticket with the new ticket (fill columns blank). Any fills not
   > entered before "Run All" are permanently unrecoverable for that date.
4. Colab downloads OHLCV data → runs Kronos forecast → generates trade ticket
5. Colab applies fills captured in step 3 to update cash, positions, and equity curve
6. Colab computes all metrics and validates data (no NaN, shares > 0, prices > 0)
7. Colab writes to **staging** sheets: Portfolio, Positions, Forecasts, Trade Ticket
   (fill columns blank), Risk Metrics
8. If validation passes, Colab atomically promotes staging → live sheets (copy values,
   clear staging)
9. Colab appends new trades to Trade Log — ID dedup guard (skip if `id` already exists)
10. Colab updates Forecast History: resolves prior-day `actual_return`, then appends
    today's predictions
11. Colab writes `status=completed`, `timestamp=now` to Pipeline Status sheet
12. If any step fails, Colab writes `status=failed`, `error=<message>` to Pipeline Status
    and sends LINE Notify
13. **After broker execution:** User opens Trade Ticket sheet, enters actual fill prices and
    shares in `filled_price`, `filled_shares`, `fill_timestamp` columns — ready for tomorrow's
    Colab run (step 3)
14. **Anytime:** User visits web app URL → checks Pipeline Status → reads from live sheets →
    renders dashboard
15. User clicks "Export CSV" → staleness check → CSV text downloaded via Blob

---

## Google Sheets Layout

Single spreadsheet: **Kronos-TH Portfolio**

**9 live sheets + 5 staging sheets = 14 total tabs.**

### Live Sheets

| Sheet | Columns | Written by | Read by | Row behavior |
|-------|---------|------------|---------|--------------|
| **Portfolio** | cash, initial_capital, mode, model_version, forecast_date | Colab | Web App | Single row, overwritten daily |
| **Equity Curve** | date, equity, cash, invested | Colab | Web App | **Date-aware upsert** |
| **Positions** | ticker, shares, avg_cost, entry_date, sector, current_price, pnl, pnl_pct, pct_to_stoploss | Colab | Web App | Full replace daily |
| **Trade Log** | timestamp, ticker, action, shares, price, rationale, friction_cost, model_version, id, ref_id | Colab | Web App | **Append-only with CANCEL convention** |
| **Forecasts** | date_updated, ticker, rank_score, exp_ret, band_width, confidence, net_return, p5, p50, p95, sector | Colab | Web App | Full replace daily |
| **Forecast History** | date, ticker, predicted_direction, predicted_return, entry_close, actual_return, was_correct | Colab | Web App | Append new rows; targeted in-place update of `actual_return`/`was_correct` on prior rows |
| **Trade Ticket** | ticker, action, shares, est_cost_thb, rationale, sector, confidence, filled_price, filled_shares, fill_timestamp | Colab (cols 1-7) / User (cols 8-10) | Web App + Colab | Full replace daily (cols 1-7 via staging); cols 8-10 user-editable, read by next Colab run |
| **Risk Metrics** | date, equity, cash, deployed_pct, trailing_sharpe_12w, max_drawdown_pct, mtd_pnl_pct, trade_win_rate, calmar_ratio, sortino_ratio, drawdown_velocity, allocation_band, allocation_pct, market_state, is_frozen, bootstrap_p_value, friction_ytd_pct, friction_ytd_thb | Colab | Web App | **Date-aware upsert** |
| **Pipeline Status** | last_run_timestamp, status, duration_seconds, error_message, sheets_updated | Colab | Web App | Single row, overwritten each run |

### Staging Sheets (5 temporary tabs)

`Portfolio_staging`, `Positions_staging`, `Forecasts_staging`, `Trade Ticket_staging`,
`Risk Metrics_staging`. Written during pipeline execution, promoted to live on validation
pass, then cleared.

> **Note:** Trade Log and Forecast History are **never staged** — they use direct live
> writes (append + targeted cell updates). The staging pattern applies only to sheets
> that are fully replaced daily.

### Column Notes

**Equity Curve — `cash` and `invested`:**
- `equity` = total portfolio value (cash + all position mark-to-market)
- `cash` = uninvested cash balance
- `invested` = `equity - cash` = total position value
Computed fresh from portfolio state each run; not read from the existing equity_curve list.

**Equity Curve — date-aware upsert:**
Before appending, Colab scans column A for today's date. If found, overwrite that row.
If not found, append. Prevents equity curve inflation when Colab is re-run on the same day.
Same logic applies to Risk Metrics.

**Trade Log — column reconciliation with existing `portfolio.py`:**
- **Kept:** `timestamp` (was `date`), `ticker`, `action`, `shares`, `price`, `rationale`,
  `friction_cost`, `model_version`
- **Dropped:** `order_type` (always "market"), `mode` (always "paper"), `forecast_date`
  (redundant with `timestamp`)
- **Added:** `id` (idempotency key), `ref_id` (CANCEL pointer)

**Trade Log — CANCEL convention:**
The Trade Log is append-only and never deleted. To correct an erroneous entry (wrong ticker,
wrong shares, order that never actually filled), append a `CANCEL` row: `action=CANCEL`,
`ref_id=<id of original row>`, all other columns blank.

> ⚠️ **CANCEL only fixes the audit trail display** — it does NOT update the Portfolio
> sheet's cash or Positions. The web app shows the cancelled row with strikethrough, but
> the portfolio state (cash balance, position sizes) was already modified when the original
> trade was applied in Cell 10. If you need to undo the portfolio effect (e.g. a buy that
> never filled), you must also **manually edit the Portfolio sheet** to restore the correct
> cash and remove/reduce the position. CANCEL + manual Portfolio correction = full undo.

Common reasons to CANCEL: order rejected by broker, wrong ticker entered, duplicate entry.

Trade `id` format: `{YYYYMMDD}_{ticker}_{action}_{4-char hex}` (e.g. `20260604_PTT_buy_a3f1`).
Before appending, Colab scans column I (0-indexed: column 8) for the id — skip if already
present (idempotent re-run guard).

**Positions — `entry_date`:**
Not stored in the existing `portfolio.py` positions dict (`shares, avg_cost` only). The
Colab must track `entry_date` separately: when a BUY first executes for a ticker, record
`entry_date = today`. Carry it forward on subsequent Positions sheet writes.

**Positions — frozen portfolio:**
When `is_frozen = true` in Risk Metrics (portfolio drawdown reached −10% from peak), the
Dashboard shows a red banner: "Portfolio frozen — drawdown limit reached. Liquidate all
positions and reset to resume." Cell 9 (Generate Trade Ticket) produces no buy
recommendations while frozen. Cell 4 (Initialize) can be re-run after manual liquidation
to reset the portfolio to a new starting capital.

**Positions — `pct_to_stoploss` formula:**
`pct_to_stoploss = pnl_pct - STOP_LOSS = pnl_pct + 0.10`
(where `STOP_LOSS = −0.10`). Example: if `pnl_pct = −0.07`, `pct_to_stoploss = 0.03`.
Coloured red in the web app when < 0.03.

**Trade Ticket — `est_cost_thb` formula:**
Estimated total cost of the trade in THB, including round-trip friction:
```
est_cost_thb = shares × forecast_close × (1 + friction_rt)
```
where `friction_rt = commission_oneway×2 + slippage_oneway×2` from `FRICTION[asset_class]`
in `kth/data/universe.py`. This is an estimate; actual cost depends on fill price.

**Trade Ticket — board lot constraint:**
The SET minimum order unit is **100 shares** (one board lot). All `shares` values in the
Trade Ticket are pre-rounded to the nearest 100. The Export CSV reflects this.

**Trade Ticket — fill confirmation columns:**
Columns 8-10 (`filled_price`, `filled_shares`, `fill_timestamp`) are left blank by Colab
when writing today's ticket. User fills them after executing at the broker. Cell 6 reads
them before overwriting the ticket. If blank at run time, Colab uses forecast close as
assumed fill and logs `fill_source=assumed` in the Trade Log rationale. If an order was
only partially filled, enter the partial quantity in `filled_shares`.

**Forecast History — `entry_close` column:**
When Colab appends today's predictions, it writes `entry_close = today's close price`.
This is the reference price for computing `actual_return` on the next run.

Actual return resolution logic on Day N:
1. Read all Forecast History rows, tracking each row's **1-based Sheets row index**
   (Python list index + 2, accounting for header row).
2. Filter to rows where `actual_return` is blank.
3. For each row, look up `today_close` from today's OHLCV using the row's `ticker`.
   **If `today_close` is unavailable (download failure, suspension):** skip this row,
   leave `actual_return` blank, try again on the next run.
4. Compute `actual_return = (today_close - float(entry_close)) / float(entry_close)`
5. `was_correct = 1` if `sign(actual_return) == sign(float(predicted_return))`, else `0`
6. Collect all updates and call **`worksheet.batch_update(updates)` once** (see format below).
   Never update cells individually in a loop — 50 tickers × days of history quickly hits
   the 60 write-requests/minute quota.
7. Append today's predictions with `entry_close` populated, `actual_return` blank.

`batch_update` format:
```python
updates = []
for row_idx, actual_ret, correct in resolved_rows:
    # row_idx is 1-based Sheets row number (list_index + 2 for header)
    updates.append({
        'range': f'F{row_idx}:G{row_idx}',   # F=actual_return, G=was_correct
        'values': [[round(actual_ret, 4), correct]]
    })
if updates:
    fh_ws.batch_update(updates)
```

Forecast History bypasses staging because it requires targeted cell updates, not a full
replace.

**gspread type casting — applies to all Colab cells that read from Sheets:**
`gspread.get_all_values()` returns every cell as a Python **string**, regardless of the
stored type. All numeric columns require explicit casting before arithmetic:
```python
cash      = float(row[0])
shares    = int(row[1])
pnl_pct   = float(row[7])
is_frozen = row[13] == 'TRUE'
```
Failure to cast produces silent wrong results (`"500000.0" + 1000` raises `TypeError`) or
incorrect comparisons. Cast immediately after reading.

---

## Colab Notebook

Single file: `kronos_daily_pipeline.ipynb` (placed in `google_suite/`)

> **Colab session timeout:** Colab free tier disconnects after ~90 minutes of idle time.
> Keep the browser tab active and do not lock your screen during a run. First runs that
> download model weights may take longer; use Colab Pro or break into two sessions if needed.

> **gspread API rate limit:** Google Sheets API allows 60 write requests/minute. Add
> `time.sleep(1)` between sequential sheet writes (e.g. between each staging sheet write
> in Cell 13) to avoid intermittent HTTP 429 errors on slow connections.

### Cells

**Cell 1 — Mount Drive & Install Deps:**
```python
from google.colab import drive
drive.mount('/content/drive')

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                       "gspread", "google-auth", "pandas", "yfinance"])

# kth is NOT on PyPI — install from the Drive-mounted repo
KTH_REPO = '/content/drive/MyDrive/Kronos_Thai_Retail'   # ← adjust to your Drive path
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", KTH_REPO])
# If repo is not on Drive yet, clone it first:
# !git clone https://github.com/<user>/Kronos_Thai_Retail {KTH_REPO}
```

**Cell 2 — Load Secrets & User Parameters:**
```python
from google.colab import userdata

# ── Secrets (stored in Colab Secrets, never hardcoded) ──────────────────────
SPREADSHEET_ID = userdata.get('KRONOS_SPREADSHEET_ID')
LINE_TOKEN     = userdata.get('LINE_NOTIFY_TOKEN')   # optional, None if absent

if not SPREADSHEET_ID:
    raise ValueError(
        "KRONOS_SPREADSHEET_ID not found in Colab Secrets.\n"
        "Add it: click the key icon in the left sidebar → New secret."
    )

# ── User-configurable parameters ─────────────────────────────────────────────
INITIAL_CAPITAL = 500_000.0   # ← change this to your starting capital in THB
```
Non-sensitive parameters (tickers, friction rates) are imported from `kth.data.universe`.
`MODEL_VERSION` is imported from `kth.trading.portfolio` in Cell 4.

**Cell 3 — Authenticate & Open Spreadsheet:**
```python
from google.colab import auth
auth.authenticate_user()      # opens OAuth popup once per session

from google.auth import default
import gspread

creds, _ = default()
gc = gspread.Client(auth=creds)   # gspread >= 5.x — do NOT call gc.login()
sh = gc.open_by_key(SPREADSHEET_ID)
```
> **gspread 5.x pattern:** `gspread.Client(auth=creds)` is correct. Do **not** call
> `gc.login()` (removed in 5.x), `gspread.service_account()` (needs a key file), or
> `gspread.oauth()` (needs a local credentials file).
> Remember: all `sh.worksheet('X').get_all_values()` calls return **strings** — cast
> every numeric value explicitly before use.

**Cell 4 — Initialize Portfolio if Empty:**
```python
from datetime import date
from kth.trading.portfolio import MODEL_VERSION   # import only MODEL_VERSION, not INITIAL_CAPITAL
                                                   # INITIAL_CAPITAL comes from Cell 2 user param

portfolio_ws = sh.worksheet('Portfolio')
rows = portfolio_ws.get_all_values()
if len(rows) <= 1:   # header only or completely empty
    portfolio_ws.append_row([
        INITIAL_CAPITAL,   # cash       ← Cell 2 user parameter
        INITIAL_CAPITAL,   # initial_capital
        'paper',
        MODEL_VERSION,
        str(date.today()),
    ])
    print(f"First run: portfolio initialised at ฿{INITIAL_CAPITAL:,.0f}")
```

**Cell 5 — Set Pipeline Status: Running:**
Write `status=running`, `timestamp=now` to Pipeline Status sheet.

**Cell 6 — Read Prior-Day Fills:**
At this point the Trade Ticket sheet still contains the previous run's ticket with user-
entered fills in columns 8-10. Read columns 8-10, cast all values to float/int, build
fills dict: `{ticker: {price: float, shares: int, timestamp: str, fill_source: str}}`.
- All three columns populated → `fill_source = "confirmed"`
- Any column blank → `fill_source = "assumed"`, fall back to forecast close, print warning

**Cell 7 — Download Data:**
Fetch OHLCV via yfinance, apply 30% price sanity filter. Store as `ohlcv_dict`:
`{ticker: DataFrame}` — used by Cell 8 (forecasts), Cell 10 (portfolio), and Cell 16
(Forecast History resolution). Tickers with download failures stored in `failed_tickers`
set and skipped in all subsequent cells.

**Cell 8 — Run Forecasts:**
Load KronosTH, `forecast_batch()`, cache to Drive. Skip tickers in `failed_tickers`.

**Cell 9 — Generate Trade Ticket:**
Apply 3-filter rule:
1. `net_return > friction` — expected return after costs is positive
2. `confidence != "red"` — band_width ≤ 30%
3. sector count ≤ 2 — no more than 2 open positions in the same SET sector

**Cell 10 — Update Portfolio State:**
1. **Read current state from Sheets first:** read the Portfolio sheet's single data row to
   get current `cash`, `initial_capital`, and `is_frozen`; read the Positions sheet to
   rebuild the in-memory positions dict `{ticker: {shares, avg_cost, entry_date}}`.
   Cast all values immediately (float/int).
2. Apply fills dict from Cell 6: for each confirmed/assumed fill, execute the trade logic
   (deduct cost from cash for buys, add proceeds for sells, set `entry_date` for new
   positions). Uses actual fill prices where confirmed; forecast close where assumed.
3. Recompute mark-to-market equity from `ohlcv_dict`. For tickers in `failed_tickers`,
   use `avg_cost` as the fallback price (no P&L change shown for that position).
4. Log each applied fill to the in-memory trade log with `fill_source` in rationale.
All values read from Sheets must already be cast to numeric types.

**Cell 11 — Compute Metrics:**
Trailing Sharpe, drawdown, win rate, drawdown velocity, bootstrap p-value, cumulative
friction YTD. Reads from in-memory state, not from Sheets.

**Cell 12 — Validate Data:**
Assert: no NaN in critical columns, shares > 0, prices > 0, cash > 0, no duplicate
tickers in Positions. If fails → write `status=failed` + error to Pipeline Status, send
LINE Notify, stop. Staging is never promoted on validation failure.

**Cell 13 — Write to Staging:**
Write all computed data to `_staging` sheets. Trade Ticket staged with columns 8-10
blank (ready for user fill input). Add `time.sleep(1)` between each staging sheet write
to stay under the 60 write-requests/minute quota.

**Cell 14 — Promote Staging to Live:**
Copy staging values to live sheets, clear staging sheets.

**Cell 15 — Append Trade Log:**
For each new trade: scan column I (0-indexed: col 8) for existing `id`, skip if found.
Append net-new trades only. `CANCEL` rows follow the same append path.

**Cell 16 — Update & Append Forecast History:**
Resolve prior-day `actual_return` using `batch_update` (see Forecast History schema note
for exact format and row-index tracking). Skip any ticker in `failed_tickers` — leave
`actual_return` blank, try again next run. Then append today's predictions with
`entry_close` populated.

**Cell 17 — Set Pipeline Status: Completed:**
Write `status=completed`, `duration_seconds`, `sheets_updated` list.

**Cell 18 — LINE Notify:**
On failure: error message + cell number. On success: optional summary (capital, P&L MTD,
trades today, fills confirmed vs. assumed count). If `LINE_TOKEN` is None, skip silently.

**Cell 19 — Summary:**
Print: capital, P&L MTD, allocation band, trades today, fills confirmed/assumed, friction YTD.

### LINE Notify Integration

- Token from Colab Secrets (`LINE_NOTIFY_TOKEN`). Absent → pipeline continues, warning printed.
- On failure: error + which cell number failed.
- On success: optional summary.

---

## Google Apps Script Web App

### Deployment — Container-Bound Script

**Create the Apps Script project from within the spreadsheet:**
Open "Kronos-TH Portfolio" → Extensions > Apps Script. This creates a **container-bound**
script that can access the spreadsheet via `SpreadsheetApp.getActiveSpreadsheet()` — no
spreadsheet ID needed in `Code.gs`.

Do **not** create a standalone Apps Script project (script.google.com) — that requires
`SpreadsheetApp.openById(id)` and manual ID management.

- **Execute as:** Me
- **Access:** Only myself (requires Google login to view)
- **Runtime:** V8 (Project Settings > Runtime version — default after 2020)

**Rationale for "Only myself":** positions, cash, trade history, and risk metrics are
private financial data. "Anyone with link" exposes all of it to anyone who finds the URL.
To share with one trusted person, add them explicitly in Apps Script sharing settings.

> ⚠️ **Deployment version:** Every time `Code.gs` is edited, create a new deployment:
> Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy.
> The URL stays the same; the version increments. The old URL serves the previous version
> until you do this.

### Apps Script Calling Convention

Apps Script web apps do **not** expose REST endpoints. All `Code.gs` functions are called
from the frontend via `google.script.run`:
```javascript
google.script.run
  .withSuccessHandler(function(data) { /* render */ })
  .withFailureHandler(function(err)  { /* show error */ })
  .getAllData();
```
There is no `fetch()` or `XMLHttpRequest` to an API URL. Functions in `Code.gs` run
server-side and return plain JavaScript objects/arrays to the callback. All calls are
**asynchronous** — show a loading state until the callback fires.

### Google Charts Load Order

The equity curve chart uses Google Charts, which requires an external library. The
`getAllData()` call must happen **inside the Charts ready callback**, not on `window.onload`,
otherwise `google.visualization` is undefined and the chart crashes:

```html
<!-- Index.html — correct load order -->
<script src="https://www.gstatic.com/charts/loader.js"></script>
<script>
  google.charts.load('current', {packages: ['corechart']});
  google.charts.setOnLoadCallback(function() {
    showLoadingSpinner();
    google.script.run
      .withSuccessHandler(function(d) {
        hideSpinner();
        // d.pipeline is a single object (Pipeline Status row), not an array.
        // getAllData() extracts pipelineRows[0] so renderPipelineStatus receives
        // {status, last_run_timestamp, error_message, ...} directly.
        renderPipelineStatus(d.pipeline);          // ← must be first
        renderDashboard(d.portfolio, d.equityCurve, d.riskMetrics);
        renderPositions(d.positions);
        renderTradeLog(d.tradeLog);
        renderForecasts(d.forecasts, d.forecastHistory);
        renderTicket(d.ticket);
      })
      .withFailureHandler(showError)
      .getAllData();
  });
</script>
```

`renderPipelineStatus()` must be the first render call — it controls the green/yellow/red
status banner that frames all other content. `d.pipeline` is a plain object (single row
extracted in `getAllData()`), not an array — access fields directly as `d.pipeline.status`,
`d.pipeline.last_run_timestamp`, etc.

### `submitFills()` — Fill Confirmation from Web App

Allows users to enter actual broker fill prices directly from the dashboard without
opening the spreadsheet. Called by the fill modal in `renderTicket`.

```javascript
function submitFills(fills) {
  // fills = [{ticker, filled_price, filled_shares, fill_timestamp}, ...]
  // Writes to Trade Ticket sheet cols 8-10, then clears cache
}
```

Returns `{ok: true, updated: N}`. On success, the frontend calls `refreshAllData()` so
fill status updates immediately without a manual page reload.

### Single `getAllData()` Function

One server round-trip on page load. Multiple simultaneous `google.script.run` calls would
deliver callbacks in unpredictable order, causing race conditions in the frontend.

```javascript
// ── Code.gs ────────────────────────────────────────────────────────────────
function doGet() {
  return HtmlService
    .createHtmlOutputFromFile('Index')
    .setTitle('Kronos-TH Portfolio')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getAllData() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet(); // container-bound: no ID needed
  var cache = CacheService.getScriptCache();
  var hit   = cache.get('all_data');
  if (hit) return JSON.parse(hit);

  var pipelineRows = _readSheet(ss, 'Pipeline Status');
  var data = {
    pipeline:        pipelineRows.length ? pipelineRows[0] : null, // single-row → object, not array
    portfolio:       _readSheet(ss, 'Portfolio'),
    equityCurve:     _readSheetLimited(ss, 'Equity Curve',      90),
    positions:       _readSheet(ss, 'Positions'),
    tradeLog:        _readSheetLimited(ss, 'Trade Log',         200),
    forecasts:       _readSheet(ss, 'Forecasts'),
    forecastHistory: _readSheetLimited(ss, 'Forecast History',  180),
    ticket:          _readSheet(ss, 'Trade Ticket'),
    riskMetrics:     _readSheetLimited(ss, 'Risk Metrics',      365),
  };

  var json = JSON.stringify(data);
  if (json.length < 100000)          // skip cache if > 100KB — do not store silently
    cache.put('all_data', json, 300); // 5-minute TTL
  return data;
}

// ── Helpers ────────────────────────────────────────────────────────────────
function _rowToObj(headers, row) {
  var obj = {};
  headers.forEach(function(h, i) {
    var v = row[i];
    if (v === '' || v === null || v === undefined) {
      obj[h] = null;
    } else if (v instanceof Date) {
      // getValues() returns Date objects for date-formatted cells — format as string,
      // NOT Number(v) which would give a Unix timestamp in milliseconds
      obj[h] = Utilities.formatDate(v, 'Asia/Bangkok', 'yyyy-MM-dd');
    } else if (!isNaN(Number(v))) {
      obj[h] = Number(v);
    } else {
      obj[h] = v;
    }
  });
  return obj;
}

function _readSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  var data  = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];
  var headers = data[0];
  return data.slice(1).map(function(row) { return _rowToObj(headers, row); });
}

function _readSheetLimited(ss, name, maxRows) {
  var sheet   = ss.getSheetByName(name);
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  // Read only the tail — do NOT getValues() the full sheet then slice in memory
  var startRow = Math.max(2, lastRow - maxRows + 1);
  var numRows  = lastRow - startRow + 1;
  var numCols  = sheet.getLastColumn();
  var headers  = sheet.getRange(1, 1, 1, numCols).getValues()[0];
  var values   = sheet.getRange(startRow, 1, numRows, numCols).getValues();
  return values.map(function(row) { return _rowToObj(headers, row); });
}

function _csvField(v) {
  var s = (v == null) ? '' : String(v);
  // RFC 4180: quote fields containing commas, double-quotes, or newlines
  return (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0)
    ? '"' + s.replace(/"/g, '""') + '"'
    : s;
}
```

`_rowToObj` handles three cases in order: empty → null; Date object → formatted string
(prevents corrupt Unix-timestamp values); numeric string → Number. Date cells from
`getValues()` are `Date` objects in Apps Script — always check `instanceof Date` before
`isNaN(Number(v))` since `Number(new Date())` is a valid large integer.

### Read Limits and CacheService 100KB Guard

`CacheService.put()` **silently fails** for values over 100KB — no error, cache bypassed
every time. Mitigation:
1. `_readSheetLimited()` reads from `getRange(startRow, ...)` — never reads the full sheet
   then slices. This keeps payload small and the read fast.
2. `json.length < 100000` guard before `cache.put()` — explicit skip rather than silent fail.
3. "Refresh" button bypasses cache (`cache.remove('all_data')` + re-call `getAllData()`).

### `getExportCsv()` — Staleness Check

`getExportCsv()` is called on demand (Export CSV button click). It must check Pipeline
Status before returning data, and prepend a warning if stale:

```javascript
function getExportCsv() {
  var ss     = SpreadsheetApp.getActiveSpreadsheet();
  var status = _readSheet(ss, 'Pipeline Status');
  var lastRun = status.length ? new Date(status[0].last_run_timestamp) : null;
  var hoursAgo = lastRun ? (Date.now() - lastRun.getTime()) / 3600000 : 999;

  var warning = hoursAgo > 24
    ? '# WARNING: Pipeline last ran ' + Math.round(hoursAgo) + ' hours ago. Data may be stale.\n'
    : '';

  var ticket = _readSheet(ss, 'Trade Ticket');
  var rows   = ticket.map(function(r) {
    // Use _csvField to quote fields — rationale commonly contains commas
    return [r.ticker, r.action, r.shares, r.est_cost_thb, _csvField(r.rationale)].join(',');
  });
  var header = '# Execute at next market open (Bangkok time). Prices are previous close estimates.\n'
             + '# Enter actual fills in the Trade Ticket sheet after execution.\n';
  return warning + header + 'ticker,action,shares,est_cost_thb,rationale\n' + rows.join('\n');
}
```

Frontend download trigger (unchanged):
```javascript
google.script.run.withSuccessHandler(function(csv) {
  var blob = new Blob([csv], {type: 'text/csv'});
  var url  = URL.createObjectURL(blob);
  var a    = document.createElement('a');
  a.href = url; a.download = 'kronos_ticket.csv'; a.click();
  URL.revokeObjectURL(url);
}).getExportCsv();
```

### Files (in `google_suite/apps_script/`)

- `Code.gs` — `doGet()`, `getAllData()`, `refreshAllData()`, `submitFills()`,
  `getExportCsv()`, `_readSheet()`, `_readSheetLimited()`, `_rowToObj()`, `_csvField()`
- `Index.html` — 5-tab SPA with Google Charts load order, fill modal, sortable tables

### Frontend Tabs

1. **Dashboard** — Google Charts load gate then `getAllData()`; pipeline status banner
   rendered first (green/yellow/red + "Last updated: X"); regime badge (BULL/NEUTRAL/BEAR/EXIT)
   with plain-English band definition; hero cards (capital, P&L MTD, Sharpe, MaxDD, Friction YTD);
   equity curve chart; fills status indicator ("X confirmed / Y assumed today")
2. **Positions** — sortable table, green/gray/red P&L, `% to stop-loss` (red < 3%);
   red frozen banner if `is_frozen = true`; "as of {forecast_date}" freshness label;
   **Exp Ret** and **Signal** columns showing today's forecast for each open position
   (joined client-side from `d.forecasts` by ticker)
3. **Trade Log** — read-only audit trail, sortable. Cancelled rows strikethrough.
   CANCEL entries show `↩ cancels {ref_id}`. Note: "CANCEL only updates this display —
   also correct the Portfolio sheet manually if needed."
4. **Forecasts** — sorted by rank_score; confidence badges (green/yellow/red); **Δ Prev column**
   showing change in `exp_ret` vs previous pipeline run (▲ green / ▼ red; only shown when
   history exists); **📅 data date badge**; Forecast History sub-tab with:
   - **Historical date selector** dropdown (newest first, "📅 All dates" default) — filters
     the accuracy table to any past run date; rows sorted by predicted_return desc for that
     date (equivalent to a historical ranking view); per-date accuracy summary updates live.
   - `_forecastHistory` kept in module scope; `filterHistoryByDate(date)` re-renders table
     and re-attaches column sort. `_buildHistoryTable(rows)` is a shared helper.
   All column headers have tooltips using Glossary definitions.
5. **Trade Ticket** — recommendations (board-lot rounded) + fill status per ticker
   (confirmed/assumed) + "Export CSV" button + **"Enter Fills" button** (opens fill modal)

### Regime Indicator

- **BULL** (green): Sharpe > 1.0 → 15% per position (≤75% total deployed)
- **NEUTRAL** (yellow): Sharpe 0.5–1.0 → 10% per position (≤50% total)
- **BEAR** (red): Sharpe 0–0.5 → 5% per position (≤25% total)
- **EXIT** (dark red): Sharpe ≤ 0 or < 20 closed trades → 0%, cash only

`allocation_pct` is read from the latest Risk Metrics row. Display as:
`"Sizing: {allocation_pct*100}% per position"` alongside the band badge.

Context note below badge:
> "Backtest 2022–2024: CAGR +31.4%, Sharpe 1.40, Alpha vs. EW +29.9%/yr.
> The model is trend-following; alpha was lower in the 2023 bull market."

### Backtest Comparison

Risk Metrics tab — static "Expected" row. Source: `data/backtest_results/thai_equity_2022-2024_v2/metrics.json`
(period: 2022-01-01 → 2024-12-31, config: `thai_equity_2022-2024_v2/config.json`).

| Metric | Expected (2022–2024 backtest) | Source |
|--------|-------------------------------|--------|
| CAGR | +31.44% | `metrics.json → cagr` |
| Sharpe | 1.40 | `metrics.json → sharpe` |
| Max DD | −17.97% | `metrics.json → max_drawdown` |
| Alpha vs EW | +29.9%/yr | strategy CAGR − EW CAGR (1.50%) from `benchmark_equal_weight.parquet` |
| p-value | 0.034 (significant) | `metrics.json → p_value` (t-test; significant at 5%) |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Sheets empty (first run) | Cell 4 initialises Portfolio. Web app shows "No data yet." |
| Pipeline status = "running" | Spinner: "Pipeline running… please wait" |
| Pipeline status = "failed" | Red banner with error message + timestamp |
| Pipeline status stale (>24h) | Yellow banner: "Pipeline hasn't run in X days." |
| Export CSV with stale pipeline | CSV prepended with `# WARNING: … hours ago` |
| Pipeline fails mid-way | Staging not promoted → live sheets retain last good data |
| Data validation fails | Pipeline stops before promotion. Error → Pipeline Status + LINE Notify |
| Portfolio frozen (−10% drawdown) | Red banner on Dashboard + Positions. No buys. Liquidate + re-run Cell 4. |
| CacheService value > 100KB | `getAllData()` skips caching. Every load hits Sheets directly. |
| Web app not on latest version | Deploy → Manage deployments → Edit → New version → Deploy |
| LINE Notify token missing | Pipeline continues. Warning printed in Colab output. |
| Staging write rate-limited | `time.sleep(1)` between staging writes in Cell 13 prevents HTTP 429. |
| Fills not entered before next run | Cell 6 falls back to forecast close. `fill_source=assumed` logged. Fills unrecoverable. |
| Colab re-run same day | Equity Curve + Risk Metrics upsert. Trade Log dedup skips existing IDs. |
| Erroneous Trade Log entry | Append CANCEL row + manually correct Portfolio sheet cash/positions. |
| kth not on PyPI | Cell 1 installs from Drive-mounted repo. Wrong path fails before data is touched. |
| `SPREADSHEET_ID` missing from Secrets | Cell 2 raises `ValueError` with setup instructions. |
| gspread values not cast | `_rowToObj()` in Code.gs and explicit casts in Colab cells handle this. |
| Colab idle timeout (~90 min) | Keep browser tab active. Use Colab Pro for long first-run downloads. |
| OHLCV unavailable for a ticker | Stored in `failed_tickers`; skipped in forecasts, portfolio update, and Forecast History resolution. `actual_return` stays blank for that ticker until next successful download. |
| Google Charts not loaded | `getAllData()` called inside `google.charts.setOnLoadCallback()` — Charts always ready before render. |
| `d.pipeline` is null (empty sheet) | `renderPipelineStatus(null)` — frontend must guard: `if (!d.pipeline) { showNoPipelineYet(); return; }` |
| Date cells rendered as timestamps | `_rowToObj` checks `instanceof Date` before `Number()` cast — always produces `'yyyy-MM-dd'` string. |

---

## File Structure

```
google_suite/
├── README.md                    # Setup guide (step-by-step)
├── migrate_to_sheets.py         # One-time migration: JSON/CSV → Sheets
├── kronos_daily_pipeline.ipynb  # Colab notebook (19 cells)
└── apps_script/
    ├── Code.gs                  # doGet, getAllData, getExportCsv, helpers (V8, container-bound)
    └── Index.html               # 5-tab SPA, Google Charts load gate
```

---

## Setup Steps (for README)

1. Create a new Google Spreadsheet named "Kronos-TH Portfolio"
2. Create **14 tabs** in this order:
   - **Live (9):** Portfolio, Equity Curve, Positions, Trade Log, Forecasts, Forecast History,
     Trade Ticket, Risk Metrics, Pipeline Status
   - **Staging (5):** Portfolio_staging, Positions_staging, Forecasts_staging,
     Trade Ticket_staging, Risk Metrics_staging
3. Add header rows to each sheet (column names exactly as in Sheets Layout — column order
   matters for row-index references in Colab cells)
4. **From within the spreadsheet**, open Apps Script: Extensions > Apps Script.
   Paste `Code.gs` content. Add `Index.html` (File > New > HTML file, paste content).
   Confirm V8 runtime (Project Settings > Runtime version).
   > Container-bound script: `SpreadsheetApp.getActiveSpreadsheet()` works automatically.
   > Do not create a standalone Apps Script project.
5. Deploy as web app: **Execute as:** Me / **Access:** Only myself. Note the URL.
   > ⚠️ Every future `Code.gs` edit requires a new deployment version to take effect.
6. In Colab, open Secrets (key icon in left sidebar) and add:
   - `KRONOS_SPREADSHEET_ID` = the spreadsheet ID from the URL (`/d/<ID>/edit`)
   - `LINE_NOTIFY_TOKEN` = your LINE Notify token (optional)
7. Upload `kronos_daily_pipeline.ipynb` to Colab (or open from Drive)
8. In Cell 1, confirm `KTH_REPO` path points to your Drive-mounted repo
9. In Cell 2, set `INITIAL_CAPITAL` to your starting capital in THB
10. **(Optional)** Run `migrate_to_sheets.py` to import existing paper trading history
11. Run all cells → Cell 4 initialises Portfolio → visit web app URL

---

## Comparison: Old vs New

| Aspect | Flask Dashboard | Google Suite |
|--------|---------------|--------------|
| Hosting | Local machine | Google (free) |
| Access | `localhost:5555` | Private URL (Google login) |
| Compute | Local Python | Colab (free GPU/TPU) |
| Data storage | JSON/CSV/Parquet | Google Sheets |
| Daily run | Cron | Manual (Colab Run All) |
| Trade execution | POST /api/trades | CSV export → broker → fill columns |
| Fill confirmation | POST /api/trades with actual price | User edits Trade Ticket fill columns |
| Trade log | Editable (delete/patch) | Append-only + CANCEL + manual Portfolio fix |
| Pipeline status | Health endpoint | Pipeline Status sheet + banner |
| Data integrity | None | Staging → validate → promote |
| Forecast tracking | None | Forecast History (batch_update resolution) |
| Failure alerting | LINE Notify | LINE Notify + web app banner |
| Regime awareness | Allocation band only | Badge + definition + context note |
| Stop-loss visibility | In code only | % to stop-loss column + frozen banner |
| Friction tracking | In backtest only | Cumulative friction YTD in Risk Metrics |
| Backtest comparison | None | Static "Expected" row in Risk Metrics |
| kth install | `pip install -e .` | Drive-mounted repo, Cell 1 |
| Auth pattern | N/A | Colab auth → gspread.Client(auth=creds) |
| Code.gs spreadsheet access | N/A | getActiveSpreadsheet() — container-bound |
| Frontend calls | fetch() / REST | google.script.run inside Charts callback |
| CSV download | File path | Blob + URL.createObjectURL() |
| CSV staleness guard | None | Pipeline age check + WARNING comment in CSV |
| First-run init | reset_portfolio() CLI | Cell 4 auto-initialises if Portfolio empty |
| Sheets cache safety | N/A | 100KB guard + _readSheetLimited() |
| Type safety | N/A | _rowToObj() casts all values; explicit Colab casts |
| Write quota safety | N/A | batch_update() for Forecast History; sleep(1) for staging |
| CANCEL semantics | Delete/patch | Audit trail only — Portfolio sheet corrected manually |
| Missing OHLCV handling | N/A | failed_tickers set; skipped in all downstream cells |
| Daily routine | Not documented | Step-by-step box + Bangkok timezone |
| Glossary | None | Fill, 3-filter, bands, metrics, board lot, frozen, CANCEL |
| Cost | Electricity only | Free |
| Uptime required | Machine must be on | No |
| Mobile access | No | Yes |
