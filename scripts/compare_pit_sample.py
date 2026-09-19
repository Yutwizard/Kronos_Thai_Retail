"""Compare the old (look-ahead) forecast cache with the point-in-time sample.

Ticket .scratch/future-plan/00. For every date present in both
data/forecast_cache and data/forecast_cache_pit, per ticker:
  signal = p50(day 20) / close(date) - 1          (what compute_signals uses)
  realized = close(date + 20 trading days) / close(date) - 1
and reports, old vs new: median |signal|, mean per-date Spearman IC of signal vs
realized return, top-5 pick overlap, and Spearman between the two signals.
Also checks the new folders are point-in-time (lookback_end <= date).

Few dates and overlapping 20-day windows mean the IC comparison is indicative,
not a significance test.

Usage: venv/bin/python scripts/compare_pit_sample.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from kth.data.universe import UNIVERSE

OLD = Path("data/forecast_cache/NeoQuasar_Kronos-small")
NEW = Path("data/forecast_cache_pit/NeoQuasar_Kronos-small")
HORIZON = 20
TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]


def _p50(root: Path, day: str, ticker: str):
    f = root / day / f"{ticker}.parquet"
    return float(pd.read_parquet(f)["p50"].iloc[-1]) if f.exists() else None


def main():
    closes = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        closes[t] = d.set_index(pd.to_datetime(d["timestamps"]))["close"]

    days = sorted(p.name for p in NEW.iterdir() if p.is_dir() and (OLD / p.name).exists())
    rows, bad_pit = [], 0
    for day in days:
        ts = pd.Timestamp(day)
        sig_old, sig_new, real = {}, {}, {}
        for t in TICKERS:
            po, pn = _p50(OLD, day, t), _p50(NEW, day, t)
            c = closes[t]
            pos = c.index.searchsorted(ts, side="right") - 1
            if po is None or pn is None or pos < 0 or pos + HORIZON >= len(c):
                continue
            meta = json.loads((NEW / day / f"{t}_meta.json").read_text())
            bad_pit += pd.Timestamp(meta["lookback_end"]) > ts
            last = c.iloc[pos]
            sig_old[t], sig_new[t] = po / last - 1, pn / last - 1
            real[t] = c.iloc[pos + HORIZON] / last - 1
        if len(real) < 10:
            continue
        ks = list(real)
        o, n, r = (np.array([d[k] for k in ks]) for d in (sig_old, sig_new, real))
        top = lambda s: set(np.array(ks)[np.argsort(-s)[:5]])
        rows.append({
            "date": day, "n": len(ks),
            "med_abs_old": float(np.median(np.abs(o))), "med_abs_new": float(np.median(np.abs(n))),
            "ic_old": float(spearmanr(o, r)[0]), "ic_new": float(spearmanr(n, r)[0]),
            "old_vs_new_corr": float(spearmanr(o, n)[0]), "top5_overlap": len(top(o) & top(n)),
        })

    df = pd.DataFrame(rows)
    print(df.round(3).to_string(index=False))
    print(f"\ndates compared: {len(df)}   new folders violating point-in-time: {bad_pit}")
    print(f"median |signal|   old {df.med_abs_old.mean():.1%}   new {df.med_abs_new.mean():.1%}")
    print(f"mean IC vs realized {HORIZON}d return   old {df.ic_old.mean():+.3f}   new {df.ic_new.mean():+.3f}")
    print(f"mean Spearman(old signal, new signal) {df.old_vs_new_corr.mean():+.3f}   "
          f"mean top-5 overlap {df.top5_overlap.mean():.1f} of 5")
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    df.to_json("data/logs/compare_pit_sample.json", orient="records", indent=2)


if __name__ == "__main__":
    main()
