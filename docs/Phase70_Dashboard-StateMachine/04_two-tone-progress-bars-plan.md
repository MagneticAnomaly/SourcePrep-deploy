# Two-Tone Progress Bars — Implementation Plan

## Problem

The Graph Enrichment pipeline has 11 stages. When running incrementally (re-processing only changed files), some stages show a two-tone progress bar (green for already-done, orange for new work). But this only works for 4 out of 11 stages. The rest show either a generic fallback or no two-tone at all.

## Current State

| # | Stage | Two-Tone? | How | Data Source |
|---|-------|-----------|-----|-------------|
| 1 | Structural Graph | N/A | Rust engine, instant | — |
| 2 | Edge Discovery | **Full** | Per-stage `slot_progress.baseline` | `InferredEdgesStatus` |
| 3 | Fast Catalogue | **Full** | Per-stage `progress_baseline` | `AugmentationStatus` |
| 4 | Relationship Validation | N/A | Rust pass-through, instant | — |
| 5 | Knowledge Embedding | **Full** | Per-stage `progress_baseline` | `KnowledgeEmbeddingStatus` |
| 6 | Deep Reasoning | **Full** | Per-stage `progress_baseline` | `EpistemicStatus` |
| 6b | Group Reasoning | **Fallback** | Project-wide `staleCounts` | Generic — all stages show SAME ratio |
| 7 | Module Synthesis | **Fallback** | Project-wide `staleCounts` | Generic — all stages show SAME ratio |
| 8 | Atlas Building | **Fallback** | Project-wide `staleCounts` | Generic — all stages show SAME ratio |
| 9 | Continuous Deepening | **Fallback** | Project-wide `staleCounts` | Generic — all stages show SAME ratio |
| 10 | Deep Knowledge Embedding | **None** | No two-tone at all | — |

## Architecture

The two-tone pattern works via `StageProgressBar` component which accepts a `rerun` prop:

```typescript
rerun?: { donePercent: number; stalePercent: number }
```

When `rerun` is defined:
- **Green segment** (left): `donePercent` — already-completed work from previous run
- **Orange segment** (right): `stalePercent` — newly-processing work, with sub-segments for completed vs pending within the stale portion

The data flows:
1. **Backend**: `BuildSlot.progress_baseline` tracks items completed in previous runs
2. **API**: `/pipeline/status` includes `slot_progress.baseline` per active stage
3. **Frontend**: `computeStageRerun(baseline, total, staleCounts)` in `GraphEnrichmentPipeline.tsx` computes the two-tone split
4. **Component**: `StageProgressBar` renders the two-tone bar

## What Needs to Change

### For each missing stage, add `progress_baseline` support:

### Stage 6b: Group Reasoning

**Backend type** (`src/codrag/services/pipeline/workers.py` or status types):
- Ensure `GroupReasoningStatus` includes `progress_baseline?: number`
- Populate from `slot_progress.baseline` in pipeline status API

**Frontend** (`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`):
- Change from: `computeStageRerun(undefined, undefined, staleCounts)`
- Change to: `computeStageRerun(groupReasoning?.progress_baseline, groupReasoning?.progress_total, staleCounts)`

### Stage 7: Module Synthesis (Clustering)

Same pattern:
- Add `progress_baseline` to `ModuleStatus` type
- Update `computeStageRerun` call for clustering stage

### Stage 8: Atlas Building

Same pattern:
- Add `progress_baseline` to Atlas status
- Update `computeStageRerun` call for atlas stage

### Stage 9: Continuous Deepening

Same pattern:
- Add `progress_baseline` to `DeepeningStatus` type
- Update `computeStageRerun` call for deepening stage

### Stage 10: Deep Knowledge Embedding

This stage has NO two-tone at all:
- Add `progress_baseline` to the deep knowledge tracking
- Add `rerun` prop to the StageProgressBar for this stage
- Wire `computeStageRerun` into the deep knowledge section

## Files to Modify

| File | What |
|------|------|
| `packages/ui/src/types.ts` | Add `progress_baseline` to missing status types |
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | Update `computeStageRerun` calls for stages 6b, 7, 8, 9, 10 |
| `src/codrag/api/routers/pipeline.py` | Ensure `slot_progress.baseline` is exposed for all active stages |

## Key Component References

| Component | File | Lines |
|-----------|------|-------|
| `StageProgressBar` | `packages/ui/src/components/trace/StageProgressBar.tsx` | Renders two-tone bar |
| `computeStageRerun` | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:140-154` | Computes donePercent/stalePercent |
| Stage rendering | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:930-1010` | Where `rerun` prop is passed per stage |

## Testing Checklist

After implementation, verify each stage shows correct two-tone behavior:

- [ ] **Edge Discovery** (Stage 2): Green portion = previously discovered edges, orange = new edges being processed
- [ ] **Fast Catalogue** (Stage 3): Green = already catalogued nodes, orange = newly cataloguing
- [ ] **Knowledge Embedding** (Stage 5): Green = already embedded, orange = newly embedding
- [ ] **Deep Reasoning** (Stage 6): Green = already enriched files, orange = newly enriching
- [ ] **Group Reasoning** (Stage 6b): Green = already grouped, orange = newly grouping (NOT generic fallback)
- [ ] **Module Synthesis** (Stage 7): Green = already clustered, orange = newly clustering (NOT generic fallback)
- [ ] **Atlas Building** (Stage 8): Green = reused atlas segments, orange = newly generating
- [ ] **Continuous Deepening** (Stage 9): Green = already deepened, orange = newly deepening (NOT generic fallback)
- [ ] **Deep Knowledge Embedding** (Stage 10): Green = already embedded, orange = newly embedding (currently NO bar)

## Verification Steps

1. Build the index for a project (full pipeline run)
2. Add a few new files to the project
3. Re-run the pipeline (incremental)
4. Watch each stage — the progress bar should show green (reused) + orange (new) split
5. The green/orange ratio should match the actual reused/new file ratio, NOT the project-wide stale ratio
