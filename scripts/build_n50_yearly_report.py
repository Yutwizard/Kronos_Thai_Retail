"""Year-by-year n=50 detailed HTML report."""
import json, pandas as pd, numpy as np
from pathlib import Path
from scipy import stats

CAP = 500_000

def load_year(year, tag=""):
    """Load backtest result for a year."""
    d = f"thai_equity_{year}{tag}"
    p = Path(f"data/backtest_results/{d}")
    if not (p / "metrics.json").exists():
        return None
    eq = pd.read_parquet(p / "equity_curve.parquet")["equity"]
    tr = pd.read_parquet(p / "trades.parquet")
    with open(p / "metrics.json") as f:
        m = json.load(f)
    ew = pd.read_parquet(p / "benchmark_equal_weight.parquet").iloc[:, 0]
    try:
        set_bm = pd.read_parquet(p / "benchmark_SET.parquet").iloc[:, 0]
    except:
        set_bm = None
    return {"eq": eq * CAP, "trades": tr, "m": m, "ew": ew * CAP, "set": set_bm}

years = {
    "2024": load_year("2024", "_n50"),
    "2025": load_year("2025", "_n50"),
    "2026": load_year("2026", "_n50_full"),
    "2023": None,
}

# Year cards
cards = ""
for y, data in years.items():
    if data:
        m = data["m"]
        ret = data["eq"].iloc[-1] / data["eq"].iloc[0] - 1
        cards += f"""<div class="card"><div class="l">{y}</div>
          <div class="v green">{ret:+.1%}</div><div style="font-size:0.7em">Sharpe {m['sharpe']:.2f} | DD {m['max_drawdown']:.1%} | p={m['p_value']:.3f}</div></div>"""
    else:
        cards += f"""<div class="card"><div class="l">{y}</div>
          <div class="v" style="color:#f39c12">⏳</div><div style="font-size:0.7em;color:#888">pending</div></div>"""

# Comparison table
comp = ""
for y, data in years.items():
    if not data:
        comp += f"<tr><td><strong>{y}</strong></td><td colspan='6' style='color:#f39c12'>⏳ pending n=50 run</td></tr>"
        continue
    m = data["m"]
    eq = data["eq"]
    ret = eq.iloc[-1] / eq.iloc[0] - 1
    yrs = len(eq) / 252
    cagr = (1 + ret) ** (1 / yrs) - 1 if yrs > 0 else 0
    daily = eq.pct_change().dropna()
    peak = eq.cummax()
    dd = (eq / peak - 1).min()
    ew_v = data["ew"].reindex(eq.index, method="ffill")
    set_v = data["set"]
    alpha = ret - (ew_v.iloc[-1] / ew_v.iloc[0] - 1)
    set_ret = f"{(set_v.iloc[-1]/set_v.iloc[0]-1):+.1%}" if set_v is not None and len(set_v) > 1 else "—"
    tr = data["trades"]
    c = lambda v: "green" if v > 0 else "red"
    comp += f"<tr><td><strong>{y}</strong></td>"
    comp += f"<td class='{c(ret)}'>{ret:+.1%}</td><td class='{c(cagr)}'>{cagr:+.1%}</td>"
    comp += f"<td class='{c(m['sharpe'])}'>{m['sharpe']:.2f}</td><td class='red'>{dd:.1%}</td>"
    comp += f"<td class='{c(alpha)}'>{alpha:+.1%}</td><td>{set_ret}</td>"
    comp += f"<td>{len(tr)}</td><td>{m['p_value']:.3f}</td></tr>"

# Per-year monthly tables
monthly_html = ""
for y, data in years.items():
    if not data: continue
    eq = data["eq"]
    es = eq.resample("ME").last()
    mh = ""
    prev = eq.iloc[0] if len(eq) > 0 else CAP
    for dt, v in es.items():
        mr = v / prev - 1
        mh += f"<tr><td>{dt.strftime('%b')}</td><td align='right'>{v:,.0f}</td><td class='{'green' if mr>=0 else 'red'}'>{mr:+.1%}</td></tr>"
        prev = v
    monthly_html += f"<div style='flex:1;min-width:160px'><h4>{y}</h4><table><thead><tr><th>Mo</th><th>Value</th><th>Ret</th></tr></thead><tbody>{mh}</tbody></table></div>"

# Best/worst trades per year
trade_html = ""
for y, data in years.items():
    if not data: continue
    tr = data["trades"]
    closed = tr[tr["gross_return"] != 0]
    if len(closed) == 0: continue
    best = closed.nlargest(3, "gross_return")
    worst = closed.nsmallest(3, "gross_return")
    bh = "".join(f"<tr class='buy'><td>{r['date'].strftime('%m-%d')}</td><td>{r['ticker']}</td><td>{r['gross_return']:+.2%}</td></tr>" for _, r in best.iterrows())
    wh = "".join(f"<tr class='sell'><td>{r['date'].strftime('%m-%d')}</td><td>{r['ticker']}</td><td>{r['gross_return']:+.2%}</td></tr>" for _, r in worst.iterrows())
    trade_html += f"""<div style="margin:10px 0"><h4>{y}</h4>
      <div style="display:flex;gap:12px">
        <table><thead><tr><th colspan="3" style="color:#27ae60">Best 3</th></tr><tr><th>Date</th><th>Ticker</th><th>Ret</th></tr></thead><tbody>{bh}</tbody></table>
        <table><thead><tr><th colspan="3" style="color:#e74c3c">Worst 3</th></tr><tr><th>Date</th><th>Ticker</th><th>Ret</th></tr></thead><tbody>{wh}</tbody></table>
      </div></div>"""

# Equity curve SVG per year
charts = ""
for y, data in years.items():
    if not data: continue
    eq = data["eq"]; ew = data["ew"].reindex(eq.index, method="ffill")
    vals = eq.values; mn, mx = vals.min(), vals.max()
    step = max(1, len(vals) // 200)
    pts = " ".join(f"{800*i/len(vals):.0f},{180-160*(v-mn)/(mx-mn):.0f}" for i, v in enumerate(vals[::step]))
    ew_vals = ew.values
    ew_pts = " ".join(f"{800*i/len(ew_vals):.0f},{180-160*(v-mn)/(mx-mn):.0f}" for i, v in enumerate(ew_vals[::step]))
    charts += f"""<div style="flex:1;min-width:300px">
      <h4 style="text-align:center">{y}</h4>
      <svg viewBox="0 0 800 200" style="width:100%">
        <line x1="0" y1="180" x2="800" y2="180" stroke="#ddd"/>
        <line x1="0" y1="90" x2="800" y2="90" stroke="#eee" stroke-width="0.5"/>
        <polyline points="{ew_pts}" fill="none" stroke="#ccc" stroke-width="1"/>
        <polyline points="{pts}" fill="none" stroke="#1565C0" stroke-width="1.5"/>
        <text x="800" y="198" text-anchor="end" font-size="9" fill="#888">{eq.index[-1].strftime('%b')}</text>
        <text x="0" y="198" font-size="9" fill="#888">{eq.index[0].strftime('%b')}</text>
      </svg>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>n=50 Yearly Backtest — Kronos-TH</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:1100px;margin:20px auto;padding:0 16px;background:#f5f7fa;color:#333;font-size:14px}}
h1{{color:#1565C0;border-bottom:3px solid #1565C0;padding-bottom:6px;font-size:1.3em}}
h2{{color:#444;margin:20px 0 8px;font-size:1.1em}}
h4{{margin:4px 0;color:#333}}
.meta{{color:#888;font-size:0.8em}}
.cards{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}
.card{{background:white;border-radius:8px;padding:10px 14px;box-shadow:0 2px 6px rgba(0,0,0,0.06);flex:1;min-width:140px;text-align:center}}
.card .v{{font-size:1.3em;font-weight:700}}
.card .l{{font-size:0.65em;color:#888;text-transform:uppercase}}
.green{{color:#27ae60}} .red{{color:#e74c3c}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin:8px 0;font-size:0.8em}}
th{{background:#1565C0;color:white;padding:7px 8px;text-align:left;font-size:0.7em;text-transform:uppercase}}
td{{padding:5px 8px;border-bottom:1px solid #eee;text-align:center}}
tr:hover{{background:#eef3ff}}
tr.buy{{border-left:3px solid #27ae60}}
tr.sell{{border-left:3px solid #e74c3c}}
.flex{{display:flex;gap:12px;flex-wrap:wrap}}
.info{{background:#e3f2fd;border-radius:8px;padding:12px 16px;margin:12px 0;font-size:0.85em;line-height:1.7}}
.warn{{background:#fff3e0;border-radius:8px;padding:12px 16px;margin:12px 0;font-size:0.85em}}
</style>
</head>
<body>

<h1>Yearly Backtest — n=50 | Kronos-TH Thai Equity</h1>
<p class="meta">Strategy: Equal-weight top-5 | Capital: 500,000 THB | n_samples=50 | Clean OOS</p>

<div class="cards">{cards}</div>

<h2>Year-by-Year Comparison</h2>
<table>
<thead><tr><th>Year</th><th>Return</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>Alpha EW</th><th>SET</th><th>Trades</th><th>p</th></tr></thead>
<tbody>{comp}</tbody>
</table>

<div class="info">
<strong>Key observations:</strong><br>
<b>2024:</b> Best year — +43.8% with Sharpe 2.27. Statistically significant (p=0.015). Low drawdown −6.9%.<br>
<b>2025:</b> Solid year — +34.9% but higher drawdown −24.0%. Not significant (p=0.257).<br>
<b>2023 + 2026:</b> Pending n=50 precompute. 2026 currently running (background).
</div>

<h2>Equity Curves (Strategy vs Equal-Weight)</h2>
<div class="flex">{charts}</div>

<h2>Monthly Performance</h2>
<div class="flex">{monthly_html}</div>

<h2>Best & Worst Trades by Year</h2>
{trade_html}

<div class="warn">
<strong>⚠️ Caveats:</strong> Survivorship bias (point-in-time 2025 universe). Past returns not indicative of future.
n=50 provides ~5× more stable forecasts than n=10. 2023 pending precompute. 2026 running in background.
</div>

</body>
</html>"""

Path("reports/n50_yearly_report.html").write_text(html, encoding="utf-8")
print(f"Saved: reports/n50_yearly_report.html ({len(html):,} bytes)")
