"""Signal quality of the point-in-time forecast cache over a period.

For each business day: per-ticker signal = p50(day 20)/close - 1, realized =
close 20 trading days later / close - 1. Reports mean cross-sectional Spearman IC
(with a block-bootstrap CI), top-5 vs universe mean realized return, median |signal|.

Usage: venv/bin/python scripts/pit_signal_quality.py 2024-01-01 2024-12-31
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from kth.data.universe import UNIVERSE

ROOT = Path("data/forecast_cache_pit/NeoQuasar_Kronos-small")
H = 20
TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]


def main(start, end):
    closes = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        closes[t] = d.set_index(pd.to_datetime(d["timestamps"]))["close"]
    rows = []
    for day in pd.bdate_range(start, end):
        sig, real = {}, {}
        for t in TICKERS:
            f = ROOT / day.strftime("%Y-%m-%d") / f"{t}.parquet"
            c = closes[t]
            pos = c.index.searchsorted(day, side="right") - 1
            if not f.exists() or pos < 0 or pos + H >= len(c):
                continue
            last = c.iloc[pos]
            sig[t] = float(pd.read_parquet(f)["p50"].iloc[-1]) / last - 1
            real[t] = c.iloc[pos + H] / last - 1
        if len(real) < 20:
            continue
        ks = list(real)
        s, r = np.array([sig[k] for k in ks]), np.array([real[k] for k in ks])
        top = np.argsort(-s)[:5]
        rows.append({"date": day, "ic": spearmanr(s, r)[0], "med_abs": np.median(np.abs(s)),
                     "top5_excess": r[top].mean() - r.mean(), "top5_signal": s[top].mean()})
    df = pd.DataFrame(rows).set_index("date")
    rng = np.random.default_rng(0)
    n, blk = len(df), max(1, round(len(df) ** (1 / 3)) * 4)
    ic = df["ic"].to_numpy()
    boots = []
    for _ in range(5000):
        idx = (rng.integers(0, n, n // blk + 1)[:, None] + np.arange(blk)).ravel()[:n] % n
        boots.append(ic[idx].mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"days {n}   mean IC {ic.mean():+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}] (block={blk}, overlapping 20d windows)")
    print(f"median |signal| {df.med_abs.mean():.1%}   mean top-5 signal {df.top5_signal.mean():+.1%}")
    print(f"top-5 minus universe mean realized 20d return: {df.top5_excess.mean():+.2%}  (positive share of days {(df.top5_excess > 0).mean():.0%})")
    print(df.groupby(df.index.to_period('Q'))[["ic", "top5_excess"]].mean().round(4))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
