# Concept — Synthesize

**File:** `src/prep/core/concept_synthesizer.py:292-527`
**Symbols:** `SYNTH_SYSTEM_PROMPT`, `build_synthesis_prompt`
**Invoked by:** `concept_synthesizer.synthesize_concepts()` — called once per project, terminal stage of the concept pipeline (Phase 125c)
**Pipeline stage:** synth
**Output schema:** structured JSON list of concepts with tier (T1/T2/T3), title, rationale, anchors, assertions
**Status:** baseline

## Purpose
Synthesizes cross-cutting concepts from the full grounding (atlas, audit findings, anchor-overlap clusters, doc bodies). This is where Generate-pass candidates get promoted to project-level concepts.

## Grounding (inputs)
- Atlas (root + segments)
- Audit summary
- Anchor-overlap clusters (concept candidates that share file anchors)
- Hub files and cross-cutting domains
- Doc excerpts

## Output schema
JSON list. Each concept: `{title, tier, rationale, anchors[], assertions[]}`. Rubric defines T1 (clear truth) / T2 (true with caveats) / T3 (boundary / aspirational). Banned outputs include vacuous concepts ("this project uses code"), trivial concepts, and concepts that fail the falsification step.

## Known issues / hypotheses
- **Wall-time regression** (memory: `project_synthesizer_wall_time_regression.md`). 900s cloud budget consumed by workers + T4 enrichment, synthesis silently fails, questions lost. Budget bumped to 1500s on 2026-05-02 — verify the prompt is not contributing to runtime by being prolix.
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). The prompt should use the named-tier rubric and ask for rationale BEFORE tier (avoids social-register clumping of floats). Verify SYNTH_SYSTEM_PROMPT does this; if not, that's a likely first iteration.
- **Concept promotion strategy** (memory: `project_concept_promotion_strategy.md`). 1,590 candidates is unacceptable for manual review; anchor-overlap clustering is the lever. Worth inspecting whether the synthesis prompt is producing too many T2/T3 candidates that should be deduped via anchor overlap upstream.

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `b35e784e3abd`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): captured 2026-05-18 from a fresh Phase 125c pipeline run (model: `kimi-k2.6:cloud`, 163s elapsed, swarm_size 3, prompt_revision 2)
    - All 66 concept records (status: 6 active / 10 archived / 47 seed / 3 triage_pending): [`../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-concepts.json)
    - 36 concept questions: [`../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-questions.json`](../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-questions.json)
  - Per pipeline metadata: 19 synth_concepts_emitted, 19 saved, 6 val_activated, 3 val_triaged, 10 val_archived, 0 val_parse_failures, 36 questions_created. See [`_run-metadata/powermate-reborn-pipeline-2026-05-18.json`](../snapshots/2026-05-17_baseline/outputs/_run-metadata/powermate-reborn-pipeline-2026-05-18.json)

## Iterations

_(none yet)_

## Open questions
- Does the rubric's tier definitions need few-shot examples (concept-t3-refine has them — should synth match)?
- Are "banned outputs" enforced — i.e., do real outputs ever fall into the banned categories?

## Cross-references
- Sibling: [concept-validate](./concept-validate.md), [concept-t3-refine](./concept-t3-refine.md), [concept-generate](./concept-generate.md)
- Memory: `project_synthesizer_wall_time_regression.md`, `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
