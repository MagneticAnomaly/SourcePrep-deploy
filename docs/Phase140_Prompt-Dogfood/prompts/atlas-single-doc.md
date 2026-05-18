# Atlas — single-doc

**File:** `src/prep/core/atlas/prompts.py:9-43` (SYSTEM at 9, PROMPT at 17)
**Symbols:** `ATLAS_SYSTEM`, `ATLAS_PROMPT`
**Invoked by:** `src/prep/core/atlas/generator.py`
**Pipeline stage:** atlas (post-fast)
**Output schema:** plain text (no markdown), 4 fixed sections (IDENTITY / STACK / WORKSPACE MAP / CROSS-CUTTING) ending with a `---` separator
**Status:** baseline

## Purpose
Produces the single-doc Codebase Atlas for small / single-segment projects. The atlas is embedded into AGENTS.md and served back via the MCP `prep` tool as the structural orientation an AI agent reads first.

## Grounding (inputs)
- Project identity hints (name, repo path, languages, file counts)
- Stack summary (frameworks, build tooling)
- Workspace structure (file inventory, hub files, entry points)
- Optional focus areas

## Output schema
Plain text, 4 sections in fixed order. Instruction is "no markdown, no headings beyond the labels." Downstream parser (atlas/generator.py + atlas/models.py) splits on the label words.

## Known issues / hypotheses
- **Brand split risk** (memory: `project_brand_split.md`). The atlas must surface user-facing names ("SourcePrep", "sourceprep.io") not internal slugs ("prep", "@prep/*"). Worth checking outputs for accidental code-slug leakage.
- **Markdown leakage**: instruction says "no markdown" but cloud LLMs frequently add headers/bullets anyway. Downstream parsing tolerates this; check whether the prose quality differs when the model is allowed vs forbidden from using markdown.
- **Unknown — needs baseline capture before further hypothesizing.**

## Snapshot 2026-05-17
- Prompt source SHA: `6252f4eca4b2`
- Outputs captured:
  - Slot A (SourcePrep self): TBD — `../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/sourceprep.json`
  - Slot B (PowerMateReborn, Swift, single-segment): [`../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn.json`](../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn.json) — generated 2026-04-30 by `kimi-k2.6:cloud`
  - Plus per-role projections: [`powermate-reborn-role-architect.txt`](../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn-role-architect.txt), [`powermate-reborn-role-intern.txt`](../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn-role-intern.txt)
  - Slot C: TBD

## Iterations

_(none yet)_

## Open questions
- Should IDENTITY lead with the user-facing product name or the inferred project name from `pyproject.toml` / `package.json`?
- Are workspace-map bullets useful for single-segment projects, or do they always degenerate to "the whole repo"?

## Cross-references
- [Phase 136 — Part 11: Atlas stale after rebuild](../../Phase136_Dogfood-fixes/Part11_AtlasStaleAfterRebuild/) (behavioral, not prompt)
- Memory: `project_brand_split.md`
