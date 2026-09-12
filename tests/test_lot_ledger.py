"""Tests for kth.accounting.lot_ledger.LotLedger — the single FIFO module.

Vectors are hand-computed from the four implementations this replaces
(portfolio._compute_fifo_wins/_compute_fifo_pnl, metrics'
_compute_avg_holding_period, walkforward's inline lots loop) so the
migration is pinned to identical numbers.
"""
import pytest

from kth.accounting.lot_ledger import LotLedger


def test_wins_counts_gross_per_sell_event():
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0)
    ledger.record_buy("A", 100, 12.0)
    ledger.record_sell("A", 150, 11.0)  # 100x(11-10) + 50x(11-12) = +50
    ledger.record_sell("A", 50, 11.0)  # 50x(11-12) = -50
    ledger.record_sell("B", 10, 5.0)  # no lots: closed, not a win
    assert ledger.wins() == (3, 1)


def test_realized_pnl_is_net_of_friction_per_chunk():
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0, friction=2.0)
    ledger.record_sell("A", 100, 11.0, friction=1.0)
    # gross 100 - buy 2.0 - sell 1.0
    assert ledger.realized_pnl() == pytest.approx([97.0])
    assert ledger.realized_pnl(net_of_friction=False) == pytest.approx([100.0])


def test_net_flag_flips_win_when_friction_eats_gross():
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0)
    ledger.record_sell("A", 100, 10.05, friction=10.0)  # gross +5, net -5
    assert ledger.wins() == (1, 1)
    assert ledger.wins(net_of_friction=True) == (1, 0)


def test_holding_period_is_one_per_sell_event():
    # Quirk preserved from metrics: a 100-share buy split across two 50-share
    # sells records ONE holding period (oldest open lot date), not two.
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0, date="2026-01-01")
    ledger.record_sell("A", 50, 11.0, date="2026-01-05")
    ledger.record_sell("A", 50, 11.0, date="2026-01-10")
    assert ledger.holding_periods() == [4]


def test_holding_period_full_round_trip():
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0, date="2026-01-01")
    ledger.record_sell("A", 100, 11.0, date="2026-01-06")
    assert ledger.holding_periods() == [5]


def test_record_sell_returns_matched_gross_for_live_loop():
    # walkforward's full-exit gross: (exec/entry - 1) x matched value.
    ledger = LotLedger()
    ledger.record_buy("A", 10, 100.0)
    assert ledger.record_sell("A", 10, 110.0) == pytest.approx(100.0)


def test_partial_sells_consume_lots_silently():
    ledger = LotLedger()
    ledger.record_buy("A", 100, 10.0)
    assert ledger.record_sell("A", 30, 12.0) == pytest.approx(60.0)
    assert ledger.record_sell("A", 70, 9.0) == pytest.approx(-70.0)
    assert ledger.wins() == (2, 1)


def test_empty_ledger_queries():
    ledger = LotLedger()
    assert ledger.wins() == (0, 0)
    assert ledger.realized_pnl() == []
    assert ledger.holding_periods() == []
