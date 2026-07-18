"""DR data loader — bundles underlying, DR, and FX OHLCV data."""
from kth.data.loader import load_cached, download_universe
from kth_dr.universe_dr import get_dr_info_for_display


def load_dr_bundle(underlying_ticker: str) -> dict[str, object]:
    """Load underlying OHLCV, DR OHLCV, and FX rate for a DR position.

    Returns dict with keys: underlying_ohlcv, dr_ohlcv, fx_ohlcv, dr_info.
    Raises FileNotFoundError (via load_cached) if any series isn't cached yet.
    """
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        raise FileNotFoundError(f"No DR info found for {underlying_ticker}")

    return {
        "underlying_ohlcv": load_cached(underlying_ticker),
        "dr_ohlcv": load_cached(dr_info["dr_ticker"]),
        "fx_ohlcv": load_cached(dr_info["fx_ticker"]),
        "dr_info": dr_info,
    }


def compute_dr_premium_pct(execution_close: float, underlying_close: float, fx_close: float, ratio: float) -> float:
    """DR premium: execution_close vs. intrinsic value (underlying_close × fx_close ÷ ratio).
    Raises ValueError on missing/zero inputs — the caller decides how to handle
    an unavailable premium (e.g. blank cell, skip enrichment), this function
    never guesses a fallback value."""
    if not underlying_close or not fx_close or not ratio:
        raise ValueError("missing underlying_close/fx_close/ratio for DR premium calculation")
    dr_intrinsic = (underlying_close * fx_close) / ratio
    if not dr_intrinsic:
        raise ValueError("computed zero DR intrinsic value")
    return round((execution_close / dr_intrinsic) - 1, 4)


def ensure_dr_data(underlying_ticker: str) -> None:
    """Download all data sources required for a DR position. Idempotent —
    download_universe/load_cached already skip re-downloading cached tickers.
    Useful for ad-hoc/manual use (e.g. checking a candidate before it's
    verified). The daily pipeline itself does NOT call this — see Step 2:
    it folds DR tickers into the same ticker list everything else already
    goes through, so they ride the existing batched download/cache path
    instead of a second, parallel one."""
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        return
    tickers = [underlying_ticker, dr_info["dr_ticker"]]
    if dr_info.get("fx_ticker"):
        tickers.append(dr_info["fx_ticker"])
    download_universe(tickers)
