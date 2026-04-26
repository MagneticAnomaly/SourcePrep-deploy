#!/usr/bin/env bash
set -euo pipefail

prefix="public/sourceprep-mcp"
dev_remote="mcp-dev"
public_remote="mcp"
branch="main"
push_public="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      prefix="$2"
      shift 2
      ;;
    --dev-remote)
      dev_remote="$2"
      shift 2
      ;;
    --public-remote)
      public_remote="$2"
      shift 2
      ;;
    --branch)
      branch="$2"
      shift 2
      ;;
    --promote)
      push_public="true"
      shift 1
      ;;
    -h|--help)
      echo "Usage: scripts/publish_prep_mcp_subtree.sh [--prefix PATH] [--dev-remote NAME] [--public-remote NAME] [--branch NAME] [--promote]"
      echo "  Exports subtree at PATH and pushes to dev remote; with --promote also pushes to public remote."
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel)"

if [[ ! -d "$repo_root/$prefix" ]]; then
  echo "Prefix folder not found: $prefix" >&2
  exit 1
fi

if ! git -C "$repo_root" diff --quiet; then
  echo "Working tree is not clean. Commit or stash changes before publishing." >&2
  exit 1
fi

if ! git -C "$repo_root" diff --cached --quiet; then
  echo "Index (staged changes) is not clean. Commit or unstage changes before publishing." >&2
  exit 1
fi

if ! git -C "$repo_root" remote get-url "$dev_remote" >/dev/null 2>&1; then
  echo "Missing git remote: $dev_remote" >&2
  exit 1
fi

if [[ "$push_public" == "true" ]]; then
  if ! git -C "$repo_root" remote get-url "$public_remote" >/dev/null 2>&1; then
    echo "Missing git remote: $public_remote" >&2
    exit 1
  fi
fi

split_commit="$(git -C "$repo_root" subtree split --prefix "$prefix")"

git -C "$repo_root" push "$dev_remote" "$split_commit:refs/heads/$branch"

if [[ "$push_public" == "true" ]]; then
  git -C "$repo_root" push "$public_remote" "$split_commit:refs/heads/$branch"
fi

echo "Published subtree ($prefix) as commit $split_commit"
