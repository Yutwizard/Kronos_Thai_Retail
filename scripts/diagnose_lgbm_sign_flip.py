"""Ticket .scratch/future-plan/15: diagnose the LightGBM ranker's sign flip between ticket-09's windows.

Read-only diagnostics on the FROZEN candidate-1 model from ticket 09 (kth/data/clean.py loader from ticket 13).
No parameter is tuned; no output here is adopted or promoted to the paper track (ticket 15's own rule).

Usage: venv/bin/python scripts/diagnose_lgbm_sign_flip.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import ALPHA_ADJ, MIN_HIST, N_BOOT, ONE_WAY, TICKERS, TOP_N, one_sided_p, simulate, stats  # noqa: E402
from run_set_candidates import EMBARGO, HORIZON, LGB_PARAMS, MIN_TRAIN_DATES, load_volume, month_first_days, topn_weights  # noqa: E402

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402
from kth.data.clean import load_clean_closes  # noqa: E402

WINDOWS = {"discovery": ("2023-01-02", "2026-07-25"), "holdout": ("2020-01-02", "2022-12-30")}
FEATURES = ["mom_1m", "mom_3m", "mom_12m", "vol_20d", "vol_60d", "adv_20d"]


def load_closes_original() -> pd.DataFrame:
    cols = {}
    for t in TICKERS:
        d = pd.read_parquet(f"data/raw/{t}.parquet")
        cols[t] = d.set_index(pd.to_datetime(d["timestamps"]))["close"]
    return pd.DataFrame(cols).sort_index().ffill(limit=10)


def build_ranked_features(close, vol, ret, elig):
    feats = {
        "mom_1m": close / close.shift(21) - 1, "mom_3m": close / close.shift(63) - 1,
        "mom_12m": close / close.shift(252) - 1, "vol_20d": ret.rolling(20).std(),
        "vol_60d": ret.rolling(60).std(), "adv_20d": np.log((close * vol).rolling(20).mean().where(lambda x: x > 0)),
    }
    ranked = {k: v.where(elig).rank(axis=1, pct=True) for k, v in feats.items()}
    fwd = close.shift(-HORIZON) / close - 1
    label = fwd - fwd.where(elig).mean(axis=1).to_numpy()[:, None]
    return ranked, fwd, label


def run_instrumented(close, vol, ret, elig, days, feature_subset):
    """Like run_set_candidates.lgbm_scores but records per-month feature importances, IC inputs
    and the top-10 picks, for a given feature subset (diagnostic sensitivity variant)."""
    import lightgbm as lgb

    ranked, fwd, label = build_ranked_features(close, vol, ret, elig)
    idx = close.index
    pos = pd.Series(np.arange(len(idx)), index=idx)
    stack = pd.concat({k: ranked[k].stack(future_stack=True) for k in feature_subset}, axis=1)
    stack["label"] = label.stack(future_stack=True)
    stack["date"] = stack.index.get_level_values(0)
    score = pd.DataFrame(np.nan, index=idx, columns=close.columns)
    importances, picks, ic_by_month = {}, {}, {}
    for d in month_first_days(days):
        prev = idx[idx.get_loc(d) - 1]
        cutoff = pos[prev] - EMBARGO - HORIZON
        train = stack[(stack["date"].map(pos) <= cutoff)].dropna()
        if train["date"].nunique() < MIN_TRAIN_DATES:
            continue
        model = lgb.LGBMRegressor(**LGB_PARAMS).fit(train[feature_subset], train["label"])
        importances[d] = dict(zip(feature_subset, model.feature_importances_.astype(float)))
        names = elig.loc[prev]; names = names[names].index
        x = pd.DataFrame({k: ranked[k].loc[prev, names] for k in feature_subset}).dropna()
        if len(x):
            s = pd.Series(model.predict(x), index=x.index)
            score.loc[prev, x.index] = s
            picks[d] = set(s.nlargest(TOP_N).index)
            # monthly rank IC: this month's score vs the 20-day forward return realised from `prev`
            realized = fwd.loc[prev, x.index]
            valid = realized.notna()
            if valid.sum() >= 10:
                ic_by_month[d] = float(s[valid].corr(realized[valid], method="spearman"))
    return score, importances, picks, ic_by_month


def pooled_summary(active: pd.Series) -> dict:
    by_year = {str(y): g.to_numpy() for y, g in active.groupby(active.index.year)}
    ev = evaluate_variant_vs_baseline(by_year, n_bootstrap=N_BOOT)
    p = one_sided_p(active.to_numpy())
    pl = ev["pooled"]
    return {"mean": pl["observed_mean_annualized"], "lo": pl["ci_2_5_annualized"], "hi": pl["ci_97_5_annualized"],
            "p": p, "adopt": bool(ev["adopt"] and p < ALPHA_ADJ)}


def block_ci(x: np.ndarray, seed: int = 42) -> tuple[float, float, float]:
    n = len(x)
    if n < 5:
        return float(np.mean(x)) if n else float("nan"), float("nan"), float("nan")
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


def analyze_window(label, close, vol, elig, days):
    ret = close.pct_change(fill_method=None)
    bench, _ = simulate(ret, elig, None, days)

    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")

    # 1/2/3: full-feature model, importances and monthly IC
    score, imp, picks, ic_by_month = run_instrumented(close, vol, ret, elig, days, FEATURES)
    r, to = simulate(ret, elig, score, days)
    active = r - bench
    s = pooled_summary(active)
    print(f"full model: pooled active {s['mean']:+.1%} [{s['lo']:+.1%}, {s['hi']:+.1%}] p {s['p']:.4f} turnover {to:.1f}x/yr months scored {len(imp)}")

    imp_df = pd.DataFrame(imp).T.fillna(0.0)
    imp_share = imp_df.div(imp_df.sum(axis=1), axis=0)
    print("mean feature importance share across retrain months:")
    print("  " + "  ".join(f"{k}={v:.1%}" for k, v in imp_share.mean().sort_values(ascending=False).items()))
    print("first 3 months' importance share vs last 3 months' (feature drift):")
    print("  first3: " + "  ".join(f"{k}={v:.1%}" for k, v in imp_share.iloc[:3].mean().sort_values(ascending=False).items()))
    print("  last3:  " + "  ".join(f"{k}={v:.1%}" for k, v in imp_share.iloc[-3:].mean().sort_values(ascending=False).items()))

    ic = pd.Series(ic_by_month).dropna()
    m, lo, hi = block_ci(ic.to_numpy())
    print(f"monthly rank IC (score vs realized 20d return): mean {m:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  n={len(ic)} months")

    # 5: turnover / concentration
    months = sorted(picks)
    overlaps = [len(picks[months[i]] & picks[months[i - 1]]) / TOP_N for i in range(1, len(months))]
    all_picks = pd.Series([t for s in picks.values() for t in s])
    top_held = all_picks.value_counts()
    print(f"month-to-month top-10 overlap: mean {np.mean(overlaps):.1%} (0%=fully turns over, 100%=identical); "
          f"names held in >=50% of months: {int((top_held >= len(picks) * 0.5).sum())} of {len(top_held)} ever picked")

    # 4: sensitivity -- drop each feature, and drop adv_20d specifically, report sign/magnitude only
    print("sensitivity (drop-one-feature, no bootstrap, sign/magnitude only):")
    for drop in FEATURES:
        subset = [f for f in FEATURES if f != drop]
        score_d, _, _, _ = run_instrumented(close, vol, ret, elig, days, subset)
        r_d, _ = simulate(ret, elig, score_d, days)
        active_d = (r_d - bench)
        by_year_d = {str(y): g.to_numpy() for y, g in active_d.groupby(active_d.index.year)}
        pooled_mean = np.concatenate(list(by_year_d.values())).mean() * 252
        print(f"  drop {drop:9s}: pooled active (simple ann.) {pooled_mean:+.1%}")

    return s, ic, imp_share


def main():
    orig_close = load_closes_original()
    clean_close, _, rep = load_clean_closes(TICKERS)
    vol_orig = load_volume().reindex(orig_close.index)
    vol_clean = load_volume().reindex(clean_close.index)
    elig_orig = orig_close.notna() & (orig_close.notna().cumsum() >= MIN_HIST)
    elig_clean = clean_close.notna() & (clean_close.notna().cumsum() >= MIN_HIST)
    print(f"clean loader: dropped {len(rep.dropped_dates)} stub dates, breaks {rep.applied_breaks}")

    results = {}
    for wname, (start, end) in WINDOWS.items():
        days_o = orig_close.loc[start:end].index
        days_c = clean_close.loc[start:end].index
        s_o, ic_o, imp_o = analyze_window(f"{wname} ({start}..{end}) -- ORIGINAL loader", orig_close, vol_orig, elig_orig, days_o)
        s_c, ic_c, imp_c = analyze_window(f"{wname} ({start}..{end}) -- CLEAN loader (ticket 13)", clean_close, vol_clean, elig_clean, days_c)
        results[wname] = {"orig": s_o, "clean": s_c, "ic_orig": ic_o, "ic_clean": ic_c, "imp_orig": imp_o, "imp_clean": imp_c}

    print(f"\n{'=' * 78}\nSUMMARY (item 1: original vs clean loader vs the ticket-09/14/09-robustness figures already on record)\n{'=' * 78}")
    print("ticket-09 primary (original loader):    discovery -12.6% [-23.4%, -1.4%]   holdout +9.0% [-5.6%, +24.3%]")
    print("ticket-09 robustness (ad-hoc cleaned):   discovery  -4.2% [-15.5%, +7.2%]   holdout +12.3% [-2.0%, +27.3%]")
    for wname, r in results.items():
        print(f"{wname:10s} orig  {r['orig']['mean']:+6.1%} [{r['orig']['lo']:+6.1%}, {r['orig']['hi']:+6.1%}]   "
              f"clean {r['clean']['mean']:+6.1%} [{r['clean']['lo']:+6.1%}, {r['clean']['hi']:+6.1%}]   "
              f"mean IC orig {r['ic_orig'].mean():+.3f}  clean {r['ic_clean'].mean():+.3f}")


if __name__ == "__main__":
    main()
