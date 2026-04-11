"""
CoDRAG Build Manager Service — Phase 23 Sprint 14
====================================================

**Origin:** Extracted from ``server.py`` globals (lines ~134–158) and helper
functions (lines ~839–1218).

**What this encapsulates:**
  - Per-project index caches: CodeIndex, TraceIndex, KnowledgeIndex
  - Build thread pools with locks for: index, trace, knowledge
  - Build result/error tracking
  - Embedder creation logic (priority: project override → dashboard config → CLI → native)
  - Legacy singleton index/trace for deprecated endpoints

**What stays in server.py (for now):**
  - ``_config`` dict (CLI launch params)
  - ``_registry`` (ProjectRegistry singleton)
  - ``_watcher`` / ``_project_watchers`` (file watchers)
  - ``_load_ui_config`` / ``_save_ui_config`` (config persistence)
  - ``_DEFAULT_UI_CONFIG`` (config defaults)

**Phase 24 note (State Machines SM-4, SM-6):**
  SM-4 (Build Orchestrator) will replace this class with a proper state
  machine.  Each project will have a ``BuildSlot`` with explicit phases:
  IDLE → QUEUED → BUILDING → DONE/FAILED.  The current ``is_building()``
  check-and-start pattern will become a guarded transition.

  SM-6 (Pipeline Orchestrator) will extend the trace/knowledge build
  methods with a STAGE_DEPS DAG, so e.g. knowledge build auto-waits
  for trace build completion.

  The ``_create_embedder`` logic will eventually move into a dedicated
  EmbedderFactory that reads from SM-7 (License) to gate native vs
  cloud embedders based on tier.

**Usage from server.py / routers:**
  Import the singleton: ``from codrag.services.build_manager import build_manager``
  Then call: ``build_manager.get_project_index(project)``, etc.

  During the transition, server.py also exposes module-level aliases
  (``_get_project_index``, ``_is_project_building``, etc.) that delegate
  to the singleton, so existing ``from codrag.server import ...`` in
  routers continues to work without changes.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.core import CodeIndex, KnowledgeIndex
from codrag.core.events import get_progress_manager
from codrag.core.project_registry import Project, project_index_dir
from codrag.core.trace import TraceBuilder, TraceIndex

logger = logging.getLogger(__name__)


class BuildManager:
    """Manages index caches, build threads, and locks for all project types.

    Thread-safe.  One instance per daemon process (singleton pattern).
    """

    def __init__(self) -> None:
        # ── Legacy singleton (deprecated endpoints) ──────────────
        self.legacy_index: Optional[CodeIndex] = None
        self.legacy_trace_index: Optional[TraceIndex] = None

        # ── Per-project caches ───────────────────────────────────
        self.project_indexes: Dict[str, CodeIndex] = {}
        self.project_trace_indexes: Dict[str, TraceIndex] = {}
        self.project_knowledge_indexes: Dict[str, KnowledgeIndex] = {}
        self._layered_indexes: Dict[str, Any] = {}  # Dict[str, LayeredCodeIndex]

        # ── Index build threading ────────────────────────────────
        self.build_lock = threading.Lock()
        self.build_threads: Dict[str, threading.Thread] = {}
        self.last_build_result: Dict[str, Dict[str, Any]] = {}
        self.last_build_error: Dict[str, str] = {}

        # ── Trace build threading ────────────────────────────────
        self.trace_build_lock = threading.Lock()
        self.trace_build_threads: Dict[str, threading.Thread] = {}

        # ── Knowledge build threading ────────────────────────────────
        self.knowledge_build_lock = threading.Lock()
        self.knowledge_build_threads: Dict[str, threading.Thread] = {}

        # ── Embedding serialization (DEPRECATED) ──────────────────────
        # Previously, all embedding operations acquired this lock so they
        # ran sequentially.  This caused a convoy effect: the CodeIndex
        # build held the lock for hours (file walking + chunking +
        # embedding), blocking the pipeline's knowledge stage and vice
        # versa.  The actual embedder implementations (NativeEmbedder/
        # ONNX, OllamaEmbedder/HTTP) are thread-safe, and CodeIndex vs
        # KnowledgeIndex write to different files, so concurrent builds
        # are safe.  The lock is retained for backward compatibility but
        # is no longer acquired by any worker.
        self.embedding_lock = threading.Lock()

        # ── Legacy singleton build threading ─────────────────────
        self._legacy_build_lock = threading.Lock()
        self._legacy_build_thread: Optional[threading.Thread] = None
        self._legacy_last_build_result: Optional[Dict[str, Any]] = None
        self._legacy_last_build_error: Optional[str] = None
        self._legacy_trace_build_thread: Optional[threading.Thread] = None

    # ═════════════════════════════════════════════════════════════
    # Embedder creation (delegated to embedder_factory)
    # ═════════════════════════════════════════════════════════════

    def create_embedder(self, embedding_source: Optional[str] = None) -> Any:
        """Create the appropriate embedder based on configuration.

        Delegates to ``embedder_factory.create_embedder()`` — see that
        module for the full resolution priority chain.
        """
        from codrag.services.embedder_factory import create_embedder
        return create_embedder(embedding_source)

    # ═════════════════════════════════════════════════════════════
    # Index accessors (per-project)
    # ═════════════════════════════════════════════════════════════

    def get_project_index(self, project: Project) -> CodeIndex:
        idx = self.project_indexes.get(project.id)
        idx_dir = project_index_dir(project)
        if idx is None or Path(idx.index_dir).resolve() != Path(idx_dir).resolve():
            embedding_source = (project.config or {}).get("embedding_source")
            embedder = self.create_embedder(embedding_source)
            idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
            self.project_indexes[project.id] = idx
        return idx

    def get_project_layered_index(self, project: Project):
        """Return a LayeredCodeIndex if a remote team-sync index exists.

        If no remote index is present, returns the plain CodeIndex.
        The LayeredCodeIndex merges the remote (shared) index with
        any local delta index, using tombstone masking so local edits
        take priority over the shared team graph.

        Cached per project to avoid re-creating on every request.
        Call invalidate_layered_cache(project_id) after builds or syncs.
        """
        idx_dir = Path(project_index_dir(project))
        remote_dir = idx_dir / "remote"
        remote_docs = remote_dir / "documents.json"

        if not remote_docs.exists():
            # No remote index — clear cache and return plain CodeIndex
            self._layered_indexes.pop(project.id, None)
            return self.get_project_index(project)

        # Return cached instance if available
        cached = self._layered_indexes.get(project.id)
        if cached is not None:
            return cached

        from codrag.core.layered_index import LayeredCodeIndex

        embedding_source = (project.config or {}).get("embedding_source")
        embedder = self.create_embedder(embedding_source)

        # Delta dir stores re-enriched chunks for locally modified files
        delta_dir = idx_dir / "local_deltas"

        remote_idx = CodeIndex(index_dir=remote_dir, embedder=embedder)

        delta_idx = None
        delta_docs_path = delta_dir / "documents.json"
        if delta_docs_path.exists():
            delta_idx = CodeIndex(index_dir=delta_dir, embedder=embedder)

        # Remote is primary (the shared team graph), delta overrides it
        layered = LayeredCodeIndex(remote_index=remote_idx, delta_index=delta_idx)
        self._layered_indexes[project.id] = layered
        logger.info(
            "Using layered index for project %s (remote=%s, delta=%s)",
            project.name, remote_dir, "yes" if delta_idx else "no",
        )
        return layered

    def invalidate_layered_cache(self, project_id: str) -> None:
        """Clear the cached LayeredCodeIndex for a project.

        Call after:
        - A new remote index is downloaded (sync)
        - Local deltas are written or pruned
        - A full rebuild is triggered
        """
        self._layered_indexes.pop(project_id, None)

    def get_project_trace_index(self, project: Project) -> TraceIndex:
        idx = self.project_trace_indexes.get(project.id)
        idx_dir = project_index_dir(project)
        if idx is None or Path(idx.index_dir).resolve() != Path(idx_dir).resolve():
            idx = TraceIndex(idx_dir)
            self.project_trace_indexes[project.id] = idx
        return idx

    def get_project_knowledge_index(self, project: Project) -> KnowledgeIndex:
        idx = self.project_knowledge_indexes.get(project.id)
        idx_dir = project_index_dir(project)
        if idx is None or Path(idx.index_dir).resolve() != Path(idx_dir).resolve():
            embedder = self.create_embedder()
            idx = KnowledgeIndex(idx_dir, embedder)
            self.project_knowledge_indexes[project.id] = idx
        return idx

    # ═════════════════════════════════════════════════════════════
    # Index build (per-project)
    # ═════════════════════════════════════════════════════════════

    def is_project_building(self, project_id: str) -> bool:
        t = self.build_threads.get(project_id)
        return t is not None and t.is_alive()

    def _is_pipeline_active(self, project_id: str) -> bool:
        """Check if the pipeline orchestrator has an active run for this project."""
        try:
            from codrag.services.pipeline_orchestrator import pipeline_orchestrator
            status = pipeline_orchestrator.status(project_id)
            fast = status.get("fast_sync") or {}
            deep = status.get("deep_enrichment") or {}
            return fast.get("phase") == "running" or deep.get("phase") == "running"
        except Exception:
            return False

    def start_project_build(
        self,
        project: Project,
        roots: Optional[List[str]],
        include_globs: Optional[List[str]],
        exclude_globs: Optional[List[str]],
        max_file_bytes: int,
        hard_limit_bytes: int,
        use_gitignore: bool = False,
        included_paths: Optional[List[str]] = None,
    ) -> bool:
        with self.build_lock:
            if self.is_project_building(project.id):
                return False

            t = threading.Thread(
                target=self._project_build_worker,
                args=(project, roots, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore, included_paths),
                daemon=True,
            )
            self.build_threads[project.id] = t
            t.start()
            return True

    def _project_build_worker(
        self,
        project: Project,
        roots: Optional[List[str]],
        include_globs: Optional[List[str]],
        exclude_globs: Optional[List[str]],
        max_file_bytes: int,
        hard_limit_bytes: int,
        use_gitignore: bool,
        included_paths: Optional[List[str]] = None,
    ) -> None:
        pm = get_progress_manager()
        task_id = pm.start_task("index_build", project.id)

        try:
            idx = self.get_project_index(project)

            def _progress_cb(file_path: str, current: int, total: int):
                msg = f"Indexing {file_path}"
                pm.update(task_id, msg, current, total)
                logger.info(msg)

            meta = idx.build(
                repo_root=Path(project.path),
                roots=roots,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                max_file_bytes=max_file_bytes,
                hard_limit_bytes=hard_limit_bytes,
                use_gitignore=use_gitignore,
                progress_callback=_progress_cb,
                included_paths=included_paths,
            )
            self.last_build_result[project.id] = meta
            self.last_build_error.pop(project.id, None)
            
            # Invalidate index cache so next read loads the new data
            self.project_indexes.pop(project.id, None)
            self.invalidate_layered_cache(project.id)
            
            # Invalidate mtime-based stale cache so status shows fresh
            from codrag.services.project_helpers import invalidate_stale_cache
            invalidate_stale_cache(project.id)
            
            pm.finish_task(task_id, success=True, message="Build complete")
        except Exception as e:
            logger.exception("Build failed")
            self.last_build_error[project.id] = str(e)
            pm.finish_task(task_id, success=False, message=str(e))
        finally:
            with self.build_lock:
                cur = threading.current_thread()
                if self.build_threads.get(project.id) is cur:
                    self.build_threads.pop(project.id, None)

    # ═════════════════════════════════════════════════════════════
    # Delta build (for team sync — writes only changed files to local_deltas/)
    # ═════════════════════════════════════════════════════════════

    def has_remote_index(self, project: Project) -> bool:
        """Check if a remote team-sync index exists for this project."""
        idx_dir = Path(project_index_dir(project))
        return (idx_dir / "remote" / "documents.json").exists()

    def start_project_delta_build(
        self,
        project: Project,
        changed_paths: List[str],
        include_globs: Optional[List[str]],
        exclude_globs: Optional[List[str]],
        max_file_bytes: int = 500_000,
        hard_limit_bytes: int = 100_000_000,
    ) -> bool:
        """Build only the changed files into local_deltas/ (for team sync).

        When a remote index exists, the watcher should call this instead
        of start_project_build. The main index is the remote (shared) one;
        local edits go into a separate delta directory.
        """
        with self.build_lock:
            if self.is_project_building(project.id):
                return False

            t = threading.Thread(
                target=self._project_delta_build_worker,
                args=(project, changed_paths, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes),
                daemon=True,
            )
            self.build_threads[project.id] = t
            t.start()
            return True

    def _project_delta_build_worker(
        self,
        project: Project,
        changed_paths: List[str],
        include_globs: Optional[List[str]],
        exclude_globs: Optional[List[str]],
        max_file_bytes: int,
        hard_limit_bytes: int,
    ) -> None:
        """Build worker that writes only changed files to local_deltas/."""
        pm = get_progress_manager()
        task_id = pm.start_task("delta_build", project.id)

        try:
            idx_dir = Path(project_index_dir(project))
            delta_dir = idx_dir / "local_deltas"
            delta_dir.mkdir(parents=True, exist_ok=True)

            embedder = self.create_embedder(
                (project.config or {}).get("embedding_source")
            )
            delta_idx = CodeIndex(index_dir=delta_dir, embedder=embedder)

            def _progress_cb(file_path: str, current: int, total: int):
                msg = f"Delta indexing {file_path}"
                pm.update(task_id, msg, current, total)

            # Build the delta index with only the changed file paths as roots
            # This re-indexes only the files that changed locally
            delta_idx.build(
                repo_root=Path(project.path),
                roots=changed_paths,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                max_file_bytes=max_file_bytes,
                hard_limit_bytes=hard_limit_bytes,
                progress_callback=_progress_cb,
            )

            # Invalidate layered cache so next search picks up new deltas
            self.invalidate_layered_cache(project.id)

            from codrag.services.project_helpers import invalidate_stale_cache
            invalidate_stale_cache(project.id)

            logger.info(
                "Delta build complete for %s (%d changed paths)",
                project.id, len(changed_paths),
            )
            pm.finish_task(task_id, success=True, message="Delta build complete")
        except Exception as e:
            logger.exception("Delta build failed for %s", project.id)
            self.last_build_error[project.id] = str(e)
            pm.finish_task(task_id, success=False, message=str(e))
        finally:
            with self.build_lock:
                cur = threading.current_thread()
                if self.build_threads.get(project.id) is cur:
                    self.build_threads.pop(project.id, None)

    # ═════════════════════════════════════════════════════════════
    # Trace build (per-project)
    # ═════════════════════════════════════════════════════════════

    def is_project_trace_building(self, project_id: str) -> bool:
        t = self.trace_build_threads.get(project_id)
        return t is not None and t.is_alive()

    def start_project_trace_build(
        self,
        project: Project,
        include_globs: Optional[List[str]] = None,
        exclude_globs: Optional[List[str]] = None,
        max_file_bytes: int = 500_000,
        hard_limit_bytes: int = 100_000_000,
        use_gitignore: bool = False,
    ) -> bool:
        with self.trace_build_lock:
            if self.is_project_trace_building(project.id):
                return False

            # Block trace rebuild while the pipeline orchestrator is
            # actively running stages — concurrent writes corrupt data.
            if self._is_pipeline_active(project.id):
                logger.warning(
                    "Skipping trace build for %s — pipeline is active",
                    project.id,
                )
                return False

            t = threading.Thread(
                target=self._project_trace_build_worker,
                args=(project, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore),
                daemon=True,
            )
            self.trace_build_threads[project.id] = t
            t.start()
            return True

    def _project_trace_build_worker(
        self,
        project: Project,
        include_globs: Optional[List[str]],
        exclude_globs: Optional[List[str]],
        max_file_bytes: int,
        hard_limit_bytes: int,
        use_gitignore: bool,
    ) -> None:
        pm = get_progress_manager()
        task_id = pm.start_task("trace_build", project.id)

        def progress_callback(msg: str, current: int, total: int):
            pm.update(task_id, msg, current, total)
            if msg.startswith("trace_scan") and total > 0 and current % 50 == 0:
                 logger.info(f"[Trace] Scanning... ({current}/{total})")
            elif msg == "trace_write":
                 logger.info(f"[Trace] Writing index ({current}/{total})")

        try:
            idx_dir = project_index_dir(project)
            logger.info(f"Building trace index for {project.id} in {idx_dir}")
            
            builder = TraceBuilder(
                repo_root=Path(project.path),
                index_dir=idx_dir,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                max_file_bytes=max_file_bytes,
                hard_limit_bytes=hard_limit_bytes,
                use_gitignore=use_gitignore,
            )
            builder.build(progress_callback=progress_callback)

            trace_idx = TraceIndex(idx_dir)
            trace_idx.load()
            self.project_trace_indexes[project.id] = trace_idx
            
            # Invalidate mtime-based stale cache so status shows fresh
            from codrag.services.project_helpers import invalidate_stale_cache
            invalidate_stale_cache(project.id)
            
            logger.info("Trace build completed successfully")
            pm.finish_task(task_id, success=True, message="Trace build completed")
        except Exception as e:
            logger.error(f"Trace build failed: {e}")
            pm.finish_task(task_id, success=False, message=str(e))
        finally:
            with self.trace_build_lock:
                cur = threading.current_thread()
                if self.trace_build_threads.get(project.id) is cur:
                    self.trace_build_threads.pop(project.id, None)

    # ═════════════════════════════════════════════════════════════
    # Knowledge build (per-project)
    # ═════════════════════════════════════════════════════════════

    def is_project_knowledge_building(self, project_id: str) -> bool:
        # Legacy thread-based builds
        t = self.knowledge_build_threads.get(project_id)
        if t is not None and t.is_alive():
            return True
        # Pipeline orchestrator builds (SM-4)
        try:
            from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
            slot = build_orchestrator.status(project_id, BuildType.KNOWLEDGE)
            if slot.phase == BuildPhase.RUNNING:
                return True
        except Exception:
            pass
        return False

    def start_project_knowledge_build(self, project: Project) -> bool:
        with self.knowledge_build_lock:
            if self.is_project_knowledge_building(project.id):
                return False

            t = threading.Thread(
                target=self._project_knowledge_build_worker,
                args=(project,),
                daemon=True,
            )
            self.knowledge_build_threads[project.id] = t
            t.start()
            return True

    def _project_knowledge_build_worker(self, project: Project) -> None:
        pm = get_progress_manager()
        task_id = pm.start_task("knowledge_build", project.id)

        def progress_callback(msg: str, current: int, total: int, baseline: int = 0):
            # F-44: accept and ignore baseline.  ProgressManager.update only
            # accepts (current, total); the baseline is exposed via the
            # /pipeline/status slot_progress path, not via the SSE progress
            # event.  This wrapper just needs to swallow the 4th arg so the
            # knowledge worker (which now passes baseline) doesn't TypeError.
            pm.update(task_id, msg, current, total)

        try:
            idx = self.get_project_knowledge_index(project)
            logger.info(f"Building knowledge index for {project.id}")
            
            idx.build(progress_callback=progress_callback)
            
            # Invalidate mtime-based stale cache so status shows fresh
            from codrag.services.project_helpers import invalidate_stale_cache
            invalidate_stale_cache(project.id)
            
            logger.info("Knowledge build completed successfully")
            pm.finish_task(task_id, success=True, message="Knowledge build completed")
        except Exception as e:
            logger.error(f"Knowledge build failed: {e}")
            pm.finish_task(task_id, success=False, message=str(e))
        finally:
            with self.knowledge_build_lock:
                cur = threading.current_thread()
                if self.knowledge_build_threads.get(project.id) is cur:
                    self.knowledge_build_threads.pop(project.id, None)

    # ═════════════════════════════════════════════════════════════
    # Legacy singleton accessors (deprecated endpoints)
    # ═════════════════════════════════════════════════════════════

    def get_legacy_index(self) -> CodeIndex:
        from codrag.server import _config
        if self.legacy_index is None:
            index_dir = Path(_config.get("index_dir", "./codrag_data"))
            embedder = self.create_embedder()
            self.legacy_index = CodeIndex(index_dir=index_dir, embedder=embedder)
        return self.legacy_index

    # ═════════════════════════════════════════════════════════════
    # Cleanup helpers
    # ═════════════════════════════════════════════════════════════

    def clear_project(self, project_id: str) -> None:
        """Remove all cached state for a project (after deletion)."""
        self.project_indexes.pop(project_id, None)
        self.project_trace_indexes.pop(project_id, None)
        self.project_knowledge_indexes.pop(project_id, None)
        with self.build_lock:
            self.build_threads.pop(project_id, None)
            self.last_build_result.pop(project_id, None)
            self.last_build_error.pop(project_id, None)
        with self.trace_build_lock:
            self.trace_build_threads.pop(project_id, None)
        with self.knowledge_build_lock:
            self.knowledge_build_threads.pop(project_id, None)

    def clear_all_indexes(self) -> None:
        """Invalidate all cached indexes (e.g. after embedding config change)."""
        self.legacy_index = None
        self.project_indexes.clear()


# ── Module-level singleton ───────────────────────────────────────
build_manager = BuildManager()
