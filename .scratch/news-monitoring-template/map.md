# Map: Daily news-monitoring template for the top-10 ranking

## Destination

A new standalone doc — `docs/news-monitoring-manual.md` +
`docs/news-monitoring-manual.html` (matching the existing
`operations-manual.md`/`.html` pair's structure and styling) — that defines a
**human-facing, manual news-monitoring practice** for the investor to run
alongside the daily Kaggle pipeline. It never touches pipeline/model code:
no news ingestion, scoring, or feed into `rank_score` or trade generation.
That boundary is deliberate — CLAUDE.md's hard scope limits explicitly
exclude "news sentiment" from the pipeline (`PROJECT_STRUCTURE.md §12`) —
this map does not relitigate that; it builds an entirely separate,
manually-run operator habit.

The doc covers, once all tickets below resolve:

1. A **tiered, curated source list** — primary (SET disclosures, BoT,
   company IR) vs secondary (Thai + English financial press) for SET-listed
   names, plus a **separate international source set** for the 6 DR
   underlyings (Hermès, L'Oréal, LVMH, Sanofi, Ferrari, Novo Nordisk —
   French/EU/US sources as appropriate for each).
2. **Layered cadence**: a daily quick-scan (today's `get_top_ranked(10)`
   names, from `kth/trading/trade_gen.py:371`, plus market/macro headlines)
   and a less-frequent deeper review (sector/macro context, or triggered
   when a name newly enters the top-10).
3. Recommended **alerting/aggregation tooling** (SET's own disclosure
   alerts, Google Alerts, RSS where available) so the daily habit doesn't
   mean manually opening 10+ sites every night.
4. A **lightweight decision protocol** — simple rules of thumb for when a
   primary-source finding should make the investor manually skip/flag a
   trade in the dashboard's paper-trading ticket. Judgment stays with the
   investor; nothing here is automated.

**This map's Notes override "plan, don't do"** (see below) — its final
ticket assembles the actual doc files, not just the decisions behind them.

## Notes

- **Execution override:** unlike a pure-decision map, this effort's last
  ticket (06) is a Task that writes `docs/news-monitoring-manual.md` and
  `.html` directly, synthesizing every earlier ticket's answer. Earlier
  tickets still resolve as decisions/research, not partial drafts.
- **Confirmed facts (no need to re-derive):**
  - "Top 10 ranking" = `get_top_ranked(n=10)` in
    `kth/trading/trade_gen.py:371`, sorted by `rank_score` (expected return
    ÷ forecast band width). It reshuffles daily.
  - DR underlyings in scope: Hermès, L'Oréal, LVMH, Sanofi, Ferrari, Novo
    Nordisk (per CLAUDE.md) — see `kth_dr/universe_dr.py` for the
    DR↔underlying mapping.
  - `kth/data/universe.py`'s `SECTOR` dict maps all 51 `thai_equity`
    tickers to 10 SET sectors — available if a ticket needs sector context,
    but the destination's macro scope (Q3 answer: ticker + broad
    market/macro, not sector-level) means sector isn't a primary axis.
  - Existing docs pair `.md` + `.html` per topic (e.g.
    `operations-manual.md`/`.html`); the new doc follows the same pattern
    and should reuse `operations-manual.html`'s header/CSS (Inter +
    JetBrains Mono, existing `<style>` block) for visual consistency.
  - Scope is strictly human-facing/manual. Any ticket that drifts toward
    pipeline code, automated news ingestion, or feeding signals into
    `rank_score`/trade generation is out of scope — see below.
- Skills to consult: `/research` for the source-curation and tooling
  tickets; `/grilling` + `/domain-modeling` for the decision-protocol and
  template-structure tickets.

## Decisions so far

- [01 - Curate tiered news sources for SET-listed equities](issues/01-set-source-curation.md) — Primary: SET News & Announcements (EN/TH), SET Market Alerts, BoT News & Media, company IR (no central directory). Secondary Thai: SETTRADE (has live RSS), Thunhoon, Kaohoon, efinanceThai, Bangkok Business News, Prachachat. Secondary English: Bangkok Post (RSS now bot-toll-gated), The Nation, Kaohoon International, Investing.com, Reuters/Bloomberg (macro-only). Key gap: SET's own RSS is dead — SETTRADE's RSS is the best fallback, flagged for ticket 03. **Addendum (2026-08-12):** Thai SEC (`sec.or.th`) added to primary tier — a distinct regulator from SET (tender offers, insider filings), browse-manually-only (403-blocked automated fetch). `irplus.in.th` noted as a common IR-page hosting pattern. Full detail in `research/01-set-sources-findings.md`.
- [02 - Curate tiered international news sources for DR underlyings](issues/02-dr-source-curation.md) — Grouped by exchange: Euronext Paris (Hermès/L'Oréal/LVMH/Sanofi — AMF BDIF + company IR primary; Les Echos/Boursorama/wires secondary), Milan (Ferrari — CONSOB eMarket + IR + SEC EDGAR; Il Sole 24 Ore/MilanoFinanza secondary), Copenhagen (Novo Nordisk — company IR w/ email alerts + GlobeNewswire + SEC EDGAR; DR/Børsen secondary). SET's DR channel confirmed mechanical-only (ratio/corporate-action mirroring via KTB/BLS issuer pages), not a news substitute. Several English-wire and JS-heavy IR sources flagged low-confidence, need manual spot-check. **Addendum (2026-08-12):** Seeking Alpha per-symbol RSS (`SNY`/`NVO`/`RACE`/`LVMUY`/`HESAY`/`LRLCY`) confirmed live for all 6 names — no signup, easiest source in the map to wire up. Nasdaq Copenhagen's exchange feed confirmed real but not company-filterable (Nordic-wide only) — GlobeNewswire stays the better option. Full detail in `research/02-dr-sources-findings.md`.
- [03 - Recommend alerting/aggregation tooling for the curated sources](issues/03-alerting-tooling.md) — One Inoreader account (free tier: 150 RSS + 20 email-to-RSS "Newsletter Feeds") in two folders (Thai-market / DR-underlyings), ingesting SETTRADE's RSS + Google Alerts (RSS delivery) for the 52 tickers, and DR-company IR email alerts via Inoreader's newsletter bridge. Settrade App's free per-ticker Favorites push stays the one channel outside the reader (no SET RSS/email exists). **Addendum (2026-08-12):** Google News RSS search (no-signup RSS, full-company-name phrasing required — bare tickers return stale junk) promoted to primary fallback ahead of Google Alerts; Seeking Alpha added for DR names; Yahoo Finance per-ticker RSS noted as patchy-but-usable supplemental (live for `PTT.BK`, empty for `AOT.BK`); Nikkei Asia RSS added for macro/regional context; CNBC, Trading Economics, and Investing.com RSS all ruled out (403-blocked or topic-only, no per-symbol option). Concrete setup steps + phrasing guidance in `research/03-alerting-tooling-findings.md`.
- [04 - Design the red-flag → skip/flag decision protocol](issues/04-decision-protocol.md) — Trigger: primary OR reputable secondary source, no need to wait for primary confirmation. Fixed 5-item skip list (halt/suspension, cash-balance/caution, fraud/investigation, auditor qualified opinion, sudden unscheduled C-suite exit) — everything else informational only. Strictly single-ticker scope, no macro override (leans on the existing Turmoil gate, doesn't reintroduce the retracted regime-timing pattern). DR trades also check the KTB/BLS DR-mechanics channel. Recorded via the existing `data/positions/morning_log.md` Reason field — no new dashboard/API field needed.
- [05 - Design the daily quick-scan and weekly deeper-review template structure](issues/05-template-structure.md) — Matches `operations-manual.md`'s existing house style (numbered sections, time estimate in heading, Objective + Step-by-Step). Daily quick-scan (~10-15 min): 6 fixed steps — pull top-10, skim pre-filtered Inoreader folders + Settrade App push per ticker, cross-check against ticket 04's skip list, one combined macro glance, log to `morning_log.md` daily. Weekly deeper review (~15-20 min): piggybacked onto the existing "3. Weekly Portfolio Review" slot — sector context, past week's macro/BoT releases, SET Market Alerts check, plus a deeper look at any name newly entering the top-10.
- [06 - Assemble docs/news-monitoring-manual.md and .html](issues/06-assemble-doc.md) — Written both files matching `operations-manual.md`/`.html`'s exact house style, 8 sections synthesizing tickets 01-05 in full (source directories, decision protocol, cadence templates, aggregation setup, consolidated caveats table, quick reference card). Added discoverability links in `docs/getting-started.md` and `PROJECT_STRUCTURE.md`. No pipeline/model code touched.

**Destination reached** — all 6 tickets resolved, no open frontier remains. `docs/news-monitoring-manual.md`/`.html` is the finished deliverable — this map is complete.

## Not yet specified

- Source-list maintenance/re-vetting cadence over time (link rot, an
  outlet's reliability drifting) — not sharp enough to ticket until the
  initial source lists (tickets 01/02) exist.
- Any Thai-language quick-reference notes (e.g. key terms/phrases to
  recognize in Thai-language primary sources) — deferred until ticket 01
  shows how much the curated list actually leans on Thai-only sources.

## Out of scope

- Any code change to `kth/`, `kth_dr/`, the pipeline, or the dashboard —
  ruled out from the start; this map produces documentation only (see
  Destination). Not tracked as a closed ticket since it was never charted
  as one — stated here directly per the skill's guidance for boundaries
  fixed at scoping time.
- Automated news ingestion/scoring feeding `rank_score` or trade
  generation — this is exactly CLAUDE.md's existing "news sentiment" hard
  scope limit (`PROJECT_STRUCTURE.md §12`); this map does not reopen it.
