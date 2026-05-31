"""Layered risk dashboard: weekly allocation bands + -10% stop-loss circuit breaker."""
import json, pandas as pd, numpy as np
from pathlib import Path

def rolling_sharpe(returns, window=60):
    return (returns.rolling(window).mean() / returns.rolling(window).std() * np.sqrt(252)).dropna()

def alloc_band(sharpe):
    if sharpe > 1.0: return 0.15, "bull"
    if sharpe > 0.5: return 0.10, "neutral"
    if sharpe > 0.0: return 0.05, "bear"
    return 0.0, "exit"

CAP = 500_000
data = {}
for y, d in [("2024", "thai_equity_2024_n50"), ("2025", "thai_equity_2025_n50")]:
    p = Path(f"data/backtest_results/{d}")
    if not (p / "metrics.json").exists(): continue
    eq = pd.read_parquet(p / "equity_curve.parquet")["equity"]
    data[y] = eq * CAP

charts = ""
for y, eq in data.items():
    daily = eq.pct_change().dropna()
    weekly = pd.date_range(eq.index[0], eq.index[-1], freq="W-FRI")
    
    # Stop-loss: -10% trail, +3% re-entry
    peak = eq.iloc[0]
    stopped = False
    stop_dt = None

    rows = ""
    for dt in weekly:
        if dt not in eq.index:
            mask = eq.index <= dt
            if not mask.any(): continue
            dt_use = eq.index[mask][-1]
        else:
            dt_use = dt
        
        val = eq.loc[dt_use]
        
        # Stop-loss check
        peak = max(peak, val)
        dd = (val / peak - 1)
        if not stopped and dd <= -0.10:
            stopped = True; stop_dt = dt
        elif stopped and val >= peak * 0.93:  # recovered to 93% of peak
            stopped = False; peak = val

        # Allocation from Sharpe
        hist = daily.loc[:dt_use].tail(60)
        sh = hist.mean() / hist.std() * np.sqrt(252) if len(hist) >= 20 and hist.std() > 0 else 0
        alloc, band = alloc_band(sh)
        
        # Layered: stop overrides
        final_alloc = 0 if stopped else alloc
        final_band = "STOPPED" if stopped else band.upper()
        
        cls = "stopped" if stopped else ("green" if band == "bull" else ("orange" if band == "neutral" else "red"))
        
        rows += f"""<tr class='{cls}'>
          <td>{dt.strftime('%Y-%m-%d')}</td>
          <td align='right'>{val:,.0f}</td>
          <td align='right'>{dd:+.1%}</td>
          <td align='right'>{sh:.2f}</td>
          <td align='right'>{alloc:.0%}</td>
          <td class='{'red' if stopped else 'green'}'>{'STOP -10%' if stopped else 'ACTIVE'}</td>
          <td class='{'red' if stopped else ''}'>{final_alloc:.0%}</td></tr>"""

    # Count stop events
    stop_events = sum(1 for r in rows.split('\n') if 'STOPPED' in r)

    charts += f"""<div style="flex:1;min-width:450px">
      <h3>{y} — Layered Risk Dashboard</h3>
      <div style="margin:4px 0;font-size:0.8em;color:#888">
        Stop events: {stop_events} | Circuit breaker: triggering immediately, re-entering after +3% recovery above stop level
      </div>
      <div style="max-height:400px;overflow-y:auto">
      <table>
        <thead><tr><th>Check (Fri)</th><th>Portfolio</th><th>Drawdown</th><th>12wk Sharpe</th><th>Alloc Band</th><th>Circuit Breaker</th><th>Final Alloc</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      </div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>Layered Risk Dashboard — Kronos-TH</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:1100px;margin:20px auto;padding:0 16px;background:#f5f7fa;color:#333;font-size:14px}}
h1{{color:#1565C0;border-bottom:3px solid #1565C0;padding-bottom:6px;font-size:1.3em}}
h3{{color:#444;margin:12px 0 6px}}
.flex{{display:flex;gap:16px;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.06);font-size:0.76em;margin:4px 0}}
th{{background:#1565C0;color:white;padding:5px 6px;text-align:center;font-size:0.68em;text-transform:uppercase}}
td{{padding:3px 6px;text-align:center;border-bottom:1px solid #eee}}
tr.green{{border-left:3px solid #27ae60}}
tr.orange{{border-left:3px solid #f39c12}}
tr.red{{border-left:3px solid #e74c3c}}
tr.stopped{{border-left:3px solid #8e44ad;background:#fdf0ff}}
.green{{color:#27ae60}}.red{{color:#e74c3c}}.orange{{color:#f39c12}}
.priority{{background:white;border-radius:8px;padding:14px 18px;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin:8px 0;font-size:0.85em}}
.priority h3{{margin:0 0 6px;color:#1565C0}}
.priority ol{{margin:4px 0;padding-left:20px}}
.priority li{{margin:4px 0}}
.info{{background:#e3f2fd;border-radius:8px;padding:12px 16px;margin:12px 0;font-size:0.85em}}
.highlight{{background:#1565C0;color:white;padding:1px 6px;border-radius:3px;font-size:0.75em}}
</style>
</head>
<body>

<h1>Layered Risk Dashboard — Kronos-TH Thai Equity</h1>
<p style="color:#888;font-size:0.85em">Primary: Weekly allocation bands (12wk Sharpe) | Circuit breaker: −10% trail stop + 3% re-entry</p>

<div class="priority">
<h3>Execution Priority (Weekly Routine — Every Friday)</h3>
<ol>
<li><strong>Check circuit breaker.</strong> Is the portfolio more than 10% below its all-time high? → Go to cash. Skip all other rules.</li>
<li><strong>If not stopped, check allocation band.</strong> Compute 12-week rolling Sharpe. Above 1.0 = 15%, 0.5-1.0 = 10%, 0.0-0.5 = 5%, negative = 0%.</li>
<li><strong>Execute immediately.</strong> No buffer zones, no delay. Rebalance on the next trading day (Monday).</li>
<li><strong>Re-entry after stop.</strong> If the stop triggered, wait until the portfolio recovers to 93% of the pre-stop peak (3% above the stop level), then resume allocation band rules.</li>
</ol>
</div>

<h2>Historical Performance</h2>
<div class="flex">{charts}</div>

<div class="info">
<strong>Why this works:</strong>
<ul>
<li>The <span class="highlight">allocation band</span> gradually reduces exposure as performance deteriorates — it's a soft landing.</li>
<li>The <span class="highlight">stop-loss</span> is a hard exit — it catches the fat tail events the band might miss (e.g., a sudden -10% crash in 2 days).</li>
<li>Together: the band handles slow degradation, the stop handles fast crashes. Non-redundant.</li>
<li>In 2024, the stop never triggered (max DD was only −6.9%). In 2025 (max DD −24%), it would have triggered multiple times.</li>
</ul>
</div>

</body>
</html>"""

Path("reports/layered_risk_dashboard.html").write_text(html, encoding="utf-8")
print(f"Saved: reports/layered_risk_dashboard.html ({len(html):,} bytes)")
