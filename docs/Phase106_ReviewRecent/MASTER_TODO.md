# Phase 106: Master TODO — All Open Gaps (Phases 107–115)

> **Date:** 2026-04-17
> **Scope:** Consolidates every STILL-OPEN / PARTIAL / NEEDS-VERIFICATION / DEFERRED item from the reality-checked Phase 107–111 READMEs plus the newer Phase 112–115 work.
> **Method:** Three parallel Explore agents re-read the plan docs; this file dedupes, tiers by risk, and identifies cross-phase collisions.
> **Explicitly excluded:** The application rename (Phase 102 / Phase102_Prep_rename) — tracked as a separate self-contained workstream.

---

## How to read this

- **Tier 0 – BLOCKING** — must ship before any public/MVP release; security or data-correctness.
- **Tier 1 – HIGHEST-RISK / UNVALIDATED** — plumbing exists, but we have no evidence it works on real input.
- **Tier 2 – MVP-CRITICAL** — on the golden path; user-visible if broken.
- **Tier 3 – POLISH / FOLLOW-UP** — shipped core, remaining tasks are quality/UX/coverage.
- **Tier 4 – DEFERRED** — explicitly parked; recorded here so they are not lost.

Each item cites its source phase § so you can jump to the full context.

---

## Tier 0 — BLOCKING for MVP

### Security surface (Phase 111 §5.0 — NEW gap surfaced during reality check)

- [ ] Guard `/admin/*` endpoints (`api/routers/settings.py:599-755`) — audit-log, security-health, security-report, quarantine-project, block-endpoint, approve-config. Require `CODRAG_DEV_MODE` OR auth token.
- [ ] Guard `/api/llm/proxy/test-model` (`llm.py:1088`) — currently callable without auth.
- [ ] Make `CODRAG_DEV_MODE` startup-time-only. Remove the runtime write at `license.py:580`.
- [ ] Enumerate all `/admin/*`, `/dev/*`, `/debug/*` routes. Apply a consistent guard decorator + central allow-list. Add a ruff/pytest rule flagging any new unguarded admin route.

---

## Tier 1 — HIGHEST-RISK / UNVALIDATED

### Concept quality validation (Phase 109 §4.1)
**The single largest unvalidated assumption in the product.** Every other phase assumes concepts work; nothing owns proving that.

- [ ] Run `seed_concepts` on CoDRAG itself. Grade: completeness, accuracy, anchor accuracy, actionability (1–5).
- [ ] Run `seed_concepts` on 2 external test repos (different languages / sizes).
- [ ] If quality < 3 on any dimension → iterate seeder prompts.
- [ ] Verify `codrag_concepts(action="get")` returns seeded concepts via MCP.
- [ ] Verify concept staleness detection: modify anchored file, confirm stale.
- [ ] Verify concept conflict handling: two contradicting constraint concepts on same file.
- [ ] Run concept promotion flow end-to-end.

### Audit severity recalibration (Phase 109 §4.3 ≡ Phase 108 FIX-7)
**Consolidated ownership — these are the same work.**

- [ ] Build severity calibration fixture: healthy-small, healthy-medium, unhealthy repos.
- [ ] Run `codrag_audit(action="scan")`, record finding counts by severity on each.
- [ ] Adjust thresholds in `large_files.py` (still critical at 80K), `circular_deps`, `hub_concentration`.
- [ ] Exclude log files as findings (uncommon lock formats may also slip through — audit).
- [ ] Pass/fail bar: healthy repos < 5 critical findings after calibration.
- [ ] Add regression test locking in calibrated thresholds.

### Immune system end-to-end (Phase 109 §4.5)
**Killer feature for AI agents — verification is ~5 minutes of work and has never been done.**

- [ ] Verify **AMBIENT_INJECT alerts flow into `tool_codrag` responses** (enum is defined; injection is wired; the last mile to the MCP tool response is unverified).
- [ ] End-to-end integration test: seed → derive antibody → modify violating file → verify alert in `codrag()` response.

---

## Tier 2 — MVP-CRITICAL

### Pipeline stability (Phase 107)

**§4.2 Atomic Stage Handoff** (8 items, no progress — decide MVP-critical vs defer)
- [ ] Design `StageHandoff` class with coordinating lock.
- [ ] Identify safe-in-lock vs deferred bookkeeping ops.
- [ ] Refactor `_on_build_transition` to delegate to `StageHandoff.execute()`.
- [ ] Move slow operations to post-handoff deferred queue.
- [ ] Add watchdog timer (30s stall detection).
- [ ] Add structured logging for every handoff.
- [ ] Stress test: 3 projects × 15 stages × random pauses/cancels/resumes.
- [ ] Verify zero stalls across 100 consecutive runs.

**§4.6 Incremental pipeline recovery** (F-66/67/75 class)
- [ ] Replace JSON-file incremental flag with journal event (crash-safe).
- [ ] On daemon restart, detect "interrupted incremental" and offer Resume.
- [ ] Test: kill daemon mid-stage, restart, verify resume.

**§4.7 Recovery UI wiring**
- [ ] Add `incremental_pending` field to `/pipeline/status` response.
- [ ] Dashboard: Resume vs Discard state when flag is true.
- [ ] Show "Resume" button (not "Run") in affected panels.
- [ ] Wire Resume (with offset) and Discard (clears flag) actions.
- [ ] E2E test: kill daemon mid-stage, restart, verify Resume button appears and works.

**§4.3 / §4.4 open bugs**
- [ ] F-68: Resume button state when `incremental_pending=true` — JSON flag + daemon detect exist; UI wiring missing.
- [ ] F-15: Triage test rot on resume_strategy, mcp_server, queue_router, trace_builder_globs, team_sync_integration.
- [ ] Reduce `/system/pipeline-queue` to O(1) via cached queue snapshot.

**§4.5 SQLite WAL audit**
- [ ] Audit all SQLite stores for WAL vs DELETE mode consistency.
- [ ] Verify dedicated DB files (concept_store, antibody_store, pipeline_journal) mode choice.
- [ ] Add startup health check for stale WAL files.
- [ ] Add `codrag_settings.db` `busy_timeout` configuration.

### Pipeline safety & visibility (Phase 114)
Backend + UI shipped (Tasks 1–13). Remaining: follow-ups surfaced by two reverse-engineering audit passes.

**Shipped (for reference)**
- [x] T1 — Checkpoint coverage for finalize tail (`rules`, `concepts`, `audit`, `antibodies` added to `CHECKPOINT_STAGES`/`STAGE_OUTPUTS`/`_GOLDEN_FILES`).
- [x] T2 — Barrier status surfaced on `/pipeline/status`.
- [x] T3 — `DELETE /pipeline/reset-barrier` endpoint.
- [x] T4 — `GET /pipeline/health` aggregate endpoint.
- [x] T5 — `GET /pipeline/stages/{stage}/backups` (golden + branch snapshots listing).
- [x] T6 — `POST /pipeline/stages/{stage}/restore` (per-stage restore that bypasses barrier).
- [x] T7 — `BarrierIndicator` component (commit `17f199ca` adds `barrierGuidance()` keyed by reason).
- [x] T8 — `RecoverStagePanel` (per-stage backup picker + ConfirmDialog; mock + integration tests).
- [x] T9 — Rebuild "Wipe & Rebuild All" UX with typed-confirmation gate.
- [x] T10 — `HealthBadge` polling `/pipeline/health` with stuck-run count.
- [x] T11 — Hook wiring (`useApiClient`, `usePipelineHealth`, `useEnrichment` make the four UI components live).
- [x] T12 — Mirror `RecoverStagePanel` into SettingsDrawer Danger Zone (commit `c68177de`); refresh stage data after restore + gate Recover during runs (`b5fcdc16`).
- [x] T13 — Second-audit fixes (commit `2374140f`): mock barrier state mutability, BarrierIndicator `role=status` instead of `role=alert` (no screen-reader spam on 10s poll), RecoverStagePanel stage-scoped aria-labels, `DELETE /pipeline/reset-barrier` invalidates `/pipeline/status` cache. New `test_barrier_lifecycle_end_to_end` integration test.
- [x] T14 — Checkpoint GC at daemon startup (commit `ad6eb6c0`): new `prune_checkpoints_all_projects(keep=3)` helper called from `server.configure()` after `startup_recovery()`, so projects stuck in a crash loop don't accumulate `.checkpoints/run-*` forever (observed: 4-6 per project, up to 28 MB pre-fix).

**Open follow-ups**

- [x] **T15 — Thread `panelVisible` through dashboard panels** (commit `c50d39dc`). Derives `tracePipelinePanelVisible` from `dashboardLayout` state in `App.tsx`, threads it into `useEnrichment` (as `enrichmentPanelVisible`) and into `useDashboardPanels` via a new optional `tracePipelinePanelVisible` prop that `usePipelineHealth` consumes. Defaults to `true` during layout hydration so first-paint events aren't dropped. Both hooks now skip their polls when the trace-pipeline panel is closed. Backward-compatible (default-true) for callers that haven't migrated.
- [ ] **T16 — Time-aware barrier semantics (stash@{0} decision).** A 73-line rewrite of `src/codrag/services/pipeline/recovery.py` plus updates to `tests/test_selfheal_group.py` is currently sitting in `git stash@{0}`. It distinguishes *pre-barrier* stale state (heartbeat death before barrier write — should auto-clear) from *post-barrier* in-flight state (rebuild actively running, must hold barrier). Deferred because `recovery.py` is owned by the `busy-swirles` worktree per standing constraint. **Decision needed:** (1) apply stash to main, (2) leave stashed indefinitely, (3) inspect stash diff with user first.
- [ ] **T17 — Manual end-to-end pipeline-testing pass (uses `pipeline-testing` skill runbook).** Use `swift_repo` as target. Follow the runbook to exercise: full pipeline run, mid-stage daemon kill + restart, mid-rebuild crash, per-stage restore from snapshot, barrier clear via Danger Zone, watchdog heartbeat trip, golden checkpoint promotion. Goal: surface gaps the integration tests don't cover. Output: phase findings file + concrete bug tickets. **Blocks Phase 107 §4.6/§4.7 incremental-recovery vertical slice — that work needs to be informed by what real-world failures look like.**
- [ ] **T18 — Rank resume/shutdown gaps from the manual pass.** Take T17's findings and tier them into: (a) blockers for incremental-recovery vertical slice, (b) MVP-critical, (c) polish. Feeds the Tier 2 §4.6/§4.7 work below.
- [ ] **T19 — Swarm capped at 10 concurrent (deferred — owned by parallel AI track).** Phase 112 Task 3 covers this in the dual-LLM swarm scope. No action here; this entry is a pointer so it's not lost.

**Cross-references**
- T17/T18 feed → Tier 2 §4.6 Incremental pipeline recovery + §4.7 Recovery UI wiring (cross-phase collision #5: ship as one vertical slice).
- T16 stash decision feeds → `recovery.py` ownership reconciliation between `main` and `busy-swirles` worktree.
- T15 panelVisible threading is in scope for §5.4 Polling → SSE migration (which makes the whole "is panel visible" question moot for SSE-based panels — but until SSE migration ships, panelVisible is the right primitive).

### Dual-LLM swarm + settings (Phase 112)
All 19 tasks are open. MVP-critical marked [MVP] per the Phase 112 plan.

**Backend core**
- [ ] Task 1 [MVP] — Add swarm_optimizer constants (KIMI_MAX_BATCH, GEMINI_MAX_BATCH_ITEMS, GEMINI_ATTENTION_QUALITY_CEILING_TOKENS, GEMINI_HARD_CONTEXT_TOKENS, PLAN_TIER_CONCURRENCY).
- [ ] Task 2 [MVP] — Implement `get_optimal_swarm_config()` (quality-first sizing for worker/coordinator/synthesis).
- [ ] Task 3 [MVP] — Remove stale F-59 hardcap in `batch_profiles.py`; plan-tier concurrency (Free=1, Pro=3, Max=10).
- [ ] Task 4 [MVP] — Dual-LLM `SwarmOrchestrator` constructor with inherit-from-worker fallback.
- [ ] Task 5 [MVP] — Route `_coordinate` / `_synthesize` through coordinator_llm; `_fan_out` through worker_llm.
- [ ] Task 6 [MVP] — Add `get_coordinator_llm_client()` to config_manager with inherit fallback.
- [ ] Task 7 — Wire `atlas/generator.py` call site.
- [ ] Task 8 — Wire `concept_seeder.py` call site.
- [ ] Task 9 — Wire `group_reasoning.py` call site.
- [ ] Task 10 — Wire `cluster.py` call site (resolves Phase79-DualModel TODO).
- [ ] Task 11 — Full regression smoke (backend + lint + typecheck + in-daemon Free plan).

**UI & advanced settings**
- [ ] Task 12 [MVP] — Update `RECOMMENDED_MODELS`: remove qwen3:{4b,8b,14b,30b}; recommend Gemini Flash + Kimi stack.
- [ ] Task 13 [MVP] — `AdvancedLLMSettings` type interface (`enforce_cloud_token_safety`, `max_thinking_budget`, `ollama_plan_tier`).
- [ ] Task 14 [MVP] — `AdvancedLLMSettings` UI (toggle + budget slider + plan-tier selector) + Storybook.
- [ ] Task 15 [MVP] — Mount panel in `AIModelsSettings`; verify dev-server integration.
- [ ] Task 16 [MVP] — Wire cloud-token-safety toggle into `batch_profiles.py` (promote Gemini to LARGE when disabled).
- [ ] Task 17 — Wire `max_thinking_budget` into `llm_client.py` (replace hardcap at 620–626).
- [ ] Task 18 — Surface swarm telemetry: synthesis JSON validity, worker success rate, wall-clock.
- [ ] Task 19 — E2E smoke: Max/Pro/Free plan stacks; record actual metrics.

### MCP tool quality (Phase 108)

**§4.1 Remaining fixes (2 of 9)**
- [ ] FIX-5 — Code-vs-docs multiplier on hub ranking (`atlas/generator.py:882-890`).
- [ ] FIX-7 — Audit severity (overlaps with Tier 1 §4.3 — single workstream).

**§4.2 Client-aware delivery**
- [ ] Wire `self._client_name` into rules regeneration path. **Decide:** session-reactivity vs install-time pre-generation.
- [ ] Human-test each generated format against the actual IDE.
- [ ] Add `codrag_audit(action="antibodies")` data to generated rules.

**§4.3 Swarm verification** (overlaps with Phase 112 rollout)
- [ ] Verify concept-seeding swarm end-to-end on test repo.
- [ ] Verify audit Tier 2 swarm end-to-end.
- [ ] Add swarm status to `/pipeline/status`.
- [ ] Dashboard UI for swarm status.

**§4.4 External agent integration**
- [ ] OpenClaw smoke test.
- [ ] Document multi-step pattern for compound queries.

**§4.5 MCP resources & prompts**
- [ ] Verify all MCP Resources browsable (atlas, structure, modules, audit, concepts, focus).
- [ ] Test MCP Prompts (`codrag-onboard`, `codrag-review`, `codrag-plan`, `codrag-investigate`, `codrag-health`).
- [ ] Update tool descriptions per arXiv rubric if drifted.

### MVP readiness (Phase 111)

**§5.1 Golden-path QA (human)**
- [ ] Fresh install on clean macOS.
- [ ] Small repo (~50 files) Fast Sync stages 1–5 in ≤ 5 min.
- [ ] KB Status shows "Ready".
- [ ] Cursor + CoDRAG MCP: `codrag` returns structural overview.
- [ ] `codrag_search("where is the main entry point")` returns relevant result.
- [ ] Medium repo (~500 files) ≤ 15 min.
- [ ] Large repo (~2000 files) ≤ 30 min.
- [ ] Log failures in a phase findings file.

**§5.2 API surface audit**
- [ ] Enumerate all public endpoints (76+).
- [ ] Verify envelope format consistency.
- [ ] Verify field-name consistency.
- [ ] Verify graceful degradation on empty/new projects.
- [ ] Fix inconsistencies found.
- [ ] Update `API.md` with undocumented endpoints.

**§5.3 Dev/prod separation**
- [ ] Audit all `CODRAG_DEV_MODE` reads (5+ scattered) → single import module.
- [ ] Startup-only dev mode (fixes Tier-0 item too).
- [ ] Add `_dev_only` decorator for debug endpoints.
- [ ] Verify Vite prod build strips debug console.log.
- [ ] Verify Tauri prod build sidecar has no dev deps.
- [ ] Create `BUILD_MODES.md`.

**§5.4 Polling → SSE migration** (17 pollers identified)
- [ ] Extend `/events` SSE schema (pipeline_progress, build_status, scheduler_queue, health).
- [ ] Implement `useSSEStatus` hook.
- [ ] Replace 17 pollers one-by-one.
- [ ] Remove `setInterval` from hooks.
- [ ] Verify dashboard works SSE-only.
- [ ] Measure: steady-state TCP connections drop to 1–3.

**§5.5 Phase 90 diagnostics** (19 of 21 still open)
- [ ] Verify `GET /projects/{id}/audit/findings` returns data (endpoint not located).
- [ ] Confirm atlas cycle data accessibility.
- [ ] **Design decision:** have `run_structural_audit` detect cycles directly from trace graph.
- [ ] Work through the remaining 19 items on the Haley diagnostic list.

**§5.6 Free-tier enforcement (verification)**
- [ ] Verify upgrade prompts in dashboard.
- [ ] Verify tier display in `LicenseStatusCard`.

**§5.7 MCP server resilience (0/4)**
- [ ] Handle daemon overload gracefully (timeout + retry).
- [ ] Circuit breaker: >5s unresponsive → cached context.
- [ ] Health check on startup.
- [ ] Test: full 15-stage pipeline on large repo, MCP stays connected.

**§5.8 Content & marketing alignment — path_weights gap**
- [ ] Dashboard Knowledge-Graph UI for writing `path_weights` (backend shipped; users must edit JSON/API today).
- [ ] Verify "works offline" — zero network calls in default config.
- [ ] Update stale marketing copy found during audit.

---

## Tier 3 — POLISH / FOLLOW-UP

### Retrieval intelligence (Phase 110)
Core shipped; below are the remaining polish items.

**Intent classification**
- [ ] EXAMPLE intent: boost test files; filter for usage patterns.
- [ ] COMPARE intent: parallel search + interleave.
- [ ] Tests: 5 queries per intent type.

**Path weights propagation**
- [ ] Apply path weight in `assign_lod()`.
- [ ] Apply path weight in atlas routing.
- [ ] Apply path weight in trace expansion.
- [ ] MCP response surfaces path weights.
- [ ] Document path-weight behavior in generated `AGENTS.md`.
- [ ] Dashboard writes `path_weights` (see §5.8 — same item).

**Role-based weight composition**
- [ ] Role resolver maps roles → implicit path-weight overrides.
- [ ] `role="ceo"` boosts hub files + atlas summaries.
- [ ] Verify role weights compose with explicit path weights (explicit wins).
- [ ] Test: `role="security"` + explicit `{"vendor/": 0.3}` — vendor suppression wins.

**Query signal wiring**
- [ ] Wire `QuerySignals.coverage_ratio()` into search scoring (additive boost + floor filter).
- [ ] Implement `signal_boost` (additive, like `hub_boost`).
- [ ] Filter results with 0 keyword coverage below threshold.

**Chunking**
- [ ] Decide per-chunk context headers (`# File: {path}`) vs current meta-chunk-only synopsis.
- [ ] Measure R@1 impact via `scripts/benchmark_embeddings.py`.
- [ ] Publish delta; retrospective ship/defer decision.

**Sub-atlas / role lens (Phase 104)**
- [ ] Verify sub-atlas segments render in `AtlasLensPanel`.
- [ ] Wire role lens to `codrag(role=...)`.
- [ ] Test `role="security"` focuses on auth subsystems.
- [ ] Run Phase 104 verification: ruff / pytest / typecheck / storybook.

### Knowledge-layer polish (Phase 109 §4.2, §4.4, §4.6, §4.7)

- [ ] Verify `ConceptsPanel` renders with seeded data (count, cluster summary, coverage bar, pending-question badge, inline answers).
- [ ] SARIF enrichment: snapshot test with ruff on CoDRAG; with eslint on a TS project.
- [ ] Document CI pipeline SARIF integration.
- [ ] Wire assertion checking into audit: concept-violation → audit finding (decide ship vs defer).
- [ ] L2 scoped context (Phase 80):
  - Filter observations by `working_dir` proximity.
  - Filter concepts by anchor proximity.
  - Add `working_dir` to observation query.
  - Test: observation anchored to `core/index.py` with `working_dir="core/"` → appears; with `working_dir="api/"` → does not.

---

## Tier 4 — DEFERRED (recorded so they're not lost)

- **Phase 113 folder-reorganize** — full `.prep/` folder restructure (~2 weeks). XDG migration shipped (phase113-xdg_state) and handled the primary goal; folder-reorganize can land post-MVP.
- **Phase 115 — Watcher L3 plumbing** — Watcher has no Project handle, so `trace.ignore_patterns` can't be read at watcher startup. L1+L2 complete; pipeline runs honour L3. Needs architecture change (Project lookup from `index_dir`). Park for Phase 116+.
- **Phase 115 — maturin rebuild** — Rust walker + selfheal updates are ready; Python bindings need rebuild before daemon picks them up. Trivial; bundle with next daemon-restart-requiring release.
- **Phase 115 — Pre-existing analyzer failures** — 4 tests fail (Swift/Ruby/Kotlin/C# analyzers). Unrelated to Phase 115 (confirmed via stash). Triage separately.
- **Phase 112 Task 19 follow-up** — record post-rollout metrics in `SWARM_UI_PLAN_v2.md §9` once the rollout completes.

---

## Cross-phase collisions to resolve

1. **Audit severity** — Phase 108 FIX-7 ≡ Phase 109 §4.3. Single workstream; assign one owner.
2. **Path weights UI** — Phase 110 path-weight dashboard ≡ Phase 111 §5.8 marketing alignment. Single UI task.
3. **Swarm verification** — Phase 108 §4.3 swarm e2e overlaps with Phase 112 rollout (Task 19). Do them together.
4. **`CODRAG_DEV_MODE` cleanup** — Phase 111 §5.0 security + §5.3 dev/prod separation touch the same reads (5+). Single pass.
5. **Incremental recovery** — Phase 107 §4.6 backend + §4.7 UI + F-68 (§4.3) are one user-visible feature. Ship as a vertical slice, not three separate tickets.

---

## Suggested execution order

1. **Tier 0 (1–2 days)** — security guards, startup-only dev mode. Blocking for any public release.
2. **Tier 1, concept-quality sprint (~1 week)** — seed + grade + iterate on 3+ repos. Largest unvalidated assumption in the product.
3. **Tier 1, audit-severity calibration + AMBIENT_INJECT verification (~2–3 days)** — small but load-bearing.
4. **Tier 2 in parallel tracks:**
   - Track A — Pipeline stability (107 atomic handoff + recovery UI) + Pipeline-safety UI (114 Tasks 7–10).
   - Track B — Phase 112 dual-LLM swarm backend + Advanced Settings UI (cross-cuts with 108 swarm verification).
   - Track C — Phase 111 §5.1 golden-path QA (gates ship).
   - Track D — Phase 108 FIX-5 + MCP resources/prompts polish.
5. **Tier 3 (post-MVP polish)** — Phase 110 retrieval polish, Phase 109 dashboard/SARIF, Phase 111 SSE migration.
6. **Tier 4** — pick up post-ship.

---

## Bookkeeping

- Total non-FIXED items carried forward: **~180** across phases 107–111, plus ~19 from Phase 112, ~4 from Phase 114 UI, ~3 deferred from Phase 115.
- The Phase 102 application rename is **not** tracked here; see that phase directly.
- This file supersedes the task-list portions of `MASTER_INDEX.md` and `REALITY_CHECK_SUMMARY.md` for day-to-day planning; those remain the narrative record.
