import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type ProjectConfig,
  type EnrichmentAutoConfig,
  type PipelineStatus,
  type CrashedPipelineRun,
} from '@codrag/ui'

// ── Inline types (not exported from @codrag/ui as named types) ──

export interface TraceStatus {
  enabled: boolean
  exists: boolean
  building: boolean
  counts: { nodes: number; edges: number }
  engine?: string
}

export interface TraceCoverageFile {
  path: string; language: string | null; size: number; modified: string; created: string
}

export interface TraceCoverage {
  summary: { total: number; traced: number; pending_embedding?: number; untraced: number; stale: number; excluded: number; coverage_pct: number; last_build_at: string | null } | null
  untraced: TraceCoverageFile[]
  stale: TraceCoverageFile[]
  excluded: TraceCoverageFile[]
  building: boolean
  loading: boolean
}

// ── Dependencies interface ───────────────────────────────────

export interface UseTraceSystemDeps {
  projectConfig: ProjectConfig
  setProjectConfig: (cfg: ProjectConfig) => void
  setConfigDirty: (dirty: boolean) => void
  resetDeepAnalysisStatus: () => void
  refreshStatus: (projectId: string) => void
  onResetSearch: () => void
  onError: (msg: string) => void
  findActiveTask: (type: 'index_build' | 'trace_build') => { status: string; task_id: string } | undefined
  /** Pipeline SSE events keyed by project_id (Phase 24) */
  pipelineEvents?: Record<string, PipelineStatus & { project_id: string }>
  /** Watch system handlers for auto-rebuild integration */
  startWatch?: () => Promise<void>
  stopWatch?: () => Promise<void>
  refreshWatchStatus?: (projectId: string) => Promise<void>
  /** Re-fetch the file tree after index destroy so status annotations refresh */
  refreshFileTree?: (projectId: string) => Promise<void>
  /** Clear included paths state + localStorage after full reset */
  clearIncludedPaths?: () => void
  /** Reset all enrichment state (called during destroy) */
  resetEnrichment?: () => void
}

// ── Hook ─────────────────────────────────────────────────────

/**
 * Manages trace pipeline: trace build, coverage, SSE reactions for trace status,
 * auto-config persistence, crash recovery, and graph/index destroy operations.
 * Enrichment stages are managed by useEnrichment.
 */
export function useTraceSystem(selectedProjectId: string | null, deps: UseTraceSystemDeps) {
  const api = useApiClient()

  // Refs for callbacks that shouldn't trigger re-renders
  const onErrorRef = useRef(deps.onError)
  onErrorRef.current = deps.onError
  const onResetSearchRef = useRef(deps.onResetSearch)
  onResetSearchRef.current = deps.onResetSearch
  const resetDeepAnalysisRef = useRef(deps.resetDeepAnalysisStatus)
  resetDeepAnalysisRef.current = deps.resetDeepAnalysisStatus
  const refreshStatusRef = useRef(deps.refreshStatus)
  refreshStatusRef.current = deps.refreshStatus
  const startWatchRef = useRef(deps.startWatch)
  startWatchRef.current = deps.startWatch
  const stopWatchRef = useRef(deps.stopWatch)
  stopWatchRef.current = deps.stopWatch
  const refreshWatchStatusRef = useRef(deps.refreshWatchStatus)
  refreshWatchStatusRef.current = deps.refreshWatchStatus
  const refreshFileTreeRef = useRef(deps.refreshFileTree)
  refreshFileTreeRef.current = deps.refreshFileTree
  const clearIncludedPathsRef = useRef(deps.clearIncludedPaths)
  clearIncludedPathsRef.current = deps.clearIncludedPaths
  const resetEnrichmentRef = useRef(deps.resetEnrichment)
  resetEnrichmentRef.current = deps.resetEnrichment

  // ── State ───────────────────────────────────────────────────
  const [indexAutoRebuild, setIndexAutoRebuild] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('codrag_index_auto_rebuild')
      return stored === 'true'
    } catch { return false }
  })
  const [enrichmentAutoConfig, setEnrichmentAutoConfig] = useState<EnrichmentAutoConfig>(
    { fastSync: true, deepEnrichment: 'manual' }
  )

  // Phase 25: Crash Protection
  const [crashedRuns, setCrashedRuns] = useState<CrashedPipelineRun[]>([])

  // Load enrichment auto config from backend settings (Phase 24)
  useEffect(() => {
    let cancelled = false
    api.getSetting('pipeline_config').then((result: { key: string; value: any }) => {
      if (cancelled) return
      const pc = result?.value
      if (pc) {
        setEnrichmentAutoConfig({
          fastSync: pc.fast_sync?.auto ?? true,
          deepEnrichment: pc.deep_enrichment?.mode ?? 'manual',
        })
      }
    }).catch(() => {
      // Fall back to localStorage for migration
      try {
        const stored = localStorage.getItem('codrag_enrichment_auto_config')
        if (stored) {
          const parsed = JSON.parse(stored)
          const deep = parsed.deepEnrichment
          setEnrichmentAutoConfig({
            fastSync: parsed.fastSync ?? true,
            deepEnrichment: (deep === 'manual' || deep === 'auto' || deep === 'scheduled') ? deep : 'manual',
          })
        }
      } catch { /* ignore */ }
    })
    return () => { cancelled = true }
  }, [api])
  const [traceStatus, setTraceStatus] = useState<TraceStatus>({
    enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 },
  })
  const [traceCoverage, setTraceCoverage] = useState<TraceCoverage>({
    summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false,
  })

  // Load pipeline status on project selection (Phase 24 — initial hydration)
  // Phase 25: also detect crashed runs for the crash recovery banner
  useEffect(() => {
    if (!selectedProjectId) return
    let cancelled = false
    api.getPipelineStatus(selectedProjectId).then((ps: PipelineStatus) => {
      if (cancelled) return
      const fastRunning = ps.fast_sync?.phase === 'running'
      setTraceStatus(p => ({ ...p, building: fastRunning }))
      // Phase 25: update crashed runs from the status response
      setCrashedRuns(ps.crashed_runs ?? [])
    }).catch(() => { /* silent — SSE will provide updates */ })
    return () => { cancelled = true }
  }, [api, selectedProjectId])

  // ── Fetch functions ─────────────────────────────────────────

  const fetchTraceCoverage = useCallback(() => {
    if (!selectedProjectId || !traceStatus.enabled) return
    setTraceCoverage(prev => ({ ...prev, loading: true }))
    api.getTraceCoverage(selectedProjectId).then((data) => {
      setTraceCoverage({
        summary: data.summary,
        untraced: data.untraced,
        stale: data.stale,
        excluded: data.excluded ?? (data as any).ignored ?? [],
        building: data.building,
        loading: false,
      })
    }).catch(() => {
      setTraceCoverage(prev => ({ ...prev, loading: false }))
    })
  }, [api, selectedProjectId, traceStatus.enabled])

  // ── Trace handlers ──────────────────────────────────────────

  const handleSearchTrace = useCallback(async (query: string, kinds?: string[], limit?: number) => {
    if (!selectedProjectId) return { nodes: [] }
    return api.searchTrace(selectedProjectId, query, kinds, limit)
  }, [api, selectedProjectId])

  const handleGetTraceNode = useCallback(async (nodeId: string) => {
    if (!selectedProjectId) throw new Error('No project selected')
    return api.getTraceNode(selectedProjectId, nodeId)
  }, [api, selectedProjectId])

  const handleGetTraceNeighbors = useCallback(async (nodeId: string, direction?: string) => {
    if (!selectedProjectId) throw new Error('No project selected')
    return api.getTraceNeighbors(selectedProjectId, nodeId, direction)
  }, [api, selectedProjectId])

  const handleBuildTrace = useCallback(() => {
    if (!selectedProjectId) return
    api.buildTrace(selectedProjectId).then(() => {
      setTraceStatus(prev => ({ ...prev, building: true }))
    }).catch(() => {})
  }, [api, selectedProjectId])

  const handleEnableTrace = useCallback(() => {
    if (!selectedProjectId) return
    const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig.trace, enabled: true } }
    deps.setProjectConfig(newConfig)
    deps.setConfigDirty(true)
    api.updateProject(selectedProjectId, { config: newConfig }).catch(() => {})
    setTraceStatus(prev => ({ ...prev, enabled: true }))
  }, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  const handleTogglePause = useCallback(() => {
    if (!selectedProjectId) return
    const newPaused = !deps.projectConfig.trace.paused
    const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig.trace, paused: newPaused } }
    deps.setProjectConfig(newConfig)
    deps.setConfigDirty(true)
    api.updateProject(selectedProjectId, { config: newConfig }).catch(() => {})
  }, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  const handleTraceAll = useCallback(() => {
    if (!selectedProjectId) return
    api.buildTrace(selectedProjectId).then(() => {
      setTraceStatus(prev => ({ ...prev, building: true }))
      setTraceCoverage(prev => ({ ...prev, building: true }))
    }).catch(() => {})
  }, [api, selectedProjectId])

  const handleRetraceStale = useCallback(() => {
    handleTraceAll()
  }, [handleTraceAll])

  const handleAddExcludePattern = useCallback((pattern: string) => {
    if (!selectedProjectId) return
    api.updateTraceIgnore(selectedProjectId, 'add', [pattern]).then(() => {
      fetchTraceCoverage()
    }).catch(() => {})
  }, [api, selectedProjectId, fetchTraceCoverage])

  const handleRemoveExcludePattern = useCallback((pattern: string) => {
    if (!selectedProjectId) return
    api.updateTraceIgnore(selectedProjectId, 'remove', [pattern]).then(() => {
      fetchTraceCoverage()
    }).catch(() => {})
  }, [api, selectedProjectId, fetchTraceCoverage])

  // ── Pipeline handlers ──────────────────────────────────────

  const handleRunFastSync = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      // Ensure trace is enabled in project config before launching pipeline
      // (project_trace_status returns exists:false when trace.enabled is false)
      if (!deps.projectConfig?.trace?.enabled) {
        const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig?.trace, enabled: true } }
        deps.setProjectConfig(newConfig)
        deps.setConfigDirty(true)
        api.updateProject(selectedProjectId, { config: newConfig }).catch(() => {})
      }
      setTraceStatus(prev => ({ ...prev, enabled: true, building: true }))
      await api.runPipelineFast(selectedProjectId)
    } catch (e) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      onErrorRef.current(e instanceof Error ? e.message : 'Fast sync failed')
    }
  }, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  const handleRunAutoPilot = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setTraceStatus(prev => ({ ...prev, building: true }))
      await api.runPipelineAll(selectedProjectId)
    } catch (e) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      onErrorRef.current(e instanceof Error ? e.message : 'Auto-pilot failed')
    }
  }, [api, selectedProjectId])

  // ── Config persistence handlers ─────────────────────────────

  const handleEnrichmentAutoConfigChange = useCallback((config: EnrichmentAutoConfig) => {
    setEnrichmentAutoConfig(config)
    // Persist to backend settings (Phase 24)
    api.updatePipelineConfig({
      fast_sync_auto: config.fastSync,
      deep_enrichment_mode: config.deepEnrichment,
    }).catch(() => { /* silent */ })
    // Keep localStorage as fallback
    localStorage.setItem('codrag_enrichment_auto_config', JSON.stringify(config))
  }, [api])

  const handleIndexAutoRebuildChange = useCallback(async (auto: boolean) => {
    setIndexAutoRebuild(auto)
    localStorage.setItem('codrag_index_auto_rebuild', String(auto))

    if (!selectedProjectId) return

    if (auto) {
      // Switching to Auto: start watcher for continuous updates
      try {
        await startWatchRef.current?.()
        await refreshWatchStatusRef.current?.(selectedProjectId)
      } catch {
        // Watcher start may fail if feature-gated; fall through silently
      }
    } else {
      // Switching to Manual: stop watcher
      try {
        await stopWatchRef.current?.()
        await refreshWatchStatusRef.current?.(selectedProjectId)
      } catch {
        // silent
      }
    }
  }, [selectedProjectId])

  // ── Phase 25: Crash Recovery handlers ───────────────────────

  const handleResumeCrashedRun = useCallback(async (runId: string) => {
    try {
      await api.resumeCrashedRun(runId)
      setCrashedRuns(prev => prev.filter(r => r.run_id !== runId))
      // The resumed pipeline will trigger SSE events, which will update running flags
      if (selectedProjectId) {
        setTraceStatus(p => ({ ...p, building: true }))
      }
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to resume pipeline')
    }
  }, [api, selectedProjectId])

  const handleDiscardCrashedRun = useCallback(async (runId: string) => {
    try {
      await api.discardCrashedRun(runId)
      setCrashedRuns(prev => prev.filter(r => r.run_id !== runId))
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to discard crashed run')
    }
  }, [api])

  // ── Destroy handlers ────────────────────────────────────────

  const handleDestroyGraph = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyGraph(selectedProjectId)
      setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } })
      setTraceCoverage({ summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false })
      resetEnrichmentRef.current?.()
      resetDeepAnalysisRef.current()
      void refreshStatusRef.current(selectedProjectId)
      setTimeout(() => {
        api.getTraceCoverage(selectedProjectId).then((data) => {
          setTraceCoverage({ summary: data.summary, untraced: data.untraced, stale: data.stale, excluded: data.excluded ?? [], building: false, loading: false })
        }).catch(() => {})
      }, 300)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to destroy graph')
    }
  }, [api, selectedProjectId])

  const handleDestroyIndex = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyIndex(selectedProjectId)
      setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } })
      setTraceCoverage({ summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false })
      resetEnrichmentRef.current?.()
      resetDeepAnalysisRef.current()
      onResetSearchRef.current()
      // Clear included paths and re-fetch the file tree so "Indexed" badges disappear
      clearIncludedPathsRef.current?.()
      void refreshStatusRef.current(selectedProjectId)
      // Re-fetch file tree after a short delay so backend caches are cleared
      setTimeout(() => {
        refreshFileTreeRef.current?.(selectedProjectId)
        api.getTraceCoverage(selectedProjectId).then((data) => {
          setTraceCoverage({ summary: data.summary, untraced: data.untraced, stale: data.stale, excluded: data.excluded ?? [], building: false, loading: false })
        }).catch(() => {})
      }, 300)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Failed to reset project data')
    }
  }, [api, selectedProjectId])

  // ── SSE: auto-refresh coverage when trace build completes ───

  const prevTraceBuildStatusRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    const traceTask = deps.findActiveTask('trace_build')
    const prevStatus = prevTraceBuildStatusRef.current
    prevTraceBuildStatusRef.current = traceTask?.status

    if (traceTask && prevStatus === 'running' && (traceTask.status === 'completed' || traceTask.status === 'failed')) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      setTraceCoverage(prev => ({ ...prev, building: false }))
      if (traceTask.status === 'completed' && selectedProjectId) {
        api.getTraceStatus(selectedProjectId).then((data) => {
          setTraceStatus({
            enabled: data.enabled ?? false,
            exists: data.exists ?? false,
            building: false,
            counts: data.counts ?? { nodes: 0, edges: 0 },
            engine: data.engine,
          })
        }).catch(() => {})
        setTimeout(() => fetchTraceCoverage(), 500)
      }
    }
  }, [deps.findActiveTask, fetchTraceCoverage, api, selectedProjectId])

  // ── SSE: reactive pipeline status updates (Phase 24) ────────
  // Trace-related SSE reactions only. Enrichment SSE is handled by useEnrichment.

  const pipelineEvent = selectedProjectId ? deps.pipelineEvents?.[selectedProjectId] : undefined
  const prevPipelineRef = useRef<typeof pipelineEvent>(undefined)

  useEffect(() => {
    if (!pipelineEvent || !selectedProjectId) return
    const prev = prevPipelineRef.current
    prevPipelineRef.current = pipelineEvent

    const fast = pipelineEvent.fast_sync

    // Update trace building flag from fast_sync phase
    const fastRunning = fast?.phase === 'running'
    const prevFastPhase = prev?.fast_sync?.phase

    // When fast sync transitions running→completed, don't clear building yet;
    // the completion handler below will clear it after fetching the real status.
    const fastJustCompleted = fast?.phase === 'completed' && prevFastPhase === 'running'
    if (!fastJustCompleted) {
      setTraceStatus(p => ({ ...p, building: fastRunning }))
    }

    // Detect completion of structural stage to update coverage immediately
    const currentFastStage = fast?.current_stage
    const prevFastStage = prev?.fast_sync?.current_stage

    if (prevFastStage === 'structural' && currentFastStage && currentFastStage !== 'structural') {
        // Structural stage just finished → refresh coverage now
        // Retry a few times to handle filesystem latency (hashing backfill race)
        const refresh = () => {
            void fetchTraceCoverage()
            if (selectedProjectId) {
                api.getTraceStatus(selectedProjectId).then((data) => {
                    setTraceStatus(prev => ({
                        ...prev,
                        enabled: data.enabled ?? false,
                        exists: data.exists ?? false,
                        counts: data.counts ?? { nodes: 0, edges: 0 },
                        engine: data.engine,
                    }))
                }).catch(() => {})
            }
        }
        refresh()
        setTimeout(refresh, 1000)
        setTimeout(refresh, 3000)
    }

    // Fast sync completed → refresh trace status + coverage
    if (fast?.phase === 'completed' && prevFastPhase === 'running') {
      void fetchTraceCoverage()
      api.getTraceStatus(selectedProjectId).then((data) => {
        setTraceStatus({
          enabled: data.enabled ?? false,
          exists: data.exists ?? false,
          building: false,
          counts: data.counts ?? { nodes: 0, edges: 0 },
          engine: data.engine,
        })
      }).catch(() => {
        setTraceStatus(p => ({ ...p, building: false }))
      })
    }

    if (fast?.phase === 'failed' && prevFastPhase === 'running') {
      setTraceStatus(p => ({ ...p, building: false }))
    }

    // Deep enrichment completed → refresh trace coverage
    const prevDeepPhase = prev?.deep_enrichment?.phase
    const deep = pipelineEvent.deep_enrichment
    if (deep?.phase === 'completed' && prevDeepPhase === 'running') {
      void fetchTraceCoverage()
    }
  }, [pipelineEvent, selectedProjectId, api, fetchTraceCoverage])

  // ── Polling: trace coverage during build ─────────────────────
  useEffect(() => {
    if (!selectedProjectId || !traceStatus.building) return
    const interval = setInterval(() => { fetchTraceCoverage() }, 3000)
    return () => clearInterval(interval)
  }, [selectedProjectId, traceStatus.building, fetchTraceCoverage])

  // ── Return ──────────────────────────────────────────────────

  return {
    // State
    traceStatus, setTraceStatus,
    traceCoverage, setTraceCoverage,
    indexAutoRebuild,
    enrichmentAutoConfig,
    // Phase 25: Crash Protection
    crashedRuns,
    handleResumeCrashedRun,
    handleDiscardCrashedRun,
    // Fetch
    fetchTraceCoverage,
    // Trace
    handleBuildTrace, handleEnableTrace, handleTogglePause,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleTraceAll, handleRetraceStale,
    handleAddExcludePattern, handleRemoveExcludePattern,
    // Pipeline
    handleRunFastSync, handleRunAutoPilot,
    // Config
    handleEnrichmentAutoConfigChange, handleIndexAutoRebuildChange,
    // Destroy
    handleDestroyGraph, handleDestroyIndex,
  }
}
