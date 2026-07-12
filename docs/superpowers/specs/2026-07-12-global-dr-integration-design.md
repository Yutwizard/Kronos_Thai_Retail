# Global DR Integration — Design Spec

> Expand the Kronos-TH investable universe to include global stocks accessible
> via Depositary Receipts (DRs) listed on the Stock Exchange of Thailand (SET).
> The Kronos signal runs on the **underlying** asset; the DR is the execution vehicle.

## Motivation

Thai retail investors can trade global stocks (US, HK, JP, KR, EU) through DRs
listed on the SET. Adding them to the universe gives the portfolio access to
non-Thai equity alpha without needing a foreign broker account.

## Glossary

If you're new to this codebase or to DRs, read this first — the rest of the
doc assumes these terms.

- **Depositary Receipt (DR):** A security listed on the SET (Thailand's stock
  exchange) that represents ownership of a *foreign* stock. A Thai investor
  buys/sells the DR in Thai Baht, during Thai market hours, through a normal
  Thai broker account — no foreign brokerage needed. Example: `AAPL80.BK` is
  a DR representing Apple stock.
- **Underlying:** The real, foreign stock a DR represents. For `AAPL80.BK`,
  the underlying is `AAPL` (Apple, trading on Nasdaq in USD).
- **Ratio:** How many DR units equal one share of the underlying. `ratio: 80`
  means 80 units of `AAPL80.BK` = 1 share of `AAPL`.
- **Signal vs. execution (the "dual-ticker model"):** The Kronos AI model
  predicts where `AAPL` is headed by reading *Apple's own* price history —
  that's the **signal**. But nothing in this pipeline can buy `AAPL`
  directly for a DR-based position; the investor buys `AAPL80.BK` on SET
  instead — that's the **execution**. Same trade idea, two different ticker
  symbols involved. This split is the one idea the whole spec is built
  around.
- **Ticker class:** A label like `"thai_equity"`, `"us_equity"`, `"crypto"`,
  or (new) `"dr"`. Every ticker in `universe.py` belongs to exactly one
  class, and each class has its own trading costs (`FRICTION`) and market
  calendar.
- **Sector guard:** An existing portfolio rule: never hold more than 2
  positions in the same sector (e.g. "Banking") at once, to avoid
  over-concentration. DRs are placed in their own sector, `"Global"`.
- **`verified` flag:** A DR candidate is never trusted automatically. A
  discovery script proposes candidates, but every one starts as
  `verified: false`; a human must open the mapping file, check it's a real
  and liquid DR, and flip it to `verified: true` before the pipeline will
  ever trade it.
- **Premium / discount:** A DR's SET market price can drift away from what
  the underlying is "really worth" once converted to THB. That gap
  (`premium_pct`) is tracked as a warning signal for the investor — it never
  feeds back into the trading decision itself.
- **Plugin hook / optional import:** A small, deliberate seam added to the
  existing code — a function call, or a `try/except ImportError` block —
  that does nothing if the new DR code isn't installed. This is what lets
  DR support be added (or later deleted) without editing the core pipeline
  every time.

## Worked Example: One DR Trade, Start to Finish

Concrete walk-through using Samsung (`005930.KS`, listed in Korea) and its
DR `SAMSUNG80.BK` (ratio 80), so the rest of the spec has something real to
hang onto:

1. **Seed list.** `data/dr/seed_list.json` says: "Samsung's DR is
   `SAMSUNG80.BK`, ratio 80." A human typed this in ahead of time — it's not
   guessed by a script.
2. **Discovery.** `scripts/dr/discover_drs.py` downloads `SAMSUNG80.BK`'s
   price history, computes its 30-day average volume (say 45,000 units/day)
   and confirms it has enough trading history. It writes an entry into
   `data/dr/mapping.json` with `"verified": false`.
3. **Human review.** The user opens `mapping.json`, sees `SAMSUNG80.BK` is a
   real, liquid, tradeable security, and changes `"verified"` to `true`.
   From this point on, the pipeline is allowed to trade it.
4. **Forecast.** That evening, Kronos runs on `005930.KS`'s own price
   history (never on `SAMSUNG80.BK`) and predicts Samsung will rise 3%
   tomorrow.
5. **Trade-gen.** `trade_gen.py` sees the bullish forecast for `005930.KS`,
   looks up `get_verified_dr_tickers()`, finds that `SAMSUNG80.BK` is its
   verified DR, and builds a **buy ticket for `SAMSUNG80.BK`** — using
   `SAMSUNG80.BK`'s own SET price and its own trading fees, not Samsung's.
6. **Execution & tracking.** The investor buys `SAMSUNG80.BK` on SET. From
   here on, `portfolio.py` treats it exactly like any other Thai-listed
   position (it's stored under the ticker `SAMSUNG80.BK`, marked to market
   using `SAMSUNG80.BK`'s own daily close). The only extra thing the
   dashboard shows is a `premium_pct` number — "is `SAMSUNG80.BK` trading
   above or below what Samsung is really worth in THB right now?" — which is
   informational only.

Keep this example in mind: almost every section below is really just
answering "how exactly does step 3, 5, or 6 get implemented, and what could
go wrong?"

## Core Design Decisions

1. **Dual-ticker model:** Underlying price → Kronos signal. DR price → execution
   (fill cost, premium tracking). Never mix them.
2. **1:N mapping:** One underlying can map to multiple DRs (different series,
   ratios, issuers). Pipeline picks the highest-liquidity verified DR.
3. **Seed-list-driven discovery + human review:** A curated seed list is the
   primary source of DR candidates; a scanner adds secondary candidates for
   review. The user marks entries `verified` before they are used in the
   pipeline. (See "Discovery Logic" — revised from a scan-first design.)
4. **Minimal, contained integration — not zero-change, but small and generic.**
   Almost all DR logic lives in the new `kth_dr/` package (see "Folder
   Layout"). The only touches to shared files are: a generic
   `register_asset_class()` plugin hook in `universe.py` (not DR-flavored —
   reusable for any future asset class), and two optional-import call sites
   in `trade_gen.py` that no-op cleanly if `kth_dr` isn't present. No change
   to `portfolio.py`'s `execute_trade`/`get_positions` — those are already
   ticker-agnostic and require no modification.
5. **No same-underlying double exposure:** A DR and a direct listing of the
   same underlying (e.g. `AAPL` in `us_equity` and `AAPL80.BK` in `dr`) must
   never both be eligible at once. See "Overlap with existing universe" below.

## Folder Layout — separable by design

**In plain terms:** put nearly all new DR code in one new folder
(`kth_dr/`), not scattered through the existing `kth/` folder, so it can be
deleted or copied into its own project later by touching only a handful of
lines elsewhere.

DR is a global-equity idea layered on a Thai-retail-scoped project (per
CLAUDE.md's project description). The user may want to split DR into its own
project later, separate from Thai-stock forecasting. So instead of scattering
DR logic across the existing `kth/` modules, almost all of it lives in a new,
self-contained package:

```
kth_dr/                       # everything DR-specific — the "extractable unit"
├── __init__.py                # on import, calls universe.register_asset_class(...)
├── universe_dr.py             # DR_MAP, get_dr_for_underlying, get_underlying_for_dr,
│                               # get_verified_dr_tickers, MIN_DR_HISTORY,
│                               # DR_PREMIUM_WARN_THRESHOLD, FRICTION["dr"], sector="Global"
├── loader_dr.py                # load_dr_bundle() — thin wrapper around kth.data.loader
├── discover_drs.py             # discovery algorithm (seed list + scan)
└── trade_gen_dr.py             # execution_ticker resolution + same-underlying guard

data/dr/
├── seed_list.json
└── mapping.json

scripts/dr/
└── discover_drs.py             # CLI entrypoint -> kth_dr.discover_drs.main()
```

**The only touches to existing shared files** (`kth/data/universe.py`,
`kth/trading/trade_gen.py`, `kth/trading/sheets_config.py`) are a small,
generic plugin hook and two optional-import call sites — see "Minimal,
contained integration" below and the Architecture section. If DR is ever
pulled into a separate repo, deleting `kth_dr/`, `data/dr/`, `scripts/dr/`
and the handful of hook lines is the entire removal — nothing else in `kth/`
needs to change or breaks (the optional imports degrade to no-ops).

`kth_dr` still **imports** `kth.data.loader`/`kth.data.universe` rather than
duplicating the yfinance download/caching code (reuse over duplication, per
project convention) — it depends on this repo, this repo doesn't depend on
it. That's a reasonable default while the "move to a separate project"
decision is still tentative; if/when you do split it out, that's the one
dependency to either vendor or keep as a pinned library import.

## Prerequisite: Trade-Gen Ticker Scope

**In plain terms:** before DRs can be traded at all, we need to fix a gap
where the trade-generation code only ever looks at Thai stocks — it would
silently ignore DRs even if everything else in this spec were built.

`kth/trading/trade_gen.py` currently hardcodes
`THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]` and
`load_forecasts()` only loops over that list (trade_gen.py:20,40). None of the
other 8 asset classes already defined in `universe.py` (us_equity, crypto,
etf_global, commodity, bond_proxy, reit, thai_index, fx_macro) currently
produce a trade ticket — forecasts and prices exist for them, but
`generate_trade_ticket()` can never buy/sell/reduce them. This is not a
documented scope decision; it looks like an incomplete migration from when
the universe was thai_equity-only.

**Resolution — narrow fix, not a full multi-asset rollout:** Do not generalize
`trade_gen.py` to the entire universe as part of this spec (that's a much
larger change touching position sizing and the sector guard's "Other" bucket,
which today would become a single catch-all bucket shared by 6 unrelated
asset classes competing for 2 slots — out of scope here). Instead, an
optional import that degrades to a no-op if `kth_dr` is absent (see "Folder
Layout"):

```python
# trade_gen.py
from kth.data.universe import UNIVERSE

THAI_TICKERS = [t for t, _, _ in UNIVERSE["thai_equity"]]
try:
    from kth_dr.universe_dr import get_verified_dr_tickers
    EXTRA_TICKERS = get_verified_dr_tickers()
except ImportError:
    EXTRA_TICKERS = []
TRADABLE_TICKERS = THAI_TICKERS + EXTRA_TICKERS
```

`get_verified_dr_tickers()` (in `kth_dr/universe_dr.py`) returns the
`primary_dr` ticker for every underlying whose primary alternative has
`verified: true`. `load_forecasts()` loops over `TRADABLE_TICKERS` instead of
`THAI_TICKERS`. This is the one deliberate, narrow expansion of scope; the
broader "activate us_equity/crypto/etc. in trade_gen" gap should be filed as
its own follow-up, separate from DR integration. If `kth_dr` is later
removed, this block silently falls back to thai_equity-only — no follow-up
edit required in `trade_gen.py` itself.

## Overlap With Existing Universe

**In plain terms:** don't let the portfolio accidentally buy the same
company twice under two different ticker symbols (once directly, once via
its DR) — that would look like diversification but isn't.

`universe.py` already lists `AAPL`, `MSFT`, `NVDA`, etc. under `us_equity` as
directly investable by Thai retail investors. The original spec's example
`mapping.json` used AAPL/MSFT as DR candidates — both already directly
tradeable, so a DR position and a direct position could both be open on the
same underlying at once (different sectors — `"Other"` vs `"Global"` — so the
sector guard doesn't catch it), doubling single-name exposure.

**Resolution:**
1. **Exclude at discovery time.** `kth_dr/discover_drs.py` checks each
   resolved underlying against `kth.data.universe.get_all_tickers()`; if it's
   already in `us_equity` or `etf_global`, write it with
   `"excluded_reason": "already_direct"` instead of a normal `verified: false`
   candidate, so it never reaches the review queue as if it were new. This is
   a read-only import from `kth` into `kth_dr` (the dependency direction
   established in "Folder Layout" — `kth_dr` is allowed to read from `kth`,
   `kth` never imports from `kth_dr` except via the optional-import hooks).
2. **Defense in depth at trade-gen time.** In the buy loop, track underlyings
   already held (resolving any held DR back to its underlying via
   `get_underlying_for_dr()` in `kth_dr/trade_gen_dr.py`) and skip a candidate
   whose underlying is already held either directly or via another DR —
   protects against a user manually marking an overlapping DR `verified: true`
   anyway.
3. **Re-scope the initial ticker list toward names with no existing direct
   path** — HK/JP/KR/EU large caps (e.g. Samsung, Tencent, Toyota, ASML), not
   US mega-caps already covered by `us_equity`. This is the actual source of
   incremental alpha the motivation section is after.

## Data Model

### `data/dr/mapping.json`

```json
{
  "_meta": {
    "generated": "2026-07-12T12:00:00+07:00",
    "dr_count": 3,
    "underlying_count": 2,
    "status": "needs_review"
  },
  "005930.KS": {
    "display_name": "Samsung Electronics",
    "underlying_exchange": "KR",
    "underlying_currency": "KRW",
    "fx_ticker": "THB=X",
    "primary_dr": "SAMSUNG80.BK",
    "alternatives": [
      {
        "dr_ticker": "SAMSUNG80.BK",
        "ratio": 80,
        "liquidity_rank": 1,
        "avg_volume_30d": 45000,
        "listing_date": "2022-03-14",
        "history_rows": 1050,
        "verified": true
      }
    ]
  },
  "AAPL": {
    "display_name": "Apple Inc.",
    "underlying_exchange": "US",
    "underlying_currency": "USD",
    "excluded_reason": "already_direct",
    "note": "AAPL is already directly investable via universe.py:us_equity — DR candidates for it are excluded from review, not just left unverified."
  },
  "_unresolved": [
    {
      "dr_ticker": "XYZ80.BK",
      "reason": "no underlyingSymbol/underlyingName found in yfinance Ticker.info"
    }
  ]
}
```

`history_rows` and `listing_date` are populated by `discover_drs.py` from the
downloaded DR price series (see "DR liquidity threshold" under Open
Questions — a thin-history DR should not win `primary_dr` ranking).

## Intrinsic Value & Premium Tracking

Each DR position tracks 3 data series:

| Series | Source | Purpose |
|--------|--------|---------|
| Underlying OHLCV | yfinance (`AAPL`) | Kronos signal generation |
| FX rate | yfinance (`THB=X`) | Convert to THB for portfolio |
| DR market price | yfinance (`AAPL80.BK`) | Fill cost, P&L, premium |

**DR intrinsic value** (in THB):
```
dr_intrinsic = (underlying_price × fx_rate(THB)) / ratio
```

**DR premium/discount** (monitoring metric, not used in signal):
```
premium_pct = (dr_market_price / dr_intrinsic) - 1
```

If premium/discount exceeds a threshold (e.g. ±5%), the dashboard flags it —
the investor may prefer an alternative DR or broker channel.

**Resolved: threshold = ±5%, defined once.** `DR_PREMIUM_WARN_THRESHOLD = 0.05`
lives in `universe.py` next to `DR_MAP` (single source of truth, importable by
both any future backend flag logic and the dashboard). The Positions sheet
schema is extended (see "Schema changes" below) to carry the raw
`premium_pct` number; the dashboard applies the threshold for display rather
than duplicating it as a second stored flag.

## Architecture

**In plain terms:** this section lists, file by file, exactly what code
gets added or touched. If you're implementing this spec, this is your
checklist.

### `kth/data/universe.py` — the *only* generic, non-DR-specific addition

```python
# universe.py — new, ~15 lines, reusable by any future asset-class plugin
_extra_ticker_class: dict[str, str] = {}
_extra_sector: dict[str, str] = {}
_extra_friction: dict[str, dict] = {}

def register_asset_class(ticker_class: dict[str, str],
                         sector: dict[str, str] | None = None,
                         friction: dict[str, dict] | None = None):
    """Let an external package (e.g. kth_dr) register tickers without
    universe.py knowing anything about that package's internals."""
    _extra_ticker_class.update(ticker_class)
    if sector: _extra_sector.update(sector)
    if friction: _extra_friction.update(friction)
```

`get_ticker_class()`, `get_sector()`, and `get_friction()` each gain one
fallback line to check `_extra_*` after their existing lookups fail — no
DR-flavored branches, no knowledge of "dr" as a concept. `kth_dr/__init__.py`
calls `register_asset_class(...)` once at import time with its own
`DR_MAP`-derived dicts (`"dr"` class, `"Global"` sector, thai_equity-matching
friction). Nothing else in `universe.py` changes.

### `kth_dr/universe_dr.py`
- `DR_MAP` — module-level dict, loaded once from `data/dr/mapping.json`
- `load_dr_mapping()` — loads and validates `data/dr/mapping.json`
- `get_dr_for_underlying(underlying_ticker)` — returns primary DR info,
  skipping alternatives with `history_rows < MIN_DR_HISTORY` (see below)
- `get_underlying_for_dr(dr_ticker)` — reverse lookup (DR → underlying),
  needed by trade-gen rationale, the same-underlying guard, and premium display
- `get_verified_dr_tickers()` — flat list of `primary_dr` tickers whose
  primary alternative is `verified: true`; consumed by `trade_gen.py`'s
  optional-import hook (see "Prerequisite" above)
- `MIN_DR_HISTORY = 60` — minimum price-history rows for a DR alternative to
  be eligible for `primary_dr` ranking (premium/liquidity stats need a
  handful of weeks, not Kronos's 400-row lookback — the underlying carries
  that requirement, not the DR)
- `DR_PREMIUM_WARN_THRESHOLD = 0.05`
- Calls `kth.data.universe.register_asset_class()` on import (via `__init__.py`)
  with `{dr_ticker: "dr", ...}`, `{dr_ticker: "Global", ...}`, and
  `{"dr": {"commission_oneway": 0.00168, "slippage_oneway": 0.0010}}`

### `kth_dr/discover_drs.py` (invoked via `scripts/dr/discover_drs.py`)
- Reads `data/dr/seed_list.json` first (curated, git-tracked, same
  intentional-change philosophy as `universe.py`'s hardcoded ticker list) —
  see "Discovery Logic" below for why this is now the primary path
- Secondarily scans SET via yfinance for tickers matching DR naming patterns,
  writing anything not already in the seed list as a new review candidate
- For each candidate, fetches underlying info from yfinance `Ticker.info`
  (`priceToBook`, `shortName`, `marketCap` to identify the underlying)
- Cross-checks resolved underlyings against `kth.data.universe.get_all_tickers()`;
  any underlying already in `us_equity`/`etf_global` is written with
  `"excluded_reason": "already_direct"` instead of a normal candidate
- Computes 30-day average volume for liquidity ranking, plus `listing_date`
  and `history_rows` from the downloaded DR series
- Writes to `data/dr/mapping.json`
- Does NOT set any entry to `verified: true` — that's the user's job

### `kth_dr/loader_dr.py`
- `load_dr_bundle(underlying_ticker)` returns:
  - Underlying OHLCV (from cache or download, via `kth.data.loader`)
  - DR OHLCV (from cache or download, via `kth.data.loader`)
  - FX rate series (from cache or download, via `kth.data.loader`)
- The pipeline calls this when processing DR-position days
- All three series are cached under the existing `./data/raw` directory
  (same files `kth.data.loader.download_universe`/`load_cached` already use)
  — **not** a separate cache path — so they ride along with the existing
  Kaggle-Dataset cache-persistence mechanism without extra wiring (see
  "Kaggle persistence" below)

### `kth_dr/trade_gen_dr.py` + thin hooks in `kth/trading/trade_gen.py`
- `resolve_execution_ticker(ticker)` (in `kth_dr`) — given an underlying
  ticker with a verified DR, returns the DR ticker; identity otherwise
- `trade_gen.py`'s `load_forecasts()` loops `TRADABLE_TICKERS` (thai_equity +
  verified DR primaries, per "Prerequisite" above) instead of `THAI_TICKERS`
- For a DR ticker, the forecast row is computed from the **underlying's**
  Kronos output but priced for execution using the **DR's** own cached close
  — `trade_gen.py` adds one generic `execution_ticker` field to each forecast
  row (equal to `ticker` for non-DR names; resolved via the optional-import
  hook for DR names) so the underlying/execution split isn't implicit
- `generate_trade_ticket()`'s buy/exit/reduce builders key `shares`/
  `last_close`/`estimated_thb`/friction lookups off `execution_ticker`, and
  append the underlying symbol to `rationale` for traceability (e.g.
  `"🟢↑ DR proxy for 005930.KS, rank#3..."`) — this string-building is generic,
  no DR-specific branching needed in `trade_gen.py` itself
- Buy loop's same-underlying guard: before adding a candidate, resolve every
  held ticker to its underlying (via the optional `get_underlying_for_dr`
  hook, identity if absent) and skip if the candidate's underlying is
  already held

### Schema changes
- `POSITIONS_HEADERS` (sheets_config.py) gains two columns: `underlying_ticker`,
  `premium_pct` — populated only for `dr`-class positions, blank otherwise.
  This is the one schema touch that isn't optional-import-guarded (a header
  change), but it's harmless dead weight if `kth_dr` is later removed —
  just two permanently-blank columns.

### Pipeline integration
1. **Forecast phase:** Kronos runs on underlying tickers as usual; underlying
   tickers referenced by any verified DR are added to the investable ticker
   list (download + forecast), same as any other ticker
2. **Signal phase:** `compute_signals()` sees underlying forecasts — unchanged
3. **Trade-gen phase:** `trade_gen.py` translates underlying signal →
   DR-ticket via `execution_ticker` (see above) — this is the one place with
   real code changes, not zero
4. **Execution phase:** When a DR position is opened/closed, portfolio uses
   the DR price for fill cost and the underlying for P&L attribution.
   `portfolio.execute_trade`/`get_positions` need no changes — they're called
   with the DR ticker and DR price, exactly like any other ticker
5. **Portfolio tracking:** Portfolio P&L is based on **DR execution prices**
   (actual fills). A diagnostic "signal equity" curve based on underlying intrinsic
   value is tracked separately for premium/discount analysis. Metrics (Sharpe,
   return, drawdown) use the execution-price equity curve.

### Known limitation: signal/execution timing lag
**In plain terms:** because the US stock market and the Thai stock market
are open at different times of day, the Kronos forecast for a US company is
always based on slightly "stale" data by the time the Thai-listed DR trades
on it. This isn't something DR integration causes — it already happens
today for direct US stock positions — but it's worth knowing about.

The Kaggle pipeline runs in the Thai evening (after SET close) so tomorrow's
forecast uses today's close (see CLAUDE.md). At that point in the day, the US
session for "today" hasn't opened yet (US regular hours run roughly
20:30–03:00/04:00 Thai time) — so a US underlying's Kronos forecast is based
on the **prior** US session's close, while the SET-listed DR trades same-day
with a full session of its own price action already in. This ~1-day lag
between signal timestamp and execution timestamp already exists today for
direct `us_equity` positions (same schedule, same lag) — DR integration
doesn't introduce a new problem, it inherits an existing one. No code change
proposed here; flagged so it isn't mistaken for a DR-specific defect during
review, and so a future fix (e.g. running forecasts at a US-close-aligned
time) is tracked as a separate, cross-cutting improvement rather than folded
into this spec.

## Discovery Logic

**In plain terms:** how do we build the initial list of "these are real DRs
and here's what stock each one represents"? Two ways feed into
`mapping.json`: a small hand-typed list the user trusts (primary), and an
automated scanner that guesses from ticker-name patterns (secondary,
lower-trust, everything it finds needs human sign-off).

**Resolved: seed-list-driven, not scan-first.** A hand-curated seed list is
the primary source of candidates; the regex/`Ticker.info` scan is a secondary
pass that only ever proposes new review candidates, never auto-populates
`primary_dr`. Rationale: `Ticker.info` field availability is inconsistent
across yfinance tickers and the naming heuristic (`\d+\.BK`, contains
"NVDR"/"DR") will false-positive on ordinary SET tickers — contained by
`verified: false`, but a scan-first design front-loads a large, noisy review
queue on day one. Starting from a small, known-good seed list (which also
answers Open Question 4 below) keeps the first review pass small and
non-US-focused.

`kth_dr/discover_drs.py` algorithm (invoked via `scripts/dr/discover_drs.py`):

```
1. Load data/dr/seed_list.json (git-tracked, hand-authored):
   {underlying_ticker: [{"dr_ticker": ..., "ratio": ...}, ...]}
2. For each seed entry: verify it still trades (download check), compute
   30d volume and history_rows/listing_date, cross-check against
   get_all_tickers() for "already_direct" exclusion
3. Secondary scan pass — query yfinance for SET-listed tickers matching DR
   naming patterns not already covered by the seed list:
   - Ends with `\d+\.BK` (digits before .BK suffix, e.g. AAPL80.BK)
   - Contains "NVDR" or "DR" before .BK suffix
4. For each scan candidate:
   a. Fetch Ticker.info via yfinance
   b. Recursively search info dict for fields hinting at underlying
      (e.g. "underlyingSymbol", "underlyingName")
   c. If underlying found: record (dr_ticker, underlying, ratio) as a new
      verified:false candidate
   d. If not found: flag as "unresolved" for manual mapping
5. For all resolved candidates (seed + scan):
   a. Rank alternatives per underlying by liquidity, excluding any with
      history_rows < MIN_DR_HISTORY from primary_dr eligibility
   b. Assign liquidity_rank
6. Write mapping.json. Seed-list entries retain whatever `verified` value
   the user previously set (re-running discovery must not silently
   unverify existing approvals); new candidates from the scan pass are
   always written verified: false
```

Known limitation: some DRs may be unresolvable programmatically (missing
metadata on yfinance). These are written to a `_unresolved` section for
manual input.

## Kaggle persistence

`data/dr/mapping.json`, `data/dr/seed_list.json`, and all DR/underlying/FX
parquet files live under the same paths already covered by the existing
Kaggle-Dataset cache-persistence mechanism (`./data/raw`, per the
"multi-session support with Kaggle Dataset cache persistence" work). Action
item during implementation: confirm the Kaggle notebook builder / dataset
upload step's persisted-path list explicitly includes `data/dr/` — it's a new
directory, not automatically covered just because `./data/raw` is.

## Calendar & Friction

| Property | Value |
|----------|-------|
| Asset class | `dr` |
| Calendar | Business days (SET calendar, same as thai_equity) |
| Commission (one-way) | 0.00168 (same as thai_equity) |
| Slippage (one-way) | 0.0010 (same as thai_equity) |
| FX friction | 0.0 (baked into DR price) |

DRs trade on SET hours in THB, so they follow the thai_equity calendar and
friction model.

## Sector Guard

All DRs are classified as sector `"Global"`. The sector guard (max 2 positions
per sector) treats them as a separate bucket from thai_equity sectors like
"Banking" or "Energy". This prevents a DR from competing with a Thai bank
for sector slot. This bucket is **on top of**, not a substitute for, the
same-underlying guard in "Overlap With Existing Universe" above — two
different DRs on two different underlyings can both be "Global"; the same
underlying twice (once direct, once via DR) cannot.

## User Workflow

### Initial setup
1. Author `data/dr/seed_list.json` with the initial candidate list (see
   Open Question 4, resolved below)
2. Run `python scripts/dr/discover_drs.py` → generates `data/dr/mapping.json`
   from the seed list plus a secondary scan
3. User opens the JSON, reviews each entry, sets `verified: true/false`
4. Optionally sets `primary_dr` per underlying (overrides liquidity ranking)
5. Pipeline now includes verified DRs in the investable universe via
   `get_verified_dr_tickers()` → `trade_gen.TRADABLE_TICKERS`

### Periodic maintenance
1. Re-run `scripts/dr/discover_drs.py` weekly/monthly
2. New DRs appear as `verified: false` — user reviews
3. Stale DRs (delisted) detected via download failure → flagged for user

## Open Questions — resolved

1. **DR liquidity threshold:** Resolved as `MIN_DR_HISTORY = 60` rows (not a
   volume floor) — a DR needs enough history to compute meaningful
   liquidity/premium stats, not a specific volume cutoff. Volume itself is
   only used for *ranking* alternatives against each other, not as a
   pass/fail gate; a low-volume DR with no verified competitor is still
   usable if the user marks it verified (it's their liquidity risk to accept).
2. **fx_ticker discovery:** Resolved as hardcode `THB=X` for all DRs — every
   DR trades in THB on SET regardless of underlying currency, so a single FX
   pair converts every underlying's local-currency price back to THB; no
   auto-detection needed. `underlying_currency` in the mapping is metadata
   only (for display), not used to pick the FX ticker.
3. **Premium/discount threshold:** Resolved as ±5%, `DR_PREMIUM_WARN_THRESHOLD`
   in `universe.py` (see "Intrinsic Value & Premium Tracking" above).
4. **Initial user list:** Resolved as a hand-curated `data/dr/seed_list.json`
   (see "Discovery Logic"), prioritizing **HK/JP/KR/EU names with no existing
   direct-access asset class** (e.g. Samsung, Tencent, Toyota, ASML) —
   reversed from the original "US mega-caps first" framing, since US names
   are largely already covered by `us_equity` (see "Overlap With Existing
   Universe").

## Out of Scope

- DRs for non-equity assets (ETFs, bonds, commodities)
- Real-time DR premium/discount alerts
- Auto-trading DR arbitrage (buy cheap DR, sell expensive DR)
- Non-SET DRs (listed on Singapore, London, etc.)
