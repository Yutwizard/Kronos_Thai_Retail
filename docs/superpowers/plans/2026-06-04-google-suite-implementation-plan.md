# Google Suite Dashboard — Implementation Plan

**Date:** 2026-06-04
**Spec:** [2026-06-04-google-suite-dashboard-design.md](2026-06-04-google-suite-dashboard-design.md)
**Build order:** Phase 1 → 7 (each phase is a deployable checkpoint)
**Revision:** v3 — junior-developer complete; all review issues resolved

---

## How to read this plan

Every cell in the Colab notebook and every function in Code.gs / Index.html is written in
full. Copy the code blocks exactly. Notes labelled **← CRITICAL** must not be skipped.

---

## Critical Architectural Decision: JSON-Bridge Pattern

The existing `kth.trading.portfolio` and `kth.trading.trade_gen` modules read/write
`data/positions/paper_portfolio.json`. The new Colab runs against Google Sheets as the
source of truth.

```
Sheets → read → local Drive JSON → existing kth functions → local Drive JSON → Sheets
```

**Required:** `os.chdir(KTH_REPO)` in Cell 1 makes all `Path("data/...")` calls in kth
modules resolve against the mounted Drive instead of the ephemeral Colab filesystem.

**Correct cell order — non-negotiable:**
```
Cell 9  → Update Portfolio State    ← reads Sheets → rebuilds JSON → applies fills
Cell 10 → Generate Trade Ticket     ← reads updated JSON via generate_trade_ticket()
Cell 11 → Compute Metrics           ← reads updated JSON + adds missing metrics
```
`generate_trade_ticket()` calls `compute_metrics()` internally. Fills must be applied
before the ticket is generated so allocation band and position counts are current.

---

## Pre-Requisites

> ⚠️ **Set Colab runtime to GPU FIRST.**
> Cell 8 calls `KronosTH.from_pretrained(..., device='cuda')`. On CPU this crashes.
> Before opening the notebook: **Runtime > Change runtime type > T4 GPU.**

> ⚠️ **Know your Drive path.**
> Run this in a Colab cell before anything else to find your repo:
> ```python
> from google.colab import drive; drive.mount('/content/drive')
> import os; print(os.listdir('/content/drive/MyDrive/'))
> ```
> Common paths: `/content/drive/MyDrive/Kronos_Thai_Retail`

---

## Design System

Defined once at the top of `Index.html`. All components reference these — never use
ad-hoc colour names elsewhere.

### CSS variables and base styles

```css
<style>
:root {
  --green:           #34a853;
  --yellow:          #fbbc04;
  --red:             #ea4335;
  --dark-red:        #b31412;
  --blue:            #4285f4;
  --gray:            #80868b;
  --pnl-pos-bg:      #e6f4ea;
  --pnl-neg-bg:      #fce8e6;
  --bg:              #f1f3f4;
  --card:            #ffffff;
  --border:          #dadce0;
  --text:            #202124;
  --text-muted:      #5f6368;
  --font:            'Google Sans', Arial, sans-serif;
  --font-mono:       'Roboto Mono', monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font); background: var(--bg); color: var(--text); }

/* Status banners */
.banner { padding: 10px 16px; border-radius: 6px; margin-bottom: 12px; font-size: 0.9rem; }
.banner-green  { background: #e6f4ea; color: #137333; border-left: 4px solid var(--green); }
.banner-yellow { background: #fef7e0; color: #b06000; border-left: 4px solid var(--yellow); }
.banner-red    { background: #fce8e6; color: #c5221f; border-left: 4px solid var(--red); }
.banner-gray   { background: #f1f3f4; color: var(--text-muted); border-left: 4px solid var(--gray); }

/* Tab bar */
#tab-bar { display: flex; gap: 4px; background: var(--card);
           border-bottom: 1px solid var(--border); padding: 0 16px; }
.tab-btn { padding: 12px 16px; border: none; background: none; cursor: pointer;
           font-family: var(--font); font-size: 0.9rem; color: var(--text-muted);
           border-bottom: 3px solid transparent; }
.tab-btn.active { color: var(--blue); border-bottom-color: var(--blue); }

/* Content panels */
#content { padding: 16px; }
.panel { display: none; }
.panel.active { display: block; }

/* Cards */
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.card-primary { flex: 2; min-width: 200px; background: var(--card);
                border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.card { flex: 1; min-width: 120px; background: var(--card);
        border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.card-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;
              letter-spacing: 0.5px; margin-bottom: 6px; }
.card-value { font-size: 1.5rem; font-family: var(--font-mono); font-weight: 500; }
.card-primary .card-value { font-size: 2rem; }
.card-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

/* Tables */
.table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
th, td { padding: 8px 12px; border-bottom: 1px solid var(--border); text-align: left; }
th { background: #f8f9fa; font-weight: 500; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { background: #e8eaed; }
th.sorted-asc::after  { content: ' ▲'; font-size: 0.7rem; }
th.sorted-desc::after { content: ' ▼'; font-size: 0.7rem; }
td.num { font-family: var(--font-mono); text-align: right; }
tr.cancelled td { text-decoration: line-through; color: var(--gray); }
tr:hover { background: #f8f9fa; }

/* Badges */
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 0.75rem; font-weight: 500; }
.badge-green  { background: #e6f4ea; color: #137333; }
.badge-yellow { background: #fef7e0; color: #b06000; }
.badge-red    { background: #fce8e6; color: #c5221f; }
.badge-gray   { background: #f1f3f4; color: var(--gray); }

/* Regime badge (larger) */
.regime { display: inline-flex; align-items: center; gap: 8px;
          padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 1rem; }
.regime-BULL    { background: #e6f4ea; color: #137333; }
.regime-NEUTRAL { background: #fef7e0; color: #b06000; }
.regime-BEAR    { background: #fce8e6; color: #c5221f; }
.regime-EXIT    { background: #f4c7c3; color: #b31412; }

/* Sub-tabs (inside Forecasts tab) */
.sub-tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.sub-tab { padding: 6px 14px; border: 1px solid var(--border); border-radius: 16px;
           background: none; cursor: pointer; font-size: 0.85rem; }
.sub-tab.active { background: var(--blue); color: white; border-color: var(--blue); }

/* Spinner */
#spinner { position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%);
           font-size: 1.2rem; color: var(--text-muted); }

/* Empty state */
.empty-state { padding: 40px; text-align: center; color: var(--text-muted); }

/* Mobile */
@media (max-width: 600px) {
  .cards { flex-direction: column; }
  .card-primary, .card { flex: none; width: 100%; }
  .tab-btn { font-size: 0.75rem; padding: 8px 8px; }
}
</style>
```

### Number formatting helpers

```javascript
const fmt = {
  thb:    v => '฿' + Number(v).toLocaleString('th-TH',
                  {minimumFractionDigits:2, maximumFractionDigits:2}),
  thbM:   v => Math.abs(v) >= 1e6
                ? '฿' + (v/1e6).toFixed(2) + 'M'
                : '฿' + Number(v).toLocaleString('th-TH',
                    {minimumFractionDigits:0, maximumFractionDigits:0}),
  pct:    v => (v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%'),
  ratio:  v => (v == null ? '—' : Number(v).toFixed(2)),
  date:   v => {
    if (!v) return '—';
    // Use T12:00:00 to avoid UTC-midnight timezone shifting
    const d = new Date(String(v).length === 10 ? v + 'T12:00:00' : v);
    return d.toLocaleDateString('en-GB',
      {day:'2-digit', month:'short', year:'numeric'});
  },
  shares: v => Number(v).toLocaleString(),
};
```

---

## Deliverables

```
google_suite/
├── README.md
├── migrate_to_sheets.py
├── kronos_daily_pipeline.ipynb      (19 cells)
└── apps_script/
    ├── Code.gs
    └── Index.html
```

---

## Phase 1 — Spreadsheet + Apps Script skeleton

**Goal:** web app URL opens, shows a loading spinner, no JS errors.

### 1.1 Create the Google Spreadsheet (manual)

Create spreadsheet: **"Kronos-TH Portfolio"**. Add **14 tabs**. For each tab, paste the
comma-separated header string into **row 1, column A** of that sheet (paste as plain text,
not as a formula):

| Tab name | Row 1 headers |
|----------|--------------|
| `Portfolio` | `cash,initial_capital,mode,model_version,forecast_date` |
| `Equity Curve` | `date,equity,cash,invested` |
| `Positions` | `ticker,shares,avg_cost,entry_date,sector,current_price,pnl,pnl_pct,pct_to_stoploss` |
| `Trade Log` | `timestamp,ticker,action,shares,price,rationale,friction_cost,model_version,id,ref_id` |
| `Forecasts` | `date_updated,ticker,rank_score,exp_ret,band_width,confidence,net_return,p5,p50,p95,sector` |
| `Forecast History` | `date,ticker,predicted_direction,predicted_return,entry_close,actual_return,was_correct` |
| `Trade Ticket` | `ticker,action,shares,est_cost_thb,rationale,sector,confidence,filled_price,filled_shares,fill_timestamp` |
| `Risk Metrics` | `date,equity,cash,deployed_pct,trailing_sharpe_12w,max_drawdown_pct,mtd_pnl_pct,trade_win_rate,calmar_ratio,sortino_ratio,drawdown_velocity,allocation_band,allocation_pct,market_state,is_frozen,bootstrap_p_value,friction_ytd_pct,friction_ytd_thb` |
| `Pipeline Status` | `last_run_timestamp,status,duration_seconds,error_message,sheets_updated` |
| `Portfolio_staging` | *(same as Portfolio)* |
| `Positions_staging` | *(same as Positions)* |
| `Forecasts_staging` | *(same as Forecasts)* |
| `Trade Ticket_staging` | *(same as Trade Ticket)* |
| `Risk Metrics_staging` | *(same as Risk Metrics)* |

To split a header string into separate columns: paste into A1, then Data > Split text to
columns > Separator: comma.

### 1.2 `google_suite/apps_script/Code.gs` (complete file)

```javascript
// ── Entry point ───────────────────────────────────────────────────────────
function doGet() {
  return HtmlService
    .createHtmlOutputFromFile('Index')
    .setTitle('Kronos-TH Portfolio')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ── Row helper ─────────────────────────────────────────────────────────────
function _rowToObj(headers, row) {
  var obj = {};
  headers.forEach(function(h, i) {
    var v = row[i];
    if (v === '' || v === null || v === undefined) {
      obj[h] = null;
    } else if (v instanceof Date) {
      // Must check Date BEFORE Number — Number(new Date()) returns a large timestamp int
      obj[h] = Utilities.formatDate(v, 'Asia/Bangkok', 'yyyy-MM-dd');
    } else if (!isNaN(Number(v))) {
      obj[h] = Number(v);
    } else {
      obj[h] = v;
    }
  });
  return obj;
}

// ── Sheet readers ──────────────────────────────────────────────────────────
function _readSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  var data  = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];
  var headers = data[0];
  return data.slice(1).map(function(r) { return _rowToObj(headers, r); });
}

function _readSheetLimited(ss, name, maxRows) {
  var sheet   = ss.getSheetByName(name);
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  // Read only the tail — do NOT read the full sheet then slice (100KB cache limit)
  var startRow = Math.max(2, lastRow - maxRows + 1);
  var numRows  = lastRow - startRow + 1;
  var numCols  = sheet.getLastColumn();
  var headers  = sheet.getRange(1, 1, 1, numCols).getValues()[0];
  var values   = sheet.getRange(startRow, 1, numRows, numCols).getValues();
  return values.map(function(r) { return _rowToObj(headers, r); });
}

// ── CSV helper ─────────────────────────────────────────────────────────────
function _csvField(v) {
  var s = (v == null) ? '' : String(v);
  return (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0)
    ? '"' + s.replace(/"/g, '""') + '"'
    : s;
}

// ── Main data function ─────────────────────────────────────────────────────
function getAllData() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var cache = CacheService.getScriptCache();
  var hit   = cache.get('all_data');
  if (hit) return JSON.parse(hit);

  var pipelineRows = _readSheet(ss, 'Pipeline Status');
  var data = {
    pipeline:        pipelineRows.length ? pipelineRows[0] : null,  // single object, not array
    portfolio:       _readSheet(ss, 'Portfolio'),
    equityCurve:     _readSheetLimited(ss, 'Equity Curve',      90),
    positions:       _readSheet(ss, 'Positions'),
    tradeLog:        _readSheetLimited(ss, 'Trade Log',        200),
    forecasts:       _readSheet(ss, 'Forecasts'),
    forecastHistory: _readSheetLimited(ss, 'Forecast History', 180),
    ticket:          _readSheet(ss, 'Trade Ticket'),
    riskMetrics:     _readSheetLimited(ss, 'Risk Metrics',     365),
  };

  var json = JSON.stringify(data);
  if (json.length < 100000) cache.put('all_data', json, 300);  // 5-min TTL, skip if >100KB
  return data;
}

function refreshAllData() {
  CacheService.getScriptCache().remove('all_data');
  return getAllData();
}

// ── CSV export ─────────────────────────────────────────────────────────────
function getExportCsv() {
  var ss      = SpreadsheetApp.getActiveSpreadsheet();
  var status  = _readSheet(ss, 'Pipeline Status');
  var lastRun = (status.length && status[0].last_run_timestamp)
                ? new Date(status[0].last_run_timestamp) : null;
  var hoursAgo = lastRun ? (Date.now() - lastRun.getTime()) / 3600000 : 999;
  var warning  = hoursAgo > 24
    ? '# WARNING: Pipeline last ran ' + Math.round(hoursAgo) + ' hours ago. Data may be stale.\n'
    : '';
  var ticket = _readSheet(ss, 'Trade Ticket');
  var header = '# Execute at next market open (Bangkok time, UTC+7).\n'
             + '# Prices are previous close estimates.\n'
             + '# After execution: enter fills in the Trade Ticket sheet cols 8-10.\n';
  var rows = ticket.map(function(r) {
    return [r.ticker, r.action, r.shares, r.est_cost_thb, _csvField(r.rationale)].join(',');
  });
  return warning + header + 'ticker,action,shares,est_cost_thb,rationale\n' + rows.join('\n');
}
```

### 1.3 `google_suite/apps_script/Index.html` (complete file — Phase 1 shell)

Create this file in Apps Script via **File > New > HTML file**, name it `Index`.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kronos-TH Portfolio</title>

<!-- ── Design system CSS (paste full block from Design System section above) ── -->
<style>
  /* PASTE THE FULL CSS FROM THE DESIGN SYSTEM SECTION HERE */
</style>
</head>
<body>

<!-- Pipeline status banner — always visible at top -->
<div id="status-banner"></div>

<!-- Tab navigation -->
<nav id="tab-bar">
  <button class="tab-btn active" onclick="switchTab('dashboard')">Dashboard</button>
  <button class="tab-btn"        onclick="switchTab('positions')">Positions</button>
  <button class="tab-btn"        onclick="switchTab('tradelog')">Trade Log</button>
  <button class="tab-btn"        onclick="switchTab('forecasts')">Forecasts</button>
  <button class="tab-btn"        onclick="switchTab('ticket')">Trade Ticket</button>
</nav>

<!-- Tab content -->
<main id="content">
  <div id="panel-dashboard" class="panel active"></div>
  <div id="panel-positions" class="panel"></div>
  <div id="panel-tradelog"  class="panel"></div>
  <div id="panel-forecasts" class="panel"></div>
  <div id="panel-ticket"    class="panel"></div>
</main>

<!-- Loading spinner -->
<div id="spinner">⏳ Loading…</div>

<!-- Google Charts -->
<script src="https://www.gstatic.com/charts/loader.js"></script>

<script>
// ── Number formatting ──────────────────────────────────────────────────────
// PASTE THE fmt OBJECT FROM THE DESIGN SYSTEM SECTION HERE

// ── Mock data for Phase 2 development (remove after Phase 5) ──────────────
var MOCK = {
  pipeline:    { status: 'completed', last_run_timestamp: '2026-06-04T08:15:00', error_message: null },
  portfolio:   [{ cash: 350000, initial_capital: 500000, forecast_date: '2026-06-04' }],
  equityCurve: [
    { date: '2026-05-01', equity: 500000, cash: 500000, invested: 0 },
    { date: '2026-05-15', equity: 511200, cash: 355000, invested: 156200 },
    { date: '2026-06-04', equity: 523400, cash: 350000, invested: 173400 },
  ],
  positions:   [
    { ticker: 'PTT.BK', shares: 1000, avg_cost: 33.50, entry_date: '2026-05-15',
      sector: 'Energy', current_price: 35.00, pnl: 1500, pnl_pct: 0.0448, pct_to_stoploss: 0.1448 },
    { ticker: 'AOT.BK', shares: 500, avg_cost: 58.00, entry_date: '2026-05-20',
      sector: 'Transport', current_price: 56.50, pnl: -750, pnl_pct: -0.0259, pct_to_stoploss: 0.0741 },
  ],
  tradeLog: [
    { timestamp: '2026-05-15', ticker: 'PTT.BK', action: 'buy', shares: 1000,
      price: 33.50, rationale: 'rank#1 net_ret=+3.2%', id: '20260515_PTT.BK_buy_a1b2', ref_id: null },
    { timestamp: '2026-05-20', ticker: 'AOT.BK', action: 'buy', shares: 500,
      price: 58.00, rationale: 'rank#2 net_ret=+2.1%', id: '20260520_AOT.BK_buy_c3d4', ref_id: null },
  ],
  forecasts: [
    { ticker: 'PTT.BK',    rank_score: 3.2, exp_ret: 0.045, band_width: 0.08,
      confidence: 'green',  net_return: 0.039, p50: 36.75, sector: 'Energy' },
    { ticker: 'ADVANC.BK', rank_score: 2.1, exp_ret: 0.031, band_width: 0.18,
      confidence: 'yellow', net_return: 0.025, p50: 225.0, sector: 'Telecom' },
    { ticker: 'KBANK.BK',  rank_score: 0.8, exp_ret: 0.012, band_width: 0.35,
      confidence: 'red',    net_return: 0.006, p50: 142.0, sector: 'Finance' },
  ],
  forecastHistory: [
    { date: '2026-06-03', ticker: 'PTT.BK', predicted_direction: 'up',
      predicted_return: 0.032, entry_close: 34.00, actual_return: 0.029, was_correct: 1 },
    { date: '2026-06-04', ticker: 'PTT.BK', predicted_direction: 'up',
      predicted_return: 0.045, entry_close: 34.99, actual_return: null, was_correct: null },
  ],
  ticket: [
    { ticker: 'ADVANC.BK', action: 'buy', shares: 500, est_cost_thb: 113000,
      rationale: 'rank#1 net_ret=+2.5%', sector: 'Telecom', confidence: 'yellow',
      filled_price: null, filled_shares: null, fill_timestamp: null },
  ],
  riskMetrics: [
    { date: '2026-06-04', trailing_sharpe_12w: 1.42, max_drawdown_pct: -0.08,
      allocation_band: 'BULL', allocation_pct: 0.15, is_frozen: 0,
      mtd_pnl_pct: 0.047, friction_ytd_pct: 0.008, calmar_ratio: 3.25,
      sortino_ratio: 1.85, drawdown_velocity: 0.002 },
  ],
};

// ── Tab switching ──────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.getElementById('panel-' + name).classList.add('active');
  // Find button by its onclick text matching the tab name
  document.querySelectorAll('.tab-btn').forEach(function(b) {
    if (b.getAttribute('onclick').indexOf("'" + name + "'") >= 0) b.classList.add('active');
  });
}

// ── Spinner ────────────────────────────────────────────────────────────────
function showSpinner() { document.getElementById('spinner').style.display = 'block'; }
function hideSpinner() { document.getElementById('spinner').style.display = 'none'; }

// ── Empty state ────────────────────────────────────────────────────────────
var EMPTY_STATES = {
  dashboard:  'Run the Colab pipeline to see your portfolio.',
  positions:  'No open positions. Check the <strong>Trade Ticket</strong> tab for today\'s recommendations.',
  tradelog:   'No trades recorded yet. Execute your first Trade Ticket to start the audit trail.',
  forecasts:  'No forecasts available. Run the pipeline first.',
  ticket:     'No recommendations today — either the pipeline hasn\'t run, or no signals passed the 3-filter rule.',
};
function showEmptyState(panelName) {
  document.getElementById('panel-' + panelName).innerHTML =
    '<div class="empty-state">' + EMPTY_STATES[panelName] + '</div>';
}

// ── Error handler ──────────────────────────────────────────────────────────
function showError(err) {
  hideSpinner();
  document.getElementById('status-banner').innerHTML =
    '<div class="banner banner-red">⚠️ App error: ' + String(err) + '</div>';
}

// ── Render all tabs ────────────────────────────────────────────────────────
function renderAll(d) {
  renderPipelineStatus(d.pipeline);
  renderDashboard(d.portfolio, d.equityCurve, d.riskMetrics, d.ticket);
  renderPositions(d.positions, d.riskMetrics, d.portfolio);
  renderTradeLog(d.tradeLog);
  renderForecasts(d.forecasts, d.forecastHistory);
  renderTicket(d.ticket);
}

// ── Stub render functions (Phase 1 only — replace in Phase 2) ─────────────
function renderPipelineStatus(p)           { /* Phase 2.1 */ }
function renderDashboard(pf, eq, rm, tk)   { /* Phase 2.2 */ }
function renderPositions(pos, rm, pf)      { /* Phase 2.3 */ }
function renderTradeLog(tl)                { /* Phase 2.4 */ }
function renderForecasts(fc, fh)           { /* Phase 2.5 */ }
function renderTicket(tk)                  { /* Phase 2.6 */ }

// ── Sortable table helper (used by Positions, Trade Log, Forecasts) ────────
function _makeSortable(tableId) {
  var table = document.getElementById(tableId);
  if (!table) return;
  var headers = table.querySelectorAll('th');
  var sortCol = -1; var sortAsc = true;
  headers.forEach(function(th, colIdx) {
    th.addEventListener('click', function() {
      var rows = Array.from(table.querySelectorAll('tbody tr'));
      sortAsc = (sortCol === colIdx) ? !sortAsc : true;
      sortCol = colIdx;
      headers.forEach(function(h) { h.classList.remove('sorted-asc','sorted-desc'); });
      th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
      rows.sort(function(a, b) {
        var av = a.cells[colIdx] ? a.cells[colIdx].dataset.val || a.cells[colIdx].textContent : '';
        var bv = b.cells[colIdx] ? b.cells[colIdx].dataset.val || b.cells[colIdx].textContent : '';
        var an = parseFloat(av), bn = parseFloat(bv);
        var cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
        return sortAsc ? cmp : -cmp;
      });
      var tbody = table.querySelector('tbody');
      rows.forEach(function(r) { tbody.appendChild(r); });
    });
  });
}

// ── Bootstrap: load Charts then fetch data ─────────────────────────────────
google.charts.load('current', {packages: ['corechart']});
google.charts.setOnLoadCallback(function() {
  showSpinner();
  // Development: use MOCK data. Production: use google.script.run
  // To switch to production: comment the two lines below and uncomment google.script.run block
  hideSpinner();
  renderAll(MOCK);

  /*
  google.script.run
    .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); })
    .withFailureHandler(showError)
    .getAllData();
  */
});

// ── Refresh button handler ─────────────────────────────────────────────────
function refreshData() {
  showSpinner();
  google.script.run
    .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); })
    .withFailureHandler(showError)
    .refreshAllData();
}

// ── Export CSV button handler ──────────────────────────────────────────────
function exportCsv() {
  google.script.run.withSuccessHandler(function(csv) {
    var a   = document.createElement('a');
    a.href  = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = 'kronos_ticket.csv';
    a.click();
  }).getExportCsv();
}
// Note: using data: URI instead of URL.createObjectURL() for iOS Safari compatibility.

</script>
</body>
</html>
```

### 1.4 Deploy

1. From within the spreadsheet: **Extensions > Apps Script**
2. Paste `Code.gs` content (replace default `myFunction` stub)
3. Add `Index.html`: **File > New > HTML file**, name it `Index`, paste content
4. Confirm V8 runtime: **Project Settings > Runtime version: V8**
5. **Deploy > New deployment > Web app**
   - Execute as: **Me**
   - Who has access: **Only myself**
6. Copy the web app URL — this is your dashboard URL

> ⚠️ Every future edit to `Code.gs` requires: **Deploy > Manage deployments > Edit (pencil icon) > Version: New version > Deploy**. The URL stays the same.

**Phase 1 acceptance test:**
- Web app URL opens, shows spinner then empty page (no JS errors in DevTools console)
- `getAllData()` run from Apps Script editor (**Run > Run function > getAllData**) completes without error
- `refreshAllData()` run from editor completes and returns same structure

---

## Phase 2 — Complete frontend (Index.html render functions)

**Goal:** all 5 tabs render correctly against MOCK data.
Replace the stub `/* Phase 2.x */` functions one by one. Test each against MOCK before moving to the next.

**To develop in isolation:** keep `renderAll(MOCK)` active (not `google.script.run`). Only switch to `google.script.run` after Phase 5 has run at least once.

### 2.1 Replace `renderPipelineStatus`

```javascript
function renderPipelineStatus(pipeline) {
  var el = document.getElementById('status-banner');
  if (!pipeline) {
    el.innerHTML = '<div class="banner banner-gray">No data yet. Run the Colab pipeline first.</div>';
    return;
  }
  var hoursAgo = (Date.now() - new Date(pipeline.last_run_timestamp).getTime()) / 3600000;
  var html;
  if (pipeline.status === 'running') {
    html = '<div class="banner banner-yellow">⏳ Pipeline running… please wait and refresh in a few minutes.</div>';
  } else if (pipeline.status === 'failed') {
    html = '<div class="banner banner-red">❌ Pipeline failed: '
         + (pipeline.error_message || 'unknown error') + ' &nbsp;('
         + fmt.date(pipeline.last_run_timestamp) + ')</div>';
  } else if (hoursAgo > 24) {
    html = '<div class="banner banner-yellow">⚠️ Pipeline last ran '
         + Math.round(hoursAgo) + ' hours ago. Data may be stale. Run the pipeline to refresh.</div>';
  } else {
    html = '<div class="banner banner-green">✅ Last updated: '
         + pipeline.last_run_timestamp.replace('T', ' ').substring(0, 16) + ' BKK</div>';
  }
  el.innerHTML = html;
}
```

### 2.2 Replace `renderDashboard`

```javascript
function renderDashboard(portfolio, equityCurve, riskMetrics, ticket) {
  var panel = document.getElementById('panel-dashboard');
  if (!portfolio.length) { showEmptyState('dashboard'); return; }

  var pf     = portfolio[0];
  var lastRm = riskMetrics.length ? riskMetrics[riskMetrics.length - 1] : null;
  var equity = (pf.cash || 0) + (lastRm ? (lastRm.equity - lastRm.cash) : 0);
  // Use equity from Risk Metrics if available, otherwise approximate
  if (lastRm && lastRm.equity) equity = lastRm.equity;

  var confirmed = ticket ? ticket.filter(function(r) { return r.filled_price !== null; }).length : 0;
  var pending   = ticket ? ticket.filter(function(r) { return r.filled_price === null; }).length : 0;
  var fillsHtml = pending > 0
    ? '<span style="color:var(--yellow)">⚠ ' + confirmed + ' confirmed / ' + pending + ' pending fills</span>'
    : (confirmed > 0 ? '<span style="color:var(--green)">✓ All fills confirmed</span>' : '');

  // Regime badge
  var band = lastRm ? lastRm.allocation_band : 'NEUTRAL';
  var pctPerPos = lastRm ? (lastRm.allocation_pct * 100).toFixed(0) + '% per position' : '';
  var regimeHtml = '<span class="regime regime-' + band + '">' + band + '</span>'
                 + ' <span style="font-size:0.85rem;color:var(--text-muted)">' + pctPerPos + '</span>';

  panel.innerHTML =
    '<div class="cards">' +
      '<div class="card-primary">' +
        '<div class="card-label">Total Capital</div>' +
        '<div class="card-value">' + fmt.thbM(equity) + '</div>' +
        '<div class="card-sub">Cash: ' + fmt.thb(pf.cash) + ' &nbsp;|&nbsp; ' + fillsHtml + '</div>' +
      '</div>' +
      _heroCard('P&L MTD',    lastRm ? fmt.pct(lastRm.mtd_pnl_pct) : '—',
                lastRm && lastRm.mtd_pnl_pct > 0 ? 'var(--pnl-pos-bg)' : lastRm && lastRm.mtd_pnl_pct < 0 ? 'var(--pnl-neg-bg)' : '') +
      _heroCard('Sharpe 12w', lastRm ? fmt.ratio(lastRm.trailing_sharpe_12w) : '—', '') +
      _heroCard('Max DD',     lastRm ? fmt.pct(lastRm.max_drawdown_pct) : '—',
                lastRm && lastRm.max_drawdown_pct < -0.15 ? 'var(--pnl-neg-bg)' : '') +
      _heroCard('Friction YTD', lastRm ? fmt.pct(lastRm.friction_ytd_pct) : '—', '') +
    '</div>' +
    '<div style="margin:12px 0">' + regimeHtml + '</div>' +
    '<p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:16px">' +
      'Backtest 2022–2024: CAGR +31.4%, Sharpe 1.40, Alpha vs. EW +29.9%/yr. ' +
      'Model is trend-following; alpha was lower in the 2023 bull market.' +
    '</p>' +
    '<div id="equity-chart" style="min-height:280px"></div>';

  // Draw chart after DOM is updated
  setTimeout(function() { _drawEquityCurve(equityCurve, pf.initial_capital); }, 0);
}

function _heroCard(label, value, bgColor) {
  return '<div class="card"' + (bgColor ? ' style="background:' + bgColor + '"' : '') + '>' +
    '<div class="card-label">' + label + '</div>' +
    '<div class="card-value">' + value + '</div>' +
    '</div>';
}

function _drawEquityCurve(equityCurve, initialCapital) {
  if (!equityCurve.length) return;
  var dt = new google.visualization.DataTable();
  dt.addColumn('string', 'Date');
  dt.addColumn('number', 'Portfolio');
  dt.addColumn('number', 'Initial Capital');
  equityCurve.forEach(function(r) {
    dt.addRow([fmt.date(r.date), r.equity, initialCapital]);
  });
  var chart = new google.visualization.LineChart(
    document.getElementById('equity-chart'));
  chart.draw(dt, {
    height: 280,
    legend: { position: 'bottom' },
    colors: ['#4285f4', '#dadce0'],
    series: { 1: { lineDashStyle: [4, 4] } },
    vAxis:  { format: '฿#,##0', gridlines: { count: 4 } },
    hAxis:  { slantedText: true, slantedTextAngle: 30 },
    chartArea: { width: '88%', height: '75%' },
  });
}
```

### 2.3 Replace `renderPositions`

```javascript
function renderPositions(positions, riskMetrics, portfolio) {
  var panel = document.getElementById('panel-positions');
  var lastRm = riskMetrics.length ? riskMetrics[riskMetrics.length - 1] : null;
  var pf     = portfolio.length ? portfolio[0] : null;

  var frozenHtml = (lastRm && lastRm.is_frozen)
    ? '<div class="banner banner-red">🔒 Portfolio frozen — drawdown limit reached. ' +
      'Liquidate all positions and re-run Cell 4 to resume.</div>'
    : '';
  var asOf = pf ? '<p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:8px">' +
                  'Positions as of ' + fmt.date(pf.forecast_date) + '</p>' : '';

  if (!positions.length) {
    panel.innerHTML = frozenHtml + asOf + '<div class="empty-state">' + EMPTY_STATES.positions + '</div>';
    return;
  }

  var rows = positions.map(function(p) {
    var pctStyle = p.pnl_pct > 0 ? 'color:var(--green)' : p.pnl_pct < 0 ? 'color:var(--red)' : '';
    var stopStyle = p.pct_to_stoploss < 0.03 ? 'background:var(--pnl-neg-bg);color:var(--red)' : '';
    return '<tr>' +
      _td(p.ticker) +
      _tdNum(fmt.shares(p.shares), p.shares) +
      _tdNum(fmt.thb(p.avg_cost), p.avg_cost) +
      _td(fmt.date(p.entry_date)) +
      _td(p.sector || '—') +
      _tdNum(fmt.thb(p.current_price), p.current_price) +
      '<td class="num" style="' + pctStyle + '" data-val="' + p.pnl_pct + '">' + fmt.pct(p.pnl_pct) + '</td>' +
      '<td class="num" style="' + stopStyle + '" data-val="' + p.pct_to_stoploss + '">' + fmt.pct(p.pct_to_stoploss) + '</td>' +
      '</tr>';
  }).join('');

  panel.innerHTML = frozenHtml + asOf +
    '<div class="table-wrapper">' +
    '<table id="tbl-positions">' +
    '<thead><tr>' +
      '<th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Entry Date</th>' +
      '<th>Sector</th><th>Current Price</th><th>P&L %</th><th>% to Stop</th>' +
    '</tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table></div>';
  _makeSortable('tbl-positions');
}
function _td(v)         { return '<td>' + (v != null ? v : '—') + '</td>'; }
function _tdNum(disp, raw) { return '<td class="num" data-val="' + raw + '">' + disp + '</td>'; }
```

### 2.4 Replace `renderTradeLog`

```javascript
function renderTradeLog(tradeLog) {
  var panel = document.getElementById('panel-tradelog');
  if (!tradeLog.length) { showEmptyState('tradelog'); return; }

  // Collect IDs that have been cancelled
  var cancelledIds = {};
  tradeLog.forEach(function(r) {
    if (r.action === 'CANCEL' && r.ref_id) cancelledIds[r.ref_id] = true;
  });

  var rows = tradeLog.map(function(r) {
    var isCancel    = (r.action === 'CANCEL');
    var isCancelled = cancelledIds[r.id];
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

  panel.innerHTML =
    '<div class="table-wrapper">' +
    '<table id="tbl-tradelog">' +
    '<thead><tr>' +
      '<th>Date</th><th>Ticker</th><th>Action</th>' +
      '<th>Shares</th><th>Price</th><th>Rationale</th>' +
    '</tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '</table></div>' +
    '<p style="font-size:0.8rem;color:var(--text-muted);margin-top:8px">' +
    '⚠ CANCEL rows only update this display — also correct the Portfolio sheet cash/positions manually.' +
    '</p>';
  _makeSortable('tbl-tradelog');
}
```

### 2.5 Replace `renderForecasts`

```javascript
function renderForecasts(forecasts, forecastHistory) {
  var panel = document.getElementById('panel-forecasts');
  if (!forecasts.length) { showEmptyState('forecasts'); return; }

  // Confidence badge
  function confBadge(c) {
    var cls = c === 'green' ? 'badge-green' : c === 'yellow' ? 'badge-yellow' : 'badge-red';
    var tip = c === 'green' ? 'band_width ≤ 10%' : c === 'yellow' ? 'band_width 10–30%' : 'band_width > 30%';
    return '<span class="badge ' + cls + '" title="' + tip + '">' + c + '</span>';
  }

  var fcRows = forecasts.map(function(r) {
    return '<tr>' +
      _td(r.ticker) +
      _tdNum(fmt.ratio(r.rank_score), r.rank_score) +
      _tdNum(fmt.pct(r.exp_ret), r.exp_ret) +
      '<td>' + confBadge(r.confidence) + '</td>' +
      _tdNum(fmt.pct(r.net_return), r.net_return) +
      _tdNum(r.p50 != null ? fmt.thb(r.p50) : '—', r.p50) +
      _td(r.sector) +
    '</tr>';
  }).join('');

  // Forecast History accuracy summary
  var resolved = (forecastHistory || []).filter(function(r) { return r.actual_return !== null; });
  var correct  = resolved.filter(function(r) { return r.was_correct === 1; }).length;
  var accuracyText = resolved.length
    ? correct + ' of ' + resolved.length + ' correct (' +
      Math.round(correct / resolved.length * 100) + '%)'
    : 'No resolved predictions yet.';

  var fhRows = (forecastHistory || []).map(function(r) {
    var correctCell = r.was_correct === 1
      ? '<td><span class="badge badge-green">✓ correct</span></td>'
      : r.was_correct === 0
        ? '<td><span class="badge badge-red">✗ wrong</span></td>'
        : '<td><span class="badge badge-gray">pending</span></td>';
    return '<tr>' +
      _td(fmt.date(r.date)) + _td(r.ticker) + _td(r.predicted_direction) +
      _tdNum(fmt.pct(r.predicted_return), r.predicted_return) +
      _tdNum(r.actual_return != null ? fmt.pct(r.actual_return) : '—', r.actual_return) +
      correctCell + '</tr>';
  }).join('');

  panel.innerHTML =
    '<div class="sub-tabs">' +
      '<button class="sub-tab active" id="st-fc"  onclick="showSubTab(\'fc\')">Forecasts</button>' +
      '<button class="sub-tab"        id="st-fh"  onclick="showSubTab(\'fh\')">Accuracy History</button>' +
    '</div>' +
    '<div id="sub-fc">' +
      '<div class="table-wrapper">' +
      '<table id="tbl-forecasts">' +
      '<thead><tr>' +
        '<th>Ticker</th>' +
        '<th title="Expected return ÷ uncertainty band">Rank Score</th>' +
        '<th title="Expected 20-day return">Exp Return</th>' +
        '<th title="Band width: green ≤10%, yellow 10-30%, red >30%">Confidence</th>' +
        '<th title="Expected return minus round-trip friction">Net Return</th>' +
        '<th title="Median (p50) price forecast">P50 Price</th>' +
        '<th>Sector</th>' +
      '</tr></thead>' +
      '<tbody>' + fcRows + '</tbody>' +
      '</table></div>' +
    '</div>' +
    '<div id="sub-fh" hidden>' +
      '<p style="margin-bottom:8px;font-size:0.9rem"><strong>Accuracy: </strong>' + accuracyText + '</p>' +
      '<div class="table-wrapper">' +
      '<table id="tbl-fh">' +
      '<thead><tr>' +
        '<th>Date</th><th>Ticker</th><th>Direction</th>' +
        '<th>Predicted Return</th><th>Actual Return</th><th>Result</th>' +
      '</tr></thead>' +
      '<tbody>' + fhRows + '</tbody>' +
      '</table></div>' +
    '</div>';

  _makeSortable('tbl-forecasts');
  _makeSortable('tbl-fh');
}

function showSubTab(name) {
  ['fc','fh'].forEach(function(n) {
    document.getElementById('sub-' + n).hidden = (n !== name);
    var btn = document.getElementById('st-' + n);
    if (btn) btn.classList.toggle('active', n === name);
  });
}
```

### 2.6 Replace `renderTicket`

```javascript
function renderTicket(ticket) {
  var panel  = document.getElementById('panel-ticket');
  var banner = '<div id="ticket-action-banner"></div>';

  if (!ticket || !ticket.length) {
    panel.innerHTML = banner + '<div class="empty-state">' + EMPTY_STATES.ticket + '</div>';
    return;
  }

  var confirmed = ticket.filter(function(r) { return r.filled_price !== null; }).length;
  var pending   = ticket.filter(function(r) { return r.filled_price === null; }).length;
  var actionBanner;
  if (confirmed === 0 && pending > 0) {
    actionBanner = '<div class="banner banner-yellow">' +
      '→ <strong>Step 1:</strong> Click "Export CSV" and place these orders at your broker. &nbsp;' +
      '<strong>Step 2:</strong> After orders fill, open the Trade Ticket sheet and enter ' +
      'actual fill prices in columns 8-10 (filled_price, filled_shares, fill_timestamp).</div>';
  } else if (confirmed > 0 && pending > 0) {
    actionBanner = '<div class="banner banner-green">' +
      '✓ ' + confirmed + ' fills confirmed. ' + pending + ' still pending — enter fills in the sheet.</div>';
  } else if (confirmed > 0 && pending === 0) {
    actionBanner = '<div class="banner banner-green">' +
      '✓ All ' + confirmed + ' fills recorded. Portfolio updated on next pipeline run.</div>';
  } else {
    actionBanner = '';
  }

  // Check for T+2 warning
  var hasExits = ticket.some(function(r) { return r.action === 'sell'; });
  var hasBuys  = ticket.some(function(r) { return r.action === 'buy'; });
  var t2Html   = (hasExits && hasBuys)
    ? '<div class="banner banner-yellow">⚠ T+2: exit proceeds settle in 2 business days. ' +
      'Today\'s buys draw from existing cash only.</div>'
    : '';

  var rows = ticket.map(function(r) {
    var fillStatus = r.filled_price !== null
      ? '<span style="color:var(--green)">✓ ' + fmt.thb(r.filled_price) + '</span>'
      : '<span style="color:var(--gray)">pending</span>';
    return '<tr>' +
      _td(r.ticker) +
      '<td><span class="badge ' + (r.action === 'buy' ? 'badge-green' : 'badge-red') + '">' + r.action + '</span></td>' +
      _tdNum(fmt.shares(r.shares), r.shares) +
      _tdNum(fmt.thb(r.est_cost_thb), r.est_cost_thb) +
      _td(r.sector) +
      '<td>' + (r.confidence ? '<span class="badge badge-' + r.confidence + '">' + r.confidence + '</span>' : '—') + '</td>' +
      '<td>' + fillStatus + '</td>' +
      _td(r.rationale) +
    '</tr>';
  }).join('');

  panel.innerHTML = actionBanner + t2Html +
    '<button onclick="exportCsv()" style="margin-bottom:12px;padding:8px 16px;' +
    'background:var(--blue);color:white;border:none;border-radius:4px;cursor:pointer">' +
    '⬇ Export CSV</button>' +
    '<button onclick="refreshData()" style="margin:0 0 12px 8px;padding:8px 16px;' +
    'background:none;color:var(--blue);border:1px solid var(--blue);border-radius:4px;cursor:pointer">' +
    '↻ Refresh</button>' +
    '<p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:12px">' +
    'Execute at next market open (Bangkok time). Prices are previous close estimates.</p>' +
    '<div class="table-wrapper">' +
    '<table id="tbl-ticket"><thead><tr>' +
      '<th>Ticker</th><th>Action</th><th>Shares</th><th>Est. Cost (THB)</th>' +
      '<th>Sector</th><th>Confidence</th><th>Fill Status</th><th>Rationale</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  _makeSortable('tbl-ticket');
}
```

**Switch to live data (do this after Phase 5 runs at least once):**
In the bootstrap block, comment out `renderAll(MOCK)` and uncomment the `google.script.run` block.

**Phase 2 acceptance test:**
- All 5 tabs render using MOCK data — no JS errors
- Pipeline banner shows green/yellow/red correctly for each MOCK status value
- Equity curve shows `04 Jun 2026` on X-axis (not a timestamp number)
- Positions table is sortable by clicking any column header
- Trade Log shows CANCEL rows strikethrough; CANCEL entry shows `↩ cancels {ref_id}`
- Forecasts confidence badges show green/yellow/red correctly
- Forecast History sub-tab toggle works
- Trade Ticket shows action banner (yellow "pending" state with MOCK)
- Export CSV button produces `kronos_ticket.csv` with correct columns
- Mobile: hero cards stack vertically at < 600px width (test with DevTools)

---

## Phase 3 — Colab cells 1–6 (setup and fills)

**Variable outputs from this phase used by later cells:**

| Variable | Set in | Used in |
|----------|--------|---------|
| `KTH_REPO` | Cell 1 | Cell 1, Cell 4 |
| `SPREADSHEET_ID` | Cell 2 | Cell 3 |
| `LINE_TOKEN` | Cell 2 | Cell 12, Cell 18 |
| `INITIAL_CAPITAL` | Cell 2 | Cell 4, Cell 11 |
| `sh` (spreadsheet) | Cell 3 | All cells that read/write Sheets |
| `status_ws` | Cell 5 | Cell 5, Cell 12, Cell 17 |
| `pipeline_start` | Cell 5 | Cell 17 |
| `fills` | Cell 6 | Cell 9 |

### Cell 1 — Mount Drive & Install

```python
from google.colab import drive
drive.mount('/content/drive')

import os, subprocess, sys

KTH_REPO = '/content/drive/MyDrive/Kronos_Thai_Retail'  # ← CHANGE IF YOUR PATH IS DIFFERENT
os.chdir(KTH_REPO)  # CRITICAL: makes Path("data/...") in kth modules resolve to Drive

print("Working directory:", os.getcwd())
print("Contents:", os.listdir('.'))  # should show kth/, data/, scripts/, etc.

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
                       'gspread', 'google-auth', 'pandas', 'yfinance'])
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-e', KTH_REPO])
print("All dependencies installed.")
```

### Cell 2 — Secrets & Parameters

```python
from google.colab import userdata

SPREADSHEET_ID = userdata.get('KRONOS_SPREADSHEET_ID')
LINE_TOKEN     = userdata.get('LINE_NOTIFY_TOKEN')   # optional — can be None

if not SPREADSHEET_ID:
    raise ValueError(
        "KRONOS_SPREADSHEET_ID not found in Colab Secrets.\n"
        "Click the key icon in the left sidebar → Add new secret."
    )

INITIAL_CAPITAL = 500_000.0   # ← CHANGE THIS to your starting capital in THB
print(f"Spreadsheet ID: {SPREADSHEET_ID[:8]}...")
print(f"Initial capital: ฿{INITIAL_CAPITAL:,.0f}")
print(f"LINE Notify: {'configured' if LINE_TOKEN else 'not configured (optional)'}")
```

### Cell 3 — Authenticate & Open Spreadsheet

```python
from google.colab import auth
auth.authenticate_user()   # opens a Google OAuth popup — click through and allow

from google.auth import default
import gspread

creds, _ = default()
gc = gspread.Client(auth=creds)   # gspread >= 5.x  — do NOT call gc.login()
sh = gc.open_by_key(SPREADSHEET_ID)
print("Connected to spreadsheet:", sh.title)
print("Sheets found:", [ws.title for ws in sh.worksheets()])
```

### Cell 4 — Initialize Portfolio if Empty

```python
from datetime import date
from kth.trading.portfolio import MODEL_VERSION   # import MODEL_VERSION only

portfolio_ws = sh.worksheet('Portfolio')
rows = portfolio_ws.get_all_values()

if len(rows) <= 1:   # header only or completely empty
    portfolio_ws.append_row([
        INITIAL_CAPITAL,      # cash
        INITIAL_CAPITAL,      # initial_capital
        'paper',              # mode
        MODEL_VERSION,        # model_version (e.g. "Kronos-small-zero-shot")
        str(date.today()),    # forecast_date
    ])
    print(f"First run: portfolio initialised at ฿{INITIAL_CAPITAL:,.0f}")
else:
    print(f"Portfolio already initialised: ฿{float(rows[1][0]):,.0f} cash")
```

### Cell 5 — Set Pipeline Status: Running

```python
import time
from datetime import datetime

def _set_pipeline_status(ws, status, error_msg='', sheets_updated='', duration=''):
    """Write Pipeline Status in one atomic API call."""
    ws.update('A1:E2', [
        ['last_run_timestamp', 'status', 'duration_seconds', 'error_message', 'sheets_updated'],
        [datetime.now().isoformat(), status, str(duration), str(error_msg), str(sheets_updated)],
    ])

status_ws = sh.worksheet('Pipeline Status')
_set_pipeline_status(status_ws, 'running')
pipeline_start = time.time()
print("Pipeline started at", datetime.now().strftime("%H:%M:%S BKK"))
```

### Cell 6 — Read Prior-Day Fills

```python
ticket_ws = sh.worksheet('Trade Ticket')
rows = ticket_ws.get_all_values()
headers = rows[0] if rows else []
fills = {}   # {ticker: {price, shares, action, timestamp, fill_source}}

if len(rows) > 1:
    col = {h: i for i, h in enumerate(headers)}
    for row in rows[1:]:
        if len(row) < len(headers): continue
        ticker = row[col.get('ticker', 0)]
        if not ticker: continue
        fp = row[col['filled_price']]    if 'filled_price'   in col else ''
        fs = row[col['filled_shares']]   if 'filled_shares'  in col else ''
        ft = row[col['fill_timestamp']]  if 'fill_timestamp' in col else ''
        action = row[col['action']]      if 'action'         in col else 'buy'
        if fp and fs and ft:
            fills[ticker] = {
                'price':       float(fp),
                'shares':      int(float(fs)),
                'action':      action,
                'timestamp':   ft,
                'fill_source': 'confirmed',
            }
        else:
            # No fills entered — will use forecast close price as assumed fill
            fills[ticker] = {'action': action, 'fill_source': 'assumed'}
            print(f"  ⚠ No fills for {ticker} ({action}) — will use forecast close")

confirmed_count = sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')
assumed_count   = sum(1 for f in fills.values() if f['fill_source'] == 'assumed')
print(f"Fills: {confirmed_count} confirmed, {assumed_count} assumed, {len(fills)} total")
```

**Phase 3 acceptance test:**
- All 6 cells run on a fresh session without errors
- Cell 1: `os.getcwd()` shows KTH_REPO; `os.listdir('.')` shows project folders
- Cell 3: prints spreadsheet title and list of 14 sheet names
- Cell 6: `fills` dict contains `action` field for each ticker in Trade Ticket

---

## Phase 4 — Colab cells 7–12 (pipeline logic)

**CRITICAL: Cell 9 (update portfolio) MUST run before Cell 10 (generate ticket).**

**Variable outputs from this phase:**

| Variable | Set in | Used in |
|----------|--------|---------|
| `ohlcv_dict` | Cell 7 | Cell 8, Cell 9, Cell 13, Cell 16 |
| `failed_tickers` | Cell 7 | Cell 8, Cell 16 |
| `today_str` | Cell 8 | Cell 9, Cell 10, Cell 13, Cell 16, Cell 17 |
| `pf` | Cell 9 | Cell 11, Cell 13, Cell 19 |
| `ticket_data` | Cell 10 | Cell 13, Cell 19 |
| `metrics` | Cell 11 | Cell 13, Cell 18, Cell 19 |
| `pos` | Cell 12 | Cell 13, Cell 18, Cell 19 |

### Cell 7 — Download Data

```python
from kth.data.loader import download_universe, load_cached
from kth.data.universe import get_all_tickers

# STEP 1: Download fresh OHLCV data to data/raw/*.parquet on Drive
# This takes ~2 minutes for 100 tickers. Subsequent runs reuse the cache.
print("Downloading fresh OHLCV data (takes ~2 min on first run)…")
download_universe()   # updates data/raw/*.parquet; handles retries internally
print("Download complete.")

# STEP 2: Load and apply 30% price sanity filter
tickers        = get_all_tickers()
failed_tickers = set()
ohlcv_dict     = {}

for ticker in tickers:
    try:
        df = load_cached(ticker)
        if df is None or df.empty:
            failed_tickers.add(ticker); continue
        last = float(df['close'].iloc[-1])
        prev = float(df['close'].iloc[-2]) if len(df) > 1 else last
        if prev > 0 and abs(last - prev) / prev > 0.30:
            failed_tickers.add(ticker)
            print(f"  SANITY FAIL: {ticker}  last={last:.2f}  prev={prev:.2f}")
            continue
        ohlcv_dict[ticker] = df
    except Exception as e:
        failed_tickers.add(ticker)
        print(f"  LOAD FAIL: {ticker}: {e}")

print(f"Loaded {len(ohlcv_dict)} tickers | {len(failed_tickers)} failed/excluded")
```

### Cell 8 — Run Forecasts

```python
from datetime import date
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts
from pathlib import Path

today_str  = str(date.today())
CACHE_SLUG = 'NeoQuasar_Kronos-small'

def already_done(ticker):
    safe = ticker.replace('^', '_').replace('=', '_')
    p = Path(f'data/forecast_cache/{CACHE_SLUG}/{today_str}/{safe}.parquet')
    return p.exists()

pending = [t for t in ohlcv_dict if not already_done(t)]
skipped = len(ohlcv_dict) - len(pending)
if skipped:
    print(f"Skipping {skipped} tickers already forecasted today.")

if pending:
    print(f"Running Kronos forecasts for {len(pending)} tickers…")
    th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
    precompute_forecasts(th, pending,
                         start_date=today_str, end_date=today_str,
                         pred_len=20, n_samples=50, lookback=400)

print(f"Forecasts done. Cache at: data/forecast_cache/{CACHE_SLUG}/{today_str}/")
```

### Cell 9 — Update Portfolio State ← MUST RUN BEFORE CELL 10

```python
import json as _json
from datetime import date
from pathlib import Path
from kth.trading.portfolio import execute_trade, init_portfolio, MODEL_VERSION

today_str = str(date.today())   # guard: ensure today_str is defined if Cell 8 was skipped

# 1. Read current state from Sheets (Sheets is source of truth)
pf_rows  = sh.worksheet('Portfolio').get_all_values()
pos_rows = sh.worksheet('Positions').get_all_values()
eq_rows  = sh.worksheet('Equity Curve').get_all_values()
rm_rows  = sh.worksheet('Risk Metrics').get_all_values()

# 2. Rebuild paper_portfolio.json from Sheets data
pf = init_portfolio('paper')   # creates file on Drive if missing

if len(pf_rows) > 1:
    r = pf_rows[1]
    pf['cash']            = float(r[0])
    pf['initial_capital'] = float(r[1])
    pf['mode']            = r[2]
    pf['model_version']   = r[3]

if len(pos_rows) > 1:
    ph = pos_rows[0]
    pf['positions'] = {}
    for r in pos_rows[1:]:
        row = dict(zip(ph, r))
        if not row.get('ticker'): continue
        pf['positions'][row['ticker']] = {
            'shares':     int(float(row['shares'])),
            'avg_cost':   float(row['avg_cost']),
            'entry_date': row.get('entry_date', today_str),
        }

if len(eq_rows) > 1:
    pf['equity_curve'] = [
        {'date': r[0], 'value': float(r[1])}
        for r in eq_rows[1:] if r[0] and r[1]
    ]

if len(rm_rows) > 1:
    rm_h   = rm_rows[0]
    last_rm = dict(zip(rm_h, rm_rows[-1]))
    pf['frozen']    = bool(int(float(last_rm.get('is_frozen', 0) or 0)))
    pf['frozen_at'] = last_rm.get('date', '') if pf['frozen'] else None

# 3. Save JSON to Drive so kth functions can read it
path = Path('data/positions/paper_portfolio.json')
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'w') as f:
    _json.dump(pf, f, indent=2, default=str)
print(f"Portfolio synced: ฿{pf['cash']:,.0f} cash, {len(pf.get('positions',{}))} positions, "
      f"frozen={pf.get('frozen', False)}")

# 4. Apply fills using existing execute_trade()
for ticker, fill in fills.items():
    if fill['fill_source'] == 'assumed':
        if ticker not in ohlcv_dict: continue
        price = float(ohlcv_dict[ticker]['close'].iloc[-1])
        note  = '[fill_source=assumed]'
    else:
        price = fill['price']
        note  = f'[fill_source=confirmed @{fill["timestamp"]}]'

    result = execute_trade(
        ticker=ticker,
        action=fill.get('action', 'buy'),
        shares=fill['shares'],
        fill_price=price,
        mode='paper',
        rationale=f'GS-fill {note}',
    )
    if 'error' in result:
        print(f"  Trade error for {ticker}: {result['error']}")

# Reload pf after execute_trade() updates the JSON
pf = init_portfolio('paper')
print(f"After fills: ฿{pf['cash']:,.0f} cash, {len(pf.get('positions',{}))} positions")
```

### Cell 10 — Generate Trade Ticket ← RUNS AFTER CELL 9

```python
from kth.trading.trade_gen import generate_trade_ticket

# generate_trade_ticket() reads the JSON updated by Cell 9 transparently
ticket_data = generate_trade_ticket(report_date=today_str)

exits   = ticket_data.get('exits', [])
reduces = ticket_data.get('reduces', [])
buys    = ticket_data.get('buys', [])
print(f"Ticket: {len(exits)} exits  {len(reduces)} reduces  {len(buys)} buys")
if ticket_data.get('t2_warning'):
    print(f"T+2 WARNING: {ticket_data['t2_warning']}")
if ticket_data.get('banner'):
    print(f"BANNER: {ticket_data['banner']}")
```

### Cell 11 — Compute Metrics (+ fill missing fields not returned by compute_metrics)

```python
import pandas as pd
from kth.trading.portfolio import compute_metrics, get_trade_log
from kth.backtest.metrics import compute_sortino

metrics = compute_metrics('paper')

# ── compute_metrics() does NOT return calmar, sortino, frozen, or friction_ytd ──
# ── We compute them here and add to the metrics dict                           ──

equity_vals = [e['value'] for e in pf.get('equity_curve', [])]
equity_series = pd.Series(equity_vals) if equity_vals else pd.Series([INITIAL_CAPITAL])
daily_returns = equity_series.pct_change().dropna()

# Calmar = annualised CAGR / abs(max drawdown)
if len(equity_series) >= 2 and metrics.get('drawdown', 0) < 0:
    n_years = max(len(equity_series) / 252, 0.01)
    cagr    = (equity_series.iloc[-1] / equity_series.iloc[0]) ** (1 / n_years) - 1
    metrics['calmar'] = round(cagr / abs(metrics['drawdown']), 4)
else:
    metrics['calmar'] = 0.0

# Sortino ratio (from kth.backtest.metrics)
metrics['sortino'] = round(compute_sortino(daily_returns), 4) \
                     if len(daily_returns) >= 20 else 0.0

# Frozen state (from the portfolio JSON set in Cell 9)
metrics['frozen'] = pf.get('frozen', False)

# Cumulative friction YTD — sum friction_cost column from trade_log.csv for this year
trade_log = get_trade_log('paper')
year_str   = str(date.today().year)
ytd_thb    = sum(float(t.get('friction_cost', 0) or 0)
                 for t in trade_log if t.get('date', '').startswith(year_str))
ic = pf.get('initial_capital', INITIAL_CAPITAL)
metrics['friction_ytd_thb'] = round(ytd_thb, 2)
metrics['friction_ytd_pct'] = round(ytd_thb / ic, 6) if ic else 0.0

print(f"Band: {metrics['allocation_band']}  "
      f"Sharpe: {metrics['sharpe']:.2f}  "
      f"MaxDD: {metrics.get('drawdown',0):.2%}  "
      f"Calmar: {metrics['calmar']:.2f}  "
      f"Frozen: {metrics['frozen']}  "
      f"Friction YTD: {metrics['friction_ytd_pct']:.2%}")
```

### Cell 12 — Validate Data

```python
from kth.trading.portfolio import get_positions

pos    = get_positions('paper')
errors = []

if pos['cash'] < 0:
    errors.append(f"cash negative: ฿{pos['cash']:,.0f}")

tickers_seen = set()
for p in pos['positions']:
    if p['shares'] <= 0:
        errors.append(f"{p['ticker']}: shares={p['shares']}")
    if p['avg_cost'] <= 0:
        errors.append(f"{p['ticker']}: avg_cost={p['avg_cost']}")
    if p['ticker'] in tickers_seen:
        errors.append(f"duplicate position: {p['ticker']}")
    tickers_seen.add(p['ticker'])

if errors:
    _set_pipeline_status(status_ws, 'failed', error_msg='; '.join(errors))
    if LINE_TOKEN:
        import requests
        requests.post('https://notify-api.line.me/api/notify',
                      headers={'Authorization': f'Bearer {LINE_TOKEN}'},
                      data={'message': f'Kronos FAILED Cell 12: {errors[0]}'})
    raise RuntimeError(f"Validation failed: {errors}")

print(f"Validation passed. "
      f"{len(pos['positions'])} positions | ฿{pos['cash']:,.0f} cash")
```

**Phase 4 acceptance test:**
- Cell 7: prints `Downloaded N tickers` (not zero); `failed_tickers` may be empty or small
- Cell 8: prints `Forecasts done` with a cache path
- Cell 9: prints correct cash/positions read from Sheets; fills applied without errors
- Cell 10: prints ticket counts; `reduces` shows in output
- Cell 11: `metrics['calmar']`, `metrics['sortino']`, `metrics['friction_ytd_pct']` are non-zero values (not 0.0) after the first real pipeline run
- Cell 12: prints `Validation passed`

---

## Phase 5 — Colab cells 13–19 (write-back)

**Goal:** all 9 live sheets populated; switch web app to live data.

**Variable dependencies:**

| Cell 13 needs | Cell 14 needs | Cell 15 needs | Cell 16 needs |
|---------------|---------------|---------------|---------------|
| `pf`, `pos`, `metrics`, `ohlcv_dict`, `ticket_data`, `fc_rows`, `today_str`, `sh`, `STAGING_MAP` | `STAGING_MAP`, `sh` | `sh`, `MODEL_VERSION` | `sh`, `fh_data`, `ohlcv_dict`, `failed_tickers`, `fc_rows`, `today_str` |

### Cell 13 — Write to Staging

```python
from kth.trading.portfolio import get_positions, init_portfolio
from kth.trading.trade_gen import load_forecasts
from kth.data.universe import get_sector, get_ticker_class, FRICTION

def _write_staging(ws_name, headers, rows):
    """Clear + write header + write rows in minimal API calls."""
    ws = sh.worksheet(ws_name)
    ws.clear()
    ws.append_row(headers)
    if rows:
        ws.append_rows(rows)   # one API call for all rows
    time.sleep(1)              # stay under 60 writes/minute

# ── Portfolio_staging ──────────────────────────────────────────────────────
pf_data = init_portfolio('paper')
_write_staging('Portfolio_staging',
    ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

# ── Positions_staging ──────────────────────────────────────────────────────
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
_write_staging('Positions_staging',
    ['ticker','shares','avg_cost','entry_date','sector','current_price','pnl','pnl_pct','pct_to_stoploss'],
    pos_rows)

# ── Forecasts_staging ──────────────────────────────────────────────────────
fc_rows      = load_forecasts(today_str)
fc_by_ticker = {r['ticker']: r for r in fc_rows}
_write_staging('Forecasts_staging',
    ['date_updated','ticker','rank_score','exp_ret','band_width','confidence',
     'net_return','p5','p50','p95','sector'],
    [[today_str, r['ticker'], r['rank_score'], r['exp_ret'], r['band_width'],
      r['confidence'], r['net_ret'], r['p5_close'], r['p50_close'], r['p95_close'],
      get_sector(r['ticker'])] for r in fc_rows])

# ── Trade Ticket_staging ───────────────────────────────────────────────────
tt_rows = []
all_items = (
    [('sell', item) for item in ticket_data.get('exits', [])] +
    [('sell', item) for item in ticket_data.get('reduces', [])] +
    [('buy',  item) for item in ticket_data.get('buys', [])]
)
for action_type, item in all_items:
    ticker   = item['ticker']
    close    = item.get('last_close', 0)
    cls      = get_ticker_class(ticker)
    fric     = FRICTION.get(cls, {'commission_oneway': 0.002, 'slippage_oneway': 0.001})
    fric_rt  = fric['commission_oneway'] * 2 + fric['slippage_oneway'] * 2
    est_cost = round(item['shares'] * close * (1 + fric_rt), 2)
    conf     = fc_by_ticker.get(ticker, {}).get('confidence', '')
    tt_rows.append([
        ticker, action_type, item['shares'], est_cost,
        item.get('rationale', ''), get_sector(ticker), conf,
        '', '', '',   # filled_price, filled_shares, fill_timestamp — blank, user fills these
    ])
_write_staging('Trade Ticket_staging',
    ['ticker','action','shares','est_cost_thb','rationale','sector','confidence',
     'filled_price','filled_shares','fill_timestamp'],
    tt_rows)

# ── Risk Metrics_staging ───────────────────────────────────────────────────
equity = pos['total_value']
_write_staging('Risk Metrics_staging',
    ['date','equity','cash','deployed_pct','trailing_sharpe_12w','max_drawdown_pct',
     'mtd_pnl_pct','trade_win_rate','calmar_ratio','sortino_ratio','drawdown_velocity',
     'allocation_band','allocation_pct','market_state','is_frozen','bootstrap_p_value',
     'friction_ytd_pct','friction_ytd_thb'],
    [[
        today_str, round(equity, 2), round(pf_data['cash'], 2),
        round(metrics.get('exposure', 0), 4),
        round(metrics.get('sharpe', 0), 4),
        round(metrics.get('drawdown', 0), 4),
        round(metrics.get('pnl_mtd_pct', 0), 4),
        round(metrics.get('win_rate', 0), 4),
        round(metrics.get('calmar', 0), 4),          # computed in Cell 11
        round(metrics.get('sortino', 0), 4),          # computed in Cell 11
        round(metrics.get('drawdown_velocity', 0), 4),
        metrics.get('allocation_band', 'NEUTRAL'),
        metrics.get('allocation_pct', 0.10),
        metrics.get('market_state', 'Normal'),
        1 if metrics.get('frozen') else 0,            # from Cell 11
        round(metrics.get('bootstrap_pvalue', 1.0), 4),
        round(metrics.get('friction_ytd_pct', 0), 4),  # computed in Cell 11
        round(metrics.get('friction_ytd_thb', 0), 2),   # computed in Cell 11
    ]])

print("All 5 staging sheets written.")
```

### Cell 14 — Promote Staging to Live

```python
STAGING_MAP = {
    'Portfolio_staging':     'Portfolio',
    'Positions_staging':     'Positions',
    'Forecasts_staging':     'Forecasts',
    'Trade Ticket_staging':  'Trade Ticket',
    'Risk Metrics_staging':  'Risk Metrics',
}
for staging_name, live_name in STAGING_MAP.items():
    staging_ws = sh.worksheet(staging_name)
    live_ws    = sh.worksheet(live_name)
    data = staging_ws.get_all_values()
    if data:
        live_ws.clear()
        live_ws.update('A1', data)   # range required by gspread 5.x
    staging_ws.clear()
    time.sleep(1)
print("Staging promoted to live sheets.")
```

### Cell 15 — Append Trade Log

```python
import hashlib
from kth.trading.portfolio import get_trade_log

tl_ws    = sh.worksheet('Trade Log')
all_rows = tl_ws.get_all_values()
# Column I (index 8) holds the id field
existing_ids = set(r[8] for r in all_rows[1:] if len(r) > 8 and r[8])

trade_log = get_trade_log('paper')
new_rows  = []

for trade in trade_log[-50:]:   # check only recent 50 to avoid scanning thousands
    raw      = f"{trade['date']}_{trade['ticker']}_{trade['action']}"
    hex4     = hashlib.md5(raw.encode()).hexdigest()[:4]
    trade_id = f"{trade['date'].replace('-','')}_{trade['ticker']}_{trade['action']}_{hex4}"
    if trade_id in existing_ids:
        continue
    new_rows.append([
        trade['date'],
        trade['ticker'],
        trade['action'],
        trade['shares'],
        trade['price'],
        trade.get('rationale', ''),
        trade.get('friction_cost', 0),
        trade.get('model_version', MODEL_VERSION),
        trade_id,
        '',   # ref_id — blank for normal entries
    ])
    existing_ids.add(trade_id)

if new_rows:
    tl_ws.append_rows(new_rows)   # one API call for all rows
print(f"Trade Log: {len(new_rows)} new entries appended.")
```

### Cell 16 — Update & Append Forecast History

```python
fh_ws   = sh.worksheet('Forecast History')
fh_data = fh_ws.get_all_values()
fh_h    = fh_data[0] if fh_data else []
col     = {h: i for i, h in enumerate(fh_h)}

# STEP 1: Resolve prior-day actual_return in one batch_update call
updates = []
for list_idx, row in enumerate(fh_data[1:], start=2):   # list_idx = 1-based Sheets row number
    if not row: continue
    if row[col.get('actual_return', 5)] != '': continue   # already resolved
    ticker = row[col.get('ticker', 1)]
    if ticker in failed_tickers or ticker not in ohlcv_dict: continue
    try:
        entry_close = float(row[col['entry_close']])
        pred_return = float(row[col['predicted_return']])
        today_close = float(ohlcv_dict[ticker]['close'].iloc[-1])
        act_ret     = (today_close - entry_close) / entry_close
        correct     = 1 if (act_ret > 0) == (pred_return > 0) else 0
        ar_col = col['actual_return'] + 1    # convert to 1-based column index
        wc_col = col['was_correct'] + 1
        # Convert column index to letter: 1→A, 6→F, 7→G
        updates.append({
            'range':  f'{chr(64 + ar_col)}{list_idx}:{chr(64 + wc_col)}{list_idx}',
            'values': [[round(act_ret, 4), correct]],
        })
    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        continue   # skip unresolvable rows; try again next run

if updates:
    fh_ws.batch_update(updates)   # one API call for all resolutions
    print(f"Forecast History: resolved {len(updates)} prior-day rows.")

# STEP 2: Append today's predictions in one call
today_rows = [
    [today_str, r['ticker'],
     'up' if r['exp_ret'] > 0 else 'down',
     round(r['exp_ret'], 4),
     round(r['close'], 2),   # entry_close — needed to compute actual_return tomorrow
     '',                      # actual_return — blank; resolved on tomorrow's run
     '']                      # was_correct — blank
    for r in fc_rows if r['ticker'] not in failed_tickers
]
if today_rows:
    fh_ws.append_rows(today_rows)
print(f"Forecast History: appended {len(today_rows)} predictions for {today_str}.")
```

### Cell 17 — Set Pipeline Status: Completed

```python
duration = round(time.time() - pipeline_start, 1)
_set_pipeline_status(
    status_ws, 'completed',
    duration=duration,
    sheets_updated=','.join(STAGING_MAP.values()) + ',Trade Log,Forecast History',
)
print(f"Pipeline completed in {duration}s.")
```

### Cell 18 — LINE Notify

```python
def _line_notify(msg):
    if not LINE_TOKEN: return
    import requests
    try:
        requests.post('https://notify-api.line.me/api/notify',
                      headers={'Authorization': f'Bearer {LINE_TOKEN}'},
                      data={'message': msg}, timeout=10)
    except Exception as e:
        print(f"LINE Notify failed: {e}")

_line_notify(
    f"\n✅ Kronos pipeline done ({duration}s)\n"
    f"Capital: ฿{pos['total_value']:,.0f}\n"
    f"Band: {metrics['allocation_band']} "
    f"({metrics.get('allocation_pct',0.1)*100:.0f}% per pos)\n"
    f"Buys: {len(ticket_data.get('buys',[]))}  "
    f"Exits: {len(ticket_data.get('exits',[]))}\n"
    f"Fills confirmed: "
    f"{sum(1 for f in fills.values() if f['fill_source']=='confirmed')}"
)
```

### Cell 19 — Summary

```python
confirmed = sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')
assumed   = sum(1 for f in fills.values() if f['fill_source'] == 'assumed')
print(f"""
{'='*54}
  KRONOS-TH PIPELINE COMPLETE
{'='*54}
  Capital:           ฿{pos['total_value']:>12,.0f}
  Cash:              ฿{pf_data['cash']:>12,.0f}
  P&L MTD:           {metrics.get('pnl_mtd_pct', 0):>+11.2%}
  Trailing Sharpe:   {metrics.get('sharpe', 0):>12.2f}
  Allocation band:   {metrics['allocation_band']:>12}
  Per-position:      {metrics.get('allocation_pct', 0.1)*100:>10.0f}%
  Frozen:            {str(metrics.get('frozen', False)):>12}
  Buys today:        {len(ticket_data.get('buys',[])):>12}
  Exits today:       {len(ticket_data.get('exits',[])):>12}
  Reduces today:     {len(ticket_data.get('reduces',[])):>12}
  Fills confirmed:   {confirmed:>12}
  Fills assumed:     {assumed:>12}
  Friction YTD:      {metrics.get('friction_ytd_pct', 0):>+11.2%}  \
(฿{metrics.get('friction_ytd_thb', 0):,.0f})
  Duration:          {duration:>10.1f}s
{'='*54}
""")
```

**Switch web app to live data (do this now):**
In `Index.html`, in the bootstrap block, comment out `renderAll(MOCK)` and uncomment
the `google.script.run` block. Then redeploy: Deploy > Manage deployments > New version.

**Phase 5 acceptance test:**
- Full "Run All" completes without errors (check Cell 19 summary printed)
- All 9 live sheets populated in Google Sheets (verify manually)
- Risk Metrics sheet: `calmar_ratio`, `sortino_ratio`, `friction_ytd_pct` are non-zero
- Web app Dashboard: green pipeline banner, equity curve chart visible, regime badge shown
- Web app Positions: current positions with correct prices
- Web app Trade Ticket: today's recommendations; Export CSV downloads a valid file

---

## Phase 6 — Migration script

```python
"""google_suite/migrate_to_sheets.py
One-time migration: data/positions/ JSON + CSV → Google Sheets.

Usage:
  python google_suite/migrate_to_sheets.py --id <SPREADSHEET_ID>
  
  First run opens a browser OAuth window. Credentials are saved to
  ~/.config/gspread/authorized_user.json for future runs.
"""
import json, csv, hashlib, argparse
from pathlib import Path

PORTFOLIO_JSON = Path('data/positions/paper_portfolio.json')
TRADE_LOG_CSV  = Path('data/positions/trade_log.csv')


def migrate(spreadsheet_id: str):
    import gspread
    gc = gspread.oauth()   # browser OAuth — no service account or key file needed
    sh = gc.open_by_key(spreadsheet_id)
    print(f"Connected to: {sh.title}")

    if PORTFOLIO_JSON.exists():
        pf = json.loads(PORTFOLIO_JSON.read_text())
        # Portfolio sheet
        ws = sh.worksheet('Portfolio')
        from kth.trading.portfolio import MODEL_VERSION
        ws.update('A1:E2', [
            ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
            [pf['cash'], pf['initial_capital'], pf.get('mode', 'paper'),
             pf.get('model_version', MODEL_VERSION),
             str(pf['equity_curve'][-1]['date']) if pf.get('equity_curve') else ''],
        ])
        # Equity Curve — equity only; cash/invested computed on next pipeline run
        eq_ws = sh.worksheet('Equity Curve')
        eq_ws.clear()
        eq_ws.append_row(['date', 'equity', 'cash', 'invested'])
        rows = [[e['date'], e['value'], '', ''] for e in pf.get('equity_curve', [])]
        if rows:
            eq_ws.append_rows(rows)
        print(f"Portfolio migrated. Equity curve: {len(rows)} rows.")

    if TRADE_LOG_CSV.exists():
        tl_ws = sh.worksheet('Trade Log')
        tl_ws.clear()
        tl_ws.append_row([
            'timestamp','ticker','action','shares','price','rationale',
            'friction_cost','model_version','id','ref_id',
        ])
        new_rows = []
        with open(TRADE_LOG_CSV) as f:
            for trade in csv.DictReader(f):
                raw  = f"{trade['date']}_{trade['ticker']}_{trade['action']}"
                hex4 = hashlib.md5(raw.encode()).hexdigest()[:4]
                tid  = f"{trade['date'].replace('-','')}_{trade['ticker']}_{trade['action']}_{hex4}"
                new_rows.append([
                    trade['date'], trade['ticker'], trade['action'],
                    trade['shares'], trade['price'], trade.get('rationale', ''),
                    trade.get('friction_cost', ''), trade.get('model_version', ''),
                    tid, '',
                ])
        if new_rows:
            tl_ws.append_rows(new_rows)
        print(f"Trade Log migrated: {len(new_rows)} trades.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate Kronos-TH data to Google Sheets')
    parser.add_argument('--id', required=True, help='Google Spreadsheet ID from the URL')
    args = parser.parse_args()
    migrate(args.id)
```

**Phase 6 acceptance test:**
- `python google_suite/migrate_to_sheets.py --id <ID>` — browser OAuth window opens
- Portfolio sheet row 2 shows correct cash and initial capital
- Trade Log has all historical trades with generated IDs in column I

---

## Phase 7 — README

### `google_suite/README.md` outline

Write using the Phase 1 table and the Glossary from the spec. Include:

1. **Pre-requisites:** Colab GPU runtime (mandatory), Google account owning the spreadsheet
2. **Spreadsheet setup:** create 14 tabs, paste header rows (include copy-paste table from Phase 1.1)
3. **Apps Script setup:** Extensions > Apps Script (from within spreadsheet — NOT from script.google.com); paste Code.gs + Index.html; V8 runtime; deploy
4. **⚠ Deployment version warning:** every Code.gs edit needs Deploy > New version
5. **Colab secrets:** KRONOS_SPREADSHEET_ID + LINE_NOTIFY_TOKEN (with screenshot guidance)
6. **First run:** upload notebook, verify KTH_REPO path (Cell 1 prints it), set INITIAL_CAPITAL (Cell 2), Run All
7. **Daily routine** (from spec Glossary): morning (7:00–8:30 BKK), fill entry steps, monitoring
8. **Fill entry instructions:** open Trade Ticket sheet → columns 8-10 → enter filled_price, filled_shares, fill_timestamp
9. **CANCEL convention:** how to correct a wrong entry; reminder to also fix Portfolio sheet manually
10. **Troubleshooting table:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Cell 8 crashes with CUDA error | CPU runtime | Runtime > Change runtime type > T4 GPU |
| Cell 1 shows wrong folder contents | KTH_REPO path wrong | Check `/content/drive/MyDrive/` listing |
| Cell 3 error: spreadsheet not found | Wrong spreadsheet ID in Secret | Re-copy ID from spreadsheet URL |
| Web app shows blank page | doGet() missing from Code.gs | Re-paste Code.gs, redeploy new version |
| Web app shows old data after code change | Old deployment version | Deploy > Manage deployments > New version |
| Export CSV download doesn't work on iPhone | iOS Safari Blob issue | Already handled with `data:` URI in renderTicket |
| `gspread.exceptions.APIError: 429` | Too many API calls | Cell 13 already has sleep(1); if recurring, increase sleep to 2 |

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Cell 9/10 order wrong | Both cells labelled ← CRITICAL; dependency table in Phase 4 header |
| Colab GPU not set | Pre-requisites section at top of plan |
| Drive path differs | Cell 1 prints `os.getcwd()` and `os.listdir('.')` — verify before running Cell 2 |
| `compute_metrics()` missing calmar/sortino/frozen/friction | Cell 11 explicitly computes all missing fields |
| OHLCV data stale | Cell 7 calls `download_universe()` before `load_cached()` |
| `batch_update` column letters | Forecast History has 7 columns (A-G only). Formula: `chr(64 + col_idx)` where col_idx is 1-based |
| `append_rows()` rate limit | Each `_write_staging()` call sleeps 1s; Cell 15 uses single `append_rows()` |
| `entry_date` lost on Positions replace | Cell 9 reads entry_date from Positions sheet and stores in JSON; Cell 13 writes it back |
| `is_frozen` lost on fresh Colab session | Cell 9 reads is_frozen from Risk Metrics sheet and sets `pf['frozen']` |
| iOS Safari CSV download | `data:` URI used in `exportCsv()` — works on iOS |

---

## Build Checklist

- [ ] Phase 1: 14-tab spreadsheet with correct headers; Code.gs deployed; web app URL opens, spinner visible
- [ ] Phase 2: All 5 render functions complete; MOCK data tests pass; sortable tables; sub-tab toggle; mobile layout
- [ ] Phase 3: Cells 1-6 run clean; `fills` has `action` field; Pipeline Status shows `running`
- [ ] Phase 4: Cells 7-12 in correct order (9=portfolio BEFORE 10=ticket); Cell 11 has calmar/sortino/friction; validation passes
- [ ] Phase 5: Full Run All succeeds; all 9 live sheets populated; Risk Metrics has non-zero calmar/sortino; web app switched to live data
- [ ] Phase 6: migrate_to_sheets.py migrates existing data; `__main__` block with argparse
- [ ] Phase 7: README with troubleshooting table and copy-paste headers
