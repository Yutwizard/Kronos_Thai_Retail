"""Synthetic OHLCV data generation for offline testing (no yfinance)."""
import numpy as np
import pandas as pd

from kth.data.universe import get_ticker_class


def make_synthetic_yf(ticker: str, n_days: int = 1260, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cls = get_ticker_class(ticker)
    vol_per_day = {
        "thai_equity": 0.015, "thai_index": 0.010, "us_equity": 0.018,
        "etf_global": 0.010, "commodity": 0.012, "crypto": 0.045,
        "bond_proxy": 0.005, "reit": 0.013, "fx_macro": 0.005,
    }.get(cls, 0.015)
    drift_per_day = 0.0003
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(),
                           periods=n_days, freq="B", name="Date")
    n = len(dates)
    log_rets = rng.normal(drift_per_day, vol_per_day, n)
    close = 100.0 * np.exp(np.cumsum(log_rets))
    intra_range = np.abs(rng.normal(0, vol_per_day, n))
    high = close * (1 + intra_range)
    low = close * (1 - intra_range)
    open_ = np.concatenate([[close[0]], close[:-1]]) * (
        1 + rng.normal(0, vol_per_day * 0.3, n)
    )
    base_vol = 1_000_000 * (1 + 5 * np.abs(log_rets))
    volume = (base_vol * rng.uniform(0.7, 1.3, n)).astype(np.int64)
    df = pd.DataFrame(
        {"Open": open_, "High": np.maximum.reduce([open_, close, high]),
         "Low": np.minimum.reduce([open_, close, low]),
         "Close": close, "Volume": volume},
        index=dates,
    )
    return df
