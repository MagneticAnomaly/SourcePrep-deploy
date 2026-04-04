import { useReducer, useCallback, useEffect, useRef } from 'react'
import { useApiClient, type PipelineStatus } from '@codrag/ui'
import {
  enrichmentReducer,
  initialEnrichmentState,
} from '../state/enrichmentReducer'

// ── Dependencies ──────────────────────────────────────────────

type ToastVariant = 'error' | 'warning' | 'info' | 'success'

export interface UseEnrichmentDeps {
  onError: (msg: string, variant?: ToastVariant) => void
  /** Pipeline SSE events keyed by project_id */
  pipelineEvents?: Record<string, PipelineStatus & { project_id: string }>
  /** Called when deep enrichment pipeline completes (e.g. to refresh atlas) */
  onDeepCompleted?: () => void
  /** Called when fast sync pipeline completes (e.g. to refresh provenance) */
  onFastCompleted?: () => void
  /** AbortSignal from hydration controller — aborted on project switch */
  signal?: AbortSignal
  /** True while hydration is in progress — suppress polls */
  isHydrating?: boolean
}

// ── Hook ──────────────────────────────────────────────────────

/**
 * Manages the 6 enrichment stages: augmentation, epistemic, module synthesis,
 * deepening, knowledge embedding. Owns state, SSE reactions, polling, and
 * self-hydrates on project change.
 */
export function useEnrichment(selectedProjectId: string | null, deps: UseEnrichmentDeps) {
  const api = useApiClient()
  const [state, dispatch] = useReducer(enrichmentReducer, initialEnrichmentState)

  const onErrorRef = useRef(deps.onError)
  onErrorRef.current = deps.onError
  const onDeepCompletedRef = useRef(deps.onDeepCompleted)
  onDeepCompletedRef.current = deps.onDeepCompleted
  const onFastCompletedRef = useRef(deps.onFastCompleted)
  onFastCompletedRef.current = deps.onFastCompleted

  // ── Fetch functions ─────────────────────────────────────────

  const fetchAugmentationStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getAugmentStatus(selectedProjectId)
      dispatch({ type: 'AUGMENTATION_STATUS', payload: status })
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchEpistemicStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getEpistemicStatus(selectedProjectId)
      dispatch({ type: 'EPISTEMIC_STATUS', payload: status })
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchModuleStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getModuleStatus(selectedProjectId)
      dispatch({ type: 'MODULE_STATUS', payload: status })
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchDeepeningStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getDeepeningStatus(selectedProjectId)
      dispatch({ type: 'DEEPENING_STATUS', payload: status })
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchKnowledgeStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getKnowledgeStatus(selectedProjectId)
      dispatch({ type: 'KNOWLEDGE_STATUS', payload: status })
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  // Refresh stages that have no dedicated API endpoint (inferred_edges, atlas)
  // by fetching the full pipeline status and extracting stage data.
  const refreshStageDataFromPipeline = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const ps = await api.getPipelineStatus(selectedProjectId)
      if (ps.stages?.inferred_edges) {
        dispatch({ type: 'INFERRED_EDGES_STATUS', payload: ps.stages.inferred_edges })
      }
      if (ps.stages?.atlas) {
        dispatch({ type: 'ATLAS_STATUS', payload: ps.stages.atlas })
      }
      if (ps.stages?.group_reasoning) {
        dispatch({ type: 'GROUP_REASONING_STATUS', payload: ps.stages.group_reasoning })
      }
      // Merge catalogue slot_progress (with baseline) into augmentation status
      const cat = ps.stages?.catalogue as Record<string, any> | undefined
      if (cat && (cat.progress_current != null || cat.progress_baseline != null)) {
        dispatch({ type: 'AUGMENTATION_PROGRESS', payload: {
          progress_current: cat.progress_current ?? 0,
          progress_total: cat.progress_total ?? 0,
          progress_baseline: cat.progress_baseline ?? 0,
        }})
      }
      // Merge enrichment slot_progress (with baseline) into epistemic status
      const enr = ps.stages?.enrichment as Record<string, any> | undefined
      if (enr && (enr.progress_current != null || enr.progress_baseline != null)) {
        dispatch({ type: 'EPISTEMIC_PROGRESS', payload: {
          progress_current: enr.progress_current ?? 0,
          progress_total: enr.progress_total ?? 0,
          progress_baseline: enr.progress_baseline ?? 0,
        }})
      }
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  // ── Run handlers ────────────────────────────────────────────

  const handleRunAugmentation = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'augmentation' })
    try {
      await api.runAugmentation(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'augmentation' })
      onErrorRef.current(e instanceof Error ? e.message : 'Fast Catalogue stage encountered an issue.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleRunEpistemic = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'epistemic' })
    try {
      await api.runEpistemic(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'epistemic' })
      onErrorRef.current(e instanceof Error ? e.message : 'Relationship Validation stage encountered an issue.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleRunModuleSynthesis = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'modules' })
    try {
      await api.runModuleSynthesis(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'modules' })
      onErrorRef.current(e instanceof Error ? e.message : 'Module Synthesis stage encountered an issue.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleRunDeepening = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'deepening' })
    try {
      await api.runDeepening(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'deepening' })
      onErrorRef.current(e instanceof Error ? e.message : 'Deep Reasoning stage encountered an issue.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleRunKnowledgeBuild = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'knowledge' })
    try {
      await api.runKnowledgeBuild(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'knowledge' })
      onErrorRef.current(e instanceof Error ? e.message : 'Knowledge Embedding stage encountered an issue.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleRunDeepEnrichment = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'deep_enrichment' })
    try {
      await api.runPipelineDeep(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'deep_enrichment' })
      onErrorRef.current(e instanceof Error ? e.message : 'Deep Enrichment pipeline encountered an issue. Check AI Gateway for model availability.', 'warning')
    }
  }, [api, selectedProjectId])

  const handlePausePipeline = useCallback(async (group: 'fast_sync' | 'deep_enrichment') => {
    if (!selectedProjectId) return
    try {
      await api.pausePipeline(selectedProjectId, group)
      // Optimistic UI update — don't wait for next poll cycle
      dispatch({
        type: 'SYNC_PAUSED',
        fastPaused: group === 'fast_sync' ? true : state.fastPaused,
        deepPaused: group === 'deep_enrichment' ? true : state.deepPaused,
        // We don't know the exact stage client-side at pause time;
        // the SSE event will fill it in when the backend confirms.
        fastPausedStage: group === 'fast_sync' ? undefined : state.fastPausedStage,
        deepPausedStage: group === 'deep_enrichment' ? undefined : state.deepPausedStage,
      })
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t pause pipeline.', 'warning')
    }
  }, [api, selectedProjectId, state.fastPaused, state.deepPaused])

  const handleResumePipeline = useCallback(async (group: 'fast_sync' | 'deep_enrichment') => {
    if (!selectedProjectId) return
    try {
      await api.resumePipeline(selectedProjectId, group)
      // Optimistic UI update
      dispatch({
        type: 'SYNC_PAUSED',
        fastPaused: group === 'fast_sync' ? false : state.fastPaused,
        deepPaused: group === 'deep_enrichment' ? false : state.deepPaused,
        fastPausedStage: group === 'fast_sync' ? undefined : state.fastPausedStage,
        deepPausedStage: group === 'deep_enrichment' ? undefined : state.deepPausedStage,
      })
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t resume pipeline.', 'warning')
    }
  }, [api, selectedProjectId, state.fastPaused, state.deepPaused])

  const handleSwapModel = useCallback(async (group?: 'fast_sync' | 'deep_enrichment') => {
    if (!selectedProjectId) return
    // Determine which group(s) to swap based on what's running
    const groups: ('fast_sync' | 'deep_enrichment')[] = group
      ? [group]
      : [
        ...(state.augmenting || state.inferredEdgesRunning || state.fastKnowledgeBuilding ? ['fast_sync' as const] : []),
        ...(state.epistemicRunning || state.groupReasoningRunning || state.clusterRunning || state.atlasRunning || state.deepeningRunning || state.deepKnowledgeBuilding ? ['deep_enrichment' as const] : []),
      ]
    for (const g of groups) {
      try {
        await api.swapPipelineModel(selectedProjectId, g)
      } catch {
        // Swap fails silently if group isn't running — that's fine
      }
    }
  }, [api, selectedProjectId, state])

  // ── Reset (called by destroy handlers in useTraceSystem) ────

  const resetAll = useCallback(() => {
    dispatch({ type: 'DESTROYED' })
  }, [])

  // ── Hydration: fetch all statuses + pipeline flags on project change ──

  useEffect(() => {
    // Reset all enrichment state immediately to prevent cross-project contamination
    dispatch({ type: 'DESTROYED' })

    if (!selectedProjectId) return
    const signal = deps.signal
    let unmounted = false

    // Fetch all enrichment statuses in parallel
    Promise.allSettled([
      api.getAugmentStatus(selectedProjectId),
      api.getEpistemicStatus(selectedProjectId),
      api.getModuleStatus(selectedProjectId),
    ]).then(([aug, epi, mod]) => {
      if (signal?.aborted || unmounted) return
      if (aug.status === 'fulfilled') dispatch({ type: 'AUGMENTATION_STATUS', payload: aug.value })
      if (epi.status === 'fulfilled') dispatch({ type: 'EPISTEMIC_STATUS', payload: epi.value })
      if (mod.status === 'fulfilled') dispatch({ type: 'MODULE_STATUS', payload: mod.value })
    })

    // Hydrate running flags + stage data from pipeline status
    api.getPipelineStatus(selectedProjectId).then((ps: PipelineStatus) => {
      if (signal?.aborted || unmounted) return
      // "Active" includes transient states (queued between stages, pausing,
      // recovering).  During these phases the pipeline is still "doing
      // something" — dropping all running flags would cause the UI to
      // erroneously evaluate idle-state logic and show 0-item stages as
      // "complete".
      const ACTIVE_PHASES = new Set(['running', 'queued', 'pausing', 'recovering'])
      const fastActive = ACTIVE_PHASES.has(ps.fast_sync?.phase ?? '')
      const deepActive = ACTIVE_PHASES.has(ps.deep_enrichment?.phase ?? '')
      dispatch({
        type: 'SYNC_RUNNING',
        inferredEdgesRunning: fastActive && (ps.fast_sync?.current_stage === 'inferred_edges' || false),
        augmenting: fastActive && (ps.fast_sync?.current_stage === 'catalogue' || ps.fast_sync?.current_stage === 'augment' || false),
        validating: fastActive && (ps.fast_sync?.current_stage === 'validation' || false),
        epistemicRunning: deepActive && (ps.deep_enrichment?.current_stage === 'enrichment' || false),
        groupReasoningRunning: deepActive && (ps.deep_enrichment?.current_stage === 'group_reasoning' || false),
        clusterRunning: deepActive && (ps.deep_enrichment?.current_stage === 'clustering' || false),
        atlasRunning: deepActive && (ps.deep_enrichment?.current_stage === 'atlas' || false),
        deepeningRunning: deepActive && (ps.deep_enrichment?.current_stage === 'deepening' || false),
        fastKnowledgeBuilding: fastActive && (ps.fast_sync?.current_stage === 'knowledge' || false),
        deepKnowledgeBuilding: deepActive && (ps.deep_enrichment?.current_stage === 'deep_knowledge' || false),
      })
      // Hydrate inferred_edges (no dedicated API endpoint — only in pipeline status)
      if (ps.stages?.inferred_edges) {
        dispatch({ type: 'INFERRED_EDGES_STATUS', payload: ps.stages.inferred_edges })
      }
      // Hydrate atlas status from pipeline (supplements App.tsx atlas fetch)
      if (ps.stages?.atlas) {
        dispatch({ type: 'ATLAS_STATUS', payload: ps.stages.atlas })
      }
      // Hydrate group reasoning (no dedicated API endpoint — only in pipeline status)
      if (ps.stages?.group_reasoning) {
        dispatch({ type: 'GROUP_REASONING_STATUS', payload: ps.stages.group_reasoning })
      }
      // Hydrate deepening and knowledge from pipeline status to ensure consistency
      // and avoid legacy API module gates that returned 0 scored objects.
      if (ps.stages?.deepening) {
        dispatch({ type: 'DEEPENING_STATUS', payload: ps.stages.deepening })
      }
      if (ps.stages?.deep_knowledge) {
        dispatch({ type: 'KNOWLEDGE_STATUS', payload: ps.stages.deep_knowledge })
      }
      // Hydrate paused flags on initial load
      dispatch({
        type: 'SYNC_PAUSED',
        fastPaused: ps.fast_sync?.phase === 'paused' || (ps.fast_sync?.phase === 'failed' && (ps.fast_sync?.error || '').includes('Paused by user')),
        deepPaused: ps.deep_enrichment?.phase === 'paused' || (ps.deep_enrichment?.phase === 'failed' && (ps.deep_enrichment?.error || '').includes('Paused by user')),
        fastPausedStage: (ps.fast_sync?.phase === 'paused' || (ps.fast_sync?.phase === 'failed' && (ps.fast_sync?.error || '').includes('Paused by user')))
          ? ps.fast_sync?.current_stage ?? undefined : undefined,
        deepPausedStage: (ps.deep_enrichment?.phase === 'paused' || (ps.deep_enrichment?.phase === 'failed' && (ps.deep_enrichment?.error || '').includes('Paused by user')))
          ? ps.deep_enrichment?.current_stage ?? undefined : undefined,
      })
    }).catch(() => { /* silent — SSE will provide updates */ })

    return () => { unmounted = true }
  }, [api, selectedProjectId])

  // ── SSE: enrichment-related pipeline updates ────────────────

  const pipelineEvent = selectedProjectId ? deps.pipelineEvents?.[selectedProjectId] : undefined
  const prevPipelineRef = useRef<typeof pipelineEvent>(undefined)

  useEffect(() => {
    if (!pipelineEvent || !selectedProjectId) return
    const prev = prevPipelineRef.current
    prevPipelineRef.current = pipelineEvent

    const fast = pipelineEvent.fast_sync
    const deep = pipelineEvent.deep_enrichment
    // Broad "active" for SYNC_RUNNING — keeps UI flags alive during
    // transient states so compute*State functions don't erroneously
    // evaluate idle-state logic (showing 0-item stages as "complete").
    const ACTIVE_PHASES = new Set(['running', 'queued', 'pausing', 'recovering'])
    const fastActive = ACTIVE_PHASES.has(fast?.phase ?? '')
    const deepActive = ACTIVE_PHASES.has(deep?.phase ?? '')

    // Sync running flags from current pipeline state
    dispatch({
      type: 'SYNC_RUNNING',
      inferredEdgesRunning: fastActive && (fast?.current_stage === 'inferred_edges' || false),
      augmenting: fastActive && (fast?.current_stage === 'augment' || fast?.current_stage === 'catalogue' || false),
      validating: fastActive && (fast?.current_stage === 'validation' || false),
      epistemicRunning: deepActive && (deep?.current_stage === 'enrichment' || false),
      groupReasoningRunning: deepActive && (deep?.current_stage === 'group_reasoning' || false),
      clusterRunning: deepActive && (deep?.current_stage === 'clustering' || false),
      atlasRunning: deepActive && (deep?.current_stage === 'atlas' || false),
      deepeningRunning: deepActive && (deep?.current_stage === 'deepening' || false),
      fastKnowledgeBuilding: fastActive && (fast?.current_stage === 'knowledge' || false),
      deepKnowledgeBuilding: deepActive && (deep?.current_stage === 'deep_knowledge' || false),
    })

    // Sync paused flags — state machine uses proper 'paused' phase;
    // also check legacy 'failed' + error containing 'Paused by user' for
    // backward compat (the error may be wrapped in "Stage X failed: ...")
    dispatch({
      type: 'SYNC_PAUSED',
      fastPaused: fast?.phase === 'paused' || (fast?.phase === 'failed' && (fast?.error || '').includes('Paused by user')),
      deepPaused: deep?.phase === 'paused' || (deep?.phase === 'failed' && (deep?.error || '').includes('Paused by user')),
      fastPausedStage: (fast?.phase === 'paused' || (fast?.phase === 'failed' && (fast?.error || '').includes('Paused by user')))
        ? fast?.current_stage ?? undefined : undefined,
      deepPausedStage: (deep?.phase === 'paused' || (deep?.phase === 'failed' && (deep?.error || '').includes('Paused by user')))
        ? deep?.current_stage ?? undefined : undefined,
    })

    // ── Detect transitions for status refresh ──

    const prevFastPhase = prev?.fast_sync?.phase
    const prevDeepPhase = prev?.deep_enrichment?.phase
    const prevDeepStage = prev?.deep_enrichment?.current_stage
    const currentDeepStage = deep?.current_stage

    // ── Per-stage transition refreshes (deep enrichment) ──
    // When pipeline moves past a stage, refresh that stage's status.
    // Stage order: enrichment → group_reasoning → clustering → atlas → deepening → deep_knowledge
    if (deepActive && prevDeepStage && currentDeepStage !== prevDeepStage) {
      // enrichment → group_reasoning: flush epistemic status
      if (prevDeepStage === 'enrichment') void fetchEpistemicStatus()
      // group_reasoning → clustering: refresh group reasoning via pipeline status
      if (prevDeepStage === 'group_reasoning') void refreshStageDataFromPipeline()
      // clustering → atlas: flush module status
      if (prevDeepStage === 'clustering') void fetchModuleStatus()
      // atlas → deepening: refresh atlas via pipeline status
      if (prevDeepStage === 'atlas') void refreshStageDataFromPipeline()
      // deepening → deep_knowledge: flush deepening status
      if (prevDeepStage === 'deepening') void fetchDeepeningStatus()
    }

    // ── Per-stage transition refreshes (fast sync) ──
    const prevFastStage = prev?.fast_sync?.current_stage
    const currentFastStage = fast?.current_stage
    if (fastActive && prevFastStage && currentFastStage !== prevFastStage) {
      // inferred_edges → catalogue: refresh inferred edges from pipeline status
      if (prevFastStage === 'inferred_edges') void refreshStageDataFromPipeline()
      // catalogue → validation: flush augmentation status
      if (prevFastStage === 'catalogue') void fetchAugmentationStatus()
    }

    // Fast sync completed → refresh fast-stage statuses
    // State machine allows queued→completed and queued→failed transitions,
    // so check for those in addition to running→completed/failed.
    const prevFastWasActive = prevFastPhase === 'running' || prevFastPhase === 'queued' || prevFastPhase === 'pausing'
    if (fast?.phase === 'completed' && prevFastWasActive) {
      dispatch({ type: 'FAST_COMPLETED' })
      void fetchAugmentationStatus()
      void fetchKnowledgeStatus()
      void refreshStageDataFromPipeline() // picks up final inferred_edges
      onFastCompletedRef.current?.()
    }
    if (fast?.phase === 'failed' && prevFastWasActive) {
      dispatch({ type: 'FAST_FAILED' })
    }

    // Deep enrichment completed → refresh deep-stage statuses
    const prevDeepWasActive = prevDeepPhase === 'running' || prevDeepPhase === 'queued' || prevDeepPhase === 'pausing'
    if (deep?.phase === 'completed' && prevDeepWasActive) {
      dispatch({ type: 'DEEP_COMPLETED' })
      void fetchEpistemicStatus()
      void fetchModuleStatus()
      void fetchDeepeningStatus()
      void fetchKnowledgeStatus()
      void refreshStageDataFromPipeline() // picks up final atlas + group_reasoning status
      onDeepCompletedRef.current?.()
    }
    if (deep?.phase === 'failed' && prevDeepWasActive) {
      dispatch({ type: 'DEEP_FAILED' })
    }
  }, [pipelineEvent, selectedProjectId,
    fetchAugmentationStatus, fetchKnowledgeStatus,
    fetchEpistemicStatus, fetchModuleStatus, fetchDeepeningStatus,
    refreshStageDataFromPipeline])

  // ── Polling: progress bar updates while stages are running ──

  useEffect(() => {
    if (!selectedProjectId) return
    if (deps.isHydrating) return
    const { inferredEdgesRunning, augmenting, epistemicRunning, groupReasoningRunning, clusterRunning, atlasRunning, deepeningRunning, fastKnowledgeBuilding, deepKnowledgeBuilding } = state
    const anyRunning = inferredEdgesRunning || augmenting || epistemicRunning || groupReasoningRunning || clusterRunning || atlasRunning || deepeningRunning || fastKnowledgeBuilding || deepKnowledgeBuilding
    if (!anyRunning) return

    const interval = setInterval(() => {
      if (state.inferredEdgesRunning || state.atlasRunning || state.groupReasoningRunning || state.augmenting || state.epistemicRunning) void refreshStageDataFromPipeline()
      if (state.augmenting) void fetchAugmentationStatus()
      if (state.epistemicRunning || state.clusterRunning || state.deepeningRunning) void fetchEpistemicStatus()
      if (state.clusterRunning) void fetchModuleStatus()
      if (state.deepeningRunning) void fetchDeepeningStatus()
      if (state.fastKnowledgeBuilding || state.deepKnowledgeBuilding) void fetchKnowledgeStatus()
    }, 3000)

    return () => clearInterval(interval)
  }, [
    selectedProjectId,
    state.inferredEdgesRunning,
    state.augmenting,
    state.epistemicRunning,
    state.groupReasoningRunning,
    state.clusterRunning,
    state.atlasRunning,
    state.deepeningRunning,
    state.fastKnowledgeBuilding,
    state.deepKnowledgeBuilding,
    fetchAugmentationStatus,
    fetchEpistemicStatus,
    fetchModuleStatus,
    fetchDeepeningStatus,
    fetchKnowledgeStatus,
    refreshStageDataFromPipeline,
  ])



  // ── Return ──────────────────────────────────────────────────

  return {
    // State (spread for flat access — same names as before)
    ...state,
    // Actions
    handleRunAugmentation,
    handleRunEpistemic,
    handleRunModuleSynthesis,
    handleRunDeepening,
    handleRunKnowledgeBuild,
    handleRunDeepEnrichment,
    handlePausePipeline,
    handleResumePipeline,
    handleSwapModel,
    // Fetch (for external callers that need manual refresh)
    fetchAugmentationStatus,
    fetchEpistemicStatus,
    fetchModuleStatus,
    fetchDeepeningStatus,
    fetchKnowledgeStatus,
    // Reset
    resetAll,
  }
}
