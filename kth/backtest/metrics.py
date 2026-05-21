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
        **dd_metrics,
        **var_cvar,
        **trade_m,
        "annual_turnover": annual_turnover,
        "total_friction_paid": total_friction,
        "t_stat": t_stat,
        "p_value": p_value,
    }
