"""Regenerate a small point-in-time forecast sample into a fresh cache.

Ticket .scratch/future-plan/00: the historical cache in data/forecast_cache was
conditioned on data after each folder's date. This writes forecasts for a few
trading days into data/forecast_cache_pit using the fixed precompute_forecasts
(data truncated at each day), so they can be compared with the old cache by
scripts/compare_pit_sample.py. Resumable: already-written tickers/days are skipped.

Usage:
    venv/bin/python scripts/regenerate_forecast_sample.py 2024-03-01 2024-03-29 [--step 2]
"""
import argparse

import pandas as pd

from kth.backtest.walkforward import precompute_forecasts
from kth.data.loader import load_cached
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH

MODEL = "NeoQuasar/Kronos-small"
PRED_LEN, N_SAMPLES, LOOKBACK = 20, 50, 400
CACHE_DIR = "./data/forecast_cache_pit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--step", type=int, default=1, help="use every Nth trading day")
    args = ap.parse_args()

    tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]
    ref = pd.to_datetime(load_cached("PTT.BK")["timestamps"])
    days = [d for d in ref if pd.Timestamp(args.start) <= d <= pd.Timestamp(args.end)][:: args.step]
    print(f"{len(days)} trading days: {days[0].date()} .. {days[-1].date()}  ({len(tickers)} tickers)")

    th = KronosTH.from_pretrained(MODEL, device="cuda")
    for d in days:
        precompute_forecasts(
            th, tickers, str(d.date()), str(d.date()),
            pred_len=PRED_LEN, n_samples=N_SAMPLES, lookback=LOOKBACK, cache_dir=CACHE_DIR,
        )


if __name__ == "__main__":
    main()
