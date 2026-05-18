# Part 02 — `prep_impact` correctness: bimodal-node twins

> **Status:** Stub / awaiting implementation plan
> **Triggers:** P122-D1, P122-D2, P122-D3 (MASTER_TODO 2026-05-13),
> 19_Followup Gap #2 (2026-05-11)
> **Work order:** ships first in Phase 136 (correctness > thinness)

## The bug in one paragraph

For any Python module imported via `from prep.core.X import Y`,
`prep_impact(file_path="src/prep/core/X.py", direction="dependents")`
returns `0 dependents`. The trace graph carries two nodes for the same
file: a `file:` node and an `external_module` twin (e.g.
`prep.core.roadmap_miner` with empty path). The `from package.x import y`
syntax lands incoming import edges on the `external_module` side, but
`tool_impact`'s dependents path queries only the file-node side. Result:
the file looks orphaned even when it has hundreds of callers.

This silently biases the Custodian LLM verifier (`CustodianEngine._get_impact`,
`src/prep/agents/custodian/engine.py:51`) toward `safe_to_delete` for any
package-imported module. That is the urgent fire.

## Reproduction (today, broken)

```
prep_impact(file_path="src/prep/core/__init__.py", direction="dependents")
→ "0 dependents"   # truth: hundreds
prep_impact(file_path="src/prep/core/augmenter.py", direction="dependents")
→ "4 dependents"   # truth: index.py, epistemic_enrichment.py,
                   #         orchestrator, worker_factory, many tests
prep_impact(file_path="src/prep/services/pipeline/workers.py", direction="dependents")
→ "2 dependents"   # truth: 2 (control case, single-file imports)
```

Diagnostic: `prep_search type=symbol "roadmap_miner"` returns two nodes
— a file node AND a separate `external_module` node with empty path.

## Findings folded in

| ID | Description |
|---|---|
| P122-D1 | Build a tiny fixture project and reproduce the edge-loss |
| P122-D2 | Aggregate dependents across file ↔ external_module twins |
| P122-D3 | When `file_path` resolves to no graph node, return "not indexed", not silent `0 dependents` |
| 19_Followup Gap #2 | `augmenter.py` under-stated blast radius (same root cause) |

## Files likely touched

- `src/prep/mcp/server.py` — `tool_impact` handler (around line 4280;
  `dependents` direction routes differently than `dependencies` / `all`)
- `src/prep/core/trace/index.py` — underlying impact lookup
- `src/prep/agents/custodian/engine.py:51` — downstream consumer
  (no change needed in this part, but verify `_get_impact` benefits
  from the fix without further wiring)

## Test plan

### Layer 1 — pytest

- `tests/test_prep_impact_bimodal.py` (new)
  - Fixture: 3-file tmp project, `pkg/a.py`, `pkg/b.py`, `consumer.py`
    where `consumer.py` does `from pkg.a import foo`.
  - Build a real index against the fixture (no mocks at the seam under
    test — per `feedback_test_full_import_chain` memory).
  - Assert `prep_impact("pkg/a.py", direction="dependents")` returns 1, not 0.
  - Assert `prep_impact("pkg/b.py", direction="dependents")` returns 0
    (no callers — control case).
  - Assert `prep_impact("nonexistent.py", direction="dependents")`
    returns a "not indexed" indicator, not silent zero.

### Layer 2 — live MCP probe

```
Before:
  prep_impact(file_path="src/prep/core/augmenter.py", direction="dependents")
  → 4 nodes (today)

After:
  → ≥ 5 (paste verbatim post-fix; should include index.py,
         epistemic_enrichment.py, orchestrator, worker_factory, tests/*)
```

Re-run against `src/prep/core/__init__.py` and paste the new dependent
count (should be in the hundreds).

## Acceptance

Part 02 is shipped when:

1. Pytest fixture asserts twin aggregation.
2. Live MCP probe on `augmenter.py` returns the realistic dependent set.
3. `prep_impact` on an unindexed path returns an explicit "not indexed"
   message, not `0 dependents`.
4. `CustodianEngine._get_impact` is re-run against the same fixture and
   no longer returns `dependent_count=0` for the consumer's import target.

## Risks

- **Possible double-counting** if file-node and external_module both
  carry the same edges. Mitigation: deduplicate by edge identity, not
  by node identity.
- **Performance** on hub files (`__init__.py` may have hundreds of
  reverse edges). Mitigation: existing `prep_impact` markdown output
  is already capped — verify no new cap is needed.

## Cross-refs

- `prep_observe` bug id `bd79badde4d2`
- MASTER_TODO entry: 2026-05-13 Phase 122 dogfood finding section
