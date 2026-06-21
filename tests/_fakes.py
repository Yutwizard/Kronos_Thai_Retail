"""Fake/mock classes simulating gspread, model, and data_loader for pipeline tests.

Ported from verify_kaggle_runtime.py so test_kaggle_runtime.py and daily-pipeline
tests can share the same doubles without importing the standalone runner.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from kth.data.universe import UNIVERSE
from kth.testing.synthetic import make_synthetic_yf

CACHE_SLUG = "NeoQuasar_Kronos-small"
THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]


class FakeWorksheet:
    def __init__(self, title: str, data: list[list] = None):
        self.title = title
        self._data = data or []
        self._batch_calls = []

    def get_all_values(self) -> list[list]:
        return [list(row) for row in self._data]

    def update(self, range_label: str, values: list[list]):
        if range_label == 'A1':
            self._data = [list(row) for row in values]
            return
        parts = range_label.replace('$', '').split(':')
        if len(parts) == 2:
            start_col = ord(parts[0][0].upper()) - 65
            start_row = int(parts[0][1:]) - 1
            for i, row in enumerate(values):
                for j, val in enumerate(row):
                    r = start_row + i
                    c = start_col + j
                    while len(self._data) <= r:
                        self._data.append([])
                    while len(self._data[r]) <= c:
                        self._data[r].append('')
                    self._data[r][c] = val

    def append_row(self, values: list):
        self._data.append(list(values))

    def append_rows(self, rows: list[list]):
        for row in rows:
            self._data.append(list(row))

    def clear(self):
        self._data = []

    def batch_update(self, updates: list[dict]):
        self._batch_calls.extend(updates)
        for upd in updates:
            self.update(upd['range'], upd['values'])


class FakeSpreadsheet:
    def __init__(self):
        self._worksheets = {}

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self._worksheets:
            self._worksheets[title] = FakeWorksheet(title)
        return self._worksheets[title]

    def add_worksheet(self, title: str, rows: int = 1, cols: int = 1) -> FakeWorksheet:
        ws = FakeWorksheet(title)
        self._worksheets[title] = ws
        return ws

    def del_worksheet(self, ws):
        to_del = [k for k, v in self._worksheets.items() if v is ws]
        for k in to_del:
            del self._worksheets[k]

    def worksheets(self) -> list[FakeWorksheet]:
        return list(self._worksheets.values())


class FakeGspreadClient:
    def __init__(self):
        self._spreadsheets = {}

    def open_by_key(self, key: str) -> FakeSpreadsheet:
        if key not in self._spreadsheets:
            self._spreadsheets[key] = FakeSpreadsheet()
        return self._spreadsheets[key]


def _ensure_tab(sh: FakeSpreadsheet, title: str, data: list[list] = None):
    ws = sh.worksheet(title)
    if data:
        ws._data = [list(r) for r in data]
    return ws


def _default_sheet_data() -> dict[str, list[list]]:
    return {
        'Portfolio': [['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
                      ['500000', '500000', 'paper', 'Kronos-small-zero-shot', '2026-06-18']],
        'Positions': [['ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
                       'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss']],
        'Equity Curve': [['date', 'equity', 'cash', 'invested'],
                         ['2026-06-17', '500000', '500000', '0']],
        'Risk Metrics': [['date', 'equity', 'cash', 'deployed_pct', 'trailing_sharpe_12w',
                          'max_drawdown_pct', 'mtd_pnl_pct', 'trade_win_rate', 'calmar_ratio',
                          'sortino_ratio', 'drawdown_velocity', 'allocation_band', 'allocation_pct',
                          'market_state', 'is_frozen', 'bootstrap_p_value',
                          'friction_ytd_pct', 'friction_ytd_thb'],
                         ['2026-06-17', '500000', '500000', '0', '0', '0', '0', '0',
                          '0', '0', '0', 'NEUTRAL', '0.1', 'Normal', '0', '1', '0', '0']],
        'Trade Ticket': [['ticker', 'action', 'shares', 'est_cost_thb', 'rationale',
                          'sector', 'confidence', 'filled_price', 'filled_shares', 'fill_timestamp']],
        'Trade Log': [['timestamp', 'ticker', 'action', 'shares', 'price', 'rationale',
                       'friction_cost', 'model_version', 'id', 'ref_id']],
        'Forecast History': [['date', 'ticker', 'predicted_direction', 'predicted_return',
                              'entry_close', 'actual_return', 'was_correct']],
        'Pipeline Status': [['last_run_timestamp', 'status', 'duration_seconds',
                             'error_message', 'sheets_updated'],
                            ['', '', '', '', '']],
        'Calibration': [['date', 'coverage', 'n_samples', 'status']],
        'Capital Reset': [['date', 'action', 'capital', 'confirm_text', 'requested_at']],
        'Trade Edits': [['date', 'action', 'index', 'ticker', 'shares', 'price',
                         'ref_id', 'requested_at', 'new_date']],
        'Manual Trades': [['date', 'action', 'ticker', 'shares', 'price', 'requested_at']],
    }


def seeded_fake_client(equity_history: list[str] = None) -> FakeGspreadClient:
    gc = FakeGspreadClient()
    sh = gc.open_by_key('test_id')
    for title, data in _default_sheet_data().items():
        _ensure_tab(sh, title, data)
    for staging in ['Portfolio_staging', 'Positions_staging', 'Forecasts_staging',
                    'Trade Ticket_staging', 'Risk Metrics_staging', 'Equity Curve_staging']:
        _ensure_tab(sh, staging, [])
    if equity_history:
        ws = sh.worksheet('Equity Curve')
        eq_header = ['date', 'equity', 'cash', 'invested']
        ws._data = [eq_header]
        for d in equity_history:
            ws._data.append([d, '500000', '500000', '0'])
    return gc


def client_with_pending_setup(capital: float = 300000) -> FakeGspreadClient:
    gc = seeded_fake_client()
    sh = gc.open_by_key('test_id')
    cr_ws = sh.worksheet('Capital Reset')
    cr_ws._data = [['date', 'action', 'capital', 'confirm_text', 'requested_at'],
                   ['2026-06-18', 'SETUP', str(capital), 'SETUP', '2026-06-18T00:00:00']]
    return gc


def client_with_pending_edit(index: int = 0, new_shares: int = 200,
                             ticker: str = 'AOT.BK') -> FakeGspreadClient:
    gc = seeded_fake_client()
    sh = gc.open_by_key('test_id')
    tl_ws = sh.worksheet('Trade Log')
    tl_ws._data = [['timestamp', 'ticker', 'action', 'shares', 'price', 'rationale',
                    'friction_cost', 'model_version', 'id', 'ref_id'],
                   ['2026-06-17', ticker, 'buy', '100', '50.0', 'test', '0',
                    'v1', '20260617_AOT.BK_buy_abcd', '']]
    te_ws = sh.worksheet('Trade Edits')
    te_ws._data = [['date', 'action', 'index', 'ticker', 'shares', 'price',
                    'ref_id', 'requested_at', 'new_date'],
                   ['2026-06-18', 'edit', str(index), ticker, str(new_shares),
                    '55.0', '', '2026-06-18T00:00:00', '']]
    return gc


def portfolio_initial_capital(gc: FakeGspreadClient) -> float:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Portfolio').get_all_values()
    if len(rows) > 1:
        return float(rows[1][1])
    return 0.0


def capital_reset_cleared(gc: FakeGspreadClient) -> bool:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Capital Reset').get_all_values()
    return len(rows) == 1


def trade_log_shares(gc: FakeGspreadClient, index: int) -> int:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Trade Log').get_all_values()
    if len(rows) > index + 1:
        return int(float(rows[index + 1][3]))
    return 0


def trade_edits_cleared(gc: FakeGspreadClient) -> bool:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Trade Edits').get_all_values()
    return len(rows) == 1


def last_equity_date(gc: FakeGspreadClient) -> str:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Equity Curve').get_all_values()
    if len(rows) > 1:
        return rows[-1][0]
    return ''


def pipeline_status(gc: FakeGspreadClient) -> str:
    sh = gc.open_by_key('test_id')
    rows = sh.worksheet('Pipeline Status').get_all_values()
    if len(rows) > 1:
        return rows[1][1]
    return ''


class FakeModel:
    def __init__(self, raise_on_forecast: bool = False):
        self.raise_on_forecast = raise_on_forecast

    def forecast(self, tickers: list[str], today_str: str):
        if self.raise_on_forecast:
            raise RuntimeError("Simulated forecast failure")
        cache_dir = Path('data/forecast_cache') / CACHE_SLUG / today_str
        cache_dir.mkdir(parents=True, exist_ok=True)
        for i, ticker in enumerate(tickers):
            if ticker not in THAI_TICKERS:
                continue
            safe = ticker.replace('^', '_').replace('=', '_')
            parquet = cache_dir / f"{safe}.parquet"
            if parquet.exists():
                continue
            try:
                from kth.data.loader import load_cached
                close = float(load_cached(ticker)['close'].iloc[-1])
            except Exception:
                close = 100.0
            rng = np.random.default_rng(i)
            timestamps = pd.date_range(start='2026-06-18', periods=20, freq='B')
            p50 = close * (1.10 + rng.normal(0, 0.02, 20).cumsum())
            p5 = p50 * 0.92
            p95 = p50 * 1.08
            mean = p50 * 1.005
            df = pd.DataFrame({
                'timestamps': timestamps, 'p5': p5, 'p50': p50, 'p95': p95, 'mean': mean,
            })
            df.to_parquet(parquet, index=False)


class FakeLoader:
    def ensure(self, tickers: list[str]) -> dict:
        raw_dir = Path('data/raw')
        raw_dir.mkdir(parents=True, exist_ok=True)
        ohlcv_dict = {}
        for i, ticker in enumerate(tickers):
            yf_df = make_synthetic_yf(ticker, n_days=500, seed=i * 7 + 13)
            from kth.data.loader import to_kronos_format
            k_df = to_kronos_format(yf_df, ticker)
            safe = ticker.replace('^', '_').replace('=', '_')
            k_df.to_parquet(raw_dir / f"{safe}.parquet", index=False)
            ohlcv_dict[ticker] = k_df
        return ohlcv_dict
