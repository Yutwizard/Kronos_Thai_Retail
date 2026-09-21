"""Pre-registered trend-filter check on the untouched 2018-2019 window (ticket .scratch/future-plan/10).

Usage: venv/bin/python scripts/run_trend_filter_check.py [START END]   (default 2018-01-02 2019-12-30)
Design is frozen in the ticket; do not change parameters after seeing a result.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import MIN_HIST, N_BOOT, ONE_WAY, load_closes, stats  # noqa: E402
from run_set_candidates import ew_weights, simulate_gross, sma_weights  # noqa: E402

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402

START, END = "2018-01-02", "2019-12-30"
ALPHA = 0.05 / 2  # family of 2 (V1, V2)


def sharpe(x: np.ndarray) -> float:
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def sharpe_diff_p(a: np.ndarray, b: np.ndarray, seed: int = 42) -> tuple[float, float, float]:
    """Paired stationary block bootstrap of Sharpe(a) - Sharpe(b); returns (observed, 95% CI low/high) and one-sided p via array."""
    n = len(a)
    rng = np.random.default_rng(seed)
    blk = max(int(n ** (1 / 3)), 2)
    diffs = np.empty(N_BOOT)
    for k in range(N_BOOT):
        idx, i = np.empty(n, dtype=int), 0
        while i < n:
            start, length = rng.integers(0, n), min(rng.geometric(1 / blk), n - i)
            idx[i:i + length] = (start + np.arange(length)) % n
            i += length
        diffs[k] = sharpe(a[idx]) - sharpe(b[idx])
    return sharpe(a) - sharpe(b), float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float((diffs <= 0).mean())


def index_state(index_df: pd.DataFrame) -> pd.Series:
    d = index_df[index_df["volume"] > 0].copy()
    d.index = pd.to_datetime(d["timestamps"])
    return (d["close"] > d["close"].rolling(200).mean()).astype(int)


def report(name, r, bench, note=""):
    s, b = stats(r), stats(bench)
    diff, lo, hi, p = sharpe_diff_p(r.to_numpy(), bench.to_numpy())
    active = r - bench
    by_year = {str(y): g.to_numpy() for y, g in active.groupby(active.index.year)}
    ev = evaluate_variant_vs_baseline(by_year, n_bootstrap=N_BOOT)
    pl = ev["pooled"]
    ok = (p < ALPHA) and (s["maxdd"] > b["maxdd"]) and (s["cagr"] >= b["cagr"] - 0.03)
    print(f"\n{name:20s} CAGR {s['cagr']:+7.1%}  Sharpe {s['sharpe']:5.2f}  maxDD {s['maxdd']:6.1%} {note}")
    print(f"  Sharpe diff vs equal-weight {diff:+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  one-sided p {p:.4f} (need < {ALPHA:.3f})")
    print(f"  maxDD lower than EW: {s['maxdd'] > b['maxdd']} ({s['maxdd']:.1%} vs {b['maxdd']:.1%});  CAGR gap {s['cagr'] - b['cagr']:+.1%} (limit -3.0%)")
    print(f"  secondary: pooled active ann. {pl['observed_mean_annualized']:+.1%} CI [{pl['ci_2_5_annualized']:+.1%}, {pl['ci_97_5_annualized']:+.1%}]")
    for y, res in ev["by_year"].items():
        print(f"    {y}: active {res['observed_mean_annualized']:+.1%}  CI [{res['ci_2_5_annualized']:+.1%}, {res['ci_97_5_annualized']:+.1%}]")
    print(f"  PASS (pre-registered rule): {ok}")


def main():
    close = load_closes()
    ret = close.pct_change(fill_method=None)
    elig = close.notna() & (close.notna().cumsum() >= MIN_HIST)
    start, end = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (START, END)
    days = ret.loc[start:end].index
    cols = close.columns
    g, c, bto = simulate_gross(ret, elig, days, ew_weights(elig, cols))
    bench = g - c
    b = stats(bench)
    print(f"window {start}..{end}  days {len(days)}  eligible {int(elig.loc[days[0]].sum())} at start, {int(elig.loc[days[-1]].sum())} at end")
    print(f"{'equal_weight':20s} CAGR {b['cagr']:+7.1%}  Sharpe {b['sharpe']:5.2f}  maxDD {b['maxdd']:6.1%}  turnover {bto:4.1f}x/yr")

    g1, c1, to1 = simulate_gross(ret, elig, days, sma_weights(elig, close, cols))
    report("V1 stock SMA200", g1 - c1, bench, f" turnover {to1:4.1f}x/yr")

    st = index_state(pd.read_parquet("data/raw/_SET.BK.parquet")).reindex(close.index, method="ffill").fillna(0).astype(int)
    prev_state = st.shift(1).reindex(days).fillna(0)
    switch = prev_state.diff().abs().fillna(0.0)
    r2 = prev_state * (g - c) - switch * ONE_WAY
    report("V2 index SMA200", r2, bench, f" exposure {prev_state.mean():.0%}, switches {int(switch.sum())}")


if __name__ == "__main__":
    main()
