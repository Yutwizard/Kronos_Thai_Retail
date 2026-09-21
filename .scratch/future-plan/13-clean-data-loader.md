# Ticket 13: one tested clean-data loader (TODO)

STATUS: DONE 2026-09-21 except the `^SET.BK` repair, which is BLOCKED (Yahoo returns one row). Depends on ticket 12.

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

## Result (2026-09-21)
- `kth/data/clean.py` written: `load_clean_closes(tickers, cache_dir, drop_stub_share=0.5, breaks=KNOWN_BREAKS, ffill_limit=10)` returns `(close, real, report)`; `report` lists dropped dates, applied and skipped breaks, and the per-ticker count of stub rows kept but flagged not real. Reads go through `load_cached`; it never writes to the cache.
- `KNOWN_BREAKS` starts with TRUE.BK 2023-03-03 (source recorded in the table). SCB.BK needs no adjustment (series starts at the share swap).
- `verify_clean_data.py` (synthetic data only, temp dirs) passes: stub-row definition, data-wide stub date dropped, lone stub kept but flagged, cache files hashed before and after, deterministic, break scaling gives a 0 return on the break day and leaves all other returns unchanged, unappliable breaks are reported.
- Acceptance check (done as a one-off, script not kept): on the real 51 thai_equity files the loader drops the same 57 calendar dates and applies the same TRUE factor (1.686274) as the ad-hoc cleaning behind the ticket-09 robustness table, and the price frame is identical (max absolute difference 0.0, same 2,378 x 51 shape). So those robustness numbers are reproducible through the loader.
- 50 tickers carry per-ticker stub rows that are kept but flagged not real (6,101 flagged cells in total); `scripts/check_data_sanity.py` still reports the raw cache problems.

## `^SET.BK` repair: blocked
- Retried 2026-09-21 with `yf.download(period="10y")`, `Ticker.history(period="max")` and `Ticker.history(start="2026-07-01")`: each returned a single row dated 2026-09-21. Nothing was written to the cache (cache: 2,384 rows, last 2026-09-15 stub; last real row 2026-07-17).
- Manual path if Yahoo does not recover: export the SET index daily history (open, high, low, close, volume) from SET's own market-data pages or another licensed source, convert it to the Kronos schema (`to_kronos_format`), and build a merged copy that adds only rows after 2026-07-17 with volume > 0 (about 40 trading days are missing). Run `scripts/check_data_sanity.py` on the copy, then replace the cache file deliberately (the downloader's row-count guard only protects `download_universe`).
- Until then any index-based rule can only be evaluated to 2026-07-17.
