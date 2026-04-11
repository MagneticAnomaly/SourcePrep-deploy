#!/bin/bash
# CoDRAG Troubleshooting Harness
# =================================
# Strict daemon-only environment for isolating runtime bugs.
# Unlike scripts/dev.sh, this:
#   - Starts ONLY the daemon (no dashboard, no storybook, no websites)
#   - No frontend polling storm
#   - Daemon log goes to a known file with timestamps
#   - Provides --status, --kill, --logs subcommands
#
# Usage:
#   scripts/troubleshoot.sh up        Start the daemon (kills first)
#   scripts/troubleshoot.sh down      Kill the daemon and clean up
#   scripts/troubleshoot.sh status    Show daemon state, ports, log path
#   scripts/troubleshoot.sh logs      Tail the daemon log (Ctrl-C to stop)
#   scripts/troubleshoot.sh restart   Equivalent to down + up
#   scripts/troubleshoot.sh dump      py-spy dump of the daemon's threads
#
# Why a separate script: scripts/dev.sh starts the full dashboard stack
# which polls the daemon endpoints aggressively. When investigating runtime
# bugs (F-11 thread pool exhaustion, F-35 swarm hang, AIMD recovery), the
# polling storm pollutes the daemon state and makes diagnosis harder. This
# harness gives a clean baseline.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DAEMON_PORT=8400
DAEMON_LOG="/tmp/codrag_troubleshoot.log"
DAEMON_PID_FILE="/tmp/codrag_troubleshoot.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# Kill anything on the daemon port + any codrag processes
kill_daemon() {
    local pid
    pid=$(lsof -ti :$DAEMON_PORT 2>/dev/null || true)
    if [ -n "$pid" ]; then
        log_warn "Port $DAEMON_PORT in use by PID $pid - killing..."
        kill -9 $pid 2>/dev/null || true
        sleep 0.5
    fi
    # Catch orphans not bound to the port
    pkill -9 -f "codrag.cli serve" 2>/dev/null || true
    pkill -9 -f "codrag serve"     2>/dev/null || true
    pkill -9 -f "codrag mcp"       2>/dev/null || true
    sleep 0.5
    rm -f "$DAEMON_PID_FILE"
    log_ok "Daemon killed"
}

start_daemon() {
    log_info "Starting CoDRAG daemon (troubleshooting mode)..."
    log_info "  Port: $DAEMON_PORT"
    log_info "  Log:  $DAEMON_LOG"
    log_info "  Mode: daemon ONLY — no dashboard, no storybook, no websites"
    : > "$DAEMON_LOG"

    PYTHONPATH="$PROJECT_ROOT/src" \
        "$PROJECT_ROOT/.venv/bin/python" -m codrag.cli serve --port $DAEMON_PORT \
        > "$DAEMON_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$DAEMON_PID_FILE"

    # Wait for /health to respond
    local i=0
    for i in $(seq 1 40); do
        if curl -s -m 1 "http://localhost:$DAEMON_PORT/health" >/dev/null 2>&1; then
            log_ok "Daemon ready (PID $pid) after ${i}/2s"
            return 0
        fi
        sleep 0.5
    done
    log_err "Daemon failed to come up in 20s"
    log_err "Last 20 log lines:"
    tail -20 "$DAEMON_LOG" 2>/dev/null || true
    return 1
}

show_status() {
    echo
    echo "═══ Troubleshooting Harness Status ═══"
    if [ -f "$DAEMON_PID_FILE" ]; then
        local pid=$(cat "$DAEMON_PID_FILE")
        if kill -0 $pid 2>/dev/null; then
            log_ok "Daemon: RUNNING (PID $pid)"
            ps -p $pid -o pid,etime,%cpu,%mem,state,command 2>/dev/null | tail -1
        else
            log_warn "Daemon: PID file exists but process is dead"
        fi
    else
        log_warn "Daemon: NO PID file (not started by this harness)"
    fi
    echo
    echo "Listening on port $DAEMON_PORT:"
    lsof -i :$DAEMON_PORT 2>/dev/null | head -5 || echo "  (nothing)"
    echo
    echo "Log file: $DAEMON_LOG"
    if [ -f "$DAEMON_LOG" ]; then
        echo "  Size: $(wc -c < "$DAEMON_LOG") bytes"
        echo "  Last modified: $(stat -f "%Sm" "$DAEMON_LOG")"
    fi
    echo
    echo "Established TCP connections to daemon:"
    local conn_count
    conn_count=$(lsof -i :$DAEMON_PORT 2>/dev/null | grep -c ESTABLISHED || true)
    echo "  $conn_count"
    echo
    # Quick health probe
    echo "Health probe:"
    local health
    health=$(curl -s -m 3 "http://localhost:$DAEMON_PORT/health" 2>&1 || echo "TIMEOUT")
    echo "  /health: $health"
    echo
}

case "${1:-}" in
    up|start)
        kill_daemon
        start_daemon
        show_status
        ;;
    down|stop|kill)
        kill_daemon
        ;;
    restart)
        kill_daemon
        start_daemon
        show_status
        ;;
    status)
        show_status
        ;;
    logs|tail)
        if [ ! -f "$DAEMON_LOG" ]; then
            log_err "No daemon log at $DAEMON_LOG"
            exit 1
        fi
        log_info "Tailing $DAEMON_LOG (Ctrl-C to stop)"
        tail -f "$DAEMON_LOG"
        ;;
    dump)
        if [ ! -f "$DAEMON_PID_FILE" ]; then
            log_err "No daemon PID file"
            exit 1
        fi
        local pid=$(cat "$DAEMON_PID_FILE")
        if ! kill -0 $pid 2>/dev/null; then
            log_err "Daemon process $pid is dead"
            exit 1
        fi
        log_info "py-spy dump of PID $pid:"
        if command -v sudo >/dev/null && [ -n "$TROUBLESHOOT_USE_SUDO" ]; then
            sudo "$PROJECT_ROOT/.venv/bin/py-spy" dump --pid $pid
        else
            "$PROJECT_ROOT/.venv/bin/py-spy" dump --pid $pid 2>&1 || \
                log_warn "py-spy needs sudo on macOS — re-run with TROUBLESHOOT_USE_SUDO=1"
        fi
        ;;
    *)
        cat <<EOF
CoDRAG Troubleshooting Harness

Usage: $0 <command>

Commands:
  up | start    Start the daemon (kills first)
  down | stop   Kill the daemon and clean up
  restart       Equivalent to down + up
  status        Show daemon state, ports, log info
  logs | tail   Tail the daemon log (Ctrl-C to stop)
  dump          py-spy dump of daemon threads (needs sudo on macOS)

Daemon port: $DAEMON_PORT
Log file:    $DAEMON_LOG
PID file:    $DAEMON_PID_FILE

Why this exists: scripts/dev.sh starts the full dashboard stack which
hammers the daemon with polling. This harness runs the daemon in
isolation so runtime bugs (thread pool, swarm hangs, AIMD recovery)
can be diagnosed without polling-storm noise.
EOF
        exit 0
        ;;
esac
