# Phase 02 — Dashboard TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Settings backlog: `SETTINGS_TODO.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- API contract: `../API.md`
- Workflow backbone: `../WORKFLOW_RESEARCH.md`

## Research completion checklist (P02-R*)
- [ ] P02-R1 Finalize dashboard information architecture (pages, navigation, empty/error states)
- [ ] P02-R2 Finalize UI-facing API contract shapes for:
  - projects list/add/remove
  - build/status
  - search
  - context
- [x] P02-R3 Decide minimum build progress granularity required for MVP ✅ `TaskProgress` (percent + message + current/total) via SSE

## Implementation backlog (P02-I*)
### App shell + navigation
- [x] P02-I1 Project list (sidebar) + add/remove flows ✅ `AppShell` + `Sidebar` + `ProjectList` + `AddProjectModal`
- [x] P02-I2 Project tabs (open/close, persist) ✅ Multi-project selection via `ProjectList`
- [x] P02-I3 Global settings modal (provider URLs, defaults) ✅ `SettingsDrawer` (Global) + `AIModelsSettings` (LLM Status panel detail)
  - ollama URL
  - default embedding model
  - optional: CLaRa URL + enable toggle

### Status/build
- [x] P02-I4 Status page “trust console” card(s): ✅ `IndexStatusCard` + `LLMStatusWidget`
  - right project identity (name + path)
  - index exists / last successful build
  - building / pending
  - last error (code/message/hint)
  - [x] P02-I4a Provider connectivity tests ✅ `AIModelsSettings` in panel details
- [x] P02-I5 Build actions: ✅ `BuildCard` with build polling
  - incremental build (default)
  - full rebuild (confirm)

### Search + inspection
- [x] P02-I6 Search page: ✅ `SearchPanel` + `SearchResultsList` + `ChunkPreview`
  - query input
  - results list with previews
  - chunk viewer panel/drawer
- [x] P02-I7 Search result inspectability: ✅ `SearchResultsList` + `ChunkPreview`
  - show path + span
  - copy chunk
  - optional score display behind toggle

### Context assembly
- [x] P02-I8 Context page: ✅ `ContextOptionsPanel` + `ContextOutput`
  - query input
  - bounded settings UI (`k`, `max_chars`, `min_score`)
  - output viewer with citations
  - copy-to-clipboard

### Settings
- [x] P02-I9 Per-project settings: ✅ `ProjectSettingsPanel` + `FolderTreePanel`
  - core/working roots selection
  - include/exclude globs
  - max file bytes
  - trace enabled
  - auto-rebuild enabled
  - auto-rebuild tuning (debounce, min gap)

### Error + loading states
- [x] P02-I10 Standardize UX states: loading / empty / ready / error ✅ `LoadingState` + `ErrorState` + empty state in sidebar
- [x] P02-I11 Standard error component that renders `error.code`, message, and hint consistently ✅ `ErrorState`

## Testing & validation (P02-T*)
- [x] P02-T1 E2E smoke: add project → build → search → open chunk → context ✅ `tests/test_dashboard_e2e_flow.py` + `TEST_PLAN_E2E.md`
- [x] P02-T2 Error-state tests: ✅ `tests/test_dashboard_error_states.py`
  - project not found
  - Ollama unavailable
  - build failed

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [x] STR-01 API envelope + error codes: UI component must assume stable shapes 
- [x] STR-05 Budgets: UI defaults must match daemon/MCP conservative defaults 
- [x] STR-04 Atomic build: UI must communicate “last known-good snapshot” behavior 

## Current progress (dashboard wiring)
- [x] Identified the immediate regression: `src/codrag/dashboard/src/App.tsx` was truncated and references missing state/handlers, especially around `AIModelsSettings`.
- [x] Verified the relevant backend surfaces exist:
  - legacy UI config: `GET/PUT /api/code-index/config`
  - LLM proxy: `GET /api/llm/proxy/models`, `POST /api/llm/proxy/test-model`
  - provider status: `GET /llm/status`
- [x] Verified `@codrag/ui` has the required settings UI components and stories (reference implementations):
  - `AIModelsSettings`, `EndpointManager`
  - `ProjectSettingsPanel`

## Next steps (to restore compile + functionality)
- [x] Repair `App.tsx` to compile: ✅ Full rewrite using Storybook-canonical components
  - restored LLM config state + handlers
  - restored API wiring for model fetch + test via `/api/llm/proxy/*`
  - config persistence via `PUT /projects/{id}` (canonical API)
- [ ] Smoke test flows:
  - load config on mount
  - update endpoint/model slot → save config
  - fetch models for an endpoint
  - run “test model” and surface results

## Notes / blockers
- [ ] Decide where “project path” is shown vs hidden (future remote mode redaction requirements)
- [ ] Decide whether the dashboard needs a “diagnostics” panel in MVP (Phase07 suggests it)

