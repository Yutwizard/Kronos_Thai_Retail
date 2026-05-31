"""Morning routine: download fresh data → generate daily brief."""
import subprocess, sys, time
from pathlib import Path
import pandas as pd
from datetime import date

print("=" * 55)
print(f"KRONOS-TH MORNING ROUTINE — {date.today()}")
print("=" * 55)

# Step 1: Download fresh data
print("\n[1/2] Downloading fresh data...")
t0 = time.time()
result = subprocess.run([sys.executable, "scripts/download_data.py"], capture_output=True, text=True)
if result.returncode != 0:
    print("WARNING: download_data.py failed — using cached data")
    print(result.stderr[-200:] if result.stderr else "Unknown error")
else:
    print(f"  Download complete in {time.time()-t0:.0f}s")
    # Check latest date
    from kth.data.loader import load_cached
    df = load_cached("PTT.BK")
    print(f"  Latest data: {df['timestamps'].max().date()} ({len(df)} rows)")

# Step 2: Daily brief
print(f"\n[2/2] Running daily brief...")
result = subprocess.run([sys.executable, "scripts/daily_brief.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("ERRORS:", result.stderr[-500:])

# Save output
Path("data/logs").mkdir(exist_ok=True)
log_path = f"data/logs/morning_{date.today().isoformat()}.log"
Path(log_path).write_text(result.stdout + "\n" + result.stderr)
print(f"\nLog saved: {log_path}")
print("Done.")
