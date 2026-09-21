"""Read-only audit for ticket .scratch/future-plan/12: did Yahoo stub rows fall inside the 400-row
Kronos input windows of (a) the 2024 point-in-time cache and (b) the live forecast folders?

Definitions are frozen in the ticket: stub row = volume 0 and open == high == low == close; the input window of
a forecast is the last LOOKBACK rows of the ticker's raw data up to `lookback_end` (the model's `df.tail(lookback)`);
affected = at least AFFECTED_MIN stub rows; heavy = at least HEAVY_MIN; MATERIAL if >= 10% affected or >= 2% heavy
in the 2024 PIT cache. Nothing is written to data/raw or any cache.

Usage: python scripts/audit_stub_windows.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from kth.data.universe import UNIVERSE
from kth_dr.universe_dr import get_dr_underlying_tickers

LOOKBACK = 400  # kth/models/kronos_wrapper.py forecast()/forecast_batch() default
AFFECTED_MIN, HEAVY_MIN = 4, 20
MATERIAL_AFFECTED_SHARE, MATERIAL_HEAVY_SHARE = 0.10, 0.02
LIVE_START = pd.Timestamp("2026-06-29")  # first point-in-time live folder (ticket 00)
PIT_ROOT = Path("data/forecast_cache_pit/NeoQuasar_Kronos-small")
LIVE_ROOT = Path("data/forecast_cache/NeoQuasar_Kronos-small")
RAW = Path("data/raw")


def sanitize(t: str) -> str:
    return t.replace("^", "_").replace("=", "_")


def load_stub_cumsum(ticker: str):
    p = RAW / f"{sanitize(ticker)}.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    ts = pd.to_datetime(d["timestamps"]).dt.normalize().to_numpy()
    stub = ((d["volume"] == 0) & (d["open"] == d["high"]) & (d["high"] == d["low"]) & (d["low"] == d["close"])).to_numpy()
    cs = np.concatenate([[0], np.cumsum(stub.astype(int))])
    return ts, cs


def audit(root: Path, tickers, first=None, last=None) -> pd.DataFrame:
    cache, rows = {}, []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        day = pd.Timestamp(folder.name)
        if (first and day < first) or (last and day > last):
            continue
        for t in tickers:
            m = folder / f"{t}_meta.json"
            if not m.exists():
                continue
            if t not in cache:
                cache[t] = load_stub_cumsum(t)
            if cache[t] is None:
                continue
            ts, cs = cache[t]
            lb = pd.Timestamp(json.loads(m.read_text())["lookback_end"]).normalize()
            i = np.searchsorted(ts, np.datetime64(lb))
            if i >= len(ts) or ts[i] != np.datetime64(lb):
                rows.append((day, t, np.nan, "lookback_end not in raw")); continue
            if i + 1 < LOOKBACK:
                rows.append((day, t, np.nan, "fewer than 400 rows")); continue
            rows.append((day, t, int(cs[i + 1] - cs[i + 1 - LOOKBACK]), ""))
    return pd.DataFrame(rows, columns=["date", "ticker", "stub_rows", "note"])


def summarize(df: pd.DataFrame, label: str) -> dict:
    ok = df.dropna(subset=["stub_rows"])
    n = len(ok)
    aff = float((ok["stub_rows"] >= AFFECTED_MIN).mean()) if n else float("nan")
    heavy = float((ok["stub_rows"] >= HEAVY_MIN).mean()) if n else float("nan")
    print(f"\n=== {label}: {n} windows ({len(df) - n} skipped) ===")
    print(f"  share with >= {AFFECTED_MIN} stub rows: {aff:.1%}   share with >= {HEAVY_MIN}: {heavy:.1%}   worst window: {int(ok['stub_rows'].max()) if n else 'n/a'}   mean stub rows: {ok['stub_rows'].mean():.2f}")
    by_month = ok.assign(month=ok["date"].dt.to_period("M")).groupby("month")["stub_rows"].agg(
        windows="size", affected=lambda s: (s >= AFFECTED_MIN).mean(), heavy=lambda s: (s >= HEAVY_MIN).mean(), worst="max", mean="mean")
    print(by_month.to_string(float_format=lambda x: f"{x:.2f}"))
    top = ok.groupby("ticker")["stub_rows"].mean().sort_values(ascending=False).head(8)
    print("  tickers with the highest mean stub count in their windows:", {k: round(v, 1) for k, v in top.items()})
    if len(df) - n:
        print("  skipped windows by reason:", df[df["stub_rows"].isna()]["note"].value_counts().to_dict())
    return {"windows": n, "affected": aff, "heavy": heavy}


def main() -> None:
    eq = [t for t, _, _ in UNIVERSE["thai_equity"]]
    tickers = eq + list(get_dr_underlying_tickers())
    pit = audit(PIT_ROOT, tickers)
    pit_s = summarize(pit, "2024 point-in-time cache (ticket 00 backtest)")
    live = audit(LIVE_ROOT, tickers, first=LIVE_START)
    live_s = summarize(live, "live folders from 2026-06-29 (proxy: current raw cache)")
    material = pit_s["affected"] >= MATERIAL_AFFECTED_SHARE or pit_s["heavy"] >= MATERIAL_HEAVY_SHARE
    print(f"\nVERDICT by the frozen rule (>= {MATERIAL_AFFECTED_SHARE:.0%} affected or >= {MATERIAL_HEAVY_SHARE:.0%} heavy in the 2024 PIT cache): "
          f"{'MATERIAL' if material else 'NOT MATERIAL'}")
    print("Live windows are reported only; the local raw cache may differ from what the Kaggle pipeline saw at the time.")


if __name__ == "__main__":
    main()
