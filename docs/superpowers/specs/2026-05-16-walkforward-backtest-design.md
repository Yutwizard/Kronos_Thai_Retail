# Spec B — Walk-forward Backtest

**Date:** 2026-05-16
**Subsystem:** `kth/backtest/` + `notebooks/03_walkforward_backtest.ipynb`
**Depends on:** Spec A (`KronosTH` wrapper), `kth/data/` (complete)
**Blocks:** Spec D (decision report uses the same FRICTION model and metrics)
**Status:** Approved

---

## Purpose

A strict walk-forward backtester that:
- Generates signals using only data available at each point in time (no look-ahead)
- Applies Thai-retail-realistic FRICTION on every position change
- Reports a professional-grade metric set gross and net of costs
- Compares the strategy against four honest benchmarks

Scope: **long-only**, **all 51 tickers**, **position sizing configurable** (equal-weight, signal-strength, or inverse-volatility).

---

## Module Layout

```
kth/backtest/
├── __init__.py
├── walkforward.py    # simulation loop + BacktestResult
├── strategy.py       # signal generation + position sizing
└── metrics.py        # pure metric functions
```

---

## `BacktestConfig`

```python
@dataclass
class BacktestConfig:
    start_date: str                  # ISO date, e.g. "2022-01-01"
    end_date: str                    # ISO date, e.g. "2024-12-31"
    lookback: int = 400              # context window rows per forecast call
    pred_len: int = 20               # horizon used to compute the signal
    n_samples: int = 50              # samples per forecast (more = better calibration)
    long_threshold: float = 0.01    # median forecast return > this → long signal
    entry_buffer: float = 0.005     # open only if return > threshold + buffer; close only if < threshold - buffer (Issue #2)
    min_holding_days: int = 5        # minimum days to hold a position before closing (Issue #2)
    max_positions: int = 5           # cap on simultaneous open positions
    position_sizing: str = "equal"   # "equal" | "signal" | "inv_vol"
    inv_vol_window: int = 20         # rolling window for inv_vol sizing
    trading_calendar: str = "NYSE"   # anchor calendar for loop days; per-ticker signals only on their own available dates (Issue #3)
    min_ticker_history: int = 252    # exclude tickers with fewer rows of post-lookback history in test period (Issue #12)
    forecast_cache_dir: str = "./data/forecast_cache"  # precomputed ForecastResult cache (Issue #1)
    cache_dir: str = "./data/raw"
```

`position_sizing` modes:
| Mode | Logic |
|---|---|
| `"equal"` | Each active signal: weight = 1 / min(n_signals, max_positions) |
| `"signal"` | Weight ∝ rank(median forecast return) among active positions (rank-based, not raw return, to prevent extreme concentration); normalised to sum to 1 |
| `"inv_vol"` | Weight ∝ 1 / rolling_std(close, inv_vol_window); normalised to sum to 1 |

---

## Data Structures

```python
@dataclass
class BacktestResult:
    config: BacktestConfig
    equity_curve: pd.Series              # daily portfolio value, DatetimeIndex
    gross_equity_curve: pd.Series        # same but before friction deduction
    trades: pd.DataFrame                 # date, ticker, direction, size_pct, friction_cost
    daily_returns: pd.Series             # net daily returns
    benchmarks: dict[str, pd.Series]    # "SET", "SPY", "60_40", "equal_weight"
    metrics: dict                        # full professional metric set (see below)
    per_class_attribution: pd.DataFrame  # asset_class → P&L, hit_rate, friction_paid

    def save(self, dir: str) -> None:
        """Serialise to disk: DataFrames → parquet, scalars → JSON. No pickle. (Issue #8)"""

    @classmethod
    def load(cls, dir: str) -> "BacktestResult":
        """Load from a save() directory."""
```

---

## Forecast Precomputation (Issue #1)

Running `forecast()` inside the daily loop for 51 tickers × ~750 days = 38,250 forward passes (~21–53 hours on T4). Instead, separate precomputation from simulation:

```python
def precompute_forecasts(
    kronosTH: KronosTH,
    tickers: list[str],
    start_date: str,
    end_date: str,
    pred_len: int,
    n_samples: int,
    lookback: int,
    cache_dir: str = "./data/forecast_cache",
) -> None:
    """
    Run forecast_batch() once per trading day and persist each ForecastResult
    to cache_dir/{model_slug}/{date}/{ticker}.parquet + {ticker}_meta.json.
    Idempotent — skips dates already cached.
    """
```

**Cache path includes model identity:** The full cache path is `cache_dir/{model_slug}/{date}/{ticker}.parquet` where `model_slug` is derived from `kronosTH.model_name` with `/` replaced by `_` and `@` replaced by `-` (e.g. `NeoQuasar_Kronos-small-a3f1c2d`). This prevents stale forecasts from a previous model silently polluting a backtest run after the model is switched. `run_walkforward()` receives the same `model_slug` and reads from the correct subdirectory. Two different models (zero-shot vs fine-tuned) always write to separate directories.

`run_walkforward()` checks the cache first. If a (date, ticker) pair is already computed, it loads from disk instead of calling the model. This makes repeated backtest runs (different configs, different thresholds) nearly instant after the first precomputation pass.

---

## Walk-forward Loop (`walkforward.py`)

```
Initialise: cash=1.0, holdings_units={}, holding_days={}, equity_history=[], gross_equity_history=[]

# Pre-load all ticker DataFrames into memory ONCE to avoid per-iteration parquet reads
ticker_data: dict[str, pd.DataFrame] = {t: load_cached(t) for t in eligible_tickers}

# Pre-filter: exclude tickers with < min_ticker_history post-lookback rows in test period (Issue #12)
eligible_tickers = [t for t in universe if sufficient_history(t, config)]

for each day t in config.trading_calendar between [start_date, end_date]:  # Issue #3

  1. FORECAST — load from precomputed cache (Issue #1)
     for each ticker in eligible_tickers:
       if ticker has no data on day t (e.g. Thai holiday, ticker not yet listed): skip
       result = load_forecast_cache(t, ticker, cache_dir)
       median_return = result.horizons[pred_len].summary["p50"].iloc[-1]
                       / last_close_at_t - 1

  2. SIGNAL with hysteresis buffer (Issue #2)
     for each ticker currently NOT held:
       signal = 1 if median_return > long_threshold + entry_buffer
     for each ticker currently held:
       signal = 0 if median_return < long_threshold - entry_buffer
              AND holding_days[ticker] >= min_holding_days
       signal = 1 otherwise  # hold: either buffer not breached or min hold not met
     # IMPORTANT: held positions retain their actual signal strength for ranking,
     # NOT the placeholder '1'. Store separately: {ticker: raw_median_return}

  3. POSITION SIZING
     active = tickers where signal == 1 (may be < max_positions; use however many qualify)
     # Held positions use their actual signal value, new candidates use raw signal
     top_n = top min(len(active), max_positions) tickers by median_return (alpha sort if tied)
     target_weights = apply sizing mode to top_n
     target_weights[not in top_n] = 0
     if len(top_n) == 0: portfolio stays in cash, no trades

  4. TRADES (execute at t+1 open, decided at t close)
     # Size trades against CURRENT portfolio_value (not initial cash)
     portfolio_value = cash + sum(holdings_units[t] * close_price[t])
     for each ticker where target_weight != current_weight:
       target_value = target_weight * portfolio_value
       trade_value = abs(target_value - current_position_value)
       # Convert trade value to units at execution price
       units = trade_value / price_at_t  # t+1 open
       friction = trade_value * (FRICTION[class]["commission_oneway"]
                               + FRICTION[class]["slippage_oneway"])
       holdings_units[t] += sign * units
       cash -= sign * units * price_at_t + friction
       record trade with entry_price, units, friction_cost
     update holding_days: +1 for held positions, reset to 0 on close

  5. MARK TO MARKET at t+1 close (positions execute at open, P&L marks at close)
     portfolio_value = cash + sum(holdings_units[t] * close_at_t[t+1])
     gross_portfolio_value = cash_before_friction + sum(...)  # parallel tracker

  append portfolio_value to equity_history
  append gross_portfolio_value to gross_equity_history
  daily_returns = equity_curve.pct_change()  # derived after loop completes

  # Fill trade gross_return: for trades closed this day, compute
  # (exit_price - entry_price) / entry_price * trade_value
```

**Accounting model: units, not weights.** The simulation tracks `holdings_units[t]` (number of shares/contracts owned) and a `cash` balance. Trade sizing converts target weights to units using the current `portfolio_value`, not the initial $1 cash. This is the only approach that handles portfolio growth/decay correctly. Gross equity is computed in parallel — a shadow `gross_cash` that tracks the same units but never deducts friction.

**Data preloading:** All ticker DataFrames are loaded into `ticker_data` dict once before the daily loop. The loop accesses via `ticker_data[t]` (in-memory dict lookup, ~ns) instead of `load_cached(t)` (disk read, ~ms). For 51 tickers × 750 days, this saves ~76,500 parquet reads per backtest run.

**No-look-ahead guarantee:** precomputed forecasts are stored keyed by `(date, ticker)`. `precompute_forecasts()` slices `df[df.timestamps <= date].tail(lookback)` before calling the model. The slice is enforced in precomputation, not trusted to the caller.

---

## Strategy module (`strategy.py`)

Pure functions, stateless. No class needed.

```python
def compute_signals(
    forecasts: dict[str, ForecastResult],
    last_closes: dict[str, float],
    threshold: float,
    pred_len: int,
) -> dict[str, float]:
    """Returns {ticker: median_forecast_return}. Only tickers above threshold included."""

def select_positions(
    signals: dict[str, float],
    signals_raw: dict[str, float],  # held positions' actual signal strength, not '1'
    max_positions: int,
) -> list[str]:
    """Top-N tickers by signal strength. Held positions use their actual signal value
    for ranking (from signals_raw), so a strong-held position isn't ejected by a weak
    new candidate that happens to score above 1.0."""

def compute_weights(
    selected: list[str],
    signals: dict[str, float],
    recent_vols: dict[str, float],
    mode: str,
) -> dict[str, float]:
    """Returns {ticker: portfolio_weight} summing to 1.0."""
```

---

## Metrics (`metrics.py`)

All functions are pure: `(equity_curve, trades, benchmark, rf=0.02, periods_per_year=252) → dict`.

### Return metrics
- `CAGR` — annualised compound growth rate
- `total_return` — total % over the period
- `annualised_vol` — annualised standard deviation of daily returns
- `sharpe` — annualised Sharpe with `rf=0.02`
- `sortino` — Sharpe using downside deviation only
- `calmar` — CAGR / max_drawdown
- `omega` — probability-weighted ratio of gains to losses (threshold=0)
- `information_ratio` — excess return / tracking error vs benchmark
- `alpha`, `beta` — vs SET Index and SPY (OLS regression of daily returns)

### Drawdown metrics
- `max_drawdown` — peak-to-trough maximum (%)
- `avg_drawdown` — mean of all drawdown periods (%)
- `max_drawdown_duration` — longest peak-to-trough-to-recovery (calendar days)
- `avg_drawdown_duration` — mean drawdown duration
- `ulcer_index` — RMS of all drawdown observations

### Trade-level metrics
- `hit_rate` — % of closed trades with positive gross return
- `payoff_ratio` — mean win / mean loss (absolute)
- `profit_factor` — gross profit / gross loss
- `avg_holding_period` — mean calendar days position held
- `avg_trade_return_gross`, `avg_trade_return_net`
- `max_win_streak`, `max_loss_streak`

### Risk metrics
- `var_95`, `var_99` — 1-day **historical** VaR: `np.percentile(daily_returns, [5, 1])` (Issue #6 — parametric normal VaR is replaced; financial returns are fat-tailed, especially crypto and Thai mid-caps; historical quantile is model-free and always valid)
- `cvar_95` — Expected Shortfall at 95%: mean of returns below `var_95`
- `annual_turnover` — total traded value / average portfolio value / years

### Cost metrics
- `total_friction_paid` — sum of all FRICTION costs (portfolio units)
- `sharpe_gross`, `sharpe_net` — both reported; gap shows friction drag

### Statistical significance
- `t_stat` — t-statistic on excess daily return vs equal-weight benchmark
- `p_value` — two-sided p-value

All metrics computed **gross and net** and stored in `BacktestResult.metrics` as flat dict with `_gross` / `_net` suffix where both versions exist.

---

## Benchmarks

Computed once from cached parquet, outside the walk-forward loop.

| Key | Definition |
|---|---|
| `"SET"` | Buy-and-hold `^SET.BK` over the test period |
| `"SPY"` | Buy-and-hold `SPY` |
| `"60_40"` | 60% SPY + 40% TLT, rebalanced monthly |
| `"equal_weight"` | Equal-weight all 51 eligible tickers, **rebalanced monthly** (Issue #10 — without rebalancing the benchmark drifts into whichever asset class performs best, making it an unfair comparison; monthly rebalance creates a stable 1/N reference portfolio). Each ticker is normalized to 1.0 at the start date; the portfolio value is the arithmetic mean of the normalized values. Using raw prices would let BTC-USD ($100K) dominate the 1/N basket. |

---

## Notebook 03 — Walk-forward backtest

Cells:
1. Load `KronosTH` (zero-shot, Kronos-small)
2. `BacktestConfig(start_date="2022-01-01", end_date="2024-12-31")`
3. `precompute_forecasts(k, get_all_tickers(), ...)` — run once, ~3–5 hrs on T4; subsequent runs load from cache
4. `result = run_walkforward(config, k, get_all_tickers())`  # reads from cache only; k needed for model_slug to locate correct cache directory
5. Plot equity curve (net) vs all 4 benchmarks
6. Print full metrics table (gross vs net side-by-side)
7. Drawdown chart with shaded periods
8. Per-class attribution bar chart
9. Commentary: which classes helped/hurt, what did frictions cost
10. Re-run with `position_sizing="inv_vol"` and compare Sharpe curves

---

## Files to Create

| File | Purpose |
|---|---|
| `kth/backtest/__init__.py` | Package marker |
| `kth/backtest/walkforward.py` | `BacktestConfig`, `BacktestResult`, `run_walkforward()`, `precompute_forecasts()` |
| `kth/backtest/strategy.py` | `compute_signals()`, `select_positions()`, `compute_weights()` |
| `kth/backtest/metrics.py` | All metric functions |
| `notebooks/03_walkforward_backtest.ipynb` | Backtest notebook |
| `data/forecast_cache/` | Precomputed `ForecastResult` cache (parquet + JSON per date/ticker) |
