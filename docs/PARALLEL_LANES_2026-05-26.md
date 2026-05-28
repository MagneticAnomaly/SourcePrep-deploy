# Parallel-Lane Coordination — 2026-05-26

Single source of truth for the multi-AI work split decided 2026-05-26. Supersedes ad-hoc audit summaries in chat; cross-links into `MASTER_TODO.md` for the canonical per-item history. When this doc and `MASTER_TODO.md` disagree, **this doc is newer** — it reflects code-state verified 2026-05-26 against MASTER_TODO claims that were typed weeks earlier.

## Lane status — 2026-05-28 (rolling)

> Updated as each lane lands. Newest at top.

| Lane | Owner | Status | Last update | Notes |
|---|---|---|---|---|
| **A — Docs frontier** | This session | ✅ **SHIPPED** | 2026-05-28 | See "Lane A completion record" below. |
| **B — Python correctness (Phase 136)** | Parallel AI #1 | ⏳ **wrapping up** | TBD | Lane B owner: fill this row with commit refs + verification when wrapping. |
| **C — Python reliability (Phase 127 + 129)** | Parallel AI #2 | ⏳ **wrapping up** | TBD | Lane C owner: fill this row with commit refs + verification when wrapping. |

### Atlas swarm-success persistence fix — 2026-05-28 (cross-lane)

While Lane A was verifying daemon health post-restart, a daemon-restart-triggered rebuild surfaced that `core/atlas/generator.py:generate_segmented()` had a Phase-79 regression: the swarm-success branch returned `(root_doc, swarm_docs)` without calling `self._save(root_doc)`, so the root `atlas.json` was never persisted on swarm-success runs. Sub-segments, routing, and the orchestrator-level `atlas_manifest.json` all wrote correctly — only the root was missing.

Cascade: dashboard atlas panel fell back to `.checkpoints/_golden/atlas.json` (showing stale data), `/pipeline/status` reported `atlas.exists: false`, and Phase 136 Part 11's `is_stale()` short-circuit never fired because `_load_consumed_changeset_run_id` reads from `atlas.json` which was missing.

One-line fix at `generator.py:443` plus regression test at `tests/test_atlas_swarm.py::test_swarm_success_writes_root_atlas_json`. Lives in the Phase 136 family but landed in Lane A's commit stream because Lane A's testing pass surfaced it.

## Lane A completion record (2026-05-26 → 2026-05-28)

**Branch:** `main`. **Shipped to `origin/main`** in nine commits:

```
4aed3c4d  fix(phase131): deep Phase NN sweep on publicly-shipping component surfaces
6c8a9109  fix(marketing): repoint immune-system docs links to /mcp (pre-existing broken)
f1001577  fix(phase131): strip Phase NN leaks + SiteFooter URL from public storybook
13e0bc4c  feat(phase137): commit live-asset implementation pass (29 placements)
beca8b55  fix(phase138): re-key cross-repo refs to /how-it-works/, mark phase done
2bb3a281  fix(docs): mark mcp/ides and mcp/terminal as client components
a66f075d  docs(coordination): add 3-lane parallel work plan for next batch
d66eed89  docs(phase138): rename /concepts/ -> /how-it-works/, move 4 explainer guides
(+ atlas swarm fix — to be committed alongside this doc update)
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

### Conflict-prone surfaces (verify Lane B and Lane C did not collide)

- [ ] `git log --oneline main -- src/prep/core/atlas/generator.py` — review most recent 5 commits. Verify Lane B's `is_stale`/run_id work and Lane C's LLM-dispatch guards live in non-overlapping line ranges, per the **Conflict rules** section above.
- [ ] `git log --oneline main -- src/prep/services/pipeline/orchestrator.py` — same drill for Lane B synthesizer accounting vs Lane C soft-hold call sites.
- [ ] `git diff main~10 -- src/prep/core/atlas/generator.py | grep "consumed_changeset_run_id\|_save" | head -20` — confirm Lane B did not accidentally remove the Phase 136 Part 11 invariants.
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
