# Concept — Generate (swarm)

**File:** `src/prep/core/concept_generate_prompt.py:96-237`
**Symbols:** `_GENERATE_SYSTEM_HEADER`, `build_generate_system_prompt`, `build_generate_user_prompt`, `build_worker_prompt`
**Invoked by:** Generate swarm workers (Phase 125c T2b) — one worker per category dimension
**Pipeline stage:** synth (Generate pass)
**Output schema:** JSON list of candidate concepts scoped to the worker's assigned category dimensions
**Status:** baseline

## Purpose
Swarm worker prompt that produces candidate concepts. Each worker is scoped to a subset of category dimensions (e.g., "constraints", "architecture decisions", "domain rules") so the swarm covers more ground than a single call.

## Grounding (inputs)
- Atlas summary
- Segment list with hub files
- Doc excerpts (rationale snippets)
- Spaghetti hotspots
- Antibody patterns (constraint violations the immune system has spotted)
- Worker's assigned category dimensions

## Output schema
JSON list. Each candidate: `{title, dimension, draft_rationale, anchors[]}`. Workers are explicitly told not to issue verdicts — that's Validate / T3 Refine's job downstream.

## Known issues / hypotheses
- **Swarm toggle** (memory: `project_swarm_toggle_design.md`). `swarm_enabled` defaults ON as a safety valve on top of capability check — do not remove that flag in any iteration. Outputs may differ when the swarm is off vs on; capture both.
- **Category coverage**: workers are scoped by category dimensions. Hypothesis: the dimension list (defined where?) may have gaps — worth checking that outputs cover the categories users actually care about.
- **Cross-worker dedup**: separate workers may produce near-identical candidates. Dedup happens via anchor-overlap clustering upstream of Validate. Hypothesis: the prompt could be tightened to push workers to differentiate (mention dimension explicitly in titles).

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `a474170fc6bd`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): all 66 concept records (pre-Validate state visible in `seed` status — 47 of 66): [`../snapshots/2026-05-17_baseline/outputs/concept-generate/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-generate/powermate-reborn-concepts.json)
  - **Generate-stage stats** (from manifest): `swarm_size: 3, candidates_after_dedup: 19, rationale_count: 46, prompt_revision: 2`. See [`_run-metadata/powermate-reborn-concept-generate-2026-05-18.json`](../snapshots/2026-05-17_baseline/outputs/_run-metadata/powermate-reborn-concept-generate-2026-05-18.json)
  - **Observation**: 3 workers produced 46 rationales → deduped to 19 candidates. That's ~60% dedup rate — high overlap between workers. Possible iteration: tighter per-worker category scoping per grounding doc.

## Iterations

_(none yet)_

## Open questions
- Should worker prompts include "things the other workers are looking for" (negative scoping) to reduce overlap?
- Does antibody-pattern grounding actually help worker output, or is it noise?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-validate](./concept-validate.md), [concept-t3-refine](./concept-t3-refine.md)
- Memory: `project_swarm_toggle_design.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
