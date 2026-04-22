#!/usr/bin/env bash
# Returns non-zero if any rogue CoDRAG/CLaRa references remain outside the allowlist.
# Usage: bash scripts/rename_gate.sh            # prints offending lines
#        bash scripts/rename_gate.sh | wc -l    # expected: 0 before merge
set -u
grep -rniE 'codrag|\bclara\b|codrag\.io|codrag\.ai|\brunprep\b|runprep\.io' \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=target --exclude-dir=dist --exclude-dir=build \
  --exclude-dir=__pycache__ --exclude-dir=.turbo --exclude-dir=.next \
  --exclude-dir=.mypy_cache --exclude-dir=.venv_build --exclude-dir=.codrag \
  --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude-dir=worktrees \
  --exclude-dir=.DS_Store --exclude-dir=storybook-static \
  --exclude=package-lock.json --exclude=Cargo.lock --exclude=uv.lock \
  --exclude='*.lock' --exclude='*.timestamp-*.mjs' \
  . 2>/dev/null | grep -v -F -f .rename-allowlist.txt
