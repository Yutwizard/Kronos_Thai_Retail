"""Trade ticket generator — reads forecast cache, applies 3-filter rule, produces trade tickets."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from kth.data.universe import UNIVERSE, FRICTION, get_ticker_class, get_display_name, get_sector

CACHE_SLUG = "NeoQuasar_Kronos-small"
CACHE_DIR = Path("data/forecast_cache") / CACHE_SLUG
POSITIONS_DIR = Path("data/positions")
MAX_POSITIONS = 5
MAX_SECTOR_POSITIONS = 2
THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
BACKTEST_METRICS = {
    "thai_equity": {"sharpe": 1.40, "cagr": 0.3144, "max_dd": -0.1797},
}


def _safe_ticker(ticker: str) -> str:
    return ticker.replace("^", "_").replace("=", "_")


def load_forecasts(report_date: str = None) -> list[dict]:
    """Load today's forecast cache for all Thai equity tickers."""
    if report_date is None:
        report_date = str(date.today())
    day_dir = CACHE_DIR / report_date
    if not day_dir.exists():
        return []

    rows = []
    for ticker in THAI_TICKERS:
        parquet = day_dir / f"{_safe_ticker(ticker)}.parquet"
        if not parquet.exists():
            continue
        try:
            fc = pd.read_parquet(parquet)
            from kth.data.loader import load_cached
            price_data = load_cached(ticker)
            current_close = float(price_data["close"].iloc[-1])

            p50 = float(fc["p50"].iloc[-1])
            p5 = float(fc["p5"].iloc[-1])
            p95 = float(fc["p95"].iloc[-1])
            mean_close = float(fc["mean"].iloc[-1]) if "mean" in fc.columns else p50

            exp_ret = (p50 - current_close) / current_close
            band_width = (p95 - p5) / current_close

            cls = get_ticker_class(ticker)
            fric = FRICTION.get(cls, {"commission_oneway": 0.002, "slippage_oneway": 0.001})
            friction_rt = fric["commission_oneway"] * 2 + fric["slippage_oneway"] * 2

            conf = "green" if band_width <= 0.10 else ("yellow" if band_width <= 0.30 else "red")
            direction = "up" if exp_ret > 0 else "down"
            net_ret = exp_ret - friction_rt
            rank_score = exp_ret / max(band_width, 0.001)

            rows.append({
                "ticker": ticker,
                "name": get_display_name(ticker),
                "class": cls,
                "close": round(current_close, 2),
                "p50_close": round(p50, 2),
                "p5_close": round(p5, 2),
                "p95_close": round(p95, 2),
                "mean_close": round(mean_close, 2),
                "exp_ret": round(exp_ret, 4),
                "band_width": round(band_width, 4),
                "confidence": conf,
                "direction": direction,
                "friction_rt": round(friction_rt, 4),
                "net_ret": round(net_ret, 4),
                "rank_score": round(rank_score, 4),
                "market_sharpe": BACKTEST_METRICS.get(cls, {}).get("sharpe"),
            })
        except Exception as e:
            logging.warning(f"Trade gen: skipping {ticker}: {e}")
            continue

    rows.sort(key=lambda x: x["rank_score"], reverse=True)
    return rows


def _next_business_day(d: date) -> date:
    d = d + timedelta(days=1)
    while d.weekday() >= 5:  # skip Saturday=5, Sunday=6
        d = d + timedelta(days=1)
    return d


def _one_way_friction(ticker: str) -> float:
    """One-way friction rate for a ticker (commission + slippage) from the FRICTION dict."""
    cls = get_ticker_class(ticker)
    fric = FRICTION.get(cls, {"commission_oneway": 0.002, "slippage_oneway": 0.001})
    return fric["commission_oneway"] + fric["slippage_oneway"]


def generate_trade_ticket(report_date: str = None, positions: dict = None) -> dict:
    """Generate today's trade ticket: exits, reduces, buys, cash flow."""
    forecasts = load_forecasts(report_date)
    if not forecasts:
        return {"error": "No forecasts available", "exits": [], "reduces": [], "buys": []}

    from kth.trading.portfolio import get_positions, compute_metrics, INITIAL_CAPITAL
    metrics = compute_metrics("paper")
    alloc_band = metrics["allocation_band"]
    alloc_pct = metrics["allocation_pct"]
    frozen = metrics.get("frozen", False)

    if positions is None:
        pos_data = get_positions("paper")
        held_tickers = {p["ticker"]: p for p in pos_data["positions"]}
    else:
        held_tickers = positions

    capital = pos_data.get("total_value", INITIAL_CAPITAL) if positions is None else INITIAL_CAPITAL
    deployable = capital * alloc_pct

    market_state = metrics.get("market_state", "Normal")
    if market_state == "Turmoil" or frozen or alloc_band == "EXIT":
        return {
            "exits": [],
            "reduces": [],
            "buys": [],
            "cash_flow": {"gross_proceeds": 0, "friction": 0, "net_proceeds": 0},
            "banner": "STAY CASH" if market_state == "Turmoil" else
                      "STOP-LOSS TRIGGERED" if frozen else
                      "EXIT band — no positions allowed",
            "market_state": market_state,
            "frozen": frozen,
        }

    exits = []
    reduces = []
    for f in forecasts:
        ticker = f["ticker"]
        if ticker not in held_tickers:
            continue
        if f["direction"] == "down" and f["confidence"] == "green":
            exits.append({
                "ticker": ticker,
                "shares": held_tickers[ticker]["shares"],
                "order_type": "market",
                "limit_price": None,
                "last_close": f["close"],
                "estimated_thb": round(held_tickers[ticker]["shares"] * f["close"]),
                "rationale": f"🟢↓ bearish net_ret={f['net_ret']:+.2%}",
            })
        elif f["confidence"] == "yellow":
            reduce_shares = held_tickers[ticker]["shares"] // 2
            if reduce_shares < 100:
                continue
            limit = round(f["close"] * (1 + f["exp_ret"] / 2), 2)
            reduces.append({
                "ticker": ticker,
                "shares": reduce_shares,
                "order_type": "limit",
                "limit_price": limit,
                "estimated_thb": round(reduce_shares * f["close"]),
                "rationale": f"🟡 moderate conviction, half-size",
            })

    buys = []
    remaining_cap = deployable
    exited = {e["ticker"] for e in exits}
    existing_count = len(held_tickers) - len(exited)
    slots = max(0, MAX_POSITIONS - existing_count)

    # Seed sector counts from positions being kept (not exited)
    sector_counts: dict[str, int] = {}
    for ticker in held_tickers:
        if ticker not in exited:
            sec = get_sector(ticker)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

    for rank_idx, f in enumerate(forecasts, 1):
        if len(buys) >= slots:
            break
        if f["ticker"] in held_tickers:
            continue
        if f["net_ret"] <= f["friction_rt"]:
            continue
        if f["confidence"] == "red":
            continue
        if sector_counts.get(get_sector(f["ticker"]), 0) >= MAX_SECTOR_POSITIONS:
            continue

        per_slot = remaining_cap / max(slots - len(buys), 1)
        lots = int(per_slot / f["close"] / 100) * 100
        if lots < 100:
            continue

        limit = round(f["close"] * (1 + f["exp_ret"] / 2), 2)
        sec = get_sector(f["ticker"])
        buys.append({
            "ticker": f["ticker"],
            "name": f["name"],
            "shares": lots,
            "order_type": "limit",
            "limit_price": limit,
            "last_close": f["close"],
            "estimated_thb": round(lots * f["close"]),
            "rationale": f"🟢↑ rank#{rank_idx} net_ret={f['net_ret']:+.2%}",
        })
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        remaining_cap -= lots * f["close"]

    gross_sells = sum(e["estimated_thb"] for e in exits) + sum(r["estimated_thb"] for r in reduces)
    gross_buys = sum(b["estimated_thb"] for b in buys)
    friction_sells = sum(e["estimated_thb"] * _one_way_friction(e["ticker"]) for e in exits) + \
                     sum(r["estimated_thb"] * _one_way_friction(r["ticker"]) for r in reduces)
    friction_buys = sum(b["estimated_thb"] * _one_way_friction(b["ticker"]) for b in buys)
    total_friction = round(friction_sells + friction_buys, 2)
    net_cash = gross_sells - gross_buys - total_friction

    t2_warning = None
    if (exits or reduces) and buys:
        settle = _next_business_day(_next_business_day(date.today()))
        t2_warning = (
            f"Exit/reduce proceeds settle {settle} (T+2). "
            f"Today's buys draw from existing cash only — not from today's exit proceeds."
        )

    ticket = {
        "date": report_date or str(date.today()),
        "exits": exits,
        "reduces": reduces,
        "buys": buys,
        "t2_warning": t2_warning,
        "cash_flow": {
            "gross_proceeds": round(gross_sells, 2),
            "friction": total_friction,
            "net_proceeds": round(net_cash, 2),
            "buy_cost": round(gross_buys, 2),
        },
        "market_state": market_state,
        "frozen": frozen,
        "allocation_band": alloc_band,
        "allocation_pct": alloc_pct,
    }

    POSITIONS_DIR.mkdir(parents=True, exist_ok=True)
    ticket_path = POSITIONS_DIR / f"trade_ticket_{ticket['date']}.json"
    with open(ticket_path, "w") as f:
        json.dump(ticket, f, indent=2, default=str)

    return ticket


def load_trade_ticket(report_date: str = None) -> dict:
    """Load persisted trade ticket for a date."""
    if report_date is None:
        report_date = str(date.today())
    path = POSITIONS_DIR / f"trade_ticket_{report_date}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"error": "No trade ticket for today", "exits": [], "reduces": [], "buys": []}


def get_top_ranked(n: int = 10) -> list[dict]:
    """Get top N tickers by rank score for morning brief."""
    forecasts = load_forecasts()
    return forecasts[:n]


def get_all_ranked() -> list[dict]:
    """Get all 49 tickers sorted by rank score."""
    return load_forecasts()
