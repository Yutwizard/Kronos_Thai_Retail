"""Wayfinder ticket .scratch/regime-conditional-alpha/issues/01: does the
strategy's daily active return (vs equal-weight) actually differ between
SET bull-days and bear-days, as CLAUDE.md's "Alpha is regime-conditional"
claim asserts?

Regime signal: SET index (^SET.BK), trailing 60-trading-day return (bull if
>0, bear if <=0) -- matches CLAUDE.md's own wording ("SET regimes") and
reuses the 60-day/12-week trailing-window convention kth/trading/portfolio.py
already uses for its own Sharpe band. Uses raw SET history (has data back to
2016) reindexed onto the same business-day calendar the backtest itself uses,
so early-2023 days can look back into 2022 for the trailing window.

Test: same stationary block bootstrap as scripts/analyze_cap60_significance.py
(mirrors compute_sharpe_ci's block-length heuristic in kth/backtest/metrics.py),
applied to bull-day active returns, bear-day active returns, and their
difference, per year and pooled across 2023-2026. Reads the already-saved
daily_returns.parquet / benchmark_equal_weight.parquet from the 2026-07-29
authoritative re-run -- no new backtesting.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from kth.data.loader import load_cached

RESULTS_DIR = Path("./data/backtest_results")
YEARS = {
    "2023": ("2023-01-01", "2023-12-31"),
    "2024": ("2024-01-01", "2024-12-31"),
    "2025": ("2025-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-07-25"),
}
TRAILING_WINDOW = 60
N_BOOTSTRAP = 10000
SEED = 42


def build_regime_series() -> pd.Series:
    """Trailing 60-trading-day SET return, reindexed onto a full business-day
    calendar spanning well before 2023 (for lookback) through end of 2026 range,
    using the same ffill-asof convention the backtest itself uses for prices."""
    set_df = load_cached("^SET.BK")
    set_close = set_df.set_index("timestamps")["close"].sort_index()

    full_range = pd.date_range(start="2022-01-01", end="2026-07-25", freq="B")
    set_aligned = set_close.reindex(full_range, method="ffill")

    trailing_return = set_aligned / set_aligned.shift(TRAILING_WINDOW) - 1
    regime = trailing_return.apply(lambda r: "bull" if r > 0 else "bear")
    return regime


def block_bootstrap_mean_ci(values: np.ndarray, n_bootstrap: int, seed: int) -> dict:
    n = len(values)
    if n < 2:
        return {"n_obs": n, "mean": float(values.mean()) if n else float("nan"),
                "ci_2_5": float("nan"), "ci_97_5": float("nan")}
    expected_block = max(int(n ** (1 / 3)), 2)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_bootstrap):
        sample = np.empty(n)
        idx = 0
        while idx < n:
            block_len = rng.geometric(1.0 / expected_block)
            block_len = min(block_len, n - idx)
            start = rng.integers(0, n)
            for j in range(block_len):
                sample[idx + j] = values[(start + j) % n]
            idx += block_len
        means.append(sample.mean())
    means = np.array(means)
    return {
        "n_obs": n,
        "mean": float(values.mean()),
        "ci_2_5": float(np.percentile(means, 2.5)),
        "ci_97_5": float(np.percentile(means, 97.5)),
    }


def diff_block_bootstrap_ci(bull: np.ndarray, bear: np.ndarray, n_bootstrap: int, seed: int) -> dict:
    """Bootstrap the difference (bull_mean - bear_mean) by resampling each
    group's own block bootstrap independently and differencing per draw --
    valid since bull-days and bear-days are disjoint (different calendar days)."""
    n_bull, n_bear = len(bull), len(bear)
    if n_bull < 2 or n_bear < 2:
        return {"diff_mean": float("nan"), "ci_2_5": float("nan"), "ci_97_5": float("nan"), "prob_diff_ge_zero": float("nan")}
    eb_bull = max(int(n_bull ** (1 / 3)), 2)
    eb_bear = max(int(n_bear ** (1 / 3)), 2)
    rng = np.random.default_rng(seed)

    def resample(values, n, expected_block):
        sample = np.empty(n)
        idx = 0
        while idx < n:
            block_len = min(rng.geometric(1.0 / expected_block), n - idx)
            start = rng.integers(0, n)
            for j in range(block_len):
                sample[idx + j] = values[(start + j) % n]
            idx += block_len
        return sample

    diffs = []
    for _ in range(n_bootstrap):
        bull_mean = resample(bull, n_bull, eb_bull).mean()
        bear_mean = resample(bear, n_bear, eb_bear).mean()
        diffs.append(bull_mean - bear_mean)
    diffs = np.array(diffs)
    return {
        "diff_mean": float(bull.mean() - bear.mean()),
        "ci_2_5": float(np.percentile(diffs, 2.5)),
        "ci_97_5": float(np.percentile(diffs, 97.5)),
        "prob_diff_ge_zero": float((diffs >= 0).mean()),
    }


def main():
    regime = build_regime_series()

    all_bull, all_bear = [], []
    print(f"Regime split: trailing {TRAILING_WINDOW}-day SET return, bull if >0 else bear\n")

    for year, (start, end) in YEARS.items():
        d = RESULTS_DIR / f"thai_equity_{year}_n50"
        strat = pd.read_parquet(d / "daily_returns.parquet")["daily_returns"]
        ew = pd.read_parquet(d / "benchmark_equal_weight.parquet").iloc[:, 0]
        ew_rets = ew.pct_change().dropna()

        aligned = pd.concat([strat.rename("strat"), ew_rets.rename("ew")], axis=1, join="inner").dropna()
        active = aligned["strat"] - aligned["ew"]

        year_regime = regime.reindex(active.index)
        bull_mask = year_regime == "bull"
        bear_mask = year_regime == "bear"

        bull_vals = active[bull_mask].values
        bear_vals = active[bear_mask].values
        all_bull.append(bull_vals)
        all_bear.append(bear_vals)

        bull_r = block_bootstrap_mean_ci(bull_vals, N_BOOTSTRAP, SEED)
        bear_r = block_bootstrap_mean_ci(bear_vals, N_BOOTSTRAP, SEED)
        diff_r = diff_block_bootstrap_ci(bull_vals, bear_vals, N_BOOTSTRAP, SEED)

        print(f"[{year}] bull_days={bull_r['n_obs']:4d} (mean_active={bull_r['mean']*252:+7.2%} ann, "
              f"CI=[{bull_r['ci_2_5']*252:+7.2%},{bull_r['ci_97_5']*252:+7.2%}])")
        print(f"        bear_days={bear_r['n_obs']:4d} (mean_active={bear_r['mean']*252:+7.2%} ann, "
              f"CI=[{bear_r['ci_2_5']*252:+7.2%},{bear_r['ci_97_5']*252:+7.2%}])")
        print(f"        (bull - bear) diff_ann={diff_r['diff_mean']*252:+7.2%}  "
              f"95% CI=[{diff_r['ci_2_5']*252:+7.2%}, {diff_r['ci_97_5']*252:+7.2%}]  "
              f"P(diff>=0)={diff_r['prob_diff_ge_zero']:.3f}\n")

    pooled_bull = np.concatenate(all_bull)
    pooled_bear = np.concatenate(all_bear)
    bull_r = block_bootstrap_mean_ci(pooled_bull, N_BOOTSTRAP, SEED)
    bear_r = block_bootstrap_mean_ci(pooled_bear, N_BOOTSTRAP, SEED)
    diff_r = diff_block_bootstrap_ci(pooled_bull, pooled_bear, N_BOOTSTRAP, SEED)

    print(f"[pooled 2023-2026] bull_days={bull_r['n_obs']:4d} (mean_active={bull_r['mean']*252:+7.2%} ann, "
          f"CI=[{bull_r['ci_2_5']*252:+7.2%},{bull_r['ci_97_5']*252:+7.2%}])")
    print(f"                   bear_days={bear_r['n_obs']:4d} (mean_active={bear_r['mean']*252:+7.2%} ann, "
          f"CI=[{bear_r['ci_2_5']*252:+7.2%},{bear_r['ci_97_5']*252:+7.2%}])")
    print(f"                   (bull - bear) diff_ann={diff_r['diff_mean']*252:+7.2%}  "
          f"95% CI=[{diff_r['ci_2_5']*252:+7.2%}, {diff_r['ci_97_5']*252:+7.2%}]  "
          f"P(diff>=0)={diff_r['prob_diff_ge_zero']:.3f}")


if __name__ == "__main__":
    main()
