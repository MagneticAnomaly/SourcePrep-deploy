import type {
  InferredEdgesStatus,
  AugmentationStatus,
  EpistemicStatus,
  ModuleStatus,
  DeepeningStatus,
  KnowledgeEmbeddingStatus,
  AtlasStatus,
  RulesStatus,
  ConceptsStatus,
  AuditPipelineStatus,
  AntibodiesStatus,
} from '@prep/ui'

// ── State ─────────────────────────────────────────────────────

export interface EnrichmentState {
  inferredEdgesStatus: InferredEdgesStatus
  inferredEdgesRunning: boolean
  augmentationStatus: AugmentationStatus
  augmenting: boolean
  validating: boolean
  epistemicStatus: EpistemicStatus
  epistemicRunning: boolean
  moduleStatus: ModuleStatus
  clusterRunning: boolean
  atlasStatus: AtlasStatus | null
  atlasRunning: boolean
  deepeningStatus: DeepeningStatus
  deepeningRunning: boolean
  knowledgeStatus: KnowledgeEmbeddingStatus
  /** Separate status for stage 10 (Deep Knowledge Embedding). Pre-Phase 102
   * both stages shared `knowledgeStatus` which caused progress/running
   * fields from fast-sync knowledge to bleed into the Deep Knowledge row. */
  deepKnowledgeStatus: KnowledgeEmbeddingStatus
  fastKnowledgeBuilding: boolean
  deepKnowledgeBuilding: boolean
  groupReasoningRunning: boolean
  groupReasoningStatus: { enabled: boolean; group_count: number; analyzed: number; running?: boolean; slot_phase?: string; progress_current?: number; progress_total?: number }
  /** Pipeline group is paused (phase === 'paused' | 'pausing' | legacy 'failed') */
  fastPaused: boolean
  deepPaused: boolean
  finalizePaused: boolean
  /** Explicit stage ID where the pipeline was paused (from backend current_stage) */
  fastPausedStage: string | undefined
  deepPausedStage: string | undefined
  finalizePausedStage: string | undefined
  // F-58: finalize running state (was completely missing — stages 11-15
  // showed "Not generated / Not seeded / Not run / Not derived" even while
  // the pipeline was actively processing them)
  finalizeRunning: boolean
  finalizeCurrentStage: string | undefined
  // Phase 145 I3: which stage each group is currently running, mirrored
  // from API /pipeline/status. Threaded through useDashboardPanels →
  // GraphEnrichmentPipeline so the rebuild freeze-green helper can
  // distinguish "previously-complete stages the rebuild has already
  // passed" from "downstream stages it hasn't reached yet" (stale leak).
  fastCurrentStage: string | undefined
  deepCurrentStage: string | undefined
  // §9.3 #28/#29: full group phase string (running | completed | failed |
  // cancelled | idle | queued | paused | pausing | recovering | cancelling)
  // mirrored from API /pipeline/status so the rebuild freeze-green helper
  // can coerce stale per-stage running/idle state to 'complete' once the
  // group has settled into the `completed` phase. Without this, current_stage
  // goes to undefined when the group completes but the per-stage compute
  // fns may still return a pre-completion stale value (Deep Reasoning
  // 100%-but-spinning was the live evidence).
  fastSyncPhase: string | undefined
  deepEnrichmentPhase: string | undefined
  finalizePhase: string | undefined
  // Finalize stage statuses (Phase 96)
  rulesStatus?: RulesStatus
  conceptsStatus?: ConceptsStatus
  auditPipelineStatus?: AuditPipelineStatus
  antibodiesStatus?: AntibodiesStatus
}

export const initialEnrichmentState: EnrichmentState = {
  inferredEdgesStatus: { enabled: true, exists: false, edge_count: 0 },
  inferredEdgesRunning: false,
  augmentationStatus: {
    enabled: false, total_nodes: 0, augmented_nodes: 0,
    validated_nodes: 0, avg_confidence: 0, low_confidence_count: 0,
  },
  augmenting: false,
  validating: false,
  epistemicStatus: { enabled: false, enriched_nodes: 0, avg_confidence: 0, running: false },
  epistemicRunning: false,
  moduleStatus: { enabled: false, module_count: 0, total_files_clustered: 0, running: false },
  clusterRunning: false,
  atlasStatus: null,
  atlasRunning: false,
  deepeningStatus: { running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0 },
  deepeningRunning: false,
  knowledgeStatus: { enabled: false, running: false, chunks_embedded: 0, deep_chunks_embedded: 0, last_run_at: null },
  deepKnowledgeStatus: { enabled: false, running: false, chunks_embedded: 0, deep_chunks_embedded: 0, last_run_at: null },
  fastKnowledgeBuilding: false,
  deepKnowledgeBuilding: false,
  groupReasoningRunning: false,
  groupReasoningStatus: { enabled: false, group_count: 0, analyzed: 0 },
  fastPaused: false,
  deepPaused: false,
  finalizePaused: false,
  finalizeRunning: false,
  finalizeCurrentStage: undefined,
  fastCurrentStage: undefined,
  deepCurrentStage: undefined,
  fastSyncPhase: undefined,
  deepEnrichmentPhase: undefined,
  finalizePhase: undefined,
  fastPausedStage: undefined,
  deepPausedStage: undefined,
  finalizePausedStage: undefined,
}

// ── Actions ───────────────────────────────────────────────────

type StageName = 'augmentation' | 'epistemic' | 'modules' | 'deepening' | 'knowledge' | 'deep_enrichment'

export type EnrichmentAction =
  // Individual status updates (from API fetches / polling)
  | { type: 'INFERRED_EDGES_STATUS'; payload: InferredEdgesStatus }
  | { type: 'AUGMENTATION_STATUS'; payload: AugmentationStatus }
  | { type: 'EPISTEMIC_STATUS'; payload: EpistemicStatus }
  | { type: 'MODULE_STATUS'; payload: ModuleStatus }
  | { type: 'DEEPENING_STATUS'; payload: DeepeningStatus }
  | { type: 'KNOWLEDGE_STATUS'; payload: KnowledgeEmbeddingStatus }
  | { type: 'DEEP_KNOWLEDGE_STATUS'; payload: KnowledgeEmbeddingStatus }
  | { type: 'ATLAS_STATUS'; payload: AtlasStatus }
  | { type: 'GROUP_REASONING_STATUS'; payload: { enabled: boolean; group_count: number; analyzed: number; slot_phase?: string; progress_current?: number; progress_total?: number } }
  // Sync all running flags at once (from SSE or initial hydration). Phase
  // 145 I3 added fastCurrentStage/deepCurrentStage so the rebuild freeze-
  // green helper has a per-group anchor for "downstream of current".
  | { type: 'SYNC_RUNNING'; inferredEdgesRunning: boolean; augmenting: boolean; validating: boolean; epistemicRunning: boolean; groupReasoningRunning: boolean; clusterRunning: boolean; atlasRunning: boolean; deepeningRunning: boolean; fastKnowledgeBuilding: boolean; deepKnowledgeBuilding: boolean; fastCurrentStage?: string; deepCurrentStage?: string; fastSyncPhase?: string; deepEnrichmentPhase?: string; finalizePhase?: string }
  // Sync paused flags (from pipeline phase: paused | pausing | legacy failed)
  | { type: 'SYNC_PAUSED'; fastPaused: boolean; deepPaused: boolean; finalizePaused: boolean; fastPausedStage?: string; deepPausedStage?: string; finalizePausedStage?: string }
  // Manual stage start (optimistic UI feedback)
  | { type: 'STAGE_STARTED'; stage: StageName }
  // Manual stage failure (revert optimistic flag)
  | { type: 'STAGE_FAILED'; stage: StageName }
  // Group completions — atomically clear all running flags in group
  | { type: 'FAST_COMPLETED' }
  | { type: 'FAST_FAILED' }
  | { type: 'DEEP_COMPLETED' }
  | { type: 'DEEP_FAILED' }
  | { type: 'FINALIZE_COMPLETED' }
  | { type: 'FINALIZE_FAILED' }
  // F-58: finalize running state
  | { type: 'FINALIZE_RUNNING'; running: boolean; currentStage?: string }
  // Finalize stage statuses (Phase 96)
  | { type: 'FINALIZE_STATUSES'; rules?: RulesStatus; concepts?: ConceptsStatus; audit?: AuditPipelineStatus; antibodies?: AntibodiesStatus }
  // Merge slot_progress (with baseline) from pipeline status polling
  | { type: 'AUGMENTATION_PROGRESS'; payload: { progress_current: number; progress_total: number; progress_baseline: number } }
  | { type: 'EPISTEMIC_PROGRESS'; payload: { progress_current: number; progress_total: number; progress_baseline: number } }
  // Full reset (destroy graph/index)
  | { type: 'DESTROYED' }

// ── Reducer ───────────────────────────────────────────────────

export function enrichmentReducer(state: EnrichmentState, action: EnrichmentAction): EnrichmentState {
  switch (action.type) {
    // ── Status updates ──
    case 'INFERRED_EDGES_STATUS':
      return { ...state, inferredEdgesStatus: action.payload }
    case 'AUGMENTATION_STATUS':
      return { ...state, augmentationStatus: {
        ...action.payload,
        // Preserve pipeline slot progress that AUGMENTATION_PROGRESS set
        progress_current: action.payload.progress_current ?? state.augmentationStatus.progress_current,
        progress_total: action.payload.progress_total ?? state.augmentationStatus.progress_total,
        progress_baseline: action.payload.progress_baseline ?? state.augmentationStatus.progress_baseline,
      }}
    case 'EPISTEMIC_STATUS':
      return { ...state, epistemicStatus: {
        ...action.payload,
        progress_current: action.payload.progress_current ?? state.epistemicStatus.progress_current,
        progress_total: action.payload.progress_total ?? state.epistemicStatus.progress_total,
        progress_baseline: action.payload.progress_baseline ?? state.epistemicStatus.progress_baseline,
      }}
    case 'MODULE_STATUS':
      return { ...state, moduleStatus: action.payload }
    case 'DEEPENING_STATUS':
      return { ...state, deepeningStatus: action.payload }
    case 'KNOWLEDGE_STATUS':
      return { ...state, knowledgeStatus: action.payload }
    case 'DEEP_KNOWLEDGE_STATUS':
      return { ...state, deepKnowledgeStatus: action.payload }
    case 'ATLAS_STATUS':
      return { ...state, atlasStatus: action.payload }
    case 'GROUP_REASONING_STATUS':
      return { ...state, groupReasoningStatus: action.payload }
    case 'AUGMENTATION_PROGRESS':
      return { ...state, augmentationStatus: { ...state.augmentationStatus, ...action.payload } }
    case 'EPISTEMIC_PROGRESS':
      return { ...state, epistemicStatus: { ...state.epistemicStatus, ...action.payload } }

    // ── Running flag sync (SSE / hydration) ──
    case 'SYNC_RUNNING':
      return {
        ...state,
        inferredEdgesRunning: action.inferredEdgesRunning,
        augmenting: action.augmenting,
        validating: action.validating,
        epistemicRunning: action.epistemicRunning,
        groupReasoningRunning: action.groupReasoningRunning,
        clusterRunning: action.clusterRunning,
        atlasRunning: action.atlasRunning,
        deepeningRunning: action.deepeningRunning,
        fastKnowledgeBuilding: action.fastKnowledgeBuilding,
        deepKnowledgeBuilding: action.deepKnowledgeBuilding,
        fastCurrentStage: action.fastCurrentStage,
        deepCurrentStage: action.deepCurrentStage,
        fastSyncPhase: action.fastSyncPhase,
        deepEnrichmentPhase: action.deepEnrichmentPhase,
        finalizePhase: action.finalizePhase,
      }

    case 'SYNC_PAUSED':
      return {
        ...state,
        fastPaused: action.fastPaused,
        deepPaused: action.deepPaused,
        finalizePaused: action.finalizePaused,
        fastPausedStage: action.fastPausedStage,
        deepPausedStage: action.deepPausedStage,
        finalizePausedStage: action.finalizePausedStage,
      }

    // ── Optimistic stage start ──
    case 'STAGE_STARTED':
      switch (action.stage) {
        case 'augmentation': return { ...state, augmenting: true }
        case 'epistemic': return { ...state, epistemicRunning: true }
        case 'modules': return { ...state, clusterRunning: true }
        case 'deepening': return { ...state, deepeningRunning: true }
        case 'knowledge': return { ...state, fastKnowledgeBuilding: true }
        case 'deep_enrichment': return { ...state, epistemicRunning: true }
        default: return state
      }

    // ── Revert on failure ──
    case 'STAGE_FAILED':
      switch (action.stage) {
        case 'augmentation': return { ...state, augmenting: false }
        case 'epistemic': return { ...state, epistemicRunning: false }
        case 'modules': return { ...state, clusterRunning: false }
        case 'deepening': return { ...state, deepeningRunning: false }
        case 'knowledge': return { ...state, fastKnowledgeBuilding: false }
        case 'deep_enrichment': return { ...state, epistemicRunning: false }
        default: return state
      }

    // ── Group completions (atomic multi-flag clear) ──
    case 'FAST_COMPLETED':
    case 'FAST_FAILED':
      return {
        ...state,
        inferredEdgesRunning: false, augmenting: false, validating: false, fastKnowledgeBuilding: false, fastPaused: false, fastPausedStage: undefined,
        // Phase 145 I3: clear current_stage too so downstream-anchor lookups
        // don't return a stale stage id once the group has settled.
        fastCurrentStage: undefined,
        // Clear pipeline slot progress so it doesn't bleed into next run
        augmentationStatus: { ...state.augmentationStatus, progress_current: undefined, progress_total: undefined, progress_baseline: undefined },
      }

    case 'DEEP_COMPLETED':
    case 'DEEP_FAILED':
      return {
        ...state,
        epistemicRunning: false, groupReasoningRunning: false, clusterRunning: false, atlasRunning: false, deepeningRunning: false, deepKnowledgeBuilding: false, deepPaused: false, deepPausedStage: undefined,
        deepCurrentStage: undefined,
        epistemicStatus: { ...state.epistemicStatus, progress_current: undefined, progress_total: undefined, progress_baseline: undefined },
      }

    case 'FINALIZE_RUNNING':
      return {
        ...state,
        finalizeRunning: action.running,
        finalizeCurrentStage: action.running ? action.currentStage : undefined,
      }

    case 'FINALIZE_COMPLETED':
    case 'FINALIZE_FAILED':
      return {
        ...state,
        finalizePaused: false, finalizePausedStage: undefined,
        finalizeRunning: false, finalizeCurrentStage: undefined,
      }

    // ── Full reset ──
    case 'FINALIZE_STATUSES':
      return {
        ...state,
        rulesStatus: action.rules ?? state.rulesStatus,
        conceptsStatus: action.concepts ?? state.conceptsStatus,
        auditPipelineStatus: action.audit ?? state.auditPipelineStatus,
        antibodiesStatus: action.antibodies ?? state.antibodiesStatus,
      }

    case 'DESTROYED':
      return { ...initialEnrichmentState }

    default:
      return state
  }
}
