# Quant Review Remediation — Phase 1 (No GPU) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the 29 no-GPU issues from the quant/trader/engineer review — code correctness, refactors, docs, and testing infrastructure. No Kronos model inference, no network, no GPU.

**Architecture:** Sequential tasks, each independently committable. Tasks 1-2 use the existing `verify_fixes.py` runner (pre-pytest). Task 3 introduces pytest, after which all new tests go in `tests/`. Tasks 4-15 build on the pytest foundation. Tasks 16-19 are documentation-only.

**Tech Stack:** Python 3.11, pandas, numpy, scipy, pytest (added in Task 3), ruff (added in Task 3), parquet.

**Branch strategy:** Work on `main`. Commit after every task. Each task lists the exact files to stage.

**Prerequisite:** `pip install -e . && pip install -r requirements.txt` before starting.

---

## File Structure

**New files:**
- `kth/utils/model_slug.py` — extracted slug helper (L14)
- `kth/data/versioning.py` — manifest write/verify (C6)
- `tests/conftest.py`, `tests/test_*.py` — pytest suite (C5)
- `docs/adr/0001-equal-weight-position-sizing.md`
- `docs/adr/0002-zero-shot-only.md`
- `docs/adr/0003-no-portfolio-optimization.md`

**Modified files (no GPU):**
- `kth/backtest/metrics.py` — L1, L6, L7, L8, L13, M8
- `kth/backtest/strategy.py` — L4
- `kth/backtest/walkforward.py` — L2, L3, L12, H3, M6
- `kth/data/universe.py` — H3
- `kth/data/loader.py` — C6
- `kth/trading/portfolio.py` — L5, L9, L10, L11
- `kth/trading/trade_gen.py` — L14, H3
- `scripts/dashboard.py` — M7
- `pyproject.toml` — dev deps
- `README.md`, `PROJECT_STRUCTURE.md`, `CONTEXT.md` — docs

---

## Task 1: Quick metric code fixes (Tier 1 batch)

**Files:**
- Modify: `kth/backtest/metrics.py` (lines 102, 119, 141-158, 330-336)
- Test: `verify_fixes.py` (append)

- [ ] **Step 1: Fix `compute_bootstrap_pvalue` docstring (L7)**

In `kth/backtest/metrics.py:330-336`, replace the docstring:

```python
def compute_bootstrap_pvalue(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Centered bootstrap p-value for live paper-trading alpha.
    Under H0 (active mean = 0), center the active returns by subtracting the
    observed mean, resample with replacement n_bootstrap times, and count the
    fraction of resampled means >= observed mean. Lower p = stronger edge.
    Returns {'pvalue': float|None, 'n_bootstrap': int, 'n_obs': int, 'significant': bool}
    """
```

- [ ] **Step 2: Fix `profit_factor` to return `float('inf')` not `None` (L8)**

In `kth/backtest/metrics.py:102`, change:

```python
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
```

Confirm `BacktestResult.save` at `walkforward.py:173` already converts inf to None for JSON via the `math.isinf` check. Leave the in-memory value as `inf`.

- [ ] **Step 3: Fix `compute_psr` skew/kurt consistency (L13)**

In `kth/backtest/metrics.py:141-158`, replace the manual moments with scipy:

```python
    from scipy.stats import norm, skew, kurtosis
    returns = daily_returns.dropna().values
    if len(returns) < 2:
        return 0.0
    std = daily_returns.std()
    if std == 0 or pd.isna(std):
        return 0.0
    sr_daily = float(daily_returns.mean() / std)
    benchmark_daily = benchmark_sr / np.sqrt(periods_per_year)
    T = len(returns)
    skew_val = float(skew(returns, bias=False))
    kurt_val = float(kurtosis(returns, bias=False))  # excess kurtosis
    denom_sq = 1 - skew_val * sr_daily + (kurt_val - 1) / 4 * sr_daily ** 2
    if denom_sq <= 0:
        return 0.5 if sr_daily > benchmark_daily else 0.0
    denominator = np.sqrt(denom_sq)
    z = (sr_daily - benchmark_daily) * np.sqrt(T - 1) / denominator
    return float(norm.cdf(z))
```

- [ ] **Step 4: Mark `avg_holding_period` stub (L1)**

In `kth/backtest/metrics.py:119`:

```python
        "avg_holding_period": 0.0,  # TODO Task 6: compute from FIFO-matched trades
```

- [ ] **Step 5: Append regression tests to `verify_fixes.py`**

```python
# ---- Task 1 fixes ----
def test_psr_uses_scipy_skew_kurtosis():
    import inspect
    from kth.backtest import metrics as m
    src = inspect.getsource(m.compute_psr)
    assert "from scipy.stats import" in src, "compute_psr must import scipy.stats"
    assert "bias=False" in src, "compute_psr must use bias=False"

def test_profit_factor_inf_when_no_losses():
    import pandas as pd
    trades = pd.DataFrame({"gross_return": [0.1, 0.2, 0.05], "friction_cost": [0,0,0]})
    from kth.backtest.metrics import compute_trade_metrics
    m = compute_trade_metrics(trades)
    assert m["profit_factor"] == float("inf"), f"Expected inf, got {m['profit_factor']}"

def test_bootstrap_docstring_says_centered():
    from kth.backtest.metrics import compute_bootstrap_pvalue
    assert "centered" in compute_bootstrap_pvalue.__doc__.lower()
    assert "shuffles" not in compute_bootstrap_pvalue.__doc__.lower()

def test_psr_high_sharpe_finite_after_scipy_fix():
    rng = np.random.default_rng(99)
    returns = pd.Series(rng.normal(0.003, 0.008, 300))
    from kth.backtest.metrics import compute_psr
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert np.isfinite(psr) and 0.0 <= psr <= 1.0
    print("PASS test_psr_high_sharpe_finite_after_scipy_fix")
```

- [ ] **Step 6: Run tests**

```bash
python verify_fixes.py
```
Expected: all existing + 4 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add kth/backtest/metrics.py verify_fixes.py
git commit -m "fix(metrics): scipy skew/kurtosis, inf profit_factor, docstring (L1,L7,L8,L13)"
```

---

## Task 2: Centralize friction lookup (H3)

**Files:**
- Modify: `kth/data/universe.py` (add `get_friction`)
- Modify: `kth/backtest/walkforward.py:350-352, 394-396`
- Modify: `kth/trading/portfolio.py:515-519`
- Modify: `kth/trading/trade_gen.py:57-59, 99-103`
- Test: `verify_fixes.py`

- [ ] **Step 1: Add `get_friction()` to `universe.py`**

At the end of `kth/data/universe.py` (after `get_sector`):

```python
_DEFAULT_FRICTION = {"commission_oneway": 0.003, "slippage_oneway": 0.001}


def get_friction(ticker: str) -> dict[str, float]:
    """Return the FRICTION dict for a ticker's asset class. Single source of truth."""
    cls = get_ticker_class(ticker)
    if cls is None:
        return dict(_DEFAULT_FRICTION)
    return FRICTION.get(cls, dict(_DEFAULT_FRICTION))


def get_one_way_friction_rate(ticker: str) -> float:
    """One-way friction rate (commission + slippage) for a ticker."""
    f = get_friction(ticker)
    return f["commission_oneway"] + f["slippage_oneway"]
```

- [ ] **Step 2: Replace fallbacks in `walkforward.py`**

At lines 350-352 and 394-396, replace each:

```python
                cls = get_ticker_class(t) or "us_equity"
                frict = FRICTION.get(cls, {"commission_oneway": 0.003, "slippage_oneway": 0.001})
```

with:

```python
                frict = get_friction(t)
```

Add `get_friction` to the import at line 217.

- [ ] **Step 3: Replace in `portfolio.py:515-519`**

```python
def _one_way_friction_rate(ticker: str) -> float:
    from kth.data.universe import get_one_way_friction_rate
    return get_one_way_friction_rate(ticker)
```

- [ ] **Step 4: Replace in `trade_gen.py`**

Add import `from kth.data.universe import get_friction, get_one_way_friction_rate`. At line 57-59:

```python
            fric = get_friction(ticker)
            friction_rt = fric["commission_oneway"] * 2 + fric["slippage_oneway"] * 2
```

At line 99-103, replace `_one_way_friction` body:

```python
def _one_way_friction(ticker: str) -> float:
    return get_one_way_friction_rate(ticker)
```

- [ ] **Step 5: Append tests to `verify_fixes.py`**

```python
# ---- Task 2: centralized friction ----
def test_get_friction_known_ticker():
    from kth.data.universe import get_friction, get_one_way_friction_rate
    f = get_friction("PTT.BK")
    assert f["commission_oneway"] == 0.00168
    assert get_one_way_friction_rate("PTT.BK") == 0.00268

def test_get_friction_fallback_unknown():
    from kth.data.universe import get_friction
    f = get_friction("UNKNOWN.TICKER")
    assert f["commission_oneway"] == 0.003

def test_no_inline_friction_fallbacks_remain():
    from pathlib import Path
    for f in ["kth/backtest/walkforward.py", "kth/trading/portfolio.py", "kth/trading/trade_gen.py"]:
        text = Path(f).read_text()
        assert '{"commission_oneway":' not in text, f"{f} still has inline friction fallback"
```

- [ ] **Step 6: Run + commit**

```bash
python verify_fixes.py && git add kth/data/universe.py kth/backtest/walkforward.py kth/trading/portfolio.py kth/trading/trade_gen.py verify_fixes.py && git commit -m "fix(friction): single source via universe.get_friction (H3)"
```

---

## Task 3: Add pytest + port verify scripts (C5)

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`, `tests/test_metrics.py`, `tests/test_walkforward.py`, `tests/test_portfolio.py`, `tests/test_universe.py`, `tests/test_kaggle_runtime.py`

- [ ] **Step 1: Add dev deps to `pyproject.toml`**

Append:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5", "mypy>=1.10"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]

[tool.mypy]
ignore_missing_imports = true
```

- [ ] **Step 2: Install**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
"""Shared fixtures for the Kronos-TH test suite."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def synthetic_returns():
    rng = np.random.default_rng(42)
    return pd.Series(rng.normal(0.002, 0.012, 252))


@pytest.fixture
def synthetic_equity_curve(synthetic_returns):
    cum = (1 + synthetic_returns).cumprod()
    return pd.Series(cum.values, index=pd.date_range("2024-01-01", periods=len(cum), freq="B"))


@pytest.fixture
def synthetic_trades():
    return pd.DataFrame({
        "gross_return": [0.05, 0.03, -0.02, 0.08, 0.01, -0.04, 0.06, -0.01, 0.02, -0.03],
        "friction_cost": [0.001] * 10,
        "size_pct": [1000.0] * 10,
        "ticker": ["AAPL"] * 10,
    })


@pytest.fixture
def tmp_cache(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    return d
```

- [ ] **Step 4: Port `verify_fixes.py` tests into `tests/test_metrics.py`**

Copy each `test_*` function from `verify_fixes.py` (PSR, bootstrap CI, t-test, trade metrics) and the 4 Task 1 tests + 3 Task 2 tests. Drop `print("PASS ...")` lines. Keep asserts.

- [ ] **Step 5: Port walkforward tests into `tests/test_walkforward.py`**

Port `test_equity_curve_index_is_mark_day_not_signal_day`, `test_open_trades_blends_on_rebalance`, `test_open_trades_blend_logic_correct` from `verify_fixes.py`.

- [ ] **Step 6: Port portfolio tests into `tests/test_portfolio.py`**

Port any FIFO/portfolio tests from `verify_fixes.py`.

- [ ] **Step 7: Create `tests/test_universe.py`** with the Task 2 friction tests.

- [ ] **Step 8: Port `verify_kaggle_runtime.py` (19 tests) into `tests/test_kaggle_runtime.py`**

- [ ] **Step 9: Run pytest**

```bash
pytest -q
```
Expected: ~45-50 tests pass.

- [ ] **Step 10: Run ruff on touched files**

```bash
ruff check kth/backtest/metrics.py kth/data/universe.py tests/
```
Fix only warnings in files you touched. Do not mass-reformat.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml tests/
git commit -m "test: add pytest + port verify scripts into tests/ (C5)"
```

---

## Task 4: Extract `_model_slug` (L14)

**Files:**
- Create: `kth/utils/model_slug.py`
- Modify: `kth/backtest/walkforward.py:46-50` (remove local def, import new)
- Modify: `kth/trading/trade_gen.py:14` (import from new location)

- [ ] **Step 1: Create `kth/utils/model_slug.py`**

```python
"""Filesystem-safe model name slug for cache directory naming."""
from __future__ import annotations


def model_slug(model_name: str) -> str:
    """'NeoQuasar/Kronos-small@a3f1c2d' -> 'NeoQuasar_Kronos-small-a3f1c2d'"""
    return model_name.replace("/", "_").replace("@", "-").replace("\\", "_")
```

- [ ] **Step 2: Update `walkforward.py`**

Remove the local `_model_slug` function (lines 46-50). Add import:

```python
from kth.utils.model_slug import model_slug as _model_slug
```

- [ ] **Step 3: Update `trade_gen.py:14`**

```python
from kth.utils.model_slug import model_slug as _model_slug
```

- [ ] **Step 4: Test + commit**

```bash
pytest -q tests/ && git add kth/utils/model_slug.py kth/backtest/walkforward.py kth/trading/trade_gen.py && git commit -m "refactor: extract model_slug to kth/utils (L14)"
```

---

## Task 5: Remove dead code + fix misnamed fields (L10, L11, L12)

**Files:**
- Modify: `kth/backtest/walkforward.py:40`
- Modify: `kth/trading/portfolio.py:667, 476-494, 689-697`

- [ ] **Step 1: Remove dead `trading_calendar` (L12)**

Delete line 40 in `walkforward.py`:
```python
    trading_calendar: str = "NYSE"
```

- [ ] **Step 2: Rename `weeks_active` → `distinct_trade_dates` (L10)**

In `portfolio.py:667`:

```python
    unique_dates = sorted(set(t["date"] for t in trades))
    distinct_trade_dates = len(unique_dates)
    round_trips = sum(1 for t in trades if t["action"] in ("exit", "sell"))
```

At line 678:
```python
    all_ok = (distinct_trade_dates >= 20 and round_trips >= 10 and win_rate_ok
              and sharpe_ok and dd_ok and rebalance_count >= 3)
```

In the return dict (line 683+):
```python
        "distinct_trade_dates": distinct_trade_dates,
```

In the `checks` dict (line 689+):
```python
            "20_distinct_dates": distinct_trade_dates >= 20,
```

- [ ] **Step 3: Fix `_compute_market_state` (L11)**

Replace `portfolio.py:476-494`:

```python
def _compute_market_state() -> str:
    """Returns 'Normal' | 'Elevated' | 'Turmoil' | 'Unknown' (no data)."""
    try:
        from kth.trading.trade_gen import load_forecasts
        forecasts = load_forecasts()
        if not forecasts:
            return "Unknown"
        bands = [f["band_width"] for f in forecasts if f.get("band_width")]
        red_count = sum(1 for f in forecasts if f.get("confidence") == "red")
        if not bands:
            return "Unknown"
        median_band = float(pd.Series(bands).median())
        if median_band > 0.30 or red_count > 30:
            return "Turmoil"
        if median_band > 0.20 or red_count > 15:
            return "Elevated"
        return "Normal"
    except Exception as e:
        import logging
        logging.warning(f"_compute_market_state failed: {e}")
        return "Unknown"
```

- [ ] **Step 4: Add test**

In `tests/test_portfolio.py`:

```python
def test_market_state_unknown_when_no_forecasts(monkeypatch):
    monkeypatch.setattr("kth.trading.trade_gen.load_forecasts", lambda: [])
    from kth.trading.portfolio import _compute_market_state
    assert _compute_market_state() == "Unknown"
```

- [ ] **Step 5: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/walkforward.py kth/trading/portfolio.py tests/test_portfolio.py && git commit -m "fix: dead trading_calendar, rename weeks_active, Unknown state (L10,L11,L12)"
```

---

## Task 6: Compute `avg_holding_period` from FIFO (L1)

**Files:**
- Modify: `kth/backtest/metrics.py:79-124`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Add helper + wire it in**

In `kth/backtest/metrics.py`, add before `compute_trade_metrics`:

```python
def _compute_avg_holding_period(trades: pd.DataFrame) -> float:
    """FIFO-match buy->sell per ticker, return mean holding period in days."""
    from collections import deque, defaultdict
    if trades.empty or "date" not in trades.columns:
        return 0.0
    buys: dict = defaultdict(deque)
    holding_days: list[float] = []
    for _, t in trades.iterrows():
        ticker = t["ticker"]
        direction = str(t.get("direction", "")).lower()
        if direction == "buy":
            buys[ticker].append(pd.Timestamp(t["date"]))
        elif direction in ("sell", "exit"):
            if buys[ticker]:
                buy_date = buys[ticker].popleft()
                holding_days.append((pd.Timestamp(t["date"]) - buy_date).days)
    if not holding_days:
        return 0.0
    return float(np.mean(holding_days))
```

In `compute_trade_metrics`, replace `"avg_holding_period": 0.0,` with:

```python
        "avg_holding_period": _compute_avg_holding_period(trades),
```

- [ ] **Step 2: Add tests**

In `tests/test_metrics.py`:

```python
def test_avg_holding_period_fifo():
    import pandas as pd
    from kth.backtest.metrics import _compute_avg_holding_period
    trades = pd.DataFrame({
        "ticker": ["A", "A", "A", "B", "B"],
        "direction": ["buy", "buy", "sell", "buy", "sell"],
        "date": ["2024-01-01", "2024-01-10", "2024-01-15", "2024-01-05", "2024-01-20"],
        "size_pct": [1.0]*5, "friction_cost": [0]*5, "gross_return": [0]*5,
    })
    avg = _compute_avg_holding_period(trades)
    assert abs(avg - 14.5) < 0.1, f"Expected 14.5, got {avg}"

def test_avg_holding_period_no_round_trips():
    import pandas as pd
    from kth.backtest.metrics import _compute_avg_holding_period
    trades = pd.DataFrame({
        "ticker": ["A"], "direction": ["buy"], "date": ["2024-01-01"],
        "size_pct": [1.0], "friction_cost": [0], "gross_return": [0],
    })
    assert _compute_avg_holding_period(trades) == 0.0
```

- [ ] **Step 3: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/metrics.py tests/test_metrics.py && git commit -m "fix(metrics): compute avg_holding_period from FIFO (L1)"
```

---

## Task 7: Fix `compute_calibration` to scan cache dirs (L6)

**Files:**
- Modify: `kth/backtest/metrics.py:398-451`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Replace `compute_calibration`**

```python
def compute_calibration(
    forecast_cache_dir,
    raw_data_dir,
    tickers: list,
    pred_len: int = 20,
    lookback_days: int = 60,
) -> dict:
    """P5/P95 coverage via actual cached forecast dirs (not calendar days)."""
    from pathlib import Path as _P
    from kth.data.loader import load_cached

    cache_root = _P(forecast_cache_dir)
    if not cache_root.exists():
        return {"coverage": None, "n_samples": 0, "status": "insufficient_data"}

    date_dirs = sorted(
        (d for d in cache_root.iterdir() if d.is_dir() and d.name[:4].isdigit()),
        key=lambda d: d.name,
        reverse=True,
    )[:lookback_days]

    hits, total = 0, 0
    for dd in date_dirs:
        try:
            fc_date = pd.Timestamp(dd.name)
        except ValueError:
            continue
        actual_date = fc_date + pd.Timedelta(days=pred_len)

        for ticker in tickers:
            safe = ticker.replace("^", "_").replace("=", "_")
            fc_path = dd / f"{safe}.parquet"
            if not fc_path.exists():
                continue
            try:
                fc = pd.read_parquet(fc_path)
                p5 = float(fc["p5"].iloc[-1])
                p95 = float(fc["p95"].iloc[-1])
                price_df = load_cached(ticker, cache_dir=str(raw_data_dir))
                price_df = price_df.set_index("timestamps")
                price_df.index = pd.to_datetime(price_df.index)
                if actual_date not in price_df.index:
                    idx = price_df.index.get_indexer([actual_date], method="ffill")[0]
                    if idx < 0:
                        continue
                else:
                    idx = price_df.index.get_loc(actual_date)
                actual_close = float(price_df.iloc[idx]["close"])
                total += 1
                if p5 <= actual_close <= p95:
                    hits += 1
            except Exception:
                continue

    if total < 10:
        return {"coverage": None, "n_samples": total, "status": "insufficient_data"}
    coverage = hits / total
    return {
        "coverage": round(coverage, 3),
        "n_samples": total,
        "status": "overconfident" if coverage > 0.95 else "ok",
    }
```

- [ ] **Step 2: Test**

```python
def test_calibration_no_cache_returns_insufficient(tmp_path):
    from kth.backtest.metrics import compute_calibration
    r = compute_calibration(str(tmp_path / "nope"), str(tmp_path), ["AAPL"])
    assert r["status"] == "insufficient_data"
    assert r["n_samples"] == 0
```

- [ ] **Step 3: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/metrics.py tests/test_metrics.py && git commit -m "fix(metrics): compute_calibration scans cache dirs not calendar days (L6)"
```

---

## Task 8: Consolidate hysteresis into `strategy.py` (L4)

**Files:**
- Modify: `kth/backtest/strategy.py`
- Modify: `kth/backtest/walkforward.py:286-301`
- Test: `tests/test_walkforward.py`

- [ ] **Step 1: Add `apply_hysteresis` to `strategy.py`**

```python
def apply_hysteresis(
    raw_signals: dict[str, float],
    holdings: dict[str, float],
    holding_days: dict[str, int],
    config_long_threshold: float,
    config_entry_buffer: float,
    config_min_holding_days: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply entry/exit hysteresis. Returns (signals, signals_for_ranking)."""
    signals: dict[str, float] = {}
    signals_for_ranking: dict[str, float] = {}
    for t, sig in raw_signals.items():
        if t in holdings and holdings[t] > 0:
            if (sig < config_long_threshold - config_entry_buffer
                    and holding_days.get(t, 0) >= config_min_holding_days):
                signals[t] = 0
            else:
                signals[t] = 1
                signals_for_ranking[t] = sig
        else:
            if sig > config_long_threshold + config_entry_buffer:
                signals[t] = sig
                signals_for_ranking[t] = sig
    return signals, signals_for_ranking
```

- [ ] **Step 2: Replace inline logic in `walkforward.py:286-301`**

```python
        raw_signals = compute_signals(forecasts, last_closes, config.long_threshold, config.pred_len)
        from kth.backtest.strategy import apply_hysteresis
        signals, signals_for_ranking = apply_hysteresis(
            raw_signals, holdings_units, holding_days,
            config.long_threshold, config.entry_buffer, config.min_holding_days,
        )
```

- [ ] **Step 3: Test**

```python
def test_hysteresis_entry_exit_asymmetry():
    from kth.backtest.strategy import apply_hysteresis
    raw = {"A": 0.025, "B": 0.015, "C": 0.008}
    sigs, ranking = apply_hysteresis(raw, {}, {}, 0.01, 0.005, 5)
    assert "A" in sigs and sigs["A"] == 0.025
    assert "B" not in sigs and "C" not in sigs

    raw2 = {"A": 0.003}
    sigs2, ranking2 = apply_hysteresis(raw2, {"A": 100}, {"A": 2}, 0.01, 0.005, 5)
    assert sigs2["A"] == 1
    assert "A" in ranking2

    sigs3, _ = apply_hysteresis(raw2, {"A": 100}, {"A": 6}, 0.01, 0.005, 5)
    assert sigs3["A"] == 0
```

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/strategy.py kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "refactor: consolidate hysteresis into strategy.apply_hysteresis (L4)"
```

---

## Task 9: Reject mixed crypto+equity ticker lists (L2)

**Files:**
- Modify: `kth/backtest/walkforward.py`
- Test: `tests/test_walkforward.py`

- [ ] **Step 1: Add validation helper**

Near `_get_calendar_for_tickers`:

```python
def _validate_single_calendar(tickers: list[str]) -> None:
    """Reject mixed crypto + non-crypto ticker lists."""
    from kth.data.universe import get_ticker_class
    classes = {get_ticker_class(t) for t in tickers}
    if "crypto" in classes and classes - {"crypto"}:
        non_crypto = classes - {"crypto"}
        raise ValueError(
            f"Refusing to run mixed-asset-class backtest: crypto + {non_crypto}. "
            f"Run separate backtests per asset class to keep calendars aligned."
        )
```

- [ ] **Step 2: Call it in `run_walkforward` (after eligible computed, ~line 239) and `precompute_forecasts` (after viable filter, ~line 91)**

```python
    _validate_single_calendar(eligible)
```

- [ ] **Step 3: Test**

```python
def test_mixed_class_rejected():
    from kth.backtest.walkforward import _validate_single_calendar
    with pytest.raises(ValueError, match="mixed-asset-class"):
        _validate_single_calendar(["BTC-USD", "AAPL"])

def test_single_crypto_ok():
    from kth.backtest.walkforward import _validate_single_calendar
    _validate_single_calendar(["BTC-USD", "ETH-USD"])

def test_single_equity_ok():
    from kth.backtest.walkforward import _validate_single_calendar
    _validate_single_calendar(["AAPL", "PTT.BK"])
```

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "fix(walkforward): reject mixed crypto+equity lists (L2)"
```

---

## Task 10: Rename OLS alpha (M8)

**Files:**
- Modify: `kth/backtest/metrics.py:293`
- Modify: consumers (find via grep)

- [ ] **Step 1: Find consumers**

```bash
rg "metrics\[.alpha.\]|metrics\.get\(.alpha." --type py
```

- [ ] **Step 2: Rename in `compute_metrics` output**

```python
        "alpha_vs_equal_weight": alpha,
```

- [ ] **Step 3: Update all consumers**

Replace `metrics["alpha"]` → `metrics["alpha_vs_equal_weight"]` and `metrics.get("alpha")` → `metrics.get("alpha_vs_equal_weight")` in each file found.

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add -A && git commit -m "fix(metrics): rename alpha -> alpha_vs_equal_weight (M8)"
```

---

## Task 11: Label p-values in dashboard (M7)

**Files:**
- Modify: `scripts/dashboard.py` (`/api/risk` handler)

- [ ] **Step 1: Locate the risk endpoint**

```bash
rg "api/risk|bootstrap_pvalue" scripts/dashboard.py
```

- [ ] **Step 2: Add labels to the response**

In the `/api/risk` handler, after the existing `bootstrap_pvalue` field, add:

```python
        "p_value_labels": {
            "live_bootstrap": {
                "value": bootstrap_pvalue["pvalue"],
                "label": "Live paper trading (centered bootstrap, accumulating)",
                "status": bootstrap_pvalue["significant"],
                "n_obs": bootstrap_pvalue["n_obs"],
                "interpretation": "Needs >=20 days. p<0.05 = edge confirmed; p>=0.15 = no confirmed edge.",
            },
            "historical_ttest": {
                "label": "Historical backtest (t-test, frozen in data/backtest_results/)",
                "interpretation": "Stored p-values from 2023-2026 n50 backtests. Never recalculated by dashboard.",
                "caveat": "Stored numbers are STALE pending 2026-06-21 bug-fix GPU re-run.",
            },
        },
```

- [ ] **Step 3: Commit**

```bash
git add scripts/dashboard.py && git commit -m "fix(dashboard): label live vs historical p-values (M7)"
```

---

## Task 12: Fix `_count_rebalances` + `_get_current_price` logging (L5, L9)

**Files:**
- Modify: `kth/trading/portfolio.py:102-109, 700-705`
- Test: `tests/test_portfolio.py`

- [ ] **Step 1: Improve `_get_current_price` (L5)**

```python
def _get_current_price(ticker: str) -> float | None:
    """Get latest close from cached data. Logs errors instead of swallowing."""
    import logging
    try:
        from kth.data.loader import load_cached
        df = load_cached(ticker)
        return float(df["close"].iloc[-1])
    except FileNotFoundError:
        logging.warning(f"_get_current_price: no cache for {ticker}")
        return None
    except Exception as e:
        logging.error(f"_get_current_price: corrupt cache for {ticker}: {e}")
        return None
```

- [ ] **Step 2: Improve `_count_rebalances` (L9)**

```python
def _count_rebalances(trades: list[dict]) -> int:
    """Count distinct dates with >=2 trade events (rebalance proxy)."""
    from collections import Counter
    date_counts = Counter(
        t["date"] for t in trades
        if t["action"] in ("exit", "sell", "reduce", "buy")
    )
    return sum(1 for c in date_counts.values() if c >= 2)
```

- [ ] **Step 3: Test**

```python
def test_count_rebalances_ignores_single_trade_days():
    from kth.trading.portfolio import _count_rebalances
    trades = [
        {"date": "2024-01-05", "action": "exit"},
        {"date": "2024-02-01", "action": "exit"}, {"date": "2024-02-01", "action": "buy"},
        {"date": "2024-03-10", "action": "buy"}, {"date": "2024-03-10", "action": "buy"},
    ]
    assert _count_rebalances(trades) == 2
```

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add kth/trading/portfolio.py tests/test_portfolio.py && git commit -m "fix(portfolio): log price errors, accurate rebalance count (L5, L9)"
```

---

## Task 13: Add data versioning manifest (C6)

**Files:**
- Create: `kth/data/versioning.py`
- Modify: `kth/data/loader.py` (call versioning on write)
- Test: `tests/test_versioning.py`

- [ ] **Step 1: Create `kth/data/versioning.py`**

```python
"""Data cache versioning — write + verify a manifest of per-ticker hashes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, date
from pathlib import Path


def _hash_parquet(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def write_manifest(cache_dir: Path, tickers: list[str]) -> dict:
    """Write manifest.json with per-ticker row count + SHA256 + date."""
    import pandas as pd
    cache_dir = Path(cache_dir)
    manifest = {
        "written_at": datetime.now().isoformat(),
        "download_date": str(date.today()),
        "tickers": {},
    }
    for ticker in tickers:
        safe = ticker.replace("^", "_").replace("=", "_")
        p = cache_dir / f"{safe}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        manifest["tickers"][ticker] = {
            "rows": len(df),
            "sha256_short": _hash_parquet(p),
            "last_date": str(df["timestamps"].iloc[-1]) if "timestamps" in df.columns else None,
        }
    out = cache_dir / "manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def verify_manifest(cache_dir: Path, strict: bool = False) -> dict:
    """Verify cached parquets match manifest.json."""
    cache_dir = Path(cache_dir)
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "mismatches": [], "missing": [],
                "error": "No manifest.json — run download_universe first"}
    with open(manifest_path) as f:
        manifest = json.load(f)
    mismatches, missing = [], []
    for ticker, meta in manifest["tickers"].items():
        safe = ticker.replace("^", "_").replace("=", "_")
        p = cache_dir / f"{safe}.parquet"
        if not p.exists():
            missing.append(ticker)
            continue
        actual_hash = _hash_parquet(p)
        if actual_hash != meta["sha256_short"]:
            mismatches.append(f"{ticker}: hash {actual_hash} != manifest {meta['sha256_short']}")
    result = {"ok": not (mismatches or missing), "mismatches": mismatches, "missing": missing}
    if strict and (mismatches or missing):
        raise RuntimeError(f"Data cache mismatch: {result}")
    return result
```

- [ ] **Step 2: Call `write_manifest` at end of `download_universe` in `loader.py`**

At the end of `download_universe`, after all tickers are cached:

```python
    from kth.data.versioning import write_manifest
    try:
        write_manifest(Path(cache_dir), tickers)
    except Exception as e:
        print(f"[versioning] manifest write failed: {e}")
```

- [ ] **Step 3: Create `tests/test_versioning.py`**

```python
import pandas as pd
from pathlib import Path
from kth.data.versioning import write_manifest, verify_manifest


def test_write_and_verify_manifest(tmp_path):
    df = pd.DataFrame({"timestamps": pd.date_range("2024-01-01", periods=10),
                       "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1})
    df.to_parquet(tmp_path / "AAPL.parquet")
    m = write_manifest(tmp_path, ["AAPL"])
    assert "AAPL" in m["tickers"]
    v = verify_manifest(tmp_path)
    assert v["ok"] is True


def test_verify_detects_missing(tmp_path):
    df = pd.DataFrame({"timestamps": pd.date_range("2024-01-01", periods=10),
                       "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1})
    df.to_parquet(tmp_path / "AAPL.parquet")
    write_manifest(tmp_path, ["AAPL"])
    (tmp_path / "AAPL.parquet").unlink()
    v = verify_manifest(tmp_path)
    assert v["ok"] is False
    assert "AAPL" in v["missing"]


def test_verify_detects_hash_mismatch(tmp_path):
    df = pd.DataFrame({"timestamps": pd.date_range("2024-01-01", periods=10),
                       "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1})
    df.to_parquet(tmp_path / "AAPL.parquet")
    write_manifest(tmp_path, ["AAPL"])
    df2 = df.copy()
    df2["close"] = 999
    df2.to_parquet(tmp_path / "AAPL.parquet")
    v = verify_manifest(tmp_path)
    assert v["ok"] is False
    assert len(v["mismatches"]) == 1
```

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add kth/data/versioning.py kth/data/loader.py tests/test_versioning.py && git commit -m "feat(data): add manifest-based cache versioning (C6)"
```

---

## Task 14: Optimize equal-weight benchmark (L3)

**Files:**
- Modify: `kth/backtest/walkforward.py:534-555`

- [ ] **Step 1: Replace O(n_days × n_tickers) loop with vectorized pivot**

In `_compute_benchmarks`, replace the equal-weight block:

```python
    try:
        closes = {}
        for t in tickers:
            df_t = ticker_data.get(t) if ticker_data else None
            if df_t is None:
                from kth.data.loader import load_cached
                df_t = load_cached(t, config.cache_dir)
            s = df_t.set_index("timestamps")["close"]
            closes[t] = s
        price_df = pd.DataFrame(closes)
        norm_df = price_df / price_df.loc[start_ts]
        eq_series = norm_df.mean(axis=1).reindex(trading_days, method="ffill")
        benchmarks["equal_weight"] = eq_series.fillna(1.0)
    except Exception:
        benchmarks["equal_weight"] = pd.Series(1.0, index=trading_days)
```

- [ ] **Step 2: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/walkforward.py && git commit -m "perf(walkforward): vectorize equal-weight benchmark (L3)"
```

---

## Task 15: Replace `open_trades` dict with lot ledger (M6)

**Files:**
- Modify: `kth/backtest/walkforward.py:265, 355-430, 412-430`

- [ ] **Step 1: Replace `open_trades: dict` with `lots: dict[str, list[dict]]`**

At line 265, replace:
```python
    open_trades: dict[str, dict] = {}
```
with:
```python
    lots: dict[str, list[dict]] = {}  # ticker -> list of {entry_date, units, entry_price}
```

- [ ] **Step 2: Rewrite the sell branch (lines 355-369)**

Replace the `open_trades` gross_return computation with FIFO lot matching:

```python
                if ticker_lots := lots.get(t, []):
                    remaining = units
                    gross_return = 0.0
                    while remaining > 0 and ticker_lots:
                        lot = ticker_lots[0]
                        matched = min(remaining, lot["units"])
                        gross_return += (exec_price / lot["entry_price"] - 1) * (matched * lot["entry_price"])
                        remaining -= matched
                        if lot["units"] > matched:
                            lot["units"] -= matched
                        else:
                            ticker_lots.pop(0)
                    if not ticker_lots:
                        lots.pop(t, None)
                else:
                    gross_return = 0.0
```

- [ ] **Step 3: Rewrite the buy branch (lines 412-430)**

Replace the blend logic with a simple append:

```python
            if direction == "buy":
                lots.setdefault(t, []).append({
                    "entry_date": day,
                    "units": units_delta,
                    "entry_price": exec_price,
                })
            elif direction == "sell" and t in lots:
                remaining = abs(units_delta)
                while remaining > 0 and lots[t]:
                    lot = lots[t][0]
                    matched = min(remaining, lot["units"])
                    lot["units"] -= matched
                    remaining -= matched
                    if lot["units"] <= 0:
                        lots[t].pop(0)
                if not lots[t]:
                    lots.pop(t)
```

- [ ] **Step 4: Update the regression test**

The existing test `test_open_trades_blends_on_rebalance` checks for `'blended'` in source. Replace it with:

```python
def test_lots_ledger_appends_on_buy():
    import inspect
    from kth.backtest import walkforward
    src = inspect.getsource(walkforward.run_walkforward)
    assert "lots" in src, "walkforward must use a lots ledger"
    assert "entry_date" in src or "entry_price" in src
```

- [ ] **Step 5: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "refactor(walkforward): replace open_trades dict with lot ledger (M6)"
```

---

## Task 16: Documentation — README stale numbers banner (P1, H4)

**Files:**
- Modify: `README.md:43-54`

- [ ] **Step 1: Add stale banner to "Project state" section**

After the heading `## Project state`, add:

```markdown
> **⚠️ STALE NUMBERS:** Backtest results below were computed before the
> 2026-06-21 bug fixes (PSR formula, equity curve alignment, open_trades
> blending). A GPU re-run is required. Do NOT cite these numbers until the
> re-run completes. See `data/backtest_results/MANIFEST.md`.
>
> **Survivorship bias:** Cited CAGRs are overstated by ~1-3pp/yr. Adjust
> mentally: "31.4% gross → ~28-30% survivorship-adjusted."
```

- [ ] **Step 2: Commit**

```bash
git add README.md && git commit -m "docs(README): add stale-numbers + survivorship banners (P1, H4)"
```

---

## Task 17: Documentation — Reframe alpha as regime-conditional (H1, P2)

**Files:**
- Modify: `README.md` (caveats section)
- Modify: `PROJECT_STRUCTURE.md:559-567, §14`

- [ ] **Step 1: Add to README "Honest caveats" section**

After caveat #3, add:

```markdown
4. **Alpha is regime-conditional, not year-round.** This is a defensive tilt,
   not a stock-selection edge. The strategy structurally holds cash, so it
   outperforms in bear/flat SET regimes (2024, 2025) but underperforms in broad
   bull markets (2023, 2026-to-date). In a bull regime, expect BEAR allocation
   (5% deployed) until the regime shifts. Do not expect it to beat a bull market.
```

Renumber existing caveats 4-5 to 5-6.

- [ ] **Step 2: Update `PROJECT_STRUCTURE.md §14` status date**

Change `### Current status (2026-05-21)` to `### Current status (2026-06-21, post-code-review)`.

Add after the heading:

```markdown
> **Code review fixes applied 2026-06-21.** Stored backtest numbers in
> `data/backtest_results/` are STALE pending GPU re-run. See MANIFEST.md.
> The alpha is regime-conditional (defensive tilt) — see README caveats.
```

- [ ] **Step 3: Commit**

```bash
git add README.md PROJECT_STRUCTURE.md && git commit -m "docs: reframe alpha as regime-conditional + update status date (H1, P2)"
```

---

## Task 18: Create ADRs for rejected approaches (P3)

**Files:**
- Create: `docs/adr/0001-equal-weight-position-sizing.md`
- Create: `docs/adr/0002-zero-shot-only.md`
- Create: `docs/adr/0003-no-portfolio-optimization.md`

- [ ] **Step 1: Create `docs/adr/` dir + ADR 0001**

```bash
mkdir -p docs/adr
```

```markdown
# ADR 0001: Equal-Weight Position Sizing

**Date:** 2026-06-21  **Status:** Accepted

## Context
The backtest engine supports three sizing modes: `equal`, `signal` (rank-based), and `inv_vol` (inverse volatility).

## Decision
Use `equal` weighting only.

## Rationale
`inv_vol` was backtested in `thai_equity_2022-2024_invvol/`: CAGR 13.29%, Sharpe 0.84, p=0.732. Equal-weight conclusively beat it. inv_vol over-allocates to low-vol stocks where the Kronos signal is weakest. `signal` mode is untested.

## Consequences
- All deployed strategies use equal weight.
- Do not switch to `inv_vol` without a GPU re-run that beats equal-weight.
```

- [ ] **Step 2: Create ADR 0002**

```markdown
# ADR 0002: Zero-Shot Only (No Fine-Tuning in Production)

**Date:** 2026-06-21  **Status:** Accepted

## Context
9 fine-tuned checkpoints were trained (3 markets × 3 folds) via SGDR.

## Decision
Deploy zero-shot Kronos-small only. Fine-tuned checkpoints are saved but not deployed.

## Rationale
Fine-tuning did not beat zero-shot in any of the 3 markets (thai_equity, us_equity, crypto). Direction-accuracy gains from FT did not translate to backtest alpha.

## Consequences
- All production forecasts use `NeoQuasar/Kronos-small` zero-shot.
- FT checkpoints remain at `checkpoints/{model}/fold{f}/best/` for reference.
- Re-evaluating FT requires a full re-run; do not relitigate without GPU time.
```

- [ ] **Step 3: Create ADR 0003**

```markdown
# ADR 0003: No Portfolio Optimization (Markowitz / Risk Parity / Factor Models)

**Date:** 2026-06-21  **Status:** Accepted

## Context
The strategy selects top-5 stocks by Expected Return and sizes them equally.

## Decision
Do not add Markowitz, risk parity, or factor-model optimization.

## Rationale
Per `PROJECT_STRUCTURE.md §12`: adds complexity without changing the core question ("does the model pick well?"). Equal-weight is the cleanest test of stock-selection alpha. Optimization can be Notebook 06 later if useful.

## Consequences
- Position sizing stays equal-weight (see ADR 0001).
- Portfolio optimization is out of scope until explicitly requested.
```

- [ ] **Step 4: Commit**

```bash
git add docs/adr/ && git commit -m "docs(adr): record rejected approaches (P3)"
```

---

## Task 19: Cross-link CONTEXT.md + extended-cash runbook (P4, P5)

**Files:**
- Modify: `CONTEXT.md` (add ADR links)
- Modify: `docs/operations-manual.md` (add cash-regime section) or create if missing

- [ ] **Step 1: Add ADR cross-links to CONTEXT.md**

At the end of the **Risk Band** entry, add:
```
**Decision:** See `docs/adr/0001-equal-weight-position-sizing.md`.
```

At the end of **Bootstrap p-value**, add:
```
**Decision context:** Two p-value mechanisms — see `docs/adr/` for statistical methodology decisions.
```

- [ ] **Step 2: Add extended-cash runbook**

Check if `docs/operations-manual.md` exists; if not, create it. Add a section:

```markdown
## Extended Cash Regime — Interpretation & Override Criteria

If the dashboard shows "STAY CASH" or BEAR allocation for 30+ consecutive days:

1. **This is expected in a bull market.** The strategy structurally holds cash
   when the SET is in a strong uptrend. See README caveat #4 (regime-conditional).
2. **Do not override the risk band manually.** The 12-week trailing Sharpe is
   the signal. If it rises above 0.5, the band auto-promotes to NEUTRAL.
3. **Verify the regime.** Check SET Index 60-day return. If SET is up >10% over
   60 days, BEAR allocation is the correct response, not a malfunction.
4. **Override criteria (rare):** Only override if (a) the model forecasts are
   loading correctly (check `/api/health`), AND (b) you have a documented
   thesis for why the regime is about to shift. Document the override in the
   trade log rationale field.
5. **Accumulate paper trades.** The bootstrap p-value needs ≥20 days and the
   allocation band needs ≥20 closed trades to promote from NEUTRAL bootstrap.
   Patience is the strategy.
```

- [ ] **Step 3: Commit**

```bash
git add CONTEXT.md docs/operations-manual.md && git commit -m "docs: cross-link CONTEXT to ADRs + extended-cash runbook (P4, P5)"
```

---

## Phase 1 Completion Check

- [ ] **Step 1: Run full test suite**

```bash
pytest -q tests/
python verify_data_layer.py
```
Expected: all green.

- [ ] **Step 2: Run ruff on all touched files**

```bash
ruff check kth/ tests/ scripts/
```
Fix any new warnings in files you touched.

- [ ] **Step 3: Run pipeline dry-run**

```bash
python run_pipeline.py --dry-run
```
Expected: completes without error.

- [ ] **Step 4: Verify no stale numbers quoted without caveat**

```bash
rg "CAGR.*31|Sharpe.*1.40|p.*0.015" README.md PROJECT_STRUCTURE.md
```
Every match should be within 5 lines of a "stale" or "⚠️" caveat.

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "chore: Phase 1 completion — all no-GPU fixes applied"
```

---

## Phase 1 Summary

| Task | Issues Fixed | Effort |
|------|-------------|--------|
| 1 | L1(stub), L7, L8, L13 | S |
| 2 | H3 | S |
| 3 | C5 | L |
| 4 | L14 | S |
| 5 | L10, L11, L12 | S |
| 6 | L1 (real) | M |
| 7 | L6 | M |
| 8 | L4 | M |
| 9 | L2 | S |
| 10 | M8 | M |
| 11 | M7 | M |
| 12 | L5, L9 | S |
| 13 | C6 | L |
| 14 | L3 | M |
| 15 | M6 | L |
| 16 | P1, H4 | S |
| 17 | H1, P2 | M |
| 18 | P3 | M |
| 19 | P4, P5 | M |

**Total: 29 issues fixed. Estimated effort: 3-4 focused days.**

Phase 2 (GPU-required) is in `2026-06-21-quant-review-remediation-phase2-gpu.md`.
