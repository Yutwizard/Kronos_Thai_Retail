"""Generate 2026 YTD trading journal from backtest results."""
import json
import pandas as pd
from pathlib import Path

result_dir = Path("data/backtest_results/thai_equity_2026_ytd")
trades = pd.read_parquet(result_dir / "trades.parquet")
eq = pd.read_parquet(result_dir / "equity_curve.parquet")["equity"]
with open(result_dir / "metrics.json") as f:
    metrics = json.load(f)

cap = 500_000
eq_thb = eq * cap
final_val = eq_thb.iloc[-1]
pnl = final_val - cap

print("=" * 60)
print("  2026 YTD TRADING JOURNAL  —  Kronos-TH Thai Equity")
print("=" * 60)
print(f"  Capital:     {cap:>10,.0f} THB")
print(f"  Final:       {final_val:>10,.0f} THB")
print(f"  P&L:         {pnl:>+10,.0f} THB")
print(f"  Return:      {metrics['total_return']:>+9.2%}")
print(f"  CAGR:        {metrics['cagr']:>+9.2%}")
print(f"  Sharpe:      {metrics['sharpe']:>9.2f}")
print(f"  Max DD:      {metrics['max_drawdown']:>+9.2%}")
print(f"  Trade Win:   {metrics['trade_win_rate']:>9.2%}")
print(f"  Total Trades:{len(trades):>9}")
print()

# Monthly summary
eq_monthly = eq_thb.resample("ME").last()
print(f"  {'Month':<12} {'Equity THB':>12} {'Return':>10} {'Trades':>8}")
print(f"  {'-'*42}")
print(f"  {'2025-12-31':<12} {cap:>12,} {'-':>10} {'-':>8}")
for i in range(len(eq_monthly)):
    m = eq_monthly.index[i]
    prev = eq_monthly.iloc[i-1] if i > 0 else cap
    ret = (eq_monthly.iloc[i] / prev) - 1
    start = eq_monthly.index[i-1] if i > 0 else pd.Timestamp("2026-01-01")
    end = eq_monthly.index[i]
    mask = (trades["date"] >= start) & (trades["date"] < end)
    n = mask.sum()
    print(f"  {m.strftime('%Y-%m-%d'):<12} {eq_monthly.iloc[i]:>12,.0f} {ret:>+9.2%} {n:>8}")
print(f"  {eq.index[-1].strftime('%Y-%m-%d'):<12} {eq_thb.iloc[-1]:>12,.0f}")
print()

# Top best/worst trades
closed = trades[trades["gross_return"] != 0].copy()
closed["thb_pnl"] = closed["size_pct"] * closed["gross_return"]
best = closed.nlargest(5, "gross_return")
worst = closed.nsmallest(5, "gross_return")

print(f"  TOP 5 WINNERS")
print(f"  {'Date':<12} {'Ticker':<12} {'Return':>10} {'THB':>12}")
print(f"  {'-'*46}")
for _, r in best.iterrows():
    print(f"  {str(r['date'])[:10]:<12} {r['ticker']:<12} {r['gross_return']:>+9.2%} {r['thb_pnl']:>+11,.0f}")

print(f"\n  TOP 5 LOSERS")
print(f"  {'Date':<12} {'Ticker':<12} {'Return':>10} {'THB':>12}")
print(f"  {'-'*46}")
for _, r in worst.iterrows():
    print(f"  {str(r['date'])[:10]:<12} {r['ticker']:<12} {r['gross_return']:>+9.2%} {r['thb_pnl']:>+11,.0f}")

# Monthly trade log
print(f"\n  ALL TRADES BY MONTH")
for ym in sorted(trades["date"].astype(str).str[:7].unique()):
    mask = trades["date"].astype(str).str.startswith(ym)
    sub = trades[mask].copy()
    sub["thb"] = sub["size_pct"] * cap
    print(f"\n  === {ym} === ({len(sub)} trades)")
    print(f"  {'Date':<12} {'Ticker':<12} {'Dir':<6} {'THB':>10} {'Return':>10}")
    print(f"  {'-'*50}")
    for _, r in sub.iterrows():
        ret = f"{r['gross_return']:+.2%}" if r["gross_return"] != 0 else "-"
        print(f"  {str(r['date'])[:10]:<12} {r['ticker']:<12} {r['direction']:<6} {r['thb']:>10,.0f} {ret:>10}")
