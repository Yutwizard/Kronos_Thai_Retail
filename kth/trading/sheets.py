"""Shared Google Sheets staging + promotion utilities for Colab pipeline."""
import time as _time
from typing import Any, Callable

from kth.trading.sheets_config import PORTFOLIO_HEADERS, POSITIONS_HEADERS

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


def promote_staging(sh, staging_map: dict = None, sleep_sec: float = 1.0) -> dict:
    if staging_map is None:
        staging_map = STAGING_MAP
    failures = {}
    for staging_name, live_name in staging_map.items():
        try:
            staging_ws = sh.worksheet(staging_name)
            live_ws = sh.worksheet(live_name)
            data = staging_ws.get_all_values()
            if data:
                live_ws.clear()
                live_ws.update('A1', data)
            staging_ws.clear()
        except Exception as e:
            failures[staging_name] = str(e)
            print(f"  Promotion {staging_name} -> {live_name} failed: {e}")
        _time.sleep(sleep_sec)
    return failures


def build_pos_rows(positions: dict, ohlcv_dict: dict, get_sector_fn: Callable[[str], str]) -> list:
    try:
        from kth_dr.universe_dr import get_dr_info_for_display
    except ImportError:
        get_dr_info_for_display = lambda t: None

    rows = []
    for p in positions['positions']:
        ohlcv = ohlcv_dict or {}
        if p['ticker'] in ohlcv:
            close = float(ohlcv[p['ticker']]['close'].iloc[-1])
        else:
            close = p['avg_cost']
        pnl = (close - p['avg_cost']) * p['shares']
        pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0

        underlying_ticker = ''
        premium_pct = ''
        dr_info = get_dr_info_for_display(p['ticker'])
        if dr_info:
            underlying_ticker = dr_info['underlying_ticker']
            try:
                u_close = float(ohlcv[dr_info['underlying_ticker']]['close'].iloc[-1])
                fx_close = float(ohlcv[dr_info['fx_ticker']]['close'].iloc[-1])
                dr_intrinsic = (u_close * fx_close) / dr_info['ratio']
                premium_pct = round((close / dr_intrinsic) - 1, 4) if dr_intrinsic else ''
            except (KeyError, ZeroDivisionError):
                premium_pct = ''

        rows.append([
            p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
            get_sector_fn(p['ticker']), round(close, 2),
            round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
            underlying_ticker, premium_pct,
        ])
    return rows



