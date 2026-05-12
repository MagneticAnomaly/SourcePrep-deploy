# Phase 135 Implementation Plan — Delete Mid-Pipeline Staleness Checks (Stages 7, 8, 10)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the three remaining per-stage fingerprint/hash staleness checks the pipeline still runs mid-flight (stages 7, 8, 10). Each stage instead consumes the Changeset emitted by stage 1.

**Architecture:** Same as Phase 134. Stage 1 emits the `Changeset` to `<idx_dir>/changeset.json`. `WorkerFactory._build_worker` attaches `wrapped_worker.changeset` to every closure. The three target engines (`GroupReasoningEngine`, `ClusterSynthesizer`, `KnowledgeIndex`) gain a `changeset` attribute set by the worker before invocation, inherit from the Phase 134 `Worker` base class, and use `self.should_process(file_path)` to decide what to skip — no fingerprint computation, no hash comparison.

**Tech Stack:** Python 3.11, pytest, `Changeset` dataclass (`src/prep/services/pipeline/changeset.py`), `Worker` base class (`src/prep/services/pipeline/workers/base.py`).

---

## File Structure

| File | Responsibility | Net change |
|---|---|---|
| `src/prep/core/group_reasoning.py` | Stage 7 engine. **Lose:** `member_fingerprint` field on `GroupReasoningEntry`, `compute_group_fingerprint` function, fingerprint compare loop in `run()`. **Gain:** `class GroupReasoningEngine(Worker)`, changeset-driven stale-set computation. | ~−60 |
| `src/prep/core/cluster.py` | Stage 8 engine. **Lose:** `_cluster_fingerprint` method, fingerprint match loop in `_synthesize_batched` setup. **Gain:** `class ClusterSynthesizer(Worker)`, changeset-driven stale-set. | ~−60 |
| `src/prep/core/knowledge.py` | Stage 10 engine (`is_deep=True` path). **Lose:** `prev_hash == content_hash` compare at line 454 *for the deep path only*. `_load_previous_for_reuse` simplified. **Gain:** `class KnowledgeIndex(Worker)`, changeset gates the deep path. | ~−20 |
| `src/prep/services/pipeline/workers/__init__.py` | Three injection points (~3-5 lines each). | +10 |
| `tests/test_phase135_*.py` | New TDD coverage. | +tests |

**Estimated net production diff:** −130 lines.

---

## Setup (do once before Task 0)

- [ ] **Setup Step 1: Create worktree**

```bash
git worktree add .claude/worktrees/phase-135-fingerprint-deletion -b phase-135-fingerprint-deletion
cd .claude/worktrees/phase-135-fingerprint-deletion
ln -s ../../../.venv .venv
```

Verify baseline test count:

```bash
.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q 2>&1 | tail -3
```

Expected: 55 passed (the Phase 134 suite — these must stay green throughout Phase 135).

---

## Task 0 — Phase 134 hot-fix: latent NameError in changeset injection

**Background:** Phase 134's injection pattern references a name `wrapped_worker` from inside each base-worker's inner closure (e.g. `augmenter.changeset = getattr(wrapped_worker, "changeset", None)` at `workers/__init__.py:501`). The inner `worker` closure has no `wrapped_worker` in its closure or module globals, so this raises `NameError` the moment the worker is actually invoked. Phase 134's tests pass because they only check `wrapper.changeset` was set on the wrapper — they never invoke the inner worker. The bug is silent in CI but fires the moment a real pipeline run reaches catalogue/enrichment/deepening.

**Reproduce first** (sanity check that the bug exists in your worktree):

```bash
.venv/bin/python -c "
from unittest.mock import MagicMock, patch
from prep.services.pipeline.workers.factory import WorkerFactory
from prep.services.pipeline.stages import StageId
with patch('prep.services.pipeline.workers.WorkerFactory._get_project_and_config') as mock_proj, \
     patch('prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task') as mock_llm, \
     patch('prep.core.TraceAugmenter') as mock_aug, \
     patch('prep.services.project_helpers.require_project') as req_proj, \
     patch('prep.core.project_registry.project_index_dir') as proj_idx:
    mock_proj.return_value = (MagicMock(name='p', config={}, path='/tmp/x'), {}, [], [], 0, 0, 0, 0, 0)
    mock_llm.return_value = MagicMock(model='x', provider='x')
    mock_aug.return_value.run.return_value = MagicMock(augmented=0, failed=0, skipped=0, paused=False)
    req_proj.return_value = MagicMock(id='p1', path='/tmp/x')
    proj_idx.return_value = '/tmp/x'
    worker = WorkerFactory.create_worker('p1', StageId.CATALOGUE)
    slot = MagicMock(cancel_token=None)
    worker(slot, lambda *a, **kw: None)
" 2>&1 | tail -3
```

Expected before Task 0: `NameError: name 'wrapped_worker' is not defined`.

**The fix (one line in `_build_worker`, plus one renaming sweep):**

1. In `_build_worker` (lines 186-206), also set the attribute on `base_worker` so it survives the indirection:
   ```python
   wrapped_worker.changeset = read_changeset(_idx_dir)
   base_worker.changeset = wrapped_worker.changeset  # ← new line, Phase 135 hot-fix
   ```
   And in the `except` branch:
   ```python
   wrapped_worker.changeset = None
   base_worker.changeset = None  # ← new line, Phase 135 hot-fix
   ```

2. In each inner-worker site, rename `wrapped_worker` → `worker` (the inner closure's self-reference, which Python resolves via lexical scoping). Four sites:
   - `workers/__init__.py:501` (augmenter)
   - `workers/__init__.py:710` (enricher)
   - `workers/__init__.py:1031` (enricher inside deepening)
   - `workers/__init__.py:1045` (drift_detector inside deepening)

**Files:**
- Modify: `src/prep/services/pipeline/workers/__init__.py` (4 + 2 sites)
- Test: `tests/test_phase135_injection_nameerror_fixed.py` (new — reproduces the bug and verifies the fix)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase135_injection_nameerror_fixed.py`:

```python
"""Phase 135 Task 0 — Phase 134's changeset injection had a latent
NameError because each inner worker referenced `wrapped_worker`, a name
not in its closure. This test invokes each affected worker end-to-end
and verifies (a) no NameError, (b) the changeset reaches the engine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset, write_changeset
from prep.services.pipeline.stages import StageId


@pytest.fixture
def fake_changeset(tmp_path: Path) -> Changeset:
    cs = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"c.py"}),
        run_id="r1",
        base_run_id=None,
    )
    write_changeset(tmp_path, cs)
    return cs


def _common_patches(idx_dir: Path):
    """Patch all the daemon-side dependencies so we can invoke a worker
    end-to-end without a running daemon."""
    fake_proj = MagicMock()
    fake_proj.id = "p1"
    fake_proj.name = "p"
    fake_proj.config = {}
    fake_proj.path = str(idx_dir.parent)
    return [
        patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config",
              return_value=(fake_proj, {}, [], [], 0, 0, 0, 0, 0)),
        patch("prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task",
              return_value=MagicMock(model="x", provider="x")),
        patch("prep.services.project_helpers.require_project", return_value=fake_proj),
        patch("prep.core.project_registry.project_index_dir", return_value=idx_dir),
    ]


def test_catalogue_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Phase 134 bug: invoking the catalogue worker raised NameError on
    `wrapped_worker`. Phase 135 Task 0 fixes it."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    captured: dict = {}
    fake_augmenter = MagicMock()
    fake_augmenter.run.return_value = MagicMock(
        augmented=0, failed=0, skipped=0, paused=False,
    )

    def capture_changeset(*a, **kw):
        captured["changeset"] = fake_augmenter.changeset
        return fake_augmenter

    with patch("prep.core.TraceAugmenter", side_effect=capture_changeset):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.CATALOGUE)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)  # MUST NOT NameError
        finally:
            patch.stopall()

    # Changeset reached the augmenter, not None.
    assert captured.get("changeset") is not None
    assert captured["changeset"].run_id == "r1"


def test_enrichment_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Same check for the enrichment stage."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    captured: dict = {}
    fake_enricher = MagicMock()
    fake_enricher.run.return_value = {"enriched": 0, "failed": 0}

    def capture(*a, **kw):
        captured["changeset"] = fake_enricher.changeset
        return fake_enricher

    with patch("prep.core.EpistemicEnricher", side_effect=capture):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.ENRICHMENT)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)
        finally:
            patch.stopall()

    assert captured.get("changeset") is not None


def test_deepening_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Same check for the deepening stage. Two injection sites in
    `_deepening_worker`: enricher (line 1031) and drift_detector
    (line 1045)."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    fake_loop = MagicMock()
    fake_loop.run.return_value = {"converged": True, "iterations": 0}
    fake_loop.drift_detector = MagicMock()

    with patch("prep.core.DeepeningLoop", return_value=fake_loop), \
         patch("prep.core.EpistemicEnricher"):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.DEEPENING)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)
        finally:
            patch.stopall()

    # drift_detector.changeset must be set, not raise NameError
    assert fake_loop.drift_detector.changeset is not None
```

- [ ] **Step 2: Run test to verify it fails with NameError**

Run: `.venv/bin/pytest tests/test_phase135_injection_nameerror_fixed.py -v`
Expected: FAIL with `NameError: name 'wrapped_worker' is not defined`.

- [ ] **Step 3: Fix `_build_worker` to also set the attribute on `base_worker`**

In `src/prep/services/pipeline/workers/__init__.py`, edit the `try`/`except` at lines 196-204:

```python
        # Phase 134: inject the changeset for downstream stages to consult.
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
```

- [ ] **Step 4: Rename `wrapped_worker` → `worker` at the four inner-closure sites**

In `src/prep/services/pipeline/workers/__init__.py`:

- **Line 501** (`_augment_worker`):
  ```python
  augmenter.changeset = getattr(worker, "changeset", None)
  ```
- **Line 710** (`_epistemic_worker`):
  ```python
  enricher.changeset = getattr(worker, "changeset", None)
  ```
- **Line 1031** (`_deepening_worker`, enricher injection):
  ```python
  enricher.changeset = getattr(worker, "changeset", None)
  ```
- **Line 1045** (`_deepening_worker`, drift_detector injection):
  ```python
  loop.drift_detector.changeset = getattr(worker, "changeset", None)
  ```

(In each inner-closure, `worker` is the inner `def worker(slot, progress_cb)` itself, accessible via the surrounding function's local scope where `worker` is defined.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase135_injection_nameerror_fixed.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run Phase 134 suite (no regression)**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q`
Expected: 55 passed.

- [ ] **Step 7: Commit**

```bash
git add tests/test_phase135_injection_nameerror_fixed.py \
        src/prep/services/pipeline/workers/__init__.py
git commit -m "fix(phase135-task0): Phase 134 latent NameError in changeset injection"
```

---

## Task 1 — Stage 7 (group_reasoning) changeset cutover

**Files:**
- Modify: `src/prep/core/group_reasoning.py` (delete `member_fingerprint` field, `compute_group_fingerprint`, fingerprint check loop; inherit `Worker`)
- Modify: `src/prep/services/pipeline/workers/__init__.py:754-795` (inject changeset on `GroupReasoningEngine`)
- Test: `tests/test_phase135_group_reasoning_changeset.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase135_group_reasoning_changeset.py`:

```python
"""Phase 135 — stage 7 (group_reasoning) consults the Changeset.

A group is stale iff any member file is in changeset.modified | deleted.
No fingerprint computation. No member_fingerprint field on entries.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.group_reasoning import GroupReasoningEngine, GroupReasoningEntry
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def engine(tmp_path: Path) -> GroupReasoningEngine:
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider = "test"
    return GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="p1")


def test_engine_inherits_worker(engine: GroupReasoningEngine) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(engine, Worker)


def test_engine_has_changeset_attribute(engine: GroupReasoningEngine) -> None:
    # Worker base class default
    assert engine.changeset is None


def test_should_process_routes_through_changeset(engine: GroupReasoningEngine) -> None:
    engine.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert engine.should_process("a.py") is True
    assert engine.should_process("b.py") is True
    assert engine.should_process("c.py") is False  # deleted
    assert engine.should_process("d.py") is False  # unchanged


def test_member_fingerprint_field_removed() -> None:
    """GroupReasoningEntry no longer carries member_fingerprint."""
    fields = {f for f in GroupReasoningEntry.__dataclass_fields__}
    assert "member_fingerprint" not in fields


def test_compute_group_fingerprint_deleted() -> None:
    """The fingerprint helper is gone."""
    import prep.core.group_reasoning as gr_mod
    assert not hasattr(gr_mod, "compute_group_fingerprint")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase135_group_reasoning_changeset.py -v`
Expected: FAIL — `GroupReasoningEngine is not Worker`, `compute_group_fingerprint exists`, `member_fingerprint in fields`.

- [ ] **Step 3: Implement — delete fingerprint from `GroupReasoningEntry`**

In `src/prep/core/group_reasoning.py`, at the `GroupReasoningEntry` dataclass (~line 53-95):

Remove the `member_fingerprint: str = ""` field. Remove `"member_fingerprint": self.member_fingerprint,` from `to_dict`. Remove `member_fingerprint=d.get("member_fingerprint", "")` from `from_dict`.

- [ ] **Step 4: Implement — delete `compute_group_fingerprint`**

In `src/prep/core/group_reasoning.py`, delete the entire function (lines 205-221):

```python
def compute_group_fingerprint(...) -> str:
    ...
```

- [ ] **Step 5: Implement — delete two callers of compute_group_fingerprint**

In `src/prep/core/group_reasoning.py`:
- Around line 431 (inside `_run_single_sequential` or similar): remove `fingerprint = compute_group_fingerprint(member_ids, epistemic)` and the `member_fingerprint=fingerprint,` kwarg from the `GroupReasoningEntry(...)` constructor call.
- Around line 719/732 (the `_run_swarm` synthesis path): same — remove the fingerprint compute and the kwarg.

- [ ] **Step 6: Implement — make `GroupReasoningEngine` a Worker**

In `src/prep/core/group_reasoning.py`, at the class definition (~line 226):

```python
from prep.services.pipeline.workers.base import Worker

class GroupReasoningEngine(Worker):
    """Stage 7: Group Deep Reasoning.

    Phase 135: inherits from Worker so the pipeline injects the Changeset
    before .run() and the engine can ask `self.should_process(file_path)`
    instead of computing per-group fingerprints.
    """
```

(Insert the `from ... import Worker` near the top of the file with the other prep imports.)

- [ ] **Step 7: Implement — replace fingerprint check in `run()` with changeset gate**

In `src/prep/core/group_reasoning.py`, replace lines 783-800 (the `# Check staleness` block):

```python
        # Phase 135: a group is stale iff any member file is in
        # changeset.modified | deleted. No fingerprint computation —
        # the changeset is the canonical source of truth.
        to_analyze: list[tuple[str, list[str]]] = []
        reuse: dict[str, GroupReasoningEntry] = {}

        for gid, members in group_map.items():
            ex = existing.get(gid)
            if ex is not None and not self._group_is_stale(members):
                reuse[gid] = ex
            else:
                to_analyze.append((gid, members))

        total_groups = len(group_map)
        logger.info(
            "Group reasoning: %d groups total, %d to analyze, %d reused (unchanged per changeset)",
            total_groups, len(to_analyze), len(reuse),
        )
```

Add the helper inside `GroupReasoningEngine`:

```python
    def _group_is_stale(self, member_node_ids: list[str]) -> bool:
        """A group is stale iff any member's underlying file is in
        changeset.modified | deleted. Falls back to 'all stale' if the
        changeset is unavailable (defensive — never happens in the live
        pipeline since WorkerFactory always reads it)."""
        if self.changeset is None:
            return True
        for nid in member_node_ids:
            # node_ids are stable_file_node_id("file:<rel_path>")
            file_path = nid[len("file:"):] if nid.startswith("file:") else nid
            if file_path in self.changeset.modified or file_path in self.changeset.deleted:
                return True
        return False
```

- [ ] **Step 8: Implement — inject changeset in `_group_reasoning_worker`**

In `src/prep/services/pipeline/workers/__init__.py:754-795`, replace:

```python
            engine = GroupReasoningEngine(llm=llm_client, index_dir=idx_dir, project_id=project_id)
            result = engine.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
```

with:

```python
            engine = GroupReasoningEngine(llm=llm_client, index_dir=idx_dir, project_id=project_id)
            # Phase 135: inject the Changeset so the engine can ask
            # should_process() instead of computing per-group fingerprints.
            # Use `worker` (the inner closure self-reference) — Task 0
            # fixed _build_worker to set base_worker.changeset.
            engine.changeset = getattr(worker, "changeset", None)
            result = engine.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
```

- [ ] **Step 9: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase135_group_reasoning_changeset.py -v`
Expected: PASS (5 tests).

- [ ] **Step 10: Run Phase 134 suite to ensure no regression**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q`
Expected: 55 passed.

- [ ] **Step 11: Commit**

```bash
git add tests/test_phase135_group_reasoning_changeset.py \
        src/prep/core/group_reasoning.py \
        src/prep/services/pipeline/workers/__init__.py
git commit -m "feat(phase135): stage 7 group_reasoning consults Changeset, fingerprint deleted"
```

---

## Task 2 — Stage 8 (clustering) changeset cutover

**Files:**
- Modify: `src/prep/core/cluster.py` (delete `_cluster_fingerprint`, fingerprint reuse loop; inherit `Worker`)
- Modify: `src/prep/services/pipeline/workers/__init__.py:798-843`
- Test: `tests/test_phase135_cluster_changeset.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase135_cluster_changeset.py`:

```python
"""Phase 135 — stage 8 (clustering) consults the Changeset."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.cluster import ClusterSynthesizer
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def synth(tmp_path: Path) -> ClusterSynthesizer:
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider = "test"
    return ClusterSynthesizer(
        llm=llm,
        index_dir=tmp_path,
        batch_profile=None,
        project_id="p1",
    )


def test_synthesizer_inherits_worker(synth: ClusterSynthesizer) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(synth, Worker)


def test_synthesizer_has_changeset_attribute(synth: ClusterSynthesizer) -> None:
    assert synth.changeset is None


def test_should_process_routes_through_changeset(synth: ClusterSynthesizer) -> None:
    synth.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert synth.should_process("a.py") is True
    assert synth.should_process("b.py") is True
    assert synth.should_process("c.py") is False
    assert synth.should_process("d.py") is False


def test_cluster_fingerprint_method_deleted() -> None:
    """ClusterSynthesizer._cluster_fingerprint is gone."""
    assert not hasattr(ClusterSynthesizer, "_cluster_fingerprint")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase135_cluster_changeset.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement — delete `_cluster_fingerprint`**

In `src/prep/core/cluster.py`, delete lines 1681-1686 (the `@staticmethod def _cluster_fingerprint(...)` block).

- [ ] **Step 4: Implement — delete fingerprint reuse loop**

In `src/prep/core/cluster.py`, find the block at lines 1920-1976 (the `fp_to_module` map population through the end of the `for cluster in clusters:` reuse-decision loop). Replace it with:

```python
        # Phase 135: reuse a cluster iff none of its member files is in
        # changeset.modified | deleted. No fingerprints — the changeset
        # is the canonical source of truth for "what changed."
        total_work = len(clusters)
        modules: Dict[str, ModuleEntry] = {}
        failed = 0
        reused = 0
        synthesized = 0

        to_synthesize: List[Cluster] = []
        for cluster in clusters:
            module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
            ex = existing_modules.get(module_id)
            if ex is not None and not self._cluster_is_stale(cluster.member_node_ids):
                modules[module_id] = ex
                reused += 1
                continue
            to_synthesize.append(cluster)

        logger.info(
            "Cluster reuse: %d total, %d reused (per changeset), %d to synthesize",
            total_work, reused, len(to_synthesize),
        )
```

Add the `_cluster_is_stale` helper somewhere near the top of `ClusterSynthesizer`:

```python
    def _cluster_is_stale(self, member_node_ids: List[str]) -> bool:
        if self.changeset is None:
            return True
        for nid in member_node_ids:
            file_path = nid[len("file:"):] if nid.startswith("file:") else nid
            if file_path in self.changeset.modified or file_path in self.changeset.deleted:
                return True
        return False
```

- [ ] **Step 5: Implement — make `ClusterSynthesizer` a Worker**

In `src/prep/core/cluster.py`, at the `ClusterSynthesizer` class definition, change:

```python
class ClusterSynthesizer:
```

to:

```python
from prep.services.pipeline.workers.base import Worker

class ClusterSynthesizer(Worker):
```

(Move the Worker import to the top imports of the file alongside other prep imports.)

- [ ] **Step 6: Implement — inject changeset in `_cluster_worker`**

In `src/prep/services/pipeline/workers/__init__.py:798-843`, replace:

```python
            synthesizer = ClusterSynthesizer(
                llm=llm_client,
                index_dir=idx_dir,
                batch_profile=batch_profile,
                project_id=project_id,
            )
            result = synthesizer.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
```

with:

```python
            synthesizer = ClusterSynthesizer(
                llm=llm_client,
                index_dir=idx_dir,
                batch_profile=batch_profile,
                project_id=project_id,
            )
            # Phase 135: inject the Changeset. `worker` is the inner-closure
            # self-reference (Task 0 set base_worker.changeset).
            synthesizer.changeset = getattr(worker, "changeset", None)
            result = synthesizer.run(progress_callback=log_cb, cancel_token=slot.cancel_token)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase135_cluster_changeset.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Run Phase 134 suite**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q`
Expected: 55 passed.

- [ ] **Step 9: Commit**

```bash
git add tests/test_phase135_cluster_changeset.py \
        src/prep/core/cluster.py \
        src/prep/services/pipeline/workers/__init__.py
git commit -m "feat(phase135): stage 8 clustering consults Changeset, fingerprint deleted"
```

---

## Task 3 — Stage 10 (deep_knowledge) changeset cutover

**Files:**
- Modify: `src/prep/core/knowledge.py` (gate the deep path's reuse on the changeset; inherit `Worker`)
- Modify: `src/prep/services/pipeline/workers/__init__.py:584-644` (inject changeset on `is_deep=True` path)
- Test: `tests/test_phase135_deep_knowledge_changeset.py` (new)

**Note on stage 5 vs stage 10 split:** Stage 5 (`is_deep=False`) is out of scope. The `KnowledgeIndex.build` code path is shared, so the changeset gating must be conditional on a per-instance flag that the worker sets only for the deep path. Approach: add `self.use_changeset: bool = False` default; worker sets `idx.use_changeset = True` for the deep call only.

- [ ] **Step 1: Write the failing test**

Create `tests/test_phase135_deep_knowledge_changeset.py`:

```python
"""Phase 135 — stage 10 (deep_knowledge) consults the Changeset.

Stage 5 (is_deep=False) is unaffected — same code path, but the worker
only sets `use_changeset=True` on the deep call.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.knowledge import KnowledgeIndex
from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def idx(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)
    return KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")


def test_index_inherits_worker(idx: KnowledgeIndex) -> None:
    from prep.services.pipeline.workers.base import Worker
    assert isinstance(idx, Worker)


def test_index_has_changeset_attribute(idx: KnowledgeIndex) -> None:
    assert idx.changeset is None
    assert idx.use_changeset is False  # default = stage 5 behavior


def test_should_process_routes_through_changeset(idx: KnowledgeIndex) -> None:
    idx.changeset = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset({"c.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert idx.should_process("a.py") is True
    assert idx.should_process("d.py") is False


def test_deep_path_skips_content_hash_compare(idx: KnowledgeIndex) -> None:
    """When use_changeset=True, _load_previous_for_reuse must NOT
    populate content_hash in the reuse_map values — reuse decisions
    come from the changeset, not from hash equality."""
    # Pre-populate disk state to trigger the reuse path
    import numpy as np
    import json
    docs = [{"id": "know:aug:file:foo.py", "content": "x"}]
    idx.docs_path.parent.mkdir(parents=True, exist_ok=True)
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.array([[0.0] * 8], dtype=np.float32))

    idx.use_changeset = True
    reuse_map = idx._load_previous_for_reuse()
    # Phase 135: deep path's reuse_map values carry just the vector,
    # not (content_hash, vector). When use_changeset is True, the
    # method returns {doc_id: vector} directly.
    assert "know:aug:file:foo.py" in reuse_map
    val = reuse_map["know:aug:file:foo.py"]
    # Either a numpy array directly, or a 1-tuple — either way, not a 2-tuple of (hash, vec)
    assert not (isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], str))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase135_deep_knowledge_changeset.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement — make `KnowledgeIndex` inherit Worker**

In `src/prep/core/knowledge.py`, top of file (after existing prep imports):

```python
from prep.services.pipeline.workers.base import Worker
```

Change line 33:

```python
class KnowledgeIndex:
```

to:

```python
class KnowledgeIndex(Worker):
```

In `__init__`, after the existing field assignments, add:

```python
        # Phase 135: stage 5 (initial) uses the legacy content-hash
        # reuse path; stage 10 (deep) uses the changeset.
        # Worker also adds self.changeset = None.
        self.use_changeset: bool = False
```

- [ ] **Step 4: Implement — branch `_load_previous_for_reuse` on `use_changeset`**

In `src/prep/core/knowledge.py:240-271`, replace `_load_previous_for_reuse` with:

```python
    def _load_previous_for_reuse(self):
        """Return prior embeddings keyed by doc_id.

        Phase 135: shape depends on `self.use_changeset`.
        - False (stage 5): returns {doc_id: (content_hash, vector)} —
          legacy path with content-hash compare.
        - True  (stage 10): returns {doc_id: vector} — reuse decision
          comes from the changeset, not hash equality.
        """
        # Reset barrier check — unchanged from before.
        if is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Knowledge reuse blocked by reset barrier for project %s",
                self.project_id,
            )
            return {}

        prev_docs = self._documents
        prev_emb = self._embeddings

        if (prev_docs is None or prev_emb is None) and self.docs_path.exists() and self.emb_path.exists():
            try:
                with open(self.docs_path, "r", encoding="utf-8") as f:
                    prev_docs = json.load(f)
                prev_emb = np.load(self.emb_path)
                logger.info("Cold-start incremental: loaded %d previous knowledge docs for reuse", len(prev_docs))
            except Exception as e:
                logger.warning("Failed to load previous knowledge index for reuse: %s", e)
                return {}

        if not prev_docs or prev_emb is None or len(prev_docs) != prev_emb.shape[0]:
            return {}

        if self.use_changeset:
            # Stage 10: no hash compare — return {doc_id: vector}.
            return {
                doc.get("id", ""): prev_emb[i]
                for i, doc in enumerate(prev_docs)
                if doc.get("id")
            }

        # Stage 5 (legacy): return {doc_id: (content_hash, vector)}.
        reuse_map: Dict[str, tuple] = {}
        for i, doc in enumerate(prev_docs):
            doc_id = doc.get("id", "")
            content = doc.get("content", "")
            if doc_id and content:
                reuse_map[doc_id] = (self._content_hash(content), prev_emb[i])
        return reuse_map
```

- [ ] **Step 5: Implement — branch the reuse decision in `build()` on `use_changeset`**

In `src/prep/core/knowledge.py`, at the per-doc classification loop around line 447-458, replace:

```python
        for i, doc in enumerate(docs):
            doc_id = doc.get("id", "")
            content = doc.get("content", "")
            content_hash = self._content_hash(content)

            if can_reuse and doc_id in reuse_map:
                prev_hash, prev_vec = reuse_map[doc_id]
                if prev_hash == content_hash:
                    reused_vectors[i] = prev_vec
                    continue

            docs_to_embed.append(i)
```

with:

```python
        for i, doc in enumerate(docs):
            doc_id = doc.get("id", "")
            content = doc.get("content", "")

            if can_reuse and doc_id in reuse_map:
                if self.use_changeset:
                    # Phase 135: stage 10 trusts the changeset. If the
                    # doc's underlying file is unchanged, reuse the
                    # cached vector unconditionally — no hash compare.
                    file_path = self._file_path_for_doc_id(doc_id)
                    if file_path and not self.should_process(file_path):
                        reused_vectors[i] = reuse_map[doc_id]  # plain vector in deep mode
                        continue
                else:
                    # Stage 5: legacy content-hash compare.
                    prev_hash, prev_vec = reuse_map[doc_id]
                    content_hash = self._content_hash(content)
                    if prev_hash == content_hash:
                        reused_vectors[i] = prev_vec
                        continue

            docs_to_embed.append(i)
```

Add the helper at the bottom of the `KnowledgeIndex` class:

```python
    @staticmethod
    def _file_path_for_doc_id(doc_id: str) -> str:
        """Extract the underlying file path from a knowledge doc_id.

        Doc IDs are constructed as:
          - know:aug:{node_id}        → node_id = "file:<rel_path>"
          - know:epistemic:{node_id}  → node_id = "file:<rel_path>"
          - know:module:{module_id}   → module IDs do not map to a file;
                                         return "" (caller treats as "always re-embed")
        """
        if doc_id.startswith("know:aug:") or doc_id.startswith("know:epistemic:"):
            tail = doc_id.split(":", 2)[2]  # strip "know:aug:" / "know:epistemic:"
            if tail.startswith("file:"):
                return tail[len("file:"):]
        return ""
```

(Module docs — `know:module:...` — get `""` from this helper, which means `should_process("")` is False but the caller path is gated on `file_path and not self.should_process(...)`. Empty-path module docs fall through to `docs_to_embed.append(i)`. That preserves the legacy behavior: modules re-embed each deep run, which is correct because clustering may have produced new module IDs.)

- [ ] **Step 6: Implement — inject changeset and `use_changeset=True` in `_knowledge_worker` deep path**

In `src/prep/services/pipeline/workers/__init__.py:636-637`, replace:

```python
            idx = build_manager.get_project_knowledge_index(project)
            result = idx.build(progress_callback=cb_to_use)
```

with:

```python
            idx = build_manager.get_project_knowledge_index(project)
            if is_deep:
                # Phase 135: stage 10 trusts the Changeset for reuse decisions.
                # `worker` is the inner-closure self-reference (Task 0 set
                # base_worker.changeset; this name is in scope here).
                idx.use_changeset = True
                idx.changeset = getattr(worker, "changeset", None)
            result = idx.build(progress_callback=cb_to_use)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase135_deep_knowledge_changeset.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Run Phase 134 suite**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q`
Expected: 55 passed.

- [ ] **Step 9: Commit**

```bash
git add tests/test_phase135_deep_knowledge_changeset.py \
        src/prep/core/knowledge.py \
        src/prep/services/pipeline/workers/__init__.py
git commit -m "feat(phase135): stage 10 deep_knowledge consults Changeset, hash compare deleted"
```

---

## Task 4 — Static-grep guards

**Files:**
- Test: `tests/test_phase135_no_fingerprints.py` (new)

- [ ] **Step 1: Write the test**

Create `tests/test_phase135_no_fingerprints.py`:

```python
"""Phase 135 — static guards: no mid-pipeline fingerprint computation remains.

These tests fail loudly if anyone re-introduces the deleted pattern.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "prep" / "core"


def _read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_group_reasoning_no_fingerprint_compute() -> None:
    body = _read("group_reasoning.py")
    assert "compute_group_fingerprint" not in body
    assert "member_fingerprint" not in body


def test_cluster_no_fingerprint_compute() -> None:
    body = _read("cluster.py")
    assert "_cluster_fingerprint" not in body
    assert "fp_to_module" not in body


def test_knowledge_deep_path_no_inline_hash_compare() -> None:
    """The legacy `prev_hash == content_hash` compare must only appear
    inside the use_changeset=False (stage 5) branch — not at the top
    level of the docs loop."""
    body = _read("knowledge.py")
    # The compare itself still exists for stage 5; ensure it's gated.
    # If the gate phrase disappears, the cutover regressed.
    assert "if self.use_changeset:" in body, "Stage 5/10 split gate missing"
```

- [ ] **Step 2: Run and pass**

Run: `.venv/bin/pytest tests/test_phase135_no_fingerprints.py -v`
Expected: PASS (3 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase135_no_fingerprints.py
git commit -m "test(phase135): static guards against fingerprint regression"
```

---

## Task 5 — Stage 5 unaffected guard

**Files:**
- Test: `tests/test_phase135_stage5_unaffected.py` (new)

- [ ] **Step 1: Write the test**

Create `tests/test_phase135_stage5_unaffected.py`:

```python
"""Phase 135 — stage 5 (knowledge, is_deep=False) must keep its
legacy content-hash reuse behavior. Stage 10 overwrites stage 5's
output anyway; rearchitecting stage 5 would add risk for no benefit."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from prep.core.knowledge import KnowledgeIndex


@pytest.fixture
def idx(tmp_path: Path) -> KnowledgeIndex:
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)
    return KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")


def test_default_use_changeset_is_false(idx: KnowledgeIndex) -> None:
    """Stage 5 callers don't touch use_changeset — must default False."""
    assert idx.use_changeset is False


def test_stage5_reuse_map_uses_content_hash(idx: KnowledgeIndex) -> None:
    """With use_changeset=False, reuse_map values must be (hash, vector) tuples."""
    docs = [{"id": "know:aug:file:foo.py", "content": "hello"}]
    idx.docs_path.parent.mkdir(parents=True, exist_ok=True)
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.array([[0.0] * 8], dtype=np.float32))

    assert idx.use_changeset is False
    reuse_map = idx._load_previous_for_reuse()
    val = reuse_map.get("know:aug:file:foo.py")
    assert isinstance(val, tuple)
    assert len(val) == 2
    assert isinstance(val[0], str)  # the content hash
```

- [ ] **Step 2: Run and pass**

Run: `.venv/bin/pytest tests/test_phase135_stage5_unaffected.py -v`
Expected: PASS (2 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase135_stage5_unaffected.py
git commit -m "test(phase135): stage 5 (is_deep=False) keeps legacy hash reuse"
```

---

## Task 6 — Worker injection integration test

**Files:**
- Test: `tests/test_phase135_worker_injection.py` (new)

- [ ] **Step 1: Write the test**

Create `tests/test_phase135_worker_injection.py`:

```python
"""Phase 135 — verify the three workers attach Changeset before invoking
their engine. Uses monkeypatching to inspect what's set on engine
instances at worker invocation time."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def fake_changeset() -> Changeset:
    return Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"c.py"}),
        run_id="r1",
        base_run_id=None,
    )


def test_group_reasoning_worker_injects_changeset(fake_changeset: Changeset) -> None:
    """_group_reasoning_worker attaches the Changeset to the engine
    instance before calling .run()."""
    from prep.services.pipeline.workers import WorkerFactory

    captured: dict = {}

    def fake_run(self, *args, **kwargs):
        captured["changeset"] = self.changeset
        return {"analyzed": 0, "reused": 0, "failed": 0}

    with patch("prep.core.group_reasoning.GroupReasoningEngine.run", fake_run), \
         patch("prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task") as mock_llm, \
         patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config") as mock_proj:
        mock_llm.return_value = MagicMock(model="x", provider="x")
        mock_proj.return_value = (MagicMock(name="p", config={}), {}, [], [], 0, 0, 0, 0, 0)

        worker_fn = WorkerFactory._group_reasoning_worker("proj1")
        # Simulate the closure attribute set by _build_worker:
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert captured["changeset"] is fake_changeset


def test_cluster_worker_injects_changeset(fake_changeset: Changeset) -> None:
    """_cluster_worker attaches the Changeset to ClusterSynthesizer."""
    from prep.services.pipeline.workers import WorkerFactory

    captured: dict = {}

    def fake_run(self, *args, **kwargs):
        captured["changeset"] = self.changeset
        return {"synthesized": 0, "reused": 0, "failed": 0}

    with patch("prep.core.cluster.ClusterSynthesizer.run", fake_run), \
         patch("prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task") as mock_llm, \
         patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config") as mock_proj:
        mock_llm.return_value = MagicMock(model="x", provider="x")
        mock_proj.return_value = (MagicMock(name="p", config={}), {}, [], [], 0, 0, 0, 0, 0)

        worker_fn = WorkerFactory._cluster_worker("proj1")
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert captured["changeset"] is fake_changeset


def test_deep_knowledge_worker_injects_changeset_and_use_flag(fake_changeset: Changeset) -> None:
    """_knowledge_worker with is_deep=True attaches Changeset AND sets
    use_changeset=True. The is_deep=False path does neither."""
    from prep.services.pipeline.workers import WorkerFactory

    captured: dict = {}

    def fake_build(self, *args, **kwargs):
        captured["use_changeset"] = self.use_changeset
        captured["changeset"] = self.changeset
        return {"count": 0, "status": "empty"}

    fake_idx = MagicMock()
    fake_idx.use_changeset = False
    fake_idx.changeset = None
    fake_idx.build.side_effect = lambda *a, **kw: fake_build(fake_idx, *a, **kw)

    with patch("prep.services.build_manager.build_manager.get_project_knowledge_index", return_value=fake_idx), \
         patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config") as mock_proj:
        mock_proj.return_value = (MagicMock(name="p", config={}), {}, [], [], 0, 0, 0, 0, 0)

        worker_fn = WorkerFactory._knowledge_worker("proj1", is_deep=True)
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert fake_idx.use_changeset is True
    assert fake_idx.changeset is fake_changeset
```

- [ ] **Step 2: Run and pass**

Run: `.venv/bin/pytest tests/test_phase135_worker_injection.py -v`
Expected: PASS (3 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase135_worker_injection.py
git commit -m "test(phase135): worker injection of Changeset into the three engines"
```

---

## Task 7 — End-to-end smoke

**Files:**
- Test: `tests/test_phase135_e2e_no_change_zero_work.py` (new)

This test verifies the full architectural goal: when nothing has changed,
stages 7, 8, and 10 do zero LLM-bound work.

- [ ] **Step 1: Write the test**

Create `tests/test_phase135_e2e_no_change_zero_work.py`:

```python
"""Phase 135 — E2E: on a rebuild where stage 1 emits an all-unchanged
changeset, stages 7/8/10 reuse 100% and call the LLM zero times.

This is the goal of the entire phase: 'nothing becomes stale mid-process,
so just run the pipeline.'"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def all_unchanged_changeset() -> Changeset:
    return Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"foo.py", "bar.py"}),
        run_id="r2",
        base_run_id="r1",
    )


def test_group_reasoning_zero_work_on_no_change(all_unchanged_changeset: Changeset, tmp_path: Path) -> None:
    """All-unchanged changeset → every group reused → zero LLM calls."""
    from prep.core.group_reasoning import GroupReasoningEngine, GroupReasoningEntry

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"

    engine = GroupReasoningEngine(llm=llm, index_dir=tmp_path, project_id="p1")
    engine.changeset = all_unchanged_changeset

    members = ["file:foo.py", "file:bar.py"]
    assert engine._group_is_stale(members) is False


def test_cluster_zero_work_on_no_change(all_unchanged_changeset: Changeset, tmp_path: Path) -> None:
    from prep.core.cluster import ClusterSynthesizer

    llm = MagicMock()
    llm.model = "test"
    llm.provider = "test"

    synth = ClusterSynthesizer(
        llm=llm, index_dir=tmp_path, batch_profile=None, project_id="p1",
    )
    synth.changeset = all_unchanged_changeset

    assert synth._cluster_is_stale(["file:foo.py", "file:bar.py"]) is False


def test_deep_knowledge_zero_work_on_no_change(all_unchanged_changeset: Changeset, tmp_path: Path) -> None:
    """All-unchanged changeset → every doc reused, no embedder calls."""
    import json
    import numpy as np
    from prep.core.knowledge import KnowledgeIndex

    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed.return_value = MagicMock(vector=[0.0] * 8)

    # Pre-seed the on-disk index with two docs.
    idx = KnowledgeIndex(index_dir=tmp_path, embedder=embedder, project_id="p1")
    docs = [
        {"id": "know:aug:file:foo.py", "type": "catalogue", "source_id": "file:foo.py",
         "content": "summary of foo", "metadata": {}},
        {"id": "know:aug:file:bar.py", "type": "catalogue", "source_id": "file:bar.py",
         "content": "summary of bar", "metadata": {}},
    ]
    idx.docs_path.write_text(json.dumps(docs))
    np.save(idx.emb_path, np.zeros((2, 8), dtype=np.float32))
    idx._load()  # reload from disk

    idx.use_changeset = True
    idx.changeset = all_unchanged_changeset

    # Place a trace_augmented.jsonl so build() finds inputs:
    aug_path = tmp_path / "trace_augmented.jsonl"
    aug_path.write_text(
        json.dumps({"node_id": "file:foo.py", "role": "code", "summary": "summary of foo"}) + "\n" +
        json.dumps({"node_id": "file:bar.py", "role": "code", "summary": "summary of bar"}) + "\n"
    )

    with patch.object(idx, "_embedder_model", return_value="test-embed"):
        result = idx.build(progress_callback=None)

    embedder.embed.assert_not_called()
    assert result.get("count", 0) == 2
```

- [ ] **Step 2: Run and pass**

Run: `.venv/bin/pytest tests/test_phase135_e2e_no_change_zero_work.py -v`
Expected: PASS (3 tests).

- [ ] **Step 3: Run the whole Phase 135 suite**

Run: `.venv/bin/pytest tests/test_phase135_*.py -v`
Expected: ~22 tests pass.

- [ ] **Step 4: Run Phase 134 suite (final regression check)**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_deepening.py -q`
Expected: 55 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_phase135_e2e_no_change_zero_work.py
git commit -m "test(phase135): e2e — all-unchanged changeset → zero LLM work in stages 7/8/10"
```

---

## Done criteria

- All 8 tasks (0–7) committed.
- `tests/test_phase135_*.py` all pass (~25 tests).
- `tests/test_phase134_*.py` + `tests/test_deepening.py` still pass (55 tests — no regression).
- Net production diff in the −130 range (Task 0 is roughly neutral; the deletions in Tasks 1–3 dominate).
- `git grep -n "compute_group_fingerprint\|member_fingerprint\|_cluster_fingerprint"` returns nothing.
- `git grep -n "getattr(wrapped_worker"` returns nothing (the Task 0 rename is complete).

## Hand-off

After the implementer subagent completes Task 7, follow superpowers:finishing-a-development-branch — merge to main, restart daemon, live-verify a pipeline run shows zero LLM work on a no-change rebuild for stages 7/8/10.
