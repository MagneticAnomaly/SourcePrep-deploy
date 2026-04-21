#!/bin/bash
# MCP wrapper script to use project venv for prep
# Default: server mode (proxies to daemon at :8400, full multi-project support)
# Pass --mode direct to use in-process mode (no daemon required, single project)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/.prep/logs"
mkdir -p "$LOG_DIR"
exec "$SCRIPT_DIR/.venv/bin/prep" mcp --log-file "$LOG_DIR/mcp-stdio.log" "$@"
