#!/usr/bin/env bash
set -euo pipefail

# Publish the prep-deploy subtree to a standalone public repo.
# Shared pattern for publishing a subtree to a public-facing remote.
#
# Usage:
#   scripts/publish_deploy_subtree.sh                  # push to dev remote
#   scripts/publish_deploy_subtree.sh --promote        # also push to public remote

prefix="public/sourceprep-deploy"
dev_remote="deploy-dev"
public_remote="deploy"
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
      echo "Usage: scripts/publish_deploy_subtree.sh [--prefix PATH] [--dev-remote NAME] [--public-remote NAME] [--branch NAME] [--promote]"
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
  echo "Add it with: git remote add $dev_remote git@github.com:MagneticAnomaly/SourcePrep-deploy.git"
  echo "Or run with: --dev-remote $public_remote to skip the staging hop."
  exit 1
fi

if [[ "$push_public" == "true" ]]; then
  if ! git -C "$repo_root" remote get-url "$public_remote" >/dev/null 2>&1; then
    echo "Missing git remote: $public_remote" >&2
    exit 1
  fi
fi

split_commit="$(git -C "$repo_root" subtree split --prefix "$prefix")"

# --- Content gate (DR-D §2.2 / ED-6) --------------------------------------
# subtree split publishes the subtree WITH its full history, so any secret ever
# committed under "$prefix" would leak to the remote. Gate before ANY push. The
# only fully-robust fix is a fresh-initial-commit export (no history) — see
# tools/build_public_mirror.py. Until then, hard-fail on:
#   (1) any private-key/secret marker in the subtree HISTORY, and
#   (2) any dead-codename string in the published TREE.
secret_re='-----BEGIN [A-Z ]*PRIVATE KEY-----|BEGIN OPENSSH PRIVATE KEY|rsign encrypted secret key|AKIA[0-9A-Z]{16}|gh[pousr]_[0-9A-Za-z]{36}|xox[baprs]-[0-9A-Za-z-]{20}|[sr]k_live_[0-9A-Za-z]{20}|sk-(ant|proj)-[A-Za-z0-9_-]{20}|AWS_SECRET_ACCESS_KEY=|LEMON_SQUEEZY_API_KEY=|codrag\.key'
if git -C "$repo_root" log -p "$split_commit" | grep -aE "$secret_re" >/dev/null; then
  echo "GATE FAIL: secret/private-key marker in subtree history ($prefix). Do NOT publish." >&2
  echo "  Inspect: git log -p $split_commit | grep -nE '$secret_re'" >&2
  exit 1
fi
if git -C "$repo_root" grep -I -i -E 'codrag|CoDRAG|RunPrep|\.runprep' "$split_commit" >/dev/null 2>&1; then
  echo "GATE FAIL: dead-codename string in published subtree tree ($prefix). Scrub before publishing." >&2
  echo "  Inspect: git grep -inE 'codrag|runprep' $split_commit" >&2
  exit 1
fi
echo "Content gate passed for subtree ($prefix)."
# --------------------------------------------------------------------------

git -C "$repo_root" push "$dev_remote" "$split_commit:refs/heads/$branch"

if [[ "$push_public" == "true" ]]; then
  git -C "$repo_root" push "$public_remote" "$split_commit:refs/heads/$branch"
fi

echo "Published subtree ($prefix) as commit $split_commit"
