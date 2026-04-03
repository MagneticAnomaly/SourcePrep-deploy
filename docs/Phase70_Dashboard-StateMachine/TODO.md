# Phase 70: Dashboard Project-Switch Performance — TODO

## Tactical Fixes (Current Sprint)

- [ ] **Task 1:** Create `useHydrationController` hook (AbortController + debounce)
- [ ] **Task 2:** Wire controller into App.tsx
- [ ] **Task 3:** Thread AbortSignal into simple hooks (audit, spaghetti, goalposts)
- [ ] **Task 4:** Thread AbortSignal into remaining secondary hooks (roadmap, opportunities, agentOps)
- [ ] **Task 5:** Thread AbortSignal into critical hooks (projectManager, fileSystem, trace, enrichment)
- [ ] **Task 6:** Guard all polling effects with `isHydrating` flag
- [ ] **Task 7:** Move App.tsx direct hydration effects behind the controller
- [ ] **Manual test:** Verify project switching no longer freezes

## Re-evaluation Checkpoint

After completing the above, test and decide if further work is needed:

- [ ] **Decision:** Is performance acceptable after tactical fixes?
  - If yes: close Phase 70
  - If no: proceed to structural fixes below

## Structural Fixes (If Needed)

- [ ] Tiered concurrency cap in `useHydrationController` (max 4 critical, 3 secondary)
- [ ] Full state machine (`idle -> switching -> hydrating:critical -> hydrating:secondary -> ready`)
- [ ] Server-side batched endpoint (`/api/projects/{id}/context`)
