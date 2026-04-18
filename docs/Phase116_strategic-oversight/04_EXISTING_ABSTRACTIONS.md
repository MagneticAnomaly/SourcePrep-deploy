# 04 — Existing Abstractions We Could Extend

Before designing new machinery, survey what's in-tree. Reusing existing
surfaces keeps the overseer consistent with the rest of the pipeline and
reduces risk.

## Reusable surfaces

### `TransitionGuard` — stage gating
**File:** `src/codrag/services/pipeline/state_machine.py:218-240`

Pluggable guard that can veto state transitions. Already used:
`ActiveProjectGuard` blocks `START` when project is inactive.

**Extensibility:** An `OverseerGate(TransitionGuard)` subclass would be the
natural place to block stage advancement on overseer disapproval. The
guard interface is stable enough that we don't need to re-architect.

**Caveat:** Blocks transitions; doesn't interact with mid-stage work.
Per-checkpoint gating (e.g., "check after concept promotion but before
antibody derivation") needs a finer-grained hook.

### `ManifestStore` — provenance trail
**File:** `src/codrag/services/pipeline/manifest_store.py`

Tracks per-stage provenance: model used, tokens, timing, quality. Not a
gate — audit trail only.

**Extensibility:** Add `overseer_decision`, `overseer_rubric_scores`,
`overseer_timestamp` fields to the manifest. Even without a blocking
gate, this gives us dogfooding data collection "for free" as soon as we
start invoking the overseer on any stage.

### `PipelineCheckpoint` — pause/resume
**File:** `src/codrag/services/pipeline_checkpoint.py`

Saves/restores pipeline state for pause/resume. Not a quality gate.

**Extensibility:** Add a `paused_for_overseer_review` flag distinct from
`paused_for_capacity`. Gives future HITL workflows a place to land.

### `SwarmOrchestrator` — worker aggregation
**File:** `src/codrag/core/swarm_orchestrator.py:102-250`

Coordinator + workers + synthesis. `SwarmResult.worker_results` already
exposes all N worker outputs.

**Extensibility:** Easiest win in the whole codebase.
`SwarmResult.disagreement_score()` could be a pure-data method returning
stddev-of-confidence + claim-conflict count. Zero LLM calls, just surfaces
what's already computed. This becomes the overseer's primary gate signal
for Stage 7.

### `AuditSynthesizer` parallel-report generation
**File:** `src/codrag/core/audit/synthesizer.py:96-154`

5 report generators in a `ThreadPoolExecutor` with partial-failure
tolerance.

**Extensibility:** Add a 6th "meta-report" generator that runs *after* the
5 main generators finish, reading their outputs and auditing for
cross-report contradictions. Natural overseer slot — same thread-pool,
same failure semantics.

## Gaps — what's *not* in-tree

- **No approval abstraction.** Nothing in the codebase represents "a
  decision that needs higher-tier validation." Approval is new concept
  surface we'd have to design.
- **No consensus / voting abstraction.** Swarm workers produce independent
  outputs; synthesis merges them but doesn't vote. A `Consensus.score()`
  primitive would be new.
- **No confidence normalization.** Each stage's confidence field has
  different semantics (`02_` table). A uniform `QualityScore` (or
  equivalent) is prerequisite plumbing.
- **No rubric registry.** LLM-as-judge best practice is rubric-based; we
  have no place to declare per-checkpoint rubrics yet.
- **No overseer backend client.** We have Opus clients via the
  augmenter / enrichment path, but no shared "get me an adjudication from
  the frontier tier" helper.
- **No deferred-findings surface.** For async overseer (recommended),
  findings need somewhere to land between pipeline completion and user
  view. Antibodies surface is the closest analog but not quite right.

## Integration shape (tentative, for later design)

If we do build this, the smallest-surface-area integration would look
roughly like:

```
┌─ Overseer (new)
│   ├─ OverseerGate(TransitionGuard)        ← per-stage hooks
│   ├─ CheckpointRegistry                    ← new; binds checkpoints to gates
│   ├─ Rubric                                ← new; per-checkpoint prompts
│   ├─ ConfidenceNormalizer                  ← new; unify per-stage semantics
│   ├─ DisagreementGate(SwarmResult)         ← extends SwarmResult
│   ├─ OverseerClient                        ← new; wraps Opus/GPT-5
│   └─ OverseerFindings (manifest annotation) ← extends ManifestStore
│
└─ Existing (extended, not replaced)
    ├─ TransitionGuard
    ├─ ManifestStore
    ├─ PipelineCheckpoint
    └─ SwarmOrchestrator
```

Rough count: **~4 new modules, ~4 existing modules extended.** None of this
is committed — it's a sketch of what the smallest reasonable integration
would look like. Real design happens after the dogfooding data lands.
