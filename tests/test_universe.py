"""Tests for kth.data.universe — friction, sector, ticker-class lookup, fx_macro exclusion."""
from pathlib import Path

from kth.data.universe import (
    _TICKER_CLASS_MAP,
    get_all_tickers,
    get_all_tickers_including_features,
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


def test_fx_macro_excluded_from_investable():
    """fx_macro tickers must not appear in get_all_tickers()."""
    tickers = get_all_tickers()
    fx = [t for t in tickers if get_ticker_class(t) == "fx_macro"]
    assert len(fx) == 0, f"fx_macro leaked into investable: {fx}"
    all_t = get_all_tickers_including_features()
    assert len(all_t) == 100, \
        f"get_all_tickers_including_features should return 100, got {len(all_t)}"
    assert "THB=X" in all_t, "THB=X should be in including_features"


def test_get_ticker_class_o1_lookup():
    """get_ticker_class must use O(1) dict lookup."""
    assert "AOT.BK" in _TICKER_CLASS_MAP, "Reverse-lookup map not built"
    assert _TICKER_CLASS_MAP["AOT.BK"] == "thai_equity"
    assert get_ticker_class("BTC-USD") == "crypto"
    assert get_ticker_class("NONEXISTENT") is None
