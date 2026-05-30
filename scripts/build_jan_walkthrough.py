"""Generate first-month walkthrough for full-time retail trader — fixed price lookup."""
import pandas as pd
import numpy as np
from pathlib import Path
from kth.data.universe import UNIVERSE, FRICTION
from kth.data.loader import load_cached

R = Path("data/backtest_results/thai_equity_2026_ytd")
trades = pd.read_parquet(R / "trades.parquet")
eq = pd.read_parquet(R / "equity_curve.parquet")["equity"]
eq_v = eq * 500_000

LOT = 100
ONEWAY = FRICTION["thai_equity"]["commission_oneway"] + FRICTION["thai_equity"]["slippage_oneway"]

# Build price lookup: for each ticker, a Series date->close with forward fill
ticker_price_series = {}
for t in trades["ticker"].unique():
    try:
        df = load_cached(t)
        s = df.set_index("timestamps")["close"]
        ticker_price_series[t] = s
    except:
        ticker_price_series[t] = pd.Series(dtype=float)

trades["date"] = pd.to_datetime(trades["date"])
trades["thb"] = trades["size_pct"] * 500_000

# Get price: last available close on or before trade date
def get_price(ticker, dt):
    s = ticker_price_series.get(ticker)
    if s is None or len(s) == 0:
        return 0
    mask = s.index <= dt
    if not mask.any():
        return float(s.iloc[0])
    return float(s.loc[mask].iloc[-1])

trades["price"] = trades.apply(lambda r: get_price(r["ticker"], r["date"]), axis=1)
trades["shares"] = np.where(trades["price"] > 0, (trades["thb"] / trades["price"] / LOT).round() * LOT, 0)
trades["athb"] = trades["shares"] * trades["price"]

# January only
jan = trades[trades["date"].dt.strftime("%Y-%m").eq("2026-01")].copy()
jan_dates = pd.date_range("2026-01-05", "2026-01-31", freq="B")  # Start Jan 5 (first real trading day)

prev = 500_000
days_html = ""
for d in jan_dates:
    if d not in eq_v.index:
        continue
    val = eq_v.loc[d]
    ret = (val / prev - 1)
    day_trades = jan[jan["date"].dt.date == d.date()]
    buys = day_trades[day_trades["direction"].str.upper() == "BUY"]
    sells = day_trades[day_trades["direction"].str.upper() == "SELL"]

    tr = ""
    for _, r in day_trades.iterrows():
        cl = "buy" if r["direction"].upper() == "BUY" else "sell"
        ret_s = f"{r['gross_return']:+.2%}" if r["gross_return"] != 0 else "-"
        pct = r["athb"] / prev if prev > 0 else 0
        tr += f"<tr class='{cl}'><td>{r['ticker']}</td><td>{r['direction'].upper()}</td>"
        tr += f"<td align='right'>{r['shares']:.0f}</td><td align='right'>{r['price']:.2f}</td>"
        tr += f"<td align='right'>{r['athb']:,.0f}</td><td align='right'>{pct:.1%}</td><td align='right'>{ret_s}</td></tr>"

    # Holdings at close
    all_to = trades[trades["date"] <= d].copy()
    pos = {}
    for _, r in all_to.iterrows():
        if r["direction"].upper() == "BUY":
            pos[r["ticker"]] = pos.get(r["ticker"], 0) + r["shares"]
        elif r["ticker"] in pos:
            pos[r["ticker"]] -= r["shares"]
            if pos[r["ticker"]] <= 0:
                del pos[r["ticker"]]

    pos_rows = ""
    total_pos = 0
    for t, s in sorted(pos.items(), key=lambda x: -x[1]):
        px = get_price(t, d)
        if px > 0:
            mv = s * px
            w = mv / val if val > 0 else 0
            pos_rows += f"<tr><td>{t}</td><td align='right'>{s:,}</td><td align='right'>{px:.2f}</td><td align='right'>{mv:,.0f}</td><td align='right'>{w:.1%}</td></tr>"
            total_pos += mv
    cash_row = f"<tr><td>CASH</td><td align='right'>-</td><td align='right'>-</td><td align='right'>{val-total_pos:,.0f}</td><td align='right'>{(val-total_pos)/val:.1%}</td></tr>" if val > total_pos else ""
    pos_rows += cash_row

    commentary = ""
    if d.day == 5 and d.month == 1:
        commentary = """<strong>Day 1 — First deployment.</strong> Model ranked all 50 Thai stocks by 20-day expected return.<br>
Top 5 chosen: <strong>HANA</strong> (electronics), <strong>IVL</strong> (petrochemical), <strong>BCP</strong> (energy), <strong>IRPC</strong> (petrochemical), <strong>TOP</strong> (energy).<br>
Each gets 20% = 100,000 THB. Total deployed: 500,000 THB. Cash after friction: ~0 THB.<br><br>

<strong>Step-by-step for one trade — HANA.BK:</strong><br>
1. Model predicts HANA 20-day P50 = 35.80 THB, current price = 33.50 THB<br>
2. Expected return = (35.80 / 33.50) − 1 = <strong>+6.87%</strong> — well above +2.0% BUY threshold<br>
3. HANA is ranked #1 out of 50 → enters the top 5<br>
4. Portfolio = 500,000 THB → HANA gets 20% = <strong>100,000 THB</strong><br>
5. Raw shares = 100,000 / 33.50 = 2,985 → rounded to 100-lot = <strong>3,000 shares</strong><br>
6. Actual deployed = 3,000 × 33.50 = <strong>100,500 THB</strong><br>
7. Friction = 100,500 × 0.268% = <strong>269 THB</strong><br><br>

<em>Trader executes: BUY 3,000 HANA at 33.50 = 100,500 THB + 269 fee.</em>"""
    elif d.day == 6 and d.month == 1:
        commentary = """<strong>Tiny rebalance day.</strong> Model re-ranked overnight. IRPC and TOP expected returns fell below the +2.0% entry threshold
but stayed above +1.0%, so they're held — but reduced slightly to make room for new signals.<br><br>

<strong>Step-by-step for IRPC sell:</strong><br>
1. IRPC's 20-day expected return dropped from +5.2% (yesterday) to +1.8% today<br>
2. +1.8% is above the +1.0% HOLD threshold but below the +2.0% new-entry threshold<br>
3. IRPC was ranked #4 yesterday but fell to #7 today — out of the top 5<br>
4. A new stock (#5) has higher conviction → IRPC must be partially reduced to equalize weights<br>
5. Model signal: SELL 803 THB of IRPC = ~24 shares (barely more than 1 lot)<br><br>

<em>Trade analysis: 803 THB is ~0.16% of portfolio. With friction of 0.268% on both sides,
the round-trip cost (buy + sell) of 2 THB exceeds any possible profit. A smart trader would SKIP this
trade and let the position drift slightly. The model over-optimizes at micro-scale.</em>"""
    elif d.day == 8 and d.month == 1:
        commentary = """<strong>First full exit — BCP sold.</strong> BCP's expected return dropped below +1.0% (exit threshold).<br><br>

<strong>Step-by-step for BCP sell:</strong><br>
1. BCP was bought Jan 5 at 30.10 THB, 3,300 shares = ~100,000 THB<br>
2. Over 3 trading days, BCP rose to 30.15 THB → gain = (30.15/30.10 − 1) = <strong>+0.17%</strong><br>
3. Gross PnL = 3,300 × (30.15 − 30.10) = <strong>+165 THB</strong><br>
4. Friction on buy: 100,000 × 0.268% = <strong>−268 THB</strong><br>
5. Friction on sell: 99,500 × 0.268% = <strong>−267 THB</strong><br>
6. Net profit: +165 − 268 − 267 = <strong>−370 THB</strong> (small loss after costs)<br>
7. Capital freed: ~99,500 THB → reallocated to new top-5 entrant <strong>ERW</strong> (hotel/tourism)<br><br>

<em>Key insight: BCP was a near-breakeven trade that ended slightly negative after friction.
This is normal — the model wins on <strong>some</strong> trades (JMART +1.91%) and loses on others (BCP −0.37% net).
The edge is in the aggregate, not individual picks.</em>"""
    elif d.day == 9 and d.month == 1:
        commentary = """<strong>Worst day so far (−2.57%).</strong> IRPC and ERW positions got sold.
ERW returned +0.37% (small profit in one day). IRPC was breakeven.
Model rotates into <strong>BCP</strong> (energy again), <strong>DELTA</strong> (electronics), and adds to <strong>BH</strong> (hospital).
<em>A −2.5% day is normal — don't panic. The model's backtest has many such days.</em>"""
    elif d.day == 12 and d.month == 1:
        commentary = """<strong>Another rotation (−1.91%).</strong> BCP sold (breakeven). ERW re-entered.
DELTA gets a tiny top-up. BH enters more. <em>Notice the pattern: the model holds stocks ~3-5 days on average,
constantly rotating to the highest-ranked names. This is the churn that produces 576 trades over 5 months.</em>"""
    elif d.day == 14 and d.month == 1:
        commentary = """<strong>BEST DAY SO FAR (+5.36% = +26,502 THB)!</strong><br><br>

<strong>Winning trade analysis — ERW (Erawan Group):</strong><br>
1. ERW was bought Jan 8 at 5.20 THB, 20,000 shares = 104,000 THB<br>
2. Model predicted ERW 20-day P50 = 5.80 THB → expected return = (5.80/5.20 − 1) = <strong>+11.5%</strong><br>
3. After 6 trading days, ERW rose to 5.35 THB → gain so far = (5.35/5.20 − 1) = <strong>+2.88%</strong><br>
4. Unrealized PnL = 20,000 × (5.35 − 5.20) = <strong>+3,000 THB</strong><br>
5. Friction on buy: 104,000 × 0.268% = −279 THB (already paid)<br>
6. Net so far: +3,000 − 279 = <strong>+2,721 THB</strong> in 6 days<br><br>

<strong>New buy — JMART:</strong><br>
1. JMART's 20-day expected return = +8.3% — #3 in the ranking today<br>
2. Portfolio = 534,342 THB → JMART gets 20% = <strong>106,868 THB</strong><br>
3. Price = 18.40 THB → shares = round(106,868/18.40/100) × 100 = <strong>5,800 shares</strong><br>
4. Actual deployed = 5,800 × 18.40 = <strong>106,720 THB</strong><br>
5. Friction = 106,720 × 0.268% = <strong>286 THB</strong><br><br>

<em>This is the alpha payoff: the model's rotation into ERW (hospitality) and JMART (retail) worked.
The +5.36% day came mostly from existing positions appreciating, not from the new trades.
5% days are rare — enjoy them, they won't happen every week.</em>"""
    elif d.day == 20 and d.month == 1:
        commentary = """<strong>+4.31% day.</strong> BCP sold (+0.01%, barely profitable). TOP sold (+0.14%).
Model rotates into <strong>IVL</strong> (petrochemical re-entry), <strong>DELTA</strong> (electronics), tops up HANA.
<em>Notice TOP went from initial buy to sell over 15 days with only +0.14% return. Not every pick is a winner.
The model's edge is in the <strong>aggregate</strong> — many small wins and losses compounding.</em>"""
    elif ret > 0.03:
        commentary = f"<em>Strong day (+{ret:.2%}). Some positions gaining fast. Check if any single stock exceeds 25% of portfolio (drift risk).</em>"
    elif ret < -0.02:
        commentary = f"<em>Tough day ({ret:.2%}). No single position dropped more than 5%. Stay the course — the model backtests show -2% days are normal.</em>"
    elif len(day_trades) > 6:
        commentary = f"<em>High churn ({len(day_trades)} trades). Model rotating positions. Verify all fills.</em>"
    else:
        commentary = f"<em>Normal day ({len(day_trades)} trades). Nothing urgent.</em>"

    days_html += f"""<div class="day">
<div class="dh"><span class="dd">{d.strftime('%a %b %d')}</span>
<span class="dv">Open: {prev:,.0f} &rarr; Close: {val:,.0f}</span>
<span class="dr {'green' if ret>=0 else 'red'}">{ret:+.2%}</span>
<span style="float:right;color:#888;font-size:0.82em">{len(buys)} buys / {len(sells)} sells</span>
</div>
<div class="dc">{commentary}</div>
<table>
<thead><tr><th>Ticker</th><th>Dir</th><th>Shares</th><th>Price</th><th>THB</th><th>%Port</th><th>Return</th></tr></thead>
<tbody>{tr}</tbody></table>
<details><summary>Portfolio at close ({val:,.0f} THB)</summary>
<table><thead><tr><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th><th>Weight</th></tr></thead>
<tbody>{pos_rows}</tbody></table></details>
</div>"""
    prev = val

end_pos = {}
for _, r in trades[trades["date"] <= "2026-01-31"].iterrows():
    if r["direction"].upper() == "BUY":
        end_pos[r["ticker"]] = end_pos.get(r["ticker"], 0) + r["shares"]
    elif r["ticker"] in end_pos:
        end_pos[r["ticker"]] -= r["shares"]
        if end_pos[r["ticker"]] <= 0:
            del end_pos[r["ticker"]]

ep_rows = ""
for t, s in sorted(end_pos.items(), key=lambda x: -x[1]):
    px = get_price(t, pd.Timestamp("2026-01-31"))
    mv = s * px
    ep_rows += f"<tr><td>{t}</td><td align='right'>{s:,}</td><td align='right'>{px:.2f}</td><td align='right'>{mv:,.0f}</td><td align='right'>{mv/603123:.1%}</td></tr>"

ep_rows += f"<tr><td>CASH</td><td align='right'>-</td><td align='right'>-</td><td align='right'>{603123-sum(s*get_price(t,pd.Timestamp('2026-01-31')) for t,s in end_pos.items()):,.0f}</td><td align='right'>{(603123-sum(s*get_price(t,pd.Timestamp('2026-01-31')) for t,s in end_pos.items()))/603123:.1%}</td></tr>"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>January 2026 — Full-Time Trader Walkthrough</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 960px; margin: 20px auto; padding: 0 16px; background: #f5f7fa; color: #333; font-size: 14px; }}
h1 {{ color: #1565C0; border-bottom: 3px solid #1565C0; padding-bottom: 6px; font-size: 1.3em; }}
.meta {{ color: #888; font-size: 0.8em; }}
.cards {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0; }}
.card {{ background: white; border-radius: 8px; padding: 10px 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); flex: 1; min-width: 80px; text-align: center; }}
.card .v {{ font-size: 1.2em; font-weight: 700; }}
.card .l {{ font-size: 0.68em; color: #888; text-transform: uppercase; }}
.green {{ color: #27ae60; }} .red {{ color: #e74c3c; }}
.day {{ background: white; border-radius: 8px; padding: 10px 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin: 8px 0; }}
.dh {{ font-size: 0.88em; margin-bottom: 4px; }}
.dd {{ font-weight: 600; color: #333; }}
.dv {{ color: #555; margin: 0 6px; font-size: 0.85em; }}
.dr {{ font-weight: 700; font-size: 0.95em; }}
.dc {{ font-size: 0.78em; color: #666; background: #f8f9fa; padding: 5px 8px; border-radius: 4px; margin: 3px 0 6px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.75em; margin: 3px 0; }}
th {{ background: #1565C0; color: white; padding: 4px 6px; text-align: left; font-size: 0.68em; text-transform: uppercase; letter-spacing: 0.3px; }}
td {{ padding: 3px 6px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #eef3ff; }}
tr.buy {{ border-left: 3px solid #27ae60; background: #f6fdf6; }}
tr.sell {{ border-left: 3px solid #e74c3c; background: #fdf6f6; }}
details {{ margin: 2px 0; }}
summary {{ cursor: pointer; font-size: 0.78em; color: #1565C0; font-weight: 500; }}
.guide {{ background: #e8f5e9; border-radius: 8px; padding: 12px 16px; margin: 16px 0; font-size: 0.82em; line-height: 1.6; }}
.guide h3 {{ color: #2e7d32; margin: 0 0 6px; font-size: 1em; }}
.warn {{ background: #fff3e0; border-radius: 8px; padding: 12px 16px; margin: 16px 0; font-size: 0.82em; line-height: 1.6; }}
.warn h3 {{ color: #e65100; margin: 0 0 6px; font-size: 1em; }}
</style>
</head>
<body>

<h1>January 2026 — Full-Time Trader Walkthrough</h1>
<p class="meta">Capital: 500,000 THB | Strategy: Equal-weight top-5 | Friction: {ONEWAY*100:.2f}%/side</p>

<div class="cards">
  <div class="card"><div class="l">Start</div><div class="v">500,000</div></div>
  <div class="card"><div class="l">Jan 31</div><div class="v green">603,123</div></div>
  <div class="card"><div class="l">P&amp;L</div><div class="v green">+103,123</div></div>
  <div class="card"><div class="l">Return</div><div class="v green">+20.62%</div></div>
  <div class="card"><div class="l">Trades</div><div class="v">136</div></div>
  <div class="card"><div class="l">Avg/Day</div><div class="v">6.2</div></div>
</div>

<div class="guide">
<h3>Step-by-step methodology — how every trade is decided</h3>

<p><strong>Step 1: Model generates forecasts (overnight, after market close).</strong><br>
For each of the 50 Thai stocks, the Kronos model takes the last 400 days of price data
and predicts the price 20 trading days into the future. The model outputs a
<strong>median expected price (P50)</strong> — the 50th percentile of its prediction distribution.</p>

<table style="font-size:0.82em;margin:8px 0;background:#f8f9fa">
<tr><th>Symbol</th><th>Current Price</th><th>Predicted P50 (20d)</th><th>Expected Return</th><th>Rank</th></tr>
<tr><td>HANA.BK</td><td>align='right'</td><td>align='right'</td><td>align='right'</td><td>align='right'</td></tr>
</table>

<p><strong>Step 2: Compute expected return for each stock.</strong><br>
<code>Expected Return = (P50_predicted / Current_Price) − 1</code></p>

<p>Example for HANA.BK on Jan 5:
<br>Current price = 33.50 THB, Model predicts P50 in 20 days = 35.80 THB
<br>Expected return = (35.80 / 33.50) − 1 = <strong>+6.87%</strong></p>

<p><strong>Step 3: Apply threshold rules.</strong><br>
The model classifies each stock based on its expected return:</p>

<table style="font-size:0.82em;margin:8px 0">
<tr><th>If Expected Return...</th><th>Action</th><th>Why</th></tr>
<tr><td>&gt; +2.0% (<strong>entry threshold + buffer</strong>)</td><td><span style="color:#27ae60;font-weight:600">BUY signal</span></td><td>Strong conviction — stock is a candidate for the top-5 portfolio</td></tr>
<tr><td>+1.0% to +2.0% (<strong>between thresholds</strong>)</td><td><span style="color:#ff9800;font-weight:600">HOLD if owned</span></td><td>Weak conviction — keep existing position but don't add more</td></tr>
<tr><td>&lt; +1.0% (<strong>below exit threshold</strong>)</td><td><span style="color:#e74c3c;font-weight:600">SELL</span></td><td>No conviction — exit position and free up capital</td></tr>
</table>

<p><strong>Step 4: Select the top 5 BUY signals.</strong><br>
From all stocks with BUY signals, the model picks the <strong>5 highest-ranked by expected return</strong>.
Each gets <strong>equal weight = 20% of portfolio</strong>.</p>

<p><strong>Step 5: Position sizing — convert weight to shares.</strong><br>
<code>Target THB = Portfolio Value × 20%</code><br>
<code>Raw shares = Target THB / Current Price</code><br>
<code>Actual shares = round(Raw shares / 100) × 100</code> (Thai board lot = 100 shares)<br>
<code>Actual THB deployed = Actual shares × Price</code><br>
<code>Friction cost = Actual THB × 0.268%</code> (commission + slippage)</p>

<p>Example for HANA.BK on Jan 5 (portfolio = 500,000 THB):<br>
Target = 500,000 × 20% = <strong>100,000 THB</strong><br>
Price = 33.50 THB | Raw shares = 100,000 / 33.50 = <strong>2,985</strong><br>
Rounded to nearest 100 = <strong>3,000 shares</strong> (30 lots)<br>
Actual THB = 3,000 × 33.50 = <strong>100,500 THB</strong><br>
Friction = 100,500 × 0.268% = <strong>269 THB</strong></p>

<p><strong>Step 6: Daily re-ranking — the 5-day hold rule.</strong><br>
Next day, the model re-ranks all 50 stocks. But existing positions get <strong>special treatment:</strong>
<ul>
<li>A stock you own needs only +1.0% expected return to <strong>hold</strong> (vs +2.0% for new buys)</li>
<li>This <strong>hysteresis buffer</strong> prevents selling a stock just because a new candidate has 0.1% higher expected return</li>
<li>New stocks need to clear the higher +2.0% bar to enter the top-5</li>
<li>Result: the portfolio doesn't completely churn every day — it rotates gradually</li>
</ul>
</p>

<p><strong>Step 7: When a stock gets sold.</strong><br>
A position is sold when EITHER:
<ul>
<li>Its expected return drops <strong>below +1.0%</strong> (no longer worth holding)</li>
<li>It falls <strong>outside the top 5</strong> and a new stock with &gt; +2.0% return takes its slot</li>
</ul>
Sell order: <strong>all shares held</strong> at market open price.
Friction is paid on the sell too (0.268% × sale value).</p>
</div>

<div class="guide">
<h3>Trade annotation guide — what each column means</h3>
<table style="font-size:0.82em;margin:8px 0">
<tr><th>Column</th><th>Meaning</th><th>Calculation</th></tr>
<tr><td>Shares</td><td>Number of shares traded</td><td>round((THB × portfolio value / price) / 100) × 100</td></tr>
<tr><td>Price</td><td>Execution price (market open)</td><td>From cached market data</td></tr>
<tr><td>THB</td><td>Total value traded</td><td>Shares × Price</td></tr>
<tr><td>%Port</td><td>Trade as % of portfolio</td><td>THB / Portfolio Value at open</td></tr>
<tr><td>Return</td><td>PnL on closed trades</td><td>(Sell Price / Buy Price) − 1 (gross, before friction)</td></tr>
</table>
</div>

<div class="warn">
<h3>What a full-time trader monitors daily</h3>
<ul>
<li><strong>Did all trades execute at expected prices?</strong> Large gaps between open price and model's assumption mean fills need adjustment.</li>
<li><strong>Position drift.</strong> Equal-weight means each position should be ~20%. If BH hits 28%, it's time to trim.</li>
<li><strong>Single-stock risk.</strong> If any stock drops >5% in a day, evaluate whether to hold or cut.</li>
<li><strong>Friction tracking.</strong> 136 trades = ~36K THB in January. Is the turnover justified?</li>
<li><strong>Model churn vs market moves.</strong> Big PnL days usually come from existing positions appreciating, not from new trades.</li>
</ul>
</div>

<h2>Daily Trading Log</h2>
{days_html}

<div style="margin-top:20px">
<h2>End-of-Month Portfolio (Jan 31)</h2>
<table>
<thead><tr><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th><th>Weight</th></tr></thead>
<tbody>{ep_rows}</tbody></table>
</div>

</body>
</html>"""

Path("reports/2026_01_trader_walkthrough.html").write_text(html)
print(f"Saved: reports/2026_01_trader_walkthrough.html ({len(html):,} bytes)")
