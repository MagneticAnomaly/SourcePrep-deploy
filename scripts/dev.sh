#!/bin/bash
# CoDRAG Development Server Launcher
# Launches all development services with automatic port cleanup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# F-81: Ensure the daemon watchdog and all dev-server children die when
# dev.sh exits (Ctrl-C, SIGTERM, normal exit). Without this the watchdog
# survives the script teardown and keeps respawning the daemon.
cleanup_all() {
    # Disable the trap so we don't recurse
    trap - EXIT INT TERM HUP
    # Tell watchdog to stop gracefully (so it doesn't re-spawn daemon)
    touch /tmp/codrag_daemon_stop 2>/dev/null || true
    pkill -f "daemon_watchdog.sh" 2>/dev/null || true
    # Kill all our direct children (dashboard, storybook, websites)
    pkill -P $$ 2>/dev/null || true
}
trap cleanup_all EXIT INT TERM HUP

# Port definitions
DAEMON_PORT=8400
DASHBOARD_PORT=5174
STORYBOOK_PORT=6006
MARKETING_PORT=3000
DOCS_PORT=3001
SUPPORT_PORT=3002
PAYMENTS_PORT=3003

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Kill process on a specific port if it exists
kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        log_warn "Port $port in use by PID $pid - killing..."
        kill -9 $pid 2>/dev/null || true
        sleep 0.5
        log_success "Port $port freed"
    fi
}

# Check if nvm is available and load it
load_nvm() {
    export NVM_DIR="$HOME/.nvm"
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        source "$NVM_DIR/nvm.sh"
        return 0
    elif [ -s "/usr/local/opt/nvm/nvm.sh" ]; then
        source "/usr/local/opt/nvm/nvm.sh"
        return 0
    else
        log_error "nvm not found. Please install nvm or ensure Node 20+ is available."
        return 1
    fi
}

# Cleanup function for graceful shutdown
cleanup() {
    log_info "Shutting down all services..."
    kill_port $DAEMON_PORT
    kill_port $DASHBOARD_PORT
    kill_port $STORYBOOK_PORT
    kill_port $MARKETING_PORT
    kill_port $DOCS_PORT
    kill_port $SUPPORT_PORT
    kill_port $PAYMENTS_PORT
    log_success "All services stopped"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Main
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              CoDRAG Development Environment                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    cd "$PROJECT_ROOT"

    # Kill any existing processes on our ports
    log_info "Cleaning up ports..."
    kill_port $DAEMON_PORT
    kill_port $DASHBOARD_PORT
    kill_port $STORYBOOK_PORT
    kill_port $MARKETING_PORT
    kill_port $DOCS_PORT
    kill_port $SUPPORT_PORT
    kill_port $PAYMENTS_PORT
    log_success "All ports cleared"
    echo ""

    # Load nvm and switch to correct Node version
    log_info "Loading Node.js environment..."
    if load_nvm; then
        if [ -f ".nvmrc" ]; then
            nvm use 2>/dev/null || nvm install
        fi
        log_success "Node $(node --version) active"
    fi
    echo ""

    # Start CoDRAG Daemon
    log_info "Starting CoDRAG daemon on port $DAEMON_PORT..."
    # Kill orphaned codrag processes that may not be listening on a port.
    # MCP processes hold SQLite connections to codrag_settings.db — if they
    # have uncommitted transactions, the daemon can't write to the DB.
    pkill -f "codrag.cli serve" 2>/dev/null || true
    pkill -f "codrag serve" 2>/dev/null || true
    pkill -f "codrag mcp" 2>/dev/null || true
    pkill -f "daemon_watchdog.sh" 2>/dev/null || true
    sleep 1
    # F-81: Launch under a watchdog so crash tracebacks are captured
    # (/tmp/codrag_daemon_logs/daemon_<ts>.log) and the daemon respawns
    # automatically. history.log records every spawn/exit with exit code
    # + last 40 lines of that run's log so you can see WHY it died.
    # Bails after 5 consecutive fast crashes (<30s uptime) to avoid thrash.
    PROJECT_ROOT="$PROJECT_ROOT" DAEMON_PORT="$DAEMON_PORT" \
      "$PROJECT_ROOT/scripts/daemon_watchdog.sh" &
    DAEMON_PID=$!
    sleep 3
    if kill -0 $DAEMON_PID 2>/dev/null; then
        log_success "CoDRAG daemon running under watchdog (PID: $DAEMON_PID, logs: /tmp/codrag_daemon_logs/)"
    else
        log_error "CoDRAG daemon watchdog failed to start"
    fi
    echo ""

    # Start Dashboard Frontend
    log_info "Starting Dashboard frontend on port $DASHBOARD_PORT..."
    (source ~/.nvm/nvm.sh && nvm use 20 >/dev/null && cd "$PROJECT_ROOT/src/codrag/dashboard" && npm run dev -- --port $DASHBOARD_PORT --host) &
    DASHBOARD_PID=$!
    echo ""

    # Start Storybook
    log_info "Starting Storybook on port $STORYBOOK_PORT..."
    (source ~/.nvm/nvm.sh && nvm use 20 >/dev/null && cd "$PROJECT_ROOT/packages/ui" && npm run storybook -- -p $STORYBOOK_PORT) &
    STORYBOOK_PID=$!
    echo ""

    # Start Websites (turbo dev runs all apps)
    log_info "Starting websites (marketing, docs, support, payments)..."
    if [ -d "$PROJECT_ROOT/websites/apps" ]; then
        (source ~/.nvm/nvm.sh && nvm use 20 >/dev/null && cd "$PROJECT_ROOT" && npx turbo run dev --filter="./websites/apps/*") &
        WEBSITES_PID=$!
    else
        log_warn "No websites/apps directory found — skipping website dev servers"
        WEBSITES_PID=""
    fi
    echo ""

    # Wait a moment for services to initialize
    sleep 5

    # Print summary
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Services Running                          ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  CoDRAG Daemon     │  http://localhost:$DAEMON_PORT              ║"
    echo "║  Dashboard UI      │  http://localhost:$DASHBOARD_PORT              ║"
    echo "║  Storybook         │  http://localhost:$STORYBOOK_PORT               ║"
    echo "║  Marketing Site    │  http://localhost:$MARKETING_PORT               ║"
    echo "║  Docs Site         │  http://localhost:$DOCS_PORT               ║"
    echo "║  Support Site      │  http://localhost:$SUPPORT_PORT               ║"
    echo "║  Payments Site     │  http://localhost:$PAYMENTS_PORT               ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Press Ctrl+C to stop all services                           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # Wait for all background processes
    wait
}

# Parse arguments
case "${1:-}" in
    --kill|kill)
        log_info "Killing all dev services..."
        # Stop the watchdog first so it doesn't immediately respawn the daemon
        pkill -f "daemon_watchdog.sh" 2>/dev/null || true
        kill_port $DAEMON_PORT
        kill_port $DASHBOARD_PORT
        kill_port $STORYBOOK_PORT
        kill_port $MARKETING_PORT
        kill_port $DOCS_PORT
        kill_port $SUPPORT_PORT
        kill_port $PAYMENTS_PORT
        log_success "Done"
        exit 0
        ;;
    --help|-h)
        echo "Usage: $0 [--kill|--help]"
        echo ""
        echo "  (no args)   Start all development services"
        echo "  --kill      Kill all services on dev ports"
        echo "  --help      Show this help"
        exit 0
        ;;
    *)
        main
        ;;
esac
