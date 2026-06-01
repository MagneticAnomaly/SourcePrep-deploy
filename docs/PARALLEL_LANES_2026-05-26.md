# Parallel-Lane Coordination — 2026-05-26

Single source of truth for the multi-AI work split decided 2026-05-26. Supersedes ad-hoc audit summaries in chat; cross-links into `MASTER_TODO.md` for the canonical per-item history. When this doc and `MASTER_TODO.md` disagree, **this doc is newer** — it reflects code-state verified 2026-05-26 against MASTER_TODO claims that were typed weeks earlier.

## Lane status — 2026-06-01 (rolling)

> Updated as each lane lands. Newest at top.

| Lane | Owner | Status | Last update | Notes |
|---|---|---|---|---|
| **A — Docs frontier** | Prior session | ✅ **SHIPPED on `main`** | 2026-05-28 | See "Lane A completion record" below. |
| **B — Python correctness (Phase 136)** | Prior session | ✅ **Parts 02 / 04 / 10 verified on `main`** · ⚠️ Part 09 open | 2026-05-28 | Parts 02 (`e16023c8`), 04 (`9c80a83a`), 10 (`a8d4c02f` + `a595d9c2`) had already shipped to `main`; verified post-rebuild — 14 Python dependents, 5/5 + 39/39 tests, scored_count 0→406. Part 09 still fires in 2026-05-28 07:20 telemetry; handed to next session. Details + Part 09 work order in "Lane B closeout" below. |
| **C — Python reliability (Phase 127 + 129)** | Merged this session | ✅ **MERGED to `main`** | 2026-06-01 | Merge commit `57a4e335` (`--no-ff` from `phase-127-129-hygiene`). Single conflict at `atlas/generator.py` swarm-construction kwargs resolved by combining Phase 141's `max_wall_time_s=wall_budget` with Lane C's `project_id=self.project_id or None`. 4 other files auto-merged. `tests/test_llm_direct_sites_hold_guarded.py::F2_SITES` re-anchored to post-merge line numbers. 73-test Lane-A+C+atlas cross-lane sweep + 172-test wider atlas/swarm/Lane-B sweep both green. Lane C completion record below remains the canonical scope record. |
| **Phase 141 (outside lanes)** | Emergent (prior session) | ✅ **SHIPPED on `main`** | 2026-05-28 | Unrelated to A/B/C — emergent 7-fix prevention of silent swarm cache truncation triggered by the 2026-05-26 incident. Commit `e066e5f7` on `origin/main` (pushed alongside Lane A's `c4fa0e39` on 2026-05-28). End-to-end validated in 2026-05-28 full rebuild. See "Phase 141 completion record" below. |

### Atlas swarm-success persistence fix — 2026-05-28 (cross-lane), shipped as `c4fa0e39`

While Lane A was verifying daemon health post-restart, a daemon-restart-triggered rebuild surfaced that `core/atlas/generator.py:generate_segmented()` had a Phase-79 regression: the swarm-success branch returned `(root_doc, swarm_docs)` without calling `self._save(root_doc)`, so the root `atlas.json` was never persisted on swarm-success runs. Sub-segments, routing, and the orchestrator-level `atlas_manifest.json` all wrote correctly — only the root was missing.

Cascade: dashboard atlas panel fell back to `.checkpoints/_golden/atlas.json` (showing stale data), `/pipeline/status` reported `atlas.exists: false`, and Phase 136 Part 11's `is_stale()` short-circuit never fired because `_load_consumed_changeset_run_id` reads from `atlas.json` which was missing.

One-line fix at `generator.py:443` (post-Lane-C merge: line 457) plus regression test at `tests/test_atlas_swarm.py::test_swarm_success_writes_root_atlas_json`. Lives in the Phase 136 family but landed in Lane A's commit stream because Lane A's testing pass surfaced it. **Verified in production 2026-05-28: `atlas.json` written at 2026-05-28T17:46 EDT with `file_count: 2047`.**

### Lane C merge — 2026-06-01, commit `57a4e335`

`git merge --no-ff phase-127-129-hygiene` into `main`. Branch had been sitting unmerged since 2026-05-28 per Lane C closeout's "branch only, not pushed" status. Merge ran cleanly except for a single content conflict at `atlas/generator.py` swarm-construction kwargs. Resolution: combine Phase 141's dynamic `max_wall_time_s=wall_budget` with Lane C's `project_id=self.project_id or None` — both are orthogonal improvements over the pre-Phase-141, pre-Lane-C state and both retained. Comment retained from Lane C (now-correct: project_id IS threaded).

4 other Python files auto-merged: `cluster.py`, `group_reasoning.py`, `swarm_orchestrator.py`, `services/pipeline/orchestrator.py`. Phase 141 invariants intact: `compute_swarm_wall_budget`, `_attempt_write_guard_recovery`, `_journal_run_failed`, `_compute_allowed_shrink_ratio`, `IntegrityGuard` all present. Lane B Part 02/04/10 surfaces verified clean post-merge.

Test-suite re-anchoring landed inside the merge commit (per Lane C closeout's predicted "F2 catalog line numbers drift on merge" runbook):

```
cluster.py     1301/1444/1479/1517/1846  →  1313/1456/1491/1529/1885
atlas/generator 256/579/728/889           →  257/620/769/930
group_reasoning 484/773                    →  501/832
concept_seeder  217/809/1278 unchanged.
```

Post-merge verification:
- 73 tests across Lane C suite + Lane A atlas swarm + atlas-stale + trace_routes invariant — all green.
- 172 tests across wider atlas/swarm/Lane-B-surface (test_atlas, test_atlas_validators, test_atlas_identity_brand, test_atlas_determinism, test_atlas_hash, test_partial_swarm_refused, test_spaghetti_scorer, test_audit_size_fallback, test_prep_search_locate_fallback) — all green.
- Pre-existing failures (test_concept_seeder_swarm, test_pipeline_budget, test_pipeline_stage_endpoint, test_pipeline_status_epistemic_counts, test_pipeline_scheduler) confirmed NOT introduced by Lane C — pre-existing per Lane C closeout doc.

## Lane A completion record (2026-05-26 → 2026-05-28)

**Branch:** `main`. **Shipped to `origin/main`** in nine commits:

```
c4fa0e39  fix(phase136): atlas swarm-success path must persist root atlas.json
4aed3c4d  fix(phase131): deep Phase NN sweep on publicly-shipping component surfaces
6c8a9109  fix(marketing): repoint immune-system docs links to /mcp (pre-existing broken)
f1001577  fix(phase131): strip Phase NN leaks + SiteFooter URL from public storybook
13e0bc4c  feat(phase137): commit live-asset implementation pass (29 placements)
beca8b55  fix(phase138): re-key cross-repo refs to /how-it-works/, mark phase done
2bb3a281  fix(docs): mark mcp/ides and mcp/terminal as client components
a66f075d  docs(coordination): add 3-lane parallel work plan for next batch
d66eed89  docs(phase138): rename /concepts/ -> /how-it-works/, move 4 explainer guides
```

**Closed scope items:**
- Phase 138 — `/concepts/` → `/how-it-works/` rename, 4 explainer guides migrated, 9 permanent redirects, sidebar/sitemap updated, ConceptPageShell applied to all 8 pages, cross-repo URL re-key (panelRegistry + 5 components + 1 story fixture + marketing redirect destination), CLAUDE.md / AGENTS.md verified clean.
- Phase 137 — implementation pass committed (was sitting uncommitted 12 days). `<StoryEmbed>` iframe wrapper deleted; 24 native React `<Demo*>` wrappers added in `websites/apps/docs/src/components/demos.tsx` (1372 lines). Matrix marked SHIPPED (9 of 10 "pending" rows verified already-shipped vs source; 1 remains genuinely deferred — `searchBuildWorkerDemo` on path-weights).
- Phase 131 §5.1 — build-time autodocs:false + 24-story exclusion glob (already done in §6; matrix marked done).
- Phase 131 §5.2 — deep Phase NN sweep on publicly-shipping JSDoc surfaces (`AtlasLensPanel/*`, `ConceptsPanel`, `types.ts`, `api/{mock,client}.ts`, `index.ts`, plus the user-facing JSDoc surfaces in `BarrierIndicator`, `StageRegenerateButton`, `FileExplorerDetail`, `EndpointManager`). Remaining strings in the bundle (Phase 102/114/117) come from `GraphEnrichmentPipeline`/`RebuildDropdown`/`RebuildingRow`/`ProvenanceChip` — with `autodocs:false` they are not user-visible via Controls; deferred until a future Storybook public mode might surface them.
- Phase 131 §5.3 — MOOT after Phase 137 deleted `StoryEmbed`; docs-site no longer depends on Storybook story IDs.
- Marketing `/concepts/immune-system` pre-existing broken link — repointed to `/mcp`.
- `mcp/ides` + `mcp/terminal` Phase 132 build break — `"use client"` directives added; `next build` now green.

**Dogfooded against prep MCP after daemon reconnect:**
- `prep` ambient atlas — current state retrievable; atlas/cluster summaries pending refresh from in-flight clustering run.
- `prep_search "how-it-works docs section"` — 5/5 hits on the renamed pages, scores 0.69-0.72.
- `prep_search "where is demos.tsx"` — auto-LOCATE classified, found both `demos.tsx` (new) and pre-existing `cli-demos.tsx`.
- `prep_observe save` × 2 — Phase 138 outcome anchored to `docs.ts` (id `aabedb964aa5`), Phase 128 recovery verification anchored to `recovery.py` (id `b64a9ee916aa`).

**Verified runtime behaviour from daemon restart 2026-05-28:**
- ✅ Phase 128 recovery — 4 historical crashed `deep_enrichment` runs cleaned at startup with explicit `"Process terminated (cleaned on restart)"` markers; checkpoints preserved at `.sourceprep/.checkpoints/run-*`.
- ✅ Phase 134/135 changeset-driven reuse — multiple stages report `provenance.state: "match"` confirming the changeset compare is correctly gating rebuilds.
- 🔍 Atlas swarm-success persistence bug found and fixed (see cross-lane section above).

**Out of Lane A scope (won't ship without manual involvement):**
- Phase 137 P137-T1 `netlify.toml` env-var push — gated on explicit user signal per `feedback_explicit_push_only.md`. Functionally moot for in-page demos (Phase 137 deleted `StoryEmbed`) but still gated for any future iframe-based content.
- Phase 137 visual regression sweep — needs interactive dev-server walkthrough.
- Phase 131 Bucket C component decisions — needs product input.
- Remaining Phase NN strings in transitively-bundled excluded-story components — not user-visible with `autodocs:false`.

## Phase 141 completion record — Silent shrink prevention (2026-05-27 / 2026-05-28)

> **Outside the A/B/C lane structure.** Phase 141 was emergent work triggered by the 2026-05-26 silent-shrink incident; it is unrelated to any of the three planned lanes. Documented here for unified-testing coordination since it touches files (`atlas/generator.py`, `orchestrator.py`, `cluster.py`, `group_reasoning.py`, `swarm_orchestrator.py`) that overlap with Lane B and Lane C's planned scope — see "Cross-lane impact" below.


**Branch:** `main`. **Commit:** `e066e5f7` (single bundled commit, not pushed per `feedback_explicit_push_only.md`).

### Trigger

User reported a rebuild "ended at the end of phase 9" hours after a daemon restart. Investigation surfaced a 2026-05-26 silent data-loss incident: `trace_group_reasoning.jsonl` was truncated from 166 to 61 records (37% of prior) on a barrier-triggered rebuild. The IntegrityGuard detected MAJOR_SHRINK and logged `"Write guard: RESTORED 10 files from checkpoint"` — but the restore did not actually touch the shrunken file, and the stage advanced as "completed". Subsequent golden checkpoint promotion then captured the corrupted state.

### Root cause (three independent bugs converged)

1. **`pipeline_checkpoint.TRACE_FILES` omitted `trace_group_reasoning.jsonl`.** `create_checkpoint` and `restore_checkpoint` iterate that list — anything outside it was unprotected by the per-run rollback path, even though it appeared in `_GOLDEN_FILES`. The lists had drifted out of sync.
2. **`_attempt_write_guard_recovery` accepted `restored > 0` as success without verifying the specific shrunken file was actually restored.** "RESTORED 10 files" was technically true but functionally a lie when none of the 10 were the corrupted one.
3. **Swarm fan-out wall cap fired at 900s.** Phase 82 introduced AIMD-discovered parallel cloud concurrency (~10x), invalidating the F-59 era's "sequential cloud" sizing assumption. A legitimate 160-group full rebuild legitimately needs ~1170-1750s but was cut off at 900s with 99 of 160 workers cancelled.

### Seven fixes, defense-in-depth top to bottom

| # | File | Change |
|---|---|---|
| 1 | `src/prep/services/pipeline_checkpoint.py` | Added `trace_group_reasoning.jsonl` + `group_reasoning_manifest.json` to `TRACE_FILES`. Added `group_reasoning` entry to `STAGE_OUTPUTS`. Fixed wrong manifest filename in `_GOLDEN_FILES` (was `trace_group_reasoning_manifest.json`, actual writer uses `group_reasoning_manifest.json`). Added `atlas_routing_embeddings.npy` to `_GOLDEN_FILES`. |
| 2 | `src/prep/services/pipeline/orchestrator.py` | `_attempt_write_guard_recovery` now re-snapshots data files and re-runs `should_block_stage_completion` after `restore_checkpoint`. Phantom restores (where the shrunken file is not in the restore set) are detected and return `False` instead of silently advancing. |
| 3 | `src/prep/core/swarm_orchestrator.py` + 3 callers | New `compute_swarm_wall_budget(n_items, concurrency, is_cloud)` scales fan-out wall cap with workload. `group_reasoning.py:579`, `cluster.py:1583`, `atlas/generator.py:976` all use the helper. `DEFAULT_MAX_WALL_TIME_S` bumped 900s → 1800s. |
| 4 | `src/prep/services/pipeline/orchestrator.py` | New `_journal_run_failed` helper. `_WriteGuardBlocked` handler now records `status='failed'` (via `journal.stage_failed`) instead of `status='completed'`, and explicitly does NOT promote a golden checkpoint from the corrupted state. |
| 5 | `src/prep/core/group_reasoning.py`, `cluster.py`, `atlas/generator.py` | Engine raises `RuntimeError` if `len(swarm.worker_results) < len(items)` — partial completion no longer overwrites the cache. Atlas's variant falls through to its sequential path (which is cheap and produces a complete result). |
| 6 | `src/prep/services/pipeline_integrity.py` + orchestrator | `should_block_stage_completion` accepts `allowed_shrink_ratio` kwarg. Orchestrator computes it from `Changeset.deleted` via new `_compute_allowed_shrink_ratio`. Formula: `deletion_ratio * 1.5 + 0.10`, clamped to 0.95. A user deleting 30% of files no longer trips MAJOR_SHRINK. |
| 7 | n/a | `concept_seeder.py` verified safe (DB-backed append-only with existing fallback path — Phase 136 Part 09 documented behavior). No conversion needed. |

### Tests added (+43, all passing)

- `tests/test_checkpoint_stages.py` (+3 tests): coverage parity guards — `TRACE_FILES` / `_GOLDEN_FILES` / `STAGE_OUTPUTS` consistency.
- `tests/test_write_guard.py` (+2 tests): phantom-restore detection + real-restore success.
- `tests/test_write_guard_journal.py` (NEW, 4 tests): failed-not-completed journal writes on `_WriteGuardBlocked`.
- `tests/test_swarm_wall_budget.py` (NEW, 8 tests): workload-scaled budget formula.
- `tests/test_partial_swarm_refused.py` (NEW, 6 tests): engine refuses to write truncated swarm output.
- `tests/test_changeset_aware_integrity.py` (NEW, 12 tests): deletion-proportional shrinkage tolerance.

### Verified runtime behavior (2026-05-28 full rebuild)

After user-triggered full rebuild on a daemon running the new code:

- ✅ **All 15 stages completed** end-to-end. `fast_sync`, `deep_enrichment`, `finalize` all show `phase=completed` with every stage `completed` (no skips).
- ✅ **Group reasoning ran fully** (not skipped). Barrier was active; all groups were re-analyzed; 506/506 workers completed in clustering's swarm at ~185s elapsed; zero partial-completion.
- ✅ **Fix #6 allowance text rendered correctly in the live log:** `"Write guard: RESTORED 12 files from checkpoint for stage clustering... (blocked: Stage clustering would shrink trace_modules.jsonl from 1007 to 768 records (76% of original) (allowed up to 11% shrinkage given workload deletions))"`. The new tolerance string from `pipeline_integrity.py:312` is in production.
- ✅ **Fix #2 recovery verification fired silently** — clustering's 1007→768 shrink (24%) exceeded the 11% deletion-aware allowance, triggered restore, restore succeeded, stage advanced. Cache integrity preserved.

### Observations saved to `prep_observe`

- `7760f49b71b2` — `TRACE_FILES` / `_GOLDEN_FILES` asymmetry bug (anchored to `pipeline_checkpoint.py:51`)
- `6d64c230c479` — phantom-restore acceptance bug (anchored to `orchestrator.py:4002`)
- `c61baefe20c1` — swarm wall-time cap obsolete sizing (anchored to `swarm_orchestrator.py:146`)
- `d13c97214d0e` — journal-status-on-block bug (anchored to `orchestrator.py`)
- `ae874670e8a1` — UI renders `skipped` as running spinner (anchored to `pipelineRollup.ts`, separate from Phase 141 — see notes)

### Cross-lane impact

- **Touches Lane B's `orchestrator.py` shared file.** Phase 141 edits live in `_attempt_write_guard_recovery`, `_journal_run_failed`, `_compute_allowed_shrink_ratio` — none of these overlap with Lane B's synthesizer wall-time accounting (Part 09) region. Conflict rule §2 honored.
- **Touches Lane C's shared `atlas/generator.py`.** Phase 141 edits live in the SwarmOrchestrator construction site (line ~976) and the swarm-result handling at line ~408 — same region Lane C identified for F2 LLM-direct-site refactor. Lane C should diff Phase 141's commit before applying F2 patches; the change is minimal (one helper call swap + a fall-through gate).
- **Does NOT touch Lane B's atlas `is_stale()` / `_load_consumed_changeset_run_id` (lines 1485-2160).** Per Conflict rule §1.

### Out of Phase 141 scope (intentionally deferred)

- **Reset-barrier semantic gap** — `write_reset_barrier(scope="all")` sets the in-memory "treat-cache-as-empty" flag but does not wipe the affected stage output files. With Fix #5 in place this is functionally harmless (partial completion now fails the stage instead of truncating), but the semantic gap remains. If a future stage is added without the Fix #5 guard, this could re-bite. Worth a docstring on `write_reset_barrier` and a follow-up "consider scope-aware file wipe" task.
- **`concept_seeder.py` wall budget migration to helper** — verified safe (different architecture); deferred unless evidence of failure surfaces.
- **Dashboard "skipped" rendering bug** — observation `ae874670e8a1` saved; lives in `packages/ui/src/components/trace/pipelineRollup.ts`; not in Phase 141 scope (backend only) nor in any current lane.

## Lane C completion record (2026-05-26 → 2026-05-28)

**Branch:** `phase-127-129-hygiene` on `.claude/worktrees/phase-127-129-hygiene/`. **8 commits, branched from `7e8967df`. Not pushed** per `feedback_explicit_push_only.md`.

```
671cb2ef  refactor(phase127 F6): collapse _hold_paused wrappers into HoldAwareMixin
a50978f3  feat(phase129): clear pipeline-orchestration cluster + close all 6 recipes
7477f3de  feat(phase127 F2): guard 14 LLM-direct sites with soft-hold check
8d19c308  test(phase127 F3): broaden AST guard to catch attribute-form constructor
0955a8fb  feat(phase129): high-visibility logger leak rewrite + regression test
5dcc0f22  test(phase127 F5): DeepeningLoop end-to-end pause-on-hold
fc3d8124  feat(phase127 F1): periodic stale-hold sweep with backing-state guard
267b2e3f  fix(phase127 F3): plumb project_id through trace_routes constructors
```

### Closed scope items

- **P127-F1 — Anti-stale soft-hold TTL sweep.** New `PipelineScheduler.sweep_stale_holds(grace_s=300.0)` in `services/pipeline/scheduler.py`. Backing-state predicate `_hold_has_backing_state` keeps the orphan rule in one place: `reason="exclusive"` requires `_priority_projects[set_by] == "exclusive"`; `reason="swarm"` requires `_swarm_window` owned by `set_by`; `reason="manual"` never auto-cleared. Age guard (`drain_timeout + grace`) is the safety net against racing with the natural clear path. Wired into the existing 30s drain-timer callback in `orchestrator.py:_start_drain_timer`. **Known limitation:** the drain timer only fires during swarm windows, so orphan holds created in idle periods get cleaned at the next swarm-window opening; documented in commit body.
- **P127-F2 — 14 LLM-direct sites guarded.** Per-call `if hold_paused_for_llm(...): raise_hold_paused_for_llm(...)` plus `except HoldPausedError: raise` carve-outs before existing `except Exception`. Sites covered: `cluster.py` (5: synthesize_cluster._generate_with_limit, synthesize_cluster_with_angle x3, _synthesize_batched._call_batch); `atlas/generator.py` (4: generate, _generate_root_atlas, _generate_segment_atlas, _generate_segment_atlas_with_angle); `group_reasoning.py` (2: analyze_group, analyze_group_with_angle); `concept_seeder.py` (3: _seed_concepts_sequential._call_worker, seed_concepts_swarm.worker_fn, _call_llm_for_concepts). **`CodebaseAtlas.__init__` now accepts `project_id` (defaulted to None for back-compat)** and threads it into the atlas `_run_swarm` dispatch (replacing the previous explicit `project_id=None`). Two callers updated: `services/pipeline/workers/__init__.py` atlas_worker, `services/pipeline/post_flight.py` preliminary-atlas. Carve-outs also added at the two `as_completed` catches in `cluster.py` that submit `synthesize_cluster` / `_call_batch` to `llm_pool`.
- **P127-F3 — `project_id` plumbed through `trace_routes/enrichment.py`.** Confirmed the literal `project_id=None` was already gone; the bug shifted to *omitting* the kwarg so it defaulted to `None`. Three constructors at `enrichment.py:97 / 442 / 676` now pass the path-param `project_id` through to `TraceAugmenter` / `EpistemicEnricher`. `services/headless_runner.py` deliberately keeps `project_id=""` since headless mode is single-project and never enters the multi-project priority queue.
- **P127-F4 — AtlasGenerator `project_id=None`.** ✅ already-shipped (`9c817649`, x'd in MASTER_TODO). Verified.
- **P127-F5 — DeepeningLoop hold integration test.** End-to-end coverage for both the sequential and threaded branches of `deepening.py`. `_FakePausingEnricher` raises `HoldPausedError` on the Nth `enrich_node` call; the test asserts (a) `loop.run()` returns a `DeepeningResult` without raising, (b) `result.iterations == 1` (paused mid-iteration-1), (c) `_write_epistemic` was called with the partial work, (d) the `deepening_complete` progress beacon did NOT fire on the paused run. Forces sequential vs threaded execution via a monkeypatch on `_get_llm_concurrency`.
- **P127-F6 — `HoldAwareMixin` consolidation.** New mixin in `services/pipeline/holds.py` exposes `_hold_paused` / `_raise_hold_paused`. `EpistemicEnricher`, `TraceAugmenter`, `SwarmOrchestrator` all inherit it; `SwarmOrchestrator` overrides `_hold_llm_for_check` to gate against `self.worker_llm`. Net: ~70 LoC removed, no behavior change, all 17 internal call sites unchanged because the mixin provides identical method names.
- **Phase 129 DevLeak audit — all 6 recipes closed.** 55 logger sites rewritten to drop dev nomenclature across 11 modules: `server.py`, `core/watcher.py`, `core/embedder.py`, `core/system_concept_seeder.py`, `mcp/server.py`, `services/pipeline/orchestrator.py`, `services/pipeline/recovery.py`, `services/pipeline/resume.py`, `services/pipeline/post_flight.py`, `services/pipeline_metadata.py`, `core/trace/builder.py`. Regression guard `tests/test_phase129_dev_leak_regression.py` AST-scans `logger.*` positional string literals for `Phase N` / `F-NN` prefixes — `CLEAN_MODULES` list is the source of truth for what has shipped, grows monotonically. README updated with per-cluster landing notes + recipe verdicts. Module / function docstrings still mention phase numbers per the README's "NOT a leak" rule.

### Tests added (+27 new tests, 5 new test files)

- `tests/test_trace_routes_pass_project_id.py` (+1 AST contract). F3 invariant pinned via AST inspection of every `TraceAugmenter` / `EpistemicEnricher` construction in `trace_routes/enrichment.py`. Test was hardened post-ship to match attribute-form calls (`core.TraceAugmenter(...)`) as well as bare-Name calls so a future qualified-import refactor doesn't silently bypass the guard.
- `tests/test_stale_hold_sweep.py` (+8 sweep tests). Covers orphan-clear (exclusive, swarm), backed-preserve (active priority / swarm window), grace-period respect, manual-hold immunity, and custom-grace override.
- `tests/test_deepening_hold_pause_integration.py` (+3 tests). Sequential pause mid-batch, iteration-beacon firing on immediate pause, threaded-branch pause cleanup.
- `tests/test_llm_direct_sites_hold_guarded.py` (+14 parametrized AST contracts). One test per F2 site asserts (a) hold-check call appears before the `llm.generate` within the enclosing function, (b) any `try` with `except Exception` around the call also has `except HoldPausedError: raise` before it. Line numbers in `F2_SITES` ride with the source.
- `tests/test_phase129_dev_leak_regression.py` (+11 parametrized AST contracts, one per `CLEAN_MODULES` entry). Asserts no `logger.*` positional string literal starts with `Phase N` / `Phase NNX` / `F-NN`.
- `tests/test_cluster_parallel_batched.py` (+1 fixture line). `synth.project_id = None` added to `_make_synthesizer_with_batch_profile` because the test bypasses `__init__` via `__new__`; F2 now reads `self.project_id` per dispatch.

### Cross-lane impact (READ BEFORE MERGING)

- **`src/prep/core/atlas/generator.py` — overlaps Phase 141.** Phase 141 inserted `compute_swarm_wall_budget(...)` at `atlas/generator.py:976`. Lane C's F2 work added `project_id` to `__init__` (around line 128, far from Phase 141) and changed `project_id=None` → `project_id=self.project_id or None` at the same swarm-construction site (now `~982` after Phase 141 reshuffled it). When merging Lane C to main, both edits land — they're semantically compatible (different concerns: wall budget vs. hold project_id), but a textual merge will need attention at the swarm-construction kwargs. Lane C's other atlas edits at lines 256 / 579 / 728 / 889 are inside different method bodies and won't conflict.
- **`src/prep/core/atlas/generator.py` — does NOT touch Lane B's `is_stale()` / `_load_consumed_changeset_run_id` region (lines 1485-2160).** Per conflict rule §1.
- **`src/prep/services/pipeline/orchestrator.py` — overlaps Lane B + Phase 141.** Lane C's F1 work added an 8-line stale-hold sweep call inside the existing `_start_drain_timer._check` callback (around line 117). Lane C's P129 work also rewrote 22 logger call-strings throughout the file (pure string content, args/level/exc_info unchanged). Phase 141 owns `_attempt_write_guard_recovery`, `_journal_run_failed`, `_compute_allowed_shrink_ratio`. Lane B owns synthesizer wall-time accounting (Part 09). None of these regions overlap each other line-for-line, but a 3-way merge across Lane B / Lane C / Phase 141 will benefit from doing the Phase 129 string rewrites *last* so they re-anchor against the merged file.
- **`src/prep/core/trace/builder.py` — formally in Lane B's exclusive scope.** Lane C touched it for 2 sites in the Phase 129 sweep (Phase 133 string rewrites at line 521 / 531). Pure string-content rewrite, no logic change. If Lane B's `prep_impact` bimodal-node implementation lands in this file in the same region, the merge is a simple textual swap — Lane B's logic edits win, then re-apply the Phase 129 rewrite to whatever string survives. Worth flagging to Lane B before reconcile.
- **Touches `services/pipeline/{recovery,resume,post_flight}.py` + `services/pipeline_metadata.py` for Phase 129.** Neither in Lane A's nor Lane B's exclusive scope; pure string rewrites only.

### Verified runtime behaviour

Test-suite-only verification — Lane C did not restart the daemon per coordination rule #5. End-to-end live regression remains the user's responsibility (per top-of-doc "Decisions locked" #2).

- ✅ `tests/test_trace_routes_pass_project_id.py` — 1/1
- ✅ `tests/test_stale_hold_sweep.py` — 8/8
- ✅ `tests/test_soft_hold_primitive.py` — 21/21 (all existing tests still green after F6 mixin refactor)
- ✅ `tests/test_deepening_hold_pause_integration.py` — 3/3
- ✅ `tests/test_llm_direct_sites_hold_guarded.py` — 14/14
- ✅ `tests/test_phase129_dev_leak_regression.py` — 11/11
- ✅ `tests/test_augmenter.py`, `tests/test_epistemic_enrichment.py`, `tests/test_deepening.py`, `tests/test_cluster_parallel_batched.py` — all green post-F2 / F6
- 6 pre-existing failures in `test_concept_seeder_swarm.py`, `test_pipeline_budget.py`, `test_pipeline_stage_endpoint.py`, `test_pipeline_status_epistemic_counts.py`, `test_pipeline_scheduler.py` confirmed pre-existing on `main` — NOT introduced by Lane C.

### Unified-testing recipe (when Lane B closes and we merge all three)

After Lane B merges to main, run from the merged main worktree:

```
.venv/bin/pytest \
  tests/test_trace_routes_pass_project_id.py \
  tests/test_stale_hold_sweep.py \
  tests/test_soft_hold_primitive.py \
  tests/test_deepening_hold_pause_integration.py \
  tests/test_llm_direct_sites_hold_guarded.py \
  tests/test_phase129_dev_leak_regression.py \
  tests/test_augmenter.py \
  tests/test_epistemic_enrichment.py \
  tests/test_deepening.py \
  tests/test_cluster_parallel_batched.py \
  -v
```

Expected: 120 pass, 0 fail (modulo the documented pre-existing failures above). If `test_llm_direct_sites_hold_guarded.py` fails after merge with "expected an `llm.generate` call at this line", it means the F2 catalog line numbers drifted — re-grep `self\.llm\.generate\|^\s*llm\.generate\(` in the 4 F2 files and update `F2_SITES` in the test.

### Out of Lane C scope (intentionally deferred)

- **Run-loop boundary handling for ClusterSynthesizer / GroupReasoningEngine / CodebaseAtlas.** F2 makes HoldPausedError propagate from the 14 LLM sites; it does not (yet) add a top-level `except HoldPausedError` in each `run()` to convert the pause into a paused-stats result (the way `EpistemicEnricher.run()` and `DeepeningLoop.run()` do). Today HoldPausedError bubbles up to the pipeline orchestrator's stage-level exception handler and the stage retries cleanly on the next run. Cleaner paused-stats semantics is a follow-up.
- **F1 always-on sweep.** Sweep currently only fires from the drain timer (active during swarm windows). Orphan holds outside swarm windows get cleaned on the next swarm-window opening — practical exposure bounded by normal deep-enrichment cadence. Adding a dedicated always-on timer was considered and skipped per caution.

## Decisions locked

- **Phase 138 section name:** `How It Works` (was `/concepts/` — rename to disambiguate from the `prep_concepts` MCP feature).
- **Phase 133 / 134 / 135 live regression:** the user is running this manually after rerunning the SourcePrep daemon on this repo. **No AI lane covers it.**
- **Phase 135.5 (FinishConsolidation):** parked from parallel lanes — its done-criteria conflict with Phase 136 Part 11 and with Lane C's atlas/generator.py edits. Pick up after Lane B closes.

## Corrections from code-verification (against MASTER_TODO claims)

Verified 2026-05-26 via direct grep + `git log`. The earlier audit had stale line numbers and at least one already-shipped item still listed as open.

| Claim in MASTER_TODO | Actual state | Note |
|---|---|---|
| P136 Part 11 (atlas `is_stale()` doesn't compare `run_id`) | **SHIPPED** | `core/atlas/generator.py:1511-1555` implements `_load_consumed_changeset_run_id` + run_id compare. Commit `96882585`. Remove from open list. |
| P136 Part 10 (spaghetti scorer zero-score) | **IN PROGRESS** | Commits `a595d9c2`, `a8d4c02f` landed file-node schema fallback. Not silent regression — actively patched. Lane B still owns final verification. |
| P136 Part 02 (`prep_impact` bimodal node) | **OPEN (strategy only)** | Commit `96882585` adds Part 02 *strategy* doc; no impl. Lane B owns. |
| P127-F2 LLM-direct sites — line numbers | **STALE** | Re-grepped: `cluster.py` 1294/1429/1460/1494/1819 · `atlas/generator.py` 244/563/708/865 · `group_reasoning.py` 477/762 · `concept_seeder.py` 210/794/1252 (uses `llm.generate`, not `self.llm.generate`). 14 sites, not 11. |
| P127-F3 (`project_id=None` in headless/trace) | **NEEDS RE-INVESTIGATION** | Literal pattern returned 0 hits in `headless_runner.py` and `api/routers/trace_routes/`. Either silently closed or the bug shifted. Lane C must reproduce before claiming open. |
| P127-F4 (AtlasGenerator `project_id=None`) | **CLOSED** | Commit `9c817649` verified in `git log`. Already x'd in MASTER_TODO. |
| Phase 135.5 — "scaffolded only" | **PARTIALLY SHIPPED** | `core/walker.py` exists (135 LoC, 7 callers). But done-criteria not met: `grep -rl "import prep_engine" src/prep/` returns **6 files** (target: 1); `trace_inferred_hashes` still present in 4 files (target: 0). |
| Phase 139 README status checkboxes | **DOC ROT** | `README.md:39-42` shows `[ ] Implementation` and `[ ] Validation + RESULTS.md` despite PR1+PR2 shipped and `RESULTS.md` existing. Cosmetic only. |
| Phase 128 Task 3 (sync_downstream_mtimes source) | **HALF DONE** | `orchestrator.py:217` uses `STRUCTURAL` (good); `orchestrator.py:313` still uses `CATALOGUE`. Both lines need same fix or one is intentional — Phase 128 author must clarify. |

## Lane A — Docs frontier (this session)

**Owner:** Claude in current session.
**Repo:** main worktree (`/Volumes/4TB-BAD/HumanAI/CoDRAG`).

### Tasks

1. **Phase 138 — Concepts → How It Works rename.**
   - Move `websites/apps/docs/src/app/concepts/{code-graph,context,graph-enrichment,indexing}` → `websites/apps/docs/src/app/how-it-works/...`
   - Move 4 explainer guides into the renamed section: `embeddings`, `compression`, `smart-search`, `dynamic-model-loading` from `websites/apps/docs/src/app/guides/` → `websites/apps/docs/src/app/how-it-works/`.
   - Migrate the 4 moved pages to `ConceptPageShell` layout.
   - Sweep all internal links — `git grep "/concepts/" websites/apps/docs/` must return 0 after rename.
   - Update sidebar/sitemap config.
2. **Phase 137 P137-T1.** Confirm the netlify env-var (`NEXT_PUBLIC_STORYBOOK_URL`) is staged in `websites/apps/docs/netlify.toml` and ready to push when user signals.
3. **Phase 137 P137-A1 / A2 / A3 page audit.** Walk the 24 docs pages, populate `docs/Phase137_DocsLiveAssetIntegration/03_page_audit.md` and `04_placement_matrix.md`.
4. **(stretch) Phase 131 §5.1.** Storybook env-gate `autodocs: false` for public build + story-glob exclusions.

### File scope (exclusive — Lane B and Lane C MUST NOT touch)

```
websites/apps/docs/**
packages/ui/src/stories/**
packages/ui/.storybook/**
docs/Phase137_DocsLiveAssetIntegration/**
docs/Phase138_DocsConceptsRename/**
docs/Phase131_StorybookCuration/**
```

### Stop conditions

- All `/concepts/` URL refs resolved to `/how-it-works/`.
- Docs site builds (`cd websites/apps/docs && npm run build`) — zero broken links.
- Phase 137 page audit table populated for all 24 pages with a verdict per page.
- Hand off to user for prod push (per `feedback_explicit_push_only.md`).

---

## Lane B — Python correctness regressions (Phase 136 active)

**Owner:** parallel AI session #1.
**Repo:** `git worktree add ../CoDRAG-lane-B -b phase-136-correctness`.

### Tasks

1. **Phase 136 Part 02 — `prep_impact` bimodal-node twins.**
   - Read strategy doc: `docs/Phase136_Dogfood-fixes/Part02_PrepImpactBimodalNode/IMPLEMENTATION_STRATEGY.md`.
   - Implement: `src/prep/mcp/server.py` (`tool_impact` handler, ~line 4280) must aggregate dependents across file ↔ external_module node pair.
   - Underlying fix likely in `src/prep/core/trace/index.py`.
   - Add fixture-based test that reproduces P122-D1 (3-file project, `from pkg.x import y`, assert dependent_count = 1, not 0).
2. **Phase 136 Part 09 — Synthesizer wall-time regression.**
   - Read: `docs/Phase136_Dogfood-fixes/Part09_SynthesizerWallTimeRegression/`.
   - Symptom: synthesis fails at ~914s despite 1500s budget; 1795 fallback concepts emitted, 1334 questions lost.
   - Likely culprits: worker pool exhausts budget pre-synthesis, or budget accounting includes T4 enrichment.
   - Fix in `src/prep/services/pipeline/orchestrator.py` and/or `concept_seeder.py`.
3. **Phase 136 Part 10 — Spaghetti scorer verification.**
   - Two patches landed (`a595d9c2`, `a8d4c02f`). Verify the regression is closed by running a full audit on this repo after Lane A's daemon restart.
   - If 657-files-scored baseline is restored, mark Part 10 SHIPPED; otherwise diagnose remaining gap.
4. **Phase 136 Part 04 — Search intent classifier.**
   - Symptom: `prep_search` `LOCATE` queries miss multi-token symbol names. Commit `9c80a83a` added auto-fallback to `EXPLAIN`. Verify and add tests.

### File scope (exclusive — Lane A and Lane C MUST NOT touch)

```
src/prep/mcp/server.py
src/prep/mcp_tools.py
src/prep/core/trace/index.py
src/prep/core/trace/builder.py
src/prep/core/audit/spaghetti_scorer.py
src/prep/core/audit/__init__.py
src/prep/services/pipeline/orchestrator.py   ← SHARED with Lane C; see rule below
docs/Phase136_Dogfood-fixes/Part02*/**
docs/Phase136_Dogfood-fixes/Part04*/**
docs/Phase136_Dogfood-fixes/Part09*/**
docs/Phase136_Dogfood-fixes/Part10*/**
tests/test_prep_impact*.py
tests/test_spaghetti_scorer*.py
tests/test_synthesizer*.py
tests/test_search_intent*.py
```

### Stop conditions

- Part 02: dependent_count fixture test passes; live `prep_impact` on `src/prep/core/__init__.py` returns >100 dependents.
- Part 09: synthesizer completes inside 1500s budget on this repo's rebuild; questions count > 0.
- Part 10: spaghetti scorer returns non-zero file count on a clean rebuild.
- Part 04: LOCATE→EXPLAIN fallback has a unit test.
- All four parts' status table in `docs/Phase136_Dogfood-fixes/00_Status_2026-05-17.md` updated.

---

## Lane C — Python reliability hygiene (Phase 127 + 129)

**Owner:** parallel AI session #2.
**Repo:** `git worktree add ../CoDRAG-lane-C -b phase-127-129-hygiene`.

### Tasks

1. **Phase 127 F1 — Anti-stale soft-hold TTL cleanup.**
   - Spec: `MASTER_TODO.md:1765`. `check_drain_timeouts()` reports timed-out PIDs but doesn't clear their holds.
   - Add periodic sweep (drain_timeout + grace) that clears stale holds + emits warning log.
   - Files: `src/prep/services/pipeline/scheduler.py`, `holds.py`.
2. **Phase 127 F2 — LLM-direct sites bypass soft-holds.**
   - Updated line list (verified 2026-05-26): `cluster.py:1294,1429,1460,1494,1819` · `atlas/generator.py:244,563,708,865` · `group_reasoning.py:477,762` · `concept_seeder.py:210,794,1252`.
   - 14 sites total. Wrap each in `_hold_paused()` or factor a shared `LLMDispatcher`.
3. **Phase 127 F3 — RE-INVESTIGATE before fixing.**
   - The literal `project_id=None` pattern is gone from `headless_runner.py` and `api/routers/trace_routes/`. Either silently closed (mark x) or shifted to a different shape. Reproduce on a 2-project setup before writing code.
4. **Phase 127 F5 — DeepeningLoop hold integration test.**
   - Mock `enrich_node` to raise `HoldPausedError` mid-batch; assert `loop.run()` returns paused-aware `DeepeningResult` with partial iterations + paused checkpoint persisted. No exception bubbles.
5. **Phase 129 DevLeak audit — drive 6 recipes to zero.**
   - Recipes: phase numbers in non-comment literals · commit-message narration in payloads · F-NN bug IDs in user-visible strings · AGENTS.md / `rules_generator` content · LLM-bound prompts · telemetry `remediation`/`message` fields.
   - Scope: `src/prep/` only. Comments and docstrings excluded.
6. **(stretch) Phase 127 F6** — collapse per-class `_hold_paused` wrappers into shared helper in `holds.py`. Pure DRY.

### File scope (exclusive — Lane A and Lane B MUST NOT touch)

```
src/prep/services/pipeline/scheduler.py
src/prep/services/pipeline/holds.py
src/prep/services/pipeline/swarm_orchestrator.py
src/prep/services/pipeline/recovery.py
src/prep/services/pipeline/manifest_store.py
src/prep/core/cluster.py
src/prep/core/concept_seeder.py
src/prep/core/group_reasoning.py
src/prep/core/epistemic_enrichment.py
src/prep/core/augmenter.py
src/prep/core/rules_generator.py
src/prep/core/atlas/generator.py              ← SHARED with Lane B; see rule below
src/prep/headless_runner.py
src/prep/api/routers/trace_routes/**
src/prep/api/routers/llm.py
docs/Phase127_MultiProjectQueueArchitecture/**
docs/Phase129_DevLeakAudit/**
tests/test_holds*.py
tests/test_scheduler*.py
tests/test_dev_leak*.py
```

### Stop conditions

- F1: stale-hold sweep test passes; manual restart scenario clears hold within (drain_timeout + grace).
- F2: all 14 LLM-direct sites guarded; integration test demonstrates pause works for direct-dispatch path.
- F3: either marked closed with reproduction evidence, or fixed + tested.
- F5: integration test green.
- Phase 129: `python tools/dev_leak_recipes.py` (or equivalent grep harness) returns zero hits across all 6 recipes.

---

## Conflict rules (READ BEFORE EDITING)

1. **`src/prep/core/atlas/generator.py` is shared between Lane B and Lane C.**
   - Lane B owns `is_stale()`, `_load_consumed_changeset_run_id`, `_save()`, and changeset stamping (~lines 1485-2160). **Do not touch elsewhere.**
   - Lane C owns the LLM dispatch sites at lines 244, 563, 708, 865 only. **Do not touch the staleness code.**
   - If you need to touch a third region, post in the coordination thread first.

2. **`src/prep/services/pipeline/orchestrator.py` is shared between Lane B and Lane C.**
   - Lane B owns synthesizer wall-time accounting (Part 09).
   - Lane C owns soft-hold call sites (F1).
   - These regions are physically separated; if they collide, Lane B has priority (regression > polish).

3. **`MASTER_TODO.md` is append-only during parallel work.** No lane edits existing rows. After all three lanes stop, the lane owners reconcile in one PR.

4. **No rebases on each other's branches.** Each lane lives on its own branch and merges into `main` via PR.

5. **No daemon restarts.** The user owns the daemon for live regression on Phase 133/134/135. If you need to test against a live daemon, ask first.

## Mid-stream sync points

- **First check-in:** after each lane's first task is implemented + tested. Post a one-line status in chat.
- **Conflict escalation:** if any lane needs to touch a file outside its scope, stop and post in chat before editing.
- **Branch state on stop:** push the branch with a `WIP` commit if you stop mid-task so the user can review.

## Out of scope (intentionally not assigned)

- Phase 125 T5-T10 — needs design alignment with user (settings_store schema, MCP trailer wording).
- Phase 125b live verification — depends on full rebuild.
- Phase 126 — gated on Phase 125 acceptance proof.
- Phase 132 P132-CI — three CI fidelity tests; can be next round.
- Phase 132 P132-A2 — fresh-install batch, ship-readiness window.
- Phase 130 `/guides/model-advisor` — needs live vendor pricing research.
- Phase 135.5 cleanup — invariants not met (6 prep_engine imports remain, 4 trace_inferred_hashes refs), but waiting on Lane B Part 11 atlas work to land first.
- Phase 140 — continuous, user drives.
- P82-F1 through F8 — MCP runtime observability, defer.
- P122-T-treatment_registry / swarm_optimizer / budget_enforcement — built-but-unwired triage, defer.

## Unified testing checklist (run when all three lanes have wrapped)

> Each lane self-verifies its own work in its own commits. This section is the **cross-lane smoke** to run once Lane B and Lane C land — it covers the conflict-prone surfaces (`atlas/generator.py`, `orchestrator.py`) and the runtime integrations that no single lane can verify alone.

### Static checks (fast, no daemon needed)

- [ ] `cd websites/apps/docs && npx next build` — green. Lane A baseline.
- [ ] `cd websites/apps/marketing && npx next build` — green. Lane A baseline.
- [ ] `cd packages/ui && npx tsc --noEmit` — green. Lane A + Lane B + Lane C all touch `@prep/ui` transitively.
- [ ] `.venv/bin/pytest tests/test_atlas_swarm.py tests/test_atlas.py tests/test_atlas_stale_after_consume.py -v` — green. Confirms atlas swarm fix did not regress existing swarm tests + Phase 136 Part 11 invariants still hold.
- [ ] `.venv/bin/pytest tests/test_holds.py tests/test_scheduler.py tests/test_dev_leak*.py -v` — green. Lane C smoke (P127-F1/F2/F5 + Phase 129 sweep).
- [ ] `.venv/bin/pytest tests/test_prep_impact*.py tests/test_spaghetti_scorer*.py tests/test_synthesizer*.py tests/test_search_intent*.py -v` — green. Lane B smoke (Phase 136 Parts 02/04/09/10).
- [ ] `cd packages/ui && STORYBOOK_PUBLIC=true npx storybook build -o /tmp/sb-smoke` — green. Lane A Phase 131 §5.2 verification.
- [ ] `.venv/bin/pytest tests/test_checkpoint_stages.py tests/test_write_guard.py tests/test_write_guard_journal.py tests/test_swarm_wall_budget.py tests/test_partial_swarm_refused.py tests/test_changeset_aware_integrity.py -v` — 43/43 green. Phase 141 cross-lane smoke (silent-shrink prevention).
- [ ] `.venv/bin/python -c "from prep.services.pipeline_checkpoint import TRACE_FILES, STAGE_OUTPUTS, _GOLDEN_FILES; assert 'trace_group_reasoning.jsonl' in TRACE_FILES; assert 'group_reasoning' in STAGE_OUTPUTS; assert 'group_reasoning_manifest.json' in _GOLDEN_FILES"` — Phase 141 coverage parity invariant.

### Daemon-attached checks (need `prep serve` running)

Run after Lane B/C land **and** the daemon has been restarted **and** a full pipeline rebuild has completed end-to-end on the SourcePrep project.

- [ ] **Atlas swarm persistence** — `ls -la .sourceprep/atlas.json` shows mtime within the last hour (atlas swarm fix). `python3 -c "import json; print(json.load(open('.sourceprep/atlas.json'))['consumed_changeset_run_id'])"` returns a non-empty run_id.
- [ ] **Dashboard atlas panel matches on-disk** — atlas timestamp in the UI matches `.sourceprep/atlas.json`'s `generated_at`, not the golden checkpoint.
- [ ] **`/pipeline/status` atlas.exists is true** — `curl -sS http://localhost:8400/projects/<id>/pipeline/status | jq '.data.stages.atlas.exists'` returns `true`.
- [ ] **`is_stale()` short-circuit fires** — call `prep` ambient context twice in a row with no intervening change; second call should return identical content with no atlas regeneration logged. (Phase 136 Part 11 invariant.)
- [ ] **Phase 127 F5 — DeepeningLoop hold integration** — fire a Pause mid-`deepening` and confirm checkpoint persists; resume and confirm completion. Lane C will land the unit test; this is the live cross-check.
- [ ] **Phase 136 Part 02 — `prep_impact` bimodal node** — `prep_impact src/prep/core/__init__.py` returns >100 dependents (was 0 pre-fix). Lane B owns.
- [ ] **Phase 136 Part 09 — Synthesizer wall-time** — concept seeding completes inside 1500s budget with non-zero questions count. Lane B owns.
- [ ] **Phase 136 Part 10 — Spaghetti scorer** — `prep_audit action=scan` returns >0 spaghetti findings on this repo (was 0 in the 2026-05-17 regression). Lane B owns.
- [ ] **Phase 141 — wall budget scales with workload** — trigger a full reset+rebuild; log shows `compute_swarm_wall_budget(...)` selected a budget > 900s for group_reasoning/clustering (look for `max_wall=` lines with ≥1500s). Failure mode: log shows `max_wall=900s` and a `[Swarm] Wall-time cap (900s) exceeded` warning.
- [ ] **Phase 141 — no MAJOR_SHRINK on clean full rebuild** — `grep -c "MAJOR_SHRINK" /tmp/prep_daemon_logs/daemon_*.log` returns 0 for the rebuild window. (Fix #6 may emit benign `(allowed up to N% shrinkage)` messages — those are by design and DO NOT count as shrink incidents.)
- [ ] **Phase 141 — partial-swarm-refused guard never fires on happy path** — `grep -c "INCOMPLETE: only" /tmp/prep_daemon_logs/daemon_*.log` returns 0. If non-zero, Fix #5 caught a wall-cap incident → diagnose whether budget needs further bump or LLM endpoint latency degraded.
- [ ] **Phase 141 — journal stage_results never has 'completed' for a shrunk stage** — `sqlite3 ~/.local/share/sourceprep/prep_pipeline_journal.db "SELECT run_id, status, stage_results FROM pipeline_runs WHERE error LIKE '%MAJOR_SHRINK%' OR error LIKE '%WRITE GUARD%'"` → any rows must have `status='failed'`, not `'completed'`. (Fix #4 invariant.)
- [ ] **Phase 141 — `_golden/` is never promoted from a shrunk state** — after a run with a logged MAJOR_SHRINK that didn't truly recover, `wc -l .sourceprep/.checkpoints/_golden/trace_group_reasoning.jsonl` must match the pre-shrink count, not the shrunk count.

### Conflict-prone surfaces (verify Lane B and Lane C did not collide)

- [ ] `git log --oneline main -- src/prep/core/atlas/generator.py` — review most recent 5 commits. Verify Lane B's `is_stale`/run_id work and Lane C's LLM-dispatch guards live in non-overlapping line ranges, per the **Conflict rules** section above.
- [ ] `git log --oneline main -- src/prep/services/pipeline/orchestrator.py` — same drill for Lane B synthesizer accounting vs Lane C soft-hold call sites.
- [ ] `git diff main~10 -- src/prep/core/atlas/generator.py | grep "consumed_changeset_run_id\|_save" | head -20` — confirm Lane B did not accidentally remove the Phase 136 Part 11 invariants.
- [ ] **Phase 141 ↔ Lane B/C surface check** — `git diff main~10 -- src/prep/core/atlas/generator.py | grep "compute_swarm_wall_budget\|swarm_complete"` should show Phase 141's edits at the SwarmOrchestrator construction site (~line 996 post-edit) and the swarm-result handling (~line 408 post-edit). These regions must not overlap with Lane B's `is_stale`/`_save` (lines 1485-2160) or Lane C's LLM-direct sites (244/563/708/865 pre-Phase-141, may have shifted by ±20 lines after Phase 141's edits — re-grep before applying Lane C F2 patches).
- [ ] `prep_audit action=antibodies` — confirm derived antibodies status mismatch (Phase 125 §13) is still in the fixed state (active concepts → active antibodies that fire).

### Push readiness

- [ ] `git status --short` — only intentional pending files remain.
- [ ] `git log --oneline main ^origin/main` — review every commit author and message; flag anything unexpected before `git push`.
- [ ] Confirm the 4 Netlify builds (docs / marketing / support / payments) all expected to succeed (run `npx next build` in each before push if uncertain).

### Stop conditions

- All static checks green, all daemon-attached checks green, all conflict-prone surfaces reviewed → ship.
- If any check fails: post the failing output in the coordination thread before patching. Don't "just fix it" — the failing check may be revealing a real cross-lane regression that needs a coordinated response.

## Provenance

This doc was generated 2026-05-26 by reading:
- `docs/MASTER_TODO.md` (lines 52-210, 1750-1977)
- All `docs/Phase125_*` through `docs/Phase140_*` README/status files
- Direct `git log` + `git grep` verification of every claim
- `docs/Phase136_Dogfood-fixes/00_Status_2026-05-17.md`

Lane A completion record and atlas swarm fix added 2026-05-28 after daemon restart surfaced the swarm-success persistence bug. Unified testing checklist added 2026-05-28 as a pre-merge gate for Lane B and Lane C wrap-ups.

Phase 141 completion record added 2026-05-28 after end-to-end validation. The 7-fix prevention pass was triggered by the 2026-05-26 silent-shrink incident (`trace_group_reasoning.jsonl` 166→61) and validated by the subsequent full rebuild that ran all 15 stages clean — including the Fix #6 deletion-aware allowance text rendering correctly in the live clustering write-guard recovery event.

## Lane B closeout (2026-05-28)

Lane B never needed its own branch — three of four parts had already shipped on `main` before the lane plan was written (the 5/26 audit missed commits `e16023c8`, `9c80a83a`, `a8d4c02f`, `a595d9c2`). Verified after the 2026-05-28 03:27 EDT overnight rebuild:

| Part | Status | Evidence |
|---|---|---|
| 02 prep_impact bimodal | ✅ shipped + verified | Commit `e16023c8` — Rust parser now recurses into nested imports. Live `GET /trace/impact/file:src/prep/core/augmenter.py` returns **14 Python dependents** including `deep_analysis.py` (indented-import case at lines 192/312). Baseline was 2. The original "bimodal-node twins" theory was falsified during implementation; the real bug was Rust-side indented-import dropping. |
| 04 search intent | ✅ shipped + verified | Commit `9c80a83a` — LOCATE→EXPLAIN auto-fallback in `mcp/server.py`. `pytest tests/test_prep_search_locate_fallback.py` 5/5. |
| 10 spaghetti scorer | ✅ shipped + verified | Commits `a8d4c02f` + `a595d9c2` — `size ← line_count × 40` fallback via shared `effective_file_size` helper in `prep.core.audit.models`. 2026-05-28 07:22 telemetry: `scored_count=406` (was 0 on 5/17). 39/39 tests across `test_spaghetti_scorer.py` + `test_audit_size_fallback.py`. |
| 09 synthesizer empty-output | ⚠️ **open** — handed off to next session | 2026-05-28 07:20 telemetry still emits `concepts_synthesis_failed` with `fallback_concepts=1754, fallback_questions=1295, worker_count=741`. Same fingerprint as 5/17 and 5/18. Wall-time is not the bug; synthesis returns empty/unparseable on the consolidation prompt. Phase 141 hardened adjacent swarm machinery but did not address this. |

**Phase 141 adjacency.** `compute_swarm_wall_budget(n_items, concurrency, is_cloud)` and the hardened `IntegrityGuard` are now available in `group_reasoning`, `cluster`, `atlas/generator`. Part 09's fix should lean on this rather than hard-code a new budget. Recommended work order for the Part 09 session:
1. Diagnostic logging at `concept_seeder.py:903` — capture raw LLM response on parse failure (length, finish_reason, first/last 500 chars). Land alone first.
2. Chunked synthesis (batches of ~200 workers, then synthesize-the-synthesis) to dodge the output-token cap on the consolidation prompt (~2 MB for 798 workers × +2.5K T4 enrichment).
3. Wire the 1754 fallback seed concepts into Phase 125c refinement as a distinct intake source so quality doesn't cliff when synthesis still fails.
4. Test: `tests/test_synthesis_fallback_preserves_questions.py` — force synthesis-empty, assert fallback questions individually retrievable.

**Product-feedback callouts surfaced during verification (dogfood):**
- Part 10's post-fix top hotspots are all `.md` files (`MASTER_TODO.md`, `ENTERPRISE_ADMIN_DESIGN.md`, `ROADMAP.md`, `ARCHITECTURE.md`). The `line_count × 40` heuristic overweights long markdown; pre-regression top-5 was `.py`/`.tsx`. Worth a calibration follow-up.
- `/trace/impact` HTTP response returns dependents with empty `edges` arrays. MCP rendering tags `[imports]`/`[references]` correctly; the HTTP layer drops the edge kind. Likely serialization gap in `src/prep/api/routers/trace_routes/query.py:get_trace_impact`.
