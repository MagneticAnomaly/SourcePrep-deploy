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
    _rationale_fingerprint,
    load_grounding,
    parse_synthesis_response,
)


# Phase 125c uses its own manifest file (separate from 125b's
# concept_synthesis_manifest.json). Avoids cross-contamination on a
# project that ran the 125b single-call path before upgrading: the old
# manifest stays as a 125b artifact; 125c starts fresh and writes its
# own freshness fingerprint here.
_GEN_SWARM_MANIFEST_FILENAME = "concept_generate_manifest.json"

# Bump when Generate's prompts, BANNED list, T2/T3 rubric, or grounding
# composition change in a way that would meaningfully alter outputs.
# The freshness check ignores manifests whose prompt_revision differs
# from the current value, forcing a re-run with the new behavior.
#
#   revision 1 — initial Phase 125c (T2c.2 / T6 — 2026-05-10)
#   revision 2 — post-dogfood (2026-05-11):
#       (A) audit_findings dropped from Generate prompt
#       (B) BUG DESCRIPTION / AUDIT FINDING explicitly BANNED
#       (C) T2 relaxed to allow doc-only anchoring
#       (D) rationale grounding includes content + bumped to top-200
_GEN_PROMPT_REVISION = 2


def _read_gen_swarm_manifest(idx_dir: Optional[Path]) -> Optional[dict]:
    if idx_dir is None:
        return None
    p = idx_dir / _GEN_SWARM_MANIFEST_FILENAME
    if not p.is_file():
        return None
    try:
        import json
        return json.loads(p.read_text())
    except Exception:
        return None


def _write_gen_swarm_manifest(idx_dir: Optional[Path], payload: dict) -> None:
    if idx_dir is None:
        return
    try:
        import json
        p = idx_dir / _GEN_SWARM_MANIFEST_FILENAME
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass

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
    # Phase 125c T6: deduped candidate list, available for hand-off to
    # the Validate swarm (T3b) when ``save=False``. When ``save=True``
    # this is still populated for telemetry / debugging but the rows
    # are already persisted via concept_store.save_many.
    concepts: list[SynthesizedConcept] = field(default_factory=list)
    # Phase 125c scrutiny fix: True when the swarm short-circuited
    # because rationale hasn't changed since the last successful run.
    # Lets the chain caller in workers.py also skip Validate (no
    # candidates to validate when Generate didn't run).
    skipped_fresh: bool = False


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
    save: bool = True,
    force: bool = False,
) -> GenerateSwarmReport:
    """Run the Generate swarm and (optionally) persist deduped output.

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
        save: when True (default), persist deduped concepts via
            ``concept_store.save_many``. Set False when chaining into
            the Validate swarm (T3b) — Validate re-saves with reconciled
            statuses, so saving twice is wasted work and produces
            transient pre-Validate rows in the store.
        force: bypass the freshness short-circuit (which skips the swarm
            when rationale hasn't changed since the last successful run).

    Returns a GenerateSwarmReport with per-scope emission counts and
    the deduped ``concepts`` list (always populated, regardless of save).
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

    # Freshness short-circuit — back-to-back runs with unchanged
    # rationale skip Generate (and therefore Validate, downstream).
    # Mirrors Phase 125b's single-call freshness check but reads/writes
    # its own manifest file so a 125b → 125c upgrade doesn't wrongly
    # short-circuit on the legacy artifact.
    if not force and not dry_run:
        rationale_count, rationale_max_ts = _rationale_fingerprint(project_id)
        if rationale_count > 0:
            manifest = _read_gen_swarm_manifest(idx_dir)
            if manifest:
                last_count = int(manifest.get("rationale_count") or 0)
                last_ts = float(manifest.get("rationale_max_updated_at") or 0.0)
                manifest_revision = int(manifest.get("prompt_revision") or 0)
                # Skip only when rationale is unchanged AND prompts haven't
                # been bumped. Prompt-revision mismatch forces a re-run so
                # behavior changes (banned-list additions, rubric tweaks,
                # grounding composition) take effect immediately.
                if (
                    last_count == rationale_count
                    and rationale_max_ts <= last_ts
                    and manifest_revision == _GEN_PROMPT_REVISION
                ):
                    logger.info(
                        "[GenSwarm] skipping for %s — rationale unchanged "
                        "(count=%d, max_ts=%.0f). Pass force=True to override.",
                        project_id, rationale_count, rationale_max_ts,
                    )
                    report.skipped_fresh = True
                    report.elapsed_seconds = time.time() - t0
                    try:
                        from prep.services.pipeline_telemetry import record_event
                        record_event(
                            idx_dir, "generate_swarm_skipped_fresh",
                            {
                                "rationale_count": rationale_count,
                                "last_run_ts": float(manifest.get("completed_at") or 0.0),
                            },
                            stage="concepts", project_id=project_id,
                        )
                    except Exception:
                        pass
                    return report

    # Load shared grounding + planning-doc grounding.
    # Investigation 2026-08-22 (A): pass project_root so load_grounding
    # can populate source_slices for anchor files.
    grounding = load_grounding(
        project_id, idx_dir=idx_dir, project_name=project_name,
        project_root=project_root,
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
    report.concepts = list(deduped)

    # Persist with kind='concept' via the existing save path. Skipped
    # when caller plans to chain into Validate (which re-saves with
    # reconciled statuses).
    if deduped and save:
        try:
            from prep.services.concept_store import concept_store
            save_dicts = [c.to_save_dict() for c in deduped]
            saved, skipped = concept_store.save_many(project_id, save_dicts)
            report.saved = saved
            report.skipped = skipped
        except Exception as e:
            logger.warning("[GenSwarm] save_many failed: %s", e, exc_info=True)

    # Write the freshness manifest so the next run can short-circuit
    # when rationale is unchanged AND prompts haven't been bumped.
    # Investigation 2026-08-22 (C4): only write when we actually emitted
    # candidates. Writing on an empty/failed run permanently locks out
    # future runs because the freshness check sees a matching fingerprint
    # and skips — even though the last run produced nothing.
    if report.candidates_after_dedup > 0:
        try:
            rcount, rts = _rationale_fingerprint(project_id)
            _write_gen_swarm_manifest(idx_dir, {
                "rationale_count": rcount,
                "rationale_max_updated_at": rts,
                "completed_at": time.time(),
                "swarm_size": swarm_size,
                "candidates_after_dedup": report.candidates_after_dedup,
                "prompt_revision": _GEN_PROMPT_REVISION,
            })
        except Exception:
            logger.debug("[GenSwarm] manifest write failed", exc_info=True)
    else:
        logger.info(
            "[GenSwarm] skipping manifest write — 0 candidates after dedup "
            "(failed_workers=%d). Next run will not be short-circuited.",
            len(report.failed_workers),
        )

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
