"""Tests for ResumeStrategy — Phase 72 Stage 3.

Tests the resume point detection logic that determines where to start
or resume a pipeline run. This is the #1 source of pipeline bugs per
the Bug Genealogy doc, so thorough testing is critical.
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.pipeline.manifest_store import ManifestStore
from codrag.services.pipeline.resume import ResumeStrategy
from codrag.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    StageId,
)


@pytest.fixture
def idx_dir(tmp_path):
    return tmp_path


@pytest.fixture
def store(idx_dir):
    return ManifestStore(idx_dir)


def _mock_project(idx_dir, project_path=None):
    """Create mocks so require_project/project_index_dir resolve to idx_dir."""
    project = MagicMock()
    project.id = "test-proj"
    project.path = str(project_path or idx_dir.parent)
    project.name = "Test Project"
    project.config = {}
    return project


def _patch_project(idx_dir):
    """Context manager that patches require_project and project_index_dir at their source."""
    project = _mock_project(idx_dir)
    return patch.multiple(
        "codrag.services.project_helpers",
        require_project=MagicMock(return_value=project),
    ), patch(
        "codrag.core.project_registry.project_index_dir",
        return_value=str(idx_dir),
    )


class _PatchProject:
    """Helper to patch project resolution for ResumeStrategy tests."""
    def __init__(self, idx_dir):
        self.idx_dir = idx_dir
        self.project = _mock_project(idx_dir)
        self._patches = []

    def __enter__(self):
        p1 = patch("codrag.services.project_helpers.require_project", return_value=self.project)
        p2 = patch("codrag.core.project_registry.project_index_dir", return_value=str(self.idx_dir))
        self._patches = [p1, p2]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *args):
        for p in self._patches:
            p.stop()


class TestDetectResumePoint:
    def test_returns_0_when_no_manifests(self, idx_dir):
        """No manifests on disk → start from scratch (index 0)."""
        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point("test-proj", FAST_SYNC_STAGES)
        assert result == 0

    def test_returns_len_when_all_complete(self, idx_dir, store):
        """All manifests present → all stages complete."""
        for stage in FAST_SYNC_STAGES:
            store.write_provenance(stage, {"stage_id": stage.value})
        # Structural also needs trace_nodes.jsonl
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", FAST_SYNC_STAGES, skip_mtime_cascade=True,
            )
        assert result == len(FAST_SYNC_STAGES)

    def test_resumes_from_first_missing_manifest(self, idx_dir, store):
        """If structural and inferred_edges manifests exist but catalogue is missing,
        resume from index 2 (catalogue)."""
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        store.write_provenance(StageId.INFERRED_EDGES, {"stage_id": "inferred_edges"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", FAST_SYNC_STAGES, skip_mtime_cascade=True,
            )
        assert result == 2  # catalogue

    def test_structural_incomplete_when_nodes_missing(self, idx_dir, store):
        """Structural manifest exists but trace_nodes.jsonl is missing → incomplete."""
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        # No trace_nodes.jsonl

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", FAST_SYNC_STAGES, skip_mtime_cascade=True,
            )
        assert result == 0  # restart from structural

    def test_atlas_incomplete_when_segments_missing(self, idx_dir, store):
        """Atlas manifest exists but atlas_segments_manifest.json missing → incomplete."""
        # Set up all deep enrichment stages as complete except atlas
        for stage in DEEP_ENRICHMENT_STAGES:
            store.write_provenance(stage, {"stage_id": stage.value})
        # Atlas has manifest but no segments
        # (no atlas_segments_manifest.json)

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
            )
        # Should stop at atlas (index 3 in deep enrichment stages)
        atlas_idx = list(DEEP_ENRICHMENT_STAGES).index(StageId.ATLAS)
        assert result == atlas_idx

    def test_atlas_crash_recovery_when_json_exists(self, idx_dir, store):
        """Atlas manifest missing but atlas.json exists → treat as complete."""
        for stage in DEEP_ENRICHMENT_STAGES:
            if stage != StageId.ATLAS:
                store.write_provenance(stage, {"stage_id": stage.value})
        # No atlas manifest, but atlas.json exists
        (idx_dir / "atlas.json").write_text('{"content": "test atlas", "mode": "llm"}')

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
            )
        assert result == len(DEEP_ENRICHMENT_STAGES)

    def test_mtime_cascade_skipped_when_flag_set(self, idx_dir, store):
        """With skip_mtime_cascade=True, stale mtimes don't trigger restarts."""
        # Write structural with current time
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        # Write inferred_edges with older mtime
        store.write_provenance(StageId.INFERRED_EDGES, {"stage_id": "inferred_edges"})
        import os
        old_time = time.time() - 3600
        ie_path = store.provenance_path(StageId.INFERRED_EDGES)
        os.utime(str(ie_path), (old_time, old_time))

        with _PatchProject(idx_dir):
            # With skip_mtime_cascade=True, stale mtime is ignored
            result = ResumeStrategy.detect_resume_point(
                "test-proj",
                [StageId.STRUCTURAL, StageId.INFERRED_EDGES],
                skip_mtime_cascade=True,
            )
        assert result == 2  # all complete

    def test_stale_mtime_with_existing_output_is_touched(self, idx_dir, store):
        """Stale manifest with existing output → touch manifest, treat as complete."""
        # Write structural with recent mtime
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        # Write inferred_edges with old mtime but valid output
        store.write_provenance(StageId.INFERRED_EDGES, {"stage_id": "inferred_edges"})
        (idx_dir / "trace_inferred_edges.jsonl").write_text('{"edge": "data"}\n' * 100)
        import os
        old_time = time.time() - 3600
        ie_path = store.provenance_path(StageId.INFERRED_EDGES)
        os.utime(str(ie_path), (old_time, old_time))

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj",
                [StageId.STRUCTURAL, StageId.INFERRED_EDGES],
                skip_mtime_cascade=False,  # cascade enabled
            )
        # Should treat as complete (output exists, manifest touched)
        assert result == 2

    def test_returns_0_when_project_resolution_fails(self):
        """If project can't be resolved, return 0 (start from scratch)."""
        with patch("codrag.services.project_helpers.require_project", side_effect=Exception("not found")):
            result = ResumeStrategy.detect_resume_point("bad-proj", FAST_SYNC_STAGES)
        assert result == 0

    def test_stub_downstream_does_not_prove_upstream(self, idx_dir, store):
        """A later stage with a STUB manifest (restored:true) must not be
        used as proof that an earlier stage completed. Pausing mid-enrichment
        + selfheal on resume used to chain stubs forward through
        group_reasoning and clustering, falsely skipping all three.
        """
        # Structural complete (real manifest + trace_nodes).
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')
        for s in [StageId.INFERRED_EDGES, StageId.CATALOGUE, StageId.VALIDATION, StageId.KNOWLEDGE]:
            store.write_provenance(s, {"stage_id": s.value})

        # ENRICHMENT has NO manifest — stage is supposed to run.
        # DEEPENING has a STUB manifest (selfheal wrote it from a shared
        # output file). It must NOT count as proof that ENRICHMENT
        # completed.
        store.write_provenance(StageId.DEEPENING, {
            "stage_id": "deepening",
            "restored": True,
            "source": "selfheal",
            "backup_type": "orphan_output",
        })

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
            )
        enrichment_idx = list(DEEP_ENRICHMENT_STAGES).index(StageId.ENRICHMENT)
        assert result == enrichment_idx

    def test_stub_with_dedicated_output_rejected_when_run_interrupted(
        self, idx_dir, store,
    ):
        """Stub manifest for enrichment + partial trace_epistemic.jsonl +
        pipeline_run_metadata showing interrupted run → treat as INCOMPLETE.

        Reproduces the Deep Reasoning pause bug: user paused at 70/1879,
        selfheal wrote a stub, resume used to accept the stub+output as
        COMPLETE and jump forward three stages.
        """
        # Fast sync stages complete so detect walks into deep enrichment.
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        # ENRICHMENT has a stub manifest from selfheal + a partial output.
        enrichment_output = STAGE_OUTPUT_FILE[StageId.ENRICHMENT]
        assert enrichment_output is not None
        (idx_dir / enrichment_output).write_bytes(b"x" * 4096)
        store.write_provenance(StageId.ENRICHMENT, {
            "stage_id": "enrichment",
            "restored": True,
            "source": "selfheal",
            "backup_type": "orphan_output",
        })

        # Interrupted run metadata — enrichment was pending when paused.
        (idx_dir / "pipeline_run_metadata.json").write_text(json.dumps({
            "format_version": "1.0",
            "run_id": "run-paused",
            "project_id": "test-proj",
            "group": "deep_enrichment",
            "status": "interrupted",
            "stages": [{"stage_id": "enrichment", "status": "pending"}],
        }))

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj", DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
            )
        enrichment_idx = list(DEEP_ENRICHMENT_STAGES).index(StageId.ENRICHMENT)
        assert result == enrichment_idx

    def test_stub_with_dedicated_output_accepted_when_run_completed(
        self, idx_dir, store,
    ):
        """When metadata shows the last run completed, stub + output is still
        valid evidence of completion (manifest was lost, not the work).
        """
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        (idx_dir / "trace_nodes.jsonl").write_text('{"kind":"file","file_path":"a.py"}\n')

        enrichment_output = STAGE_OUTPUT_FILE[StageId.ENRICHMENT]
        assert enrichment_output is not None
        (idx_dir / enrichment_output).write_bytes(b"x" * 4096)
        store.write_provenance(StageId.ENRICHMENT, {
            "stage_id": "enrichment",
            "restored": True,
            "source": "selfheal",
            "backup_type": "orphan_output",
        })

        (idx_dir / "pipeline_run_metadata.json").write_text(json.dumps({
            "format_version": "1.0",
            "run_id": "run-clean",
            "project_id": "test-proj",
            "group": "deep_enrichment",
            "status": "completed",
            "stages": [{"stage_id": "enrichment", "status": "completed"}],
        }))

        with _PatchProject(idx_dir):
            result = ResumeStrategy.detect_resume_point(
                "test-proj",
                [StageId.STRUCTURAL, StageId.ENRICHMENT],
                skip_mtime_cascade=True,
            )
        # Both structural + enrichment treated complete.
        assert result == 2


class TestShouldSkipStageFreshness:
    def test_skips_when_incremental(self):
        """Incremental runs always bypass freshness check."""
        should_skip, reason = ResumeStrategy.should_skip_stage_freshness(
            "test-proj", StageId.CATALOGUE, is_incremental=True,
        )
        assert should_skip is False  # bypass means "don't skip, run the stage"

    def test_structural_never_skipped(self):
        """Structural has no pipeline inputs, so freshness check returns False."""
        should_skip, reason = ResumeStrategy.should_skip_stage_freshness(
            "test-proj", StageId.STRUCTURAL, is_incremental=False,
        )
        assert should_skip is False


class TestCheckCoverageGap:
    def test_returns_needs_rebuild_true_on_failure(self):
        """If coverage check fails, default to needs_rebuild=True (safe direction)."""
        with patch("codrag.services.project_helpers.require_project", side_effect=Exception("fail")):
            result = ResumeStrategy.check_coverage_gap("bad-proj")
        assert result["needs_rebuild"] is True
        assert result["total"] == 0
