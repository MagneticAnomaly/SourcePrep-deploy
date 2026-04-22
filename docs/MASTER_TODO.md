# Prep Master TODO (Cross-Phase Orchestrator)

## Purpose
This file orchestrates work across phases by:
- Defining cross-phase sprints (thematic bundles).
- Tracking shared implementation strategies/decisions that affect multiple phases.
- Linking to phase-level `TODO.md` files (where the detailed checklists live).

**Rule of thumb:**
- Phase `README.md` defines scope/spec.
- Phase `TODO.md` tracks execution (research + implementation + tests).
- This master file coordinates cross-phase sequencing and decision sync.

**Status key:**
- `[ ]` incomplete
- `[p]` in-progress — another AI is currently working on this task
- `[x]` complete

## Quick links (authoritative docs)
- `ROADMAP.md`
- `PHASES.md`
- `PHASE_DEPENDENCIES.md`
- `PHASE_RESEARCH_GATES.md`
- `RESEARCH_BACKLOG.md`
- `WORKFLOW_RESEARCH.md`
- `DECISIONS.md`
- `ARCHITECTURE.md`
- `API.md`

## Phase TODO index
- Phase00: `Phase00_Initial-Concept/TODO.md`
- Phase01: `Phase01_Foundation/TODO.md`
- Phase02: `Phase02_Dashboard/TODO.md`
- Phase03: `Phase03_AutoRebuild/TODO.md`
- Phase04: `Phase04_TraceIndex/TODO.md` (renamed to Code Graph in UI)
- Phase05: `Phase05_MCP_Integration/TODO.md`
- Phase06: `Phase06_Team_And_Enterprise/TODO.md`
- Phase07: `Phase07_Polish_Testing/TODO.md`
- Phase08: `Phase08_Tauri_MVP/TODO.md`
- Phase09: `Phase09_Post_MVP/TODO.md`
- Phase10: `Phase10_Business_And_Competitive_Research/TODO.md`
- Phase11: *(consolidated)* App tasks → S-07/S-15/S-28/S-29 below; Manual tasks → `FOR_ERIC_TODO.md`; Website tasks → `MARKETING_MASTER_TODO.md`
- Phase12: *(consolidated)* → `MARKETING_MASTER_TODO.md`
- Phase13: `Phase13_Storybook/TODO.md`
- Phase14: `Phase14_UI_UX_Improvements/README.md`
- Phase15: `Phase15_modular-design/TODO.md`
- Phase16: `Phase16_ContextIntelligence/README.md`
- Phase17: `Phase17_VSC-plugin/TODO.md`
- Phase18: `Phase18_DataVisualization/README.md`
- Phase19: `Phase19_Alt-Dev-Workflows/TODO.md`
- Phase20: `Phase20_support_strategy/README.md`
- Phase21: `Phase21_logs-and-progress/` (covered by Sprint S-13 — complete)
- Phase22: `Phase22_trace-epistomology/` (covered by Sprint S-22 — complete)
- Phase23: `Phase23_Cleanup-refactor/REFACTORING_STRATEGY.md`
- Phase24: `Phase24_StateMachine/README.md`
- Phase25: `Phase25_crashprotection/README.md` (complete)
- Phase26: `Phase26_DeepEnrichment-settings/STRATEGY.md` (planned, not started)
- Phase27: `Phase27_bug-reporting/README.md` (MVP complete)

## Dependency anchors (planning)
- **Canonical dependency doc:** `PHASE_DEPENDENCIES.md`
- **MVP critical path (typical order):**
  - Phase01 → Phase02 → Phase03 → Phase04 (optional for MVP) → Phase05 → Phase07 → Phase08 → Phase11
- **Research-level dependencies (do not outrun these):**
  - Phase01 → Phase02 (UI depends on stable API shapes + persistence format)
  - Phase01 → Phase03 (auto-rebuild depends on stable IDs/hashes/manifest)
  - Phase01 → Phase05 (MCP depends on stable build/search/context)
  - Phase02 + Phase07 → Phase08 (packaging depends on stable UI and operational requirements)

---

## Cross-phase sprint plan
These sprints are intentionally cross-phase. Each sprint should end with:
- Updated phase TODO checkboxes.
- Updated strategy ledger (below) if decisions changed.
- A short “Sprint Notes” entry in this file (optional, at bottom).

### Sprint S-00: Research closure for MVP-critical phases (01–05)
**Goal:** unblock implementation by closing the highest-leverage research gaps.

- [x] S-00.1 Close Phase01 research blockers (manifest schema, stable IDs, recovery model) 
  - Manifest schema: defined with version, file_hashes, build stats, config
  - Stable IDs: `ids.py` with sha256-based chunk/file/node IDs
  - Recovery: atomic build swap + stale build cleanup
- [x] S-00.2 Close Phase02 research blockers (UI IA + API shapes + error states) 
  - API shapes: done. UI IA: largely done (modular dashboard). Error states: done (ErrorState component + ApiException).
  - Completed via S-02 (Dashboard) and S-15 (Modular Design).
- [x] S-00.3 Close Phase03 research blockers (watch strategy, debounce/throttle defaults) 
  - Watcher: chokidar via subprocess, debounce 5s default, throttle, watcher state machine
- [x] S-00.4 Close Phase04 research blockers (node/edge schema, analyzer MVP) 
  - Schema: file/symbol/external_module nodes, contains/imports/calls edges
  - Analyzer: Rust engine with 8 language parsers
- [x] S-00.5 Close Phase05 research blockers (tool schemas, selection rules, budgets) 
- [x] S-00.5 Close Phase05 research blockers (tool schemas, selection rules, budgets) ✅
  - 4 tools: prep_status, prep_build, prep_search, prep_context
  - Budgets: k/max_chars/min_score caps in server.py

### Sprint S-01: Core trust loop (engine + contracts) 
**Goal:** make “add → build → search → context” reliable and contract-stable.

- [x] S-01.1 Core persistence + atomic build contract (Phase01) 
- [x] S-01.2 Error envelope + error code taxonomy alignment (Phase01/02/05/07)
- [x] S-01.3 Output budgets policy (k/max_chars/min_score) alignment (Phase01/02/05)

### Sprint S-02: Trust console UX (dashboard) 
**Goal:** a dashboard that answers “right project / fresh index / verifiable sources”.

- [x] S-02.1 Project navigation + tab model (Phase02) `AppShell` + `Sidebar` + `ProjectList` + `AddProjectModal`
- [x] S-02.2 Build/status UX + error playbooks (Phase02/07) `IndexStatusCard` + `BuildCard` + `ErrorState` + build polling
- [x] S-02.3 Search + chunk viewer + context output UX (Phase02) `SearchPanel` + `SearchResultsList` + `ChunkPreview` + `ContextOutput` + `ContextOptionsPanel`

### Sprint S-03: Freshness loop (auto-rebuild)
**Goal:** predictable staleness detection and bounded incremental rebuild.

- [x] S-03.1 Watcher + debounce + throttling behaviors (Phase03)
- [x] S-03.2 Incremental rebuild (hash + stable IDs) (Phase01/03) ✅
  - Per-file hash map stored in `manifest.json` (`file_hashes: {path: hash}`)
  - Cold-start incremental: loads previous index from disk when manifest has hashes (no in-memory state needed)
  - Deleted file detection: `files_deleted` count in build stats, stale chunks excluded
  - Noop detection: `mode="noop"` when nothing changed (all files reused, 0 embedded, 0 deleted)
  - Tests: `tests/test_incremental_rebuild.py` (7 tests)
- [x] S-03.3 Freshness UI and "what changed?" surfaces (Phase02/03) `WatchControlPanel` + `WatchStatusIndicator` + watch panel in dashboard
- [x] S-03.4 Reactive Enrichment Loop (Deepening) (Phase03/22) ✅
  - Auto-chaining of Deep Enrichment after Fast Sync (PipelineOrchestrator)
  - Deepening Loop for targeted repair of stale nodes (TraceAugmenter hash diffs)
  - Documented in `docs/REACTIVE_LOOP_STRATEGY.md`

### Sprint S-04: Code Graph foundations + bounded expansion
**Goal:** structural grounding that stays small, inspectable, and safe.

- [x] S-04.1 Graph schema + stable IDs + build integration (Phase04/01) ✅
  - Rust engine: `prep-walker`, `prep-parser`, `prep-graph`, `prep-engine` (41 tests)
  - Python: `TraceBuilder.build()` + `TraceIndex` load/search/neighbors/status
  - 8 language parsers: Python, TS, JS, Go, Rust, Java, C, C++
  - Server: `/projects/{id}/trace/*` endpoints (status, build, search, nodes, neighbors)
- [x] S-04.2 Graph API + dashboard symbol browser (Phase04/02) ✅
  - API endpoints: done (search, node, neighbors, build)
  - `TraceStatusCard` UI component: done (renamed to Graph Status)
  - `TraceExplorer` symbol browser: done (renamed to Code Graph)
  - API client: `searchTrace`, `getTraceNode`, `getTraceNeighbors`, `buildTrace`
  - Panel registered as 'trace' / 'Symbol Browser' in dashboard
- [x] S-04.3 Graph-aware context expansion budgets (Phase04/01/02/05) 
  - `get_context_with_trace_expansion()` in `index.py` — follows graph edges to include related code
  - Server: `trace_expand` + `trace_max_chars` params on `POST /projects/{id}/context`
  - MCP: `trace_expand` param on `prep` tool
  - Graceful fallback: returns normal context if trace not available

### Sprint S-05: IDE workflows (MCP) 
**Goal:** stable MCP tools with conservative defaults and debuggable project selection.

- [x] S-05.1 MCP stdio server (HTTP proxy) + daemon health behavior (Phase05/01) 
- [x] S-05.2 Tool schemas aligned with `API.md` and dashboard expectations (Phase05/02) 
- [x] S-05.3 Token-efficient output modes (lean-by-default) (Phase05) 
- [x] Implement `prep` tool (formerly `prep_context`)

### Sprint S-06: Reliability baseline + evaluation harness
**Goal:** prevent regressions; make failures actionable; define perf envelope.

- [x] S-06.1 Test fixtures + unit/integration test baseline (Phase07/01–05)  `tests/test_trust_loop_integration.py` + `tests/conftest.py`
- [x] S-06.2 Recovery + corruption detection behaviors (Phase07/01)  `tests/test_index_recovery.py` (13 tests)
- [x] S-06.3 "Gold queries" and manual eval loop (Phase07/04/05)  `tests/eval/` (10 gold queries + runner)

### Sprint S-07: Desktop packaging + deployment readiness
**Goal:** Tauri app + sidecar lifecycle + signed distribution path.

- [x] S-07.1 Tauri wrapper + sidecar startup/shutdown + port strategy (Phase08) ✅ **DONE: `Prep.app` builds with PyInstaller sidecar**
- [ ] S-07.2 Python Sidecar Build (SID-1..6)
  - [x] SID-1 Recreate dev venv with native ARM Python
  - [x] SID-2 PyInstaller spec file (`prep-daemon.spec`)
  - [ ] SID-3 Test sidecar binary on macOS
  - [ ] SID-4 Test sidecar binary on Windows
  - [ ] SID-5 Sidecar binary includes native embedder deps
  - [ ] SID-6 Sidecar binary naming convention (`prep-daemon-{target-triple}`)
- [ ] S-07.3 Rust Engine Wheels (ENG-1..7)
  - [x] ENG-1 GitHub Actions workflow (`engine-wheels.yml`)
  - [x] ENG-2 macOS ARM64 wheel builds
  - [x] ENG-3 Windows x64 wheel builds
  - [x] ENG-4 Linux x64 + ARM64 wheel builds
  - [x] ENG-5 Publish wheels to PyPI
  - [x] ENG-6 Integrate correct platform wheel into sidecar build
  - [x] ENG-7 Document target matrix
- [ ] S-07.4 Tauri Desktop App Build & Signing (TAU-1..8)
  - [x] TAU-1 Verify Tauri v1 builds locally
  - [x] TAU-2 Configure `externalBin` in `tauri.conf.json` for sidecar
  - [x] TAU-3 macOS code signing in CI (secrets configured)
  - [x] TAU-4 macOS notarization in CI (secrets configured)
  - [x] TAU-5 Windows code signing in CI (secrets configured)
  - [x] TAU-6 GitHub Actions release workflow (`.github/workflows/release.yml`)
  - [x] TAU-7 Release artifacts (`.dmg`, `.exe` via tauri-action)
  - [x] TAU-8 Smoke test installation (post-build artifact verification)

### Sprint S-08: Public docs + design system alignment
**Goal:** credible public-facing docs, consistent UI primitives across app + site.

- [x] S-08.1 Getting started + MCP onboarding docs scaffold (Phase12/05)
  - `docs/GETTING_STARTED.md`, `docs/MCP_ONBOARDING.md`, `docs/TROUBLESHOOTING.md`
  - `/guides/*` pages on docs site (embeddings, path weights)
- [x] S-08.2 Visual direction prototypes + token strategy + Storybook baseline (Phase13/02/12)
  - All "Radical" visual directions (Neo-Brutalist, Retro, Glass, etc.) ported to `@prep/ui`
  - Storybook reorganized (`Dashboard/Widgets`, `Dashboard/Layouts`, `Foundations`)
  - Shared `Button` and `Select` primitives standardized across app + site

### Sprint S-09: Team/enterprise feedback loop (design constraints, post-MVP implementation)
**Goal:** keep enterprise constraints influencing earlier phases without shipping risky surfaces in MVP.

- [ ] S-09.1 Embedded mode + network-mode safety baselines (Phase06)
- [ ] S-09.2 Policy/config provenance UX implications (Phase06/02)

### Sprint S-14: Comprehensive QA & Polish (Phase 07)
**Goal:** MVP quality bar — rigorous testing, error handling, and operational visibility.

- [x] S-14.1 Test harness expansion (integration tests, failure injection, gold queries)
- [x] S-14.2 Error taxonomy refinement & actionable messaging (Phase07/02) ✅ **DONE: `docs/ERROR_CODES.md` + `ApiException`**
- [x] S-14.3 Recovery behaviors (interrupted build, corruption, disk pressure)
  - [x] Disk pressure detection (`INSUFFICIENT_SPACE`)
- [x] S-14.4 Performance benchmarks & optimization

### Sprint S-17: VS Code Extension MVP (Phase 17)
**Goal:** Native VS Code experience powered by the Prep daemon.

- [x] S-17.1 Daemon management & connectivity (auto-start, polling, health checks)
- [x] S-17.2 WebViews Integration (React + Vite + Tailwind pipeline)
  - Search, Context, Trace panels
- [x] S-17.3 Core Commands & Tree Views
  - Project/File management, Index Status, Licensing commands
- [x] S-17.4 Post-MVP polish (high-res icons, pin file command, chat provider)
- [ ] S-17.5 Extension Packaging & Publishing (VSC-1..5)
  - [ ] VSC-1 Extension sidecar: bundle Python daemon binary
  - [ ] VSC-2 Integrate correct engine wheel into extension sidecar
  - [ ] VSC-3 `vsce package` produces working `.vsix`
  - [ ] VSC-4 Publish to VS Code Marketplace (See FOR_ERIC_TODO.md)
  - [ ] VSC-5 Extension auto-update (handled natively)

### Sprint S-28: Upgrade Safety & Data Migration (Phase 11)
**Goal:** Safe upgrades across versions without data corruption.

- [ ] UPG-1 `format_version` in index/trace manifests — detect incompatibility
- [ ] UPG-2 Define what persists across upgrades
- [ ] UPG-3 Define what may break (format changes)
- [ ] UPG-4 Install/uninstall tests per OS
- [ ] UPG-5 Air-gapped sanity test (app works without internet)

### Sprint S-29: Enterprise & Alternative Distribution (Phase 11)
**Goal:** Air-gapped deployment, enterprise controls, and other app stores.

- [ ] ENT-1 Air-gapped build variant (`PREP_DISABLE_UPDATES` + `PREP_OFFLINE`)
- [ ] ENT-2 MDM-friendly license deployment
- [ ] ENT-3 Audit logging (local file or syslog)
- [ ] ENT-4 Shared team configuration export/import
- [ ] ENT-5 Document enterprise deployment guide
- [ ] MAS-1 Decide: pursue Mac App Store or defer indefinitely
- [ ] MAS-2 If yes: implement Apple IAP integration
- [ ] MAS-3 If yes: App Sandbox testing

### Sprint S-12: Context MVC Verification (Phase 19)
**Goal:** Verify and document "Verified Views" (Gemini CLI, Qwen Code) to enable BYO-View architecture.

- [ ] S-12.1 Verify Gemini CLI Desktop MCP integration (Phase19)
- [ ] S-12.2 Verify Qwen Code MCP integration (Phase19)
- [ ] S-12.3 Publish "Verified Views" integration guides (Phase19)

### Sprint S-13: Operational Visibility (Logs & Progress)
**Goal:** Real-time visibility into background processes (indexing, trace building) via Log Console and granular Progress Bars.

- [x] S-13.1 Backend Event Bus (SSE) & Log Capture (Phase02)
- [x] S-13.2 Progress Callback Wiring (Phase01/04)
- [x] S-13.3 Frontend Log Console & Progress Components (Phase02)
- [x] S-13.4 Dashboard Integration (Phase02)

### Sprint S-15: Monetization & Distribution Plumbing (Phase 11)
**Goal:** End-to-end licensing flow, payments recovery, and secure update channels.

- [x] S-15.1 License Activation Exchange (api.sourceprep.io relay + Ed25519 verification)
- [x] S-15.2 Payments Recovery (Lemon Squeezy order lookup integration)
- [ ] S-15.3 Auto-Update System (UPD-1..10)
  - [x] UPD-1 Embed updater public key in `tauri.conf.json`
  - [x] UPD-2 Configure updater endpoint → GitHub Releases
  - [x] UPD-3 `tauri-action` generates `latest.json`
  - [x] UPD-4 Frontend update check
  - [x] UPD-5 `UpdateBanner.tsx` component
  - [x] UPD-6 Wire frontend to Tauri JS API
  - [ ] UPD-7 E2E test in-app update
  - [ ] UPD-8 "What's New" modal after update
  - [ ] UPD-9 Settings toggle: "Check for updates automatically"
  - [ ] UPD-10 Enterprise config: `PREP_DISABLE_UPDATES`
- [ ] S-15.4 Licensing & Feature Gating (LIC-1..8)
  - [ ] LIC-1 Ed25519 license signature verification
  - [x] LIC-2 License file loading
  - [ ] LIC-3 Lemon Squeezy webhook → license key generation
  - [ ] LIC-4 License activation UI in Tauri
  - [ ] LIC-5 Frontend "Upgrade to Pro" prompts
  - [ ] LIC-6 License status view in Settings
  - [ ] LIC-7 `updates_until` enforcement
  - [ ] LIC-8 Define "what Prep contacts" statement

### Sprint S-16: MCP Maturity & Ecosystem (Phase 05)
**Goal:** Complete the MCP story for remote/team usage and registry publication.

- [x] S-16.1 Streamable HTTP Transport (P05-R5) - for remote/enterprise usage
  - Implemented in `src/prep/mcp_server.py` (`run_http`, `/sse`, `/message`)
- [x] S-16.2 Async Tasks for long-running builds (P05-R7)
  - Implemented as async Tool (`prep_build` returns immediate "started") + Polling (`prep_status`)
- [x] S-16.3 PyPI Package Verification for MCP Registry (P05-I19)
- [x] S-16.4 Tool Icons & Metadata Polish (P05-R9)

### Sprint S-18: Data Visualization (Phase 18)
**Goal:** Make invisible index activity visible and beautiful via CLI and Dashboard.

- [x] S-18.1 CLI Visualizations (Activity Heatmap, Index Health, Build Sparkline)
- [x] S-18.2 Dashboard Viz Panels — `IndexHealthPanel` (health score, metrics grid) + `TokenBudgetPanel` (usage bar, window timer) registered in panel registry + wired into `useDashboardPanels`
- [x] S-18.3 Index Drift & RAG Flow visualization tools

### Sprint S-19: Lean Support Strategy (Phase 20)
**Goal:** Consolidate support channels to GitHub Discussions + single email.

- [x] S-19.1 Update Marketing `/contact` page (Community vs Private split)
- [x] S-19.2 Implement standalone Support App (Headless GitHub portal)
- [x] S-19.3 Update global navigation support links

### Sprint S-20: Modular Dashboard (Phase 15)
**Goal:** Grid-based, draggable, persistent dashboard layout system.

- [x] S-20.1 Core Layout Engine (`DashboardGrid`, `PanelChrome`, `useLayoutPersistence`)
- [x] S-20.2 Panel Registry & Component Extraction
- [x] S-20.3 Panel Picker & Layout Controls
- [x] S-20.4 Storybook Documentation (Sprint 7) & DoD Checklist

### Sprint S-21: UI/UX Improvements (Phase 14)
**Goal:** Polish visual consistency, form layouts, and spacing across the dashboard.

- [x] S-21.1 Form UI Updates (BuildCard, SearchPanel, ContextOptions spacing)
- [x] S-21.2 Standardized Loaders & Icons
- [x] S-21.3 Trace Status Card consistency
- [x] S-21.4 Documentation (`Form_UI_Updates.md`)

### Sprint S-11: Frontend-Backend Integration + Tier Enforcement
**Goal:** Wire auto-rebuild ↔ auto-trace, enforce paid/free tiers, connect Rust engine info to frontend.

- [x] S-11.1 Fix watcher crash: `trigger_build` called `_start_project_build` with wrong args 
- [x] S-11.2 Wire auto-trace into watcher: file changes now trigger both index + trace rebuilds 
- [x] S-11.3 Feature gating framework (`src/prep/core/feature_gate.py`) 
  - 5 tiers: FREE, STARTER, PRO, TEAM, ENTERPRISE
  - 11 gated features + project count limits
  - License from `~/.runprep/license.json` or `PREP_TIER` env var
  - `FeatureGateError` → 403 with upgrade hint
- [x] S-11.4 Gate enforcement in server 
  - `POST /projects` → project count limit (1 free, 3 starter, unlimited pro)
  - `POST /projects/{id}/watch/start` → requires STARTER+ tier
  - `GET /license` → exposes tier + feature availability to frontend
- [x] S-11.5 Frontend Rust engine integration 
  - `TraceStatus` type: added `engine`, `supported_languages` fields
  - `TraceStatusCard`: shows "Rust Engine" badge + 8 language chips
  - `TraceCoveragePanel`: added Java, C, C++ language labels
  - `TraceExplorer`: added struct/enum/trait/interface/namespace/async_* symbol type colors
  - `compute_trace_coverage`: default globs now cover all 8 languages
  - `_detect_language`: handles Java, C, C++ extensions
- [x] S-11.6 API client + types for license endpoint 
  - `LicenseStatus`, `FeatureAvailability` types in `types.ts`
  - `getLicense()` on `ApiClient` interface + `PrepApiClient` + `MockApiClient`
- [x] S-11.7 Tests: 32 feature gate tests + 167 total passed, 0 failed 

### Sprint S-22: Trace Epistemology (Phase 22)
**Goal:** LLM-augmented trace graph with epistemic scoring, cluster synthesis, and continuous deepening.

- [x] S-22.1 Rust Markdown Extraction (Pass 0) — `markdown.rs` 11 tests, section/ref/link/status analysis
- [x] S-22.2 Strategic Snippet Selection (Pass 1) — `_get_strategic_excerpt()`, DOC_ROLE prompts
- [x] S-22.3 Pass 0.5 LLM-Guided Re-Trace — `incorporate_inferred_edges()` in prep-graph, 7 tests
- [x] S-22.4 Pass 2 Epistemic Enrichment — `epistemic_score.py` + `epistemic_enrichment.py`, topological sort, 14b prompts
- [x] S-22.5 Pass 3 Cluster Synthesis — `cluster.py`, tag grouping + connected components, `trace_modules.jsonl`
- [x] S-22.6 Pass 4+ Continuous Deepening Loop — `deepening.py`, EnrichmentQueue + DriftDetector + ConvergenceTracker
- **Test totals:** 59 Rust + 329 Python = 388 tests, ALL GREEN

### Sprint S-23: Cleanup & Refactor (Phase 23)
**Goal:** Extract god-object App.tsx into domain hooks; split server.py into routers.

- [x] S-23.1 Backend: server.py 4,352 → 313 lines; routers in `src/prep/api/routers/` (system, license, trace, knowledge, llm, projects)
- [x] S-23.2 Frontend Phase A: `enrichmentReducer.ts` + `useEnrichment.ts` extracted from useTraceSystem
- [x] S-23.3 Frontend Phase B: `useSearchContext.ts` extracted (13 useState + 3 useCallback)
- [x] S-23.4 Frontend Phase C: `useFileSystem.ts` extracted (fileTree, pathWeights, includedPaths, pinnedPaths)
- [x] S-23.5 Frontend Phase D: `useDashboardPanels` 120+ flat props → 7 domain sub-objects
- [x] S-23.6 Backend: extracted `embedder_factory.py` from `build_manager.py` (510→445 lines); 515 tests pass

### Sprint S-24: State Machine Architecture (Phase 24)
**Goal:** Replace implicit state with explicit FSMs across frontend and backend.

- [x] S-24.1 SM-4: BuildOrchestrator — `build_orchestrator.py`, BuildSlot FSM (IDLE→QUEUED→RUNNING→COMPLETED→FAILED), 8 BuildTypes
- [x] S-24.2 SM-6: PipelineOrchestrator — `pipeline_orchestrator.py`, 8-stage 2-group pipeline, WorkerFactory, auto-chain
- [x] S-24.3 Pipeline API router — `POST /pipeline/fast|deep|all`, `GET /pipeline/status`, `POST /pipeline/cancel`
- [x] S-24.4 Frontend wiring — useTraceSystem hooks → runPipelineFast/Deep/All; PipelineStatus types
- [x] S-24.5 SM-8: Knowledge Scope — `api/routers/scope.py` (status, add, remove, rebuild)
- [x] S-24.6 Settings persistence — `services/settings_store.py` SQLite key-value store with namespaces, listeners, JSON migration
- [x] S-24.7 Tier gating — `require_feature()` in `feature_gate.py`, enforced at API/action level in `projects.py`
- [x] S-24.8 SM-1 frontend reducers — useProjectManager, useEnrichment, useSearchContext, useFileSystem, self-hydrating useTraceSystem

### Sprint S-25: Crash Protection & Resumability (Phase 25)
**Goal:** Persistent pipeline journal so crashes don't lose progress.

- [x] S-25.1 `PipelineJournal` — SQLite-backed journal with CRUD, heartbeat thread, zombie detection
- [x] S-25.2 `PipelineCheckpoint` — backup/restore/verify trace files, auto-heal on recovery
- [x] S-25.3 Orchestrator integration — every state transition writes to journal before work
- [x] S-25.4 Startup recovery — `journal.init()` → `startup_recovery()` in `server.py configure()`
- [x] S-25.5 API endpoints — `GET /pipeline/crashed`, `POST /pipeline/resume|discard`
- [x] S-25.6 Frontend — `crashedRuns` state, `handleResumeCrashedRun`, crash detection on hydration
- [x] S-25.7 Tests — 31 tests covering journal, checkpoint, orchestrator integration

### Sprint S-26: Deep Enrichment Settings (Phase 26)
**Goal:** Unify Deep Enrichment UI — pipeline panel controls ↔ settings drawer ↔ backend modes.

- [x] S-26.1 Rename `DeepAnalysisSchedule` → `DeepEnrichmentConfig` + backward-compat aliases in `types.ts`; unified `DeepEnrichmentMode` from types.ts
- [x] S-26.2 True Auto mode — `_is_deep_enrichment_auto()` chains deep enrichment after fast sync in `pipeline_orchestrator.py`
- [x] S-26.3 Scheduled mode — `ScheduleEvaluator` in `pipeline_budget.py`: interval + threshold triggers, wired into `server.py` startup
- [x] S-26.4 `GraphEnrichmentPipeline.tsx` — `onOpenDeepSettings` wired, gear icon shown in scheduled mode
- [x] S-26.5 `BudgetThrottle` in `pipeline_budget.py`: per-project sliding window token cap, checked before auto-chain in `pipeline_orchestrator.py`

### Sprint S-27: Bug Reporting System (Phase 27)
**Goal:** One-click bug report from dashboard with 27-point auto-diagnostics.

- [x] S-27.1 `BugReportModal` — form (email, severity, description, steps), auto-diagnostics preview, offline JSON fallback
- [x] S-27.2 `LogConsole` updated — bug icon triggers modal
- [x] S-27.3 `diagnosticData` wiring — `useDashboardPanels` assembles from all system hooks
- [x] S-27.4 Cloud ingestion — `websites/apps/support/src/app/api/bug-report/route.ts`, Resend notification, rate limit
- [x] S-27.5 Phase 27.2: Persistent storage — `lib/reports.ts` ReportStore abstraction + CRUD API routes (in-memory MVP, pluggable for Turso/Supabase)
- [x] S-27.6 Phase 27.3: Admin dashboard — `/admin/reports` list + `/:id` detail, ADMIN_TOKEN auth, status workflow, filters, metrics
- [ ] S-27.7 Wire `RESEND_API_KEY` env var in support app deployment — *manual, see `FOR_ERIC_TODO.md` §3 (WEB-S5)*

### Sprint S-10: Context Intelligence (Phase16)
**Goal:** native embeddings (no Ollama required), user-defined path weighting.

- [x] S-10.1 Native `nomic-embed-text` embedder via ONNX Runtime (Phase16) 
  - `NativeEmbedder` class in `src/prep/core/embedder.py`
  - New deps: `onnxruntime`, `tokenizers`, `huggingface-hub`
  - Auto-download model on first use to `~/.cache/huggingface/`
  - Default embedder; Ollama becomes optional power-user config
  - CLI: `prep models` pre-downloads for air-gapped setups
  - Tests: `tests/test_native_embedder.py` (12 tests)
- [x] S-10.2 User-defined path weights for context weighting (Phase16) 
  - `path_weights: Dict[str, float]` in `repo_policy.json`
  - Applied at search time via `_resolve_path_weight()` (longest-prefix match)
  - API: `GET/PUT /projects/{id}/path_weights` + `PUT /projects/{id}` accepts `path_weights`
  - UI: weight editor (click ×1.0 badge) in FolderTree + FolderTreePanel + FileExplorerDetail
  - Hot-update: weights apply immediately to searches without rebuild
  - Tests: `tests/test_path_weights.py` (15 tests)
- [x] S-10.4 Update marketing copy to reflect embeddings as built-in core feature (Phase12/16) 
  - All hero variants updated: "built-in embeddings", "no Ollama", path weights
  - Public docs: guides for embeddings and path weights in `websites/apps/docs/`

---

## Cross-phase implementation strategy ledger
This section tracks shared decisions/strategies that must remain consistent across phases.

### STR-01: API response envelope and error model
- **Status:** ✅ Implemented
- **Source of truth:** `docs/API.md` + `src/prep/server.py` (`ApiException`, `ok()` helper)
- **Implementation:** `{ok: true, data: ...}` / `{ok: false, error: {code, message, hint}}` envelope.
  `ApiException` with status_code/code/message/hint. Parity across HTTP + MCP.
- **Remaining:** formal error code taxonomy documentation

### STR-02: Stable IDs (chunks, files, trace nodes)
- **Status:** ✅ Implemented
- **Implementation:** `src/prep/core/ids.py` — sha256-based derivations:
  - `stable_file_hash(content)` → 16-char hex
  - `stable_markdown_chunk_id(path, section, idx)`, `stable_code_chunk_id(path, idx)`
  - `stable_file_node_id(path)`, `stable_symbol_node_id(qualname, path, line)`
  - `stable_edge_id(kind, source, target)`
- **Guarantees:** deterministic, content-addressed for files, position-stable for chunks/nodes

### STR-03: Manifest schema + format versioning
- **Status:** ✅ Implemented
- **Implementation:** `src/prep/core/manifest.py` — `MANIFEST_VERSION = "1.0"`
  Fields: version, built_at, model, roots, count, embedding_dim, build (stats), config, file_hashes
- **Remaining:** formal `format_version` bump policy for breaking changes

### STR-04: Atomic build + last-known-good snapshot behavior
- **Status:** ✅ Implemented (atomic build); partial (snapshot)
- **Implementation:** `CodeIndex._swap_index_dir()` — temp dir → backup → rename → cleanup.
  `_cleanup_stale_builds()` removes orphaned temp dirs older than 1 hour.
- **Remaining:** P01-I8 — search/context from snapshot while build runs (currently blocks)

### STR-05: Output budgets and backpressure policy
- **Status:** ✅ Implemented
- **Implementation:** server-enforced caps in `server.py`:
  - search: k ≤ 100, min_score ≥ 0.0
  - context: max_chars ≤ 20,000, k ≤ 50
  - MCP: MAX_SEARCH_K=100, MAX_CONTEXT_K=50, MAX_CONTEXT_CHARS=20,000
  - trace: max_nodes ≤ 100, max_edges ≤ 200, hops ≤ 3

### STR-06: Watcher strategy (OS events vs polling fallback)
- **Status:** ✅ Implemented
- **Implementation:** chokidar via Node.js subprocess (`src/prep/watcher.py`).
  Debounce 5s default, throttle, state machine (disabled/idle/debouncing/building/throttled).
  Falls back gracefully if Node.js unavailable.

### STR-07: Trace analyzer strategy
- **Status:** ✅ Implemented
- **Implementation:** Rust engine with tree-sitter parsers for 8 languages.
  Python fallback via AST module. PyO3 bridge (`prep_engine`).
  `PREP_ENGINE=rust|python|auto` env var for selection.

### STR-08: Packaging strategy (Python sidecar)
- **Status:** Proposed
- **Impacts:** Phase08 feasibility/schedule, Phase11 distribution constraints
- **Next actions:** decide PyInstaller vs PyOxidizer for MVP and document rationale

### STR-09: Licensing + feature gating strategy
- **Status:** ✅ Decided + Enforcement Implemented
- **Implementation:** Lemon Squeezy as MoR. "Activation Exchange" flow:
  LS issues key → user enters in app → exchange via api.sourceprep.io → signed Ed25519 offline license.
  Documented in ADR-013 + `docs/DISTRIBUTION_AND_REVENUE_PLAN.md` (authoritative).
- **Enforcement:** `src/prep/core/feature_gate.py` — runtime tier checks.
  Server gates: project count, watcher.
  `GET /license` endpoint for frontend tier awareness.
  Dev override: `PREP_TIER=pro` env var.
- **Remaining:** Ed25519 signature verification in license loader, Tauri UI for license entry

### STR-10: Auto-rebuild ↔ auto-trace co-triggering
- **Status:** ✅ Implemented
- **Implementation:** Watcher `trigger_build` now calls both `_start_project_build()` (CodeIndex)
  and `_start_project_trace_build()` (Trace graph) when `trace.enabled=true` in project config.
  `is_building` checks both index and trace build threads.
- **Gating:** Auto-rebuild requires STARTER+ tier. Manual builds remain FREE.

### STR-11: Reactive Loop (Continuous Enrichment)
- **Status:** ✅ Implemented (Reactive Mode)
- **Source of truth:** `docs/REACTIVE_LOOP_STRATEGY.md`
- **Implementation:**
  - **Watcher (SM-5):** Triggers Fast Sync (Stages 1-4) on file save.
  - **Orchestrator (SM-6):** Auto-chains Deep Enrichment (Stages 5-8) if `deep_enrichment.mode="auto"`.
  - **Deepening Loop (Stage 7):** Identifies stale nodes via hash comparison (`trace_augmented.jsonl`) and re-processes only those nodes.
- **Constraints:** No infinite background loop; relies on "heal-on-save" to conserve resources. `scheduled` mode is planned but not yet implemented.

---

## Sprint notes (append-only)
Add brief notes here after completing a sprint:
- date
- what changed (decisions, scope)
- new blockers

### 2026-02-21: Phase 32 - `hi_prep` MVP Capabilities

**What was done:**
- **Doc Content Previews (O-1):** `hi_prep` now fetches the first heading + paragraph for `.md` files to provide content-aware summaries.
- **Hub File Identification (O-2):** Trace graph identifies highly-connected files in the user's selection (`GET /trace/hub_files`).
- **Filename-Based Topic Detection (O-3):** Groups selected files into project-specific topics (e.g., "authentication", "UI components") based on keyword clustering.
- **Smart Prompt Ordering (O-4):** Suggested prompts are sorted by relevance to the dominant file category selected.
- **Ambient Context Chain (O-5):** `_ai_note` updated to guide AI agents to use the `prep` tool for deeper content retrieval after `hi_prep`.
- **Change Detection (O-7):** Surfaces `stale` files from the trace coverage endpoint to warn users if their context is outdated.
- **Cross-File Relationships (O-8):** For small selections, `hi_prep` queries trace edges (`GET /trace/file_edges`) to show how selected files connect.
- **Docs updated:** `hi_prep` capabilities are documented in Quick Start, MCP Overview, and Windsurf integration pages.

### 2026-02-15: MASTER_TODO Reconciliation + Trace Graph + Bug Fixes

**What was done:**

*MASTER_TODO Reconciliation (13 stale items marked as fixed):*
- DEFAULT_LAYOUT panel ID drift → already fixed (v17 uses canonical IDs)
- Storybook FullDashboard drift → already uses PANEL_REGISTRY
- ErrorToast unwired → already wired in App.tsx
- HuggingFace download no-op → already wired via `handleDownloadModel`
- GraphEnginePanel exports → already removed
- `getGlobalConfig`/`updateGlobalConfig` legacy → already migrated to `/global/config`
- Phase 05 remaining items → already done in S-16
- Flaky test entries → fixed (see below)

*Bug Fixes:*
- **`POST /watch/stop` response shape mismatch:** Now returns `{enabled: false, state: "disabled"}` matching `WatchActionResponse` type. Start also returns flat `{enabled, state}` instead of nested `{enabled, status: {...}}`.
- **Flaky `test_deleted_file_not_carried_over`:** `FakeEmbedder.embed()` now uses `hashlib.sha256` instead of Python's `hash()` (which is randomized by `PYTHONHASHSEED`). Test itself rewritten to check `_documents` directly instead of relying on search similarity.

*New Features:*
- **Degenerate trace graph detection (P1):** `TraceIndex.status()` now returns `degraded: true` + `degraded_reason` when nodes > 0 but edges == 0. `TraceStatus` TypeScript type updated with new fields.
- **JS/TS import extraction for Python fallback (P2):** New `JSAnalyzer` class in `trace.py` — regex-based extraction of ES imports, CommonJS require, dynamic imports, re-exports, and symbols (functions, classes, interfaces, types, enums, exported constants). Relative imports resolve to file nodes. Wired into `TraceBuilder.build()` for `javascript`/`typescript` languages. 17 tests in `tests/test_js_analyzer.py`.

**Files changed:**
- `src/prep/api/routers/projects.py` — watch/start + watch/stop response shape
- `src/prep/core/trace.py` — JSAnalyzer class + degraded detection in status()
- `src/prep/core/embedder.py` — FakeEmbedder deterministic hash
- `packages/ui/src/types.ts` — TraceStatus degraded fields
- `tests/test_js_analyzer.py` — NEW (17 tests)
- `tests/test_incremental_rebuild.py` — fixed flaky test
- `docs/MASTER_TODO.md` — reconciled 13+ stale items

**Test results:** 55 passed (test_js_analyzer + test_incremental_rebuild + test_deep_merge + test_primer + test_atomic_build), 0 failed.

### 2026-02-14: Reactive Loop Strategy & Verification

**What was done:**
- Verified "Continuous Loop" implementation is actually a "Reactive Loop" (heal-on-save).
- Confirmed `PipelineOrchestrator` auto-chains Deep Enrichment after Fast Sync when in `auto` mode.
- Confirmed `DeepeningLoop` correctly uses file hash diffs to target only stale nodes.
- Created `docs/REACTIVE_LOOP_STRATEGY.md` to formalize this architecture.

**Status:**
- "Continuous" mode is fully functional as "Reactive Auto-Chain".
- `scheduled` mode is config-only (no active cron).

### 2026-02-01: API envelope + manifest/IDs scaffolding

**What was built:**
- HTTP daemon now supports the `docs/API.md` envelope and UI-facing routes:
  - `/projects/*` endpoints
  - `/llm/status` and `/llm/test`
- Shared helpers:
  - `src/prep/api/envelope.py` (envelope + exception handlers)
  - `src/prep/core/ids.py` (stable IDs + file hashes)
  - `src/prep/core/manifest.py` (manifest read/write + builder)
- Minimal tests added for envelope + manifest/ID roundtrips.

**Known followups:**
- `src/prep/api/responses.py` duplicates envelope helpers (see `docs/QA.md`).
- Phase03 incremental rebuild spec requires richer per-file manifest fields (see `docs/QA.md`).

### 2026-02-01: Sprint S-05 (MCP Integration) Complete

**What was built:**
- `src/prep/mcp_server.py` — Full MCP server implementation (stdio transport)
  - Tools: `prep_status`, `prep_build`, `prep_search`, `prep_context`
  - JSON-RPC protocol handling per spec 2025-11-25
  - Token-efficient lean outputs
  - Proper error codes (DAEMON_UNAVAILABLE, etc.)
- `prep mcp` CLI command — Runs MCP server with `--project` or `--auto` modes
- `prep mcp-config` CLI command — Generates configs for 5 IDEs:
  - Claude Desktop, Cursor, VS Code, JetBrains, Windsurf
- `tests/test_mcp_server.py` — Comprehensive test suite
- `mcp-server.json` — MCP Registry metadata file
- `src/prep/api/responses.py` — Standardized API response envelope
- Updated CLI: `status`, `search`, `context`, `build` now connect to daemon

**Research completed:**
- MCP spec 2025-11-25 analysis (transports, tools, Tasks, etc.)
- IDE compatibility matrix (15+ clients support stdio)
- Official SDK survey (Python SDK recommended)

**Decisions made:**
- HTTP proxy architecture (MCP server → daemon API)
- stdio transport first (universal IDE support)
- Tool naming: lowercase + underscores (per SEP-986)

**Remaining for Phase05:**
- [x] P05-I7 Ambiguity handling for multi-project
- [x] P05-I11 Debug mode file logging
- [x] P05-R5 Streamable HTTP transport (for remote/enterprise) ✅ Done in S-16.1
- [x] P05-R7 Async Tasks for long builds ✅ Done in S-16.2
- [x] P05-I19 PyPI verification for MCP Registry ✅ Done in S-16.3

### 2026-02-02: Documentation alignment + CLI/MCP gaps identified

**What was done:**
- Aligned `docs/Phase12.../MCP-Shim-strategy-and-examples.md` with canonical domain (`sourceprep.io`), repo name (`prep-mcp`), and attribution policy (optional/user-controlled).
- Updated `docs/Phase14_MCP-CLI/PUBLIC_GITHUB_STRATEGY.md` with current implementation status.

**Known gaps to resolve (CLI/daemon):**
- [x] CLI commands (`add`, `list`, `status`, `build`, `search`, `context`) do not unwrap `ApiEnvelope` ✅ **FIXED:** `_post_json` and `_get_json` now call `_unwrap_envelope` automatically
- [x] CLI extras (`activity`, `coverage`, `overview`) — **FIXED:** now use project-scoped endpoints `/projects/{id}/*`

### 2026-02-03: Dashboard “Pinned Files” feature groundwork

**What was built:**
- UI package groundwork for 2 new dashboard panels:
  - `file-tree`
  - `pinned-files`
  - Added new panel category: `projects`
  - Registered panels in `packages/ui/src/config/panelRegistry.ts`
  - Added default layout entries (hidden by default) in `packages/ui/src/types/layout.ts`
- UI behavior fix: `FolderTree` now propagates `onNodeClick` through nested nodes.
- Backend capability: added canonical file-content endpoint:
  - `GET /projects/{project_id}/file?path=<repo-root-relative-path>`
  - Includes path traversal + repo-root containment protections and a `max_file_bytes` limit.

**Research / gotchas discovered:**
- Python `Path.match()` has surprising edge cases with patterns like `**/*.md` and `**/.git/**` at repo root.
- Implemented glob checks using `fnmatch` with a normalization rule for patterns starting with `**/` (also test without that prefix) to ensure root-level files match as expected.

**Remaining work (next):**
- Implement `usePinnedFiles` (localStorage + fetch content) and wire `FolderTreePanel` + `PinnedTextFilesPanel` into:
  - `src/prep/dashboard/src/App.tsx`
  - Storybook `FullDashboard` demo
- Add missing scrollbar utilities + update UI package exports for new panels.
- [ ] MCP direct mode (`prep mcp --mode direct`) needs verification/smoke test.

### 2026-02-03: Progress capture + next TODOs

 **Progress captured/verified:**
 - Websites monorepo scaffold exists under `websites/apps/*`:
   - `websites/apps/marketing`, `websites/apps/docs`, `websites/apps/support`, `websites/apps/payments`
   - Each is a Next.js app using `@prep/ui` and the shared Tailwind preset.
 - Dev-only website UI controls implemented:
   - `DevToolbar` added (dev-only gated) to all 4 app layouts to switch `theme`, `dark`, and marketing `hero` variant via URL query params.
   - Marketing homepage wired to render a hero variant dynamically in dev (via `DevMarketingHero`).
 - Canonical daemon API uses `/projects/*` routes (legacy `/api/code-index/*` still exists in server but should be treated as compatibility only).

 **What’s left (prioritized):**

 #### Implementation
 - [ ] Websites: fix Next.js dev static asset 404s on ports 3000–3003 (`/_next/static/css/app/layout.css`, `/_next/static/chunks/main-app.js`, `app-pages-internals.js`)
   - Symptom: HTML can return `200`, but CSS/JS requests 404 causing unstyled/broken pages.
   - First attempt: stop all website dev servers, wipe `.next`, restart via `scripts/run_websites.sh --clean --dev`.
 - [x] Fix CLI HTTP client to unwrap `ApiEnvelope` everywhere (core commands and any remaining helpers). ✅ **DONE: `_unwrap_envelope` wired into all HTTP helpers**
 - [x] Resolve CLI endpoint drift: ✅ **DONE: all CLI commands use `/projects/{project_id}/*` routes**
 - [x] Project Primer MVP: ✅ **DONE**
   - config schema in `repo_policy.py` (filenames, score_boost, always_include, max_primer_chars)
   - score boost in `CodeIndex.search()` via `_primer_boosts()`
   - always-include option in `get_context_structured()` with deduplication
   - `FakeEmbedder` added for testing; 14 tests in `tests/test_primer.py`
 - [x] Atomic build + last-known-good snapshot (temp dir + swap) and recovery behavior on crash/interruption. ✅ **DONE**
   - Implemented in `CodeIndex.build()`: builds to `.index_build_<uuid>`, atomic swap via rename
   - Added `_cleanup_stale_builds()` to auto-recover on init
   - 4 tests in `tests/test_atomic_build.py`
 - [x] Implement staleness semantics (`status.stale`) for watcher/index ✅ **DONE**
   - `AutoRebuildWatcher.status()` now returns `stale` (bool) + `stale_since` (ISO timestamp)
   - Added project watcher endpoints: `/projects/{project_id}/watch/start|stop|status`
   - Project status endpoint exposes `stale` + `stale_since` at top level
   - 9 tests in `tests/test_watcher_staleness.py`
 - [x] MCP: add Streamable HTTP transport support (Phase05 P05-R5/P05-R7) ✅ **DONE**
   - Added `prep mcp --transport http --port 8401`
   - Implemented SSE endpoint (`/sse`) and message endpoint (`/message`) using FastAPI/Uvicorn

### 2026-02-09: VS Code daemon wiring audit — license + MCP config endpoints

**What changed:**
- Implemented missing daemon endpoints used by the VS Code extension client:
  - `POST /license/activate`
  - `POST /license/deactivate`
  - `GET /api/code-index/mcp-config`
- Updated `tests/test_mcp_config_endpoint.py` to unwrap the standard `{success,data,error}` envelope.

**New TODOs discovered:**
- [x] Backend: `POST /projects/{project_id}/watch/stop` response shape mismatch ✅ **FIXED**
  - `packages/vscode/src/client.ts` expects `{ enabled: boolean; state: string }`.
  - `packages/ui/src/api/types.ts` expects `WatchActionResponse` (`{ enabled: boolean; state: string }`).
  - Server now returns `{"enabled": false, "state": "disabled"}`. Start returns `{"enabled": true, "state": "..."}`.
- [x] Docs: add `POST /license/activate`, `POST /license/deactivate`, `GET /api/code-index/mcp-config` to `docs/API.md`.
 - [x] MCP direct mode smoke test ✅ **DONE: `tests/test_mcp_direct_smoke.py` (10 tests, uses FakeEmbedder)**

### 2026-02-14: Pinned Files feature (Dashboard)
- [x] Implemented "Pinned Files" feature in Dashboard (Phase02)
  - **Backend**: Added `GET /projects/{id}/file?path=...` endpoint with safety checks (traversal, globs, max_bytes).
  - **UI**: Added `FolderTreePanel` (browsable tree) and `PinnedTextFilesPanel` (content viewer).
  - **State**: Persisted pinned paths in `localStorage`.
  - **Integration**: Wired into `App.tsx` and Storybook.

### 2026-02-12: Trace Endpoint Stability & Test Polish

**What was done:**
- Fixed regression in `tests/test_trace_endpoints.py` caused by debug print statements interfering with response body assertions.
- Verified trace endpoint tests pass.
- Validated `tests/test_watcher_staleness.py` passes.
- Confirmed strict adherence to API envelope in test clients.

**Status:**
- All critical test suites (Integration, Trace, Watcher, Atomic Build) are passing.
- Ready for next phase of work.

 ### 2026-02-04: Universal UI + Storybook-First Strategy

 **What changed:**
 - **Workflow Shift**: Switched from running 4x Next.js dev servers (fragile, slow) to Storybook-first development (fast, isolated).
 - **Universal UI**: All marketing/docs components (`MarketingHero`, `FeatureBlocks`, `IndexStats`, `TraceGraph`) are now canonical in `@prep/ui`.
 - **Themes Ported**: All "Radical" visual directions (Neo-Brutalist, Retro, Glass, etc.) + required fonts are fully integrated into the shared package.

 ### 2026-02-05: Frontend-Backend Integration (S-02)

 **What was built:**
 - **Typed API Client** (`packages/ui/src/api/client.ts`): Extended `PrepApiClient` with 9 new methods:
   - Project CRUD: `createProject`, `getProject`, `updateProject`, `deleteProject`
   - Build: `buildProject` (with polling)
   - Roots: `getProjectRoots`
   - Watch: `startWatch`, `stopWatch`, `getWatchStatus`
   - Health: `getHealth`
 - **New API types** (`packages/ui/src/api/types.ts`): `CreateProjectRequest/Response`, `UpdateProjectRequest/Response`, `DeleteProjectResponse`, `BuildProjectResponse`, `WatchActionResponse`
 - **App.tsx full rewrite** (`src/prep/dashboard/src/App.tsx`): 1009→573 lines, exclusively Storybook components:
   - `AppShell` + `Sidebar` + `ProjectList` for multi-project navigation
   - `AddProjectModal` for project creation via `POST /projects`
   - `LoadingState` / `ErrorState` pattern components
   - `Button` atomic primitive (newly exported from `@prep/ui`)
   - `FolderTreePanel` wired to `/projects/{id}/roots`
   - All API calls via `useApiClient()` → canonical `/projects/{id}/*` routes
   - Removed: legacy `/api/code-index` routes, hand-rolled fetch, inline tree logic, raw HTML buttons
 - **main.tsx**: Wrapped with `ApiClientProvider` using `PrepApiClient`
 - **New exports from `@prep/ui`**: `Button`, `AddProjectModal`, `AddProjectModalProps`

 **Additional work (same session):**
 - **Select primitive** (`packages/ui/src/components/primitives/Select.tsx`): New Storybook component with variants (default, ghost) and sizes
 - **Panel details**: Restored `panelDetails` prop with `AIModelsSettings` (LLM expanded view) and `FolderTree` (roots expanded view)
 - **LLM config handlers**: Full endpoint management (add/edit/delete/test), model fetching via `/api/llm/proxy/*`, model testing
 - **Pinned Files feature**: 
   - Added `getProjectFileContent` to API client (uses `GET /projects/{id}/file?path=...`)
   - Pinned files state with localStorage persistence
   - `FolderTreePanel` wired with `includedPaths`, `onToggleInclude`, `onNodeClick` for pin/unpin
   - `PinnedTextFilesPanel` in `panelContent` with `onUnpin`
   - Content fetched from backend on pin

 **Decisions:**
 - Dashboard uses `window.location.origin` as API base (works when served by daemon)
 - Build polling at 2s intervals until `status.building === false`
 - Project config loaded from `GET /projects/{id}` on project selection
 - Pinned file paths persisted in `localStorage` under key `prep_pinned_files`

 ### 2026-02-05: HTTP API Integration Tests (S-06.1)

 **What was built:**
 - `tests/test_trust_loop_integration.py` — 18 tests covering the **core trust loop** HTTP API:
   - **Project Lifecycle**: add, get, list, delete, 404 handling
   - **Build Operations**: trigger build, wait for completion, status before build
   - **Search Operations**: search after build, search before build (409), min_score filtering
   - **Context Operations**: context assembly, max_chars limiting
   - **End-to-End**: full add → build → search → context flow
   - **Error Handling**: invalid project IDs across all endpoints

 **Test coverage now includes:**
 - `test_trust_loop_integration.py` (18 tests) — HTTP API integration
 - `test_mcp_direct_smoke.py` (10 tests) — MCP direct mode
 - `test_atomic_build.py` (4 tests) — Atomic build/recovery
 - `test_primer.py` (14 tests) — Primer feature
 - `test_watcher_staleness.py` (9 tests) — Watcher staleness
 - `test_trace_endpoints.py` — Trace API endpoints
 - `test_api_envelope.py` — Error envelope formatting

 #### Research / decisions
 - [x] STR-01: finalize error code taxonomy + `hint` rules across daemon/UI/MCP/CLI. ✅ **DONE: `docs/ERROR_CODES.md`**
 - [x] STR-03: manifest schema/versioning decision (per-file manifest fields vs format bump strategy). ✅ **DONE: `docs/MANIFEST_SCHEMA.md`**
 - [x] STR-04: atomic build + recovery contract (what gets swapped, how to detect partial builds). ✅ **DONE: `docs/ATOMIC_BUILD.md`**
 - [x] STR-05: budgets policy (server-enforced max caps) and alignment across UI + MCP + docs. ✅ **DONE: `docs/BUDGETS_POLICY.md`**
 - [x] Decide primer detection precedence (e.g. `AGENTS.md` vs `PREP_PRIMER.md`, root-only vs glob). ✅ **DONE: `docs/PRIMER_DETECTION.md`**

 #### Planning / coordination
 - [x] Sprint S-01: choose the next “trust loop hardening” bundle: ✅ **DONE**
   - CLI envelope + endpoint drift fixes
   - atomic build + recovery
   - minimal integration tests (add project → build → search → context) ✅ `tests/test_trust_loop_integration.py`
 - [x] Sprint S-08: publishable docs plan (Getting Started + MCP onboarding + Troubleshooting-first). ✅ **DONE**
   - `docs/GETTING_STARTED.md` — Installation and quick start
   - `docs/MCP_ONBOARDING.md` — AI assistant integration guide
   - `docs/TROUBLESHOOTING.md` — Common issues and solutions

 ### 2026-02-08: Frontend-Backend Integration + Tier Enforcement (S-11)

 **Critical bugs fixed:**
 - **Watcher crash:** `trigger_build` closure called `_start_project_build(proj)` with 1 arg but function requires 5. Auto-rebuild was broken at runtime for all users. Fixed with proper config extraction.
 - **No auto-trace:** Watcher only rebuilt CodeIndex (embeddings), never the trace graph. Files could change and trace would go silently stale. Now both are co-triggered.

 **Feature gating framework built:**
 - `src/prep/core/feature_gate.py` — Tier model (FREE→STARTER→PRO→TEAM→ENTERPRISE)
 - 11 feature gates + project count limits per tier
 - `FeatureGateError` → HTTP 403 with `FEATURE_GATED` code + upgrade URL
 - License from `~/.runprep/license.json` or `PREP_TIER` env var (dev override)
 - `GET /license` endpoint returns tier + full feature availability map
 - Server enforces: project count limit on `POST /projects`, watcher on `POST /watch/start`
 - Tests: `tests/test_feature_gate.py` (32 tests)
 - `conftest.py`: auto-use fixture sets `PREP_TIER=pro` so existing tests aren't blocked

 **Frontend-Rust engine integration:**
 - Backend: `TraceIndex.status()` now returns `engine` ("rust"/"python") and `supported_languages` (8 langs)
 - Backend: `compute_trace_coverage()` default globs now cover Go, Rust, Java, C/C++ (was Python/TS/JS only)
 - Backend: `_detect_language()` handles Java, C, C++ extensions; `SUPPORTED_EXTENSIONS` updated
 - Frontend `TraceStatus` type: added `engine?`, `supported_languages?` fields
 - Frontend `TraceStatusCard`: renamed "Trace Index" → "Code Graph", shows Rust Engine badge (⚡ orange) + 8 language chips
 - Frontend `TraceCoveragePanel`: added Java, C, C++ to `LANG_LABELS`
 - Frontend `TraceExplorer`: added `struct`, `enum`, `trait`, `interface`, `namespace`, `async_function`, `async_method` to `SymbolTypeTag` color map
 - Frontend API client: `getLicense()` method on `ApiClient`, `PrepApiClient`, `MockApiClient`
 - Frontend types: `LicenseStatus`, `FeatureAvailability` interfaces

 **Test results:** 167 passed, 36 skipped, 0 failed (ENGINE=rust)

 **Tier enforcement matrix (implemented):**
 ```
 Feature              FREE   STARTER  PRO    TEAM   ENTERPRISE
 ─────────────────────────────────────────────────────────────
 Projects max         1      3        ∞      ∞      ∞
 Manual build         ✓      ✓        ✓      ✓      ✓
 Manual trace build   ✓      ✓        ✓      ✓      ✓
 Trace search         ✓      ✓        ✓      ✓      ✓
 MCP tools (basic)    ✓      ✓        ✓      ✓      ✓
 Path weights         ✓      ✓        ✓      ✓      ✓
 Auto-rebuild         ✗      ✓        ✓      ✓      ✓
 Auto-trace           ✗      ✓        ✓      ✓      ✓
 MCP trace expand     ✗      ✗        ✓      ✓      ✓
 LOD compression      ✓      ✓        ✓      ✓      ✓
 Multi-repo agent     ✗      ✗        ✓      ✓      ✓
 Team config          ✗      ✗        ✗      ✓      ✓
 Audit log            ✗      ✗        ✗      ✗      ✓
 ```

 **Remaining work / roadblockers:**
 - [ ] Ed25519 license signature verification (currently trusts JSON file contents)
 - [ ] Tauri license entry UI + activation exchange flow
 - [x] Frontend upgrade prompts: **WON'T DO** — no upgrade prompts by design
 - [x] ~~Gate `lod_compression`~~ **REMOVED** — LOD compression is free for all tiers, no gate needed
 - [x] Gate `mcp_trace_expand` in context endpoint ✅ `context_project()` now calls `require_feature("mcp_trace_expand")` when `trace_expand=true`
 - [x] `WatchControlPanel` upgrade prompt: **WON'T DO** — no upgrade prompts by design
 - [x] `test_incremental_rebuild.py::test_deleted_file_not_carried_over` flaky test ✅ **FIXED:** `FakeEmbedder` now uses `hashlib.sha256` instead of `hash()` for cross-run determinism. Test now checks `_documents` directly instead of relying on search similarity.
 - [x] `test_mcp_config_endpoint.py` endpoint moved from `/api/code-index/mcp-config` to `/mcp/config` — tests updated ✅

 ### 2026-02-08 (continued): Deep Architecture Audit

 **API spec (docs/API.md) was missing 17+ endpoints.** All now documented:
 - `GET /license` — tier + feature availability
 - `POST/GET /projects/{id}/watch/start|stop|status` — file watcher
 - `GET/PUT /projects/{id}/path_weights` — per-path weight multipliers
 - `POST /projects/{id}/trace/build` — trigger trace build
 - `GET /projects/{id}/trace/coverage` — trace coverage stats
 - `POST /projects/{id}/trace/ignore` — manage trace ignore patterns
 - `GET /projects/{id}/roots`, `GET /projects/{id}/files`, `GET /projects/{id}/file` — file access
 - `GET /embedding/status`, `POST /embedding/download` — native embedder
 - Added `FEATURE_GATED` error code and HTTP 403 to spec

 **Architecture doc (ARCHITECTURE.md) had stale class names.** Fixed:
 - `IndexManager` → `CodeIndex` (actual class)
 - `LLMCoordinator` → `NativeEmbedder` + `OllamaEmbedder` + `LODExtractor` (actual classes)
 - `FileWatcher` → `AutoRebuildWatcher` (actual class)
 - Added `FeatureGate` to core engine diagram
 - Added `AutoRebuildWatcher` row (triggers both CodeIndex + TraceBuilder)
 - Updated external services: Ollama now optional, added Native ONNX + License

 **Duplicate trace endpoints found (3 pairs):**
 - `GET /trace/node/{id}` AND `GET /trace/nodes/{id}` — same handler
 - `GET /trace/neighbors/{id}` AND `GET /trace/nodes/{id}/neighbors` — same handler
 - `GET /trace/search` AND `POST /trace/search` — GET is query-param based, POST is body-based
 - **Decision needed:** consolidate to canonical paths only, deprecate duplicates

 **Frontend API client gaps (endpoints exist but no client method):**
 - [ ] `POST /llm/test` — force connectivity check (spec exists, no client method; `testLLMEndpoint()` calls `/api/llm/proxy/test` which is a different handler)
 - [x] `GET /embedding/status` — ✅ `getEmbeddingStatus()` added
 - [x] `POST /embedding/download` — ✅ `downloadEmbedding()` added
 - [x] `GET /projects/{id}/activity` — ✅ `getProjectActivity()` added
 - [x] `GET /projects/{id}/coverage` — ✅ `getProjectCoverage()` added

 **Tier enforcement audit — all gates now wired:**
 | Enforcement Point | Feature | Status |
 |---|---|---|
 | `POST /projects` | `projects_max` (count limit) | ✅ Wired |
 | `POST /watch/start` | `auto_rebuild` (STARTER+) | ✅ Wired |
 | `_apply_compression()` | LOD compression (all tiers) | ✅ Free |
 | `context_project()` trace_expand | `mcp_trace_expand` (PRO+) | ✅ Wired |
 | `GET /license` | All features | ✅ Wired |

 **UX revamp docs (Phase 14) — planned but not yet implemented:**
 - [x] COMPONENT_AUDIT_V2.md: **WON'T DO** — current panel names are final
 - [x] DASHBOARD_UX_REVAMP.md: **WON'T DO** — current dashboard layout is final
 - [x] Merge FolderTree + TraceCoverage: **WON'T DO** — separate panels preferred
 - [x] Move LLM settings to settings modal: **WON'T DO** — stays in dashboard
 - [x] "Bicameral" layout: **WON'T DO** — modular grid layout preferred

 **Phase TODO gaps — research items still open:**
 - [ ] P02-R1: Finalize dashboard information architecture
 - [x] P02-R3: Decide minimum build progress granularity for MVP ✅ SSE `TaskProgress` + per-stage progress bars (determinate + indeterminate)
 - [x] P02-T1/T2: E2E smoke tests and error-state tests for dashboard ✅ `tests/test_dashboard_e2e_flow.py` + `tests/test_dashboard_error_states.py`
 - [x] P02-I3: Global settings modal (Ollama URL, defaults) ✅ `SettingsDrawer` (Global tab) + `AIModelsSettings`

 **Test results:** 154 passed, 36 skipped, 0 failed (excluding known pre-existing failures)

 ### 2026-02-08 (continued): Frontend–Storybook–Backend Alignment Audit

 **Panel Registry vs App.tsx vs Storybook — misalignments found and fixed:**
 - [x] `file-tree` panel: registered in PANEL_REGISTRY but had NO content in App.tsx `panelContent` → would render empty panel. **Fixed:** added `FolderTreePanel` with file navigation.
 - [x] `pinned-files` panel: registered in PANEL_REGISTRY but had NO content in App.tsx `panelContent` → would render empty panel. **Fixed:** added pinned files list with unpin buttons + empty state.
 - [x] Storybook `FullDashboard` used non-canonical `trace-mini` and `trace-explorer` panel IDs not in PANEL_REGISTRY → registry's `trace` panel had no story content. **Fixed:** renamed to canonical `trace`, removed extra panel defs.
 - [x] Storybook `FullDashboard` missing `pinned-files` panel content. **Fixed:** added empty-state content.
 - [x] Removed unused imports: `Network`, `Badge`, `TraceGraphMini` from FullDashboard story.

 **Type mismatches found and fixed:**
 - [x] `LicenseTier` type was `'free' | 'pro' | 'team' | 'enterprise'` — missing `'starter'` tier that backend sends. **Fixed.**
 - [x] `LicenseStatusCard.tsx` `tierConfig` Record was missing `starter` entry → would crash on starter tier. **Fixed:** added blue-themed starter entry.

 **API client gaps found and fixed (7 methods added):**
 - [x] `getEmbeddingStatus()` → `GET /embedding/status`
 - [x] `downloadEmbedding()` → `POST /embedding/download`
 - [x] `getProjectActivity()` → `GET /projects/{id}/activity`
 - [x] `getProjectCoverage()` → `GET /projects/{id}/coverage`
 - [x] `testLLMEndpoint()` → `POST /api/llm/proxy/test`
 - [x] `fetchLLMModels()` → `POST /api/llm/proxy/models`
 - [x] `testLLMModel()` → `POST /api/llm/proxy/test-model`
 - [x] `MockApiClient` updated with stubs for all 9 new methods.

 **App.tsx LLM handlers migrated from raw `fetch` to typed `ApiClient` methods:**
 - [x] `handleTestEndpoint` → now uses `api.testLLMEndpoint()`
 - [x] `handleFetchModels` → now uses `api.fetchLLMModels()`
 - [x] `handleTestModel` → now uses `api.testLLMModel()`

 **Full Panel Registry ↔ App.tsx ↔ Storybook alignment matrix (current `PANEL_REGISTRY`):**
 | Panel ID | Registry | App.tsx | Storybook (FullDashboard) | Backend Connected |
 |---|---|---|---|---|
 | `log-console` | ✅ | ✅ LogConsole | ❌ | ✅ SSE events |
 | `usage-guide` | ✅ | ✅ UsageGuidePanel | ✅ | — |
 | `status` | ✅ | ✅ IndexStatusCard | ✅ | ✅ getProjectStatus |
 | `llm-status` | ✅ | ✅ LLMStatusWidget (+ details: AIModelsSettings) | ✅ | ✅ getLLMStatus + LLM proxy |
 | `search` | ✅ | ✅ SearchPanel | ✅ | ✅ search |
 | `context-options` | ✅ | ✅ ContextOptionsPanel | ✅ | ✅ assembleContext |
 | `results` | ✅ | ✅ SearchResultsList+ChunkPreview | ✅ | ✅ search |
 | `context-output` | ✅ | ✅ ContextOutput | ✅ | ✅ assembleContext |
 | `watch` | ✅ | ✅ WatchControlPanel | ✅ | ✅ start/stop/getWatchStatus |
 | `file-tree` | ✅ | ✅ FolderTreePanel (+ details: FileExplorerDetail) | ❌ (uses legacy `roots`) | ✅ roots/files/file |
 | `trace` | ✅ | ✅ TraceExplorer | ✅ | ✅ searchTrace/getTraceNode/etc |
 | `deep-analysis` | ✅ | ✅ DeepAnalysisSettings | ❌ | ✅ deep-analysis schedule/status |
 | `trace-pipeline` | ✅ | ✅ GraphEnrichmentPipeline | ❌ | ✅ augmentation/epistemic/modules/deepening/knowledge |
 | `graph-structure` | ✅ | ✅ GraphStructurePanel | ❌ (uses legacy `trace-coverage`) | ✅ getTraceCoverage + ignore patterns |

 **Legacy / non-registry panel IDs (should not appear in `PANEL_REGISTRY`):**
 `build`, `roots`, `trace-coverage`, `pinned-files`, `settings`, `graph-engine`.

 **Full Backend ↔ Frontend endpoint coverage (all 35+ endpoints):**
 All canonical endpoints now have typed `ApiClient` methods. Legacy `/api/*` proxy endpoints
 wrapped via `testLLMEndpoint`, `fetchLLMModels`, `testLLMModel`. Global config still uses
 legacy `/api/code-index/config` path (migrate to canonical path when ready).

 **Remaining blockers / tech debt:**
 - [x] App.tsx LLM handlers: migrate from raw `fetch` to typed ApiClient methods (3 handlers) ✅ **DONE**
 - [x] `getGlobalConfig`/`updateGlobalConfig` migrated to `/global/config` ✅ (legacy `/api/code-index/config` deprecated with sunset headers)
 - [x] Dashboard default layout drift: `DEFAULT_LAYOUT` v17 now uses only canonical `PANEL_REGISTRY` IDs ✅
 - [x] Storybook `FullDashboard` drift: now uses `PANEL_REGISTRY` directly with content for all 14 canonical panels ✅
 - [x] Dashboard error UX: `ErrorToast` component wired in `App.tsx` with auto-dismiss ✅
 - [x] AI Models settings: `onHFDownload` wired to `handleDownloadModel` → `api.downloadEmbedding()` ✅
 - [x] Activity heatmap panel: ✅ Registered in `PANEL_REGISTRY`, wired in `useDashboardPanels`, fetches from `/projects/{id}/activity`
 - [ ] Storybook `NodeDetailPanel.stories.tsx` exists but NodeDetailPanel not wired as a dashboard panel
 - [ ] `WatchStatusIndicator.stories.tsx` exists but component not used in dashboard (WatchControlPanel used instead)

 **Build verification:** `tsc --noEmit` ✅ | `vite build` ✅ (6.08s) | backend tests 154 passed, 36 skipped, 0 failed

 ### 2026-02-09: VS Code Extension Implementation (Phase 17)

 **What was built:**
 - **Extension Host (`packages/vscode/src/`)**: Daemon-backed architecture.
   - `DaemonManager`: Auto-starts `prep serve`, polls health, manages connection state.
   - `PrepDaemonClient`: Typed HTTP client for all daemon endpoints.
   - `StatusBarManager`: Persistent status item with tier/connection info.
   - **Commands**: 18 commands covering Project CRUD, Search, Context, Build, Trace, Licensing.
 - **WebViews (`packages/vscode/webview-ui/`)**: React + Vite + Tailwind pipeline.
   - `SearchResults`: Interactive results list.
   - `ContextPreview`: Assembled context with copy button.
   - `TracePanel`: Pro feature upsell / results view.
 - **Tree Views**:
   - `Projects`: Manage projects, auto-select based on active file.
   - `FileTree`: Browse indexed files.
   - `IndexStatus`: View chunks, model, build status, staleness.

 **Verification:**
 - Builds cleanly (`npm run build` in `packages/vscode` triggers `webview-ui` build then `esbuild`).
 - React assets packaged into `dist/webview`.
 - CSP enabled for WebViews.

 ### 2026-02-08 (continued): Comprehensive Loose Threads Audit

 #### Critical: CLI Bugs (5 runtime crashes)

 `src/prep/cli.py` — three commands reference `project_id` which is **not a function parameter**,
 causing `NameError` at runtime when the server is reachable:
 - [x] **BUG** `activity` command: `_resolve_project(base, project_id)` — `project_id` undefined. **Fixed:** added `--project/-p` param.
 - [x] **BUG** `coverage` command: `_resolve_project(base, project_id)` — `project_id` undefined. **Fixed:** added `--project/-p` param.
 - [x] **BUG** `overview` command: `_resolve_project(base, project_id)` — `project_id` undefined. **Fixed:** added `--project/-p` param.

 Two helper functions were called but **never defined** in `cli.py`:
 - [x] **BUG** `_is_server_available(base)` — **Fixed:** implemented as health check (`GET /health`, 3s timeout).
 - [x] **BUG** `_unwrap_envelope(r.json())` — **Fixed:** implemented to extract `data` from `{success, data, error}` envelope.

 Additional fix:
 - [x] `overview` command called `/trace/stats` (non-existent endpoint). **Fixed:** now reuses `status_data["trace"]` from the already-fetched project status.

 #### CLI: Unimplemented Commands ✅ ALL DONE
 - [x] `config` command: **Implemented** ✅ — now calls `GET/PUT /api/code-index/config` with dot-notation key support
 - [x] `coverage` command: fetches from `/projects/{id}/coverage`, falls back to demo data ✅
 - [x] `overview` command: was calling `/trace/stats` (non-existent) — **Fixed:** now reuses `status_data["trace"]`
 - [x] `drift` command: **Implemented** ✅ — shows index drift report (stale files, freshness metrics)
 - [x] `flow` command: **Implemented** ✅ — shows RAG flow visualization (query → retrieval → context)

 #### Backend: TODO Stubs in Production Code ✅ FIXED
- [x] `server.py` — Trace expansion integration implemented in legacy `/api/context` endpoint ✅
  Now uses `get_context_with_trace_expansion()` when `trace_expand=true`, matching project-scoped behavior.
- [x] `mcp_direct.py` — Progress callback implemented for build notifications ✅
  Logs progress at start, end, and every 50 files during builds.

 #### Dead Code ✅ DELETED
- [x] **`server_old.py`** (317 lines) — deleted ✅
- [x] **`api/responses.py`** (227 lines) — deleted ✅

 #### MCP Server: ~~Missing~~ Trace Tools ✅ DONE
`mcp_tools.py` now defines **7 tools**: `prep_status`, `prep_build`, `prep_search`, `prep_context`, plus the three trace tools below.
- [x] Add `prep_trace_search` MCP tool — search trace graph nodes by name/kind ✅
- [x] Add `prep_trace_neighbors` MCP tool — get neighbors for a node ID ✅
- [x] Add `prep_trace_coverage` MCP tool — get trace coverage summary ✅
All three trace tools now proxy to the project-scoped HTTP endpoints in `mcp_server.py`.

 #### Test Coverage Gaps
 - [x] `_deep_merge()` tests added — `tests/test_deep_merge.py` (13 tests, all pass)
 - [ ] No tests for any CLI commands (`cli.py` — 900 lines, 0 test coverage)
 - [ ] No tests for `viz/` module (activity_heatmap, coverage, overview, drift, flow, health, trace, context)
 - [ ] `test_mcp_config_endpoint.py` — pre-existing failure (404 on endpoint), excluded from CI
 - [ ] `test_trust_loop_integration.py` — excluded from runs
 - [x] `test_incremental_rebuild.py::test_deleted_file_not_carried_over` — ✅ **FIXED** (hashlib + direct doc check)

 #### Config Loading Bugfixes (user-applied, 2026-02-08)
 - [x] **Critical fix:** `loadConfig` in App.tsx no longer sets `llmConfigLoaded=true` on error.
   Previously, a failed config load would allow auto-save to trigger with empty/default state,
   **overwriting the server's persisted config**. Now `llmConfigLoaded` stays `false` on error.
 - [x] `PersistenceStatus` component now accepts `onRetry` callback; shows **Retry** button on error.
 - [x] `loadConfig` extracted to `useCallback` so it can be passed as `onRetry` prop.
 - [x] `PUT /api/code-index/config` endpoint now uses `_deep_merge()` instead of `dict.update()`,
   preventing partial updates from overwriting nested keys (e.g., sending `{llm_config: {nested: {...}}}`
   would previously wipe `llm_config.saved_endpoints`).

 #### pyproject.toml Issues ✅ FIXED
- [x] `requires-python = ">=3.11"` — kept as-is (3.11 is intended minimum per classifiers)
- [x] `project.urls` → updated to `github.com/MagneticAnomaly/SourcePrep-MCP` ✅
- [x] `addopts` → removed `--cov` flags that crash pytest without pytest-cov ✅

 #### Wrong Org URL — ~~`anthropics/Prep`~~ ✅ FIXED
All URLs updated to `github.com/MagneticAnomaly/SourcePrep-MCP`:
- [x] `pyproject.toml` lines 71-74 — `project.urls` ✅
- [x] `packages/ui/package.json` line 83 — `repository.url` ✅
- [x] `mcp-server.json` lines 5-6 — `homepage` + `repository` ✅
- [x] `.venv/*/dist-info/METADATA` — auto-fixed on next `pip install -e .`

 #### Environment Variables — Undocumented
 Two env vars are used in code but not documented in README or any user-facing docs:
 - [ ] `PREP_ENGINE` — selects engine: `auto` (default), `rust`, `python` (`core/__init__.py`) WE ALWAYS USE RUST,  I don't know why we still have the python engine
 - [ ] `PREP_TIER` — overrides license tier for development/testing (`core/feature_gate.py`)
 Document these in README.md or a configuration reference.

 #### Security Posture (local-first, acceptable for now)
 - `allow_origins=["*"]` CORS — fine for localhost, **must restrict for network/team mode** (Phase 06) TODO BUILD RESERACH DOC 
 - No authentication on any endpoint — planned for Phase 06 network mode
 - API keys passed in LLM proxy request bodies — acceptable for local, never stored server-side
 - File content endpoint (`/projects/{id}/file`) properly rejects path traversal (`..`) ✅

 #### Phase Doc Coverage — Untracked Open Work

 **Phase 07 (Polish & Testing) — ~~CRITICAL: Entirely open~~ Materially complete (S-14):**
 - [x] P07-R1/R2/R3: Research (test suite definition, perf targets, mock strategy) ✅
 - [x] P07-I1-I3: Error taxonomy + actionable messaging ✅ `docs/ERROR_CODES.md` + `ApiException`
 - [x] P07-I4-I6: Recovery behaviors (interrupted build, corruption, disk pressure) ✅
 - [x] P07-I7-I8: Observability (per-project logs, diagnostics bundle) ✅ SSE log console + progress bars
 - [x] P07-I9-I12: Test harness (fixture strategy, integration tests, failure injection, gold queries) ✅
 - [x] P07-I13-I14: Performance benchmarks ✅

 **Phase 05 (MCP) — ~~4 open items remaining~~ All complete (S-16):**
 - [x] P05-R5: Streamable HTTP transport ✅ Done in S-16.1
 - [x] P05-R7: Async Tasks for `prep_build` ✅ Done in S-16.2
 - [x] P05-R9: Tool icons (`_meta.icons`) ✅ Done in S-16.4
 - [x] P05-I19: PyPI package verification for MCP Registry ✅ Done in S-16.3

 **Phase 06 (Team & Enterprise) — All implementation open:**
 - [ ] P06-I1-I3: Shared team config (schema done in `team_config.py`, but merge precedence and
   provenance reporting not implemented)
 - [ ] P06-I4-I6: Embedded mode (layout defined, but incompatibility detection + watch-loop
   avoidance not implemented)
 - [ ] P06-I7-I9: Network mode (auth requirement, header standardization, redaction rules)
 - [ ] P06-T1-T3: All tests open

 **Phase 08 (Tauri MVP) — Mostly complete:**
- [x] P08-I1/I2/I3: Sidecar lifecycle — `Prep.app` builds with PyInstaller sidecar ✅
- [x] P08-I4/I6: Port 8400 check + health check attach-or-launch ✅
- [x] P08-I7/I8: StartupScreen with 30s health poll + error/retry/quit ✅
- [x] P08-T1: Basic sidecar launch test ✅
- [ ] P08-I5: Dynamic port fallback if 8400 occupied by non-Prep process
- [ ] P08-T2/T3: Port conflict and crash recovery integration tests

 **Phase 11 (Deployment) — All open:**
 - [ ] P11-I1-I3: Distribution artifacts (macOS, Windows, enterprise)
 - [ ] P11-I4-I5: Offline mode guarantees
 - [ ] P11-I6-I8: Licensing enforcement (partially addressed by `feature_gate.py`)
 - [ ] P11-I9-I10: Upgrade safety

 **Phase 15 (Modular Design) — Nearly complete:**
 - [x] Sprints 1-6: All implemented and integrated
 - [ ] Sprint 7: Documentation stories (`Introduction.mdx` not created)
 - [ ] Definition of Done checklist: verify all items pass

 **Phase 17 (VS Code Extension) — Future work, ~45 items:**
 - All 6 sprints open. Dependencies: license endpoint (exists), signed binaries (not yet),
   Lemon Squeezy activation (not yet).

 #### Settings Panel — Missing UI Primitives
 Per `docs/Phase02_Dashboard/SETTINGS_TODO.md`:
 - [ ] `ToggleSwitch` — currently inline in `ProjectSettingsPanel`, needs extraction
 - [ ] `NumberField` — with min/max, unit, validation
 - [ ] `TagListEditor` — for include/exclude glob editing
 - [ ] `BudgetPill` — for `max_chars`, `max_nodes` display
 - [ ] `BudgetPreview` — estimated chars/tokens preview
 - [ ] `ConfigProvenanceRow` — show source: default/global/team/project
 - [ ] `CopyDiagnosticsButton` — version/OS/config/error snapshot

 #### Core Modules — Clean ✅
 All audited with no TODOs or stubs:
 - `core/index.py` (1095 lines) — hybrid semantic+keyword search
 - `core/embedder.py` (313 lines) — Ollama, Native, Fake providers
 - `core/compressor.py` (247 lines) — LinguaCompressor + Noop
 - `core/chunking.py` (274 lines) — markdown + code chunking
 - `core/trace.py` (40k+ lines) — trace builder + index
 - `core/project_registry.py` (234 lines) — SQLite registry
 - `core/team_config.py` (155 lines) — team config loader
 - `core/feature_gate.py` (5.9k) — 5-tier gating, 11 features
 - `core/watcher.py` (11.6k) — debounced file watching
 - `core/repo_policy.py` (5.3k) — include/exclude policy
 - `core/repo_profile.py` (6.3k) — file classification + role weights
 - `mcp_config.py` (93 lines) — 5 IDE config generators

 #### Dashboard Vite Proxy — ~~Missing Routes~~ ✅ FIXED
 `src/prep/dashboard/vite.config.ts` now proxies **all 7 prefixes** to the daemon at `127.0.0.1:8400`:
 `/api`, `/projects`, `/health`, `/llm`, `/license`, `/embedding`, `/compression`.
 - [x] `/embedding/*` — ✅ proxy added
 - [x] `/compression/*` — ✅ proxy added (replaces the removed sidecar route)
 - [x] `/license` — ✅ proxy added (vite.config.ts lines 90-94)

 #### ~~Legacy Endpoints Incompatible with Multi-Project~~ ✅ DELETED
 All legacy `/api/code-index/*` endpoints have been deleted:
 - [x] `POST /api/code-index/context` — **DELETED** (use `/projects/{id}/context`)
 - [x] `POST /api/code-index/chunk` — **DELETED** (use `/projects/{id}/search`)
 - [x] `GET/PUT /api/code-index/config` — **DELETED** (use `/global/config`)
 - [x] `GET /api/code-index/mcp-config` — **MOVED** to `/mcp/config`
 - [x] CLI `config` command migrated to `/global/config`
 - [x] VS Code client migrated to `/mcp/config`
 - [x] Tests migrated to `/mcp/config`

 #### Dead Code: `api/responses.py` (227 lines)
 `src/prep/api/responses.py` defines `APIException`, `ErrorCode`, typed error subclasses
 (`ProjectNotFoundError`, `BuildAlreadyRunningError`, `OllamaUnavailableError`, etc.) and
 `register_exception_handlers()` — but is **never imported** by any module. The server uses
 `api/envelope.py` exclusively (which defines `ApiException`, `ok()`, `fail()`).
 - [ ] Either consolidate `responses.py` typed errors into `envelope.py` (better DX), or delete it.
   The typed error subclasses are a good pattern — consider adopting them in `envelope.py`.

 #### Updated Priority Summary (after Round 2)
 | Priority | Category | Count | Status | Description |
 |---|---|---|---|---|
 | ~~**P0**~~ | ~~CLI bugs~~ | ~~6~~ | ✅ **FIXED** | ~~Runtime crashes~~ |
 | ~~**P0**~~ | ~~Config safety~~ | ~~1~~ | ✅ **FIXED** | ~~`_deep_merge` tests~~ |
 | ~~**P0**~~ | ~~Eval runner bug~~ | ~~1~~ | ✅ **FIXED** | ~~`embedder.encode()` → `embed()`~~ |
 | ~~**P0**~~ | ~~`/llm/test` bug~~ | ~~1~~ | ✅ **FIXED** | ~~LLM connectivity hardcoded `False`~~ |
 | **P1** | API docs gaps | 13 | ✅ **FIXED** | Undocumented server endpoints |
 | **P1** | Phase 07 (Testing) | 14 | Open | Entire phase unstarted — MVP quality bar |
 | **P1** | Test coverage | 2 | Open | CLI (900 lines), viz (8 files) untested |
 | ~~**P1**~~ | ~~pyproject.toml~~ | ~~3~~ |  **FIXED** | ~~Wrong URLs, Python version, pytest-cov~~ |
 | ~~**P1**~~ | ~~Legacy endpoints~~ | ~~3~~ |  **DEPRECATED** | ~~`/api/code-index/*`~~ → deprecation warnings added |
 | ~~**P1**~~ | ~~Dashboard error UX~~ | ~~1~~ |  **FIXED** | ~~`_error` state~~ → ErrorToast component wired |
 | ~~**P2**~~ | ~~Dead code~~ | ~~2~~ |  **DELETED** | ~~`server_old.py` + `api/responses.py`~~ |
 | ~~**P2**~~ | ~~Endpoint cleanup~~ | ~~3~~ | ✅ **OK** | ~~Duplicate trace endpoints~~ → intentional aliases |
 | ~~**P2**~~ | ~~UX renames~~ | ~~9~~ | ✅ **DONE** | Panel registry updated: Knowledge Base Status, AI Gateway, Knowledge Query, Context Assembler, Retrieved Context, Prompt Buffer, Live Sync, Knowledge Sources, Code Graph Explorer |
 | ~~**P2**~~ | ~~Frontend client gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`/llm/test`~~ → `testLLMConnectivity()` added |
 | ~~**P2**~~ | ~~Env var docs~~ | ~~2~~ |  **FIXED** | ~~`PREP_ENGINE`, `PREP_TIER`~~ → documented in README |
 | ~~**P2**~~ | ~~Settings primitives~~ | ~~7~~ | ✅ **DONE** | SettingsSection, SettingsRow, TagListEditor, BudgetPill, BudgetPreview — all exported from @prep/ui |
 | **P3** | Phase 06/08/11 | ~30 | Open | Team, Tauri, Deployment (post-MVP) |
 | **P3** | Phase 17 | ~45 | Open | VS Code extension (future) |
 | ~~**P3**~~ | ~~Website builds~~ | ~~1~~ | ✅ **OK** | `turbo.json` `^build` dependency ensures @prep/ui builds first |

 ### 2026-02-12: Master TODO Audit & Expansion

**What changed:**
- **Audit completed:** Verified status of Phase 14 (UI/UX), Phase 15 (Modular Dashboard), Phase 17 (VS Code), and Phase 18 (Data Viz).
- **New Sprints defined:** Added S-14 through S-21 to explicitly track work that was previously implicit or buried in phase docs.
  - S-14: QA & Polish (Phase 07)
  - S-15: Monetization Plumbing (Phase 11)
  - S-16: MCP Maturity (Phase 05)
  - S-17: VS Code MVP (Phase 17)
  - S-18: Data Visualization (Phase 18)
  - S-19: Support Strategy (Phase 20)
  - S-20: Modular Dashboard (Phase 15)
  - S-21: UI/UX Improvements (Phase 14)
- **Completed items marked:**
  - S-08 (Public Docs / Design System) marked complete.
  - S-00.2 (Phase 02 Research) marked complete.
  - S-20 (Modular Dashboard) implementation marked complete (docs pending).
  - S-21 (UI/UX) marked complete.
  - S-17 (VS Code) implementation marked complete (polish pending).

**Priorities updated:**
- **Immediate:** Close S-20.4 (Storybook docs) and S-17.4 (VS Code polish).
- **Next:** S-15 (Monetization) and S-14 (QA/Polish) are critical for release.

### 2026-02-09: Deep Audit — Round 3

 #### Items Closed (verified as fixed)

 **Vite Proxy — all routes now proxied ✅**
 `src/prep/dashboard/vite.config.ts` lines 90-104 now include `/license`, `/embedding/*`,
 and `/compression/*` proxy rules. All endpoint prefixes reach the daemon in dev mode.

 **App.tsx LLM handlers — fully migrated ✅**
 All 3 handlers (`handleTestEndpoint`, `handleFetchModels`, `handleTestModel`) now use typed
 `ApiClient` methods. The remaining tech debt item on line 687 was stale and has been marked done.

 #### NEW: License Activation Exchange — NOT_IMPLEMENTED
 `server.py:990` — `POST /license/activate` exists but returns `NOT_IMPLEMENTED` error for the
 full Lemon Squeezy activation exchange flow. It currently only accepts:
 - Direct JSON license payload
 - Tier name string (`free`/`starter`/`pro`/`team`/`enterprise`)
 - Base64url-encoded JSON token
 The planned flow (user enters LS key → exchange via `api.sourceprep.io` → signed Ed25519 offline
 license) is **not implemented**. This blocks the full licensing story.
 - [ ] Implement Lemon Squeezy activation exchange in `POST /license/activate`
 - [ ] Wire `api.sourceprep.io` relay service for key → license exchange
 - [ ] Ed25519 signature verification in license loader (already tracked)

 #### NEW: Payments Recovery Route — Mock Stub
 `websites/apps/payments/src/app/api/recover/route.ts:14` has:
 ```
 // TODO: Integrate with Lemon Squeezy API to find orders by email
 // and trigger license key resend or return keys.
 // For now, we simulate a success to unblock the UI flow.
 ```
 The endpoint returns a hardcoded success response. Blocks real license recovery.
 - [ ] Integrate `POST /api/recover` with Lemon Squeezy order lookup API

 #### ~~NEW: Dashboard Error Toast — Unwired~~ ✅ ALREADY WIRED
 `src/prep/dashboard/src/App.tsx`:
 - `ErrorToast` component defined (lines 163-178) with auto-dismiss after 5s
 - `_error` state set in 10+ catch blocks throughout the file
 - Rendered at bottom of JSX: `{_error && <ErrorToast message={_error} onDismiss={() => setError(null)} />}`
 - [x] Error toast is fully wired and functional ✅

 #### ~~NEW: viz Module — Not Exported / Not Wired~~ ✅ FIXED
 ~~`src/prep/viz/__init__.py` exports 7 functions but **2 viz modules are orphaned**:~~
 - [x] `render_drift_report` (`viz/drift.py`) — exported from `__init__.py` ✅, CLI `prep drift` added ✅
 - [x] `render_rag_flow` (`viz/flow.py`) — exported from `__init__.py` ✅, CLI `prep flow` added ✅
 All viz modules now exported and wired to CLI commands.

 #### ~~NEW: MockApiClient — 38 Stub Methods~~ ✅ FIXED
 ~~`packages/ui/src/api/mock.ts` — all 38 methods throw `"not implemented"` errors.~~
 **All methods now return realistic mock data for Storybook demos.**
 - [x] Implemented mock data returns for all methods including `getHealth`, `listProjects`,
   `getProjectStatus`, `search`, `assembleContext`, `testLLMConnectivity`, and more ✅

 #### NEW: Phase TODO Docs — Stale (reconciliation needed)

 **Phase 03 (`Phase03_AutoRebuild/TODO.md`) — entirely stale:**
 All 20+ items marked `[ ]` but most are **already implemented**:
 - Watcher service: ✅ `core/watcher.py` (11.6k lines)
 - Storm control (debounce/throttle): ✅ implemented
 - Hash-based change detection: ✅ `manifest.json` file_hashes
 - Atomic rebuild: ✅ `CodeIndex._swap_index_dir()`
 - Watch status fields: ✅ `stale`, `stale_since`, `pending_paths_count`, etc.
 - Tests: ✅ `test_watcher_staleness.py` (9 tests), `test_incremental_rebuild.py` (7 tests)
 - [x] **ACTION:** Update Phase 03 TODO.md to reflect actual implementation state ✅ DONE

 **Phase 01 (`Phase01_Foundation/TODO.md`) — cross-phase refs stale:**
 Lines 64-68 reference STR-01 through STR-05 as `[ ]` but all are ✅ implemented.
 Open items P01-R3 (FTS detection), P01-R5 (perf envelope), P01-I8 (search during build),
 P01-U1/U2 (unification) are genuinely open.
 - [x] **ACTION:** Update Phase 01 TODO.md cross-phase strategy checkboxes ✅ DONE

 **Phase 07 (`Phase07_Polish_Testing/TODO.md`) — cross-phase refs stale:**
 Lines 56-58 reference STR-01, STR-04, STR-05 as `[ ]` but all are ✅ implemented.
 Also has cross-cutting gap about `envelope.py` vs `responses.py` duplication (line 26) —
 this overlaps with the existing dead code item in MASTER_TODO.
 - [x] **ACTION:** Update Phase 07 TODO.md cross-phase strategy checkboxes ✅ DONE

 **Phase 17 (`Phase17_VSC-plugin/TODO.md`) — ✅ dependencies table updated:**
 All daemon endpoints now marked ✅ Exists. Remaining ❌ items are genuine gaps:
 - `api.sourceprep.io` activation exchange endpoint (P1 License activation)
 - Lemon Squeezy product + activation limits (P2 Payments recovery)
 - Signed Prep binaries on PATH (dev-only, not blocking)
 - [x] **ACTION:** Update Phase 17 TODO.md dependencies table ✅ DONE

 #### NEW: Phase 15 — Open Items
 `docs/Phase15_modular-design/TODO.md` has remaining open items:
 - [ ] Sprint 7: `Introduction.mdx` documentation story not created
 - [ ] Sprint 3.2: `DashboardGrid.stories.tsx` not created (covered by ModularDashboard)
 - [ ] Definition of Done checklist (lines 161-170) — not formally verified
 - [ ] Future: multi-column layouts, sidebar panels, server-side layout sync

 #### Reconciliation: Items Already Tracked (no change needed)
 The following items were found during the scan and are **already tracked** in MASTER_TODO:
 - `cli.py:725-734` — `config` command prints "Not implemented yet" (3 TODOs) → tracked as "CLI config stub"
 - `server.py:2630` — trace expansion `pass` no-op → tracked as "Backend stubs"
 - `mcp_direct.py:164` — progress callback TODO → tracked as "Backend stubs"
 - `commands.ts:315` — VS Code pin/unpin TODO → tracked under Phase 17
 - `server_old.py` — 14 TODOs, all NOT_IMPLEMENTED stubs → tracked as "Dead code"
 - Rust engine crates — **zero TODOs** found, confirmed clean ✅

 #### Updated Priority Summary (after Round 3)
 | Priority | Category | Count | Status | Description |
 |---|---|---|---|---|
 | ~~**P0**~~ | ~~CLI bugs~~ | ~~6~~ | ✅ **FIXED** | ~~Runtime crashes~~ |
 | ~~**P0**~~ | ~~Config safety~~ | ~~1~~ | ✅ **FIXED** | ~~`_deep_merge` tests~~ |
 | ~~**P0**~~ | ~~Eval runner bug~~ | ~~1~~ | ✅ **FIXED** | ~~`embedder.encode()` → `embed()`~~ |
 | ~~**P0**~~ | ~~`/llm/test` bug~~ | ~~1~~ | ✅ **FIXED** | ~~LLM connectivity hardcoded `False`~~ |
 | ~~**P0**~~ | ~~Vite proxy~~ | ~~3~~ | ✅ **FIXED** | ~~`/embedding`, `/compression`, `/license` now proxied~~ |
 | **P1** | License activation | 3 | **NEW** | Exchange flow NOT_IMPLEMENTED, Ed25519, relay service |
 | ~~**P1**~~ | ~~API docs gaps~~ | ~~13~~ | ✅ **FIXED** | ~~Undocumented server endpoints~~ → added to API.md |
| ~~**P1**~~ | ~~Backend stubs~~ | ~~2~~ | ✅ **FIXED** | ~~Trace expansion no-op, progress callback~~ |
| ~~**P1**~~ | ~~MCP gaps~~ | ~~3~~ | ✅ **DONE** | ~~No trace tools in MCP~~ → 3 trace tools added |
| **P1** | Phase 07 (Testing) | 14 | Open | Entire phase unstarted — MVP quality bar |
| **P1** | Test coverage | 2 | **Partial** | CLI (900 lines), viz (8 files) untested; +24 new tests: `test_pipeline_budget.py` (15), `test_embedder_factory.py` (9) |
| ~~**P1**~~ | ~~pyproject.toml~~ | ~~3~~ |  **FIXED** | ~~Python version, pytest-cov crash, wrong org URL~~ |
| ~~**P1**~~ | ~~Wrong org URL~~ | ~~3~~ |  **FIXED** | ~~`anthropics/Prep`~~ → `MagneticAnomaly/SourcePrep` |
| ~~**P1**~~ | ~~Legacy endpoints~~ | ~~3~~ |  **DEPRECATED** | ~~`/api/code-index/*`~~ → deprecation warnings added |
 | ~~**P1**~~ | ~~Dashboard error UX~~ | ~~1~~ |  **FIXED** | ~~`_error` state~~ → ErrorToast component wired |
 | ~~**P2**~~ | ~~Dead code~~ | ~~2~~ |  **DELETED** | ~~`server_old.py` + `api/responses.py`~~ |
| **P2** | Endpoint cleanup | 3 | **OK** | Duplicate trace endpoints → intentional aliases |
| ~~**P2**~~ | ~~UX renames~~ | ~~9~~ | ✅ **DONE** | All panel titles updated in `panelRegistry.ts` |
| ~~**P2**~~ | ~~Frontend client gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`/llm/test`~~ → `testLLMConnectivity()` added |
| ~~**P2**~~ | ~~Env var docs~~ | ~~2~~ | ✅ **FIXED** | ~~`PREP_ENGINE`, `PREP_TIER`~~ → documented in README |
 | **P2** | Settings primitives | 7 | Open | Missing form/budget/diagnostics components |
 | ~~**P2**~~ | ~~MockApiClient~~ | ~~1~~ | ✅ **FIXED** | ~~38 stub methods~~ → all methods now return mock data |
 | ~~**P2**~~ | ~~viz module gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`drift` + `flow`~~ → exported + CLI commands added |
| ~~**P2**~~ | ~~Missing exports~~ | ~~2~~ | ✅ **FIXED** | ~~team + viz components~~ → added to packages/ui/index.ts |
| ~~**P2**~~ | ~~Dead CLI file~~ | ~~1~~ | ✅ **DELETED** | ~~`cli_new.py` (542 lines)~~ → removed |
 | **P2** | Payments recovery | 1 | **NEW** | Mock stub, needs Lemon Squeezy integration |
 | ~~**P2**~~ | ~~Phase doc staleness~~ | ~~4~~ |  **FIXED** | ~~Phase 01/03/07 TODOs~~ → reconciled with implementation |
 | ~~**P2**~~ | ~~Phase 15 open items~~ | ~~3~~ | ✅ **DONE** | ~~Sprint 7 docs, DashboardGrid story, DoD checklist~~ → all verified complete |
 | ~~**P1**~~ | ~~Trace graph empty~~ | ~~4~~ | ✅ **FIXED** | ~~Python fallback 0 edges~~ → JSAnalyzer + degraded detection + UX banner |
 | ~~**P1**~~ | ~~Phase 24 SM-1~~ | ~~1~~ | ✅ **DONE** | ~~Phase D (useDashboardPanels)~~ — already had domain grouping. useProjectManager extracted, self-hydration done |
 | ~~**P2**~~ | ~~Phase 26 (Deep Enrichment Settings)~~ | ~~5~~ | ✅ **DONE** | SlidingSwitch3 + mode sync + auto-chain + tier gating all implemented |
 | ~~**P2**~~ | ~~Phase 27.2/27.3~~ | ~~7~~ | ✅ **DONE** | ReportStore abstraction, CRUD APIs, admin dashboard with auth, filters, metrics |
 | ~~**P2**~~ | ~~Phase 23 backend~~ | ~~1~~ | ✅ **DONE** | server.py 4,352→313 lines (−93%), all routers + services extracted |
 | **P3** | Phase 06/08/11 | ~32 | Open | Team, Tauri, Deployment (post-MVP); Phase 08 mostly done (P08-I5/T2/T3 remain) |
 | **P3** | Phase 17 | ~45 | Open | VS Code extension (future) |
 | ~~**P3**~~ | ~~Website builds~~ | ~~1~~ | ✅ **OK** | `turbo.json` `^build` dependency ensures @prep/ui builds first |

 ### 2026-02-12: Cross-Reference Graph — Empty Graph Bug + UX Clarity

 **Symptom:** The Cross-Reference Graph panel shows `670 symbols · 0 edges` for a TypeScript
 project. Selecting any node shows `← 0 in → 0 out`. The graph is technically "working" but
 provides zero useful information — every node is an island with no connections.

 **Root cause (data bug):** The Python trace fallback (`src/prep/core/trace.py` line 498)
 only runs `PythonAnalyzer` for `.py` files. For all other languages (TypeScript, JavaScript,
 Go, Rust, Java, C, C++) the `else` branch at line 526 just increments `files_parsed` without
 extracting any symbols or edges. Result: file nodes are created (670 of them) but zero
 `contains`, `imports`, or `calls` edges exist. The Rust engine (`prep_engine` via PyO3)
 handles all 8 languages correctly, but if it's not installed the Python fallback silently
 produces a degenerate graph.

 **Impact:** Any project that isn't pure Python gets a useless trace graph when using the
 Python fallback. This is the most common scenario for new users who haven't built the Rust
 engine from source.

 **Action items:**
 - [x] **P1 — Backend: Detect and warn on degenerate trace graph.** ✅
   `TraceIndex.status()` now returns `degraded: true` + `degraded_reason` when nodes > 0 but edges == 0.
   Reason varies by engine: Python fallback warns about limited language support; Rust suggests rebuild.
 - [x] **P1 — Frontend: Show informational banner when graph is degraded.** ✅
   `TraceExplorer` shows amber warning banner when `edges === 0 && nodes > 0`.
   Message explains Python fallback limitation and suggests Rust engine install.
 - [x] **P1 — UX: Clarify "← 0 in → 0 out" display.** ✅
   Labels now read "X references in" / "X dependencies out" with title-attribute tooltips
   explaining callers/importers (in) and calls/imports (out).
 - [x] **P2 — Backend: Add basic TS/JS import extraction to Python fallback.** ✅
   `JSAnalyzer` class added to `trace.py`: regex-based extraction of ES imports, CommonJS require,
   dynamic imports, re-exports, and symbols (functions, classes, interfaces, types, enums, exports).
   Relative imports resolve to file nodes. 17 tests in `tests/test_js_analyzer.py`.
 - [x] **P2 — UX: Rename panel.** "Cross-Reference Graph" is vague. Renamed to "Code Graph" (and "Graph Status") to immediately communicate what connections mean. The "(i)" tooltip now explains: *"Shows how files and symbols in your codebase are connected through imports, function calls, and class inheritance."*

### 2026-02-12: Settings Drawer Refactor (S-22)

**Goal:** Clean separation of project-level and global settings; remove stale dashboard panels.

 **What was done:**
- **SettingsDrawer refactored** to two tabs: **Project** (ProjectSettingsPanel + DeepAnalysisSettings) and **Global** (Appearance, Background Image, Connection Debugger).
- **Panels removed from `panelRegistry.ts`:** `roots`, `deep-analysis` (previously removed: `file-tree`, `pinned-files`, `settings`).
- **App.tsx cleanup:** Removed all Pinned Files logic (`handlePinFile`, `handleUnpinFile`, `pinnedPaths`, `pinnedFiles`, `PINNED_PREFIX`, `dynamicPanelDefs`), File Tree state (`fileTree`, `includedPaths`, `setFileTree`, `setIncludedPaths`, `handleToggleInclude`, `handleLoadChildren`, `handleLoadFileContent`, `collectIndexedPaths`), and `handlePanelClose` pinned-file dispatching.
- **DeepAnalysisSettings** integrated into SettingsDrawer Project tab (was previously only in `panelContent`/`panelDetails` grid panels).
- **Fixed syntax error** at line 838 caused by a broken/duplicate `handleDeepAnalysisRun` callback from a previous failed edit.
- **Fixed bare JS comment** (`// ── Global tab ──`) that should have been a JSX comment.
- **Unused imports removed:** `Pin`, `CopyButton`, `PanelDefinition`, `TreeNode`, `FolderTree`.
- **Panel audit table updated** in MASTER_TODO.md (14 panels → 11 panels).

### 2026-02-14: Dashboard Panel ID Drift (DEFAULT_LAYOUT vs Registry vs App vs Storybook)

#### ~~`DEFAULT_LAYOUT` still references legacy/orphaned panel IDs~~ ✅ ALREADY FIXED

`DEFAULT_LAYOUT` (version 17) now uses only canonical `PANEL_REGISTRY` IDs. All legacy IDs (`build`, `trace-coverage`, `roots`, `pinned-files`) have been removed. `graph-structure` is included.

- [x] Align `DEFAULT_LAYOUT` panel IDs to the canonical `PANEL_REGISTRY`. ✅
- [x] Layout migration removes orphaned panel IDs. ✅
- [x] First-run dashboard experience verified. ✅

#### ~~Storybook `FullDashboard` uses non-canonical IDs~~ ✅ ALREADY FIXED

`FullDashboard.stories.tsx` now uses `PANEL_REGISTRY` directly and supplies `panelContent` for all 14 canonical panel IDs: `usage-guide`, `status`, `llm-status`, `search`, `context-options`, `results`, `context-output`, `file-tree`, `watch`, `trace`, `graph-structure`, `trace-pipeline`, `deep-analysis`, `log-console`.

- [x] Update `FullDashboard` story to use canonical panel IDs. ✅
- [x] Story supplies content for every panel in `PANEL_REGISTRY`. ✅

#### ~~Dashboard Error Toast appears to be unwired~~ ✅ ALREADY FIXED

`ErrorToast` component exists at `src/prep/dashboard/src/components/ErrorToast.tsx`. It is imported and rendered in `App.tsx` line ~847: `<ErrorToast message={error} onClose={() => setError(null)} />`. Auto-dismisses after 5s with fade animation.

- [x] Error Toast is fully wired and functional. ✅

#### ~~HuggingFace model download UI is a no-op~~ ✅ ALREADY FIXED

`useLLMConfig.ts` defines `handleDownloadModel` which calls `api.downloadEmbedding()`. This is passed through `useDashboardPanels.tsx` as `onHFDownload={p.handleDownloadModel}` to `AIModelsSettings`.

- [x] `onHFDownload` wired to `ApiClient.downloadEmbedding()`. ✅

#### ~~NEW: Analytics TODO placeholders in all website app layouts~~ ✅ DONE

All four Next.js sites now use Plausible via `<Script strategy="afterInteractive" />`:
- [x] `websites/apps/marketing/src/app/layout.tsx` — `data-domain="sourceprep.io"` ✅
- [x] `websites/apps/docs/src/app/layout.tsx` — `data-domain="docs.sourceprep.io"` ✅
- [x] `websites/apps/support/src/app/layout.tsx` — `data-domain="support.sourceprep.io"` ✅
- [x] `websites/apps/payments/src/app/layout.tsx` — `data-domain="payments.sourceprep.io"` ✅

**Note:** Plausible account + site setup still required. Script loads but won't report until sites are registered at plausible.io.

#### ~~Deprecated `GraphEnginePanel` still exported~~ ✅ ALREADY FIXED

`GraphEnginePanel` component and its exports have been fully removed from `packages/ui`.

- [x] Deprecated exports removed. ✅

### 2026-02-14: Pinned Files feature (Dashboard)

**What was built:**
- **Backend**: Added `GET /projects/{id}/file?path=...` endpoint with safety checks (traversal, globs, max_bytes).
- **UI**: Added `FolderTreePanel` (browsable tree) and `PinnedTextFilesPanel` (content viewer).
- **State**: Persisted pinned paths in `localStorage`.
- **Integration**: Wired into `App.tsx` and Storybook.

### 2026-02-15: Folder Selection Fixes & Status UX Polish

**What was done:**
- **Folder Tree Selection Logic:** Fixed bug where selecting a parent folder didn't visually select loaded children due to strict path matching.
  - Implemented `isPathOrAncestorIncluded` helper in `FolderTree.tsx`.
  - Children now properly inherit "selected" state if *any* ancestor path is in `includedPaths`.
  - Fixed `handleToggleInclude` to clean up orphaned descendants in `includedPaths` (localStorage) when a parent is unchecked.
  - Added one-time `localStorage` migration (v2) to clear stale orphaned paths from previous buggy behavior.
- **Index Status UX:**
  - **Transient "Build Complete" State:** Progress bar now stays at 100% (green) for 5 seconds after build completion before reverting to the status controls.
  - **Graph in Distribution Chart:** Added "Graph" segment (purple) to the "Code vs Docs" bar in `IndexStatusCard`.
  - **Smart Unit Switching:** If trace graph chunks exist, the distribution chart automatically switches unit from "files/lines" to "chunks" to allow apples-to-apples comparison of Code/Docs/Graph.

**Files changed:**
- `packages/ui/src/components/project/FolderTree.tsx` — selection logic
- `packages/ui/src/components/dashboard/IndexStatusCard.tsx` — graph stats + hideChart prop
- `src/prep/dashboard/src/App.tsx` — toggle handler + transient state logic

### 2026-02-15: Dashboard UI Refinements — Progress Bars, Coverage Panel, Trace Robustness

**What was done:**

*Graph Enrichment Pipeline — Per-Stage Progress Bars:*
- `StageProgressBar` (`packages/ui/src/components/trace/StageProgressBar.tsx`): `progress` prop is now optional. When `undefined`, renders an **indeterminate shimmer** animation (1/3-width bar sliding back and forth via CSS `animate-indeterminate`).
- `StageRow` in `GraphEnrichmentPipeline.tsx`: Now shows a progress bar for **all** running stages, replacing the status text (e.g., "Augmenting..."). Stages with percentage data (Catalogue, Epistemic, Deepening) show a **determinate** bar with `%` label. Stages without (Structural, Validation, Knowledge, Clustering, Deep Knowledge) show an **indeterminate** shimmer bar.
- `tailwind.config.js`: Added `indeterminate` keyframe animation (`translateX -100% → 400%`, 1.5s ease-in-out infinite).
- Bar is `h-1.5` (6px) inside an `h-[13px]` container, matching text line height — **no layout shift**.

*Trace Coverage Panel — Embedding Status Distinction:*
- **Backend**: `compute_trace_coverage()` now accepts `embedded_paths: Optional[Set[str]]` and splits traced files into `traced` (traced & embedded in RAG) and `pending_embedding` (traced but not yet embedded).
- **Backend**: `CodeIndex.get_indexed_file_paths()` added — returns set of file paths with at least one embedded chunk.
- **Backend**: `trace_coverage_project` API endpoint fetches embedded paths from CodeIndex and passes them to coverage computation.
- **Frontend**: `TraceCoverageSummary` and `TraceCoverage` types updated with `pending_embedding` field.
- **Frontend**: `TraceCoveragePanel` updated:
  - "traced" label → "traced & embedded"
  - `pending_embedding` files counted as "in-progress" in the coverage bar
  - Removed `<Clock />` spinner from "Queue" tab (redundant)
  - Progress text: "Mapping full codebase..." (initial) vs "Updating to reflect codebase changes..." (incremental)

*Trace Builder Robustness:*
- `TraceBuilder.build()` now implements **robust sanitization** — filters out invalid nodes and edges instead of aborting the entire build on validation errors. Always writes a partial but valid graph.
- `trace.enabled` is now set to `true` in project config after a successful structural build, preventing the "Initialize Trace Graph" button from reappearing.

**Files changed:**
- `packages/ui/src/components/trace/StageProgressBar.tsx` — indeterminate mode
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — progress bar for all running stages
- `packages/ui/tailwind.config.js` — indeterminate animation keyframe
- `packages/ui/src/components/trace/TraceCoveragePanel.tsx` — embedding status, label changes, spinner removal
- `packages/ui/src/types.ts` — `pending_embedding` field
- `src/prep/core/trace.py` — sanitization + `compute_trace_coverage` embedded_paths
- `src/prep/core/index.py` — `get_indexed_file_paths()`
- `src/prep/api/routers/trace.py` — pass embedded_paths to coverage
- `src/prep/services/pipeline_orchestrator.py` — sets `trace.enabled` on build
- `src/prep/dashboard/src/hooks/useTraceSystem.ts` — completion handler fix

---

## Phase 29 UX Audit — TODO Items (from `Phase29_Website-UX-Audit/`)

### Product / Codebase
- [x] **Embedding model upgrade**: `v2-moe` evaluated in Phase 33 and rejected. `nomic-embed-text-v1.5` ONNX remains the default.
- [x] **Academic terminology audit**: ✅ Completed. User-facing labels renamed: "Epistemic Enrichment" → "Deep Reasoning", "Cluster Synthesis" → "Module Synthesis", "Epistemic Score" → "Understanding Score", "Confidence" → "Understanding" in IndexHealthPanel. Academic terms preserved in italicized descriptions, tooltips, and docs explanations. No API/code field names changed. Full epistemological foundation written in `/concepts/graph-enrichment` docs page. All docs updated to 9-stage pipeline.
- [ ] **Debug log export guide**: Implement a safe "Export Debug Bundle" feature or document a manual process for users to collect logs without leaking source code. Add to FAQ + Troubleshooting. (`src/prep/api/`, docs site)
- [-] **CLI/Dashboard docs toggle**: Design a toggle in the docs site that lets users switch between "Dashboard" and "CLI" instructions for the same task (default: Dashboard). This is a large scope item — create implementation strategy before building. (`websites/apps/docs/`)
- [ ] **`<Badge>Pro</Badge>` component for docs**: Implement a visual badge to tag Pro-only features (auto-rebuild, scheduled enrichment, mcp_trace_expand) in the docs. Clarify the correct free-tier definition in all docs: Free = 1 project + manual only. (`websites/apps/docs/`, `packages/ui/`)
- [ ] **Atlas FAQ entry**: Verify whether Atlas routing actually reduces token usage (pre-retrieval scoping ≠ fewer tokens sent). If confirmed, add FAQ: "What is Codebase Atlas and how does it save tokens?" (`websites/apps/marketing/src/app/faq/`)
- [ ] **Community page definition**: Define what `/community` on the marketing site should be. Scope unknown — may not be MVP. (`websites/apps/marketing/src/app/community/`)

### 2026-02-22: Legacy Endpoint Cleanup + Activity Heatmap Wiring

**What was done:**

*Legacy `/api/code-index/*` endpoints — DELETED:*
- `POST /api/code-index/context` — deleted from `projects.py` (used global singleton `_get_index()`)
- `POST /api/code-index/chunk` — deleted from `projects.py`
- `GET/PUT /api/code-index/config` — deleted from `system.py` (deprecated aliases for `/global/config`)
- `GET /api/code-index/mcp-config` — **moved** to `GET /mcp/config` in `system.py`
- CLI `config` command: migrated from `/api/code-index/config` to `/global/config`
- VS Code client `getMCPConfig()`: migrated from `/api/code-index/mcp-config` to `/mcp/config`
- `tests/test_mcp_config_endpoint.py`: all 5 tests updated to `/mcp/config`
- Vite proxy: added `/mcp` prefix to `vite.config.ts`
- Root endpoint `GET /`: updated `api` field from `/api/code-index/status` to `/projects`

*Activity Heatmap panel — WIRED:*
- `panelRegistry.ts`: `activity-heatmap` panel already registered; added `Flame` icon import
- `useDashboardPanels.tsx`: imported `ActivityHeatmap` + `ActivityHeatmapData`; added `activityData` prop; renders heatmap or empty-state placeholder
- `App.tsx`: added `activityData` state; fetches from `api.getProjectActivity()` on project selection
- `client.ts`: fixed `getProjectActivity` return type from `{ weeks, total_builds }` to `{ days, totals }` matching backend
- `mock.ts`: fixed mock return shape to `{ days: [], totals: { embeddings: 0, trace: 0, builds: 0 } }`
- `FullDashboard.stories.tsx`: added `activity-heatmap` panel content with sample data

*MASTER_TODO updates:*
- Marked upgrade prompts as **WON'T DO** (no upgrade prompts by design)
- Marked UX revamp docs (COMPONENT_AUDIT_V2, DASHBOARD_UX_REVAMP, Bicameral layout, LLM settings modal, FolderTree merge) as **WON'T DO**
- Marked MCP config endpoint test as fixed
- Updated legacy endpoints section to reflect deletion

**Files changed:**
- `src/prep/api/routers/system.py` — deleted deprecated config aliases, moved MCP config to `/mcp/config`
- `src/prep/api/routers/projects.py` — deleted `/api/code-index/context` + `/api/code-index/chunk`
- `src/prep/cli.py` — config command uses `/global/config`
- `packages/vscode/src/client.ts` — uses `/mcp/config`
- `tests/test_mcp_config_endpoint.py` — uses `/mcp/config`
- `src/prep/dashboard/vite.config.ts` — added `/mcp` proxy
- `packages/ui/src/config/panelRegistry.ts` — added `Flame` import (already had entry)
- `packages/ui/src/api/client.ts` — fixed `getProjectActivity` return type
- `packages/ui/src/api/mock.ts` — fixed mock return shape
- `src/prep/dashboard/src/hooks/useDashboardPanels.tsx` — wired `ActivityHeatmap` panel
- `src/prep/dashboard/src/App.tsx` — added activity data state + fetching
- `packages/ui/src/stories/dashboard/FullDashboard.stories.tsx` — added heatmap panel content
