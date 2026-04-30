# Reset Clean-Slate Design

**Status:** Draft (awaiting review)
**Date:** 2026-04-29
**Phase:** Phase 119 follow-up / scoped reset hardening
**Scope:** `DELETE /projects/{id}/enrichment/full-reset` (6–15) and `DELETE /projects/{id}/finalize/full-reset` (11–15)

## Problem

The two scoped Danger-Zone reset endpoints leave stale state behind across multiple subsystems. After clicking Reset 6–15, the dashboard reports stages as already complete, in-memory caches feed phantom counts, and the next pipeline run reuses fingerprints from data the reset was supposed to delete.

User-visible failure mode: "Concept Seeding ✓ 1 concepts" appears after a fresh reset. Behind it, the concept store has 200 stale rows, the antibody store has 373, the pipeline-run journal has 12 stale rows, and the `audit/` directory still contains `spaghetti.json`. Stage-internal incremental reuse (clustering fingerprint match, deepening drift detection, knowledge incremental embed) reads pre-reset artifacts when they survive on disk.

The root pattern is two-sided:

1. The wipe is incomplete. `DEEP_ENRICHMENT_FILES` is a curated denylist that misses real outputs (`atlas_swarm_synthesis.json`, `trace_cluster_swarm_synthesis.json`, `trace_swarm_synthesis.json`, the `audit/` rmtree leak), and several SQLite-backed stores never get touched at all (`pipeline_runs`, `KnowledgeIndex` in-memory).
2. Cleanup failures are swallowed. `concept_store.clear_project()` and `antibody_store.clear_project()` are wrapped in `try/except` blocks that log at DEBUG and return success. Empirical evidence shows neither store has actually been cleared in days despite multiple resets.

## Goal

Reset means reset. When `DELETE /projects/{id}/enrichment/full-reset` returns 200:

- Every artifact produced by stages 6–15 is gone from disk.
- Every SQLite row produced by stages 6–15 is gone (concepts, antibodies, journal rows for `deep_enrichment` and `finalize` groups).
- Every in-memory cache that contributes to 6–15 state is invalidated.
- Selfheal cannot resurrect 6–15 data on subsequent daemon restart until the next finalize completes legitimately.
- The next pipeline run starting at stage 6 behaves as if 6–15 has never run — no fingerprint reuse, no drift cache hits, no zombie concepts.
- Stages 1–5 outputs survive untouched.

`DELETE /projects/{id}/finalize/full-reset` provides the same guarantees scoped to 11–15. Stages 1–10 outputs survive untouched.

Backups (timestamped copies created when developer-debug mode is enabled) are explicitly preserved as a separate concern; they live under `<idx_dir>/backups/` which is on the keep list.

A future "repair" capability that *intentionally* resurrects from `_golden/` snapshots is out of scope. Notes captured in `## Future work` below.

## Non-goals

- Investigating the overnight daemon-death pattern. Tracked separately.
- Refactoring the journal schema. We add a delete-by-project method; the rest stays.
- Changing observation-store behavior. Observations are user-authored cross-session notes and survive reset by design.
- Changing the system-concept-seeder behavior (re-seeds 1 concept per project on daemon startup). It runs after reset by design and is independent of reset correctness.

## Approach

### Architecture

Keep `_scoped_full_reset()` in `src/prep/api/routers/trace_routes/enrichment.py` as the single reset orchestrator. Both endpoints (`enrichment_full_reset`, `finalize_full_reset`) delegate to it with scope-specific parameters. No new "reset coordinator" layer.

What changes inside the orchestrator:

- Disk wipe switches from a curated denylist (`DEEP_ENRICHMENT_FILES` etc.) to an **allowlist**. The allowlist is derived at build time from a single declarative `STAGE_OUTPUTS` registry that maps every stage to the files / directories it produces. Reset 6–15 keeps the union of stage 1–5 outputs; Reset 11–15 keeps the union of stage 1–10 outputs.
- Cleanup failures for journal / concept store / antibody store / KnowledgeIndex are now **fatal** to the reset call. They surface as a 500 with the failure detail. The barrier remains in place so partial state can't be misinterpreted as clean.
- A new `pipeline_journal.delete_runs(project_id, *, groups: set[str] | None)` method removes stale `pipeline_runs` rows scoped by group (`deep_enrichment`, `finalize`, or both).
- A new `knowledge_index.invalidate_project(project_id, *, scope: str)` method clears the in-memory chunk cache for a project. For `scope='enrichment'` it drops everything; for `scope='finalize'` it's a no-op (finalize doesn't touch KnowledgeIndex).
- Stage-internal reuse paths (`cluster.py:_cluster_fingerprint`, `deepening.py` drift, `group_reasoning.py` cache, `knowledge.py` incremental) gain a barrier check. A new `recovery.is_reuse_blocked(project_id, *, stage_group)` helper centralizes the logic. If barrier scope subsumes the consumer's group, the function returns True and the stage treats existing artifacts as nonexistent.

### Data flow during reset

```
1. PRE-FLIGHT
   - Reject if pipeline running (409)
   - Acquire project-scoped reset lock so concurrent resets serialize

2. WRITE BARRIER FIRST (atomicity primitive)
   - .reset_barrier file written before any wipe
   - Daemon-restart mid-wipe is safe: barrier still gates selfheal,
     wipe is idempotent

3. STOP IN-FLIGHT WORK
   - pipeline_orchestrator.clear_project() (existing)
   - knowledge_index.invalidate_project(project_id, scope=...) (new)
   - _project_trace_indexes.pop(project_id) (existing)

4. WIPE DISK (allowlist-based)
   - Optional debug backup of allowlist-violating files (existing logic)
   - For every entry in <idx_dir>:
       keep if name in build_keep_set(scope)
       else: unlink (file) or rmtree (dir)
   - PROJECT_META always preserved: project.json, repo_policy.json,
     logs/, backups/

5. WIPE STORES (errors fatal)
   - pipeline_journal.delete_runs(project_id, groups=...)
   - concept_store.clear_project(project_id)
   - antibody_store.clear_project(project_id)

6. WIPE CHECKPOINTS
   - .checkpoints/ rmtree (existing)

7. RETURN 200 — barrier remains active
```

### Anti-zombie guarantees

**Selfheal cannot override reset.** Two layers:

1. The barrier file is written **before** any wipe step. If the process dies mid-wipe and restarts, recovery sees the barrier and refuses to resurrect orphan outputs (existing F-78 protection).
2. After step 7 returns, the barrier persists until the next legitimate finalize completes. During that window, no recovery path can write to 6–15 territory.

**Stage-internal reuse cannot pull stale data.** Every existing reuse read site that does fingerprint / hash / drift comparison gains an early-exit:

```python
# In cluster.py, deepening.py, group_reasoning.py, knowledge.py
if recovery.is_reuse_blocked(project_id, stage_group=GROUP_DEEP_ENRICHMENT):
    return {}   # treat as no prior data
```

This is what would have prevented the 84/247 fingerprint reuse observed in the recent run.

### Scope-aware behavior

Both reset endpoints share `_scoped_full_reset()`. They pass different parameters:

| Behavior | Reset 6–15 (`enrichment_full_reset`) | Reset 11–15 (`finalize_full_reset`) |
|---|---|---|
| Disk allowlist preserves | stages 1–5 outputs + project meta | stages 1–10 outputs + project meta |
| Journal rows wiped | groups: `{deep_enrichment, finalize}` | group: `{finalize}` only |
| Concept store wiped | yes (concepts come from stage 13) | yes (same) |
| Antibody store wiped | yes (come from stage 15) | yes (same) |
| `KnowledgeIndex` invalidate scope | `enrichment` (kills stage-10 chunks) | `finalize` (no-op) |
| Barrier reason / scope | `enrichment_reset` / `enrichment` | `finalize_reset` / `finalize` |
| Reuse gates that block | clustering, deepening, group_reasoning, knowledge incremental | atlas swarm, concepts swarm, audit reuse |
| Auto-clear barrier when | finalize group completes (existing) | finalize group completes (existing) |

The barrier scope is consulted by `is_reuse_blocked()` so that an enrichment-scope barrier subsumes finalize-scope blocking, but a finalize-scope barrier does not block enrichment reuse.

### `STAGE_OUTPUTS` registry

A new declarative dict in `src/prep/services/pipeline/__init__.py` (or co-located with the existing `StageId` constants):

```python
STAGE_OUTPUTS: dict[StageId, OutputSpec] = {
    'structural':       OutputSpec(files=['trace_nodes.jsonl', 'trace_edges.jsonl', 'trace_manifest.json']),
    'inferred_edges':   OutputSpec(files=['trace_inferred_edges.jsonl', 'trace_inferred_hashes.json', 'trace_inferred_manifest.json']),
    'catalogue':        OutputSpec(files=['catalogue.jsonl', 'catalogue_manifest.json',
                                          'trace_augmented.jsonl', 'trace_augment_manifest.json']),
    'validation':       OutputSpec(files=['validation_manifest.json']),
    'knowledge':        OutputSpec(files=['documents.json', 'embeddings.npy', 'manifest.json']),
    'enrichment':       OutputSpec(files=['trace_epistemic.jsonl', 'trace_epistemic_manifest.json']),
    'group_reasoning':  OutputSpec(files=['trace_group_reasoning.jsonl', 'group_reasoning_manifest.json']),
    'clustering':       OutputSpec(files=['trace_modules.jsonl', 'trace_modules_manifest.json', 'trace_cluster_swarm_synthesis.json']),
    'deepening':        OutputSpec(files=['deepening_manifest.json']),
    'deep_knowledge':   OutputSpec(files=['deep_knowledge_manifest.json']),
    'atlas':            OutputSpec(files=['atlas.json', 'atlas_prev.json', 'atlas_manifest.json',
                                          'atlas_segments_manifest.json', 'atlas_routing.json',
                                          'atlas_routing_embeddings.npy', 'atlas_updated.signal',
                                          'atlas_swarm_synthesis.json'],
                                   dirs=['atlas_roles', 'atlas_segments']),
    'rules':            OutputSpec(files=['rules_manifest.json']),
    'concepts':         OutputSpec(files=['concepts_manifest.json']),
    'audit':            OutputSpec(files=['audit_manifest.json'], dirs=['audit']),
    'antibodies':       OutputSpec(files=['antibodies_manifest.json']),
}
```

`build_keep_set(scope)` returns the union of `OutputSpec` entries for the stages that survive the given reset. Reset 6–15 → union of 1–5. Reset 11–15 → union of 1–10.

`PROJECT_META` (always preserved) is a small, fixed set: `project.json`, `repo_policy.json`, the `logs/` directory, the `backups/` directory. It does NOT include `pipeline_run_metadata.json`, which is run-state and gets wiped along with the stage outputs that produced it. The exact set lives in a single constant `PROJECT_META_ALLOWLIST` co-located with `STAGE_OUTPUTS`.

Note: the `catalogue` stage's exact output filenames must be confirmed against current code before merge. The values shown above are based on existing references in the repo; if they've drifted, the registry entry updates without affecting the rest of the design.

This registry also closes the "missing swarm synthesis files" bug (atlas swarm + cluster swarm now declared as their stage's outputs).

### Error handling

- **Store wipe failures (concepts, antibodies, journal, KnowledgeIndex)** → 500 with `{detail: {step: 'concept_store.clear_project', error: '...'}}`. Barrier stays so retry is safe.
- **Disk wipe failures (per-file unlink, rmtree errors)** → collected into `errors` list, response status becomes 207 if non-empty. UI surfaces as warning.
- **Logging** raised from DEBUG to WARNING for any reset-cleanup path. Reset is rare and explicit; failures should never be silent.

## Testing

Three new test files plus an extension of the existing `test_scoped_full_reset.py`. All zombie tests run parametrized over both endpoints `[enrichment_full_reset, finalize_full_reset]` to prevent scope drift.

### `tests/test_scoped_full_reset_zombies.py`

For each subsystem, set up state, call reset, assert it's gone:

- 5 concepts seeded → reset → 0 rows in concept_store for project_id
- 5 antibodies seeded → reset → 0 rows in antibody_store for project_id
- 3 journal runs inserted with various statuses → reset → 0 rows for project_id (scoped by group)
- KnowledgeIndex populated with 100 chunks → reset → `index.chunk_count(project_id) == 0`
- `audit/spaghetti.json` written → reset → directory absent

### `tests/test_scoped_full_reset_selfheal_race.py`

- Write `_golden/` snapshots, call reset, simulate daemon restart by re-instantiating recovery, assert `auto_heal()` does NOT resurrect 6–15 outputs while barrier active
- Direct selfheal invocation with barrier present → short-circuits, returns no-op
- Crash-mid-reset simulation: write barrier, partial wipe, kill, restart → daemon completes the wipe-equivalent behavior (treats remaining files as orphan), no resurrection

### `tests/test_scoped_full_reset_reuse_gate.py`

- Seed `trace_modules.jsonl` with 100 modules → set barrier → run clustering → assert `existing_modules == 0` (treated as no prior data)
- Seed `trace_epistemic.jsonl` with stale entries → set barrier → run deepening → assert no drift cache hits
- Same for group_reasoning fingerprint cache and knowledge incremental
- After clearing barrier, re-run each → assert reuse works as expected (happy path not broken)

### Extension to existing `tests/test_scoped_full_reset.py`

- Drop a file with a made-up name (`atlas_swarm_synthesis_v99.json`) into idx_dir → call reset → assert it's gone (proves allowlist behavior, not denylist)
- Drop `made_up_stage_dir/` into idx_dir → call reset → assert it's gone

## Future work

A "repair" capability that *intentionally* resurrects from `_golden/` snapshots and other recovery sources is captured here for the future:

- Repair would be a separate endpoint, not invoked by reset
- Use case: user wants to recover from accidental Reset All on a project they wanted to keep
- Implementation would consult `_golden/` snapshot, branch_snapshots, and the journal to reconstruct prior state
- Out of scope for this work — reset must be a clean slate first

## Files touched

- `src/prep/api/routers/trace_routes/enrichment.py` — `_scoped_full_reset` rewrite
- `src/prep/services/pipeline/__init__.py` — `STAGE_OUTPUTS` registry, `build_keep_set` helper
- `src/prep/services/pipeline_journal.py` — new `delete_runs` method
- `src/prep/services/pipeline/recovery.py` — new `is_reuse_blocked` helper, barrier scope tracking
- `src/prep/core/cluster.py` — barrier check in `load_existing_modules`
- `src/prep/core/deepening.py` — barrier check in drift detection
- `src/prep/core/group_reasoning.py` — barrier check in fingerprint reuse
- Knowledge incremental-embed entry point (path TBD during implementation; planning step 1 confirms location) — barrier check
- KnowledgeIndex in-memory cache holder (path TBD during implementation; planning step 1 confirms location) — new `invalidate_project` method
- `tests/test_scoped_full_reset.py` — extend with allowlist assertions
- `tests/test_scoped_full_reset_zombies.py` — new
- `tests/test_scoped_full_reset_selfheal_race.py` — new
- `tests/test_scoped_full_reset_reuse_gate.py` — new
