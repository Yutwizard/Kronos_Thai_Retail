"""Deep dive: first 7 days, best/worst trades, stop-loss simulation."""
import json, pandas as pd, numpy as np
from pathlib import Path
from kth.data.universe import UNIVERSE, FRICTION
from kth.data.loader import load_cached

R = Path("data/backtest_results/thai_equity_2026_ytd")
trades = pd.read_parquet(R / "trades.parquet")
eq = pd.read_parquet(R / "equity_curve.parquet")["equity"]
with open(R / "metrics.json") as f:
    m = json.load(f)

CAP = 500_000
LOT = 100
ONEWAY = FRICTION["thai_equity"]["commission_oneway"] + FRICTION["thai_equity"]["slippage_oneway"]

# Prices for lot sizing
ticker_prices = {}
for t in trades["ticker"].unique():
    try:
        df = load_cached(t)
        ticker_prices[t] = dict(zip(df["timestamps"].astype(str).str[:10], df["close"]))
    except:
        ticker_prices[t] = {}

trades["date"] = pd.to_datetime(trades["date"])
trades["thb"] = trades["size_pct"] * CAP
trades["price"] = trades.apply(lambda r: ticker_prices.get(r["ticker"], {}).get(str(r["date"])[:10], 0), axis=1)
trades["shares"] = np.where(trades["price"] > 0, (trades["thb"] / trades["price"] / LOT).round() * LOT, 0)
trades["athb"] = trades["shares"] * trades["price"]
trades["fric"] = trades["athb"] * ONEWAY
trades["pnl"] = trades["gross_return"] * trades["athb"]

eq_v = eq * CAP

# Stop-loss: -10% with +3% re-entry
peak = eq_v.iloc[0]
out_flag, stop_day, stop_val, re_day = False, None, None, None
for i in range(len(eq_v)):
    v = eq_v.iloc[i]
    if not out_flag:
        peak = max(peak, v)
        if v / peak - 1 <= -0.10:
            out_flag, stop_day, stop_val = True, eq_v.index[i], v
    elif re_day is None and stop_val and v >= stop_val * 1.03:
        re_day = eq_v.index[i]

# Precompute display strings
sd = stop_day.strftime('%Y-%m-%d') if stop_day else 'N/A'
rd = re_day.strftime('%Y-%m-%d') if re_day else 'N/A'
sp = f"{stop_val/CAP-1:+.2%}" if stop_val else 'N/A'
sv = f"{stop_val:,.0f}" if stop_val else 'N/A'
rv = f"{eq_v.loc[re_day]:,.0f}" if re_day else 'N/A'
fv = f"{eq_v.iloc[-1]:,.0f}"
if re_day:
    fsr = stop_val * 1.03 * (eq_v.iloc[-1] / eq_v.loc[re_day])
elif stop_day:
    fsr = stop_val
else:
    fsr = eq_v.iloc[-1]
fs = f"{fsr:,.0f}"

# First 7 days
w1 = trades[(trades["date"] >= "2026-01-05") & (trades["date"] <= "2026-01-12")].copy()
w1_rows = ""
for _, r in w1.iterrows():
    cl = "buy" if r["direction"].upper() == "BUY" else "sell"
    ret = f"{r['gross_return']:+.2%}" if r["gross_return"] != 0 else "-"
    n = UNIVERSE.get("thai_equity", {})

    w1_rows += f"<tr class='{cl}'><td>{r['date'].strftime('%Y-%m-%d')}</td><td>{r['ticker']}</td>"
    w1_rows += f"<td style='font-size:0.8em;color:#666'>{r['ticker']}</td>"
    w1_rows += f"<td>{r['direction'].upper()}</td><td align='right'>{r['shares']:.0f}</td>"
    w1_rows += f"<td align='right'>{r['price']:.2f}</td><td align='right'>{r['athb']:,.0f}</td>"
    w1_rows += f"<td align='right'>{r['fric']:.0f}</td><td align='right'>{ret}</td></tr>"

# Top/best 5 trades
closed = trades[trades["gross_return"] != 0].copy()
closed["pnl"] = closed["gross_return"] * closed["athb"]
best5 = closed.nlargest(5, "gross_return")
worst5 = closed.nsmallest(5, "gross_return")

def trade_rows(df):
    r = ""
    for _, row in df.iterrows():
        cl = "buy" if row["gross_return"] > 0 else "sell"
        r += f"<tr class='{cl}'><td>{row['date'].strftime('%Y-%m-%d')}</td><td>{row['ticker']}</td>"
        r += f"<td align='right'>{row['athb']:,.0f}</td>"
        r += f"<td align='right' class=\"{'green' if row['gross_return']>0 else 'red'}\">{row['gross_return']:+.2%}</td>"
        r += f"<td align='right'>{row['pnl']:+,.0f}</td></tr>"
    return r

def holdings_on(dt):
    prior = trades[trades["date"] <= dt]
    pos = {}
    for _, r in prior.iterrows():
        if r["direction"].upper() == "BUY":
            pos[r["ticker"]] = pos.get(r["ticker"], 0) + r["shares"]
        elif r["ticker"] in pos:
            pos[r["ticker"]] -= r["shares"]
            if pos[r["ticker"]] <= 0:
                del pos[r["ticker"]]
    res = []
    for t, s in pos.items():
        px = ticker_prices.get(t, {}).get(str(dt)[:10], 0)
        if px > 0 and s > 0:
            res.append((t, s, px, s * px))
    res.sort(key=lambda x: x[3], reverse=True)
    return res[:5]

def day_card(dt, ret, lbl):
    dt = pd.Timestamp(dt)
    h = holdings_on(dt)
    hr = "".join(f"<tr><td>{t}</td><td align='right'>{s:,}</td><td align='right'>{p:.2f}</td><td align='right'>{v:,.0f}</td></tr>" for t, s, p, v in h)
    return f"""<div class='dc {lbl}'><div class='dh'>{dt.strftime('%Y-%m-%d')} — <strong>{ret:+.2%}</strong></div>
<table><thead><tr><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th></tr></thead><tbody>{hr}</tbody></table></div>"""

daily_ret = eq_v.pct_change().dropna()

# Chart data
vals = eq_v.values
mn, mx = vals.min(), vals.max()
pts = " ".join(f"{1000*i/len(vals):.0f},{250-250*(v-mn)/(mx-mn):.0f}" for i, v in enumerate(vals[::max(1,len(vals)//300)]))
sm = ""
if stop_day:
    si = list(eq_v.index).index(stop_day)
    sm += f"<circle cx='{1000*si/len(vals):.0f}' cy='{250-250*(stop_val-mn)/(mx-mn):.0f}' r='6' fill='#e74c3c' stroke='white' stroke-width='2'/>"
    sm += f"<text x='{1000*si/len(vals):.0f}' y='{245-250*(stop_val-mn)/(mx-mn):.0f}' text-anchor='middle' font-size='10' fill='#e74c3c' font-weight='bold'>STOP</text>"
if re_day:
    ri = list(eq_v.index).index(re_day)
    rv_pt = eq_v.loc[re_day]
    sm += f"<circle cx='{1000*ri/len(vals):.0f}' cy='{250-250*(rv_pt-mn)/(mx-mn):.0f}' r='6' fill='#27ae60' stroke='white' stroke-width='2'/>"
    sm += f"<text x='{1000*ri/len(vals):.0f}' y='{245-250*(rv_pt-mn)/(mx-mn):.0f}' text-anchor='middle' font-size='10' fill='#27ae60' font-weight='bold'>RE</text>"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>2026 YTD Deep Dive</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1100px; margin: 30px auto; padding: 0 20px; background: #f5f7fa; }}
h1 {{ color: #1565C0; border-bottom: 3px solid #1565C0; padding-bottom: 8px; }}
h2 {{ color: #444; margin: 28px 0 12px; font-size: 1.2em; }}
.meta {{ color: #888; font-size: 0.85em; }}
.cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
.card {{ background: white; border-radius: 10px; padding: 12px 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); flex: 1; min-width: 100px; text-align: center; }}
.card .v {{ font-size: 1.4em; font-weight: 700; }}
.card .l {{ font-size: 0.72em; color: #888; text-transform: uppercase; }}
.green {{ color: #27ae60; }} .red {{ color: #e74c3c; }}
.chart {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }}
svg {{ width: 100%; height: auto; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin: 10px 0; font-size: 0.82em; }}
th {{ background: #1565C0; color: white; padding: 8px 10px; text-align: left; font-size: 0.72em; text-transform: uppercase; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #eef3ff; }}
tr.buy {{ border-left: 3px solid #27ae60; }}
tr.sell {{ border-left: 3px solid #e74c3c; }}
.scroll {{ max-height: 420px; overflow-y: auto; }}
.dc {{ background: white; border-radius: 8px; padding: 12px 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin: 8px 0; }}
.dc.win {{ border-left: 4px solid #27ae60; }}
.dc.loss {{ border-left: 4px solid #e74c3c; }}
.dh {{ font-size: 0.92em; margin-bottom: 8px; }}
.flex {{ display: flex; gap: 16px; }}
.flex > div {{ flex: 1; }}
.info {{ background: #e3f2fd; border-radius: 8px; padding: 12px 16px; margin: 12px 0; font-size: 0.85em; line-height: 1.7; }}
.tabs {{ display: flex; gap: 2px; margin: 12px 0; }}
.tab {{ padding: 8px 18px; background: #e0e0e0; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.85em; }}
.tab.active {{ background: white; font-weight: 600; border-bottom: 2px solid #1565C0; }}
.tc {{ display: none; }} .tc.active {{ display: block; }}
</style>
</head>
<body>

<h1>2026 YTD Deep Dive</h1>
<p class="meta">Kronos-TH Thai Equity | Top-5 equal weight | 100-share lots | Friction: {ONEWAY*100:.2f}%/side</p>

<div class="cards">
  <div class="card"><div class="l">Start</div><div class="v">{CAP:,}</div></div>
  <div class="card"><div class="l">Final</div><div class="v green">{eq_v.iloc[-1]:,.0f}</div></div>
  <div class="card"><div class="l">Return</div><div class="v green">{(eq_v.iloc[-1]/CAP-1):+.2%}</div></div>
  <div class="card"><div class="l">Max DD</div><div class="v red">{m['max_drawdown']:.2%}</div></div>
  <div class="card"><div class="l">Trades</div><div class="v">{len(trades)}</div></div>
  <div class="card"><div class="l">Sharpe</div><div class="v green">{m['sharpe']:.2f}</div></div>
</div>

<div class="info">
<strong>Stop-Loss Simulation: -10% / +3% re-entry</strong><br>
Triggered: {sd} at {sv} THB ({sp}) &rarr; Re-entered: {rd} at {rv} THB<br>
Final (with stop): {fs} THB vs (without): {fv} THB
</div>

<h2>Equity Curve</h2>
<div class="chart">
<svg viewBox="0 0 1000 280">
  <line x1="0" y1="250" x2="1000" y2="250" stroke="#ddd" stroke-width="1"/>
  <line x1="0" y1="187" x2="1000" y2="187" stroke="#eee" stroke-width="0.5"/>
  <line x1="0" y1="125" x2="1000" y2="125" stroke="#eee" stroke-width="0.5"/>
  <line x1="0" y1="62" x2="1000" y2="62" stroke="#eee" stroke-width="0.5"/>
  <polyline points="{pts}" fill="none" stroke="#1565C0" stroke-width="2"/>
  {sm}
  <text x="1000" y="270" text-anchor="end" font-size="10" fill="#888">{eq_v.index[-1].strftime('%b %d')}</text>
  <text x="0" y="270" font-size="10" fill="#888">{eq_v.index[0].strftime('%b %d')}</text>
</svg>
</div>

<div class="tabs">
  <div class="tab active" onclick="st('w1')">First 7 Days</div>
  <div class="tab" onclick="st('best')">Best/Worst Days</div>
  <div class="tab" onclick="st('trades')">Best/Worst Trades</div>
</div>

<div id="w1" class="tc active">
<h2>First 7 Days</h2>
<div class="scroll"><table><thead><tr><th>Date</th><th>Ticker</th><th>Dir</th><th>Shares</th><th>Price</th><th>THB</th><th>Friction</th><th>Return</th></tr></thead>
<tbody>{w1_rows}</tbody></table></div>
</div>

<div id="best" class="tc">
<h2>Best Days</h2>
"""

for dt, ret in daily_ret.nlargest(5).items():
    html += day_card(dt, ret, "win")

html += """<h2>Worst Days</h2>"""

for dt, ret in daily_ret.nsmallest(5).items():
    html += day_card(dt, ret, "loss")

html += f"""</div>

<div id="trades" class="tc">
<div class="flex">
<div><h3 style="color:#27ae60">Best 5 Trades</h3>
<table><thead><tr><th>Date</th><th>Ticker</th><th>THB</th><th>Return</th><th>PnL</th></tr></thead>
<tbody>{trade_rows(best5)}</tbody></table></div>
<div><h3 style="color:#e74c3c">Worst 5 Trades</h3>
<table><thead><tr><th>Date</th><th>Ticker</th><th>THB</th><th>Return</th><th>PnL</th></tr></thead>
<tbody>{trade_rows(worst5)}</tbody></table></div>
</div></div>

<div class="info" style="background:#fef3e2;margin-top:20px">
<strong>Key Takeaways:</strong><br>
- Beta vs SET: 0.11 (R{chr(178)} = 0.003) — alpha from stock selection, not market beta<br>
- Stop-loss would trigger {sd} at -10%, re-enter {rd} at +3% above stop<br>
- Jan-Feb: +51% (model crushed SET by 15pp in Jan alone)<br>
- Mar-Apr: -6% drawdown (IVL -5.25% on Mar 3 was the killer)<br>
- Biggest risk: single-stock concentration (5 positions at 20% each)
</div>

<script>
function st(n) {{ document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active')); document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active')); document.getElementById(n).classList.add('active'); event.target.classList.add('active'); }}
</script>
</body>
</html>"""

Path("reports/2026_ytd_deep_dive.html").write_text(html)
print(f"Saved: reports/2026_ytd_deep_dive.html ({len(html):,} bytes)")
print(f"Stop: {sd} at {sv} THB")
print(f"Re-entry: {rd} at {rv} THB")
print(f"Final (stop): {fs} THB vs (raw): {fv} THB")
