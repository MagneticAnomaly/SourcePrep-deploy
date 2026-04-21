# Pipeline Stage Sync Requirement (GAP-10)

Pipeline stage IDs are defined in three separate locations that must be
kept in sync manually.  Adding or removing a pipeline stage requires
updating all three.

## Locations

### 1. Python Backend — Source of Truth
**File:** `src/prep/services/pipeline_orchestrator.py`
```python
class StageId(str, enum.Enum):
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    ATLAS = "atlas"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"
```

### 2. TypeScript Types
**File:** `packages/ui/src/types.ts`
```typescript
export type EnrichmentStageId =
  | 'structural'
  | 'inferred_edges'
  | 'catalogue'
  | 'validation'
  | 'knowledge'
  | 'enrichment'
  | 'group_reasoning'
  | 'clustering'
  | 'atlas'
  | 'deepening'
  | 'deep_knowledge';
```

### 3. React UI Labels
**File:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

Stage labels and descriptions are defined inline in the component's
stage configuration array.

## Sync Protocol

When adding a new stage:
1. Add to `StageId` enum in `pipeline_orchestrator.py`
2. Add to `STAGE_BUILD_TYPE` mapping
3. Add to the appropriate group list (`FAST_SYNC_STAGES` or `DEEP_ENRICHMENT_STAGES`)
4. Add to `STAGE_MODEL_SLOT` if it uses an LLM
5. Create the worker function in `WorkerFactory`
6. Add to `EnrichmentStageId` type in `types.ts`
7. Add stage label + description in `GraphEnrichmentPipeline.tsx`

## Future Improvement

Consider a build-time script that generates the TypeScript type from the
Python enum (e.g. via `scripts/sync_stage_ids.py`).  This would eliminate
the manual sync requirement.
