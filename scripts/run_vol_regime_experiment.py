"""Ticket .scratch/future-plan/03: volatility-regime entry-buffer experiment.

Compares the Baseline Configuration (production entry/exit settings) against ONE
fixed variant -- entry buffer doubled when today's cross-sectional median 20-day
volatility is above its expanding historical 80th percentile -- for thai_equity,
n_samples=50, per year 2023-2026. No grid: parameters are fixed before running.

Reads entirely from the local Forecast Cache (no Kronos inference). The baseline
run must reproduce the stored authoritative n50 metrics or the script aborts, so a
verdict is never issued against a baseline that drifted.

Acceptance rule (kth.backtest.metrics.evaluate_variant_vs_baseline): adopt only if
the pooled 2023-2026 paired block-bootstrap 95% CI on daily active return
(variant - baseline) is entirely above zero AND no single year's CI is entirely
below zero.

Usage: venv/bin/python scripts/run_vol_regime_experiment.py
Output: data/backtest_results/vol_regime_experiment/
"""
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kth.backtest.metrics import evaluate_variant_vs_baseline
from kth.backtest.walkforward import BacktestConfig, run_walkforward
from kth.data.universe import UNIVERSE

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]

YEARS = {
    "2023": ("2023-01-01", "2023-12-31"),
    "2024": ("2024-01-01", "2024-12-31"),
    "2025": ("2025-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-07-25"),
}

VARIANT_MULTIPLIER = 2.0
OUT_ROOT = Path("./data/backtest_results/vol_regime_experiment")
STORED_ROOT = Path("./data/backtest_results")
N_BOOTSTRAP = 10000
SEED = 42

REPORT_KEYS = ["cagr", "sharpe", "max_drawdown", "annual_turnover", "total_friction_paid"]


@dataclass
class _StubModel:
    model_name: str = "NeoQuasar/Kronos-small"


def _config(start: str, end: str, multiplier: float | None) -> BacktestConfig:
    return BacktestConfig(
        start_date=start, end_date=end,
        lookback=400, pred_len=20, n_samples=50,
        position_sizing="equal", max_positions=5,
        min_ticker_history=20,
        regime_buffer_multiplier=multiplier,
    )


def _check_baseline_matches_stored(year: str, metrics: dict) -> None:
    stored = json.loads((STORED_ROOT / f"thai_equity_{year}_n50" / "metrics.json").read_text())
    for key in ("cagr", "sharpe", "max_drawdown"):
        if not math.isclose(metrics[key], stored[key], rel_tol=1e-6, abs_tol=1e-9):
            raise RuntimeError(
                f"Baseline {year} {key}={metrics[key]!r} does not reproduce the stored "
                f"authoritative run ({stored[key]!r}). Aborting: no verdict against a drifted baseline."
            )


def main():
    stub = _StubModel()
    print(f"Universe: {len(TICKERS)} thai_equity tickers; variant = entry buffer x{VARIANT_MULTIPLIER} "
          f"in high-vol regimes\n")

    rows = []
    active_by_year = {}
    t_start = time.time()

    for year, (start, end) in YEARS.items():
        results = {}
        for name, multiplier in (("baseline", None), ("variant", VARIANT_MULTIPLIER)):
            t0 = time.time()
            result = run_walkforward(_config(start, end, multiplier), stub, TICKERS)
            out_dir = OUT_ROOT / f"{name}_{year}"
            out_dir.mkdir(parents=True, exist_ok=True)
            result.save(str(out_dir))
            results[name] = result
            if name == "baseline":
                _check_baseline_matches_stored(year, result.metrics)
            m = result.metrics
            rows.append({"config": name, "year": year, **{k: m.get(k) for k in REPORT_KEYS},
                         "n_trades": len(result.trades) if result.trades is not None else 0})
            print(f"[{name:8s} {year}] {time.time() - t0:5.1f}s  CAGR={m['cagr']:+.2%}  "
                  f"Sharpe={m['sharpe']:.2f}  turnover={m['annual_turnover']:.2f}  "
                  f"friction={m['total_friction_paid']:.4f}", flush=True)

        aligned = pd.concat([results["variant"].daily_returns.rename("v"),
                             results["baseline"].daily_returns.rename("b")], axis=1).dropna()
        active_by_year[year] = (aligned["v"] - aligned["b"]).to_numpy()

    verdict = evaluate_variant_vs_baseline(active_by_year, n_bootstrap=N_BOOTSTRAP, seed=SEED)

    print(f"\nPaired block bootstrap (n={N_BOOTSTRAP}, seed={SEED}), variant - baseline daily active return:")
    for year, r in verdict["by_year"].items():
        print(f"  [{year}] n={r['n_obs']:4d}  active(ann)={r['observed_mean_annualized']:+8.2%}  "
              f"95% CI=[{r['ci_2_5_annualized']:+8.2%}, {r['ci_97_5_annualized']:+8.2%}]")
    p = verdict["pooled"]
    print(f"  [pooled] n={p['n_obs']:4d}  active(ann)={p['observed_mean_annualized']:+8.2%}  "
          f"95% CI=[{p['ci_2_5_annualized']:+8.2%}, {p['ci_97_5_annualized']:+8.2%}]")
    print(f"\nClean-loss years: {verdict['clean_loss_years'] or 'none'}")
    print(f"VERDICT: {'ADOPT' if verdict['adopt'] else 'REJECT'}")
    print(f"Total time: {(time.time() - t_start) / 60:.1f} min")

    (OUT_ROOT / "summary.json").write_text(json.dumps({"runs": rows, "verdict": verdict}, indent=2, default=float))


if __name__ == "__main__":
    main()
