#!/usr/bin/env bash
# Returns non-zero if any rogue CoDRAG/CLaRa references remain outside the allowlist.
# Usage: bash scripts/rename_gate.sh            # prints offending lines
#        bash scripts/rename_gate.sh | wc -l    # expected: 0 before merge
set -u
grep -rniE 'codrag|clara|codrag\.io|codrag\.ai' \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=target --exclude-dir=dist --exclude-dir=build \
  --exclude-dir=__pycache__ --exclude-dir=.turbo --exclude-dir=.next \
  --exclude=package-lock.json --exclude=Cargo.lock --exclude=uv.lock \
  --exclude='*.lock' \
  . 2>/dev/null | grep -v -F -f .rename-allowlist.txt
