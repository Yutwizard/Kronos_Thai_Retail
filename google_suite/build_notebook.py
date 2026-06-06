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
import json, hashlib

CELLS = []

def code(src):
    CELLS.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"id": hashlib.md5(src.encode()).hexdigest()[:12]},
        "outputs": [],
        "source": src.splitlines(keepends=True),
    })

def md(src):
    CELLS.append({
        "cell_type": "markdown",
        "metadata": {"id": hashlib.md5(src.encode()).hexdigest()[:12]},
        "source": src.splitlines(keepends=True),
    })

md("""# Kronos-TH Daily Pipeline

19-cell Colab notebook. Run All each morning (Bangkok time, UTC+7).

**Prerequisites:**
1. Runtime > Change runtime type > T4 GPU
2. Colab Secrets configured: `KRONOS_SPREADSHEET_ID`, `LINE_NOTIFY_TOKEN` (optional)
3. Google Drive mounted with the Kronos_Thai_Retail repo

**Architecture:** JSON-bridge pattern — Sheets → Drive JSON → existing kth functions → Drive JSON → Sheets
""")

code(r"""from google.colab import drive
drive.mount('/content/drive')

import os, subprocess, sys

KTH_REPO = '/content/drive/MyDrive/Kronos_Thai_Retail'  # ← CHANGE IF YOUR PATH IS DIFFERENT
os.chdir(KTH_REPO)  # CRITICAL: makes Path("data/...") in kth modules resolve to Drive

print("Working directory:", os.getcwd())
print("Contents:", os.listdir('.'))

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
                       'gspread', 'google-auth', 'pandas', 'yfinance'])
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-e', KTH_REPO])
print("All dependencies installed.")
""")

code(r"""from google.colab import userdata

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
""")

code(r"""from google.colab import auth
auth.authenticate_user()

from google.auth import default
import gspread

creds, _ = default()
gc = gspread.Client(auth=creds)
sh = gc.open_by_key(SPREADSHEET_ID)
print("Connected to spreadsheet:", sh.title)
print("Sheets found:", [ws.title for ws in sh.worksheets()])
""")

md("""## Cell 4 — Initialize Portfolio if Empty""")

code(r"""from datetime import date
from kth.trading.portfolio import MODEL_VERSION

portfolio_ws = sh.worksheet('Portfolio')
rows = portfolio_ws.get_all_values()

if len(rows) <= 1:
    portfolio_ws.append_row([
        INITIAL_CAPITAL,
        INITIAL_CAPITAL,
        'paper',
        MODEL_VERSION,
        str(date.today()),
    ])
    print(f"First run: portfolio initialised at ฿{INITIAL_CAPITAL:,.0f}")
else:
    print(f"Portfolio already initialised: ฿{float(rows[1][0]):,.0f} cash")
""")

md("""## Cell 5 — Set Pipeline Status: Running""")

code(r"""import time
from datetime import datetime

def _set_pipeline_status(ws, status, error_msg='', sheets_updated='', duration=''):
    ws.update('A1:E2', [
        ['last_run_timestamp', 'status', 'duration_seconds', 'error_message', 'sheets_updated'],
        [datetime.now().isoformat(), status, str(duration), str(error_msg), str(sheets_updated)],
    ])

status_ws = sh.worksheet('Pipeline Status')
_set_pipeline_status(status_ws, 'running')
pipeline_start = time.time()
print("Pipeline started at", datetime.now().strftime("%H:%M:%S BKK"))
""")

md("""## Cell 6 — Read Prior-Day Fills""")

code(r"""ticket_ws = sh.worksheet('Trade Ticket')
rows = ticket_ws.get_all_values()
headers = rows[0] if rows else []
fills = {}

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
            fills[ticker] = {'action': action, 'fill_source': 'assumed'}
            print(f"  ⚠ No fills for {ticker} ({action}) — will use forecast close")

confirmed_count = sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')
assumed_count   = sum(1 for f in fills.values() if f['fill_source'] == 'assumed')
print(f"Fills: {confirmed_count} confirmed, {assumed_count} assumed, {len(fills)} total")
""")

md("""## Cell 7 — Download Data""")

code(r"""from kth.data.loader import download_universe, load_cached
from kth.data.universe import get_all_tickers

print("Downloading fresh OHLCV data (takes ~2 min on first run)…")
download_universe()
print("Download complete.")

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
""")

md("""## Cell 8 — Run Forecasts

**Requires T4 GPU runtime.** On CPU this cell crashes.""")

code(r"""from datetime import date
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
""")

md("""## Cell 9 — Update Portfolio State ← MUST RUN BEFORE CELL 10""")

code(r"""import json as _json
from datetime import date
from pathlib import Path
from kth.trading.portfolio import execute_trade, init_portfolio, MODEL_VERSION

today_str = str(date.today())

pf_rows  = sh.worksheet('Portfolio').get_all_values()
pos_rows = sh.worksheet('Positions').get_all_values()
eq_rows  = sh.worksheet('Equity Curve').get_all_values()
rm_rows  = sh.worksheet('Risk Metrics').get_all_values()

pf = init_portfolio('paper')

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

path = Path('data/positions/paper_portfolio.json')
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'w') as f:
    _json.dump(pf, f, indent=2, default=str)
print(f"Portfolio synced: ฿{pf['cash']:,.0f} cash, {len(pf.get('positions',{}))} positions, "
      f"frozen={pf.get('frozen', False)}")

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

pf = init_portfolio('paper')
print(f"After fills: ฿{pf['cash']:,.0f} cash, {len(pf.get('positions',{}))} positions")
""")

md("""## Cell 10 — Generate Trade Ticket ← RUNS AFTER CELL 9""")

code(r"""from kth.trading.trade_gen import generate_trade_ticket

ticket_data = generate_trade_ticket(report_date=today_str)

exits   = ticket_data.get('exits', [])
reduces = ticket_data.get('reduces', [])
buys    = ticket_data.get('buys', [])
print(f"Ticket: {len(exits)} exits  {len(reduces)} reduces  {len(buys)} buys")
if ticket_data.get('t2_warning'):
    print(f"T+2 WARNING: {ticket_data['t2_warning']}")
if ticket_data.get('banner'):
    print(f"BANNER: {ticket_data['banner']}")
""")

md("""## Cell 11 — Compute Metrics""")

code(r"""import pandas as pd
from kth.trading.portfolio import compute_metrics, get_trade_log
from kth.backtest.metrics import compute_sortino

metrics = compute_metrics('paper')

equity_vals = [e['value'] for e in pf.get('equity_curve', [])]
equity_series = pd.Series(equity_vals) if equity_vals else pd.Series([INITIAL_CAPITAL])
daily_returns = equity_series.pct_change().dropna()

if len(equity_series) >= 2 and metrics.get('drawdown', 0) < 0:
    n_years = max(len(equity_series) / 252, 0.01)
    cagr    = (equity_series.iloc[-1] / equity_series.iloc[0]) ** (1 / n_years) - 1
    metrics['calmar'] = round(cagr / abs(metrics['drawdown']), 4)
else:
    metrics['calmar'] = 0.0

metrics['sortino'] = round(compute_sortino(daily_returns), 4) \
                     if len(daily_returns) >= 20 else 0.0

metrics['frozen'] = pf.get('frozen', False)

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
""")

md("""## Cell 12 — Validate Data""")

code(r"""from kth.trading.portfolio import get_positions

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
""")

md("""## Cell 13 — Write to Staging Sheets""")

code(r"""from kth.trading.portfolio import get_positions, init_portfolio
from kth.trading.trade_gen import load_forecasts
from kth.data.universe import get_sector, get_ticker_class, FRICTION

def _write_staging(ws_name, headers, rows):
    ws = sh.worksheet(ws_name)
    ws.clear()
    ws.append_row(headers)
    if rows:
        ws.append_rows(rows)
    time.sleep(1)

pf_data = init_portfolio('paper')
_write_staging('Portfolio_staging',
    ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
    [[pf_data['cash'], pf_data['initial_capital'], 'paper', MODEL_VERSION, today_str]])

pos = get_positions('paper')
pos_rows = []
for p in pos['positions']:
    close   = float(ohlcv_dict[p['ticker']]['close'].iloc[-1]) \
              if p['ticker'] in ohlcv_dict else p['avg_cost']
    pnl     = (close - p['avg_cost']) * p['shares']
    pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0
# NOTE: `current_price` and `pct_to_stoploss` are computed locally from
# `ohlcv_dict[ticker]['close'].iloc[-1]`, NOT from `get_positions()`.
# `get_positions()` returns `mark` (not `current_price`) and no stop-loss column.
# Do not refactor to use `get_positions()` here without updating
# the Positions sheet schema and Index.html renderPositions().
    pos_rows.append([
        p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
        get_sector(p['ticker']), round(close, 2),
        round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
    ])
_write_staging('Positions_staging',
    ['ticker','shares','avg_cost','entry_date','sector','current_price','pnl','pnl_pct','pct_to_stoploss'],
    pos_rows)

fc_rows      = load_forecasts(today_str)
fc_by_ticker = {r['ticker']: r for r in fc_rows}
_write_staging('Forecasts_staging',
    ['date_updated','ticker','rank_score','exp_ret','band_width','confidence',
     'net_return','p5','p50','p95','sector'],
    [[today_str, r['ticker'], r['rank_score'], r['exp_ret'], r['band_width'],
      r['confidence'], r['net_ret'], r['p5_close'], r['p50_close'], r['p95_close'],
      get_sector(r['ticker'])] for r in fc_rows])

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
        '', '', '',
    ])
_write_staging('Trade Ticket_staging',
    ['ticker','action','shares','est_cost_thb','rationale','sector','confidence',
     'filled_price','filled_shares','fill_timestamp'],
    tt_rows)

equity = pos['total_value']
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
        round(metrics.get('calmar', 0), 4),
        round(metrics.get('sortino', 0), 4),
        round(metrics.get('drawdown_velocity', 0), 4),
        metrics.get('allocation_band', 'NEUTRAL'),
        metrics.get('allocation_pct', 0.10),
        metrics.get('market_state', 'Normal'),
        1 if metrics.get('frozen') else 0,
        round(metrics.get('bootstrap_pvalue', 1.0), 4),
        round(metrics.get('friction_ytd_pct', 0), 4),
        round(metrics.get('friction_ytd_thb', 0), 2),
    ]])

print("All 5 staging sheets written.")
""")

md("""## Cell 14 — Promote Staging to Live Sheets""")

code(r"""STAGING_MAP = {
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
        live_ws.update('A1', data)
    staging_ws.clear()
    time.sleep(1)
print("Staging promoted to live sheets.")
""")

md("""## Cell 15 — Append Trade Log""")

code(r"""import hashlib
from kth.trading.portfolio import get_trade_log

tl_ws    = sh.worksheet('Trade Log')
all_rows = tl_ws.get_all_values()
existing_ids = set(r[8] for r in all_rows[1:] if len(r) > 8 and r[8])

trade_log = get_trade_log('paper')
new_rows  = []

for trade in trade_log[-50:]:
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
        '',
    ])
    existing_ids.add(trade_id)

if new_rows:
    tl_ws.append_rows(new_rows)
print(f"Trade Log: {len(new_rows)} new entries appended.")
""")

md("""## Cell 16 — Update & Append Forecast History""")

code(r"""fh_ws   = sh.worksheet('Forecast History')
fh_data = fh_ws.get_all_values()
fh_h    = fh_data[0] if fh_data else []
col     = {h: i for i, h in enumerate(fh_h)}

updates = []
for list_idx, row in enumerate(fh_data[1:], start=2):
    if not row: continue
    if row[col.get('actual_return', 5)] != '': continue
    ticker = row[col.get('ticker', 1)]
    if ticker in failed_tickers or ticker not in ohlcv_dict: continue
    try:
        entry_close = float(row[col['entry_close']])
        pred_return = float(row[col['predicted_return']])
        today_close = float(ohlcv_dict[ticker]['close'].iloc[-1])
        act_ret     = (today_close - entry_close) / entry_close
        correct     = 1 if (act_ret > 0) == (pred_return > 0) else 0
        ar_col = col['actual_return'] + 1
        wc_col = col['was_correct'] + 1
        updates.append({
            'range':  f'{chr(64 + ar_col)}{list_idx}:{chr(64 + wc_col)}{list_idx}',
            'values': [[round(act_ret, 4), correct]],
        })
    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        continue

if updates:
    fh_ws.batch_update(updates)
    print(f"Forecast History: resolved {len(updates)} prior-day rows.")

today_rows = [
    [today_str, r['ticker'],
     'up' if r['exp_ret'] > 0 else 'down',
     round(r['exp_ret'], 4),
     round(r['close'], 2),
     '',
     '']
    for r in fc_rows if r['ticker'] not in failed_tickers
]
if today_rows:
    fh_ws.append_rows(today_rows)
print(f"Forecast History: appended {len(today_rows)} predictions for {today_str}.")
""")

md("""## Cell 17 — Set Pipeline Status: Completed""")

code(r"""duration = round(time.time() - pipeline_start, 1)
_set_pipeline_status(
    status_ws, 'completed',
    duration=duration,
    sheets_updated=','.join(STAGING_MAP.values()) + ',Trade Log,Forecast History',
)
print(f"Pipeline completed in {duration}s.")
""")

md("""## Cell 18 — LINE Notify""")

code(r"""def _line_notify(msg):
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
""")

md("""## Cell 19 — Summary""")

code(r"""confirmed = sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')
assumed   = sum(1 for f in fills.values() if f['fill_source'] == 'assumed')
sep = '=' * 54
print(f'''
{sep}
  KRONOS-TH PIPELINE COMPLETE
{sep}
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
{sep}
''')""")

# Build notebook
nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {
            "provenance": [],
            "gpuType": "T4",
            "toc_visible": True,
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": CELLS,
}

path = __file__.replace('build_notebook.py', 'kronos_daily_pipeline.ipynb')
with open(path, 'w') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"Generated {path} — {len(CELLS)} cells")
