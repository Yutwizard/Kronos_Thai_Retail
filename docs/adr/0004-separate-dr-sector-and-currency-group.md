# ADR 0004: Separate DR Sector from DR Currency Group

**Date:** 2026-07-18  **Status:** Accepted

## Context
Commit `aaadfe2` (2026-07-18) made the sector concentration guard DR-aware by setting `sector[dr_ticker] = underlying_currency` — grouping DR positions by HKD/JPY/EUR/... instead of a flat "Global" bucket, since FX/regional-close correlation is real risk the old bucket ignored. This fixed one problem but created another: it overloaded "sector" to mean "currency" for DR, so DR tickers have no real industry-sector classification at all, and the dashboard's "Sector" column shows a currency code for DR rows.

## Decision
Track DR sector and DR currency as two independent concentration pools, each capped separately, instead of one field doing both jobs:

1. **`SECTOR`** (existing, thai_equity) + a new hand-curated DR sector dict in `kth_dr/universe_dr.py`, using a **separate global industry taxonomy** (Tech, Auto, Luxury/Consumer, Healthcare, Semiconductors, Financials, ...) — not SET's 10 Thai-market buckets, and not merged into the thai_equity sector pool.
2. **`CURRENCY_GROUP`** (new), DR-only, sourced from `underlying_currency`. `thai_equity` tickers return no currency group (`None`) and are exempt from this check entirely — no `"THB"` bucket is created.
3. Both pools are capped at 2 (`MAX_SECTOR_POSITIONS`, `MAX_CURRENCY_POSITIONS` — separate constants, not shared, even though they start equal). A DR buy candidate must clear both caps; either being full is a hard reject, same behavior as the existing sector guard.
4. Dashboard shows two columns, Sector and Currency; thai_equity rows show `—` under Currency.

## Rationale
- **Not a combined sector×currency key:** too granular given the DR universe size — most pairs would have 0-1 positions, so the cap would never bind.
- **Not a shared taxonomy across thai_equity and DR:** SET's 10 sectors are built around the Thai economy and don't map cleanly onto foreign large-caps (Tencent, Toyota, LVMH); forcing DRs into them would misclassify most into a generic "Other".
- **Not a `"THB"` bucket for thai_equity:** with `MAX_POSITIONS = 5` portfolio-wide, a uniformly-applied currency cap of 2 would silently cap thai_equity at 2 positions regardless of sector — an unrelated, severe side effect. thai_equity's concentration risk is already fully covered by its sector guard; currency adds no information in a single-currency domestic universe.
- **DR sector data lives in code, not `data/dr/mapping.json`:** mapping.json is verified-market-fact data (ratios, tickers, liquidity, source-checked against KTB/BLS/InnovestX) with its own review workflow (`_meta.status`). Sector classification is a judgment call, not a verifiable fact, and mixing the two would conflate different kinds of truth.

## Consequences
- `register_asset_class()` (`kth/data/universe.py`) gains a `currency_group` param alongside `sector`/`friction`.
- New `get_currency_group()` accessor, `None` default for tickers with no registered group.
- `kth_dr/universe_dr.py`'s `build_registration_dicts()` needs the DR sector dict populated (curation work, not yet done) and now also returns a currency-group dict built from `underlying_currency`.
- `kth/trading/trade_gen.py`'s buy loop checks both pools (AND, hard reject) instead of one `sector_counts` dict.
- See `CONTEXT.md`: [[Sector Concentration]], [[Currency Group]], [[DR (Depositary Receipt)]].
