"""Ticket 18 (.scratch/future-plan/18, approved 2026-09-24): are Kronos-small's 2024 point-in-time quantile
forecasts more accurate than a naive forecast?

Primary: mean pinball loss at h = 20, Kronos vs B1 (historical simulation). Read-only; CPU only.
    python scripts/forecast_quality_vs_naive.py --selftest    # synthetic checks, no real data
    python scripts/forecast_quality_vs_naive.py               # the one pre-registered run
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_track_review import FROZEN_THAI_EQUITY, STUB_DATE_SHARE, sanitize  # noqa: E402

FC_ROOT = Path("data/forecast_cache_pit/NeoQuasar_Kronos-small")
RAW = Path.home() / "backups" / "kronos-th-snapshots" / "2026-09-23T222128" / "raw"
TAUS = np.array([0.05, 0.25, 0.5, 0.75, 0.95])
QCOLS = ["p5", "p25", "p50", "p75", "p95"]
Z = np.array([-1.6449, -0.6745, 0.0, 0.6745, 1.6449])
HORIZONS = (1, 5, 20)
PRIMARY_H = 20
LOOKBACK = 400
N_BOOT, SEED, BLOCK = 10_000, 42, 20


def pinball(q: np.ndarray, y: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(TAUS * d, (TAUS - 1) * d)))


def b1_quantiles(window: np.ndarray, h: int) -> np.ndarray | None:
    ends = np.arange(len(window) - 1, h - 1, -h)
    r = np.log(window[ends] / window[ends - h])
    if len(r) < 10:
        return None
    return np.quantile(r - np.median(r), TAUS)


def b2_quantiles(window: np.ndarray, h: int) -> np.ndarray:
    lr = np.diff(np.log(window[-61:]))
    return Z * lr.std(ddof=1) * np.sqrt(h)


def block_ci(x: np.ndarray, seed: int = SEED) -> tuple[float, float, float]:
    n = len(x)
    rng = np.random.default_rng(seed)
    means = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx, i = np.empty(n, dtype=int), 0
        while i < n:
            s, ln = rng.integers(0, n), min(rng.geometric(1 / BLOCK), n - i)
            idx[i:i + ln] = (s + np.arange(ln)) % n
            i += ln
        means[b] = x[idx].mean()
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def load_raw(tickers):
    frames, stub = {}, {}
    for t in tickers:
        d = pd.read_parquet(RAW / f"{sanitize(t)}.parquet")
        d.index = pd.to_datetime(d["timestamps"]).dt.normalize()
        frames[t] = d
        stub[t] = (d["volume"] == 0) & (d["open"] == d["high"]) & (d["high"] == d["low"]) & (d["low"] == d["close"])
    s = pd.DataFrame(stub).fillna(False)
    stub_dates = set(s.index[s.sum(axis=1) >= STUB_DATE_SHARE * len(tickers)])
    return frames, stub_dates


def score(fc_root: Path, frames: dict, stub_dates: set) -> pd.DataFrame:
    rows = []
    for folder in sorted(p for p in fc_root.iterdir() if p.is_dir()):
        for t, d in frames.items():
            f, m = folder / f"{sanitize(t)}.parquet", folder / f"{sanitize(t)}_meta.json"
            if not f.exists() or not m.exists():
                continue
            lb = pd.Timestamp(json.loads(m.read_text())["lookback_end"]).normalize()
            if lb not in d.index:
                continue
            i = d.index.get_loc(lb)
            if i + 1 < LOOKBACK:
                continue
            window = d["close"].to_numpy()[i + 1 - LOOKBACK:i + 1]
            base = window[-1]
            fc = pd.read_parquet(f).set_index("timestamps")
            for h in HORIZONS:
                if i + h >= len(d) or d.index[i + h] in stub_dates or h not in fc.index:
                    continue
                y = float(np.log(d["close"].iloc[i + h] / base))
                kq = np.log(fc.loc[h, QCOLS].to_numpy(dtype=float) / base)
                b1 = b1_quantiles(window, h)
                b2 = b2_quantiles(window, h)
                rows.append({
                    "date": pd.Timestamp(folder.name), "ticker": t, "h": h, "y": y,
                    "L_kronos": pinball(kq, y), "L_b1": None if b1 is None else pinball(b1, y), "L_b2": pinball(b2, y),
                    "abs_err_kronos": abs(y - kq[2]), "abs_err_b1": None if b1 is None else abs(y - b1[2]),
                    "abs_err_b2": abs(y - b2[2]),
                    "in90_kronos": kq[0] <= y <= kq[4], "in50_kronos": kq[1] <= y <= kq[3],
                    "in90_b1": None if b1 is None else b1[0] <= y <= b1[4],
                    "in50_b1": None if b1 is None else b1[1] <= y <= b1[3],
                    "in90_b2": b2[0] <= y <= b2[4], "in50_b2": b2[1] <= y <= b2[3],
                })
    return pd.DataFrame(rows)


def compare(res: pd.DataFrame, h: int, base: str) -> dict:
    sub = res[(res["h"] == h)].dropna(subset=[f"L_{base}"])
    per_date = (sub["L_kronos"] - sub[f"L_{base}"].astype(float)).groupby(sub["date"]).mean().to_numpy()
    mean, lo, hi = block_ci(per_date)
    verdict = "BETTER" if hi < 0 else "WORSE" if lo > 0 else "NO DIFFERENCE SHOWN"
    return {"h": h, "baseline": base, "dates": len(per_date), "pairs": len(sub),
            "mean_loss_kronos": float(sub["L_kronos"].mean()), f"mean_loss_{base}": float(sub[f"L_{base}"].astype(float).mean()),
            "diff_mean": mean, "diff_ci": (lo, hi), "verdict": verdict}


def selftest() -> None:
    assert abs(pinball(np.zeros(5), 0.0)) < 1e-15
    # y above every quantile by 1: loss = mean(tau) * 1 = 0.5
    assert abs(pinball(np.zeros(5), 1.0) - 0.5) < 1e-12
    w = np.exp(np.cumsum(np.full(400, 0.01)))  # constant 1% daily drift
    q = b1_quantiles(w, 20)
    assert q is not None and np.allclose(q, 0.0), q  # all 20-day returns equal -> centred quantiles are 0
    assert np.allclose(b2_quantiles(w, 5), 0.0)  # zero volatility
    rng = np.random.default_rng(0)
    w2 = np.exp(np.cumsum(rng.normal(0, 0.02, 400)))
    q2 = b2_quantiles(w2, 20)
    assert q2[2] == 0 and 0.05 < q2[4] < 0.2, q2  # 2% daily x sqrt(20) x 1.645 ~ 0.147
    m, lo, hi = block_ci(rng.normal(-1.0, 0.1, 262))
    assert hi < 0 and lo < m < hi
    m, lo, hi = block_ci(rng.normal(0.0, 0.1, 262))
    assert lo < 0 < hi
    print("selftest passed (pinball, B1 centring, B2 scale, block bootstrap CI)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    frames, stub_dates = load_raw(FROZEN_THAI_EQUITY)
    res = score(FC_ROOT, frames, stub_dates)
    print(f"forecast folders: {res['date'].nunique()}, scored (ticker, date, h): {len(res)}, stub calendar dates in data: {len(stub_dates)}")
    out = []
    for h in HORIZONS:
        for base in ("b1", "b2"):
            c = compare(res, h, base)
            out.append(c)
            tag = "PRIMARY" if (h == PRIMARY_H and base == "b1") else "secondary"
            print(f"[{tag}] h={h:>2} vs {base}: Kronos {c['mean_loss_kronos']:.5f}  {base} {c[f'mean_loss_{base}']:.5f}  "
                  f"diff {c['diff_mean']:+.5f}  95% CI [{c['diff_ci'][0]:+.5f}, {c['diff_ci'][1]:+.5f}]  "
                  f"({c['dates']} dates, {c['pairs']} pairs)  -> {c['verdict']}")
    print("\ndescriptive (not tested): p50 abs log error and band coverage")
    for h in HORIZONS:
        s = res[res["h"] == h]
        cells = []
        for m in ("kronos", "b1", "b2"):
            cells.append(f"{m}: |err| {s[f'abs_err_{m}'].astype(float).mean():.4f}  cov90 {s[f'in90_{m}'].astype(float).mean():.3f}  "
                         f"cov50 {s[f'in50_{m}'].astype(float).mean():.3f}")
        print(f"  h={h:>2}  " + "  |  ".join(cells))
    primary = next(c for c in out if c["h"] == PRIMARY_H and c["baseline"] == "b1")
    print(f"\nPRIMARY VERDICT (h=20, Kronos vs B1 pinball): {primary['verdict']}")


if __name__ == "__main__":
    sys.exit(main())
