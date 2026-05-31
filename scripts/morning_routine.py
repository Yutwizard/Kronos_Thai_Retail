"""Morning routine: download data → forecast → risk check → HTML report."""
import subprocess, sys, time, json, os
from pathlib import Path
from datetime import date, datetime
import pandas as pd, numpy as np

os.environ['HF_HUB_OFFLINE'] = '1'
today = date.today()

# Step 1: Download fresh data
print(f"[1/3] Downloading data...", flush=True)
subprocess.run([sys.executable, "scripts/download_data.py"], capture_output=True)

# Step 2: Import + forecast
print(f"[2/3] Generating forecasts...", flush=True)
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached

tickers = [t for t, _, _ in UNIVERSE['thai_equity']]
ticker_names = {t: n for t, n, _ in UNIVERSE['thai_equity']}

k = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
fc = k.forecast_batch(tickers, pred_lens=[20], n_samples=50)

# Step 3: Rank + risk check
print(f"[3/3] Computing rankings + risk...", flush=True)
ranked = []
for t, r in fc.items():
    try:
        df = load_cached(t)
        price = float(df['close'].iloc[-1])
    except:
        price = 0
    p50 = r.horizons[20].summary['p50'].iloc[-1]
    exp_ret = (p50 / price - 1) if price > 0 else 0
    ranked.append({'ticker': t, 'price': price, 'exp_ret': exp_ret})
ranked.sort(key=lambda x: x['exp_ret'], reverse=True)

# Risk controls from latest backtest
alloc = 0.10; sh = 0; dd = 0; stopped = False
try:
    for y in ['2025', '2024']:
        p = Path(f'data/backtest_results/thai_equity_{y}_n50')
        if (p / 'equity_curve.parquet').exists():
            eq = pd.read_parquet(p / 'equity_curve.parquet')['equity']
            daily = eq.pct_change().dropna()
            hist = daily.tail(60)
            if len(hist) >= 20 and hist.std() > 0:
                sh = hist.mean() / hist.std() * np.sqrt(252)
            alloc = 0.15 if sh > 1 else (0.10 if sh > 0.5 else (0.05 if sh > 0 else 0))
            peak = eq.cummax().iloc[-1]
            dd = eq.iloc[-1] / peak - 1
            stopped = dd <= -0.10
            break
except: pass

final_alloc = 0 if stopped else alloc
band = "CASH (stopped)" if stopped else ("BULL 15%" if sh > 1 else ("NEUTRAL 10%" if sh > 0.5 else ("BEAR 5%" if sh > 0 else "EXIT 0%")))

# Trade plan
CAP = 500000
top5 = ranked[:5]
bottom5 = ranked[-5:]
per_pos = CAP * final_alloc / 5 if final_alloc > 0 else 0

# Build trade rows
trade_rows = ""
for r in top5:
    lots = int(per_pos / r['price'] / 100) * 100 if r['price'] > 0 and per_pos > 0 else 0
    thb = lots * r['price']
    cl = "green" if r['exp_ret'] > 0.02 else ("orange" if r['exp_ret'] > 0.01 else "red")
    trade_rows += f"""<tr class='{cl}'>
      <td>{r['ticker']}</td><td style='font-size:0.8em;color:#666'>{ticker_names.get(r['ticker'],'')}</td>
      <td align='right'>{r['price']:.2f}</td>
      <td align='right' class='{'green' if r['exp_ret']>0 else 'red'}'>{r['exp_ret']:+.2%}</td>
      <td align='right'>{lots:,.0f}</td><td align='right'>{thb:,.0f}</td></tr>"""

avoid_rows = ""
for r in bottom5:
    avoid_rows += f"<tr class='red'><td>{r['ticker']}</td><td style='font-size:0.8em;color:#666'>{ticker_names.get(r['ticker'],'')}</td><td align='right'>{r['price']:.2f}</td><td align='right' class='red'>{r['exp_ret']:+.2%}</td></tr>"

# Full ranking rows
rank_rows = ""
for i, r in enumerate(ranked):
    cl = "green" if r['exp_ret'] > 0.02 else ("orange" if r['exp_ret'] > 0.01 else "red")
    rank_rows += f"<tr class='{cl}'><td>{i+1}</td><td>{r['ticker']}</td><td style='font-size:0.8em;color:#666'>{ticker_names.get(r['ticker'],'')}</td><td align='right'>{r['price']:.2f}</td><td align='right'>{r['exp_ret']:+.2%}</td></tr>"

stop_cls = "red" if stopped else "green"
allocs_cls = "green" if sh > 1 else ("orange" if sh > 0.5 else "red")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>Daily Brief — Kronos-TH — {today}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:800px;margin:20px auto;padding:0 16px;background:#f5f7fa;color:#333;font-size:14px}}
h1{{color:#1565C0;border-bottom:2px solid #1565C0;padding-bottom:4px;font-size:1.2em}}
h2{{color:#444;margin:16px 0 8px;font-size:1em}}
.meta{{color:#888;font-size:0.8em}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:6px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin:6px 0;font-size:0.8em}}
th{{background:#1565C0;color:white;padding:5px 8px;text-align:left;font-size:0.7em;text-transform:uppercase}}
td{{padding:4px 8px;border-bottom:1px solid #eee}}
tr:hover{{background:#eef3ff}}
tr.green{{border-left:3px solid #27ae60}}
tr.orange{{border-left:3px solid #f39c12}}
tr.red{{border-left:3px solid #e74c3c}}
.green{{color:#27ae60}}.red{{color:#e74c3c}}.orange{{color:#f39c12}}
.controls{{display:flex;gap:10px;margin:8px 0}}
.ctl{{background:white;border-radius:6px;padding:8px 12px;box-shadow:0 2px 4px rgba(0,0,0,0.04);flex:1;text-align:center}}
.ctl .v{{font-size:1.2em;font-weight:700}}
.ctl .l{{font-size:0.62em;color:#888;text-transform:uppercase;letter-spacing:0.3px}}
.summary{{background:white;border-radius:8px;padding:12px 16px;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin:8px 0;font-size:0.85em}}
.summary code{{background:#e3f2fd;padding:2px 6px;border-radius:3px;font-size:0.9em}}
</style>
</head>
<body>

<h1>📊 Daily Brief — {today}</h1>
<p class="meta">Kronos-TH Thai Equity | Top-5 Equal Weight | n_samples=50 | Generated: {datetime.now().strftime('%H:%M')}</p>

<div class="controls">
  <div class="ctl"><div class="l">Allocation Band</div><div class="v {allocs_cls}">{final_alloc:.0%}</div><div style="font-size:0.7em;color:#888">{band}</div></div>
  <div class="ctl"><div class="l">12-Week Sharpe</div><div class="v {'green' if sh>1 else ('orange' if sh>0.5 else 'red')}">{sh:.2f}</div></div>
  <div class="ctl"><div class="l">Max Drawdown</div><div class="v {stop_cls}">{dd:+.1%}</div></div>
  <div class="ctl"><div class="l">Stop-Loss (-10%)</div><div class="v {stop_cls}">{'TRIGGERED' if stopped else 'OK'}</div></div>
</div>

<div class="summary">
<strong>Trading plan:</strong> Allocate <code>{final_alloc:.0%}</code> of portfolio ({CAP*final_alloc:,.0f} THB) into {len(top5)} positions.
</div>

<h2>🔝 Top 5 — Buy</h2>
<table><thead><tr><th>Ticker</th><th>Name</th><th>Price</th><th>Exp Ret (20d)</th><th>Shares</th><th>THB</th></tr></thead><tbody>{trade_rows}</tbody></table>

<h2>🔻 Bottom 5 — Avoid</h2>
<table><thead><tr><th>Ticker</th><th>Name</th><th>Price</th><th>Exp Ret (20d)</th></tr></thead><tbody>{avoid_rows}</tbody></table>

<h2>📊 Full Ranking (50 stocks)</h2>
<div style="max-height:400px;overflow-y:auto">
<table><thead><tr><th>#</th><th>Ticker</th><th>Name</th><th>Price</th><th>Exp Ret (20d)</th></tr></thead><tbody>{rank_rows}</tbody></table>
</div>

<p class="meta" style="margin-top:20px">Not financial advice. Past performance does not guarantee future results.</p>

</body>
</html>"""

# Save
Path("reports").mkdir(exist_ok=True)
report_path = Path(f"reports/{today}_daily_brief.html")
report_path.write_text(html, encoding="utf-8")
print(f"Saved: {report_path}")

# Also save to logs
Path("data/logs").mkdir(exist_ok=True)
Path(f"data/logs/morning_{today}.log").write_text(
    f"MORNING ROUTINE {today}\n"
    f"Allocation: {final_alloc:.0%} | Sharpe: {sh:.2f} | DD: {dd:+.1%} | Stop: {stopped}\n"
    f"\nTop 5 Buy:\n" + "\n".join(f"  {r['ticker']:<12} {r['exp_ret']:+.2%}" for r in top5) +
    f"\n\nBottom 5 Avoid:\n" + "\n".join(f"  {r['ticker']:<12} {r['exp_ret']:+.2%}" for r in bottom5)
)
