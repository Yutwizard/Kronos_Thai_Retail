# Kronos-TH News Monitoring Manual

> **Reference document — manual, human-facing practice only.**
>
> This manual is a news-monitoring habit for sanity-checking the daily
> pipeline's top-10 ranking (`get_top_ranked(10)` in
> `kth/trading/trade_gen.py`) against real-world news. **It never touches
> pipeline or model code** — no news ingestion, no scoring, nothing feeds
> into `rank_score` or trade generation. CLAUDE.md's hard scope limit on
> "news sentiment" in the automated pipeline stays exactly as-is; this is a
> separate, entirely manual operator habit that sits alongside
> [operations-manual.md](operations-manual.md) and
> [morning-paper-trading-guide.md](morning-paper-trading-guide.md).
>
> Produced via a [wayfinder](../.scratch/news-monitoring-template/map.md)
> planning effort — see that map and its child tickets for the full research
> and reasoning behind every source and rule below.

---

## Table of Contents

1. [Daily Quick-Scan](#1-daily-quick-scan-10-15-minutes)
2. [Weekly Deeper Review](#2-weekly-deeper-review-15-20-minutes)
3. [Red-Flag Decision Protocol](#3-red-flag-decision-protocol)
4. [Source Directory — SET-Listed Equities](#4-source-directory--set-listed-equities)
5. [Source Directory — DR Underlyings](#5-source-directory--dr-underlyings)
6. [One-Time Aggregation Setup](#6-one-time-aggregation-setup)
7. [Caveats & Known Gaps](#7-caveats--known-gaps)
8. [Quick Reference Card](#8-quick-reference-card)

---

## 1. Daily Quick-Scan (10-15 minutes)

### Objective
Sanity-check whatever 10 tickers land in today's `get_top_ranked(10)` output
against real news, using sources already pre-filtered by §4-§6 — this is a
skim of what's already there, not research from scratch.

### When
Fold into the existing evening pipeline routine (~23:45 BKK, per CLAUDE.md),
after the Trade Ticket is generated and before recording any paper trades.

### Step-by-Step

#### Step 1.1 — Pull today's top-10

Open the dashboard's Trade Ticket (or run `get_top_ranked(10)` directly) and
note the 10 tickers for tonight's scan.

#### Step 1.2 — Skim the Inoreader folders, per ticker

For each of the 10 tickers, check whichever Inoreader folder applies
(**Thai-market** or **DR-underlyings**, set up per §6) for anything new
since yesterday, filtered to that ticker's name.

#### Step 1.3 — Check the Settrade App favorites (SET names only)

Glance at the Settrade App's push notifications for anything Inoreader
missed — SET Group's own per-ticker channel (§6), covers SET-listed names
only, not DR underlyings.

#### Step 1.4 — Cross-check against the skip list

For anything flagged in Steps 1.2-1.3, check it against the fixed 5-item
skip list in §3. **Only those five ever trigger a skip** — routine earnings
misses, analyst rating changes, guidance revisions, ordinary management
reshuffles, and mechanical DR ratio/conversion notices are informational
only and don't block the trade.

#### Step 1.5 — One combined macro glance

Not per-ticker — a single check: SET index level/direction, USD/THB, and
whether BoT released anything today. Pairs with the Nikkei Asia feed in the
Inoreader macro folder (§6) if you want regional context too.

#### Step 1.6 — Log the day's entry

Append to `data/positions/morning_log.md` (the same daily journal the
paper-trading flow already writes to — see
[morning-paper-trading-guide.md](morning-paper-trading-guide.md) Step 9).
Even a "no flags found" day gets a line, so there's a trace the scan
actually happened:

```
News scan: no flags found across today's top-10.
```

If a red flag *did* fire and you skipped a trade because of it, log it per
§3's phrasing convention.

---

## 2. Weekly Deeper Review (15-20 minutes)

### Objective
Broader sector and macro context that the daily quick-scan intentionally
skips, plus a deeper one-time look at any name newly entering the top-10.

### When
Piggybacked onto the *existing* "3. Weekly Portfolio Review (15-20 minutes)"
slot in [operations-manual.md](operations-manual.md) — every Sunday evening
or Monday morning before market open. Not a separate standalone cadence.

### Step-by-Step

#### Step 2.1 — Sector context

For whichever `SECTOR` buckets (per `kth/data/universe.py`) the current
top-10 touches, skim for sector-wide news beyond what the daily per-ticker
scan caught.

#### Step 2.2 — Past week's macro releases

Review the week's Bank of Thailand releases and any Thai SEC items (§4) that
the daily glance (Step 1.5) wouldn't have surfaced in depth.

#### Step 2.3 — SET Market Alerts check

Check SET Market Alerts for any name that's been sitting in the top-10
across multiple days — catches a structural flag (halt, caution list,
cash-balance designation) that might have been missed on a day-to-day basis.

#### Step 2.4 — New-entrant deep look

For any ticker newly entering the top-10 for the first time in a while, do
one deeper pass: its IR page (§4/§5), recent filings, and — for a DR
name — a check of the KTB/BLS DR-mechanics page (§5). This is the
"event-triggered" component of the weekly review, folded into the
calendar cadence rather than run as a separate always-on watcher.

---

## 3. Red-Flag Decision Protocol

### Trigger threshold

A red flag can come from **either** a primary source **or** a reputable
secondary source (§4/§5's tiered lists) — you don't need to wait for a
primary-source confirmation before acting. Primary disclosure feeds are
often slow or non-existent (SET's own RSS is dead; Nasdaq Copenhagen's feed
isn't company-filterable), so a same-day secondary-press report is often the
only realistic signal you'll get before market open.

### The fixed skip list

Only these five trigger a skip. Everything else — routine earnings
misses/beats, analyst rating changes, guidance revisions, ordinary
management reshuffles, mechanical DR ratio/conversion notices — is
informational only.

| # | Trigger | Where it typically shows up |
|---|---|---|
| 1 | Trading halt / suspension | SET Market Alerts; home-exchange equivalent for DR names |
| 2 | Cash-balance-only or caution-list designation | SET Market Alerts |
| 3 | Fraud allegation or regulatory investigation/enforcement action | Thai SEC, AMF, CONSOB, or SEC EDGAR enforcement item |
| 4 | Auditor's qualified opinion, disclaimer, or going-concern flag | Company IR / annual filing coverage |
| 5 | Sudden, unscheduled C-suite departure | Company IR, primary/secondary press (not a *scheduled* transition) |

### Scope

**Strictly single-ticker.** A red flag skips only the flagged name's trade —
this protocol does not add a macro-level override. The dashboard's existing
Market State/Turmoil gate already handles systemic days (see
[operations-manual.md](operations-manual.md) §1, Step 1.4's "All signals 🔴 →
Market turmoil" row), and CLAUDE.md already retracted manually overriding
allocation based on a perceived SET macro regime (the
regime-conditional-alpha decision). This protocol deliberately doesn't
reintroduce that pattern via a news-driven back door.

### DR-specific addition

For DR trades, also check the KTB/BLS issuer-page DR-mechanics channel
(§5) — a ratio/conversion event severe enough to pair with a
trading-halt-equivalent triggers a skip even if nothing shows up in the
underlying's home-market news, since this failure mode has no equivalent on
the Paris/Milan/Copenhagen side.

### Recording the override

Log it in the existing `data/positions/morning_log.md` Reason field (same
file as §1's daily entry), using a consistent phrasing convention:

```
Reason: Manual override — news red flag ([trigger type], [source]).
```

No new field, no dashboard/API change — this reuses infrastructure that
already exists.

---

## 4. Source Directory — SET-Listed Equities

Covers the `thai_equity`/`thai_index` universe (`kth/data/universe.py`) —
the names that can appear in `get_top_ranked(10)`. Full research trail:
`.scratch/news-monitoring-template/research/01-set-sources-findings.md`.

### Primary (official/regulatory)

| Source | URL | Notes |
|---|---|---|
| SET News & Announcements (EN/TH) | [set.or.th/en/market/news-and-alert/news](https://www.set.or.th/en/market/news-and-alert/news) | The master disclosure feed, filterable by ticker. No RSS — SET's old feed hub (`classic.set.or.th`) is dead. |
| SET Market Alerts | [set.or.th/en/market/news-and-alert/market-alerts](https://www.set.or.th/en/market/news-and-alert/market-alerts) | Halts, suspensions, caution/cash-balance flags — feeds §3's skip list directly. |
| Thai SEC (สำนักงาน ก.ล.ต.) | [sec.or.th](https://www.sec.or.th) | A **distinct regulator from SET** — tender offers, prospectuses, insider-transaction filings. No RSS found; browse manually. |
| Bank of Thailand — News & Media | [bot.or.th/en/news-and-media/news.html](https://www.bot.or.th/en/news-and-media/news.html) | Rate decisions, monthly economic conditions. No RSS/email found. |
| Company IR pages | varies per ticker | No central SET directory exists. Check the company's own site first; many are hosted on the shared `<company>.irplus.in.th` platform if not obvious. |

### Secondary — Thai

| Source | URL | RSS? |
|---|---|---|
| SETTRADE.com news portal | [settrade.com/th/news-and-articles/news/main](https://www.settrade.com/th/news-and-articles/news/main) | **Yes** — live directory at [settrade.com/th/rss](https://www.settrade.com/th/rss), 6 topic feeds (not per-ticker). |
| Thunhoon | [thunhoon.com](https://thunhoon.com/) | No |
| Kaohoon | [kaohoon.com](https://www.kaohoon.com/) | No (has a mobile app) |
| efinanceThai | [efinancethai.com/LastestNews/AllLatestNews.aspx](https://www.efinancethai.com/LastestNews/AllLatestNews.aspx) | No |
| Bangkok Business News (Finance) | [bangkokbiznews.com/finance](https://www.bangkokbiznews.com/finance) | Not confirmed |
| Prachachat Business | [prachachat.net/finance](https://www.prachachat.net/finance) | Not confirmed |

### Secondary — English

| Source | URL | RSS? |
|---|---|---|
| Bangkok Post Business | [bangkokpost.com/business](https://www.bangkokpost.com/business) | Site fine for browsing; RSS is bot-toll-gated (HTTP 402) — don't rely on it for automation. |
| The Nation Thailand Business | [nationthailand.com/business](https://www.nationthailand.com/business) | Not confirmed |
| Kaohoon International | [kaohooninternational.com/thailand](https://www.kaohooninternational.com/thailand) | No |
| Investing.com — Thailand SET | [investing.com/indices/thailand-set-news](https://www.investing.com/indices/thailand-set-news) | **No per-symbol RSS confirmed** (topic feeds only) — browse manually. |
| Reuters / Bloomberg — Asia markets | reuters.com/markets/asia, bloomberg.com/quote/SET:IND | Macro-only, no Thailand company depth. |

**Deprioritized:** Thairath and other general-interest dailies (lower
signal-density than finance-specialist outlets). **Dead/broken:**
`classic.set.or.th`'s RSS hub, efinanceThai's old frame-based news URL.

---

## 5. Source Directory — DR Underlyings

Covers the 6 DR underlyings tradable on the SET in THB. Confirmed against
`kth_dr/universe_dr.py`. Full research trail:
`.scratch/news-monitoring-template/research/02-dr-sources-findings.md`.

| Underlying | Home exchange | DR ticker (issuer) |
|---|---|---|
| Hermès (`RMS.PA`) | Euronext Paris | `HERMES80.BK` (KTB) |
| L'Oréal (`OR.PA`) | Euronext Paris | `LOREAL80.BK` (KTB) |
| LVMH (`MC.PA`) | Euronext Paris | `LVMH01.BK` (BLS) |
| Sanofi (`SAN.PA`) | Euronext Paris | `SANOFI80.BK` (KTB) |
| Ferrari (`RACE.MI`) | Borsa Italiana / Euronext Milan (dual-listed NYSE `RACE`) | `FERRARI80.BK` (KTB) |
| Novo Nordisk (`NOVO-B.CO`) | Nasdaq Copenhagen | `NOVOB80.BK` (KTB) |

### Group 1 — Euronext Paris (Hermès, L'Oréal, LVMH, Sanofi)

**Primary:** AMF BDIF regulated-disclosure database
([bdif.amf-france.org/en](https://bdif.amf-france.org/en)) + each company's
own IR page (Sanofi's has an explicit email-alert signup; LVMH's is
JS-heavy, verify manually). **Secondary:** Les Echos (note: owned by LVMH's
parent group — a real independence caveat for LVMH coverage specifically),
Boursorama, Reuters/Bloomberg/FT (English wires, account-gated).

### Group 2 — Milan (Ferrari, dual-listed NYSE)

**Primary:** CONSOB's eMarket storage mechanism, Ferrari IR (JS-heavy,
verify manually), SEC EDGAR (NYSE cross-check). **Secondary:** Il Sole 24
Ore, MilanoFinanza.

### Group 3 — Copenhagen (Novo Nordisk)

**Primary:** company IR (has an explicit email-alert signup), GlobeNewswire
(Novo's chosen regulatory-announcement wire), SEC EDGAR (ADR `NVO`
cross-check). Nasdaq Copenhagen's own exchange feed
(`subscribe.news.eu.nasdaq.com/rss`) is real but **Nordic-wide only, not
filterable to Novo Nordisk** — GlobeNewswire is the better company-specific
option. **Secondary:** DR (Danmarks Radio) Penge desk, Børsen
(account-gated).

### Cross-cutting — Seeking Alpha per-symbol RSS

The single easiest source in this whole directory to plug into a reader —
free, no signup, one uniform mechanism covering all 6 names via their US
OTC/ADR/NYSE tickers:

| Underlying | Seeking Alpha feed |
|---|---|
| Sanofi | `seekingalpha.com/api/sa/combined/SNY.xml` |
| Novo Nordisk | `seekingalpha.com/api/sa/combined/NVO.xml` |
| Ferrari | `seekingalpha.com/api/sa/combined/RACE.xml` |
| LVMH | `seekingalpha.com/api/sa/combined/LVMUY.xml` |
| Hermès | `seekingalpha.com/api/sa/combined/HESAY.xml` |
| L'Oréal | `seekingalpha.com/api/sa/combined/LRLCY.xml` |

Treat as a secondary-tier, cross-cutting supplement — not a replacement for
the primary regulatory/IR sources above.

### SET's DR-mechanics channel (not a news substitute)

Per-DR issuer pages — KTB (`krungthai.com`) for 5 of 6, BLS
(`bualuang.co.th`) for LVMH01 — mirror ratio/conversion/corporate-action
changes. SET's own DR quote pages have no news tab. SET's general newsroom
separately covers DR-product-wide circulars (trading hours, new listings).
**None of this substitutes for the home-market source tables above** — it's
a low-frequency mechanics check, feeding §3's DR-specific skip-list
addition.

---

## 6. One-Time Aggregation Setup

Full research trail:
`.scratch/news-monitoring-template/research/03-alerting-tooling-findings.md`.
Since both universes (52 tickers, 6 DR underlyings) are fixed lists, this
is a one-time setup, not daily reconfiguration.

1. **Create a free Inoreader account** (150 RSS feeds + 20 email-to-RSS
   "Newsletter Feeds" on the free tier — chosen over Feedly, whose free tier
   excludes newsletters).
2. **"Thai-market" folder:** add SETTRADE's 6 RSS feeds
   ([settrade.com/th/rss](https://www.settrade.com/th/rss)).
3. **"Thai-market" folder, continued:** for each of the 52
   `thai_equity`/`thai_index` tickers, add a **Google News RSS search**
   feed — `https://news.google.com/rss/search?q="TICKER.BK"+"Company Name"`.
   **Always include the full company name in the query, not just the
   ticker** — a bare-ticker query returns stale, years-old results. For
   names whose English name collides with a common word, add a
   disambiguating News/Finance-only phrasing.
4. **"DR-underlyings" folder:** add all 6 Seeking Alpha per-symbol feeds
   (§5) — no signup needed, just add the URLs.
5. **"DR-underlyings" folder, continued:** create an Inoreader Newsletter
   Feed for each DR-underlying company that offers an email-alert signup
   (confirmed for Sanofi and Novo Nordisk; check Hermès/L'Oréal/LVMH/Ferrari
   too) and subscribe using the generated address.
6. **"DR-underlyings" folder, continued:** add 6 Google News RSS search
   feeds for the underlying names — Ferrari needs a disambiguator (pair
   with `"RACE.MI"`), L'Oréal needs both spellings (`L'Oréal` / `L'Oreal`).
7. **Optional macro addition:** add Nikkei Asia's RSS
   (`asia.nikkei.com/rss/feed/nar`) to a macro/regional folder — personal,
   non-commercial use only per its terms.
8. **Separately, install the Settrade App** and add all 52
   `thai_equity`/`thai_index` tickers to its Favorites list for push
   notifications. This is SET Group's own per-ticker channel and the only
   piece that stays outside Inoreader — no RSS/email export exists for it.

### Daily habit

Open Inoreader, filter to unread items across both folders, cross-reference
against today's `get_top_ranked(10)` output — skim only the items touching
today's top-10 names (§1) — then separately glance at the Settrade App's
notifications for the same names.

---

## 7. Caveats & Known Gaps

Sources that were checked and ruled out, or flagged as unconfirmed —
recorded here so a future pass doesn't re-chase them without reason.

| Source | Status |
|---|---|
| CNBC RSS | HTTP 403 on direct fetch — bot-gated, not usable for automation. |
| Trading Economics RSS | HTTP 403 on direct fetch — bot-gated. |
| Investing.com | No per-symbol RSS exists, topic feeds only. Manual browse only. |
| PR Newswire APAC | Only broad topic-category feeds, no company/Thailand-specific option. |
| StockTitan.net | No public per-ticker RSS found (internal JSON API only). |
| IR Plus (`irplus.in.th`) | A shared Thai IR-hosting platform (`<company>.irplus.in.th`), not a cross-company alert source — useful as a lookup heuristic only. |
| WiSET (SET's 2026 super-app) | Alerting appears tied to actual portfolio holdings, not a free watchlist — unconfirmed, spot-check in-app before relying on it. |
| SET Member account alerting | Unconfirmed beyond gating the apps above — low priority given the Settrade App already covers per-ticker push. |
| Yahoo Finance per-ticker RSS (`feeds.finance.yahoo.com/rss/2.0/headline?s=<TICKER>`) | Mechanism is live, but Thai-side coverage is patchy (confirmed content for `PTT.BK`, empty for `AOT.BK`). Worth a per-ticker try as a supplement, not a primary source. |
| LVMH's and Ferrari's own IR pages | Heavily JS-rendered — verify manually in a browser rather than assuming a feed can be scripted against them. |
| La Tribune, Børsen, Berlingske Business | Not independently confirmed live this session — well-known outlets, but spot-check before relying on them. |
| Nasdaq Copenhagen exchange feed | Real, but Nordic-wide only — not filterable to Novo Nordisk specifically. |

---

## 8. Quick Reference Card

```
DAILY (10-15 min)   Pull top-10 -> skim Inoreader (per ticker) -> check
                     Settrade App (SET names) -> cross-check skip list ->
                     one macro glance -> log to morning_log.md.

WEEKLY (15-20 min)  Piggybacked on the existing Weekly Portfolio Review:
                     sector context -> week's macro/BoT -> SET Market
                     Alerts check -> deep look at any new top-10 entrant.

SKIP LIST (5)       Halt/suspension. Cash-balance/caution. Fraud or
                     regulatory investigation. Auditor qualified opinion.
                     Sudden unscheduled C-suite exit.
                     -> Everything else is informational only.

SCOPE               Single-ticker only. No macro override here -- that's
                     the dashboard's existing Turmoil gate's job.

DR ADDITION         Also check the KTB/BLS DR-mechanics page for a
                     severe ratio/conversion event.

RECORDING           data/positions/morning_log.md, Reason field:
                     "Manual override -- news red flag ([type], [source])"
```

---

*This manual is a purely human-facing, manual practice — it does not touch
`kth/`, `kth_dr/`, the pipeline, or the dashboard. Not financial advice.
Sourced from a wayfinder planning effort — see
`.scratch/news-monitoring-template/map.md` for the full decision trail.*
