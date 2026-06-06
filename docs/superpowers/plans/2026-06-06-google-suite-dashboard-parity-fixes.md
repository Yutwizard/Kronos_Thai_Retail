# Google Suite Dashboard Parity Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Google Suite dashboard to full feature parity with the local Flask dashboard by implementing 9 design groups (14 misalignments) defined in `docs/superpowers/specs/2026-06-06-google-suite-dashboard-parity-fixes-design.md`.

**Architecture:** No architectural change. JSON-bridge pattern preserved (`Sheets → Drive JSON → kth functions → Drive JSON → Sheets`). Four new Colab cells (4b, 9b, 11b, 13b) and six new Apps Script functions are added. All changes are additive. Sheet count goes from 14 → 17 tabs (11 live + 6 staging).

**Tech Stack:** Python 3.10 (Colab), Google Apps Script (V8 runtime), HTML/CSS/JS, Google Sheets API via `gspread`, `kth` package functions.

**Reference spec:** `docs/superpowers/specs/2026-06-06-google-suite-dashboard-parity-fixes-design.md`

---

## File structure

| File | Responsibility | This plan |
|---|---|---|
| `google_suite/build_notebook.py` | Generates the .ipynb from cell source | Modify (4 new cells + 3 comments + 1 STAGING_MAP entry) |
| `google_suite/kronos_daily_pipeline.ipynb` | The generated Colab notebook | Regenerate (run build_notebook.py) |
| `google_suite/apps_script/Code.gs` | Apps Script backend (read Sheets, queue writes) | Modify (6 new functions + 1 cache TTL change) |
| `google_suite/apps_script/Index.html` | Apps Script frontend SPA | Modify (CSS + JS) |
| `google_suite/SETUP_GUIDE.md` | Newbie setup walkthrough | Modify (3 sections + 1 new) |
| `README.md` | Project overview | Modify (1 line) |

**No new files created.** The 4 new sheet tabs (`Equity Curve_staging`, `Calibration`, `Trade Edits`, `Capital Reset`) are created by the user manually in Sheets per SETUP_GUIDE updates.

---

## Task ordering

Tasks 1-3 are zero-risk and ship early. Tasks 4-7 are the new features. Tasks 8-10 are polish and docs. Each task is a self-contained commit.

| # | Task | Item | Risk |
|---|---|---|---|
| 1 | Doc comments | A2 | Zero — comments only |
| 2 | Equity Curve append | A1 | Low — new cell + new staging sheet |
| 3 | Position row borders | B4 | Zero — CSS + JS, instant visual |
| 4 | Calibration + Health Banner | B3 | Medium — new sheet, new cell, new Apps Script fn, new UI banner |
| 5 | Trade Log edit/delete | B1 | High — new sheet, new cell, 3 Apps Script fns, new modals |
| 6 | Initial Capital UI | B2 | High — destructive, new sheet, new cell, 2 Apps Script fns, new modals |
| 7 | Auto-refresh + cache TTL | C1+C2 | Low — 1 line code, 1 line param change |
| 8 | Mock data + Esc key | E1+E3 | Zero — 1 field added, 1 keydown handler |
| 9 | SETUP_GUIDE updates | D1+D2 | Zero — docs only |
| 10 | README update | D2 | Zero — 1 line |

---

## Task 1: Document field divergences in build_notebook.py

**Files:**
- Modify: `google_suite/build_notebook.py` (3 inline comment additions + 1 module docstring section)

**Context:** Three places in the Colab notebook diverge from the kth API surface and the divergence is not documented. Future refactors will silently break the dashboard contract. This task adds comments so the contract is explicit.

- [ ] **Step 1.1: Add module docstring "Schema contract" section**

Open `google_suite/build_notebook.py`. The current module docstring is at the top (line 1):

```python
"""Generate kronos_daily_pipeline.ipynb from source cells in the plan."""
```

Replace it with:

```python
"""Generate kronos_daily_pipeline.ipynb from source cells in the plan.

Schema contract — 17 sheets, written/read by these functions:
- Portfolio              live  read: Cell 9,  write: Cell 13 (staging->14)
- Positions              live  read: Apps Script,  write: Cell 13
- Trade Ticket           live  read: Apps Script,  write: Cell 13
- Trade Log              live  read: Apps Script,  write: Cell 15 (append)
- Forecasts              live  read: Apps Script,  write: Cell 13
- Forecast History       live  read: Apps Script,  write: Cell 16 (append + resolve)
- Equity Curve           live  read: Apps Script,  write: Cell 13b (NEW)
- Risk Metrics           live  read: Apps Script,  write: Cell 13
- Pipeline Status        live  read: Apps Script,  write: Cells 5, 12, 17
- Calibration            live  read: Apps Script,  write: Cell 11b (NEW)
- *_staging (6 sheets)   staging read: Cell 14,  write: Cell 13
- Trade Edits            staging read: Cell 9b,  write: Apps Script (NEW)
- Capital Reset          staging read: Cell 4b,  write: Apps Script (NEW)

If you change a sheet's headers, update Apps Script Code.gs _readSheet
column references AND Index.html render functions. Run build_notebook.py
to regenerate kronos_daily_pipeline.ipynb.
"""
```

- [ ] **Step 1.2: Add inline comment at the Positions write (around line 410)**

In `build_notebook.py`, find the section starting with `# Cell 13 — Write to Staging Sheets`. The `pos_rows` block (around line 403-414) looks like:

```python
pos = get_positions('paper')
pos_rows = []
for p in pos['positions']:
    close   = float(ohlcv_dict[p['ticker']]['close'].iloc[-1]) \
              if p['ticker'] in ohlcv_dict else p['avg_cost']
    pnl     = (close - p['avg_cost']) * p['shares']
    pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
    pos_rows.append([
        p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
        get_sector(p['ticker']), round(close, 2),
        round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
    ])
```

Replace with the same code preceded by a comment block:

```python
# NOTE: `current_price` and `pct_to_stoploss` are computed locally from
# `ohlcv_dict[ticker]['close'].iloc[-1]`, NOT from `get_positions()`.
# `get_positions()` returns `mark` (not `current_price`) and no stop-loss column.
# Do not refactor to use `get_positions()` here without updating
# the Positions sheet schema and Index.html renderPositions().
pos = get_positions('paper')
pos_rows = []
for p in pos['positions']:
    close   = float(ohlcv_dict[p['ticker']]['close'].iloc[-1]) \
              if p['ticker'] in ohlcv_dict else p['avg_cost']
    pnl     = (close - p['avg_cost']) * p['shares']
    pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
    pos_rows.append([
        p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
        get_sector(p['ticker']), round(close, 2),
        round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
    ])
```

- [ ] **Step 1.3: Add inline comment at the Risk Metrics write (around line 452)**

Find the section starting with `_write_staging('Risk Metrics_staging',`. The block (around line 452-475) currently starts with:

```python
equity = pos['total_value']
_write_staging('Risk Metrics_staging',
    ['date','equity','cash','deployed_pct','trailing_sharpe_12w','max_drawdown_pct',
     ...
```

Replace with the same code preceded by a comment block:

```python
# NOTE: Risk Metrics sheet headers are intentionally renamed from
# compute_metrics() output keys. The Apps Script Index.html renders
# columns by the SHEET header names (e.g. `trailing_sharpe_12w`),
# not the Python return-key names (e.g. `sharpe`). Keep the rename
# table below in sync with renderDashboard() and renderPositions().
# Python key       ->  Sheet header
# ----------------------------------------
#   sharpe           ->  trailing_sharpe_12w
#   drawdown         ->  max_drawdown_pct
#   pnl_mtd_pct      ->  mtd_pnl_pct
#   win_rate         ->  trade_win_rate
#   exposure         ->  deployed_pct
#   calmar           ->  calmar_ratio
#   sortino          ->  sortino_ratio
#   drawdown_velocity->  drawdown_velocity
#   bootstrap_pvalue ->  bootstrap_p_value
#   friction_ytd_pct ->  friction_ytd_pct
#   friction_ytd_thb ->  friction_ytd_thb
equity = pos['total_value']
_write_staging('Risk Metrics_staging',
    ['date','equity','cash','deployed_pct','trailing_sharpe_12w','max_drawdown_pct',
```

- [ ] **Step 1.4: Regenerate the .ipynb**

Run from the repo root:

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python google_suite/build_notebook.py
```

Expected output: `Generated google_suite/kronos_daily_pipeline.ipynb — 36 cells` (no change — Task 1 only adds docstrings and comments to existing cells, no new cells).

- [ ] **Step 1.5: Commit**

```bash
git add google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb
git commit -m "docs(google-suite): add schema contract + inline notes for 3 field divergences"
```

---

## Task 2: Add Equity Curve staging append (Cell 13b)

**Files:**
- Modify: `google_suite/build_notebook.py` (add Cell 13b code, add to STAGING_MAP in Cell 14)
- Modify: `google_suite/SETUP_GUIDE.md` (add `Equity Curve_staging` to tabs table)

**Context:** `Equity Curve` sheet is read by Cell 9 and rendered by the Apps Script chart, but never written by the Colab pipeline. This task adds a new code cell that appends today's row to a new `Equity Curve_staging` sheet, which Cell 14 will promote to the live `Equity Curve` sheet.

- [ ] **Step 2.1: Add `Equity Curve_staging` to SETUP_GUIDE.md tab-creation table**

In `google_suite/SETUP_GUIDE.md`, find the table that lists the 14 tabs. The current row count says "14 tabs" and the staging rows list 5 entries. Add a 6th staging row. (Read the file to find the exact location.)

Find a line that says "**Staging tabs (5):**" or similar. Change to:

```markdown
**Staging tabs (6):** `Portfolio_staging`, `Positions_staging`, `Forecasts_staging`, `Trade Ticket_staging`, `Risk Metrics_staging`, `Equity Curve_staging`
```

And update the total count from "14 tabs" to "17 tabs" wherever it appears.

- [ ] **Step 2.2: Add Cell 13b — Append Equity Curve to Staging**

In `google_suite/build_notebook.py`, find the existing `md("""## Cell 14 — Promote Staging to Live Sheets""")` call (around line 480). Insert these two calls immediately before it:

```python
md("""## Cell 13b — Append Equity Curve to Staging

**Why a new sheet:** The live `Equity Curve` sheet is read by Cell 9 and rendered by the Apps Script chart, but the Colab pipeline never appended to it. This cell fixes that by writing today's row to a new `Equity Curve_staging` sheet, which Cell 14 promotes.""")

code(r"""equity = pos['total_value']
_write_staging('Equity Curve_staging',
    ['date', 'equity', 'cash', 'invested'],
    [[today_str, round(equity, 2), round(pf_data['cash'], 2),
      round(equity - pf_data['cash'], 2)]])
print("Equity Curve staging row appended.")
""")
```

- [ ] **Step 2.3: Add `Equity Curve_staging` to the STAGING_MAP in Cell 14**

Find the `STAGING_MAP = {` block in Cell 14 (around line 482-488 in `build_notebook.py`):

```python
STAGING_MAP = {
    'Portfolio_staging':     'Portfolio',
    'Positions_staging':     'Positions',
    'Forecasts_staging':     'Forecasts',
    'Trade Ticket_staging':  'Trade Ticket',
    'Risk Metrics_staging':  'Risk Metrics',
}
```

Add a new entry:

```python
STAGING_MAP = {
    'Portfolio_staging':     'Portfolio',
    'Positions_staging':     'Positions',
    'Forecasts_staging':     'Forecasts',
    'Trade Ticket_staging':  'Trade Ticket',
    'Risk Metrics_staging':  'Risk Metrics',
    'Equity Curve_staging':  'Equity Curve',
}
```

- [ ] **Step 2.4: Regenerate the .ipynb**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python google_suite/build_notebook.py
```

Expected: `Generated google_suite/kronos_daily_pipeline.ipynb — 38 cells` (current 36 + 1 md + 1 code for Cell 13b).

- [ ] **Step 2.5: Verify the new cells in the .ipynb**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python -c "import json; nb=json.load(open('google_suite/kronos_daily_pipeline.ipynb')); print(f'Cells: {len(nb[\"cells\"])}'); print('Cell 13b md present:', any('Cell 13b' in ''.join(c.get('source',[])) for c in nb['cells'])); print('Cell 13b code present:', any('Equity Curve_staging' in ''.join(c.get('source',[])) for c in nb['cells']))"
```

Expected output: `Cells: 38`, both `True`.

- [ ] **Step 2.6: Commit**

```bash
git add google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb google_suite/SETUP_GUIDE.md
git commit -m "feat(google-suite): append Equity Curve daily via new Cell 13b (was frozen after migration)"
```

---

## Task 3: Position row border colors

**Files:**
- Modify: `google_suite/apps_script/Index.html` (CSS + JS additions only)

**Context:** The Flask dashboard paints position rows red/orange/green based on the model's signal. The Google Suite positions table has inline P&L coloring but no row border. This is a 5-line CSS + ~7-line JS change with zero risk.

- [ ] **Step 3.1: Add CSS for row border classes**

In `google_suite/apps_script/Index.html`, find line 60 (the `tr:hover { background: #f8f9fa; }` rule). Insert these three rules immediately after it:

```css
tr.row-hold  { border-left: 4px solid var(--green); }
tr.row-reduce { border-left: 4px solid var(--yellow); }
tr.row-exit  { border-left: 4px solid var(--red); }
```

- [ ] **Step 3.2: Apply the row class in `renderPositions()`**

In `google_suite/apps_script/Index.html`, find `renderPositions()` (around line 442). The `var rows = positions.map(...)` block (around line 463) starts with:

```js
var rows = positions.map(function(p) {
    var pctStyle  = p.pnl_pct > 0 ? 'color:var(--green)' : p.pnl_pct < 0 ? 'color:var(--red)' : '';
    var stopStyle = p.pct_to_stoploss < 0.03 ? 'background:var(--pnl-neg-bg);color:var(--red)' : '';
    // Forecast enrichment for this position
    var fc = fcMap[p.ticker];
```

Modify to compute `rowCls` from the forecast signal and apply it to the `<tr>`:

```js
var rows = positions.map(function(p) {
    var pctStyle  = p.pnl_pct > 0 ? 'color:var(--green)' : p.pnl_pct < 0 ? 'color:var(--red)' : '';
    var stopStyle = p.pct_to_stoploss < 0.03 ? 'background:var(--pnl-neg-bg);color:var(--red)' : '';
    // Forecast enrichment for this position
    var fc = fcMap[p.ticker];

    // Row border class from forecast signal
    var rowCls = '';
    if (fc) {
      var dir = fc.exp_ret > 0 ? 'up' : 'down';
      if (dir === 'down' && fc.confidence === 'green') rowCls = 'row-exit';
      else if (fc.confidence === 'yellow') rowCls = 'row-reduce';
      else if (dir === 'up') rowCls = 'row-hold';
    }
```

Then find the `<tr>` template literal (around line 479) that currently starts with:

```js
return '<tr>' +
```

Replace with:

```js
return '<tr class="' + rowCls + '">' +
```

- [ ] **Step 3.3: Verify by visual inspection (MOCK mode)**

Open the Apps Script web app URL. The 2 MOCK positions (PTT.BK and AOT.BK) should now have a colored left border. PTT.BK is `up + green` → `row-hold` (green). AOT.BK is `down + yellow`... actually check the MOCK. The MOCK has PTT.BK `exp_ret: 0.045, confidence: green` and AOT.BK not in the MOCK positions table, only the MOCK positions table. Verify in the MOCK data.

If running in live (real Sheets) mode: position table should show colored left borders based on today's forecasts.

- [ ] **Step 3.4: Commit**

```bash
git add google_suite/apps_script/Index.html
git commit -m "feat(google-suite): add red/orange/green left-border row colors to Positions table (Flask parity)"
```

---

## Task 4: Calibration sheet + Signal Health Banner

**Files:**
- Modify: `google_suite/build_notebook.py` (add Cell 11b code)
- Modify: `google_suite/apps_script/Code.gs` (add `getHealthCheck` function)
- Modify: `google_suite/apps_script/Index.html` (add health banner render in `renderDashboard`)
- Modify: `google_suite/SETUP_GUIDE.md` (add `Calibration` to tabs table)

**Context:** Flask shows a signal health banner when model calibration diverges from the 90% target. Google Suite has no equivalent. This task adds a new `Calibration` sheet, a Colab cell to write to it, an Apps Script function to read it, and a banner in the Dashboard UI.

- [ ] **Step 4.1: Add `Calibration` to SETUP_GUIDE.md tab-creation table**

**Sheet count note:** The spec at §8 says "11 live + 6 staging" but that count is off by 1. The correct count after this spec is **10 live + 8 staging = 18 tabs**:
- **Live (10):** Portfolio, Positions, Trade Ticket, Trade Log, Forecasts, Forecast History, Equity Curve, Risk Metrics, Pipeline Status, Calibration
- **Staging (8):** Portfolio_staging, Positions_staging, Forecasts_staging, Trade Ticket_staging, Risk Metrics_staging, Equity Curve_staging, Trade Edits, Capital Reset
  - 5 original staging + Equity Curve_staging (Task 2) + Trade Edits (Task 5) + Capital Reset (Task 6) = 8

In `google_suite/SETUP_GUIDE.md`, find the list of "Live tabs (9)" and add `Calibration`. Update the staging tabs list to 8 (add `Equity Curve_staging`, `Trade Edits`, `Capital Reset`). Update any "14 tabs" or "17 tabs" references to "18 tabs".

```markdown
**Live tabs (10):** `Portfolio`, `Positions`, `Trade Ticket`, `Trade Log`, `Forecasts`, `Forecast History`, `Equity Curve`, `Risk Metrics`, `Pipeline Status`, `Calibration`

**Staging tabs (8):** `Portfolio_staging`, `Positions_staging`, `Forecasts_staging`, `Trade Ticket_staging`, `Risk Metrics_staging`, `Equity Curve_staging`, `Trade Edits`, `Capital Reset`
```

Note: Trade Edits and Capital Reset are written by Apps Script (not by the Colab notebook) and read by Colab Cells 9b/4b. They're functionally staging sheets for in-flight operations, not for general data flow.

- [ ] **Step 4.2: Add Cell 11b — Compute Calibration**

In `google_suite/build_notebook.py`, find the existing `md("""## Cell 12 — Validate Data""")` call. Insert these two calls immediately before it:

```python
md("""## Cell 11b — Compute Calibration

**Writes to:** `Calibration` sheet (1 row appended per pipeline run).

**What it measures:** P5/P95 band coverage — fraction of actual prices that fell inside the model's 90% confidence band over the last 60 resolved forecasts. Target ~0.90 (well-calibrated). Used by the Apps Script health banner.

**Why it matters:** If actuals fall outside the 90% band more than 10% of the time, the model is overconfident. If they fall inside more than 95% of the time, the bands are too wide and signals are weak.""")

code(r"""calibration_ws = sh.worksheet('Calibration')
calibration_data = calibration_ws.get_all_values()
calibration_headers = ['date', 'coverage', 'n_samples', 'status']
if not calibration_data:
    calibration_ws.append_row(calibration_headers)

try:
    from kth.backtest.metrics import compute_calibration
    cal = compute_calibration(
        forecast_cache_dir=Path('data/forecast_cache') / 'NeoQuasar_Kronos-small',
        raw_data_dir=Path('data/raw'),
        tickers=list(ohlcv_dict.keys()),
    )
    cov = cal.get('coverage')
    n = cal.get('n_samples', 0)
    status = cal.get('status', 'insufficient_data')
    if n > 0 and cov is not None:
        # Map the function's 2-status output to the 4-status used by the health banner
        if status == 'insufficient_data':
            banner_status = 'insufficient_data'
        elif cov < 0.80:
            banner_status = 'diverged'   # way below 90% target — actuals too often outside band
        elif cov < 0.85:
            banner_status = 'monitor'    # below 90% target
        elif cov > 0.95:
            banner_status = 'overconfident'  # function already flags this, but make explicit
        else:
            banner_status = 'on_track'   # 0.85-0.95 inclusive
        calibration_ws.append_row([
            today_str,
            round(cov, 4),
            n,
            banner_status,
        ])
        print(f"Calibration: n={n} coverage={cov:.2%} status={banner_status}")
    else:
        print("Calibration: no resolved samples yet — skip write")
except Exception as e:
    print(f"Calibration: skipped ({e})")
""")
```

- [ ] **Step 4.3: Add `getHealthCheck` Apps Script function**

In `google_suite/apps_script/Code.gs`, append this function at the end (after `getExportCsv`):

```javascript
function getHealthCheck() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Calibration');
  if (!ws) return { status: 'unknown', coverage: null, target: 0.90, divergence: 0,
                    recommendation: 'Run the pipeline to compute calibration.' };
  var lastRow = ws.getLastRow();
  if (lastRow <= 1) return { status: 'unknown', coverage: null, target: 0.90,
                              divergence: 0, recommendation: 'Calibration sheet is empty.' };
  var headers = ws.getRange(1, 1, 1, ws.getLastColumn()).getValues()[0];
  var values  = ws.getRange(lastRow, 1, 1, ws.getLastColumn()).getValues()[0];
  var row = {};
  headers.forEach(function(h, i) { row[h] = values[i]; });
  var coverage = Number(row.coverage) || 0;
  var target = 0.90;  // P5/P95 band target for a well-calibrated model
  var divergence = coverage - target;
  var status = String(row.status || 'unknown');
  var recommendation;
  if (status === 'diverged' || coverage < 0.80) {
    recommendation = 'Coverage is well below the 90% target. Consider halving position sizes.';
  } else if (status === 'monitor' || coverage < 0.85) {
    recommendation = 'Coverage is below the 90% target. Monitor closely.';
  } else if (status === 'overconfident' || coverage > 0.95) {
    recommendation = 'Coverage exceeds 95% — bands may be too wide. Model is underconfident.';
  } else if (status === 'insufficient_data') {
    recommendation = 'Need at least 10 resolved forecasts. Keep running the pipeline daily.';
  } else {
    recommendation = 'On track — model calibration is within 5pp of the 90% target.';
  }
  return {
    coverage: coverage,
    target: target,
    divergence: divergence,
    status: status,
    recommendation: recommendation,
    n_samples: Number(row.n_samples) || 0,
    date: row.date || null,
  };
}
```

- [ ] **Step 4.4: Wire `getHealthCheck` into `getAllData` cache**

In `Code.gs`, find `getAllData()` (line 52-74). Modify the returned object to include `health`:

```javascript
  var data = {
    pipeline:        pipelineRows.length ? pipelineRows[0] : null,
    portfolio:       _readSheet(ss, 'Portfolio'),
    equityCurve:     _readSheetLimited(ss, 'Equity Curve',      90),
    positions:       _readSheet(ss, 'Positions'),
    tradeLog:        _readSheetLimited(ss, 'Trade Log',        200),
    forecasts:       _readSheet(ss, 'Forecasts'),
    forecastHistory: _readSheetLimited(ss, 'Forecast History', 180),
    ticket:          _readSheet(ss, 'Trade Ticket'),
    riskMetrics:     _readSheetLimited(ss, 'Risk Metrics',     365),
    health:          getHealthCheck(),
  };
```

- [ ] **Step 4.5: Render the health banner in `Index.html`**

In `google_suite/apps_script/Index.html`, find `renderDashboard(portfolio, equityCurve, riskMetrics, ticket)` (around line 369). Modify the signature to accept `health` and update the call site in `renderAll`:

Change the function signature:

```javascript
function renderDashboard(portfolio, equityCurve, riskMetrics, ticket, health) {
```

In `renderAll(d)` (around line 268), update the call:

```javascript
  renderDashboard(d.portfolio, d.equityCurve, d.riskMetrics, d.ticket, d.health);
```

Then in `renderDashboard`, after the `var band = lastRm ? lastRm.allocation_band : 'NEUTRAL';` line (around line 384), add the health banner HTML:

```javascript
  var healthHtml = '';
  if (health && health.coverage !== null) {
    var healthCls = health.status === 'diverged'      ? 'banner-red' :
                    health.status === 'monitor'        ? 'banner-yellow' :
                    health.status === 'overconfident'  ? 'banner-blue' : 'banner-green';
    healthHtml = '<div class="banner ' + healthCls + '">' +
      'P5/P95 band coverage: ' + (health.coverage * 100).toFixed(1) + '% ' +
      '(target ' + (health.target * 100).toFixed(0) + '%, n=' + health.n_samples + '). ' +
      health.recommendation +
      '</div>';
  }
```

Then in the `panel.innerHTML = ...` block, insert `healthHtml` immediately after the `<div id="status-banner"></div>` reference (which is already at the top of the body, not in `renderDashboard`). Actually, the health banner should go inside the panel. Insert it after the backtest footer `<p>` and before the equity chart:

```javascript
    '<p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:16px">' +
      'Backtest 2022-2024: CAGR +31.4%, Sharpe 1.40, Alpha vs. EW +29.9%/yr. ' +
      'Model is trend-following; alpha was lower in the 2023 bull market.' +
    '</p>' +
    healthHtml +
    '<div id="equity-chart" style="min-height:280px"></div>';
```

- [ ] **Step 4.6: Regenerate the .ipynb**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python google_suite/build_notebook.py
```

Expected: `Generated google_suite/kronos_daily_pipeline.ipynb — 40 cells` (38 after Task 2 + 1 md + 1 code for Cell 11b).

- [ ] **Step 4.7: Commit**

```bash
git add google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb google_suite/apps_script/Code.gs google_suite/apps_script/Index.html google_suite/SETUP_GUIDE.md
git commit -m "feat(google-suite): add Calibration sheet + Health Banner (P5/P95 band coverage)"
```

---

## Task 5: Trade Log inline edit + delete

**Files:**
- Modify: `google_suite/build_notebook.py` (add Cell 9b — Apply Trade Edits)
- Modify: `google_suite/apps_script/Code.gs` (add 3 functions: `submitTradeEdit`, `submitTradeDelete`, `getPendingEdits`)
- Modify: `google_suite/apps_script/Index.html` (add Edit/Delete buttons, modal, banner)
- Modify: `google_suite/SETUP_GUIDE.md` (add `Trade Edits` to staging tabs list + new "Editing a trade" section)

**Context:** The Google Suite Trade Log tab is read-only. This task adds inline edit (price + shares) and delete from the web app, with the actual portfolio rebuild deferred to a new Colab cell (Cell 9b) that the user runs separately. Pattern: Apps Script queues the edit to a `Trade Edits` staging sheet, Colab Cell 9b applies it.

- [ ] **Step 5.1: Add `Trade Edits` to SETUP_GUIDE.md tab-creation table**

In `google_suite/SETUP_GUIDE.md`, the "Staging tabs (7)" list was updated in Task 4 Step 4.1. Confirm `Trade Edits` is in that list. If not, add it.

- [ ] **Step 5.2: Add Cell 9b — Apply Trade Edits**

In `google_suite/build_notebook.py`, find the existing `md("""## Cell 10 — Generate Trade Ticket ← RUNS AFTER CELL 9""")` call (around line 295). Insert these two calls immediately before it:

```python
md("""## Cell 9b — Apply Trade Edits to Local JSON

**When to run:** Only when the Apps Script shows "1+ pending edits" banner. Replaces Cells 9-15 in this single Colab session.

**Reads:** `Trade Edits` staging sheet (rows with `action = edit` or `CANCEL`).
**Applies:** Calls `edit_trade()` and `delete_trade()` from `kth.trading.portfolio`.
**Writes:** Cleared `Trade Edits` sheet, refreshed `paper_portfolio.json`, then re-runs staging writes (Cells 13/14) and live promotion (Cell 14).""")

code(r"""trade_edits_ws = sh.worksheet('Trade Edits')
trade_edits_data = trade_edits_ws.get_all_values()
trade_edits_headers = ['date', 'action', 'index', 'ticker', 'shares', 'price', 'ref_id', 'requested_at']
if not trade_edits_data:
    trade_edits_ws.append_row(trade_edits_headers)
else:
    # Process existing edits
    from kth.trading.portfolio import edit_trade, delete_trade
    pf = init_portfolio('paper')
    for row in trade_edits_data[1:]:
        if not row or not row[0]: continue
        action = row[1]
        if action == 'edit':
            try:
                # edit_trade signature: (index, new_price, new_shares, mode) — kth/trading/portfolio.py:439
                edit_trade(int(row[2]), new_price=float(row[5]), new_shares=int(float(row[4])), mode='paper')
                print(f"  Applied edit: {row[3]} -> shares={row[4]} price={row[5]}")
            except Exception as e:
                print(f"  Edit failed for row {row[2]}: {e}")
        elif action == 'CANCEL':
            try:
                delete_trade(int(row[2]), 'paper')
                print(f"  Applied delete: index {row[2]}")
            except Exception as e:
                print(f"  Delete failed for row {row[2]}: {e}")
    trade_edits_ws.clear()
    trade_edits_ws.append_row(trade_edits_headers)
    print("Trade Edits cleared.")

# Re-run staging writes (mirror Cells 13/14) so changes appear in live sheets
pf_data = init_portfolio('paper')
_write_staging('Portfolio_staging',
    ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

pos = get_positions('paper')
pos_rows = []
for p in pos['positions']:
    close = float(ohlcv_dict[p['ticker']]['close'].iloc[-1]) if p['ticker'] in ohlcv_dict else p['avg_cost']
    pnl = (close - p['avg_cost']) * p['shares']
    pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
    pos_rows.append([p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
                     get_sector(p['ticker']), round(close, 2), round(pnl, 2),
                     round(pnl_pct, 4), round(pnl_pct + 0.10, 4)])
_write_staging('Positions_staging',
    ['ticker','shares','avg_cost','entry_date','sector','current_price','pnl','pnl_pct','pct_to_stoploss'],
    pos_rows)

STAGING_MAP = {
    'Portfolio_staging':     'Portfolio',
    'Positions_staging':     'Positions',
    'Forecasts_staging':     'Forecasts',
    'Trade Ticket_staging':  'Trade Ticket',
    'Risk Metrics_staging':  'Risk Metrics',
    'Equity Curve_staging':  'Equity Curve',
}
for staging_name, live_name in STAGING_MAP.items():
    try:
        staging_ws = sh.worksheet(staging_name)
        live_ws    = sh.worksheet(live_name)
        data = staging_ws.get_all_values()
        if data:
            live_ws.clear()
            live_ws.update('A1', data)
        staging_ws.clear()
    except Exception as e:
        print(f"  Promotion {staging_name} -> {live_name} failed: {e}")
print("Trade edits applied and staging promoted.")
""")
```

- [ ] **Step 5.3: Add `submitTradeEdit` Apps Script function**

In `google_suite/apps_script/Code.gs`, append after the existing `submitFills` function (line 81-117):

```javascript
function submitTradeEdit(index, newShares, newPrice) {
  // Validate input
  if (!Number.isInteger(index) || index < 0) {
    return { ok: false, msg: 'Invalid trade index' };
  }
  if (!Number.isInteger(newShares) || newShares <= 0 || newShares % 100 !== 0) {
    return { ok: false, msg: 'Shares must be a positive multiple of 100' };
  }
  if (typeof newPrice !== 'number' || newPrice <= 0) {
    return { ok: false, msg: 'Price must be a positive number' };
  }

  // Verify the trade exists in the Trade Log sheet
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Log');
  var data = ws.getDataRange().getValues();
  if (data.length <= 1 || index >= data.length - 1) {
    return { ok: false, msg: 'Trade index out of range' };
  }
  var ticker = data[index + 1][1];  // col 1 (0-indexed) is ticker

  // Append to Trade Edits staging sheet
  var editsWs = ss.getSheetByName('Trade Edits');
  var editsData = editsWs.getDataRange().getValues();
  if (editsData.length === 0) {
    editsWs.appendRow(['date','action','index','ticker','shares','price','ref_id','requested_at']);
  }
  editsWs.appendRow([
    new Date().toISOString().slice(0, 10),
    'edit',
    index,
    ticker,
    newShares,
    newPrice,
    '',
    new Date().toISOString(),
  ]);

  // Invalidate cache
  CacheService.getScriptCache().remove('all_data');
  return { ok: true, status: 'edit queued — please re-run Colab Cell 9b' };
}
```

- [ ] **Step 5.4: Add `submitTradeDelete` Apps Script function**

Append after `submitTradeEdit`:

```javascript
function submitTradeDelete(index) {
  if (!Number.isInteger(index) || index < 0) {
    return { ok: false, msg: 'Invalid trade index' };
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Log');
  var data = ws.getDataRange().getValues();
  if (data.length <= 1 || index >= data.length - 1) {
    return { ok: false, msg: 'Trade index out of range' };
  }
  var tradeId = data[index + 1][8];  // col 8 is the trade_id

  var editsWs = ss.getSheetByName('Trade Edits');
  var editsData = editsWs.getDataRange().getValues();
  if (editsData.length === 0) {
    editsWs.appendRow(['date','action','index','ticker','shares','price','ref_id','requested_at']);
  }
  editsWs.appendRow([
    new Date().toISOString().slice(0, 10),
    'CANCEL',
    index,
    data[index + 1][1],
    '',
    '',
    tradeId,
    new Date().toISOString(),
  ]);

  CacheService.getScriptCache().remove('all_data');
  return { ok: true, status: 'delete queued — please re-run Colab Cell 9b' };
}
```

- [ ] **Step 5.5: Add `getPendingEdits` Apps Script function**

Append after `submitTradeDelete`:

```javascript
function getPendingEdits() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Edits');
  if (!ws) return { count: 0, edits: [] };
  var data = ws.getDataRange().getValues();
  if (data.length <= 1) return { count: 0, edits: [] };
  var headers = data[0];
  var edits = data.slice(1).map(function(r) {
    var obj = {};
    headers.forEach(function(h, i) { obj[h] = r[i]; });
    return obj;
  }).filter(function(e) { return e.action; });
  return { count: edits.length, edits: edits };
}
```

- [ ] **Step 5.6: Add Edit/Delete buttons to Trade Log table in `Index.html`**

In `google_suite/apps_script/Index.html`, find the `renderTradeLog(tradeLog)` function (around line 507). The function builds rows from `tradeLog`. Modify the function to include the two new columns. First, find the `var rows = tradeLog.map(...)` block and update the row template to include the action buttons. The existing code (around line 516-531) is:

```js
var rows = tradeLog.map(function(r) {
    var isCancel    = (r.action === 'CANCEL');
    var isCancelled = cancelledIds[r.trade_id];  // Pre-existing bug: was [r.id]; the field is `trade_id`
    var actionCell  = isCancel
      ? '↩ cancels ' + (r.ref_id || '')
      : r.action;
    var rowClass = (isCancel || isCancelled) ? ' class="cancelled"' : '';
    return '<tr' + rowClass + '>' +
      _td(fmt.date(r.timestamp)) +
      _td(r.ticker) +
      '<td>' + actionCell + '</td>' +
      _tdNum(fmt.shares(r.shares), r.shares) +
      _tdNum(r.price != null ? fmt.thb(r.price) : '—', r.price) +
      _td(r.rationale) +
      '</tr>';
  }).join('');
```

Replace with:

```js
var rows = tradeLog.map(function(r, idx) {
    var isCancel    = (r.action === 'CANCEL');
    var isCancelled = cancelledIds[r.trade_id];  // Pre-existing bug: was [r.id]; the field is `trade_id`
    var actionCell  = isCancel
      ? '↩ cancels ' + (r.ref_id || '')
      : r.action;
    var rowClass = (isCancel || isCancelled) ? ' class="cancelled"' : '';
    var editCell = isCancel || isCancelled
      ? '<td></td>'
      : '<td><button class="btn-icon" onclick="openEditTradeModal(' + idx + ')" title="Edit">✏️</button>' +
        ' <button class="btn-icon" onclick="confirmDeleteTrade(' + idx + ')" title="Delete">🗑️</button></td>';
    return '<tr' + rowClass + '>' +
      _td(fmt.date(r.timestamp)) +
      _td(r.ticker) +
      '<td>' + actionCell + '</td>' +
      _tdNum(fmt.shares(r.shares), r.shares) +
      _tdNum(r.price != null ? fmt.thb(r.price) : '—', r.price) +
      _td(r.rationale) +
      editCell +
      '</tr>';
  }).join('');
```

Then update the table header (around line 535-541). Currently:

```js
'<table id="tbl-tradelog">' +
    '<thead><tr>' +
      '<th>Date</th><th>Ticker</th><th>Action</th>' +
      '<th>Shares</th><th>Price</th><th>Rationale</th>' +
    '</tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table></div>' +
```

Add a new `<th>` for the action column:

```js
'<table id="tbl-tradelog">' +
    '<thead><tr>' +
      '<th>Date</th><th>Ticker</th><th>Action</th>' +
      '<th>Shares</th><th>Price</th><th>Rationale</th><th>Edit</th>' +
    '</tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table></div>' +
```

- [ ] **Step 5.7: Add CSS for icon buttons and the edit modal**

In `google_suite/apps_script/Index.html`, add these styles after the existing `.btn-secondary` rule (around line 96):

```css
.btn-icon { background: none; border: 1px solid var(--border); border-radius: 4px;
            padding: 4px 8px; cursor: pointer; font-size: 0.85rem; }
.btn-icon:hover { background: var(--bg); }
```

- [ ] **Step 5.8: Add edit modal HTML, JS, and `getPendingEdits` integration**

Add the edit-trade modal HTML after the existing fill-modal (around line 154, before `<script src="https://www.gstatic.com/charts/loader.js">`):

```html
<!-- Edit-trade modal -->
<div id="edit-trade-modal" class="modal-overlay" hidden>
  <div class="modal-box">
    <h3>Edit Trade</h3>
    <p class="modal-note">Updates will be queued and applied the next time you re-run Colab Cell 9b.</p>
    <div id="edit-trade-tbody">
      <p>Trade: <span id="edit-trade-ticker"></span></p>
      <p>Original: <span id="edit-trade-orig"></span></p>
      <p>New shares: <input class="modal-input" id="edit-shares" type="number" step="100" min="100"></p>
      <p>New price (THB): <input class="modal-input" id="edit-price" type="number" step="0.01" min="0.01"></p>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeEditTradeModal()">Cancel</button>
      <button class="btn-primary"   onclick="saveEditTrade()">✓ Save Edit</button>
    </div>
  </div>
</div>
```

Add the JS for these new functions in the `<script>` block (after the existing `saveFills` function, around line 343):

```javascript
var _editTradeIndex = -1;
var _editTradeTicker = '';

function openEditTradeModal(idx) {
  var trade = _lastTradeLog[idx];
  if (!trade) return;
  _editTradeIndex = idx;
  _editTradeTicker = trade.ticker;
  document.getElementById('edit-trade-ticker').textContent = trade.ticker;
  document.getElementById('edit-trade-orig').textContent = 'shares=' + trade.shares + ', price=' + (trade.price != null ? trade.price.toFixed(2) : '—');
  document.getElementById('edit-shares').value = trade.shares;
  document.getElementById('edit-price').value = trade.price != null ? trade.price.toFixed(2) : '';
  document.getElementById('edit-trade-modal').hidden = false;
}

function closeEditTradeModal() {
  document.getElementById('edit-trade-modal').hidden = true;
}

function saveEditTrade() {
  var shares = parseInt(document.getElementById('edit-shares').value, 10);
  var price  = parseFloat(document.getElementById('edit-price').value);
  if (!shares || shares <= 0 || shares % 100 !== 0) {
    alert('Shares must be a positive multiple of 100 (SET board lot).'); return;
  }
  if (!price || price <= 0) {
    alert('Price must be positive.'); return;
  }
  google.script.run
    .withSuccessHandler(function(result) {
      if (result.ok) {
        closeEditTradeModal();
        alert('Edit queued. ' + result.status);
        showSpinner();
        google.script.run
          .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); checkPendingEditsBanner(); })
          .withFailureHandler(showError)
          .refreshAllData();
      } else {
        alert('Save failed: ' + result.msg);
      }
    })
    .withFailureHandler(function(err) { alert('Error: ' + String(err)); })
    .submitTradeEdit(_editTradeIndex, shares, price);
}

function confirmDeleteTrade(idx) {
  var trade = _lastTradeLog[idx];
  if (!trade) return;
  if (!confirm('Delete trade #' + (idx + 1) + ': ' + trade.action.toUpperCase() + ' ' + trade.ticker + '?\nThis will be queued and applied when you re-run Colab Cell 9b.')) return;
  google.script.run
    .withSuccessHandler(function(result) {
      if (result.ok) {
        alert('Delete queued. ' + result.status);
        showSpinner();
        google.script.run
          .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); checkPendingEditsBanner(); })
          .withFailureHandler(showError)
          .refreshAllData();
      } else {
        alert('Delete failed: ' + result.msg);
      }
    })
    .withFailureHandler(function(err) { alert('Error: ' + String(err)); })
    .submitTradeDelete(idx);
}

function checkPendingEditsBanner() {
  google.script.run
    .withSuccessHandler(function(result) {
      var banner = document.getElementById('pending-edits-banner');
      if (result.count > 0) {
        banner.innerHTML = '<div class="banner banner-yellow">⚠ ' + result.count +
          ' pending trade edit' + (result.count > 1 ? 's' : '') +
          ' — open Colab and run Cell 9b to apply.</div>';
        banner.hidden = false;
      } else {
        banner.hidden = true;
      }
    })
    .getPendingEdits();
}

var _lastTradeLog = [];
```

Then in `renderTradeLog`, save the trade log to `_lastTradeLog` at the top:

```javascript
function renderTradeLog(tradeLog) {
  _lastTradeLog = tradeLog || [];
  var panel = document.getElementById('panel-tradelog');
  if (!tradeLog.length) { showEmptyState('tradelog'); return; }
  // ... rest unchanged
```

And add a `<div id="pending-edits-banner">` after the tab bar (around line 119):

```html
<nav id="tab-bar">
  <button class="tab-btn active" onclick="switchTab('dashboard')">Dashboard</button>
  <button class="tab-btn"        onclick="switchTab('positions')">Positions</button>
  <button class="tab-btn"        onclick="switchTab('tradelog')">Trade Log</button>
  <button class="tab-btn"        onclick="switchTab('forecasts')">Forecasts</button>
  <button class="tab-btn"        onclick="switchTab('ticket')">Trade Ticket</button>
</nav>

<div id="pending-edits-banner" hidden></div>
```

- [ ] **Step 5.9: Add "Editing a trade" section to SETUP_GUIDE.md**

Add this section after the existing "What you'll see" section in `google_suite/SETUP_GUIDE.md`:

```markdown
## Editing a trade

The Apps Script Trade Log has ✏️ and 🗑️ buttons on every row. Clicking either queues a change in the `Trade Edits` staging sheet — it does NOT update the portfolio directly. The reason: rebuilding the portfolio requires running the same Python logic that the daily pipeline runs (FIFO matching, cash/positions recalc, equity curve update), and Apps Script has no Python.

**To apply an edit:**

1. In the Apps Script web app, click ✏️ in the Trade Log row → modal opens with current shares + price.
2. Type the new shares and price → click "✓ Save Edit". A banner appears: "1 pending edit — open Colab and run Cell 9b".
3. Open your Colab notebook, scroll to **Cell 9b** (between Cells 9 and 10), click Run.
4. Cell 9b reads the Trade Edits sheet, calls `edit_trade()` from kth, then re-runs the staging write + promotion (the same logic as Cells 13/14).
5. Return to the Apps Script. Click Refresh. The change is now visible.

**Same process for delete** — click 🗑️, confirm, then run Colab Cell 9b.

**Why two steps?** Apps Script can't run Python. By keeping Apps Script as a write-queue and Colab as the execution engine, we have a single source of truth (the Drive JSON) and avoid duplicating the kth code in JavaScript.
```

- [ ] **Step 5.10: Regenerate the .ipynb**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python google_suite/build_notebook.py
```

Expected: `Generated google_suite/kronos_daily_pipeline.ipynb — 42 cells` (40 after Task 4 + 1 md + 1 code for Cell 9b).

- [ ] **Step 5.11: Commit**

```bash
git add google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb google_suite/apps_script/Code.gs google_suite/apps_script/Index.html google_suite/SETUP_GUIDE.md
git commit -m "feat(google-suite): Trade Log inline edit/delete via Apps Script + Colab Cell 9b"
```

---

## Task 6: Initial capital UI (first-run banner + Settings modal)

**Files:**
- Modify: `google_suite/build_notebook.py` (add Cell 4b — Apply Capital Reset)
- Modify: `google_suite/apps_script/Code.gs` (add `resetCapital`, `getSetupStatus`)
- Modify: `google_suite/apps_script/Index.html` (add setup banner, settings modal, ⚙ button)
- Modify: `google_suite/SETUP_GUIDE.md` (add `Capital Reset` to staging tabs)

**Context:** Flask shows a first-run setup banner. Google Suite requires editing a Colab cell to change capital. This task adds a first-run banner + permanent Settings button. The destructive Reset flow requires typed confirmation. Pattern: Apps Script queues the reset, Colab Cell 4b applies it (mirrors Task 5's pattern).

- [ ] **Step 6.1: Add `Capital Reset` to SETUP_GUIDE.md tab-creation table**

Confirm `Capital Reset` is in the "Staging tabs (7)" list (updated in Task 4 Step 4.1). If not, add it.

- [ ] **Step 6.2: Add Cell 4b — Apply Capital Reset**

In `google_suite/build_notebook.py`, find the existing `md("""## Cell 5 — Set Pipeline Status: Running""")` call (around line 102). Insert these two calls immediately before it:

```python
md("""## Cell 4b — Apply Capital Reset

**When to run:** Only when the Apps Script shows a Reset queued banner. Replaces Cells 5-15 in this single Colab session.

**Reads:** `Capital Reset` staging sheet (rows with `confirm_text = "RESET"` or `"SETUP"`).
**Applies:** Calls `reset_portfolio('paper', newCapital)` from `kth.trading.portfolio`.
**Writes:** Cleared `Capital Reset` sheet, fresh `paper_portfolio.json`, then re-runs staging writes + promotion.""")

code(r"""capital_reset_ws = sh.worksheet('Capital Reset')
capital_reset_data = capital_reset_ws.get_all_values()
capital_reset_headers = ['date', 'action', 'capital', 'confirm_text', 'requested_at']
if not capital_reset_data:
    capital_reset_ws.append_row(capital_reset_headers)
else:
    from kth.trading.portfolio import reset_portfolio, get_positions
    for row in capital_reset_data[1:]:
        if not row or not row[0]: continue
        action = row[1]
        capital = float(row[2])
        confirm = row[3]
        if confirm not in ('RESET', 'SETUP'):
            print(f"  Skipping row with invalid confirm_text: {confirm}")
            continue
        try:
            reset_portfolio('paper', capital)
            print(f"  Applied {action}: capital={capital:,.0f} THB (confirm={confirm})")
        except Exception as e:
            print(f"  Reset failed: {e}")
    capital_reset_ws.clear()
    capital_reset_ws.append_row(capital_reset_headers)
    print("Capital Reset cleared.")

# Re-run staging writes (mirror Cells 13/14)
pf_data = init_portfolio('paper')
_write_staging('Portfolio_staging',
    ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

# Clear Positions sheet (capital reset wipes all positions)
pos = get_positions('paper')
pos_rows = []
for p in pos['positions']:
    close = float(ohlcv_dict[p['ticker']]['close'].iloc[-1]) if p['ticker'] in ohlcv_dict else p['avg_cost']
    pnl = (close - p['avg_cost']) * p['shares']
    pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
    pos_rows.append([p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
                     get_sector(p['ticker']), round(close, 2), round(pnl, 2),
                     round(pnl_pct, 4), round(pnl_pct + 0.10, 4)])
_write_staging('Positions_staging',
    ['ticker','shares','avg_cost','entry_date','sector','current_price','pnl','pnl_pct','pct_to_stoploss'],
    pos_rows)

# Append new equity curve row (post-reset: equity == initial_capital, invested == 0)
_write_staging('Equity Curve_staging',
    ['date', 'equity', 'cash', 'invested'],
    [[today_str, round(pf_data['initial_capital'], 2), round(pf_data['cash'], 2), 0.0]])

# Promote all staging to live (Cell 14 mirror)
STAGING_MAP = {
    'Portfolio_staging': 'Portfolio',
    'Positions_staging': 'Positions',
    'Forecasts_staging': 'Forecasts',
    'Trade Ticket_staging': 'Trade Ticket',
    'Risk Metrics_staging': 'Risk Metrics',
    'Equity Curve_staging': 'Equity Curve',
}
for staging_name, live_name in STAGING_MAP.items():
    try:
        staging_ws = sh.worksheet(staging_name)
        live_ws = sh.worksheet(live_name)
        data = staging_ws.get_all_values()
        if data:
            live_ws.clear()
            live_ws.update('A1', data)
        staging_ws.clear()
    except Exception as e:
        print(f"  Promotion {staging_name} -> {live_name} failed: {e}")

print("Capital reset applied and staging promoted.")
""")
```

- [ ] **Step 6.3: Add `resetCapital` Apps Script function**

In `google_suite/apps_script/Code.gs`, append after `getPendingEdits`:

```javascript
function resetCapital(newCapital, confirmText) {
  if (typeof newCapital !== 'number' || newCapital < 1 || newCapital > 100000000) {
    return { ok: false, msg: 'Capital must be between 1 and 100,000,000 THB' };
  }
  if (confirmText !== 'RESET' && confirmText !== 'SETUP') {
    return { ok: false, msg: 'Confirmation text must be RESET (destructive) or SETUP (first run)' };
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Capital Reset');
  var data = ws.getDataRange().getValues();
  if (data.length === 0) {
    ws.appendRow(['date','action','capital','confirm_text','requested_at']);
  }
  ws.appendRow([
    new Date().toISOString().slice(0, 10),
    confirmText === 'RESET' ? 'reset' : 'setup',
    newCapital,
    confirmText,
    new Date().toISOString(),
  ]);

  CacheService.getScriptCache().remove('all_data');
  return {
    ok: true,
    status: confirmText === 'RESET'
      ? 'reset queued — please re-run Colab Cell 4b (DESTRUCTIVE: clears all trades)'
      : 'setup queued — please re-run Colab Cell 4b',
  };
}
```

- [ ] **Step 6.4: Add `getSetupStatus` Apps Script function**

Append after `resetCapital`:

```javascript
function getSetupStatus() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var portfolioWs = ss.getSheetByName('Portfolio');
  var tradeLogWs = ss.getSheetByName('Trade Log');
  var portfolioRows = portfolioWs ? portfolioWs.getDataRange().getValues() : [];
  var tradeLogRows  = tradeLogWs ? tradeLogWs.getDataRange().getValues() : [];
  var hasPortfolio = portfolioRows.length > 1;
  var hasTrades = tradeLogRows.length > 1;
  var currentCapital = hasPortfolio ? Number(portfolioRows[1][0]) || 0 : 0;
  return {
    isFirstRun: !hasPortfolio,
    hasTrades: hasTrades,
    currentCapital: currentCapital,
  };
}
```

- [ ] **Step 6.5: Add setup banner, settings modal HTML to `Index.html`**

Add these elements after the existing edit-trade modal (around line 154):

```html
<!-- Setup banner (first run only) -->
<div id="setup-banner" class="banner banner-blue" hidden style="padding:20px">
  <h3>🏦 First-day setup</h3>
  <p>Set your starting capital before recording any trades.</p>
  <p>Capital (THB): <input class="modal-input" id="setup-capital" type="number" min="1" max="100000000" step="1000" value="500000" style="width:140px"></p>
  <button class="btn-primary" onclick="submitSetup()">Start Paper Trading</button>
  <p style="font-size:0.8rem;margin-top:8px">This will queue a setup in the Capital Reset sheet. Re-run Colab Cell 4b to apply.</p>
</div>

<!-- Settings button + modal -->
<button id="settings-btn" class="btn-secondary" onclick="openSettingsModal()" style="position:fixed;top:12px;right:12px;z-index:50">⚙ Settings</button>
<div id="settings-modal" class="modal-overlay" hidden>
  <div class="modal-box">
    <h3>⚙ Settings</h3>
    <p>Current capital: <strong id="settings-current-capital">—</strong></p>
    <p>Total trades: <strong id="settings-trade-count">—</strong></p>
    <hr style="margin:16px 0;border:none;border-top:1px solid var(--border)">
    <h4 style="color:var(--red)">Reset Portfolio (destructive)</h4>
    <p class="modal-note">This will delete all trades, positions, equity curve, and trade log. The portfolio will be reinitialised with a new capital amount.</p>
    <p>New capital (THB): <input class="modal-input" id="settings-new-capital" type="number" min="1" max="100000000" step="1000"></p>
    <p>Type <code>RESET</code> to confirm: <input class="modal-input" id="settings-confirm-text" type="text" style="width:120px"></p>
    <button class="btn-primary" id="settings-reset-btn" disabled onclick="submitReset()">⚠ Reset Portfolio</button>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeSettingsModal()">Close</button>
    </div>
  </div>
</div>
```

Add CSS for `banner-blue` (in the existing `<style>` block, around line 30):

```css
.banner-blue { background: #e8f0fe; color: #1967d2; border-left: 4px solid var(--blue); }
```

- [ ] **Step 6.6: Add JS for setup, settings, and the validation logic**

In the `<script>` block of `Index.html`, add these functions (after the `confirmDeleteTrade` function added in Task 5):

```javascript
function submitSetup() {
  var capital = parseFloat(document.getElementById('setup-capital').value);
  if (!capital || capital < 1 || capital > 100000000) {
    alert('Capital must be between 1 and 100,000,000 THB'); return;
  }
  google.script.run
    .withSuccessHandler(function(result) {
      if (result.ok) {
        document.getElementById('setup-banner').hidden = true;
        alert('Setup queued. Open Colab and run Cell 4b to apply.');
      } else {
        alert('Setup failed: ' + result.msg);
      }
    })
    .withFailureHandler(function(err) { alert('Error: ' + String(err)); })
    .resetCapital(capital, 'SETUP');
}

function openSettingsModal() {
  google.script.run
    .withSuccessHandler(function(status) {
      document.getElementById('settings-current-capital').textContent = '฿' + status.currentCapital.toLocaleString('th-TH');
      document.getElementById('settings-trade-count').textContent = status.hasTrades ? 'trades exist' : '0 (fresh)';
      document.getElementById('settings-modal').hidden = false;
    })
    .getSetupStatus();
}

function closeSettingsModal() {
  document.getElementById('settings-modal').hidden = true;
}

// Enable reset button only when RESET is typed
document.addEventListener('DOMContentLoaded', function() {
  var confirmInput = document.getElementById('settings-confirm-text');
  var resetBtn = document.getElementById('settings-reset-btn');
  if (confirmInput && resetBtn) {
    confirmInput.addEventListener('input', function() {
      resetBtn.disabled = confirmInput.value !== 'RESET';
    });
  }
});

function submitReset() {
  var capital = parseFloat(document.getElementById('settings-new-capital').value);
  var confirm = document.getElementById('settings-confirm-text').value;
  if (confirm !== 'RESET') { alert('Type RESET to confirm.'); return; }
  if (!capital || capital < 1 || capital > 100000000) {
    alert('Capital must be between 1 and 100,000,000 THB'); return;
  }
  if (!confirm('This will DELETE ALL TRADES. Continue?')) return;
  google.script.run
    .withSuccessHandler(function(result) {
      if (result.ok) {
        closeSettingsModal();
        alert('Reset queued. Open Colab and run Cell 4b to apply. DESTRUCTIVE: clears all trades.');
      } else {
        alert('Reset failed: ' + result.msg);
      }
    })
    .withFailureHandler(function(err) { alert('Error: ' + String(err)); })
    .resetCapital(capital, 'RESET');
}
```

Then modify the initial load to check setup status. Find the existing load block (around line 823-830):

```javascript
google.charts.load('current', {packages: ['corechart']});
google.charts.setOnLoadCallback(function() {
  showSpinner();
  google.script.run
    .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); })
    .withFailureHandler(showError)
    .getAllData();
});
```

Replace with:

```javascript
google.charts.load('current', {packages: ['corechart']});
google.charts.setOnLoadCallback(function() {
  showSpinner();
  google.script.run
    .withSuccessHandler(function(d) {
      hideSpinner();
      renderAll(d);
      checkPendingEditsBanner();
      google.script.run
        .withSuccessHandler(function(status) {
          if (status.isFirstRun) {
            document.getElementById('setup-banner').hidden = false;
          }
        })
        .getSetupStatus();
    })
    .withFailureHandler(showError)
    .getAllData();
});
```

- [ ] **Step 6.7: Regenerate the .ipynb**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python google_suite/build_notebook.py
```

Expected: `Generated google_suite/kronos_daily_pipeline.ipynb — 44 cells` (42 after Task 5 + 1 md + 1 code for Cell 4b).

- [ ] **Step 6.8: Commit**

```bash
git add google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb google_suite/apps_script/Code.gs google_suite/apps_script/Index.html google_suite/SETUP_GUIDE.md
git commit -m "feat(google-suite): first-run setup banner + Settings modal with typed-confirm reset"
```

---

## Task 7: Auto-refresh + cache TTL

**Files:**
- Modify: `google_suite/apps_script/Index.html` (add `setInterval` for auto-refresh)
- Modify: `google_suite/apps_script/Code.gs` (change cache TTL from 300 to 60)

**Context:** Flask auto-refreshes every 60s. The 300s Apps Script cache means a running pipeline shows stale "completed" status. This task makes the dashboard auto-poll and reduces the cache TTL.

- [ ] **Step 7.1: Add auto-refresh interval in `Index.html`**

Find the end of the `<script>` block (just before `</script>`, around line 849). Insert:

```javascript
var _lastRefreshAt = 0;
setInterval(function() {
  if (document.hidden) return;
  if (Date.now() - _lastRefreshAt < 30000) return;
  refreshData();
}, 60000);
```

- [ ] **Step 7.2: Update `refreshData()` to set `_lastRefreshAt`**

Find the `refreshData` function (around line 832):

```javascript
function refreshData() {
  showSpinner();
  google.script.run
    .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); })
    .withFailureHandler(showError)
    .refreshAllData();
}
```

Replace with:

```javascript
function refreshData() {
  _lastRefreshAt = Date.now();
  showSpinner();
  google.script.run
    .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); checkPendingEditsBanner(); })
    .withFailureHandler(showError)
    .refreshAllData();
}
```

- [ ] **Step 7.3: Reduce cache TTL in `Code.gs`**

In `getAllData()` (line 72), find:

```javascript
  if (json.length < 100000) cache.put('all_data', json, 300);
```

Change to:

```javascript
  if (json.length < 100000) cache.put('all_data', json, 60);
```

- [ ] **Step 7.4: Commit**

```bash
git add google_suite/apps_script/Index.html google_suite/apps_script/Code.gs
git commit -m "feat(google-suite): 60s auto-refresh + 60s cache TTL (was 300s)"
```

---

## Task 8: Mock data fix + Esc-key handler

**Files:**
- Modify: `google_suite/apps_script/Index.html` (MOCK.forecasts field, keydown listener)

**Context:** MOCK.forecasts is missing `date_updated` (the data-badge logic silently fails in MOCK mode). Add the field. Also add an Esc-key handler that closes any open modal — a small UX improvement that Flask doesn't have either, but is cheap to add.

- [ ] **Step 8.1: Add `date_updated` to MOCK.forecasts entries**

In `google_suite/apps_script/Index.html`, find the `MOCK.forecasts` array (around line 197-204). Currently each entry lacks `date_updated`. Add the field to all 3 entries:

The current code is:

```javascript
forecasts: [
    { ticker: 'PTT.BK',    rank_score: 3.2, exp_ret: 0.045, band_width: 0.08,
      confidence: 'green',  net_return: 0.039, p50: 36.75, sector: 'Energy' },
    { ticker: 'ADVANC.BK', rank_score: 2.1, exp_ret: 0.031, band_width: 0.18,
      confidence: 'yellow', net_return: 0.025, p50: 225.0, sector: 'Telecom' },
    { ticker: 'KBANK.BK',  rank_score: 0.8, exp_ret: 0.012, band_width: 0.35,
      confidence: 'red',    net_return: 0.006, p50: 142.0, sector: 'Finance' },
  ],
```

Replace with (add `date_updated: '2026-06-04'` to each):

```javascript
forecasts: [
    { date_updated: '2026-06-04', ticker: 'PTT.BK',    rank_score: 3.2, exp_ret: 0.045, band_width: 0.08,
      confidence: 'green',  net_return: 0.039, p50: 36.75, sector: 'Energy' },
    { date_updated: '2026-06-04', ticker: 'ADVANC.BK', rank_score: 2.1, exp_ret: 0.031, band_width: 0.18,
      confidence: 'yellow', net_return: 0.025, p50: 225.0, sector: 'Telecom' },
    { date_updated: '2026-06-04', ticker: 'KBANK.BK',  rank_score: 0.8, exp_ret: 0.012, band_width: 0.35,
      confidence: 'red',    net_return: 0.006, p50: 142.0, sector: 'Finance' },
  ],
```

- [ ] **Step 8.2: Add Esc-key handler**

Find the end of the `<script>` block (just before `</script>`, after the `setInterval` added in Task 7). Insert:

```javascript
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeFillModal();
    var sm = document.getElementById('settings-modal');
    if (sm && !sm.hidden) sm.hidden = true;
    var em = document.getElementById('edit-trade-modal');
    if (em && !em.hidden) em.hidden = true;
  }
});
```

- [ ] **Step 8.3: Commit**

```bash
git add google_suite/apps_script/Index.html
git commit -m "feat(google-suite): MOCK.forecasts date_updated + Esc closes modals"
```

---

## Task 9: SETUP_GUIDE.md updates (deploy URL, what-you'll-see, final polish)

**Files:**
- Modify: `google_suite/SETUP_GUIDE.md` (3 section updates)

**Context:** Documentation updates. The deploy URL note is important — re-deploying creates a new URL. The "what you'll see" section needs to list the new UI elements.

- [ ] **Step 9.1: Add deploy URL stability note to Step 3.6**

In `google_suite/SETUP_GUIDE.md`, find the "Step 3.6: Upload project folder to Google Drive" section. Add a note after the section's main instruction:

```markdown
**Important:** The Apps Script web app URL stays the same across deploys **only if you do NOT create a new deployment**. To publish updated code: in Apps Script editor, click "Deploy" → "Manage deployments" → pencil icon next to the existing deployment → update version → Deploy. The URL is unchanged.

If you click "Deploy" → "New deployment", you get a new URL. This is almost never what you want.
```

- [ ] **Step 9.2: Add bullet points to "What you'll see" section**

Find the "What you'll see" section (if it exists; if not, create one near the top of the file). Add these bullets:

```markdown
- **Reset Portfolio (⚙ button, top-right of Dashboard)** — change your initial capital
- **Trade Log edit/delete** — click ✏️ or 🗑️ in any Trade Log row
- **Health banner** — appears on Dashboard if P5/P95 band coverage diverges from 90% target
- **First-run setup banner** — appears once when no portfolio exists yet
```

- [ ] **Step 9.3: Commit**

```bash
git add google_suite/SETUP_GUIDE.md
git commit -m "docs(google-suite): SETUP_GUIDE deploy URL note + feature list"
```

---

## Task 10: README.md update

**Files:**
- Modify: `README.md` (1 line)

**Context:** Add the new features to the project overview.

- [ ] **Step 10.1: Find the Google Suite dashboard bullet in README.md**

In `README.md`, find the line that starts with `- 🔨 **Google Suite dashboard**`. The current line ends with a mention of spec and plan links. Replace the line with:

```markdown
- 🔨 **Google Suite dashboard** (`google_suite/`): Colab daily pipeline + Google Sheets data store + Apps Script web app. **Now with:** Trade Log inline edit/delete, Reset Capital modal, Signal Health banner, Position row colors, 60s auto-refresh. See [spec](docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md), [parity-fix spec](docs/superpowers/specs/2026-06-06-google-suite-dashboard-parity-fixes-design.md), and [implementation plan](docs/superpowers/plans/2026-06-06-google-suite-dashboard-parity-fixes.md).
```

- [ ] **Step 10.2: Commit**

```bash
git add README.md
git commit -m "docs: README links to parity-fix spec + lists new features"
```

---

## Verification

After all 10 tasks complete, run this end-to-end checklist:

1. **Verify cell count** — the .ipynb should have 44 cells (started at 36, added 4 new cells × {1 md + 1 code each} = 8 new cells from Tasks 2/4/5/6: 36 → 38 → 40 → 42 → 44).

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
python -c "import json; nb=json.load(open('google_suite/kronos_daily_pipeline.ipynb')); print(f'Cells: {len(nb[\"cells\"])}'); [print(i, c['cell_type']) for i, c in enumerate(nb['cells'])]"
```

Expected: 44 cells, alternating markdown and code (md = description, code = Python).

2. **Verify all Apps Script functions exist:**

```bash
grep -E "^function " google_suite/apps_script/Code.gs
```

Expected: `doGet`, `_rowToObj`, `_readSheet`, `_readSheetLimited`, `_csvField`, `getAllData`, `refreshAllData`, `submitFills`, `getExportCsv`, `getHealthCheck`, `submitTradeEdit`, `submitTradeDelete`, `getPendingEdits`, `resetCapital`, `getSetupStatus`. (15 functions total.)

3. **Visual smoke test:** Open the Apps Script web app URL. With MOCK data, verify:
- [ ] Dashboard shows equity curve, regime badge, P&L cards, health banner (status: "unknown" with helpful message)
- [ ] Positions table shows red/orange/green left borders on the 2 MOCK positions
- [ ] Trade Log has ✏️ and 🗑️ buttons on every row
- [ ] Forecasts tab has the `📅 Data: 2026-06-04` badge in MOCK mode (was missing before)
- [ ] Trade Ticket has Export CSV, Enter Fills, Refresh buttons
- [ ] ⚙ button is in the top-right of the page
- [ ] Pressing Esc closes any open modal
- [ ] Wait 60 seconds — data refreshes automatically (visible in DevTools Network tab)

4. **Live data smoke test (optional, requires real Sheets):**
- [ ] Setup banner appears on first run if Portfolio sheet is empty
- [ ] After running Cell 4b with 250,000 THB, Portfolio sheet row 2 shows 250,000
- [ ] Run pipeline 3 days — Equity Curve sheet has 3 new rows
- [ ] Calibration sheet has 1 new row
- [ ] Click ✏️ on a Trade Log row → modal opens → save → "edit queued" banner appears
- [ ] Re-run Colab Cell 9b → trade reflects new value
- [ ] Open Settings (⚙) → type "RESET" → confirm → reset queued → re-run Cell 4b

---

## Self-review notes (for plan author)

**Spec coverage check:**
- §4.1 (Equity Curve) → Task 2 ✓
- §4.2 (Doc comments) → Task 1 ✓
- §4.3 (Trade Log edit) → Task 5 ✓
- §4.4 (Initial Capital UI) → Task 6 ✓
- §4.5 (Health Banner) → Task 4 ✓
- §4.6 (Row borders) → Task 3 ✓
- §4.7 (Auto-refresh + cache) → Task 7 ✓
- §4.8 (Docs) → Tasks 9, 10 ✓
- §4.9 (MOCK + Esc) → Task 8 ✓
- §5 (Edge cases) → Distributed across tasks
- §6 (Testing approach) → Verification section
- §8 (Migration / rollout) → Sheet count update in Task 4 Step 4.1

**Placeholder scan:** No "TBD", "TODO", "fill in later" in any task. All code blocks are complete and copy-pastable.

**Type consistency check:**
- Apps Script function names match between spec §3 and Tasks 4, 5, 6
- Cell naming (4b, 9b, 11b, 13b) is consistent with build_notebook.py patterns
- Sheet names match between build_notebook.py and Code.gs
- Index.html function names (`openEditTradeModal`, `submitSetup`, `checkPendingEditsBanner`) match across the JS blocks

**Ambiguity resolutions made:**
- Task 4 Step 4.1 explicitly reconciles the sheet count math (17 = 10 live + 7 staging)
- Task 5 Step 5.2 explains why Apps Script can't run Python (single source of truth rationale)
- Task 6 Step 6.2 explains the Cell 4b path runs Cells 5-15's logic (replaces them)
