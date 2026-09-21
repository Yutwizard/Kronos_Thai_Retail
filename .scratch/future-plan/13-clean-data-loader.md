# Ticket 13: one tested clean-data loader (TODO)

STATUS: TODO. Depends on ticket 12 (to know what must be handled).

## Goal
Replace the ad-hoc cleaning in the ticket-09 robustness script with one small, tested loader, so future analyses use identical cleaned prices, and retry the `^SET.BK` repair.

## Design
- New module `kth/data/clean.py`: `load_clean_closes(tickers, cache_dir="data/raw", drop_stub_share=0.5, breaks=KNOWN_BREAKS)`; returns `(close, real)` where `real` marks non-stub prices. Never writes to `data/raw`.
- Stub handling as in `scripts/check_data_sanity.py`: a flat zero-volume row is a stub; calendar dates where at least half of the tickers are stubbed are dropped; single-ticker stubs stay as NaN in `real` (price carried forward, not eligible).
- Corporate-action breaks: an explicit, reviewed table, no automatic guessing. Initial entries: `TRUE.BK` 2023-03-03 (DTAC merger, scale earlier prices so the day's return is 0) and `SCB.BK` (series starts at the 2022-04-27 share swap; no adjustment, note only). New entries need a source noted in the table.
- Report function returning what was dropped or adjusted, so results can cite it.
- Self-test in the style of `verify_*.py` (plain asserts on synthetic frames): stub-date drop, TRUE-style break scaling, no mutation of the cache, idempotence.

## `^SET.BK` repair (separate step, needs network)
1. Retry a fresh Yahoo download of `^SET.BK` into the scratchpad only. If it returns one row again, stop; do not overwrite the cache (the downloader's row-count guard also blocks it).
2. If Yahoo recovers with a full history, merge only rows after the last real cache row (2026-07-17) with volume > 0, then run `scripts/check_data_sanity.py`.
3. If it does not recover, document a manual path (export from SET's own data) in this ticket and leave the cache as it is.

## Done when
- Self-test passes; the loader is documented in a CLAUDE.md quirks bullet; `scripts/check_data_sanity.py` still reports the raw cache problems (the loader does not hide them).
- The ticket-09 robustness numbers can be reproduced through the loader.

## Out of scope
Fixing the raw cache in place, automatic corporate-action detection, changing the pre-registered runners of tickets 09/10.
