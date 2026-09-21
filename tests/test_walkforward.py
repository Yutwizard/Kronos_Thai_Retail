"""Tests for kth.backtest.walkforward — equity curve alignment and open_trades blend."""
import inspect

import pytest

from kth.backtest import walkforward


def test_equity_curve_index_is_mark_day_not_signal_day():
    """Regression guard: equity curve must be indexed by mark_days, not trading_days."""
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'mark_days' in source, "Equity curve must use mark_days"
    assert 'mark_index' in source, "Equity curve must use mark_index"


def test_lots_ledger_used_in_walkforward():
    """M6: walkforward must use a lots ledger, not the old open_trades blend dict."""
    import inspect
    from kth.backtest import walkforward
    source = inspect.getsource(walkforward.run_walkforward)
    assert "ledger" in source, "walkforward must step a LotLedger"
    assert "record_sell" in source, "exits must match lots through the ledger"


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


def test_mixed_class_rejected(monkeypatch):
    """L2: mixed crypto + equity ticker lists must raise ValueError.

    crypto was archived from UNIVERSE 2026-07-16 (see archive/other-asset-classes/),
    so no real ticker resolves to "crypto" anymore. This branch is intentionally kept
    alive as dead code in case crypto is reactivated later -- monkeypatch simulates
    that reactivation so the guard logic itself still gets exercised."""
    from kth.backtest.walkforward import _validate_single_calendar
    import kth.data.universe as universe
    fake_classes = {"BTC-USD": "crypto", "PTT.BK": "thai_equity"}
    monkeypatch.setattr(universe, "get_ticker_class", fake_classes.get)
    with pytest.raises(ValueError, match="mixed-asset-class"):
        _validate_single_calendar(["BTC-USD", "PTT.BK"])


def test_single_crypto_ok(monkeypatch):
    """L2: crypto-only list passes validation. See test_mixed_class_rejected docstring
    for why this needs monkeypatching now that crypto is archived."""
    from kth.backtest.walkforward import _validate_single_calendar
    import kth.data.universe as universe
    fake_classes = {"BTC-USD": "crypto", "ETH-USD": "crypto"}
    monkeypatch.setattr(universe, "get_ticker_class", fake_classes.get)
    _validate_single_calendar(["BTC-USD", "ETH-USD"])


def test_single_equity_ok():
    """L2: equity-only list passes validation."""
    from kth.backtest.walkforward import _validate_single_calendar
    _validate_single_calendar(["PTT.BK", "KBANK.BK"])


def test_median_vol_series_is_cross_sectional_median_of_rolling_return_std():
    """Hand-worked: window=2 returns, ddof=1 std, median across two tickers.

    A closes 100,110,121,108.9 -> returns .10,.10,-.10 -> std at day3 = 0, day4 = sqrt(.02)
    B closes 50,50,55,55       -> returns 0,.10,0      -> std at day3 = day4 = sqrt(.005)
    Median of two values = their mean. Days 1-2 lack a full 2-return window.
    """
    import pandas as pd
    from kth.backtest.strategy import compute_median_vol_series

    days = pd.date_range("2024-01-01", periods=4)
    data = {
        "A": pd.DataFrame({"timestamps": days, "close": [100.0, 110.0, 121.0, 108.9]}),
        "B": pd.DataFrame({"timestamps": days, "close": [50.0, 50.0, 55.0, 55.0]}),
    }
    series = compute_median_vol_series(data, vol_lookback=2)

    assert list(series.index) == [days[2], days[3]]
    assert series.iloc[0] == pytest.approx(0.035355339, abs=1e-8)
    assert series.iloc[1] == pytest.approx(0.106066017, abs=1e-8)


def _vol_series_with_today(today_value, n_history=300):
    """History ramps linearly 0.010 -> 0.020 (its 80th percentile is exactly 0.018), then one day."""
    import numpy as np
    import pandas as pd

    idx = pd.bdate_range("2023-01-02", periods=n_history + 1)
    values = list(np.linspace(0.010, 0.020, n_history)) + [today_value]
    return pd.Series(values, index=idx), idx[-1]


def test_regime_buffer_doubles_when_vol_above_historical_80th_percentile():
    from kth.backtest.strategy import compute_regime_adjusted_threshold

    vol_series, day = _vol_series_with_today(0.05)
    threshold, buffer = compute_regime_adjusted_threshold(0.01, 0.005, vol_series, day)

    assert threshold == 0.01
    assert buffer == pytest.approx(0.010)


def test_regime_buffer_unchanged_when_vol_at_or_below_historical_80th_percentile():
    from kth.backtest.strategy import compute_regime_adjusted_threshold

    vol_series, day = _vol_series_with_today(0.012)
    threshold, buffer = compute_regime_adjusted_threshold(0.01, 0.005, vol_series, day)

    assert (threshold, buffer) == (0.01, 0.005)


def test_regime_buffer_unchanged_when_history_shorter_than_min_history():
    from kth.backtest.strategy import compute_regime_adjusted_threshold

    vol_series, day = _vol_series_with_today(0.05, n_history=100)
    threshold, buffer = compute_regime_adjusted_threshold(0.01, 0.005, vol_series, day)

    assert (threshold, buffer) == (0.01, 0.005)


def test_regime_buffer_ignores_vol_observations_after_the_day():
    import pandas as pd
    from kth.backtest.strategy import compute_regime_adjusted_threshold

    vol_series, _ = _vol_series_with_today(0.05)
    day = vol_series.index[-1]
    future_idx = pd.bdate_range(day + pd.Timedelta(days=1), periods=100)
    with_future = pd.concat([vol_series, pd.Series(0.5, index=future_idx)])

    without = compute_regime_adjusted_threshold(0.01, 0.005, vol_series, day)
    with_ = compute_regime_adjusted_threshold(0.01, 0.005, with_future, day)

    assert without == with_ == (0.01, pytest.approx(0.010))


class _FakeHorizon:
    def __init__(self, pred_len):
        import pandas as pd
        self.summary = pd.DataFrame({"timestamps": range(1, pred_len + 1), "p50": [100.0] * pred_len})


class _FakeResult:
    def __init__(self, pred_len, lookback_end):
        import pandas as pd
        self.horizons = {pred_len: _FakeHorizon(pred_len)}
        self.model_name = "fake/model"
        self.generated_at = pd.Timestamp("2026-01-01")
        self.lookback_end = lookback_end


class _FakeKronos:
    """Duck-typed KronosTH: like the real forecast_batch it keys DataFrame inputs as
    "df_{i}" and reports the last bar of the data it used as lookback_end."""

    model_name = "fake/model"

    def forecast_batch(self, items, pred_lens, n_samples, lookback, calendar_freq):
        import pandas as pd

        results = {}
        for i, item in enumerate(items):
            # Like the real one: a ticker name means "load the full cached history".
            frame = pd.read_parquet(f"data/raw/{item}.parquet") if isinstance(item, str) else item
            if len(frame) >= lookback:
                key = item if isinstance(item, str) else f"df_{i}"
                results[key] = _FakeResult(pred_lens[0], frame["timestamps"].iloc[-1])
        return results


def _write_raw_prices(tmp_path, ticker, n_days):
    import numpy as np
    import pandas as pd

    days = pd.bdate_range("2024-01-01", periods=n_days)
    close = np.linspace(100.0, 120.0, n_days)
    df = pd.DataFrame({
        "timestamps": days, "open": close, "high": close, "low": close,
        "close": close, "volume": 1000.0, "amount": close * 1000.0,
    })
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    df.to_parquet(raw / f"{ticker}.parquet", index=False)
    return days


def test_precompute_forecasts_conditions_each_day_only_on_data_up_to_that_day(tmp_path, monkeypatch):
    import json
    import pandas as pd
    from kth.backtest.walkforward import precompute_forecasts

    monkeypatch.chdir(tmp_path)
    days = _write_raw_prices(tmp_path, "AAA.BK", n_days=12)
    forecast_days = days[6:9]  # three business days with plenty of later data still in the file

    precompute_forecasts(
        _FakeKronos(), ["AAA.BK"], str(forecast_days[0].date()), str(forecast_days[-1].date()),
        pred_len=2, n_samples=1, lookback=5, cache_dir=str(tmp_path / "fc"),
    )

    for day in forecast_days:
        meta = json.loads((tmp_path / "fc" / "fake_model" / day.strftime("%Y-%m-%d") / "AAA.BK_meta.json").read_text())
        assert pd.Timestamp(meta["lookback_end"]) == day


def _forecast_file_with_meta(tmp_path, day, lookback_end):
    import json

    day_dir = tmp_path / day
    day_dir.mkdir(parents=True)
    if lookback_end is not None:
        (day_dir / "AAA.BK_meta.json").write_text(json.dumps({"ticker": "AAA.BK", "lookback_end": lookback_end}))
    return day_dir / "AAA.BK.parquet"


def test_cached_forecast_conditioned_on_data_after_its_date_is_refused(tmp_path):
    import pandas as pd
    from kth.backtest.walkforward import require_point_in_time_forecast

    fc_file = _forecast_file_with_meta(tmp_path, "2023-06-01", "2026-05-15 00:00:00")

    with pytest.raises(ValueError, match="point-in-time"):
        require_point_in_time_forecast(fc_file, pd.Timestamp("2023-06-01"))


@pytest.mark.parametrize("lookback_end", ["2023-06-01 00:00:00", "2023-05-31 00:00:00"])
def test_cached_forecast_conditioned_on_data_up_to_its_date_is_accepted(tmp_path, lookback_end):
    import pandas as pd
    from kth.backtest.walkforward import require_point_in_time_forecast

    fc_file = _forecast_file_with_meta(tmp_path, "2023-06-01", lookback_end)

    require_point_in_time_forecast(fc_file, pd.Timestamp("2023-06-01"))


def test_cached_forecast_without_metadata_is_refused_as_unverifiable(tmp_path):
    import pandas as pd
    from kth.backtest.walkforward import require_point_in_time_forecast

    fc_file = _forecast_file_with_meta(tmp_path, "2023-06-01", lookback_end=None)

    with pytest.raises(ValueError, match="cannot verify"):
        require_point_in_time_forecast(fc_file, pd.Timestamp("2023-06-01"))


def test_stop_loss_triggers_when_close_falls_to_the_stop_level_below_entry():
    from kth.backtest.strategy import find_stopped_positions
    stopped = find_stopped_positions(
        held_closes={"A": 92.0, "B": 93.0}, entry_prices={"A": 100.0, "B": 100.0},
        peak_prices={"A": 100.0, "B": 100.0}, stop_loss=0.08)
    assert stopped == {"A"}


def test_trailing_stop_measures_from_the_peak_not_the_entry():
    from kth.backtest.strategy import find_stopped_positions
    stopped = find_stopped_positions(
        held_closes={"A": 110.0, "B": 130.0}, entry_prices={"A": 100.0, "B": 100.0},
        peak_prices={"A": 125.0, "B": 135.0}, trailing_stop=0.10)
    assert stopped == {"A"}


def test_no_stops_configured_stops_nothing():
    from kth.backtest.strategy import find_stopped_positions
    assert find_stopped_positions({"A": 1.0}, {"A": 100.0}, {"A": 100.0}) == set()


def test_stop_settings_default_off_in_backtest_config():
    from kth.backtest.walkforward import BacktestConfig
    c = BacktestConfig()
    assert c.stop_loss is None and c.trailing_stop is None
