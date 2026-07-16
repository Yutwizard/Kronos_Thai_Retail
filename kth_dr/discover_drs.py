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
    """Only catches exact matches against universe.py's hardcoded UNIVERSE
    tickers (thai_equity + thai_index as of 2026-07-16 — us_equity and other
    non-SET classes were archived, see archive/other-asset-classes/). Does NOT
    know that "any US-listed stock" is directly investable — that judgment
    call is why Task 4's seed list uses home-market tickers instead of US
    ADRs. Don't rely on this function alone when adding new seed entries."""
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

    # Track verified status (and any other human-added fields, e.g. verified_note)
    # across runs so re-running discovery never silently un-verifies something
    # the user already approved, or discards the sourcing trail behind it.
    previous_verified: dict[str, dict] = {}
    for underlying, entry in existing.items():
        if underlying.startswith("_"):
            continue
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                previous_verified[alt["dr_ticker"]] = alt

    mapping = {}
    excluded = {}

    for underlying, candidates in seed.items():
        if underlying.startswith("_"):
            continue
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
        prev = previous_verified.get(dr_ticker)

        alt = {
            "dr_ticker": dr_ticker,
            "ratio": ratio,
            "avg_volume_30d": stats["avg_volume_30d"],
            "listing_date": stats["listing_date"],
            "history_rows": stats["history_rows"],
            "verified": bool(prev),
        }
        if prev and "verified_note" in prev:
            # Carry forward the human's sourcing note — losing it on every
            # re-run would erase the audit trail for why this DR was trusted.
            alt["verified_note"] = prev["verified_note"]

        mapping[underlying] = {
            "display_name": display_name,
            "underlying_exchange": exchange,
            "underlying_currency": currency,
            "fx_ticker": fx_ticker_for_currency(currency),
            "primary_dr": dr_ticker,
            "alternatives": rank_alternatives([alt]),
        }

    # Carry forward the human-curated review status/summary the same way
    # per-ticker verified_note is carried forward above -- otherwise every
    # re-run silently resets a hand-written "reviewed" status_note back to
    # "needs_review", discarding real verification work. Only safe to carry
    # forward if the set of underlyings hasn't changed since that review;
    # new/removed entries genuinely do need re-review.
    existing_meta = existing.get("_meta", {})
    existing_underlyings = {k for k in existing if not k.startswith("_")}
    new_underlyings = set(mapping.keys())
    if existing_meta.get("status") and existing_underlyings == new_underlyings:
        review_meta = {"status": existing_meta["status"]}
        if "status_note" in existing_meta:
            review_meta["status_note"] = existing_meta["status_note"]
    else:
        review_meta = {"status": "needs_review"}

    output = {
        "_meta": {
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
            "dr_count": len(mapping),
            "underlying_count": len(mapping),
            **review_meta,
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
