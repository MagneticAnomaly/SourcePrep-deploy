import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { FileText, Settings, AlertCircle, AlertTriangle, X, GitBranch } from 'lucide-react'
import type { AtlasStatus, ActivityHeatmapData, UserRole, PipelineProvenance, AssignmentMode, LLMConfig } from '@codrag/ui'
import {
  // API
  useApiClient,
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  SidebarAIGateway,
  SidebarPipelineQueue,
  TeamSyncIndicator,
  // Dashboard
  ModularDashboard,
  // Project
  AddProjectModal,
  // Patterns
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
import { useHydrationController } from './hooks/useHydrationController'
import { useDashboardPanels } from './hooks/useDashboardPanels'
import { useAuditSystem } from './hooks/useAuditSystem'
import { useSpaghettiSystem } from './hooks/useSpaghettiSystem'
import { useGoalpostsSystem } from './hooks/useGoalpostsSystem'
import { useRoadmapSystem } from './hooks/useRoadmapSystem'
import { useOpportunitiesSystem } from './hooks/useOpportunitiesSystem'
import { useArchitectureSystem } from './hooks/useArchitectureSystem'
import { useConceptSystem } from './hooks/useConceptSystem'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

// ── App ──────────────────────────────────────────────────────

function App() {
  const api = useApiClient()

  // ── Connection state ───────────────────────────────────────
  const [isConnected, setIsConnected] = useState(false)
  const [isDaemonUnhealthy, setIsDaemonUnhealthy] = useState(false)

  // Health polling: visibility-aware with grace period to prevent
  // flicker when Chrome throttles background tabs.
  useEffect(() => {
    let interval: NodeJS.Timeout
    let failCount = 0
    const FAIL_THRESHOLD = 3  // Require 3 consecutive failures before showing banner

    const checkHealth = async () => {
      // Skip health checks while tab is hidden — Chrome throttles
      // background timers, causing fetch timeouts that trigger
      // the "daemon lost" banner.
      if (document.hidden) return

      try {
        await api.getHealth()
        if (!isConnected) setIsConnected(true)
        failCount = 0
        setIsDaemonUnhealthy(false)
      } catch {
        failCount++
        // Only show unhealthy banner after FAIL_THRESHOLD consecutive failures
        // to prevent single-tick flicker from background tab throttling
        if (isConnected && failCount >= FAIL_THRESHOLD) {
          setIsDaemonUnhealthy(true)
        }
      }
    }

    // When tab becomes visible again, immediately re-check health
    // instead of waiting for the next interval tick
    const onVisibilityChange = () => {
      if (!document.hidden && isConnected) {
        // Reset fail count on tab switch — the previous failures
        // were likely from throttled background timers, not real outages
        failCount = 0
        setIsDaemonUnhealthy(false)
        void checkHealth()
      }
    }

    // Start polling once connected (StartupScreen handles the initial wait)
    if (isConnected) {
      interval = setInterval(checkHealth, 5000)
      checkHealth()
      document.addEventListener('visibilitychange', onVisibilityChange)
    }

    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
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
  const [fastCollapsed, setFastCollapsed] = useState<boolean>(true);
  const [deepCollapsed, setDeepCollapsed] = useState<boolean>(true);
  const [finalizeCollapsed, setFinalizeCollapsed] = useState<boolean>(true);
  const [maxActiveProjects, setMaxActiveProjects] = useState<number | 'infinite'>('infinite')
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null)
  const [computeNodes, setComputeNodes] = useState<any[]>([])
  const [dashboardLayout, setDashboardLayout] = useState<DashboardLayout | null>(null)
  const [projectLimitBannerDismissed, setProjectLimitBannerDismissed] = useState(false)
  const [devRoleOverride, setDevRoleOverride] = useState<UserRole | null>(() => {
    const stored = localStorage.getItem('codrag_dev_role_override')
    return stored ? stored as UserRole : null
  })
  const [globalConfig, setGlobalConfig] = useState<{ developer_debug_mode?: boolean; developer_show_dev_panels?: boolean }>({})

  const [adminPolicy, setAdminPolicy] = useState<any>(null)
  const [seatStatus, setSeatStatus] = useState<any>(null)
  const [securityHealth, setSecurityHealth] = useState<any>(null)
  const [securityEvents, setSecurityEvents] = useState<any[]>([])

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
  // Signal/isHydrating refs — populated by useHydrationController below,
  // but available to useProjectManager's effects which run after all hooks.
  const hydrationSignalRef = useRef<AbortSignal | undefined>(undefined)
  const hydrationIsHydratingRef = useRef(false)

  const project = useProjectManager({
    onError: (msg, variant) => showToast(msg, variant),
    handleStartWatch: async () => { await watchHookPlaceholder.current?.handleStartWatch?.() },
    refreshWatchStatus: async (pid) => { await watchHookPlaceholder.current?.refreshWatchStatus?.(pid) },
    fetchFileTree: async (pid) => { await fetchFileTreeRef.current?.(pid) },
    includedPaths: includedPathsRef.current,
    signal: hydrationSignalRef.current,
    isHydrating: hydrationIsHydratingRef.current,
  })
  // (includedPathsRef.current is updated below after useFileSystem runs)
  const {
    selectedProjectId, selectedProject, projectStatus, projectSummaries,
    projectConfig, configDirty, transientCompleteProjects,
    setSelectedProjectId, refreshProjects, refreshStatus,
    handleAddProject, handleArchiveProject, handleUnarchiveProject, handleDeleteProject, handleBuild,
    handleSaveConfig, handleProjectConfigChange, handleDetectStack,
    handleToggleActive, handleToggleStar, handleCyclePriority,
    setProjectConfig, setConfigDirty,
  } = project

  // ── Hydration controller (Phase 70) ────────────────────────
  // Coordinates project-switch: debounces ID, manages AbortController,
  // tracks hydration progress to suppress polls during transition.
  const hydration = useHydrationController(selectedProjectId)
  hydrationSignalRef.current = hydration.signal
  hydrationIsHydratingRef.current = hydration.isHydrating

  // Derive which project (if any) holds exclusive priority
  const exclusiveProjectId = useMemo(() => {
    const exc = projectSummaries.find(p => p.priority_level === 'exclusive');
    return exc?.id ?? null;
  }, [projectSummaries]);

  const sortedProjectSummaries = useMemo(() => {
    const levelOrder = { exclusive: 0, boost: 1, none: 2 };
    return [...projectSummaries].sort((a, b) => {
      const al = levelOrder[a.priority_level ?? (a.is_starred ? 'boost' : 'none')];
      const bl = levelOrder[b.priority_level ?? (b.is_starred ? 'boost' : 'none')];
      return al - bl; // higher priority first
    })
  }, [projectSummaries])

  // ── Search + Context (hook) ─────────────────────────────────
  const {
    query, setQuery, searchK, setSearchK, minScore, setMinScore,
    searchLoading, searchResults, selectedChunk, setSelectedChunk,
    contextK, setContextK, contextMaxChars, setContextMaxChars,
    contextIncludeSources, setContextIncludeSources,
    contextIncludeScores, setContextIncludeScores,
    contextStructured, setContextStructured,
    contextIncludeAtlas, setContextIncludeAtlas,
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
  } = useFileSystem(selectedProjectId, { layoutApiRef, signal: hydration.signal })
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
    tokenUsageData,
  } = useDeepAnalysis(selectedProjectId, {
    onError: (msg, variant) => showToast(msg, variant),
    // F-56: per-project deep analysis schedule scoping.
    projectConfig,
    setProjectConfig,
    setConfigDirty,
  })

  // ── Audit system (Phase 43) ────────────────────────────────
  const audit = useAuditSystem(hydration.hydratedProjectId, { signal: hydration.signal, isHydrating: hydration.isHydrating })

  // ── Spaghetti Finder (Phase 52) ─────────────────────────────
  const spaghetti = useSpaghettiSystem(hydration.hydratedProjectId, { signal: hydration.signal })

  // ── Goalposts (Phase 57) ────────────────────────────────────
  const goalposts = useGoalpostsSystem(hydration.hydratedProjectId, { signal: hydration.signal, isHydrating: hydration.isHydrating })

  // ── Roadmap (Phase 59) ──────────────────────────────────────
  const roadmap = useRoadmapSystem(hydration.hydratedProjectId, { signal: hydration.signal, isHydrating: hydration.isHydrating })

  // ── Opportunities (Phase 63) ───────────────────────────────
  const opportunities = useOpportunitiesSystem(hydration.hydratedProjectId, { signal: hydration.signal, isHydrating: hydration.isHydrating })

  // ── Architecture Diagram (Phase 71) ────────────────────────
  const architecture = useArchitectureSystem(hydration.hydratedProjectId, { signal: hydration.signal })

  // ── Concepts (Phase 74) ────────────────────────────────────
  const concepts = useConceptSystem(hydration.hydratedProjectId, { signal: hydration.signal })

  // ── Event Stream ───────────────────────────────────────────
  const eventsUrl = import.meta.env.DEV
    ? `http://${window.location.hostname}:8400/events`
    : `${api.baseUrl}/events`;
  const { logs, tasks, clearLogs, pipelineEvents, scopeEvents, queueVersion } = useEventStream(eventsUrl, 1000);

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
  // Phase 114 T15: derive trace-pipeline panel visibility once, share it
  // between useEnrichment (for /pipeline/status polling) and
  // useDashboardPanels (for usePipelineHealth polling). Both hooks only
  // matter when the panel that renders their output is on-screen.
  // Default to true during layout hydration so early lifecycle events
  // (project switch, first paint) aren't dropped.
  const tracePipelinePanelVisible = dashboardLayout
    ? (dashboardLayout.panels.find((pnl) => pnl.id === 'trace-pipeline')?.visible ?? true)
    : true

  const {
    inferredEdgesStatus, inferredEdgesRunning,
    augmentationStatus, augmenting, validating,
    epistemicStatus, epistemicRunning,
    groupReasoningRunning,
    moduleStatus, clusterRunning,
    atlasRunning,
    deepeningStatus, deepeningRunning,
    knowledgeStatus, deepKnowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding,
    groupReasoningStatus,
    // Phase 96F: Finalize stage statuses (rules / concepts / audit / antibodies).
    // These come from the enrichment reducer state spread.  Without them in the
    // destructure list the dashboard crashes with "rulesStatus is not defined"
    // when GraphEnrichmentPipeline tries to render the Finalize group.
    rulesStatus,
    conceptsStatus,
    auditPipelineStatus,
    antibodiesStatus,
    finalizeRunning,
    finalizeCurrentStage,
    handleRunAugmentation, handleRunEpistemic, handleRunModuleSynthesis,
    handleRunDeepening, handleRunKnowledgeBuild,
    handleRunDeepEnrichment,
    handleRunFinalize,
    handlePausePipeline, handleResumePipeline, handleSwapModel,
    fastPaused, deepPaused, finalizePaused,
    fastPausedStage, deepPausedStage, finalizePausedStage,
    resetAll: resetEnrichment,
    rehydrate: rehydrateEnrichment,
    refreshStageDataFromPipeline,
  } = useEnrichment(selectedProjectId, {
    onError: (msg, variant) => showToast(msg, variant),
    pipelineEvents,
    onDeepCompleted: () => { void fetchAtlas(); void fetchProvenance() },
    onFastCompleted: () => { void fetchProvenance() },
    signal: hydration.signal,
    isHydrating: hydration.isHydrating,
    // Phase 114 T15: gate background polls on panel visibility so the
    // enrichment pipeline hook stops pinging /pipeline/status when the
    // trace-pipeline panel is hidden. Defaults to true when layout is
    // still hydrating (first paint) so we don't miss early events.
    enrichmentPanelVisible: tracePipelinePanelVisible,
  })

  // ── Atlas (Phase 29) ─────────────────────────────────────────
  const [atlasStatus, setAtlasStatus] = useState<AtlasStatus | null>(null)
  const [activityData, setActivityData] = useState<ActivityHeatmapData | null>(null)

  // ── Pipeline Provenance (Phase 49) ──────────────────────────
  const [pipelineProvenance, setPipelineProvenance] = useState<PipelineProvenance | null>(null)

  const fetchProvenance = useCallback(async (signal?: AbortSignal) => {
    if (!selectedProjectId || signal?.aborted) return
    try {
      const data = await api.getPipelineProvenance(selectedProjectId)
      if (signal?.aborted) return
      setPipelineProvenance(data)
    } catch { /* Provenance not available yet */ }
  }, [api, selectedProjectId])

  // ── Trace system (hook) ───────────────────────────────────────
  const {
    projectLoading,
    traceStatus,
    traceCoverage,
    indexAutoRebuild, enrichmentAutoConfig,
    fetchTraceCoverage,
    handleBuildTrace, handleEnableTrace,
    handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
    handleTraceAll, handleRetraceStale,
    handleAddExcludePattern, handleRemoveExcludePattern,
    handleRunFastSync,
    handleEnrichmentAutoConfigChange, handleIndexAutoRebuildChange,
    handleDestroyIndex, handleRebuildPipeline,
    handleDestroyEnrichmentFull, handleDestroyFinalizeFull,
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
    rehydrateEnrichment,
    fetchProvenance,
    syncDeepAnalysisScheduleMode: (mode) =>
      setDeepAnalysisSchedule((prev) => ({ ...prev, mode: mode as any })),
    pausePipeline: handlePausePipeline,
    signal: hydration.signal,
    isHydrating: hydration.isHydrating,
  })

  const fetchAtlas = useCallback(async (signal?: AbortSignal) => {
    if (!selectedProjectId || signal?.aborted) return
    try {
      const data = await api.getAtlas(selectedProjectId)
      if (signal?.aborted) return  // Don't update state if project switched
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
    markLLMConfigClean, flushPendingSave,
    fetchLLMSlotsStatus,
  } = useLLMConfig({
    onDirty: () => setConfigDirty(true),
    onSwapModel: handleSwapModel,
  })

  // Apply mode switch: flush any pending debounced slot save first so the
  // mode-switch sees the latest config, then switch modes.
  const handleModeApply = useCallback(
    async (mode: AssignmentMode, blocks?: LLMConfig['assignment_blocks']) => {
      await flushPendingSave()
      await handleModeSwitch(mode, blocks)
    },
    [flushPendingSave, handleModeSwitch]
  )

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
  const uiPrefsInitialMount = useRef(true)
  useEffect(() => {
    if (uiPrefsInitialMount.current) { uiPrefsInitialMount.current = false; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({
        ui_preferences: { mode: uiMode, theme: uiTheme, bg_image: bgImage },
      }).catch(() => { })
    }, 500)
    return () => clearTimeout(timeout)
  }, [api, uiMode, uiTheme, bgImage])

  const handleMaxActiveProjectsChange = useCallback((value: number | 'infinite') => {
    setMaxActiveProjects(value)
    api.updateGlobalConfig({ max_active_projects: value }).catch(() => { })
  }, [api])

  const handleDevRoleOverrideChange = useCallback((role: UserRole | null) => {
    setDevRoleOverride(role)
    if (role) localStorage.setItem('codrag_dev_role_override', role)
    else localStorage.removeItem('codrag_dev_role_override')
  }, [])

  const handleGlobalConfigChange = useCallback((patch: Record<string, any>) => {
    setGlobalConfig(prev => ({ ...prev, ...patch }))
    api.updateGlobalConfig(patch as any).catch(() => { })
  }, [api])

  const handleToggleGroupCollapsed = useCallback((group: 'fast' | 'deep' | 'finalize') => {
    let nextFast = fastCollapsed;
    let nextDeep = deepCollapsed;
    let nextFin = finalizeCollapsed;
    if (group === 'fast') { nextFast = !fastCollapsed; setFastCollapsed(nextFast); }
    if (group === 'deep') { nextDeep = !deepCollapsed; setDeepCollapsed(nextDeep); }
    if (group === 'finalize') { nextFin = !finalizeCollapsed; setFinalizeCollapsed(nextFin); }
    api.updateGlobalConfig({
      pipeline_ui: {
        fast_collapsed: nextFast,
        deep_collapsed: nextDeep,
        finalize_collapsed: nextFin,
      },
    } as any).catch(() => { });
  }, [api, fastCollapsed, deepCollapsed, finalizeCollapsed])

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


  // Poll scheduler status when connected.
  // F-11: bumped 5s -> 10s and added document.hidden pause +
  // in-flight guard to stop request stacking when the daemon is busy.
  useEffect(() => {
    if (!isConnected) return
    let inFlight = false
    const poll = async () => {
      if (document.hidden || inFlight) return
      inFlight = true
      try {
        const s = await api.getSchedulerStatus()
        setSchedulerStatus(s)
      } catch {
        // ignore
      } finally {
        inFlight = false
      }
    }
    void poll()
    const interval = setInterval(poll, 10000)
    return () => clearInterval(interval)
  }, [isConnected, api])

  // LS-2: Periodic license re-validation (every hour, backend checks 7-day interval)
  useEffect(() => {
    if (!isConnected) return
    const validate = () => {
      api.validateLicense().catch(() => { })
    }
    const fetchAdminData = () => {
      api.getAdminPolicy().then(setAdminPolicy).catch(() => { })
      api.getSeatStatus().then(setSeatStatus).catch(() => { })
      api.getSecurityHealth().then(setSecurityHealth).catch(() => { })
      api.getSecurityEvents(30).then(setSecurityEvents).catch(() => { })
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
      .catch(() => { })
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
    if (!isConnected) return
    const init = async () => {
      try {
        await refreshProjects()
        try {
          const globalCfg = await api.getGlobalConfig()
          // Read developer_debug_mode FIRST — before any operations that
          // might throw and skip it via the catch block below.
          if (globalCfg.developer_debug_mode !== undefined || globalCfg.developer_show_dev_panels !== undefined) {
            setGlobalConfig(prev => ({
              ...prev,
              ...(globalCfg.developer_debug_mode !== undefined && { developer_debug_mode: globalCfg.developer_debug_mode }),
              ...(globalCfg.developer_show_dev_panels !== undefined && { developer_show_dev_panels: globalCfg.developer_show_dev_panels }),
            }))
          }
          if (globalCfg.max_active_projects) {
            setMaxActiveProjects(globalCfg.max_active_projects)
          }
          if (globalCfg.llm_config) {
            setLLMConfig(globalCfg.llm_config)
          }
          // Arm auto-save regardless of whether the backend had a saved llm_config —
          // fresh installs start with llm_config: null but still need the dirty baseline set.
          setTimeout(() => markLLMConfigClean(), 100)
          if (globalCfg.deep_analysis) setDeepAnalysisSchedule((prev) => ({ ...prev, ...globalCfg.deep_analysis } as any))
          if (globalCfg.ui_preferences) {
            const prefs = globalCfg.ui_preferences
            if (prefs.mode) setUiMode(prefs.mode)
            if (prefs.theme) setUiTheme(prefs.theme)
            if (prefs.bg_image !== undefined) setBgImage(prefs.bg_image)
          }
          if (globalCfg.pipeline_ui) {
            const pui = globalCfg.pipeline_ui;
            if (typeof pui.fast_collapsed === 'boolean') setFastCollapsed(pui.fast_collapsed);
            if (typeof pui.deep_collapsed === 'boolean') setDeepCollapsed(pui.deep_collapsed);
            if (typeof pui.finalize_collapsed === 'boolean') setFinalizeCollapsed(pui.finalize_collapsed);
          }
          if (globalCfg.module_layout?.version) {
            // Only write backend layout to localStorage if localStorage
            // doesn't already have a NEWER layout. localStorage may contain
            // unsaved changes from a previous session (e.g. if the backend
            // auto-save failed due to SQLite lock contention).
            let localIsNewer = false
            try {
              const existingRaw = localStorage.getItem('codrag_dashboard_layout')
              if (existingRaw) {
                const existing = JSON.parse(existingRaw)
                if (existing?.savedAt && existing.savedAt > (globalCfg.module_layout.savedAt ?? 0)) {
                  localIsNewer = true
                  // Push the fresher local layout to the backend to sync
                  api.updateGlobalConfig({ module_layout: existing }).catch(() => { })
                }
              }
            } catch { /* parse error — overwrite with backend */ }
            if (!localIsNewer) {
              try { localStorage.setItem('codrag_dashboard_layout', JSON.stringify(globalCfg.module_layout)) } catch { /* storage full */ }
            }
          }
        } catch { /* Global config not available — use defaults */ }
        void fetchLLMSlotsStatus()
        void fetchLicense()
      } catch { /* Error already set */ } finally { setLoading(false) }
    }
    void init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProjects, isConnected])

  // ── Auto-save dashboard layout to backend ───────────────────
  const layoutInitialMount = useRef(true)
  const dashboardLayoutRef = useRef(dashboardLayout)
  dashboardLayoutRef.current = dashboardLayout

  useEffect(() => {
    if (!dashboardLayout) return
    if (layoutInitialMount.current) { layoutInitialMount.current = false; return }
    const timeout = setTimeout(() => {
      api.updateGlobalConfig({ module_layout: dashboardLayout }).catch((err) => {
        console.warn('[Layout] Backend save failed — layout is safe in localStorage:', err?.message ?? err)
      })
    }, 1000)
    return () => clearTimeout(timeout)
  }, [api, dashboardLayout])

  // Flush layout to backend on tab close so the backend stays in sync.
  // fetch with keepalive survives page unload and supports PUT.
  useEffect(() => {
    const flushToBackend = () => {
      const layout = dashboardLayoutRef.current
      if (!layout) return
      try {
        const url = `${api.baseUrl.replace(/\/$/, '')}/global/config`
        fetch(url, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ module_layout: layout }),
          keepalive: true,
        }).catch(() => { /* best effort */ })
      } catch { /* best effort */ }
    }
    window.addEventListener('beforeunload', flushToBackend)
    return () => window.removeEventListener('beforeunload', flushToBackend)
  }, [api.baseUrl])

  // ── Refresh project status when scope orchestrator signals a build ──
  useEffect(() => {
    const pid = hydration.hydratedProjectId
    if (!pid) return
    const se = scopeEvents[pid]
    if (se?.state === 'building' || se?.state === 'idle') {
      void refreshStatus(pid)
    }
  }, [scopeEvents, hydration.hydratedProjectId, refreshStatus])

  // ── Refresh watch + deep analysis on project change ─────────
  // NOTE: Project status, config, trace — all self-hydrate in their own hooks now.
  useEffect(() => {
    const pid = hydration.hydratedProjectId
    if (!pid) return
    const signal = hydration.signal
    // Reset stale data immediately to prevent cross-project contamination
    setAtlasStatus(null)
    setActivityData(null)
    setPipelineProvenance(null)
    void refreshWatchStatus(pid)
    void fetchDeepAnalysisStatus()
    void fetchAtlas(signal)
    void fetchProvenance(signal)
    api.getProjectActivity(pid, 12)
      .then((data) => { if (!signal.aborted) setActivityData(data) })
      .catch(() => { })
  }, [hydration.hydratedProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Periodic provenance refresh while pipeline is running ───
  // Refreshes every 10s so the UI updates as each stage completes.
  const anyPipelineRunning = augmenting || validating || inferredEdgesRunning ||
    epistemicRunning || groupReasoningRunning || clusterRunning ||
    atlasRunning || deepeningRunning || fastKnowledgeBuilding || deepKnowledgeBuilding ||
    finalizeRunning

  useEffect(() => {
    if (!selectedProjectId || !anyPipelineRunning || hydration.isHydrating) return
    const signal = hydration.signal
    // F-11: bumped 10s -> 15s, added document.hidden pause +
    // in-flight guard. /pipeline/provenance is an expensive
    // aggregation endpoint that combines all stages.
    let inFlight = false
    const tick = async () => {
      if (document.hidden || inFlight || signal.aborted) return
      inFlight = true
      try {
        await fetchProvenance(signal)
      } finally {
        inFlight = false
      }
    }
    const interval = setInterval(tick, 15_000)
    return () => clearInterval(interval)
  }, [selectedProjectId, anyPipelineRunning, fetchProvenance, hydration.signal, hydration.isHydrating])

  // ── Project limit ───────────────────────────────────────────
  // Free tier: hard cap of 1 total project.
  // Pro+ tiers: unlimited projects (maxActiveProjects only limits concurrent pipelines, not total count).
  const projectLimit = effectiveTier === 'free' ? 1 : Infinity
  const isOverProjectLimit = project.projects.length > projectLimit
  const isAtProjectLimit = project.projects.length >= projectLimit

  // ── Dashboard panels (hook) ─────────────────────────────────
  const { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX: pinnedPrefix } = useDashboardPanels({
    // Cross-cutting
    projectStatus, selectedProject, selectedProjectId, projectConfig, isPro, limitReached: isOverProjectLimit,
    inactive: selectedProject?.config?.active === false || selectedProject?.activity_status === 'inactive' || selectedProject?.activity_status === 'locked',
    scopeStatus: selectedProjectId ? scopeEvents[selectedProjectId] : undefined,
    logs, clearLogs, findActiveTask, handleBuild,
    transientComplete: selectedProjectId ? transientCompleteProjects.has(selectedProjectId) : false,
    onOpenDeepSettings: () => { setSettingsOpenToTab('project'); setScrollToDeepAnalysis(true); setSettingsOpen(true) },
    onOpenSettings: () => { setSettingsOpenToTab('global'); setSettingsOpen(true) },
    onOpenDetails: (panelId: string) => layoutApiRef.current?.openDetails(panelId),
    showDevPanels: globalConfig.developer_show_dev_panels ?? false,
    tracePipelinePanelVisible,
    // Domain groups
    search: {
      query, setQuery, searchK, setSearchK, minScore, setMinScore,
      searchLoading, searchResults, selectedChunk, setSelectedChunk, handleSearch,
      contextK, setContextK, contextMaxChars, setContextMaxChars,
      contextIncludeSources, setContextIncludeSources,
      contextIncludeScores, setContextIncludeScores,
      contextStructured, setContextStructured,
      contextIncludeAtlas, setContextIncludeAtlas,
      context, contextMeta, handleGetContext, handleCopyContext,
    },
    files: {
      fileTree, includedPaths, handleToggleInclude,
      pathWeights, handlePathWeightChange, handleLoadChildren,
      pinnedPaths, pinnedFiles, handlePinFile, handleUnpinFile, handleLoadFileContent,
    },
    trace: {
      traceStatus, traceCoverage, projectLoading, indexAutoRebuild, handleIndexAutoRebuildChange,
      enrichmentAutoConfig, handleEnrichmentAutoConfigChange: handleSyncedEnrichmentAutoConfigChange,
      handleSearchTrace, handleGetTraceNode, handleGetTraceNeighbors,
      handleBuildTrace, handleEnableTrace,
      handleTraceAll, handleRetraceStale, handleAddExcludePattern, handleRemoveExcludePattern,
      fetchTraceCoverage, handleRunFastSync,
    },
    enrichment: {
      pipelineProvenance,
      inferredEdgesStatus, inferredEdgesRunning,
      augmentationStatus, augmenting, validating, handleRunAugmentation,
      epistemicStatus, epistemicRunning, handleRunEpistemic,
      groupReasoningRunning,
      moduleStatus, clusterRunning, handleRunModuleSynthesis,
      atlasRunning,
      deepeningStatus, deepeningRunning, handleRunDeepening,
      knowledgeStatus, deepKnowledgeStatus, fastKnowledgeBuilding, deepKnowledgeBuilding, handleRunKnowledgeBuild,
      handleRunDeepEnrichment,
      handleRunFinalize,
      handlePausePipeline, handleResumePipeline,
      fastPaused,
      deepPaused,
      finalizePaused,
      fastPausedStage,
      deepPausedStage,
      finalizePausedStage,
      fastCollapsed,
      deepCollapsed,
      finalizeCollapsed,
      onToggleGroupCollapsed: handleToggleGroupCollapsed,
      groupReasoningStatus,
      rulesStatus,
      conceptsStatus,
      auditPipelineStatus,
      antibodiesStatus,
      finalizeRunning,
      finalizeCurrentStage,
      refreshStageDataFromPipeline,
    },
    llm: {
      llmConfig, llmSlotsStatus,
      handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
      handleTestEndpoint, handleFetchModels, handleTestModel, handleClearTestResult, handleDownloadModel,
      handleModeApply,
      availableModels, modelDetails, loadingModels, testingSlot, testResults,
      maxActiveProjects, onMaxActiveProjectsChange: handleMaxActiveProjectsChange,
      schedulerStatus,
      computeNodes,
      onComputeNodeAdd: handleComputeNodeAdd,
      onComputeNodeUpdate: handleComputeNodeUpdate,
      onComputeNodeDelete: handleComputeNodeDelete,
      onEndpointNodeChange: handleEndpointNodeChange,
    },
    deepAnalysis: { deepAnalysisSchedule, setDeepAnalysisSchedule, budgetUsage, tokenUsageData },
    atlas: { atlasStatus },
    audit,
    spaghetti,
    goalposts,
    roadmap,
    opportunities,
    architecture,
    concepts,
    activityData,
    adminPolicy,
    seatStatus,
    onProvisionSeat: handleProvisionSeat,
    securityHealth,
    securityEvents,
    onExportSecurityReport: () => {
      api.exportSecurityReport().then((data: any) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = 'codrag-security-report.json'; a.click()
        URL.revokeObjectURL(url)
      }).catch(() => { })
    },
    onExportAuditLog: () => {
      api.exportAuditLog('csv').then((data: any) => {
        const content = data.content || JSON.stringify(data, null, 2)
        const blob = new Blob([content], { type: data.format === 'csv' ? 'text/csv' : 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = `codrag-audit-log.${data.format || 'json'}`; a.click()
        URL.revokeObjectURL(url)
      }).catch(() => { })
    },
  })

  // ── Loading state ──────────────────────────────────────────
  // Consolidated: show StartupScreen throughout both the daemon‐connection
  // phase AND the subsequent init/hydration phase. The stage text updates
  // to keep the user informed without jarring screen transitions.
  if (!isConnected || loading) {
    return (
      <StartupScreen
        apiBaseUrl={api.baseUrl}
        onReady={() => setIsConnected(true)}
        stage={isConnected ? 'initializing' : undefined}
        stageMessage={isConnected ? 'Loading projects and configuration…' : undefined}
      />
    )
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
        projectId={selectedProjectId}
        pipelineRunning={
          inferredEdgesRunning || augmenting || validating || epistemicRunning ||
          groupReasoningRunning || clusterRunning || atlasRunning || deepeningRunning ||
          fastKnowledgeBuilding || deepKnowledgeBuilding
        }
        onDestroyIndex={handleDestroyIndex}
        onDestroyEnrichmentFull={handleDestroyEnrichmentFull}
        onDestroyFinalizeFull={handleDestroyFinalizeFull}
        onRebuildPipeline={handleRebuildPipeline}
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
            footer={sidebarCollapsed ? (
              <SidebarAIGateway
                slotsStatus={llmSlotsStatus}
                collapsed
                onOpenDetails={() => layoutApiRef.current?.openDetails('llm-status')}
              />
            ) : undefined}
          >
            {!sidebarCollapsed && (
              <ProjectList
                beforeActions={
                  <>
                    <SidebarPipelineQueue
                      baseUrl={import.meta.env.DEV ? `http://${window.location.hostname}:8400` : api.baseUrl}
                      queueVersion={queueVersion}
                    />
                    <SidebarAIGateway
                      slotsStatus={llmSlotsStatus}
                      onOpenDetails={() => layoutApiRef.current?.openDetails('llm-status')}
                    />
                  </>
                }
                projects={sortedProjectSummaries}
                selectedProjectId={selectedProjectId ?? undefined}
                onProjectSelect={setSelectedProjectId}
                onAddProject={() => setAddModalOpen(true)}
                onDeleteProject={handleDeleteProject}
                onArchiveProject={handleArchiveProject}
                onUnarchiveProject={handleUnarchiveProject}
                onToggleActive={(projectId: string, active: boolean, touch?: boolean) => {
                  handleToggleActive(projectId, active, touch)
                }}
                onToggleStar={handleToggleStar}
                onCyclePriority={handleCyclePriority}
                exclusiveProjectId={exclusiveProjectId}
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
              key={selectedProjectId}
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
                  {selectedProjectId && pipelineEvents?.[selectedProjectId]?.branch && (
                    <div className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-md bg-stone-100 dark:bg-stone-800/80 text-stone-600 dark:text-stone-300 border border-stone-200 dark:border-stone-700">
                      <GitBranch className="w-3.5 h-3.5" />
                      <span className="max-w-[120px] truncate" title={pipelineEvents[selectedProjectId]!.branch!}>
                        {pipelineEvents[selectedProjectId]!.branch!}
                      </span>
                      {pipelineEvents[selectedProjectId]!.branch_state?.transition_from && (
                        <div className="flex items-center ml-1">
                          <span className="w-1 h-1 rounded-full bg-blue-500 mr-1.5 animate-pulse" />
                          <span className="text-blue-600 dark:text-blue-400 font-semibold" title={`Restored from: ${pipelineEvents[selectedProjectId]!.branch_state.transition_from}`}>
                            Restored
                          </span>
                        </div>
                      )}
                    </div>
                  )}
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
        onAdd={async (...args) => {
          await handleAddProject(...args)
          setAddModalOpen(false)
        }}
        limitReached={isAtProjectLimit}
        currentTierLabel={effectiveTier === 'free' ? 'Free' : effectiveTier === 'starter' ? 'Starter' : undefined}
        currentLimit={projectLimit === Infinity ? undefined : projectLimit}
        onUpgrade={() => { setAddModalOpen(false); setSettingsOpenToTab('global'); setSettingsOpen(true) }}
      />
    </>
  )
}

export default App
