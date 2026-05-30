"""Generate 2026 YTD trading journal HTML with daily detail."""
import json
import pandas as pd
from pathlib import Path
from datetime import date

result_dir = Path("data/backtest_results/thai_equity_2026_ytd")
trades = pd.read_parquet(result_dir / "trades.parquet")
eq = pd.read_parquet(result_dir / "equity_curve.parquet")["equity"]
daily_ret = pd.read_parquet(result_dir / "daily_returns.parquet")["daily_returns"]
with open(result_dir / "metrics.json") as f:
    m = json.load(f)

cap = 500_000
eq_thb = eq * cap
pnl = eq_thb.iloc[-1] - cap

# Build daily portfolio value series
daily_val = eq_thb.reindex(pd.date_range(eq.index[0], eq.index[-1], freq="D")).ffill()

# Daily trade summary
trades["date"] = pd.to_datetime(trades["date"])
trades["thb"] = trades["size_pct"] * cap
trades["direction"] = trades["direction"].str.upper()

# Compute daily P&L per ticker
trades["pnl_thb"] = trades["gross_return"] * trades["size_pct"] * cap

# Group by date
daily_buys = trades[trades["direction"] == "BUY"].groupby(trades["date"].dt.date).agg(
    buys=("thb", "sum"), buy_count=("thb", "count")
)
daily_sells = trades[trades["direction"] == "SELL"].groupby(trades["date"].dt.date).agg(
    sells=("thb", "sum"), sell_count=("thb", "count"),
    pnl=("pnl_thb", "sum")
)

daily_summary = pd.concat([daily_buys, daily_sells], axis=1).fillna(0)
daily_summary["net"] = daily_summary["sells"] - daily_summary["buys"]

# Trade detail HTML
trade_rows = []
for _, r in trades.iterrows():
    cls = " class='buy'" if r["direction"] == "BUY" else " class='sell'"
    ret = f"{r['gross_return']:.2%}" if r["gross_return"] != 0 else "—"
    trade_rows.append(
        f"  <tr{cls}><td>{r['date'].strftime('%Y-%m-%d')}</td>"
        f"<td>{r['ticker']}</td><td>{r['direction']}</td>"
        f"<td align='right'>{r['thb']:,.0f}</td>"
        f"<td align='right'>{r['friction_cost']:.2f}</td>"
        f"<td align='right'>{ret}</td></tr>"
    )

# Portfolio value rows (show every 5th day to keep it readable)
pv_rows = []
for i, (d, v) in enumerate(daily_val.items()):
    if i % 2 == 0 or i == len(daily_val) - 1:
        pv_rows.append(f"  <tr><td>{d.strftime('%Y-%m-%d')}</td><td align='right'>{v:,.0f}</td></tr>")

# Monthly stats
monthly = eq_thb.resample("ME").last()
monthly_pct = monthly.pct_change()

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>2026 YTD Trading Journal — Kronos-TH</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 1100px; margin: 30px auto; padding: 0 20px; background: #f8f9fa; color: #333; }}
  h1 {{ color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 8px; }}
  h2 {{ color: #444; margin-top: 32px; }}
  .meta {{ color: #666; font-size: 0.9em; }}
  .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
  .card {{ background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 140px; text-align: center; }}
  .card .val {{ font-size: 1.6em; font-weight: 700; margin: 4px 0; }}
  .card .lbl {{ font-size: 0.8em; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
  .green {{ color: #27ae60; }} .red {{ color: #e74c3c; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 12px 0; }}
  th {{ background: #1565C0; color: white; padding: 10px 12px; text-align: left; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }}
  tr:hover {{ background: #f0f4ff; }}
  tr.buy td {{ border-left: 3px solid #27ae60; }}
  tr.sell td {{ border-left: 3px solid #e74c3c; }}
  .chart {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 12px 0; height: 300px; position: relative; }}
  .bar {{ position: absolute; bottom: 20px; width: 100%; left: 0; padding: 0 20px; }}
  .bar-inner {{ display: flex; align-items: flex-end; height: 220px; gap: 2px; }}
  .bar-col {{ flex: 1; min-width: 4px; background: linear-gradient(to top, #1565C0, #42a5f5); border-radius: 2px 2px 0 0; position: relative; }}
  .bar-col:hover {{ background: linear-gradient(to top, #0d47a1, #1565C0); }}
  .disclaimer {{ background: #fff3e0; padding: 16px; border-radius: 8px; margin-top: 32px; font-size: 0.85em; color: #e65100; }}
  .tabs {{ display: flex; gap: 4px; margin: 16px 0; }}
  .tab {{ padding: 8px 20px; background: #e0e0e0; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.9em; }}
  .tab.active {{ background: white; font-weight: 600; border-bottom: 2px solid #1565C0; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .scroll {{ max-height: 500px; overflow-y: auto; }}
</style>
</head>
<body>

<h1>📊 2026 YTD Trading Journal</h1>
<p class="meta">Kronos-TH Thai Equity | Strategy: Equal-weight top-5 | Generated: {date.today()}</p>

<div class="summary">
  <div class="card">
    <div class="lbl">Starting Capital</div>
    <div class="val">{cap:,.0f}</div>
  </div>
  <div class="card">
    <div class="lbl">Final Value</div>
    <div class="val {'green' if pnl > 0 else 'red'}">{eq_thb.iloc[-1]:,.0f}</div>
  </div>
  <div class="card">
    <div class="lbl">Total P&L</div>
    <div class="val {'green' if pnl > 0 else 'red'}">{pnl:+,.0f}</div>
  </div>
  <div class="card">
    <div class="lbl">Return</div>
    <div class="val {'green' if m['total_return'] > 0 else 'red'}">{m['total_return']:+.2%}</div>
  </div>
  <div class="card">
    <div class="lbl">Sharpe</div>
    <div class="val {'green' if m['sharpe'] > 1 else 'red'}">{m['sharpe']:.2f}</div>
  </div>
  <div class="card">
    <div class="lbl">Max DD</div>
    <div class="val red">{m['max_drawdown']:.2%}</div>
  </div>
</div>

<div class="summary">
  <div class="card">
    <div class="lbl">Total Trades</div>
    <div class="val">{len(trades)}</div>
  </div>
  <div class="card">
    <div class="lbl">Win Rate</div>
    <div class="val">{m['trade_win_rate']:.1%}</div>
  </div>
  <div class="card">
    <div class="lbl">Annual Turnover</div>
    <div class="val">{m.get('annual_turnover', 0):.0f}x</div>
  </div>
  <div class="card">
    <div class="lbl">p-value</div>
    <div class="val">{m['p_value']:.3f}</div>
  </div>
  <div class="card">
    <div class="lbl">CAGR</div>
    <div class="val green">{m['cagr']:+.2%}</div>
  </div>
</div>

<h2>📈 Portfolio Value</h2>
<div class="chart" id="equity-chart">
  <div class="bar-inner" style="height:260px;display:flex;align-items:flex-end;gap:1px;">
"""

# Build mini bar chart (sample every nth day)
vals = daily_val.values
min_v, max_v = vals.min(), vals.max()
norm = lambda v: (v - min_v) / (max_v - min_v) if max_v > min_v else 0.5
step = max(1, len(vals) // 200)
for i in range(0, len(vals), step):
    h = norm(vals[i]) * 230
    html += f"    <div class='bar-col' style='height:{h:.0f}px' title='{daily_val.index[i].strftime('%Y-%m-%d')}: {vals[i]:,.0f}'></div>\n"

html += """  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('trades')">📋 All Trades</div>
  <div class="tab" onclick="showTab('daily')">📅 Daily Summary</div>
  <div class="tab" onclick="showTab('monthly')">📆 Monthly</div>
</div>

<div id="tab-trades" class="tab-content active">
<div class="scroll">
<table>
<thead><tr><th>Date</th><th>Ticker</th><th>Dir</th><th>THB</th><th>Friction</th><th>Return</th></tr></thead>
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
<thead><tr><th>Date</th><th>Portfolio Value</th></tr></thead>
<tbody>
"""

html += "\n".join(pv_rows)

html += """
</tbody></table>
</div>
</div>

<div id="tab-monthly" class="tab-content">
<table>
<thead><tr><th>Month</th><th>End Value</th><th>Return</th><th>Trades</th></tr></thead>
<tbody>
"""

prev = cap
for i in range(len(monthly)):
    mv = monthly.iloc[i]
    ret = (mv / prev) - 1
    md = monthly.index[i]
    n_trades = len(trades[(trades["date"] >= prev_date if i > 0 else trades["date"] >= pd.Timestamp("2026-01-01")) & (trades["date"] < md)])
    cls = "green" if ret > 0 else "red"
    html += f"  <tr><td>{md.strftime('%Y-%m')}</td><td align='right'>{mv:,.0f}</td><td align='right' class='{cls}'>{ret:+.2%}</td><td align='right'>{n_trades}</td></tr>\n"
    prev = mv
    prev_date = md

html += f"""
</tbody></table>
</div>

<h2>🏆 Best & Worst Trades</h2>
<table>
<thead><tr><th>Rank</th><th>Date</th><th>Ticker</th><th>Return</th><th>THB</th></tr></thead>
<tbody>
"""

closed = trades[trades["gross_return"] != 0].copy()
closed["pnl"] = closed["gross_return"] * closed["size_pct"] * cap
best = closed.nlargest(5, "gross_return")
worst = closed.nsmallest(5, "gross_return")

for _, r in best.iterrows():
    html += f"  <tr class='buy'><td>WIN</td><td>{r['date'].strftime('%Y-%m-%d')}</td><td>{r['ticker']}</td><td>{r['gross_return']:+.2%}</td><td>{r['pnl']:+,.0f}</td></tr>\n"
for _, r in worst.iterrows():
    html += f"  <tr class='sell'><td>LOSS</td><td>{r['date'].strftime('%Y-%m-%d')}</td><td>{r['ticker']}</td><td>{r['gross_return']:+.2%}</td><td>{r['pnl']:+,.0f}</td></tr>\n"

html += """
</tbody></table>

<div class="disclaimer">
<strong>⚠️ Disclaimer:</strong> This is a backtest simulation using historical data with the Kronos-TH model.
Past performance does not guarantee future results. All figures are in THB. Friction costs are estimated
using per-class commission + slippage rates from the universe definition. The model's forecasts are
statistical predictions, not financial advice.
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

out_path = Path("reports/2026_ytd_trading_journal.html")
out_path.write_text(html)
print(f"Saved: {out_path} ({len(html):,} bytes)")
