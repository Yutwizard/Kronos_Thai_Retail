"""Smoke test for Colab pipeline cells — verifies imports and data flow.

Runs without GPU by using synthetic data. Tests that cells 1-17 concepts
execute without error.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import pytest


@pytest.fixture
def mock_env():
    """Simulate the state built up across Colab cells."""
    with tempfile.TemporaryDirectory() as tmp:
        orig_cwd = os.getcwd()
        os.chdir(tmp)
        Path('data/raw').mkdir(parents=True)
        Path('data/positions').mkdir(parents=True)
        Path('data/forecast_cache').mkdir(parents=True)
        dates = pd.date_range('2026-01-01', periods=400, freq='B')
        ohlcv = pd.DataFrame({
            'timestamps': dates,
            'open': 35.0, 'high': 36.0, 'low': 34.0, 'close': 35.5,
            'volume': 1000000, 'amount': 35500000,
        }, index=range(400))
        yield {'ohlcv_dict': {'PTT.BK': ohlcv}, 'sh': MagicMock()}
        os.chdir(orig_cwd)


def test_init_portfolio_smoke(mock_env):
    """Cell 4 logic: init portfolio when empty."""
    from kth.trading.portfolio import init_portfolio, INITIAL_CAPITAL
    pf = init_portfolio('paper')
    assert pf['cash'] == INITIAL_CAPITAL
    assert pf['positions'] == {}


def test_execute_fills_smoke(mock_env):
    """Cell 9 logic: execute fills on portfolio."""
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper')
    fills = {'PTT.BK': {'action': 'buy', 'shares': 100, 'fill_source': 'assumed'}}
    ohlcv = mock_env['ohlcv_dict']

    for ticker, fill in fills.items():
        if fill['fill_source'] == 'assumed':
            price = float(ohlcv[ticker]['close'].iloc[-1])
        else:
            price = fill.get('price', 0)
        result = execute_trade(ticker, fill['action'], fill['shares'], price, 'paper', 'test')
        assert 'error' not in result

    pf = init_portfolio('paper')
    assert 'PTT.BK' in pf.get('positions', {})


def test_build_pos_rows_smoke(mock_env):
    """Cell 13 logic: build_pos_rows from kth.trading.sheets."""
    from kth.trading.sheets import build_pos_rows
    from kth.data.universe import get_sector
    from kth.trading.portfolio import init_portfolio, execute_trade

    init_portfolio('paper')
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'test')
    from kth.trading.portfolio import get_positions
    pos = get_positions('paper')
    rows = build_pos_rows(pos, mock_env['ohlcv_dict'], get_sector)
    assert len(rows) == 1
    assert rows[0][0] == 'PTT.BK'
    assert rows[0][1] == 100
    assert rows[0][5] == 35.5


def test_write_staging_smoke(mock_env):
    """Cell 13 logic: write_staging works with a mock sheet."""
    from kth.trading.sheets import write_staging
    ws = MagicMock()
    write_staging(ws, ['ticker', 'shares'], [['PTT.BK', 100]])
    ws.clear.assert_called_once()
    ws.append_row.assert_called_once_with(['ticker', 'shares'])
    ws.append_rows.assert_called_once_with([['PTT.BK', 100]])
