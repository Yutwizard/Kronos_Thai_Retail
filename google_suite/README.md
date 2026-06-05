# Google Suite Dashboard — Kronos-TH

Replaces the local Flask dashboard with a zero-cost Google-hosted stack:
- **Google Colab** — daily compute engine (T4 GPU)
- **Google Sheets** — persistent data store + fill-confirmation input
- **Google Apps Script web app** — 5-tab dashboard accessible from any device

## Prerequisites

- Colab runtime: **Runtime > Change runtime type > T4 GPU** (Cell 8 requires CUDA)
- Google account that owns the spreadsheet
- `kth/` package installed on Drive: `pip install -e /content/drive/MyDrive/Kronos_Thai_Retail`

## Spreadsheet Setup

Create a spreadsheet named **"Kronos-TH Portfolio"** with these 14 tabs. For each tab, paste the header row into cell A1, then **Data > Split text to columns > Separator: comma**.

| Tab name | Row 1 headers |
|----------|--------------|
| `Portfolio` | `cash,initial_capital,mode,model_version,forecast_date` |
| `Equity Curve` | `date,equity,cash,invested` |
| `Positions` | `ticker,shares,avg_cost,entry_date,sector,current_price,pnl,pnl_pct,pct_to_stoploss` |
| `Trade Log` | `timestamp,ticker,action,shares,price,rationale,friction_cost,model_version,id,ref_id` |
| `Forecasts` | `date_updated,ticker,rank_score,exp_ret,band_width,confidence,net_return,p5,p50,p95,sector` |
| `Forecast History` | `date,ticker,predicted_direction,predicted_return,entry_close,actual_return,was_correct` |
| `Trade Ticket` | `ticker,action,shares,est_cost_thb,rationale,sector,confidence,filled_price,filled_shares,fill_timestamp` |
| `Risk Metrics` | `date,equity,cash,deployed_pct,trailing_sharpe_12w,max_drawdown_pct,mtd_pnl_pct,trade_win_rate,calmar_ratio,sortino_ratio,drawdown_velocity,allocation_band,allocation_pct,market_state,is_frozen,bootstrap_p_value,friction_ytd_pct,friction_ytd_thb` |
| `Pipeline Status` | `last_run_timestamp,status,duration_seconds,error_message,sheets_updated` |
| `Portfolio_staging` | (same as Portfolio) |
| `Positions_staging` | (same as Positions) |
| `Forecasts_staging` | (same as Forecasts) |
| `Trade Ticket_staging` | (same as Trade Ticket) |
| `Risk Metrics_staging` | (same as Risk Metrics) |

## Apps Script Setup

1. From within the spreadsheet: **Extensions > Apps Script** (not script.google.com)
2. Paste `apps_script/Code.gs` (replace default `myFunction`)
3. **File > New > HTML file**, name it `Index`, paste `apps_script/Index.html`
4. **Project Settings > Runtime version:** V8
5. **Deploy > New deployment > Web app**
   - Execute as: **Me**
   - Who has access: **Only myself**
6. Copy the web app URL — this is your dashboard URL

> ⚠️ Every edit to `Code.gs` requires: **Deploy > Manage deployments > Edit (pencil icon) > Version: New version > Deploy**. The URL stays the same.

## Colab Secrets

Click the key icon in the Colab left sidebar → Add new secret:

| Secret name | Value |
|-------------|-------|
| `KRONOS_SPREADSHEET_ID` | Your spreadsheet ID (from the URL: `docs.google.com/spreadsheets/d/<ID>/`) |
| `LINE_NOTIFY_TOKEN` | (optional) LINE Notify personal access token |

## First Run

1. Open `kronos_daily_pipeline.ipynb` in Colab
2. **Runtime > Change runtime type > T4 GPU**
3. In Cell 1, verify `KTH_REPO` matches your Drive path
4. In Cell 2, set `INITIAL_CAPITAL` to your starting capital in THB
5. **Run All** (takes ~5-10 min: 2 min data download + 3-5 min forecasts)

## Dashboard Features

| Tab | Features |
|-----|----------|
| **Dashboard** | Total capital, P&L MTD, Sharpe, Max DD, Friction YTD hero cards; equity curve chart; regime badge (BULL/NEUTRAL/BEAR/EXIT) with per-position allocation %; fill confirmation status |
| **Positions** | Sortable table with P&L colouring; **Exp Ret** and **Signal** columns from today's forecast; % to stop-loss (red if < 3%); frozen-portfolio banner |
| **Trade Log** | Append-only audit trail; cancelled rows shown with strikethrough; `↩ cancels {ref_id}` for CANCEL entries |
| **Forecasts** | **Δ Prev column** (▲▼ change vs previous pipeline run); **📅 data date badge**; confidence badges (green/yellow/red); Forecast History sub-tab with accuracy % |
| **Trade Ticket** | Today's recommendations; **Export CSV** button; **Enter Fills** button (modal to record actual broker fills without leaving the dashboard); T+2 warning when exits + buys co-exist |

## Daily Routine

1. **Morning (7:00-8:30 BKK):** Open Colab → "Run All"
2. After pipeline completes, open the web app to review today's Trade Ticket
3. Click **Export CSV** → place orders at your broker
4. After orders fill: click **Enter Fills** in the Trade Ticket tab → enter actual prices in the modal → Save Fills
   - Alternatively: open the Trade Ticket sheet → columns H-J → enter `filled_price`, `filled_shares`, `fill_timestamp`
5. Next pipeline run picks up fills automatically

## CANCEL Convention

To correct a wrong entry: append a row to Trade Log with `action=CANCEL` and `ref_id=<original_trade_id>`. Also manually correct the Portfolio sheet cash/positions.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Cell 8 crashes with CUDA error | CPU runtime | Runtime > Change runtime type > T4 GPU |
| Cell 1 shows wrong folder contents | KTH_REPO path wrong | Check `/content/drive/MyDrive/` listing |
| Cell 3 error: spreadsheet not found | Wrong spreadsheet ID | Re-copy ID from spreadsheet URL |
| Web app shows blank page | doGet() missing from Code.gs | Re-paste Code.gs, redeploy new version |
| Web app shows old data after code change | Old deployment version | Deploy > Manage deployments > New version |
| Export CSV download doesn't work on iPhone | iOS Safari Blob issue | Already handled with `data:` URI in `exportCsv()` |
| `gspread.exceptions.APIError: 429` | Too many API calls | Sleep 1s between writes in Cell 13 |

## Live Data

The dashboard is already configured to load live data from Sheets. No changes needed. After the first successful pipeline run, refresh the web app and all tabs will populate with real data.
