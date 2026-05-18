# Part 03 — No-arg `prep` never returns a degraded atlas

> **Status:** Stub / **DEMOTED 2026-05-17 — not reproducible on current rebuild**
> **Triggers:** P82-F5 (new, 2026-05-13), P82-F6 (new, 2026-05-13)
> **Work order:** ships LAST in Phase 136 (regression guard only)

## Status update — 2026-05-17

Live probe against the freshly-rebuilt `.sourceprep` index returned
**798 modules / 10 segments**, matching `atlas.json` exactly. The
2026-05-13 baseline "1 of 10 modules" is no longer reproducible. The
original bug was likely state-specific (stale projection cache that
didn't survive the rebuild).

Part 03 is therefore **demoted from "must never happen" correctness
invariant to "regression guard only"**:

- Ship the invariant test (Layer 1 below) as a guard.
- Skip the runtime ERROR-level log and the three-hypothesis
  instrumentation — overkill for a bug we can't currently see.
- If the bug recurs on a future rebuild, this Part re-promotes; the
  full investigation plan below remains the reference.

See `00_Status_2026-05-17.md` for the probe evidence.

## The framing

A live `prep()` call with no arguments returning **less context than the
static `CLAUDE.md` atlas it would replace is a failure, not a trim
choice.** The dogfooding rule "call `prep` at the start of every task"
must hold — if it returns less than `CLAUDE.md` does, the rule is
actively misleading and agents that follow it lose context.

This is treated as a **correctness invariant**, not a polish item.
Part 03 ships a guard, an invariant test, and instrumentation across
all candidate root causes before patching a symptom.

## Reproduction (today, broken)

Observed 2026-05-10 and 2026-05-12: bare `prep()` call returned exactly
one module ("Roadmap & Sprint Planning Orchestrator") with `0 concepts (0
active, 0 seed) + 1 module rationale (0 active, 1 seed)`. Static atlas in
`CLAUDE.md` at the same moment carried all ten modules with rich
descriptions, hub files, and cross-cutting concerns.

## Candidate root causes (instrument all three)

1. **Module-filter / role-projection over-trim.** The Claude Code budget
   in `_CLIENT_BUDGETS` may apply a relevance threshold that ejects
   most modules when no query is supplied (relevance to "no query" is
   undefined → any positive threshold ejects).
2. **Atlas-source divergence.** The static `CLAUDE.md` atlas reads from
   on-disk `atlas.json`. The live `prep` call may read from a different
   in-memory source (a structural cache that hasn't re-hydrated since
   the last Finalize stage). Compare `core/atlas/loader.py` paths for
   `prep` vs the `CLAUDE.md` regeneration codepath.
3. **Project-id misrouting.** Bare `prep` may fall back to a
   default-project or most-recently-built project — possibly different
   from the project whose atlas `CLAUDE.md` was generated from.

Part 03 instruments **all three** before picking a fix. Patching one
hypothesis blindly leaves the others as latent regression paths.

## The invariant

```
For any no-arg prep() call:
  module_count_in_response >= module_count_in_on_disk_atlas_json
```

When `prep` is called without a query, no projection signal exists, so
no module-trim is legitimate. Any reduction below the on-disk count is
either a bug or an explicit user-opt (out of scope here).

## Files likely touched

- `src/prep/mcp/server.py` — `_CLIENT_BUDGETS`, ambient context handler,
  `_assemble_ambient_context` integration
- `src/prep/api/routers/projects/search.py` — `_assemble_ambient_context`,
  `_format_module_tiers` (no-query path)
- `src/prep/core/atlas/loader.py` — atlas source resolution
- `src/prep/core/atlas/generator.py` — confirm what `atlas.json` records
  vs what runtime serves

## Test plan

### Layer 1 — pytest

- `tests/test_no_arg_prep_invariant.py` (new)
  - Fixture project with N modules in `atlas.json`.
  - Call the MCP no-arg context path.
  - Assert returned module count ≥ N.
  - Parametrize across `_CLIENT_BUDGETS` entries (Claude Code,
    Cursor, Windsurf, default) — invariant must hold for every client.

- `tests/test_prep_atlas_source_parity.py` (new)
  - Build atlas.
  - Hit `_format_module_tiers` directly and the MCP no-arg path.
  - Assert both surface the same modules.

### Layer 2 — runtime guard

Add an ERROR-level log event in `_assemble_ambient_context`:

```python
on_disk = atlas_loader.module_count()
served = len(modules_in_response)
if not query and served < on_disk:
    logger.error(
        "no_arg_prep_degraded",
        on_disk=on_disk, served=served, client=client_id,
    )
```

Future regressions are loud, not silent. The audit/observability story is
half the value of Part 03.

### Layer 3 — live MCP probe

```
Before (2026-05-10 baseline):
  prep()
  → 1 module returned; CLAUDE.md atlas had 10

After:
  prep()
  → 10 modules returned; matches on-disk atlas.json count exactly
```

Re-grade `prep` no-arg in `99_Scorecard.md`.

## Acceptance

Part 03 is shipped when:

1. The three candidate root causes are instrumented and the actual root
   cause is identified by evidence, not guess.
2. The invariant test passes against the live MCP path.
3. The runtime guard logs degraded responses at ERROR.
4. Live probe returns module-count parity with `atlas.json`.

## Risks

- **Patching one root cause leaves others latent.** Mitigation:
  instrumentation lands before the fix, so we know which path the
  symptom came from.
- **Budget starvation.** If we stop trimming modules on no-query, the
  remaining budget for hub files / neighbors compresses. Mitigation:
  re-tune `_CLIENT_BUDGETS` if module-count parity blows out total
  output; verify against the FIX-16-1 cap that already bounds
  per-module text.

## Cross-refs

- `prep_observe` bug id `ff75c58924d7` (saved 2026-05-10)
- `docs/Phase82_MCP-Dogfooding/20_Followup_2026-05-13.md` §1
- MASTER_TODO entry: 2026-05-13 P82-F5 / P82-F6 (new)
