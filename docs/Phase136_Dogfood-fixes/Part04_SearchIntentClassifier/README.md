# Part 04 — `prep_search` intent classifier robustness

> **Status:** Stub / awaiting implementation plan
> **Triggers:** P82-F4 (2026-05-08), 18_Followup §1 (2026-05-09),
> 19_Followup Gap #1 (2026-05-11)
> **Work order:** ships after Part 01 (file-role split) — shares fixtures

## The pattern

Three independent dogfood observations converge on the same failure
mode: the intent classifier is brittle on natural-language descriptive
prose. Specifically:

1. **Locate/trace over-trigger on multi-word queries.**
   `"where is the file watcher debounce"` is auto-classified as
   `locate` (symbol mode), which expects a single bare token, returns
   `No symbols found matching: the file watcher debounce`, and fails
   closed instead of falling back to `explain`.
2. **Symbol-name-overlap classification on real natural language.**
   `"where is the prep no-arg ambient context budget assembled"`
   returned zero hits when the symbol obviously exists. Classifier
   matched on literal symbol-name overlap, not semantic intent.
3. **Multi-word descriptive queries collapse to `MASTER_ROADMAP.md`.**
   Two unrelated queries (`"file_hash staleness compare augmentation
   entry"` and `"incremental rebuild changed paths pipeline stage"`)
   both returned `MASTER_ROADMAP.md` with low confidence. Part 01 fixes
   the ranking side; this Part fixes the classification side.

## Why these are one Part

All three are bugs in `_classify_query_intent` (or its routing through
`tool_search`). Same handler, same fix surface, shared test fixtures.

## Files likely touched

- `src/prep/core/index.py` — `_classify_query_intent` (~lines 990–1080),
  `_intent_role_multipliers` (~1100–1110), token-set definitions
- `src/prep/mcp/server.py` — `tool_search` dispatch, NODE_NOT_FOUND
  fallback handling

## Proposed fixes

### F1 — Length-aware locate/trace gating

```
if intent in {"locate", "trace"} and len(query_tokens) >= 4:
    # Multi-word descriptive prose is almost never a literal symbol
    fall back to "explain"
```

A 7-token descriptive phrase is almost never a literal symbol name.

### F2 — NODE_NOT_FOUND retry

If `locate` / `trace` classification produces `NODE_NOT_FOUND` on a
multi-token query, automatically retry as `explain` before returning.
This saves the override-and-retry round-trip.

### F3 — Stricter locate trigger

Require one of:
- A single bare token, OR
- An `@path:line` shape, OR
- A clear `"where is X"` / `"find X"` pattern where X is a single
  identifier-like token

Multi-word descriptions should not trigger symbol mode.

## Test plan

### Layer 1 — pytest

- `tests/test_search_intent_classifier.py` (new, or extend Part 01's file)
  - Parametric table of `(query, expected_intent)` pairs covering all
    three failure modes above.
  - Assert `"where is the file watcher debounce"` resolves to `explain`
    (or `locate` that then retries as `explain`).
  - Assert NODE_NOT_FOUND auto-retry path produces a non-empty result.

### Layer 2 — live MCP probe

```
Before:
  prep_search "where is the file watcher debounce"
  → NODE_NOT_FOUND: Node not found: the file watcher debounce

After:
  → AutoRebuildWatcher._on_coverage_check @ src/prep/core/watcher.py:...
```

Same probe for the two collapsed-to-MASTER_ROADMAP queries — they
should return real code locations after Part 04 + Part 01 both ship.

## Acceptance

Part 04 is shipped when:

1. Multi-token descriptive queries no longer return NODE_NOT_FOUND.
2. NODE_NOT_FOUND is never a user-visible response from `prep_search`
   (matches the Phase 124 thesis).
3. Live probes on the three trigger queries return useful results.

## Risks

- **Over-fallback to `explain`.** If every short query falls back, the
  symbol-mode performance gains evaporate. Mitigation: F3's strict
  locate trigger keeps symbol mode for the right shape of query.
- **Coupling with Part 01.** Some test fixtures may be shared. Land
  Part 01 first to avoid double work.

## Cross-refs

- `docs/Phase82_MCP-Dogfooding/18_Followup_2026-05-09.md` §1
- `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` Gap #1
- MASTER_TODO: P82-F4 entry
