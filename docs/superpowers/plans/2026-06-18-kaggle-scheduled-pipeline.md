# Kaggle Scheduled Pipeline — Implementation Plan

**Date:** 2026-06-18
**Spec:** [2026-06-18-kaggle-scheduled-pipeline-design.md](../specs/2026-06-18-kaggle-scheduled-pipeline-design.md)
**Revision:** v2 — re-sequenced around risk after senior review; junior-dev complete.
**Method:** TDD, project-style. For each logic unit: write the assertion in
`verify_kaggle_runtime.py` first (**RED**), implement until `python verify_kaggle_runtime.py`
passes (**GREEN**), then **REFACTOR**. **No pytest, no CI** (hard scope limits).

---

## How to read this plan

- Phases are ordered **by risk, not by comfort**. Phase 0 is a hard gate — if it fails, stop.
- Every code block below is a skeleton to copy and complete. `# TODO(impl)` marks the body.
- "Seam" = an injected dependency (`getter`, `client_factory`, `model`, `data_loader`,
  `today`, `notifier`, `work_dir`) that lets GPU/Sheets/Kaggle code run offline with fakes.
- Run all tests from the repo root with the venv active.

**Testing conventions (read before Phase 1 — the existing style has two gotchas):**
- `verify_data_layer.py` runs **top-level `print`/`assert` on import** — it has no `def test_*`
  and no runner. Our new file uses `def test_*()` functions **plus an explicit runner at the
  bottom** so `python verify_kaggle_runtime.py` actually executes them:
  ```python
  if __name__ == "__main__":
      fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
      for fn in fns:
          # pass a fresh temp dir to tests that take one
          import inspect, tempfile
          if inspect.signature(fn).parameters:
              with tempfile.TemporaryDirectory() as tmp: fn(tmp)
          else: fn()
          print("PASS", fn.__name__)
      print("ALL PASSED")
  ```
- **Do NOT `from verify_data_layer import make_synthetic_yf`** — importing that file runs its whole
  suite as a side effect. Copy `make_synthetic_yf` into `verify_kaggle_runtime.py` (or first
  refactor it into a small importable module, e.g. `kth/testing/synthetic.py`, and have both
  verify files import from there).
- **Working dir, not `data_dir`:** `kth.trading.portfolio` hardcodes `POSITIONS_DIR =
  Path("data/positions")` (resolved against CWD) — it does **not** take a path arg. So the seam
  is `work_dir`: `run_daily_pipeline` does `os.chdir(work_dir)` (the proven Colab mechanism) so
  `data/positions/*.json` lands under the temp dir. Tests pass a `tempfile.TemporaryDirectory()`;
  restore the original CWD in a `finally`.

---

## Phase 0 — Platform spike (HARD GATE, no production code)

Goal: prove the risky platform assumptions **before** investing in the refactor. Do this in a
**throwaway Kaggle notebook** (not committed). Record results in the plan PR description.

### 0.1 Manual Google setup
- [ ] Create a GCP project; enable **Google Sheets API** and **Google Drive API**.
- [ ] Create a **service account**; create a JSON key; download it.
- [ ] Open the dashboard spreadsheet → Share → add the SA `client_email` as **Editor**.

### 0.2 Kaggle secrets
- [ ] In a Kaggle notebook: Add-ons → Secrets. Create:
  - `GCP_SA_JSON` — paste the SA JSON. If it exceeds the secret size limit, store **base64** of it.
  - `SPREADSHEET_ID` — the spreadsheet id (from its URL).
  - `HF_TOKEN` — optional (only if the model repo needs auth).
  - `GITHUB_PAT` — only if the repo is private.

### 0.3 Spike notebook — prove the trifecta
- [ ] Settings: **Accelerator = GPU**, **Internet = On**. Attach the 4 secrets.
- [ ] Cell content (throwaway):
```python
import torch, requests, json, base64, gspread
from kaggle_secrets import UserSecretsClient
s = UserSecretsClient()

# R1: GPU present in this session?
print("CUDA:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "—")

# R2: yfinance reachable from Kaggle's IP?
import yfinance as yf
df = yf.download("AOT.BK", period="5d", interval="1d", progress=False)
print("yfinance rows:", len(df))   # >0 means OK

# HuggingFace reachable?
print("HF status:", requests.get("https://huggingface.co", timeout=10).status_code)

# R6: secrets readable + SA can write the Sheet
raw = s.get_secret("GCP_SA_JSON")
try: info = json.loads(raw)
except Exception: info = json.loads(base64.b64decode(raw))
gc = gspread.service_account_from_dict(info)
sh = gc.open_by_key(s.get_secret("SPREADSHEET_ID"))
# Write to a SCRATCH tab — never touch real dashboard tabs in the spike.
try: scratch = sh.worksheet("_spike")
except Exception: scratch = sh.add_worksheet("_spike", rows=1, cols=1)
scratch.update("A1", [["spike OK"]])
print("Sheet write OK:", [ws.title for ws in sh.worksheets()][:5])
# Clean up: sh.del_worksheet(scratch) once verified.
```
- [ ] **Schedule** this notebook to run once (Kaggle → notebook → Schedule). Confirm the
  scheduled run (not just interactive) **gets a GPU, reaches yfinance + HF, reads secrets, and
  writes the Sheet**. Check the scheduled run's logs.

**HARD GATE / Checkpoint:** all five must be true in the **scheduled** run:
GPU available · yfinance rows > 0 · HF reachable · secrets read · Sheet write succeeded.
- If **R1 fails** (no GPU on schedule) → stop; fall back to local-GPU cron. Abort plan.
- If **R2 fails** (yfinance blocked) → switch to the contingency in Phase 3.5 before proceeding.

---

## Phase 1 — Runtime auth/config (TDD)

New module `kth/io/kaggle_runtime.py`. Pure + injectable → fully offline-testable.

```python
# kth/io/kaggle_runtime.py
import base64, json
from dataclasses import dataclass

@dataclass
class RuntimeConfig:
    spreadsheet_id: str
    sa_info: dict
    hf_token: str | None = None
    github_pat: str | None = None

def _parse_sa(raw: str) -> dict:
    """Accept raw JSON or base64-encoded JSON; raise a clear error otherwise."""
    # TODO(impl): try json.loads(raw); on failure try json.loads(base64.b64decode(raw));
    #             on failure raise RuntimeError("GCP_SA_JSON is not valid JSON or base64-JSON")

def load_secrets(getter, *, required=("GCP_SA_JSON", "SPREADSHEET_ID")) -> RuntimeConfig:
    """getter(name)->str|None. Used with Kaggle UserSecretsClient().get_secret or os.environ.get.
    Validate required keys present; parse SA; return RuntimeConfig."""
    # TODO(impl): for k in required: if not getter(k): raise RuntimeError(f"Missing secret: {k}")
    #             return RuntimeConfig(spreadsheet_id=getter("SPREADSHEET_ID"),
    #                                  sa_info=_parse_sa(getter("GCP_SA_JSON")),
    #                                  hf_token=getter("HF_TOKEN"), github_pat=getter("GITHUB_PAT"))

def make_sheets_client(sa_info: dict, *, client_factory=None):
    """client_factory(sa_info)->client; defaults to gspread.service_account_from_dict."""
    # TODO(impl): factory = client_factory or _default_gspread_factory; return factory(sa_info)
```

- [ ] **RED:** in new `verify_kaggle_runtime.py`:
```python
def fake_getter(d): return lambda k: d.get(k)

def test_load_secrets_ok():
    cfg = load_secrets(fake_getter({"GCP_SA_JSON": '{"client_email":"x@y"}',
                                    "SPREADSHEET_ID": "abc", "HF_TOKEN": "t"}))
    assert cfg.spreadsheet_id == "abc" and cfg.sa_info["client_email"] == "x@y" and cfg.hf_token == "t"

def test_load_secrets_base64():
    import base64
    raw = base64.b64encode(b'{"client_email":"x@y"}').decode()
    cfg = load_secrets(fake_getter({"GCP_SA_JSON": raw, "SPREADSHEET_ID": "abc"}))
    assert cfg.sa_info["client_email"] == "x@y"

def test_missing_secret_raises():
    try: load_secrets(fake_getter({"SPREADSHEET_ID": "abc"})); assert False
    except RuntimeError as e: assert "GCP_SA_JSON" in str(e)

def test_bad_json_raises():
    try: load_secrets(fake_getter({"GCP_SA_JSON": "not json", "SPREADSHEET_ID": "a"})); assert False
    except RuntimeError: pass

def test_make_client_uses_factory():
    seen = {}
    c = make_sheets_client({"client_email":"x"}, client_factory=lambda i: seen.setdefault("i", i) or "CLIENT")
    assert c == "CLIENT" and seen["i"]["client_email"] == "x"
```
- [ ] **GREEN:** implement the bodies.
- [ ] **REFACTOR:** error messages name the missing/invalid secret and how to fix it.

**Files:** `kth/io/__init__.py`, `kth/io/kaggle_runtime.py`, `verify_kaggle_runtime.py`
**Checkpoint:** `python verify_kaggle_runtime.py` green (Phase 1 tests).

---

## Phase 2 — Extract daily orchestration (TDD) — the core refactor

Lift the Colab cell bodies into one testable function. **This is the largest, highest-risk
phase.** Reuse `kth.trading.{portfolio,trade_gen,sheets}`; do not duplicate their logic.

```python
# kth/pipeline/daily.py
from datetime import date

def run_daily_pipeline(gc, spreadsheet_id, *, model, data_loader, today: date,
                       work_dir: str = ".", notifier=None) -> dict:
    """Idempotent daily run. Steps (ORDER MATTERS):
      0. os.chdir(work_dir) in a try/finally (restore CWD) so kth's hardcoded
         POSITIONS_DIR=Path("data/positions") resolves under work_dir
      1. open spreadsheet
      2. apply_capital_reset(sh, today)     # Cell 4b — BEFORE init/forecasts (first-run SETUP)
      3. rebuild local JSON state from Sheets (writes data/positions/*.json under CWD)
      4. apply_trade_edits(sh, today)       # Cell 9b — after state rebuild, before ticket
      5. data_loader.ensure(tickers)        # download/load OHLCV
      6. forecasts = model.forecast(...)    # skip tickers already done for `today` (idempotent)
      7. apply fills (if any) -> rebuild
      8. ticket = generate_trade_ticket(report_date=str(today))   # NOTE: takes a STRING
      9. metrics = compute_metrics(...)
     10. write staging (Portfolio/Positions/Forecasts/Ticket/Risk/EquityCurve/ForecastHistory)
         using DATE-KEYED UPSERT for Equity Curve + Forecast History (replace today's row,
         PRESERVE prior dates)
     11. promote_staging(...)
     12. write Pipeline Status status='ok'
    On any exception: write Pipeline Status status='failed', error=str(e); notifier('error', …); raise.
    Returns {'status','forecasts','exits','buys','reduces'}.
    """
    # TODO(impl): lift Cells 4b, 9, 9b, 10–17, 13b from build_notebook.py; replace every
    #             date.today()/datetime.now() with `today`; wrap body in
    #             cwd=os.getcwd(); os.chdir(work_dir); try: ... finally: os.chdir(cwd).
```

Idempotency helper (replaces blind append):
```python
def upsert_by_date(ws_rows: list[list], header: list, new_row: list, date_col: int = 0) -> list[list]:
    """Return rows with new_row replacing any existing row whose date_col matches, else appended.
    Used for Equity Curve and Forecast History so same-day re-runs don't duplicate."""
    # TODO(impl)
```

- [ ] **RED:** extend `verify_kaggle_runtime.py` with in-memory fakes + synthetic data:
```python
# FakeWorksheet: holds a list-of-lists; supports get_all_values/update/append_row/clear/title
# FakeSpreadsheet: dict of title->FakeWorksheet; worksheet(title) returns it
# FakeGspreadClient: open_by_key(id)->FakeSpreadsheet
# FakeModel.forecast(...) -> deterministic summary frames for given tickers
# reuse make_synthetic_yf from verify_data_layer.py for data_loader

def test_pipeline_writes_all_tabs(tmp):           # tmp = temp work dir (chdir target)
    gc = seeded_fake_client()                      # portfolio+trade-log seeded
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(), today=D, work_dir=tmp)
    sh = gc.open_by_key("id")
    for tab in ["Portfolio","Positions","Forecasts","Trade Ticket","Risk Metrics",
                "Equity Curve","Pipeline Status"]:
        assert len(sh.worksheet(tab).get_all_values()) >= 2   # header + ≥1 row

def test_idempotent_preserves_history(tmp):        # R3 — and guards the Equity Curve history-loss bug
    gc = seeded_fake_client(equity_history=["2026-06-13","2026-06-14"])  # 2 prior days seeded
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(), today=D, work_dir=tmp)
    rows1 = gc.open_by_key("id").worksheet("Equity Curve").get_all_values()
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(), today=D, work_dir=tmp)
    rows2 = gc.open_by_key("id").worksheet("Equity Curve").get_all_values()
    dates = [r[0] for r in rows2[1:]]
    assert len(rows1) == len(rows2)                          # same-day re-run adds no duplicate
    assert {"2026-06-13","2026-06-14"} <= set(dates)         # prior history PRESERVED (not replaced)
    assert dates.count(str(D)) == 1                          # exactly one row for today

def test_capital_reset_applied_before_forecasts(tmp):   # C3 / first-run SETUP
    gc = client_with_pending_setup(capital=300000)
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(), today=D, work_dir=tmp)
    assert portfolio_initial_capital(gc) == 300000 and capital_reset_cleared(gc)

def test_trade_edit_applied(tmp):                  # C3
    gc = client_with_pending_edit(index=0, new_shares=200)
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(), today=D, work_dir=tmp)
    assert trade_log_shares(gc, 0) == 200 and trade_edits_cleared(gc)

def test_uses_injected_today_not_utc(tmp):         # R4
    run_daily_pipeline(gc, "id", model=FakeModel(), data_loader=FakeLoader(),
                       today=date(2026,6,15), work_dir=tmp)
    assert last_equity_date(gc) == "2026-06-15"

def test_failure_writes_status_and_notifies(tmp):  # R7
    calls = []
    boom = FakeModel(raise_on_forecast=True)
    try: run_daily_pipeline(gc, "id", model=boom, data_loader=FakeLoader(), today=D,
                            work_dir=tmp, notifier=lambda lvl,msg: calls.append(lvl))
    except Exception: pass
    assert pipeline_status(gc) == "failed" and "error" in calls
```
- [ ] **GREEN:** implement `run_daily_pipeline` + `upsert_by_date` by lifting the cells. Verify
  the Equity Curve write logic during lift (current cell writes a single today-row to staging —
  confirm promote accumulates history; if it replaces, switch Equity Curve to **append+upsert
  against the live tab**, not staging-replace).
- [ ] **REFACTOR:** ensure `build_notebook.py` cell bodies are deleted/replaced by calls into
  `kth.pipeline.daily` (single source of truth). No business logic left in notebook cells.

**Files:** `kth/pipeline/__init__.py`, `kth/pipeline/daily.py`, `verify_kaggle_runtime.py`
**Checkpoint:** `python verify_kaggle_runtime.py` green (Phases 1–2). Full pipeline + 4b/9b +
idempotency + tz + failure-path all proven offline.

---

## Phase 3 — Real model + data wiring (integration; dry-run smoke)

```python
# run_pipeline.py  (repo root, thin entrypoint)
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from kth.io.kaggle_runtime import load_secrets, make_sheets_client
from kth.pipeline.daily import run_daily_pipeline

def main(dry_run=False):
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    if dry_run:
        # wire fakes from verify_kaggle_runtime for a fast offline sanity check
        ...
        return
    cfg = load_secrets(os.environ.get)            # local: env vars; Kaggle: see notebook
    gc = make_sheets_client(cfg.sa_info)
    model = _load_real_model(cfg)                 # KronosTH.from_pretrained(..., device="cuda")
    data_loader = _real_data_loader()             # download_universe + load_cached
    notifier = _make_notifier(cfg)                # email/webhook; see Phase 4
    run_daily_pipeline(gc, cfg.spreadsheet_id, model=model, data_loader=data_loader,
                       today=today, notifier=notifier)

if __name__ == "__main__":
    import sys; main(dry_run="--dry-run" in sys.argv)
```

- [ ] Implement `_load_real_model` (HF or Kaggle-Dataset weights — see Phase 3.5) and
  `_real_data_loader` (wrap `download_universe`/`load_cached`).
- [ ] **Model weights = Kaggle Dataset by default.** Upload Kronos-small weights once as a Kaggle
  Dataset; `_load_real_model` prefers the attached dataset path, falls back to HF download.
- [ ] `python run_pipeline.py --dry-run` must be green (fakes end-to-end) and run with no network.

**Checkpoint:** `--dry-run` green locally; one **interactive** Kaggle run writes all tabs.

### Phase 3.5 — yfinance contingency (only if R2 failed in Phase 0)
- [ ] If yfinance is blocked from Kaggle: ship a **pre-cached OHLCV Kaggle Dataset** and have the
  data_loader read/extend it incrementally; or switch the source (e.g. stooq) behind the
  existing `data_loader` seam. Decide in Phase 0; implement here.

---

## Phase 4 — Thin Kaggle notebook + failure alerting

```python
# kaggle/build_kaggle_notebook.py  → emits kaggle/kronos_kaggle_pipeline.ipynb
#   Cell 1: pip install deps; git clone <repo>@<PINNED_COMMIT> (use GITHUB_PAT if private); pip install -e .
#   Cell 2: from kth.io.kaggle_runtime import load_secrets, make_sheets_client
#           from kaggle_secrets import UserSecretsClient; s = UserSecretsClient()
#           cfg = load_secrets(s.get_secret)
#   Cell 3: gc = make_sheets_client(cfg.sa_info)
#   Cell 4: today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
#           run_daily_pipeline(gc, cfg.spreadsheet_id, model=…, data_loader=…, today=today, notifier=…)
```

- [ ] Build the notebook (≤5 logical cells; **no business logic** — only wiring).
- [ ] Implement `_make_notifier`: email (SMTP) or webhook on `level=='error'`. (Note: LINE Notify
  was deprecated in 2025 — do **not** rely on it; use email/webhook.) Notifier is optional/injectable.
- [ ] Pin the clone to a commit/tag; document how to bump it.

**Files:** `kaggle/build_kaggle_notebook.py`, generated notebook, notifier impl.
**Checkpoint:** generated notebook runs top-to-bottom on Kaggle and updates the dashboard;
a forced error sends an alert and sets Pipeline Status `failed`.

---

## Phase 5 — Schedule + prove unattended (do NOT retire Colab yet)

- [ ] Enable Kaggle **scheduled run** (daily, evening BKK), GPU + Internet, secrets attached.
- [ ] Verify a scheduled run writes Sheets and the dashboard reflects it within ~60s.
- [ ] Verify failure path on a scheduled run (force an error once): status `failed` + alert fired.
- [ ] **Prove 2 consecutive unattended days** stay current.

**Checkpoint (rollback gate):** two green scheduled days. If not green, keep Colab and iterate;
do not proceed to Phase 6.

---

## Phase 6 — Retire Colab + docs

- [ ] Only now: move `google_suite/kronos_daily_pipeline.ipynb` + `google_suite/build_notebook.py`
  to `docs/superpowers/archive/` with a deprecation note → Kaggle.
- [ ] `docs/kaggle-setup.md`: service account, Sheet sharing, the 4 secrets (+ base64 tip),
  GPU/Internet toggles, weights-dataset upload, enabling the schedule, troubleshooting, how to
  bump the pinned commit, rollback to Colab.
- [ ] Update `CLAUDE.md` Layer 5 + architecture table: Colab → Kaggle primary runtime; note the
  ~24h latency for dashboard-initiated changes.
- [ ] Final: `python verify_data_layer.py` and `python verify_kaggle_runtime.py` both green;
  `python run_pipeline.py --dry-run` green.

---

## Test inventory (no pytest)

| File | Covers | Run |
|---|---|---|
| `verify_kaggle_runtime.py` | P1 auth/config + P2 orchestration (4b/9b, idempotency, tz, failure) via fakes+synthetic | `python verify_kaggle_runtime.py` |
| `run_pipeline.py --dry-run` | full wiring smoke, offline | `python run_pipeline.py --dry-run` |
| `verify_data_layer.py` (existing) | data-layer regression | `python verify_data_layer.py` |

## Definition of done

- Phase 0 hard gate passed (GPU+Internet+yfinance+Secrets+Sheets on a **scheduled** run).
- Scheduled Kaggle run updates the dashboard daily, unattended, at $0; applies queued
  setup/edits each run; idempotent on retry; BKK-dated; alerts on failure.
- Two green scheduled days **before** Colab is archived (rollback preserved).
- `verify_kaggle_runtime.py`, `verify_data_layer.py`, and `run_pipeline.py --dry-run` all green.
- `docs/kaggle-setup.md` lets a fresh user reproduce it end-to-end.
