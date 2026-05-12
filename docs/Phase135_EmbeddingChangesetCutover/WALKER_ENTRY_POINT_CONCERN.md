# Concern — `prep_engine.walk_repo` entry-point sprawl

> **Status:** Not blocking Phase 135. Captured here so the next walker
> consolidation has the context.
> **Date raised:** 2026-05-12 (during Phase 133b scrutiny pass)
> **Related commits:** `34cb9ad2`, `91fb2614`, `5ed14dfe`
> **Related phases:** Phase 133 (Rust walker cutover), Phase 133b (dot-dir
> policy + catalog refinement)

## The shape

After Phase 133 cut the file walker over to `prep_engine.walk_repo`,
the Python side has **six independent callers** of that binding:

| # | Caller | Site |
|---|---|---|
| 1 | `compute_trace_coverage` | `src/prep/core/trace/coverage.py:163` |
| 2 | `TraceBuilder._compute_file_hashes` | `src/prep/core/trace/builder.py:543` |
| 3 | `TraceBuilder._enumerate_files` | `src/prep/core/trace/builder.py:570` |
| 4 | `_iter_repo_files` (profile repo scan) | `src/prep/core/repo_profile.py:381` |
| 5 | `scan_for_presets` (stack detection) | `src/prep/core/repo_profile.py:289` |
| 6 | `_walk_markdown` (atlas T2 link extractor) | `src/prep/core/atlas/markdown_links.py:158` |

Plus a seventh independent walker (own implementation, not
`prep_engine.walk_repo`) for concept synthesis grounding:

| 7 | `_walk_md_files` (concept synthesizer's docs walker) | `src/prep/core/docs_grounding.py:286` |

Each of these:

- Resolves include/exclude globs independently
- Must remember to merge `DEFAULT_EXCLUDE_DIR_NAMES` + `DEFAULT_EXCLUDE_FILE_GLOBS`
  as a system-level baseline when the caller passes its own globs
  (otherwise the catalog gets bypassed — the failure mode that Phase
  133b's hot-fix on coverage.py / TraceBuilder / markdown_links closed)
- Honors `max_file_bytes` consistently
- Picks up new entries when `DEFAULT_EXCLUDE_DIR_NAMES` grows

Today the consistency is held by:

- The catalog (`DEFAULT_EXCLUDE_DIR_NAMES`, `DEFAULT_EXCLUDE_FILE_GLOBS`)
  in `repo_profile.py`
- The merge pattern (`for d in sorted(...): if pattern not in eg: eg.append(pattern)`)
  copy-pasted into each caller
- `effective_excludes()` in `repo_policy.py`, which centralizes the
  three-layer L1/L2/L3 policy union — but only some callers use it

## Why it's not great

1. **N copies of the merge boilerplate.** Each caller re-implements the
   same "merge DEFAULT_EXCLUDE_DIR_NAMES into the caller-supplied list"
   pattern. Phase 133b had to patch this in three places (coverage.py,
   builder.py, markdown_links.py) once we found that the project's
   registry config can carry an exclude_globs list that doesn't include
   `.claude/**`, `.agents/**`, etc.
2. **New walker callers risk re-introducing the leak.** A future
   contributor adding a 7th walker caller (e.g., a new finalize stage,
   a new admin endpoint) has to know the merge dance. The compiler
   won't catch it; the failure mode is silent (files leak in, agent
   re-ingests its own instructions, recursive output).
3. **The docs_grounding walker has the OPPOSITE policy and its own
   implementation.** It's correct that concept synthesis includes
   `.claude/.cursor/.agents/`, but the fact that the implementation is
   a separate `pathlib.Path` walker (instead of `prep_engine.walk_repo`
   with a different exclude set) is another inconsistency. Phase 133's
   plan §"Deferred items" notes the docs_grounding walker swap as a
   follow-up.

## What "good" looks like (sketch — not a spec)

A single `prep.core.walker` module that:

1. Wraps `prep_engine.walk_repo` with default-baseline merge applied
   unconditionally (the L1 catalog always unions in, regardless of
   what the caller passes).
2. Exposes two purpose-driven APIs:
   - `walk_for_source(repo_root, *, user_exclude_globs=None) -> list[Entry]`
     — for trace pipeline / build / coverage. Applies L1 + L2 + L3.
   - `walk_for_planning_docs(repo_root, *, include_agent_dirs=True)`
     — for the concept synthesizer. Same L1 baseline MINUS the agent
     dirs (`.claude`, `.cursor`, etc.) when `include_agent_dirs=True`.
3. Owns the only call to `prep_engine.walk_repo` in the Python codebase.
4. Has a `tests/test_walker_entry_point.py` that grep-asserts no other
   file imports `prep_engine.walk_repo` directly (lockdown test).

This would let the catalog evolve without touching N callers, and
make policy mistakes impossible by construction (you can't bypass the
merge because there's no path that skips it).

## Why this is deferred (and what would unblock it)

- Phase 133b already closed the immediate leak surface. The system is
  consistent today; the concern is about **maintainability**, not
  current correctness.
- Phase 134 and 135 are mid-flight (changeset-driven pipeline /
  embedding cutover). Doing a walker consolidation now risks merge
  conflicts and slows those phases.
- The right time to consolidate is **after** Phase 135 lands, when
  `coverage.py`, `builder.py`, and the embedding worker have all
  stopped moving.
- Reasonable scope: a Phase 136 or Phase 137 with one task per caller
  (migrate to the wrapper) + one task for the lockdown test. ~150 LoC,
  high confidence (mechanical).

## What to do if you encounter another walker leak in the meantime

Apply the same pattern Phase 133b used:

```python
# Phase 133b: always merge DEFAULT_EXCLUDE_DIR_NAMES as a system-level
# baseline. User config extends; never overrides.
from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES, DEFAULT_EXCLUDE_FILE_GLOBS
merged = list(exclude_globs or [])
for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
    pattern = f"**/{d}/**"
    if pattern not in merged:
        merged.append(pattern)
for pattern in DEFAULT_EXCLUDE_FILE_GLOBS:
    if pattern not in merged:
        merged.append(pattern)
exclude_globs = merged
```

Then add the new caller to the table at the top of this doc.
