"""Pure metric functions for backtest evaluation. All return dicts."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def compute_sharpe(
    daily_returns: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    excess = daily_returns - rf / periods_per_year
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))


def compute_sortino(
    daily_returns: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    excess = daily_returns - rf / periods_per_year
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(periods_per_year))


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    return float(drawdown.min())


def compute_drawdown_metrics(equity_curve: pd.Series) -> dict:
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak  # negative values

    max_dd = float(drawdown.min())

    # Average drawdown
    avg_dd = float(drawdown[drawdown < 0].mean()) if (drawdown < 0).any() else 0.0

    # Ulcer index: RMS of drawdowns
    ulcer = float(np.sqrt((drawdown ** 2).mean()))

    # Drawdown durations
    underwater = drawdown < 0
    if not underwater.any():
        return {"max_drawdown": 0.0, "avg_drawdown": 0.0, "ulcer_index": 0.0,
                "max_drawdown_duration": 0, "avg_drawdown_duration": 0}

    # Find underwater periods
    groups = (underwater != underwater.shift(1)).cumsum()
    durations = groups[underwater].value_counts()
    max_dur = int(durations.max()) if len(durations) > 0 else 0
    avg_dur = float(durations.mean()) if len(durations) > 0 else 0.0

    return {
        "max_drawdown": max_dd,
        "avg_drawdown": avg_dd,
        "ulcer_index": ulcer,
        "max_drawdown_duration": max_dur,
        "avg_drawdown_duration": avg_dur,
    }


def compute_var_cvar(daily_returns: pd.Series) -> dict:
    returns_arr = daily_returns.dropna().values
    var_95 = float(np.percentile(returns_arr, 5))
    var_99 = float(np.percentile(returns_arr, 1))
    cvar_95 = float(returns_arr[returns_arr <= var_95].mean()) if (returns_arr <= var_95).any() else 0.0
    return {"var_95": var_95, "var_99": var_99, "cvar_95": cvar_95}


def compute_trade_metrics(trades: pd.DataFrame) -> dict:
    """
    NOTE: 'trade_win_rate' is the proportion of trades with gross_return > 0.
    For a long-biased rolling strategy, this measures position-churn P&L,
    NOT forecast direction accuracy. A low trade_win_rate (<5%) is expected
    when the strategy holds positions continuously and only rebalances.

    For forecast direction accuracy, see eval_holdout.py results.
    """
    if trades.empty:
        return {"trade_win_rate": 0.0, "payoff_ratio": 0.0, "profit_factor": 0.0,
                "avg_holding_period": 0.0, "avg_trade_return_gross": 0.0,
                "avg_trade_return_net": 0.0, "max_win_streak": 0, "max_loss_streak": 0}

    wins = trades[trades["gross_return"] > 0]
    losses = trades[trades["gross_return"] < 0]

    hit_rate = len(wins) / len(trades) if len(trades) > 0 else 0.0
    avg_win = wins["gross_return"].mean() if len(wins) > 0 else 0.0
    avg_loss = abs(losses["gross_return"].mean()) if len(losses) > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    gross_profit = wins["gross_return"].sum() if len(wins) > 0 else 0.0
    gross_loss = abs(losses["gross_return"].sum()) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Win/loss streaks
    outcomes = (trades["gross_return"] > 0).astype(int)
    max_win = max_loss = current_win = current_loss = 0
    for o in outcomes:
        if o:
            current_win += 1; current_loss = 0
            max_win = max(max_win, current_win)
        else:
            current_loss += 1; current_win = 0
            max_loss = max(max_loss, current_loss)

    return {
        "trade_win_rate": hit_rate,
        "payoff_ratio": payoff,
        "profit_factor": profit_factor,
        "avg_holding_period": 0.0,  # filled by walkforward loop
        "avg_trade_return_gross": float(trades["gross_return"].mean()) if len(trades) > 0 else 0.0,
        "avg_trade_return_net": float((trades["gross_return"] - trades["friction_cost"]).mean()) if len(trades) > 0 else 0.0,
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
    }


def compute_psr(
    daily_returns: pd.Series,
    benchmark_sr: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Probabilistic Sharpe Ratio (Bailey & Lopez de Prado, 2012).
    P(SR > benchmark_sr) — probability that the true Sharpe exceeds the benchmark.

    PSR = Φ( (SR - SR*) × √(T-1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) )

    where SR is the observed annualized Sharpe, SR* is the benchmark (default 0),
    T is the number of observations, γ₃ is skewness, and γ₄ is kurtosis.
    """
    from scipy.stats import norm
    returns = daily_returns.dropna().values
    if len(returns) < 2:
        return 0.0
    sr = float(daily_returns.mean() / daily_returns.std() * np.sqrt(periods_per_year)) if daily_returns.std() > 0 else 0.0
    T = len(returns)
    skew = float(np.mean((returns - returns.mean()) ** 3) / returns.std() ** 3) if returns.std() > 0 else 0.0
    kurt = float(np.mean((returns - returns.mean()) ** 4) / returns.std() ** 4 - 3) if returns.std() > 0 else 0.0
    denominator = np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    if denominator == 0:
        return 0.5 if sr > benchmark_sr else 0.0
    z = (sr - benchmark_sr) * np.sqrt(T - 1) / denominator
    return float(norm.cdf(z))


def compute_sharpe_ci(
    daily_returns: pd.Series,
    periods_per_year: int = 252,
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
) -> dict:
    """
    Bootstrap 95% confidence interval for the annualized Sharpe ratio.
    Non-parametric — resamples daily returns with replacement.
    """
    returns = daily_returns.dropna().values
    if len(returns) < 2:
        return {"sharpe_ci_2_5": 0.0, "sharpe_ci_97_5": 0.0}

    bootstrapped = []
    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        sample = rng.choice(returns, size=len(returns), replace=True)
        sr = float(sample.mean() / sample.std() * np.sqrt(periods_per_year)) if sample.std() > 0 else 0.0
        bootstrapped.append(sr)

    return {
        "sharpe_ci_2_5": float(np.percentile(bootstrapped, alpha * 100 / 2)),
        "sharpe_ci_97_5": float(np.percentile(bootstrapped, 100 - alpha * 100 / 2)),
    }


def compute_metrics(
    equity_curve: pd.Series,
    daily_returns: pd.Series,
    trades: pd.DataFrame,
    benchmark: pd.Series,
    rf: float = 0.02,
    periods_per_year: int = 252,
) -> dict:
    """
    Compute full professional metric set from equity curve and trades.
    Returns flat dict. All ratio metrics computed gross and net where applicable.
    """
    n_days = len(daily_returns)
    years = n_days / periods_per_year

    # CAGR
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    cagr = float((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0

    # Volatility
    ann_vol = float(daily_returns.std() * np.sqrt(periods_per_year))

    # Sharpe / Sortino / Calmar
    sharpe = compute_sharpe(daily_returns, rf, periods_per_year)
    sortino = compute_sortino(daily_returns, rf, periods_per_year)
    dd_metrics = compute_drawdown_metrics(equity_curve)
    calmar = cagr / abs(dd_metrics["max_drawdown"]) if dd_metrics["max_drawdown"] != 0 else 0.0

    # Omega
    gains = daily_returns[daily_returns > 0].sum()
    losses = abs(daily_returns[daily_returns < 0].sum())
    omega = float(gains / losses) if losses > 0 else float("inf")

    # Information ratio
    excess_returns = daily_returns - benchmark.pct_change()
    tracking_error = excess_returns.std() * np.sqrt(periods_per_year)
    info_ratio = float(excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)) if tracking_error > 0 else 0.0

    # Alpha / Beta (OLS)
    bm_rets = benchmark.pct_change().dropna()
    aligned = pd.concat([daily_returns, bm_rets], axis=1).dropna()
    if len(aligned) > 2:
        aligned.columns = ["strategy", "benchmark"]
        if aligned["benchmark"].nunique() > 1:
            slope, intercept, _, _, _ = stats.linregress(aligned["benchmark"], aligned["strategy"])
            beta = slope
            alpha = intercept * periods_per_year
        else:
            beta = alpha = 0.0
    else:
        beta = alpha = 0.0

    # VaR / CVaR
    var_cvar = compute_var_cvar(daily_returns)

    # Trade metrics
    trade_m = compute_trade_metrics(trades)

    # Annual turnover
    total_traded = trades["size_pct"].sum() if not trades.empty else 0.0
    avg_portfolio_value = float(equity_curve.mean())
    annual_turnover = float(total_traded / avg_portfolio_value / years) if years > 0 else 0.0

    # Total friction
    total_friction = float(trades["friction_cost"].sum()) if not trades.empty else 0.0

    # t-stat vs benchmark
    excess_daily = daily_returns - benchmark.pct_change().fillna(0)
    if excess_daily.std() > 0:
        t_stat = float(excess_daily.mean() / (excess_daily.std() / np.sqrt(len(excess_daily))))
        p_value = float(2 * stats.t.sf(abs(t_stat), df=len(excess_daily) - 1))
    else:
        t_stat = p_value = 0.0

    # PSR — probability true Sharpe exceeds benchmarks
    psr_half = compute_psr(daily_returns, benchmark_sr=0.5, periods_per_year=periods_per_year)
    psr_one = compute_psr(daily_returns, benchmark_sr=1.0, periods_per_year=periods_per_year)

    # Bootstrap Sharpe CI
    sharpe_ci = compute_sharpe_ci(daily_returns, periods_per_year=periods_per_year)

    return {
        "cagr": cagr,
        "total_return": total_return,
        "annualised_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "omega": omega,
        "information_ratio": info_ratio,
        "alpha": alpha,
        "beta": beta,
        "psr_0_5": psr_half,
        "psr_1_0": psr_one,
        **sharpe_ci,
        **dd_metrics,
        **var_cvar,
        **trade_m,
        "annual_turnover": annual_turnover,
        "total_friction_paid": total_friction,
        "t_stat": t_stat,
        "p_value": p_value,
    }


def compute_drawdown_velocity(
    equity_curve: pd.Series,
    window: int = 5,
    threshold: float = -0.03,
) -> dict:
    """
    Flag a slow portfolio grind: return < threshold over the last `window` trading days.
    Catches regime deterioration that doesn't trigger single-day thresholds.
    Returns {'grind': bool, 'velocity': float, 'window': int}
    """
    if len(equity_curve) < window + 1:
        return {"grind": False, "velocity": 0.0, "window": window}
    recent = equity_curve.iloc[-(window + 1):]
    velocity = float(recent.iloc[-1] / recent.iloc[0] - 1)
    return {"grind": velocity < threshold, "velocity": round(velocity, 4), "window": window}


def compute_bootstrap_pvalue(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Bootstrap p-value: fraction of n_bootstrap shuffles of strategy_returns that
    beat benchmark_returns by >= the observed active return margin.
    Lower p = stronger evidence of genuine edge.
    Returns {'pvalue': float|None, 'n_bootstrap': int, 'n_obs': int, 'significant': bool}
    """
    if len(strategy_returns) < 20:
        return {"pvalue": None, "n_bootstrap": n_bootstrap,
                "n_obs": len(strategy_returns), "significant": False}

    rng = np.random.default_rng(seed)
    strat = strategy_returns.values
    if benchmark_returns is not None:
        bench = benchmark_returns.reindex(strategy_returns.index).fillna(0).values
    else:
        bench = np.zeros(len(strat))

    active = strat - bench
    observed_alpha = active.mean()
    # Bootstrap under H0: active mean = 0.
    # Center the active returns, resample with replacement, count how often
    # resampled mean >= observed mean. Permutation is wrong here because
    # permutation preserves the mean exactly.
    centered = active - observed_alpha
    beat_count = sum(
        rng.choice(centered, size=len(centered), replace=True).mean() >= observed_alpha
        for _ in range(n_bootstrap)
    )
    pvalue = beat_count / n_bootstrap
    return {
        "pvalue": round(pvalue, 3),
        "n_bootstrap": n_bootstrap,
        "n_obs": len(strategy_returns),
        "significant": pvalue < 0.05,
    }


def compute_information_ratio(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """IR = annualised active return / tracking error vs benchmark."""
    bench = benchmark_returns.reindex(strategy_returns.index).fillna(0)
    active = strategy_returns - bench
    if active.std() == 0:
        return 0.0
    return float(active.mean() / active.std() * np.sqrt(periods_per_year))


def compute_batting_average(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """% of calendar months where strategy mean daily return beat benchmark."""
    df = pd.DataFrame({
        "strat": strategy_returns,
        "bench": benchmark_returns.reindex(strategy_returns.index).fillna(0),
    })
    df.index = pd.to_datetime(df.index)
    monthly = df.resample("ME").mean()
    if len(monthly) == 0:
        return 0.0
    wins = (monthly["strat"] > monthly["bench"]).sum()
    return float(wins / len(monthly))


def compute_calibration(
    forecast_cache_dir,
    raw_data_dir,
    tickers: list,
    pred_len: int = 20,
    lookback_days: int = 60,
) -> dict:
    """
    P5/P95 coverage: fraction of actual prices that fell within the forecast band.
    Looks back `lookback_days` forecast dates, checks outcome `pred_len` days later.
    Returns {'coverage': float|None, 'n_samples': int, 'status': str}
    status: 'ok' | 'overconfident' (>95%) | 'insufficient_data' (<10 samples)
    """
    from pathlib import Path as _P
    from datetime import date as _d, timedelta
    from kth.data.loader import load_cached

    hits, total = 0, 0
    today = _d.today()

    for ticker in tickers:
        safe = ticker.replace("^", "_").replace("=", "_")
        try:
            price_df = load_cached(ticker, cache_dir=str(raw_data_dir))
            price_df.index = pd.to_datetime(price_df.index)
        except Exception:
            continue

        for days_ago in range(pred_len + 1, lookback_days + pred_len + 1):
            fc_path = _P(forecast_cache_dir) / str(today - timedelta(days=days_ago)) / f"{safe}.parquet"
            actual_date = (today - timedelta(days=days_ago - pred_len))
            if not fc_path.exists():
                continue
            try:
                fc = pd.read_parquet(fc_path)
                p5 = float(fc["p5"].iloc[-1])
                p95 = float(fc["p95"].iloc[-1])
                rows = price_df[price_df.index.date == actual_date]
                if rows.empty:
                    continue
                total += 1
                if p5 <= float(rows["close"].iloc[0]) <= p95:
                    hits += 1
            except Exception:
                continue

    if total < 10:
        return {"coverage": None, "n_samples": total, "status": "insufficient_data"}
    coverage = hits / total
    return {
        "coverage": round(coverage, 3),
        "n_samples": total,
        "status": "overconfident" if coverage > 0.95 else "ok",
    }
