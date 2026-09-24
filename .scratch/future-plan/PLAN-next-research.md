# Plan: next research steps (written 2026-09-21)

Sequence, dependencies, gates and the multiple-testing budget for tickets 12-16. Tickets are files here because `gh` is not installed (see README). Do one ticket at a time; each ticket names its own stop condition.

## Result of step 1 (2026-09-21)
Ticket 12 returned MATERIAL: 76.9% of the 2024 PIT input windows contained at least 4 stub rows and 48.6% at least 20 (about 11% of rows by December). New ticket 17 (rerun of the 2024 PIT forecasts on cleaned inputs) is drafted and inserted after ticket 13; it needs the user's approval and a compute choice. Steps 13 and 14 are unchanged.

## Result of ticket 17 (2026-09-22)
Stage 1 (53-date sample) found no detectable change in signal quality from cleaning (gate G3, inconclusive but centered near zero). User chose to close the ticket without running Stage 2 (~33h). The 2024 point-in-time result stands: it is not attributable to the stub-row data-quality problem found in ticket 09's audit.

## Why this order
The 2026-09-21 data audit (ticket 09) found Yahoo stub rows on 57 dates (49 in 2024) and unadjusted corporate-action breaks in the cache. Every earlier result, including the point-in-time 2024 backtest (ticket 00) and the live forecasts, was computed from that cache. So the first job is to learn whether those results are affected, then fix the data once, then re-check the one marginal lead, and only then spend effort on new ideas.

| Order | Ticket | What | Depends on | Needs GPU / network | Gate to the next step |
|---|---|---|---|---|---|
| 1 | 12 stub-impact audit | Count stub rows inside the 400-row Kronos input windows (2024 PIT cache, live folders). Read-only. | none | no | If "material" (rule in the ticket), open a follow-up ticket for a rerun on cleaned inputs and ask the user before any GPU use. Otherwise record "not material" and continue. |
| 2 | 13 clean data loader | One tested loader that drops stub dates and applies an explicit break table; retry the `^SET.BK` repair. | 12 (to know what must be handled) | index retry needs network | Loader passes its synthetic self-test; documented in CLAUDE.md. |
| 3 | 14 factor baselines on cleaned data | Rerun ticket 06's three factor rules, same design, on the loader's output. | 13 | no | Decides whether the momentum lead is withdrawn or stays "weak, unconfirmed". |
| 4 | 15 LightGBM sign-flip diagnostic | Explain why the ticket-09 ranker flipped sign between windows. Diagnostic only. | 13 | no | None; feeds no adoption decision. |
| 5 | 16 non-arXiv literature | SSRN, journals and Thai-institution sources for SET momentum/anomaly evidence. | none, but do not test anything before 12-14 are done | web only | Produces a ranked shortlist; any test needs a new pre-registration. |

Target: steps 1-3 done before the first live review on 2026-12-30, so the review runs on a cache whose problems are known. Steps 4-5 are optional.

## Multiple-testing register (do not forget this when a new test is proposed)
Correction families already spent on the SET data windows 2018-2026:
- Ticket 06: 3 factor rules (family threshold 0.05/3).
- Ticket 07 (entry/exit/stop variants on clean windows; there is no 07 file, see the README row and `data/logs/stop_loss_sweep.log`, `scripts/run_entry_exit_sweep.py`): none adopted. The exact number of variants tried is not recorded in this plan; count it from those logs before proposing a new test on the same windows.
- Ticket 09: 3 literature candidates (family threshold 0.05/3); none adopted.
- Ticket 10: 2 trend filters on the untouched 2018-2019 window (0.05/2); none passed.
- Ticket 14 (below) re-runs 06's family on cleaned data; it does NOT open a new family and keeps threshold 0.05/3.
- Forward, proposed 2026-09-23 (ticket 20, DRAFT): Kronos live book (frozen 0.05) + S1 momentum + S2 SMA200 as one register entry of 3; S1/S2 at 0.05/3 each. Ticket 11 addendum A2 adds a second look at the Kronos edge question at 24 months (p < 0.025).
- Not counted: ticket 18 (forecast accuracy vs naive, no trading rule) and ticket 19 (data-input audit).
No unseen SET window is left except data that has not happened yet: the live track (ticket 11). A new candidate from ticket 16 therefore has no clean historical window to be tested on; it should be tested by adding it to the forward paper track with a pre-committed rule, not by another backtest on 2018-2026.

## Standing rules
- Pre-register before any run; run once; no tuning after seeing a result.
- Say "abstract read" vs "full text read"; never cite a search summary as fact.
- Never compare the live track with its benchmark before the ticket-11 review dates (data-input checks are allowed).
- No change to the ticket-11 rule after seeing live results.

## 2026-09-23 review (user "agree" to all six items)
Done: live-evidence snapshots (ticket 05), `compute_calibration` fixed (trading-day horizon, unelapsed forecasts skipped, both directions labelled), stub share added to the review process log (ticket 12). Drafted, need approval: ticket 11 addendum A, tickets 18, 19, 20. Recommended order: 11-A, then 19 (before 2026-12-30), then 18, then 20 (start 2026-11).
