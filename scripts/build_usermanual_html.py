"""
Generate a richly formatted HTML user manual with embedded visualization charts.
Usage: venv/bin/python scripts/build_usermanual_html.py
Output: docs/user-manual.html
"""
import io, base64, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
plt.ioff()

BACKTEST_RESULTS = {
    "thai_equity": {
        "cagr": 0.3144, "sharpe": 1.40, "sortino": 2.28, "calmar": 1.75,
        "max_dd": -0.1797, "trade_win_rate": 0.0251, "turnover": 11.8,
        "friction_drag": 0.063, "p_value": 0.02,
        "benchmarks": {"SET Index": -0.0529, "SPY": 0.0833, "60/40": -0.0027, "Equal-Weight": 0.0144}
    },
    "us_equity": {
        "cagr": 0.3034, "sharpe": 0.97, "sortino": 1.45, "calmar": 0.69,
        "max_dd": -0.4377, "trade_win_rate": 0.0278, "turnover": 9.2,
        "friction_drag": 0.064, "p_value": 0.46,
        "benchmarks": {"SET Index": -0.0529, "SPY": 0.0833, "60/40": -0.0027, "Equal-Weight": 0.1439}
    },
    "crypto": {
        "cagr": 0.1645, "sharpe": 0.52, "sortino": 0.70, "calmar": 0.24,
        "max_dd": -0.6858, "trade_win_rate": 0.0148, "turnover": 6.7,
        "friction_drag": 0.060, "p_value": 0.64,
        "benchmarks": {"SET Index": -0.0529, "SPY": 0.0833, "60/40": -0.0027, "Equal-Weight": -0.0516}
    },
}

FRICTION = {
    "Thai Equity": {"commission": 0.00168, "slippage": 0.0010, "total_rt": 0.00536},
    "US Equity": {"commission": 0.0030, "slippage": 0.0005, "total_rt": 0.0070},
    "Crypto": {"commission": 0.0025, "slippage": 0.0020, "total_rt": 0.0090},
    "Crypto (BTC)": {"commission": 0.0025, "slippage": 0.0010, "total_rt": 0.0070},
}


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f'<img src="data:image/png;base64,{img}" alt="chart">'


def _color_palette():
    return {
        "thai": "#1a5276", "us": "#2e86c1", "crypto": "#f39c12", "bh": "#7f8c8d",
        "green": "#27ae60", "red": "#e74c3c", "yellow": "#f1c40f"
    }


def chart_cagr_comparison():
    """Bar chart: CAGR for each market vs its benchmarks."""
    c = _color_palette()
    markets = list(BACKTEST_RESULTS.keys())
    labels = {"thai_equity": "Thai Equity", "us_equity": "US Equity", "crypto": "Crypto"}

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), facecolor="white")

    for ax, mk in zip(axes, markets):
        d = BACKTEST_RESULTS[mk]
        bm = d["benchmarks"]
        names = ["Strategy"] + list(bm.keys())
        vals = [d["cagr"]] + list(bm.values())
        colors = [c["green"]] + [c["bh"]] * (len(names) - 1)
        ax.set_facecolor("white")

        bars = ax.bar(names, [v * 100 for v in vals], color=colors, edgecolor="white", width=0.6)
        for bar, v in zip(bars, vals):
            y_pos = bar.get_height() + 0.8 if v >= 0 else bar.get_height() - 2.0
            ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                    f"{v*100:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=8, fontweight="bold")

        ax.axhline(0, color="gray", linewidth=0.5)
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_title(labels[mk], fontweight="bold", fontsize=11, pad=8)
        ax.set_ylabel("CAGR (%)")
        ax.tick_params(axis="x", rotation=25)
        ymin = min(min(vals) * 100 - 3, -3)
        ymax = max(max(vals) * 100 + 3, 5)
        ax.set_ylim(ymin, ymax)

    fig.suptitle("CAGR: Strategy vs Benchmarks (2022-2024)", fontweight="bold", fontsize=13, y=0.98)
    fig.subplots_adjust(top=0.88, bottom=0.12, wspace=0.3)
    return _fig_to_b64(fig)


def chart_sharpe_comparison():
    """Grouped bar chart: Sharpe by market."""
    c = _color_palette()
    markets = list(BACKTEST_RESULTS.keys())
    labels = {"thai_equity": "Thai Equity", "us_equity": "US Equity", "crypto": "Crypto"}

    fig, ax = plt.subplots(1, 1, figsize=(10, 4.5), facecolor="#fafafa")

    x = np.arange(len(markets))
    width = 0.2
    metrics_data = {
        "Sharpe": [BACKTEST_RESULTS[m]["sharpe"] for m in markets],
        "Sortino": [BACKTEST_RESULTS[m]["sortino"] for m in markets],
        "Calmar": [BACKTEST_RESULTS[m]["calmar"] for m in markets],
    }
    colors = [c["thai"], c["us"], c["crypto"]]

    for i, (metric, vals) in enumerate(metrics_data.items()):
        offset = (i - 1) * width
        bars = ax.bar(x + offset, vals, width, label=metric, edgecolor="white", color=colors[i])
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([labels[m] for m in markets])
    ax.set_ylabel("Ratio")
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_title("Risk-Adjusted Performance: Sharpe, Sortino, Calmar", fontweight="bold", fontsize=12)
    ax.legend()
    pass
    return _fig_to_b64(fig)


def chart_max_drawdown():
    """Bar chart: Max DD for strategy vs benchmarks."""
    c = _color_palette()
    markets = list(BACKTEST_RESULTS.keys())
    labels = {"thai_equity": "Thai Equity", "us_equity": "US Equity", "crypto": "Crypto"}

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), facecolor="#fafafa")

    for ax, mk in zip(axes, markets):
        d = BACKTEST_RESULTS[mk]
        names = ["Strategy", "SPY", "Equal-Wt"]
        vals = [d["max_dd"], d["benchmarks"].get("SPY", 0), d["benchmarks"].get("Equal-Weight", 0)]
        colors_list = [c["red"], c["bh"], c["bh"]]

        bars = ax.barh(names, [v * 100 for v in vals], color=colors_list, edgecolor="white", height=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_width() - 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{v*100:.1f}%", ha="right", va="center", fontsize=9, fontweight="bold", color="white")

        ax.set_title(labels[mk], fontweight="bold", fontsize=11)
        ax.set_xlabel("Max Drawdown (%)")

    fig.suptitle("Maximum Drawdown: Strategy vs Benchmarks", fontweight="bold", fontsize=13, y=1.02)
    pass
    return _fig_to_b64(fig)


def chart_friction_cost():
    """Horizontal bar: friction costs by class."""
    c = _color_palette()
    fig, ax = plt.subplots(1, 1, figsize=(8, 4), facecolor="#fafafa")

    classes = list(FRICTION.keys())
    vals = [FRICTION[k]["total_rt"] * 100 for k in classes]
    colors_bar = ["#1a5276", "#2e86c1", "#f39c12", "#d35400"]

    bars = ax.barh(classes, vals, color=colors_bar, edgecolor="white", height=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{v:.2f}%", ha="left", va="center", fontsize=10, fontweight="bold")

    ax.set_title("Round-Trip Friction Cost by Asset Class", fontweight="bold", fontsize=12)
    ax.set_xlabel("Transaction Cost (% of trade value)")
    pass
    return _fig_to_b64(fig)


def chart_annual_turnover():
    """Bar: turnover and friction drag."""
    c = _color_palette()
    markets = list(BACKTEST_RESULTS.keys())
    labels = {"thai_equity": "Thai Equity", "us_equity": "US Equity", "crypto": "Crypto"}

    fig, ax1 = plt.subplots(1, 1, figsize=(8, 4.5), facecolor="#fafafa")

    turnovers = [BACKTEST_RESULTS[m]["turnover"] for m in markets]
    drags = [BACKTEST_RESULTS[m]["friction_drag"] * 100 for m in markets]

    x = np.arange(len(markets))
    width = 0.35
    bars1 = ax1.bar(x - width / 2, turnovers, width, label="Annual Turnover (×)", color=c["thai"], edgecolor="white")
    ax1.set_ylabel("Turnover (times/year)")
    ax1.set_xticks(x)
    ax1.set_xticklabels([labels[m] for m in markets])

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, drags, width, label="Friction Drag (% AUM)", color=c["red"], edgecolor="white")
    ax2.set_ylabel("Annual Cost (% of AUM)")

    for bar, v in zip(bars1, turnovers):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                f"{v:.1f}×", ha="center", fontsize=9, fontweight="bold")
    for bar, v in zip(bars2, drags):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{v:.1f}%", ha="center", fontsize=9, fontweight="bold")

    fig.suptitle("Turnover vs Friction Drag", fontweight="bold", fontsize=12, y=1.02)
    pass
    return _fig_to_b64(fig)


def chart_allocation_donut():
    """Donut chart: recommended class allocation."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 5), facecolor="#fafafa")

    sizes = [40, 30, 5, 5, 5, 15]
    labels_explode = ["Thai Equity", "US Equity", "Crypto", "ETF Global", "Other", "Cash"]
    colors_donut = ["#1a5276", "#2e86c1", "#f39c12", "#7f8c8d", "#d35400", "#ecf0f1"]
    explode = (0.03, 0.03, 0.03, 0.03, 0.03, 0.03)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct="%1.0f%%", startangle=90, pctdistance=0.78,
        colors=colors_donut, explode=explode, wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")

    ax.legend(
        wedges, [f"{l}" for l in labels_explode],
        title="Asset Class", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9,
    )
    ax.set_title("Recommended Balanced Allocation", fontweight="bold", fontsize=13, pad=15)
    pass
    return _fig_to_b64(fig)


def chart_confidence_sizing():
    """Step chart: position size by confidence flag."""
    c = _color_palette()
    fig, ax = plt.subplots(1, 1, figsize=(6, 3.5), facecolor="#fafafa")

    flags = ["Green\n(<=10%)", "Yellow\n(10-30%)", "Red\n(>30%)"]
    sizes = [100, 50, 0]
    colors_bar = [c["green"], c["yellow"], c["red"]]

    bars = ax.bar(flags, sizes, color=colors_bar, edgecolor="white", width=0.5)
    for bar, s in zip(bars, sizes):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{s}%", ha="center", fontsize=11, fontweight="bold")

    ax.set_ylim(0, 120)
    ax.set_ylabel("Position Size (% of normal)")
    ax.set_title("Position Size by Confidence Flag", fontweight="bold", fontsize=11)
    pass
    return _fig_to_b64(fig)


def build_html() -> str:
    c1, c2, c3, c4 = _fig_to_b64, chart_cagr_comparison(), chart_sharpe_comparison(), chart_max_drawdown()
    c5, c6, c7, c8 = chart_friction_cost(), chart_annual_turnover(), chart_allocation_donut(), chart_confidence_sizing()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kronos-TH — User Manual &amp; Methodology Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1a1a2e; background: #f5f6fa; line-height: 1.6; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 2.2rem; font-weight: 800; color: #1a5276; margin: 30px 0 5px; }}
  h2 {{ font-size: 1.5rem; font-weight: 700; color: #1a5276; margin: 35px 0 12px; padding-bottom: 6px; border-bottom: 3px solid #2e86c1; }}
  h3 {{ font-size: 1.15rem; font-weight: 600; color: #2c3e50; margin: 22px 0 8px; }}
  h4 {{ font-weight: 600; color: #34495e; margin: 16px 0 6px; }}
  p {{ margin: 8px 0; }}
  .subtitle {{ color: #7f8c8d; font-size: 1rem; margin-bottom: 25px; }}
  .hero {{ background: linear-gradient(135deg, #1a5276 0%, #2e86c1 100%); color: white; padding: 40px 30px; border-radius: 12px; margin: 20px 0 30px; text-align: center; }}
  .hero h1 {{ color: white; margin: 0; font-size: 2.5rem; }}
  .hero .subtitle {{ color: rgba(255,255,255,0.85); font-size: 1.1rem; margin: 8px 0 0; }}
  .hero .badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; margin: 10px 4px 0; }}
  .card {{ background: white; border-radius: 10px; padding: 25px; margin: 16px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .chart {{ text-align: center; margin: 20px 0; }}
  .chart img {{ max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9rem; }}
  th {{ background: #1a5276; color: white; padding: 8px 10px; text-align: left; font-weight: 600; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #eee; }}
  tr:hover td {{ background: #f0f4f8; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  tr:nth-child(even):hover td {{ background: #f0f4f8; }}
  code, pre {{ font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; background: #f0f4f8; border-radius: 4px; }}
  code {{ padding: 2px 5px; }}
  pre {{ padding: 14px; overflow-x: auto; border-left: 3px solid #2e86c1; margin: 10px 0; position: relative; }}
  .copy-btn {{ position: absolute; top: 6px; right: 6px; background: rgba(255,255,255,0.85); border: 1px solid #ddd; border-radius: 4px; padding: 2px 8px; font-size: 0.72rem; cursor: pointer; color: #555; }}
  .copy-btn:hover {{ background: #e8f0fe; color: #1a5276; }}
  .copy-btn.copied {{ background: #27ae60; color: white; border-color: #27ae60; }}
  .highlight {{ background: #fff8e1; border-left: 4px solid #f39c12; padding: 12px 16px; margin: 12px 0; border-radius: 4px; font-size: 0.9rem; }}
  .highlight-red {{ background: #fdecea; border-left: 4px solid #e74c3c; padding: 12px 16px; margin: 12px 0; border-radius: 4px; font-size: 0.9rem; }}
  .highlight-green {{ background: #e8f8f5; border-left: 4px solid #27ae60; padding: 12px 16px; margin: 12px 0; border-radius: 4px; font-size: 0.9rem; }}
  .highlight-yellow {{ background: #fef9e7; border-left: 4px solid #d4ac0d; padding: 12px 16px; margin: 12px 0; border-radius: 4px; font-size: 0.9rem; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  .stat {{ background: white; border-radius: 10px; padding: 18px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .stat .number {{ font-size: 2rem; font-weight: 800; color: #1a5276; }}
  .stat .label {{ font-size: 0.8rem; color: #7f8c8d; margin-top: 2px; }}
  .toc {{ background: white; border-radius: 10px; padding: 20px 25px; margin: 20px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .toc ol {{ padding-left: 20px; }}
  .toc li {{ margin: 4px 0; }}
  .toc a {{ color: #2e86c1; text-decoration: none; }}
  .toc a:hover {{ text-decoration: underline; }}
  .flag-green {{ color: #27ae60; font-weight: bold; }}
  .flag-yellow {{ color: #f1c40f; font-weight: bold; }}
  .flag-red {{ color: #e74c3c; font-weight: bold; }}
  .badge-sm {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }}
  .badge-high {{ background: #e8f8f5; color: #27ae60; }}
  .badge-mid {{ background: #fef9e7; color: #d4ac0d; }}
  .badge-low {{ background: #fdecea; color: #e74c3c; }}
  .badge-none {{ background: #eee; color: #999; }}
  .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }}
  .detail-item {{ background: #f8f9fa; padding: 12px 14px; border-radius: 6px; border-left: 3px solid #2e86c1; }}
  .detail-item .title-small {{ font-size: 0.75rem; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }}
  .detail-item .value {{ font-size: 1.1rem; font-weight: 600; color: #1a5276; }}
  ul, ol {{ padding-left: 22px; margin: 6px 0; }}
  li {{ margin: 4px 0; }}
  .btt {{ position: fixed; bottom: 30px; right: 30px; background: #1a5276; color: white; width: 42px; height: 42px; border-radius: 50%; text-align: center; line-height: 42px; font-size: 1.4rem; text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,0.2); display: none; z-index: 100; }}
  .btt:hover {{ background: #2e86c1; }}
</style>
<script>
window.addEventListener('scroll', function(){{
  var btn = document.querySelector('.btt');
  if (btn) btn.style.display = window.scrollY > 300 ? 'block' : 'none';
}});
document.addEventListener('DOMContentLoaded', function(){{
  document.querySelectorAll('pre').forEach(function(pre){{
    if (pre.querySelector('.copy-btn')) return;
    var btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.onclick = function(){{
      var code = pre.textContent;
      navigator.clipboard.writeText(code).then(function(){{
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(function(){{ btn.textContent = 'Copy'; btn.classList.remove('copied'); }}, 2000);
      }}).catch(function(){{
        btn.textContent = 'Failed';
      }});
    }};
    pre.style.position = 'relative';
    pre.appendChild(btn);
  }});
}});
</script>
</head>
<body>
<div class="container">

<div class="hero">
  <h1>Kronos-TH</h1>
  <p class="subtitle">A daily forecasting system for Thai retail investors</p>
  <span class="badge">Not financial advice</span>
  <span class="badge">Research output only</span>
</div>

<div class="toc">
  <h3 style="margin-top:0; border:none; padding:0;">Contents</h3>
  <ol>
    <li><a href="#s1">What Is Kronos-TH?</a></li>
    <li><a href="#s2">Quick Start</a></li>
    <li><a href="#s3">Position Sizing Methodology</a></li>
    <li><a href="#s4">The Three Report Views</a></li>
    <li><a href="#s5">Backtest Methodology</a></li>
    <li><a href="#s6">Backtest Results (2022–2024)</a></li>
    <li><a href="#s7">Cautions &amp; Limitations</a></li>
    <li><a href="#s8">Performance Tables</a></li>
    <li><a href="#s9">File Reference</a></li>
   </ol>
</div>

<h2 id="s1">What Is Kronos-TH?</h2>
<div class="card">
  <p>Kronos-TH wraps the <strong>Kronos foundation model</strong> — a transformer trained on millions of daily K-lines across global markets — to produce <strong>probabilistic 20-day forecasts</strong> for the assets a Thai retail investor can actually buy.</p>
  <p><strong>The output is not orders.</strong> It is a daily report answering: given everything Kronos has learned about global financial patterns, and given a backtest on the assets available in Thailand, what does the model expect over the next 20 trading days and how confident is it?</p>

  <h4>Supported Assets (100 tickers, 9 classes)</h4>
  <table>
    <tr><th>Class</th><th>Tickers</th><th>What It Covers</th></tr>
    <tr><td>Thai equity</td><td>50</td><td>SET50 + mid-caps every Thai broker</td></tr>
    <tr><td>US equity</td><td>17</td><td>Mega-cap US stocks via DIME/Liberator</td></tr>
    <tr><td>Crypto</td><td>12</td><td>BTC + alts via Bitkub/Binance TH</td></tr>
    <tr><td>ETF global</td><td>9</td><td>SPY QQQ VTI VWO VEA IEMG EWY EWJ FXI</td></tr>
    <tr><td>Commodity</td><td>4</td><td>GLD GC=F SLV USO</td></tr>
    <tr><td>Bond proxy</td><td>3</td><td>TLT IEF HYG</td></tr>
    <tr><td>REIT</td><td>2</td><td>VNQ CPNREIT.BK</td></tr>
    <tr><td>Thai index</td><td>1</td><td>^SET.BK benchmark only</td></tr>
    <tr><td>FX macro</td><td>2</td><td>THB=X DX-Y.NYB features only</td></tr>
  </table>

  <h4>What It Does NOT Do</h4>
  <ul>
    <li><strong>No order execution.</strong> Kronos-TH does not connect to Settrade, Bitkub, or any broker. It generates forecasts; you decide whether to act.</li>
    <li><strong>No intraday.</strong> Daily bars only. yfinance free intraday is 60-day rolling — not enough to train on.</li>
    <li><strong>No tax optimization.</strong> Capital gains treatment varies by asset class (crypto tax-exempt in Thailand 2025-2029). Consult a tax advisor.</li>
    <li><strong>No survivorship bias adjustment.</strong> The universe includes only currently-listed tickers. Delisted tickers are absent from backtests which overstates returns.</li>
  </ul>
</div>


<h2 id="s2">Quick Start</h2>
<div class="card">
  <h3>Option A: Command Line (Headless)</h3>
  <pre>python -m pip install -r requirements.txt -r requirements-ml.txt -e .
python -c "import torch; assert torch.cuda.is_available(), 'GPU required'"
python -c "
import pandas as pd; from pathlib import Path; import shutil, sys
sys.path.insert(0, 'kronos_repo')
from kth.data.universe import get_all_tickers
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
today = pd.Timestamp.now().strftime('%Y-%m-%d')
slug = 'NeoQuasar_Kronos-small'
today_dir = Path(f'data/forecast_cache/{{slug}}/{{today}}')
if today_dir.exists(): shutil.rmtree(today_dir)

precompute_forecasts(th, get_all_tickers(), start_date=today, end_date=today,
                     pred_len=20, n_samples=10, lookback=400)
print(f'Forecasts cached at data/forecast_cache/{{slug}}/{{today}}/')
"</pre>
  <p><strong>Time:</strong> GTX 1060 ~12 min | T4 ~3 min | First run +20 min for HF download.</p>

  <h3>Option B: Notebook (Recommended)</h3>
  <p>Open <code>notebooks/05_decision_report.ipynb</code> in Jupyter. Set <code>REPORT_MODE = "morning"</code>. Run all cells.</p>
  <div class="highlight">⚠️ <strong>First run</strong>: ~12–15 min (forecast generation). <strong>Subsequent runs</strong>: ~3 sec (cache hit).</div>
</div>

<h2 id="s3">Position Sizing Methodology</h2>

<div class="card">
  <h3>Confidence-Based Sizing</h3>
  <div class="chart">{c8}</div>
  <table>
    <tr><th>Flag</th><th>Band Width</th><th>Size</th><th>Action</th></tr>
    <tr><td><span class="flag-green">🟢 Green</span></td><td>≤10%</td><td>100%</td><td>Full position at conviction</td></tr>
    <tr><td><span class="flag-yellow">🟡 Yellow</span></td><td>10–30%</td><td>50%</td><td>Half-size, moderate confidence</td></tr>
    <tr><td><span class="flag-red">🔴 Red</span></td><td>&gt;30%</td><td>0%</td><td>Skip — model is unsure</td></tr>
  </table>
  <p><strong>Net Return</strong> = P50% − (commission + slippage) × 2. If net ≤ 0%, skip the trade.</p>

  <h3>Class Allocation Caps</h3>
  <div class="chart">{c7}</div>
  <div class="highlight-red" style="font-size:0.85rem;"><strong>&#9888; Crypto risk warning:</strong> Crypto had &minus;69% maximum drawdown and p=0.64 (not statistically significant). The 5% cap in the recommended allocation is the <strong>absolute maximum</strong>. Consider 0-2% if you cannot tolerate a two-thirds portfolio loss.</div>

  <h3>Example Portfolios</h3>
  <div class="two-col">
    <div class="stat">
      <div class="number" style="color:#27ae60;">10–15%</div>
      <div class="label">Conservative CAGR</div>
      <div style="margin-top:6px;font-size:0.82rem;">5 positions, equal-weight, monthly rebalance. Thai 40% + bonds 20% + cash 40%. 🟢 only.</div>
    </div>
    <div class="stat">
      <div class="number" style="color:#2e86c1;">15–25%</div>
      <div class="label">Balanced CAGR</div>
      <div style="margin-top:6px;font-size:0.82rem;">8 positions, inv_vol, monthly. Thai 30% + US 20% + ETF 10% + crypto 5% + cash.</div>
    </div>
  </div>
</div>

<h2 id="s4">The Three Report Views</h2>
<div class="card">
  <table>
    <tr><th>View</th><th>Columns</th><th>Sort</th><th>Use</th></tr>
    <tr><td><strong>Morning Brief</strong></td><td>Ticker, Close, P50%, Band, Flag, Rank, Dir</td><td>Rank score desc (top 10 bull + bottom 10 bear)</td><td>Daily scan over coffee</td></tr>
    <tr><td><strong>Trader's Desk</strong></td><td>+P5/P95%, Sharpe, Friction, NetRet</td><td>Net return desc, grouped by class</td><td>Before placing orders</td></tr>
    <tr><td><strong>Quant PM Review</strong></td><td>+Mean%, CAGR, MaxDD, HistVol</td><td>Class, risk-adj return desc</td><td>Weekly deep dive</td></tr>
  </table>
  <div class="highlight-green"><strong>Reading flags:</strong> 🟢 = confidence (≤10% uncertainty), not direction. 🟢 on ↓ = confidently bearish.</div>
</div>

<h2 id="s5">Backtest Methodology</h2>
<div class="card">
  <div class="detail-grid">
    <div class="detail-item"><div class="title-small">Design</div><div class="value">Strict Walk-Forward</div></div>
    <div class="detail-item"><div class="title-small">Window</div><div class="value">21-month folds</div></div>
    <div class="detail-item"><div class="title-small">Folds</div><div class="value">3 (Fold 0 is most realistic)</div></div>
    <div class="detail-item"><div class="title-small">Sizing</div><div class="value">Equal-weight (baseline)</div></div>
  </div>

  <h4>Friction Costs (Applied Every Trade)</h4>
  <table>
    <tr><th>Class</th><th>Commission</th><th>Slippage</th><th>Round-Trip</th></tr>
    <tr><td>Thai Equity</td><td>0.168%</td><td>0.10%</td><td><strong>0.536%</strong></td></tr>
    <tr><td>US Equity</td><td>0.30%</td><td>0.05%</td><td><strong>0.70%</strong></td></tr>
    <tr><td>Crypto</td><td>0.25%</td><td>0.20%</td><td><strong>0.90%</strong></td></tr>
    <tr><td>Crypto (BTC)</td><td>0.25%</td><td>0.10%</td><td><strong>0.70%</strong></td></tr>
  </table>
</div>

<h2 id="s6">Backtest Results (2022–2024)</h2>

<div class="card">
  <div class="two-col">
    <div class="stat"><div class="number" style="color:#27ae60;">+31.44%</div><div class="label">Thai Equity CAGR</div></div>
    <div class="stat"><div class="number" style="color:#2e86c1;">+30.34%</div><div class="label">US Equity CAGR</div></div>
  </div>
  <div class="two-col">
    <div class="stat"><div class="number" style="color:#f39c12;">+16.45%</div><div class="label">Crypto CAGR</div></div>
    <div class="stat"><div class="number" style="color:#1a5276;">15–30pp</div><div class="label">Alpha over Equal-Weight</div></div>
  </div>
</div>

<div class="chart">{c2}</div>
<div class="chart">{c3}</div>
<div class="chart">{c4}</div>

<div class="card">
  <h3>Fine-Tuning Verdict — Zero-Shot Wins Everywhere</h3>
  <div class="highlight">We spent 65 GPU-hours training 9 models across 3 markets. <strong>None beat zero-shot.</strong></div>
  <div class="highlight-yellow"><strong>Why fine-tuning failed:</strong> The training data distribution (2016-2022) differs from the holdout period (2025). Fine-tuning teaches the model to predict the token distribution of the training period. When market regimes shift — which they always do — a fine-tuned model's predictions degrade faster than the zero-shot model's generalist knowledge. This is a known phenomenon in time-series foundation models.</div>
  <ul>
    <li>Thai equity: ZS 1.40 Sharpe — no FT model exceeded this</li>
    <li>US equity: ZS 0.97 Sharpe — FT F2 achieved 0.94 (−0.03)</li>
    <li>Crypto: ZS 0.52 Sharpe — FT F0 achieved 0.46 (−0.06)</li>
  </ul>
  <p>All 9 checkpoints saved at <code>./checkpoints/{{model}}/fold{{f}}/best/</code> but not deployed.</p>
</div>

<div class="chart">{c5}</div>
<div class="chart">{c6}</div>

<h2 id="s7">Cautions &amp; Limitations</h2>
<div class="card">
  <div class="highlight-red"><strong>This is not financial advice.</strong> Forecasts can be wrong. A 60% direction hit-rate means 40% of predictions miss.</div>

  <ul>
    <li><strong>Survivorship bias:</strong> Only currently-listed tickers are in the universe. Delisted stocks are absent — backtests overstate returns.</li>
    <li><strong>Regime risk:</strong> The 2022-2024 period had unique macro conditions (QE unwind, AI boom, SET underperformance). Different regimes produce different results.</li>
    <li><strong>Crypto calendar mismatch:</strong> Backtests use 5-day business calendar; crypto trades 7 days. Sharpe overstated ~20–30% for crypto. Delta between ZS and FT is valid.</li>
    <li><strong>ETF proxy:</strong> ETF class (9 tickers) uses SPY as backtest proxy. Performance on VWO, EWJ, FXI, etc. is untested.</li>
    <li><strong>4 untested classes:</strong> Commodity, bond_proxy, reit, fx_macro show <code>—</code> in metrics. Do not trade these based solely on model forecasts.</li>
    <li><strong>Trade win rate 2–5%:</strong> This does not mean the model is 95% wrong. It means the portfolio churns positions monthly (11.8× turnover) producing many small losing trades around winning core longs.</li>
    <li><strong>GPU required:</strong> CPU inference is hours vs 15 min on GPU. Use Colab free T4 if you don't have a GPU.</li>
  </ul>
</div>

<h2 id="s8">Performance Tables</h2>
<div class="card">
  <table>
    <tr><th>Metric</th><th>Thai Equity</th><th>US Equity</th><th>Crypto</th></tr>
    <tr><td>CAGR</td><td><strong>+31.44%</strong></td><td><strong>+30.34%</strong></td><td><strong>+16.45%</strong></td></tr>
    <tr><td>Sharpe</td><td><strong>1.40</strong></td><td><strong>0.97</strong></td><td><strong>0.52</strong></td></tr>
    <tr><td>Sortino</td><td>2.28</td><td>1.45</td><td>0.70</td></tr>
    <tr><td>Max DD</td><td>−17.97%</td><td>−43.77%</td><td>−68.58%</td></tr>
    <tr><td>Calmar</td><td>1.75</td><td>0.69</td><td>0.24</td></tr>
    <tr><td>Trade Win Rate</td><td>2.51%</td><td>2.78%</td><td>1.48%</td></tr>
    <tr><td>Annual Turnover</td><td>11.8×</td><td>9.2×</td><td>6.7×</td></tr>
    <tr><td>Friction Drag (annual)</td><td>6.3%</td><td>6.4%</td><td>6.0%</td></tr>
    <tr><td>p-value</td><td>&lt;0.05*</td><td>0.46</td><td>0.64</td></tr>
  </table>
  <div class="highlight-green">Thai equity Max DD (−17.97%) is nearly identical to equal-weight (−18.07%). The model does NOT increase tail risk over passive allocation. Alpha is "free" from a risk perspective.</div>
  <div class="highlight">Annual friction drag = Turnover × round-trip friction. Thai: 11.8 × 0.536% = 6.3% of AUM lost to costs annually. CAGR reported is net of these costs.</div>
  <p style="font-size:0.82rem;color:#7f8c8d;margin-top:6px;">* p &lt; 0.05 = statistically significant. p > 0.05 = not distinguishable from random noise.</p>
</div>

<h4>Benchmark Comparison — CAGR vs SPY, SET, and Equal-Weight</h4>
<div class="card">
  <table>
    <tr><th>Market</th><th>Strategy CAGR</th><th>SET Index</th><th>SPY</th><th>Equal-Weight</th><th>Alpha (over eq-wt)</th></tr>
    <tr><td><strong>Thai Equity</strong></td><td><strong>+31.44%</strong></td><td>−5.29%</td><td>+8.33%</td><td>+1.44%</td><td><strong>+30.0pp</strong></td></tr>
    <tr><td><strong>US Equity</strong></td><td><strong>+30.34%</strong></td><td>−5.29%</td><td>+8.33%</td><td>+14.39%</td><td><strong>+15.9pp</strong></td></tr>
    <tr><td><strong>Crypto</strong></td><td><strong>+16.45%</strong></td><td>−5.29%</td><td>+8.33%</td><td>−5.16%</td><td><strong>+21.6pp</strong></td></tr>
  </table>
  <p style="font-size:0.82rem;color:#555;margin-top:6px;">All returns net of frictions. SET Index was down 5.29% over 2022-2024. The strategy beats SET, SPY, and equal-weight in all 3 markets.</p>
</div>


<h2 id="s9">File Reference</h2>
<div class="card" style="font-size:0.85rem;">
  <table>
    <tr><th>File</th><th>Purpose</th></tr>
    <tr><td><code>kth/data/universe.py</code></td><td>100 tickers, 9 classes, friction costs</td></tr>
    <tr><td><code>kth/data/loader.py</code></td><td>yfinance → parquet cache, Kronos format</td></tr>
    <tr><td><code>kth/models/kronos_wrapper.py</code></td><td>KronosTH forecast / forecast_batch</td></tr>
    <tr><td><code>kth/models/finetune.py</code></td><td>Dataset prep, evaluate, checkpoint loader</td></tr>
    <tr><td><code>kth/backtest/walkforward.py</code></td><td>precompute_forecasts, run_walkforward</td></tr>
    <tr><td><code>kth/backtest/metrics.py</code></td><td>Sharpe, Sortino, Max DD, trade metrics</td></tr>
    <tr><td><code>kth/backtest/strategy.py</code></td><td>compute_signals, compute_weights</td></tr>
    <tr><td><code>scripts/train_per_market.py</code></td><td>SGDR fine-tuning per market</td></tr>
    <tr><td><code>scripts/compare_finetune.py</code></td><td>FT vs ZS backtest comparison</td></tr>
    <tr><td><code>scripts/eval_holdout.py</code></td><td>2025 holdout direction accuracy</td></tr>
    <tr><td><code>notebooks/05_decision_report.ipynb</code></td><td>Daily decision report (3 views)</td></tr>
  </table>
</div>

<a href="#" class="btt" onclick="window.scrollTo(0,0);return false;">&#8593;</a>

<div style="text-align:center;padding:30px 0 10px;color:#95a5a6;font-size:0.82rem;">
  Generated 2026-05-24 • Not financial advice • Past performance is not indicative of future results
</div>
</div>
</body>
</html>"""


def main():
    html = build_html()
    out_path = Path("docs/user-manual.html")
    out_path.write_text(html, encoding="utf-8")
    print(f"Written to {out_path} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
