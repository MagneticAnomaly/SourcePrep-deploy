"""
CoDRAG Pipeline Orchestrator — Phase 24 (SM-6) + Phase 25 (Crash Protection)
=============================================================================

Sequences the 11-stage Trace Graph enrichment pipeline using
BuildOrchestrator (SM-4) slots.

**Two Groups:**

  Group A — Fast Sync (stages 1–5):
    1. structural      (Rust: AST parse → nodes + edges)
    2. inferred_edges  (LLM: cross-language/dynamic edge discovery)
    3. augment         (3b LLM: fast catalogue)
    4. validate        (Rust: relationship validation)
    5. knowledge       (Embedding: embed fast-pass metadata)

  Group B — Deep Enrichment (stages 6–10):
    6. epistemic   (14b LLM: deep reasoning + confidence)
    7. cluster     (14b LLM: module-level synthesis)
    8. deepening   (Loop: re-enrich stale nodes)
    9. atlas       (14b LLM: codebase orientation document)
   10. knowledge   (Embedding: re-embed with deep metadata)

**Controls (group-level, NOT per-stage):**
  - Fast Sync: boolean on/off
  - Deep Enrichment: 'manual' | 'auto' | 'scheduled'

**Staleness model:**
  When a file changes → Fast Sync re-runs (stages 1-4) → marks affected
  trace nodes as "stale" in epistemic data → the deepening loop (stage 7)
  naturally picks up stale nodes in the next Group B run.

**Crash Protection (Phase 25):**
  Every state transition is persisted to a SQLite journal *before* the
  work begins.  On startup, any journal entry still marked "running" is
  detected as a crash, and the user is offered Resume/Discard via the UI.
  Heartbeat timestamps prevent zombie detection false-positives.
  Checkpoints back up trace files before destructive stages (deepening).

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
    """The 11 pipeline stages, matching the UI's EnrichmentStageId."""
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    ATLAS = "atlas"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"


# Map StageId → BuildType for dispatch to the orchestrator
STAGE_BUILD_TYPE: Dict[StageId, BuildType] = {
    StageId.STRUCTURAL: BuildType.TRACE,
    StageId.INFERRED_EDGES: BuildType.INFERRED_EDGES,
    StageId.CATALOGUE: BuildType.AUGMENT,
    StageId.VALIDATION: BuildType.VALIDATE,
    StageId.KNOWLEDGE: BuildType.KNOWLEDGE,
    StageId.ENRICHMENT: BuildType.EPISTEMIC,
    StageId.GROUP_REASONING: BuildType.GROUP_REASONING,
    StageId.CLUSTERING: BuildType.CLUSTER,
    StageId.ATLAS: BuildType.ATLAS,
    StageId.DEEPENING: BuildType.DEEPENING,
    StageId.DEEP_KNOWLEDGE: BuildType.KNOWLEDGE,  # Same build type, re-runs with richer data
}

FAST_SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL,
    StageId.INFERRED_EDGES,
    StageId.CATALOGUE,
    StageId.VALIDATION,
    StageId.KNOWLEDGE,
]

DEEP_ENRICHMENT_STAGES: List[StageId] = [
    StageId.ENRICHMENT,
    StageId.GROUP_REASONING,
    StageId.CLUSTERING,
    StageId.ATLAS,
    StageId.DEEPENING,
    StageId.DEEP_KNOWLEDGE,
]


# ── Model Slot Mapping ───────────────────────────────────────────
# Which LLM slot each stage uses.  None = no LLM needed.
# Used by the VRAM lifecycle manager to unload models between slot transitions.

STAGE_MODEL_SLOT: Dict[StageId, Optional[str]] = {
    StageId.STRUCTURAL:     None,
    StageId.INFERRED_EDGES: "code",   # prefers code slot; worker falls back to small
    StageId.CATALOGUE:      "small",
    StageId.VALIDATION:     None,
    StageId.KNOWLEDGE:      None,      # embedding only
    StageId.ENRICHMENT:     "large",
    StageId.GROUP_REASONING: "large",
    StageId.CLUSTERING:     "large",
    StageId.ATLAS:          "large",
    StageId.DEEPENING:      "large",
    StageId.DEEP_KNOWLEDGE: None,      # embedding only
}


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
    # Phase 25: Journal run ID for crash recovery
    journal_run_id: Optional[str] = None

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
            "journal_run_id": self.journal_run_id,
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
        elif stage == StageId.INFERRED_EDGES:
            return WorkerFactory._inferred_edges_worker(project_id)
        elif stage == StageId.CATALOGUE:
            return WorkerFactory._augment_worker(project_id)
        elif stage == StageId.VALIDATION:
            return WorkerFactory._validate_worker(project_id)
        elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
            return WorkerFactory._knowledge_worker(project_id)
        elif stage == StageId.ENRICHMENT:
            return WorkerFactory._epistemic_worker(project_id)
        elif stage == StageId.GROUP_REASONING:
            return WorkerFactory._group_reasoning_worker(project_id)
        elif stage == StageId.CLUSTERING:
            return WorkerFactory._cluster_worker(project_id)
        elif stage == StageId.ATLAS:
            return WorkerFactory._atlas_worker(project_id)
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

        pcfg = project.config or {}
        include_globs = pcfg.get("include_globs") or ui_cfg.get("include_globs") or []
        exclude_globs = pcfg.get("exclude_globs") or ui_cfg.get("exclude_globs") or []
        max_file_bytes = pcfg.get("max_file_bytes") or ui_cfg.get("max_file_bytes", 500_000)
        hard_limit_bytes = pcfg.get("hard_limit_bytes") or ui_cfg.get("hard_limit_bytes", 100_000_000)

        # Merge user trace-specific ignore patterns (from Exclude Tree / Patterns tab)
        trace_ignore = (pcfg.get("trace") or {}).get("ignore_patterns", [])
        if isinstance(trace_ignore, list) and trace_ignore:
            merged = set(exclude_globs)
            merged.update(str(p) for p in trace_ignore if p)
            exclude_globs = sorted(merged)

        # Advanced trace limits (per-project overrides)
        adv = pcfg.get("advanced") or {}
        max_files = int(adv.get("max_files", 50_000))
        max_nodes = int(adv.get("max_nodes", 100_000))
        max_edges = int(adv.get("max_edges", 500_000))

        return project, ui_cfg, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, max_files, max_nodes, max_edges

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

    @staticmethod
    def _get_batch_profile(llm_client):
        """Detect the batch profile for an LLM client, respecting user override."""
        try:
            from codrag.core.batch_profiles import resolve_profile
            from codrag.server import _load_ui_config
            ui_cfg = _load_ui_config()
            override = (ui_cfg.get("llm_config") or {}).get("batch_mode")
            return resolve_profile(llm_client.provider, llm_client.model, override=override)
        except Exception:
            return None

    @staticmethod
    def _logged_progress(stage_name: str, progress_cb: Callable, project_name: str = "") -> Callable:
        """Wrap a progress callback to also emit logger.info for Process Logs."""
        tag = f"{project_name}/{stage_name}" if project_name else stage_name
        def _wrapper(message: str, current: int, total: int) -> None:
            progress_cb(message, current, total)
            if total > 0:
                pct = round(current / total * 100)
                logger.info("[%s] %s (%d/%d — %d%%)", tag, message, current, total, pct)
            else:
                logger.info("[%s] %s", tag, message)
        return _wrapper

    # ── Stage Workers ──────────────────────────────────────────

    @staticmethod
    def _trace_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.build_manager import build_manager
            from codrag.core.trace import TraceBuilder, TraceIndex
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, ui_cfg, inc, exc, max_fb, hard_lb, max_f, max_n, max_e = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            builder = TraceBuilder(
                repo_root=Path(project.path),
                index_dir=idx_dir,
                include_globs=inc,
                exclude_globs=exc,
                max_file_bytes=max_fb,
                hard_limit_bytes=hard_lb,
                max_files=max_f,
                max_nodes=max_n,
                max_edges=max_e,
            )
            log_cb = WorkerFactory._logged_progress("Structural", progress_cb, project.name)
            logger.info("[%s/Structural] Starting trace build", project.name)
            builder.build(progress_callback=log_cb)

            trace_idx = TraceIndex(idx_dir)
            trace_idx.load()
            build_manager.project_trace_indexes[project_id] = trace_idx
            logger.info("[%s/Structural] Complete — %d nodes", project.name, trace_idx.node_count())

            # Ensure trace.enabled=true in project config so status endpoint
            # reports exists correctly (belt-and-suspenders with frontend fix)
            cfg = project.config if isinstance(project.config, dict) else {}
            trace_cfg = cfg.get("trace") if isinstance(cfg.get("trace"), dict) else {}
            if not trace_cfg.get("enabled"):
                import copy
                new_cfg = copy.deepcopy(cfg)
                new_cfg.setdefault("trace", {})["enabled"] = True
                project.config = new_cfg
                try:
                    from codrag.core.project_registry import get_registry
                    get_registry().update_project(project.id, config=new_cfg)
                except Exception:
                    pass  # Non-fatal: frontend also sets this

            return {"stage": "structural", "nodes": trace_idx.node_count()}
        return worker

    @staticmethod
    def _inferred_edges_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import InferredEdgesAnalyzer
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            # Prefer code model slot; fall back to small model
            llm_client = None
            slot_used = None
            for try_slot in ("code", "small"):
                try:
                    client = WorkerFactory._get_llm_client(try_slot)
                    if client and client.is_available():
                        llm_client = client
                        slot_used = try_slot
                        break
                except RuntimeError:
                    pass

            if not llm_client:
                logger.info("[Edge Discovery] No code or small model available — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "inferred_edges", "skipped": True, "reason": "no_llm"}

            # Verbose pipeline file logging
            try:
                from codrag.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
                pfl.log("inferred_edges", f"Starting: model={llm_client.model}, endpoint={llm_client.endpoint_url}")
            except Exception:
                pfl = None

            batch_profile = WorkerFactory._get_batch_profile(llm_client)
            if pfl and batch_profile:
                pfl.log("inferred_edges", f"Batch profile: {batch_profile.name.value}")

            logger.info("[%s/Edge Discovery] Starting: model=%s, slot=%s", project.name, llm_client.model, slot_used)
            log_cb = WorkerFactory._logged_progress("Edge Discovery", progress_cb, project.name)
            analyzer = InferredEdgesAnalyzer(
                index_dir=idx_dir,
                repo_root=project.path,
                llm_client=llm_client,
                batch_profile=batch_profile,
            )
            result = analyzer.run(progress_callback=log_cb)
            logger.info(
                "[%s/Edge Discovery] Complete — %d files analyzed, %d edges written",
                project.name, result.files_analyzed, result.edges_written,
            )

            if pfl:
                pfl.log("inferred_edges", "Inferred edges complete", {
                    "files_analyzed": result.files_analyzed,
                    "edges_found": result.edges_found,
                    "edges_written": result.edges_written,
                    "skipped_low_confidence": result.skipped_low_confidence,
                    "skipped_duplicate": result.skipped_duplicate,
                    "failed": result.failed,
                    "duration_ms": result.duration_ms,
                })

            return {
                "stage": "inferred_edges",
                "files_analyzed": result.files_analyzed,
                "edges_written": result.edges_written,
            }
        return worker

    @staticmethod
    def _augment_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import TraceAugmenter
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("small")
            idx_dir = project_index_dir(project)

            batch_profile = WorkerFactory._get_batch_profile(llm_client)

            # Verbose pipeline file logging
            try:
                from codrag.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
                pfl.log("catalogue", f"Augmenter starting: model={llm_client.model}, endpoint={llm_client.endpoint_url}, batch_profile={batch_profile.name.value if batch_profile else 'none'}")
            except Exception:
                pfl = None

            logger.info("[%s/Fast Catalogue] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Fast Catalogue", progress_cb, project.name)
            augmenter = TraceAugmenter(
                index_dir=idx_dir,
                repo_root=project.path,
                llm_client=llm_client,
                batch_profile=batch_profile,
            )
            result = augmenter.run(progress_callback=log_cb)
            logger.info(
                "[%s/Fast Catalogue] Complete — %d augmented, %d failed, %d skipped",
                project.name, result.augmented, result.failed, result.skipped,
            )

            if pfl:
                pfl.log("catalogue", "Augmentation complete", {
                    "total_nodes": result.total_nodes,
                    "augmented": result.augmented,
                    "synthetic": result.synthetic,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "coverage_pct": round((result.augmented + result.synthetic) / result.total_nodes * 100, 1) if result.total_nodes else 0,
                    "duration_ms": result.duration_ms,
                })
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

            logger.info("[%s/Validation] Starting relationship validation", project.name)
            progress_cb("Validating relationships", 0, 1)
            progress_cb("Validation complete", 1, 1)
            logger.info("[%s/Validation] Complete — trace exists=%s", project.name, trace_idx.exists())
            return {"stage": "validation", "exists": trace_idx.exists()}
        return worker

    @staticmethod
    def _knowledge_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.build_manager import build_manager

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            logger.info("[%s/Knowledge Embedding] Starting", project.name)
            log_cb = WorkerFactory._logged_progress("Knowledge Embedding", progress_cb, project.name)
            idx = build_manager.get_project_knowledge_index(project)
            result = idx.build(progress_callback=log_cb)
            logger.info("[%s/Knowledge Embedding] Complete", project.name)
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

            # Verbose pipeline file logging
            try:
                from codrag.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
                pfl.log("enrichment", f"Epistemic starting: model={llm_client.model}, endpoint={llm_client.endpoint_url}")
            except Exception:
                pfl = None

            batch_profile = WorkerFactory._get_batch_profile(llm_client)
            if pfl and batch_profile:
                pfl.log("enrichment", f"Batch profile: {batch_profile.name.value}")

            logger.info("[%s/Deep Reasoning] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Deep Reasoning", progress_cb, project.name)
            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
                batch_profile=batch_profile,
            )
            result = enricher.run(progress_callback=log_cb)
            enriched = result.get("enriched_this_run", 0)
            failed = result.get("failed_this_run", 0)
            logger.info(
                "[%s/Deep Reasoning] Complete — enriched=%s, failed=%s",
                project.name, enriched, failed,
            )

            if pfl:
                pfl.log("enrichment", "Epistemic enrichment complete", {
                    "total_file_nodes": result.get("total_file_nodes"),
                    "enriched_this_run": enriched,
                    "failed_this_run": failed,
                    "skipped": result.get("skipped"),
                    "total_enriched": result.get("total_enriched"),
                    "duration_ms": result.get("duration_ms"),
                })

            # If we attempted enrichment but got 0 results with failures,
            # treat this as a failure so the UI shows warning (not green).
            if enriched == 0 and failed > 0:
                raise RuntimeError(
                    f"Epistemic enrichment failed: 0 enriched, {failed} failed. "
                    "Check model availability, timeout settings, and num_predict."
                )
            return {"stage": "enrichment", **(result or {})}
        return worker

    @staticmethod
    def _group_reasoning_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import GroupReasoningEngine
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("large")
            idx_dir = project_index_dir(project)

            logger.info("[%s/Group Reasoning] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Group Reasoning", progress_cb, project.name)
            engine = GroupReasoningEngine(llm=llm_client, index_dir=idx_dir)
            result = engine.run(progress_callback=log_cb)
            analyzed = result.get("analyzed", 0)
            failed = result.get("failed", 0)
            logger.info(
                "[%s/Group Reasoning] Complete — %d analyzed, %d reused, %d failed",
                project.name, analyzed, result.get("reused", 0), failed,
            )
            return {"stage": "group_reasoning", **(result or {})}
        return worker

    @staticmethod
    def _cluster_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import ClusterSynthesizer
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            llm_client = WorkerFactory._get_llm_client("large")
            idx_dir = project_index_dir(project)

            batch_profile = WorkerFactory._get_batch_profile(llm_client)

            logger.info("[%s/Module Synthesis] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Module Synthesis", progress_cb, project.name)
            synthesizer = ClusterSynthesizer(llm=llm_client, index_dir=idx_dir, batch_profile=batch_profile)
            result = synthesizer.run(progress_callback=log_cb)
            logger.info("[%s/Module Synthesis] Complete", project.name)
            return {"stage": "clustering", **(result or {})}
        return worker

    @staticmethod
    def _atlas_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core.atlas import CodebaseAtlas
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            # Use large LLM if available; fall back to structural atlas
            try:
                llm_client = WorkerFactory._get_llm_client("large")
                # Atlas generates 4096 tokens of free-form prose — thinking
                # models need much longer than the default 60s timeout.
                llm_client.timeout = 300.0
            except RuntimeError:
                llm_client = None

            logger.info("[%s/Atlas] Starting atlas generation", project.name)
            log_cb = WorkerFactory._logged_progress("Atlas", progress_cb, project.name)
            atlas = CodebaseAtlas(idx_dir, llm=llm_client, project_root=Path(project.path))

            # Only regenerate if stale or missing
            if not atlas.is_stale() and atlas.exists():
                logger.info("[Atlas] Up-to-date — skipping regeneration")
                log_cb("Atlas up-to-date", 1, 1)
                doc = atlas.load()
                result = {
                    "stage": "atlas",
                    "skipped": True,
                    "chars": doc.char_count if doc else 0,
                    "mode": doc.mode if doc else "none",
                }
            else:
                # Use segmented generation — produces root + per-segment atlases.
                # Falls back to single atlas if <2 segments are discovered.
                doc, segment_docs = atlas.generate_segmented(progress_callback=log_cb)
                result = {
                    "stage": "atlas",
                    "skipped": False,
                    "chars": doc.char_count,
                    "mode": doc.mode,
                    "file_count": doc.file_count,
                    "module_count": doc.module_count,
                    "segment_count": len(segment_docs),
                }

            # Generate routing index (pre-retrieval segment selection)
            try:
                from codrag.services.build_manager import build_manager
                embedder = build_manager.create_embedder()
                routing_descs = atlas.generate_routing(embedder, progress_callback=log_cb)
                result["routing_segments"] = len(routing_descs)
                logger.info("[Atlas] Routing complete — %d segments", len(routing_descs))
            except Exception as e:
                logger.info("[Atlas] Routing generation skipped: %s", e)
                result["routing_segments"] = 0

            return result
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
            logger.info("[%s/Deepening] Starting deepening loop: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Deepening", progress_cb, project.name)
            loop = DeepeningLoop(
                enricher=enricher,
                index_dir=idx_dir,
                max_iterations=10,
                batch_size=20,
            )
            result = loop.run(progress_callback=log_cb)
            logger.info(
                "[Deepening] Complete — %d iterations, converged=%s",
                result.iterations, bool(result.convergence),
            )
            return {
                "stage": "deepening",
                "iterations": result.iterations,
                "converged": bool(result.convergence),
            }
        return worker


# ── Pipeline Orchestrator ────────────────────────────────────────

class PipelineOrchestrator:
    """Sequences the 11-stage pipeline in two groups.

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
        # Per-project pipeline file loggers
        self._file_loggers: Dict[str, Any] = {}
        # Register for build completion events
        self._orchestrator.add_listener(self._on_build_transition)
        # Phase 25: cached crashed runs discovered at startup
        self._crashed_runs: List[Any] = []

    def _get_file_logger(self, project_id: str):
        """Get or create a PipelineFileLogger for a project."""
        if project_id not in self._file_loggers:
            try:
                from codrag.services.project_helpers import require_project
                from codrag.core.project_registry import project_index_dir
                project = require_project(project_id)
                idx_dir = project_index_dir(project)
                from codrag.services.pipeline_logger import PipelineFileLogger
                self._file_loggers[project_id] = PipelineFileLogger(idx_dir)
            except Exception:
                logger.debug("Could not create pipeline file logger for %s", project_id, exc_info=True)
                self._file_loggers[project_id] = None
        return self._file_loggers.get(project_id)

    # ── Public API ─────────────────────────────────────────────

    def run_fast_sync(self, project_id: str) -> bool:
        """Start the Fast Sync group (stages 1-5).  Returns False if already running."""
        return self._start_group(project_id, "fast_sync", FAST_SYNC_STAGES)

    def run_deep_enrichment(self, project_id: str) -> bool:
        """Start the Deep Enrichment group (stages 6-10).  Returns False if already running."""
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
        # Clear cached file logger so it doesn't reference stale paths
        self._file_loggers.pop(project_id, None)

    # ── Internal ───────────────────────────────────────────────

    @staticmethod
    def _is_deep_enrichment_auto(project_id: str) -> bool:
        """Check if deep enrichment should auto-chain after fast sync.

        Returns True if either:
        - deep_enrichment.mode is 'auto', OR
        - fast_sync.auto is True (user expectation: AUTO runs the full pipeline)
        """
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            deep_mode = (config.get("deep_enrichment") or {}).get("mode", "manual")
            fast_auto = (config.get("fast_sync") or {}).get("auto", False)
            return deep_mode == "auto" or fast_auto
        except Exception:
            return False

    def _start_group(
        self, project_id: str, group: str, stages: List[StageId],
        chain_deep: bool = False, resume_from: int = 0,
    ) -> bool:
        """Start a group of stages sequentially.

        Returns False if this group OR any other group for the same
        project is already active — groups share files and must not
        run concurrently.
        """
        with self._lock:
            # Block if this group is already running
            key = (project_id, group)
            existing = self._runs.get(key)
            if existing and existing.is_active:
                return False

            # Block if ANY other group for the same project is running.
            # Fast Sync and Deep Enrichment share trace files (knowledge,
            # modules, epistemic) and running them concurrently causes
            # data corruption (e.g. knowledge embedding "doubling").
            for run_key, run_obj in self._runs.items():
                if run_key[0] == project_id and run_key[1] != group and run_obj.is_active:
                    logger.warning(
                        "Cannot start %s/%s — %s is already active for this project",
                        project_id, group, run_key[1],
                    )
                    return False

            run = PipelineRun(
                project_id=project_id,
                group=group,
                stages=list(stages),
                phase=PipelineRunPhase.RUNNING,
                started_at=time.time(),
                current_stage_index=resume_from,
            )
            self._runs[key] = run

        # Start pipeline file logger for this run
        pfl = self._get_file_logger(project_id)
        if pfl:
            pfl.start_run(group, [s.value for s in stages], project_id=project_id)

        # Phase 25: persist intent to journal before starting work
        try:
            from codrag.services.pipeline_journal import journal
            run_id = journal.start_run(
                project_id, group,
                [s.value for s in stages],
                chain_deep=chain_deep,
            )
            run.journal_run_id = run_id
            # If resuming, mark already-completed stages
            if resume_from > 0:
                for i in range(resume_from):
                    stage_val = stages[i].value
                    run.stage_results[stage_val] = "completed"
                    journal.stage_completed(run_id, stage_val)
                journal.stage_started(run_id, stages[resume_from].value, resume_from)
        except Exception:
            logger.debug("Journal write failed (non-fatal)", exc_info=True)

        # Start the first (or resumed) stage
        self._advance_pipeline(run)
        return True

    def _advance_pipeline(self, run: PipelineRun) -> None:
        """Advance to the next stage in the pipeline, or finish."""
        pfl = self._get_file_logger(run.project_id)
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
            if pfl:
                pfl.end_run("completed")
            # VRAM lifecycle: unload models used by this group
            self._unload_group_models(run)
            # Phase 25: journal — mark run completed + cleanup checkpoint
            self._journal_run_completed(run)
            # After any group completes, trigger CodeIndex build so
            # /context search works and file tree status badges update.
            if run.group in ("fast_sync", "deep_enrichment"):
                self._trigger_code_index_build(run.project_id, pfl)
            # Chain deep enrichment after fast sync if configured or explicitly requested
            if run.group == "fast_sync":
                should_chain = False
                chain_reason = "none"
                # 1. Explicit chain from run_all()
                chain_deep = getattr(self, "_chain_deep", {})
                if chain_deep.pop(run.project_id, False):
                    should_chain = True
                    chain_reason = "explicit_run_all"
                # 2. Auto-chain: check persisted pipeline config
                if not should_chain:
                    is_auto = self._is_deep_enrichment_auto(run.project_id)
                    logger.info(
                        "Auto-chain check for %s: _is_deep_enrichment_auto=%s",
                        run.project_id, is_auto,
                    )
                    if is_auto:
                        should_chain = True
                        chain_reason = "auto_config"
                # Phase 26 (S-26.5): Budget throttle — skip auto-chain if budget exhausted
                if should_chain and chain_reason != "explicit_run_all":
                    try:
                        from codrag.services.pipeline_budget import budget as _budget
                        if not _budget.check_allowed(run.project_id):
                            usage = _budget.get_usage(run.project_id)
                            logger.info(
                                "Budget exhausted for %s — skipping auto-chain "
                                "(used %d/%d tokens, resets in %ds)",
                                run.project_id,
                                usage["tokens_used"], usage["max_tokens"],
                                usage["window_resets_in"],
                            )
                            if pfl:
                                pfl.log("fast_sync", f"Auto-chain SKIPPED: budget exhausted ({usage['tokens_used']}/{usage['max_tokens']} tokens)")
                            should_chain = False
                            chain_reason = "budget_exhausted"
                    except Exception:
                        pass  # Budget module unavailable — allow chain

                if should_chain:
                    logger.info(
                        "Chaining deep enrichment after fast sync for %s (reason=%s)",
                        run.project_id, chain_reason,
                    )
                    try:
                        started = self.run_deep_enrichment(run.project_id)
                        logger.info(
                            "Deep enrichment chain result for %s: started=%s",
                            run.project_id, started,
                        )
                        if pfl:
                            pfl.log("fast_sync", f"Auto-chained deep enrichment: started={started}, reason={chain_reason}")
                    except Exception as chain_exc:
                        logger.exception(
                            "Failed to chain deep enrichment for %s: %s",
                            run.project_id, chain_exc,
                        )
                        if pfl:
                            pfl.log("fast_sync", f"Auto-chain FAILED: {chain_exc}")
                else:
                    logger.info(
                        "NOT chaining deep enrichment for %s (reason=%s)",
                        run.project_id, chain_reason,
                    )
            return

        stage = run.stages[run.current_stage_index]
        build_type = STAGE_BUILD_TYPE[stage]

        # VRAM lifecycle: unload previous model if the slot is changing
        self._maybe_unload_previous_model(run, stage)

        logger.info(
            "Pipeline %s/%s — starting stage %d/%d: %s",
            run.project_id, run.group,
            run.current_stage_index + 1, len(run.stages),
            stage.value,
        )
        if pfl:
            pfl.stage_start(stage.value, {
                "stage_index": run.current_stage_index,
                "total_stages": len(run.stages),
                "group": run.group,
            })

        # Phase 25: journal — record stage start
        self._journal_stage_started(run, stage)

        # Phase 25: checkpoint — backup trace files before destructive stages
        self._create_checkpoint_if_needed(run, stage)

        worker = WorkerFactory.create_worker(run.project_id, stage)
        started = self._orchestrator.start(run.project_id, build_type, worker)

        if not started:
            # Build slot is stuck in RUNNING/QUEUED from a prior run.
            # Force-reset it and retry once so the pipeline doesn't stall.
            logger.warning(
                "Stage %s slot already active for %s — force-resetting stuck slot",
                stage.value, run.project_id,
            )
            self._orchestrator.cancel(run.project_id, build_type)
            # Small delay to let the slot settle after cancel
            time.sleep(0.1)
            started = self._orchestrator.start(run.project_id, build_type, worker)
            if not started:
                raise RuntimeError(
                    f"Cannot start stage {stage.value}: build slot {build_type.value} "
                    f"is stuck for project {run.project_id}"
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
                # Pipeline file logger
                pfl = self._get_file_logger(project_id)
                if pfl:
                    slot = self._orchestrator.status(project_id, build_type)
                    pfl.stage_end(stage.value, "completed", data={
                        "result": slot.result,
                        "duration": slot.duration_seconds,
                    })
                    pfl.transition(build_type.value, old_phase.value, new_phase.value,
                                   f"Stage {stage.value} completed")
                # Phase 25: journal — record stage completion
                self._journal_stage_completed(matching_run, stage)
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
                # Pipeline file logger
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.stage_end(stage.value, "failed", error=slot.error, data={
                        "duration": slot.duration_seconds,
                    })
                    pfl.end_run("failed", error=slot.error)
                # Phase 25: journal — record stage failure
                self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
                # VRAM lifecycle: unload models on failure
                self._unload_group_models(matching_run)
                return

        # Advance outside the lock — wrapped in try/except so a failure
        # in stage creation marks the run FAILED instead of silently stalling.
        if matching_run and matching_run.is_active:
            try:
                self._advance_pipeline(matching_run)
            except Exception as exc:
                logger.exception(
                    "Pipeline %s/%s — _advance_pipeline failed after stage %s: %s",
                    matching_run.project_id, matching_run.group,
                    stage.value if stage else "?", exc,
                )
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.log(stage.value if stage else "unknown",
                            f"_advance_pipeline failed: {exc}")
                    pfl.end_run("failed", error=str(exc))
                with self._lock:
                    matching_run.phase = PipelineRunPhase.FAILED
                    matching_run.finished_at = time.time()
                    matching_run.error = f"Failed to advance after {stage.value if stage else '?'}: {exc}"

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

        # Phase 25: journal — record cancellation
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal cancel write failed", exc_info=True)
        return True

    # ── VRAM Lifecycle ─────────────────────────────────────────────

    def _maybe_unload_previous_model(self, run: PipelineRun, next_stage: StageId) -> None:
        """Unload the previous stage's LLM model if the slot is changing.

        Prevents two models from occupying VRAM simultaneously.
        Only acts when transitioning between different model slots
        (e.g. small→None, small→large, large→None).

        Non-fatal: logs warnings on failure but never blocks the pipeline.
        """
        next_slot = STAGE_MODEL_SLOT.get(next_stage)

        # Determine the previous stage's slot
        prev_slot: Optional[str] = None
        if run.current_stage_index > 0:
            prev_stage = run.stages[run.current_stage_index - 1]
            prev_slot = STAGE_MODEL_SLOT.get(prev_stage)

        # No transition needed if slot hasn't changed, or previous had no model
        if prev_slot is None or prev_slot == next_slot:
            return

        # Unload the previous model
        try:
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot(prev_slot)
            if client:
                logger.info(
                    "VRAM lifecycle: unloading %s model (%s) before stage %s",
                    prev_slot, client.model, next_stage.value,
                )
                client.unload()
        except Exception as e:
            logger.warning("VRAM lifecycle: failed to unload %s model: %s", prev_slot, e)

    def _unload_group_models(self, run: PipelineRun) -> None:
        """Unload any LLM models used by the completed/failed group.

        Called when a pipeline group finishes to free VRAM for the next
        group or for the user's own work.
        """
        # Find the last model slot used in this group's stages
        slots_used = set()
        for stage in run.stages:
            slot = STAGE_MODEL_SLOT.get(stage)
            if slot:
                slots_used.add(slot)

        for slot_name in slots_used:
            try:
                from codrag.server import _get_llm_client_for_slot
                client = _get_llm_client_for_slot(slot_name)
                if client:
                    logger.info("VRAM lifecycle: unloading %s model (%s) — group %s finished",
                                slot_name, client.model, run.group)
                    client.unload()
            except Exception as e:
                logger.warning("VRAM lifecycle: failed to unload %s model after group: %s", slot_name, e)

    # ── CodeIndex Build (post-pipeline) ─────────────────────────────

    def _trigger_code_index_build(self, project_id: str, pfl: Any = None) -> None:
        """Trigger a CodeIndex build after deep enrichment completes.

        The pipeline builds KnowledgeIndex (knowledge_documents.json) but the
        /context search endpoint requires CodeIndex (documents.json +
        embeddings.npy).  This fires the build in the background so search
        works immediately after the pipeline finishes.
        """
        try:
            from codrag.services.build_manager import build_manager
            from codrag.services.project_helpers import require_project

            project = require_project(project_id)
            cfg = project.config or {}
            include_globs = cfg.get("include_globs") or None
            exclude_globs = cfg.get("exclude_globs") or None
            max_file_bytes = int(cfg.get("max_file_bytes") or 500_000)
            hard_limit_bytes = int(cfg.get("hard_limit_bytes") or 100_000_000)
            included_paths = cfg.get("included_paths") or None

            started = build_manager.start_project_build(
                project, None, include_globs, exclude_globs,
                max_file_bytes, hard_limit_bytes,
                included_paths=included_paths,
            )
            logger.info(
                "CodeIndex build triggered for %s after pipeline: started=%s",
                project_id, started,
            )
            if pfl:
                pfl.log("code_index", f"CodeIndex build triggered: started={started}")
        except Exception as e:
            logger.warning("Failed to trigger CodeIndex build for %s: %s", project_id, e)
            if pfl:
                pfl.log("code_index", f"CodeIndex build FAILED: {e}")

    # ── Phase 25: Journal Helpers ─────────────────────────────────

    def _journal_stage_started(self, run: PipelineRun, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_started(run.journal_run_id, stage.value, run.current_stage_index)
        except Exception:
            logger.debug("Journal stage_started write failed", exc_info=True)

    def _journal_stage_completed(self, run: PipelineRun, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_completed(run.journal_run_id, stage.value)
        except Exception:
            logger.debug("Journal stage_completed write failed", exc_info=True)

    def _journal_stage_failed(self, run: PipelineRun, stage: StageId, error: str) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_failed(run.journal_run_id, stage.value, error)
        except Exception:
            logger.debug("Journal stage_failed write failed", exc_info=True)

    def _journal_run_completed(self, run: PipelineRun) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.run_completed(run.journal_run_id)
        except Exception:
            logger.debug("Journal run_completed write failed", exc_info=True)
        # Cleanup checkpoint
        try:
            from codrag.services.pipeline_journal import journal as j
            entry = j.get_run(run.journal_run_id)
            if entry and entry.checkpoint_path:
                from codrag.services.pipeline_checkpoint import cleanup_checkpoint
                cleanup_checkpoint(entry.checkpoint_path)
        except Exception:
            logger.debug("Checkpoint cleanup failed", exc_info=True)

    def _create_checkpoint_if_needed(self, run: PipelineRun, stage: StageId) -> None:
        """Create a checkpoint before destructive stages."""
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_checkpoint import create_checkpoint, CHECKPOINT_STAGES
            if stage.value not in CHECKPOINT_STAGES:
                return
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            project = require_project(run.project_id)
            idx_dir = project_index_dir(project)
            cp_path = create_checkpoint(idx_dir, run.journal_run_id, stage.value)
            if cp_path:
                from codrag.services.pipeline_journal import journal
                journal.set_checkpoint(run.journal_run_id, cp_path)
        except Exception:
            logger.debug("Checkpoint creation failed (non-fatal)", exc_info=True)

    # ── Phase 25: Crash Recovery ──────────────────────────────────

    def startup_recovery(self) -> List[Any]:
        """Called once on daemon startup.  Detects crashed runs.

        Returns list of JournalEntry dicts for the UI to display.
        """
        try:
            from codrag.services.pipeline_journal import journal
            crashed = journal.recover_crashed_runs()
            self._crashed_runs = crashed
            if crashed:
                logger.warning(
                    "Crash recovery: found %d crashed pipeline run(s)", len(crashed)
                )
                # Auto-heal: verify trace files for each crashed project
                for entry in crashed:
                    try:
                        from codrag.services.pipeline_checkpoint import verify_trace_files, auto_heal
                        from codrag.core.project_registry import project_index_dir
                        from codrag.services.project_helpers import require_project
                        project = require_project(entry.project_id)
                        idx_dir = project_index_dir(project)
                        valid, corrupt = verify_trace_files(idx_dir)
                        if not valid:
                            logger.warning(
                                "Corrupt trace files for %s: %s — attempting auto-heal",
                                entry.project_id, corrupt,
                            )
                            results = auto_heal(idx_dir, entry.checkpoint_path)
                            logger.info("Auto-heal results for %s: %s", entry.project_id, results)
                    except Exception:
                        logger.debug("Auto-heal failed for %s", entry.project_id, exc_info=True)
            return [e.to_dict() for e in crashed]
        except Exception:
            logger.debug("Startup recovery failed", exc_info=True)
            return []

    def get_crashed_runs(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get crashed runs (for UI display)."""
        try:
            from codrag.services.pipeline_journal import journal
            entries = journal.get_crashed_runs(project_id)
            return [e.to_dict() for e in entries]
        except Exception:
            return []

    def resume_crashed_run(self, run_id: str) -> bool:
        """Resume a crashed pipeline run from the stage it was on.

        Creates a new run starting from the crashed stage.
        Returns True if resumed successfully.
        """
        try:
            from codrag.services.pipeline_journal import journal
            entry = journal.get_run(run_id)
            if not entry or entry.status != "crashed":
                return False

            # Resolve the crashed run
            journal.resolve_crashed_run(run_id, "resumed")

            # Determine stages and resume point
            if entry.group == "fast_sync":
                stages = FAST_SYNC_STAGES
            elif entry.group == "deep_enrichment":
                stages = DEEP_ENRICHMENT_STAGES
            else:
                return False

            resume_from = entry.current_stage_index
            chain_deep = entry.chain_deep

            logger.info(
                "Resuming crashed run %s: %s/%s from stage %d (%s)",
                run_id, entry.project_id, entry.group,
                resume_from, entry.current_stage,
            )

            return self._start_group(
                entry.project_id, entry.group, stages,
                chain_deep=chain_deep, resume_from=resume_from,
            )
        except Exception:
            logger.exception("Resume failed for run %s", run_id)
            return False

    def discard_crashed_run(self, run_id: str) -> bool:
        """Discard a crashed pipeline run without resuming."""
        try:
            from codrag.services.pipeline_journal import journal
            return journal.resolve_crashed_run(run_id, "discarded")
        except Exception:
            return False


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
