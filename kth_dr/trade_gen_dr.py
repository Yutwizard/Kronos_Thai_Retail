"""DR-specific trade generation helpers — execution ticker/price/name
resolution, and the same-underlying guard used by trade_gen.py's buy loop."""
from kth_dr.universe_dr import get_dr_for_underlying, get_underlying_for_dr, get_dr_info_for_display


def resolve_execution_ticker(ticker: str) -> str:
    """Given an underlying ticker, return its DR ticker if a verified one
    exists. Identity for non-DR tickers."""
    dr = get_dr_for_underlying(ticker)
    if dr:
        return dr["dr_ticker"]
    return ticker


def resolve_execution_price(underlying_ticker: str, execution_ticker: str, underlying_close: float) -> float:
    """Return the price to actually trade at. For a DR position this MUST be
    the DR's own SET close (in THB) — never the underlying's raw
    foreign-currency close. `underlying_close` is returned unchanged when
    there's no DR (execution_ticker == underlying_ticker)."""
    if execution_ticker == underlying_ticker:
        return underlying_close
    from kth.data.loader import load_cached
    return float(load_cached(execution_ticker)["close"].iloc[-1])


def resolve_display_name(underlying_ticker: str, fallback: str) -> str:
    """Prefer the DR mapping's display_name (e.g. 'Samsung Electronics') over
    the raw underlying ticker string, which usually has no friendly name in
    universe.py's _DISPLAY_NAME_MAP."""
    dr = get_dr_for_underlying(underlying_ticker)
    if not dr:
        return fallback
    info = get_dr_info_for_display(dr["dr_ticker"])
    return info["display_name"] if info else fallback


def get_underlying_for_held(ticker: str) -> str:
    """If ticker is a DR, return its underlying. Identity for non-DR tickers.
    Used by the same-underlying guard in the buy loop."""
    underlying = get_underlying_for_dr(ticker)
    return underlying if underlying else ticker


def is_held_underlying(held_tickers: list[str], candidate_underlying: str) -> bool:
    """True if candidate_underlying is already held, whether directly or via
    a DR — prevents holding e.g. both AAPL and AAPL80.BK at once."""
    for held in held_tickers:
        if get_underlying_for_held(held) == candidate_underlying:
            return True
    return False
