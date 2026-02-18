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

from codrag.core import CodeIndex, OllamaEmbedder, NativeEmbedder, KnowledgeIndex
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

        # ── Index build threading ────────────────────────────────
        self.build_lock = threading.Lock()
        self.build_threads: Dict[str, threading.Thread] = {}
        self.last_build_result: Dict[str, Dict[str, Any]] = {}
        self.last_build_error: Dict[str, str] = {}

        # ── Trace build threading ────────────────────────────────
        self.trace_build_lock = threading.Lock()
        self.trace_build_threads: Dict[str, threading.Thread] = {}

        # ── Knowledge build threading ────────────────────────────
        self.knowledge_build_lock = threading.Lock()
        self.knowledge_build_threads: Dict[str, threading.Thread] = {}

        # ── Legacy singleton build threading ─────────────────────
        self._legacy_build_lock = threading.Lock()
        self._legacy_build_thread: Optional[threading.Thread] = None
        self._legacy_last_build_result: Optional[Dict[str, Any]] = None
        self._legacy_last_build_error: Optional[str] = None
        self._legacy_trace_build_thread: Optional[threading.Thread] = None

    # ═════════════════════════════════════════════════════════════
    # Embedder creation
    # ═════════════════════════════════════════════════════════════

    def create_embedder(self, embedding_source: Optional[str] = None) -> Any:
        """Create the appropriate embedder based on configuration.

        Priority (highest → lowest):
        1. Explicit *embedding_source* parameter (project-level override).
        2. Dashboard ``llm_config.embedding`` settings persisted in ui_config.json.
        3. CLI ``_config`` values (``--model``, ``--ollama-url``).
        4. NativeEmbedder (if deps available), else OllamaEmbedder fallback.
        """
        from codrag.server import _config, _load_ui_config

        # ── 1. Explicit project-level override ──────────────────
        if embedding_source == "ollama":
            ollama_url = _config.get("ollama_url", "http://localhost:11434")
            model = _config.get("model", "nomic-embed-text")
            logger.info("Using OllamaEmbedder (project override, model=%s, url=%s)", model, ollama_url)
            return OllamaEmbedder(model=model, base_url=ollama_url)

        if embedding_source == "native":
            native = NativeEmbedder()
            if native.is_available():
                logger.info("Using NativeEmbedder (project override)")
                return native

        # ── 2. Dashboard llm_config (ui_config.json) ────────────
        if embedding_source is None:
            try:
                ui_cfg = _load_ui_config()
                emb_cfg = (ui_cfg.get("llm_config") or {}).get("embedding") or {}
                dash_source = emb_cfg.get("source", "")

                if dash_source == "huggingface":
                    native = NativeEmbedder()
                    if native.is_available():
                        logger.info("Using NativeEmbedder (dashboard: HuggingFace source)")
                        return native
                    logger.warning("Dashboard set to HuggingFace but NativeEmbedder deps missing")

                elif dash_source == "endpoint":
                    ep_id = emb_cfg.get("endpoint_id", "")
                    dash_model = emb_cfg.get("model", "")
                    if ep_id and dash_model:
                        endpoints = (ui_cfg.get("llm_config") or {}).get("saved_endpoints") or []
                        ep = next((e for e in endpoints if e.get("id") == ep_id), None)
                        if ep and ep.get("provider") == "ollama":
                            ep_url = ep.get("url", "http://localhost:11434")
                            logger.info(
                                "Using OllamaEmbedder (dashboard: endpoint=%s, model=%s, url=%s)",
                                ep_id, dash_model, ep_url,
                            )
                            return OllamaEmbedder(model=dash_model, base_url=ep_url)
            except Exception:
                logger.debug("Failed to read dashboard embedding config; falling back", exc_info=True)

        # ── 3. CLI _config fallback ─────────────────────────────
        cli_source = _config.get("embedding_source", "native")
        if cli_source == "ollama":
            ollama_url = _config.get("ollama_url", "http://localhost:11434")
            model = _config.get("model", "nomic-embed-text")
            logger.info("Using OllamaEmbedder (cli fallback, model=%s, url=%s)", model, ollama_url)
            return OllamaEmbedder(model=model, base_url=ollama_url)

        # ── 4. NativeEmbedder default / OllamaEmbedder fallback ─
        native = NativeEmbedder()
        if native.is_available():
            logger.info("Using NativeEmbedder (nomic-embed-text-v1.5 via ONNX)")
            return native

        logger.warning("NativeEmbedder deps not installed; falling back to OllamaEmbedder")
        ollama_url = _config.get("ollama_url", "http://localhost:11434")
        model = _config.get("model", "nomic-embed-text")
        return OllamaEmbedder(model=model, base_url=ollama_url)

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

            # Block code-index rebuild while the pipeline orchestrator is
            # actively running stages — the atomic directory swap would race
            # with pipeline file writes and could snapshot stale data.
            if self._is_pipeline_active(project.id):
                logger.warning(
                    "Skipping code-index build for %s — pipeline is active",
                    project.id,
                )
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

            if self._is_pipeline_active(project.id):
                logger.warning(
                    "Skipping knowledge build for %s — pipeline is active",
                    project.id,
                )
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

        def progress_callback(msg: str, current: int, total: int):
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
