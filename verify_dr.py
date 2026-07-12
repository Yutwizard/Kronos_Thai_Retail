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
