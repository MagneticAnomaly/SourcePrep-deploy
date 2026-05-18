# Atlas — segment

**File:** `src/prep/core/atlas/prompts.py:75-117` (SYSTEM at 75, PROMPT at 84)
**Symbols:** `SEGMENT_ATLAS_SYSTEM`, `SEGMENT_ATLAS_PROMPT`
**Invoked by:** `src/prep/core/atlas/generator.py` once per workspace segment
**Pipeline stage:** atlas (post-fast)
**Output schema:** plain text — segment-scoped IDENTITY / STACK / WORKSPACE MAP / CROSS-CUTTING (segment-internal cross-cutting, not project-wide)
**Status:** baseline

## Purpose
Per-segment orientation in a multi-segment project. Each segment (e.g., `packages/ui`, `src/prep/dashboard`, `websites/apps/marketing`) gets its own atlas so segment-focused work doesn't have to chew on the whole monorepo.

## Grounding (inputs)
- The single segment's file inventory
- Segment-scoped hub files and entry points
- Brief reference to the root atlas (so the segment doesn't repeat the global stack)

## Output schema
Plain text, same 4-section shape as single-doc atlas but scoped. Instruction explicitly forbids fabrication when the segment is small / underspecified.

## Known issues / hypotheses
- **Small-segment fabrication**: very small segments (10-20 files) tempt the LLM to invent purpose. The "no fabrication" instruction is there for a reason; worth A/B testing variants that say it more or less aggressively.
- **Naming inheritance**: segment IDENTITY often re-uses parent product naming. Should each segment have its own micro-identity, or inherit?
- **Cross-segment leakage**: instruction says "segment-internal cross-cutting" but outputs sometimes drift to project-wide concerns. Capture and inspect.

## Snapshot 2026-05-17
- Prompt source SHA: `6252f4eca4b2`
- Outputs captured:
  - Slot A (SourcePrep self — multiple segments): TBD per segment
  - Slots B/C: N/A unless multi-segment

## Iterations

_(none yet)_

## Open questions
- For a segment <10 files, should we suppress the atlas entirely?
- Should CROSS-CUTTING be omitted for segments that are leaf libraries (no children)?

## Cross-references
- Sibling: [atlas-root](./atlas-root.md), [atlas-single-doc](./atlas-single-doc.md)
- Memory: `project_brand_split.md`
