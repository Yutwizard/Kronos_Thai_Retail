"""Weekly allocation band report based on rolling 12-week Sharpe."""
import json, pandas as pd, numpy as np
from pathlib import Path

def rolling_sharpe(returns, window=60):
    """12-week rolling Sharpe (60 trading days)."""
    return (returns.rolling(window).mean() / returns.rolling(window).std() * np.sqrt(252)).dropna()

def allocation_band(sharpe):
    """Immediate mechanical rule: no buffers, no delays."""
    if sharpe > 1.0: return 0.15, "bull"
    if sharpe > 0.5: return 0.10, "neutral"
    if sharpe > 0.0: return 0.05, "bear"
    return 0.0, "exit"

# ── Load data ──
data = {}
for y, d in [("2024", "thai_equity_2024_n50"), ("2025", "thai_equity_2025_n50")]:
    p = Path(f"data/backtest_results/{d}")
    if not (p / "metrics.json").exists(): continue
    eq = pd.read_parquet(p / "equity_curve.parquet")["equity"]
    data[y] = eq * 500_000

# ── Compute weekly allocation bands ──
CAP = 500_000
charts = ""
for y, eq in data.items():
    daily = eq.pct_change().dropna()
    weekly_dates = pd.date_range(eq.index[0], eq.index[-1], freq="W-FRI")
    weekly_dates = weekly_dates[weekly_dates >= daily.index[0]]
    
    # Get Sharpe at each weekly check (using Friday's last available data)
    weekly_rows = ""
    for dt in weekly_dates:
        # Find closest date <= dt
        mask = daily.index <= dt
        if not mask.any(): continue
        cutoff = daily.index[mask][-1]
        hist = daily.loc[:cutoff].tail(60)
        if len(hist) < 20: continue  # need at least 20 days
        
        sh = hist.mean() / hist.std() * np.sqrt(252) if hist.std() > 0 else 0
        alloc, band = allocation_band(sh)
        port_val = eq.loc[cutoff]
        
        cls = "green" if band == "bull" else ("orange" if band == "neutral" else "red")
        weekly_rows += f"""<tr>
          <td>{dt.strftime('%Y-%m-%d')}</td>
          <td align='right'>{port_val:,.0f}</td>
          <td align='right'>{sh:.2f}</td>
          <td class='{cls}'>{alloc:.0%}</td>
          <td class='{cls}'>{band.upper()}</td></tr>"""

    # Compute allocation for every day for chart overlay
    alloc_series = pd.Series(index=daily.index, dtype=float)
    for i in range(60, len(daily)):
        hist = daily.iloc[i-60:i]
        sh = hist.mean() / hist.std() * np.sqrt(252) if hist.std() > 0 else 0
        alloc, _ = allocation_band(sh)
        alloc_series.iloc[i] = alloc * 100  # percentage points
    
    # Chart SVG
    eq_vals = eq.values
    mn, mx = eq_vals.min(), eq_vals.max()
    step = max(1, len(eq_vals) // 300)
    eq_pts = " ".join(f"{800*i/len(eq_vals):.0f},{200-160*(v-mn)/(mx-mn):.0f}" for i, v in enumerate(eq_vals[::step]))
    
    alloc_vals = alloc_series.dropna().values
    ai = alloc_series.dropna().index
    alloc_pts = ""
    for i in range(0, len(alloc_vals), step):
        x = 800 * (list(eq.index).index(ai[i])) / len(eq_vals)
        y = 200 - 30 * alloc_vals[i]  # map 0-15% to y space
        alloc_pts += f"{x:.0f},{y:.0f} "

    charts += f"""<div style="flex:1;min-width:400px">
      <h3 style="text-align:center">{y} — Allocation Bands (12-week rolling Sharpe)</h3>
      <svg viewBox="0 0 800 240" style="width:100%">
        <rect x="0" y="0" width="800" height="15" fill="#27ae60" opacity="0.1"/>
        <text x="800" y="12" text-anchor="end" font-size="8" fill="#27ae60">15% BULL</text>
        <rect x="0" y="15" width="800" height="15" fill="#f39c12" opacity="0.1"/>
        <text x="800" y="27" text-anchor="end" font-size="8" fill="#f39c12">10% NEUTRAL</text>
        <rect x="0" y="30" width="800" height="15" fill="#e74c3c" opacity="0.1"/>
        <text x="800" y="42" text-anchor="end" font-size="8" fill="#e74c3c">5% BEAR</text>
        <line x1="0" y1="200" x2="800" y2="200" stroke="#ddd"/>
        <polyline points="{eq_pts}" fill="none" stroke="#1565C0" stroke-width="1.5"/>
        <polyline points="{alloc_pts}" fill="none" stroke="#e74c3c" stroke-width="0.5" stroke-dasharray="4,2"/>
        <text x="800" y="238" text-anchor="end" font-size="8" fill="#888">{eq.index[-1].strftime('%b')}</text>
        <text x="0" y="238" font-size="8" fill="#888">{eq.index[0].strftime('%b')}</text>
        <line x1="700" y1="10" x2="720" y2="10" stroke="#1565C0" stroke-width="1.5"/>
        <text x="725" y="14" font-size="7" fill="#666">Equity</text>
        <line x1="700" y1="22" x2="720" y2="22" stroke="#e74c3c" stroke-width="0.5" stroke-dasharray="4,2"/>
        <text x="725" y="26" font-size="7" fill="#666">Allocation %</text>
      </svg>
      <div style="max-height:300px;overflow-y:auto;margin-top:8px">
      <table>
        <thead><tr><th>Check Date (Fri)</th><th>Portfolio</th><th>12wk Sharpe</th><th>Target</th><th>Band</th></tr></thead>
        <tbody>{weekly_rows}</tbody>
      </table>
      </div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>Weekly Allocation Bands — Kronos-TH</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:1100px;margin:20px auto;padding:0 16px;background:#f5f7fa;color:#333;font-size:14px}}
h1{{color:#1565C0;border-bottom:3px solid #1565C0;padding-bottom:6px;font-size:1.3em}}
h2,h3{{color:#444;margin:16px 0 8px}}
.flex{{display:flex;gap:16px;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.06);font-size:0.78em;margin:4px 0}}
th{{background:#1565C0;color:white;padding:5px 8px;text-align:center;font-size:0.68em;text-transform:uppercase}}
td{{padding:4px 8px;text-align:center;border-bottom:1px solid #eee}}
tr:hover{{background:#eef3ff}}
.green{{color:#27ae60;font-weight:600}}
.orange{{color:#f39c12;font-weight:600}}
.red{{color:#e74c3c;font-weight:600}}
.rules{{background:white;border-radius:8px;padding:14px 18px;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin:8px 0;font-size:0.85em}}
.rules h3{{margin:0 0 8px;color:#1565C0}}
.rules table{{font-size:0.85em;margin:8px 0}}
.info{{background:#e3f2fd;border-radius:8px;padding:12px 16px;margin:12px 0;font-size:0.85em}}
</style>
</head>
<body>

<h1>Weekly Allocation Bands — Kronos-TH Thai Equity</h1>
<p style="color:#888;font-size:0.85em">Mechanical rule: Every Friday, check 12-week rolling Sharpe → adjust allocation immediately. No buffers.</p>

<div class="rules">
<h3>Allocation Rules</h3>
<table>
<tr><th>12-Week Rolling Sharpe</th><th>Target Allocation</th><th>Band</th><th>Action</th></tr>
<tr><td class="green">&gt; 1.0</td><td class="green">15%</td><td class="green">BULL</td><td>Full conviction — allocate aggressively</td></tr>
<tr><td class="orange">0.5 – 1.0</td><td class="orange">10%</td><td class="orange">NEUTRAL</td><td>Baseline — maintain steady allocation</td></tr>
<tr><td class="red">0.0 – 0.5</td><td class="red">5%</td><td class="red">BEAR</td><td>Caution — reduce exposure</td></tr>
<tr><td class="red">&lt; 0.0</td><td class="red">0%</td><td class="red">EXIT</td><td>Negative Sharpe — go to cash</td></tr>
</table>
<div style="font-size:0.8em;margin-top:4px;color:#888">
<strong>Monitoring:</strong> Every Friday (or last trading day of the week).<br>
<strong>Execution:</strong> Next trading day (usually Monday).<br>
<strong>Capital base:</strong> Total portfolio (e.g., 500,000 THB total → 5% = 25,000, 15% = 75,000 allocated to strategy).
</div>
</div>

<h2>Historical Allocation Timeline</h2>
<div class="flex">{charts}</div>

<div class="info">
<strong>How to use this weekly:</strong><br>
1. Every Friday, run <code>venv/bin/python scripts/run_daily_report.py</code> to get the latest model signals.<br>
2. Compute the 12-week Sharpe from your portfolio tracker (or use the backtest equity curve).<br>
3. Check the table above for your target allocation band.<br>
4. Rebalance on Monday: adjust position sizes to match the target % of your total portfolio.<br>
5. The model still picks the stocks (top-5 equal weight) — this only controls HOW MUCH capital is deployed.
</div>

</body>
</html>"""

Path("reports/weekly_allocation_bands.html").write_text(html, encoding="utf-8")
print(f"Saved: reports/weekly_allocation_bands.html ({len(html):,} bytes)")
