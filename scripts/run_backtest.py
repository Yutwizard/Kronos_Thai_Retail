"""
Phase 2 — Full 51-ticker walk-forward backtest on GPU.

Required: scripts/download_data.py run first.
          ~30-90 min on T4 GPU (one-time precomputation, idempotent).
          Subsequent reruns skip already-cached dates (~instant).
          Writes ~76,500 files: .parquet + _meta.json per ticker per day.
"""
import time
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import (
    BacktestConfig, precompute_forecasts, run_walkforward,
)
from kth.data.universe import get_all_tickers


OUTPUT_DIR = Path("./data/backtest_results/2022-2024")


def main():
    tickers = get_all_tickers()
    print(f"Universe: {len(tickers)} tickers across 9 asset classes\n")

    # 1. Load model (auto-detect GPU/CPU)
    print("Loading Kronos-small (auto device)...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="auto")
    print(f"  Model: {k.model_name}")
    print(f"  Device: {k.device}")

    # 2. Backtest config
    config = BacktestConfig(
        start_date="2022-01-01",
        end_date="2024-12-31",
        lookback=400,
        pred_len=20,
        n_samples=50,
        position_sizing="equal",
    )

    # 3. Precompute forecasts (one-time, batches all 51 tickers per day)
    print(f"\nPrecomputing forecasts for {len(tickers)} tickers x ~750 days...")
    print("(Idempotent — skips already-cached dates.)")
    t0 = time.time()
    precompute_forecasts(
        k, tickers,
        start_date=config.start_date,
        end_date=config.end_date,
        pred_len=config.pred_len,
        n_samples=config.n_samples,
        lookback=config.lookback,
    )
    elapsed = time.time() - t0
    print(f"Precomputation done in {elapsed/60:.0f} min ({elapsed/3600:.1f} hrs)")

    # 4. Run walk-forward backtest (reads from cache)
    print("\nRunning walk-forward backtest...")
    t0 = time.time()
    result = run_walkforward(config, k, tickers)
    elapsed = time.time() - t0
    print(f"Backtest done in {elapsed:.1f}s")

    # 5. Print key metrics
    m = result.metrics
    print("\n=== KEY METRICS (net of friction) ===")
    print(f"  CAGR:              {m['cagr']:+.2%}")
    print(f"  Total Return:      {m['total_return']:+.2%}")
    print(f"  Sharpe:            {m['sharpe']:.2f}")
    print(f"  Sortino:           {m['sortino']:.2f}")
    print(f"  Max Drawdown:      {m['max_drawdown']:.2%}")
    print(f"  Calmar:            {m['calmar']:.2f}")
    print(f"  Trade Win Rate:    {m['trade_win_rate']:.2%}")
    print(f"  Profit Factor:     {m['profit_factor']:.2f}")
    print(f"  Total Friction:    {m['total_friction_paid']:.4f}")
    print(f"  Annual Turnover:   {m['annual_turnover']:.2f}")
    print(f"  VaR 95% (1d):      {m['var_95']:+.4f}")
    print(f"  Alpha (vs EW):     {m['alpha']:+.4f}")
    print(f"  Beta (vs EW):      {m['beta']:.3f}")
    print(f"  t-stat (vs EW):    {m['t_stat']:.2f} (p={m['p_value']:.3f})")

    # 6. Per-class attribution
    print("\n=== PER-CLASS ATTRIBUTION ===")
    attr = result.per_class_attribution
    if not attr.empty:
        print(attr.to_string(index=False))

    # 7. Benchmark comparison (CAGR)
    print("\n=== BENCHMARK COMPARISON (CAGR) ===")
    for name, curve in result.benchmarks.items():
        bench_cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / (len(curve) / 252)) - 1
        print(f"  {name:15s} {bench_cagr:+.2%}")

    # 8. Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.save(str(OUTPUT_DIR))
    print(f"\nResults saved to: {OUTPUT_DIR}")

    # 9. Re-run with inv_vol sizing for comparison
    print("\n\nRe-running with inverse-volatility sizing...")
    config_invvol = BacktestConfig(
        start_date="2022-01-01",
        end_date="2024-12-31",
        lookback=400,
        pred_len=20,
        n_samples=50,
        position_sizing="inv_vol",
    )
    result_invvol = run_walkforward(config_invvol, k, tickers)
    m2 = result_invvol.metrics
    print(f"\n=== INV-VOL SIZING ===")
    print(f"  Sharpe:  {m2['sharpe']:.2f} (equal: {m['sharpe']:.2f})")
    print(f"  Max DD:  {m2['max_drawdown']:.2%} (equal: {m['max_drawdown']:.2%})")
    invvol_dir = Path("./data/backtest_results/2022-2024_invvol")
    result_invvol.save(str(invvol_dir))
    print(f"Saved to: {invvol_dir}")

    print("\n=== PHASE 2 COMPLETE ===")


if __name__ == "__main__":
    main()
