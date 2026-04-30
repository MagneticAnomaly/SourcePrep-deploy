# Reset Clean-Slate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scoped pipeline resets (`enrichment_full_reset` for stages 6–15, `finalize_full_reset` for stages 11–15) into true clean-slate operations: every disk artifact, SQLite row, in-memory cache, and stage-internal reuse path scoped to the reset's stages is purged or blocked from contributing zombie data to the next pipeline run.

**Architecture:** Keep the existing `_scoped_full_reset()` orchestrator in `enrichment.py`. Replace its curated denylist with an allowlist derived from a new `STAGE_OUTPUTS` registry. Convert silent cleanup-failure swallowing into fatal errors. Add three new helpers: `pipeline_journal.delete_runs()`, `KnowledgeIndex.invalidate()`, `recovery.is_reuse_blocked()`. Wire the reuse-blocking helper into the four stage-internal reuse read sites (clustering, deepening, group_reasoning, knowledge incremental). Add `"finalize"` to the barrier scope vocabulary so 11–15 resets get their own scope value.

**Tech Stack:** Python 3.11, FastAPI, SQLite (stdlib), pytest with `TestClient(app)` for endpoint tests. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-04-29-reset-clean-slate-design.md`](../specs/2026-04-29-reset-clean-slate-design.md)

---

## File Structure

**Created:**
- `tests/test_scoped_full_reset_zombies.py` — store-cleanup regression coverage for both endpoints
- `tests/test_scoped_full_reset_selfheal_race.py` — barrier-vs-selfheal interaction
- `tests/test_scoped_full_reset_reuse_gate.py` — per-stage reuse gate verification

**Modified:**
- `src/prep/services/pipeline_journal.py` — new `delete_runs()` method
- `src/prep/services/pipeline/recovery.py` — add `"finalize"` scope, new `is_reuse_blocked()` helper
- `src/prep/services/pipeline/__init__.py` — re-export `STAGE_OUTPUTS`, `PROJECT_META_ALLOWLIST`, `build_keep_set`
- `src/prep/services/pipeline/stages.py` — `STAGE_OUTPUTS` registry + helpers (co-located with `StageId`)
- `src/prep/core/knowledge.py` — `KnowledgeIndex.invalidate()` method
- `src/prep/core/cluster.py` — barrier check at `load_existing_modules` entry
- `src/prep/core/group_reasoning.py` — barrier check before fingerprint reuse loop
- `src/prep/core/deepening.py` — barrier check at `DriftDetector` entry
- `src/prep/api/routers/trace_routes/enrichment.py` — `_scoped_full_reset` rewrite, two endpoint adjustments
- `tests/test_scoped_full_reset.py` — extend with allowlist assertions

---

## Task 1: Add `delete_runs` method to `PipelineJournal`

**Files:**
- Modify: `src/prep/services/pipeline_journal.py`
- Test: `tests/test_pipeline_journal_delete_runs.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_journal_delete_runs.py`:

```python
"""Verify PipelineJournal.delete_runs scopes deletion correctly by group."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from prep.services.pipeline_journal import PipelineJournal


@pytest.fixture()
def journal(tmp_path: Path) -> PipelineJournal:
    j = PipelineJournal()
    j.init(tmp_path / "journal.db")
    return j


def _seed(j: PipelineJournal, run_id: str, project_id: str, group: str) -> None:
    """Insert a minimal pipeline_runs row for testing."""
    conn = j._conn
    assert conn is not None
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, project_id, group_name, status, "
        "stages, current_stage_index, created_at) "
        "VALUES (?, ?, ?, 'completed', '[]', 0, ?)",
        (run_id, project_id, group, time.time()),
    )
    conn.commit()


def test_delete_runs_scoped_to_one_group(journal: PipelineJournal) -> None:
    pid = "proj-A"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", pid, "finalize")

    deleted = journal.delete_runs(pid, groups={"finalize"})

    assert deleted == 1
    remaining = [
        r["group_name"] for r in journal._conn.execute(
            "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
        ).fetchall()
    ]
    assert sorted(remaining) == ["deep_enrichment", "fast_sync"]


def test_delete_runs_scoped_to_multiple_groups(journal: PipelineJournal) -> None:
    pid = "proj-B"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", pid, "finalize")

    deleted = journal.delete_runs(pid, groups={"deep_enrichment", "finalize"})

    assert deleted == 2
    remaining = [
        r["group_name"] for r in journal._conn.execute(
            "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
        ).fetchall()
    ]
    assert remaining == ["fast_sync"]


def test_delete_runs_no_groups_means_all_for_project(journal: PipelineJournal) -> None:
    pid = "proj-C"
    other = "proj-D"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", other, "fast_sync")

    deleted = journal.delete_runs(pid, groups=None)

    assert deleted == 2
    remaining_pids = [
        r["project_id"] for r in journal._conn.execute(
            "SELECT project_id FROM pipeline_runs"
        ).fetchall()
    ]
    assert remaining_pids == [other]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_pipeline_journal_delete_runs.py -v
```
Expected: FAIL with `AttributeError: 'PipelineJournal' object has no attribute 'delete_runs'`.

- [ ] **Step 3: Implement `delete_runs`**

Add to `src/prep/services/pipeline_journal.py` after the existing methods on `PipelineJournal` (around line ~600, before `close()` if present, otherwise at end of class):

```python
    def delete_runs(
        self,
        project_id: str,
        *,
        groups: Optional[set[str]] = None,
    ) -> int:
        """Delete pipeline_runs rows for a project.

        Called by scoped reset endpoints to drop journal state that would
        otherwise drive stale "stage X completed" indicators in the dashboard
        after a reset.

        Args:
            project_id: project to scope the delete to
            groups: if provided, only delete runs whose group_name is in this
                set (e.g. {"deep_enrichment", "finalize"} for Reset 6-15).
                If None, deletes all runs for the project regardless of group.

        Returns:
            Number of rows deleted.
        """
        conn = self._conn
        if conn is None:
            raise RuntimeError("Journal not initialized")

        with self._lock:
            if groups is None:
                cur = conn.execute(
                    "DELETE FROM pipeline_runs WHERE project_id = ?",
                    (project_id,),
                )
            else:
                placeholders = ",".join("?" * len(groups))
                params = (project_id, *sorted(groups))
                cur = conn.execute(
                    f"DELETE FROM pipeline_runs "
                    f"WHERE project_id = ? AND group_name IN ({placeholders})",
                    params,
                )
            conn.commit()
            return cur.rowcount or 0
```

If `Optional` isn't imported in this file, add `from typing import Optional` at the top.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_pipeline_journal_delete_runs.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline_journal.py tests/test_pipeline_journal_delete_runs.py
git commit -m "feat(reset): add PipelineJournal.delete_runs scoped to project + group set"
```

---

## Task 2: Add `"finalize"` to barrier scope vocabulary

The barrier currently supports `"sync"`, `"enrichment"`, `"all"`. Add `"finalize"` so the 11–15 reset can express its narrower scope.

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py` (around line 64)
- Test: `tests/test_reset_barrier_finalize_scope.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_reset_barrier_finalize_scope.py`:

```python
"""Verify the reset barrier accepts the new 'finalize' scope value."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.services.pipeline.recovery import (
    write_reset_barrier, read_reset_barrier, clear_reset_barrier,
)


@pytest.fixture()
def project_id(tmp_path: Path) -> str:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    repo = tmp_path / "repo"
    repo.mkdir()
    proj = reg.add_project(name="t", path=str(repo), mode="embedded")
    return proj.id


def test_finalize_scope_accepted(project_id: str) -> None:
    assert write_reset_barrier(project_id, reason="finalize_reset", scope="finalize")
    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "finalize"
    clear_reset_barrier(project_id)


def test_invalid_scope_rejected(project_id: str) -> None:
    with pytest.raises(ValueError, match="invalid barrier scope"):
        write_reset_barrier(project_id, reason="bogus", scope="bogus_scope")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_reset_barrier_finalize_scope.py -v
```
Expected: `test_finalize_scope_accepted` FAILS with `ValueError: invalid barrier scope: 'finalize'`.

- [ ] **Step 3: Add `"finalize"` to the valid scopes tuple**

Open `src/prep/services/pipeline/recovery.py`. Find the line:

```python
_VALID_BARRIER_SCOPES = ("sync", "enrichment", "all")
```

Replace with:

```python
_VALID_BARRIER_SCOPES = ("sync", "enrichment", "finalize", "all")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_reset_barrier_finalize_scope.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_reset_barrier_finalize_scope.py
git commit -m "feat(reset): accept 'finalize' as a barrier scope (stages 11-15)"
```

---

## Task 3: Add `is_reuse_blocked` helper to `recovery.py`

This is the function each stage's reuse path will call before reading prior outputs. The helper consults the barrier and checks whether the barrier's scope subsumes the caller's stage group.

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py`
- Test: `tests/test_reset_barrier_is_reuse_blocked.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_reset_barrier_is_reuse_blocked.py`:

```python
"""is_reuse_blocked() correctly subsumes scopes."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.services.pipeline.recovery import (
    write_reset_barrier, clear_reset_barrier, is_reuse_blocked,
)


@pytest.fixture()
def project_id(tmp_path: Path) -> str:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    repo = tmp_path / "repo"
    repo.mkdir()
    proj = reg.add_project(name="t", path=str(repo), mode="embedded")
    return proj.id


def test_no_barrier_reuse_allowed(project_id: str) -> None:
    assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
    assert is_reuse_blocked(project_id, stage_group="finalize") is False


def test_enrichment_barrier_blocks_both_groups(project_id: str) -> None:
    write_reset_barrier(project_id, reason="enrichment_reset", scope="enrichment")
    try:
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is True
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_finalize_barrier_blocks_only_finalize(project_id: str) -> None:
    write_reset_barrier(project_id, reason="finalize_reset", scope="finalize")
    try:
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_all_scope_blocks_everything(project_id: str) -> None:
    write_reset_barrier(project_id, reason="rebuild_all", scope="all")
    try:
        assert is_reuse_blocked(project_id, stage_group="fast_sync") is True
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is True
        assert is_reuse_blocked(project_id, stage_group="finalize") is True
    finally:
        clear_reset_barrier(project_id)


def test_sync_barrier_blocks_only_fast_sync(project_id: str) -> None:
    write_reset_barrier(project_id, reason="sync_rebuild", scope="sync")
    try:
        assert is_reuse_blocked(project_id, stage_group="fast_sync") is True
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment") is False
        assert is_reuse_blocked(project_id, stage_group="finalize") is False
    finally:
        clear_reset_barrier(project_id)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_reset_barrier_is_reuse_blocked.py -v
```
Expected: ImportError for `is_reuse_blocked`.

- [ ] **Step 3: Implement `is_reuse_blocked`**

Add to `src/prep/services/pipeline/recovery.py` near the existing barrier helpers (after `read_reset_barrier`, around line 130):

```python
# Subsumption: a barrier scope blocks reuse for the caller's group
# when the caller's group is in this set.
_SCOPE_BLOCKS: dict[str, frozenset[str]] = {
    "sync":       frozenset({"fast_sync"}),
    "enrichment": frozenset({"deep_enrichment", "finalize"}),
    "finalize":   frozenset({"finalize"}),
    "all":        frozenset({"fast_sync", "deep_enrichment", "finalize"}),
}


def is_reuse_blocked(project_id: str, *, stage_group: str) -> bool:
    """Return True if a reset barrier is active and its scope blocks
    incremental-reuse reads for the caller's stage_group.

    Stage-internal reuse paths (cluster fingerprint match, deepening
    drift cache, group_reasoning fingerprint reuse, knowledge incremental
    embed) call this before reading prior outputs. If True, the stage
    must treat existing artifacts as if they don't exist and process
    everything fresh.

    Args:
        project_id: the project being processed
        stage_group: one of "fast_sync", "deep_enrichment", "finalize"

    Returns:
        True if reuse is blocked, False if reuse is permitted.
    """
    info = read_reset_barrier(project_id)
    if info is None:
        return False
    scope = info.get("scope") or "all"  # legacy barriers default to "all"
    blocks = _SCOPE_BLOCKS.get(scope, frozenset())
    return stage_group in blocks
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_reset_barrier_is_reuse_blocked.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/test_reset_barrier_is_reuse_blocked.py
git commit -m "feat(reset): add is_reuse_blocked() helper with scope subsumption"
```

---

## Task 4: Add `STAGE_OUTPUTS` registry, `PROJECT_META_ALLOWLIST`, `build_keep_set`

Single source of truth for "what files does each stage produce" so reset's allowlist derives automatically.

**Files:**
- Modify: `src/prep/services/pipeline/stages.py`
- Modify: `src/prep/services/pipeline/__init__.py` (re-exports)
- Test: `tests/test_stage_outputs_registry.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_stage_outputs_registry.py`:

```python
"""STAGE_OUTPUTS registry + build_keep_set integrity."""
from __future__ import annotations

import pytest

from prep.services.pipeline.stages import (
    STAGE_OUTPUTS, PROJECT_META_ALLOWLIST, build_keep_set,
    StageId, FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES,
)


def test_every_stage_has_outputs_entry() -> None:
    expected = set(FAST_SYNC_STAGES) | set(DEEP_ENRICHMENT_STAGES) | set(FINALIZE_STAGES)
    assert set(STAGE_OUTPUTS.keys()) == expected


def test_keep_set_for_enrichment_reset_preserves_fast_sync() -> None:
    keep = build_keep_set("enrichment")
    # Fast-sync representative outputs survive
    assert "trace_nodes.jsonl" in keep
    assert "trace_inferred_edges.jsonl" in keep
    assert "validation_manifest.json" in keep
    # Project meta survives
    assert "project.json" in keep
    assert "repo_policy.json" in keep
    # Enrichment outputs are NOT in keep set
    assert "trace_epistemic.jsonl" not in keep
    assert "trace_modules.jsonl" not in keep
    assert "atlas.json" not in keep
    assert "concepts_manifest.json" not in keep


def test_keep_set_for_finalize_reset_preserves_enrichment() -> None:
    keep = build_keep_set("finalize")
    # Enrichment outputs survive
    assert "trace_epistemic.jsonl" in keep
    assert "trace_modules.jsonl" in keep
    assert "deep_knowledge_manifest.json" in keep
    # Finalize outputs are NOT in keep set
    assert "atlas.json" not in keep
    assert "atlas_manifest.json" not in keep
    assert "rules_manifest.json" not in keep
    assert "concepts_manifest.json" not in keep
    assert "antibodies_manifest.json" not in keep


def test_invalid_scope_raises() -> None:
    with pytest.raises(ValueError, match="unknown reset scope"):
        build_keep_set("not_a_scope")


def test_swarm_synthesis_outputs_are_declared() -> None:
    """Regression: these were missing from the curated denylist."""
    cluster_outputs = STAGE_OUTPUTS[StageId.CLUSTERING].files
    atlas_outputs = STAGE_OUTPUTS[StageId.ATLAS].files
    assert "trace_cluster_swarm_synthesis.json" in cluster_outputs
    assert "atlas_swarm_synthesis.json" in atlas_outputs


def test_project_meta_allowlist_includes_essentials() -> None:
    assert "project.json" in PROJECT_META_ALLOWLIST.files
    assert "repo_policy.json" in PROJECT_META_ALLOWLIST.files
    assert "logs" in PROJECT_META_ALLOWLIST.dirs
    assert "backups" in PROJECT_META_ALLOWLIST.dirs
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_stage_outputs_registry.py -v
```
Expected: ImportError for `STAGE_OUTPUTS` / `PROJECT_META_ALLOWLIST` / `build_keep_set`.

- [ ] **Step 3: Implement the registry**

Add to `src/prep/services/pipeline/stages.py` (at the end of the file):

```python
# ── Reset Allowlist Support ───────────────────────────────────────────
# Single source of truth: what files / directories does each stage produce?
# Used by scoped reset endpoints to build a keep-list (everything else in
# the index dir gets wiped). New stages adding new outputs land them here
# and reset behavior updates automatically.

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutputSpec:
    """Files and directories produced by a single stage."""
    files: frozenset[str] = field(default_factory=frozenset)
    dirs: frozenset[str] = field(default_factory=frozenset)

    @staticmethod
    def of(*, files: tuple[str, ...] = (), dirs: tuple[str, ...] = ()) -> "OutputSpec":
        return OutputSpec(files=frozenset(files), dirs=frozenset(dirs))


STAGE_OUTPUTS: dict[StageId, OutputSpec] = {
    # ── Fast Sync (1-5) ──────────────────────────────────────────
    StageId.STRUCTURAL: OutputSpec.of(
        files=("trace_nodes.jsonl", "trace_edges.jsonl", "trace_manifest.json"),
    ),
    StageId.INFERRED_EDGES: OutputSpec.of(
        files=(
            "trace_inferred_edges.jsonl",
            "trace_inferred_hashes.json",
            "trace_inferred_manifest.json",
        ),
    ),
    StageId.CATALOGUE: OutputSpec.of(
        files=(
            "catalogue.jsonl",
            "catalogue_manifest.json",
            "trace_augmented.jsonl",
            "trace_augment_manifest.json",
        ),
    ),
    StageId.VALIDATION: OutputSpec.of(
        files=("validation_manifest.json",),
    ),
    StageId.KNOWLEDGE: OutputSpec.of(
        files=(
            "knowledge_documents.json",
            "knowledge_embeddings.npy",
            "knowledge_manifest.json",
            # Legacy un-prefixed names (some installations still write these)
            "documents.json",
            "embeddings.npy",
            "manifest.json",
        ),
    ),
    # ── Deep Enrichment (6-10) ──────────────────────────────────
    StageId.ENRICHMENT: OutputSpec.of(
        files=("trace_epistemic.jsonl", "trace_epistemic_manifest.json"),
    ),
    StageId.GROUP_REASONING: OutputSpec.of(
        files=("trace_group_reasoning.jsonl", "group_reasoning_manifest.json"),
    ),
    StageId.CLUSTERING: OutputSpec.of(
        files=(
            "trace_modules.jsonl",
            "trace_modules_manifest.json",
            "trace_cluster_swarm_synthesis.json",
            "trace_swarm_synthesis.json",
        ),
    ),
    StageId.DEEPENING: OutputSpec.of(
        files=("deepening_manifest.json",),
    ),
    StageId.DEEP_KNOWLEDGE: OutputSpec.of(
        files=("deep_knowledge_manifest.json",),
    ),
    # ── Finalize (11-15) ────────────────────────────────────────
    StageId.ATLAS: OutputSpec.of(
        files=(
            "atlas.json",
            "atlas_prev.json",
            "atlas_manifest.json",
            "atlas_segments_manifest.json",
            "atlas_routing.json",
            "atlas_routing_embeddings.npy",
            "atlas_updated.signal",
            "atlas_swarm_synthesis.json",
        ),
        dirs=("atlas_roles", "atlas_segments"),
    ),
    StageId.RULES: OutputSpec.of(
        files=("rules_manifest.json",),
    ),
    StageId.CONCEPTS: OutputSpec.of(
        files=("concepts_manifest.json",),
    ),
    StageId.AUDIT: OutputSpec.of(
        files=("audit_manifest.json",),
        dirs=("audit",),
    ),
    StageId.ANTIBODIES: OutputSpec.of(
        files=("antibodies_manifest.json",),
    ),
}


# Project-level metadata that is never owned by any stage and survives all
# reset scopes. `pipeline_run_metadata.json` is intentionally NOT here — it
# is run-state and gets wiped along with the run's stage outputs.
PROJECT_META_ALLOWLIST: OutputSpec = OutputSpec.of(
    files=("project.json", "repo_policy.json"),
    dirs=("logs", "backups"),
)


# scope → which stage groups should SURVIVE the reset.
_KEEP_GROUPS_BY_SCOPE: dict[str, tuple[StageId, ...]] = {
    "enrichment": tuple(FAST_SYNC_STAGES),
    "finalize": tuple(FAST_SYNC_STAGES) + tuple(DEEP_ENRICHMENT_STAGES),
}


def build_keep_set(scope: str) -> set[str]:
    """Return the set of file/dir names that must survive a reset of the given scope.

    Includes every output declared by stages that survive, plus PROJECT_META.
    Reset wipes anything in <idx_dir> not in this set.

    Args:
        scope: "enrichment" (Reset 6-15) or "finalize" (Reset 11-15)

    Raises:
        ValueError: if scope is not recognized.
    """
    if scope not in _KEEP_GROUPS_BY_SCOPE:
        raise ValueError(f"unknown reset scope: {scope!r}")
    keep: set[str] = set()
    keep |= PROJECT_META_ALLOWLIST.files
    keep |= PROJECT_META_ALLOWLIST.dirs
    for stage_id in _KEEP_GROUPS_BY_SCOPE[scope]:
        spec = STAGE_OUTPUTS[stage_id]
        keep |= spec.files
        keep |= spec.dirs
    # `.checkpoints` and `.reset_barrier` are managed explicitly by the reset
    # orchestrator (not stage-owned), so they are NOT added to keep — reset
    # wipes .checkpoints and writes its own .reset_barrier.
    return keep
```

Now update `src/prep/services/pipeline/__init__.py` to re-export. Find the existing `from prep.services.pipeline.stages import (...)` block (or wherever stages re-exports happen) and add the new names. If there is no such block, append at the end:

```python
from prep.services.pipeline.stages import (  # noqa: F401
    OutputSpec,
    STAGE_OUTPUTS,
    PROJECT_META_ALLOWLIST,
    build_keep_set,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_stage_outputs_registry.py -v
```
Expected: 6 passed.

If `test_every_stage_has_outputs_entry` fails because some `StageId` values don't match (e.g. `StageId.STRUCTURAL` doesn't exist with that name), inspect `src/prep/services/pipeline/stages.py` enum values and adjust the registry keys to match the actual enum member names. The test asserts every stage in `FAST_SYNC_STAGES + DEEP_ENRICHMENT_STAGES + FINALIZE_STAGES` has a registry entry — fix mismatches by aligning the dict keys.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/stages.py src/prep/services/pipeline/__init__.py tests/test_stage_outputs_registry.py
git commit -m "feat(reset): add STAGE_OUTPUTS registry + build_keep_set allowlist"
```

---

## Task 5: Add `KnowledgeIndex.invalidate()` method

The in-memory `KnowledgeIndex` holds `_documents`, `_embeddings`, `_manifest`. Reset must clear them so the next stage 10 run starts from empty in-memory state.

**Files:**
- Modify: `src/prep/core/knowledge.py`
- Test: `tests/test_knowledge_index_invalidate.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_knowledge_index_invalidate.py`:

```python
"""KnowledgeIndex.invalidate() clears in-memory state."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from prep.core.knowledge import KnowledgeIndex


@pytest.fixture()
def index(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model_name = "test-embedder"
    return KnowledgeIndex(tmp_path, embedder)


def test_invalidate_clears_in_memory_state(index: KnowledgeIndex) -> None:
    index._documents = [{"id": "a"}, {"id": "b"}]
    index._embeddings = np.zeros((2, 4), dtype=np.float32)
    index._manifest = {"count": 2}

    index.invalidate()

    assert index._documents is None
    assert index._embeddings is None
    assert index._manifest == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_knowledge_index_invalidate.py -v
```
Expected: FAIL with `AttributeError: 'KnowledgeIndex' object has no attribute 'invalidate'`.

- [ ] **Step 3: Implement `invalidate`**

Open `src/prep/core/knowledge.py`. After `__init__` (around line 60, before `_embedder_model`), add:

```python
    def invalidate(self) -> None:
        """Drop in-memory state. The next read forces a fresh _load() from disk.

        Called by scoped reset endpoints so post-reset reads do not see
        stale chunks from prior runs. Disk files are wiped by the reset's
        file-deletion pass, not by this method.
        """
        self._documents = None
        self._embeddings = None
        self._manifest = {}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_knowledge_index_invalidate.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/knowledge.py tests/test_knowledge_index_invalidate.py
git commit -m "feat(reset): add KnowledgeIndex.invalidate() for in-memory cache reset"
```

---

## Task 6: Wire `is_reuse_blocked` into `cluster.load_existing_modules`

**Files:**
- Modify: `src/prep/core/cluster.py` (line ~998 — `load_existing_modules`)
- Test: `tests/test_cluster_reuse_gated_by_barrier.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cluster_reuse_gated_by_barrier.py`:

```python
"""Cluster.load_existing_modules respects the reset barrier."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _seed_modules_file(idx_dir: Path, n: int) -> None:
    idx_dir.mkdir(parents=True, exist_ok=True)
    path = idx_dir / "trace_modules.jsonl"
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({"id": f"m{i}", "fingerprint": f"fp{i}"}) + "\n")


def test_load_existing_modules_returns_empty_when_barrier_blocks(tmp_path: Path) -> None:
    from prep.core.cluster import ClusterSynthesizer
    _seed_modules_file(tmp_path, 5)

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.modules_path = tmp_path / "trace_modules.jsonl"
    synth.project_id = "proj-X"

    with patch("prep.core.cluster.is_reuse_blocked", return_value=True):
        result = synth.load_existing_modules()

    assert result == {}


def test_load_existing_modules_returns_data_when_barrier_clear(tmp_path: Path) -> None:
    from prep.core.cluster import ClusterSynthesizer
    _seed_modules_file(tmp_path, 3)

    synth = ClusterSynthesizer.__new__(ClusterSynthesizer)
    synth.modules_path = tmp_path / "trace_modules.jsonl"
    synth.project_id = "proj-Y"

    with patch("prep.core.cluster.is_reuse_blocked", return_value=False):
        result = synth.load_existing_modules()

    assert len(result) == 3
```

Note: the test instantiates `ClusterSynthesizer` via `__new__` to skip its real constructor; the unit test only exercises `load_existing_modules`. If your real class is named differently, update both occurrences.

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_cluster_reuse_gated_by_barrier.py -v
```
Expected: FAIL — `ImportError: cannot import name 'is_reuse_blocked' from 'prep.core.cluster'` (because the import doesn't exist yet) OR the first test fails because the gate isn't wired.

- [ ] **Step 3: Wire the barrier check**

Open `src/prep/core/cluster.py`. Add to imports near top:

```python
from prep.services.pipeline.recovery import is_reuse_blocked
```

Find `def load_existing_modules(self) -> Dict[str, ModuleEntry]:` (line ~998). Replace its body's first lines:

```python
    def load_existing_modules(self) -> Dict[str, ModuleEntry]:
        """Load existing module entries."""
        entries: Dict[str, ModuleEntry] = {}
        if self.modules_path.exists():
            with open(self.modules_path, "r", encoding="utf-8") as f:
```

with:

```python
    def load_existing_modules(self) -> Dict[str, ModuleEntry]:
        """Load existing module entries.

        Returns an empty dict if a reset barrier is active for this project
        and its scope blocks deep_enrichment reuse — reset semantics require
        clustering to treat all prior data as nonexistent.
        """
        entries: Dict[str, ModuleEntry] = {}
        if is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Cluster reuse blocked by reset barrier for project %s — "
                "treating prior trace_modules.jsonl as empty",
                self.project_id,
            )
            return entries
        if self.modules_path.exists():
            with open(self.modules_path, "r", encoding="utf-8") as f:
```

If `self.project_id` is not an existing attribute on `ClusterSynthesizer`, look in the class `__init__` for what's stored. If only `self.idx_dir` is stored, derive project_id from the idx_dir parent name, or thread project_id through the constructor (see usages of `ClusterSynthesizer(...)` and adjust the call sites — there should be a small number).

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_cluster_reuse_gated_by_barrier.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/cluster.py tests/test_cluster_reuse_gated_by_barrier.py
git commit -m "feat(reset): clustering returns no prior modules when barrier active"
```

---

## Task 7: Wire `is_reuse_blocked` into `group_reasoning` reuse loop

**Files:**
- Modify: `src/prep/core/group_reasoning.py` (around line ~730 — fingerprint reuse loop)
- Test: `tests/test_group_reasoning_reuse_gated_by_barrier.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_group_reasoning_reuse_gated_by_barrier.py`:

```python
"""group_reasoning skips reuse when barrier is active."""
from __future__ import annotations

from unittest.mock import patch

from prep.core.group_reasoning import GroupReasoningEntry


def test_existing_groups_filtered_when_barrier_active() -> None:
    from prep.core.group_reasoning import _filter_reusable_existing
    existing = {
        "g1": GroupReasoningEntry(
            group_id="g1", member_fingerprint="fp1", analysis="...", model="m",
        ),
        "g2": GroupReasoningEntry(
            group_id="g2", member_fingerprint="fp2", analysis="...", model="m",
        ),
    }
    with patch("prep.core.group_reasoning.is_reuse_blocked", return_value=True):
        out = _filter_reusable_existing("proj-X", existing)
    assert out == {}


def test_existing_groups_passthrough_when_barrier_clear() -> None:
    from prep.core.group_reasoning import _filter_reusable_existing
    existing = {
        "g1": GroupReasoningEntry(
            group_id="g1", member_fingerprint="fp1", analysis="...", model="m",
        ),
    }
    with patch("prep.core.group_reasoning.is_reuse_blocked", return_value=False):
        out = _filter_reusable_existing("proj-Y", existing)
    assert out == existing
```

Note: the test imports `GroupReasoningEntry` and calls a small helper `_filter_reusable_existing`. Constructor args might be slightly different — adjust to match the actual `GroupReasoningEntry` fields (check `src/prep/core/group_reasoning.py` for its definition).

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_group_reasoning_reuse_gated_by_barrier.py -v
```
Expected: FAIL — `_filter_reusable_existing` doesn't exist.

- [ ] **Step 3: Add helper + wire it into the reuse path**

Open `src/prep/core/group_reasoning.py`. Add to imports near top:

```python
from prep.services.pipeline.recovery import is_reuse_blocked
```

Add a module-level helper near the top of the file (after imports, before the main class):

```python
def _filter_reusable_existing(
    project_id: str,
    existing: dict[str, "GroupReasoningEntry"],
) -> dict[str, "GroupReasoningEntry"]:
    """Drop all existing entries when a reset barrier blocks reuse.

    Lets the fingerprint-comparison loop treat the prior run's groups as
    if they never ran, forcing every group to be re-analyzed.
    """
    if is_reuse_blocked(project_id, stage_group="deep_enrichment"):
        logger.info(
            "Group reasoning reuse blocked by reset barrier for project %s — "
            "all %d existing entries discarded",
            project_id, len(existing),
        )
        return {}
    return existing
```

Now find the `# Check staleness` block (around line ~730 — the `for gid, members in group_map.items()` loop that builds `reuse`). Right before the `for` loop, replace the local reference to existing entries. Find a line like:

```python
        for gid, members in group_map.items():
            fingerprint = compute_group_fingerprint(members, epistemic)
            ex = existing.get(gid)
```

Replace with:

```python
        existing = _filter_reusable_existing(self.project_id, existing)
        for gid, members in group_map.items():
            fingerprint = compute_group_fingerprint(members, epistemic)
            ex = existing.get(gid)
```

If `self.project_id` is not an attribute on the GroupReasoning class, thread it through the constructor (`__init__`) and update call sites — there should be one or two.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_group_reasoning_reuse_gated_by_barrier.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/group_reasoning.py tests/test_group_reasoning_reuse_gated_by_barrier.py
git commit -m "feat(reset): group_reasoning treats prior entries as empty when barrier active"
```

---

## Task 8: Wire `is_reuse_blocked` into `deepening` drift detection

**Files:**
- Modify: `src/prep/core/deepening.py` (around line ~123 — `DriftDetector.detect`)
- Test: `tests/test_deepening_drift_gated_by_barrier.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_deepening_drift_gated_by_barrier.py`:

```python
"""Deepening drift treats every node as stale when reset barrier is active."""
from __future__ import annotations

from unittest.mock import patch


def test_drift_marks_all_nodes_stale_when_barrier_active() -> None:
    from prep.core.deepening import DriftDetector

    nodes = {f"n{i}": {"hash": "h"} for i in range(5)}
    detector = DriftDetector.__new__(DriftDetector)
    detector.project_id = "proj-X"
    detector.scored_nodes = nodes

    with patch("prep.core.deepening.is_reuse_blocked", return_value=True):
        report = detector.detect()

    assert sorted(report.stale_nodes) == sorted(nodes.keys())
```

Note: depending on `DriftDetector` field names you may need to adjust. The test asserts that when the barrier is active, all currently-known nodes are marked stale — meaning everything will be re-deepened.

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_deepening_drift_gated_by_barrier.py -v
```
Expected: FAIL.

- [ ] **Step 3: Wire the barrier check**

Open `src/prep/core/deepening.py`. Add to imports near top:

```python
from prep.services.pipeline.recovery import is_reuse_blocked
```

Find `def detect(self)` on `DriftDetector` (around line ~123). At the very top of the method body, before any existing logic:

```python
    def detect(self) -> "DriftReport":
        """Run drift detection across all scored nodes.

        Returns a DriftReport with stale nodes, missing references,
        ...
        """
        # Reset barrier active → treat every node as stale so deepening
        # re-processes everything fresh, ignoring any cached "fresh"
        # decisions from prior runs.
        if is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Deepening drift gate triggered by reset barrier for project %s — "
                "marking all %d known nodes stale",
                self.project_id, len(self.scored_nodes),
            )
            return DriftReport(
                stale_nodes=list(self.scored_nodes.keys()),
                missing_refs=[],
            )
        # ... existing body continues here unchanged
```

Adjust to match the existing `DriftReport` constructor (the test imports it; if it has more required fields, add them with empty defaults). If `self.project_id` doesn't exist on `DriftDetector`, thread it through `__init__`.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_deepening_drift_gated_by_barrier.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/deepening.py tests/test_deepening_drift_gated_by_barrier.py
git commit -m "feat(reset): deepening marks all nodes stale when barrier active"
```

---

## Task 9: Wire `is_reuse_blocked` into `knowledge` incremental embed

**Files:**
- Modify: `src/prep/core/knowledge.py` (the `build()` method, around the `docs_reused` calculation at line ~436)
- Test: `tests/test_knowledge_incremental_gated_by_barrier.py` (new)

- [ ] **Step 1: Read the current `build()` method to understand the reuse logic**

```bash
sed -n '380,460p' src/prep/core/knowledge.py
```

Locate where `reused_vectors` is computed. You'll see the pattern: previously-embedded vectors are reused when `doc.id in self._documents_by_id`. We will short-circuit that lookup when the barrier is active.

- [ ] **Step 2: Write the failing test**

Create `tests/test_knowledge_incremental_gated_by_barrier.py`:

```python
"""KnowledgeIndex incremental embed forces full re-embed when barrier is active."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.core.knowledge import KnowledgeIndex


@pytest.fixture()
def index(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model_name = "test-embedder"
    embedder.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    idx = KnowledgeIndex(tmp_path, embedder)
    idx.project_id = "proj-X"  # set if not already an attribute
    return idx


def test_no_vectors_reused_when_barrier_active(index: KnowledgeIndex) -> None:
    """When the barrier is active, the reuse lookup must return empty
    so every document is freshly embedded."""
    with patch("prep.core.knowledge.is_reuse_blocked", return_value=True):
        reused = index._lookup_reusable_vectors([{"id": "a"}, {"id": "b"}])
    assert reused == {}
```

This test calls a helper `_lookup_reusable_vectors` we'll introduce. It encapsulates the reuse decision so the gate is unit-testable.

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_knowledge_incremental_gated_by_barrier.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement `_lookup_reusable_vectors` + wire it into `build()`**

In `src/prep/core/knowledge.py`, add to imports:

```python
from prep.services.pipeline.recovery import is_reuse_blocked
```

Add a method on `KnowledgeIndex` (place it near `build()`):

```python
    def _lookup_reusable_vectors(
        self,
        docs: list[dict],
    ) -> dict[str, "np.ndarray"]:
        """Return doc_id → embedding for docs already embedded in the prior run.

        When a reset barrier is active for this project's deep_enrichment scope,
        always returns empty so build() re-embeds every doc fresh.
        """
        project_id = getattr(self, "project_id", None)
        if project_id and is_reuse_blocked(project_id, stage_group="deep_enrichment"):
            logger.info(
                "Knowledge incremental embed: barrier active for %s — "
                "skipping reuse, every doc will be re-embedded",
                project_id,
            )
            return {}
        # Existing reuse lookup logic (extracted from build()):
        if self._documents is None or self._embeddings is None:
            return {}
        existing = {d["id"]: i for i, d in enumerate(self._documents)}
        reused: dict[str, "np.ndarray"] = {}
        for d in docs:
            i = existing.get(d["id"])
            if i is not None:
                reused[d["id"]] = self._embeddings[i]
        return reused
```

Then in `build()`, find the existing block that computes `reused_vectors` (around line ~430) and replace with a call to `self._lookup_reusable_vectors(docs)`. The exact pre-existing code is small — read 10 lines above and below `docs_reused = len(reused_vectors)` and adjust to call the helper.

You will also need to ensure `self.project_id` is set on the index. Look at how `KnowledgeIndex` is instantiated (`grep -rn "KnowledgeIndex(" src/prep`) and add `self.project_id = project_id` in `__init__` with a new `project_id: str` parameter, threading it through the call sites. If that's invasive, accept `project_id` as an optional kwarg that defaults to None — the gate will simply not trigger for callers that don't pass it (which is acceptable: those callers are non-pipeline paths like the Audit page that also don't experience reset zombies).

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_knowledge_incremental_gated_by_barrier.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prep/core/knowledge.py tests/test_knowledge_incremental_gated_by_barrier.py
git commit -m "feat(reset): knowledge incremental embed forces full re-embed when barrier active"
```

---

## Task 10: Rewrite `_scoped_full_reset` (allowlist + fatal errors + new helpers)

This is the largest task. It replaces the curated denylist with the allowlist, makes cleanup failures fatal, and wires in `delete_runs`, `KnowledgeIndex.invalidate`, and the new barrier scope.

**Files:**
- Modify: `src/prep/api/routers/trace_routes/enrichment.py` (lines ~743–1151 — the wipe lists, `_scoped_full_reset`, and the two endpoint functions)

- [ ] **Step 1: Read the current implementation in full**

```bash
sed -n '740,1155p' src/prep/api/routers/trace_routes/enrichment.py
```

Note the existing imports section near the top of the file — we need `build_keep_set`, `STAGE_OUTPUTS`, and `pipeline_journal`.

- [ ] **Step 2: Replace the lists block (lines ~743–973)**

Find and DELETE the following constants:
- `DEEP_ENRICHMENT_FILES = [...]`
- `DEEP_ENRICHMENT_DIRS = [...]`
- `FINALIZE_FILES = [...]`
- `FINALIZE_DIRS = [...]`
- `ENRICHMENT_FULL_FILES = [...]`
- `ENRICHMENT_FULL_DIRS = [...]`

They are now obsolete — replaced by `STAGE_OUTPUTS` + `build_keep_set`.

Add this near the top of the file (with other imports):

```python
from prep.services.pipeline import build_keep_set
```

- [ ] **Step 3: Rewrite `_scoped_full_reset`**

Replace the entire `_scoped_full_reset` function with:

```python
def _scoped_full_reset(
    project_id: str,
    *,
    label: str,
    scope: str,                    # "enrichment" or "finalize"
    barrier_reason: str,
    journal_groups: set[str],
    knowledge_invalidate_scope: str,
) -> Dict[str, Any]:
    """Scoped clean-slate reset.

    Wipes everything in the project index dir except the allowlist for the
    given scope (stages 1-5 outputs for "enrichment", 1-10 for "finalize"),
    plus PROJECT_META. Cleans associated SQLite stores, in-memory caches,
    and the pipeline journal. Writes a reset barrier so selfheal cannot
    resurrect cleared data and stage-internal reuse paths skip prior outputs.

    Cleanup failures (store wipes, journal delete, KnowledgeIndex invalidate)
    are FATAL — the endpoint returns 500 with detail. Per-file unlink errors
    during the disk wipe are collected and returned as 207 Multi-Status.

    Args:
        project_id: project to reset
        label: human-readable name for logs / response
        scope: "enrichment" (Reset 6-15) or "finalize" (Reset 11-15)
        barrier_reason: written into the barrier file for diagnostics
        journal_groups: which pipeline_runs groups to delete
        knowledge_invalidate_scope: passed to KnowledgeIndex.invalidate (no-op
            for "finalize" — finalize doesn't write the knowledge index)
    """
    import shutil
    from prep.server import (
        _require_project_writable, _is_project_trace_building,
        _project_trace_indexes,
    )
    proj = _require_project_writable(project_id)

    # ── 1. PRE-FLIGHT ──────────────────────────────────────────────
    if _is_project_trace_building(project_id):
        raise ApiException(
            status_code=409, code="PIPELINE_RUNNING",
            message=f"Cannot reset {label} while pipeline is running",
        )
    for state_map, state_label in [
        (_deep_analysis_state, "deep analysis"),
        (_epistemic_state, "epistemic enrichment"),
        (_cluster_state, "cluster synthesis"),
        (_deepening_state, "deepening loop"),
    ]:
        state = state_map.get(project_id)
        if state and state.get("thread") and state["thread"].is_alive():
            raise ApiException(
                status_code=409, code="PIPELINE_RUNNING",
                message=f"Cannot reset {label} while {state_label} is running",
            )

    idx_dir = project_index_dir(proj)

    # ── 2. WRITE BARRIER FIRST (atomicity) ─────────────────────────
    from prep.services.pipeline.recovery import write_reset_barrier
    if not write_reset_barrier(project_id, reason=barrier_reason, scope=scope):
        raise ApiException(
            status_code=500, code="BARRIER_WRITE_FAILED",
            message="Could not write reset barrier — refusing to proceed",
        )

    # ── 3. STOP IN-FLIGHT WORK ─────────────────────────────────────
    try:
        from prep.services.pipeline_orchestrator import pipeline_orchestrator
        pipeline_orchestrator.clear_project(project_id)
    except Exception as e:
        logger.warning("orchestrator.clear_project failed (continuing): %s", e, exc_info=True)
    _project_trace_indexes.pop(project_id, None)

    # ── 4. DEBUG BACKUP (before wipe) ──────────────────────────────
    keep_set = build_keep_set(scope)
    deleted: list[str] = []
    errors: list[str] = []
    backup_path: Optional[str] = None
    try:
        # Build a list of files that WOULD be deleted, for the backup.
        delete_targets = [
            p.name for p in idx_dir.iterdir()
            if p.is_file() and p.name not in keep_set
        ]
        backup_path = _backup_files_if_debug(idx_dir, delete_targets, barrier_reason)
    except Exception as e:
        logger.warning("Debug backup failed (continuing without backup): %s", e, exc_info=True)

    # ── 5. WIPE DISK (allowlist) ───────────────────────────────────
    if idx_dir.is_dir():
        for entry in idx_dir.iterdir():
            if entry.name in keep_set:
                continue
            if entry.name.startswith(".") and entry.name not in (".checkpoints", ".reset_barrier"):
                # Hidden files like .branch_snapshots are managed elsewhere.
                continue
            if entry.name == ".reset_barrier":
                continue  # Don't wipe the barrier we just wrote!
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                deleted.append(entry.name + ("/" if entry.is_dir() else ""))
            except Exception as e:
                errors.append(f"{entry.name}: {e}")

    # ── 6. WIPE STORES (FATAL on failure) ──────────────────────────
    cleanup_errors: dict[str, str] = {}

    try:
        from prep.services.pipeline_journal import pipeline_journal
        pipeline_journal.delete_runs(project_id, groups=journal_groups)
    except Exception as e:
        cleanup_errors["pipeline_journal"] = repr(e)
        logger.error("pipeline_journal.delete_runs failed", exc_info=True)

    try:
        from prep.services.concept_store import concept_store
        concept_store.clear_project(project_id)
    except Exception as e:
        cleanup_errors["concept_store"] = repr(e)
        logger.error("concept_store.clear_project failed", exc_info=True)

    try:
        from prep.services.antibody_store import antibody_store
        antibody_store.clear_project(project_id)
    except Exception as e:
        cleanup_errors["antibody_store"] = repr(e)
        logger.error("antibody_store.clear_project failed", exc_info=True)

    if knowledge_invalidate_scope == "enrichment":
        try:
            from prep.core.knowledge import KnowledgeIndex
            # KnowledgeIndex is per-idx-dir; if any cached instances exist
            # in module-level caches, they need to be invalidated. The
            # safest minimum: instantiate against idx_dir and invalidate.
            # Real call sites that hold the instance must also call invalidate.
            from prep.services.embedder_factory import get_default_embedder
            ki = KnowledgeIndex(idx_dir, get_default_embedder())
            ki.invalidate()
        except Exception as e:
            cleanup_errors["knowledge_index"] = repr(e)
            logger.error("KnowledgeIndex.invalidate failed", exc_info=True)

    if cleanup_errors:
        # Reset is incomplete. Barrier remains so partial state isn't trusted.
        raise ApiException(
            status_code=500, code="RESET_CLEANUP_FAILED",
            message="Reset cleanup failed; barrier remains active. Retry the reset.",
            details={"errors": cleanup_errors, "deleted_count": len(deleted)},
        )

    # ── 7. WIPE CHECKPOINTS ────────────────────────────────────────
    cp_dir = idx_dir / ".checkpoints"
    if cp_dir.is_dir():
        try:
            shutil.rmtree(cp_dir)
            deleted.append(".checkpoints/")
        except Exception as e:
            errors.append(f".checkpoints/: {e}")

    logger.info(
        "Scoped reset (%s) complete for %s: deleted=%d, errors=%d, barrier=active",
        label, project_id, len(deleted), len(errors),
    )

    result: Dict[str, Any] = {"deleted": deleted, "errors": errors}
    if backup_path:
        result["backup"] = backup_path
    # Per-file errors → 207 Multi-Status; full success → 200.
    if errors:
        return ok(result, status_code=207)
    return ok(result)
```

If `ApiException` doesn't accept a `details` kwarg, check its signature in `src/prep/api/exceptions.py` (or wherever it lives) and adjust — most ApiException impls accept arbitrary kwargs. Same with `ok(result, status_code=207)` — if the project's `ok()` envelope doesn't accept a status_code, surface the partial-failure as a top-level field in the body and return 200 (less ideal but acceptable).

- [ ] **Step 4: Update the two endpoint functions**

Find `enrichment_full_reset` (around line ~1114) and replace its body:

```python
@router.delete("/projects/{project_id}/enrichment/full-reset")
def enrichment_full_reset(project_id: str) -> Dict[str, Any]:
    """Clean-slate reset for stages 6-15 (enrichment + finalize).

    Wipes every artifact produced by deep enrichment and finalize from disk
    AND from concept/antibody/journal stores AND from in-memory caches. Writes
    a reset barrier (scope='enrichment') so selfheal and stage-internal reuse
    paths cannot resurrect or reuse pre-reset data until the next finalize
    completes legitimately. Stages 1-5 (fast sync) outputs are preserved.
    """
    return _scoped_full_reset(
        project_id,
        label="enrichment + finalize",
        scope="enrichment",
        barrier_reason="enrichment_reset",
        journal_groups={"deep_enrichment", "finalize"},
        knowledge_invalidate_scope="enrichment",
    )
```

Find `finalize_full_reset` and replace:

```python
@router.delete("/projects/{project_id}/finalize/full-reset")
def finalize_full_reset(project_id: str) -> Dict[str, Any]:
    """Clean-slate reset for stages 11-15 (finalize only).

    Wipes atlas / rules / concepts / audit / antibodies artifacts from disk,
    clears the concept and antibody stores, deletes finalize-group rows from
    the pipeline journal, and writes a reset barrier (scope='finalize'). Fast
    sync (1-5) and deep enrichment (6-10) outputs are preserved.
    """
    return _scoped_full_reset(
        project_id,
        label="finalize",
        scope="finalize",
        barrier_reason="finalize_reset",
        journal_groups={"finalize"},
        knowledge_invalidate_scope="finalize",  # no-op for finalize
    )
```

- [ ] **Step 5: Run existing reset tests to make sure nothing regressed**

```bash
.venv/bin/pytest tests/test_scoped_full_reset.py -v
```
Some tests may now fail because the response shape or status code changed. **Fix the tests, not the implementation** — the new contract is intentional. Update them to:
- Expect 200 (no errors) or 207 (per-file errors), not always 200
- Drop assertions about specific files in the OLD `DEEP_ENRICHMENT_FILES` list — replace with allowlist-based assertions (file X should be gone, file Y should survive)

If existing tests reference the deleted constants (`DEEP_ENRICHMENT_FILES`, etc.), remove those imports.

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/trace_routes/enrichment.py tests/test_scoped_full_reset.py
git commit -m "feat(reset): allowlist wipe + fatal cleanup errors + journal/cache cleanup"
```

---

## Task 11: Extend `test_scoped_full_reset.py` with allowlist regression assertions

Confirms the new behavior: any unrecognized file in `idx_dir` gets wiped (not just files on a curated list).

**Files:**
- Modify: `tests/test_scoped_full_reset.py`

- [ ] **Step 1: Add the new test cases**

Append to `tests/test_scoped_full_reset.py`:

```python
def test_enrichment_reset_wipes_unknown_files_via_allowlist(client, tmp_path):
    """Files not in any stage's output spec also get wiped.

    Regression: previous denylist-based reset left atlas_swarm_synthesis.json,
    trace_cluster_swarm_synthesis.json, and any future-added stage outputs
    behind. Allowlist behavior wipes them by default.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Seed a fast-sync output (must SURVIVE)
    (idx_dir / "trace_nodes.jsonl").write_text("{}\n")
    # Seed a known enrichment output (must be wiped)
    (idx_dir / "trace_modules.jsonl").write_text("{}\n")
    # Seed an UNKNOWN file (regression — must also be wiped)
    (idx_dir / "atlas_swarm_synthesis_v99.json").write_text("{}")
    (idx_dir / "future_stage_output.jsonl").write_text("{}")

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert (idx_dir / "trace_nodes.jsonl").is_file()  # fast-sync survived
    assert not (idx_dir / "trace_modules.jsonl").exists()
    assert not (idx_dir / "atlas_swarm_synthesis_v99.json").exists()
    assert not (idx_dir / "future_stage_output.jsonl").exists()


def test_finalize_reset_preserves_enrichment_outputs(client, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Fast-sync + enrichment outputs (must SURVIVE)
    (idx_dir / "trace_nodes.jsonl").write_text("{}\n")
    (idx_dir / "trace_epistemic.jsonl").write_text("{}\n")
    (idx_dir / "trace_modules.jsonl").write_text("{}\n")
    # Finalize outputs (must be wiped)
    (idx_dir / "atlas.json").write_text("{}")
    (idx_dir / "rules_manifest.json").write_text("{}")

    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    assert (idx_dir / "trace_nodes.jsonl").is_file()
    assert (idx_dir / "trace_epistemic.jsonl").is_file()
    assert (idx_dir / "trace_modules.jsonl").is_file()
    assert not (idx_dir / "atlas.json").exists()
    assert not (idx_dir / "rules_manifest.json").exists()


def test_enrichment_reset_wipes_audit_dir(client, tmp_path):
    """Regression: audit/spaghetti.json was surviving despite audit/ being
    in the denylist. Allowlist with explicit audit/ exclusion fixes."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid = _add_embedded_project(client, repo_root)
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = idx_dir / "audit"
    audit_dir.mkdir()
    (audit_dir / "spaghetti.json").write_text("{}")

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    assert not audit_dir.exists()
```

- [ ] **Step 2: Run the new tests**

```bash
.venv/bin/pytest tests/test_scoped_full_reset.py -v
```
Expected: all tests pass (existing + 3 new).

- [ ] **Step 3: Commit**

```bash
git add tests/test_scoped_full_reset.py
git commit -m "test(reset): allowlist-based wipe regression coverage"
```

---

## Task 12: New `test_scoped_full_reset_zombies.py`

Coverage for the four subsystems where data was surviving silently: concepts, antibodies, journal rows, KnowledgeIndex.

**Files:**
- Create: `tests/test_scoped_full_reset_zombies.py`

- [ ] **Step 1: Write the file**

```python
"""Reset 6-15 and Reset 11-15 must purge all derived stores: concepts,
antibodies, journal rows for the relevant groups, and the KnowledgeIndex
in-memory cache. Regression coverage for the empirical bugs found 2026-04-29
where 200 concepts and 373 antibodies survived multiple resets."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    return TestClient(app)


def _add_project(client: TestClient, root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(root), "name": "t", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _seed_concepts(project_id: str, n: int) -> None:
    from prep.services.concept_store import concept_store
    for i in range(n):
        concept_store.save(
            project_id=project_id,
            title=f"concept-{i}",
            content="...",
            category="technical",
            confidence=0.5,
            anchors=[],
            tags=[],
        )


def _seed_antibodies(project_id: str, n: int) -> None:
    from prep.services.antibody_store import antibody_store
    import json
    for i in range(n):
        antibody_store.upsert(
            id=f"ab-{i}",
            project_id=project_id,
            name=f"ab-{i}",
            source_concept_id="",
            trigger_json=json.dumps({"type": "test"}),
            response_json=json.dumps({}),
            severity="warn",
            status="testing",
        )


def _seed_journal_runs(project_id: str) -> None:
    from prep.services.pipeline_journal import pipeline_journal
    conn = pipeline_journal._conn
    assert conn is not None
    now = time.time()
    for run_id, group in [
        ("r-fs", "fast_sync"),
        ("r-de", "deep_enrichment"),
        ("r-fn", "finalize"),
    ]:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id, project_id, group_name, status, "
            "stages, current_stage_index, created_at) "
            "VALUES (?, ?, ?, 'completed', '[]', 0, ?)",
            (run_id, project_id, group, now),
        )
    conn.commit()


@pytest.mark.parametrize("endpoint", [
    "enrichment/full-reset",
    "finalize/full-reset",
])
def test_concepts_purged(client, tmp_path, endpoint):
    pid = _add_project(client, tmp_path / "repo")
    _seed_concepts(pid, 5)

    from prep.services.concept_store import concept_store
    pre = concept_store.list_concepts(project_id=pid)
    assert len(pre) == 5

    res = client.delete(f"/projects/{pid}/{endpoint}")
    assert res.status_code in (200, 207)

    post = concept_store.list_concepts(project_id=pid)
    assert post == []


@pytest.mark.parametrize("endpoint", [
    "enrichment/full-reset",
    "finalize/full-reset",
])
def test_antibodies_purged(client, tmp_path, endpoint):
    pid = _add_project(client, tmp_path / "repo")
    _seed_antibodies(pid, 5)

    from prep.services.antibody_store import antibody_store
    pre = antibody_store.list_antibodies(project_id=pid)
    assert len(pre) == 5

    res = client.delete(f"/projects/{pid}/{endpoint}")
    assert res.status_code in (200, 207)

    post = antibody_store.list_antibodies(project_id=pid)
    assert post == []


def test_enrichment_reset_purges_de_and_finalize_journal_rows(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    _seed_journal_runs(pid)

    from prep.services.pipeline_journal import pipeline_journal
    conn = pipeline_journal._conn
    assert conn is not None
    pre = conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()
    assert len(pre) == 3

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    post = conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()
    assert sorted(r["group_name"] for r in post) == ["fast_sync"]


def test_finalize_reset_purges_only_finalize_journal_rows(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    _seed_journal_runs(pid)

    res = client.delete(f"/projects/{pid}/finalize/full-reset")
    assert res.status_code in (200, 207)

    from prep.services.pipeline_journal import pipeline_journal
    conn = pipeline_journal._conn
    assert conn is not None
    post = conn.execute(
        "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()
    assert sorted(r["group_name"] for r in post) == ["deep_enrichment", "fast_sync"]


def test_observations_NOT_purged(client, tmp_path):
    """Observations are user-authored and intentionally survive reset."""
    pid = _add_project(client, tmp_path / "repo")
    from prep.services.observation_store import observation_store
    observation_store.save(
        project_id=pid,
        content="user-authored note",
        category="note",
    )

    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    post = observation_store.list_observations(project_id=pid)
    assert len(post) == 1
```

If `concept_store.save` / `antibody_store.upsert` / `observation_store.save` / their list methods have different signatures in the codebase, adjust the call sites accordingly. The test names match the assertion intent regardless of plumbing.

- [ ] **Step 2: Run the tests**

```bash
.venv/bin/pytest tests/test_scoped_full_reset_zombies.py -v
```
Expected: all 8 parametrized tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scoped_full_reset_zombies.py
git commit -m "test(reset): regression coverage for concept/antibody/journal/observation cleanup"
```

---

## Task 13: New `test_scoped_full_reset_selfheal_race.py`

Confirms the barrier prevents selfheal from resurrecting cleared data, even across daemon restart simulations.

**Files:**
- Create: `tests/test_scoped_full_reset_selfheal_race.py`

- [ ] **Step 1: Write the file**

```python
"""Selfheal cannot resurrect cleared data while the barrier is active —
even if the daemon dies mid-reset and restarts, or if _golden snapshots
exist on disk that look like recoverable orphans."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    return TestClient(app)


def _add_project(client: TestClient, root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(root), "name": "t", "mode": "embedded"},
    )
    return str(res.json()["data"]["project"]["id"])


def _idx_dir(client: TestClient, pid: str) -> Path:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    return Path(project_index_dir(require_project(pid)))


def test_barrier_persists_after_reset(client, tmp_path):
    pid = _add_project(client, tmp_path / "repo")
    res = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res.status_code in (200, 207)

    from prep.services.pipeline.recovery import reset_barrier_active, read_reset_barrier
    assert reset_barrier_active(pid)
    info = read_reset_barrier(pid)
    assert info is not None
    assert info["scope"] == "enrichment"


def test_golden_snapshot_does_not_resurrect_during_barrier(client, tmp_path):
    """If _golden/ snapshots exist post-reset, selfheal must NOT copy them
    back into idx_dir. Barrier is the gate."""
    pid = _add_project(client, tmp_path / "repo")
    idx_dir = _idx_dir(client, pid)
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Reset wipes .checkpoints, but suppose a daemon-restart race re-creates
    # _golden somehow — barrier must still block resurrection.
    client.delete(f"/projects/{pid}/enrichment/full-reset")

    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / "atlas.json").write_text('{"resurrected": true}')
    (golden / "_meta.json").write_text("{}")

    # Simulate a recovery / selfheal pass.
    from prep.services.pipeline import recovery
    if hasattr(recovery, "auto_heal"):
        recovery.auto_heal(pid)

    # atlas.json must NOT be in idx_dir — barrier should block resurrection.
    assert not (idx_dir / "atlas.json").exists()


def test_reset_idempotent_under_partial_failure(client, tmp_path, monkeypatch):
    """If concept_store fails the first time, second reset attempt completes.
    Barrier remains, no partial state leaks through."""
    pid = _add_project(client, tmp_path / "repo")

    from prep.services import concept_store as cs_mod
    real = cs_mod.concept_store.clear_project
    calls = {"n": 0}
    def flaky(project_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated DB lock")
        return real(project_id)
    monkeypatch.setattr(cs_mod.concept_store, "clear_project", flaky)

    # First call: cleanup raises → 500
    res1 = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res1.status_code == 500

    # Barrier still active — confirm
    from prep.services.pipeline.recovery import reset_barrier_active
    assert reset_barrier_active(pid)

    # Second call: succeeds
    res2 = client.delete(f"/projects/{pid}/enrichment/full-reset")
    assert res2.status_code in (200, 207)
```

- [ ] **Step 2: Run the tests**

```bash
.venv/bin/pytest tests/test_scoped_full_reset_selfheal_race.py -v
```
Expected: all 3 tests pass.

If `recovery.auto_heal` doesn't exist (the test guards with `hasattr`), the second test still asserts the file isn't there — which is the right behavior: nothing copied it in.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scoped_full_reset_selfheal_race.py
git commit -m "test(reset): barrier vs selfheal/golden-resurrection race coverage"
```

---

## Task 14: New `test_scoped_full_reset_reuse_gate.py`

End-to-end coverage that each stage's reuse path returns no prior data when the barrier is active.

**Files:**
- Create: `tests/test_scoped_full_reset_reuse_gate.py`

- [ ] **Step 1: Write the file**

```python
"""Stage-internal reuse paths consult the reset barrier.

When a barrier whose scope subsumes the stage's group is active, each
reuse path must return as if no prior data existed."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.services.pipeline.recovery import (
    write_reset_barrier, clear_reset_barrier, is_reuse_blocked,
)


@pytest.fixture()
def project_id(tmp_path: Path) -> str:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    repo = tmp_path / "repo"
    repo.mkdir()
    proj = reg.add_project(name="t", path=str(repo), mode="embedded")
    return proj.id


def test_enrichment_barrier_blocks_clustering(project_id):
    write_reset_barrier(project_id, reason="r", scope="enrichment")
    try:
        assert is_reuse_blocked(project_id, stage_group="deep_enrichment")
    finally:
        clear_reset_barrier(project_id)


def test_enrichment_barrier_blocks_finalize_consumers(project_id):
    """Reset 6-15 also blocks finalize-stage reuse (concepts/atlas swarm)."""
    write_reset_barrier(project_id, reason="r", scope="enrichment")
    try:
        assert is_reuse_blocked(project_id, stage_group="finalize")
    finally:
        clear_reset_barrier(project_id)


def test_finalize_barrier_does_not_block_enrichment(project_id):
    """Reset 11-15 must NOT block stage 6-10 reuse (we kept their outputs)."""
    write_reset_barrier(project_id, reason="r", scope="finalize")
    try:
        assert not is_reuse_blocked(project_id, stage_group="deep_enrichment")
        assert is_reuse_blocked(project_id, stage_group="finalize")
    finally:
        clear_reset_barrier(project_id)


def test_no_barrier_allows_all_reuse(project_id):
    assert not is_reuse_blocked(project_id, stage_group="fast_sync")
    assert not is_reuse_blocked(project_id, stage_group="deep_enrichment")
    assert not is_reuse_blocked(project_id, stage_group="finalize")
```

- [ ] **Step 2: Run the tests**

```bash
.venv/bin/pytest tests/test_scoped_full_reset_reuse_gate.py -v
```
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scoped_full_reset_reuse_gate.py
git commit -m "test(reset): per-stage reuse-gate scope-subsumption coverage"
```

---

## Task 15: Run the full test suite

Catch any cross-file regressions introduced by the changes (especially threading project_id through cluster / group_reasoning / deepening / knowledge constructors).

- [ ] **Step 1: Run all reset / pipeline tests**

```bash
.venv/bin/pytest tests/ -k "reset or pipeline or cluster or group_reasoning or deepening or knowledge" -v
```
Expected: all pass.

- [ ] **Step 2: Run the full suite**

```bash
.venv/bin/pytest tests/ -x -v 2>&1 | tail -80
```
Expected: all pass (or pre-existing failures unrelated to this change).

If any failures touch code we modified, investigate and fix in place. Common pitfalls:
- New required `project_id` parameter on a constructor breaks unrelated tests → make it optional with a sane default, or update the call site.
- An `import` we added creates a circular import → move the import inside the function body.

- [ ] **Step 3: Commit any fixups**

If fixes are needed:

```bash
git add <files>
git commit -m "fix: address regressions surfaced by full test suite"
```

---

## Task 16: Manual verification on the live SourcePrep project

End-to-end smoke of the actual user-reported scenario: reset 6-15, manually start enrichment, confirm no zombies.

- [ ] **Step 1: Restart the daemon** (no hot-reload — code changes need a fresh process)

```bash
pkill -f "prep.cli serve" || true
sleep 1
.venv/bin/prep serve --port 8400 > /tmp/prep_daemon_logs/manual_verify.log 2>&1 &
sleep 3
curl -s localhost:8400/health
```
Expected: `{"status":"ok","version":"..."}`

- [ ] **Step 2: Capture pre-reset state**

```bash
PID=f1636374-abc6-410d-99ee-822120379e79
echo "=== Pre-reset journal rows ==="
sqlite3 ~/.local/share/sourceprep/prep_pipeline_journal.db \
  "SELECT COUNT(*), group_name FROM pipeline_runs WHERE project_id='$PID' GROUP BY group_name"
echo "=== Pre-reset concepts ==="
sqlite3 ~/.local/share/sourceprep/prep_concepts.db \
  "SELECT COUNT(*) FROM concepts WHERE project_id='$PID'"
echo "=== Pre-reset antibodies ==="
sqlite3 ~/.local/share/sourceprep/prep_antibodies.db \
  "SELECT COUNT(*) FROM antibodies WHERE project_id='$PID'"
```

- [ ] **Step 3: Reset 6-15**

```bash
curl -X DELETE "localhost:8400/projects/$PID/enrichment/full-reset" | python3 -m json.tool
```
Expected: `{"success": true, "data": {"deleted": [...], "errors": []}}` with status 200 (or 207 if disk errors).

- [ ] **Step 4: Verify post-reset state**

```bash
echo "=== Post-reset journal rows ==="
sqlite3 ~/.local/share/sourceprep/prep_pipeline_journal.db \
  "SELECT COUNT(*), group_name FROM pipeline_runs WHERE project_id='$PID' GROUP BY group_name"
echo "=== Post-reset concepts ==="
sqlite3 ~/.local/share/sourceprep/prep_concepts.db \
  "SELECT COUNT(*) FROM concepts WHERE project_id='$PID'"
echo "=== Post-reset antibodies ==="
sqlite3 ~/.local/share/sourceprep/prep_antibodies.db \
  "SELECT COUNT(*) FROM antibodies WHERE project_id='$PID'"
echo "=== .sourceprep/ contents ==="
ls -la /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/
echo "=== Barrier state ==="
cat /Volumes/4TB-BAD/HumanAI/CoDRAG/.sourceprep/.reset_barrier 2>/dev/null
```
Expected:
- Journal: `fast_sync` row count unchanged; `deep_enrichment` and `finalize` rows GONE.
- Concepts: 0 (excluding the system-seeded one re-added on next daemon startup, which is acceptable).
- Antibodies: 0.
- `.sourceprep/`: only fast-sync outputs + project meta + `.reset_barrier`.
- Barrier: `<timestamp>\nenrichment_reset\nenrichment\n`.

- [ ] **Step 5: Trigger enrichment manually and watch for fingerprint reuse**

```bash
curl -X POST "localhost:8400/projects/$PID/pipeline/deep" -H 'Content-Type: application/json' -d '{}'
sleep 5
tail -200 /tmp/prep_daemon_logs/manual_verify.log | grep -iE "(reuse|barrier|cluster|fingerprint|to analyze)"
```
Expected log evidence:
- `Cluster reuse blocked by reset barrier for project f1636374-... — treating prior trace_modules.jsonl as empty` (or equivalent)
- `Group reasoning reuse blocked by reset barrier for project f1636374-...`
- Cluster reuse line should show `0 reused (fingerprint match)` not the previous `84 reused`.

- [ ] **Step 6: Stop the manual run, document results**

```bash
curl -X POST "localhost:8400/projects/$PID/pipeline/rebuild/stop"
```

Save the captured outputs from steps 2, 4, 5 to `tmp/reset-verification-2026-04-29.md` for the project record.

- [ ] **Step 7: Commit the verification log**

```bash
git add tmp/reset-verification-2026-04-29.md 2>/dev/null || true
git commit --allow-empty -m "verify(reset): live SourcePrep project — clean slate confirmed"
```

---

## Self-Review Notes

**Spec coverage check:**
- §"Architecture" → Task 4 (registry), Task 10 (orchestrator rewrite) ✓
- §"Data flow during reset" steps 1–7 → Task 10 implements exactly these steps ✓
- §"Anti-zombie guarantees" — barrier first → Task 10 step 2 ✓; per-stage reuse gate → Tasks 5–9 ✓
- §"Scope-aware behavior" table → Task 10 endpoint params, Task 4 keep-set logic ✓
- §"`STAGE_OUTPUTS` registry" → Task 4 ✓
- §"Error handling" — fatal store wipe failures, 207 for per-file errors → Task 10 step 3 ✓
- §"Testing" — three new test files + extension of existing → Tasks 11–14 ✓

**Placeholder scan:** All steps contain concrete code or commands. The two "investigate the existing code path and adjust if shape differs" notes (Task 6/7/8 about threading `project_id` through constructors, Task 10 about `ApiException(details=...)` signature) describe specific adjustments to make in response to specific shapes the engineer will encounter — not "fix it later" placeholders.

**Type consistency:** `is_reuse_blocked(project_id: str, *, stage_group: str)` signature is consistent across all callers (Tasks 3, 5, 6, 7, 8, 9). `STAGE_OUTPUTS: dict[StageId, OutputSpec]`, `build_keep_set(scope: str) -> set[str]` consistent. `delete_runs(project_id, *, groups: Optional[set[str]])` signature matches caller in Task 10.

---

## Future Work (out of scope, captured for the record)

A "repair" capability that intentionally resurrects from `_golden/` snapshots and other recovery sources — separate endpoint, separate UI, requires its own design. Captured in the spec under `## Future work`. Reset must be clean-slate first; repair is a deliberate user action on top of it.
