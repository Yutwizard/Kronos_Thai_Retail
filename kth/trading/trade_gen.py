"""Trade ticket generator — reads forecast cache, applies 3-filter rule, produces trade tickets."""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from kth.data.universe import UNIVERSE, FRICTION, get_ticker_class, get_display_name, get_sector, get_currency_group, get_friction, get_one_way_friction_rate
from kth.data.loader import sanitize_ticker
from kth.data.pricestore import PriceStore
from kth.trading.execution import ExecutionResolver

from kth.utils.model_slug import model_slug as _model_slug
CACHE_SLUG = _model_slug("NeoQuasar/Kronos-small")
CACHE_DIR = Path("data/forecast_cache") / CACHE_SLUG
POSITIONS_DIR = Path("data/positions")
MAX_POSITIONS = 5
MAX_SECTOR_POSITIONS = 2
MAX_CURRENCY_POSITIONS = 2
TOP_N = 10
THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
try:
    from kth_dr.universe_dr import get_dr_underlying_tickers
    DR_UNDERLYING_TICKERS = get_dr_underlying_tickers()
except ImportError:
    DR_UNDERLYING_TICKERS = []
except Exception as e:
    # kth_dr present but unusable (e.g. hand-edited mapping.json with a bad
    # schema) — degrade to thai-only rather than killing the module import.
    logging.warning(f"kth_dr present but unusable ({e}) — continuing without DR tickers")
    DR_UNDERLYING_TICKERS = []
TRADABLE_TICKERS = THAI_TICKERS + DR_UNDERLYING_TICKERS
BACKTEST_METRICS = {
    "thai_equity": {"sharpe": 1.40, "cagr": 0.3144, "max_dd": -0.1797},
}


def _execution_forecast_price(
    underlying_close: float, forecast_price: float, execution_close: float
) -> Optional[float]:
    """Convert an underlying forecast to the execution ticker's price scale."""
    try:
        valid_scale = (
            math.isfinite(underlying_close)
            and underlying_close > 0
            and math.isfinite(execution_close)
            and execution_close > 0
        )
    except (TypeError, ValueError):
        valid_scale = False
    if not valid_scale:
        return None
    return forecast_price * execution_close / underlying_close


def _tag_tiers(rows: list[dict], n: int = TOP_N) -> list[dict]:
    """Tag each row (already sorted desc by rank_score) with tier "bull"/"bear"/"".

    Display-only classification for the dashboard's top/bottom-N views — does
    not feed trade selection. if/elif keeps top-n and bottom-n windows
    mutually exclusive even when they'd overlap (total < 2*n); if total <= n
    every row falls in the "bull" branch. Doesn't occur in practice (~87
    tradable tickers).
    """
    total = len(rows)
    for i, r in enumerate(rows):
        if i < n:
            r["tier"] = "bull"
        elif i >= total - n:
            r["tier"] = "bear"
        else:
            r["tier"] = ""
    return rows


def latest_forecast_date(on_or_before: str | None = None) -> str | None:
    """Newest forecast folder (with at least one parquet) dated on or before `on_or_before` (default today).
    The pipeline runs in the evening, so in the morning the forecasts to trade from are dated the day before."""
    limit = on_or_before or str(date.today())
    if not CACHE_DIR.exists():
        return None
    days = sorted(d.name for d in CACHE_DIR.iterdir()
                  if d.is_dir() and d.name <= limit and any(d.glob("*.parquet")))
    return days[-1] if days else None


def latest_ticket_date(on_or_before: str | None = None) -> str | None:
    """Newest saved trade ticket dated on or before `on_or_before` (default today)."""
    limit = on_or_before or str(date.today())
    days = sorted(p.stem.replace("trade_ticket_", "") for p in POSITIONS_DIR.glob("trade_ticket_*.json"))
    days = [d for d in days if d <= limit]
    return days[-1] if days else None


def load_forecasts(report_date: str = None, prices: PriceStore | None = None,
                    resolver: ExecutionResolver | None = None) -> list[dict]:
    """Load today's forecast cache for every tradable ticker (thai_equity +
    underlyings with a verified DR). For a DR-mapped underlying, the row also
    carries execution_ticker/exec_close so trade-gen prices the trade in THB
    against the DR's own SET close, never the underlying's raw close.

    prices/resolver: per-run seams (the test surface — inject fakes, no disk)."""
    if report_date is None:  # latest forecasts on or before today (evening runs are dated the day before)
        report_date = latest_forecast_date()
        if report_date is None:
            return []
    day_dir = CACHE_DIR / report_date
    if not day_dir.exists():
        return []

    prices = prices or PriceStore()
    resolver = resolver or ExecutionResolver(prices)
    rows = []
    for ticker in TRADABLE_TICKERS:
        parquet = day_dir / f"{sanitize_ticker(ticker)}.parquet"
        if not parquet.exists():
            continue
        try:
            fc = pd.read_parquet(parquet)
            current_close = prices.get_close(ticker)
            if current_close is None:
                continue

            p50 = float(fc["p50"].iloc[-1])
            p5 = float(fc["p5"].iloc[-1])
            p95 = float(fc["p95"].iloc[-1])
            mean_close = float(fc["mean"].iloc[-1]) if "mean" in fc.columns else p50

            # exp_ret/band_width are ratios — currency-agnostic, safe to compute
            # off the underlying's own close.
            exp_ret = (p50 - current_close) / current_close
            band_width = (p95 - p5) / current_close

            exec_ticker = resolver.execution_ticker(ticker)
            exec_close = resolver.execution_price(ticker, exec_ticker, current_close)
            target_price = _execution_forecast_price(current_close, p50, exec_close)
            p95_price = _execution_forecast_price(current_close, p95, exec_close)

            # Friction/class must be resolved off the EXECUTION ticker — a DR
            # position pays "dr" friction (thai_equity rate), not the
            # underlying's own asset-class friction (e.g. us_equity's higher rate).
            cls = get_ticker_class(exec_ticker)
            fric = get_friction(exec_ticker)
            friction_rt = fric["commission_oneway"] * 2 + fric["slippage_oneway"] * 2

            conf = "green" if band_width <= 0.10 else ("yellow" if band_width <= 0.30 else "red")
            direction = "up" if exp_ret > 0 else "down"
            net_ret = exp_ret - friction_rt
            rank_score = exp_ret / max(band_width, 0.001)

            # Display-only, mirrors get_positions()'s premium enrichment — never
            # feeds rank_score or the buy filter, so a failure here must not
            # drop the candidate from the ranking.
            _, premium_pct = resolver.premium(exec_ticker, exec_close)

            rows.append({
                "ticker": ticker,
                "execution_ticker": exec_ticker,
                "exec_close": round(exec_close, 2),
                "target_price": round(target_price, 2) if target_price is not None else None,
                "p95_price": round(p95_price, 2) if p95_price is not None else None,
                "name": resolver.display_name(ticker, get_display_name(ticker)),
                "class": cls,
                "sector": get_sector(exec_ticker),
                "currency_group": get_currency_group(exec_ticker),
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
                "premium_pct": premium_pct,
            })
        except Exception as e:
            logging.warning(f"Trade gen: skipping {ticker}: {e}")
            continue

    rows.sort(key=lambda x: x["rank_score"], reverse=True)
    return _tag_tiers(rows)


def _next_business_day(d: date) -> date:
    d = d + timedelta(days=1)
    while d.weekday() >= 5:  # skip Saturday=5, Sunday=6
        d = d + timedelta(days=1)
    return d


def _one_way_friction(ticker: str) -> float:
    """One-way friction rate for a ticker (commission + slippage)."""
    return get_one_way_friction_rate(ticker)


def generate_trade_ticket(report_date: str = None, positions: dict = None,
                          prices: PriceStore | None = None,
                          resolver: ExecutionResolver | None = None) -> dict:
    """Generate today's trade ticket: exits, reduces, buys, cash flow.

    Every ticket item's "ticker" field is the EXECUTION ticker (what you'd
    actually place an order for) — the DR ticker for a DR-backed trade, the
    ticker itself otherwise. "underlying" carries the signal-source ticker
    for display/rationale only. This keeps friction/sector lookups correct
    for free, since get_friction()/get_sector() key off the execution ticker.
    """
    prices = prices or PriceStore()
    resolver = resolver or ExecutionResolver(prices)
    if report_date is None:  # date the ticket by the forecasts it uses, not by the clock (a run can cross midnight)
        report_date = latest_forecast_date()
    forecasts = load_forecasts(report_date, prices=prices, resolver=resolver) if report_date else []
    if not forecasts:
        return {"error": "No forecasts available", "exits": [], "reduces": [], "buys": []}

    from kth.trading.portfolio import get_positions, compute_metrics, INITIAL_CAPITAL
    metrics = compute_metrics("paper")
    alloc_band = metrics["allocation_band"]
    alloc_pct = metrics["allocation_pct"]
    frozen = metrics.get("frozen", False)

    if positions is None:
        pos_data = get_positions("paper")
        held_tickers = {p["ticker"]: p for p in pos_data["positions"]}  # keyed by execution ticker
        available_cash = pos_data.get("cash", INITIAL_CAPITAL)
    else:
        held_tickers = positions
        available_cash = INITIAL_CAPITAL

    capital = pos_data.get("total_value", INITIAL_CAPITAL) if positions is None else INITIAL_CAPITAL
    deployable = min(capital * alloc_pct, available_cash)

    market_state = metrics.get("market_state", "Normal")
    if market_state == "Turmoil" or frozen or alloc_band == "EXIT":
        return {
            "exits": [], "reduces": [], "buys": [],
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
        exec_ticker = f.get("execution_ticker", f["ticker"])
        if exec_ticker not in held_tickers:
            continue
        exec_close = f.get("exec_close", f["close"])
        held = held_tickers[exec_ticker]
        if f["direction"] == "down" and f["confidence"] == "green":
            exits.append({
                "ticker": exec_ticker,
                "underlying": f["ticker"],
                "shares": held["shares"],
                "order_type": "market",
                "limit_price": None,
                "last_close": exec_close,
                "estimated_thb": round(held["shares"] * exec_close),
                "rationale": f"🟢↓ bearish net_ret={f['net_ret']:+.2%}",
            })
        elif f["confidence"] == "yellow" and f["direction"] == "down":
            reduce_shares = held["shares"] // 2
            if reduce_shares < 100:
                continue
            limit = round(exec_close * (1 + f["exp_ret"] / 2), 2)
            reduces.append({
                "ticker": exec_ticker,
                "underlying": f["ticker"],
                "shares": reduce_shares,
                "order_type": "limit",
                "limit_price": limit,
                "estimated_thb": round(reduce_shares * exec_close),
                "rationale": f"🟡 moderate conviction, half-size",
            })

    buys = []
    remaining_cap = deployable
    exited = {e["ticker"] for e in exits}
    existing_count = len(held_tickers) - len(exited)
    slots = max(0, MAX_POSITIONS - existing_count)

    # Sector and currency-group counts are independent concentration pools —
    # see docs/adr/0004-separate-dr-sector-and-currency-group.md. Both are
    # seeded from held tickers, which are already execution tickers.
    # get_currency_group() returns None for thai_equity, so those tickers
    # never populate currency_counts.
    sector_counts: dict[str, int] = {}
    currency_counts: dict[str, int] = {}
    for ticker in held_tickers:
        if ticker not in exited:
            sec = get_sector(ticker)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            cur = get_currency_group(ticker)
            if cur is not None:
                currency_counts[cur] = currency_counts.get(cur, 0) + 1

    for rank_idx, f in enumerate(forecasts, 1):
        if len(buys) >= slots:
            break
        exec_ticker = f.get("execution_ticker", f["ticker"])
        if exec_ticker in held_tickers:
            continue
        if resolver.is_held_underlying(list(held_tickers.keys()), f["ticker"]):
            continue  # same underlying already held directly or via a different DR
        if f["net_ret"] <= f["friction_rt"]:
            continue
        if f["confidence"] == "red":
            continue
        if sector_counts.get(get_sector(exec_ticker), 0) >= MAX_SECTOR_POSITIONS:
            continue
        exec_currency = get_currency_group(exec_ticker)
        if exec_currency is not None and currency_counts.get(exec_currency, 0) >= MAX_CURRENCY_POSITIONS:
            continue

        exec_close = f.get("exec_close", f["close"])
        per_slot = remaining_cap / max(slots - len(buys), 1)
        lots = int(per_slot / exec_close / 100) * 100
        if lots < 100:
            continue

        limit = round(exec_close * (1 + f["exp_ret"] / 2), 2)
        sec = get_sector(exec_ticker)
        is_dr = exec_ticker != f["ticker"]
        rationale = (
            f"🟢↑ DR proxy for {f['ticker']}, rank#{rank_idx} net_ret={f['net_ret']:+.2%}"
            if is_dr else
            f"🟢↑ rank#{rank_idx} net_ret={f['net_ret']:+.2%}"
        )
        buys.append({
            "ticker": exec_ticker,
            "underlying": f["ticker"],
            "name": f["name"],
            "shares": lots,
            "order_type": "limit",
            "limit_price": limit,
            "last_close": exec_close,
            "estimated_thb": round(lots * exec_close),
            "rationale": rationale,
        })
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        if exec_currency is not None:
            currency_counts[exec_currency] = currency_counts.get(exec_currency, 0) + 1
        remaining_cap -= lots * exec_close

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
    """Load the persisted trade ticket for a date; default = the latest ticket on or before today (the evening
    run's ticket is dated the day before the morning session it is traded in)."""
    if report_date is None:
        report_date = latest_ticket_date() or str(date.today())
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
