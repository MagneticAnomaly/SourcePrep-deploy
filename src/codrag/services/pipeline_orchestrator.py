"""
CoDRAG Pipeline Orchestrator — Phase 24 (SM-6)
================================================

Sequences the 8-stage Trace Graph enrichment pipeline using
BuildOrchestrator (SM-4) slots.

**Two Groups:**

  Group A — Fast Sync (stages 1–4):
    1. structural  (Rust: AST parse → nodes + edges)
    2. augment     (3b LLM: fast catalogue)
    3. validate    (Rust: relationship validation)
    4. knowledge   (Embedding: embed fast-pass metadata)

  Group B — Deep Enrichment (stages 5–8):
    5. epistemic   (14b LLM: deep reasoning + confidence)
    6. cluster     (14b LLM: module-level synthesis)
    7. deepening   (Loop: re-enrich stale nodes)
    8. knowledge   (Embedding: re-embed with deep metadata)

**Controls (group-level, NOT per-stage):**
  - Fast Sync: boolean on/off
  - Deep Enrichment: 'manual' | 'auto' | 'scheduled'

**Staleness model:**
  When a file changes → Fast Sync re-runs (stages 1-4) → marks affected
  trace nodes as "stale" in epistemic data → the deepening loop (stage 7)
  naturally picks up stale nodes in the next Group B run.

**Relationship to BuildOrchestrator (SM-4):**
  Each stage dispatches its work via ``build_orchestrator.start()``.
  The pipeline watches for COMPLETED/FAILED transitions to advance
  to the next stage.

**Relationship to BuildManager:**
  BuildManager still owns index/trace/knowledge caches and embedder creation.
  The pipeline orchestrator creates worker functions that use BuildManager
  internals to do the actual work.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from codrag.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
    build_orchestrator,
)

logger = logging.getLogger(__name__)


# ── Stage Definitions ────────────────────────────────────────────

class StageId(str, enum.Enum):
    """The 8 pipeline stages, matching the UI's EnrichmentStageId."""
    STRUCTURAL = "structural"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    ENRICHMENT = "enrichment"
    CLUSTERING = "clustering"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"


# Map StageId → BuildType for dispatch to the orchestrator
STAGE_BUILD_TYPE: Dict[StageId, BuildType] = {
    StageId.STRUCTURAL: BuildType.TRACE,
    StageId.CATALOGUE: BuildType.AUGMENT,
    StageId.VALIDATION: BuildType.VALIDATE,
    StageId.KNOWLEDGE: BuildType.KNOWLEDGE,
    StageId.ENRICHMENT: BuildType.EPISTEMIC,
    StageId.CLUSTERING: BuildType.CLUSTER,
    StageId.DEEPENING: BuildType.DEEPENING,
    StageId.DEEP_KNOWLEDGE: BuildType.KNOWLEDGE,  # Same build type, re-runs with richer data
}

FAST_SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL,
    StageId.CATALOGUE,
    StageId.VALIDATION,
    StageId.KNOWLEDGE,
]

DEEP_ENRICHMENT_STAGES: List[StageId] = [
    StageId.ENRICHMENT,
    StageId.CLUSTERING,
    StageId.DEEPENING,
    StageId.DEEP_KNOWLEDGE,
]


# ── Pipeline Run ─────────────────────────────────────────────────

class PipelineRunPhase(str, enum.Enum):
    """Overall phase of a pipeline run (group-level)."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineRun:
    """Tracks a single pipeline group run (fast sync or deep enrichment)."""
    project_id: str
    group: str  # "fast_sync" or "deep_enrichment"
    stages: List[StageId]
    phase: PipelineRunPhase = PipelineRunPhase.IDLE
    current_stage_index: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    # Per-stage completion tracking
    stage_results: Dict[str, str] = field(default_factory=dict)  # stage_id → "completed"|"failed"|"skipped"

    @property
    def current_stage(self) -> Optional[StageId]:
        if self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return None

    @property
    def is_active(self) -> bool:
        return self.phase == PipelineRunPhase.RUNNING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "group": self.group,
            "phase": self.phase.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "current_stage_index": self.current_stage_index,
            "total_stages": len(self.stages),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "stage_results": self.stage_results,
        }


# ── Worker Factory ───────────────────────────────────────────────

class WorkerFactory:
    """Creates worker functions for each stage.

    Each worker is a callable that takes (BuildSlot, progress_callback)
    and returns a result dict.  Workers use BuildManager internals.

    This is the integration layer between the state machine and the
    actual build logic.
    """

    @staticmethod
    def create_worker(
        project_id: str,
        stage: StageId,
    ) -> Callable[[BuildSlot, Callable[[str, int, int], None]], Dict[str, Any]]:
        """Return a worker function for the given stage.

        Each worker directly instantiates the core classes (TraceBuilder,
        TraceAugmenter, EpistemicEnricher, etc.) and runs them synchronously.
        The BuildOrchestrator runs the worker in a managed daemon thread.
        """

        if stage == StageId.STRUCTURAL:
            return WorkerFactory._trace_worker(project_id)
        elif stage == StageId.CATALOGUE:
            return WorkerFactory._augment_worker(project_id)
        elif stage == StageId.VALIDATION:
            return WorkerFactory._validate_worker(project_id)
        elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
            return WorkerFactory._knowledge_worker(project_id)
        elif stage == StageId.ENRICHMENT:
            return WorkerFactory._epistemic_worker(project_id)
        elif stage == StageId.CLUSTERING:
            return WorkerFactory._cluster_worker(project_id)
        elif stage == StageId.DEEPENING:
            return WorkerFactory._deepening_worker(project_id)
        else:
            raise ValueError(f"Unknown stage: {stage}")

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _get_project_and_config(project_id: str):
        """Shared helper: load project, ui_config, and common build params."""
        from codrag.services.project_helpers import require_project
        from codrag.server import _load_ui_config

        project = require_project(project_id)
        ui_cfg = _load_ui_config()

        include_globs = (project.config or {}).get("include_globs") or ui_cfg.get("include_globs") or []
        exclude_globs = (project.config or {}).get("exclude_globs") or ui_cfg.get("exclude_globs") or []
        max_file_bytes = (project.config or {}).get("max_file_bytes") or ui_cfg.get("max_file_bytes", 500_000)
        hard_limit_bytes = ui_cfg.get("hard_limit_bytes", 100_000_000)

        return project, ui_cfg, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes

    @staticmethod
    def _get_llm_client(slot_name: str):
        """Get an LLM client for the given slot ('small' or 'large'), with fallback."""
        from codrag.server import _get_llm_client_for_slot

        client = _get_llm_client_for_slot(slot_name)
        if not client and slot_name == "large":
            client = _get_llm_client_for_slot("small")
        if not client:
            raise RuntimeError(f"No {slot_name} model configured. Configure a model in AI Models settings.")
        if not client.is_available():
            raise RuntimeError(f"Model endpoint not reachable: {client.endpoint_url}")
        return client

    # ── Stage Workers ──────────────────────────────────────────

    @staticmethod
    def _trace_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.build_manager import build_manager
            from codrag.core.trace import TraceBuilder, TraceIndex
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, ui_cfg, inc, exc, max_fb, hard_lb = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            builder = TraceBuilder(
                repo_root=Path(project.path),
                index_dir=idx_dir,
                include_globs=inc,
                exclude_globs=exc,
                max_file_bytes=max_fb,
                hard_limit_bytes=hard_lb,
            )
            builder.build(progress_callback=progress_cb)

            trace_idx = TraceIndex(idx_dir)
            trace_idx.load()
            build_manager.project_trace_indexes[project_id] = trace_idx

            return {"stage": "structural", "nodes": trace_idx.node_count()}
        return worker

    @staticmethod
    def _augment_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import TraceAugmenter
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("small")
            idx_dir = project_index_dir(project)

            augmenter = TraceAugmenter(
                index_dir=idx_dir,
                repo_root=project.path,
                llm_client=llm_client,
            )
            result = augmenter.run(progress_callback=progress_cb)
            return {"stage": "catalogue", "augmented": result.augmented}
        return worker

    @staticmethod
    def _validate_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            # Relationship validation is currently part of the Rust trace build.
            # This stage reports existing validation state as a pass-through.
            # Future: dedicated Rust validation pass.
            from codrag.services.build_manager import build_manager

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            trace_idx = build_manager.get_project_trace_index(project)

            progress_cb("Validating relationships", 0, 1)
            progress_cb("Validation complete", 1, 1)
            return {"stage": "validation", "exists": trace_idx.exists()}
        return worker

    @staticmethod
    def _knowledge_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.build_manager import build_manager

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx = build_manager.get_project_knowledge_index(project)
            result = idx.build(progress_callback=progress_cb)
            return {"stage": "knowledge", **(result or {})}
        return worker

    @staticmethod
    def _epistemic_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import EpistemicEnricher
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("large")
            idx_dir = project_index_dir(project)

            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
            )
            result = enricher.run(progress_callback=progress_cb)
            return {"stage": "enrichment", **(result or {})}
        return worker

    @staticmethod
    def _cluster_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import ClusterSynthesizer
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("large")
            idx_dir = project_index_dir(project)

            synthesizer = ClusterSynthesizer(llm=llm_client, index_dir=idx_dir)
            result = synthesizer.run()
            return {"stage": "clustering", **(result or {})}
        return worker

    @staticmethod
    def _deepening_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import EpistemicEnricher, DeepeningLoop
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("large")
            idx_dir = project_index_dir(project)

            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
            )
            loop = DeepeningLoop(
                enricher=enricher,
                index_dir=idx_dir,
                max_iterations=10,
                batch_size=20,
            )
            result = loop.run(progress_callback=progress_cb)
            return {
                "stage": "deepening",
                "iterations": result.iterations,
                "converged": bool(result.convergence),
            }
        return worker


# ── Pipeline Orchestrator ────────────────────────────────────────

class PipelineOrchestrator:
    """Sequences the 8-stage pipeline in two groups.

    Uses BuildOrchestrator (SM-4) for individual stage execution and
    listens for completion events to advance the pipeline.

    Usage::

        pipeline.run_fast_sync("proj-1")
        pipeline.run_deep_enrichment("proj-1")
        pipeline.run_all("proj-1")  # fast sync then deep enrichment

        status = pipeline.status("proj-1")
    """

    def __init__(self, orchestrator: Optional[BuildOrchestrator] = None) -> None:
        self._orchestrator = orchestrator or build_orchestrator
        self._lock = threading.Lock()
        # Active pipeline runs: (project_id, group) → PipelineRun
        self._runs: Dict[tuple[str, str], PipelineRun] = {}
        # Register for build completion events
        self._orchestrator.add_listener(self._on_build_transition)

    # ── Public API ─────────────────────────────────────────────

    def run_fast_sync(self, project_id: str) -> bool:
        """Start the Fast Sync group (stages 1-4).  Returns False if already running."""
        return self._start_group(project_id, "fast_sync", FAST_SYNC_STAGES)

    def run_deep_enrichment(self, project_id: str) -> bool:
        """Start the Deep Enrichment group (stages 5-8).  Returns False if already running."""
        return self._start_group(project_id, "deep_enrichment", DEEP_ENRICHMENT_STAGES)

    def run_all(self, project_id: str) -> bool:
        """Start Fast Sync, then chain Deep Enrichment after it completes."""
        # Start fast sync; deep enrichment will be chained via the listener
        with self._lock:
            key = (project_id, "fast_sync")
            run = self._runs.get(key)
            if run and run.is_active:
                return False
            # Mark that deep should chain after fast
            self._chain_deep: Dict[str, bool] = getattr(self, "_chain_deep", {})
            self._chain_deep[project_id] = True
        return self.run_fast_sync(project_id)

    def status(self, project_id: str) -> Dict[str, Any]:
        """Get pipeline status for a project."""
        with self._lock:
            fast_run = self._runs.get((project_id, "fast_sync"))
            deep_run = self._runs.get((project_id, "deep_enrichment"))

        # Also get individual stage statuses from the build orchestrator
        stage_statuses = {}
        for stage_id in list(StageId):
            bt = STAGE_BUILD_TYPE[stage_id]
            slot = self._orchestrator.status(project_id, bt)
            stage_statuses[stage_id.value] = slot.to_dict()

        return {
            "fast_sync": fast_run.to_dict() if fast_run else None,
            "deep_enrichment": deep_run.to_dict() if deep_run else None,
            "stages": stage_statuses,
            "any_running": (
                (fast_run.is_active if fast_run else False) or
                (deep_run.is_active if deep_run else False)
            ),
        }

    def cancel_fast_sync(self, project_id: str) -> bool:
        """Cancel the Fast Sync group."""
        return self._cancel_group(project_id, "fast_sync")

    def cancel_deep_enrichment(self, project_id: str) -> bool:
        """Cancel the Deep Enrichment group."""
        return self._cancel_group(project_id, "deep_enrichment")

    def clear_project(self, project_id: str) -> None:
        """Remove all pipeline state for a project."""
        with self._lock:
            keys = [k for k in self._runs if k[0] == project_id]
            for k in keys:
                del self._runs[k]
        self._orchestrator.clear_project(project_id)

    # ── Internal ───────────────────────────────────────────────

    @staticmethod
    def _is_deep_enrichment_auto(project_id: str) -> bool:
        """Check if deep enrichment mode is 'auto' in persisted pipeline config."""
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            mode = (config.get("deep_enrichment") or {}).get("mode", "manual")
            return mode == "auto"
        except Exception:
            return False

    def _start_group(
        self, project_id: str, group: str, stages: List[StageId]
    ) -> bool:
        """Start a group of stages sequentially."""
        with self._lock:
            key = (project_id, group)
            existing = self._runs.get(key)
            if existing and existing.is_active:
                return False

            run = PipelineRun(
                project_id=project_id,
                group=group,
                stages=list(stages),
                phase=PipelineRunPhase.RUNNING,
                started_at=time.time(),
            )
            self._runs[key] = run

        # Start the first stage
        self._advance_pipeline(run)
        return True

    def _advance_pipeline(self, run: PipelineRun) -> None:
        """Advance to the next stage in the pipeline, or finish."""
        if run.current_stage_index >= len(run.stages):
            # All stages complete
            with self._lock:
                run.phase = PipelineRunPhase.COMPLETED
                run.finished_at = time.time()
            logger.info(
                "Pipeline %s/%s completed in %.1fs",
                run.project_id, run.group,
                (run.finished_at or 0) - (run.started_at or 0),
            )
            # Chain deep enrichment after fast sync if configured or explicitly requested
            if run.group == "fast_sync":
                should_chain = False
                # 1. Explicit chain from run_all()
                chain_deep = getattr(self, "_chain_deep", {})
                if chain_deep.pop(run.project_id, False):
                    should_chain = True
                # 2. Auto-chain: check persisted pipeline config
                if not should_chain:
                    should_chain = self._is_deep_enrichment_auto(run.project_id)
                if should_chain:
                    logger.info("Chaining deep enrichment after fast sync for %s", run.project_id)
                    self.run_deep_enrichment(run.project_id)
            return

        stage = run.stages[run.current_stage_index]
        build_type = STAGE_BUILD_TYPE[stage]

        logger.info(
            "Pipeline %s/%s — starting stage %d/%d: %s",
            run.project_id, run.group,
            run.current_stage_index + 1, len(run.stages),
            stage.value,
        )

        worker = WorkerFactory.create_worker(run.project_id, stage)
        started = self._orchestrator.start(run.project_id, build_type, worker)

        if not started:
            # Build type already active (e.g. someone triggered it manually)
            # Wait for it to complete via the listener
            logger.info(
                "Stage %s already active for %s — waiting for completion",
                stage.value, run.project_id,
            )

    def _on_build_transition(
        self,
        project_id: str,
        build_type: BuildType,
        old_phase: BuildPhase,
        new_phase: BuildPhase,
    ) -> None:
        """Called by BuildOrchestrator when a build slot transitions.

        Advances the pipeline if the completed build matches the current stage.
        """
        if new_phase not in (BuildPhase.COMPLETED, BuildPhase.FAILED):
            return

        with self._lock:
            # Find any active pipeline run for this project where the current
            # stage matches this build type
            matching_run: Optional[PipelineRun] = None
            for key, run in self._runs.items():
                if run.project_id != project_id or not run.is_active:
                    continue
                current = run.current_stage
                if current and STAGE_BUILD_TYPE[current] == build_type:
                    matching_run = run
                    break

            if matching_run is None:
                return

            stage = matching_run.current_stage
            if stage is None:
                return

            if new_phase == BuildPhase.COMPLETED:
                matching_run.stage_results[stage.value] = "completed"
                matching_run.current_stage_index += 1
                logger.info(
                    "Pipeline %s/%s — stage %s completed",
                    project_id, matching_run.group, stage.value,
                )
            elif new_phase == BuildPhase.FAILED:
                matching_run.stage_results[stage.value] = "failed"
                slot = self._orchestrator.status(project_id, build_type)
                matching_run.phase = PipelineRunPhase.FAILED
                matching_run.finished_at = time.time()
                matching_run.error = f"Stage {stage.value} failed: {slot.error}"
                logger.error(
                    "Pipeline %s/%s — stage %s failed: %s",
                    project_id, matching_run.group, stage.value, slot.error,
                )
                return

        # Advance outside the lock
        if matching_run and matching_run.is_active:
            self._advance_pipeline(matching_run)

    def _cancel_group(self, project_id: str, group: str) -> bool:
        """Cancel a running group."""
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run or not run.is_active:
                return False

            current = run.current_stage
            run.phase = PipelineRunPhase.FAILED
            run.finished_at = time.time()
            run.error = "Cancelled by user"

        # Cancel the current stage's build
        if current:
            bt = STAGE_BUILD_TYPE[current]
            self._orchestrator.cancel(project_id, bt)
        return True


# ── SSE Event Bridge ─────────────────────────────────────────────

def _create_sse_bridge(pipeline: PipelineOrchestrator) -> None:
    """Register a BuildOrchestrator listener that emits SSE events
    for pipeline stage transitions.  Called once at module init."""

    def _on_transition(
        project_id: str,
        build_type: BuildType,
        old_phase: BuildPhase,
        new_phase: BuildPhase,
    ) -> None:
        try:
            from codrag.core.events import get_event_bus, get_progress_manager

            bus = get_event_bus()
            pm = get_progress_manager()

            # Emit a task-level event for the build type
            task_id = f"pipeline_{build_type.value}_{project_id}"

            if new_phase == BuildPhase.RUNNING:
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "running",
                    "project_id": project_id,
                    "build_type": build_type.value,
                })
            elif new_phase == BuildPhase.COMPLETED:
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "completed",
                    "project_id": project_id,
                    "build_type": build_type.value,
                })
            elif new_phase == BuildPhase.FAILED:
                slot = pipeline._orchestrator.status(project_id, build_type)
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "failed",
                    "project_id": project_id,
                    "build_type": build_type.value,
                    "error": slot.error,
                })

            # Also emit pipeline group-level status
            status = pipeline.status(project_id)
            bus.emit("pipeline_status", {
                "project_id": project_id,
                **status,
            })
        except Exception:
            logger.debug("SSE bridge emit failed (event bus not ready)", exc_info=True)

    pipeline._orchestrator.add_listener(_on_transition)


# ── Module-level singleton ───────────────────────────────────────
pipeline_orchestrator = PipelineOrchestrator()
_create_sse_bridge(pipeline_orchestrator)
