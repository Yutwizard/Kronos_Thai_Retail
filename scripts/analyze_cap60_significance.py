"""Wayfinder ticket follow-up: is cap60's edge over baseline distinguishable
from ordinary return-path noise, holding the (single) Kronos forecast draw
fixed?

Deliberately NOT reusing compute_bootstrap_pvalue() (CLAUDE.md reserves that
one for live dashboard /api/risk only) or touching compute_metrics()'s
t-test p_value (reserved for historical-backtest citation, never changed).
This is a new, separate statistic: a stationary block bootstrap (same
block-length heuristic as compute_sharpe_ci in kth/backtest/metrics.py, which
already uses this method for Sharpe CIs) on the *paired daily active-return
series* (cap60 - baseline), per year and pooled across 2023-2026.

Reads the already-saved daily_returns.parquet from
data/backtest_results/max_holding_sweep/{baseline,cap60}_{year}/ -- no new
Kronos inference, no new walk-forward runs.
"""
import numpy as np
import pandas as pd
from pathlib import Path

RESULTS_DIR = Path("./data/backtest_results/max_holding_sweep")
YEARS = ["2023", "2024", "2025", "2026"]
N_BOOTSTRAP = 10000
SEED = 42


def load_daily_returns(config: str, year: str) -> pd.Series:
    path = RESULTS_DIR / f"{config}_{year}" / "daily_returns.parquet"
    return pd.read_parquet(path)["daily_returns"]


def block_bootstrap_mean_ci(active: np.ndarray, n_bootstrap: int, seed: int) -> dict:
    """Same stationary block bootstrap as compute_sharpe_ci (kth/backtest/metrics.py):
    geometric block lengths, expected block ~ n^(1/3). Returns CI + P(mean<=0)
    on the *mean* of the resampled active-return series (not centered under H0
    -- a direct percentile bootstrap CI, mirroring compute_sharpe_ci's method)."""
    n = len(active)
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
                sample[idx + j] = active[(start + j) % n]
            idx += block_len
        means.append(sample.mean())
    means = np.array(means)
    return {
        "n_obs": n,
        "observed_mean_daily": float(active.mean()),
        "observed_mean_annualized": float(active.mean() * 252),
        "ci_2_5_annualized": float(np.percentile(means, 2.5) * 252),
        "ci_97_5_annualized": float(np.percentile(means, 97.5) * 252),
        "prob_mean_le_zero": float((means <= 0).mean()),
    }


def main():
    print(f"Block bootstrap (n={N_BOOTSTRAP}, seed={SEED}) on cap60 - baseline daily active returns\n")
    all_active = []
    for year in YEARS:
        base = load_daily_returns("baseline", year)
        cap60 = load_daily_returns("cap60", year)
        aligned = pd.concat([cap60.rename("cap60"), base.rename("base")], axis=1).dropna()
        active = (aligned["cap60"] - aligned["base"]).values
        all_active.append(active)

        r = block_bootstrap_mean_ci(active, N_BOOTSTRAP, SEED)
        print(
            f"[{year}] n={r['n_obs']:4d}  "
            f"active_mean(ann)={r['observed_mean_annualized']:+7.2%}  "
            f"95% CI=[{r['ci_2_5_annualized']:+7.2%}, {r['ci_97_5_annualized']:+7.2%}]  "
            f"P(active<=0)={r['prob_mean_le_zero']:.3f}"
        )

    pooled = np.concatenate(all_active)
    r = block_bootstrap_mean_ci(pooled, N_BOOTSTRAP, SEED)
    print(f"\n[pooled 2023-2026] n={r['n_obs']:4d}  "
          f"active_mean(ann)={r['observed_mean_annualized']:+7.2%}  "
          f"95% CI=[{r['ci_2_5_annualized']:+7.2%}, {r['ci_97_5_annualized']:+7.2%}]  "
          f"P(active<=0)={r['prob_mean_le_zero']:.3f}")


if __name__ == "__main__":
    main()
