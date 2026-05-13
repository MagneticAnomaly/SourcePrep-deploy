# Phase 135.5 Implementation Plan — Finish Walker + Staleness Consolidation

> **For agentic workers:** Same TDD-per-task workflow as Phase 135. Each task: write failing test → minimal impl → run → commit. No --amend. No Co-Authored-By trailer. Single commit per task. ALWAYS work in the worktree at `/Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/phase-135-5-finish` — verify `pwd` and `git branch --show-current` before every commit.

**Goal:** Eliminate the last two per-stage staleness checks (stages 2 and 11) AND consolidate the 9 walker callers behind a single `prep.core.walker` wrapper.

**Branch:** `phase-135-5-finish` (already created).

---

## Task 1 — Stage 2 (`inferred_edges`) changeset cutover

**Files:**
- Modify: `src/prep/core/inferred_edges.py`
- Modify: `src/prep/services/pipeline/workers/__init__.py` (inferred_edges worker)
- Test: `tests/test_phase135_5_inferred_edges_changeset.py` (new)

### Steps

1. Read the current shape with `grep -n "trace_inferred_hashes\|content_hash\|manifest" src/prep/core/inferred_edges.py | head -20`. The Phase 134 anti-pattern lives at:
   - `inferred_edges.py:179` — `self.manifest_path = self.index_dir / "trace_inferred_hashes.json"`
   - `inferred_edges.py:240` — `if content_hash and manifest.get(fp) == content_hash: continue`
   - `inferred_edges.py:299, 396, 455, 490` — `new_manifest[fp] = content_hash` writes
   - `inferred_edges.py:689, 708` — load/save manifest helpers

2. Write test `tests/test_phase135_5_inferred_edges_changeset.py` covering:
   - `InferredEdgesAnalyzer` (or whatever the class is — check `inferred_edges.py:145`) inherits `Worker`
   - `analyzer.changeset` defaults to `None`
   - `should_process` routes through changeset
   - A new helper `_edge_is_stale(file_path)` or equivalent returns False when file is in `changeset.unchanged`
   - `trace_inferred_hashes.json` manifest file is no longer written by run()

3. Run test, confirm failures.

4. Apply production changes:
   - Add `from prep.services.pipeline.workers.base import Worker` import.
   - Change `class InferredEdgesAnalyzer:` → `class InferredEdgesAnalyzer(Worker):`.
   - Delete `self.manifest_path` field and `_load_manifest`/`_save_manifest` helpers.
   - Replace the per-file `if content_hash and manifest.get(fp) == content_hash:` check at line 240 (and any sibling sites at 299, 396, 455, 490) with `if not self.should_process(fp): continue`.
   - Delete the `new_manifest` build-up and the save_manifest call at end of `run()`.
   - Update any docstring/log mentioning "hash manifest" to reference the changeset.

5. Wire injection in `_inferred_edges_worker` in `workers/__init__.py`. Pattern from Phase 135 Tasks 1/2/3:
   ```python
   analyzer = InferredEdgesAnalyzer(...)
   analyzer.changeset = getattr(worker, "changeset", None)
   result = analyzer.run(...)
   ```

6. Run tests:
   - `.venv/bin/pytest tests/test_phase135_5_inferred_edges_changeset.py -v`
   - `.venv/bin/pytest tests/test_phase134_*.py tests/test_phase135_*.py tests/test_deepening.py -q` (must stay green; ~90+ passing)
   - `.venv/bin/pytest tests/ -k inferred -q` (pre-existing tests unmodified)

7. Commit:
   ```
   git add tests/test_phase135_5_inferred_edges_changeset.py \
           src/prep/core/inferred_edges.py \
           src/prep/services/pipeline/workers/__init__.py
   git commit -m "feat(phase135.5): stage 2 inferred_edges consults Changeset, hash manifest deleted"
   ```

---

## Task 2 — Stage 11 (`atlas`) changeset cutover

**Files:**
- Modify: `src/prep/core/atlas/generator.py`
- Modify: `src/prep/core/atlas/models.py` (delete `fingerprint` fields)
- Modify: `src/prep/services/pipeline/workers/__init__.py` (atlas worker)
- Test: `tests/test_phase135_5_atlas_changeset.py` (new)

### Steps

1. Read current shape:
   ```
   grep -n "fingerprint\|is_stale\|_compute_fingerprint" src/prep/core/atlas/generator.py | head -20
   grep -n "fingerprint" src/prep/core/atlas/models.py
   ```

2. Write test covering:
   - `CodebaseAtlas` (the class in `generator.py` that owns `is_stale`) inherits `Worker`.
   - `atlas.changeset` defaults to `None`.
   - `atlas.is_stale()` returns True iff `changeset is None` OR `changeset.modified | changeset.deleted` is non-empty. False if all-unchanged.
   - The `fingerprint` field is gone from `AtlasDocument` (or whatever the dataclass is in `models.py`).
   - `_compute_fingerprint` is gone from `generator.py`.

3. Run test, confirm failures.

4. Apply production changes:
   - `class CodebaseAtlas(Worker):` (find the actual class in `generator.py`).
   - Replace `is_stale()` body with:
     ```python
     def is_stale(self) -> bool:
         """Phase 135.5: stale iff stage 1's Changeset has any churn at all.
         Atlas summarizes the whole project; any change is potentially atlas-
         relevant. The old 3-trigger fingerprint check is gone — fingerprint
         was the Phase 134 anti-pattern."""
         if self.changeset is None:
             return True  # defensive
         if self.changeset.modified or self.changeset.deleted:
             return True
         # All unchanged — only stale if atlas itself doesn't exist yet
         return not self.exists()
     ```
   - Delete `_compute_fingerprint` method.
   - Delete `fingerprint` field on dataclasses in `models.py` (3 occurrences per the audit — `models.py:18, 100, 158`). Update `to_dict` and `from_dict` (drop the kwarg, silently ignore on read).
   - Update docstrings.

5. Wire injection in `_atlas_worker` in `workers/__init__.py`. The atlas worker is around line 847. Pattern:
   ```python
   atlas = CodebaseAtlas(idx_dir)
   atlas.changeset = getattr(worker, "changeset", None)
   if not atlas.is_stale() and atlas.exists():
       ...skip...
   ```

6. Run tests:
   - `.venv/bin/pytest tests/test_phase135_5_atlas_changeset.py -v`
   - Full Phase 134/135/135.5 regression
   - `.venv/bin/pytest tests/ -k atlas -q` (pre-existing — adjust if any reference `fingerprint` field; conservatively, update assertions to match new shape rather than deleting tests)

7. Commit:
   ```
   git commit -m "feat(phase135.5): stage 11 atlas consults Changeset, fingerprint machinery deleted"
   ```

---

## Task 3 — New `prep.core.walker` module

**Files:**
- Create: `src/prep/core/walker.py`
- Test: `tests/test_phase135_5_walker_module.py` (new)

This task is centralization-only — no caller migrations yet. Just create the wrapper, prove it works correctly, prove the catalog merge is always applied.

### Steps

1. Write test first covering:
   - `walk_for_source(repo_root, exclude_globs=None)` returns entries (smoke test — actually walks a tiny tmp dir)
   - `walk_for_source` always merges `DEFAULT_EXCLUDE_DIR_NAMES` regardless of caller's exclude_globs (assert that `.claude/` files don't appear in output even when `exclude_globs=[]`)
   - `walk_for_source` honors caller's additional excludes (caller's `exclude_globs=["**/foo/**"]` filters foo/ files)
   - `walk_for_planning_docs(repo_root, include_agent_dirs=True)` returns entries from `.claude/`, `.cursor/`, etc. (the opposite policy)
   - `walk_for_planning_docs(repo_root, include_agent_dirs=False)` excludes agent dirs

2. Create `src/prep/core/walker.py`:

```python
"""Phase 135.5 — the single sanctioned walker.

Every file walk in prep MUST go through one of these two APIs.
Direct imports of `prep_engine.walk_repo` outside this module are
banned by `tests/test_phase135_5_walker_lockdown.py`.

Two purpose-driven APIs:

- walk_for_source     : trace pipeline / build / coverage / atlas TOC scans
- walk_for_planning_docs : concept synthesis grounding (opposite agent-dir policy)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

import prep_engine

from prep.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)

# Agent-output dirs that planning docs explicitly INCLUDE
# (the opposite of source walks, which exclude these).
_AGENT_DIRS = frozenset({".claude", ".cursor", ".agents", ".windsurf", ".copilot"})


def _baseline_excludes_for_source(
    user_exclude_globs: List[str] | None,
) -> List[str]:
    """Union L1 catalog with user-supplied excludes. User extends; never replaces."""
    merged = list(user_exclude_globs or [])
    for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
        pattern = f"**/{d}/**"
        if pattern not in merged:
            merged.append(pattern)
    for pattern in DEFAULT_EXCLUDE_FILE_GLOBS:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def walk_for_source(
    repo_root: Path | str,
    *,
    include_globs: List[str] | None = None,
    user_exclude_globs: List[str] | None = None,
    use_gitignore: bool = False,
    max_file_bytes: int | None = None,
) -> List[Any]:
    """The single sanctioned walker for source-code-style scans.

    Always applies L1 (DEFAULT_EXCLUDE_DIR_NAMES + DEFAULT_EXCLUDE_FILE_GLOBS).
    Caller-supplied `user_exclude_globs` EXTEND the catalog; they never replace it.
    """
    exclude_globs = _baseline_excludes_for_source(user_exclude_globs)
    kwargs: dict = {
        "repo_root": str(repo_root),
        "include_globs": include_globs or [],
        "exclude_globs": exclude_globs,
        "use_gitignore": use_gitignore,
    }
    if max_file_bytes is not None:
        kwargs["max_file_bytes"] = max_file_bytes
    return prep_engine.walk_repo(**kwargs)


def walk_for_planning_docs(
    repo_root: Path | str,
    *,
    include_globs: List[str] | None = None,
    include_agent_dirs: bool = True,
) -> List[Any]:
    """Walker for concept-synthesis grounding / planning-doc collection.

    By default INCLUDES agent-output dirs (.claude/, .cursor/, etc.) — the
    opposite of walk_for_source. Set include_agent_dirs=False to behave
    identically to walk_for_source w.r.t. agent dirs.
    """
    base_excludes: List[str] = []
    for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
        if include_agent_dirs and d in _AGENT_DIRS:
            continue  # explicitly DON'T exclude agent dirs in this mode
        base_excludes.append(f"**/{d}/**")
    base_excludes.extend(DEFAULT_EXCLUDE_FILE_GLOBS)
    return prep_engine.walk_repo(
        repo_root=str(repo_root),
        include_globs=include_globs or ["**/*.md", "**/*.markdown"],
        exclude_globs=base_excludes,
        use_gitignore=False,
    )
```

3. Verify the test passes (with a temp repo containing both regular and `.claude/` files).

4. Phase 134/135/135.5 regression check.

5. Commit:
   ```
   git commit -m "feat(phase135.5): introduce prep.core.walker — single sanctioned walker"
   ```

---

## Task 4 — Migrate trace/builder.py + trace/coverage.py + atlas/markdown_links.py

**Files:**
- Modify: `src/prep/core/trace/builder.py` (2 call sites)
- Modify: `src/prep/core/trace/coverage.py` (1 call site)
- Modify: `src/prep/core/atlas/markdown_links.py` (1 call site)

Each call site currently does some form of:
```python
import prep_engine
entries = prep_engine.walk_repo(repo_root=..., include_globs=..., exclude_globs=...)
```
plus an inline merge of `DEFAULT_EXCLUDE_DIR_NAMES`.

Replace each with:
```python
from prep.core.walker import walk_for_source
entries = walk_for_source(repo_root, include_globs=..., user_exclude_globs=...)
```

Delete the inline `DEFAULT_EXCLUDE_DIR_NAMES` merge — the wrapper does it now.

### Steps

1. Find each call site exactly (the line numbers in the spec are approximate).
2. Per file: replace the `prep_engine.walk_repo` call + inline merge with `walk_for_source(...)`.
3. Delete now-unused imports (`prep_engine`, `DEFAULT_EXCLUDE_DIR_NAMES`, `DEFAULT_EXCLUDE_FILE_GLOBS`) IF nothing else in the file uses them.
4. Run tests:
   - `.venv/bin/pytest tests/test_phase134_*.py tests/test_phase135_*.py tests/test_phase135_5_*.py tests/test_deepening.py -q`
   - `.venv/bin/pytest tests/test_trace_coverage*.py tests/test_atlas*.py tests/test_trace_*.py -q`
5. Commit:
   ```
   git commit -m "feat(phase135.5): migrate trace/atlas walkers to prep.core.walker"
   ```

---

## Task 5 — Migrate repo_profile.py (2 callers) + orchestrator.py:2715

**Files:**
- Modify: `src/prep/core/repo_profile.py` (2 call sites: `scan_for_presets:289`, `_iter_repo_files:381`)
- Modify: `src/prep/services/pipeline/orchestrator.py` (1 call site at line 2715, currently bypasses catalog)

The orchestrator call is a "count up to 5 files to confirm repo isn't empty" sanity check. It currently inlines `_EXCL_GLOBS = ["**/.*/**", ...]` without the full catalog. Migrating to `walk_for_source` applies the catalog — almost certainly correct, but verify file counts don't change unexpectedly.

### Steps

1. For each call site, replace with `walk_for_source` (use_gitignore propagation as needed).
2. Special attention on orchestrator.py:2715: the `_EXCL_GLOBS` list and the `_CODE_GLOBS` list. The latter becomes `include_globs=_CODE_GLOBS`. The former is now redundant (walker baseline includes `.git`, `node_modules`, `__pycache__`, etc.).
3. Run all tests + the pipeline-specific suite.
4. Commit:
   ```
   git commit -m "feat(phase135.5): migrate repo_profile + orchestrator sanity-count to prep.core.walker"
   ```

---

## Task 6 — Migrate project_helpers.py raw os.walk + docs_grounding.py independent walker

**Files:**
- Modify: `src/prep/services/project_helpers.py` (raw `os.walk` at line 548)
- Modify: `src/prep/core/docs_grounding.py` (`_walk_md_files` at line 282)

### Steps

1. **project_helpers.py:548** — read context first. Determine what the walk is for (looks like a source-style scan based on the surroundings). Replace with `walk_for_source(...)`. If the original loop iterated `(root_dir, dirs, filenames)`, adapt to iterate the walker's entries instead.

2. **docs_grounding.py:282** — read `_walk_md_files`. It's a pathlib-based walker that explicitly includes `.claude/`, `.cursor/`, etc. (the opposite policy). Replace its body with `walk_for_planning_docs(root, include_agent_dirs=True)`. Keep the function as a thin wrapper if other code calls `_walk_md_files` directly.

3. Run tests including any docs_grounding tests and project_helpers tests.

4. Commit:
   ```
   git commit -m "feat(phase135.5): migrate project_helpers + docs_grounding walkers to prep.core.walker"
   ```

---

## Task 7 — Lockdown test + verification

**Files:**
- Test: `tests/test_phase135_5_walker_lockdown.py` (new)

Asserts no file other than `src/prep/core/walker.py` and the test files themselves imports `prep_engine` for walking. Anyone re-introducing a direct `prep_engine.walk_repo` call gets caught at CI.

### Test content

```python
"""Phase 135.5 lockdown — no file outside prep.core.walker may import
prep_engine for walking. If you re-introduce a direct prep_engine
import, this test fails — by design.

Exempt: prep.core.walker itself (the wrapper), test files."""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "prep"


def test_no_direct_prep_engine_imports_outside_walker_module() -> None:
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        if py.name == "walker.py" and py.parent.name == "core":
            continue  # the sanctioned home
        body = py.read_text(encoding="utf-8", errors="ignore")
        # Allow inline mentions inside comments / docstrings; the test
        # specifically guards against `import prep_engine` and
        # `from prep_engine import` statements.
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if (
                stripped == "import prep_engine"
                or stripped.startswith("import prep_engine as ")
                or stripped.startswith("from prep_engine ")
                or "prep_engine.walk_repo" in stripped
                or "_prep_engine.walk_repo" in stripped
            ):
                offenders.append(f"{py.relative_to(SRC.parents[1])}: {stripped}")
                break
    assert not offenders, (
        "Direct prep_engine usage outside prep.core.walker is banned by Phase 135.5. "
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_walker_module_is_the_only_prep_engine_consumer() -> None:
    """Smoke check: prep.core.walker DOES import prep_engine."""
    walker = SRC / "core" / "walker.py"
    assert walker.exists()
    body = walker.read_text(encoding="utf-8")
    assert "import prep_engine" in body
```

### Steps

1. Create the test.
2. Run it. If anything fails, fix the offender (it's a Phase 135.5 task that didn't migrate cleanly).
3. Run the FULL test suite one more time to confirm everything green.
4. Commit:
   ```
   git commit -m "test(phase135.5): lockdown — prep.core.walker is the sole prep_engine consumer"
   ```

---

## Done criteria

After Task 7:

- `git grep -l "import prep_engine" src/prep/` returns exactly **`src/prep/core/walker.py`** (no other files).
- `git grep "prep_engine.walk_repo\|_prep_engine.walk_repo" src/prep/` returns matches only inside `walker.py` and comments.
- `git grep "trace_inferred_hashes\|_compute_fingerprint" src/prep/core/` returns 0.
- `git grep "fingerprint" src/prep/core/atlas/models.py src/prep/core/atlas/generator.py` returns 0 (or only explanatory comments).
- All Phase 134/135/135.5 tests pass.
- Pre-existing tests unchanged (or minimally updated to match new shape).

After merge to main: restart daemon, trigger a full rebuild, verify stages 2 and 11 reuse correctly on a no-change rerun.
