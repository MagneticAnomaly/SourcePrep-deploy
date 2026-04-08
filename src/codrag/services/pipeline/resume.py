"""
ResumeStrategy — Pipeline resume point detection and coverage gap analysis.

Phase 72 Stage 3: Extracted from orchestrator.py. Determines where to
start or resume a pipeline run based on manifest state on disk.

Key methods:
- detect_resume_point: Scans manifests to find first incomplete stage
- check_coverage_gap: Compares filesystem vs trace for stale/untraced files
- refresh_manifest_hashes: Updates file_hashes without re-running structural
- should_skip_stage_freshness: Checks if outputs are newer than inputs
- maybe_retrigger_for_coverage: Auto-retriggers after completion if gaps exist
"""
from __future__ import annotations

import logging
import os
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
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            return 0

        store = ManifestStore(idx_dir)

        baseline_mtime = 0.0
        if not skip_mtime_cascade:
            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)

        stage_decisions: list[dict] = []

        for i, stage in enumerate(stages):
            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            if manifest_file:
                mpath = idx_dir / manifest_file  # for logging/size checks
                if store.provenance_exists(stage):
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
                            else:
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
                    output_file = STAGE_OUTPUT_FILE.get(stage)
                    if output_file:
                        opath = idx_dir / output_file
                        if not opath.exists() or opath.stat().st_size == 0:
                            logger.warning(
                                "Stage %s has manifest but output %s is "
                                "missing/empty — treating as incomplete",
                                stage.value, output_file,
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "INCOMPLETE",
                                "reason": (
                                    f"Manifest exists but {output_file} "
                                    f"missing/empty (stage may have been skipped)"
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
                    elif stage == StageId.ATLAS:
                        segments_path = idx_dir / "atlas_segments_manifest.json"
                        if not segments_path.exists() or segments_path.stat().st_size == 0:
                            logger.warning(
                                "Atlas manifest exists but atlas_segments_manifest.json "
                                "is missing/empty — treating as incomplete"
                            )
                            stage_decisions.append({
                                "stage": stage.value,
                                "decision": "INCOMPLETE",
                                "reason": "Manifest exists but atlas_segments_manifest.json missing",
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
            from codrag.core.project_registry import project_index_dir
            from codrag.core.trace.coverage import compute_trace_coverage
            from codrag.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            repo_root = Path(project.path)

            pcfg = project.config or {}
            include_globs = pcfg.get("include_globs") or None
            exclude_globs = pcfg.get("exclude_globs") or None
            max_file_bytes = int(pcfg.get("max_file_bytes") or 500_000)

            coverage = compute_trace_coverage(
                repo_root=repo_root,
                index_dir=idx_dir,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
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
    def refresh_manifest_hashes(project_id: str) -> int:
        """Refresh ``file_hashes`` in ``trace_manifest.json`` without re-running
        the structural stage.

        Returns the number of hashes that changed.
        """
        import json as _json
        import tempfile

        from codrag.core.ids import stable_file_hash
        from codrag.core.trace.utils import _to_posix

        try:
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
        except ImportError:
            return 0

        try:
            project = require_project(project_id)
        except Exception:
            return 0

        idx_dir = Path(project_index_dir(project))
        manifest_path = idx_dir / "trace_manifest.json"

        if not manifest_path.exists():
            return 0

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = _json.load(f)
        except Exception:
            return 0

        old_hashes: dict[str, str] = manifest.get("file_hashes") or {}
        if not old_hashes:
            return 0

        repo_root = Path(project.path).resolve()
        pcfg = project.config or {}
        max_file_bytes = int(pcfg.get("max_file_bytes") or 500_000)

        # Collect traced paths from trace_nodes.jsonl for backfill
        traced_node_paths: set[str] = set()
        nodes_path = idx_dir / "trace_nodes.jsonl"
        if nodes_path.exists():
            try:
                with open(nodes_path, encoding="utf-8") as nf:
                    for line in nf:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            node = _json.loads(line)
                            if node.get("kind") == "file" and node.get("file_path"):
                                traced_node_paths.add(node["file_path"])
                        except _json.JSONDecodeError:
                            continue
            except Exception:
                pass

        import pathspec

        from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
        from codrag.core.trace.builder import TraceBuilder
        from codrag.core.trace.utils import _is_relevant

        gitignore_spec = None
        gitignore_path = repo_root / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
            except Exception:
                pass

        default_builder = TraceBuilder(
            repo_root=repo_root,
            index_dir=idx_dir,
            max_file_bytes=max_file_bytes,
        )
        include_globs = default_builder.include_globs
        exclude_globs = default_builder.exclude_globs

        updated = 0
        new_hashes = dict(old_hashes)
        seen_paths: set[str] = set()

        for root_dir, dirs, filenames in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIR_NAMES and not d.startswith(".")]
            root_path = Path(root_dir)
            for fname in filenames:
                file_path = root_path / fname
                if file_path.is_symlink():
                    continue
                rel_path = _to_posix(str(file_path.relative_to(repo_root)))

                if gitignore_spec and gitignore_spec.match_file(rel_path):
                    continue
                if not _is_relevant(rel_path, include_globs, exclude_globs):
                    continue

                try:
                    fsize = file_path.stat().st_size
                    if fsize > max_file_bytes:
                        with open(file_path, encoding="utf-8", errors="ignore") as hf:
                            source = hf.read(50_000)
                    else:
                        source = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                current_hash = stable_file_hash(source)
                seen_paths.add(rel_path)

                prev_hash = old_hashes.get(rel_path)
                if prev_hash is None:
                    if rel_path in traced_node_paths:
                        new_hashes[rel_path] = current_hash
                        updated += 1
                elif prev_hash != current_hash:
                    new_hashes[rel_path] = current_hash
                    updated += 1

        # Remove hashes for deleted files
        deleted_paths = set(old_hashes.keys()) - seen_paths
        for dp in deleted_paths:
            del new_hashes[dp]
            updated += 1

        if updated == 0:
            return 0

        # Write atomically — preserve built_at to avoid mtime cascade
        manifest["file_hashes"] = new_hashes
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                dir=str(idx_dir),
                delete=False,
                encoding="utf-8",
            )
            _json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, manifest_path)
            logger.info(
                "Refreshed %d file_hashes in trace_manifest.json for %s "
                "(added/updated: %d, deleted: %d)",
                updated,
                project_id,
                updated - len(deleted_paths),
                len(deleted_paths),
            )
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            logger.warning(
                "Failed to write updated file_hashes for %s",
                project_id,
                exc_info=True,
            )

        return updated

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
            from codrag.core.project_registry import project_index_dir
            from codrag.services.pipeline.stages import STAGE_INPUT_FILES
            from codrag.services.pipeline_integrity import STAGE_DATA_FILES, integrity_guard
            from codrag.services.project_helpers import require_project

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
        refresh_hashes_fn: Callable[[str], int],
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
                    from codrag.services.settings_store import settings as _ss

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

                # Refresh hashes before checking
                try:
                    refreshed = refresh_hashes_fn(project_id)
                    if refreshed > 0:
                        logger.info(
                            "Coverage retrigger: refreshed %d file hashes for %s",
                            refreshed,
                            project_id,
                        )
                except Exception:
                    pass

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
