import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { FileText, Settings, AlertCircle, AlertTriangle, X, GitBranch } from 'lucide-react'
import type { AdvancedConfig, AtlasStatus, ActivityHeatmapData, UserRole, PipelineProvenance, AssignmentMode, LLMConfig } from '@prep/ui'
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
  SyncStatusCard,
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
} from '@prep/ui'
import { StartupScreen } from './components/StartupScreen'
import { UpdateBanner } from './components/UpdateBanner'
import { SettingsOverlay } from './components/settings/v2/SettingsOverlay'
import { renderSettingsPage } from './components/settings/v2/pages'
import type { SettingsPageId } from './components/settings/v2/routeParser'
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
    (localStorage.getItem('prep_ui_mode') as 'light' | 'dark') ?? 'light'
  )
  const [uiTheme, setUiTheme] = useState<string>(() =>
    localStorage.getItem('prep_ui_theme') ?? 'none'
  )
  // Opens the V2 settings overlay at a specific page by pushing
  // `?settings=<page>` into the URL and firing a popstate so the
  // overlay's useSettingsRoute hook picks it up.
  const openSettingsAt = useCallback((page: SettingsPageId) => {
    const next = new URL(window.location.href)
    next.searchParams.set('settings', page)
    window.history.pushState(window.history.state, '', next.toString())
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, [])
  const [bgImage, setBgImage] = useState<string | null>(() =>
    localStorage.getItem('prep_bg_image') ?? null
  )
  const [fastCollapsed, setFastCollapsed] = useState<boolean>(true);
  const [deepCollapsed, setDeepCollapsed] = useState<boolean>(true);
  const [finalizeCollapsed, setFinalizeCollapsed] = useState<boolean>(true);
  const [maxActiveProjects, setMaxActiveProjects] = useState<number | 'infinite'>('infinite')
  const [globalAdvanced, setGlobalAdvanced] = useState<AdvancedConfig>({
    checkpoint_interval: 500,
    min_edge_confidence: 0.5,
    chunk_max_chars: 2000,
    chunk_overlap_chars: 200,
    md_chunk_max_chars: 1800,
    md_chunk_min_chars: 350,
  })
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null)
  const [computeNodes, setComputeNodes] = useState<any[]>([])
  const [dashboardLayout, setDashboardLayout] = useState<DashboardLayout | null>(null)
  const [projectLimitBannerDismissed, setProjectLimitBannerDismissed] = useState(false)
  const [devRoleOverride, setDevRoleOverride] = useState<UserRole | null>(() => {
    const stored = localStorage.getItem('prep_dev_role_override')
    return stored ? stored as UserRole : null
  })
  const [globalConfig, setGlobalConfig] = useState<{
    developer_debug_mode?: boolean;
    exploratory_testing_mode?: boolean;
    developer_show_dev_panels?: boolean;
  }>({})

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
    window.addEventListener('prep:open-ai-gateway', handler)
    return () => window.removeEventListener('prep:open-ai-gateway', handler)
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
    selectedProjectId, selectedProject, projectStatus, projectStatusUnreachable, projectSummaries,
    projectConfig, configDirty, transientCompleteProjects,
    setSelectedProjectId, refreshProjects, refreshStatus,
    handleAddProject, handleArchiveProject, handleUnarchiveProject, handleDeleteProject, handleBuild,
    handleSaveConfig, handleProjectConfigChange, handleDetectStack,
    handleToggleActive, handleToggleStar, handleCyclePriority,
    gateState, vendorScan,
    handleGate1FixFirst, handleGate1ForceExclude, handleGate1Continue,
    setProjectConfig, setConfigDirty,
  } = project

  // ⌘, (Ctrl+, on non-Mac) opens the settings overlay at the default page.
  // Close is owned by SettingsOverlay itself so the dirty guard fires there.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = navigator.platform.includes('Mac') ? e.metaKey : e.ctrlKey
      if (!mod || e.key !== ',') return
      // If overlay is already open, SettingsOverlay's own handler closes it.
      const current = new URLSearchParams(window.location.search).get('settings')
      if (current) return
      e.preventDefault()
      const next = new URL(window.location.href)
      next.searchParams.set('settings', selectedProjectId ? 'sources' : 'appearance')
      window.history.pushState(window.history.state, '', next.toString())
      window.dispatchEvent(new PopStateEvent('popstate'))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedProjectId])

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

  // Dismiss the "Project 'X' is marked as inactive." toast once X is active again.
  // The backend raises this on writes against an inactive project; once the user
  // re-activates it, the warning is no longer relevant.
  useEffect(() => {
    if (!toast) return;
    const match = toast.text.match(/Project '(.+?)' is marked as inactive\./);
    if (!match) return;
    const proj = projectSummaries.find(p => p.name === match[1]);
    if (proj && proj.activity_status === 'active') {
      setToast(null);
    }
  }, [projectSummaries, toast]);


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
    // Reducer's atlasStatus carries progress_current/progress_total merged
    // in from /pipeline/status.stages.atlas. The dashboard panels prop
    // chain (atlas: { atlasStatus }) defaults to the standalone /atlas
    // endpoint, which has the content but not progress — without merging
    // these, the Atlas Building progress bar stays empty during runs.
    atlasStatus: pipelineAtlasStatus,
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
    // Phase 145 I3: anchors for the rebuild freeze-green helper.
    fastCurrentStage,
    deepCurrentStage,
    // §9.3 #28/#29: full group phase strings for completed-coercion.
    fastSyncPhase,
    deepEnrichmentPhase,
    finalizePhase,
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
    // Phase 117: scoped rebuild + stop
    triggerRebuild,
    stopRebuild,
  } = useEnrichment(selectedProjectId, {
    onError: (msg, variant) => showToast(msg, variant),
    pipelineEvents,
    onDeepCompleted: () => { void fetchAtlas(); void fetchProvenance() },
    onFastCompleted: () => { void fetchProvenance() },
    onFinalizeCompleted: () => {
      // Refresh provenance plus the panels that depend on finalize
      // outputs but don't otherwise know that the pipeline ran. Without
      // these the Concepts panel keeps showing "No Concepts Yet" and the
      // Audit panel keeps showing "No audit results yet" even after the
      // stages have written their data.
      void fetchProvenance()
      void concepts.handleRefresh()
      void audit.refresh()
    },
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
    handleDestroyCodeIndex,
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

  // ── Settings v2: Project autosave wiring ────────────────────
  // Project pages autosave on change (debounced). No explicit Save/Discard.
  const [projectSaving, setProjectSaving] = useState(false)
  useEffect(() => {
    if (!configDirty || !selectedProjectId) return
    const t = window.setTimeout(() => {
      setProjectSaving(true)
      void handleSaveConfig().finally(() => setProjectSaving(false))
    }, 500)
    return () => window.clearTimeout(t)
  }, [configDirty, selectedProjectId, handleSaveConfig])

  // ── LLM config (hook) ───────────────────────────────────────
  const {
    llmConfig, setLLMConfig,
    availableModels, modelDetails, loadingModels, testingSlot, testResults,
    cloudModels, loadingCloudModels,
    llmSlotsStatus,
    handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
    handleTestEndpoint, handleFetchModels, handleFetchCloudModels, handleTestModel, handleClearTestResult,
    handleDownloadModel, handleModeSwitch,
    markLLMConfigClean, flushPendingSave,
    fetchLLMSlotsStatus,
  } = useLLMConfig({
    // Intentionally no onDirty: LLM has its own useDebouncedAutoSave + flushPendingSave.
    // Piping LLM changes into setConfigDirty would re-trigger project-config autosave
    // whenever model details refresh (mergeContextCache) — manifests as a blinking
    // "Saving…" indicator in the settings overlay.
    onSwapModel: handleSwapModel,
    // Phase 119 Phase A 5b: surface validator warnings (e.g. saving an Ollama
    // Cloud endpoint without picking a plan tier) via the dashboard toast.
    // Each warning becomes its own toast so users can read and dismiss them.
    onWarnings: (warnings) => {
      for (const w of warnings) showToast(w, 'warning', 7000)
    },
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
    root.setAttribute('data-prep-theme', uiTheme === 'none' ? 'a' : uiTheme)
    localStorage.setItem('prep_ui_mode', uiMode)
    localStorage.setItem('prep_ui_theme', uiTheme)
    if (bgImage) localStorage.setItem('prep_bg_image', bgImage)
    else localStorage.removeItem('prep_bg_image')
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
    if (role) localStorage.setItem('prep_dev_role_override', role)
    else localStorage.removeItem('prep_dev_role_override')
  }, [])

  const handleGlobalConfigChange = useCallback((patch: Record<string, any>) => {
    setGlobalConfig(prev => ({ ...prev, ...patch }))
    api.updateGlobalConfig(patch as any).catch(() => { })
  }, [api])

  const handleOpenAiGateway = useCallback(() => {
    const next = new URL(window.location.href)
    next.searchParams.delete('settings')
    window.history.replaceState(window.history.state, '', next.toString())
    window.dispatchEvent(new CustomEvent('prep:open-ai-gateway'))
  }, [])

  const handleGlobalAdvancedChange = useCallback((patch: Partial<AdvancedConfig>) => {
    setGlobalAdvanced(prev => ({ ...prev, ...patch }))
    api.updateAdvancedConfig(patch).catch(() => { })
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
              const existingRaw = localStorage.getItem('prep_dashboard_layout')
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
              try { localStorage.setItem('prep_dashboard_layout', JSON.stringify(globalCfg.module_layout)) } catch { /* storage full */ }
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

  // ── Init: load advanced config (chunking/pipeline defaults) ─────────
  useEffect(() => {
    if (!isConnected) return
    api.getAdvancedConfig().then(setGlobalAdvanced).catch(() => { })
  }, [api, isConnected])

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
    projectStatus, projectStatusUnreachable, selectedProject, selectedProjectId, projectConfig, isPro, limitReached: isOverProjectLimit,
    inactive: selectedProject?.config?.active === false || selectedProject?.activity_status === 'inactive' || selectedProject?.activity_status === 'locked',
    scopeStatus: selectedProjectId ? scopeEvents[selectedProjectId] : undefined,
    logs, clearLogs, findActiveTask, handleBuild,
    transientComplete: selectedProjectId ? transientCompleteProjects.has(selectedProjectId) : false,
    gateState, vendorScan,
    handleGate1FixFirst, handleGate1ForceExclude, handleGate1Continue,
    onOpenDeepSettings: () => { openSettingsAt('deep-analysis') },
    onOpenSettings: () => { openSettingsAt(selectedProjectId ? 'sources' : 'appearance') },
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
      fastCurrentStage,
      deepCurrentStage,
      fastSyncPhase,
      deepEnrichmentPhase,
      finalizePhase,
      refreshStageDataFromPipeline,
      // Phase 117: scoped rebuild + stop handlers
      triggerRebuild,
      stopRebuild,
    },
    llm: {
      llmConfig, llmSlotsStatus,
      handleLLMConfigChange, handleAddEndpoint, handleEditEndpoint, handleDeleteEndpoint,
      handleTestEndpoint, handleFetchModels, handleFetchCloudModels, handleTestModel, handleClearTestResult, handleDownloadModel,
      handleModeApply,
      availableModels, modelDetails, loadingModels, testingSlot, testResults,
      cloudModels, loadingCloudModels,
      maxActiveProjects, onMaxActiveProjectsChange: handleMaxActiveProjectsChange,
      schedulerStatus,
      computeNodes,
      onComputeNodeAdd: handleComputeNodeAdd,
      onComputeNodeUpdate: handleComputeNodeUpdate,
      onComputeNodeDelete: handleComputeNodeDelete,
      onEndpointNodeChange: handleEndpointNodeChange,
    },
    deepAnalysis: { deepAnalysisSchedule, setDeepAnalysisSchedule, budgetUsage, tokenUsageData },
    atlas: {
      atlasStatus: atlasStatus
        ? ({
            ...atlasStatus,
            progress_current: pipelineAtlasStatus?.progress_current ?? atlasStatus.progress_current,
            progress_total: pipelineAtlasStatus?.progress_total ?? atlasStatus.progress_total,
            progress_baseline: pipelineAtlasStatus?.progress_baseline ?? atlasStatus.progress_baseline,
          } as typeof atlasStatus)
        : (pipelineAtlasStatus as typeof atlasStatus | null),
    },
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
        const a = document.createElement('a'); a.href = url; a.download = 'prep-security-report.json'; a.click()
        URL.revokeObjectURL(url)
      }).catch(() => { })
    },
    onExportAuditLog: () => {
      api.exportAuditLog('csv').then((data: any) => {
        const content = data.content || JSON.stringify(data, null, 2)
        const blob = new Blob([content], { type: data.format === 'csv' ? 'text/csv' : 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = `prep-audit-log.${data.format || 'json'}`; a.click()
        URL.revokeObjectURL(url)
      }).catch(() => { })
    },
  })

  // Pipeline-running signal used by the Settings Danger Zone (legacy drawer
  // and v2 overlay both consume this to disable Recover-from-Snapshot
  // during active runs). Extracted so both code paths see the same value.
  const settingsPipelineRunning =
    inferredEdgesRunning || augmenting || validating || epistemicRunning ||
    groupReasoningRunning || clusterRunning || atlasRunning || deepeningRunning ||
    fastKnowledgeBuilding || deepKnowledgeBuilding

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
            onClick={() => openSettingsAt('license')}
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
          Connection to SourcePrep daemon lost. Attempting to reconnect...
        </div>
      )}
      <SettingsOverlay
        renderPage={(page) => renderSettingsPage(page, {
          globalConfig,
          activeProjectId: selectedProjectId,
          projectName: selectedProject?.name ?? null,
          projectConfigTyped: selectedProjectId ? projectConfig : null,
          projectSaving,
          onProjectChange: handleProjectConfigChange,
          onDetectStack: selectedProjectId ? handleDetectStack : undefined,
          deepAnalysisSchedule,
          onDeepAnalysisScheduleChange: handleSyncedDeepAnalysisScheduleChange,
          largeModelConfigured: !!(llmConfig.large_model?.endpoint_id && llmConfig.large_model?.model),
          fastModelConfigured: !!(llmConfig.small_model?.endpoint_id && llmConfig.small_model?.model),
          pipelineRunning: settingsPipelineRunning,
          // Phase 117b: scoped danger-zone actions. Rebuild routes through
          // useEnrichment.triggerRebuild for sync/enrichment scopes (Phase 117);
          // 'all' falls through to handleRebuildPipeline (full /pipeline/rebuild).
          // Reset dispatches to the existing destroy handlers by scope.
          onRebuildScoped: (scope) => {
            if (scope === 'all') {
              void handleRebuildPipeline();
            } else {
              void triggerRebuild(scope);
            }
          },
          onResetScoped: (scope) => {
            if (scope === 'all') {
              void handleDestroyIndex();
            } else if (scope === 'enrichment') {
              void handleDestroyEnrichmentFull();
            } else if (scope === 'code-index') {
              void handleDestroyCodeIndex();
            } else {
              void handleDestroyFinalizeFull();
            }
          },
          uiMode,
          onModeChange: setUiMode,
          uiTheme,
          onThemeChange: setUiTheme,
          bgImage,
          onBgImageChange: setBgImage,
          globalAdvanced,
          onGlobalAdvancedChange: handleGlobalAdvancedChange,
          maxActiveProjects,
          onMaxActiveProjectsChange: handleMaxActiveProjectsChange,
          licenseStatus,
          licenseKeyInput,
          onLicenseKeyInputChange: setLicenseKeyInput,
          onActivateLicense: handleActivateLicense,
          onDeactivateLicense: handleDeactivateLicense,
          licenseLoading,
          licenseError,
          devTierOverride,
          onOpenAiGateway: handleOpenAiGateway,
          onGlobalConfigChange: handleGlobalConfigChange,
          onDevTierOverrideChange: handleDevTierOverrideChange,
          devRoleOverride,
          onDevRoleOverrideChange: handleDevRoleOverrideChange,
          onDestroyAtlas: handleDestroyAtlas,
          onDestroyGroupReasoning: handleDestroyGroupReasoning,
          onDestroyDeepEnrichment: handleDestroyDeepEnrichment,
        })}
        projectName={selectedProject?.name ?? null}
      />
      {/* Floating Settings trigger — always visible; overlay (z-[110]) masks it when open. */}
      <Button
        variant="outline"
        size="icon"
        onClick={() => openSettingsAt(selectedProjectId ? 'sources' : 'appearance')}
        title="Settings"
        className="fixed bottom-4 right-4 z-40 shadow-lg bg-surface hover:bg-surface-raised"
      >
        <Settings className="w-5 h-5" />
      </Button>
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
                projects={projectSummaries}
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
            {projectStatus?.sync && (
              <SyncStatusCard
                status={projectStatus.sync}
                onSyncNow={async () => {
                  if (!selectedProjectId) return
                  try {
                    await api.syncNow(selectedProjectId)
                  } catch (e) {
                    console.error('Sync now failed', e)
                  }
                  // status refreshes on the next /status poll
                }}
              />
            )}
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
        onUpgrade={() => { setAddModalOpen(false); openSettingsAt('license') }}
      />
    </>
  )
}

export default App
