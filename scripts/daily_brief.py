"""Daily operations script — generate signals + apply allocation bands + stop-loss check."""
import json, pandas as pd, numpy as np
from pathlib import Path
from datetime import date, timedelta
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached

today = date.today()
friday = pd.Timestamp(today) - pd.tseries.offsets.Week(weekday=4)  # last Friday

print("=" * 55)
print(f"KRONOS-TH DAILY BRIEF — {today}")
print("=" * 55)

# 1. Load model + generate signals
print("\n[1/4] Loading model + generating signals...")
tickers = [t for t, _, _ in UNIVERSE['thai_equity']]
k = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')
fc = k.forecast_batch(tickers, pred_lens=[20], n_samples=50)

# 2. Rank by 20d expected return
ranked = []
last_closes = {}
for t, r in fc.items():
    try:
        df = load_cached(t)
        price = float(df['close'].iloc[-1])
        last_closes[t] = price
    except:
        price = 0
    p50 = r.horizons[20].summary['p50'].iloc[-1]
    exp_ret = (p50 / price - 1) if price > 0 else 0
    ranked.append({'ticker': t, 'price': price, 'expected_return': exp_ret})

ranked.sort(key=lambda x: x['expected_return'], reverse=True)

print("\n[2/4] Top 5 Signals (20-day expected return):")
print(f"{'Rank':<6} {'Ticker':<12} {'Price':>8} {'Exp Return':>12} {'Signal':<10}")
print("-" * 50)
top5 = ranked[:5]
for i, r in enumerate(top5, 1):
    sig = 'BUY' if r['expected_return'] > 0.02 else ('HOLD' if r['expected_return'] > 0.01 else 'SELL')
    print(f"{i:<6} {r['ticker']:<12} {r['price']:>8.2f} {r['expected_return']:>+11.2%} {sig:<10}")

# 3. Weekly allocation check (from backtest or live portfolio tracker)
print("\n[3/4] Risk Controls:")

# Load the latest backtest equity curve for Sharpe calculation
# In live mode, this would be your actual portfolio tracker
try:
    eq = None
    for y in ['2025', '2024']:
        p = Path(f'data/backtest_results/thai_equity_{y}_n50')
        if (p / 'equity_curve.parquet').exists():
            eq = pd.read_parquet(p / 'equity_curve.parquet')['equity']
            break
    if eq is not None:
        daily = eq.pct_change().dropna()
        hist = daily.tail(60)
        sh = hist.mean() / hist.std() * np.sqrt(252)
        alloc = 0.15 if sh > 1.0 else (0.10 if sh > 0.5 else (0.05 if sh > 0 else 0))
        peak = eq.cummax().iloc[-1]
        dd = eq.iloc[-1] / peak - 1
        stopped = dd <= -0.10
        final_alloc = 0 if stopped else alloc
        
        print(f"  12-week Sharpe: {sh:.2f}")
        print(f"  Allocation band: {alloc:.0%}")
        print(f"  Max drawdown: {dd:+.1%}")
        print(f"  Stop-loss: {'TRIGGERED -> CASH' if stopped else 'OK'}")
        print(f"  FINAL ALLOCATION: {final_alloc:.0%}")
    else:
        print("  No backtest data for Sharpe calculation")
        print("  FINAL ALLOCATION: use manual override")
except Exception as e:
    print(f"  Error computing risk controls: {e}")

# 4. Bottom 5 to avoid
print("\n[4/4] Bottom 5 — Avoid/Reduce:")
bottom5 = ranked[-5:]
for r in bottom5:
    print(f"  {r['ticker']:<12} Exp Return: {r['expected_return']:+.2%} -> AVOID")

# Summary box
print("\n" + "=" * 55)
print("TRADING PLAN:")
if top5:
    capital = 500_000
    per_pos = capital * final_alloc / 5 if final_alloc > 0 else 0
    print(f"  Allocate {final_alloc:.0%} of portfolio ({capital * final_alloc:,.0f} THB)")
    if final_alloc > 0:
        print(f"  Buy {len(top5)} positions at {per_pos:,.0f} THB each:")
        for r in top5:
            lots = int(per_pos / r['price'] / 100) * 100
            print(f"    {r['ticker']:<12} {lots:>5} shares x {r['price']:.2f} = {lots * r['price']:>8,.0f} THB")
    else:
        print(f"  ALLOCATION = 0% -> Stay in cash (stop-loss triggered or negative Sharpe)")
print("=" * 55)
