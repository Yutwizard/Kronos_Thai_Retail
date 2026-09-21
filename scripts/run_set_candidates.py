"""Pre-registered literature candidates vs equal-weight (ticket .scratch/future-plan/09).

Usage: venv/bin/python scripts/run_set_candidates.py [START END]   (default 2023-01-02 2026-07-25)
Design is frozen in the ticket; do not change parameters after seeing a result.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import (  # noqa: E402
    ALPHA_ADJ, MIN_HIST, N_BOOT, ONE_WAY, TICKERS, TOP_N, load_closes, one_sided_p, simulate, stats,
)

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402

START, END = "2023-01-02", "2026-07-25"
INDEX_END = "2026-07-17"  # last real ^SET.BK row (later row is a zero-volume stub)
EMBARGO, HORIZON, MIN_TRAIN_DATES, LAMBDA = 90, 20, 250, 0.90
LGB_PARAMS = dict(n_estimators=50, max_depth=3, num_leaves=8, min_child_samples=50, learning_rate=0.05,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=0, verbosity=-1)


def load_volume() -> pd.DataFrame:
    cols = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        cols[t] = d.set_index(pd.to_datetime(d["timestamps"]))["volume"]
    return pd.DataFrame(cols).sort_index()


def month_first_days(days) -> list:
    out, last = [], None
    for d in days:
        if d.month != last:
            last = d.month
            out.append(d)
    return out


def simulate_gross(ret, elig, days, weights_fn):
    """Like run_factor_baselines.simulate but returns gross returns and rebalance costs separately."""
    w = pd.Series(0.0, index=ret.columns)
    gross, cost_s, turnover, last_month = {}, {}, 0.0, None
    for d in days:
        prev = ret.index[ret.index.get_loc(d) - 1]
        cost = 0.0
        if d.month != last_month:
            last_month = d.month
            target = weights_fn(prev)
            t_o = float((target - w).abs().sum())
            turnover += t_o
            cost = t_o * ONE_WAY
            w = target
        r = ret.loc[d].fillna(0.0)
        day_ret = float((w * r).sum())
        gross[d], cost_s[d] = day_ret, cost
        g = 1.0 + day_ret
        w = w * (1.0 + r) / g if g > 0 else w
    return pd.Series(gross), pd.Series(cost_s), turnover / (len(days) / 252)


def ew_weights(elig, cols):
    def fn(prev):
        e = elig.loc[prev]
        names = e[e].index
        t = pd.Series(0.0, index=cols)
        t[names] = 1.0 / len(names)
        return t
    return fn


def topn_weights(elig, score, cols):
    ew = ew_weights(elig, cols)

    def fn(prev):
        e = elig.loc[prev]
        picks = score.loc[prev, e[e].index].dropna().nlargest(TOP_N).index
        if len(picks) == 0:  # too little training data: hold the equal-weight basket
            return ew(prev)
        t = pd.Series(0.0, index=cols)
        t[picks] = 1.0 / len(picks)
        return t
    return fn


def sma_weights(elig, close, cols):
    sma = close.rolling(200).mean()

    def fn(prev):
        e = elig.loc[prev]
        names = e[e].index
        hold = [n for n in names if close.loc[prev, n] > sma.loc[prev, n]]
        t = pd.Series(0.0, index=cols)
        t[hold] = 1.0 / len(names)  # remainder of the book is cash
        return t
    return fn


def vp_macd_state(index_df: pd.DataFrame) -> pd.Series:
    d = index_df[index_df["volume"] > 0].copy()
    d.index = pd.to_datetime(d["timestamps"])
    rng = d["high"] - d["low"]
    sigma = (d["high"] - d["low"]).rolling(20).std() / d["close"]
    r = ((d["close"] - d["open"]).abs() / rng.where(rng > 0)).fillna(0.0)
    num = (d["close"] * d["volume"] * sigma * r).rolling(20).sum()
    p_star = num / d["volume"].rolling(20).sum()
    macd = p_star.ewm(span=12, adjust=False).mean() - p_star.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    buy = (macd.shift(1) <= LAMBDA * sig.shift(1)) & (macd > LAMBDA * sig)
    sell = (macd.shift(1) >= sig.shift(1)) & (macd < sig)
    state, cur = [], 0
    for b, s in zip(buy.to_numpy(), sell.to_numpy()):
        if b:
            cur = 1
        elif s:
            cur = 0
        state.append(cur)
    return pd.Series(state, index=d.index)


def lgbm_scores(close, vol, ret, elig, days) -> pd.DataFrame:
    import lightgbm as lgb

    feats = {
        "mom_1m": close / close.shift(21) - 1, "mom_3m": close / close.shift(63) - 1,
        "mom_12m": close / close.shift(252) - 1, "vol_20d": ret.rolling(20).std(),
        "vol_60d": ret.rolling(60).std(), "adv_20d": np.log((close * vol).rolling(20).mean().where(lambda x: x > 0)),
    }
    ranked = {k: v.where(elig).rank(axis=1, pct=True) for k, v in feats.items()}
    fwd = close.shift(-HORIZON) / close - 1
    label = fwd - fwd.where(elig).mean(axis=1).to_numpy()[:, None]
    idx = close.index
    pos = pd.Series(np.arange(len(idx)), index=idx)
    stack = pd.concat({k: v.stack(future_stack=True) for k, v in ranked.items()}, axis=1)
    stack["label"] = label.stack(future_stack=True)
    stack["date"] = stack.index.get_level_values(0)
    score = pd.DataFrame(np.nan, index=idx, columns=close.columns)
    for d in month_first_days(days):
        prev = idx[idx.get_loc(d) - 1]
        cutoff = pos[prev] - EMBARGO - HORIZON
        train = stack[(stack["date"].map(pos) <= cutoff)].dropna()
        if train["date"].nunique() < MIN_TRAIN_DATES:
            continue
        model = lgb.LGBMRegressor(**LGB_PARAMS).fit(train[list(feats)], train["label"])
        names = elig.loc[prev]
        names = names[names].index
        x = pd.DataFrame({k: ranked[k].loc[prev, names] for k in feats}).dropna()
        score.loc[prev, x.index] = model.predict(x)
    return score


def report(name, r, bench, to=None, note=""):
    s, active = stats(r), (r - bench)
    by_year = {str(y): g.to_numpy() for y, g in active.groupby(active.index.year)}
    ev = evaluate_variant_vs_baseline(by_year, n_bootstrap=N_BOOT)
    p = one_sided_p(active.to_numpy())
    pl = ev["pooled"]
    tos = f"  turnover {to:5.1f}x/yr" if to is not None else ""
    print(f"\n{name:22s} CAGR {s['cagr']:+7.1%}  Sharpe {s['sharpe']:5.2f}  maxDD {s['maxdd']:6.1%}{tos} {note}")
    print(f"  pooled active ann. {pl['observed_mean_annualized']:+.1%} CI [{pl['ci_2_5_annualized']:+.1%}, {pl['ci_97_5_annualized']:+.1%}]  one-sided p {p:.4f} (need < {ALPHA_ADJ:.4f} discovery / < 0.05 holdout)")
    for y, res in ev["by_year"].items():
        print(f"    {y}: active {res['observed_mean_annualized']:+.1%}  CI [{res['ci_2_5_annualized']:+.1%}, {res['ci_97_5_annualized']:+.1%}]")
    print(f"  clean-loss years {ev['clean_loss_years']}  ->  ADOPT (discovery rule): {ev['adopt'] and p < ALPHA_ADJ}")


def main():
    close = load_closes()
    vol = load_volume().reindex(close.index)
    ret = close.pct_change(fill_method=None)
    elig = close.notna() & (close.notna().cumsum() >= MIN_HIST)
    start, end = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (START, END)
    days = ret.loc[start:end].index
    cols = close.columns
    g, c, bench_to = simulate_gross(ret, elig, days, ew_weights(elig, cols))
    bench = g - c
    chk, _ = simulate(ret, elig, None, days)
    assert np.allclose(bench.to_numpy(), chk.to_numpy()), "benchmark mismatch vs ticket-06 simulate"
    b = stats(bench)
    print(f"window {start}..{end}  days {len(days)}  eligible {int(elig.loc[days[0]].sum())} at start, {int(elig.loc[days[-1]].sum())} at end")
    print(f"{'equal_weight':22s} CAGR {b['cagr']:+7.1%}  Sharpe {b['sharpe']:5.2f}  maxDD {b['maxdd']:6.1%}  turnover {bench_to:5.1f}x/yr")

    # Candidate 1: monthly LightGBM long-leg ranker
    score = lgbm_scores(close, vol, ret, elig, days)
    fired = int(score.notna().any(axis=1).sum())
    g1, c1, to1 = simulate_gross(ret, elig, days, topn_weights(elig, score, cols))
    report("C1 lgbm_top10_monthly", g1 - c1, bench, to1, f"(retrain months scored: {fired})")

    # Candidate 2: VP-MACD index-timing overlay on the equal-weight basket
    st = vp_macd_state(pd.read_parquet("data/raw/_SET.BK.parquet"))
    st = st.reindex(close.index, method="ffill").fillna(0).astype(int)
    d2 = days[days <= pd.Timestamp(INDEX_END)]
    prev_state = st.shift(1).reindex(d2).fillna(0)
    switch = prev_state.diff().abs().fillna(0.0)
    r2 = prev_state * (g.loc[d2] - c.loc[d2]) - switch * ONE_WAY
    report("C2 vpmacd_overlay", r2, bench.loc[d2], None,
           f"(days {len(d2)}, exposure {prev_state.mean():.0%}, switches {int(switch.sum())})")

    # Candidate 3: stock-level 200d SMA trend filter (rest in cash)
    g3, c3, to3 = simulate_gross(ret, elig, days, sma_weights(elig, close, cols))
    report("C3 sma200_filter", g3 - c3, bench, to3)


if __name__ == "__main__":
    main()
