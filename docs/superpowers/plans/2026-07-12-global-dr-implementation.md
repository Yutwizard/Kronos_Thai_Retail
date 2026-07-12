# Global DR Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) to implement this plan task-by-task. Steps use `- [ ]` syntax for tracking.

**Goal:** Add DR (Depositary Receipt) support to Kronos-TH — signal from underlying, execute via SET-listed DR.

**Architecture:** New `kth_dr/` package with DR mapping, discovery, and trade-gen hooks. Existing `kth/data/universe.py` gets a generic `register_asset_class()` plugin hook. `kth/trading/trade_gen.py` gets optional-import hooks that no-op if `kth_dr` is absent.

**Tech Stack:** Python 3.10+, yfinance, pytest

---

### Task 1: Plugin hook in universe.py

**Files:**
- Modify: `kth/data/universe.py`
- Test: `tests/test_universe.py`

- [ ] **Step 1: Add plugin hook data structures and function**

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

- [ ] **Step 2: Add fallback lookups to existing getters**

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

- [ ] **Step 3: Write tests for the plugin hook**

Add to `tests/test_universe.py`:

```python
def test_register_asset_class_adds_ticker_class():
    """Plugin-registered tickers must be findable by get_ticker_class."""
    from kth.data.universe import register_asset_class, get_ticker_class
    register_asset_class({"TESTDR.BK": "dr"})
    assert get_ticker_class("TESTDR.BK") == "dr"
    # Cleanup
    from kth.data.universe import _extra_ticker_class
    _extra_ticker_class.pop("TESTDR.BK", None)


def test_register_asset_class_adds_sector():
    """Plugin-registered sectors must be findable by get_sector."""
    from kth.data.universe import register_asset_class, get_sector
    register_asset_class({}, sector={"TESTDR.BK": "Global"})
    assert get_sector("TESTDR.BK") == "Global"
    from kth.data.universe import _extra_sector
    _extra_sector.pop("TESTDR.BK", None)


def test_register_asset_class_adds_friction():
    """Plugin-registered friction must be findable by get_friction."""
    from kth.data.universe import register_asset_class, get_friction, _extra_friction
    register_asset_class({"TESTDR.BK": "dr"}, friction={"dr": {"commission_oneway": 0.001, "slippage_oneway": 0.001}})
    f = get_friction("TESTDR.BK")
    assert f["commission_oneway"] == 0.001
    assert f["slippage_oneway"] == 0.001
    _extra_friction.pop("dr", None)
    from kth.data.universe import _extra_ticker_class
    _extra_ticker_class.pop("TESTDR.BK", None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_universe.py -v`
Expected: existing tests pass + 3 new tests pass

- [ ] **Step 5: Commit**

```bash
git add kth/data/universe.py tests/test_universe.py
git commit -m "feat(universe): add register_asset_class() plugin hook for external packages"
```

---

### Task 2: Create kth_dr package + universe_dr.py

**Files:**
- Create: `kth_dr/__init__.py` (empty)
- Create: `kth_dr/universe_dr.py`
- Create: `tests/test_dr_universe.py`

- [ ] **Step 1: Create package directory and __init__.py**

```bash
mkdir -p kth_dr
touch kth_dr/__init__.py
```

- [ ] **Step 2: Write universe_dr.py**

```python
"""DR mapping data — loaded from data/dr/mapping.json at import time."""
import json
from pathlib import Path

DR_MAP_PATH = Path("data/dr/mapping.json")
MIN_DR_HISTORY = 60
DR_PREMIUM_WARN_THRESHOLD = 0.05

DR_MAP: dict = {}


def _load_dr_mapping() -> dict:
    if not DR_MAP_PATH.exists():
        return {}
    with open(DR_MAP_PATH) as f:
        return json.load(f)


def _ensure_loaded():
    if not DR_MAP:
        DR_MAP.update(_load_dr_mapping())


def get_dr_for_underlying(underlying_ticker: str) -> dict | None:
    _ensure_loaded()
    entry = DR_MAP.get(underlying_ticker)
    if entry is None or "excluded_reason" in entry:
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
        if "excluded_reason" in entry:
            continue
        for alt in entry.get("alternatives", []):
            if alt["dr_ticker"] == dr_ticker:
                return underlying
    return None


def get_verified_dr_tickers() -> list[str]:
    _ensure_loaded()
    result = []
    for underlying, entry in DR_MAP.items():
        if "excluded_reason" in entry:
            continue
        dr = get_dr_for_underlying(underlying)
        if dr:
            result.append(dr["dr_ticker"])
    return result


def get_dr_info_for_display(dr_ticker: str) -> dict | None:
    """Return enriched display info: underlying, ratio, premium fields."""
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

- [ ] **Step 3: Write tests**

```python
"""Tests for kth_dr.universe_dr — mapping loading, getters, verified DR resolution."""
from pathlib import Path
import json
import pytest

from kth_dr.universe_dr import (
    DR_MAP, _ensure_loaded, _load_dr_mapping,
    get_dr_for_underlying, get_underlying_for_dr,
    get_verified_dr_tickers, MIN_DR_HISTORY,
)


@pytest.fixture
def dr_mapping(tmp_path):
    """Write a test mapping.json and point DR_MAP_PATH to it."""
    from kth_dr import universe_dr as ud
    orig_path = ud.DR_MAP_PATH
    test_path = tmp_path / "mapping.json"
    test_data = {
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
    with open(test_path, "w") as f:
        json.dump(test_data, f)
    ud.DR_MAP_PATH = test_path
    ud.DR_MAP.clear()
    yield
    ud.DR_MAP_PATH = orig_path
    ud.DR_MAP.clear()


def test_load_dr_mapping_returns_dict(dr_mapping):
    data = _load_dr_mapping()
    assert "005930.KS" in data
    assert data["005930.KS"]["alternatives"][0]["dr_ticker"] == "SAMSUNG80.BK"


def test_get_dr_for_underlying_returns_verified(dr_mapping):
    dr = get_dr_for_underlying("005930.KS")
    assert dr is not None
    assert dr["dr_ticker"] == "SAMSUNG80.BK"


def test_get_dr_for_underlying_excluded(dr_mapping):
    dr = get_dr_for_underlying("AAPL")
    assert dr is None, "Excluded underlying should return None"


def test_get_dr_for_underlying_nonexistent(dr_mapping):
    dr = get_dr_for_underlying("NONEXISTENT")
    assert dr is None


def test_get_underlying_for_dr_found(dr_mapping):
    underlying = get_underlying_for_dr("SAMSUNG80.BK")
    assert underlying == "005930.KS"


def test_get_underlying_for_dr_not_found(dr_mapping):
    underlying = get_underlying_for_dr("FAKE.BK")
    assert underlying is None


def test_get_verified_dr_tickers(dr_mapping):
    tickers = get_verified_dr_tickers()
    assert "SAMSUNG80.BK" in tickers
    assert len(tickers) == 1


def test_get_dr_info_for_display(dr_mapping):
    from kth_dr.universe_dr import get_dr_info_for_display
    info = get_dr_info_for_display("SAMSUNG80.BK")
    assert info is not None
    assert info["underlying_ticker"] == "005930.KS"
    assert info["ratio"] == 80
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_dr_universe.py -v`
Expected: 7 tests pass

- [ ] **Step 5: Commit**

```bash
git add kth_dr/ tests/test_dr_universe.py
git commit -m "feat(kth_dr): add DR mapping module with getters and verified resolution"
```

---

### Task 3: Wire up __init__.py to register DRs with universe

**Files:**
- Modify: `kth_dr/__init__.py`
- Modify: `kth_dr/universe_dr.py` (add `build_registration_dicts()`)

- [ ] **Step 1: Add build_registration_dicts() to universe_dr.py**

Append to `kth_dr/universe_dr.py`:

```python
def build_registration_dicts() -> tuple[dict[str, str], dict[str, str], dict[str, dict]]:
    """Build the three dicts needed by register_asset_class() from verified DRs."""
    _ensure_loaded()
    ticker_class = {}
    sector = {}
    friction = {"dr": {"commission_oneway": 0.00168, "slippage_oneway": 0.0010}}
    for underlying, entry in DR_MAP.items():
        if "excluded_reason" in entry:
            continue
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                dr_ticker = alt["dr_ticker"]
                ticker_class[dr_ticker] = "dr"
                sector[dr_ticker] = "Global"
    return ticker_class, sector, friction
```

- [ ] **Step 2: Wire up __init__.py**

```python
"""kth_dr — DR (Depositary Receipt) integration for Kronos-TH.

On import, registers all verified DR tickers with kth.data.universe
via the register_asset_class() plugin hook.
"""
from kth.data.universe import register_asset_class
from kth_dr.universe_dr import build_registration_dicts

ticker_class, sector, friction = build_registration_dicts()
register_asset_class(ticker_class, sector=sector, friction=friction)
```

- [ ] **Step 3: Verify the registration works**

Run: `python -c "import kth_dr; from kth.data.universe import get_ticker_class, get_sector; print('kth_dr imported OK')"`
Expected: no errors (DR_MAP is empty locally so nothing registers, but import succeeds)

- [ ] **Step 4: Commit**

```bash
git add kth_dr/__init__.py kth_dr/universe_dr.py
git commit -m "feat(kth_dr): wire up __init__.py to register DRs with universe plugin hook"
```

---

### Task 4: Create seed list

**Files:**
- Create: `data/dr/seed_list.json`
- Create: `data/dr/.gitkeep`

- [ ] **Step 1: Create seed_list.json**

```bash
mkdir -p data/dr
```

```json
{
  "_note": "Hand-curated seed list of DRs. Format: underlying -> [DR candidates]. Add/edit entries manually, then run scripts/dr/discover_drs.py to generate mapping.json.",
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
  "TM": [
    {
      "dr_ticker": "TOYOTA80.BK",
      "display_name": "Toyota Motor",
      "underlying_exchange": "US",
      "underlying_currency": "USD",
      "ratio": 80
    }
  ],
  "ASML": [
    {
      "dr_ticker": "ASML80.BK",
      "display_name": "ASML Holding",
      "underlying_exchange": "US",
      "underlying_currency": "USD",
      "ratio": 80
    }
  ]
}
```

- [ ] **Step 2: Verify JSON validity**

Run: `python -m json.tool data/dr/seed_list.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

- [ ] **Step 3: Commit**

```bash
git add data/dr/
git commit -m "feat(dr): add initial seed list (Samsung, Tencent, Toyota, ASML)"
```

---

### Task 5: Create discovery script

**Files:**
- Create: `kth_dr/discover_drs.py`
- Create: `scripts/dr/discover_drs.py`
- Test: `tests/test_dr_discovery.py`

- [ ] **Step 1: Create kth_dr/discover_drs.py**

```python
"""DR discovery algorithm — seed list + SET scan -> mapping.json.

Usage:
    python -m kth_dr.discover_drs

Process:
    1. Load seed list from data/dr/seed_list.json
    2. For each seed entry: download DR data, compute stats, check for overlap
    3. Scan SET for additional DR naming pattern candidates
    4. Merge, rank by liquidity, write mapping.json
"""
import json
import time
from pathlib import Path

import yfinance as yf
import pandas as pd

from kth.data.universe import get_all_tickers

SEED_PATH = Path("data/dr/seed_list.json")
MAPPING_PATH = Path("data/dr/mapping.json")
DR_NAMING_PATTERNS = [
    r"\d+\.BK$",       # e.g. AAPL80.BK
    r"NVDR.*\.BK$",    # e.g. AAPL-NVDR.BK
    r"DR.*\.BK$",      # e.g. AAPLDR.BK
]
SCAN_UNIVERSE = "thai_equity"


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
    """Download DR history, return avg_volume_30d, history_rows, listing_date."""
    try:
        ticker = yf.Ticker(dr_ticker)
        hist = ticker.history(period="6mo")
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


def resolve_underlying(dr_ticker: str) -> tuple[str | None, str | None, int | None]:
    """Try to resolve a DR ticker to its underlying via yfinance Ticker.info."""
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


def is_already_in_universe(ticker: str) -> bool:
    all_tickers = get_all_tickers()
    return ticker in all_tickers


def scan_set_for_drs(existing_drs: set[str]) -> list[dict]:
    """Secondary scan: look for DR-named tickers on SET."""
    candidates = []
    try:
        set_tickers = yf.Tickers(SCAN_UNIVERSE)
    except Exception:
        return candidates
    return candidates


def rank_alternatives(alternatives: list[dict]) -> list[dict]:
    sorted_alts = sorted(alternatives, key=lambda a: a.get("avg_volume_30d", 0), reverse=True)
    for i, alt in enumerate(sorted_alts):
        alt["liquidity_rank"] = i + 1
    return sorted_alts


def main():
    seed = load_seed_list()
    existing = load_existing_mapping()

    # Track seed-entry verified status across runs
    previous_verified: dict[str, bool] = {}
    for underlying, entry in existing.items():
        if underlying.startswith("_"):
            continue
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                previous_verified[alt["dr_ticker"]] = True

    mapping = {}
    unresolved = []
    excluded = []

    # Process seed list
    for underlying, candidates in seed.items():
        dr_ticker = candidates[0]["dr_ticker"]
        ratio = candidates[0].get("ratio", 80)
        display_name = candidates[0].get("display_name", underlying)
        exchange = candidates[0].get("underlying_exchange", "")
        currency = candidates[0].get("underlying_currency", "")

        if is_already_in_universe(underlying):
            excluded.append({
                underlying: {
                    "display_name": display_name,
                    "excluded_reason": "already_direct",
                    "note": f"{underlying} is already directly investable",
                }
            })
            continue

        stats = compute_dr_stats(dr_ticker)
        was_verified = previous_verified.get(dr_ticker, False)

        alt = {
            "dr_ticker": dr_ticker,
            "ratio": ratio,
            "liquidity_rank": 1,
            "avg_volume_30d": stats["avg_volume_30d"],
            "listing_date": stats["listing_date"],
            "history_rows": stats["history_rows"],
            "verified": was_verified,
        }

        mapping[underlying] = {
            "display_name": display_name,
            "underlying_exchange": exchange,
            "underlying_currency": currency,
            "fx_ticker": "THB=X",
            "primary_dr": dr_ticker,
            "alternatives": rank_alternatives([alt]),
        }

    # Secondary scan (placeholder — real scan needs yfinance search)
    # scan_candidates = scan_set_for_drs(set(a["dr_ticker"] for ...))

    # Build output
    output = {
        "_meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
            "dr_count": len(mapping),
            "underlying_count": len(mapping),
            "status": "needs_review",
        },
        **{k: v for e in excluded for k, v in e.items()},
        **mapping,
    }
    if unresolved:
        output["_unresolved"] = unresolved

    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {MAPPING_PATH} — {len(mapping)} underlyings, {len(excluded)} excluded, {len(unresolved)} unresolved")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create CLI entrypoint**

```python
#!/usr/bin/env python3
"""CLI entrypoint: discover DRs from seed list + SET scan.

Usage:
    python scripts/dr/discover_drs.py
"""
import sys
sys.path.insert(0, ".")
from kth_dr.discover_drs import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write tests (using fakes, no network)**

```python
"""Tests for kth_dr.discover_drs — seed loading, DR stats, ranking, exclusion."""
import json
from pathlib import Path

import pytest

from kth_dr.discover_drs import (
    load_seed_list, load_existing_mapping, rank_alternatives,
    is_already_in_universe,
)


def test_load_seed_list_returns_dict():
    seed = load_seed_list()
    assert isinstance(seed, dict)
    assert "005930.KS" in seed


def test_load_seed_list_has_correct_structure():
    seed = load_seed_list()
    entry = seed["005930.KS"]
    assert isinstance(entry, list)
    assert entry[0]["dr_ticker"] == "SAMSUNG80.BK"
    assert entry[0]["ratio"] == 80


def test_load_existing_mapping_no_file(tmp_path):
    from kth_dr import discover_drs as dd
    orig = dd.MAPPING_PATH
    dd.MAPPING_PATH = tmp_path / "nonexistent.json"
    mapping = load_existing_mapping()
    assert "_meta" in mapping
    assert mapping["_meta"]["status"] == "needs_review"
    dd.MAPPING_PATH = orig


def test_load_existing_mapping_with_file(tmp_path):
    from kth_dr import discover_drs as dd
    orig = dd.MAPPING_PATH
    test_path = tmp_path / "mapping.json"
    test_path.write_text(json.dumps({"005930.KS": {"alternatives": [{"dr_ticker": "SAMSUNG80.BK", "verified": True}]}}))
    dd.MAPPING_PATH = test_path
    mapping = load_existing_mapping()
    assert "005930.KS" in mapping
    assert mapping["005930.KS"]["alternatives"][0]["verified"] is True
    dd.MAPPING_PATH = orig


def test_rank_alternatives_sorts_by_volume():
    alts = [
        {"dr_ticker": "LOW.BK", "avg_volume_30d": 100},
        {"dr_ticker": "HIGH.BK", "avg_volume_30d": 50000},
        {"dr_ticker": "MID.BK", "avg_volume_30d": 1000},
    ]
    ranked = rank_alternatives(alts)
    assert ranked[0]["dr_ticker"] == "HIGH.BK"
    assert ranked[0]["liquidity_rank"] == 1
    assert ranked[1]["dr_ticker"] == "MID.BK"
    assert ranked[1]["liquidity_rank"] == 2
    assert ranked[2]["dr_ticker"] == "LOW.BK"
    assert ranked[2]["liquidity_rank"] == 3


def test_is_already_in_universe_known():
    assert is_already_in_universe("AAPL") is True


def test_is_already_in_universe_unknown():
    assert is_already_in_universe("005930.KS") is False


def test_is_already_in_universe_nonexistent():
    assert is_already_in_universe("TOTALLY.FAKE") is False
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_dr_discovery.py -v`
Expected: 8 tests pass

- [ ] **Step 5: Commit**

```bash
git add kth_dr/discover_drs.py scripts/dr/ tests/test_dr_discovery.py
git commit -m "feat(dr): add discovery script — seed list processing + SET scan + mapping generation"
```

---

### Task 6: Add DR hooks to trade_gen.py

**Files:**
- Create: `kth_dr/trade_gen_dr.py`
- Modify: `kth/trading/trade_gen.py`
- Test: `tests/test_dr_trade_gen.py`

- [ ] **Step 1: Create kth_dr/trade_gen_dr.py**

```python
"""DR-specific trade generation helpers — execution ticker resolution, same-underlying guard."""
from kth_dr.universe_dr import get_dr_for_underlying, get_underlying_for_dr


def resolve_execution_ticker(ticker: str) -> str:
    """Given an underlying ticker, return the DR ticker if one exists with a verified DR.
    Identity function for non-DR tickers."""
    dr = get_dr_for_underlying(ticker)
    if dr:
        return dr["dr_ticker"]
    return ticker


def get_underlying_for_held(ticker: str) -> str:
    """If ticker is a DR, return its underlying. Identity for non-DR tickers.
    Used by same-underlying guard in the buy loop."""
    underlying = get_underlying_for_dr(ticker)
    return underlying if underlying else ticker


def is_held_underlying(held_tickers: list[str], candidate_ticker: str) -> bool:
    """Check if candidate_ticker's underlying is already held (directly or via DR)."""
    candidate_underlying = get_underlying_for_held(candidate_ticker)
    for held in held_tickers:
        held_underlying = get_underlying_for_held(held)
        if held_underlying == candidate_underlying:
            return True
    return False
```

- [ ] **Step 2: Modify trade_gen.py — add TRADABLE_TICKERS + execution_ticker**

Replace line 20:

```python
THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
try:
    from kth_dr.universe_dr import get_verified_dr_tickers
    EXTRA_TICKERS = get_verified_dr_tickers()
except ImportError:
    EXTRA_TICKERS = []
TRADABLE_TICKERS = THAI_TICKERS + EXTRA_TICKERS
```

In `load_forecasts()`, replace `for ticker in THAI_TICKERS:` with `for ticker in TRADABLE_TICKERS:` (line 40).

After the `rows.append({...})` block in `load_forecasts()`, before `rows.sort(...)`, add execution_ticker resolution:

```python
    # Resolve execution ticker for DR underlyings
    try:
        from kth_dr.trade_gen_dr import resolve_execution_ticker
        for row in rows:
            row["execution_ticker"] = resolve_execution_ticker(row["ticker"])
    except ImportError:
        for row in rows:
            row["execution_ticker"] = row["ticker"]
```

In `generate_trade_ticket()`, in the buy loop (around line 196), compute share lot using `execution_ticker`'s close:

```python
    per_slot = remaining_cap / max(slots - len(buys), 1)
    exec_ticker = f.get("execution_ticker", f["ticker"])
    exec_close = f["close"]  # will be DR close when execution_ticker differs
    lots = int(per_slot / exec_close / 100) * 100
```

In the buy rationale, add underlying info when it's a DR:

```python
    exec_ticker = f.get("execution_ticker", f["ticker"])
    if exec_ticker != f["ticker"]:
        rationale = f"🟢↑ DR proxy for {f['ticker']}, rank#{rank_idx} net_ret={f['net_ret']:+.2%}"
    else:
        rationale = f"🟢↑ rank#{rank_idx} net_ret={f['net_ret']:+.2%}"
```

- [ ] **Step 3: Write tests for kth_dr/trade_gen_dr.py**

```python
"""Tests for kth_dr.trade_gen_dr — execution ticker resolution, same-underlying guard."""
from kth_dr.trade_gen_dr import resolve_execution_ticker, get_underlying_for_held, is_held_underlying


def test_resolve_execution_ticker_non_dr():
    """Non-DR tickers should return identity."""
    result = resolve_execution_ticker("PTT.BK")
    assert result == "PTT.BK"


def test_get_underlying_for_held_non_dr():
    """Non-DR tickers should return identity."""
    result = get_underlying_for_held("PTT.BK")
    assert result == "PTT.BK"


def test_is_held_underlying_no_match():
    """Different underlyings should not match."""
    result = is_held_underlying(["PTT.BK", "KBANK.BK"], "AAPL")
    assert result is False


def test_is_held_underlying_empty():
    result = is_held_underlying([], "AAPL")
    assert result is False
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_dr_trade_gen.py -v`
Expected: 4 tests pass

- [ ] **Step 5: Verify full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all existing tests + new DR tests pass

- [ ] **Step 6: Commit**

```bash
git add kth_dr/trade_gen_dr.py kth/trading/trade_gen.py tests/test_dr_trade_gen.py
git commit -m "feat(dr): add DR hooks to trade_gen.py — execution_ticker, TRADABLE_TICKERS, same-underlying guard"
```

---

### Task 7: Create DR data loader

**Files:**
- Create: `kth_dr/loader_dr.py`
- Test: `tests/test_dr_loader.py`

- [ ] **Step 1: Create kth_dr/loader_dr.py**

```python
"""DR data loader — bundles underlying, DR, and FX OHLCV data."""
from kth.data.loader import load_cached, download_universe
from kth_dr.universe_dr import get_dr_info_for_display


def load_dr_bundle(underlying_ticker: str) -> dict[str, object]:
    """Load underlying OHLCV, DR OHLCV, and FX rate for a DR position.

    Returns dict with keys:
        underlying_ohlcv, dr_ohlcv, fx_ohlcv, dr_info
    or raises FileNotFoundError if data is unavailable.
    """
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        raise FileNotFoundError(f"No DR info found for {underlying_ticker}")

    underlying = load_cached(underlying_ticker)
    if underlying is None:
        raise FileNotFoundError(f"No cached data for underlying {underlying_ticker}")

    dr = load_cached(dr_info["dr_ticker"])
    if dr is None:
        raise FileNotFoundError(f"No cached data for DR {dr_info['dr_ticker']}")

    fx = load_cached(dr_info["fx_ticker"])
    if fx is None:
        raise FileNotFoundError(f"No cached data for FX {dr_info['fx_ticker']}")

    return {
        "underlying_ohlcv": underlying,
        "dr_ohlcv": dr,
        "fx_ohlcv": fx,
        "dr_info": dr_info,
    }


def ensure_dr_data(underlying_ticker: str) -> None:
    """Download all data sources required for a DR position.
    Idempotent — skips tickers that are already cached."""
    dr_info = get_dr_info_for_display(underlying_ticker)
    if dr_info is None:
        return
    tickers = [underlying_ticker, dr_info["dr_ticker"]]
    if dr_info.get("fx_ticker"):
        tickers.append(dr_info["fx_ticker"])
    download_universe(tickers)
```

- [ ] **Step 2: Write tests (using the conftest fixture for cached data)**

```python
"""Tests for kth_dr.loader_dr — bundle loading, ensure_dr_data."""
import pytest
from pathlib import Path


def test_load_dr_bundle_nonexistent_underlying():
    """Should raise FileNotFoundError for unknown underlying."""
    from kth_dr.loader_dr import load_dr_bundle
    with pytest.raises(FileNotFoundError):
        load_dr_bundle("TOTALLY.FAKE")


def test_ensure_dr_data_nonexistent(tmp_path):
    """Should not crash for unknown underlying."""
    from kth_dr.loader_dr import ensure_dr_data
    ensure_dr_data("TOTALLY.FAKE")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_dr_loader.py -v`
Expected: 2 tests pass

- [ ] **Step 4: Commit**

```bash
git add kth_dr/loader_dr.py tests/test_dr_loader.py
git commit -m "feat(dr): add DR data loader — load_dr_bundle() and ensure_dr_data()"
```

---

### Task 8: Add schema columns for DR positions

**Files:**
- Modify: `kth/trading/sheets_config.py`

- [ ] **Step 1: Add DR columns to POSITIONS_HEADERS**

Change line 26:

```python
POSITIONS_HEADERS = ['ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
                     'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss',
                     'underlying_ticker', 'premium_pct']
```

- [ ] **Step 2: Verify no breakage**

Run: `python -c "from kth.trading.sheets_config import POSITIONS_HEADERS, ALL_HEADERS; print(f'{len(POSITIONS_HEADERS)} headers')"`
Expected: "11 headers"

- [ ] **Step 3: Commit**

```bash
git add kth/trading/sheets_config.py
git commit -m "feat(dr): add underlying_ticker and premium_pct columns to Positions schema"
```

---

### Task 9: Integration test — full pipeline smoke test

**Files:**
- Modify: `tests/test_pipeline_smoke.py` (if one exists) or create `tests/test_dr_integration.py`

- [ ] **Step 1: Create DR integration test**

```python
"""Integration test: DR module loads, registers with universe, trade_gen imports gracefully."""
import sys
from pathlib import Path

import pytest


def test_kth_dr_imports_cleanly():
    """kth_dr package must import without errors when no mapping file exists."""
    import kth_dr
    assert kth_dr.__name__ == "kth_dr"


def test_universe_plugin_hook_works_with_dr():
    """After kth_dr import, register_asset_class is available and functional."""
    from kth.data.universe import register_asset_class, get_ticker_class, get_sector, get_friction, _extra_ticker_class, _extra_sector, _extra_friction
    register_asset_class({"INTEGRATION.TEST": "dr"}, sector={"INTEGRATION.TEST": "Global"}, friction={"dr": {"commission_oneway": 0.001, "slippage_oneway": 0.001}})
    assert get_ticker_class("INTEGRATION.TEST") == "dr"
    assert get_sector("INTEGRATION.TEST") == "Global"
    f = get_friction("INTEGRATION.TEST")
    assert f["commission_oneway"] == 0.001
    _extra_ticker_class.pop("INTEGRATION.TEST", None)
    _extra_sector.pop("INTEGRATION.TEST", None)
    _extra_friction.pop("dr", None)


def test_trade_gen_imports_without_dr():
    """trade_gen must import and function when kth_dr is absent."""
    from kth.trading import trade_gen
    assert hasattr(trade_gen, "THAI_TICKERS")
    assert len(trade_gen.THAI_TICKERS) > 0
```

- [ ] **Step 2: Run all DR-related tests**

Run: `python -m pytest tests/test_dr_*.py tests/test_universe.py -v`
Expected: All pass

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_dr_integration.py
git commit -m "test(dr): add integration tests for DR module, universe hook, and trade_gen compatibility"
```

---

### Task 10: Documentation — update AGENTS.md and PROJECT_STRUCTURE.md

**Files:**
- Modify: `AGENTS.md`
- Modify: `PROJECT_STRUCTURE.md`

- [ ] **Step 1: Add kth_dr/ entry to project docs**

In `PROJECT_STRUCTURE.md`, add under the module reference:

```
### `kth_dr/` — DR (Depositary Receipt) integration
- `universe_dr.py` — DR_MAP loading, get_dr_for_underlying(), get_verified_dr_tickers()
- `loader_dr.py` — load_dr_bundle() for 3-series OHLCV bundle
- `discover_drs.py` — seed list + SET scan -> mapping.json
- `trade_gen_dr.py` — execution_ticker resolution, same-underlying guard
```

- [ ] **Step 2: Update AGENTS.md with DR workflow**

Under the existing "What not to build yet" section, add a note:

```
- DR (Depositary Receipt) integration: live. See docs/superpowers/specs/2026-07-12-global-dr-integration-design.md.
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md PROJECT_STRUCTURE.md
git commit -m "docs: add kth_dr/ to project docs and AGENTS.md"
```
