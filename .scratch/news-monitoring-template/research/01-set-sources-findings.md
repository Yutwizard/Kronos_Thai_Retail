# Research findings: tiered news sources for SET-listed equities

Resolves ticket `.scratch/news-monitoring-template/issues/01-set-source-curation.md`.
Scope: `thai_equity`/`thai_index` universe only (`kth/data/universe.py`) — the
names that can appear in `get_top_ranked(10)`. DR underlyings are ticket 02,
out of scope here.

Verification method: every source below was checked live via web search and/or
direct fetch on **2026-08-11**. Note: 2026-08-11 is a Thai public holiday
(HM Queen Sirikit's Birthday / Mother's Day), so a couple of Thai-language
sites rendered a holiday banner on their homepage instead of the normal news
grid on first fetch — this reflects the holiday, not a defunct site; each such
case was re-confirmed via a dated article/search hit below.

---

## Primary tier — official / regulatory

These are authoritative by construction: the regulator/exchange itself, the
central bank, or the company's own filings.

| Name | URL | Language | Best for | RSS/alert |
|---|---|---|---|---|
| SET News & Announcements (English) | https://www.set.or.th/en/market/news-and-alert/news | EN | The master feed of company disclosures/material events, filterable by ticker, news type (earnings, corporate actions, etc.), and date range. This is the single most important primary source — it's where `SETLink` submissions (below) actually surface publicly. | No working RSS found (see Caveats — the old `classic.set.or.th` RSS directory is gone). Page has a "watchlist/follow" (`ข่าวหลักทรัพย์ที่ติดตาม`) feature for logged-in users but no confirmed email/RSS push. |
| SET News & Announcements (Thai) | https://www.set.or.th/th/market/news-and-alert/news | TH | Same content as above, Thai-language UI (some disclosures are Thai-only, esp. from smaller-cap issuers). | Same as above. |
| SET Market Alerts | https://www.set.or.th/en/market/news-and-alert/market-alerts | EN/TH | Trading halts/suspensions/pauses, dynamic price-band triggers, cash-balance-only designations, caution measures, auditor's-opinion flags — the "something is structurally wrong with this stock" signal, distinct from routine disclosure news. | No confirmed RSS; browse or call SET Contact Center (+66 2009 9999). |
| SETLink | https://www.setlink.set.or.th/main | — | **Not a public browsing tool.** This is the electronic system listed companies use to *file* disclosures/financials with SET (per SET circular Bor.Jor.(Wor.) 5/2012 — hard-copy filing has been abolished, SETLink is the sole submission channel and counts as simultaneous SEC filing). Useful to know the term exists (you'll see "filed via SETLink" in secondary-press coverage) but the investor-facing surface is the News & Announcements pages above, not SETLink itself. | N/A (company-facing filing system) |
| SET Periodic Disclosure rules page | https://www.set.or.th/en/listing/listed-company/simplified-regulations/disclosure/periodic-disclosure | EN | Reference page explaining *when* companies must disclose what (audited annuals within 2-3 months, reviewed quarterlies within 45 days, MD&A) — useful for calibrating "is this filing on time or a red flag" rather than a news feed itself. | N/A |
| Bank of Thailand — News & Media | https://www.bot.or.th/en/news-and-media/news.html | EN (Thai mirror at `/th/...`) | Monthly "Economic and Monetary Conditions" press releases, Monetary Policy Committee rate decisions, and BOT measures (e.g. relief programs) — the macro/rate backdrop that moves the whole SET, especially banks/financials. | No RSS or email-subscription mechanism found on the site; BOT does list social channels (Facebook/X/YouTube/Instagram/LINE) as an alternative push channel. |
| Company investor-relations (IR) page | (varies per ticker — no central directory) | Varies (most large caps publish EN+TH) | Primary-source filings, presentations, and press releases straight from the company. SET provides listed companies a free/paid "IR Website" widget service (`https://www.set.or.th/en/services/ir-website`) that many issuers embed, but **there is no SET-hosted directory of company IR URLs** — you have to go to the company's own corporate site (typically `ir.<company>.com` or a `/investor-relations` path) or find it linked from that company's SET news page. | Varies by company; many large-cap IR sites do offer their own email-alert signup. |

## Secondary tier — press

### Thai-language

| Name | URL | Best for | RSS/alert |
|---|---|---|---|
| SETTRADE.com news portal | https://www.settrade.com/th/news-and-articles/news/main | Aggregator front-end (by the SET Group itself) pulling from Bangkok Post, efinanceThai, Businesstoday, SET, Thairath, TNN Online and others, filterable by outlet. Good single stop for a daily Thai-language scan. | **Yes — live RSS directory at https://www.settrade.com/th/rss**, six FeedBurner-hosted feeds: IAA analyst-consensus, all research, market-condition analysis, technical analysis, per-stock analysis, IPO analysis. Free for personal non-commercial use per their terms. |
| ทันหุ้น (Thunhoon) | https://thunhoon.com/ | Self-described "investment newsroom" — equities, funds, insurance, fixed income, macro, sector rotation/earnings analysis, morning briefs. Confirmed live and actively publishing. | No RSS/alert found on-site; social presence on X (`@thunhoon1`) and Instagram (`@thunhoon.news`) as an informal push channel. |
| ข่าวหุ้น / Kaohoon (Thai) | https://www.kaohoon.com/ | Long-running Thai stock-market news brand ("independent voice of the capital market"); confirmed live via Google Play app listing and site nav. Parent of the English `kaohooninternational.com` (see below). | Has a mobile app (Kaohoon, Google Play) pushing real-time notifications; no confirmed web RSS. |
| efinanceThai | https://www.efinancethai.com/ (news list: `https://www.efinancethai.com/LastestNews/AllLatestNews.aspx`) | Real-time-oriented stock data/news site running since 2001; daily stock-news summaries, per-stock analysis, and the `efin StockPickUp` desktop terminal used by several Thai brokerages (e.g. bundled by Krungsri Securities, บัวหลวง). | No RSS confirmed; has a paid desktop terminal product with its own alerting. **Caveat:** the old direct-news-frame URL (`LastestNewsFrame.aspx`) returned HTTP 410 Gone — use `AllLatestNews.aspx` or the homepage instead, the frame-based URL scheme is retired. |
| กรุงเทพธุรกิจ (Bangkok Business News) — Finance section | https://www.bangkokbiznews.com/finance | Confirmed live, dated same-day articles (checked 2026-08-11, Thai Buddhist-calendar-dated): SET close recaps, company earnings (e.g. TCAP, WHAUP, WHA), broker sector calls. Good for company-specific and sector-level Thai coverage. | Not confirmed on the fetched page; not investigated further (lower priority — SETTRADE aggregates it). |
| ประชาชาติธุรกิจ (Prachachat Business) — Finance section | https://www.prachachat.net/finance | Confirmed live with current 2026-dated articles (SET foreign-roadshow coverage, SME/finance-expo news). Broader business/finance/economy/political-economy angle than pure stock-tips outlets — useful for the macro-adjacent stories around a name (regulatory, trade-policy). | Not confirmed; site has active Facebook (`PrachachatOnline`), X (`@prachachat`), YouTube presence as informal push channels. |

### English-language

| Name | URL | Best for | RSS/alert |
|---|---|---|---|
| Bangkok Post — Business | https://www.bangkokpost.com/business | Thailand's most established English-language business desk — stocks, investment, economy. Confirmed the section exists and is actively maintained via search indexing. | **Caveat (see below): could not verify — automated access to both the section and its RSS feed (`/rss/data/business.xml`) is now gated.** Recommend manual browser access only. |
| The Nation Thailand — Business | https://www.nationthailand.com/business | Confirmed live with same-day dated headlines (checked 2026-08-11): baht moves, FTA trade data, corporate-closure trend stories. Good English alternative to Bangkok Post, decent macro/company mix. | General RSS index exists at `https://www.nationthailand.com/rss` but no business-specific feed was visible in that page's content; not fully confirmed. |
| Kaohoon International | https://www.kaohooninternational.com/thailand | English arm of Kaohoon; confirmed live, dated 2026-08-11 content — SET Index close, company earnings (e.g. IRPC 2Q26), M&A news (Minor Food/Bonchon). Good if you want Thai-market depth in English without relying solely on the two legacy broadsheets. | No RSS confirmed; has "Trending News" module but no subscription mechanism surfaced. |
| Investing.com — Thailand SET Index News | https://uk.investing.com/indices/thailand-set-news (analysis/opinion variant: https://www.investing.com/indices/thailand-set-opinion) | International-investor framing of the SET index — decent for a quick sanity check against how foreign/global-macro desks are reading Thai equities, index-level technicals. Confirmed live via search (real-time SET Index quote + dedicated news/opinion pages indexed). | Investing.com offers account-based email/push price alerts (not a public RSS) — out of scope to verify further here, covered by ticket 03 (alerting/tooling). |
| Reuters / Bloomberg — Asia markets coverage | reuters.com/markets/asia , bloomberg.com/quote/SET:IND | Global wire-service coverage of the SET index and baht as part of broader Asia-markets reporting — useful for macro/FX context (e.g. a Fed decision or China data print moving the whole board) but **not** a dedicated Thailand vertical with company-level depth. Confirmed both maintain live SET Index/SET50 quote pages. | Standard wire-service subscription/terminal products; no free dedicated Thailand RSS identified. |

---

## Caveats / sources ruled out or downgraded

- **`classic.set.or.th` (old SET RSS directory) is defunct.** Search results
  still surface `https://classic.set.or.th/th/rss/rss_p1.html` as SET's RSS
  hub, and general web knowledge would assume it still works — but the
  `classic.set.or.th` hostname **no longer resolves at all** (DNS failure on
  direct fetch, 2026-08-11). SET appears to have decommissioned the "classic"
  site entirely during its redesign to `www.set.or.th`. The new site's
  `/th/rss` and `/en/rss` paths both 404. **No working SET RSS feed was found
  as of this research** — this should be flagged for ticket 03
  (alerting/tooling) as a gap, not assumed solved.
- **Bangkok Post — automated/RSS access appears gated as of 2026-08-11.**
  Both `https://www.bangkokpost.com/business` and its RSS feed
  (`/rss/data/business.xml`) now 307-redirect to a `tollbit.bangkokpost.com`
  subdomain, and the RSS endpoint there returned **HTTP 402 Payment
  Required**. TollBit is a commercial service publishers use to charge
  automated/AI crawlers for content access — this looks like a bot-toll
  gate rather than a full reader paywall, and the section almost certainly
  still renders normally for a human in an ordinary browser (it's Bangkok
  Post's flagship business vertical, not something they'd pull down). But
  **do not assume the RSS feed is usable for any future automated tooling**
  (ticket 03) without re-checking — as of this research it is not freely
  fetchable by a plain HTTP client.
- **efinanceThai's old frame-based news URL is dead** (`LastestNewsFrame.aspx`
  → HTTP 410 Gone). The site itself is alive and current; use
  `AllLatestNews.aspx` or the homepage. Flagging so a future session doesn't
  waste time on the stale URL pattern.
- **No central directory of company IR pages exists on SET's own site.** The
  `/en/services/ir-website` page is a service SET sells *to* listed companies
  (a widget they embed), not a public index of IR URLs. A retail investor has
  to reach a specific company's IR page via the company's own corporate site
  or a link surfaced from that company's SET news page — there's no
  one-stop "pick a ticker, get the IR URL" tool. Worth noting explicitly in
  the final doc so users aren't sent looking for a directory that doesn't
  exist.
- **Considered and not included:** ไทยรัฐ (Thairath) and other general-interest
  Thai dailies — they do carry business sections and appear as a source
  option inside the SETTRADE aggregator, but they're general news outlets
  first, not finance-specialist desks, so they're lower-signal-density for
  this specific use case than the sources listed above. Not flagged as
  defunct, just deprioritized — could be added back if the assembled doc
  wants a broader-headlines net.
- **Not independently re-verified in this pass** (time-boxed to the sources
  above, all reasonably high-confidence from search evidence even where a
  direct fetch wasn't attempted): ryt9.com (a long-running Thai
  corporate-press-release wire, saw it cited re: efinanceThai's own launch
  announcement — plausible primary-adjacent source for company press
  releases, worth a look in a future pass) and Businesstoday /
  TNN Online (both appeared as source options inside the SETTRADE
  aggregator's outlet filter, implying they're live, but weren't fetched
  directly).

## Addendum (2026-08-12): a missed primary regulator, and an IR-page hosting pattern

Follow-up research (user asked to keep digging for more sources) surfaced one real
gap in the original primary tier:

- **Thai SEC (สำนักงาน ก.ล.ต. — Securities and Exchange Commission, `sec.or.th`)**
  is a **distinct regulator from SET**, missed in the original pass. SET is the
  exchange/self-regulatory body for listing and trading; the SEC is the
  government capital-markets regulator with authority over prospectuses, tender
  offers, insider-transaction reporting (Section 246/247 filings), and
  fund/securities-business licensing — a genuinely separate primary-source
  channel from SET's own disclosure feed, not a duplicate of it. **Could not be
  verified live this session** — both `sec.or.th/EN/Pages/News_Detail.aspx` and
  `sec.or.th/EN/Pages/Home.aspx` returned HTTP 403 Forbidden on direct
  `WebFetch`, the same bot-gating pattern seen elsewhere in this map (Trading
  Economics, CNBC). No RSS found via search either. **Add to the primary tier
  with the same treatment as Bank of Thailand** (browse manually, no automated
  feed available) — it's a real gap in the "official/regulatory" coverage that's
  worth listing even without a feed, since a red flag like an SEC enforcement
  action or insider-trading filing on a top-10 name wouldn't show up on SET's
  own news page.
- **IR Plus (`irplus.in.th`)** is a shared Thai IR-hosting platform — confirmed
  several SET-listed companies run their investor-relations sites as
  `<company>.irplus.in.th` subdomains (e.g. `thaieasternbiopower.irplus.in.th`).
  This isn't a new distinct source, but it's a useful **search heuristic** for
  the "no central directory of company IR pages" gap already flagged above: if
  a top-10 name's IR page isn't easy to find via its own corporate site, check
  whether it's hosted on IR Plus. The platform itself doesn't expose a
  cross-company RSS/alert mechanism — each company's IR Plus-hosted page would
  need its own manual check or (if it offers one) its own email-alert signup,
  same as any other standalone company IR page.
- **Not independently verified, deprioritized:** GlobeNewswire's general
  organization-search feed pattern (`globenewswire.com/en/search/organization/...`)
  — already confirmed working for Novo Nordisk specifically in ticket 02's
  original research; a broader re-check of the general search page timed out
  this session but doesn't change that existing finding.

## Summary for the doc-assembly ticket (06)

**Daily quick-scan candidates** (fastest signal, matches the map's "layered
cadence" requirement): SET News & Announcements (EN or TH, filtered to
today's top-10 tickers) + SETTRADE's aggregator page or its RSS feeds +
one Thai outlet (Thunhoon or Kaohoon) + one English outlet (Kaohoon
International or Bangkok Post, browser-checked) for a two-language
cross-check.

**Deeper/weekly review candidates**: Bank of Thailand press releases (rate
decisions, monthly economic conditions) for macro backdrop; SET Market Alerts
for any structural red flags (halts, cash-balance, caution list) on names
that have been sitting in the top-10 for a while; company IR pages for any
name that's newly entered the top-10 (per the map's trigger condition).
