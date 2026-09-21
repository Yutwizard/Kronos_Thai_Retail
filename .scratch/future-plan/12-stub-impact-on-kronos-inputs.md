# Ticket 12: did stub rows contaminate the Kronos input windows? (TODO)

STATUS: TODO. Read-only, CPU-only. First step of `PLAN-next-research.md`.

## Question
The 2026-09-21 audit found flat zero-volume stub rows on 57 calendar dates (49 in 2024, 1 in 2025, 7 in 2026). Kronos reads the last 400 rows of each ticker (`kth/models/kronos_wrapper.py` `lookback=400`). How many of those input windows contained stub rows, in (a) the 2024 point-in-time backtest whose result was CAGR -26% (ticket 00) and (b) the live forecasts since 2026-06-29?

## Fixed definitions (chosen before counting)
- Stub row: volume == 0 and open == high == low == close in `data/raw/<ticker>.parquet`.
- Input window for forecast date D and ticker T: the last 400 rows of T's raw data up to and including the row at `lookback_end` (read from the forecast's `_meta.json`), which is exactly what `precompute_forecasts` and the live pipeline feed the model.
- Affected window: at least 4 stub rows (1% of 400). Heavy window: at least 20 stub rows (5%).
- MATERIAL if at least 10% of (ticker, date) windows in the 2024 PIT cache are affected, or at least 2% are heavy.

## Steps
1. Enumerate forecast folders: `data/forecast_cache_pit/NeoQuasar_Kronos-small/<date>/` (262 folders, 2024) and `data/forecast_cache/NeoQuasar_Kronos-small/<date>/` from 2026-06-29 onward (live). Ignore the earlier contaminated folders of the old cache.
2. For each `<ticker>.parquet` and its `_meta.json`, compute the stub count in the 400-row window. Only tickers of the frozen 51 thai_equity list and the 36 DR underlyings' foreign tickers that exist in `data/raw`.
3. Report per year/month: number of windows, share affected, share heavy, worst window, and which tickers are hit most.
4. Limitation to state: the live folders were produced on Kaggle from a fresh download at the time, and the local cache today may differ from what the pipeline saw. The count is therefore a proxy for the live case and exact only for the 2024 PIT cache, which was generated from the current raw files.
5. Write the result table into this ticket and set MATERIAL / NOT MATERIAL by the rule above.

## Decision
- NOT MATERIAL: record it, keep the 2024 finding as is, continue to ticket 13.
- MATERIAL: do not re-run inference here. Open a ticket "rerun 2024 PIT forecasts on cleaned inputs" (GPU or slow CPU, needs the user's approval and a pre-committed comparison rule) and still continue to ticket 13.
- For the live windows: only report. Any product change (for example skipping stub rows in the daily pipeline) is a recommendation to the user, and the ticket-11 rule is not changed.

## Outputs
- `scripts/audit_stub_windows.py` (read-only), log in `data/logs/stub_windows_audit.log`, results and verdict appended below.

## Out of scope
Re-running the model, re-generating any forecast, editing `data/raw`, comparing the live track with its benchmark.
