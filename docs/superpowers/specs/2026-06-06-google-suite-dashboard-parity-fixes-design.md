# Google Suite Dashboard Parity Fixes — Design Spec

**Date:** 2026-06-06
**Status:** Draft (pending review)
**Supersedes:** Nothing — additive to `2026-06-04-google-suite-dashboard-design.md`
**Target files:** `google_suite/build_notebook.py`, `google_suite/kronos_daily_pipeline.ipynb`, `google_suite/apps_script/Code.gs`, `google_suite/apps_script/Index.html`, `google_suite/SETUP_GUIDE.md`, `google_suite/README.md`

## 1. Problem statement

The Google Suite dashboard (Layer 5 migration, shipped 2026-06-04) achieves broad feature parity with the local Flask dashboard, but a 2026-06-06 audit found 14 misalignments — 3 critical, 6 significant, 5 cosmetic. This spec brings the Google Suite to full feature parity, fixes the data integrity issues, and adds the missing safety net (Reset Capital) and observability (Health Banner).

The goal: a user who has run paper trading for 30 days should not be able to tell that the local Flask dashboard and the Google Suite dashboard were built by different people for different environments.

## 2. Goals and non-goals

### Goals
- Equity Curve grows daily (currently freezes after one-time migration)
- Trade Log supports inline edit + delete from the web app (currently read-only)
- Initial capital can be set or reset from the web app (currently requires editing a Colab cell)
- Signal health banner shows up if model accuracy diverges from backtest
- Position rows show the same red/orange/green border colors as Flask
- Dashboard auto-refreshes every 60 seconds during a pipeline run
- Mock data renders identical to real data
- User can close modals with the Esc key
- Documentation reflects the new features

### Non-goals
- No new asset classes or new strategy variants
- No migration of historical Flask data — fresh-start only (migration script already exists for that)
- No multi-user support — still single-user paper trading
- No real-time data — still end-of-day OHLCV
- No broker integration — still paper trading only
- No changes to kth/ trading/portfolio.py or trade_gen.py — Apps Script uses the same Python functions via a new "Colab Cell 9b" step

## 3. Architecture overview

No architectural change. The JSON-bridge pattern (`Sheets → Drive JSON → kth functions → Drive JSON → Sheets`) is preserved. All changes are additive.

**New notebook cells (additive):**
- Cell 11b — Compute Calibration (writes to new `Calibration` sheet)
- Cell 13b — Append Equity Curve to Staging (adds to `STAGING_MAP`)
- Cell 4b — Apply Capital Reset (reads new `Capital Reset` staging, calls `reset_portfolio()`)
- Cell 9b — Apply Trade Edits (reads new `Trade Edits` staging, calls `edit_trade()` / `delete_trade()`)

Cells 4b and 9b re-run the staging writes (currently in Cell 13) and the staging → live promotion (currently in Cell 14) so the changes from those operations are visible in the live sheets. The pipeline contract is preserved: the same sheets are written, just from one of two paths. The 19-cell normal-path is unchanged; the edit-path is a 2-cell (or 11-cell) superset.

**New Apps Script functions:**
- `submitTradeEdit(index, newShares, newPrice)` — queues an edit
- `submitTradeDelete(index)` — queues a delete
- `getPendingEdits()` — returns queued edits for the UI banner
- `resetCapital(newCapital, confirmText)` — queues a portfolio reset
- `getSetupStatus()` — returns `{isFirstRun, hasTrades, currentCapital}` for first-run UI
- `getHealthCheck()` — reads last row of `Calibration` sheet, returns banner state

**New `Index.html` UI additions:**
- 5 lines of CSS for row border colors
- Auto-refresh setInterval
- Esc-key handler for modals
- Edit / Delete buttons in Trade Log
- Reset Capital modal with typed confirmation
- Health banner on Dashboard tab
- `date_updated` field on MOCK forecasts

**Documentation updates:** `SETUP_GUIDE.md` (3 sections touched + 1 new section), `README.md` (1 line).

## 4. Detailed design

### 4.1 Equity Curve append (Item A1 — Critical)

**Problem:** `Equity Curve` sheet is read by Cell 9 (build_notebook.py:228) and rendered by the Apps Script chart (Code.gs:62), but never written by the Colab pipeline. After the one-time `migrate_to_sheets.py` runs, the curve is frozen.

**Solution:** Add a new "Cell 13b — Append Equity Curve to Staging" that appends today's row.

**Implementation:**

1. New sheet `Equity Curve_staging` (header row only, no data). Add to `SETUP_GUIDE.md` tab-creation table.
2. New code cell in `build_notebook.py` (between current Cells 13 and 14):
   ```python
   _write_staging('Equity Curve_staging',
       ['date', 'equity', 'cash', 'invested'],
       [[today_str, round(equity, 2), round(pf_data['cash'], 2),
         round(equity - pf_data['cash'], 2)]])
   ```
3. Add `'Equity Curve_staging': 'Equity Curve'` to `STAGING_MAP` in Cell 14.
4. Sheet stays bounded: `Apps Script _readSheetLimited(..., 90)` already limits to last 90 rows. After 90 days the chart shows only the last 90 days (acceptable).

**Verification:** Run pipeline on a test day → confirm `Equity Curve` sheet has one new row per day.

### 4.2 Document field divergences (Item A2)

**Problem:** Three place where the Colab notebook diverges from the kth API surface and is not documented. Future refactors will silently break the dashboard contract.

**Solution:** Add inline comments in `build_notebook.py` at the three locations.

**Locations and comments:**

1. Cell 13, Positions write (around build_notebook.py:415):
   ```python
   # NOTE: `current_price` and `pct_to_stoploss` are computed locally from
   # `ohlcv_dict[ticker]['close'].iloc[-1]`, NOT from `get_positions()`.
   # `get_positions()` returns `mark` (not `current_price`) and no stop-loss column.
   # Do not refactor to use `get_positions()` here without updating
   # the Positions sheet schema and Index.html renderPositions().
   ```

2. Cell 13, Risk Metrics write (around build_notebook.py:452):
   ```python
   # NOTE: Risk Metrics sheet headers are intentionally renamed from
   # compute_metrics() output keys. The Apps Script Index.html renders
   # columns by the SHEET header names (e.g. `trailing_sharpe_12w`),
   # not the Python return-key names (e.g. `sharpe`). Keep the rename
   # table below in sync with renderDashboard() and renderPositions().
   ```

3. Top of `build_notebook.py` (line ~1, in module docstring): add a "Schema contract" section listing the 9 sheets and which functions read each one. This is a 20-line reference for future maintainers.

**Verification:** Re-read the comments and the sheet-creation table side by side; confirm zero ambiguity.

### 4.3 Trade Log inline edit + delete (Item B1 — Significant)

**Problem:** Flask dashboard supports inline edit (price + shares) and delete on every trade (dashboard.html:706-803). The Google Suite Trade Log tab is read-only.

**Solution:** Add three Apps Script backend functions + matching UI.

**Backend (`Code.gs`):**

1. `submitTradeEdit(index, newShares, newPrice)`:
   - Validates `newShares` is a positive multiple of 100
   - Validates `newPrice` > 0
   - Validates the trade index exists in the Trade Log sheet
   - Reads the current row, applies the change in-memory
   - Calls a new Colab cell (Cell 9b) to rebuild the portfolio JSON
   - **Atomicity:** the Apps Script does NOT write back to the Trade Log sheet directly. Instead it appends a "pending_edit" row to a new "Trade Edits" staging sheet and prompts the user to re-run Colab cells 9–15. **Reason:** rebuilding the Portfolio/Positions/Equity Curve/Risk Metrics sheets requires running the same Python logic as Cells 13/14. Doing that in Apps Script (no Python) would duplicate the kth code. The pending_edit approach keeps a single source of truth.
   - Returns `{ok: true, status: "edit queued — please re-run Colab cells 9-15"}`

2. `submitTradeDelete(index)`:
   - Validates the index exists
   - Appends a `{action: "CANCEL", ref_id: <existing trade_id>}` row to Trade Edits staging
   - Returns same status as above

3. `getPendingEdits()`:
   - Returns pending edits from the Trade Edits sheet for the UI to display a "1 pending edit — re-run Colab" banner
   - Cleared automatically when the user runs Cell 9b (which reads + applies + clears the sheet)

**New Colab cell (Cell 9b):** "Apply Trade Edits to Local JSON". Reads Trade Edits staging, applies each edit/delete to the local `paper_portfolio.json` via `edit_trade()` and `delete_trade()`, clears the Trade Edits sheet, then runs the same staging-write + staging-promote logic as Cells 13/14. The user runs Cell 9b **instead of** Cells 9–15 in a single Colab session.

**UI (`Index.html`):**
- Trade Log table gains two new columns: ✏️ Edit, 🗑️ Delete (icons only)
- Click ✏️ → modal with Shares input + Price input + "Save Edit" + "Cancel"
- Click 🗑️ → `confirm()` dialog → on OK, call `submitTradeDelete(index)` → show "Edit queued — re-run Colab" banner
- Banner persists on Dashboard tab (top of page) until `getPendingEdits()` returns empty

**Trade-offs accepted:** The user must switch to Colab and click "Run" on Cell 9b to apply an edit. This is more friction than Flask (which does it instantly). The trade-off is worth it because: (a) Colab is the only environment with Python, (b) `edit_trade()` rebuilds the portfolio from FIFO and any race condition in Apps Script would be hard to test, (c) the user is already in Colab every morning for the pipeline.

**Verification:** Edit a trade in MOCK mode → confirm modal flow → confirm "edit queued" banner shows → re-run pipeline in MOCK → confirm Trade Log shows the new price.

### 4.4 Initial capital UI (Item B2 — Significant)

**Problem:** Flask shows a setup banner on first load (dashboard.html:54-61). Google Suite has no UI to set or change initial capital.

**Solution:** First-run setup banner + permanent Settings button with destructive Reset flow.

**Backend (`Code.gs`):**

1. `resetCapital(newCapital, confirmText)`:
   - Validates `1 <= newCapital <= 100_000_000`
   - For the destructive path (Reset Portfolio), validates that `confirmText === "RESET"`
   - For the first-run setup path, validates that `confirmText === "SETUP"`
   - Appends a single row to the `Capital Reset` staging sheet with columns `[action, capital, confirm_text, requested_at]`
   - Returns `{ok: true, status: "reset queued — re-run Colab cells 4b-15"}`
   - The new capital is read from the staging sheet by Cell 4b, not from the Apps Script parameter (to keep a single source of truth).

2. New Colab cell (Cell 4b): "Apply Capital Reset". Reads Capital Reset staging, calls `reset_portfolio()`, clears the staging sheet, then runs the same staging-write + staging-promote logic as Cells 13/14. The user runs Cell 4b **instead of** Cells 5–15 in a single Colab session.

3. `getSetupStatus()`: Returns `{isFirstRun: bool, hasTrades: bool, currentCapital: number}` so the UI can decide whether to show the setup banner.

**UI (`Index.html`):**
- **First-run banner** (top of Dashboard tab, only when `getSetupStatus().isFirstRun === true`): blue banner with capital input (default 500,000) + "Start Paper Trading" button. On click, calls `resetCapital(newCapital, "SETUP")`. Banner shows "Setup queued — open Colab and run Cell 4b" with a 60s auto-dismiss.
- **Settings button** (⚙ icon, top-right of Dashboard tab, always visible): opens a modal showing current capital + a "Reset Portfolio" button. The button is RED and disabled until the user types "RESET" in a confirmation text input.
- **Reset is destructive** — clears Trade Log, Equity Curve, Positions, Risk Metrics. Requires typed confirmation. Warns user with: "This will delete all N trades. Type RESET to confirm."

**Trade-offs accepted:** Two-step setup (queue via Apps Script → run Colab cell) is the only way without writing a full Python runtime in Apps Script. We accept this because (a) the user runs Colab every morning anyway, (b) the first-run experience is "set capital in UI → click Start → instructions say 'open Colab and run Cell 4b'".

**Verification:** Fresh install → setup banner shows → enter 250,000 → "queued" → run Colab → confirm Portfolio sheet shows 250,000 cash.

### 4.5 Signal health banner (Item B3 — Significant)

**Problem:** Flask shows a signal health banner (dashboard.html:47-51) that warns if model accuracy diverges from backtest. Google Suite has no equivalent.

**Solution:** Add a new sheet + new Colab cell + new Apps Script function.

**Backend:**

1. New sheet `Calibration` (1 row per pipeline run). Columns: `date, coverage, n_samples, mean_predicted_return, mean_actual_return, accuracy_pct, backtest_baseline, status`.
2. New Colab cell (Cell 11b): "Compute Calibration". Calls `compute_calibration()` from `kth.backtest.metrics`, writes to Calibration sheet (append, never overwrite).
3. New Apps Script function `getHealthCheck()`: reads last row of Calibration sheet, returns `{accuracy, baseline, divergence, status, recommendation}`.
4. Recommendation rule: if `accuracy < baseline - 0.10` → "halve position sizes" (matches Flask). Else if `accuracy < baseline - 0.05` → "monitor". Else "ok".

**UI (`Index.html`):**
- Banner on Dashboard tab, between status banner and Capital card
- Green ("✅ Model accuracy 58% vs baseline 57% — on track")
- Yellow ("⚠ Model accuracy 52% vs baseline 57% — monitor")
- Red ("🚨 Model accuracy 44% vs baseline 57% — halve position sizes")

**Verification:** Run pipeline on a test day → confirm Calibration sheet has 1 row → confirm banner shows.

### 4.6 Position row border color (Item B4 — Cosmetic)

**Problem:** Flask positions table uses `row-exit` / `row-reduce` / `row-hold` CSS classes for visual signal. Google Suite has inline color only.

**Solution:** Add CSS rules + apply the classes in `renderPositions()`. Compute `direction` from `exp_ret` at render time (the Forecasts sheet has no `direction` column).

**CSS additions to `Index.html` (after line 60):**
```css
tr.row-hold  { border-left: 4px solid var(--green); }
tr.row-reduce { border-left: 4px solid var(--yellow); }
tr.row-exit  { border-left: 4px solid var(--red); }
```

**JS additions to `renderPositions()` (after line 467, before `<tr>`):**
```js
var dir = fc.exp_ret > 0 ? 'up' : 'down';
var rowCls = '';
if (dir === 'down' && fc.confidence === 'green') rowCls = 'row-exit';
else if (fc.confidence === 'yellow') rowCls = 'row-reduce';
else if (dir === 'up') rowCls = 'row-hold';
return '<tr class="' + rowCls + '">' + ...
```

**Verification:** With MOCK data, the position table shows colored left borders on the 2 example positions.

### 4.7 Auto-refresh + cache TTL (Items C1 + C2)

**Problem:** Flask auto-refreshes every 60s (dashboard.html:681). Google Suite has only a manual Refresh button. Plus the 300s cache means a running pipeline shows stale "completed" status.

**Solution:** 60s polling + reduce Pipeline Status cache TTL.

**JS additions to `Index.html` (end of file, before `</script>`):**
```js
var _lastRefreshAt = 0;
setInterval(function() {
  if (document.hidden) return;
  if (Date.now() - _lastRefreshAt < 30000) return;  // skip if user just refreshed
  refreshData();
}, 60000);
```

Modify `refreshData()` to set `_lastRefreshAt = Date.now()` at the start.

**Code.gs change:**
- In `getAllData()` (line 52-74): change `if (json.length < 100000) cache.put('all_data', json, 300);` to use a per-key TTL: `cache.put('all_data', json, 60);` (60s instead of 300s). Trade-off: more API calls (was every 5min, now every 1min). Cost: $0.04/day for 100 daily reads, negligible.
- Add a `bustCache` flag: when `?bustCache=1` is passed to `refreshAllData()`, skip the cache read entirely. Caller (the JS) can use this if it knows the data just changed (e.g., after a fill).

**Verification:** Open dashboard → wait 60s → confirm data refreshes (visible in Network tab).

### 4.8 Documentation updates (Item D1 + D2)

**SETUP_GUIDE.md changes:**

1. **Section "Step 3.6: Upload project folder to Google Drive"** (already exists) — add a note: "Apps Script will keep the same URL across deploys only if you DO NOT create a new deployment. Edit the existing one to publish new code."
2. **Tabs table** — add `Equity Curve_staging` and `Equity Curve` to the list (it was missing).
3. **Section "What you'll see"** — add bullet points: "Reset Portfolio (⚙) — change initial capital", "Trade Log edit/delete — click ✏️ or 🗑️", "Health banner — shows on Dashboard if model diverges".
4. **New section "Editing a trade"** — explain the queue + re-run pattern (2 paragraphs).

**README.md changes:**
- One new line in the "Google Suite dashboard" bullet: "Trade Log inline edit, Reset Capital modal, Signal Health banner, row border colors, 60s auto-refresh."

### 4.9 Mock data + Esc key (Items E1, E3)

**E1: MOCK.forecasts `date_updated` field:**
Add `date_updated: '2026-06-04'` to each of the 3 MOCK forecast entries. Pure cosmetic — only affects MOCK mode. The real Forecasts sheet has this field; MOCK was missing it.

**E3: Esc closes modals:**
Add to `Index.html` (before the closing `</script>`):
```js
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeFillModal();
    var sm = document.getElementById('settings-modal');
    if (sm && !sm.hidden) sm.hidden = true;
    var em = document.getElementById('edit-trade-modal');
    if (em && !em.hidden) em.hidden = true;
  }
});
```

## 5. Edge cases and error handling

| Scenario | Behavior |
|---|---|
| First run (no Portfolio row) | Setup banner shows with default 500,000 THB |
| User changes capital mid-portfolio (has trades) | "Reset Portfolio" button is RED + requires typed "RESET" + shows trade count warning |
| User edits a trade that has already been used in a closed round-trip | Apps Script warns "this trade is part of a closed position — recomputing FIFO may change historical metrics. Continue?" |
| User tries to edit shares below board lot (not multiple of 100) | Modal shows error: "Shares must be a multiple of 100" |
| User opens dashboard during pipeline run | Status banner says "Pipeline running…" within 60s (cache TTL) |
| Pipeline fails mid-run | Status banner shows "Pipeline failed: <error>" with red color |
| Equity Curve sheet has 90+ rows | Apps Script reads only last 90 (existing `_readSheetLimited` handles this) |
| User opens dashboard with no data at all | All 5 tabs show empty state with helpful messages (already implemented) |
| Two users open the same Apps Script URL | No conflict — Apps Script is single-user-per-deployment; shared URLs are read-only views |
| Apps Script quota exceeded (rare) | Status banner shows "Apps Script quota — try again in 1 minute" |

## 6. Testing approach

**Manual smoke test (one afternoon):**
1. Fresh install: clone repo, run Colab, run SETUP_GUIDE steps 1-5
2. Setup banner appears on Dashboard → enter 600,000 → click "Start" → re-run Colab Cell 4b → confirm Portfolio sheet shows 600,000
3. Run pipeline 3 days in a row (with synthetic data)
4. Day 2: confirm Equity Curve sheet has 2 rows
5. Day 3: open dashboard, edit a trade in MOCK mode → modal works → trade queued
6. Day 3: re-run Colab cells 9-15 → trade reflects new value
7. Day 3: dashboard auto-refreshes after 60s (open DevTools Network tab)
8. Day 3: open Trade Log → click 🗑️ on a trade → confirm dialog → "delete queued" banner shows
9. Day 3: reset capital via Settings → type "RESET" → confirm → "reset queued" → re-run Colab
10. Day 3: position table has colored left borders

**No automated tests** (project doesn't use pytest, per AGENTS.md). All verification is by inspecting Sheets content + Apps Script UI.

## 7. Out of scope (future specs)

- Multi-user support (would need OAuth + per-user Spreadsheet)
- Real-time prices (would need streaming API)
- Broker integration (still paper only)
- Mobile app (Apps Script is mobile-friendly enough)
- Historical backfill UI (Flask has `/api/forecasts/dates` — could be ported later)

## 8. Migration / rollout

**Sheet count change:** The current SETUP_GUIDE creates 14 tabs (9 live + 5 staging). This spec adds 4 new sheets:
- `Equity Curve_staging` (adds to the staging list — replaces 1 of the original 5 staging entries because Equity Curve was previously a live-only sheet; the live `Equity Curve` sheet already exists)
- `Calibration` (new live sheet)
- `Trade Edits` (new staging sheet, written by Apps Script, read by Colab Cell 9b)
- `Capital Reset` (new staging sheet, written by Apps Script, read by Colab Cell 4b)

New total: 17 tabs (11 live + 6 staging). The SETUP_GUIDE tab-creation table will be updated.

**No data migration required** for existing users. All changes are additive to existing sheets. New sheets are empty until first pipeline run. Existing `Equity Curve` sheet keeps its data; the new `Equity Curve_staging` is a one-row header-only sheet.

**Rollout:** Commit and push. Existing users re-run the SETUP_GUIDE step that creates the new sheets. New users follow the full updated guide.

**Backwards compatibility:** All changes are forward-compatible. Existing sheets keep their schemas.

## 9. Open questions

None. All 14 items have concrete designs.

## 10. References

- `docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md` — original Google Suite spec
- `docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md` — Flask dashboard spec (companion — both available)
- `scripts/dashboard.py` — Flask backend (450 lines, the source of parity)
- `scripts/static/dashboard.html` — Flask frontend (888 lines)
- `google_suite/build_notebook.py` — Colab notebook generator (668 lines, target of edits)
- `google_suite/apps_script/Code.gs` — Apps Script backend (136 lines, target of edits)
- `google_suite/apps_script/Index.html` — Apps Script frontend (851 lines, target of edits)
- `kth/trading/portfolio.py` — kth portfolio module (defines `edit_trade`, `delete_trade`, `reset_portfolio`, `compute_metrics`)
- `kth/trading/trade_gen.py` — kth trade ticket generator (defines `generate_trade_ticket`, `load_trade_ticket`)
- `kth/backtest/metrics.py` — kth metrics module (defines `compute_calibration`, `compute_bootstrap_pvalue`, `compute_sortino`, `compute_drawdown_velocity`)
