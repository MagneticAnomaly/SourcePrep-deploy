# CoDRAG Master TODO (Cross-Phase Orchestrator)

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
- Phase04: `Phase04_TraceIndex/TODO.md`
- Phase05: `Phase05_MCP_Integration/TODO.md`
- Phase06: `Phase06_Team_And_Enterprise/TODO.md`
- Phase07: `Phase07_Polish_Testing/TODO.md`
- Phase08: `Phase08_Tauri_MVP/TODO.md`
- Phase09: `Phase09_Post_MVP/TODO.md`
- Phase10: `Phase10_Business_And_Competitive_Research/TODO.md`
- Phase11: `Phase11_Deployment/TODO.md`
- Phase12: `Phase12_Marketing-Documentation-Website/TODO.md`
- Phase13: `Phase13_Storybook/TODO.md`
- Phase14: `Phase14_UI_UX_Improvements/README.md`
- Phase15: `Phase15_modular-design/TODO.md`
- Phase16: `Phase16_ContextIntelligence/README.md`
- Phase17: `Phase17_VSC-plugin/TODO.md`
- Phase18: `Phase18_DataVisualization/README.md`
- Phase19: `Phase19_Alt-Dev-Workflows/TODO.md`
- Phase20: `Phase20_support_strategy/README.md`

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
  - 4 tools: codrag_status, codrag_build, codrag_search, codrag_context
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

### Sprint S-04: Trace foundations + bounded expansion
**Goal:** structural grounding that stays small, inspectable, and safe.

- [x] S-04.1 Trace schema + stable IDs + build integration (Phase04/01) ✅
  - Rust engine: `codrag-walker`, `codrag-parser`, `codrag-graph`, `codrag-engine` (41 tests)
  - Python: `TraceBuilder.build()` + `TraceIndex` load/search/neighbors/status
  - 8 language parsers: Python, TS, JS, Go, Rust, Java, C, C++
  - Server: `/projects/{id}/trace/*` endpoints (status, build, search, nodes, neighbors)
- [x] S-04.2 Trace API + dashboard symbol browser (Phase04/02) ✅
  - API endpoints: done (search, node, neighbors, build)
  - `TraceStatusCard` UI component: done
  - `TraceExplorer` symbol browser: done (search, detail pane, neighbor navigation)
  - API client: `searchTrace`, `getTraceNode`, `getTraceNeighbors`, `buildTrace`
  - Panel registered as 'trace' / 'Symbol Browser' in dashboard
- [x] S-04.3 Trace-aware context expansion budgets (Phase04/01/02/05) 
  - `get_context_with_trace_expansion()` in `index.py` — follows trace edges to include related code
  - Server: `trace_expand` + `trace_max_chars` params on `POST /projects/{id}/context`
  - MCP: `trace_expand` param on `codrag` tool
  - Graceful fallback: returns normal context if trace not available

### Sprint S-05: IDE workflows (MCP) 
**Goal:** stable MCP tools with conservative defaults and debuggable project selection.

- [x] S-05.1 MCP stdio server (HTTP proxy) + daemon health behavior (Phase05/01) 
- [x] S-05.2 Tool schemas aligned with `API.md` and dashboard expectations (Phase05/02) 
- [x] S-05.3 Token-efficient output modes (lean-by-default) (Phase05) 
- [x] Implement `codrag` tool (formerly `codrag_context`)

### Sprint S-06: Reliability baseline + evaluation harness
**Goal:** prevent regressions; make failures actionable; define perf envelope.

- [x] S-06.1 Test fixtures + unit/integration test baseline (Phase07/01–05)  `tests/test_trust_loop_integration.py` + `tests/conftest.py`
- [x] S-06.2 Recovery + corruption detection behaviors (Phase07/01)  `tests/test_index_recovery.py` (13 tests)
- [x] S-06.3 "Gold queries" and manual eval loop (Phase07/04/05)  `tests/eval/` (10 gold queries + runner)

### Sprint S-07: Desktop packaging + deployment readiness
**Goal:** Tauri app + sidecar lifecycle + signed distribution path.

- [x] S-07.1 Tauri wrapper + sidecar startup/shutdown + port strategy (Phase08) ✅ **DONE: `CoDRAG.app` builds with PyInstaller sidecar**
- [ ] S-07.2 OS distribution + signing/notarization plan (Phase11)
- [ ] S-07.3 Offline-friendly licensing + feature gating plan (Phase11/07)

### Sprint S-08: Public docs + design system alignment
**Goal:** credible public-facing docs, consistent UI primitives across app + site.

- [x] S-08.1 Getting started + MCP onboarding docs scaffold (Phase12/05)
  - `docs/GETTING_STARTED.md`, `docs/MCP_ONBOARDING.md`, `docs/TROUBLESHOOTING.md`
  - `/guides/*` pages on docs site (embeddings, clara, path weights)
- [x] S-08.2 Visual direction prototypes + token strategy + Storybook baseline (Phase13/02/12)
  - All "Radical" visual directions (Neo-Brutalist, Retro, Glass, etc.) ported to `@codrag/ui`
  - Storybook reorganized (`Dashboard/Widgets`, `Dashboard/Layouts`, `Foundations`)
  - Shared `Button` and `Select` primitives standardized across app + site

### Sprint S-09: Team/enterprise feedback loop (design constraints, post-MVP implementation)
**Goal:** keep enterprise constraints influencing earlier phases without shipping risky surfaces in MVP.

- [ ] S-09.1 Embedded mode + network-mode safety baselines (Phase06)
- [ ] S-09.2 Policy/config provenance UX implications (Phase06/02)

### Sprint S-14: Comprehensive QA & Polish (Phase 07)
**Goal:** MVP quality bar — rigorous testing, error handling, and operational visibility.

- [ ] S-14.1 Test harness expansion (integration tests, failure injection, gold queries)
- [x] S-14.2 Error taxonomy refinement & actionable messaging (Phase07/02) ✅ **DONE: `docs/ERROR_CODES.md` + `ApiException`**
- [ ] S-14.3 Recovery behaviors (interrupted build, corruption, disk pressure)
  - [x] Disk pressure detection (`INSUFFICIENT_SPACE`)
- [ ] S-14.4 Performance benchmarks & optimization

### Sprint S-17: VS Code Extension MVP (Phase 17)
**Goal:** Native VS Code experience powered by the CoDRAG daemon.

- [x] S-17.1 Daemon management & connectivity (auto-start, polling, health checks)
- [x] S-17.2 WebViews Integration (React + Vite + Tailwind pipeline)
  - Search, Context, Trace panels
- [x] S-17.3 Core Commands & Tree Views
  - Project/File management, Index Status, Licensing commands
- [ ] S-17.4 Post-MVP polish (high-res icons, pin file command, chat provider)

### Sprint S-12: Context MVC Verification (Phase 19)
**Goal:** Verify and document "Verified Views" (Gemini CLI, Qwen Code) to enable BYO-View architecture.

- [ ] S-12.1 Verify Gemini CLI Desktop MCP integration (Phase19)
- [ ] S-12.2 Verify Qwen Code MCP integration (Phase19)
- [ ] S-12.3 Publish "Verified Views" integration guides (Phase19)

### Sprint S-13: Operational Visibility (Logs & Progress)
**Goal:** Real-time visibility into background processes (indexing, trace building) via Log Console and granular Progress Bars.

- [ ] S-13.1 Backend Event Bus (SSE) & Log Capture (Phase02)
- [ ] S-13.2 Progress Callback Wiring (Phase01/04)
- [ ] S-13.3 Frontend Log Console & Progress Components (Phase02)
- [ ] S-13.4 Dashboard Integration (Phase02)

### Sprint S-15: Monetization & Distribution Plumbing (Phase 11)
**Goal:** End-to-end licensing flow, payments recovery, and secure update channels.

- [ ] S-15.1 License Activation Exchange (api.codrag.io relay + Ed25519 verification)
- [ ] S-15.2 Payments Recovery (Lemon Squeezy order lookup integration)
- [ ] S-15.3 Signed Distribution Pipeline (Mac/Windows signing, auto-update)

### Sprint S-16: MCP Maturity & Ecosystem (Phase 05)
**Goal:** Complete the MCP story for remote/team usage and registry publication.

- [x] S-16.1 Streamable HTTP Transport (P05-R5) - for remote/enterprise usage
  - Implemented in `src/codrag/mcp_server.py` (`run_http`, `/sse`, `/message`)
- [ ] S-16.2 Async Tasks for long-running builds (P05-R7)
- [ ] S-16.3 PyPI Package Verification for MCP Registry (P05-I19)
- [ ] S-16.4 Tool Icons & Metadata Polish (P05-R9)

### Sprint S-18: Data Visualization (Phase 18)
**Goal:** Make invisible index activity visible and beautiful via CLI and Dashboard.

- [x] S-18.1 CLI Visualizations (Activity Heatmap, Index Health, Build Sparkline)
- [ ] S-18.2 Dashboard Viz Panels (Activity, Health, Token Budget)
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
- [x] S-11.3 Feature gating framework (`src/codrag/core/feature_gate.py`) 
  - 5 tiers: FREE, STARTER, PRO, TEAM, ENTERPRISE
  - 11 gated features + project count limits
  - License from `~/.codrag/license.json` or `CODRAG_TIER` env var
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
  - `getLicense()` on `ApiClient` interface + `CodragApiClient` + `MockApiClient`
- [x] S-11.7 Tests: 32 feature gate tests + 167 total passed, 0 failed 

### Sprint S-10: Context Intelligence (Phase16)
**Goal:** native embeddings (no Ollama required), user-defined path weighting, CLaRa context compression.

- [x] S-10.1 Native `nomic-embed-text` embedder via ONNX Runtime (Phase16) 
  - `NativeEmbedder` class in `src/codrag/core/embedder.py`
  - New deps: `onnxruntime`, `tokenizers`, `huggingface-hub`
  - Auto-download model on first use to `~/.cache/huggingface/`
  - Default embedder; Ollama becomes optional power-user config
  - CLI: `codrag models` pre-downloads for air-gapped setups
  - Tests: `tests/test_native_embedder.py` (12 tests)
- [x] S-10.2 User-defined path weights for context weighting (Phase16) 
  - `path_weights: Dict[str, float]` in `repo_policy.json`
  - Applied at search time via `_resolve_path_weight()` (longest-prefix match)
  - API: `GET/PUT /projects/{id}/path_weights` + `PUT /projects/{id}` accepts `path_weights`
  - UI: weight editor (click ×1.0 badge) in FolderTree + FolderTreePanel + FileExplorerDetail
  - Hot-update: weights apply immediately to searches without rebuild
  - Tests: `tests/test_path_weights.py` (15 tests)
- [x] S-10.3 CLaRa context compression via `CLaRa-Remembers-It-All` subtree (Phase16) 
  - `ContextCompressor` ABC + `ClaraCompressor` + `NoopCompressor` in `src/codrag/core/compressor.py`
  - Sidecar HTTP client calling CLaRa server at configurable URL (default `:8765`)
  - API: `compression="clara"` param on `/projects/{id}/context` + `GET /clara/status`
  - MCP: `codrag` tool accepts compression params
  - Graceful fallback: returns uncompressed on timeout/error
  - Tests: `tests/test_compressor.py` (19 tests)
- [x] S-10.4 Update marketing copy to reflect embeddings as built-in core feature (Phase12/16) 
  - All hero variants updated: "built-in embeddings", "no Ollama", path weights, CLaRa compression
  - Public docs: guides for embeddings, path weights, and CLaRa in `websites/apps/docs/`

---

## Cross-phase implementation strategy ledger
This section tracks shared decisions/strategies that must remain consistent across phases.

### STR-01: API response envelope and error model
- **Status:** ✅ Implemented
- **Source of truth:** `docs/API.md` + `src/codrag/server.py` (`ApiException`, `ok()` helper)
- **Implementation:** `{ok: true, data: ...}` / `{ok: false, error: {code, message, hint}}` envelope.
  `ApiException` with status_code/code/message/hint. Parity across HTTP + MCP.
- **Remaining:** formal error code taxonomy documentation

### STR-02: Stable IDs (chunks, files, trace nodes)
- **Status:** ✅ Implemented
- **Implementation:** `src/codrag/core/ids.py` — sha256-based derivations:
  - `stable_file_hash(content)` → 16-char hex
  - `stable_markdown_chunk_id(path, section, idx)`, `stable_code_chunk_id(path, idx)`
  - `stable_file_node_id(path)`, `stable_symbol_node_id(qualname, path, line)`
  - `stable_edge_id(kind, source, target)`
- **Guarantees:** deterministic, content-addressed for files, position-stable for chunks/nodes

### STR-03: Manifest schema + format versioning
- **Status:** ✅ Implemented
- **Implementation:** `src/codrag/core/manifest.py` — `MANIFEST_VERSION = "1.0"`
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
- **Implementation:** chokidar via Node.js subprocess (`src/codrag/watcher.py`).
  Debounce 5s default, throttle, state machine (disabled/idle/debouncing/building/throttled).
  Falls back gracefully if Node.js unavailable.

### STR-07: Trace analyzer strategy
- **Status:** ✅ Implemented
- **Implementation:** Rust engine with tree-sitter parsers for 8 languages.
  Python fallback via AST module. PyO3 bridge (`codrag_engine`).
  `CODRAG_ENGINE=rust|python|auto` env var for selection.

### STR-08: Packaging strategy (Python sidecar)
- **Status:** Proposed
- **Impacts:** Phase08 feasibility/schedule, Phase11 distribution constraints
- **Next actions:** decide PyInstaller vs PyOxidizer for MVP and document rationale

### STR-09: Licensing + feature gating strategy
- **Status:** ✅ Decided + Enforcement Implemented
- **Implementation:** Lemon Squeezy as MoR. "Activation Exchange" flow:
  LS issues key → user enters in app → exchange via api.codrag.io → signed Ed25519 offline license.
  Documented in ADR-013 + `docs/Phase11_Deployment/LEMON_SQUEEZY_INTEGRATION.md`.
- **Enforcement:** `src/codrag/core/feature_gate.py` — runtime tier checks.
  Server gates: project count, watcher, CLaRa.
  `GET /license` endpoint for frontend tier awareness.
  Dev override: `CODRAG_TIER=pro` env var.
- **Remaining:** Ed25519 signature verification in license loader, Tauri UI for license entry

### STR-10: Auto-rebuild ↔ auto-trace co-triggering
- **Status:** ✅ Implemented
- **Implementation:** Watcher `trigger_build` now calls both `_start_project_build()` (CodeIndex)
  and `_start_project_trace_build()` (Trace graph) when `trace.enabled=true` in project config.
  `is_building` checks both index and trace build threads.
- **Gating:** Auto-rebuild requires STARTER+ tier. Manual builds remain FREE.

---

## Sprint notes (append-only)
Add brief notes here after completing a sprint:
- date
- what changed (decisions, scope)
- new blockers

### 2026-02-01: API envelope + manifest/IDs scaffolding

**What was built:**
- HTTP daemon now supports the `docs/API.md` envelope and UI-facing routes:
  - `/projects/*` endpoints
  - `/llm/status` and `/llm/test`
- Shared helpers:
  - `src/codrag/api/envelope.py` (envelope + exception handlers)
  - `src/codrag/core/ids.py` (stable IDs + file hashes)
  - `src/codrag/core/manifest.py` (manifest read/write + builder)
- Minimal tests added for envelope + manifest/ID roundtrips.

**Known followups:**
- `src/codrag/api/responses.py` duplicates envelope helpers (see `docs/QA.md`).
- Phase03 incremental rebuild spec requires richer per-file manifest fields (see `docs/QA.md`).

### 2026-02-01: Sprint S-05 (MCP Integration) Complete

**What was built:**
- `src/codrag/mcp_server.py` — Full MCP server implementation (stdio transport)
  - Tools: `codrag_status`, `codrag_build`, `codrag_search`, `codrag_context`
  - JSON-RPC protocol handling per spec 2025-11-25
  - Token-efficient lean outputs
  - Proper error codes (DAEMON_UNAVAILABLE, etc.)
- `codrag mcp` CLI command — Runs MCP server with `--project` or `--auto` modes
- `codrag mcp-config` CLI command — Generates configs for 5 IDEs:
  - Claude Desktop, Cursor, VS Code, JetBrains, Windsurf
- `tests/test_mcp_server.py` — Comprehensive test suite
- `mcp-server.json` — MCP Registry metadata file
- `src/codrag/api/responses.py` — Standardized API response envelope
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
- [ ] P05-R5 Streamable HTTP transport (for remote/enterprise)
- [ ] P05-R7 Async Tasks for long builds
- [ ] P05-I19 PyPI verification for MCP Registry

### 2026-02-02: Documentation alignment + CLI/MCP gaps identified

**What was done:**
- Aligned `docs/Phase12.../MCP-Shim-strategy-and-examples.md` with canonical domain (`codrag.io`), repo name (`codrag-mcp`), and attribution policy (optional/user-controlled).
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
  - `src/codrag/dashboard/src/App.tsx`
  - Storybook `FullDashboard` demo
- Add missing scrollbar utilities + update UI package exports for new panels.
- [ ] MCP direct mode (`codrag mcp --mode direct`) needs verification/smoke test.

### 2026-02-03: Progress capture + next TODOs

 **Progress captured/verified:**
 - Websites monorepo scaffold exists under `websites/apps/*`:
   - `websites/apps/marketing`, `websites/apps/docs`, `websites/apps/support`, `websites/apps/payments`
   - Each is a Next.js app using `@codrag/ui` and the shared Tailwind preset.
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
   - Added `codrag mcp --transport http --port 8401`
   - Implemented SSE endpoint (`/sse`) and message endpoint (`/message`) using FastAPI/Uvicorn

### 2026-02-09: VS Code daemon wiring audit — license + MCP config endpoints

**What changed:**
- Implemented missing daemon endpoints used by the VS Code extension client:
  - `POST /license/activate`
  - `POST /license/deactivate`
  - `GET /api/code-index/mcp-config`
- Updated `tests/test_mcp_config_endpoint.py` to unwrap the standard `{success,data,error}` envelope.

**New TODOs discovered:**
- [ ] Backend: `POST /projects/{project_id}/watch/stop` response shape mismatch
  - `packages/vscode/src/client.ts` expects `{ enabled: boolean; state: string }`.
  - `packages/ui/src/api/types.ts` expects `WatchActionResponse` (`{ enabled: boolean; state: string }`).
  - Server currently returns `{"enabled": false}` only.
- [x] Docs: add `POST /license/activate`, `POST /license/deactivate`, `GET /api/code-index/mcp-config` to `docs/API.md`.
 - [x] MCP direct mode smoke test ✅ **DONE: `tests/test_mcp_direct_smoke.py` (10 tests, uses FakeEmbedder)**

 ### 2026-02-04: Universal UI + Storybook-First Strategy

 **What changed:**
 - **Workflow Shift**: Switched from running 4x Next.js dev servers (fragile, slow) to Storybook-first development (fast, isolated).
 - **Universal UI**: All marketing/docs components (`MarketingHero`, `FeatureBlocks`, `IndexStats`, `TraceGraph`) are now canonical in `@codrag/ui`.
 - **Themes Ported**: All "Radical" visual directions (Neo-Brutalist, Retro, Glass, etc.) + required fonts are fully integrated into the shared package.

 ### 2026-02-05: Frontend-Backend Integration (S-02)

 **What was built:**
 - **Typed API Client** (`packages/ui/src/api/client.ts`): Extended `CodragApiClient` with 9 new methods:
   - Project CRUD: `createProject`, `getProject`, `updateProject`, `deleteProject`
   - Build: `buildProject` (with polling)
   - Roots: `getProjectRoots`
   - Watch: `startWatch`, `stopWatch`, `getWatchStatus`
   - Health: `getHealth`
 - **New API types** (`packages/ui/src/api/types.ts`): `CreateProjectRequest/Response`, `UpdateProjectRequest/Response`, `DeleteProjectResponse`, `BuildProjectResponse`, `WatchActionResponse`
 - **App.tsx full rewrite** (`src/codrag/dashboard/src/App.tsx`): 1009→573 lines, exclusively Storybook components:
   - `AppShell` + `Sidebar` + `ProjectList` for multi-project navigation
   - `AddProjectModal` for project creation via `POST /projects`
   - `LoadingState` / `ErrorState` pattern components
   - `Button` atomic primitive (newly exported from `@codrag/ui`)
   - `FolderTreePanel` wired to `/projects/{id}/roots`
   - All API calls via `useApiClient()` → canonical `/projects/{id}/*` routes
   - Removed: legacy `/api/code-index` routes, hand-rolled fetch, inline tree logic, raw HTML buttons
 - **main.tsx**: Wrapped with `ApiClientProvider` using `CodragApiClient`
 - **New exports from `@codrag/ui`**: `Button`, `AddProjectModal`, `AddProjectModalProps`

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
 - Pinned file paths persisted in `localStorage` under key `codrag_pinned_files`

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
 - [x] Decide primer detection precedence (e.g. `AGENTS.md` vs `CODRAG_PRIMER.md`, root-only vs glob). ✅ **DONE: `docs/PRIMER_DETECTION.md`**

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
 - `src/codrag/core/feature_gate.py` — Tier model (FREE→STARTER→PRO→TEAM→ENTERPRISE)
 - 11 feature gates + project count limits per tier
 - `FeatureGateError` → HTTP 403 with `FEATURE_GATED` code + upgrade URL
 - License from `~/.codrag/license.json` or `CODRAG_TIER` env var (dev override)
 - `GET /license` endpoint returns tier + full feature availability map
 - Server enforces: project count limit on `POST /projects`, watcher on `POST /watch/start`
 - Tests: `tests/test_feature_gate.py` (32 tests)
 - `conftest.py`: auto-use fixture sets `CODRAG_TIER=pro` so existing tests aren't blocked

 **Frontend-Rust engine integration:**
 - Backend: `TraceIndex.status()` now returns `engine` ("rust"/"python") and `supported_languages` (8 langs)
 - Backend: `compute_trace_coverage()` default globs now cover Go, Rust, Java, C/C++ (was Python/TS/JS only)
 - Backend: `_detect_language()` handles Java, C, C++ extensions; `SUPPORTED_EXTENSIONS` updated
 - Frontend `TraceStatus` type: added `engine?`, `supported_languages?` fields
 - Frontend `TraceStatusCard`: renamed "Trace Index" → "Code Graph", shows Rust Engine badge (⚡ orange) + 8 language chips
 - Frontend `TraceCoveragePanel`: added Java, C, C++ to `LANG_LABELS`
 - Frontend `TraceExplorer`: added `struct`, `enum`, `trait`, `interface`, `namespace`, `async_function`, `async_method` to `SymbolTypeTag` color map
 - Frontend API client: `getLicense()` method on `ApiClient`, `CodragApiClient`, `MockApiClient`
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
 CLaRa compression    ✗      ✗        ✓      ✓      ✓
 Multi-repo agent     ✗      ✗        ✓      ✓      ✓
 Team config          ✗      ✗        ✗      ✓      ✓
 Audit log            ✗      ✗        ✗      ✗      ✓
 ```

 **Remaining work / roadblockers:**
 - [ ] Ed25519 license signature verification (currently trusts JSON file contents)
 - [ ] Tauri license entry UI + activation exchange flow
 - [ ] Frontend upgrade prompts: show "Upgrade to Starter" when free user hits limit
 - [x] Gate `clara_compression` in context endpoint ✅ `_apply_compression()` now calls `require_feature("clara_compression")`
 - [x] Gate `mcp_trace_expand` in context endpoint ✅ `context_project()` now calls `require_feature("mcp_trace_expand")` when `trace_expand=true`
 - [ ] Frontend `WatchControlPanel` should show upgrade prompt for FREE tier
 - [ ] `test_incremental_rebuild.py::test_deleted_file_not_carried_over` is flaky (FakeEmbedder uses non-deterministic `hash()`; needs `PYTHONHASHSEED` or deterministic seed)
 - [ ] Pre-existing: `test_mcp_config_endpoint.py::test_mcp_config_default_daemon_url_uses_base_url` fails (404 on endpoint)

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
 - `GET /clara/status`, `GET /clara/health` — CLaRa sidecar
 - Added `FEATURE_GATED` error code and HTTP 403 to spec

 **Architecture doc (ARCHITECTURE.md) had stale class names.** Fixed:
 - `IndexManager` → `CodeIndex` (actual class)
 - `LLMCoordinator` → `NativeEmbedder` + `OllamaEmbedder` + `ClaraCompressor` (actual classes)
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
 - [x] `GET /clara/status` — ✅ `getClaraStatus()` added
 - [x] `GET /clara/health` — ✅ `getClaraHealth()` added (client.ts:314)
 - [x] `GET /projects/{id}/activity` — ✅ `getProjectActivity()` added
 - [x] `GET /projects/{id}/coverage` — ✅ `getProjectCoverage()` added

 **Tier enforcement audit — all gates now wired:**
 | Enforcement Point | Feature | Status |
 |---|---|---|
 | `POST /projects` | `projects_max` (count limit) | ✅ Wired |
 | `POST /watch/start` | `auto_rebuild` (STARTER+) | ✅ Wired |
 | `_apply_compression()` | `clara_compression` (PRO+) | ✅ Wired |
 | `context_project()` trace_expand | `mcp_trace_expand` (PRO+) | ✅ Wired |
 | `GET /license` | All features | ✅ Wired |

 **UX revamp docs (Phase 14) — planned but not yet implemented:**
 - [ ] COMPONENT_AUDIT_V2.md: rename "Index Status"→"Knowledge Base Status", "Symbol Browser"→"Code Graph Explorer", etc.
 - [ ] DASHBOARD_UX_REVAMP.md: unified search bar, context budget meter, smart presets
 - [ ] Merge FolderTree + TraceCoverage into unified "Codebase Explorer"
 - [ ] Move LLM settings to a settings modal (out of main dashboard)
 - [ ] "Bicameral" layout: Knowledge (left) | Assembly (center) | Structure (right)

 **Phase TODO gaps — research items still open:**
 - [ ] P02-R1: Finalize dashboard information architecture
 - [ ] P02-R3: Decide minimum build progress granularity for MVP
 - [ ] P02-T1/T2: E2E smoke tests and error-state tests for dashboard
 - [ ] P02-I3: Global settings modal (Ollama URL, CLaRa URL, defaults)

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

 **API client gaps found and fixed (9 methods added):**
 - [x] `getEmbeddingStatus()` → `GET /embedding/status`
 - [x] `downloadEmbedding()` → `POST /embedding/download`
 - [x] `getClaraStatus()` → `GET /clara/status`
 - [x] `getClaraHealth()` → `GET /clara/health`
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

 **Full Panel Registry ↔ App.tsx ↔ Storybook alignment matrix (all 14 panels):**
 | Panel ID | Registry | App.tsx | Storybook | Backend Connected |
 |---|---|---|---|---|
 | `status` | ✅ | ✅ IndexStatusCard | ✅ | ✅ getProjectStatus |
 | `build` | ✅ | ✅ BuildCard | ✅ | ✅ buildProject |
 | `llm-status` | ✅ | ✅ LLMStatusWidget | ✅ | ✅ getLLMStatus |
 | `search` | ✅ | ✅ SearchPanel | ✅ | ✅ search |
 | `context-options` | ✅ | ✅ ContextOptionsPanel | ✅ | ✅ assembleContext |
 | `results` | ✅ | ✅ SearchResultsList+ChunkPreview | ✅ | ✅ search |
 | `context-output` | ✅ | ✅ ContextOutput | ✅ | ✅ assembleContext |
 | `roots` | ✅ | ✅ FolderTreePanel | ✅ | ✅ getProjectFiles |
 | `settings` | ✅ | ✅ ProjectSettingsPanel | ✅ | ✅ updateProject |
 | `file-tree` | ✅ | ✅ FolderTreePanel | ✅ | ✅ getProjectFiles |
 | `pinned-files` | ✅ | ✅ Inline list | ✅ | ✅ getProjectFileContent |
 | `watch` | ✅ | ✅ WatchControlPanel | ✅ | ✅ start/stop/getWatchStatus |
 | `trace` | ✅ | ✅ TraceExplorer | ✅ | ✅ searchTrace/getTraceNode/etc |
 | `trace-coverage` | ✅ | ✅ TraceCoveragePanel | ✅ | ✅ getTraceCoverage |

 **Full Backend ↔ Frontend endpoint coverage (all 35+ endpoints):**
 All canonical endpoints now have typed `ApiClient` methods. Legacy `/api/*` proxy endpoints
 wrapped via `testLLMEndpoint`, `fetchLLMModels`, `testLLMModel`. Global config still uses
 legacy `/api/code-index/config` path (migrate to canonical path when ready).

 **Remaining blockers / tech debt:**
 - [x] App.tsx LLM handlers: migrate from raw fetch to typed ApiClient methods (3 handlers) ✅ **DONE** (see lines 650-653)
 - [ ] `getGlobalConfig`/`updateGlobalConfig` use legacy `/api/code-index/config` — migrate to canonical endpoint
 - [ ] Activity heatmap panel: `ActivityHeatmap.stories.tsx` exists but no panel registered or wired in App.tsx
 - [ ] Storybook `NodeDetailPanel.stories.tsx` exists but NodeDetailPanel not wired as a dashboard panel
 - [ ] `WatchStatusIndicator.stories.tsx` exists but component not used in dashboard (WatchControlPanel used instead)

 **Build verification:** `tsc --noEmit` ✅ | `vite build` ✅ (6.08s) | backend tests 154 passed, 36 skipped, 0 failed

 ### 2026-02-09: VS Code Extension Implementation (Phase 17)

 **What was built:**
 - **Extension Host (`packages/vscode/src/`)**: Daemon-backed architecture.
   - `DaemonManager`: Auto-starts `codrag serve`, polls health, manages connection state.
   - `CodragDaemonClient`: Typed HTTP client for all daemon endpoints.
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

 `src/codrag/cli.py` — three commands reference `project_id` which is **not a function parameter**,
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
`mcp_tools.py` now defines **7 tools**: `codrag_status`, `codrag_build`, `codrag_search`, `codrag_context`, plus the three trace tools below.
- [x] Add `codrag_trace_search` MCP tool — search trace graph nodes by name/kind ✅
- [x] Add `codrag_trace_neighbors` MCP tool — get neighbors for a node ID ✅
- [x] Add `codrag_trace_coverage` MCP tool — get trace coverage summary ✅
All three trace tools now proxy to the project-scoped HTTP endpoints in `mcp_server.py`.

 #### Test Coverage Gaps
 - [x] `_deep_merge()` tests added — `tests/test_deep_merge.py` (13 tests, all pass)
 - [ ] No tests for any CLI commands (`cli.py` — 900 lines, 0 test coverage)
 - [ ] No tests for `viz/` module (activity_heatmap, coverage, overview, drift, flow, health, trace, context)
 - [ ] `test_mcp_config_endpoint.py` — pre-existing failure (404 on endpoint), excluded from CI
 - [ ] `test_trust_loop_integration.py` — excluded from runs
 - [ ] `test_incremental_rebuild.py::test_deleted_file_not_carried_over` — flaky (`hash()` non-determinism)

 #### Config Loading Bugfixes (user-applied, 2026-02-08)
 - [x] **Critical fix:** `loadConfig` in App.tsx no longer sets `llmConfigLoaded=true` on error.
   Previously, a failed config load would allow auto-save to trigger with empty/default state,
   **overwriting the server's persisted config**. Now `llmConfigLoaded` stays `false` on error.
 - [x] `PersistenceStatus` component now accepts `onRetry` callback; shows **Retry** button on error.
 - [x] `loadConfig` extracted to `useCallback` so it can be passed as `onRetry` prop.
 - [x] `PUT /api/code-index/config` endpoint now uses `_deep_merge()` instead of `dict.update()`,
   preventing partial updates from overwriting nested keys (e.g., sending `{llm_config: {clara: {...}}}`
   would previously wipe `llm_config.saved_endpoints`).

 #### pyproject.toml Issues ✅ FIXED
- [x] `requires-python = ">=3.11"` — kept as-is (3.11 is intended minimum per classifiers)
- [x] `project.urls` → updated to `github.com/EricBintner/CoDRAG` ✅
- [x] `addopts` → removed `--cov` flags that crash pytest without pytest-cov ✅

 #### Wrong Org URL — ~~`anthropics/CoDRAG`~~ ✅ FIXED
All URLs updated to `github.com/EricBintner/CoDRAG`:
- [x] `pyproject.toml` lines 71-74 — `project.urls` ✅
- [x] `packages/ui/package.json` line 83 — `repository.url` ✅
- [x] `mcp-server.json` lines 5-6 — `homepage` + `repository` ✅
- [x] `.venv/*/dist-info/METADATA` — auto-fixed on next `pip install -e .`

 #### Environment Variables — Undocumented
 Two env vars are used in code but not documented in README or any user-facing docs:
 - [ ] `CODRAG_ENGINE` — selects engine: `auto` (default), `rust`, `python` (`core/__init__.py`)
 - [ ] `CODRAG_TIER` — overrides license tier for development/testing (`core/feature_gate.py`)
 Document these in README.md or a configuration reference.

 #### Security Posture (local-first, acceptable for now)
 - `allow_origins=["*"]` CORS — fine for localhost, **must restrict for network/team mode** (Phase 06)
 - No authentication on any endpoint — planned for Phase 06 network mode
 - API keys passed in LLM proxy request bodies — acceptable for local, never stored server-side
 - File content endpoint (`/projects/{id}/file`) properly rejects path traversal (`..`) ✅

 #### Phase Doc Coverage — Untracked Open Work

 **Phase 07 (Polish & Testing) — CRITICAL: Entirely open**
 This phase defines the MVP quality bar but has **zero completed items**:
 - [ ] P07-R1/R2/R3: Research (test suite definition, perf targets, mock strategy)
 - [ ] P07-I1-I3: Error taxonomy + actionable messaging
 - [ ] P07-I4-I6: Recovery behaviors (interrupted build, corruption, disk pressure)
 - [ ] P07-I7-I8: Observability (per-project logs, diagnostics bundle)
 - [ ] P07-I9-I12: Test harness (fixture strategy, integration tests, failure injection, gold queries)
 - [ ] P07-I13-I14: Performance benchmarks

 **Phase 05 (MCP) — 4 open items remaining:**
 - [ ] P05-R5: Streamable HTTP transport (stdio done, HTTP not started)
 - [ ] P05-R7: Async Tasks for `codrag_build` (long-running)
 - [ ] P05-R9: Tool icons (`_meta.icons`)
 - [ ] P05-I19: PyPI package verification for MCP Registry

 **Phase 06 (Team & Enterprise) — All implementation open:**
 - [ ] P06-I1-I3: Shared team config (schema done in `team_config.py`, but merge precedence and
   provenance reporting not implemented)
 - [ ] P06-I4-I6: Embedded mode (layout defined, but incompatibility detection + watch-loop
   avoidance not implemented)
 - [ ] P06-I7-I9: Network mode (auth requirement, header standardization, redaction rules)
 - [ ] P06-T1-T3: All tests open

 **Phase 08 (Tauri MVP) — All open:**
 - [ ] P08-I1-I3: Sidecar lifecycle (startup, shutdown, crash recovery)
 - [ ] P08-I4-I6: Port strategy (conflict detection, fallback)
 - [ ] P08-I7-I8: UX surfaces ("Backend starting" screen)
 - [ ] P08-R1-R3: Research (packaging, port strategy, signing)

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
 - `core/compressor.py` (235 lines) — CLaRa + Noop
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
 `src/codrag/dashboard/vite.config.ts` now proxies **all 7 prefixes** to the daemon at `127.0.0.1:8400`:
 `/api`, `/projects`, `/health`, `/llm`, `/license`, `/embedding`, `/clara`.
 - [x] `/embedding/*` — ✅ proxy added (vite.config.ts lines 95-99)
 - [x] `/clara/*` — ✅ proxy added (vite.config.ts lines 100-104)
 - [x] `/license` — ✅ proxy added (vite.config.ts lines 90-94)

 #### Legacy Endpoints Incompatible with Multi-Project
 Three legacy endpoints use the global `_get_index()` singleton instead of project-scoped
 `_get_project_index()`. They **silently break** in multi-project configurations:
 - [ ] `POST /api/code-index/context` — uses `_get_index()` and global `_trace_index` singleton
 - [ ] `POST /api/code-index/chunk` — uses `_get_index()`
 - [ ] `GET/PUT /api/code-index/config` — global config, not project-aware
 These should be deprecated (add deprecation warning header) and callers migrated to the
 project-scoped equivalents (`/projects/{id}/context`, `/projects/{id}/search`).
 Note: the frontend `getGlobalConfig/updateGlobalConfig` already uses the legacy `/api/code-index/config`
 path — this needs a migration plan (track as tech debt item in MASTER_TODO).

 #### Dead Code: `api/responses.py` (227 lines)
 `src/codrag/api/responses.py` defines `APIException`, `ErrorCode`, typed error subclasses
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
 | ~~**P0**~~ | ~~`/llm/test` bug~~ | ~~1~~ | ✅ **FIXED** | ~~CLaRa connectivity hardcoded `False`~~ |
 | **P1** | API docs gaps | 13 | ✅ **FIXED** | Undocumented server endpoints |
 | **P1** | Phase 07 (Testing) | 14 | Open | Entire phase unstarted — MVP quality bar |
 | **P1** | Test coverage | 2 | Open | CLI (900 lines), viz (8 files) untested |
 | ~~**P1**~~ | ~~pyproject.toml~~ | ~~3~~ |  **FIXED** | ~~Wrong URLs, Python version, pytest-cov~~ |
 | ~~**P1**~~ | ~~Legacy endpoints~~ | ~~3~~ |  **DEPRECATED** | ~~`/api/code-index/*`~~ → deprecation warnings added |
 | ~~**P1**~~ | ~~Dashboard error UX~~ | ~~1~~ |  **FIXED** | ~~`_error` state~~ → ErrorToast component wired |
 | ~~**P2**~~ | ~~Dead code~~ | ~~2~~ |  **DELETED** | ~~`server_old.py` + `api/responses.py`~~ |
 | ~~**P2**~~ | ~~Endpoint cleanup~~ | ~~3~~ | ✅ **OK** | ~~Duplicate trace endpoints~~ → intentional aliases |
 | **P2** | UX renames | 9 | Open | Phase 14 component rename plan |
 | ~~**P2**~~ | ~~Frontend client gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`/llm/test`~~ → `testLLMConnectivity()` added |
 | ~~**P2**~~ | ~~Env var docs~~ | ~~2~~ |  **FIXED** | ~~`CODRAG_ENGINE`, `CODRAG_TIER`~~ → documented in README |
 | **P2** | Settings primitives | 7 | Open | Missing form/budget/diagnostics components |
 | **P3** | Phase 06/08/11 | ~30 | Open | Team, Tauri, Deployment (post-MVP) |
 | **P3** | Phase 17 | ~45 | Open | VS Code extension (future) |
 | **P3** | Website builds | 1 | Open | `@codrag/ui` resolution (build order) |

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

 **Vite Proxy — all 3 missing routes now proxied ✅**
 `src/codrag/dashboard/vite.config.ts` lines 90-104 now include `/license`, `/embedding/*`,
 `/clara/*` proxy rules. All 7 endpoint prefixes reach the daemon in dev mode.

 **Frontend API client — `getClaraHealth()` exists ✅**
 `packages/ui/src/api/client.ts:314` implements `getClaraHealth()` → `GET /clara/health`.
 Previously listed as a gap — now closed.

 **App.tsx LLM handlers — fully migrated ✅**
 All 3 handlers (`handleTestEndpoint`, `handleFetchModels`, `handleTestModel`) now use typed
 `ApiClient` methods. The remaining tech debt item on line 687 was stale and has been marked done.

 #### NEW: License Activation Exchange — NOT_IMPLEMENTED
 `server.py:990` — `POST /license/activate` exists but returns `NOT_IMPLEMENTED` error for the
 full Lemon Squeezy activation exchange flow. It currently only accepts:
 - Direct JSON license payload
 - Tier name string (`free`/`starter`/`pro`/`team`/`enterprise`)
 - Base64url-encoded JSON token
 The planned flow (user enters LS key → exchange via `api.codrag.io` → signed Ed25519 offline
 license) is **not implemented**. This blocks the full licensing story.
 - [ ] Implement Lemon Squeezy activation exchange in `POST /license/activate`
 - [ ] Wire `api.codrag.io` relay service for key → license exchange
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
 `src/codrag/dashboard/src/App.tsx`:
 - `ErrorToast` component defined (lines 163-178) with auto-dismiss after 5s
 - `_error` state set in 10+ catch blocks throughout the file
 - Rendered at bottom of JSX: `{_error && <ErrorToast message={_error} onDismiss={() => setError(null)} />}`
 - [x] Error toast is fully wired and functional ✅

 #### ~~NEW: viz Module — Not Exported / Not Wired~~ ✅ FIXED
 ~~`src/codrag/viz/__init__.py` exports 7 functions but **2 viz modules are orphaned**:~~
 - [x] `render_drift_report` (`viz/drift.py`) — exported from `__init__.py` ✅, CLI `codrag drift` added ✅
 - [x] `render_rag_flow` (`viz/flow.py`) — exported from `__init__.py` ✅, CLI `codrag flow` added ✅
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
 - `api.codrag.io` activation exchange endpoint (P1 License activation)
 - Lemon Squeezy product + activation limits (P2 Payments recovery)
 - Signed CoDRAG binaries on PATH (dev-only, not blocking)
 - [x] **ACTION:** Update Phase 17 TODO.md dependencies table ✅ DONE

 #### NEW: Phase 15 — Open Items
 `docs/Phase15_modular-design/TODO.md` has remaining open items:
 - [ ] Sprint 7: `Introduction.mdx` documentation story not created
 - [ ] Sprint 3.2: `DashboardGrid.stories.tsx` not created (covered by ModularDashboard)
 - [ ] Definition of Done checklist (lines 161-170) — not formally verified
 - [ ] Future: multi-column layouts, sidebar panels, server-side layout sync

 #### NEW: CLaRa Vendor — MLX Backend TODO
 `vendor/clara-server/src/clara_server/model.py:231`:
 ```python
 # TODO: Implement MLX loading when CLaRa MLX weights are available
 ```
 This is in the vendored CLaRa subtree. Low priority — only relevant for Apple Silicon
 native inference. Not blocking any CoDRAG functionality.
 - [ ] Implement MLX model loading in CLaRa when weights become available (vendor subtree)

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
 | ~~**P0**~~ | ~~`/llm/test` bug~~ | ~~1~~ | ✅ **FIXED** | ~~CLaRa connectivity hardcoded `False`~~ |
 | ~~**P0**~~ | ~~Vite proxy~~ | ~~3~~ | ✅ **FIXED** | ~~`/embedding`, `/clara`, `/license` now proxied~~ |
 | **P1** | License activation | 3 | **NEW** | Exchange flow NOT_IMPLEMENTED, Ed25519, relay service |
 | ~~**P1**~~ | ~~API docs gaps~~ | ~~13~~ | ✅ **FIXED** | ~~Undocumented server endpoints~~ → added to API.md |
| ~~**P1**~~ | ~~Backend stubs~~ | ~~2~~ | ✅ **FIXED** | ~~Trace expansion no-op, progress callback~~ |
| ~~**P1**~~ | ~~MCP gaps~~ | ~~3~~ | ✅ **DONE** | ~~No trace tools in MCP~~ → 3 trace tools added |
| **P1** | Phase 07 (Testing) | 14 | Open | Entire phase unstarted — MVP quality bar |
| **P1** | Test coverage | 2 | Open | CLI (900 lines), viz (8 files) untested |
| ~~**P1**~~ | ~~pyproject.toml~~ | ~~3~~ |  **FIXED** | ~~Python version, pytest-cov crash, wrong org URL~~ |
| ~~**P1**~~ | ~~Wrong org URL~~ | ~~3~~ |  **FIXED** | ~~`anthropics/CoDRAG`~~ → `EricBintner/CoDRAG` |
| ~~**P1**~~ | ~~Legacy endpoints~~ | ~~3~~ |  **DEPRECATED** | ~~`/api/code-index/*`~~ → deprecation warnings added |
 | ~~**P1**~~ | ~~Dashboard error UX~~ | ~~1~~ |  **FIXED** | ~~`_error` state~~ → ErrorToast component wired |
 | ~~**P2**~~ | ~~Dead code~~ | ~~2~~ |  **DELETED** | ~~`server_old.py` + `api/responses.py`~~ |
| **P2** | Endpoint cleanup | 3 | **OK** | Duplicate trace endpoints → intentional aliases |
| **P2** | UX renames | 9 | Open | Phase 14 component rename plan |
| ~~**P2**~~ | ~~Frontend client gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`/llm/test`~~ → `testLLMConnectivity()` added |
| ~~**P2**~~ | ~~Env var docs~~ | ~~2~~ | ✅ **FIXED** | ~~`CODRAG_ENGINE`, `CODRAG_TIER`~~ → documented in README |
 | **P2** | Settings primitives | 7 | Open | Missing form/budget/diagnostics components |
 | ~~**P2**~~ | ~~MockApiClient~~ | ~~1~~ | ✅ **FIXED** | ~~38 stub methods~~ → all methods now return mock data |
 | ~~**P2**~~ | ~~viz module gaps~~ | ~~2~~ | ✅ **FIXED** | ~~`drift` + `flow`~~ → exported + CLI commands added |
| ~~**P2**~~ | ~~Missing exports~~ | ~~2~~ | ✅ **FIXED** | ~~team + viz components~~ → added to packages/ui/index.ts |
| ~~**P2**~~ | ~~Dead CLI file~~ | ~~1~~ | ✅ **DELETED** | ~~`cli_new.py` (542 lines)~~ → removed |
 | **P2** | Payments recovery | 1 | **NEW** | Mock stub, needs Lemon Squeezy integration |
 | ~~**P2**~~ | ~~Phase doc staleness~~ | ~~4~~ |  **FIXED** | ~~Phase 01/03/07 TODOs~~ → reconciled with implementation |
 | **P2** | Phase 15 open items | 3 | **NEW** | Sprint 7 docs, DashboardGrid story, DoD checklist |
 | **P3** | Phase 06/08/11 | ~30 | Open | Team, Tauri, Deployment (post-MVP) |
 | **P3** | Phase 17 | ~45 | Open | VS Code extension (future) |
 | **P3** | Website builds | 1 | Open | `@codrag/ui` resolution (build order) |
