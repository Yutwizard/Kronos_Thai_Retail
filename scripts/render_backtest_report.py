"""
Generate a comprehensive backtest HTML report with embedded charts.
Usage: venv/bin/python scripts/render_backtest_report.py <backtest_dir> [output_path]
"""
import io
import base64
import sys
from pathlib import Path
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

plt.ioff()

from kth.backtest.walkforward import BacktestResult


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{img}"


def _fmt(val, fmt_str):
    if val is None:
        return "N/A"
    return f"{val:{fmt_str}}"

def _metrics_table(m: dict) -> str:
    rows = [
        ("Total Return", _fmt(m.get("total_return"), "+.2%")),
        ("CAGR", _fmt(m.get("cagr"), "+.2%")),
        ("Annualised Vol", _fmt(m.get("annualised_vol"), ".2%")),
        ("Sharpe Ratio", _fmt(m.get("sharpe"), ".2f")),
        ("Sortino Ratio", _fmt(m.get("sortino"), ".2f")),
        ("Calmar Ratio", _fmt(m.get("calmar"), ".2f")),
        ("Omega Ratio", _fmt(m.get("omega"), ".2f")),
        ("Information Ratio", _fmt(m.get("information_ratio"), ".2f")),
        ("Max Drawdown", _fmt(m.get("max_drawdown"), ".2%")),
        ("Avg Drawdown", _fmt(m.get("avg_drawdown"), ".2%")),
        ("Ulcer Index", _fmt(m.get("ulcer_index"), ".4f")),
        ("Max DD Duration", _fmt(m.get("max_drawdown_duration"), ".0f") + "d"),
        ("Avg DD Duration", _fmt(m.get("avg_drawdown_duration"), ".0f") + "d"),
        ("VaR 95%", _fmt(m.get("var_95"), "+.4f")),
        ("CVaR 95%", _fmt(m.get("cvar_95"), "+.4f")),
        ("Trade Win Rate", _fmt(m.get("trade_win_rate"), ".2%")),
        ("Profit Factor", _fmt(m.get("profit_factor"), ".2f")),
        ("Payoff Ratio", _fmt(m.get("payoff_ratio"), ".2f")),
        ("Alpha (vs EW)", _fmt(m.get("alpha"), "+.4f")),
        ("Beta (vs EW)", _fmt(m.get("beta"), ".3f")),
        ("t-stat (vs EW)", _fmt(m.get("t_stat"), ".2f")),
        ("p-value", _fmt(m.get("p_value"), ".3f")),
        ("Total Friction Paid", _fmt(m.get("total_friction_paid"), ".4f")),
        ("Annual Turnover", _fmt(m.get("annual_turnover"), ".2f") + "x"),
    ]
    html = "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>"
    for name, val in rows:
        html += f"<tr><td>{name}</td><td><strong>{val}</strong></td></tr>"
    html += "</tbody></table>"
    return html


def _benchmark_table(result) -> str:
    html = "<table><thead><tr><th>Benchmark</th><th>CAGR</th><th>Final Value</th></tr></thead><tbody>"
    for name, curve in result.benchmarks.items():
        cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / (len(curve) / 252)) - 1
        html += f"<tr><td>{name}</td><td>{cagr:+.2%}</td><td>{curve.iloc[-1]:.4f}</td></tr>"
    html += "</tbody></table>"
    return html


def _attribution_table(result) -> str:
    attr = result.per_class_attribution
    if attr.empty:
        return "<p>No trades — no attribution data.</p>"
    html = "<table><thead><tr>"
    for col in attr.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in attr.iterrows():
        html += "<tr>"
        for col in attr.columns:
            val = row[col]
            if isinstance(val, float):
                html += f"<td>{val:+.4f}</td>" if "pnl" in col or "friction" in col else f"<td>{val:.2%}</td>" if "rate" in col else f"<td>{val}</td>"
            else:
                html += f"<td>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def _monthly_returns_table(equity_curve: pd.Series) -> str:
    daily_ret = equity_curve.pct_change().dropna()
    monthly = daily_ret.groupby(pd.Grouper(freq="ME")).apply(lambda x: (1 + x).prod() - 1).to_frame("return")
    monthly["year"] = monthly.index.year
    monthly["month"] = monthly.index.month
    pivot = monthly.pivot_table(index="year", columns="month", values="return")
    pivot = pivot * 100
    html = "<table><thead><tr><th>Year</th>"
    for m in range(1, 13):
        html += f"<th>{date(2000,m,1).strftime('%b')}</th>"
    html += "</tr></thead><tbody>"
    for year, row in pivot.iterrows():
        html += f"<tr><td>{int(year)}</td>"
        for m in range(1, 13):
            val = row.get(m, None)
            if pd.isna(val):
                html += "<td>—</td>"
            else:
                color = "#e8f5e9" if val > 0 else "#ffebee"
                html += f"<td style='background:{color}'>{val:+.1f}%</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def _trades_table(trades: pd.DataFrame, top_n: int = 20) -> str:
    if trades.empty:
        return "<p>No trades executed.</p>"
    cols = trades.columns.tolist()
    html = f"<table class='compact'><thead><tr>"
    for c in cols:
        html += f"<th>{c}</th>"
    html += "</tr></thead><tbody>"
    # Show top N by size
    sorted_trades = trades.sort_values("size_pct", ascending=False).head(top_n)
    for _, row in sorted_trades.iterrows():
        html += "<tr>"
        for c in cols:
            val = row[c]
            if isinstance(val, float):
                html += f"<td>{val:+.6f}</td>"
            else:
                html += f"<td>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def render_backtest_html(
    result: BacktestResult,
    path: str,
    title: str = "Kronos-TH Backtest Report",
) -> str:
    m = result.metrics
    config = result.config

    # Generate charts
    eq_fig = _plot_equity(result)
    eq_img = _fig_to_b64(eq_fig)

    dd_fig = _plot_drawdown(result)
    dd_img = _fig_to_b64(dd_fig)

    attr_fig = _plot_attribution(result)
    attr_img = _fig_to_b64(attr_fig) if attr_fig else None

    date_str = date.today().isoformat()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} — {date_str}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #fafafa; color: #333; }}
    h1 {{ color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 8px; }}
    h2 {{ color: #333; margin-top: 36px; }}
    p.meta {{ color: #666; font-size: 0.9em; }}
    .section {{ background: white; padding: 20px; margin: 16px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .charts {{ display: flex; flex-direction: column; gap: 20px; }}
    .charts img {{ width: 100%; border-radius: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
    th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
    th {{ background: #1565C0; color: white; font-weight: 600; }}
    tr:nth-child(even) {{ background: #f5f5f5; }}
    .compact td, .compact th {{ padding: 4px 8px; font-size: 0.85em; }}
    .config-grid {{ display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; }}
    .config-grid .label {{ font-weight: 600; color: #555; }}
    .disclaimer {{ background: #fff3e0; padding: 16px; border-left: 4px solid #FF9800; margin-top: 32px; border-radius: 4px; }}
    @media print {{ .section {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; Model: {config.forecast_cache_dir.split('/')[-2] if '/' in config.forecast_cache_dir else 'Kronos'}</p>

  <div class="section">
    <h2>Configuration</h2>
    <div class="config-grid">
      <span class="label">Period</span><span>{config.start_date} → {config.end_date}</span>
      <span class="label">Lookback</span><span>{config.lookback} days</span>
      <span class="label">Prediction Horizon</span><span>{config.pred_len} days</span>
      <span class="label">Samples</span><span>{config.n_samples}</span>
      <span class="label">Position Sizing</span><span>{config.position_sizing}</span>
      <span class="label">Max Positions</span><span>{config.max_positions}</span>
      <span class="label">Long Threshold</span><span>{config.long_threshold}</span>
      <span class="label">Min Holding Days</span><span>{config.min_holding_days}</span>
      <span class="label">Entry Buffer</span><span>{config.entry_buffer}</span>
    </div>
  </div>

  <div class="section">
    <h2>Key Metrics</h2>
    {_metrics_table(m)}
  </div>

  <div class="section">
    <h2>Equity Curve</h2>
    <p>Net (solid) vs gross (dashed) portfolio value, normalized to start at 1.0.</p>
    <img src="{eq_img}" alt="Equity Curve" style="width:100%">
  </div>

  <div class="section">
    <h2>Drawdown</h2>
    <img src="{dd_img}" alt="Drawdown" style="width:100%">
  </div>

  <div class="section">
    <h2>Benchmark Comparison</h2>
    {_benchmark_table(result)}
  </div>

  <div class="section">
    <h2>Per-Class Attribution</h2>
    { _attribution_table(result) }
    { '<img src=\\"'+attr_img+'\\" style=\\"width:100%\\">' if attr_img else '' }
  </div>

  <div class="section">
    <h2>Monthly Returns (%)</h2>
    {_monthly_returns_table(result.equity_curve)}
  </div>

  <div class="section">
    <h2>Trade Log (Top {_trades_table(result.trades, 20).count('tr')} by Size)</h2>
    <p>Showing largest trades by value.</p>
    {_trades_table(result.trades, 30)}
  </div>

  <div class="disclaimer">
    <h2>Disclaimer</h2>
    <p>This is research output from a forecasting model, not financial advice.
    Past performance does not guarantee future results. All investments carry risk.
    Backtest results are subject to survivorship bias, look-ahead bias, and regime shifts.
    The friction model approximates Thai retail broker costs but may not reflect actual execution.</p>
  </div>
</body>
</html>"""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report saved: {out_path}")
    return str(out_path)


def _plot_equity(result):
    fig, ax = plt.subplots(figsize=(12, 5))
    eq = result.equity_curve
    ax.plot(eq.index, eq.values, color="#2196F3", linewidth=1.5, label="Strategy (net)")
    gross = result.gross_equity_curve
    ax.plot(gross.index, gross.values, color="#2196F3", linewidth=1.0, linestyle="--", alpha=0.6, label="Strategy (gross)")
    colors = {"SET": "#FF9800", "SPY": "#4CAF50", "60_40": "#9C27B0", "equal_weight": "#607D8B"}
    for name, curve in result.benchmarks.items():
        c = colors.get(name, "gray")
        ax.plot(curve.index, curve.values, color=c, linewidth=1.0, alpha=0.7, label=name)
    # Final annotation
    final_val = eq.iloc[-1]
    ax.annotate(f"{final_val:.2f}x", xy=(eq.index[-1], final_val), fontsize=10, color="#2196F3",
                xytext=(5, 5), textcoords="offset points")
    ax.set_title("Portfolio Equity Curve vs Benchmarks")
    ax.set_ylabel("Portfolio Value (normalized)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    return fig


def _plot_drawdown(result):
    fig, ax = plt.subplots(figsize=(12, 4))
    equity = result.equity_curve
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    ax.fill_between(drawdown.index, drawdown.values, 0, where=(drawdown < 0), color="#F44336", alpha=0.3)
    ax.plot(drawdown.index, drawdown.values, color="#F44336", linewidth=0.8)
    min_dd = drawdown.min()
    ax.annotate(f"{min_dd:.1%}", xy=(drawdown.idxmin(), min_dd), fontsize=10, color="#F44336",
                xytext=(5, 5), textcoords="offset points")
    ax.set_title("Drawdown Series")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    return fig


def _plot_attribution(result):
    attr = result.per_class_attribution
    if attr.empty:
        return None
    fig, ax = plt.subplots(figsize=(10, max(3, len(attr) * 0.5)))
    classes = attr["asset_class"].tolist()
    pnl = attr["pnl"].tolist()
    friction = attr["friction_paid"].tolist()
    trade_count = attr["trade_count"].tolist()
    y_pos = range(len(classes))
    bars1 = ax.barh(y_pos, pnl, height=0.5, color="#4CAF50", alpha=0.7, label="Gross P&L")
    bars2 = ax.barh(y_pos, [-f for f in friction], height=0.5, color="#F44336", alpha=0.7, label="Friction")
    for i, (p, tc) in enumerate(zip(pnl, trade_count)):
        ax.text(p + 0.0001 if p >= 0 else p - 0.002, i, f"  {tc}t", va="center", fontsize=9, color="#555")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(classes)
    ax.set_xlabel("P&L Contribution")
    ax.set_title("Per-Class Attribution — Gross P&L vs Friction Paid")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.axvline(0, color="black", linewidth=0.5)
    return fig


if __name__ == "__main__":
    backtest_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/backtest_results/thai_equity_2022-2024"
    output = sys.argv[2] if len(sys.argv) > 2 else f"./reports/backtest_{Path(backtest_dir).stem}_{date.today().isoformat()}.html"

    result = BacktestResult.load(backtest_dir)
    m = result.metrics
    cagr_str = _fmt(m.get("cagr"), "+.2%")
    print(f"Loaded backtest: Sharpe={m.get('sharpe', 0):.2f}, CAGR={cagr_str}", flush=True)
    render_backtest_html(result, output,
                         title=f"Kronos-TH Backtest Report — {Path(backtest_dir).stem}")
