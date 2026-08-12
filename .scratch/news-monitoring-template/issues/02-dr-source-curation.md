# 02 - Curate tiered international news sources for DR underlyings

Type: research
Status: resolved

## Question

The universe includes DRs (Depositary Receipts) of 6 major foreign stocks
tradable on the SET in THB: Hermès, L'Oréal, LVMH, Sanofi, Ferrari, Novo
Nordisk (per CLAUDE.md; confirm exact tickers and home exchanges via
`kth_dr/universe_dr.py`). Their price-relevant news happens on their home
exchanges (Euronext Paris, NYSE/Milan for Ferrari, Copenhagen for Novo
Nordisk), not in Thailand — a Thai-source-only monitoring list would miss
it entirely.

Produce a tiered source list per underlying (or grouped by exchange/home
market where sources overlap, e.g. one Euronext Paris source set covering
Hermès/L'Oréal/LVMH/Sanofi):

- **Primary** — home-exchange regulatory disclosure (e.g. AMF/Euronext
  filings for the Paris-listed names, company IR pages).
- **Secondary** — reputable financial press in the relevant language/market
  (French press for Paris-listed names, English wire coverage — Reuters/
  Bloomberg/FT — for all of them, Danish press for Novo Nordisk if
  useful).

Also note: since these trade as DRs in THB on the SET, flag whether SET's
own disclosure channel carries anything DR-specific (e.g. DR ratio
changes, conversion notices) distinct from the underlying's home-market
news — that would belong in this list too, not ticket 01's.

Same format as ticket 01: name, URL, tier, language, what it's best for,
RSS/alert availability. Verify sources are currently live, not assumed
from training knowledge.

## Answer

Full findings, verified live via web search/fetch (August 2026):
`research/02-dr-sources-findings.md` (pulled onto `main` from the throwaway
`research/dr-news-sources` branch, commit `1242ef5`).

Confirmed against `kth_dr/universe_dr.py`/`data/dr/mapping.json`: Hermès
(`RMS.PA`/`HERMES80.BK`), L'Oréal (`OR.PA`/`LOREAL80.BK`), LVMH
(`MC.PA`/`LVMH01.BK`), Sanofi (`SAN.PA`/`SANOFI80.BK`) — all Euronext
Paris — plus Ferrari (`RACE.MI`/`FERRARI80.BK`, Borsa Italiana, dual-listed
NYSE) and Novo Nordisk (`NOVO-B.CO`/`NOVOB80.BK`, Nasdaq Copenhagen).

**Grouped by exchange (3 groups, not 6 separate lists) since sources
overlap:**
- **Group 1 — Euronext Paris (Hermès/L'Oréal/LVMH/Sanofi):** Primary = AMF
  BDIF regulated-disclosure database + each company's own IR page (all 4
  IR pages live-confirmed with current 2026 releases except LVMH's, which
  is JS-heavy and needs manual browser verification). Secondary = Les
  Echos, La Tribune (low-confidence), Boursorama, Reuters/Bloomberg/FT
  (English wires, none independently fetchable — bot-blocked, but
  well-established). Noted: Les Echos is owned by LVMH's parent group —
  a caveat on independence specifically for LVMH coverage.
- **Group 2 — Ferrari (Milan/NYSE dual-listed):** Primary = CONSOB's
  eMarket storage mechanism + Ferrari IR (JS-heavy, needs manual check) +
  SEC EDGAR (cross-check via the NYSE listing). Secondary = Il Sole 24 Ore
  and MilanoFinanza (both live-confirmed with same-day price data),
  Reuters/Bloomberg/FT.
- **Group 3 — Novo Nordisk (Copenhagen):** Primary = company IR (has an
  explicit email-alert signup), GlobeNewswire (Novo's chosen
  regulatory-announcement wire), SEC EDGAR (ADR cross-check). Nasdaq
  Copenhagen's own exchange-level feed URL couldn't be pinned down —
  flagged as unverified, don't cite a specific URL yet. Secondary = DR
  (Danmarks Radio) Penge desk (free, live-confirmed with a
  Novo-Nordisk-specific article), Børsen (paywalled/bot-blocked,
  well-known but unverified this session), Berlingske Business
  (unconfirmed, may need dropping).

**SET DR-specific disclosure channel — answered:** yes, but only
mechanical/administrative, not a substitute for home-market monitoring.
Per-DR issuer pages (KTB for 5 of 6, BLS for LVMH01) mirror
ratio/corporate-action changes; SET's DR quote pages themselves have no
news tab; SET's general newsroom separately covers DR-product-wide
circulars (trading hours, new listings) but not underlying company news.
Recommendation carried into ticket 06: treat these as a low-frequency
"DR-mechanics check," clearly separate from the actual news-monitoring
source tables.

**Lower-confidence items flagged for manual spot-check** (bot-blocked or
JS-heavy, not independently fetch-verified this session): LVMH's and
Ferrari's own IR pages, La Tribune, Børsen, Berlingske Business,
Reuters/Bloomberg/FT generally, and Nasdaq Copenhagen's exchange-level
feed URL.

Status: resolved.

**Addendum (2026-08-12):** follow-up research found **Seeking Alpha's
per-symbol RSS feed** (`seekingalpha.com/api/sa/combined/<TICKER>.xml`) —
free, no signup, directly `WebFetch`-confirmed live for all 6 underlyings
via their US OTC/ADR/NYSE tickers (`SNY`, `NVO`, `RACE`, `LVMUY`, `HESAY`,
`LRLCY`), each returning 30+ real Jul/Aug-2026-dated items (earnings
transcripts, analyst pieces, news briefs). This is the single easiest
source in the whole ticket to plug into an RSS reader — one uniform
mechanism covering all 6 names, no bridge/JS-rendering issues. Treat as a
secondary-tier, English-language, cross-cutting supplement to the
per-exchange primary/secondary tables above, not a replacement for them.
Also resolved: Nasdaq Copenhagen's exchange-level feed
(`subscribe.news.eu.nasdaq.com/rss`) is real but only offers broad
Nordic-wide category feeds, not filterable to Novo Nordisk specifically —
GlobeNewswire stays the better company-specific option. Full detail
appended to `research/02-dr-sources-findings.md`.
