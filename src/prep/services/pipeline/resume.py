"""
ResumeStrategy — Pipeline resume point detection and coverage gap analysis.

Phase 72 Stage 3: Extracted from orchestrator.py. Determines where to
start or resume a pipeline run based on manifest state on disk.

Key methods:
- detect_resume_point: Scans manifests to find first incomplete stage
- check_coverage_gap: Compares filesystem vs trace for stale/untraced files
- should_skip_stage_freshness: Checks if outputs are newer than inputs
- maybe_retrigger_for_coverage: Auto-retriggers after completion if gaps exist
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest_store import ManifestStore
from .stages import (
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    StageId,
)

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage_group_active_in_journal(project_id: str, stage: StageId) -> bool:
    """Phase 128: True iff the journal shows an active run for the group
    that owns ``stage``.

    Used by all recovery-stub writers in this module to refuse stub
    writes during a live run. Without this, a parallel resume scan can
    write a "recovered, finished_at=NOW" stub claiming a stage finished
    while the actual worker (post-F-67 manifest delete) is still
    computing, producing inconsistent on-disk state.
    """
    try:
        from .stages import (
            DEEP_ENRICHMENT_STAGES,
            FAST_SYNC_STAGES,
            FINALIZE_STAGES,
        )
        from prep.services.pipeline_journal import journal as _journal

        if stage in FAST_SYNC_STAGES:
            group_name = "fast_sync"
        elif stage in DEEP_ENRICHMENT_STAGES:
            group_name = "deep_enrichment"
        elif stage in FINALIZE_STAGES:
            group_name = "finalize"
        else:
            return False

        return _journal.get_active_run(project_id, group_name) is not None
    except Exception:
        logger.debug(
            "Phase 128: active-run check failed for %s (non-fatal)",
            stage.value, exc_info=True,
        )
        return False


# Delay before checking coverage gaps after pipeline completion
COVERAGE_RETRIGGER_DELAY = 15.0  # seconds


class ResumeStrategy:
    """Determines where to start or resume a pipeline run.

    All methods are static — no instance state. Uses ManifestStore for
    manifest queries and disk state inspection.
    """

    @staticmethod
    def detect_resume_point(
        project_id: str,
        stages: list[StageId],
        skip_mtime_cascade: bool = False,
        pfl_fn: Callable[[str], Any] | None = None,
    ) -> int:
        """Detect the first incomplete stage by checking manifest files on disk.

        A stage is considered "complete" if its manifest file exists.
        Returns the index of the first incomplete stage. If all stages
        are complete, returns ``len(stages)``.

        Args:
            pfl_fn: Optional callable (project_id) -> pipeline file logger
        """
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            return 0

        store = ManifestStore(idx_dir)

        baseline_mtime = 0.0
        if not skip_mtime_cascade:
            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)

        stage_decisions: list[dict] = []

        # Phase 118 U24: read the rebuild barrier once for the whole
        # detection pass. Used below to identify manifests whose recorded
        # finished_at predates the current rebuild — those are pre-rebuild
        # artifacts and don't satisfy the rebuild's "stage finished"
        # condition, even when present and structurally valid (non-stub).
        _u24_barrier_floor: float | None = None
        try:
            from .recovery import read_reset_barrier as _u24_read_barrier
            _u24_binfo = _u24_read_barrier(project_id)
            if _u24_binfo:
                _wa = _u24_binfo.get("written_at")
                if isinstance(_wa, (int, float)):
                    _u24_barrier_floor = float(_wa)
        except Exception:
            _u24_barrier_floor = None

        for i, stage in enumerate(stages):
            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            if manifest_file:
                mpath = idx_dir / manifest_file  # for logging/size checks
                if store.provenance_exists(stage):
                    # Phase 118 U24: barrier-floor check for non-stub manifests.
                    # When a rebuild is in flight (barrier active), a manifest
                    # whose finished_at predates the barrier is from a prior
                    # run and does not prove the stage ran in this rebuild.
                    # Without this, a paused rebuild with stale downstream
                    # manifests (e.g. clustering finished_at on May 6 while
                    # the May 8 rebuild only made it through stage 7) is
                    # reported as "all complete" because the old finished_at
                    # passes the existence check. Selfheal touches mtimes at
                    # rebuild start, so mtime alone is unreliable — we need
                    # to read finished_at from the manifest body itself.
                    if _u24_barrier_floor is not None:
                        try:
                            md = store.read_provenance(stage)
                            if isinstance(md, dict) and not md.get("recovered"):
                                fa_str = md.get("finished_at")
                                fa_ts: float | None = None
                                if isinstance(fa_str, str):
                                    try:
                                        from datetime import datetime
                                        fa_ts = datetime.fromisoformat(
                                            fa_str.replace("Z", "+00:00")
                                        ).timestamp()
                                    except Exception:
                                        fa_ts = None
                                elif isinstance(fa_str, (int, float)):
                                    fa_ts = float(fa_str)
                                if fa_ts is not None and fa_ts < _u24_barrier_floor:
                                    logger.warning(
                                        "Stage %s manifest finished_at=%s "
                                        "predates rebuild barrier — treating "
                                        "as INCOMPLETE so the rebuild runs it",
                                        stage.value, fa_str,
                                    )
                                    stage_decisions.append({
                                        "stage": stage.value,
                                        "decision": "PRE_BARRIER_STALE",
                                        "reason": (
                                            f"Manifest finished_at={fa_str} "
                                            f"predates barrier_floor={_u24_barrier_floor:.0f} "
                                            f"— stage hasn't run in current rebuild"
                                        ),
                                    })
                                    ResumeStrategy._log_resume_decisions(
                                        project_id, stages, i, stage_decisions,
                                        skip_mtime_cascade, pfl_fn,
                                    )
                                    return i
                        except Exception:
                            logger.debug(
                                "U24 finished_at check failed for %s",
                                stage.value, exc_info=True,
                            )

                    # Phase 72D: Stub manifest check.
                    # Stubs are created by auto-recovery (Phase 72C) when a
                    # manifest is missing but a data file exists. However, the
                    # data file may belong to a PRIOR stage (e.g. enrichment's
                    # trace_epistemic.jsonl is shared with deepening), so a
                    # stub does NOT prove the stage itself completed.
                    #
                    # Stages with dedicated output files (enrichment, clustering, etc.)
                    # can be validated by checking their output exists and is substantial.
                    # Stages with NO dedicated output (deep_knowledge) or SHARED output
                    # (deepening shares trace_epistemic.jsonl with enrichment) need the
                    # stub to be treated as incomplete.
                    if store.is_stub_manifest(stage):
                        # Phase 118 U20b: while a reset_barrier is active, any
                        # stub manifest written during this rebuild's lifetime
                        # is recovery-derived, not the result of the stage
                        # actually running. The rebuild's whole purpose is to
                        # genuinely re-execute every stage, so trusting a stub
                        # marks the stage as falsely complete and the rebuild
                        # never finishes. Treat the stub as INCOMPLETE so
                        # resume detection pins here and the user gets a
                        # paused state machine to resume from.
                        try:
                            from .recovery import read_reset_barrier
                            _binfo = read_reset_barrier(project_id)
                        except Exception:
                            _binfo = None
                        if _binfo is not None:
                            logger.warning(
                                "Stage %s has a stub manifest while a reset "
                                "barrier is active (rebuild in progress) — "
                                "treating as INCOMPLETE so the rebuild "
                                "actually runs the stage",
                                stage.value,
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "STUB_DURING_REBUILD",
                                "reason": (
                                    "Stub manifest detected with reset_barrier "
                                    "active — rebuild must re-execute this stage"
                                ),
                            })
                            ResumeStrategy._log_resume_decisions(
                                project_id, stages, i, stage_decisions,
                                skip_mtime_cascade, pfl_fn,
                            )
                            return i

                        # Stages that share output with prior stages or have no output
                        _SHARED_OUTPUT_STAGES = {
                            StageId.DEEPENING,       # shares trace_epistemic.jsonl with ENRICHMENT
                            StageId.DEEP_KNOWLEDGE,  # shares knowledge_* with KNOWLEDGE
                        }
                        if stage in _SHARED_OUTPUT_STAGES:
                            logger.warning(
                                "Stage %s has a stub manifest (auto-recovery) but "
                                "shares its output file with a prior stage — treating "
                                "as INCOMPLETE so it actually runs",
                                stage.value,
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "STUB_INCOMPLETE",
                                "reason": (
                                    "Stub manifest from auto-recovery — stage never "
                                    "actually completed (shared output with prior stage)"
                                ),
                            })
                            ResumeStrategy._log_resume_decisions(
                                project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                            )
                            return i

                        # For stages with dedicated output, verify the output
                        # file looks like it was produced by THIS stage, not just
                        # inherited from a prior run. Accept if output has
                        # substantial content.
                        output_file = STAGE_OUTPUT_FILE.get(stage)
                        if output_file:
                            opath = idx_dir / output_file
                            if not opath.exists() or opath.stat().st_size < 100:
                                logger.warning(
                                    "Stage %s has a stub manifest but output "
                                    "%s is missing/tiny — treating as INCOMPLETE",
                                    stage.value, output_file,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "STUB_NO_OUTPUT",
                                    "reason": (
                                        f"Stub manifest but {output_file} "
                                        f"missing or < 100 bytes"
                                    ),
                                })
                                ResumeStrategy._log_resume_decisions(
                                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                                )
                                return i

                            # Don't treat a stub as complete when
                            # pipeline_run_metadata shows this stage was
                            # pending in the most recent interrupted run —
                            # the output on disk is partial paused work, not
                            # a genuine completion signal.
                            from prep.services.pipeline_metadata import (
                                is_stage_pending_in_interrupted_run,
                            )
                            if is_stage_pending_in_interrupted_run(idx_dir, stage.value):
                                logger.warning(
                                    "Stage %s has a stub manifest and output %s "
                                    "(%d bytes), but last run was interrupted with "
                                    "this stage pending — treating as INCOMPLETE",
                                    stage.value, output_file, opath.stat().st_size,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "STUB_INTERRUPTED",
                                    "reason": (
                                        f"Stub manifest + output exists but last run "
                                        f"interrupted with {stage.value} pending — "
                                        f"output is partial paused work"
                                    ),
                                })
                                ResumeStrategy._log_resume_decisions(
                                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                                )
                                return i

                            logger.info(
                                "Stage %s has a stub manifest but dedicated "
                                "output %s exists (%d bytes) — accepting as complete",
                                stage.value, output_file, opath.stat().st_size,
                            )

                    # Phase 81: Generic output-file check for non-stub manifests.
                    # A manifest can exist even when the worker returned
                    # skipped:true (e.g. clustering skipped due to missing LLM).
                    # Without this, the resume detector thinks the stage is
                    # complete and skips it on every subsequent run.
                    #
                    # Phase 118 U10: BUT a stage that genuinely produced
                    # zero results (e.g. Edge Discovery on a project where
                    # no cross-file edges exist, or Validation on a clean
                    # graph) won't write an output file at all. The
                    # manifest still records `finished_at` because the
                    # worker did finish. Without an exception here, the
                    # resume detector misclassifies these legitimate
                    # zero-result completions as incomplete on every
                    # restart, which causes the orchestrator's hydration
                    # path to synthesize a ghost "Paused at <stage>" state
                    # in the UI even when the user has a fully-built
                    # project. Trust manifests that have `finished_at`
                    # set: that's the worker's signal that it ran to
                    # completion. Fall back to the strict output-file
                    # check only for manifests without `finished_at`
                    # (the original "skipped" / partial scenarios).
                    output_file = STAGE_OUTPUT_FILE.get(stage)
                    if output_file:
                        opath = idx_dir / output_file
                        if not opath.exists() or opath.stat().st_size == 0:
                            manifest_finished = False
                            try:
                                manifest_data = store.read_provenance(stage)
                                manifest_finished = bool(
                                    isinstance(manifest_data, dict)
                                    and manifest_data.get("finished_at")
                                )
                            except Exception:
                                manifest_finished = False
                            if manifest_finished:
                                logger.info(
                                    "Stage %s manifest has finished_at but output %s "
                                    "is empty/missing — accepting as a legitimate "
                                    "zero-result completion (Phase 118 U10)",
                                    stage.value, output_file,
                                )
                            else:
                                logger.warning(
                                    "Stage %s has manifest but output %s is "
                                    "missing/empty AND manifest has no finished_at "
                                    "— treating as incomplete",
                                    stage.value, output_file,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "INCOMPLETE",
                                    "reason": (
                                        f"Manifest exists but {output_file} "
                                        f"missing/empty and no finished_at recorded"
                                    ),
                                })
                                ResumeStrategy._log_resume_decisions(
                                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                                )
                                return i

                    # Structural: verify trace_nodes.jsonl exists
                    if stage == StageId.STRUCTURAL:
                        nodes_path = idx_dir / "trace_nodes.jsonl"
                        if not nodes_path.exists() or nodes_path.stat().st_size == 0:
                            logger.warning(
                                "Structural manifest exists but trace_nodes.jsonl is "
                                "missing/empty — treating as incomplete"
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "INCOMPLETE",
                                "reason": "Manifest exists but trace_nodes.jsonl missing/empty",
                            })
                            ResumeStrategy._log_resume_decisions(
                                project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                            )
                            return i

                    # Atlas: verify segments manifest exists
                    # Phase 118 U10: small projects may legitimately produce
                    # no atlas segments (atlas.json alone is the deliverable).
                    # Trust manifests with finished_at set; only flag as
                    # incomplete if the worker never recorded completion.
                    elif stage == StageId.ATLAS:
                        segments_path = idx_dir / "atlas_segments_manifest.json"
                        if not segments_path.exists() or segments_path.stat().st_size == 0:
                            atlas_finished = False
                            try:
                                atlas_md = store.read_provenance(stage)
                                atlas_finished = bool(
                                    isinstance(atlas_md, dict)
                                    and atlas_md.get("finished_at")
                                )
                            except Exception:
                                atlas_finished = False
                            if atlas_finished:
                                logger.info(
                                    "Atlas manifest has finished_at but "
                                    "atlas_segments_manifest.json missing — accepting "
                                    "as a legitimate no-segments completion (Phase 118 U10)"
                                )
                            else:
                                logger.warning(
                                    "Atlas manifest exists but atlas_segments_manifest.json "
                                    "is missing/empty AND no finished_at recorded — "
                                    "treating as incomplete"
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "INCOMPLETE",
                                    "reason": "Manifest exists but atlas_segments_manifest.json missing and no finished_at",
                                })
                                ResumeStrategy._log_resume_decisions(
                                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                                )
                                return i

                    # Staleness check
                    if (
                        not skip_mtime_cascade
                        and stage != StageId.STRUCTURAL
                        and baseline_mtime > 0
                    ):
                        manifest_mtime = store.provenance_mtime(stage)
                        age_gap = baseline_mtime - manifest_mtime
                        if manifest_mtime < baseline_mtime:
                            # Sub-second tolerance
                            if age_gap <= 5.0:
                                logger.info(
                                    "Stage %s manifest mtime gap is %.1fs "
                                    "(within 5s tolerance) — treating as COMPLETE",
                                    stage.value,
                                    age_gap,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "COMPLETE",
                                    "note": f"mtime gap {age_gap:.1f}s within tolerance",
                                    "manifest_size": mpath.stat().st_size,
                                })
                                continue

                            # Content-aware staleness: if output exists, touch and continue
                            output_file = STAGE_OUTPUT_FILE.get(stage)
                            has_existing_output = False
                            if output_file:
                                opath = idx_dir / output_file
                                if opath.exists() and opath.stat().st_size > 1024:
                                    has_existing_output = True
                            elif stage == StageId.ATLAS:
                                opath = idx_dir / "atlas.json"
                                output_file = "atlas.json"
                                if opath.exists() and opath.stat().st_size > 1024:
                                    has_existing_output = True
                            elif stage == StageId.DEEP_KNOWLEDGE:
                                # DEEP_KNOWLEDGE has no STAGE_OUTPUT_FILE entry
                                # (it re-embeds into the shared knowledge index).
                                # Treat knowledge_embeddings.npy as its completion
                                # marker so mtime cascades don't force a re-run
                                # when the embeddings already exist on disk.
                                opath = idx_dir / "knowledge_embeddings.npy"
                                output_file = "knowledge_embeddings.npy"
                                if opath.exists() and opath.stat().st_size > 1024:
                                    has_existing_output = True

                            if has_existing_output:
                                store.touch_provenance_mtime(stage, baseline_mtime)
                                logger.info(
                                    "Stage %s manifest is stale (gap=%.0fs) but has "
                                    "existing output (%s, %d bytes) — touching manifest "
                                    "and treating as COMPLETE",
                                    stage.value,
                                    age_gap,
                                    output_file,
                                    (idx_dir / output_file).stat().st_size,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "COMPLETE",
                                    "note": (
                                        f"mtime gap {age_gap:.0f}s but output exists "
                                        f"({output_file}) — manifest touched"
                                    ),
                                    "manifest_size": mpath.stat().st_size,
                                })
                                continue

                            # No output — genuinely stale
                            logger.info(
                                "Stage %s manifest is stale (%.0f < %.0f, gap=%.1fs) "
                                "and has NO existing output — restarting stage",
                                stage.value,
                                manifest_mtime,
                                baseline_mtime,
                                age_gap,
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "STALE_MTIME",
                                "reason": f"Manifest mtime {manifest_mtime:.0f} < structural mtime {baseline_mtime:.0f}",
                                "age_gap_seconds": round(age_gap, 1),
                            })
                            ResumeStrategy._log_resume_decisions(
                                project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                            )
                            return i

                    stage_decisions.append({
                        "stage": stage.value,
                        "decision": "COMPLETE",
                        "manifest_size": mpath.stat().st_size,
                    })
                    continue

                # Manifest missing or empty

                # Atlas crash-loop guard: if atlas.json AND segments manifest
                # both exist, write a recovery provenance manifest so
                # downstream freshness checks and resume detection work
                # correctly.  If only atlas.json exists (no segments),
                # Atlas needs to actually re-run.
                if stage == StageId.ATLAS:
                    atlas_json = idx_dir / "atlas.json"
                    segments_manifest = idx_dir / "atlas_segments_manifest.json"
                    if (
                        atlas_json.exists()
                        and atlas_json.stat().st_size > 10
                        and segments_manifest.exists()
                        and segments_manifest.stat().st_size > 10
                    ):
                        # Phase 128: Refuse to write a recovery stub if
                        # the journal says finalize is currently running.
                        # The orchestrator F-67-deletes atlas_manifest.json
                        # at stage start; a parallel resume scan that sees
                        # atlas.json + atlas_segments_manifest.json from a
                        # PRIOR run would otherwise write a stub claiming
                        # atlas finished while the worker is still
                        # computing. Same race as the downstream-proves-
                        # upstream stub at line 537.
                        if _stage_group_active_in_journal(project_id, stage):
                            logger.info(
                                "Phase 128: Refusing to write atlas crash-loop "
                                "stub — journal shows active finalize run "
                                "(avoiding F-67 race)"
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "ACTIVE_RUN_DEFER",
                                "reason": (
                                    "Active finalize run in journal — "
                                    "deferring atlas stub to avoid F-67 race"
                                ),
                            })
                            ResumeStrategy._log_resume_decisions(
                                project_id, stages, i, stage_decisions,
                                skip_mtime_cascade, pfl_fn,
                            )
                            return i

                        # Both data files exist — write a recovery manifest
                        # so downstream stages see correct mtimes.
                        store.write_provenance(stage, {
                            "format_version": "2.0",
                            "stage_id": "atlas",
                            "recovered": True,
                            "recovery_note": (
                                "Manifest reconstructed from existing "
                                "atlas.json + atlas_segments_manifest.json"
                            ),
                            "finished_at": _iso_now(),
                        })
                        logger.warning(
                            "Atlas manifest missing but atlas.json (%d bytes) "
                            "and segments manifest (%d bytes) exist — wrote "
                            "recovery manifest",
                            atlas_json.stat().st_size,
                            segments_manifest.stat().st_size,
                        )
                        stage_decisions.append({
                            "stage": stage.value,
                            "decision": "CRASH_RECOVERY",
                            "reason": (
                                f"Atlas manifest missing but atlas.json "
                                f"({atlas_json.stat().st_size} bytes) and "
                                f"segments ({segments_manifest.stat().st_size} "
                                f"bytes) exist — recovery manifest written"
                            ),
                        })
                        continue

                # Downstream-proves-upstream recovery: if ANY later stage in
                # this group has a completed manifest, the current stage must
                # have run to produce the inputs for it. Pipeline stages run
                # sequentially through _start_group, so a later manifest can
                # only exist if earlier stages finished. This handles the
                # "zombie paused validation" symptom — a wipe / partial reset
                # / prior-bug deleted this stage's manifest, but the work
                # actually completed. Write a recovery manifest so resume
                # detection stops pinning here on every daemon restart.
                #
                # Critical: reject downstream STUB manifests. Selfheal writes
                # stubs (restored:true) from orphan outputs and backup
                # sources — those are NOT proof the stage ran in order.
                # Treating a stub as proof propagates false completion back
                # up the chain, skipping multiple legitimate stages.
                # Phase 118 U20: if a reset barrier is active (rebuild in
                # progress), reject downstream evidence written BEFORE the
                # barrier — those manifests are from a prior run and don't
                # prove the missing stage ran during the current rebuild.
                # Without this check, a rebuild interrupted at e.g. catalogue
                # gets fake-recovered using last-week's validation manifest,
                # which marks the current rebuild as "all complete" without
                # the missing stage ever actually running.
                barrier_floor: float | None = None
                try:
                    from .recovery import read_reset_barrier
                    binfo = read_reset_barrier(project_id)
                    if binfo:
                        wa = binfo.get("written_at")
                        if isinstance(wa, (int, float)):
                            barrier_floor = float(wa)
                except Exception:
                    barrier_floor = None

                downstream_complete_stage = None
                for j in range(i + 1, len(stages)):
                    next_manifest = STAGE_MANIFEST_FILE.get(stages[j])
                    if not next_manifest:
                        continue
                    npath = idx_dir / next_manifest
                    if not (npath.exists() and npath.stat().st_size > 0):
                        continue
                    if store.is_stub_manifest(stages[j]):
                        continue
                    # Phase 118 U20 (finished_at variant): mtime is unreliable
                    # because selfheal touches downstream manifest mtimes at
                    # rebuild kickoff to keep them above the structural baseline.
                    # Read finished_at from the manifest BODY instead — that's
                    # written once when the worker actually completes and is
                    # never touched again. Without this, U20 was accepting
                    # deepening's May-6 manifest as evidence that clustering
                    # ran in today's rebuild simply because selfheal had
                    # touched its mtime to today.
                    if barrier_floor is not None:
                        try:
                            md = store.read_provenance(stages[j])
                            fa_ts: float | None = None
                            if isinstance(md, dict):
                                fa_str = md.get("finished_at")
                                if isinstance(fa_str, str):
                                    try:
                                        from datetime import datetime
                                        fa_ts = datetime.fromisoformat(
                                            fa_str.replace("Z", "+00:00")
                                        ).timestamp()
                                    except Exception:
                                        fa_ts = None
                                elif isinstance(fa_str, (int, float)):
                                    fa_ts = float(fa_str)
                            if fa_ts is None:
                                # Fall back to mtime if finished_at is missing.
                                fa_ts = npath.stat().st_mtime
                            if fa_ts < barrier_floor:
                                continue
                        except Exception:
                            pass
                    downstream_complete_stage = stages[j]
                    break

                if downstream_complete_stage is not None:
                    # Phase 128: Refuse to write a recovery stub if the
                    # journal says this stage's group is currently running.
                    # See _stage_group_active_in_journal for the full F-67
                    # race rationale. Observed at 21:22:35 on 2026-05-05 in
                    # the user's pipeline.
                    if _stage_group_active_in_journal(project_id, stage):
                        logger.info(
                            "Phase 128: Refusing to write downstream-proves-"
                            "upstream stub for %s — journal shows active run "
                            "(avoiding F-67 race)",
                            stage.value,
                        )
                        stage_decisions.append({
                            "stage": stage.value,
                            "decision": "ACTIVE_RUN_DEFER",
                            "reason": (
                                "Active run in journal — deferring recovery "
                                "stub to avoid F-67 race"
                            ),
                        })
                        ResumeStrategy._log_resume_decisions(
                            project_id, stages, i, stage_decisions,
                            skip_mtime_cascade, pfl_fn,
                        )
                        return i

                    try:
                        store.write_provenance(stage, {
                            "format_version": "2.0",
                            "stage_id": stage.value,
                            "recovered": True,
                            "recovery_note": (
                                f"Manifest missing but downstream stage "
                                f"{downstream_complete_stage.value} completed — "
                                f"stage must have finished to produce its input"
                            ),
                            "finished_at": _iso_now(),
                        })
                        logger.warning(
                            "Stage %s manifest missing but downstream %s is "
                            "complete — wrote recovery manifest",
                            stage.value, downstream_complete_stage.value,
                        )
                        stage_decisions.append({
                            "stage": stage.value,
                            "decision": "CRASH_RECOVERY",
                            "reason": (
                                f"Manifest missing but downstream "
                                f"{downstream_complete_stage.value} completed — "
                                f"recovery manifest written"
                            ),
                        })
                        continue
                    except Exception:
                        logger.debug(
                            "Failed to write recovery manifest for %s "
                            "(non-fatal — falling through to MISSING_MANIFEST)",
                            stage.value, exc_info=True,
                        )

                stage_decisions.append({
                    "stage": stage.value,
                    "decision": "MISSING_MANIFEST",
                    "reason": f"{manifest_file} missing or empty",
                })
                ResumeStrategy._log_resume_decisions(
                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                )
                return i

            # Stage has no manifest mapping — check output file
            output_file = STAGE_OUTPUT_FILE.get(stage)
            if output_file:
                opath = idx_dir / output_file
                if opath.exists() and opath.stat().st_size > 0:
                    stage_decisions.append({
                        "stage": stage.value,
                        "decision": "COMPLETE",
                        "output_size": opath.stat().st_size,
                    })
                    continue
                stage_decisions.append({
                    "stage": stage.value,
                    "decision": "MISSING_OUTPUT",
                    "reason": f"{output_file} missing or empty",
                })
                ResumeStrategy._log_resume_decisions(
                    project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
                )
                return i

            # No manifest and no output — needs to run
            stage_decisions.append({
                "stage": stage.value,
                "decision": "NO_OUTPUT_FILE",
                "reason": "No manifest or output file configured",
            })
            ResumeStrategy._log_resume_decisions(
                project_id, stages, i, stage_decisions, skip_mtime_cascade, pfl_fn
            )
            return i

        # All stages complete
        ResumeStrategy._log_resume_decisions(
            project_id, stages, len(stages), stage_decisions, skip_mtime_cascade, pfl_fn
        )
        return len(stages)

    @staticmethod
    def _log_resume_decisions(
        project_id: str,
        stages: list,
        resume_index: int,
        stage_decisions: list[dict],
        skip_mtime_cascade: bool,
        pfl_fn: Callable[[str], Any] | None = None,
    ) -> None:
        """Log the per-stage resume point decision audit trail."""
        try:
            pfl = pfl_fn(project_id) if pfl_fn else None
            if not pfl:
                return

            all_complete = resume_index >= len(stages)
            resume_stage = None if all_complete else stages[resume_index].value

            pfl.decision("resume_point", resume_stage or "all_complete", {
                "resume_index": resume_index,
                "total_stages": len(stages),
                "all_complete": all_complete,
                "skip_mtime_cascade": skip_mtime_cascade,
                "per_stage": stage_decisions,
            })
        except Exception:
            logger.debug("Failed to log resume decisions (non-fatal)", exc_info=True)

    @staticmethod
    def check_coverage_gap(project_id: str, include_paths: bool = False) -> dict[str, Any]:
        """Check if there are files that should be traced but aren't.

        Returns dict with total, traced, untraced, stale, needs_rebuild,
        coverage_pct, and optionally changed_paths.
        """
        try:
            from prep.core.project_registry import project_index_dir
            from prep.core.trace.coverage import compute_trace_coverage
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            repo_root = Path(project.path)

            pcfg = project.config or {}
            include_globs = pcfg.get("include_globs") or None
            exclude_globs = pcfg.get("exclude_globs") or None
            max_file_bytes = int(pcfg.get("max_file_bytes") or 500_000)

            # Phase 89: Pass user_exclude_globs from trace config, matching
            # the API endpoint at trace_routes/query.py. Without this,
            # AGENTS.md and other excluded files appear as "untraced" in the
            # coverage gap check, triggering infinite rebuild loops.
            trace_cfg = pcfg.get("trace") if isinstance(pcfg, dict) else None
            trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
            user_exclude_globs = [str(p) for p in trace_ignore] if isinstance(trace_ignore, list) else []

            coverage = compute_trace_coverage(
                repo_root=repo_root,
                index_dir=idx_dir,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                user_exclude_globs=user_exclude_globs,
                max_file_bytes=max_file_bytes,
            )
            summary = coverage.get("summary", {})
            untraced = summary.get("untraced", 0)
            stale = summary.get("stale", 0)

            result: dict[str, Any] = {
                "total": summary.get("total", 0),
                "traced": summary.get("traced", 0),
                "untraced": untraced,
                "stale": stale,
                "needs_rebuild": (untraced + stale) > 0,
                "coverage_pct": summary.get("coverage_pct", 0.0),
            }

            if include_paths and result["needs_rebuild"]:
                changed: set[str] = set()
                for f in coverage.get("untraced", []):
                    changed.add(f["path"])
                for f in coverage.get("stale", []):
                    changed.add(f["path"])
                result["changed_paths"] = changed

            return result
        except Exception:
            logger.warning(
                "Coverage gap check failed for %s — defaulting to needs_rebuild=True",
                project_id,
                exc_info=True,
            )
            return {
                "total": 0,
                "traced": 0,
                "untraced": 0,
                "stale": 0,
                "needs_rebuild": True,
                "coverage_pct": 0.0,
            }

    @staticmethod
    def should_skip_stage_freshness(
        run_project_id: str,
        stage: StageId,
        is_incremental: bool,
        pfl: Any = None,
    ) -> tuple[bool, str | None]:
        """Check if a stage's outputs are already newer than its inputs.

        Returns (should_skip, reason). Does NOT mutate the run state —
        the caller handles marking skipped and advancing.
        """
        if is_incremental:
            logger.debug(
                "Freshness check bypassed for %s/%s (incremental run)",
                run_project_id,
                stage.value,
            )
            if pfl:
                pfl.log(stage.value, "Freshness check bypassed (incremental mode)")
            return False, None

        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline.stages import STAGE_INPUT_FILES
            from prep.services.pipeline_integrity import STAGE_DATA_FILES, integrity_guard
            from prep.services.project_helpers import require_project

            project = require_project(run_project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            # If the stage has no provenance manifest, it never completed
            # successfully — don't skip it regardless of file mtimes.
            # This prevents the case where a stage's output IS its input
            # (e.g. deepening writes to trace_epistemic.jsonl) causing
            # the freshness check to always say "already current."
            if not store.provenance_exists(stage):
                return False, None

            input_files = STAGE_INPUT_FILES.get(stage, [])
            output_files = STAGE_DATA_FILES.get(stage.value, [])

            if not input_files:
                return False, None

            should_skip, reason = integrity_guard.check_stage_freshness(
                idx_dir, input_files, output_files
            )
            return should_skip, reason
        except Exception:
            logger.debug(
                "Freshness check failed (non-fatal) for %s/%s",
                run_project_id,
                stage.value,
                exc_info=True,
            )
        return False, None

    @staticmethod
    def maybe_retrigger_for_coverage(
        project_id: str,
        run_fast_sync_fn: Callable[[str], bool],
        is_any_active_fn: Callable[[str], bool],
        pfl: Any = None,
    ) -> None:
        """After pipeline completion, check for untraced/stale files and
        auto-retrigger if needed. Runs in a delayed background thread.
        """

        def _check_and_retrigger():
            try:
                time.sleep(COVERAGE_RETRIGGER_DELAY)

                # Respect pipeline mode
                try:
                    from prep.services.settings_store import settings as _ss

                    pc = _ss.get("pipeline_config") or {}
                    fast_auto = (pc.get("fast_sync") or {}).get("auto", False)
                    if not fast_auto:
                        logger.debug(
                            "Coverage retrigger skipped for %s — pipeline in manual mode",
                            project_id,
                        )
                        return
                except Exception:
                    pass

                # Don't retrigger if another run started
                if is_any_active_fn(project_id):
                    logger.debug(
                        "Coverage retrigger skipped for %s — pipeline already running",
                        project_id,
                    )
                    return

                gap = ResumeStrategy.check_coverage_gap(project_id)
                if not gap["needs_rebuild"]:
                    logger.info(
                        "Coverage check for %s: %d/%d files traced (%.1f%%) — no retrigger needed",
                        project_id,
                        gap["traced"],
                        gap["total"],
                        gap["coverage_pct"],
                    )
                    return

                stale_count = gap.get("stale", 0)
                untraced_count = gap.get("untraced", 0)

                # Only retrigger for STALE files
                if stale_count == 0:
                    if untraced_count > 0:
                        logger.info(
                            "Coverage check for %s: 0 stale, %d untraced "
                            "(need structural rebuild) — no retrigger",
                            project_id,
                            untraced_count,
                        )
                    return

                logger.info(
                    "Coverage gap detected for %s: %d untraced + %d stale "
                    "out of %d total files (%.1f%% coverage) — retriggering fast sync",
                    project_id,
                    untraced_count,
                    stale_count,
                    gap["total"],
                    gap["coverage_pct"],
                )
                if pfl:
                    pfl.log(
                        "coverage_gap",
                        f"Retriggering: {untraced_count} untraced + {stale_count} stale files",
                    )

                started = run_fast_sync_fn(project_id)
                logger.info("Coverage retrigger for %s: started=%s", project_id, started)
            except Exception:
                logger.debug("Coverage retrigger failed for %s", project_id, exc_info=True)

        t = threading.Thread(target=_check_and_retrigger, daemon=True)
        t.start()
