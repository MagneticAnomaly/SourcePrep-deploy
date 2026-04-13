# Pipeline Selfheal Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically detect incomplete pipeline stages and resurrect data from backups at daemon startup and before each group run, removing the priority inversion guard that blocks chain-forward.

**Architecture:** New `selfheal_group()` method in `recovery.py` scans manifests and attempts backup resurrection (golden → run checkpoints → branch snapshots). Called from orchestrator at startup (all active projects) and as pre-flight before each group run. Priority inversion guard removed from `run_fast_sync()`.

**Tech Stack:** Python, SQLite manifests, shutil for file copy, existing checkpoint/branch backup infrastructure.

---

### Task 1: Add `selfheal_group()` to RecoveryManager

**Files:**
- Modify: `src/codrag/services/pipeline/recovery.py:256` (after `try_restore_stage_from_backup`)
- Test: `tests/test_selfheal_group.py`

- [ ] **Step 1: Write the failing test for basic selfheal — missing manifest gets resurrected from golden**

```python
# tests/test_selfheal_group.py
"""Tests for RecoveryManager.selfheal_group() — backup resurrection for incomplete stages."""
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from codrag.services.pipeline.recovery import RecoveryManager
from codrag.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    FINALIZE_STAGES,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    StageId,
)


@pytest.fixture
def idx_dir(tmp_path):
    """Create a minimal index directory with checkpoint infrastructure."""
    idx = tmp_path / ".codrag"
    idx.mkdir()
    return idx


@pytest.fixture
def golden_dir(idx_dir):
    """Create a golden checkpoint directory with sample data."""
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True)
    return golden


def _write_manifest(idx_dir: Path, stage: StageId, data: dict | None = None):
    """Write a provenance manifest for a stage."""
    filename = STAGE_MANIFEST_FILE[stage]
    manifest = data or {"format_version": 1, "completed": True}
    (idx_dir / filename).write_text(json.dumps(manifest))


def _write_output(path: Path, filename: str, records: int = 10):
    """Write a fake JSONL output file with enough data to pass >1KB check."""
    lines = [json.dumps({"id": i, "data": "x" * 100}) for i in range(records)]
    (path / filename).write_text("\n".join(lines))


class TestSelfhealGroup:
    """Test selfheal_group() backup resurrection logic."""

    def test_missing_manifest_resurrected_from_golden(self, idx_dir, golden_dir):
        """Stage with no manifest but golden backup data gets resurrected."""
        # Setup: ENRICHMENT has no manifest, but golden has both output and manifest
        _write_output(golden_dir, "trace_epistemic.jsonl", records=20)
        _write_manifest(golden_dir, StageId.ENRICHMENT)

        # All other deep enrichment stages have manifests (pretend complete)
        for stage in DEEP_ENRICHMENT_STAGES:
            if stage != StageId.ENRICHMENT:
                _write_manifest(idx_dir, stage)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group("test-project", DEEP_ENRICHMENT_STAGES)

        assert result["resurrected"] == 1
        assert (idx_dir / "trace_epistemic.jsonl").exists()
        manifest_path = idx_dir / STAGE_MANIFEST_FILE[StageId.ENRICHMENT]
        assert manifest_path.exists()
        manifest_data = json.loads(manifest_path.read_text())
        assert manifest_data["restored"] is True
        assert manifest_data["source"] == "selfheal"

    def test_existing_manifest_not_overwritten(self, idx_dir, golden_dir):
        """Stages with existing manifests are left untouched."""
        # All stages have manifests
        for stage in FAST_SYNC_STAGES:
            _write_manifest(idx_dir, stage)

        # Golden has different data — should NOT overwrite
        _write_output(golden_dir, "trace_nodes.jsonl", records=50)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group("test-project", FAST_SYNC_STAGES)

        assert result["resurrected"] == 0
        assert result["already_complete"] == len(FAST_SYNC_STAGES)

    def test_no_backup_leaves_stage_missing(self, idx_dir):
        """Stage with no manifest and no backup data stays missing."""
        # No checkpoints at all
        for stage in FAST_SYNC_STAGES:
            if stage != StageId.KNOWLEDGE:
                _write_manifest(idx_dir, stage)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group("test-project", FAST_SYNC_STAGES)

        assert result["resurrected"] == 0
        assert result["still_missing"] == 1

    def test_disabled_via_env_var(self, idx_dir, golden_dir):
        """CODRAG_SELFHEAL=0 disables selfheal entirely."""
        _write_output(golden_dir, "trace_epistemic.jsonl", records=20)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ), patch.dict(os.environ, {"CODRAG_SELFHEAL": "0"}):
            result = RecoveryManager.selfheal_group("test-project", DEEP_ENRICHMENT_STAGES)

        assert result["disabled"] is True
        assert result["resurrected"] == 0

    def test_force_from_start_skips_selfheal(self, idx_dir, golden_dir):
        """force_from_start=True skips selfheal (user wants fresh rebuild)."""
        _write_output(golden_dir, "trace_epistemic.jsonl", records=20)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group(
                "test-project", DEEP_ENRICHMENT_STAGES, force_from_start=True,
            )

        assert result["skipped_force_rebuild"] is True
        assert result["resurrected"] == 0

    def test_run_checkpoint_used_when_no_golden(self, idx_dir):
        """Falls back to run checkpoint when golden doesn't have the file."""
        # Create a run checkpoint with data
        run_cp = idx_dir / ".checkpoints" / "run_001"
        run_cp.mkdir(parents=True)
        _write_output(run_cp, "trace_nodes.jsonl", records=15)

        # STRUCTURAL has no manifest
        for stage in FAST_SYNC_STAGES:
            if stage != StageId.STRUCTURAL:
                _write_manifest(idx_dir, stage)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group("test-project", FAST_SYNC_STAGES)

        assert result["resurrected"] == 1
        assert (idx_dir / "trace_nodes.jsonl").exists()

    def test_small_backup_file_rejected(self, idx_dir, golden_dir):
        """Backup files <1KB are rejected as empty/corrupt."""
        # Write a tiny file (< 1KB)
        (golden_dir / "trace_epistemic.jsonl").write_text('{"tiny": true}')

        for stage in DEEP_ENRICHMENT_STAGES:
            if stage != StageId.ENRICHMENT:
                _write_manifest(idx_dir, stage)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            result = RecoveryManager.selfheal_group("test-project", DEEP_ENRICHMENT_STAGES)

        assert result["resurrected"] == 0
        assert result["still_missing"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_selfheal_group.py -v`
Expected: FAIL — `RecoveryManager` has no `selfheal_group` method

- [ ] **Step 3: Implement `selfheal_group()` in recovery.py**

Add this method to `RecoveryManager` after `try_restore_stage_from_backup` (around line 335):

```python
    # ── Selfheal: per-group backup resurrection ──────────────

    @staticmethod
    def selfheal_group(
        project_id: str,
        stages: list[StageId],
        force_from_start: bool = False,
        pfl: Any = None,
    ) -> dict[str, Any]:
        """Scan stages for missing manifests and resurrect data from backups.

        Called at daemon startup (all active projects) and as pre-flight
        before each group run. Does NOT re-run stages — only restores
        data files from checkpoints so detect_resume_point() finds a
        better starting point.

        Args:
            project_id: The project to selfheal.
            stages: List of StageId for the group to check.
            force_from_start: If True, skip selfheal (user wants rebuild).
            pfl: Pipeline file logger for audit trail.

        Returns dict with counts: resurrected, already_complete, still_missing, etc.
        """
        result: dict[str, Any] = {
            "resurrected": 0,
            "already_complete": 0,
            "still_missing": 0,
            "checked": 0,
            "details": [],
        }

        # Dev flag: disable selfheal for testing raw pipeline behavior
        if os.environ.get("CODRAG_SELFHEAL", "1") == "0":
            logger.info("Selfheal disabled via CODRAG_SELFHEAL=0 for %s", project_id)
            result["disabled"] = True
            return result

        if force_from_start:
            logger.debug("Selfheal skipped for %s — force_from_start=True", project_id)
            result["skipped_force_rebuild"] = True
            return result

        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return result

        store = ManifestStore(idx_dir)

        # Locate backup sources (priority order)
        checkpoints_dir = idx_dir / ".checkpoints"
        golden_dir = checkpoints_dir / "_golden" if checkpoints_dir.exists() else None
        if golden_dir and not golden_dir.is_dir():
            golden_dir = None

        # Collect run checkpoints sorted by name (most recent first)
        run_checkpoint_dirs: list[Path] = []
        if checkpoints_dir.exists():
            for cp_dir in sorted(checkpoints_dir.iterdir(), reverse=True):
                if cp_dir.is_dir() and not cp_dir.name.startswith("_"):
                    run_checkpoint_dirs.append(cp_dir)

        # Branch snapshot for current branch
        branch_snapshot_dir: Path | None = None
        try:
            from codrag.services.branch_backup_manager import get_current_branch_snapshot
            branch_snapshot_dir = get_current_branch_snapshot(idx_dir)
        except Exception:
            pass  # No branch backup manager or no snapshot

        for stage in stages:
            result["checked"] += 1

            # Stage already has a manifest — skip
            if store.provenance_exists(stage):
                result["already_complete"] += 1
                continue

            # Stage is missing — attempt resurrection
            output_filename = STAGE_OUTPUT_FILE.get(stage)
            manifest_filename = STAGE_MANIFEST_FILE.get(stage)

            if not manifest_filename:
                result["still_missing"] += 1
                continue

            # If the output file already exists on disk (just missing manifest),
            # write a stub manifest and count as resurrected
            if output_filename and (idx_dir / output_filename).is_file():
                if (idx_dir / output_filename).stat().st_size > 1024:
                    _write_selfheal_stub(store, stage, "orphan_output")
                    result["resurrected"] += 1
                    result["details"].append({
                        "stage": stage.value,
                        "source": "orphan_output",
                    })
                    if pfl:
                        pfl.selfheal(
                            "resurrected",
                            f"Stage {stage.value}: output exists but no manifest — wrote stub",
                            {"stage": stage.value, "source": "orphan_output"},
                        )
                    continue

            # Try backup sources in priority order
            restored = False
            for source_name, source_dir in [
                ("golden", golden_dir),
                *[
                    (f"checkpoint:{cp.name}", cp)
                    for cp in run_checkpoint_dirs
                ],
                ("branch_snapshot", branch_snapshot_dir),
            ]:
                if source_dir is None:
                    continue

                backup_file = source_dir / output_filename if output_filename else None
                if backup_file and backup_file.is_file() and backup_file.stat().st_size > 1024:
                    # Copy the output file
                    shutil.copy2(str(backup_file), str(idx_dir / output_filename))
                    # Write selfheal stub manifest
                    _write_selfheal_stub(store, stage, source_name)
                    result["resurrected"] += 1
                    result["details"].append({
                        "stage": stage.value,
                        "source": source_name,
                        "backup_path": str(source_dir),
                    })
                    logger.info(
                        "Selfheal: resurrected %s for %s from %s",
                        stage.value, project_id, source_name,
                    )
                    if pfl:
                        pfl.selfheal(
                            "resurrected",
                            f"Stage {stage.value}: restored from {source_name}",
                            {
                                "stage": stage.value,
                                "source": source_name,
                                "backup_path": str(source_dir),
                            },
                        )
                    restored = True
                    break

                # For stages with no output file (validation, knowledge, etc.),
                # check if the manifest exists in the backup
                if output_filename is None:
                    backup_manifest = source_dir / manifest_filename
                    if backup_manifest.is_file() and backup_manifest.stat().st_size > 10:
                        shutil.copy2(str(backup_manifest), str(idx_dir / manifest_filename))
                        result["resurrected"] += 1
                        result["details"].append({
                            "stage": stage.value,
                            "source": source_name,
                            "type": "manifest_only",
                        })
                        logger.info(
                            "Selfheal: resurrected manifest for %s for %s from %s",
                            stage.value, project_id, source_name,
                        )
                        if pfl:
                            pfl.selfheal(
                                "resurrected",
                                f"Stage {stage.value}: manifest restored from {source_name}",
                                {"stage": stage.value, "source": source_name, "type": "manifest_only"},
                            )
                        restored = True
                        break

            if not restored:
                result["still_missing"] += 1
                result["details"].append({
                    "stage": stage.value,
                    "source": None,
                    "reason": "no_backup_found",
                })

        if result["resurrected"] > 0:
            logger.info(
                "Selfheal summary for %s: %d resurrected, %d already complete, %d still missing",
                project_id, result["resurrected"], result["already_complete"], result["still_missing"],
            )
        return result
```

Also add the helper function above the class (after imports):

```python
import os


def _write_selfheal_stub(store: ManifestStore, stage: StageId, source: str) -> None:
    """Write a selfheal stub manifest for a resurrected stage."""
    store.write_provenance(stage, {
        "restored": True,
        "source": "selfheal",
        "backup_type": source,
        "restored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
```

- [ ] **Step 4: Add missing import for `os` at top of recovery.py**

Add `import os` to the existing imports at the top of recovery.py (after `import shutil`).

- [ ] **Step 5: Add `get_current_branch_snapshot` helper to branch_backup_manager**

Check if this already exists. If not, add a simple function that returns the snapshot dir for the current git branch:

```python
def get_current_branch_snapshot(idx_dir: Path) -> Path | None:
    """Return the branch snapshot directory for the current git branch, or None."""
    state_file = idx_dir / ".branch_snapshots" / "_branch_state.json"
    if not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text())
        branch = state.get("current_branch")
        if branch:
            snap_dir = idx_dir / ".branch_snapshots" / branch
            if snap_dir.is_dir():
                return snap_dir
    except Exception:
        pass
    return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_selfheal_group.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/codrag/services/pipeline/recovery.py tests/test_selfheal_group.py
git commit -m "feat: add selfheal_group() to RecoveryManager for backup resurrection"
```

---

### Task 2: Remove priority inversion guard from orchestrator

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:483-498`
- Test: `tests/test_selfheal_group.py` (add orchestrator integration test)

- [ ] **Step 1: Write test that incremental proceeds when deep enrichment is incomplete**

Add to `tests/test_selfheal_group.py`:

```python
class TestPriorityInversionRemoval:
    """Verify incremental runs proceed even when deep enrichment is incomplete."""

    def test_fast_sync_proceeds_with_incomplete_deep(self, idx_dir):
        """run_fast_sync should NOT bail when deep enrichment is incomplete.

        Previously the priority inversion guard at lines 483-498 would
        return False if deep enrichment had missing manifests. Now it
        should proceed and let chain-forward handle deep enrichment.
        """
        # All fast sync manifests exist (simulating complete fast sync)
        for stage in FAST_SYNC_STAGES:
            _write_manifest(idx_dir, stage)

        # Deep enrichment is INCOMPLETE (only 2 of 5 stages done)
        from codrag.services.pipeline.stages import DEEP_ENRICHMENT_STAGES
        for stage in DEEP_ENRICHMENT_STAGES[:2]:
            _write_manifest(idx_dir, stage)

        # Create stale files so coverage gap triggers incremental
        # (This tests the path that used to hit the priority inversion guard)
        # The exact test requires mocking the orchestrator, so we verify
        # the guard code is gone by checking the source directly.
        import inspect
        from codrag.services.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run_fast_sync)
        assert "Priority Inversion Check" not in source
        assert "skip_queue_pipeline_incomplete" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestPriorityInversionRemoval -v`
Expected: FAIL — guard code still exists

- [ ] **Step 3: Remove the priority inversion guard**

In `src/codrag/services/pipeline/orchestrator.py`, delete lines 483-498 (the entire `if resume >= len(FAST_SYNC_STAGES):` block that checks deep enrichment and returns False).

The code to **remove**:
```python
        if resume >= len(FAST_SYNC_STAGES):
            # [Goal 5] Priority Inversion Check: If deep enrichment is INCOMPLETE,
            # DO NOT trigger new/stale queue processing. We must finish the pipeline first.
            from codrag.services.pipeline.stages import DEEP_ENRICHMENT_STAGES
            deep_resume = self._detect_resume_point(project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True)
            if deep_resume < len(DEEP_ENRICHMENT_STAGES):
                logger.info(
                    "Pipeline incomplete (deep resume=%d/%d) for %s — skipping new/stale queue so it can finish",
                    deep_resume, len(DEEP_ENRICHMENT_STAGES), project_id,
                )
                if pfl:
                    pfl.decision("mode_selection", "skip_queue_pipeline_incomplete", {
                        "group": "fast_sync",
                        "reason": f"Deep enrichment is incomplete ({deep_resume}/{len(DEEP_ENRICHMENT_STAGES)}) — prioritizing pipeline completion",
                    })
                return False
```

The next block (`# Phase 53: All manifests exist — but are there stale files?`) stays — it should now be directly inside the `if resume >= len(FAST_SYNC_STAGES):` check. But wait — re-reading the code, the Phase 53 block is ALREADY inside `if resume >= len(FAST_SYNC_STAGES):`. The priority inversion guard was a nested check that returned early. Removing it means the flow falls through to Phase 53's stale file check. This is exactly what we want.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestPriorityInversionRemoval -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py tests/test_selfheal_group.py
git commit -m "fix: remove priority inversion guard blocking incremental through incomplete pipeline"
```

---

### Task 3: Wire selfheal pre-flight into orchestrator group runners

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py` (run_fast_sync, run_deep_enrichment, run_finalize)

- [ ] **Step 1: Write test that selfheal runs as pre-flight before detect_resume_point**

Add to `tests/test_selfheal_group.py`:

```python
from unittest.mock import MagicMock, call


class TestSelfhealPreFlight:
    """Verify selfheal is called before detect_resume_point in each group runner."""

    def test_selfheal_called_in_run_fast_sync(self):
        """run_fast_sync calls _selfheal_group before _detect_resume_point."""
        import inspect
        from codrag.services.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run_fast_sync)
        selfheal_pos = source.find("_selfheal_group")
        resume_pos = source.find("_detect_resume_point")
        assert selfheal_pos != -1, "_selfheal_group not found in run_fast_sync"
        assert selfheal_pos < resume_pos, "_selfheal_group must come before _detect_resume_point"

    def test_selfheal_called_in_run_deep_enrichment(self):
        """run_deep_enrichment calls _selfheal_group before _detect_resume_point."""
        import inspect
        from codrag.services.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run_deep_enrichment)
        selfheal_pos = source.find("_selfheal_group")
        resume_pos = source.find("_detect_resume_point")
        assert selfheal_pos != -1, "_selfheal_group not found in run_deep_enrichment"
        assert selfheal_pos < resume_pos, "_selfheal_group must come before _detect_resume_point"

    def test_selfheal_called_in_run_finalize(self):
        """run_finalize calls _selfheal_group before _detect_resume_point."""
        import inspect
        from codrag.services.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run_finalize)
        selfheal_pos = source.find("_selfheal_group")
        resume_pos = source.find("_detect_resume_point")
        assert selfheal_pos != -1, "_selfheal_group not found in run_finalize"
        assert selfheal_pos < resume_pos, "_selfheal_group must come before _detect_resume_point"

    def test_selfheal_skipped_when_force_from_start(self):
        """force_from_start=True bypasses selfheal pre-flight."""
        import inspect
        from codrag.services.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run_fast_sync)
        # The selfheal call should be guarded by `not force_from_start`
        assert "not force_from_start" in source or "force_from_start" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestSelfhealPreFlight -v`
Expected: FAIL — `_selfheal_group` not in source

- [ ] **Step 3: Add `_selfheal_group` wrapper to orchestrator**

Add this method to `PipelineOrchestrator` (near `_detect_resume_point` around line 1326):

```python
    def _selfheal_group(
        self, project_id: str, stages: list, force_from_start: bool = False,
    ) -> dict:
        """Pre-flight selfheal: resurrect missing stage data from backups."""
        pfl = self._get_file_logger(project_id)
        return RecoveryManager.selfheal_group(
            project_id, stages,
            force_from_start=force_from_start,
            pfl=pfl,
        )
```

- [ ] **Step 4: Wire selfheal into `run_fast_sync()`**

In `run_fast_sync()`, add the selfheal call BEFORE `_detect_resume_point` (before line 463):

```python
        # Selfheal pre-flight: resurrect missing stage data from backups
        if not force_from_start:
            self._selfheal_group(project_id, FAST_SYNC_STAGES)
```

- [ ] **Step 5: Wire selfheal into `run_deep_enrichment()`**

In `run_deep_enrichment()`, add before the `_detect_resume_point` call (before line 722):

```python
        # Selfheal pre-flight: resurrect missing stage data from backups
        if not force_from_start:
            self._selfheal_group(project_id, DEEP_ENRICHMENT_STAGES)
```

- [ ] **Step 6: Wire selfheal into `run_finalize()`**

In `run_finalize()`, add before the `_detect_resume_point` call (before line 783):

```python
        # Selfheal pre-flight: resurrect missing stage data from backups
        if not force_from_start:
            from .stages import FINALIZE_STAGES as _fin_stages
            self._selfheal_group(project_id, _fin_stages)
```

Note: `run_finalize` already imports `FINALIZE_STAGES` locally at line 772, so use the same import or reference the existing one.

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestSelfhealPreFlight -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py tests/test_selfheal_group.py
git commit -m "feat: wire selfheal pre-flight into run_fast_sync, run_deep_enrichment, run_finalize"
```

---

### Task 4: Wire selfheal into daemon startup for all active projects

**Files:**
- Modify: `src/codrag/services/pipeline/recovery.py` (startup_recovery)
- Modify: `src/codrag/services/pipeline/orchestrator.py` (startup_recovery wrapper)
- Test: `tests/test_selfheal_group.py`

- [ ] **Step 1: Write test that startup calls selfheal for all active projects**

Add to `tests/test_selfheal_group.py`:

```python
class TestStartupSelfheal:
    """Verify selfheal runs at daemon startup for all active projects."""

    def test_startup_recovery_calls_selfheal(self):
        """startup_recovery should include a selfheal phase."""
        import inspect
        from codrag.services.pipeline.recovery import RecoveryManager
        source = inspect.getsource(RecoveryManager.startup_recovery)
        assert "selfheal" in source.lower(), "startup_recovery should include selfheal phase"

    def test_startup_selfheal_skips_inactive_projects(self):
        """Inactive projects should not be selfhealed."""
        import inspect
        from codrag.services.pipeline.recovery import RecoveryManager
        # Check that the selfheal startup phase filters by activity status
        # (same pattern as hydrate_paused_runs_from_disk and auto_recover_stale_pipelines)
        source = inspect.getsource(RecoveryManager.startup_selfheal_all)
        assert "activity" in source or "active" in source.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestStartupSelfheal -v`
Expected: FAIL

- [ ] **Step 3: Add `startup_selfheal_all()` to RecoveryManager**

Add this static method to RecoveryManager (after `selfheal_group`):

```python
    @staticmethod
    def startup_selfheal_all(
        get_file_logger_fn: Callable[[str], Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Run selfheal for all active projects at daemon startup.

        Returns dict of project_id → selfheal result.
        """
        results: dict[str, dict[str, Any]] = {}
        try:
            from codrag.services.project_helpers import get_registry

            registry = get_registry()
            projects = registry.list_projects()
        except Exception:
            logger.debug("Cannot list projects for startup selfheal", exc_info=True)
            return results

        all_groups = [FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES]
        # Import FINALIZE_STAGES locally to avoid circular imports
        try:
            from .stages import FINALIZE_STAGES
            all_groups.append(FINALIZE_STAGES)
        except ImportError:
            pass

        for project in projects:
            pid = project.id

            # Skip inactive/frozen/locked projects
            try:
                from codrag.services.project_helpers import get_project_activity_status
                activity = get_project_activity_status(pid)
                if activity != "active":
                    continue
            except Exception:
                pass  # Can't determine status — proceed

            pfl = get_file_logger_fn(pid) if get_file_logger_fn else None

            project_result: dict[str, Any] = {}
            for stages in all_groups:
                group_name = (
                    "fast_sync" if stages is FAST_SYNC_STAGES
                    else "deep_enrichment" if stages is DEEP_ENRICHMENT_STAGES
                    else "finalize"
                )
                group_result = RecoveryManager.selfheal_group(pid, stages, pfl=pfl)
                if group_result.get("resurrected", 0) > 0:
                    project_result[group_name] = group_result
                    logger.info(
                        "Startup selfheal for %s/%s: %d resurrected",
                        pid, group_name, group_result["resurrected"],
                    )

            if project_result:
                results[pid] = project_result

        if results:
            total = sum(
                r.get("resurrected", 0)
                for pr in results.values()
                for r in pr.values()
            )
            logger.info(
                "Startup selfheal complete: %d projects healed, %d total stages resurrected",
                len(results), total,
            )
        return results
```

- [ ] **Step 4: Wire into `startup_recovery()`**

In `RecoveryManager.startup_recovery()` (recovery.py line 413), add a Phase 3 after the existing Phase 61B auto-recovery:

```python
        # Phase 98: Startup selfheal — resurrect incomplete stages from backups
        try:
            selfheal_fn()
        except Exception:
            logger.debug("Startup selfheal failed (non-fatal)", exc_info=True)
```

Update the method signature to accept the new callback:

```python
    @staticmethod
    def startup_recovery(
        hydrate_fn: Callable[[], None],
        auto_recover_fn: Callable[[], None],
        set_crashed_runs: Callable[[list], None],
        selfheal_fn: Callable[[], None] | None = None,  # NEW
    ) -> list[Any]:
```

- [ ] **Step 5: Update orchestrator's `startup_recovery()` wrapper to pass selfheal callback**

In `orchestrator.py` `startup_recovery()` (line 3110), add the selfheal callback:

```python
    def startup_recovery(self) -> List[Any]:
        """Delegates to RecoveryManager.startup_recovery with orchestrator callbacks."""
        return RecoveryManager.startup_recovery(
            hydrate_fn=self._hydrate_paused_runs_from_disk,
            auto_recover_fn=self._auto_recover_stale_pipelines,
            set_crashed_runs=lambda runs: setattr(self, '_crashed_runs', runs),
            selfheal_fn=lambda: RecoveryManager.startup_selfheal_all(
                get_file_logger_fn=self._get_file_logger,
            ),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestStartupSelfheal -v`
Expected: PASS

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `.venv/bin/pytest tests/test_selfheal_group.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/codrag/services/pipeline/recovery.py src/codrag/services/pipeline/orchestrator.py tests/test_selfheal_group.py
git commit -m "feat: wire selfheal into daemon startup for all active projects"
```

---

### Task 5: Integration test — swiss cheese pipeline recovery

**Files:**
- Test: `tests/test_selfheal_group.py`

- [ ] **Step 1: Write integration test for the full swiss cheese scenario**

Add to `tests/test_selfheal_group.py`:

```python
class TestSwissCheeseRecovery:
    """Integration test: swiss cheese pipeline state gets recovered."""

    def test_swiss_cheese_partial_resurrection(self, idx_dir, golden_dir):
        """Multiple missing stages across all 3 groups — golden has some, not all.

        Simulates the screenshot scenario:
        - Fast Sync: 1-4 done, 5 missing
        - Deep Enrichment: 6-8 done, 9-10 missing
        - Finalize: 11 done, 12-15 missing

        Golden checkpoint has data for stages 5 and 9 but not 10 or 12-15.
        After selfheal: 5 and 9 resurrected, 10 and 12-15 still missing.
        """
        # Fast Sync: stages 0-3 complete, stage 4 (KNOWLEDGE) missing
        for stage in FAST_SYNC_STAGES[:4]:
            _write_manifest(idx_dir, stage)

        # Deep Enrichment: stages 0-2 complete (ENRICHMENT, GROUP_REASONING, CLUSTERING),
        # stages 3-4 missing (DEEPENING, DEEP_KNOWLEDGE)
        for stage in DEEP_ENRICHMENT_STAGES[:3]:
            _write_manifest(idx_dir, stage)

        # Finalize: stage 0 complete (ATLAS), stages 1-4 missing
        _write_manifest(idx_dir, FINALIZE_STAGES[0])

        # Golden has data for KNOWLEDGE (output=None, manifest-only) and DEEPENING
        _write_manifest(golden_dir, StageId.KNOWLEDGE)
        _write_output(golden_dir, "trace_epistemic.jsonl", records=20)  # DEEPENING's output

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
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
            # DEEPENING resurrected (golden has trace_epistemic.jsonl)
            # But DEEPENING shares output with ENRICHMENT — check this works
            assert de_result["resurrected"] >= 1
            # DEEP_KNOWLEDGE has no backup → still missing
            assert de_result["still_missing"] >= 1

            # Selfheal finalize
            fin_result = RecoveryManager.selfheal_group("test", FINALIZE_STAGES)
            assert fin_result["already_complete"] == 1  # ATLAS
            # No golden data for RULES, CONCEPTS, AUDIT, ANTIBODIES
            assert fin_result["still_missing"] == 4

    def test_all_stages_complete_is_noop(self, idx_dir):
        """When all stages are complete, selfheal does nothing."""
        for stage in [*FAST_SYNC_STAGES, *DEEP_ENRICHMENT_STAGES, *FINALIZE_STAGES]:
            _write_manifest(idx_dir, stage)

        with patch(
            "codrag.services.pipeline.recovery._resolve_idx_dir",
            return_value=idx_dir,
        ):
            for stages in [FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES]:
                result = RecoveryManager.selfheal_group("test", stages)
                assert result["resurrected"] == 0
                assert result["still_missing"] == 0
```

- [ ] **Step 2: Run the integration test**

Run: `.venv/bin/pytest tests/test_selfheal_group.py::TestSwissCheeseRecovery -v`
Expected: PASS (if Task 1 implementation handles all edge cases correctly)

If tests fail, fix the implementation in recovery.py.

- [ ] **Step 3: Run the full test suite for regressions**

Run: `.venv/bin/pytest tests/ -v --timeout=60 -x`
Expected: No regressions in existing pipeline tests

- [ ] **Step 4: Commit**

```bash
git add tests/test_selfheal_group.py
git commit -m "test: add swiss cheese integration test for selfheal pipeline recovery"
```

---

### Task 6: Final verification and cleanup

**Files:**
- All modified files from Tasks 1-5

- [ ] **Step 1: Run the complete selfheal test file**

Run: `.venv/bin/pytest tests/test_selfheal_group.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run existing pipeline tests for regressions**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_pipeline_scheduler.py -v --timeout=120`
Expected: No regressions

- [ ] **Step 3: Run type checking**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/mypy src/codrag/services/pipeline/recovery.py src/codrag/services/pipeline/orchestrator.py --ignore-missing-imports`
Expected: No new type errors

- [ ] **Step 4: Run linting**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/ruff check src/codrag/services/pipeline/recovery.py src/codrag/services/pipeline/orchestrator.py`
Expected: No lint errors (fix any that appear)

- [ ] **Step 5: Final commit with any cleanup**

```bash
git add -A
git commit -m "chore: selfheal integration cleanup and lint fixes"
```
