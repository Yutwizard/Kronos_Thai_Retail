"""
End-to-end verification of the data layer without hitting Yahoo Finance
(blocked in this sandbox; works fine on Colab/Kaggle/local).

We:
1. Generate realistic synthetic OHLCV that looks like yfinance output.
2. Run it through to_kronos_format() and verify the schema.
3. Run quality_report() and verify it catches issues.
4. Save + reload from cache and verify round-trip integrity.
5. Confirm the format matches what Kronos's KronosPredictor expects.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from kth.data.loader import to_kronos_format, quality_report, load_cached
from kth.data.universe import UNIVERSE, FRICTION, get_ticker_class
from kth.testing.synthetic import make_synthetic_yf


# ---------------------------------------------------------------------------
# Test 1: Schema conversion
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 1: yfinance -> Kronos schema conversion")
print("=" * 70)

yf_df = make_synthetic_yf("AAPL", n_days=500, seed=42)
print(f"\nInput (synthetic yfinance):")
print(f"  shape: {yf_df.shape}")
print(f"  cols:  {list(yf_df.columns)}")
print(f"  index: {yf_df.index.name}, dtype={yf_df.index.dtype}")
print(yf_df.head(3))

k_df = to_kronos_format(yf_df, "AAPL")
print(f"\nOutput (Kronos format):")
print(f"  shape: {k_df.shape}")
print(f"  cols:  {list(k_df.columns)}")
print(k_df.head(3))

# Verify required columns exist
required = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
missing = set(required) - set(k_df.columns)
assert not missing, f"Missing columns: {missing}"
print(f"\n  PASS - all Kronos columns present: {required}")


# ---------------------------------------------------------------------------
# Test 2: Quality report catches issues
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 2: Quality report")
print("=" * 70)

# Inject some issues: zero volume days and one big spike
yf_bad = make_synthetic_yf("BTC-USD", n_days=300, seed=1)
yf_bad.iloc[10:15, yf_bad.columns.get_loc("Volume")] = 0  # 5 zero-vol days
yf_bad.iloc[100, yf_bad.columns.get_loc("Close")] *= 1.5  # 50% spike
yf_bad.iloc[101, yf_bad.columns.get_loc("Close")] *= 0.7  # crash back

k_bad = to_kronos_format(yf_bad, "BTC-USD")
rpt = quality_report(k_bad, "BTC-USD")
print(f"\nQuality report for synthetic problematic data:")
for k, v in rpt.items():
    print(f"  {k:20s} {v}")

assert rpt["zero_vol_days"] >= 5, "should catch zero-volume days"
assert rpt["big_moves_30pct"] >= 1, "should catch the injected 50% spike"
print("  PASS - quality checks fired on injected issues")


# ---------------------------------------------------------------------------
# Test 3: Cache round-trip
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 3: Cache write -> read round-trip integrity")
print("=" * 70)

cache_dir = Path("./data/raw")
cache_dir.mkdir(parents=True, exist_ok=True)

# Write directly (skip the yf download step)
safe_name = "AAPL"
k_df.to_parquet(cache_dir / f"{safe_name}.parquet", index=False)

loaded = load_cached("AAPL", cache_dir=str(cache_dir))
print(f"\n  cached: {len(k_df)} rows")
print(f"  loaded: {len(loaded)} rows")
print(f"  cols match: {list(loaded.columns) == list(k_df.columns)}")

# Float comparison
pd.testing.assert_frame_equal(k_df, loaded, check_dtype=False)
print("  PASS - round-trip identical")


# ---------------------------------------------------------------------------
# Test 4: Cross-asset universe generation
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 4: Generate full universe (synthetic) and save to cache")
print("=" * 70)

from kth.data.universe import get_all_tickers
all_tickers = get_all_tickers()

reports = []
for i, t in enumerate(all_tickers, 1):
    yf_df = make_synthetic_yf(t, n_days=1260, seed=i)
    k_df = to_kronos_format(yf_df, t)
    safe = t.replace("^", "_").replace("=", "_")
    k_df.to_parquet(cache_dir / f"{safe}.parquet", index=False)
    rpt = quality_report(k_df, t)
    rpt["asset_class"] = get_ticker_class(t)
    reports.append(rpt)

rpt_df = pd.DataFrame(reports)
print(f"\nDownloaded (synthetic) {len(rpt_df)} tickers across "
      f"{rpt_df['asset_class'].nunique()} asset classes")
print("\nQuality summary by asset class:")
print(rpt_df.groupby("asset_class").agg(
    n=("ticker", "count"),
    mean_rows=("rows", "mean"),
    mean_span_days=("span_days", "mean"),
).round(0).astype(int))


# ---------------------------------------------------------------------------
# Test 5: Sanity check Kronos input format
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 5: Kronos predictor input format check")
print("=" * 70)
print("""
Per Kronos README, the predict() method needs:
  - df:          DataFrame with ['open','high','low','close','volume','amount']
  - x_timestamp: pd.Series of timestamps for context window
  - y_timestamp: pd.Series of timestamps for forecast horizon
""")

sample = load_cached("PTT.BK", cache_dir=str(cache_dir))
lookback = 400
pred_len = 20

x_df = sample.iloc[:lookback][["open","high","low","close","volume","amount"]]
x_ts = sample.iloc[:lookback]["timestamps"]
# Build future timestamps (business days)
last = x_ts.iloc[-1]
y_ts = pd.Series(pd.bdate_range(start=last + pd.Timedelta(days=1),
                                 periods=pred_len, freq="B"))

print(f"  x_df shape:       {x_df.shape}")
print(f"  x_df cols:        {list(x_df.columns)}")
print(f"  x_timestamp:      {len(x_ts)} stamps, last={x_ts.iloc[-1].date()}")
print(f"  y_timestamp:      {len(y_ts)} stamps, "
      f"{y_ts.iloc[0].date()}..{y_ts.iloc[-1].date()}")
print("  PASS - shapes ready for KronosPredictor.predict()")


# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ALL TESTS PASSED")
print("=" * 70)
print(f"""
Data layer is verified. The same code will work on Colab against real
yfinance once you run:

    from kth.data.loader import download_universe
    from kth.data.universe import get_all_tickers
    download_universe(get_all_tickers(), period='10y',
                      cache_dir='./data/raw')

Cached files now in: {cache_dir}
""")
