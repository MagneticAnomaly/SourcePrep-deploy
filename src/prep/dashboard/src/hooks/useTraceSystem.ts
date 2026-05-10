import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useApiClient,
  type ProjectConfig,
  type EnrichmentAutoConfig,
  type PipelineStatus,
  type CrashedPipelineRun,
} from '@prep/ui'

// ── Inline types (not exported from @prep/ui as named types) ──

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
  // F-53: surface the daemon's `traced` array so the Graph Scope panel can
  // show what's currently in scope when there's no pending/stale work.
  traced: TraceCoverageFile[]
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
  onError: (msg: string, variant?: 'error' | 'warning' | 'info' | 'success') => void
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
  /** Reset atlas state (called during destroy) */
  resetAtlas?: () => void
  /** Force a fresh hydration of enrichment statuses from the server.
   *  Called after any mutation that the polling tick wouldn't pick up
   *  (resets, one-off stage regenerations, etc). */
  rehydrateEnrichment?: (projectId: string) => void
  /** Re-fetch pipeline provenance (stage model/age/version labels).
   *  Same refresh concern as rehydrateEnrichment — provenance is
   *  fetched on pipeline events only, so resets leave it stale. */
  fetchProvenance?: (signal?: AbortSignal) => Promise<void> | void
  /** Sync the deep-analysis schedule mode when the toggle flips. The
   *  schedule panel (Settings drawer) reads its mode from this slice —
   *  without the sync, reset-to-manual leaves the drawer showing the
   *  pre-reset mode (auto / scheduled). */
  syncDeepAnalysisScheduleMode?: (mode: 'manual' | 'auto' | 'scheduled') => void
  /** Pause a running pipeline group (Phase 81: used when Auto→Manual toggle) */
  pausePipeline?: (group: 'fast_sync' | 'deep_enrichment') => Promise<void>
  /** AbortSignal from hydration controller — aborted on project switch */
  signal?: AbortSignal
  /** True while hydration is in progress — suppress polls */
  isHydrating?: boolean
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
  const resetAtlasRef = useRef(deps.resetAtlas)
  resetAtlasRef.current = deps.resetAtlas
  const rehydrateEnrichmentRef = useRef(deps.rehydrateEnrichment)
  rehydrateEnrichmentRef.current = deps.rehydrateEnrichment
  const fetchProvenanceRef = useRef(deps.fetchProvenance)
  fetchProvenanceRef.current = deps.fetchProvenance
  const syncDeepAnalysisScheduleModeRef = useRef(deps.syncDeepAnalysisScheduleMode)
  syncDeepAnalysisScheduleModeRef.current = deps.syncDeepAnalysisScheduleMode
  // Populated below once handleEnrichmentAutoConfigChange exists.
  // Reset handlers call this to force every Manual/Auto switch back to
  // Manual after a wipe ('scheduled' is preserved — the user wants
  // those runs to keep firing on their cadence regardless of resets).
  const flipTogglesToManualRef = useRef<() => void>(() => { /* populated below */ })
  const pausePipelineRef = useRef(deps.pausePipeline)
  pausePipelineRef.current = deps.pausePipeline

  // ── State ───────────────────────────────────────────────────
  /** True while the initial hydration API calls are in-flight after a project switch.
   *  Used by the pipeline panel to show a loading state instead of the "Initialize" hero. */
  const [projectLoading, setProjectLoading] = useState(false)

  const [indexAutoRebuild, setIndexAutoRebuild] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('prep_index_auto_rebuild')
      return stored === 'true'
    } catch { return false }
  })
  const [enrichmentAutoConfig, setEnrichmentAutoConfig] = useState<EnrichmentAutoConfig>(
    // F-56: include the required `finalize` field. Pre-existing TS errors
    // here were because Phase 96E added the field to the interface but the
    // 4 setEnrichmentAutoConfig call sites in this hook never set it.
    { fastSync: true, deepEnrichment: 'manual', finalize: 'manual' }
  )

  // Phase 25: Crash Protection
  const [crashedRuns, setCrashedRuns] = useState<CrashedPipelineRun[]>([])

  // F-56 / F-65: Per-project enrichment auto config.
  //
  // Each project stores its own Manual/Auto/Sched state in
  // project.config.auto_config. The global pipeline_config is ONLY used
  // as a default for projects that have never been toggled (migration).
  //
  // F-65: The previous implementation fell through to the global config
  // on every project switch because deps.projectConfig is briefly
  // undefined during hydration. The async global fetch would resolve
  // and overwrite the per-project config that arrived moments later.
  // Fix: only fall back to global on the FIRST mount (no selectedProjectId
  // change), and skip the global fallback entirely when switching projects.
  const prevProjectIdRef = useRef<string | null>(null)
  useEffect(() => {
    // Honest defaults: when a key is unset (per-project auto_config is
    // null OR the per-project key is missing), the toggle MUST display
    // Manual — not Auto. The previous `?? true` defaults made the
    // toggle paint "Auto" for any project that had never been clicked,
    // while the watcher gate (PipelineOrchestrator._is_fast_sync_auto)
    // correctly returned False. Result: a green "Auto" pill on a
    // muzzled watcher with no UI signal that anything was wrong.
    const projAuto = (deps.projectConfig as any)?.auto_config
    if (projAuto && typeof projAuto === 'object') {
      setEnrichmentAutoConfig({
        fastSync: projAuto.fastSync ?? projAuto.fast_sync ?? false,
        deepEnrichment:
          projAuto.deepEnrichment ?? projAuto.deep_enrichment ?? 'manual',
        finalize: projAuto.finalize ?? 'manual',
      })
      prevProjectIdRef.current = selectedProjectId
      return
    }
    // No per-project auto_config yet. Only fall back to global on first
    // mount OR if this is the same project (config just hasn't loaded yet).
    // When SWITCHING projects, wait for the per-project config to arrive
    // instead of loading the global (which is the LAST project's state).
    if (selectedProjectId && selectedProjectId !== prevProjectIdRef.current) {
      // Project switched — reset to honest defaults while we wait for
      // the per-project config to arrive via deps.projectConfig.
      prevProjectIdRef.current = selectedProjectId
      setEnrichmentAutoConfig({ fastSync: false, deepEnrichment: 'manual', finalize: 'manual' })
      return
    }
    prevProjectIdRef.current = selectedProjectId
    // Same project or first mount — try global as migration fallback.
    // Note: the backend gates (PipelineOrchestrator._is_*_auto) no
    // longer consult the global; this fallback is purely a UI
    // convenience for projects whose per-project auto_config has not
    // been written yet. Defaulting to false matches the gates' default.
    let cancelled = false
    api.getSetting('pipeline_config').then((result: { key: string; value: any }) => {
      if (cancelled) return
      const pc = result?.value
      if (pc) {
        setEnrichmentAutoConfig({
          fastSync: pc.fast_sync?.auto ?? false,
          deepEnrichment: pc.deep_enrichment?.mode ?? 'manual',
          finalize: pc.finalize?.mode ?? 'manual',
        })
      }
    }).catch(() => { /* ignore */ })
    return () => { cancelled = true }
  }, [api, selectedProjectId, deps.projectConfig])
  const [traceStatus, setTraceStatus] = useState<TraceStatus>({
    enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 },
  })
  const [traceCoverage, setTraceCoverage] = useState<TraceCoverage>({
    summary: null, untraced: [], stale: [], traced: [], excluded: [], building: false, loading: false,
  })

  // ── Self-hydrate on project change (SM-1 Phase A4) ──────────
  // Fetches trace status, coverage, and pipeline status when project changes.
  // This replaces the external hydration that was in App.tsx's project-change effect.
  useEffect(() => {
    // Reset trace state immediately to prevent cross-project contamination
    setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } })
    setTraceCoverage({ summary: null, untraced: [], stale: [], traced: [], excluded: [], building: false, loading: false })
    setProjectLoading(true)

    if (!selectedProjectId) { setProjectLoading(false); return }
    const signal = deps.signal
    let unmounted = false

    // Hydrate trace status with retry — daemon may be busy with pipeline work.
    const hydrateTrace = async (pid: string) => {
      const delays = [2000, 4000] // retry after 2s, then 4s
      for (let attempt = 0; attempt <= delays.length; attempt++) {
        if (signal?.aborted || unmounted) return
        try {
          const data = await api.getTraceStatus(pid)
          if (signal?.aborted || unmounted) return
          const enabled = data.enabled ?? false
          setTraceStatus({
            enabled,
            exists: data.exists ?? false,
            building: data.building ?? false,
            counts: data.counts ?? { nodes: 0, edges: 0 },
            engine: data.engine,
          })
          setProjectLoading(false)
          // Fetch coverage if trace data exists on disk.
          // Phase 72: Fetch the lightweight summary first (from cache, <1s) to
          // populate the progress bars immediately.  Then fetch the full coverage
          // (which includes file lists for Queue/Patterns tabs) in the background.
          //
          // F-53: was previously gated on `enabled` only. Same root-cause class
          // as F-39 / F-49 — `enabled` is the auto-build preference, not the
          // data-presence flag. Now we fetch coverage when EITHER enabled or
          // exists is true so the Graph Scope panel populates for projects
          // that have a built graph but the auto-build flag was never flipped.
          const traceExists = data.exists ?? false
          if ((enabled || traceExists) && pid) {
            setTraceCoverage(prev => ({ ...prev, loading: true }))
            // Fast path — summary only (cached on server, returns instantly)
            api.getTraceCoverageSummary(pid).then((summ) => {
              if (signal?.aborted || unmounted) return
              setTraceCoverage(prev => ({
                ...prev,
                summary: summ.summary,
                building: summ.building,
                // Keep loading=true — full file lists still incoming
              }))
            }).catch(() => { /* summary not available — wait for full fetch */ })

            // Full coverage (may take 1-45s depending on codebase size)
            api.getTraceCoverage(pid).then((cov) => {
              if (signal?.aborted || unmounted) return
              setTraceCoverage({
                summary: cov.summary,
                untraced: cov.untraced,
                stale: cov.stale,
                traced: (cov as any).traced ?? [],
                excluded: cov.excluded ?? (cov as any).ignored ?? [],
                building: cov.building,
                loading: false,
              })
            }).catch(() => {
              if (!signal?.aborted && !unmounted) setTraceCoverage(prev => ({ ...prev, loading: false }))
            })
          }
          // Pipeline status — runs AFTER trace status so its `building`
          // flag takes precedence (Phase 24 + Phase 25 crash recovery).
          try {
            const ps = await api.getPipelineStatus(pid)
            if (signal?.aborted || unmounted) return
            const fastRunning = ps.fast_sync?.phase === 'running'
            if (fastRunning) {
              setTraceStatus(p => ({ ...p, building: true }))
            }
            setCrashedRuns(ps.crashed_runs ?? [])
          } catch { /* pipeline status is supplementary — don't retry */ }
          return // success
        } catch {
          if (attempt < delays.length && !signal?.aborted && !unmounted) {
            await new Promise(r => setTimeout(r, delays[attempt]))
          }
        }
      }
      // Phase 60D: All retry attempts failed (daemon under heavy load).
      // DON'T reset exists=false — that shows the misleading "Initialize
      // Trace Graph" hero.  Keep projectLoading=true so the user sees
      // a loading spinner instead.  The next polling cycle will retry.
      if (!signal?.aborted && !unmounted) {
        // Only reset if we've never successfully loaded trace data.
        // This prevents flashing "Initialize" when daemon is just slow.
        setTraceStatus(prev => {
          if (prev.exists) return prev  // Keep known-good state
          return { enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } }
        })
        setProjectLoading(false)
      }
    }

    void hydrateTrace(selectedProjectId)

    return () => { unmounted = true }
  }, [api, selectedProjectId])

  // ── Fetch functions ─────────────────────────────────────────

  const fetchTraceCoverage = useCallback(() => {
    // F-53: gate on data presence, not the auto-build preference.
    // Same root-cause class as F-39 / F-49.
    if (!selectedProjectId || (!traceStatus.enabled && !traceStatus.exists)) return
    setTraceCoverage(prev => ({ ...prev, loading: true }))
    api.getTraceCoverage(selectedProjectId).then((data) => {
      setTraceCoverage({
        summary: data.summary,
        untraced: data.untraced,
        stale: data.stale,
        traced: (data as any).traced ?? [],
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
    }).catch(() => { })
  }, [api, selectedProjectId])

  const handleEnableTrace = useCallback(() => {
    if (!selectedProjectId) return
    const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig.trace, enabled: true } }
    deps.setProjectConfig(newConfig)
    deps.setConfigDirty(true)
    // Send only the diff. Sending the full snapshot leaked stale `active`
    // across project switches and re-promoted deactivated projects.
    api.updateProject(selectedProjectId, { config: { trace: { ...deps.projectConfig.trace, enabled: true } } }).catch(() => { })
    setTraceStatus(prev => ({ ...prev, enabled: true }))
  }, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  // Accept either a single pattern or an array. Multiple patterns are sent
  // in a SINGLE /trace/ignore request to avoid read-modify-write races on
  // the backend — two concurrent single-pattern POSTs both read the same
  // config snapshot, append their pattern, and write; the second write wins
  // and the first pattern is lost on refresh.
  const handleAddExcludePattern = useCallback((pattern: string | string[]) => {
    if (!selectedProjectId) return
    const patterns = Array.isArray(pattern) ? pattern : [pattern]
    if (patterns.length === 0) return
    api.updateTraceIgnore(selectedProjectId, 'add', patterns).then(() => {
      fetchTraceCoverage()
    }).catch(() => { })
  }, [api, selectedProjectId, fetchTraceCoverage])

  const handleRemoveExcludePattern = useCallback((pattern: string | string[]) => {
    if (!selectedProjectId) return
    const patterns = Array.isArray(pattern) ? pattern : [pattern]
    if (patterns.length === 0) return
    api.updateTraceIgnore(selectedProjectId, 'remove', patterns).then(() => {
      fetchTraceCoverage()
    }).catch(() => { })
  }, [api, selectedProjectId, fetchTraceCoverage])

  // ── Pipeline handlers ──────────────────────────────────────

  const handleRunFastSync = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      // Auto-enable trace in project config when launching the pipeline.
      // F-39 fixed the daemon-side false-negative on `exists`, so this is no
      // longer needed for status correctness — but we still flip the flag so
      // the watcher and the auto-trigger paths (which DO gate on enabled by
      // design) pick up future file changes.
      if (!deps.projectConfig?.trace?.enabled) {
        const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig?.trace, enabled: true } }
        deps.setProjectConfig(newConfig)
        deps.setConfigDirty(true)
        // Diff-only update — see handleEnableTrace.
        api.updateProject(selectedProjectId, { config: { trace: { ...deps.projectConfig?.trace, enabled: true } } }).catch(() => { })
      }
      setTraceStatus(prev => ({ ...prev, enabled: true, building: true }))
      await api.runPipelineFast(selectedProjectId)
    } catch (e) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      onErrorRef.current(e instanceof Error ? e.message : 'Fast Sync encountered an issue. Check AI Gateway for model availability.', 'warning')
    }
  }, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  const handleRunAutoPilot = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setTraceStatus(prev => ({ ...prev, building: true }))
      await api.runPipelineAll(selectedProjectId)
    } catch (e) {
      setTraceStatus(prev => ({ ...prev, building: false }))
      onErrorRef.current(e instanceof Error ? e.message : 'Auto-pilot encountered an issue. Check AI Gateway for model availability.', 'warning')
    }
  }, [api, selectedProjectId])

  // handleTraceAll / handleRetraceStale — MUST be declared after
  // handleRunFastSync since they delegate to the pipeline orchestrator.
  const handleTraceAll = useCallback(() => {
    // Use the pipeline orchestrator (Fast Sync) instead of the legacy
    // buildTrace endpoint.  The legacy endpoint only runs Stage 1
    // (Rust parser) and never chains to stages 2-5 (edge discovery,
    // catalogue, validation, knowledge embedding).
    handleRunFastSync()
  }, [handleRunFastSync])

  const handleRetraceStale = useCallback(() => {
    // Same as handleTraceAll — pipeline orchestrator detects stale files
    // via check_coverage_gap() and runs them through all stages incrementally.
    handleRunFastSync()
  }, [handleRunFastSync])

  // ── Config persistence handlers ─────────────────────────────

  const handleEnrichmentAutoConfigChange = useCallback(async (config: EnrichmentAutoConfig) => {
    const prevFastSync = enrichmentAutoConfig.fastSync
    const prevDeep = enrichmentAutoConfig.deepEnrichment
    setEnrichmentAutoConfig(config)
    // F-56: persist to the SELECTED PROJECT'S config so each project has
    // its own Manual/Auto state. Was previously persisted only to the
    // global pipeline_config setting which all projects shared.
    if (selectedProjectId && deps.projectConfig) {
      const auto_config = {
        fastSync: config.fastSync,
        deepEnrichment: config.deepEnrichment,
        finalize: config.finalize,
      }
      const newProjectConfig = { ...deps.projectConfig, auto_config }
      deps.setProjectConfig(newProjectConfig)
      deps.setConfigDirty(true)
      // Diff-only update — see handleEnableTrace.
      api.updateProject(selectedProjectId, { config: { auto_config } }).catch(() => { /* silent */ })
    }
    // Also keep the global pipeline_config in sync as a default for new
    // projects (and so the auto-trigger paths in settings.py:308/332 still
    // see a sane default for any project that lacks its own auto_config).
    api.updatePipelineConfig({
      fast_sync_auto: config.fastSync,
      deep_enrichment_mode: config.deepEnrichment,
    }).catch(() => { /* silent */ })
    // Keep localStorage as a final fallback
    localStorage.setItem('prep_enrichment_auto_config', JSON.stringify(config))
    // Sync the legacy indexAutoRebuild flag so the watcher hydration
    // effect (which checks both flags) works correctly on page reload.
    if (config.fastSync !== indexAutoRebuild) {
      setIndexAutoRebuild(config.fastSync)
      localStorage.setItem('prep_index_auto_rebuild', String(config.fastSync))
    }

    if (!selectedProjectId) return

    // Phase 81: When switching to Manual, pause any running pipeline for that group.
    // This ensures the toggle is the single source of truth for "is this running."
    if (!config.fastSync && prevFastSync && traceStatus.building) {
      pausePipelineRef.current?.('fast_sync').catch(() => { /* silent — may not be running */ })
    }
    if (config.deepEnrichment === 'manual' && prevDeep !== 'manual') {
      pausePipelineRef.current?.('deep_enrichment').catch(() => { /* silent — may not be running */ })
    }

    // Phase 118 U5: Auto/Manual is a USER PREFERENCE controlling whether
    // the pipeline auto-triggers on file changes — it MUST NOT trigger a
    // fresh run by itself. The previous behavior called runPipelineFast /
    // runPipelineDeep here, which (a) lost the resume cursor when the
    // user toggled while paused mid-run, restarting from an earlier
    // stage; and (b) made the Auto toggle behave like a hidden Run
    // button with no opt-out. The user has explicit Run buttons for
    // each group; the toggle now only:
    //   - persists the preference
    //   - starts the file watcher (if switching TO auto)
    //   - pauses the running pipeline (if switching TO manual; handled above)
    // No API trigger. If the user wants a run, they click Run.
    if (config.fastSync && !prevFastSync) {
      // Side-effect kept: ensure the file watcher is running so future
      // file changes can auto-trigger the pipeline (the actual purpose
      // of Auto mode). Also ensure trace.enabled so the watcher has a
      // build target. NEITHER of these triggers a run.
      try {
        await startWatchRef.current?.()
        await refreshWatchStatusRef.current?.(selectedProjectId)
      } catch { /* watcher start may be feature-gated */ }
      if (!deps.projectConfig?.trace?.enabled) {
        const newCfg = { ...deps.projectConfig, trace: { ...deps.projectConfig?.trace, enabled: true } }
        deps.setProjectConfig(newCfg)
        deps.setConfigDirty(true)
        // Diff-only update — see handleEnableTrace.
        api.updateProject(selectedProjectId, { config: { trace: { ...deps.projectConfig?.trace, enabled: true } } }).catch(() => { })
      }
    }
    // Note: deepEnrichment toggle to 'auto' is now also a pure preference
    // change — no run trigger. The deep group will start automatically
    // when fast_sync next chains into it (auto mode), or when the user
    // clicks Run on Deep Enrichment.
  }, [api, selectedProjectId, enrichmentAutoConfig.fastSync, enrichmentAutoConfig.deepEnrichment, traceStatus.building, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])

  // Populate the reset-time toggle flipper now that
  // handleEnrichmentAutoConfigChange exists. Reads the live config so it
  // sees the user's current 'scheduled' choice (if any) rather than a
  // stale closure capture.
  flipTogglesToManualRef.current = () => {
    const currentDeep = enrichmentAutoConfig.deepEnrichment
    const nextDeep = currentDeep === 'scheduled' ? 'scheduled' : 'manual'
    handleEnrichmentAutoConfigChange({
      fastSync: false,
      deepEnrichment: nextDeep,
      finalize: 'manual',
    })
    // Keep the Settings drawer's schedule-mode slice in sync with the
    // toggle. Raw handleEnrichmentAutoConfigChange doesn't touch it.
    syncDeepAnalysisScheduleModeRef.current?.(nextDeep)
  }

  const handleIndexAutoRebuildChange = useCallback(async (auto: boolean) => {
    setIndexAutoRebuild(auto)
    localStorage.setItem('prep_index_auto_rebuild', String(auto))

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
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t resume pipeline.', 'warning')
    }
  }, [api, selectedProjectId])

  const handleDiscardCrashedRun = useCallback(async (runId: string) => {
    try {
      await api.discardCrashedRun(runId)
      setCrashedRuns(prev => prev.filter(r => r.run_id !== runId))
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t discard crashed run.', 'warning')
    }
  }, [api])

  // ── Destroy handlers ────────────────────────────────────────
  // Reset Graph removed — use handleDestroyIndex for a full clean wipe
  // (now also writes a reset barrier that blocks selfheal resurrection
  // until the next finalize completes).

  const handleDestroyIndex = useCallback(async (opts: { force?: boolean } = {}) => {
    if (!selectedProjectId) return
    try {
      await api.destroyIndex(selectedProjectId, opts)
      flipTogglesToManualRef.current()
      setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } })
      setTraceCoverage({ summary: null, untraced: [], stale: [], traced: [], excluded: [], building: false, loading: false })
      resetEnrichmentRef.current?.()
      resetAtlasRef.current?.()
      resetDeepAnalysisRef.current()
      onResetSearchRef.current()
      // Clear included paths and re-fetch the file tree so "Indexed" badges disappear
      clearIncludedPathsRef.current?.()
      void refreshStatusRef.current(selectedProjectId)
      rehydrateEnrichmentRef.current?.(selectedProjectId)
      void fetchProvenanceRef.current?.()
      // Re-fetch file tree after a short delay so backend caches are cleared
      setTimeout(() => {
        refreshFileTreeRef.current?.(selectedProjectId)
        api.getTraceCoverage(selectedProjectId).then((data) => {
          setTraceCoverage({ summary: data.summary, untraced: data.untraced, stale: data.stale, traced: (data as any).traced ?? [], excluded: data.excluded ?? [], building: false, loading: false })
        }).catch(() => { })
        rehydrateEnrichmentRef.current?.(selectedProjectId)
      void fetchProvenanceRef.current?.()
      }, 300)
    } catch (e) {
      const msg = e instanceof Error ? e.message : ''
      // The daemon returns 409 PIPELINE_RUNNING with a hint pointing at
      // the queue / force reset. Surface that hint instead of the generic
      // toast so the user knows what to do next without reading the API.
      const isRunningGate = /running/i.test(msg)
      const friendly = isRunningGate
        ? 'Cancel the running task from the Pipeline Queue (X button) before resetting.'
        : (msg || 'Couldn\u2019t reset project data.')
      onErrorRef.current(friendly, 'error')
    }
  }, [api, selectedProjectId])

  const handleRebuildPipeline = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.rebuildPipeline(selectedProjectId)
    } catch (err) {
      console.error('Failed to trigger pipeline rebuild:', err)
    }
  }, [api, selectedProjectId])

  // Scoped Danger-Zone resets — wipe stages 6-15 or 11-15 while
  // leaving fast_sync (stages 1-5) intact. Both write a reset barrier
  // server-side so selfheal cannot resurrect cleared stages until the
  // next finalize run completes.

  const handleDestroyEnrichmentFull = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyEnrichmentFull(selectedProjectId)
      flipTogglesToManualRef.current()
      resetEnrichmentRef.current?.()
      resetAtlasRef.current?.()
      resetDeepAnalysisRef.current()
      void refreshStatusRef.current(selectedProjectId)
      // Re-pull every enrichment + finalize status from disk. Without
      // this, stages 1-5 display the cleared state (the dispatch
      // DESTROYED in resetEnrichment nuked their slices) until the user
      // hard-refreshes or a polling tick fires — which it won't while
      // everything is idle.
      rehydrateEnrichmentRef.current?.(selectedProjectId)
      void fetchProvenanceRef.current?.()
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t reset enrichment data.', 'error')
    }
  }, [api, selectedProjectId])

  const handleDestroyFinalizeFull = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyFinalizeFull(selectedProjectId)
      flipTogglesToManualRef.current()
      resetAtlasRef.current?.()
      void refreshStatusRef.current(selectedProjectId)
      rehydrateEnrichmentRef.current?.(selectedProjectId)
      void fetchProvenanceRef.current?.()
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t reset finalize data.', 'error')
    }
  }, [api, selectedProjectId])

  // CodeIndex-only reset — wipes the four files written by CodeIndex
  // (documents.json, embeddings.npy, manifest.json, fts.sqlite3) and the
  // team-sync directories (local_deltas/, remote/). Trace, atlas, concepts,
  // observations, and project config (FolderTree / Knowledge Scope
  // selections) are untouched. No reset barrier — barriers gate trace.
  const handleDestroyCodeIndex = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.destroyCodeIndex(selectedProjectId)
      void refreshStatusRef.current(selectedProjectId)
    } catch (e) {
      onErrorRef.current(e instanceof Error ? e.message : 'Couldn\u2019t reset the code index.', 'error')
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
        }).catch(() => { })
        setTimeout(() => fetchTraceCoverage(), 500)
      }
    }
  }, [deps.findActiveTask, fetchTraceCoverage, api, selectedProjectId])

  // ── SSE: auto-refresh file tree when code index build completes ──

  const prevIndexBuildStatusRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    const indexTask = deps.findActiveTask('index_build')
    const prevStatus = prevIndexBuildStatusRef.current
    prevIndexBuildStatusRef.current = indexTask?.status

    if (indexTask && prevStatus === 'running' && indexTask.status === 'completed' && selectedProjectId) {
      // Code index build just finished — refresh the file tree so
      // status badges transition from Pending → Indexed.
      refreshFileTreeRef.current?.(selectedProjectId)
      // Retry after a short delay in case the index hasn't fully flushed
      setTimeout(() => refreshFileTreeRef.current?.(selectedProjectId), 2000)
    }
  }, [deps.findActiveTask, selectedProjectId])

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
    // Broad "active" — pipeline is doing something (including waiting for
    // compute slots between stages).  Keeps building=true during transient
    // states so the UI doesn't momentarily show idle stage evaluations.
    const ACTIVE_PHASES = new Set(['running', 'queued', 'pausing', 'recovering'])
    const fastActive = ACTIVE_PHASES.has(fast?.phase ?? '')
    const prevFastPhase = prev?.fast_sync?.phase

    // When fast sync transitions to a terminal state, don't clear building yet;
    // the completion handler below will clear it after fetching the real status.
    const fastJustCompleted = fast?.phase === 'completed' && (prevFastPhase === 'running' || prevFastPhase === 'queued' || prevFastPhase === 'pausing')
    if (!fastJustCompleted) {
      setTraceStatus(p => ({ ...p, building: fastActive }))
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
          }).catch(() => { })
        }
      }
      refresh()
      setTimeout(refresh, 1000)
      setTimeout(refresh, 3000)
    }

    // Fast sync completed → refresh trace status + coverage + file tree
    // Retry a few times to handle filesystem latency (files may not be
    // flushed to disk by the time the SSE event arrives).
    // State machine allows queued→completed transitions, so check broadly.
    const prevFastWasActive = prevFastPhase === 'running' || prevFastPhase === 'queued' || prevFastPhase === 'pausing'
    if (fast?.phase === 'completed' && prevFastWasActive) {
      const refreshTraceOnComplete = () => {
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
      refreshTraceOnComplete()
      setTimeout(refreshTraceOnComplete, 1000)
      setTimeout(refreshTraceOnComplete, 3000)
      // Refresh file tree so status badges (Pending→Indexed) update
      setTimeout(() => refreshFileTreeRef.current?.(selectedProjectId), 2000)
    }

    if (fast?.phase === 'failed' && prevFastWasActive) {
      setTraceStatus(p => ({ ...p, building: false }))
    }

    // Deep enrichment completed → refresh trace coverage + file tree
    // (deep enrichment triggers a CodeIndex build, so file statuses change)
    const prevDeepPhase = prev?.deep_enrichment?.phase
    const deep = pipelineEvent.deep_enrichment
    if (deep?.phase === 'completed' && prevDeepPhase === 'running') {
      void fetchTraceCoverage()
      // CodeIndex build fires after deep enrichment; give it time to finish
      setTimeout(() => refreshFileTreeRef.current?.(selectedProjectId), 5000)
      setTimeout(() => refreshFileTreeRef.current?.(selectedProjectId), 15000)
    }

    // Phase 118 U1: finalize completed → re-fetch trace status. Without
    // this the dashboard never refreshes `trace.exists` after a full
    // pipeline finishes (the existing fast_sync handler only fires when
    // fast_sync is the LAST group to settle, which happens for pure-fast
    // runs but not for full Initial / Rebuild). The polling loop also
    // exits as soon as `building=false` so it can't pick up the late
    // file-presence change either. Without a refresh here the panel
    // reads a stale `exists=false` snapshot from a mid-rebuild moment
    // and reverts to the "Initialize Trace Graph" hero.
    const prevFinalizePhase = prev?.finalize?.phase
    const finalize = pipelineEvent.finalize
    if (finalize?.phase === 'completed' && (prevFinalizePhase === 'running' || prevFinalizePhase === 'queued' || prevFinalizePhase === 'pausing')) {
      const refreshTraceOnFinalize = () => {
        api.getTraceStatus(selectedProjectId).then((data) => {
          setTraceStatus({
            enabled: data.enabled ?? false,
            exists: data.exists ?? false,
            building: false,
            counts: data.counts ?? { nodes: 0, edges: 0 },
            engine: data.engine,
          })
        }).catch(() => { /* keep prior state on transient fetch failure */ })
      }
      refreshTraceOnFinalize()
      setTimeout(refreshTraceOnFinalize, 1000)
      setTimeout(refreshTraceOnFinalize, 3000)
    }
  }, [pipelineEvent, selectedProjectId, api, fetchTraceCoverage])

  // ── Ensure watcher is running when Auto is on (hydration) ────
  // The watcher runs in-memory on the backend.  If the daemon restarts,
  // the watcher is lost but the frontend still knows "auto=true".  This
  // effect checks the backend watcher status on project change and
  // re-starts it if needed.  A short delay avoids racing with the
  // license sync (dev-tier override must reach the backend before the
  // require_feature("auto_rebuild") gate passes).
  //
  // Two separate toggles can enable auto mode:
  //   1. indexAutoRebuild (legacy localStorage toggle from IndexStatusCard)
  //   2. enrichmentAutoConfig.fastSync (pipeline config toggle)
  // Either one being true should ensure the watcher is running.
  const shouldAutoWatch = indexAutoRebuild || enrichmentAutoConfig.fastSync
  useEffect(() => {
    if (!selectedProjectId || !shouldAutoWatch) return
    let cancelled = false

    const timer = setTimeout(() => {
      if (cancelled) return
      // Check current watcher status first
      api.getWatchStatus(selectedProjectId).then((ws) => {
        if (cancelled) return
        // Only start if not already running
        if (!ws.enabled || ws.state === 'disabled') {
          startWatchRef.current?.().then(() => {
            refreshWatchStatusRef.current?.(selectedProjectId)
          }).catch(() => {
            // Feature-gated or other error — silently fall through
          })
        }
      }).catch(() => {
        // Status fetch failed — try starting anyway
        if (cancelled) return
        startWatchRef.current?.().catch(() => { })
      })
    }, 2000) // 2s delay for license sync to complete

    return () => { cancelled = true; clearTimeout(timer) }
  }, [api, selectedProjectId, shouldAutoWatch])

  // ── Polling: trace coverage during build ─────────────────────
  // F-11: bumped 3s -> 8s with document.hidden pause + in-flight guard.
  // /trace/coverage does a filesystem scan; previously this could
  // pile up requests when multiple stages were running concurrently.
  useEffect(() => {
    if (!selectedProjectId || !traceStatus.building || deps.isHydrating) return
    let inFlight = false
    const tick = async () => {
      if (document.hidden || inFlight) return
      inFlight = true
      try {
        await fetchTraceCoverage()
      } finally {
        inFlight = false
      }
    }
    const interval = setInterval(tick, 8000)
    return () => clearInterval(interval)
  }, [selectedProjectId, traceStatus.building, fetchTraceCoverage, deps.isHydrating])

  // ── Return ──────────────────────────────────────────────────

  return {
    // State (read-only — hook owns hydration, no external setters)
    projectLoading,
    traceStatus,
    traceCoverage,
    indexAutoRebuild,
    enrichmentAutoConfig,
    // Phase 25: Crash Protection
    crashedRuns,
    handleResumeCrashedRun,
    handleDiscardCrashedRun,
    // Fetch
    fetchTraceCoverage,
    // Trace
    handleBuildTrace, handleEnableTrace,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleTraceAll, handleRetraceStale,
    handleAddExcludePattern, handleRemoveExcludePattern,
    // Pipeline
    handleRunFastSync, handleRunAutoPilot,
    // Config
    handleEnrichmentAutoConfigChange, handleIndexAutoRebuildChange,
    // Destroy
    handleDestroyIndex, handleRebuildPipeline,
    handleDestroyEnrichmentFull, handleDestroyFinalizeFull,
    handleDestroyCodeIndex,
  }
}
