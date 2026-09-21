"""Clean read of the cached OHLCV for analysis (ticket .scratch/future-plan/13).

Why this module exists: the 2026-09-21 audit found Yahoo "stub rows" (flat, zero-volume candles on real trading
days) on 57 calendar dates and unadjusted corporate-action breaks in data/raw/. Every analysis that worked around
this did it ad hoc. This is the one tested way to do it.

What it does, and does not do:
- Read-only. Never writes to the cache; `check_data_sanity.py` still reports the raw problems (nothing is hidden).
- A stub row is volume == 0 and open == high == low == close. A calendar date on which at least `drop_stub_share`
  of the tickers are stubbed is a data-wide outage: the date is dropped from every series (returns over the gap are
  multi-day, not lumped into a fake zero-return day).
- A single ticker's stub row on an otherwise good date stays in the frame (price carried forward) but is False in
  `real`, so it can be made ineligible instead of being treated as a real price.
- Corporate-action breaks come only from an explicit, reviewed table (KNOWN_BREAKS); nothing is guessed. A break
  scales the earlier prices so that day's return is 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from kth.data.loader import load_cached

# ticker -> [(break date, why / source)]. Add entries only with a source.
KNOWN_BREAKS: dict[str, list[tuple[str, str]]] = {
    "TRUE.BK": [("2023-03-03", "DTAC merger: price frozen 2023-02-20..03-02, new TRUE first traded 2023-03-03 "
                               "(TRUE investor relations, Bangkok Post, 2026-09-21 audit)")],
    # SCB.BK: the series starts at the 2022-04-27 SCB X share swap (1,074 rows); nothing to scale.
}


@dataclass
class CleanReport:
    dropped_dates: list = field(default_factory=list)
    applied_breaks: list = field(default_factory=list)   # (ticker, date, scale factor)
    skipped_breaks: list = field(default_factory=list)   # (ticker, date, reason)
    ticker_stub_rows: dict = field(default_factory=dict)  # ticker -> number of stub rows kept but flagged not real


def stub_mask(df: pd.DataFrame) -> pd.Series:
    """True where a row is a stub: zero volume and a perfectly flat candle."""
    return (df["volume"] == 0) & (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])


def load_clean_closes(
    tickers,
    cache_dir: str = "data/raw",
    drop_stub_share: float = 0.5,
    breaks: dict | None = None,
    ffill_limit: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, CleanReport]:
    """Return (close, real, report) on the union calendar.

    close: adjusted closes, forward-filled up to `ffill_limit` rows (the convention of the SET analyses),
           with stub dates dropped and known breaks scaled.
    real:  True where the ticker has a real (non-stub) price that day; aligned to `close`.
    """
    breaks = KNOWN_BREAKS if breaks is None else breaks
    report = CleanReport()
    close, real = {}, {}
    for t in tickers:
        df = load_cached(t, cache_dir)
        idx = pd.to_datetime(df["timestamps"])
        stub = stub_mask(df).to_numpy()
        close[t] = pd.Series(df["close"].to_numpy(), index=idx)
        real[t] = pd.Series(~stub, index=idx)
    close = pd.DataFrame(close).sort_index()
    real = pd.DataFrame(real).reindex(close.index).fillna(False).astype(bool)
    close = close.ffill(limit=ffill_limit)

    present = close.notna().sum(axis=1).clip(lower=1)
    share_stub = 1.0 - real.sum(axis=1) / present
    bad = list(share_stub[share_stub >= drop_stub_share].index)
    report.dropped_dates = bad
    close, real = close.drop(index=bad), real.drop(index=bad)

    for t, items in breaks.items():
        for day, why in items:
            day = pd.Timestamp(day)
            if t not in close.columns:
                report.skipped_breaks.append((t, str(day.date()), "ticker not requested")); continue
            if day not in close.index:
                report.skipped_breaks.append((t, str(day.date()), "break date not in calendar")); continue
            i = close.index.get_loc(day)
            prev, cur = close[t].iloc[i - 1] if i > 0 else np.nan, close[t].iloc[i]
            if not (np.isfinite(prev) and np.isfinite(cur) and prev > 0):
                report.skipped_breaks.append((t, str(day.date()), "no valid prices around the break")); continue
            factor = float(cur / prev)
            close.loc[close.index[:i], t] = close[t].iloc[:i] * factor
            report.applied_breaks.append((t, str(day.date()), round(factor, 6)))

    report.ticker_stub_rows = {t: int((~real[t]).sum()) for t in real.columns if (~real[t]).any()}
    return close, real, report
