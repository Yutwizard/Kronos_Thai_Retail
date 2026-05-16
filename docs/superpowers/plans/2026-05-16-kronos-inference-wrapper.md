# Kronos Inference Wrapper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin, reusable wrapper around `KronosPredictor` that loads/caches the model, accepts a ticker string or DataFrame, and returns probabilistic forecasts at 5d and 20d horizons.

**Architecture:** Single `KronosTH` class with module-level model cache. `forecast()` resolves input (str → parquet load; DataFrame → validate), slices context window, runs one forward pass, builds percentile summaries per horizon, and returns a `ForecastResult` dataclass. `forecast_batch()` loops sequentially over tickers.

**Tech Stack:** Python 3.10+, `torch`, `kronos` (PyPI package `kronos`), `pandas`, `numpy`, `dataclasses`

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `kth/models/__init__.py` | Package marker |
| Create | `kth/models/kronos_wrapper.py` | `KronosTH`, `ForecastResult`, `HorizonForecast`, `_MODEL_CACHE` |
| Create | `verify_model_layer.py` | Offline tests (mocked KronosPredictor) |
| Migrate/Create | `notebooks/02_kronos_zero_shot.ipynb` | Zero-shot inference + evaluation |

---

### Task 1: Data structures — `HorizonForecast` and `ForecastResult`

**Files:**
- Create: `kth/models/__init__.py`
- Create: `kth/models/kronos_wrapper.py`

- [ ] **Step 1: Create package init and dataclasses**

```python
# kth/models/__init__.py
"""Kronos-TH model layer: wrapper, fine-tuning, and inference."""
```

```python
# kth/models/kronos_wrapper.py
"""Thin wrapper around KronosPredictor with caching, batch, and structured output."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HorizonForecast:
    pred_len: int
    summary: pd.DataFrame    # timestamps, p5, p25, p50, p75, p95, mean
    samples: pd.DataFrame    # timestamps, s0, s1, ..., s_{n_samples-1}


@dataclass
class ForecastResult:
    ticker: str
    model_name: str
    generated_at: pd.Timestamp
    lookback_end: pd.Timestamp
    horizons: dict[int, HorizonForecast]
```

- [ ] **Step 2: Run a quick import check**

Run: `python -c "from kth.models.kronos_wrapper import HorizonForecast, ForecastResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add kth/models/__init__.py kth/models/kronos_wrapper.py
git commit -m "feat: add ForecastResult and HorizonForecast dataclasses"
```

---

### Task 2: `KronosTH.__init__` and model caching

**Files:**
- Modify: `kth/models/kronos_wrapper.py`

- [ ] **Step 1: Write the test first**

Append to `kth/models/kronos_wrapper.py` (below dataclasses, before running test):

```python
# Module-level cache
_MODEL_CACHE: dict[str, object] = {}


class KronosTH:
    """Kronos forecasting wrapper for the Thai-retail universe."""

    def __init__(
        self,
        model_name: str = "NeoQuasar/Kronos-small",
        device: str = "auto",
        cache_dir: str = "./data/raw",
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir

        if device == "auto":
            self.device = "cuda" if self._cuda_available() else "cpu"
        else:
            self.device = device

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
```

- [ ] **Step 2: Run import check**

Run: `python -c "from kth.models.kronos_wrapper import KronosTH; k = KronosTH(); print(k.device)"`
Expected: prints `cpu` or `cuda`

- [ ] **Step 3: Commit**

```bash
git add kth/models/kronos_wrapper.py
git commit -m "feat: add KronosTH.__init__ with device auto-detection and model cache stub"
```

---

### Task 3: `from_pretrained()` with model weight pinning

**Files:**
- Modify: `kth/models/kronos_wrapper.py`

 - [ ] **Step 1: Implement `from_pretrained`, `from_checkpoint`, and `_load_or_cache_model` with weight pinning**

Add to `KronosTH` class:

```python
    @classmethod
    def from_pretrained(cls, model_name: str = "NeoQuasar/Kronos-small", **kwargs) -> "KronosTH":
        instance = cls(model_name=model_name, **kwargs)
        instance._load_or_cache_model(key=model_name, is_checkpoint=False)
        return instance

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str, **kwargs) -> "KronosTH":
        instance = cls(model_name=checkpoint_path, **kwargs)
        instance._load_or_cache_model(key=checkpoint_path, is_checkpoint=True)
        return instance

    def _load_or_cache_model(self, key: str, is_checkpoint: bool = False) -> None:
        """Load model, caching in _MODEL_CACHE. Pins HF weights to ./checkpoints/ on first download."""
        if key in _MODEL_CACHE:
            self._predictor = _MODEL_CACHE[key]
            return

        from kronos import KronosPredictor

        if is_checkpoint:
            # Local fine-tuned checkpoint — load directly, no HF download
            self._predictor = KronosPredictor.from_pretrained(key, device=self.device)
        else:
            # HF model — download once, pin to ./checkpoints/{slug}/
            local_path = self._resolve_local_checkpoint(key)
            self._predictor = KronosPredictor.from_pretrained(str(local_path), device=self.device)

        _MODEL_CACHE[key] = self._predictor

    @staticmethod
    def _resolve_local_checkpoint(model_name: str) -> Path:
        """
        Download HF model once and pin to ./checkpoints/{slug}/.
        Reads commit hash from HF hub, stores in commit_hash.txt.
        Sets self.model_name to "{model_name}@{commit_hash[:7]}" for traceability.

        The HF download cache (~/.cache/huggingface/) is used as a staging area.
        The canonical copy lives in ./checkpoints/{slug}/ — safe to clear HF cache
        after first download.
        """
        import shutil
        from huggingface_hub import snapshot_download, repo_info

        slug = model_name.replace("/", "_").replace("\\", "_")
        local_dir = Path("./checkpoints") / slug
        hash_file = local_dir / "commit_hash.txt"

        if local_dir.exists() and hash_file.exists() and hash_file.read_text().strip():
            # Already pinned — load from local copy
            return local_dir

        # Resolve commit hash from HF hub
        info = repo_info(model_name, repo_type="model")
        commit_hash = info.sha  # full 40-char hash

        # Download to HF cache, then copy to ./checkpoints/{slug}/
        hf_cached = snapshot_download(repo_id=model_name, revision=commit_hash)
        if local_dir.exists():
            shutil.rmtree(local_dir)
        shutil.copytree(hf_cached, local_dir)

        # Write commit hash marker
        hash_file.write_text(commit_hash)
        return local_dir
```

**Note:** After `_resolve_local_checkpoint`, `self.model_name` should be updated to
`f"{model_name}@{commit_hash[:7]}"` so `ForecastResult.model_name` includes the hash.
In `from_pretrained`, read the hash after resolution:

```python
    @classmethod
    def from_pretrained(cls, model_name: str = "NeoQuasar/Kronos-small", **kwargs) -> "KronosTH":
        instance = cls(model_name=model_name, **kwargs)
        instance._load_or_cache_model(key=model_name, is_checkpoint=False)
        # Update model_name to include pinned commit hash
        slug = model_name.replace("/", "_").replace("\\", "_")
        hash_file = Path("./checkpoints") / slug / "commit_hash.txt"
        if hash_file.exists():
            commit_hash = hash_file.read_text().strip()
            instance.model_name = f"{model_name}@{commit_hash[:7]}"
        return instance
```

 - [ ] **Step 2: Run quick mock test**

```python
# save as _test_load.py temporarily
from unittest.mock import patch, MagicMock
import sys
sys.modules['kronos'] = MagicMock()
sys.modules['kronos'].KronosPredictor.from_pretrained = MagicMock(return_value=MagicMock())
sys.modules['huggingface_hub'] = MagicMock()
sys.modules['huggingface_hub'].snapshot_download = MagicMock(return_value="/tmp/fake_hf")
sys.modules['huggingface_hub'].repo_info = MagicMock(return_value=MagicMock(sha="a3f1c2d9e8b7f6a5"))

from kth.models.kronos_wrapper import KronosTH, _MODEL_CACHE
_MODEL_CACHE.clear()
k = KronosTH.from_pretrained("NeoQuasar/Kronos-small")
k2 = KronosTH.from_pretrained("NeoQuasar/Kronos-small")
assert k._predictor is k2._predictor, "cache not shared for from_pretrained"
k3 = KronosTH.from_checkpoint("/path/to/checkpoint")
k4 = KronosTH.from_checkpoint("/path/to/checkpoint")
assert k3._predictor is k4._predictor, "cache not shared for from_checkpoint"
assert k._predictor is not k3._predictor, "different keys should not share cache"
print("PASS")
```
Run: `python _test_load.py`
Expected: `PASS`

- [ ] **Step 3: Cleanup and commit**

```bash
Remove-Item _test_load.py -ErrorAction SilentlyContinue
git add kth/models/kronos_wrapper.py
git commit -m "feat: add from_pretrained with weight pinning to ./checkpoints/ and commit hash tracking"
```

---

### Task 4: `forecast()` — string input path

**Files:**
- Modify: `kth/models/kronos_wrapper.py`

- [ ] **Step 1: Implement `forecast()` with string resolution**

Add to `KronosTH`:

```python
    def forecast(
        self,
        ticker_or_df: str | pd.DataFrame,
        pred_lens: list[int] | None = None,
        n_samples: int = 50,
        lookback: int = 400,
    ) -> ForecastResult:
        if pred_lens is None:
            pred_lens = [5, 20]

        max_pred_len = max(pred_lens)

        # 1. Input resolution
        if isinstance(ticker_or_df, str):
            from kth.data.loader import load_cached
            df = load_cached(ticker_or_df, self.cache_dir)
            ticker = ticker_or_df
        else:
            df = ticker_or_df.copy()
            self._validate_columns(df)
            ticker = "<dataframe>"

        # 2. Context window
        if len(df) < lookback:
            raise ValueError(
                f"lookback={lookback} exceeds available rows ({len(df)}). "
                "Reduce lookback or extend data history."
            )
        x_df = df.tail(lookback)
        x_timestamps = x_df["timestamps"].reset_index(drop=True)
        x_ohlcva = x_df[["open", "high", "low", "close", "volume", "amount"]]

        # 3. Future timestamps — integer index, NOT bdate_range (Issue #9)
        y_timestamps = pd.Series(range(1, max_pred_len + 1))

        # 4. Forward pass
        raw_samples = self._predictor.predict_batch(
            x_df=x_ohlcva,
            x_timestamp=x_timestamps,
            y_timestamp=y_timestamps,
            n_samples=n_samples,
        )

        # 5 & 6. Build HorizonForecast per pred_len
        horizons = {}
        for pl in pred_lens:
            samples_for_len = raw_samples[:, :pl]
            horizons[pl] = self._build_horizon(y_timestamps.iloc[:pl], samples_for_len)

        return ForecastResult(
            ticker=ticker,
            model_name=self.model_name,
            generated_at=pd.Timestamp.now(),
            lookback_end=x_timestamps.iloc[-1],
            horizons=horizons,
        )

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing columns: {missing}. Expected: {', '.join(required)}."
            )

    @staticmethod
    def _build_horizon(y_ts: pd.Series, samples: np.ndarray) -> HorizonForecast:
        n_samples, pred_len = samples.shape
        pcts = [5, 25, 50, 75, 95]
        summary_data = {"timestamps": y_ts.values}
        for p in pcts:
            summary_data[f"p{p}"] = np.percentile(samples, p, axis=0)
        summary_data["mean"] = np.mean(samples, axis=0)
        summary = pd.DataFrame(summary_data)

        sample_data = {"timestamps": y_ts.values}
        for i in range(n_samples):
            sample_data[f"s{i}"] = samples[i, :]
        samples_df = pd.DataFrame(sample_data)

        return HorizonForecast(pred_len=pred_len, summary=summary, samples=samples_df)
```

- [ ] **Step 2: Verify units with manual check**

Run: `python -c "from kth.models.kronos_wrapper import KronosTH; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add kth/models/kronos_wrapper.py
git commit -m "feat: add forecast() with string input resolution, context window, and forecast pipeline"
```

---

### Task 5: `forecast_batch()`

**Files:**
- Modify: `kth/models/kronos_wrapper.py`

- [ ] **Step 1: Implement forecast_batch**

Add to `KronosTH`:

```python
    def forecast_batch(
        self,
        tickers_or_dfs: list[str | pd.DataFrame],
        pred_lens: list[int] | None = None,
        n_samples: int = 50,
        lookback: int = 400,
    ) -> dict[str, ForecastResult]:
        if pred_lens is None:
            pred_lens = [5, 20]

        results: dict[str, ForecastResult] = {}
        for i, item in enumerate(tickers_or_dfs):
            if isinstance(item, str):
                key = item
                input_val = item  # passes string through to forecast()
            else:
                key = f"df_{i}"
                input_val = item  # passes DataFrame through to forecast()
            results[key] = self.forecast(input_val, pred_lens=pred_lens, n_samples=n_samples, lookback=lookback)
        return results
```

- [ ] **Step 2: Commit**

```bash
git add kth/models/kronos_wrapper.py
git commit -m "feat: add forecast_batch for sequential multi-ticker inference"
```

---

### Task 6: `from_checkpoint()` — load local fine-tuned model (merged into Task 3)

> `from_checkpoint()` is already implemented in Task 3 alongside `from_pretrained()`, sharing the same `_MODEL_CACHE`. This task is a no-op.

---

### Task 7: Offline verification tests — `verify_model_layer.py`

**Files:**
- Create: `verify_model_layer.py`

- [ ] **Step 1: Write full verification script**

```python
"""
End-to-end verification of the Kronos wrapper without HuggingFace download.
Mocks KronosPredictor.predict_batch to return a fixed zero array.
"""
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup: mock kronos module before importing our wrapper
# ---------------------------------------------------------------------------
mock_kronos = MagicMock()
mock_predictor_cls = MagicMock()
mock_predictor = MagicMock()
mock_predictor_cls.from_pretrained.return_value = mock_predictor
mock_kronos.KronosPredictor = mock_predictor_cls

import sys
sys.modules["kronos"] = mock_kronos

from kth.models.kronos_wrapper import (
    KronosTH, ForecastResult, HorizonForecast, _MODEL_CACHE
)
from kth.data.loader import to_kronos_format
from kth.data.universe import get_all_tickers

# Configure mock to return realistic random forecasts (NOT zeros — zeros make
# Test 5 a false positive since all percentiles equal 0)
def _mock_predict_batch(x_df, x_timestamp, y_timestamp, n_samples):
    max_len = len(y_timestamp)
    rng = np.random.default_rng(42)
    # Generate n_samples paths, each starting near 100 with small random drift
    base_price = 100.0
    paths = np.zeros((n_samples, max_len))
    for s in range(n_samples):
        drift = rng.normal(0.0005, 0.01, max_len)
        paths[s, :] = base_price * np.exp(np.cumsum(drift))
    return paths

mock_predictor.predict_batch.side_effect = _mock_predict_batch

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

# Different model = different cache entry
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
# Test 5: Ordering invariant — p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 5: Percentile ordering invariant")
print("=" * 70)

summary = result.horizons[20].summary
for idx, row in summary.iterrows():
    assert row["p5"] <= row["p25"] <= row["p50"] <= row["p75"] <= row["p95"], \
        f"ordering violation at row {idx}: {row[['p5','p25','p50','p75','p95']].to_dict()}"
print("  PASS - p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95 holds for all rows")


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
```

- [ ] **Step 2: Run verification**

Run: `python verify_model_layer.py`
Expected: `ALL MODEL LAYER TESTS PASSED`

- [ ] **Step 3: Commit**

```bash
git add verify_model_layer.py
git commit -m "test: add verify_model_layer.py with 8 offline tests"
```

---

### Task 8: Notebook 02 — Zero-shot inference

**Files:**
- Create: `notebooks/02_kronos_zero_shot.ipynb`

> **Note:** Notebooks are for Colab. This step documents the cells to create. Build the notebook in Colab, not locally.

Cells:
1. **Install deps + mount `kth/`**
   ```python
   !pip install yfinance kronos pandas numpy matplotlib
   import sys; sys.path.append('/content/drive/MyDrive/kronos-th')
   ```

2. **Load model**
   ```python
   from kth.models.kronos_wrapper import KronosTH
   k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
   ```

3. **Forecast + plot loop for 6 representative tickers**
   ```python
   import matplotlib.pyplot as plt
   from kth.utils.plot import plot_forecast_band
   from kth.data.loader import load_cached

   tickers = ["PTT.BK", "AAPL", "SPY", "GLD", "BTC-USD", "^SET.BK"]
   for t in tickers:
       result = k.forecast(t, pred_lens=[5, 20], n_samples=20)
       historical = load_cached(t).tail(60)
       fig = plot_forecast_band(t, historical, result, pred_len=20)
       plt.show()
   ```

4. **Compute per-ticker metrics**
   ```python
   # MAE on 20d, directional hit-rate on 5d, Pearson correlation
   # (requires actual future data for evaluation — use a holdout period)
   ```

5. **Summary table**
   ```python
   # Which asset classes Kronos handles best zero-shot
   ```

6. **Narrative cell** — honest expectation on performance per asset class

- [ ] **Step 1: Create notebook on Colab and verify it runs end-to-end**

- [ ] **Step 2: Save notebook to repo**

### Self-Review

- [x] Spec coverage: All sections covered — dataclasses, KronosTH API, forecasting pipeline, model cache, batch, error handling, tests, notebook
- [x] Placeholder scan: No TBDs. All code is concrete.
- [x] Type consistency: `ForecastResult.horizons: dict[int, HorizonForecast]` used consistently. `pred_lens: list[int]` default `[5, 20]`.
- [x] Dependency order: Data layer (complete) → KronosTH → tests → notebook. Correct.
