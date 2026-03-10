import { useState, useEffect, useCallback, useRef } from 'react'
import { FileText, Settings, AlertCircle, AlertTriangle, X } from 'lucide-react'
import type { AtlasStatus, ActivityHeatmapData, UserRole } from '@codrag/ui'
import {
  // API
  useApiClient,
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  TeamSyncIndicator,
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
import { Toast, makeToast } from './components/Toast'
import type { ToastMessage, ToastVariant } from './components/Toast'
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
import { useAuditSystem } from './hooks/useAuditSystem'
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
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const showToast = useCallback((text: string, variant: ToastVariant = 'error', duration?: number) => {
    setToast(makeToast(text, variant, duration))
  }, [])
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
  const [settingsOpenToTab, setSettingsOpenToTab] = useState<'project' | 'global' | 'advanced' | 'developer' | undefined>(undefined)
  const [scrollToDeepAnalysis, setScrollToDeepAnalysis] = useState(false)
  const [bgImage, setBgImage] = useState<string | null>(() =>
    localStorage.getItem('codrag_bg_image') ?? null
  )
  const [maxActiveProjects, setMaxActiveProjects] = useState<number | 'infinite'>('infinite')
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null)
  const [computeNodes, setComputeNodes] = useState<any[]>([])
  const [batchEstimate, setBatchEstimate] = useState<any>(null)
  const [dashboardLayout, setDashboardLayout] = useState<DashboardLayout | null>(null)
  const [projectLimitBannerDismissed, setProjectLimitBannerDismissed] = useState(false)
  const [devRoleOverride, setDevRoleOverride] = useState<UserRole | null>(() => {
    const stored = localStorage.getItem('codrag_dev_role_override')
    return stored ? stored as UserRole : null
  })
  const [globalConfig, setGlobalConfig] = useState<{ developer_debug_mode?: boolean }>({})

  const [adminPolicy, setAdminPolicy] = useState<any>(null)
  const [seatStatus, setSeatStatus] = useState<any>(null)

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

  const licTier = licenseStatus?.license?.tier
  useEffect(() => {
    // Refresh projects after the backend license status changes (e.g., dev override synced).
    // licenseStatus updates AFTER the API call completes, so the backend has the correct tier.
    if (licTier) project.refreshProjects()
  }, [licTier])

  const layoutApiRef = useRef<DashboardLayoutApi | null>(null)

  // Open AI Gateway panel when triggered from Global Settings
  useEffect(() => {
    const handler = () => {
      layoutApiRef.current?.openDetails('llm-status')
    }
    window.addEventListener('codrag:open-ai-gateway', handler)
    return () => window.removeEventListener('codrag:open-ai-gateway', handler)
  }, [])

  // ── Watch (hook) ─────────────────────────────────────────────
  // Declared before useProjectManager so refs can be passed as deps
  const watchHookPlaceholder = useRef<ReturnType<typeof useWatchSystem> | null>(null)
  // Ref-forward fetchFileTree (defined later in useFileSystem) into useProjectManager
  const fetchFileTreeRef = useRef<((projectId: string) => Promise<void>) | undefined>(undefined)
  // Ref-forward includedPaths (defined later in useFileSystem) into useProjectManager
  const includedPathsRef = useRef<Set<string>>(new Set())

  // ── Project manager (hook — SM-1 Phase C1) ─────────────────
  // Owns: projects, selectedProjectId, projectStatuses, buildingProjects,
  // transientCompleteProjects, projectConfig, configDirty, and related actions.
  const project = useProjectManager({
    onError: (msg, variant) => showToast(msg, variant),
    handleStartWatch: async () => { await watchHookPlaceholder.current?.handleStartWatch?.() },
    refreshWatchStatus: async (pid) => { await watchHookPlaceholder.current?.refreshWatchStatus?.(pid) },
    fetchFileTree: async (pid) => { await fetchFileTreeRef.current?.(pid) },
    includedPaths: includedPathsRef.current,
  })
  // (includedPathsRef.current is updated below after useFileSystem runs)
  const {
    selectedProjectId, selectedProject, projectStatus, projectSummaries,
    projectConfig, configDirty, transientCompleteProjects,
    setSelectedProjectId, refreshProjects, refreshStatus,
    handleAddProject, handleDeleteProject, handleBuild,
    handleSaveConfig, handleProjectConfigChange, handleDetectStack,
    handleToggleActive,
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
  } = useSearchContext(selectedProjectId, { onError: (msg, variant) => showToast(msg, variant) })

  // ── File system (hook) ───────────────────────────────────
  const {
    fileTree, pathWeights, includedPaths, pinnedPaths, pinnedFiles,
    fetchFileTree, handleLoadChildren, handlePathWeightChange,
    handleToggleInclude, clearIncludedPaths,
    handlePinFile, handleUnpinFile, handleLoadFileContent,
  } = useFileSystem(selectedProjectId, { layoutApiRef })
  includedPathsRef.current = includedPaths

  // ── Watch (hook) ─────────────────────────────────────────────
  const {
    watchStatus, watchLoading,
    refreshWatchStatus, handleStartWatch, handleStopWatch,
  } = useWatchSystem(selectedProjectId, { onError: (msg, variant) => showToast(msg, variant ?? 'warning') })
  // Update the placeholder ref so useProjectManager can call watch handlers
  watchHookPlaceholder.current = { watchStatus, watchLoading, refreshWatchStatus, handleStartWatch, handleStopWatch }
  // Update the fetchFileTree ref so useProjectManager can refresh the tree after builds
  fetchFileTreeRef.current = fetchFileTree
  // Update refs that useProjectManager reads (done automatically via its internal ref pattern)

  // ── Deep analysis (hook) ─────────────────────────────────────
  const {
    deepAnalysisSchedule, setDeepAnalysisSchedule,
    setDeepAnalysisStatus,
    fetchDeepAnalysisStatus,
    budgetUsage,
  } = useDeepAnalysis(selectedProjectId, { onError: (msg, variant) => showToast(msg, variant) })

  // ── Audit system (Phase 43) ────────────────────────────────
  const audit = useAuditSystem(selectedProjectId)

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
    groupReasoningRunning,
    moduleStatus, clusterRunning,
    atlasRunning,
    deepeningStatus, deepeningRunning,
    knowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding,
    groupReasoningStatus,
    handleRunAugmentation, handleRunEpistemic, handleRunModuleSynthesis,
    handleRunDeepening, handleRunKnowledgeBuild,
    handleRunDeepEnrichment,
    handlePausePipeline, handleResumePipeline,
    fastPaused, deepPaused,
    resetAll: resetEnrichment,
  } = useEnrichment(selectedProjectId, {
    onError: (msg, variant) => showToast(msg, variant),
    pipelineEvents,
    onDeepCompleted: () => void fetchAtlas(),
  })

  // ── Atlas (Phase 29) ─────────────────────────────────────────
  const [atlasStatus, setAtlasStatus] = useState<AtlasStatus | null>(null)
  const [activityData, setActivityData] = useState<ActivityHeatmapData | null>(null)

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
    onError: (msg, variant) => showToast(msg, variant),
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
    availableModels, modelDetails, loadingModels, testingSlot, testResults,
    llmSlotsStatus,
    handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint, handleFetchModels, handleTestModel, handleClearTestResult,
    handleDownloadModel, handleModeSwitch,
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

  const handleMaxActiveProjectsChange = useCallback((value: number | 'infinite') => {
    setMaxActiveProjects(value)
    api.updateGlobalConfig({ max_active_projects: value }).catch(() => {})
  }, [api])

  const handleDevRoleOverrideChange = useCallback((role: UserRole | null) => {
    setDevRoleOverride(role)
    if (role) localStorage.setItem('codrag_dev_role_override', role)
    else localStorage.removeItem('codrag_dev_role_override')
  }, [])

  const handleGlobalConfigChange = useCallback((patch: Record<string, any>) => {
    setGlobalConfig(prev => ({ ...prev, ...patch }))
    api.updateGlobalConfig(patch as any).catch(() => {})
  }, [api])

  const handleDestroyAtlas = useCallback(async () => {
    if (!selectedProjectId) return
    try { await api.destroyAtlas(selectedProjectId) } catch (e) { console.error('destroyAtlas failed', e) }
  }, [api, selectedProjectId])

  const handleDestroyGroupReasoning = useCallback(async () => {
    if (!selectedProjectId) return
    try { await api.destroyGroupReasoning(selectedProjectId) } catch (e) { console.error('destroyGroupReasoning failed', e) }
  }, [api, selectedProjectId])

  const handleDestroyDeepEnrichment = useCallback(async () => {
    if (!selectedProjectId) return
    try { await api.destroyDeepEnrichment(selectedProjectId) } catch (e) { console.error('destroyDeepEnrichment failed', e) }
  }, [api, selectedProjectId])


  // Poll scheduler status every 5s when connected
  useEffect(() => {
    if (!isConnected) return
    const poll = () => {
      api.getSchedulerStatus()
        .then(setSchedulerStatus)
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [isConnected, api])

  // Fetch batch estimate on connect and when LLM config changes
  const refreshBatchEstimate = useCallback(() => {
    api.getBatchEstimate()
      .then(setBatchEstimate)
      .catch(() => {})
  }, [api])

  useEffect(() => {
    if (isConnected) refreshBatchEstimate()
  }, [isConnected, refreshBatchEstimate, llmConfig])

  // LS-2: Periodic license re-validation (every hour, backend checks 7-day interval)
  useEffect(() => {
    if (!isConnected) return
    const validate = () => {
      api.validateLicense().catch(() => {})
    }
    const fetchAdminData = () => {
      api.getAdminPolicy().then(setAdminPolicy).catch(() => {})
      api.getSeatStatus().then(setSeatStatus).catch(() => {})
    }
    validate() // Check on connect
    fetchAdminData()
    const interval = setInterval(() => {
      validate()
      fetchAdminData()
    }, 60 * 60 * 1000) // Every hour
    return () => clearInterval(interval)
  }, [isConnected, api])

  // Load compute nodes on connect
  const refreshComputeNodes = useCallback(() => {
    api.getComputeNodes()
      .then((res) => setComputeNodes(res.nodes))
      .catch(() => {})
  }, [api])

  useEffect(() => {
    if (isConnected) refreshComputeNodes()
  }, [isConnected, refreshComputeNodes])

  const handleComputeNodeAdd = useCallback(async (node: any) => {
    await api.createComputeNode(node)
    refreshComputeNodes()
  }, [api, refreshComputeNodes])

  const handleComputeNodeUpdate = useCallback(async (nodeId: string, updates: any) => {
    await api.updateComputeNode(nodeId, updates)
    refreshComputeNodes()
  }, [api, refreshComputeNodes])

  const handleComputeNodeDelete = useCallback(async (nodeId: string) => {
    await api.deleteComputeNode(nodeId)
    refreshComputeNodes()
  }, [api, refreshComputeNodes])

  const handleEndpointNodeChange = useCallback((endpointId: string, nodeId: string | null) => {
    const ep = llmConfig.saved_endpoints?.find((e: any) => e.id === endpointId)
    if (!ep) return
    handleEditEndpoint({ ...ep, compute_node_id: nodeId })
  }, [llmConfig.saved_endpoints, handleEditEndpoint])

  const handleProvisionSeat = useCallback(async (email: string) => {
    try {
      return await api.provisionSeat(email)
    } catch (e: any) {
      throw new Error(e.message || 'Failed to provision seat')
    }
  }, [api])

  // ── Init: load projects + global config ─────────────────────
  useEffect(() => {
    const init = async () => {
      try {
        await refreshProjects()
        try {
          const globalCfg = await api.getGlobalConfig()
          if (globalCfg.max_active_projects) {
            setMaxActiveProjects(globalCfg.max_active_projects)
          }
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
          if (globalCfg.developer_debug_mode !== undefined) {
            setGlobalConfig(prev => ({ ...prev, developer_debug_mode: globalCfg.developer_debug_mode }))
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

  // ── Refresh project status when scope orchestrator signals a build ──
  useEffect(() => {
    if (!selectedProjectId) return
    const se = scopeEvents[selectedProjectId]
    if (se?.state === 'building' || se?.state === 'idle') {
      void refreshStatus(selectedProjectId)
    }
  }, [scopeEvents, selectedProjectId, refreshStatus])

  // ── Refresh watch + deep analysis on project change ─────────
  // NOTE: Project status, config, trace — all self-hydrate in their own hooks now.
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshWatchStatus(selectedProjectId)
    void fetchDeepAnalysisStatus()
    void fetchAtlas()
    api.getProjectActivity(selectedProjectId, 12).then(setActivityData).catch(() => {})
  }, [selectedProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Project limit ───────────────────────────────────────────
  // Free tier: hard cap of 1 total project.
  // Pro+ tiers: unlimited projects (maxActiveProjects only limits concurrent pipelines, not total count).
  const projectLimit = effectiveTier === 'free'
    ? 1
    : (maxActiveProjects === 'infinite' ? Infinity : maxActiveProjects)
  const isOverProjectLimit = project.projects.length > projectLimit
  const isAtProjectLimit = project.projects.length >= projectLimit

  // ── Dashboard panels (hook) ─────────────────────────────────
  const { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX: pinnedPrefix } = useDashboardPanels({
    // Cross-cutting
    projectStatus, selectedProject, selectedProjectId, projectConfig, isPro, limitReached: isOverProjectLimit,
    inactive: selectedProject?.config?.active === false || selectedProject?.activity_status === 'inactive' || selectedProject?.activity_status === 'frozen' || selectedProject?.activity_status === 'locked',
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
      groupReasoningRunning,
      moduleStatus, clusterRunning, handleRunModuleSynthesis,
      atlasRunning,
      deepeningStatus, deepeningRunning, handleRunDeepening,
      knowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding, handleRunKnowledgeBuild,
      handleRunDeepEnrichment,
      handlePausePipeline, handleResumePipeline,
      fastPaused,
      deepPaused,
      groupReasoningStatus,
    },
    llm: {
      llmConfig, llmSlotsStatus,
      handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
      handleTestEndpoint, handleFetchModels, handleTestModel, handleClearTestResult, handleDownloadModel,
      availableModels, modelDetails, loadingModels, testingSlot, testResults,
      maxActiveProjects, onMaxActiveProjectsChange: handleMaxActiveProjectsChange,
      schedulerStatus,
      computeNodes,
      onComputeNodeAdd: handleComputeNodeAdd,
      onComputeNodeUpdate: handleComputeNodeUpdate,
      onComputeNodeDelete: handleComputeNodeDelete,
      onEndpointNodeChange: handleEndpointNodeChange,
      batchEstimate,
    },
    deepAnalysis: { deepAnalysisSchedule, setDeepAnalysisSchedule, budgetUsage },
    atlas: { atlasStatus },
    audit,
    activityData,
    adminPolicy,
    seatStatus,
    onProvisionSeat: handleProvisionSeat,
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
      <Toast message={toast} onClose={() => setToast(null)} />
      <UpdateBanner />
      {isOverProjectLimit && !projectLimitBannerDismissed && (
        <div className="fixed inset-x-0 top-0 z-[95] bg-amber-500/90 backdrop-blur text-white px-4 py-2 text-sm font-medium flex items-center justify-center gap-2 shadow-lg">
          <AlertTriangle className="w-4 h-4" />
          <span>
            You have {project.projects.length} projects but your {effectiveTier === 'free' ? 'Free' : effectiveTier.charAt(0).toUpperCase() + effectiveTier.slice(1)} plan supports {projectLimit === Infinity ? 'unlimited' : projectLimit}. Project updates and syncing are paused.
          </span>
          <button
            onClick={() => { setSettingsOpenToTab('global'); setSettingsOpen(true) }}
            className="ml-2 px-2 py-0.5 bg-white/20 hover:bg-white/30 rounded font-semibold transition-colors"
          >
            Upgrade to Pro
          </button>
          <button
            onClick={() => setProjectLimitBannerDismissed(true)}
            className="ml-2 p-1 hover:bg-white/20 rounded transition-colors"
            title="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
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
        maxActiveProjects={maxActiveProjects}
        onMaxActiveProjectsChange={handleMaxActiveProjectsChange}
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
        projectName={selectedProject?.name}
        onDestroyGraph={handleDestroyGraph}
        onDestroyIndex={handleDestroyIndex}
        onDestroyAtlas={handleDestroyAtlas}
        onDestroyGroupReasoning={handleDestroyGroupReasoning}
        onDestroyDeepEnrichment={handleDestroyDeepEnrichment}
        globalConfig={globalConfig}
        onGlobalConfigChange={handleGlobalConfigChange}
        devTierOverride={devTierOverride}
        onDevTierOverrideChange={handleDevTierOverrideChange}
        devRoleOverride={devRoleOverride}
        onDevRoleOverrideChange={handleDevRoleOverrideChange}
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
                onToggleActive={async (projectId: string, active: boolean, touch?: boolean) => {
                  if (!active) {
                    // Auto-pause any running pipelines before deactivating
                    await Promise.allSettled([
                      handlePausePipeline('fast_sync'),
                      handlePausePipeline('deep_enrichment'),
                    ])
                  }
                  handleToggleActive(projectId, active, touch)
                }}
                isPro={isPro}
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
              headerRight={
                <div className="flex items-center gap-2">
                  <TeamSyncIndicator status={projectStatus?.sync} />
                </div>
              }
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
