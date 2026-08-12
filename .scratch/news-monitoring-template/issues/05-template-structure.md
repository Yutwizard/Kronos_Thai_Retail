# 05 - Design the daily quick-scan and weekly deeper-review template structure

Type: grilling
Status: resolved

## Question

Design the actual structure/format of the two cadence layers named in the
map's Destination:

- **Daily quick-scan**: run against whatever 10 tickers `get_top_ranked(10)`
  returns that day, plus a market/macro headline check. What does this
  actually look like as a followable template — a per-ticker checklist
  with fixed fields (e.g. "any primary-source disclosure since last
  check?", "any secondary-source coverage flagged?", "macro headline
  check: SET index, USD/THB, BoT")? A single page the investor fills in
  daily, or a mental checklist with no artifact?
- **Weekly/deeper review**: broader sector and macro context, or triggered
  when a name newly enters the top-10 for the first time in a while. What
  triggers it, and what does it cover that the daily scan doesn't?

Grill the user on format preferences (checklist table, prose walkthrough,
etc.) and how this should read inside `docs/news-monitoring-manual.html`
alongside the existing docs' style (e.g. `operations-manual.html`'s daily
routine section, `morning-paper-trading-guide.md`'s structure) — consult
those files for tone/format precedent before proposing options.

## Answer

Grilled and confirmed with the user. **House-style precedent checked first**
(not asked, looked up): `docs/operations-manual.md` uses numbered top-level
sections with a time estimate in the heading (e.g. "1. Daily Morning Routine
(12-15 minutes)"), each with an Objective subsection then `#### Step N.M —
<verb phrase>` subsections, interpretation tables, code-block example
output, and worked examples. The new doc's two cadence sections follow this
same pattern for consistency with the rest of the ops docs.

**Daily quick-scan (~10-15 minutes)** — folded into the existing evening
pipeline routine, produces a log entry (not a mental-only checklist):

1. Pull today's `get_top_ranked(10)` list (`kth/trading/trade_gen.py:371`).
2. Per ticker: check the relevant Inoreader folder (Thai-market or
   DR-underlyings, per ticket 03) for anything new since yesterday.
3. Per ticker (SET names only): glance at the Settrade App favorites push
   for anything Inoreader missed.
4. Cross-check any flagged item against ticket 04's fixed 5-item skip list
   — only those five ever trigger a skip.
5. One combined macro glance (not per-ticker): SET index level/direction,
   USD/THB, any same-day BoT release.
6. Log the day's entry in `data/positions/morning_log.md` — even a
   "no flags found" day gets a line, so there's a trace that the scan
   actually happened.

**Weekly deeper review (~15-20 minutes)** — piggybacked onto the *existing*
"3. Weekly Portfolio Review (15-20 minutes)" slot in `operations-manual.md`
rather than a new standalone cadence:

- Sector-level context for whichever sectors the current top-10 touches.
- Macro/BoT releases from the past week.
- SET Market Alerts check for any name that's been sitting in the top-10
  across multiple days.
- Event-triggered step: a deeper look (IR page, recent filings) at any
  name newly entering the top-10 for the first time in a while — this is
  the "triggered" component folded into the calendar cadence rather than
  run as a separate always-on watcher.

**Recording:** both cadences write into the existing `morning_log.md`/weekly
review journal — no new file, no dashboard/API change, consistent with
ticket 04's recording decision.

Status: resolved.
