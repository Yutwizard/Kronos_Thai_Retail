"""Tests for kth/trading/portfolio.py critical functions."""
import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def temp_positions_dir():
    """Change to a temp dir so Path('data/positions/') doesn't collide with real data."""
    with tempfile.TemporaryDirectory() as tmp:
        orig_cwd = os.getcwd()
        os.chdir(tmp)
        yield tmp
        os.chdir(orig_cwd)


def test_init_portfolio_creates_default(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, INITIAL_CAPITAL
    pf = init_portfolio('paper')
    assert pf['mode'] == 'paper'
    assert pf['cash'] == INITIAL_CAPITAL
    assert pf['initial_capital'] == INITIAL_CAPITAL
    assert pf['positions'] == {}


def test_reset_portfolio_sets_capital(temp_positions_dir):
    from kth.trading.portfolio import reset_portfolio, init_portfolio
    reset_portfolio('paper', initial_capital=100000.0)
    pf = init_portfolio('paper')
    assert pf['cash'] == 100000.0
    assert pf['initial_capital'] == 100000.0
    assert pf['positions'] == {}
    assert len(pf['equity_curve']) == 1


def test_execute_trade_basic(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper')
    result = execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'market', 'test trade')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert 'PTT.BK' in pf['positions']
    assert pf['positions']['PTT.BK']['shares'] == 100
    assert pf['positions']['PTT.BK']['avg_cost'] == 35.0


def test_execute_trade_sell_reduces_shares(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper')
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'market', 'buy')
    result = execute_trade('PTT.BK', 'sell', 50, 38.0, 'paper', 'market', 'sell')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert pf['positions']['PTT.BK']['shares'] == 50


def test_execute_trade_sell_all_removes_position(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade
    init_portfolio('paper')
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'market', 'buy')
    execute_trade('PTT.BK', 'sell', 100, 38.0, 'paper', 'market', 'sell all')
    pf = init_portfolio('paper')
    assert 'PTT.BK' not in pf['positions']


def test_edit_trade_updates_price_and_shares(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade, edit_trade
    init_portfolio('paper')
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'market', 'buy')
    result = edit_trade(0, new_price=36.0, new_shares=200, mode='paper')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert pf['positions']['PTT.BK']['avg_cost'] == 36.0
    assert pf['positions']['PTT.BK']['shares'] == 200


def test_delete_trade_removes_position(temp_positions_dir):
    from kth.trading.portfolio import init_portfolio, execute_trade, delete_trade
    init_portfolio('paper')
    execute_trade('PTT.BK', 'buy', 100, 35.0, 'paper', 'market', 'buy')
    result = delete_trade(0, 'paper')
    assert 'error' not in result
    pf = init_portfolio('paper')
    assert 'PTT.BK' not in pf['positions']
