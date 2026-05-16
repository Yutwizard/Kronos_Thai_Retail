# Spec A — Kronos Inference Wrapper

**Date:** 2026-05-16
**Subsystem:** `kth/models/kronos_wrapper.py` + `notebooks/02_kronos_zero_shot.ipynb`
**Depends on:** `kth/data/loader.py`, `kth/data/universe.py` (both complete)
**Blocks:** Spec B (backtest), Spec C (fine-tune), Spec D (report)
**Status:** Approved

---

## Purpose

A thin, reusable wrapper around `KronosPredictor` that:
- Loads Kronos-small or Kronos-base (or any local fine-tuned checkpoint) once and caches it in memory
- Accepts a ticker string or a pre-loaded DataFrame
- Returns probabilistic forecasts at two horizons (5d and 20d) in a structured dataclass
- Is the single interface all downstream notebooks and library code call — no notebook should import `KronosPredictor` directly

---

## Data Structures

```python
@dataclass
class HorizonForecast:
    pred_len: int                        # 5 or 20
    summary: pd.DataFrame                # timestamps, p5, p25, p50, p75, p95, mean
    samples: pd.DataFrame                # timestamps, s0, s1, ..., s_{n_samples-1}

@dataclass
class ForecastResult:
    ticker: str
    model_name: str                      # includes HuggingFace commit hash, e.g. "NeoQuasar/Kronos-small@a3f1c2d"
    generated_at: pd.Timestamp
    lookback_end: pd.Timestamp           # last date of the context window used
    horizons: dict[int, HorizonForecast] # {5: HorizonForecast, 20: HorizonForecast}
```

### Accessors (convenience)
- `result.horizons[20].summary` → DataFrame for the daily report
- `result.horizons[20].samples` → raw paths for backtest calibration
- `result.horizons[5].summary` → short-term directional check

---

## Public API

```python
class KronosTH:

    def __init__(
        self,
        model_name: str = "NeoQuasar/Kronos-small",
        device: str = "auto",           # "auto" → cuda if available, else cpu
        cache_dir: str = "./data/raw",
    ) -> None: ...

    @classmethod
    def from_pretrained(cls, model_name: str, **kwargs) -> "KronosTH":
        """Load a Kronos checkpoint from HuggingFace Hub."""

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str, **kwargs) -> "KronosTH":
        """Load a locally fine-tuned checkpoint (output of kth/models/finetune.py / notebook 04).
        Expects the same directory structure that finetune.py writes: a HuggingFace-compatible
        checkpoint directory containing config.json + pytorch_model.bin (or safetensors)."""

    def forecast(
        self,
        ticker_or_df: str | pd.DataFrame,
        pred_lens: list[int] = [5, 20],
        n_samples: int = 50,
        lookback: int = 400,
    ) -> ForecastResult: ...

    def forecast_batch(
        self,
        tickers_or_dfs: list[str | pd.DataFrame],
        pred_lens: list[int] = [5, 20],
        n_samples: int = 50,
        lookback: int = 400,
    ) -> dict[str, ForecastResult]: ...
    # Dict keys: ticker string when input is str; "df_0", "df_1", ... when input is DataFrame.
```

### `n_samples` guidance (documented, not enforced)
| Use case | Recommended value |
|---|---|
| Exploration / iteration (notebooks 02–03) | 20 |
| Final decision report (notebook 05) | 50 |
| Backtest calibration (notebook 03) | 50 |

`forecast()` defaults to `n_samples=50` (decision-grade). Callers opt down to 20 for iteration speed. The cost difference is marginal (~1-2 extra seconds on T4 per ticker for 50 vs 20 samples).

### `forecast_batch` behaviour
Runs sequentially, one ticker per forward pass. No multi-GPU or thread-parallel batching — the single GPU is fully utilized per call and 51 tickers at n_samples=50 completes in ~5–8 min on a T4.

---

## Internal Data Flow

```
forecast(ticker_or_df, pred_lens=[5, 20], n_samples=50, lookback=400)

1. Input resolution
   ├─ str  → load_cached(ticker, self.cache_dir)  →  Kronos-format DataFrame
   │         ForecastResult.ticker = ticker string
   └─ DataFrame → validate required columns
                  ForecastResult.ticker = "<dataframe>" [timestamps, open, high, low,
                  close, volume, amount]; raise ValueError if missing

2. Context window
   └─ df.tail(lookback) → x_df (shape: lookback × 6), x_timestamps
      y_timestamps = pd.Series(range(1, max_pred_len + 1))  # integer index
      (NOT bdate_range — integer index avoids calendar confusion across asset classes)

3. KronosPredictor.predict_batch()
   └─ one forward pass → raw_samples: np.ndarray shape (n_samples, max_pred_len)
      representing predicted close prices

4. Slice per horizon
   └─ for pred_len in pred_lens: raw_samples[:, :pred_len]

5. Build HorizonForecast per pred_len
   ├─ samples DataFrame: columns [timestamps, s0..s_{n-1}]
   └─ summary DataFrame: timestamps + {p5, p25, p50, p75, p95, mean}
      computed via np.percentile across axis=0

6. Return ForecastResult(
       ticker, model_name, generated_at=pd.Timestamp.now(),
       lookback_end=x_timestamps.iloc[-1],
       horizons={pred_len: HorizonForecast(...) for pred_len in pred_lens}
   )
```

### Model caching
```python
_MODEL_CACHE: dict[str, KronosPredictor] = {}  # module-level singleton
```
`__init__` checks `_MODEL_CACHE[model_name]` before loading. First call per model: ~30s (HuggingFace download + GPU transfer). Subsequent calls with the same `model_name`: instant.

### Model weight pinning (Issue #5)
`from_pretrained()` downloads model weights once and saves them to `./checkpoints/{model_name_slug}/` on first call. Subsequent calls load from local disk — no network required. The HuggingFace commit hash is resolved at download time and stored in `./checkpoints/{model_name_slug}/commit_hash.txt`. `ForecastResult.model_name` is formatted as `"{model_name}@{commit_hash[:7]}"` so every result is reproducibly traceable to the exact weights used.

**HuggingFace cache vs local checkpoint:** `KronosPredictor` internally uses HF's download cache (`~/.cache/huggingface/`). `from_pretrained()` wraps this by: (1) calling `huggingface_hub.snapshot_download()` or `hf_hub_download()` to get the resolved commit hash, (2) copying the downloaded files to `./checkpoints/{model_name_slug}/`, and (3) loading `KronosPredictor` from the local copy via `KronosPredictor.from_pretrained("./checkpoints/{model_name_slug}")`. This avoids double-storing weights — the local `./checkpoints/` copy is the canonical source; the HF cache is a temporary staging area and can be cleared safely after first run. The `commit_hash.txt` file serves as the marker that the local copy is complete; if it is missing or empty, re-download is triggered.

**Caching:** Both `from_pretrained()` and `from_checkpoint()` share the same `_MODEL_CACHE` module-level dict. `from_checkpoint()` checks the cache before loading from disk. Two calls to `from_checkpoint("/same/path")` return instances sharing the same underlying predictor — same as `from_pretrained` behaviour.

### Calendar alignment (Issue #9)
`y_timestamps` is an integer index `[1, 2, ..., max_pred_len]`, NOT generated via `pd.bdate_range`. Kronos uses timestamps for positional encoding only, so the forecast quality is unaffected by calendar choice — but displaying US business day calendar dates for Thai equities or crypto misleads readers. The integer index is unambiguous: day 1 means "next trading day for this asset," day 20 means "20 trading days from now." All plotting code MUST label the x-axis as "trading days ahead" and never show specific calendar dates from the forecast horizon.

---

## Error Handling

Validate at system boundaries only. Internal logic trusts its own invariants.

| Condition | Behaviour |
|---|---|
| `ticker_or_df` is str, parquet not found | `FileNotFoundError`: "No cache for {ticker}. Run download_universe() first." |
| DataFrame missing Kronos columns | `ValueError`: "Missing columns: {missing}. Expected: timestamps, open, high, low, close, volume, amount." |
| `lookback` > available rows | `ValueError`: "lookback={lookback} exceeds available rows ({n}). Reduce lookback or extend data history." |
| HuggingFace download fails | Propagate as-is (network error is caller's problem) |
| CUDA OOM | Propagate as-is with hint in docstring: "Reduce n_samples or use device='cpu'." |

---

## Testing (`verify_model_layer.py`)

New file, same pattern as `verify_data_layer.py`. No HuggingFace download — mocks `KronosPredictor.predict_batch` to return random walk paths (NOT zeros) so percentile ordering can be tested.

Tests:
1. **Constructor + cache**: two `KronosTH("same-model")` instances share the same `_MODEL_CACHE` entry. Same for `from_checkpoint`.
2. **String input**: `forecast("AAPL")` loads from parquet, returns `ForecastResult`
3. **DataFrame input**: `forecast(df)` accepts a pre-loaded Kronos-format DataFrame
4. **Output shape**: `summary` has 7 columns, `samples` has `n_samples + 1` columns (timestamps + samples)
5. **Ordering invariant**: `p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95` row-wise in summary. Mock must return non-constant data (e.g. `np.random.randn`) to validate the percentile computation — all-zero mock makes this test a false positive.
6. **Both horizons**: `result.horizons` contains both 5 and 20 when `pred_lens=[5,20]`
7. **lookback_end**: equals the last timestamp in x_timestamps
8. **Batch**: `forecast_batch(["AAPL","PTT.BK"])` returns a dict with both tickers
9. **y_timestamps**: integer `[1..max_pred_len]`, not calendar dates

---

## Notebook 02 — Zero-shot inference

**Goal:** validate what Kronos-small says about each asset class with no fine-tuning.

Cells:
1. Install deps; mount `kth/` package
2. `k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")`
3. For 6 representative tickers (PTT.BK, AAPL, SPY, GLD, BTC-USD, ^SET.BK):
   - `result = k.forecast(ticker, pred_lens=[5, 20], n_samples=20)`
   - Plot: actual last 60d + forecast P5/P50/P95 band for 20d horizon
4. Compute per-ticker: MAE on 20d, directional hit-rate on 5d, Pearson correlation
5. Summary table: which asset classes Kronos handles best zero-shot
6. Narrative: honest expectation — US mega-caps likely best, Thai mid-caps likely weakest

---

## Files to Create

| File | Purpose |
|---|---|
| `kth/models/__init__.py` | Package marker |
| `kth/models/kronos_wrapper.py` | `KronosTH`, `ForecastResult`, `HorizonForecast` |
| `verify_model_layer.py` | Offline tests (mocked KronosPredictor) |
| `notebooks/02_kronos_zero_shot.ipynb` | Zero-shot inference + evaluation notebook |
