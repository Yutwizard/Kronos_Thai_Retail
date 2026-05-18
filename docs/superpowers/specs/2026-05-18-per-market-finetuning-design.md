# Per-Market Fine-Tuning Design

> Fine-tune Kronos-small models for each investable market accessible to Thai retail investors.
> Each model is trained independently on its own class's data with expanded ticker coverage.

---

## 1. Motivation

The existing backtest uses a single zero-shot Kronos-small model across all 51 tickers. A single model cannot specialise to the distinct price dynamics of each market — Thai SET stocks behave differently than crypto, which behaves differently than US mega-cap equities.

Training separate models per market allows each to learn its own distribution, improving forecast accuracy (hit-rate) and reducing out-of-distribution errors.

---

## 2. Universe Design

### 2.1 Asset Classes and Model Count

8 fine-tuned models, one per investable class:

| Model | Tickers | Source |
|-------|---------|--------|
| `kronos-thai-equity` | 50 | Expanded SET stocks (15→50) |
| `kronos-thai-index` | 2 | ^SET.BK + TDEX.BK (added) |
| `kronos-us-equity` | 17 | 10 existing + 7 added |
| `kronos-commodity` | 5 | GLD, GC=F, SLV, USO, BNO (TFEX proxies) |
| `kronos-crypto` | 20 | 5 existing + 15 added |
| `kronos-reit-infra` | 9 | Thai REITs + infrastructure |
| `kronos-fx-major` | 8 | Major FX pairs |
| `kronos-fx-thb` | 6 | THB crosses (TFEX futures) |

**Excluded from fine-tuning:** bond_proxy, etf_global.

### 2.2 Expanded Tickers

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
| **Total** | | **50** |

#### commodity (+1)

GLD, GC=F, SLV, USO, **BNO** (Brent crude — TFEX proxy).

> **Review note:** GLD and GC=F both track gold (~0.95 correlation). USO and BNO both track crude (~0.90 correlation). The model gets only 3 independent signals from 5 tickers. If overfitting appears, drop GC=F (redundant) and BNO (USO covers crude adequately).

#### us_equity (+7)

COST, WMT, NFLX, AMD, DIS, KO, PEP

#### crypto (5 → 20)

| Round | Ticker | Name |
|-------|--------|------|
| Existing (5) | BTC-USD, ETH-USD, SOL-USD, BNB-USD, XRP-USD | Blue chips |
| Round 1 (9) | ADA-USD, DOGE-USD, AVAX-USD, DOT-USD, LINK-USD, MATIC-USD, ATOM-USD, TRX-USD, APT-USD | Mid-large cap |
| Round 2 (6) | LTC-USD, SHIB-USD, ARB-USD, NEAR-USD, VET-USD, SEI-USD | Broad |

> **Review note:** 20 crypto tickers are dominated by BTC correlation (most alts have 0.7–0.9 r² with BTC). The model may not learn 20 independent signals. If early folds show val loss not improving, trim to 12 tickers (BTC, ETH, 3-4 L1s, 1 memecoin, 1 DeFi).

#### thai_index (+1)

^SET.BK, TDEX.BK

> **Review note:** TDEX.BK has only ~1 year of data (2025+). It contributes to fold 2 training only. At 2 tickers, this model risks overfitting. If val metrics are poor, keep thai_index as zero-shot only.

#### fx_major (8 major pairs)

EURUSD=X, GBPUSD=X, USDJPY=X, USDCAD=X, AUDUSD=X, NZDUSD=X, USDCHF=X, USDSGD=X

#### fx_thb (6 THB crosses — TFEX futures)

THB=X, EURTHB=X, JPYTHB=X, GBPTHB=X, AUDTHB=X, SGDTHB=X

> **Review note:** 6 THB crosses all share the THB leg — if THB weakens, all 6 move together. This gives the model ~1.5 independent signals from 6 tickers. Consider merging fx_major + fx_thb into a single 14-ticker FX model for more signal diversity, or keeping fx_thb zero-shot.

#### reit (+7, remove VNQ)

CPNREIT.BK, WHART.BK, IMPACT.BK, FTREIT.BK, AIMIRT.BK, TFFIF.BK, DIF.BK, 3BBIF.BK

---

## 3. Data Pipeline

### 3.1 Download Strategy

All tickers are downloaded via yfinance and cached as parquet in `./data/raw/`. Tickers that don't exist on yfinance or have insufficient history are logged and excluded.

**Total tickers: ~117** (50 Thai equity + 17 US equity + 20 crypto + 9 REIT + 5 commodity + 8 FX major + 6 FX THB + 2 Thai index).

### 3.2 Dataset Construction

Each model gets its own dataset built by `prepare_dataset()` with an explicit `tickers` parameter:

```
prepare_dataset(tickers=model.tickers, fold=fold, cache_dir="./data/raw")
```

- **Train:** sliding windows, stride=1, lookback=400, pred_len=20, log-return targets
- **Val:** non-overlapping windows, stride=pred_len
- **Test:** non-overlapping windows, stride=pred_len
- **3-fold walk-forward:** fold 0 (train → 2022-06), fold 1 (→ 2022-12), fold 2 (→ 2023-06)

Only tickers with `len(df) >= lookback + pred_len` for a given fold's date range are included.

**Empty val set handling:** If a model's val set has <1 window, `finetune_predictor` receives `val_data=None` and skips early stopping. This is expected for thai_index (2 tickers) and any class where tickers have short histories.

---

## 4. Training Architecture

### 4.1 Training Flow (per model)

```
for model, tickers in [
    ("thai_equity", 50 SET tickers),
    ("thai_index",  ["^SET.BK", "TDEX.BK"]),
    ("us_equity",   17 US tickers),
    ("commodity",   ["GLD","GC=F","SLV","USO","BNO"]),
    ("crypto",      20 crypto tickers),
    ("reit_infra",  8 Thai REIT + infra tickers),
    ("fx_major",    8 major FX pairs),
    ("fx_thb",      6 THB crosses),
]:
    for fold in [0, 1, 2]:
        dataset = prepare_dataset(tickers=tickers, fold=fold)
        tok_path = finetune_tokenizer(dataset, ...)
        pred_path = finetune_predictor(dataset, tok_path, ...)
        eval_results = evaluate_model(pred_path, dataset["test"])
    pick best fold (by test hit-rate) → save as model checkpoint
```

Total: 8 models × 3 folds = 24 training runs.

### 4.2 Tokenizer Caching

`finetune_tokenizer` loads `KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")` once per process. Store in a module-level variable so subsequent folds reuse it without HuggingFace lookups:

```python
_TOKENIZER_CACHE: dict = {}

def _get_base_tokenizer():
    if "base" not in _TOKENIZER_CACHE:
        from kronos import KronosTokenizer
        _TOKENIZER_CACHE["base"] = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    return _TOKENIZER_CACHE["base"]
```

### 4.3 Hyperparameters

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

### 4.4 Evaluation Harness

`kth/models/finetune.py` gains a new function:

```python
def evaluate_model(
    checkpoint_path: str,
    test_dataset: KronosDataset,
    model_name: str = "NeoQuasar/Kronos-small",
) -> dict:
    """
    Load a fine-tuned checkpoint, run inference on test_dataset,
    return metrics: hit_rate, mae, sharpe, per_ticker_hit_rates.
    Also runs the SAME test set through zero-shot for comparison.
    """
```

Returns a dict with both fine-tuned and zero-shot metrics side by side.

### 4.5 Hardware Budget

Per run on Colab T4:
- **Tokenizer fine-tune:** ~30 min
- **Predictor fine-tune:** ~2 hours per fold (5 epochs)
- **Total per model:** ~7 hours (3 folds)
- **Total all 8 models sequentially:** ~56 hours → not feasible in one T4 session

**Mitigation:** Run in parallel across multiple Colab sessions (one per model). Each session fits within the 8-hour T4 cap. Use Drive to share checkpoints.

---

## 5. Evaluation

### 5.1 Metrics per Model

For each fine-tuned model vs zero-shot baseline:
- **Directional hit-rate** — % of forecast sign matches actual sign
- **MAE** — mean absolute error of predicted log-return vs actual
- **Sharpe ratio** — of a simple signal-based strategy on the test set
- **Per-ticker hit-rate** — for confidence calibration in daily reports

### 5.2 Backtest Integration

After selecting the best checkpoint per model, the real test is a **walk-forward backtest**:

```
for each model:
    k_ft = KronosTH.from_checkpoint(f"./checkpoints/{model}/best")
    result_ft = run_walkforward(config, k_ft, model.tickers)
    result_zs = run_walkforward(config, k_zs, model.tickers)  # zero-shot baseline

    compare:
        - CAGR:  ft vs zs
        - Sharpe: ft vs zs
        - Max DD: ft vs zs
        - Hit rate improvement (pp)
```

This is the **same backtest engine** used in our Thai equity 2022–2024 run. The bar is: does fine-tuning beat zero-shot after frictions?

### 5.3 Holdout Validation

The 3-fold walk-forward covers 2022–2024. After picking the best fold, the chosen checkpoint must be validated against a **true holdout period**: 2025-01 to present. This data has not been used in ANY training fold, fold selection, or hyperparameter tuning.

If the fine-tuned model performs worse than zero-shot on holdout data, the fine-tune is overfit and should not be deployed. The model must improve on holdout to be accepted.

### 5.4 Success Criteria

| Criterion | Target |
|-----------|--------|
| Fine-tuned hit-rate > zero-shot (test set, each fold) | ≥2pp improvement (or ≥3 of 5 metrics improve) |
| Consistent across 3 folds | Hit-rate improves in ≥2 of 3 folds |
| Diverse ticker improvement | ≥50% of tickers in class show non-negative change |
| Holdout validation | Fine-tuned beats zero-shot on 2025 holdout (hit-rate or Sharpe) |

---

## 6. Checkpoint Storage

```
checkpoints/
  ├── thai_equity/
  │   ├── fold0/
  │   ├── fold1/
  │   └── fold2/          # best → promoted to final/
  ├── thai_index/
  ├── us_equity/
  ├── commodity/
  ├── crypto/
  ├── reit_infra/
  ├── fx_major/
  └── fx_thb/
```

Each checkpoint is a full HuggingFace-compatible directory (`config.json`, `pytorch_model.bin`, `tokenizer.json`, `training_args.json`). Loadable via:

```python
k = KronosTH.from_checkpoint("./checkpoints/crypto/fold2")
```

---

## 7. Implementation Order

1. **Update `kth/data/universe.py`** — add 35 new Thai stocks, 7 US stocks, 15 crypto, 1 index, 1 commodity, 14 FX, 7 REIT. Remove bond_proxy and etf_global.
2. **Refactor `kth/models/finetune.py:prepare_dataset()`** — add `tickers: list[str] | None = None` parameter, skip `get_all_tickers()` when provided.
3. **Add `evaluate_model()`** to `finetune.py` — reusable eval against zero-shot baseline.
4. **Add tokenizer caching** — module-level singleton in `finetune_tokenizer`.
5. **Handle empty val sets** — if val dataset has 0 samples, pass `None` to predictor and skip early stopping.
6. **Update download script** — download expanded universe (~117 tickers).
7. **Create training notebook** — `notebooks/04_finetune_per_market.ipynb`.
8. **Run 8 Colab sessions** — one per model, ~7 hours each.
9. **Holdout evaluation** — compare best checkpoint vs zero-shot on 2025 data.
10. **Document results** — which models improved, which didn't, recommendations.

---

## 8. Open Questions

1. **T4 session limit:** 8 models × ~7 hours each = ~56 hours. Run sequentially (one Colab account, manual restart) or parallel (multiple accounts)? Parallel is 1 session per model = 1 day total.

2. **fx_thb (6 tickers):** All share the THB leg — ~1.5 independent signals. Merge into fx_major as one 14-ticker FX model for better signal diversity, or keep separate?

3. **thai_index (2 tickers):** TDEX.BK has only ~2025+ data. If hit-rate doesn't beat zero-shot, keep as zero-shot and skip fine-tuning for this class.

4. **Crypto 20 → 12 trim?** If early folds show no val loss improvement, trim to BTC, ETH, SOL, ADA, AVAX, LINK, DOGE, DOT, LTC, NEAR, VET, MATIC. Keep the cut list documented.

5. **commodity duplication:** GLD/GC=F and USO/BNO are near-identical pairs. If overfitting, drop GC=F and BNO.

---

*Document version: 2026-05-18. Source: `docs/superpowers/specs/2026-05-18-per-market-finetuning-design.md`*
