# Phase 134 — Changeset-Driven Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete every per-stage staleness check across the enrichment pipeline (augmenter, deepening, epistemic enrichment, epistemic scoring, audit StalenessAnalyzer), replace with a single explicit `Changeset` object emitted by stage 1 and consumed by stages 2-15. Converge the four remaining `os.walk` callers in pipeline-relevant code onto `prep_engine.walk_repo`. Net result: ~600 lines removed, one source of truth for "what changed in this run," cache-invalidation cascade eliminated by construction.

**Architecture:** Stage 1 (TraceBuilder structural) walks via `prep_engine.walk_repo`, hashes via `prep_engine.hash_content`, diffs against the prior `trace_manifest.json::file_hashes`, and emits a `Changeset(added, modified, deleted, unchanged, run_id, base_run_id)` written atomically to `.sourceprep/changeset.json`. `WorkerFactory` reads the Changeset before constructing each downstream stage's worker and injects it via attribute assignment. Workers use `self.changeset.should_process(file_path)` instead of any hash comparison. The manifest stays as the persistent hash store stage 1 needs to compute the next run's diff; the changeset is purely the inter-stage staleness contract.

**Tech Stack:** Python 3.11 (FastAPI/asyncio backend), Rust (PyO3 bindings via `prep_engine`), pytest (asyncio_mode = "auto"), ruff/mypy.

**Read first (the engineer needs this context):**

- The spec: `docs/Phase134_ChangesetDrivenPipeline/README.md` — design rationale, three migration cases, change manifest, success criteria.
- Phase 133's spec and plan: `docs/Phase133_RustWalkerHasherCutover/{README.md,IMPLEMENTATION_PLAN.md}` — establishes context for what this phase is correcting.
- Phase 133's hot-fix commit `889c042b` — the `is_hash_stale` helper this phase deletes.
- The current per-stage staleness sites the engineer will delete:
  - `src/prep/core/augmenter.py:516-530` (`_should_skip` hash compare)
  - `src/prep/core/deepening.py:158-175` (decay_neighbors stale check)
  - `src/prep/core/epistemic_enrichment.py:466-480` (`_is_stale`)
  - `src/prep/core/epistemic_score.py:208-220` (c6 staleness component)
  - `src/prep/core/audit/analyzers/staleness.py:30-58` (the entire file's hash-compare logic)
- The existing `_changed_paths` infrastructure in `src/prep/services/pipeline/orchestrator.py:96, 2452` — Phase 134 generalizes this from "paths to STRUCTURAL only" to "Changeset to ALL workers."
- Project memories: `feedback_no_coauthored_by.md` (no Co-Authored-By trailer), `feedback_use_venv.md` (use `.venv/bin/pytest`), `feedback_test_full_import_chain.md` (at least one test must not mock the seam under test), `feedback_restart_daemon_before_live_validation.md` (daemon has no hot-reload), `feedback_explicit_push_only.md` (commit locally; never push without explicit signal).

**Worktree:** Run this work on a dedicated branch (e.g., `phase-134-changeset-driven-pipeline`) created via `superpowers:using-git-worktrees`. The default branch should remain shippable throughout.

**Net diff target:** −400 lines minimum (spec goal #5). Track this per task; abort to brainstorming reset if mid-implementation the diff trends positive.

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `src/prep/services/pipeline/changeset.py` | **CREATE** (~120 lines) | `Changeset` dataclass + `read_changeset(idx_dir)` + `write_changeset(idx_dir, cs)` |
| `src/prep/core/trace/builder.py` | MODIFY (+50 / −0) | After manifest write, compute & write Changeset (`_emit_changeset` helper). Three migration cases: no manifest / BLAKE3 manifest / SHA-256 manifest. |
| `src/prep/services/pipeline/workers/factory.py` | MODIFY (+20 / −0) | Load changeset once per stage start, inject via `worker.changeset = cs` |
| `src/prep/core/augmenter.py` | MODIFY (+5 / −20) | DELETE `AugmentationEntry.file_hash` field + emission + 524-block hash compare. REPLACE with `if not self.changeset.should_process(path): continue`. |
| `src/prep/core/deepening.py` | MODIFY (+10 / −30) | DELETE `_load_manifest_hashes` (~25 lines) + stale-set hash compare loop (~10 lines). REPLACE with changeset-driven stale_set computation. |
| `src/prep/core/epistemic_enrichment.py` | MODIFY (+5 / −30) | DELETE per-stage manifest hash reads (lines 449, 1365) + per-entry compare (line 475). REPLACE with `should_process` check. |
| `src/prep/core/epistemic_score.py` | MODIFY (+10 / −15) | DELETE c6 staleness check (lines 208-220). Renormalize SCORE_WEIGHTS so the remaining components sum to 1.0. |
| `src/prep/core/audit/analyzers/staleness.py` | REWRITE (~80 → ~50 lines) | Two narrow checks: orphan (deleted files with surviving augmentations), coverage gap (added/modified files the augmenter didn't process). |
| `src/prep/core/trace/coverage.py` | MODIFY (+30 / −180) | DELETE per-file hash compare branch, Path A self-heal, backfill carve-out. REPLACE with changeset read + walker-only diff for "what's new on disk since last run." |
| `src/prep/services/pipeline/resume.py` | MODIFY (+0 / −220) | DELETE entire `refresh_manifest_hashes` method (lines 816-1043). |
| `src/prep/services/pipeline/orchestrator.py` | MODIFY (+0 / −30) | DELETE 3 `refresh_manifest_hashes` call sites (lines 572, 684, 2231). Simplify F-67 backup pattern: keep rename-to-`.f67_pending`, drop the inline restore (changeset is now the inter-stage truth). |
| `src/prep/core/ids.py` | MODIFY (+0 / −45) | DELETE `is_hash_stale` helper (Phase 133 hot-fix, ~45 lines including docstring). |
| `src/prep/core/repo_profile.py` | MODIFY (+10 / −15) | `os.walk` → `prep_engine.walk_repo` at lines 241, 327. |
| `src/prep/core/atlas/markdown_links.py` | MODIFY (+5 / −10) | `os.walk` → `prep_engine.walk_repo` at line 152. |
| `tests/test_phase134_changeset.py` | **CREATE** | Changeset dataclass unit tests |
| `tests/test_phase134_worker_changeset_injection.py` | **CREATE** | WorkerFactory injects changeset; Worker.should_process honors it |
| `tests/test_phase134_migration_cases.py` | **CREATE** | The 3 migration cases (no manifest / BLAKE3 / SHA-256) |
| `tests/test_phase134_stage_cutover.py` | **CREATE** | Per-stage cutover: each of augmenter/deepening/enrichment/score/audit consumes changeset |
| `tests/test_phase134_walker_convergence.py` | **CREATE** | Greps for `os.walk` in pipeline-relevant code; asserts zero hits |
| `tests/test_phase134_e2e_no_llm_recall.py` | **CREATE** | Headline regression: SHA-256 manifest + stub augmentations → zero LLM call sites invoked |
| `docs/MASTER_TODO.md` | MODIFY | Append Phase 134 entry |
| `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` | **CREATE** | Phase 134 dogfooding follow-up: Phase 133 lesson + 3 prep MCP gaps observed during spec phase |

---

## Task ordering

The plan is ordered so each task lands a complete, testable feature increment:

1. Foundation: `Changeset` dataclass + persistence (no behavior change yet)
2. Stage 1 emits the Changeset (the three migration cases work end-to-end)
3. Worker contract: `WorkerFactory` injects changeset (still no consumer change)
4. Augmenter cutover (first downstream consumer migrated)
5. Deepening cutover
6. Epistemic enrichment cutover
7. Epistemic score cutover (c6 deletion + reweighting)
8. Audit StalenessAnalyzer rewrite
9. `compute_trace_coverage` simplification
10. Delete `refresh_manifest_hashes` + 3 orchestrator call sites
11. F-67 backup simplification
12. Delete `is_hash_stale` helper (last 5 callers gone after tasks 4-8)
13-15. Walker convergence: repo_profile.py, builder._enumerate_files, atlas/markdown_links
16. End-to-end migration smoke test (proves the cascade is dead)
17. Walker-convergence guard test
18. Doc closes: MASTER_TODO + dogfooding follow-up

Each task ends with a commit. Each commit is bisectable, revertable.

---

### Task 1: Add `Changeset` dataclass and persistence

**Files:**
- Create: `src/prep/services/pipeline/changeset.py`
- Test: `tests/test_phase134_changeset.py` (new)

This task is foundation-only: no behavior change anywhere else. It introduces the `Changeset` type and disk persistence helpers that subsequent tasks will use.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_phase134_changeset.py`:

```python
"""Phase 134 — Changeset dataclass and persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.services.pipeline.changeset import (
    Changeset,
    read_changeset,
    write_changeset,
)


def test_changeset_should_process_added():
    cs = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"b.py"}),
        run_id="run-1",
        base_run_id=None,
    )
    assert cs.should_process("a.py") is True


def test_changeset_should_process_modified():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"a.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("b.py") is True


def test_changeset_should_not_process_unchanged():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset({"a.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("a.py") is False


def test_changeset_should_not_process_deleted():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset({"old.py"}),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.should_process("old.py") is False


def test_changeset_should_not_process_unknown():
    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    assert cs.should_process("never-seen.py") is False


def test_changeset_all_known_excludes_deleted():
    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset({"gone.py"}),
        unchanged=frozenset({"same.py"}),
        run_id="run-1",
        base_run_id="run-0",
    )
    assert cs.all_known() == frozenset({"new.py", "changed.py", "same.py"})
    assert "gone.py" not in cs.all_known()


def test_write_and_read_round_trip(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"a.py", "b.py"}),
        modified=frozenset({"c.py"}),
        deleted=frozenset({"old.py"}),
        unchanged=frozenset({"d.py"}),
        run_id="run-abc123",
        base_run_id="run-def456",
    )
    write_changeset(idx, cs)
    loaded = read_changeset(idx)
    assert loaded == cs


def test_read_changeset_returns_none_when_absent(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    assert read_changeset(idx) is None


def test_read_changeset_returns_none_when_malformed(tmp_path: Path):
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "changeset.json").write_text("not valid json{{{")
    assert read_changeset(idx) is None


def test_write_changeset_atomic_via_tempfile(tmp_path: Path):
    """Atomic write: a crash mid-write must leave the prior changeset intact."""
    idx = tmp_path / "index"
    idx.mkdir()
    # Pre-existing valid changeset
    cs1 = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    write_changeset(idx, cs1)
    # Overwrite with new one — must succeed atomically
    cs2 = Changeset(
        added=frozenset(),
        modified=frozenset({"a.py"}),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-2",
        base_run_id="run-1",
    )
    write_changeset(idx, cs2)
    loaded = read_changeset(idx)
    assert loaded.run_id == "run-2"


def test_serialized_format_uses_sorted_lists(tmp_path: Path):
    """Sets serialize to sorted lists for deterministic JSON output
    (helps with diffing changeset.json across runs in test fixtures
    and in debugging)."""
    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"z.py", "a.py", "m.py"}),
        modified=frozenset(),
        deleted=frozenset(),
        unchanged=frozenset(),
        run_id="run-1",
        base_run_id=None,
    )
    write_changeset(idx, cs)
    raw = json.loads((idx / "changeset.json").read_text())
    assert raw["added"] == ["a.py", "m.py", "z.py"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase134_changeset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prep.services.pipeline.changeset'`.

- [ ] **Step 3: Implement `changeset.py`**

Create `src/prep/services/pipeline/changeset.py`:

```python
"""Phase 134 — the Changeset object and its disk persistence.

The Changeset is the SINGLE inter-stage artifact for "what changed in
this pipeline run." Stage 1 (TraceBuilder structural) emits one
Changeset per run by diffing the prior trace_manifest's file_hashes
against the fresh walk's hashes. WorkerFactory loads it once at stage
start and injects it into every downstream worker. Workers use
should_process(path) — no per-stage hash comparison exists post-Phase-134.

The Phase 134 spec at docs/Phase134_ChangesetDrivenPipeline/README.md
explains why this exists. Short version: Phase 133 left six
independent staleness-check sites that all derived "what changed"
from hashes — a hash format change invalidated all six caches
simultaneously and triggered a full LLM re-run on unchanged content.
This object centralizes the truth so the cascade can't recur.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional


CHANGESET_FILENAME = "changeset.json"
CHANGESET_VERSION = 1


@dataclass(frozen=True)
class Changeset:
    """The single source of truth for 'what changed in this pipeline run.'

    Emitted by stage 1 (structural). Read by every downstream stage
    via WorkerFactory injection. Persisted to .sourceprep/changeset.json
    so it survives daemon restarts mid-run.
    """
    added:       FrozenSet[str]   # files new since base_run_id
    modified:    FrozenSet[str]   # files whose content changed
    deleted:     FrozenSet[str]   # files in base_run, no longer present
    unchanged:   FrozenSet[str]   # everything else (carry forward)
    run_id:      str              # this pipeline run's ID (matches journal)
    base_run_id: Optional[str]    # prior run we diffed against; None on first build

    def should_process(self, file_path: str) -> bool:
        """Return True iff a stage worker should run on this file in
        this run. Files in `unchanged` skip processing (carry-forward
        augmentation entries as-is); files in `deleted` are handled
        by the post-stage cleanup pass; everything in `added` or
        `modified` is fair game."""
        return file_path in self.added or file_path in self.modified

    def all_known(self) -> FrozenSet[str]:
        """Union of added | modified | unchanged — every file the
        pipeline knows about for this run. `deleted` is intentionally
        excluded (no longer present, not 'known' for downstream
        consumers' purposes). Used by the audit orphan check."""
        return self.added | self.modified | self.unchanged


def read_changeset(idx_dir: Path) -> Optional[Changeset]:
    """Load the changeset from idx_dir/changeset.json. Returns None
    if the file is absent or malformed (caller decides fallback)."""
    path = Path(idx_dir) / CHANGESET_FILENAME
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return Changeset(
            added=frozenset(raw.get("added") or []),
            modified=frozenset(raw.get("modified") or []),
            deleted=frozenset(raw.get("deleted") or []),
            unchanged=frozenset(raw.get("unchanged") or []),
            run_id=str(raw.get("run_id") or ""),
            base_run_id=raw.get("base_run_id"),
        )
    except (TypeError, ValueError):
        return None


def write_changeset(idx_dir: Path, cs: Changeset) -> None:
    """Atomic write of the changeset to idx_dir/changeset.json via
    tempfile + rename. A crash mid-write leaves the prior changeset
    on disk (or no file at all if first write)."""
    path = Path(idx_dir) / CHANGESET_FILENAME
    payload = {
        "version": CHANGESET_VERSION,
        "run_id": cs.run_id,
        "base_run_id": cs.base_run_id,
        "added": sorted(cs.added),
        "modified": sorted(cs.modified),
        "deleted": sorted(cs.deleted),
        "unchanged": sorted(cs.unchanged),
    }
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=str(idx_dir),
        delete=False, encoding="utf-8",
    )
    try:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_changeset.py -v`
Expected: 11 PASSED.

- [ ] **Step 5: Lint check**

Run: `.venv/bin/ruff check src/prep/services/pipeline/changeset.py tests/test_phase134_changeset.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/changeset.py tests/test_phase134_changeset.py
git commit -m "feat(phase134): add Changeset dataclass + disk persistence

The Changeset is the single inter-stage artifact for 'what changed
in this run'. Stage 1 will emit it (Task 2); WorkerFactory will
inject it into downstream workers (Task 3); per-stage staleness
checks will be deleted in favor of self.changeset.should_process(path)
(Tasks 4-8). This task is foundation-only — no behavior change."
```

---

### Task 2: Stage 1 emits the Changeset (three migration cases)

**Files:**
- Modify: `src/prep/core/trace/builder.py` — after manifest write in `_build_python` (~line 358) and `_build_rust` (~line 460), compute and write the changeset.
- Test: `tests/test_phase134_migration_cases.py` (new)

This task makes stage 1 emit the changeset for all three migration cases described in the spec: never-built (Case 1), Phase-133+ BLAKE3 manifest (Case 2), pre-Phase-133 SHA-256 manifest or no `hash_algo` field (Case 3 — the trust-prior-work case).

- [ ] **Step 1: Read the current builder structure**

Run: `grep -n "self._write_manifest\|file_hashes\|hash_algo\|build()" src/prep/core/trace/builder.py | head -30`
Expected: locate `_build_python` and `_build_rust` write sites, the `build()` entry point, and the manifest hash fields.

- [ ] **Step 2: Write the failing migration tests**

Create `tests/test_phase134_migration_cases.py`:

```python
"""Phase 134 — Stage 1 emits the Changeset for all three migration cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from prep.services.pipeline.changeset import read_changeset
from prep.core.trace.builder import TraceBuilder


def _has_prep_engine() -> bool:
    try:
        import prep_engine  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_prep_engine(),
    reason="prep_engine PyO3 binding not built; stage 1 cannot run without it",
)


@pytest.fixture
def small_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    (repo / "util.py").write_text("def util(): return 1\n")
    idx = tmp_path / "index"
    idx.mkdir()
    return repo, idx


def _build_via_python(repo: Path, idx: Path, monkeypatch):
    """Force the Python build path for deterministic test behavior."""
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()
    return builder


def test_case1_never_built_emits_added_everything(small_repo, monkeypatch):
    """Case 1: project has no prior manifest. Changeset added=everything,
    modified/deleted/unchanged all empty. base_run_id is None."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)

    cs = read_changeset(idx)
    assert cs is not None, "stage 1 must emit a changeset on every build"
    assert cs.added == frozenset({"main.py", "util.py"}), (
        f"Case 1 added must include every walked file; got {cs.added}"
    )
    assert cs.modified == frozenset()
    assert cs.deleted == frozenset()
    assert cs.unchanged == frozenset()
    assert cs.base_run_id is None


def test_case2_blake3_manifest_real_diff(small_repo, monkeypatch):
    """Case 2: prior manifest has hash_algo='blake3-128'. Stage 1
    does a real hash diff. Files unchanged stay in unchanged; one
    file modified moves to modified."""
    repo, idx = small_repo
    # First build: establishes a Phase-133+ manifest
    _build_via_python(repo, idx, monkeypatch)
    cs1 = read_changeset(idx)
    assert cs1 is not None

    # Modify one file
    (repo / "main.py").write_text("def main(): return 'changed'\n")

    # Second build: real diff
    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert cs2 is not None
    assert "main.py" in cs2.modified
    assert "util.py" in cs2.unchanged
    assert cs2.added == frozenset()
    assert cs2.deleted == frozenset()
    assert cs2.base_run_id == cs1.run_id


def test_case2_added_and_deleted(small_repo, monkeypatch):
    """Case 2 with file additions/deletions in addition to modifications."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)

    # Add a file, delete a file
    (repo / "new.py").write_text("def new(): pass\n")
    (repo / "util.py").unlink()

    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert "new.py" in cs2.added
    assert "util.py" in cs2.deleted
    assert "main.py" in cs2.unchanged


def test_case3_pre_phase133_manifest_trusts_prior_work(small_repo, monkeypatch):
    """Case 3: prior manifest has hash_algo absent or 'sha256-64'
    (pre-Phase-133). Stage 1 cannot meaningfully diff SHA-256 vs
    BLAKE3, so it emits the migration changeset:
        unchanged = {everything in prior manifest still on disk}
        added = {files on disk NOT in prior manifest}
        modified = {} (we cannot tell)
        deleted = {files in prior manifest no longer on disk}
    This UNCONDITIONALLY trusts the prior augmentation work — the
    cache invalidation cascade Phase 133's hot-fix patched is dead
    by construction."""
    repo, idx = small_repo

    # Hand-craft a pre-Phase-133 manifest: SHA-256-64 hashes, no hash_algo.
    sha_main = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    sha_util = hashlib.sha256(b"def util(): return 1\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1.0",
        "built_at": "2026-04-01T00:00:00Z",
        # NO hash_algo field — this is the legacy state
        "file_hashes": {"main.py": sha_main, "util.py": sha_util},
    }))
    # Also seed a trace_nodes file so the build doesn't think this is
    # a never-built project (Case 1 detection).
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n" +
        json.dumps({"kind": "file", "file_path": "util.py", "id": "file:util.py"}) + "\n"
    )

    # Add one new file, delete nothing — to make the migration's
    # add/delete handling distinguishable from "everything unchanged."
    (repo / "new_after_phase133.py").write_text("def new(): pass\n")

    _build_via_python(repo, idx, monkeypatch)

    cs = read_changeset(idx)
    assert cs is not None

    # The headline assertion: existing manifest entries enter
    # `unchanged`, NOT `modified`. This preserves the user's hours
    # of LLM work.
    assert "main.py" in cs.unchanged, (
        "Case 3 must put pre-Phase-133 manifest entries in `unchanged` "
        "to preserve prior augmentation work; got modified={}, unchanged={}"
        .format(cs.modified, cs.unchanged)
    )
    assert "util.py" in cs.unchanged
    # New files enter `added` normally.
    assert "new_after_phase133.py" in cs.added
    # `modified` is intentionally empty in Case 3 (we cannot tell
    # which files actually changed without comparable hashes).
    assert cs.modified == frozenset()


def test_case3_deletes_files_no_longer_on_disk(small_repo, monkeypatch):
    """Case 3 still detects deletes — files in the prior manifest
    that are gone from disk go into `deleted`, not `unchanged`."""
    repo, idx = small_repo

    # Pre-Phase-133 manifest references util.py
    sha_main = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    sha_util = hashlib.sha256(b"def util(): return 1\n").hexdigest()[:16]
    sha_gone = hashlib.sha256(b"deleted").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1.0",
        "file_hashes": {
            "main.py": sha_main,
            "util.py": sha_util,
            "removed_long_ago.py": sha_gone,  # not on disk
        },
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    _build_via_python(repo, idx, monkeypatch)
    cs = read_changeset(idx)
    assert "removed_long_ago.py" in cs.deleted
    assert "removed_long_ago.py" not in cs.unchanged
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase134_migration_cases.py -v`
Expected: FAIL — stage 1 doesn't write changeset.json yet.

- [ ] **Step 4: Add the `_emit_changeset` helper to TraceBuilder**

Edit `src/prep/core/trace/builder.py`. After the existing `_build_manifest` instance method (around line 593), add:

```python
def _emit_changeset(
    self,
    new_file_hashes: Dict[str, str],
    prior_manifest: Optional[Dict[str, Any]],
    run_id: str,
) -> None:
    """Phase 134: compute and write .sourceprep/changeset.json by
    diffing this build's file_hashes against the prior manifest.

    Three cases:
    - Case 1 (no prior manifest): added = everything, others empty
    - Case 2 (prior manifest has matching hash_algo): real diff
    - Case 3 (prior manifest has mismatched/absent hash_algo):
      unchanged = {prior manifest paths still on disk},
      added = {new paths not in prior manifest},
      modified = {} (cannot meaningfully compare SHA-256 vs BLAKE3),
      deleted = {prior manifest paths no longer on disk}

    See docs/Phase134_ChangesetDrivenPipeline/README.md for rationale.
    """
    from prep.services.pipeline.changeset import Changeset, write_changeset
    from prep.core.manifest import CURRENT_HASH_ALGO

    new_paths = frozenset(new_file_hashes.keys())

    if prior_manifest is None:
        cs = Changeset(
            added=new_paths,
            modified=frozenset(),
            deleted=frozenset(),
            unchanged=frozenset(),
            run_id=run_id,
            base_run_id=None,
        )
        write_changeset(self.index_dir, cs)
        return

    prior_hashes: Dict[str, str] = prior_manifest.get("file_hashes") or {}
    prior_paths = frozenset(prior_hashes.keys())
    prior_algo = prior_manifest.get("hash_algo")
    base_run_id = prior_manifest.get("run_id")  # may be None on Case 3

    if prior_algo == CURRENT_HASH_ALGO:
        # Case 2: real hash diff
        added = new_paths - prior_paths
        deleted = prior_paths - new_paths
        common = new_paths & prior_paths
        modified: set[str] = set()
        unchanged: set[str] = set()
        for path in common:
            if new_file_hashes[path] == prior_hashes[path]:
                unchanged.add(path)
            else:
                modified.add(path)
        cs = Changeset(
            added=frozenset(added),
            modified=frozenset(modified),
            deleted=frozenset(deleted),
            unchanged=frozenset(unchanged),
            run_id=run_id,
            base_run_id=base_run_id,
        )
        write_changeset(self.index_dir, cs)
        return

    # Case 3: hash format mismatch — trust prior work unconditionally.
    # Files in prior manifest that still exist enter `unchanged`;
    # files no longer on disk enter `deleted`; new files enter
    # `added`; `modified` is intentionally empty.
    common_alive = frozenset(p for p in prior_paths if p in new_paths)
    deleted_paths = prior_paths - new_paths
    added_paths = new_paths - prior_paths
    cs = Changeset(
        added=added_paths,
        modified=frozenset(),
        deleted=deleted_paths,
        unchanged=common_alive,
        run_id=run_id,
        base_run_id=base_run_id,
    )
    write_changeset(self.index_dir, cs)
```

- [ ] **Step 5: Wire `_emit_changeset` into `_build_python`**

Find the `_build_python` finalization (around line 358 — after `self._write_manifest(manifest)`). Read the prior manifest (if any) BEFORE the new write, then call `_emit_changeset` AFTER the write. The Phase 134 writes happen after the manifest is durable on disk so a crash mid-`_emit_changeset` doesn't lose the manifest.

```python
# Just before self._write_manifest(manifest) at line ~358:
prior_manifest_for_changeset: Optional[Dict[str, Any]] = None
if self.manifest_path.exists():
    try:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            prior_manifest_for_changeset = json.load(f)
    except Exception:
        prior_manifest_for_changeset = None

# Existing write:
self._write_manifest(manifest)

# Phase 134: emit the changeset for downstream stages.
import uuid
run_id = manifest.get("run_id") or f"run-{uuid.uuid4().hex[:12]}"
self._emit_changeset(file_hashes, prior_manifest_for_changeset, run_id)
```

(If the orchestrator already provides a stable `run_id`, prefer it; for now `uuid.uuid4().hex[:12]` is a safe default.)

- [ ] **Step 6: Wire `_emit_changeset` into `_build_rust`**

Find the `_build_rust` post-merge step (the block that sets `manifest["file_hashes"]` and `manifest["hash_algo"]` then calls `self._write_manifest(manifest)`). Apply the same pattern: read prior manifest, write new manifest, then `_emit_changeset`. The `prior_manifest_for_changeset` here is `old_manifest` (already loaded earlier in `_build_rust` for the preserve+merge step).

- [ ] **Step 7: Run the migration tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_migration_cases.py -v`
Expected: 5 PASSED.

- [ ] **Step 8: Run the full Phase 133 test suite to catch regressions**

Run: `.venv/bin/pytest tests/test_phase133_*.py tests/test_walker_parity.py --tb=short -q`
Expected: all PASSED. The Phase 133 work depends on the manifest contract; Phase 134's changeset write is additive and should not break it.

- [ ] **Step 9: Commit**

```bash
git add src/prep/core/trace/builder.py tests/test_phase134_migration_cases.py
git commit -m "feat(phase134): TraceBuilder emits Changeset to .sourceprep/changeset.json

Stage 1 (structural) now writes a Changeset alongside the manifest.
Three migration cases handled:
- Case 1 (no prior manifest): added = everything walked
- Case 2 (BLAKE3 manifest): real hash diff, partition into added/
  modified/deleted/unchanged
- Case 3 (pre-Phase-133 SHA-256 manifest): UNCONDITIONALLY trust
  prior work — entries enter `unchanged`, modified stays empty.
  This is the cascade-prevention logic moved from Phase 133's per-
  stage hot-fix to the changeset boundary, applied once at stage 1.

The changeset is written AFTER the manifest is durable on disk so
a crash mid-changeset-write doesn't lose the manifest. Both the
Python (_build_python) and Rust (_build_rust post-merge) paths emit.

5 migration tests pass. Phase 133 + walker_parity suite still green."
```

---

### Task 3: Worker contract — `WorkerFactory` injects the Changeset

**Files:**
- Modify: `src/prep/services/pipeline/workers/factory.py` (or wherever `WorkerFactory` lives — verify with `grep -rn "class WorkerFactory" src/prep/`)
- Modify: A worker base class to add `Worker.changeset: Optional[Changeset]` and `Worker.should_process(path)` (or define a mixin if no shared base exists)
- Test: `tests/test_phase134_worker_changeset_injection.py` (new)

This task lands the worker contract without yet using it in any consumer. Tasks 4-8 then cut over each consumer.

- [ ] **Step 1: Locate `WorkerFactory` and the worker base**

Run: `grep -rn "class WorkerFactory\|def create_worker" src/prep/services/pipeline/ | head -10`
Run: `grep -rn "class.*Worker\b" src/prep/services/pipeline/workers/ src/prep/core/ | head -20`

Find `WorkerFactory.create_worker`'s entry signature and any common worker base class. If no shared base exists, this task adds a thin mixin.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_phase134_worker_changeset_injection.py`:

```python
"""Phase 134 — WorkerFactory loads the Changeset and injects it into
each worker before construction returns. Workers consume via
self.changeset.should_process(path)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset, write_changeset


def test_worker_factory_loads_changeset_from_disk(tmp_path: Path):
    """When WorkerFactory.create_worker is invoked, it reads the
    project's .sourceprep/changeset.json and the resulting worker has
    .changeset set."""
    from prep.services.pipeline.workers.factory import WorkerFactory
    from prep.services.pipeline.stages import StageId

    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="run-test",
        base_run_id=None,
    )
    write_changeset(idx, cs)

    # Mock the project lookup so create_worker can resolve idx_dir
    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(tmp_path / "repo")

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        # Pick a stage that doesn't actually run side effects when
        # constructed — the structural worker is fine because we
        # only instantiate, we don't invoke it.
        worker = WorkerFactory.create_worker("test-proj", StageId.STRUCTURAL)

    assert worker.changeset is not None
    assert worker.changeset.run_id == "run-test"
    assert worker.changeset.should_process("new.py") is True
    assert worker.changeset.should_process("old.py") is False


def test_worker_factory_injects_none_when_changeset_missing(tmp_path: Path):
    """If no changeset.json exists on disk yet (e.g. very first build
    before Task 2 has emitted one), WorkerFactory injects None.
    Workers fall back to processing everything (defensive)."""
    from prep.services.pipeline.workers.factory import WorkerFactory
    from prep.services.pipeline.stages import StageId

    idx = tmp_path / "index"
    idx.mkdir()  # no changeset.json

    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(tmp_path / "repo")

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        worker = WorkerFactory.create_worker("test-proj", StageId.STRUCTURAL)

    assert worker.changeset is None


def test_worker_should_process_none_changeset_returns_true():
    """The defensive fallback: if changeset is None, should_process
    returns True (process everything). This protects against the
    orchestrator forgetting to inject during a refactor."""
    # Use a minimal worker class with the should_process mixin.
    from prep.services.pipeline.workers.base import Worker

    class TestWorker(Worker):
        pass

    w = TestWorker()
    w.changeset = None
    assert w.should_process("anything.py") is True


def test_worker_should_process_with_changeset():
    from prep.services.pipeline.workers.base import Worker

    class TestWorker(Worker):
        pass

    w = TestWorker()
    w.changeset = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert w.should_process("new.py") is True
    assert w.should_process("changed.py") is True
    assert w.should_process("old.py") is False
    assert w.should_process("never-seen.py") is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase134_worker_changeset_injection.py -v`
Expected: FAIL — `Worker.changeset` and `Worker.should_process` don't exist; WorkerFactory doesn't load changeset.

- [ ] **Step 4: Add the Worker base mixin**

Find the worker module. If `src/prep/services/pipeline/workers/base.py` exists, add to it. If not, create it. The mixin is minimal:

```python
# src/prep/services/pipeline/workers/base.py (create if absent)
"""Phase 134: Worker base providing the changeset contract.

Workers need to know what files to process in this run. Pre-Phase-134
each worker independently re-derived staleness from hashes (Important
#3 cascade). Phase 134 centralizes that decision in a single
Changeset emitted by stage 1; WorkerFactory injects it here."""
from __future__ import annotations

from typing import Optional

from prep.services.pipeline.changeset import Changeset


class Worker:
    """Base for pipeline stage workers. Phase 134 contract: workers
    receive `self.changeset` from WorkerFactory and use
    `self.should_process(path)` to gate per-file work."""

    changeset: Optional[Changeset] = None

    def should_process(self, file_path: str) -> bool:
        """Return True iff this worker should run on this file in
        this run. Defensive: if changeset is None (orchestrator
        forgot to inject), process everything — the per-stage
        cutover tests verify the orchestrator DOES inject in
        practice, but failing closed here would be worse than
        failing open if the contract regresses."""
        if self.changeset is None:
            return True
        return self.changeset.should_process(file_path)
```

If a different base class already exists for workers, add the same `changeset` attribute and `should_process` method to it instead — preserve the existing class hierarchy. The grep in Step 1 will show you what's there.

- [ ] **Step 5: Update existing worker classes to inherit from `Worker`**

Find each worker class (per Step 1's grep). For each, ensure it inherits from `Worker` (or whatever base now has the changeset attribute). For example:

```python
# Before:
class StructuralWorker:
    def __init__(self, project_id: str): ...

# After:
class StructuralWorker(Worker):
    def __init__(self, project_id: str): ...
```

If the existing classes use a different inheritance pattern (e.g., they're functions returning a callable), define `Worker` as a mixin and apply it via composition or `setattr`. Match the existing pattern.

- [ ] **Step 6: Inject the changeset in `WorkerFactory.create_worker`**

Find `WorkerFactory.create_worker`. After the worker is constructed, before return:

```python
# Existing construction:
worker = <existing worker construction>

# Phase 134: inject the changeset for downstream stages to consult.
# Stage 1 (structural) writes the changeset; WorkerFactory loads it
# here for stages 2-15. The structural worker itself does not consume
# its own changeset (it produces it), but the injection is harmless
# (worker.changeset = None gracefully falls through to "process
# everything" via the should_process default).
try:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    from prep.services.pipeline.changeset import read_changeset
    proj = require_project(project_id)
    idx_dir = project_index_dir(proj)
    worker.changeset = read_changeset(idx_dir)
except Exception:
    # Defensive: if project lookup or changeset load fails, leave
    # worker.changeset as None — Worker.should_process falls through
    # to "process everything."
    worker.changeset = None

return worker
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_worker_changeset_injection.py -v`
Expected: 4 PASSED.

- [ ] **Step 8: Run Phase 134 + Phase 133 suites for regressions**

Run: `.venv/bin/pytest tests/test_phase134_*.py tests/test_phase133_*.py tests/test_walker_parity.py --tb=short -q`
Expected: all PASSED.

- [ ] **Step 9: Commit**

```bash
git add src/prep/services/pipeline/workers/base.py src/prep/services/pipeline/workers/factory.py tests/test_phase134_worker_changeset_injection.py
# Plus any worker classes you updated to inherit from Worker.
git commit -m "feat(phase134): WorkerFactory injects Changeset into every worker

Worker base now exposes self.changeset (Optional[Changeset]) and
self.should_process(path). WorkerFactory.create_worker reads the
project's .sourceprep/changeset.json once at construction time and
sets worker.changeset before returning. Defensive fallback: if
changeset is None, should_process returns True (process everything).

This task lands the contract; tasks 4-8 cut over each downstream
consumer (augmenter, deepening, enrichment, scoring, audit) to use
self.should_process instead of per-stage hash comparison."
```

---

### Task 4: Augmenter cutover — delete file_hash compare, use changeset

**Files:**
- Modify: `src/prep/core/augmenter.py` — DELETE the hash compare block (lines 516-526), the `file_hash` field on `AugmentationEntry` (line 94), the field's serialize/deserialize (lines 114-115, 137). REPLACE the staleness gate with `self.changeset.should_process(path)`.
- Test: `tests/test_phase134_stage_cutover.py` — add the augmenter section.

This is the first downstream consumer cutover. Pattern repeats for tasks 5-8.

- [ ] **Step 1: Read the current augmenter staleness logic**

Run: `sed -n '90,130p' src/prep/core/augmenter.py` and `sed -n '510,530p' src/prep/core/augmenter.py`
Expected: shows `AugmentationEntry.file_hash` field + the `_should_skip` hash compare added by Phase 133's hot-fix.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase134_stage_cutover.py`:

```python
"""Phase 134 — per-stage cutover tests. Each downstream stage
(augmenter, deepening, epistemic_enrichment, epistemic_score, audit
StalenessAnalyzer) consumes Changeset.should_process(path) and has
no hash comparison logic remaining."""
from __future__ import annotations

import inspect

from prep.services.pipeline.changeset import Changeset


def test_augmenter_uses_changeset_should_process_not_file_hash():
    """The augmenter's per-node 'should I process this' decision
    must consult self.changeset.should_process — not a hash compare.
    Verified by source-code inspection: the file must reference
    'should_process' and must NOT reference 'file_hash' (the field
    is deleted in Phase 134)."""
    from prep.core import augmenter

    src = inspect.getsource(augmenter)
    assert "should_process" in src, (
        "augmenter.py must use self.changeset.should_process(path) "
        "as the staleness gate"
    )
    assert "file_hash" not in src, (
        "augmenter.py must NOT reference file_hash — the field is "
        "deleted in Phase 134 and the per-stage hash compare is gone. "
        "Found 'file_hash' references; expected zero."
    )
    # Also verify the Phase 133 hot-fix helper is no longer imported.
    assert "is_hash_stale" not in src, (
        "augmenter.py must not import is_hash_stale; that helper "
        "is being deleted in Task 12."
    )


def test_augmentation_entry_has_no_file_hash_field():
    """AugmentationEntry's dataclass schema must not include
    file_hash (the field is deleted in Phase 134)."""
    from prep.core.augmenter import AugmentationEntry
    fields = {f.name for f in AugmentationEntry.__dataclass_fields__.values()}
    assert "file_hash" not in fields, (
        f"AugmentationEntry must not have file_hash field; got fields={fields}"
    )


def test_augmenter_skips_unchanged_files_per_changeset():
    """Behavioral: when changeset says a file is unchanged, the
    augmenter's _should_skip returns True (skip — cached entry is
    trusted). When changeset says modified, _should_skip returns
    False (re-process)."""
    from prep.core.augmenter import TraceAugmenter, AugmentationEntry

    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    aug = TraceAugmenter.__new__(TraceAugmenter)  # bypass __init__
    aug.changeset = cs

    existing = {
        "file:old.py": AugmentationEntry(node_id="file:old.py", summary="x"),
        "file:changed.py": AugmentationEntry(node_id="file:changed.py", summary="y"),
    }

    # Method signature varies — we use whatever the augmenter exposes
    # for the per-node skip decision. If _should_skip is the method,
    # call it; otherwise the test should adapt to the actual API.
    # In Phase 134 the method takes a node and the existing dict
    # and returns a bool.
    assert aug._should_skip({"id": "file:old.py", "file_path": "old.py"}, existing) is True
    assert aug._should_skip({"id": "file:changed.py", "file_path": "changed.py"}, existing) is False
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py::test_augmenter_uses_changeset_should_process_not_file_hash -v`
Expected: FAIL — augmenter still references file_hash and is_hash_stale.

- [ ] **Step 4: Delete the `file_hash` field from `AugmentationEntry`**

Find `AugmentationEntry` (around line 90 of augmenter.py). DELETE the `file_hash` field and its serialization:

```python
# Before (delete these lines):
@dataclass
class AugmentationEntry:
    node_id: str
    summary: str = ""
    ...
    file_hash: Optional[str] = None  # ← DELETE
    ...

    def to_dict(self) -> Dict[str, Any]:
        d = {...}
        if self.file_hash:                    # ← DELETE
            d["file_hash"] = self.file_hash   # ← DELETE
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AugmentationEntry":
        return cls(
            ...
            file_hash=d.get("file_hash"),     # ← DELETE
        )

# After: file_hash field is gone; existing on-disk entries with the
# field continue to load (extra fields ignored by from_dict).
```

The `from_dict` change matters: ensure it constructs the dataclass via fields it explicitly knows about, so an unknown `file_hash` key in stored JSON is silently ignored (the typical `cls(**filtered_dict)` pattern).

- [ ] **Step 5: Replace the hash compare with `should_process`**

Find `_should_skip` (around line 516). Replace the hash compare block:

```python
def _should_skip(self, node: Dict[str, Any], existing: Dict[str, AugmentationEntry]) -> bool:
    """Phase 134: skip a node iff it's already augmented AND the
    changeset says we should not process its file in this run.
    Replaces pre-Phase-134 per-entry file_hash comparison."""
    node_id = node["id"]
    if node_id not in existing:
        return False  # never augmented → process
    file_path = node.get("file_path", "")
    if not file_path:
        # Symbol-level node without a file_path; nothing to gate on.
        return True  # already in existing, no change signal → skip
    return not self.should_process(file_path)
```

Note the inversion: `_should_skip` returns True when we should NOT process; `should_process` returns True when we SHOULD process. So `_should_skip = not should_process` for any file we already have an entry for.

- [ ] **Step 6: Verify augmenter no longer imports `is_hash_stale`**

Run: `grep -n "is_hash_stale\|file_hash" src/prep/core/augmenter.py`
Expected: zero hits. If any remain, find and remove them.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py::test_augmenter_uses_changeset_should_process_not_file_hash tests/test_phase134_stage_cutover.py::test_augmentation_entry_has_no_file_hash_field tests/test_phase134_stage_cutover.py::test_augmenter_skips_unchanged_files_per_changeset -v`
Expected: 3 PASSED.

- [ ] **Step 8: Run the augmenter regression suite**

Run: `.venv/bin/pytest tests/ -k "augmenter" --tb=short -q`
Expected: pre-existing tests still pass (or, if any tested the deleted hash compare logic, they fail and need to be deleted in this commit).

- [ ] **Step 9: Commit**

```bash
git add src/prep/core/augmenter.py tests/test_phase134_stage_cutover.py
git commit -m "feat(phase134): augmenter consumes Changeset, file_hash field deleted

AugmentationEntry.file_hash field removed. _should_skip rewritten
to use self.changeset.should_process(file_path) — pre-Phase-134
hash compare deleted entirely.

Existing on-disk entries with the file_hash field continue to load
(from_dict ignores unknown keys). Rollback safety: if Phase 134 is
reverted, the old code reads the field as None and treats as 'no
comparison data' → up-to-date (graceful)."
```

---

### Task 5: Deepening cutover

**Files:**
- Modify: `src/prep/core/deepening.py` — DELETE `_load_manifest_hashes` (~line 649), the stale-set hash compare loop (lines 158-175). REPLACE the stale_set computation with changeset-driven.
- Test: `tests/test_phase134_stage_cutover.py` — add deepening section.

- [ ] **Step 1: Read the current deepening staleness logic**

Run: `sed -n '155,180p' src/prep/core/deepening.py` and `sed -n '645,680p' src/prep/core/deepening.py`

- [ ] **Step 2: Add failing tests**

Append to `tests/test_phase134_stage_cutover.py`:

```python
def test_deepening_uses_changeset_not_file_hash():
    from prep.core import deepening
    src = inspect.getsource(deepening)
    assert "should_process" in src, (
        "deepening.py must consult changeset.should_process for stale_set"
    )
    assert "file_hash" not in src, (
        "deepening.py must not reference file_hash — Phase 134 deletes "
        "all per-stage hash compares"
    )
    assert "is_hash_stale" not in src
    assert "_load_manifest_hashes" not in src, (
        "_load_manifest_hashes is deleted in Phase 134 — staleness "
        "comes from the changeset, not from a per-stage manifest read"
    )


def test_deepening_stale_set_from_changeset():
    """The stale_set in decay_neighbors comes from changeset.modified
    (NOT from a hash comparison). Pre-Phase-134 stale_set was the
    set of nodes whose stored aug.file_hash differed from the
    manifest's current_hash. Post-Phase-134 stale_set is the set of
    nodes whose file_path is in changeset.modified | changeset.deleted."""
    from prep.core.deepening import DeepeningWorker  # or whatever the class is named
    cs = Changeset(
        added=frozenset(),
        modified=frozenset({"changed.py"}),
        deleted=frozenset({"gone.py"}),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    worker = DeepeningWorker.__new__(DeepeningWorker)
    worker.changeset = cs

    # The exact API of DeepeningWorker varies; this test asserts
    # behavior at the seam where stale_set is built from the
    # augmentations dict + changeset. If the worker exposes a
    # method that returns the stale set, call it and assert.
    augmentations = {
        "file:changed.py": {"node_id": "file:changed.py"},
        "file:gone.py": {"node_id": "file:gone.py"},
        "file:old.py": {"node_id": "file:old.py"},
    }
    stale = worker._compute_stale_set(augmentations)
    assert "file:changed.py" in stale  # in changeset.modified
    assert "file:gone.py" in stale     # in changeset.deleted (orphan)
    assert "file:old.py" not in stale  # in changeset.unchanged
```

(If the existing API doesn't expose a `_compute_stale_set` helper, this test motivates extracting one — better seam for testing.)

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py::test_deepening_uses_changeset_not_file_hash tests/test_phase134_stage_cutover.py::test_deepening_stale_set_from_changeset -v`
Expected: FAIL.

- [ ] **Step 4: Delete `_load_manifest_hashes`**

Find `_load_manifest_hashes` (~line 649). DELETE the entire method.

- [ ] **Step 5: Replace the stale_set computation**

Find the `decay_neighbors` (or equivalent) where stale_set is built. Replace:

```python
# Before (delete):
stale_set: Set[str] = set()
for node_id, score in scores.items():
    aug = augmentations.get(node_id)
    if not aug:
        continue
    file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
    aug_hash = aug.get("file_hash") or ""
    current_hash = current_file_hashes.get(file_path) or ""
    if is_hash_stale(aug_hash, current_hash):
        stale_set.add(node_id)
        report.stale_nodes.append(node_id)
        report.decayed_nodes[node_id] = 0.0

# After:
stale_set: Set[str] = self._compute_stale_set(augmentations)
for node_id in stale_set:
    report.stale_nodes.append(node_id)
    report.decayed_nodes[node_id] = 0.0
```

Add the helper:

```python
def _compute_stale_set(self, augmentations: Dict[str, Dict[str, Any]]) -> Set[str]:
    """Phase 134: stale_set is the set of node IDs whose underlying
    file is in the changeset's modified or deleted set. Replaces
    pre-Phase-134 per-entry hash comparison."""
    if self.changeset is None:
        return set()  # defensive: no changeset → assume nothing stale
    stale: Set[str] = set()
    invalid_paths = self.changeset.modified | self.changeset.deleted
    for node_id in augmentations.keys():
        file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
        if file_path and file_path in invalid_paths:
            stale.add(node_id)
    return stale
```

- [ ] **Step 6: Remove the `current_file_hashes` argument plumbing**

Find callers of `decay_neighbors` (or whatever method took `current_file_hashes`). Drop the argument — the changeset is on `self`.

Run: `grep -n "current_file_hashes\|file_hashes" src/prep/core/deepening.py`
Expected: zero hits after the cutover. If any remain, find and remove.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "deepening" -v`
Expected: PASSED.

- [ ] **Step 8: Run the deepening regression suite**

Run: `.venv/bin/pytest tests/ -k "deepening" --tb=short -q`
Expected: pass (or delete tests that asserted the deleted hash-compare behavior).

- [ ] **Step 9: Commit**

```bash
git add src/prep/core/deepening.py tests/test_phase134_stage_cutover.py
git commit -m "feat(phase134): deepening consumes Changeset for stale_set

decay_neighbors no longer reads manifest file_hashes or per-entry
aug.file_hash. _load_manifest_hashes deleted entirely.
_compute_stale_set computes from self.changeset.modified | deleted —
the same staleness signal stage 1 emitted, no recomputation."
```

---

### Task 6: Epistemic enrichment cutover

**Files:**
- Modify: `src/prep/core/epistemic_enrichment.py` — DELETE per-stage manifest hash reads (lines 449, 1365), per-entry compare in `_is_stale` (line 475). REPLACE with `should_process` check.
- Test: `tests/test_phase134_stage_cutover.py` — add enrichment section.

- [ ] **Step 1: Read the current logic**

Run: `sed -n '460,490p' src/prep/core/epistemic_enrichment.py` and `sed -n '445,460p' src/prep/core/epistemic_enrichment.py` and `sed -n '1360,1380p' src/prep/core/epistemic_enrichment.py`

- [ ] **Step 2: Add failing tests**

Append to `tests/test_phase134_stage_cutover.py`:

```python
def test_epistemic_enrichment_uses_changeset_not_file_hash():
    from prep.core import epistemic_enrichment
    src = inspect.getsource(epistemic_enrichment)
    assert "should_process" in src
    assert "file_hash" not in src
    assert "is_hash_stale" not in src
    # The lambda/method that loaded manifest hashes is gone.
    assert 'manifest.get("file_hashes"' not in src, (
        "epistemic_enrichment.py must not read manifest.file_hashes — "
        "staleness is in the changeset, not the manifest"
    )


def test_epistemic_enrichment_is_stale_uses_changeset():
    """EpistemicEnricher._is_stale returns True iff the file_path is
    in changeset.modified (need re-enrichment) — never from a hash
    compare."""
    from prep.core.epistemic_enrichment import EpistemicEnricher

    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    enricher = EpistemicEnricher.__new__(EpistemicEnricher)
    enricher.changeset = cs
    # Provide minimal augmentations so _is_stale's "is the file
    # already enriched" check has something to look at.
    augmentations = {
        "file:changed.py": {"node_id": "file:changed.py"},
        "file:old.py": {"node_id": "file:old.py"},
    }
    enricher._existing_enrichments = {"file:changed.py", "file:old.py"}

    # _is_stale signature: (self, node, augmentations) -> bool
    assert enricher._is_stale({"id": "file:changed.py", "file_path": "changed.py"}, augmentations) is True
    assert enricher._is_stale({"id": "file:old.py", "file_path": "old.py"}, augmentations) is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "epistemic_enrichment" -v`
Expected: FAIL.

- [ ] **Step 4: Delete the manifest-hash-loading helpers**

Find the closure / method that returns `manifest.get("file_hashes", {})` (around lines 449 and 1365). DELETE both.

- [ ] **Step 5: Rewrite `_is_stale`**

Find `_is_stale` (around line 466). Replace:

```python
# Before:
def _is_stale(self, node: Dict[str, Any], augmentations: Dict[str, Any]) -> bool:
    node_id = node["id"]
    if node_id not in self._existing_enrichments:
        return False
    file_path = node.get("file_path", "")
    if file_path:
        from prep.core.ids import is_hash_stale
        current_hash = file_hashes.get(file_path) or ""
        aug_hash = augmentations[node_id].get("file_hash") or ""
        if is_hash_stale(aug_hash, current_hash):
            return True
    return False

# After:
def _is_stale(self, node: Dict[str, Any], augmentations: Dict[str, Any]) -> bool:
    """Phase 134: a node is 'stale' (needs re-enrichment) iff its
    file_path is in changeset.modified. Files in changeset.unchanged
    have trusted prior enrichments; files in added haven't been
    enriched yet (caller handles); files in deleted are orphaned
    (audit handles)."""
    node_id = node["id"]
    if node_id not in self._existing_enrichments:
        return False
    file_path = node.get("file_path", "")
    if not file_path:
        return False  # symbol-level node, no file gate
    if self.changeset is None:
        return False  # defensive
    return file_path in self.changeset.modified
```

- [ ] **Step 6: Verify cleanup**

Run: `grep -n "is_hash_stale\|file_hash\|manifest.get..file_hashes" src/prep/core/epistemic_enrichment.py`
Expected: zero hits.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "epistemic_enrichment" -v`
Expected: PASSED.

- [ ] **Step 8: Regression check**

Run: `.venv/bin/pytest tests/ -k "epistemic" --tb=short -q`
Expected: pass (or delete obsolete tests).

- [ ] **Step 9: Commit**

```bash
git add src/prep/core/epistemic_enrichment.py tests/test_phase134_stage_cutover.py
git commit -m "feat(phase134): epistemic_enrichment consumes Changeset

_is_stale rewritten to check file_path in self.changeset.modified —
no manifest read, no per-entry hash compare, no is_hash_stale
import. Two manifest-hash-loading helpers deleted (lines ~449, 1365)."
```

---

### Task 7: Epistemic score — drop c6 staleness component, renormalize weights

**Files:**
- Modify: `src/prep/core/epistemic_score.py` — DELETE c6 staleness check (lines 208-220). Renormalize `SCORE_WEIGHTS` so the remaining 5 components sum to 1.0.
- Test: `tests/test_phase134_stage_cutover.py` — add scoring section.

- [ ] **Step 1: Read SCORE_WEIGHTS and the c6 calculation**

Run: `grep -n "SCORE_WEIGHTS\|composite\|c1\|c2\|c3\|c4\|c5\|c6" src/prep/core/epistemic_score.py | head -20`

- [ ] **Step 2: Add failing test**

Append to `tests/test_phase134_stage_cutover.py`:

```python
def test_epistemic_score_no_c6_staleness_check():
    from prep.core import epistemic_score
    src = inspect.getsource(epistemic_score)
    # The c6 staleness component is deleted in Phase 134.
    assert "is_hash_stale" not in src
    assert "current_file_hashes" not in src, (
        "epistemic_score must not take current_file_hashes — c6 deleted"
    )


def test_score_weights_sum_to_one_after_c6_removal():
    """After deleting the c6 staleness weight, SCORE_WEIGHTS must
    still sum to 1.0 (renormalized across the remaining 5
    components)."""
    from prep.core.epistemic_score import SCORE_WEIGHTS
    total = sum(SCORE_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, (
        f"SCORE_WEIGHTS must sum to 1.0 after c6 removal; got {total}"
    )
    assert "staleness" not in SCORE_WEIGHTS, (
        "staleness weight removed in Phase 134 — composite no longer "
        "discounts for stale enrichment because stale entries don't "
        "exist (the changeset prevents them at the augmenter level)"
    )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "score" -v`
Expected: FAIL.

- [ ] **Step 4: Delete c6, renormalize SCORE_WEIGHTS**

Find `SCORE_WEIGHTS` and the composite formula. DELETE the staleness key from the dict and the c6 term from the composite. Then redistribute the c6 weight proportionally across the remaining components, OR drop the c6 weight entirely and renormalize the others.

```python
# Before (example — actual values may differ):
SCORE_WEIGHTS = {
    "summary_confidence": 0.25,
    "validation_status": 0.20,
    "neighbor_coverage": 0.20,
    "cross_reference_density": 0.15,
    "pass_progression": 0.10,
    "staleness": 0.10,  # ← c6, DELETE
}

# After: drop c6 weight, redistribute its 0.10 proportionally:
SCORE_WEIGHTS = {
    "summary_confidence": 0.278,   # 0.25 / 0.90
    "validation_status": 0.222,    # 0.20 / 0.90
    "neighbor_coverage": 0.222,    # 0.20 / 0.90
    "cross_reference_density": 0.167,  # 0.15 / 0.90
    "pass_progression": 0.111,     # 0.10 / 0.90
}
```

(Use the exact pre-change values from your file; renormalize by dividing each by `(1.0 - old_staleness_weight)`.)

In the composite formula, delete the c6 term:

```python
# Before:
composite = (
    SCORE_WEIGHTS["summary_confidence"] * c1
    + SCORE_WEIGHTS["validation_status"] * c2
    + SCORE_WEIGHTS["neighbor_coverage"] * c3
    + SCORE_WEIGHTS["cross_reference_density"] * c4
    + SCORE_WEIGHTS["pass_progression"] * c5
    + SCORE_WEIGHTS["staleness"] * c6   # ← DELETE
)

# After:
composite = (
    SCORE_WEIGHTS["summary_confidence"] * c1
    + SCORE_WEIGHTS["validation_status"] * c2
    + SCORE_WEIGHTS["neighbor_coverage"] * c3
    + SCORE_WEIGHTS["cross_reference_density"] * c4
    + SCORE_WEIGHTS["pass_progression"] * c5
)
```

Also delete the c6 calculation block (lines ~208-220) and remove `current_file_hashes` and `augmentation` from the function signature if they were only used by c6.

- [ ] **Step 5: Update callers that pass `current_file_hashes`**

Run: `grep -rn "current_file_hashes" src/prep/`
Expected: any callers found should drop the argument (the parameter no longer exists).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "score" -v`
Expected: PASSED.

- [ ] **Step 7: Run the broader scoring + epistemic test suite**

Run: `.venv/bin/pytest tests/ -k "score or epistemic" --tb=short -q`
Expected: pass. If a test asserted specific composite scores that included c6, it'll need updating to the new normalization (or deletion).

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/epistemic_score.py tests/test_phase134_stage_cutover.py
git commit -m "feat(phase134): epistemic_score drops c6 staleness, renormalizes weights

The c6 staleness component existed to discount scores for entries
whose file content drifted from the recorded hash. With Phase 134
the changeset prevents stale entries from existing at the augmenter
level — there is no 'stale enrichment' to discount. c6 deleted;
SCORE_WEIGHTS renormalized so the remaining 5 components sum to 1.0."
```

---

### Task 8: Audit StalenessAnalyzer rewrite — orphan + coverage gap checks

**Files:**
- Modify: `src/prep/core/audit/analyzers/staleness.py` — REWRITE the analyzer from "compare hashes" to two narrow checks.
- Test: `tests/test_phase134_stage_cutover.py` — add audit section.

- [ ] **Step 1: Read the current analyzer**

Run: `cat src/prep/core/audit/analyzers/staleness.py`
Expected: shows the post-Phase-133-hot-fix analyzer with `is_hash_stale` calls.

- [ ] **Step 2: Add failing test**

Append to `tests/test_phase134_stage_cutover.py`:

```python
def test_audit_staleness_uses_changeset_not_hashes():
    from prep.core.audit.analyzers import staleness
    src = inspect.getsource(staleness)
    assert "is_hash_stale" not in src
    assert "prep_engine.hash_content" not in src, (
        "audit StalenessAnalyzer must not hash files itself — orphan "
        "and coverage-gap checks read changeset; no hashing"
    )
    assert "should_process" in src or "changeset" in src, (
        "audit StalenessAnalyzer must consult the changeset"
    )


def test_audit_staleness_orphan_check():
    """Files in changeset.deleted that still have augmentations are
    orphans — flag them."""
    from prep.core.audit.analyzers.staleness import StalenessAnalyzer
    from prep.core.audit.models import AuditContext

    cs = Changeset(
        added=frozenset(),
        modified=frozenset(),
        deleted=frozenset({"gone.py"}),
        unchanged=frozenset({"alive.py"}),
        run_id="r1",
        base_run_id=None,
    )
    ctx = AuditContext(
        project_root=Path("/tmp/fake"),
        augmentations={
            "file:gone.py": {"node_id": "file:gone.py"},
            "file:alive.py": {"node_id": "file:alive.py"},
        },
        changeset=cs,
    )
    analyzer = StalenessAnalyzer()
    findings = analyzer.analyze(ctx)
    # Should find one orphan (gone.py) and zero stale-content findings
    orphan_findings = [f for f in findings if "orphan" in f.title.lower() or "deleted" in f.title.lower()]
    assert len(orphan_findings) == 1
```

(If `AuditContext` doesn't have a `changeset` field today, this test motivates adding one — that's part of this task.)

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "audit_staleness" -v`
Expected: FAIL.

- [ ] **Step 4: Add `changeset` to `AuditContext`**

Find `AuditContext` in `src/prep/core/audit/models.py` (or wherever it lives). Add the field:

```python
@dataclass
class AuditContext:
    project_root: Path
    augmentations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    file_hashes: Dict[str, str] = field(default_factory=dict)  # legacy, may be removed in cleanup
    # Phase 134:
    changeset: Optional[Changeset] = None
    ...
```

Update the audit context builder (probably in `audit/context.py` or `runner.py`) to populate `changeset` from `read_changeset(idx_dir)`.

- [ ] **Step 5: Rewrite the analyzer**

Replace `src/prep/core/audit/analyzers/staleness.py` with the new two-check version:

```python
"""Phase 134 — Staleness analyzer rewrite.

Pre-Phase-134 this analyzer hashed every file and compared against
the manifest's file_hashes (per-stage staleness check, the bug class
Phase 134 deletes). Post-Phase-134 the analyzer consults the
changeset for two narrow, well-scoped checks:

1. Orphan check: files in changeset.deleted that still have
   augmentation entries on disk. These are leftover state from
   files the user removed; the augmentation pipeline should clean
   them up.
2. Coverage-gap check: files in changeset.added | modified that
   the augmenter didn't process by run end. These indicate the
   augmenter silently failed for some inputs."""
from __future__ import annotations

from typing import List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class StalenessAnalyzer(BaseAnalyzer):
    name = "staleness"
    category = "quality"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []
        if ctx.changeset is None:
            return findings

        # Check 1: orphan augmentations
        deleted_paths = ctx.changeset.deleted
        orphan_node_ids: List[str] = []
        for node_id in ctx.augmentations.keys():
            file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
            if file_path and file_path in deleted_paths:
                orphan_node_ids.append(node_id)

        if orphan_node_ids:
            severity = "warning" if len(orphan_node_ids) > 10 else "info"
            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"{len(orphan_node_ids)} orphan augmentations (deleted files)",
                description=(
                    f"{len(orphan_node_ids)} augmentation entries reference "
                    f"files that were deleted in this run. Cleanup pass "
                    f"should remove them.\n"
                    f"Top orphans: {', '.join(orphan_node_ids[:10])}"
                ),
                file_paths=[node_id.replace("file:", "", 1) for node_id in orphan_node_ids[:20]],
                evidence={"orphan_count": len(orphan_node_ids)},
                suggested_action="Run augmentation cleanup to remove orphan entries.",
            ))

        # Check 2: coverage gap
        expected_processed = ctx.changeset.added | ctx.changeset.modified
        actually_processed = {
            node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
            for node_id in ctx.augmentations.keys()
        }
        gap = expected_processed - actually_processed
        if gap:
            severity = "warning" if len(gap) > 5 else "info"
            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"{len(gap)} files added/modified but not augmented",
                description=(
                    f"{len(gap)} files are in this run's changeset (added "
                    f"or modified) but no augmentation entry exists for "
                    f"them. The augmenter may have silently failed.\n"
                    f"Top missing: {', '.join(sorted(gap)[:10])}"
                ),
                file_paths=sorted(gap)[:20],
                evidence={"gap_count": len(gap)},
                suggested_action="Re-run augmentation for the affected files.",
            ))

        return findings
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_phase134_stage_cutover.py -k "audit" -v`
Expected: PASSED.

- [ ] **Step 7: Regression check**

Run: `.venv/bin/pytest tests/ -k "audit or staleness" --tb=short -q`
Expected: pass. Old hash-based staleness tests will need to be deleted — they tested the deleted code.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/audit/analyzers/staleness.py src/prep/core/audit/models.py tests/test_phase134_stage_cutover.py
git commit -m "feat(phase134): audit StalenessAnalyzer rewrite — orphan + coverage-gap checks

Pre-Phase-134 the analyzer hashed every file and compared against
manifest. Post-Phase-134: two narrow checks consulting only the
changeset:

1. Orphan check: augmentations for files in changeset.deleted
2. Coverage gap: files in added/modified missing from augmentations

AuditContext gains an optional changeset field. The analyzer no
longer imports prep_engine.hash_content or is_hash_stale."
```

---

### Task 9: `compute_trace_coverage` simplification

**Files:**
- Modify: `src/prep/core/trace/coverage.py` — DELETE per-file hash compare branch (~lines 320-460), Path A `hash_algo_mismatch` self-heal (~30 lines), backfill carve-out (~lines 110-220). REPLACE with changeset read + walker-only diff.
- Test: existing `tests/test_phase133_*.py` should mostly pass with adjustments; add `tests/test_phase134_coverage_simplified.py` for the new behavior.

- [ ] **Step 1: Read the current coverage.py size**

Run: `wc -l src/prep/core/trace/coverage.py`
Run: `grep -n "hash_algo_mismatch\|backfill\|prep_engine.hash_content" src/prep/core/trace/coverage.py`

Expected: ~500 lines today; the backfill block and hash compare each ~50-80 lines.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase134_coverage_simplified.py`:

```python
"""Phase 134 — compute_trace_coverage reads the changeset, performs
no hashing, has no Path A self-heal, has no backfill carve-out."""
from __future__ import annotations

import inspect

from prep.core.trace import coverage


def test_coverage_does_not_hash():
    src = inspect.getsource(coverage)
    assert "prep_engine.hash_content" not in src, (
        "compute_trace_coverage must not hash files — staleness comes "
        "from the changeset, not from hash comparison"
    )
    assert "hash_algo_mismatch" not in src, (
        "Path A self-heal removed in Phase 134"
    )
    assert "stable_file_hash" not in src
    assert "_backfill_lock" not in src, (
        "backfill carve-out removed; changeset is the truth"
    )


def test_coverage_reads_changeset():
    src = inspect.getsource(coverage)
    assert "read_changeset" in src or "Changeset" in src, (
        "compute_trace_coverage must read the changeset"
    )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_coverage_simplified.py -v`
Expected: FAIL.

- [ ] **Step 4: Rewrite `compute_trace_coverage`**

This is a significant rewrite — keep the public function signature stable (callers expect `traced/untraced/stale/excluded/pending_embedding/summary` keys) but the implementation simplifies to:

1. Load the changeset (`read_changeset(idx_dir)`).
2. Walk the disk via `prep_engine.walk_repo` for the current file list.
3. Categorize:
   - `traced` = files in `changeset.unchanged` AND in `embedded_paths`
   - `pending_embedding` = files in `changeset.unchanged` but NOT in `embedded_paths`
   - `stale` = files in `changeset.modified` (per the changeset, not via re-hashing)
   - `untraced` = files on disk NOT in `changeset.all_known()` (the dashboard's "you have unindexed files" surface)
   - `excluded` = files matching user_exclude_globs (unchanged)
4. Compute summary counts and coverage_pct from the categorized lists.

Replace the bulk of `compute_trace_coverage` (everything between the manifest read and the return statement) with:

```python
from prep.services.pipeline.changeset import read_changeset

def compute_trace_coverage(
    repo_root: Path,
    index_dir: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
    user_exclude_globs: Optional[List[str]] = None,
    max_file_bytes: int = 500_000,
    embedded_paths: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Phase 134: read the changeset (single source of truth for what
    the pipeline knows about) plus a walker-only diff for what's been
    added on disk since the last run. No hashing. No Path A self-heal.
    No backfill carve-out. ~180 lines deleted from this function."""
    repo_root = Path(repo_root).resolve()
    if embedded_paths is None:
        embedded_paths = set()

    # ... (keep the include_globs/exclude_globs default-resolution
    # and DEFAULT_EXCLUDE_FILE_GLOBS / user_exclude_globs handling
    # — these remain because the walker needs them) ...

    import prep_engine
    entries = prep_engine.walk_repo(
        str(repo_root),
        include_globs=list(include_globs) if include_globs else None,
        exclude_globs=list(exclude_globs) if exclude_globs else None,
        max_file_bytes=int(max_file_bytes),
    )

    warnings: List[str] = []
    WALKER_MAX_FILES = 100_000
    if len(entries) >= WALKER_MAX_FILES:
        warnings.append(
            f"max_files cap hit: walker returned exactly {len(entries):,} files. "
            f"Files beyond the cap were silently dropped."
        )

    # User-exclude (still applies on top of walker output)
    import pathspec
    user_exclude_spec = (
        pathspec.PathSpec.from_lines("gitwildmatch", user_exclude_globs)
        if user_exclude_globs else None
    )

    # Load the changeset (the truth from the last pipeline run).
    cs = read_changeset(Path(index_dir))

    # Categorize.
    walker_paths = {e.path for e in entries}
    traced_files: List[Dict[str, Any]] = []
    untraced_files: List[Dict[str, Any]] = []
    stale_files: List[Dict[str, Any]] = []
    excluded_files: List[Dict[str, Any]] = []
    pending_embedding: List[Dict[str, Any]] = []

    def _make_info(entry) -> Dict[str, Any]:
        rel = entry.path
        return {
            "path": rel,
            "language": _detect_language(rel),
            "size": int(entry.size),
            "modified": (
                datetime.fromtimestamp(entry.modified_secs, tz=timezone.utc).isoformat()
                if entry.modified_secs else "1970-01-01T00:00:00+00:00"
            ),
            "created": (
                datetime.fromtimestamp(entry.modified_secs, tz=timezone.utc).isoformat()
                if entry.modified_secs else "1970-01-01T00:00:00+00:00"
            ),
        }

    for entry in entries:
        info = _make_info(entry)
        rel = entry.path

        if user_exclude_spec and user_exclude_spec.match_file(rel):
            excluded_files.append(info)
            continue

        if cs is None:
            # Never built — everything is untraced.
            untraced_files.append(info)
            continue

        if rel in cs.modified:
            stale_files.append(info)
        elif rel in cs.unchanged:
            if rel in embedded_paths:
                traced_files.append(info)
            else:
                pending_embedding.append(info)
        elif rel in cs.added:
            # Files the pipeline JUST added in the current/most-recent
            # run — between run completion and the next run. Treat as
            # pending embedding (analogous to unchanged-but-not-embedded).
            if rel in embedded_paths:
                traced_files.append(info)
            else:
                pending_embedding.append(info)
        else:
            # Walked file is not in any changeset bucket — it appeared
            # on disk after the last pipeline run.
            untraced_files.append(info)

    # Sort + summary (unchanged from pre-Phase-134)
    traced_files.sort(key=lambda f: f["path"])
    untraced_files.sort(key=lambda f: f["path"])
    stale_files.sort(key=lambda f: f["path"])
    excluded_files.sort(key=lambda f: f["path"])
    pending_embedding.sort(key=lambda f: f["path"])

    total = len(traced_files) + len(pending_embedding) + len(untraced_files) + len(stale_files)
    traced_count_all = len(traced_files) + len(pending_embedding)
    coverage_pct = round(traced_count_all / total * 100, 1) if total > 0 else 0.0

    # Edge counts (unchanged — keep the existing trace_edges /
    # trace_inferred_edges file reads at the bottom of the function).

    return {
        "traced": traced_files,
        "pending_embedding": pending_embedding,
        "untraced": untraced_files,
        "stale": stale_files,
        "excluded": excluded_files,
        "warnings": warnings,
        "summary": {
            "total": total,
            "traced": len(traced_files),
            "pending_embedding": len(pending_embedding),
            "untraced": len(untraced_files),
            "stale": len(stale_files),
            "excluded": len(excluded_files),
            "coverage_pct": coverage_pct,
            # ... existing edge_counts block ...
        },
    }
```

DELETE the manifest-load block at the top of the function (lines ~100-225 — the 125-line block that reads `trace_manifest.json`, computes `manifest_hashes`, runs the backfill carve-out, etc.). The changeset replaces all of it.

DELETE the `hash_algo_mismatch` branch (lines ~230-247 — the Path A self-heal added in Phase 133).

DELETE the per-file hash compare loop body wherever `prep_engine.hash_content` is called (lines ~163, ~389, ~455).

- [ ] **Step 5: Verify the deletions**

Run: `wc -l src/prep/core/trace/coverage.py`
Expected: significantly fewer lines than before (target: ~250 → ~150 lines, depending on how aggressively you collapse).

Run: `grep -n "hash\|stable_file_hash\|prep_engine.hash_content\|hash_algo_mismatch\|_backfill_lock" src/prep/core/trace/coverage.py`
Expected: zero hits in the function body. (Imports may still reference `prep_engine` for the walker — that's fine.)

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/pytest tests/test_phase134_coverage_simplified.py tests/test_phase133_coverage_uses_rust_walker.py tests/test_phase133_hidden_dirs.py tests/test_phase133_max_files_warning.py -v`
Expected: Phase 134 simplification tests pass. Phase 133 tests should mostly pass (the contract tests for "uses walker" and "hidden dirs visible" still hold).

The Phase 133 hash migration tests (`test_phase133_hash_migration.py`) likely need updating — their assertions about `stale` file count when manifest has hash format mismatch are no longer relevant (the changeset handles that now). Either delete those tests OR rewrite them to test the changeset-side migration logic added in Task 2.

- [ ] **Step 7: Run the broader coverage suite**

Run: `.venv/bin/pytest tests/ -k "coverage or trace_coverage" --tb=short -q`
Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/trace/coverage.py tests/test_phase134_coverage_simplified.py
# Plus any deleted/updated Phase 133 tests.
git commit -m "feat(phase134): compute_trace_coverage reads Changeset, no hashing

DELETED:
- per-file hash compare loop (~80 lines)
- Path A hash_algo_mismatch self-heal branch (~30 lines)
- backfill carve-out / _backfill_lock block (~125 lines)
- manifest-hash loading at function top

REPLACED with: read changeset.json + walker-only file enumeration +
set-based categorization. The dashboard's 'untraced' surface now
shows files on disk NOT in changeset.all_known() — the natural
'you have unindexed files' signal."
```

---

### Task 10: Delete `ResumeStrategy.refresh_manifest_hashes` + 3 orchestrator call sites

**Files:**
- Modify: `src/prep/services/pipeline/resume.py` — DELETE the entire `refresh_manifest_hashes` static method (lines 816-1043, ~220 lines).
- Modify: `src/prep/services/pipeline/orchestrator.py` — DELETE 3 call sites at lines ~572, 684, 2231.
- Test: `tests/test_phase134_refresh_deleted.py` (new)

This task closes the Critical #1 bug class from the Phase 133 review. The function existed to "refresh hashes between rebuilds"; with the changeset as the staleness signal, it has no purpose.

- [ ] **Step 1: Locate all call sites**

Run: `grep -rn "refresh_manifest_hashes\|_refresh_manifest_hashes" src/prep/`
Expected: the static method definition + 3 orchestrator call sites + maybe one test reference.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase134_refresh_deleted.py`:

```python
"""Phase 134 — ResumeStrategy.refresh_manifest_hashes is deleted.

Pre-Phase-134 this 220-line method walked the disk, hashed every
file, and rewrote trace_manifest.json::file_hashes. The orchestrator
called it on three hot paths (force_from_start gap-check, Phase 72
pre-gap refresh, post-fast_sync refresh). With Phase 134's changeset
as the single staleness signal, this function has no purpose."""
from __future__ import annotations


def test_refresh_manifest_hashes_method_deleted():
    from prep.services.pipeline.resume import ResumeStrategy
    assert not hasattr(ResumeStrategy, "refresh_manifest_hashes"), (
        "Phase 134 deletes ResumeStrategy.refresh_manifest_hashes — "
        "the changeset is the staleness signal, refreshing manifest "
        "hashes between runs is unnecessary"
    )


def test_orchestrator_no_refresh_call_sites():
    """Verify by source inspection that orchestrator.py doesn't call
    the deleted method."""
    import inspect
    from prep.services.pipeline import orchestrator
    src = inspect.getsource(orchestrator)
    assert "refresh_manifest_hashes" not in src, (
        "orchestrator.py must not call the deleted refresh_manifest_hashes"
    )
    assert "_refresh_manifest_hashes" not in src
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_refresh_deleted.py -v`
Expected: FAIL.

- [ ] **Step 4: Delete the method**

Edit `src/prep/services/pipeline/resume.py`. Find `def refresh_manifest_hashes(...)` (~line 816). DELETE the entire method body (~220 lines, ending around line 1043). If there's an associated `_refresh_manifest_hashes` private wrapper, delete that too.

- [ ] **Step 5: Delete the 3 orchestrator call sites**

Edit `src/prep/services/pipeline/orchestrator.py`. Find each `_refresh_manifest_hashes` call. DELETE the call AND any surrounding "if refreshed > 0: log" block.

For example, at line ~572 (in the U19 force_from_start gap check):

```python
# Before (delete the entire try block):
try:
    refreshed = self._refresh_manifest_hashes(project_id)
    if refreshed > 0 and pfl:
        pfl.log("fast_sync", f"Pre-rebuild: refreshed {refreshed} file hashes")
except Exception:
    logger.debug("U19 manifest hash refresh failed (non-fatal)", exc_info=True)

# After: deleted entirely. The changeset (emitted by stage 1) is
# the staleness signal; refreshing manifest hashes pre-rebuild is
# unnecessary because the rebuild itself rewrites the manifest.
```

Do the same for the call sites at lines ~684 (Phase 72 pre-gap refresh) and ~2231 (post-fast_sync refresh).

- [ ] **Step 6: Verify deletions**

Run: `grep -rn "refresh_manifest_hashes" src/prep/`
Expected: zero hits in src/.

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/pytest tests/test_phase134_refresh_deleted.py tests/test_phase133_refresh_manifest_hashes_cutover.py -v`

The Phase 133 cutover test (`test_phase133_refresh_manifest_hashes_cutover.py`) tested the Phase 133 fix to refresh_manifest_hashes. Since the function is now deleted, that test file is obsolete. **Delete it:**

```bash
git rm tests/test_phase133_refresh_manifest_hashes_cutover.py
```

Re-run:

Run: `.venv/bin/pytest tests/test_phase134_refresh_deleted.py -v`
Expected: 2 PASSED.

- [ ] **Step 8: Run the broader pipeline + recovery tests**

Run: `.venv/bin/pytest tests/ -k "pipeline_orchestrator or resume or recovery or phase133" --tb=short -q`
Expected: pass. The function deletion may break other tests — investigate any failures, delete tests that asserted the deleted behavior.

- [ ] **Step 9: Commit**

```bash
git add src/prep/services/pipeline/resume.py src/prep/services/pipeline/orchestrator.py tests/test_phase134_refresh_deleted.py
git rm tests/test_phase133_refresh_manifest_hashes_cutover.py
git commit -m "feat(phase134): delete refresh_manifest_hashes and 3 orchestrator call sites

The 220-line ResumeStrategy.refresh_manifest_hashes method existed
to refresh trace_manifest.json::file_hashes between rebuilds (so
coverage's per-file hash compare wouldn't drift). With Phase 134
the changeset is the staleness signal — manifest hashes are an
internal stage-1 detail, not consumed by anyone else.

Deletes:
- resume.py:816-1043 (the entire method)
- orchestrator.py:572 (U19 force_from_start gap-check call)
- orchestrator.py:684 (Phase 72 pre-gap refresh call)
- orchestrator.py:2231 (post-fast_sync refresh call)
- tests/test_phase133_refresh_manifest_hashes_cutover.py (tested
  the Phase 133 fix to a now-deleted function)

Closes the Critical #1 bug class from the Phase 133 post-review."
```

---

### Task 11: F-67 backup pattern simplification

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py:2453-2495` — drop the inline restore logic; keep the rename for now.

This is a small simplification: with the changeset as the inter-stage truth, the manifest is no longer load-bearing for downstream stages. The F-67 rename-to-`.f67_pending` pattern was added in Phase 133 commit `d8e89580` to protect against Rust panics wiping the manifest. The rename is still useful (resume detection) but the inline restore-from-backup logic is unnecessary.

- [ ] **Step 1: Read the current F-67 block**

Run: `sed -n '2453,2495p' src/prep/services/pipeline/orchestrator.py`

- [ ] **Step 2: Simplify**

Drop the restore-from-backup logic; keep the rename so resume-point detection still works (a missing manifest signals "stage incomplete"):

```python
# Phase 134 simplification: the changeset is now the inter-stage
# truth, so the manifest's role is downgraded. We still rename
# instead of unlink so resume-point detection sees the absence
# (stage = incomplete), but we no longer restore from backup —
# if the stage fails, the changeset from the last successful run
# is still on disk and downstream stages keep working off it.
try:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    _proj = require_project(run.project_id)
    _idx_dir = Path(project_index_dir(_proj))
    _manifest_file = STAGE_MANIFEST_FILE.get(stage)
    if _manifest_file:
        _manifest_path = _idx_dir / _manifest_file
        _backup_path = _idx_dir / f"{_manifest_file}.f67_pending"
        if _manifest_path.exists():
            if _backup_path.exists():
                _backup_path.unlink()
            _manifest_path.rename(_backup_path)
            logger.info(
                "F-67: Renamed stale manifest %s → %s.f67_pending before starting stage %s",
                _manifest_file, _manifest_file, stage.value,
            )
except Exception:
    logger.debug("F-67: manifest invalidation failed (non-fatal)", exc_info=True)
```

- [ ] **Step 3: Run regression tests**

Run: `.venv/bin/pytest tests/ -k "phase133 or pipeline_orchestrator" --tb=no -q`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "feat(phase134): simplify F-67 backup pattern (drop inline restore)

With the changeset as the inter-stage truth, the manifest is no
longer load-bearing for downstream stages. The F-67 rename-to-
.f67_pending stays (resume-point detection needs the absence
signal), but the inline restore-from-backup added in Phase 133
commit d8e89580 is no longer needed — if a stage fails, the prior
run's changeset is still on disk and consumers keep working."
```

---

### Task 12: Delete `is_hash_stale` helper (last 5 callers gone after tasks 4-8)

**Files:**
- Modify: `src/prep/core/ids.py` — DELETE `is_hash_stale` and its docstring (~45 lines added in Phase 133 commit `889c042b`).
- Test: `tests/test_phase134_is_hash_stale_deleted.py` (new)

After tasks 4-8 cut over each consumer, `is_hash_stale` should have zero callers. This task verifies and deletes.

- [ ] **Step 1: Verify zero callers remain**

Run: `grep -rn "is_hash_stale" src/prep/`
Expected: only the definition in `src/prep/core/ids.py`. If any call sites remain, find which task missed them and circle back.

- [ ] **Step 2: Write the test**

Create `tests/test_phase134_is_hash_stale_deleted.py`:

```python
"""Phase 134 — is_hash_stale helper deleted (Phase 133 hot-fix gone)."""
from __future__ import annotations


def test_is_hash_stale_helper_deleted():
    from prep.core import ids
    assert not hasattr(ids, "is_hash_stale"), (
        "Phase 134 deletes is_hash_stale — the per-stage staleness "
        "checks it patched are themselves deleted, so the helper is "
        "now dead code"
    )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase134_is_hash_stale_deleted.py -v`
Expected: FAIL.

- [ ] **Step 4: Delete the helper**

Edit `src/prep/core/ids.py`. DELETE the `is_hash_stale` function and its docstring block (the ~45 lines starting with `# ── Phase 133 hot-fix: hash format mismatch grace check ──`).

- [ ] **Step 5: Delete the Phase 133 hot-fix test**

```bash
git rm tests/test_phase133_hotfix_hash_format_grace.py
```

The hot-fix tests are tied to a function that no longer exists.

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase134_is_hash_stale_deleted.py -v`
Expected: PASSED.

- [ ] **Step 7: Run the broader Phase 133 / 134 suite**

Run: `.venv/bin/pytest tests/test_phase133_*.py tests/test_phase134_*.py --tb=short -q`
Expected: pass. If anything still imports `is_hash_stale`, fix the import.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/ids.py tests/test_phase134_is_hash_stale_deleted.py
git rm tests/test_phase133_hotfix_hash_format_grace.py
git commit -m "feat(phase134): delete is_hash_stale helper (Phase 133 hot-fix removed)

After tasks 4-8 cut over each per-stage consumer to use
self.changeset.should_process(path), is_hash_stale has zero
remaining call sites. The Phase 133 hot-fix existed only to keep
the patient alive until Phase 134; the proper fix (centralized
staleness via the changeset) makes the bandage unnecessary."
```

---

### Task 13: Walker convergence — `repo_profile.py`

**Files:**
- Modify: `src/prep/core/repo_profile.py:241, 327` — `os.walk` → `prep_engine.walk_repo`.

- [ ] **Step 1: Read the current callers**

Run: `sed -n '235,260p' src/prep/core/repo_profile.py` and `sed -n '320,345p' src/prep/core/repo_profile.py`

These are `compute_index_metrics` (?) and `_collect_files` (?) — verify by reading. Both walk for index-metrics purposes, not for staleness — the conversion is mechanical.

- [ ] **Step 2: Migrate each `os.walk` to `prep_engine.walk_repo`**

Pattern:

```python
# Before:
for dirpath, dirnames, filenames in os.walk(str(root)):
    # ... custom prune logic ...
    for fname in filenames:
        # ... process ...

# After:
import prep_engine
entries = prep_engine.walk_repo(
    str(root),
    include_globs=None,    # or per-caller
    exclude_globs=[f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES],
    max_file_bytes=500_000,
)
for entry in entries:
    # ... process via entry.path / entry.abs_path ...
```

Match each caller's existing filter behavior — read the surrounding code carefully so you don't drop or add filtering by accident. The Rust walker honors `include_globs`, `exclude_globs`, and `.gitignore` natively, so any custom prune logic can usually be expressed via globs.

- [ ] **Step 3: Verify**

Run: `grep -n "os.walk" src/prep/core/repo_profile.py`
Expected: zero hits.

- [ ] **Step 4: Run regression tests**

Run: `.venv/bin/pytest tests/ -k "repo_profile or compute_index_metrics" --tb=no -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/repo_profile.py
git commit -m "feat(phase134): repo_profile walker convergence onto prep_engine.walk_repo

Two os.walk callers in repo_profile.py (compute_index_metrics,
_collect_files) migrated to prep_engine.walk_repo for filter
parity with the rest of the pipeline."
```

---

### Task 14: Walker convergence — `builder._enumerate_files`

**Files:**
- Modify: `src/prep/core/trace/builder.py:557` — `os.walk` → `prep_engine.walk_repo`. May allow deletion of `_enumerate_files` entirely if no remaining caller after Task 6 of Phase 133.

- [ ] **Step 1: Verify callers**

Run: `grep -n "_enumerate_files" src/prep/core/trace/builder.py`

If `_enumerate_files` is only called by `_build_python` (the Python build path), and that path is rare/legacy, consider deleting `_enumerate_files` entirely and inlining the walker call into `_build_python`. Otherwise, migrate the walker.

- [ ] **Step 2: Migrate**

Replace the `os.walk` block with `prep_engine.walk_repo` per the same pattern as Task 13.

- [ ] **Step 3: Verify**

Run: `grep -n "os.walk" src/prep/core/trace/builder.py`
Expected: zero hits.

- [ ] **Step 4: Test**

Run: `.venv/bin/pytest tests/ -k "trace_builder or trace.build" --tb=no -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/trace/builder.py
git commit -m "feat(phase134): builder._enumerate_files walker convergence

Migrated to prep_engine.walk_repo for filter parity with the
structural rebuild path and compute_trace_coverage."
```

---

### Task 15: Walker convergence — `atlas/markdown_links.py`

**Files:**
- Modify: `src/prep/core/atlas/markdown_links.py:152` — `os.walk` → `prep_engine.walk_repo`.

- [ ] **Step 1: Read the caller**

Run: `sed -n '145,165p' src/prep/core/atlas/markdown_links.py`

- [ ] **Step 2: Migrate**

Same pattern as Tasks 13-14.

- [ ] **Step 3: Verify**

Run: `grep -n "os.walk" src/prep/core/atlas/markdown_links.py`
Expected: zero hits.

- [ ] **Step 4: Test**

Run: `.venv/bin/pytest tests/ -k "markdown_links or atlas" --tb=no -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/atlas/markdown_links.py
git commit -m "feat(phase134): atlas/markdown_links walker convergence onto prep_engine.walk_repo"
```

---

### Task 15b: Walker convergence — `orchestrator.py` post-structural sanity

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py:2772` — `os.walk` → `prep_engine.walk_repo`.

The last remaining `os.walk` in pipeline-relevant code. Lives inside the post-structural sanity check that fires when the structural stage completes with zero nodes.

- [ ] **Step 1: Read the current caller**

Run: `sed -n '2765,2795p' src/prep/services/pipeline/orchestrator.py`

The block walks `_repo` looking for `.py` files when structural reports 0 nodes — a sanity-check diagnostic. Migrate it to the walker primitive for filter parity.

- [ ] **Step 2: Migrate**

```python
# Before:
for _r, _ds, _fs in os.walk(_repo):
    # ... custom logic to count .py files ...

# After:
import prep_engine
entries = prep_engine.walk_repo(
    str(_repo),
    include_globs=["**/*.py"],
    exclude_globs=None,  # walker defaults apply
    max_file_bytes=500_000,
)
# ... count len(entries) or iterate entry.path ...
```

Preserve the diagnostic's intent — if the original was counting files, count `len(entries)`; if it was walking to find a specific file, iterate `entries` and check `entry.path`.

- [ ] **Step 3: Verify**

Run: `grep -n "os.walk" src/prep/services/pipeline/orchestrator.py`
Expected: zero hits.

- [ ] **Step 4: Test**

Run: `.venv/bin/pytest tests/test_phase134_walker_convergence.py -v`
Expected: passes (orchestrator now in the clean set).

Run: `.venv/bin/pytest tests/ -k "pipeline_orchestrator" --tb=no -q`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "feat(phase134): orchestrator post-structural sanity walker convergence

The post-structural sanity diagnostic (orchestrator.py:2772) was
the last os.walk in pipeline-relevant code. Migrated to
prep_engine.walk_repo for filter parity. With this, the
test_phase134_walker_convergence guard passes across all 8 covered
files."
```

---

### Task 16: End-to-end migration smoke — proves the cascade is dead

**Files:**
- Create: `tests/test_phase134_e2e_no_llm_recall.py`

The headline regression test for Important #3. Builds a fixture project with stub augmentations carrying SHA-256 hashes, runs stage 1 + augmenter, asserts zero augmenter LLM call sites were invoked.

- [ ] **Step 1: Write the test**

Create `tests/test_phase134_e2e_no_llm_recall.py`:

```python
"""Phase 134 — end-to-end migration smoke. The headline regression
test for Important #3 (cache invalidation cascade).

Setup: a project with a pre-Phase-133 manifest (SHA-256 hashes, no
hash_algo) and stub augmentations also carrying SHA-256 hashes.
This is exactly the state the SourcePrep project was in on 2026-05-10
when clicking deep_enrichment Auto re-ran every LLM call.

Phase 134 expectation: stage 1 emits a Case-3 changeset (everything
in `unchanged`), the augmenter sees should_process(path) → False
for every existing entry, ZERO LLM call sites are invoked.

If this test ever fails post-Phase-134, the cascade is back."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _has_prep_engine() -> bool:
    try:
        import prep_engine  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_prep_engine(),
    reason="prep_engine PyO3 binding not built",
)


@pytest.fixture
def pre_phase133_project(tmp_path: Path):
    """A project with a SHA-256 manifest and stub augmentations."""
    repo = tmp_path / "repo"
    repo.mkdir()
    files = {"main.py": "def main(): pass\n", "util.py": "def util(): return 1\n"}
    for name, body in files.items():
        (repo / name).write_text(body)

    idx = tmp_path / "index"
    idx.mkdir()

    # Pre-Phase-133 manifest (SHA-256-64, no hash_algo)
    manifest = {
        "version": "1.0",
        "built_at": "2026-04-01T00:00:00Z",
        "file_hashes": {
            name: hashlib.sha256(body.encode()).hexdigest()[:16]
            for name, body in files.items()
        },
    }
    (idx / "trace_manifest.json").write_text(json.dumps(manifest))

    # trace_nodes.jsonl seed
    nodes = "\n".join(
        json.dumps({"kind": "file", "file_path": name, "id": f"file:{name}"})
        for name in files
    )
    (idx / "trace_nodes.jsonl").write_text(nodes + "\n")

    # Stub augmentations with SHA-256 hashes (the pre-Phase-134 state).
    # Stored without file_hash field per Phase 134 (Task 4 deleted it),
    # but legacy entries on disk may have it — load path ignores unknowns.
    augs = [
        {"node_id": f"file:{name}", "summary": f"summary for {name}"}
        for name in files
    ]
    (idx / "trace_augmented.jsonl").write_text(
        "\n".join(json.dumps(a) for a in augs) + "\n"
    )

    return repo, idx, files


def test_no_llm_recall_on_phase133_to_134_migration(pre_phase133_project, monkeypatch):
    """Build via stage 1, then invoke the augmenter. Assert that the
    augmenter's LLM call site is NEVER invoked — every existing
    augmentation entry should be preserved because the changeset
    placed every file in `unchanged`."""
    repo, idx, files = pre_phase133_project

    # Force Python build path for deterministic test
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")

    # Stage 1: build, emit changeset
    from prep.core.trace.builder import TraceBuilder
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()

    # Verify the changeset is the migration shape (Case 3)
    from prep.services.pipeline.changeset import read_changeset
    cs = read_changeset(idx)
    assert cs is not None
    assert "main.py" in cs.unchanged, (
        f"Case 3 migration: main.py should be unchanged; got {cs.unchanged}"
    )
    assert cs.modified == frozenset(), (
        f"Case 3 migration: modified must be empty; got {cs.modified}"
    )

    # Run the augmenter — patch the LLM call site to count invocations
    from prep.core.augmenter import TraceAugmenter
    llm_call_count = MagicMock()

    # Whatever the LLM call site is named — find by inspection. Common
    # names: _augment_node, _llm_request, _call_llm. Adjust to the
    # actual method name.
    with patch.object(TraceAugmenter, "_augment_node", llm_call_count):
        augmenter = TraceAugmenter(
            repo_root=repo,
            index_dir=idx,
        )
        # Inject the changeset as WorkerFactory would
        augmenter.changeset = cs
        # Run the augmenter on the existing nodes
        augmenter.augment_all()  # or whatever the entry point is

    assert llm_call_count.call_count == 0, (
        f"Phase 134 contract violation: augmenter called LLM "
        f"{llm_call_count.call_count} times for files in changeset.unchanged. "
        f"The cache invalidation cascade is back. Investigate before merging."
    )
```

(The test's exact API depends on the augmenter's actual entry point and LLM call site names — adapt to your codebase. The contract is: zero LLM calls when the changeset places every file in `unchanged`.)

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_phase134_e2e_no_llm_recall.py -v`
Expected: PASSED. If failed, inspect the augmenter's actual code path — the test contract may need adjustment to match the exact API.

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase134_e2e_no_llm_recall.py
git commit -m "test(phase134): e2e regression — Important #3 cascade is dead

Headline test: project with pre-Phase-133 SHA-256 manifest + stub
augmentations. Stage 1 emits Case-3 migration changeset (unchanged
= everything). Augmenter is invoked, asserts zero LLM call sites
were invoked.

If this test ever fails, the cascade has returned."
```

---

### Task 17: Walker-convergence guard test

**Files:**
- Create: `tests/test_phase134_walker_convergence.py`

Greps the codebase for `os.walk` in pipeline-relevant code, asserts zero hits. Guards against future re-introduction.

- [ ] **Step 1: Write the test**

Create `tests/test_phase134_walker_convergence.py`:

```python
"""Phase 134 — guard against os.walk re-introduction in pipeline-
relevant code paths."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that may legitimately use os.walk (eval fixtures, scripts,
# tests themselves).
EXCLUSIONS = {
    "tests/eval/",
    "tests/fixtures/",
    "scripts/",
}


def test_no_os_walk_in_pipeline_code():
    """grep across the pipeline-relevant code paths for os.walk.
    Expected: zero hits. Phase 134 converges all walkers onto
    prep_engine.walk_repo."""
    result = subprocess.run(
        ["grep", "-rn", "os.walk",
         "src/prep/core/augmenter.py",
         "src/prep/core/deepening.py",
         "src/prep/core/epistemic_enrichment.py",
         "src/prep/core/epistemic_score.py",
         "src/prep/core/audit/analyzers/",
         "src/prep/core/trace/",
         "src/prep/core/repo_profile.py",
         "src/prep/core/atlas/markdown_links.py",
         "src/prep/services/pipeline/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # grep returns 1 when no matches found — that's the success case.
    if result.returncode == 0:
        # Found something — Phase 134 contract violated.
        hits = result.stdout.strip().split("\n")
        # Filter out comment-only mentions (the Phase 134 spec/comments
        # may legitimately reference os.walk by name).
        code_hits = [h for h in hits if "os.walk(" in h]
        assert not code_hits, (
            f"Phase 134 contract violation: os.walk re-appeared in "
            f"pipeline code. Use prep_engine.walk_repo instead.\n"
            f"Hits:\n  " + "\n  ".join(code_hits)
        )
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_phase134_walker_convergence.py -v`
Expected: PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase134_walker_convergence.py
git commit -m "test(phase134): guard against os.walk re-introduction in pipeline code

Greps across augmenter, deepening, enrichment, score, audit
analyzers, trace, repo_profile, atlas/markdown_links, and pipeline
services. Asserts zero os.walk hits. Tests/eval/scripts excluded."
```

---

### Task 18: Doc closes — MASTER_TODO + dogfooding follow-up

**Files:**
- Modify: `docs/MASTER_TODO.md` — append Phase 134 entry to the recent-phases index.
- Create: `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md`

- [ ] **Step 1: Append the MASTER_TODO entry**

Edit `docs/MASTER_TODO.md`. In the "Recent phases (100+) — quick index" section, after the Phase 133 entry, add:

```markdown
- Phase 134 (ChangesetDrivenPipeline) — completes what Phase 133
  was supposed to deliver: a single source of truth for "what
  changed in this run" emitted by stage 1 and consumed by every
  downstream stage. Deletes per-stage staleness checks across
  augmenter, deepening, epistemic enrichment, epistemic scoring,
  audit StalenessAnalyzer. Converges 4 remaining os.walk callers
  onto prep_engine.walk_repo. Deletes Phase 133 hot-fix
  is_hash_stale helper. Deletes ResumeStrategy.refresh_manifest_hashes
  (Critical #1 from Phase 133 review). Net diff target: -400 to
  -600 lines. **Implemented 2026-05-11**; see
  docs/Phase134_ChangesetDrivenPipeline/{README.md,IMPLEMENTATION_PLAN.md}.
```

- [ ] **Step 2: Create the dogfooding follow-up**

Create `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md`:

```markdown
---
date: 2026-05-11
session: Phase 134 spec + plan + execution review of Phase 133
author: Claude Opus 4.7
---

# 19 — Follow-up Dogfooding (2026-05-11)

Phase 134 is the architectural correction of Phase 133. This doc
captures both the Phase 133 → 134 lesson and three concrete prep MCP
gaps observed during the 2026-05-11 spec authoring session.

## 1. The Phase 133 → 134 lesson

Phase 133's stated goal was "unify the walker, single source of
truth for staleness." It shipped one walker unification (coverage
path) and one hash format migration (SHA-256 → BLAKE3). It DID NOT
delete the per-stage staleness checks. Result: a hash format change
invalidated six caches simultaneously and triggered a full LLM re-run
on unchanged content (Important #3 cascade, observed live 2026-05-10).

**Lesson:** when the goal is "single source of truth," verify by
counting independent derivation sites. Phase 133's review caught
this in concept but I deferred the fix as "follow-up." Phase 134
fixes it properly.

**Pattern to watch for in future phases:** any phase whose name
includes "unify," "single source of truth," or "delete duplication"
must include a verification step that counts the independent
sites BEFORE and AFTER. If the count didn't go down, the phase
didn't land its claim.

## 2. prep MCP gaps observed during Phase 134 spec authoring

### Gap #1: prep_search collapses to MASTER_ROADMAP.md on multi-word descriptive queries

Two different prep_search queries returned the same result with
similar low confidence:
- `"file_hash staleness compare augmentation entry"` → MASTER_ROADMAP.md (conf 0.49)
- `"incremental rebuild changed paths pipeline stage"` → MASTER_ROADMAP.md (conf 0.59)

This is the same pattern documented in 18_Followup. The intent
classifier is collapsing onto the docs hub when the query is
file-system-y but multi-word.

### Gap #2: prep_impact over-filters for hub files (now confirmed twice)

`prep_impact src/prep/core/augmenter.py direction=all` returned
4 nodes / 4 edges. The augmenter is imported by `index.py`,
`epistemic_enrichment.py`, the orchestrator, the worker factory,
and many tests — yet only 3 dependents shown. Same pattern
flagged for `server.py` in the Phase 132 follow-up. This is a
real product bug; impact analysis is supposed to be the BLAST
RADIUS and is silently understating it for the most-used files.

### Gap #3: Atlas role projection ignores task-named files

I called `prep` with a task description that explicitly named
`augmenter`, `deepening`, `epistemic_enrichment`, `audit`, plus
`working_dir=src/prep/services/pipeline`. The "RELEVANT FILES"
section returned `treatment_registry`, `swarm_orchestrator`,
`useLLMConfig`, `useTraceSystem` — none of the files I named.
The Working Area observation, by contrast, correctly surfaced the
deeply-relevant Phase 61B mtime-staleness observation.

The role projection is over-weighting the role tag ("Software
Engineer") and under-weighting the task description. Worth tuning
the relevance score so explicit file mentions dominate.

## 3. Phase 134 success criteria

The architectural correction:
- Single source of truth for "what changed in this run" — a
  Changeset object emitted by stage 1, consumed by every
  downstream stage.
- Per-stage staleness checks deleted across all 5 sites.
- 4 remaining os.walk callers converged onto prep_engine.walk_repo.
- Phase 133 hot-fix `is_hash_stale` deleted.
- Net diff target: −400 to −600 lines.

If Phase 134 ships and a future hash format change is a non-event
for stages 2-15 by construction (verifiable by trying to introduce
a new hash format and observing zero LLM re-runs), the architecture
holds.
```

- [ ] **Step 3: Commit**

```bash
git add docs/MASTER_TODO.md docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md
git commit -m "docs(phase134): MASTER_TODO entry + dogfooding follow-up

Closes the Phase 134 paper trail. The dogfooding doc documents:
1. The Phase 133 → 134 architectural-correction lesson
2. Three concrete prep MCP gaps observed during Phase 134 spec authoring
   (intent classifier collapsing to MASTER_ROADMAP, prep_impact
   over-filtering for hub files, atlas role projection ignoring
   task-named files)"
```

---

## Final verification

After Task 18, run the full Phase 134 test suite + a broader sanity sweep:

- [ ] **Verify all Phase 134 tests pass together**

Run:

```bash
.venv/bin/pytest \
  tests/test_phase134_changeset.py \
  tests/test_phase134_worker_changeset_injection.py \
  tests/test_phase134_migration_cases.py \
  tests/test_phase134_stage_cutover.py \
  tests/test_phase134_coverage_simplified.py \
  tests/test_phase134_refresh_deleted.py \
  tests/test_phase134_is_hash_stale_deleted.py \
  tests/test_phase134_e2e_no_llm_recall.py \
  tests/test_phase134_walker_convergence.py \
  -v
```

Expected: all PASSED. ~40 tests.

- [ ] **Verify Phase 133 + walker_parity still pass**

```bash
.venv/bin/pytest \
  tests/test_phase133_*.py \
  tests/test_walker_parity.py \
  --tb=no -q
```

Expected: pass (with the deleted Phase 133 tests removed in Tasks 10 + 12).

- [ ] **Adjacent-area sanity sweep**

```bash
.venv/bin/pytest tests/ -k "trace or watcher or pipeline_orchestrator or coverage or builder or manifest or augmenter or deepening or epistemic or audit or staleness" --tb=no -q --ignore=tests/eval --ignore=tests/test_summary_lint.py
```

Expected: no NEW failures. Pre-existing failures (test_trace_endpoints 409s, test_summary_lint collection error) unchanged.

- [ ] **Verify net line delta is negative**

```bash
git diff main...HEAD --stat | tail -3
```

Expected: net `−` lines. If positive, the phase didn't land its point — investigate before declaring done.

- [ ] **Restart daemon + live verification**

```bash
# Kill old daemon
PID=$(lsof -tiTCP:8400 -sTCP:LISTEN 2>/dev/null | head -1)
[ -n "$PID" ] && kill $PID && sleep 2

# Start fresh
nohup .venv/bin/python -m prep.cli serve --port 8400 > /tmp/phase134_daemon.log 2>&1 &
sleep 6

# Health check
curl -s http://localhost:8400/health

# Coverage call — should NOT trigger any rebuild (changeset is loaded from disk)
PROJ=f1636374-abc6-410d-99ee-822120379e79
curl -s "http://localhost:8400/projects/$PROJ/trace/coverage" | jq '.data.summary'

# Verify changeset.json was emitted (or will be on next stage 1 run)
ls -la ~/.local/share/sourceprep/projects/$PROJ/.sourceprep/changeset.json 2>/dev/null \
  || echo "no changeset yet — will be emitted on next pipeline run"

# Click deep_enrichment Auto and watch the augmenter NOT re-run
# (the headline live test for the cascade fix)
```

---

## Notes for the executing engineer

- **No `Co-Authored-By` trailer** in any commit (per `feedback_no_coauthored_by.md`).
- **Don't push without explicit instruction** (per `feedback_explicit_push_only.md`).
- **Use `.venv/bin/pytest` and `.venv/bin/ruff`**, not the system tools (per `feedback_use_venv.md`).
- **Daemon restart is required after each backend change you want to live-test** (per `feedback_restart_daemon_before_live_validation.md`).
- **The line numbers in this plan are based on `HEAD` at plan-write time.** If they've drifted, use `grep`/`sed` to relocate the symbol.
- **The net delta target is −400 lines minimum.** If after Task 12 the diff is positive, abort and reconsider — the phase didn't land its point.
- **The end-to-end migration smoke test (Task 16) is the canary.** If it ever fails post-implementation, the cascade has returned and the architecture is broken.
- **The `is_hash_stale` deletion (Task 12) requires zero remaining callers.** If `grep -rn is_hash_stale src/prep/` returns hits before Task 12 starts, find which earlier task missed the call site and circle back.
