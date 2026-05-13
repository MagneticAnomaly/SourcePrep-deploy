# Phase 135.5 — Finish what 133/134/135 started

> The original task: two "single source of truth" cutovers. One for the
> file walker (Phase 133's promise). One for staleness via Changeset
> (Phase 134's promise). Both have been partially landed across three
> phases and never fully closed. This phase finishes them.

## What's still missing

### Staleness — 2 stages still have the Phase 134 anti-pattern

| Stage | File | What survives |
|---|---|---|
| 2 `inferred_edges` | `src/prep/core/inferred_edges.py` | `trace_inferred_hashes.json` manifest + per-file `if content_hash and manifest.get(fp) == content_hash:` at line 240 |
| 11 `atlas` | `src/prep/core/atlas/generator.py` | `is_stale()` at line 1560 — 3-trigger fingerprint check (module fp + hub file content + file count delta) gated on `_compute_fingerprint(...)` at line 1644 |

Stage 13 (`concepts`) has `_rationale_fingerprint` but it's a **DB-state delta check**, not the Phase 134 anti-pattern. Rationales can be written by non-pipeline paths (dashboard, MCP, agents); the changeset can't see those. Leave alone.

### Walker — 9 direct callers, no single chokepoint

| # | Caller | File:line | Today |
|---|---|---|---|
| 1 | `_compute_file_hashes` | `trace/builder.py:561` | via `effective_excludes()` |
| 2 | `_enumerate_files` | `trace/builder.py:588` | via `effective_excludes()` |
| 3 | `scan_for_presets` | `repo_profile.py:289` | inline merge |
| 4 | `_iter_repo_files` | `repo_profile.py:381` | inline merge |
| 5 | `compute_trace_coverage` | `trace/coverage.py:163` | inline merge (Phase 133b hot-fix) |
| 6 | `_walk_markdown` | `atlas/markdown_links.py:152` | inline merge (Phase 133b hot-fix) |
| 7 | repo-sanity-count | `orchestrator.py:2715` | **bypasses catalog** (only `**/.*/**`) |
| 8 | unknown caller | `project_helpers.py:548` | raw `os.walk` |
| 9 | `_walk_md_files` | `docs_grounding.py:282` | independent walker, opposite policy by design |

Plus `src/prep/core/index.py:375,378` (`CodeIndex` source code embedding) — explicitly out of scope per user (concurrent task, not a pipeline stage).

## The architectural endpoint

### Staleness

```
Stage 1 (TraceBuilder) ─emits─▶ changeset.json
                                     │
                       Every other stage reads it.
                       Every stale check is "is this file in changeset.modified|deleted?"
                       NO stage computes its own fingerprint.
```

`InferredEdgesEngine` and atlas's `is_stale()` become Worker-style consumers — same pattern as Phase 135 Tasks 1/2/3.

For atlas specifically: "stale iff `changeset.modified | deleted` is non-empty AND any of those files is in atlas's input set (the files that contributed to modules / epistemic / augmented data)." Or, since atlas summarizes the whole project, simpler still: **stale iff `changeset.modified | deleted` is non-empty**. The whole-project view means any change is potentially atlas-relevant.

### Walker

```
prep_engine.walk_repo  (the Rust primitive)
        ▲
        │  ONE wrapper imports it.
        │
prep.core.walker
  ├── walk_for_source(repo_root, *, user_exclude_globs=None, ...)
  │     ─ unions L1 (DEFAULT_EXCLUDE_DIR_NAMES + DEFAULT_EXCLUDE_FILE_GLOBS)
  │       + L2/L3 from repo_policy + caller's user_exclude_globs
  │     ─ used by trace/builder, trace/coverage, repo_profile,
  │       atlas/markdown_links, orchestrator sanity-count, project_helpers
  │
  └── walk_for_planning_docs(repo_root, *, include_agent_dirs=True)
        ─ L1 baseline MINUS the agent-output dirs (.claude, .cursor, .agents)
        ─ used by docs_grounding (concept synthesis)

EVERY OTHER FILE: no `import prep_engine` for walking. Lockdown test seals this.
```

## Out of scope (still)

- `src/prep/core/index.py` `CodeIndex` — concurrent task, separate concern, off-limits per user.
- Stage 5 knowledge initial pass — stage 10 overwrites it; keep legacy hash reuse.
- Stage 13 concepts `_rationale_fingerprint` — legitimate DB-state delta, NOT a file-staleness duplicate.

## Net diff target

**~−200 net production lines** is realistic. Numbers below are estimates from the actual surface:

| Change | Rough net |
|---|---|
| `inferred_edges.py` — delete manifest + hash compare + add changeset gate | −50 |
| `atlas/generator.py` — delete `is_stale()` body, `_compute_fingerprint`, fingerprint fields on models | −60 |
| New `prep.core.walker` module | +80 |
| Migrate 9 callers to wrapper (replace ~10 lines each with 2-3 line call) | −60 |
| Lockdown test + cutover tests | +30 |
| **Net** | **~−60 production** (plus the new walker module is centralization, not bloat) |

The "−200" framing earlier was too aggressive. The honest math is more like **−60 net production, with the new walker module as a +80 centralization line cost we explicitly take on for maintainability**.

## Risk

- `is_stale()` in atlas has 3 triggers, one of which (`file_count delta > 20%`) the changeset doesn't capture (file count is a count over the full walked set, not a delta over changed files). Need to either keep that one trigger or rephrase it as "changeset.added or .deleted is non-empty." Latter is simpler and arguably more correct.
- `orchestrator.py:2715` (repo-sanity-count) currently bypasses the catalog by design (it's a sanity check, not an indexing op). Migrating it to `walk_for_source` would apply the catalog — almost certainly the right call. Confirm with a single quick test that file counts don't get strange.
- `docs_grounding.py:_walk_md_files` has the opposite policy (includes `.claude/.cursor/.agents`). Must preserve via `walk_for_planning_docs(include_agent_dirs=True)`. Verified by a test.

## Done criteria

- `git grep "import prep_engine" src/prep/ --files-with-matches | wc -l` returns **1** (the new walker module only).
- `git grep -n "trace_inferred_hashes\|is_stale()\|_compute_fingerprint" src/prep/core/inferred_edges.py src/prep/core/atlas/generator.py` returns **0**.
- All pre-existing tests still pass (90 Phase 134/135 + pre-existing suites).
- New Phase 135.5 tests pass.
- Live verify: full pipeline rebuild on a no-change repo → stages 2/11 reuse 100%, all other stages do same.
