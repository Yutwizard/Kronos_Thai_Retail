"""Tests for kth.data.pricestore.PriceStore — the single seam for cached-OHLCV reads."""
import pandas as pd
import pytest

from kth.data.pricestore import PriceStore
from kth.data.loader import sanitize_ticker


def _frame(closes):
    n = len(closes)
    return pd.DataFrame({
        "timestamps": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [1000.0] * n, "amount": [c * 1000.0 for c in closes],
    })


def test_sanitize_ticker():
    assert sanitize_ticker("^SET.BK") == "_SET.BK"
    assert sanitize_ticker("THB=X") == "THB_X"
    assert sanitize_ticker("AOT.BK") == "AOT.BK"


def test_get_close_returns_last_close(tmp_cache):
    _frame([10.0, 11.0, 12.5]).to_parquet(tmp_cache / "AOT.BK.parquet", index=False)
    store = PriceStore(cache_dir=str(tmp_cache))
    assert store.get_close("AOT.BK") == 12.5


def test_get_close_memoizes_within_instance(tmp_cache):
    _frame([10.0, 11.0]).to_parquet(tmp_cache / "AOT.BK.parquet", index=False)
    calls = []

    def counting_read(path):
        calls.append(path)
        return pd.read_parquet(path)

    store = PriceStore(cache_dir=str(tmp_cache), read_fn=counting_read)
    assert store.get_close("AOT.BK") == 11.0
    assert store.get_close("AOT.BK") == 11.0
    assert store.get_ohlcv("AOT.BK") is store.get_ohlcv("AOT.BK")
    assert len(calls) == 1


def test_instances_do_not_share_memo(tmp_cache):
    # Per-run memo: a fresh store must re-read (no stale closes across days).
    _frame([10.0]).to_parquet(tmp_cache / "AOT.BK.parquet", index=False)
    first = PriceStore(cache_dir=str(tmp_cache))
    assert first.get_close("AOT.BK") == 10.0
    _frame([99.0]).to_parquet(tmp_cache / "AOT.BK.parquet", index=False)
    second = PriceStore(cache_dir=str(tmp_cache))
    assert second.get_close("AOT.BK") == 99.0


def test_get_close_missing_ticker_returns_none(tmp_cache):
    store = PriceStore(cache_dir=str(tmp_cache))
    assert store.get_close("NOPE.BK") is None


def test_get_ohlcv_missing_ticker_raises_like_load_cached(tmp_cache):
    store = PriceStore(cache_dir=str(tmp_cache))
    with pytest.raises(FileNotFoundError):
        store.get_ohlcv("NOPE.BK")


def test_batch_returns_frame_per_ticker(tmp_cache):
    _frame([10.0]).to_parquet(tmp_cache / "AOT.BK.parquet", index=False)
    _frame([20.0]).to_parquet(tmp_cache / "PTT.BK.parquet", index=False)
    store = PriceStore(cache_dir=str(tmp_cache))
    out = store.batch(["AOT.BK", "PTT.BK", "NOPE.BK"])
    assert set(out) == {"AOT.BK", "PTT.BK"}
    assert float(out["PTT.BK"]["close"].iloc[-1]) == 20.0


def test_with_frames_skips_disk(tmp_cache):
    store = PriceStore.with_frames({"AOT.BK": _frame([7.5])}, cache_dir=str(tmp_cache))
    assert store.get_close("AOT.BK") == 7.5
    assert store.get_close("PTT.BK") is None  # falls back to disk, still missing


def test_sanitized_names_hit_same_file(tmp_cache):
    _frame([5.0]).to_parquet(tmp_cache / "_SET.BK.parquet", index=False)
    store = PriceStore(cache_dir=str(tmp_cache))
    assert store.get_close("^SET.BK") == 5.0
