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

**Excluded from fine-tuning:** bond_proxy (not practical for Thai retail), etf_global (dropped).

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

| Ticker | Name | Why |
|--------|------|-----|
| GLD | ✅ already in | Gold ETF |
| GC=F | ✅ already in | Gold futures (TFEX proxy) |
| SLV | ✅ already in | Silver ETF |
| USO | ✅ already in | WTI crude oil |
| **BNO** | United States Brent Oil | Brent crude (TFEX proxy) |

#### us_equity (+7)

| Ticker | Name |
|--------|------|
| COST | Costco |
| WMT | Walmart |
| NFLX | Netflix |
| AMD | AMD |
| DIS | Disney |
| KO | Coca-Cola |
| PEP | PepsiCo |

#### crypto (5 → 20)

| Round | Ticker | Name |
|-------|--------|------|
| Existing (5) | BTC-USD | Bitcoin |
| | ETH-USD | Ethereum |
| | SOL-USD | Solana |
| | BNB-USD | Binance Coin |
| | XRP-USD | Ripple |
| Round 1 (9) | ADA-USD | Cardano |
| | DOGE-USD | Dogecoin |
| | AVAX-USD | Avalanche |
| | DOT-USD | Polkadot |
| | LINK-USD | Chainlink |
| | MATIC-USD | Polygon |
| | ATOM-USD | Cosmos |
| | TRX-USD | TRON |
| | APT-USD | Aptos |
| Round 2 (6) | LTC-USD | Litecoin |
| | SHIB-USD | Shiba Inu |
| | ARB-USD | Arbitrum |
| | NEAR-USD | NEAR Protocol |
| | VET-USD | VeChain |
| | SEI-USD | Sei |

#### thai_index (+1)

| Ticker | Name |
|--------|------|
| TDEX.BK | One Asset SET50 ETF |

#### fx_major (8 major pairs)

EURUSD=X, GBPUSD=X, USDJPY=X, USDCAD=X, AUDUSD=X, NZDUSD=X, USDCHF=X, USDSGD=X

#### fx_thb (6 THB crosses — TFEX futures)

| Ticker | Name |
|--------|------|
| THB=X | USD/THB |
| EURTHB=X | Euro / THB |
| JPYTHB=X | Japanese Yen / THB |
| GBPTHB=X | British Pound / THB |
| AUDTHB=X | Australian Dollar / THB |
| SGDTHB=X | Singapore Dollar / THB |

#### reit (+7, remove VNQ)

| Ticker | Name | Type |
|--------|------|------|
| CPNREIT.BK | Central Pattana REIT | Retail |
| WHART.BK | WHA Premium Industrial REIT | Industrial |
| IMPACT.BK | Impact Growth REIT | Convention centre |
| FTREIT.BK | Frasers Property REIT | Office/industrial |
| AIMIRT.BK | AIM Industrial Growth REIT | Industrial |
| TFFIF.BK | Thai Future Fund | Government infrastructure |
| DIF.BK | Digital Infrastructure Fund | Telecom towers |
| 3BBIF.BK | 3BB Internet Infrastructure Fund | Broadband |

---

## 3. Data Pipeline

### 3.1 Download Strategy

All tickers are downloaded via yfinance and cached as parquet in `./data/raw/`. Tickers that don't exist on yfinance or have insufficient history are logged and excluded.

Expansion adds 17 new tickers (7 US + 9 crypto + 1 index). Total download: ~68 tickers across all classes.

### 3.2 Dataset Construction

Each model gets its own dataset built by `prepare_dataset()`:

- **Train:** sliding windows, stride=1, lookback=400, pred_len=20, log-return targets
- **Val:** non-overlapping windows, stride=pred_len
- **Test:** non-overlapping windows, stride=pred_len
- **3-fold walk-forward:** fold 0 (train → 2022-06), fold 1 (→ 2022-12), fold 2 (→ 2023-06)

Only tickers with sufficient data for a given fold are included in that fold's training set.

---

## 4. Training Architecture

### 4.1 Training Flow (per model)

```
for each model in [thai_equity, thai_index, us_equity, commodity, crypto, reit, fx_macro]:
    for fold in [0, 1, 2]:
        dataset = prepare_dataset(tickers=model.tickers, fold=fold)
        tok_path = finetune_tokenizer(dataset, ...)
        pred_path = finetune_predictor(dataset, tok_path, ...)
        evaluate(pred_path, dataset["test"])
    pick best fold checkpoint → save as model checkpoint
```

Total: 7 models × 3 folds = 21 training runs.

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

### 4.3 Hardware Budget

Per run on Colab T4:
- **Tokenizer fine-tune:** ~30 min (varies by dataset size)
- **Predictor fine-tune:** ~2 hours per fold (5 epochs)
- **Total per model:** ~7 hours (3 folds)
- **Total all 7 models sequentially:** ~49 hours → not feasible in T4 session

**Mitigation:** Run models in parallel across multiple Colab sessions (one session per model). Each session fits within the 8-hour T4 cap.

---

## 5. Evaluation

### 5.1 Metrics per Model

For each fine-tuned model vs zero-shot baseline on the same test set:
- Directional hit-rate (% of forecast sign matches actual sign)
- MAE of predicted close vs actual close
- Sharpe ratio of a simple strategy using the model's signals
- Per-ticker hit-rate for confidence calibration

### 5.2 Success Criteria

| Criterion | Target |
|-----------|--------|
| Fine-tuned hit-rate > zero-shot | ≥5pp improvement on test set |
| Consistent across 3 folds | Hit-rate improves in ≥2 of 3 folds |
| Diverse ticker improvement | ≥60% of tickers in class show improvement |

---

## 6. Checkpoint Storage

```
checkpoints/
  ├── thai_equity/
  │   ├── fold0/
  │   ├── fold1/
  │   └── fold2/          # best → final
  ├── thai_index/
  ├── us_equity/
  ├── commodity/
  ├── crypto/
  ├── reit_infra/
  └── fx_macro/
```

Each checkpoint is a full HuggingFace-compatible directory (`config.json`, `pytorch_model.bin`, `tokenizer.json`, `training_args.json`). Loadable via:

```python
k = KronosTH.from_checkpoint("./checkpoints/crypto/fold2")
```

---

## 7. Implementation Order

1. Update `kth/data/universe.py` — add new tickers to each class, remove bond_proxy and etf_global
2. Create `kth/models/finetune.py:prepare_dataset()` — add `tickers` parameter (currently hardcoded to full universe)
3. Create per-market training notebook: `notebooks/04_finetune_per_market.ipynb`
4. Run training on Colab (7 models × 3 folds)
5. Evaluate and select best checkpoints
6. Document results

---

## 8. Open Questions

1. **T4 session limit:** 8 models × ~7 hours each = ~56 hours total. Run sequentially (auto-resume across sessions) or in parallel (multiple Colab accounts)?
2. **fx_macro (2 tickers):** Too small to fine-tune effectively. Keep as zero-shot only?
3. **thai_index (2 tickers):** TDEX.BK has only ~1 year history — will only contribute to fold 2 training. Acceptable?

---

*Document version: 2026-05-18. Source: `docs/superpowers/specs/2026-05-18-per-market-finetuning-design.md`*
