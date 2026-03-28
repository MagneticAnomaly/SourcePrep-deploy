"""
Pipeline worker factory — creates worker callables for each pipeline stage.
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

from .stages import (
    StageId, STAGE_TASK_ID, STAGE_MODEL_SLOT,
    STAGE_MANIFEST_FILE, STAGE_OUTPUT_FILE, STAGE_CONFIDENCE_FIELD,
)

logger = logging.getLogger(__name__)


def _capture_model_info(llm_client) -> Dict[str, Any]:
    """Extract model provenance info from an LLMClient for manifest writing."""
    if llm_client is None:
        return {}
    try:
        from codrag.core.provenance import extract_model_info_from_llm_client
        return extract_model_info_from_llm_client(llm_client)
    except Exception:
        return {"model_name": getattr(llm_client, "model", "unknown")}


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
            base_worker = WorkerFactory._trace_worker(project_id)
        elif stage == StageId.INFERRED_EDGES:
            base_worker = WorkerFactory._inferred_edges_worker(project_id)
        elif stage == StageId.CATALOGUE:
            base_worker = WorkerFactory._augment_worker(project_id)
        elif stage == StageId.VALIDATION:
            base_worker = WorkerFactory._validate_worker(project_id)
        elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
            base_worker = WorkerFactory._knowledge_worker(project_id)
        elif stage == StageId.ENRICHMENT:
            base_worker = WorkerFactory._epistemic_worker(project_id)
        elif stage == StageId.GROUP_REASONING:
            base_worker = WorkerFactory._group_reasoning_worker(project_id)
        elif stage == StageId.CLUSTERING:
            base_worker = WorkerFactory._cluster_worker(project_id)
        elif stage == StageId.ATLAS:
            base_worker = WorkerFactory._atlas_worker(project_id)
        elif stage == StageId.DEEPENING:
            base_worker = WorkerFactory._deepening_worker(project_id)
        else:
            raise ValueError(f"Unknown stage: {stage}")

        def wrapped_worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.token_telemetry import set_telemetry_context
            with set_telemetry_context(project_id, stage.value):
                return base_worker(slot, progress_cb)

        return wrapped_worker

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
    def _get_llm_client_for_task(task_id: str):
        """Get an LLM client for the given task, with availability check.

        Phase 44: Uses the unified resolver which respects assignment_mode.
        Raises RuntimeError if no model is configured or endpoint is unreachable.
        """
        from codrag.server import _get_llm_client_for_task

        client = _get_llm_client_for_task(task_id)
        if not client:
            raise RuntimeError(f"No model configured for task '{task_id}'. Configure a model in AI Models settings.")
        if not client.is_available():
            raise RuntimeError(f"Model endpoint not reachable: {client.endpoint_url}")
        return client

    @staticmethod
    def _get_llm_client(slot_name: str):
        """Legacy helper — resolves via slot name.  Prefer _get_llm_client_for_task()."""
        from codrag.server import _get_llm_client_for_slot

        client = _get_llm_client_for_slot(slot_name)
        if not client and slot_name in ("large", "code"):
            client = _get_llm_client_for_slot("small")
        if not client:
            raise RuntimeError(f"No {slot_name} model configured. Configure a model in AI Models settings.")
        if not client.is_available():
            raise RuntimeError(f"Model endpoint not reachable: {client.endpoint_url}")
        return client

    @staticmethod
    def _get_batch_profile(llm_client):
        """Detect the batch profile for an LLM client.

        Resolution order:
        1. Context-window-based detection (from persisted model_context_cache)
        2. Regex-based model name detection (fallback)
        """
        try:
            from codrag.core.batch_profiles import resolve_profile
            from codrag.server import _load_ui_config
            ui_cfg = _load_ui_config()
            llm_cfg = ui_cfg.get("llm_config") or {}

            # Look up context_tokens from persisted model_context_cache
            context_tokens = None
            try:
                cache = llm_cfg.get("model_context_cache") or {}
                ctx = cache.get(llm_client.model)
                if isinstance(ctx, (int, float)) and ctx > 0:
                    context_tokens = int(ctx)
            except Exception:
                pass

            return resolve_profile(
                llm_client.provider, llm_client.model,
                context_tokens=context_tokens,
            )
        except Exception:
            return None

    @staticmethod
    def _logged_progress(stage_name: str, progress_cb: Callable, project_name: str = "") -> Callable:
        """Wrap a progress callback to also emit logger.info for Process Logs."""
        tag = f"{project_name}/{stage_name}" if project_name else stage_name
        def _wrapper(message: str, current: int, total: int, baseline: int = 0) -> None:
            progress_cb(message, current, total, baseline)
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
            _t0 = time.time()
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

            return {
                "stage": "structural",
                "nodes": trace_idx.node_count(),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _inferred_edges_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import InferredEdgesAnalyzer
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            # Phase 44: resolve via task ID (respects structured/mapped mode)
            try:
                llm_client = WorkerFactory._get_llm_client_for_task("inferred_edges")
            except RuntimeError:
                logger.info("[Edge Discovery] No model available for inferred_edges task — skipping")
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

            _t0 = time.time()
            logger.info("[%s/Edge Discovery] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Edge Discovery", progress_cb, project.name)
            analyzer = InferredEdgesAnalyzer(
                index_dir=idx_dir,
                repo_root=project.path,
                llm_client=llm_client,
                batch_profile=batch_profile,
            )
            result = analyzer.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
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
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _augment_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import TraceAugmenter
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("catalogue")
            except RuntimeError:
                logger.info("[Fast Catalogue] No model available for catalogue task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "catalogue", "skipped": True, "reason": "no_llm"}

            batch_profile = WorkerFactory._get_batch_profile(llm_client)

            # Verbose pipeline file logging
            try:
                from codrag.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
                pfl.log("catalogue", f"Augmenter starting: model={llm_client.model}, endpoint={llm_client.endpoint_url}, batch_profile={batch_profile.name.value if batch_profile else 'none'}")
            except Exception:
                pfl = None

            _t0 = time.time()
            logger.info("[%s/Fast Catalogue] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Fast Catalogue", progress_cb, project.name)
            augmenter = TraceAugmenter(
                index_dir=idx_dir,
                repo_root=project.path,
                llm_client=llm_client,
                batch_profile=batch_profile,
            )
            result = augmenter.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
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
                    "batches_attempted": result.batches_attempted,
                    "batches_failed": result.batches_failed,
                    "items_batched": result.items_batched,
                    "items_parsed": result.items_parsed,
                    "max_prompt_tokens": result.max_prompt_tokens,
                })
            
            model_info = _capture_model_info(llm_client)
            if hasattr(result, "batches_attempted") and result.batches_attempted > 0:
                model_info["telemetry"] = {
                    "batches_attempted": result.batches_attempted,
                    "batches_failed": result.batches_failed,
                    "items_batched": result.items_batched,
                    "items_parsed": result.items_parsed,
                    "max_prompt_tokens": result.max_prompt_tokens,
                    "avg_prompt_tokens": round(result.total_prompt_tokens / result.batches_attempted) if result.batches_attempted else 0,
                    "model_ctx_size": result.model_ctx_size,
                    "parse_success_rate": round(result.items_parsed / result.items_batched * 100, 1) if result.items_batched else 0,
                    "synthetic_reasons": getattr(result, "synthetic_reasons", {}),
                }
                
            return {
                "stage": "catalogue",
                "augmented": result.augmented,
                "total_nodes": result.total_nodes,
                "failed": result.failed,
                "skipped": result.skipped,
                "synthetic": result.synthetic,
                "_model_info": model_info,
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
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

            _t0 = time.time()
            logger.info("[%s/Validation] Starting relationship validation", project.name)
            progress_cb("Validating relationships", 0, 1)
            progress_cb("Validation complete", 1, 1)
            logger.info("[%s/Validation] Complete — trace exists=%s", project.name, trace_idx.exists())
            return {
                "stage": "validation",
                "exists": trace_idx.exists(),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _knowledge_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.services.build_manager import build_manager

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            _t0 = time.time()
            logger.info("[%s/Knowledge Embedding] Starting", project.name)
            log_cb = WorkerFactory._logged_progress("Knowledge Embedding", progress_cb, project.name)
            idx = build_manager.get_project_knowledge_index(project)
            result = idx.build(progress_callback=log_cb)
            logger.info("[%s/Knowledge Embedding] Complete", project.name)
            return {
                "stage": "knowledge",
                **(result or {}),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _epistemic_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import EpistemicEnricher
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("enrichment")
            except RuntimeError:
                logger.info("[Deep Reasoning] No model available for enrichment task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "enrichment", "skipped": True, "reason": "no_llm"}

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

            _t0 = time.time()
            logger.info("[%s/Deep Reasoning] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Deep Reasoning", progress_cb, project.name)
            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
                batch_profile=batch_profile,
            )
            result = enricher.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
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
            return {
                "stage": "enrichment",
                **(result or {}),
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _group_reasoning_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import GroupReasoningEngine
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("group_reasoning")
            except RuntimeError:
                logger.info("[Group Reasoning] No model available for group_reasoning task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "group_reasoning", "skipped": True, "reason": "no_llm"}

            _t0 = time.time()
            logger.info("[%s/Group Reasoning] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Group Reasoning", progress_cb, project.name)
            engine = GroupReasoningEngine(llm=llm_client, index_dir=idx_dir)
            result = engine.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
            analyzed = result.get("analyzed", 0)
            failed = result.get("failed", 0)
            
            # If all attempts failed, abort so the pipeline pauses/reverts
            # instead of skipping the stage silently.
            if analyzed == 0 and failed > 0:
                raise RuntimeError(
                    f"Group reasoning failed: 0 analyzed, {failed} failed. "
                    "Check model availability, timeout settings, and num_predict."
                )
                
            logger.info(
                "[%s/Group Reasoning] Complete — %d analyzed, %d reused, %d failed",
                project.name, analyzed, result.get("reused", 0), failed,
            )
            return {
                "stage": "group_reasoning",
                **(result or {}),
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _cluster_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import ClusterSynthesizer
            from codrag.core.project_registry import project_index_dir

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("clustering")
            except RuntimeError:
                logger.info("[Module Synthesis] No model available for clustering task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "clustering", "skipped": True, "reason": "no_llm"}

            batch_profile = WorkerFactory._get_batch_profile(llm_client)

            _t0 = time.time()
            logger.info("[%s/Module Synthesis] Starting: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Module Synthesis", progress_cb, project.name)
            synthesizer = ClusterSynthesizer(llm=llm_client, index_dir=idx_dir, batch_profile=batch_profile)
            result = synthesizer.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
            
            synthesized = result.get("synthesized", 0)
            failed = result.get("failed", 0)
            
            # If all attempts failed, abort so pipeline correctly pauses/reverts
            if synthesized == 0 and failed > 0:
                raise RuntimeError(
                    f"Module synthesis failed: 0 synthesized, {failed} failed. "
                    "Check model availability, timeout settings, and num_predict."
                )
                
            logger.info("[%s/Module Synthesis] Complete", project.name)
            return {
                "stage": "clustering",
                **(result or {}),
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _atlas_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core.atlas import CodebaseAtlas
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            # Use task-assigned LLM if available; fall back to structural atlas
            try:
                llm_client = WorkerFactory._get_llm_client_for_task("atlas")
                # Atlas generates 4096 tokens of free-form prose — thinking
                # models need much longer than the default 60s timeout.
                llm_client.timeout = 300.0
            except RuntimeError:
                llm_client = None

            _t0 = time.time()
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

            result["_model_info"] = _capture_model_info(llm_client) if llm_client else {}
            result["_stage_timing"] = {"started_at": _t0, "elapsed": time.time() - _t0}
            return result
        return worker

    @staticmethod
    def _deepening_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from codrag.core import EpistemicEnricher, DeepeningLoop
            from codrag.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("deepening")
            except RuntimeError:
                logger.info("[Deepening] No model available for deepening task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                return {"stage": "deepening", "skipped": True, "reason": "no_llm"}

            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
            )
            _t0 = time.time()
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
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker


# ── Pipeline Orchestrator ────────────────────────────────────────
