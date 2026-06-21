"""Tests for Kaggle runtime auth/config and daily pipeline orchestration.

Ported from verify_kaggle_runtime.py (20 tests) plus 3 daily-pipeline tests from
verify_fixes.py that need the same fakes. Fake gspread/model/loader classes live
in tests/_fakes.py so both this file and other daily-pipeline tests can share them.
"""
import base64
import csv
import os
from datetime import date

from _fakes import (
    FakeLoader,
    FakeModel,
    capital_reset_cleared,
    client_with_pending_edit,
    client_with_pending_setup,
    last_equity_date,
    pipeline_status,
    portfolio_initial_capital,
    seeded_fake_client,
    trade_edits_cleared,
)

from kth.io.kaggle_runtime import _parse_sa, load_secrets, make_sheets_client
from kth.pipeline.daily import run_daily_pipeline, upsert_by_date

D = date(2026, 6, 18)


def fake_getter(d):
    return lambda k: d.get(k)


def test_parse_sa_json():
    result = _parse_sa('{"client_email": "x@y.com"}')
    assert result["client_email"] == "x@y.com"


def test_parse_sa_base64():
    raw = base64.b64encode(b'{"client_email": "x@y.com"}').decode()
    result = _parse_sa(raw)
    assert result["client_email"] == "x@y.com"


def test_parse_sa_bad():
    try:
        _parse_sa("not json at all")
        assert False, "should have raised"
    except RuntimeError:
        pass


def test_load_secrets_ok():
    cfg = load_secrets(fake_getter({
        "GCP_SA_JSON": '{"client_email":"x@y"}',
        "SPREADSHEET_ID": "abc",
        "HF_TOKEN": "t",
    }))
    assert cfg.spreadsheet_id == "abc"
    assert cfg.sa_info["client_email"] == "x@y"
    assert cfg.hf_token == "t"


def test_load_secrets_base64():
    raw = base64.b64encode(b'{"client_email":"x@y"}').decode()
    cfg = load_secrets(fake_getter({"GCP_SA_JSON": raw, "SPREADSHEET_ID": "abc"}))
    assert cfg.sa_info["client_email"] == "x@y"


def test_missing_secret_raises():
    try:
        load_secrets(fake_getter({"SPREADSHEET_ID": "abc"}))
        assert False, "should have raised"
    except RuntimeError as e:
        assert "GCP_SA_JSON" in str(e)


def test_bad_json_raises():
    try:
        load_secrets(fake_getter({"GCP_SA_JSON": "not json", "SPREADSHEET_ID": "a"}))
        assert False, "should have raised"
    except RuntimeError:
        pass


def test_make_client_uses_factory():
    seen = []

    def my_factory(sa):
        seen.append(sa)
        return "CLIENT"

    c = make_sheets_client({"client_email": "x"}, client_factory=my_factory)
    assert c == "CLIENT"
    assert seen[0]["client_email"] == "x"


def test_upsert_by_date_replaces():
    header = ['date', 'value']
    existing = [header, ['2026-06-17', '100'], ['2026-06-18', '200']]
    result = upsert_by_date(existing, header, ['2026-06-18', '250'], date_col=0)
    assert len(result) == 3
    assert result[2] == ['2026-06-18', '250']
    assert result[1] == ['2026-06-17', '100']


def test_upsert_by_date_appends():
    header = ['date', 'value']
    existing = [header, ['2026-06-17', '100']]
    result = upsert_by_date(existing, header, ['2026-06-18', '200'], date_col=0)
    assert len(result) == 3
    assert result[2] == ['2026-06-18', '200']


def test_upsert_by_date_preserves_prior():
    header = ['date', 'value']
    existing = [header, ['2026-06-13', '100'], ['2026-06-14', '200']]
    result = upsert_by_date(existing, header, ['2026-06-18', '300'], date_col=0)
    assert len(result) == 4
    assert result[1][0] == '2026-06-13'
    assert result[2][0] == '2026-06-14'
    assert result[3][0] == '2026-06-18'


def test_pipeline_writes_all_tabs(tmp_path):
    gc = seeded_fake_client()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=str(tmp_path), staging_sleep=0,
    )
    sh = gc.open_by_key("test_id")
    for tab in ["Portfolio", "Forecasts", "Trade Ticket",
                "Risk Metrics", "Equity Curve", "Pipeline Status"]:
        data = sh.worksheet(tab).get_all_values()
        assert len(data) >= 2, f"{tab}: expected >= 2 rows, got {len(data)}"


def test_idempotent_preserves_history(tmp_path):
    gc = seeded_fake_client(equity_history=["2026-06-13", "2026-06-14"])
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=str(tmp_path), staging_sleep=0,
    )
    rows1 = gc.open_by_key("test_id").worksheet("Equity Curve").get_all_values()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=str(tmp_path), staging_sleep=0,
    )
    rows2 = gc.open_by_key("test_id").worksheet("Equity Curve").get_all_values()
    dates = [r[0] for r in rows2[1:]]
    assert len(rows1) == len(rows2), f"Row count changed: {len(rows1)} vs {len(rows2)}"
    assert {"2026-06-13", "2026-06-14"} <= set(dates), \
        f"Prior history missing: {dates}"
    assert dates.count(str(D)) == 1, \
        f"Expected exactly 1 entry for {D}, got {dates.count(str(D))}"


def test_capital_reset_applied_before_forecasts(tmp_path):
    gc = client_with_pending_setup(capital=300000)
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=str(tmp_path), staging_sleep=0,
    )
    assert portfolio_initial_capital(gc) == 300000, \
        f"Expected 300000, got {portfolio_initial_capital(gc)}"
    assert capital_reset_cleared(gc), "Capital Reset sheet should be cleared"


def test_trade_edit_applied(tmp_path):
    gc = client_with_pending_edit(index=0, new_shares=200)
    csv_dir = tmp_path / 'data' / 'positions'
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / 'trade_log.csv'
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['date', 'ticker', 'action', 'shares', 'price', 'order_type',
                    'mode', 'rationale', 'friction_cost', 'model_version', 'forecast_date'])
        w.writerow(['2026-06-17', 'AOT.BK', 'buy', '100', '50.0', 'market',
                    'paper', 'test', '0', 'v1', '2026-06-17'])
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=D, work_dir=str(tmp_path), staging_sleep=0,
    )
    orig = os.getcwd()
    os.chdir(str(tmp_path))
    from kth.trading.portfolio import init_portfolio
    pf = init_portfolio('paper')
    pos = pf.get('positions', {})
    os.chdir(orig)
    assert 'AOT.BK' in pos, f"Expected AOT.BK position, got {list(pos.keys())}"
    assert pos['AOT.BK']['shares'] == 200, \
        f"Expected 200 shares, got {pos['AOT.BK']['shares']}"
    assert trade_edits_cleared(gc), "Trade Edits sheet should be cleared"


def test_uses_injected_today_not_utc(tmp_path):
    gc = seeded_fake_client()
    run_daily_pipeline(
        gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
        today=date(2026, 6, 15), work_dir=str(tmp_path), staging_sleep=0,
    )
    assert last_equity_date(gc) == "2026-06-15", \
        f"Expected 2026-06-15, got {last_equity_date(gc)}"


def test_failure_writes_status_and_notifies(tmp_path):
    gc = seeded_fake_client()
    calls = []
    boom = FakeModel(raise_on_forecast=True)
    try:
        run_daily_pipeline(
            gc, "test_id", model=boom, data_loader=FakeLoader(),
            today=D, work_dir=str(tmp_path), staging_sleep=0,
            notifier=lambda lvl, msg: calls.append(lvl),
        )
    except Exception:
        pass
    assert pipeline_status(gc) == "failed", \
        f"Expected 'failed', got '{pipeline_status(gc)}'"
    assert "error" in calls, \
        f"Expected notifier to be called with 'error', got {calls}"


def test_forecast_history_idempotent(tmp_path):
    """Same-day re-run must not duplicate today's Forecast History rows (R3)."""
    gc = seeded_fake_client()
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=D, work_dir=str(tmp_path), staging_sleep=0)
    fh1 = gc.open_by_key("test_id").worksheet("Forecast History").get_all_values()
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=D, work_dir=str(tmp_path), staging_sleep=0)
    fh2 = gc.open_by_key("test_id").worksheet("Forecast History").get_all_values()
    today1 = [r for r in fh1[1:] if r and r[0] == str(D)]
    today2 = [r for r in fh2[1:] if r and r[0] == str(D)]
    assert len(today1) > 0, "first run wrote no forecast-history rows"
    assert len(today1) == len(today2), \
        f"Forecast History duplicated on re-run: {len(today1)} -> {len(today2)}"


def test_trade_edit_correct_row_with_same_day_fill(tmp_path):
    """Edit must apply BEFORE fills create trade_log.csv, else the sheet-based edit
    index targets the wrong row in the (fills-only) local CSV (C3 regression)."""
    gc = client_with_pending_edit(index=0, new_shares=200, ticker='AOT.BK')
    sh = gc.open_by_key("test_id")
    sh.worksheet('Trade Ticket')._data = [
        ['ticker', 'action', 'shares', 'est_cost_thb', 'rationale', 'sector',
         'confidence', 'filled_price', 'filled_shares', 'fill_timestamp'],
        ['PTT.BK', 'buy', '100', '3500', 'test', 'Energy', 'green',
         '35.0', '100', '2026-06-18T09:30'],
    ]
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=D, work_dir=str(tmp_path), staging_sleep=0)
    orig = os.getcwd()
    os.chdir(str(tmp_path))
    from kth.trading.portfolio import init_portfolio
    pos = init_portfolio('paper').get('positions', {})
    os.chdir(orig)
    assert pos.get('AOT.BK', {}).get('shares') == 200, \
        f"Edit hit the wrong row; AOT.BK = {pos.get('AOT.BK')}"


def test_manual_trade_applied(tmp_path):
    """A queued manual buy is executed by the pipeline and ends up in positions."""
    gc = seeded_fake_client()
    sh = gc.open_by_key("test_id")
    sh.worksheet('Manual Trades')._data = [
        ['date', 'action', 'ticker', 'shares', 'price', 'requested_at'],
        [str(D), 'buy', 'AOT.BK', '100', '50.0', '2026-06-18T09:30'],
    ]
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=D, work_dir=str(tmp_path), staging_sleep=0)
    orig = os.getcwd()
    os.chdir(str(tmp_path))
    from kth.trading.portfolio import init_portfolio
    pos = init_portfolio('paper').get('positions', {})
    os.chdir(orig)
    assert pos.get('AOT.BK', {}).get('shares') == 100, \
        f"Manual buy not applied; AOT.BK = {pos.get('AOT.BK')}"
    assert len(sh.worksheet('Manual Trades').get_all_values()) == 1, \
        "Manual Trades sheet should be cleared after apply"


def test_column_to_letter():
    """Column index to A1 notation must work for columns > 26."""
    from kth.pipeline.daily import _col_to_letter
    assert _col_to_letter(0) == "A"
    assert _col_to_letter(25) == "Z"
    assert _col_to_letter(26) == "AA"
    assert _col_to_letter(27) == "AB"
    assert _col_to_letter(51) == "AZ"


def test_calibration_idempotent_on_rerun(tmp_path):
    """Same-day re-run must not append duplicate Calibration rows.
    Monkeypatches _compute_calibration_data so the append path is exercised."""
    import kth.pipeline.daily as daily_mod
    orig_cal = daily_mod._compute_calibration_data
    daily_mod._compute_calibration_data = lambda ohlcv, today_str: {
        'date': today_str, 'coverage': 0.88, 'n_samples': 15, 'status': 'on_track'
    }
    try:
        gc = seeded_fake_client()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026, 6, 18), work_dir=str(tmp_path), staging_sleep=0)
        rows1 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026, 6, 18), work_dir=str(tmp_path), staging_sleep=0)
        rows2 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        today1 = [r for r in rows1[1:] if r and r[0] == "2026-06-18"]
        today2 = [r for r in rows2[1:] if r and r[0] == "2026-06-18"]
        assert len(today1) == len(today2), \
            f"Calibration duplicated: {len(today1)} -> {len(today2)}"
    finally:
        daily_mod._compute_calibration_data = orig_cal


def test_risk_metrics_history_preserved_on_rerun(tmp_path):
    """Same-day re-run must not wipe Risk Metrics history."""
    gc = seeded_fake_client()
    sh = gc.open_by_key("test_id")
    sh.worksheet("Risk Metrics")._data = [
        ["date", "equity", "cash", "deployed_pct", "trailing_sharpe_12w", "max_drawdown_pct",
         "mtd_pnl_pct", "trade_win_rate", "calmar_ratio", "sortino_ratio", "drawdown_velocity",
         "allocation_band", "allocation_pct", "market_state", "is_frozen", "bootstrap_p_value",
         "friction_ytd_pct", "friction_ytd_thb"],
        ["2026-06-16", "500000", "500000", "0", "0", "0", "0", "0", "0", "0", "0",
         "NEUTRAL", "0.1", "Normal", "0", "1", "0", "0"],
        ["2026-06-17", "500000", "500000", "0", "0", "0", "0", "0", "0", "0", "0",
         "NEUTRAL", "0.1", "Normal", "0", "1", "0", "0"],
    ]
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=date(2026, 6, 18), work_dir=str(tmp_path), staging_sleep=0)
    rows = gc.open_by_key("test_id").worksheet("Risk Metrics").get_all_values()
    dates = [r[0] for r in rows[1:]]
    assert "2026-06-16" in dates, f"Prior day wiped! dates={dates}"
    assert "2026-06-17" in dates, f"Prior day wiped! dates={dates}"
    assert dates.count("2026-06-18") == 1, f"Today duplicated: {dates}"
