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

### 2026-05-19: A1 — structural review + corrects page stub schema

**Type:** analysis-only (no baseline; SourcePrep self would generate this for each segment)

**Read materials:**
- `SEGMENT_ATLAS_SYSTEM` + `SEGMENT_ATLAS_PROMPT` (`atlas/prompts.py:75-117`).

**Correction to page stub schema (line 7) — page says "IDENTITY / STACK / WORKSPACE MAP / CROSS-CUTTING" (4 sections, copy-pasted from root-atlas). Actual prompt requires SIX sections** in this order:

1. SEGMENT (header line with segment name + dir + file count — template-filled)
2. ROLE — what this subsystem does
3. KEY FILES — `filename: purpose` per line
4. INTERNAL FLOW — concrete file-by-file data/control flow within segment
5. DEPENDENCIES — which other segments this one depends on or serves. "Only from data."
6. STATUS — implementation maturity + tech debt. If none, write "(none flagged)"

Page `## Output schema` block should be updated to reflect actual 6-section structure.

**Finding #1 — anti-fabrication discipline is stronger here than in root-atlas.** System prompt lines 76-82 carry 7 rules including:
- Rule 2: "Every claim must come from the provided data. Do not invent file names, class names, or functionality not present in the FILE LISTING or MODULE SUMMARIES."
- Rule 3: "Use ONLY exact file paths and names from the FILE LISTING. Never fabricate file names."
- Rule 5: "If data is insufficient for a section, write '(insufficient data)' rather than guessing."

And the user prompt repeats it (line 106): "IMPORTANT: Only reference files that appear in the FILE LISTING above. Do not invent file names."

Repeating the same instruction in both system and user prompt is a known emphasis pattern for high-stakes anti-hallucination requirements. Grounding §9 supports: when failure mode is fabrication, double-state the prohibition.

**Finding #2 — STATUS section's "(none flagged)" fallback is well-designed.** Line 115: "If none flagged, write '(none flagged)'." This is the explicit-fallback pattern that `atlas-single-doc` LACKS for its FLOW / CROSS-CUTTING sections (where the model silently skips instead of falling back). Worth porting the same explicit-fallback discipline to `atlas-single-doc`'s prompt.

**Finding #3 — same budget-vs-coverage risk as the other atlas prompts.** Six sections is more than `atlas-single-doc`'s five. If `compute_atlas_budget` (or whatever the segment-budget function is) returns a tight value for a small segment, the silent-skip mode observed on `atlas-single-doc` would be even worse here.

**Verdict:** **analysis (no edit, no PowerMate baseline to validate against).** Three deferred actions:

1. **Update page stub** to reflect actual 6-section schema (not the copy-pasted 4-section one).
2. **Capture a multi-segment baseline.** SourcePrep self would generate this per-segment.
3. **If `atlas-single-doc` Iteration #1's all-sections-present fix ships**, port to this prompt too. The fix is even more important here because (a) more sections, (b) STATUS already demonstrates the explicit-fallback pattern, so consistency arg is stronger.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield + Constitutional AI: explicit anti-hallucination doubled across system and user prompts).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (length calibration).

**Cross-references:** [`atlas-single-doc.md`](./atlas-single-doc.md) Iteration #1, [`atlas-root.md`](./atlas-root.md) Iteration #1.

## Open questions
- For a segment <10 files, should we suppress the atlas entirely?
- Should CROSS-CUTTING be omitted for segments that are leaf libraries (no children)?

## Cross-references
- Sibling: [atlas-root](./atlas-root.md), [atlas-single-doc](./atlas-single-doc.md)
- Memory: `project_brand_split.md`
