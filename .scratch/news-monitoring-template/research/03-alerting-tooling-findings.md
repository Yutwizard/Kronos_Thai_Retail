# Research findings: alerting/aggregation tooling for the curated sources

Resolves ticket `.scratch/news-monitoring-template/issues/03-alerting-tooling.md`,
using the source lists from ticket 01
(`research/01-set-sources-findings.md`, SET-listed `thai_equity`/`thai_index`
universe) and ticket 02 (`research/02-dr-sources-findings.md`, the 6 DR
underlyings) as input. All tooling claims below were checked live via
WebSearch/WebFetch on **2026-08-11**, not assumed from training data — see
inline citations of what was actually confirmed vs. what remains a search
snippet.

---

## 1. Does SET have a per-ticker email/alert subscription, beyond the dead RSS?

Ticket 01 already established `classic.set.or.th`'s RSS directory is gone and
`set.or.th`'s `/rss` paths 404. This ticket dug further for a different
subscription mechanism (account-based watchlist/alert) rather than RSS, and
found **three distinct SET-Group-affiliated apps/accounts, none of which is a
plain email or RSS push**:

| Mechanism | What it actually is | Per-ticker? | Push channel | Confidence |
|---|---|---|---|---|
| **WiSET** (`wiset` — "วิเศษ") app | SET's own newly-launched (2026) investor "super-app" — consolidates portfolio holdings across brokers/registrars ("My Wealth", via TSD e-Service), market news/statistics, and "important alerts." Confirmed via Google Play/App Store listings and Thai press coverage (themomentum.co, hoonvision.com) as an official SET Group product. | Its clearest alerting feature (dividend alerts) is tied to *actual holdings* recorded via TSD e-Service, not a free-standing watchlist of arbitrary tickers — could not confirm whether you can add a ticker you don't hold purely to get its news alerts. | Mobile push (app), not email/RSS | Medium — app existence and holdings-based alerts confirmed via multiple sources; pure-watchlist-without-holding capability unconfirmed, verify in-app |
| **Settrade App** (`settrade.com`'s own app, SET Group's brokerage-facing platform, distinct from WiSET) | Has a "Favorite list" + Notifications feature that pushes "SET news and company news of listed companies in their favorite list." Confirmed via App Store/Play Store listings. | **Yes** — favorite list is a plain add/remove ticker watchlist, not tied to holdings | Mobile push (app) | Medium-high — feature described consistently across both store listings; exact latency (real-time vs. digest) not confirmed |
| **SET Member account** (`member.set.or.th`) | A SET-wide login used across SET's web properties (SETSMART, WiSET, market pages) — "set up app and notifications" is listed as an account-management capability once logged in. | Unconfirmed whether this unlocks a *browser/email*-based per-ticker alert (as opposed to just gating the apps above) | Unclear | Low — surfaced only in a search snippet, not independently fetched; treat as "an account exists," not a confirmed alert feature |
| SET's website "watchlist/follow" widget (ข่าวหลักทรัพย์ที่ติดตาม, noted in ticket 01) | Logged-in-only follow button on the news page | Yes, browsing-session only | None confirmed (no email/push found) | Low (per ticket 01) |

**Bottom line: no email or RSS alert exists directly from `set.or.th`.** The
closest thing to "SET's own per-ticker alert" is the **Settrade App's
favorites-list push notifications** — it's SET Group's own platform (not a
third party), free, genuinely per-ticker (add/remove tickers freely, cheap to
reconfigure), and pulls both SET disclosures and company news. Its
limitation for this template is that it's a **mobile push channel**, not
something that lands in the same RSS reader as everything else in §2-4
below — so it works as a *standalone* daily-check habit (open the app,
scan today's top-10 favorites) rather than folding into one aggregation
point. WiSET is worth a follow-up spot-check once it matures, but is not
recommended as the primary mechanism yet given the holdings-based ambiguity.

## 2. One aggregation point: RSS reader + email-to-RSS bridge

The question of whether SETTRADE's RSS feeds and the DR-underlying
companies' email-alert signups (Sanofi, Novo Nordisk, Hermès — see ticket 02)
can land in one place has a concrete **yes**, verified this session:

**Recommended reader: Inoreader**, not Feedly, specifically because of the
email-newsletter feature:

- Inoreader's Free plan ($0/forever) includes **150 RSS feed subscriptions
  plus 20 "Newsletter Feeds"** — confirmed by directly fetching
  `inoreader.com/pricing` (not just a search snippet): each Newsletter Feed
  generates its own unique inbound email address; anything sent there is
  converted into feed items that mix into the same reading list as regular
  RSS, and can be filtered/tagged/pushed like any other feed. This is a
  **built-in email-to-RSS bridge** — no separate third-party service needed
  for the Sanofi/Novo Nordisk/Hermès IR email-alert signups from ticket 02.
- By contrast, **Feedly's Free plan explicitly excludes newsletters**
  (100 sources, 3 folders, but newsletter ingestion is Pro-only per Feedly's
  own 2026 pricing breakdown) — confirmed via search of Feedly's 2026
  pricing pages. Feedly would require its $6-7/mo Pro tier to do what
  Inoreader does for free, so Inoreader is the better default recommendation
  purely on cost.
- **Fallback / no-account alternative: Kill the Newsletter** (kill-the-newsletter.com)
  — confirmed live via direct fetch on 2026-08-11: free, no account
  registration required, MIT-licensed and self-hostable, generates a unique
  email address per feed and converts incoming mail to an Atom feed URL you
  can add to *any* RSS reader (including Feedly's free tier, since at that
  point it's "just RSS" to Feedly). One caveat surfaced in research: some
  publishers (notably Substack-hosted newsletters) block Kill the
  Newsletter's sending domain — not expected to be an issue for the
  corporate-IR mailing lists in scope here (Sanofi/Novo Nordisk/Hermès don't
  send via Substack), but worth knowing if a future source turns out to.

**Practical setup**: one Inoreader account, feeding from:
- SETTRADE's 6 FeedBurner RSS feeds directly (ticket 01) — note these are
  **broad topic feeds** (all research, market analysis, technical analysis,
  per-stock analysis, IPO analysis), not query-string-filterable by ticker,
  so treat them as a skim-and-scan source rather than something you can
  narrow to "just today's top-10," same limitation ticket 01 already flagged.
- Inoreader "Newsletter Feed" addresses used to sign up for Sanofi's
  "Sign up to receive email alerts," Novo Nordisk's "Sign up to Novo Nordisk
  News," and any other IR email-alert forms from ticket 02.
- Google Alerts, delivered as RSS (see §3) rather than email, so they also
  land in the same reader instead of a separate inbox.

This answers the map's open question directly: **yes, a single aggregation
point can realistically cover both the Thai-market RSS sources and the
international DR-underlying email-alert sources** — they're mechanically
different (RSS vs. email) but Inoreader's built-in bridge normalizes both
into one feed list. The Settrade App favorites (§1) remains the one channel
that stays outside this aggregation point, because it's app-push-only with
no RSS/email export found.

## 3. Google Alerts as fallback

Confirmed still functional in 2026 with **RSS delivery** (not just email) —
searched specifically for whether Google deprecated this, since it has
flip-flopped historically (pulled after Google Reader's 2013 shutdown,
restored later): current sources confirm the "Deliver to" dropdown still
offers "RSS Feed" as an option alongside email digest. **This is the piece
that unifies Google Alerts into the same Inoreader aggregation point from
§2** — set delivery to RSS instead of email, then subscribe the resulting
feed URL directly in Inoreader, no bridge needed.

Phrasing guidance, split by the ambiguity problem the ticket calls out:

**Thai tickers/companies — ambiguity risk is real and asymmetric:**
- The `.BK`-suffixed ticker itself (e.g. `"AOT.BK"`) is essentially
  unambiguous as a quoted exact-match phrase — few other things on the web
  are written that way — so ticker-as-query is low-noise and can be the
  entire alert for large, distinctively-named companies.
- The risk is companies whose **English name or ticker collides with a
  common word or acronym** (e.g. a ticker or brand fragment that's also a
  generic term) — Google Alerts guidance confirmed via research: use the
  quoted ticker/brand phrase **plus a disambiguating second term** — company
  suffix, "SET", "Bangkok", or the sector word (e.g.
  `"XXXX.BK" OR ("Company Full Name" "SET")`), and set the alert's Sources
  filter to "News" or "Finance" rather than "Everything," which drops a lot
  of generic-web noise. Since the exact set of top-10 names changes daily
  but the universe of 52 `thai_equity`/`thai_index` tickers is fixed and
  small, this per-ticker phrasing only needs to be worked out **once per
  ticker, not once per day** — set up all names that are plausible top-10
  candidates as standing alerts, and just skim whichever ones are live in
  today's list, rather than creating/deleting alerts daily.
- For Thai-language coverage specifically, Google Alerts supports a
  "Language" filter (settable to Thai) as a second axis to narrow a
  Thai-only-listed small-cap name that an English-only alert would miss
  entirely.

**DR underlying names — much lower ambiguity, per ticket 02's names:**
- Hermès, LVMH, Sanofi, Novo Nordisk are distinctive enough that a plain
  quoted company-name alert is low-noise on its own. L'Oréal and Ferrari are
  the two exceptions worth a disambiguator: "Ferrari" collides with the
  generic surname/adjective usage in some contexts (mitigate by pairing with
  `"RACE.MI"` or `"Borsa Italiana"` in an OR clause) and "L'Oréal" is
  distinctive but apostrophe/accent handling can fragment matches across
  sources that render it differently (`"L'Oreal"` vs `"L'Oréal"`) — alert on
  both spellings.
- Since the DR underlyings are a fixed set of 6 names (not a reshuffling
  pool the way the 52-ticker thai_equity universe partially is), these 6
  Google Alerts are a true one-time setup with near-zero ongoing
  reconfiguration cost — reinforcing that Google Alerts fits the "cheap to
  reconfigure" preference at both ends of the universe (add once, adjust
  rarely).

## 4. One habit or two?

**Recommend one aggregation point (Inoreader) feeding two visually-separated
folders**, not two entirely separate tools/habits:

- **Folder A — Thai-market**: SETTRADE's 6 RSS feeds + Google Alerts (RSS
  delivery) for each of the 52 `thai_equity`/`thai_index` tickers.
- **Folder B — DR underlyings**: Inoreader Newsletter Feeds subscribed to
  Sanofi/Novo Nordisk/Hermès IR alert signups + GlobeNewswire's Novo Nordisk
  organization feed (ticket 02 confirmed GlobeNewswire itself offers email
  alerts, which can also be routed through a Newsletter Feed the same way)
  + Google Alerts (RSS) for the 6 underlying names.

Reasons this is one habit with two folders rather than two separate tools:
- Both source sets reduce to the same two primitives — **native RSS** and
  **email-alert-via-Inoreader's-bridge** — so there's no technical reason to
  split tooling; splitting would only double the daily-check overhead the
  ticket is trying to eliminate.
- The map's own "layered cadence" design (daily quick-scan of today's
  top-10, from `kth/trading/trade_gen.py:371`) already treats Thai and DR
  names as one combined ranked list — a top-10 day could contain both SET
  equities and DR names simultaneously — so a reader view that can show
  "today's top-10 only" across both folders in one pass matches the actual
  daily task better than two separately-opened tools.
- The **one genuine exception is the Settrade App** (§1) — since it has no
  RSS/email export, it necessarily stays a second, separate touchpoint
  (open the app, glance at favorites) rather than folding into Inoreader.
  This is a real two-tool outcome, but scoped narrowly to "Inoreader for
  reading + Settrade App for the one push-notification channel SET Group
  offers," not a Thai-vs-international split.

## 5. Summary for the doc-assembly ticket (06)

**One-time setup** (per the "cheap to reconfigure" preference, most of this
is configure-once since both universes — 52 thai_equity/thai_index tickers,
6 DR underlyings — are fixed lists, not something reconfigured daily):

1. Create a free Inoreader account.
2. Add SETTRADE's 6 RSS feeds (URLs in ticket 01 / `settrade.com/th/rss`) to
   a "Thai-market" folder.
3. Create a Google Alert (RSS delivery, News/Finance source filter) for each
   of the 52 thai_equity/thai_index tickers, phrased as `"TICKER.BK"` alone
   for distinctive names, or `"TICKER.BK" OR ("Company Name" "SET")` for
   names that collide with common words; add each resulting RSS URL to the
   same "Thai-market" folder.
4. Create an Inoreader Newsletter Feed per DR-underlying company that offers
   an email-alert signup (confirmed for Sanofi, Novo Nordisk per ticket 02;
   check Hermès/L'Oréal/LVMH/Ferrari's IR pages too) and subscribe using the
   generated address; put these in a "DR underlyings" folder.
5. Create 6 Google Alerts (RSS delivery) for the DR underlying names, with
   the disambiguating OR-clauses noted in §3 for Ferrari and L'Oréal; add to
   the same "DR underlyings" folder.
6. Separately, install the Settrade App and add all 52 thai_equity tickers
   (SET doesn't list DRs as separately favoritable in confirmed research) to
   its Favorites list for push notifications — this is the one channel that
   stays outside Inoreader.

**Daily habit**: open Inoreader, filter/sort to unread items across both
folders, cross-reference against today's `get_top_ranked(10)` output —
skim only the items touching today's top-10 names — then separately glance
at the Settrade App's notification feed for the same names.

## Caveats / not fully resolved

- **WiSET's pure-watchlist (non-holdings) alerting capability is unconfirmed**
  — it's SET's own newest app (2026) and the strongest "official SET alert"
  candidate if it does support watchlisting names you don't hold, but this
  session couldn't confirm that distinction from published descriptions.
  Worth an in-app spot-check by a future session rather than assuming either
  way.
- **SET Member account's (`member.set.or.th`) alerting capability, if any,
  beyond gating the apps above, is unconfirmed** — surfaced only in a search
  snippet ("set up app and notifications"), not independently verified.
  Low priority to chase further given the Settrade App answer already covers
  the "per-ticker push from SET Group" need.
- **SETTRADE's RSS feeds are not per-ticker filterable** (confirmed — they're
  6 broad topic feeds, e.g. "all research," "individual stock analysis"
  covering all covered stocks, not one feed per ticker or a query-string
  filter option) — this was already flagged as a gap in ticket 01 and is
  reconfirmed here, not newly discovered.
- **Inoreader Newsletter Feed count (20 on Free) is a hard cap** — with 6 DR
  underlyings this isn't a near-term constraint, but if the doc later wants
  to add per-company IR alert signups for individual `thai_equity` names too
  (not just the 6 DRs), 20 could become binding; the fallback in that case
  is routing overflow companies through the free, uncapped Kill the
  Newsletter bridge instead and adding those Atom URLs as plain RSS feeds
  (which count against the 150 RSS cap, not the 20 newsletter cap).
- **Did not independently verify** Reuters/Bloomberg/FT/Boursorama's
  account-based email-alert mechanisms mentioned in ticket 02 beyond noting
  they exist and are subscription/account-gated (out of scope for a "cheap
  to reconfigure, free" recommendation — not pursued further here since
  Google Alerts + the IR-page alerts already give free coverage of the same
  underlying names).

## Addendum (2026-08-12): more free RSS sources, and a simpler alternative to Google Alerts

Follow-up research (user asked to broaden the global news-house/investment-site pool)
directly `WebFetch`-verified several more candidates:

- **Google News RSS search (`news.google.com/rss/search?q=...`) is a genuinely
  simpler alternative to the Google Alerts recommendation in §3 above** — it's a
  plain RSS URL with **no account/signup at all**, so it can be added straight to
  Inoreader without the "set delivery to RSS" configuration step Google Alerts
  needs. But **phrasing is more sensitive than Alerts**: a bare ticker query
  (`q="AOT.BK"`) returned stale, junk results (old static profile pages from
  2017-2022) on direct fetch-verification. Adding the **full company name** to the
  query (`q="Airports of Thailand" AOT`) fixed this — returned genuinely fresh,
  correctly Aug-2026-dated headlines. **Revised phrasing guidance for ticket 06:
  always include the company's full name in the query, not just the ticker/brand
  fragment**, for both the thai_equity universe and the DR underlyings. Given this
  is simpler than Google Alerts and covers the same need, recommend it as the
  **primary** fallback mechanism, with Google Alerts (§3) as a secondary option
  only useful for its extra Language/Sources filter controls that Google News RSS
  search doesn't expose as query parameters.
- **Yahoo Finance's per-ticker RSS** (`feeds.finance.yahoo.com/rss/2.0/headline?s=<TICKER>`)
  is a live, real mechanism — confirmed by its `lastBuildDate` updating on repeated
  fetches — and works well for the DR underlyings' home-market tickers (e.g.
  `SAN.PA` returned real dated items) and for large-cap `thai_equity` names (e.g.
  `PTT.BK` returned a real, dated LNG-negotiations article). **Coverage on the Thai
  side is patchy, though**: `AOT.BK` returned a structurally valid but completely
  empty feed at the same fetch time. Recommend trying this per-ticker across the
  52-name universe as a supplemental source (not a primary one to build the
  template around, since it can't be guaranteed for every name) — cheap to check
  once per ticker, since it's just a URL pattern with the ticker swapped in.
- **Nikkei Asia RSS** (`asia.nikkei.com/rss/feed/nar`) confirmed live — real
  current headlines on Asia-Pacific business/politics/tech, no publication dates in
  this particular feed variant. Not company- or Thailand-specific, but a reasonable
  addition to the macro/regional-context side of the daily reader (pairs with BoT
  releases from ticket 01) — terms of use restrict it to personal, noncommercial
  viewing, which fits this template's use case. **Note the ToS explicitly prohibits
  republication/redistribution** — fine for personal reading in Inoreader, would
  not be fine if the assembled doc or any future tooling redistributed its content.
- **CNBC's RSS (`cnbc.com/id/.../rss.html`) and Trading Economics' RSS
  (`tradingeconomics.com/rss/`) both returned HTTP 403 Forbidden** on direct
  fetch-verification — same bot-gating pattern already seen with Bangkok
  Post/Reuters/FT elsewhere in this map. Not usable for automated aggregation;
  could still be browsed manually, not worth building the template around.
- **PR Newswire's APAC RSS page** only exposes broad topic-category feeds (Energy,
  Health, etc.), not company- or Thailand-specific ones, and the actual feed URLs
  require clicking an interactive button rather than being linkable directly —
  low value for this use case, not pursued further.
- **StockTitan.net** appears to have no public per-ticker RSS (only a live-stream
  webpage and an internal JSON API not intended for public RSS consumption) — ruled
  out.

**Revised summary for ticket 06**: add Seeking Alpha's per-symbol feed (all 6 DR
tickers, see ticket 02's addendum) and Google News RSS search (both universes,
full-company-name phrasing) to the Inoreader setup steps in §5 above — both are
simpler to configure than the email-alert-bridge route since neither needs an
account. Yahoo Finance per-ticker RSS is worth a mention as an optional
supplemental check, with the explicit caveat that Thai-ticker coverage isn't
guaranteed per name.

## Addendum (2026-08-12): more sources checked, mostly negative results

Further digging (user asked to keep researching before moving to the grilling
tickets) directly `WebFetch`-verified a few more candidates:

- **Investing.com has no per-symbol RSS** — `investing.com/webmaster-tools/rss`
  confirmed to only offer broad topic/category feeds ("Stock Market News," "All
  News," "Analysis & Opinion," etc.), no ticker-level filtering. This resolves
  the ambiguity ticket 01 left open about Investing.com's alert mechanism —
  its per-symbol option is account-based push/email only, not RSS. Deprioritize
  it as an aggregation-point source; keep it only as a manual-browse macro
  cross-check per ticket 01.
- **Thai SEC (`sec.or.th`) could not be verified** — 403 Forbidden on two
  different pages, no RSS found via search. See ticket 01's addendum — added to
  the primary tier there as a browse-manually source (same treatment as BoT),
  not usable for automated aggregation here.
- **GlobeNewswire's general organization-search page** timed out on a broader
  re-check, but doesn't change the already-confirmed working pattern for Novo
  Nordisk specifically (see ticket 02's original research) — no update needed.

Net effect on the tooling recommendation: no changes to the core Inoreader setup
from this round — it mainly closes out previously-unconfirmed items with
negative (but useful) answers, so ticket 06 doesn't need to chase them further.
