# Part 08 — Cross-tool "Next Steps" suggestions

> **Status:** Stub / awaiting implementation plan
> **Trigger:** FIX-7 (Phase 82 prioritized fix plan, P2)
> **Work order:** last in Phase 136

## The gap

Today's MCP tools are isolated. `prep_audit` flags a bottleneck file;
the agent has to guess that `prep_impact` is the next call. Tying
results together transforms the toolset into a guided workflow.

## The fix shape

Each tool handler appends a `## Suggested Next Steps` block to its
markdown response. Example from the Phase 82 sketch:

```python
# At end of tool_audit response:
tips = []
for f in top_findings:
    if f["severity"] == "critical" and "bottleneck" in f.get("tags", []):
        tips.append(f"→ prep_impact(file_path='{f['files'][0]}') for blast radius")
    if f["category"] == "circular_dependency":
        tips.append(f"→ prep_search(query='{f['files'][0]} {f['files'][1]}') for context")
if tips:
    result["_to_markdown"] += "\n\n## Suggested Next Steps\n" + "\n".join(tips)
```

Apply the pattern to every tool. Specific suggestion logic per tool TBD
in plan, but the categories:

- `prep_audit` → `prep_impact` (for hubs), `prep_search` (for cycles)
- `prep_impact` → `prep_search` (for callers' context)
- `prep_search` (low confidence) → `prep` (refresh structural context)
- `prep` → `prep_impact` (for hub files surfaced)

## Files likely touched

- `src/prep/mcp/server.py` — all tool handlers gain a suggestion
  appender
- Possibly a shared `src/prep/mcp/suggestions.py` to centralize
  the logic per tool

## Test plan

### Layer 1 — pytest

- `tests/test_next_steps_suggestions.py` (new)
  - Mock tool outputs with known finding types.
  - Assert appropriate next-step suggestions appear.
  - Assert no suggestions appear when none apply (don't pollute
    "all clear" responses).

### Layer 2 — live MCP probe

```
Before:
  prep_audit
  → findings list, no follow-up direction

After:
  prep_audit
  → findings list
  → ## Suggested Next Steps
  → - prep_impact(file_path='src/prep/mcp/server.py') for blast radius
```

## Acceptance

Part 08 is shipped when:

1. Each tool's response gains a `Suggested Next Steps` block when
   applicable.
2. Suggestions cite real call shapes the agent can copy.
3. No false-positive suggestions on empty / all-clear responses.

## Risks

- **Suggestion overload.** Mitigation: cap at 3 suggestions per
  response.
- **Stale suggestions** that point to deprecated tools / shapes.
  Mitigation: suggestions are code, not strings — generated from the
  same tool schemas so they stay in sync.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/07_Prioritized_Fix_Plan.md` FIX-7
