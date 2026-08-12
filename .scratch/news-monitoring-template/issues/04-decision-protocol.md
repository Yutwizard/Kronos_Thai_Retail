# 04 - Design the red-flag → skip/flag decision protocol

Type: grilling
Status: resolved

## Question

Design the lightweight decision protocol referenced in the map's
Destination: simple rules of thumb for when a news finding should make the
investor manually skip or flag a trade in the dashboard's paper-trading
ticket, before it executes.

Grill the user to pin down, at minimum:

- What counts as a "red flag" worth acting on (e.g. primary-source-only,
  or does a secondary-source report from a reputable outlet also qualify
  if primary sources haven't caught up yet)?
- Does severity matter (e.g. a regulatory investigation vs a routine
  earnings miss vs a management resignation) — one uniform rule, or a
  small taxonomy?
- Scope of action: skip only the flagged ticker's trade, or does a
  macro-level red flag (e.g. surprise BoT rate move) affect the whole
  day's top-10 batch?
- How does this interact with a DR vs its underlying — does a red flag on
  the underlying's home-market news apply to the DR trade the same way?
- Where does the investor record that they overrode/skipped a signal for
  this reason (does the existing paper-trading ticket flow in the
  dashboard have a place for a note, or does the template need to define
  one)?

Keep the protocol simple — it's a heuristic for human judgment, not a
formal rules engine, and explicitly does not touch pipeline/model code or
`rank_score`.

## Answer

Grilled and confirmed with the user. **Fact found first** (not asked, looked
up): the dashboard's paper-trading flow already has an override-recording
mechanism — `data/positions/morning_log.md` (Step 9 of
`docs/morning-paper-trading-guide.md`) logs a free-text Reason when staying
in cash, with "Manual override" already one of the enumerated options.
There is no reason/note field in the `/api/trades` API itself — the record
lives in that separate markdown journal, not the dashboard's data model.

**The protocol:**

1. **Trigger threshold:** a red flag can come from either a primary source
   (SET/Thai SEC/BoT disclosures, or AMF/CONSOB/company IR/SEC EDGAR for DR
   names) *or* a reputable secondary source (the tiered press lists from
   tickets 01/02) — doesn't require primary-source confirmation first,
   since primary disclosures often lag same-day press (and tickets 01/02
   found several primary feeds are slow or non-existent, e.g. SET's own
   RSS is dead).
2. **Fixed skip-trigger list** — only these five cause an action, everything
   else (routine earnings misses/beats, analyst rating changes, guidance
   revisions, ordinary management reshuffles, mechanical DR ratio/conversion
   notices) is informational only, never a trigger on its own:
   - Trading halt / suspension
   - Cash-balance-only or caution-list designation
   - Fraud allegation or regulatory investigation/enforcement action
   - Auditor's qualified opinion, disclaimer, or going-concern flag
   - Sudden, unscheduled C-suite departure (not a scheduled/planned
     transition)
3. **Scope:** strictly single-ticker. Skip only the flagged name's trade —
   no macro-level override in this protocol. The dashboard's existing
   Market State/Turmoil gate already handles systemic days, and CLAUDE.md
   already retracted manually overriding allocation based on a perceived
   macro regime (the regime-conditional-alpha decision) — this protocol
   deliberately doesn't reintroduce that pattern via a news-driven back
   door.
4. **DR-specific addition:** for DR trades, also check the KTB/BLS
   issuer-page DR-mechanics channel (ticket 02) — a ratio/conversion event
   severe enough to pair with a trading-halt-equivalent triggers a skip
   even if nothing shows up in the underlying's home-market news, since
   this failure mode has no equivalent on the Paris/Milan/Copenhagen side.
5. **Recording:** log it in the existing `data/positions/morning_log.md`
   Reason field, using a consistent phrasing convention:
   `Reason: Manual override — news red flag ([trigger type], [source])`.
   No new field, no dashboard/API change — reuses infrastructure that
   already exists.

Status: resolved.
