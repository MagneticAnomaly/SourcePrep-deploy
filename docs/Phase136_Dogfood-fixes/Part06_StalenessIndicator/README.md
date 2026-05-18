# Part 06 — Staleness indicator on MCP responses

> **Status:** Stub / awaiting implementation plan
> **Trigger:** FIX-9 (Phase 82 prioritized fix plan, P2)
> **Work order:** first of Cluster F (06–08)

## Why this ships before Parts 07 and 08

Staleness is a **correctness signal** — agents should not act on stale
data. Parts 07 (`detail` parameter) and 08 (next-steps suggestions) are
pure ergonomics. Correctness ships first inside the Cluster F group.

## The gap

MCP responses do not indicate when the underlying index was last built
or how many pending file changes the watcher has captured but not yet
processed. Agents act on data without knowing whether it reflects the
current code state.

## The fix shape

Add a freshness envelope to every MCP response:

```json
{
  ...response body...,
  "_freshness": {
    "last_build_at": "2026-05-17T10:42:13Z",
    "pending_changes": 7,
    "staleness": "fresh|recent|stale"
  }
}
```

Where:

- `fresh`: built within the last N minutes, 0 pending changes
- `recent`: built within the last N minutes, some pending
- `stale`: build older than threshold OR many pending changes

Threshold and pending-count cutoffs tunable; sensible defaults
TBD in plan.

## Files likely touched

- `src/prep/mcp/server.py` — envelope wrapping at response time
- `src/prep/core/watcher.py` — expose last-build timestamp and
  pending-changes count (per Phase 82 FIX-9 sketch)
- `src/prep/mcp_tools.py` — schema additions (optional response field)

## Test plan

### Layer 1 — pytest

- `tests/test_freshness_envelope.py` (new)
  - Mock watcher state with known timestamps and pending counts.
  - Assert envelope appears on every MCP response.
  - Assert staleness classification matches expectations across
    cutoff boundaries.

### Layer 2 — live MCP probe

```
Before:
  any tool call
  → no freshness signal

After:
  prep_search "..."
  → {..., "_freshness": {"last_build_at": "...", "pending_changes": 0,
                          "staleness": "fresh"}}
```

Touch a file, wait for watcher capture, re-call without rebuilding —
expect `staleness: recent` and `pending_changes >= 1`.

## Acceptance

Part 06 is shipped when:

1. Every MCP tool response carries the `_freshness` envelope.
2. Touching a file moves a fresh response to `recent` or `stale`.
3. A daemon restart followed by no rebuild correctly reports an old
   `last_build_at`.

## Risks

- **Envelope clutter** if agents don't surface it. Mitigation: keep
  the envelope small, document the convention in `AGENTS.md` /
  generated rules.
- **Threshold misconfiguration.** Mitigation: cutoffs read from config
  with sensible defaults; tunable per-project.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/07_Prioritized_Fix_Plan.md` FIX-9
