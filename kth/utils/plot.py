"""Reusable matplotlib chart functions for notebooks 02–05."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


def plot_forecast_band(
    ticker: str,
    historical: pd.DataFrame,
    result,  # ForecastResult
    pred_len: int = 20,
    n_history_days: int = 60,
):
    """
    Actual close (last n_history_days) + shaded P5/P95 band + P50 line for pred_len.
    Returns matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    hist = historical.tail(n_history_days).copy()
    hist_dates = pd.to_datetime(hist["timestamps"])
    ax.plot(hist_dates, hist["close"], color="black", linewidth=1.5, label="Historical close")

    h = result.horizons[pred_len]
    fc_dates = pd.to_datetime(h.summary["timestamps"])

    last_hist_date = hist_dates.iloc[-1]
    x_fc = [last_hist_date] + list(fc_dates)
    last_close = float(hist["close"].iloc[-1])

    p50 = np.concatenate([[last_close], h.summary["p50"].values])
    ax.plot(x_fc, p50, color="#2196F3", linewidth=1.5, label=f"P50 ({pred_len}d)")

    p5 = np.concatenate([[last_close], h.summary["p5"].values])
    p95 = np.concatenate([[last_close], h.summary["p95"].values])
    ax.fill_between(x_fc, p5, p95, alpha=0.15, color="#2196F3", label="P5–P95 band")

    ax.set_title(f"{ticker} — {pred_len}-day Forecast Band")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)

    return fig


def plot_equity_curve(
    backtest_result,  # BacktestResult
    include_benchmarks: bool = True,
):
    """Net equity curve vs benchmarks. Gross curve as dashed line."""
    fig, ax = plt.subplots(figsize=(12, 5))

    equity = backtest_result.equity_curve
    ax.plot(equity.index, equity.values, color="#2196F3", linewidth=1.5, label="Strategy (net)")

    gross = backtest_result.gross_equity_curve
    ax.plot(gross.index, gross.values, color="#2196F3", linewidth=1.0, linestyle="--", alpha=0.6, label="Strategy (gross)")

    if include_benchmarks:
        colors = {"SET": "#FF9800", "SPY": "#4CAF50", "60_40": "#9C27B0", "equal_weight": "#607D8B"}
        for name, curve in backtest_result.benchmarks.items():
            color = colors.get(name, "gray")
            ax.plot(curve.index, curve.values, color=color, linewidth=1.0, alpha=0.7, label=name)

    ax.set_title("Portfolio Equity Curve")
    ax.set_ylabel("Portfolio Value (normalized)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    return fig


def plot_attribution(backtest_result):
    """Horizontal bar chart: per-class P&L contribution."""
    fig, ax = plt.subplots(figsize=(10, 6))

    attr = backtest_result.per_class_attribution
    if attr.empty:
        ax.text(0.5, 0.5, "No trades — no attribution", ha="center", va="center")
        return fig

    classes = attr["asset_class"].tolist()
    pnl = attr["pnl"].tolist()
    friction = attr["friction_paid"].tolist()

    y_pos = range(len(classes))
    ax.barh(y_pos, pnl, height=0.6, color="#4CAF50", alpha=0.7, label="Gross P&L")
    ax.barh(y_pos, [-f for f in friction], height=0.6, color="#F44336", alpha=0.7, label="Friction paid")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(classes)
    ax.set_xlabel("P&L Contribution")
    ax.set_title("Per-Class Attribution — Gross P&L vs Friction")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axvline(0, color="black", linewidth=0.5)

    return fig


def plot_drawdown(backtest_result):
    """Drawdown series with shaded underwater periods."""
    fig, ax = plt.subplots(figsize=(12, 5))

    equity = backtest_result.equity_curve
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak

    ax.fill_between(drawdown.index, drawdown.values, 0,
                    where=(drawdown < 0), color="#F44336", alpha=0.3, label="Drawdown")
    ax.plot(drawdown.index, drawdown.values, color="#F44336", linewidth=0.8)

    ax.set_title("Drawdown Series")
    ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.grid(True, alpha=0.3)

    return fig
