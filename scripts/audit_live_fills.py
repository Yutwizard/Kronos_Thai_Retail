"""Ticket 19 (.scratch/future-plan/19, approved 2026-09-24): are the live paper fills achievable, and how big is
the nominal-vs-dividend-adjusted valuation bias in the ticket-11 review?

Data-input audit only: it computes no live return, benchmark or IC (ticket 11 forbids that before the review).
    python scripts/audit_live_fills.py --selftest                  # hand-made cases, no network, no real data
    python scripts/audit_live_fills.py --download                  # fetch unadjusted OHLC into data/audit/unadjusted/
    python scripts/audit_live_fills.py                             # audit (reads the snapshot + downloaded files)
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

SNAPSHOT = Path.home() / "backups" / "kronos-th-snapshots" / "2026-09-23T222128"
AUDIT_DIR = Path("data/audit/unadjusted")
MODEL_DIR = "NeoQuasar_Kronos-small"
CAPITAL = 500_000.0
DL_START = "2026-05-25"
BIAS_RULE = 0.0025      # apply the fix if |net bias| >= 0.25% of capital
CLASS_C_RULE = 0.10     # "fills partly not achievable" if class C >= 10% of trades or of value
DR_SUFFIXES = ("80.BK", "23.BK", "01.BK", "03.BK", "06.BK", "19.BK")


def tick(price: float) -> float:
    for bound, t in ((2, 0.01), (5, 0.02), (10, 0.05), (25, 0.10), (100, 0.25), (200, 0.50), (400, 1.00)):
        if price < bound:
            return t
    return 2.00


def tolerance(price: float) -> float:
    return max(tick(price), 0.001 * price)


def in_range(price: float, bar) -> bool:
    tol = tolerance(price)
    return bar is not None and bar["Low"] - tol <= price <= bar["High"] + tol


def session_on_or_after(df: pd.DataFrame, day, strictly_after=False):
    idx = df.index[df.index > day] if strictly_after else df.index[df.index >= day]
    return idx[0] if len(idx) else None


def session_on_or_before(df: pd.DataFrame, day):
    idx = df.index[df.index <= day]
    return idx[-1] if len(idx) else None


def classify(row, df: pd.DataFrame | None, lookback_end) -> dict:
    """Class A/B/C/D, the intended session and whether the trade was logged before it."""
    if df is None or df.empty:
        return {"cls": "D", "intended": None, "logged_before_session": None}
    if lookback_end is None:  # off-ticket trade: no forecast to anchor it, so the log-date session is intended
        intended = session_on_or_after(df, row["date"])
    else:
        intended = session_on_or_after(df, lookback_end, strictly_after=True)
    log_day = row["date"] if row["date"] in df.index else None
    bar_i = df.loc[intended] if intended is not None else None
    bar_l = df.loc[log_day] if log_day is not None else None
    if bar_i is None and bar_l is None:
        cls = "D"
    elif in_range(row["price"], bar_i):
        cls = "A"
    elif in_range(row["price"], bar_l):
        cls = "B"
    else:
        cls = "C"
    before = None if (intended is None or lookback_end is None) else bool(row["date"] < intended)
    return {"cls": cls, "intended": intended, "logged_before_session": before}


def adj_factor(df: pd.DataFrame | None, day) -> float | None:
    if df is None or df.empty:
        return None
    s = session_on_or_before(df, day)
    if s is None:
        return None
    c, a = float(df.loc[s, "Close"]), float(df.loc[s, "Adj Close"])
    return a / c if c > 0 else None


ACTION_LISTS = {"buy": ("buys",), "exit": ("exits", "reduces"), "sell": ("exits", "reduces")}


def ticket_entries(positions_dir: Path, day: str, _cache={}) -> dict[str, set]:
    """{ticker: set of ticket lists it appears in} for trade_ticket_<day>.json."""
    key = (str(positions_dir), day)
    if key not in _cache:
        p = positions_dir / f"trade_ticket_{day}.json"
        out = {}
        if p.exists():
            d = json.loads(p.read_text())
            for lst in ("buys", "exits", "reduces"):
                for e in d.get(lst) or []:
                    out.setdefault(e["ticker"], set()).add(lst)
        _cache[key] = out
    return _cache[key]


def source_ticket_date(row, positions_dir: Path) -> str | None:
    """The trade ticket a logged trade came from (the log's own `forecast_date` column is just the entry date).
    Ticket D if it lists the ticker under the matching action (a ticket regenerated after the trade cannot list a
    trade already done), else the latest earlier ticket that does; None = off-ticket trade."""
    lists = ACTION_LISTS.get(row["action"], ())
    days = sorted((p.stem.replace("trade_ticket_", "") for p in positions_dir.glob("trade_ticket_*.json")), reverse=True)
    log_day = str(pd.Timestamp(row["date"]).date())
    for day in days:
        if day > log_day:
            continue
        if ticket_entries(positions_dir, day).get(row["ticker"], set()) & set(lists):
            return day
    return None


def lookback_end_for(row, source_day: str | None, fc_root: Path | None = None) -> pd.Timestamp | None:
    if source_day is None:
        return None
    m = (fc_root or SNAPSHOT / "forecast_cache" / MODEL_DIR) / source_day / f"{row['ticker']}_meta.json"
    if m.exists():
        return pd.Timestamp(json.loads(m.read_text())["lookback_end"]).normalize()
    return pd.Timestamp(source_day)


def download(tickers) -> None:
    import yfinance as yf
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"downloaded_on": str(date.today()), "start": DL_START, "tickers": {}}
    for t in tickers:
        for attempt in range(3):
            try:
                tk = yf.Ticker(t)
                h = tk.history(start=DL_START, auto_adjust=False, actions=True)
                if h.empty:
                    raise ValueError("empty")
                h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
                h.to_parquet(AUDIT_DIR / f"{t}.parquet")
                meta["tickers"][t] = {"rows": len(h), "last": str(h.index[-1].date()),
                                      "dividends": {str(d.date()): float(v) for d, v in h["Dividends"][h["Dividends"] > 0].items()}}
                print(f"  {t}: {len(h)} rows")
                break
            except Exception as e:
                if attempt == 2:
                    meta["tickers"][t] = {"error": str(e)}
                    print(f"  {t}: FAILED {e}")
                time.sleep(2 ** (attempt + 1))
        time.sleep(0.5)
    (AUDIT_DIR / "download_meta.json").write_text(json.dumps(meta, indent=2))


def load_prices(t):
    p = AUDIT_DIR / f"{t}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def audit(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for _, r in trades.iterrows():
        df = load_prices(r["ticker"])
        src = source_ticket_date(r, SNAPSHOT / "positions")
        lb = lookback_end_for(r, src)
        c = classify(r, df, lb)
        f = adj_factor(df, r["date"])
        value = r["shares"] * r["price"]
        sign = 1 if r["action"] == "buy" else -1
        rows.append({**r.to_dict(), "source_ticket": src, "lookback_end": lb, **c, "F": f, "value": value,
                     "bias": None if f is None else sign * value * (1 - f),
                     "kind": "DR" if r["ticker"].endswith(DR_SUFFIXES) else "thai_equity"})
    out = pd.DataFrame(rows)
    n, v = len(out), out["value"].sum()
    c_share_n = (out["cls"] == "C").mean()
    c_share_v = out.loc[out["cls"] == "C", "value"].sum() / v
    net = out["bias"].sum(skipna=True)
    gross_buy = out.loc[out["action"] == "buy", "bias"].sum(skipna=True)
    summary = {
        "trades": n, "traded_value_thb": round(v, 2),
        "class_counts": out["cls"].value_counts().to_dict(),
        "class_value_thb": {k: round(x, 2) for k, x in out.groupby("cls")["value"].sum().items()},
        "class_by_kind": {f"{k}/{c}": int(x) for (k, c), x in out.groupby(["kind", "cls"]).size().items()},
        "logged_before_intended_session": int(out["logged_before_session"].fillna(False).sum()),
        "off_ticket_trades": int(out["source_ticket"].isna().sum()),
        "class_C_share_trades": round(c_share_n, 4), "class_C_share_value": round(c_share_v, 4),
        "fills_partly_not_achievable": bool(c_share_n >= CLASS_C_RULE or c_share_v >= CLASS_C_RULE),
        "net_bias_thb": round(net, 2), "net_bias_share_of_capital": round(net / CAPITAL, 5),
        "gross_buy_bias_thb": round(gross_buy, 2),
        "trades_without_factor": int(out["F"].isna().sum()),
        "apply_total_return_fix": bool(abs(net) / CAPITAL >= BIAS_RULE),
    }
    return out, summary


def selftest() -> None:
    assert tick(1.99) == 0.01 and tick(2.0) == 0.02 and tick(24.9) == 0.10 and tick(131.5) == 0.50 and tick(500) == 2.0
    assert abs(tolerance(131.5) - 0.50) < 1e-12 and abs(tolerance(1000) - 2.0) < 1e-12 and abs(tolerance(3000) - 3.0) < 1e-12
    idx = pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"])
    df = pd.DataFrame({"Low": [9.0, 10.0, 11.0], "High": [9.5, 10.5, 11.5],
                       "Close": [9.2, 10.2, 11.2], "Adj Close": [9.2 * 0.97, 10.2 * 0.97, 11.2]}, index=idx)
    ev = lambda price, logd: {"date": pd.Timestamp(logd), "price": price}
    # evening run: lookback_end = log date 07-02 -> intended 07-03; logged before the session
    c = classify(ev(11.2, "2026-07-02"), df, pd.Timestamp("2026-07-02"))
    assert c["cls"] == "A" and c["intended"] == idx[2] and c["logged_before_session"] is True, c
    c = classify(ev(10.2, "2026-07-02"), df, pd.Timestamp("2026-07-02"))
    assert c["cls"] == "B", c  # only the log-date session reaches it
    c = classify(ev(12.0, "2026-07-02"), df, pd.Timestamp("2026-07-02"))
    assert c["cls"] == "C", c
    c = classify(ev(11.55, "2026-07-02"), df, pd.Timestamp("2026-07-02"))
    assert c["cls"] == "A", c  # within one tick (0.10) of the high
    # morning run: lookback_end 07-01, log 07-02 -> intended 07-02, not logged before it
    c = classify(ev(10.2, "2026-07-02"), df, pd.Timestamp("2026-07-01"))
    assert c["cls"] == "A" and c["logged_before_session"] is False, c
    assert classify(ev(10.0, "2026-07-02"), None, idx[0])["cls"] == "D"
    assert abs(adj_factor(df, pd.Timestamp("2026-07-02")) - 0.97) < 1e-12
    assert abs(adj_factor(df, pd.Timestamp("2026-07-04")) - 1.0) < 1e-12  # weekend -> last session
    # source ticket: a buy listed only in yesterday's buys (today's ticket shows it as a post-trade reduce)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "trade_ticket_2026-07-01.json").write_text(json.dumps({"buys": [{"ticker": "X.BK"}], "exits": [], "reduces": []}))
        (d / "trade_ticket_2026-07-02.json").write_text(json.dumps({"buys": [], "exits": [], "reduces": [{"ticker": "X.BK"}]}))
        (d / "trade_ticket_2026-07-03.json").write_text(json.dumps({"buys": [{"ticker": "X.BK"}], "exits": [], "reduces": []}))
        assert source_ticket_date({"date": "2026-07-02", "ticker": "X.BK", "action": "buy"}, d) == "2026-07-01"
        assert source_ticket_date({"date": "2026-07-02", "ticker": "X.BK", "action": "exit"}, d) == "2026-07-02"
        assert source_ticket_date({"date": "2026-07-03", "ticker": "X.BK", "action": "buy"}, d) == "2026-07-03"
        assert source_ticket_date({"date": "2026-07-03", "ticker": "Y.BK", "action": "buy"}, d) is None
    c = classify(ev(10.2, "2026-07-02"), df, None)  # off-ticket: the log-date session is the intended one
    assert c["cls"] == "A" and c["intended"] == idx[1] and c["logged_before_session"] is None, c
    print("selftest passed (source ticket, tick table, tolerance, classes A-D, intended session both regimes, factor)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--snapshot", help="snapshot folder to audit (default: the 2026-09-23 one; reviews pass theirs)")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    global SNAPSHOT
    if a.snapshot:
        SNAPSHOT = Path(a.snapshot)
    trades = pd.read_csv(SNAPSHOT / "positions" / "trade_log.csv", parse_dates=["date", "forecast_date"])
    if a.download:
        return download(sorted(trades["ticker"].unique()))
    meta = json.loads((AUDIT_DIR / "download_meta.json").read_text())
    out, summary = audit(trades)
    cols = ["date", "ticker", "action", "shares", "price", "source_ticket", "lookback_end", "intended",
            "logged_before_session", "cls", "F", "bias"]
    pd.set_option("display.width", 200)
    print(f"snapshot {SNAPSHOT.name}; unadjusted prices downloaded {meta['downloaded_on']}")
    print(out[cols].to_string())
    print("\ndividends listed by Yahoo after each ticker's first trade (MISMATCH = F<1 on some trade date xor such a dividend)")
    for t, m in meta["tickers"].items():
        f_lt_1 = any((x or 1) < 0.9999 for x in out.loc[out["ticker"] == t, "F"])
        first_trade = out.loc[out["ticker"] == t, "date"].min()
        divs = {d: v for d, v in m.get("dividends", {}).items() if pd.Timestamp(d) > first_trade}
        flag = "  <-- MISMATCH" if f_lt_1 != bool(divs) else ""
        print(f"  {t}: {divs or m.get('error', 'none')}{flag}")
    print("\nSUMMARY", json.dumps(summary, indent=2, default=str))
    # Per-trade factors for live_track_review.py --fill-factors (ticket 19 Q5): used only if the rule says so.
    factors = {"snapshot": SNAPSHOT.name, "apply_total_return_fix": summary["apply_total_return_fix"],
               "F_by_row": {int(i): (None if pd.isna(f) else float(f)) for i, f in out["F"].items()}}
    fpath = AUDIT_DIR.parent / f"fill_factors_{SNAPSHOT.name}.json"
    fpath.write_text(json.dumps(factors, indent=2))
    print(f"factors written to {fpath} (apply_total_return_fix={summary['apply_total_return_fix']})")


if __name__ == "__main__":
    sys.exit(main())
