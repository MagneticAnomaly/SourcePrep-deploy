"""Phase 125c T2c.2 — the Generate swarm runner.

Ties together every T2 piece:

    load_grounding (Phase 125b)         shared atlas/audit/spaghetti/antibodies
    load_or_build_docs_grounding (T2c)  planning-doc grounding
    build_worker_scopes (T2a)            partition by category dimension
    build_worker_payload (T2b)           per-scope grounding payload
    build_worker_prompt (T2b)            per-worker (system, user) prompt
    parallel LLM calls                   ThreadPoolExecutor across N workers
    parse_synthesis_response (Phase 125b) per-worker JSON → SynthesizedConcept
    dedupe_swarm_outputs (T2c.1)         cross-worker anchor-overlap dedup
    concept_store.save_many              persist with kind='concept'

Why ThreadPoolExecutor instead of SwarmOrchestrator: our scopes are
pre-determined by ``swarm_size``, not LLM-assigned, so the coordinator
phase is dead weight. We do reuse the scheduler's concurrency budget
discovery (Phase 82 unbounded latency-aware) — that's the part of the
swarm infrastructure that earns its keep here.

See ``docs/Phase125c_QualityCheckedConceptSwarm/README.md`` §3.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .concept_generate_dedup import (
    dedupe_swarm_outputs,
    load_or_build_docs_grounding,
)
from .concept_generate_grounding import (
    WorkerScope,
    build_worker_scopes,
)
from .concept_generate_prompt import (
    build_worker_payload,
    build_worker_prompt,
)
from .concept_synthesizer import (
    MAX_SYNTHESIZED_CONCEPTS,
    TIER_TO_CONFIDENCE,
    Grounding,
    SynthesizedConcept,
    load_grounding,
    parse_synthesis_response,
)

logger = logging.getLogger(__name__)


# Wall-time guardrails per Phase 123 follow-up — generous to fit
# planning-doc-rich prompts on long-context cloud models.
DEFAULT_PER_WORKER_TIMEOUT_S = 240.0
DEFAULT_TOTAL_TIMEOUT_S = 1500.0


@dataclass
class GenerateSwarmReport:
    """Aggregate output of one Generate swarm run."""
    project_id: str = ""
    swarm_size: int = 1
    worker_count: int = 0
    candidates_emitted_per_scope: dict[str, int] = field(default_factory=dict)
    candidates_emitted_total: int = 0
    candidates_after_dedup: int = 0
    saved: int = 0
    skipped: int = 0
    failed_workers: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


def synthesize_concepts_swarm(
    project_id: str,
    *,
    llm: Any,
    swarm_size: int = 3,
    idx_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
    project_name: str = "",
    per_worker_timeout_s: float = DEFAULT_PER_WORKER_TIMEOUT_S,
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
    dry_run: bool = False,
) -> GenerateSwarmReport:
    """Run the Generate swarm and persist deduped output.

    Args:
        project_id: project scope.
        llm: LLM client. Must expose ``.generate(prompt, system, json_mode,
            temperature, num_predict, think) -> (text, tokens)``.
        swarm_size: 1, 3, or 10. Maps to 1, 3, or 11 workers.
        idx_dir / project_root: resolved from registry when None.
        project_name: human-readable header for prompts; resolved when ''.
        per_worker_timeout_s: max wall-time per LLM call.
        total_timeout_s: hard cap on the whole swarm.
        dry_run: build prompts and return counts but skip the LLM + save.

    Returns a GenerateSwarmReport with per-scope emission counts.
    """
    t0 = time.time()
    report = GenerateSwarmReport(project_id=project_id, swarm_size=swarm_size)

    # Resolve idx_dir / project_root if not provided.
    if idx_dir is None or project_root is None or not project_name:
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project
        project = require_project(project_id)
        if idx_dir is None:
            idx_dir = Path(project_index_dir(project))
        if project_root is None:
            project_root = Path(project.path)
        if not project_name:
            project_name = project.name or ""

    # Load shared grounding + planning-doc grounding.
    grounding = load_grounding(
        project_id, idx_dir=idx_dir, project_name=project_name,
    )
    docs = load_or_build_docs_grounding(
        project_id, idx_dir=idx_dir, project_root=project_root,
    )

    scopes = build_worker_scopes(swarm_size)
    report.worker_count = len(scopes)

    # Build per-worker payloads and prompts.
    payloads = [
        build_worker_payload(scope, grounding=grounding, docs=docs)
        for scope in scopes
    ]
    prompts = [build_worker_prompt(p) for p in payloads]

    if dry_run:
        for scope, (sys_p, usr_p) in zip(scopes, prompts):
            logger.info(
                "[GenSwarm/dry-run] scope=%s system_chars=%d user_chars=%d",
                scope.label, len(sys_p), len(usr_p),
            )
        report.elapsed_seconds = time.time() - t0
        return report

    # Fire workers in parallel. Each worker is an independent LLM call.
    all_concepts: list[SynthesizedConcept] = []
    with ThreadPoolExecutor(max_workers=len(scopes)) as pool:
        future_to_scope = {
            pool.submit(
                _run_one_worker,
                llm=llm, system=sys_p, user=usr_p, scope=scope,
                timeout_s=per_worker_timeout_s,
            ): scope
            for (sys_p, usr_p), scope in zip(prompts, scopes)
        }
        for fut in as_completed(future_to_scope, timeout=total_timeout_s):
            scope = future_to_scope[fut]
            try:
                worker_concepts = fut.result()
            except Exception as e:
                logger.warning(
                    "[GenSwarm/%s] worker failed: %s", scope.label, e,
                )
                report.failed_workers.append(scope.label)
                continue
            report.candidates_emitted_per_scope[scope.label] = len(worker_concepts)
            all_concepts.extend(worker_concepts)

    report.candidates_emitted_total = len(all_concepts)

    # Cross-worker dedup. Anchor-overlap clustering picks one winner
    # per cluster, so concepts emitted by multiple workers about the
    # same anchored claim collapse to the highest-tier representative.
    deduped = dedupe_swarm_outputs(all_concepts)

    # Sort by tier descending, cap defensively. Same shape as 125b.
    deduped.sort(
        key=lambda c: TIER_TO_CONFIDENCE.get(c.tier, 0.0), reverse=True,
    )
    if len(deduped) > MAX_SYNTHESIZED_CONCEPTS:
        logger.warning(
            "[GenSwarm] %d deduped concepts; capping to %d (highest tier first)",
            len(deduped), MAX_SYNTHESIZED_CONCEPTS,
        )
        deduped = deduped[:MAX_SYNTHESIZED_CONCEPTS]

    report.candidates_after_dedup = len(deduped)

    # Persist with kind='concept' via the existing save path.
    if deduped:
        try:
            from prep.services.concept_store import concept_store
            save_dicts = [c.to_save_dict() for c in deduped]
            saved, skipped = concept_store.save_many(project_id, save_dicts)
            report.saved = saved
            report.skipped = skipped
        except Exception as e:
            logger.warning("[GenSwarm] save_many failed: %s", e, exc_info=True)

    # Telemetry.
    try:
        from prep.services.pipeline_telemetry import record_event
        tier_dist: dict[str, int] = {}
        for c in deduped:
            tier_dist[c.tier] = tier_dist.get(c.tier, 0) + 1
        record_event(
            idx_dir,
            "generate_swarm_complete",
            {
                "swarm_size": swarm_size,
                "worker_count": len(scopes),
                "candidates_emitted_total": report.candidates_emitted_total,
                "candidates_after_dedup": report.candidates_after_dedup,
                "saved": report.saved,
                "tier_distribution": tier_dist,
                "failed_workers": list(report.failed_workers),
                "per_scope_counts": dict(report.candidates_emitted_per_scope),
                "elapsed_seconds": time.time() - t0,
            },
            stage="concepts", project_id=project_id,
        )
    except Exception:
        logger.debug("[GenSwarm] telemetry record failed", exc_info=True)

    report.elapsed_seconds = time.time() - t0
    return report


def _run_one_worker(
    *,
    llm: Any,
    system: str,
    user: str,
    scope: WorkerScope,
    timeout_s: float,  # noqa: ARG001 — caller-side timeout via as_completed
) -> list[SynthesizedConcept]:
    """One worker LLM call → parsed candidates filtered to scope categories.

    The scope-category filter at parse time is belt-and-suspenders: the
    prompt instructs the worker to emit only its scope's categories, but
    if it strays we drop the off-scope outputs at parse time so cross-
    worker dedup doesn't have to reason about it.
    """
    text, _tokens = llm.generate(
        prompt=user,
        system=system,
        json_mode=True,
        temperature=0.1,
        num_predict=5000,
        think=False,
    )
    parsed = parse_synthesis_response(text or "")
    allowed = set(scope.categories)
    return [c for c in parsed if c.category in allowed]
