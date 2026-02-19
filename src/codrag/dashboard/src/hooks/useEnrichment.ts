import { useReducer, useCallback, useEffect, useRef } from 'react'
import { useApiClient, type PipelineStatus } from '@codrag/ui'
import {
  enrichmentReducer,
  initialEnrichmentState,
} from '../state/enrichmentReducer'

// ── Dependencies ──────────────────────────────────────────────

export interface UseEnrichmentDeps {
  onError: (msg: string) => void
  /** Pipeline SSE events keyed by project_id */
  pipelineEvents?: Record<string, PipelineStatus & { project_id: string }>
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

  // ── Run handlers ────────────────────────────────────────────

  const handleRunAugmentation = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'augmentation' })
    try {
      await api.runAugmentation(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'augmentation' })
      onErrorRef.current(e instanceof Error ? e.message : 'Augmentation failed')
    }
  }, [api, selectedProjectId])

  const handleRunEpistemic = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'epistemic' })
    try {
      await api.runEpistemic(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'epistemic' })
      onErrorRef.current(e instanceof Error ? e.message : 'Epistemic enrichment failed')
    }
  }, [api, selectedProjectId])

  const handleRunModuleSynthesis = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'modules' })
    try {
      await api.runModuleSynthesis(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'modules' })
      onErrorRef.current(e instanceof Error ? e.message : 'Module synthesis failed')
    }
  }, [api, selectedProjectId])

  const handleRunDeepening = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'deepening' })
    try {
      await api.runDeepening(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'deepening' })
      onErrorRef.current(e instanceof Error ? e.message : 'Deepening loop failed')
    }
  }, [api, selectedProjectId])

  const handleRunKnowledgeBuild = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'knowledge' })
    try {
      await api.runKnowledgeBuild(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'knowledge' })
      onErrorRef.current(e instanceof Error ? e.message : 'Knowledge build failed')
    }
  }, [api, selectedProjectId])

  const handleRunDeepEnrichment = useCallback(async () => {
    if (!selectedProjectId) return
    dispatch({ type: 'STAGE_STARTED', stage: 'deep_enrichment' })
    try {
      await api.runPipelineDeep(selectedProjectId)
    } catch (e) {
      dispatch({ type: 'STAGE_FAILED', stage: 'deep_enrichment' })
      onErrorRef.current(e instanceof Error ? e.message : 'Deep enrichment failed')
    }
  }, [api, selectedProjectId])

  // ── Reset (called by destroy handlers in useTraceSystem) ────

  const resetAll = useCallback(() => {
    dispatch({ type: 'DESTROYED' })
  }, [])

  // ── Hydration: fetch all statuses + pipeline flags on project change ──

  useEffect(() => {
    if (!selectedProjectId) return
    let cancelled = false

    // Fetch all enrichment statuses in parallel
    Promise.allSettled([
      api.getAugmentStatus(selectedProjectId),
      api.getEpistemicStatus(selectedProjectId),
      api.getModuleStatus(selectedProjectId),
      api.getDeepeningStatus(selectedProjectId),
      api.getKnowledgeStatus(selectedProjectId),
    ]).then(([aug, epi, mod, deep, know]) => {
      if (cancelled) return
      if (aug.status === 'fulfilled') dispatch({ type: 'AUGMENTATION_STATUS', payload: aug.value })
      if (epi.status === 'fulfilled') dispatch({ type: 'EPISTEMIC_STATUS', payload: epi.value })
      if (mod.status === 'fulfilled') dispatch({ type: 'MODULE_STATUS', payload: mod.value })
      if (deep.status === 'fulfilled') dispatch({ type: 'DEEPENING_STATUS', payload: deep.value })
      if (know.status === 'fulfilled') dispatch({ type: 'KNOWLEDGE_STATUS', payload: know.value })
    })

    // Hydrate running flags from pipeline status
    api.getPipelineStatus(selectedProjectId).then((ps: PipelineStatus) => {
      if (cancelled) return
      const fastRunning = ps.fast_sync?.phase === 'running'
      const deepRunning = ps.deep_enrichment?.phase === 'running'
      dispatch({
        type: 'SYNC_RUNNING',
        augmenting: fastRunning && (ps.fast_sync?.current_stage === 'catalogue' || ps.fast_sync?.current_stage === 'augment' || false),
        validating: fastRunning && (ps.fast_sync?.current_stage === 'validation' || false),
        epistemicRunning: deepRunning && (ps.deep_enrichment?.current_stage === 'enrichment' || false),
        clusterRunning: deepRunning && (ps.deep_enrichment?.current_stage === 'clustering' || false),
        deepeningRunning: deepRunning && (ps.deep_enrichment?.current_stage === 'deepening' || false),
        knowledgeBuilding:
          (fastRunning && ps.fast_sync?.current_stage === 'knowledge') ||
          (deepRunning && ps.deep_enrichment?.current_stage === 'deep_knowledge'),
      })
    }).catch(() => { /* silent — SSE will provide updates */ })

    return () => { cancelled = true }
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
    const fastRunning = fast?.phase === 'running'
    const deepRunning = deep?.phase === 'running'

    // Sync running flags from current pipeline state
    dispatch({
      type: 'SYNC_RUNNING',
      augmenting: fastRunning && (fast?.current_stage === 'augment' || fast?.current_stage === 'catalogue' || false),
      validating: fastRunning && (fast?.current_stage === 'validation' || false),
      epistemicRunning: deepRunning && (deep?.current_stage === 'enrichment' || false),
      clusterRunning: deepRunning && (deep?.current_stage === 'clustering' || false),
      deepeningRunning: deepRunning && (deep?.current_stage === 'deepening' || false),
      knowledgeBuilding:
        (fastRunning && fast?.current_stage === 'knowledge') ||
        (deepRunning && deep?.current_stage === 'deep_knowledge'),
    })

    // ── Detect transitions for status refresh ──

    const prevFastPhase = prev?.fast_sync?.phase
    const prevDeepPhase = prev?.deep_enrichment?.phase
    const prevDeepStage = prev?.deep_enrichment?.current_stage
    const currentDeepStage = deep?.current_stage

    // When deep pipeline moves away from 'enrichment' stage, flush epistemic status
    if (prevDeepStage === 'enrichment' && currentDeepStage !== 'enrichment' && deepRunning) {
      void fetchEpistemicStatus()
    }

    // Fast sync completed → refresh fast-stage statuses
    if (fast?.phase === 'completed' && prevFastPhase === 'running') {
      dispatch({ type: 'FAST_COMPLETED' })
      void fetchAugmentationStatus()
      void fetchKnowledgeStatus()
    }
    if (fast?.phase === 'failed' && prevFastPhase === 'running') {
      dispatch({ type: 'FAST_FAILED' })
    }

    // Deep enrichment completed → refresh deep-stage statuses
    if (deep?.phase === 'completed' && prevDeepPhase === 'running') {
      dispatch({ type: 'DEEP_COMPLETED' })
      void fetchEpistemicStatus()
      void fetchModuleStatus()
      void fetchDeepeningStatus()
      void fetchKnowledgeStatus()
    }
    if (deep?.phase === 'failed' && prevDeepPhase === 'running') {
      dispatch({ type: 'DEEP_FAILED' })
    }
  }, [pipelineEvent, selectedProjectId,
    fetchAugmentationStatus, fetchKnowledgeStatus,
    fetchEpistemicStatus, fetchModuleStatus, fetchDeepeningStatus])

  // ── Polling: progress bar updates while stages are running ──

  useEffect(() => {
    if (!selectedProjectId) return
    const { augmenting, epistemicRunning, clusterRunning, deepeningRunning, knowledgeBuilding } = state
    const anyRunning = augmenting || epistemicRunning || clusterRunning || deepeningRunning || knowledgeBuilding
    if (!anyRunning) return

    const interval = setInterval(() => {
      if (state.augmenting) void fetchAugmentationStatus()
      if (state.epistemicRunning || state.clusterRunning || state.deepeningRunning) void fetchEpistemicStatus()
      if (state.clusterRunning) void fetchModuleStatus()
      if (state.deepeningRunning) void fetchDeepeningStatus()
      if (state.knowledgeBuilding) void fetchKnowledgeStatus()
    }, 3000)

    return () => clearInterval(interval)
  }, [
    selectedProjectId,
    state.augmenting,
    state.epistemicRunning,
    state.clusterRunning,
    state.deepeningRunning,
    state.knowledgeBuilding,
    fetchAugmentationStatus,
    fetchEpistemicStatus,
    fetchModuleStatus,
    fetchDeepeningStatus,
    fetchKnowledgeStatus,
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
