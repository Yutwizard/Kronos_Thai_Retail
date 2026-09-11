"""Tests for kth.trading.execution.ExecutionResolver — one adapter for the
underlying→execution seam (DR tickers vs plain tickers)."""
import sys

import pandas as pd

from kth.data.pricestore import PriceStore
from kth.trading.execution import ExecutionResolver


def _block_dr_plugin(monkeypatch):
    monkeypatch.setitem(sys.modules, "kth_dr.trade_gen_dr", None)
    monkeypatch.setitem(sys.modules, "kth_dr.loader_dr", None)


def test_resolver_is_identity_without_dr_plugin(monkeypatch, tmp_cache):
    _block_dr_plugin(monkeypatch)
    resolver = ExecutionResolver(PriceStore(cache_dir=str(tmp_cache)))
    assert resolver.execution_ticker("AOT.BK") == "AOT.BK"
    assert resolver.execution_price("AOT.BK", "AOT.BK", 100.0) == 100.0
    assert resolver.display_name("AOT.BK", "Fallback") == "Fallback"
    assert resolver.premium("AOT.BK", 100.0) == ("", None)
    assert resolver.is_held_underlying(["AOT.BK"], "PTT.BK") is False


def test_resolver_delegates_plain_ticker_to_kth_dr(tmp_cache):
    resolver = ExecutionResolver(PriceStore(cache_dir=str(tmp_cache)))
    assert resolver.execution_ticker("AOT.BK") == "AOT.BK"
    assert resolver.execution_price("AOT.BK", "AOT.BK", 100.0) == 100.0
    assert resolver.display_name("AOT.BK", "Fallback") == "Fallback"
    assert resolver.premium("AOT.BK", 100.0) == ("", None)
    assert resolver.is_held_underlying(["AOT.BK"], "AOT.BK") is True
    assert resolver.is_held_underlying(["AOT.BK"], "PTT.BK") is False


def test_resolver_premium_needs_no_store_for_plain_ticker(tmp_cache):
    # Non-DR premium short-circuits before any price read — an empty store
    # (and no disk) must suffice.
    resolver = ExecutionResolver(PriceStore(cache_dir=str(tmp_cache)))
    assert resolver.premium("AOT.BK", 100.0) == ("", None)


def test_load_forecasts_accepts_injected_resolver(monkeypatch, tmp_path):
    from kth.trading import trade_gen

    report_date = "2026-08-18"
    day_dir = tmp_path / report_date
    day_dir.mkdir()
    (day_dir / "AAPL.parquet").touch()

    monkeypatch.setattr(trade_gen, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(trade_gen, "TRADABLE_TICKERS", ["AAPL"])
    monkeypatch.setattr(trade_gen.pd, "read_parquet", lambda _: pd.DataFrame({
        "p5": [90.0], "p50": [110.0], "p95": [130.0], "mean": [112.0]
    }))
    monkeypatch.setattr(trade_gen, "get_ticker_class", lambda _: "thai_equity")
    monkeypatch.setattr(trade_gen, "get_friction", lambda _: {
        "commission_oneway": 0.001, "slippage_oneway": 0.001
    })
    monkeypatch.setattr(trade_gen, "get_sector", lambda _: "other")
    monkeypatch.setattr(trade_gen, "get_currency_group", lambda _: None)
    monkeypatch.setattr(trade_gen, "get_display_name", lambda _: "Apple")

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

    rows = trade_gen.load_forecasts(
        report_date, prices=_FakePrices(), resolver=_FakeResolver())
    assert len(rows) == 1
    row = rows[0]
    assert row["execution_ticker"] == "AAPL80.BK"
    assert row["target_price"] == 55.0  # 110 * 50/100, execution scale
    assert row["p50_close"] == 110.0  # raw underlying scale untouched
