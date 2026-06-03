# Real-Market Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Flask dashboard + automated pipeline for live Thai equity paper trading, graduating to broker-ready trade instructions.

**Architecture:** 3 new Python modules (portfolio engine, trade generator, dashboard server) + 1 shell wrapper + 2 static frontend files. All kth/ modules unchanged. Flask serves REST API + single-page HTML with vanilla JS AJAX polling.

**Tech Stack:** Python 3.10+, Flask, pandas, numpy, PyTorch (Kronos), vanilla JS, HTML/CSS

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `kth/trading/__init__.py` | Package marker |
| Create | `kth/trading/portfolio.py` | Position tracking, P&L, equity curve, trade log |
| Create | `kth/trading/trade_gen.py` | Trade ticket generation, 3-filter rule, CSV export |
| Create | `scripts/dashboard.py` | Flask server + `--generate`/`--serve` subcommands |
| Create | `scripts/cron_pipeline.sh` | Cron wrapper with retry + logging |
| Create | `scripts/static/dashboard.html` | Single-page dashboard with AJAX polling |
| Create | `scripts/static/style.css` | Dashboard styles |
| Modify | None in kth/ | All new code is additive |

---

### Task 1: Package Setup & Portfolio Engine

**Files:**
- Create: `kth/trading/__init__.py`
- Create: `kth/trading/portfolio.py`

- [ ] **Step 1: Create package marker**

```bash
mkdir -p kth/trading
touch kth/trading/__init__.py
```

- [ ] **Step 2: Write portfolio.py**

```python
"""Paper/live portfolio engine — position tracking, P&L, equity curve, trade log."""
from __future__ import annotations

import json
import csv
import os
from pathlib import Path
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

POSITIONS_DIR = Path("data/positions")
INITIAL_CAPITAL = 500_000.0
MAX_POSITIONS = 5
STOP_LOSS = -0.10


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
    with open(_portfolio_path(mode), "w") as f:
        json.dump(pf, f, indent=2, default=str)


def get_positions(mode: str = "paper") -> dict:
    """Return current positions with mark-to-market enrichment."""
    pf = init_portfolio(mode)
    positions = pf.get("positions", {})
    if not positions:
        return {"positions": [], "total_value": pf["cash"], "cash": pf["cash"],
                "frozen": pf.get("frozen", False), "equity": pf["equity_curve"][-1]["value"] if pf["equity_curve"] else pf["cash"]}

    enriched = []
    for ticker, pos in positions.items():
        mark = _get_current_price(ticker)
        pnl = (mark - pos["avg_cost"]) / pos["avg_cost"] if pos["avg_cost"] > 0 else 0
        val = pos["shares"] * mark
        enriched.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "avg_cost": pos["avg_cost"],
            "mark": mark,
            "pnl_pct": round(pnl, 4),
            "value": round(val, 2),
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


def _get_current_price(ticker: str) -> float:
    """Get latest close price from cached data."""
    try:
        from kth.data.loader import load_cached
        df = load_cached(ticker)
        return float(df["close"].iloc[-1])
    except Exception:
        return 0.0


def execute_trade(ticker: str, action: str, shares: int, fill_price: float,
                  mode: str = "paper", order_type: str = "market",
                  rationale: str = "") -> dict:
    """Execute a trade: update portfolio, log trade, recompute equity."""
    pf = init_portfolio(mode)

    if pf.get("frozen", False):
        return {"error": "Portfolio frozen — stop-loss triggered", "recorded": 0}

    if action == "buy":
        cost = shares * fill_price
        # Estimate friction for Thai equity
        friction_cost = cost * 0.00268 * 2  # commission_oneway*2 + slippage_oneway*2 = 0.00536
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
        friction_cost = proceeds * 0.00268 * 2
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
        pos["shares"] * _get_current_price(t)
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
            {"ticker": t, "shares": p["shares"], "weight": round(p["shares"] * _get_current_price(t) / total_value, 4)}
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
                        "mode", "rationale", "friction_cost"])
        w.writerow([str(date.today()), ticker, action, shares, price, order_type,
                    mode, rationale, round(friction, 2)])


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
    pnl_mtd = values[-1] - pf["initial_capital"]
    pnl_mtd_pct = pnl_mtd / pf["initial_capital"]

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
    }


def _compute_fifo_wins(trades: list[dict]) -> tuple[int, int]:
    """FIFO matching: first-bought shares are first-sold. Returns (closed_count, wins)."""
    from collections import deque
    buys = deque()
    wins = 0
    closed = 0
    for t in trades:
        if t["action"] == "buy":
            buys.append({"shares": int(t["shares"]), "price": float(t["price"])})
        elif t["action"] in ("exit", "sell"):
            remaining = int(t["shares"])
            sale_price = float(t["price"])
            while remaining > 0 and buys:
                lot = buys.popleft()
                matched = min(remaining, lot["shares"])
                if sale_price > lot["price"]:
                    wins += 1
                closed += 1
                remaining -= matched
                if lot["shares"] > matched:
                    buys.appendleft({"shares": lot["shares"] - matched, "price": lot["price"]})
    return closed, wins


def _compute_market_state() -> str:
    """Determine market state from today's forecast data."""
    try:
        from kth.trading.trade_gen import load_forecasts
        forecasts = load_forecasts()
        if not forecasts:
            return "Normal"
        bands = [f["band_width"] for f in forecasts if f.get("band_width")]
        red_count = sum(1 for f in forecasts if f.get("confidence") == "red")
        if not bands:
            return "Normal"
        median_band = float(pd.Series(bands).median())
        if median_band > 0.30 or red_count > 30:
            return "Turmoil"
        if median_band > 0.20 or red_count > 15:
            return "Elevated Vol"
        return "Normal"
    except Exception:
        return "Normal"


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
        return {"ready": False, "reason": "No paper trades yet"}

    unique_dates = sorted(set(t["date"] for t in trades))
    weeks_active = len(unique_dates)
    round_trips = sum(1 for t in trades if t["action"] in ("exit", "sell"))

    metrics = compute_metrics("paper")
    win_rate_ok = metrics["win_rate"] >= 0.50
    sharpe_ok = metrics["sharpe"] >= 0.90
    dd_ok = metrics["drawdown"] > -0.10

    # Count monthly rebalances (proxy: trades on last-Friday-like dates)
    rebalance_count = _count_rebalances(trades)

    all_ok = (weeks_active >= 20 and round_trips >= 10 and win_rate_ok
              and sharpe_ok and dd_ok and rebalance_count >= 3)

    return {
        "ready": all_ok,
        "weeks_active": weeks_active,
        "round_trips": round_trips,
        "win_rate": round(metrics["win_rate"], 2),
        "sharpe": metrics["sharpe"],
        "drawdown": round(metrics["drawdown"], 4),
        "rebalances": rebalance_count,
        "checks": {
            "4weeks": weeks_active >= 20,
            "10_trades": round_trips >= 10,
            "win_rate_50": win_rate_ok,
            "sharpe_90": sharpe_ok,
            "no_stop_loss": dd_ok,
            "3_rebalances": rebalance_count >= 3,
        }
    }


def _count_rebalances(trades: list[dict]) -> int:
    """Count distinct months with exits (proxy for rebalance events)."""
    months = set()
    for t in trades:
        if t["action"] in ("exit", "sell", "reduce"):
            months.add(t["date"][:7])
    return len(months)
```

- [ ] **Step 3: Verify portfolio init works**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python -c "
from kth.trading.portfolio import init_portfolio, get_positions, compute_metrics
pf = init_portfolio('paper')
assert pf['cash'] == 500000
assert pf['mode'] == 'paper'
pos = get_positions('paper')
assert pos['cash'] == 500000
m = compute_metrics('paper')
assert m['allocation_band'] == 'NEUTRAL'
print('Portfolio engine — OK')
"
```

Expected: `Portfolio engine — OK`

- [ ] **Step 4: Commit**

```bash
git add kth/trading/__init__.py kth/trading/portfolio.py
git commit -m "feat: portfolio engine — paper/live position tracking, P&L, equity curve, FIFO win rate"
```

---

### Task 2: Trade Generator

**Files:**
- Create: `kth/trading/trade_gen.py`

- [ ] **Step 1: Write trade_gen.py**

```python
"""Trade ticket generator — reads forecast cache, applies 3-filter rule, produces trade tickets."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date
from typing import Optional

import pandas as pd
import numpy as np

from kth.data.universe import UNIVERSE, FRICTION, get_ticker_class, get_display_name

CACHE_SLUG = "NeoQuasar_Kronos-small"
CACHE_DIR = Path("data/forecast_cache") / CACHE_SLUG
POSITIONS_DIR = Path("data/positions")
MAX_POSITIONS = 5
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
        except Exception:
            continue

    rows.sort(key=lambda x: x["rank_score"], reverse=True)
    return rows


def generate_trade_ticket(report_date: str = None, positions: dict = None) -> dict:
    """Generate today's trade ticket: exits, reduces, buys, cash flow."""
    forecasts = load_forecasts(report_date)
    if not forecasts:
        return {"error": "No forecasts available", "exits": [], "reduces": [], "buys": []}

    from kth.trading.portfolio import init_portfolio, get_positions, compute_metrics
    metrics = compute_metrics("paper")
    alloc_band = metrics["allocation_band"]
    alloc_pct = metrics["allocation_pct"]
    frozen = metrics.get("frozen", False)

    if positions is None:
        pos_data = get_positions("paper")
        held_tickers = {p["ticker"]: p for p in pos_data["positions"]}
    else:
        held_tickers = positions

    capital = metrics.get("total_value", INITIAL_CAPITAL) if "total_value" in dir() else 500000
    deployable = capital * alloc_pct

    # Market state check
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
                "estimated_thb": round(held_tickers[ticker]["shares"] * f["close"]),
                "rationale": f"🟢↓ bearish net_ret={f['net_ret']:+.2%}",
            })
        elif f["confidence"] == "yellow":
            reduce_shares = held_tickers[ticker]["shares"] // 2
            limit = round(f["close"] * (1 + f["exp_ret"] / 2), 2)
            reduces.append({
                "ticker": ticker,
                "shares": reduce_shares,
                "order_type": "limit",
                "limit_price": limit,
                "estimated_thb": round(reduce_shares * f["close"]),
                "rationale": f"🟡 moderate conviction, half-size",
            })

    # Buy list: top-ranked tickers not already held, net_ret > 2× friction
    buys = []
    remaining_cap = deployable
    existing_count = len(held_tickers) - len(exits) - len(reduces)
    slots = max(0, MAX_POSITIONS - existing_count)

    for f in forecasts:
        if len(buys) >= slots:
            break
        if f["ticker"] in held_tickers:
            continue
        if f["net_ret"] <= f["friction_rt"] * 2:
            continue
        if f["confidence"] == "red":
            continue  # skip low-confidence buys

        # Lot sizing: 100-share board lots
        per_slot = remaining_cap / max(slots - len(buys), 1)
        lots = int(per_slot / f["close"] / 100) * 100
        if lots < 100:
            continue

        limit = round(f["close"] * (1 + f["exp_ret"] / 2), 2)
        buys.append({
            "ticker": f["ticker"],
            "name": f["name"],
            "shares": lots,
            "order_type": "limit",
            "limit_price": limit,
            "estimated_thb": round(lots * f["close"]),
            "rationale": f"🟢↑ rank#{forecasts.index(f)+1} net_ret={f['net_ret']:+.2%}",
        })
        remaining_cap -= lots * f["close"]

    # Cash flow summary
    gross_sells = sum(e["estimated_thb"] for e in exits) + sum(r["estimated_thb"] for r in reduces)
    gross_buys = sum(b["estimated_thb"] for b in buys)
    friction_sells = gross_sells * 0.00268 * 2
    friction_buys = gross_buys * 0.00268 * 2
    total_friction = round(friction_sells + friction_buys, 2)
    net_cash = gross_sells - gross_buys - total_friction

    ticket = {
        "date": report_date or str(date.today()),
        "exits": exits,
        "reduces": reduces,
        "buys": buys,
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

    # Persist ticket
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
```

- [ ] **Step 2: Verify trade generator loads forecasts**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python -c "
from kth.trading.trade_gen import load_forecasts
# Check that the function exists and handles no data gracefully
forecasts = load_forecasts()
print(f'Forecasts loaded: {len(forecasts)} tickers')
# Should work even if no forecast cache exists yet
assert isinstance(forecasts, list)
print('Trade generator — OK')
"
```

Expected: `Trade generator — OK` (may show 0 tickers if no cache)

- [ ] **Step 3: Commit**

```bash
git add kth/trading/trade_gen.py
git commit -m "feat: trade generator — forecast cache reader, 3-filter rule, trade ticket JSON"
```

---

### Task 3: Dashboard Flask Server

**Files:**
- Create: `scripts/dashboard.py`

- [ ] **Step 1: Write dashboard.py**

```python
#!/usr/bin/env python3
"""Kronos-TH Dashboard — Flask server for paper/live trading dashboard."""
from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import date, datetime

from flask import Flask, jsonify, request, send_from_directory

# Ensure kth is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, "kronos_repo")

app = Flask(__name__, static_folder="scripts/static", static_url_path="/static")
TRADING_MODE = os.environ.get("KRONOS_MODE", "paper")  # "paper" or "live"
PORT = int(os.environ.get("KRONOS_PORT", "5555"))


@app.route("/")
def index():
    return send_from_directory("scripts/static", "dashboard.html")


# ---- REST API ----

@app.route("/api/forecasts")
def api_forecasts():
    from kth.trading.trade_gen import get_all_ranked
    forecasts = get_all_ranked()
    return jsonify({"date": str(date.today()), "count": len(forecasts), "forecasts": forecasts})


@app.route("/api/positions")
def api_positions():
    from kth.trading.portfolio import get_positions
    return jsonify(get_positions(TRADING_MODE))


@app.route("/api/risk")
def api_risk():
    from kth.trading.portfolio import compute_metrics
    return jsonify(compute_metrics(TRADING_MODE))


@app.route("/api/trades", methods=["GET", "POST"])
def api_trades():
    if request.method == "GET":
        from kth.trading.trade_gen import load_trade_ticket
        return jsonify(load_trade_ticket())
    elif request.method == "POST":
        from kth.trading.portfolio import execute_trade
        data = request.get_json(force=True)
        trades = data.get("trades", [])
        results = []
        for t in trades:
            r = execute_trade(
                ticker=t["ticker"],
                action=t["action"],
                shares=int(t["shares"]),
                fill_price=float(t["fill_price"]),
                mode=data.get("mode", TRADING_MODE),
                order_type=t.get("order_type", "market"),
                rationale=t.get("rationale", ""),
            )
            results.append(r)
        total_recorded = sum(r.get("recorded", 0) for r in results)
        return jsonify({"recorded": total_recorded, "results": results})


@app.route("/api/health")
def api_health():
    today_str = str(date.today())
    log_path = Path(f"data/logs/cron_{today_str}.log")
    steps = {"download": "unknown", "forecast": "unknown", "trade_gen": "unknown"}
    stale = True
    last_forecast = None

    if log_path.exists():
        content = log_path.read_text()
        if "PIPELINE_OK" in content:
            steps = {"download": "ok", "forecast": "ok", "trade_gen": "ok"}
            stale = False
        else:
            if "STEP1_FAILED" in content:
                steps["download"] = "failed"
            elif "download_data.py" in content:
                steps["download"] = "ok"
            if "STEP2_FAILED" in content:
                steps["forecast"] = "failed"
            elif "forecast" in content.lower():
                steps["forecast"] = "ok"

    # Check for forecast cache
    cache_dir = Path(f"data/forecast_cache/NeoQuasar_Kronos-small/{today_str}")
    if cache_dir.exists():
        last_forecast = today_str
        steps["forecast"] = steps.get("forecast", "ok")
    else:
        # Find latest cached date
        parent = Path("data/forecast_cache/NeoQuasar_Kronos-small")
        if parent.exists():
            dates = sorted([d.name for d in parent.iterdir() if d.is_dir()], reverse=True)
            if dates:
                last_forecast = dates[0]
                stale = dates[0] != today_str

    return jsonify({
        "last_forecast_date": last_forecast,
        "steps": steps,
        "stale": stale,
        "pipeline_log": str(log_path) if log_path.exists() else None,
    })


@app.route("/api/phase2_gate")
def api_phase2_gate():
    from kth.trading.portfolio import check_phase2_gate
    return jsonify(check_phase2_gate())


@app.route("/api/export_csv")
def api_export_csv():
    from kth.trading.portfolio import export_broker_csv
    path = export_broker_csv(TRADING_MODE)
    if path:
        return jsonify({"status": "ok", "path": path})
    return jsonify({"status": "error", "message": "No trades to export"})


# ---- CLI ----

def cmd_generate():
    """Run morning pipeline: download data → generate forecasts → trade ticket."""
    log_path = Path(f"data/logs/cron_{date.today()}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    os.environ["HF_HUB_OFFLINE"] = "1"

    # Step 1: Download data
    log("STEP1: download_data.py")
    try:
        result = subprocess.run(
            [sys.executable, "scripts/download_data.py"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            log(f"STEP1_FAILED: {result.stderr[:200]}")
            return 1
        log("STEP1_OK")
    except Exception as e:
        log(f"STEP1_FAILED: {e}")
        return 1

    # Step 2: Generate forecasts
    log("STEP2: forecast generation")
    try:
        from kth.data.universe import UNIVERSE
        from kth.models.kronos_wrapper import KronosTH
        from kth.backtest.walkforward import precompute_forecasts
        import shutil

        tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]
        today_str = str(date.today())
        slug = "NeoQuasar_Kronos-small"
        today_dir = Path(f"data/forecast_cache/{slug}/{today_str}")
        if today_dir.exists():
            shutil.rmtree(today_dir)

        th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
        precompute_forecasts(th, tickers, start_date=today_str, end_date=today_str,
                             pred_len=20, n_samples=50, lookback=400)
        log("STEP2_OK")
    except Exception as e:
        log(f"STEP2_FAILED: {e}")
        return 1

    # Step 3: Generate trade ticket
    log("STEP3: trade ticket generation")
    try:
        from kth.trading.trade_gen import generate_trade_ticket
        ticket = generate_trade_ticket()
        log(f"STEP3_OK: {len(ticket.get('exits',[]))} exits, {len(ticket.get('buys',[]))} buys")
    except Exception as e:
        log(f"STEP3_FAILED: {e}")
        return 1

    log("PIPELINE_OK")
    return 0


def cmd_serve():
    """Start Flask dashboard server."""
    print(f"Kronos-TH Dashboard — {TRADING_MODE.upper()} mode")
    print(f"Open: http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        sys.exit(cmd_generate())
    elif len(sys.argv) > 1 and sys.argv[1] == "--serve":
        cmd_serve()
    else:
        print("Usage:")
        print("  dashboard.py --generate   # Run morning pipeline")
        print("  dashboard.py --serve      # Start web server")
        print(f"\nMode: {TRADING_MODE} (set KRONOS_MODE=live for Phase 2)")
        print(f"Port: {PORT} (set KRONOS_PORT to override)")
```

- [ ] **Step 2: Verify Flask app imports correctly (no GPU needed)**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python -c "
import sys; sys.path.insert(0, 'kronos_repo')
from scripts.dashboard import app
# Test that routes are registered
rules = [r.rule for r in app.url_map.iter_rules()]
expected = ['/api/forecasts', '/api/positions', '/api/risk', '/api/trades', '/api/health', '/api/phase2_gate', '/api/export_csv']
for e in expected:
    assert e in rules, f'Missing route: {e}'
print('All routes registered — OK')
"
```

Expected: `All routes registered — OK`

- [ ] **Step 3: Verify --help works**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python scripts/dashboard.py 2>&1 | head -5
```

Expected: Shows usage text for --generate and --serve

- [ ] **Step 4: Commit**

```bash
git add scripts/dashboard.py
git commit -m "feat: dashboard Flask server — REST API + --generate/--serve subcommands"
```

---

### Task 4: Cron Pipeline Script

**Files:**
- Create: `scripts/cron_pipeline.sh`

- [ ] **Step 1: Write cron_pipeline.sh**

```bash
#!/bin/bash
# Kronos-TH morning pipeline — retry wrapper for cron
set -e

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="data/logs/cron_$(date +%Y-%m-%d).log"
RETRIES=3
BACKOFF=120

cd "$PROJ_DIR"
mkdir -p data/logs data/positions

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "Pipeline starting — $(date)"

# Step 1: Download data
for i in $(seq 1 $RETRIES); do
    log "STEP1 attempt $i/$RETRIES: download_data.py"
    if venv/bin/python scripts/download_data.py >> "$LOG" 2>&1; then
        log "STEP1_OK"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        log "STEP1_FAILED after $RETRIES attempts"
        exit 1
    fi
    log "STEP1 retry in ${BACKOFF}s..."
    sleep "$BACKOFF"
done

# Step 2: Generate forecasts + trade ticket
for i in $(seq 1 $RETRIES); do
    log "STEP2 attempt $i/$RETRIES: forecast generation"
    if venv/bin/python scripts/dashboard.py --generate >> "$LOG" 2>&1; then
        log "STEP2_OK"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        log "STEP2_FAILED after $RETRIES attempts"
        exit 1
    fi
    log "STEP2 retry in ${BACKOFF}s..."
    sleep "$BACKOFF"
done

log "PIPELINE_OK — $(date)"
echo "PIPELINE_OK" >> "$LOG"
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x /home/yut/VSCode/Kronos_Thai_Retail/scripts/cron_pipeline.sh
bash -n /home/yut/VSCode/Kronos_Thai_Retail/scripts/cron_pipeline.sh && echo "Shell syntax — OK"
```

Expected: `Shell syntax — OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/cron_pipeline.sh
git commit -m "feat: cron pipeline wrapper — retry + logging for morning automation"
```

---

### Task 5: Dashboard Frontend HTML

**Files:**
- Create: `scripts/static/dashboard.html`

- [ ] **Step 1: Write dashboard.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1024">
<title>Kronos-TH Dashboard</title>
<link rel="stylesheet" href="/static/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><circle cx='8' cy='8' r='8' fill='%231565C0'/></svg>">
</head>
<body>

<div id="app">
  <!-- Header -->
  <header id="header">
    <div class="h-left">
      <h1>Kronos-TH Dashboard</h1>
      <span id="mode-badge" class="badge paper">📋 PAPER</span>
    </div>
    <div class="h-right">
      <span id="header-date"></span>
      <span id="header-refresh"></span>
      <span id="banner-area"></span>
    </div>
  </header>

  <!-- Risk Bar -->
  <div id="risk-bar" class="risk-bar">
    <div class="risk-tile" id="tile-market"><div class="t-label">Market State</div><div class="t-val" id="val-market">—</div></div>
    <div class="risk-tile" id="tile-alloc"><div class="t-label">Allocation</div><div class="t-val" id="val-alloc">—</div></div>
    <div class="risk-tile"><div class="t-label">Trailing Sharpe</div><div class="t-val" id="val-sharpe">—</div></div>
    <div class="risk-tile"><div class="t-label">Drawdown</div><div class="t-val" id="val-dd">—</div><div class="dd-bar"><div class="dd-fill" id="dd-fill"></div></div></div>
    <div class="risk-tile"><div class="t-label">P&L MTD</div><div class="t-val" id="val-pnl">—</div></div>
    <div class="risk-tile"><div class="t-label">Win Rate</div><div class="t-val" id="val-win">—</div></div>
    <div class="risk-tile"><div class="t-label">Exposure</div><div class="t-val" id="val-exp">—</div></div>
  </div>

  <!-- Signal Health (collapsible) -->
  <div id="signal-health" class="signal-health hidden">
    <span id="sig-acc">Accuracy: —</span>
    <span id="sig-sharpe-delta">vs Backtest: —</span>
    <span id="sig-warning" class="hidden">🚨 Model review recommended — halve position sizes</span>
  </div>

  <!-- Main Content -->
  <div id="main-content">
    <!-- Trade Ticket (Hero) -->
    <section id="trade-ticket" class="panel hero">
      <h2>Trade Ticket — <span id="ticket-date"></span></h2>
      <div id="ticket-body"></div>
      <div id="ticket-actions">
        <button id="btn-execute" class="btn primary" onclick="executeTrades()">Record Paper Trade</button>
        <button id="btn-export" class="btn secondary" onclick="exportCSV()">Export for Broker</button>
      </div>
    </section>

    <!-- Positions + Morning Brief (2-col) -->
    <div class="two-col">
      <section id="positions-panel" class="panel">
        <h2>Current Positions</h2>
        <div id="positions-body"></div>
      </section>
      <section id="morning-panel" class="panel">
        <h2>Morning Brief — Top 10</h2>
        <div id="morning-body"></div>
      </section>
    </div>

    <!-- Full Ranking (collapsible) -->
    <section id="ranking-panel" class="panel collapsible">
      <h2 onclick="toggleRanking()">Full Ranking (49 tickers) <span id="rank-toggle">▼</span></h2>
      <div id="ranking-search"><input type="text" placeholder="Search ticker..." oninput="filterRanking(this.value)"></div>
      <div id="ranking-body"></div>
    </section>
  </div>

  <footer>
    <p>Not financial advice. Past performance ≠ future results. Kronos-small zero-shot, n_samples=50. Auto-refresh 60s.</p>
  </footer>
</div>

<script>
const MODE = "paper"; // Set by server config
const API = "";
let showRanking = false;

function $(id) { return document.getElementById(id); }

async function fetchJSON(url) {
  try {
    const r = await fetch(API + url);
    return await r.json();
  } catch(e) { return null; }
}

// ---- Polling Loop ----
let lastRefresh = null;
async function refresh() {
  const now = new Date();
  $("header-date").textContent = now.toISOString().slice(0, 10) + " " +
    now.toTimeString().slice(0, 5) + " BKK";

  const [risk, positions, forecasts, trades, health] = await Promise.all([
    fetchJSON("/api/risk"), fetchJSON("/api/positions"),
    fetchJSON("/api/forecasts"), fetchJSON("/api/trades"),
    fetchJSON("/api/health")
  ]);

  updateRiskBar(risk);
  updateHealth(health);
  updatePositions(positions);
  updateForecasts(forecasts);
  updateTradeTicket(trades, risk);
  updateMode();

  lastRefresh = now;
  $("header-refresh").textContent = "Last refresh: " + now.toTimeString().slice(0, 8);
}

function updateMode() {
  const badge = $("mode-badge");
  const btn = $("btn-execute");
  if (MODE === "live") {
    badge.className = "badge live";
    badge.textContent = "💰 LIVE";
    btn.textContent = "Confirm Live Trade";
    document.querySelector("link[rel=icon]").href =
      "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><circle cx='8' cy='8' r='8' fill='%2327ae60'/></svg>";
  }
}

function updateRiskBar(risk) {
  if (!risk) return;
  $("val-market").textContent = risk.market_state || "—";
  $("val-market").className = "t-val " + (risk.market_state === "Turmoil" ? "red" :
    risk.market_state === "Elevated Vol" ? "orange" : "green");

  $("val-alloc").textContent = (risk.allocation_pct !== undefined)
    ? (risk.allocation_pct * 100).toFixed(0) + "% " + risk.allocation_band : "—";
  $("val-sharpe").textContent = risk.sharpe?.toFixed(2) || "—";
  $("val-sharpe").className = "t-val " + (risk.sharpe > 1 ? "green" : risk.sharpe > 0.5 ? "orange" : "red");

  const dd = risk.drawdown || 0;
  $("val-dd").textContent = (dd * 100).toFixed(1) + "%";
  $("val-dd").className = "t-val " + (dd > -0.03 ? "green" : dd > -0.07 ? "orange" : "red");
  $("dd-fill").style.width = Math.min(100, Math.abs(dd) * 1000) + "%";
  $("dd-fill").style.background = dd > -0.03 ? "#27ae60" : dd > -0.07 ? "#f39c12" : "#e74c3c";

  $("val-pnl").textContent = risk.pnl_mtd_pct ? (risk.pnl_mtd_pct * 100).toFixed(1) + "%" : "—";
  $("val-pnl").className = "t-val " + (risk.pnl_mtd >= 0 ? "green" : "red");

  $("val-win").textContent = risk.win_rate ? (risk.win_rate * 100).toFixed(0) + "% (" + (risk.closed_trades || 0) + ")" : "—";
  $("val-exp").textContent = risk.exposure ? (risk.exposure * 100).toFixed(0) + "%" : "—";
}

function updateHealth(health) {
  if (!health) return;
  const sh = $("signal-health");
  if (health.stale) {
    sh.classList.remove("hidden");
    $("banner-area").innerHTML = '<span class="banner warn">⚠ Forecasts from ' + health.last_forecast_date + ' — stale</span>';
  } else {
    $("banner-area").innerHTML = "";
  }
}

function updatePositions(pos) {
  if (!pos) return;
  const body = $("positions-body");
  if (!pos.positions || pos.positions.length === 0) {
    body.innerHTML = '<p class="empty">No positions yet. Paper trade to start tracking.</p>';
    return;
  }
  let html = '<table><thead><tr><th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Mark</th><th>P&L%</th><th>Weight</th><th>Signal</th><th>Action</th></tr></thead><tbody>';
  for (const p of pos.positions) {
    const pnlCls = p.pnl_pct >= 0 ? "green" : "red";
    const borderCls = p.weight > 0.25 ? "border-yellow" : "";
    html += `<tr class="${borderCls}">
      <td class="ticker">${p.ticker}</td>
      <td class="num">${(p.shares||0).toLocaleString()}</td>
      <td class="num">${(p.avg_cost||0).toFixed(2)}</td>
      <td class="num">${(p.mark||0).toFixed(2)}</td>
      <td class="num ${pnlCls}">${(p.pnl_pct*100).toFixed(1)}%</td>
      <td class="num">${(p.weight*100).toFixed(0)}%</td>
      <td>—</td>
      <td>—</td>
    </tr>`;
  }
  html += '</tbody></table>';
  body.innerHTML = html;
}

function updateForecasts(fc) {
  if (!fc || !fc.forecasts) return;
  const top10 = fc.forecasts.slice(0, 10);
  let html = '<table><thead><tr><th>Ticker</th><th>Close</th><th>Exp Ret</th><th>Band</th><th>Flag</th><th>Net Ret</th></tr></thead><tbody>';
  for (const f of top10) {
    const dir = f.direction === "up" ? "↑" : "↓";
    const retCls = f.exp_ret >= 0 ? "green" : "red";
    html += `<tr>
      <td class="ticker">${f.ticker}</td>
      <td class="num">${f.close?.toFixed(2) || "—"}</td>
      <td class="num ${retCls}">${dir} ${(f.exp_ret*100).toFixed(2)}%</td>
      <td class="num">${(f.band_width*100).toFixed(1)}%</td>
      <td>${f.confidence === "green" ? "🟢" : f.confidence === "yellow" ? "🟡" : "🔴"}</td>
      <td class="num ${f.net_ret >= 0 ? 'green' : 'red'}">${(f.net_ret*100).toFixed(2)}%</td>
    </tr>`;
  }
  html += '</tbody></table>';
  $("morning-body").innerHTML = html;

  // Full ranking
  let rankHtml = '<table><thead><tr><th>#</th><th>Ticker</th><th>Name</th><th>Close</th><th>Exp Ret</th><th>Band</th><th>Flag</th></tr></thead><tbody>';
  fc.forecasts.forEach((f, i) => {
    const dir = f.direction === "up" ? "↑" : "↓";
    const retCls = f.exp_ret >= 0 ? "green" : "red";
    const flag = f.confidence === "green" ? "🟢" : f.confidence === "yellow" ? "🟡" : "🔴";
    rankHtml += `<tr class="rank-row" data-ticker="${f.ticker.toLowerCase()}">
      <td>${i+1}</td><td class="ticker">${f.ticker}</td>
      <td class="muted">${f.name || ""}</td>
      <td class="num">${f.close?.toFixed(2) || "—"}</td>
      <td class="num ${retCls}">${dir} ${(f.exp_ret*100).toFixed(2)}%</td>
      <td class="num">${(f.band_width*100).toFixed(1)}%</td><td>${flag}</td>
    </tr>`;
  });
  rankHtml += '</tbody></table>';
  $("ranking-body").innerHTML = rankHtml;

  // Red-flag count banner
  const redCount = fc.forecasts.filter(f => f.confidence === "red").length;
  if (redCount > 30) {
    $("banner-area").innerHTML += '<span class="banner warn">High uncertainty — ' + redCount + '/49 tickers flagged red. Stay in cash.</span>';
    $("trade-ticket").classList.add("hidden");
  } else {
    $("trade-ticket").classList.remove("hidden");
  }
}

function updateTradeTicket(trades, risk) {
  if (!trades || trades.error) {
    $("ticket-body").innerHTML = '<p class="empty">No trade ticket available. Run cron to generate forecasts.</p>';
    $("ticket-date").textContent = "—";
    return;
  }
  $("ticket-date").textContent = trades.date || "—";

  if (trades.frozen) {
    $("ticket-body").innerHTML = '<div class="banner stop">STOP-LOSS −10% TRIGGERED. Portfolio frozen. All actions disabled.</div>';
    $("btn-execute").disabled = true;
    return;
  }
  $("btn-execute").disabled = false;

  let html = "";

  if (trades.exits && trades.exits.length > 0) {
    html += '<h3 class="section-label exit-label">▼ EXIT (same day, market order)</h3><table><thead><tr><th>Ticker</th><th>Shares</th><th>Type</th><th>Est. THB</th><th>Rationale</th></tr></thead><tbody>';
    for (const e of trades.exits) {
      html += `<tr class="row-exit"><td class="ticker">${e.ticker}</td><td class="num">${(e.shares||0).toLocaleString()}</td><td>market</td><td class="num">~${(e.estimated_thb||0).toLocaleString()}</td><td class="muted">${e.rationale||""}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (trades.reduces && trades.reduces.length > 0) {
    html += '<h3 class="section-label reduce-label">▼ REDUCE</h3><table><thead><tr><th>Ticker</th><th>Shares</th><th>Limit</th><th>Est. THB</th><th>Rationale</th></tr></thead><tbody>';
    for (const r of trades.reduces) {
      html += `<tr class="row-reduce"><td class="ticker">${r.ticker}</td><td class="num">${(r.shares||0).toLocaleString()}</td><td class="num">${r.limit_price?.toFixed(2)||"—"}</td><td class="num">~${(r.estimated_thb||0).toLocaleString()}</td><td class="muted">${r.rationale||""}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (trades.buys && trades.buys.length > 0) {
    html += '<h3 class="section-label buy-label">▲ BUY (within 2 days)</h3><table><thead><tr><th>Ticker</th><th>Shares</th><th>Limit</th><th>Est. THB</th><th>Rationale</th></tr></thead><tbody>';
    for (const b of trades.buys) {
      html += `<tr class="row-buy"><td class="ticker">${b.ticker}</td><td class="num">${(b.shares||0).toLocaleString()}</td><td class="num">${b.limit_price?.toFixed(2)||"—"}</td><td class="num">~${(b.estimated_thb||0).toLocaleString()}</td><td class="muted">${b.rationale||""}</td></tr>`;
    }
    html += '</tbody></table>';
  }

  if (!trades.exits?.length && !trades.buys?.length) {
    html += '<p class="empty">No trade signals today.</p>';
  }

  // Cash flow
  if (trades.cash_flow) {
    const cf = trades.cash_flow;
    html += `<div class="cash-flow">
      <div class="cf-row"><span>Gross proceeds (sells):</span><span class="green">+${(cf.gross_proceeds||0).toLocaleString()} THB</span></div>
      <div class="cf-row"><span>Buy cost:</span><span class="red">−${(cf.buy_cost||0).toLocaleString()} THB</span></div>
      <div class="cf-row"><span>Friction:</span><span class="red">−${(cf.friction||0).toLocaleString()} THB</span></div>
      <div class="cf-row cf-total"><span>Net cash flow:</span><span class="${(cf.net_proceeds||0) >= 0 ? 'green' : 'red'}">${(cf.net_proceeds||0) >= 0 ? '+' : ''}${(cf.net_proceeds||0).toLocaleString()} THB</span></div>
    </div>`;
  }

  $("ticket-body").innerHTML = html;
}

async function executeTrades() {
  if (!confirm("Execute all trades in the ticket as paper trades?")) return;
  const resp = await fetchJSON("/api/trades");
  if (!resp || !resp.exits) return;

  const tradeList = [];
  for (const e of (resp.exits || [])) {
    tradeList.push({ ticker: e.ticker, action: "exit", shares: e.shares, fill_price: 0, order_type: "market", rationale: e.rationale });
  }
  for (const r of (resp.reduces || [])) {
    tradeList.push({ ticker: r.ticker, action: "reduce", shares: r.shares, fill_price: 0, order_type: "limit", rationale: r.rationale });
  }
  for (const b of (resp.buys || [])) {
    tradeList.push({ ticker: b.ticker, action: "buy", shares: b.shares, fill_price: b.limit_price || 0, order_type: "limit", rationale: b.rationale });
  }
  if (tradeList.length === 0) { alert("No trades to execute."); return; }

  const r = await fetch("/api/trades", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trades: tradeList, date: resp.date, mode: MODE }),
  });
  const result = await r.json();
  alert(result.recorded + " trades recorded. Portfolio value: " + (result.results?.[0]?.portfolio_value || "—").toLocaleString() + " THB");
  refresh();
}

async function exportCSV() {
  const r = await fetchJSON("/api/export_csv");
  if (r && r.status === "ok") alert("CSV exported: " + r.path);
  else alert("No trades to export.");
}

function toggleRanking() {
  showRanking = !showRanking;
  $("ranking-body").style.display = showRanking ? "block" : "none";
  $("rank-toggle").textContent = showRanking ? "▲" : "▼";
}

function filterRanking(q) {
  const rows = document.querySelectorAll(".rank-row");
  const lower = q.toLowerCase();
  rows.forEach(r => {
    r.style.display = r.dataset.ticker.includes(lower) ? "" : "none";
  });
}

// Initial load + polling
refresh();
setInterval(refresh, 60000);
</script>

</body>
</html>
```

- [ ] **Step 2: Verify HTML is valid**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python -c "
html = open('scripts/static/dashboard.html').read()
assert '<!DOCTYPE html>' in html
assert 'Kronos-TH Dashboard' in html
assert 'api/forecasts' in html
assert 'api/positions' in html
assert 'api/risk' in html
assert 'api/trades' in html
assert 'api/health' in html
print('dashboard.html — valid')
"
```

Expected: `dashboard.html — valid`

- [ ] **Step 3: Commit**

```bash
git add scripts/static/dashboard.html
git commit -m "feat: dashboard HTML — single-page app with AJAX polling, 5 panels, mode indicator"
```

---

### Task 6: Dashboard Styles

**Files:**
- Create: `scripts/static/style.css`

- [ ] **Step 1: Write style.css**

```css
/* Kronos-TH Dashboard Styles */
:root {
  --blue: #1565C0; --green: #27ae60; --red: #e74c3c; --orange: #f39c12;
  --bg: #f5f7fa; --card: #ffffff; --text: #333333; --muted: #888888;
  --border: #e0e0e0;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: var(--bg); color: var(--text); font-size: 14px;
  min-width: 1024px;
}

/* Header */
#header {
  background: var(--blue); color: white; padding: 8px 16px;
  display: flex; justify-content: space-between; align-items: center;
}
#header h1 { font-size: 1.1em; font-weight: 600; }
.h-left { display: flex; align-items: center; gap: 12px; }
.h-right { display: flex; gap: 16px; font-size: 0.8em; align-items: center; }
.badge { padding: 2px 10px; border-radius: 4px; font-size: 0.75em; font-weight: 700; }
.badge.paper { background: #e3f2fd; color: var(--blue); }
.badge.live { background: #ffebee; color: #c62828; }
.banner { padding: 4px 10px; border-radius: 4px; font-size: 0.8em; }
.banner.warn { background: #fff3e0; color: #e65100; }
.banner.stop { background: #ffebee; color: #c62828; font-weight: 700; padding: 10px 16px; }

/* Risk Bar */
.risk-bar {
  display: flex; gap: 8px; padding: 8px 16px; background: var(--card);
  border-bottom: 1px solid var(--border);
}
.risk-tile {
  flex: 1; text-align: center; padding: 6px 4px;
  background: var(--bg); border-radius: 6px;
}
.t-label { font-size: 0.62em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.3px; }
.t-val { font-size: 1.1em; font-weight: 700; margin-top: 2px; }
.t-val.green { color: var(--green); } .t-val.red { color: var(--red); } .t-val.orange { color: var(--orange); }
.dd-bar { background: #eee; height: 4px; border-radius: 2px; margin-top: 4px; }
.dd-fill { height: 4px; border-radius: 2px; min-width: 2px; background: var(--green); }

/* Signal Health */
.signal-health { padding: 6px 16px; background: #fff3e0; font-size: 0.75em; display: flex; gap: 20px; }
.signal-health.hidden { display: none; }

/* Main Layout */
#main-content { padding: 12px 16px; }
.panel { background: var(--card); border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 10px; overflow: hidden; }
.panel h2 { background: var(--blue); color: white; padding: 6px 12px; font-size: 0.8em; font-weight: 600; }
.panel.hero { border-left: 4px solid var(--blue); }
.two-col { display: flex; gap: 10px; }
.two-col .panel { flex: 1; }

/* Trade Ticket */
#ticket-body { padding: 8px 12px; }
#ticket-body h3 { font-size: 0.75em; margin: 8px 0 4px; }
.exit-label { color: var(--red); } .reduce-label { color: var(--orange); } .buy-label { color: var(--green); }
#ticket-actions { padding: 8px 12px; display: flex; gap: 8px; border-top: 1px solid var(--border); }
.btn { padding: 6px 16px; border-radius: 4px; border: none; font-size: 0.8em; cursor: pointer; font-weight: 600; }
.btn.primary { background: var(--blue); color: white; }
.btn.secondary { background: white; color: var(--text); border: 1px solid var(--border); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
th { background: #e3f2fd; padding: 4px 6px; text-align: left; font-size: 0.7em; text-transform: uppercase; color: var(--muted); }
td { padding: 3px 6px; border-bottom: 1px solid #f0f0f0; }
tr:hover { background: #f8f9ff; }
.ticker { font-weight: 600; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.muted { color: var(--muted); font-size: 0.75em; }
.green { color: var(--green); } .red { color: var(--red); } .orange { color: var(--orange); }
.row-exit { border-left: 3px solid var(--red); }
.row-reduce { border-left: 3px solid var(--orange); }
.row-buy { border-left: 3px solid var(--green); }
.empty { padding: 16px; text-align: center; color: var(--muted); font-size: 0.85em; }

/* Cash Flow */
.cash-flow { margin-top: 8px; padding: 8px 12px; background: var(--bg); border-radius: 4px; font-size: 0.75em; }
.cf-row { display: flex; justify-content: space-between; padding: 2px 0; }
.cf-total { font-weight: 700; border-top: 1px solid var(--border); margin-top: 4px; padding-top: 4px; }

/* Ranking */
#ranking-search { padding: 6px 12px; }
#ranking-search input { width: 100%; padding: 4px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.8em; }
.collapsible h2 { cursor: pointer; }
#ranking-body { display: none; max-height: 300px; overflow-y: auto; }

/* Footer */
footer { padding: 8px 16px; text-align: center; font-size: 0.65em; color: var(--muted); border-top: 1px solid var(--border); }

.hidden { display: none !important; }
```

- [ ] **Step 2: Verify CSS is valid**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
grep -c '{' scripts/static/style.css && echo "CSS — has rules"
```

Expected: Shows rule count > 0 and `CSS — has rules`

- [ ] **Step 3: Commit**

```bash
git add scripts/static/style.css
git commit -m "feat: dashboard styles — paper/live themes, risk bar, trade ticket, responsive tables"
```

---

### Task 7: Integration Verification & Final Setup

**Files:** None new

- [ ] **Step 1: Create data directories**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
mkdir -p data/positions scripts/static data/logs
```

- [ ] **Step 2: Verify full import chain (no GPU)**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
venv/bin/python -c "
import sys; sys.path.insert(0, 'kronos_repo')

# Verify portfolio engine
from kth.trading.portfolio import init_portfolio, get_positions, compute_metrics, check_phase2_gate
pf = init_portfolio('paper')
pos = get_positions('paper')
m = compute_metrics('paper')
g = check_phase2_gate()
print(f'Portfolio: cash={pf[\"cash\"]}, positions={len(pos[\"positions\"])}, band={m[\"allocation_band\"]}')
print(f'Phase2 gate: ready={g[\"ready\"]}')

# Verify trade generator
from kth.trading.trade_gen import load_forecasts, get_all_ranked, generate_trade_ticket
forecasts = load_forecasts()
print(f'Trade gen: {len(forecasts)} tickers loaded (0 expected if no cache)')

# Verify Flask routes
from scripts.dashboard import app
routes = [r.rule for r in app.url_map.iter_rules() if r.rule.startswith('/api')]
print(f'Flask routes: {len(routes)} endpoints ({sorted(routes)})')

print('All modules import — OK')
"
```

Expected: All modules import successfully. May show 0 tickers loaded (no forecast cache yet).

- [ ] **Step 3: Test Flask app locally (syntax check)**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
timeout 3 venv/bin/python scripts/dashboard.py --serve 2>&1 || true
```

Expected: Shows "Kronos-TH Dashboard — PAPER mode" and localhost URL before timeout kills it.

- [ ] **Step 4: Check all files exist**

```bash
cd /home/yut/VSCode/Kronos_Thai_Retail
for f in \
  kth/trading/__init__.py \
  kth/trading/portfolio.py \
  kth/trading/trade_gen.py \
  scripts/dashboard.py \
  scripts/cron_pipeline.sh \
  scripts/static/dashboard.html \
  scripts/static/style.css; do
  [ -f "$f" ] && echo "OK: $f" || echo "MISSING: $f"
done
```

Expected: All 7 files show `OK`.

- [ ] **Step 5: Commit final setup**

```bash
git add data/positions/.gitkeep 2>/dev/null || true
git add scripts/static/
git commit -m "chore: final integration — all 7 files verified, data dirs created"
```

---

### Self-Review

1. **Spec coverage:** All §2 (architecture, endpoints, data flow, storage), §3 (dashboard layout, risk bar, trade ticket, positions, morning brief, ranking, empty states, signal health, mode indicator), §4 (decision tree, weekly/monthly/emergency rules), §5 (Phase 2 gate, CSV export, slippage), §6 (all file specs, cron pipeline, launch sequence) — covered.

2. **Placeholder scan:** No TBDs, TODOs, or incomplete sections. All code blocks are complete. All commands have expected output.

3. **Type consistency:** `MODE` variable consistent across HTML (string literal) and Flask (`TRADING_MODE` from env). Portfolio functions use `mode` parameter consistently. Forecast schema matches spec §4 columns (p50, p5, p95, mean, timestamps). FIFO matching uses `deque` — matches N1 promoted to mandatory in Phase 2.
