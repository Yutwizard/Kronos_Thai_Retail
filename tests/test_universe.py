"""Tests for kth.data.universe — friction, sector, ticker-class lookup, SET+DR-only scope."""
from pathlib import Path

from kth.data.universe import (
    _TICKER_CLASS_MAP,
    FRICTION,
    UNIVERSE,
    get_friction,
    get_one_way_friction_rate,
    get_sector,
    get_ticker_class,
)


def test_get_friction_known_ticker():
    """H3: get_friction returns the right dict for a known Thai equity ticker."""
    f = get_friction("PTT.BK")
    assert f["commission_oneway"] == 0.00168
    assert f["slippage_oneway"] == 0.0010
    assert get_one_way_friction_rate("PTT.BK") == 0.00268


def test_get_friction_fallback_unknown():
    """H3: get_friction returns conservative default for unknown ticker."""
    f = get_friction("UNKNOWN.TICKER")
    assert f["commission_oneway"] == 0.003
    assert f["slippage_oneway"] == 0.001


def test_no_inline_friction_fallbacks_remain():
    """H3: no module should have inline friction dict-literal fallbacks."""
    for f in ["kth/backtest/walkforward.py", "kth/trading/portfolio.py",
              "kth/trading/trade_gen.py", "kth/pipeline/daily.py"]:
        text = Path(f).read_text()
        assert '{"commission_oneway":' not in text, \
            f"{f} still has inline friction fallback — use universe.get_friction()"


def test_mega_bk_sector_is_healthcare():
    """MEGA.BK (Mega Lifesciences) is a healthcare company, not Retail."""
    assert get_sector("MEGA.BK") == "Healthcare", \
        f"MEGA.BK should be Healthcare, got {get_sector('MEGA.BK')}"


def test_universe_is_set_only():
    """UNIVERSE must contain only thai_equity and thai_index -- DR lives in the
    separate kth_dr plugin (register_asset_class()), never in UNIVERSE itself.
    Other asset classes (us_equity, etf_global, commodity, crypto, bond_proxy,
    reit, fx_macro) were archived 2026-07-16 -- see archive/other-asset-classes/."""
    assert set(UNIVERSE.keys()) == {"thai_equity", "thai_index"}, UNIVERSE.keys()
    assert set(FRICTION.keys()) == {"thai_equity", "thai_index"}, FRICTION.keys()


def test_cpnreit_folded_into_thai_equity():
    """CPNREIT.BK (formerly a standalone 'reit' class with VNQ) now inherits
    thai_equity's friction and is sector-mapped to Property."""
    assert get_ticker_class("CPNREIT.BK") == "thai_equity"
    assert get_friction("CPNREIT.BK") == get_friction("PTT.BK")
    assert get_sector("CPNREIT.BK") == "Property"


def test_get_ticker_class_o1_lookup():
    """get_ticker_class must use O(1) dict lookup."""
    assert "AOT.BK" in _TICKER_CLASS_MAP, "Reverse-lookup map not built"
    assert _TICKER_CLASS_MAP["AOT.BK"] == "thai_equity"
    assert get_ticker_class("NONEXISTENT") is None
