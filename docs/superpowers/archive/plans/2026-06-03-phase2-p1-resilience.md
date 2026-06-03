# Phase 2 — P1 Resilience

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Complete Phase 1 (P0 bug fixes) before starting this phase.

**Goal:** Three resilience improvements — sector concentration guard prevents correlated position blowups; atomic portfolio write prevents data loss on crash; forecast partial-failure recovery avoids losing completed ticker forecasts on pipeline retry.

**Decisions locked (grilling session 2026-06-03):**
- Sector data: add `SECTOR` dict + `get_sector()` to `universe.py` (explicit, version-controlled). Map all 50 thai_equity tickers to 10 SET-standard sector labels.
- Sector cap: max 2 positions per sector (hard filter in buy loop, not a warning).
- Atomic write: write to `.tmp` file then `os.replace()` — one line change.
- Forecast recovery: check if per-ticker parquet exists and was written today before re-running that ticker.

**Estimated time:** ~2 hours total.

---

### File Structure

| Action | Path | Change |
|--------|------|--------|
| Modify | `kth/data/universe.py` | Add `SECTOR` dict + `get_sector()` helper |
| Modify | `kth/trading/trade_gen.py` | Sector guard in buy loop |
| Modify | `kth/trading/portfolio.py` | Atomic write for `paper_portfolio.json` |
| Modify | `scripts/dashboard.py` | Skip already-forecasted tickers on `--generate` retry |

---

### Task 1 — Add SECTOR dict to universe.py

**File:** `kth/data/universe.py`

Add after the `UNIVERSE` and `FRICTION` dicts (append before the helper functions).

- [ ] **Step 1: Add `SECTOR` dict** mapping every `thai_equity` ticker to one of 10 SET-standard sector labels:

```python
# SET sector classification for thai_equity tickers.
# Used by the sector concentration guard (max 2 positions per sector).
SECTOR: dict[str, str] = {
    # Banking (7)
    "KBANK.BK": "Banking", "SCB.BK": "Banking", "BBL.BK": "Banking",
    "KTB.BK":   "Banking", "TISCO.BK": "Banking", "TCAP.BK": "Banking", "KKP.BK": "Banking",
    # Energy (10)
    "PTT.BK":   "Energy", "PTTEP.BK": "Energy", "BGRIM.BK": "Energy", "GPSC.BK": "Energy",
    "TOP.BK":   "Energy", "IRPC.BK":  "Energy", "BANPU.BK": "Energy", "BCP.BK":  "Energy",
    "RATCH.BK": "Energy", "GULF.BK":  "Energy",
    # Property (7)
    "LH.BK":    "Property", "QH.BK":   "Property", "AP.BK":   "Property", "ORI.BK":  "Property",
    "SIRI.BK":  "Property", "PSH.BK":  "Property", "CPN.BK":  "Property",
    # Healthcare (4)
    "BDMS.BK":  "Healthcare", "BH.BK": "Healthcare", "BCH.BK": "Healthcare", "CHG.BK": "Healthcare",
    # Retail (6)
    "CPALL.BK": "Retail", "HMPRO.BK": "Retail", "CRC.BK":    "Retail",
    "GLOBAL.BK":"Retail", "DOHOME.BK":"Retail",  "MEGA.BK":   "Retail",
    # Hospitality & Tourism (4)
    "MINT.BK":   "Hospitality", "CENTEL.BK": "Hospitality",
    "ERW.BK":    "Hospitality", "AOT.BK":    "Hospitality",
    # Telecom (2)
    "ADVANC.BK": "Telecom", "TRUE.BK": "Telecom",
    # Food & Beverage (3)
    "CPF.BK": "Food", "OSP.BK": "Food", "ICHI.BK": "Food",
    # Tech & Electronics (3)
    "JMART.BK": "Tech", "HANA.BK": "Tech", "DELTA.BK": "Tech",
    # Logistics & Infrastructure (2)
    "BEM.BK": "Logistics", "BTS.BK": "Logistics",
    # Other / Diversified (2)
    "IVL.BK": "Other", "SCC.BK": "Other",
}
```

- [ ] **Step 2: Add `get_sector()` helper** alongside the existing `get_ticker_class()` and `get_display_name()`:

```python
def get_sector(ticker: str) -> str:
    """Return SET sector label for a thai_equity ticker. Returns 'Other' for non-Thai tickers."""
    return SECTOR.get(ticker, "Other")
```

- [ ] **Step 3: Verify** — total entries in SECTOR dict must equal 50 (all thai_equity tickers):

```python
python -c "from kth.data.universe import SECTOR, UNIVERSE; thai = [t for t,_,_ in UNIVERSE['thai_equity']]; assert set(thai) == set(SECTOR.keys()), f'Missing: {set(thai)-set(SECTOR.keys())}'; print(f'OK — {len(SECTOR)} tickers mapped')"
```

---

### Task 2 — Sector concentration guard in buy loop

**File:** `kth/trading/trade_gen.py`

**Context:** The buy loop (currently lines 160–185) fills up to `slots` positions by ranked signal. It has no awareness of sector exposure. With 5 max positions, 3 banking picks = 60% banking — a single sector shock wipes the portfolio.

- [ ] **Step 1: Import `get_sector`** at the top of `trade_gen.py`:

```python
from kth.data.universe import UNIVERSE, FRICTION, get_ticker_class, get_display_name, get_sector
```

- [ ] **Step 2: Add sector counter** just before the buy loop:

```python
MAX_SECTOR_POSITIONS = 2
sector_counts: dict[str, int] = {}
# Seed with sectors already held (from existing positions, not being exited)
for ticker in held_tickers:
    if ticker not in [e["ticker"] for e in exits]:
        sec = get_sector(ticker)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
```

- [ ] **Step 3: Add sector guard check** inside the buy loop, before the `lots` calculation:

```python
for rank_idx, f in enumerate(forecasts, 1):
    if len(buys) >= slots:
        break
    if f["ticker"] in held_tickers:
        continue
    if f["net_ret"] <= f["friction_rt"]:
        continue
    if f["confidence"] == "red":
        continue

    # --- SECTOR GUARD ---
    sec = get_sector(f["ticker"])
    if sector_counts.get(sec, 0) >= MAX_SECTOR_POSITIONS:
        continue
    # ---

    per_slot = remaining_cap / max(slots - len(buys), 1)
    lots = int(per_slot / f["close"] / 100) * 100
    if lots < 100:
        continue

    limit = round(f["close"] * (1 + f["exp_ret"] / 2), 2)
    buys.append({
        "ticker": f["ticker"],
        "name": f["name"],
        "shares": lots,
        "order_type": "limit",
        "limit_price": limit,
        "estimated_thb": round(lots * f["close"]),
        "rationale": f"🟢↑ rank#{rank_idx} net_ret={f['net_ret']:+.2%}",
    })
    sector_counts[sec] = sector_counts.get(sec, 0) + 1
    remaining_cap -= lots * f["close"]
```

- [ ] **Step 4: Verify** — write a quick mental test: if top 5 ranked are all Banking, only first 2 are bought and the loop continues to find non-Banking picks for slots 3–5.

---

### Task 3 — Atomic write for portfolio JSON

**File:** `kth/trading/portfolio.py`

**Root cause:** Any function that writes `paper_portfolio.json` with `open(..., "w")` + `json.dump()` will leave a corrupt/empty file if the process is killed mid-write. `os.replace()` is atomic on Linux/macOS — the old file is never visible in a partial state.

- [ ] **Step 1: Find all write sites** — search for `json.dump` in `portfolio.py`:

```bash
grep -n "json.dump" kth/trading/portfolio.py
```

- [ ] **Step 2: Replace each write pattern** from:

```python
with open(path, "w") as f:
    json.dump(data, f, indent=2, default=str)
```

To:

```python
tmp = path.with_suffix(".tmp")
with open(tmp, "w") as f:
    json.dump(data, f, indent=2, default=str)
os.replace(tmp, path)  # atomic on Linux/macOS
```

- [ ] **Step 3: Ensure `import os`** is present at the top of `portfolio.py` (it likely already is via pathlib, but confirm).

- [ ] **Step 4: Apply same pattern** to `live_portfolio.json` write sites if present.

- [ ] **Step 5: Verify** — `python -c "from kth.trading.portfolio import get_positions; print(get_positions('paper'))"` must not raise.

---

### Task 4 — Forecast partial-failure recovery

**File:** `scripts/dashboard.py` (`--generate` subcommand)

**Root cause:** The `--generate` flow deletes today's forecast cache directory first, then forecasts 49 tickers sequentially (~12 min). If the process crashes at ticker 30, all completed work is lost. On retry, all 49 must re-run.

**Fix:** Remove the upfront directory delete. Instead, per-ticker: check if today's parquet already exists and has today's mtime — if yes, skip. This makes `--generate` idempotent and restartable.

- [ ] **Step 1: Find the directory delete** in the `--generate` block:

```bash
grep -n "rmdir\|rmtree\|shutil\|Deletes today" scripts/dashboard.py
```

- [ ] **Step 2: Replace upfront delete** with a per-ticker skip check. Find the forecasting loop and add a guard at the top of each ticker iteration:

```python
ticker_safe = ticker.replace("^", "_").replace("=", "_")
out_path = day_dir / f"{ticker_safe}.parquet"

# Skip if already forecasted today (mtime is today)
if out_path.exists():
    file_date = datetime.fromtimestamp(out_path.stat().st_mtime).date()
    if file_date == date.today():
        logging.info(f"Skipping {ticker} — already forecasted today")
        continue
```

- [ ] **Step 3: Ensure `day_dir` is created** with `day_dir.mkdir(parents=True, exist_ok=True)` before the loop (not deleted).

- [ ] **Step 4: To force a full refresh** (e.g., the model was wrong), document in the ops manual that the user runs:

```bash
rm -rf data/forecast_cache/NeoQuasar_Kronos-small/$(date +%Y-%m-%d)/
```

Then re-runs `--generate`. This is the manual escape hatch.

- [ ] **Step 5: Verify** — run `--generate` on a day where some parquets already exist; confirm those tickers log "Skipping" and the others proceed normally.

---

### Verification Checklist

- [ ] `python verify_data_layer.py` — all 5 tests pass
- [ ] Sector dict covers all 50 thai_equity tickers exactly (Task 1 Step 3 assertion)
- [ ] Buy loop with 7 Banking tickers at the top of rankings: only 2 Banking picks enter the ticket
- [ ] Killing `--generate` at ticker 20 and re-running: only tickers 21–49 re-forecast
- [ ] Portfolio JSON write survives `kill -9` mid-write (tmp file exists; original untouched)
