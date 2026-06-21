# Kronos-TH Google Suite — Step-by-Step Setup Guide

> **For absolute beginners to Google Sheets, Apps Script, and Colab/Kaggle.**
> No prior experience needed. Each step tells you exactly what to click and what to type.
>
> **Note:** This is one of two dashboard options. The Google Suite dashboard is zero-cost, browser-based, and requires no local GPU. The Flask dashboard (`docs/dashboard-user-manual.md`) is the alternative for users with a local Python + GPU setup. Both are fully functional; choose based on your environment.
>
> **Kaggle (recommended):** The pipeline runs unattended on Kaggle's free T4 GPU each evening. See `docs/kaggle-setup.md` for the Kaggle-specific setup. If using Kaggle, skip Phases 3–6 of this guide — the daily run is automated.

---

## Before You Start

### Get these files

You need the `google_suite/` folder on your computer. This folder contains the notebook, scripts, and code for the dashboard. Here's how to get it:

1. Go to **https://github.com/Yutwizard/Kronos_Thai_Retail**
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Open the downloaded ZIP file on your computer
5. Extract (unzip) it — on most computers, double-clicking the ZIP file does this
6. Inside the extracted folder, find the folder named `google_suite`
7. Remember where this folder is — you'll need it throughout this guide

> If someone sent you these files (e.g. via email, USB drive), just save the `google_suite` folder somewhere you can find it, like your **Desktop** or **Downloads** folder.

### You need a Google Account

A **Google Account** (Gmail is enough). If you don't have one:

1. Go to https://accounts.google.com/signup
2. Fill in your name, email preference, password
3. Verify your phone number
4. Done. You now have a Google Account.

---

## Phase 1 — Create the Spreadsheet (Google Sheets)

Google Sheets is like Microsoft Excel but inside your web browser.

### Step 1.1 — Create a new spreadsheet

1. Open your web browser and go to **https://sheets.new**
   - This creates a brand new spreadsheet automatically
   - Alternatively: go to https://sheets.google.com → click the big **+** (plus) button

2. You'll see a blank grid with "Untitled spreadsheet" at the top

3. Click where it says **"Untitled spreadsheet"** (top-left corner)

4. Type: `Kronos-TH Portfolio`
   - Press **Enter** on your keyboard to save the name

### Step 1.2 — Find your Spreadsheet ID

You will need this ID later. Here's how to find it:

1. Look at the web address (URL) in your browser's address bar
   - It looks like: `https://docs.google.com/spreadsheets/d/`**`abc123xyz789`**`/edit`
2. The long random-looking part between `/d/` and `/edit` is your **Spreadsheet ID**
3. **Copy it now** and paste into a text file or sticky note — you will need it later

Example:
```
Full URL:  https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890/edit
ID:        1aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890
```

### Step 1.3 — Rename the first sheet tab

At the bottom of the screen you'll see a tab labelled **"Sheet1"**.

1. Double-click on the word **"Sheet1"**
2. Type: `Portfolio`
3. Press **Enter**

### Step 1.4 — Add the first header row

1. Click on cell **A1** (the top-left cell)
2. Type or copy-paste this exactly:
   ```
   cash,initial_capital,mode,model_version,forecast_date
   ```
3. Press **Enter**
   - After pressing Enter, the blue box moves down to cell A2. That's normal.

Now we need to split the text into separate columns (one word per column):

4. **Click back on cell A1** (the blue box should be around A1 again)
5. Click the menu **Data** (at the top of the screen)
6. Click **Split text to columns**
7. A small panel appears at the bottom — click the dropdown that says **"Detect automatically"**
8. Choose **"Comma"** from the list
9. The text splits into 5 separate columns (A through E), each with its own header word

### Step 1.5 — Create the remaining 17 tabs

Now add the rest of the sheet tabs. For each one:

1. Click the **+** (plus) icon at the bottom-left of the screen (next to your "Portfolio" tab)
   - This creates a new blank tab
2. Double-click the new tab name (like "Sheet2")
3. Type the exact tab name from the list below
4. Press **Enter**
5. Click cell **A1** in the new tab
6. Copy the header row text below
7. Press **Ctrl+V** (Windows) or **Cmd+V** (Mac) to paste
8. Click **Data > Split text to columns > Comma** (same as step 1.4)

**The `Portfolio` tab was already created in Step 1.3.** Skip it here and create tabs 2 through 10:

| # | Tab name | Paste this into A1 |
|---|----------|--------------------|
| 2 | `Equity Curve` | `date,equity,cash,invested` |
| 3 | `Positions` | `ticker,shares,avg_cost,entry_date,sector,current_price,pnl,pnl_pct,pct_to_stoploss` |
| 4 | `Trade Log` | `timestamp,ticker,action,shares,price,rationale,friction_cost,model_version,id,ref_id` |
| 5 | `Forecasts` | `date_updated,ticker,rank_score,exp_ret,band_width,confidence,net_return,p5,p50,p95,sector` |
| 6 | `Forecast History` | `date,ticker,predicted_direction,predicted_return,entry_close,actual_return,was_correct` |
| 7 | `Trade Ticket` | `ticker,action,shares,est_cost_thb,rationale,sector,confidence,filled_price,filled_shares,fill_timestamp` |
| 8 | `Risk Metrics` | *This one is long. Copy-paste this exactly:*<br>`date,equity,cash,deployed_pct,trailing_sharpe_12w,max_drawdown_pct,mtd_pnl_pct,trade_win_rate,calmar_ratio,sortino_ratio,drawdown_velocity,allocation_band,allocation_pct,market_state,is_frozen,bootstrap_p_value,friction_ytd_pct,friction_ytd_thb` |
| 9 | `Pipeline Status` | `last_run_timestamp,status,duration_seconds,error_message,sheets_updated` |
| 10 | `Calibration` | `date,coverage,n_samples,status` |

**Staging tabs (8):** `Portfolio_staging`, `Positions_staging`, `Forecasts_staging`, `Trade Ticket_staging`, `Risk Metrics_staging`, `Equity Curve_staging`, `Trade Edits`, `Capital Reset`

> **Note:** `Trade Edits` and `Capital Reset` are written by the Apps Script dashboard (not by the Colab/Kaggle pipeline) and read by the pipeline's Cells 9b and 4b respectively. Leave their A1 cells empty — the dashboard populates them.

**Now create tabs 11 through 18** — these are "staging" copies used by the pipeline. For each one, you will **copy the headers from the matching tab above**:

| # | Tab name | How to fill A1 |
|---|----------|----------------|
| 11 | `Portfolio_staging` | Copy headers from the **Portfolio** tab (instructions below) |
| 12 | `Positions_staging` | Copy headers from the **Positions** tab |
| 13 | `Forecasts_staging` | Copy headers from the **Forecasts** tab |
| 14 | `Trade Ticket_staging` | Copy headers from the **Trade Ticket** tab |
| 15 | `Risk Metrics_staging` | Copy headers from the **Risk Metrics** tab |
| 16 | `Equity Curve_staging` | Copy headers from the **Equity Curve** tab |
| 17 | `Trade Edits` | Leave A1 empty (Apps Script dashboard populates this) |
| 18 | `Capital Reset` | Leave A1 empty (Apps Script dashboard populates this) |

For each staging tab (11-18), do this:
1. Click on the **matching original tab** (e.g. click "Portfolio" at the bottom)
2. Click cell **A1**, then hold **Shift** and click the last header cell (e.g. E1 for Portfolio — 5 columns) to select all headers
3. Press **Ctrl+C** (Windows) or **Cmd+C** (Mac) to copy
4. Click the **staging tab** at the bottom (e.g. "Portfolio_staging")
5. Click cell **A1**
6. Press **Ctrl+V** (Windows) or **Cmd+V** (Mac) to paste
   - The headers will paste as separate cells automatically — no need to split

### Step 1.6 — Verify you have exactly 18 tabs

Check the bottom of your screen. You should see these 18 tabs in order:
```
Portfolio | Equity Curve | Positions | Trade Log | Forecasts | Forecast History | Trade Ticket | Risk Metrics | Pipeline Status | Calibration | Portfolio_staging | Positions_staging | Forecasts_staging | Trade Ticket_staging | Risk Metrics_staging | Equity Curve_staging | Trade Edits | Capital Reset
```

**Keep this browser tab open.** You'll come back to it later.

---

## Phase 2 — Set Up Apps Script (the dashboard web app)

Apps Script is Google's built-in coding tool. You access it from inside your spreadsheet.

### Step 2.1 — Open Apps Script

1. In your spreadsheet, look at the top menu
2. Click **Extensions**
3. From the dropdown, click **Apps Script**
   - A new browser tab opens with a code editor
   - It looks like a simple text editor with a white background
   - You'll see some placeholder code that says `function myFunction() { ... }`

### Step 2.2 — Delete the placeholder code

1. Click anywhere inside the large text area
2. Press **Ctrl+A** (Windows) or **Cmd+A** (Mac) to select all the text
3. Press **Delete** or **Backspace** to clear it

### Step 2.3 — Paste Code.gs

Now you need the code from the file `apps_script/Code.gs`.

1. Find the `google_suite` folder on your computer (the one you downloaded in "Before You Start")
2. Open the `apps_script` folder inside it
3. You'll see two files: `Code.gs` and `Index.html`
4. **Open `Code.gs` in a text editor:**
   - **Windows:** Right-click `Code.gs` → **Open with** → **Notepad**
   - **Mac:** Right-click `Code.gs` → **Open With** → **TextEdit**
   - (If you can't find Notepad/TextEdit, just double-click the file — it opens in your browser. Then press **Ctrl+A** to select all, **Ctrl+C** to copy.)
5. In the text editor, press **Ctrl+A** (Windows) or **Cmd+A** (Mac) to select **all** the text
6. Press **Ctrl+C** (Windows) or **Cmd+C** (Mac) to copy it
7. Go back to the Apps Script browser tab
8. Click in the empty code area
9. Press **Ctrl+V** (Windows) or **Cmd+V** (Mac) to paste

You should now see about 98 lines of code in the editor.

### Step 2.4 — Create the Index.html file

Now you need to add a second file to the Apps Script project (so far you only have Code.gs).

1. In Apps Script, look at the left sidebar where it says **Files**
2. Click the **+** (plus) icon next to "Files" to add a new file
   - If you don't see a + icon, look for a button that says **"Add a file"** or **"+ Add"** near the top of the Files panel
   - If still unsure, click the three-dot menu (⋮) next to "Files" and choose **"Create file"**
3. A menu pops up — choose **HTML**
4. A dialog box appears asking for a filename
5. Type: `Index` (capital I, rest lowercase — this is IMPORTANT)
6. Click **Create**
7. A new editor tab opens next to `Code.gs`
8. You'll see placeholder HTML code. Select it all (Ctrl+A) and delete it (Delete)

Now paste the Index.html code:

9. Go back to your computer's `google_suite/apps_script/` folder
10. Open `Index.html` in Notepad or TextEdit (same as step 2.3)
11. Press **Ctrl+A** to select all text, **Ctrl+C** to copy it
12. Go back to Apps Script, click in the empty Index.html editor area
13. Press **Ctrl+V** to paste

You should now see about 612 lines of HTML code.

### Step 2.5 — Check the two files exist

Look at the left sidebar of Apps Script. You should see two files listed:
- `Code.gs` (under "Files")
- `Index.html` (under "HTML Files")

### Step 2.6 — Verify V8 runtime

1. In Apps Script, click **Project Settings** (the gear icon in the left sidebar)
2. Scroll down to "Runtime"
3. Make sure **"V8"** is selected (not "Rhino")
4. If it says "Rhino", click the dropdown and change it to "V8"

### Step 2.7 — Deploy the web app

1. In Apps Script, click the **Deploy** button (top-right, green or blue)
2. Click **New deployment**
3. A panel opens. Next to "Select type", click the gear icon
4. Choose **Web app**
5. Fill in the form:
   - **Description:** `Kronos-TH Portfolio Dashboard` (or anything you like)
   - **Execute as:** Choose **Me** (this is important)
   - **Who has access:** Choose **Only myself** (or "Anyone" if you want to share with others)
6. Click **Deploy**
7. A popup appears asking you to review permissions — click **Authorize access**
8. A new window opens asking you to choose a Google account — click yours
9. A warning screen says **"This app isn't verified"** — this is normal!
   - Google shows this for ANY personal project you create yourself, even big companies' apps go through this
   - It says "unsafe" but that's because Google hasn't reviewed it — YOU wrote this code, so you know it's safe
   - Click **Advanced** (small text near the bottom-left)
   - Click **Go to Kronos-TH Portfolio Dashboard (unsafe)**
   - Click **Allow** (check the boxes and click the blue button)
   - You will be sent back to the deployment panel automatically

### Step 2.8 — Copy your Web App URL

1. You'll see a field called **"Web app"** with a URL like:
   `https://script.google.com/macros/s/abc123xyz/exec`
2. Click the **Copy** icon next to the URL
3. Paste this URL into a text file or sticky note — this is your dashboard URL
4. Click **Done**

**Important:** The Apps Script web app URL stays the same across deploys **only if you do NOT create a new deployment**. To publish updated code: in Apps Script editor, click "Deploy" → "Manage deployments" → pencil icon next to the existing deployment → update version → Deploy. The URL is unchanged.

If you click "Deploy" → "New deployment", you get a new URL. This is almost never what you want.

### Step 2.9 — Test your web app

1. Open a new browser tab
2. Paste the Web App URL you just copied
3. Press **Enter**
4. You should see a page titled "Kronos-TH Portfolio" with:
   - A **gray banner** at the top saying **"No data yet. Run the Colab pipeline first."**
   - Five tabs: Dashboard, Positions, Trade Log, Forecasts, Trade Ticket
   - All tabs show empty state messages — this is normal! The spreadsheet has no data yet because you haven't run the pipeline.

If you see the page with the gray banner and five tabs, **congratulations — the dashboard is working!** The "No data yet" message means it's connected to your spreadsheet correctly. Data will appear after you run the Colab pipeline in Phase 4.

**What you'll see once the pipeline has run at least once:**
- **Reset Portfolio (⚙ button, top-right of Dashboard)** — change your initial capital
- **Trade Log edit/delete** — click ✏️ or 🗑️ in any Trade Log row
- **Health banner** — appears on Dashboard if P5/P95 band coverage diverges from 90% target
- **First-run setup banner** — appears once when no portfolio exists yet

**Common problem:** If you see a blank white page, try:
- Wait 30 seconds and refresh
- Make sure both Code.gs and Index.html are saved (Ctrl+S each)
- Re-deploy: **Deploy > Manage deployments > Edit (pencil icon) > Version: New version > Deploy**

---

## Phase 3 — Set Up Colab (if using Kaggle, skip to `docs/kaggle-setup.md`)

Google Colab is a website that lets you run Python code (including AI models) in your browser using Google's computers.

### Step 3.1 — Find the notebook file on your computer

1. Remember the `google_suite` folder from "Before You Start"? Find it on your computer
2. Inside it, you'll see a file called `kronos_daily_pipeline.ipynb`
3. This is the Colab notebook — you'll upload it to Google in a moment

### Step 3.2 — Open Google Colab

1. Go to **https://colab.research.google.com**
   - If you're not signed in, click "Sign in" (top-right) and use your Google Account
2. You'll see a welcome screen with options

### Step 3.3 — Upload the notebook

1. Click **File** (top menu)
2. Click **Upload notebook**
3. Click the **"Choose File"** button
4. Find and select `kronos_daily_pipeline.ipynb` on your computer
5. Click **Open**

The notebook opens with 44 cells (23 code cells + 21 explanation cells). You can scroll through them.

### Step 3.4 — Set runtime to GPU (IMPORTANT)

The forecast step requires a GPU (graphics card). Without this, the notebook WILL crash.

1. In Colab, click **Runtime** (top menu)
2. Click **Change runtime type**
3. In the panel that opens, find **Hardware accelerator**
4. Click the dropdown — it probably says "None" or "CPU"
5. Choose **T4 GPU**
6. Click **Save**

### Step 3.5 — Configure secrets

Colab Secrets are like a password vault. You'll store your Spreadsheet ID here.

1. Look at the left sidebar of Colab — there are several icons
2. Click the **key icon** (tooltip says "Secrets")
   - If you don't see it, click the **>** arrow at the far left to expand the sidebar
   - If you still don't see it, click the three-line menu icon (hamburger) top-left, then **Secrets**
3. Click **+ Add new secret**
4. A new row appears. Fill it in:
   - **Name:** type `KRONOS_SPREADSHEET_ID` (exactly like this, all caps)
   - **Value:** paste your Spreadsheet ID (from Phase 1.2)
5. Under **"Notebook access"**, check the box or toggle the switch so this notebook can use the secret (it should show the notebook's name)
6. Click **+ Add new secret** again
7. **Name:** `LINE_NOTIFY_TOKEN`
8. **Value:** leave blank (this is optional — for LINE messaging)
9. Make sure the "Notebook access" box is checked for this one too

### Step 3.6 — Upload project folder to Google Drive (IMPORTANT)

The notebook needs the entire `Kronos_Thai_Retail` project folder on your Google Drive. This folder contains the `kth/` package (data loader, model, backtester) and `data/` cache.

1. Open a new browser tab and go to **https://drive.google.com**
2. Look at the top-left, click **+ New** (blue button)
3. A menu appears with several options. Click **Folder upload** (NOT "File upload")
4. A file picker opens. Find the `Kronos_Thai_Retail` folder on your computer (the one you extracted from the ZIP in "Before You Start")
5. Select the **entire `Kronos_Thai_Retail` folder** (not just the files inside it) and click **Upload**
   - **Windows:** Click the folder once to highlight it, then click **OK**
   - **Mac:** Click the folder once, then click **Upload**
6. Wait for the upload to finish — this takes 1-2 minutes depending on your internet
7. Once done, you should see a folder named `Kronos_Thai_Retail` in your Google Drive

**Important:** The notebook assumes this folder is at `/content/drive/MyDrive/Kronos_Thai_Retail`. If you upload it to a subfolder (e.g. inside a "Trading" folder), you'll need to update the path in Step 3.8 below.

### Step 3.7 — Mount Google Drive

The notebook needs access to your Google Drive to read the project files and save data.

1. Skip this for now — the notebook does this in Cell 1 automatically
2. When you run Cell 1, Colab will ask you to:
   - Choose your Google account
   - Click "Allow" for permissions
   - This mounts your Google Drive so the notebook can read/write files

### Step 3.8 — Know your Drive path

The notebook assumes your project folder is at `/content/drive/MyDrive/Kronos_Thai_Retail`.

If you uploaded the folder to a different location on Google Drive:
1. In Cell 1 (the first code cell), find this line:
   ```python
   KTH_REPO = '/content/drive/MyDrive/Kronos_Thai_Retail'
   ```
2. Change it to match where the folder actually lives
3. Examples:
   - In a "Trading" folder: `KTH_REPO = '/content/drive/MyDrive/Trading/Kronos_Thai_Retail'`
   - Named differently: `KTH_REPO = '/content/drive/MyDrive/MyProject'`

### Step 3.9 — Set your starting capital

In Cell 2, find this line:
```python
INITIAL_CAPITAL = 500_000.0   # ← CHANGE THIS
```

Change `500_000.0` to however much money you're starting with (in Thai Baht). Examples:
- 100,000 baht: `INITIAL_CAPITAL = 100_000.0`
- 1,000,000 baht: `INITIAL_CAPITAL = 1_000_000.0`

### Step 3.10 — Save a copy to your Drive

1. Click **File > Save a copy in Drive**
2. This saves the **notebook itself** to your Google Drive so you can find it later
3. Close the original "Uploaded" tab
4. Open your saved copy from **File > Open notebook > Recent**

> Your project folder (with `kth/`, `data/`, etc.) was already uploaded to Drive in Step 3.6. The notebook + the project folder are now both on Google Drive — that's everything you need.

---

## Phase 4 — First Run (Colab; automated on Kaggle)

### Step 4.1 — Run the entire notebook

1. Click **Runtime** (top menu)
2. Click **Run all**
   - Colab will start running each cell one by one
   - A blue bar at the top shows progress
   - This takes about **5-10 minutes** total

### Step 4.2 — What each cell does

| Cell | What happens | Time | What to check |
|------|-------------|------|---------------|
| 1 | Mounts Google Drive, installs packages | ~1 min (first time only) | A popup asks you to choose your Google account and allow Drive access — click your account then **Allow** |
| 2 | Loads secrets (spreadsheet ID) | ~2 sec | Should print "Spreadsheet ID: abc12345..." |
| 3 | Authenticates to Google Sheets | ~5 sec | **Another popup appears** asking you to choose your account and allow Sheets access — click your account, then **Allow** (this is normal, you need to approve both) |
| 4 | Initializes portfolio if first run | ~2 sec | Prints "First run: portfolio initialised" |
| 5 | Sets pipeline status to "running" | ~2 sec | Prints "Pipeline started at 08:15:00 BKK" |
| 6 | Reads any pending fills | ~2 sec | Prints "Fills: 0 confirmed, 0 assumed, 0 total" (first run) |
| 7 | Downloads OHLCV data | ~2 min | Prints "Loaded 100 tickers \| 0 failed/excluded" |
| 8 | Runs Kronos forecasts | ~3-5 min | Prints "Forecasts done. Cache at: ..." |
| 9 | Syncs portfolio from Sheets | ~2 sec | Prints "Portfolio synced: ฿XXX cash, 0 positions" |
| 10 | Generates trade ticket | ~2 sec | Prints "Ticket: 0 exits 0 reduces N buys" |
| 11 | Computes risk metrics | ~2 sec | Prints "Band: NEUTRAL Sharpe: 0.00 MaxDD: 0.00%" |
| 12 | Validates data | ~2 sec | Prints "Validation passed. 0 positions" |
| 13 | Writes to staging sheets | ~5 sec | Prints "All 5 staging sheets written." |
| 14 | Promotes staging to live | ~5 sec | Prints "Staging promoted to live sheets." |
| 15 | Appends trade log | ~2 sec | Prints "Trade Log: 0 new entries appended." (first run) |
| 16 | Updates forecast history | ~2 sec | Prints "Forecast History: appended N predictions." |
| 17 | Sets status to "completed" | ~2 sec | Prints "Pipeline completed in XXXs." |
| 18 | Sends LINE notification | ~2 sec | Prints nothing and skips silently if no LINE token was set |
| 19 | Prints summary table | ~2 sec | Shows a table with all key metrics |

**Optional cells (run only when triggered):**

| Cell | When to run | What it does |
|------|------------|--------------|
| **4b** — Apply Capital Reset | Only when the Apps Script shows a "setup/reset queued" banner (first-run or after ⚙ Settings → Reset) | Reads `Capital Reset` sheet, calls `reset_portfolio()`, clears the sheet, re-runs staging writes + promotion. **Run instead of** Cells 5–15 in this single session. |
| **9b** — Apply Trade Edits | Only when the Apps Script shows a "trade edit(s) pending" banner (after clicking ✏️ or 🗑️ in the Trade Log) | Reads `Trade Edits` sheet, calls `edit_trade()` / `delete_trade()` for each row, clears the sheet, re-runs staging writes + promotion. **Run instead of** Cells 9–15 in this single session. |
| **11b** — Compute Calibration | Runs automatically in the normal Run-All path (between Cells 11 and 12) | Appends today's P5/P95 band coverage to the `Calibration` sheet for the health banner. |
| **13b** — Append Equity Curve | Runs automatically in the normal Run-All path (between Cells 13 and 14) | Appends today's equity, cash, and invested values to `Equity Curve_staging` (promoted to live in Cell 14). |

### Step 4.3 — Check for errors

- If a cell has a **red X** icon next to it, something went wrong
- Read the error message in red text below that cell
- Common first-run errors and fixes:

| Error | Fix |
|-------|-----|
| `Cell 1: "Cannot mount Drive"` | Make sure you clicked "Allow" when the popup appeared |
| `Cell 2: "KRONOS_SPREADSHEET_ID not found"` | Go back to Colab Secrets (Phase 3.5) and add the secret correctly |
| `Cell 3: "Spreadsheet not found"` | Your Spreadsheet ID is wrong — re-check it from the URL |
| `Cell 8: "CUDA error"` | You didn't set GPU runtime — go back to Phase 3.4 |
| `Cell 8: "out of memory"` | Close other browser tabs, or try reducing n_samples to 20 |
| `pip install` errors | Click **Runtime > Restart runtime** and try Run All again |

### Step 4.4 — After successful first run

1. Go back to your spreadsheet (`Kronos-TH Portfolio`)
2. Click on the **Portfolio** tab
3. You should see data in row 2: your cash, initial capital, etc.
4. Click on the **Forecasts** tab
5. You should see rows of tickers with their expected returns
6. Click on the **Pipeline Status** tab
7. You should see "completed" with a duration

---

## Phase 5 — Using the Web App Dashboard

### Step 5.1 — Open your dashboard

1. Open the Web App URL you saved in Phase 2.8
2. Bookmark it in your browser for daily use
3. You'll see a gray banner: **"No data yet. Run the Colab pipeline first."** — this is expected. The dashboard is connected to your spreadsheet, but the spreadsheet is empty until the pipeline runs. After Phase 4 (First Run), refresh this page and you'll see your real data.

### Step 5.2 — Confirm dashboard is using live data

The dashboard is already set up to load real data from your spreadsheet. No changes needed. To confirm:

1. Go to Apps Script (from Phase 2.1: **Extensions > Apps Script**)
2. Click on `Index.html` in the left sidebar
3. Press **Ctrl+F** (Windows) or **Cmd+F** (Mac) to search. Type `renderAll`
4. You should see **only one result**: `renderAll(d)` inside the `withSuccessHandler` block — like this:
   ```javascript
   showSpinner();
   google.script.run
     .withSuccessHandler(function(d) { hideSpinner(); renderAll(d); })
     .withFailureHandler(showError)
     .getAllData();
   ```
   If you see this, the dashboard is already on live data. **You're done — skip to Step 5.3.**

5. If instead you see `renderAll(MOCK)`, the dashboard is showing fake sample data. Fix it:
   - Find these lines near the bottom:
     ```javascript
     hideSpinner();
     renderAll(MOCK);
     ```
   - Put `//` in front of each line to disable them:
     ```javascript
     // hideSpinner();
     // renderAll(MOCK);
     ```
   - Find the `/*` and `*/` lines around the `google.script.run` block and delete them
   - Press **Ctrl+S** to save
   - **Deploy > Manage deployments > Edit (pencil) > New version > Deploy**
   - Refresh the dashboard

### Step 5.3 — What each tab shows

**Dashboard tab:**
- Big number at top: your total portfolio value
- Four cards: P&L this month, 12-week Sharpe ratio, Maximum drawdown, Friction YTD
- Regime badge (BULL/NEUTRAL/BEAR/EXIT) showing your current allocation band
- Equity curve chart (blue line = portfolio, grey dashed = initial capital)
- Fill confirmation status for today's trades

**Positions tab:**
- Table of all open positions
- Columns: Ticker, Shares, Avg Cost, Entry Date, Sector, Current Price, P&L %, % to Stop
- Sortable — click any column header to sort
- Red background on % to Stop if it's below 3% (close to stop-loss)
- "Portfolio frozen" red banner if drawdown limit was hit

**Trade Log tab:**
- Complete history of all trades
- Sortable by date, ticker, action
- Cancel entries shown with strikethrough

**Forecasts tab:**
- Two sub-tabs: "Forecasts" and "Accuracy History"
- Forecasts: expected returns, confidence badges (green/yellow/red), P50 prices
- Accuracy History: past predictions vs actual outcomes, accuracy percentage
- Sortable by any column

**Trade Ticket tab:**
- Today's recommended trades (buys, sells, reduces)
- Action banner telling you what to do (yellow = pending, green = confirmed)
- **Export CSV** button — downloads a file you can send to your broker
- **Refresh** button — manually reloads data from Google Sheets
- T+2 warning if you're both buying and selling (proceeds settle in 2 days)

---

## Phase 6 — Daily Routine (Colab manual; automated on Kaggle)

Every trading morning (Bangkok time, 7:00-8:30):

### Step 6.1 — Run the pipeline

1. Go to **https://colab.research.google.com**
2. Open your saved notebook:
   - Click **File > Open notebook**
   - Click the **Google Drive** tab
   - Find `Copy of kronos_daily_pipeline` (or `kronos_daily_pipeline`) and click it
   - Alternatively, go to **https://drive.google.com**, find the file, and double-click it
3. Click **Runtime > Run all**
4. Wait 5-10 minutes for it to complete
5. Check Cell 19 for the summary table — make sure there are no errors

### Step 6.2 — Review the dashboard

1. Open your Web App dashboard
2. Check the **Dashboard** tab for current portfolio value and metrics
3. Check the **Forecasts** tab for today's predicted winners/losers
4. Check the **Trade Ticket** tab for today's recommended trades

### Step 6.3 — Execute trades

1. On the **Trade Ticket** tab, click **Export CSV**
2. A file called `kronos_ticket.csv` downloads to your computer
3. Open this CSV in a text editor or Excel — it lists which stocks to buy/sell and how many shares
4. Place these orders at your broker (broker app, website, or phone call)
   - **Don't have a broker yet?** No problem — you can still run the pipeline every day to see what it recommends. The forecasts are useful even without trading. Just skip to "Step 6.5 — Check tomorrow".
5. After each order fills, note the actual price and number of shares

### Step 6.4 — Enter fills

1. Go to your spreadsheet (`Kronos-TH Portfolio`)
2. Click the **Trade Ticket** tab at the bottom
3. Find the row for each trade you executed (look at the ticker name in column A)
4. Fill in columns **H**, **I**, and **J** (each column has a letter at the very top):
   - **H (filled_price):** The actual price you paid/received (e.g. 33.50)
   - **I (filled_shares):** The actual number of shares filled (e.g. 1000)
   - **J (fill_timestamp):** Date and time of fill (e.g. `2026-06-04 09:15`)
5. **Important:** If an order didn't fill at all, leave the row as-is
6. Next time you run the pipeline, these fills will be applied automatically

### Step 6.5 — Check tomorrow

The next morning, start again from Step 6.1. The pipeline reads yesterday's fills and generates today's trade ticket.

---

## Phase 7 — Migrating Existing Data (if you already have trades)

If you've been using the Flask dashboard and have existing trades in `data/positions/`:

### Step 7.1 — Run the migration script

> **This step requires using the terminal (command line).** If you've never used a terminal before, that's OK — just ask a developer friend to run this for you. It takes 30 seconds.

1. Open your terminal:
   - **Windows:** Press **Windows key**, type `cmd`, press **Enter**
   - **Mac:** Press **Cmd+Space**, type `terminal`, press **Enter**
2. Navigate to the `Kronos_Thai_Retail` folder:
   ```bash
   cd path/to/Kronos_Thai_Retail
   ```
   (Replace `path/to/` with the actual location of the folder on your computer)

3. Install the `kth` package:
   ```bash
   pip install -e .
   ```
   (If you get "pip not found", type `pip3 install -e .` instead)

4. Run the migration:
   ```bash
   python google_suite/migrate_to_sheets.py --id YOUR_SPREADSHEET_ID
   ```
   Replace `YOUR_SPREADSHEET_ID` with the ID you copied in Phase 1.2

5. A browser window opens asking you to sign in to Google — click your account
6. Click **Allow** for permissions
7. The script migrates:
   - Your portfolio JSON → Portfolio sheet
   - Your equity curve → Equity Curve sheet
   - Your trade log CSV → Trade Log sheet

---

## Troubleshooting

### After Phase 4, the dashboard still shows "No data yet"

1. Open the Web App URL
2. Click the **Refresh** button on the Trade Ticket tab
3. If still empty: go to your spreadsheet and check the **Portfolio** tab has data in row 2
4. If row 2 is empty, the pipeline didn't complete — go back to Colab and check for red X errors
5. If the Portfolio tab has data but the dashboard still shows "No data yet": re-deploy the web app (Deploy > Manage deployments > New version > Deploy)

### Spreadsheet says "Loading..." forever

1. Check your internet connection
2. Refresh the page (F5)
3. Wait 30 seconds

### Web app shows blank white page

1. Open Apps Script (**Extensions > Apps Script** from the spreadsheet)
2. Click **Deploy > Manage deployments**
3. Click the pencil (edit) icon
4. Click **New version**
5. Click **Deploy**
6. Wait 2 minutes
7. Refresh the web app

### Web app shows "App error: TypeError: Cannot read property..."

1. Your spreadsheet might be missing some data
2. Make sure you've run the Colab pipeline at least once successfully
3. Check that all 18 tabs exist with correct headers
4. Redeploy the web app

### Colab cell 8 fails with "out of memory"

1. Click **Runtime > Factory reset runtime** (this clears memory)
2. Set runtime to GPU: **Runtime > Change runtime type > T4 GPU**
3. In Cell 8, change `n_samples=50` to `n_samples=20` (fewer samples = less memory)
4. Click **Runtime > Run all** again

### Colab says "You are on a free tier and GPU may be limited"

1. This is normal for free Colab — you may need to wait if GPU quota is exceeded
2. Try running the notebook on CPU instead (much slower but works):
   - In Cell 8, change `device='cuda'` to `device='cpu'`
   - Runtime > Change runtime type > None (no accelerator)
3. Or wait a few hours for GPU quota to reset

### "gspread.exceptions.APIError: 429" (too many writes)

1. This happens if the pipeline runs too fast
2. Open Cell 13 in the notebook
3. Find `time.sleep(1)` and change it to `time.sleep(2)`
4. Re-run

### "Entry_date" data keeps disappearing

This is a known quirk. Cell 9 in the notebook now reads `entry_date` from the Positions sheet and stores it in the JSON file, then Cell 13 writes it back. If it still disappears:
1. Open the **Positions** sheet in your spreadsheet
2. Make sure every position row has a value in column D (entry_date)
3. Re-run the pipeline

### CANCEL a wrong trade

If you entered a fill by mistake:
1. Go to the **Trade Log** sheet in your spreadsheet
2. In the next available row, enter:
   - timestamp: today's date
   - ticker: the same ticker
   - action: `CANCEL`
   - ref_id: the original trade's ID (column I of the original row)
3. Also manually fix the **Portfolio** sheet:
   - Add back the cash that was subtracted
   - In **Positions** sheet: remove or adjust the position
4. Run the pipeline to sync

---

## Keyboard Shortcuts Reference

| Action | Windows | Mac |
|--------|---------|-----|
| Copy | Ctrl+C | Cmd+C |
| Paste | Ctrl+V | Cmd+V |
| Select all | Ctrl+A | Cmd+A |
| Save (Apps Script) | Ctrl+S | Cmd+S |
| Find in page | Ctrl+F | Cmd+F |
| Refresh page | F5 | Cmd+R |
| New browser tab | Ctrl+T | Cmd+T |
| Open Colab notebook quickly | https://colab.new | (same) |
| Open Sheets quickly | https://sheets.new | (same) |

---

## Quick Reference Card (print this)

```
┌────────────────────────────────────────────────────────────┐
│              KRONOS-TH — DAILY CHECKLIST                    │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ☐ 1. Open Colab → Runtime > Run all (5-10 min)            │
│  ☐ 2. Check Cell 19 for errors                              │
│  ☐ 3. Open Web App dashboard                                │
│  ☐ 4. Review Trade Ticket tab                               │
│  ☐ 5. Export CSV → place orders at broker                   │
│  ☐ 6. Enter fills in Trade Ticket sheet (cols H-J)          │
│                                                             │
│  Web App URL: _________________________________             │
│  Spreadsheet ID: _________________________________          │
│  Colab notebook: Google Drive → Kronos repo                 │
│                                                             │
│  ⚠ Always set runtime to T4 GPU before Run All             │
│  (Run All handles cell order automatically — don't worry)   │
└────────────────────────────────────────────────────────────┘
```
