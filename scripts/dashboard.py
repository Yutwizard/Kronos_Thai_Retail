#!/usr/bin/env python3
"""Kronos-TH Dashboard — Flask server for paper/live trading dashboard."""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from datetime import date, datetime

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
                errors.append(
                    f"{pfx}: fill_price {fill_price} deviates {deviation:.0%} from cached close "
                    f"{cached} — exceeds 20% sanity limit"
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
    return send_from_directory("scripts/static", "dashboard.html")


# ---- REST API ----

@app.route("/api/forecasts")
def api_forecasts():
    from kth.trading.trade_gen import get_all_ranked
    forecasts = get_all_ranked()
    return jsonify({"date": str(date.today()), "count": len(forecasts), "forecasts": forecasts})


@app.route("/api/positions")
def api_positions():
    from kth.trading.portfolio import get_positions
    return jsonify(get_positions(TRADING_MODE))


@app.route("/api/risk")
def api_risk():
    from kth.trading.portfolio import compute_metrics
    metrics = compute_metrics(TRADING_MODE)
    metrics["calibration"] = _get_calibration()
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
        log("STEP1_OK")
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
