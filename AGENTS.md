# AGENTS.md — Kronos-TH

> Notebook-first research repo. Only the data layer is built; everything else is planned.
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
- **Current state:** Layers 1–2 (data) are ✅. Layers 3–5 (model, backtest, report) are ⬜ planned but empty.

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
- **Calendar fix:** `bdate_range` replaced with `date_range(D/B)` — crypto gets 7-day calendar
- **Metrics:** `hit_rate` renamed to `trade_win_rate` (trade P&L, not forecast direction accuracy)

### HF Manager Review fixes (2026-05-21)
6 issues identified, 5 of 6 fixed. Only remaining: FT backtests (us_equity + crypto) — specs approved, pending GPU sessions.

## What not to build yet

## What not to build yet
- Do not add a web UI, live trading, or intraday data — all explicitly out of scope per `PROJECT_STRUCTURE.md` §12.
- Do not add `pytest`, `tox`, or CI config unless explicitly asked.
- `Makefile` and `docker-compose.yml` already exist for Docker workflows — do not remove them.

## Reading order for context
1. `PROJECT_STRUCTURE.md` — authoritative design doc, module specs, open questions
2. `README.md` — project overview, caveats, quick start
3. `docs/superpowers/specs/` — approved design specs for all layers
4. `docs/superpowers/plans/` — implementation plans (specs → bite-sized tasks)
5. `docs/superpowers/specs/2026-05-16-local-testing-design.md` — local testing pipeline (CPU + GPU)
6. `kth/data/loader.py` — actual implementation of schema conversion and caching
7. `kth/data/universe.py` — universe + friction definitions
8. `kth/models/kronos_wrapper.py` — KronosTH wrapper (adapted to real Kronos API)
9. `kth/models/_kronos_bridge.py` — import bridge for non-pip-installable Kronos repo

