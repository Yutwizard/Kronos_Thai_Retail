# Ticket 12: did stub rows contaminate the Kronos input windows? (TODO)

STATUS: DONE 2026-09-21. VERDICT: MATERIAL. Follow-up: ticket 17 (needs the user's approval before any inference). First step of `PLAN-next-research.md`.

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

## Results (run 2026-09-21, `scripts/audit_stub_windows.py`, log `data/logs/stub_windows_audit.log`)
Tickers audited: the 51 thai_equity and the DR underlyings' foreign tickers, wherever a forecast and a raw file both exist. Windows: last 400 raw rows up to each forecast's `lookback_end`.

### 2024 point-in-time cache (13,100 windows, 0 skipped)
- Share with at least 4 stub rows: 76.9%. Share with at least 20: 48.6%. Worst window: 74 stub rows. Mean: 22.4 stub rows per 400.
- By month, share affected / heavy / mean stub rows: Jan 2% / 0% / 0.2; Feb 2% / 0% / 0.2; Mar 23% / 0% / 2.1; Apr 94% / 1% / 7.4; May 100% / 4% / 12.9; Jun 100% / 50% / 19.2; Jul 100% / 77% / 25.9; Aug 100% / 87% / 30.8; Sep 100% / 88% / 37.2; Oct 100% / 91% / 42.6; Nov 100% / 92% / 45.1; Dec 100% / 92% / 45.1.
- Highest mean stub count: TRUE.BK 36.6, BTS.BK 33.8, KBANK.BK 33.8, LH.BK 30.0, BDMS.BK 29.9, TISCO.BK 29.8, TOP.BK 29.7, BCP.BK 28.3.
- Why it grows: the 57 stub calendar dates begin 2024-03-12 and 49 fall in 2024, so a 400-row window in late 2024 spans almost all of them (about 11% of the input rows), plus per-ticker stubs.

### Live folders from 2026-06-29 (4,897 windows, 26 skipped: lookback_end not in the local raw file)
- Share with at least 4 stub rows: 78.7%; with at least 20: 0.0%; worst window 18; mean 5.25 stub rows per 400 (about 1.3%).
- By month, mean stub rows: Jun 4.4, Jul 4.6, Aug 5.8, Sep 5.7. Highest: BANPU.BK 8.2, several others about 7.7.
- Caveat as planned: this uses the local raw cache, which may differ from what the Kaggle pipeline saw on the day. The 2024 figure is exact for the PIT cache because it was generated from the current raw files.

## Verdict by the frozen rule
MATERIAL (76.9% affected, 48.6% heavy, against thresholds of 10% and 2%).

## What this does and does not say
- It does NOT say the 2024 result is wrong or that an edge exists. It says the 2024 point-in-time backtest (CAGR -26%, IC -0.10) was produced from model inputs in which up to about 11% of rows were stale zero-volume stub candles, so it is not a clean test of the signal, and it has not been re-checked on cleaned inputs.
- It weakens, but does not by itself change, the standing conclusion "no valid evidence of an edge": the evidence for a loss is now itself unreliable, and the evidence for an edge was already withdrawn.
- The live track sees a milder version of the same contamination (about 1.3% of input rows on average).

## Decision (per this ticket)
- No inference was run here. Follow-up ticket 17 defines a rerun of the 2024 PIT forecasts on cleaned inputs, with a comparison rule fixed in advance. It needs the clean loader (ticket 13) and the user's approval, including the compute choice.
- Live windows: report only. Two recommendations for the user, neither applied: (1) have the daily pipeline skip stub rows when building the 400-row input; (2) add the stub share of the live input windows to the ticket-11 review process log (reporting only, never used to adjust a result, rule unchanged).
