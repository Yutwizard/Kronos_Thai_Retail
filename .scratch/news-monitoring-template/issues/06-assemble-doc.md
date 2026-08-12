# 06 - Assemble docs/news-monitoring-manual.md and .html

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05

## Question

Synthesize every earlier ticket's answer into the actual deliverable:
`docs/news-monitoring-manual.md` and `docs/news-monitoring-manual.html`,
matching the structure/style of the existing `operations-manual.md`/`.html`
pair (same header, same Inter + JetBrains Mono styling in the `.html`
version).

Contents, pulling directly from the resolved tickets:

1. Tiered source lists (from tickets 01 and 02) — SET-listed equities and
   DR underlyings, clearly separated.
2. Recommended alerting/aggregation setup (from ticket 03).
3. The daily quick-scan and weekly deeper-review templates (from ticket
   05), in the format that ticket settled on.
4. The red-flag decision protocol (from ticket 04).

This is the map's execution override (see map.md Notes) — it produces the
destination artifact directly rather than stopping at a decision. No
pipeline/model code is touched; this is a docs-only change.

## Answer

Written `docs/news-monitoring-manual.md` and `docs/news-monitoring-manual.html`,
matching `operations-manual.md`/`.html`'s exact house style (same CSS block,
hero/toc/card/step-box/highlight/trade-grid/quick-ref pattern, numbered
sections with time estimates, Objective + Step-by-Step). Eight sections:

1. Daily Quick-Scan (10-15 min) — ticket 05's 6-step sequence.
2. Weekly Deeper Review (15-20 min) — ticket 05's calendar+event-trigger design.
3. Red-Flag Decision Protocol — ticket 04's full protocol (trigger threshold,
   5-item skip list, single-ticker scope, DR addition, recording convention).
4. Source Directory — SET-Listed Equities — ticket 01's tiered tables plus
   its Thai SEC/IR Plus addendum.
5. Source Directory — DR Underlyings — ticket 02's exchange-grouped tables
   plus its Seeking Alpha and Nasdaq Copenhagen addenda.
6. One-Time Aggregation Setup — ticket 03's Inoreader/Settrade App/Google
   News RSS setup, including both addenda rounds.
7. Caveats & Known Gaps — consolidated table of every ruled-out/unconfirmed
   source across all three research tickets, so a future pass doesn't
   re-chase them without reason.
8. Quick Reference Card — condensed cheat-sheet mirroring
   `operations-manual.html`'s closing pattern.

Also added discoverability links: a row in `docs/getting-started.md`'s
"Where to Go Next" table, and an entry in `PROJECT_STRUCTURE.md`'s file
listing next to the operations-manual entries — both minimal, docs-only
additions consistent with how the other manuals are cross-referenced.

Verified the HTML is well-formed (balanced `<div>`/`<table>` tags, parses
cleanly). No pipeline/model code touched anywhere in this ticket — purely
new/edited Markdown and HTML files plus two existing-doc cross-link
insertions.

Status: resolved.
