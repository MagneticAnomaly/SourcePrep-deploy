#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DO_CLEAN=0
DO_INSTALL=0
DO_BUILD=0
DO_DEV=0
CHECK_PORTS=1

if [[ $# -eq 0 ]]; then
  DO_CLEAN=1
  DO_BUILD=1
  DO_DEV=1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)
      DO_CLEAN=1
      shift
      ;;
    --install)
      DO_INSTALL=1
      shift
      ;;
    --build)
      DO_BUILD=1
      shift
      ;;
    --dev)
      DO_DEV=1
      shift
      ;;
    --no-port-check)
      CHECK_PORTS=0
      shift
      ;;
    -h|--help)
      printf '%s\n' "Usage: scripts/run_websites.sh [--clean] [--install] [--build] [--dev]" \
        "" \
        "No args defaults to: --clean --build --dev" \
        "" \
        "Examples:" \
        "  bash scripts/run_websites.sh" \
        "  bash scripts/run_websites.sh --clean --build" \
        "  bash scripts/run_websites.sh --dev" \
        "" \
        "Notes:" \
        "  --clean removes Next.js/Vite build artifacts to fix occasional corrupt build outputs." \
        "  By default, builds require ports 3000-3003 to be free (use --no-port-check to bypass)."
      exit 0
      ;;
    *)
      printf '%s\n' "Unknown arg: $1" "Run with --help for usage." >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ $CHECK_PORTS -eq 1 && ( $DO_CLEAN -eq 1 || $DO_BUILD -eq 1 ) ]]; then
  BUSY=0
  for PORT in 3000 3001 3003; do
    PID="$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
    if [[ -n "${PID}" ]]; then
      CMD="$(ps -p "${PID}" -o command= 2>/dev/null | head -n 1 || true)"
      printf '%s\n' "Port ${PORT} is in use by PID ${PID}: ${CMD}" >&2
      BUSY=1
    fi
  done
  if [[ $BUSY -eq 1 ]]; then
    printf '%s\n' "Stop the running dev server(s) and re-run (or pass --no-port-check)." >&2
    exit 1
  fi
fi

if [[ $DO_CLEAN -eq 1 ]]; then
  rm -rf "$ROOT_DIR/.turbo" || true
  rm -rf "$ROOT_DIR/websites/apps"/*/.next || true
  rm -rf "$ROOT_DIR/websites/apps"/*/out || true
  rm -rf "$ROOT_DIR/websites/apps"/*/.turbo || true
  rm -rf "$ROOT_DIR/packages/ui/dist" || true
  rm -rf "$ROOT_DIR/packages/ui/storybook-static" || true
  rm -rf "$ROOT_DIR/src/prep/dashboard/dist" || true
  rm -rf "$ROOT_DIR/src/prep/dashboard/.vite" || true
fi

if [[ $DO_INSTALL -eq 1 ]]; then
  npm install
fi

if [[ $DO_BUILD -eq 1 ]]; then
  NODE_ENV=production npm run build
fi

if [[ $DO_DEV -eq 1 ]]; then
  npm run dev
fi
