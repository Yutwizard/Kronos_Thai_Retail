"""
Data loader for the Thai-retail universe.

Why this exists separately from just calling `yf.download()`:
1. Caching: yfinance is slow and rate-limited. Download once, reuse.
2. Schema: Kronos expects columns ['open','high','low','close','volume',
   'amount'] in lowercase, plus a 'timestamps' column. yfinance gives
   'Open','High','Low','Close','Volume' with a DatetimeIndex.
3. Gaps: Different markets have different trading calendars (SET vs NYSE
   vs 24/7 crypto). We do NOT forward-fill across markets — gaps stay
   as gaps so the model sees real trading days only.
4. Multi-ticker: download_universe() pulls everything in one batched
   request (faster, gentler on Yahoo).
5. Quality checks: flag suspiciously low volume, missing days, extreme
   single-day moves (potential bad ticks).

Usage:
    from kth.data.loader import download_universe, load_cached

    # First time (or to refresh)
    download_universe(period="5y", cache_dir="./data/raw")

    # Subsequent loads
    df = load_cached("AAPL", cache_dir="./data/raw")
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import numpy as np


# Lazy import so universe.py is usable standalone in environments without yfinance
def _import_yfinance():
    try:
        import yfinance as yf
        return yf
    except ImportError as e:
        raise ImportError(
            "yfinance is required for downloading. Install via "
            "`pip install yfinance`."
        ) from e


# ---------------------------------------------------------------------------
# Core download with retries and rate-limit politeness
# ---------------------------------------------------------------------------

def _download_one(
    ticker: str,
    period: str = "10y",
    interval: str = "1d",
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> Optional[pd.DataFrame]:
    """
    Download a single ticker with exponential backoff.
    Returns None on permanent failure (delisted, no data, blocked).
    """
    yf = _import_yfinance()
    for attempt in range(max_retries):
        try:
            df = yf.download(
                ticker, period=period, interval=interval,
                progress=False, auto_adjust=True, threads=False,
            )
            if df is None or df.empty:
                return None
            # yfinance may return MultiIndex columns when single ticker too;
            # flatten that case.
            if isinstance(df.columns, pd.MultiIndex):
                # Take the first level (Open/High/Low/Close/Volume)
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  [FAIL] {ticker}: {type(e).__name__}: {e}")
                return None
            wait = base_delay * (2 ** attempt)
            print(f"  [retry {attempt+1}] {ticker} in {wait:.1f}s ({e})")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# Schema conversion: yfinance -> Kronos
# ---------------------------------------------------------------------------

def to_kronos_format(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Convert yfinance dataframe to Kronos-expected schema.

    Kronos expects:
      - 'timestamps'  : pd.Timestamp series
      - 'open','high','low','close' : float
      - 'volume','amount' : float (amount = price * volume, used by Kronos as
                                   a 2nd intensity channel)

    Why we compute 'amount' ourselves:
      Yahoo doesn't provide it. Kronos's tokenizer treats volume and amount
      as separate channels (turnover). We approximate amount = close * volume,
      which is what the original Kronos repo also does for markets that don't
      publish turnover.
    """
    out = pd.DataFrame(index=df.index)
    out["open"]   = df["Open"].astype(float)
    out["high"]   = df["High"].astype(float)
    out["low"]    = df["Low"].astype(float)
    out["close"]  = df["Close"].astype(float)
    out["volume"] = df["Volume"].astype(float).fillna(0.0)
    out["amount"] = out["close"] * out["volume"]
    out = out.reset_index().rename(columns={"Date": "timestamps",
                                            "Datetime": "timestamps",
                                            "index": "timestamps"})
    out["timestamps"] = pd.to_datetime(out["timestamps"])
    # Drop rows where close is NaN (true missing data, not just zero volume)
    out = out.dropna(subset=["close"]).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def quality_report(df: pd.DataFrame, ticker: str) -> dict:
    """Return a dict describing data quality issues."""
    n = len(df)
    if n == 0:
        return {"ticker": ticker, "rows": 0, "issue": "empty"}

    span_days = (df["timestamps"].max() - df["timestamps"].min()).days
    expected_business_days = span_days * 5 / 7  # rough; ignores holidays
    coverage = n / max(expected_business_days, 1)

    # Suspicious single-day moves (>20% for stocks, >50% for crypto -- we use
    # a loose 30% threshold here, just to flag)
    rets = df["close"].pct_change().abs()
    big_moves = (rets > 0.30).sum()

    zero_vol_days = (df["volume"] == 0).sum()

    return {
        "ticker": ticker,
        "rows": n,
        "start": df["timestamps"].min().strftime("%Y-%m-%d"),
        "end":   df["timestamps"].max().strftime("%Y-%m-%d"),
        "span_days": span_days,
        "coverage_vs_5wk": round(coverage, 2),
        "zero_vol_days": int(zero_vol_days),
        "big_moves_30pct": int(big_moves),
    }


# ---------------------------------------------------------------------------
# Batch download to cache
# ---------------------------------------------------------------------------

def download_universe(
    tickers: Iterable[str],
    period: str = "10y",
    cache_dir: str = "./data/raw",
    pause_between: float = 0.5,
) -> pd.DataFrame:
    """
    Download all tickers to parquet files in cache_dir.
    Returns a quality report DataFrame.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    reports = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(list(tickers)) if hasattr(tickers,'__len__') else '?'}] "
              f"{ticker}...", end=" ", flush=True)
        raw = _download_one(ticker, period=period)
        if raw is None:
            print("FAILED")
            reports.append({"ticker": ticker, "rows": 0, "issue": "download failed"})
            continue
        df = to_kronos_format(raw, ticker)
        # Sanitize filename: SPY -> SPY, BTC-USD -> BTC-USD, ^SET.BK -> _SET.BK
        safe = ticker.replace("^", "_").replace("=", "_")
        outfile = cache_path / f"{safe}.parquet"
        df.to_parquet(outfile, index=False)
        rpt = quality_report(df, ticker)
        reports.append(rpt)
        print(f"OK {rpt['rows']} rows {rpt['start']}..{rpt['end']}")
        time.sleep(pause_between)

    from kth.data.versioning import write_manifest
    try:
        write_manifest(cache_path, list(tickers))
    except Exception as e:
        print(f"[versioning] manifest write failed: {e}")

    return pd.DataFrame(reports)


def load_cached(ticker: str, cache_dir: str = "./data/raw") -> pd.DataFrame:
    """Load a ticker's cached parquet. Returns Kronos-format DataFrame."""
    safe = ticker.replace("^", "_").replace("=", "_")
    path = Path(cache_dir) / f"{safe}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"No cached file for {ticker} at {path}. "
            "Run download_universe() first."
        )
    return pd.read_parquet(path)


def list_cached(cache_dir: str = "./data/raw") -> list:
    """List all tickers currently cached."""
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return []
    files = sorted(cache_path.glob("*.parquet"))
    return [f.stem.replace("_SET.BK", "^SET.BK") for f in files]
