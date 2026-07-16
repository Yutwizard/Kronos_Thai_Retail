# Crypto Backtest Comparison — Fine-Tuned vs Zero-Shot Design (Item 5-crypto)

> Scope: Run walk-forward backtest comparison for crypto fold 0 (fine-tuned) vs zero-shot on 2022-2024 window. 12 tickers, GTX 1060 6GB, ~15.5 hrs total.
> Strategy: Fold 0 only (single fold, honest out-of-sample). If FT beats ZS, run folds 1-2 to confirm.

---

## 1. Problem

The crypto fine-tuning showed **0.0pp improvement** on 2025 holdout evaluation (ZS: 56.4%, FT F1: 56.4%). The holdout measures pure direction accuracy. The backtest measures trade-level P&L — including position sizing, volatility exposure, and friction costs. It's possible for a model to tie on hit-rate but outperform on Sharpe (by being right on high-volatility moves and wrong on noise).

**We don't know if crypto FT adds trading alpha until the backtest runs.**

The backtest comparison was specified in Task 8 of the fine-tuning plan but never executed for crypto.

---

## 2. Data: Crypto Universe

| # | Ticker | Rows | Data Range | Backtest 2022-2024 | Notes |
|---|--------|------|------------|---------------------|-------|
| 1 | BTC-USD | 3,652 | 2016-05-18 → 2026-05-18 | ✅ Full | |
| 2 | ETH-USD | 3,112 | 2017-11-09 → 2026-05-18 | ✅ Full | |
| 3 | SOL-USD | 2,229 | 2020-04-10 → 2026-05-18 | ✅ Full | |
| 4 | ADA-USD | 3,112 | 2017-11-09 → 2026-05-18 | ✅ Full | |
| 5 | AVAX-USD | 2,066 | 2020-07-13 → 2026-05-18 | ✅ Full | |
| 6 | LINK-USD | 3,112 | 2017-11-09 → 2026-05-18 | ✅ Full | |
| 7 | DOGE-USD | 3,112 | 2017-11-09 → 2026-05-18 | ✅ Full | |
| 8 | DOT-USD | 2,097 | 2020-08-20 → 2026-05-18 | ✅ Full | |
| 9 | LTC-USD | 3,652 | 2016-05-18 → 2026-05-18 | ✅ Full | |
| 10 | NEAR-USD | 2,042 | 2020-10-14 → 2026-05-18 | ✅ Full | |
| 11 | VET-USD | 2,845 | 2018-08-03 → 2026-05-18 | ✅ Full | |
| 12 | MATIC-USD | 2,158 | 2019-04-28 → **2025-03-24** | ✅ Full (2022-2024) | ⚠️ Ends 2025-03-24 — Polygon MATIC→POL migration. No POL-USD on Yahoo. Fine for 2022-2024 window. |

**Verdict:** All 12 tickers have full data for 2022-2024 backtest. MATIC-USD gap only affects post-2024 extensions.

---

## 3. Fold Structure (Fold 0)

| Split | Dates | Rows (crypto) | Status |
|-------|-------|---------------|--------|
| Train | Data start → 2022-06-30 | Varies by ticker | ✅ |
| Val | 2022-07-01 → 2024-03-30 | 639 calendar days | ✅ 132 samples |
| Test | 2024-03-31 → 2025-12-30 | — | N/A for backtest |

The backtest evaluates forecasts on **2022-01-01 to 2024-12-31**. Fold 0 trains through 2022-06-30 — so the backtest's first 6 months (2022 H1) use a lookback window that's in-sample (data ≤ 2022-06-30), while 2022 H2+ uses lookback windows that progressively cross the training boundary. By 2024, all lookback data is out-of-sample.

**Training regime characteristics (2022-06-30 cutoff):**
- BTC was down ~65% from its Nov 2021 peak — the model was trained in a bear market
- 2022-Q3/Q4 was the start of the recovery cycle
- This regime shift means the FT model's edge (if any) must survive a distribution change

---

## 4. Architecture

### 4.1 Shared infrastructure (built in us_equity spec)

`load_finetuned_checkpoint()` is extracted to `kth/models/finetune.py` (shared by `eval_holdout.py` and `compare_finetune.py`). See `2026-05-21-backtest-comparison-design.md` §3.1 for implementation.

### 4.2 `compare_finetune.py` — model-agnostic CLI

```
scripts/compare_finetune.py --model crypto --fold 0
```

Derives from `--model`:
- `MODEL_TICKERS["crypto"]` → 12 tickers
- `checkpoints/crypto/fold0/best/` → checkpoint path
- `data/forecast_cache/crypto_zs/` → ZS cache
- `data/forecast_cache/crypto_ft_fold0/` → FT cache
- `data/backtest_results/crypto_zs/` → ZS results
- `data/backtest_results/crypto_ft_fold0/` → FT results

### 4.3 Data flow

```
checkpoints/crypto/fold0/best/
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
  precompute_forecasts(th, 12 tickers, 2022-2024)  ──→  data/forecast_cache/crypto_{zs,ft_fold0}/
        │
        ▼
  run_walkforward(config, th, 12 tickers)  ──→  data/backtest_results/crypto_{zs,ft_fold0}/
```

---

## 5. Known Issue: Business Day Bias on Crypto Data

### 5.1 The bug

Two places use `pd.bdate_range(freq="B")` (Monday-Friday only):

```python
# walkforward.py line 79 — precompute loop
trading_days = pd.bdate_range(start=start_date, end=end_date, freq="B")

# kronos_wrapper.py line 152 — forecast future timestamps
y_timestamps = pd.Series(pd.bdate_range(start=..., periods=max_pred_len, freq="B"))
```

Crypto trades 7 days/week. The backtest **skips 28% of crypto price data** (every Saturday/Sunday).

### 5.2 Impact

| Component | Effect |
|-----------|--------|
| Precompute | Forecasts generated only for weekdays — 28% fewer predictions |
| Future horizon | 20-day prediction uses 20 business days = 28 calendar days. Actual crypto return is measured over 28 days, not 20 |
| Volatility | Realized volatility in backtest is **understated by ~20-30%** because weekend moves are compressed into Monday gaps |
| Sharpe | Systematically overstated (denominator is lower than true volatility) |

### 5.3 Why not fix now

- The bug affects ZS and FT **equally** — the delta (FT − ZS) is still valid
- Fixing requires: (a) `crypto_calendar_days()` helper, (b) modifying `KronosTH.forecast()` to accept a calendar frequency parameter, (c) changing `precompute_forecasts()` to use it, (d) retraining all models
- Impact on absolute metrics is significant but irrelevant for **comparison**
- Fix is tracked as a separate issue for post-comparison cleanup

### 5.4 Mitigation

- Log a warning banner in the comparison output: `"Crypto backtest uses business days (5d/week). Crypto trades 7d/week. Absolute Sharpe numbers are 20-30% overstated. Delta (FT vs ZS) is valid."`
- Output a "BTC only" Sharpe line — BTC has the cleanest 24/7 behavior and is least affected by gap compression

---

## 6. Output Format

### 6.1 Per-fold table

```
=== crypto: Fine-Tuned vs Zero-Shot (Fold 0) ===
  Tickers: 12 | Window: 2022-01-01 → 2024-12-31 | Backtest samples: XXX
  Training regime: BTC -65% from ATH at train cutoff (2022-06-30)
  ⚠️ Crypto backtest: 5d/week bias → Sharpe overstated ~20-30%. Delta valid.

  Gross (before frictions):
  Metric               Zero-Shot  Fine-Tuned        Δ
  --------------------------------------------------------
  CAGR                   +X.XX%     +X.XX%     +X.XX%
  Sharpe                  X.XX        X.XX      +X.XX
  Sortino                 X.XX        X.XX      +X.XX
  Max Drawdown           -X.XX%     -X.XX%     +X.XX%
  Calmar                  X.XX        X.XX      +X.XX
  Trade Hit Rate         XX.X%       XX.X%     +XX.X%

  BTC-only contribution:
  Metric               Zero-Shot  Fine-Tuned        Δ
  --------------------------------------------------------
  Sharpe                  X.XX        X.XX      +X.XX
  Trade Hit Rate         XX.X%       XX.X%     +XX.X%

  Net of frictions (crypto: 0.25% one-way, 0.45% round-trip):
  Metric               Zero-Shot  Fine-Tuned        Δ
  --------------------------------------------------------
  CAGR                   +X.XX%     +X.XX%     +X.XX%
  Sharpe                  X.XX        X.XX      +X.XX
  Sortino                 X.XX        X.XX      +X.XX
  Max Drawdown           -X.XX%     -X.XX%     +X.XX%
  Calmar                  X.XX        X.XX      +X.XX
  Trade Hit Rate         XX.X%       XX.X%     +XX.X%

  Per-Ticker Trade Hit Rate (gross_return > 0):
  Ticker           ZS Rate      FT Rate          Δ
  --------------------------------------------------------
  BTC-USD          XX.X%        XX.X%        +XX.X%
  ETH-USD          XX.X%        XX.X%        +XX.X%
  SOL-USD          XX.X%        XX.X%        +XX.X%
  ... (all 12 tickers)

  Verdict: [Deploy / Marginal / Pass]
```

### 6.2 BTC-only Sharpe

Crypto is a 1.5-factor bet — BTC drives 80%+ of alt-coin movement. A model that predicts BTC well but degrades on alts will show a portfolio Sharpe near BTC's individual Sharpe. The "BTC-only" line isolates: did the model capture the dominant factor, or does alt-coin noise hurt it?

Computed by filtering `BacktestResult.trades` to `ticker == 'BTC-USD'` and recalculating Sharpe on BTC-only returns.

### 6.3 Verdict rules (same as us_equity)

```
Deploy   = FT Sharpe ≥ ZS Sharpe + 0.05 AND FT CAGR ≥ ZS CAGR
Marginal = FT Sharpe > ZS Sharpe but CAGR not better
Pass     = FT Sharpe ≤ ZS Sharpe (zero-shot wins)
PARTIAL  = <10 tickers available (<80% of 12-ticker universe)
```

---

## 7. Cache Management

| Cache | Path | Cleaned between folds? |
|-------|------|------------------------|
| ZS forecasts | `data/forecast_cache/crypto_zs/` | No (shared) |
| FT fold 0 forecasts | `data/forecast_cache/crypto_ft_fold0/` | N/A (single fold) |

Single-process only — GTX 1060 can't run concurrent forecasts.

---

## 8. Time Estimate

Kronos-small on GTX 1060 6GB, batch inference via `predict_batch`:

| Step | Time |
|------|------|
| ZS precompute (12 tickers × ~750 days × 3s) | **~7.5 hrs** |
| FT fold 0 precompute | **~7.5 hrs** |
| Walkforward ZS | ~10 min |
| Walkforward FT | ~10 min |
| Per-ticker + BTC-only computation | ~1 min |
| **Total** | **~15.5 hrs** |

**Schedule (GTX 1060):**
| Session | What | Duration |
|---------|------|----------|
| Night 1 | ZS precompute | 7.5 hrs |
| Night 2 | FT fold 0 precompute | 7.5 hrs |
| Daytime | Walkforward + output | 20 min |

---

## 9. Implementation

### 9.1 Generalize `compare_finetune.py` CLI

Replace hardcoded `MODEL_TICKERS` + `checkpoint_path` with:

```
scripts/compare_finetune.py --model crypto --fold 0
scripts/compare_finetune.py --model us_equity --fold 2
scripts/compare_finetune.py --model thai_equity --fold 0
```

### 9.2 Extract `load_finetuned_checkpoint()` to `kth/models/finetune.py`

Same function as defined in us_equity spec §3.1. Update `eval_holdout.py` to import it.

### 9.3 Add crypto-specific output sections

- Training regime log (BTC drawdown at train cutoff)
- Business-day bias warning banner
- BTC-only Sharpe computation from trades dataframe
- Per-ticker trade hit rate from trades dataframe

### 9.4 Error handling

- Per-ticker try/except in precompute loop (same as us_equity)
- Minimum 10 tickers for valid comparison (≥80% of 12)
- Handle missing `commit_hash.txt`: `"unknown (pre-hash era)"`
- VRAM cleanup: `del k_ft; torch.cuda.empty_cache()` after walkforward

---

## 10. Success Criteria

- `compare_finetune.py` accepts `--model crypto --fold 0` without hardcoded paths
- `load_finetuned_checkpoint()` importable from `kth.models.finetune.py`
- BacktestOutput saved for ZS and FT (2 configs)
- Gross + net-of-friction tables printed
- BTC-only Sharpe line computed and displayed
- 5-day bias warning displayed
- Training regime characteristics logged
- Verdict rule applied (Deploy/Marginal/Pass)
- ZS forecast cache created once; FT cache created for fold 0
- Per-ticker failures logged but do not abort

---

## 11. Dependencies

- `kth/models/finetune.py` — NEW: `load_finetuned_checkpoint()`
- `kth/models/kronos_wrapper.py` — `KronosTH`
- `kth/backtest/walkforward.py` — `precompute_forecasts()`, `run_walkforward()`, `BacktestConfig`
- `scripts/eval_holdout.py` — update import to use shared function
- `data/raw/*.parquet` — 12 crypto tickers cached
- `checkpoints/crypto/fold0/best/model_config.json` + `model.safetensors`
- `safetensors` Python package

---

## 12. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Fold 0 only | Honest out-of-sample test. Fold 1 is in-sample (trained through 2024-03, tested on 2022). Prior from holdout is neutral (0.0pp) — fold 0 suffices for verdict |
| 2 | `--model` + `--fold` CLI args | One script for all 3 asset classes — DRY |
| 3 | BTC-only Sharpe line | Crypto is a BTC factor bet. Isolate the signal from the noise |
| 4 | Business-day bias: warn, don't fix | Affects ZS and FT equally. Delta is valid. Fix is a separate project |
| 5 | Training regime logged in output | Prevents misattributing regime-shift underperformance to model failure |
| 6 | MATIC-USD: keep in 12-ticker set | 2022-2024 data is complete. Gap only affects 2025+ |
| 7 | Minimum 10 tickers for valid verdict | 80% of 12-ticker universe |
| 8 | Gross + net tables, verdict rules | Same framework as us_equity for consistency |

---

*Document version: 2026-05-21. Source: Item 5-crypto of remaining work from `2026-05-18-per-market-finetuning.md`. Reviewed: HF manager + SWE.*

---

## Appendix A: MATIC-USD Data Gap

```
MATIC-USD: 2158 rows, 2019-04-28 → 2025-03-24
BTC-USD:   3652 rows, 2016-05-18 → 2026-05-18 (all other 11 tickers go to 2026)

Verdict: Polygon (MATIC) migrated to POL token. No POL-USD ticker exists on Yahoo Finance.
MATIC-USD has sufficient data for 2022-2024 backtest (2,158 rows fully covers the window).
For future 2025+ backtests, MATIC-USD will silently stop providing data after 2025-03-24.
Consider replacing with a different L1/L2 alt-coin if 2025 coverage is needed later.
```
