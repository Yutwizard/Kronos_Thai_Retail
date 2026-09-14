"""PriceStore — the single seam for all cached-OHLCV reads.

Why this module exists: close-price reads fanned out across trade_gen,
portfolio, sheets, dashboard and walkforward, each with its own copy of
ticker sanitization and its own parquet round-trip (load_forecasts did ~3N
reads for N tickers). Every reader now goes through here.

Depth: a small interface (get_close / get_ohlcv / batch) over memoized
per-run reads. Memoization is per-instance on purpose — a fresh store per
run means no stale closes can leak across days in a long-lived process.

`load_cached` in kth.data.loader keeps its exact semantics (it is the
store's IO adapter); only the filename rule moved to sanitize_ticker().
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from kth.data.loader import sanitize_ticker

logger = logging.getLogger(__name__)


class PriceStore:
    """Memoized reader for per-ticker cached OHLCV parquet files."""

    def __init__(
        self,
        cache_dir: str = "./data/raw",
        read_fn: Callable[[Path], pd.DataFrame] | None = None,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        # Accept the dependency, don't create it: tests inject a counting
        # fake; production defaults to a plain parquet read.
        self._read = read_fn or pd.read_parquet
        self._memo: dict[str, pd.DataFrame] = {}

    @classmethod
    def with_frames(
        cls,
        frames: dict[str, pd.DataFrame],
        cache_dir: str = "./data/raw",
    ) -> "PriceStore":
        """A store preloaded with frames (e.g. daily's ensure() output).

        Preloaded tickers never touch disk; anything else falls back to
        the normal cached read.
        """
        store = cls(cache_dir=cache_dir)
        store._memo = dict(frames)
        return store

    def _path(self, ticker: str) -> Path:
        return self._cache_dir / f"{sanitize_ticker(ticker)}.parquet"

    def get_ohlcv(self, ticker: str) -> pd.DataFrame:
        """Full cached frame for a ticker. Raises FileNotFoundError when
        missing — same contract as load_cached."""
        if ticker not in self._memo:
            path = self._path(ticker)
            if not path.exists():
                raise FileNotFoundError(
                    f"No cached file for {ticker} at {path}. "
                    "Run download_universe() first."
                )
            self._memo[ticker] = self._read(path)
        return self._memo[ticker]

    def get_close(self, ticker: str) -> Optional[float]:
        """Latest close, or None when uncached/corrupt. Same contract as
        portfolio._get_current_price (warn, don't raise)."""
        try:
            return float(self.get_ohlcv(ticker)["close"].iloc[-1])
        except FileNotFoundError:
            logger.warning("PriceStore: no cache for %s", ticker)
            return None
        except Exception as e:
            logger.error("PriceStore: corrupt cache for %s: %s", ticker, e)
            return None

    def batch(self, tickers: list[str]) -> dict[str, pd.DataFrame]:
        """One memoized frame per ticker; missing tickers are skipped
        (same leniency as the walkforward preload loop)."""
        out: dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            try:
                out[ticker] = self.get_ohlcv(ticker)
            except FileNotFoundError:
                continue
        return out
