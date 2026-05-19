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

### 2026-05-18: observation — Generate produces high-quality implementation claims that Validate cannot confirm

**Type:** observation (no edit)

**What I noticed** while auditing concept-validate's 53% reject rate on PowerMate: Generate is producing implementation-specific candidates that look substantively correct (dlopen patterns, gamma isolation, OSC byte ordering, signal handler patterns), but Validate rejects most of them because the upstream grounding doesn't include the actual file content needed to falsify them.

**This is not a Generate bug.** Generate is producing exactly the kind of concept the project wants — concrete, falsifiable, anchored to specific files. The problem is downstream.

But this surfaces an opportunity for Generate: if we **could** know whether downstream will have grounding for a given concept, Generate could be asked to either (a) defer generating concepts whose anchors lack rationale-level grounding, or (b) include the file slice it relied on as part of the candidate (which Validate could then re-use).

**Verdict:** **observation, no edit.** Real action belongs on the upstream grounding pipeline (path A in [`concept-validate.md`](./concept-validate.md) Iteration #1) or on Validate (path B). Generate is not the right lever.

**Cross-references:** [`concept-validate.md`](./concept-validate.md) Iteration #1, [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md)

### 2026-05-19: B2 — Generate prompt audit (scope-tighten precedent + swarm dedup overhead)

**Type:** analysis-only (no prompt edit)

**Read materials:**
- `_GENERATE_SYSTEM_HEADER` + `build_generate_system_prompt` (`concept_generate_prompt.py:96-117`) — per-worker scope orientation prepended to `SYNTH_SYSTEM_PROMPT`.
- `build_generate_user_prompt` (`concept_generate_prompt.py:146-229`) — per-worker user prompt with payload composition (atlas, segments, full+headings docs, in-scope rationale, spaghetti, antibodies).
- `WorkerPayload` dataclass (`concept_generate_prompt.py:32-52`) — the per-scope filtered grounding shape, **with `audit_findings` deliberately omitted** (see docstring at lines 44-47).
- Snapshot: `swarm_size=3, candidates_after_dedup=19, rationale_count=46, prompt_revision=2`.

**Observation #2 — `audit_findings` deliberate omission is a thoughtful scope-tighten worth flagging as a pattern.** Lines 44-47 + lines 197-200 document that `audit_findings` was previously passed to Generate but caused emit of bug-description-shaped pseudo-concepts ("X causes Y desync", "Module Z has known issue Q"). The fix was scope-tightening at the grounding layer rather than adding more "DO NOT EMIT BUG REPORTS" instructions to `SYNTH_SYSTEM_PROMPT` (which it already has — see lines 329-350 of `concept_synthesizer.py`). This is the right move and is a **transferable design pattern**: when an emit-shape violation persists despite a prompt-level prohibition, the more durable fix is to remove the failure-mode-generating grounding rather than restate the prohibition. Worth citing in the methodology doc when a similar issue arises (e.g., if `epistemic-doc` emits architecture findings that belong in `audit-architecture`, look first for grounding-layer overlap).

**Observation #3 — 60% inter-worker overlap (46 rationales → 19 candidates) suggests scope dimensions are not orthogonal.** The current swarm runs 3 workers in parallel, each with `scope.categories` defined by `WorkerScope` (lives in `concept_generate_grounding.py`). 60% dedup is high; in the limit of perfectly-orthogonal scopes the dedup rate would be near 0% (each worker emits candidates the others don't). 60% means workers are independently surfacing the same patterns from the same grounding, which the per-worker rationale filter is supposed to prevent. Two diagnostics worth running:

   1. Is `filter_rationale_by_scope` returning sufficiently disjoint slices? If three workers each see the same top-N rationale items, identical output is the expected behavior.
   2. Are the scope `categories` lists themselves overlapping (e.g., one scope claims "architecture, decision" and another claims "architecture, constraint" — both will surface architecture rationale)?

   This is *not* a prompt-copy iteration; it's a scope-design iteration that lives in `concept_generate_grounding.py:WorkerScope`. Flagging here for the next concept-pipeline architecture pass.

**Observation #4 — `SYNTH_SYSTEM_PROMPT` reuse means any edit to that prompt propagates to Generate workers.** `build_generate_system_prompt` returns `scope_block + SYNTH_SYSTEM_PROMPT` (line 117). Concept-synthesize Iteration #1 considered two candidate edits to `SYNTH_SYSTEM_PROMPT`: (a) groundedness gate, (b) anti-echo gate. **Both would also reshape Generate behavior.** Specifically: a groundedness gate added to `SYNTH_SYSTEM_PROMPT` would cause Generate workers to also suppress implementation-detail claims at emit time — possibly reducing dedup overhead (workers emit fewer candidates that downstream all reject) and possibly reducing the false-implementation-claim shape that surfaces in `concept-validate`. This is a useful coupling. When prototyping any `SYNTH_SYSTEM_PROMPT` edit, capture both Generate output (`concept-generate/`) and Synthesize output (`concept-synthesize/`) and compare both.

**Verdict:** `analysis (no edit)`. Generate's prompt copy is well-engineered; failures here are upstream (scope orthogonality) or downstream (grounding shape).

**Recommended next iterations (out of this session):**
1. Audit `WorkerScope` definitions for category-overlap (out of Phase 140 prompt-copy scope; belongs to Phase 125c architecture).
2. When testing any `SYNTH_SYSTEM_PROMPT` edit (from concept-synthesize), capture Generate output too — the prompt is shared between sites.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §10 (Batched prompts: position-effect, BatchPrompt order-shuffling) — applicable to Generate swarm output ordering across workers.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §4 (Self-Refine: role separation > unified critic) — Generate (producer) ↔ Validate (critic) split is consistent with the published architecture.

**Cross-references:** [`concept-synthesize.md`](./concept-synthesize.md) Iteration #1 (shared `SYNTH_SYSTEM_PROMPT`), [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md).

## Open questions
- Should worker prompts include "things the other workers are looking for" (negative scoping) to reduce overlap?
- Does antibody-pattern grounding actually help worker output, or is it noise?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-validate](./concept-validate.md), [concept-t3-refine](./concept-t3-refine.md)
- Memory: `project_swarm_toggle_design.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
