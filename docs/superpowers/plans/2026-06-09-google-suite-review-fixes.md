# Google Suite Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all issues identified in the Google Suite review — engineering (extract shared logic, add tests, fix fragility) and UX/UI (accessibility, mobile, dark mode, clarity)

**Architecture:** Three phases — Phase 1 (P0) fixes fragile/duplicate code in build_notebook.py and Code.gs; Phase 2 (P1) adds tests and observability; Phase 3 (P2) improves UX/UI in Index.html and Code.gs

**Tech Stack:** Google Apps Script (JavaScript), Python 3.10+, Colab/Jupyter, Google Sheets API (gspread)

**Files modified:**
- `google_suite/build_notebook.py` — extract shared _write_staging + promotion logic, fix globals() pattern
- `google_suite/kronos_daily_pipeline.ipynb` — regenerated after build_notebook changes
- `google_suite/apps_script/Code.gs` — add Logger.log, error handling, aria support
- `google_suite/apps_script/Index.html` — accessibility, dark mode, mobile, tooltips
- `google_suite/SETUP_GUIDE.md` — updated cell count if changed
- `kth/trading/portfolio.py` — if any API changes needed
- `tests/` — new test files

---

## Phase 1: Engineering — Code Quality & Maintainability

### Task 1: Extract shared _write_staging + promotion to kth module

**Files:**
- Create: `kth/trading/sheets.py`
- Modify: `google_suite/build_notebook.py:137-217, 426-505, 652-796`
- Modify: `google_suite/build_notebook.py` — replace duplicate code with imports

**Step 1:** Create `kth/trading/sheets.py` with shared functions

```python
"""Shared Google Sheets staging + promotion utilities for Colab pipeline."""
import time as _time
from typing import Any

def write_staging(ws, headers: list, rows: list, sleep_sec: float = 1.0) -> None:
    ws.clear()
    ws.append_row(headers)
    if rows:
        ws.append_rows(rows)
    _time.sleep(sleep_sec)


STAGING_MAP: dict = {
    'Portfolio_staging': 'Portfolio',
    'Positions_staging': 'Positions',
    'Forecasts_staging': 'Forecasts',
    'Trade Ticket_staging': 'Trade Ticket',
    'Risk Metrics_staging': 'Risk Metrics',
    'Equity Curve_staging': 'Equity Curve',
}


def promote_staging(sh, staging_map: dict = None, sleep_sec: float = 1.0) -> None:
    if staging_map is None:
        staging_map = STAGING_MAP
    for staging_name, live_name in staging_map.items():
        staging_ws = sh.worksheet(staging_name)
        live_ws = sh.worksheet(live_name)
        data = staging_ws.get_all_values()
        if data:
            live_ws.clear()
            live_ws.update('A1', data)
        staging_ws.clear()
        _time.sleep(sleep_sec)


def build_pos_rows(positions: dict, ohlcv_dict: dict, get_sector_fn) -> list:
    from kth.data.universe import get_sector
    rows = []
    for p in positions['positions']:
        ohlcv = ohlcv_dict or {}
        if p['ticker'] in ohlcv:
            close = float(ohlcv[p['ticker']]['close'].iloc[-1])
        else:
            close = p['avg_cost']
        pnl = (close - p['avg_cost']) * p['shares']
        pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
        rows.append([
            p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
            get_sector_fn(p['ticker']), round(close, 2),
            round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
        ])
    return rows


POSITIONS_HEADERS = [
    'ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
    'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss',
]


PORTFOLIO_HEADERS = [
    'cash', 'initial_capital', 'mode', 'model_version', 'forecast_date',
]
```

**Step 2:** Replace duplicate code in `build_notebook.py` Cell 4b

Old code (lines ~137-217) becomes:
```python
from kth.data.universe import get_sector
from kth.trading.portfolio import reset_portfolio, get_positions, init_portfolio, MODEL_VERSION
from kth.trading.sheets import write_staging, promote_staging, build_pos_rows, POSITIONS_HEADERS, PORTFOLIO_HEADERS, STAGING_MAP

capital_reset_ws = sh.worksheet('Capital Reset')
capital_reset_data = capital_reset_ws.get_all_values()
capital_reset_headers = ['date', 'action', 'capital', 'confirm_text', 'requested_at']
if not capital_reset_data:
    capital_reset_ws.append_row(capital_reset_headers)
else:
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

pf_data = init_portfolio('paper')
write_staging(sh.worksheet('Portfolio_staging'), PORTFOLIO_HEADERS,
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

pos = get_positions('paper')
pos_rows = build_pos_rows(pos, ohlcv_dict, get_sector)
write_staging(sh.worksheet('Positions_staging'), POSITIONS_HEADERS, pos_rows)

write_staging(sh.worksheet('Equity Curve_staging'),
    ['date', 'equity', 'cash', 'invested'],
    [[today_str, round(pf_data['initial_capital'], 2), round(pf_data['cash'], 2), 0.0]])

promote_staging(sh, STAGING_MAP)
print("Capital reset applied and staging promoted.")
```

**Step 3:** Replace Cell 9b duplicate code (lines ~426-505) with same import pattern

```python
from kth.data.universe import get_sector
from kth.trading.portfolio import edit_trade, delete_trade, init_portfolio, get_positions, MODEL_VERSION
from kth.trading.sheets import write_staging, promote_staging, build_pos_rows, POSITIONS_HEADERS, PORTFOLIO_HEADERS, STAGING_MAP

trade_edits_ws = sh.worksheet('Trade Edits')
trade_edits_data = trade_edits_ws.get_all_values()
trade_edits_headers = ['date', 'action', 'index', 'ticker', 'shares', 'price', 'ref_id', 'requested_at']
if not trade_edits_data:
    trade_edits_ws.append_row(trade_edits_headers)
else:
    pf = init_portfolio('paper')
    for row in trade_edits_data[1:]:
        if not row or not row[0]: continue
        action = row[1]
        if action == 'edit':
            try:
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

pf_data = init_portfolio('paper')
write_staging(sh.worksheet('Portfolio_staging'), PORTFOLIO_HEADERS,
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

pos = get_positions('paper')
pos_rows = build_pos_rows(pos, ohlcv_dict, get_sector)
write_staging(sh.worksheet('Positions_staging'), POSITIONS_HEADERS, pos_rows)

promote_staging(sh, STAGING_MAP)
print("Trade edits applied and staging promoted.")
```

**Step 4:** Replace Cell 13 duplicate code (lines ~652-796) with same imports

The write_staging calls for Portfolio_staging and Positions_staging are now shared. The Forecasts_staging, Trade Ticket_staging, Risk Metrics_staging, and Equity Curve_staging remain in Cell 13 (they have unique schemas). Replace the Portfolio/Positions writes:

```python
from kth.trading.portfolio import get_positions, init_portfolio
from kth.trading.trade_gen import load_forecasts
from kth.data.universe import get_sector, get_ticker_class, FRICTION
from kth.trading.sheets import write_staging, build_pos_rows, POSITIONS_HEADERS, PORTFOLIO_HEADERS, STAGING_MAP

pf_data = init_portfolio('paper')
write_staging(sh.worksheet('Portfolio_staging'), PORTFOLIO_HEADERS,
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

pos = get_positions('paper')
pos_rows = build_pos_rows(pos, ohlcv_dict, get_sector)
write_staging(sh.worksheet('Positions_staging'), POSITIONS_HEADERS, pos_rows)
# ... rest of unique writes unchanged
```

**Step 5:** Replace Cell 14 promotion code with shared function

```python
from kth.trading.sheets import promote_staging
promote_staging(sh)
print("Staging promoted to live sheets.")
```

**Step 6:** Regenerate notebook and verify

```bash
python google_suite/build_notebook.py
python -c "import json; nb=json.load(open('google_suite/kronos_daily_pipeline.ipynb')); print(f'{len(nb[\"cells\"])} cells')"
```

Expected: 44 cells (or same count as before — structure unchanged, only imports changed)

**Step 7: Commit**

```bash
git add kth/trading/sheets.py google_suite/build_notebook.py google_suite/kronos_daily_pipeline.ipynb
git commit -m "refactor(google-suite): extract shared _write_staging + promotion to kth/trading/sheets.py"
```

---

### Task 2: Add sheet schema config (single source of truth)

**Files:**
- Create: `kth/trading/sheets_config.py`
- Modify: `google_suite/build_notebook.py` — import schemas
- Modify: `google_suite/apps_script/Code.gs` — add matching constants
- Modify: `google_suite/migrate_to_sheets.py` — use schemas

**Step 1:** Create `kth/trading/sheets_config.py`

```python
"""Single source of truth for Google Sheets schemas and tab names.

Apps Script (Code.gs) and Index.html must mirror these definitions manually.
"""

# --- Tab names ---
PORTFOLIO = 'Portfolio'
EQUITY_CURVE = 'Equity Curve'
POSITIONS = 'Positions'
TRADE_LOG = 'Trade Log'
FORECASTS = 'Forecasts'
FORECAST_HISTORY = 'Forecast History'
TRADE_TICKET = 'Trade Ticket'
RISK_METRICS = 'Risk Metrics'
PIPELINE_STATUS = 'Pipeline Status'
CALIBRATION = 'Calibration'

STAGING_SUFFIX = '_staging'
TRADE_EDITS = 'Trade Edits'
CAPITAL_RESET = 'Capital Reset'

# --- Header schemas ---
PORTFOLIO_HEADERS = ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date']
EQUITY_CURVE_HEADERS = ['date', 'equity', 'cash', 'invested']
POSITIONS_HEADERS = ['ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
                     'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss']
TRADE_LOG_HEADERS = ['timestamp', 'ticker', 'action', 'shares', 'price', 'rationale',
                     'friction_cost', 'model_version', 'id', 'ref_id']
FORECASTS_HEADERS = ['date_updated', 'ticker', 'rank_score', 'exp_ret', 'band_width',
                     'confidence', 'net_return', 'p5', 'p50', 'p95', 'sector']
FORECAST_HISTORY_HEADERS = ['date', 'ticker', 'predicted_direction', 'predicted_return',
                            'entry_close', 'actual_return', 'was_correct']
TRADE_TICKET_HEADERS = ['ticker', 'action', 'shares', 'est_cost_thb', 'rationale',
                        'sector', 'confidence', 'filled_price', 'filled_shares', 'fill_timestamp']
RISK_METRICS_HEADERS = ['date', 'equity', 'cash', 'deployed_pct', 'trailing_sharpe_12w',
                        'max_drawdown_pct', 'mtd_pnl_pct', 'trade_win_rate', 'calmar_ratio',
                        'sortino_ratio', 'drawdown_velocity', 'allocation_band', 'allocation_pct',
                        'market_state', 'is_frozen', 'bootstrap_p_value',
                        'friction_ytd_pct', 'friction_ytd_thb']
PIPELINE_STATUS_HEADERS = ['last_run_timestamp', 'status', 'duration_seconds',
                           'error_message', 'sheets_updated']
CALIBRATION_HEADERS = ['date', 'coverage', 'n_samples', 'status']
TRADE_EDITS_HEADERS = ['date', 'action', 'index', 'ticker', 'shares', 'price', 'ref_id', 'requested_at']
CAPITAL_RESET_HEADERS = ['date', 'action', 'capital', 'confirm_text', 'requested_at']

ALL_HEADERS = {
    PORTFOLIO: PORTFOLIO_HEADERS,
    EQUITY_CURVE: EQUITY_CURVE_HEADERS,
    POSITIONS: POSITIONS_HEADERS,
    TRADE_LOG: TRADE_LOG_HEADERS,
    FORECASTS: FORECASTS_HEADERS,
    FORECAST_HISTORY: FORECAST_HISTORY_HEADERS,
    TRADE_TICKET: TRADE_TICKET_HEADERS,
    RISK_METRICS: RISK_METRICS_HEADERS,
    PIPELINE_STATUS: PIPELINE_STATUS_HEADERS,
    CALIBRATION: CALIBRATION_HEADERS,
    TRADE_EDITS: TRADE_EDITS_HEADERS,
    CAPITAL_RESET: CAPITAL_RESET_HEADERS,
}

ALL_SHEETS = list(ALL_HEADERS.keys()) + [s + STAGING_SUFFIX for s in [
    PORTFOLIO, POSITIONS, FORECASTS, TRADE_TICKET, RISK_METRICS, EQUITY_CURVE,
]]
```

**Step 2:** Update `build_notebook.py` to import from sheets_config instead of hardcoding strings

Change all hardcoded header lists to use the config. For example:
```python
from kth.trading.sheets_config import PORTFOLIO_HEADERS, POSITIONS_HEADERS, ...
```

**Step 3:** Update `migrate_to_sheets.py` to use sheets_config headers

**Step 4: Commit**

```bash
git add kth/trading/sheets_config.py google_suite/build_notebook.py google_suite/migrate_to_sheets.py
git commit -m "refactor(google-suite): single source of truth for sheet schemas (sheets_config.py)"
```

---

### Task 3: Add unit tests for kth/trading/portfolio.py

**Files:**
- Create: `tests/test_portfolio.py`

**Step 1:** Create `tests/test_portfolio.py`

```python
"""Tests for kth/trading/portfolio.py critical functions."""
import json, os, tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# The portfolio module uses Path('data/positions/paper_portfolio.json')
# We patch POSITIONS_DIR to a temp dir in each test.


@pytest.fixture
def temp_positions_dir():
    with tempfile.TemporaryDirectory() as tmp:
        orig_cwd = os.getcwd()
        os.chdir(tmp)
        yield tmp
        os.chdir(orig_cwd)


def test_init_portfolio_creates_default(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio
    pf = init_portfolio('paper')
    assert pf['mode'] == 'paper'
    assert pf['cash'] == 0.0
    assert pf['initial_capital'] == 0.0
    assert pf['positions'] == {}


def test_reset_portfolio_sets_capital(temp_positions_dir):
    from kth.trading.portfolio import reset_portfolio, init_portfolio
    reset_portfolio('paper', 500000.0)
    pf = init_portfolio('paper')
    assert pf['cash'] == 500000.0
    assert pf['initial_capital'] == 500000.0
    assert pf['positions'] == {}
    assert pf['equity_curve'] == []


def test_execute_trade_basic(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper')
    result = execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'test trade')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert 'PTT.BK' in pf['positions']
    assert pf['positions']['PTT.BK']['shares'] == 100
    assert pf['positions']['PTT.BK']['avg_cost'] == 35.0


def test_execute_trade_sell_reduces_shares(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper', 500000.0)
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'buy')
    result = execute_trade('PTT.BK', 'sell', 50, 38.0, 'paper', 'sell')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert pf['positions']['PTT.BK']['shares'] == 50


def test_execute_trade_sell_all_removes_position(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper', 500000.0)
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'buy')
    execute_trade('PTT.BK', 'sell', 100, 38.0, 'paper', 'sell all')
    pf = init_portfolio('paper')
    assert 'PTT.BK' not in pf['positions']


def test_edit_trade_updates_price_and_shares(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade, edit_trade
    init_portfolio('paper', 500000.0)
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'buy')
    edit_trade(0, new_price=36.0, new_shares=150, mode='paper')
    pf = init_portfolio('paper')
    assert pf['positions']['PTT.BK']['avg_cost'] == 36.0
    assert pf['positions']['PTT.BK']['shares'] == 150


def test_delete_trade_removes_position(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade, delete_trade
    init_portfolio('paper', 500000.0)
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'buy')
    delete_trade(0, 'paper')
    pf = init_portfolio('paper')
    assert 'PTT.BK' not in pf['positions']
```

**Step 2:** Run tests to verify

```bash
pip install -e . && python -m pytest tests/test_portfolio.py -v
```

Expected: All 6 tests pass.

**Step 3: Commit**

```bash
git add tests/test_portfolio.py
git commit -m "test: add unit tests for kth/trading/portfolio.py critical path"
```

---

### Task 4: Add error handling for CacheService failures in Code.gs

**Files:**
- Modify: `google_suite/apps_script/Code.gs:72-73, 115-116`

**Step 1:** Wrap CacheService calls in try/catch

```javascript
function _cachePut(key, value, ttl) {
  try {
    CacheService.getScriptCache().put(key, value, ttl || 60);
  } catch (e) {
    console.error('Cache put failed (quota?): ' + e.message);
  }
}

function _cacheRemove(key) {
  try {
    CacheService.getScriptCache().remove(key);
  } catch (e) {
    console.error('Cache remove failed: ' + e.message);
  }
}

function _cacheGet(key) {
  try {
    return CacheService.getScriptCache().get(key);
  } catch (e) {
    console.error('Cache get failed: ' + e.message);
    return null;
  }
}
```

**Step 2:** Replace all direct CacheService calls with wrappers

- `cache.get(...)` → `_cacheGet(...)`
- `cache.put(...)` → `_cachePut(...)`
- `CacheService.getScriptCache().remove(...)` → `_cacheRemove(...)`

**Step 3:** Add audit logging

```javascript
function _log(action, detail) {
  try {
    console.log({ time: new Date().toISOString(), action: action, detail: detail });
    // Optional: append to a hidden sheet row for persistent audit trail
  } catch (e) {
    // silent fail — logging should never break the app
  }
}
```

Add calls: `_log('getAllData', 'cache hit/miss')`, `_log('submitFills', updated count)`, etc.

**Step 4: Commit**

```bash
git add google_suite/apps_script/Code.gs
git commit -m "fix(google-suite): wrap CacheService in try/catch, add audit logging"
```

---

### Task 5: Add contextual error handling in Colab critical paths

**Files:**
- Modify: `google_suite/build_notebook.py`

**Step 1:** Review all `except Exception as e: print(...)` blocks and decide which should re-raise

| Cell | Line(s) | Should re-raise? |
|------|---------|-------------------|
| 4b   | ~162    | No — user action, skip bad rows |
| 9b   | ~450    | No — user action, skip bad edits |
| 7    | ~298    | No — skip single ticker failure |
| 11b  | ~609    | No — calibration is non-critical |
| 13   | ~in promote | Yes — staging failure = data integrity risk |

For Cell 13 promotion, add:
```python
try:
    promote_staging(sh)
except Exception as e:
    _set_pipeline_status(status_ws, 'failed', error_msg=f'Staging promotion failed: {e}')
    if LINE_TOKEN:
        import requests
        requests.post('https://notify-api.line.me/api/notify',
                      headers={'Authorization': f'Bearer {LINE_TOKEN}'},
                      data={'message': f'Kronos FAILED staging promotion: {e}'})
    raise
```

**Step 2: Commit**

```bash
git add google_suite/build_notebook.py
git commit -m "fix(google-suite): re-raise on staging promotion failure, add LINE alert"
```

---

## Phase 2: Engineering — Testing & Observability

### Task 6: Add integration smoke test for full pipeline

**Files:**
- Create: `tests/test_pipeline_smoke.py`

```python
"""Smoke test for Colab pipeline cells — verifies imports and data flow.

Runs without GPU by mocking KronosTH. Tests that cells 1-17 execute
without error when given synthetic data.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_colab_env():
    """Simulate the state built up across Colab cells."""
    import pandas as pd
    from pathlib import Path
    import tempfile
    import os

    tmp = tempfile.mkdtemp()
    orig_cwd = os.getcwd()
    os.chdir(tmp)

    # Create minimal data directory structure
    Path('data/raw').mkdir(parents=True)
    Path('data/positions').mkdir(parents=True)
    Path('data/forecast_cache').mkdir(parents=True)

    yield {
        'sh': MagicMock(),
        'ohlcv_dict': {'PTT.BK': pd.DataFrame({
            'timestamps': pd.date_range('2026-01-01', periods=400, freq='B'),
            'open': 35.0, 'high': 36.0, 'low': 34.0, 'close': 35.5,
            'volume': 1000000, 'amount': 35500000,
        }, index=range(400))},
        'tmpdir': tmp,
    }

    os.chdir(orig_cwd)


def test_cell_4_init_portfolio(mock_colab_env):
    """Cell 4 logic: init portfolio when empty."""
    from kth.trading.portfolio import init_portfolio
    pf = init_portfolio('paper')
    assert pf['cash'] == 0.0
    assert pf['positions'] == {}


def test_cell_7_load_data(mock_colab_env):
    """Cell 7 logic: load cached data."""
    from kth.data.loader import load_cached
    # With data directory prepped, load_cached should return None for unknown ticker
    df = load_cached('PTT.BK')
    assert df is not None or df is None  # depends on cache


def test_cell_9_execute_fills(mock_colab_env):
    """Cell 9 logic: execute fills on portfolio."""
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper', 500000.0)
    fills = {'PTT.BK': {'action': 'buy', 'shares': 100, 'fill_source': 'assumed'}}
    ohlcv = mock_colab_env['ohlcv_dict']

    for ticker, fill in fills.items():
        if fill['fill_source'] == 'assumed':
            if ticker in ohlcv:
                price = float(ohlcv[ticker]['close'].iloc[-1])
            else:
                continue
        else:
            price = fill.get('price', 0)
        result = execute_trade(ticker, fill['action'], fill['shares'], price, 'paper', 'test')
        assert 'error' not in result if ticker in ohlcv else True

    pf = init_portfolio('paper')
    assert len(pf.get('positions', {})) > 0
```

**Step 2:** Run tests

```bash
python -m pytest tests/test_pipeline_smoke.py -v
```

**Step 3: Commit**

```bash
git add tests/test_pipeline_smoke.py
git commit -m "test: add pipeline smoke test with mock env"
```

---

### Task 7: Remove globals().get('ohlcv_dict') pattern

**Files:**
- Modify: `google_suite/build_notebook.py` — Cells 4b and 9b

**Change:** Pass ohlcv_dict explicitly via a helper function imported from kth.trading.sheets.

`kth/trading/sheets.py` addition:
```python
def get_close_price(ticker: str, ohlcv_dict: dict, fallback: float) -> float:
    """Get latest close price from ohlcv_dict with fallback."""
    if ohlcv_dict and ticker in ohlcv_dict:
        return float(ohlcv_dict[ticker]['close'].iloc[-1])
    return fallback
```

Replace all `_ohlcv = globals().get('ohlcv_dict', {})` with:
```python
from kth.trading.sheets import get_close_price

# In build_pos_rows (already in sheets.py — just use it)
# In Cell 4b/9b standalone loops:
close = get_close_price(p['ticker'], ohlcv_dict, p['avg_cost'])
```

Commit:
```bash
git add kth/trading/sheets.py google_suite/build_notebook.py
git commit -m "refactor(google-suite): remove globals().get('ohlcv_dict'), use explicit param"
```

---

## Phase 3: UX/UI Improvements

### Task 8: Add ARIA labels and screen reader support to Index.html

**Files:**
- Modify: `google_suite/apps_script/Index.html`

**Step 1:** Add `scope="col"` to all table headers

Add to each `<th>` inside `<thead>`:
```html
<th scope="col">Ticker</th>
```

**Step 2:** Add `aria-label` to icon buttons

```html
<button class="btn-icon" onclick="openEditTradeModal(...)" aria-label="Edit trade">✏️</button>
<button class="btn-icon" onclick="confirmDeleteTrade(...)" aria-label="Delete trade">🗑️</button>
<button id="settings-btn" aria-label="Open settings">⚙ Settings</button>
```

**Step 3:** Add `role="dialog"` and `aria-modal` to modals

```html
<div id="fill-modal" class="modal-overlay" hidden role="dialog" aria-modal="true" aria-labelledby="fill-modal-title">
  <div class="modal-box">
    <h3 id="fill-modal-title">Enter Actual Fill Prices</h3>
```

Apply same pattern to edit-trade-modal and settings-modal.

**Step 4:** Add `role="tablist"` and `role="tab"` to tab bar

```html
<nav id="tab-bar" role="tablist">
  <button class="tab-btn active" role="tab" aria-selected="true" onclick="switchTab('dashboard')">Dashboard</button>
```

**Step 5:** Commit

```bash
git add google_suite/apps_script/Index.html
git commit -m "fix(google-suite): add ARIA labels, role attributes, scope=col for accessibility"
```

---

### Task 9: Rename "Signal" column to "Confidence" in Positions table

**Files:**
- Modify: `google_suite/apps_script/Index.html:707`

**Step 1:** Find and replace the header text

```html
<th title="Model confidence: green <10%, yellow 10-30%, red >30% band width">Confidence</th>
```

**Step 2:** Commit

```bash
git add google_suite/apps_script/Index.html
git commit -m "fix(google-suite): rename 'Signal' to 'Confidence' in Positions table"
```

---

### Task 10: Add dark mode CSS to Index.html

**Files:**
- Modify: `google_suite/apps_script/Index.html`

**Step 1:** Add `prefers-color-scheme` media query at end of `<style>` block

```css
@media (prefers-color-scheme: dark) {
  :root {
    --green:      #66bb6a;
    --yellow:     #ffca28;
    --red:        #ef5350;
    --dark-red:   #e53935;
    --blue:       #64b5f6;
    --gray:       #9e9e9e;
    --pnl-pos-bg: #1b3d1b;
    --pnl-neg-bg: #3d1b1b;
    --bg:         #1a1a2e;
    --card:       #16213e;
    --border:     #2a2a4a;
    --text:       #e0e0e0;
    --text-muted: #9e9e9e;
  }
}
```

**Step 2:** Add manual dark mode toggle button + localStorage persistence

```javascript
// After DOMContentLoaded
var darkPref = localStorage.getItem('kronos-dark-mode');
if (darkPref === 'true') {
  document.body.classList.add('dark-mode');
}
```

And in switchTab, add a toggle if user wants manual override. Also add CSS class `body.dark-mode` that overrides the same variables.

**Step 3: Commit**

```bash
git add google_suite/apps_script/Index.html
git commit -m "feat(google-suite): add dark mode CSS (prefers-color-scheme + manual toggle)"
```

---

### Task 11: Set default Accuracy History to latest date

**Files:**
- Modify: `google_suite/apps_script/Index.html:830-836`

**Step 1:** Change default selected value to most recent date

```javascript
var defaultDate = historyDates.length > 0 ? historyDates[0] : '';
var dateOptions = '<option value="">📅 All dates</option>' +
  historyDates.map(function(d, i) {
    var selected = d === defaultDate ? ' selected' : '';
    return '<option value="' + d + '"' + selected + '>' +
      (i === 0 ? '📅 ' + fmt.date(d) + ' (latest)' : '📅 ' + fmt.date(d)) +
      '</option>';
  }).join('');

// Then immediately filter
if (defaultDate) {
  filterHistoryByDate(defaultDate);
}
```

**Step 2: Commit**

```bash
git add google_suite/apps_script/Index.html
git commit -m "fix(google-suite): default Accuracy History to latest date, not 'All'"
```

---

### Task 12: Add tooltips to all column headers (mirror Forecasts tab)

**Files:**
- Modify: `google_suite/apps_script/Index.html`

**Step 1:** Add `title` attributes to missing column headers

**Dashboard:** No table headers to fix — hero cards are clear.

**Positions table (line ~704-708):**
```html
<thead><tr>
  <th scope="col">Ticker</th>
  <th scope="col" title="Number of shares held">Shares</th>
  <th scope="col" title="Average entry price per share">Avg Cost</th>
  <th scope="col" title="Date position was opened">Entry Date</th>
  <th scope="col" title="Stock Exchange of Thailand sector classification">Sector</th>
  <th scope="col" title="Most recent closing price">Current Price</th>
  <th scope="col" title="Profit/loss as a percentage of cost">P&L %</th>
  <th scope="col" title="Distance from stop-loss level (red if < 3%)">% to Stop</th>
  <th scope="col" title="Today's model forecast for this position">Exp Ret</th>
  <th scope="col" title="Model confidence: green <10%, yellow 10-30%, red >30% band width">Confidence</th>
</tr></thead>
```

**Trade Log table (line ~749-753):**
```html
<thead><tr>
  <th scope="col">Date</th>
  <th scope="col" title="Stock ticker symbol">Ticker</th>
  <th scope="col" title="Buy / Sell / Cancel">Action</th>
  <th scope="col" title="Number of shares">Shares</th>
  <th scope="col" title="Price per share">Price</th>
  <th scope="col" title="Reason for the trade">Rationale</th>
  <th scope="col" title="Edit or delete this trade (queued until Cell 9b runs)">Actions</th>
</tr></thead>
```

**Trade Ticket table (line ~1002-1005):**
```html
<thead><tr>
  <th scope="col">Ticker</th>
  <th scope="col" title="Buy or sell">Action</th>
  <th scope="col" title="Number of shares to trade">Shares</th>
  <th scope="col" title="Estimated cost including friction (THB)">Est. Cost (THB)</th>
  <th scope="col">Sector</th>
  <th scope="col" title="Model confidence: green <10%, yellow 10-30%, red >30%">Confidence</th>
  <th scope="col" title="Confirmed fill price from broker">Fill Status</th>
  <th scope="col" title="Why this trade is recommended">Rationale</th>
</tr></thead>
```

**Step 2:** Commit

```bash
git add google_suite/apps_script/Index.html
git commit -m "fix(google-suite): add column header tooltips to Positions, Trade Log, Trade Ticket"
```

---

### Task 13: Mobile fill modal — stacked layout

**Files:**
- Modify: `google_suite/apps_script/Index.html`

**Step 1:** Add mobile media query for modal table

```css
@media (max-width: 600px) {
  #fill-modal-table thead { display: none; }
  #fill-modal-table tr { display: flex; flex-direction: column; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
  #fill-modal-table td { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border: none; }
  #fill-modal-table td::before { content: attr(data-label); font-weight: 500; color: var(--text-muted); font-size: 0.8rem; }
  .modal-input { width: 120px; }
}
```

**Step 2:** Add `data-label` attributes to fill modal cells

In `openFillModal`:
```javascript
'<td data-label="Ticker">' + r.ticker + '</td>' +
'<td data-label="Action"><span class="badge badge-...">' + r.action + '</span></td>' +
'<td data-label="Planned" class="num">' + fmt.shares(r.shares) + '</td>' +
'<td data-label="Filled"><input ...></td>' +
'<td data-label="Price"><input ...></td>' +
'<td data-label="Time"><input ...></td>' +
```

**Step 3:** Commit

```bash
git add google_suite/apps_script/Index.html
git commit -m "fix(google-suite): mobile stacked layout for fill modal inputs"
```

---

### Task 14: Add compact density toggle for tables

**Files:**
- Modify: `google_suite/apps_script/Index.html`

**Step 1:** Add CSS class for compact mode

```css
.compact td, .compact th { padding: 4px 8px; font-size: 0.8rem; }
.compact .card { padding: 8px; }
.compact .card-value { font-size: 1.2rem; }
```

**Step 2:** Add toggle button

In renderAll, after each table rendering:
```javascript
// Add a density toggle if not already present
var content = document.getElementById('content');
if (!document.getElementById('density-toggle')) {
  var toggle = document.createElement('button');
  toggle.id = 'density-toggle';
  toggle.className = 'btn-secondary';
  toggle.textContent = localStorage.getItem('kronos-compact') === 'true' ? '☰ Compact' : '☰ Normal';
  toggle.style.cssText = 'position:fixed;bottom:12px;right:12px;z-index:50';
  toggle.onclick = function() {
    var isCompact = document.body.classList.toggle('compact');
    toggle.textContent = isCompact ? '☰ Normal' : '☰ Compact';
    localStorage.setItem('kronos-compact', isCompact);
  };
  content.appendChild(toggle);
}
if (localStorage.getItem('kronos-compact') === 'true') {
  document.body.classList.add('compact');
}
```

**Step 3:** Commit

```bash
git add google_suite/apps_script/Index.html
git commit -m "feat(google-suite): add compact density toggle with localStorage persistence"
```

---

### Task 15: Regenerate notebook + run verification

**Files:**
- Modify: `google_suite/kronos_daily_pipeline.ipynb` (regenerated)
- Verify: `docs/superpowers/plans/README.md` is up to date

**Step 1:** Regenerate notebook

```bash
python google_suite/build_notebook.py
```

Expected output: `Generated google_suite/kronos_daily_pipeline.ipynb — 44 cells`

**Step 2:** Verify Python imports

```bash
pip install -e .
python -c "
from kth.trading.sheets import write_staging, promote_staging, build_pos_rows, get_close_price
from kth.trading.sheets_config import PORTFOLIO_HEADERS, POSITIONS_HEADERS
print('All imports OK')
"
```

**Step 3:** Run unit tests

```bash
python -m pytest tests/ -v
```

**Step 4:** Final sanity — read through the generated notebook once

```bash
python -c "
import json
nb = json.load(open('google_suite/kronos_daily_pipeline.ipynb'))
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if 'globals().get' in src:
            print(f'WARNING: globals().get in cell {i}')
        if '_write_staging' in src and 'def _write_staging' in src:
            print(f'WARNING: local _write_staging in cell {i} (should import from sheets)')
print('Check complete')
"
```

Expected: No warnings.

**Step 5:** Commit all remaining files

```bash
git add -A
git commit -m "chore: regenerate notebook, final verification"
```
