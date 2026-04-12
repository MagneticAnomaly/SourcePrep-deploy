# Pipeline 15-Stage Reorganization Plan

## Overview

Reorganize the pipeline from 11 sequential stages + ad-hoc post-flight actions into a clean **3 x 5** grid: Sync (1-5), Enrich (6-10), Finalize (11-15). This is **not a feature build** — it's a reorganization that promotes existing post-pipeline tools into first-class stages with proper state tracking, UI visibility, and manual/auto controls.

The key insight: Atlas (currently stage 9) is a leaf node in the pipeline — no downstream stage reads its output. Moving it out of Enrich lets Deepening run immediately after Clustering, and Atlas joins the other post-pipeline tools as a Finalize stage. The math works out perfectly: removing Atlas from the 6-stage Deep Enrichment group leaves exactly 5 Enrich stages, and the 5 post-pipeline tools (Atlas, Concepts, Audit, Rules, Antibodies) become the 5 Finalize stages.

## Current State

### Pipeline (11 stages, 2 groups)
```
Fast Sync (1-5):        Structural → Inferred Edges → Catalogue → Validation → Knowledge
Deep Enrichment (6-11): Enrichment → Group Reasoning → Clustering → Atlas → Deepening → Deep Knowledge
```

### Post-Flight (ad-hoc, invisible to UI)
- Rules generation (runs twice: structural-only after stage 1, full after Atlas)
- CodeIndex rebuild (after deep enrichment completes)
- Concept seeding (daemon thread, after deep enrichment)
- Deepening retrigger (conditional, after deep enrichment)
- Audit — manual only, via API endpoint
- Antibodies — derived from concepts at write-time, no scheduled trigger

### Problems with Current Layout
1. **Atlas blocks Deepening for no reason** — Atlas output (`atlas.json`) is not consumed by stages 10-11 (Deepening, Deep Knowledge). They only need `trace_epistemic.jsonl` and `trace_modules.jsonl`.
2. **Post-pipeline work is invisible** — concept seeding, rules generation, and audit run in daemon threads or manual API calls with no UI presence. Users can't see their status, trigger them, or know when they're done.
3. **Asymmetric groups** — 5 + 6 stages feels unbalanced in the UI. The 6th deep stage (Deep Knowledge) is really just a re-embedding pass, thematically closer to "finalization" than "enrichment."
4. **No parallelism** — all 11 stages run strictly sequentially. The Finalize group is the natural place to introduce controlled parallelism since several of its stages have independent inputs.

## Proposed State: 3 x 5

### Group 1: Sync (stages 1-5) — UNCHANGED
```
1. Structural        (Rust)       — Parse AST, build node/edge graph
2. Inferred Edges    (LLM/Code)   — Discover semantic dependencies
3. Catalogue         (LLM/Fast)   — Augment nodes with descriptions
4. Validation        (Rust)       — Validate graph consistency
5. Knowledge         (Embedding)  — Build semantic search index
```
No changes to stages, ordering, inputs, outputs, or behavior. The "Fast Sync" group header, auto/manual toggle, and watching badge stay exactly as they are.

### Group 2: Enrich (stages 6-10) — REORDERED, ATLAS REMOVED
```
 6. Deep Reasoning     (LLM/Thinking) — Epistemic scoring (layers, domains, confidence)
 7. Group Reasoning    (LLM/Thinking) — Multi-symbol semantic clustering
 8. Module Synthesis   (LLM/Thinking) — Module boundary discovery
 9. Deepening          (LLM/Thinking) — Iterative epistemic refinement
10. Deep Knowledge     (Embedding)    — Re-embed with enriched data
```
**What changed:** Atlas (old stage 9) moved out. Deepening (old 10) and Deep Knowledge (old 11) shift up to fill the gap. No other changes — same stage logic, same inputs/outputs, same LLM tasks. Deepening now runs immediately after Clustering/Module Synthesis instead of waiting for Atlas, which is a throughput improvement for free.

The "Deep Enrichment" group header rename to "Enrich" is cosmetic. The auto/manual/scheduled mode selector stays exactly as-is.

### Group 3: Finalize (stages 11-15) — NEW GROUP, EXISTING LOGIC
```
11. Atlas             (LLM/Thinking) — Generate architectural overview document
12. Rules             (CPU)          — Generate IDE rules files (AGENTS.md, .cursor/, etc.)
13. Concepts          (LLM/Large)    — Seed concepts from atlas + modules + audit
14. Audit             (CPU + optional LLM) — Run structural analyzers, optional LLM synthesis
15. Antibodies        (CPU)          — Derive immune system defenses from concepts
```

**This is the only group where stages can run in parallel.** The dependency graph within Finalize is:

```
           ┌──────────┐
     ┌────►│ 12. Rules │ (needs atlas)
     │     └──────────┘
┌────┴───┐                  ┌──────────────┐
│11. Atlas├────────────────►│ 13. Concepts  │──────►┌──────────────┐
└────┬───┘                  └──────────────┘       │15. Antibodies│
     │     ┌──────────┐                            └──────────────┘
     └────►│ 14. Audit │ (atlas optional, can start early)
           └──────────┘
```

**Parallelism strategy:**
- Stage 11 (Atlas) runs first — it's the root dependency
- Stages 12 (Rules), 13 (Concepts), 14 (Audit) can run simultaneously after Atlas completes
  - Audit can optionally start even before Atlas (it degrades gracefully), but for UI simplicity, wait for Atlas
- Stage 15 (Antibodies) runs after Concepts (derives from concept assertions)

In practice this means Finalize has 3 "waves":
1. Atlas alone
2. Rules + Concepts + Audit in parallel
3. Antibodies alone

**This is the only place in the pipeline where parallelism exists.** Sync and Enrich remain strictly sequential.

## What Changes (and What Doesn't)

### Backend: `src/codrag/services/pipeline/stages.py`

**StageId enum** — Add 4 new members:
```python
class StageId(str, enum.Enum):
    # Sync (1-5) — unchanged
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    # Enrich (6-10) — Atlas removed, rest unchanged
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    DEEPENING = "deepening"          # was stage 10, now stage 9
    DEEP_KNOWLEDGE = "deep_knowledge" # was stage 11, now stage 10
    # Finalize (11-15) — NEW
    ATLAS = "atlas"                   # moved from Enrich
    RULES = "rules"                   # NEW — was post-flight
    CONCEPTS = "concepts"             # NEW — was post-flight daemon thread
    AUDIT = "audit"                   # NEW — was manual API only
    ANTIBODIES = "antibodies"         # NEW — was implicit
```

**Group constants** — Replace 2-group model with 3-group:
```python
SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL, StageId.INFERRED_EDGES, StageId.CATALOGUE,
    StageId.VALIDATION, StageId.KNOWLEDGE,
]

ENRICH_STAGES: List[StageId] = [
    StageId.ENRICHMENT, StageId.GROUP_REASONING, StageId.CLUSTERING,
    StageId.DEEPENING, StageId.DEEP_KNOWLEDGE,
]

FINALIZE_STAGES: List[StageId] = [
    StageId.ATLAS, StageId.RULES, StageId.CONCEPTS,
    StageId.AUDIT, StageId.ANTIBODIES,
]
```

**All stage mapping dicts** — Add entries for the 4 new stages (RULES, CONCEPTS, AUDIT, ANTIBODIES). Atlas entries stay but move position. Add new `BuildType` variants if needed, or map to existing ones with a `FINALIZE` queue type.

**New: `STAGE_PARALLEL_GROUP`** — Optional dict marking which Finalize stages can run concurrently:
```python
STAGE_PARALLEL_GROUP: Dict[StageId, int] = {
    StageId.ATLAS:      0,  # wave 0: runs alone
    StageId.RULES:      1,  # wave 1: parallel
    StageId.CONCEPTS:   1,  # wave 1: parallel
    StageId.AUDIT:      1,  # wave 1: parallel
    StageId.ANTIBODIES: 2,  # wave 2: after concepts
}
```

### Backend: `src/codrag/services/pipeline/orchestrator.py`

**State machine** — Add a third group. Currently tracks `fast_sync` and `deep_enrichment` as two independent state machines. Add `finalize` as a third with the same state transitions (PENDING → RUNNING → COMPLETED/FAILED/PAUSED).

**`_advance_pipeline()`** — For the Finalize group, instead of advancing to the single next stage, check `STAGE_PARALLEL_GROUP` and launch all stages in the same wave concurrently. Track completion of all wave members before advancing to the next wave.

**Post-flight simplification** — Most of `post_flight.py` becomes stage logic:
- `generate_preliminary_atlas_and_rules()` after stage 1 — KEEP as-is (this is a fast structural-only preview, separate from the full Finalize Atlas stage)
- `regenerate_rules_with_full_atlas()` after old Atlas stage — REMOVE (now stage 12 handles this)
- `trigger_concept_seeding()` — REMOVE (now stage 13)
- `trigger_code_index_build()` after deep enrichment — KEEP (this is the CodeIndex rebuild, distinct from pipeline stages)
- `maybe_retrigger_deepening()` — KEEP (this is auto-convergence logic, not a stage)

**Group chaining** — Currently fast_sync can auto-chain to deep_enrichment. Add: deep_enrichment (now "enrich") can auto-chain to finalize. Same budget-aware throttle logic.

### Backend: `src/codrag/services/pipeline/workers.py`

**Existing Atlas worker** — No changes needed, it's already a proper worker. Just moves to the Finalize dispatch.

**New workers needed:**
- `RulesWorker` — Extract logic from `PostFlightActions.regenerate_rules_with_full_atlas()` and `rules_generator.write_rules_file()`. Same code, just wrapped as a pipeline worker with progress reporting.
- `ConceptsWorker` — Extract from `PostFlightActions.trigger_concept_seeding()` and `concept_seeder.py`. Remove daemon-thread wrapper since the orchestrator handles async dispatch.
- `AuditWorker` — Extract from `audit/runner.py:run_audit()`. Currently manual-only; now also triggerable as a pipeline stage. The manual API endpoint stays (users can still run audit independently).
- `AntibodiesWorker` — Extract from `antibodies.py` derivation logic. Lightweight CPU-only pass.

Each worker follows the existing pattern: accepts a `BuildSlot`, reports progress, writes to manifest, returns completion status.

### Backend: `src/codrag/api/routers/pipeline.py`

**Endpoints** — Add Finalize group operations:
- `POST /projects/{id}/pipeline/finalize` — Run Finalize stages (11-15)
- Extend `POST /projects/{id}/pipeline/all` to include Finalize
- Update `GET /projects/{id}/pipeline/status` to return 3-group status
- Extend cancel/pause/resume to accept `"finalize"` group

**Request models** — Update group type from `"fast_sync" | "deep_enrichment"` to `"sync" | "enrich" | "finalize"` (backward-compat: accept old names too).

### Frontend: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

**Type update:**
```typescript
export type EnrichmentStageId =
  | 'structural' | 'inferred_edges' | 'catalogue' | 'validation' | 'knowledge'     // Sync
  | 'enrichment' | 'group_reasoning' | 'clustering' | 'deepening' | 'deep_knowledge' // Enrich
  | 'atlas' | 'rules' | 'concepts' | 'audit' | 'antibodies';                        // Finalize
```

**Stage arrays** — Build a third `finalizeStages` array alongside `fastStages` and `deepStages`:
```typescript
const finalizeStages: EnrichmentStage[] = [
  { id: 'atlas',      label: 'Atlas Building',      icon: Map,          modelTag: 'Thinking' },
  { id: 'rules',      label: 'Rules Generation',    icon: FileText,     modelTag: 'CPU' },
  { id: 'concepts',   label: 'Concept Seeding',     icon: Lightbulb,    modelTag: 'Thinking' },
  { id: 'audit',      label: 'Structural Audit',    icon: ClipboardCheck, modelTag: 'CPU' },
  { id: 'antibodies', label: 'Immune System',       icon: Shield,       modelTag: 'CPU' },
];
```

**Third group header** — Add a "Finalize" section below the existing divider, with the same auto/manual toggle pattern. This group uses the same Run/Resume/Pause controls.

**Parallel indicator** — For Finalize stages that are running concurrently, show them with a visual indicator (e.g., a bracket or parallel rail) instead of the linear connector line used in Sync/Enrich. This is the only UI novelty — everything else is the same `StageRow` component reused.

**Group classification** — Update the group lookup:
```typescript
const group = ['structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge'].includes(stage.id)
  ? 'sync'
  : ['enrichment', 'group_reasoning', 'clustering', 'deepening', 'deep_knowledge'].includes(stage.id)
  ? 'enrich'
  : 'finalize';
```

### Frontend: `packages/ui/src/types.ts`

**New status interfaces** for the 4 new stages:
- `RulesStatus` — { generated: boolean, targets: string[], stale: boolean }
- `ConceptsStatus` — { seeded: boolean, concept_count: number, question_count: number, running: boolean }
- `AuditStatus` — { exists: boolean, finding_count: number, last_run: string, running: boolean, tier2: boolean }
- `AntibodiesStatus` — { count: number, firing: number, last_derived: string }

These mirror the existing status interfaces (`AtlasStatus`, `EpistemicStatus`, etc.) and are consumed by the same polling endpoint.

### Backend: Status endpoint

**`GET /projects/{id}/pipeline/status`** — Currently returns a two-group response. Extend to three groups. The new Finalize stages need status fields:
- Rules: check if IDE rules files exist and are stale
- Concepts: query ConceptStore for count
- Audit: check if `audit_findings.json` exists, read finding count
- Antibodies: query antibody store for count and firing status

## What Does NOT Change

- **Stage 1-5 logic** — Sync is completely untouched
- **Stage 6-8 logic** — Enrichment, Group Reasoning, Clustering are untouched
- **Deepening logic** — Same iterative refinement, just runs earlier (after Clustering instead of after Atlas)
- **Deep Knowledge logic** — Same re-embedding pass
- **Atlas generation logic** — Same code in `core/atlas/generator.py`, just dispatched from Finalize instead of Deep Enrichment
- **Concept seeder logic** — Same `concept_seeder.py`, just wrapped as a worker
- **Audit analyzer logic** — Same `audit/runner.py`, just also triggerable as a pipeline stage
- **Rules generator logic** — Same `rules_generator.py`
- **Manual audit API** — Still works independently outside the pipeline
- **Preliminary rules after stage 1** — Still runs as a fast post-flight action
- **Deepening retrigger logic** — Still runs as post-Enrich-group logic
- **CodeIndex rebuild** — Still runs as post-Enrich-group logic

## Migration / Backward Compatibility

**Stage ID stability** — All existing stage IDs keep their string values. Only Atlas moves groups. The 4 new stage IDs are additive. Any external code referencing `StageId.ATLAS` still works.

**Group name rename** — `fast_sync` → `sync`, `deep_enrichment` → `enrich`, plus new `finalize`. Add backward-compat aliases in the API for the old names so existing dashboard versions don't break during rollout.

**Existing manifests** — Projects with existing `atlas_manifest.json` (from when Atlas was stage 9 in Deep Enrichment) work fine. The manifest file mapping just moves Atlas to the Finalize group. No data migration needed.

**Provenance** — Existing provenance data for Atlas carries over. New stages (Rules, Concepts, Audit, Antibodies) start with no provenance until first run.

## Implementation Order

1. **Backend stages.py** — Add new StageIds, update group constants and all mapping dicts
2. **Backend workers** — Create RulesWorker, ConceptsWorker, AuditWorker, AntibodiesWorker wrappers
3. **Backend orchestrator** — Add Finalize group state machine, wave-based parallel dispatch
4. **Backend post_flight** — Remove logic that's now handled by Finalize stages
5. **Backend API** — Extend pipeline endpoints for 3-group model
6. **Frontend types** — Add new status interfaces and stage IDs
7. **Frontend component** — Add Finalize group rendering with parallel indicator
8. **Testing** — Verify stage ordering, parallel dispatch, backward compat

## Open Questions

1. **Should Audit Tier 2 (LLM synthesis) be opt-in per run, or always attempted?** Currently Tier 2 is a separate flag on the manual API. As a pipeline stage, default to Tier 1 only (CPU, fast) with Tier 2 as an optional setting.
Hmm. I don't want to complicate the UI and I don't want to miss an opportunity. I'm unsure if the LLM will do that much but we should build the LLM into it anyway. baybe we can built the LLM as default and then test later and if it's not good enough we can add a flag to disable it. 

2. **Should Finalize auto-chain from Enrich like Enrich auto-chains from Sync?** Probably yes — if the user has auto mode on for Enrich, Finalize should follow. But Finalize is cheap (mostly CPU + one Atlas LLM call), so auto is less risky than auto-chaining expensive LLM Enrich stages.
use he same manual/auto UI 

3. **Deepening retrigger** — Currently post-flight can re-trigger the entire Deep Enrichment group for convergence. In the new model, this only re-triggers Enrich (6-10), not Finalize (11-15). That's correct — Finalize should only re-run when Enrich produces new data, not on every deepening iteration.
I don't fully understad, but any initial/incremental/rebuild pipelin should continue on from 10 to 11 if auto is on, and puse there if it's set to manual. If deepening isn't adding incremental files etc then it doen't ned to run.

4. **Naming: "Finalize" vs alternatives** — Other candidates: "Synthesize", "Materialize", "Publish". "Finalize" chosen because it's clear these are wrap-up stages that produce deliverables (atlas doc, rules files, concepts, audit report, defenses) from the enriched data.
Finalize is ok I guess, we can change it later if needed