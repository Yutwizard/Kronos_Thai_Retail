# 01 - Curate tiered news sources for SET-listed equities

Type: research
Status: resolved

## Question

Produce a tiered, curated list of reliable news/information sources for
monitoring SET-listed Thai equities (the `thai_equity`/`thai_index`
universe in `kth/data/universe.py`) — the kind of names that show up in
`get_top_ranked(10)` (`kth/trading/trade_gen.py:371`).

Tier as:

- **Primary** — official/regulatory: SET's own disclosure portal
  (setsmart/SET announcements), Bank of Thailand releases, company investor
  relations pages/filings. These are authoritative by construction.
- **Secondary** — reputable press interpreting/reporting on primary events,
  split by language:
  - Thai-language (e.g. กรุงเทพธุรกิจ, ประชาชาติธุรกิจ, or equivalents —
    verify current, actively-published outlets rather than assuming names
    from training data are still active).
  - English-language (e.g. Bangkok Post Business, The Nation Thailand
    Business, Reuters/Bloomberg Thailand coverage, SET's English disclosure
    feed).

For each source, record: name, URL, primary/secondary tier, language,
what kind of information it's best for (e.g. "company filings", "sector
news", "macro/SET-index commentary"), and whether it publishes an
RSS/email-alert mechanism (feeds ticket 03).

Flag explicitly if any commonly-cited source turns out to be defunct,
paywalled without a workable free tier, or unreliable on verification —
don't just assume a name from training knowledge is still live; check.

## Answer

Full findings, every source verified live via web search/fetch on
2026-08-11: `research/01-set-sources-findings.md` (pulled onto `main` from
the throwaway `research/set-news-sources` branch, commit `55f32ea`).

**Primary tier:** SET News & Announcements (EN + TH — the master
disclosure feed, filterable by ticker), SET Market Alerts (halts/
suspensions/caution-list — the "something's structurally wrong" signal),
SET's periodic-disclosure rules page (reference, not a feed), Bank of
Thailand News & Media (rate decisions, monthly economic conditions),
company IR pages (no central SET directory exists — reach via the
company's own site or a link from its SET news page). Noted `SETLink` is
a company-facing filing system, not investor-facing.

**Secondary Thai:** SETTRADE.com aggregator (has a live RSS directory,
6 feeds — good fallback given SET's own RSS gap), Thunhoon, Kaohoon,
efinanceThai, Bangkok Business News, Prachachat Business.

**Secondary English:** Bangkok Post Business (site fine for humans, but
its RSS/automated access is now bot-toll-gated via TollBit — HTTP 402 —
don't assume it's scriptable), The Nation Thailand Business, Kaohoon
International, Investing.com's Thailand SET pages, Reuters/Bloomberg Asia
markets (macro-only, no Thailand-specific depth).

**Key gap flagged for ticket 03 (alerting/tooling):** SET's own RSS feed
is dead — the old `classic.set.or.th` RSS hub no longer resolves at all,
and the new site has no working `/rss` path. SETTRADE's RSS directory is
the best available fallback for automatable aggregation.

**Ruled out/deprioritized:** Thairath and other general-interest Thai
dailies (lower signal-density than finance-specialist outlets, though not
defunct). efinanceThai's old frame-based news URL is dead (410) — use
`AllLatestNews.aspx` instead.

**Suggested split for ticket 06:** daily quick-scan = SET News &
Announcements filtered to today's top-10 + SETTRADE aggregator/RSS + one
Thai outlet + one English outlet; weekly/deeper review = BoT releases +
SET Market Alerts + IR pages for any newly-entered top-10 name.

Status: resolved.

**Addendum (2026-08-12):** follow-up research found a real gap — **Thai SEC
(สำนักงาน ก.ล.ต., `sec.or.th`)** is a distinct regulator from SET (tender
offers, prospectuses, insider-transaction filings), missed in the original
pass. Add to the primary tier alongside BoT — no RSS found and the site
403-blocked automated fetch, so it's browse-manually-only, but a real red
flag (e.g. an SEC enforcement action) wouldn't necessarily surface on SET's
own news page. Also noted: many company IR pages are hosted on the shared
`irplus.in.th` platform (`<company>.irplus.in.th`) — useful as a search
heuristic given there's no central IR-page directory, not a new source in
itself. Full detail appended to `research/01-set-sources-findings.md`.
