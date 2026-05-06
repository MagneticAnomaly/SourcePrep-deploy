# Phase 128 — Pipeline Recovery Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate spurious full-rebuild triggers from Phase 61B auto-recovery by making the pipeline journal authoritative for completion state, fix dead-code mtime touch logic, persist a build-success marker that survives ungraceful daemon termination, harden the resume.py downstream-stub race, surface migration orphans, and complete the residual `.runprep → .sourceprep` brand-split cleanup.

**Architecture:**
- The SQLite pipeline journal (`prep_pipeline_journal.db`) becomes the source of truth for "did this group complete?" — Phase 61B consults it via `journal.get_latest_run(project_id, group)` before falling back to mtime/marker heuristics. A journal entry with `status='completed'` post-dating the structural manifest mtime is conclusive proof of healthy state.
- A new `.pipeline_last_success` marker is written when finalize completes successfully, separate from the lifespan-shutdown marker. This survives kill -9 / USB eject / sleep, closing the case where the existing `.pipeline_clean_shutdown` marker is missing only because the daemon never received SIGTERM.
- The dead-code Phase 72 touch in `recovery.py:1432` (uses `CATALOGUE` as touch source, but `CATALOGUE` is always older than `STRUCTURAL`) is corrected to use `STRUCTURAL` so the existing self-heal path actually works as a safety net.
- `resume.py:478` "downstream-proves-upstream" stub writer learns to refuse writing recovery stubs while the journal shows an active run for that group — closes the F-67 race.
- `paths.py` migration logic gains an orphan-detection log warning when both legacy (`.runprep` / `.codrag`) and current (`.sourceprep`) directories coexist.
- License path readers (`feature_gate.py`, `lemon_squeezy.py`) prefer `~/.sourceprep/license.json` and fall back to `~/.runprep/license.json` for legacy installs; new license writes go to the new path.

**Tech Stack:** Python (`recovery.py`, `resume.py`, `server.py`, `paths.py`, `feature_gate.py`, `lemon_squeezy.py`, `pipeline_journal.py`), SQLite (existing journal schema), pytest with `asyncio_mode = "auto"` (TDD).

**Pre-flight notes:**
- The codrag daemon has no hot-reload; restart with `prep serve` after each commit that touches recovery code, before any live validation. (Memory: `feedback_restart_daemon_before_live_validation`.)
- All Python commands use the project venv: `.venv/bin/python` and `.venv/bin/pytest`. (Memory: `feedback_use_venv`.)
- All commits omit the `Co-Authored-By` trailer. (Memory: `feedback_no_coauthored_by`.)
- For cross-module fixes (Tasks 7-9 especially), at least one test must NOT mock the seam under test — exercise the real ManifestStore + Journal stack. (Memory: `feedback_test_full_import_chain`.)

---

## Phase 1 — Quick Wins (low-risk, high-leverage)

These three tasks are independent of each other and can ship in any order. They unblock the rest of the plan by either resolving the immediate symptom (Task 3) or by clearing peripheral noise that obscures recovery diagnostics (Tasks 1, 2).

### Task 1: Migration orphan warning at startup

**Files:**
- Modify: `src/prep/core/paths.py`
- Test: `tests/test_paths_migration_orphan_warning.py` (new)

- [ ] **Step 1: Read current migration logic to anchor the change**

Run: `.venv/bin/python -c "from prep.core.paths import migrate_project_index_dir; help(migrate_project_index_dir)" 2>&1 | head -20`

Expected: prints docstring referencing `.codrag → .runprep → .sourceprep` rename one-shot.

- [ ] **Step 2: Write the failing test**

Create `tests/test_paths_migration_orphan_warning.py`:

```python
"""Phase 128 Task 1: orphan legacy-dir warning when both old and new exist."""
import logging
from pathlib import Path
import pytest


def test_warns_when_runprep_and_sourceprep_coexist(tmp_path: Path, caplog):
    """If both .runprep/ and .sourceprep/ exist, log a warning."""
    from prep.core.paths import migrate_project_index_dir

    (tmp_path / ".runprep").mkdir()
    (tmp_path / ".sourceprep").mkdir()
    # Marker file inside legacy dir to make the warning actionable
    (tmp_path / ".runprep" / ".pipeline_clean_shutdown").write_text("123")

    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        migrate_project_index_dir(tmp_path)

    msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(".runprep" in m for m in msgs), f"no warning about .runprep orphan: {msgs}"
    assert any("orphan" in m.lower() for m in msgs)


def test_no_warning_when_only_sourceprep_exists(tmp_path: Path, caplog):
    """No warning if only the current dir is present."""
    from prep.core.paths import migrate_project_index_dir
    (tmp_path / ".sourceprep").mkdir()
    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        migrate_project_index_dir(tmp_path)
    msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert not any("orphan" in m.lower() for m in msgs)


def test_warning_lists_all_legacy_dirs(tmp_path: Path, caplog):
    """Both .codrag and .runprep orphans are surfaced in one message."""
    from prep.core.paths import migrate_project_index_dir
    (tmp_path / ".codrag").mkdir()
    (tmp_path / ".runprep").mkdir()
    (tmp_path / ".sourceprep").mkdir()
    with caplog.at_level(logging.WARNING, logger="prep.core.paths"):
        migrate_project_index_dir(tmp_path)
    msgs = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
    assert ".codrag" in msgs
    assert ".runprep" in msgs
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_paths_migration_orphan_warning.py -v`

Expected: FAIL — no warning is emitted because the migration function silently skips when target exists.

- [ ] **Step 4: Add the warning logic**

In `src/prep/core/paths.py`, locate `migrate_project_index_dir` (around line 60). After the existing rename branches finish, append:

```python
    # Phase 128: Warn about orphaned legacy directories. The migration
    # `if not target.exists(): rename(...)` branches above silently no-op
    # when the user has already created .sourceprep/ via wipe-and-rebuild.
    # That leaves .runprep/ or .codrag/ as silent orphans on disk, taking
    # space and confusing operators (and recovery code that grep-walks
    # the project root). Surface them once at startup with an actionable
    # hint — do not auto-delete: the user might have data in there they
    # haven't migrated yet.
    sourceprep_target = project_root / ".sourceprep"
    if sourceprep_target.exists():
        legacy_orphans = [
            name for name in (".codrag", ".runprep")
            if (project_root / name).exists()
        ]
        if legacy_orphans:
            logger.warning(
                "Legacy index directories found alongside .sourceprep/ at %s: %s. "
                "These are orphans from the brand-rename migration and can be "
                "safely deleted after verifying .sourceprep/ has all your data.",
                project_root,
                ", ".join(legacy_orphans),
            )
```

If the file does not already import `logging`/declare a `logger`, add at the top of the file:

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_paths_migration_orphan_warning.py -v`

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prep/core/paths.py tests/test_paths_migration_orphan_warning.py
git commit -m "fix(paths): warn on orphaned legacy index dirs after brand rename

Phase 128 Task 1: when .sourceprep/ exists alongside .runprep/ or .codrag/,
the runprep→sourceprep rename branch in migrate_project_index_dir silently
no-ops, leaving the legacy dir as a disk-eating, log-confusing orphan. Log
a one-time warning at startup so operators can clean up explicitly."
```

---

### Task 2: License path fallback (`.sourceprep/` first, `.runprep/` legacy)

**Files:**
- Modify: `src/prep/core/feature_gate.py:106`
- Modify: `src/prep/core/lemon_squeezy.py` (docstring + any license-write paths)
- Test: `tests/test_license_path_fallback.py` (new)

- [ ] **Step 1: Locate every reference to `~/.runprep/license.json`**

Run: `grep -n "\.runprep/license\|\.runprep.*license" src/prep/core/feature_gate.py src/prep/core/lemon_squeezy.py`

Expected: feature_gate.py:106 has `_LICENSE_PATH = Path.home() / ".runprep" / "license.json"`, plus comments/docstrings.

- [ ] **Step 2: Write the failing test**

Create `tests/test_license_path_fallback.py`:

```python
"""Phase 128 Task 2: license path resolves new dir first, legacy as fallback."""
from pathlib import Path
from unittest.mock import patch
import pytest


def test_resolves_sourceprep_when_present(tmp_path):
    """If ~/.sourceprep/license.json exists, prefer it over .runprep."""
    from prep.core.feature_gate import _resolve_license_path
    new_dir = tmp_path / ".sourceprep"
    new_dir.mkdir()
    (new_dir / "license.json").write_text("{}")
    legacy_dir = tmp_path / ".runprep"
    legacy_dir.mkdir()
    (legacy_dir / "license.json").write_text("{}")
    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        assert _resolve_license_path() == new_dir / "license.json"


def test_falls_back_to_runprep_when_sourceprep_missing(tmp_path):
    """If only .runprep/license.json exists, return that."""
    from prep.core.feature_gate import _resolve_license_path
    legacy_dir = tmp_path / ".runprep"
    legacy_dir.mkdir()
    (legacy_dir / "license.json").write_text("{}")
    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        assert _resolve_license_path() == legacy_dir / "license.json"


def test_returns_sourceprep_path_for_new_writes_when_neither_exists(tmp_path):
    """When no license file exists yet, point to the new path for writes."""
    from prep.core.feature_gate import _resolve_license_path
    with patch("prep.core.feature_gate.Path.home", return_value=tmp_path):
        result = _resolve_license_path()
        assert result.parent.name == ".sourceprep"
        assert result.name == "license.json"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_license_path_fallback.py -v`

Expected: FAIL — `_resolve_license_path` does not exist; current code uses module-level `_LICENSE_PATH` constant.

- [ ] **Step 4: Replace the constant with a resolver function**

In `src/prep/core/feature_gate.py`, replace line 106:

```python
# OLD:
_LICENSE_PATH = Path.home() / ".runprep" / "license.json"

# NEW:
_LICENSE_PATH_NEW = Path.home() / ".sourceprep" / "license.json"
_LICENSE_PATH_LEGACY = Path.home() / ".runprep" / "license.json"


def _resolve_license_path() -> Path:
    """Return the active license path.

    Phase 128: Reads prefer the new .sourceprep path; fall back to the
    legacy .runprep path so existing licensed installs keep working
    through the brand split. New writes go to the new path.
    """
    if _LICENSE_PATH_NEW.exists():
        return _LICENSE_PATH_NEW
    if _LICENSE_PATH_LEGACY.exists():
        return _LICENSE_PATH_LEGACY
    return _LICENSE_PATH_NEW
```

Then update every internal use of `_LICENSE_PATH` in this file to call `_resolve_license_path()` instead. Run `grep -n _LICENSE_PATH src/prep/core/feature_gate.py` to find all callsites.

- [ ] **Step 5: Update lemon_squeezy.py docstring and any write paths**

In `src/prep/core/lemon_squeezy.py`, search for `.runprep/license.json` (around line 14 in the docstring). Update to mention both: `~/.sourceprep/license.json` (new writes) and `~/.runprep/license.json` (legacy fallback). If the file actually writes a license file, update the write target to use `_LICENSE_PATH_NEW` from `feature_gate`:

```python
from prep.core.feature_gate import _LICENSE_PATH_NEW
# ...
_LICENSE_PATH_NEW.parent.mkdir(parents=True, exist_ok=True)
_LICENSE_PATH_NEW.write_text(license_payload)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_license_path_fallback.py -v`

Expected: 3 passed.

- [ ] **Step 7: Run full feature_gate test suite to ensure no regressions**

Run: `.venv/bin/pytest tests/ -k "feature_gate or license" -v`

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/feature_gate.py src/prep/core/lemon_squeezy.py tests/test_license_path_fallback.py
git commit -m "fix(license): prefer .sourceprep, fall back to .runprep for legacy installs

Phase 128 Task 2: feature_gate and lemon_squeezy still hardcoded the
pre-rename .runprep path. Switch to a resolver function that reads
.sourceprep first and falls back to .runprep so existing licensed
installs survive the brand split. New writes go to the new path."
```

---

### Task 3: Fix `sync_downstream_mtimes` touch source (`CATALOGUE` → `STRUCTURAL`)

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py:1432`
- Test: `tests/test_phase128_touch_source.py` (new)

- [ ] **Step 1: Confirm the bug from disk evidence**

Run: `grep -n "sync_downstream_mtimes" src/prep/services/pipeline/recovery.py`

Expected output: line 1432 calls `store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))`.

Verify that this is the only callsite of `sync_downstream_mtimes` from recovery.py. The bug: CATALOGUE's mtime is always older than STRUCTURAL because STRUCTURAL gets touched at the end of build sequences. Touching deep stages forward to CATALOGUE leaves them still older than STRUCTURAL, so the staleness re-check at lines 1434-1442 still trips and triggers a full rebuild.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase128_touch_source.py`:

```python
"""Phase 128 Task 3: Phase 72 touch-and-recheck must move deep stages
forward of structural, not just forward of catalogue."""
from pathlib import Path
import time
import pytest

from prep.services.pipeline.manifest_store import ManifestStore
from prep.services.pipeline.stages import StageId, DEEP_ENRICHMENT_STAGES


@pytest.fixture
def store_with_skewed_mtimes(tmp_path: Path) -> ManifestStore:
    """Build a manifest store where structural is the newest stage."""
    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()
    store = ManifestStore(idx_dir)
    base = time.time() - 3600  # 1 hour ago
    # Order matches a typical build: catalogue early, deep stages middle,
    # structural last (touched at finalize time).
    for offset, stage in enumerate([StageId.CATALOGUE, StageId.ENRICHMENT,
                                    StageId.GROUP_REASONING, StageId.CLUSTERING,
                                    StageId.DEEPENING, StageId.DEEP_KNOWLEDGE,
                                    StageId.STRUCTURAL]):
        store.write_provenance(stage, {"format_version": "2.0", "stage_id": stage.value})
        store.touch_provenance_mtime(stage, base + offset * 60)
    return store


def test_touch_to_structural_resolves_staleness(store_with_skewed_mtimes):
    """After touching deep stages to STRUCTURAL's mtime, none should remain
    older than structural — the post-touch staleness re-check should pass."""
    store = store_with_skewed_mtimes
    structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)

    store.sync_downstream_mtimes(StageId.STRUCTURAL, list(DEEP_ENRICHMENT_STAGES))

    for stage in DEEP_ENRICHMENT_STAGES:
        assert store.provenance_mtime(stage) >= structural_mtime, (
            f"Stage {stage.value} still older than structural after touch"
        )


def test_touch_to_catalogue_does_not_resolve(store_with_skewed_mtimes):
    """Sanity: the OLD behavior (touch to CATALOGUE) leaves deep stages
    older than structural — proving the bug exists."""
    store = store_with_skewed_mtimes
    structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)

    store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))

    deep_after = [store.provenance_mtime(s) for s in DEEP_ENRICHMENT_STAGES]
    assert all(m < structural_mtime for m in deep_after), (
        "Touching to CATALOGUE should leave deep stages older than STRUCTURAL"
    )
```

- [ ] **Step 3: Run tests to verify the first fails and the second passes**

Run: `.venv/bin/pytest tests/test_phase128_touch_source.py -v`

Expected: `test_touch_to_structural_resolves_staleness` may pass already (since the API supports it), but the existing recovery.py call uses CATALOGUE. Run the full recovery test:

Run: `.venv/bin/pytest tests/test_phase128_touch_source.py::test_touch_to_catalogue_does_not_resolve -v`

Expected: PASS — confirms the bug exists.

- [ ] **Step 4: Apply the one-line fix in `recovery.py`**

In `src/prep/services/pipeline/recovery.py`, locate line 1432:

```python
# OLD:
store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))

# NEW:
# Phase 128: STRUCTURAL is the comparison reference at line 1426 above
# (`if store.provenance_mtime(stage) < structural_mtime`). Touching deep
# stages forward to CATALOGUE's mtime leaves them still older than
# STRUCTURAL — the post-touch re-check always still trips, defeating the
# heal-in-place safety net. Touch to STRUCTURAL so the re-check can pass.
store.sync_downstream_mtimes(StageId.STRUCTURAL, list(DEEP_ENRICHMENT_STAGES))
```

- [ ] **Step 5: Re-run the test for the structural path**

Run: `.venv/bin/pytest tests/test_phase128_touch_source.py -v`

Expected: 2 passed.

- [ ] **Step 6: Run the existing recovery test suite for regressions**

Run: `.venv/bin/pytest tests/ -k "recovery or phase61 or phase72" -v`

Expected: all pass. If any fail, investigate before proceeding — Phase 72 has subtle interactions with finalize hydration.

- [ ] **Step 7: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_phase128_touch_source.py
git commit -m "fix(recovery): Phase 72 mtime-touch source CATALOGUE → STRUCTURAL

Phase 128 Task 3: recovery.py:1432 touched deep stages forward to
CATALOGUE's mtime, but the comparison at line 1426 is against STRUCTURAL.
Since STRUCTURAL is always the newest manifest after a successful build,
touching to CATALOGUE never resolved the staleness check — the heal-in-
place path was dead code. Touch to STRUCTURAL so the re-check passes."
```

---

## Phase 2 — Build-Success Marker (heal across ungraceful daemon termination)

The existing `.pipeline_clean_shutdown` marker is only written in the FastAPI lifespan shutdown handler — kill -9, USB eject, sleep, or any crash leaves a healthy build with no marker, vulnerable to spurious Phase 61B re-trigger on next start. This phase adds a separate "I successfully completed a pipeline run" marker that is written when finalize completes, surviving any subsequent ungraceful termination.

### Task 4: Add `write_build_success_marker` / `check_build_success_marker` to RecoveryManager

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py:60-61` (add filename constant)
- Modify: `src/prep/services/pipeline/recovery.py:235-380` (add new marker methods alongside clean shutdown methods)
- Test: `tests/test_phase128_build_success_marker.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase128_build_success_marker.py`:

```python
"""Phase 128 Task 4: build-success marker survives ungraceful daemon stop."""
from pathlib import Path
from unittest.mock import patch
import pytest


@pytest.fixture
def fake_idx(tmp_path: Path):
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    yield idx


def test_write_creates_marker(fake_idx):
    from prep.services.pipeline.recovery import RecoveryManager
    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=fake_idx):
        assert RecoveryManager.write_build_success_marker("proj-1")
    assert (fake_idx / ".pipeline_last_success").exists()


def test_check_returns_true_when_present(fake_idx):
    from prep.services.pipeline.recovery import RecoveryManager
    (fake_idx / ".pipeline_last_success").write_text("123.0")
    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=fake_idx):
        assert RecoveryManager.check_build_success_marker("proj-1") is True


def test_check_returns_false_when_absent(fake_idx):
    from prep.services.pipeline.recovery import RecoveryManager
    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=fake_idx):
        assert RecoveryManager.check_build_success_marker("proj-1") is False


def test_marker_is_independent_of_clean_shutdown_marker(fake_idx):
    """Build-success marker survives even if clean-shutdown marker is absent."""
    from prep.services.pipeline.recovery import RecoveryManager
    (fake_idx / ".pipeline_last_success").write_text("123.0")
    # clean shutdown marker NOT written
    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=fake_idx):
        assert RecoveryManager.check_build_success_marker("proj-1") is True
        assert RecoveryManager.check_clean_shutdown_marker("proj-1") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase128_build_success_marker.py -v`

Expected: FAIL — `write_build_success_marker` does not exist.

- [ ] **Step 3: Add the marker methods**

In `src/prep/services/pipeline/recovery.py`, near line 60 add a new constant alongside `_CLEAN_SHUTDOWN_FILENAME`:

```python
_CLEAN_SHUTDOWN_FILENAME = ".pipeline_clean_shutdown"
_BUILD_SUCCESS_FILENAME = ".pipeline_last_success"  # Phase 128
```

Then in the `RecoveryManager` class, after `read_and_clear_clean_shutdown_marker` (around line 380), add:

```python
    # ── Build-Success Markers (Phase 128) ──────────────────────
    #
    # Separate from clean-shutdown markers. The clean-shutdown marker
    # records "the daemon was gracefully stopped while no run was active"
    # — it can only be written from the lifespan shutdown handler on
    # SIGTERM. The build-success marker records "a complete pipeline run
    # finished successfully on disk" and is written at the end of
    # finalize (or after fast_sync if only fast_sync ran). It survives
    # any subsequent ungraceful daemon termination, closing the gap
    # where Phase 61B re-triggers a full rebuild after kill -9 / USB
    # eject / sleep.
    #
    # The marker is NOT cleared on read — it persists until invalidated
    # by an actual structural rebuild that produces newer outputs.
    # Phase 61B treats this marker as authoritative: if present, deep
    # enrichment data is healthy and recovery is skipped.

    @staticmethod
    def write_build_success_marker(project_id: str) -> bool:
        """Write a marker indicating the pipeline last completed successfully."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        try:
            marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
            marker_path.write_text(str(time.time()))
            return True
        except Exception:
            logger.debug(
                "Failed to write build success marker for %s",
                project_id, exc_info=True,
            )
            return False

    @staticmethod
    def check_build_success_marker(project_id: str) -> bool:
        """Check if a build-success marker exists (read-only)."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        return (idx_dir / _BUILD_SUCCESS_FILENAME).exists()

    @staticmethod
    def build_success_marker_mtime(project_id: str) -> Optional[float]:
        """Return the mtime of the build-success marker, or None if absent.

        Phase 61B uses this to compare against structural mtime: if the
        marker post-dates structural, the existing data is fresh.
        """
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return None
        marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
        if not marker_path.exists():
            return None
        try:
            return marker_path.stat().st_mtime
        except OSError:
            return None

    @staticmethod
    def invalidate_build_success_marker(project_id: str) -> bool:
        """Remove the marker (e.g. when a destructive reset wipes outputs)."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
        if not marker_path.exists():
            return False
        try:
            marker_path.unlink()
            return True
        except Exception:
            logger.debug(
                "Failed to invalidate build success marker for %s",
                project_id, exc_info=True,
            )
            return False
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_phase128_build_success_marker.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_phase128_build_success_marker.py
git commit -m "feat(recovery): build-success marker independent of clean-shutdown

Phase 128 Task 4: introduce .pipeline_last_success marker that records
a successful pipeline run on disk. Unlike the clean-shutdown marker
(only written on SIGTERM), this marker survives kill -9 / USB eject /
sleep / crash. Phase 61B will consult it to skip recovery for projects
with provably healthy data (next task)."
```

---

### Task 5: Write build-success marker on finalize completion + invalidate on destructive reset

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py` (locate finalize-completion path)
- Modify: `src/prep/services/pipeline/orchestrator.py` (locate destructive-reset path) and `src/prep/api/routers/trace_routes/shared.py` if reset lives there
- Test: `tests/test_phase128_marker_writeback.py` (new)

- [ ] **Step 1: Locate the finalize-completion code path**

Run: `grep -n "finalize.*complete\|all_complete.*finalize\|finalize_complete\|_finalize_completed\|run_finalize" src/prep/services/pipeline/orchestrator.py | head -10`

Identify the function that runs after the last finalize stage (`antibodies`) succeeds. This is where the marker write must happen — AFTER the manifest is durably on disk.

- [ ] **Step 2: Locate every destructive-reset path**

Run: `grep -rn "index_destroy_project\|full-reset\|full_reset\|invalidate.*deep\|wipe_deep" src/prep/api/routers/ src/prep/services/pipeline/ 2>/dev/null | grep -v __pycache__ | head -15`

Expected: at least the `/enrichment/full-reset` and `/finalize/full-reset` endpoints, plus the `index_destroy_project` function. Each must invalidate the marker.

- [ ] **Step 3: Write the failing test**

Create `tests/test_phase128_marker_writeback.py`:

```python
"""Phase 128 Task 5: marker is written on finalize success and invalidated
on destructive reset."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_marker_invalidated_on_full_reset(tmp_path: Path):
    """A scoped or full reset must remove the build-success marker so the
    next start doesn't see stale "healthy" state."""
    from prep.services.pipeline.recovery import RecoveryManager
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    (idx / ".pipeline_last_success").write_text("123.0")

    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=idx):
        assert RecoveryManager.invalidate_build_success_marker("proj-1") is True
        assert not (idx / ".pipeline_last_success").exists()


def test_marker_invalidate_idempotent(tmp_path: Path):
    """Invalidating a non-existent marker returns False, no error."""
    from prep.services.pipeline.recovery import RecoveryManager
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    with patch("prep.services.pipeline.recovery._resolve_idx_dir",
               return_value=idx):
        assert RecoveryManager.invalidate_build_success_marker("proj-1") is False
```

For the orchestrator-side write, add an integration-style test that uses a real ManifestStore + RecoveryManager (no mocks for the seam):

```python
def test_orchestrator_writes_marker_after_finalize(tmp_path: Path):
    """End of finalize group must write the build-success marker.

    Real components: project on disk, real ManifestStore, real
    RecoveryManager. Drive the orchestrator's "finalize completed"
    callback and assert the marker file is on disk.
    """
    # NOTE: see below for the exact function to call once Step 4 lands.
    pytest.skip("Wire after Step 4 introduces _on_finalize_completed callback")
```

- [ ] **Step 4: Add the marker write at finalize completion**

In `src/prep/services/pipeline/orchestrator.py`, find the function that handles the post-finalize success path (suggested name based on existing code: search for where `antibodies` completion is handled or where `all_complete` is logged for the `finalize` group).

Add at the success branch:

```python
# Phase 128: Persist build-success marker so Phase 61B knows this
# project's data is healthy across daemon restarts, including
# ungraceful ones (kill -9, USB eject, sleep). Written at the very
# end of finalize so any failure mid-pipeline leaves the marker
# either absent (first build) or stale-but-correct (last successful).
from prep.services.pipeline.recovery import RecoveryManager
RecoveryManager.write_build_success_marker(project_id)
logger.info("Phase 128: Wrote build-success marker for %s", project_id)
```

If the codebase has a single "after final stage in any successful run" hook for fast_sync-only runs (no finalize), also write the marker there — fast_sync alone is a complete pipeline for projects that don't run deep enrichment. Search: `grep -n "fast_sync.*complete\|fast_sync_complete\|knowledge.*complete" src/prep/services/pipeline/orchestrator.py`.

- [ ] **Step 5: Invalidate the marker on every destructive reset endpoint**

For each location identified in Step 2, add:

```python
# Phase 128: Reset wipes outputs — marker must reflect that the data
# is no longer "healthy" until a new run completes.
from prep.services.pipeline.recovery import RecoveryManager
RecoveryManager.invalidate_build_success_marker(project_id)
```

Place the invalidation BEFORE the actual file deletion — if the deletion fails partway, the marker is already gone, which is the safe direction.

- [ ] **Step 6: Unskip the orchestrator integration test**

Replace the `pytest.skip` line in `test_orchestrator_writes_marker_after_finalize` with the concrete drive-the-real-orchestrator code. Use `TestClient(app)` from FastAPI — see `tests/test_scoped_full_reset.py` for the pattern.

```python
def test_orchestrator_writes_marker_after_finalize(tmp_path: Path):
    from fastapi.testclient import TestClient
    from prep.server import app

    # Set up a tiny project, run finalize via API, assert marker exists.
    # See tests/test_scoped_full_reset.py for project setup pattern.
    # Key assertion after the API call:
    project_idx = tmp_path / ".sourceprep"
    assert (project_idx / ".pipeline_last_success").exists()
```

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/test_phase128_marker_writeback.py tests/test_phase128_build_success_marker.py -v`

Expected: all pass.

- [ ] **Step 8: Run reset regression suite**

Run: `.venv/bin/pytest tests/test_scoped_full_reset.py tests/ -k "reset" -v`

Expected: all pass, including the new invalidation behavior.

- [ ] **Step 9: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py src/prep/api/routers/trace_routes/shared.py tests/test_phase128_marker_writeback.py
git commit -m "feat(orchestrator): write build-success marker on finalize, invalidate on reset

Phase 128 Task 5: orchestrator now persists .pipeline_last_success at
the end of finalize and clears it on every destructive reset endpoint.
This is the durable signal Phase 61B (Task 6) will use to skip recovery
for projects with provably healthy data — independent of whether the
daemon was gracefully shut down."
```

---

### Task 6: Phase 61B respects build-success marker before mtime check

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py:1326-1349` (Phase 93 clean-shutdown gate; add Phase 128 build-success gate alongside)
- Test: `tests/test_phase128_phase61b_respects_marker.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase128_phase61b_respects_marker.py`:

```python
"""Phase 128 Task 6: Phase 61B skips recovery when build-success marker
post-dates the structural manifest, even without a clean-shutdown marker."""
from pathlib import Path
import time
import pytest

# Use a real ManifestStore + RecoveryManager + journal — do not mock the
# seam. (Memory: feedback_test_full_import_chain.)


@pytest.fixture
def project_with_completed_build(tmp_path):
    """Set up a fake project where a deep_enrichment run completed on
    disk (all manifests present, structural newest), build-success
    marker present, but NO clean-shutdown marker (simulates kill -9
    after a successful build)."""
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.stages import StageId, FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    store = ManifestStore(idx)
    base = time.time() - 3600
    for offset, stage in enumerate(list(FAST_SYNC_STAGES) + list(DEEP_ENRICHMENT_STAGES)):
        store.write_provenance(stage, {"format_version": "2.0", "stage_id": stage.value})
        store.touch_provenance_mtime(stage, base + offset * 60)
    # Structural touched LAST (the bug-causing pattern)
    store.touch_provenance_mtime(StageId.STRUCTURAL, time.time() - 60)
    # Build-success marker post-dates structural
    (idx / ".pipeline_last_success").write_text(str(time.time() - 30))
    # NO clean-shutdown marker — that's the point
    return idx


def test_phase61b_skips_when_build_success_marker_post_dates_structural(
    project_with_completed_build, monkeypatch, caplog
):
    """The mtime check at line 1426 would normally fire; the build-success
    marker should suppress it."""
    from prep.services.pipeline import recovery as rec
    monkeypatch.setattr(rec, "_resolve_idx_dir",
                        lambda pid: project_with_completed_build)
    # Force is_deep_auto_fn -> True so we don't short-circuit on auto check
    auto_recover_called = []
    def fake_run_deep(pid):
        auto_recover_called.append(pid)
        return True
    rec.RecoveryManager.auto_recover_stale_pipelines(
        project_ids=["proj-1"],
        is_deep_auto_fn=lambda pid: True,
        is_run_active_fn=lambda pid: False,
        clear_paused_runs_fn=lambda pid: [],
        run_deep_enrichment_fn=fake_run_deep,
    )
    assert auto_recover_called == [], (
        "Phase 61B triggered recovery despite build-success marker"
    )


def test_phase61b_still_runs_when_marker_predates_structural(
    project_with_completed_build, monkeypatch
):
    """Sanity: a stale build-success marker (e.g. from before a structural
    rebuild) does NOT suppress recovery — structural mtime > marker mtime."""
    from prep.services.pipeline import recovery as rec
    # Make marker OLDER than structural to invalidate it
    (project_with_completed_build / ".pipeline_last_success").write_text("1.0")
    import os
    os.utime(project_with_completed_build / ".pipeline_last_success", (1.0, 1.0))
    monkeypatch.setattr(rec, "_resolve_idx_dir",
                        lambda pid: project_with_completed_build)
    auto_recover_called = []
    rec.RecoveryManager.auto_recover_stale_pipelines(
        project_ids=["proj-1"],
        is_deep_auto_fn=lambda pid: True,
        is_run_active_fn=lambda pid: False,
        clear_paused_runs_fn=lambda pid: [],
        run_deep_enrichment_fn=lambda pid: auto_recover_called.append(pid) or True,
    )
    assert auto_recover_called == ["proj-1"], (
        "Stale marker (predates structural) should NOT suppress recovery"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase128_phase61b_respects_marker.py -v`

Expected: `test_phase61b_skips_when_build_success_marker_post_dates_structural` FAILS — auto_recover is invoked despite the marker.

- [ ] **Step 3: Add the build-success marker gate in Phase 61B**

In `src/prep/services/pipeline/recovery.py`, locate lines 1326-1347 (the Phase 93 clean-shutdown gate). Add a NEW gate immediately after it (before the `is_deep_auto_fn` check at line 1349):

```python
            # Phase 128: Build-success marker gate. Even without a
            # clean-shutdown marker (which only exists if the daemon got
            # SIGTERM), if a finalize has successfully completed and the
            # marker post-dates the structural manifest, the on-disk
            # data is healthy. This closes the kill -9 / USB eject / sleep
            # gap that left the user with spurious full rebuilds.
            try:
                marker_mtime = RecoveryManager.build_success_marker_mtime(pid)
                if marker_mtime is not None:
                    store_for_check = ManifestStore(idx_dir)
                    if store_for_check.provenance_exists(StageId.STRUCTURAL):
                        struct_mtime = store_for_check.provenance_mtime(StageId.STRUCTURAL)
                        if marker_mtime >= struct_mtime:
                            logger.info(
                                "Phase 128: Build-success marker for %s "
                                "post-dates structural — data healthy, "
                                "skipping deep enrichment auto-recovery",
                                pid,
                            )
                            if pfl:
                                pfl.selfheal(
                                    "auto_recover",
                                    "Skipped — build-success marker proves healthy data",
                                    {"project_id": pid,
                                     "marker_mtime": marker_mtime,
                                     "structural_mtime": struct_mtime},
                                )
                            continue
            except Exception:
                logger.debug(
                    "Phase 128: build-success marker check failed for %s",
                    pid, exc_info=True,
                )
                # Fall through to existing recovery logic
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_phase128_phase61b_respects_marker.py -v`

Expected: 2 passed.

- [ ] **Step 5: Run full Phase 61B regression suite**

Run: `.venv/bin/pytest tests/ -k "phase61 or phase93 or recovery" -v`

Expected: all pass. Pay attention to anything that asserts auto-recovery DID fire — those tests should still pass because they don't set up a build-success marker.

- [ ] **Step 6: Restart daemon and live-validate**

```bash
# Stop any running daemon
pkill -f "prep serve" || true
# Manually create the marker for the user's existing project to suppress
# the next spurious recovery (one-time fix for current state):
touch /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/.pipeline_last_success
# Restart
.venv/bin/prep serve &
sleep 5
# Confirm Phase 61B did NOT trigger:
grep "Phase 61B\|Phase 128" /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/logs/pipeline_*.log | tail -10
```

Expected: log shows "Phase 128: Build-success marker post-dates structural — skipping" or similar.

- [ ] **Step 7: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_phase128_phase61b_respects_marker.py
git commit -m "fix(recovery): Phase 61B respects build-success marker

Phase 128 Task 6: when .pipeline_last_success post-dates structural,
treat the data as healthy and skip deep enrichment auto-recovery.
Closes the kill -9 / USB eject / sleep gap where the existing clean-
shutdown marker (SIGTERM-only) is missing despite a successful build."
```

---

## Phase 3 — Journal as Authority

The pipeline journal (`prep_pipeline_journal.db`) records every run with `status` ∈ `{running, completed, failed, crashed, cancelled}`. It is already the authoritative source for "did this run finish?" but Phase 61B never consults it. This phase adds journal-based authority on top of the marker-based authority from Phase 2.

### Task 7: Add `journal.has_recent_completed_run(project_id, group, since_mtime)` helper

**Files:**
- Modify: `src/prep/services/pipeline_journal.py` (add new method around line 393, near `get_latest_run`)
- Test: `tests/test_phase128_journal_authority.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase128_journal_authority.py`:

```python
"""Phase 128 Task 7: journal helper for "is this group provably done?"."""
import time
import pytest


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))
    from prep.services.pipeline_journal import PipelineJournal
    j = PipelineJournal(db_path=tmp_path / "test_journal.db")
    yield j
    j.close()


def test_returns_true_when_completed_run_post_dates_reference(journal):
    journal.run_started("run-1", "proj-1", "deep_enrichment", 5)
    journal.run_completed("run-1")
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=time.time() - 3600
    ) is True


def test_returns_false_when_completed_run_pre_dates_reference(journal):
    journal.run_started("run-1", "proj-1", "deep_enrichment", 5)
    journal.run_completed("run-1")
    # Reference time in the future
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=time.time() + 3600
    ) is False


def test_returns_false_when_only_failed_runs(journal):
    journal.run_started("run-1", "proj-1", "deep_enrichment", 5)
    journal.run_failed("run-1", "synthetic error")
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=0.0
    ) is False


def test_returns_false_when_no_runs_for_project(journal):
    assert journal.has_recent_completed_run(
        "proj-2", "deep_enrichment", since_mtime=0.0
    ) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase128_journal_authority.py -v`

Expected: FAIL — `has_recent_completed_run` does not exist.

- [ ] **Step 3: Implement the helper**

In `src/prep/services/pipeline_journal.py`, after `get_latest_run` (around line 405), add:

```python
    def has_recent_completed_run(
        self,
        project_id: str,
        group: str,
        since_mtime: float,
    ) -> bool:
        """Phase 128: Authoritative "is this group provably done?" check.

        Returns True iff there exists at least one run for this
        (project_id, group) with status='completed' and finished_at
        >= since_mtime. Used by Phase 61B as the primary gate before
        falling back to mtime/marker heuristics.
        """
        with self._connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM pipeline_runs
                   WHERE project_id = ?
                     AND group_name = ?
                     AND status = 'completed'
                     AND finished_at >= ?
                   LIMIT 1""",
                (project_id, group, since_mtime),
            ).fetchone()
            return row is not None
```

If the journal stores `finished_at` in a different format (ISO string vs. epoch float), inspect the schema with: `.venv/bin/python -c "from prep.services.pipeline_journal import journal; print(journal.get_latest_run('any', 'deep_enrichment'))"` and adapt the comparison accordingly. The `JournalEntry` dataclass at line ~75 will reveal the type.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_phase128_journal_authority.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline_journal.py tests/test_phase128_journal_authority.py
git commit -m "feat(journal): has_recent_completed_run helper for Phase 61B authority

Phase 128 Task 7: add journal helper that answers \"is this group's
last successful run more recent than this reference time?\". This is
the canonical signal Phase 61B (Task 8) will use as primary authority,
demoting mtime ordering to advisory."
```

---

### Task 8: Phase 61B consults journal before mtime check

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py` (after the build-success marker gate from Task 6, before the existing mtime check at line 1359)
- Test: `tests/test_phase128_phase61b_journal_authority.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase128_phase61b_journal_authority.py`:

```python
"""Phase 128 Task 8: Phase 61B trusts journal-recorded completion."""
import time
import pytest


@pytest.fixture
def healthy_project_with_journal(tmp_path, monkeypatch):
    """Project on disk + completed run recorded in journal, but NO
    clean-shutdown marker AND NO build-success marker (simulates the
    journal as the only signal)."""
    from prep.services.pipeline import recovery as rec
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.stages import StageId, DEEP_ENRICHMENT_STAGES
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    store = ManifestStore(idx)
    base = time.time() - 3600
    for offset, stage in enumerate(list(DEEP_ENRICHMENT_STAGES) + [StageId.STRUCTURAL]):
        store.write_provenance(stage, {"format_version": "2.0", "stage_id": stage.value})
        store.touch_provenance_mtime(stage, base + offset * 60)
    # Structural is newest (the bug-causing ordering)

    # Record completed run in journal
    from prep.services.pipeline_journal import journal as global_journal
    run_id = "run-test-128"
    global_journal.run_started(run_id, "proj-1", "deep_enrichment", 5)
    global_journal.run_completed(run_id)

    monkeypatch.setattr(rec, "_resolve_idx_dir", lambda pid: idx)
    return idx


def test_journal_completion_skips_recovery(healthy_project_with_journal):
    from prep.services.pipeline.recovery import RecoveryManager
    triggered = []
    RecoveryManager.auto_recover_stale_pipelines(
        project_ids=["proj-1"],
        is_deep_auto_fn=lambda pid: True,
        is_run_active_fn=lambda pid: False,
        clear_paused_runs_fn=lambda pid: [],
        run_deep_enrichment_fn=lambda pid: triggered.append(pid) or True,
    )
    assert triggered == [], "Journal-recorded completion should suppress recovery"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase128_phase61b_journal_authority.py -v`

Expected: FAIL — Phase 61B doesn't consult the journal.

- [ ] **Step 3: Add the journal-authority gate in Phase 61B**

In `src/prep/services/pipeline/recovery.py`, after the Phase 128 build-success marker gate from Task 6 (and after the Phase 93 clean-shutdown gate at line 1347), add:

```python
            # Phase 128: Journal-authority gate. The pipeline_journal records
            # every run's status. If a 'completed' deep_enrichment run for
            # this project post-dates the structural manifest mtime, the
            # data is provably healthy by the journal's authority — skip
            # recovery. This handles the case where neither marker survived
            # but the journal (SQLite, atomic writes) did.
            try:
                from prep.services.pipeline_journal import journal as _journal
                store_for_check = ManifestStore(idx_dir)
                if store_for_check.provenance_exists(StageId.STRUCTURAL):
                    struct_mtime = store_for_check.provenance_mtime(StageId.STRUCTURAL)
                    if _journal.has_recent_completed_run(
                        pid, "deep_enrichment", since_mtime=struct_mtime
                    ):
                        logger.info(
                            "Phase 128: Journal records completed deep_enrichment "
                            "run for %s post-dating structural — data healthy, "
                            "skipping recovery",
                            pid,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                "Skipped — journal proves recent completion",
                                {"project_id": pid,
                                 "structural_mtime": struct_mtime},
                            )
                        continue
            except Exception:
                logger.debug(
                    "Phase 128: journal authority check failed for %s",
                    pid, exc_info=True,
                )
                # Fall through to existing recovery logic
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_phase128_phase61b_journal_authority.py -v`

Expected: 1 passed.

- [ ] **Step 5: Run full recovery test suite**

Run: `.venv/bin/pytest tests/ -k "phase61 or phase93 or phase128 or recovery" -v`

Expected: all pass.

- [ ] **Step 6: Live validation**

```bash
pkill -f "prep serve" || true
# Confirm the user's project has a completed run in the journal:
.venv/bin/python -c "
from prep.services.pipeline_journal import journal
runs = journal.get_project_runs('f1636374-abc6-410d-99ee-822120379e79', limit=10)
for r in runs:
    print(r.run_id, r.group_name, r.status, r.finished_at)
"
.venv/bin/prep serve &
sleep 5
grep "Phase 128.*[Jj]ournal\|Phase 61B" /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/logs/pipeline_*.log | tail -10
```

Expected: at least one journal entry with status='completed' for `deep_enrichment`. On daemon start, log line "Phase 128: Journal records completed deep_enrichment run ... skipping recovery".

- [ ] **Step 7: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_phase128_phase61b_journal_authority.py
git commit -m "fix(recovery): Phase 61B trusts journal as completion authority

Phase 128 Task 8: Phase 61B now consults pipeline_journal.has_recent_
completed_run() before the mtime check. A completed journal entry that
post-dates the structural manifest is conclusive proof of healthy data
— even when both markers are absent. This eliminates the entire class
of \"naive mtime ordering triggers spurious rebuilds\" bugs."
```

---

## Phase 4 — Resume Race Hardening

### Task 9: `resume.py` downstream-stub writer respects active runs

**Files:**
- Modify: `src/prep/services/pipeline/resume.py:478-505`
- Test: `tests/test_phase128_resume_no_stub_during_active_run.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase128_resume_no_stub_during_active_run.py`:

```python
"""Phase 128 Task 9: resume.py must not write a recovery stub while a
journal entry says the stage is currently running."""
import time
import pytest


def test_no_stub_written_while_journal_active(tmp_path, monkeypatch):
    """When a deep_enrichment run is active in the journal and the
    orchestrator has just F-67-deleted a stage manifest before starting
    its worker, the parallel resume scan must NOT write a recovery
    stub claiming the stage is done — that creates the race observed
    on 2026-05-05 (group_reasoning_manifest written at 21:22:35 with
    recovered=true while the worker was mid-execution)."""
    from prep.services.pipeline import resume as resume_mod
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.stages import StageId
    from prep.services.pipeline_journal import journal

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    monkeypatch.setenv("PREP_DATA_DIR", str(tmp_path))

    # Set up: clustering manifest exists (downstream "complete"), group_
    # reasoning manifest is gone (just F-67-deleted). Journal says
    # deep_enrichment is RUNNING for this project.
    store = ManifestStore(idx)
    store.write_provenance(StageId.CLUSTERING, {"format_version": "2.0",
                                                 "stage_id": "clustering"})
    journal.run_started("run-active", "proj-1", "deep_enrichment", 5)

    # Drive the resume strategy
    resume_mod.ResumeStrategy.resolve_resume_point(
        project_id="proj-1",
        idx_dir=idx,
        stages=[StageId.GROUP_REASONING, StageId.CLUSTERING],
        skip_mtime_cascade=False,
    )

    # Assert: no stub manifest was written for group_reasoning
    gr_manifest = idx / "group_reasoning_manifest.json"
    if gr_manifest.exists():
        import json
        data = json.loads(gr_manifest.read_text())
        assert not data.get("recovered"), (
            f"Stub was written despite active journal run: {data}"
        )

    # Cleanup
    journal.run_completed("run-active")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase128_resume_no_stub_during_active_run.py -v`

Expected: FAIL — current code writes a stub regardless of active-run status.

- [ ] **Step 3: Add the active-run guard in resume.py**

In `src/prep/services/pipeline/resume.py`, around line 478 (the "downstream-proves-upstream" branch), add an early bail BEFORE `store.write_provenance`:

```python
                if downstream_complete_stage is not None:
                    # Phase 128: refuse to write a recovery stub if the
                    # journal says this group is currently running. The
                    # orchestrator just F-67-deleted the manifest at
                    # stage start; writing a stub here races the worker
                    # and produces contradictory disk state where the
                    # manifest claims "recovered, finished_at=NOW" while
                    # the actual worker is still mid-execution.
                    try:
                        from prep.services.pipeline_journal import journal
                        # Determine which group this stage belongs to
                        # (deep_enrichment / fast_sync / finalize) — see
                        # stages.py STAGE_GROUP mapping
                        from prep.services.pipeline.stages import STAGE_GROUP
                        group = STAGE_GROUP.get(stage)
                        if group:
                            active = journal.get_active_run(project_id, group.value)
                            if active is not None:
                                logger.info(
                                    "Phase 128: skipping downstream-proves-"
                                    "upstream stub for %s — journal shows "
                                    "active %s run %s",
                                    stage.value, group.value, active.run_id,
                                )
                                stage_decisions.append({
                                    "stage": stage.value,
                                    "decision": "ACTIVE_RUN_DEFER",
                                    "reason": (
                                        f"Active {group.value} run in journal — "
                                        "deferring recovery stub to avoid race"
                                    ),
                                })
                                continue
                    except Exception:
                        logger.debug(
                            "Phase 128: active-run check failed for %s",
                            stage.value, exc_info=True,
                        )

                    try:
                        store.write_provenance(stage, {
                            "format_version": "2.0",
                            # ... existing stub fields ...
                        })
                        # ... existing logging ...
```

If `STAGE_GROUP` does not exist as a direct mapping, derive it: search `src/prep/services/pipeline/stages.py` for `FAST_SYNC_STAGES`, `DEEP_ENRICHMENT_STAGES`, `FINALIZE_STAGES` and write a small helper:

```python
# Top of resume.py
from prep.services.pipeline.stages import (
    StageId, FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES,
)

def _group_of(stage: StageId) -> Optional[str]:
    if stage in FAST_SYNC_STAGES: return "fast_sync"
    if stage in DEEP_ENRICHMENT_STAGES: return "deep_enrichment"
    if stage in FINALIZE_STAGES: return "finalize"
    return None
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_phase128_resume_no_stub_during_active_run.py -v`

Expected: PASS.

- [ ] **Step 5: Run resume.py regression suite**

Run: `.venv/bin/pytest tests/ -k "resume or selfheal or downstream" -v`

Expected: all pass. The other downstream-proves-upstream cases (no active run, journal corrupt, etc.) should still write stubs as before.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/resume.py tests/test_phase128_resume_no_stub_during_active_run.py
git commit -m "fix(resume): no recovery stub while journal shows active run

Phase 128 Task 9: resume.py:478 downstream-proves-upstream branch now
checks pipeline_journal.get_active_run() before writing a stub manifest.
Closes the F-67 race observed on 2026-05-05 where the orchestrator
deleted group_reasoning_manifest.json at stage start and a parallel
resume scan immediately wrote a recovery stub claiming the stage
finished, while the actual worker was still computing."
```

---

## Phase 5 — Documentation & memory hygiene

### Task 10: Update memory observations + cross-reference

**Files:**
- Run `prep_observe save` for the resolved bug
- Update `docs/Phase128_PipelineRecoveryHardening/README.md` (new, brief)

- [ ] **Step 1: Save resolution observation**

Run from this session (or via the prep MCP tool in a fresh session):

```python
prep_observe(
    action="save",
    category="decision",
    file_path="src/prep/services/pipeline/recovery.py",
    content=(
        "Phase 128 closed Phase 61B spurious-rebuild bug class. "
        "Three-layer authority: (1) journal.has_recent_completed_run() "
        "primary, (2) .pipeline_last_success marker secondary, (3) "
        ".pipeline_clean_shutdown marker tertiary. Mtime ordering is "
        "now advisory only. resume.py:478 stub writer respects "
        "journal active-run state. sync_downstream_mtimes touch "
        "source corrected from CATALOGUE to STRUCTURAL."
    ),
)
```

- [ ] **Step 2: Write a brief README for the phase dir**

Create `docs/Phase128_PipelineRecoveryHardening/README.md`:

```markdown
# Phase 128 — Pipeline Recovery Hardening

> **Scope:** Eliminate spurious full-rebuild triggers from Phase 61B
> auto-recovery. Make the pipeline journal authoritative, add a build-
> success marker that survives ungraceful daemon termination, fix the
> dead-code Phase 72 mtime touch, and harden the resume.py downstream-
> stub race.
>
> **Prior art:** Phase 61B (auto-recovery for stale pipelines), Phase 72
> (touch-and-recheck mtime self-heal), Phase 93 (clean-shutdown marker
> gating), F-66/67/75 (recovery gaps), F-78 (full-reset gaps).
>
> **Status:** Plan written 2026-05-05. Implementation pending.
> **Trigger incident:** 2026-05-05 21:22 — daemon restart after
> ungraceful stop triggered full deep_enrichment re-run on user's
> project despite a clean May 3 build.

See `IMPLEMENTATION_PLAN.md` for the bite-sized task breakdown.
```

- [ ] **Step 3: Commit**

```bash
git add docs/Phase128_PipelineRecoveryHardening/
git commit -m "docs(phase128): scaffold Pipeline Recovery Hardening phase"
```

---

## Self-Review (Reverse Engineering the Plan)

This walks back through the plan from the desired end state to verify each link in the chain is present.

**End state:** Phase 61B never triggers a full rebuild on a project with healthy on-disk data, regardless of how the daemon last terminated.

Reverse trace:
1. **Last gate that runs:** existing mtime check at `recovery.py:1426`. → For this to be reached, the new gates above must NOT have skipped. ✓ Tasks 6 and 8 add those gates with explicit "continue" exits.
2. **Task 8 gate (journal authority):** requires `journal.has_recent_completed_run`. ✓ Task 7 defines it. Requires `STAGE_GROUP` knowledge → handled in Task 8 via direct `journal.get_active_run` call.
3. **Task 6 gate (build-success marker):** requires `RecoveryManager.build_success_marker_mtime`. ✓ Task 4 defines it. Requires the marker to exist on disk → Task 5 writes it on finalize success.
4. **Task 5 marker write:** requires `RecoveryManager.write_build_success_marker`. ✓ Task 4. Requires invalidation on reset → Task 5 Step 5 covers all reset endpoints.
5. **Task 3 (mtime touch fix):** independent — produces correct heal-in-place behavior even if Tasks 6 and 8 both fail.
6. **Task 9 (resume.py race):** independent of the gating chain — fixes the on-disk-state-during-recovery confusion. Requires `journal.get_active_run` (existing).
7. **Tasks 1, 2:** independent cleanup — surface orphans + license path. No dependency.

**Spec coverage check:**
- ✓ #1 Journal as authority → Tasks 7, 8
- ✓ #2 sync_downstream_mtimes source bug → Task 3
- ✓ #3 Build-success marker → Tasks 4, 5, 6
- ✓ #4 Migration orphan warning → Task 1
- ✓ #5 License path fallback → Task 2
- ✓ #6 F-67 + resume.py:485 race → Task 9

**Type/signature consistency check:**
- `RecoveryManager.write_build_success_marker(project_id: str) -> bool` — used in Task 5, defined in Task 4. ✓
- `RecoveryManager.build_success_marker_mtime(project_id: str) -> Optional[float]` — used in Task 6, defined in Task 4. ✓
- `RecoveryManager.invalidate_build_success_marker(project_id: str) -> bool` — used in Task 5, defined in Task 4. ✓
- `journal.has_recent_completed_run(project_id, group, since_mtime) -> bool` — used in Task 8, defined in Task 7. ✓
- `_resolve_license_path() -> Path` — used in Task 2 callsite update, defined in Task 2 step 4. ✓

**Placeholder scan:** None. All test code, file edits, and commands are concrete.

**Risk assessment:**
- HIGH risk: Task 8 (journal authority) — interacts with hydration on daemon start. Mitigation: full recovery test suite at Step 5 + live validation at Step 6.
- MEDIUM risk: Task 9 (resume.py race) — STAGE_GROUP mapping may not exist yet; the plan provides the fallback `_group_of()` helper.
- LOW risk: Tasks 1, 2, 3, 4, 5, 7 — surgical, well-tested changes.

**Sequencing constraint:** Must execute in numeric order. Task 6 depends on Tasks 4-5. Task 8 depends on Task 7. Tasks 1, 2, 3, 9 can ship in parallel with the rest.

---

## Execution Handoff

Plan complete and saved to `docs/Phase128_PipelineRecoveryHardening/IMPLEMENTATION_PLAN.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration, fits the 9-task split well.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch each fix land in real time and can spare the context budget.

Both options assume the daemon is restarted after each commit that touches recovery code (memory: `feedback_restart_daemon_before_live_validation`).

Which approach?
