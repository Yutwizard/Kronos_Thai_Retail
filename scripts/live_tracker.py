"""Weekly live-vs-backtest tracker. Compare actual portfolio to expected equity curve."""
import json, pandas as pd, numpy as np, sys
from pathlib import Path
from datetime import date

LIVE_FILE = Path("data/live_portfolio.csv")
today = date.today()

# Load backtest reference
ref = None; ref_label = ""
for y, d in [("2024-2025", "thai_equity_2025_n50"), ("2025", "thai_equity_2025_n50"),
             ("2022-2024 v2", "thai_equity_2022-2024_v2")]:
    p = Path(f"data/backtest_results/{d}")
    if (p / "equity_curve.parquet").exists():
        ref = pd.read_parquet(p / "equity_curve.parquet")["equity"]
        ref_label = y; break
if ref is None:
    print("No backtest reference found. Run a backtest first.")
    sys.exit(1)

# Initialize or load live tracker
if not LIVE_FILE.exists():
    LIVE_FILE.write_text(f"date,value\n{today},500000\n")
    live = pd.read_csv(LIVE_FILE, parse_dates=["date"])
    print(f"Created tracker: {LIVE_FILE} (start: 500,000)")
else:
    live = pd.read_csv(LIVE_FILE, parse_dates=["date"])

    # If arg given: append today's value
    if len(sys.argv) > 1:
        new_val = float(sys.argv[1])
        with open(LIVE_FILE, "a") as f:
            f.write(f"{today},{new_val}\n")
        live = pd.read_csv(LIVE_FILE, parse_dates=["date"])
        print(f"Recorded: {today} = {new_val:,.0f} THB")

live_val = float(live["value"].iloc[-1])
live_date = live["date"].iloc[-1].date()

# Get reference value
start_date = pd.to_datetime(live["date"].iloc[0])
ref_idx = ref.index[ref.index >= start_date]
if len(ref_idx) == 0:
    # Live starts after backtest ends — use last backtest date as baseline
    ref_idx = [ref.index[-1]]
    print(f"Note: Live starts after backtest ends. Using last backtest date ({ref.index[-1].date()}) as baseline.")
    print(f"Run the 2026 n=50 backtest to get a proper reference curve.")

ref_start = ref.loc[ref_idx[0]]
ref_date = ref_idx[0].date()
ref_closest = ref.loc[ref_idx[-1]] if pd.Timestamp(live_date) >= ref_idx[0] else ref_start

# Compute comparison
live_norm = live_val / 500_000
ref_norm = ref_closest / ref_start

live_ret = live_norm - 1
ref_ret = ref_norm - 1
deviation = live_ret - ref_ret

print()
print("=" * 55)
print(f"LIVE vs BACKTEST — {today}")
print("=" * 55)
print(f"  Reference: {ref_label} (normalized from {ref_date})")
print(f"  Tracking since: {live['date'].iloc[0].date()} ({len(live)} entries)")
print()
print(f"  Live Portfolio:       {live_val:>10,.0f} THB  ({live_ret:+.2%})")
print(f"  Backtest Expected:    {ref_norm * 500_000:>10,.0f} THB  ({ref_ret:+.2%})")
print(f"  Deviation:            {deviation * 500_000:>+10,.0f} THB  ({deviation:+.2%})")
print()

if abs(deviation) > 0.05:
    print(f"  ⚠️  DEVIATION > 5pp — investigate!")
    print(f"  Possible: execution slippage, signal degradation, regime change")
elif abs(deviation) > 0.03:
    print(f"  ⚡ Deviation > 3pp — monitor closely next week")
else:
    print(f"  ✅ Deviation within expected range (<3pp)")

# Weekly prompt
last_tracked = live["date"].iloc[-1].date()
if last_tracked < today and len(sys.argv) == 1:
    days = (today - last_tracked).days
    print(f"\n  Last entry: {last_tracked} ({days}d ago)")
    print(f"  To record today: python scripts/live_tracker.py {live_val:.0f}")
    print(f"  Then enter the actual broker value.")

print(f"\n  Tracker: {LIVE_FILE}")
