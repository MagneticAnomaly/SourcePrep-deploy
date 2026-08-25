"""
Pipeline worker factory — creates worker callables for each pipeline stage.

Phase 134: WorkerFactory.create_worker now loads the project Changeset
from disk and injects it onto the returned callable as `.changeset`.
Downstream consumers call worker.changeset.should_process(path) to gate
per-file work instead of performing independent hash comparisons.
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from prep.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
    build_orchestrator,
)

from prep.services.pipeline.stages import (
    StageId, STAGE_TASK_ID, STAGE_MODEL_SLOT,
    STAGE_MANIFEST_FILE, STAGE_OUTPUT_FILE, STAGE_CONFIDENCE_FIELD,
)
from prep.services.pipeline.scheduler import pipeline_scheduler
from .base import Worker  # Phase 134: worker contract

logger = logging.getLogger(__name__)


def _capture_model_info(llm_client) -> Dict[str, Any]:
    """Extract model provenance info from an LLMClient for manifest writing."""
    if llm_client is None:
        return {}
    try:
        from prep.core.provenance import extract_model_info_from_llm_client
        return extract_model_info_from_llm_client(llm_client)
    except Exception:
        return {"model_name": getattr(llm_client, "model", "unknown")}


def _should_dispatch_or_pause(
    *,
    project_id: str,
    endpoint_id: str,
    poll_interval_s: float = 1.0,
    max_wait_s: float = 600.0,
) -> bool:
    """Phase 127 soft-hold check called by stage workers before each LLM
    dispatch.

    Returns True when the worker may dispatch (no hold OR hold cleared
    within ``max_wait_s``).  Returns False if the hold is still active
    after ``max_wait_s`` — caller should checkpoint and exit cleanly.

    The poll interval is deliberately coarse; long-running LLM calls
    don't notice this overhead because the check fires only between
    dispatches.
    """
    deadline = time.monotonic() + max_wait_s
    while True:
        if not pipeline_scheduler.is_held(project_id, endpoint_id):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval_s)


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


# ── Deepening override-key helper (PR-S-fixup-r2) ────────────────


def _compute_deepening_override_keys(
    enricher: Any,
    *,
    idx_dir: Optional[Path] = None,
    project_id: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Compute (_expected_total, _processed_count) for the deepening
    worker_result override.

    §9.3 #32 evolution — round-2 scrutiny corrections F-1/F-2/F-3/
    F-5/F-6/F-7 (supersedes PR-S-fixup-r1's convergence-preferred
    strategy).

    Single source of truth: file-node scope read with TWO filters.

      Denominator: count of file_nodes with kind == "file" AND
        non-empty content (matches ENRICHMENT's scope at
        epistemic_enrichment.py:1037-1045 so the "Deep Reasoning"
        and "Continuous Deepening" chips share a denominator).

      Numerator: count of in-scope entries with pass_number >= 3
        (DEEPENING-touched). ENRICHMENT writes pass_number = 2
        (epistemic_score.py:86 default); DEEPENING always writes
        max(prev+1, 3) per PR-S-fixup-r2 F-2 (deepening.py:497, 554).

    Why convergence path was DROPPED (PR-S-fixup-r1's preferred
    path, removed in PR-S-fixup-r2 per scrutiny F-1):
      - convergence.total_count comes from compute_all_scores
        (epistemic_enrichment.py:1346) which applies NO empty-file
        filter → denominator drifts from ENRICHMENT's by the count
        of empty file nodes.
      - convergence.settled_count = "node has score >= threshold",
        which mixes ENRICHMENT and DEEPENING semantics (an
        ENRICHMENT-high-confidence node was always settled, even
        without deepening touching it). Not the chip semantic
        we want.
      The scope+pass_number read is uniformly the right answer.

    Edge cases:
      - Empty project (no file_nodes): returns (0, 0). Caller emits
        the keys so the chip shows 0/0 (no work to do) rather than
        falling back to JSONL semantics (the §9.3 #32 bug). F-5.
      - Read failure: returns (None, None). WARNING + telemetry are
        emitted from THIS function's except block where the
        exception is still in scope, so exc_info and per-exception
        payload are preserved (PR-S-fixup-r1 had moved them to the
        caller and lost both). F-3.

    idx_dir/project_id are required for failure telemetry. When
    None, the WARNING still fires but no telemetry event is emitted.

    PR-S-fixup-r3 cleanup: dropped the `deepening_result` parameter
    that PR-S-fixup-r2 kept "for backward compatibility". A module-
    private helper with one caller has no backward-compat surface;
    the parameter was a foot-gun inviting future re-introduction of
    the convergence path that two rounds of scrutiny dropped. If a
    future PR genuinely needs DeepeningResult context, that becomes
    a deliberate API addition.

    I/O cost note: this helper ALWAYS reads disk (load_trace_nodes
    + load_existing + _get_file_excerpt for each file). On a 10k-
    file project that's ~10k file-line-reads + 2 jsonl parses post-
    LLM. Cost is acceptable relative to LLM-bound deepening (minutes)
    but is the reason a future profiler might be tempted to revert
    to convergence-only path. DON'T — convergence has the FIXUP-1
    denominator drift documented above.
    """
    import json as _json

    try:
        all_nodes = enricher.load_trace_nodes()
        file_nodes: List[Dict[str, Any]] = []
        for n in all_nodes:
            if n.get("kind") != "file":
                continue
            # Empty-file filter — matches ENRICHMENT scope. Excludes
            # empty __init__.py files that have a trace node but no
            # content to enrich/deepen.
            #
            # F-6: narrowed inner except. _get_file_excerpt raises
            # OSError for FS errors and UnicodeDecodeError for
            # non-text content. Programmer errors (TypeError,
            # AttributeError) propagate to the outer except.
            try:
                excerpt = enricher._get_file_excerpt(
                    n.get("file_path", ""), max_lines=1,
                )
            except (OSError, ValueError, UnicodeDecodeError):
                excerpt = ""
            if not excerpt:
                continue
            file_nodes.append(n)
        file_node_ids = {n["id"] for n in file_nodes}

        existing = enricher.load_existing()
        # pass_number >= 3 → DEEPENING-touched entries only.
        in_scope_deepened = sum(
            1 for nid, entry in existing.items()
            if nid in file_node_ids
            and getattr(entry, "pass_number", 2) >= 3
        )
        # T-S1.0 touchpoint 1 / T-S1.3: profile-aware denominator. Deepening
        # is disabled for prose_docs and system_config profiles; counting
        # gate-rejected files inflates _expected_total and pins the chip at
        # success_rate < 1.0 forever (T-S1.0 verdict). The orchestrator clamps
        # processed to expected, so prior orphan deepening entries on
        # newly-gate-rejected files can't leak as >1.0. No gate → unchanged.
        gate = getattr(enricher, "profile_gate", None)
        if gate is not None:
            expected = sum(
                1
                for n in file_nodes
                if n.get("file_path") and gate.allows(n["file_path"])
            )
        else:
            expected = len(file_nodes)
        return expected, in_scope_deepened
    except (
        OSError,
        _json.JSONDecodeError,
        ValueError,
        AttributeError,
        KeyError,  # F-7: corrupt jsonl missing 'id' key
    ) as e:
        # F-3: emit WARNING + telemetry from inside the except block
        # so the exception is still in scope (exc_info + per-exception
        # payload).
        logger.warning(
            "[Deepening] override-key scope-read failed (%s): %s — "
            "manifest.quality falls back to JSONL semantics, "
            "re-introduces §9.3 #32 chip leak on this run",
            type(e).__name__, str(e),
            exc_info=True,
        )
        if idx_dir is not None and project_id is not None:
            # F-4: narrowed telemetry except (was bare Exception).
            # ImportError catches the optional module absence; OSError
            # catches event-log write failures. Other exceptions
            # (programmer errors) propagate so telemetry-introduced
            # bugs surface in tests.
            try:
                from prep.services.pipeline_telemetry import record_event
                # PR-S-fixup-r3 FIX-1: telemetry must NEVER crash the
                # deepening worker after all LLM work completed. The
                # narrow except above catches today's known failure
                # modes; this inner safety net guards against future
                # record_event signature drift or refactors that emit
                # a different exception class. Asymmetric cost
                # strongly favors defensive wrapping for telemetry.
                try:
                    record_event(
                        idx_dir,
                        "deepening_override_failed",
                        {
                            "reason": "scope_read_failure",
                            "error_type": type(e).__name__,
                            "error_message": str(e)[:500],
                        },
                        stage="deepening",
                        project_id=project_id,
                    )
                except Exception:
                    logger.debug(
                        "[Deepening] telemetry record_event raised; "
                        "swallowed to protect deepening worker exit "
                        "(non-fatal)",
                        exc_info=True,
                    )
            except (ImportError, OSError):
                pass
        return None, None


def _compute_deepening_override_keys_from_disk(
    idx_dir: Path,
    repo_root: Path,
    *,
    project_id: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Skip-path version of `_compute_deepening_override_keys` that
    reads jsonl files directly without an `EpistemicEnricher` object.

    PR-T closes the round-1 / round-3 deferred gap on PR-S: when the
    deepening worker hits the LLM-unavailable skip path, it returns
    BEFORE instantiating the enricher, so the enricher-based helper
    is unreachable there. Without override keys the orchestrator
    falls back to JSONL semantics — the §9.3 #32 bug PR-S was meant
    to close re-surfaces on the chip whenever LLM config is missing.

    This helper duplicates the scope-read logic at the file-system
    layer:
      - Reads `trace_nodes.jsonl` directly, applies kind == "file"
        + empty-file filter (matches ENRICHMENT scope).
      - Reads `trace_epistemic.jsonl` directly, applies orphan
        filter + `pass_number >= 3` filter (matches PR-S-fixup-r2's
        chip-correct numerator semantic).

    File-system layer = no EpistemicEntry parsing, no LLM client,
    no caching. Cost is one full read each of two jsonl files +
    one open/readline per file_node. Acceptable for the rare
    skip-path case.

    Same return contract as the enricher-based helper:
      - `(int, int)` on success (including `(0, 0)` for empty
        projects so the caller emits the keys explicitly).
      - `(None, None)` on failure. WARNING + telemetry emitted from
        the except block where the exception is still in scope.
    """
    import json as _json

    try:
        trace_nodes_path = idx_dir / "trace_nodes.jsonl"
        epistemic_path = idx_dir / "trace_epistemic.jsonl"

        # Read trace_nodes.jsonl with kind + empty-file filters.
        file_nodes: List[Dict[str, Any]] = []
        if trace_nodes_path.exists():
            with open(trace_nodes_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        node = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue  # skip corrupt lines, don't crash
                    if node.get("kind") != "file":
                        continue
                    # Empty-file filter — same semantic as
                    # _get_file_excerpt(max_lines=1): file must have
                    # non-empty first line.
                    rel_path = node.get("file_path", "")
                    if not rel_path:
                        continue
                    full_path = repo_root / rel_path
                    try:
                        with open(full_path, encoding="utf-8", errors="replace") as fp:
                            first_line = fp.readline()
                    except (OSError, UnicodeDecodeError):
                        continue
                    if not first_line.strip():
                        continue
                    file_nodes.append(node)

        file_node_ids = {n["id"] for n in file_nodes}

        # Read trace_epistemic.jsonl with pass_number >= 3 filter.
        in_scope_deepened = 0
        if epistemic_path.exists():
            with open(epistemic_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    nid = entry.get("node_id")
                    if not nid or nid not in file_node_ids:
                        continue
                    if entry.get("pass_number", 2) >= 3:
                        in_scope_deepened += 1

        return len(file_nodes), in_scope_deepened
    except (OSError, ValueError, AttributeError, KeyError) as e:
        logger.warning(
            "[Deepening] skip-path override-key scope-read failed (%s): %s — "
            "manifest.quality falls back to JSONL semantics, "
            "re-introduces §9.3 #32 chip leak on this run",
            type(e).__name__, str(e),
            exc_info=True,
        )
        if project_id is not None:
            try:
                from prep.services.pipeline_telemetry import record_event
                try:
                    record_event(
                        idx_dir,
                        "deepening_override_failed",
                        {
                            "reason": "skip_path_scope_read_failure",
                            "error_type": type(e).__name__,
                            "error_message": str(e)[:500],
                        },
                        stage="deepening",
                        project_id=project_id,
                    )
                except Exception:
                    logger.debug(
                        "[Deepening] skip-path telemetry record_event "
                        "raised; swallowed (non-fatal)",
                        exc_info=True,
                    )
            except (ImportError, OSError):
                pass
        return None, None


# ── Worker Factory ───────────────────────────────────────────────

class WorkerFactory:
    """Creates worker functions for each stage.

    Each worker is a callable that takes (BuildSlot, progress_callback)
    and returns a result dict.  Workers use BuildManager internals.

    This is the integration layer between the state machine and the
    actual build logic.
    """

    # Class-level store for changed paths from coverage gap (set by PipelineOrchestrator)
    _changed_paths: Dict[str, set] = {}
    # Class-level store for force_from_start rebuilds (set by PipelineOrchestrator).
    # The structural worker passes it to TraceBuilder.build so the emitted
    # changeset routes every file to `added` (workers re-process) instead of
    # diffing against the prior manifest (everything `unchanged` — Rebuild
    # silently did nothing — 2026-05-17 regression).
    _force_from_start: set = set()

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
            # Pop changed_paths if available (incremental rebuild)
            changed = WorkerFactory._changed_paths.pop(project_id, None)
            force = project_id in WorkerFactory._force_from_start
            WorkerFactory._force_from_start.discard(project_id)
            base_worker = WorkerFactory._trace_worker(
                project_id, changed_paths=changed, force_from_start=force,
            )
        elif stage == StageId.INFERRED_EDGES:
            base_worker = WorkerFactory._inferred_edges_worker(project_id)
        elif stage == StageId.CATALOGUE:
            base_worker = WorkerFactory._augment_worker(project_id)
        elif stage == StageId.VALIDATION:
            base_worker = WorkerFactory._validate_worker(project_id)
        elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
            base_worker = WorkerFactory._knowledge_worker(
                project_id, is_deep=(stage == StageId.DEEP_KNOWLEDGE),
            )
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
        elif stage == StageId.RULES:
            base_worker = WorkerFactory._rules_worker(project_id)
        elif stage == StageId.CONCEPTS:
            base_worker = WorkerFactory._concepts_worker(project_id)
        elif stage == StageId.AUDIT:
            base_worker = WorkerFactory._audit_worker(project_id)
        elif stage == StageId.ANTIBODIES:
            base_worker = WorkerFactory._antibodies_worker(project_id)
        else:
            raise ValueError(f"Unknown stage: {stage}")

        def wrapped_worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.services.token_telemetry import set_telemetry_context
            with set_telemetry_context(project_id, stage.value):
                return base_worker(slot, progress_cb)

        # Phase 134: inject the changeset for downstream stages to consult.
        # Read once at construction time so downstream workers don't need to
        # know how to find idx_dir. Defensive: if anything goes wrong (first
        # build, missing file, import error), set None — workers fall back to
        # processing everything (see Worker.should_process).
        # Phase 135 Task 0: ALSO set the attribute on base_worker so the
        # inner closure's `worker` self-reference can read it. The inner
        # closures use `getattr(worker, "changeset", None)` — `wrapped_worker`
        # is NOT in their scope.
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            from prep.services.pipeline.changeset import read_changeset
            _proj = require_project(project_id)
            _idx_dir = project_index_dir(_proj)
            wrapped_worker.changeset = read_changeset(_idx_dir)  # type: ignore[attr-defined]
            base_worker.changeset = wrapped_worker.changeset  # type: ignore[attr-defined]
        except Exception:
            wrapped_worker.changeset = None  # type: ignore[attr-defined]
            base_worker.changeset = None  # type: ignore[attr-defined]

        # T-S1.3: inject the per-stage ProfileGate parallel to .changeset. The
        # 5 per-file stages (inferred_edges, catalogue, enrichment, deepening,
        # deep_knowledge) consult gate.allows(fp) in their skip checks; the
        # other stages carry it harmlessly (gate is never raised on their
        # behalf). Defensive like changeset: a None gate → process everything
        # (identical to pre-profile behavior). Set on both wrapped_worker and
        # base_worker so inner closures reading `getattr(worker, ...)` resolve
        # the same way they do for changeset (Phase 135 Task 0 pattern).
        try:
            from prep.core.pipeline_profiles import ProfileGate

            _gate = ProfileGate(project_id, stage)
            wrapped_worker.profile_gate = _gate  # type: ignore[attr-defined]
            base_worker.profile_gate = _gate  # type: ignore[attr-defined]
        except Exception:
            wrapped_worker.profile_gate = None  # type: ignore[attr-defined]
            base_worker.profile_gate = None  # type: ignore[attr-defined]

        return wrapped_worker

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _get_project_and_config(project_id: str):
        """Shared helper: load project, ui_config, and common build params."""
        from prep.services.project_helpers import require_project
        from prep.server import _load_ui_config

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
        from prep.server import _get_llm_client_for_task

        client = _get_llm_client_for_task(task_id)
        if not client:
            raise RuntimeError(f"No model configured for task '{task_id}'. Configure a model in AI Models settings.")
        if not client.is_available():
            raise RuntimeError(f"Model endpoint not reachable: {client.endpoint_url}")
        return client

    @staticmethod
    def _get_coordinator_llm_client():
        """Resolve the Swarm Coordinator LLMClient.

        Phase 112: Coordinator drives Phases 1 (planning) and 3 (synthesis)
        of the swarm pipeline.  Falls back to the large-slot client when
        unconfigured or when ``coordinator_model.inherit_from_large`` is True
        (the default).  See SWARM_UI_PLAN.md §2.
        """
        from prep.server import _get_llm_client_for_slot
        return _get_llm_client_for_slot("coordinator")

    @staticmethod
    def _get_llm_client(slot_name: str):
        """Legacy helper — resolves via slot name.  Prefer _get_llm_client_for_task()."""
        from prep.server import _get_llm_client_for_slot

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
            from prep.core.batch_profiles import resolve_profile
            from prep.server import _load_ui_config
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
    def _trace_worker(
        project_id: str,
        changed_paths: Optional[set] = None,
        force_from_start: bool = False,
    ):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.services.build_manager import build_manager
            from prep.core.trace import TraceBuilder, TraceIndex
            from prep.core.project_registry import project_index_dir
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
            if changed_paths:
                logger.info(
                    "[%s/Structural] Starting INCREMENTAL trace build — %d changed paths",
                    project.name, len(changed_paths),
                )
            else:
                logger.info("[%s/Structural] Starting trace build", project.name)
            _t0 = time.time()
            builder.build(
                progress_callback=log_cb,
                changed_paths=changed_paths,
                force_from_start=force_from_start,
            )

            trace_idx = TraceIndex(idx_dir)
            trace_idx.load()
            build_manager.project_trace_indexes[project_id] = trace_idx
            logger.info("[%s/Structural] Complete — %d nodes", project.name, trace_idx.node_count())

            # Ensure trace.enabled=true in project config so status endpoint
            # reports exists correctly (belt-and-suspenders with frontend fix).
            #
            # F-46: Project is a frozen dataclass — direct attribute assignment
            # raises FrozenInstanceError and tanks the entire fast_sync run.
            # F-85: Re-read config from the registry right before the update
            # instead of writing back the worker's stale snapshot. Previously,
            # if the user edited ignore_patterns / exclude globs in the UI
            # while Fast Sync was running, this block would clobber those
            # edits with the pre-run config when structural finished. Now
            # we fetch-merge-write, and skip entirely when trace.enabled is
            # already set in the current persisted config.
            try:
                from prep.core.project_registry import get_registry
                registry = get_registry()
                fresh = registry.get_project(project.id)
                fresh_cfg = (fresh.config if fresh and isinstance(fresh.config, dict) else {}) or {}
                fresh_trace = fresh_cfg.get("trace") if isinstance(fresh_cfg.get("trace"), dict) else {}
                if not fresh_trace.get("enabled"):
                    import copy
                    new_cfg = copy.deepcopy(fresh_cfg)
                    new_cfg.setdefault("trace", {})["enabled"] = True
                    registry.update_project(project.id, config=new_cfg)
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
            from prep.core import InferredEdgesAnalyzer
            from prep.core.project_registry import project_index_dir

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
                from prep.services.pipeline_logger import get_pipeline_logger
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
            # Phase 135.5: inject the Changeset. `worker` is the inner-closure
            # self-reference (Phase 135 Task 0 set base_worker.changeset).
            analyzer.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (inferred_edges is a per-file stage).
            analyzer.profile_gate = getattr(worker, "profile_gate", None)
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
            from prep.core import TraceAugmenter
            from prep.core.project_registry import project_index_dir

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
                from prep.services.pipeline_logger import get_pipeline_logger
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
                project_id=project_id,
            )
            # Phase 134: pass the changeset from the worker closure
            # attribute to the augmenter so its should_process can consult it.
            augmenter.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (catalogue is a per-file stage).
            augmenter.profile_gate = getattr(worker, "profile_gate", None)
            result = augmenter.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
            paused = bool(getattr(result, "paused", False))
            logger.info(
                "[%s/Fast Catalogue] Complete — %d augmented, %d failed, %d skipped%s",
                project.name, result.augmented, result.failed, result.skipped,
                " (paused on hold)" if paused else "",
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
                    "paused": paused,
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

            # Phase 127: a paused run is NOT a failure — it stopped early
            # because a soft-hold blocked dispatch.  In-flight calls
            # finished, results were checkpointed, and the next run
            # resumes when the hold clears.  Surface paused in the
            # return dict so upstream stage-status logic can show
            # "paused" instead of red "failed".
            return {
                "stage": "catalogue",
                "augmented": result.augmented,
                "total_nodes": result.total_nodes,
                "failed": result.failed,
                "skipped": result.skipped,
                "synthetic": result.synthetic,
                "paused": paused,
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
            from prep.services.build_manager import build_manager

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
    def _knowledge_worker(project_id: str, is_deep: bool = False):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.services.build_manager import build_manager

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            _t0 = time.time()
            stage_label = "Deep Knowledge Embedding" if is_deep else "Knowledge Embedding"
            logger.info("[%s/%s] Starting", project.name, stage_label)
            log_cb = WorkerFactory._logged_progress(stage_label, progress_cb, project.name)

            # KnowledgeIndex.build reports `baseline = docs_reused` — chunks
            # whose content hash matched the cached embedding. For stage 5
            # (KNOWLEDGE) this correctly means "previously done by this
            # stage." For stage 10 (DEEP_KNOWLEDGE), the cached embeddings
            # file was populated by stage 5, so docs_reused includes
            # upstream-inherited chunks too. Surfacing that as `baseline`
            # makes the dashboard render a two-tone "incremental" bar even
            # on a fresh post-reset deep run, which contradicts the user's
            # mental model that every stage looks like a fresh build until
            # there's prior work BY THE SAME STAGE to preserve.
            #
            # We rewrite the baseline before it leaves the worker: read
            # `deep_knowledge_manifest.json` (written only at successful
            # completion of a prior deep_knowledge run) and clamp the
            # callback's baseline to that recorded count. After a reset
            # (manifest deleted) → baseline=0, single-tone bar. After a
            # successful prior deep run → baseline=prior_count, two-tone
            # bar that legitimately reflects this stage's prior work.
            cb_to_use = log_cb
            if is_deep:
                from pathlib import Path
                from prep.core.project_registry import project_index_dir
                manifest_path = Path(project_index_dir(project)) / "deep_knowledge_manifest.json"
                prior_deep_chunks = 0
                if manifest_path.exists():
                    try:
                        import json as _json
                        data = _json.loads(manifest_path.read_text(encoding="utf-8"))
                        prior_deep_chunks = int(
                            (data.get("quality") or {}).get("total_items") or 0
                        )
                    except Exception:
                        prior_deep_chunks = 0

                def deep_cb(message, current, total, baseline=0):
                    # Clamp baseline to prior deep work only. KnowledgeIndex's
                    # docs_reused count includes fast-stage inheritance, which
                    # we explicitly do NOT want surfaced as this-stage baseline.
                    effective = min(int(baseline), prior_deep_chunks) if prior_deep_chunks > 0 else 0
                    log_cb(message, current, total, effective)
                cb_to_use = deep_cb

            idx = build_manager.get_project_knowledge_index(project)
            # Phase 135: ALWAYS reset both attributes — build_manager caches
            # the KnowledgeIndex instance per project, so an `if is_deep:`-only
            # write would leak `use_changeset=True` from a prior stage 10 run
            # into the next run's stage 5. Always-write keeps stage 5 on the
            # legacy hash path and stage 10 on the changeset path.
            # `worker` is the inner-closure self-reference (Task 0 set
            # base_worker.changeset; this name resolves there).
            idx.use_changeset = is_deep
            idx.changeset = getattr(worker, "changeset", None) if is_deep else None
            # T-S1.3: profile gate — deep_knowledge (is_deep) is per-file gated;
            # knowledge (stage 5) is never-gated, so it gets None here.
            idx.profile_gate = getattr(worker, "profile_gate", None) if is_deep else None
            result = idx.build(progress_callback=cb_to_use)
            logger.info("[%s/%s] Complete", project.name, stage_label)
            return {
                "stage": "deep_knowledge" if is_deep else "knowledge",
                **(result or {}),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
        return worker

    @staticmethod
    def _epistemic_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core import EpistemicEnricher
            from prep.core.project_registry import project_index_dir
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
                from prep.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
                pfl.log("enrichment", f"Epistemic starting: model={llm_client.model}, endpoint={llm_client.endpoint_url}")
            except Exception:
                pfl = None

            batch_profile = WorkerFactory._get_batch_profile(llm_client)
            if pfl and batch_profile:
                pfl.log("enrichment", f"Batch profile: {batch_profile.name.value}")

            _t0 = time.time()
            logger.info("[%s/Deep Reasoning] Starting: model=%s", project.name, llm_client.model)

            # Pre-flight: trace_augmented.jsonl is the sole input. If it's
            # missing or empty, _needs_enrichment returns False for every
            # node and the stage silently produces 0 — which then starves
            # stages 7, 8, 9, 10 of work. Fail loudly instead so the UI
            # surfaces a real error and the user can rebuild Fast Sync.
            aug_path = Path(idx_dir) / "trace_augmented.jsonl"
            try:
                aug_size = aug_path.stat().st_size if aug_path.exists() else 0
            except OSError:
                aug_size = 0
            if aug_size == 0:
                msg = (
                    "Epistemic enrichment input missing: "
                    f"{aug_path} (size={aug_size}). "
                    "Stage 5 (Fast Catalogue/augmentation) must run first. "
                    "Click 'Rebuild Fast Sync' to regenerate."
                )
                if pfl:
                    pfl.log("enrichment", msg)
                raise RuntimeError(msg)

            log_cb = WorkerFactory._logged_progress("Deep Reasoning", progress_cb, project.name)
            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
                batch_profile=batch_profile,
                project_id=project_id,
            )
            # Phase 134: inject the changeset from the worker closure
            # attribute so _needs_enrichment can check changeset.modified
            # instead of comparing manifest file hashes.
            enricher.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (enrichment is a per-file stage).
            enricher.profile_gate = getattr(worker, "profile_gate", None)
            result = enricher.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
            enriched = result.get("enriched_this_run", 0)
            failed = result.get("failed_this_run", 0)
            paused = bool(result.get("paused"))
            logger.info(
                "[%s/Deep Reasoning] Complete — enriched=%s, failed=%s%s",
                project.name, enriched, failed, " (paused on hold)" if paused else "",
            )

            if pfl:
                pfl.log("enrichment", "Epistemic enrichment complete", {
                    "total_file_nodes": result.get("total_file_nodes"),
                    "enriched_this_run": enriched,
                    "failed_this_run": failed,
                    "skipped": result.get("skipped"),
                    "total_enriched": result.get("total_enriched"),
                    "duration_ms": result.get("duration_ms"),
                    "paused": paused,
                })

            # Phase 127: a paused run is NOT a failure — it stopped early
            # because a soft-hold blocked dispatch.  In-flight calls
            # finished, results were checkpointed, and the next run
            # resumes from that checkpoint when the hold clears.  Skip
            # the failure heuristic in that case.
            #
            # If we attempted enrichment but got 0 results with failures,
            # treat this as a real failure so the UI shows warning (not
            # green).
            if not paused and enriched == 0 and failed > 0:
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
            from prep.core import GroupReasoningEngine
            from prep.core.project_registry import project_index_dir

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
            engine = GroupReasoningEngine(llm=llm_client, index_dir=idx_dir, project_id=project_id)
            # Phase 135: inject the Changeset. `worker` is the inner-closure
            # self-reference; Task 0 set base_worker.changeset so this read works.
            engine.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (group_reasoning consults it via T-S1.6's
            # input-set filter; harmless here otherwise).
            engine.profile_gate = getattr(worker, "profile_gate", None)
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
            from prep.core import ClusterSynthesizer
            from prep.core.project_registry import project_index_dir

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
            synthesizer = ClusterSynthesizer(
                llm=llm_client,
                index_dir=idx_dir,
                batch_profile=batch_profile,
                project_id=project_id,
            )
            # Phase 135: inject the Changeset. `worker` is the inner-closure
            # self-reference (Task 0 set base_worker.changeset).
            synthesizer.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (clustering is per-graph; carried harmlessly).
            synthesizer.profile_gate = getattr(worker, "profile_gate", None)
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
            from prep.core.atlas import CodebaseAtlas
            from prep.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                from prep.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(idx_dir)
            except Exception:
                pfl = None

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
            atlas = CodebaseAtlas(
                idx_dir, llm=llm_client, project_root=Path(project.path),
                project_name=project.name,
                project_id=project.id,
            )
            # Phase 135.5: inject the Changeset so the atlas's is_stale gate
            # consults stage 1's canonical "what changed" signal instead of
            # computing its own fingerprint.
            atlas.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (atlas selects prompt variant by dominant
            # profile in T-S2.3; not a per-file skip gate).
            atlas.profile_gate = getattr(worker, "profile_gate", None)

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
                # Phase 127 (P127-F9): pass cancel_token so the underlying
                # SwarmOrchestrator honors user-pause at phase boundaries.
                doc, segment_docs = atlas.generate_segmented(
                    progress_callback=log_cb,
                    cancel_token=slot.cancel_token,
                )
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
                from prep.services.build_manager import build_manager
                embedder = build_manager.create_embedder()
                routing_descs = atlas.generate_routing(embedder, progress_callback=log_cb)
                result["routing_segments"] = len(routing_descs)
                logger.info("[Atlas] Routing complete — %d segments", len(routing_descs))
            except Exception as e:
                logger.info("[Atlas] Routing generation skipped: %s", e)
                result["routing_segments"] = 0

            # Phase 64A: Pre-cache role sub-atlases for all built-in roles.
            # Uses existing epistemic + module data — no LLM calls (~30ms).
            try:
                role_cache = atlas.cache_role_atlases()
                result["role_atlases_cached"] = len(role_cache)
                logger.info("[Atlas] Role atlases cached — %d roles", len(role_cache))
                if pfl:
                    pfl.log("atlas", f"Role atlases cached for {len(role_cache)} agents")
            except Exception as e:
                logger.info("[Atlas] Role atlas caching skipped: %s", e)
                result["role_atlases_cached"] = 0
                if pfl:
                    pfl.log("atlas", f"Role atlas caching skipped: {e}")

            # Phase 124 T2: extract markdown→code cross-links and persist
            # as atlas_markdown_links.json so downstream stages can consume
            # them — concepts (T4) reads it for per-module relevant_docs;
            # audit synthesizer (T5b) can cite hotspot doc references.
            # Deterministic, no LLM, runs in seconds. Best-effort: failure
            # is non-fatal because atlas itself already shipped above.
            try:
                from prep.core.atlas.markdown_links import (
                    extract as _md_extract,
                    save as _md_save,
                    load_indexed_files,
                )
                indexed = load_indexed_files(idx_dir)
                md_result = _md_extract(Path(project.path), indexed_files=indexed)
                _md_save(md_result, idx_dir)
                result["markdown_links_md_count"] = md_result.md_count
                result["markdown_links_valid_links"] = md_result.valid_link_count
                logger.info(
                    "[Atlas] Markdown links extracted — %d md → %d code files (raw mentions: %d)",
                    md_result.md_count, md_result.valid_link_count,
                    md_result.raw_mention_count,
                )
                if pfl:
                    pfl.log(
                        "atlas",
                        f"Markdown links: {md_result.md_count} md → "
                        f"{md_result.valid_link_count} code files",
                    )
                # Phase 124 telemetry: record T2 firing with rich payload
                # so post-run analysis can confirm wire-up works.
                try:
                    from prep.services.pipeline_telemetry import record_event
                    top_md = sorted(
                        md_result.md_to_files.items(),
                        key=lambda kv: -len(kv[1]),
                    )[:5]
                    record_event(
                        idx_dir,
                        "md_links_extracted",
                        {
                            "md_count": md_result.md_count,
                            "valid_link_count": md_result.valid_link_count,
                            "raw_mention_count": md_result.raw_mention_count,
                            "indexed_file_count": len(indexed) if indexed else 0,
                            "top_md_by_links": [
                                {"path": p, "link_count": len(refs)}
                                for p, refs in top_md
                            ],
                        },
                        stage="atlas", project_id=project_id,
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.info("[Atlas] Markdown link extraction skipped: %s", e)
                result["markdown_links_md_count"] = 0
                if pfl:
                    pfl.log("atlas", f"Markdown link extraction skipped: {e}")
                try:
                    from prep.services.pipeline_telemetry import record_event
                    record_event(
                        idx_dir, "md_links_failed",
                        {"error": str(e)},
                        stage="atlas", project_id=project_id,
                    )
                except Exception:
                    pass

            result["_model_info"] = _capture_model_info(llm_client) if llm_client else {}
            result["_stage_timing"] = {"started_at": _t0, "elapsed": time.time() - _t0}
            return result
        return worker

    @staticmethod
    def _deepening_worker(project_id: str):
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core import EpistemicEnricher, DeepeningLoop
            from prep.core.project_registry import project_index_dir
            from pathlib import Path

            project, *_ = WorkerFactory._get_project_and_config(project_id)
            idx_dir = project_index_dir(project)

            try:
                llm_client = WorkerFactory._get_llm_client_for_task("deepening")
            except RuntimeError:
                logger.info("[Deepening] No model available for deepening task — skipping")
                progress_cb("Skipped (no LLM configured)", 1, 1)
                # PR-T (closes PR-S round-1 FIXUP-5 / round-3 DEF-6):
                # the skip path still emits override keys via the
                # enricher-free `_compute_deepening_override_keys_from_disk`
                # helper. Without this, manifest.quality falls back
                # to aggregate_quality_metrics' JSONL-line-count
                # semantics — re-introducing the §9.3 #32 chip leak
                # whenever LLM config is missing. The disk-based
                # helper reads trace_nodes.jsonl + trace_epistemic.jsonl
                # directly and applies the same kind / empty-file /
                # pass_number filters as the enricher path.
                skip_total, skip_processed = _compute_deepening_override_keys_from_disk(
                    idx_dir,
                    Path(project.path),
                    project_id=project_id,
                )
                skip_result: Dict[str, Any] = {
                    "stage": "deepening",
                    "skipped": True,
                    "reason": "no_llm",
                }
                if skip_total is not None:
                    skip_result["_expected_total"] = skip_total
                    skip_result["_processed_count"] = skip_processed
                return skip_result

            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
                project_id=project_id,
            )
            # Phase 134: inject changeset onto the enricher so _needs_enrichment
            # can check changeset.modified instead of comparing manifest hashes.
            enricher.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (deepening is a per-file stage).
            enricher.profile_gate = getattr(worker, "profile_gate", None)
            _t0 = time.time()
            logger.info("[%s/Deepening] Starting deepening loop: model=%s", project.name, llm_client.model)
            log_cb = WorkerFactory._logged_progress("Deepening", progress_cb, project.name)
            loop = DeepeningLoop(
                enricher=enricher,
                index_dir=idx_dir,
                max_iterations=10,
                batch_size=20,
                project_id=project_id,
            )
            # Phase 134: inject the changeset from the worker closure
            # attribute onto the DriftDetector so it can compute stale_set from
            # changeset.modified | deleted instead of per-entry hash comparison.
            loop.drift_detector.changeset = getattr(worker, "changeset", None)
            # T-S1.3: profile gate (deepening DriftDetector is per-file).
            loop.drift_detector.profile_gate = getattr(worker, "profile_gate", None)
            result = loop.run(progress_callback=log_cb)
            logger.info(
                "[Deepening] Complete — %d iterations, converged=%s",
                result.iterations, bool(result.convergence),
            )

            # §9.3 #32 (PR-S + PR-S-fixup-r1 + PR-S-fixup-r2): emit
            # the orchestrator override keys `_expected_total` and
            # `_processed_count` so _apply_worker_quality_overrides
            # hoists them into manifest.quality and the "Continuous
            # Deepening" chip shows a semantically-coherent ratio
            # rather than the JSONL line count.
            #
            # ORPHAN RETENTION (not cumulative growth):
            #   DEEPENING and ENRICHMENT both write to
            #   trace_epistemic.jsonl per stages.py STAGE_OUTPUT_FILE
            #   (218/222). The jsonl is atomically rewritten from a
            #   dict each pass (epistemic_enrichment._write_epistemic),
            #   so it does not grow line-by-line cumulatively. The
            #   issue is ORPHAN RETENTION across rebuilds: entries
            #   for files no longer in scope (deleted, L3-filtered)
            #   stay in the dict and inflate the line count past the
            #   current file_nodes denominator.
            #
            # Helper uses file-node scope read with empty-file +
            # pass_number>=3 filters (PR-S-fixup-r2 collapsed the
            # convergence path that round-2 scrutiny showed had
            # mismatched semantics). WARNING + telemetry on failure
            # are emitted from the helper's except block where the
            # exception is in scope.
            #
            # Returns (0, 0) for empty projects — caller emits the
            # override keys so the chip shows 0/0 explicitly rather
            # than falling back to JSONL semantics (PR-S-fixup-r2
            # F-5).
            #
            # Closes PRQ-CSI-002 from PR-Q round-1 scrutiny.
            expected_total, processed_count = _compute_deepening_override_keys(
                enricher,
                idx_dir=idx_dir,
                project_id=project_id,
            )

            worker_result: Dict[str, Any] = {
                "stage": "deepening",
                "iterations": result.iterations,
                "converged": bool(result.convergence),
                "_model_info": _capture_model_info(llm_client),
                "_stage_timing": {"started_at": _t0, "elapsed": time.time() - _t0},
            }
            # PR-S-fixup-r2 F-5: emit override keys for both happy
            # path AND empty-project case (expected_total == 0). Only
            # skip when scope-read failed entirely (None) — in that
            # case the helper already logged WARNING + telemetry from
            # its except block.
            if expected_total is not None:
                worker_result["_expected_total"] = expected_total
                worker_result["_processed_count"] = processed_count
            return worker_result
        return worker

    @staticmethod
    def _rules_worker(project_id: str):
        """Generate/update IDE rules files (AGENTS.md, .cursor/, etc.)."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.atlas import CodebaseAtlas
            from prep.core.project_registry import project_index_dir
            from prep.core.rules_generator import write_rules_file
            from prep.services.project_helpers import require_project
            from prep.services.pipeline.manifest_store import ManifestStore
            from pathlib import Path

            project = require_project(project_id)
            idx_dir = project_index_dir(project)
            log_cb = WorkerFactory._logged_progress("Rules", progress_cb, project.name)

            _t0 = time.time()
            log_cb("Loading atlas", 0, 3)

            atlas = CodebaseAtlas(idx_dir)
            doc = atlas.load()

            if not doc or not doc.content:
                log_cb("No atlas — writing structural rules", 1, 3)
                write_rules_file(
                    project_path=Path(project.path),
                    project_name=project.name or project_id,
                    atlas_content=None,
                    is_preliminary=True,
                    ide="auto",
                    project_id=project_id,
                )
                log_cb("Done", 3, 3)
                return {
                    "stage": "rules",
                    "skipped": False,
                    "mode": "structural",
                    "_stage_timing": {
                        "started_at": _t0,
                        "elapsed": time.time() - _t0,
                    },
                }

            log_cb("Generating rules files", 1, 3)
            store = ManifestStore(Path(idx_dir))
            stats = store.read_graph_stats()
            if doc.file_count:
                stats.setdefault("node_count", doc.file_count)

            pcfg = project.config or {}
            included_paths = pcfg.get("included_paths") or []

            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content,
                included_paths=included_paths if included_paths else None,
                is_preliminary=False,
                stats=stats,
                ide="auto",
                project_id=project_id,
            )

            log_cb("Writing atlas signal", 2, 3)
            from prep.services.pipeline.post_flight import PostFlightActions
            PostFlightActions.write_atlas_signal(idx_dir)

            log_cb("Done", 3, 3)
            return {
                "stage": "rules",
                "skipped": False,
                "mode": doc.mode,
                "atlas_chars": doc.char_count,
                "_stage_timing": {
                    "started_at": _t0,
                    "elapsed": time.time() - _t0,
                },
            }
        return worker

    @staticmethod
    def _concepts_worker(project_id: str):
        """Seed concepts from atlas + modules + audit data."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.concept_seeder import seed_concepts
            from prep.services.concept_store import concept_store

            log_cb = WorkerFactory._logged_progress("Concepts", progress_cb, "")
            _t0 = time.time()

            # Capture the model BEFORE running so the manifest records it
            # regardless of whether seed_concepts ends up calling the LLM
            # path or the template path. Without this, the dashboard
            # rendered "built-in" for the Concepts stage even though the
            # task is configured to use the Thinking model.
            llm_client = None
            try:
                llm_client = WorkerFactory._get_llm_client_for_task("concepts")
            except RuntimeError:
                pass
            model_info = _capture_model_info(llm_client) if llm_client else {}

            # Phase 125 fix (2026-05-02): freshness-based skip instead of
            # existence-based skip. The previous "if any concept exists,
            # skip" guard was load-bearing on the bug where a hallucinated
            # SourcePrep-themed concept would block all subsequent concept
            # seeding for the project — even after a DB nuke, because the
            # next run would emit ONE more concept and re-trigger the guard.
            #
            # New rule: skip only when the concepts manifest is newer than
            # ALL declared inputs (trace_modules.jsonl + atlas_markdown_links.json
            # per stages.STAGE_INPUT_FILES) — same pattern other stages use.
            # When inputs change OR no manifest exists, re-seed.
            from pathlib import Path  # local import: workers.py has no top-level pathlib
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            from prep.services.pipeline.stages import StageId, STAGE_INPUT_FILES
            project_obj = require_project(project_id)
            idx_dir = Path(project_index_dir(project_obj))
            manifest_path = idx_dir / "concepts_manifest.json"
            input_paths = [
                idx_dir / fn for fn in STAGE_INPUT_FILES.get(StageId.CONCEPTS, [])
            ]
            # Phase 125b: skip the SEEDER (Pass 1, the per-module rationale
            # extractor) only when manifest is fresh AND the rationale
            # layer already has rows. Pass 3 (concept_synthesizer) runs
            # regardless so the cross-cutting concept layer stays current
            # without forcing a full re-seed.
            stats = concept_store.get_stats(project_id)
            rationale_count = stats.get("module_rationale_count", stats.get("total", 0))
            should_skip_seeder = False
            if manifest_path.is_file() and rationale_count > 0 and input_paths:
                manifest_mtime = manifest_path.stat().st_mtime
                input_mtimes = [
                    p.stat().st_mtime for p in input_paths if p.is_file()
                ]
                if input_mtimes:
                    should_skip_seeder = manifest_mtime > max(input_mtimes)

            if should_skip_seeder:
                log_cb(
                    f"{rationale_count} module rationale entries fresh — skipping seeder",
                    1, 4,
                )
                # Skip the seeder but DO NOT return — Generate / Validate
                # / Gate still need to run.
                concepts_created = 0
                questions_created = 0
                result = {"status": "skipped_fresh", "mode": "seeder_skipped"}
            else:
                log_cb("Seeding concepts from pipeline data (Pass 1)", 0, 4)
                # Plumb log_cb through to seed_concepts so the dashboard's
                # Concept Seeding progress bar fills as each per-module
                # worker completes, instead of binary 0% → 100%.
                def _seed_progress(message: str, current: int, total: int) -> None:
                    # Per-module progress is mapped onto the first quarter
                    # of the stage's progress (0..1 of 4) so seeder fan-out
                    # doesn't overshoot the stage progress bar.
                    log_cb(message, current, max(total, 1) * 4)
                # Phase 127 (P127-F9): pass cancel_token so the underlying
                # SwarmOrchestrator honors user-pause at phase boundaries
                # and stops dispatching new fanout workers.
                result = seed_concepts(
                    project_id,
                    progress_callback=_seed_progress,
                    cancel_token=slot.cancel_token,
                )
            concepts_created = result.get("concepts_created", 0)
            questions_created = result.get("questions_created", 0)
            log_cb(
                f"{concepts_created} module rationale entries seeded",
                1, 4,
            )

            # Phase 125b — Pass 3: cross-cutting concept synthesis.
            # Lifts abstraction from the per-module rationale layer
            # (just produced) to a small ~30-100 concept layer
            # (kind='concept'). Single LLM call with rich grounding
            # from atlas + audit + spaghetti + antibodies + rationale
            # clusters + T2 doc links. See concept_synthesizer.py and
            # docs/Phase125b_TwoLayerConceptArchitecture/README.md.
            #
            # Best-effort: if synthesis fails we still consider the
            # stage successful (rationale is the substantive output;
            # synthesis adds the curated layer on top).
            # Phase 125c — Pass 2: Generate swarm (replaces 125b single-call).
            # Per-category fan-out with rich grounding (atlas + planning
            # docs + rationale + audit + spaghetti + antibodies).
            # save=False so we hand candidates to Validate in-memory and
            # the store gets one definitive write at Validate's reconciled
            # statuses, not two writes (synthesizer-tier then verdict-tier).
            synth_emitted = 0
            synth_saved = 0
            val_activated = 0
            val_triaged = 0
            val_archived = 0
            val_parse_failures = 0
            try:
                from prep.core.concept_generate_dedup import (
                    load_or_build_docs_grounding,
                )
                from prep.core.concept_generate_swarm import (
                    synthesize_concepts_swarm,
                )
                from prep.core.concept_synthesizer import load_grounding
                from prep.core.concept_validate_swarm import (
                    validate_concepts_swarm,
                )
                project_root = Path(project_obj.path)
                project_name = project_obj.name or ""

                log_cb("Generating concepts via swarm (Pass 2)", 1, 4)
                gen_report = synthesize_concepts_swarm(
                    project_id,
                    llm=llm_client,
                    swarm_size=3,            # default 3-axis fan-out
                    idx_dir=idx_dir,
                    project_root=project_root,
                    project_name=project_name,
                    save=False,               # hand off to Validate
                )
                synth_emitted = gen_report.candidates_after_dedup
                if gen_report.skipped_fresh:
                    log_cb(
                        "Generate skipped — rationale unchanged since last run",
                        2, 4,
                    )
                else:
                    log_cb(
                        f"Generated {synth_emitted} candidates ({len(gen_report.failed_workers)} workers failed)",
                        2, 4,
                    )

                if gen_report.concepts and not gen_report.skipped_fresh:
                    # Reload grounding for Validate. Cheap relative to
                    # LLM cost — JSON reads + concept_store row pull.
                    grounding = load_grounding(
                        project_id, idx_dir=idx_dir, project_name=project_name,
                    )
                    docs = load_or_build_docs_grounding(
                        project_id, idx_dir=idx_dir, project_root=project_root,
                    )
                    log_cb("Validating concepts via swarm (Pass 3)", 2, 4)
                    val_report = validate_concepts_swarm(
                        project_id,
                        candidates=gen_report.concepts,
                        llm=llm_client,
                        grounding=grounding,
                        docs=docs,
                        idx_dir=idx_dir,
                    )
                    val_activated = val_report.activated
                    val_triaged = val_report.triaged
                    val_archived = val_report.archived
                    val_parse_failures = val_report.parse_failures
                    synth_saved = val_report.saved
                    log_cb(
                        f"Validated: {val_activated} active, "
                        f"{val_triaged} triage, {val_archived} archived",
                        3, 4,
                    )
                else:
                    log_cb(
                        "Skipping Validate (Generate produced no candidates "
                        "or short-circuited fresh)",
                        3, 4,
                    )
            except Exception as e:
                logger.warning(
                    "[Concepts/Pass2-3] Generate+Validate failed (non-fatal): %s",
                    e, exc_info=True,
                )
                log_cb(
                    "Generate/Validate failed — see logs",
                    3, 4,
                )

            # Phase 125c — Pass 4: deterministic confidence gate.
            # Sweeps any seed concepts not promoted by Validate (e.g.
            # parse failures that fell through to default state) and
            # any leftover module_rationale-style anomalies. Validate
            # is the source of truth for tier; the gate is just a
            # tiebreaker that catches edge cases.
            gate_activated = 0
            gate_triaged = 0
            gate_archived = 0
            try:
                from prep.core.concept_promotion_pipeline import run_pass4_gate
                log_cb("Gating remaining seeds (Pass 4)", 3, 4)
                gate_report = run_pass4_gate(
                    project_id, idx_dir=idx_dir, kind="concept",
                )
                gate_activated = gate_report.activated
                gate_triaged = gate_report.triaged
                gate_archived = gate_report.archived
                log_cb(
                    f"Gate: {gate_activated} active, {gate_triaged} triage, "
                    f"{gate_archived} archived",
                    4, 4,
                )
            except Exception as e:
                logger.warning(
                    "[Concepts/Pass4] gate failed (non-fatal): %s",
                    e, exc_info=True,
                )

            return {
                "stage": "concepts",
                "skipped": False,
                "status": result.get("status"),
                "concepts_created": concepts_created,         # rationale layer
                "synth_concepts_emitted": synth_emitted,      # Phase 125c Generate
                "synth_concepts_saved": synth_saved,
                "val_activated": val_activated,                # Phase 125c Validate
                "val_triaged": val_triaged,
                "val_archived": val_archived,
                "val_parse_failures": val_parse_failures,
                "gate_activated": gate_activated,             # Phase 125c T5
                "gate_triaged": gate_triaged,
                "gate_archived": gate_archived,
                "questions_created": questions_created,
                "_model_info": model_info,
                "_stage_timing": {
                    "started_at": _t0,
                    "elapsed": time.time() - _t0,
                },
            }
        return worker

    @staticmethod
    def _audit_worker(project_id: str):
        """Run structural audit analyzers + LLM synthesis."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.audit.runner import run_audit, save_findings
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            from pathlib import Path

            project = require_project(project_id)
            idx_dir = project_index_dir(project)
            log_cb = WorkerFactory._logged_progress(
                "Audit", progress_cb, project.name,
            )

            _t0 = time.time()
            log_cb("Running structural analyzers", 0, 2)

            result = run_audit(
                index_dir=Path(idx_dir),
                project_root=Path(project.path),
                progress_callback=lambda phase, cur, tot: log_cb(
                    phase, cur, tot,
                ),
            )

            finding_count = (
                len(result.findings) if result.findings else 0
            )
            # Persist Tier 1 findings to disk BEFORE Tier 2 synthesis
            # runs. Without this, /pipeline/status reads
            # idx_dir/audit/findings.json (which never gets written) and
            # reports `0 findings` in the dashboard even though the
            # synthesis docs (saved later) clearly describe many. Save
            # here — Tier 2's save_documents() writes its own markdown
            # files alongside; the two artifacts coexist.
            try:
                save_findings(result, Path(idx_dir))
            except Exception as e:
                logger.warning(
                    "[%s/Audit] save_findings failed (non-fatal): %s",
                    project.name, e, exc_info=True,
                )

            # Phase 124 T5: spaghetti scoring runs in Tier 1, before the LLM
            # synthesis. Migration history: spaghetti was a separate panel,
            # got merged via run_health_scan, then the panel→pipeline cutover
            # wired only run_audit and forgot spaghetti. Direct call here is
            # ~10 LoC; reuses ctx-loader (one duplicate load, ~5s) without
            # changing run_audit's return type. T5b will refactor to share
            # ctx with the Tier 2 synthesizer prompt.
            sp_result = None
            try:
                from prep.core.audit.spaghetti_scorer import (
                    run_spaghetti_scan, save_spaghetti,
                )
                sp_result = run_spaghetti_scan(Path(idx_dir), Path(project.path))
                save_spaghetti(sp_result, Path(idx_dir))
                log_cb(
                    f"Spaghetti scoring complete — {sp_result.file_count} files",
                    1, 2,
                )
                # Phase 124 telemetry: record T5 firing + top hotspots
                try:
                    from prep.services.pipeline_telemetry import record_event
                    sev = dict(sp_result.severity_counts) if hasattr(sp_result, "severity_counts") else {}
                    top_hotspots = sorted(
                        (sp_result.files or []),
                        key=lambda f: -f.score,
                    )[:5]
                    record_event(
                        Path(idx_dir),
                        "spaghetti_scored",
                        {
                            "file_count": sp_result.file_count,
                            "scored_count": getattr(sp_result, "scored_count", None),
                            "severity_counts": sev,
                            "top_hotspots": [
                                {
                                    "file_path": f.file_path,
                                    "score": round(f.score, 3),
                                    "severity": f.severity,
                                    "in_circular": f.in_circular,
                                    "tech_debt_count": f.tech_debt_count,
                                }
                                for f in top_hotspots
                            ],
                        },
                        stage="audit", project_id=project_id,
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning(
                    "[%s/Audit] spaghetti scoring failed (non-fatal): %s",
                    project.name, e, exc_info=True,
                )
                try:
                    from prep.services.pipeline_telemetry import record_event
                    record_event(
                        Path(idx_dir), "spaghetti_failed",
                        {"error": str(e)},
                        stage="audit", project_id=project_id,
                    )
                except Exception:
                    pass

            log_cb(
                f"Tier 1 complete — {finding_count} findings", 1, 2,
            )

            tier2_ok = False
            tier2_mode = "skipped"
            tier2_doc_count = 0
            try:
                from prep.core.audit.synthesizer import (
                    AuditSynthesizer, save_documents,
                )
                from prep.core.audit.runner import load_audit_context
                llm_client = WorkerFactory._get_llm_client_for_task("audit")
                synth = AuditSynthesizer(llm_client, project_name=project.name)

                # Phase 96F: Source concurrency from the scheduler.  When
                # the audit stage runs inside a swarm window (it is in
                # SWARM_CAPABLE_STAGES), full_budget_for_swarm returns
                # the full per-node worker budget instead of fair-share.
                tier2_concurrency = 1
                try:
                    from prep.services.pipeline.scheduler import pipeline_scheduler
                    full = pipeline_scheduler.full_budget_for_swarm(
                        llm_client.provider, llm_client.model,
                        project_id=project_id,
                    )
                    if full is not None:
                        tier2_concurrency = full
                except Exception:
                    logger.debug(
                        "[Audit] swarm budget lookup failed, using sequential",
                        exc_info=True,
                    )

                log_cb(
                    f"Running LLM synthesis ({tier2_concurrency} workers)",
                    1, 2,
                )

                # Synthesizer needs an AuditContext for finding formatting.
                # Reload it cheaply (Tier 1 already loaded the same data).
                ctx = load_audit_context(
                    Path(idx_dir),
                    Path(project.path),
                )
                # Phase 124 T5b: pass the spaghetti result (computed in
                # Tier 1 above) into Tier 2 so AUDIT_SUMMARY and
                # TECH_DEBT_REPORT cite hotspots structurally instead of
                # re-deriving them from raw findings.
                documents = synth.synthesize_all(
                    result, ctx,
                    progress_callback=lambda phase, cur, tot: log_cb(
                        phase, cur, tot,
                    ),
                    concurrency=tier2_concurrency,
                    spaghetti=sp_result,
                )
                save_documents(documents, Path(idx_dir))
                tier2_doc_count = len(documents)
                tier2_ok = True
                tier2_mode = "parallel" if tier2_concurrency > 1 else "sequential"
            except Exception as e:
                logger.info("[Audit] Tier 2 synthesis skipped: %s", e, exc_info=True)

            log_cb("Done", 2, 2)
            audit_model_info: Dict[str, Any] = {}
            try:
                _audit_client = WorkerFactory._get_llm_client_for_task("audit")
                if _audit_client:
                    audit_model_info = _capture_model_info(_audit_client)
            except Exception:
                pass
            return {
                "stage": "audit",
                "skipped": False,
                "finding_count": finding_count,
                "tier2": tier2_ok,
                "tier2_mode": tier2_mode,
                "tier2_doc_count": tier2_doc_count,
                "errors": result.errors if result.errors else [],
                "_model_info": audit_model_info,
                "_stage_timing": {
                    "started_at": _t0,
                    "elapsed": time.time() - _t0,
                },
            }
        return worker

    @staticmethod
    def _antibodies_worker(project_id: str):
        """Derive immune system antibodies from concepts."""
        def worker(slot: BuildSlot, progress_cb: Callable) -> Dict[str, Any]:
            from prep.core.antibody_derivation import (
                derive_antibodies_for_project,
            )
            from prep.services.antibody_store import antibody_store
            from prep.services.concept_store import concept_store

            log_cb = WorkerFactory._logged_progress(
                "Antibodies", progress_cb, "",
            )
            _t0 = time.time()

            log_cb("Loading concepts", 0, 2)
            concepts = concept_store.list_concepts(project_id)

            if not concepts:
                log_cb("No concepts — skipping", 1, 1)
                return {
                    "stage": "antibodies",
                    "skipped": True,
                    "reason": "no_concepts",
                    "_stage_timing": {
                        "started_at": _t0,
                        "elapsed": time.time() - _t0,
                    },
                }

            log_cb("Deriving antibodies", 1, 2)
            concept_dicts = [
                c.to_dict() if hasattr(c, "to_dict") else c
                for c in concepts
            ]
            antibodies = derive_antibodies_for_project(concept_dicts)

            saved = 0
            try:
                saved = antibody_store.save_many(project_id, antibodies)
            except Exception as e:
                logger.warning(
                    "save_many failed for antibodies, falling back to per-item saves: %s",
                    e,
                )
                for ab in antibodies:
                    try:
                        antibody_store.save(project_id, ab)
                        saved += 1
                    except Exception as e2:
                        logger.warning("Failed to save antibody %s: %s", ab.id, e2)

            log_cb(f"{saved} antibodies derived", 2, 2)
            return {
                "stage": "antibodies",
                "skipped": False,
                "derived": len(antibodies),
                "saved": saved,
                "_stage_timing": {
                    "started_at": _t0,
                    "elapsed": time.time() - _t0,
                },
            }
        return worker


# ── Pipeline Orchestrator ────────────────────────────────────────
