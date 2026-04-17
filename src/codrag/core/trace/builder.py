"""
TraceBuilder — orchestrates file scanning and trace graph construction.

Contains: TraceBuilder class and build_trace() convenience function.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pathspec

from codrag.core.ids import (
    stable_edge_id,
    stable_external_module_id,
    stable_file_hash,
    stable_file_node_id,
)
from codrag.core.repo_policy import effective_excludes, ensure_repo_policy
from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES

from .models import (
    FileError,
    TraceNode,
    TraceEdge,
    TRACE_MANIFEST_VERSION,
)
from .utils import _detect_language, _to_posix, _is_relevant
from .analyzers import PythonAnalyzer, SwiftAnalyzer, GenericRegexAnalyzer, JSAnalyzer

logger = logging.getLogger(__name__)

# --- Rust engine availability (set in core/__init__.py) ---
try:
    from codrag.core import ENGINE as _ENGINE, _rust_engine
except ImportError:
    _ENGINE = "python"
    _rust_engine = None


class TraceBuilder:
    """
    Builds trace index files: trace_manifest.json, trace_nodes.jsonl, trace_edges.jsonl.
    """

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        include_globs: Optional[List[str]] = None,
        exclude_globs: Optional[List[str]] = None,
        max_file_bytes: int = 500_000,
        hard_limit_bytes: int = 100_000_000,
        use_gitignore: bool = False,
        max_files: int = 50_000,
        max_nodes: int = 100_000,
        max_edges: int = 500_000,
        max_failures: int = 50,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.index_dir = Path(index_dir).resolve()

        # Fall back to repo_policy.json when callers don't supply globs.
        # effective_excludes() unions L1/L2/L3 (see repo_policy.py), so this
        # is the single place hardcoded filter literals used to live.
        if not include_globs or not exclude_globs:
            policy = ensure_repo_policy(self.index_dir, self.repo_root)
            if not include_globs:
                include_globs = list(policy.get("include_globs") or [])
            if not exclude_globs:
                exclude_globs = effective_excludes(
                    index_dir=self.index_dir,
                    repo_root=self.repo_root,
                )

        # Safety net: if the policy produced no includes (e.g. profile_repo
        # ran on a repo with no detectable source, or TS-vs-JS detection
        # dropped a dialect), fall back to the broad language-agnostic list
        # so we don't silently index zero files. Exclude globs always come
        # from L1+L2+L3 above — no hardcoded exclude fallback here.
        if not include_globs:
            include_globs = [
                "**/*.py",
                "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx",
                "**/*.go",
                "**/*.rs",
                "**/*.java",
                "**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.cc",
                "**/*.swift",
                "**/*.md", "**/*.markdown",
                "**/*.kt", "**/*.kts",
                "**/*.cs",
                "**/*.rb",
                "**/*.php",
                "**/*.dart",
                "**/*.scala", "**/*.sc",
                "**/*.sh", "**/*.bash", "**/*.zsh",
                "**/*.lua",
                "**/*.zig",
                "**/*.ex", "**/*.exs",
            ]

        self.include_globs = include_globs
        self.exclude_globs = exclude_globs
        self.max_file_bytes = max_file_bytes
        self.hard_limit_bytes = hard_limit_bytes
        self.use_gitignore = use_gitignore
        self.max_files = max_files
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.max_failures = max_failures

        self.manifest_path = self.index_dir / "trace_manifest.json"
        self.nodes_path = self.index_dir / "trace_nodes.jsonl"
        self.edges_path = self.index_dir / "trace_edges.jsonl"
        self.gitignore_spec = None

    def _get_analyzer(self, language: Optional[str], rel_path: str, source: str):
        """Return the appropriate analyzer for the given language, or None."""
        if language == "python":
            return PythonAnalyzer(rel_path, source, self.repo_root)
        if language == "swift":
            return SwiftAnalyzer(rel_path, source, self.repo_root)
        if language in ("javascript", "typescript"):
            return JSAnalyzer(rel_path, source, self.repo_root)
        if language in GenericRegexAnalyzer.LANGUAGE_CONFIGS:
            return GenericRegexAnalyzer(rel_path, source, self.repo_root, language)
        return None

    @staticmethod
    def _collect_analyzer_result(
        sym_nodes: List[TraceNode],
        sym_edges: List[TraceEdge],
        nodes: List[TraceNode],
        edges: List[TraceEdge],
        external_modules: Dict[str, TraceNode],
    ) -> None:
        """Merge analyzer output into the shared node/edge lists and register external modules."""
        nodes.extend(sym_nodes)
        for edge in sym_edges:
            if edge.metadata.get("external"):
                ext_name = str(edge.metadata.get("import", ""))
                if ext_name and ext_name not in external_modules:
                    ext_node = TraceNode(
                        id=stable_external_module_id(ext_name),
                        kind="external_module",
                        name=ext_name,
                        file_path="",
                        span=None,
                        language=None,
                        metadata={"external": True},
                    )
                    external_modules[ext_name] = ext_node
        edges.extend(sym_edges)

    def build(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        changed_paths: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        self.index_dir.mkdir(parents=True, exist_ok=True)

        if _ENGINE == "rust" and _rust_engine is not None:
            return self._build_rust(progress_callback)

        # Load .gitignore if requested
        if self.use_gitignore:
            gitignore_path = self.repo_root / ".gitignore"
            if gitignore_path.exists():
                try:
                    with open(gitignore_path, "r", encoding="utf-8") as f:
                        self.gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
                    logger.info("Loaded .gitignore from %s", gitignore_path)
                except Exception as e:
                    logger.warning("Failed to parse .gitignore: %s", e)

        files = self._enumerate_files()
        if len(files) > self.max_files:
            logger.warning(f"File count {len(files)} exceeds max_files {self.max_files}, truncating")
            files = files[: self.max_files]

        nodes: List[TraceNode] = []
        edges: List[TraceEdge] = []
        external_modules: Dict[str, TraceNode] = {}
        file_errors: List[FileError] = []
        file_hashes: Dict[str, str] = {}  # rel_path -> content hash
        files_parsed = 0
        files_failed = 0

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback("trace_scan", i, len(files))

            rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))

            # Read source and compute content hash for staleness detection
            try:
                # Check size for parsing decision
                file_size = file_path.stat().st_size
                is_large = file_size > self.max_file_bytes
                
                if is_large:
                     # For large files, we skip reading full content for hash/parsing
                     # Just hash the path + size + mtime as a proxy? 
                     # Or read a prefix. Let's read prefix for consistency with index.py
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read(50_000)
                else:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                source = ""
            
            file_hashes[rel_path] = stable_file_hash(source)

            file_node = TraceNode(
                id=stable_file_node_id(rel_path),
                kind="file",
                name=file_path.name,
                file_path=rel_path,
                span=None,
                language=_detect_language(rel_path),
                metadata={"truncated": is_large, "size": file_size} if 'file_size' in locals() else {},
            )
            nodes.append(file_node)

            if is_large:
                # Skip parsing for large files
                continue

            language = _detect_language(rel_path)
            analyzer = self._get_analyzer(language, rel_path, source)
            if analyzer is not None:
                try:
                    sym_nodes, sym_edges = analyzer.analyze()
                    self._collect_analyzer_result(
                        sym_nodes, sym_edges, nodes, edges, external_modules,
                    )
                    files_parsed += 1
                except Exception as e:
                    files_failed += 1
                    if len(file_errors) < self.max_failures:
                        file_errors.append(FileError(rel_path, type(e).__name__, str(e)))
            else:
                files_parsed += 1

            if len(nodes) > self.max_nodes:
                logger.warning(f"Node count exceeds max_nodes {self.max_nodes}, stopping")
                break
            if len(edges) > self.max_edges:
                logger.warning(f"Edge count exceeds max_edges {self.max_edges}, stopping")
                break

        nodes.extend(external_modules.values())

        # Sanitization: Filter out invalid nodes AND edges
        valid_nodes = []
        node_ids = set()
        
        for n in nodes:
            if n.id in node_ids:
                logger.warning(f"Dropping duplicate node ID: {n.id}")
                continue
            if n.file_path and (n.file_path.startswith("/") or "\\" in n.file_path):
                logger.warning(f"Dropping node with non-portable path: {n.id} ({n.file_path})")
                continue
            
            node_ids.add(n.id)
            valid_nodes.append(n)
            
        nodes = valid_nodes

        valid_edges = []
        edge_ids = set()
        
        for e in edges:
            if e.id in edge_ids:
                continue # Skip duplicate edge IDs silently
            
            if e.source not in node_ids:
                logger.warning(f"Dropping edge {e.id}: source {e.source} not found")
                continue
            if e.target not in node_ids:
                logger.warning(f"Dropping edge {e.id}: target {e.target} not found")
                continue
                
            edge_ids.add(e.id)
            valid_edges.append(e)
            
        edges = valid_edges

        # Final validation check (should pass now)
        valid, validation_error = self._validate(nodes, edges)
        if not valid:
             # This should ideally not happen after sanitization, but if it does, 
             # we still try to write what we have or just log error.
             # Given we just sanitized, let's trust our sanitization and only log if it still fails.
             logger.error(f"Trace validation failed after sanitization: {validation_error}")
             # Proceed anyway? No, if it still fails, something is structurally wrong.
             # But let's try to write at least the manifest with last_error.
             manifest = self._build_manifest(
                nodes_count=0,
                edges_count=0,
                files_parsed=files_parsed,
                files_failed=files_failed,
                file_errors=file_errors,
                last_error=validation_error,
                file_hashes=file_hashes,
            )
             self._write_manifest(manifest)
             return manifest

        # Phase 60C: Content-hash comparison — if the file set hasn't
        # changed, skip the destructive write to preserve the existing
        # manifest mtime and prevent false STALE_MTIME cascade.
        skip_write = False
        if self.manifest_path.exists():
            try:
                import json as _json
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    existing_manifest = _json.load(f)
                existing_hashes = existing_manifest.get("file_hashes", {})
                existing_counts = existing_manifest.get("counts", {})

                if (existing_hashes
                        and existing_hashes == file_hashes
                        and existing_counts.get("nodes", 0) == len(nodes)
                        and existing_counts.get("edges", 0) == len(edges)):
                    skip_write = True
                    logger.info(
                        "Structural trace unchanged (%d nodes, %d edges, "
                        "%d file hashes identical) — skipping write to "
                        "preserve manifest mtime",
                        len(nodes), len(edges), len(file_hashes),
                    )
            except Exception:
                pass  # Can't read existing manifest — write anyway

        if skip_write:
            # Return the existing manifest without updating its mtime
            manifest = existing_manifest
        else:
            self._write_atomic(nodes, edges)

            manifest = self._build_manifest(
                nodes_count=len(nodes),
                edges_count=len(edges),
                files_parsed=files_parsed,
                files_failed=files_failed,
                file_errors=file_errors,
                last_error=None,
                file_hashes=file_hashes,
            )
            self._write_manifest(manifest)

        if progress_callback:
            progress_callback("trace_write", len(files), len(files))

        return manifest

    def _build_rust(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Delegate trace build to the Rust engine via codrag_engine."""
        import time

        logger.info("Building trace index via Rust engine")
        start = time.monotonic()

        # Preserve existing file_hashes before Rust overwrites the manifest.
        # The Rust engine writes a minimal manifest without file_hashes,
        # which causes IntegrityGuard to flag a catastrophic shrink
        # (e.g. 95KB → 304B).
        saved_file_hashes: Optional[Dict[str, str]] = None
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    old_manifest = json.load(f)
                saved_file_hashes = old_manifest.get("file_hashes")
                if saved_file_hashes:
                    logger.info("Preserved %d file_hashes before Rust engine build", len(saved_file_hashes))
            except Exception:
                pass

        if progress_callback:
            # Emit a "running" state so the UI knows it hasn't stalled
            progress_callback("trace_scan", 0, 1)

        try:
            # Note: _rust_engine.build_trace blocks until the build is complete.
            # To get real-time progress we would need the rust engine to accept a callback,
            # but for now we log that it is actively running.
            handle = _rust_engine.build_trace(
                str(self.repo_root),
                str(self.index_dir),
                include_globs=self.include_globs,
                exclude_globs=self.exclude_globs,
                max_file_bytes=self.max_file_bytes,
            )
        except Exception as e:
            logger.error(f"Rust engine build failed: {e}")
            manifest = self._build_manifest(
                nodes_count=0,
                edges_count=0,
                files_parsed=0,
                files_failed=0,
                file_errors=[],
                last_error=str(e),
            )
            self._write_manifest(manifest)
            return manifest

        elapsed = time.monotonic() - start
        status = handle.status()
        counts = status.get("counts", {})

        logger.info(
            "Rust engine build complete: %d nodes, %d edges in %.3fs",
            counts.get("nodes", 0),
            counts.get("edges", 0),
            elapsed,
        )

        if progress_callback:
            progress_callback("trace_write", 1, 1)

        # Read the manifest the Rust engine wrote
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {
                "version": TRACE_MANIFEST_VERSION,
                "built_at": status.get("last_build_at", ""),
                "project": {"repo_root": str(self.repo_root)},
                "counts": counts,
                "file_errors": [],
                "last_error": None,
            }

        # Rust engine doesn't write file_hashes — compute them in Python
        # so that compute_trace_coverage can determine traced/untraced/stale.
        if "file_hashes" not in manifest:
            logger.info("Computing file_hashes for Rust-built trace manifest")
            new_hashes = self._compute_file_hashes()
            if saved_file_hashes:
                # Merge: start with preserved hashes, overlay with freshly computed
                merged = dict(saved_file_hashes)
                merged.update(new_hashes)
                manifest["file_hashes"] = merged
                logger.info("Merged %d preserved + %d new = %d file_hashes",
                            len(saved_file_hashes), len(new_hashes), len(merged))
            else:
                manifest["file_hashes"] = new_hashes
            self._write_manifest(manifest)

        return manifest

    _PRUNE_DIRS = DEFAULT_EXCLUDE_DIR_NAMES

    def _compute_file_hashes(self) -> Dict[str, str]:
        """Compute content hashes for all eligible files (used to backfill Rust manifests)."""
        files = self._enumerate_files()
        file_hashes: Dict[str, str] = {}
        for file_path in files:
            rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))
            try:
                file_size = file_path.stat().st_size
                if file_size > self.max_file_bytes:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read(50_000)
                else:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                source = ""
            file_hashes[rel_path] = stable_file_hash(source)
        return file_hashes

    def _enumerate_files(self) -> List[Path]:
        all_files: List[Path] = []

        for root, dirs, files in os.walk(self.repo_root):
            # Prune dot-directories and explicit exclude dirs
            dirs[:] = [
                d for d in dirs 
                if d not in self._PRUNE_DIRS and not d.startswith(".")
            ]
            root_path = Path(root)
            for fname in files:
                file_path = root_path / fname
                rel_path = _to_posix(str(file_path.relative_to(self.repo_root)))

                if file_path.is_symlink():
                    continue

                if not _is_relevant(rel_path, self.include_globs, self.exclude_globs):
                    continue

                if self.gitignore_spec and self.gitignore_spec.match_file(rel_path):
                    continue

                try:
                    if file_path.stat().st_size > self.hard_limit_bytes:
                        continue
                except OSError:
                    continue

                all_files.append(file_path)

        all_files.sort(key=lambda p: _to_posix(str(p.relative_to(self.repo_root))))
        return all_files

    def _validate(self, nodes: List[TraceNode], edges: List[TraceEdge]) -> Tuple[bool, Optional[str]]:
        node_ids: Set[str] = set()
        for n in nodes:
            if n.id in node_ids:
                return False, f"Duplicate node ID: {n.id}"
            node_ids.add(n.id)

            if n.file_path and (n.file_path.startswith("/") or "\\" in n.file_path):
                return False, f"Non-portable file_path in node {n.id}: {n.file_path}"

        edge_ids: Set[str] = set()
        for e in edges:
            if e.id in edge_ids:
                return False, f"Duplicate edge ID: {e.id}"
            edge_ids.add(e.id)

            if e.source not in node_ids:
                return False, f"Edge {e.id} references unknown source: {e.source}"
            if e.target not in node_ids:
                return False, f"Edge {e.id} references unknown target: {e.target}"

        return True, None

    def _sort_nodes(self, nodes: List[TraceNode]) -> List[TraceNode]:
        def sort_key(n: TraceNode) -> Tuple[int, str, int, str]:
            kind_order = {"file": 0, "symbol": 1, "external_module": 2}
            start_line = (n.span or {}).get("start_line", 0)
            return (kind_order.get(n.kind, 99), n.file_path, start_line, n.name)

        return sorted(nodes, key=sort_key)

    def _sort_edges(self, edges: List[TraceEdge]) -> List[TraceEdge]:
        def sort_key(e: TraceEdge) -> Tuple[str, str, str, str]:
            return (e.kind, e.source, e.target, e.id)

        return sorted(edges, key=sort_key)

    def _write_atomic(self, nodes: List[TraceNode], edges: List[TraceEdge]) -> None:
        sorted_nodes = self._sort_nodes(nodes)
        sorted_edges = self._sort_edges(edges)

        tmp_nodes = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            for n in sorted_nodes:
                tmp_nodes.write(json.dumps(n.to_dict(), sort_keys=True) + "\n")
            tmp_nodes.flush()
            os.fsync(tmp_nodes.fileno())
            tmp_nodes.close()
            os.rename(tmp_nodes.name, self.nodes_path)
        except Exception:
            try:
                os.unlink(tmp_nodes.name)
            except OSError:
                pass
            raise

        tmp_edges = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            for e in sorted_edges:
                tmp_edges.write(json.dumps(e.to_dict(), sort_keys=True) + "\n")
            tmp_edges.flush()
            os.fsync(tmp_edges.fileno())
            tmp_edges.close()
            os.rename(tmp_edges.name, self.edges_path)
        except Exception:
            try:
                os.unlink(tmp_edges.name)
            except OSError:
                pass
            raise

    def _build_manifest(
        self,
        nodes_count: int,
        edges_count: int,
        files_parsed: int,
        files_failed: int,
        file_errors: List[FileError],
        last_error: Optional[str],
        file_hashes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {
            "version": TRACE_MANIFEST_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "repo_root": str(self.repo_root),
            },
            "config": {
                "include_globs": self.include_globs,
                "exclude_globs": self.exclude_globs,
                "max_file_bytes": self.max_file_bytes,
            },
            "counts": {
                "nodes": nodes_count,
                "edges": edges_count,
                "files_parsed": files_parsed,
                "files_failed": files_failed,
            },
            "file_errors": [{"file_path": e.file_path, "error_type": e.error_type, "message": e.message} for e in file_errors],
            "last_error": last_error,
        }
        if file_hashes is not None:
            manifest["file_hashes"] = file_hashes
        return manifest

    def _write_manifest(self, manifest: Dict[str, Any]) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir, delete=False, encoding="utf-8"
        )
        try:
            json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.manifest_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise


def build_trace(
    repo_root: Path,
    index_dir: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    max_file_bytes: int = 500_000,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to build trace index.
    """
    builder = TraceBuilder(
        repo_root=repo_root,
        index_dir=index_dir,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        max_file_bytes=max_file_bytes,
    )
    return builder.build(progress_callback=progress_callback)
