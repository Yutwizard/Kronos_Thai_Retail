#!/usr/bin/env python3
"""Backfill a single missed forecast date.

Re-generates the daily forecast cache for an as-of date by slicing each
ticker's raw parquet to timestamps <= AS_OF, so the forecast uses only the
close data that would have been available that day (matches the evening-run
methodology). Writes into data/forecast_cache/{slug}/{AS_OF}/ in the same
format as precompute_forecasts.

Usage:
    python scripts/backfill_forecast.py 2026-06-15
"""
import json
import sys
from pathlib import Path

import pandas as pd

from kth.data.loader import load_cached
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import _model_slug

PRED_LEN = 20
N_SAMPLES = 50
LOOKBACK = 400
MODEL = "NeoQuasar/Kronos-small"


def main(as_of: str) -> int:
    as_of_ts = pd.Timestamp(as_of)
    slug = _model_slug(MODEL)
    out_dir = Path(f"data/forecast_cache/{slug}/{as_of}")
    out_dir.mkdir(parents=True, exist_ok=True)

    tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]

    # Slice each ticker's parquet to <= as_of and keep those with enough history.
    sliced: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = load_cached(t)
        except FileNotFoundError:
            continue
        df = df[df["timestamps"] <= as_of_ts].reset_index(drop=True)
        if len(df) < LOOKBACK:
            print(f"[skip] {t}: only {len(df)} bars <= {as_of}")
            continue
        last = df["timestamps"].iloc[-1]
        if last != as_of_ts:
            print(f"[warn] {t}: last bar is {last.date()} (no {as_of} bar) — using anyway")
        sliced[t] = df

    if not sliced:
        print("Nothing to forecast.")
        return 1

    # Skip tickers already cached for this day.
    pending_keys = []
    pending_dfs = []
    for t, df in sliced.items():
        safe = t.replace("^", "_").replace("=", "_")
        if (out_dir / f"{safe}.parquet").exists():
            continue
        pending_keys.append(t)
        pending_dfs.append(df)

    if not pending_dfs:
        print(f"All {len(sliced)} tickers already cached for {as_of}.")
        return 0

    print(f"[backfill] {as_of}: forecasting {len(pending_dfs)} tickers (slug={slug})")
    th = KronosTH.from_pretrained(MODEL, device="cuda")
    results = th.forecast_batch(
        pending_dfs, pred_lens=[PRED_LEN], n_samples=N_SAMPLES,
        lookback=LOOKBACK, calendar_freq="B",
    )

    # forecast_batch keys DataFrame inputs as "df_{i}" by enumerate index.
    written = 0
    for i, t in enumerate(pending_keys):
        result = results.get(f"df_{i}")
        if result is None:
            print(f"[miss] {t}: no result returned")
            continue
        safe = t.replace("^", "_").replace("=", "_")
        h_df = result.horizons[PRED_LEN].summary.copy()
        h_df["ticker"] = t
        h_df.to_parquet(out_dir / f"{safe}.parquet", index=False)
        meta = {
            "ticker": t,
            "model_name": result.model_name,
            "generated_at": str(result.generated_at),
            "lookback_end": str(result.lookback_end),
        }
        with open(out_dir / f"{safe}_meta.json", "w") as f:
            json.dump(meta, f)
        written += 1

    print(f"[backfill] wrote {written} forecasts to {out_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/backfill_forecast.py YYYY-MM-DD")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
