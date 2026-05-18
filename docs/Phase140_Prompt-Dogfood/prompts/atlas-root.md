# Atlas — root (multi-segment)

**File:** `src/prep/core/atlas/prompts.py:44-74` (SYSTEM at 44, PROMPT at 52)
**Symbols:** `ROOT_ATLAS_SYSTEM`, `ROOT_ATLAS_PROMPT`
**Invoked by:** `src/prep/core/atlas/generator.py` when project has >1 workspace segment
**Pipeline stage:** atlas (post-fast)
**Output schema:** plain text — global IDENTITY / STACK + WORKSPACE MAP that enumerates each segment with a one-liner; no per-segment deep dive (that's the segment atlas's job)
**Status:** baseline

## Purpose
Top-level orientation for multi-segment monorepos. The root atlas tells an agent "here's how the segments relate" before sending them to the per-segment doc.

## Grounding (inputs)
- All inputs the single-doc atlas gets
- Plus a workspace map with per-segment names, paths, file counts, primary languages

## Output schema
Plain text, similar to single-doc but WORKSPACE MAP carries weight (it must enumerate each segment briefly without trying to describe them in detail).

## Known issues / hypotheses
- **Segment-name fidelity**: the WORKSPACE MAP labels need to match the slugs that segment-atlas pages use, or cross-referencing breaks. Worth checking output names against `atlas/segments/` directory entries.
- **Cross-segment concerns**: instruction asks for CROSS-CUTTING domains. Outputs sometimes degenerate to generic "uses TypeScript" when the real cross-cutting concern is something subtle (e.g., shared MCP types). Capture and inspect.
- **Hub-file selection**: ROOT_ATLAS_PROMPT mentions hub files. Verify the hub files cited in output are the most-connected nodes (cross-check with `prep_impact`).

## Snapshot 2026-05-17
- Prompt source SHA: `6252f4eca4b2`
- Outputs captured:
  - Slot A (SourcePrep self — IS multi-segment): TBD
  - Slot B (small Py lib — likely single-segment, skip): N/A
  - Slot C (TS React): TBD if monorepo, else N/A
  - Slot D (monorepo, deferred): TBD when activated

## Iterations

_(none yet)_

## Open questions
- When the project has exactly 2 segments, is the root atlas useful or noise?
- Should the root atlas's CROSS-CUTTING section be deduplicated against per-segment CROSS-CUTTING?

## Cross-references
- Sibling: [atlas-segment](./atlas-segment.md), [atlas-single-doc](./atlas-single-doc.md)
- Memory: `project_brand_split.md`
