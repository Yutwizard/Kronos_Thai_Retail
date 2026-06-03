# AGENTS.md — Kronos-TH

> All 5 layers + 15-item QFM enhancement plan ✅ complete. Pending: 2023 n=50 backtest (~12 hrs GPU).
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
- **Current state:** All 5 layers ✅ built. Layer 5 is a local Flask dashboard (`scripts/dashboard.py`) for paper/live paper trading with a daily cron pipeline. 15-item QFM enhancement plan ✅ complete (2026-06-03). Pending: 2023 n=50 backtest (~12 hrs GPU).

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
  - Benchmark comparison: SET −5.29% (Sharpe −0.63), SPY +8.33% (0.44), equal-weight +1.44% (0.00)
  - Signal is genuine — model adds ~30pp alpha over equal-weight, beats all 4 benchmarks
  - Previous 14-ticker backtest conclusion (p=0.25) invalid — signal required diversification to compound

### Expanded backtest (2020-2024, Thai equity)
- **Full period:** CAGR +35.16%, Sharpe 1.29, Max DD −37.90%, Alpha vs EW +23.32%, p=0.174
- **COVID crash (Mitigate):** −1.62% CAGR vs SET −27.43% — model protected capital (+21.63pp alpha)
- **Recovery (Thrive):** +65.96% CAGR (+29.73pp alpha) — model captured rebound aggressively
- **Rate hikes (Thrive):** +27.94% CAGR (+20.29pp alpha) — consistent with 3-year run
- Caveat: full-period p not significant (0.174) due to crash noise; n_samples=10 vs 50 in 3-year run

### Yearly n=50 backtests (clean OOS, 2023-2026)
- **2024 n=50:** +43.78%, Sharpe 2.27, Max DD −6.92%, p=0.015 (significant)
- **2025 n=50:** +34.92%, Sharpe 1.03, Max DD −24.00%, p=0.257
- **2026 n=50:** +45.28%, Sharpe 2.42, Max DD −18.26%, p=0.353 (107 days, short period)
- **2023 n=50:** pending (252 days, ~12 hrs)
- n=10→n=50 upgrade improved 2025 by +12.4pp return, Sharpe +0.24 (n=10 forecasts were noisy)
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

## What not to build yet
- Do not add live order execution, broker API integration, or intraday data — all explicitly out of scope per `PROJECT_STRUCTURE.md` §12. The local dashboard is for paper trading + broker-ready CSV exports only.
- Do not add `pytest`, `tox`, or CI config unless explicitly asked.
- `Makefile` and `docker-compose.yml` already exist for Docker workflows — do not remove them.

## Reading order for context
1. `PROJECT_STRUCTURE.md` — authoritative design doc, module specs, open questions
2. `CONTEXT.md` — domain language glossary (14 terms, example dialogue)
3. `README.md` — project overview, caveats, quick start
4. `docs/getting-started.md` — **start here if new** — installation, paper trading, first-week walkthrough
5. `docs/dashboard-user-manual.md` — step-by-step dashboard operating guide
6. `docs/operations-manual.md` — decision rules reference (original notebook workflow)
7. `docs/user-manual.md` — full methodology, backtest results, and usage instructions
8. `docs/monthly-walkthrough.html` — 21-day simulated month with real trades and portfolio outcomes
9. `docs/superpowers/specs/` — approved design specs for all layers (6 active, 5 archived)
10. `docs/superpowers/plans/` — implementation plans (3 active, 14 archived). Active: expanded backtest, OOS yearly, n50 completion
11. `docs/superpowers/archive/` — completed/superseded plans (incl. all 4 QFM phase plans)
12. `docs/superpowers/specs/2026-06-02-real-market-dashboard-design.md` — real-market dashboard design spec
13. `kth/data/loader.py` — schema conversion and caching implementation
14. `kth/data/universe.py` — universe, friction, and sector definitions
15. `kth/models/kronos_wrapper.py` — KronosTH wrapper (adapted to real Kronos API)
16. `kth/models/_kronos_bridge.py` — import bridge for non-pip-installable Kronos repo
14. `kth/data/loader.py` — actual implementation of schema conversion and caching
15. `kth/data/universe.py` — universe + friction definitions
16. `kth/models/kronos_wrapper.py` — KronosTH wrapper (adapted to real Kronos API)
17. `kth/models/_kronos_bridge.py` — import bridge for non-pip-installable Kronos repo

