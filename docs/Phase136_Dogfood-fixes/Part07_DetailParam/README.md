# Part 07 — `detail` parameter for progressive disclosure

> **Status:** Stub / awaiting implementation plan
> **Trigger:** FIX-8 (Phase 82 prioritized fix plan, P2)
> **Work order:** after Part 06

## The gap

All MCP tools dump maximum context — none offer "give me the 3 most
important things." This wastes token budget and slows agent decisions.
The verbose plumbing for `prep_context` (shipped 2026-05-08 as part of
FIX-16-1) is a single-tool precedent; this Part generalizes it.

## The fix shape

Add a `detail` parameter to every MCP tool with three levels:

- `detail="brief"`: top-3 items, minimal context, ~1K chars
- `detail="default"`: current behavior, unchanged
- `detail="verbose"`: full firehose (mirrors today's `verbose=true` on
  `prep_context`)

Tools that already have `verbose` migrate: `verbose=true` becomes a
deprecated alias for `detail="verbose"`.

## Files likely touched

- `src/prep/mcp_tools.py` — add `detail` to all five tool schemas
- `src/prep/mcp/server.py` — all tool handlers respect detail level
- `src/prep/api/routers/projects/*` — wire `detail` through endpoints

This is the largest Part by LOC. Schema changes touch every tool.

## Test plan

### Layer 1 — pytest

- `tests/test_detail_param.py` (new)
  - Parametric over all five tools × three detail levels.
  - Assert `brief` returns less content than `default`; `verbose`
    returns at least as much as `default`.
  - Assert `verbose=true` legacy still works (alias for `detail="verbose"`).

### Layer 2 — live MCP probe

```
prep_search "augmenter" detail=brief
  → 3 results, minimal context

prep_search "augmenter" detail=verbose
  → all hits, full docstrings
```

## Acceptance

Part 07 is shipped when:

1. `detail` parameter accepted on all five MCP tools.
2. Three levels behave as specified.
3. Legacy `verbose=true` callers continue to work.
4. AGENTS.md / generated rules document the parameter.

## Risks

- **Scope creep.** Touching five tool schemas could ripple into the
  routers and the dashboard's API client. Mitigation: stop at the
  MCP boundary; dashboard can opt in later.
- **Default-level regression.** If `default` accidentally shifts
  behavior, every existing agent's expectations break. Mitigation:
  pin `default` to current-behavior tests pre-change, run them
  post-change unchanged.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/07_Prioritized_Fix_Plan.md` FIX-8
- 2026-05-08 FIX-16-1 verbose plumbing — the precedent
