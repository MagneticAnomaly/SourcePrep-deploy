#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════
# Prep Overnight Build & Test Suite
# ═══════════════════════════════════════════════════════════════════
# Run this unattended overnight. Logs everything to overnight_results/
#
# Usage:
#   bash scripts/overnight_build.sh          # run all stages
#   bash scripts/overnight_build.sh --skip-tauri  # skip Tauri (needs Xcode)
#
# Stages:
#   1. Python test suite (pytest)
#   2. TypeScript type check (tsc --noEmit)
#   3. Rust engine wheel (maturin build)
#   4. Rust cargo test + cargo audit
#   5. PyInstaller sidecar build
#   6. npm audit (all packages)
#   7. Tauri app build (optional)
#
# Each stage logs to overnight_results/<stage>.log
# Final summary written to overnight_results/SUMMARY.txt
# ═══════════════════════════════════════════════════════════════════

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$REPO_ROOT/overnight_results"
SKIP_TAURI=false

PYTHON="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

MATURIN="$REPO_ROOT/.venv/bin/maturin"
if [ ! -x "$MATURIN" ]; then
  MATURIN="maturin"
fi

if [ -s "$HOME/.nvm/nvm.sh" ]; then
  . "$HOME/.nvm/nvm.sh"
  if [ -f "$REPO_ROOT/.nvmrc" ]; then
    nvm use "$(cat "$REPO_ROOT/.nvmrc")" >/dev/null 2>&1 || true
  else
    nvm use 20 >/dev/null 2>&1 || true
  fi
fi

if command -v rustup &> /dev/null; then
  RUSTUP_CARGO="$(rustup which cargo 2>/dev/null || true)"
  if [ -n "$RUSTUP_CARGO" ] && [ -x "$RUSTUP_CARGO" ]; then
    export PATH="$(dirname "$RUSTUP_CARGO"):$PATH"
  fi
fi

for arg in "$@"; do
  case "$arg" in
    --skip-tauri) SKIP_TAURI=true ;;
  esac
done

mkdir -p "$RESULTS_DIR"
SUMMARY="$RESULTS_DIR/SUMMARY.txt"

echo "Prep Overnight Build — $(date)" | tee "$SUMMARY"
echo "======================================" | tee -a "$SUMMARY"
echo "" | tee -a "$SUMMARY"

PASS=0
FAIL=0
SKIP=0

run_stage() {
  local name="$1"
  local logfile="$RESULTS_DIR/${name}.log"
  shift

  echo -n "[$name] Running... "
  echo "=== $name ===" >> "$SUMMARY"

  local start_time=$(date +%s)
  if "$@" > "$logfile" 2>&1; then
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    echo "✅ PASS (${duration}s)"
    echo "  ✅ PASS (${duration}s)" >> "$SUMMARY"
    PASS=$((PASS + 1))
  else
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local exit_code=$?
    echo "❌ FAIL (exit $exit_code, ${duration}s)"
    echo "  ❌ FAIL (exit $exit_code, ${duration}s)" >> "$SUMMARY"
    echo "  Last 20 lines of log:" >> "$SUMMARY"
    tail -20 "$logfile" | sed 's/^/    /' >> "$SUMMARY"
    FAIL=$((FAIL + 1))
  fi
  echo "" >> "$SUMMARY"
}

skip_stage() {
  local name="$1"
  echo "[$name] SKIPPED"
  echo "=== $name ===" >> "$SUMMARY"
  echo "  ⏭️  SKIPPED" >> "$SUMMARY"
  echo "" >> "$SUMMARY"
  SKIP=$((SKIP + 1))
}

# ── Stage 1: Python Tests ────────────────────────────────────────
# Run without -x (fail-fast) so we get all test results, then check for failures
run_stage "python-tests" "$PYTHON" -m pytest "$REPO_ROOT/tests" -v --tb=short -q

# ── Stage 2: TypeScript Type Check ───────────────────────────────
run_stage "ts-typecheck" "$REPO_ROOT/node_modules/.bin/tsc" -p "$REPO_ROOT/src/prep/dashboard/tsconfig.json" --noEmit

# ── Stage 3: Rust Engine Wheel ───────────────────────────────────
run_stage "engine-wheel" bash -c "cd '$REPO_ROOT/engine' && \"$MATURIN\" build --release"

# ── Stage 4: Rust Tests ─────────────────────────────────────────
run_stage "rust-tests" bash -c "cd '$REPO_ROOT/engine' && cargo test --workspace --locked"

# ── Stage 5: Cargo Audit ─────────────────────────────────────────
if command -v cargo-audit &> /dev/null; then
  run_stage "cargo-audit" bash -c "cd '$REPO_ROOT/engine' && cargo audit"
else
  # Try to install cargo-audit first
  echo "[cargo-audit] Installing cargo-audit..."
  if cargo install cargo-audit 2>/dev/null; then
    run_stage "cargo-audit" bash -c "cd '$REPO_ROOT/engine' && cargo audit"
  else
    skip_stage "cargo-audit"
  fi
fi

# ── Stage 6: PyInstaller Sidecar Build ───────────────────────────
run_stage "sidecar-build" bash "$REPO_ROOT/scripts/build_sidecar.sh"

# ── Stage 7: npm audit ──────────────────────────────────────────
# Run on each package that has a package-lock.json
run_stage "npm-audit-root" bash -c "cd '$REPO_ROOT' && npm audit --omit=dev 2>&1 || true"
run_stage "npm-audit-ui" bash -c "cd '$REPO_ROOT/packages/ui' && npm audit --omit=dev 2>&1 || true"
run_stage "npm-audit-mcp" bash -c "cd '$REPO_ROOT/public/prep-mcp' && npm audit --omit=dev 2>&1 || true"

# ── Stage 8: Tauri App Build ────────────────────────────────────
if [ "$SKIP_TAURI" = true ]; then
  skip_stage "tauri-build"
else
  # Tauri build exits 0 even with signing warnings - check for actual build artifacts
  run_stage "tauri-build" bash -c "cd '$REPO_ROOT/src/prep/dashboard' && npx tauri build 2>&1 && ls -la src-tauri/target/release/bundle/macos/Prep.app 2>/dev/null || ls -la src-tauri/target/release/bundle/dmg/*.dmg 2>/dev/null"
fi

# ── Summary ─────────────────────────────────────────────────────
echo "" | tee -a "$SUMMARY"
echo "======================================" | tee -a "$SUMMARY"
echo "TOTAL: $PASS passed, $FAIL failed, $SKIP skipped" | tee -a "$SUMMARY"
echo "Completed: $(date)" | tee -a "$SUMMARY"
echo ""
echo "Full results in: $RESULTS_DIR/"
echo "Summary: $SUMMARY"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "⚠️  $FAIL stage(s) failed. Check logs in $RESULTS_DIR/"
  exit 1
fi
