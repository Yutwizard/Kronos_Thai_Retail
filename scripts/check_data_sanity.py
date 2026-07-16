"""
One-shot sanity sweep over data/raw/ for every current-universe ticker.
Flags: missing files, the exact-1260-row synthetic fingerprint (see the
2026-07-16 test-pollution incident), suspiciously large single-day jumps
(possible bad split/dividend adjustment), and stale last-date.

Usage: python scripts/check_data_sanity.py
"""
from pathlib import Path
from datetime import date

import pandas as pd

from kth.data.universe import get_all_tickers

JUMP_THRESHOLD = 0.20  # flag any single-day |% change| above this for manual review
SYNTHETIC_ROWCOUNT = 1260  # verify_data_layer.py Test 4's n_days -- see incident note above

cache_dir = Path("data/raw")
tickers = get_all_tickers()

rows = []
for t in tickers:
    safe = t.replace("^", "_").replace("=", "_")
    path = cache_dir / f"{safe}.parquet"
    if not path.exists():
        rows.append({"ticker": t, "status": "MISSING", "detail": str(path)})
        continue
    df = pd.read_parquet(path)
    if df.empty:
        rows.append({"ticker": t, "status": "EMPTY", "detail": ""})
        continue

    n = len(df)
    last_close = float(df["close"].iloc[-1])
    last_date = pd.Timestamp(df["timestamps"].iloc[-1]).date()
    pct = df["close"].pct_change().abs()
    max_jump = float(pct.max()) if len(pct) > 1 else 0.0
    max_jump_date = df["timestamps"].iloc[pct.idxmax()] if len(pct) > 1 and pct.notna().any() else None

    flags = []
    if n == SYNTHETIC_ROWCOUNT:
        flags.append(f"SYNTHETIC_ROWCOUNT(={n})")
    if max_jump > JUMP_THRESHOLD:
        flags.append(f"BIG_JUMP({max_jump:.1%} on {max_jump_date})")
    days_stale = (date.today() - last_date).days
    if days_stale > 5:
        flags.append(f"STALE({days_stale}d old, last={last_date})")

    rows.append({
        "ticker": t, "status": "OK" if not flags else "REVIEW",
        "rows": n, "last_close": round(last_close, 2), "last_date": str(last_date),
        "max_jump": f"{max_jump:.1%}", "detail": "; ".join(flags),
    })

df_report = pd.DataFrame(rows)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 160)
print(df_report.to_string(index=False))

n_missing = (df_report["status"] == "MISSING").sum()
n_empty = (df_report["status"] == "EMPTY").sum()
n_review = (df_report["status"] == "REVIEW").sum()
n_ok = (df_report["status"] == "OK").sum()

print(f"\n{'='*70}")
print(f"Total: {len(df_report)}  OK: {n_ok}  REVIEW: {n_review}  MISSING: {n_missing}  EMPTY: {n_empty}")
if n_review or n_missing or n_empty:
    print("\nNeeds attention:")
    print(df_report[df_report["status"] != "OK"].to_string(index=False))
else:
    print("All clear -- no flags raised.")
