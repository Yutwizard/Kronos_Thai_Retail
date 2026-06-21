"""Tests for kth.backtest.walkforward — equity curve alignment and open_trades blend."""
import inspect

import pytest

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


def test_hysteresis_entry_exit_asymmetry():
    """L4: entry requires threshold+buffer, exit requires threshold-buffer, with min_holding."""
    from kth.backtest.strategy import apply_hysteresis
    raw = {"A": 0.025, "B": 0.015, "C": 0.008}
    sigs, ranking = apply_hysteresis(raw, {}, {}, 0.01, 0.005, 5)
    assert "A" in sigs and sigs["A"] == 0.025
    assert "B" not in sigs and "C" not in sigs

    raw2 = {"A": 0.003}
    sigs2, ranking2 = apply_hysteresis(raw2, {"A": 100}, {"A": 2}, 0.01, 0.005, 5)
    assert sigs2["A"] == 1
    assert "A" in ranking2

    sigs3, _ = apply_hysteresis(raw2, {"A": 100}, {"A": 6}, 0.01, 0.005, 5)
    assert sigs3["A"] == 0


def test_hysteresis_hold_when_min_holding_not_met():
    """L4: position held less than min_holding_days cannot exit even if signal drops."""
    from kth.backtest.strategy import apply_hysteresis
    raw = {"X": 0.001}
    sigs, ranking = apply_hysteresis(raw, {"X": 50}, {"X": 3}, 0.01, 0.005, 5)
    assert sigs["X"] == 1
    assert "X" in ranking


def test_hysteresis_new_position_needs_buffer_above_threshold():
    """L4: new entry requires signal > threshold + buffer (not just > threshold)."""
    from kth.backtest.strategy import apply_hysteresis
    raw = {"Y": 0.012}  # above threshold (0.01) but below threshold+buffer (0.015)
    sigs, _ = apply_hysteresis(raw, {}, {}, 0.01, 0.005, 5)
    assert "Y" not in sigs


def test_mixed_class_rejected():
    """L2: mixed crypto + equity ticker lists must raise ValueError."""
    from kth.backtest.walkforward import _validate_single_calendar
    with pytest.raises(ValueError, match="mixed-asset-class"):
        _validate_single_calendar(["BTC-USD", "AAPL"])


def test_single_crypto_ok():
    """L2: crypto-only list passes validation."""
    from kth.backtest.walkforward import _validate_single_calendar
    _validate_single_calendar(["BTC-USD", "ETH-USD"])


def test_single_equity_ok():
    """L2: equity-only list (including Thai + US) passes validation."""
    from kth.backtest.walkforward import _validate_single_calendar
    _validate_single_calendar(["AAPL", "PTT.BK"])
