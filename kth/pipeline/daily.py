"""Daily pipeline orchestration — lifts Colab cell bodies into one testable function."""
import hashlib
import json
import os
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from kth.data.universe import get_all_tickers_including_features, get_sector, get_currency_group, get_friction
from kth.trading.portfolio import (
    init_portfolio, get_positions, get_trade_log, compute_metrics, MODEL_VERSION,
    reset_portfolio, execute_trade, edit_trade, delete_trade,
)
from kth.trading.trade_gen import generate_trade_ticket, load_trade_ticket, load_forecasts
from kth.trading.sheets import write_staging, promote_staging, build_pos_rows, STAGING_MAP
from kth.trading.sheets_config import (
    PORTFOLIO_HEADERS, POSITIONS_HEADERS, EQUITY_CURVE_HEADERS,
    FORECASTS_HEADERS, TRADE_TICKET_HEADERS, RISK_METRICS_HEADERS,
    FORECAST_HISTORY_HEADERS, CALIBRATION_HEADERS, TRADE_LOG_HEADERS,
)


CACHE_SLUG = "NeoQuasar_Kronos-small"


def _col_to_letter(col_index: int) -> str:
    """Convert 0-based column index to A1 letter notation (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    col = col_index + 1
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(65 + rem) + result
    return result


def _set_pipeline_status(ws, status: str, error_msg: str = "",
                         sheets_updated: str = "", duration: str = ""):
    ws.update('A1:E2', [
        ['last_run_timestamp', 'status', 'duration_seconds',
         'error_message', 'sheets_updated'],
        [datetime.now().isoformat(), status, str(duration),
         str(error_msg), str(sheets_updated)],
    ])


def _apply_capital_reset(sh, mode: str):
    capital_reset_ws = sh.worksheet('Capital Reset')
    data = capital_reset_ws.get_all_values()
    headers = ['date', 'action', 'capital', 'confirm_text', 'requested_at']
    if not data:
        capital_reset_ws.append_row(headers)
        return
    for row in data[1:]:
        if not row or not row[0]:
            continue
        action = row[1]
        capital = float(row[2])
        confirm = row[3]
        if confirm not in ('RESET', 'SETUP'):
            print(f"  Skipping reset row with invalid confirm_text: {confirm}")
            continue
        try:
            reset_portfolio(mode, capital)
            print(f"  Applied {action}: capital={capital:,.0f} THB (confirm={confirm})")
        except Exception as e:
            print(f"  Reset failed: {e}")
    capital_reset_ws.clear()
    capital_reset_ws.append_row(headers)
    print("Capital Reset cleared.")


def _sync_trade_log_from_sheets(sh):
    """Rebuild trade_log.csv from the Trade Log sheet only if no CSV exists yet.
    Translates sheet headers to the CSV format expected by portfolio.edit_trade()."""
    path = Path('data/positions/trade_log.csv')
    if path.exists():
        return
    import csv
    tl_ws = sh.worksheet('Trade Log')
    rows = tl_ws.get_all_values()
    if len(rows) <= 1:
        return
    sheet_header = rows[0]
    col_map = {h: i for i, h in enumerate(sheet_header)}
    csv_header = ['date', 'ticker', 'action', 'shares', 'price', 'order_type',
                  'mode', 'rationale', 'friction_cost', 'model_version', 'forecast_date']
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(csv_header)
        for row in rows[1:]:
            ts = row[col_map.get('timestamp', 0)] if len(row) > 0 else ''
            ticker = row[col_map.get('ticker', 1)] if len(row) > 1 else ''
            action = row[col_map.get('action', 2)] if len(row) > 2 else ''
            shares = row[col_map.get('shares', 3)] if len(row) > 3 else ''
            price = row[col_map.get('price', 4)] if len(row) > 4 else ''
            rationale = row[col_map.get('rationale', 5)] if len(row) > 5 else ''
            friction = row[col_map.get('friction_cost', 6)] if len(row) > 6 else ''
            mv = row[col_map.get('model_version', 7)] if len(row) > 7 else ''
            tid = row[col_map.get('id', 8)] if len(row) > 8 else ''
            w.writerow([ts, ticker, action, shares, price, 'market',
                        'paper', rationale, friction, mv, ts])


def _apply_trade_edits(sh, mode: str):
    _sync_trade_log_from_sheets(sh)
    trade_edits_ws = sh.worksheet('Trade Edits')
    data = trade_edits_ws.get_all_values()
    headers = ['date', 'action', 'index', 'ticker', 'shares', 'price', 'ref_id', 'requested_at', 'new_date']
    if not data:
        trade_edits_ws.append_row(headers)
        return
    for row in data[1:]:
        if not row or not row[0]:
            continue
        action = row[1]
        if action == 'edit':
            new_date = row[8].strip() if len(row) > 8 and row[8] else None
            result = edit_trade(int(row[2]), new_price=float(row[5]),
                                new_shares=int(float(row[4])), mode=mode, new_date=new_date)
            if 'error' in result:
                print(f"  Edit failed for row {row[2]}: {result['error']}")
            else:
                print(f"  Applied edit: {row[3]} -> shares={row[4]} price={row[5]}")
        elif action == 'CANCEL':
            result = delete_trade(int(row[2]), mode)
            if 'error' in result:
                print(f"  Delete failed for row {row[2]}: {result['error']}")
            else:
                print(f"  Applied delete: index {row[2]}")
    trade_edits_ws.clear()
    trade_edits_ws.append_row(headers)
    print("Trade Edits cleared.")


def _apply_manual_trades(sh, mode: str):
    """Execute trades queued from the dashboard's 'Add Manual Trade' modal.

    Reads the 'Manual Trades' staging sheet (date, action, ticker, shares, price,
    requested_at), calls execute_trade for each, then clears the sheet. The tab is
    optional — older spreadsheets without it are skipped silently.
    """
    headers = ['date', 'action', 'ticker', 'shares', 'price', 'requested_at']
    try:
        ws = sh.worksheet('Manual Trades')
    except Exception:
        return  # tab not present in this spreadsheet
    data = ws.get_all_values()
    if not data:
        ws.append_row(headers)
        return
    applied = 0
    for row in data[1:]:
        if not row or not row[0]:
            continue
        try:
            action = row[1]
            ticker = row[2]
            shares = int(float(row[3]))
            price = float(row[4])
        except (IndexError, ValueError) as e:
            print(f"  Manual trade skipped (bad row {row}): {e}")
            continue
        result = execute_trade(ticker, action, shares, price, mode,
                               order_type='market', rationale='manual entry')
        if result.get('error'):
            print(f"  Manual trade failed: {action} {shares} {ticker} — {result['error']}")
        else:
            applied += 1
            print(f"  Applied manual trade: {action} {shares} {ticker} @ {price}")
    ws.clear()
    ws.append_row(headers)
    if applied:
        print(f"Manual Trades: applied {applied}, sheet cleared.")


def _read_fills(sh) -> dict:
    ticket_ws = sh.worksheet('Trade Ticket')
    rows = ticket_ws.get_all_values()
    headers = rows[0] if rows else []
    fills = {}
    if len(rows) > 1:
        col = {h: i for i, h in enumerate(headers)}
        for row in rows[1:]:
            if len(row) < len(headers):
                continue
            ticker = row[col.get('ticker', 0)]
            if not ticker:
                continue
            fp = row[col['filled_price']] if 'filled_price' in col else ''
            fs = row[col['filled_shares']] if 'filled_shares' in col else ''
            ft = row[col['fill_timestamp']] if 'fill_timestamp' in col else ''
            action = row[col['action']] if 'action' in col else 'buy'
            shares = int(float(row[col['shares']])) if 'shares' in col and row[col['shares']] else 0
            if fp and fs and ft:
                fills[ticker] = {
                    'price': float(fp), 'shares': int(float(fs)),
                    'action': action, 'timestamp': ft, 'fill_source': 'confirmed',
                }
            else:
                fills[ticker] = {
                    'action': action, 'shares': shares, 'fill_source': 'assumed',
                }
                print(f"  No fills for {ticker} ({action}) — will use forecast close, shares={shares}")
    confirmed = sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')
    assumed = sum(1 for f in fills.values() if f['fill_source'] == 'assumed')
    print(f"Fills: {confirmed} confirmed, {assumed} assumed, {len(fills)} total")
    return fills


def _rebuild_state_from_sheets(sh, mode: str, today_str: str = ""):
    if not today_str:
        today_str = str(date.today())
    pf_rows = sh.worksheet('Portfolio').get_all_values()
    pos_rows = sh.worksheet('Positions').get_all_values()
    eq_rows = sh.worksheet('Equity Curve').get_all_values()
    rm_rows = sh.worksheet('Risk Metrics').get_all_values()

    pf = init_portfolio(mode)
    if len(pf_rows) > 1:
        r = pf_rows[1]
        pf['cash'] = float(r[0])
        pf['initial_capital'] = float(r[1])
        pf['mode'] = r[2]
        pf['model_version'] = r[3]
    if len(pos_rows) > 1:
        ph = pos_rows[0]
        pf['positions'] = {}
        for r in pos_rows[1:]:
            row = dict(zip(ph, r))
            if not row.get('ticker'):
                continue
            pf['positions'][row['ticker']] = {
                'shares': int(float(row['shares'])),
                'avg_cost': float(row['avg_cost']),
                'entry_date': row.get('entry_date', today_str),
            }
    if len(eq_rows) > 1:
        pf['equity_curve'] = [
            {'date': r[0], 'value': float(r[1])}
            for r in eq_rows[1:] if r[0] and r[1]
        ]
    if len(rm_rows) > 1:
        rm_h = rm_rows[0]
        last_rm = dict(zip(rm_h, rm_rows[-1]))
        pf['frozen'] = bool(int(float(last_rm.get('is_frozen', 0) or 0)))
        pf['frozen_at'] = last_rm.get('date', '') if pf['frozen'] else None
    path = Path('data/positions/paper_portfolio.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(pf, f, indent=2, default=str)
    print(f"Portfolio synced from sheets: ฿{pf['cash']:,.0f} cash, "
          f"{len(pf.get('positions', {}))} positions, frozen={pf.get('frozen', False)}")


def _apply_fills(fills: dict, ohlcv_dict: dict, mode: str):
    for ticker, fill in fills.items():
        if fill['fill_source'] == 'assumed':
            if ticker not in ohlcv_dict:
                continue
            price = float(ohlcv_dict[ticker]['close'].iloc[-1])
            note = '[fill_source=assumed]'
        else:
            price = fill['price']
            note = f'[fill_source=confirmed @{fill["timestamp"]}]'
        result = execute_trade(
            ticker=ticker, action=fill.get('action', 'buy'),
            shares=fill['shares'], fill_price=price,
            mode=mode, rationale=f'GS-fill {note}',
        )
        if 'error' in result:
            print(f"  Trade error for {ticker}: {result['error']}")
    pf = init_portfolio(mode)
    print(f"After fills: ฿{pf['cash']:,.0f} cash, {len(pf.get('positions', {}))} positions")


def _append_trade_log(sh, mode: str):
    tl_ws = sh.worksheet('Trade Log')
    all_rows = tl_ws.get_all_values()
    existing_ids = set(r[8] for r in all_rows[1:] if len(r) > 8 and r[8])
    trade_log = get_trade_log(mode)
    new_rows = []
    for trade in trade_log[-50:]:
        raw = f"{trade['date']}_{trade['ticker']}_{trade['action']}"
        hex4 = hashlib.md5(raw.encode()).hexdigest()[:4]
        trade_id = f"{trade['date'].replace('-', '')}_{trade['ticker']}_{trade['action']}_{hex4}"
        if trade_id in existing_ids:
            continue
        new_rows.append([
            trade['date'], trade['ticker'], trade['action'],
            trade['shares'], trade['price'],
            trade.get('rationale', ''), trade.get('friction_cost', 0),
            trade.get('model_version', MODEL_VERSION), trade_id, '',
        ])
        existing_ids.add(trade_id)
    if new_rows:
        tl_ws.append_rows(new_rows)
    print(f"Trade Log: {len(new_rows)} new entries appended.")


def _compute_calibration_data(ohlcv_dict: dict, today_str: str) -> dict | None:
    try:
        from kth.backtest.metrics import compute_calibration
        cal = compute_calibration(
            forecast_cache_dir=Path('data/forecast_cache') / CACHE_SLUG,
            raw_data_dir=Path('data/raw'),
            tickers=list(ohlcv_dict.keys()),
        )
        cov = cal.get('coverage')
        n = cal.get('n_samples', 0)
        status = cal.get('status', 'insufficient_data')
        if n > 0 and cov is not None:
            if status == 'insufficient_data':
                banner_status = 'insufficient_data'
            elif cov < 0.80:
                banner_status = 'diverged'
            elif cov < 0.85:
                banner_status = 'monitor'
            elif cov > 0.95:
                banner_status = 'overconfident'
            else:
                banner_status = 'on_track'
            return {'date': today_str, 'coverage': round(cov, 4),
                    'n_samples': n, 'status': banner_status}
        return None
    except Exception as e:
        print(f"Calibration: skipped ({e})")
        return None


def _validate_positions(mode: str) -> list[str]:
    pos = get_positions(mode)
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
    return errors


def _write_risk_metrics_row(metrics: dict, pf_data: dict, today_str: str):
    equity = pf_data.get('total_value', pf_data.get('cash', 0))
    dd_vel = metrics.get('drawdown_velocity', 0)
    if isinstance(dd_vel, dict):
        dd_vel = dd_vel.get('velocity', 0)
    bp = metrics.get('bootstrap_pvalue', 1.0)
    if isinstance(bp, dict):
        bp = bp.get('pvalue', 1.0) or 1.0
    return [[
        today_str,
        round(equity, 2),
        round(pf_data['cash'], 2),
        round(metrics.get('exposure', 0), 4),
        round(metrics.get('sharpe', 0), 4),
        round(metrics.get('drawdown', 0), 4),
        round(metrics.get('pnl_mtd_pct', 0), 4),
        round(metrics.get('win_rate', 0), 4),
        round(metrics.get('calmar', 0), 4),
        round(metrics.get('sortino', 0), 4),
        round(dd_vel, 4),
        metrics.get('allocation_band', 'NEUTRAL'),
        metrics.get('allocation_pct', 0.10),
        metrics.get('market_state', 'Normal'),
        1 if metrics.get('frozen') else 0,
        round(bp, 4),
        round(metrics.get('friction_ytd_pct', 0), 4),
        round(metrics.get('friction_ytd_thb', 0), 2),
    ]]


def _write_forecast_history(sh, ohlcv_dict: dict, fc_rows: list,
                            failed_tickers: set, today_str: str):
    fh_ws = sh.worksheet('Forecast History')
    fh_data = fh_ws.get_all_values()
    fh_h = fh_data[0] if fh_data else []
    col = {h: i for i, h in enumerate(fh_h)}
    updates = []
    for list_idx, row in enumerate(fh_data[1:], start=2):
        if not row:
            continue
        if row[col.get('actual_return', 5)] != '':
            continue
        ticker = row[col.get('ticker', 1)]
        if ticker in failed_tickers or ticker not in ohlcv_dict:
            continue
        try:
            entry_close = float(row[col['entry_close']])
            pred_return = float(row[col['predicted_return']])
            today_close = float(ohlcv_dict[ticker]['close'].iloc[-1])
            act_ret = (today_close - entry_close) / entry_close
            correct = 1 if (act_ret > 0) == (pred_return > 0) else 0
            ar_col_letter = _col_to_letter(col['actual_return'])
            wc_col_letter = _col_to_letter(col['was_correct'])
            updates.append({
                'range': f'{ar_col_letter}{list_idx}:{wc_col_letter}{list_idx}',
                'values': [[round(act_ret, 4), correct]],
            })
        except (ValueError, KeyError, IndexError, ZeroDivisionError):
            continue
    if updates:
        fh_ws.batch_update(updates)
        print(f"Forecast History: resolved {len(updates)} prior-day rows.")
    # Idempotent append: skip (date,ticker) pairs already present for today so a
    # same-day re-run or scheduler retry doesn't duplicate the day's predictions.
    already_today = {
        row[col.get('ticker', 1)]
        for row in fh_data[1:]
        if row and len(row) > 1 and row[col.get('date', 0)] == today_str
    }
    today_rows = [
        [today_str, r['ticker'],
         'up' if r['exp_ret'] > 0 else 'down',
         round(r['exp_ret'], 4), round(r['close'], 2), '', '']
        for r in fc_rows
        if r['ticker'] not in failed_tickers and r['ticker'] not in already_today
    ]
    if today_rows:
        fh_ws.append_rows(today_rows)
    print(f"Forecast History: appended {len(today_rows)} predictions for {today_str}.")


def upsert_by_date(ws_rows: list[list], header: list, new_row: list,
                   date_col: int = 0) -> list[list]:
    if not header or not ws_rows:
        return [header, new_row] if header else [new_row]
    new_date = new_row[date_col] if date_col < len(new_row) else None
    replaced = False
    result = [ws_rows[0]]
    for existing in ws_rows[1:]:
        if existing and date_col < len(existing) and existing[date_col] == new_date:
            result.append(new_row)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(new_row)
    return result


def _write_staging_for_equity_curve(sh, pf_data: dict, today_str: str):
    eq_rows = sh.worksheet('Equity Curve').get_all_values()
    eq_header = EQUITY_CURVE_HEADERS
    equity = pf_data.get('total_value', pf_data.get('cash', 0))
    new_row = [today_str, round(equity, 2), round(pf_data['cash'], 2),
               round(equity - pf_data['cash'], 2)]
    all_rows = upsert_by_date(eq_rows if eq_rows else [], eq_header, new_row)
    ws = sh.worksheet('Equity Curve_staging')
    ws.clear()
    ws.update('A1', all_rows)


def run_daily_pipeline(gc, spreadsheet_id, *, model, data_loader,
                       today: date, work_dir: str = ".", notifier=None,
                       staging_sleep: float = 1.0) -> dict:
    cwd = os.getcwd()
    os.chdir(work_dir)
    pipeline_start = time.time()
    ohlcv_dict = {}
    fc_rows = []
    ticket_data = {"exits": [], "reduces": [], "buys": []}
    pf_data = {}
    metrics = {}
    sh = None
    failed_tickers: set = set()
    try:
        sh = gc.open_by_key(spreadsheet_id)
        today_str = str(today)

        _set_pipeline_status(sh.worksheet('Pipeline Status'), 'running')
        print(f"Pipeline started: {today_str}")

        _rebuild_state_from_sheets(sh, 'paper', today_str=today_str)

        _apply_capital_reset(sh, 'paper')

        # Trade edits BEFORE fills. _apply_trade_edits syncs the full Trade Log from
        # the sheet into trade_log.csv, but only if that CSV does not exist yet. Fills
        # (execute_trade) create the CSV with only today's trades, so if edits ran after
        # fills the sync would be skipped and edit_trade(index=N) — where N is the sheet
        # row — would target the wrong row in the fills-only CSV.
        _apply_trade_edits(sh, 'paper')

        _apply_manual_trades(sh, 'paper')

        fills = _read_fills(sh)

        tickers = get_all_tickers_including_features()
        try:
            from kth_dr.universe_dr import get_all_download_tickers
            tickers = get_all_download_tickers(tickers)
        except ImportError:
            pass
        except Exception as e:
            # kth_dr present but unusable — run the pipeline without DRs
            # rather than failing the whole daily run over an optional feature.
            print(f"WARN: DR ticker wiring skipped: {e}")
        ohlcv_dict = data_loader.ensure(tickers)
        if not ohlcv_dict:
            raise RuntimeError("No data loaded — aborting pipeline")

        model.forecast(tickers, today_str)

        _apply_fills(fills, ohlcv_dict, 'paper')
        pf_data = init_portfolio('paper')

        ticket_data = generate_trade_ticket(report_date=today_str)
        if 'error' in ticket_data:
            print(f"Ticket warning: {ticket_data.get('error')}")

        metrics = _compute_all_metrics(pf_data, today_str, today)

        errors = _validate_positions('paper')
        if errors:
            _set_pipeline_status(sh.worksheet('Pipeline Status'), 'failed',
                                 error_msg='; '.join(errors))
            raise RuntimeError(f"Validation failed: {errors}")

        fc_rows = load_forecasts(today_str)

        _write_all_staging(sh, ohlcv_dict, ticket_data, metrics, fc_rows,
                           pf_data, today_str, staging_sleep=staging_sleep)

        _append_trade_log(sh, 'paper')

        failures = promote_staging(sh, STAGING_MAP, sleep_sec=staging_sleep)
        if failures:
            msg = f"Staging promotion failed for: {', '.join(failures.keys())}"
            raise RuntimeError(msg)

        duration = round(time.time() - pipeline_start, 1)
        _set_pipeline_status(
            sh.worksheet('Pipeline Status'), 'completed',
            duration=duration,
            sheets_updated=','.join(STAGING_MAP.values()) + ',Trade Log,Forecast History',
        )

        if notifier:
            notifier('success', _summary_msg(pf_data, metrics, ticket_data, fills, today_str, duration))

        print(f"Pipeline completed in {duration}s.")
        return {
            'status': 'ok',
            'forecasts': len(fc_rows),
            'exits': len(ticket_data.get('exits', [])),
            'reduces': len(ticket_data.get('reduces', [])),
            'buys': len(ticket_data.get('buys', [])),
            'duration': duration,
        }

    except Exception as e:
        duration = round(time.time() - pipeline_start, 1)
        print(f"Pipeline failed after {duration}s: {e}")
        if sh is not None:
            try:
                _set_pipeline_status(sh.worksheet('Pipeline Status'), 'failed',
                                     error_msg=str(e), duration=duration)
            except Exception:
                pass
        if notifier:
            notifier('error', str(e))
        raise

    finally:
        os.chdir(cwd)


def _compute_all_metrics(pf_data: dict, today_str: str, today: date) -> dict:
    from kth.backtest.metrics import compute_sortino
    import pandas as pd

    metrics = compute_metrics('paper')
    equity_vals = [e['value'] for e in pf_data.get('equity_curve', [])]
    equity_series = pd.Series(equity_vals) if equity_vals else pd.Series([500_000.0])
    daily_returns = equity_series.pct_change().dropna()

    if len(equity_series) >= 2 and metrics.get('drawdown', 0) < 0:
        n_years = max(len(equity_series) / 252, 0.01)
        cagr = (equity_series.iloc[-1] / equity_series.iloc[0]) ** (1 / n_years) - 1
        metrics['calmar'] = round(cagr / abs(metrics['drawdown']), 4)
    else:
        metrics['calmar'] = 0.0

    metrics['sortino'] = round(compute_sortino(daily_returns), 4) \
        if len(daily_returns) >= 20 else 0.0

    metrics['frozen'] = pf_data.get('frozen', False)
    trade_log = get_trade_log('paper')
    year_str = str(today.year)
    ytd_thb = sum(float(t.get('friction_cost', 0) or 0)
                  for t in trade_log if t.get('date', '').startswith(year_str))
    ic = pf_data.get('initial_capital', 500_000.0)
    metrics['friction_ytd_thb'] = round(ytd_thb, 2)
    metrics['friction_ytd_pct'] = round(ytd_thb / ic, 6) if ic else 0.0

    print(f"Band: {metrics['allocation_band']}  "
          f"Sharpe: {metrics['sharpe']:.2f}  "
          f"MaxDD: {metrics.get('drawdown', 0):.2%}  "
          f"Calmar: {metrics['calmar']:.2f}  "
          f"Frozen: {metrics['frozen']}  "
          f"Friction YTD: {metrics['friction_ytd_pct']:.2%}")
    return metrics


def _write_all_staging(sh, ohlcv_dict: dict, ticket_data: dict,
                       metrics: dict, fc_rows: list, pf_data: dict,
                       today_str: str, staging_sleep: float = 1.0):
    from kth.trading.sheets import POSITIONS_HEADERS, PORTFOLIO_HEADERS

    pf = init_portfolio('paper')
    write_staging(sh.worksheet('Portfolio_staging'), PORTFOLIO_HEADERS,
                  [[pf['cash'], pf['initial_capital'], 'paper', MODEL_VERSION, today_str]],
                  sleep_sec=staging_sleep)

    pos = get_positions('paper')
    pos_rows = build_pos_rows(pos, ohlcv_dict, get_sector)
    write_staging(sh.worksheet('Positions_staging'), POSITIONS_HEADERS, pos_rows,
                  sleep_sec=staging_sleep)

    fc_by_ticker = {r['ticker']: r for r in fc_rows}
    write_staging(sh.worksheet('Forecasts_staging'),
                  FORECASTS_HEADERS,
                  [[today_str, r['ticker'], r['rank_score'], r['exp_ret'],
                    r['band_width'], r['confidence'], r['net_ret'],
                    r['p5_close'], r['p50_close'], r['p95_close'],
                    get_sector(r['ticker']), get_currency_group(r['ticker']) or '',
                    r.get('tier', '')] for r in fc_rows],
                  sleep_sec=staging_sleep)

    tt_rows = []
    all_items = (
        [('sell', item) for item in ticket_data.get('exits', [])] +
        [('sell', item) for item in ticket_data.get('reduces', [])] +
        [('buy', item) for item in ticket_data.get('buys', [])]
    )
    for action_type, item in all_items:
        ticker = item['ticker']
        close = item.get('last_close', 0)
        fric = get_friction(ticker)
        fric_rt = fric['commission_oneway'] * 2 + fric['slippage_oneway'] * 2
        est_cost = round(item['shares'] * close * (1 + fric_rt), 2)
        conf = fc_by_ticker.get(ticker, {}).get('confidence', '')
        tt_rows.append([
            ticker, action_type, item['shares'], est_cost,
            item.get('rationale', ''), get_sector(ticker), get_currency_group(ticker) or '', conf,
            '', '', '',
        ])
    write_staging(sh.worksheet('Trade Ticket_staging'),
                  TRADE_TICKET_HEADERS, tt_rows, sleep_sec=staging_sleep)

    risk_row = _write_risk_metrics_row(metrics, pf_data, today_str)
    rm_live = sh.worksheet('Risk Metrics').get_all_values()
    rm_header = RISK_METRICS_HEADERS
    all_rm = upsert_by_date(rm_live if rm_live else [], rm_header, risk_row[0])
    write_staging(sh.worksheet('Risk Metrics_staging'), rm_header,
                  all_rm[1:] if len(all_rm) > 1 else [],
                  sleep_sec=staging_sleep)

    _write_staging_for_equity_curve(sh, pf_data, today_str)

    cal_data = _compute_calibration_data(ohlcv_dict, today_str)
    if cal_data:
        cal_ws = sh.worksheet('Calibration')
        cal_existing = cal_ws.get_all_values()
        if not cal_existing:
            cal_ws.append_row(CALIBRATION_HEADERS)
            cal_existing = [CALIBRATION_HEADERS]
        already_today = any(
            row and row[0] == today_str
            for row in cal_existing[1:]
        )
        if not already_today:
            cal_ws.append_row([
                cal_data['date'], cal_data['coverage'],
                cal_data['n_samples'], cal_data['status'],
            ])
            print(f"Calibration: n={cal_data['n_samples']} "
                  f"coverage={cal_data['coverage']:.2%} status={cal_data['status']}")
        else:
            print(f"Calibration: today already logged — skip")

    _write_forecast_history(sh, ohlcv_dict, fc_rows, set(), today_str)

    print("All staging sheets written.")


def _summary_msg(pf_data: dict, metrics: dict, ticket_data: dict,
                 fills: dict, today_str: str, duration: float) -> str:
    pf = pf_data or {}
    return (
        f"Kronos pipeline done ({duration}s)\n"
        f"Capital: ฿{pf.get('total_value', pf.get('cash', 0)):,.0f}\n"
        f"Band: {metrics.get('allocation_band', 'NEUTRAL')} "
        f"({metrics.get('allocation_pct', 0.1) * 100:.0f}% per pos)\n"
        f"Buys: {len(ticket_data.get('buys', []))}  "
        f"Exits: {len(ticket_data.get('exits', []))}\n"
        f"Fills confirmed: "
        f"{sum(1 for f in fills.values() if f['fill_source'] == 'confirmed')}"
    )
