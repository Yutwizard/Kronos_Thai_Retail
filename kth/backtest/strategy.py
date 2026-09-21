"""Pure strategy functions: signal generation, position selection, weight computation."""
from __future__ import annotations

import numpy as np
import pandas as pd


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
        inv_vols = {}
        for t in selected:
            vol = recent_vols.get(t, 0.01)
            if vol is None or pd.isna(vol) or vol <= 0:
                vol = 0.01
            inv_vols[t] = 1.0 / max(vol, 1e-8)
        total = sum(inv_vols.values())
        return {t: inv_vols[t] / total for t in selected}

    raise ValueError(f"Unknown position_sizing mode: {mode}")


def apply_hysteresis(
    raw_signals: dict[str, float],
    holdings: dict[str, float],
    holding_days: dict[str, int],
    config_long_threshold: float,
    config_entry_buffer: float,
    config_min_holding_days: int,
    max_holding_days: int | None = None,
    cooldown_days: int | None = None,
    cooldown_remaining: dict[str, int] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply entry/exit hysteresis to raw signals.

    Returns (signals, signals_for_ranking):
      - signals: {ticker: 0 or 1 or signal_value} — 0=close, 1=hold, value=open
      - signals_for_ranking: {ticker: signal_value} — only held + newly opened

    `max_holding_days`/`cooldown_days`/`cooldown_remaining` are an experimental,
    disabled-by-default extension (see Wayfinder map .scratch/optimize-entry-exit):
    when `max_holding_days` is set, a position is force-closed once its holding
    days reach the cap regardless of signal, and `cooldown_remaining[t]` is set
    to `cooldown_days` to block re-entry. The caller owns `cooldown_remaining`
    and is responsible for decrementing it once per day — apply_hysteresis only
    reads it (for the entry gate) and writes it (on a forced exit).
    """
    signals: dict[str, float] = {}
    signals_for_ranking: dict[str, float] = {}
    if cooldown_remaining is None:
        cooldown_remaining = {}
    for t, sig in raw_signals.items():
        if t in holdings and holdings[t] > 0:
            days_held = holding_days.get(t, 0)
            forced_exit = max_holding_days is not None and days_held >= max_holding_days
            hysteresis_exit = (sig < config_long_threshold - config_entry_buffer
                                and days_held >= config_min_holding_days)
            if forced_exit or hysteresis_exit:
                signals[t] = 0
                if forced_exit and cooldown_days:
                    cooldown_remaining[t] = cooldown_days
            else:
                signals[t] = 1
                signals_for_ranking[t] = sig
        else:
            if cooldown_remaining.get(t, 0) > 0:
                continue
            if sig > config_long_threshold + config_entry_buffer:
                signals[t] = sig
                signals_for_ranking[t] = sig
    return signals, signals_for_ranking


def compute_median_vol_series(
    ticker_data: dict[str, pd.DataFrame],
    vol_lookback: int = 20,
) -> pd.Series:
    """Daily cross-sectional median of each ticker's rolling std of daily returns.

    Each value uses only closes up to and including its own date.
    """
    vols = {}
    for ticker, df in ticker_data.items():
        close = df.set_index(pd.to_datetime(df["timestamps"]))["close"]
        vols[ticker] = close.pct_change(fill_method=None).rolling(vol_lookback).std()
    return pd.DataFrame(vols).median(axis=1, skipna=True).dropna()


def compute_regime_adjusted_threshold(
    base_threshold: float,
    base_buffer: float,
    vol_series: pd.Series,
    day: pd.Timestamp,
    percentile: float = 80.0,
    min_history: int = 252,
    multiplier: float = 2.0,
) -> tuple[float, float]:
    """Raise the entry buffer when today's median volatility is historically high."""
    history = vol_series[vol_series.index < day]
    if len(history) < min_history:
        return base_threshold, base_buffer
    if day in vol_series.index and vol_series.loc[day] > np.percentile(history.to_numpy(), percentile):
        return base_threshold, base_buffer * multiplier
    return base_threshold, base_buffer


def find_stopped_positions(
    held_closes: dict[str, float],
    entry_prices: dict[str, float],
    peak_prices: dict[str, float],
    stop_loss: float | None = None,
    trailing_stop: float | None = None,
) -> set[str]:
    """Held tickers whose latest close is at or below the fixed stop (from entry) or the trailing stop (from peak)."""
    stopped = set()
    for t, close in held_closes.items():
        if stop_loss is not None and close <= entry_prices[t] * (1 - stop_loss):
            stopped.add(t)
        elif trailing_stop is not None and close <= peak_prices[t] * (1 - trailing_stop):
            stopped.add(t)
    return stopped
