# 08 — Surprises and Product Feedback

Incidental findings from the Phase 116 exploration that are **not about the
overseer idea specifically**. Some are actionable independently. Each one
is product feedback from dogfooding the codebase.

None of these *block* Phase 116 work. But several are candidates for their
own micro-phase and could be promoted out-of-band.

---

## S1. Stage-advancement regression (Phase 76 / 89 / 91 / 92)

**File:** `src/prep/services/pipeline/state_machine.py:25`

State-machine code has a comment referencing lost stage advancement across
multiple prior phases. Transitions are declared (RUNNING → RUNNING on
STAGE_COMPLETED) but the location where `current_stage_index` is actually
incremented is not obvious from a cold read.

**Impact:** Any overseer gate that hooks into stage transitions needs
confidence in the transition mechanics. If advancement is flaky or
implicit, gates built on top inherit the flakiness.

**Recommendation:** Audit the advancement path before Phase 116
implementation. Promote to its own task if non-trivial. Matches the
existing MEMORY entry about pipeline sequencing bugs.

---

## S2. Swarm worker timeouts are silent

**File:** `src/prep/core/swarm_orchestrator.py` (workers marked `failed`
at `DEFAULT_WORKER_TIMEOUT_S=180s`)

When workers exceed timeout they're marked failed in `worker_results`, but
synthesis proceeds with the surviving subset with no warning at any
aggregation level. 3-of-5 timeouts produces a 2-worker consensus
masquerading as a full swarm.

**Impact:** Invisible data-quality loss. Swarm sizes that look adequate
on paper may be de facto running at 40% strength under load.

**Recommendation:** At minimum, log a WARNING when `failed_count /
total_count > 0.2`. Surface in manifest. Independent of Phase 116 —
fixable today.

---

## S3. Confidence fields are inconsistent across stages

**Covered in `02_` and `06_`.** Each stage uses slightly different
semantics:

- `confidence` (0–1) in INFERRED_EDGES, CATALOGUE, GROUP_REASONING
- `epistemic_confidence` (0–1) in ENRICHMENT, DEEPENING
- No confidence field in CLUSTERING

**Impact:** Downstream consumers can't reason uniformly about "what
outputs should I trust?" Portable gating policies are impossible without
a normalization layer.

**Recommendation:** Standardize on a `quality_score` (or similar)
produced by all stages. This is a 2–5 day refactor and pays back far
more than Phase 116 alone — it enables any future cross-stage reasoning.

---

## S4. Hub-file detection exists but is unused by enrichment

**Files:** `prep_impact` tool knows blast radius; `src/prep/services/pipeline/workers.py:100-150`
(epistemic worker) treats hub files identically to leaves.

**Impact:** We already *know* which files are hubs, but the enrichment
prompt, confidence threshold, and post-processing treat them the same as
peripheral files. Hub-file misclassifications are invisible to the fast
tier that produces them.

**Recommendation:** Pass hub-file metadata into Stages 6–8 as prompt
context ("this file has N dependents; take extra care with role
classification"). Independent of Phase 116. Easy win.

---

## S5. Audit reports have no cross-consistency check

**File:** `src/prep/core/audit/synthesizer.py:96-154`

5 reports (SUMMARY, ARCHITECTURE, GAP, INVENTORY, TECH_DEBT) generate in
parallel with no check that they agree. ARCHITECTURE can say "monolithic"
while INVENTORY lists microservices.

**Impact:** User-facing contradictions erode trust in the full audit
surface — even if 4/5 reports are excellent.

**Recommendation:** Either (a) add a 6th meta-consistency generator (best
done once overseer exists; see checkpoint #3), or (b) add a simple
keyword-overlap contradiction scanner today. Option (b) is a weekend
project.

---

## S6. Concept promotion is grounding-free

**File:** `src/prep/core/concept_promotion.py:28-72`

`suggest_promotion()` promotes observations → concepts by category alone.
No check that the observation is anchored to code that exists, no
corroboration across files, no assertion extraction.

**Impact:** Concepts feed antibody generation (`antibody_derivation.py`).
A concept with no grounding produces antibodies that either fire on
nothing (dead rules) or fire constantly (false positives). Either erodes
user trust.

**Recommendation:** Before Phase 116 ships, add a minimum-viable grounding
check: "does the observation's anchor file exist? Does at least one other
file reference the same pattern?" Checkpoint #2 builds on this.

---

## S7. Knowledge stages produce no artifact but manifest doesn't reflect

**Files:** Stages 5 and 10 (`workers.py:127` shared).

`STAGE_OUTPUT_FILE=None` for both. Intentional — they're embedding-only
passes. But manifest schema doesn't distinguish "no-output stage" from
"failed stage." Debugging is harder than it needs to be.

**Impact:** Low. Annoying, not dangerous.

**Recommendation:** Add an explicit `output_kind` enum to stage
definitions: `jsonl`, `embedding`, `status_only`. Trivial.

---

## S8. No approval / consensus abstraction in-tree

**Noted in `04_`.** Prep has excellent *recovery* abstractions
(`TransitionGuard`, `ManifestStore`, `PipelineCheckpoint`) but nothing
representing "a decision that needs higher-tier validation" or "a group
of workers that voted."

**Impact:** Adding consensus/approval semantics is greenfield surface.
Not a bug — but a real design cost for Phase 116.

**Recommendation:** Out of scope for today. Worth noting when we start
the design phase.

---

## Meta-observation (dogfooding the whole pipeline)

Several of the above (S1, S2, S3, S4, S5, S6) point in the same direction:
**the pipeline is built for happy paths, not for introspection.** Silent
failures, inconsistent signals, missing cross-stage feedback — these are
exactly the seams where an overseer *could* help, and exactly the seams
that make the overseer hard to build.

The path of least resistance may be:

1. **Fix the low-cost introspection gaps first** (S2 warning log, S3 field
   unification, S4 hub propagation, S5 consistency scanner) — each is a
   small standalone win.
2. **Then collect dogfooding data** against the improved pipeline.
3. **Then design the overseer** against data, not guesswork.

Each of (1)'s items is worth doing on its own. Phase 116's timing may
effectively be "whenever those are enough done that the overseer has
signals to work with."
