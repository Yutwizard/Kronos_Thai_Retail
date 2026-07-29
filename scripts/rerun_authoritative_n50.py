"""Re-run the authoritative per-year thai_equity n=50 backtests
(data/backtest_results/MANIFEST.md) now that the duplicate-mark-day bug in
run_walkforward (fixed alongside .scratch/optimize-entry-exit) no longer
crashes compute_metrics(). Same config as the original run_<year>_n50.py
scripts; overwrites the stale pre-2026-06-21-fix directories in place
(data/backtest_results/ is git-ignored, purely local cache).

No new Kronos inference needed -- data/forecast_cache/NeoQuasar_Kronos-small/
already covers 2020-01-01 to 2026-07-25, so a lightweight stub stands in for
KronosTH (run_walkforward only reads .model_name to derive the cache slug).
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from kth.data.universe import UNIVERSE
from kth.backtest.walkforward import BacktestConfig, run_walkforward

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]

YEARS = {
    "2023": ("2023-01-01", "2023-12-31"),
    "2024": ("2024-01-01", "2024-12-31"),
    "2025": ("2025-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-07-25"),
}

OUT_ROOT = Path("./data/backtest_results")


@dataclass
class _StubModel:
    model_name: str = "NeoQuasar/Kronos-small"


def main():
    stub = _StubModel()
    print(f"Universe: {len(TICKERS)} thai_equity tickers, n_samples=50\n")

    summary = []
    for year, (start, end) in YEARS.items():
        t0 = time.time()
        config = BacktestConfig(
            start_date=start, end_date=end,
            lookback=400, pred_len=20, n_samples=50,
            position_sizing="equal", max_positions=5,
            min_ticker_history=20,
        )
        result = run_walkforward(config, stub, TICKERS)
        elapsed = time.time() - t0

        out_dir = OUT_ROOT / f"thai_equity_{year}_n50"
        out_dir.mkdir(parents=True, exist_ok=True)
        result.save(str(out_dir))

        m = result.metrics
        row = {"year": year, **m, "n_trades": len(result.trades)}
        summary.append(row)
        print(
            f"[{year}] elapsed={elapsed:5.1f}s  CAGR={m['cagr']:+.2%}  "
            f"Sharpe={m['sharpe']:.2f}  Sortino={m['sortino']:.2f}  "
            f"MaxDD={m['max_drawdown']:.2%}  PSR0.5={m['psr_0_5']:.3f}  "
            f"alpha={m['alpha_vs_equal_weight']:+.4f}  beta={m['beta']:.3f}  "
            f"IR={m['information_ratio']:.2f}  p={m['p_value']:.3f}  "
            f"friction={m['total_friction_paid']:.4f}  trades={row['n_trades']}",
            flush=True,
        )
        print(f"  -> saved to {out_dir}")

    with open(OUT_ROOT / "authoritative_n50_rerun_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {OUT_ROOT / 'authoritative_n50_rerun_summary.json'}")


if __name__ == "__main__":
    main()
