#!/bin/bash
set -e

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ_DIR"

VENV_DIR="$PROJ_DIR/venv"
LOG_DIR="$PROJ_DIR/data/logs"
PORT="${KRONOS_PORT:-5555}"
PID_FILE="$PROJ_DIR/.dashboard.pid"
mkdir -p "$LOG_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
log()   { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }
fatal() { err "$1"; exit 1; }

usage() {
    cat <<EOF
Kronos-TH dashboard launcher

Usage:  $0 [command]
Commands:
  start    (default) set up venv, start dashboard (data + forecasts are
           generated on demand -- click "Run Pipeline" in the UI, or use
           the CLI: venv/bin/python scripts/dashboard.py --generate)
  stop             stop the running dashboard
  status           show dashboard status
  logs             tail the dashboard log (Ctrl+C to exit)
  restart          stop + start
  clean            remove venv and PID file (forces full re-setup on next start)

Environment:
  KRONOS_PORT      dashboard port (default 5555)
  INITIAL_CAPITAL  starting capital in THB (read by dashboard.py)
  KRONOS_MODE      paper or live (default paper)
  LINE_NOTIFY_TOKEN  optional, for cron failure alerts
EOF
}

require_python() {
    command -v python3 >/dev/null 2>&1 || fatal "python3 not found. Install: sudo apt install python3 python3-venv"
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    [ "$(echo "$PY_VERSION >= 3.10" | python3 -c 'import sys; print(sys.version_info >= (3,10))' 2>/dev/null)" = "True" ] || \
        fatal "Python 3.10+ required (have $PY_VERSION)"
    log "Python $PY_VERSION OK"
}

setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating venv at $VENV_DIR ..."
        python3 -m venv "$VENV_DIR"
        log "Installing data-layer dependencies (1-2 min) ..."
        "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        "$VENV_DIR/bin/pip" install --quiet -r requirements.txt
        log "Installing package in editable mode ..."
        "$VENV_DIR/bin/pip" install --quiet -e .
        log "Installing ML stack (torch + transformers, 3-5 min) ..."
        "$VENV_DIR/bin/pip" install --quiet -r requirements-ml.txt
        log "Venv ready"
    else
        log "Venv exists, reusing"
    fi
}

check_gpu() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        log "GPU: $GPU_NAME (${VRAM_MB}MB VRAM)"
        if [ "${VRAM_MB:-0}" -lt 6000 ]; then
            warn "VRAM < 6GB. Edit scripts/dashboard.py line ~513 to use n_samples=10 or 20"
        fi
    else
        warn "No NVIDIA GPU. Forecasts will be slow on CPU. Colab recommended for first run."
    fi
}

free_port() {
    if lsof -ti:$PORT >/dev/null 2>&1; then
        warn "Port $PORT in use, killing existing process"
        lsof -ti:$PORT | xargs -r kill -9 2>/dev/null || true
        sleep 2
    fi
}

start_dashboard() {
    require_python
    setup_venv
    check_gpu
    free_port
    log "Starting dashboard on http://localhost:$PORT ..."
    log "No data/forecasts generated yet -- click \"Run Pipeline\" in the UI, or run: $VENV_DIR/bin/python scripts/dashboard.py --generate"
    nohup "$VENV_DIR/bin/python" scripts/dashboard.py --serve > "$LOG_DIR/dashboard.log" 2>&1 &
    DASH_PID=$!
    echo "$DASH_PID" > "$PID_FILE"
    log "Waiting for dashboard to respond (up to 30s) ..."
    for _ in $(seq 1 30); do
        if curl -s --max-time 1 "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
            log "Dashboard ready"
            echo
            echo "  URL:   http://localhost:$PORT"
            echo "  PID:   $DASH_PID  (file: $PID_FILE)"
            echo "  Logs:  $LOG_DIR/dashboard.log"
            echo "  Stop:  $0 stop"
            return 0
        fi
        sleep 1
    done
    fatal "Dashboard did not respond within 30s. Check: tail $LOG_DIR/dashboard.log"
}

stop_dashboard() {
    if [ ! -f "$PID_FILE" ]; then
        warn "No PID file at $PID_FILE"
        free_port
        return
    fi
    local pid
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        log "Stopping dashboard (PID $pid) ..."
        kill "$pid" 2>/dev/null || true
        sleep 2
        kill -9 "$pid" 2>/dev/null || true
    else
        warn "PID $pid not running"
    fi
    rm -f "$PID_FILE"
    free_port
}

status_dashboard() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        local pid
        pid=$(cat "$PID_FILE")
        log "Dashboard running (PID $pid, port $PORT)"
        curl -s --max-time 2 "http://localhost:$PORT/api/health" | head -c 400
        echo
    else
        warn "Dashboard not running"
        return 1
    fi
}

clean_state() {
    warn "Removing venv and PID file"
    rm -rf "$VENV_DIR" "$PID_FILE"
    log "Clean complete. Next start will re-install dependencies."
}

case "${1:-start}" in
    start)    start_dashboard ;;
    stop)     stop_dashboard ;;
    status)   status_dashboard ;;
    logs)     tail -f "$LOG_DIR/dashboard.log" ;;
    restart)  stop_dashboard; start_dashboard ;;
    clean)    clean_state ;;
    -h|--help|help) usage ;;
    *)        usage; exit 1 ;;
esac
