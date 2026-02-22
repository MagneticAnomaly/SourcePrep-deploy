import { useState, useEffect, useCallback, useRef } from 'react'
import { FileText, Settings, AlertCircle } from 'lucide-react'
import type { AtlasStatus } from '@codrag/ui'
import {
  // API
  useApiClient,
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
  type DashboardLayoutApi,
  type DashboardLayout,
  // Layout
  PanelPicker,
  useEventStream,
} from '@codrag/ui'
import { StartupScreen } from './components/StartupScreen'
import { UpdateBanner } from './components/UpdateBanner'
import { SettingsDrawer } from './components/settings/SettingsDrawer'
import { ErrorToast } from './components/ErrorToast'
import { useLicenseSystem } from './hooks/useLicenseSystem'
import { useLLMConfig } from './hooks/useLLMConfig'
import { useDeepAnalysis } from './hooks/useDeepAnalysis'
import { useWatchSystem } from './hooks/useWatchSystem'
import { useTraceSystem } from './hooks/useTraceSystem'
import { useEnrichment } from './hooks/useEnrichment'
import { useSearchContext } from './hooks/useSearchContext'
import { useFileSystem } from './hooks/useFileSystem'
import { useProjectManager } from './hooks/useProjectManager'
import { useDashboardPanels } from './hooks/useDashboardPanels'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

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
  const [settingsOpenToTab, setSettingsOpenToTab] = useState<'project' | 'global' | 'developer' | undefined>(undefined)
  const [scrollToDeepAnalysis, setScrollToDeepAnalysis] = useState(false)
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

  const layoutApiRef = useRef<DashboardLayoutApi | null>(null)

  // ── Watch (hook) ─────────────────────────────────────────────
  // Declared before useProjectManager so refs can be passed as deps
  const watchHookPlaceholder = useRef<ReturnType<typeof useWatchSystem> | null>(null)

  // ── Project manager (hook — SM-1 Phase C1) ─────────────────
  // Owns: projects, selectedProjectId, projectStatuses, buildingProjects,
  // transientCompleteProjects, projectConfig, configDirty, and related actions.
  const project = useProjectManager({
    onError: (msg) => setError(msg),
    handleStartWatch: async () => { await watchHookPlaceholder.current?.handleStartWatch?.() },
    refreshWatchStatus: async (pid) => { await watchHookPlaceholder.current?.refreshWatchStatus?.(pid) },
  })
  const {
    selectedProjectId, selectedProject, projectStatus, projectSummaries,
    projectConfig, configDirty, transientCompleteProjects,
    setSelectedProjectId, refreshProjects, refreshStatus,
    handleAddProject, handleDeleteProject, handleBuild,
    handleSaveConfig, handleProjectConfigChange, handleDetectStack,
    setProjectConfig, setConfigDirty,
  } = project

  // ── Search + Context (hook) ─────────────────────────────────
  const {
    query, setQuery, searchK, setSearchK, minScore, setMinScore,
    searchLoading, searchResults, selectedChunk, setSelectedChunk,
    contextK, setContextK, contextMaxChars, setContextMaxChars,
    contextIncludeSources, setContextIncludeSources,
    contextIncludeScores, setContextIncludeScores,
    contextStructured, setContextStructured,
    contextIncludeAtlas, setContextIncludeAtlas,
    contextCompression, setContextCompression,
    context, contextMeta,
    handleSearch, handleGetContext, handleCopyContext,
    resetSearch,
  } = useSearchContext(selectedProjectId, { onError: (msg) => setError(msg) })

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
  // Update the placeholder ref so useProjectManager can call watch handlers
  watchHookPlaceholder.current = { watchStatus, watchLoading, refreshWatchStatus, handleStartWatch, handleStopWatch }

  // Wire cross-hook deps into useProjectManager via refs (updated each render)
  useEffect(() => {
    // These are read via refs inside useProjectManager callbacks, not during render
  }, [fetchFileTree, includedPaths])
  // Update refs that useProjectManager reads (done automatically via its internal ref pattern)

  // ── Deep analysis (hook) ─────────────────────────────────────
  const {
    deepAnalysisSchedule, setDeepAnalysisSchedule,
    setDeepAnalysisStatus,
    fetchDeepAnalysisStatus,
    budgetUsage,
  } = useDeepAnalysis(selectedProjectId, { onError: (msg) => setError(msg) })

  // ── Event Stream ───────────────────────────────────────────
  const eventsUrl = import.meta.env.DEV
    ? `http://${window.location.hostname}:8400/events`
    : `${api.baseUrl}/events`;
  const { logs, tasks, clearLogs, pipelineEvents, scopeEvents } = useEventStream(eventsUrl, 1000);

  // Helper to find relevant task for current project.
  // Prefer running tasks over completed ones so transition detectors
  // pick up new builds instead of sticking on old completed entries.
  const findActiveTask = useCallback((type: 'index_build' | 'trace_build') => {
    if (!selectedProjectId) return undefined;
    const matching = Object.values(tasks).filter(t => 
      t.task_id.startsWith(`${type}:${selectedProjectId}`) && 
      (t.status === 'running' || t.status === 'completed')
    );
    return matching.find(t => t.status === 'running') ?? matching[matching.length - 1];
  }, [tasks, selectedProjectId]);

  // ── Enrichment (hook) ───────────────────────────────────────
  const {
    inferredEdgesStatus, inferredEdgesRunning,
    augmentationStatus, augmenting, validating,
    epistemicStatus, epistemicRunning,
    moduleStatus, clusterRunning,
    atlasRunning,
    deepeningStatus, deepeningRunning,
    knowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding,
    handleRunAugmentation, handleRunEpistemic, handleRunModuleSynthesis,
    handleRunDeepening, handleRunKnowledgeBuild,
    handleRunDeepEnrichment,
    resetAll: resetEnrichment,
  } = useEnrichment(selectedProjectId, {
    onError: (msg) => setError(msg),
    pipelineEvents,
  })

  // ── Atlas (Phase 29) ─────────────────────────────────────────
  const [atlasStatus, setAtlasStatus] = useState<AtlasStatus | null>(null)

  // ── Trace system (hook) ───────────────────────────────────────
  const {
    traceStatus,
    traceCoverage,
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
    resetAtlas: () => setAtlasStatus(null),
  })

  const fetchAtlas = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      const data = await api.getAtlas(selectedProjectId)
      setAtlasStatus(data)
    } catch { /* Atlas not available yet */ }
  }, [api, selectedProjectId])

  // ── Mode sync: keep panel switch ↔ settings dropdown in sync ──
  const handleSyncedEnrichmentAutoConfigChange = useCallback((newConfig: typeof enrichmentAutoConfig) => {
    handleEnrichmentAutoConfigChange(newConfig)
    if (newConfig.deepEnrichment !== deepAnalysisSchedule.mode) {
      setDeepAnalysisSchedule((prev) => ({ ...prev, mode: newConfig.deepEnrichment as any }))
    }
  }, [handleEnrichmentAutoConfigChange, deepAnalysisSchedule.mode, setDeepAnalysisSchedule])

  const handleSyncedDeepAnalysisScheduleChange = useCallback((newSchedule: typeof deepAnalysisSchedule) => {
    setDeepAnalysisSchedule(newSchedule)
    if (newSchedule.mode !== enrichmentAutoConfig.deepEnrichment) {
      handleEnrichmentAutoConfigChange({ ...enrichmentAutoConfig, deepEnrichment: newSchedule.mode })
    }
  }, [setDeepAnalysisSchedule, enrichmentAutoConfig, handleEnrichmentAutoConfigChange])

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
        try {
          const globalCfg = await api.getGlobalConfig()
          if (globalCfg.llm_config) {
            setLLMConfig(globalCfg.llm_config)
            // Fetch compression status to populate lingua_downloaded
            try {
              const compressionStatus = await api.getCompressionStatus()
              if (compressionStatus.lingua) {
                setLLMConfig((prev) => ({
                  ...prev,
                  compression: {
                    ...prev.compression,
                    lingua_downloaded: compressionStatus.lingua.downloaded ?? false,
                  },
                }))
              }
            } catch { /* Compression status not critical */ }
          }
          if (globalCfg.deep_analysis) setDeepAnalysisSchedule((prev) => ({ ...prev, ...globalCfg.deep_analysis } as any))
          if (globalCfg.ui_preferences) {
            const prefs = globalCfg.ui_preferences
            if (prefs.mode) setUiMode(prefs.mode)
            if (prefs.theme) setUiTheme(prefs.theme)
            if (prefs.bg_image !== undefined) setBgImage(prefs.bg_image)
          }
          if (globalCfg.module_layout?.version) {
            try { localStorage.setItem('codrag_dashboard_layout', JSON.stringify(globalCfg.module_layout)) } catch { /* storage full */ }
          }
        } catch { /* Global config not available — use defaults */ }
        void fetchLLMSlotsStatus()
        void fetchLicense()
      } catch { /* Error already set */ } finally { setLoading(false) }
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

  // ── Refresh watch + deep analysis on project change ─────────
  // NOTE: Project status, config, trace — all self-hydrate in their own hooks now.
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshWatchStatus(selectedProjectId)
    void fetchDeepAnalysisStatus()
    void fetchAtlas()
  }, [selectedProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Project limit ───────────────────────────────────────────
  const projectLimit = effectiveTier === 'free' ? 1 : Infinity
  const isAtProjectLimit = project.projects.length >= projectLimit

  // ── Dashboard panels (hook) ─────────────────────────────────
  const { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX: pinnedPrefix } = useDashboardPanels({
    // Cross-cutting
    projectStatus, selectedProject, selectedProjectId, projectConfig, isPro,
    scopeStatus: selectedProjectId ? scopeEvents[selectedProjectId] : undefined,
    logs, clearLogs, findActiveTask, handleBuild,
    transientComplete: selectedProjectId ? transientCompleteProjects.has(selectedProjectId) : false,
    onOpenDeepSettings: () => { setSettingsOpenToTab('project'); setScrollToDeepAnalysis(true); setSettingsOpen(true) },
    onOpenSettings: () => { setSettingsOpenToTab('global'); setSettingsOpen(true) },
    // Domain groups
    search: {
      query, setQuery, searchK, setSearchK, minScore, setMinScore,
      searchLoading, searchResults, selectedChunk, setSelectedChunk, handleSearch,
      contextK, setContextK, contextMaxChars, setContextMaxChars,
      contextIncludeSources, setContextIncludeSources,
      contextIncludeScores, setContextIncludeScores,
      contextStructured, setContextStructured,
      contextIncludeAtlas, setContextIncludeAtlas,
      contextCompression, setContextCompression,
      context, contextMeta, handleGetContext, handleCopyContext,
    },
    files: {
      fileTree, includedPaths, handleToggleInclude,
      pathWeights, handlePathWeightChange, handleLoadChildren,
      pinnedPaths, pinnedFiles, handlePinFile, handleUnpinFile, handleLoadFileContent,
    },
    trace: {
      traceStatus, traceCoverage, indexAutoRebuild, handleIndexAutoRebuildChange,
      enrichmentAutoConfig, handleEnrichmentAutoConfigChange: handleSyncedEnrichmentAutoConfigChange,
      handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
      handleBuildTrace, handleEnableTrace, handleTogglePause,
      handleTraceAll, handleRetraceStale, handleAddExcludePattern, handleRemoveExcludePattern,
      fetchTraceCoverage, handleRunFastSync, handleDestroyGraph,
    },
    enrichment: {
      inferredEdgesStatus, inferredEdgesRunning,
      augmentationStatus, augmenting, validating, handleRunAugmentation,
      epistemicStatus, epistemicRunning, handleRunEpistemic,
      moduleStatus, clusterRunning, handleRunModuleSynthesis,
      atlasRunning,
      deepeningStatus, deepeningRunning, handleRunDeepening,
      knowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding, handleRunKnowledgeBuild,
      handleRunDeepEnrichment,
    },
    watch: { watchStatus, watchLoading, handleStartWatch, handleStopWatch },
    llm: {
      llmConfig, llmSlotsStatus,
      handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
      handleTestEndpoint, handleFetchModels, handleTestModel, handleDownloadModel,
      availableModels, loadingModels, testingSlot, testResults,
    },
    deepAnalysis: { deepAnalysisSchedule, setDeepAnalysisSchedule, budgetUsage },
    atlas: { atlasStatus },
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
      <UpdateBanner />
      {isDaemonUnhealthy && (
        <div className="fixed inset-x-0 top-0 z-[100] bg-error text-white px-4 py-2 text-sm font-bold flex items-center justify-center gap-2 shadow-lg">
        <AlertCircle className="w-4 h-4" />
        Connection to CoDRAG daemon lost. Attempting to reconnect...
      </div>
      )}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => { setSettingsOpen(false); setScrollToDeepAnalysis(false) }}
        openToTab={settingsOpenToTab}
        scrollToDeepAnalysis={scrollToDeepAnalysis}
        projectConfig={projectConfig}
        onProjectConfigChange={handleProjectConfigChange}
        onSaveConfig={() => void handleSaveConfig()}
        configDirty={configDirty}
        hasProject={!!selectedProjectId}
        onDetectStack={selectedProjectId ? handleDetectStack : undefined}
        deepAnalysisSchedule={deepAnalysisSchedule}
        onDeepAnalysisScheduleChange={handleSyncedDeepAnalysisScheduleChange}
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
          onClick={() => { setSettingsOpenToTab(undefined); setSettingsOpen(true) }}
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
        limitReached={isAtProjectLimit}
        currentTierLabel={effectiveTier === 'free' ? 'Free' : effectiveTier === 'starter' ? 'Starter' : undefined}
        currentLimit={projectLimit === Infinity ? undefined : projectLimit}
        onUpgrade={() => { setAddModalOpen(false); setSettingsOpenToTab('global'); setSettingsOpen(true) }}
      />
    </>
  )
}

export default App
