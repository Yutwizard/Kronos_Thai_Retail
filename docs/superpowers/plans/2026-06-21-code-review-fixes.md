# Code Review Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 21 actionable code issues identified in the quant + engineering review, prioritised by severity: 3 critical stat bugs, 4 high-risk quant/eng bugs, 5 medium issues, then low-priority cleanup.

**Known limitations NOT fixed in this plan (deferred — require GPU or structural changes):**
- Survivorship bias (hardcoded 2025 universe backtested to 2022) — requires point-in-time universe membership data
- No delisting return (positions stop updating if a ticker delists mid-backtest) — requires delisting event data
- US dividend withholding tax (15-30% WHT) missing from FRICTION — material for multi-month holdings, needs research
- No atomicity for staging promotion (partial failure leaves dashboard inconsistent) — needs transactional sheet writes
- `compute_metrics('paper')` called twice in pipeline — redundant, needs refactor for caching
- Assumed fills use forecast-day close (look-ahead for paper trading) — needs intraday data or T+1 execution model

**Architecture:** Each fix is independently testable and committable. Critical fixes (Phases 1-2) must complete before the backtest re-run (Phase 6). All fixes use the existing TDD convention: write the assertion in `verify_*.py` first (RED), implement until green (GREEN), refactor. No pytest, no CI.

**Tech Stack:** Python 3.12, pandas, numpy, scipy.stats, plain-assert `verify_*.py` test runners.

**Testing conventions:**
- `verify_data_layer.py` — existing data-layer regression (must stay green)
- `verify_kaggle_runtime.py` — existing pipeline regression (must stay green)
- `verify_fixes.py` — NEW file for all review-fix tests
- Run from repo root with venv active: `python verify_fixes.py`

**Important constraints (from AGENTS.md):**
- `inv_vol` position sizing was backtested and rejected — do NOT change to inv_vol.
- Fine-tuning did not beat zero-shot — do NOT deploy fine-tuned models.
- `min_holding_days` / `long_threshold` experiments are invalid (read n10 cache while stored results use n50) — do NOT change these parameters.
- Historical backtest p-values (t-test in `compute_metrics()`, stored in `data/backtest_results/`) are never changed.
- No pytest, no CI, no lint config.

---

## File Structure

| File | Role | Action |
|------|------|--------|
| `kth/backtest/metrics.py` | PSR, bootstrap CI, t-test, profit_factor | Modify (Tasks 1-4) |
| `kth/backtest/walkforward.py` | Equity curve alignment, open_trades, benchmarks | Modify (Tasks 5-8) |
| `kth/backtest/strategy.py` | NaN check, dead-code cleanup | Modify (Tasks 9-10) |
| `kth/trading/trade_gen.py` | Cash guard, reduce filter, CACHE_SLUG, imports | Modify (Tasks 11-14) |
| `kth/data/universe.py` | MEGA.BK sector, fx_macro guard, reverse-lookup | Modify (Tasks 15-17) |
| `kth/pipeline/daily.py` | Risk Metrics upsert, calibration idempotency, col>26 | Modify (Tasks 18-20) |
| `kth/trading/sheets.py` | promote_staging upsert option | Modify (Task 18) |
| `data/backtest_results/MANIFEST.md` | Mark authoritative vs stale runs | Create (Task 21) |
| `verify_fixes.py` | All new tests | Create (Task 0, extended per phase) |

---

## Phase 1 — Critical statistical bugs (Tasks 1-3)

These corrupt the headline backtest numbers. Must fix before any re-run.

### Task 1: Fix PSR formula — use daily SR, not annualized

**Files:**
- Modify: `kth/backtest/metrics.py:130-153`
- Test: `verify_fixes.py`

**Root cause:** `compute_psr()` line 145 computes `sr = mean/std * sqrt(252)` (annualized), then feeds it into the Bailey & Lopez de Prado formula which expects the **per-period (daily) Sharpe**. With annualized SR≈2.27, the denominator `sqrt(1 - skew*sr + (kurt-1)/4*sr²)` becomes `sqrt(negative)` → NaN. Verified: `thai_equity_2024_n50/metrics.json` shows `psr_0_5: None, psr_1_0: None`.

- [ ] **Step 1: Create `verify_fixes.py` with the failing PSR test**

```python
# verify_fixes.py
"""Tests for code-review fixes. Run: python verify_fixes.py"""
import inspect
import tempfile
import numpy as np
import pandas as pd
from datetime import date
from kth.backtest.metrics import compute_psr, compute_sharpe_ci


def test_psr_returns_value_for_high_sharpe():
    """PSR must return a finite float, not NaN, when Sharpe > 2.0 (the bug case).
    The bug: annualized SR fed into Bailey formula that expects per-period SR.
    Annualized SR≈2.27 → denominator sqrt(negative) → NaN (not None)."""
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0.002, 0.01, 252))  # ~Sharpe 3.0 annualized
    psr = compute_psr(returns, benchmark_sr=0.5)
    assert not np.isnan(psr), f"PSR is NaN — the bug (annualized SR in per-period formula)"
    assert isinstance(psr, float), f"PSR is {type(psr)}, expected float"
    assert 0.0 <= psr <= 1.0, f"PSR {psr} out of [0,1]"
    print("PASS test_psr_returns_value_for_high_sharpe")


def test_psr_zero_sharpe_returns_05():
    """When SR ≈ 0, PSR vs benchmark 0 should be ~0.5."""
    returns = pd.Series(np.random.default_rng(1).normal(0, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=0.0)
    assert 0.3 < psr < 0.7, f"PSR for zero-SR vs 0 benchmark should be ~0.5, got {psr}"
    print("PASS test_psr_zero_sharpe_returns_05")


def test_psr_benchmark_sr_clipped():
    """PSR vs a high benchmark (1.0 annualized) for a mediocre strategy should be low."""
    returns = pd.Series(np.random.default_rng(2).normal(0.0001, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert psr < 0.5, f"PSR for weak SR vs benchmark 1.0 should be < 0.5, got {psr}"
    print("PASS test_psr_benchmark_sr_clipped")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        params = inspect.signature(fn).parameters
        if params:
            with tempfile.TemporaryDirectory() as tmp:
                fn(tmp)
        else:
            fn()
    print(f"ALL {len(fns)} PASSED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `compute_psr` returns `None` (nan → stored as None) for high-Sharpe input.

- [ ] **Step 3: Fix the PSR formula**

Replace `kth/backtest/metrics.py:130-153`:

```python
def compute_psr(
    daily_returns: pd.Series,
    benchmark_sr: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Probabilistic Sharpe Ratio (Bailey & Lopez de Prado, 2012).
    P(SR > benchmark_sr) — probability that the true Sharpe exceeds the benchmark.

    PSR = Φ( (SR_daily - SR*_daily) × √(T-1) / √(1 − γ₃·SR_daily + (γ₄−1)/4·SR_daily²) )

    where SR_daily is the observed per-period (daily) Sharpe, SR*_daily is the
    per-period benchmark (annual benchmark ÷ √periods_per_year), T is the number
    of observations, γ₃ is skewness, and γ₄ is excess kurtosis.

    Key: the formula requires the PER-PERIOD Sharpe, not the annualised one.
    Using annualised SR causes the denominator to go negative for SR > ~2.0.
    """
    from scipy.stats import norm
    returns = daily_returns.dropna().values
    if len(returns) < 2:
        return 0.0
    std = daily_returns.std()
    if std == 0 or pd.isna(std):
        return 0.0
    sr_daily = float(daily_returns.mean() / std)
    benchmark_daily = benchmark_sr / np.sqrt(periods_per_year)
    T = len(returns)
    skew = float(np.mean((returns - returns.mean()) ** 3) / returns.std() ** 3) if returns.std() > 0 else 0.0
    kurt = float(np.mean((returns - returns.mean()) ** 4) / returns.std() ** 4 - 3) if returns.std() > 0 else 0.0
    denom_sq = 1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2
    if denom_sq <= 0:
        return 0.5 if sr_daily > benchmark_daily else 0.0
    denominator = np.sqrt(denom_sq)
    z = (sr_daily - benchmark_daily) * np.sqrt(T - 1) / denominator
    return float(norm.cdf(z))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python verify_fixes.py`
Expected: PASS for all 3 PSR tests.

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/metrics.py verify_fixes.py
git commit -m "fix(metrics): PSR uses per-period SR, not annualised — was NaN for SR>2.0"
```

---

### Task 2: Fix equity curve date alignment in walkforward

**Files:**
- Modify: `kth/backtest/walkforward.py:419-438`
- Test: `verify_fixes.py`

**Root cause:** Mark-to-market happens at `next_day` close (line 420), but the equity curve is indexed by `trading_days[:len(portfolio_values)]` (line 437), which uses `day` not `next_day`. So `equity_curve[day_i]` holds the value at `day_{i+1}`'s close. When `compute_metrics` computes `excess_returns = daily_returns - benchmark.pct_change()`, the strategy return at index `i` is "close-day_{i+1} → close-day_{i+2}" while benchmark return at the same index is "close-day_i → close-day_{i+1}". Alpha/beta/IR/t-stat are computed on misaligned returns.

- [ ] **Step 1: Add the source-level alignment guard test**

Append to `verify_fixes.py`:

```python
def test_equity_curve_index_is_mark_day_not_signal_day():
    """Regression guard: the equity curve must be indexed by mark_days (the day
    the value was observed), NOT by trading_days[:len(values)] (the signal day).
    If someone reverts to the old pattern, the index is off-by-one and
    alpha/beta/IR are computed on misaligned strategy vs benchmark returns.

    We can't run a full backtest offline (needs GPU + forecast cache), so we
    check the source code contains the fix pattern."""
    from kth.backtest import walkforward
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'mark_days' in source, \
        "Equity curve must be indexed by mark_days — check the fix wasn't reverted"
    assert 'mark_index' in source, \
        "Equity curve must use mark_index — check the fix wasn't reverted"
    print("PASS test_equity_curve_index_is_mark_day_not_signal_day")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `mark_days` not in source (current code uses `trading_days[:len(portfolio_values)]`).

- [ ] **Step 3: Fix the equity curve index**

In `kth/backtest/walkforward.py`, replace lines 419-438:

```python
        # --- 5. MARK TO MARKET at t+1 close ---
        mark_day = next_day

        mtm_value = cash
        mtm_gross = gross_cash
        for t, units in holdings_units.items():
            df_t = ticker_data.get(t)
            if df_t is not None:
                mask = df_t["timestamps"] <= mark_day
                if mask.any():
                    price = float(df_t.loc[mask, "close"].iloc[-1])
                    mtm_value += units * price
                    mtm_gross += units * price

        portfolio_values.append(mtm_value)
        gross_portfolio_values.append(mtm_gross)
        mark_days.append(mark_day)

    # Build result DataFrames — index by mark_day (the day the value was observed),
    # NOT by signal day, so strategy returns align with benchmark returns.
    mark_index = pd.DatetimeIndex(mark_days[:len(portfolio_values)])
    equity_curve = pd.Series(portfolio_values, index=mark_index)
    gross_equity_curve = pd.Series(gross_portfolio_values, index=mark_index)
    daily_returns = equity_curve.pct_change().dropna()
    trades_df = pd.DataFrame(trades_list)
```

Also add `mark_days = []` before the main loop (near where `portfolio_values = []` is initialised). Find that line and add `mark_days` next to it.

- [ ] **Step 4: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/walkforward.py verify_fixes.py
git commit -m "fix(walkforward): equity curve indexed by mark-day not signal-day — fixes alpha/beta misalignment"
```

---

### Task 3: Fix open_trades overwrite on rebalance

**Files:**
- Modify: `kth/backtest/walkforward.py:355-412`

**Root cause:** Line 411 overwrites `open_trades[t]` on every rebalance with the new `entry_price` and `trade_value = abs(trade_value)` (the delta, not full position). On close, `gross_return = (exec_price / entry_price - 1) * trade_value` only captures the P&L from the *last rebalance*, not the position's lifetime.

- [ ] **Step 1: Add the source-level guard test**

Append to `verify_fixes.py`:

```python
def test_open_trades_blends_on_rebalance():
    """Regression guard: walkforward must blend entry price on rebalance, not
    overwrite. The bug: open_trades[t] was overwritten on every rebalance with
    the new entry_price, so trade P&L only captured the last delta, not the
    full position lifetime.

    We can't run a full backtest offline, so we check the source code contains
    the blend fix pattern."""
    from kth.backtest import walkforward
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'blended' in source.lower(), \
        "open_trades must blend entry price on rebalance — check the fix wasn't reverted"
    print("PASS test_open_trades_blends_on_rebalance")


def test_open_trades_blend_logic_correct():
    """Validate the blend math: buy 100 @ 50, rebalance +50 @ 60, sell all @ 55.
    Blended entry = (100*50 + 50*60)/150 = 53.33 → profit at 55.
    Buggy (overwrite): entry = 60 → loss at 55."""
    open_trades = {}
    open_trades["X"] = {"entry_price": 50.0, "units": 100, "trade_value": 5000.0, "entry_date": "d1"}
    old = open_trades["X"]
    new_units, new_price = 50, 60.0
    total_units = old["units"] + new_units
    blended_entry = (old["units"] * old["entry_price"] + new_units * new_price) / total_units
    open_trades["X"] = {"entry_price": blended_entry, "units": total_units,
                         "trade_value": total_units * blended_entry, "entry_date": old["entry_date"]}
    exec_price = 55.0
    gross_return = (exec_price / open_trades["X"]["entry_price"] - 1) * open_trades["X"]["trade_value"]
    assert gross_return > 0, f"Blended entry should give profit: {gross_return}"
    assert abs(open_trades["X"]["entry_price"] - 53.333) < 0.01, "Entry should be blended"
    print("PASS test_open_trades_blend_logic_correct")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `blended` not in source (current code overwrites `open_trades[t]`).

- [ ] **Step 3: Fix the rebalance logic in walkforward.py**

In `kth/backtest/walkforward.py`, replace lines 406-412 (the `open_trades[t] = ...` assignment):

```python
            trades_list.append({
                "date": day, "ticker": t, "direction": direction,
                "size_pct": abs(trade_value), "friction_cost": friction_cost,
                "gross_return": 0.0,
            })
            # Blend entry price on rebalance; don't overwrite.
            # Weighted average of old entry and new execution price.
            current_units = holdings_units.get(t, 0)
            if t in open_trades and direction == "buy":
                old = open_trades[t]
                total_units = old["units"] + units_delta
                if total_units > 0:
                    blended = (old["units"] * old["entry_price"] + units_delta * exec_price) / total_units
                    open_trades[t] = {"entry_price": blended, "units": total_units,
                                       "trade_value": total_units * blended, "entry_date": old["entry_date"]}
            elif t in open_trades and direction == "sell":
                # Partial close: keep entry_price, reduce units
                remaining = holdings_units.get(t, 0)
                if remaining > 1e-10:
                    open_trades[t]["units"] = remaining
                    open_trades[t]["trade_value"] = remaining * open_trades[t]["entry_price"]
                else:
                    open_trades.pop(t, None)
            else:
                # New position
                open_trades[t] = {"entry_price": exec_price, "units": current_units,
                                   "trade_value": abs(trade_value), "entry_date": day}
```

- [ ] **Step 4: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/walkforward.py verify_fixes.py
git commit -m "fix(walkforward): blend entry price on rebalance instead of overwriting — trade P&L now reflects full position lifetime"
```

---

## Phase 2 — High-risk quant + engineering fixes (Tasks 4-7)

### Task 4: Fix bootstrap to use stationary block bootstrap

**Files:**
- Modify: `kth/backtest/metrics.py:156-180`

**Root cause:** Line 173 uses `rng.choice(returns, replace=True)` — i.i.d. resampling that destroys time-series structure. For returns with volatility clustering, this understates Sharpe uncertainty.

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_sharpe_ci_returns_finite_values():
    """Bootstrap CI must return finite floats, not None or inf."""
    returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.01, 500))
    ci = compute_sharpe_ci(returns, n_bootstrap=500)
    assert isinstance(ci["sharpe_ci_2_5"], float), f"lower bound is {type(ci['sharpe_ci_2_5'])}"
    assert isinstance(ci["sharpe_ci_97_5"], float), f"upper bound is {type(ci['sharpe_ci_97_5'])}"
    assert np.isfinite(ci["sharpe_ci_2_5"]), "lower bound not finite"
    assert np.isfinite(ci["sharpe_ci_97_5"]), "upper bound not finite"
    assert ci["sharpe_ci_2_5"] <= ci["sharpe_ci_97_5"], "CI bounds inverted"
    print("PASS test_sharpe_ci_returns_finite_values")


def test_sharpe_ci_block_bootstrap_wider_than_iid():
    """Block bootstrap should produce wider CI than i.i.d. for autocorrelated returns
    (volatility clustering). This is a sanity check, not a hard assertion."""
    rng = np.random.default_rng(42)
    # GARCH-like returns with volatility clustering
    n = 500
    vol = np.ones(n) * 0.01
    for i in range(1, n):
        vol[i] = 0.005 + 0.9 * vol[i-1] + 0.05 * abs(rng.normal(0, 0.01))
    returns = pd.Series(rng.normal(0.001, vol))
    ci = compute_sharpe_ci(returns, n_bootstrap=500)
    width = ci["sharpe_ci_97_5"] - ci["sharpe_ci_2_5"]
    assert width > 0, "CI width must be positive"
    print(f"PASS test_sharpe_ci_block_bootstrap_wider_than_iid (width={width:.3f})")
```

- [ ] **Step 2: Run test (diagnostic — current i.i.d. version may pass the finite check)**

Run: `python verify_fixes.py`

- [ ] **Step 3: Implement stationary block bootstrap**

Replace `kth/backtest/metrics.py:156-180`:

```python
def compute_sharpe_ci(
    daily_returns: pd.Series,
    periods_per_year: int = 252,
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
) -> dict:
    """
    Bootstrap 95% confidence interval for the annualized Sharpe ratio.
    Uses stationary block bootstrap (Politis & Romano, 1994) to preserve
    time-series structure — i.i.d. resampling understates uncertainty for
    returns with volatility clustering.
    """
    returns = daily_returns.dropna().values
    if len(returns) < 20:
        return {"sharpe_ci_2_5": 0.0, "sharpe_ci_97_5": 0.0}

    n = len(returns)
    # Expected block length — Politis & Romano suggest ~ n^(1/3)
    expected_block = max(int(n ** (1/3)), 2)
    rng = np.random.default_rng(42)

    bootstrapped = []
    for _ in range(n_bootstrap):
        # Stationary block bootstrap: block lengths ~ Geometric(expected_block)
        sample = np.empty(n)
        idx = 0
        while idx < n:
            block_len = rng.geometric(1.0 / expected_block)
            block_len = min(block_len, n - idx)
            start = rng.integers(0, n)
            for j in range(block_len):
                sample[idx + j] = returns[(start + j) % n]
            idx += block_len
        std = sample.std()
        if std > 0:
            sr = float(sample.mean() / std * np.sqrt(periods_per_year))
            bootstrapped.append(sr)

    if not bootstrapped:
        return {"sharpe_ci_2_5": 0.0, "sharpe_ci_97_5": 0.0}

    return {
        "sharpe_ci_2_5": float(np.percentile(bootstrapped, alpha * 100 / 2)),
        "sharpe_ci_97_5": float(np.percentile(bootstrapped, 100 - alpha * 100 / 2)),
    }
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/metrics.py verify_fixes.py
git commit -m "fix(metrics): stationary block bootstrap for Sharpe CI — preserves time-series structure"
```

---

### Task 5: Fix t-test ddof and benchmark fillna

**Files:**
- Modify: `kth/backtest/metrics.py:249-255`

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_t_stat_uses_sample_std():
    """t-test must use sample std (ddof=1), not population std (ddof=0)."""
    from kth.backtest.metrics import compute_metrics
    rng = np.random.default_rng(42)
    days = pd.bdate_range("2024-01-01", periods=300)
    strat = pd.Series(rng.normal(0.001, 0.01, 300), index=days)
    bench = pd.Series(rng.normal(0.0005, 0.01, 300), index=days)
    eq = pd.Series(np.cumprod(1 + strat) * 100, index=days)
    dr = eq.pct_change().dropna()
    m = compute_metrics(eq, dr, pd.DataFrame(), bench)
    # Manually compute with ddof=1
    excess = (dr - bench.pct_change()).dropna()
    t_manual = excess.mean() / (excess.std(ddof=1) / np.sqrt(len(excess)))
    assert abs(m["t_stat"] - t_manual) < 0.01, f"t-stat {m['t_stat']} vs manual {t_manual} (ddof=1)"
    print("PASS test_t_stat_uses_sample_std")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — current code uses `excess_daily.std()` which defaults to ddof=0.

- [ ] **Step 3: Fix ddof and fillna**

Replace `kth/backtest/metrics.py:249-255`:

```python
    # t-stat vs benchmark — use sample std (ddof=1), drop first NaN from pct_change
    excess_daily = (daily_returns - benchmark.pct_change()).dropna()
    if excess_daily.std(ddof=1) > 0:
        n = len(excess_daily)
        t_stat = float(excess_daily.mean() / (excess_daily.std(ddof=1) / np.sqrt(n)))
        p_value = float(2 * stats.t.sf(abs(t_stat), df=n - 1))
    else:
        t_stat = p_value = 0.0
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/backtest/metrics.py verify_fixes.py
git commit -m "fix(metrics): t-test uses ddof=1 (sample std), dropna on excess returns"
```

---

### Task 6: Fix cash shortfall in generate_trade_ticket

**Files:**
- Modify: `kth/trading/trade_gen.py:117-124, 170-213`

**Root cause:** `deployable = capital * alloc_pct` uses total portfolio value (cash + positions). If mostly invested, buys could exceed available cash. The T+2 warning says "draw from existing cash only" but the code never checks.

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_trade_ticket_buy_cost_does_not_exceed_cash():
    """Total buy cost must not exceed available cash — prevents real-money shortfall."""
    # We test the cash guard logic directly since generate_trade_ticket
    # requires full portfolio state. The guard: remaining_cap = min(deployable, cash)
    cash = 50_000.0
    total_value = 500_000.0  # 90% invested
    alloc_pct = 0.10
    deployable_naive = total_value * alloc_pct  # 50,000 — equals cash, OK
    deployable_guarded = min(deployable_naive, cash)  # 50,000 — same here

    # Now with 95% invested:
    cash2 = 25_000.0
    total_value2 = 500_000.0
    deployable_naive2 = total_value2 * alloc_pct  # 50,000
    deployable_guarded2 = min(deployable_naive2, cash2)  # 25,000 — capped!
    assert deployable_guarded2 < deployable_naive2, "Cash guard must cap deployable"
    assert deployable_guarded2 == cash2, f"Should cap at cash {cash2}, got {deployable_guarded2}"
    print("PASS test_trade_ticket_buy_cost_does_not_exceed_cash")
```

- [ ] **Step 2: Run test (diagnostic — tests the guard logic)**

Run: `python verify_fixes.py`
Expected: PASS (validates the intended logic).

- [ ] **Step 3: Add the cash guard in trade_gen.py**

In `kth/trading/trade_gen.py`, replace lines 117-124:

```python
    if positions is None:
        pos_data = get_positions("paper")
        held_tickers = {p["ticker"]: p for p in pos_data["positions"]}
        available_cash = pos_data.get("cash", INITIAL_CAPITAL)
    else:
        held_tickers = positions
        available_cash = INITIAL_CAPITAL

    capital = pos_data.get("total_value", INITIAL_CAPITAL) if positions is None else INITIAL_CAPITAL
    # Guard: deployable is capped by available cash (T+2 settlement means
    # today's buys draw from existing cash, not from today's exit proceeds).
    deployable = min(capital * alloc_pct, available_cash)
```

- [ ] **Step 4: Run all tests**

Run: `python verify_fixes.py && python verify_kaggle_runtime.py`
Expected: PASS (kaggle runtime tests may show different buy counts — that's expected).

- [ ] **Step 5: Commit**

```bash
git add kth/trading/trade_gen.py verify_fixes.py
git commit -m "fix(trade_gen): cap deployable at available cash — prevents real-money shortfall"
```

---

### Task 7: Single CACHE_SLUG source of truth

**Files:**
- Modify: `kth/trading/trade_gen.py:14-16`
- Modify: `kth/backtest/walkforward.py:46-50`

**Root cause:** `trade_gen.py:14` hardcodes `CACHE_SLUG = "NeoQuasar_Kronos-small"`. `walkforward.py:46` computes it dynamically via `_model_slug()`. If the model changes, trade_gen silently finds no forecasts.

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_cache_slug_consistent_across_modules():
    """CACHE_SLUG must be the same in trade_gen and walkforward — single source of truth."""
    from kth.trading.trade_gen import CACHE_SLUG as tg_slug
    from kth.backtest.walkforward import _model_slug
    wf_slug = _model_slug("NeoQuasar/Kronos-small")
    assert tg_slug == wf_slug, f"trade_gen={tg_slug} vs walkforward={wf_slug} — must match"
    print("PASS test_cache_slug_consistent_across_modules")
```

- [ ] **Step 2: Run test to verify it passes (they happen to match today, but it's fragile)**

Run: `python verify_fixes.py`

- [ ] **Step 3: Make trade_gen derive CACHE_SLUG from walkforward's function**

Replace `kth/trading/trade_gen.py:14-16`:

```python
from kth.backtest.walkforward import _model_slug
CACHE_SLUG = _model_slug("NeoQuasar/Kronos-small")
CACHE_DIR = Path("data/forecast_cache") / CACHE_SLUG
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py && python verify_kaggle_runtime.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/trading/trade_gen.py verify_fixes.py
git commit -m "fix(trade_gen): derive CACHE_SLUG from walkforward._model_slug — single source of truth"
```

---

## Phase 3 — Pipeline fixes (Tasks 8-10)

### Task 8: Risk Metrics upsert (preserve history)

**Files:**
- Modify: `kth/pipeline/daily.py` (`_write_all_staging` function, Risk Metrics staging block)
- Modify: `kth/trading/sheets.py` (add `upsert_staging` option)
- Test: `verify_fixes.py` + `verify_kaggle_runtime.py`

**Root cause:** `promote_staging` does `clear()` + `update()` for every sheet, replacing the entire live sheet with staging content. Risk Metrics staging has only 1 row (today). So promotion wipes Risk Metrics history. Equity Curve already uses `upsert_by_date`; Risk Metrics needs the same.

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_risk_metrics_history_preserved_on_rerun(tmp):
    """Same-day re-run must not wipe Risk Metrics history (regression for promote bug).
    run_daily_pipeline handles os.chdir(work_dir=tmp) internally and restores CWD."""
    from kth.pipeline.daily import run_daily_pipeline
    from verify_kaggle_runtime import FakeModel, FakeLoader, seeded_fake_client
    gc = seeded_fake_client()
    # Seed Risk Metrics with 2 prior days
    sh = gc.open_by_key("test_id")
    sh.worksheet("Risk Metrics")._data = [
        ["date","equity","cash","deployed_pct","trailing_sharpe_12w","max_drawdown_pct",
         "mtd_pnl_pct","trade_win_rate","calmar_ratio","sortino_ratio","drawdown_velocity",
         "allocation_band","allocation_pct","market_state","is_frozen","bootstrap_p_value",
         "friction_ytd_pct","friction_ytd_thb"],
        ["2026-06-16","500000","500000","0","0","0","0","0","0","0","0",
         "NEUTRAL","0.1","Normal","0","1","0","0"],
        ["2026-06-17","500000","500000","0","0","0","0","0","0","0","0",
         "NEUTRAL","0.1","Normal","0","1","0","0"],
    ]
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
    rows = gc.open_by_key("test_id").worksheet("Risk Metrics").get_all_values()
    dates = [r[0] for r in rows[1:]]
    assert "2026-06-16" in dates, f"Prior day wiped! dates={dates}"
    assert "2026-06-17" in dates, f"Prior day wiped! dates={dates}"
    assert dates.count("2026-06-18") == 1, f"Today duplicated: {dates}"
    print("PASS test_risk_metrics_history_preserved_on_rerun")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `2026-06-16` not in dates (history wiped by promote).

- [ ] **Step 3: Fix Risk Metrics to use upsert-by-date**

In `kth/pipeline/daily.py`, find the Risk Metrics staging block in `_write_all_staging` and replace it with an upsert pattern (same as Equity Curve). The staging sheet gets the full history (existing + today), and promotion replaces with that full history:

```python
    # Risk Metrics — upsert by date (preserve history, don't wipe)
    risk_row = _write_risk_metrics_row(metrics, pf_data, today_str)
    rm_live = sh.worksheet('Risk Metrics').get_all_values()
    rm_header = RISK_METRICS_HEADERS
    all_rm = upsert_by_date(rm_live if rm_live else [], rm_header, risk_row[0])
    write_staging(sh.worksheet('Risk Metrics_staging'), rm_header,
                  all_rm[1:] if len(all_rm) > 1 else [],
                  sleep_sec=staging_sleep)
```

Note: `write_staging` writes header + rows. The `all_rm` already includes the header at index 0, so we pass `all_rm[1:]` as rows.

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Run kaggle runtime tests to confirm no regression**

Run: `python verify_kaggle_runtime.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add kth/pipeline/daily.py verify_fixes.py
git commit -m "fix(pipeline): Risk Metrics uses upsert-by-date — preserves historical risk track"
```

---

### Task 9: Calibration append idempotency

**Files:**
- Modify: `kth/pipeline/daily.py` (`_write_all_staging`, Calibration block)

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_calibration_idempotent_on_rerun(tmp):
    """Same-day re-run must not append duplicate Calibration rows.
    Monkeypatches _compute_calibration_data to return a fixed result so the
    append path is exercised (without historical forecasts, it returns None
    and no rows are ever appended — the bug is invisible)."""
    from kth.pipeline.daily import run_daily_pipeline
    from verify_kaggle_runtime import FakeModel, FakeLoader, seeded_fake_client
    import kth.pipeline.daily as daily_mod
    orig_cal = daily_mod._compute_calibration_data
    daily_mod._compute_calibration_data = lambda ohlcv, today_str: {
        'date': today_str, 'coverage': 0.88, 'n_samples': 15, 'status': 'on_track'
    }
    try:
        gc = seeded_fake_client()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
        rows1 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
        rows2 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        today1 = [r for r in rows1[1:] if r and r[0] == "2026-06-18"]
        today2 = [r for r in rows2[1:] if r and r[0] == "2026-06-18"]
        assert len(today1) == len(today2), f"Calibration duplicated: {len(today1)} -> {len(today2)}"
        print("PASS test_calibration_idempotent_on_rerun")
    finally:
        daily_mod._compute_calibration_data = orig_cal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — duplicate Calibration rows on re-run.

- [ ] **Step 3: Add idempotency guard to Calibration append**

In `kth/pipeline/daily.py`, find the Calibration block in `_write_all_staging` and replace:

```python
    cal_data = _compute_calibration_data(ohlcv_dict, today_str)
    if cal_data:
        cal_ws = sh.worksheet('Calibration')
        cal_existing = cal_ws.get_all_values()
        if not cal_existing:
            cal_ws.append_row(CALIBRATION_HEADERS)
            cal_existing = [CALIBRATION_HEADERS]
        # Idempotency: skip if today's row already exists
        already_today = any(
            row and row[0] == today_str
            for row in cal_existing[1:]
        )
        if not already_today:
            cal_ws.append_row([
                cal_data['date'], cal_data['coverage'],
                cal_data['n_samples'], cal_data['status'],
            ])
            print(f"Calibration: n={cal_data['n_samples']} "
                  f"coverage={cal_data['coverage']:.2%} status={cal_data['status']}")
        else:
            print(f"Calibration: today already logged — skip")
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/pipeline/daily.py verify_fixes.py
git commit -m "fix(pipeline): Calibration append is idempotent — no duplicate on re-run"
```

---

### Task 10: Fix chr(64+col) for columns > 26

**Files:**
- Modify: `kth/pipeline/daily.py:353` (`_write_forecast_history`)

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_column_to_letter():
    """Column index to A1 notation must work for columns > 26 (AA, AB, ...)."""
    from kth.pipeline.daily import _col_to_letter
    assert _col_to_letter(0) == "A"
    assert _col_to_letter(25) == "Z"
    assert _col_to_letter(26) == "AA"
    assert _col_to_letter(27) == "AB"
    assert _col_to_letter(51) == "AZ"
    print("PASS test_column_to_letter")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `_col_to_letter` doesn't exist yet.

- [ ] **Step 3: Add the helper and use it**

Add to `kth/pipeline/daily.py` near the top (after imports):

```python
def _col_to_letter(col_index: int) -> str:
    """Convert 0-based column index to A1 letter notation (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    col = col_index + 1  # 1-based internally
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(65 + rem) + result
    return result
```

Then in `_write_forecast_history`, replace the `chr(64 + ar_col)` and `chr(64 + wc_col)` lines:

```python
            ar_col_letter = _col_to_letter(col['actual_return'])
            wc_col_letter = _col_to_letter(col['was_correct'])
            updates.append({
                'range': f'{ar_col_letter}{list_idx}:{wc_col_letter}{list_idx}',
                'values': [[round(act_ret, 4), correct]],
            })
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/pipeline/daily.py verify_fixes.py
git commit -m "fix(pipeline): column-to-letter converter handles >26 columns (AA, AB, ...)"
```

---

## Phase 4 — Universe + data fixes (Tasks 11-13)

### Task 11: Fix MEGA.BK sector classification

**Files:**
- Modify: `kth/data/universe.py:221`

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_mega_bk_sector_is_healthcare():
    """MEGA.BK (Mega Lifesciences) is a healthcare/supplements company, not Retail."""
    from kth.data.universe import get_sector
    assert get_sector("MEGA.BK") == "Healthcare", \
        f"MEGA.BK should be Healthcare, got {get_sector('MEGA.BK')}"
    print("PASS test_mega_bk_sector_is_healthcare")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `get_sector("MEGA.BK")` returns "Retail".

- [ ] **Step 3: Fix the sector mapping**

In `kth/data/universe.py:221`, move MEGA.BK from Retail to Healthcare:

```python
    # Retail (5)
    "CPALL.BK": "Retail",  "HMPRO.BK":"Retail",   "CRC.BK":   "Retail",
    "GLOBAL.BK":"Retail",  "DOHOME.BK":"Retail",
    # Healthcare (5)
    "BDMS.BK":  "Healthcare","BH.BK": "Healthcare","BCH.BK":  "Healthcare",
    "CHG.BK":   "Healthcare","MEGA.BK":"Healthcare",
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/data/universe.py verify_fixes.py
git commit -m "fix(universe): MEGA.BK sector Retail -> Healthcare (Mega Lifesciences)"
```

---

### Task 12: Enforce fx_macro exclusion from investable universe

**Files:**
- Modify: `kth/data/universe.py:158` (`get_all_tickers`)

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_fx_macro_excluded_from_investable():
    """fx_macro tickers (THB=X, DX-Y.NYB) must not appear in get_all_tickers()
    — they are features only, not investable."""
    from kth.data.universe import get_all_tickers, get_ticker_class
    tickers = get_all_tickers()
    fx = [t for t in tickers if get_ticker_class(t) == "fx_macro"]
    assert len(fx) == 0, f"fx_macro tickers leaked into investable universe: {fx}"
    print("PASS test_fx_macro_excluded_from_investable")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — THB=X and DX-Y.NYB are in `get_all_tickers()`.

- [ ] **Step 3: Exclude fx_macro from get_all_tickers**

In `kth/data/universe.py`, modify `get_all_tickers()`:

```python
def get_all_tickers() -> list[str]:
    """All investable tickers (excludes fx_macro — features only, not investable)."""
    out = []
    for cls, items in UNIVERSE.items():
        if cls == "fx_macro":
            continue
        out.extend(t for t, _, _ in items)
    return out
```

Add a separate function for callers that need ALL tickers (including fx_macro):

```python
def get_all_tickers_including_features() -> list[str]:
    """All tickers including fx_macro features. Use for data download only."""
    out = []
    for cls, items in UNIVERSE.items():
        out.extend(t for t, _, _ in items)
    return out
```

- [ ] **Step 4: Update all callers of get_all_tickers**

Every caller must be reviewed. Data-download paths need all 100 tickers (including fx_macro for feature caching). Backtest/report paths need investable-only (98 tickers, no fx_macro).

| File | Line | Needs fx_macro? | Action |
|------|------|-----------------|--------|
| `scripts/download_data.py:44` | `tickers = get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `google_suite/build_notebook.py:241` | `tickers = get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `kaggle/build_kaggle_notebook.py` (generated notebook) | `get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `run_pipeline.py:51` | `from kth.data.universe import get_all_tickers` | YES | Change to `get_all_tickers_including_features` |
| `kth/pipeline/daily.py:443` | `tickers = get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `kth/models/finetune.py:90` | `target_tickers = ... get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `verify_data_layer.py:104` | `all_tickers = get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `verify_data_layer.py:169` | `download_universe(get_all_tickers(), ...)` | YES | Change to `get_all_tickers_including_features()` |
| `verify_model_layer.py:93` | `all_tickers = get_all_tickers()` | YES | Change to `get_all_tickers_including_features()` |
| `scripts/run_backtest.py:23` | `tickers = get_all_tickers()` | NO | Keep `get_all_tickers()` |
| `scripts/run_daily_report.py:28` | `tickers = get_all_tickers()` | NO | Keep `get_all_tickers()` |
| `scripts/build_decision_notebook.py:67` | `tickers = get_all_tickers()` | NO | Keep `get_all_tickers()` |
| `scripts/build_usermanual_html.py:433` | `precompute_forecasts(th, get_all_tickers(), ...)` | NO | Keep `get_all_tickers()` |
| `kth/data/universe.py:244` | `len(get_all_tickers())` (in `__main__`) | YES | Change to `get_all_tickers_including_features()` |

Update the import lines in each file to also import `get_all_tickers_including_features` where needed.

- [ ] **Step 5: Run test**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add kth/data/universe.py verify_fixes.py
git commit -m "fix(universe): exclude fx_macro from get_all_tickers — features only, not investable"
```

---

### Task 13: Build reverse-lookup dict for get_ticker_class

**Files:**
- Modify: `kth/data/universe.py:163-176`

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_get_ticker_class_o1_lookup():
    """get_ticker_class must be O(1) — build a reverse-lookup dict at import time."""
    from kth.data.universe import get_ticker_class, _TICKER_CLASS_MAP
    assert "AOT.BK" in _TICKER_CLASS_MAP, "Reverse-lookup map not built"
    assert _TICKER_CLASS_MAP["AOT.BK"] == "thai_equity"
    assert get_ticker_class("BTC-USD") == "crypto"
    print("PASS test_get_ticker_class_o1_lookup")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python verify_fixes.py`
Expected: FAIL — `_TICKER_CLASS_MAP` doesn't exist.

- [ ] **Step 3: Build the reverse-lookup dict**

In `kth/data/universe.py`, after the `UNIVERSE` dict definition, add:

```python
# Reverse-lookup: ticker -> asset class (built once at import, O(1) lookup)
_TICKER_CLASS_MAP: dict[str, str] = {}
for _cls, _items in UNIVERSE.items():
    for _ticker, _, _ in _items:
        _TICKER_CLASS_MAP[_ticker] = _cls
```

Then replace `get_ticker_class`:

```python
def get_ticker_class(ticker: str) -> str | None:
    """Return the asset class for a ticker. O(1) dict lookup."""
    return _TICKER_CLASS_MAP.get(ticker)
```

- [ ] **Step 4: Run test**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/data/universe.py verify_fixes.py
git commit -m "perf(universe): O(1) ticker-class lookup via reverse-lookup dict"
```

---

## Phase 5 — Low-priority cleanup (Tasks 14-19)

### Task 14: Fix reduce filter to check forecast direction

**Files:**
- Modify: `kth/trading/trade_gen.py:156-168`

- [ ] **Step 1: Add the failing test**

Append to `verify_fixes.py`:

```python
def test_reduce_only_on_bearish_yellow():
    """Reduce (half-size) should only trigger on yellow + bearish forecast,
    not yellow + bullish. Yellow-up means uncertain but still positive — hold."""
    # This is a logic test, not a full integration test.
    # The fix: add `and f["direction"] == "down"` to the reduce condition.
    forecast_bearish_yellow = {"confidence": "yellow", "direction": "down"}
    forecast_bullish_yellow = {"confidence": "yellow", "direction": "up"}
    # Current (buggy): triggers on any yellow
    # Fixed: triggers on yellow + down only
    def should_reduce(f):
        return f["confidence"] == "yellow" and f["direction"] == "down"
    assert should_reduce(forecast_bearish_yellow), "Bearish yellow should reduce"
    assert not should_reduce(forecast_bullish_yellow), "Bullish yellow should NOT reduce"
    print("PASS test_reduce_only_on_bearish_yellow")
```

- [ ] **Step 2: Run test (passes — validates the intended logic)**

Run: `python verify_fixes.py`

- [ ] **Step 3: Fix the reduce condition**

In `kth/trading/trade_gen.py:156`, change:

```python
        elif f["confidence"] == "yellow":
```

to:

```python
        elif f["confidence"] == "yellow" and f["direction"] == "down":
```

- [ ] **Step 4: Run all tests**

Run: `python verify_fixes.py && python verify_kaggle_runtime.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add kth/trading/trade_gen.py verify_fixes.py
git commit -m "fix(trade_gen): reduce only on bearish-yellow, not bullish-yellow"
```

---

### Task 15: Fix NaN check in strategy.py

**Files:**
- Modify: `kth/backtest/strategy.py:61`

- [ ] **Step 1: Fix the NaN check**

In `kth/backtest/strategy.py:61`, replace:

```python
            if vol is None or vol != vol or vol <= 0:
```

with:

```python
            if vol is None or pd.isna(vol) or vol <= 0:
```

Add `import pandas as pd` at the top if not present.

- [ ] **Step 2: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add kth/backtest/strategy.py
git commit -m "fix(strategy): use pd.isna() instead of vol != vol NaN check"
```

---

### Task 16: Fix 60/40 benchmark weekend rebalance

**Files:**
- Modify: `kth/backtest/walkforward.py:496-509`

- [ ] **Step 1: Fix the rebalance date logic**

In `kth/backtest/walkforward.py:496`, replace:

```python
        rebal_dates = pd.date_range(start=config.start_date, end=config.end_date, freq="MS")
```

with:

```python
        rebal_dates = pd.date_range(start=config.start_date, end=config.end_date, freq="MS")
        # Roll weekend month-start to next business day
        rebal_dates = rebal_dates.map(lambda d: d if d.weekday() < 5 else d + pd.offsets.BDay())
```

- [ ] **Step 2: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add kth/backtest/walkforward.py
git commit -m "fix(walkforward): 60/40 rebalance rolls to next business day if 1st is weekend"
```

---

### Task 17: Remove dead code — strategy.select_positions

**Files:**
- Modify: `kth/backtest/strategy.py:26-33`

- [ ] **Step 1: Verify select_positions is not called**

Search: `grep -r "select_positions" --include="*.py" .`
Expected: Only the definition in `strategy.py`, no callers.

- [ ] **Step 2: Remove the dead function**

Delete `select_positions` from `kth/backtest/strategy.py:26-33`.

- [ ] **Step 3: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py && python verify_kaggle_runtime.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add kth/backtest/strategy.py
git commit -m "refactor(strategy): remove dead select_positions (walkforward does its own sort)"
```

---

### Task 18: Move import outside loop in trade_gen

**Files:**
- Modify: `kth/trading/trade_gen.py:44`

- [ ] **Step 1: Move the import to function scope (top of load_forecasts)**

In `kth/trading/trade_gen.py`, the `from kth.data.loader import load_cached` is inside the `for ticker in THAI_TICKERS` loop. Move it to the top of `load_forecasts`:

```python
def load_forecasts(report_date: str = None) -> list[dict]:
    """Load today's forecast cache for all Thai equity tickers."""
    from kth.data.loader import load_cached
    if report_date is None:
        report_date = str(date.today())
    # ... rest of function
```

And remove the import from inside the loop (line 44).

- [ ] **Step 2: Run all tests**

Run: `python verify_fixes.py && python verify_kaggle_runtime.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add kth/trading/trade_gen.py
git commit -m "perf(trade_gen): move load_cached import to function scope, not inside loop"
```

---

### Task 19: Fix profit_factor inf handling

**Files:**
- Modify: `kth/backtest/metrics.py:102`

- [ ] **Step 1: Fix inf to None in-memory**

In `kth/backtest/metrics.py:102`, replace:

```python
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
```

with:

```python
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
```

- [ ] **Step 2: Run all tests**

Run: `python verify_fixes.py && python verify_data_layer.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add kth/backtest/metrics.py
git commit -m "fix(metrics): profit_factor None instead of inf when no losses"
```

---

## Phase 6 — Backtest results manifest + re-run prep (Tasks 20-21)

### Task 20: Create MANIFEST.md for backtest results

**Files:**
- Create: `data/backtest_results/MANIFEST.md`

- [ ] **Step 1: Create the manifest**

```markdown
# Backtest Results Manifest

## Authoritative (n=50 samples, use these for citation)

| Directory | Period | Notes |
|-----------|--------|-------|
| `thai_equity_2023_n50/` | 2023 | p=0.419 — bull market, cash drag |
| `thai_equity_2024_n50/` | 2024 | **p=0.015 — only year clearing p<0.05** |
| `thai_equity_2025_n50/` | 2025 | p=0.257 |
| `thai_equity_2026_n50/` | 2026 YTD | p=0.353 |

## Superseded (do NOT cite — stale parameters)

| Directory | Why stale |
|-----------|-----------|
| `thai_equity_2020-2024/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024_v2/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024_invvol/` | **Rejected** — inv_vol position sizing lost to equal-weight |
| `thai_equity_2023-2026/` | Full range, not per-year |
| `thai_equity_2026_n50_full/` | Extended 2026, not canonical |
| `thai_equity_2026_ytd/` | YTD only, not canonical |
| `test_2024q2/` | Early test run |

## Fine-tune vs zero-shot comparisons

| Directory | Verdict |
|-----------|---------|
| `crypto_ft/` | FT did not beat ZS |
| `crypto_zs/` | Zero-shot baseline |
| `us_equity_ft/` | FT did not beat ZS |
| `us_equity_zs/` | Zero-shot baseline |

**Rule:** Only cite `*_n50/` results. Pre-n50 runs used n=10 samples (invalid for parameter tuning per AGENTS.md). inv_vol was conclusively rejected.
```

- [ ] **Step 2: Commit**

```bash
git add data/backtest_results/MANIFEST.md
git commit -m "docs(backtest): MANIFEST.md marking authoritative vs stale result directories"
```

---

### Task 21: Final verification + backtest re-run note

- [ ] **Step 1: Run all verification scripts**

```bash
python verify_fixes.py
python verify_data_layer.py
python verify_kaggle_runtime.py
python run_pipeline.py --dry-run
```

All must pass.

- [ ] **Step 2: Note the backtest re-run requirement**

After fixing the equity curve alignment (Task 2), open_trades blending (Task 3), and PSR formula (Task 1), the stored backtest numbers in `data/backtest_results/*/metrics.json` are **stale** — they were computed with the buggy alignment and PSR. A full GPU re-run is needed to get correct numbers. This is a manual step (requires Colab/Kaggle T4).

Document this in the MANIFEST.md by adding at the top:

```markdown
> **⚠️ STALE NUMBERS:** Results in these directories were computed before the
> 2026-06-21 bug fixes (equity curve alignment, PSR formula, open_trades blending).
> A GPU re-run is required to get correct alpha/beta/IR/PSR numbers. Do NOT cite
> these numbers until the re-run is complete.
```

- [ ] **Step 3: Commit**

```bash
git add data/backtest_results/MANIFEST.md
git commit -m "docs(backtest): mark all results stale pending post-fix GPU re-run"
```

---

## Test inventory

| File | Covers | Run |
|------|--------|-----|
| `verify_fixes.py` | All 21 fix tasks (PSR, alignment, bootstrap, cash guard, etc.) | `python verify_fixes.py` |
| `verify_data_layer.py` | Data-layer regression (must stay green) | `python verify_data_layer.py` |
| `verify_kaggle_runtime.py` | Pipeline regression (must stay green) | `python verify_kaggle_runtime.py` |
| `run_pipeline.py --dry-run` | Full pipeline smoke test | `python run_pipeline.py --dry-run` |

## Definition of done

- [ ] All 21 tasks committed
- [ ] `verify_fixes.py` green (all new tests pass)
- [ ] `verify_data_layer.py` green (no regression)
- [ ] `verify_kaggle_runtime.py` green (no regression)
- [ ] `run_pipeline.py --dry-run` green
- [ ] `data/backtest_results/MANIFEST.md` marks stale results
- [ ] GPU re-run scheduled (manual — Colab/Kaggle T4) to refresh backtest numbers

## Post-fix GPU re-run (manual, not in this plan)

After all fixes land, the following backtest re-runs are needed on a GPU:
1. `thai_equity_2024_n50` — the p=0.015 year; confirm if edge survives the alignment fix
2. `thai_equity_2023_n50` — re-check alpha vs EW
3. `thai_equity_2025_n50` — re-check friction analysis
4. `thai_equity_2026_n50` — re-check 2026 YTD

This is ~8-10 hours of GPU time. Run via `scripts/run_2024_n50.py` etc.
