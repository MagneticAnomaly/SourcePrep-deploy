import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type ProjectConfig,
  type AugmentationStatus,
  type EpistemicStatus,
  type ModuleStatus,
  type DeepeningStatus,
  type KnowledgeEmbeddingStatus,
  type EnrichmentAutoConfig,
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
  summary: { total: number; traced: number; untraced: number; stale: number; excluded: number; coverage_pct: number; last_build_at: string | null } | null
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
}

// ── Hook ─────────────────────────────────────────────────────

/**
 * Manages the trace/enrichment pipeline: trace build, coverage, augmentation,
 * epistemic enrichment, module synthesis, deepening, knowledge embedding,
 * auto-config persistence, and graph/index destroy operations.
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

  // ── State ───────────────────────────────────────────────────

  const [augmentationStatus, setAugmentationStatus] = useState<AugmentationStatus>({
    enabled: false, total_nodes: 0, augmented_nodes: 0, validated_nodes: 0,
    avg_confidence: 0, low_confidence_count: 0,
  })
  const [augmenting, setAugmenting] = useState(false)
  const [epistemicStatus, setEpistemicStatus] = useState<EpistemicStatus>({
    enabled: false, enriched_nodes: 0, avg_confidence: 0, running: false,
  })
  const [epistemicRunning, setEpistemicRunning] = useState(false)
  const [moduleStatus, setModuleStatus] = useState<ModuleStatus>({
    enabled: false, module_count: 0, total_files_clustered: 0, running: false,
  })
  const [clusterRunning, setClusterRunning] = useState(false)
  const [deepeningStatus, setDeepeningStatus] = useState<DeepeningStatus>({
    running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0,
  })
  const [deepeningRunning, setDeepeningRunning] = useState(false)
  const [knowledgeStatus, setKnowledgeStatus] = useState<KnowledgeEmbeddingStatus>({
    enabled: false, running: false, chunks_embedded: 0, last_run_at: null,
  })
  const [knowledgeBuilding, setKnowledgeBuilding] = useState(false)
  const [indexAutoRebuild, setIndexAutoRebuild] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('codrag_index_auto_rebuild')
      return stored === 'true'
    } catch { return false }
  })
  const [enrichmentAutoConfig, setEnrichmentAutoConfig] = useState<EnrichmentAutoConfig>(() => {
    try {
      const stored = localStorage.getItem('codrag_enrichment_auto_config')
      if (stored) {
        const parsed = JSON.parse(stored)
        const deep = parsed.deepEnrichment
        return {
          fastSync: parsed.fastSync ?? true,
          deepEnrichment: (deep === 'manual' || deep === 'auto' || deep === 'scheduled') ? deep : 'manual',
        }
      }
      return { fastSync: true, deepEnrichment: 'manual' }
    } catch {
      return { fastSync: true, deepEnrichment: 'manual' }
    }
  })
  const [traceStatus, setTraceStatus] = useState<TraceStatus>({
    enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 },
  })
  const [traceCoverage, setTraceCoverage] = useState<TraceCoverage>({
    summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false,
  })

  // ── Fetch functions ─────────────────────────────────────────

  const fetchAugmentationStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getAugmentStatus(selectedProjectId)
      setAugmentationStatus(status)
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchEpistemicStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getEpistemicStatus(selectedProjectId)
      setEpistemicStatus(status)
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchModuleStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getModuleStatus(selectedProjectId)
      setModuleStatus(status)
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchDeepeningStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getDeepeningStatus(selectedProjectId)
      setDeepeningStatus(status)
    } catch { /* silent */ }
  }, [api, selectedProjectId])

  const fetchKnowledgeStatus = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const status = await api.getKnowledgeStatus(selectedProjectId)
      setKnowledgeStatus(status)
    } catch { /* silent */ }
  }, [api, selectedProjectId])

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

  // ── Enrichment handlers ─────────────────────────────────────

  const handleRunAugmentation = useCallback(async () => {
    if (!selectedProjectId) return
    setAugmenting(true)
    try {
      await api.runAugmentation(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getAugmentStatus(selectedProjectId)
          setAugmentationStatus(status)
        } catch { /* ignore */ }
      }, 3000)
      setTimeout(() => {
        clearInterval(poll)
        setAugmenting(false)
        void fetchAugmentationStatus()
      }, 300000)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Augmentation failed')
      setAugmenting(false)
    }
  }, [api, selectedProjectId])

  const handleRunEpistemic = useCallback(async () => {
    if (!selectedProjectId) return
    setEpistemicRunning(true)
    try {
      await api.runEpistemic(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getEpistemicStatus(selectedProjectId)
          setEpistemicStatus(status)
          if (!status.running) { clearInterval(poll); setEpistemicRunning(false) }
        } catch { clearInterval(poll); setEpistemicRunning(false) }
      }, 3000)
    } catch (e) {
      setEpistemicRunning(false)
      onErrorRef.current(e instanceof Error ? e.message : 'Epistemic enrichment failed')
    }
  }, [api, selectedProjectId])

  const handleRunModuleSynthesis = useCallback(async () => {
    if (!selectedProjectId) return
    setClusterRunning(true)
    try {
      await api.runModuleSynthesis(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getModuleStatus(selectedProjectId)
          setModuleStatus(status)
          if (!status.running) { clearInterval(poll); setClusterRunning(false) }
        } catch { clearInterval(poll); setClusterRunning(false) }
      }, 3000)
    } catch (e) {
      setClusterRunning(false)
      onErrorRef.current(e instanceof Error ? e.message : 'Module synthesis failed')
    }
  }, [api, selectedProjectId])

  const handleRunDeepening = useCallback(async () => {
    if (!selectedProjectId) return
    setDeepeningRunning(true)
    try {
      await api.runDeepening(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getDeepeningStatus(selectedProjectId)
          setDeepeningStatus(status)
          if (!status.running) { clearInterval(poll); setDeepeningRunning(false) }
        } catch { clearInterval(poll); setDeepeningRunning(false) }
      }, 3000)
    } catch (e) {
      setDeepeningRunning(false)
      onErrorRef.current(e instanceof Error ? e.message : 'Deepening loop failed')
    }
  }, [api, selectedProjectId])

  const handleRunKnowledgeBuild = useCallback(async () => {
    if (!selectedProjectId) return
    setKnowledgeBuilding(true)
    try {
      await api.runKnowledgeBuild(selectedProjectId)
      const poll = setInterval(async () => {
        try {
          const status = await api.getKnowledgeStatus(selectedProjectId)
          setKnowledgeStatus(status)
          if (!status.running) { clearInterval(poll); setKnowledgeBuilding(false) }
        } catch { clearInterval(poll); setKnowledgeBuilding(false) }
      }, 3000)
    } catch (e) {
      setKnowledgeBuilding(false)
      onErrorRef.current(e instanceof Error ? e.message : 'Knowledge build failed')
    }
  }, [api, selectedProjectId])

  const handleRunFastSync = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setTraceStatus(prev => ({ ...prev, building: true }))
      await api.buildTrace(selectedProjectId)
    } catch (e) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      onErrorRef.current(e instanceof Error ? e.message : 'Fast sync failed')
    }
  }, [api, selectedProjectId])

  const handleRunDeepEnrichment = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.runEpistemic(selectedProjectId)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Deep enrichment failed')
    }
  }, [api, selectedProjectId])

  const handleRunAutoPilot = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.buildTrace(selectedProjectId)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Auto-pilot failed')
    }
  }, [api, selectedProjectId])

  // ── Config persistence handlers ─────────────────────────────

  const handleEnrichmentAutoConfigChange = useCallback((config: EnrichmentAutoConfig) => {
    setEnrichmentAutoConfig(config)
    localStorage.setItem('codrag_enrichment_auto_config', JSON.stringify(config))
  }, [])

  const handleIndexAutoRebuildChange = useCallback((auto: boolean) => {
    setIndexAutoRebuild(auto)
    localStorage.setItem('codrag_index_auto_rebuild', String(auto))
  }, [])

  // ── Destroy handlers ────────────────────────────────────────

  const handleDestroyGraph = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyGraph(selectedProjectId)
      setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } })
      setAugmentationStatus({ enabled: false, total_nodes: 0, augmented_nodes: 0, validated_nodes: 0, avg_confidence: 0, low_confidence_count: 0 })
      resetDeepAnalysisRef.current()
      setEpistemicStatus({ enabled: false, enriched_nodes: 0, avg_confidence: 0, running: false })
      setModuleStatus({ enabled: false, module_count: 0, total_files_clustered: 0, running: false })
      setDeepeningStatus({ running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0 })
      setTraceCoverage({ summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false })
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
      setAugmentationStatus({ enabled: false, total_nodes: 0, augmented_nodes: 0, validated_nodes: 0, avg_confidence: 0, low_confidence_count: 0 })
      resetDeepAnalysisRef.current()
      setEpistemicStatus({ enabled: false, enriched_nodes: 0, avg_confidence: 0, running: false })
      setModuleStatus({ enabled: false, module_count: 0, total_files_clustered: 0, running: false })
      setDeepeningStatus({ running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0 })
      onResetSearchRef.current()
      setTraceCoverage({ summary: null, untraced: [], stale: [], excluded: [], building: false, loading: false })
      void refreshStatusRef.current(selectedProjectId)
      setTimeout(() => {
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

  // ── Return ──────────────────────────────────────────────────

  return {
    // State
    traceStatus, setTraceStatus,
    traceCoverage, setTraceCoverage,
    augmentationStatus, augmenting,
    epistemicStatus, epistemicRunning,
    moduleStatus, clusterRunning,
    deepeningStatus, deepeningRunning,
    knowledgeStatus, knowledgeBuilding,
    indexAutoRebuild, enrichmentAutoConfig,
    // Fetch
    fetchAugmentationStatus, fetchEpistemicStatus, fetchModuleStatus,
    fetchDeepeningStatus, fetchKnowledgeStatus, fetchTraceCoverage,
    // Trace
    handleBuildTrace, handleEnableTrace, handleTogglePause,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleTraceAll, handleRetraceStale,
    handleAddExcludePattern, handleRemoveExcludePattern,
    // Enrichment
    handleRunAugmentation, handleRunEpistemic, handleRunModuleSynthesis,
    handleRunDeepening, handleRunKnowledgeBuild,
    handleRunFastSync, handleRunDeepEnrichment, handleRunAutoPilot,
    // Config
    handleEnrichmentAutoConfigChange, handleIndexAutoRebuildChange,
    // Destroy
    handleDestroyGraph, handleDestroyIndex,
  }
}
