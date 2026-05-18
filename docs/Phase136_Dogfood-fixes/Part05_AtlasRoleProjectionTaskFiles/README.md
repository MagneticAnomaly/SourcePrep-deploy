# Part 05 — Atlas role projection: task-named files dominate role tag

> **Status:** Stub / awaiting implementation plan
> **Trigger:** 19_Followup Gap #3 (2026-05-11)
> **Work order:** after Part 04, before Cluster F (06–08)

## The bug

Calling `prep` with a task description that explicitly names
`augmenter`, `deepening`, `epistemic_enrichment`, `audit`, plus
`working_dir=src/prep/services/pipeline`, the "RELEVANT FILES" section
returned `treatment_registry`, `swarm_orchestrator`, `useLLMConfig`,
`useTraceSystem` — **none of the files the caller named**. The
Working Area observation, by contrast, correctly surfaced a deeply-
relevant Phase 61B mtime-staleness observation.

The role projection is over-weighting the role tag (e.g. "Software
Engineer") and under-weighting the task description's explicit file
mentions.

## The fix shape

`compute_role_relevance` (or its caller) needs to weight explicit file
mentions in the task description more heavily than role-tag affinity.
When an agent says `task="...augmenter.py..."`, that file should
dominate — role projection is a tiebreaker, not a primary signal.

## Files likely touched

- `src/prep/core/atlas/role_projection.py` — relevance scoring
- `src/prep/core/atlas/role_resolver.py` — role modifiers
- Possibly `src/prep/mcp/server.py` — how task strings are passed
  down to projection

## Test plan

### Layer 1 — pytest

- `tests/test_role_projection_task_files.py` (new)
  - Build a small atlas with multiple modules.
  - Call projection with `task="work on augmenter.py and deepening"`.
  - Assert `augmenter.py` and `deepening.py` appear in top-3 results.
  - Parametric over several role tags — task mention should win
    across all roles.

### Layer 2 — live MCP probe

```
Before:
  prep(task="...augmenter, deepening, epistemic_enrichment, audit...",
       working_dir="src/prep/services/pipeline")
  → RELEVANT FILES: treatment_registry, swarm_orchestrator,
                    useLLMConfig, useTraceSystem

After:
  → RELEVANT FILES: augmenter.py, deepening.py,
                    epistemic_enrichment.py, audit/*
```

## Acceptance

Part 05 is shipped when:

1. Explicit file mentions in `task=` dominate role-tag affinity.
2. Live probe returns the named files in top results.
3. Role-projection-only (no task string) behavior is unchanged
   (regression guard).

## Risks

- **Over-correcting:** if task-mentions completely override role,
  projection becomes a substring matcher. Mitigation: weight, don't
  short-circuit. Role tag stays as a tiebreaker among task-mentioned
  candidates.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` Gap #3
