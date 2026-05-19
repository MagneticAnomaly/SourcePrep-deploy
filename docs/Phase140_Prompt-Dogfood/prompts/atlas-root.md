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

### 2026-05-19: A1 — structural review (no PowerMate baseline; SourcePrep self is multi-segment)

**Type:** analysis-only (no Slot B output — PowerMate is single-segment so root-atlas does not fire there)

**Read materials:**
- `ROOT_ATLAS_SYSTEM` + `ROOT_ATLAS_PROMPT` (`atlas/prompts.py:44-70`) — 4 sections: IDENTITY / STACK / WORKSPACE MAP / CROSS-CUTTING.
- Budget: `compute_root_atlas_budget(file_count)` (`atlas/generator.py:508`); same 1.3× max-overflow rule as single-doc.

**Finding #1 — sibling of `atlas-single-doc`; same silent-section-drop risk under budget pressure.** ROOT_ATLAS_PROMPT requests 4 sections. If `compute_root_atlas_budget` returns a tight value, the same selective-skip behavior observed on `atlas-single-doc` Iteration #1 would apply. The fix proposed there (all-sections-present-even-if-shorter clause) is portable verbatim to this prompt.

**Finding #2 — WORKSPACE MAP format is well-specified.** Line 67: "List each segment with file count and primary role, one per line. Use 'name (dir_path, N files): role' format." Concrete format instruction. This is the kind of grounding-doc-§1-style specificity that batched prompts often lack.

**Finding #3 — IDENTITY constraint is one-sentence.** Line 65: "One sentence — what this project is and does." Same as `atlas-single-doc`. Good cross-prompt consistency.

**Finding #4 — CROSS-CUTTING is qualified "Only from data" (line 68).** Anti-hallucination guard against the over-abduction failure mode (grounding §9). Good.

**Verdict:** **analysis (no edit, no rerun possible without multi-segment baseline).** Three deferred actions:

1. **Capture a multi-segment baseline.** SourcePrep self is multi-segment and indexed at project_id `f1636374-abc6-410d-99ee-822120379e79`. The daemon could be pointed at it to generate a root atlas. Without output, this is structural review only.
2. **If `atlas-single-doc` Iteration #1's all-sections-present fix is shipped and validated**, port the same clause to this prompt.
3. **Sibling: `atlas-segment` has the same fix-portability case** — see [`atlas-segment.md`](./atlas-segment.md) Iteration #1.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (length calibration — same applies as single-doc).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 ("Only from data" is correct anti-hallucination phrasing).

**Cross-references:** [`atlas-single-doc.md`](./atlas-single-doc.md) Iteration #1 (same budget-vs-coverage finding from the side with data), [`atlas-segment.md`](./atlas-segment.md).

## Open questions
- When the project has exactly 2 segments, is the root atlas useful or noise?
- Should the root atlas's CROSS-CUTTING section be deduplicated against per-segment CROSS-CUTTING?

## Cross-references
- Sibling: [atlas-segment](./atlas-segment.md), [atlas-single-doc](./atlas-single-doc.md)
- Memory: `project_brand_split.md`
