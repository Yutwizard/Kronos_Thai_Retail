"""Ticket 17 Stage 1: generate point-in-time Kronos forecasts on CLEANED inputs for 53 dates
(every 5th business day of 2024), to compare signal quality with the existing 2024 PIT cache.

Design frozen in .scratch/future-plan/17-rerun-2024-pit-on-cleaned-inputs.md: same model, n_samples,
pred_len, lookback and point-in-time discipline as the original run (scripts/run_pit_backtest.py /
scripts/regenerate_forecast_sample.py); only the input frames are cleaned (kth.data.clean.load_clean_frames).
Idempotent per date/ticker; safe to stop and resume.

Usage: venv/bin/python scripts/run_pit_stage1_clean.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kth.data.clean import load_clean_frames  # noqa: E402
from kth.data.loader import sanitize_ticker  # noqa: E402
from kth.data.universe import UNIVERSE  # noqa: E402
from kth.models.kronos_wrapper import KronosTH  # noqa: E402

MODEL = "NeoQuasar/Kronos-small"
LOOKBACK, PRED_LEN, N_SAMPLES = 400, 20, 50
CACHE_DIR = Path("data/forecast_cache_pit_clean")
YEAR_START, YEAR_END = "2024-01-01", "2024-12-31"
STAGE1_STRIDE = 5  # every 5th business day -> 53 dates


def stage1_dates() -> list[pd.Timestamp]:
    return list(pd.bdate_range(YEAR_START, YEAR_END)[::STAGE1_STRIDE])


def main() -> None:
    tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]
    dates = stage1_dates()
    print(f"[stage1] {len(dates)} dates, {tickers.__len__()} candidate tickers, output {CACHE_DIR}")

    frames, rep = load_clean_frames(tickers, cache_dir="data/raw")
    print(f"[stage1] cleaning: dropped {len(rep.dropped_dates)} stub dates; "
          f"breaks {rep.applied_breaks}; skipped {rep.skipped_breaks}; "
          f"tickers with own stub rows removed: {len(rep.ticker_stub_rows)}")

    th = None
    slug = MODEL.replace("/", "_")
    cache_path = CACHE_DIR / slug
    for day in dates:
        day_str = day.strftime("%Y-%m-%d")
        day_dir = cache_path / day_str
        day_dir.mkdir(parents=True, exist_ok=True)

        uncached = [t for t in tickers
                    if t in frames and not (day_dir / f"{sanitize_ticker(t)}.parquet").exists()]
        if not uncached:
            print(f"[{day_str}] already cached, skipping")
            continue

        batch, batch_tickers = [], []
        for t in uncached:
            df = frames[t]
            window = df[df["timestamps"] <= day].tail(LOOKBACK).reset_index(drop=True)
            if len(window) == LOOKBACK:
                batch.append(window)
                batch_tickers.append(t)
        skipped = len(uncached) - len(batch)
        if not batch:
            print(f"[{day_str}] 0 tickers with a full clean 400-row window (skipped {skipped})")
            continue

        if th is None:
            print(f"[stage1] loading {MODEL} on cuda ...")
            th = KronosTH.from_pretrained(MODEL, device="cuda")

        print(f"[{day_str}] forecasting {len(batch)} tickers (skipped {skipped} without a full clean window)...")
        results = th.forecast_batch(batch, pred_lens=[PRED_LEN], n_samples=N_SAMPLES, lookback=LOOKBACK)

        for i, t in enumerate(batch_tickers):
            result = results.get(f"df_{i}")
            if result is None:
                continue
            safe = sanitize_ticker(t)
            h_df = result.horizons[PRED_LEN].summary.copy()
            h_df["ticker"] = t
            h_df.to_parquet(day_dir / f"{safe}.parquet", index=False)
            meta = {"ticker": t, "model_name": result.model_name, "generated_at": str(result.generated_at),
                    "lookback_end": str(result.lookback_end)}
            (day_dir / f"{safe}_meta.json").write_text(json.dumps(meta))
            if pd.Timestamp(result.lookback_end).normalize() > day.normalize():
                raise RuntimeError(f"look-ahead: {t} on {day_str} conditioned on data through {result.lookback_end}")

    print("[stage1] done.")


if __name__ == "__main__":
    main()
