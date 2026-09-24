"""Pre-committed review of the live paper track (ticket .scratch/future-plan/11, approved 2026-09-21).

Real-data use is REFUSED before the review date (guard below). Test it with:
    python scripts/live_track_review.py --selftest        # asserts on hand-computed cases
    python scripts/live_track_review.py --synthetic       # end-to-end on generated data
Real reviews (only on/after the date):
    python scripts/live_track_review.py --review six-month      # >= 2026-12-30, futility only
    python scripts/live_track_review.py --review twelve-month   # >= 2027-06-30, the edge decision
Design is frozen in ticket 11; do not change parameters after seeing a live result.
"""
import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_factor_baselines import N_BOOT, ONE_WAY, one_sided_p  # noqa: E402

from kth.backtest.metrics import evaluate_variant_vs_baseline  # noqa: E402

WINDOW_START = "2026-06-26"
REVIEW_DATES = {"six-month": "2026-12-30", "twelve-month": "2027-06-30"}
INITIAL_CAPITAL = 500_000.0
IC_HORIZON = 20
MIN_IC_NAMES = 10
STUB_DATE_SHARE = 0.5  # >= half of tickers stubbed on a date -> drop the date (as check_data_sanity.py)
BLOCK_SEED = 42
MODEL_DIR = "NeoQuasar_Kronos-small"

FROZEN_THAI_EQUITY = (
    "ADVANC.BK", "AOT.BK", "AP.BK", "BANPU.BK", "BBL.BK", "BCH.BK", "BCP.BK", "BDMS.BK", "BEM.BK",
    "BGRIM.BK", "BH.BK", "BTS.BK", "CENTEL.BK", "CHG.BK", "CPALL.BK", "CPF.BK", "CPN.BK", "CPNREIT.BK",
    "CRC.BK", "DELTA.BK", "DOHOME.BK", "ERW.BK", "GLOBAL.BK", "GPSC.BK", "GULF.BK", "HANA.BK", "HMPRO.BK",
    "ICHI.BK", "IRPC.BK", "IVL.BK", "JMART.BK", "KBANK.BK", "KKP.BK", "KTB.BK", "LH.BK", "MEGA.BK",
    "MINT.BK", "ORI.BK", "OSP.BK", "PSH.BK", "PTT.BK", "PTTEP.BK", "QH.BK", "RATCH.BK", "SCB.BK", "SCC.BK",
    "SIRI.BK", "TCAP.BK", "TISCO.BK", "TOP.BK", "TRUE.BK",
)

FROZEN_DR = (
    "ASML01.BK", "BABA80.BK", "BIDU80.BK", "BYDCOM80.BK", "CATL80.BK", "CMBANK23.BK", "FERRARI80.BK",
    "GEELY80.BK", "HERMES80.BK", "HORIZON23.BK", "JD80.BK", "KEYENCE23.BK", "KINGSOFT23.BK", "KUAISH80.BK",
    "LOREAL80.BK", "LVMH01.BK", "MEITUAN80.BK", "NETEASE80.BK", "NONGFU80.BK", "NOVOB80.BK", "PETROCN80.BK",
    "POPMART80.BK", "SANOFI80.BK", "SANRIO23.BK", "SENSE23.BK", "SINGTEL80.BK", "SOFTBANK23.BK", "SONY80.BK",
    "SUSHI23.BK", "TEL23.BK", "TENCENT80.BK", "TOYOTA80.BK", "UBTECH23.BK", "UNIQLO80.BK", "XIAOMI80.BK",
    "ZIJIN80.BK",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def sanitize(t: str) -> str:
    return t.replace("^", "_").replace("=", "_")


def load_frames(raw_dir: Path, tickers) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (close, real) frames on the union calendar. `real` is True where the ticker has a
    real (non-stub) price that day: volume > 0 and not a flat zero-volume row."""
    close, real = {}, {}
    for t in tickers:
        p = raw_dir / f"{sanitize(t)}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"missing price file for {t}: {p}")
        d = pd.read_parquet(p)
        d.index = pd.to_datetime(d["timestamps"])
        stub = (d["volume"] == 0) & (d["open"] == d["high"]) & (d["high"] == d["low"]) & (d["low"] == d["close"])
        close[t] = d["close"]
        real[t] = (d["volume"] > 0) & ~stub
    close = pd.DataFrame(close).sort_index()
    real = pd.DataFrame(real).reindex(close.index).fillna(False)
    return close, real


def drop_stub_dates(close: pd.DataFrame, real: pd.DataFrame):
    """Drop calendar dates where >= half of the tickers have no real price."""
    share_stub = 1.0 - real.sum(axis=1) / real.shape[1]
    bad = share_stub[share_stub >= STUB_DATE_SHARE].index
    return close.drop(index=bad), real.drop(index=bad), list(bad)


def load_trades(path: Path) -> pd.DataFrame:
    t = pd.read_csv(path, parse_dates=["date"])
    bad = set(t["action"]) - {"buy", "exit"}
    if bad:
        raise ValueError(f"unknown trade actions in log: {bad}")
    t["row"] = t.index  # position in the log, the key of the ticket-19 fill-factor file
    return t.sort_values("date", kind="stable").reset_index(drop=True)


def add_apply_dates(trades: pd.DataFrame, close: pd.DataFrame, positions_dir: Path, fc_root: Path) -> pd.DataFrame:
    """Ticket 19 Q6: a trade applies on the LATER of its intended session (the ticker's first priced session after
    the source forecast's lookback_end; source rule in audit_live_fills.py) and its log date: never before the order
    could fill, never before it was recorded. A recorded `fill_date` (Q7, from 2026-09-24) is used as is."""
    from audit_live_fills import lookback_end_for, source_ticket_date
    out = []
    for _, r in trades.iterrows():
        if "fill_date" in trades.columns and pd.notna(r.get("fill_date")) and str(r["fill_date"]).strip():
            out.append(pd.Timestamp(r["fill_date"]).normalize())
            continue
        src = source_ticket_date(r, positions_dir)
        lb = lookback_end_for(r, src, fc_root)
        d = r["date"]
        if lb is not None and r["ticker"] in close.columns:
            later = close[r["ticker"]].dropna().index
            later = later[later > lb]
            if len(later):
                d = max(later[0], r["date"])
        out.append(d)
    t = trades.assign(apply_date=out)
    return t.sort_values(["apply_date", "row"], kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Live book and benchmark
# ---------------------------------------------------------------------------
def live_values(trades: pd.DataFrame, close: pd.DataFrame, start, end, capital=INITIAL_CAPITAL,
                fill_factors: dict | None = None) -> pd.Series:
    """Daily portfolio value = cash + shares x close, rebuilt from the trade log. Trades dated on or before
    `start` set the starting state; later trades apply on their date (`apply_date` if present, ticket 19 Q6,
    else the log date), or the next calendar date.
    fill_factors (ticket 19 Q5, only when the pre-review audit requires it): {log row: F = adj/unadj close on the
    trade date}. Holdings are then tracked as effective shares n / F, so a buy is worth exactly its cost that day
    and an exit's cash includes the dividends earned while held (total-return accounting, like the benchmark)."""
    cal = close.loc[start:end].index
    px = close.ffill(limit=10)
    when = "apply_date" if "apply_date" in trades.columns else "date"
    cash, shares, eff = float(capital), {}, {}

    def factor(row):
        f = (fill_factors or {}).get(int(getattr(row, "row", -1)))
        return 1.0 if f is None else float(f)

    def apply(row):
        nonlocal cash
        gross = row.shares * row.price
        held = shares.get(row.ticker, 0)
        if row.action == "buy":
            cash -= gross + row.friction_cost
            shares[row.ticker] = held + row.shares
            eff[row.ticker] = eff.get(row.ticker, 0.0) + row.shares / factor(row)
        else:
            if row.shares > held:
                raise ValueError(f"sold more than held: {row.ticker} on {getattr(row, when).date()}")
            removed = eff.get(row.ticker, 0.0) * row.shares / held
            cash += removed * row.price * factor(row) - row.friction_cost
            shares[row.ticker] = held - row.shares
            eff[row.ticker] = eff.get(row.ticker, 0.0) - removed
    pre = trades[trades[when] <= pd.Timestamp(start)]
    for row in pre.itertuples():
        apply(row)
    post = trades[trades[when] > pd.Timestamp(start)].reset_index(drop=True)
    out, k = {}, 0
    for d in cal:
        while k < len(post) and post.loc[k, when] <= d:
            apply(next(post.iloc[[k]].itertuples()))
            k += 1
        held = {t: e for t, e in eff.items() if shares.get(t)}
        missing = [t for t in held if t not in px.columns]
        if missing:
            raise KeyError(f"held tickers without price data: {missing}")
        out[d] = cash + sum(e * px.loc[d, t] for t, e in held.items())
    return pd.Series(out)


def benchmark_returns(close: pd.DataFrame, real: pd.DataFrame, start, end) -> pd.Series:
    """Equal-weight, monthly rebalanced (first day of the window and first trading day of each month), price-only
    eligibility at the prior close, ONE_WAY friction on turnover, weights drift between rebalances."""
    ret = close.ffill(limit=10).pct_change(fill_method=None)
    days = close.loc[start:end].index[1:]  # returns start the day after `start`
    w = pd.Series(0.0, index=close.columns)
    out, last_month = {}, None
    for d in days:
        prev = close.index[close.index.get_loc(d) - 1]
        cost = 0.0
        if last_month is None or d.month != last_month:
            last_month = d.month
            names = real.loc[prev][real.loc[prev]].index
            target = pd.Series(0.0, index=close.columns)
            if len(names):
                target[names] = 1.0 / len(names)
            t_o = float((target - w).abs().sum())
            cost, w = t_o * ONE_WAY, target
        r = ret.loc[d].fillna(0.0)
        day = float((w * r).sum())
        out[d] = day - cost
        g = 1.0 + day
        w = w * (1.0 + r) / g if g > 0 else w
    return pd.Series(out)


# ---------------------------------------------------------------------------
# Signal quality: rank IC of the logged 20-day expected return vs realised 20-day return
# ---------------------------------------------------------------------------
def rank_ic_series(fc_root: Path, close: pd.DataFrame, tickers, start, as_of) -> pd.Series:
    cal = close.index
    out = {}
    for folder in sorted(p for p in fc_root.iterdir() if p.is_dir()):
        day = pd.Timestamp(folder.name)
        if day < pd.Timestamp(start) or day > pd.Timestamp(as_of):
            continue
        exp, real = {}, {}
        for t in tickers:
            f, m = folder / f"{t}.parquet", folder / f"{t}_meta.json"
            if not f.exists() or not m.exists():
                continue
            lb = pd.Timestamp(json.loads(m.read_text())["lookback_end"]).normalize()
            if lb not in cal:
                continue
            i = cal.get_loc(lb)
            if i + IC_HORIZON >= len(cal) or cal[i + IC_HORIZON] > pd.Timestamp(as_of):
                continue  # realised horizon not elapsed yet
            fc = pd.read_parquet(f)
            p50 = fc.loc[fc["timestamps"] == IC_HORIZON, "p50"]
            base, fut = close[t].iloc[i], close[t].iloc[i + IC_HORIZON]
            if p50.empty or not np.isfinite(base) or not np.isfinite(fut) or base <= 0:
                continue
            exp[t], real[t] = float(p50.iloc[0]) / base - 1.0, fut / base - 1.0
        if len(exp) >= MIN_IC_NAMES:
            out[day] = pd.Series(exp).corr(pd.Series(real), method="spearman")
    return pd.Series(out, dtype=float)


def input_window_stub_share(fc_root: Path, raw_dir: Path, tickers, start, as_of, lookback: int = 400) -> dict:
    """Process log only (ticket 12): stub rows inside each forecast's 400-row model input window, read from
    the ticker's own raw rows up to its `lookback_end`. Never used to adjust a result."""
    stub_rows, windows = {}, []
    for t in tickers:
        p = raw_dir / f"{sanitize(t)}.parquet"
        if p.exists():
            d = pd.read_parquet(p)
            flat = (d["volume"] == 0) & (d["open"] == d["high"]) & (d["high"] == d["low"]) & (d["low"] == d["close"])
            stub_rows[t] = pd.Series(flat.to_numpy(), index=pd.to_datetime(d["timestamps"]).dt.normalize())
    for folder in sorted(p for p in fc_root.iterdir() if p.is_dir()):
        day = pd.Timestamp(folder.name)
        if day < pd.Timestamp(start) or day > pd.Timestamp(as_of):
            continue
        for t, flat in stub_rows.items():
            m = folder / f"{t}_meta.json"
            if m.exists():
                lb = pd.Timestamp(json.loads(m.read_text())["lookback_end"]).normalize()
                windows.append(int(flat.loc[:lb].tail(lookback).sum()))
    if not windows:
        return {"windows": 0}
    w = np.array(windows)
    return {"windows": int(len(w)), "mean_stub_rows_per_window": round(float(w.mean()), 2),
            "share_windows_ge_4_stub_rows": round(float((w >= 4).mean()), 3), "max_stub_rows": int(w.max())}


def mean_ci(x: np.ndarray, seed: int = BLOCK_SEED) -> tuple[float, float, float]:
    """Stationary block bootstrap 95% CI of a mean (not annualised)."""
    n = len(x)
    if n < 5:
        return float(np.mean(x)) if n else float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    blk = max(int(n ** (1 / 3)), 2)
    means = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx, i = np.empty(n, dtype=int), 0
        while i < n:
            s, ln = rng.integers(0, n), min(rng.geometric(1 / blk), n - i)
            idx[i:i + ln] = (s + np.arange(ln)) % n
            i += ln
        means[b] = x[idx].mean()
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


# ---------------------------------------------------------------------------
# Decision rule (frozen in ticket 11)
# ---------------------------------------------------------------------------
def decide(review: str, active_ci_low, active_ci_high, active_p, halves_positive, ic_low, ic_high) -> str:
    if review == "six-month":
        if active_ci_high < 0 and ic_high < 0:
            return "FUTILE: pooled active-return CI and rank-IC CI are both entirely below 0 (recommendation to the user only)"
        return "INCONCLUSIVE: continue to twelve months; no edge claim (power is too low at six months)"
    if active_ci_low > 0 and active_p < 0.05 and halves_positive and ic_low > 0:
        return "EDGE CANDIDATE: worth a small real-capital discussion, never automatic (compare logged vs achievable prices first)"
    return "NO EDGE DEMONSTRATED: stays a forecasting/monitoring tool"


def guard(review: str | None, as_of: date) -> None:
    if review not in REVIEW_DATES:
        raise SystemExit("real-data runs require --review six-month|twelve-month (or use --synthetic / --selftest)")
    if as_of < date.fromisoformat(REVIEW_DATES[review]):
        raise SystemExit(f"REFUSED: the {review} review is not due until {REVIEW_DATES[review]} (as-of {as_of}). "
                         "Ticket 11 forbids comparing the live track with the benchmark before the review date.")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_review(root: Path, eq, dr, review: str, as_of, start=WINDOW_START, capital=INITIAL_CAPITAL,
               fill_factors: dict | None = None) -> dict:
    tickers = list(eq) + list(dr)
    close, real = load_frames(root / "raw", tickers)
    close, real, dropped = drop_stub_dates(close, real)
    trades = add_apply_dates(load_trades(root / "positions" / "trade_log.csv"), close, root / "positions",
                             root / "forecast_cache" / MODEL_DIR)
    end = pd.Timestamp(as_of)
    live = live_values(trades, close, start, end, capital, fill_factors)
    live_ret = live.pct_change().dropna()
    bench = benchmark_returns(close, real, start, end)
    common = live_ret.index.intersection(bench.index)
    active = (live_ret.loc[common] - bench.loc[common])
    half_cut = pd.Timestamp(REVIEW_DATES["six-month"])
    parts = {"H1": active[active.index <= half_cut].to_numpy()}
    if review == "twelve-month":
        parts["H2"] = active[active.index > half_cut].to_numpy()
    ev = evaluate_variant_vs_baseline({k: v for k, v in parts.items() if len(v) > 1}, n_bootstrap=N_BOOT)
    p = one_sided_p(active.to_numpy())
    ic = rank_ic_series(root / "forecast_cache" / MODEL_DIR, close, eq, start, as_of)
    ic_mean, ic_lo, ic_hi = mean_ci(ic.to_numpy()) if len(ic) else (float("nan"),) * 3
    halves_pos = all(res["observed_mean_annualized"] > 0 for res in ev["by_year"].values())
    pl = ev["pooled"]
    verdict = decide(review, pl["ci_2_5_annualized"], pl["ci_97_5_annualized"], p, halves_pos, ic_lo, ic_hi)
    tickets = {p.stem.replace("trade_ticket_", "") for p in (root / "positions").glob("trade_ticket_*.json")}
    process = {
        "trading_days_in_window": int(len(common)),
        "stub_calendar_dates_dropped": len(dropped),
        "trading_days_without_trade_ticket": sorted(str(d.date()) for d in common if str(d.date()) not in tickets),
        "trades_in_log": int(len(trades)),
        "trades_applied_after_log_date": int((trades["apply_date"] > trades["date"]).sum()),
        "total_return_fill_factors_used": fill_factors is not None,
        "ic_forecast_dates_used": int(len(ic)),
        "input_window_stub_rows": input_window_stub_share(root / "forecast_cache" / MODEL_DIR, root / "raw", eq, start, as_of),
    }
    return {"live_total_return": float(live.iloc[-1] / live.iloc[0] - 1), "bench_total_return": float((1 + bench.loc[common]).prod() - 1),
            "pooled_active_ann": pl["observed_mean_annualized"], "active_ci": (pl["ci_2_5_annualized"], pl["ci_97_5_annualized"]),
            "one_sided_p": p, "halves_positive": halves_pos, "mean_ic": ic_mean, "ic_ci": (ic_lo, ic_hi), "verdict": verdict,
            "process_log": process}


def print_report(res: dict, review: str, as_of) -> None:
    print(f"LIVE PAPER-TRACK REVIEW ({review}), window {WINDOW_START} .. {as_of}")
    print(f"  live total return {res['live_total_return']:+.2%}   benchmark total return {res['bench_total_return']:+.2%}")
    lo, hi = res["active_ci"]
    print(f"  pooled active return (annualised) {res['pooled_active_ann']:+.1%}  95% CI [{lo:+.1%}, {hi:+.1%}]  one-sided p {res['one_sided_p']:.4f}")
    print(f"  positive in every evaluated half: {res['halves_positive']}")
    ilo, ihi = res["ic_ci"]
    print(f"  mean rank IC {res['mean_ic']:+.3f}  95% CI [{ilo:+.3f}, {ihi:+.3f}]")
    print(f"  VERDICT: {res['verdict']}")
    log = dict(res["process_log"])
    missing = log.pop("trading_days_without_trade_ticket")
    log["trading_days_without_trade_ticket_count"] = len(missing)
    log["first_missing_ticket_days"] = missing[:5]
    print("  process log:", json.dumps(log, indent=2))


# ---------------------------------------------------------------------------
# Synthetic data and self-tests (no real data is touched)
# ---------------------------------------------------------------------------
def make_synthetic(root: Path, seed: int = 7, n_eq: int = 14, n_days: int = 400, signal: float = 0.0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-11-03", periods=n_days)
    eq = [f"SYN{i:02d}.BK" for i in range(n_eq)]
    (root / "raw").mkdir(parents=True); (root / "positions").mkdir(); fc_root = root / "forecast_cache" / MODEL_DIR; fc_root.mkdir(parents=True)
    px = {}
    for t in eq:
        r = rng.normal(0.0003, 0.015, n_days)
        c = 20 * np.exp(np.cumsum(r)); px[t] = c
        vol = rng.integers(1_000, 50_000, n_days).astype(float)
        pd.DataFrame({"timestamps": dates, "open": c * 0.999, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": vol,
                      "amount": c * vol}).to_parquet(root / "raw" / f"{t}.parquet")
    start_i = int(np.searchsorted(dates, pd.Timestamp(WINDOW_START)))
    rows = [dict(date=dates[start_i - 3], ticker=eq[0], action="buy", shares=1000, price=float(px[eq[0]][start_i - 3]), order_type="limit",
                 mode="paper", rationale="", friction_cost=50.0, model_version="syn", forecast_date=str(dates[start_i - 3].date()))]
    rows.append(dict(date=dates[start_i + 10], ticker=eq[1], action="buy", shares=500, price=float(px[eq[1]][start_i + 10]), order_type="market",
                     mode="paper", rationale="", friction_cost=30.0, model_version="syn", forecast_date=str(dates[start_i + 10].date())))
    rows.append(dict(date=dates[start_i + 60], ticker=eq[0], action="exit", shares=1000, price=float(px[eq[0]][start_i + 60]), order_type="market",
                     mode="paper", rationale="", friction_cost=50.0, model_version="syn", forecast_date=str(dates[start_i + 60].date())))
    pd.DataFrame(rows).to_csv(root / "positions" / "trade_log.csv", index=False)
    for i in range(start_i, n_days - IC_HORIZON):
        day = dates[i]
        (fc_root / str(day.date())).mkdir()
        for t in eq:
            future = px[t][i + IC_HORIZON] / px[t][i] - 1
            p50 = px[t][i] * (1 + signal * future + rng.normal(0, 0.02))
            pd.DataFrame({"timestamps": range(1, 31), "p5": p50, "p25": p50, "p50": p50, "p75": p50, "p95": p50, "mean": p50, "ticker": t}
                         ).to_parquet(fc_root / str(day.date()) / f"{t}.parquet")
            (fc_root / str(day.date()) / f"{t}_meta.json").write_text(json.dumps({"lookback_end": str(day)}))
        (root / "positions" / f"trade_ticket_{day.date()}.json").write_text("{}")
    return eq, dates


def selftest() -> None:
    idx = pd.bdate_range("2026-06-24", periods=6)
    # 1) live value: buy 10 @10 with friction 1 on d1 -> cash 1000-101, value at close 11 = 899 + 110
    close = pd.DataFrame({"A.BK": [10, 10, 11, 12, 12, 12.0]}, index=idx)
    trades = pd.DataFrame([dict(date=idx[2], ticker="A.BK", action="buy", shares=10, price=10.0, friction_cost=1.0)])
    v = live_values(trades, close, idx[1], idx[-1], capital=1000.0)
    assert abs(v.iloc[0] - 1000.0) < 1e-9 and abs(v.loc[idx[2]] - (899.0 + 110.0)) < 1e-9, v
    assert abs(v.iloc[-1] - (899.0 + 120.0)) < 1e-9
    # exit: sell 10 @12 on last day with friction 2 -> cash 899 + 120 - 2
    t2 = pd.concat([trades, pd.DataFrame([dict(date=idx[5], ticker="A.BK", action="exit", shares=10, price=12.0, friction_cost=2.0)])], ignore_index=True)
    assert abs(live_values(t2, close, idx[1], idx[-1], capital=1000.0).iloc[-1] - (899 + 120 - 2)) < 1e-9
    # 1b) ticket 19 Q5: F = 0.9 on the buy (later dividends of 10%), 1.0 on the exit. A buy is worth its cost on
    # the day (10 shares/0.9 x adjusted close 9 = 100), and the exit's cash adds the dividend: 10/0.9 x 12 x 1.0
    adj = pd.DataFrame({"A.BK": [9, 9, 9, 10.8, 12, 12.0]}, index=idx)
    t3 = pd.concat([trades.assign(row=0), pd.DataFrame([dict(date=idx[5], ticker="A.BK", action="exit", shares=10,
                   price=12.0, friction_cost=0.0, row=1)])], ignore_index=True)
    v3 = live_values(t3, adj, idx[1], idx[-1], capital=1000.0, fill_factors={0: 0.9, 1: 1.0})
    assert abs(v3.loc[idx[2]] - (899.0 + 100.0)) < 1e-9, v3
    assert abs(v3.iloc[-1] - (899.0 + 10 / 0.9 * 12.0)) < 1e-9, v3
    assert abs(live_values(t3, adj, idx[1], idx[-1], capital=1000.0).loc[idx[2]] - (899.0 + 90.0)) < 1e-9  # unfixed
    # 1c) ticket 19 Q6: a trade logged on d2 from a forecast with lookback_end d2 applies on d3
    with tempfile.TemporaryDirectory() as d:
        d = Path(d); fc = d / "fc"; (fc / str(idx[2].date())).mkdir(parents=True)
        (fc / str(idx[2].date()) / "A.BK_meta.json").write_text(json.dumps({"lookback_end": str(idx[2])}))
        (d / f"trade_ticket_{idx[2].date()}.json").write_text(json.dumps({"buys": [{"ticker": "A.BK"}]}))
        ta = add_apply_dates(trades.assign(row=0), close, d, fc)
        assert ta.loc[0, "apply_date"] == idx[3], ta
        va = live_values(ta, close, idx[1], idx[-1], capital=1000.0)
        assert abs(va.loc[idx[2]] - 1000.0) < 1e-9 and abs(va.loc[idx[3]] - (899.0 + 120.0)) < 1e-9, va
        late = trades.assign(row=0, date=idx[4])  # entered two sessions after its intended one -> the log date
        assert add_apply_dates(late, close, d, fc).loc[0, "apply_date"] == idx[4]
        filled = trades.assign(row=0, fill_date=str(idx[5].date()))  # a recorded fill_date wins
        assert add_apply_dates(filled, close, d, fc).loc[0, "apply_date"] == idx[5]
    # 2) benchmark: two flat tickers, first day pays ONE_WAY on turnover 1.0
    c2 = pd.DataFrame({"A": [10.0] * 6, "B": [5.0] * 6}, index=idx); r2 = pd.DataFrame(True, index=idx, columns=["A", "B"])
    b = benchmark_returns(c2, r2, idx[1], idx[-1])
    assert abs(b.iloc[0] + ONE_WAY) < 1e-12 and (b.iloc[1:].abs() < 1e-12).all(), b
    # price-only eligibility: a stubbed ticker at the prior close is excluded from that month
    r3 = r2.copy(); r3.loc[idx[1], "B"] = False
    c3 = pd.DataFrame({"A": [10.0] * 6, "B": [5, 5, 5.5, 5.5, 5.5, 5.5]}, index=idx)
    assert abs(benchmark_returns(c3, r3, idx[1], idx[-1]).iloc[0] + ONE_WAY) < 1e-12  # only A held: turnover 1, B's +10% ignored
    # 3) stub dates dropped when >= half the tickers are stubbed
    rr = pd.DataFrame({"A": [True, False, True], "B": [True, False, True], "C": [True, True, True]}, index=idx[:3])
    _, _, dropped = drop_stub_dates(pd.DataFrame(1.0, index=idx[:3], columns=list("ABC")), rr)
    assert dropped == [idx[1]], dropped
    # 4) decision rules
    assert decide("six-month", -0.5, -0.1, 0.9, False, -0.2, -0.05).startswith("FUTILE")
    assert decide("six-month", -0.5, 0.1, 0.9, False, -0.2, -0.05).startswith("INCONCLUSIVE")
    assert decide("six-month", 0.1, 0.5, 0.01, True, 0.05, 0.2).startswith("INCONCLUSIVE")  # no edge at six months, ever
    assert decide("twelve-month", 0.05, 0.4, 0.01, True, 0.02, 0.1).startswith("EDGE")
    assert decide("twelve-month", 0.05, 0.4, 0.01, False, 0.02, 0.1).startswith("NO EDGE")
    # 5) guard refuses early real runs and unknown review names
    for bad_review, when in (("six-month", date(2026, 12, 29)), (None, date(2027, 7, 1)), ("twelve-month", date(2027, 6, 29))):
        try:
            guard(bad_review, when); raise AssertionError("guard did not refuse")
        except SystemExit:
            pass
    guard("six-month", date(2026, 12, 30)); guard("twelve-month", date(2027, 6, 30))
    # 6) rank IC: forecasts equal to the realised return give IC = 1, pure noise ~ 0
    with tempfile.TemporaryDirectory() as d:
        eq, dates = make_synthetic(Path(d), signal=1.0, n_eq=14)
        close, _ = load_frames(Path(d) / "raw", eq)
        ic = rank_ic_series(Path(d) / "forecast_cache" / MODEL_DIR, close, eq, WINDOW_START, dates[-1])
        assert len(ic) > 50 and ic.mean() > 0.8, ic.describe()
    with tempfile.TemporaryDirectory() as d:
        eq, dates = make_synthetic(Path(d), signal=0.0, n_eq=14)
        close, _ = load_frames(Path(d) / "raw", eq)
        ic0 = rank_ic_series(Path(d) / "forecast_cache" / MODEL_DIR, close, eq, WINDOW_START, dates[-1])
        assert abs(ic0.mean()) < 0.15, ic0.mean()
        # horizon not elapsed => those dates are skipped: stop as-of early and the series shortens
        ic_short = rank_ic_series(Path(d) / "forecast_cache" / MODEL_DIR, close, eq, WINDOW_START, dates[-1] - pd.Timedelta(days=60))
        assert len(ic_short) < len(ic0)
    # 7) process-log stub count: 3 stub rows before lookback_end, 1 after (must not count), lookback 5
    with tempfile.TemporaryDirectory() as d:
        d = Path(d); (d / "raw").mkdir(); fc = d / "fc"; (fc / "2026-07-01").mkdir(parents=True)
        idx7 = pd.bdate_range("2026-06-22", periods=10)
        vol = [1, 1, 0, 1, 0, 0, 1, 1, 1, 0]
        pd.DataFrame({"timestamps": idx7, "open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0, "volume": vol}).to_parquet(d / "raw" / "A.BK.parquet")
        (fc / "2026-07-01" / "A.BK_meta.json").write_text(json.dumps({"lookback_end": str(idx7[7])}))
        got = input_window_stub_share(fc, d / "raw", ["A.BK"], WINDOW_START, idx7[-1], lookback=5)
        assert got == {"windows": 1, "mean_stub_rows_per_window": 2.0, "share_windows_ge_4_stub_rows": 0.0, "max_stub_rows": 2}, got
    print("selftest passed (live value, benchmark cost, price-only eligibility, stub dates, decision rules, guard, rank IC, stub-window count, fill factors, apply dates)")


def synthetic_run() -> None:
    with tempfile.TemporaryDirectory() as d:
        eq, dates = make_synthetic(Path(d), signal=0.0)
        res = run_review(Path(d), eq, [], "twelve-month", dates[-1].date())
        assert res["process_log"]["trading_days_in_window"] > 100
        print_report(res, "twelve-month (SYNTHETIC DATA)", dates[-1].date())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--review", choices=list(REVIEW_DATES))
    ap.add_argument("--as-of", default=str(date.today()))
    ap.add_argument("--root", default="data")
    ap.add_argument("--fill-factors", help="ticket-19 factor file; used only if it says apply_total_return_fix")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.synthetic:
        return synthetic_run()
    as_of = date.fromisoformat(a.as_of)
    guard(a.review, as_of)
    root = Path(a.root)
    if (root / "MANIFEST.sha256").exists():  # a frozen snapshot from snapshot_live_data.py
        from snapshot_live_data import verify
        bad = verify(root)
        if bad:
            raise SystemExit(f"snapshot {root} fails its hash check ({len(bad)} files), first: {bad[:3]}")
        print(f"data: snapshot {root.resolve()} (hash check OK)")
    else:
        print(f"data: {root.resolve()} (NOT a frozen snapshot; ticket 11 addendum asks for one)")
    factors = None
    if a.fill_factors:
        ff = json.loads(Path(a.fill_factors).read_text())
        if ff["snapshot"] != root.name:
            raise SystemExit(f"fill factors are for snapshot {ff['snapshot']}, not {root.name}; rerun the ticket-19 audit")
        if ff["apply_total_return_fix"]:
            factors = {int(k): v for k, v in ff["F_by_row"].items()}
        print(f"ticket-19 audit: apply_total_return_fix={ff['apply_total_return_fix']}")
    else:
        print("WARNING: no --fill-factors; ticket 11 addendum B asks for the ticket-19 audit on this snapshot first")
    res = run_review(root, FROZEN_THAI_EQUITY, FROZEN_DR, a.review, as_of, fill_factors=factors)
    print_report(res, a.review, as_of)


if __name__ == "__main__":
    main()
