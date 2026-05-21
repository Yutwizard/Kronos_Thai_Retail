# Backtest Comparison — Fine-Tuned vs Zero-Shot Design (Item 1)

> Scope: Fix and run `scripts/compare_finetune.py` for us_equity (all 3 folds) vs zero-shot on 2022-2024 walk-forward backtest. Item 1 of the remaining work queue from `2026-05-18-per-market-finetuning.md`.

---

## 1. Problem

The existing `scripts/compare_finetune.py` calls `KronosTH.from_checkpoint()` which fails because our checkpoints store the Kronos model config in `model_config.json` (not `config.json`), and the tokenizer config in `config.json` (overwritten). Kronos's `from_pretrained()` expects Kronos params in `config.json` — crashes with wrong positional args (`n_layers`, `token_dropout_p`, `learn_te` missing).

The backtest comparison was specified in Task 8 of the fine-tuning plan but never executed.

## 2. Architecture

Follow the proven pattern from `scripts/eval_holdout.py` — bypass `KronosTH.from_checkpoint()` entirely and use a helper that reconstructs the predictor from the raw checkpoint files:

```
model_config.json + model.safetensors
        │
        ▼
    Kronos(**cfg).load_state_dict(safetensors)
        │                    │
        ▼                    ▼
  KronosPredictor(model, tokenizer)
        │
        ▼
  KronosTH._predictor = predictor  ← swap
        │
        ▼
  th.forecast() / precompute_forecasts()  ← works normally
```

## 3. Implementation

### 3.1 Add `build_th(ckpt_dir, device)` helper

```python
def build_th(ckpt_dir, device):
    ckpt = Path(ckpt_dir)
    with open(ckpt / "model_config.json") as f:
        cfg = json.load(f)
    model = Kronos(**cfg)
    sd = load_file(str(ckpt / "model.safetensors"), device=device)
    model.load_state_dict(sd, strict=True)
    model.eval().to(device)
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    tokenizer.eval().to(device)
    th = KronosTH(model_name=ckpt_dir, device=device)
    th._predictor = KronosPredictor(model=model, tokenizer=tokenizer, device=device)
    return th
```

### 3.2 Fix `main()` flow

- Remove `k_ft = KronosTH.from_checkpoint(checkpoint_path, device)` — broken
- Replace with `k_ft = build_th(checkpoint_path, device)`
- Accept `--folds all|0|1|2` argument (default: all)
- Zero-shot precompute once, cache to `data/forecast_cache/us_equity_zs/`
- FT precompute per fold, cache to `data/forecast_cache/us_equity_ft_fold{f}/`
- Delete FT cache between folds to prevent bleed

### 3.3 Output

Per-fold side-by-side table:
```
=== us_equity: Fine-Tuned vs Zero-Shot (Fold 0) ===
Metric               Zero-Shot  Fine-Tuned        Δ
--------------------------------------------------------
CAGR                +XX.XX%     +XX.XX%     +XX.XX%
Sharpe               X.XX        X.XX        X.XX
Sortino              X.XX        X.XX        X.XX
Max Drawdown        -XX.XX%    -XX.XX%     +XX.XX%
Calmar               X.XX        X.XX        X.XX
Hit Rate             XX.X%       XX.X%      +XX.X%

Statistical Significance (vs equal-weight benchmark):
  Zero-Shot:  t=X.XX p=0.XXX
  Fine-Tuned: t=X.XX p=0.XXX
```

Final summary table comparing all 3 folds vs zero-shot. Results saved to `data/backtest_results/us_equity_ft_fold{f}/` and `data/backtest_results/us_equity_zs/`.

## 4. Cache Management

| Cache | Path | Cleaned between models? |
|-------|------|------------------------|
| ZS forecasts | `data/forecast_cache/us_equity_zs/` | No (reused across all folds) |
| FT fold 0 forecasts | `data/forecast_cache/us_equity_ft_fold0/` | Yes |
| FT fold 1 forecasts | `data/forecast_cache/us_equity_ft_fold1/` | Yes |
| FT fold 2 forecasts | `data/forecast_cache/us_equity_ft_fold2/` | Yes |

## 5. Time Estimate

| Step | Time |
|------|------|
| Bug fix (build_th helper) | 15 min |
| Script refactor (--folds arg, cache paths) | 15 min |
| ZS precompute (17 tickers, 2022-2024) | ~1.5 hrs |
| FT precompute per fold (×3) | ~1.5 hrs each |
| Walkforward per model (×4) | ~10 min each |
| **Total** | **~6.5 hrs** |

## 6. Success Criteria

- Script runs without crashing for us_equity fold 0, 1, 2
- BacktestOutput is saved for all 4 configurations (ZS + 3 FT folds)
- Side-by-side metrics table printed for each fold
- Final fold comparison summary output
- No forecast cache contamination between models

## 7. Dependencies

- `kth/backtest/walkforward.py` — `precompute_forecasts()`, `run_walkforward()`, `BacktestConfig`
- `kth/models/_kronos_bridge.py` — `KronosTokenizer`, `Kronos`, `KronosPredictor`
- `kth/models/kronos_wrapper.py` — `KronosTH`
- `data/raw/*.parquet` — 17 US equity tickers cached
- `checkpoints/us_equity/fold{f}/best/model_config.json` + `model.safetensors`
- `safetensors` Python package

## 8. Decisions

- **Fix location:** `scripts/compare_finetune.py` (not `eval_holdout.py` or `kronos_wrapper.py`) — keeps change isolated
- **Pattern:** Mirrors `eval_holdout.py` `build_th()` — proven, zero risk
- **All 3 folds:** Run even though F2 is best — provides confidence that the pattern is consistent
- **Clean cache:** Between FT folds — prevents bugs from stale predictions

---

*Document version: 2026-05-21. Source: Item 1 of remaining work from `2026-05-18-per-market-finetuning.md`.*
