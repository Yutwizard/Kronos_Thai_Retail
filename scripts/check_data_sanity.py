"""
One-shot sanity sweep over data/raw/ for every current-universe ticker.
Flags: missing files, the exact-1260-row synthetic fingerprint (see the
2026-07-16 test-pollution incident), suspiciously large single-day jumps
(possible bad split/dividend adjustment), and stale last-date. Also flags the
Yahoo "stub row" pattern (2026-09-21 audit): a flat zero-volume row (open ==
high == low == close, volume 0) is a day with no usable price. Checked as
(a) dates where >=half of all tickers are stubbed at once, (b) a series whose
last row has zero volume (a stub or a halt/holiday carry-over), (c) a >10-day gap between consecutive rows, (d) a >15%
move on the first real row after a stub (halt resumption or unadjusted
corporate action, e.g. TRUE.BK 2023-03-03).

Usage: python scripts/check_data_sanity.py
"""
from pathlib import Path
from datetime import date

import pandas as pd

from kth.data.universe import get_all_tickers

JUMP_THRESHOLD = 0.20  # flag any single-day |% change| above this for manual review
SYNTHETIC_ROWCOUNT = 1260  # verify_data_layer.py Test 4's n_days -- see incident note above
BREAK_AFTER_STUB = 0.15    # |% change| on the first real row after a stub row
MAX_GAP_DAYS = 10          # calendar days between consecutive rows (longest normal SET break is ~5)
CROSS_STUB_SHARE = 0.5     # share of tickers stubbed on one date to call it a data-wide outage

cache_dir = Path("data/raw")
tickers = get_all_tickers()

rows = []
stub_by_ticker = {}
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

    ts = pd.to_datetime(df["timestamps"])
    stub = (df["volume"] == 0) & (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    stub_by_ticker[t] = pd.Series(stub.to_numpy().astype(float), index=ts.to_numpy())

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
    if bool(stub.iloc[-1]) or float(df["volume"].iloc[-1]) == 0:
        flags.append(f"LAST_ROW_ZERO_VOLUME({last_date})")
    gaps = ts.diff().dt.days
    if gaps.max() > MAX_GAP_DAYS:
        flags.append(f"GAP({int(gaps.max())}d ending {ts[gaps.idxmax()].date()})")
    resumed = stub.shift(1, fill_value=False) & ~stub & (df["close"].pct_change().abs() > BREAK_AFTER_STUB)
    if resumed.any():
        flags.append("BREAK_AFTER_STUB(" + ", ".join(str(d.date()) for d in ts[resumed]) + ")")
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

stub_frame = pd.DataFrame(stub_by_ticker)
share = stub_frame.sum(axis=1) / stub_frame.notna().sum(axis=1)
cross_dates = share[share >= CROSS_STUB_SHARE]
print(f"\nCross-ticker stub dates (>= {CROSS_STUB_SHARE:.0%} of tickers flat with zero volume on the same date): {len(cross_dates)}")
if len(cross_dates):
    by_year = cross_dates.groupby(pd.DatetimeIndex(cross_dates.index).year).size().to_dict()
    print(f"  by year: {by_year}; first {pd.Timestamp(cross_dates.index[0]).date()}, last {pd.Timestamp(cross_dates.index[-1]).date()}")
    print("  These are real trading days with no usable prices: stale prices carry into the next real day,")
    print("  so daily returns are lumped and volume features are corrupted. Drop or handle before daily-return stats.")

n_missing = (df_report["status"] == "MISSING").sum()
n_empty = (df_report["status"] == "EMPTY").sum()
n_review = (df_report["status"] == "REVIEW").sum()
n_ok = (df_report["status"] == "OK").sum()

print(f"\n{'='*70}")
print(f"Total: {len(df_report)}  OK: {n_ok}  REVIEW: {n_review}  MISSING: {n_missing}  EMPTY: {n_empty}")
if n_review or n_missing or n_empty or len(cross_dates):
    print("\nNeeds attention:")
    print(df_report[df_report["status"] != "OK"].to_string(index=False))
else:
    print("All clear -- no flags raised.")
