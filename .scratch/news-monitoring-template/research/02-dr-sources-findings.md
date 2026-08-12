# 02 — DR underlying news source curation: findings

Research for `.scratch/news-monitoring-template/issues/02-dr-source-curation.md`.
Produced on throwaway branch `research/dr-news-sources`; a future session should
pull these findings into the ticket's `## Answer` section on main.

Scope confirmed against `kth_dr/universe_dr.py` + `data/dr/mapping.json`
(`_meta.status`: "reviewed", 36/37 DR candidates verified 2026-07-15/16) — the
6 DRs named in CLAUDE.md all resolve to verified, currently-tracked mappings:

| Underlying | Display name | Home exchange | Currency | DR ticker (issuer) |
|---|---|---|---|---|
| `RMS.PA` | Hermès International | Euronext Paris (FR) | EUR | `HERMES80.BK` (KTB) |
| `OR.PA` | L'Oréal | Euronext Paris (FR) | EUR | `LOREAL80.BK` (KTB) |
| `MC.PA` | LVMH | Euronext Paris (FR) | EUR | `LVMH01.BK` (BLS / Bualuang) |
| `SAN.PA` | Sanofi | Euronext Paris (FR) | EUR | `SANOFI80.BK` (KTB) |
| `RACE.MI` | Ferrari | Borsa Italiana / Euronext Milan (IT); also dual-listed NYSE as `RACE` | EUR | `FERRARI80.BK` (KTB) |
| `NOVO-B.CO` | Novo Nordisk | Nasdaq Copenhagen (DK) | DKK | `NOVOB80.BK` (KTB) |

Grouped below by home exchange per the ticket's suggestion, since 4 of the 6
(Hermès/L'Oréal/LVMH/Sanofi) share one Euronext Paris source set. All URLs
below were checked live in this session (August 2026) via `WebFetch`/`WebSearch`
except where explicitly flagged **not independently verified** — those are
long-established, widely-known outlets that either block automated fetch
(paywall/bot-protection, e.g. Reuters/Bloomberg/FT) or where a specific stable
URL could not be pinned down in this session; treat those as lower-confidence
and spot-check manually before relying on them operationally.

---

## Group 1 — Euronext Paris: Hermès, L'Oréal, LVMH, Sanofi

### Primary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| AMF (Autorité des marchés financiers) BDIF regulated-disclosure database | https://bdif.amf-france.org/en | FR/EN | Authoritative regulated filings for all 4 (French securities regulator, all are AMF-supervised Euronext Paris issuers) | None found | Yes — AMF's own page (amf-france.org) fetch-confirmed live 2026, links directly to bdif.amf-france.org/en as "Decisions and financial disclosures database" |
| Hermès — company IR | https://finance.hermes.com/en/investors/ | FR/EN | Press releases, financial calendar, URD | "Receive our financial information" subscribe option present | Yes — fetch-confirmed live, showing H1 2026 revenue (€8,163m) and Q3 2026 calendar entry (Oct 22 2026) |
| L'Oréal — company IR | https://www.loreal-finance.com/eng/news-releases | FR/EN | Press releases, financial calendar | No RSS found on this page | Yes — fetch-confirmed live, showed July 29 2026 H1 results and July 7 2026 Gucci-license release |
| LVMH — company IR | https://www.lvmh.com/en/press and https://www.lvmh.com/en/investors/investors-and-analysts | FR/EN | Press releases, publications, financial calendar | Not confirmed (page too JS-heavy to fetch) | Partial — URL structure confirmed to exist via search (2025/2026-dated calendar and publications pages indexed); direct WebFetch timed out twice (site appears client-rendered/slow) — **verify manually in a browser before relying on it** |
| Sanofi — company IR | https://www.sanofi.com/en/investors | FR/EN | Press releases, financial calendar, regulatory filings | Yes — explicit "Sign up to receive email alerts" | Yes — fetch-confirmed live, showed Aug 4 2026 and July 30 2026 dated releases |

Note on Les Echos ownership: Les Echos is owned by LVMH's parent group (Bernard
Arnault) — still a reputable financial daily, but worth knowing when judging
independence of LVMH coverage specifically.

### Secondary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| Les Echos (Finance/Marchés) | https://www.lesechos.fr/finance-marches | FR | Daily French financial press covering all 4 CAC 40 names | Not checked | Partial — WebFetch blocked by site (bot protection); confirmed as a live, actively-publishing outlet via search results (referenced by other live pages, e.g. a dated July 28 2026 Boursorama piece on LVMH cites the same market moment) — **spot-check manually** |
| La Tribune (Bourse) | https://www.latribune.fr | FR | French financial press, second-tier alternative to Les Echos | Not checked | Not independently verified this session — search returned only generic/background results, no live dated article confirmed. **Lower confidence — verify before relying on it** |
| Boursorama (Bourse actualités) | https://www.boursorama.com/bourse/actualites | FR | Free aggregator of French-listed company + market news, has account-based alerts | Account-based alerts available (not free-tier RSS) | Yes — a July 28 2026-dated LVMH article was returned directly in search results |
| Reuters (company news) | https://www.reuters.com/markets/companies/MC.PA (swap ticker: RMS.PA, OR.PA, SAN.PA) | EN | English wire coverage, fast on material events | Reuters offers email/app alerts (account required) | **Not independently verified** — WebFetch blocked by site; Reuters is a globally recognized live wire service, but this session could not confirm the specific page renders — spot-check manually |
| Bloomberg (quote/profile) | https://www.bloomberg.com/quote/MC:FP (swap ticker per name) | EN | English wire, deep company profile + news | Bloomberg terminal/app alerts (subscription) | Partial — WebFetch blocked (paywall); confirmed live via search-indexed quote/profile pages with current data |
| Financial Times (company search) | https://www.ft.com/companies | EN | English wire, strong European corporate coverage | FT myFT alerts (subscription) | **Not independently verified** — WebFetch blocked (paywall); well-known live outlet, spot-check manually |

---

## Group 2 — Ferrari (`RACE.MI`, Borsa Italiana/Euronext Milan; dual-listed NYSE `RACE`)

### Primary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| CONSOB-authorized regulated-information storage (eMarket SDIR/STORAGE, operated by Teleborsa) | https://www.emarketstorage.it/home/homepage.en.htm (note: `.com` 301-redirects to `.it`) | IT/EN | Official Italian regulated-disclosure filings (CONSOB Art.113-ter authorized mechanism) | Not confirmed | Partial — the `.com`→`.it` redirect and CONSOB's own authorization of this mechanism were confirmed live (consob.it lists it under "centralized storage mechanisms for regulated information"); the specific homepage path 404'd on direct fetch — **use CONSOB's own list page (consob.it) to find the current entry URL rather than guessing the homepage path** |
| Ferrari corporate IR | https://www.ferrari.com/en-EN/corporate/investors and /press-releases | EN/IT | Press releases, results, stock info | Not confirmed | Partial — URL confirmed to exist (301-redirects from corporate.ferrari.com/en/investors), and search snippets describe live IR content (events, results, stock info), but WebFetch returned blank content on repeated attempts (heavy client-side rendering) — **verify manually in a browser** |
| SEC EDGAR — Ferrari N.V. (foreign private issuer, NYSE `RACE`) | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=ferrari | EN | 20-F/6-K regulatory filings, useful cross-check since Ferrari is also NYSE-listed | EDGAR filing-alert email service exists | Yes — SEC EDGAR is a long-standing, definitively live government system (not separately fetched this session but not in question) |

### Secondary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| Il Sole 24 Ore (Mercati) | https://mercati.ilsole24ore.com/azioni/borsa-italiana/dettaglio-completo/RACE.MI | IT | Leading Italian financial daily; price + quote context | Not checked | Yes — fetch-confirmed live with an Aug 11 2026-dated intraday price move (-0.79%, €352.85); note the page's "Ultime notizie" module skewed toward generic market headlines rather than Ferrari-specific stories on the day checked — pair with a direct site search for company-specific pieces |
| MilanoFinanza | https://www.milanofinanza.it/quotazioni/dettaglio/ferrari-2ae106d | IT | Second major Italian financial daily | Not checked | Yes — confirmed live via search snippet showing current intraday price data (€355.7, session high/low) |
| Reuters/Bloomberg/FT | (see Group 1 URLs, swap ticker to RACE.MI / RACE) | EN | English wire coverage | Subscription-based | Same caveats as Group 1 — not independently fetch-verified this session, but well-known live outlets |

---

## Group 3 — Novo Nordisk (`NOVO-B.CO`, Nasdaq Copenhagen)

### Primary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| Novo Nordisk — company IR / financial results | https://www.novonordisk.com/investors/financial-results.html | EN/DA | Company announcements, quarterly results, financial calendar | Yes — explicit "Sign up to Novo Nordisk News" email-alert service for press releases, trading announcements, material news | Yes — fetch-confirmed live, Q2 2026 (Aug 4 2026) and Q1 2026 (May 6 2026) dated results, Q3 2026 calendar entry (Nov 4 2026) |
| GlobeNewswire — Novo Nordisk regulatory-announcement distributor | https://www.globenewswire.com/en/search/organization/Novo%20Nordisk%20A%2FS | EN | Novo Nordisk's chosen wire for exchange-regulatory announcements (insider trading notices, material news) | GlobeNewswire offers email alerts | Yes — an Aug 6 2026-dated "Trading in Novo Nordisk shares by board members..." release found directly in search results |
| SEC EDGAR — Novo Nordisk A/S (ADR `NVO`, NYSE) | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=novo+nordisk | EN | 20-F/6-K filings, cross-check since it also trades as a NYSE ADR | EDGAR filing-alert email service | Yes — same long-standing EDGAR system as above |
| Nasdaq Copenhagen exchange-level company-news/regulated-announcement feed | (exact current URL not pinned down this session — Nasdaq Nordic's "Companynews" service structure has changed before) | EN/DA | The exchange's own regulated-announcement feed, distinct from the company's self-published IR page | Unknown | **Not verified this session** — flagged for follow-up; do not cite a specific URL until confirmed live |

### Secondary

| Source | URL | Language | Best for | RSS/alerts | Verified live |
|---|---|---|---|---|---|
| Børsen | https://borsen.dk | DA | Leading Danish business daily | Subscription-based alerts | **Not independently verified** — WebFetch blocked by the site on two attempts (likely bot-protection/paywall); Børsen is a well-known, definitionally live major Danish outlet — spot-check manually |
| DR (Danmarks Radio) — Penge (business desk) | https://www.dr.dk/nyheder/penge | DA | Free, public-broadcaster business coverage | Not checked | Yes — fetch/search confirmed live with a specific dated Novo Nordisk stock-reaction article ("Novo-aktien får hård medfart på børsen efter 'pænt regnskab'") |
| Berlingske Business | (URL not confirmed) | DA | Secondary Danish business coverage | Not checked | **Not verified this session** — search returned no live, dated Berlingske Business article about Novo Nordisk; lower confidence than Børsen/DR — verify manually or drop if it can't be confirmed |
| Reuters/Bloomberg/FT | (see Group 1 URLs, ticker `NVO` / `NOVO-B.CO`) | EN | English wire coverage | Subscription-based | Same caveats as Group 1 |

---

## SET's own disclosure channel — is there DR-specific news distinct from home-market news?

**Short answer: yes, but it's administrative/mechanical, not a substitute for
home-market news monitoring.** Two distinct things live on the SET side:

1. **Per-DR issuer product pages** (KTB's `krungthai.com` for 5 of the 6 —
   Hermès/L'Oréal/Sanofi/Ferrari/Novo Nordisk — and BLS's `bualuang.co.th` for
   LVMH01) carry the DR's own factsheet and, per SET's DR FAQ, the issuer is
   obligated to mirror underlying-affecting news here and on SET's own
   channel. Confirmed live examples:
   - `https://krungthai.com/th/content/depositary-receipt/stock-dr/hermes80` (Thai-language, fetch/search-confirmed live)
   - `https://www.bualuang.co.th/en/financial-service/inav-lists/dr/dr01-inav/lvmh01` (English, fetch/search-confirmed live)
   These are **ratio/conversion/corporate-action mirrors**, not original
   reporting on the underlying business — useful as a DR-mechanics sanity
   check (e.g. "did the ratio change"), not as a news source about Hermès,
   Sanofi, etc.

2. **SET's own DR quote pages** (e.g.
   `https://www.set.or.th/en/market/product/dr/quote/HERMES80/price`,
   mirrored on `settrade.com/th/equities/dr/quote/hermes80/overview`) —
   both fetch-confirmed live — do **not** carry a dedicated news/disclosure
   tab. Their tabs are Price / Rights & Benefits / DR Profile only.

3. **SET's "Introduction to DR" FAQ**
   (`https://www.set.or.th/en/market/product/dr/introduction`, fetch-confirmed
   live) states that when the underlying has price/rights-affecting news, "the
   DR issuer must disclose information to investors through SET's channel as
   well as the issuer's website," and that DR issuers request SET display the
   same XD/H/SP trading signs as the underlying carries. So the obligation
   exists, but in practice it manifests as same-day sign-mirroring plus the
   issuer-page factsheets in (1) — not a separately readable DR-news article
   feed.

4. **SET's general newsroom** (`set.or.th/en/market/news-and-alert/news`)
   does separately publish **market-structure circulars specifically about
   DR products as an asset class** — confirmed live example: "SET to extend
   trading hours for depositary receipts, starting May 6"
   (`https://www.set.or.th/en/market/news-and-alert/newsdetails?id=95921400&symbol=SET`,
   dated April 28, 2025, fetch-confirmed live), which explicitly points readers
   to `www.set.or.th/dr` for more DR-product information. This is SET talking
   about the DR *product/market mechanics* (trading hours, new listings), not
   about Hermès/Ferrari/Novo Nordisk's business — still worth knowing about
   since it can affect when/how a DR is tradable, but it is not underlying
   company news either.

**Recommendation for the doc this feeds into:** include the per-DR KTB/BLS
issuer product pages as a low-frequency "DR-mechanics check" (ratio/corporate
action only), and SET's general newsroom as an even-lower-frequency check for
DR-product-wide changes (trading hours, new DR listings) — clearly separated
from, and not a replacement for, the Primary/Secondary home-market source
tables above, which remain the actual news-monitoring habit.

---

## Addendum (2026-08-12): Seeking Alpha per-symbol RSS — cross-cutting all 6 underlyings

Follow-up research (prompted by user request to look for more global-investment-site RSS)
found a genuinely valuable source this ticket missed: **Seeking Alpha's per-symbol RSS
feed**, `https://seekingalpha.com/api/sa/combined/<TICKER>.xml` — free, no signup, and
directly `WebFetch`-confirmed live on 2026-08-12 for all 6 underlyings via their US
OTC/ADR/NYSE tickers:

| Underlying | Seeking Alpha ticker | Confirmed content (2026-08-12 fetch) |
|---|---|---|
| Sanofi | `SNY` | Q2 earnings call presentation, FDA/regulatory news, dividend analysis — items dated Aug 2026 |
| Novo Nordisk | `NVO` | Q2 earnings, GLP-1 competitive coverage — items dated Aug 2026 |
| Ferrari | `RACE` | Q2 earnings call transcript/presentation, EPS beat, EV news — items dated Aug 2026 |
| LVMH | `LVMUY` | Q2 earnings call presentation, valuation analysis — items dated Jul 2026 |
| Hermès | `HESAY` | Q2 earnings call transcript, EPS/revenue, analyst commentary — items dated Jul 2026 |
| L'Oréal | `LRLCY` | Q2 earnings call transcript/presentation, conference coverage — items dated Jul 2026 |

Unlike the Group 1-3 tables above (which are mostly primary regulatory/IR + regional
press, several flagged low-confidence due to JS-heavy sites or bot-blocking), this is
a **single, uniform, directly-fetchable RSS mechanism that covers all 6 names** with
30+ items each spanning roughly the trailing year — earnings transcripts, analyst
articles, and news briefs mixed together. It should be treated as a **secondary-tier,
English-language, cross-cutting supplement** to the per-exchange tables, not a
replacement for the primary regulatory/IR sources (Seeking Alpha itself aggregates
from and comments on those primary events, it isn't the primary source).

Practical note for ticket 06: this is the single easiest source in this entire ticket
to actually plug into an RSS reader — no email-alert signup, no bridge service, no
JS-rendering problem, just a stable URL per ticker.

**Also resolved this pass:** the "exact current URL for Nasdaq Copenhagen's own
exchange-level regulated-announcement feed" flagged as unconfirmed in Group 3 above
— found and `WebFetch`-confirmed: `subscribe.news.eu.nasdaq.com/rss` is real and live,
but it is **not company-filterable**. It only offers broad category feeds ("Nasdaq
Europe Main Markets Notices," "First North Notices," "Exchange and IT Notices," "News
Releases") covering Copenhagen/Stockholm/Helsinki/Iceland together — Novo Nordisk's
regulated announcements would appear mixed into "Main Markets Notices" alongside every
other Nordic large-cap, not as a filterable single-company feed. Useful as a broad
regulatory catch-all if the reader can tolerate the noise, but not recommended as a
Novo-Nordisk-specific source — GlobeNewswire (above) remains the better company-specific
option.

---

## Sources not fully verifiable this session (follow-up list)

- LVMH's own `lvmh.com` IR/press pages (URL structure confirmed via search,
  but WebFetch could not render the page directly — likely heavy client-side
  JS)
- Ferrari's own `ferrari.com` corporate/investors pages (same symptom — 301
  redirect confirmed, but WebFetch returned blank content)
- La Tribune's live bourse coverage (no dated article confirmed this session)
- Børsen's homepage (WebFetch blocked by the site both attempts)
- Berlingske Business coverage of Novo Nordisk specifically (no live article
  found this session — may need a different query or direct site visit)
- The exact current URL for Nasdaq Copenhagen's own exchange-level
  regulated-announcement feed for Novo Nordisk (distinct from the company's
  self-published IR page)
- Reuters, Bloomberg, and FT company pages generally — all block automated
  `WebFetch` (paywall/bot-protection), so liveness here rests on their
  well-established reputations rather than a direct fetch in this session
