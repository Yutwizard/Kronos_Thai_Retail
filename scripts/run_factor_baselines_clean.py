"""Ticket-06 factor baselines re-run on cleaned data (ticket .scratch/future-plan/14).

Robustness check of the ticket-06 family, NOT a new family: same three rules, same windows, same friction, same
bootstrap, same threshold 0.05/3. Only the price loader changes (kth.data.clean.load_clean_closes). Both the
original loader and the cleaned loader are run in one pass so the comparison uses identical code and data.

Usage: venv/bin/python scripts/run_factor_baselines_clean.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import (  # noqa: E402
    ALPHA_ADJ, MIN_HIST, N_BOOT, TICKERS, load_closes, one_sided_p, signals, simulate, stats,
)

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402
from kth.data.clean import load_clean_closes  # noqa: E402

WINDOWS = {"discovery": ("2023-01-02", "2026-07-25"), "holdout": ("2020-01-02", "2022-12-30")}


def run(close: pd.DataFrame, start: str, end: str) -> dict:
    ret = close.pct_change(fill_method=None)
    elig = close.notna() & (close.notna().cumsum() >= MIN_HIST)
    days = ret.loc[start:end].index
    bench, bench_to = simulate(ret, elig, None, days)
    out = {"days": len(days), "equal_weight": {**stats(bench), "turnover": bench_to}}
    for name, score in signals(close, ret).items():
        r, to = simulate(ret, elig, score, days)
        active = r - bench
        by_year = {str(y): g.to_numpy() for y, g in active.groupby(active.index.year)}
        ev = evaluate_variant_vs_baseline(by_year, n_bootstrap=N_BOOT)
        p = one_sided_p(active.to_numpy())
        out[name] = {**stats(r), "turnover": to, "pooled": ev["pooled"], "p": p, "by_year": ev["by_year"],
                     "clean_loss_years": ev["clean_loss_years"], "adopt": bool(ev["adopt"] and p < ALPHA_ADJ)}
    return out


def line(tag, r):
    pl = r["pooled"]
    return (f"  {tag:9s} CAGR {r['cagr']:+7.1%} Sharpe {r['sharpe']:5.2f} maxDD {r['maxdd']:6.1%} turn {r['turnover']:5.1f}x | "
            f"pooled active {pl['observed_mean_annualized']:+6.1%} [{pl['ci_2_5_annualized']:+6.1%}, {pl['ci_97_5_annualized']:+6.1%}] "
            f"p {r['p']:.4f} | clean-loss yrs {r['clean_loss_years']} | adopt {r['adopt']}")


def main():
    raw_close = load_closes()
    clean_close, _, rep = load_clean_closes(TICKERS)
    print(f"cleaning: dropped {len(rep.dropped_dates)} stub dates; breaks applied {rep.applied_breaks}; skipped {rep.skipped_breaks}")
    results = {}
    for wname, (s, e) in WINDOWS.items():
        a, b = run(raw_close, s, e), run(clean_close, s, e)
        results[wname] = (a, b)
        print(f"\n===== {wname} {s}..{e}  (days: original {a['days']}, cleaned {b['days']}) =====")
        for tag, r in (("orig EW", a["equal_weight"]), ("clean EW", b["equal_weight"])):
            print(f"  {tag:9s} CAGR {r['cagr']:+7.1%} Sharpe {r['sharpe']:5.2f} maxDD {r['maxdd']:6.1%} turn {r['turnover']:5.1f}x")
        for rule in ("momentum_12_1", "low_vol_60", "reversal_1m"):
            print(f"\n {rule}")
            print(line("original", a[rule])); print(line("cleaned", b[rule]))
            for y in b[rule]["by_year"]:
                ya, yb = a[rule]["by_year"].get(y), b[rule]["by_year"][y]
                if ya:
                    print(f"      {y}: original {ya['observed_mean_annualized']:+6.1%} -> cleaned {yb['observed_mean_annualized']:+6.1%}")
    mom_clean = results["discovery"][1]["momentum_12_1"]
    print("\nVERDICT (rule frozen in ticket 14): momentum on cleaned discovery data ->",
          "STILL WEAK AND UNCONFIRMED (passes the 0.0167 discovery bar; the 2020-2022 holdout is a separate question)"
          if mom_clean["adopt"] else "MOMENTUM LEAD WITHDRAWN (does not pass the discovery bar on cleaned data)")


if __name__ == "__main__":
    main()
