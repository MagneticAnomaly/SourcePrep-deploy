# Phase 133 — Rust Walker/Hasher Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Python's `os.walk` + `fnmatch` + `hashlib.sha256` with the existing Rust `prep-walker` primitives (`prep_engine.walk_repo`, `prep_engine.hash_content`) on the Graph Scope coverage path. Eliminates the 6-surface filter divergence between `compute_trace_coverage` and the structural rebuild walker. Adds a `hash_algo` field to manifests for self-healing migration from SHA-256-64 to BLAKE3-128.

**Architecture:** Python orchestrates and categorizes; Rust does the disk-touching primitives. The Rust `walk_repo` returns a `FileEntry` list in one PyO3 boundary crossing; Python then categorizes each entry into `traced` / `untraced` / `stale` / `excluded` / `pending_embedding` lists by comparing against the loaded manifest. Hash comparison uses BLAKE3-128 going forward; pre-cutover SHA-256-64 manifests are detected via the new `hash_algo` field and self-heal on next rebuild.

**Tech Stack:** Python 3.11 (FastAPI/asyncio backend), Rust (PyO3 bindings via `prep_engine`), pytest (asyncio_mode = "auto"), ruff/mypy.

**Read first (the engineer needs this context):**
- The spec: `docs/Phase133_RustWalkerHasherCutover/README.md` — design rationale, divergence map, hash format problem, Migration Path A.
- The Rust walker entry point: `engine/crates/prep-walker/src/lib.rs:180` (`walk_repo` function) and `engine/crates/prep-walker/src/lib.rs:322` (`hash_content`). The PyO3 bindings are at `engine/crates/prep-engine/src/lib.rs:34` (walk_repo) and `:91` (hash_content).
- The current Python coverage implementation: `src/prep/core/trace/coverage.py` — focus on the `compute_trace_coverage` function (lines 31-393), especially the `os.walk` block at line 236 and the `fnmatch` blocks at lines 256-303. The hash-compare branch at lines 332-364 is what gains the self-heal.
- The current builder: `src/prep/core/trace/builder.py` — focus on `_build_python` (line ~189), `_build_rust` (line 365), and `_compute_file_hashes` (line 466).
- The "preserve + merge" defensive logic that this phase keeps but neutralizes: `src/prep/core/trace/builder.py:375-388, 451-457`.
- Existing parity test (string-only): `tests/test_walker_parity.py` — Phase 115 Step 9 baseline.
- Project memories worth respecting: `feedback_no_coauthored_by.md` (no Co-Authored-By trailer), `feedback_use_venv.md` (use `.venv/bin/pytest`), `feedback_test_full_import_chain.md` (at least one test must not mock the Python/Rust seam), `feedback_restart_daemon_before_live_validation.md` (daemon has no hot-reload).

**Worktree:** Run this work on a dedicated branch (e.g., `phase-133-rust-walker-cutover`) created via `superpowers:using-git-worktrees`. The default branch should remain shippable throughout.

---

## File structure

| File | Responsibility | Change type |
|---|---|---|
| `src/prep/core/manifest.py` | Manifest schema definition | Modify — add `hash_algo` parameter to `build_manifest`, add `CURRENT_HASH_ALGO` module constant |
| `src/prep/core/trace/coverage.py` | Walks filesystem, categorizes files into traced/stale/untraced/excluded/pending_embedding | Modify — swap `os.walk` + `fnmatch` for `prep_engine.walk_repo`; swap `stable_file_hash` for `prep_engine.hash_content`; add `hash_algo` self-heal branch |
| `src/prep/core/trace/builder.py` | Builds the trace graph (Python and Rust paths) | Modify — swap `stable_file_hash` for `prep_engine.hash_content`; pass `hash_algo` to `build_manifest`; migrate `_compute_file_hashes` to `prep_engine.walk_repo`; add temporary assertion at merge site |
| `tests/fixtures/walker_parity_repo/` | Git-tracked fixture exposing all 6 divergence surfaces + Phase 125c bimodal trigger files | Create — directory of small text files |
| `tests/test_walker_parity.py` | Behavior-parity tests over the fixture (extends Phase 115 string-parity tests) | Modify — add behavior tests including Phase 125c bimodal pair |
| `tests/test_phase133_hash_migration.py` | End-to-end self-heal test | Create |
| `tests/test_phase133_coverage_uses_rust_walker.py` | Locks the cutover (mock-based contract test) | Create |
| `tests/test_phase133_hidden_dirs.py` | Regression guard for divergence #2 (`.github/workflows/*`) | Create |
| `tests/test_phase133_max_files_warning.py` | Regression guard for divergence #5 (cap surface) | Create |
| `docs/MASTER_TODO.md` | Cross-phase index | Modify — append Phase 133 entry |
| `docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md` | Dogfooding doc | Modify — closing note that filter divergence root cause closed in Phase 133 |

---

## Task ordering

This plan is ordered so each task lands a complete, testable feature increment. The dependency chain:

1. Schema first (Task 1) — non-breaking add of `hash_algo` field.
2. Fixture second (Task 2) — required for every behavior-parity test that follows.
3. Walker cutover (Task 3) — moves coverage to `prep_engine.walk_repo`.
4. Hash cutover with self-heal (Task 4) — moves coverage to `prep_engine.hash_content` and adds the migration branch.
5. Builder hash cutover (Task 5) — same hash swap on the writer side.
6. Builder walker cutover (Task 6) — `_compute_file_hashes` joins coverage on the same primitive.
7. Defensive assertion (Task 7) — proves the merge produces zero additions before we delete the safety net.
8. Hidden-dirs regression test (Task 8) — divergence #2 explicit guard.
9. Phase 125c bimodal walker test (Task 9) — locks the doc-discovery forward-look.
10. max_files cap surfacing (Task 10) — divergence #5 explicit guard.
11. Doc closes (Task 11).

---

### Task 1: Add `CURRENT_HASH_ALGO` shared constant and forward-proof embedding manifest

**Files:**
- Modify: `src/prep/core/manifest.py` — add `CURRENT_HASH_ALGO` module constant; add `hash_algo` parameter to `build_manifest` (the embedding manifest builder).
- Test: `tests/test_phase133_manifest_hash_algo.py` (new)

**Important context — the codebase has TWO `build_manifest` symbols:**

| Symbol | What it builds | Read by |
|---|---|---|
| `prep.core.manifest.build_manifest` (function) | Embedding/CodeIndex manifest (`model`, `embedding_dim`, `build`, etc.) | `index.py`, `knowledge.py` |
| `TraceBuilder._build_manifest` (instance method, `src/prep/core/trace/builder.py:593`) | **Trace manifest (`trace_manifest.json`) — the one `compute_trace_coverage` reads** | `coverage.py` (Phase 133's load-bearing target) |

This task only touches the **embedding manifest** function and adds the shared constant. The trace manifest's `_build_manifest` instance method is updated in Task 5 (where it's actually load-bearing for Phase 133).

The forward-proofing modification to the embedding manifest's `build_manifest` is harmless — no current consumer compares its `file_hashes` for staleness — but landing the field now means a future phase that migrates the embedding manifest to BLAKE3 inherits Path A self-heal for free.

- [ ] **Step 1: Read the current `build_manifest` to find the parameter list and emission block**

Run: `sed -n '50,95p' src/prep/core/manifest.py`
Expected: shows the function signature (kw-only params: `model`, `embedding_dim`, `roots`, `count`, `build`, `config`, `file_hashes`, `version`, `built_at`) and the conditional `m["file_hashes"] = dict(file_hashes)` emission.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase133_manifest_hash_algo.py`:

```python
"""Phase 133 — embedding manifest forward-proofs the hash_algo field
+ CURRENT_HASH_ALGO shared constant lives here. Note: the trace
manifest (the one Phase 133 actually depends on) is built by
TraceBuilder._build_manifest, tested in test_phase133_builder_writes_hash_algo.py.
"""
from __future__ import annotations

from prep.core.manifest import CURRENT_HASH_ALGO, ManifestBuildStats, build_manifest


def test_current_hash_algo_constant_is_blake3_128():
    """The cutover target. Phase 133 establishes BLAKE3-128 as the post-cutover algo."""
    assert CURRENT_HASH_ALGO == "blake3-128"


def _stats() -> ManifestBuildStats:
    """Minimal stats tuple required by the embedding manifest builder."""
    return ManifestBuildStats(
        mode="full",
        files_total=0,
        files_reused=0,
        files_embedded=0,
    )


def test_embedding_manifest_emits_hash_algo_when_provided():
    m = build_manifest(
        model="test-model",
        embedding_dim=64,
        roots=["/tmp/repo"],
        count=0,
        build=_stats(),
        config={},
        file_hashes={"src/foo.py": "deadbeef" * 4},
        hash_algo="blake3-128",
    )
    assert m["hash_algo"] == "blake3-128"
    assert m["file_hashes"] == {"src/foo.py": "deadbeef" * 4}


def test_embedding_manifest_omits_hash_algo_when_not_provided():
    """Back-compat: existing callers that don't pass hash_algo get the
    same manifest shape they get today."""
    m = build_manifest(
        model="test-model",
        embedding_dim=64,
        roots=["/tmp/repo"],
        count=0,
        build=_stats(),
        config={},
    )
    assert "hash_algo" not in m
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase133_manifest_hash_algo.py -v`
Expected: FAIL with `ImportError: cannot import name 'CURRENT_HASH_ALGO' from 'prep.core.manifest'`.

- [ ] **Step 4: Implement the schema change**

Edit `src/prep/core/manifest.py`. Add the constant near the top of the module (after the imports / before `MANIFEST_VERSION`):

```python
CURRENT_HASH_ALGO = "blake3-128"
"""Phase 133: post-cutover hash algorithm tag for prep manifests
that store ``file_hashes``. The trace manifest
(``TraceBuilder._build_manifest``) writes this constant unconditionally.
The embedding manifest (``build_manifest`` below) accepts it as an
optional parameter so a future phase can adopt the same self-healing
migration without a schema change."""
```

Then modify `build_manifest`'s signature — add `hash_algo: Optional[str] = None` next to `file_hashes`, and add the emission block alongside the existing `file_hashes` emission:

```python
def build_manifest(
    *,
    model: str,
    embedding_dim: int,
    roots: list[str],
    count: int,
    build: ManifestBuildStats,
    config: Dict[str, Any],
    file_hashes: Optional[Dict[str, str]] = None,
    hash_algo: Optional[str] = None,           # ← NEW
    version: str = MANIFEST_VERSION,
    built_at: Optional[str] = None,
) -> Dict[str, Any]:
    m: Dict[str, Any] = {
        # ... existing fields unchanged ...
    }
    if file_hashes is not None:
        m["file_hashes"] = dict(file_hashes)
    if hash_algo is not None:                  # ← NEW
        m["hash_algo"] = hash_algo
    return m
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_manifest_hash_algo.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Verify nothing else broke**

Run: `.venv/bin/pytest tests/ -k "manifest" -v 2>&1 | tail -20`
Expected: all manifest-related tests pass.

- [ ] **Step 7: Lint check**

Run: `.venv/bin/ruff check src/prep/core/manifest.py tests/test_phase133_manifest_hash_algo.py`
Expected: no new errors.

- [ ] **Step 8: Commit**

```bash
git add src/prep/core/manifest.py tests/test_phase133_manifest_hash_algo.py
git commit -m "feat(phase133): add CURRENT_HASH_ALGO constant + embedding-manifest hash_algo field

CURRENT_HASH_ALGO='blake3-128' is the shared constant. Embedding
manifest (build_manifest) gains an optional hash_algo parameter for
forward-proofing; no current consumer compares its file_hashes for
staleness, but a future phase migrating the embedding manifest to
BLAKE3 inherits Path A self-heal automatically.

Note: trace manifest (TraceBuilder._build_manifest) — the one Phase 133
actually depends on — is updated in Task 5."
```

---

### Task 2: Build the walker-parity test fixture

**Files:**
- Create: `tests/fixtures/walker_parity_repo/` and its contents (see file tree below)

The fixture exposes the six divergence surfaces from the spec plus the Phase 125c bimodal trigger files. No tests yet; this task just creates the inputs that subsequent tasks will assert against.

- [ ] **Step 1: Create the fixture directory**

```bash
mkdir -p tests/fixtures/walker_parity_repo/{src,deep/nested/path,sub/with_gitignore,.github/workflows,.cursor/rules}
```

- [ ] **Step 2: Create the divergence-trigger files**

Create each of these files (the contents themselves don't matter much — they just need to exist):

```bash
# Divergence #1 trigger — `**/*.py` deep in tree (fnmatch fails on this)
echo 'def deep(): return 1' > tests/fixtures/walker_parity_repo/deep/nested/path/leaf.py

# Divergence #2 trigger — hidden dir not in default exclude_globs
mkdir -p tests/fixtures/walker_parity_repo/.github/workflows
cat > tests/fixtures/walker_parity_repo/.github/workflows/ci.yml <<'EOF'
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps: [{uses: actions/checkout@v4}]
EOF

# Divergence #3 trigger — basename match vs path match
echo '{"name": "stub"}' > tests/fixtures/walker_parity_repo/package-lock.json

# Divergence #6 trigger — nested .gitignore
echo '*.tmp' > tests/fixtures/walker_parity_repo/sub/with_gitignore/.gitignore
echo "should be ignored" > tests/fixtures/walker_parity_repo/sub/with_gitignore/secret.tmp
echo "should appear" > tests/fixtures/walker_parity_repo/sub/with_gitignore/visible.py

# Phase 125c forward-look — files that source-indexing excludes but doc-discovery should find
echo '# Project Instructions' > tests/fixtures/walker_parity_repo/CLAUDE.md
cat > tests/fixtures/walker_parity_repo/.cursor/rules/sample.mdc <<'EOF'
---
description: Sample cursor rule
---
Some rule body.
EOF

# Normal source files (control — should always appear)
echo 'def main(): pass' > tests/fixtures/walker_parity_repo/src/main.py
echo '# Test repo' > tests/fixtures/walker_parity_repo/README.md
```

- [ ] **Step 3: Verify file tree**

Run: `find tests/fixtures/walker_parity_repo -type f | sort`
Expected output (10 files):

```
tests/fixtures/walker_parity_repo/.cursor/rules/sample.mdc
tests/fixtures/walker_parity_repo/.github/workflows/ci.yml
tests/fixtures/walker_parity_repo/CLAUDE.md
tests/fixtures/walker_parity_repo/README.md
tests/fixtures/walker_parity_repo/deep/nested/path/leaf.py
tests/fixtures/walker_parity_repo/package-lock.json
tests/fixtures/walker_parity_repo/src/main.py
tests/fixtures/walker_parity_repo/sub/with_gitignore/.gitignore
tests/fixtures/walker_parity_repo/sub/with_gitignore/secret.tmp
tests/fixtures/walker_parity_repo/sub/with_gitignore/visible.py
```

- [ ] **Step 4: Document the fixture**

Create `tests/fixtures/walker_parity_repo/README.md`:

```markdown
# Walker parity fixture

Phase 133 (Rust Walker/Hasher Cutover). Each file targets one of the six
divergence surfaces or the Phase 125c forward-look. Do NOT add files
without updating `tests/test_walker_parity.py` — every file here is
load-bearing for at least one assertion.

| File | Surface | Expected behavior (default exclude set) |
|---|---|---|
| `deep/nested/path/leaf.py` | #1 glob engine — recursive `**/*.py` | included |
| `.github/workflows/ci.yml` | #2 hidden dirs | included (no default exclude for `.github/`) |
| `package-lock.json` | #3 glob anchor | excluded (`**/*.lock`-style default) |
| `sub/with_gitignore/.gitignore` | #6 nested gitignore | scaffolding for the next two |
| `sub/with_gitignore/secret.tmp` | #6 nested gitignore | excluded (per the nested .gitignore) |
| `sub/with_gitignore/visible.py` | #6 nested gitignore | included |
| `CLAUDE.md` | Phase 125c — source-indexing exclude | excluded by default; included when caller drops the AI-rule excludes |
| `.cursor/rules/sample.mdc` | Phase 125c — source-indexing exclude | excluded by default; included when caller drops the AI-rule excludes |
| `src/main.py` | control | included |
| `README.md` | control | included |
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/walker_parity_repo/
git commit -m "test(phase133): add walker parity fixture covering 6 divergence surfaces

Fixture targets each surface explicitly (recursive glob, hidden dirs,
glob anchor, nested gitignore) plus the Phase 125c bimodal trigger
files (CLAUDE.md, .cursor/rules/sample.mdc). README documents which
file targets which surface."
```

---

### Task 3: Switch `compute_trace_coverage` discovery to `prep_engine.walk_repo`

**Files:**
- Modify: `src/prep/core/trace/coverage.py` — replace the `os.walk` + `fnmatch` block (currently lines ~227-303). Categorization stays in Python.
- Test: `tests/test_phase133_coverage_uses_rust_walker.py` (new)
- Test: extend `tests/test_walker_parity.py` with behavior-parity tests against the fixture

This is the headline cutover. After this task, the Graph Scope panel and the rebuild walk via the same Rust primitive — divergences #1, #2, #3, and #6 are killed by construction. Hashing is still SHA-256 (Task 4 swaps that).

- [ ] **Step 1: Read the current `compute_trace_coverage` discovery block to know what to replace**

Run: `sed -n '227,310p' src/prep/core/trace/coverage.py`
Expected: shows the `_PRUNE_DIRS` constant, the `os.walk` loop, the `fnmatch` include/exclude blocks, and the `is_user_excluded` block. Note the line numbers — they may have drifted since the spec was written.

- [ ] **Step 2: Write the contract test for the cutover**

Create `tests/test_phase133_coverage_uses_rust_walker.py`:

```python
"""Phase 133 — coverage discovery routes through prep_engine.walk_repo.

Mock-based contract test. Locks in the cutover at the Python/Rust seam
so subsequent refactors can't accidentally regress to os.walk + fnmatch.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.trace.coverage import compute_trace_coverage


@pytest.fixture
def empty_index(tmp_path: Path):
    """Minimal index_dir with an empty trace_manifest.json."""
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "file_hashes": {},
    }))
    return idx


def test_compute_trace_coverage_calls_prep_engine_walk_repo(tmp_path, empty_index):
    """The cutover. compute_trace_coverage must delegate file discovery
    to the Rust walker; it must not call os.walk for the eligibility
    set anymore."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    with patch("prep_engine.walk_repo") as mock_walk:
        # Return a single FileEntry-shaped object. The real binding
        # returns a list of objects with .path / .abs_path / .size /
        # .modified_secs attributes; coverage iterates them.
        class _StubEntry:
            def __init__(self, path, abs_path, size, modified_secs):
                self.path = path
                self.abs_path = abs_path
                self.size = size
                self.modified_secs = modified_secs

        mock_walk.return_value = [
            _StubEntry(
                path="main.py",
                abs_path=str(repo / "main.py"),
                size=18,
                modified_secs=0.0,
            ),
        ]

        compute_trace_coverage(
            repo_root=repo,
            index_dir=empty_index,
            include_globs=["**/*.py"],
            exclude_globs=[],
            user_exclude_globs=[],
            max_file_bytes=500_000,
        )

    assert mock_walk.called, "compute_trace_coverage must call prep_engine.walk_repo"
    # First positional arg must be the repo root as a string.
    args, kwargs = mock_walk.call_args
    walk_root = args[0] if args else kwargs.get("root")
    assert str(walk_root) == str(repo)
```

- [ ] **Step 3: Extend `tests/test_walker_parity.py` with the behavior-parity test**

Append to `tests/test_walker_parity.py`:

```python
# ── Phase 133: behavior parity over the divergence-trigger fixture ──

import json
from pathlib import Path
from prep.core.trace.coverage import compute_trace_coverage

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "walker_parity_repo"


def _coverage_paths(*, include_globs, exclude_globs):
    """Run compute_trace_coverage on the fixture, return the union of
    traced+untraced+stale+excluded paths. (We don't care about the
    categorization here — only the discovery set.)"""
    # Fresh index dir per call so the cached manifest doesn't leak.
    import tempfile
    idx = Path(tempfile.mkdtemp())
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))
    result = compute_trace_coverage(
        repo_root=FIXTURE,
        index_dir=idx,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )
    paths = set()
    for key in ("traced", "untraced", "stale", "excluded", "pending_embedding"):
        for entry in result.get(key, []):
            paths.add(entry["path"])
    return paths


def test_recursive_py_glob_picks_up_deep_files() -> None:
    """Divergence #1: stdlib fnmatch fails on `**/*.py` against
    `deep/nested/path/leaf.py`. Rust globset succeeds."""
    paths = _coverage_paths(include_globs=["**/*.py"], exclude_globs=[])
    assert "deep/nested/path/leaf.py" in paths


def test_hidden_github_workflow_visible() -> None:
    """Divergence #2: Python's `not d.startswith('.')` prune drops
    `.github/workflows/ci.yml`. Rust walker doesn't prune hidden dirs."""
    paths = _coverage_paths(include_globs=["**/*.yml", "**/*.py"], exclude_globs=[])
    assert ".github/workflows/ci.yml" in paths


def test_nested_gitignore_honored() -> None:
    """Divergence #6: nested .gitignore must apply. visible.py appears,
    secret.tmp does not."""
    paths = _coverage_paths(include_globs=["**/*.py", "**/*.tmp"], exclude_globs=[])
    assert "sub/with_gitignore/visible.py" in paths
    assert "sub/with_gitignore/secret.tmp" not in paths


def test_max_files_cap_respected() -> None:
    """Divergence #5: walker caps at 100k. Fixture is small, so just
    confirm the response shape doesn't error when called normally.
    The cap-WARNING surface is tested in test_phase133_max_files_warning.py."""
    paths = _coverage_paths(include_globs=["**/*.py"], exclude_globs=[])
    assert len(paths) > 0, "expected at least one .py file from the fixture"
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `.venv/bin/pytest tests/test_phase133_coverage_uses_rust_walker.py tests/test_walker_parity.py -v`
Expected: the cutover contract test FAILS (`compute_trace_coverage` doesn't call `prep_engine.walk_repo` yet). The behavior-parity tests may also FAIL (especially `test_recursive_py_glob_picks_up_deep_files` — fnmatch can't match it) and `test_hidden_github_workflow_visible` (Python prunes hidden dirs).

- [ ] **Step 5: Implement the cutover in `compute_trace_coverage`**

Edit `src/prep/core/trace/coverage.py`. Replace the `os.walk` block (currently around lines 227-303) with a `prep_engine.walk_repo` call. Keep everything else (manifest load, backfill block, hash compare, categorization, sorting).

The replacement block looks like this — drop it in place of the `os.walk` loop and the per-file include/exclude/user-exclude logic:

```python
# Phase 133: discovery via the Rust walker. Replaces the previous
# os.walk + fnmatch implementation (which diverged from the Rust
# walker on six surfaces; see Phase 133 spec). User-configurable
# excludes still go through the same exclude_globs argument; the
# Rust walker honors gitignore (root + nested + global + git_exclude)
# and applies include/exclude globs via globset/gitwildmatch.
import prep_engine

# walk_repo expects a string root.
entries = prep_engine.walk_repo(
    str(repo_root),
    include_globs=list(include_globs) if include_globs else None,
    exclude_globs=list(exclude_globs) if exclude_globs else None,
    max_file_bytes=int(max_file_bytes),
)

# user_exclude_globs is the user's "shown in Excluded list" surface —
# applied on top of the walker's output, not as an exclusion to the
# walker (so the user sees what they manually excluded).
import pathspec
user_exclude_spec = (
    pathspec.PathSpec.from_lines("gitwildmatch", user_exclude_globs)
    if user_exclude_globs else None
)

for entry in entries:
    rel_path = entry.path  # already POSIX, repo-relative per walker contract
    file_path = Path(entry.abs_path)

    # Backfill carve-out: even if a file isn't in the walker's output,
    # if it's in manifest_hashes we still include it (the walker may
    # have current globs narrower than what the manifest was built
    # with). Note: this loop only sees walker-included files; the
    # carve-out for manifest-only files happens in a separate pass
    # below.
    pass  # categorization continues — see existing code

    # User-excluded surface (shown in 'excluded' list)
    is_user_excluded = bool(
        user_exclude_spec and user_exclude_spec.match_file(rel_path)
    )

    # Stat for timestamps (the walker provides size + modified_secs;
    # use them when possible).
    file_size = int(entry.size)
    modified_ts = (
        datetime.fromtimestamp(entry.modified_secs, tz=timezone.utc).isoformat()
        if entry.modified_secs else "1970-01-01T00:00:00+00:00"
    )
    try:
        created_ts = (
            datetime.fromtimestamp(file_path.stat().st_birthtime, tz=timezone.utc).isoformat()
            if file_path.exists() and hasattr(file_path.stat(), "st_birthtime")
            else modified_ts
        )
    except OSError:
        created_ts = modified_ts

    language = _detect_language(rel_path)

    file_info: Dict[str, Any] = {
        "path": rel_path,
        "language": language,
        "size": file_size,
        "modified": modified_ts,
        "created": created_ts,
    }

    if is_user_excluded:
        excluded_files.append(file_info)
        continue

    # Hash-compare branch (existing logic — unchanged in this task;
    # Task 4 swaps the hash function).
    prev_hash = manifest_hashes.get(rel_path)
    if prev_hash is None:
        untraced_files.append(file_info)
    else:
        # ... existing needs_hash / mtime fast-path / hash compare ...
        # (Keep the existing hash-compare block here.)
        pass

# Backfill carve-out pass: any file in manifest_hashes that the
# walker didn't return AND that still exists on disk goes through
# the same hash compare. Preserves the prior "if rel_path not in
# manifest_hashes: continue" carve-out behavior at the categorization
# layer instead of the discovery filter.
walker_paths = {e.path for e in entries}
for rel_path in manifest_hashes.keys() - walker_paths:
    abs_p = repo_root / rel_path
    if not abs_p.exists():
        continue
    # ... emit a file_info and run the same hash compare as above ...
```

(The exact integration with the existing categorization code requires preserving the hash-compare block, the mtime fast-path at lines ~338-365, and the lists `traced_files` / `untraced_files` / `stale_files` / `excluded_files` / `pending_embedding`. Keep all of those. The change is purely the discovery loop's source of `rel_path`.)

- [ ] **Step 6: Run the cutover contract test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_coverage_uses_rust_walker.py -v`
Expected: 1 PASSED.

- [ ] **Step 7: Run the behavior-parity tests**

Run: `.venv/bin/pytest tests/test_walker_parity.py -v`
Expected: all PASSED including the new `test_recursive_py_glob_picks_up_deep_files`, `test_hidden_github_workflow_visible`, `test_nested_gitignore_honored`.

- [ ] **Step 8: Run the full coverage test suite to catch regressions**

Run: `.venv/bin/pytest tests/ -k "coverage or trace" -v 2>&1 | tail -30`
Expected: all PASSED (or pre-existing failures unchanged — note them).

- [ ] **Step 9: Lint check**

Run: `.venv/bin/ruff check src/prep/core/trace/coverage.py tests/test_phase133_coverage_uses_rust_walker.py tests/test_walker_parity.py`
Expected: no new errors.

- [ ] **Step 10: Commit**

```bash
git add src/prep/core/trace/coverage.py tests/test_phase133_coverage_uses_rust_walker.py tests/test_walker_parity.py
git commit -m "feat(phase133): cutover compute_trace_coverage discovery to prep_engine.walk_repo

Replaces os.walk + fnmatch with the same Rust walker the structural
rebuild already uses. Kills divergences #1 (recursive globs), #2
(hidden dirs), #3 (glob anchor), #6 (nested .gitignore) by
construction. Backfill carve-out moves to the categorization layer.
Hashing still SHA-256 (Task 4 swaps that).

Tests: test_phase133_coverage_uses_rust_walker (mock contract);
test_walker_parity (behavior parity over the fixture)."
```

---

### Task 4: Swap `compute_trace_coverage` hashing to `prep_engine.hash_content` and add `hash_algo` self-heal

**Files:**
- Modify: `src/prep/core/trace/coverage.py` — replace the two `stable_file_hash(source)` calls (currently lines ~163 and ~354) with `prep_engine.hash_content(source)`. Add the `hash_algo` mismatch self-heal branch.
- Test: `tests/test_phase133_hash_migration.py` (new)

This is Migration Path A. After this task lands, an existing project's pre-cutover manifest (SHA-256-64) is detected on first coverage call → all files marked stale once → next structural rebuild rewrites the manifest with `hash_algo: "blake3-128"` and BLAKE3 hashes.

- [ ] **Step 1: Locate the two hash-compute sites**

Run: `grep -n "stable_file_hash" src/prep/core/trace/coverage.py`
Expected: two hits — one in the backfill block (around line 163), one in the per-file hash compare (around line 354).

- [ ] **Step 2: Write the failing migration test**

Create `tests/test_phase133_hash_migration.py`:

```python
"""Phase 133 — Migration Path A self-heal test.

Pre-cutover manifest has hash_algo="sha256-64" (or absent → defaulted
to that). On first coverage call after the cutover, all hashed files
must be marked stale without computing the current hash. After a
structural rebuild rewrites the manifest with hash_algo="blake3-128",
the next coverage call must categorize files normally.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.trace.coverage import compute_trace_coverage


@pytest.fixture
def repo_with_pre_cutover_manifest(tmp_path: Path):
    """A repo with one .py file and a manifest carrying SHA-256 hashes
    and explicitly hash_algo='sha256-64'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    # Compute the SHA-256-64 hash the pre-cutover code would have written.
    import hashlib
    sha = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "hash_algo": "sha256-64",
        "file_hashes": {"main.py": sha},
        "built_at": "2026-05-01T00:00:00Z",
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )
    return repo, idx


def test_pre_cutover_manifest_marks_all_files_stale(repo_with_pre_cutover_manifest):
    repo, idx = repo_with_pre_cutover_manifest

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    stale = {f["path"] for f in result.get("stale", [])}
    traced = {f["path"] for f in result.get("traced", [])}
    untraced = {f["path"] for f in result.get("untraced", [])}

    # The single file must be stale (algo mismatch, no hash computed,
    # marked stale to trigger rebuild).
    assert stale == {"main.py"}, f"expected main.py stale; got stale={stale} traced={traced} untraced={untraced}"


def test_post_cutover_manifest_categorizes_normally(tmp_path):
    """After a hypothetical rebuild has written hash_algo='blake3-128',
    coverage must categorize files via the normal hash-compare path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()

    # Compute the BLAKE3-128 hash that prep_engine.hash_content would write.
    import prep_engine
    blake = prep_engine.hash_content("def main(): pass\n")

    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "hash_algo": "blake3-128",
        "file_hashes": {"main.py": blake},
        "built_at": "2030-01-01T00:00:00Z",  # future to defeat mtime fast-path
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    traced_or_pending = (
        {f["path"] for f in result.get("traced", [])}
        | {f["path"] for f in result.get("pending_embedding", [])}
    )
    stale = {f["path"] for f in result.get("stale", [])}

    assert "main.py" in traced_or_pending, f"expected main.py traced; got traced/pending={traced_or_pending} stale={stale}"


def test_absent_hash_algo_defaults_to_sha256_64(tmp_path):
    """A manifest from before this phase had no hash_algo field. It
    must be treated as sha256-64 → mismatch with current → self-heal."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    import hashlib
    sha = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        # no hash_algo field — defaults to sha256-64
        "file_hashes": {"main.py": sha},
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    stale = {f["path"] for f in result.get("stale", [])}
    assert stale == {"main.py"}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase133_hash_migration.py -v`
Expected: at least the second test (`test_post_cutover_manifest_categorizes_normally`) FAILS because Python `stable_file_hash` produces a SHA-256 prefix that doesn't match the BLAKE3 prefix in the manifest. The first test may pass accidentally (hash mismatch → stale) but is still load-bearing.

- [ ] **Step 4: Implement the hash swap and self-heal branch**

Edit `src/prep/core/trace/coverage.py`. Three changes:

(a) Near the top of `compute_trace_coverage`, after the manifest load (around where `manifest_built_at_ts` is set), add:

```python
from prep.core.manifest import CURRENT_HASH_ALGO

manifest_hash_algo = (
    manifest.get("hash_algo") or "sha256-64"  # back-compat: pre-cutover manifests
) if manifest_path.exists() else CURRENT_HASH_ALGO
hash_algo_mismatch = manifest_hash_algo != CURRENT_HASH_ALGO
```

(b) Replace the backfill `stable_file_hash(source)` call (around line 163):

```python
# Was: new_hashes[rel_path] = stable_file_hash(source)
import prep_engine
new_hashes[rel_path] = prep_engine.hash_content(source)
```

(c) Replace the per-file hash-compare `stable_file_hash(source)` call and add the self-heal branch (around line 354):

```python
# In the per-file categorization loop, where prev_hash is non-None:
if prev_hash is not None:
    if hash_algo_mismatch:
        # Self-heal: don't compute current hash; mark stale unconditionally.
        # Next structural rebuild will rewrite the manifest with the
        # current algo, after which subsequent coverage calls compare
        # normally.
        stale_files.append(file_info)
        continue

    # Existing mtime fast-path...
    needs_hash = True
    if manifest_built_at_ts is not None:
        try:
            file_mtime = stat.st_mtime
            if file_mtime < manifest_built_at_ts:
                needs_hash = False
        except Exception:
            pass

    if needs_hash:
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            current_hash = prep_engine.hash_content(source)  # was: stable_file_hash(source)
        except Exception:
            current_hash = ""

        if current_hash != prev_hash:
            stale_files.append(file_info)
        else:
            traced_files.append(file_info)
    else:
        traced_files.append(file_info)
```

(d) Remove the now-unused `from prep.core.ids import stable_file_hash` import at the top of `coverage.py` (line ~20). The categorization layer no longer hashes via Python.

- [ ] **Step 5: Run the migration test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_hash_migration.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Run the broader coverage suite**

Run: `.venv/bin/pytest tests/test_walker_parity.py tests/test_phase133_*.py tests/ -k "coverage or trace_coverage" -v 2>&1 | tail -25`
Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/prep/core/trace/coverage.py tests/test_phase133_hash_migration.py
git commit -m "feat(phase133): cutover compute_trace_coverage hashing to prep_engine.hash_content + Path A self-heal

Two stable_file_hash sites in coverage.py now call prep_engine.hash_content
(BLAKE3-128). Manifest's hash_algo field is consulted on load; mismatch
with CURRENT_HASH_ALGO marks all hashed files stale without computing
new hashes — the next structural rebuild rewrites the manifest with
the current algo, self-healing the migration.

Tests: test_phase133_hash_migration covers pre-cutover, post-cutover,
and absent-hash_algo (defaults to sha256-64) cases."
```

---

### Task 5: Switch `TraceBuilder` hash callers to `prep_engine.hash_content` and write `hash_algo` into the trace manifest

**Files:**
- Modify: `src/prep/core/trace/builder.py` — two `stable_file_hash` call sites (lines 218 and 481), the `_build_manifest` instance method (line 593), and the `_build_rust` post-merge step.
- Test: `tests/test_phase133_builder_writes_hash_algo.py` (new)

**Important — about `_build_manifest`:**
This task modifies `TraceBuilder._build_manifest` (instance method at line 593), NOT the imported `build_manifest` from `manifest.py` (a different function for the embedding manifest, modified in Task 1). The trace manifest — which is what `compute_trace_coverage` reads and what Phase 133's self-heal depends on — is built by `_build_manifest`.

The cleanest fix is to make `_build_manifest` always tag the manifest it writes with `CURRENT_HASH_ALGO` (default-valued kwarg). All three existing callers (lines 305, 349, 407) inherit the new field automatically — no caller-site changes needed.

The "preserve + merge" defensive logic at lines 379-388 and 451-457 stays put; Task 7 adds the assertion that proves it's dead, deletion deferred.

- [ ] **Step 1: Locate the call sites**

Run: `grep -n "stable_file_hash\|self\._build_manifest\|def _build_manifest\|self._write_manifest" src/prep/core/trace/builder.py`
Expected hits:
- `stable_file_hash` at lines 21 (import), 218 (in `_build_python`), 481 (in `_compute_file_hashes`)
- `self._build_manifest(` at lines 305, 349, 407 (three callers; line 305 is the post-validation-error fallback in `_build_python`, line 349 is the normal `_build_python` finalization, line 407 is the `_build_rust` error fallback)
- `def _build_manifest(` at line 593 (the instance method itself)
- `self._write_manifest(` at lines 314, 358, 415, 460 (four call sites — the last one is in `_build_rust` after the merge)

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase133_builder_writes_hash_algo.py`:

```python
"""Phase 133 — TraceBuilder writes hash_algo + BLAKE3 hashes into the
trace manifest. Targets the *trace* manifest specifically (the one
compute_trace_coverage reads) — the embedding manifest is covered by
test_phase133_manifest_hash_algo.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.manifest import CURRENT_HASH_ALGO
from prep.core.trace.builder import TraceBuilder


@pytest.fixture
def small_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()
    return repo, idx


def test_python_builder_emits_hash_algo_blake3_128(small_repo, monkeypatch):
    """Force the Python build path via the _ENGINE module global so we
    test the Python hashing site directly (not the Rust path's
    post-build re-hash). Engine selection in this codebase is via
    PREP_ENGINE env var → prep.core._ENGINE global; we monkeypatch
    the in-builder copy so the test doesn't depend on env var ordering."""
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")

    repo, idx = small_repo
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()

    manifest = json.loads((idx / "trace_manifest.json").read_text())
    assert manifest.get("hash_algo") == CURRENT_HASH_ALGO
    # Hashes are 32-hex-char BLAKE3, not 16-hex-char SHA-256.
    for rel_path, h in (manifest.get("file_hashes") or {}).items():
        assert len(h) == 32, f"{rel_path}: expected 32-char BLAKE3, got {len(h)}-char {h!r}"


def test_build_manifest_method_emits_hash_algo_unconditionally():
    """`_build_manifest` is the trace manifest factory. After Phase 133
    it always tags the manifest with CURRENT_HASH_ALGO, regardless of
    whether file_hashes is supplied — so even error-fallback manifests
    carry the algo tag."""
    import tempfile
    repo = Path(tempfile.mkdtemp())
    idx = Path(tempfile.mkdtemp())
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    # Direct invocation of the instance method — minimal args.
    m = builder._build_manifest(
        nodes_count=0,
        edges_count=0,
        files_parsed=0,
        files_failed=0,
        file_errors=[],
        last_error=None,
    )
    assert m.get("hash_algo") == CURRENT_HASH_ALGO
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase133_builder_writes_hash_algo.py -v`
Expected: both FAIL — manifest doesn't carry `hash_algo` yet, and hashes are 16-char SHA-256.

- [ ] **Step 4: Implement — part (a) imports**

Edit `src/prep/core/trace/builder.py`. Near the top of the file, add the imports:

```python
# Existing import at line 21 (keep — stable_file_hash may still be
# used by other code paths in this module that aren't in scope for
# Phase 133):
from prep.core.ids import (
    stable_file_hash,  # ← stays
    ...
)

# NEW imports for Phase 133:
import prep_engine
from prep.core.manifest import CURRENT_HASH_ALGO
```

- [ ] **Step 5: Implement — part (b) swap the `_build_python` per-file hash (line 218)**

Find the `_build_python` per-file hashing block:

```python
# Was: file_hashes[rel_path] = stable_file_hash(source)
file_hashes[rel_path] = prep_engine.hash_content(source)
```

- [ ] **Step 6: Implement — part (c) swap the `_compute_file_hashes` hash (line 481)**

Find the `_compute_file_hashes` per-file hashing block:

```python
# Was: file_hashes[rel_path] = stable_file_hash(source)
file_hashes[rel_path] = prep_engine.hash_content(source)
```

- [ ] **Step 7: Implement — part (d) extend `_build_manifest` instance method to always emit `hash_algo`**

Find `def _build_manifest(...)` at line 593. Modify the signature and the manifest dict:

```python
def _build_manifest(
    self,
    nodes_count: int,
    edges_count: int,
    files_parsed: int,
    files_failed: int,
    file_errors: List[FileError],
    last_error: Optional[str],
    file_hashes: Optional[Dict[str, str]] = None,
    hash_algo: str = CURRENT_HASH_ALGO,   # ← NEW: defaults so all callers inherit
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "version": TRACE_MANIFEST_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "repo_root": str(self.repo_root),
        },
        "config": {
            "include_globs": self.include_globs,
            "exclude_globs": self.exclude_globs,
            "max_file_bytes": self.max_file_bytes,
        },
        "counts": {
            "nodes": nodes_count,
            "edges": edges_count,
            "files_parsed": files_parsed,
            "files_failed": files_failed,
        },
        "file_errors": [
            {"file_path": e.file_path, "error_type": e.error_type, "message": e.message}
            for e in file_errors
        ],
        "last_error": last_error,
        "hash_algo": hash_algo,                # ← NEW: always emit
    }
    if file_hashes is not None:
        manifest["file_hashes"] = file_hashes
    return manifest
```

The three existing callers at lines 305, 349, 407 don't need changes — they get `hash_algo=CURRENT_HASH_ALGO` from the default.

- [ ] **Step 8: Implement — part (e) `_build_rust` post-merge step also tags `hash_algo`**

The `_build_rust` path doesn't always go through `_build_manifest` — when the Rust build succeeds, it reads the manifest the Rust engine wrote, then attaches `file_hashes`. Find the post-merge block (around lines 451-460) and add the algo tag:

```python
# Around line 451:
if "file_hashes" not in manifest:
    logger.info("Computing file_hashes for Rust-built trace manifest")
    new_hashes = self._compute_file_hashes()
    if saved_file_hashes:
        # ... existing merge logic ...
        merged = dict(saved_file_hashes)
        merged.update(new_hashes)
        manifest["file_hashes"] = merged
        logger.info(...)
    else:
        manifest["file_hashes"] = new_hashes
    manifest["hash_algo"] = CURRENT_HASH_ALGO   # ← NEW: tag post-Rust-build manifest
    self._write_manifest(manifest)
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_builder_writes_hash_algo.py -v`
Expected: 2 PASSED.

- [ ] **Step 10: Run the broader builder suite to catch regressions**

Run: `.venv/bin/pytest tests/ -k "trace_builder or trace.build or builder" -v 2>&1 | tail -25`
Expected: all PASSED.

- [ ] **Step 11: Lint check**

Run: `.venv/bin/ruff check src/prep/core/trace/builder.py tests/test_phase133_builder_writes_hash_algo.py`
Expected: no new errors.

- [ ] **Step 12: Commit**

```bash
git add src/prep/core/trace/builder.py tests/test_phase133_builder_writes_hash_algo.py
git commit -m "feat(phase133): TraceBuilder writes BLAKE3 hashes + hash_algo to trace manifest

Two stable_file_hash call sites (builder.py:218, :481) now call
prep_engine.hash_content. _build_manifest instance method (line 593)
gains hash_algo: str = CURRENT_HASH_ALGO default kwarg, always emits
the field in the manifest dict — three existing callers inherit it
automatically. _build_rust post-merge step (line ~458) also tags
manifest['hash_algo'] = CURRENT_HASH_ALGO before the final write so
the Rust path's manifest carries the algo too.

Preserve+merge defensive logic at lines 379-388, 451-457 stays put —
Task 7 adds the runtime assertion proving it's dead code; deletion
is deferred one release cycle per the spec."
```

---

### Task 6: Migrate `_compute_file_hashes` to `prep_engine.walk_repo`

**Files:**
- Modify: `src/prep/core/trace/builder.py:466-489` (the `_compute_file_hashes` method).
- Test: `tests/test_phase133_compute_file_hashes_uses_walker.py` (new)

After this task, both `_compute_file_hashes` and `compute_trace_coverage` walk via the same Rust primitive — by construction, they emit identical file sets, and the "preserve + merge" defensive logic in `_build_rust` no longer has any merging to do.

- [ ] **Step 1: Read the current `_compute_file_hashes`**

Run: `sed -n '466,489p' src/prep/core/trace/builder.py`
Expected: shows the method that calls `self._enumerate_files()` and loops through them, computing hashes.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase133_compute_file_hashes_uses_walker.py`:

```python
"""Phase 133 — _compute_file_hashes walks via prep_engine.walk_repo.

Locks the cutover at the seam: this method previously walked via
self._enumerate_files() (Python os.walk), which could disagree with
the Rust walker that build_trace already uses. After Phase 133 both
walks share a primitive."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.trace.builder import TraceBuilder


def test_compute_file_hashes_calls_prep_engine_walk_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()

    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )

    with patch("prep_engine.walk_repo") as mock_walk:
        class _StubEntry:
            def __init__(self, path, abs_path, size, modified_secs):
                self.path = path
                self.abs_path = abs_path
                self.size = size
                self.modified_secs = modified_secs

        mock_walk.return_value = [
            _StubEntry("main.py", str(repo / "main.py"), 18, 0.0),
        ]

        builder._compute_file_hashes()

    assert mock_walk.called, "_compute_file_hashes must walk via prep_engine.walk_repo"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase133_compute_file_hashes_uses_walker.py -v`
Expected: FAIL — `_compute_file_hashes` walks via `self._enumerate_files()` today.

- [ ] **Step 4: Implement the migration**

Edit `src/prep/core/trace/builder.py`. Replace the body of `_compute_file_hashes` (around line 466):

```python
def _compute_file_hashes(self) -> Dict[str, str]:
    """Compute content hashes for all eligible files.

    Phase 133: walks via prep_engine.walk_repo for parity with
    compute_trace_coverage and the Rust trace builder. Both sides
    now share one walker primitive.
    """
    import prep_engine

    file_hashes: Dict[str, str] = {}
    entries = prep_engine.walk_repo(
        str(self.repo_root),
        include_globs=list(self.include_globs) if self.include_globs else None,
        exclude_globs=list(self.exclude_globs) if self.exclude_globs else None,
        max_file_bytes=int(self.max_file_bytes),
    )

    for entry in entries:
        rel_path = entry.path  # already POSIX, repo-relative
        abs_path = Path(entry.abs_path)
        try:
            file_size = int(entry.size)
            if file_size > self.max_file_bytes:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read(50_000)
            else:
                source = abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            source = ""
        file_hashes[rel_path] = prep_engine.hash_content(source)

    return file_hashes
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_compute_file_hashes_uses_walker.py -v`
Expected: 1 PASSED.

- [ ] **Step 6: Run the full builder suite**

Run: `.venv/bin/pytest tests/ -k "trace_builder or trace.build or phase133" -v 2>&1 | tail -25`
Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/prep/core/trace/builder.py tests/test_phase133_compute_file_hashes_uses_walker.py
git commit -m "feat(phase133): migrate _compute_file_hashes to prep_engine.walk_repo

Both _compute_file_hashes and compute_trace_coverage now walk via the
same Rust primitive. By construction they emit identical file sets;
the preserve+merge defensive logic in _build_rust has no merging to
do. Task 7 adds the runtime assertion proving this."
```

---

### Task 7: Add temporary assertion at the merge site

**Files:**
- Modify: `src/prep/core/trace/builder.py:451-457` (the merge block in `_build_rust`).
- Test: `tests/test_phase133_merge_is_dead_code.py` (new)

This task installs a runtime assertion that the merge produces zero additions. If divergence resurfaces (regression in the walker, new caller bypasses the primitive, etc.), the assertion fires loudly. After one full release cycle in production with the assertion green, a follow-up patch deletes the entire preserve+merge block.

- [ ] **Step 1: Locate the merge site**

Run: `sed -n '440,465p' src/prep/core/trace/builder.py`
Expected: shows the `if "file_hashes" not in manifest:` block where `merged = dict(saved_file_hashes); merged.update(new_hashes)`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase133_merge_is_dead_code.py`:

```python
"""Phase 133 — assert the preserve+merge defensive logic produces
zero additions on a real fixture. If this test fires, the Rust walker
and Python side disagree on a file (which Phase 133 was supposed to
make impossible)."""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.core.trace.builder import TraceBuilder


def test_rust_path_merge_has_zero_additions_on_fixture(tmp_path: Path, monkeypatch):
    """Build via the Rust path twice. The second build's saved_file_hashes
    must equal new_hashes — the merge adds nothing. Skip if Rust engine
    isn't available in the test environment (PyO3 wheel not built)."""
    pytest.importorskip("prep_engine")
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "rust")

    fixture = Path(__file__).parent / "fixtures" / "walker_parity_repo"
    idx = tmp_path / "index"
    idx.mkdir()

    builder = TraceBuilder(
        repo_root=fixture,
        index_dir=idx,
        include_globs=["**/*.py", "**/*.md", "**/*.yml"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )

    # First build populates the manifest.
    builder.build()

    # Second build: the assertion installed in builder.py fires under
    # PYTEST_CURRENT_TEST if saved - new is non-empty. Reaching this
    # line without AssertionError is the contract.
    builder.build()
```

- [ ] **Step 3: Run the test to verify it passes (no assertion installed yet, but the build path runs)**

Run: `.venv/bin/pytest tests/test_phase133_merge_is_dead_code.py -v`
Expected: PASS (the test only asserts no AssertionError; we haven't added the assertion yet, so any path passes).

- [ ] **Step 4: Install the assertion in `_build_rust`**

Edit `src/prep/core/trace/builder.py` around line 451-457. Find the merge block:

```python
if saved_file_hashes:
    # Merge: start with preserved hashes, overlay with freshly computed
    merged = dict(saved_file_hashes)
    merged.update(new_hashes)
    manifest["file_hashes"] = merged
    logger.info("Merged %d preserved + %d new = %d file_hashes",
                len(saved_file_hashes), len(new_hashes), len(merged))
```

Add the assertion + warning right before the merge:

```python
if saved_file_hashes:
    # Phase 133 Task 7: temporary assertion. After both _compute_file_hashes
    # and compute_trace_coverage walk via prep_engine.walk_repo (same as
    # the Rust trace builder), the two file sets MUST agree by
    # construction. If they don't, divergence has resurfaced and we want
    # to know loudly. Deletion of the preserve+merge logic is deferred
    # one release cycle to confirm this assertion stays green in
    # production. After that, the entire `if saved_file_hashes:` block
    # below can be removed.
    additions = set(saved_file_hashes) - set(new_hashes)
    if additions:
        # Log a WARNING (don't crash — this is observability) but assert
        # in tests so any regression is loud.
        sample = sorted(additions)[:10]
        logger.warning(
            "Phase 133 Task 7 invariant violation: preserve+merge added "
            "%d files not in walker output (sample: %s). Walker/coverage "
            "divergence has resurfaced. See docs/Phase133_RustWalkerHasherCutover/README.md",
            len(additions), sample,
        )
        # Test-mode hard fail (production keeps the merge as defense-in-depth):
        if __debug__:
            import os
            if os.environ.get("PYTEST_CURRENT_TEST"):
                raise AssertionError(
                    f"Phase 133: preserve+merge produced {len(additions)} "
                    f"additions; walker divergence has returned. "
                    f"Sample: {sample}"
                )

    # Existing merge logic (unchanged):
    merged = dict(saved_file_hashes)
    merged.update(new_hashes)
    manifest["file_hashes"] = merged
    logger.info("Merged %d preserved + %d new = %d file_hashes",
                len(saved_file_hashes), len(new_hashes), len(merged))
```

- [ ] **Step 5: Run the test to verify it still passes (zero additions on real fixture)**

Run: `.venv/bin/pytest tests/test_phase133_merge_is_dead_code.py -v`
Expected: PASS — the assertion holds because both walkers now use the same primitive.

- [ ] **Step 6: Run the full pipeline + builder suite**

Run: `.venv/bin/pytest tests/ -k "trace_builder or builder or phase133" -v 2>&1 | tail -30`
Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/prep/core/trace/builder.py tests/test_phase133_merge_is_dead_code.py
git commit -m "feat(phase133): add temporary assertion that preserve+merge is dead code

After Tasks 3 and 6, both _compute_file_hashes and compute_trace_coverage
walk via prep_engine.walk_repo. The preserve+merge defensive logic in
_build_rust should never produce additions. The assertion fires loudly
under pytest if divergence regresses; production logs a WARNING but
keeps the merge as defense-in-depth. Deletion of the preserve+merge
block is deferred one release cycle."
```

---

### Task 8: Hidden-dirs explicit regression test

**Files:**
- Create: `tests/test_phase133_hidden_dirs.py`

This task is small and may already pass (Task 3's behavior-parity tests already cover divergence #2). It exists as an explicit, narrowly-named regression guard so future engineers can search "hidden dir" in the test suite and find the contract.

- [ ] **Step 1: Write the test**

Create `tests/test_phase133_hidden_dirs.py`:

```python
"""Phase 133 divergence #2 — hidden directories not in default
exclude_globs must appear in coverage output. Pre-cutover Python
coverage silently pruned all `.foo` directories via the
`not d.startswith('.')` filter; the Rust walker doesn't, and after
the cutover Python doesn't either."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.trace.coverage import compute_trace_coverage


def test_github_workflows_directory_visible_in_coverage(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py", "**/*.yml"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    paths = set()
    for key in ("traced", "untraced", "stale", "excluded", "pending_embedding"):
        for entry in result.get(key, []):
            paths.add(entry["path"])

    assert ".github/workflows/ci.yml" in paths, (
        "Phase 133 divergence #2 regression: hidden-dir contents must "
        "appear in coverage. The previous `not d.startswith('.')` prune "
        "is gone; only the exclude_globs determine inclusion."
    )
    assert "src/main.py" in paths, "control file should also appear"
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_hidden_dirs.py -v`
Expected: 1 PASSED (already passes due to Task 3).

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase133_hidden_dirs.py
git commit -m "test(phase133): explicit regression guard for hidden-dir divergence

Narrowly-named test asserting .github/workflows/ci.yml appears in
coverage output. Already passes after Task 3 (the cutover removed
Python's hidden-dir prune); this test exists so future engineers
searching 'hidden dir' find the contract."
```

---

### Task 9: Phase 125c bimodal walker test

**Files:**
- Create: `tests/test_phase133_bimodal_walker.py`

Locks the spec's success-criteria #9: the walker primitive must support both source-indexing-mode (CLAUDE.md, `.cursor/rules/*.mdc` excluded) and doc-discovery-mode (those files included) without code changes to the primitive itself.

- [ ] **Step 1: Identify the source-indexing default exclude set**

Run: `grep -n "DEFAULT_EXCLUDE_FILE_GLOBS" src/prep/core/repo_profile.py`
Expected: a list including `**/AGENTS.md`, `**/CLAUDE.md`, `**/.cursor/rules/*.mdc` and similar AI-rule patterns.

- [ ] **Step 2: Write the test**

Create `tests/test_phase133_bimodal_walker.py`:

```python
"""Phase 133 — Phase 125c forward-look: walker primitive bimodal use.

The Rust walker accepts include_globs and exclude_globs from the caller.
For source indexing (today's coverage path), CLAUDE.md and
.cursor/rules/*.mdc are in DEFAULT_EXCLUDE_FILE_GLOBS — they must
NOT appear. For a hypothetical doc-discovery caller (Phase 125c), the
caller passes a different exclude set without those globs — those
files MUST appear.

Phase 133's contract: the walker primitive supports both modes.
Phase 125c (separate phase) builds the doc-discovery caller."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep_engine

FIXTURE = Path(__file__).parent / "fixtures" / "walker_parity_repo"


def test_source_indexing_mode_excludes_ai_rule_files():
    """Caller passes the source-indexing exclude set → CLAUDE.md and
    .cursor/rules/*.mdc are NOT in the walker output."""
    from prep.core.repo_profile import DEFAULT_EXCLUDE_FILE_GLOBS, DEFAULT_EXCLUDE_DIR_NAMES

    excludes = list(DEFAULT_EXCLUDE_FILE_GLOBS) + [f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES]

    entries = prep_engine.walk_repo(
        str(FIXTURE),
        include_globs=["**/*.md", "**/*.mdc", "**/*.py", "**/*.yml"],
        exclude_globs=excludes,
        max_file_bytes=500_000,
    )
    paths = {e.path for e in entries}

    assert "CLAUDE.md" not in paths, (
        "source-indexing mode must exclude CLAUDE.md — it's in DEFAULT_EXCLUDE_FILE_GLOBS"
    )
    assert ".cursor/rules/sample.mdc" not in paths, (
        "source-indexing mode must exclude .cursor/rules/*.mdc"
    )


def test_doc_discovery_mode_includes_ai_rule_files():
    """Caller passes a curated exclude set without the AI-rule globs →
    CLAUDE.md and .cursor/rules/*.mdc DO appear. This is the Phase 125c
    forward-look surface; Phase 133 just proves the walker supports it."""
    # Doc-discovery exclude set: still cull build artifacts and VCS,
    # but NOT the AI-rule files.
    excludes = [
        "**/.git/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
    ]

    entries = prep_engine.walk_repo(
        str(FIXTURE),
        include_globs=["**/*.md", "**/*.mdc", "**/*.py", "**/*.yml"],
        exclude_globs=excludes,
        max_file_bytes=500_000,
    )
    paths = {e.path for e in entries}

    assert "CLAUDE.md" in paths, (
        "doc-discovery mode must include CLAUDE.md when caller drops the AI-rule excludes"
    )
    assert ".cursor/rules/sample.mdc" in paths, (
        "doc-discovery mode must include .cursor/rules/*.mdc when caller drops them"
    )
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_bimodal_walker.py -v`
Expected: 2 PASSED (the walker primitive already supports both modes — the test just locks it in).

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase133_bimodal_walker.py
git commit -m "test(phase133): bimodal walker contract for Phase 125c forward-look

Two tests asserting the walker primitive supports both source-indexing
mode (CLAUDE.md / .cursor/rules/*.mdc excluded by default) and
doc-discovery mode (caller drops those globs to find the same files).
Phase 125c builds the doc-discovery caller; Phase 133 proves the
primitive doesn't need changes for it."
```

---

### Task 10: max_files cap WARNING surface in coverage response

**Files:**
- Modify: `src/prep/core/trace/coverage.py` — detect when the walker hit its `max_files` cap and surface a WARNING in the response envelope.
- Modify: `src/prep/api/routers/trace_routes/query.py` — pass the warning through to the HTTP response.
- Test: `tests/test_phase133_max_files_warning.py` (new)

When the Rust walker truncates at 100k files, today the user sees no signal. This task adds an explicit WARNING field to the coverage response so operators can see when truncation is biting.

- [ ] **Step 1: Read the walker's cap behavior**

Run: `sed -n '270,285p' engine/crates/prep-walker/src/lib.rs`
Expected: shows the `if entries.len() >= config.max_files` block that breaks the walk and logs a `log::warn!`. The Python binding doesn't surface this cap-hit signal directly today.

- [ ] **Step 2: Write the failing test**

Create `tests/test_phase133_max_files_warning.py`:

```python
"""Phase 133 divergence #5 surface — coverage response carries a
warning when the walker hits its max_files cap, so operators see
truncation instead of silently losing files."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.trace.coverage import compute_trace_coverage


def test_coverage_emits_max_files_warning_when_cap_hit(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    # Stub walk_repo to return exactly 100_000 entries (Rust default cap).
    class _StubEntry:
        def __init__(self, i):
            self.path = f"f{i}.py"
            self.abs_path = str(repo / f"f{i}.py")
            self.size = 1
            self.modified_secs = 0.0

    with patch("prep_engine.walk_repo") as mock_walk:
        mock_walk.return_value = [_StubEntry(i) for i in range(100_000)]
        result = compute_trace_coverage(
            repo_root=repo,
            index_dir=idx,
            include_globs=["**/*.py"],
            exclude_globs=[],
            user_exclude_globs=[],
            max_file_bytes=500_000,
        )

    warnings = result.get("warnings") or []
    cap_warnings = [w for w in warnings if "max_files" in str(w).lower() or "cap" in str(w).lower()]
    assert cap_warnings, (
        f"expected a max_files cap warning when walker returned exactly 100k entries; "
        f"got warnings={warnings}"
    )


def test_coverage_no_warning_below_cap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    warnings = result.get("warnings") or []
    assert not warnings, f"expected no warnings on tiny repo; got {warnings}"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_phase133_max_files_warning.py -v`
Expected: FAIL — `compute_trace_coverage` doesn't emit warnings yet.

- [ ] **Step 4: Implement the warning surface**

Edit `src/prep/core/trace/coverage.py`. Right after the `entries = prep_engine.walk_repo(...)` call from Task 3, add:

```python
# Phase 133 divergence #5 surface: walker caps at max_files (100k by
# default in WalkConfig). When we hit that cap, files past it are
# silently dropped — surface a WARNING so operators know.
warnings: List[str] = []
WALKER_MAX_FILES = 100_000  # mirror engine/crates/prep-walker/src/lib.rs:168
if len(entries) >= WALKER_MAX_FILES:
    warnings.append(
        f"max_files cap hit: walker returned exactly {len(entries):,} files. "
        f"Files beyond the cap were silently dropped. If your repo legitimately "
        f"has more than {WALKER_MAX_FILES:,} eligible files, raise the cap in "
        f"prep-walker WalkConfig."
    )
```

At the end of `compute_trace_coverage`, where the result dict is assembled (around line 380-395), add `warnings` to the output:

```python
return {
    "summary": summary,
    "traced": final_traced,
    "pending_embedding": pending_embedding,
    "untraced": untraced_files,
    "stale": stale_files,
    "excluded": excluded_files,
    "warnings": warnings,  # ← new (always emitted, empty list when none)
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_phase133_max_files_warning.py -v`
Expected: 2 PASSED.

- [ ] **Step 6: Verify the HTTP response carries the warning**

The HTTP envelope in `src/prep/api/routers/trace_routes/query.py` returns the result dict via `ok(...)`. Since `warnings` is now a top-level key on the dict, it flows through automatically. Confirm:

Run: `grep -n "warnings\|return ok" src/prep/api/routers/trace_routes/query.py | head`
Expected: the existing `ok(...)` wraps the full coverage dict; no router change needed.

- [ ] **Step 7: Commit**

```bash
git add src/prep/core/trace/coverage.py tests/test_phase133_max_files_warning.py
git commit -m "feat(phase133): surface max_files cap warning in coverage response

When prep_engine.walk_repo returns exactly its max_files cap, coverage
emits a warning in the response envelope. Operators see truncation
explicitly instead of silently losing files past the cap. Closes
divergence #5 from the Phase 133 spec."
```

---

### Task 11: Doc closes — dogfooding follow-up + MASTER_TODO entry

**Files:**
- Modify: `docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md` — append a closing note.
- Modify: `docs/MASTER_TODO.md` — append Phase 133 entry to the recent-phases index.

- [ ] **Step 1: Append the dogfooding doc closing note**

Edit `docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md`. At the bottom of the file, add:

```markdown
---

## Closing note (Phase 133 follow-up)

The "filter divergence is real" finding documented under §3 above
(2026-05-09 dogfooding session) was the trigger for **Phase 133 —
Rust Walker/Hasher Cutover**. That phase removed the root cause:
`compute_trace_coverage` and `_compute_file_hashes` now walk via
`prep_engine.walk_repo` (the same primitive the structural rebuild
uses), and hashing moved to `prep_engine.hash_content` (BLAKE3-128)
with self-healing manifest migration via the new `hash_algo` field.

The 6-surface divergence map from this dogfooding doc is now
closed by construction. See
`docs/Phase133_RustWalkerHasherCutover/README.md` for the full
spec and `IMPLEMENTATION_PLAN.md` for the change manifest.

The U19 logging the spec calls out as a *symptom mitigation* can be
removed in a future phase (the divergence it logs no longer occurs);
left in place pending Phase 133 Task 7's assertion proving the
preserve+merge is truly dead.
```

- [ ] **Step 2: Append the MASTER_TODO entry**

Edit `docs/MASTER_TODO.md`. In the "Recent phases (100+) — quick index" section, append:

```markdown
- Phase 133 (Rust Walker/Hasher Cutover) — completes the half-shipped
  migration from Python `os.walk` + `fnmatch` + `hashlib.sha256` to
  `prep_engine.walk_repo` + BLAKE3-128 on the Graph Scope coverage
  path. Eliminates 6-surface filter divergence between coverage and
  the structural rebuild. Manifest gains `hash_algo` field for
  self-healing migration. See
  `docs/Phase133_RustWalkerHasherCutover/README.md` and
  `IMPLEMENTATION_PLAN.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md docs/MASTER_TODO.md
git commit -m "docs(phase133): close dogfooding follow-up + MASTER_TODO entry

Closing note on the 18_Followup dogfooding doc cross-links the
divergence finding to its Phase 133 resolution. MASTER_TODO recent-
phases index gains the Phase 133 entry."
```

---

## Final verification

After Task 11, run the full Phase 133 test suite + a broader sanity sweep:

- [ ] **Verify all Phase 133 tests pass together**

Run:

```bash
.venv/bin/pytest \
  tests/test_phase133_manifest_hash_algo.py \
  tests/test_phase133_coverage_uses_rust_walker.py \
  tests/test_phase133_hash_migration.py \
  tests/test_phase133_builder_writes_hash_algo.py \
  tests/test_phase133_compute_file_hashes_uses_walker.py \
  tests/test_phase133_merge_is_dead_code.py \
  tests/test_phase133_hidden_dirs.py \
  tests/test_phase133_bimodal_walker.py \
  tests/test_phase133_max_files_warning.py \
  tests/test_walker_parity.py \
  -v
```

Expected: all PASSED (count: ~30 tests).

- [ ] **Verify no broader regressions in adjacent suites**

Run:

```bash
.venv/bin/pytest \
  tests/ -k "trace or watcher or pipeline_orchestrator or coverage or builder or manifest" \
  --tb=no -q 2>&1 | tail -10
```

Expected: PASSED count rises by ~30; FAILED count unchanged from main (any failures should match pre-existing list documented in Phase 132 follow-up).

- [ ] **Lint sweep**

Run:

```bash
.venv/bin/ruff check src/prep/core/manifest.py src/prep/core/trace/coverage.py src/prep/core/trace/builder.py src/prep/api/routers/trace_routes/query.py tests/test_phase133_*.py tests/test_walker_parity.py
```

Expected: no NEW errors. Pre-existing line-length warnings in `coverage.py` / `builder.py` are acceptable.

- [ ] **Restart the daemon and run the migration validation probes from the spec**

Per `feedback_restart_daemon_before_live_validation.md`, the daemon has no hot-reload. Restart, then:

```bash
# Restart daemon
pkill -f "prep.*serve"  # or however you stop it
.venv/bin/prep serve &

# Sleep until daemon is ready (use the Monitor tool's polling or the dev script's wait helper).
# Then probe one project's manifest:
PID="<your project_id>"
curl -s "http://localhost:8400/projects/$PID/trace/coverage" | jq '.data | {summary: .summary, warnings: .warnings, hash_algo: (.summary.hash_algo // "absent"), stale: (.stale | length), traced: (.traced | length)}'
```

Expected: `stale` is non-zero on the first call (self-heal triggers); after a structural rebuild, second call returns `stale=0`.

- [ ] **Verify the manifest hash_algo migrated**

```bash
for dir in ~/.local/share/sourceprep/projects/*/; do
  echo "$dir: $(jq -r '.hash_algo // "absent"' "$dir/trace_manifest.json")"
done
```

Expected: every project's manifest reads `blake3-128` after at least one rebuild has run post-Phase-133.

---

## Notes for the executing engineer

- **No `Co-Authored-By` trailer** in any commit (per repo convention `feedback_no_coauthored_by.md`).
- **Don't push without explicit instruction** (per `feedback_explicit_push_only.md`). Commits stay local until the user says "push" / "ship" / "deploy."
- **Use `.venv/bin/pytest` and `.venv/bin/ruff`**, not the system `pytest` / `ruff` (per `feedback_use_venv.md`).
- **Daemon restart is required after each backend change you want to live-test** (per `feedback_restart_daemon_before_live_validation.md`). Pure unit tests don't need it.
- **Line numbers in the spec and this plan are based on `HEAD` at spec-write time.** If they've drifted, use `grep`/`sed` to relocate the symbol; the symbol names (`stable_file_hash`, `_build_rust`, `_compute_file_hashes`, etc.) are stable.
- **If `prep_engine` import fails** in a test environment (no Rust toolchain / wheel not built), the test should `pytest.skip` with a clear message. Production code keeps the existing fallback in `src/prep/core/__init__.py`.
- **The "preserve + merge" defensive logic is NOT deleted in this phase.** Task 7 adds an assertion proving it's dead code; deletion is a follow-up patch one release cycle later.
