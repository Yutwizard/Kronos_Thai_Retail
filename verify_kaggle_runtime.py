"""
End-to-end verification of Kaggle runtime modules (Phases 1-2).

Run: python verify_kaggle_runtime.py
"""
import base64
import json
import os
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from kth.data.universe import UNIVERSE, get_all_tickers
from kth.testing.synthetic import make_synthetic_yf

# ── Phase 1 imports ──────────────────────────────────────────────────────
from kth.io.kaggle_runtime import _parse_sa, load_secrets, make_sheets_client

# ── Phase 2 imports ──────────────────────────────────────────────────────
from kth.pipeline.daily import run_daily_pipeline, upsert_by_date


# ═══════════════════════════════════════════════════════════════════════════
# Fake/mock classes — simulate gspread, model, data_loader
# ═══════════════════════════════════════════════════════════════════════════

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


# ── Fake Model ────────────────────────────────────────────────────────────

CACHE_SLUG = "NeoQuasar_Kronos-small"
THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]


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


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1 Tests — auth/config
# ═══════════════════════════════════════════════════════════════════════════

D = date(2026, 6, 18)


def fake_getter(d):
    return lambda k: d.get(k)


def test_parse_sa_json():
    result = _parse_sa('{"client_email": "x@y.com"}')
    assert result["client_email"] == "x@y.com"
    print("PASS test_parse_sa_json")


def test_parse_sa_base64():
    raw = base64.b64encode(b'{"client_email": "x@y.com"}').decode()
    result = _parse_sa(raw)
    assert result["client_email"] == "x@y.com"
    print("PASS test_parse_sa_base64")


def test_parse_sa_bad():
    try:
        _parse_sa("not json at all")
        assert False, "should have raised"
    except RuntimeError:
        pass
    print("PASS test_parse_sa_bad")


def test_load_secrets_ok():
    cfg = load_secrets(fake_getter({
        "GCP_SA_JSON": '{"client_email":"x@y"}',
        "SPREADSHEET_ID": "abc",
        "HF_TOKEN": "t",
    }))
    assert cfg.spreadsheet_id == "abc"
    assert cfg.sa_info["client_email"] == "x@y"
    assert cfg.hf_token == "t"
    print("PASS test_load_secrets_ok")


def test_load_secrets_base64():
    raw = base64.b64encode(b'{"client_email":"x@y"}').decode()
    cfg = load_secrets(fake_getter({"GCP_SA_JSON": raw, "SPREADSHEET_ID": "abc"}))
    assert cfg.sa_info["client_email"] == "x@y"
    print("PASS test_load_secrets_base64")


def test_missing_secret_raises():
    try:
        load_secrets(fake_getter({"SPREADSHEET_ID": "abc"}))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "GCP_SA_JSON" in str(e)
    print("PASS test_missing_secret_raises")


def test_bad_json_raises():
    try:
        load_secrets(fake_getter({"GCP_SA_JSON": "not json", "SPREADSHEET_ID": "a"}))
        assert False, "should have raised"
    except RuntimeError:
        pass
    print("PASS test_bad_json_raises")


def test_make_client_uses_factory():
    seen = []
    def my_factory(sa):
        seen.append(sa)
        return "CLIENT"
    c = make_sheets_client({"client_email": "x"}, client_factory=my_factory)
    assert c == "CLIENT"
    assert seen[0]["client_email"] == "x"
    print("PASS test_make_client_uses_factory")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2 Tests — orchestration
# ═══════════════════════════════════════════════════════════════════════════

def test_upsert_by_date_replaces():
    header = ['date', 'value']
    existing = [header, ['2026-06-17', '100'], ['2026-06-18', '200']]
    result = upsert_by_date(existing, header, ['2026-06-18', '250'], date_col=0)
    assert len(result) == 3
    assert result[2] == ['2026-06-18', '250']
    assert result[1] == ['2026-06-17', '100']
    print("PASS test_upsert_by_date_replaces")


def test_upsert_by_date_appends():
    header = ['date', 'value']
    existing = [header, ['2026-06-17', '100']]
    result = upsert_by_date(existing, header, ['2026-06-18', '200'], date_col=0)
    assert len(result) == 3
    assert result[2] == ['2026-06-18', '200']
    print("PASS test_upsert_by_date_appends")


def test_upsert_by_date_preserves_prior():
    header = ['date', 'value']
    existing = [header, ['2026-06-13', '100'], ['2026-06-14', '200']]
    result = upsert_by_date(existing, header, ['2026-06-18', '300'], date_col=0)
    assert len(result) == 4
    assert result[1][0] == '2026-06-13'
    assert result[2][0] == '2026-06-14'
    assert result[3][0] == '2026-06-18'
    print("PASS test_upsert_by_date_preserves_prior")


def test_pipeline_writes_all_tabs(tmp):
    gc = seeded_fake_client()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=tmp,
    )
    sh = gc.open_by_key("test_id")
    for tab in ["Portfolio", "Forecasts", "Trade Ticket",
                "Risk Metrics", "Equity Curve", "Pipeline Status"]:
        data = sh.worksheet(tab).get_all_values()
        assert len(data) >= 2, f"{tab}: expected >= 2 rows, got {len(data)}"
    print("PASS test_pipeline_writes_all_tabs")


def test_idempotent_preserves_history(tmp):
    gc = seeded_fake_client(equity_history=["2026-06-13", "2026-06-14"])
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=tmp,
    )
    rows1 = gc.open_by_key("test_id").worksheet("Equity Curve").get_all_values()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=tmp,
    )
    rows2 = gc.open_by_key("test_id").worksheet("Equity Curve").get_all_values()
    dates = [r[0] for r in rows2[1:]]
    assert len(rows1) == len(rows2), f"Row count changed: {len(rows1)} vs {len(rows2)}"
    assert {"2026-06-13", "2026-06-14"} <= set(dates), \
        f"Prior history missing: {dates}"
    assert dates.count(str(D)) == 1, \
        f"Expected exactly 1 entry for {D}, got {dates.count(str(D))}"
    print("PASS test_idempotent_preserves_history")


def test_capital_reset_applied_before_forecasts(tmp):
    gc = client_with_pending_setup(capital=300000)
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=tmp,
    )
    assert portfolio_initial_capital(gc) == 300000, \
        f"Expected 300000, got {portfolio_initial_capital(gc)}"
    assert capital_reset_cleared(gc), "Capital Reset sheet should be cleared"
    print("PASS test_capital_reset_applied_before_forecasts")


def test_trade_edit_applied(tmp):
    gc = client_with_pending_edit(index=0, new_shares=200)
    csv_dir = Path(tmp) / 'data' / 'positions'
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / 'trade_log.csv'
    import csv
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['date', 'ticker', 'action', 'shares', 'price', 'order_type',
                     'mode', 'rationale', 'friction_cost', 'model_version', 'forecast_date'])
        w.writerow(['2026-06-17', 'AOT.BK', 'buy', '100', '50.0', 'market',
                     'paper', 'test', '0', 'v1', '2026-06-17'])
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=tmp,
    )
    # Must chdir back to tmp because run_daily_pipeline restores CWD on exit
    # and init_portfolio resolves relative to CWD
    orig = os.getcwd()
    os.chdir(tmp)
    from kth.trading.portfolio import init_portfolio
    pf = init_portfolio('paper')
    pos = pf.get('positions', {})
    os.chdir(orig)
    assert 'AOT.BK' in pos, f"Expected AOT.BK position, got {list(pos.keys())}"
    assert pos['AOT.BK']['shares'] == 200, \
        f"Expected 200 shares, got {pos['AOT.BK']['shares']}"
    assert trade_edits_cleared(gc), "Trade Edits sheet should be cleared"
    print("PASS test_trade_edit_applied")


def test_uses_injected_today_not_utc(tmp):
    gc = seeded_fake_client()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=date(2026, 6, 15), work_dir=tmp,
    )
    assert last_equity_date(gc) == "2026-06-15", \
        f"Expected 2026-06-15, got {last_equity_date(gc)}"
    print("PASS test_uses_injected_today_not_utc")


def test_failure_writes_status_and_notifies(tmp):
    gc = seeded_fake_client()
    calls = []
    boom = FakeModel(raise_on_forecast=True)
    try:
        run_daily_pipeline(
            gc, "test_id", model=boom, data_loader=FakeLoader(),
            today=D, work_dir=tmp,
            notifier=lambda lvl, msg: calls.append(lvl),
        )
    except Exception:
        pass
    assert pipeline_status(gc) == "failed", \
        f"Expected 'failed', got '{pipeline_status(gc)}'"
    assert "error" in calls, \
        f"Expected notifier to be called with 'error', got {calls}"
    print("PASS test_failure_writes_status_and_notifies")


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_")]
    import inspect
    for fn in fns:
        params = inspect.signature(fn).parameters
        if params:
            with tempfile.TemporaryDirectory() as tmp:
                fn(tmp)
        else:
            fn()
        print("PASS", fn.__name__)
    print("ALL PASSED")
