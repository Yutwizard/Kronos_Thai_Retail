"""
Run 5-year Thai equity backtest (2020-2024) with COVID/recovery/rate-hike regime decomposition.

Usage:
    venv/bin/python scripts/run_expanded_backtest.py              # full run
    venv/bin/python scripts/run_expanded_backtest.py --dry-run    # pre-flight only
    venv/bin/python scripts/run_expanded_backtest.py --resume     # resume from checkpoint

Checkpoint file: data/forecast_cache/run_expanded_backtest.json
"""
import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from kth.backtest.metrics import compute_metrics
from kth.backtest.walkforward import (
    BacktestConfig, precompute_forecasts, run_walkforward,
)
from kth.data.loader import load_cached
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH

logger = logging.getLogger("expanded_backtest")

TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]

PERIODS = [
    ("Stress (COVID crash)",   "2020-01-01", "2020-06-30"),
    ("Rebound (Recovery)",     "2020-07-01", "2021-12-31"),
    ("Current (Rate hikes)",   "2022-01-01", "2024-12-31"),
]

VERDICTS = [
    ("Thrive",    lambda a, c, s: a > 0 and c > 0),
    ("Survive",   lambda a, c, s: a > 0 and s > 0.5),
    ("Mitigate",  lambda a, c, s: a > 0 and c <= 0),
    ("Struggle",  lambda a, c, s: a <= 0),
]

CHECKPOINT_PATH = Path("data/forecast_cache/run_expanded_backtest.json")
OUTPUT_DIR = Path("data/backtest_results/thai_equity_2020-2024")

# NOTE: n_samples=10 (not 50 from 2022-2024 run) due to 5x longer period.
# 50 samples would take ~52 hrs — not feasible overnight.
# Results across periods are NOT directly comparable due to sample count difference.
config = BacktestConfig(
    start_date="2020-01-01",
    end_date="2024-12-31",
    lookback=400, pred_len=20, n_samples=10,
    position_sizing="equal",
    max_positions=5,
    long_threshold=0.01,
    entry_buffer=0.005,
    min_holding_days=5,
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _forecast_slug(model_name: str) -> str:
    """Match walkforward.py's _model_slug convention."""
    return model_name.replace("/", "_").replace("@", "-").replace("\\", "_")


def _period_trades(trades_df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Filter trades to a date window. Handles empty/None trades_df."""
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    ts, te = pd.Timestamp(start), pd.Timestamp(end)
    return trades_df[(trades_df["date"] >= ts) & (trades_df["date"] <= te)].copy()


def _cagr_alpha(strat_eq: pd.Series, bm_eq: pd.Series) -> float:
    """CAGR alpha = CAGR_strategy - CAGR_benchmark.
    Both series should share the same date index (same trading days)."""
    years_strat = len(strat_eq) / 252
    years_bm = len(bm_eq) / 252
    if years_strat <= 0 or years_bm <= 0:
        return 0.0
    strat_cagr = (strat_eq.iloc[-1] / strat_eq.iloc[0]) ** (1 / years_strat) - 1
    bm_cagr = (bm_eq.iloc[-1] / bm_eq.iloc[0]) ** (1 / years_bm) - 1
    return strat_cagr - bm_cagr


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------

def validate_data(tickers: list[str], lookback: int, start_date: str) -> list[str]:
    """Check that all tickers have enough cached OHLCV data.
    Returns viable tickers. On dry-run, prints status per ticker."""
    viable = []
    missing = []
    start_ts = pd.Timestamp(start_date)
    min_date = start_ts - pd.Timedelta(days=int(lookback * 1.5))

    for t in tickers:
        try:
            df = load_cached(t)
            if len(df) < lookback:
                missing.append((t, f"only {len(df)} rows, need {lookback}"))
                continue
            if df["timestamps"].min() > min_date:
                missing.append((t, f"earliest data {df['timestamps'].min().date()}, need {min_date.date()}"))
                continue
            viable.append(t)
        except FileNotFoundError:
            missing.append((t, "not cached"))

    if missing:
        logger.warning("Data issues for %d tickers:", len(missing))
        for t, reason in missing:
            logger.warning("  %s: %s", t, reason)
    logger.info("Viable tickers: %d / %d", len(viable), len(tickers))
    return viable


def run_dry_run():
    """Check data availability, cache state, config — no GPU needed."""
    logger.info("=== DRY RUN ===")
    logger.info("Target: %d Thai equity tickers", len(TICKERS))

    viable = validate_data(TICKERS, config.lookback, config.start_date)

    # Check what's already cached
    model_name = "NeoQuasar/Kronos-small"
    cache_root = Path(config.forecast_cache_dir) / _forecast_slug(model_name)
    cached_dates = sorted(d.name for d in cache_root.iterdir() if d.is_dir()) if cache_root.exists() else []
    logger.info("Cached dates: %d (2020-2024 range)", len(cached_dates))
    cached_2020 = [d for d in cached_dates if d.startswith("2020")]
    cached_2021 = [d for d in cached_dates if d.startswith("2021")]
    logger.info("  2020 dates: %d, 2021 dates: %d", len(cached_2020), len(cached_2021))

    n_days = len(pd.date_range(start=config.start_date, end=config.end_date, freq="B"))
    est_hrs = n_days * 30 / 3600  # ~30 sec per day (batches all tickers together)
    logger.info("Estimated precompute: %.1f hrs (%d days x %d tickers)", est_hrs, n_days, len(viable))
    logger.info("Estimated walk-forward: ~90 sec")
    logger.info("Dry run — no execution. Run without --dry-run to proceed.")


# ---------------------------------------------------------------------------
# Checkpoint and cache management
# ---------------------------------------------------------------------------

def save_checkpoint(state: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2, default=str))


def load_checkpoint() -> dict | None:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return None


def clean_old_cache(model_name: str):
    """Delete 2020 and 2021 date directories from forecast cache only.
    Preserves 2022-2024 cached data for all markets.
    model_name: e.g. 'NeoQuasar/Kronos-small'"""
    slug = _forecast_slug(model_name)
    cache_root = Path(config.forecast_cache_dir) / slug
    if not cache_root.exists():
        logger.info("No cache directory found at %s", cache_root)
        return
    deleted = 0
    for d in cache_root.iterdir():
        if d.is_dir():
            try:
                pd.Timestamp(d.name)
            except (ValueError, TypeError):
                continue
            if d.name.startswith(("2020-", "2021-")):
                logger.info("Deleting old cache: %s", d.name)
                shutil.rmtree(d)
                deleted += 1
    logger.info("Deleted %d cache directories (2020-2021)", deleted)


# ---------------------------------------------------------------------------
# Period decomposition
# ---------------------------------------------------------------------------

def decompose_periods(
    equity_curve: pd.Series,
    trades_df: pd.DataFrame,
    ew_benchmark: pd.Series,
    set_benchmark: pd.Series | None,
) -> list[dict]:
    """Slice equity curve by period, compute metrics + verdict for each.
    Uses CAGR alpha consistently (not OLS alpha from compute_metrics).
    Filters trades per period so trade-level metrics are correct."""
    results = []
    for label, start, end in PERIODS:
        eq = equity_curve.loc[start:end]
        ew = ew_benchmark.loc[start:end]
        set_s = set_benchmark.loc[start:end] if set_benchmark is not None else None

        if len(eq) < 10:
            results.append({"period": label, "status": "Insufficient data (<10 days)"})
            continue

        daily = eq.pct_change().dropna()
        period_trades = _period_trades(trades_df, start, end)
        metrics = compute_metrics(eq, daily, period_trades, ew)

        set_cagr = None
        if set_s is not None and len(set_s) > 5:
            set_cagr = (set_s.iloc[-1] / set_s.iloc[0]) ** (252 / len(set_s)) - 1

        cagr = metrics["cagr"]
        sharpe = metrics["sharpe"]
        alpha = _cagr_alpha(eq, ew)  # CAGR alpha, consistent across all periods
        p_value = metrics["p_value"]

        verdict = "Inconclusive"
        for v_name, cond in VERDICTS:
            if cond(alpha, cagr, sharpe):
                verdict = v_name
                break

        results.append({
            "period": label, "cagr": cagr, "sharpe": sharpe,
            "max_dd": metrics["max_drawdown"], "alpha": alpha,
            "p_value": p_value, "set_cagr": set_cagr,
            "n_trades": len(period_trades),  # individual transactions (buy + sell rows)
            "verdict": verdict,
        })
    return results


def print_results(
    full_metrics: dict,
    period_results: list[dict],
):
    """Print formatted output table."""
    print("\n" + "=" * 70)
    print("THAI EQUITY — WALK-FORWARD BACKTEST (2020-2024)")
    print("=" * 70)
    print(f"Tickers: {len(TICKERS)} | Calendar: 5-day (business) | Equal weight | n_samples={config.n_samples}")
    print()
    print(f"Full Period (2020-2024):")
    print(f"  CAGR: {full_metrics['cagr']:+9.2%}  Sharpe: {full_metrics['sharpe']:6.2f}  "
          f"Max DD: {full_metrics['max_drawdown']:+8.2%}  "
          f"Alpha vs EW: {full_metrics.get('alpha_cagr', full_metrics.get('alpha', 0)):+8.2%}  "
          f"p={full_metrics['p_value']:.3f}")
    print()
    print(f"{'Period':<25} {'CAGR':>9} {'Sharpe':>7} {'Max DD':>9} {'Alpha EW':>9} "
          f"{'SET CAGR':>9} {'Trades':>7} {'p-value':>8} {'Verdict':<12}")
    print("-" * 98)
    for p in period_results:
        if "status" in p:
            print(f"{p['period']:<25} {'N/A':>9} {'N/A':>7} {'N/A':>9} "
                  f"{'N/A':>9} {'N/A':>9} {'N/A':>7} {'N/A':>8} {p['status']:<12}")
        else:
            sc = f"{p['set_cagr']:+8.2%}" if p['set_cagr'] is not None else "N/A"
            print(f"{p['period']:<25} {p['cagr']:+8.2%} {p['sharpe']:6.2f} "
                  f"{p['max_dd']:+8.2%} {p['alpha']:+8.2%} {sc:>9} "
                  f"{p['n_trades']:>7} {p['p_value']:7.3f} {p['verdict']:<12}")

    # Caveats
    sp = next((p for p in period_results if "stress" in p["period"].lower()), None)
    if sp and "n_trades" in sp and sp["n_trades"] < 50:
        print(f"\n  * Stress period: ~{sp['n_trades']} trades (~125 days) — limited sample size. "
              f"p={sp['p_value']:.3f} indicates inconclusive.")
    print("\n  → Universe is point-in-time (2025). Delisted/merged tickers from 2020-2022")
    print("    are excluded. COVID stress period results may be overstated.")
    print("  → Alpha per period is the relevant metric for regime analysis.")
    print("  → Lower 5-year CAGR vs 2022-2024 alone is expected (includes COVID crash).")
    print("  → Multi-period testing: 3 periods × α=0.05 → ~14% probability of ≥1 false positive.")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Expanded backtest 2020-2024")
    parser.add_argument("--dry-run", action="store_true", help="Pre-flight check only")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("data/logs/expanded_backtest.log"),
            logging.StreamHandler(),
        ],
    )
    logger.info("Thai Equity Expanded Backtest (2020-2024)")
    logger.info("Tickers: %d", len(TICKERS))

    if args.dry_run:
        run_dry_run()
        return

    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            logger.info("Resuming from checkpoint (phase=%s)", checkpoint.get("phase"))
        else:
            logger.warning("No checkpoint found — starting fresh")
            checkpoint = None
    else:
        checkpoint = None

    # Phase 1: Data validation
    if not checkpoint or checkpoint.get("phase") == "validate":
        logger.info("Phase: validate")
        viable = validate_data(TICKERS, config.lookback, config.start_date)
        if len(viable) < 40:
            logger.error("Only %d viable tickers — aborting", len(viable))
            sys.exit(1)
        save_checkpoint({"phase": "clean_cache", "viable": viable})
    else:
        viable = checkpoint.get("viable", TICKERS)
        logger.info("Skipping validation — %d viable from checkpoint", len(viable))

    # Phase 2: Clean 2020-2021 cache (one-time, skipped on resume past this phase)
    if not checkpoint or checkpoint.get("phase") == "clean_cache":
        logger.info("Phase: clean cache")
        th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
        clean_old_cache(th.model_name)
        save_checkpoint({"phase": "precompute", "viable": viable})
    else:
        th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")

    # Phase 3: Precompute forecasts (idempotent — skips already-cached dates)
    if not checkpoint or checkpoint.get("phase") == "precompute":
        logger.info("Phase: precompute forecasts")
        logger.info("Period: %s → %s", config.start_date, config.end_date)
        t0 = time.time()
        try:
            precompute_forecasts(
                th, viable,
                start_date=config.start_date, end_date=config.end_date,
                pred_len=config.pred_len, n_samples=config.n_samples,
                lookback=config.lookback,
                cache_dir=config.forecast_cache_dir,
            )
        except Exception:
            logger.exception("Precompute failed at %.1f hrs", (time.time() - t0) / 3600)
            save_checkpoint({"phase": "precompute", "viable": viable})
            raise
        elapsed = time.time() - t0
        logger.info("Precompute done: %.1f hrs", elapsed / 3600)
        save_checkpoint({"phase": "walkforward", "viable": viable})

    # Phase 5: Walk-forward
    logger.info("Phase: walk-forward")
    t0 = time.time()
    try:
        result = run_walkforward(config, th, viable)
    except Exception:
        logger.exception("Walk-forward failed")
        raise
    logger.info("Walk-forward done: %.1f sec", time.time() - t0)

    # Phase 6: Full-period metrics
    logger.info("Phase: metrics")
    full_metrics = result.metrics
    ew_benchmark = result.benchmarks.get("equal_weight", pd.Series(1.0, index=result.equity_curve.index))
    set_benchmark = result.benchmarks.get("SET")
    full_metrics["alpha_cagr"] = _cagr_alpha(result.equity_curve, ew_benchmark)

    # Phase 7: Period decomposition
    logger.info("Phase: period decomposition")
    period_results = decompose_periods(
        result.equity_curve, result.trades,
        ew_benchmark, set_benchmark,
    )

    # Phase 8: Output
    print_results(full_metrics, period_results)

    # Phase 9: Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.save(str(OUTPUT_DIR))
    logger.info("Results saved to %s", OUTPUT_DIR)
    logger.info("Done.")

    # Clean up checkpoint
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


if __name__ == "__main__":
    main()
