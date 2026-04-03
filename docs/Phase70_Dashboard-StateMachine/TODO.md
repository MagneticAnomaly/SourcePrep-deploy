# Phase 70: Dashboard Project-Switch Performance — TODO

## Tactical Fixes (Complete)

- [x] **Task 1:** Create `useHydrationController` hook (AbortController + debounce)
- [x] **Task 2:** Wire controller into App.tsx
- [x] **Task 3:** Thread AbortSignal into simple hooks (audit, spaghetti, goalposts)
- [x] **Task 4:** Thread AbortSignal into remaining secondary hooks (roadmap, opportunities, agentOps)
- [x] **Task 5:** Thread AbortSignal into critical hooks (projectManager, fileSystem, trace, enrichment)
- [x] **Task 6:** Guard all polling effects with `isHydrating` flag
- [x] **Task 7:** Move App.tsx direct hydration effects behind the controller

## Code Review Fixes (Complete)

- [x] **C1:** Fix `isHydrating` permanently stuck true (removed unused registerHook/markHydrated)
- [x] **I2:** Restore cleanup functions in useEnrichment/useTraceSystem
- [x] **I3:** Guard fetchFileTree with signal
- [x] **Signal lifecycle:** Move AbortController replacement to render phase (fixed blank panels)

## Panel Reliability Fixes (Complete)

- [x] **API timeout:** Add 10s request timeout to CodragApiClient (prevents indefinite hangs)
- [x] **Retry:** Add retry-once-after-3s to useProjectManager hydration (fixes Knowledge Base Status)
- [x] **Retry:** Add retry-once-after-3s to useTraceSystem hydration (fixes Graph Explorer + Graph Scope)

## Manual Testing

- [ ] **Test 1:** Start daemon with multiple projects, switch between them rapidly — no freeze
- [ ] **Test 2:** Start daemon under pipeline load, select project — panels load within ~15s (timeout + retry)
- [ ] **Test 3:** Switch projects while daemon is busy — old project data doesn't leak into new project

## Re-evaluation Checkpoint

- [ ] **Decision:** Is performance acceptable?
  - If yes: merge to main
  - If no: proceed to structural fixes below

## Structural Fixes (If Needed)

- [ ] Tiered concurrency cap in `useHydrationController` (max 4 critical, 3 secondary)
- [ ] Full state machine (`idle -> switching -> hydrating:critical -> hydrating:secondary -> ready`)
- [ ] Server-side batched endpoint (`/api/projects/{id}/context`)
