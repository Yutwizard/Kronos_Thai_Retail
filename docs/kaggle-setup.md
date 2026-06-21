# Kronos-TH — Fully Automated Pipeline (Kaggle → Google Sheets → Dashboard)

This guide takes you from zero to a **$0, hands-off daily pipeline**: a Kaggle notebook
runs every evening on a free GPU, writes results to Google Sheets, and the Apps Script
web app shows them on your dashboard — no computer of yours needs to be on.

```
Kaggle Notebook  (scheduled daily, free GPU, Internet ON)
   └─ run_pipeline / kth.pipeline.daily.run_daily_pipeline()
        download data → forecast → ticket → metrics → write Google Sheets
Google Sheets  (18 tabs = the shared data store)
        ▲ reads (60s cache, auto-refresh)
Apps Script Web App  →  your dashboard (unchanged)
```

**You only set this up once.** After that it runs itself. Edits you make in the dashboard
(set capital, edit/delete a trade) are applied on the **next scheduled run** (up to ~24h
later) — there is no instant "run now" button by design.

---

## What you need
- A Google account (for Sheets + Apps Script).
- A **free** Kaggle account, **phone-verified** (required to enable GPU + Internet).
- This repo on GitHub (yours is `https://github.com/Yutwizard/Kronos_Thai_Retail`).
- ~45 minutes for first-time setup.

---

## Part A — Dashboard (Sheets + Apps Script)

If you already have the Google Sheets spreadsheet and the deployed Apps Script web app,
**skip to Part B.**

If not, follow **[google_suite/SETUP_GUIDE.md](../google_suite/SETUP_GUIDE.md) Phases 1–2 only**:
- **Phase 1** — create the spreadsheet, its **18 tabs**, and note the **Spreadsheet ID**
  (the long string in the sheet URL between `/d/` and `/edit`).
- **Phase 2** — paste `Code.gs` + `Index.html`, deploy the web app, copy the Web App URL.

> ⚠️ **Skip that guide's Phase 3 (Colab).** Kaggle replaces Colab — that's what this
> document sets up instead.

At the end of Part A you have: a **Spreadsheet ID** and a working (empty) dashboard URL.

---

## Part B — Google service account (unattended auth)

Colab logged in interactively; a scheduled Kaggle run can't click a popup, so it
authenticates as a **service account** instead.

1. Go to <https://console.cloud.google.com> → create (or pick) a project.
2. **APIs & Services → Library** → enable **Google Sheets API** and **Google Drive API**.
3. **APIs & Services → Credentials → Create credentials → Service account**.
   - Give it a name (e.g. `kronos-kaggle`), click through, **Done**.
4. Open the new service account → **Keys → Add key → Create new key → JSON → Create**.
   A `.json` file downloads. **Keep it private — it's a password.**
5. Open that JSON, copy the value of **`client_email`** (looks like
   `kronos-kaggle@your-project.iam.gserviceaccount.com`).
6. Open your **spreadsheet → Share** → paste that email → give it **Editor** → Send.

> The service account now has write access to your sheet, the same way a human editor would.

---

## Part C — Kaggle setup

### C.1 — Create the notebook
1. Sign in at <https://www.kaggle.com> (phone-verify your account under **Settings** if you
   haven't — without it, GPU/Internet are disabled).
2. **Create → New Notebook**.
3. In the right-hand panel:
   - **Accelerator → GPU** (P100 or T4).
   - **Internet → On**.
4. Replace the starter cell by pasting the contents of
   **[kaggle/kronos_kaggle_pipeline.ipynb](../kaggle/kronos_kaggle_pipeline.ipynb)**
   (File → Import Notebook, or copy each cell). This notebook is **thin wiring only** —
   all logic lives in `kth.pipeline.daily`.

### C.2 — Point it at your repo + a pinned commit
In the first code cell:
- `REPO_URL` is already `https://github.com/Yutwizard/Kronos_Thai_Retail.git`.
- Set `PINNED_COMMIT` to a real commit hash for reproducibility (recommended) instead of
  `"main"`. Get it locally with `git rev-parse --short HEAD`. To upgrade later, change this
  value and re-import the notebook.
- If your repo is **private**, uncomment the PAT line and add a `GITHUB_PAT` secret (C.3).

### C.3 — Add secrets (Add-ons → Secrets)
The pipeline reads these via `kth.io.kaggle_runtime.load_secrets`. Create:

| Secret | Required? | Value |
|---|---|---|
| `GCP_SA_JSON` | ✅ | Paste the **entire** service-account JSON from Part B. If Kaggle rejects it for size, paste its **base64** instead (`base64 -w0 key.json`) — the loader handles both. |
| `SPREADSHEET_ID` | ✅ | Your spreadsheet ID from Part A. |
| `HF_TOKEN` | optional | A HuggingFace token (only if the model download ever needs auth). |
| `GITHUB_PAT` | only if private repo | A fine-grained PAT with read access to the repo. |

Then **attach** each secret to the notebook (the toggle next to it).

### C.4 — First manual run (verify before scheduling)
Click **Run All**. Watch for, in order:
- `CUDA available: True`
- `Auth OK — spreadsheet: …`
- data download + `Forecasted N tickers`
- `Pipeline result: {...}`

Then open your **dashboard URL** — it should now show forecasts, the trade ticket, and
the equity curve. Also check the **Pipeline Status** tab reads `ok`.

> First run downloads ~10y OHLCV for ~100 tickers + the model, so it's the slowest. Later
> runs are faster (forecasts already cached for the day are skipped).

---

## Part D — Schedule it (the automation)

1. On the notebook page (saved/committed version), open the **⋮ menu → Schedule a notebook run**
   (or the **Schedule** button).
2. Set a **daily** cadence in the **evening Bangkok time** (after the SET close). Kaggle
   schedules in UTC and timing is *best-effort* — the pipeline already stamps dates in
   `Asia/Bangkok`, so exact minute doesn't matter.
3. Confirm GPU + Internet are still enabled for the scheduled version, and that the four
   secrets are attached.
4. Save the schedule.

That's it — the pipeline now runs itself every day and the dashboard updates within ~60s
of each run (the SPA auto-refreshes).

---

## Part E — Prove the automation works
- After the **first scheduled** run fires, open the scheduled run's **logs** and confirm
  GPU was granted, yfinance returned data, secrets were read, and the sheet was written.
- Open the dashboard the next morning — the data date should be current.
- Let it run **two consecutive days** unattended before you trust it fully.

---

## Daily life (once it's running)
- **Nothing to do.** Check the dashboard whenever you like.
- **Record/edit a trade:** do it in the dashboard. It's queued and **applied on the next
  scheduled run** (Capital Reset and Trade Edits are processed every run).
- **First-day capital:** set it in the dashboard setup banner — it's applied on the next run.

---

## Operations & troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard not updating | Open Pipeline Status tab; if `failed`, read `error_message`; check the scheduled run's Kaggle logs. |
| `Missing secret: GCP_SA_JSON` | Secret not added/attached, or typo in the name. |
| `GCP_SA_JSON is not valid JSON or base64-JSON` | Re-paste the full JSON, or base64 it. |
| Auth/permission error | The service-account `client_email` isn't shared as Editor on the sheet (Part B step 6). |
| No GPU on scheduled run | Phone-verify Kaggle; re-enable GPU on the scheduled version. |
| yfinance returns no data | Kaggle IP rate-limited — see the fallback note below. |
| Bump to new code | Update `PINNED_COMMIT`, re-import the notebook, re-run once manually. |

**yfinance fallback:** if Yahoo blocks Kaggle's shared IPs, switch the data source — upload a
pre-cached OHLCV Kaggle Dataset and have the loader read/extend it. (This is the documented
Phase 3.5 contingency in
[docs/superpowers/plans/2026-06-18-kaggle-scheduled-pipeline.md](superpowers/plans/2026-06-18-kaggle-scheduled-pipeline.md).)

**Rollback:** the Colab notebook (`google_suite/kronos_daily_pipeline.ipynb`) still works as a
manual fallback if Kaggle is ever unavailable.

---

## Test it locally (optional, no Kaggle/GPU)
From the repo root with the venv active:

```bash
python run_pipeline.py --dry-run     # full pipeline against in-memory fakes, no network
python verify_kaggle_runtime.py      # 19 unit/integration checks (auth, orchestration)
```

To run the **real** pipeline locally (needs a GPU + the same secrets as env vars):

```bash
export GCP_SA_JSON="$(cat key.json)"
export SPREADSHEET_ID="your_spreadsheet_id"
python run_pipeline.py
```

---

## Appendix — how it fits together
- **Auth/config:** `kth/io/kaggle_runtime.py` (`load_secrets`, `make_sheets_client`).
- **Orchestration:** `kth/pipeline/daily.py::run_daily_pipeline` — the single source of truth
  (the notebook and `run_pipeline.py` are thin wrappers around it).
- **Notebook generator:** `kaggle/build_kaggle_notebook.py` → `kaggle/kronos_kaggle_pipeline.ipynb`
  (run the builder to regenerate after changing wiring).
- **Sheets schema:** `kth/trading/sheets_config.py` (the 18 tabs and their headers).
- **Dashboard:** `google_suite/apps_script/{Code.gs,Index.html}` — reads the sheets, unchanged.
- **Design/decisions:** `docs/superpowers/specs/2026-06-18-kaggle-scheduled-pipeline-design.md`.
