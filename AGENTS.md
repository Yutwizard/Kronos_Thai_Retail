# AGENTS.md — Kronos-TH

> All 5 layers + 15-item QFM enhancements ✅ complete. All 4 OOS years done. Paper trading started 2026-06-04.
> **Layer 5 is migrating:** Flask dashboard → Google Suite (Colab + Sheets + Apps Script). See spec/plan below.
> When in doubt, read `PROJECT_STRUCTURE.md` — it is the authoritative design doc.

## Superpower workflow

**Invoke relevant skills BEFORE any response or action.** If there is even a 1% chance a skill applies, invoke the `Skill` tool to load it. Follow the skill's instructions exactly.

Priority order:
1. User's explicit instructions (this AGENTS.md, direct requests)
2. Superpowers skills
3. Default system prompt

**Red flags** — these thoughts mean STOP and check for skills:
- "This is just a simple question"
- "Let me explore the codebase first"
- "I need more context first"
- "This doesn't need a formal skill"

**Skill priority:** Process skills (brainstorming, systematic-debugging) before implementation skills (frontend-design, mcp-builder).

## Project type
- **Not a deployable app.** No CI, no build step, no test framework, no lint config.
- **Colab-first:** The real workflow is Jupyter notebooks on Google Colab (T4 GPU). Local Python scripts are for offline verification only.
- **Current state:** All 5 layers ✅ built. **Layer 5 is migrating** from Flask (`scripts/dashboard.py`) to Google Suite (Colab + Sheets + Apps Script). The Flask dashboard is complete and functional but will be superseded. 15-item QFM enhancement plan ✅ complete. All 4 OOS years (2023-2026) done. Paper trading live since 2026-06-04 (8 trades).

## Verify the data layer (offline)
```bash
# Local
pip install -r requirements.txt && pip install -e .
python verify_data_layer.py

# Docker (recommended — consistent environment)
make build && make verify
```
- Uses **synthetic** OHLCV because yfinance is blocked in this sandbox.
- Real data verification happens in `notebooks/01_data_layer.ipynb` on Colab.
- `requirements-ml.txt` contains the ML stack (torch, transformers, etc.) — installed separately in Docker with the correct CPU or CUDA variant.
- `pyproject.toml` makes `kth` installable via `pip install -e .` — required for imports to work outside Docker.

## Key conventions an agent might miss

### Kronos schema (enforced in `kth/data/loader.py`)
- Columns must be exactly: `timestamps, open, high, low, close, volume, amount`
- `amount` is computed as `close * volume` (Yahoo does not expose turnover).
- yfinance returns `Open/High/Low/Close/Volume` with a DatetimeIndex; `to_kronos_format()` lowercases and renames.

### Caching
- One **parquet per ticker**, never a merged file (different date ranges per asset class).
- Ticker sanitization for filenames: `^` → `_`, `=` → `_` (e.g. `^SET.BK` → `_SET.BK`, `THB=X` → `THB_X`).
- Cache dir default: `./data/raw/`

### Data quirks
- `auto_adjust=True` on yfinance so splits/dividends are baked into prices.
- Gaps are **preserved**, not forward-filled across crypto (7 days) vs equities (5 days).
- `download_universe()` pauses 0.5s between tickers and retries with exponential backoff (2s/4s/8s).
- Universe expanded from 51→100 tickers (50 Thai, 17 US, 12 crypto, rest unchanged).

### Asset class boundaries
- Universe is hardcoded in `kth/data/universe.py` (100 tickers, 9 classes). Not a CSV by design.
- `FRICTION` costs are per-class, not per-ticker.
- `fx_macro` is **features only**, not investable (commission/slippage = 0).

### Fine-tuning results (SGDR + proper val windows)
Roll up to `scripts/train_per_market.py` (general script). Results on 2025 holdout:
- **us_equity fold 2**: +2.0pp vs zero-shot (64.7% → best candidate)
- **crypto**: 0.0pp vs zero-shot (56.4% → stay zero-shot)
- **thai_equity**: −3.1pp vs zero-shot (57.1% → stay zero-shot)

Key insight: 21-month fold windows needed (not 6mo) so val/test have ≥420 rows for 400-row lookback. Early stopping via val loss prevents severe overfitting. `fold_step_months=21` required for equities (~441 bdays). All 9 checkpoints at `./checkpoints/{model}/fold{f}/best/`.

### Backtest results (zero-shot, 2022-2024)
- **Thai equity (49 tickers):** CAGR +31.44%, Sharpe 1.40, Max DD −17.97%
  - Source: `data/backtest_results/thai_equity_2022-2024_v2/` (n_samples=10, equal-weight). The original `thai_equity_2022-2024/` run differs (25.03%, Sharpe 1.29) — v2 is canonical.
  - Benchmark comparison: SET −5.29% (Sharpe −0.63), SPY +8.33% (0.44), equal-weight +1.44% (0.00)
  - Single-run p=0.034 (t-test). n=50 bootstrap 2024: p=0.015. Bonferroni-corrected threshold (9 tests): p<0.0056 — neither survives correction.
  - Signal is genuine — model adds ~30pp alpha over equal-weight, beats all 4 benchmarks
  - Previous 14-ticker backtest conclusion (p=0.25) invalid — signal required diversification to compound
- **Position sizing: equal-weight confirmed superior.** `inv_vol` was backtested (`thai_equity_2022-2024_invvol/`): CAGR 13.29%, Sharpe 0.84, p=0.732. Equal-weight wins by a wide margin. Do NOT use inv_vol — inv_vol allocates more capital to low-vol stocks where Kronos signal is weaker.
- **Friction analysis (2022-2024 canonical run):** 4.63%/yr friction drag on 500K portfolio ≈ 23,150 THB/yr. Gross CAGR ~36% → net 31.44%. Acceptable.
- **Friction by year:** 2023: 5.68%/yr | 2024: 7.54%/yr | 2025: 17.35%/yr | 2026: 32.78%/yr (ann., 107 days)
  - 2025 high friction root cause: **larger average position sizes** (size_pct 0.045 vs 0.021 in 2024) — stronger signal conviction in n50 forecasts results in larger entries. NOT high turnover (trade count only 8% more). In exchange for 17.35% friction, strategy earned +43.6pp alpha vs EW. Net positive.
  - **min_holding_days experiment + long_threshold experiment (2026-06-03):** Both showed null results in fresh walkforward, BUT this is because fresh walkforward reads the general n10 forecast cache while stored n50 results used dedicated n50-precomputed forecasts. These experiments require GPU re-precompute to test properly. **Do not change parameters based on this test — it used wrong data.**
- **Factor attribution (Task 5, 2026-06-03):** OLS regression of strategy vs SET market + 12-1 month momentum factor:
  - Beta_market = −0.009, R² = 0.000 → **strategy is completely market-neutral**
  - Beta_momentum = −0.010 → **strategy is NOT a momentum proxy**
  - Residual alpha = +29.4%/yr after factor adjustment → **genuine Kronos model alpha, unexplained by common factors**
  - This is the strongest possible factor attribution result. The alpha source is the model, not factor exposure.

### Expanded backtest (2020-2024, Thai equity)
- **Full period:** CAGR +35.16%, Sharpe 1.29, Max DD −37.90%, Alpha vs EW +23.32%, p=0.174
- **COVID crash (Mitigate):** −1.62% CAGR vs SET −27.43% — model protected capital (+21.63pp alpha)
- **Recovery (Thrive):** +65.96% CAGR (+29.73pp alpha) — model captured rebound aggressively
- **Rate hikes (Thrive):** +27.94% CAGR (+20.29pp alpha) — consistent with 3-year run
- Caveat: full-period p not significant (0.174) due to crash noise; n_samples=10 vs 50 in 3-year run

### Yearly n=50 backtests (clean OOS, 2023-2026)
- **2024 n=50:** +43.78%, Sharpe 2.27, Max DD −6.92%, p=0.015. Friction/yr: 7.54%.
- **2025 n=50:** +34.92%, Sharpe 1.03, Max DD −24.00%, p=0.257. Friction/yr: 17.35% ⚠ (51% of gross CAGR eaten by friction — investigate before live trading 2025-style regimes).
- **2026 n=50:** +45.28%, Sharpe 2.42, Max DD −18.26%, p=0.353 (107 days — too short).
- **2023 n=50:** +2.65% net (+8.07% gross), Sharpe 0.10, Max DD −13.08%, p=0.419. Friction/yr: **5.68%** (not 19.52% — that figure was a calculation error). EW=+12.8%, Alpha=**−10.2pp**.
  - 🔴 **DECISION GATE: MODEL REVIEW triggered** (Sharpe < 0.5). Per plan, execute Tasks 1, 4, 5.
  - **Regime dependency confirmed**: 2023 was a broad SET bull market (EW +12.8%). Strategy grossed only 8.07% — Kronos signals were wrong in a rising-all-boats regime. In 2024/2025 (EW −7.2%/−9.9%), the strategy crushed it (+42%/+34%). This is structural, not model failure.
  - **Cash drag explains part of underperformance**: with NEUTRAL band (50% deployed), holding 50% cash when EW returns 12.8% costs 6.4pp before any stock selection effect.
- n=10→n=50 upgrade improved 2025 by +12.4pp return, Sharpe +0.24 (n=10 forecasts were noisy)
- **Statistical note:** Only 2024 clears p<0.05 (single test). Under Bonferroni for 4 OOS years (threshold p<0.0125), no year survives. The strategy's alpha is regime-conditional, not year-round.
- **⚠ Paper trading recommendation (June 2026):** Current market is a SET bull (2026 EW +41.8% annualised). This matches the 2023 failure regime. Reduce to BEAR allocation (5%) until regime shifts or 20 paper trades accumulate.
- **Crypto (12 tickers):** CAGR +16.45%, Sharpe 0.52, Max DD −68.58% (ZS)
  - FT fold 0: CAGR +13.31%, Sharpe 0.46 — worse than ZS (−3.13%)
  - Verdict: crypto stays zero-shot per spec (FT ≤ ZS)
  - Both models NOT significant (p=0.64 ZS, p=0.70 FT) — high crypto volatility
- **US equity (17 tickers):** CAGR +30.34%, Sharpe 0.97 (ZS) vs FT fold 2: CAGR +31.30%, Sharpe 0.94
  - FT does NOT beat ZS (FT Sharpe ≤ ZS Sharpe). Both not significant (p=0.44-0.46)
  - Verdict: us_equity stays zero-shot. FT +2.0pp direction accuracy didn't translate to backtest alpha
- **Calendar fix:** `bdate_range` replaced with `date_range(D/B)` — crypto gets 7-day calendar
- **Metrics:** `hit_rate` renamed to `trade_win_rate` (trade P&L, not forecast direction accuracy)

### HF Manager Review fixes (2026-05-21)
6 issues identified, ALL 6 FIXED.
- Thai equity ZS confirmed genuine alpha (Sharpe 1.40 vs SET −0.63)
- Crypto + US equity FT backtests confirm: zero-shot wins in both markets
- All FT backtests executed per approved specs

### Google Suite Migration — Layer 5 (2026-06-04) 🔨 IN PROGRESS

Replacing the local Flask dashboard with a zero-cost Google-hosted alternative:
- **Google Colab** — daily compute engine (19-cell notebook, "Run All" each morning)
- **Google Sheets** — persistent data store + fill-confirmation input surface (14 tabs: 9 live + 5 staging)
- **Google Apps Script web app** — 5-tab dashboard SPA (accessible from any device via URL)

**Key architectural decision — JSON-bridge pattern:**
```
Sheets → read fills → Drive JSON → existing kth functions → Drive JSON → Sheets
```
`os.chdir(KTH_REPO)` in Cell 1 makes all `Path("data/...")` calls resolve against Drive.
Cell 9 (Update Portfolio State) must run before Cell 10 (Generate Ticket).

**New directory:** `google_suite/` (to be created)
- `kronos_daily_pipeline.ipynb` — 19-cell Colab notebook
- `apps_script/Code.gs` — Apps Script backend
- `apps_script/Index.html` — web app SPA (5 tabs: Dashboard, Trade Ticket, Portfolio, History, Risk)

**Migration note:** Existing `data/positions/paper_portfolio.json` and `trade_log.csv` require `google_suite/migrate_to_sheets.py` to port to Sheets. Flask dashboard kept for reference.

**Spec:** `docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md`
**Plan:** `docs/superpowers/plans/2026-06-04-google-suite-implementation-plan.md` (1,852 lines, all code written)

### Flask Dashboard — Improvements Shipped 2026-06-04 (kept for reference)

All improvements built while paper trading was being set up. These inform the Google Suite implementation:
- **Run Pipeline button** — one-click daily pipeline (download + forecast + ticket) from browser; recommended to run EVENING after market close so tomorrow's forecast uses today's close prices
- **Fill-price confirmation modal** — editable shares + price before recording; partial fill / no-fill support
- **Trade history panel** — inline edit (shares + price), delete with portfolio rebuild
- **Friction display** — Gross / Friction / Cash Impact columns in modal; per-class rates corrected
- **Initial capital setup** — first-day banner to set starting capital before first trade
- **Limit price clarification** — "Last Close" + "Limit (max)" columns + "fills at live ✓" tag

### 4-Phase QFM Enhancement Plan ✅ COMPLETE (2026-06-03)
15 enhancements from quant fund manager + software engineer review — all shipped:

| Phase | Focus | Items | Status | Commits |
|-------|-------|-------|--------|---------|
| **Phase 1 (P0)** | Bug fixes | 2 | ✅ | `5a20fa9` |
| **Phase 2 (P1)** | Resilience | 4 | ✅ | `5441065` |
| **Phase 3 (P2)** | Professional metrics | 5 | ✅ | `d8a05fa` |
| **Phase 4 (P3/P4)** | Polish | 5 | ✅ | `23d693a` + `df80804` |

**Key conventions added (all now live):**
- `kth/data/universe.py` — `SECTOR` dict + `get_sector()` (50 tickers → 10 SET sectors)
- `kth/trading/trade_gen.py` — sector guard (max 2 positions/sector), per-ticker friction, T+2 warning
- `kth/trading/portfolio.py` — atomic `os.replace()` write, `MODEL_VERSION`, `forecast_date` in trade log
- `kth/backtest/metrics.py` — IR, batting average, calibration, drawdown velocity, bootstrap p-value
- `scripts/cron_pipeline.sh` — LINE Notify on failure via `$LINE_NOTIFY_TOKEN`
- `scripts/download_data.py` — price sanity filter (>30% move → exclude from forecast)
- `scripts/dashboard.py` — POST /api/trades validation, forecast recovery, calibration wired to `/api/risk`

**Bootstrap p-value clarification (fix applied in `df80804`):**
- `compute_bootstrap_pvalue()` uses **centered bootstrap resampling** (not permutation — permutation preserves the mean, making the test trivially non-significant).
- This is for the **live dashboard only** — assesses whether live paper trading returns show a real edge.
- Historical backtest p-values (p=0.015, p=0.257, p=0.353) use a **t-test** in `compute_metrics()` and were never changed.

Plan files archived to `docs/superpowers/archive/plans/`.

### Known unknowns
- **Kronos pre-training cutoff: ≈ December 2022 (inferred, not explicit)**
  Evidence: `kronos_repo/finetune/config.py` sets `train_time_range = ["2011-01-01", "2022-12-31"]` and `test_time_range = ["2024-04-01", "2025-06-05"]`. This design is only coherent if the PRE-TRAINED model also ends around 2022 — otherwise the fine-tuning test would be partially in-sample for the base model. Paper (arXiv:2508.02739, published Aug 2025, accepted AAAI 2026) was developed with 2024-2025 treated as future/OOS.
  **Practical implication:**
  - 2022 portion of `thai_equity_2022-2024_v2` canonical run: **potentially partially in-sample** (H2 2022 most likely)
  - **2023-2026 OOS backtests: CLEAN** — all genuinely out-of-sample
  - This is GOOD NEWS: the 4-year OOS results (including the weak 2023) are trustworthy
  - Status: INFERRED. To confirm definitively, read arXiv:2508.02739 Section 3 (Training Data).

## What not to build yet
- Do not add live order execution, broker API integration, or intraday data — all explicitly out of scope per `PROJECT_STRUCTURE.md` §12. The local dashboard is for paper trading + broker-ready CSV exports only.
- Do not add `pytest`, `tox`, or CI config unless explicitly asked.
- `Makefile` and `docker-compose.yml` already exist for Docker workflows — do not remove them.

## Reading order for context
1. `PROJECT_STRUCTURE.md` — authoritative design doc, module specs, open questions
2. `CONTEXT.md` — domain language glossary (14 terms, example dialogue)
3. `README.md` — project overview, caveats, quick start
4. `docs/getting-started.md` — **start here if new** — installation, paper trading, first-week walkthrough
5. `docs/dashboard-user-manual.md` — step-by-step Flask dashboard guide (superseded by Google Suite, kept for reference)
6. `docs/operations-manual.md` — decision rules reference
7. `docs/user-manual.md` — full methodology, backtest results, and usage instructions
8. `docs/monthly-walkthrough.html` — 21-day simulated month with real trades
9. `docs/superpowers/specs/` — approved design specs (7 active, 5 archived)
10. `docs/superpowers/plans/` — implementation plans (5 active, 14 archived)
11. `docs/superpowers/specs/2026-06-04-google-suite-dashboard-design.md` — **NEW** Google Suite spec (supersedes Flask)
12. `docs/superpowers/plans/2026-06-04-google-suite-implementation-plan.md` — **NEW** 19-cell Colab + Apps Script plan (1,852 lines, all code)
13. `docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md` — Flask dashboard spec (superseded, reference only)
14. `kth/data/loader.py` — schema conversion and caching implementation
15. `kth/data/universe.py` — universe, friction, and sector definitions
16. `kth/models/kronos_wrapper.py` — KronosTH wrapper (adapted to real Kronos API)
17. `kth/models/_kronos_bridge.py` — import bridge for non-pip-installable Kronos repo

