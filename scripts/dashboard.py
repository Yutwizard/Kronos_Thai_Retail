#!/usr/bin/env python3
"""Kronos-TH Dashboard — Flask server for paper/live trading dashboard."""
from __future__ import annotations

import logging
import os
import sys
import subprocess
from pathlib import Path
from datetime import date, datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

from flask import Flask, jsonify, request, send_from_directory

# Ensure kth is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "kronos_repo"))

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "scripts/static"), static_url_path="/static")
TRADING_MODE = os.environ.get("KRONOS_MODE", "paper")  # "paper" or "live"
PORT = int(os.environ.get("KRONOS_PORT", "5555"))

_pipeline_proc: "subprocess.Popen | None" = None

_calibration_cache: dict = {"date": None, "result": None}
_forecast_cache: dict = {"date": None, "data": {}}
_compare_cache: dict = {"date": None, "data": {}}


def _get_cached_closes() -> dict[str, float]:
    """Return {ticker: close} from today's forecast cache. Used for fill_price validation."""
    today = str(date.today())
    if _forecast_cache["date"] == today:
        return _forecast_cache["data"]
    try:
        from kth.trading.trade_gen import load_forecasts
        rows = load_forecasts(today)
        closes = {r["ticker"]: r["close"] for r in rows}
    except Exception:
        closes = {}
    # Self-heal: skip tickers whose close is wildly different from the norm
    from kth.data.loader import load_cached
    for ticker in list(closes.keys()):
        close = closes[ticker]
        try:
            price_data = load_cached(ticker)
            prev = float(price_data["close"].iloc[-2]) if len(price_data) > 1 else close
            ratio = close / prev if prev else 1
            if ratio > 3 or ratio < 1/3:
                logger.warning(
                    f"Data quality: {ticker} close {close} vs prev {prev} "
                    f"(ratio {ratio:.2f}) — skipping price deviation check for this ticker"
                )
                del closes[ticker]
        except Exception:
            pass
    _forecast_cache["date"] = today
    _forecast_cache["data"] = closes
    return closes


def _validate_trade_request(trades: list[dict]) -> list[str]:
    """Return list of error strings. Empty = valid."""
    errors = []
    closes = _get_cached_closes()
    valid_actions = {"buy", "sell", "exit", "reduce"}
    for i, t in enumerate(trades):
        pfx = f"Trade {i + 1} ({t.get('ticker', '?')})"
        action = t.get("action", "")
        shares = t.get("shares")
        fill_price = t.get("fill_price")

        if action not in valid_actions:
            errors.append(f"{pfx}: invalid action '{action}' — must be one of {sorted(valid_actions)}")
        if not isinstance(shares, (int, float)) or shares <= 0:
            errors.append(f"{pfx}: shares must be positive, got {shares!r}")
        elif int(shares) % 100 != 0:
            errors.append(f"{pfx}: shares must be a multiple of 100 (SET board lot), got {int(shares)}")
        if not isinstance(fill_price, (int, float)) or fill_price <= 0:
            errors.append(f"{pfx}: fill_price must be positive, got {fill_price!r}")
        elif closes and t.get("ticker") in closes:
            cached = closes[t["ticker"]]
            deviation = abs(fill_price - cached) / cached if cached else 0
            if deviation > 0.20:
                logger.warning(
                    f"Price deviation: ticker={t.get('ticker')} "
                    f"fill_price={fill_price} cached_close={cached} "
                    f"deviation={deviation:.2%}"
                )
    return errors

def _get_calibration() -> dict:
    """Compute P5/P95 calibration once per day; return cached result otherwise."""
    today = str(date.today())
    if _calibration_cache["date"] == today:
        return _calibration_cache["result"]
    try:
        from kth.backtest.metrics import compute_calibration
        from kth.data.universe import UNIVERSE
        tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]
        result = compute_calibration(
            forecast_cache_dir=PROJECT_ROOT / "data/forecast_cache/NeoQuasar_Kronos-small",
            raw_data_dir=PROJECT_ROOT / "data/raw",
            tickers=tickers,
        )
    except Exception:
        result = {"coverage": None, "n_samples": 0, "status": "error"}
    _calibration_cache["date"] = today
    _calibration_cache["result"] = result
    return result


@app.route("/")
def index():
    return send_from_directory(str(PROJECT_ROOT / "scripts/static"), "dashboard.html")


# ---- REST API ----

@app.route("/api/forecasts")
def api_forecasts():
    from kth.trading.trade_gen import get_all_ranked
    forecasts = get_all_ranked()
    return jsonify({"date": str(date.today()), "count": len(forecasts), "forecasts": forecasts})


def _cache_dates() -> list[str]:
    from pathlib import Path as _P
    cache_root = _P("data/forecast_cache/NeoQuasar_Kronos-small")
    if not cache_root.exists():
        return []
    return sorted(
        [d.name for d in cache_root.iterdir()
         if d.is_dir() and len(list(d.glob("*.parquet"))) > 0],
        reverse=True
    )


@app.route("/api/forecasts/dates")
def api_forecasts_dates():
    """Return all available forecast run dates (newest first)."""
    dates = _cache_dates()
    return jsonify({"dates": dates, "latest": dates[0] if dates else None})


@app.route("/api/forecasts/history/<run_date>")
def api_forecasts_history(run_date):
    """Return forecasts for a specific past run date, enriched with delta vs the date before it."""
    from kth.trading.trade_gen import load_forecasts
    dates = _cache_dates()
    if run_date not in dates:
        return jsonify({"error": f"No forecast cache for {run_date}"}), 404

    idx = dates.index(run_date)
    prev_date = dates[idx + 1] if idx + 1 < len(dates) else None

    target_fc = {f["ticker"]: f for f in load_forecasts(run_date)}
    prev_fc   = {f["ticker"]: f for f in load_forecasts(prev_date)} if prev_date else {}

    # data_date: latest close date used
    data_date = None
    try:
        from kth.data.loader import load_cached
        sample = next(iter(target_fc.keys()), None)
        if sample:
            df = load_cached(sample)
            # Use the parquet mtime as proxy — look for the close before run_date
            import pandas as pd
            ts = pd.to_datetime(run_date)
            hist = df[df["timestamps"] <= ts]
            data_date = str(hist["timestamps"].iloc[-1].date()) if not hist.empty else None
    except Exception:
        pass

    result = []
    for tkr, f in target_fc.items():
        p = prev_fc.get(tkr, {})
        delta_exp  = round(f["exp_ret"] - p.get("exp_ret", f["exp_ret"]), 4) if p else None
        flag_change = (p.get("confidence") != f["confidence"]) if p else False
        result.append({**f, "delta_exp_ret": delta_exp,
                        "prev_confidence": p.get("confidence"), "flag_changed": flag_change})
    result.sort(key=lambda x: x["rank_score"], reverse=True)
    return jsonify({"today": run_date, "prev": prev_date, "data_date": data_date,
                    "count": len(result), "forecasts": result})


@app.route("/api/forecasts/compare")
def api_forecasts_compare():
    """Return today's forecasts enriched with delta vs the previous available forecast date."""
    from kth.trading.trade_gen import load_forecasts
    dates = _cache_dates()
    today_date = dates[0] if dates else str(date.today())
    prev_date  = dates[1] if len(dates) > 1 else None

    today_fc = {f["ticker"]: f for f in load_forecasts(today_date)}
    prev_fc  = {f["ticker"]: f for f in load_forecasts(prev_date)} if prev_date else {}

    result = []
    for tkr, f in today_fc.items():
        p = prev_fc.get(tkr, {})
        delta_exp  = round(f["exp_ret"] - p.get("exp_ret", f["exp_ret"]), 4) if p else None
        flag_change = (p.get("confidence") != f["confidence"]) if p else False
        result.append({**f, "delta_exp_ret": delta_exp,
                        "prev_confidence": p.get("confidence"), "flag_changed": flag_change})
    result.sort(key=lambda x: x["rank_score"], reverse=True)

    # Find the actual close data date (last row of any raw parquet)
    data_date = None
    try:
        from kth.data.loader import load_cached
        sample = next(iter(today_fc.keys()), None)
        if sample:
            df = load_cached(sample)
            data_date = str(df["timestamps"].iloc[-1].date())
    except Exception:
        pass

    return jsonify({"today": today_date, "prev": prev_date,
                    "data_date": data_date,
                    "count": len(result), "forecasts": result})


@app.route("/api/positions")
def api_positions():
    from kth.trading.portfolio import get_positions
    return jsonify(get_positions(TRADING_MODE))


@app.route("/api/risk")
def api_risk():
    from kth.trading.portfolio import compute_metrics
    metrics = compute_metrics(TRADING_MODE)
    metrics["calibration"] = _get_calibration()
    bootstrap_pvalue = metrics.get("bootstrap_pvalue", {})
    metrics["p_value_labels"] = {
        "live_bootstrap": {
            "value": bootstrap_pvalue.get("pvalue"),
            "label": "Live paper trading (centered bootstrap, accumulating)",
            "status": bootstrap_pvalue.get("significant"),
            "n_obs": bootstrap_pvalue.get("n_obs"),
            "interpretation": (
                "Needs >=20 days. Grows as paper trading history accumulates. "
                "p<0.05 = edge confirmed; p>=0.15 = no confirmed edge."
            ),
        },
        "historical_ttest": {
            "label": "Historical backtest (t-test, frozen in data/backtest_results/)",
            "interpretation": (
                "Stored p-values from the 2023-2026 n50 backtests. "
                "Never recalculated by the dashboard. See MANIFEST.md for which runs are authoritative."
            ),
            "caveat": "Stored numbers are STALE pending 2026-06-21 bug-fix GPU re-run.",
        },
    }
    return jsonify(metrics)


@app.route("/api/trades", methods=["GET", "POST"])
def api_trades():
    if request.method == "GET":
        from kth.trading.trade_gen import load_trade_ticket
        return jsonify(load_trade_ticket())
    elif request.method == "POST":
        from kth.trading.portfolio import execute_trade
        data = request.get_json(force=True)
        if not data or "trades" not in data:
            return jsonify({"error": "Missing trades array", "recorded": 0}), 400
        trades = data.get("trades", [])
        errors = _validate_trade_request(trades)
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400
        results = []
        for t in trades:
            r = execute_trade(
                ticker=t["ticker"],
                action=t["action"],
                shares=int(t["shares"]),
                fill_price=float(t["fill_price"]),
                mode=data.get("mode", TRADING_MODE),
                order_type=t.get("order_type", "market"),
                rationale=t.get("rationale", ""),
            )
            results.append(r)
        total_recorded = sum(r.get("recorded", 0) for r in results)
        return jsonify({"recorded": total_recorded, "results": results})


@app.route("/api/health")
def api_health():
    today_str = str(date.today())
    log_path = Path(f"data/logs/cron_{today_str}.log")
    steps = {"download": "unknown", "forecast": "unknown", "trade_gen": "unknown"}
    stale = True
    last_forecast = None

    if log_path.exists():
        content = log_path.read_text()
        if "PIPELINE_OK" in content:
            steps = {"download": "ok", "forecast": "ok", "trade_gen": "ok"}
            stale = False
        else:
            if "STEP1_FAILED" in content:
                steps["download"] = "failed"
            elif "download_data.py" in content:
                steps["download"] = "ok"
            if "STEP2_FAILED" in content:
                steps["forecast"] = "failed"
            elif "forecast" in content.lower():
                steps["forecast"] = "ok"

    # Check for forecast cache
    cache_dir = Path(f"data/forecast_cache/NeoQuasar_Kronos-small/{today_str}")
    if cache_dir.exists():
        last_forecast = today_str
        steps["forecast"] = steps.get("forecast", "ok")
    else:
        # Find latest cached date
        parent = Path("data/forecast_cache/NeoQuasar_Kronos-small")
        if parent.exists():
            dates = sorted([d.name for d in parent.iterdir() if d.is_dir()], reverse=True)
            if dates:
                last_forecast = dates[0]
                stale = dates[0] != today_str

    sanity_failures = []
    sanity_log = Path(f"data/logs/sanity_{today_str}.json")
    if sanity_log.exists():
        try:
            import json as _json
            sanity_failures = _json.loads(sanity_log.read_text()).get("failures", [])
        except Exception:
            pass

    return jsonify({
        "last_forecast_date": last_forecast,
        "steps": steps,
        "stale": stale,
        "pipeline_log": str(log_path) if log_path.exists() else None,
        "sanity_failures": sanity_failures,
    })


@app.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    """Spawn the morning pipeline (download + forecast + trade ticket) in background."""
    global _pipeline_proc
    if _pipeline_proc and _pipeline_proc.poll() is None:
        return jsonify({"status": "running", "message": "Pipeline already running", "pid": _pipeline_proc.pid}), 409
    log_path = PROJECT_ROOT / f"data/logs/cron_{date.today()}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "w")
    _pipeline_proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "scripts/dashboard.py"), "--generate"],
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=log_f,
    )
    return jsonify({"status": "started", "pid": _pipeline_proc.pid})


@app.route("/api/pipeline/status")
def api_pipeline_status():
    """Return current pipeline run state and per-step progress from the log."""
    global _pipeline_proc
    running = bool(_pipeline_proc and _pipeline_proc.poll() is None)
    return_code = _pipeline_proc.poll() if _pipeline_proc else None
    log_path = PROJECT_ROOT / f"data/logs/cron_{date.today()}.log"
    steps = {"download": "pending", "forecast": "pending", "trade_gen": "pending"}
    stage = "running" if running else "idle"

    if log_path.exists():
        content = log_path.read_text()
        if "PIPELINE_OK" in content:
            steps = {"download": "ok", "forecast": "ok", "trade_gen": "ok"}
            stage = "complete"
        elif "STEP2_FAILED" in content:
            steps["download"] = "ok"
            steps["forecast"] = "failed"
            stage = "failed"
        elif "STEP1_FAILED" in content:
            steps["download"] = "failed"
            stage = "failed"
        elif "STEP3" in content:
            steps["download"] = "ok"
            steps["forecast"] = "ok"
            steps["trade_gen"] = "running"
        elif "STEP2_OK" in content:
            steps["download"] = "ok"
            steps["forecast"] = "ok"
            steps["trade_gen"] = "pending"
        elif "STEP2" in content:
            steps["download"] = "ok"
            steps["forecast"] = "running"
        elif "STEP1_OK" in content:
            steps["download"] = "ok"
            steps["forecast"] = "pending"
        elif "STEP1" in content:
            steps["download"] = "running"

    return jsonify({
        "running": running,
        "stage": stage,
        "steps": steps,
        "return_code": return_code,
        "pid": _pipeline_proc.pid if _pipeline_proc else None,
    })


@app.route("/api/portfolio/init", methods=["POST"])
def api_portfolio_init():
    data = request.get_json(force=True) or {}
    try:
        capital = float(data.get("capital", 500000))
    except (TypeError, ValueError):
        return jsonify({"error": "capital must be a number"}), 400
    if not (1 <= capital <= 100_000_000):
        return jsonify({"error": "Capital must be between 1 and 100,000,000 THB"}), 400
    from kth.trading.portfolio import reset_portfolio
    pf = reset_portfolio(TRADING_MODE, capital)
    return jsonify({"status": "ok", "initial_capital": capital, "cash": pf["cash"]})


@app.route("/api/trades/history")
def api_trades_history():
    from kth.trading.portfolio import get_trade_log
    trades = get_trade_log(TRADING_MODE)
    return jsonify({"trades": [{"index": i, **t} for i, t in enumerate(trades)]})


@app.route("/api/trades/history/<int:index>", methods=["DELETE"])
def api_delete_trade(index):
    from kth.trading.portfolio import delete_trade
    result = delete_trade(index, TRADING_MODE)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/trades/history/<int:index>", methods=["PATCH"])
def api_edit_trade(index):
    data = request.get_json(force=True) or {}
    new_price = new_shares = new_date = None
    if "price" in data:
        try:
            new_price = float(data["price"])
            if new_price <= 0:
                return jsonify({"error": "price must be positive"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "price must be a number"}), 400
    if "shares" in data:
        try:
            new_shares = int(data["shares"])
        except (TypeError, ValueError):
            return jsonify({"error": "shares must be an integer"}), 400
    if "date" in data:
        new_date = str(data["date"]).strip()
        try:
            datetime.strptime(new_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    if new_price is None and new_shares is None and new_date is None:
        return jsonify({"error": "supply at least one of: price, shares, date"}), 400
    from kth.trading.portfolio import edit_trade
    result = edit_trade(index, new_price, new_shares, TRADING_MODE, new_date=new_date)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/performance")
def api_performance():
    from kth.trading.portfolio import get_equity_performance
    return jsonify(get_equity_performance(TRADING_MODE))


@app.route("/api/phase2_gate")
def api_phase2_gate():
    from kth.trading.portfolio import check_phase2_gate
    return jsonify(check_phase2_gate())


@app.route("/api/export_csv")
def api_export_csv():
    try:
        from kth.trading.portfolio import export_broker_csv
        path = export_broker_csv(TRADING_MODE)
        if path:
            return jsonify({"status": "ok", "path": str(path)})
        return jsonify({"status": "error", "message": "No trades to export"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---- CLI ----

def cmd_generate():
    """Run morning pipeline: download data → generate forecasts → trade ticket."""
    import shutil
    log_path = Path(f"data/logs/cron_{date.today()}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    os.environ["HF_HUB_OFFLINE"] = "1"

    # Step 1: Download data
    log("STEP1: download_data.py")
    try:
        result = subprocess.run(
            [sys.executable, "scripts/download_data.py"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            log(f"STEP1_FAILED: {result.stderr[:200]}")
            return 1
        # download_data.py can exit 0 while individual tickers silently failed
        # to download (yfinance quirks per exchange, rate limits, etc.) --
        # those tickers then vanish from the forecast run with only a vague
        # "insufficient history" message in Step 2, no visible cause. Surface
        # per-ticker failures/sanity flags here so STEP1_OK never hides them.
        warn_lines = [l for l in result.stdout.splitlines() if "FAILED" in l or "⚠" in l]
        for wl in warn_lines:
            log(f"STEP1_WARN: {wl.strip()}")
        log("STEP1_OK" + (f" ({len(warn_lines)} ticker warning(s), see above)" if warn_lines else ""))
    except Exception as e:
        log(f"STEP1_FAILED: {e}")
        return 1

    # Step 2: Generate forecasts
    log("STEP2: forecast generation")
    try:
        from kth.data.universe import UNIVERSE
        from kth.models.kronos_wrapper import KronosTH
        from kth.backtest.walkforward import precompute_forecasts

        tickers = [t for t, _, _ in UNIVERSE["thai_equity"]]
        try:
            from kth_dr.universe_dr import get_verified_dr_tickers, get_dr_underlying_tickers, DR_MAP, _ensure_loaded
            _ensure_loaded()
            dr_tickers = get_verified_dr_tickers()
            dr_underlyings = get_dr_underlying_tickers()
            dr_fx_tickers = list({DR_MAP[u].get("fx_ticker", "THB=X") for u in dr_underlyings if u in DR_MAP})
            tickers = tickers + dr_tickers + dr_underlyings + dr_fx_tickers
        except ImportError:
            pass
        except Exception as e:
            log(f"STEP2: DR ticker wiring skipped: {e}")
        today_str = str(date.today())
        slug = "NeoQuasar_Kronos-small"
        today_dir = Path(f"data/forecast_cache/{slug}/{today_str}")
        today_dir.mkdir(parents=True, exist_ok=True)

        def _already_done(ticker: str) -> bool:
            safe = ticker.replace("^", "_").replace("=", "_")
            p = today_dir / f"{safe}.parquet"
            if not p.exists():
                return False
            from datetime import datetime as _dt
            return _dt.fromtimestamp(p.stat().st_mtime).date() == date.today()

        # Skip tickers that failed price sanity check
        sanity_log = PROJECT_ROOT / f"data/logs/sanity_{today_str}.json"
        sanity_failures = set()
        if sanity_log.exists():
            import json as _json
            sanity_failures = set(_json.loads(sanity_log.read_text()).get("failures", []))
            if sanity_failures:
                log(f"STEP2: excluding {len(sanity_failures)} sanity-failed tickers: {sorted(sanity_failures)}")

        pending = [t for t in tickers if not _already_done(t) and t not in sanity_failures]
        skipped = len(tickers) - len(pending) - len(sanity_failures)
        if skipped:
            log(f"STEP2: {skipped} tickers already forecasted today, running {len(pending)} remaining")

        if pending:
            th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
            precompute_forecasts(th, pending, start_date=today_str, end_date=today_str,
                                 pred_len=20, n_samples=50, lookback=400)
        log("STEP2_OK")
    except Exception as e:
        log(f"STEP2_FAILED: {e}")
        return 1

    # Step 3: Generate trade ticket
    log("STEP3: trade ticket generation")
    try:
        from kth.trading.trade_gen import generate_trade_ticket
        ticket = generate_trade_ticket()
        log(f"STEP3_OK: {len(ticket.get('exits',[]))} exits, {len(ticket.get('buys',[]))} buys")
    except Exception as e:
        log(f"STEP3_FAILED: {e}")
        return 1

    log("PIPELINE_OK")
    return 0


def cmd_serve():
    """Start Flask dashboard server."""
    print(f"Kronos-TH Dashboard — {TRADING_MODE.upper()} mode")
    print(f"Open: http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        sys.exit(cmd_generate())
    elif len(sys.argv) > 1 and sys.argv[1] == "--serve":
        cmd_serve()
    else:
        print("Usage:")
        print("  dashboard.py --generate   # Run morning pipeline")
        print("  dashboard.py --serve      # Start web server")
        print(f"\nMode: {TRADING_MODE} (set KRONOS_MODE=live for Phase 2)")
        print(f"Port: {PORT} (set KRONOS_PORT to override)")
