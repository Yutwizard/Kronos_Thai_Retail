# Per-Market Fine-Tuning Design

> Fine-tune Kronos-small models for markets with sufficient signal diversity and data depth.
> Scope: 3 models (thai_equity, us_equity, crypto). Remaining classes stay zero-shot.

---

## 1. Why Only 3 Models

The original spec proposed 8 models. After review:

| Model | Verdict | Reason |
|-------|---------|--------|
| **thai_equity** | ✅ Go | 50 tickers, 8 sectors, 3+ years each |
| **us_equity** | ✅ Go | 17 tickers, deep history, diverse |
| **crypto** | ⚠️ Experiment | 12 tickers (trimmed), 0.8+ correlation risk |
| thai_index | ❌ Zero-shot | 2 tickers — overfits |
| commodity | ❌ Zero-shot | 3 independent signals across 5 tickers |
| reit_infra | ❌ Zero-shot | Most tickers have <1 year data |
| fx_major | ❌ Zero-shot | 8 pairs, all correlated — no edge from fine-tune |
| fx_thb | ❌ Zero-shot | 6 tickers, 1 signal (THB direction) |

**Why skip small models:** Kronos-small has 24.7M parameters. A model trained on 2-6 correlated tickers will memorise noise. It will pass in-fold validation but fail on 2025 holdout. Zero-shot generalises better on thin data.

---

## 2. Universe Updates

### Added to Universe

#### thai_equity (15 → 50)

| Sector | Tickers | Count |
|--------|---------|-------|
| Energy | PTT.BK, PTTEP.BK, BGRIM.BK, GPSC.BK, TOP.BK, IRPC.BK, BANPU.BK, BCP.BK, RATCH.BK | 9 |
| Banking | KBANK.BK, SCB.BK, BBL.BK, KTB.BK, TISCO.BK, TCAP.BK, KKP.BK, MEGA.BK | 8 |
| Property/Constr. | CPN.BK, LH.BK, QH.BK, AP.BK, ORI.BK, SCC.BK, HMPRO.BK, SIRI.BK, PSH.BK | 9 |
| Commerce/Retail | CPALL.BK, CRC.BK, GLOBAL.BK, DOHOME.BK | 4 |
| Food/Beverage | MINT.BK, CPF.BK, OSP.BK, ICHI.BK, SAPPE.BK | 5 |
| Healthcare | BDMS.BK, BH.BK, BCH.BK, CHG.BK | 4 |
| Telecom/Tech | ADVANC.BK, TRUE.BK, JMART.BK, HANA.BK, DELTA.BK, GULF.BK | 6 |
| Tourism/Logistics | AOT.BK, CENTEL.BK, ERW.BK, BEM.BK, BTS.BK | 5 |

#### us_equity (10 → 17)

COST, WMT, NFLX, AMD, DIS, KO, PEP

#### crypto (5 → 12, trimmed from 20)

BTC-USD, ETH-USD, SOL-USD, ADA-USD, AVAX-USD, LINK-USD, DOGE-USD, DOT-USD, LTC-USD, NEAR-USD, VET-USD, MATIC-USD

**Removed from original 20:** BNB-USD, XRP-USD (exchange tokens — different risk), TRX-USD, APT-USD, SHIB-USD, ARB-USD, SEI-USD, ATOM-USD (correlated with BTC beta, no independent signal).

### Other Classes Stay As-Is

| Class | Tickers | Status |
|-------|---------|--------|
| thai_index | ^SET.BK | Zero-shot |
| commodity | GLD, GC=F, SLV, USO | Zero-shot |
| reit | VNQ, CPNREIT.BK | Zero-shot (revert to original 2) |
| fx_major | — | Zero-shot |
| fx_thb | THB=X | Zero-shot |
| bond_proxy | TLT, IEF, HYG | Zero-shot |
| etf_global | SPY, QQQ, VTI, VWO, VEA, IEMG, EWY, EWJ, FXI | Zero-shot |

**Total tickers added to universe:** 35 Thai + 7 US + 7 crypto = **49 new** (vs 80 in original spec).

---

## 3. Data Pipeline

### 3.1 Download

All 100+ tickers downloaded via yfinance, cached as parquet in `./data/raw/`.

### 3.2 Dataset Construction

`prepare_dataset()` updated to accept a `tickers` parameter and optionally a pre-loaded `dict[str, DataFrame]`:

```python
def prepare_dataset(
    tickers: list[str] | None = None,
    ticker_data: dict[str, pd.DataFrame] | None = None,
    ...
) -> dict[str, KronosDataset]:
```

- `tickers`: list of tickers to include (defaults to `get_all_tickers()`)
- `ticker_data`: pre-loaded data dicts. If None, loads via `load_cached()`.
  Callers can load once and pass slices to avoid redundant I/O across models.

**Fold dates** (same across all models):
- Fold 0: train → 2022-06, val 2022-07→12, test 2023-01→06
- Fold 1: train → 2022-12, val 2023-01→06, test 2023-07→12
- Fold 2: train → 2023-06, val 2023-07→12, test 2024-01→06

**Empty val handling:** if val set has <1 window, `finetune_predictor` receives `val_data=None` and skips early stopping.

---

## 4. Training Architecture

### 4.1 Training Flow

```
for model_name, tickers in [
    ("thai_equity", [50 SET tickers]),
    ("us_equity",   [17 US tickers]),
    ("crypto",      [12 crypto tickers]),
]:
    for fold in [0, 1, 2]:
        dataset = prepare_dataset(tickers=tickers, fold=fold)
        tok_path = finetune_tokenizer(dataset, ...)
        pred_path = finetune_predictor(dataset, tok_path, ...)
        eval_results = evaluate_model(pred_path, dataset["test"])
    pick best fold → save as model checkpoint
```

Total: 3 models × 3 folds = 9 training runs.

### 4.2 Hyperparameters

| Parameter | Tokenizer | Predictor |
|-----------|-----------|-----------|
| Epochs | 1 | 5 |
| Batch size | 32 | 8 |
| Grad accum | — | 4 |
| Learning rate | 1e-4 | 5e-5 |
| LR scheduler | — | cosine |
| FP16 | — | yes |
| Early stopping | — | patience 2 |
| Save every | — | 200 steps |

### 4.3 Tokenizer Caching

Module-level singleton to avoid redundant HuggingFace loading across folds and models:

```python
_TOKENIZER_CACHE: dict = {}

def _get_base_tokenizer():
    if "base" not in _TOKENIZER_CACHE:
        from kronos import KronosTokenizer
        _TOKENIZER_CACHE["base"] = KronosTokenizer.from_pretrained(
            "NeoQuasar/Kronos-Tokenizer-base"
        )
    return _TOKENIZER_CACHE["base"]
```

### 4.4 Hardware Budget

| Model | Train samples (fold 0) | Tokenizer | Predictor (per fold) | Total (3 folds) |
|-------|----------------------|-----------|---------------------|-----------------|
| thai_equity | ~500K | 30 min | ~2 hr | ~6.5 hr |
| us_equity | ~170K | 10 min | ~40 min | ~2 hr |
| crypto | ~130K | 10 min | ~30 min | ~1.5 hr |

All 3 models fit in a single 8-hour T4 session (sequential). Total: ~10 hours — run as 2 sessions, 2 models first, then the last.

### 4.5 Checkpoint Compatibility

`KronosTH.from_checkpoint()` must handle local directories without calling `_resolve_hf_checkpoint()` (which downloads from HuggingFace). Current code:

```python
@classmethod
def from_checkpoint(cls, checkpoint_path: str, **kwargs):
    instance = cls(model_name=checkpoint_path, **kwargs)
    instance._load_or_cache_model(key=checkpoint_path, is_checkpoint=True)
    return instance
```

`is_checkpoint=True` skips the HuggingFace commit-hash pinning in `_load_or_cache_model`. Verified path: loads both tokenizer and model from the same local directory.

---

## 5. Evaluation

### 5.1 evaluate_model()

```python
def evaluate_model(
    checkpoint_path: str,
    test_dataset: KronosDataset,
) -> dict:
    """Returns {hit_rate, mae, sharpe, per_ticker_hit_rates}
       for both fine-tuned and zero-shot on the same test set."""
```

Reports both absolute and relative improvement. Example output:
```
thai_equity fold 0:
  hit_rate:  zs=0.523  ft=0.541  +1.8pp (+3.4% relative)
  mae:       zs=0.034  ft=0.032  -5.9%
  sharpe:    zs=0.87   ft=1.02   +17.2%
  tickers improved: 33/50 (66%)
```

### 5.2 Backtest Integration

Best checkpoint per model goes through `run_walkforward()` against zero-shot:

```
k_ft = KronosTH.from_checkpoint(f"./checkpoints/{model}/best")
result_ft = run_walkforward(config, k_ft, model.tickers)
result_zs = run_walkforward(config, k_zs, model.tickers)
compare: CAGR, Sharpe, Max DD, hit-rate
```

### 5.3 Holdout Validation

Must beat zero-shot on 2025 data (unseen in any fold) to be deployed. If holdout performance is worse, fine-tuned checkpoint is rejected and the model stays zero-shot.

### 5.4 Success Criteria

| Criterion | Target |
|-----------|--------|
| Hit-rate improvement (test set) | ≥1.5pp |
| Consistent across folds | Improves in ≥2 of 3 |
| Ticker-level improvement | ≥50% of tickers non-negative |
| Holdout (2025) | Beats zero-shot on hit-rate or Sharpe |

---

## 6. Checkpoint Storage

```
checkpoints/
  ├── thai_equity/
  │   ├── fold0/
  │   ├── fold1/
  │   └── fold2/          # best → final/
  ├── us_equity/
  │   └── ...
  └── crypto/
      └── ...
```

---

## 7. Implementation Order

1. **Update `kth/data/universe.py`** — add 35 Thai stocks, 7 US stocks, 7 crypto. Keep all other classes unchanged.
2. **Refactor `prepare_dataset()`** — add `tickers` and `ticker_data` parameters.
3. **Add `evaluate_model()`** to `finetune.py`.
4. **Add tokenizer caching** to `finetune_tokenizer()`.
5. **Handle empty val sets** — `None` passthrough, no early stopping.
6. **Download expanded universe** — run `download_data.py` with new tickers.
7. **Run training** on Colab T4 (2 sessions, ~5 hours total).
8. **Holdout evaluation** on 2025 data.
9. **Document results** with per-model verdict (deploy or stay zero-shot).

---

## 8. Remaining Open Questions

1. **crypto trim from 20→12:** Agreed? Cut list: keep BTC, ETH, SOL, ADA, AVAX, LINK, DOGE, DOT, LTC, NEAR, VET, MATIC. Drop BNB, XRP, TRX, APT, SHIB, ARB, SEI, ATOM.
2. **reit revert:** Revert to original 2 tickers (VNQ, CPNREIT.BK) and skip infrastructure funds that have <1 year data?

---

*Document version: 2026-05-18. Source: `docs/superpowers/specs/2026-05-18-per-market-finetuning-design.md`*
