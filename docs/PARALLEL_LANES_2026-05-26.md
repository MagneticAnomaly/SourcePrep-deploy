# Parallel-Lane Coordination — 2026-05-26

Single source of truth for the multi-AI work split decided 2026-05-26. Supersedes ad-hoc audit summaries in chat; cross-links into `MASTER_TODO.md` for the canonical per-item history. When this doc and `MASTER_TODO.md` disagree, **this doc is newer** — it reflects code-state verified 2026-05-26 against MASTER_TODO claims that were typed weeks earlier.

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

## Provenance

This doc was generated 2026-05-26 by reading:
- `docs/MASTER_TODO.md` (lines 52-210, 1750-1977)
- All `docs/Phase125_*` through `docs/Phase140_*` README/status files
- Direct `git log` + `git grep` verification of every claim
- `docs/Phase136_Dogfood-fixes/00_Status_2026-05-17.md`
