# Audit — Gap analysis

**File:** `src/prep/core/audit/prompts.py:80-110`
**Symbols:** `GAP_ANALYSIS_SYSTEM`, `GAP_ANALYSIS_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_gaps`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — misplaced imports, dead code, tech-debt indicators, dependency diagram
**Status:** baseline

## Purpose
Identifies "gaps" — code that isn't doing what its location suggests, dead branches, or accumulated debt that's signaling.

## Grounding (inputs)
- Dead-code candidates from structural analysis
- Misplaced imports (e.g., business logic imported from `utils/`)
- Tech-debt markers (TODOs, deprecated calls, `xfail` tests)

## Output schema
Markdown sections. Includes a "dependency diagram" — text-rendered, not graphical.

## Known issues / hypotheses
- **False-positive dead code**: structural dead-code detection misses dynamic dispatch and plugin loading. Hypothesis: prompt should be told "treat structural dead-code list as candidates only; explain why each is or isn't actually dead." Without that nudge, outputs are too confident.
- **Diagram quality**: text dependency diagrams are notorious for being wrong (mis-arrowed, mis-grouped). Worth comparing "include diagram" vs "omit diagram" outputs.
- **Tech debt double-counting**: this prompt and `audit-tech-debt` both surface tech debt. Verify they don't say contradictory things on the same items.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md)

## Iterations

_(none yet)_

## Open questions
- Should dead-code items in the output link to `prep_search` queries that would let the user verify?
- Drop the text dependency diagram entirely?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-architecture](./audit-architecture.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`
