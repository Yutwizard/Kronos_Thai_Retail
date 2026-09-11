"""ExecutionResolver — one adapter for the underlying→execution seam.

Every Trade Signal starts life on an *underlying* ticker (what the model
forecast) but executes on an *execution* ticker (what you place the order
for): the DR ticker for DR-backed trades, the ticker itself otherwise.
That translation — ticker, price, display name, DR premium, and the
same-underlying guard — used to sprawl across per-call-site
try/except ImportError fallback triples. It now lives here, behind one
small interface.

Without the kth_dr plugin every method is the identity/no-op (a plain
ticker executes as itself); with it, each method delegates. Non-DR is
the identity path *inside* the adapter, never a caller branch.
"""
from __future__ import annotations

from kth.data.pricestore import PriceStore


class ExecutionResolver:
    """Resolves underlying tickers to their execution form."""

    def __init__(self, prices: PriceStore | None = None) -> None:
        self._prices = prices or PriceStore()
        try:
            from kth_dr.trade_gen_dr import (
                resolve_execution_ticker,
                resolve_execution_price,
                resolve_display_name,
                is_held_underlying,
            )
            from kth_dr.loader_dr import enrich_dr_premium
        except ImportError:
            resolve_execution_ticker = lambda t: t  # noqa: E731
            resolve_execution_price = lambda u, e, c: c  # noqa: E731
            resolve_display_name = lambda t, fallback: fallback  # noqa: E731
            enrich_dr_premium = lambda t, c, get_close: ("", None)  # noqa: E731
            is_held_underlying = lambda held, cand: False  # noqa: E731
        self._execution_ticker = resolve_execution_ticker
        self._execution_price = resolve_execution_price
        self._display_name = resolve_display_name
        self._enrich_dr_premium = enrich_dr_premium
        self._is_held_underlying = is_held_underlying

    def execution_ticker(self, ticker: str) -> str:
        """DR ticker for a DR-backed underlying, else the ticker itself."""
        return self._execution_ticker(ticker)

    def execution_price(
        self, underlying_ticker: str, execution_ticker: str, underlying_close: float
    ) -> float:
        """Price to actually trade at — the DR's own SET close in THB for
        DR-backed trades, the underlying close otherwise."""
        return self._execution_price(underlying_ticker, execution_ticker, underlying_close)

    def display_name(self, ticker: str, fallback: str) -> str:
        """DR mapping's friendly name, else the caller's fallback."""
        return self._display_name(ticker, fallback)

    def premium(self, exec_ticker: str, exec_close: float) -> tuple[str, float | None]:
        """(underlying_ticker, premium_pct) — ''/None for non-DR tickers or
        when the premium can't be computed. Display-only; never feeds
        rank_score or any buy/filter decision."""
        return self._enrich_dr_premium(exec_ticker, exec_close, self._prices.get_close)

    def is_held_underlying(self, held_tickers: list, candidate_underlying: str) -> bool:
        """True when the candidate is already held directly or via a DR."""
        return bool(self._is_held_underlying(held_tickers, candidate_underlying))
