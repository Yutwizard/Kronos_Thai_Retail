import pandas as pd
import pytest

from kth.trading import trade_gen
from kth.trading.trade_gen import _execution_forecast_price


def test_execution_forecast_price_keeps_native_scale():
    assert _execution_forecast_price(100.0, 105.0, 100.0) == pytest.approx(105.0)


def test_execution_forecast_price_scales_forecast_for_dr():
    assert _execution_forecast_price(100.0, 110.0, 50.0) == pytest.approx(55.0)


def test_execution_forecast_price_returns_none_when_underlying_close_is_invalid():
    assert _execution_forecast_price(0.0, 110.0, 50.0) is None


def test_execution_forecast_price_returns_none_when_execution_close_is_invalid():
    assert _execution_forecast_price(100.0, 110.0, 0.0) is None


@pytest.mark.parametrize("underlying_close, execution_close", [
    (100.0, None),
    (float("nan"), 50.0),
    (100.0, float("inf")),
])
def test_execution_forecast_price_returns_none_for_non_finite_scale(
    underlying_close, execution_close
):
    assert _execution_forecast_price(underlying_close, 110.0, execution_close) is None


def test_load_forecasts_exposes_execution_scale_targets_without_changing_raw_prices(
    monkeypatch, tmp_path
):
    report_date = "2026-08-18"
    day_dir = tmp_path / report_date
    day_dir.mkdir()
    (day_dir / "AAPL.parquet").touch()

    monkeypatch.setattr(trade_gen, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(trade_gen, "TRADABLE_TICKERS", ["AAPL"])
    monkeypatch.setattr(trade_gen.pd, "read_parquet", lambda _: pd.DataFrame({
        "p5": [90.0], "p50": [110.0], "p95": [130.0], "mean": [112.0]
    }))

    class _FakePrices:
        def get_close(self, ticker):
            return 100.0

    class _FakeResolver:
        def execution_ticker(self, ticker):
            return "AAPL80.BK"

        def execution_price(self, underlying, exec_ticker, underlying_close):
            return 50.0

        def display_name(self, ticker, fallback):
            return fallback

        def premium(self, exec_ticker, exec_close):
            return ("", None)

    monkeypatch.setattr(trade_gen, "get_ticker_class", lambda _: "thai_equity")
    monkeypatch.setattr(trade_gen, "get_friction", lambda _: {
        "commission_oneway": 0.001, "slippage_oneway": 0.001
    })
    monkeypatch.setattr(trade_gen, "get_sector", lambda _: "other")
    monkeypatch.setattr(trade_gen, "get_currency_group", lambda _: None)
    monkeypatch.setattr(trade_gen, "get_display_name", lambda _: "Apple")

    row = trade_gen.load_forecasts(report_date, prices=_FakePrices(), resolver=_FakeResolver())[0]

    assert row["p50_close"] == pytest.approx(110.0)
    assert row["p95_close"] == pytest.approx(130.0)
    assert row["target_price"] == pytest.approx(55.0)
    assert row["p95_price"] == pytest.approx(65.0)


def test_load_forecasts_uses_none_for_invalid_execution_scale(monkeypatch, tmp_path):
    report_date = "2026-08-18"
    day_dir = tmp_path / report_date
    day_dir.mkdir()
    (day_dir / "AAPL.parquet").touch()

    monkeypatch.setattr(trade_gen, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(trade_gen, "TRADABLE_TICKERS", ["AAPL"])
    monkeypatch.setattr(trade_gen.pd, "read_parquet", lambda _: pd.DataFrame({
        "p5": [90.0], "p50": [110.0], "p95": [130.0], "mean": [112.0]
    }))

    class _FakePrices:
        def get_close(self, ticker):
            return 100.0

    class _FakeResolver:
        def execution_ticker(self, ticker):
            return "AAPL80.BK"

        def execution_price(self, underlying, exec_ticker, underlying_close):
            return float("nan")

        def display_name(self, ticker, fallback):
            return fallback

        def premium(self, exec_ticker, exec_close):
            return ("", None)

    monkeypatch.setattr(trade_gen, "get_ticker_class", lambda _: "thai_equity")
    monkeypatch.setattr(trade_gen, "get_friction", lambda _: {
        "commission_oneway": 0.001, "slippage_oneway": 0.001
    })
    monkeypatch.setattr(trade_gen, "get_sector", lambda _: "other")
    monkeypatch.setattr(trade_gen, "get_currency_group", lambda _: None)
    monkeypatch.setattr(trade_gen, "get_display_name", lambda _: "Apple")

    row = trade_gen.load_forecasts(report_date, prices=_FakePrices(), resolver=_FakeResolver())[0]

    assert row["target_price"] is None
    assert row["p95_price"] is None
