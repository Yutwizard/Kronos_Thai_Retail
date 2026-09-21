"""Pre-registered factor baselines vs equal-weight (ticket .scratch/future-plan/06).

Usage: venv/bin/python scripts/run_factor_baselines.py [START END]   (default 2023-01-02 2026-07-25)
"""
import sys

import numpy as np
import pandas as pd

from kth.backtest.metrics import evaluate_variant_vs_baseline
from kth.data.universe import UNIVERSE

TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
START, END = "2023-01-02", "2026-07-25"
TOP_N, ONE_WAY, MIN_HIST = 10, 0.00168 + 0.0010, 252
N_BOOT, ALPHA_ADJ = 10000, 0.05 / 3


def load_closes() -> pd.DataFrame:
    cols = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        cols[t] = d.set_index(pd.to_datetime(d["timestamps"]))["close"]
    return pd.DataFrame(cols).sort_index().ffill(limit=10)


def signals(close: pd.DataFrame, ret: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "momentum_12_1": close.shift(21) / close.shift(MIN_HIST) - 1,
        "low_vol_60": -ret.rolling(60).std(),
        "reversal_1m": -(close / close.shift(21) - 1),
    }


def simulate(ret: pd.DataFrame, elig: pd.DataFrame, score: pd.DataFrame | None, days) -> tuple[pd.Series, float]:
    w = pd.Series(0.0, index=ret.columns)
    out, turnover, last_month = {}, 0.0, None
    for i, d in enumerate(days):
        prev = ret.index[ret.index.get_loc(d) - 1]
        cost = 0.0
        if d.month != last_month:
            last_month = d.month
            e = elig.loc[prev]
            names = e[e].index
            if score is not None:
                names = score.loc[prev, names].dropna().nlargest(TOP_N).index
            target = pd.Series(0.0, index=ret.columns)
            target[names] = 1.0 / len(names)
            t_o = float((target - w).abs().sum())
            turnover += t_o
            cost = t_o * ONE_WAY
            w = target
        r = ret.loc[d].fillna(0.0)
        day_ret = float((w * r).sum())
        out[d] = day_ret - cost
        gross = 1.0 + day_ret
        w = w * (1.0 + r) / gross if gross > 0 else w
    years = len(days) / 252
    return pd.Series(out), turnover / years


def stats(r: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "sharpe": r.mean() / r.std() * np.sqrt(252),
            "maxdd": float((eq / eq.cummax() - 1).min())}


def one_sided_p(active: np.ndarray, seed: int = 42) -> float:
    n = len(active)
    rng = np.random.default_rng(seed)
    blk = max(int(n ** (1 / 3)), 2)
    means = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx, i = np.empty(n, dtype=int), 0
        while i < n:
            start, length = rng.integers(0, n), min(rng.geometric(1 / blk), n - i)
            idx[i:i + length] = (start + np.arange(length)) % n
            i += length
        means[b] = active[idx].mean()
    return float((means <= 0).mean())


def main():
    close = load_closes()
    ret = close.pct_change(fill_method=None)
    elig = close.notna() & (close.notna().cumsum() >= MIN_HIST)
    start, end = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (START, END)
    days = ret.loc[start:end].index
    bench, bench_to = simulate(ret, elig, None, days)
    print(f"days {len(days)}  eligible tickers {int(elig.loc[days[0]].sum())} at start, {int(elig.loc[days[-1]].sum())} at end")
    b = stats(bench)
    print(f"{'equal_weight':16s} CAGR {b['cagr']:+7.1%}  Sharpe {b['sharpe']:5.2f}  maxDD {b['maxdd']:6.1%}  turnover {bench_to:5.1f}x/yr")
    for name, score in signals(close, ret).items():
        r, to = simulate(ret, elig, score, days)
        s, active = stats(r), (r - bench)
        by_year = {str(y): g.to_numpy() for y, g in active.groupby(active.index.year)}
        ev = evaluate_variant_vs_baseline(by_year, n_bootstrap=N_BOOT)
        p = one_sided_p(active.to_numpy())
        adopt = ev["adopt"] and p < ALPHA_ADJ
        print(f"\n{name:16s} CAGR {s['cagr']:+7.1%}  Sharpe {s['sharpe']:5.2f}  maxDD {s['maxdd']:6.1%}  turnover {to:5.1f}x/yr")
        pl = ev["pooled"]
        print(f"  pooled active ann. {pl['observed_mean_annualized']:+.1%} CI [{pl['ci_2_5_annualized']:+.1%}, {pl['ci_97_5_annualized']:+.1%}]  one-sided p {p:.4f} (need < {ALPHA_ADJ:.4f})")
        for y, res in ev["by_year"].items():
            print(f"    {y}: active {res['observed_mean_annualized']:+.1%}  CI [{res['ci_2_5_annualized']:+.1%}, {res['ci_97_5_annualized']:+.1%}]")
        print(f"  clean-loss years {ev['clean_loss_years']}  ->  ADOPT: {adopt}")


if __name__ == "__main__":
    main()
