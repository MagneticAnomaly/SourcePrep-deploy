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

### 2026-05-19: A1 — sections silently dropped under budget pressure

**Type:** analysis-only (proposes a concrete prompt edit)

**Read materials:**
- `ATLAS_SYSTEM` + `ATLAS_PROMPT` (`atlas/prompts.py:9-39`) — prompt requires 5 sections in order: IDENTITY / STACK / ARCHITECTURE / FLOW / CROSS-CUTTING.
- `atlas/generator.py:205-248` — calls the prompt with `target_chars = max(MIN_ATLAS_CHARS=1200, compute_atlas_budget(file_count))`, `max_chars = target_chars * 1.3` (so for PowerMate's 24 files: target=1200, max=1560). Post-processor truncates at max_chars at last sentence/newline.
- PowerMate Slot B output: [`../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn.json`](../snapshots/2026-05-17_baseline/outputs/atlas-single-doc/powermate-reborn.json) — `char_count: 1551`, model: `kimi-k2.6:cloud`.

**Finding #1 — captured output has 3 of 5 required sections.** Required: IDENTITY, STACK, ARCHITECTURE, FLOW, CROSS-CUTTING. Actually emitted: IDENTITY, STACK, ARCHITECTURE. The FLOW and CROSS-CUTTING sections were dropped — not emitted as `(insufficient data)` per system-prompt rule 2, but silently omitted.

The output is right at the budget ceiling (1551 of 1560). This means one of:
- **(a) Model self-throttled.** Kimi K2.6 saw "Target {target_chars} characters. Do not exceed {max_chars}" and stopped early, prioritizing early sections.
- **(b) Post-processor truncated.** Model emitted >1560 chars; `_postprocess` cut at last sentence/newline, which happened to land at the end of ARCHITECTURE.

Either way the result is the same: the prompt asks for 5 sections, the user (an AI agent reading this atlas) gets 3. There is no "(insufficient data)" marker for the missing sections — the agent has no signal that FLOW and CROSS-CUTTING were attempted-and-failed vs intentionally-not-applicable.

**Finding #2 — quality of the 3 emitted sections is excellent.** Where it does write, the output is dense and grounded:
- IDENTITY (one sentence): "PowerMateReborn is a native Swift menu-bar macOS app that resurrects Griffin PowerMate USB/Bluetooth controllers for modern macOS, providing volume, brightness, MIDI, and custom application-profile control modes with per-app profiles and Sparkle auto-updates."
- STACK: precise file counts ("Swift 15 files, Markdown 6, XML 2, Shell 1"), runtime version ("macOS 13 minimum"), framework list with private APIs called out ("private DisplayServices and IOKit I2C via dlopen").
- ARCHITECTURE: 5 layers with file counts AND incoming-edge counts ("PowerMateManager.swift (gesture/LED coordination hub, 13 incoming edges)"). Hub annotations are useful — that's exactly the kind of file an agent should be careful editing.

Plain-text rule honored (no markdown). Brand: uses "PowerMateReborn" not internal slug. Memory `project_brand_split.md` check: passes.

**Finding #3 — `compute_atlas_budget(24 files) ≈ 1200 chars` is too tight for 5 sections at the requested density.** Rough math: 5 sections × ~300 chars each = 1500 chars (excluding section labels and blank lines). At 1200 target / 1560 max, the model has effectively ~240-300 chars per section. ARCHITECTURE alone consumed ~900 chars (well over its share), leaving nothing for FLOW + CROSS-CUTTING. The model made the right per-section trade-off (ARCHITECTURE is the most useful section for a 24-file project) but did it silently.

For a fresh AI agent opening this repo via `prep()`, reading the atlas: it would see 3 sections, not know that 2 are missing, and not have FLOW guidance (how events propagate) or CROSS-CUTTING (shared deps/patterns).

**Two paths to fix:**

**(A) Edit the prompt to enforce all-sections-present even if shorter.** Add to `ATLAS_PROMPT` after the section listing:

> **Section budget allocation:** All five sections MUST appear in your output. If the target character count cannot fit dense paragraphs for each, write shorter entries per section — better to emit a 1-sentence FLOW and 1-sentence CROSS-CUTTING than to omit them. If a section truly has no distinct content (e.g. the project is too small for distinct CROSS-CUTTING beyond what ARCHITECTURE already covers), emit the section label followed by "(see ARCHITECTURE)" or "(insufficient data)" — DO NOT silently skip the section. Agents reading this need to know the section was considered.

- **Pro:** in scope (prompt copy only). Addresses both failure modes — model self-throttle AND post-processor truncation (post-processor will still cut, but the model will allocate budget proportionally, so the last section to be cut would be CROSS-CUTTING's "(see ARCHITECTURE)" not the full section).
- **Con:** for tiny projects, the "(see ARCHITECTURE)" sections add ceremony.
- **Estimated impact:** PowerMate atlas would gain 2 short sections (~50-100 chars each) at the cost of slightly trimming ARCHITECTURE.

**(B) Raise the budget floor.** Change `MIN_ATLAS_CHARS` from 1200 to ~1800. Out of Phase 140 scope (routing.py / budget logic, not prompt copy).

**Verdict:** **analysis (no edit shipped this iteration).** Path A is in scope and addresses the silent-skip behavior. The PowerMate atlas works as-is — but the silent failure mode means small-project users get a degraded, non-self-describing atlas.

Confidence in shipping Path A without rerun: **85%.** The risk is the model interpreting "shorter entries per section" too literally and emitting 5 one-word sections instead of allocating. Worth testing on PowerMate after restart.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (Claude calibrates response length — explicit per-section budget instructions work better than overall length target alone).
- Memory: `feedback_marketing_voice.md` — terse and grounded is correct; the issue isn't density, it's coverage.

**Cross-references:** [`atlas-root.md`](./atlas-root.md), [`atlas-segment.md`](./atlas-segment.md) (siblings — likely same budget-vs-coverage pattern when run on a multi-segment repo).

## Open questions
- Should IDENTITY lead with the user-facing product name or the inferred project name from `pyproject.toml` / `package.json`?
- Are workspace-map bullets useful for single-segment projects, or do they always degenerate to "the whole repo"?

## Cross-references
- [Phase 136 — Part 11: Atlas stale after rebuild](../../Phase136_Dogfood-fixes/Part11_AtlasStaleAfterRebuild/) (behavioral, not prompt)
- Memory: `project_brand_split.md`
