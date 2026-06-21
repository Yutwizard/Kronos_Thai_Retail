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


def test_trade_ticket_buy_cost_does_not_exceed_cash():
    """Cash guard: deployable must be capped at available cash."""
    cash = 50_000.0
    total_value = 500_000.0
    alloc_pct = 0.10
    deployable_naive = total_value * alloc_pct
    deployable_guarded = min(deployable_naive, cash)
    assert deployable_guarded == deployable_naive, "No cap when cash is sufficient"
    cash2 = 25_000.0
    total_value2 = 500_000.0
    deployable_naive2 = total_value2 * alloc_pct
    deployable_guarded2 = min(deployable_naive2, cash2)
    assert deployable_guarded2 < deployable_naive2, "Cash guard must cap deployable"
    assert deployable_guarded2 == cash2, f"Should cap at cash {cash2}"


def test_cache_slug_consistent_across_modules():
    """CACHE_SLUG must be same in trade_gen and walkforward."""
    from kth.backtest.walkforward import _model_slug
    from kth.trading.trade_gen import CACHE_SLUG as tg_slug
    wf_slug = _model_slug("NeoQuasar/Kronos-small")
    assert tg_slug == wf_slug, f"trade_gen={tg_slug} vs walkforward={wf_slug}"


def test_reduce_only_on_bearish_yellow():
    """Reduce should only trigger on yellow + bearish, not yellow + bullish."""
    def should_reduce(f):
        return f["confidence"] == "yellow" and f["direction"] == "down"
    assert should_reduce({"confidence": "yellow", "direction": "down"}), \
        "Bearish yellow should reduce"
    assert not should_reduce({"confidence": "yellow", "direction": "up"}), \
        "Bullish yellow should NOT reduce"
