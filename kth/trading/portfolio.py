"""Paper/live portfolio engine — position tracking, P&L, equity curve, trade log."""
from __future__ import annotations

import json
import csv
import os
from pathlib import Path
from datetime import date, datetime

import numpy as np
import pandas as pd

POSITIONS_DIR = Path("data/positions")
INITIAL_CAPITAL = 500_000.0
STOP_LOSS = -0.10
MODEL_VERSION = "Kronos-small-zero-shot"


def _portfolio_path(mode: str) -> Path:
    return POSITIONS_DIR / f"{mode}_portfolio.json"


def _trade_log_path() -> Path:
    return POSITIONS_DIR / "trade_log.csv"


def _ensure_dirs():
    POSITIONS_DIR.mkdir(parents=True, exist_ok=True)


def init_portfolio(mode: str = "paper") -> dict:
    """Load or create a portfolio. Returns dict with cash, positions, equity_curve."""
    _ensure_dirs()
    path = _portfolio_path(mode)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    pf = {
        "mode": mode,
        "initial_capital": INITIAL_CAPITAL,
        "cash": INITIAL_CAPITAL,
        "positions": {},
        "equity_curve": [{"date": str(date.today()), "value": INITIAL_CAPITAL}],
        "frozen": False,
        "frozen_at": None,
    }
    _save_portfolio(mode, pf)
    return pf


def _save_portfolio(mode: str, pf: dict):
    _ensure_dirs()
    path = _portfolio_path(mode)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(pf, f, indent=2, default=str)
    os.replace(tmp, path)


def get_positions(mode: str = "paper") -> dict:
    """Return current positions with mark-to-market enrichment."""
    pf = init_portfolio(mode)
    positions = pf.get("positions", {})
    if not positions:
        return {"positions": [], "total_value": pf["cash"], "cash": pf["cash"],
                "frozen": pf.get("frozen", False), "equity": pf["equity_curve"][-1]["value"] if pf["equity_curve"] else pf["cash"]}

    from kth.data.universe import get_ticker_class
    try:
        from kth_dr.universe_dr import get_dr_info_for_display
        from kth_dr.loader_dr import compute_dr_premium_pct
    except ImportError:
        get_dr_info_for_display = lambda t: None
        compute_dr_premium_pct = None

    enriched = []
    for ticker, pos in positions.items():
        mark = _get_current_price(ticker)
        if mark is None or mark == 0:
            mark = 0.0  # fallback
        pnl = (mark - pos["avg_cost"]) / pos["avg_cost"] if pos["avg_cost"] > 0 else 0
        val = pos["shares"] * mark

        underlying_ticker = None
        premium_pct = None
        dr_info = get_dr_info_for_display(ticker)
        if dr_info:
            underlying_ticker = dr_info["underlying_ticker"]
            u_close = _get_current_price(dr_info["underlying_ticker"])
            fx_close = _get_current_price(dr_info["fx_ticker"])
            try:
                premium_pct = compute_dr_premium_pct(mark, u_close, fx_close, dr_info["ratio"])
            except ValueError:
                premium_pct = None

        enriched.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "avg_cost": pos["avg_cost"],
            "mark": mark,
            "pnl_pct": round(pnl, 4),
            "value": round(val, 2),
            "class": get_ticker_class(ticker),
            "underlying_ticker": underlying_ticker,
            "premium_pct": premium_pct,
        })

    # Sort by value desc
    enriched.sort(key=lambda x: x["value"], reverse=True)
    total_pos_value = sum(p["value"] for p in enriched)
    total_value = pf["cash"] + total_pos_value

    # Add weight to each position
    for p in enriched:
        p["weight"] = round(p["value"] / total_value, 4) if total_value > 0 else 0

    return {
        "positions": enriched,
        "total_value": round(total_value, 2),
        "cash": round(pf["cash"], 2),
        "frozen": pf.get("frozen", False),
        "equity": round(total_value, 2),
    }


def _get_current_price(ticker: str) -> float | None:
    """Get latest close price from cached data. Logs errors instead of swallowing."""
    import logging
    try:
        from kth.data.loader import load_cached
        df = load_cached(ticker)
        return float(df["close"].iloc[-1])
    except FileNotFoundError:
        logging.warning(f"_get_current_price: no cache for {ticker}")
        return None
    except Exception as e:
        logging.error(f"_get_current_price: corrupt cache for {ticker}: {e}")
        return None


def execute_trade(ticker: str, action: str, shares: int, fill_price: float,
                  mode: str = "paper", order_type: str = "market",
                  rationale: str = "") -> dict:
    """Execute a trade: update portfolio, log trade, recompute equity."""
    pf = init_portfolio(mode)

    if pf.get("frozen", False):
        return {"error": "Portfolio frozen — stop-loss triggered", "recorded": 0}

    if action == "buy":
        cost = shares * fill_price
        friction_cost = cost * _one_way_friction_rate(ticker)
        total_cost = cost + friction_cost
        if total_cost > pf["cash"]:
            return {"error": f"Insufficient cash: need {total_cost:.0f}, have {pf['cash']:.0f}",
                    "recorded": 0}
        pf["cash"] -= total_cost
        existing = pf["positions"].get(ticker, {"shares": 0, "avg_cost": 0})
        new_shares = existing["shares"] + shares
        new_cost = ((existing["shares"] * existing["avg_cost"]) + cost) / new_shares
        pf["positions"][ticker] = {"shares": new_shares, "avg_cost": round(new_cost, 4)}

    elif action in ("exit", "sell"):
        pos = pf["positions"].get(ticker)
        if not pos or pos["shares"] < shares:
            return {"error": f"Cannot exit {shares} shares of {ticker}: only {pos['shares'] if pos else 0} held",
                    "recorded": 0}
        proceeds = shares * fill_price
        friction_cost = proceeds * _one_way_friction_rate(ticker)
        pf["cash"] += proceeds - friction_cost
        remaining = pos["shares"] - shares
        if remaining <= 0:
            del pf["positions"][ticker]
        else:
            pf["positions"][ticker]["shares"] = remaining

    elif action == "reduce":
        pos = pf["positions"].get(ticker)
        if not pos:
            return {"error": f"No position in {ticker}", "recorded": 0}
        actual = min(shares, pos["shares"])
        return execute_trade(ticker, "exit", actual, fill_price, mode, order_type, rationale)

    else:
        return {"error": f"Unknown action: {action}", "recorded": 0}

    # Recompute equity
    total_pos_value = sum(
        pos["shares"] * (_get_current_price(t) or pos["avg_cost"])
        for t, pos in pf["positions"].items()
    )
    total_value = pf["cash"] + total_pos_value
    pf["equity_curve"].append({"date": str(date.today()), "value": round(total_value, 2)})

    # Check stop-loss
    peak = max(e["value"] for e in pf["equity_curve"])
    dd = total_value / peak - 1
    if dd <= STOP_LOSS:
        pf["frozen"] = True
        pf["frozen_at"] = str(date.today())

    _save_portfolio(mode, pf)

    # Log trade
    _log_trade(ticker, action, shares, fill_price, order_type, mode, rationale, friction_cost)

    return {
        "recorded": 1,
        "portfolio_value": round(total_value, 2),
        "cash": round(pf["cash"], 2),
        "new_positions": [
            {"ticker": t, "shares": p["shares"], "weight": round(p["shares"] * (_get_current_price(t) or p["avg_cost"]) / total_value, 4)}
            for t, p in pf["positions"].items()
        ],
        "frozen": pf["frozen"],
        "drawdown": round(dd, 4),
    }


def _log_trade(ticker: str, action: str, shares: int, price: float,
               order_type: str, mode: str, rationale: str, friction: float):
    path = _trade_log_path()
    file_exists = path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["date", "ticker", "action", "shares", "price", "order_type",
                        "mode", "rationale", "friction_cost", "model_version", "forecast_date"])
        w.writerow([str(date.today()), ticker, action, shares, price, order_type,
                    mode, rationale, round(friction, 2), MODEL_VERSION, str(date.today())])


def get_trade_log(mode: str = None) -> list[dict]:
    """Read trade log, optionally filtered by mode."""
    path = _trade_log_path()
    if not path.exists():
        return []
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if mode:
        rows = [r for r in rows if r.get("mode") == mode]
    return rows


def compute_metrics(mode: str = "paper") -> dict:
    """Compute Sharpe, drawdown, P&L, win rate, exposure."""
    pf = init_portfolio(mode)
    curve = pf.get("equity_curve", [])
    if len(curve) < 2:
        return {"sharpe": 0, "drawdown": 0, "pnl_mtd": 0, "pnl_mtd_pct": 0,
                "win_rate": 0, "exposure": 0, "allocation_band": "NEUTRAL",
                "allocation_pct": 0.10, "market_state": "Normal", "closed_trades": 0}

    values = [e["value"] for e in curve]
    peak = max(values)
    dd = values[-1] / peak - 1 if peak > 0 else 0

    # 12-week trailing Sharpe (approx 60 trading days)
    if len(values) >= 22:
        daily = pd.Series(values).pct_change().dropna().tail(60)
        if len(daily) >= 20 and daily.std() > 0:
            sharpe = float(daily.mean() / daily.std() * np.sqrt(252))
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # P&L MTD
    today = date.today()
    month_start = today.replace(day=1)
    mtd_curve = [e for e in curve if e["date"] >= str(month_start)]
    month_start_value = mtd_curve[0]["value"] if mtd_curve else pf["initial_capital"]
    pnl_mtd = values[-1] - month_start_value
    pnl_mtd_pct = pnl_mtd / month_start_value if month_start_value > 0 else 0

    # Win rate (closed round-trips via FIFO)
    trades = get_trade_log(mode)
    closed_count, wins = _compute_fifo_wins(trades)
    win_rate = wins / closed_count if closed_count > 0 else 0

    # Exposure
    pos_info = get_positions(mode)
    total_value = pos_info["total_value"]
    total_pos_value = sum(p["value"] for p in pos_info["positions"])
    exposure = total_pos_value / total_value if total_value > 0 else 0

    # Allocation band from trailing Sharpe. Bootstrap: NEUTRAL until 20+ trades.
    if closed_count < 20:
        band = "NEUTRAL"
        alloc_pct = 0.10
    elif sharpe > 1.0:
        band = "BULL"
        alloc_pct = 0.15
    elif sharpe > 0.5:
        band = "NEUTRAL"
        alloc_pct = 0.10
    elif sharpe > 0:
        band = "BEAR"
        alloc_pct = 0.05
    else:
        band = "EXIT"
        alloc_pct = 0.0

    # Market state
    market_state = _compute_market_state()

    from kth.backtest.metrics import compute_drawdown_velocity, compute_bootstrap_pvalue
    equity_series = pd.Series(values)
    dd_velocity = compute_drawdown_velocity(equity_series)

    daily_returns = pd.Series(values).pct_change().dropna()
    bootstrap_pvalue = compute_bootstrap_pvalue(daily_returns)

    return {
        "sharpe": round(sharpe, 2),
        "drawdown": round(dd, 4),
        "pnl_mtd": round(pnl_mtd, 2),
        "pnl_mtd_pct": round(pnl_mtd_pct, 4),
        "win_rate": round(win_rate, 4),
        "exposure": round(exposure, 4),
        "allocation_band": band,
        "allocation_pct": round(alloc_pct, 2),
        "closed_trades": closed_count,
        "market_state": market_state,
        "drawdown_velocity": dd_velocity,
        "bootstrap_pvalue": {k: bool(v) if isinstance(v, (np.bool_, bool)) else float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else v
                             for k, v in bootstrap_pvalue.items()},
    }


def get_equity_performance(mode: str = "paper") -> dict:
    """Equity curve + summary stats for the Performance dashboard tab.

    Returns the full equity_curve as plottable points plus inception-to-date
    stats (total return, max drawdown over the whole curve, peak equity) and
    re-uses compute_metrics() for Sharpe / win rate / closed trades.
    """
    pf = init_portfolio(mode)
    curve = pf.get("equity_curve", [])
    initial = float(pf.get("initial_capital", INITIAL_CAPITAL))

    points = [{"date": e["date"], "value": round(float(e["value"]), 2)} for e in curve]
    values = [p["value"] for p in points]
    current = values[-1] if values else initial
    peak = max(values) if values else initial

    # Max drawdown over the entire curve (not just current vs peak).
    max_dd = 0.0
    running_peak = float("-inf")
    for v in values:
        running_peak = max(running_peak, v)
        if running_peak > 0:
            max_dd = min(max_dd, v / running_peak - 1)

    # Inception = first activity across trade log + equity curve (authoritative
    # start of paper trading). days_tracked = calendar days since then, inclusive —
    # NOT distinct equity-curve dates (those only exist on trade/rebuild days).
    trade_dates = [t["date"] for t in get_trade_log(mode) if t.get("date")]
    all_dates = trade_dates + [p["date"] for p in points]
    inception = min(all_dates) if all_dates else str(date.today())
    try:
        incep_d = datetime.strptime(inception, "%Y-%m-%d").date()
        days_tracked = (date.today() - incep_d).days + 1
    except ValueError:
        days_tracked = len({p["date"] for p in points})

    m = compute_metrics(mode)
    trades = get_trade_log(mode)

    # --- Realized P&L stats (FIFO, net of friction) ---
    realized = _compute_fifo_pnl(trades)
    wins = [r for r in realized if r > 0]
    losses = [r for r in realized if r < 0]
    realized_pnl = sum(realized)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None  # None = no losses yet (∞)
    avg_win = round(gross_profit / len(wins), 2) if wins else 0.0
    avg_loss = round(gross_loss / len(losses), 2) if losses else 0.0
    payoff_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else None
    total_friction = round(sum(float(t.get("friction_cost", 0) or 0) for t in trades), 2)

    # --- Unrealized P&L + concentration (from open positions) ---
    pos_info = get_positions(mode)
    open_positions = pos_info.get("positions", [])
    unrealized_pnl = round(sum((p["mark"] - p["avg_cost"]) * p["shares"] for p in open_positions), 2)
    largest_weight = round(max((p["weight"] for p in open_positions), default=0.0), 4)
    from kth.data.universe import get_sector
    sector_weights: dict = {}
    for p in open_positions:
        sec = get_sector(p["ticker"]) or "Other"
        sector_weights[sec] = sector_weights.get(sec, 0.0) + p["weight"]
    top_sector, top_sector_weight = (max(sector_weights.items(), key=lambda kv: kv[1])
                                     if sector_weights else ("—", 0.0))

    # --- Drawdown shape over the curve ---
    from kth.backtest.metrics import compute_drawdown_metrics
    dd_metrics = compute_drawdown_metrics(pd.Series(values)) if len(values) >= 2 else {
        "avg_drawdown": 0.0, "ulcer_index": 0.0, "max_drawdown_duration": 0}

    return {
        "initial_capital": round(initial, 2),
        "current_equity": round(current, 2),
        "total_pnl": round(current - initial, 2),
        "total_return_pct": round(current / initial - 1, 4) if initial > 0 else 0,
        "peak_equity": round(peak, 2),
        "max_drawdown": round(max_dd, 4),
        "current_drawdown": m["drawdown"],
        "avg_drawdown": round(dd_metrics["avg_drawdown"], 4),
        "ulcer_index": round(dd_metrics["ulcer_index"], 4),
        "max_drawdown_duration": dd_metrics["max_drawdown_duration"],
        "inception_date": inception,
        "days_tracked": days_tracked,
        "num_points": len(points),
        "sharpe": m["sharpe"],
        "win_rate": m["win_rate"],
        "closed_trades": m["closed_trades"],
        "bootstrap_pvalue": m.get("bootstrap_pvalue"),
        # realized / friction
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": unrealized_pnl,
        "profit_factor": profit_factor,
        "payoff_ratio": payoff_ratio,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "total_friction": total_friction,
        # concentration
        "open_positions": len(open_positions),
        "largest_weight": largest_weight,
        "top_sector": top_sector,
        "top_sector_weight": round(top_sector_weight, 4),
        "points": points,
    }


def _compute_fifo_pnl(trades: list[dict]) -> list[float]:
    """FIFO matching → net realized P&L (THB) per matched buy↔sell chunk.

    Matching is PER TICKER (a sell of ticker X matches X's own oldest buys).
    Net = (sell_price − buy_price) × shares, minus the friction attributable to
    both the buy lot (pro-rated per share) and the sell (pro-rated per share).
    """
    from collections import deque, defaultdict
    buys: dict = defaultdict(deque)  # ticker -> deque of {shares, price, fps}
    realized: list[float] = []
    for t in trades:
        ticker = t["ticker"]
        shares = int(t["shares"])
        price = float(t["price"])
        fric = float(t.get("friction_cost", 0) or 0)
        if shares <= 0:
            continue
        if t["action"] == "buy":
            buys[ticker].append({"shares": shares, "price": price, "fps": fric / shares})
        elif t["action"] in ("exit", "sell", "reduce"):
            remaining = shares
            sell_fps = fric / shares
            q = buys[ticker]
            while remaining > 0 and q:
                lot = q.popleft()
                matched = min(remaining, lot["shares"])
                gross = (price - lot["price"]) * matched
                net = gross - matched * lot["fps"] - matched * sell_fps
                realized.append(net)
                remaining -= matched
                if lot["shares"] > matched:
                    q.appendleft({"shares": lot["shares"] - matched,
                                  "price": lot["price"], "fps": lot["fps"]})
    return realized


def _compute_fifo_wins(trades: list[dict]) -> tuple[int, int]:
    """FIFO matching (PER TICKER): first-bought shares are first-sold.

    Returns (closed_round_trips, wins) where a round-trip = one sell event and a
    win = a sell event whose aggregate realized gross P&L (across the buy lots it
    consumes) is positive.
    """
    from collections import deque, defaultdict
    buys: dict = defaultdict(deque)  # ticker -> deque of {shares, price}
    wins = 0
    closed_round_trips = 0
    for t in trades:
        ticker = t["ticker"]
        if t["action"] == "buy":
            buys[ticker].append({"shares": int(t["shares"]), "price": float(t["price"])})
        elif t["action"] in ("exit", "sell", "reduce"):
            remaining = int(t["shares"])
            sale_price = float(t["price"])
            closed_round_trips += 1
            event_pnl = 0.0
            q = buys[ticker]
            while remaining > 0 and q:
                lot = q.popleft()
                matched = min(remaining, lot["shares"])
                event_pnl += (sale_price - lot["price"]) * matched
                remaining -= matched
                if lot["shares"] > matched:
                    q.appendleft({"shares": lot["shares"] - matched, "price": lot["price"]})
            if event_pnl > 0:
                wins += 1
    return closed_round_trips, wins


def _compute_market_state() -> str:
    """Determine market state from today's forecast data.
    Returns 'Normal' | 'Elevated' | 'Turmoil' | 'Unknown' (no data)."""
    try:
        from kth.trading.trade_gen import load_forecasts
        forecasts = load_forecasts()
        if not forecasts:
            return "Unknown"
        bands = [f["band_width"] for f in forecasts if f.get("band_width")]
        red_count = sum(1 for f in forecasts if f.get("confidence") == "red")
        if not bands:
            return "Unknown"
        median_band = float(pd.Series(bands).median())
        if median_band > 0.30 or red_count > 30:
            return "Turmoil"
        if median_band > 0.20 or red_count > 15:
            return "Elevated"
        return "Normal"
    except Exception as e:
        import logging
        logging.warning(f"_compute_market_state failed: {e}")
        return "Unknown"


def reset_portfolio(mode: str = "paper", initial_capital: float = None) -> dict:
    """Create or reset portfolio with specified initial capital. Clears all positions and equity curve."""
    if initial_capital is None:
        initial_capital = INITIAL_CAPITAL
    pf = {
        "mode": mode,
        "initial_capital": float(initial_capital),
        "cash": float(initial_capital),
        "positions": {},
        "equity_curve": [{"date": str(date.today()), "value": float(initial_capital)}],
        "frozen": False,
        "frozen_at": None,
    }
    _ensure_dirs()
    _save_portfolio(mode, pf)
    return pf


def _one_way_friction_rate(ticker: str) -> float:
    from kth.data.universe import get_one_way_friction_rate
    return get_one_way_friction_rate(ticker)


def rebuild_from_trades(mode: str = "paper") -> dict:
    """
    Rebuild portfolio cash + positions by replaying trade_log.csv.
    Appends one new equity_curve point with the recalculated total value.
    The historical equity curve is preserved (approximation after edits).
    """
    pf = init_portfolio(mode)
    trades = [t for t in get_trade_log() if t.get("mode") == mode]

    cash = float(pf.get("initial_capital", INITIAL_CAPITAL))
    positions: dict = {}

    for t in trades:
        ticker, shares, price, action = t["ticker"], int(t["shares"]), float(t["price"]), t["action"]
        if action == "buy":
            cost = shares * price
            friction = cost * _one_way_friction_rate(ticker)
            cash -= cost + friction
            existing = positions.get(ticker, {"shares": 0, "avg_cost": 0})
            new_shares = existing["shares"] + shares
            new_avg = ((existing["shares"] * existing["avg_cost"]) + cost) / new_shares if new_shares > 0 else price
            positions[ticker] = {"shares": new_shares, "avg_cost": round(new_avg, 4)}
        elif action in ("exit", "sell", "reduce"):
            proceeds = shares * price
            friction = proceeds * _one_way_friction_rate(ticker)
            cash += proceeds - friction
            pos = positions.get(ticker, {"shares": 0, "avg_cost": 0})
            remaining = pos["shares"] - shares
            if remaining <= 0:
                positions.pop(ticker, None)
            else:
                positions[ticker] = {"shares": remaining, "avg_cost": pos["avg_cost"]}

    pf["cash"] = round(cash, 2)
    pf["positions"] = positions
    total_pos = sum(
        pos["shares"] * (_get_current_price(t) or pos["avg_cost"])
        for t, pos in positions.items()
    )
    total_value = round(cash + total_pos, 2)
    pf["equity_curve"].append({"date": str(date.today()), "value": total_value})
    _save_portfolio(mode, pf)
    return pf


def delete_trade(index: int, mode: str = "paper") -> dict:
    """Delete trade at CSV row index (0-based) and rebuild portfolio from remaining trades."""
    path = _trade_log_path()
    if not path.exists():
        return {"error": "No trade log found"}
    with open(path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if index < 0 or index >= len(rows):
        return {"error": f"Invalid index {index} — log has {len(rows)} trades"}
    deleted = rows.pop(index)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    rebuild_from_trades(mode)
    return {"deleted": deleted, "remaining_trades": len(rows)}


def edit_trade(index: int, new_price: float | None = None,
               new_shares: int | None = None, mode: str = "paper",
               new_date: str | None = None) -> dict:
    """Edit fill price, shares, and/or trade date of a trade at CSV row index, then rebuild portfolio."""
    path = _trade_log_path()
    if not path.exists():
        return {"error": "No trade log found"}
    with open(path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if index < 0 or index >= len(rows):
        return {"error": f"Invalid index {index}"}

    old_price = float(rows[index]["price"])
    old_shares = int(rows[index]["shares"])
    old_date = rows[index]["date"]

    if new_price is not None:
        rows[index]["price"] = str(round(new_price, 4))
    if new_shares is not None:
        if new_shares <= 0 or new_shares % 100 != 0:
            return {"error": f"Shares must be a positive multiple of 100, got {new_shares}"}
        rows[index]["shares"] = str(new_shares)
    if new_date is not None:
        try:
            datetime.strptime(new_date, "%Y-%m-%d")
        except (TypeError, ValueError):
            return {"error": f"Date must be YYYY-MM-DD, got {new_date!r}"}
        if new_date > str(date.today()):
            return {"error": f"Date {new_date} is in the future"}
        rows[index]["date"] = new_date

    price = float(rows[index]["price"])
    shares = int(rows[index]["shares"])
    rows[index]["friction_cost"] = str(round(shares * price * _one_way_friction_rate(rows[index]["ticker"]), 2))

    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    rebuild_from_trades(mode)
    return {
        "updated": True,
        "old_price": old_price, "new_price": price,
        "old_shares": old_shares, "new_shares": shares,
        "old_date": old_date, "new_date": rows[index]["date"],
    }


def export_broker_csv(mode: str = "paper", output_path: str = None) -> str:
    """Export trade log as broker-ready CSV."""
    trades = get_trade_log(mode)
    if not trades:
        return ""
    if output_path is None:
        output_path = str(POSITIONS_DIR / f"broker_export_{date.today()}.csv")
    with open(output_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "action", "ticker", "shares", "order_type", "limit_price", "estimated_thb", "rationale"])
        for t in trades:
            r = t.get("rationale", "")
            est = int(t["shares"]) * float(t["price"])
            w.writerow([t["date"], t["action"], t["ticker"], t["shares"],
                       t.get("order_type", "market"), t.get("limit_price", ""),
                       f"~{est:.0f}", r])
    return output_path


def check_phase2_gate() -> dict:
    """Check if Phase 2 transition gate conditions are met."""
    trades = get_trade_log("paper")
    if len(trades) < 2:
        return {"ready": False, "reason": "Need at least 2 paper trades" if len(trades) < 2 else "Not ready"}

    unique_dates = sorted(set(t["date"] for t in trades))
    distinct_trade_dates = len(unique_dates)
    round_trips = sum(1 for t in trades if t["action"] in ("exit", "sell"))

    metrics = compute_metrics("paper")
    win_rate_ok = metrics["win_rate"] >= 0.50
    sharpe_ok = metrics["sharpe"] >= 0.90
    dd_ok = metrics["drawdown"] > -0.10

    # Count monthly rebalances (proxy: trades on last-Friday-like dates)
    rebalance_count = _count_rebalances(trades)

    all_ok = (distinct_trade_dates >= 20 and round_trips >= 10 and win_rate_ok
              and sharpe_ok and dd_ok and rebalance_count >= 3)

    return {
        "ready": all_ok,
        "distinct_trade_dates": distinct_trade_dates,
        "round_trips": round_trips,
        "win_rate": round(metrics["win_rate"], 2),
        "sharpe": metrics["sharpe"],
        "drawdown": round(metrics["drawdown"], 4),
        "rebalances": rebalance_count,
        "checks": {
            "20_distinct_dates": distinct_trade_dates >= 20,
            "10_trades": round_trips >= 10,
            "win_rate_50": win_rate_ok,
            "sharpe_90": sharpe_ok,
            "no_stop_loss": dd_ok,
            "3_rebalances": rebalance_count >= 3,
        }
    }


def _count_rebalances(trades: list[dict]) -> int:
    """Count distinct dates with >=2 trade events (proxy for rebalance days).
    A single tax-loss harvest on one date does not count."""
    from collections import Counter
    date_counts = Counter(
        t["date"] for t in trades
        if t["action"] in ("exit", "sell", "reduce", "buy")
    )
    return sum(1 for c in date_counts.values() if c >= 2)
