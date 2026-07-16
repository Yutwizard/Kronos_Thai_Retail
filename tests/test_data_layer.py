"""Tests for the data layer — schema conversion, quality report, cache round-trip,
universe generation, and Kronos predictor input format.

Ported from verify_data_layer.py (which used inline print-based blocks, not functions).
Uses the tmp_cache fixture from conftest.py so no writes hit the real ./data/raw.
"""
import pandas as pd

from kth.data.loader import load_cached, quality_report, to_kronos_format
from kth.data.universe import get_all_tickers_including_features, get_ticker_class
from kth.testing.synthetic import make_synthetic_yf


def test_schema_conversion():
    """yfinance -> Kronos schema conversion produces all required columns."""
    yf_df = make_synthetic_yf("AAPL", n_days=500, seed=42)
    k_df = to_kronos_format(yf_df, "AAPL")
    required = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
    missing = set(required) - set(k_df.columns)
    assert not missing, f"Missing columns: {missing}"


def test_quality_report_catches_issues(tmp_cache):
    """quality_report must flag zero-volume days and big moves."""
    yf_bad = make_synthetic_yf("BTC-USD", n_days=300, seed=1)
    yf_bad.iloc[10:15, yf_bad.columns.get_loc("Volume")] = 0
    yf_bad.iloc[100, yf_bad.columns.get_loc("Close")] *= 1.5
    yf_bad.iloc[101, yf_bad.columns.get_loc("Close")] *= 0.7

    k_bad = to_kronos_format(yf_bad, "BTC-USD")
    rpt = quality_report(k_bad, "BTC-USD")
    assert rpt["zero_vol_days"] >= 5, "should catch zero-volume days"
    assert rpt["big_moves_30pct"] >= 1, "should catch the injected 50% spike"


def test_cache_round_trip(tmp_cache):
    """Cache write -> read round-trip must be identical."""
    yf_df = make_synthetic_yf("AAPL", n_days=500, seed=42)
    k_df = to_kronos_format(yf_df, "AAPL")
    k_df.to_parquet(tmp_cache / "AAPL.parquet", index=False)

    loaded = load_cached("AAPL", cache_dir=str(tmp_cache))
    pd.testing.assert_frame_equal(k_df, loaded, check_dtype=False)


def test_cross_asset_universe_generation(tmp_cache):
    """Generate full universe (synthetic) and verify every ticker round-trips."""
    all_tickers = get_all_tickers_including_features()
    asset_classes = set()
    for i, t in enumerate(all_tickers, 1):
        yf_df = make_synthetic_yf(t, n_days=1260, seed=i)
        k_df = to_kronos_format(yf_df, t)
        safe = t.replace("^", "_").replace("=", "_")
        k_df.to_parquet(tmp_cache / f"{safe}.parquet", index=False)
        rpt = quality_report(k_df, t)
        asset_classes.add(get_ticker_class(t))
        assert rpt["rows"] > 0, f"{t}: no rows generated"
    assert len(all_tickers) == 52, f"Universe should be 52 tickers, got {len(all_tickers)}"
    assert len(asset_classes) == 2, f"Expected 2 asset classes, got {asset_classes}"


def test_kronos_input_format_check(tmp_cache):
    """Cached frame must be sliceable into the shapes KronosPredictor.predict() expects."""
    yf_df = make_synthetic_yf("PTT.BK", n_days=500, seed=7)
    k_df = to_kronos_format(yf_df, "PTT.BK")
    k_df.to_parquet(tmp_cache / "PTT.BK.parquet", index=False)

    sample = load_cached("PTT.BK", cache_dir=str(tmp_cache))
    lookback = 400
    pred_len = 20

    x_df = sample.iloc[:lookback][["open", "high", "low", "close", "volume", "amount"]]
    x_ts = sample.iloc[:lookback]["timestamps"]
    last = x_ts.iloc[-1]
    y_ts = pd.Series(pd.bdate_range(start=last + pd.Timedelta(days=1), periods=pred_len, freq="B"))

    assert x_df.shape == (lookback, 6), f"x_df shape wrong: {x_df.shape}"
    assert len(x_ts) == lookback
    assert len(y_ts) == pred_len
