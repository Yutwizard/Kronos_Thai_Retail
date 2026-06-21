# Kronos-TH — Complete Setup Guide (Zero to Dashboard)

> **For absolute beginners.** No coding experience needed. Every click, every URL,
> every key-press is written out. If a step fails, read the ⚠️ caution under it.

**What you'll have at the end:** A web dashboard showing Thai stock forecasts,
trade tickets, and portfolio performance — updated automatically every evening
at $0/month, forever.

```
You (any browser) →  Apps Script Web App (dashboard)
                           ↑ reads
                      Google Sheets (database, 18 tabs)
                           ↑ writes
                      Kaggle Notebook (runs every evening, free GPU)
                           ↑ reads secrets
                      GCP Service Account (password-free auth)
```

**Time:** ~60 minutes for first-time setup. You only do this once.

---

## What You Need

| Thing | Where |
|-------|-------|
| A Google account (free) | gmail.com or Google Workspace |
| A Kaggle account (free) | kaggle.com — must be **phone-verified** |
| A GCP (Google Cloud) account (free) | console.cloud.google.com — same Google login |
| A GitHub account (free, for getting the code) | github.com |

> ⚠️ **Kaggle phone verification is mandatory.** Without it, Kaggle disables GPU + Internet
> and the pipeline cannot run. Go to kaggle.com → your avatar → Settings → Phone Verification,
> enter your number, and enter the SMS code before proceeding.

---

## Phase 1 — Create the Google Sheets Spreadsheet

**What this builds:** An 18-tab spreadsheet that holds all your portfolio data,
forecasts, and trade history. The dashboard reads from this.

### Step 1.1 — Create the spreadsheet

1. Go to https://sheets.google.com and click **+ Blank** (big plus icon, top left).
2. A new spreadsheet opens. Click the title "Untitled spreadsheet" (top left) and
   rename it to **`Kronos-TH`**.
3. Look at your browser's address bar. The URL contains a long random-looking string:
   ```
   https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ.../edit
   ```
   That string between `/d/` and `/edit` is your **Spreadsheet ID**. Copy it and
   save it somewhere — you'll need it 3 times.

> ⚠️ **Save your Spreadsheet ID.** Write it down or paste it into a text file.
> You'll paste this into (1) Kaggle secrets and (2) the Apps Script.

### Step 1.2 — Rename the first tab

At the bottom of the spreadsheet you see a tab called "Sheet1":
1. **Right-click** the tab → **Rename**.
2. Type: **`Portfolio`** and press Enter.

### Step 1.3 — Add headers to the Portfolio tab

Click cell **A1** and type: `cash`

Press **Tab** (not Enter) to move to B1 and type each header:

| Cell | Type |
|------|------|
| A1 | `cash` |
| B1 | `initial_capital` |
| C1 | `mode` |
| D1 | `model_version` |
| E1 | `forecast_date` |

You should see these 5 words in cells A1 through E1.

> ⚠️ **Type exactly — no extra spaces.** Apps Script reads headers by name.
> If you type `cash ` (with trailing space) instead of `cash`, the code won't find it.

### Step 1.4 — Create 17 more tabs

At the bottom left, click the **+** (plus) button to add a new tab (sheet).
Rename it immediately by right-clicking. Repeat until you have exactly 18 tabs:

| # | Tab name | What to put in A1 |
|---|----------|-------------------|
| 1 | `Portfolio` | **(already done in 1.3)** |
| 2 | `Equity Curve` | `date,equity,cash,invested` |
| 3 | `Positions` | `ticker,shares,avg_cost,entry_date,sector,current_price,pnl,pnl_pct,pct_to_stoploss` |
| 4 | `Trade Log` | `timestamp,ticker,action,shares,price,rationale,friction_cost,model_version,id,ref_id` |
| 5 | `Forecasts` | `date_updated,ticker,rank_score,exp_ret,band_width,confidence,net_return,p5,p50,p95,sector` |
| 6 | `Forecast History` | `date,ticker,predicted_direction,predicted_return,entry_close,actual_return,was_correct` |
| 7 | `Trade Ticket` | `ticker,action,shares,est_cost_thb,rationale,sector,confidence,filled_price,filled_shares,fill_timestamp` |
| 8 | `Risk Metrics` | `date,equity,cash,deployed_pct,trailing_sharpe_12w,max_drawdown_pct,mtd_pnl_pct,trade_win_rate,calmar_ratio,sortino_ratio,drawdown_velocity,allocation_band,allocation_pct,market_state,is_frozen,bootstrap_p_value,friction_ytd_pct,friction_ytd_thb` |
| 9 | `Pipeline Status` | `last_run_timestamp,status,duration_seconds,error_message,sheets_updated` |
| 10 | `Calibration` | `date,coverage,n_samples,status` |
| 11 | `Portfolio_staging` | `cash,initial_capital,mode,model_version,forecast_date` |
| 12 | `Positions_staging` | `ticker,shares,avg_cost,entry_date,sector,current_price,pnl,pnl_pct,pct_to_stoploss` |
| 13 | `Forecasts_staging` | `date_updated,ticker,rank_score,exp_ret,band_width,confidence,net_return,p5,p50,p95,sector` |
| 14 | `Trade Ticket_staging` | `ticker,action,shares,est_cost_thb,rationale,sector,confidence,filled_price,filled_shares,fill_timestamp` |
| 15 | `Risk Metrics_staging` | `date,equity,cash,deployed_pct,trailing_sharpe_12w,max_drawdown_pct,mtd_pnl_pct,trade_win_rate,calmar_ratio,sortino_ratio,drawdown_velocity,allocation_band,allocation_pct,market_state,is_frozen,bootstrap_p_value,friction_ytd_pct,friction_ytd_thb` |
| 16 | `Equity Curve_staging` | `date,equity,cash,invested` |
| 17 | `Trade Edits` | Leave empty (populated by dashboard) |
| 18 | `Capital Reset` | Leave empty (populated by dashboard) |

> ⚠️ **The headers MUST match exactly.** The longest ones (Risk Metrics headers)
> are sensitive to ordering. If a header is mis-typed, that column will show blank
> on the dashboard. Copy-paste each line from this table rather than typing.

> ⚠️ **The tab names MUST match exactly.** Capital letters, spaces, underscores —
> everything. If you create `Portfolio_Staging` instead of `Portfolio_staging`,
> the pipeline won't find it.

**To add a header row:** click the new tab → click cell A1 → type or paste the
entire comma-separated list from the table above. Press Enter. Google Sheets will
automatically split the commas into separate cells — you'll see each word in its
own column.

### Step 1.5 — Verify

Count your tabs (bottom of screen): exactly 18 tabs visible. Verify the names
match the table above, especially the `_staging` suffix.

> ⚠️ **Missing a tab?** Add it now. The pipeline will crash if it tries to read
> a tab that doesn't exist. Better to check now than debug later.

---

## Phase 2 — Create the Apps Script Web App

**What this builds:** The dashboard you'll check every morning. A 5-tab web page
that reads your Sheets data and displays it in charts, tables, and trade tickets.

### Step 2.1 — Open Apps Script

From your spreadsheet: **Extensions → Apps Script**.

A new tab opens with some placeholder code (`function myFunction() {}`).
This is the Apps Script editor.

### Step 2.2 — Delete placeholder

Select ALL the existing code (Ctrl+A / Cmd+A) and press Delete. The editor
should be empty.

### Step 2.3 — Paste the backend code

1. In your browser, open this URL to view the backend code:
   `https://raw.githubusercontent.com/Yutwizard/Kronos_Thai_Retail/main/google_suite/apps_script/Code.gs`
2. Select ALL (Ctrl+A / Cmd+A) and copy (Ctrl+C / Cmd+C).
3. Paste into the empty Apps Script editor (Ctrl+V / Cmd+V).
4. The file should now contain ~15 functions. The top of the editor says
   `Code.gs` (filename).

### Step 2.4 — Create the frontend file

1. In the Apps Script editor, next to "Files", click **+ → HTML**.
2. Name the new file: **`Index`** (without `.html` — it adds the extension
   automatically).
3. Open this URL: `https://raw.githubusercontent.com/Yutwizard/Kronos_Thai_Retail/main/google_suite/apps_script/Index.html`
4. Copy ALL the code and paste it into the new `Index.html` file.

You should now have **two files** in the left panel:
- **Code.gs**
- **Index.html**

### Step 2.5 — Set V8 runtime

1. Click **Project Settings** (gear icon, left panel).
2. Under **General Settings**, check the box:
   ☑ **Enable Chrome V8 runtime**
3. Click **Save** and go back (arrow or "Editor" link at top left).

> ⚠️ **V8 runtime is required.** The code uses modern JavaScript features
> that only work with V8. Without it, the dashboard shows a blank page.

### Step 2.6 — Deploy

1. Click the blue **Deploy** button (top right) → **New deployment**.
2. Click the gear icon next to **Select type** → choose **Web app**.
3. Fill in:
   - **Description:** `Kronos-TH Dashboard`
   - **Execute as:** `Me` (your Google account)
   - **Who has access:** `Anyone`
4. Click **Deploy**.
5. Click **Authorize access** → pick your Google account → click **Allow**.

> ⚠️ **Google will show a warning**: "This app isn't verified." That's normal
> — this is your own code, not a commercial app. Click **Advanced → Go to
> Kronos-TH (unsafe)** to proceed.

6. After authorization, you see a **Web App URL**. Copy it and bookmark it.
   This is your dashboard. It will look something like:
   ```
   https://script.google.com/macros/s/AKfycbx.../exec
   ```

### Step 2.7 — Test the dashboard

Open the Web App URL in a new tab. You should see:
- A page titled **"Kronos-TH Portfolio"**
- A gray banner: **"No data yet. Run the pipeline first."**
- Five tabs: Dashboard, Positions, Trade Log, Forecasts, Trade Ticket

> ✅ **If you see this, the dashboard is working.** The "no data" message means
> it connected to your spreadsheet correctly. Data appears after Phase 4.

> ⚠️ **If the page is blank white**, re-check Step 2.5 (V8 runtime must be ON).

> ⚠️ **If you see "App error: TypeError..."**, close the tab, go back to the
> Apps Script editor, click **Deploy → Manage deployments**, find your deployment,
> click **Edit** (pencil icon) and set **Execute as** to `Me`. Re-deploy.
> Re-open the new URL.

---

## Phase 3 — Create the Google Service Account

**What this builds:** A password-free login that the Kaggle pipeline uses to
write to your Google Sheets. Normal logins (OAuth/password) don't work for
unattended scheduled tasks — service accounts do.

### Step 3.1 — Open Google Cloud Console

Go to https://console.cloud.google.com

> ⚠️ **This is NOT the same as Google Sheets or Google Drive.** It's a separate
> developer console at a different URL. If you get lost, check the address bar.

### Step 3.2 — Create or select a project

1. Click the project dropdown at the top of the page (left of the search bar).
   It might say "Select a project" or "My First Project".
2. In the popup, click **NEW PROJECT** (top right).
3. Name: `kronos-th` → click **CREATE**. Wait a few seconds.

> ⚠️ **If you already have GCP projects**, pick an existing one — no need to
> create a new one. The service account lives inside a project.

### Step 3.3 — Enable required APIs

1. From the left menu (☰ hamburger), go to **APIs & Services → Library**.
2. In the search bar, type **Google Sheets API** → click the result → click
   the blue **ENABLE** button.
3. Go back to the Library (left menu or back button).
4. Search for **Google Drive API** → click it → click **ENABLE**.

Wait 30 seconds after enabling — GCP sometimes takes a moment to activate.

### Step 3.4 — Create the Service Account

1. **APIs & Services → Credentials** (left menu).
2. Click **+ CREATE CREDENTIALS** → **Service account**.
3. Fill in:
   - **Service account name:** `kronos-kaggle`
   - **Service account ID:** auto-fills (leave as-is)
   - **Description** (optional): `Kronos-TH daily pipeline access`
4. Click **DONE**.

### Step 3.5 — Create the JSON key

1. In the Credentials page, find your new service account in the table
   (look under "Service Accounts" at the bottom).
2. Click on its email address (or the pencil/edit icon).
3. Go to the **KEYS** tab.
4. Click **ADD KEY → Create new key**.
5. Select **JSON** → click **CREATE**.
6. A `.json` file downloads to your computer.

> ⚠️ **Keep this JSON file private.** Anyone with this file can write to your
> Google Sheets. Don't upload it publicly, don't email it. Treat it like a
> password. Kaggle stores it in an encrypted Secret.

### Step 3.6 — Get the service account email and share your sheet

1. Open the downloaded JSON file (right-click → Open With → Notepad or any
   text editor).
2. Find the line that starts with `"client_email"`. Copy the value — it looks
   like `kronos-kaggle@kronos-th.iam.gserviceaccount.com`.
3. Go back to your Google Sheets spreadsheet.
4. Click the green **Share** button (top right).
5. Paste the `client_email` into the "Add people and groups" field.
6. Set permission to **Editor** (not Viewer).
7. Uncheck "Notify people" (service accounts can't receive email).
8. Click **Send** (or **Share**).

> ⚠️ **Must be Editor, not Viewer.** The pipeline WRITES data to the sheet.
> Viewer permission means it can't write → every run will fail.

> ⚠️ **If you see "Can't share with this address"**, you may have pasted the
> wrong thing. Re-open the JSON, find `client_email`, copy ONLY the email
> (between the quotes), and re-paste.

---

## Phase 4 — Set Up Kaggle

**What this builds:** A notebook that runs every evening on Kaggle's free GPU,
forecasts your stocks, and writes results to Google Sheets automatically.

### Step 4.1 — Create Kaggle account and verify phone

1. Go to https://www.kaggle.com → **Register** (or Sign In if you have one).
2. After signing in, click your avatar (top right) → **Settings**.
3. Find **Phone Verification** → enter your phone number → wait for the SMS →
   enter the code.

> ⚠️ **This is the most common failure point.** Without phone verification,
> Kaggle disables GPU and Internet access for your account. The pipeline WILL
> fail — you'll see "CUDA available: False" or network errors. Verify before
> continuing.

### Step 4.2 — Import the notebook from GitHub

1. Go to **Create → New Notebook** (big blue button on kaggle.com).
2. In the new notebook, click **File → Import Notebook**.
3. In the popup:
   - Select the **GitHub** tab
   - Repository: `Yutwizard/Kronos_Thai_Retail`
   - File path: `kaggle/kronos_kaggle_pipeline.ipynb`
   - Click **Import**

> ⚠️ **If the GitHub tab shows an error** ("Repository not found" or "Rate
> limited"), you can instead:
> 1. Open `https://github.com/Yutwizard/Kronos_Thai_Retail/blob/main/kaggle/kronos_kaggle_pipeline.ipynb`
> 2. Click **Raw** (upper right of the file view)
> 3. Copy the entire content
> 4. In Kaggle, create an empty notebook, then **File → Import Notebook → Upload** and paste.

### Step 4.3 — Configure runtime settings

In the right-hand panel of the notebook:

| Setting | Value |
|---------|-------|
| **Accelerator** | **GPU P100** (or GPU T4 x2 if P100 not available) |
| **Internet** | **On** |
| **Persistence** | Leave as default (Output only) |
| **Environment** | Leave as default (latest Python) |

> ⚠️ **Don't skip GPU.** Forecasts on CPU take 45+ minutes and may timeout.
> On GPU they take ~3 minutes.

### Step 4.4 — Pin the code version (edit Cell 1)

The first code cell has this line near the top:
```python
PINNED_COMMIT = "main"
```

Change `"main"` to a specific commit hash so your pipeline uses a tested version
and doesn't break if new code is pushed. The latest tested commit is:

```python
PINNED_COMMIT = "1b6b33d"
```

> ⚠️ **To update later** (when you want newer code): change the commit hash,
> re-run the notebook once manually, and the schedule picks up the new version.

### Step 4.5 — Add and attach secrets

In the right panel: **Add-ons → Secrets** (need to scroll down).

Click **+ New Secret** and add these **4 secrets** one by one:

| Name | Required | What to paste |
|------|----------|---------------|
| `GCP_SA_JSON` | ✅ | The **entire** contents of the `.json` key file from Phase 3 Step 5. Open the file in Notepad, Select All (Ctrl+A), Copy, paste into the secret value. |
| `SPREADSHEET_ID` | ✅ | The long string you saved from Phase 1 Step 1.3 (between `/d/` and `/edit` in your sheet's URL). **Just the ID, not the full URL.** |
| `HF_TOKEN` | ❌ | Leave **empty** — the model is public and doesn't need auth. Only fill this if HuggingFace requires it in the future. |
| `GITHUB_PAT` | ❌ | Leave **empty** — your repo is public. Only fill this if you make your repo private. |

> ⚠️ **If Kaggle rejects GCP_SA_JSON as too large** (secret size limit), you
> need to base64-encode it. On Windows: open Command Prompt, run:
> `certutil -encode key.json key.txt`, then paste the long string from `key.txt`
> (NOT the `-----BEGIN CERTIFICATE-----` header/footer — just the body).
> The pipeline's `load_secrets()` function auto-detects and decodes base64.

After creating each secret, click the **toggle switch** next to it to **attach**
(the toggle turns blue/on). All 4 secrets should show as "Attached".

> ⚠️ **Adding is NOT attaching.** You must both create the secret AND flip the
> toggle. If the toggle is gray, the notebook can't read that secret and the
> pipeline will fail with "Missing secret: ...".

### Step 4.6 — First manual run (verify everything works)

1. Click **Run All** (top right of the notebook).
2. Scroll down and watch each cell execute. The cell numbers on the left turn
   green as they complete.

**Expected output, in order:**

| Cell | What you should see | Wait time |
|------|---------------------|-----------|
| 1 | Git clone + pip install messages, ends with "Dependencies installed." | ~2 min |
| 2 | "Auth OK — spreadsheet: ..." | ~5 sec |
| 3 | "CUDA available: True", then data download progress, then "Forecasted N tickers", then "Pipeline result: {'status': 'ok', ...}" | ~5-10 min |

> ✅ **If you see "Pipeline result: {'status': 'ok'}" at the end,** the pipeline
> ran successfully. Open your dashboard URL — data should appear.

> ⚠️ **If "CUDA available: False"**, your GPU is not enabled. Check the
> right panel → Accelerator → GPU. Save the notebook, then re-run. If GPU is
> still unavailable, check phone verification (Step 4.1).

> ⚠️ **If "Missing secret: GCP_SA_JSON"**, the secret wasn't created or wasn't
> attached. Go back to Step 4.5, check the toggle is ON for each secret.

> ⚠️ **If auth fails with permission error**, the service account email wasn't
> shared correctly. Go back to Phase 3 Step 3.6, verify the `client_email` from
> your JSON file matches what you shared, and that it has **Editor** access.

> ⚠️ **If yfinance returns 0 rows**, Yahoo Finance may be rate-limiting Kaggle
> IPs. This happens occasionally. Wait an hour and re-run. If it persists, switch
> to the fallback: upload a pre-cached OHLCV dataset (out of scope for this
> guide — see the troubleshooting appendix).

### Step 4.7 — Save the notebook

Click **Save Version** (top right) with a message like "Initial working pipeline".
This makes the notebook permanent. Without saving, Kaggle treats it as a draft.

---

## Phase 5 — Schedule Daily Runs

**What this does:** Tells Kaggle to re-run your notebook every evening, forever,
without you touching anything.

### Step 5.1 — Open the schedule panel

On your notebook page (after saving), click **⋮** (three dots, top right) →
**Schedule a notebook run**.

> ⚠️ **If you don't see "Schedule a notebook run"**, you may still be in draft
> mode. Click **Save Version** first, then try again.

### Step 5.2 — Configure the schedule

| Setting | Value |
|---------|-------|
| **Schedule name** | Leave default |
| **Frequency** | **Daily** |
| **Time** | Set to **12:00 PM UTC** (this is **7:00 PM Bangkok time**, well after SET market close at 5:00 PM) |
| **Notify on failure** | Checked (so you get an email if it fails) |

> ⚠️ **Time zone:** Kaggle schedules in UTC. Bangkok is UTC+7. 12:00 UTC =
> 19:00 BKK. The exact minute doesn't matter — the pipeline always stamps
> dates in `Asia/Bangkok`.

### Step 5.3 — Verify GPU + Internet + Secrets for scheduled runs

**IMPORTANT:** The settings you see now apply only to interactive runs.
Scheduled runs have their OWN environment settings.

1. In the schedule panel, look for the **Environment** section.
2. Confirm: **Accelerator = GPU P100**, **Internet = ON**.
3. Scroll down to **Secrets** — all 4 should show as attached.
4. Click **Save**.

> ⚠️ **Notebook settings ≠ Schedule settings.** If you set GPU in the notebook
> panel but not in the schedule panel, the scheduled run will run on CPU and
> timeout. Check BOTH.

### Step 5.4 — Test the scheduled run

Kaggle usually runs the first scheduled execution within a few minutes of saving.
To check:

1. Go to your notebook page.
2. Click the **"Runs"** tab (or use the left panel → "Your work" → find the
   notebook → click the expand arrow).
3. Look for a run labeled "Scheduled" (not "Interactive").
4. Click on it → **Logs**.
5. Verify the same output as your manual run: CUDA available, data loaded,
   `Pipeline result: {'status': 'ok'}`.

> ✅ **If the scheduled run completed with status 'ok',** you're done. The
> pipeline is autonomous.

> ⚠️ **If no scheduled run appears**, wait 10 minutes. Kaggle scheduling is
> "best-effort" — it may be delayed by a few minutes to an hour, especially
> on free tier.

---

## Phase 6 — Daily Life

### What happens each day (you do nothing)

- Evening (BKK time): Kaggle runs your notebook.
- It downloads fresh market data, runs Kronos forecasts, generates a trade
  ticket, and writes all results to Google Sheets.
- The dashboard auto-detects new data within 60 seconds and refreshes.
- You open your dashboard URL **anytime** — the data is always current.

### What you should do

| When | What |
|------|------|
| **Morning** | Open the dashboard. Check the Trade Ticket tab for buy/sell suggestions. |
| **After trading** | Enter fill prices and shares in the Trade Ticket tab's fill columns. |
| **Weekends** | Nothing. Pipeline runs Mon-Fri only. |
| **Once a month** | Check Pipeline Status tab — if it shows `failed`, check Kaggle logs. |

### Important: ~24h latency for dashboard edits

When you change your initial capital or edit/delete a trade in the dashboard,
the change is **queued**. It takes effect on the **next pipeline run** (next
evening). There is no instant "Run Now" — this is by design to keep costs at $0.

> ⚠️ **To apply an urgent change immediately:** open Kaggle, click **Run All**
> on the notebook interactively (it's idempotent — same-day re-runs don't
> duplicate data).

### To update code later

1. Pull the latest repo on your computer: `git pull`
2. Get the new commit hash: `git rev-parse --short HEAD`
3. In Kaggle, open the notebook, edit Cell 1: `PINNED_COMMIT = "newhash"`
4. Re-run manually once.
5. Save. The schedule will use the new code from the next run.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dashboard blank white page | V8 runtime not enabled | Phase 2 Step 2.5 |
| "Missing secret: GCP_SA_JSON" | Secret not attached | Phase 4 Step 4.5 — toggle ON |
| "No data yet" after successful pipeline | Web app cache | Ctrl+Shift+R to force-refresh |
| App error on dashboard | Execute-as wrong user | Redeploy as "Me" — Phase 2 Step 2.6 |
| CUDA available: False | GPU not configured for scheduled run | Phase 5 Step 5.3 |
| yfinance returns 0 data | Yahoo rate-limiting Kaggle IPs | Wait 1-2 hours, re-run |
| Pipeline status: failed | Check error_message column | Open the sheet, check Pipeline Status column D |
| Forecasts tab shows fewer than 49 tickers | Some tickers had data issues | Check Kaggle logs for SKIP/FAIL messages |
| Spreadsheet "Loading..." forever | Script quota exceeded | Wait a few minutes — auto-throttled |
| "Out of memory" during forecast | Model + data exceeds 16GB VRAM | Ensure GPU T4/P100 is selected |

---

*Setup complete. Your dashboard is at the Web App URL from Phase 2 Step 2.6.*

*This guide version: 2026-06-21.*
