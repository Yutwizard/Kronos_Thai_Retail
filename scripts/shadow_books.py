"""Forward shadow books (ticket .scratch/future-plan/20, approved 2026-09-24): S1 momentum 12-1 and S2 stock-level
SMA200 filter, run forward next to the Kronos live book and judged against equal-weight of the same universe.

    python scripts/shadow_books.py --record              # append next month's candidate picks (pipeline STEP3b)
    python scripts/shadow_books.py --selftest            # synthetic data only
    python scripts/shadow_books.py --review six-month --root <snapshot>   # refused before its date
Rules are reused unchanged from the tested ticket-06/09 scripts. Design and timing are frozen in ticket 20.
"""
import argparse
import csv
import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import MIN_HIST, N_BOOT, TICKERS, one_sided_p  # noqa: E402
from run_set_candidates import ew_weights, month_first_days, simulate_gross, sma_weights, topn_weights  # noqa: E402

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402
from kth.data.clean import load_clean_closes  # noqa: E402

WINDOW_START = "2026-11-02"
FIRST_TARGET_MONTH = "2026-11"
RECORD_FROM_DAY = 20
HALF_CUT = "2027-04-30"
ALPHA = 0.05 / 3
REVIEWS = {"six-month": ("2027-05-03", None), "twelve-month": ("2027-11-01", ALPHA), "24-month": ("2028-11-01", ALPHA / 2)}
BOOKS = ("S1_momentum_12_1", "S2_sma200")
CAND_COLS = ["recorded_at", "target_month", "signal_date", "book", "ticker", "weight", "score"]


def load_prices(raw_dir, tickers=TICKERS):
    close, real, _ = load_clean_closes(list(tickers), cache_dir=str(raw_dir))
    return close, real


def rule_fns(close, real) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Weight functions of the frozen rules, keyed by book, plus the benchmark; eligibility = 252 closes + real price."""
    elig = (close.notna().cumsum() >= MIN_HIST) & real
    score = close.shift(21) / close.shift(MIN_HIST) - 1  # run_factor_baselines.signals()["momentum_12_1"]
    cols = close.columns
    fns = {"S1_momentum_12_1": topn_weights(elig, score, cols), "S2_sma200": sma_weights(elig, close, cols),
           "benchmark": ew_weights(elig, cols)}
    return fns, elig, score


def read_candidates(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=CAND_COLS)
    return pd.read_csv(path, dtype={"target_month": str, "signal_date": str})


# ---------------------------------------------------------------------------
# Recording (forward honesty)
# ---------------------------------------------------------------------------
def record(raw_dir: Path, cand_path: Path, tickers=TICKERS, now: datetime | None = None) -> str:
    close, real = load_prices(raw_dir, tickers)
    last = close.index[-1]
    if last.day < RECORD_FROM_DAY:
        return f"no record: latest session {last.date()} is before day {RECORD_FROM_DAY} of its month"
    target = (last + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
    if target < FIRST_TARGET_MONTH:
        return f"no record: target month {target} is before {FIRST_TARGET_MONTH}"
    existing = read_candidates(cand_path)
    sig = str(last.date())
    if ((existing["target_month"] == target) & (existing["signal_date"] == sig)).any():
        return f"no record: candidates for {target} with signal {sig} already recorded"
    fns, _, score = rule_fns(close, real)
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    rows = []
    for book in BOOKS:
        w = fns[book](last)
        for t, x in w[w > 0].items():
            s = score.loc[last, t] if book == "S1_momentum_12_1" else close.loc[last, t]
            rows.append([stamp, target, sig, book, t, round(float(x), 10), round(float(s), 6)])
    new = not cand_path.exists()
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cand_path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CAND_COLS)
        w.writerows(rows)
    return f"recorded {len(rows)} candidate rows for {target}, signal {sig}"


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
def book_returns(close, real, cands: pd.DataFrame, start, end) -> tuple[dict, dict]:
    ret = close.pct_change(fill_method=None)
    days = ret.loc[start:end].index
    fns, elig, _ = rule_fns(close, real)
    log = {"months": [str(d.date()) for d in month_first_days(days)], "late_or_missing": [], "revised": []}

    def recorded_fn(book):
        base = fns[book]

        def fn(prev):
            d = ret.index[ret.index.get_loc(prev) + 1]
            month, sig = d.strftime("%Y-%m"), str(prev.date())
            c = cands[(cands["book"] == book) & (cands["target_month"] == month) & (cands["signal_date"] == sig)]
            c = c[pd.to_datetime(c["recorded_at"]).dt.normalize() < d]
            recomputed = base(prev)
            if c.empty:
                log["late_or_missing"].append(f"{book} {month}")
                return recomputed
            w = pd.Series(0.0, index=close.columns)
            w[c["ticker"].to_numpy()] = c["weight"].to_numpy(dtype=float)
            if not np.allclose(w.to_numpy(), recomputed.to_numpy(), atol=1e-9):
                log["revised"].append(f"{book} {month}")
            return w
        return fn

    out = {}
    for book in BOOKS:
        g, c, _ = simulate_gross(ret, elig, days, recorded_fn(book))
        out[book] = g - c
    g, c, _ = simulate_gross(ret, elig, days, fns["benchmark"])
    out["benchmark"] = g - c
    return out, log


def decide(review: str, lo, hi, p, halves_positive) -> str:
    if review == "six-month":
        return "FUTILE (recommend stopping this book)" if hi < 0 else "INCONCLUSIVE (continue; no edge claim)"
    if lo > 0 and p < REVIEWS[review][1] and halves_positive:
        return "EDGE CANDIDATE (discussion only, never automatic)"
    return "NO EDGE SHOWN"


def run_review(root: Path, review: str, as_of, tickers=TICKERS) -> dict:
    close, real = load_prices(root / "raw", tickers)
    cands = read_candidates(root / "positions" / "shadow_candidates.csv")
    rets, log = book_returns(close, real, cands, WINDOW_START, pd.Timestamp(as_of))
    res = {"process_log": {**log, "months": len(log["months"])}}
    for book in BOOKS:
        active = rets[book] - rets["benchmark"]
        cut = pd.Timestamp(HALF_CUT)
        parts = {"H1": active[active.index <= cut].to_numpy()}
        if review != "six-month":
            parts["H2"] = active[(active.index > cut) & (active.index <= cut + pd.DateOffset(months=6))].to_numpy()
            if review == "24-month":
                later = active[active.index > cut + pd.DateOffset(months=6)]
                parts["H3"] = later[later.index <= cut + pd.DateOffset(months=12)].to_numpy()
                parts["H4"] = later[later.index > cut + pd.DateOffset(months=12)].to_numpy()
        ev = evaluate_variant_vs_baseline({k: v for k, v in parts.items() if len(v) > 1}, n_bootstrap=N_BOOT)
        pl, p = ev["pooled"], one_sided_p(active.to_numpy())
        halves = all(r["observed_mean_annualized"] > 0 for r in ev["by_year"].values())
        res[book] = {"days": int(len(active)), "book_total": float((1 + rets[book]).prod() - 1),
                     "bench_total": float((1 + rets["benchmark"]).prod() - 1),
                     "active_ann": pl["observed_mean_annualized"],
                     "active_ci": (pl["ci_2_5_annualized"], pl["ci_97_5_annualized"]), "one_sided_p": p,
                     "halves_positive": halves,
                     "verdict": decide(review, pl["ci_2_5_annualized"], pl["ci_97_5_annualized"], p, halves)}
    return res


def guard(review: str | None, as_of: date) -> None:
    if review not in REVIEWS:
        raise SystemExit(f"REFUSED: pass --review {' | '.join(REVIEWS)}")
    due = date.fromisoformat(REVIEWS[review][0])
    if as_of < due:
        raise SystemExit(f"REFUSED: the {review} shadow-book review is not due until {due} (as-of {as_of}). "
                         "Ticket 20 forbids comparing the books with the benchmark before then.")


# ---------------------------------------------------------------------------
# Self-test (synthetic data only)
# ---------------------------------------------------------------------------
def _write_synthetic(raw: Path, dates, n=14, seed=3) -> list:
    rng = np.random.default_rng(seed)
    raw.mkdir(parents=True, exist_ok=True)
    tickers = [f"SYN{i:02d}.BK" for i in range(n)]
    for i, t in enumerate(tickers):
        drift = 0.0015 * (i - n / 2) / n  # persistent drifts give momentum something to rank
        px = 10 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(dates))))
        pd.DataFrame({"timestamps": dates, "open": px, "high": px * 1.01, "low": px * 0.99, "close": px,
                      "volume": 1e6, "amount": px * 1e6}).to_parquet(raw / f"{t}.parquet")
    return tickers


def selftest() -> None:
    dates = pd.bdate_range("2024-06-03", "2027-12-31")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        tickers = _write_synthetic(d / "full" / "raw", dates)
        cand = d / "full" / "positions" / "shadow_candidates.csv"
        # 1) recording: before day 20 nothing; on 2026-10-23 picks for 2026-11; idempotent; before Nov target nothing
        for cutoff, expect in (("2026-10-16", "no record"), ("2026-10-23", "recorded"), ("2026-10-23", "no record"),
                               ("2026-09-25", "no record"), ("2026-10-30", "recorded")):
            part = d / f"cut_{cutoff}" / "raw"
            if not part.exists():
                for t in tickers:
                    df = pd.read_parquet(d / "full" / "raw" / f"{t}.parquet")
                    part.mkdir(parents=True, exist_ok=True)
                    df[df["timestamps"] <= cutoff].to_parquet(part / f"{t}.parquet")
            msg = record(part, cand, tickers, now=datetime.fromisoformat(cutoff + "T23:00:00"))
            assert msg.startswith(expect), (cutoff, msg)
        c = read_candidates(cand)
        assert set(c["signal_date"]) == {"2026-10-23", "2026-10-30"} and set(c["target_month"]) == {"2026-11"}, c
        s1 = c[(c["book"] == "S1_momentum_12_1") & (c["signal_date"] == "2026-10-30")]
        assert len(s1) == 10 and abs(s1["weight"].sum() - 1) < 1e-9, s1
        # 2) review: November uses the 2026-10-30 candidate (the session before 2026-11-02); later months are
        #    recomputed and logged as late; a tampered recorded weight is used as recorded and logged as revised
        close, real = load_prices(d / "full" / "raw", tickers)
        rets, log = book_returns(close, real, c, WINDOW_START, pd.Timestamp("2027-11-01"))
        assert "S1_momentum_12_1 2026-11" not in log["late_or_missing"] and "S1_momentum_12_1 2026-12" in log["late_or_missing"]
        assert log["revised"] == [], log["revised"]
        t2 = c.copy()
        mask = (t2["book"] == "S1_momentum_12_1") & (t2["signal_date"] == "2026-10-30")
        only = t2[mask].iloc[0]["ticker"]
        t2 = pd.concat([t2[~mask], t2[mask].iloc[[0]].assign(weight=1.0)])  # all-in one name
        rets2, log2 = book_returns(close, real, t2, WINDOW_START, pd.Timestamp("2027-11-01"))
        assert "S1_momentum_12_1 2026-11" in log2["revised"], log2
        first = pd.Timestamp(WINDOW_START)
        r1 = close[only].pct_change().loc[first]
        from run_factor_baselines import ONE_WAY
        assert abs(rets2["S1_momentum_12_1"].loc[first] - (r1 - ONE_WAY)) < 1e-12  # recorded picks drive the book
        # a candidate recorded on/after the month's first session does not count
        late = c.assign(recorded_at="2026-11-02T20:00:00")
        _, log3 = book_returns(close, real, late, WINDOW_START, pd.Timestamp("2026-12-31"))
        assert "S1_momentum_12_1 2026-11" in log3["late_or_missing"]
        # 3) decisions and guard
        assert decide("six-month", -0.3, -0.01, 0.9, False).startswith("FUTILE")
        assert decide("six-month", 0.1, 0.4, 0.001, True).startswith("INCONCLUSIVE")
        assert decide("twelve-month", 0.01, 0.4, 0.01, True).startswith("EDGE")
        assert decide("twelve-month", 0.01, 0.4, 0.02, True).startswith("NO EDGE")  # 0.02 > 0.0167
        assert decide("24-month", 0.01, 0.4, 0.01, True).startswith("NO EDGE")      # 0.01 > 0.0083
        for bad, when in (("six-month", date(2027, 5, 2)), ("twelve-month", date(2027, 10, 29)), (None, date(2030, 1, 1))):
            try:
                guard(bad, when); raise AssertionError("guard did not refuse")
            except SystemExit:
                pass
        guard("twelve-month", date(2027, 11, 1))
        # 4) end to end on the synthetic snapshot layout
        res = run_review(d / "full", "twelve-month", date(2027, 11, 1), tickers)
        assert res["S1_momentum_12_1"]["days"] > 200 and np.isfinite(res["S2_sma200"]["one_sided_p"]), res
    print("selftest passed (record window/idempotence, effective picks, late/revised logging, cost, decisions, guard)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--review", choices=list(REVIEWS))
    ap.add_argument("--as-of", default=str(date.today()))
    ap.add_argument("--root", default="data")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.record:
        print(record(Path(a.root) / "raw", Path(a.root) / "positions" / "shadow_candidates.csv"))
        return
    as_of = date.fromisoformat(a.as_of)
    guard(a.review, as_of)
    root = Path(a.root)
    if (root / "MANIFEST.sha256").exists():
        from snapshot_live_data import verify
        bad = verify(root)
        if bad:
            raise SystemExit(f"snapshot {root} fails its hash check, first: {bad[:3]}")
    res = run_review(root, a.review, as_of)
    print(f"SHADOW-BOOK REVIEW ({a.review}), window {WINDOW_START} .. {as_of}, data {root.resolve()}")
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
