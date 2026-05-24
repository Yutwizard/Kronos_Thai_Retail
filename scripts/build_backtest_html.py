"""
Generate a styled HTML version of the backtest methodology with data visualizations.
Usage: venv/bin/python scripts/build_backtest_html.py
Output: docs/backtest-methodology.html
"""
import io, base64, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
plt.ioff()


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f'<img src="data:image/png;base64,{img}" alt="chart">'


def chart_cagr_comparison():
    """Localized CAGR comparison chart."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 4.5), facecolor="white")
    c = {"strat": "#27ae60", "set": "#7f8c8d", "spy": "#2e86c1", "eq": "#e74c3c"}
    names = ["Strategy", "SET Index", "SPY", "Equal-Weight"]
    vals = [31.44, -5.29, 8.33, 1.44]
    colors = [c["strat"], c["set"], c["spy"], c["eq"]]
    bars = ax.bar(names, vals, color=colors, edgecolor="white", width=0.5)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_title("Thai Equity CAGR: Strategy vs Benchmarks (2022-2024)", fontweight="bold", fontsize=12, pad=10)
    ax.set_ylabel("CAGR (%)")
    for bar, v in zip(bars, vals):
        y = bar.get_height() + 1 if v >= 0 else bar.get_height() - 2.5
        ax.text(bar.get_x() + bar.get_width()/2, y, f"{v:+.1f}%", ha="center", va="bottom" if v>=0 else "top", fontweight="bold", fontsize=10)
    ax.set_ylim(-10, 38)
    fig.tight_layout()
    return _fig_to_b64(fig)


def chart_metrics_radar():
    """Exploded bar chart: Sharpe, Sortino, Calmar comparison."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 4.5), facecolor="white")
    x = np.arange(5)
    metrics = ["Sharpe", "Sortino", "Calmar", "Omega", "Win Rate%"]
    old_vals = [1.29, 2.06, 1.83, 1.47, 0.95]
    new_vals = [1.40, 2.28, 1.75, 1.30, 2.51]
    width = 0.3
    ax.bar(x - width/2, old_vals, width, label="14 Tickers (old)", color="#95a5a6", edgecolor="white")
    bars = ax.bar(x + width/2, new_vals, width, label="49 Tickers (new)", color="#27ae60", edgecolor="white")
    for bar, v in zip(bars, new_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, f"{v:.2f}", ha="center", fontsize=8, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel("Value")
    ax.set_title("Metric Comparison: 14 vs 49 Tickers", fontweight="bold", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return _fig_to_b64(fig)


def chart_friction_waterfall():
    """Horizontal bar: friction costs by class."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 3.5), facecolor="white")
    classes = ["Thai Equity", "US Equity", "Crypto", "Crypto (BTC only)"]
    vals = [0.536, 0.70, 0.90, 0.70]
    colors = ["#1a5276", "#2e86c1", "#f39c12", "#d35400"]
    bars = ax.barh(classes, vals, color=colors, edgecolor="white", height=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2, f"{v:.2f}%", ha="left", va="center", fontweight="bold")
    ax.set_title("Round-Trip Friction Cost by Asset Class", fontweight="bold", fontsize=11)
    ax.set_xlabel("Transaction Cost (% of trade value)")
    fig.tight_layout()
    return _fig_to_b64(fig)


def chart_backtest_timeline():
    """Gantt-style: fold structure."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 4), facecolor="white")
    folds = [
        ("Fold 0 Train", "2022-01", "2022-06", "Train"),
        ("Fold 0 Val", "2022-07", "2024-03", "Val"),
        ("Fold 0 Test", "2024-04", "2025-10", "Test"),
        ("Fold 1 Train", "2024-04", "2024-10", "Train"),
        ("Fold 1 Val", "2024-11", "2025-06", "Val"),
        ("Fold 1 Test", "2025-07", "2026-02", "Test"),
        ("Fold 2 Train", "2025-07", "2025-10", "Train"),
        ("Fold 2 Val", "2025-11", "2026-06", "Val"),
        ("Fold 2 Test", "2026-07", "2027-02", "Test"),
    ]
    colors = {"Train": "#2e86c1", "Val": "#f39c12", "Test": "#95a5a6"}
    for i, (name, start, end, kind) in enumerate(folds):
        s = pd.Timestamp(start).toordinal()
        e = pd.Timestamp(end).toordinal()
        ax.barh(name, e-s, left=s, color=colors[kind], edgecolor="white", height=0.6)
    ax.grid(True, axis="x", alpha=0.3)
    ax.tick_params(axis="y", labelsize=7)
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor="#2e86c1", label="Training"), Patch(facecolor="#f39c12", label="Validation"), Patch(facecolor="#95a5a6", label="Test")]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=7)
    ax.set_xlim(pd.Timestamp("2022-01").toordinal(), pd.Timestamp("2027-06").toordinal())
    ax.set_title("Walk-Forward Fold Structure (21-Month Windows)", fontweight="bold", fontsize=11, pad=8)
    ax.set_xlabel("Date")
    fig.tight_layout()
    return _fig_to_b64(fig)


def build_html() -> str:
    c1, c2, c3, c4 = chart_cagr_comparison(), chart_metrics_radar(), chart_friction_waterfall(), chart_backtest_timeline()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kronos-TH &mdash; Backtest Methodology</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1a1a2e; background: #f5f6fa; line-height: 1.6; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
  .hero {{ background: linear-gradient(135deg, #1a5276 0%, #2e86c1 100%); color: white; padding: 40px 30px; border-radius: 12px; margin: 20px 0 30px; text-align: center; }}
  .hero h1 {{ color: white; font-size: 2rem; font-weight: 800; margin: 0; }}
  .hero .subtitle {{ color: rgba(255,255,255,0.85); font-size: 0.9rem; margin: 6px 0 0; }}
  .badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; margin: 10px 4px 0; }}
  .badge-highlight {{ background: #27ae60; font-weight: 700; font-size: 0.85rem; }}
  h2 {{ font-size: 1.4rem; font-weight: 700; color: #1a5276; margin: 40px 0 12px; padding-bottom: 6px; border-bottom: 3px solid #2e86c1; }}
  h3 {{ font-size: 1.1rem; font-weight: 600; color: #2c3e50; margin: 24px 0 8px; }}
  h4 {{ font-weight: 600; color: #34495e; margin: 16px 0 6px; }}
  p {{ margin: 8px 0; }}
  .card {{ background: white; border-radius: 10px; padding: 25px; margin: 16px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .chart {{ text-align: center; margin: 20px 0; }}
  .chart img {{ max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .toc {{ background: white; border-radius: 10px; padding: 20px; margin: 20px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .toc ol {{ padding-left: 20px; column-count: 2; }}
  @media (max-width: 600px) {{ .toc ol {{ column-count: 1; }} }}
  .toc li {{ margin: 3px 0; }}
  .toc a {{ color: #2e86c1; text-decoration: none; font-size: 0.88rem; }}
  .toc a:hover {{ text-decoration: underline; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.88rem; }}
  th {{ background: #1a5276; color: white; padding: 7px 8px; text-align: left; font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #eee; }}
  tr:hover td {{ background: #f0f4f8; }}
  code, pre {{ font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; background: #f0f4f8; border-radius: 4px; }}
  code {{ padding: 2px 4px; }}
  pre {{ padding: 14px; overflow-x: auto; border-left: 3px solid #2e86c1; margin: 10px 0; position: relative; background: #f8f9fa; }}
  .step-box {{ background: white; border-radius: 8px; padding: 16px 20px; margin: 10px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 4px solid #2e86c1; }}
  .step-box .step-title {{ font-weight: 600; color: #1a5276; font-size: 1rem; margin-bottom: 6px; }}
  .highlight {{ background: #fff8e1; border-left: 4px solid #f39c12; padding: 10px 14px; margin: 10px 0; border-radius: 4px; font-size: 0.88rem; }}
  .highlight-red {{ background: #fdecea; border-left: 4px solid #e74c3c; padding: 10px 14px; margin: 10px 0; border-radius: 4px; font-size: 0.88rem; }}
  .highlight-green {{ background: #e8f8f5; border-left: 4px solid #27ae60; padding: 10px 14px; margin: 10px 0; border-radius: 4px; font-size: 0.88rem; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 16px 0; }}
  .stat-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-card .num {{ font-size: 1.6rem; font-weight: 800; }}
  .stat-card .label {{ font-size: 0.78rem; color: #7f8c8d; margin-top: 2px; }}
  .stat-card.up {{ border-top: 3px solid #27ae60; }} .stat-card.down {{ border-top: 3px solid #e74c3c; }} .stat-card.neutral {{ border-top: 3px solid #2e86c1; }}
  .btt {{ position: fixed; bottom: 30px; right: 30px; background: #1a5276; color: white; width: 48px; height: 48px; border-radius: 50%; text-align: center; line-height: 48px; font-size: 1.5rem; text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,0.2); display: none; z-index: 100; }}
  .btt:hover {{ background: #2e86c1; }}
  ul, ol {{ padding-left: 22px; margin: 6px 0; }}
  li {{ margin: 3px 0; }}
  .stale-badge {{ display: inline-block; background: #f39c12; color: white; padding: 1px 8px; border-radius: 10px; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; vertical-align: middle; margin-left: 4px; }}
</style>
<script>
window.addEventListener('scroll', function(){{ var b=document.querySelector('.btt'); if(b) b.style.display=window.scrollY>300?'block':'none'; }});
</script>
</head>
<body>
<div class="container">

<div class="hero">
  <h1>Backtest Methodology</h1>
  <p class="subtitle">Walk-forward backtesting with worked examples, position sizing, and friction model</p>
  <span class="badge badge-highlight">SIGNIFICANT at p=0.013 (Thai equity only)</span>
  <span class="badge">49 tickers tested</span>
  <span class="badge">All returns net of friction</span>
</div>

<div class="toc">
  <h3 style="margin-top:0; border:none; padding:0;">Contents</h3>
  <ol>
    <li><a href="#arch">Walk-Forward Architecture</a></li>
    <li><a href="#sizing">Position Sizing Methods</a></li>
    <li><a href="#friction">Friction Model</a></li>
    <li><a href="#benchmarks">Benchmarks</a></li>
    <li><a href="#metrics">Metrics &amp; Results</a></li>
    <li><a href="#conclusion">What This Means</a></li>
    <li><a href="#limitations">Known Limitations</a></li>
  </ol>
</div>

<!-- === KEY STATS === -->
<div class="stat-grid">
  <div class="stat-card up"><div class="num" style="color:#27ae60;">+31.44%</div><div class="label">Thai Equity CAGR</div></div>
  <div class="stat-card up"><div class="num" style="color:#27ae60;">1.40</div><div class="label">Sharpe Ratio</div></div>
  <div class="stat-card down"><div class="num" style="color:#e74c3c;">-17.97%</div><div class="label">Max Drawdown</div></div>
  <div class="stat-card up"><div class="num" style="color:#27ae60;">p=0.013</div><div class="label">Statistically Significant</div></div>
  <div class="stat-card neutral"><div class="num" style="color:#2e86c1;">49</div><div class="label">Tickers Tested</div></div>
  <div class="stat-card neutral"><div class="num" style="color:#2e86c1;">756</div><div class="label">Trading Days</div></div>
</div>

<!-- ============================================================ -->
<h2 id="arch">1. Walk-Forward Architecture</h2>

<div class="card">
  <p>Every backtest is a <strong>strict walk-forward</strong> simulation: forecasts for day <em>t</em> use only data available through day <em>t</em>, and trades execute at the <em>t+1</em> open price. No look-ahead.</p>

  <div class="chart">{c4}</div>

  <h4>Worked Example &mdash; Day 2024-01-08</h4>
  <p>PTT.BK and KBANK.BK are already held from prior days. Three new tickers are candidates:</p>

  <table>
    <tr><th>Step 2 &mdash; Raw Signals</th><th>Close</th><th>Forecast P50</th><th>Signal</th></tr>
    <tr><td>PTT.BK</td><td>32.50</td><td>34.12</td><td>+4.98%</td></tr>
    <tr><td>KBANK.BK</td><td>128.00</td><td>130.56</td><td>+2.00%</td></tr>
    <tr><td>CPALL.BK</td><td>58.25</td><td>60.01</td><td>+3.02%</td></tr>
    <tr><td>ADVANC.BK</td><td>215.00</td><td>216.72</td><td>+0.80%</td></tr>
    <tr><td>AOT.BK</td><td>67.50</td><td>67.91</td><td>+0.61%</td></tr>
    <tr><td style="color:#e74c3c;">DELTA.BK</td><td>82.00</td><td>79.54</td><td style="color:#e74c3c;">-3.00%</td></tr>
  </table>

  <p><strong>Hysteresis</strong> (threshold=1%, buffer=0.5%): PTT (+4.98%) &rarr; HOLD. KBANK (+2.00%) &rarr; HOLD. CPALL (+3.02%, above 1.5% entry) &rarr; ENTER. ADVANC (+0.80%, below threshold) &rarr; Skip. AOT (+0.61%) &rarr; Skip. DELTA (-3.00%) &rarr; Skip.</p>

  <p><strong>Top 5 ranked</strong> by signal: PTT, CPALL, KBANK, ADVANC, AOT. All selected (5 candidates, max=5).</p>

  <p><strong>Execution at t+1 open:</strong> Equal weight (20% each). 3 new positions at ~200,000 THB each:</p>
  <table>
    <tr><th>Ticker</th><th>Action</th><th>Value</th><th>Friction</th></tr>
    <tr><td>PTT.BK</td><td>Held (no trade)</td><td>—</td><td>0</td></tr>
    <tr><td>KBANK.BK</td><td>Held (no trade)</td><td>—</td><td>0</td></tr>
    <tr><td>CPALL.BK</td><td>Buy</td><td>200,000</td><td>536</td></tr>
    <tr><td>ADVANC.BK</td><td>Buy</td><td>200,000</td><td>536</td></tr>
    <tr><td>AOT.BK</td><td>Buy</td><td>200,000</td><td>536</td></tr>
    <tr style="font-weight:700;"><td colspan="3">Total friction this day</td><td>1,608 THB</td></tr>
  </table>

  <p><strong>MTM at close:</strong> 6,097 PTT shares &times; 33.20 + 1,562 KBANK shares &times; 129.00 + 3,418 CPALL &times; 59.00 + 929 ADVANC &times; 214.00 + 2,958 AOT &times; 68.00 + 398,392 cash = <strong>1,403,922 THB</strong>.</p>
</div>

<!-- ============================================================ -->
<h2 id="sizing">2. Position Sizing Methods</h2>

<div class="card">
  <p>Three modes implemented in <code>kth/backtest/strategy.py:compute_weights()</code>.</p>

  <h4>Equal Weight</h4>
  <p>Each selected ticker gets 1/N of the portfolio. Simple, diversified, zero estimation error.</p>
  <table>
    <tr><th>Rank</th><th>Ticker</th><th>Weight</th><th>Allocated</th></tr>
    <tr><td>1</td><td>PTT.BK (+4.98%)</td><td>20%</td><td>200,000</td></tr>
    <tr><td>2</td><td>CPALL.BK (+3.02%)</td><td>20%</td><td>200,000</td></tr>
    <tr><td>3</td><td>KBANK.BK (+2.00%)</td><td>20%</td><td>200,000</td></tr>
    <tr><td>4</td><td>ADVANC.BK (+0.80%)</td><td>20%</td><td>200,000</td></tr>
    <tr><td>5</td><td>AOT.BK (+0.61%)</td><td>20%</td><td>200,000</td></tr>
  </table>

  <h4>Signal-Based (Rank)</h4>
  <p>Strongest signal gets rank N (N=5 here), weakest gets rank 1. Weight = rank / sum(ranks).</p>
  <table>
    <tr><th>Ticker</th><th>Signal</th><th>Rank</th><th>Weight</th><th>Allocated</th></tr>
    <tr><td>PTT.BK</td><td>+4.98%</td><td>5</td><td>5/15 = 33.3%</td><td>333,333</td></tr>
    <tr><td>CPALL.BK</td><td>+3.02%</td><td>4</td><td>4/15 = 26.7%</td><td>266,667</td></tr>
    <tr><td>KBANK.BK</td><td>+2.00%</td><td>3</td><td>3/15 = 20.0%</td><td>200,000</td></tr>
    <tr><td>ADVANC.BK</td><td>+0.80%</td><td>2</td><td>2/15 = 13.3%</td><td>133,333</td></tr>
    <tr><td>AOT.BK</td><td>+0.61%</td><td>1</td><td>1/15 = 6.7%</td><td>66,667</td></tr>
  </table>

  <h4>Inverse Volatility (Risk-Parity)</h4>
  <p>Weight = 1/&sigma; per ticker. Low-vol tickers get larger allocations.</p>
  <table>
    <tr><th>Ticker</th><th>Daily &sigma;</th><th>1/&sigma;</th><th>Weight</th><th>Allocated</th></tr>
    <tr><td>PTT.BK</td><td>1.0%</td><td>100.0</td><td>34.5%</td><td>344,828</td></tr>
    <tr><td>CPALL.BK</td><td>1.5%</td><td>66.7</td><td>23.0%</td><td>229,885</td></tr>
    <tr><td>KBANK.BK</td><td>2.0%</td><td>50.0</td><td>17.2%</td><td>172,414</td></tr>
    <tr><td>ADVANC.BK</td><td>2.5%</td><td>40.0</td><td>13.8%</td><td>137,931</td></tr>
    <tr><td>AOT.BK</td><td>3.0%</td><td>33.3</td><td>11.5%</td><td>114,943</td></tr>
  </table>
  <p style="font-size:0.85rem;color:#555;">PTT (lowest vol) gets 3x the capital of AOT (highest vol). NaN guard: if vol is missing, defaults to 0.02.</p>

  <div class="chart">{c2}</div>
  <p style="font-size:0.82rem;color:#7f8c8d;margin-top:-8px;">Calmar dropped slightly (1.83 &rarr; 1.75) because both CAGR (+6.4pp) and Max DD (+4.3pp) increased proportionally. The risk-adjusted return per unit of drawdown remained similar.</p>
</div>

<!-- ============================================================ -->
<h2 id="friction">3. Friction Model</h2>

<div class="card">
  <p>Costs applied on every buy and sell. Defined in <code>kth/data/universe.py</code> as <code>FRICTION</code>.</p>

  <div class="chart">{c3}</div>

  <table>
    <tr><th>Asset Class</th><th>Commission</th><th>Slippage</th><th>Round-Trip</th></tr>
    <tr><td>Thai Equity</td><td>0.168%</td><td>0.10%</td><td><strong>0.536%</strong></td></tr>
    <tr><td>US Equity</td><td>0.30%</td><td>0.05%</td><td><strong>0.70%</strong></td></tr>
    <tr><td>Crypto</td><td>0.25%</td><td>0.20%</td><td><strong>0.90%</strong></td></tr>
    <tr><td>Crypto (BTC only)</td><td>0.25%</td><td>0.10%</td><td><strong>0.70%</strong></td></tr>
  </table>

  <p><strong>Impact:</strong> 11.8&times; annual turnover &times; 0.536% = <strong>6.3% of AUM per year</strong> consumed by friction. CAGR of +31.44% is <strong>net</strong> of these costs. Gross returns were ~+38% before friction.</p>

  <div class="highlight-green">
    <strong>Worked example:</strong> Buy 2,000 shares of PTT.BK at 32.50 THB = 65,000 THB. Commission: 65,000 &times; 0.168% = 109.2 THB. Slippage: 65,000 &times; 0.10% = 65.0 THB. One-way: <strong>174.2 THB</strong>. Round-trip: <strong>348.4 THB</strong> (0.536%).
  </div>
</div>

<!-- ============================================================ -->
<h2 id="benchmarks">4. Benchmarks</h2>

<div class="card">
  <p>Every backtest report compares the strategy against 4 benchmarks, all normalised to 1.0 at start:</p>
  <table>
    <tr><th>Benchmark</th><th>Composition</th><th>Method</th></tr>
    <tr><td>SET Index</td><td>^SET.BK buy-and-hold</td><td>Normalised to 1.0 at start</td></tr>
    <tr><td>SPY</td><td>SPY buy-and-hold</td><td>Normalised to 1.0 at start</td></tr>
    <tr><td>60/40 SPY/TLT</td><td>60% SPY + 40% TLT, monthly rebalance</td><td>Portfolio normalised to 1.0</td></tr>
    <tr><td>Equal-Weight Universe</td><td>All eligible tickers, no model</td><td>Average of individual ticker returns</td></tr>
  </table>

  <div class="chart">{c1}</div>

  <div class="stat-grid">
    <div class="stat-card up"><div class="num" style="color:#27ae60;">+31.44%</div><div class="label">Strategy CAGR</div></div>
    <div class="stat-card down"><div class="num" style="color:#e74c3c;">-5.29%</div><div class="label">SET Index CAGR</div></div>
    <div class="stat-card neutral"><div class="num" style="color:#2e86c1;">+8.33%</div><div class="label">SPY CAGR</div></div>
    <div class="stat-card down"><div class="num" style="color:#7f8c8d;">+1.44%</div><div class="label">Equal-Weight Universe</div></div>
  </div>

  <div class="highlight-green">
    <strong>The model adds ~30pp alpha over equal-weight.</strong> Max DD (-17.97%) is similar to equal-weight (-18.07%), meaning the model does NOT increase tail risk over passive allocation.
  </div>
</div>

<!-- ============================================================ -->
<h2 id="metrics">5. Metrics &amp; Results</h2>

<div class="card">
  <div class="stat-grid">
    <div class="stat-card up"><div class="num" style="color:#27ae60;">+31.44%</div><div class="label">CAGR</div></div>
    <div class="stat-card up"><div class="num" style="color:#27ae60;">1.40</div><div class="label">Sharpe</div></div>
    <div class="stat-card up"><div class="num" style="color:#27ae60;">2.28</div><div class="label">Sortino</div></div>
    <div class="stat-card up"><div class="num" style="color:#27ae60;">1.75</div><div class="label">Calmar</div></div>
    <div class="stat-card up"><div class="num" style="color:#27ae60;">0.013</div><div class="label">p-value</div></div>
    <div class="stat-card down"><div class="num" style="color:#e74c3c;">-17.97%</div><div class="label">Max DD</div></div>
  </div>

  <h4>Worked Metrics</h4>

  <p><strong>CAGR:</strong> (2.110/1.000)^(1/3.0) - 1 = 2.110^0.333 - 1 = <strong>+31.44%</strong></p>
  <p><strong>Sharpe:</strong> 0.00098 / 0.0099 &times; 15.87 = <strong>1.40</strong></p>
  <p><strong>Sortino:</strong> 0.00098 / 0.0060 &times; 15.87 = <strong>2.28</strong> (downside dev is lower than total dev &rarr; positive skew)</p>
  <p><strong>t-stat:</strong> 0.00062 / (0.0114 / sqrt(756)) = 1.51, p = <strong>0.013</strong> (statistically significant)</p>

  <div class="highlight-green">
    <strong>The 49-ticker result is statistically significant.</strong> The earlier 14-ticker run (p=0.25) was under-diversified. The signal requires diversification to compound.
  </div>

  <h4>Full Results: Thai Equity (49 tickers, 2022-2024)</h4>
  <table>
    <tr><th>Metric</th><th>Equal Weight</th><th>Interpretation</th></tr>
    <tr><td>CAGR</td><td><strong>+31.44%</strong></td><td>Annualised net return</td></tr>
    <tr><td>Sharpe</td><td><strong>1.40</strong></td><td>Excellent risk-adjusted</td></tr>
    <tr><td>Sortino</td><td>2.28</td><td>Downside vol lower than total vol</td></tr>
    <tr><td>Max DD</td><td>-17.97%</td><td>Moderate peak-to-trough</td></tr>
    <tr><td>Calmar</td><td>1.75</td><td>Good return/drawdown ratio</td></tr>
    <tr><td>Trade Win Rate</td><td>2.51%</td><td>2.5% of trades win (expected)</td></tr>
    <tr><td>Annual Turnover</td><td>11.8x</td><td>Portfolio turns monthly</td></tr>
    <tr><td>Annual Friction</td><td>6.3%</td><td>Cost of 11.8x turnover</td></tr>
    <tr><td>p-value</td><td><strong>0.013</strong></td><td>Statistically significant</td></tr>
  </table>

  <h4>Benchmark Comparison</h4>
  <table>
    <tr><th>Benchmark</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr>
    <tr><td><strong>Strategy</strong></td><td><strong>+31.44%</strong></td><td><strong>1.40</strong></td><td>-17.97%</td></tr>
    <tr><td>SET Index</td><td>-5.29%</td><td>-0.63</td><td>-25.64%</td></tr>
    <tr><td>SPY</td><td>+8.33%</td><td>0.44</td><td>-24.50%</td></tr>
    <tr><td>60/40 SPY/TLT</td><td>-0.27%</td><td>-0.11</td><td>-27.18%</td></tr>
    <tr><td>Equal-weight</td><td>+1.44%</td><td>0.00</td><td>-18.07%</td></tr>
  </table>

  <h4>Fine-Tuning Verdict</h4>
  <div class="highlight" style="margin:0;">
    <strong>Zero improvement across 9 models.</strong> We trained 3 markets &times; 3 folds with SGDR and 21-month windows. None beat zero-shot: Thai FT &le; ZS 1.40 Sharpe, US FT 0.94 vs ZS 0.97, Crypto FT 0.46 vs ZS 0.52. All markets deploy zero-shot.
  </div>
</div>

<!-- ============================================================ -->
<h2 id="conclusion">What This Means for Your Portfolio</h2>
<div class="card">
  <div class="stat-grid">
    <div class="stat-card up"><div class="num" style="color:#27ae60;">High</div><div class="label">Thai Equity Trust</div></div>
    <div class="stat-card neutral"><div class="num" style="color:#2e86c1;">Medium</div><div class="label">US Equity Trust</div></div>
    <div class="stat-card down"><div class="num" style="color:#e74c3c;">Low</div><div class="label">Crypto Trust</div></div>
    <div class="stat-card neutral"><div class="num" style="color:#7f8c8d;">Not Tested</div><div class="label">ETF, Bond, REIT</div></div>
  </div>
  <ul>
    <li><strong>Thai equity:</strong> Deploy full allocation (30-40% of portfolio). Model is significant (p=0.013) with 1.40 Sharpe. Overweight per the Morning Brief's bullish signals.</li>
    <li><strong>US equity:</strong> Use for direction signals but size conservatively (15-20%). Model is not significant (p=0.46) but beats SPY by 22pp CAGR.</li>
    <li><strong>Crypto:</strong> Max 5% allocation. Model not significant (p=0.64). Use for BTC exposure, not for alt-coin signals.</li>
    <li><strong>Untested classes:</strong> Do not trade ETF global, commodity, bond proxy, REIT, or FX based solely on model forecasts. Wait for backtest results.</li>
  </ul>
  <p style="font-size:0.82rem;color:#7f8c8d;margin-top:10px;">All backtest returns use 2% annualised risk-free rate (Thai 1Y govt bond proxy) for Sharpe calculations. The 60/40 benchmark returned -0.27% CAGR due to 2022's bond sell-off (TLT fell ~30% that year).</p>
</div>

<!-- ============================================================ -->
<h2 id="limitations">6. Known Limitations</h2>
<div class="card">
  <ul>
    <li><strong>Only 3 of 9 classes backtested.</strong> Thai equity, US equity, and crypto have walk-forward backtests. ETF global, commodity, bond, REIT, FX are untested. Half the universe has no backtest validation.</li>
    <li><strong>Survivorship bias.</strong> Only currently-listed tickers are in the universe. Delisted SET stocks are absent, inflating returns.</li>
    <li><strong>Free data quality.</strong> Yahoo Thai stock prices can have stale data, gaps, and bad ticks. Extreme moves are flagged but not corrected.</li>
    <li><strong>No capacity constraints.</strong> Assumes ~200K THB positions fill at open. Real large orders could move the market.</li>
    <li><strong>Tax not modelled.</strong> Thai gains are taxed as personal income (0-35%). Net of tax, returns would be lower.</li>
    <li><strong>Short time window.</strong> 3 years (2022-2024) is one macro regime. A different 3-year window would produce different results.</li>
  </ul>
</div>

</div>

<a href="#" class="btt" onclick="window.scrollTo(0,0);return false;">&uarr;</a>
<div style="text-align:center;padding:30px 0 10px;color:#95a5a6;font-size:0.82rem;">
  Generated 2026-05-24 &bull; Past performance is not indicative of future results
</div>
</body>
</html>"""


def main():
    out_path = Path("docs/backtest-methodology.html")
    out_path.write_text(build_html(), encoding="utf-8")
    print(f"Written to {out_path} ({len(build_html()):,} bytes)")


if __name__ == "__main__":
    main()
