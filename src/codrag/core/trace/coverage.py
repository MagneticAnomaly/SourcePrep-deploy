"""
Trace coverage analysis — compares filesystem against trace manifest.

Contains: compute_trace_coverage() function.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pathspec

from codrag.core.ids import stable_file_hash
from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES, DEFAULT_EXCLUDE_FILE_GLOBS

from .utils import _detect_language, _to_posix

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
    Compute trace coverage by comparing current filesystem against trace manifest.

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
      - stale: files that were traced but content has changed
      - excluded: files explicitly excluded by user-configured patterns
      - summary: {total, traced, pending_embedding, untraced, stale, excluded, coverage_pct}
    """
    repo_root = Path(repo_root).resolve()
    
    if embedded_paths is None:
        embedded_paths = set()

    # Load .gitignore to ensure coverage aligns identically with TraceBuilder
    gitignore_spec = None
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
        except Exception as e:
            logger.warning("Failed to parse .gitignore during coverage check: %s", e)

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
        exclude_globs.extend(DEFAULT_EXCLUDE_FILE_GLOBS)
    if user_exclude_globs is None:
        user_exclude_globs = []

    # Load trace manifest file_hashes (if exists)
    manifest_path = Path(index_dir) / "trace_manifest.json"
    nodes_path = Path(index_dir) / "trace_nodes.jsonl"
    manifest_hashes: Dict[str, str] = {}
    manifest_built_at: Optional[str] = None
    manifest_built_at_ts: Optional[float] = None  # Unix epoch seconds for mtime comparison
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest_hashes = manifest.get("file_hashes") or {}
            manifest_built_at = manifest.get("built_at") or manifest.get("finished_at")
            # Parse ISO timestamp to Unix epoch for fast mtime comparison
            if manifest_built_at:
                try:
                    manifest_built_at_ts = datetime.fromisoformat(manifest_built_at).timestamp()
                except (ValueError, TypeError):
                    pass

            # Backfill: ensure file_hashes includes ALL files from trace_nodes.jsonl.
            # The Rust engine discovers files that the Python augmenter may not have
            # hashed (structural-only nodes). Without this, those files appear as
            # "Untraced" in the queue even though they're in the knowledge graph.
            # This runs when hashes are empty OR when trace_nodes has entries
            # missing from the existing hashes.
            if nodes_path.exists() and nodes_path.stat().st_size > 0:
                try:
                    traced_paths: List[str] = []
                    with open(nodes_path, "r", encoding="utf-8") as nf:
                        for line in nf:
                            line = line.strip()
                            if not line:
                                continue
                            node = json.loads(line)
                            if node.get("kind") == "file":
                                fp = node.get("file_path", "")
                                if fp and fp not in manifest_hashes:
                                    traced_paths.append(fp)

                    if traced_paths:
                        logger.info(
                            "Backfilling %d file_hashes from traced nodes "
                            "(Rust engine files not in manifest)",
                            len(traced_paths),
                        )
                        for rel_path in traced_paths:
                            full = repo_root / rel_path
                            if not full.exists():
                                continue
                            try:
                                fsize = full.stat().st_size
                                if fsize > max_file_bytes:
                                    with open(full, "r", encoding="utf-8", errors="ignore") as hf:
                                        source = hf.read(50_000)
                                else:
                                    source = full.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                source = ""
                            manifest_hashes[rel_path] = stable_file_hash(source)

                        # Persist so this backfill only runs once per new file set
                        manifest["file_hashes"] = manifest_hashes
                        tmp_manifest = tempfile.NamedTemporaryFile(
                            mode="w", suffix=".json", dir=str(Path(index_dir)),
                            delete=False, encoding="utf-8",
                        )
                        try:
                            json.dump(manifest, tmp_manifest, indent=2, sort_keys=True)
                            tmp_manifest.flush()
                            os.fsync(tmp_manifest.fileno())
                            tmp_manifest.close()
                            os.rename(tmp_manifest.name, manifest_path)
                            logger.info("Backfilled %d file_hashes into manifest (total: %d)", len(traced_paths), len(manifest_hashes))
                        except Exception:
                            try:
                                os.unlink(tmp_manifest.name)
                            except OSError:
                                pass
                except Exception as e:
                    logger.warning("file_hashes backfill failed: %s", e)
        except Exception:
            pass

    # Directories to always prune from os.walk — these are never interesting
    # and can contain tens of thousands of files (e.g. node_modules).
    _PRUNE_DIRS = DEFAULT_EXCLUDE_DIR_NAMES

    traced_files: List[Dict[str, Any]] = []
    untraced_files: List[Dict[str, Any]] = []
    stale_files: List[Dict[str, Any]] = []
    excluded_files: List[Dict[str, Any]] = []

    for root_dir, dirs, filenames in os.walk(repo_root):
        # Prune noisy directories in-place so os.walk never descends into them
        dirs[:] = [d for d in dirs if d not in _PRUNE_DIRS and not d.startswith(".")]
        root_path = Path(root_dir)
        for fname in filenames:
            file_path = root_path / fname
            if file_path.is_symlink():
                continue

            rel_path = _to_posix(str(file_path.relative_to(repo_root)))

            # Phase 67: Ignore files matching .gitignore identically to TraceBuilder
            if gitignore_spec and gitignore_spec.match_file(rel_path):
                continue

            # Check if file matches include globs at all (only code files)
            base = os.path.basename(rel_path)
            matches_any_include = False
            if not include_globs:
                matches_any_include = True
            else:
                for g in include_globs:
                    patterns = [g]
                    if g.startswith("**/"):
                        patterns.append(g[3:])
                    for p in patterns:
                        if fnmatch(rel_path, p) or fnmatch(base, p):
                            matches_any_include = True
                            break
                    if matches_any_include:
                        break

            if not matches_any_include:
                # Even if the file doesn't match current include_globs, count it
                # if it's already in the trace manifest (the trace builder found it).
                # This prevents misleading coverage when config globs are narrower
                # than the trace builder's own file discovery.
                if rel_path not in manifest_hashes:
                    continue

            # Check if excluded by default/system patterns (silently skip)
            is_default_excluded = False
            for g in exclude_globs:
                patterns = [g]
                if g.startswith("**/"):
                    patterns.append(g[3:])
                for p in patterns:
                    if fnmatch(rel_path, p) or fnmatch(base, p):
                        is_default_excluded = True
                        break
                if is_default_excluded:
                    break

            if is_default_excluded:
                continue

            # Check if excluded by user-configured patterns (show in 'excluded' list)
            is_user_excluded = False
            for g in user_exclude_globs:
                patterns = [g]
                if g.startswith("**/"):
                    patterns.append(g[3:])
                for p in patterns:
                    if fnmatch(rel_path, p) or fnmatch(base, p):
                        is_user_excluded = True
                        break
                if is_user_excluded:
                    break

            # Get file stat for timestamps
            try:
                stat = file_path.stat()
                file_size = stat.st_size
                modified_ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                created_ts = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc).isoformat() if hasattr(stat, 'st_birthtime') else modified_ts
            except OSError:
                continue

            if file_size > max_file_bytes:
                continue

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

            # Compare against manifest hashes
            prev_hash = manifest_hashes.get(rel_path)
            if prev_hash is None:
                # Not in trace manifest → untraced
                untraced_files.append(file_info)
            else:
                # Was traced — check if stale.
                # Fast path: if file mtime is older than the manifest build time,
                # the file hasn't changed since we last traced it → skip the
                # expensive hash computation.  Only re-hash files that were
                # modified after the manifest was written.
                needs_hash = True
                if manifest_built_at_ts is not None:
                    try:
                        file_mtime = stat.st_mtime
                        if file_mtime < manifest_built_at_ts:
                            needs_hash = False
                    except Exception:
                        pass  # Fall through to hash

                if needs_hash:
                    try:
                        source = file_path.read_text(encoding="utf-8", errors="ignore")
                        current_hash = stable_file_hash(source)
                    except Exception:
                        current_hash = ""

                    if current_hash != prev_hash:
                        stale_files.append(file_info)
                    else:
                        traced_files.append(file_info)
                else:
                    # mtime hasn't changed since build → still fresh
                    traced_files.append(file_info)

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
