import pandas as pd
from kth.data.versioning import write_manifest, verify_manifest


def test_write_and_verify_manifest(tmp_path):
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=10),
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1,
    })
    df.to_parquet(tmp_path / "AAPL.parquet", index=False)
    m = write_manifest(tmp_path, ["AAPL"])
    assert "AAPL" in m["tickers"]
    assert m["tickers"]["AAPL"]["rows"] == 10
    v = verify_manifest(tmp_path)
    assert v["ok"] is True


def test_verify_detects_missing(tmp_path):
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=10),
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1,
    })
    df.to_parquet(tmp_path / "AAPL.parquet", index=False)
    write_manifest(tmp_path, ["AAPL"])
    (tmp_path / "AAPL.parquet").unlink()
    v = verify_manifest(tmp_path)
    assert v["ok"] is False
    assert "AAPL" in v["missing"]


def test_verify_detects_hash_mismatch(tmp_path):
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=10),
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1,
    })
    df.to_parquet(tmp_path / "AAPL.parquet", index=False)
    write_manifest(tmp_path, ["AAPL"])
    df2 = df.copy()
    df2["close"] = 999
    df2.to_parquet(tmp_path / "AAPL.parquet", index=False)
    v = verify_manifest(tmp_path)
    assert v["ok"] is False
    assert len(v["mismatches"]) == 1


def test_verify_no_manifest_returns_error(tmp_path):
    v = verify_manifest(tmp_path)
    assert v["ok"] is False
    assert "error" in v


def test_verify_strict_raises(tmp_path):
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=10),
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1,
    })
    df.to_parquet(tmp_path / "AAPL.parquet", index=False)
    write_manifest(tmp_path, ["AAPL"])
    (tmp_path / "AAPL.parquet").unlink()
    import pytest
    with pytest.raises(RuntimeError, match="Data cache mismatch"):
        verify_manifest(tmp_path, strict=True)
