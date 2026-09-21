"""
Verification of kth/data/clean.py on synthetic data only (never touches ./data/raw).

Checks: stub-date drop, per-ticker stub kept but flagged not real, known-break scaling (return on the break day
becomes 0, every other return unchanged), skipped breaks are reported, the cache is not modified, results are
deterministic, and the "^" filename rule is honoured.
"""
import hashlib
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from kth.data.clean import CleanReport, load_clean_closes, stub_mask


def write(cache: Path, ticker: str, close, volume=None, stub_rows=()):
    n = len(close)
    dates = pd.bdate_range("2024-01-01", periods=n)
    c = np.asarray(close, dtype=float)
    vol = np.full(n, 1000.0) if volume is None else np.asarray(volume, dtype=float)
    o, h, l = c * 0.999, c * 1.01, c * 0.99
    for i in stub_rows:  # flat zero-volume row carrying the previous close
        c[i] = c[i - 1]; o[i] = h[i] = l[i] = c[i]; vol[i] = 0.0
    df = pd.DataFrame({"timestamps": dates, "open": o, "high": h, "low": l, "close": c, "volume": vol, "amount": c * vol})
    df.to_parquet(cache / f"{ticker.replace('^', '_').replace('=', '_')}.parquet")
    return dates


def digest(cache: Path) -> dict:
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(cache.glob("*.parquet"))}


print("=" * 70)
print("TEST 1: stub row definition")
print("=" * 70)
flat = pd.DataFrame({"open": [5.0, 5.0], "high": [5.0, 5.1], "low": [5.0, 4.9], "close": [5.0, 5.0], "volume": [0.0, 0.0]})
assert stub_mask(flat).tolist() == [True, False], "flat zero-volume row is a stub; zero volume with a range is not"
print("  OK")

with tempfile.TemporaryDirectory() as d:
    cache = Path(d)
    n = 30
    rng = np.random.default_rng(1)
    base = 20 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    # 4 tickers; on row 10 three of four are stubbed (data-wide outage), on row 20 only ticker A is stubbed
    dates = write(cache, "A.BK", base, stub_rows=(10, 20))
    write(cache, "B.BK", base * 1.5, stub_rows=(10,))
    write(cache, "C.BK", base * 0.7, stub_rows=(10,))
    write(cache, "D.BK", base * 2.0)
    write(cache, "^IDX", base * 100)  # filename rule: _IDX.parquet
    before = digest(cache)

    print("\n" + "=" * 70)
    print("TEST 2: data-wide stub date dropped, lone stub kept but flagged, cache untouched")
    print("=" * 70)
    tick = ["A.BK", "B.BK", "C.BK", "D.BK", "^IDX"]
    close, real, rep = load_clean_closes(tick, cache_dir=str(cache), breaks={})
    assert isinstance(rep, CleanReport)
    assert rep.dropped_dates == [dates[10]], rep.dropped_dates
    assert dates[10] not in close.index and len(close) == n - 1
    assert dates[20] in close.index and not real.loc[dates[20], "A.BK"] and real.loc[dates[20], "B.BK"]
    assert close.loc[dates[20], "A.BK"] == close.loc[dates[19], "A.BK"], "lone stub keeps the carried-forward price"
    assert rep.ticker_stub_rows.get("A.BK") == 1 and "D.BK" not in rep.ticker_stub_rows
    assert "^IDX" in close.columns
    assert digest(cache) == before, "cache files were modified"
    print("  OK")

    print("\n" + "=" * 70)
    print("TEST 3: deterministic")
    print("=" * 70)
    close2, real2, rep2 = load_clean_closes(tick, cache_dir=str(cache), breaks={})
    pd.testing.assert_frame_equal(close, close2); pd.testing.assert_frame_equal(real, real2)
    assert rep.dropped_dates == rep2.dropped_dates
    print("  OK")

    print("\n" + "=" * 70)
    print("TEST 4: known break scaled so that day's return is 0; other returns unchanged")
    print("=" * 70)
    brk = np.concatenate([np.full(15, 5.0) * (1 + 0.001 * np.arange(15)), np.full(15, 8.0) * (1 + 0.001 * np.arange(15))])
    write(cache, "BRK.BK", brk)
    dbrk = pd.bdate_range("2024-01-01", periods=30)[15]
    c3, r3, rep3 = load_clean_closes(["BRK.BK", "D.BK"], cache_dir=str(cache), breaks={"BRK.BK": [(str(dbrk.date()), "test")]})
    raw_ret = pd.Series(brk, index=pd.bdate_range("2024-01-01", periods=30)).pct_change()
    new_ret = c3["BRK.BK"].pct_change()
    assert abs(new_ret.loc[dbrk]) < 1e-12, new_ret.loc[dbrk]
    others = new_ret.drop(index=dbrk).iloc[1:]
    assert np.allclose(others.to_numpy(), raw_ret.drop(index=dbrk).iloc[1:].to_numpy())
    assert rep3.applied_breaks and rep3.applied_breaks[0][0] == "BRK.BK" and abs(rep3.applied_breaks[0][2] - brk[15] / brk[14]) < 1e-5
    assert c3["BRK.BK"].iloc[-1] == brk[-1], "prices after the break are untouched"
    print("  OK")

    print("\n" + "=" * 70)
    print("TEST 5: breaks that cannot be applied are reported, not silently ignored")
    print("=" * 70)
    _, _, rep4 = load_clean_closes(["D.BK"], cache_dir=str(cache), breaks={"NOPE.BK": [("2024-01-10", "x")], "D.BK": [("2030-01-01", "x")]})
    reasons = sorted(r[2] for r in rep4.skipped_breaks)
    assert reasons == ["break date not in calendar", "ticker not requested"], reasons
    assert not rep4.applied_breaks
    print("  OK")

    print("\n" + "=" * 70)
    print("TEST 6: cache still unmodified after all calls (except the file added by the test itself)")
    print("=" * 70)
    after = digest(cache)
    assert all(after[k] == v for k, v in before.items())
    print("  OK")

print("\nAll clean-data checks passed.")
