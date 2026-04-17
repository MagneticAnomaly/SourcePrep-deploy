# Implementation Plan

**Phase:** 115 — Filter Universality & Self-Ingestion Prevention
**Drafted:** 2026-04-17

Ordered steps. Each is an independent commit. Checkpoints marked `[gate]` are where a test or verification must pass before proceeding.

## Sequencing principle

**Data structures first, enforcement second, tests last.** Steps 0–2 add the registry + default sets. Steps 3–8 wire every consumer to read them. Steps 9–11 pin the behaviour with tests. Any order that ships tests before enforcement will have noisy red; any order that ships enforcement before the registry exists will churn.

## The 12 steps

### Step 0 — Add `CODRAG_OUTPUT_*` registry

**File:** `src/codrag/core/repo_profile.py`

Add at top of file:

```python
CODRAG_OUTPUT_DIRS: Set[str] = {".codrag", "codrag_data"}
CODRAG_OUTPUT_FILE_GLOBS: Sequence[str] = (... existing AI-tool globs ...)
```

Re-derive `DEFAULT_EXCLUDE_DIR_NAMES` to include `CODRAG_OUTPUT_DIRS` as a superset base. Leave `DEFAULT_EXCLUDE_FILE_GLOBS` including `*CODRAG_OUTPUT_FILE_GLOBS`. No behaviour change yet — the old set already included the AI-tool globs; this just renames the source.

**[gate]** `pytest tests/` must still be green. Unit test that `CODRAG_OUTPUT_DIRS <= DEFAULT_EXCLUDE_DIR_NAMES`.

---

### Step 1 — Add generated dirs to `DEFAULT_EXCLUDE_DIR_NAMES`

**File:** `src/codrag/core/repo_profile.py`

Add to the set:

```
storybook-static, coverage, out, .turbo, .vercel, .parcel-cache,
.svelte-kit, .astro, .nuxt
```

`.next` and `.cache` already present. Verified against `repo_policy.json` exclude list.

**[gate]** Manual diff check: `DEFAULT_EXCLUDE_DIR_NAMES` is now ≥44 entries.

---

### Step 2 — Add build-artifact file globs to `DEFAULT_EXCLUDE_FILE_GLOBS`

**File:** `src/codrag/core/repo_profile.py`

Add:

```python
"**/*.d.ts",      # TypeScript declaration files — generated
"**/*.min.js",
"**/*.min.css",
"**/*.map",       # source maps
```

Remove the narrow `**/codrag_data/ui_config.json` — `codrag_data` is now a dir-level exclude via step 0, so the specific file glob is redundant.

**[gate]** Unit test: `DEFAULT_EXCLUDE_FILE_GLOBS` contains all four new entries.

---

### Step 3 — Extend `ensure_repo_policy` auto-merge to file globs

**File:** `src/codrag/core/repo_policy.py`

At `repo_policy.py:151-163`, after the dir-glob union, also union `DEFAULT_EXCLUDE_FILE_GLOBS`:

```python
default_file_globs = set(DEFAULT_EXCLUDE_FILE_GLOBS)
if not default_file_globs.issubset(current_excludes):
    existing["exclude_globs"] = sorted(
        current_excludes | default_excludes | default_file_globs
    )
    write_repo_policy(path, existing)
```

**[gate]** Start the daemon against the dogfood repo. Observe that `.codrag/repo_policy.json` gets rewritten with the 10+ new entries. Diff the before/after file; entries should be added, not replaced. No entry already in the user's file should vanish.

---

### Step 4 — Sync Rust walker defaults

**File:** `engine/crates/codrag-walker/src/lib.rs`

Update `WalkConfig::default().exclude_globs` to mirror the Python `DEFAULT_EXCLUDE_DIR_NAMES`-derived list. Rust defaults are a safety net; the caller (Python daemon) passes the resolved filter. Selfheal (`codrag-selfheal`) reads its filter from `repo_policy.json` + `project.config.trace.ignore_patterns` separately (Step 7).

```rust
exclude_globs: vec![
    "**/.codrag/**".into(),
    "**/codrag_data/**".into(),
    "**/node_modules/**".into(),
    "**/.git/**".into(),
    "**/__pycache__/**".into(),
    "**/.venv/**".into(),
    "**/venv/**".into(),
    "**/env/**".into(),
    "**/.env/**".into(),
    "**/dist/**".into(),
    "**/build/**".into(),
    "**/target/**".into(),
    "**/storybook-static/**".into(),
    "**/coverage/**".into(),
    "**/out/**".into(),
    "**/.next/**".into(),
    "**/.turbo/**".into(),
    "**/.vercel/**".into(),
    "**/.parcel-cache/**".into(),
    "**/.svelte-kit/**".into(),
    "**/.astro/**".into(),
    "**/.nuxt/**".into(),
    "**/.cache/**".into(),
    "**/.pytest_cache/**".into(),
    "**/.mypy_cache/**".into(),
    "**/.ruff_cache/**".into(),
    "**/htmlcov/**".into(),
    "**/.coverage/**".into(),
    "**/.tox/**".into(),
    "**/.gradle/**".into(),
    "**/DerivedData/**".into(),
    "**/Pods/**".into(),
    "**/Carthage/**".into(),
    "**/vendor/**".into(),
    "**/bundle/**".into(),
    "**/.bundle/**".into(),
    "**/bower_components/**".into(),
    "**/.claude/**".into(),
    "**/.cursor/**".into(),
    "**/.windsurf/**".into(),
    "**/.continue/**".into(),
    "**/.cody/**".into(),
    "**/.aider/**".into(),
],
```

**[gate]** `cargo build --release` and `cargo test`. `maturin develop` (or rebuild bindings) to propagate to Python.

---

### Step 5 — Delete `TraceBuilder` hardcoded include/exclude

**File:** `src/codrag/core/trace/builder.py` (lines 66-100)

Remove the hardcoded `include_globs` and `exclude_globs` default branches. Replace with a call to a new helper that reads from `repo_policy.json`:

```python
from codrag.core.repo_policy import ensure_repo_policy

def __init__(self, ..., include_globs=None, exclude_globs=None, ...):
    ...
    if include_globs is None or exclude_globs is None:
        policy = ensure_repo_policy(self.index_dir, self.repo_root)
        if include_globs is None:
            include_globs = list(policy.get("include_globs") or [])
        if exclude_globs is None:
            exclude_globs = list(policy.get("exclude_globs") or [])
    self.include_globs = include_globs
    self.exclude_globs = exclude_globs
```

**[gate]** Rebuild dogfood index. Confirm no path starting with `packages/ui/storybook-static/`, `codrag_data/`, `coverage/`, `out/` appears in `trace_nodes.jsonl`. `.d.ts` files absent. This is the primary correctness gate for the phase.

---

### Step 6 — Fix `epistemic_enrichment.load_trace_nodes` filter

**File:** `src/codrag/core/epistemic_enrichment.py` (around line 290-300)

Apply the three-layer filter when reading `trace_nodes.jsonl`. Even if the file on disk has stale entries (pre-fix), enrichment should not process them.

```python
from codrag.core.repo_policy import effective_excludes  # new helper from 01_TARGET_DESIGN

def load_trace_nodes(index_dir, repo_root, trace_ignore_patterns=None):
    excludes = effective_excludes(
        index_dir=index_dir,
        repo_root=repo_root,
        trace_ignore_patterns=trace_ignore_patterns,
    )
    spec = pathspec.PathSpec.from_lines("gitwildmatch", excludes)
    with open(index_dir / "trace_nodes.jsonl") as f:
        for line in f:
            node = json.loads(line)
            if spec.match_file(node["path"]):
                continue  # excluded
            yield node
```

Callers already pass `index_dir`; `repo_root` and `trace_ignore_patterns` need to be threaded through. Audit upstream call sites.

**[gate]** Unit test that passes an `ignore_patterns=["**/*.d.ts"]` to `load_trace_nodes` and confirms `.d.ts` entries are filtered even when `trace_nodes.jsonl` contains them.

---

### Step 7 — Fix Rust selfheal L3 gap

**File:** `engine/crates/codrag-selfheal/src/main.rs` (around lines 93-103)

Selfheal currently reads `repo_policy.json.exclude_globs` and unions with walker defaults. Must also read `project.config.trace.ignore_patterns` (location: per-project config, typically `.codrag/project.config.json` or the project registry row).

Implementation note: if the config isn't easily reachable from Rust, expose a resolved `effective_exclude_globs` list via a JSON file that the Python daemon writes to `.codrag/` on any policy or ignore-pattern change. Selfheal reads the resolved list, not the raw sources.

**[gate]** Add an entry to `trace.ignore_patterns` via the Knowledge Scope endpoint, kill the Python daemon, run selfheal directly. Confirm the ignored path is not re-added to the graph by selfheal.

---

### Step 8 — Audit watcher filter merge

**File:** `src/codrag/services/watcher.py` (verify)

Confirm the watcher uses `effective_excludes()` when deciding whether a change event should trigger reindexing. If it doesn't read L3, fix it.

**[gate]** Touch a file under a path in `trace.ignore_patterns`. Watcher must not trigger a rebuild.

---

### Step 9 — Python/Rust parity test

**File:** `tests/test_walker_parity.py` (new)

Assert the Rust walker's `WalkConfig::default().exclude_globs` is a superset (or semantic equivalent) of the Python-derived default glob set.

Two ways to implement:

- (a) Serialize Rust defaults to JSON in a test helper, compare sets.
- (b) Walk a fixture tree with both walkers, assert identical output.

Prefer (b) — it tests behaviour, not set equality.

**[gate]** Test passes on CI. Fixture includes at least: `node_modules/`, `storybook-static/`, `codrag_data/`, `.next/`, `dist/`, `coverage/`, one `.d.ts` file, one `.min.js` file, and a valid `.py` + `.ts` pair that should be kept.

---

### Step 10 — Integration test: user exclude respected

**File:** `tests/test_user_exclude_respected.py` (new)

Given a fixture repo with a folder `foo/`, a user sets `trace.ignore_patterns = ["foo/**"]` via `/trace/ignore` POST, triggers a rebuild, and asserts no path starting with `foo/` appears in `trace_nodes.jsonl`.

Run twice: once with `foo/` in a directory covered by include globs (should still be excluded), once with user-toggling it on and off via `useDashboardPanels.handleToggleExclude` to catch any UI-path regressions.

**[gate]** Test passes.

---

### Step 11 — Self-ingestion regression test

**File:** `tests/test_no_self_ingestion.py` (new)

```python
def test_no_codrag_outputs_in_trace_nodes(dogfood_index):
    nodes = [json.loads(line) for line in open(index/"trace_nodes.jsonl")]
    offenders = [
        n["path"] for n in nodes
        if any(
            n["path"].startswith(d + "/") or f"/{d}/" in n["path"]
            for d in CODRAG_OUTPUT_DIRS
        )
    ]
    assert offenders == [], f"Self-ingestion leaked: {offenders}"
```

This is the load-bearing invariant. Every future writer must update `CODRAG_OUTPUT_DIRS` or `CODRAG_OUTPUT_FILE_GLOBS`; this test will catch any that doesn't.

**[gate]** Test passes. Add to CI.

---

## Rollback plan

Each step is one commit. Steps 0–3 and 5–8 are pure Python edits; revert by `git revert`. Step 4 is Rust — revert is the same but requires `cargo build` + `maturin develop` afterward. Steps 9–11 are tests; reverting a test doesn't affect prod behaviour.

If Step 5 (TraceBuilder uses policy) causes any regression, revert that single commit; the hardcoded-list behaviour returns while the registry and Rust work remain.

## Sequencing with in-flight pipeline run

`run-3639f940ba9f` is still executing Deep Reasoning. Two options:

- **Let it finish.** The current run costs money but finishes cleanly. Future runs benefit from the filter fix.
- **Pause and restart after Step 5.** Saves ~30 min of bad-file reasoning. Requires a daemon restart to pick up code changes anyway.

**Default:** let it finish. The fix requires a daemon restart regardless, and interrupting Deep Reasoning mid-swarm risks the pause-state bugs listed in the pipeline-testing runbook (P3, P5). After Step 5 lands + daemon restart, a fresh `/pipeline/rebuild` is the clean test of the fix.

## Verbose progress notes

A companion log lives at `docs/Phase115_filter-universality/PROGRESS.md`. Each step's commit hash, gate result, and any surprises get logged there as work proceeds.
