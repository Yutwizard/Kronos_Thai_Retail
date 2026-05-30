"""Generate realistic YTD journal: use real equity curve, add lot-size + friction display."""
import json
import pandas as pd
import numpy as np
from pathlib import Path

result_dir = Path("data/backtest_results/thai_equity_2026_ytd")
trades = pd.read_parquet(result_dir / "trades.parquet")
eq = pd.read_parquet(result_dir / "equity_curve.parquet")["equity"]
with open(result_dir / "metrics.json") as f:
    m = json.load(f)

cap = 500_000
eq_thb = eq * cap

# Load cached prices for share calculations
from kth.data.loader import load_cached
ticker_prices = {}
for t in trades["ticker"].unique():
    try:
        df = load_cached(t)
        ticker_prices[t] = dict(zip(df["timestamps"].astype(str).str[:10], df["close"]))
    except:
        ticker_prices[t] = {}

LOT = 100
from kth.data.universe import FRICTION
frict = FRICTION["thai_equity"]
oneway = frict["commission_oneway"] + frict["slippage_oneway"]

# Annotate trades with share lots and friction THB
trades["date"] = pd.to_datetime(trades["date"])
trades["thb"] = trades["size_pct"] * cap
trades["price"] = trades.apply(lambda r: ticker_prices.get(r["ticker"], {}).get(str(r["date"])[:10], 0), axis=1)
trades["shares"] = np.where(trades["price"] > 0, (trades["thb"] / trades["price"] / LOT).round() * LOT, 0)
trades["actual_thb"] = trades["shares"] * trades["price"]
trades["friction_thb"] = trades["actual_thb"] * oneway
trades["pnl_thb"] = trades["gross_return"] * trades["thb"]

# Total friction
total_friction_thb = trades["friction_thb"].sum()
total_pnl = trades["pnl_thb"].sum()

# Monthly from equity curve
monthly = eq_thb.resample("ME").last()

# Build rows
trade_rows = []
for _, r in trades.iterrows():
    cls = "buy" if r["direction"].upper() == "BUY" else "sell"
    ret = f"{r['gross_return']:.2%}" if r["gross_return"] != 0 else "—"
    trade_rows.append(
        f"  <tr class='{cls}'><td>{r['date'].strftime('%Y-%m-%d')}</td>"
        f"<td>{r['ticker']}</td><td>{r['direction'].upper()}</td>"
        f"<td align='right'>{r['shares']:.0f}</td>"
        f"<td align='right'>{r['price']:.2f}</td>"
        f"<td align='right'>{r['actual_thb']:,.0f}</td>"
        f"<td align='right'>{r['friction_thb']:.0f}</td>"
        f"<td align='right'>{ret}</td></tr>"
    )

# Portfolio value rows (every 3rd day)
pv_rows = []
for i in range(0, len(eq_thb), 3):
    pv_rows.append(f"  <tr><td>{eq_thb.index[i].strftime('%Y-%m-%d')}</td><td align='right'>{eq_thb.iloc[i]:,.0f}</td></tr>")
pv_rows.append(f"  <tr><td>{eq_thb.index[-1].strftime('%Y-%m-%d')}</td><td align='right'>{eq_thb.iloc[-1]:,.0f}</td></tr>")

# Normalize equity curve for chart
eq_n = (eq_thb.values - eq_thb.min()) / (eq_thb.max() - eq_thb.min() + 1)
bar_step = max(1, len(eq_n) // 200)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>2026 YTD Trading Journal — Kronos-TH (Lot-Size Adjusted)</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 1200px; margin: 30px auto; padding: 0 20px; background: #f5f7fa; color: #333; }}
  h1 {{ color: #1565C0; border-bottom: 3px solid #1565C0; padding-bottom: 8px; }}
  h2 {{ color: #444; margin: 28px 0 12px; }}
  .meta {{ color: #888; font-size: 0.85em; }}
  .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 20px 0; }}
  .card {{ background: white; border-radius: 10px; padding: 14px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); flex: 1; min-width: 120px; text-align: center; }}
  .card .val {{ font-size: 1.5em; font-weight: 700; margin: 4px 0; }}
  .card .lbl {{ font-size: 0.75em; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
  .green {{ color: #27ae60; }} .red {{ color: #e74c3c; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin: 12px 0; font-size: 0.82em; }}
  th {{ background: #1565C0; color: white; padding: 10px 10px; text-align: left; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #eef3ff; }}
  tr.buy td {{ border-left: 3px solid #27ae60; background: #f0faf0; }}
  tr.sell td {{ border-left: 3px solid #e74c3c; background: #fef0f0; }}
  .chart {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin: 12px 0; }}
  .bars {{ display: flex; align-items: flex-end; height: 250px; gap: 1px; }}
  .bar {{ flex: 1; min-width: 3px; background: linear-gradient(to top, #1565C0, #64b5f6); border-radius: 2px 2px 0 0; cursor: pointer; }}
  .bar.red {{ background: linear-gradient(to top, #e53935, #ef9a9a); }}
  .tabs {{ display: flex; gap: 2px; margin: 12px 0; }}
  .tab {{ padding: 8px 18px; background: #e0e0e0; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.85em; user-select: none; }}
  .tab.active {{ background: white; font-weight: 600; border-bottom: 2px solid #1565C0; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .scroll {{ max-height: 520px; overflow-y: auto; }}
  .info {{ background: #e3f2fd; border-radius: 8px; padding: 12px 16px; margin: 12px 0; font-size: 0.85em; }}
  .info strong {{ color: #1565C0; }}
  .disclaimer {{ background: #fff3e0; padding: 16px; border-radius: 10px; margin-top: 32px; font-size: 0.85em; color: #e65100; }}
</style>
</head>
<body>

<h1>📊 2026 YTD Trading Journal — REALISTIC</h1>
<p class="meta">Kronos-TH Thai Equity | Strategy: Equal-weight top-5 | 100-share lots | Friction: {oneway*100:.2f}%/side | Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}</p>

<div class="info">
<strong>What's displayed:</strong>
<ul style="margin:4px 0">
<li><strong>Equity curve:</strong> From the actual backtest engine (continuous sizing, net of friction)</li>
<li><strong>Trade lots:</strong> Each trade shows 100-share rounded quantity for reference</li>
<li><strong>Friction:</strong> Commission {frict['commission_oneway']:.4f} + slippage {frict['slippage_oneway']:.4f} = {oneway:.4f} per side (displayed per trade)</li>
</ul>
</div>

<div class="summary">
  <div class="card"><div class="lbl">Start</div><div class="val">{cap:,}</div></div>
  <div class="card"><div class="lbl">Final</div><div class="val {'green' if eq_thb.iloc[-1] > cap else 'red'}">{eq_thb.iloc[-1]:,.0f}</div></div>
  <div class="card"><div class="lbl">P&L</div><div class="val {'green' if eq_thb.iloc[-1] > cap else 'red'}">{eq_thb.iloc[-1] - cap:+,.0f}</div></div>
  <div class="card"><div class="lbl">Return</div><div class="val {'green' if m['total_return'] > 0 else 'red'}">{m['total_return']:+.2%}</div></div>
  <div class="card"><div class="lbl">Sharpe</div><div class="val {'green' if m['sharpe'] > 1 else 'red'}">{m['sharpe']:.2f}</div></div>
  <div class="card"><div class="lbl">Max DD</div><div class="val red">{m['max_drawdown']:.2%}</div></div>
</div>

<div class="summary">
  <div class="card"><div class="lbl">Trades</div><div class="val">{len(trades)}</div></div>
  <div class="card"><div class="lbl">Win Rate</div><div class="val">{m['trade_win_rate']:.1%}</div></div>
  <div class="card"><div class="lbl">Total Friction</div><div class="val red">{total_friction_thb:,.0f} THB</div></div>
  <div class="card"><div class="lbl">Total P&L (Gross)</div><div class="val {'green' if total_pnl > 0 else 'red'}">{total_pnl:+,.0f}</div></div>
  <div class="card"><div class="lbl">CAGR</div><div class="val green">{m['cagr']:+.2%}</div></div>
</div>

<h2>📈 Equity Curve (Net of Friction)</h2>
<div class="chart">
<div class="bars">
"""

for i in range(0, len(eq_n), bar_step):
    h = eq_n[i] * 230
    is_down = i > 0 and eq_thb.iloc[i] < eq_thb.iloc[max(0, i-3)]
    html += f"  <div class='bar{' red' if is_down else ''}' style='height:{max(h, 2):.0f}px' title='{eq_thb.index[i].strftime('%Y-%m-%d')}: {eq_thb.iloc[i]:,.0f}'></div>\n"

html += """</div>
</div>

<h2>📆 Monthly</h2>
<table>
<thead><tr><th>Month</th><th>Value</th><th>Return</th></tr></thead>
<tbody>
"""
pv = cap
for i in range(len(monthly)):
    v = monthly.iloc[i]
    r = (v / pv) - 1
    cl = "green" if r > 0 else "red"
    html += f"  <tr><td>{monthly.index[i].strftime('%Y-%m')}</td><td align='right'>{v:,.0f}</td><td align='right' class='{cl}'>{r:+.2%}</td></tr>\n"
    pv = v

html += f"""  <tr><td><strong>Final</strong></td><td align='right'><strong>{eq_thb.iloc[-1]:,.0f}</strong></td><td align='right' class="{'green' if m['total_return'] > 0 else 'red'}"><strong>{m['total_return']:+.2%}</strong></td></tr>
</tbody></table>

<div class="tabs">
  <div class="tab active" onclick="showTab('trades')">📋 All Trades</div>
  <div class="tab" onclick="showTab('daily')">📅 Portfolio</div>
</div>

<div id="tab-trades" class="tab-content active">
<div class="scroll">
<table>
<thead><tr><th>Date</th><th>Ticker</th><th>Dir</th><th>Shares (lot)</th><th>Price</th><th>THB</th><th>Friction</th><th>Return</th></tr></thead>
<tbody>
"""

html += "\n".join(trade_rows)
html += """
</tbody></table>
</div>
</div>

<div id="tab-daily" class="tab-content">
<div class="scroll">
<table>
<thead><tr><th>Date</th><th>Portfolio (THB)</th></tr></thead>
<tbody>
"""
html += "\n".join(pv_rows)
html += """
</tbody></table>
</div>
</div>

<div class="disclaimer">
<strong>⚠️ Disclaimer:</strong> This is a backtest simulation. Lot sizes are approximate (prices from cached data).
Past performance does not guarantee future results. Not financial advice.
</div>

<script>
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}
</script>
</body>
</html>
"""

out = Path("reports/2026_ytd_trading_journal_realistic.html")
out.write_text(html)
print(f"Saved: {out} ({len(html):,} bytes)")
print(f"Capital: {cap:,} THB")
print(f"Final:   {eq_thb.iloc[-1]:,.0f} THB")
print(f"P&L:     {eq_thb.iloc[-1] - cap:+,.0f} THB ({m['total_return']:+.2%})")
print(f"Friction: {total_friction_thb:,.0f} THB total")
print(f"Trades:  {len(trades)}")
