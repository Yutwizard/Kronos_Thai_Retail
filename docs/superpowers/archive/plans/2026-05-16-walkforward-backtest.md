# Walk-forward Backtest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict walk-forward backtester that generates signals using only in-time data, applies Thai-retail frictions on every trade, and reports professional-grade metrics against four honest benchmarks.

**Architecture:** Three modules: `strategy.py` (pure signal/weight functions), `metrics.py` (pure metric functions returning dicts), `walkforward.py` (simulation loop + precomputation cache + `BacktestResult`). Forecasts are precomputed once keyed by `(date, ticker)`, making repeated backtest runs instant.

**Tech Stack:** Python 3.10+, `pandas`, `numpy`, `dataclasses`, `scipy.stats` (t-test, OLS), Spec A (`KronosTH`, `ForecastResult`)

**Depends on:** Spec A (KronosTH wrapper) — MUST be implemented first.

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `kth/backtest/__init__.py` | Package marker |
| Create | `kth/backtest/strategy.py` | `compute_signals`, `select_positions`, `compute_weights` |
| Create | `kth/backtest/metrics.py` | All metric functions (CAGR, Sharpe, drawdowns, etc.) |
| Create | `kth/backtest/walkforward.py` | `BacktestConfig`, `BacktestResult`, `run_walkforward`, `precompute_forecasts`, `compute_benchmarks` |
| Create | `notebooks/03_walkforward_backtest.ipynb` | Backtest notebook |

---

### Task 1: `strategy.py` — pure signal and position functions

**Files:**
- Create: `kth/backtest/__init__.py`
- Create: `kth/backtest/strategy.py`

- [ ] **Step 1: Write failing test scaffold**

```python
# tests/backtest/test_strategy.py (run inline for now)
import sys; sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from kth.backtest.strategy import compute_signals, select_positions, compute_weights

# Minimal ForecastResult mock — p50 must be a PRICE, not a return
class MockHorizon:
    def __init__(self, summary_df):
        self.summary = summary_df

class MockResult:
    def __init__(self, p50_price):
        # p50_price: the median forecast CLOSE PRICE (e.g. 103.0 for 3% above 100)
        self.horizons = {
            20: MockHorizon(pd.DataFrame({"p50": [p50_price]}))
        }

# Test compute_signals — p50 at pred_len=20 is the forecast close price
# AAPL: last_close=100, p50=103 → return = 3% (above 1% threshold → included)
# PTT.BK: last_close=50, p50=50.5 → return = 1% (at threshold, not above → excluded)
# SPY: last_close=400, p50=396 → return = -1% (below 0 → excluded)
forecasts = {"AAPL": MockResult(103.0), "PTT.BK": MockResult(50.5), "SPY": MockResult(396.0)}
last_closes = {"AAPL": 100.0, "PTT.BK": 50.0, "SPY": 400.0}
signals = compute_signals(forecasts, last_closes, threshold=0.01, pred_len=20)
assert signals == {"AAPL": 0.03}, f"expected {{'AAPL': 0.03}}, got {signals}"
print("PASS: compute_signals")

# Test select_positions — held positions pass actual signal, not placeholder '1'
# signals_raw contains the real signal values for ranking (both held and candidates)
signals_for_ranking = {"AAPL": 0.03}
selected = select_positions(signals_for_ranking, max_positions=2)
assert len(selected) == 1
assert selected[0] == "AAPL"
print("PASS: select_positions")

# Test select_positions with held+new — higher-signal held beats lower-signal new
signals_for_ranking = {"AAPL": 0.03, "PTT.BK": 0.02}
selected = select_positions(signals_for_ranking, max_positions=2)
assert selected == ["AAPL", "PTT.BK"], f"expected ['AAPL','PTT.BK'], got {selected}"
print("PASS: select_positions ranking order")

# Test compute_weights — equal
weights = compute_weights(["AAPL", "PTT.BK"], signals, {}, mode="equal")
assert abs(sum(weights.values()) - 1.0) < 1e-10
assert weights == {"AAPL": 0.5, "PTT.BK": 0.5}
print("PASS: compute_weights equal")

# Test compute_weights — signal
weights_s = compute_weights(["AAPL", "PTT.BK"], signals, {}, mode="signal")
assert abs(sum(weights_s.values()) - 1.0) < 1e-10
assert weights_s["AAPL"] > weights_s["PTT.BK"]
print("PASS: compute_weights signal")

# Test compute_weights — inv_vol
recent_vols = {"AAPL": 0.02, "PTT.BK": 0.04}
weights_v = compute_weights(["AAPL", "PTT.BK"], signals, recent_vols, mode="inv_vol")
assert abs(sum(weights_v.values()) - 1.0) < 1e-10
assert weights_v["AAPL"] > weights_v["PTT.BK"]  # lower vol → higher weight
print("PASS: compute_weights inv_vol")

print("ALL STRATEGY TESTS PASSED")
```

Run: `python tests/backtest/test_strategy.py`
Expected: `FAIL` with `ModuleNotFoundError`

- [ ] **Step 2: Implement `strategy.py`**

```python
# kth/backtest/__init__.py
"""Kronos-TH backtest layer: walk-forward simulation, strategy, metrics."""
```

```python
# kth/backtest/strategy.py
"""Pure strategy functions: signal generation, position selection, weight computation."""
from __future__ import annotations


def compute_signals(
    forecasts: dict[str, object],  # dict of ForecastResult
    last_closes: dict[str, float],
    threshold: float,
    pred_len: int,
) -> dict[str, float]:
    """
    Returns {ticker: median_forecast_return} for tickers where last_close is known.
    Median forecast return = (p50 at pred_len / last_close) - 1.
    """
    signals: dict[str, float] = {}
    for ticker, result in forecasts.items():
        if ticker not in last_closes:
            continue
        median_close = result.horizons[pred_len].summary["p50"].iloc[-1]
        ret = (median_close / last_closes[ticker]) - 1.0
        if ret > threshold:
            signals[ticker] = ret
    return signals


def select_positions(
    signals: dict[str, float],
    max_positions: int,
) -> list[str]:
    """Top-N tickers by signal strength (descending). Held positions should pass
    their actual signal value (not '1') so they rank correctly against new candidates."""
    sorted_tickers = sorted(signals.keys(), key=lambda t: signals[t], reverse=True)
    return sorted_tickers[:max_positions]


def compute_weights(
    selected: list[str],
    signals: dict[str, float],
    recent_vols: dict[str, float],
    mode: str = "equal",
) -> dict[str, float]:
    """Returns {ticker: portfolio_weight} summing to 1.0."""
    if not selected:
        return {}

    if mode == "equal":
        w = 1.0 / len(selected)
        return {t: w for t in selected}

    if mode == "signal":
        # Rank-based: highest signal gets rank len(selected), lowest gets 1
        ranked = sorted(selected, key=lambda t: signals.get(t, 0.0))
        ranks = {t: i + 1 for i, t in enumerate(ranked)}
        total_rank = sum(ranks.values())
        return {t: ranks[t] / total_rank for t in selected}

    if mode == "inv_vol":
        inv_vols = {t: 1.0 / max(recent_vols.get(t, 0.01), 1e-8) for t in selected}
        total = sum(inv_vols.values())
        return {t: inv_vols[t] / total for t in selected}

    raise ValueError(f"Unknown position_sizing mode: {mode}")
```

- [ ] **Step 3: Run tests**

Run: `python tests/backtest/test_strategy.py`
Expected: `ALL STRATEGY TESTS PASSED`

- [ ] **Step 4: Commit**

```bash
git add kth/backtest/__init__.py kth/backtest/strategy.py tests/backtest/test_strategy.py
git commit -m "feat: add strategy.py with pure signal/position/weight functions"
```

---

### Task 2: `metrics.py` — pure metric functions

**Files:**
- Create: `kth/backtest/metrics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtest/test_metrics.py
import sys; sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from kth.backtest.metrics import compute_metrics, compute_sharpe, compute_max_drawdown

# Test max drawdown
np.random.seed(42)
returns = pd.Series(np.random.normal(0.0005, 0.01, 500))
equity = (1 + returns).cumprod()
dd = compute_max_drawdown(equity)
assert isinstance(dd, float)
assert dd <= 1.0, f"drawdown should be <= 1.0, got {dd}"
print(f"PASS: max_drawdown = {dd:.4f}")

# Test Sharpe
sharpe = compute_sharpe(returns, rf=0.02, periods_per_year=252)
assert isinstance(sharpe, float)
print(f"PASS: sharpe = {sharpe:.4f}")

# Test full metric set
trades = pd.DataFrame(columns=["ticker", "direction", "size_pct", "friction_cost", "gross_return"])
metrics = compute_metrics(equity, returns, trades, benchmark=equity * 1.001, rf=0.02)
required_keys = ["cagr", "sharpe", "max_drawdown", "sortino", "calmar", "var_95"]
for k in required_keys:
    assert k in metrics, f"missing key: {k}"
print(f"PASS: compute_metrics returns {len(metrics)} keys including {required_keys}")

print("ALL METRICS TESTS PASSED")
```

Run: `python tests/backtest/test_metrics.py`
Expected: `FAIL`

- [ ] **Step 2: Implement `metrics.py`**

```python
# kth/backtest/metrics.py
"""Pure metric functions for backtest evaluation. All return dicts."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def compute_sharpe(
    daily_returns: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    excess = daily_returns - rf / periods_per_year
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))


def compute_sortino(
    daily_returns: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    excess = daily_returns - rf / periods_per_year
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(periods_per_year))


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    return float(drawdown.min())


def compute_drawdown_metrics(equity_curve: pd.Series) -> dict:
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak  # negative values

    max_dd = float(drawdown.min())

    # Average drawdown
    avg_dd = float(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0.0

    # Ulcer index: RMS of drawdowns
    ulcer = float(np.sqrt((drawdown ** 2).mean()))

    # Drawdown durations
    underwater = drawdown < 0
    if not underwater.any():
        return {"max_drawdown": 0.0, "avg_drawdown": 0.0, "ulcer_index": 0.0,
                "max_drawdown_duration": 0, "avg_drawdown_duration": 0}

    # Find underwater periods
    groups = (underwater != underwater.shift(1)).cumsum()
    durations = groups[underwater].value_counts()
    max_dur = int(durations.max()) if len(durations) > 0 else 0
    avg_dur = float(durations.mean()) if len(durations) > 0 else 0.0

    return {
        "max_drawdown": max_dd,
        "avg_drawdown": avg_dd,
        "ulcer_index": ulcer,
        "max_drawdown_duration": max_dur,
        "avg_drawdown_duration": avg_dur,
    }


def compute_var_cvar(daily_returns: pd.Series) -> dict:
    returns_arr = daily_returns.dropna().values
    var_95 = float(np.percentile(returns_arr, 5))
    var_99 = float(np.percentile(returns_arr, 1))
    cvar_95 = float(returns_arr[returns_arr <= var_95].mean()) if (returns_arr <= var_95).any() else 0.0
    return {"var_95": var_95, "var_99": var_99, "cvar_95": cvar_95}


def compute_trade_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"hit_rate": 0.0, "payoff_ratio": 0.0, "profit_factor": 0.0,
                "avg_holding_period": 0.0, "avg_trade_return_gross": 0.0,
                "avg_trade_return_net": 0.0, "max_win_streak": 0, "max_loss_streak": 0}

    wins = trades[trades["gross_return"] > 0]
    losses = trades[trades["gross_return"] < 0]

    hit_rate = len(wins) / len(trades) if len(trades) > 0 else 0.0
    avg_win = wins["gross_return"].mean() if len(wins) > 0 else 0.0
    avg_loss = abs(losses["gross_return"].mean()) if len(losses) > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    gross_profit = wins["gross_return"].sum() if len(wins) > 0 else 0.0
    gross_loss = abs(losses["gross_return"].sum()) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Win/loss streaks
    outcomes = (trades["gross_return"] > 0).astype(int)
    max_win = max_loss = current_win = current_loss = 0
    for o in outcomes:
        if o:
            current_win += 1; current_loss = 0
            max_win = max(max_win, current_win)
        else:
            current_loss += 1; current_win = 0
            max_loss = max(max_loss, current_loss)

    return {
        "hit_rate": hit_rate,
        "payoff_ratio": payoff,
        "profit_factor": profit_factor,
        "avg_holding_period": 0.0,  # filled by walkforward loop
        "avg_trade_return_gross": float(trades["gross_return"].mean()) if len(trades) > 0 else 0.0,
        "avg_trade_return_net": float((trades["gross_return"] - trades["friction_cost"]).mean()) if len(trades) > 0 else 0.0,
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
    }


def compute_metrics(
    equity_curve: pd.Series,
    daily_returns: pd.Series,
    trades: pd.DataFrame,
    benchmark: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> dict:
    """
    Compute full professional metric set from equity curve and trades.
    Returns flat dict. All ratio metrics computed gross and net where applicable.
    """
    n_days = len(daily_returns)
    years = n_days / periods_per_year

    # CAGR
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    cagr = float((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0

    # Volatility
    ann_vol = float(daily_returns.std() * np.sqrt(periods_per_year))

    # Sharpe / Sortino / Calmar
    sharpe = compute_sharpe(daily_returns, rf, periods_per_year)
    sortino = compute_sortino(daily_returns, rf, periods_per_year)
    dd_metrics = compute_drawdown_metrics(equity_curve)
    calmar = cagr / abs(dd_metrics["max_drawdown"]) if dd_metrics["max_drawdown"] != 0 else 0.0

    # Omega
    gains = daily_returns[daily_returns > 0].sum()
    losses = abs(daily_returns[daily_returns < 0].sum())
    omega = float(gains / losses) if losses > 0 else float("inf")

    # Information ratio
    excess_returns = daily_returns - benchmark.pct_change()
    tracking_error = excess_returns.std() * np.sqrt(periods_per_year)
    info_ratio = float(excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)) if tracking_error > 0 else 0.0

    # Alpha / Beta (OLS)
    bm_rets = benchmark.pct_change().dropna()
    aligned = pd.concat([daily_returns, bm_rets], axis=1).dropna()
    if len(aligned) > 2:
        aligned.columns = ["strategy", "benchmark"]
        slope, intercept, _, _, _ = stats.linregress(aligned["benchmark"], aligned["strategy"])
        beta = slope
        alpha = intercept * periods_per_year
    else:
        beta = alpha = 0.0

    # VaR / CVaR
    var_cvar = compute_var_cvar(daily_returns)

    # Trade metrics
    trade_m = compute_trade_metrics(trades)

    # Annual turnover
    total_traded = trades["size_pct"].sum() if not trades.empty else 0.0
    avg_portfolio_value = float(equity_curve.mean())
    annual_turnover = float(total_traded / avg_portfolio_value / years) if years > 0 else 0.0

    # Total friction
    total_friction = float(trades["friction_cost"].sum()) if not trades.empty else 0.0

    # t-stat vs benchmark
    excess_daily = daily_returns - benchmark.pct_change().fillna(0)
    if excess_daily.std() > 0:
        t_stat = float(excess_daily.mean() / (excess_daily.std() / np.sqrt(len(excess_daily))))
        p_value = float(2 * stats.t.sf(abs(t_stat), df=len(excess_daily) - 1))
    else:
        t_stat = p_value = 0.0

    return {
        "cagr": cagr,
        "total_return": total_return,
        "annualised_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "omega": omega,
        "information_ratio": info_ratio,
        "alpha": alpha,
        "beta": beta,
        **dd_metrics,
        **var_cvar,
        **trade_m,
        "annual_turnover": annual_turnover,
        "total_friction_paid": total_friction,
        "t_stat": t_stat,
        "p_value": p_value,
    }
```

- [ ] **Step 3: Run tests**

Run: `python tests/backtest/test_metrics.py`
Expected: `ALL METRICS TESTS PASSED`

- [ ] **Step 4: Commit**

```bash
git add kth/backtest/metrics.py tests/backtest/test_metrics.py
git commit -m "feat: add metrics.py with professional metric set (CAGR, Sharpe, drawdowns, VaR, trade stats)"
```

---

### Task 3: `BacktestConfig` dataclass

**Files:**
- Create: `kth/backtest/walkforward.py`

- [ ] **Step 1: Write BacktestConfig**

```python
# kth/backtest/walkforward.py (start)
"""Walk-forward backtest simulation with strict no-look-ahead."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    start_date: str = "2022-01-01"
    end_date: str = "2024-12-31"
    lookback: int = 400
    pred_len: int = 20
    n_samples: int = 50
    long_threshold: float = 0.01
    entry_buffer: float = 0.005
    min_holding_days: int = 5
    max_positions: int = 5
    position_sizing: str = "equal"
    inv_vol_window: int = 20
    trading_calendar: str = "NYSE"
    min_ticker_history: int = 252
    forecast_cache_dir: str = "./data/forecast_cache"
    cache_dir: str = "./data/raw"
```

- [ ] **Step 2: Verify import**

Run: `python -c "from kth.backtest.walkforward import BacktestConfig; c = BacktestConfig(); print(c.long_threshold)"`
Expected: `0.01`

- [ ] **Step 3: Commit**

```bash
git add kth/backtest/walkforward.py
git commit -m "feat: add BacktestConfig dataclass"
```

---

### Task 4: `precompute_forecasts()` — forecast cache

**Files:**
- Modify: `kth/backtest/walkforward.py`

- [ ] **Step 1: Implement precompute_forecasts**

Append to `walkforward.py`:

```python
def _model_slug(model_name: str) -> str:
    """Convert model_name to a filesystem-safe slug for cache directory naming.
    e.g. 'NeoQuasar/Kronos-small@a3f1c2d' → 'NeoQuasar_Kronos-small-a3f1c2d'
    """
    return model_name.replace("/", "_").replace("@", "-").replace("\\", "_")


def precompute_forecasts(
    kronos_th,  # KronosTH instance
    tickers: list[str],
    start_date: str,
    end_date: str,
    pred_len: int,
    n_samples: int,
    lookback: int,
    cache_dir: str = "./data/forecast_cache",
) -> None:
    """
    Run forecast_batch() once per trading day. Idempotent — skips cached dates.
    Persists each ForecastResult as {cache_dir}/{model_slug}/{date}/{ticker}.parquet
    + {ticker}_meta.json.

    The model slug is derived from kronos_th.model_name so that forecasts from
    different models (zero-shot vs fine-tuned) are stored in separate directories
    and never silently overwrite each other.
    """
    import json

    slug = _model_slug(kronos_th.model_name)
    cache_path = Path(cache_dir) / slug
    cache_path.mkdir(parents=True, exist_ok=True)
    print(f"[precompute] Model: {kronos_th.model_name}  Cache: {cache_path}")

    # NOTE: pd.bdate_range includes Mon-Fri including US holidays.
    # Days with no ticker data produce no forecasts and no trades — no error.
    # Switching to pandas_market_calendars would be more precise but adds a dependency.
    trading_days = pd.bdate_range(start=start_date, end=end_date, freq="B")

    for day in trading_days:
        day_str = day.strftime("%Y-%m-%d")
        day_dir = cache_path / day_str
        day_dir.mkdir(parents=True, exist_ok=True)

        # Filter tickers not yet cached for this day
        uncached = []
        for t in tickers:
            out_file = day_dir / f"{t.replace('^','_').replace('=','_')}.parquet"
            if not out_file.exists():
                uncached.append(t)

        if not uncached:
            continue

        print(f"[{day_str}] {len(uncached)} tickers to forecast...")
        results = kronos_th.forecast_batch(uncached, pred_lens=[pred_len], n_samples=n_samples, lookback=lookback)

        for t, result in results.items():
            safe = t.replace("^", "_").replace("=", "_")
            h_df = result.horizons[pred_len].summary.copy()
            h_df["ticker"] = t
            h_df.to_parquet(day_dir / f"{safe}.parquet", index=False)
            meta = {
                "ticker": t,
                "model_name": result.model_name,
                "generated_at": str(result.generated_at),
                "lookback_end": str(result.lookback_end),
            }
            with open(day_dir / f"{safe}_meta.json", "w") as f:
                json.dump(meta, f)
```

- [ ] **Step 2: Commit**

```bash
git add kth/backtest/walkforward.py
git commit -m "feat: add precompute_forecasts with model-slug-keyed parquet cache"
```

---

### Task 5: `run_walkforward()` — main simulation loop

**Files:**
- Modify: `kth/backtest/walkforward.py`

- [ ] **Step 1: Implement the walkforward loop with BacktestResult**

This is the largest task. Implement the full simulation loop described in Spec B §Walk-forward Loop.

```python
# ---- Module-level cache classes (NOT inside the loop) ----

class _CachedHorizon:
    """Lightweight wrapper around a forecast summary DataFrame."""
    __slots__ = ("summary",)
    def __init__(self, df: pd.DataFrame):
        self.summary = df

class _CachedResult:
    """Lightweight ForecastResult-compatible object from precomputed cache."""
    __slots__ = ("horizons",)
    def __init__(self, df: pd.DataFrame, pred_len: int):
        self.horizons = {pred_len: _CachedHorizon(df)}


@dataclass
class BacktestResult:
    config: BacktestConfig
    equity_curve: pd.Series
    gross_equity_curve: pd.Series
    trades: pd.DataFrame
    daily_returns: pd.Series
    benchmarks: dict[str, pd.Series]
    metrics: dict
    per_class_attribution: pd.DataFrame

    def save(self, dir_path: str) -> None:
        out = Path(dir_path)
        out.mkdir(parents=True, exist_ok=True)
        self.equity_curve.to_frame("equity").to_parquet(out / "equity_curve.parquet")
        self.gross_equity_curve.to_frame("gross_equity").to_parquet(out / "gross_equity_curve.parquet")
        self.trades.to_parquet(out / "trades.parquet", index=False)
        self.daily_returns.to_frame("daily_returns").to_parquet(out / "daily_returns.parquet")
        for name, series in self.benchmarks.items():
            series.to_frame(name).to_parquet(out / f"benchmark_{name}.parquet")
        self.per_class_attribution.to_parquet(out / "per_class_attribution.parquet")
        with open(out / "metrics.json", "w") as f:
            import math
            # Replace inf/nan with None — JSON does not support IEEE 754 infinities.
            # profit_factor is inf when there are no losing trades.
            safe_metrics = {
                k: (None if isinstance(v, float) and (math.isinf(v) or math.isnan(v)) else v)
                for k, v in self.metrics.items()
            }
            json.dump(safe_metrics, f)
        with open(out / "config.json", "w") as f:
            json.dump(self.config.__dict__, f)

    @classmethod
    def load(cls, dir_path: str) -> "BacktestResult":
        raise NotImplementedError("load() deferred to Task 6")


def run_walkforward(
    config: BacktestConfig,
    kronos_th,  # KronosTH
    tickers: list[str],
) -> BacktestResult:
    """
    Strict walk-forward backtest. Reads from precomputed forecast cache.
    Uses UNITS-based accounting — tracks shares held, not abstract weights.
    Cache path: config.forecast_cache_dir / {model_slug} / {date} / {ticker}.parquet
    Run precompute_forecasts() first with the same kronos_th instance.
    """
    from kth.data.loader import load_cached
    from kth.data.universe import get_ticker_class, FRICTION
    from kth.backtest.strategy import compute_signals, select_positions, compute_weights

    slug = _model_slug(kronos_th.model_name)
    forecast_cache = Path(config.forecast_cache_dir) / slug
    if not forecast_cache.exists():
        raise FileNotFoundError(
            f"No forecast cache found at {forecast_cache}. "
            f"Run precompute_forecasts() with model '{kronos_th.model_name}' first."
        )

    # NOTE: pd.bdate_range includes US holidays; days with no data produce no trades.
    trading_days = pd.bdate_range(start=config.start_date, end=config.end_date, freq="B")

    # Pre-filter eligible tickers
    eligible = []
    for t in tickers:
        try:
            df_full = load_cached(t, config.cache_dir)
            test_start = pd.Timestamp(config.start_date)
            test_rows = df_full[df_full["timestamps"] >= test_start]
            if len(test_rows) >= config.min_ticker_history:
                eligible.append(t)
        except FileNotFoundError:
            continue
    print(f"Eligible tickers: {len(eligible)} / {len(tickers)}")

    # ---- PRELOAD all ticker data into memory ONCE ----
    ticker_data: dict[str, pd.DataFrame] = {}
    for t in eligible:
        try:
            ticker_data[t] = load_cached(t, config.cache_dir)
        except FileNotFoundError:
            continue

    # Compute benchmarks once
    benchmarks = _compute_benchmarks(config, eligible, ticker_data)

    # ---- Portfolio state (UNITS-BASED) ----
    cash = 1.0
    gross_cash = 1.0                # parallel tracker — same units, never subtracts friction
    holdings_units: dict[str, float] = {}   # ticker → number of shares
    gross_units: dict[str, float] = {}      # same positions, mirrored for gross curve
    holding_days: dict[str, int] = {}        # ticker → consecutive days held
    portfolio_values: list[float] = []
    gross_portfolio_values: list[float] = []
    trades_list: list[dict] = []
    open_trades: dict[str, dict] = {}  # ticker → {entry_price, units, entry_date}

    for day_idx, day in enumerate(trading_days):
        day_str = day.strftime("%Y-%m-%d")

        # --- 1. FORECAST ---
        forecasts = {}
        last_closes = {}
        for t in eligible:
            safe = t.replace("^", "_").replace("=", "_")
            fc_file = forecast_cache / day_str / f"{safe}.parquet"
            if not fc_file.exists():
                continue
            fc_df = pd.read_parquet(fc_file)
            forecasts[t] = _CachedResult(fc_df, config.pred_len)
            # Last close from preloaded data (in-memory, not disk)
            df_t = ticker_data.get(t)
            if df_t is not None:
                mask = df_t["timestamps"] <= day
                if mask.any():
                    last_closes[t] = float(df_t.loc[mask, "close"].iloc[-1])

        # --- 2. SIGNAL with hysteresis ---
        raw_signals = compute_signals(forecasts, last_closes, config.long_threshold, config.pred_len)
        signals: dict[str, float] = {}           # 0=close, sig=open, actual_value=hold
        signals_for_ranking: dict[str, float] = {}  # actual signal values for position ranking

        for t, sig in raw_signals.items():
            if t in holdings_units and holdings_units[t] > 0:
                # Currently held — hysteresis logic
                if sig < config.long_threshold - config.entry_buffer and holding_days.get(t, 0) >= config.min_holding_days:
                    signals[t] = 0  # close
                    # Don't add to signals_for_ranking — position closes
                else:
                    signals[t] = 1  # hold
                    signals_for_ranking[t] = sig  # use REAL signal value for ranking
            else:
                # Not held
                if sig > config.long_threshold + config.entry_buffer:
                    signals[t] = sig  # open
                    signals_for_ranking[t] = sig

        # --- 3. POSITION SIZING ---
        # active is union of {held AND not closing} + {new opens}
        active = {t: sig for t, sig in signals.items() if sig > 0}
        # Rank all active positions by their actual signal strength
        ranked = sorted(signals_for_ranking.keys(), key=lambda t: signals_for_ranking[t], reverse=True)
        selected = ranked[:config.max_positions]

        recent_vols = {}
        if config.position_sizing == "inv_vol":
            for t in selected:
                try:
                    df_t = ticker_data.get(t)
                    if df_t is not None:
                        mask = df_t["timestamps"] <= day
                        vol_df = df_t[mask].tail(config.inv_vol_window)
                        recent_vols[t] = float(vol_df["close"].pct_change().std())
                except Exception:
                    recent_vols[t] = 0.02

        target_weights = compute_weights(selected, signals_for_ranking, recent_vols, config.position_sizing)

        # --- 4. TRADES (execute at t+1 open prices) ---
        next_day = trading_days[day_idx + 1] if day_idx + 1 < len(trading_days) else day
        # Compute current portfolio value for trade sizing
        portfolio_value = cash
        gross_portfolio_value = gross_cash
        for t, units in holdings_units.items():
            df_t = ticker_data.get(t)
            if df_t is not None:
                mask = df_t["timestamps"] <= day
                if mask.any():
                    price = float(df_t.loc[mask, "close"].iloc[-1])
                    portfolio_value += units * price
                    gross_portfolio_value += units * price

        # Close positions not in target
        for t in list(holdings_units.keys()):
            if t not in target_weights and holdings_units.get(t, 0) > 0:
                df_t = ticker_data.get(t)
                if df_t is not None:
                    mask_open = df_t["timestamps"] <= next_day
                    if mask_open.any():
                        exec_price = float(df_t.loc[mask_open, "open"].iloc[-1])
                    else:
                        exec_price = float(df_t[df_t["timestamps"] <= day]["close"].iloc[-1])
                else:
                    continue
                units = holdings_units[t]
                trade_value = units * exec_price
                cls = get_ticker_class(t) or "us_equity"
                frict = FRICTION.get(cls, {"commission_oneway": 0.003, "slippage_oneway": 0.001})
                friction_cost = trade_value * (frict["commission_oneway"] + frict["slippage_oneway"])

                cash += trade_value - friction_cost
                gross_cash += trade_value  # no friction deduction
                # Compute gross return for closed trade
                if t in open_trades:
                    entry_price = open_trades[t]["entry_price"]
                    gross_return = (exec_price / entry_price - 1) * open_trades[t]["trade_value"]
                else:
                    gross_return = 0.0

                trades_list.append({
                    "date": day, "ticker": t, "direction": "sell",
                    "size_pct": trade_value, "friction_cost": friction_cost,
                    "gross_return": gross_return,
                })
                del holdings_units[t]
                gross_units.pop(t, None)
                holding_days.pop(t, None)
                open_trades.pop(t, None)

        # Open/adjust positions
        for t, tw in target_weights.items():
            df_t = ticker_data.get(t)
            if df_t is None:
                continue
            mask_open = df_t["timestamps"] <= next_day
            if not mask_open.any():
                continue
            exec_price = float(df_t.loc[mask_open, "open"].iloc[-1])

            target_value = tw * portfolio_value
            current_units = holdings_units.get(t, 0)
            # Compute current value using today's close (already have from above)
            current_value = 0.0
            if current_units > 0:
                mask_day = df_t["timestamps"] <= day
                if mask_day.any():
                    current_value = current_units * float(df_t.loc[mask_day, "close"].iloc[-1])

            trade_value = target_value - current_value
            if abs(trade_value) < 1e-6:
                continue

            units_delta = trade_value / exec_price
            cls = get_ticker_class(t) or "us_equity"
            frict = FRICTION.get(cls, {"commission_oneway": 0.003, "slippage_oneway": 0.001})
            friction_cost = abs(trade_value) * (frict["commission_oneway"] + frict["slippage_oneway"])

            direction = "buy" if trade_value > 0 else "sell"
            cash -= trade_value + friction_cost
            gross_cash -= trade_value  # same units delta, no friction

            holdings_units[t] = holdings_units.get(t, 0) + units_delta
            if holdings_units[t] <= 1e-10:
                del holdings_units[t]
                holding_days.pop(t, None)

            trades_list.append({
                "date": day, "ticker": t, "direction": direction,
                "size_pct": abs(trade_value), "friction_cost": friction_cost,
                "gross_return": 0.0,  # filled on close
            })
            # Track open trade for gross_return computation
            open_trades[t] = {"entry_price": exec_price, "units": holdings_units.get(t, 0),
                              "trade_value": abs(trade_value), "entry_date": day}

        # Update holding days
        for t in list(holdings_units.keys()):
            if holdings_units.get(t, 0) > 0:
                holding_days[t] = holding_days.get(t, 0) + 1

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

    # Build result DataFrames
    equity_curve = pd.Series(portfolio_values, index=trading_days[:len(portfolio_values)])
    gross_equity_curve = pd.Series(gross_portfolio_values, index=trading_days[:len(gross_portfolio_values)])
    daily_returns = equity_curve.pct_change().dropna()
    trades_df = pd.DataFrame(trades_list)

    # Metrics
    from kth.backtest.metrics import compute_metrics
    metrics = compute_metrics(equity_curve, daily_returns, trades_df,
                              benchmarks.get("equal_weight", equity_curve))

    # Per-class attribution
    per_class = _compute_attribution(trades_df, eligible)

    return BacktestResult(
        config=config,
        equity_curve=equity_curve,
        gross_equity_curve=gross_equity_curve,
        trades=trades_df,
        daily_returns=daily_returns,
        benchmarks=benchmarks,
        metrics=metrics,
        per_class_attribution=per_class,
    )
```

> **Note:** `_compute_benchmarks` and `_compute_attribution` are helper functions defined alongside `run_walkforward`:

```python
def _compute_benchmarks(config: BacktestConfig, tickers: list[str], ticker_data: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.Series]:
    """Compute 4 benchmark equity curves: SET, SPY, 60_40, equal_weight.
    Accepts preloaded ticker_data dict to avoid redundant parquet reads in equal-weight benchmark."""
    from kth.data.loader import load_cached
    benchmarks = {}
    trading_days = pd.bdate_range(start=config.start_date, end=config.end_date, freq="B")
    start_ts = pd.Timestamp(config.start_date)

    # SET buy-and-hold
    try:
        set_df = load_cached("^SET.BK", config.cache_dir)
        set_close = set_df.set_index("timestamps")["close"]
        set_aligned = set_close.reindex(trading_days, method="ffill").dropna()
        if len(set_aligned) > 0:
            benchmarks["SET"] = set_aligned / set_aligned.iloc[0]
    except Exception:
        benchmarks["SET"] = pd.Series(1.0, index=trading_days)

    # SPY buy-and-hold
    try:
        spy_df = load_cached("SPY", config.cache_dir)
        spy_close = spy_df.set_index("timestamps")["close"]
        spy_aligned = spy_close.reindex(trading_days, method="ffill").dropna()
        if len(spy_aligned) > 0:
            benchmarks["SPY"] = spy_aligned / spy_aligned.iloc[0]
    except Exception:
        benchmarks["SPY"] = pd.Series(1.0, index=trading_days)

    # 60/40 SPY/TLT monthly rebalance
    try:
        spy = load_cached("SPY", config.cache_dir).set_index("timestamps")["close"]
        tlt = load_cached("TLT", config.cache_dir).set_index("timestamps")["close"]
        combined = pd.concat([spy.rename("spy"), tlt.rename("tlt")], axis=1).dropna()
        rebal_dates = pd.date_range(start=config.start_date, end=config.end_date, freq="MS")
        values = []
        w_spy, w_tlt = 0.6, 0.4
        spy_units = w_spy / combined.iloc[0]["spy"]
        tlt_units = w_tlt / combined.iloc[0]["tlt"]
        for day in trading_days:
            if day in rebal_dates and day in combined.index:
                val = spy_units * combined.loc[day, "spy"] + tlt_units * combined.loc[day, "tlt"]
                spy_units = w_spy * val / combined.loc[day, "spy"]
                tlt_units = w_tlt * val / combined.loc[day, "tlt"]
            if day in combined.index:
                val = spy_units * combined.loc[day, "spy"] + tlt_units * combined.loc[day, "tlt"]
            values.append(val)
        benchmarks["60_40"] = pd.Series(values, index=trading_days) / values[0] if values else pd.Series(1.0, index=trading_days)
    except Exception:
        benchmarks["60_40"] = pd.Series(1.0, index=trading_days)

    # Equal-weight — NORMALIZED to 1.0 at start (not mean of raw prices)
    # Uses preloaded ticker_data if available, otherwise falls back to load_cached
    try:
        eq_series = pd.Series(1.0, index=trading_days)
        for day_idx, day in enumerate(trading_days):
            norm_vals = []
            for t in tickers:
                try:
                    df_t = ticker_data.get(t) if ticker_data else None
                    if df_t is None:
                        df_t = load_cached(t, config.cache_dir)
                    close_mask = df_t["timestamps"] <= day
                    start_mask = df_t["timestamps"] <= start_ts
                    if close_mask.any() and start_mask.any():
                        price = float(df_t.loc[close_mask, "close"].iloc[-1])
                        start_price = float(df_t.loc[start_mask, "close"].iloc[-1])
                        if start_price > 0:
                            norm_vals.append(price / start_price)
                except Exception:
                    continue
            if norm_vals:
                eq_series.iloc[day_idx] = np.mean(norm_vals)
        benchmarks["equal_weight"] = eq_series
    except Exception:
        benchmarks["equal_weight"] = pd.Series(1.0, index=trading_days)

    return benchmarks


def _compute_attribution(trades: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Per-class attribution of P&L, hit-rate, friction."""
    from kth.data.universe import get_ticker_class
    if trades.empty:
        return pd.DataFrame(columns=["asset_class", "pnl", "hit_rate", "friction_paid"])
    trades = trades.copy()
    trades["asset_class"] = trades["ticker"].apply(lambda t: get_ticker_class(t) or "unknown")
    attribution = trades.groupby("asset_class").agg(
        pnl=("gross_return", "sum"),
        hit_rate=("gross_return", lambda x: (x > 0).mean()),
        friction_paid=("friction_cost", "sum"),
        trade_count=("ticker", "count"),
    ).reset_index()
    return attribution
```

- [ ] **Step 2: Verify import**

Run: `python -c "from kth.backtest.walkforward import run_walkforward, BacktestResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add kth/backtest/walkforward.py
git commit -m "feat: add run_walkforward simulation loop with strict no-look-ahead"
```

---

### Task 6: BacktestResult `save()` and `load()`

**Files:**
- Modify: `kth/backtest/walkforward.py`

- [ ] **Step 1: Move BacktestResult to final position (already in file) and implement load()**

The `save()` method is already in Task 5's BacktestResult. Add `load()`:

```python
    @classmethod
    def load(cls, dir_path: str) -> "BacktestResult":
        out = Path(dir_path)
        equity_curve = pd.read_parquet(out / "equity_curve.parquet")["equity"]
        gross = pd.read_parquet(out / "gross_equity_curve.parquet")["gross_equity"]
        trades = pd.read_parquet(out / "trades.parquet")
        daily_returns = pd.read_parquet(out / "daily_returns.parquet")["daily_returns"]
        benchmarks = {}
        for bm_file in out.glob("benchmark_*.parquet"):
            name = bm_file.stem.replace("benchmark_", "")
            benchmarks[name] = pd.read_parquet(bm_file).iloc[:, 0]
        per_class = pd.read_parquet(out / "per_class_attribution.parquet")
        with open(out / "metrics.json") as f:
            metrics = json.load(f)
        with open(out / "config.json") as f:
            config_dict = json.load(f)
        config = BacktestConfig(**config_dict)
        return cls(
            config=config, equity_curve=equity_curve, gross_equity_curve=gross,
            trades=trades, daily_returns=daily_returns, benchmarks=benchmarks,
            metrics=metrics, per_class_attribution=per_class,
        )
```

- [ ] **Step 2: Commit**

```bash
git add kth/backtest/walkforward.py
git commit -m "feat: add BacktestResult save/load serialization"
```

---

### Task 7: Notebook 03 — Walk-forward backtest notebook

**Files:**
- Create: `notebooks/03_walkforward_backtest.ipynb`

**Cells:**
1. Mount Drive, import deps
2. Load KronosTH zero-shot, define BacktestConfig
3. `precompute_forecasts(k, get_all_tickers(), ...)` — first run ~3-5 hrs; subsequent instant
4. `result = run_walkforward(config, k, get_all_tickers())`
5. Plot net equity curve vs 4 benchmarks
6. Print full metrics table (gross vs net)
7. Drawdown chart
8. Per-class attribution bar chart
9. Re-run with `position_sizing="inv_vol"`, compare
10. Commentary cell

- [ ] **Step 1: Create and run on Colab, save to repo**

---

### Self-Review

- [x] Spec coverage: All sections — BacktestConfig, precompute_forecasts, walk-forward loop with hysteresis buffer, position sizing modes, metrics, benchmarks, attribution, save/load
- [x] Placeholder scan: No TBDs. Placeholder `_CachedHorizon`/`_CachedResult` classes handle cached forecast loading.
- [x] Type consistency: `BacktestConfig.position_sizing` used consistently in `compute_weights()`. `pred_len` from config flows through to strategy and forecasts.
