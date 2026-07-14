# Global DR Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) to implement this plan task-by-task. Steps use `- [ ]` syntax for tracking.

**Goal:** Add DR (Depositary Receipt) support to Kronos-TH — signal from underlying, execute via SET-listed DR.

**Architecture:** New `kth_dr/` package with DR mapping, discovery, and trade-gen hooks. Existing `kth/data/universe.py` gets a generic `register_asset_class()` plugin hook. `kth/trading/trade_gen.py` gets optional-import hooks that no-op if `kth_dr` is absent. Forecasts are generated on the **underlying** ticker; trade tickets and portfolio positions are keyed by the **execution ticker** (the DR itself, or the underlying unchanged if it has no DR) — every ticket/position field that involves money (price, shares, cost, friction) must come from the execution ticker's own cached close, never the underlying's.

**Tech Stack:** Python 3.10+, yfinance. **No pytest/tox** — `CLAUDE.md`'s hard scope limits explicitly exclude test frameworks. Verification follows this repo's existing convention (`verify_data_layer.py`, `verify_fixes.py`, `verify_kaggle_runtime.py`): flat `test_*()` functions, plain `assert`, `print("PASS ...")`, and a `if __name__ == "__main__":` runner that calls every `test_*` function found in `globals()`. All DR verification lives in one new `verify_dr.py` at the repo root, appended to task by task.

**Status (2026-07-14):** Tasks 1–11 implemented and verified (`python verify_dr.py` → `ALL 39 PASSED`). Tasks 1–10 are commits `bbb5c94`…`94d79dd`; Task 11 is the 2026-07-14 code-review pass (FX-pair bug, `_unresolved` crash, broken-mapping resilience). Every code block below is the **final reviewed version** — implementing this plan from scratch, task by task, reproduces the corrected code, so treat the blocks as authoritative full replacements and don't "fix" them against older commits. Runtime note: the feature stays inert until `data/dr/mapping.json` exists and a human flips `verified: true` — see `data/dr/README.md` (created in Task 11) for that workflow.

---

### Task 1: Plugin hook in universe.py

**Files:**
- Modify: `kth/data/universe.py`
- Create: `verify_dr.py`

- [x] **Step 1: Add plugin hook data structures and function**

Add after the `_DISPLAY_NAME_MAP` block (after line 168):

```python
_extra_ticker_class: dict[str, str] = {}
_extra_sector: dict[str, str] = {}
_extra_friction: dict[str, dict] = {}

def register_asset_class(
    ticker_class: dict[str, str],
    sector: dict[str, str] | None = None,
    friction: dict[str, dict] | None = None,
):
    _extra_ticker_class.update(ticker_class)
    if sector:
        _extra_sector.update(sector)
    if friction:
        _extra_friction.update(friction)
```

- [x] **Step 2: Add fallback lookups to existing getters**

In `get_ticker_class()`, after the existing `return _TICKER_CLASS_MAP.get(ticker)`:

```python
def get_ticker_class(ticker):
    result = _TICKER_CLASS_MAP.get(ticker)
    if result is not None:
        return result
    return _extra_ticker_class.get(ticker)
```

In `get_sector()`, after the existing `return SECTOR.get(ticker, "Other")`:

```python
def get_sector(ticker: str) -> str:
    result = SECTOR.get(ticker)
    if result is not None:
        return result
    return _extra_sector.get(ticker, "Other")
```

In `get_friction()`, after the existing `return dict(FRICTION.get(cls, _DEFAULT_FRICTION))`:

```python
def get_friction(ticker: str) -> dict[str, float]:
    cls = get_ticker_class(ticker)
    if cls is None:
        return dict(_DEFAULT_FRICTION)
    base = FRICTION.get(cls)
    if base is not None:
        return dict(base)
    extra = _extra_friction.get(cls)
    if extra is not None:
        return dict(extra)
    return dict(_DEFAULT_FRICTION)
```

- [x] **Step 3: Create `verify_dr.py` with the first checks**

This file grows across every task in this plan — always append, never replace. Start it with:

```python
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
```

- [x] **Step 4: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 3 PASSED`

- [x] **Step 5: Commit**

```bash
git add kth/data/universe.py verify_dr.py
git commit -m "feat(universe): add register_asset_class() plugin hook for external packages"
```

---

### Task 2: Create kth_dr package + universe_dr.py

**Files:**
- Create: `kth_dr/__init__.py` (empty for now — wired in Task 3)
- Create: `kth_dr/universe_dr.py`
- Modify: `verify_dr.py`

- [x] **Step 1: Create package directory**

```bash
mkdir -p kth_dr
touch kth_dr/__init__.py
```

- [x] **Step 2: Write universe_dr.py**

```python
"""DR mapping data — loaded from data/dr/mapping.json at import time."""
import json
import logging
from pathlib import Path

DR_MAP_PATH = Path("data/dr/mapping.json")
MIN_DR_HISTORY = 60
DR_PREMIUM_WARN_THRESHOLD = 0.05

DR_MAP: dict = {}


def _load_dr_mapping() -> dict:
    """mapping.json is hand-edited (a human flips `verified`), so a typo here
    must degrade to "no DRs" — never crash the pipeline that imports us."""
    if not DR_MAP_PATH.exists():
        return {}
    try:
        with open(DR_MAP_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning(f"DR mapping unreadable ({DR_MAP_PATH}): {e} — continuing without DRs")
        return {}
    if not isinstance(data, dict):
        logging.warning(f"DR mapping malformed ({DR_MAP_PATH}): top level must be an object — continuing without DRs")
        return {}
    return data


def _ensure_loaded():
    if not DR_MAP:
        DR_MAP.update(_load_dr_mapping())


def get_dr_for_underlying(underlying_ticker: str) -> dict | None:
    _ensure_loaded()
    entry = DR_MAP.get(underlying_ticker)
    # isinstance guard: _meta is a dict but _unresolved is a list — every DR_MAP
    # iteration/lookup below must skip non-dict entries or it AttributeErrors.
    if not isinstance(entry, dict) or "excluded_reason" in entry:
        return None
    alternatives = entry.get("alternatives", [])
    if not alternatives:
        return None
    primary_ticker = entry.get("primary_dr")
    if primary_ticker:
        for alt in alternatives:
            if alt["dr_ticker"] == primary_ticker and alt.get("verified") and alt.get("history_rows", 0) >= MIN_DR_HISTORY:
                return alt
    valid = [a for a in alternatives if a.get("verified") and a.get("history_rows", 0) >= MIN_DR_HISTORY]
    if not valid:
        return None
    return max(valid, key=lambda a: a.get("avg_volume_30d", 0))


def get_underlying_for_dr(dr_ticker: str) -> str | None:
    _ensure_loaded()
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        for alt in entry.get("alternatives", []):
            if alt["dr_ticker"] == dr_ticker:
                return underlying
    return None


def get_verified_dr_tickers() -> list[str]:
    """Flat list of DR tickers themselves (e.g. 'SAMSUNG80.BK'). Used to make sure
    DR price data gets downloaded/cached and for the discovery script — NOT for
    trade_gen's forecast loop (see get_dr_underlying_tickers below)."""
    _ensure_loaded()
    result = []
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        dr = get_dr_for_underlying(underlying)
        if dr:
            result.append(dr["dr_ticker"])
    return result


def get_dr_underlying_tickers() -> list[str]:
    """Underlying tickers that have a verified DR (e.g. '005930.KS').

    This is the list trade_gen.py's forecast loop must use — NOT
    get_verified_dr_tickers(). Kronos forecasts are always cached under the
    underlying's own ticker (the model never runs on the DR itself), so looping
    over DR tickers there would look for a forecast cache file that can never
    exist and silently drop every DR candidate. See implementation-plan review
    2026-07-12 for the bug this fixes.
    """
    _ensure_loaded()
    result = []
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        if get_dr_for_underlying(underlying):
            result.append(underlying)
    return result


def get_dr_info_for_display(dr_ticker: str) -> dict | None:
    """Return enriched display info: underlying, ratio, fx_ticker, display_name."""
    underlying = get_underlying_for_dr(dr_ticker)
    if underlying is None:
        return None
    _ensure_loaded()
    entry = DR_MAP.get(underlying, {})
    for alt in entry.get("alternatives", []):
        if alt["dr_ticker"] == dr_ticker:
            return {
                "underlying_ticker": underlying,
                "display_name": entry.get("display_name", underlying),
                "ratio": alt.get("ratio", 1),
                "fx_ticker": entry.get("fx_ticker", "THB=X"),
            }
    return None
```

- [x] **Step 3: Append verify checks**

Append to `verify_dr.py` (before the `if __name__ ==` block):

```python
# ---- Task 2: kth_dr/universe_dr.py — DR mapping getters ----

_TEST_MAPPING = {
    "_meta": {"generated": "2026-07-12", "status": "needs_review"},
    "005930.KS": {
        "display_name": "Samsung Electronics",
        "underlying_exchange": "KR",
        "underlying_currency": "KRW",
        "fx_ticker": "KRWTHB=X",
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
        assert info["fx_ticker"] == "KRWTHB=X", "must carry the mapping's own FX pair, not a THB=X default"
    _with_test_mapping(tmp, check)
    print("PASS test_get_dr_info_for_display")
```

- [x] **Step 4: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 12 PASSED` (3 from Task 1 + 9 here)

- [x] **Step 5: Commit**

```bash
git add kth_dr/ verify_dr.py
git commit -m "feat(kth_dr): add DR mapping module with getters and verified resolution"
```

---

### Task 3: Wire up __init__.py to register DRs with universe

**Files:**
- Modify: `kth_dr/__init__.py`
- Modify: `kth_dr/universe_dr.py` (add `build_registration_dicts()`)

- [x] **Step 1: Add build_registration_dicts() to universe_dr.py**

Append to `kth_dr/universe_dr.py`:

```python
def build_registration_dicts() -> tuple[dict[str, str], dict[str, str], dict[str, dict]]:
    """Build the three dicts needed by register_asset_class() from verified DRs."""
    _ensure_loaded()
    ticker_class = {}
    sector = {}
    friction = {"dr": {"commission_oneway": 0.00168, "slippage_oneway": 0.0010}}
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                dr_ticker = alt["dr_ticker"]
                ticker_class[dr_ticker] = "dr"
                sector[dr_ticker] = "Global"
    return ticker_class, sector, friction
```

- [x] **Step 2: Wire up __init__.py**

```python
"""kth_dr — DR (Depositary Receipt) integration for Kronos-TH.

On import, registers all verified DR tickers with kth.data.universe
via the register_asset_class() plugin hook.
"""
import logging

try:
    from kth.data.universe import register_asset_class
    from kth_dr.universe_dr import build_registration_dicts

    ticker_class, sector, friction = build_registration_dicts()
    register_asset_class(ticker_class, sector=sector, friction=friction)
except Exception as e:
    # Registration is best-effort: a broken mapping.json must degrade to
    # "no DRs registered", never make `import kth_dr` fail — trade_gen and
    # the daily pipeline import this package behind optional-import guards.
    logging.warning(f"kth_dr: DR registration skipped: {e}")
```

- [x] **Step 3: Verify the registration works**

Run: `python -c "import kth_dr; from kth.data.universe import get_ticker_class, get_sector; print('kth_dr imported OK')"`
Expected: no errors (`DR_MAP` is empty locally — no `data/dr/mapping.json` yet — so nothing registers, but import succeeds)

- [x] **Step 4: Commit**

```bash
git add kth_dr/__init__.py kth_dr/universe_dr.py
git commit -m "feat(kth_dr): wire up __init__.py to register DRs with universe plugin hook"
```

---

### Task 4: Create seed list

**Files:**
- Create: `data/dr/seed_list.json`

**Ticker choice matters here — read before typing tickers in.** Per the design
spec's "Overlap With Existing Universe" section, a DR is only worth adding if
the underlying isn't already reachable directly. `universe.py`'s own docstring
says *any* US-listed stock is already directly buyable by a Thai investor
(fractional shares, since 2022) — not just the 17 tickers hardcoded under
`us_equity`. That means picking a US-listed ADR as the "underlying" (e.g.
Toyota's NYSE ticker `TM`, or ASML's Nasdaq ticker `ASML`) defeats the purpose
even though `is_already_in_universe()` won't catch it (it only checks the
hardcoded 100). **Use the home-market listing, not the US ADR:**

- [x] **Step 1: Create seed_list.json**

```bash
mkdir -p data/dr
```

```json
{
  "_note": "Hand-curated seed list of DRs. Format: underlying -> [DR candidates]. Add/edit entries manually, then run scripts/dr/discover_drs.py to generate mapping.json. Use home-market tickers for the underlying, not a US ADR that's already directly investable (see universe.py's us_equity notes) — that's why Toyota is 7203.T (Tokyo) and ASML is ASML.AS (Amsterdam), not their US-listed tickers.",
  "005930.KS": [
    {
      "dr_ticker": "SAMSUNG80.BK",
      "display_name": "Samsung Electronics",
      "underlying_exchange": "KR",
      "underlying_currency": "KRW",
      "ratio": 80
    }
  ],
  "0700.HK": [
    {
      "dr_ticker": "TENCENT80.BK",
      "display_name": "Tencent Holdings",
      "underlying_exchange": "HK",
      "underlying_currency": "HKD",
      "ratio": 80
    }
  ],
  "7203.T": [
    {
      "dr_ticker": "TOYOTA80.BK",
      "display_name": "Toyota Motor",
      "underlying_exchange": "JP",
      "underlying_currency": "JPY",
      "ratio": 80
    }
  ],
  "ASML.AS": [
    {
      "dr_ticker": "ASML80.BK",
      "display_name": "ASML Holding",
      "underlying_exchange": "NL",
      "underlying_currency": "EUR",
      "ratio": 80
    }
  ]
}
```

- [x] **Step 2: Verify JSON validity**

Run: `python -m json.tool data/dr/seed_list.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

- [x] **Step 3: Commit**

```bash
git add data/dr/
git commit -m "feat(dr): add initial seed list (Samsung, Tencent, Toyota, ASML — home listings)"
```

---

### Task 5: Create discovery script

**Files:**
- Create: `kth_dr/discover_drs.py`
- Create: `scripts/dr/discover_drs.py`
- Modify: `verify_dr.py`

**Scope note:** per the design spec, the seed list is the *primary* source of
candidates; the SET-wide scan is a secondary, lower-trust pass. This task
implements the seed-list path fully. The scan path (`scan_set_for_drs`,
`resolve_underlying`) is stubbed and **deliberately not wired into `main()`
yet** — it's a separate follow-up, not a shortcut you forgot to finish. Don't
mark this "done" and assume the scanner works; it doesn't, on purpose, for now.

- [x] **Step 1: Create kth_dr/discover_drs.py**

```python
"""DR discovery algorithm — seed list -> mapping.json.

Usage:
    python -m kth_dr.discover_drs

Process (seed-list path, implemented):
    1. Load seed list from data/dr/seed_list.json
    2. For each seed entry: check for overlap with the existing universe,
       download DR data, compute liquidity/history stats
    3. Rank alternatives, write mapping.json

NOT implemented yet (tracked as a follow-up, not a bug in this task):
    - Secondary SET-wide scan for DR naming patterns (scan_set_for_drs,
      resolve_underlying below are stubs — they exist to show the intended
      shape of that follow-up, but main() never calls them).
"""
import json
import time
from pathlib import Path

import yfinance as yf

from kth.data.universe import get_all_tickers

SEED_PATH = Path("data/dr/seed_list.json")
MAPPING_PATH = Path("data/dr/mapping.json")

# Naming patterns a future SET-wide scan would match against — unused today,
# kept here so the follow-up task starts from a documented starting point.
DR_NAMING_PATTERNS = [
    r"\d+\.BK$",       # e.g. AAPL80.BK
    r"NVDR.*\.BK$",    # e.g. AAPL-NVDR.BK
    r"DR.*\.BK$",      # e.g. AAPLDR.BK
]


def fx_ticker_for_currency(currency: str) -> str:
    """Yahoo FX symbol converting `currency` to THB. Yahoo quotes USD/THB as
    plain 'THB=X'; every other pair is '<CCY>THB=X' (e.g. 'KRWTHB=X').
    Hard-coding 'THB=X' for a KRW/HKD/JPY/EUR underlying would multiply the
    foreign close by the USD/THB rate and make premium_pct garbage."""
    if not currency or currency.upper() == "USD":
        return "THB=X"
    return f"{currency.upper()}THB=X"


def load_seed_list() -> dict:
    if not SEED_PATH.exists():
        return {}
    with open(SEED_PATH) as f:
        return json.load(f)


def load_existing_mapping() -> dict:
    if not MAPPING_PATH.exists():
        return {"_meta": {"generated": "", "dr_count": 0, "underlying_count": 0, "status": "needs_review"}}
    with open(MAPPING_PATH) as f:
        return json.load(f)


def compute_dr_stats(dr_ticker: str) -> dict:
    """Download DR history, return avg_volume_30d, history_rows, listing_date.

    period="max": history_rows feeds the MIN_DR_HISTORY gate — a capped window
    (e.g. "6mo" ≈ 125 rows) would silently disqualify every DR if the gate is
    ever raised past the cap. Volume still averages only the last 30 rows."""
    try:
        ticker = yf.Ticker(dr_ticker)
        hist = ticker.history(period="max")
        if hist.empty:
            return {"avg_volume_30d": 0, "history_rows": 0, "listing_date": None}
        recent = hist.tail(30)
        avg_vol = float(recent["Volume"].mean()) if not recent.empty else 0
        first_date = str(hist.index[0].date()) if not hist.empty else None
        return {
            "avg_volume_30d": round(avg_vol),
            "history_rows": len(hist),
            "listing_date": first_date,
        }
    except Exception:
        return {"avg_volume_30d": 0, "history_rows": 0, "listing_date": None}


def is_already_in_universe(ticker: str) -> bool:
    """Only catches exact matches against universe.py's hardcoded 100 tickers.
    Does NOT know that "any US-listed stock" is directly investable — that
    judgment call is why Task 4's seed list uses home-market tickers instead of
    US ADRs. Don't rely on this function alone when adding new seed entries."""
    all_tickers = get_all_tickers()
    return ticker in all_tickers


def resolve_underlying(dr_ticker: str) -> tuple[str | None, str | None, int | None]:
    """[Follow-up, not called by main()] Try to resolve a DR ticker to its
    underlying via yfinance Ticker.info. Field availability is inconsistent
    across tickers — this needs real-world tuning before it's trustworthy."""
    try:
        ticker = yf.Ticker(dr_ticker)
        info = ticker.info
        underlying = info.get("underlyingSymbol") or info.get("underlying") or info.get("symbol")
        name = info.get("underlyingName") or info.get("shortName") or ""
        if underlying:
            return underlying, name, 80
    except Exception:
        pass
    return None, None, None


def scan_set_for_drs(existing_drs: set[str]) -> list[dict]:
    """[Follow-up, not called by main()] Secondary scan: look for DR-named
    tickers on SET not already in the seed list. Not implemented — yfinance has
    no ticker-search API; this needs an external SET listing source."""
    return []


def rank_alternatives(alternatives: list[dict]) -> list[dict]:
    sorted_alts = sorted(alternatives, key=lambda a: a.get("avg_volume_30d", 0), reverse=True)
    for i, alt in enumerate(sorted_alts):
        alt["liquidity_rank"] = i + 1
    return sorted_alts


def main():
    seed = load_seed_list()
    existing = load_existing_mapping()

    # Track verified status across runs so re-running discovery never silently
    # un-verifies something the user already approved.
    previous_verified: dict[str, bool] = {}
    for underlying, entry in existing.items():
        if underlying.startswith("_"):
            continue
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                previous_verified[alt["dr_ticker"]] = True

    mapping = {}
    excluded = {}

    for underlying, candidates in seed.items():
        dr_ticker = candidates[0]["dr_ticker"]
        ratio = candidates[0].get("ratio", 80)
        display_name = candidates[0].get("display_name", underlying)
        exchange = candidates[0].get("underlying_exchange", "")
        currency = candidates[0].get("underlying_currency", "")

        if is_already_in_universe(underlying):
            excluded[underlying] = {
                "display_name": display_name,
                "excluded_reason": "already_direct",
                "note": f"{underlying} is already directly investable",
            }
            continue

        stats = compute_dr_stats(dr_ticker)
        was_verified = previous_verified.get(dr_ticker, False)

        alt = {
            "dr_ticker": dr_ticker,
            "ratio": ratio,
            "avg_volume_30d": stats["avg_volume_30d"],
            "listing_date": stats["listing_date"],
            "history_rows": stats["history_rows"],
            "verified": was_verified,
        }

        mapping[underlying] = {
            "display_name": display_name,
            "underlying_exchange": exchange,
            "underlying_currency": currency,
            "fx_ticker": fx_ticker_for_currency(currency),
            "primary_dr": dr_ticker,
            "alternatives": rank_alternatives([alt]),
        }

    output = {
        "_meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
            "dr_count": len(mapping),
            "underlying_count": len(mapping),
            "status": "needs_review",
        },
        **excluded,
        **mapping,
    }

    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {MAPPING_PATH} — {len(mapping)} underlyings, {len(excluded)} excluded")


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Create CLI entrypoint**

```python
#!/usr/bin/env python3
"""CLI entrypoint: discover DRs from seed list.

Usage:
    python scripts/dr/discover_drs.py
"""
import sys
sys.path.insert(0, ".")
from kth_dr.discover_drs import main

if __name__ == "__main__":
    main()
```

- [x] **Step 3: Append verify checks (no network — uses fakes/temp files)**

Append to `verify_dr.py`:

```python
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
```

- [x] **Step 4: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 20 PASSED` (12 so far + 8 here)

- [x] **Step 5: Commit**

```bash
git add kth_dr/discover_drs.py scripts/dr/ verify_dr.py
git commit -m "feat(dr): add discovery script — seed list processing + mapping generation"
```

---

### Task 6: Add DR hooks to trade_gen.py (the core translation layer)

**Files:**
- Create: `kth_dr/trade_gen_dr.py`
- Modify: `kth/trading/trade_gen.py`
- Modify: `verify_dr.py`

**Read this before editing anything.** `trade_gen.py`'s forecast rows need two
extra fields beyond what exists today:

- `execution_ticker` — the ticker to actually trade (the DR ticker, or the
  same as `ticker` if there's no DR). Everywhere the old code used `f["close"]`
  for **money** (share-lot sizing, `estimated_thb`, friction, limit price),
  it must use the **execution ticker's own cached close** instead — using the
  underlying's close there would size a THB budget against a foreign-currency
  price (e.g. Samsung's raw KRW close).
- Positions and held tickers are keyed by whatever ticker `execute_trade()`
  was called with — for a DR position that's the **DR ticker**, not the
  underlying. So the exits/reduces loop (which matches forecasts against
  `held_tickers`) must compare against `execution_ticker`, not `ticker`, or a
  held DR position will never match its own forecast and can never be exited.

Because so many lines inside `load_forecasts()` and `generate_trade_ticket()`
change together, **replace each function's full body** rather than patching
individual lines — line-number patches are fragile once earlier tasks have
already changed the file.

- [x] **Step 1: Create kth_dr/trade_gen_dr.py**

```python
"""DR-specific trade generation helpers — execution ticker/price/name
resolution, and the same-underlying guard used by trade_gen.py's buy loop."""
from kth_dr.universe_dr import get_dr_for_underlying, get_underlying_for_dr, get_dr_info_for_display


def resolve_execution_ticker(ticker: str) -> str:
    """Given an underlying ticker, return its DR ticker if a verified one
    exists. Identity for non-DR tickers."""
    dr = get_dr_for_underlying(ticker)
    if dr:
        return dr["dr_ticker"]
    return ticker


def resolve_execution_price(underlying_ticker: str, execution_ticker: str, underlying_close: float) -> float:
    """Return the price to actually trade at. For a DR position this MUST be
    the DR's own SET close (in THB) — never the underlying's raw
    foreign-currency close. `underlying_close` is returned unchanged when
    there's no DR (execution_ticker == underlying_ticker)."""
    if execution_ticker == underlying_ticker:
        return underlying_close
    from kth.data.loader import load_cached
    return float(load_cached(execution_ticker)["close"].iloc[-1])


def resolve_display_name(underlying_ticker: str, fallback: str) -> str:
    """Prefer the DR mapping's display_name (e.g. 'Samsung Electronics') over
    the raw underlying ticker string, which usually has no friendly name in
    universe.py's _DISPLAY_NAME_MAP."""
    dr = get_dr_for_underlying(underlying_ticker)
    if not dr:
        return fallback
    info = get_dr_info_for_display(dr["dr_ticker"])
    return info["display_name"] if info else fallback


def get_underlying_for_held(ticker: str) -> str:
    """If ticker is a DR, return its underlying. Identity for non-DR tickers.
    Used by the same-underlying guard in the buy loop."""
    underlying = get_underlying_for_dr(ticker)
    return underlying if underlying else ticker


def is_held_underlying(held_tickers: list[str], candidate_underlying: str) -> bool:
    """True if candidate_underlying is already held, whether directly or via
    a DR — prevents holding e.g. both AAPL and AAPL80.BK at once."""
    for held in held_tickers:
        if get_underlying_for_held(held) == candidate_underlying:
            return True
    return False
```

- [x] **Step 2: Replace `THAI_TICKERS`/`TRADABLE_TICKERS` setup (near the top of trade_gen.py)**

```python
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
```

- [x] **Step 3: Replace `load_forecasts()` in full**

```python
def load_forecasts(report_date: str = None) -> list[dict]:
    """Load today's forecast cache for every tradable ticker (thai_equity +
    underlyings with a verified DR). For a DR-mapped underlying, the row also
    carries execution_ticker/exec_close so trade-gen prices the trade in THB
    against the DR's own SET close, never the underlying's raw close."""
    if report_date is None:
        report_date = str(date.today())
    day_dir = CACHE_DIR / report_date
    if not day_dir.exists():
        return []

    from kth.data.loader import load_cached
    try:
        from kth_dr.trade_gen_dr import resolve_execution_ticker, resolve_execution_price, resolve_display_name
    except ImportError:
        resolve_execution_ticker = lambda t: t
        resolve_execution_price = lambda u, e, c: c
        resolve_display_name = lambda t, fallback: fallback

    rows = []
    for ticker in TRADABLE_TICKERS:
        parquet = day_dir / f"{_safe_ticker(ticker)}.parquet"
        if not parquet.exists():
            continue
        try:
            fc = pd.read_parquet(parquet)
            price_data = load_cached(ticker)
            current_close = float(price_data["close"].iloc[-1])

            p50 = float(fc["p50"].iloc[-1])
            p5 = float(fc["p5"].iloc[-1])
            p95 = float(fc["p95"].iloc[-1])
            mean_close = float(fc["mean"].iloc[-1]) if "mean" in fc.columns else p50

            # exp_ret/band_width are ratios — currency-agnostic, safe to compute
            # off the underlying's own close.
            exp_ret = (p50 - current_close) / current_close
            band_width = (p95 - p5) / current_close

            exec_ticker = resolve_execution_ticker(ticker)
            exec_close = resolve_execution_price(ticker, exec_ticker, current_close)

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

            rows.append({
                "ticker": ticker,
                "execution_ticker": exec_ticker,
                "exec_close": round(exec_close, 2),
                "name": resolve_display_name(ticker, get_display_name(ticker)),
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
```

- [x] **Step 4: Replace `generate_trade_ticket()` in full**

```python
def generate_trade_ticket(report_date: str = None, positions: dict = None) -> dict:
    """Generate today's trade ticket: exits, reduces, buys, cash flow.

    Every ticket item's "ticker" field is the EXECUTION ticker (what you'd
    actually place an order for) — the DR ticker for a DR-backed trade, the
    ticker itself otherwise. "underlying" carries the signal-source ticker
    for display/rationale only. This keeps friction/sector lookups correct
    for free, since get_friction()/get_sector() key off the execution ticker.
    """
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

    # Sector counts are seeded from held tickers, which are already execution
    # tickers (get_sector resolves DR tickers to "Global" via the plugin hook).
    sector_counts: dict[str, int] = {}
    for ticker in held_tickers:
        if ticker not in exited:
            sec = get_sector(ticker)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

    try:
        from kth_dr.trade_gen_dr import is_held_underlying
    except ImportError:
        is_held_underlying = None

    for rank_idx, f in enumerate(forecasts, 1):
        if len(buys) >= slots:
            break
        exec_ticker = f.get("execution_ticker", f["ticker"])
        if exec_ticker in held_tickers:
            continue
        if is_held_underlying and is_held_underlying(list(held_tickers.keys()), f["ticker"]):
            continue  # same underlying already held directly or via a different DR
        if f["net_ret"] <= f["friction_rt"]:
            continue
        if f["confidence"] == "red":
            continue
        if sector_counts.get(get_sector(exec_ticker), 0) >= MAX_SECTOR_POSITIONS:
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
```

Note: `friction_sells`/`friction_buys`/`_one_way_friction(...)` already key off
each ticket item's `"ticker"` field — which is now always the execution
ticker — so this part needs no change beyond what's shown above; it
automatically applies "dr" friction to DR trades.

- [x] **Step 5: Append verify checks for trade_gen_dr.py**

```python
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
```

- [x] **Step 6: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 26 PASSED` (20 so far + 6 here)

- [x] **Step 7: Commit**

```bash
git add kth_dr/trade_gen_dr.py kth/trading/trade_gen.py verify_dr.py
git commit -m "feat(dr): wire execution-ticker translation into trade_gen — fixes forecast-loop and pricing bugs from plan review"
```

---

### Task 7: Create DR data loader + wire it into the daily pipeline

**Files:**
- Create: `kth_dr/loader_dr.py`
- Modify: `kth/pipeline/daily.py`
- Modify: `verify_dr.py`

- [x] **Step 1: Create kth_dr/loader_dr.py**

`kth.data.loader.load_cached()` already raises `FileNotFoundError` itself on a
missing file — it never returns `None` — so `load_dr_bundle()` doesn't need
to check for `None` after calling it; let the exception propagate with
`load_cached`'s own message.

```python
"""DR data loader — bundles underlying, DR, and FX OHLCV data."""
from kth.data.loader import load_cached, download_universe
from kth_dr.universe_dr import get_dr_info_for_display


def load_dr_bundle(underlying_ticker: str) -> dict[str, object]:
    """Load underlying OHLCV, DR OHLCV, and FX rate for a DR position.

    Returns dict with keys: underlying_ohlcv, dr_ohlcv, fx_ohlcv, dr_info.
    Raises FileNotFoundError (via load_cached) if any series isn't cached yet.
    """
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        raise FileNotFoundError(f"No DR info found for {underlying_ticker}")

    return {
        "underlying_ohlcv": load_cached(underlying_ticker),
        "dr_ohlcv": load_cached(dr_info["dr_ticker"]),
        "fx_ohlcv": load_cached(dr_info["fx_ticker"]),
        "dr_info": dr_info,
    }


def ensure_dr_data(underlying_ticker: str) -> None:
    """Download all data sources required for a DR position. Idempotent —
    download_universe/load_cached already skip re-downloading cached tickers.
    Useful for ad-hoc/manual use (e.g. checking a candidate before it's
    verified). The daily pipeline itself does NOT call this — see Step 2:
    it folds DR tickers into the same ticker list everything else already
    goes through, so they ride the existing batched download/cache path
    instead of a second, parallel one."""
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        return
    tickers = [underlying_ticker, dr_info["dr_ticker"]]
    if dr_info.get("fx_ticker"):
        tickers.append(dr_info["fx_ticker"])
    download_universe(tickers)
```

- [x] **Step 2: Wire DR tickers into the daily pipeline's ticker list**

Without this step, DR/underlying/FX data is never downloaded during a real
pipeline run, and `build_pos_rows()` (Task 8) has nothing to compute
`premium_pct` from. In `kth/pipeline/daily.py`, in `run_daily_pipeline()`,
change:

```python
tickers = get_all_tickers_including_features()
ohlcv_dict = data_loader.ensure(tickers)
```

to:

```python
tickers = get_all_tickers_including_features()
try:
    from kth_dr.universe_dr import get_verified_dr_tickers, get_dr_underlying_tickers, DR_MAP, _ensure_loaded
    _ensure_loaded()
    dr_tickers = get_verified_dr_tickers()
    dr_underlyings = get_dr_underlying_tickers()
    dr_fx_tickers = list({DR_MAP[u].get("fx_ticker", "THB=X") for u in dr_underlyings if u in DR_MAP})
    tickers = tickers + dr_tickers + dr_underlyings + dr_fx_tickers
except ImportError:
    pass
except Exception as e:
    # kth_dr present but unusable — run the pipeline without DRs
    # rather than failing the whole daily run over an optional feature.
    print(f"WARN: DR ticker wiring skipped: {e}")
ohlcv_dict = data_loader.ensure(tickers)
```

This means Kronos's `model.forecast(tickers, today_str)` call right below
also runs on the DR tickers themselves (not just their underlyings) — a small,
deliberate inefficiency (a handful of unused forecast-cache files per DR)
rather than splitting the pipeline's single ticker list into two separate
flows for "needs a forecast" vs. "needs OHLCV only." Acceptable trade-off;
don't refactor this further without a specific reason to.

- [x] **Step 3: Append verify checks**

```python
# ---- Task 7: kth_dr/loader_dr.py ----

def test_load_dr_bundle_nonexistent_underlying():
    """Should raise FileNotFoundError for an underlying with no DR mapping."""
    from kth_dr.loader_dr import load_dr_bundle
    try:
        load_dr_bundle("TOTALLY.FAKE")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
    print("PASS test_load_dr_bundle_nonexistent_underlying")


def test_ensure_dr_data_nonexistent_does_not_raise():
    """Should not crash for unknown underlying — just a no-op."""
    from kth_dr.loader_dr import ensure_dr_data
    ensure_dr_data("TOTALLY.FAKE")
    print("PASS test_ensure_dr_data_nonexistent_does_not_raise")
```

- [x] **Step 4: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 28 PASSED` (26 so far + 2 here)

- [x] **Step 5: Commit**

```bash
git add kth_dr/loader_dr.py kth/pipeline/daily.py verify_dr.py
git commit -m "feat(dr): add DR data loader and wire DR tickers into the daily pipeline's download list"
```

---

### Task 8: Add DR columns to the Positions schema (with real data, not blanks)

**Files:**
- Modify: `kth/trading/sheets_config.py`
- Modify: `kth/trading/sheets.py`
- Modify: `verify_dr.py`

Adding the header columns alone isn't enough — `build_pos_rows()` builds each
data row independently of `POSITIONS_HEADERS` and must be taught to emit the
two new values, or they'll be permanently blank in the sheet even though the
header says otherwise.

- [x] **Step 1: Add DR columns to POSITIONS_HEADERS**

```python
POSITIONS_HEADERS = ['ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
                     'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss',
                     'underlying_ticker', 'premium_pct']
```

- [x] **Step 2: Update build_pos_rows() to populate them**

In `kth/trading/sheets.py`, replace `build_pos_rows()` in full:

```python
def build_pos_rows(positions: dict, ohlcv_dict: dict, get_sector_fn: Callable[[str], str]) -> list:
    try:
        from kth_dr.universe_dr import get_dr_info_for_display
    except ImportError:
        get_dr_info_for_display = lambda t: None

    rows = []
    for p in positions['positions']:
        ohlcv = ohlcv_dict or {}
        if p['ticker'] in ohlcv:
            close = float(ohlcv[p['ticker']]['close'].iloc[-1])
        else:
            close = p['avg_cost']
        pnl = (close - p['avg_cost']) * p['shares']
        pnl_pct = (close / p['avg_cost'] - 1) if p['avg_cost'] else 0

        underlying_ticker = ''
        premium_pct = ''
        dr_info = get_dr_info_for_display(p['ticker'])
        if dr_info:
            underlying_ticker = dr_info['underlying_ticker']
            try:
                u_close = float(ohlcv[dr_info['underlying_ticker']]['close'].iloc[-1])
                fx_close = float(ohlcv[dr_info['fx_ticker']]['close'].iloc[-1])
                dr_intrinsic = (u_close * fx_close) / dr_info['ratio']
                premium_pct = round((close / dr_intrinsic) - 1, 4) if dr_intrinsic else ''
            except (KeyError, ZeroDivisionError):
                premium_pct = ''  # underlying/FX not in ohlcv_dict this run — leave blank, don't crash

        rows.append([
            p['ticker'], p['shares'], p['avg_cost'], p.get('entry_date', ''),
            get_sector_fn(p['ticker']), round(close, 2),
            round(pnl, 2), round(pnl_pct, 4), round(pnl_pct + 0.10, 4),
            underlying_ticker, premium_pct,
        ])
    return rows
```

- [x] **Step 3: Append verify checks**

```python
# ---- Task 8: sheets_config.py / sheets.py — Positions schema ----

def test_positions_headers_has_11_columns():
    from kth.trading.sheets_config import POSITIONS_HEADERS
    assert len(POSITIONS_HEADERS) == 11, POSITIONS_HEADERS
    assert POSITIONS_HEADERS[-2:] == ['underlying_ticker', 'premium_pct']
    print("PASS test_positions_headers_has_11_columns")


def test_build_pos_rows_row_length_matches_headers():
    """Regression guard: every row build_pos_rows emits must have exactly as
    many values as POSITIONS_HEADERS has columns."""
    import pandas as pd
    from kth.trading.sheets import build_pos_rows
    from kth.trading.sheets_config import POSITIONS_HEADERS
    from kth.data.universe import get_sector
    positions = {"positions": [{"ticker": "PTT.BK", "shares": 100, "avg_cost": 30.0, "entry_date": "2026-01-01"}]}
    ohlcv = {"PTT.BK": pd.DataFrame({"close": [31.0]})}
    rows = build_pos_rows(positions, ohlcv, get_sector)
    assert len(rows[0]) == len(POSITIONS_HEADERS)
    print("PASS test_build_pos_rows_row_length_matches_headers")


def test_build_pos_rows_blank_for_non_dr_position():
    import pandas as pd
    from kth.trading.sheets import build_pos_rows
    from kth.data.universe import get_sector
    positions = {"positions": [{"ticker": "PTT.BK", "shares": 100, "avg_cost": 30.0, "entry_date": "2026-01-01"}]}
    ohlcv = {"PTT.BK": pd.DataFrame({"close": [31.0]})}
    rows = build_pos_rows(positions, ohlcv, get_sector)
    assert rows[0][-2] == '', "non-DR position must have blank underlying_ticker"
    assert rows[0][-1] == '', "non-DR position must have blank premium_pct"
    print("PASS test_build_pos_rows_blank_for_non_dr_position")
```

- [x] **Step 4: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 31 PASSED` (28 so far + 3 here)

- [x] **Step 5: Commit**

```bash
git add kth/trading/sheets_config.py kth/trading/sheets.py verify_dr.py
git commit -m "feat(dr): add underlying_ticker/premium_pct to Positions schema, wire real values into build_pos_rows"
```

---

### Task 9: Full verify_dr.py run + manual smoke test

**Files:**
- Modify: `verify_dr.py`

- [x] **Step 1: Append final integration checks**

```python
# ---- Task 9: end-to-end wiring checks ----

def test_kth_dr_imports_cleanly():
    """kth_dr package must import without errors even with no mapping file."""
    import kth_dr
    assert kth_dr.__name__ == "kth_dr"
    print("PASS test_kth_dr_imports_cleanly")


def test_universe_plugin_hook_works_with_dr():
    from kth.data.universe import register_asset_class, get_ticker_class, get_sector, get_friction, _extra_ticker_class, _extra_sector, _extra_friction
    register_asset_class({"INTEGRATION.TEST": "dr"}, sector={"INTEGRATION.TEST": "Global"}, friction={"dr": {"commission_oneway": 0.001, "slippage_oneway": 0.001}})
    assert get_ticker_class("INTEGRATION.TEST") == "dr"
    assert get_sector("INTEGRATION.TEST") == "Global"
    assert get_friction("INTEGRATION.TEST")["commission_oneway"] == 0.001
    _extra_ticker_class.pop("INTEGRATION.TEST", None)
    _extra_sector.pop("INTEGRATION.TEST", None)
    _extra_friction.pop("dr", None)
    print("PASS test_universe_plugin_hook_works_with_dr")


def test_trade_gen_imports_and_functions_without_dr():
    """trade_gen must import and function even if kth_dr is absent/broken."""
    from kth.trading import trade_gen
    assert hasattr(trade_gen, "THAI_TICKERS")
    assert hasattr(trade_gen, "TRADABLE_TICKERS")
    assert len(trade_gen.THAI_TICKERS) > 0
    print("PASS test_trade_gen_imports_and_functions_without_dr")
```

- [x] **Step 2: Run the whole thing**

Run: `python verify_dr.py`
Expected: `ALL 34 PASSED`

- [x] **Step 3: Manual smoke test (no network required)**

1. Confirm `data/dr/mapping.json` does not need to exist for anything in this
   plan to import cleanly: `rm -f data/dr/mapping.json && python -c "import kth_dr"` should succeed silently.
2. Hand-write a minimal `data/dr/mapping.json` (copy the `_TEST_MAPPING` dict
   from `verify_dr.py`), then run `python -c "from kth.trading.trade_gen import TRADABLE_TICKERS; print(TRADABLE_TICKERS)"` and confirm `"005930.KS"` appears in the list — **not** `"SAMSUNG80.BK"`.
3. Delete the hand-written `data/dr/mapping.json` when done — it's scratch,
   not meant to be committed.

- [x] **Step 4: Commit**

```bash
git add verify_dr.py
git commit -m "test(dr): add end-to-end wiring checks for DR module, universe hook, and trade_gen compatibility"
```

---

### Task 10: Documentation — update AGENTS.md, CLAUDE.md, and PROJECT_STRUCTURE.md

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `PROJECT_STRUCTURE.md`

- [x] **Step 1: Add kth_dr/ entry to PROJECT_STRUCTURE.md**

```
### `kth_dr/` — DR (Depositary Receipt) integration
- `universe_dr.py` — DR_MAP loading, get_dr_for_underlying(), get_dr_underlying_tickers(), get_verified_dr_tickers()
- `loader_dr.py` — load_dr_bundle() for 3-series OHLCV bundle
- `discover_drs.py` — seed list -> mapping.json (SET-wide scan is a stubbed follow-up, not implemented)
- `trade_gen_dr.py` — execution ticker/price/name resolution, same-underlying guard
```

- [x] **Step 2: Add the verify_dr.py command to CLAUDE.md's Commands section**

Next to the existing `verify_*.py` entries:

```
python verify_dr.py                     # DR integration: plugin hook, mapping, trade-gen wiring (34 tests; Task 11 raises this to 39)
```

- [x] **Step 3: Update AGENTS.md with DR workflow**

```
- DR (Depositary Receipt) integration: live. See docs/superpowers/specs/2026-07-12-global-dr-integration-design.md.
```

- [x] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md PROJECT_STRUCTURE.md
git commit -m "docs: add kth_dr/ to project docs, CLAUDE.md commands, and AGENTS.md"
```

---

### Task 11: Code-review hardening — FX correctness + broken-mapping resilience (2026-07-14)

**Files:**
- Modify: `kth_dr/discover_drs.py`
- Modify: `kth_dr/universe_dr.py`
- Modify: `kth_dr/__init__.py`
- Modify: `kth/trading/trade_gen.py`
- Modify: `kth/pipeline/daily.py`
- Modify: `verify_dr.py`
- Create: `data/dr/README.md`
- Modify: `CLAUDE.md`

Post-implementation review (2026-07-14) of Tasks 1–10 found four defects. The
corrected code is **already folded into the earlier tasks' code blocks above**
— if you implemented Tasks 1–10 from this document as written, items 1–4 below
are already in place and this task is only the verify checks + docs. If you are
patching a checkout built from the *original* plan, apply all four:

1. **FX-pair bug (correctness).** `discover_drs.py` hard-coded
   `"fx_ticker": "THB=X"` (the **USD**/THB rate) for every underlying, but the
   seed entries are priced in KRW/HKD/JPY/EUR — `premium_pct` was garbage for
   all of them (e.g. Samsung: KRW close × USD rate ≈ −99.97% "premium").
   Fixed by `fx_ticker_for_currency()` (see Task 5's code block) and
   `_TEST_MAPPING`'s `"fx_ticker": "KRWTHB=X"`.
2. **`_unresolved` crash (latent, import-time).** `_unresolved` in mapping.json
   is a *list*; `build_registration_dicts()` called `.get()` on it →
   `AttributeError` at `import kth_dr` time, which `except ImportError` does
   not catch. Fixed by the `isinstance(entry, dict)` guards in Task 2/3's
   blocks.
3. **Broken ≠ absent (resilience).** mapping.json is hand-edited (a human
   flips `verified`), so a JSON typo must degrade to "no DRs", not kill
   `import kth.trading.trade_gen` and with it the whole daily pipeline.
   Fixed in three layers: `_load_dr_mapping()` catches decode errors (Task 2),
   `kth_dr/__init__.py` wraps registration in try/except (Task 3), and
   trade_gen/daily each add an `except Exception` arm beside their
   `except ImportError` (Tasks 6/7).
4. **`history_rows` cap (latent).** `compute_dr_stats` used `period="6mo"`
   (≈125 rows max), so raising `MIN_DR_HISTORY` past ~125 would silently
   disqualify every DR. Fixed with `period="max"` (Task 5's block).

- [x] **Step 1: Apply fixes 1–4** (no-op if you implemented Tasks 1–10 from
  this document — the blocks above are the corrected versions)

- [x] **Step 2: Append verify checks**

Append to `verify_dr.py` (before the `if __name__ ==` block) — also update
`_TEST_MAPPING`'s fx_ticker to `"KRWTHB=X"` and add the fx_ticker assertion to
`test_get_dr_info_for_display` as shown in Task 2's verify block:

```python
# ---- Task 11: code-review hardening (2026-07-14) — FX correctness + broken-mapping resilience ----

def test_fx_ticker_for_currency():
    """Bug-fix regression guard: fx_ticker must match the underlying's own
    currency. Hard-coded 'THB=X' (USD/THB) made premium_pct garbage for every
    non-USD underlying — all four seed entries."""
    from kth_dr.discover_drs import fx_ticker_for_currency
    assert fx_ticker_for_currency("USD") == "THB=X"
    assert fx_ticker_for_currency("KRW") == "KRWTHB=X"
    assert fx_ticker_for_currency("HKD") == "HKDTHB=X"
    assert fx_ticker_for_currency("JPY") == "JPYTHB=X"
    assert fx_ticker_for_currency("EUR") == "EURTHB=X"
    assert fx_ticker_for_currency("") == "THB=X"
    print("PASS test_fx_ticker_for_currency")


def test_build_registration_dicts_skips_non_dict_entries(tmp):
    """Bug-fix regression guard: _unresolved (a list) crashed
    build_registration_dicts with AttributeError at `import kth_dr` time."""
    from kth_dr.universe_dr import build_registration_dicts
    def check():
        ticker_class, sector, friction = build_registration_dicts()
        assert ticker_class == {"SAMSUNG80.BK": "dr"}, ticker_class
        assert sector == {"SAMSUNG80.BK": "Global"}
        assert "dr" in friction
    _with_test_mapping(tmp, check)
    print("PASS test_build_registration_dicts_skips_non_dict_entries")


def test_load_dr_mapping_malformed_returns_empty(tmp):
    """A hand-edit typo in mapping.json must degrade to 'no DRs', not raise."""
    from pathlib import Path
    from kth_dr import universe_dr as ud
    bad_path = Path(tmp) / "mapping.json"
    bad_path.write_text("{ this is not json")
    orig_path = ud.DR_MAP_PATH
    ud.DR_MAP_PATH = bad_path
    ud.DR_MAP.clear()
    try:
        assert ud._load_dr_mapping() == {}
        assert ud.get_dr_for_underlying("005930.KS") is None
        assert ud.get_dr_underlying_tickers() == []
    finally:
        ud.DR_MAP_PATH = orig_path
        ud.DR_MAP.clear()
    print("PASS test_load_dr_mapping_malformed_returns_empty")


def test_trade_gen_import_survives_malformed_mapping(tmp):
    """End-to-end guard for the optional-import seams: with a corrupt
    data/dr/mapping.json in cwd, `import kth.trading.trade_gen` must still
    succeed and keep the full thai_equity list tradable."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    dr_dir = Path(tmp) / "data" / "dr"
    dr_dir.mkdir(parents=True)
    (dr_dir / "mapping.json").write_text("{ this is not json")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c",
         "from kth.trading.trade_gen import TRADABLE_TICKERS, THAI_TICKERS; "
         "assert set(THAI_TICKERS).issubset(set(TRADABLE_TICKERS)); print('OK')"],
        cwd=tmp, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
    print("PASS test_trade_gen_import_survives_malformed_mapping")


def test_build_pos_rows_dr_premium_uses_fx(tmp):
    """premium_pct = dr_close / (underlying_close × fx / ratio) − 1, using the
    mapping's own FX pair. 32000 KRW × 0.025 THB/KRW ÷ 80 = 10.00 THB intrinsic;
    DR at 10.50 THB → +5% premium."""
    import pandas as pd
    from kth.trading.sheets import build_pos_rows
    from kth.data.universe import get_sector
    def check():
        positions = {"positions": [{"ticker": "SAMSUNG80.BK", "shares": 100, "avg_cost": 10.0, "entry_date": "2026-01-01"}]}
        ohlcv = {
            "SAMSUNG80.BK": pd.DataFrame({"close": [10.5]}),
            "005930.KS": pd.DataFrame({"close": [32000.0]}),
            "KRWTHB=X": pd.DataFrame({"close": [0.025]}),
        }
        rows = build_pos_rows(positions, ohlcv, get_sector)
        assert rows[0][-2] == "005930.KS", rows[0]
        assert rows[0][-1] == 0.05, rows[0]
    _with_test_mapping(tmp, check)
    print("PASS test_build_pos_rows_dr_premium_uses_fx")
```

- [x] **Step 3: Create `data/dr/README.md`** documenting the seed → discover →
  verify workflow — in particular **who flips `verified: true` and on what
  criteria** (SET factsheet cross-check, ratio match, liquidity rule of thumb,
  `MIN_DR_HISTORY`). Nothing trades until that manual step; the README is the
  only place that says so explicitly.

- [x] **Step 4: Update `CLAUDE.md`'s verify_dr.py entry to 39 tests**

- [x] **Step 5: Run and verify**

Run: `python verify_dr.py`
Expected: `ALL 39 PASSED` (34 so far + 5 here)

Also re-run `python verify_fixes.py` and `python verify_kaggle_runtime.py` —
this task touches `trade_gen.py` and `daily.py`, which those suites cover.

- [x] **Step 6: Commit**

```bash
git add kth_dr/ kth/trading/trade_gen.py kth/pipeline/daily.py verify_dr.py data/dr/README.md CLAUDE.md
git commit -m "fix(dr): per-currency FX pairs, broken-mapping resilience, _unresolved guard (code review 2026-07-14)"
```
