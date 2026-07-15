# DR (Depositary Receipt) data — seed list, discovery, verification

How a DR goes from "candidate" to "tradable". Nothing trades until a human
completes step 3 — that is by design, not a missing feature.

## Files

- `seed_list.json` — hand-curated candidates, committed to git.
  Format: `underlying ticker -> [DR candidates]`. **Key by the home-market
  listing** (`7203.T`, `ASML.AS`), never a US ADR (`TM`, `ASML`) — any
  US-listed stock is already directly buyable by a Thai investor, so a DR on
  a US ADR has no reason to exist (see `kth/data/universe.py` us_equity notes).
  **Issuer policy**: only DRs issued by a Thai bank or a securities-firm
  subsidiary of one — KTB (Krungthai Bank, ticker suffix `80`), BLS (Bualuang
  Securities/Bangkok Bank, suffix `01`), INVX (InnovestX/SCBX-Siam Commercial
  Bank, suffix `23`). Do not add Yuanta Securities (Thailand) (suffix `19`,
  a Taiwan Yuanta Financial Holdings subsidiary) or KGI Securities (suffix
  `13`, also Taiwan-affiliated) — confirmed empirically that each numeric
  ticker suffix maps 1:1 to one issuer.
- `mapping.json` — **generated** by discovery, then hand-edited to verify.
  **Committed to git** (not left to regenerate) — Kaggle notebook runs are
  ephemeral, so the human-verification work (`verified` flags and their
  `verified_note` sourcing) would be lost between sessions otherwise. The
  pipeline degrades gracefully to "no DRs" if it is absent or malformed (a
  hand-edit typo logs a warning and disables DRs for that run — it does not
  crash the daily pipeline).

## Workflow

1. **Add a candidate** to `seed_list.json` (underlying keyed by home listing,
   with `dr_ticker`, `display_name`, `underlying_exchange`,
   `underlying_currency`, `ratio`).
2. **Run discovery** on a network-enabled machine (Colab/Kaggle/local):
   `python scripts/dr/discover_drs.py`. This downloads DR history, computes
   `avg_volume_30d` / `history_rows` / `listing_date`, derives `fx_ticker`
   from `underlying_currency` (`KRW` → `KRWTHB=X`; `USD` → `THB=X`), and
   writes `mapping.json` with `"verified": false` and
   `_meta.status: "needs_review"`. Re-running discovery never un-verifies an
   entry you already approved.
3. **Verify by hand** — open `mapping.json` and flip `"verified": true` only
   after checking, per DR:
   - the DR actually tracks the claimed underlying (check the SET factsheet
     at set.or.th — search the DR ticker),
   - the `ratio` matches the factsheet (DR-per-underlying conversion),
   - `avg_volume_30d` is liquid enough to exit a position in one session
     (rule of thumb: your position ≤ 10% of a day's volume),
   - `history_rows >= 60` (`MIN_DR_HISTORY` in `kth_dr/universe_dr.py`).

   Where to find the ratio, by issuer:
   - **KTB**: `krungthai.com/th/content/depositary-receipt/stock-dr/<ticker
     lowercase>` — a static page, plain fetch works.
   - **BLS**: `bualuang.co.th/en/financial-service/inav-lists/dr/dr01-inav/<ticker
     lowercase>` — static, plain fetch works.
   - **INVX**: `dr23.innovestx.co.th/dr/product/<TICKER>` — a JS-rendered SPA,
     a plain HTTP fetch returns an empty shell. Render it first:
     `google-chrome --headless=new --disable-gpu --no-sandbox --dump-dom
     --virtual-time-budget=8000 <url>`, then look for the field labeled
     `อัตราแปลงสภาพ` (conversion ratio), format `<DR units>:1`. Always
     cross-check the scraped number against live prices before trusting it:
     `implied_ratio = (underlying_close * fx_close) / dr_close` should land
     within a few percent of the scraped value (that gap is the DR's real
     premium/discount, not scrape error) — a bigger mismatch means re-scrape
     or find another source before flipping `verified: true`.
4. **Done.** On the next pipeline run the DR registers with the universe
   (class `dr`, sector `Global`), its underlying joins the forecast loop, and
   trade tickets key money fields off the DR's own SET close.

An entry with `"excluded_reason"` is skipped everywhere. `_meta` and
`_unresolved` are bookkeeping keys, ignored by all lookups.
