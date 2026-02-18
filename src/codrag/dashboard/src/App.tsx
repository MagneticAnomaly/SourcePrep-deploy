import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { FileText, Settings, AlertCircle } from 'lucide-react'
import {
  // API
  useApiClient,
  type ProjectListItem,
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  // Dashboard
  ModularDashboard,
  // Project
  AddProjectModal,
  // Patterns
  LoadingState,
  EmptyState,
  // Primitives
  Button,
  // Types
  type ProjectConfig,
  type ProjectSummary,
  type ProjectStatus,
  type StatusState,
  type ProjectMode,
  type DashboardLayoutApi,
  type DashboardLayout,
  // Layout
  PanelPicker,
  useEventStream,
} from '@codrag/ui'
import { StartupScreen } from './components/StartupScreen'
import { SettingsDrawer } from './components/settings/SettingsDrawer'
import { ErrorToast } from './components/ErrorToast'
import { useLicenseSystem } from './hooks/useLicenseSystem'
import { useLLMConfig } from './hooks/useLLMConfig'
import { useDeepAnalysis } from './hooks/useDeepAnalysis'
import { useWatchSystem } from './hooks/useWatchSystem'
import { useTraceSystem, type TraceCoverage } from './hooks/useTraceSystem'
import { useEnrichment } from './hooks/useEnrichment'
import { useSearchContext } from './hooks/useSearchContext'
import { useFileSystem } from './hooks/useFileSystem'
import { useDashboardPanels } from './hooks/useDashboardPanels'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

// ── Helpers ──────────────────────────────────────────────────


function deriveStatus(ps: ProjectStatus | null, building: boolean): StatusState {
  if (building) return 'building'
  if (!ps) return 'pending'
  if (ps.building) return 'building'
  if (ps.stale) return 'stale'
  if (ps.index.exists) return 'fresh'
  return 'pending'
}

function toProjectSummary(p: ProjectListItem, ps: ProjectStatus | null, building: boolean): ProjectSummary {
  return {
    id: p.id,
    name: p.name,
    path: p.path,
    mode: p.mode ?? 'standalone',
    status: deriveStatus(ps, building),
    chunk_count: ps?.index.total_chunks,
    last_build_at: ps?.index.last_build_at ?? undefined,
  }
}

// ── App ──────────────────────────────────────────────────────

function App() {
  const api = useApiClient()

  // ── Connection state ───────────────────────────────────────
  const [isConnected, setIsConnected] = useState(false)
  const [isDaemonUnhealthy, setIsDaemonUnhealthy] = useState(false)

  // Initial connection & health polling
  useEffect(() => {
    let interval: NodeJS.Timeout

    const checkHealth = async () => {
      try {
        await api.getHealth()
        if (!isConnected) setIsConnected(true)
        setIsDaemonUnhealthy(false)
      } catch {
        if (isConnected) setIsDaemonUnhealthy(true)
      }
    }

    // Start polling once connected (StartupScreen handles the initial wait)
    if (isConnected) {
      interval = setInterval(checkHealth, 2000)
      checkHealth()
    }

    return () => clearInterval(interval)
  }, [api, isConnected])

  // ── Global state ───────────────────────────────────────────
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── Project list ───────────────────────────────────────────
  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [projectStatuses, setProjectStatuses] = useState<Record<string, ProjectStatus>>({})
  const [buildingProjects, setBuildingProjects] = useState<Set<string>>(new Set())
  const [transientCompleteProjects, setTransientCompleteProjects] = useState<Set<string>>(new Set())
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // ── UI preferences ─────────────────────────────────────────
  const [uiMode, setUiMode] = useState<'light' | 'dark'>(() =>
    (localStorage.getItem('codrag_ui_mode') as 'light' | 'dark') ?? 'light'
  )
  const [uiTheme, setUiTheme] = useState<string>(() =>
    localStorage.getItem('codrag_ui_theme') ?? 'none'
  )
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [bgImage, setBgImage] = useState<string | null>(() =>
    localStorage.getItem('codrag_bg_image') ?? null
  )
  const [dashboardLayout, setDashboardLayout] = useState<DashboardLayout | null>(null)

  // ── License (hook) ─────────────────────────────────────────
  const {
    licenseStatus, licenseKeyInput, setLicenseKeyInput,
    licenseLoading, licenseError, devTierOverride,
    fetchLicense, handleActivateLicense, handleDeactivateLicense,
    handleDevTierOverrideChange,
  } = useLicenseSystem()

  // Derive isPro from dev tier override or actual license
  const effectiveTier = devTierOverride ?? licenseStatus?.license?.tier ?? 'free'
  const isPro = effectiveTier !== 'free'

  // ── Search + Context (hook) ─────────────────────────────────
  const {
    query, setQuery, searchK, setSearchK, minScore, setMinScore,
    searchLoading, searchResults, selectedChunk, setSelectedChunk,
    contextK, setContextK, contextMaxChars, setContextMaxChars,
    contextIncludeSources, setContextIncludeSources,
    contextIncludeScores, setContextIncludeScores,
    contextStructured, setContextStructured,
    context, contextMeta,
    handleSearch, handleGetContext, handleCopyContext,
    resetSearch,
  } = useSearchContext(selectedProjectId, { onError: (msg) => setError(msg) })

  const layoutApiRef = useRef<DashboardLayoutApi | null>(null)

  // ── File system (hook) ───────────────────────────────────
  const {
    fileTree, pathWeights, includedPaths, pinnedPaths, pinnedFiles,
    fetchFileTree, handleLoadChildren, handlePathWeightChange,
    handleToggleInclude, clearIncludedPaths,
    handlePinFile, handleUnpinFile, handleLoadFileContent,
  } = useFileSystem(selectedProjectId, { layoutApiRef })

  // ── Watch (hook) ─────────────────────────────────────────────
  const {
    watchStatus, watchLoading,
    refreshWatchStatus, handleStartWatch, handleStopWatch,
  } = useWatchSystem(selectedProjectId, { onError: (msg) => setError(msg) })

  // ── Settings state ─────────────────────────────────────────
  const [projectConfig, setProjectConfig] = useState<ProjectConfig>({
    include_globs: ['**/*.md', '**/*.py', '**/*.ts', '**/*.tsx', '**/*.js', '**/*.json'],
    exclude_globs: ['**/.git/**', '**/node_modules/**', '**/__pycache__/**', '**/.venv/**', '**/dist/**', '**/build/**', '**/.next/**'],
    max_file_bytes: 400_000,
    use_gitignore: true,
    trace: { enabled: false },
    auto_rebuild: { enabled: false, debounce_ms: 5000 },
  })
  const [configDirty, setConfigDirty] = useState(false)
  // ── Deep analysis (hook) ─────────────────────────────────────
  const {
    deepAnalysisSchedule, setDeepAnalysisSchedule,
    deepAnalysisStatus, setDeepAnalysisStatus,
    deepAnalysisRunning,
    fetchDeepAnalysisStatus, handleRunDeepAnalysis, handleCancelDeepAnalysis,
  } = useDeepAnalysis(selectedProjectId, { onError: (msg) => setError(msg) })

  // ── Event Stream ───────────────────────────────────────────
  // In dev mode, bypass Vite proxy (which buffers SSE) and connect directly to daemon
  const eventsUrl = import.meta.env.DEV
    ? `http://${window.location.hostname}:8400/events`
    : `${api.baseUrl}/events`;
  const { logs, tasks, clearLogs, pipelineEvents, scopeEvents } = useEventStream(eventsUrl, 1000);

  // Helper to find relevant task for current project
  const findActiveTask = useCallback((type: 'index_build' | 'trace_build') => {
    if (!selectedProjectId) return undefined;
    const entry = Object.values(tasks).find(t => 
      t.task_id.startsWith(`${type}:${selectedProjectId}`) && 
      (t.status === 'running' || t.status === 'completed')
    );
    return entry;
  }, [tasks, selectedProjectId]);

  // ── Data fetching ──────────────────────────────────────────

  const refreshProjects = useCallback(async () => {
    try {
      const data = await api.listProjects()
      setProjects(data.projects)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to list projects')
    }
  }, [api])

  const refreshStatus = useCallback(async (projectId: string) => {
    try {
      const status = await api.getProjectStatus(projectId)
      setProjectStatuses((prev) => ({ ...prev, [projectId]: status }))
      if (!status.building) {
        setBuildingProjects((prev) => {
          const next = new Set(prev)
          next.delete(projectId)
          return next
        })
      }
    } catch {
      // Silently ignore status errors for background polling
    }
  }, [api])

  // ── Enrichment (hook) ───────────────────────────────────────
  const {
    augmentationStatus, augmenting, validating,
    epistemicStatus, epistemicRunning,
    moduleStatus, clusterRunning,
    deepeningStatus, deepeningRunning,
    knowledgeStatus, knowledgeBuilding,
    handleRunAugmentation, handleRunEpistemic, handleRunModuleSynthesis,
    handleRunDeepening, handleRunKnowledgeBuild,
    handleRunDeepEnrichment,
    resetAll: resetEnrichment,
  } = useEnrichment(selectedProjectId, {
    onError: (msg) => setError(msg),
    pipelineEvents,
  })

  // ── Trace system (hook) ───────────────────────────────────────
  const {
    traceStatus, setTraceStatus,
    traceCoverage, setTraceCoverage,
    indexAutoRebuild, enrichmentAutoConfig,
    fetchTraceCoverage,
    handleBuildTrace, handleEnableTrace, handleTogglePause,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleTraceAll, handleRetraceStale,
    handleAddExcludePattern, handleRemoveExcludePattern,
    handleRunFastSync,
    handleEnrichmentAutoConfigChange, handleIndexAutoRebuildChange,
    handleDestroyGraph, handleDestroyIndex,
  } = useTraceSystem(selectedProjectId, {
    projectConfig,
    setProjectConfig,
    setConfigDirty,
    resetDeepAnalysisStatus: () => setDeepAnalysisStatus({} as any),
    refreshStatus,
    onResetSearch: resetSearch,
    onError: (msg) => setError(msg),
    findActiveTask,
    pipelineEvents,
    startWatch: handleStartWatch,
    stopWatch: handleStopWatch,
    refreshWatchStatus,
    refreshFileTree: fetchFileTree,
    clearIncludedPaths,
    resetEnrichment,
  })

  // ── LLM config (hook) ───────────────────────────────────────
  const {
    llmConfig, setLLMConfig,
    availableModels, loadingModels, testingSlot, testResults,
    llmSlotsStatus,
    handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint, handleFetchModels, handleTestModel,
    handleDownloadModel,
    fetchLLMSlotsStatus,
  } = useLLMConfig({ onDirty: () => setConfigDirty(true) })

  // ── Derived ────────────────────────────────────────────────
  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )
  const projectStatus = selectedProjectId ? projectStatuses[selectedProjectId] ?? null : null

  const projectSummaries = useMemo(
    () => projects.map((p) => toProjectSummary(p, projectStatuses[p.id] ?? null, buildingProjects.has(p.id))),
    [projects, projectStatuses, buildingProjects],
  )

  // ── Actions ────────────────────────────────────────────────

  const handleAddProject = useCallback(async (path: string, name: string, mode: ProjectMode, indexPath?: string) => {
    try {
      const data = await api.createProject({ path, name, mode, ...(indexPath ? { index_path: indexPath } : {}) })
      setProjects((prev) => [...prev, data.project])
      setSelectedProjectId(data.project.id)
      setAddModalOpen(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add project'
      setError(msg)
      throw e // Re-throw so modal can handle state
    }
  }, [api])

  const handleDeleteProject = useCallback(async (projectId: string) => {
    try {
      await api.deleteProject(projectId)
      setProjects((prev) => prev.filter((p) => p.id !== projectId))
      if (selectedProjectId === projectId) setSelectedProjectId(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete project')
    }
  }, [api, selectedProjectId])

  // Ref to track auto-rebuild state for use in handleBuild callback
  const indexAutoRebuildRef = useRef(indexAutoRebuild)
  indexAutoRebuildRef.current = indexAutoRebuild

  // Ref to track includedPaths for use in handleBuild callback
  const includedPathsRef = useRef(includedPaths)
  includedPathsRef.current = includedPaths

  const handleBuild = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      setBuildingProjects((prev) => new Set(prev).add(selectedProjectId))
      // Pass file tree selections to backend so only selected files are indexed
      const paths = [...includedPathsRef.current]
      await api.buildProject(selectedProjectId, false, paths.length > 0 ? paths : undefined)
      // Poll status until build completes
      const poll = setInterval(async () => {
        try {
          const status = await api.getProjectStatus(selectedProjectId)
          setProjectStatuses((prev) => ({ ...prev, [selectedProjectId]: status }))
          if (!status.building) {
            clearInterval(poll)
            setBuildingProjects((prev) => {
              const next = new Set(prev)
              next.delete(selectedProjectId)
              return next
            })
            
            // Set transient complete state for 5 seconds
            setTransientCompleteProjects((prev) => new Set(prev).add(selectedProjectId))
            setTimeout(() => {
              setTransientCompleteProjects((prev) => {
                const next = new Set(prev)
                next.delete(selectedProjectId)
                return next
              })
            }, 5000)

            // Refresh status after build
            void refreshStatus(selectedProjectId)
            // Refresh file tree to update indexed/pending statuses in UI
            void fetchFileTree(selectedProjectId)
            
            // If Auto mode is on, start the watcher after initial build
            if (indexAutoRebuildRef.current) {
              handleStartWatch().then(() => refreshWatchStatus(selectedProjectId)).catch(() => {})
            }
          }
        } catch (e) {
          // Ignore transient errors, keep polling
          console.warn('Poll failed', e)
        }
      }, 2000)
    } catch (e) {
      setBuildingProjects((prev) => {
        const next = new Set(prev)
        next.delete(selectedProjectId)
        return next
      })
      setError(e instanceof Error ? e.message : 'Build failed')
    }
  }, [api, selectedProjectId, handleStartWatch, refreshWatchStatus])

  const handleSaveConfig = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.updateProject(selectedProjectId, {
        config: {
          include_globs: projectConfig.include_globs,
          exclude_globs: projectConfig.exclude_globs,
          max_file_bytes: projectConfig.max_file_bytes,
          trace: projectConfig.trace,
          auto_rebuild: projectConfig.auto_rebuild,
        },
      })
      setConfigDirty(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save config')
    }
  }, [api, projectConfig, selectedProjectId])

  const handleProjectConfigChange = useCallback((cfg: ProjectConfig) => {
    setProjectConfig(cfg)
    setConfigDirty(true)
  }, [])

  const handleDetectStack = useCallback(async () => {
    if (!selectedProjectId) throw new Error("No project selected")
    return await api.detectStack(selectedProjectId)
  }, [api, selectedProjectId])

  // ── Theme effect ───────────────────────────────────────────
  useEffect(() => {
    const root = document.documentElement
    if (uiMode === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
    root.setAttribute('data-codrag-theme', uiTheme === 'none' ? 'a' : uiTheme)
    localStorage.setItem('codrag_ui_mode', uiMode)
    localStorage.setItem('codrag_ui_theme', uiTheme)
    if (bgImage) localStorage.setItem('codrag_bg_image', bgImage)
    else localStorage.removeItem('codrag_bg_image')
  }, [uiMode, uiTheme, bgImage])

  // ── Persist UI preferences to backend ─────────────────────
  const uiPrefsSkipRef = useRef(0)
  useEffect(() => {
    if (uiPrefsSkipRef.current < 2) { uiPrefsSkipRef.current++; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({
        ui_preferences: { mode: uiMode, theme: uiTheme, bg_image: bgImage },
      }).catch(() => {})
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, uiMode, uiTheme, bgImage])

  // ── Init: load projects + global config ─────────────────────
  useEffect(() => {
    const init = async () => {
      try {
        await refreshProjects()
        // Load global config (LLM endpoints, models, etc.)
        try {
          const globalCfg = await api.getGlobalConfig()
          if (globalCfg.llm_config) {
            setLLMConfig(globalCfg.llm_config)
          }
          if (globalCfg.deep_analysis) {
            setDeepAnalysisSchedule((prev) => ({ ...prev, ...globalCfg.deep_analysis }))
          }
          if (globalCfg.ui_preferences) {
            const prefs = globalCfg.ui_preferences
            if (prefs.mode) setUiMode(prefs.mode)
            if (prefs.theme) setUiTheme(prefs.theme)
            if (prefs.bg_image !== undefined) setBgImage(prefs.bg_image)
          }
          if (globalCfg.module_layout && globalCfg.module_layout.version) {
            // Persist to localStorage so useLayoutPersistence picks it up
            try {
              localStorage.setItem('codrag_dashboard_layout', JSON.stringify(globalCfg.module_layout))
            } catch { /* storage full */ }
          }
        } catch {
          // Global config not available — use defaults
        }
        // Check LLM connectivity
        void fetchLLMSlotsStatus()
        // Fetch license status
        void fetchLicense()
      } catch {
        // Error already set
      } finally {
        setLoading(false)
      }
    }
    void init()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProjects])

  // ── Auto-save dashboard layout to backend ───────────────────
  const layoutSkipRef = useRef(0)
  useEffect(() => {
    if (!dashboardLayout) return
    if (layoutSkipRef.current < 2) { layoutSkipRef.current++; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ module_layout: dashboardLayout }).catch(() => {})
    }, 1000)
    return () => clearTimeout(timeout)
  }, [api, dashboardLayout])

  // ── Refresh status + watch when project changes ─────────────
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshStatus(selectedProjectId)
    void refreshWatchStatus(selectedProjectId)
    void fetchDeepAnalysisStatus()
    // Fetch trace status, then coverage if trace is enabled
    api.getTraceStatus(selectedProjectId).then((data) => {
      const enabled = data.enabled ?? false
      setTraceStatus({
        enabled,
        exists: data.exists ?? false,
        building: data.building ?? false,
        counts: data.counts ?? { nodes: 0, edges: 0 },
        engine: data.engine,
      })
      // Fetch coverage directly — can't rely on fetchTraceCoverage() here
      // because setTraceStatus hasn't applied yet (stale closure)
      if (enabled && selectedProjectId) {
        setTraceCoverage((prev: TraceCoverage) => ({ ...prev, loading: true }))
        api.getTraceCoverage(selectedProjectId).then((cov) => {
          setTraceCoverage({
            summary: cov.summary,
            untraced: cov.untraced,
            stale: cov.stale,
            excluded: cov.excluded ?? (cov as any).ignored ?? [],
            building: cov.building,
            loading: false,
          })
        }).catch(() => {
          setTraceCoverage((prev: TraceCoverage) => ({ ...prev, loading: false }))
        })
      }
    }).catch(() => { setTraceStatus({ enabled: false, exists: false, building: false, counts: { nodes: 0, edges: 0 } }) })
    // Load project config
    api.getProject(selectedProjectId).then((data) => {
      const cfg = data.project.config
      if (cfg) {
        setProjectConfig({
          include_globs: cfg.include_globs ?? projectConfig.include_globs,
          exclude_globs: cfg.exclude_globs ?? projectConfig.exclude_globs,
          max_file_bytes: cfg.max_file_bytes ?? projectConfig.max_file_bytes,
          use_gitignore: cfg.use_gitignore ?? projectConfig.use_gitignore,
          trace: cfg.trace ?? projectConfig.trace,
          auto_rebuild: cfg.auto_rebuild ?? projectConfig.auto_rebuild,
        })
        setConfigDirty(false)
      }
    }).catch(() => {})
    // Auto-select first project if none selected
  }, [selectedProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-select first project
  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id)
    }
  }, [projects, selectedProjectId])

  // ── Dashboard panels (hook) ─────────────────────────────────
  const { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX: pinnedPrefix } = useDashboardPanels({
    projectStatus, selectedProject, selectedProjectId, projectConfig, isPro,
    scopeStatus: selectedProjectId ? scopeEvents[selectedProjectId] : undefined,
    logs, clearLogs, findActiveTask,
    handleBuild,
    transientComplete: selectedProjectId ? transientCompleteProjects.has(selectedProjectId) : false,
    query, setQuery, searchK, setSearchK, minScore, setMinScore,
    searchLoading, searchResults, selectedChunk, setSelectedChunk, handleSearch,
    contextK, setContextK, contextMaxChars, setContextMaxChars,
    contextIncludeSources, setContextIncludeSources,
    contextIncludeScores, setContextIncludeScores,
    contextStructured, setContextStructured,
    context, contextMeta, handleGetContext, handleCopyContext,
    watchStatus, watchLoading, handleStartWatch, handleStopWatch,
    fileTree, includedPaths, handleToggleInclude,
    pathWeights, handlePathWeightChange, handleLoadChildren,
    pinnedPaths, pinnedFiles, handlePinFile, handleUnpinFile, handleLoadFileContent,
    traceStatus, traceCoverage, indexAutoRebuild, handleIndexAutoRebuildChange,
    enrichmentAutoConfig, handleEnrichmentAutoConfigChange,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleBuildTrace, handleEnableTrace, handleTogglePause,
    handleTraceAll, handleRetraceStale, handleAddExcludePattern, handleRemoveExcludePattern, fetchTraceCoverage,
    augmentationStatus, augmenting, validating, handleRunAugmentation,
    epistemicStatus, epistemicRunning, handleRunEpistemic,
    moduleStatus, clusterRunning, handleRunModuleSynthesis,
    deepeningStatus, deepeningRunning, handleRunDeepening,
    knowledgeStatus, knowledgeBuilding, handleRunKnowledgeBuild,
    handleRunFastSync, handleRunDeepEnrichment, handleDestroyGraph,
    deepAnalysisSchedule, setDeepAnalysisSchedule,
    deepAnalysisStatus, deepAnalysisRunning, handleRunDeepAnalysis, handleCancelDeepAnalysis,
    llmConfig, llmSlotsStatus,
    handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint,
    handleFetchModels,
    handleTestModel,
    handleDownloadModel,
    availableModels,
    loadingModels,
    testingSlot,
    testResults,
  })

  // ── Loading state ──────────────────────────────────────────
  if (!isConnected) {
    return (
      <StartupScreen
        apiBaseUrl={api.baseUrl}
        onReady={() => setIsConnected(true)}
      />
    )
  }

  if (loading) {
    return <LoadingState message="Connecting to CoDRAG daemon..." />
  }

  // ── Render ─────────────────────────────────────────────────
  return (
    <>
      <ErrorToast message={error} onClose={() => setError(null)} />
      {isDaemonUnhealthy && (
        <div className="fixed inset-x-0 top-0 z-[100] bg-error text-white px-4 py-2 text-sm font-bold flex items-center justify-center gap-2 shadow-lg">
        <AlertCircle className="w-4 h-4" />
        Connection to CoDRAG daemon lost. Attempting to reconnect...
      </div>
      )}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        projectConfig={projectConfig}
        onProjectConfigChange={handleProjectConfigChange}
        onSaveConfig={() => void handleSaveConfig()}
        configDirty={configDirty}
        hasProject={!!selectedProjectId}
        onDetectStack={selectedProjectId ? handleDetectStack : undefined}
        deepAnalysisSchedule={deepAnalysisSchedule}
        onDeepAnalysisScheduleChange={setDeepAnalysisSchedule}
        largeModelConfigured={!!(llmConfig.large_model?.endpoint_id && llmConfig.large_model?.model)}
        fastModelConfigured={!!(llmConfig.small_model?.endpoint_id && llmConfig.small_model?.model)}
        uiMode={uiMode}
        onModeChange={setUiMode}
        uiTheme={uiTheme}
        onThemeChange={setUiTheme}
        bgImage={bgImage}
        onBgImageChange={setBgImage}
        licenseStatus={licenseStatus}
        licenseKeyInput={licenseKeyInput}
        onLicenseKeyInputChange={setLicenseKeyInput}
        onActivateLicense={handleActivateLicense}
        onDeactivateLicense={handleDeactivateLicense}
        licenseLoading={licenseLoading}
        licenseError={licenseError}
        onDestroyGraph={handleDestroyGraph}
        onDestroyIndex={handleDestroyIndex}
        devTierOverride={devTierOverride}
        onDevTierOverrideChange={handleDevTierOverrideChange}
      />
      {/* Floating Settings trigger — always visible */}
      {!settingsOpen && (
        <Button
          variant="outline"
          size="icon"
          onClick={() => setSettingsOpen(true)}
          title="Settings"
          className="fixed bottom-4 right-4 z-40 shadow-lg bg-surface hover:bg-surface-raised"
        >
          <Settings className="w-5 h-5" />
        </Button>
      )}
      {/* Background image overlay */}
      {bgImage && (
        <div
          className="fixed inset-0 z-[-1] bg-cover bg-center opacity-10 pointer-events-none"
          style={{ backgroundImage: `url(${bgImage})` }}
        />
      )}
      <AppShell
        sidebar={
          <Sidebar
            collapsed={sidebarCollapsed}
            onCollapseToggle={() => setSidebarCollapsed((c) => !c)}
          >
            {!sidebarCollapsed && (
              <ProjectList
                projects={projectSummaries}
                selectedProjectId={selectedProjectId ?? undefined}
                onProjectSelect={setSelectedProjectId}
                onAddProject={() => setAddModalOpen(true)}
                onDeleteProject={handleDeleteProject}
                extraActions={
                  dashboardLayout && layoutApiRef.current ? (
                    <PanelPicker
                      layout={dashboardLayout}
                      panelDefinitions={allPanelDefs}
                      onTogglePanel={layoutApiRef.current.togglePanelVisibility}
                      onResetLayout={layoutApiRef.current.resetLayout}
                      onRefitLayout={layoutApiRef.current.reflowLayout}
                      onCopyLayout={layoutApiRef.current.copyLayout}
                      onPasteLayout={layoutApiRef.current.pasteLayout}
                    />
                  ) : undefined
                }
              />
            )}
          </Sidebar>
        }
      >
        {selectedProject ? (
          <div className="w-full space-y-6">
            <ModularDashboard
              panelDefinitions={allPanelDefs}
              panelContent={panelContent}
              panelDetails={panelDetails}
              onPanelClose={(panelId) => {
                if (panelId.startsWith(pinnedPrefix)) {
                  handleUnpinFile(panelId)
                }
              }}
              onLayoutReady={(api) => { layoutApiRef.current = api }}
              onLayoutChange={setDashboardLayout}
              hidePanelPicker
            />
          </div>
        ) : (
          <EmptyState
            icon={<FileText />}
            title="No Project Selected"
            description="Select a project from the sidebar or create a new one to get started."
            action={{ label: 'Add Project', onClick: () => setAddModalOpen(true) }}
          />
        )}
      </AppShell>

      <AddProjectModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdd={handleAddProject}
      />
    </>
  )
}

export default App
