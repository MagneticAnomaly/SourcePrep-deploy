# Phase 81 — UI Bugfixes & Dashboard State Audit

**Branch:** `phase81/ui-bugfixes`
**Date:** 2026-04-07
**Status:** Stages 0-3 complete, Stage 4 (error visibility) deferred

---

## Summary

Systematic audit and fix of the CoDRAG dashboard state management. The pause button was the entry point but the real issue was broader: 9 of 18 hooks lacked hydration support, panels showed stale data across project switches, and loading states were absent or misleading.

## Documents

| Doc | Description |
|-----|-------------|
| [01_Pipeline_Pause_and_UI_State_Audit.md](01_Pipeline_Pause_and_UI_State_Audit.md) | Initial audit: 10 bugs, 3 systemic issues in pipeline pause system |
| [02_Dashboard_Panel_Inventory.md](02_Dashboard_Panel_Inventory.md) | Full inventory of 18 hooks, 37 panels, hydration gap analysis |
| [03_Pause_Fix_Implementation.md](03_Pause_Fix_Implementation.md) | P0 pause fixes (committed to main) |
| [04_Implementation_Plan.md](04_Implementation_Plan.md) | 4-stage plan with research findings and decision log |
| [05_Stage1_Pause_P1_Implementation.md](05_Stage1_Pause_P1_Implementation.md) | Backend SSE emit, pausing detection, Auto->Manual pause, dead code removal |
| [06_Stage2_Hydration_Gaps.md](06_Stage2_Hydration_Gaps.md) | AbortSignal for concepts, reset for search/atlas/deep analysis |
| [07_Stage3_Loading_States.md](07_Stage3_Loading_States.md) | PanelLoading component, null-state fallback replacement |

## Commits

| Commit | Stage | Summary |
|--------|-------|---------|
| `a86331b0` (main) | Stage 0 | P0 pause fixes + audit docs |
| `acfb33b9` | Stage 1 | Backend SSE + pause P1 fixes + dead code cleanup |
| `9303c08b` | Stage 2 | Hydration gaps: concepts, search, atlas, deep analysis |
| `545a1035` | Stage 3 | PanelLoading component + null-state fallback cleanup |

## Key Findings

1. **Backend SSE gap:** `_pause_group()` did not emit SSE after `PAUSING->PAUSED` transition. Frontend had a 3+ second blind spot where pause state was only discoverable via polling.

2. **Hydration controller adoption:** Only 9/18 hooks used the Phase 70 hydration controller. Hooks without it fired requests for stale projects during rapid switching.

3. **Legacy pause detection:** `build_orchestrator.py` still emits `phase: FAILED, error: "Paused by user"` at the slot level. The pipeline state machine wraps this with proper `PAUSED` state, but the SSE bridge fires on the slot transition, not the state machine transition. Both detection paths are needed.

4. **Dead code:** `handleTogglePause` toggled `projectConfig.trace.paused` (a config flag ignored by the pipeline orchestrator). It was wired through 4 files but never actually used in the component render body.

## Remaining Work (Stage 4 — deferred)

- Replace silent error swallowing (`catch { /* silent */ }`) with visible error states
- Add error prop to hooks that currently swallow failures
- Consider React error boundaries around each panel in ModularDashboard
- Move atlas/activity/provenance from bare `useState` in App.tsx to a dedicated hook
