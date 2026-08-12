# 03 - Recommend alerting/aggregation tooling for the curated sources

Type: research
Status: resolved
Blocked by: 01, 02 (both resolved — unblocked)

## Question

Given the source lists from ticket 01 (SET-listed equities) and ticket 02
(DR underlyings), recommend concrete tooling so the daily quick-scan
doesn't mean manually opening 10+ sites every night for whichever tickers
rank in today's top-10.

Investigate and recommend, matched against the actual sources those
tickets surfaced:

- SET's own alert/email subscription service for company disclosures (does
  it support per-ticker subscriptions? digest vs real-time?).
- RSS feeds where the curated sources publish one (aggregatable in a single
  reader).
- Google Alerts (or equivalent) as a fallback for sources without native
  feeds — how to phrase per-ticker queries to minimize noise given tickers
  like "AOT.BK" or company names that collide with common words.
- Whether a single aggregation point (RSS reader, email digest) can
  realistically cover both the Thai-market sources (ticket 01) and the
  international DR-underlying sources (ticket 02), or whether the template
  should recommend two separate habits.

Since the top-10 list reshuffles daily, prefer tooling that's cheap to
reconfigure per-ticker (e.g. saved searches) over one-time manual
subscriptions per company, where the two trade off.

## Answer

Full findings, verified live (2026-08-11):
`research/03-alerting-tooling-findings.md` (pulled onto `main` from the
throwaway `research/news-alerting-tooling` branch, commit `ca4e1cc`).

**SET's own alert:** no email/RSS exists on `set.or.th` itself (confirms
ticket 01's RSS-is-dead finding). Best available "SET Group per-ticker
alert": the **Settrade App**'s free Favorites-list push notifications —
genuinely per-ticker, but mobile-push-only, so it stays a separate
touchpoint rather than folding into an RSS reader. (WiSET, SET's newer
super-app, has alerts but they appear tied to actual portfolio holdings,
not a free watchlist — unconfirmed, flagged for future spot-check.)

**One aggregation point — recommended: Inoreader**, not Feedly. Inoreader's
free plan bundles 150 RSS feeds + 20 "Newsletter Feeds" (a built-in
email-to-RSS bridge, confirmed live via its pricing page) — this ingests
both SETTRADE's RSS feeds (ticket 01) *and* the DR-underlying companies'
IR email-alert signups (Sanofi, Novo Nordisk, etc., ticket 02) into one
reader. Feedly's free tier excludes newsletters. **Kill the Newsletter**
confirmed live as a free fallback bridge if the 20-newsletter cap is hit.

**Google Alerts:** confirmed still offers RSS delivery in 2026, so it
plugs into the same Inoreader reader with no extra bridge. Phrasing:
quoted `"TICKER.BK"` is low-noise for most Thai names; ambiguous
names need a disambiguating OR-clause + News/Finance source filter (+
Thai-language filter for Thai-only small caps). DR underlyings are mostly
unambiguous except Ferrari (pair with `"RACE.MI"`) and L'Oréal (alert both
spellings). Since both universes (52 tickers, 6 DR underlyings) are fixed
lists, this is a one-time setup, not daily reconfiguration.

**One habit, not two:** recommended one Inoreader account with two
folders (Thai-market / DR-underlyings) rather than separate tools, since
both reduce to the same RSS + email-bridge primitives and the top-10 list
can mix SET and DR names on any given day. The Settrade App remains the
one channel that stays outside Inoreader (no RSS/email export).

**Concrete setup steps and daily habit** are spelled out in the findings
file's §5, ready for ticket 06 to lift directly.

**Unresolved, flagged for a future session:** WiSET's non-holdings
watchlist capability, SET Member account's alerting beyond app-gating,
and whether Reuters/Bloomberg/FT/Boursorama's paid alert mechanisms are
worth adding (deprioritized — free coverage already exists via Google
Alerts + IR pages).

Status: resolved.

**Addendum (2026-08-12):** follow-up research verified more free sources.
**Google News RSS search** (`news.google.com/rss/search?q=...`) is simpler
than the Google Alerts route above — a plain no-signup RSS URL — and is
now the recommended **primary** fallback mechanism, promoted ahead of
Google Alerts (which stays useful only for its extra Language/Sources
filter controls). Critical phrasing correction found via direct testing:
a bare ticker query returns stale junk (verified — years-old static
pages); the query **must include the company's full name**, not just the
ticker, to return genuinely current results. **Seeking Alpha's per-symbol
RSS** (see ticket 02's addendum — `SNY`/`NVO`/`RACE`/`LVMUY`/`HESAY`/`LRLCY`)
should be added to the Inoreader "DR underlyings" folder — no
account/bridge needed, the easiest source in the whole map to wire up.
**Yahoo Finance's per-ticker RSS** works but has patchy Thai-side coverage
(confirmed live for `PTT.BK`, empty for `AOT.BK`) — worth a supplemental
per-ticker check, not a primary mechanism. **Nikkei Asia RSS** is a
reasonable macro/regional addition (ToS: personal use only, no
redistribution). **CNBC and Trading Economics RSS both returned HTTP 403**
(bot-gated, same pattern as Bangkok Post/Reuters/FT) — not usable for
automation. PR Newswire APAC and StockTitan don't offer usable
company-specific RSS — ruled out. Full detail appended to
`research/03-alerting-tooling-findings.md`.

**Second addendum (2026-08-12):** Investing.com confirmed to have no
per-symbol RSS (topic-only feeds) — deprioritized as a manual-browse-only
macro cross-check. Thai SEC and a broader GlobeNewswire re-check yielded
no new tooling changes (see tickets 01/02 addenda). No changes to the
core Inoreader recommendation.
