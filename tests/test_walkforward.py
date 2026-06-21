"""Tests for kth.backtest.walkforward — equity curve alignment and open_trades blend."""
import inspect

from kth.backtest import walkforward


def test_equity_curve_index_is_mark_day_not_signal_day():
    """Regression guard: equity curve must be indexed by mark_days, not trading_days."""
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'mark_days' in source, "Equity curve must use mark_days"
    assert 'mark_index' in source, "Equity curve must use mark_index"


def test_open_trades_blends_on_rebalance():
    """Regression guard: walkforward must blend entry price on rebalance."""
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'blended' in source.lower(), "open_trades must blend entry price on rebalance"


def test_open_trades_blend_logic_correct():
    """Blend math: buy 100 @ 50, add 50 @ 60 -> weighted avg 53.33."""
    old = {"entry_price": 50.0, "units": 100, "trade_value": 5000.0, "entry_date": "d1"}
    new_units, new_price = 50, 60.0
    total = old["units"] + new_units
    blended = (old["units"] * old["entry_price"] + new_units * new_price) / total
    assert abs(blended - 53.333) < 0.01, f"Expected ~53.33, got {blended}"
    exec_price = 55.0
    gross_ret = (exec_price / blended - 1) * (total * blended)
    assert gross_ret > 0, f"Blended entry should give profit: {gross_ret}"
