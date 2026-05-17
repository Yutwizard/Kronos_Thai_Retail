"""
End-to-end verification of the Kronos wrapper without HuggingFace download.
Mocks KronosPredictor.predict_batch to return random walk paths (NOT zeros)
so percentile ordering can be validated.
"""
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup: mock kronos module before importing our wrapper
# ---------------------------------------------------------------------------
mock_kronos = MagicMock()

# KronosTokenizer + Kronos return new mocks each call (different keys -> different instances)
mock_kronos.KronosTokenizer = MagicMock()
mock_kronos.Kronos = MagicMock()
mock_kronos.KronosTokenizer.from_pretrained = MagicMock(side_effect=lambda *a, **kw: MagicMock())
mock_kronos.Kronos.from_pretrained = MagicMock(side_effect=lambda *a, **kw: MagicMock())

# KronosPredictor: each constructor returns a unique mock with predict() configured
def _make_predictor(*args, **kwargs):
    p = MagicMock()
    def _mock_predict(df, x_timestamp, y_timestamp, pred_len, T=1.0, top_k=0, top_p=0.9, sample_count=1, verbose=False):
        max_len = len(y_timestamp)
        rng = np.random.default_rng(42)
        base_price = df["close"].iloc[-1] if len(df) > 0 else 100.0
        path = np.zeros(max_len)
        drift = rng.normal(0.0005, 0.01, max_len)
        path[:] = base_price * np.exp(np.cumsum(drift))
        return pd.DataFrame({"close": path, "open": path, "high": path, "low": path, "volume": np.zeros(max_len), "amount": np.zeros(max_len)})
    p.predict.side_effect = _mock_predict
    return p

mock_kronos.KronosPredictor = MagicMock(side_effect=_make_predictor)

import sys
sys.modules["kronos"] = mock_kronos
sys.modules["huggingface_hub"] = MagicMock()

# Pre-create checkpoint dirs so _resolve_local_checkpoint returns early
# without actually calling huggingface_hub APIs
for model_name in ["NeoQuasar_Kronos-small", "NeoQuasar_Kronos-base"]:
    ckpt_dir = Path("./checkpoints") / model_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    (ckpt_dir / "commit_hash.txt").write_text("mockabc123")

from kth.models.kronos_wrapper import (
    KronosTH, ForecastResult, HorizonForecast, _MODEL_CACHE
)
from kth.data.loader import to_kronos_format
from kth.data.universe import get_all_tickers

# Create synthetic data matching verify_data_layer.py pattern
def make_synthetic_yf(ticker: str, n_days: int = 1260, seed: int = 0) -> pd.DataFrame:
    from kth.data.universe import get_ticker_class
    rng = np.random.default_rng(seed)
    cls = get_ticker_class(ticker)
    vol_per_day = {
        "thai_equity": 0.015, "thai_index": 0.010, "us_equity": 0.018,
        "etf_global": 0.010, "commodity": 0.012, "crypto": 0.045,
        "bond_proxy": 0.005, "reit": 0.013, "fx_macro": 0.005,
    }.get(cls, 0.015)
    drift_per_day = 0.0003
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(),
                           periods=n_days, freq="B", name="Date")
    n = len(dates)
    log_rets = rng.normal(drift_per_day, vol_per_day, n)
    close = 100.0 * np.exp(np.cumsum(log_rets))
    intra_range = np.abs(rng.normal(0, vol_per_day, n))
    high = close * (1 + intra_range)
    low = close * (1 - intra_range)
    open_ = np.concatenate([[close[0]], close[:-1]]) * (
        1 + rng.normal(0, vol_per_day * 0.3, n)
    )
    base_vol = 1_000_000 * (1 + 5 * np.abs(log_rets))
    volume = (base_vol * rng.uniform(0.7, 1.3, n)).astype(np.int64)
    df = pd.DataFrame(
        {"Open": open_, "High": np.maximum.reduce([open_, close, high]),
         "Low": np.minimum.reduce([open_, close, low]),
         "Close": close, "Volume": volume},
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# Ensure cache dir exists with synthetic data
# ---------------------------------------------------------------------------
cache_dir = Path("./data/raw")
cache_dir.mkdir(parents=True, exist_ok=True)
all_tickers = get_all_tickers()
for i, t in enumerate(all_tickers, 1):
    yf_df = make_synthetic_yf(t, n_days=600, seed=i)
    k_df = to_kronos_format(yf_df, t)
    safe = t.replace("^", "_").replace("=", "_")
    k_df.to_parquet(cache_dir / f"{safe}.parquet", index=False)


# ---------------------------------------------------------------------------
# Test 1: Constructor + model cache
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 1: Constructor + model cache singleton")
print("=" * 70)

_MODEL_CACHE.clear()
k1 = KronosTH.from_pretrained("NeoQuasar/Kronos-small")
k2 = KronosTH.from_pretrained("NeoQuasar/Kronos-small")
assert k1._predictor is k2._predictor, "cache not shared between instances"
print("  PASS - two instances share same cached model")

k3 = KronosTH.from_pretrained("NeoQuasar/Kronos-base")
assert k3._predictor is not k1._predictor, "different models should not share cache entry"
print("  PASS - different models get separate cache entries")


# ---------------------------------------------------------------------------
# Test 2: String input — forecast("AAPL")
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 2: forecast() with string ticker input")
print("=" * 70)

k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", cache_dir=str(cache_dir))
result = k.forecast("AAPL", pred_lens=[5, 20], n_samples=20, lookback=400)
assert isinstance(result, ForecastResult), "should return ForecastResult"
assert result.ticker == "AAPL", f"expected ticker 'AAPL', got '{result.ticker}'"
assert result.horizons is not None, "horizons should not be None"
print(f"  ticker: {result.ticker}")
print(f"  generated_at: {result.generated_at}")
print(f"  lookback_end: {result.lookback_end}")
print("  PASS - string input returns ForecastResult")


# ---------------------------------------------------------------------------
# Test 3: DataFrame input
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 3: forecast() with DataFrame input")
print("=" * 70)

df = to_kronos_format(make_synthetic_yf("PTT.BK", n_days=600, seed=99), "PTT.BK")
result_df = k.forecast(df, pred_lens=[5, 20], n_samples=20, lookback=400)
assert isinstance(result_df, ForecastResult)
assert result_df.ticker == "<dataframe>"
print("  PASS - DataFrame input returns ForecastResult")


# ---------------------------------------------------------------------------
# Test 4: Output shape
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 4: Output shape — summary + samples")
print("=" * 70)

h20 = result.horizons[20]
assert h20.summary.shape == (20, 7), f"summary shape {h20.summary.shape}, expected (20, 7)"
assert h20.samples.shape == (20, 21), f"samples shape {h20.samples.shape}, expected (20, 21)"
print(f"  summary columns: {list(h20.summary.columns)}")
print(f"  samples columns: first={h20.samples.columns[0]}, last={h20.samples.columns[-1]}")
print("  PASS - output shapes correct")


# ---------------------------------------------------------------------------
# Test 5: Ordering invariant — p5 <= p25 <= p50 <= p75 <= p95
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 5: Percentile ordering invariant")
print("=" * 70)

summary = result.horizons[20].summary
for idx, row in summary.iterrows():
    assert row["p5"] <= row["p25"] <= row["p50"] <= row["p75"] <= row["p95"], \
        f"ordering violation at row {idx}: {row[['p5','p25','p50','p75','p95']].to_dict()}"
print("  PASS - p5 <= p25 <= p50 <= p75 <= p95 holds for all rows")


# ---------------------------------------------------------------------------
# Test 6: Both horizons present
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 6: Both horizons (5 and 20) present")
print("=" * 70)

assert 5 in result.horizons, "horizon 5 missing"
assert 20 in result.horizons, "horizon 20 missing"
assert result.horizons[5].pred_len == 5
assert result.horizons[20].pred_len == 20
print("  PASS - both horizons returned with correct pred_len")


# ---------------------------------------------------------------------------
# Test 7: lookback_end equals last x_timestamp
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 7: lookback_end invariant")
print("=" * 70)

k_df = to_kronos_format(make_synthetic_yf("AAPL", n_days=600, seed=42), "AAPL")
last_x = k_df.tail(400)["timestamps"].iloc[-1]
r = k.forecast("AAPL", pred_lens=[20], n_samples=20, lookback=400)
assert r.lookback_end == last_x, f"lookback_end {r.lookback_end} != last x_ts {last_x}"
print("  PASS - lookback_end matches last context timestamp")


# ---------------------------------------------------------------------------
# Test 8: Batch forecast
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 8: forecast_batch")
print("=" * 70)

batch_results = k.forecast_batch(["AAPL", "PTT.BK"], pred_lens=[5, 20], n_samples=20, lookback=400)
assert len(batch_results) == 2, f"expected 2 results, got {len(batch_results)}"
assert "AAPL" in batch_results, "AAPL missing from batch results"
assert "PTT.BK" in batch_results, "PTT.BK missing from batch results"
for tkr, res in batch_results.items():
    assert isinstance(res, ForecastResult), f"{tkr}: should be ForecastResult"
    assert 5 in res.horizons and 20 in res.horizons
print("  PASS - batch returns dict with both tickers and both horizons")


# ---------------------------------------------------------------------------
# Test 9: y_timestamps are integer indices, not calendar dates
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 9: y_timestamps are integer indices (not bdate_range)")
print("=" * 70)

h5_ts = result.horizons[5].summary["timestamps"].values
h20_ts = result.horizons[20].summary["timestamps"].values
assert list(h5_ts) == [1, 2, 3, 4, 5], f"expected [1,2,3,4,5], got {list(h5_ts)}"
assert list(h20_ts[:5]) == [1, 2, 3, 4, 5], f"expected [1,2,3,4,5,...], got {list(h20_ts[:5])}"
print("  PASS - y_timestamps are integer indices")


# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ALL MODEL LAYER TESTS PASSED")
print("=" * 70)
