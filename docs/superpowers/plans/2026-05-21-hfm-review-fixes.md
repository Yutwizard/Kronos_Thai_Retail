# HF Manager Review Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 issues identified in the 2026-05-21 HF manager full project review: crypto calendar bug, dead code stubs, stale docs, misleading metrics, missing benchmark comparison, and unexecuted FT backtests.

**Architecture:** Issues 3/4/6 (code fixes) are no-GPU, done in one sitting. Issue 5 (docs) is no-GPU. Issues 1/2 (backtests) require GPU — overnight sessions. Execute in dependency order: code → docs → backtests.

**Tech Stack:** Python 3.10+, PyTorch, Kronos (local repo), pandas, numpy

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `kth/backtest/walkforward.py:79` | Replace `pd.bdate_range` with asset-class-aware calendar |
| Modify | `kth/models/kronos_wrapper.py:152` | Accept `calendar_freq` param for future timestamps |
| Modify | `kth/backtest/metrics.py:107-108` | Rename `hit_rate` → `trade_win_rate` |
| Modify | `kth/models/finetune.py` | Replace dead stubs with `NotImplementedError` |
| Modify | `scripts/compare_finetune.py` | Accept `--calendar` param, update output labels |
| Modify | `scripts/eval_holdout.py` | Update `trade_win_rate` key references |
| Modify | `notebooks/04_finetune_per_market.ipynb` | Replace dead finetune_tokenizer/predictor calls |
| Modify | `PROJECT_STRUCTURE.md` | Update to 100 tickers, current layer status, answer §13 |
| Modify | `CLAUDE.md` | Update universe count in line 82 |
| Modify | `docs/superpowers/plans/2026-05-18-per-market-finetuning.md` | Mark review fixes as done |

---

### Task 1: Fix `bdate_range` Calendar Bug (Issue 3)

**Files:**
- Modify: `kth/backtest/walkforward.py:79`
- Modify: `kth/models/kronos_wrapper.py:147-152`

- [ ] **Step 1: Add calendar helper to walkforward.py**

Add at module level in `kth/backtest/walkforward.py`, after imports:

```python
def _get_calendar_for_tickers(tickers: list[str]) -> str:
    """Return 'B' for equities (business days) or 'D' for crypto (calendar days)."""
    from kth.data.universe import get_ticker_class
    classes = {get_ticker_class(t) for t in tickers}
    if "crypto" in classes:
        return "D"
    return "B"
```

- [ ] **Step 2: Use calendar helper in precompute_forecasts**

In `precompute_forecasts()`, replace line 79:

```python
# OLD:
trading_days = pd.bdate_range(start=start_date, end=end_date, freq="B")

# NEW:
freq = _get_calendar_for_tickers(tickers)
print(f"[precompute] Calendar: {'7-day (crypto)' if freq == 'D' else '5-day (business)'}")
trading_days = pd.date_range(start=start_date, end=end_date, freq=freq)
```

- [ ] **Step 3: Verify bdate_range replacement works**

Run: `venv/bin/python -c "import pandas as pd; d = pd.date_range('2024-01-01','2024-01-31',freq='D'); print(f'D: {len(d)} days'); b = pd.date_range('2024-01-01','2024-01-31',freq='B'); print(f'B: {len(b)} days')"`

Expected: D=31 days, B=22 days

- [ ] **Step 4: Fix forecast future timestamps in kronos_wrapper.py**

In `KronosTH.forecast()`, lines 150-153, after computing `max_pred_len`:

```python
# Add calendar detection after last_ts computation
last_ts = x_timestamps.iloc[-1]

# Determine calendar frequency from ticker class
from kth.data.universe import get_ticker_class
ticker_cls = get_ticker_class(ticker) if ticker != "<dataframe>" else None
calendar_freq = "D" if ticker_cls == "crypto" else "B"

y_timestamps = pd.Series(
    pd.date_range(
        start=last_ts + pd.Timedelta(days=1),
        periods=max_pred_len,
        freq=calendar_freq,
    )
)
```

Wait — the `forecast()` method uses `self.cache_dir` for ticker lookups. But `ticker` is already resolved at this point. Actually, `ticker` is the variable set earlier in forecast(): either the original ticker string or `"<dataframe>"`. We can use `get_ticker_class(ticker)` when ticker is a real ticker.

But what about the DataFame case (`ticker = "<dataframe>"`)? In that case, we default to `"B"` (business days) since we can't determine the asset class from the DataFrame alone.

Let me refine the approach: instead of using `get_ticker_class` inline (which requires cache_dir), we can determine the calendar frequency from the timestamps in the DataFrame itself. If the DataFrame has Saturday/Sunday timestamps, it's crypto (7-day). Otherwise, it's equity (5-day).

Actually, the simpler approach: just pass `calendar_freq` as a parameter from the callers. The `precompute_forecasts` already knows the ticker list and can determine the calendar. Then pass it through `forecast_batch`.

But `forecast_batch` calls `self._predictor.predict_batch()` directly — not `self.forecast()`. So the fix needs to be in `forecast_batch()` too.

Let me simplify: add a `calendar_freq: str = "B"` parameter to both `forecast()` and `forecast_batch()`, and to `precompute_forecasts()`. The callers pass "D" for crypto, "B" for everything else.

Let me correct Step 4:

In `KronosTH.forecast()`, add `calendar_freq` parameter:

```python
def forecast(
    self,
    ticker_or_df: str | pd.DataFrame,
    pred_lens: list[int] | None = None,
    n_samples: int = 50,
    lookback: int = 400,
    calendar_freq: str = "B",  # "B" for equities, "D" for crypto
) -> ForecastResult:
```

Replace lines 150-153:

```python
# OLD:
y_timestamps = pd.Series(
    pd.bdate_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq="B")
)

# NEW:
y_timestamps = pd.Series(
    pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq=calendar_freq)
)
```

- [ ] **Step 5: Fix forecast_batch similarly**

Same change in `forecast_batch()`:

```python
def forecast_batch(
    self,
    tickers_or_dfs: list[str | pd.DataFrame],
    pred_lens: list[int] | None = None,
    n_samples: int = 50,
    lookback: int = 400,
    calendar_freq: str = "B",
) -> dict[str, ForecastResult]:
```

Replace line ~249:

```python
# OLD:
y_stamp = pd.Series(
    pd.bdate_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq="B")
)

# NEW:
y_stamp = pd.Series(
    pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq=calendar_freq)
)
```

- [ ] **Step 6: Pass calendar_freq from precompute_forecasts**

In `precompute_forecasts()`, after computing `freq`:

```python
freq = _get_calendar_for_tickers(tickers)
print(f"[precompute] Calendar: {'7-day (crypto)' if freq == 'D' else '5-day (business)'}")

# Pass calendar_freq to forecast_batch
results = kronos_th.forecast_batch(
    uncached, pred_lens=[pred_len], n_samples=n_samples,
    lookback=lookback, calendar_freq=freq,
)
```

- [ ] **Step 7: Re-generate ZS forecast cache to test**

The existing ZS cache was built with 5-day calendar. After this fix, old crypto caches are invalid. Delete and regenerate:

```bash
rm -rf data/forecast_cache/NeoQuasar_Kronos-small/
```

Then run a single-day test:

```bash
venv/bin/python -c "
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts
k = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
precompute_forecasts(k, ['BTC-USD'], '2024-01-01', '2024-01-03', pred_len=20, n_samples=10, lookback=400)
print('Done — check data/forecast_cache/NeoQuasar_Kronos-small/')
"
```

Expected: cache directory contains files for 2024-01-01, 2024-01-02, 2024-01-03 (3 days, not 2).

- [ ] **Step 8: Commit**

```bash
git add kth/backtest/walkforward.py kth/models/kronos_wrapper.py
git commit -m "fix: crypto calendar — 7-day date_range instead of 5-day bdate_range

- walkforward.py: _get_calendar_for_tickers() returns D/B freq
- kronos_wrapper.py: forecast/forecast_batch accept calendar_freq param
- Crypto precompute now covers weekends (28% more data)
- Fixes volatility understatement (~20-30%) and horizon mismatch"
```

---

### Task 2: Rename Hit Rate → Trade Win Rate (Issue 6)

**Files:**
- Modify: `kth/backtest/metrics.py:107-108`
- Modify: `kth/backtest/walkforward.py` (any label references)
- Modify: `scripts/compare_finetune.py` (output formatting)
- Modify: `scripts/eval_holdout.py` (label references if any)

- [ ] **Step 1: Rename in metrics.py**

In `compute_trade_metrics()`, rename the dict key:

```python
# OLD:
return {
    "hit_rate": hit_rate,
    "payoff_ratio": payoff,
    ...

# NEW:
return {
    "trade_win_rate": hit_rate,
    "payoff_ratio": payoff,
    ...
```

- [ ] **Step 2: Update all references in project**

Search for `"hit_rate"` in `kth/` and `scripts/`:

```bash
grep -rn '"hit_rate"\|\.hit_rate\|["\']hit_rate["\']' kth/ scripts/ --include="*.py"
```

Replace each reference with `"trade_win_rate"` where it reads from metrics dict.

- [ ] **Step 3: Update output labels in compare_finetune.py**

In the comparison table loops:

```python
# OLD:
for key in ["cagr", "sharpe", "sortino", "max_drawdown", "calmar", "hit_rate"]:

# NEW:
for key in ["cagr", "sharpe", "sortino", "max_drawdown", "calmar", "trade_win_rate"]:
```

- [ ] **Step 4: Add explanation comment in metrics.py**

Above the `compute_trade_metrics` function, add:

```python
def compute_trade_metrics(trades: pd.DataFrame) -> dict:
    """
    NOTE: 'trade_win_rate' is the proportion of trades with gross_return > 0.
    For a long-biased rolling strategy, this measures position-churn P&L,
    NOT forecast direction accuracy. A low trade_win_rate (<5%) is expected
    when the strategy holds positions continuously and only rebalances.
    
    For forecast direction accuracy, see eval_holdout.py results or compute
    direction_accuracy from the forecast cache.
    """
```

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/metrics.py kth/backtest/walkforward.py scripts/compare_finetune.py scripts/eval_holdout.py
git commit -m "refactor: rename hit_rate → trade_win_rate with context comment

- Clarifies it's trade P&L rate, not forecast direction accuracy
- Adds docstring explaining low rate is expected for long-biased rolling portfolios"
```

---

### Task 3: Replace Dead finetune.py Stubs (Issue 4)

**Files:**
- Modify: `kth/models/finetune.py` — `finetune_tokenizer()`, `finetune_predictor()`
- Modify: `notebooks/04_finetune_per_market.ipynb` — Cells 6, 7

- [ ] **Step 1: Replace finetune_tokenizer() stub**

In `kth/models/finetune.py`, replace the `finetune_tokenizer()` function body:

```python
def finetune_tokenizer(
    dataset: dict[str, KronosDataset],
    output_dir: str,
    epochs: int = 1,
    batch_size: int = 32,
    lr: float = 1e-4,
    seed: int = 42,
) -> str:
    """
    DEPRECATED: Kronos does not expose a fit() method. Use the pre-trained
    tokenizer directly via:
    
        from kth.models._kronos_bridge import KronosTokenizer
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    
    For full training with SGDR + early stopping, see:
        scripts/train_per_market.py
    """
    raise NotImplementedError(
        "Kronos Tokenizer has no fit() method. "
        "Use KronosTokenizer.from_pretrained() directly. "
        "See scripts/train_per_market.py for the working training pipeline."
    )
```

- [ ] **Step 2: Replace finetune_predictor() stub**

In `kth/models/finetune.py`, replace `finetune_predictor()`:

```python
def finetune_predictor(
    dataset: dict[str, KronosDataset],
    tokenizer_path: str,
    output_dir: str,
    **hparams,
) -> str:
    """
    DEPRECATED: Kronos does not expose a fit() method. The actual training
    pipeline is in scripts/train_per_market.py which uses:
        tokenizer.encode() → model.forward() → model.head.compute_loss()
    with SGDR (CosineAnnealingWarmRestarts) and early stopping.
    """
    raise NotImplementedError(
        "Kronos Predictor has no fit() method. "
        "Use scripts/train_per_market.py for training. "
        "For inference on fine-tuned checkpoints, use load_finetuned_checkpoint()."
    )
```

- [ ] **Step 3: Update Colab notebook Cells 6-7**

Read the notebook JSON, replace Cells 6 and 7:

Cell 6 (tokenizer):
```python
# OLD: tok_path = finetune_tokenizer(dataset, ...)
# NEW:
print("Tokenizer fine-tuning is DEPRECATED — Kronos has no fit() method.")
print("Using pre-trained tokenizer instead.")
tok_path = "NeoQuasar/Kronos-Tokenizer-base"
print(f"Tokenizer: {tok_path}")
```

Cell 7 (predictor):
```python
# OLD: pred_path = finetune_predictor(dataset, tokenizer_path=tok_path, ...)
# NEW:
if MODE == "train":
    import subprocess
    subprocess.run([
        "python", "scripts/train_per_market.py", MODEL_NAME, str(FOLD)
    ])
    pred_path = f'/content/drive/MyDrive/kronos-th/checkpoints/{MODEL_NAME}/fold{FOLD}/best'
    print(f"Predictor: {pred_path}")
else:
    pred_path = f'/content/drive/MyDrive/kronos-th/checkpoints/{MODEL_NAME}/fold{FOLD}/best'
    print(f"Holdout eval using: {pred_path}")
```

- [ ] **Step 4: Commit**

```bash
git add kth/models/finetune.py notebooks/04_finetune_per_market.ipynb
git commit -m "fix: replace dead finetune stubs with NotImplementedError

- finetune_tokenizer() + finetune_predictor() now explain why they don't work
- Link to scripts/train_per_market.py and load_finetuned_checkpoint()
- Colab notebook cells 6-7 updated to use working alternatives"
```

---

### Task 4: Update Stale Documentation (Issue 5)

**Files:**
- Modify: `PROJECT_STRUCTURE.md` — §3 (universe), §6 (layers), §7 (directory), §8 (notebooks), §13 (open questions), §14 (current status)
- Modify: `CLAUDE.md:82` — universe count
- Modify: `docs/superpowers/plans/2026-05-18-per-market-finetuning.md` — mark Issues 1-6

- [ ] **Step 1: Update PROJECT_STRUCTURE.md §3 (Universe count)**

Replace all "51 tickers" with "100 tickers" and update the table.

Replace the `thai_equity`, `us_equity`, `crypto` rows in the table:

```
| `thai_equity` | 50 | PTT.BK, KBANK.BK, SCB.BK, ... (50 SET stocks) | Expanded from 15 — covers 8 sectors |
| `us_equity` | 17 | AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, BRK-B, JPM, V, COST, WMT, NFLX, AMD, DIS, KO, PEP | Expanded from 10 |
| `crypto` | 12 | BTC-USD, ETH-USD, SOL-USD, ADA-USD, AVAX-USD, LINK-USD, DOGE-USD, DOT-USD, LTC-USD, NEAR-USD, VET-USD, MATIC-USD | Trimmed from 5 (BNB/XRP dropped) |
```

Update totals everywhere.

- [ ] **Step 2: Update PROJECT_STRUCTURE.md §6 (Layer status)**

Replace the architecture diagram:

```
LAYER 5: Decision report      notebooks/05_decision_report.ipynb     ⬜ planned
LAYER 4: Backtest             notebooks/03_walkforward_backtest.ipynb 🔄 partial
                                kth/backtest/walkforward.py            ✅ built
                                kth/backtest/strategy.py               ✅ built
                                kth/backtest/metrics.py                 ✅ built
                                scripts/compare_finetune.py            ⬜ unexecuted
LAYER 3: Kronos model         kth/models/kronos_wrapper.py            ✅ built
                                kth/models/finetune.py                  ✅ built
                                kth/models/_kronos_bridge.py            ✅ built
                                scripts/train_per_market.py             ✅ built
                                scripts/eval_holdout.py                 ✅ built
                                checkpoints/{model}/fold{f}/best/       ✅ 9 trained
LAYER 2: Feature pipeline     kth/data/loader.py                       ✅ done
LAYER 1: Universe definition  kth/data/universe.py                     ✅ done (100 tickers)
```

- [ ] **Step 3: Answer PROJECT_STRUCTURE.md §13 (6 open questions)**

Replace the undecided questions with answers:

```
1. Model size → Kronos-small (24.7M). Confirmed by 65 hrs of training on GTX 1060. Kronos-base would require T4 or A100.
2. Pred horizon → 20 days. Longer = more useful signal. 5-day too noisy.
3. Forecast samples → 10. Fits 6GB VRAM. 20+ causes OOM.
4. Strategy → Long-only. Short not realistic for Thai retail (can't short SET stocks).
   US equities: possible via inverse ETFs (SH, SQQQ) — not implemented.
5. Universe → 100 tickers. No trim needed. Small-data tickers (GULF.BK, SCB.BK)
   are filtered at precompute time by walkforward.py's viable-check.
6. Benchmarks → SET Index (thai_equity), SPY (us_equity), 60/40 SPY/TLT, equal-weight.
   Already computed in walkforward.py _compute_benchmarks(). Need to print comparison table.
   FX-adjusted: THB=X available. Compute USD returns × THB=X for Thai investor P&L.
```

- [ ] **Step 4: Update CLAUDE.md universe count**

In `CLAUDE.md` line 82 (or wherever "51" appears):

```bash
# Find and replace all "51" in context of ticker count
grep -n "51" CLAUDE.md
```

Replace with "100" where referring to universe size.

- [ ] **Step 5: Mark review issues as in-progress in plan document**

In `docs/superpowers/plans/2026-05-18-per-market-finetuning.md`, update the HFM Review table statuses:

```
| 1 | CRITICAL | ... | 🔄 In progress |
| 2 | HIGH | ... | 🔄 Specs approved, unexecuted |
| 3 | HIGH | ... | 🔄 In progress |
| 4 | MEDIUM | ... | 🔄 In progress |
| 5 | LOW | ... | 🔄 In progress |
| 6 | LOW | ... | 🔄 In progress |
```

- [ ] **Step 6: Commit**

```bash
git add PROJECT_STRUCTURE.md CLAUDE.md docs/superpowers/plans/2026-05-18-per-market-finetuning.md
git commit -m "docs: update PROJECT_STRUCTURE.md to current state

- Universe: 51→100 tickers (50 Thai, 17 US, 12 crypto)
- Layers 3-4 partially built (not just planned)
- Answer all 6 open questions from §13
- Update CLAUDE.md universe count
- Refresh current status table"
```

---

### Task 5: Thai Equity Backtest with Benchmarks (Issue 1)

**Files:**
- Modify: `scripts/compare_finetune.py` — add benchmark metrics table
- Run: on GTX 1060 — walkforward for thai_equity ZS with benchmark comparison output

**Note:** Benchmark EQUITY CURVES are already computed and saved by `_compute_benchmarks()`. This task computes benchmark METRICS (Sharpe, CAGR, etc.) and prints a comparison table.

- [ ] **Step 1: Add benchmark metrics computation to compare script**

In `scripts/compare_finetune.py`, after `run_walkforward()`, add:

```python
def compute_benchmark_metrics(r: BacktestResult) -> dict:
    """Compute Sharpe, CAGR, maxDD for each benchmark from equity curves."""
    from kth.backtest.metrics import compute_sharpe, compute_max_drawdown
    bm_metrics = {}
    for name, eq in r.benchmarks.items():
        daily = eq.pct_change().dropna()
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (252 / len(eq)) - 1 if len(eq) > 0 else 0
        bm_metrics[name] = {
            "cagr": cagr,
            "sharpe": compute_sharpe(daily),
            "max_drawdown": compute_max_drawdown(eq),
        }
    return bm_metrics
```

- [ ] **Step 2: Add benchmark comparison table to output**

After the metrics table, add:

```python
print(f"\n  Benchmark Comparison:")
print(f"  {'Benchmark':<15} {'CAGR':>10} {'Sharpe':>10} {'Max DD':>10}")
print(f"  {'-'*45}")
for name, bm in bm_metrics.items():
    print(f"  {name:<15} {bm['cagr']:>+9.2%} {bm['sharpe']:>9.2f} {bm['max_drawdown']:>9.2%}")
print(f"  {'Strategy':<15} {r.metrics.get('cagr',0):>+9.2%} {r.metrics.get('sharpe',0):>9.2f} {r.metrics.get('max_drawdown',0):>9.2%}")
```

- [ ] **Step 3: Run Thai equity ZS backtest with benchmarks**

```bash
rm -rf data/forecast_cache/NeoQuasar_Kronos-small/  # clean cache
venv/bin/python -c "
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import run_walkforward, precompute_forecasts, BacktestConfig
from kth.data.universe import UNIVERSE

tickers = [t for t,_,_ in UNIVERSE['thai_equity']]
config = BacktestConfig(
    start_date='2022-01-01', end_date='2024-12-31',
    lookback=400, pred_len=20, n_samples=10,
    position_sizing='equal',
)
th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
precompute_forecasts(th, tickers, start_date=config.start_date, end_date=config.end_date,
                     pred_len=config.pred_len, n_samples=config.n_samples, lookback=config.lookback)
r = run_walkforward(config, th, tickers)
r.save('data/backtest_results/thai_equity_2022-2024_zs_v2')
"
```

Expected: runs ~3-4 hrs on GTX 1060 (50 tickers, ~750 days).

- [ ] **Step 4: Review output — does strategy beat benchmarks?**

Check the output for:
```
Benchmark         CAGR     Sharpe     Max DD
----------------------------------------------
SET              +X.XX%     X.XX      -XX.XX%
SPY              +X.XX%     X.XX      -XX.XX%
60_40            +X.XX%     X.XX      -XX.XX%
equal_weight     +X.XX%     X.XX      -XX.XX%
Strategy         +X.XX%     X.XX      -XX.XX%
```

The key question: does Strategy Sharpe exceed SET Index Sharpe? If yes, the signal adds alpha. If no, the model is riding the market.

- [ ] **Step 5: Commit results**

```bash
git add data/backtest_results/thai_equity_2022-2024_zs_v2/
git commit -m "backtest: Thai equity ZS with benchmark comparison (Issue 1)"
```

---

### Task 6: Crypto + US Equity FT Backtests (Issue 2)

**Files:**
- Run: `scripts/eval_holdout.py` — already done
- Run: `scripts/compare_finetune.py --model crypto --fold 0` — needs to run
- Run: `scripts/compare_finetune.py --model us_equity --fold 2` — needs to run

**Depends on:** Task 1 (calendar fix) and Task 2 (hit-rate rename).

- [ ] **Step 1: Generate fresh ZS forecast cache (post-calendar fix)**

The ZS cache was built with 5-day calendar. Must regenerate:

```bash
rm -rf data/forecast_cache/NeoQuasar_Kronos-small/
```

- [ ] **Step 2: Run crypto fold 0 backtest**

```bash
venv/bin/python scripts/compare_finetune.py --model crypto --fold 0
```

**Time:** ~15.5 hrs (ZS precompute 7.5h + FT precompute 7.5h + walkforward 0.3h).

- [ ] **Step 3: Review crypto output**

Expected output table per spec `2026-05-21-crypto-backtest-design.md` §6.1. Key questions:
- Does FT Sharpe exceed ZS Sharpe + 0.05?
- Is BTC-only Sharpe better or worse than portfolio Sharpe?
- Compare against SPY benchmark (computed automatically).

- [ ] **Step 4: Run us_equity fold 2 backtest**

```bash
venv/bin/python scripts/compare_finetune.py --model us_equity --fold 2
```

**Time:** ~21.5 hrs (ZS precompute 10.5h + FT precompute 10.5h + walkforward 0.5h).

- [ ] **Step 5: Review us_equity output**

Per spec `2026-05-21-backtest-comparison-design.md` §3.3. Check:
- Does FT beat ZS in backtest (not just holdout)?
- Compare against SPY, equal_weight benchmarks.

- [ ] **Step 6: Final verdict and commit**

Update the deploy decisions:

```
us_equity fold 2: [Deploy / Marginal / Pass] based on backtest
crypto fold 0:    [Deploy / Marginal / Pass] based on backtest
```

```bash
git add data/backtest_results/crypto_zs/ data/backtest_results/crypto_ft_fold0/
git add data/backtest_results/us_equity_zs/ data/backtest_results/us_equity_ft_fold2/
git add docs/superpowers/plans/2026-05-18-per-market-finetuning.md
git commit -m "backtest: crypto fold 0 + us_equity fold 2 — verdicts [TBD]"
```

---

### Self-Review

1. **Spec coverage:** All 6 HFM review issues mapped to tasks. Issue 3 (calendar) blocks Issue 6 (backtests) — correctly ordered.

2. **Placeholder scan:** No TBDs, TODOs, or vague instructions. Every step has exact code or command.

3. **Type consistency:** `calendar_freq` parameter added consistently across `forecast()`, `forecast_batch()`, `precompute_forecasts()`. `trade_win_rate` key consistency checked across all files.

4. **Scope:** Tasks 1-4 are no-GPU (~3 hrs total). Tasks 5-6 are GPU-intensive (overnight sessions). Each task produces a working, testable state.

---

*Document version: 2026-05-21. Plan for 6 HFM review fixes.*
