"""LotLedger — the single FIFO module for Position accounting.

Four copies of first-bought-first-sold matching used to live in portfolio
(win counts, realized P&L), metrics (holding periods) and walkforward's day
loop (live gross_return). They disagreed on gross-vs-net and on what a
"round trip" is, with no interface test able to catch it. All matching now
lives here, behind one stateful interface:

- Step it live (walkforward): record_buy/record_sell as the loop executes;
  record_sell returns the matched gross immediately.
- Feed it post-hoc (portfolio, metrics): construct, replay the trade log,
  then query wins()/realized_pnl()/holding_periods().

Quirks preserved verbatim (behavior freeze — revisit via follow-up issues,
not drive-by fixes):
- A sell event with no open lots still counts as closed, never a win.
- holding_periods() records ONE period per sell event (oldest open lot
  date), even when the sell only partially consumes the lot.
- wins() defaults to gross, realized_pnl() defaults to net — the two
  historical semantics, now an explicit net_of_friction flag instead of
  two separate functions.
"""
from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd


class LotLedger:
    """Per-ticker FIFO lots with eager per-sell-event accounting."""

    def __init__(self) -> None:
        self._lots: dict = defaultdict(deque)  # ticker -> deque of lots
        self._buy_dates: dict = defaultdict(deque)  # ticker -> deque of dates
        self._events: list[dict] = []  # one per record_sell call
        self._chunks: list[tuple[float, float]] = []  # (gross, net) per lot consumed

    def record_buy(
        self,
        ticker: str,
        shares: float,
        price: float,
        date=None,
        friction: float = 0.0,
    ) -> None:
        """Open (or add to) a lot. friction is the whole-trade cost,
        pro-rated per share inside."""
        shares = float(shares)
        if shares <= 0:
            return
        price = float(price)
        self._lots[ticker].append({
            "shares": shares,
            "price": price,
            "fps": float(friction or 0) / shares,
            "date": pd.Timestamp(date) if date is not None else None,
        })
        if date is not None:
            self._buy_dates[ticker].append(pd.Timestamp(date))

    def record_sell(
        self,
        ticker: str,
        shares: float,
        price: float,
        date=None,
        friction: float = 0.0,
    ) -> float:
        """Consume open lots FIFO. Returns the matched gross P&L
        (Σ (price − lot_price) × matched) for the live loop; the caller
        decides whether to book it. The event counts as closed even when
        no lots are open."""
        shares = float(shares)
        price = float(price)
        sell_fps = float(friction or 0) / shares if shares > 0 else 0.0
        gross_event = 0.0
        net_event = 0.0
        remaining = shares
        queue = self._lots[ticker]
        while remaining > 0 and queue:
            lot = queue.popleft()
            matched = min(remaining, lot["shares"])
            gross = (price - lot["price"]) * matched
            net = gross - matched * lot["fps"] - matched * sell_fps
            self._chunks.append((gross, net))
            gross_event += gross
            net_event += net
            remaining -= matched
            if lot["shares"] > matched:
                queue.appendleft({
                    "shares": lot["shares"] - matched,
                    "price": lot["price"],
                    "fps": lot["fps"],
                    "date": lot["date"],
                })
        holding = None
        if date is not None and self._buy_dates[ticker]:
            buy_date = self._buy_dates[ticker].popleft()
            holding = (pd.Timestamp(date) - buy_date).days
        self._events.append({"gross": gross_event, "net": net_event, "holding": holding})
        return gross_event

    def wins(self, net_of_friction: bool = False) -> tuple[int, int]:
        """(closed_round_trips, wins). A round trip is one sell event; a win
        is an event with positive aggregate P&L (gross by default)."""
        key = "net" if net_of_friction else "gross"
        closed = len(self._events)
        wins = sum(1 for e in self._events if e[key] > 0)
        return closed, wins

    def realized_pnl(self, net_of_friction: bool = True) -> list[float]:
        """Per-consumed-chunk P&L (net of friction by default)."""
        idx = 1 if net_of_friction else 0
        return [c[idx] for c in self._chunks]

    def holding_periods(self) -> list[float]:
        """Holding days, one per sell event that met a dated lot."""
        return [e["holding"] for e in self._events if e["holding"] is not None]


def feed_paper_trades(trades: list[dict]) -> LotLedger:
    """Replay a paper trade log (action/shares/price/friction_cost/date
    dicts) into a fresh ledger. One shared feeder so every paper query
    sees the same replay."""
    ledger = LotLedger()
    for t in trades:
        action = t.get("action")
        if action == "buy":
            ledger.record_buy(
                t["ticker"], t["shares"], t["price"],
                date=t.get("date"), friction=t.get("friction_cost", 0) or 0,
            )
        elif action in ("exit", "sell", "reduce"):
            ledger.record_sell(
                t["ticker"], t["shares"], t["price"],
                date=t.get("date"), friction=t.get("friction_cost", 0) or 0,
            )
    return ledger
