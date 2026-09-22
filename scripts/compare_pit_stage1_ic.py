"""Ticket 17 Stage 1: compare signal quality (rank IC) of the original 2024 PIT cache vs the cleaned-input
rerun, on the SAME 53 dates. Design frozen in .scratch/future-plan/17-rerun-2024-pit-on-cleaned-inputs.md.

Metric: per-date cross-sectional Spearman rank IC of (p50 at horizon 20 / close - 1) vs the realised 20-trading-day
return, using kth.data.universe closes (unclean, since the realised return is a fact, not a model input) for both
caches so the comparison isolates the effect of cleaning the model's INPUT only. Applies the frozen gate rules.

Usage: venv/bin/python scripts/compare_pit_stage1_ic.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from kth.data.universe import UNIVERSE

ORIG_ROOT = Path("data/forecast_cache_pit/NeoQuasar_Kronos-small")
CLEAN_ROOT = Path("data/forecast_cache_pit_clean/NeoQuasar_Kronos-small")
H = 20
N_BOOT, SEED = 10000, 42
TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]


def load_closes() -> dict[str, pd.Series]:
    out = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        out[t] = d.set_index(pd.to_datetime(d["timestamps"]))["close"]
    return out


def daily_ic(root: Path, dates: list[pd.Timestamp], closes: dict) -> pd.Series:
    rows = {}
    for day in dates:
        folder = root / day.strftime("%Y-%m-%d")
        sig, real = {}, {}
        for t in TICKERS:
            f = folder / f"{t}.parquet"
            c = closes[t]
            pos = c.index.searchsorted(day, side="right") - 1
            if not f.exists() or pos < 0 or pos + H >= len(c):
                continue
            last = c.iloc[pos]
            sig[t] = float(pd.read_parquet(f)["p50"].iloc[-1]) / last - 1
            real[t] = c.iloc[pos + H] / last - 1
        if len(real) < 20:
            rows[day] = np.nan
            continue
        ks = list(real)
        rows[day] = spearmanr([sig[k] for k in ks], [real[k] for k in ks])[0]
    return pd.Series(rows)


def block_bootstrap_ci(x: np.ndarray, seed: int = SEED) -> tuple[float, float, float]:
    n = len(x)
    rng = np.random.default_rng(seed)
    blk = max(int(n ** (1 / 3)), 2)
    means = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx, i = np.empty(n, dtype=int), 0
        while i < n:
            s, ln = rng.integers(0, n), min(rng.geometric(1 / blk), n - i)
            idx[i:i + ln] = (s + np.arange(ln)) % n
            i += ln
        means[b] = x[idx].mean()
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    clean_dates = sorted(p.name for p in CLEAN_ROOT.iterdir() if p.is_dir())
    dates = [pd.Timestamp(d) for d in clean_dates]
    assert len(dates) == 53, f"expected 53 Stage 1 dates, found {len(dates)}"
    closes = load_closes()

    ic_orig = daily_ic(ORIG_ROOT, dates, closes)
    ic_clean = daily_ic(CLEAN_ROOT, dates, closes)
    both = pd.DataFrame({"original": ic_orig, "cleaned": ic_clean}).dropna()
    print(f"dates requested: 53 | dates with a valid paired IC (>=20 names both sides): {len(both)}")

    for label, s in (("original (same 53 dates)", both["original"]), ("cleaned (Stage 1)", both["cleaned"])):
        m, lo, hi = block_bootstrap_ci(s.to_numpy())
        print(f"  {label:30s} mean IC {m:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  n={len(s)}")

    diff = (both["cleaned"] - both["original"]).to_numpy()
    dm, dlo, dhi = block_bootstrap_ci(diff)
    print(f"  {'paired difference (cleaned - original)':30s} mean {dm:+.4f}  95% CI [{dlo:+.4f}, {dhi:+.4f}]")
    print(f"  cleaned > original on {int((diff > 0).sum())} of {len(diff)} dates")

    _, clo, chi = block_bootstrap_ci(both["cleaned"].to_numpy())
    if dlo > 0 or clo > 0:
        verdict = "G1: run Stage 2 and the full backtest comparison"
    elif (dlo <= 0 <= dhi) and chi < 0:
        verdict = "G2: STOP -- cleaning does not change the signal; the -26% 2024 loss stands as originally measured"
    else:
        verdict = "G3: inconclusive (both CIs include 0) -- stop and ask the user whether the remaining ~33h is worth it"
    print(f"\nVERDICT (frozen gate): {verdict}")


if __name__ == "__main__":
    main()
