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
