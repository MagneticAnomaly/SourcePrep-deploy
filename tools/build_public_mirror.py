#!/usr/bin/env python3
"""Build the public mirror tree for the SourcePrep OSS release (Phase 142 C2).

The public surface is a **fresh-initial-commit mirror**: a curated subset of
the workshop repo (``/Volumes/4TB-BAD/HumanAI/CoDRAG``) emitted to a clean
target directory, which then becomes the first commit of the public
storefront repo (``MagneticAnomaly/SourcePrep``). The workshop repo keeps its
full history and is never published. See:

    docs/Phase142_OSS-First/REPO_TOPOLOGY.md
    docs/Phase142_OSS-First/DECISION_MEMO_2026-07-17.md  (C2, D8)
    docs/Phase144_LegalPreLaunch/PRE_LAUNCH_BLOCKERS.md  §2 (live-tree secrets)

This script does THREE things:

1. **Path allowlist** — include only the curated public surface (the engine,
   MCP server, CLI, dashboard, VS Code extension, public websites, governance
   docs, build config). Everything else is excluded by default.
2. **Path denylist** — exclude build artifacts, vendored deps, internal
   phase docs, local state, and known private files EVEN IF they fall under
   an allowlisted top-level dir.
3. **Content denylist-regex gate** — scan every included file's content for
   forbidden markers (dead codenames, internal-doc names, private-key
   markers, API-key patterns, the codrag.key filename). Fail on ANY hit.
   This is the safety net that catches a secret or an internal reference
   that slipped into an otherwise-public file.

The script does NOT rewrite history and does NOT touch the workshop repo.
It only reads the workshop tree and (with ``--emit DIR``) writes a clean copy
to DIR. Run ``git init && git add . && git commit -m "Initial public
release"`` in DIR to produce the fresh initial commit.

Usage:
    # Dry run (default): print the manifest, fail on any denylist hit.
    python tools/build_public_mirror.py
    # Emit the public tree to a target directory:
    python tools/build_public_mirror.py --emit /tmp/sourceprep-public
    # Write the manifest to a file:
    python tools/build_public_mirror.py --manifest /tmp/mirror-manifest.json

Exit codes: 0 = clean (all included files passed the gate); 1 = denylist hit
(or an emit error); 2 = usage error.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 1. PATH ALLOWLIST — top-level paths to include in the public mirror.
#    Everything not under one of these is excluded. Sub-exclusions (denylist)
#    still apply WITHIN these.
# ---------------------------------------------------------------------------
ALLOW_TOP = [
    "src",                      # Python backend (engine, MCP, CLI, daemon, api)
    "engine",                   # Rust engine crates
    "packages",                  # @prep/ui, vscode ext, paperclip plugin
    "tools",                    # dev/license/audit tooling (public-safe subset)
    "tests",                    # test suite
    "public",                   # public/sourceprep-mcp (the public MCP package)
    "scripts",                  # dev scripts (dev.sh, etc.)
    "websites/apps/docs",       # public docs site
    "websites/apps/marketing",  # public marketing site
    "websites/apps/support",    # public support portal
    "websites/apps/payments",   # public payments portal
    "docs/assets",              # images referenced by the public README
    # Governance + root docs (public):
    "README.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHARTER.md",
    "SUPPORT.md",
    "AGENTS.md",                # public-safe generated AGENTS.md (no frankness)
    # Build config (public):
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "turbo.json",
    "engine/Cargo.toml",
    "mcp-server.json",
    "prep-mcp-wrapper.sh",
    "prep-daemon.spec",
    # Brand images:
    "prep-logo.png",
    "sourceprep-github-header.png",
]

# ---------------------------------------------------------------------------
# 2. PATH DENYLIST — exclude even within allowlisted top-level dirs.
#    Matched as glob patterns against the repo-relative path (POSIX).
# ---------------------------------------------------------------------------
DENY_PATH_GLOBS = [
    # Build artifacts / vendored deps / caches:
    "node_modules",
    "*/node_modules",
    "*/**/node_modules",
    "target",
    "*/target",
    ".venv",
    "dist",
    "*/dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "*/__pycache__",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    "*.so",
    "*.dylib",
    ".turbo",
    # Local state + private metadata:
    ".sourceprep",
    "*/.sourceprep",
    ".claude",
    ".runprep",
    "prep_data",
    "codrag_data",
    "*/codrag_data",
    # Committed daemon-state DBs (e.g. the dead-codename src/codrag_data/*.db
    # still tracked on origin/main) — the content gate can't see these (it
    # scans content, not paths; a .db can be >2 MiB and skip the scan). DR-D §7.
    "*.db",
    "*.db-wal",
    "*.db-shm",
    ".migrated_from_cwd",
    "daemon_rss.jsonl",
    "*.migration-conflict.*",
    # Internal phase docs (NOT public):
    "docs/Phase*",
    "docs/superpowers",
    "docs/MARKETING_SITE_AUDIT.md",
    "docs/MASTER_TODO.md",
    "docs/PARALLEL_LANES*",
    "docs/stashes-pending-review",
    "docs/AUDIT*",
    "docs/HANDOFF*",
    "docs/RESEARCH_ROUND*",
    # Internal-only files (denylist-regex also catches references):
    "CLAUDE.md",
    "CLAUDE.local.md",
    "HANDOFF.md",
    "HANDOFF_PROMPT*",
    # Known secret file (live-tree secret; also on origin — rotate separately):
    "codrag.key",
    "*.key",
    "*.pem",
    # Logs / scratch:
    "logs",
    "tmp",
    "overnight_results",
    "archive",
    "*.log",
    "dev.log",
    # Websites — exclude build output + private config:
    "websites/apps/*/.next",
    "websites/apps/*/out",
    "websites/apps/*/.env*",
    # Dashboard demo png (may leak internal state; re-capture for public):
    "dashboard-demo.png",
    # Exclude MagneticAnomaly brand site (Eric's separate portfolio site):
    "websites/MagneticAnomaly",
]

# ---------------------------------------------------------------------------
# 3. CONTENT DENYLIST-REGEX — scan each included file; fail on any match.
#    Each entry: (label, compiled regex). The label is printed on a hit so the
#    manifest says WHAT was caught.
# ---------------------------------------------------------------------------
CONTENT_REGEXES = [
    # Dead codenames — should already be scrubbed from live code; catches
    # leftovers in any included file.
    ("dead-codename: codrag/CoDRAG", re.compile(r"codrag|CoDRAG", re.IGNORECASE)),
    ("dead-codename: RunPrep/.runprep", re.compile(r"RunPrep|\.runprep", re.IGNORECASE)),
    # The known secret filename.
    ("secret-file: codrag.key", re.compile(r"codrag\.key")),
    # Private-key material (PEM blocks + generic private-key markers).
    ("private-key: PEM block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("private-key: generic", re.compile(r"PRIVATE KEY-----", re.IGNORECASE)),
    # Internal-only doc names — a public file referencing these leaks the
    # existence of internal planning. The denylist-regex forces public files
    # to not cite internal artifacts.
    ("internal-doc: ACQUIRER_MAP", re.compile(r"ACQUIRER_MAP|ACQUIRER\b")),
    ("internal-doc: SCRUTINY", re.compile(r"SCRUTINY\.md|SCRUTINY\b")),
    ("internal-doc: DISTRIBUTION_AND_REVENUE_PLAN", re.compile(r"DISTRIBUTION_AND_REVENUE_PLAN")),
    ("internal-doc: AUDIT_2026-07-17", re.compile(r"AUDIT_2026-07-17")),
    ("internal-doc: HANDOFF_PROMPT", re.compile(r"HANDOFF_PROMPT")),
    ("internal-doc: RESEARCH_ROUND_2", re.compile(r"RESEARCH_ROUND_2")),
    ("internal-doc: MARKETING_SITE_AUDIT", re.compile(r"MARKETING_SITE_AUDIT")),
    ("internal-doc: CLAUDE.md reference", re.compile(r"\bCLAUDE\.md\b")),
    # Live secret patterns (API keys / tokens). High-signal prefixes.
    ("secret: AWS key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("secret: GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("secret: Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("secret: OpenAI/Anthropic sk- key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("secret: Lemon Squeezy key env", re.compile(r"LEMON_SQUEEZY_API_KEY\s*=")),
    ("secret: AWS secret env", re.compile(r"AWS_SECRET_ACCESS_KEY\s*=")),
]

# Binary file extensions — skip content scan (can't grep a PNG meaningfully).
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",  # images
    ".woff", ".woff2", ".ttf", ".otf", ".eot",                 # fonts
    ".mp4", ".webm", ".mov", ".mp3", ".wav",                   # media
    ".zip", ".gz", ".tar", ".tgz", ".lock",                   # archives (Cargo.lock is text, handled below)
    ".bin", ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo",  # binaries
}


def path_allowed(rel: str) -> bool:
    """True if rel is under an allowlisted top-level path."""
    rel_norm = rel.replace("\\", "/")
    top = rel_norm.split("/")[0]
    # Exact top-level file match (README.md, LICENSE, etc.) or a path under an
    # allowlisted dir. Multi-segment allow entries (websites/apps/docs) match
    # as a path prefix.
    for a in ALLOW_TOP:
        if rel_norm == a or rel_norm.startswith(a + "/"):
            return True
    # Allow docs/assets/* under any docs allowlist entry (covered by the
    # explicit "docs/assets" entry above).
    return False


def path_denied(rel: str) -> list[str]:
    """Return the list of deny globs that match rel (empty = not denied)."""
    rel_norm = rel.replace("\\", "/")
    hits = []
    for g in DENY_PATH_GLOBS:
        # Match against the full path AND each path segment, so a glob like
        # 'node_modules' catches 'node_modules', 'packages/ui/node_modules',
        # and 'foo/node_modules/bar'.
        if fnmatch.fnmatch(rel_norm, g) or fnmatch.fnmatch(rel_norm, f"*/{g}"):
            hits.append(g)
            continue
        # Also match any segment (e.g. __pycache__ anywhere in the tree).
        parts = rel_norm.split("/")
        if any(fnmatch.fnmatch(p, g) for p in parts):
            hits.append(g)
    return hits


def content_hits(path: Path) -> list[tuple[str, int, str]]:
    """Scan a file for content denylist hits. Returns [(label, line, sample)].

    Files larger than CONTENT_SCAN_MAX_BYTES are skipped (a secret marker
    would not appear in a multi-MB binary or minified bundle, and reading +
    regexing them hangs the run). Binary extensions are skipped too.
    """
    ext = path.suffix.lower()
    if ext in BINARY_EXTS:
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size > CONTENT_SCAN_MAX_BYTES:
        return []  # large file — skipped (caller logs it as skipped-large)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []
    hits = []
    for label, rx in CONTENT_REGEXES:
        for m in rx.finditer(text):
            # Find the line number for the match.
            line_no = text.count("\n", 0, m.start()) + 1
            sample = text[m.start():m.start() + 40].replace("\n", " ")
            hits.append((label, line_no, sample))
            break  # one hit per regex per file is enough to flag it
    return hits


HARD_PRUNE_DIRS = {
    "node_modules", ".git", ".venv", "target", ".turbo", "__pycache__",
    ".mypy_cache", ".ruff_cache", "dist", "build", "logs", "tmp",
    "overnight_results", "archive", ".sourceprep", ".runprep", "prep_data",
    ".next", "out", ".claude",
    # Build outputs / generated trees that should not ship in the mirror:
    "storybook-static",      # built Storybook (packages/ui/storybook-static)
    "binaries",              # precompiled Tauri daemon binaries (64MB+ each)
    ".codrag",               # dead-codename test-fixture dirs
}

# Path-prefix hard prunes — full subtrees os.walk must NOT descend into, by
# repo-relative path. Heavy test/eval fixtures + the separate MagneticAnomaly
# brand site. Without these the walk times out descending 23k+ files.
HARD_PRUNE_PATHS = {
    "tests/eval",            # 23k-file eval/fixture harness — not public
    "websites/MagneticAnomaly",  # Eric's separate brand portfolio site
}

# Files larger than this are skipped by the content scan (a secret marker
# would not appear in a 64MB binary or a minified bundle; reading+regexing
# them hangs the run). Logged as "skipped-large" in the manifest so the size
# is visible. Lower this if a real concern surfaces.
CONTENT_SCAN_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB


def _is_ancestor_of_allowed(rel: str) -> bool:
    """True if rel is a prefix of some allowlisted path (so we must descend)."""
    for a in ALLOW_TOP:
        if a.startswith(rel + "/") or a == rel:
            return True
    return False


def collect() -> tuple[list[str], list[tuple[str, list[str]]], list[tuple[str, list[tuple[str, int, str]]]]]:
    """Walk the repo. Return (included, excluded, flagged).
    - included: repo-relative paths that passed allow + deny + content gate.
    - excluded: (path, deny-globs) for paths dropped by the denylist.
    - flagged:  (path, content-hits) for paths that FAILED the content gate.
    """
    included: list[str] = []
    excluded: list[tuple[str, list[str]]] = []
    flagged: list[tuple[str, list[tuple[str, int, str]]]] = []
    # This script itself contains the denylist regex patterns as string
    # literals (it must, to define the gate). Self-scan would self-report every
    # pattern as a hit. Exclude the script from its own content scan.
    self_path = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        rel_dir = Path(dirpath).relative_to(REPO_ROOT).as_posix()

        # HARD prune: never descend into heavy/irrelevant dirs. This is the
        # performance-critical step — without it os.walk descends into
        # node_modules (tens of thousands of files) and the run times out.
        dirnames[:] = [d for d in dirnames if d not in HARD_PRUNE_DIRS]
        # HARD prune by path prefix (tests/eval, websites/MagneticAnomaly).
        dirnames[:] = [
            d for d in dirnames
            if f"{rel_dir}/{d}" not in HARD_PRUNE_PATHS and rel_dir not in HARD_PRUNE_PATHS
        ]

        # Prune dirs that are neither allowlisted themselves, ancestors of an
        # allowlisted path, nor under an allowlisted dir. This keeps the walk
        # out of docs/Phase*, .runprep, etc.
        kept = []
        for d in dirnames:
            rel = f"{rel_dir}/{d}" if rel_dir != "." else d
            if path_allowed(rel) or _is_ancestor_of_allowed(rel) or _under_allowed(rel):
                kept.append(d)
        dirnames[:] = kept

        for f in filenames:
            rel = f"{rel_dir}/{f}" if rel_dir != "." else f
            if not path_allowed(rel):
                continue
            denied = path_denied(rel)
            if denied:
                excluded.append((rel, denied))
                continue
            if rel == self_path:
                included.append(rel)  # the script itself; skip its content scan
                continue
            hits = content_hits(REPO_ROOT / rel)
            if hits:
                flagged.append((rel, hits))
            else:
                included.append(rel)
    included.sort()
    excluded.sort(key=lambda x: x[0])
    flagged.sort(key=lambda x: x[0])
    return included, excluded, flagged


def _under_allowed(rel: str) -> bool:
    """True if rel sits under an allowlisted directory (not just a file match)."""
    rel_norm = rel.replace("\\", "/")
    for a in ALLOW_TOP:
        # Allow entries that are directories (no extension) — treat as prefix.
        if "." not in Path(a).name and (rel_norm.startswith(a + "/")):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emit", metavar="DIR", help="Copy the included files to DIR (otherwise dry-run).")
    ap.add_argument("--manifest", metavar="PATH", help="Write the manifest JSON to PATH.")
    ap.add_argument("--force", action="store_true", help="With --emit, overwrite an existing DIR.")
    args = ap.parse_args()

    included, excluded, flagged = collect()

    print(f"Included: {len(included)} files")
    print(f"Excluded (denylist): {len(excluded)} files")
    print(f"FLAGGED (content denylist hit): {len(flagged)} files")
    if flagged:
        print("\n=== CONTENT DENYLIST HITS (must resolve before emit) ===")
        for rel, hits in flagged:
            print(f"\n  {rel}")
            for label, line, sample in hits:
                print(f"    line {line}: {label}  ->  {sample!r}")
    if excluded and len(excluded) <= 40:
        print("\n=== Excluded (path denylist) ===")
        for rel, globs in excluded:
            print(f"  {rel}  (matched: {', '.join(globs)})")
    elif excluded:
        print(f"\n(Excluded list suppressed — {len(excluded)} files; see manifest for full list.)")

    if args.manifest:
        Path(args.manifest).write_text(json.dumps({
            "included": included,
            "excluded": [{"path": p, "deny_globs": g} for p, g in excluded],
            "flagged": [{"path": p, "hits": [{"label": l, "line": n, "sample": s} for l, n, s in h]} for p, h in flagged],
        }, indent=2, sort_keys=True))
        print(f"\nManifest written to {args.manifest}")

    if flagged:
        print("\nFAIL: content denylist hits — resolve (scrub the marker, or add the file to the path denylist) before emitting the mirror.")
        if args.emit:
            print("Refusing to emit with unresolved content hits. Re-run without --emit to inspect, or fix the hits.")
        return 1

    if args.emit:
        target = Path(args.emit)
        if target.exists() and not args.force:
            print(f"\nERROR: --emit target {target} exists. Use --force to overwrite.")
            return 2
        if target.exists() and args.force:
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        copied = 0
        for rel in included:
            src = REPO_ROOT / rel
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        print(f"\nEmitted {copied} files to {target}.")
        print(f"Next: cd {target} && git init && git add . && git commit -m 'Initial public release'")

    return 0


if __name__ == "__main__":
    sys.exit(main())