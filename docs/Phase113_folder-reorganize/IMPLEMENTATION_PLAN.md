# Implementation Plan

This is the step-by-step plan for executing Phase 113. It is organized as discrete steps with explicit acceptance criteria, verification commands, and PR boundaries. Each step is independently shippable, reviewable, and revertable.

Before starting any step, the relevant Open Questions in [04_RISKS.md](04_RISKS.md) for that step should be resolved.

---

## Step 0a — Discovery and verification (no code changes)

**Goal:** Resolve the open questions in [04_RISKS.md](04_RISKS.md) so that the centralization PR is built on confirmed facts, not extrapolated path-mapping data.

**Tasks:**

1. **Q1 — `CodeIndex.index_dir` resolution.** Read `core/index.py`, trace one writer end-to-end, confirm whether the `index/` segment is part of `self.index_dir` or part of the basename. Document the answer in this file (append a "Resolved questions" section at the bottom).
2. **Q2 — Dead `.db` stub investigation.** Full-tree grep for `codrag_settings.db` and `settings.db`. For each match, classify as "live writer", "live reader", "dead reference", "comment". Document.
3. **Q3 — `architecture/graph_state.json` purpose.** Find writer + readers. Confirm load-bearing or dead.
4. **Q4 — Trace-file site cardinality.** Run the grep commands from [04_RISKS.md](04_RISKS.md) Q4. Record the actual count.
5. **Q5 — Watcher path coupling.** Read `services/file_watcher.py` (or equivalent) for hardcoded paths.
6. **Q6 — Non-Python readers of `.codrag/` paths.** Run the cross-language greps from Q6.
7. **Q7 — Multiple-project safety.** Confirm by reading the project-load lifecycle.
8. **Discovery sweep.** `rg --type=python -e 'idx_dir / "' src/`, `rg --type=python -e 'index_dir / "' src/`, `rg --type=python -e 'project_index_dir' src/` — collect every site and cross-check against [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md). Add anything missing.

**Acceptance:**

- All open questions answered in writing (append to this file).
- Inventory updated to reflect any discovered sites or artifacts.

**Output:** A short addendum at the bottom of this file titled "Step 0a — Resolved Findings" with bullet points per question. No source changes.

**PR:** None (pure investigation).

---

## Step 0b — Introduce `project_paths` module (no behavior change)

**Goal:** Create the canonical accessor module without yet routing any caller through it. The module exists and is tested in isolation; nothing in the wider codebase depends on it yet.

**Tasks:**

1. Create `src/codrag/core/project_paths.py`. Initial content:

   ```python
   """Canonical path resolution for project index directory artifacts.

   Every artifact under project_index_dir(project) MUST be accessed
   through an accessor in this module. No string literals for these
   paths should exist anywhere else in the codebase.
   """
   from __future__ import annotations
   from pathlib import Path

   LAYOUT_VERSION = 1   # bumped to 2 in Step 4 (the move)

   # ── Identity & policy ───────────────────────────────────────────
   def version_marker_path(idx_dir: Path) -> Path: ...
   def project_pointer_path(idx_dir: Path) -> Path: ...
   def repo_policy_path(idx_dir: Path) -> Path: ...

   # ── Runtime ─────────────────────────────────────────────────────
   def pipeline_state_path(idx_dir: Path) -> Path: ...
   def clean_shutdown_marker_path(idx_dir: Path) -> Path: ...
   def reset_barrier_marker_path(idx_dir: Path) -> Path: ...

   # ── Plans ───────────────────────────────────────────────────────
   def goalposts_path(idx_dir: Path) -> Path: ...
   def roadmap_path(idx_dir: Path) -> Path: ...

   # ── Agents ──────────────────────────────────────────────────────
   def hr_roster_path(idx_dir: Path) -> Path: ...

   # ── Index ───────────────────────────────────────────────────────
   def index_dir(idx_dir: Path) -> Path: ...
   def index_documents_path(idx_dir: Path) -> Path: ...
   def index_embeddings_path(idx_dir: Path) -> Path: ...
   def index_manifest_path(idx_dir: Path) -> Path: ...
   def index_fts_path(idx_dir: Path) -> Path: ...

   # ── Knowledge ───────────────────────────────────────────────────
   def knowledge_documents_path(idx_dir: Path) -> Path: ...
   def knowledge_embeddings_path(idx_dir: Path) -> Path: ...
   def knowledge_manifest_path(idx_dir: Path) -> Path: ...

   # ── Trace stage outputs ─────────────────────────────────────────
   def trace_nodes_path(idx_dir: Path) -> Path: ...
   def trace_edges_path(idx_dir: Path) -> Path: ...
   def trace_augmented_path(idx_dir: Path) -> Path: ...
   def trace_inferred_edges_path(idx_dir: Path) -> Path: ...
   def trace_inferred_hashes_path(idx_dir: Path) -> Path: ...
   def trace_epistemic_path(idx_dir: Path) -> Path: ...
   def trace_modules_path(idx_dir: Path) -> Path: ...
   def trace_group_reasoning_path(idx_dir: Path) -> Path: ...

   # ── Trace manifests ─────────────────────────────────────────────
   def trace_manifest_path(idx_dir: Path) -> Path: ...
   def trace_augment_manifest_path(idx_dir: Path) -> Path: ...
   def trace_inferred_manifest_path(idx_dir: Path) -> Path: ...
   def trace_epistemic_manifest_path(idx_dir: Path) -> Path: ...
   def trace_modules_manifest_path(idx_dir: Path) -> Path: ...
   def trace_group_reasoning_manifest_path(idx_dir: Path) -> Path: ...
   def trace_validation_manifest_path(idx_dir: Path) -> Path: ...
   def trace_deepening_manifest_path(idx_dir: Path) -> Path: ...
   def trace_deep_knowledge_manifest_path(idx_dir: Path) -> Path: ...

   # ── Trace synthesis ─────────────────────────────────────────────
   def trace_swarm_synthesis_path(idx_dir: Path) -> Path: ...
   def trace_cluster_swarm_synthesis_path(idx_dir: Path) -> Path: ...

   # ── Atlas ───────────────────────────────────────────────────────
   def atlas_dir(idx_dir: Path) -> Path: ...
   def atlas_current_path(idx_dir: Path) -> Path: ...
   def atlas_previous_path(idx_dir: Path) -> Path: ...
   def atlas_manifest_path(idx_dir: Path) -> Path: ...
   def atlas_segments_manifest_path(idx_dir: Path) -> Path: ...
   def atlas_routing_path(idx_dir: Path) -> Path: ...
   def atlas_routing_embeddings_path(idx_dir: Path) -> Path: ...
   def atlas_updated_signal_path(idx_dir: Path) -> Path: ...
   def atlas_swarm_synthesis_path(idx_dir: Path) -> Path: ...
   def atlas_segments_dir(idx_dir: Path) -> Path: ...
   def atlas_roles_dir(idx_dir: Path) -> Path: ...

   # ── Stage manifests (SQLite-backed stages) ──────────────────────
   def pipeline_run_metadata_path(idx_dir: Path) -> Path: ...
   def rules_manifest_path(idx_dir: Path) -> Path: ...
   def concepts_manifest_path(idx_dir: Path) -> Path: ...
   def antibodies_manifest_path(idx_dir: Path) -> Path: ...

   # ── Existing organized subdirs ──────────────────────────────────
   def architecture_dir(idx_dir: Path) -> Path: ...
   def architecture_graph_state_path(idx_dir: Path) -> Path: ...
   def audit_dir(idx_dir: Path) -> Path: ...
   def audit_manifest_path(idx_dir: Path) -> Path: ...
   def audit_spaghetti_path(idx_dir: Path) -> Path: ...
   def git_evidence_dir(idx_dir: Path) -> Path: ...
   def git_evidence_churn_path(idx_dir: Path) -> Path: ...
   def git_evidence_signature_path(idx_dir: Path) -> Path: ...
   def logs_dir(idx_dir: Path) -> Path: ...
   def mcp_stdio_log_path(idx_dir: Path) -> Path: ...
   def pipeline_log_path(idx_dir: Path, ts: str) -> Path: ...
   def backups_dir(idx_dir: Path) -> Path: ...

   # ── Snapshots ───────────────────────────────────────────────────
   def snapshots_dir(idx_dir: Path) -> Path: ...
   def checkpoints_dir(idx_dir: Path) -> Path: ...
   def checkpoint_run_dir(idx_dir: Path, run_id: str) -> Path: ...
   def golden_checkpoint_dir(idx_dir: Path) -> Path: ...
   def branch_snapshots_dir(idx_dir: Path) -> Path: ...
   def branch_state_path(idx_dir: Path) -> Path: ...
   def branch_snapshot_dir(idx_dir: Path, branch: str) -> Path: ...

   # ── Enumeration helpers (used by destroy and the migrator) ──────
   def all_files(idx_dir: Path) -> list[Path]:
       """Every file artifact this module knows about, using current LAYOUT_VERSION."""
       ...

   def all_dirs(idx_dir: Path) -> list[Path]:
       """Every subdirectory this module knows about, using current LAYOUT_VERSION."""
       ...
   ```

   In Step 0b, every body returns the **current (v1) on-disk path**:

   ```python
   def trace_nodes_path(idx_dir): return idx_dir / "trace_nodes.jsonl"
   def trace_manifest_path(idx_dir): return idx_dir / "trace_manifest.json"
   def index_dir(idx_dir): return idx_dir / "index"
   def index_documents_path(idx_dir): return index_dir(idx_dir) / "documents.json"
   ...
   ```

   This is critical — Step 0b is a no-behavior-change refactor. Bodies match disk reality today.

2. Write unit tests for `project_paths` that pin every accessor to its v1 path. These tests will be updated when bodies change in Step 4.

3. Confirm `project_paths` builds, types check, lints clean.

**Acceptance:**

- Module exists with all accessors documented in [01_PATH_INVENTORY.md](01_PATH_INVENTORY.md).
- Tests pin every accessor to its current path.
- No call sites have been changed; nothing imports `project_paths` yet.

**Verification:**

```bash
.venv/bin/pytest tests/test_project_paths.py -v
.venv/bin/ruff check src/codrag/core/project_paths.py
.venv/bin/mypy src/codrag/core/project_paths.py
```

**PR:** "Phase 113 Step 0b — introduce project_paths module (unused)". Pure addition. Easy review.

---

## Step 1 — Route trace-file call sites through `project_paths`

**Goal:** Every reader/writer of trace files goes through `project_paths`. No more `idx_dir / "trace_*"` literals outside the module.

**Why this group first:** It's the highest-risk group (~40 sites, no centralization). Closing the dominant risk surface first means subsequent steps have less ambient anxiety.

**Tasks:**

1. For each writer in `core/trace/builder.py`, `core/augmenter.py`, `core/inferred_edges.py`, `core/epistemic_enrichment.py`, `core/group_reasoning.py`, the modules stage, and `core/atlas/generator.py`'s trace-related writes: replace `idx_dir / "trace_X"` with `project_paths.trace_X_path(idx_dir)`.
2. For every reader: same.
3. Update `TRACE_FILES` in `api/routers/trace_routes/shared.py` to derive from `project_paths.all_files()` filtered to trace-namespace, OR delete `TRACE_FILES` and have callers use `project_paths` directly.
4. Update tests.

**Acceptance:**

- Grep gate: `rg --type=python -e 'idx_dir / "trace_' src/` returns zero matches outside `project_paths.py` and the migrator.
- All tests pass.
- Pipeline runs to completion on dogfood (full reset + rebuild).

**Verification:**

```bash
.venv/bin/pytest tests/ -v
rg --type=python -e 'idx_dir / "trace_' src/ | rg -v 'project_paths\\.py|migrator'
# ↑ should be empty
.venv/bin/codrag serve  # smoke-test daemon startup
# manual: trigger a full pipeline via dashboard, confirm completion
```

**PR:** "Phase 113 Step 1 — route trace files through project_paths". Touches ~10 files, ~15 sites. Behavior identical.

---

## Step 2 — Route remaining call sites through `project_paths`

**Goal:** Same as Step 1 but for everything else: knowledge, index, atlas, plans, agents, runtime, stage manifests, subdir helpers.

**Tasks:**

1. Knowledge: `core/knowledge.py` + `core/trace/maintenance.py`.
2. Index: `core/index.py`, `core/repo_policy.py`. Resolve Q1 here — wherever the actual disk truth is, that's what the accessor returns.
3. Atlas: `core/atlas/*`.
4. Plans: `core/goalposts_models.py`.
5. Agents: `agents/hr/roster.py`.
6. Runtime: `services/pipeline/orchestrator.py`, `services/pipeline/recovery.py`.
7. Stage manifests: each stage that writes one.
8. Existing subdirs: `core/architecture_state.py`, `core/audit/*`, `core/git_evidence.py`, `services/pipeline_logger.py`, `services/branch_backup_manager.py`, `services/pipeline_checkpoint.py`.
9. Update `INDEX_FILES`/`ALL_DATA_FILES` in `shared.py` to derive from `project_paths.all_files()`.
10. Update `index_destroy_project()` in `enrichment.py` to use `project_paths.all_files()` and `all_dirs()` instead of hardcoded lists. **Closes the `architecture/` omission and any Q1-revealed gaps.**
11. Update tests.

**Acceptance:**

- Grep gates from [03_STRATEGY.md](03_STRATEGY.md) "Definition of done" return only `project_paths.py`, the migrator, and tests.
- All tests pass.
- Full reset on dogfood now removes `architecture/graph_state.json` (verifying the destroy fix).
- Pipeline runs to completion on dogfood.

**Verification:**

```bash
.venv/bin/pytest tests/ -v
rg --type=python -e 'idx_dir / "' src/ | rg -v 'project_paths\\.py|migrator|test_'
# ↑ should be empty (or just trivially 1-2 unmoved literals tracked as todos)
rg --type=python -e 'INDEX_FILES|TRACE_FILES|ALL_DATA_FILES' src/
# ↑ should match only project_paths-derived helpers
ls .codrag/architecture/  # should exist before reset
# trigger full reset via dashboard
ls .codrag/  # confirm architecture/ is gone
```

**PR:** "Phase 113 Step 2 — route remaining paths through project_paths". Touches ~15 files, ~55 sites. Behavior identical except for closed destroy gaps (which are bug fixes, not regressions).

---

## Step 3 — Snapshot test for current layout

**Goal:** Lock in the current (v1) layout via a snapshot test, so when the migrator runs in Step 4 we have a baseline to migrate from in tests.

**Tasks:**

1. Add `tests/test_project_layout.py` with two assertions:
   - `test_v1_layout_paths`: For a fresh `.codrag/` populated by a known fixture, every file is at its expected v1 path. Uses `project_paths` accessors.
   - `test_destroy_enumerates_everything`: Build a fixture, call destroy, confirm directory is empty.
2. Pin the test against the v1 layout for now. In Step 4, this test gets a v2 sibling.

**Acceptance:**

- New test passes against current `project_paths` v1 bodies.
- Test would fail if any accessor body changed without the fixture changing.

**PR:** "Phase 113 Step 3 — snapshot test for layout". Tests-only.

---

## Step 4 — The move (layout v2)

**Goal:** Change `project_paths` accessor bodies to point at the new layout. Add migrator. Bump `LAYOUT_VERSION` to 2. Run migrator at startup.

**Tasks:**

1. **Update accessor bodies in `project_paths.py`** to point at the v2 layout per [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md).

2. **Bump `LAYOUT_VERSION` to 2.**

3. **Update `all_files()` and `all_dirs()`** to enumerate the v2 layout.

4. **Write the migrator** at `src/codrag/core/project_paths_migrator.py`:

   ```python
   def needs_migration(idx_dir: Path) -> bool:
       """True if version file is missing or < LAYOUT_VERSION."""

   def migrate(idx_dir: Path) -> MigrationReport:
       """Move files from v1 to v2 layout. Idempotent. Atomic per file.

       1. Refuse if .migration_in_progress exists (previous migration crashed).
       2. Write .migration_in_progress.
       3. For each (old_path, new_path) in V1_TO_V2_MAPPING:
            - skip if old_path doesn't exist
            - mkdir -p new_path.parent
            - shutil.move(old_path, new_path) (preserves mode bits)
       4. Sweep for unrecognized files in idx_dir; log them, leave in place.
       5. Write version file = '2'.
       6. Remove .migration_in_progress.
       7. Return report (moved, skipped, unrecognized, errors).
       """
   ```

   The `V1_TO_V2_MAPPING` is a hand-maintained dict in the migrator file. Each entry is one rename. It is not derived from `project_paths` — it is a frozen snapshot of the v1 layout (because by the time the migrator runs, `project_paths` only knows v2).

5. **Wire the migrator into project load.** Wherever `project_index_dir()` is first called for a project (likely on project open / daemon serve), gate it:

   ```python
   idx_dir = project_index_dir(proj)
   if needs_migration(idx_dir):
       report = migrate(idx_dir)
       logger.info("Migrated %s to layout v%s: %s", proj.id, LAYOUT_VERSION, report)
   ```

   Crucially, this runs **before** the file watcher starts and **before** any reader/writer touches the directory.

6. **Update Step 3's snapshot test** with a v2 sibling that asserts the new layout. The v1 test stays (using historical paths) and is used by the migrator test.

7. **Add migrator tests:**
   - `test_migrate_dogfood_fixture`: Build a v1-layout fixture (full set of artifacts), run migrator, assert v2 layout exactly.
   - `test_migrate_idempotent`: Run migrator twice, assert second run is a no-op.
   - `test_migrate_partial_v2_resumes`: Hand-build a half-migrated state, run migrator, assert it completes.
   - `test_migrate_preserves_hr_roster_mode`: Confirm 0600.
   - `test_migrate_unrecognized_files_logged`: Drop a stranger file in v1 layout, confirm it's preserved + logged.
   - `test_migrate_refuses_on_in_progress_marker`: Pre-create `.migration_in_progress`, confirm migrator refuses.

8. **Update destroy enumeration** if needed (it should already use `project_paths`, so this is automatic — but verify).

9. **Manual dogfood validation:**
   - Make a tarball backup of the dogfood `.codrag/` first.
   - Start the daemon. Migrator runs.
   - Inspect `.codrag/` — confirm it matches [02_TARGET_LAYOUT.md](02_TARGET_LAYOUT.md).
   - Trigger a full pipeline run. Confirm completion.
   - Trigger a full reset. Confirm `.codrag/` returns to a true blank state.

**Acceptance:**

- All tests pass, including new migrator tests.
- Dogfood index migrated successfully.
- Fresh build produces the documented layout exactly.
- Full reset wipes everything.

**Verification:**

```bash
.venv/bin/pytest tests/test_project_paths.py tests/test_project_layout.py tests/test_migrator.py -v
.venv/bin/pytest tests/ -v
# manual:
tar -czf /tmp/codrag-dogfood-pre-migration.tgz .codrag/
.venv/bin/codrag serve
# inspect logs for migration report
ls .codrag/
# expected: version, project.json, repo_policy.json, runtime/, plans/, agents/, ...
```

**Rollback plan:** If the migrator fails on dogfood, restore from the tarball, file an issue with the migration report, do not merge the PR.

**PR:** "Phase 113 Step 4 — migrate to layout v2". Touches `project_paths.py`, adds migrator, adds startup hook, updates tests. The biggest semantic change in the phase but contained to a small surface.

---

## Step 5 — Documentation and lockdown

**Goal:** Document the new layout for future contributors and prevent regression.

**Tasks:**

1. Update `CLAUDE.md` and `AGENTS.md` if they reference any old paths (probably not, but check).
2. Add a section to `docs/architecture/` (or wherever the architecture docs live) documenting `project_paths` as the canonical resolver.
3. Add a CI check (or pre-commit hook) that fails if `idx_dir / "..."` literals appear outside `project_paths.py`. The grep gate from [03_STRATEGY.md](03_STRATEGY.md) becomes enforced.
4. Update [README.md](README.md) status to "Phase A complete".

**Acceptance:**

- Docs reflect new layout.
- Grep gate enforced in CI.

**PR:** "Phase 113 Step 5 — document and lock". Mostly docs.

---

## Step 6 — Phase B trigger (separate phase)

After Phase A is stable on dogfood for a week, kick off Phase B per [05_PHASE_B_DEDUPE.md](05_PHASE_B_DEDUPE.md).

---

## Summary table

| Step | Type | PR size | Risk | Acceptance |
|---|---|---|---|---|
| 0a | Investigation | None | n/a | Open questions answered |
| 0b | Pure addition | Small | LOW | New module + tests, unused |
| 1 | Refactor | Medium | MED | Trace sites routed |
| 2 | Refactor | Medium | MED | All other sites routed; destroy fixed |
| 3 | Test addition | Small | LOW | v1 layout pinned |
| 4 | Move + migrator | Medium | HIGH | New layout active |
| 5 | Docs + CI | Small | LOW | Locked down |
| 6 | Trigger | n/a | n/a | Phase B started |

**Total estimated wall time:** 2-3 days of focused work spread across a week, accounting for review and dogfood validation between PRs.

---

## Step 0a — Resolved Findings (filled in during Step 0a)

*To be appended after Step 0a runs. Each open question gets a short answer here, with file:line citations and any updates to the inventory.*

### Q1 — `CodeIndex.index_dir`

*[pending]*

### Q2 — Empty `.db` stubs

*[pending]*

### Q3 — `architecture/` purpose

*[pending]*

### Q4 — Trace site cardinality

*[pending]*

### Q5 — Watcher path coupling

*[pending]*

### Q6 — Non-Python readers

*[pending]*

### Q7 — Multi-project safety

*[pending]*

### Discovery sweep additions

*[pending]*
