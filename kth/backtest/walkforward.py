"""Walk-forward backtest simulation with strict no-look-ahead."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

import numpy as np
import pandas as pd


def _get_calendar_for_tickers(tickers: list[str]) -> str:
    """Return 'B' for equities (business days) or 'D' for crypto (calendar days).

    Known limitation: returns "D" if ANY crypto ticker is present, applying the
    crypto (7-day) calendar to ALL tickers in the run — including equities.
    This is a design trade-off: a single backtest run uses one calendar.
    Separate crypto-only and equity-only runs to avoid this."""
    from kth.data.universe import get_ticker_class
    classes = {get_ticker_class(t) for t in tickers}
    if "crypto" in classes:
        return "D"
    return "B"


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


def _model_slug(model_name: str) -> str:
    """Convert model_name to a filesystem-safe slug for cache directory naming.
    e.g. 'NeoQuasar/Kronos-small@a3f1c2d' -> 'NeoQuasar_Kronos-small-a3f1c2d'
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

    # Pre-filter tickers that have enough data for lookback
    from kth.data.loader import load_cached
    viable = []
    for t in tickers:
        try:
            df = load_cached(t)
            if len(df) >= lookback:
                viable.append(t)
        except FileNotFoundError:
            continue
    if len(viable) < len(tickers):
        print(f"[precompute] Skipped {len(tickers) - len(viable)} tickers (insufficient history)")
    tickers = viable

    freq = _get_calendar_for_tickers(tickers)
    print(f"[precompute] Calendar: {'7-day (crypto)' if freq == 'D' else '5-day (business)'}")
    trading_days = pd.date_range(start=start_date, end=end_date, freq=freq)

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
        results = kronos_th.forecast_batch(uncached, pred_lens=[pred_len], n_samples=n_samples,
                                            lookback=lookback, calendar_freq=freq)

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
            safe_metrics = {
                k: (None if isinstance(v, float) and (math.isinf(v) or math.isnan(v)) else v)
                for k, v in self.metrics.items()
            }
            json.dump(safe_metrics, f)
        with open(out / "config.json", "w") as f:
            json.dump(self.config.__dict__, f)

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

    freq = _get_calendar_for_tickers(eligible)
    print(f"Calendar: {'7-day (crypto)' if freq == 'D' else '5-day (business)'}")
    trading_days = pd.date_range(start=config.start_date, end=config.end_date, freq=freq)

    # ---- PRELOAD all ticker data into memory ONCE ----
    ticker_data: dict[str, pd.DataFrame] = {}
    for t in eligible:
        try:
            ticker_data[t] = load_cached(t, config.cache_dir)
        except FileNotFoundError:
            continue

    # Compute benchmarks once
    benchmarks = _compute_benchmarks(config, eligible, ticker_data, freq=freq)

    # ---- Portfolio state (UNITS-BASED) ----
    cash = 1.0
    gross_cash = 1.0
    holdings_units: dict[str, float] = {}
    holding_days: dict[str, int] = {}
    portfolio_values: list[float] = []
    gross_portfolio_values: list[float] = []
    mark_days: list = []
    trades_list: list[dict] = []
    open_trades: dict[str, dict] = {}

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
            df_t = ticker_data.get(t)
            if df_t is not None:
                mask = df_t["timestamps"] <= day
                if mask.any():
                    last_closes[t] = float(df_t.loc[mask, "close"].iloc[-1])

        # --- 2. SIGNAL with hysteresis ---
        raw_signals = compute_signals(forecasts, last_closes, config.long_threshold, config.pred_len)
        signals: dict[str, float] = {}
        signals_for_ranking: dict[str, float] = {}

        for t, sig in raw_signals.items():
            if t in holdings_units and holdings_units[t] > 0:
                if sig < config.long_threshold - config.entry_buffer and holding_days.get(t, 0) >= config.min_holding_days:
                    signals[t] = 0  # close
                else:
                    signals[t] = 1  # hold
                    signals_for_ranking[t] = sig  # real signal value
            else:
                if sig > config.long_threshold + config.entry_buffer:
                    signals[t] = sig  # open
                    signals_for_ranking[t] = sig

        # --- 3. POSITION SIZING ---
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
                        if len(vol_df) >= 2:
                            vol = float(vol_df["close"].pct_change().std())
                        else:
                            vol = 0.02
                        recent_vols[t] = vol if (vol is not None and vol == vol and vol > 0) else 0.02
                except Exception:
                    recent_vols[t] = 0.02

        target_weights = compute_weights(selected, signals_for_ranking, recent_vols, config.position_sizing)

        # --- 4. TRADES (execute at t+1 open prices) ---
        next_day = trading_days[day_idx + 1] if day_idx + 1 < len(trading_days) else day
        portfolio_value = cash
        for t, units in holdings_units.items():
            df_t = ticker_data.get(t)
            if df_t is not None:
                mask = df_t["timestamps"] <= day
                if mask.any():
                    price = float(df_t.loc[mask, "close"].iloc[-1])
                    portfolio_value += units * price

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
                gross_cash += trade_value
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
            gross_cash -= trade_value

            holdings_units[t] = holdings_units.get(t, 0) + units_delta
            if holdings_units[t] <= 1e-10:
                del holdings_units[t]
                holding_days.pop(t, None)

            trades_list.append({
                "date": day, "ticker": t, "direction": direction,
                "size_pct": abs(trade_value), "friction_cost": friction_cost,
                "gross_return": 0.0,
            })
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
        mark_days.append(mark_day)

    # Build result DataFrames — index by mark_day so strategy returns align with benchmark
    mark_index = pd.DatetimeIndex(mark_days[:len(portfolio_values)])
    equity_curve = pd.Series(portfolio_values, index=mark_index)
    gross_equity_curve = pd.Series(gross_portfolio_values, index=mark_index)
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


def _compute_benchmarks(config: BacktestConfig, tickers: list[str], ticker_data: dict[str, pd.DataFrame] | None = None, freq: str = "B") -> dict[str, pd.Series]:
    """Compute 4 benchmark equity curves: SET, SPY, 60_40, equal_weight.
    Accepts preloaded ticker_data dict to avoid redundant parquet reads in equal-weight benchmark.
    freq: "B" for equities (business days), "D" for crypto (calendar days)."""
    from kth.data.loader import load_cached
    benchmarks = {}
    trading_days = pd.date_range(start=config.start_date, end=config.end_date, freq=freq)
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
    """Per-class attribution of P&L, trade-win-rate, friction."""
    from kth.data.universe import get_ticker_class
    if trades.empty:
        return pd.DataFrame(columns=["asset_class", "pnl", "trade_win_rate", "friction_paid"])
    trades = trades.copy()
    trades["asset_class"] = trades["ticker"].apply(lambda t: get_ticker_class(t) or "unknown")
    attribution = trades.groupby("asset_class").agg(
        pnl=("gross_return", "sum"),
        trade_win_rate=("gross_return", lambda x: (x > 0).mean()),
        friction_paid=("friction_cost", "sum"),
        trade_count=("ticker", "count"),
    ).reset_index()
    return attribution
