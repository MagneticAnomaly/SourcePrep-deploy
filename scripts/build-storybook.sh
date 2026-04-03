#!/usr/bin/env bash
# scripts/build-storybook.sh — Build Storybook static assets for docs embeds.
#
# Usage:
#   ./scripts/build-storybook.sh          # Build only
#   ./scripts/build-storybook.sh --copy   # Build + copy to docs public dir
#
# The storybook-static/ directory is the source of truth for docs embeds.
# Run this after any changes to packages/ui/src/stories/ or components/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UI_DIR="$ROOT_DIR/packages/ui"
DOCS_PUBLIC="$ROOT_DIR/websites/apps/docs/public/storybook"

echo "🔨 Building Storybook..."
cd "$UI_DIR"
npx storybook build --quiet

echo "✅ Storybook built → $UI_DIR/storybook-static/"

if [[ "${1:-}" == "--copy" ]]; then
  echo "📦 Copying to docs public directory..."
  rm -rf "$DOCS_PUBLIC"
  cp -r "$UI_DIR/storybook-static" "$DOCS_PUBLIC"
  echo "✅ Copied → $DOCS_PUBLIC"
fi

echo "Done."
