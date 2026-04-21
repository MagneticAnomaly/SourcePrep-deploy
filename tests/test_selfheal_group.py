"""Tests for RecoveryManager.selfheal_group() — backup resurrection for pipeline stages."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.manifest_store import ManifestStore
from prep.services.pipeline.recovery import (
    RecoveryManager,
    _RESET_BARRIER_FILENAME,
    _write_selfheal_stub,
    clear_reset_barrier,
    reset_barrier_active,
    write_reset_barrier,
)
from prep.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    FINALIZE_STAGES,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    StageId,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def idx_dir(tmp_path: Path) -> Path:
    """Create a minimal index directory structure."""
    idx = tmp_path / "idx"
    idx.mkdir()
    return idx


@pytest.fixture()
def golden_dir(idx_dir: Path) -> Path:
    """Create (and return) the golden checkpoint directory inside idx_dir."""
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    return golden


@pytest.fixture()
def _patch_resolve(idx_dir: Path):
    """Patch _resolve_idx_dir to return our tmp_path-based idx_dir."""
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx_dir,
    ):
        yield


@pytest.fixture()
def pfl() -> MagicMock:
    """A mock pipeline file logger."""
    mock = MagicMock()
    mock.selfheal = MagicMock()
    return mock


# ── Helpers ───────────────────────────────────────────────────────────


def _write_manifest(idx_dir: Path, stage: StageId, data: dict[str, Any] | None = None) -> None:
    """Write a manifest file for a stage."""
    mf = STAGE_MANIFEST_FILE[stage]
    content = data or {"stage_id": stage.value, "completed": True}
    (idx_dir / mf).write_text(json.dumps(content), encoding="utf-8")


def _write_output(idx_dir: Path, stage: StageId, size: int = 2048) -> None:
    """Write a fake output file for a stage."""
    of = STAGE_OUTPUT_FILE.get(stage)
    if of:
        (idx_dir / of).write_bytes(b"x" * size)


def _make_golden(idx_dir: Path, stage: StageId, size: int = 2048) -> None:
    """Create a golden checkpoint with data for the given stage."""
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    of = STAGE_OUTPUT_FILE.get(stage)
    if of:
        (golden / of).write_bytes(b"x" * size)


def _make_run_checkpoint(idx_dir: Path, run_id: str, stage: StageId, size: int = 2048) -> None:
    """Create a run checkpoint with data for the given stage."""
    cp = idx_dir / ".checkpoints" / run_id
    cp.mkdir(parents=True, exist_ok=True)
    of = STAGE_OUTPUT_FILE.get(stage)
    if of:
        (cp / of).write_bytes(b"x" * size)


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patch_resolve")
class TestSelfhealGroup:
    """Tests for RecoveryManager.selfheal_group()."""

    def test_missing_manifest_resurrected_from_golden(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """Stage with no manifest but golden has data -> resurrected."""
        stage = StageId.ENRICHMENT  # has output file trace_epistemic.jsonl
        _make_golden(idx_dir, stage, size=2048)

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[stage],
            pfl=pfl,
        )

        assert result["resurrected"] == 1
        assert result["still_missing"] == 0
        assert result["checked"] == 1

        # Verify the output file was copied
        of = STAGE_OUTPUT_FILE[stage]
        assert (idx_dir / of).exists()
        assert (idx_dir / of).stat().st_size == 2048

        # Verify a stub manifest was written
        store = ManifestStore(idx_dir)
        assert store.provenance_exists(stage)
        data = store.read_provenance(stage)
        assert data["restored"] is True
        assert data["source"] == "selfheal"
        assert data["backup_type"] == "golden"

    def test_existing_manifest_not_overwritten(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """All stages have manifests -> nothing changes."""
        stages = [StageId.ENRICHMENT, StageId.CLUSTERING]
        for s in stages:
            _write_manifest(idx_dir, s)

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=stages,
            pfl=pfl,
        )

        assert result["already_complete"] == 2
        assert result["resurrected"] == 0
        assert result["checked"] == 2

    def test_no_backup_leaves_stage_missing(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """Missing manifest, no backup -> still_missing."""
        stage = StageId.ENRICHMENT

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[stage],
            pfl=pfl,
        )

        assert result["still_missing"] == 1
        assert result["resurrected"] == 0
        assert result["checked"] == 1

    def test_disabled_via_env_var(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """PREP_SELFHEAL=0 -> disabled, nothing resurrected."""
        stage = StageId.ENRICHMENT
        _make_golden(idx_dir, stage)

        with patch.dict("os.environ", {"PREP_SELFHEAL": "0"}):
            result = RecoveryManager.selfheal_group(
                project_id="test-proj",
                stages=[stage],
                pfl=pfl,
            )

        assert result["disabled"] is True
        assert result["resurrected"] == 0

    def test_force_from_start_skips_selfheal(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """force_from_start=True -> skipped."""
        stage = StageId.ENRICHMENT
        _make_golden(idx_dir, stage)

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[stage],
            force_from_start=True,
            pfl=pfl,
        )

        assert result["skipped_force_rebuild"] is True
        assert result["resurrected"] == 0

    def test_run_checkpoint_used_when_no_golden(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """No golden, but run checkpoint has data -> resurrected."""
        stage = StageId.ENRICHMENT
        _make_run_checkpoint(idx_dir, "run-20260411-001", stage, size=2048)

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[stage],
            pfl=pfl,
        )

        assert result["resurrected"] == 1
        assert result["still_missing"] == 0

        # Verify the stub manifest records the run checkpoint source
        store = ManifestStore(idx_dir)
        data = store.read_provenance(stage)
        assert data["restored"] is True
        assert data["backup_type"] == "run_checkpoint"

    def test_small_backup_file_rejected(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """Backup file <1KB -> rejected, stage stays missing."""
        stage = StageId.ENRICHMENT
        _make_golden(idx_dir, stage, size=500)  # < 1KB

        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[stage],
            pfl=pfl,
        )

        assert result["still_missing"] == 1
        assert result["resurrected"] == 0


class TestSwissCheeseRecovery:
    """Integration test: swiss cheese pipeline state gets recovered."""

    def test_swiss_cheese_partial_resurrection(self, idx_dir: Path, golden_dir: Path) -> None:
        """Multiple missing stages across all 3 groups — golden has some, not all.

        Simulates the screenshot scenario:
        - Fast Sync: stages 0-3 complete, stage 4 (KNOWLEDGE) missing
        - Deep Enrichment: stages 0-2 complete, stages 3-4 missing (DEEPENING, DEEP_KNOWLEDGE)
        - Finalize: stage 0 (ATLAS) complete, stages 1-4 missing

        Golden checkpoint has data for KNOWLEDGE manifest and DEEPENING output.
        After selfheal: KNOWLEDGE and DEEPENING resurrected, others still missing.
        """
        # Fast Sync: stages 0-3 complete, stage 4 (KNOWLEDGE) missing
        for stage in FAST_SYNC_STAGES[:4]:
            _write_manifest(idx_dir, stage)

        # Deep Enrichment: stages 0-2 complete, stages 3-4 missing
        for stage in DEEP_ENRICHMENT_STAGES[:3]:
            _write_manifest(idx_dir, stage)

        # Finalize: stage 0 (ATLAS) complete, stages 1-4 missing
        _write_manifest(idx_dir, FINALIZE_STAGES[0])

        # Golden has KNOWLEDGE manifest (KNOWLEDGE has no output file, just manifest)
        _write_manifest(golden_dir, StageId.KNOWLEDGE)
        # Golden has DEEPENING output file (trace_epistemic.jsonl — shared with ENRICHMENT)
        deepening_output = STAGE_OUTPUT_FILE[StageId.DEEPENING]  # "trace_epistemic.jsonl"
        assert deepening_output is not None
        (golden_dir / deepening_output).write_bytes(b"x" * 2048)

        with patch(
            "prep.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            # Selfheal fast sync
            fs_result = RecoveryManager.selfheal_group("test", FAST_SYNC_STAGES)
            assert fs_result["already_complete"] == 4
            assert fs_result["resurrected"] == 1  # KNOWLEDGE from golden manifest
            assert fs_result["still_missing"] == 0

            # Selfheal deep enrichment
            de_result = RecoveryManager.selfheal_group("test", DEEP_ENRICHMENT_STAGES)
            assert de_result["already_complete"] == 3
            assert de_result["resurrected"] >= 1  # DEEPENING from golden output
            # DEEP_KNOWLEDGE has no output file and no golden manifest
            assert de_result["still_missing"] >= 1

            # Selfheal finalize
            fin_result = RecoveryManager.selfheal_group("test", FINALIZE_STAGES)
            assert fin_result["already_complete"] == 1  # ATLAS
            # No golden data for RULES, CONCEPTS, AUDIT, ANTIBODIES
            assert fin_result["still_missing"] == 4

    def test_all_stages_complete_is_noop(self, idx_dir: Path) -> None:
        """When all stages are complete, selfheal does nothing."""
        for stage in [*FAST_SYNC_STAGES, *DEEP_ENRICHMENT_STAGES, *FINALIZE_STAGES]:
            _write_manifest(idx_dir, stage)

        with patch(
            "prep.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            for stages in [FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES]:
                result = RecoveryManager.selfheal_group("test", stages)
                assert result["resurrected"] == 0
                assert result["still_missing"] == 0


class TestSharedOutputSafety:
    """Verify selfheal handles shared output files correctly."""

    @pytest.mark.usefixtures("_patch_resolve")
    def test_deepening_orphan_not_claimed_from_enrichment_output(
        self, idx_dir: Path,
    ) -> None:
        """DEEPENING shares trace_epistemic.jsonl with ENRICHMENT.

        If ENRICHMENT completed (output exists) but DEEPENING never ran,
        selfheal must NOT claim DEEPENING is complete based on the orphan
        output — that file belongs to ENRICHMENT, not DEEPENING.
        """
        # ENRICHMENT completed: manifest + output
        _write_manifest(idx_dir, StageId.ENRICHMENT)
        _write_output(idx_dir, StageId.ENRICHMENT, size=4096)

        # DEEPENING has no manifest (never ran)
        # trace_epistemic.jsonl exists on disk (from ENRICHMENT) but should NOT
        # be claimed as DEEPENING's orphan output.
        result = RecoveryManager.selfheal_group("test", [StageId.DEEPENING])

        # DEEPENING should be still_missing, NOT resurrected via orphan detection
        assert result["resurrected"] == 0
        assert result["still_missing"] == 1

    @pytest.mark.usefixtures("_patch_resolve")
    def test_deep_knowledge_orphan_not_claimed(self, idx_dir: Path) -> None:
        """DEEP_KNOWLEDGE shares output with KNOWLEDGE — same protection."""
        _write_manifest(idx_dir, StageId.KNOWLEDGE)

        result = RecoveryManager.selfheal_group("test", [StageId.DEEP_KNOWLEDGE])

        assert result["resurrected"] == 0
        assert result["still_missing"] == 1


class TestOrphanOutputDetection:
    """Verify orphan output detection (output exists, manifest missing)."""

    @pytest.mark.usefixtures("_patch_resolve")
    def test_orphan_output_gets_stub_manifest(self, idx_dir: Path) -> None:
        """Output file exists but no manifest — selfheal writes a stub."""
        # Write output file directly (no manifest)
        _write_output(idx_dir, StageId.CATALOGUE, size=4096)

        result = RecoveryManager.selfheal_group("test", [StageId.CATALOGUE])

        assert result["resurrected"] == 1
        assert result["still_missing"] == 0

        # Verify stub manifest was written
        store = ManifestStore(idx_dir)
        assert store.provenance_exists(StageId.CATALOGUE)
        data = store.read_provenance(StageId.CATALOGUE)
        assert data["restored"] is True
        assert data["source"] == "selfheal"
        assert data["backup_type"] == "orphan_output"

    @pytest.mark.usefixtures("_patch_resolve")
    def test_orphan_skipped_when_stage_pending_in_interrupted_run(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        """Partial output from a paused/interrupted run must NOT be resurrected.

        Reproduces the Deep Reasoning pause bug: the user paused mid-enrichment
        with 70/1879 records written. Selfheal's orphan_output branch used to
        claim the partial file as a completed stage, causing resume to skip
        the stage entirely on unpause.
        """
        stage = StageId.ENRICHMENT
        _write_output(idx_dir, stage, size=4096)  # partial output

        # Simulate pipeline_run_metadata.json for an interrupted run where
        # enrichment was pending when the user paused.
        (idx_dir / "pipeline_run_metadata.json").write_text(json.dumps({
            "format_version": "1.0",
            "run_id": "run-paused",
            "project_id": "test-proj",
            "group": "deep_enrichment",
            "status": "interrupted",
            "stages": [
                {"stage_id": "enrichment", "status": "pending"},
                {"stage_id": "group_reasoning", "status": "pending"},
            ],
        }))

        result = RecoveryManager.selfheal_group(
            project_id="test-proj", stages=[stage], pfl=pfl,
        )

        assert result["resurrected"] == 0
        assert result["still_missing"] == 1
        store = ManifestStore(idx_dir)
        assert not store.provenance_exists(stage)
        # Selfheal must record why it skipped, for post-mortem visibility.
        detail = result["details"][0]
        assert detail["status"] == "skipped_interrupted_run"

    @pytest.mark.usefixtures("_patch_resolve")
    def test_orphan_resurrected_when_last_run_completed(
        self, idx_dir: Path,
    ) -> None:
        """If the last run completed cleanly, an orphan output on disk really is
        orphan (manifest truly lost) and should be resurrected as before."""
        stage = StageId.CATALOGUE
        _write_output(idx_dir, stage, size=4096)

        (idx_dir / "pipeline_run_metadata.json").write_text(json.dumps({
            "format_version": "1.0",
            "run_id": "run-clean",
            "project_id": "test-proj",
            "group": "fast_sync",
            "status": "completed",
            "stages": [{"stage_id": "catalogue", "status": "completed"}],
        }))

        result = RecoveryManager.selfheal_group("test-proj", [stage])
        assert result["resurrected"] == 1


class TestManifestOnlyResurrection:
    """Verify stages with no output file get selfheal stubs (not raw copies)."""

    @pytest.mark.usefixtures("_patch_resolve")
    def test_manifest_only_stage_gets_stub_not_raw_copy(
        self, idx_dir: Path, golden_dir: Path,
    ) -> None:
        """For stages like KNOWLEDGE (output=None), backup manifest should
        produce a selfheal stub, not a raw copy of the backup manifest."""
        # Golden has a manifest for KNOWLEDGE with original data
        original_data = {"stage_id": "knowledge", "model": "ollama/nomic", "completed": True}
        _write_manifest(golden_dir, StageId.KNOWLEDGE, data=original_data)

        result = RecoveryManager.selfheal_group("test", [StageId.KNOWLEDGE])

        assert result["resurrected"] == 1

        # The manifest on disk should be a selfheal stub, NOT the original data
        store = ManifestStore(idx_dir)
        data = store.read_provenance(StageId.KNOWLEDGE)
        assert data["restored"] is True
        assert data["source"] == "selfheal"
        assert data["backup_type"] == "golden"
        # Original fields should NOT be present
        assert "model" not in data


@pytest.mark.usefixtures("_patch_resolve")
class TestResetBarrier:
    """Barrier set by Reset All / Rebuild blocks selfheal until finalize."""

    def test_barrier_blocks_orphan_output_resurrection(
        self, idx_dir: Path, pfl: MagicMock,
    ) -> None:
        stage = StageId.ENRICHMENT
        output_file = STAGE_OUTPUT_FILE[stage]
        assert output_file is not None
        (idx_dir / output_file).write_bytes(b"x" * 2048)
        write_reset_barrier("test-proj", reason="full_reset")

        result = RecoveryManager.selfheal_group(
            project_id="test-proj", stages=[stage], pfl=pfl,
        )

        assert result == {"skipped_reset_barrier": True, "resurrected": 0}
        store = ManifestStore(idx_dir)
        assert not store.provenance_exists(stage)

    def test_barrier_blocks_golden_resurrection(self, idx_dir: Path) -> None:
        stage = StageId.ENRICHMENT
        _make_golden(idx_dir, stage, size=2048)
        write_reset_barrier("test-proj", reason="rebuild")

        result = RecoveryManager.selfheal_group(
            project_id="test-proj", stages=[stage],
        )
        assert result.get("skipped_reset_barrier") is True

    def test_barrier_cleared_allows_selfheal(self, idx_dir: Path) -> None:
        stage = StageId.ENRICHMENT
        _make_golden(idx_dir, stage, size=2048)
        write_reset_barrier("test-proj", reason="full_reset")
        assert reset_barrier_active("test-proj") is True

        clear_reset_barrier("test-proj")
        assert reset_barrier_active("test-proj") is False

        result = RecoveryManager.selfheal_group(
            project_id="test-proj", stages=[stage],
        )
        assert result["resurrected"] == 1

    def test_barrier_write_creates_sentinel_file(self, idx_dir: Path) -> None:
        write_reset_barrier("test-proj", reason="full_reset")
        barrier = idx_dir / _RESET_BARRIER_FILENAME
        assert barrier.is_file()
        content = barrier.read_text()
        assert "full_reset" in content

    def test_clear_returns_false_when_no_barrier(self, idx_dir: Path) -> None:
        assert clear_reset_barrier("test-proj") is False

    def test_force_from_start_precedes_barrier(self, idx_dir: Path) -> None:
        """force_from_start check runs before barrier — both skip selfheal,
        but force_from_start returns its own sentinel."""
        write_reset_barrier("test-proj", reason="full_reset")
        result = RecoveryManager.selfheal_group(
            project_id="test-proj",
            stages=[StageId.ENRICHMENT],
            force_from_start=True,
        )
        assert result.get("skipped_force_rebuild") is True
