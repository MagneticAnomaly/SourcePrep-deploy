"""
Trace coverage analysis — categorizes filesystem files using the Changeset.

Contains: compute_trace_coverage() function.

Phase 134: simplified to read changeset.json (the pipeline's single source of
truth for what changed) + walker-only file enumeration (no hashing).  The old
per-file hash-compare loop, Path A self-heal, backfill carve-out, and the
backfill lock global have all been removed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pathspec

# Phase 133: prep_engine (Rust PyO3 binding) is required by the walker cutover.
# Defer the import-error to first call so the daemon can boot and serve other
# routes — instead of fast-crashing at module load and triggering the watchdog
# crash-loop guard.  See scripts/daemon_watchdog.sh for the python-picking
# logic that also helps avoid this case.
try:
    import prep_engine
except ImportError as _prep_engine_import_err:
    prep_engine = None  # type: ignore[assignment]
    _prep_engine_import_err_msg = str(_prep_engine_import_err)


def _require_prep_engine() -> None:
    if prep_engine is None:
        raise RuntimeError(
            "prep_engine (Rust PyO3 binding) is not installed in the current "
            "Python interpreter. Install with: "
            "`cd engine && maturin develop --release` (and ensure the daemon "
            "launcher uses the same python). "
            f"Original ImportError: {_prep_engine_import_err_msg}"
        )


from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES, DEFAULT_EXCLUDE_FILE_GLOBS
from prep.services.pipeline.changeset import Changeset, read_changeset

from .utils import _detect_language

logger = logging.getLogger(__name__)


def compute_trace_coverage(
    repo_root: Path,
    index_dir: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    user_exclude_globs: Optional[List[str]] = None,
    max_file_bytes: int = 500_000,
    embedded_paths: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Compute trace coverage using the Changeset as the single source of truth.

    Phase 134 simplification: categorization is set-based against the
    changeset — no per-file hashing, no backfill carve-out, no self-heal.
    Staleness == changeset.modified; untraced == files on disk NOT in
    changeset.all_known().

    Args:
      exclude_globs: default/system patterns — files matching these are silently skipped.
      user_exclude_globs: user-configured patterns — files matching these appear in the
                          'excluded' list so users can see what they manually excluded.
      embedded_paths: set of file paths that are already embedded in the vector index.
                      Used to distinguish 'traced & embedded' from 'pending embedding'.

    Returns dict with:
      - traced: files that are traced, up-to-date, AND embedded
      - pending_embedding: files that are traced and up-to-date but NOT yet embedded
      - untraced: files eligible for trace but not yet traced
      - stale: files that were traced but content has changed (per changeset.modified)
      - excluded: files explicitly excluded by user-configured patterns
      - warnings: list of operator-visible warning strings
      - summary: {total, traced, pending_embedding, untraced, stale, excluded, coverage_pct,
                  last_build_at, edge_counts}
    """
    repo_root = Path(repo_root).resolve()

    if embedded_paths is None:
        embedded_paths = set()

    if include_globs is None:
        include_globs = [
            "**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
            "**/*.go", "**/*.rs", "**/*.java",
            "**/*.c", "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp",
            "**/*.swift",
            "**/*.md", "**/*.markdown",
        ]
    if exclude_globs is None:
        # Base excludes
        exclude_globs = [f"**/{d}/**" for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES)]
        # Add specific file patterns
        exclude_globs.extend([
            "**/*.lock",
            "**/*.log",
            "**/.DS_Store",
        ])
    else:
        # User-provided exclude_globs — make a mutable copy
        exclude_globs = list(exclude_globs)
    # Phase 89: Always include system-level file exclusions (e.g. AGENTS.md).
    # These are Prep-generated files that should never appear as "untraced".
    # Previously only added when exclude_globs was None, causing AGENTS.md
    # files to show as permanently untraced when project had custom excludes.
    for pattern in DEFAULT_EXCLUDE_FILE_GLOBS:
        if pattern not in exclude_globs:
            exclude_globs.append(pattern)
    # Phase 133 follow-up (2026-05-12): Always merge DEFAULT_EXCLUDE_DIR_NAMES
    # as a system-level baseline. Pre-Phase-133, os.walk + a `not
    # name.startswith(".")` filter implicitly excluded every dot-dir; the
    # Rust walker's `hidden(false)` strategy lets dot-dirs through unless
    # exclude_globs catches them. A project with custom exclude_globs that
    # doesn't list `.claude/**` / `.agents/**` / `.cursor/**` would otherwise
    # leak agent-instruction dirs into the trace queue. Treat the dir
    # catalog the same way Phase 89 treats DEFAULT_EXCLUDE_FILE_GLOBS:
    # always merged, user config extends rather than overrides.
    for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
        pattern = f"**/{d}/**"
        if pattern not in exclude_globs:
            exclude_globs.append(pattern)
    if user_exclude_globs is None:
        user_exclude_globs = []

    # Phase 134: read the changeset — the single source of truth for what
    # changed in the last pipeline run.  Falls back to an empty Changeset
    # when no changeset.json exists yet (first build, pre-134 daemon, etc.)
    # — in that case all walker-returned files appear as "untraced" until
    # the first pipeline run completes and writes changeset.json.
    cs: Optional[Changeset] = read_changeset(Path(index_dir))
    all_known: frozenset[str] = cs.all_known() if cs is not None else frozenset()
    stale_set: frozenset[str] = cs.modified if cs is not None else frozenset()

    # Minimal manifest read — only for last_build_at in summary.
    manifest_built_at: Optional[str] = None
    manifest_path = Path(index_dir) / "trace_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as _mf:
                _m = json.load(_mf)
            manifest_built_at = _m.get("built_at") or _m.get("finished_at")
        except Exception:
            pass

    traced_files: List[Dict[str, Any]] = []
    untraced_files: List[Dict[str, Any]] = []
    stale_files: List[Dict[str, Any]] = []
    excluded_files: List[Dict[str, Any]] = []

    # Phase 133/134: discovery via the Rust walker. Walker honors gitignore
    # (root + nested + global + git_exclude) and applies include/exclude globs
    # via globset/gitwildmatch.
    _require_prep_engine()
    entries = prep_engine.walk_repo(
        str(repo_root),
        include_globs=list(include_globs) if include_globs else None,
        exclude_globs=list(exclude_globs) if exclude_globs else None,
        max_file_bytes=int(max_file_bytes),
    )

    # Phase 133 divergence #5 surface: walker caps at max_files (100k by
    # default in WalkConfig). When we hit that cap, files past it are
    # silently dropped — surface a WARNING so operators know.
    warnings: List[str] = []
    WALKER_MAX_FILES = 100_000  # mirror engine/crates/prep-walker/src/lib.rs:168
    if len(entries) >= WALKER_MAX_FILES:
        warnings.append(
            f"max_files cap hit: walker returned exactly {len(entries):,} files. "
            f"Files beyond the cap were silently dropped. If your repo legitimately "
            f"has more than {WALKER_MAX_FILES:,} eligible files, raise the cap in "
            f"prep-walker WalkConfig."
        )

    # user_exclude_globs is the user's "shown in Excluded list" surface —
    # applied on top of the walker's output, not as an exclusion to the
    # walker (so the user sees what they manually excluded).
    user_exclude_spec = (
        pathspec.PathSpec.from_lines("gitwildmatch", user_exclude_globs)
        if user_exclude_globs else None
    )

    for entry in entries:
        rel_path = entry.path  # already POSIX, repo-relative per walker contract
        file_path = Path(entry.abs_path)

        # User-excluded surface (shown in 'excluded' list)
        is_user_excluded = bool(
            user_exclude_spec and user_exclude_spec.match_file(rel_path)
        )

        # Stat for timestamps (the walker provides size + modified_secs;
        # use them when possible).
        file_size = int(entry.size)
        modified_ts = (
            datetime.fromtimestamp(entry.modified_secs, tz=timezone.utc).isoformat()
            if entry.modified_secs else "1970-01-01T00:00:00+00:00"
        )
        try:
            _stat = file_path.stat()
            created_ts = (
                datetime.fromtimestamp(_stat.st_birthtime, tz=timezone.utc).isoformat()
                if file_path.exists() and hasattr(_stat, "st_birthtime")
                else modified_ts
            )
        except OSError:
            created_ts = modified_ts

        language = _detect_language(rel_path)

        file_info: Dict[str, Any] = {
            "path": rel_path,
            "language": language,
            "size": file_size,
            "modified": modified_ts,
            "created": created_ts,
        }

        if is_user_excluded:
            excluded_files.append(file_info)
            continue

        # Phase 134 set-based categorization (replaces per-file hash compare):
        #   stale   — changeset says this file was modified in the last run
        #   traced  — changeset knows this file (unchanged or added) → it's indexed
        #   untraced — changeset has no record → not yet indexed
        if rel_path in stale_set:
            stale_files.append(file_info)
        elif rel_path in all_known:
            traced_files.append(file_info)
        else:
            untraced_files.append(file_info)

    # Sort lists by path
    traced_files.sort(key=lambda f: f["path"])
    untraced_files.sort(key=lambda f: f["path"])
    stale_files.sort(key=lambda f: f["path"])
    excluded_files.sort(key=lambda f: f["path"])

    # Split traced files into 'traced' (embedded) and 'pending_embedding' (not embedded)
    final_traced: List[Dict[str, Any]] = []
    pending_embedding: List[Dict[str, Any]] = []

    for f in traced_files:
        if f["path"] in embedded_paths:
            final_traced.append(f)
        else:
            pending_embedding.append(f)

    # Calculate coverage based on effective files (traced + pending + stale)
    # Total eligible files = traced + pending + stale + untraced
    total = len(final_traced) + len(pending_embedding) + len(untraced_files) + len(stale_files)

    # Coverage % is files that have been traced (even if not yet embedded)
    # This keeps the progress bar consistent with "Tracing" status, while the UI
    # distinguishes "Ready" (embedded) vs "In Progress" (pending embedding)
    traced_count_all = len(final_traced) + len(pending_embedding)
    coverage_pct = round(traced_count_all / total * 100, 1) if total > 0 else 0.0

    # Count LSP edges (Phase 39 W1a)
    lsp_edge_count = 0
    lsp_edges_path = Path(index_dir) / "trace_lsp_edges.jsonl"
    if lsp_edges_path.exists():
        try:
            with open(lsp_edges_path, "r", encoding="utf-8") as f:
                lsp_edge_count = sum(1 for line in f if line.strip())
        except OSError:
            pass

    # Count static + inferred edges for comparison
    static_edge_count = 0
    edges_path = Path(index_dir) / "trace_edges.jsonl"
    if edges_path.exists():
        try:
            with open(edges_path, "r", encoding="utf-8") as f:
                static_edge_count = sum(1 for line in f if line.strip())
        except OSError:
            pass

    inferred_edge_count = 0
    inferred_path = Path(index_dir) / "trace_inferred_edges.jsonl"
    if inferred_path.exists():
        try:
            with open(inferred_path, "r", encoding="utf-8") as f:
                inferred_edge_count = sum(1 for line in f if line.strip())
        except OSError:
            pass

    return {
        "traced": final_traced,
        "pending_embedding": pending_embedding,
        "untraced": untraced_files,
        "stale": stale_files,
        "excluded": excluded_files,
        "warnings": warnings,
        "summary": {
            "total": total,
            "traced": len(final_traced),
            "pending_embedding": len(pending_embedding),
            "untraced": len(untraced_files),
            "stale": len(stale_files),
            "excluded": len(excluded_files),
            "coverage_pct": coverage_pct,
            "last_build_at": manifest_built_at,
            "edge_counts": {
                "static": static_edge_count,
                "inferred": inferred_edge_count,
                "lsp": lsp_edge_count,
                "total": static_edge_count + inferred_edge_count + lsp_edge_count,
            },
        },
    }
