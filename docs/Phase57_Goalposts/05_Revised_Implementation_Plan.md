# Goalposts: Revised Implementation Plan (v2)

> This plan supersedes `02_Architecture_Pipeline.md` and `03_Dashboard_UX.md` based on findings in `04_RnD_Deep_Analysis.md`.

## Architecture Summary

```
Atlas (~4K) ──────────────┐
Audit Tech Debt (~2K) ────┤─→ GoalpostsPlanner (LLM, ~7K prompt) ─→ goalposts.json
User Product Intent (~500) ┘

goalposts.json ──→ Dashboard Panel (approve/dismiss/refine)
               ──→ MCP Tool (codrag_goalposts) [future]
               ──→ Next Goalposts run (steered by approvals + answers)
```

## Key Corrections from R&D
1. **Not a pipeline stage** — independent background job (like `DeepAnalysisOrchestrator`)
2. **~7K char prompt, not 50K+** — uses Atlas compression
3. **"Goalposts" not "Sprints"** — user-agnostic milestone framing
4. **Dashboard panel, not tab** — follows `ModularDashboard` + `useDashboardPanels` architecture
5. **Product Intent required** — must build input mechanism first

## Files to Create
| Layer | File | Pattern |
|-------|------|---------|
| Core | `src/codrag/core/goalposts_planner.py` | Like `DeepAnalysisOrchestrator` |
| Core | `src/codrag/core/goalposts_models.py` | Pydantic dataclasses |
| API | `src/codrag/api/routers/projects/goalposts.py` | Like audit endpoints |
| Hook | `dashboard/src/hooks/useGoalpostsSystem.ts` | Like `useAuditSystem` |
| UI | `packages/ui/src/components/GoalpostsPanel.tsx` | Like `AuditPanel` |
| Wiring | `dashboard/src/hooks/useDashboardPanels.tsx` | Add `'goalposts'` key |
| Wiring | `dashboard/src/App.tsx` | Add hook + pass props |
