# Backtest Comparison — Fine-Tuned vs Zero-Shot Design (Item 1)

> Scope: Fix and run `scripts/compare_finetune.py` for us_equity (all 3 folds) vs zero-shot on 2022-2024 walk-forward backtest. Item 1 of the remaining work queue from `2026-05-18-per-market-finetuning.md`.

---

## 1. Problem

The existing `scripts/compare_finetune.py` calls `KronosTH.from_checkpoint()` which fails because our checkpoints store the Kronos model config in `model_config.json` (not `config.json`), and the tokenizer config in `config.json` (overwritten). Kronos's `from_pretrained()` expects Kronos params in `config.json` — crashes with wrong positional args (`n_layers`, `token_dropout_p`, `learn_te` missing).

The backtest comparison was specified in Task 8 of the fine-tuning plan but never executed.

**Additional bugs found in review:**

| # | Issue | Severity |
|---|-------|----------|
| 1 | `build_th()` duplicated in `eval_holdout.py` and `compare_finetune.py` — will diverge | High |
| 2 | Ratio metrics (Sharpe, Sortino, Calmar) formatted as `%` — displays 0.5 as 50.00% | Medium |
| 3 | Precompute time estimate off by 6× — 35 min/ticker, not 5 min | Medium |
| 4 | No per-ticker error handling in precompute loop — single failure kills all | Low |
| 5 | ZS baseline HF commit hash not frozen — comparison may drift over time | Low |

---

## 2. Architecture

### 2.1 Extract `build_th()` to shared location

Move the checkpoint reconstruction logic from `scripts/eval_holdout.py` into `kth/models/finetune.py` as a public function. Both scripts import it from one place. If checkpoint format changes, fix once.

```python
# kth/models/finetune.py

def load_finetuned_checkpoint(checkpoint_dir: str, device: str = "auto") -> "KronosTH":
    """
    Reconstruct a KronosTH from fine-tuned checkpoint (model_config.json + model.safetensors).
    Returns KronosTH with _predictor set to the fine-tuned KronosPredictor.
    """
    ...
```

### 2.2 Data flow

```
checkpoints/us_equity/fold{f}/best/
    model_config.json  ──→  Kronos(**cfg)
    model.safetensors  ──→  .load_state_dict()
        │                          │
        ▼                          ▼
  KronosPredictor(model, KronosTokenizer.from_pretrained(base))
        │
        ▼
  KronosTH._predictor = predictor
        │
        ▼
  precompute_forecasts(th, tickers, ...)  ──→  data/forecast_cache/us_equity_{zs,ft_fold{f}}/
        │
        ▼
  run_walkforward(config, th, tickers)  ──→  data/backtest_results/us_equity_{zs,ft_fold{f}}/
```

---

## 3. Implementation

### 3.1 Extract `load_finetuned_checkpoint()` (Review fix #1)

Add to `kth/models/finetune.py`:

```python
def load_finetuned_checkpoint(checkpoint_dir: str, device: str = "auto") -> "KronosTH":
    from pathlib import Path
    from safetensors.torch import load_file
    from kth.models._kronos_bridge import KronosTokenizer, Kronos, KronosPredictor
    from kth.models.kronos_wrapper import KronosTH

    if device == "auto":
        device = "cuda" if __import__("torch").cuda.is_available() else "cpu"

    ckpt = Path(checkpoint_dir)
    with open(ckpt / "model_config.json") as f:
        cfg = json.load(f)
    model = Kronos(**cfg)
    sd = load_file(str(ckpt / "model.safetensors"), device=device)
    model.load_state_dict(sd, strict=True)
    model.eval().to(device)

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    tokenizer.eval().to(device)

    th = KronosTH(model_name=checkpoint_dir, device=device)
    th._predictor = KronosPredictor(model=model, tokenizer=tokenizer, device=device)
    return th
```

Update `scripts/eval_holdout.py` to import from `kth.models.finetune` instead of defining its own `build_th()`.

### 3.2 Fix `main()` flow

- Remove `k_ft = KronosTH.from_checkpoint(checkpoint_path, device)` — broken
- Replace with `k_ft = load_finetuned_checkpoint(checkpoint_path, device)`
- Accept `--folds all|0|1|2` argument (default: all)
- Zero-shot precompute once, cache to `data/forecast_cache/us_equity_zs/`
- FT precompute per fold, cache to `data/forecast_cache/us_equity_ft_fold{f}/`
- Delete FT cache between folds to prevent bleed
- Freeze ZS model: verify and log `commit_hash.txt` from `checkpoints/NeoQuasar_Kronos-small/commit_hash.txt` (Review fix #5)

### 3.3 Output format (Review fixes #2, #3)

**Per-fold table — ratio metrics formatted correctly:**

```
=== us_equity: Fine-Tuned vs Zero-Shot (Fold 0) ===
  Tickers: 17 | Window: 2022-2024 | Eval samples: XXX

  Gross (before frictions):
  Metric               Zero-Shot  Fine-Tuned        Δ
  --------------------------------------------------------
  CAGR                   +X.XX%     +X.XX%     +X.XX%
  Sharpe                  X.XX        X.XX      +X.XX
  Sortino                 X.XX        X.XX      +X.XX
  Max Drawdown           -X.XX%     -X.XX%     +X.XX%
  Calmar                  X.XX        X.XX      +X.XX
  Hit Rate               XX.X%       XX.X%     +XX.X%

  Net of frictions (US equity: 0.35% one-way, 0.70% round-trip):
  Metric               Zero-Shot  Fine-Tuned        Δ
  --------------------------------------------------------
  CAGR                   +X.XX%     +X.XX%     +X.XX%
  Sharpe                  X.XX        X.XX      +X.XX
  Sortino                 X.XX        X.XX      +X.XX
  Max Drawdown           -X.XX%     -X.XX%     +X.XX%
  Calmar                  X.XX        X.XX      +X.XX
  Hit Rate               XX.X%       XX.X%     +XX.X%

  Per-Ticker Hit Rate:
  Ticker           ZS Rate      FT Rate          Δ
  --------------------------------------------------------
  AAPL             XX.X%        XX.X%        +XX.X%
  MSFT             XX.X%        XX.X%        +XX.X%
  NVDA             XX.X%        XX.X%        +XX.X%
  ... (all 17 tickers)

  Statistical Significance (vs equal-weight benchmark):
    Zero-Shot:  t=X.XX p=0.XXX
    Fine-Tuned: t=X.XX p=0.XXX
```

**Final summary table:**

```
=== Final Comparison: All Folds ===
  ZS baseline commit: abc123def456

  Fold    ZS CAGR   FT CAGR   Δ CAGR   ZS Sharpe  FT Sharpe  Δ Sharpe   Verdict
  ---------------------------------------------------------------------------
  F0      +X.XX%    +X.XX%    +X.XX%   X.XX       X.XX       +X.XX      ?
  F1      +X.XX%    +X.XX%    +X.XX%   X.XX       X.XX       +X.XX      ?
  F2      +X.XX%    +X.XX%    +X.XX%   X.XX       X.XX       +X.XX      ?
```

Results saved to `data/backtest_results/us_equity_ft_fold{f}/` and `data/backtest_results/us_equity_zs/`.

### 3.4 Per-ticker error handling in precompute (Review fix #4)

Wrap the per-ticker precompute loop in try/except, log failures, continue to next ticker:

```python
failures = []
for ticker in tickers:
    try:
        precompute_forecasts(th, [ticker], ...)
    except Exception as e:
        failures.append((ticker, str(e)))
if failures:
    print(f"WARNING: {len(failures)}/{len(tickers)} tickers failed precompute:")
    for t, err in failures:
        print(f"  {t}: {err}")
```

---

## 4. Cache Management

| Cache | Path | Cleaned between folds? | Concurrent-safe? |
|-------|------|------------------------|-------------------|
| ZS forecasts | `data/forecast_cache/us_equity_zs/` | No (shared) | ⚠️ Not safe — single process only |
| FT fold 0 forecasts | `data/forecast_cache/us_equity_ft_fold0/` | Yes | ⚠️ Not safe — single process only |
| FT fold 1 forecasts | `data/forecast_cache/us_equity_ft_fold1/` | Yes | ⚠️ Not safe — single process only |
| FT fold 2 forecasts | `data/forecast_cache/us_equity_ft_fold2/` | Yes | ⚠️ Not safe — single process only |

> **Concurrency note:** Cache paths are not namespaced by PID/timestamp. The script is designed for single-process execution on GTX 1060 (single GPU). Do not run multiple instances concurrently.

---

## 5. Time Estimate (Review fix #3 — revised)

Kronos-small inference on GTX 1060 6GB via `predict_batch`:

| Metric | Value |
|--------|-------|
| Seconds per forecast (1 ticker, 1 date) | ~3s |
| Trading days per ticker (2022-2024) | ~750 |
| Forecast time per ticker | ~750 × 3s = ~37 min |
| Tickers | 17 |
| Forecast time per model | 17 × 37 min ≈ **10.5 hrs** |

| Step | Time |
|------|------|
| Extract `load_finetuned_checkpoint()` + update both scripts | 30 min |
| ZS precompute (17 tickers × 750 days) | ~10.5 hrs |
| FT precompute per fold (×3) | ~10.5 hrs each |
| Walkforward per model (×4) | ~15 min each |
| Delete forecast cache between FT folds | ~1 min each |
| **Total (1 fold)** | **~21.5 hrs** |
| **Total (3 folds)** | **~42.5 hrs** |

> **Practical note:** 42.5 hrs is too long for a single GTX 1060 session. Recommended strategy: run ZS precompute once (10.5 hrs), then run folds 0-2 sequentially across 2-3 sessions. Each fold ~11 hrs. The walkforward runs are negligible (~15 min each).

---

## 6. Success Criteria

- `load_finetuned_checkpoint()` in `kth/models/finetune.py` — importable and used by both scripts
- `eval_holdout.py` updated to import from `kth.models.finetune` (no code duplication)
- Script runs without crashing for us_equity fold 0, 1, 2
- Per-ticker failures logged but do not abort the run
- BacktestOutput saved for all 4 configurations (ZS + 3 FT folds)
- Gross AND net-of-friction metrics tables printed for each fold
- Per-ticker hit-rate table appended to each fold output
- Ratio metrics (Sharpe, Sortino, Calmar) formatted correctly (no % suffix)
- ZS baseline commit hash printed and logged
- Final fold comparison summary with `Δ CAGR` and `Δ Sharpe` columns
- No forecast cache contamination between folds
- ZS forecast cache reused across all folds (not recomputed)

---

## 7. Dependencies

- `kth/backtest/walkforward.py` — `precompute_forecasts()`, `run_walkforward()`, `BacktestConfig`
- `kth/models/_kronos_bridge.py` — `KronosTokenizer`, `Kronos`, `KronosPredictor`
- `kth/models/kronos_wrapper.py` — `KronosTH`
- `kth/models/finetune.py` — NEW: `load_finetuned_checkpoint()` (extracted from eval_holdout.py)
- `scripts/eval_holdout.py` — update import to use new shared function
- `data/raw/*.parquet` — 17 US equity tickers cached
- `checkpoints/us_equity/fold{f}/best/model_config.json` + `model.safetensors`
- `safetensors` Python package

---

## 8. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Extract `build_th()` to `kth/models/finetune.py` | DRY — two scripts, one checkpoint format |
| 2 | Gross + net-of-friction tables side-by-side | US equity has 0.70% round-trip — cost must be visible |
| 3 | Per-ticker hit-rate breakdown | Diagnostic — identifies which tickers drive model performance |
| 4 | Ratio metrics formatted without `%` | Sharpe=1.2, not 120.00% — correct formatting |
| 5 | Per-ticker try/except in precompute | Graceful degradation — one bad ticker doesn't kill the run |
| 6 | ZS commit hash frozen and logged | Reproducibility — comparison is meaningless if ZS changes |
| 7 | Single-process only (no PID in cache paths) | GTX 1060 can only run one model at a time anyway |
| 8 | ZS cache reused across all folds | ZS predictions are identical — no need to recompute |
| 9 | All 3 folds run | Even though F2 leads in hit-rate, backtest metrics may differ |

---

*Document version: 2026-05-21-v2. Source: Item 1 of remaining work from `2026-05-18-per-market-finetuning.md`. Reviewed: HF manager + SWE.*
