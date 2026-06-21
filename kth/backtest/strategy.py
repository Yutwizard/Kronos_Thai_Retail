"""Pure strategy functions: signal generation, position selection, weight computation."""
from __future__ import annotations

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
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply entry/exit hysteresis to raw signals.

    Returns (signals, signals_for_ranking):
      - signals: {ticker: 0 or 1 or signal_value} — 0=close, 1=hold, value=open
      - signals_for_ranking: {ticker: signal_value} — only held + newly opened
    """
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
