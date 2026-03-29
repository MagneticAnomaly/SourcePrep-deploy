#!/bin/bash
# MCP wrapper script to use project venv for codrag
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/codrag" mcp --mode direct "$@"
