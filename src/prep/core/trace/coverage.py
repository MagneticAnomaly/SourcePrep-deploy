"""
Trace coverage analysis — compares filesystem against trace manifest.

Contains: compute_trace_coverage() function.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pathspec
import prep_engine

from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES, DEFAULT_EXCLUDE_FILE_GLOBS

from .utils import _detect_language

logger = logging.getLogger(__name__)

# Prevent concurrent backfill writes from clobbering each other
_backfill_lock = threading.Lock()


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
    # Phase 133: hash algorithm mirroring engine/crates/prep-walker/src/lib.rs:168
    # This constant must match prep.core.manifest.CURRENT_HASH_ALGO to avoid circular import
    CURRENT_HASH_ALGO = "blake3-128"

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
                        # Compute hashes for the missing files
                        new_hashes: Dict[str, str] = {}
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
                            new_hashes[rel_path] = prep_engine.hash_content(source)

                        # Persist with lock to avoid clobbering concurrent
                        # writes (e.g. TraceBuilder._compute_file_hashes
                        # writing a more complete set at the same time).
                        if not _backfill_lock.acquire(blocking=False):
                            # Another backfill is already writing — skip.
                            # Our in-memory manifest_hashes still has the
                            # new entries so this call's coverage calc is
                            # correct; the next call will persist if needed.
                            manifest_hashes.update(new_hashes)
                            logger.info(
                                "Backfill skipped write (another writer active) — "
                                "%d hashes computed in-memory only",
                                len(new_hashes),
                            )
                        else:
                            try:
                                # Re-read manifest to merge with any hashes
                                # the builder wrote since our initial read.
                                try:
                                    with open(manifest_path, "r", encoding="utf-8") as rf:
                                        fresh_manifest = json.load(rf)
                                    fresh_hashes = fresh_manifest.get("file_hashes") or {}
                                except Exception:
                                    fresh_manifest = manifest
                                    fresh_hashes = manifest_hashes

                                # Merge: start with fresh on-disk hashes,
                                # overlay our new backfill entries.
                                merged_hashes = dict(fresh_hashes)
                                merged_hashes.update(new_hashes)
                                fresh_manifest["file_hashes"] = merged_hashes

                                # Update our in-memory view too
                                manifest_hashes.update(fresh_hashes)
                                manifest_hashes.update(new_hashes)

                                tmp_manifest = tempfile.NamedTemporaryFile(
                                    mode="w", suffix=".json", dir=str(Path(index_dir)),
                                    delete=False, encoding="utf-8",
                                )
                                try:
                                    json.dump(fresh_manifest, tmp_manifest, indent=2, sort_keys=True)
                                    tmp_manifest.flush()
                                    os.fsync(tmp_manifest.fileno())
                                    tmp_manifest.close()
                                    os.rename(tmp_manifest.name, manifest_path)
                                    logger.info(
                                        "Backfilled %d file_hashes into manifest (total: %d)",
                                        len(new_hashes), len(merged_hashes),
                                    )
                                except Exception:
                                    try:
                                        os.unlink(tmp_manifest.name)
                                    except OSError:
                                        pass
                            finally:
                                _backfill_lock.release()
                except Exception as e:
                    logger.warning("file_hashes backfill failed: %s", e)
        except Exception:
            pass

    # Phase 133: detect hash format mismatch for Migration Path A self-heal.
    # Pre-cutover manifests have no hash_algo field (default "sha256-64") or
    # carry it explicitly. Post-cutover manifests carry "blake3-128".
    # On mismatch, the per-file hash compare branches below skip computing the
    # current hash and mark every previously-hashed file stale unconditionally.
    # The next structural rebuild rewrites the manifest with CURRENT_HASH_ALGO,
    # after which hash_algo_mismatch becomes False and hash compare resumes.
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as _mf:
                _m = json.load(_mf)
            manifest_hash_algo = _m.get("hash_algo") or "sha256-64"
        except Exception:
            manifest_hash_algo = "sha256-64"
    else:
        manifest_hash_algo = None  # No manifest → no mismatch to self-heal
    hash_algo_mismatch = manifest_hash_algo is not None and manifest_hash_algo != CURRENT_HASH_ALGO

    traced_files: List[Dict[str, Any]] = []
    untraced_files: List[Dict[str, Any]] = []
    stale_files: List[Dict[str, Any]] = []
    excluded_files: List[Dict[str, Any]] = []

    # Phase 133: discovery via the Rust walker. Replaces the previous
    # os.walk + fnmatch implementation (which diverged from the Rust
    # walker on six surfaces; see Phase 133 spec). User-configurable
    # excludes still go through the same exclude_globs argument; the
    # Rust walker honors gitignore (root + nested + global + git_exclude)
    # and applies include/exclude globs via globset/gitwildmatch.
    entries = prep_engine.walk_repo(
        str(repo_root),
        include_globs=list(include_globs) if include_globs else None,
        exclude_globs=list(exclude_globs) if exclude_globs else None,
        max_file_bytes=int(max_file_bytes),
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

        # Hash-compare branch (existing logic — KEEP unchanged in this task;
        # Task 4 swaps the hash function and adds the hash_algo self-heal).
        prev_hash = manifest_hashes.get(rel_path)
        if prev_hash is None:
            # Even if the file doesn't match current include_globs natively,
            # count it if it's already in the trace manifest (the trace builder
            # found it). The walker may not return it because include_globs are
            # narrower than the trace builder's scope; the backfill pass below
            # handles those manifest-only paths. For walker-returned paths, if
            # prev_hash is None, the file is simply untraced.
            untraced_files.append(file_info)
        else:
            # Was traced — check if stale.
            if hash_algo_mismatch:
                # Phase 133 self-heal: manifest was written with a different hash
                # algo. Skip computing the current hash; mark stale unconditionally
                # so the next structural rebuild rewrites the manifest with
                # CURRENT_HASH_ALGO (blake3-128), after which subsequent calls
                # compare normally.
                stale_files.append(file_info)
                continue

            # Fast path: if file mtime is older than the manifest build time,
            # the file hasn't changed since we last traced it → skip the
            # expensive hash computation. Only re-hash files that were
            # modified after the manifest was written.
            needs_hash = True
            if manifest_built_at_ts is not None:
                try:
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < manifest_built_at_ts:
                        needs_hash = False
                except Exception:
                    pass  # Fall through to hash

            if needs_hash:
                try:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
                    current_hash = prep_engine.hash_content(source)
                except Exception:
                    current_hash = ""

                if current_hash != prev_hash:
                    stale_files.append(file_info)
                else:
                    traced_files.append(file_info)
            else:
                # mtime hasn't changed since build → still fresh
                traced_files.append(file_info)

    # Backfill carve-out pass: any file in manifest_hashes that the
    # walker didn't return AND that still exists on disk goes through
    # the same hash compare. Preserves the prior behavior where files
    # already in the trace manifest (the trace builder may have had
    # slightly broader scope than current include_globs) still appear
    # in coverage output rather than silently disappearing.
    walker_paths = {e.path for e in entries}
    for rel_path in set(manifest_hashes.keys()) - walker_paths:
        abs_p = Path(repo_root) / rel_path
        if not abs_p.exists():
            continue
        try:
            _bstat = abs_p.stat()
            file_size = _bstat.st_size
            if file_size > max_file_bytes:
                continue  # too big, skip same as walker would
            modified_ts = datetime.fromtimestamp(_bstat.st_mtime, tz=timezone.utc).isoformat()
            try:
                created_ts = (
                    datetime.fromtimestamp(_bstat.st_birthtime, tz=timezone.utc).isoformat()
                    if hasattr(_bstat, "st_birthtime")
                    else modified_ts
                )
            except Exception:
                created_ts = modified_ts
        except OSError:
            continue
        file_info = {
            "path": rel_path,
            "language": _detect_language(rel_path),
            "size": file_size,
            "modified": modified_ts,
            "created": created_ts,
        }
        # Run the same hash compare for backfilled paths. prev_hash is
        # always non-None here by definition (came from manifest_hashes).
        prev_hash = manifest_hashes[rel_path]

        if hash_algo_mismatch:
            # Phase 133 self-heal: same short-circuit as the main loop.
            stale_files.append(file_info)
            continue

        needs_hash = True
        if manifest_built_at_ts is not None:
            try:
                file_mtime = abs_p.stat().st_mtime
                if file_mtime < manifest_built_at_ts:
                    needs_hash = False
            except Exception:
                pass
        if needs_hash:
            try:
                source = abs_p.read_text(encoding="utf-8", errors="ignore")
                current_hash = prep_engine.hash_content(source)
            except Exception:
                current_hash = ""
            if current_hash != prev_hash:
                stale_files.append(file_info)
            else:
                traced_files.append(file_info)
        else:
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
