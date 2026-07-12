"""Verify DR (Depositary Receipt) integration — plugin hook, mapping, trade-gen
wiring, positions schema. Follows the repo convention (see verify_fixes.py):
plain assert + print("PASS ..."), no pytest.

Run: python verify_dr.py
"""

# ---- Task 1: universe.py plugin hook ----

def test_register_asset_class_adds_ticker_class():
    """Plugin-registered tickers must be findable by get_ticker_class."""
    from kth.data.universe import register_asset_class, get_ticker_class, _extra_ticker_class
    register_asset_class({"TESTDR.BK": "dr"})
    assert get_ticker_class("TESTDR.BK") == "dr"
    _extra_ticker_class.pop("TESTDR.BK", None)
    print("PASS test_register_asset_class_adds_ticker_class")


def test_register_asset_class_adds_sector():
    """Plugin-registered sectors must be findable by get_sector."""
    from kth.data.universe import register_asset_class, get_sector, _extra_sector
    register_asset_class({}, sector={"TESTDR.BK": "Global"})
    assert get_sector("TESTDR.BK") == "Global"
    _extra_sector.pop("TESTDR.BK", None)
    print("PASS test_register_asset_class_adds_sector")


def test_register_asset_class_adds_friction():
    """Plugin-registered friction must be findable by get_friction."""
    from kth.data.universe import register_asset_class, get_friction, _extra_friction, _extra_ticker_class
    register_asset_class({"TESTDR.BK": "dr"}, friction={"dr": {"commission_oneway": 0.001, "slippage_oneway": 0.001}})
    f = get_friction("TESTDR.BK")
    assert f["commission_oneway"] == 0.001
    assert f["slippage_oneway"] == 0.001
    _extra_friction.pop("dr", None)
    _extra_ticker_class.pop("TESTDR.BK", None)
    print("PASS test_register_asset_class_adds_friction")


# ---- Task 2: kth_dr/universe_dr.py — DR mapping getters ----

_TEST_MAPPING = {
    "_meta": {"generated": "2026-07-12", "status": "needs_review"},
    "005930.KS": {
        "display_name": "Samsung Electronics",
        "underlying_exchange": "KR",
        "underlying_currency": "KRW",
        "fx_ticker": "THB=X",
        "primary_dr": "SAMSUNG80.BK",
        "alternatives": [
            {
                "dr_ticker": "SAMSUNG80.BK",
                "ratio": 80,
                "liquidity_rank": 1,
                "avg_volume_30d": 45000,
                "history_rows": 1050,
                "verified": True,
            }
        ],
    },
    "AAPL": {
        "display_name": "Apple Inc.",
        "excluded_reason": "already_direct",
        "note": "AAPL is already directly investable",
    },
    "_unresolved": [{"dr_ticker": "XYZ80.BK", "reason": "no underlying info"}],
}


def _with_test_mapping(tmp, check_fn):
    """Point DR_MAP_PATH at a throwaway mapping.json, run check_fn(), restore after.
    Always call through this helper — never leave DR_MAP_PATH pointed at a temp
    file, or later verify_dr.py functions (and any real pipeline run in the same
    process) will silently read test data."""
    import json
    from pathlib import Path
    from kth_dr import universe_dr as ud
    test_path = Path(tmp) / "mapping.json"
    with open(test_path, "w") as f:
        json.dump(_TEST_MAPPING, f)
    orig_path = ud.DR_MAP_PATH
    ud.DR_MAP_PATH = test_path
    ud.DR_MAP.clear()
    try:
        check_fn()
    finally:
        ud.DR_MAP_PATH = orig_path
        ud.DR_MAP.clear()


def test_load_dr_mapping_returns_dict(tmp):
    from kth_dr.universe_dr import _load_dr_mapping
    def check():
        data = _load_dr_mapping()
        assert "005930.KS" in data
        assert data["005930.KS"]["alternatives"][0]["dr_ticker"] == "SAMSUNG80.BK"
    _with_test_mapping(tmp, check)
    print("PASS test_load_dr_mapping_returns_dict")


def test_get_dr_for_underlying_returns_verified(tmp):
    from kth_dr.universe_dr import get_dr_for_underlying
    def check():
        dr = get_dr_for_underlying("005930.KS")
        assert dr is not None
        assert dr["dr_ticker"] == "SAMSUNG80.BK"
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_for_underlying_returns_verified")


def test_get_dr_for_underlying_excluded(tmp):
    from kth_dr.universe_dr import get_dr_for_underlying
    def check():
        assert get_dr_for_underlying("AAPL") is None, "Excluded underlying should return None"
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_for_underlying_excluded")


def test_get_dr_for_underlying_nonexistent(tmp):
    from kth_dr.universe_dr import get_dr_for_underlying
    def check():
        assert get_dr_for_underlying("NONEXISTENT") is None
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_for_underlying_nonexistent")


def test_get_underlying_for_dr_found(tmp):
    from kth_dr.universe_dr import get_underlying_for_dr
    def check():
        assert get_underlying_for_dr("SAMSUNG80.BK") == "005930.KS"
    _with_test_mapping(tmp, check)
    print("PASS test_get_underlying_for_dr_found")


def test_get_underlying_for_dr_not_found(tmp):
    from kth_dr.universe_dr import get_underlying_for_dr
    def check():
        assert get_underlying_for_dr("FAKE.BK") is None
    _with_test_mapping(tmp, check)
    print("PASS test_get_underlying_for_dr_not_found")


def test_get_verified_dr_tickers(tmp):
    from kth_dr.universe_dr import get_verified_dr_tickers
    def check():
        tickers = get_verified_dr_tickers()
        assert tickers == ["SAMSUNG80.BK"], tickers
    _with_test_mapping(tmp, check)
    print("PASS test_get_verified_dr_tickers")


def test_get_dr_underlying_tickers(tmp):
    """Bug-fix regression guard: trade_gen.py's forecast loop needs underlying
    tickers, not DR tickers — see the docstring on get_dr_underlying_tickers."""
    from kth_dr.universe_dr import get_dr_underlying_tickers
    def check():
        tickers = get_dr_underlying_tickers()
        assert tickers == ["005930.KS"], tickers
        assert "SAMSUNG80.BK" not in tickers
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_underlying_tickers")


def test_get_dr_info_for_display(tmp):
    from kth_dr.universe_dr import get_dr_info_for_display
    def check():
        info = get_dr_info_for_display("SAMSUNG80.BK")
        assert info is not None
        assert info["underlying_ticker"] == "005930.KS"
        assert info["ratio"] == 80
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_info_for_display")


# ---- Task 5: kth_dr/discover_drs.py — seed loading, ranking, exclusion ----

def test_load_seed_list_returns_dict():
    from kth_dr.discover_drs import load_seed_list
    seed = load_seed_list()
    assert isinstance(seed, dict)
    assert "005930.KS" in seed
    print("PASS test_load_seed_list_returns_dict")


def test_load_seed_list_has_correct_structure():
    from kth_dr.discover_drs import load_seed_list
    seed = load_seed_list()
    entry = seed["005930.KS"]
    assert isinstance(entry, list)
    assert entry[0]["dr_ticker"] == "SAMSUNG80.BK"
    assert entry[0]["ratio"] == 80
    print("PASS test_load_seed_list_has_correct_structure")


def test_seed_list_uses_home_market_tickers_not_us_adr():
    """Regression guard: Toyota/ASML must be keyed by their home listing, not
    their US ADR ticker, or the DR loses its reason for existing."""
    from kth_dr.discover_drs import load_seed_list
    seed = load_seed_list()
    assert "TM" not in seed, "Toyota must be keyed by 7203.T (Tokyo), not the NYSE ADR 'TM'"
    assert "ASML" not in seed, "ASML must be keyed by ASML.AS (Amsterdam), not the Nasdaq ticker 'ASML'"
    assert "7203.T" in seed
    assert "ASML.AS" in seed
    print("PASS test_seed_list_uses_home_market_tickers_not_us_adr")


def test_load_existing_mapping_no_file(tmp):
    from pathlib import Path
    from kth_dr import discover_drs as dd
    orig = dd.MAPPING_PATH
    dd.MAPPING_PATH = Path(tmp) / "nonexistent.json"
    try:
        mapping = dd.load_existing_mapping()
        assert "_meta" in mapping
        assert mapping["_meta"]["status"] == "needs_review"
    finally:
        dd.MAPPING_PATH = orig
    print("PASS test_load_existing_mapping_no_file")


def test_load_existing_mapping_with_file(tmp):
    import json
    from pathlib import Path
    from kth_dr import discover_drs as dd
    orig = dd.MAPPING_PATH
    test_path = Path(tmp) / "mapping.json"
    test_path.write_text(json.dumps({"005930.KS": {"alternatives": [{"dr_ticker": "SAMSUNG80.BK", "verified": True}]}}))
    dd.MAPPING_PATH = test_path
    try:
        mapping = dd.load_existing_mapping()
        assert "005930.KS" in mapping
        assert mapping["005930.KS"]["alternatives"][0]["verified"] is True
    finally:
        dd.MAPPING_PATH = orig
    print("PASS test_load_existing_mapping_with_file")


def test_rank_alternatives_sorts_by_volume():
    from kth_dr.discover_drs import rank_alternatives
    alts = [
        {"dr_ticker": "LOW.BK", "avg_volume_30d": 100},
        {"dr_ticker": "HIGH.BK", "avg_volume_30d": 50000},
        {"dr_ticker": "MID.BK", "avg_volume_30d": 1000},
    ]
    ranked = rank_alternatives(alts)
    assert [a["dr_ticker"] for a in ranked] == ["HIGH.BK", "MID.BK", "LOW.BK"]
    assert [a["liquidity_rank"] for a in ranked] == [1, 2, 3]
    print("PASS test_rank_alternatives_sorts_by_volume")


def test_is_already_in_universe_known():
    from kth_dr.discover_drs import is_already_in_universe
    assert is_already_in_universe("AAPL") is True
    print("PASS test_is_already_in_universe_known")


def test_is_already_in_universe_unknown():
    from kth_dr.discover_drs import is_already_in_universe
    assert is_already_in_universe("005930.KS") is False
    print("PASS test_is_already_in_universe_unknown")


# ---- Task 6: kth_dr/trade_gen_dr.py — execution resolution, same-underlying guard ----

def test_resolve_execution_ticker_non_dr():
    from kth_dr.trade_gen_dr import resolve_execution_ticker
    assert resolve_execution_ticker("PTT.BK") == "PTT.BK"
    print("PASS test_resolve_execution_ticker_non_dr")


def test_resolve_execution_price_non_dr_returns_input_close():
    from kth_dr.trade_gen_dr import resolve_execution_price
    assert resolve_execution_price("PTT.BK", "PTT.BK", 42.5) == 42.5
    print("PASS test_resolve_execution_price_non_dr_returns_input_close")


def test_get_underlying_for_held_non_dr():
    from kth_dr.trade_gen_dr import get_underlying_for_held
    assert get_underlying_for_held("PTT.BK") == "PTT.BK"
    print("PASS test_get_underlying_for_held_non_dr")


def test_is_held_underlying_no_match():
    from kth_dr.trade_gen_dr import is_held_underlying
    assert is_held_underlying(["PTT.BK", "KBANK.BK"], "AAPL") is False
    print("PASS test_is_held_underlying_no_match")


def test_is_held_underlying_empty():
    from kth_dr.trade_gen_dr import is_held_underlying
    assert is_held_underlying([], "AAPL") is False
    print("PASS test_is_held_underlying_empty")


def test_tradable_tickers_includes_thai_equity():
    """Regression guard: TRADABLE_TICKERS must never shrink below THAI_TICKERS
    even if kth_dr is broken/absent."""
    from kth.trading.trade_gen import TRADABLE_TICKERS, THAI_TICKERS
    assert set(THAI_TICKERS).issubset(set(TRADABLE_TICKERS))
    print("PASS test_tradable_tickers_includes_thai_equity")


if __name__ == "__main__":
    import inspect
    import tempfile
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        params = inspect.signature(fn).parameters
        if params:
            with tempfile.TemporaryDirectory() as tmp:
                fn(tmp)
        else:
            fn()
    print(f"ALL {len(fns)} PASSED")
