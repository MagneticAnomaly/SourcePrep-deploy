import { useMemo, useState, useCallback, useEffect } from 'react'
import { useApiClient, useScopes } from '@prep/ui'
import type { ScopeRecord } from '@prep/ui'
import { usePipelineHealth } from './usePipelineHealth'
import type { UseGoalpostsSystemReturn } from './useGoalpostsSystem'
import type { UseRoadmapSystemReturn } from './useRoadmapSystem'
import { FileText } from 'lucide-react'
import { AtlasLensContainer } from '../components/AtlasLensContainer'
import {
  IndexStatusCard,
  SearchPanel,
  UsageGuidePanel,
  ContextOptionsPanel,
  SearchResultsList,
  ChunkPreview,
  ContextOutput,

  AIModelsSettings,
  DeepAnalysisSettings,
  TraceExplorer,
  GraphEnrichmentPipeline,
  GraphStructurePanel,
  FolderTreePanel,
  AgentOpsPanel,
  type AgentOpsData,
  type MCPStatusData,
  type MCPInstallResult,
  FileExplorerDetail,
  CopyButton,
  LogConsole,
  IndexHealthPanel,
  TokenBudgetPanel,
  ActivityHeatmap,
  AuditPanel,
  SpaghettiFinderPanel,
  HealthScannerPanel,
  EnterpriseAdminPanel,
  type ActivityHeatmapData,
  PANEL_REGISTRY,
  type SearchResult,
  type ContextMeta,
  type ProjectConfig,
  type ProjectStatus,
  type ProjectListItem,
  type TreeNode,
  type PinnedTextFile,
  type DeepAnalysisSchedule,
  type InferredEdgesStatus,
  type AugmentationStatus,
  type EpistemicStatus,
  type ModuleStatus,
  type DeepeningStatus,
  type KnowledgeEmbeddingStatus,
  type EnrichmentAutoConfig,
  type LLMConfig,
  type LLMSlotsStatus,
  type SavedEndpoint,
  type EndpointTestResult,
  type ScopeStatus,
  type TokenBudgetData,
  type AtlasStatus,
  type RulesStatus,
  type ConceptsStatus,
  type AuditPipelineStatus,
  type AntibodiesStatus,
  GoalpostsPanel,
  AdvisorPanel,
  RoadmapPanel,
  OpportunitiesPanel,
  ArchitectureDiagramPanel,
  ArchitectureDiagramDetail,
  ConceptsPanel,
  ConceptsDetail,
  PanelLoading,
} from '@prep/ui'
import type { TraceStatus, TraceCoverage } from './useTraceSystem'
import type { UseAuditSystemReturn } from './useAuditSystem'
import type { UseSpaghettiSystemReturn } from './useSpaghettiSystem'
import type { UseOpportunitiesSystemReturn } from './useOpportunitiesSystem'
import type { UseArchitectureSystemReturn } from './useArchitectureSystem'
import type { UseConceptSystemReturn } from './useConceptSystem'

const PINNED_PREFIX = 'pinned:'

// Mirror of src/prep/core/repo_profile.py DEFAULT_EXCLUDE_FILE_GLOBS.
// Files matching these patterns render in the Scope tree as "always-ignored"
// (strikethrough, no include/exclude icons) because they're AI-assistant rule
// files that should stay available to agents but out of the index.
const DEFAULT_ALWAYS_IGNORED_GLOBS: string[] = [
  '**/AGENTS.md',
  '**/CLAUDE.md',
  '**/.cursor/rules/*.mdc',
  '**/.cursorrules',
  '**/.windsurfrules',
  '**/.windsurf/rules/*.md',
  '**/.github/copilot-instructions.md',
  '**/GEMINI.md',
  '**/.clinerules',
  '**/.roorules',
  '**/.qwencoderules',
]

// ── Sub-interfaces (grouped by domain hook) ──────────────────

export interface PanelSearchProps {
  query: string
  setQuery: (q: string) => void
  searchK: number
  setSearchK: (k: number) => void
  minScore: number
  setMinScore: (s: number) => void
  searchLoading: boolean
  searchResults: SearchResult[]
  selectedChunk: SearchResult | null
  setSelectedChunk: (c: SearchResult | null) => void
  handleSearch: () => void
  contextK: number
  setContextK: (k: number) => void
  contextMaxChars: number
  setContextMaxChars: (n: number) => void
  contextIncludeSources: boolean
  setContextIncludeSources: (b: boolean) => void
  contextIncludeScores: boolean
  setContextIncludeScores: (b: boolean) => void
  contextStructured: boolean
  setContextStructured: (b: boolean) => void
  contextIncludeAtlas: boolean
  setContextIncludeAtlas: (b: boolean) => void
  context: string
  contextMeta: ContextMeta | null
  handleGetContext: () => void
  handleCopyContext: () => void
}

export interface PanelFileSystemProps {
  fileTree: TreeNode[]
  includedPaths: Set<string>
  handleToggleInclude: (paths: string[], action: 'add' | 'remove') => void
  pathWeights: Record<string, number>
  handlePathWeightChange: (path: string, weight: number | null) => void
  handleLoadChildren: (path: string) => Promise<TreeNode[]>
  pinnedPaths: Set<string>
  pinnedFiles: PinnedTextFile[]
  handlePinFile: (path: string) => void
  handleUnpinFile: (path: string) => void
  handleLoadFileContent: (path: string) => Promise<string>
}

export interface PanelTraceProps {
  traceStatus: TraceStatus
  traceCoverage: TraceCoverage
  projectLoading: boolean
  indexAutoRebuild: boolean
  handleIndexAutoRebuildChange: (auto: boolean) => void
  enrichmentAutoConfig: EnrichmentAutoConfig
  handleEnrichmentAutoConfigChange: (config: EnrichmentAutoConfig) => void
  handleSearchTrace: (query: string, kinds?: string[], limit?: number) => Promise<any>
  handleGetTraceNode: (nodeId: string) => Promise<any>
  handleGetTraceNeighbors: (nodeId: string, direction?: string) => Promise<any>
  handleBuildTrace: () => void
  handleEnableTrace: () => void
  handleTraceAll: () => void
  handleRetraceStale: () => void
  handleAddExcludePattern: (pattern: string | string[]) => void
  handleRemoveExcludePattern: (pattern: string | string[]) => void
  fetchTraceCoverage: () => void
  handleRunFastSync: () => void
}

export interface PanelEnrichmentProps {
  pipelineProvenance: import('@prep/ui').PipelineProvenance | null
  inferredEdgesStatus: InferredEdgesStatus
  inferredEdgesRunning: boolean
  augmentationStatus: AugmentationStatus
  augmenting: boolean
  validating: boolean
  handleRunAugmentation: () => void
  epistemicStatus: EpistemicStatus
  epistemicRunning: boolean
  handleRunEpistemic: () => void
  groupReasoningRunning: boolean
  moduleStatus: ModuleStatus
  clusterRunning: boolean
  handleRunModuleSynthesis: () => void
  atlasRunning: boolean
  deepeningStatus: DeepeningStatus
  deepeningRunning: boolean
  handleRunDeepening: () => void
  knowledgeStatus: KnowledgeEmbeddingStatus
  deepKnowledgeStatus: KnowledgeEmbeddingStatus
  fastKnowledgeBuilding: boolean
  deepKnowledgeBuilding: boolean
  handleRunKnowledgeBuild: () => void
  handleRunDeepEnrichment: () => void
  handleRunFinalize: () => void
  handlePausePipeline: (group: 'fast_sync' | 'deep_enrichment' | 'finalize') => void
  handleResumePipeline: (group: 'fast_sync' | 'deep_enrichment' | 'finalize') => void
  fastPaused: boolean
  deepPaused: boolean
  finalizePaused: boolean
  /** Explicit stage ID where fast sync was paused (from backend SSE) */
  fastPausedStage?: string
  /** Explicit stage ID where deep enrichment was paused (from backend SSE) */
  deepPausedStage?: string
  /** Explicit stage ID where finalize was paused (from backend SSE) */
  finalizePausedStage?: string
  /** F-58: whether the finalize group is actively running */
  finalizeRunning?: boolean
  /** F-58: which finalize stage is currently active */
  finalizeCurrentStage?: string
  rulesStatus?: RulesStatus
  conceptsStatus?: ConceptsStatus
  auditPipelineStatus?: AuditPipelineStatus
  antibodiesStatus?: AntibodiesStatus
  groupReasoningStatus: { enabled: boolean; group_count: number; analyzed: number; running?: boolean; slot_phase?: string; progress_current?: number; progress_total?: number }
  /** Phase 98: collapse state for pipeline stage groups */
  fastCollapsed?: boolean;
  deepCollapsed?: boolean;
  finalizeCollapsed?: boolean;
  onToggleGroupCollapsed?: (group: 'fast' | 'deep' | 'finalize') => void;
  /** Phase 114: called after a per-stage restore so the panel can repaint stage status immediately. */
  refreshStageDataFromPipeline?: () => Promise<void> | void;
  /** Phase 117: trigger a scoped rebuild (sync / enrichment / all). */
  triggerRebuild: (scope: import('@prep/ui').RebuildScope) => Promise<void>;
  /** Phase 117: stop the in-flight rebuild. */
  stopRebuild: () => Promise<void>;
}

export interface PanelLLMProps {
  llmConfig: LLMConfig
  llmSlotsStatus: LLMSlotsStatus | null
  handleLLMConfigChange: (config: LLMConfig) => void
  handleAddEndpoint: (ep: Omit<SavedEndpoint, 'id'>) => void
  handleEditEndpoint: (ep: SavedEndpoint) => void
  handleDeleteEndpoint: (id: string) => void
  handleTestEndpoint: (ep: SavedEndpoint) => Promise<any>
  handleFetchModels: (endpointId: string) => Promise<any>
  handleTestModel: (slot: 'embedding' | 'small' | 'large' | 'code' | 'coordinator') => Promise<any>
  handleClearTestResult: (slot: string) => void
  handleDownloadModel: (slot: 'embedding') => Promise<void>
  availableModels: Record<string, string[]>
  modelDetails: Record<string, Array<{ name: string; context_window?: string; cost_tier?: string; rate_limits?: { rpd?: number; rpm?: number }; batch_estimate?: { files_per_request: number; daily_file_capacity?: number } }>>
  loadingModels: Record<string, boolean>
  testingSlot: 'small' | 'embedding' | 'large' | 'code' | 'coordinator' | null
  testResults: Record<string, EndpointTestResult>
  // Compute settings (Phase 45)
  maxActiveProjects?: number | 'infinite'
  onMaxActiveProjectsChange?: (val: number | 'infinite') => void
  schedulerStatus?: { nodes: Record<string, { max_concurrent: number; current_load: number; active: Record<string, string>; queued: Array<{ project_id: string; stage: string; waiting_seconds: number }> }> } | null
  // Compute node CRUD (Phase 45D)
  computeNodes?: import('@prep/ui').ComputeNode[]
  onComputeNodeAdd?: (node: Omit<import('@prep/ui').ComputeNode, 'id'>) => void
  onComputeNodeUpdate?: (nodeId: string, updates: Partial<import('@prep/ui').ComputeNode>) => void
  onComputeNodeDelete?: (nodeId: string) => void
  onEndpointNodeChange?: (endpointId: string, nodeId: string | null) => void
  handleModeApply?: (mode: import('@prep/ui').AssignmentMode, blocks?: import('@prep/ui').LLMConfig['assignment_blocks']) => Promise<void>
}

export interface PanelDeepAnalysisProps {
  deepAnalysisSchedule: DeepAnalysisSchedule
  setDeepAnalysisSchedule: (s: DeepAnalysisSchedule | ((prev: DeepAnalysisSchedule) => DeepAnalysisSchedule)) => void
  budgetUsage: TokenBudgetData | null
  tokenUsageData: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }> | null
}

export interface PanelAtlasProps {
  atlasStatus: AtlasStatus | null
}

// ── Main interface ────────────────────────────────────────────

export interface DashboardPanelsProps {
  // Cross-cutting
  projectStatus: ProjectStatus | null
  /** True when /status has failed repeatedly — IndexStatusCard renders a "stats stale" indicator */
  projectStatusUnreachable?: boolean
  selectedProject: ProjectListItem | null
  selectedProjectId: string | null
  projectConfig: ProjectConfig
  isPro: boolean
  limitReached?: boolean
  inactive?: boolean
  scopeStatus?: ScopeStatus
  logs: any[]
  clearLogs: () => void
  findActiveTask: (type: 'index_build' | 'trace_build') => any
  handleBuild: () => void
  transientComplete: boolean
  /** Open settings drawer to the Deep Enrichment section */
  onOpenDeepSettings?: () => void
  /** Open settings drawer (generic — used for upgrade CTAs) */
  onOpenSettings?: () => void
  /** Open detail overlay for a specific panel */
  onOpenDetails?: (panelId: string) => void
  showDevPanels?: boolean
  /**
   * Phase 114 T15: whether the `trace-pipeline` dashboard panel is
   * currently visible. Used to gate `usePipelineHealth`'s 10s poll so the
   * health endpoint isn't hit when the user has that panel closed.
   * Defaults to `true` (always poll) when undefined — preserves backward
   * compatibility with callers that haven't threaded visibility yet.
   */
  tracePipelinePanelVisible?: boolean
  // Domain groups
  search: PanelSearchProps
  files: PanelFileSystemProps
  trace: PanelTraceProps
  enrichment: PanelEnrichmentProps
  llm: PanelLLMProps
  deepAnalysis: PanelDeepAnalysisProps
  atlas: PanelAtlasProps
  audit: UseAuditSystemReturn
  spaghetti: UseSpaghettiSystemReturn
  goalposts: UseGoalpostsSystemReturn
  roadmap: UseRoadmapSystemReturn
  opportunities: UseOpportunitiesSystemReturn
  architecture: UseArchitectureSystemReturn
  concepts: UseConceptSystemReturn
  activityData: ActivityHeatmapData | null
  // Enterprise
  adminPolicy?: import('@prep/ui').AdminPolicy | null
  seatStatus?: any | null
  onProvisionSeat?: (email: string) => Promise<{ provisioned: boolean; message: string }>
  // Admin Security (EA-I)
  securityHealth?: import('@prep/ui').SecurityHealthResult | null
  securityEvents?: Array<{ timestamp: number; event_type: string; severity: string; message: string }>
  onExportSecurityReport?: () => void
  onExportAuditLog?: () => void
}

/** Builds all dashboard panel content, detail views, and dynamic panel definitions from domain state. */
export function useDashboardPanels(props: DashboardPanelsProps) {
  // Flatten grouped sub-objects for backward-compatible p.xxx access internally
  const { search, files, trace, enrichment, llm, deepAnalysis, atlas, audit: auditProps, spaghetti: spaghettiProps, goalposts: goalpostsProps, roadmap: roadmapProps, opportunities: opportunitiesProps, architecture: archProps, concepts: conceptsProps, ...core } = props
  const p = { ...core, ...search, ...files, ...trace, ...enrichment, ...llm, ...deepAnalysis }

  // ── Pipeline health polling (Phase 114) ──────────────────────
  // T15: gate polling on trace-pipeline panel visibility. Default to true
  // for the (now rare) callers that don't thread visibility, which matches
  // useEnrichment's backward-compat default.
  const apiClient = useApiClient()
  // ── Named Scopes (Phase 120) ─────────────────────────────────
  const scopes = useScopes(p.selectedProjectId, apiClient)
  const [activeScopeRecord, setActiveScopeRecord] = useState<ScopeRecord | null>(null)
  useEffect(() => {
    if (scopes.activeScopeId === 'global' || !p.selectedProjectId) {
      setActiveScopeRecord(null)
      return
    }
    void apiClient.getScope(p.selectedProjectId, scopes.activeScopeId)
      .then(setActiveScopeRecord)
      .catch(() => setActiveScopeRecord(null))
  }, [scopes.activeScopeId, p.selectedProjectId, apiClient])
  const scopeIncludedPaths = scopes.activeScopeId === 'global'
    ? p.includedPaths
    : new Set(activeScopeRecord?.paths ?? [])
  const { health, refetch: refetchHealth, clearBarrier } = usePipelineHealth(
    p.selectedProjectId,
    p.tracePipelinePanelVisible ?? true,
  )

  const handleStageRestored = useCallback((_stageId: string, _snapshotId: string) => {
    // Phase 114: after a per-stage restore, repaint both health AND stage status.
    // Health alone isn't enough — the user needs to see the stage's enrichment
    // counters swap to the restored snapshot's values immediately, not after the
    // next 1s poll tick.
    void refetchHealth()
    void p.refreshStageDataFromPipeline?.()
  }, [refetchHealth, p])

  // Agent ops state — fetched when project changes
  const mapAgentStatus = (raw: any): AgentOpsData => ({
    hr: { last_run: raw.hr?.roles?.length > 0 ? `${raw.hr.role_count} roles` : null, push_count: 0 },
    researcher: { last_run: raw.researcher?.latest_run ?? null, push_count: 0 },
    custodian: { last_run: raw.custodian?.archive_count > 0 ? `${raw.custodian.archive_count} archived` : null, push_count: 0 },
  })
  const [agentOpsData, setAgentOpsData] = useState<AgentOpsData | null>(null)
  const [agentOpsLoading, setAgentOpsLoading] = useState(false)
  const [pushSettings, setPushSettings] = useState<{ auto_push: boolean; min_significance: 'all' | 'recommended' | 'mandatory'; paperclip_project: string }>({ auto_push: false, min_significance: 'recommended', paperclip_project: '' })

  useEffect(() => {
    setAgentOpsData(null)
    if (!p.selectedProjectId) return
    setAgentOpsLoading(true)
    fetch(`/projects/${p.selectedProjectId}/agents/status`)
      .then(r => r.json())
      .then(json => setAgentOpsData(mapAgentStatus(json.data ?? json)))
      .catch(() => {})
      .finally(() => setAgentOpsLoading(false))
  }, [p.selectedProjectId])

  // Paperclip skill status — global (not per-workspace)
  const [mcpStatus, setMcpStatus] = useState<MCPStatusData | null>(null)

  const fetchMcpStatus = useCallback(() => {
    fetch('/paperclip/skill-status')
      .then(r => r.json())
      .then(json => setMcpStatus(json.data ?? json))
      .catch(() => {})
  }, [])

  useEffect(() => { fetchMcpStatus() }, [fetchMcpStatus])

  const handleMCPInstall = useCallback(async (): Promise<MCPInstallResult> => {
    const res = await fetch('/paperclip/install-skill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'symlink' }),
    })
    const json = await res.json()
    return json.data ?? json
  }, [])

  const handleMCPUninstall = useCallback(async (): Promise<void> => {
    await fetch('/paperclip/uninstall-skill', {
      method: 'POST',
    })
  }, [])

  // Optimistic local state for excluded paths — updates INSTANTLY on click.
  // Seeded from trace coverage when it arrives, but local clicks are immediate.
  const [localExcludedPaths, setLocalExcludedPaths] = useState<Set<string>>(new Set())

  // Reset local state when switching projects to avoid cross-contamination
  useEffect(() => {
    setLocalExcludedPaths(new Set())
  }, [p.selectedProject?.id])

  // Hydrate excluded paths from persisted ignore_patterns on project load.
  // When users click a folder in the Exclude Tree, handleToggleExclude saves
  // both the folder path (e.g. "tests/eval") and a glob (e.g. "tests/eval/**").
  // On restart/reload, we read these patterns back and extract the folder-level
  // entries (patterns that DON'T end in "/**") so the FolderTree checkboxes
  // render correctly.
  const persistedIgnorePatterns = p.projectConfig?.trace?.ignore_patterns
  // Stable key for the effect's dependency array. Using `.length` would miss
  // pattern swaps of the same cardinality (e.g. replace "a" with "b").
  const ignorePatternKey = persistedIgnorePatterns?.join('|') ?? ''
  useEffect(() => {
    if (!persistedIgnorePatterns || persistedIgnorePatterns.length === 0) return
    setLocalExcludedPaths(prev => {
      const merged = new Set(prev)
      for (const pattern of persistedIgnorePatterns) {
        // Skip glob-only patterns (e.g. "tests/eval/**") — the tree only
        // needs the folder path itself (e.g. "tests/eval")
        if (pattern.endsWith('/**')) continue
        // Skip patterns with wildcards (these are glob patterns, not folder paths)
        if (pattern.includes('*') || pattern.includes('?')) continue
        // Clean trailing slashes
        const clean = pattern.replace(/\/$/, '')
        if (clean) merged.add(clean)
      }
      if (merged.size === prev.size) return prev
      return merged
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.selectedProject?.id, ignorePatternKey])

  // Sync server-side excluded paths into local state (additive merge)
  useEffect(() => {
    if (p.traceCoverage?.excluded) {
      setLocalExcludedPaths(prev => {
        const merged = new Set(prev)
        for (const f of p.traceCoverage!.excluded!) {
          merged.add(f.path)
        }
        // Only update if the set actually changed
        if (merged.size === prev.size) return prev
        return merged
      })
    }
  }, [p.traceCoverage?.excluded])

  // Toggle exclude: mirrors the Knowledge Sources selection model exactly.
  // - Add folder: adds folder path, removes descendant paths (parent covers them)
  // - Remove child within selected parent: "explodes" the ancestor by removing it
  //   and re-adding all sibling paths, then removing the target child.
  const handleToggleExclude = useCallback(
    (paths: string[], action: 'add' | 'remove') => {
      // Helper: walk the fileTree to find sibling paths to preserve when
      // "exploding" an ancestor selection (identical to Knowledge Sources logic)
      function getExplodedPaths(ancestorPath: string, targetPath: string): string[] {
        const tree = p.fileTree
        const ancestorParts = ancestorPath.split('/')
        const targetParts = targetPath.split('/')
        let currentNodes = tree
        for (const part of ancestorParts) {
          const node = currentNodes.find((n: { name: string }) => n.name === part)
          if (!node || !node.children) return []
          currentNodes = node.children
        }
        const relativeParts = targetParts.slice(ancestorParts.length)
        const result: string[] = []
        let currentBasePath = ancestorPath
        for (const part of relativeParts) {
          for (const child of currentNodes) {
            if (child.name !== part && child.status !== 'ignored') {
              result.push(`${currentBasePath}/${child.name}`)
            }
          }
          const nextNode = currentNodes.find((n: { name: string }) => n.name === part)
          if (!nextNode || !nextNode.children) break
          currentNodes = nextNode.children
          currentBasePath = `${currentBasePath}/${part}`
        }
        return result
      }

      // 1. Optimistic UI update — instant red/strikethrough
      setLocalExcludedPaths(prev => {
        const next = new Set(prev)
        for (const rawPath of paths) {
          const cleanPath = rawPath.replace(/\/$/, '')
          if (action === 'add') {
            // Add the path
            next.add(cleanPath)
            // Remove any existing descendants (parent covers them)
            const prefix = cleanPath + '/'
            for (const existing of prev) {
              if (existing.startsWith(prefix)) {
                next.delete(existing)
              }
            }
          } else {
            // Check if an ancestor is selected (need to "explode" it)
            let ancestorFound: string | null = null
            const parts = cleanPath.split('/')
            for (let i = parts.length - 1; i >= 1; i--) {
              const ancestor = parts.slice(0, i).join('/')
              if (next.has(ancestor)) {
                ancestorFound = ancestor
                break
              }
            }
            if (ancestorFound) {
              // Remove ancestor, re-add siblings to preserve them
              next.delete(ancestorFound)
              const siblingsToKeep = getExplodedPaths(ancestorFound, cleanPath)
              siblingsToKeep.forEach(s => next.add(s))
            }
            // Remove the path itself
            next.delete(cleanPath)
            // Remove any descendants
            const prefix = cleanPath + '/'
            for (const existing of prev) {
              if (existing.startsWith(prefix)) {
                next.delete(existing)
              }
            }
          }
        }
        return next
      })

      // 2. Fire a SINGLE API call with all patterns for this toggle.
      // We must not issue one POST per pattern — the /trace/ignore
      // endpoint does read-modify-write on the project config, so
      // concurrent POSTs race and the second write clobbers the first,
      // causing "exclude vanishes after refresh".
      const addBatch: string[] = []
      const removeBatch: string[] = []
      for (const rawPath of paths) {
        const cleanPath = rawPath.replace(/\/$/, '')
        const bucket = action === 'add' ? addBatch : removeBatch
        bucket.push(cleanPath)
        bucket.push(`${cleanPath}/**`)
      }
      if (addBatch.length > 0) p.handleAddExcludePattern(addBatch)
      if (removeBatch.length > 0) p.handleRemoveExcludePattern(removeBatch)
    },
    [p.handleAddExcludePattern, p.handleRemoveExcludePattern, p.fileTree]
  )

  // Use local optimistic state as the source of truth for the UI
  const excludedPaths = localExcludedPaths

  // Phase 119 Phase A: Live AI Gateway view shared between the in-grid
  // `llm-status` panel and the expand-arrow detail overlay. Mounting the
  // full AIModelsSettings (endpoint cards + Plan dropdown + integer Cloud
  // Models for Ollama) means clicking the sidebar expand-arrow lands the
  // user on their endpoint config without a Settings detour.
  const aiModelsSettingsView = (
    <AIModelsSettings
      config={p.llmConfig}
      onConfigChange={p.handleLLMConfigChange}
      onAddEndpoint={p.handleAddEndpoint}
      onEditEndpoint={p.handleEditEndpoint}
      onDeleteEndpoint={p.handleDeleteEndpoint}
      onTestEndpoint={p.handleTestEndpoint}
      onFetchModels={p.handleFetchModels}
      onTestModel={p.handleTestModel}
      onClearTestResult={p.handleClearTestResult}
      onHFDownload={p.handleDownloadModel}
      availableModels={p.availableModels}
      modelDetails={p.modelDetails}
      loadingModels={p.loadingModels}
      testingSlot={p.testingSlot}
      testResults={p.testResults}
      maxActiveProjects={p.maxActiveProjects}
      onMaxActiveProjectsChange={p.onMaxActiveProjectsChange}
      schedulerStatus={p.schedulerStatus}
      computeNodes={p.computeNodes}
      onComputeNodeAdd={p.onComputeNodeAdd}
      onComputeNodeUpdate={p.onComputeNodeUpdate}
      onComputeNodeDelete={p.onComputeNodeDelete}
      onEndpointNodeChange={p.onEndpointNodeChange}
      onModeApply={p.handleModeApply}
      onAssignmentBlockAdd={() => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: [
            ...(p.llmConfig.assignment_blocks || []),
            { id: `block-${Date.now()}`, endpoint_id: '', model: '', tasks: [] },
          ],
        });
      }}
      onAssignmentBlockDelete={(blockId) => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: (p.llmConfig.assignment_blocks || []).filter((b) => b.id !== blockId),
        });
      }}
      onAssignmentBlockEndpointChange={(blockId, endpointId) => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: (p.llmConfig.assignment_blocks || []).map((b) =>
            b.id === blockId ? { ...b, endpoint_id: endpointId, model: '' } : b
          ),
        });
      }}
      onAssignmentBlockModelChange={(blockId, model) => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: (p.llmConfig.assignment_blocks || []).map((b) =>
            b.id === blockId ? { ...b, model } : b
          ),
        });
      }}
      onAssignmentBlockAddTask={(blockId, taskId) => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: (p.llmConfig.assignment_blocks || []).map((b) =>
            b.id === blockId ? { ...b, tasks: [...b.tasks, taskId] } : b
          ),
        });
      }}
      onAssignmentBlockRemoveTask={(blockId, taskId) => {
        p.handleLLMConfigChange({
          ...p.llmConfig,
          assignment_blocks: (p.llmConfig.assignment_blocks || []).map((b) =>
            b.id === blockId ? { ...b, tasks: b.tasks.filter((t) => t !== taskId) } : b
          ),
        });
      }}
      onAssignmentBlockTest={async (blockId) => {
        // Simplified testing for mapped blocks using existing handleTestEndpoint logic
        const block = p.llmConfig.assignment_blocks?.find(b => b.id === blockId);
        if (!block) return { success: false, message: 'Block not found' };
        const ep = p.llmConfig.saved_endpoints?.find(e => e.id === block.endpoint_id);
        if (!ep) return { success: false, message: 'Endpoint not found' };
        return p.handleTestEndpoint(ep);
      }}
      baseUrl={apiClient.baseUrl}
    />
  )

  const panelContent = useMemo(() => ({
    'log-console': (
      <LogConsole
        logs={p.logs}
        onClear={p.clearLogs}
        className="h-full border-none shadow-none bg-transparent"
        defaultExpanded={true}
        diagnosticData={{
          license_tier: p.isPro ? 'pro+' : 'free',
          project: p.selectedProject ? {
            id: p.selectedProject.id,
            name: p.selectedProject.name,
            path: p.selectedProject.path,
            mode: p.selectedProject.mode,
          } : null,
          project_status: p.projectStatus ? {
            building: p.projectStatus.building,
            stale: p.projectStatus.stale,
            stale_since: p.projectStatus.stale_since,
            stale_count: p.projectStatus.stale_count,
            index: p.projectStatus.index,
            trace: p.projectStatus.trace,
            watch: p.projectStatus.watch,
          } : null,
          project_config: {
            include_globs: p.projectConfig.include_globs,
            exclude_globs: p.projectConfig.exclude_globs,
            max_file_bytes: p.projectConfig.max_file_bytes,
            use_gitignore: p.projectConfig.use_gitignore,
            trace: p.projectConfig.trace,
            auto_rebuild: p.projectConfig.auto_rebuild,
          },
          trace_status: p.traceStatus ?? null,
          trace_coverage: p.traceCoverage ?? null,
          scope_status: p.scopeStatus ?? null,
          index_auto_rebuild: p.indexAutoRebuild,
          enrichment_auto_config: p.enrichmentAutoConfig ?? null,
          enrichment: {
            inferred_edges: p.inferredEdgesStatus,
            inferred_edges_running: p.inferredEdgesRunning,
            augmentation: p.augmentationStatus,
            augmenting: p.augmenting,
            validating: p.validating,
            epistemic: p.epistemicStatus,
            epistemic_running: p.epistemicRunning,
            modules: p.moduleStatus,
            cluster_running: p.clusterRunning,
            atlas_running: p.atlasRunning,
            deepening: p.deepeningStatus,
            deepening_running: p.deepeningRunning,
            knowledge: p.knowledgeStatus,
            fast_knowledge_building: p.fastKnowledgeBuilding,
            deep_knowledge_building: p.deepKnowledgeBuilding,
          },
          llm_config: {
            embedding: p.llmConfig.embedding,
            small_model: p.llmConfig.small_model ? {
              endpoint_id: p.llmConfig.small_model.endpoint_id,
              model: p.llmConfig.small_model.model,
            } : null,
            large_model: p.llmConfig.large_model ? {
              endpoint_id: p.llmConfig.large_model.endpoint_id,
              model: p.llmConfig.large_model.model,
            } : null,
            saved_endpoints: p.llmConfig.saved_endpoints?.map((ep: SavedEndpoint) => ({
              id: ep.id, name: ep.name, provider: ep.provider, url: ep.url,
            })),
          },
          llm_slots_status: p.llmSlotsStatus ?? null,
          deep_analysis_schedule: p.deepAnalysisSchedule ?? null,
          active_tasks: {
            index_build: p.findActiveTask('index_build') ?? null,
            trace_build: p.findActiveTask('trace_build') ?? null,
          },
          transient_complete: p.transientComplete,
        }}
      />
    ),
    'usage-guide': (
      <UsageGuidePanel bare />
    ),
    status: (
      <IndexStatusCard
        stats={p.projectStatus ? {
          loaded: p.projectStatus.index.exists,
          index_dir: p.selectedProject?.path,
          total_documents: p.projectStatus.index.total_chunks,
          model: p.projectStatus.index.embedding_model,
          built_at: p.projectStatus.index.last_build_at ?? undefined,
          embedding_dim: p.projectStatus.index.embedding_dim,
          build: p.projectStatus.index.build,
        } : {
          loaded: false,
          total_documents: 0,
          embedding_dim: 0,
          model: 'Unknown',
          built_at: undefined,
          build: undefined,
        }}
        building={p.projectStatus?.building ?? false}
        stale={p.projectStatus?.stale ?? false}
        progress={p.transientComplete ? {
          task_id: 'complete',
          message: 'Build complete',
          current: p.projectStatus?.index.total_chunks ?? 0,
          total: p.projectStatus?.index.total_chunks ?? 0,
          percent: 100,
          status: 'completed'
        } : p.findActiveTask('index_build')}
        lastError={p.projectStatus?.index.last_error?.message}
        onBuild={p.selectedProjectId ? p.handleBuild : undefined}
        traceChunks={p.traceStatus.counts?.nodes ?? 0}
        autoRebuild={p.indexAutoRebuild}
        onAutoRebuildChange={p.handleIndexAutoRebuildChange}
        isPro={p.isPro}
        limitReached={p.limitReached}
        inactive={p.inactive}
        statsUnreachable={p.projectStatusUnreachable}
        className="h-full border-none shadow-none bg-transparent"
        bare
        hideChart={p.transientComplete}
      />
    ),
    // Phase 119 Phase A: per-endpoint Plan dropdown + integer Cloud Models
    // belong on the endpoint itself (not buried in Settings → AI Models). The
    // sidebar AI Gateway expand-arrow targets this panel id, so mount the live
    // AIModelsSettings here too — both the in-grid panel and the detail
    // overlay (panelDetails['llm-status']) share the same view.
    'llm-status': (
      <div className="h-full overflow-auto p-4">
        {aiModelsSettingsView}
      </div>
    ),
    search: (
      <SearchPanel
        query={p.query}
        onQueryChange={p.setQuery}
        k={p.searchK}
        onKChange={p.setSearchK}
        minScore={p.minScore}
        onMinScoreChange={p.setMinScore}
        onSearch={p.handleSearch}
        loading={p.searchLoading}
        bare
      />
    ),
    'context-options': (
      <ContextOptionsPanel
        k={p.contextK}
        onKChange={p.setContextK}
        maxChars={p.contextMaxChars}
        onMaxCharsChange={p.setContextMaxChars}
        includeSources={p.contextIncludeSources}
        onIncludeSourcesChange={p.setContextIncludeSources}
        includeScores={p.contextIncludeScores}
        onIncludeScoresChange={p.setContextIncludeScores}
        structured={p.contextStructured}
        onStructuredChange={p.setContextStructured}
        includeAtlas={search.contextIncludeAtlas}
        onIncludeAtlasChange={search.setContextIncludeAtlas}
        onGetContext={p.handleGetContext}
        onCopyContext={p.handleCopyContext}
        hasContext={!!p.context}
        disabled={!p.query.trim()}
        bare
      />
    ),
    results: (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full overflow-hidden">
        <div className="h-full overflow-y-auto min-h-0">
          <SearchResultsList
            results={p.searchResults}
            selectedId={p.selectedChunk?.chunk_id}
            onSelect={p.setSelectedChunk}
          />
        </div>
        <div className="h-full overflow-y-auto min-h-0 border-l border-border pl-4">
          <ChunkPreview
            content={p.selectedChunk?.content}
            sourcePath={p.selectedChunk?.source_path}
            section={p.selectedChunk?.section}
            bare
          />
        </div>
      </div>
    ),
    'context-output': (
      <ContextOutput
        context={p.context}
        meta={p.contextMeta}
        bare
      />
    ),
    'file-tree': (
      <FolderTreePanel
        data={p.fileTree}
        includedPaths={scopeIncludedPaths}
        scopeStatus={p.scopeStatus}
        onToggleInclude={async (paths, action) => {
          if (scopes.activeScopeId === 'global') {
            p.handleToggleInclude(paths, action)
          } else {
            if (action === 'add') {
              await scopes.addPaths(scopes.activeScopeId, paths)
            } else {
              await scopes.removePaths(scopes.activeScopeId, paths)
            }
            // Refresh the full scope record so the tree reflects the new paths
            if (p.selectedProjectId && scopes.activeScopeId !== 'global') {
              const updated = await apiClient.getScope(p.selectedProjectId, scopes.activeScopeId)
              setActiveScopeRecord(updated)
            }
          }
        }}
        pathWeights={p.pathWeights}
        onWeightChange={p.handlePathWeightChange}
        excludedPaths={excludedPaths}
        onToggleExclude={handleToggleExclude}
        alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_GLOBS}
        onLoadChildren={p.handleLoadChildren}
        title="Scope"
        bare
        scopes={scopes.scopes}
        activeScopeId={scopes.activeScopeId}
        onSetActiveScope={scopes.setActiveScopeId}
        onCreateScope={scopes.createScope}
        onRenameScope={scopes.renameScope}
        onDeleteScope={scopes.deleteScope}
      />
    ),
    'agent-ops': (
      <AgentOpsPanel
        data={agentOpsData}
        loading={agentOpsLoading}
        mcpStatus={mcpStatus}
        onMCPInstall={handleMCPInstall}
        onMCPUninstall={handleMCPUninstall}
        onMCPRefresh={fetchMcpStatus}
        pushSettings={pushSettings}
        onPushSettingsUpdate={setPushSettings}
        className="h-full"
      />
    ),
    ...Object.fromEntries(
      [...p.pinnedPaths].map((path) => {
        const file = p.pinnedFiles.find((f) => f.path === path)
        return [
          `${PINNED_PREFIX}${path}`,
          file ? (
            <div key={path} className="h-full flex flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-2 px-1 py-1 border-b border-border shrink-0">
                <span className="text-xs font-mono text-text-muted truncate flex-1">{file.path}</span>
                <CopyButton text={file.content} label="Copy" />
              </div>
              <pre className="flex-1 min-h-0 p-3 text-xs whitespace-pre-wrap font-mono text-text overflow-y-auto custom-scrollbar">
                {file.content}
              </pre>
            </div>
          ) : (
            <div key={path} className="h-full flex items-center justify-center text-sm text-text-muted">
              Loading {path.split('/').pop()}…
            </div>
          ),
        ]
      })
    ),
    trace: (
      <TraceExplorer
        traceEnabled={p.traceStatus.enabled}
        traceExists={p.traceStatus.exists}
        traceBuilding={p.traceStatus.building}
        traceCounts={p.traceStatus.counts}
        engine={p.traceStatus.engine}
        onSearchTrace={p.handleSearchTrace}
        onGetNode={p.handleGetTraceNode}
        onGetNeighbors={p.handleGetTraceNeighbors}
        onBuildTrace={p.handleBuildTrace}
        onEnableTrace={p.handleEnableTrace}
        progress={p.findActiveTask('trace_build')}
      />
    ),
    // trace-coverage removed — consolidated into graph-structure (Graph Scope)
    'deep-analysis': (
      <div className="h-full overflow-y-auto">
        <DeepAnalysisSettings
          schedule={p.deepAnalysisSchedule}
          onScheduleChange={p.setDeepAnalysisSchedule}
          largeModelConfigured={!!(p.llmConfig.large_model?.endpoint_id && p.llmConfig.large_model?.model)}
          fastModelConfigured={!!(p.llmConfig.small_model?.endpoint_id && p.llmConfig.small_model?.model)}
        />
      </div>
    ),
    'trace-pipeline': (
      <div className="h-full overflow-y-auto">
        <GraphEnrichmentPipeline
          projectLoading={p.projectLoading}
          trace={{
            enabled: p.traceStatus.enabled,
            exists: p.traceStatus.exists,
            building: p.traceStatus.building,
            counts: p.traceStatus.counts,
            last_build_at: null,
          }}
          inferredEdges={p.inferredEdgesStatus}
          augmentation={p.augmentationStatus}
          epistemic={p.epistemicStatus}
          modules={p.moduleStatus}
          deepening={p.deepeningStatus}
          knowledge={p.knowledgeStatus}
          deepKnowledge={p.deepKnowledgeStatus}
          atlas={atlas.atlasStatus ?? undefined}
          groupReasoning={p.groupReasoningStatus}
          smallModelConfigured={!!(p.llmConfig.small_model?.endpoint_id && p.llmConfig.small_model?.model)}
          largeModelConfigured={!!(p.llmConfig.large_model?.endpoint_id && p.llmConfig.large_model?.model)}
          codeModelConfigured={!!(p.llmConfig.code_model?.endpoint_id && p.llmConfig.code_model?.model)}
          onBuildTrace={p.handleBuildTrace}
          onRunAugmentation={p.handleRunAugmentation}
          onRunEpistemic={p.handleRunEpistemic}
          onRunModuleSynthesis={p.handleRunModuleSynthesis}
          onRunDeepening={p.handleRunDeepening}
          onRunKnowledgeBuild={p.handleRunKnowledgeBuild}
          onRunFastSync={p.handleRunFastSync}
          onRunDeepEnrichment={p.handleRunDeepEnrichment}
          onRunFinalize={p.handleRunFinalize}
          onOpenDeepSettings={p.onOpenDeepSettings}
          augmenting={p.augmenting}
          validating={p.validating}
          inferredEdgesRunning={p.inferredEdgesRunning}
          epistemicRunning={p.epistemicRunning}
          groupReasoningRunning={p.groupReasoningRunning}
          clusterRunning={p.clusterRunning}
          atlasRunning={p.atlasRunning}
          deepeningRunning={p.deepeningRunning}
          fastKnowledgeBuilding={p.fastKnowledgeBuilding}
          deepKnowledgeBuilding={p.deepKnowledgeBuilding}
          onPausePipeline={p.handlePausePipeline}
          onResumePipeline={p.handleResumePipeline}
          fastPaused={p.fastPaused}
          deepPaused={p.deepPaused}
          finalizePaused={p.finalizePaused}
          fastPausedStage={p.fastPausedStage}
          deepPausedStage={p.deepPausedStage}
          finalizePausedStage={p.finalizePausedStage}
          finalizeGroupRunning={p.finalizeRunning}
          finalizeCurrentStage={p.finalizeCurrentStage}
          rulesStatus={p.rulesStatus}
          conceptsStatus={p.conceptsStatus}
          auditPipelineStatus={p.auditPipelineStatus}
          antibodiesStatus={p.antibodiesStatus}
          autoConfig={p.enrichmentAutoConfig}
          onAutoConfigChange={p.handleEnrichmentAutoConfigChange}
          isPro={p.isPro}
          limitReached={p.limitReached}
          inactive={p.inactive}
          staleCounts={{
            total: p.traceCoverage.summary?.traced ?? 0,
            stale: p.traceCoverage.summary?.stale ?? 0
          }}
          provenance={p.pipelineProvenance?.current_data}
          fastCollapsed={p.fastCollapsed}
          deepCollapsed={p.deepCollapsed}
          finalizeCollapsed={p.finalizeCollapsed}
          onToggleFastCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('fast') : undefined}
          onToggleDeepCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('deep') : undefined}
          onToggleFinalizeCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('finalize') : undefined}
          projectId={p.selectedProjectId ?? undefined}
          apiClient={apiClient}
          barrier={health?.barrier}
          health={health ?? undefined}
          onClearBarrier={clearBarrier}
          onStageRestored={handleStageRestored}
          onRebuild={(scope) => { void p.triggerRebuild(scope); }}
          onStopRebuild={() => { void p.stopRebuild(); }}
        />
      </div>
    ),
    'graph-structure': (
      <GraphStructurePanel
        summary={p.traceCoverage.summary}
        epistemic={p.epistemicStatus}
        augmentation={p.augmentationStatus}
        moduleStatus={p.moduleStatus}
        knowledgeStatus={p.knowledgeStatus}
        untracedFiles={p.traceCoverage.untraced}
        staleFiles={p.traceCoverage.stale}
        tracedFiles={p.traceCoverage.traced}
        excludedFiles={p.traceCoverage.excluded}
        building={p.traceStatus.building || p.traceCoverage.building || p.inferredEdgesRunning || p.augmenting || p.validating || p.fastKnowledgeBuilding}
        progress={p.findActiveTask('trace_build')}
        loading={p.traceCoverage.loading}
        onTraceAll={p.handleTraceAll}
        onRetraceStale={p.handleRetraceStale}
        onAddExcludePattern={p.handleAddExcludePattern}
        onRemoveExcludePattern={p.handleRemoveExcludePattern}
        onRefresh={p.fetchTraceCoverage}
        traceExists={p.traceStatus.exists}
      />
    ),
    // graph-engine removed — consolidated into trace-pipeline (Graph Enrichment)
    'index-health': (
      <IndexHealthPanel
        data={p.projectStatus ? {
          total_chunks: p.projectStatus.index.total_chunks || p.knowledgeStatus.chunks_embedded || 0,
          total_files: p.traceCoverage.summary?.traced ?? p.traceStatus.counts?.nodes ?? 0,
          stale_count: p.projectStatus.stale_count ?? 0,
          error_count: p.projectStatus.index.last_error ? 1 : 0,
          last_build_at: p.projectStatus.index.last_build_at ?? p.knowledgeStatus.last_run_at ?? null,
          embedding_dim: p.projectStatus.index.embedding_dim ?? 0,
          trace_nodes: p.traceStatus.counts?.nodes ?? 0,
          trace_edges: p.traceStatus.counts?.edges ?? 0,
          coverage_pct: p.traceCoverage.summary?.coverage_pct ?? 0,
          catalogued_nodes: p.augmentationStatus.augmented_nodes,
          catalogued_total: p.augmentationStatus.total_nodes,
          deep: (p.epistemicStatus.enriched_nodes > 0 || p.moduleStatus.module_count > 0
              || p.epistemicRunning || p.clusterRunning || p.deepeningRunning) ? {
            enriched_nodes: p.epistemicStatus.enriched_nodes,
            enriched_total: p.epistemicStatus.total_file_nodes ?? 0,
            avg_confidence: p.epistemicStatus.avg_confidence ?? 0,
            module_count: p.moduleStatus.module_count,
            files_clustered: p.moduleStatus.total_files_clustered,
            deepening_settled_ratio: p.deepeningStatus.settled_ratio,
            deepening_iteration: p.deepeningStatus.iteration ?? 0,
            knowledge_chunks: p.knowledgeStatus.deep_chunks_embedded ?? 0,
            deep_running: p.epistemicRunning || p.clusterRunning || p.deepeningRunning,
            last_deep_at: p.epistemicStatus.pipeline_running ? null
              : (p.moduleStatus.last_run_at ?? null),
          } : null,
        } : null}
      />
    ),
    atlas: (
      <AtlasLensContainer
        projectId={p.selectedProjectId}
        className="h-full"
      />
    ),
    'activity-heatmap': props.activityData ? (
      <ActivityHeatmap
        data={props.activityData}
        weeks={12}
        showLegend={true}
        showLabels={true}
        className="h-full border-none shadow-none bg-transparent"
      />
    ) : (
      <div className="h-full flex items-center justify-center text-sm text-text-muted">
        No activity data available yet. Build your index to see activity.
      </div>
    ),
    audit: (
      <AuditPanel
        status={auditProps.auditStatus}
        findings={auditProps.auditFindings}
        reports={auditProps.auditReports}
        onRunAudit={auditProps.handleRunAudit}
        onViewReport={auditProps.handleViewAuditReport}
        reportContent={auditProps.auditReportContent}
        viewingReport={auditProps.viewingAuditReport}
      />
    ),
    health_scanner: (
      <HealthScannerPanel
        status={auditProps.auditStatus}
        findings={auditProps.auditFindings}
        reports={auditProps.auditReports}
        onRunAudit={auditProps.handleRunAudit}
        onViewReport={auditProps.handleViewAuditReport}
        reportContent={auditProps.auditReportContent}
        viewingReport={auditProps.viewingAuditReport}
        files={spaghettiProps.spaghettiFiles}
        fileCount={spaghettiProps.spaghettiFileCount}
        scoredCount={spaghettiProps.spaghettiScoredCount}
        severityCounts={spaghettiProps.spaghettiSeverityCounts}
        spaghettiLoading={spaghettiProps.spaghettiLoading}
        onRefreshSpaghetti={spaghettiProps.handleSpaghettiRefresh}
      />
    ),
    spaghetti: (
      <SpaghettiFinderPanel
        files={spaghettiProps.spaghettiFiles}
        fileCount={spaghettiProps.spaghettiFileCount}
        scoredCount={spaghettiProps.spaghettiScoredCount}
        severityCounts={spaghettiProps.spaghettiSeverityCounts}
        loading={spaghettiProps.spaghettiLoading}
        onRefresh={spaghettiProps.handleSpaghettiRefresh}
      />
    ),
    goalposts: goalpostsProps.state ? (
      <GoalpostsPanel
        productIntent={goalpostsProps.state.product_intent}
        proposals={goalpostsProps.state.proposals}
        questions={goalpostsProps.state.questions}
        generating={goalpostsProps.state.generating}
        error={goalpostsProps.state.error}
        ready={goalpostsProps.state.ready}
        hasAudit={goalpostsProps.state.has_audit}
        hasIntent={goalpostsProps.state.has_intent}
        missing={goalpostsProps.state.missing}
        lastGeneratedAt={goalpostsProps.state.last_generated_at}
        modelUsed={goalpostsProps.state.model_used}
        onGenerate={goalpostsProps.handleGenerate}
        onUpdateIntent={goalpostsProps.handleUpdateIntent}
        onApprove={goalpostsProps.handleApprove}
        onDismiss={goalpostsProps.handleDismiss}
        onAnswerQuestion={goalpostsProps.handleAnswerQuestion}
      />
    ) : (
      <PanelLoading message="Loading goalposts..." />
    ),
    advisor: goalpostsProps.state ? (
      <AdvisorPanel
        productIntent={goalpostsProps.state.product_intent}
        proposals={goalpostsProps.state.proposals}
        questions={goalpostsProps.state.questions}
        generating={goalpostsProps.state.generating}
        error={goalpostsProps.state.error}
        ready={goalpostsProps.state.ready}
        hasAudit={goalpostsProps.state.has_audit}
        hasIntent={goalpostsProps.state.has_intent}
        missing={goalpostsProps.state.missing}
        lastGeneratedAt={goalpostsProps.state.last_generated_at}
        modelUsed={goalpostsProps.state.model_used}
        onGenerate={goalpostsProps.handleGenerate}
        onUpdateIntent={goalpostsProps.handleUpdateIntent}
        onApprove={goalpostsProps.handleApprove}
        onDismiss={goalpostsProps.handleDismiss}
        onAnswerQuestion={goalpostsProps.handleAnswerQuestion}
      />
    ) : (
      <PanelLoading message="Loading advisor..." />
    ),
    roadmap: roadmapProps.state ? (
      <RoadmapPanel
        nodes={roadmapProps.state.nodes}
        questions={roadmapProps.state.questions}
        northStar={roadmapProps.state.north_star}
        appEthos={roadmapProps.state.app_ethos}
        generating={roadmapProps.state.generating}
        scanning={roadmapProps.state.scanning}
        error={roadmapProps.state.error}
        ready={true}
        lastGeneratedAt={roadmapProps.state.last_generated_at}
        modelUsed={roadmapProps.state.model_used}
        velocityData={roadmapProps.velocityData}
        sprintSuggestion={roadmapProps.sprintSuggestion}
        loadingSprint={roadmapProps.loadingSprint}
        onGenerate={roadmapProps.handleGenerate}
        onScanTodos={roadmapProps.handleScanTodos}
        onUpdateEthos={roadmapProps.handleUpdateEthos}
        onPromoteNode={roadmapProps.handlePromoteNode}
        onDismissNode={roadmapProps.handleDismissNode}
        onDeleteNode={roadmapProps.handleDeleteNode}
        onCreateNode={roadmapProps.handleCreateNode}
        onAnswerQuestion={roadmapProps.handleAnswerQuestion}
        onSyncGitHub={roadmapProps.handleSyncGitHub}
        onMineRoadmap={roadmapProps.handleMineRoadmap}
        onPushToGitHub={roadmapProps.handlePushNodeToGitHub}
        onSuggestSprint={roadmapProps.handleSuggestSprint}
        onExecuteNode={roadmapProps.handleExecuteNode}
        githubStatus={roadmapProps.state?.github_sync ? {
          configured: true,
          owner: roadmapProps.state.github_sync.owner,
          repo: roadmapProps.state.github_sync.repo,
          error: roadmapProps.state.github_sync.error || null,
          last_sync: roadmapProps.state.github_sync.last_synced_at || null,
        } : { configured: false }}
      />
    ) : (
      <PanelLoading message="Loading roadmap..." />
    ),
    'token-budget': (
      <TokenBudgetPanel
        data={p.deepAnalysisSchedule.budget_enabled ? (p.budgetUsage ?? {
          tokens_used: 0,
          max_tokens: p.deepAnalysisSchedule.budget_max_tokens,
          window_minutes: p.deepAnalysisSchedule.budget_max_minutes,
          remaining: p.deepAnalysisSchedule.budget_max_tokens,
          window_resets_in: 0,
        }) : null}
        deepMode={p.enrichmentAutoConfig?.deepEnrichment ?? 'manual'}
      />
    ),
    opportunities: (
      <OpportunitiesPanel
        items={opportunitiesProps.items}
        summary={opportunitiesProps.summary}
        loading={opportunitiesProps.loading}
        refreshing={opportunitiesProps.refreshing}
        error={opportunitiesProps.error}
        onRefresh={opportunitiesProps.handleRefresh}
        onDismiss={opportunitiesProps.handleDismiss}
        onRestore={opportunitiesProps.handleRestore}
        onExport={opportunitiesProps.handleExport}
        categoryFilter={opportunitiesProps.categoryFilter}
        onCategoryFilterChange={opportunitiesProps.setCategoryFilter}
        priorityFilter={opportunitiesProps.priorityFilter}
        onPriorityFilterChange={opportunitiesProps.setPriorityFilter}
        sourceFilter={opportunitiesProps.sourceFilter}
        onSourceFilterChange={opportunitiesProps.setSourceFilter}
        showDismissed={opportunitiesProps.showDismissed}
        onShowDismissedChange={opportunitiesProps.setShowDismissed}
        agentStatus={opportunitiesProps.agentStatus}
      />
    ),
    architecture: (
      <ArchitectureDiagramPanel
        summary={archProps.summary}
        loading={archProps.loading}
        error={archProps.error}
        onOpenDetail={() => props.onOpenDetails?.('architecture')}
      />
    ),
    concepts: (
      <ConceptsPanel
        concepts={conceptsProps.concepts}
        questions={conceptsProps.questions}
        stats={conceptsProps.stats}
        loading={conceptsProps.loading}
        initializing={conceptsProps.initializing}
        error={conceptsProps.error}
        onInitialize={conceptsProps.handleInitialize}
        onApprove={conceptsProps.handleApprove}
        onArchive={conceptsProps.handleArchive}
        onDelete={conceptsProps.handleDelete}
        onMarkFresh={conceptsProps.handleMarkFresh}
        onAnswerQuestion={conceptsProps.handleAnswerQuestion}
        onRefresh={conceptsProps.handleRefresh}
        onOpenDetail={() => props.onOpenDetails?.('concepts')}
      />
    ),
  }), [p, excludedPaths, handleToggleExclude, archProps,
      conceptsProps.concepts, conceptsProps.questions, conceptsProps.stats,
      conceptsProps.loading, conceptsProps.initializing, conceptsProps.error])

  const dynamicPanelDefs = useMemo(() =>
    [...p.pinnedPaths].map((path) => ({
      id: `${PINNED_PREFIX}${path}`,
      title: path.split('/').pop() ?? path,
      description: path,
      icon: FileText,
      minHeight: 4,
      defaultHeight: 8,
      category: 'projects' as const,
      closeable: true,
      resizable: true,
    })),
    [p.pinnedPaths]
  )

  const showDevPanels = props.showDevPanels ?? false
  const allPanelDefs = useMemo(
    () => [
      ...PANEL_REGISTRY.filter(p => !p.devOnly || showDevPanels),
      ...dynamicPanelDefs,
    ],
    [dynamicPanelDefs, showDevPanels]
  )

  const panelDetails = useMemo(() => ({
    'llm-status': (
      <div className="max-w-6xl mx-auto w-full p-6 space-y-8">
        {aiModelsSettingsView}
      </div>
    ),
    'file-tree': (
      <FileExplorerDetail
        treeData={p.fileTree}
        pinnedPaths={p.pinnedPaths}
        onPinFile={p.handlePinFile}
        onUnpinFile={p.handleUnpinFile}
        onLoadFileContent={p.handleLoadFileContent}
        includedPaths={p.includedPaths}
        scopeStatus={p.scopeStatus}
        onToggleInclude={p.handleToggleInclude}
        pathWeights={p.pathWeights}
        onWeightChange={p.handlePathWeightChange}
        onLoadChildren={p.handleLoadChildren}
        excludedPaths={excludedPaths}
        onToggleExclude={handleToggleExclude}
        alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_GLOBS}
      />
    ),
    'graph-structure': (
      <FileExplorerDetail
        treeData={p.fileTree}
        pinnedPaths={p.pinnedPaths}
        onPinFile={p.handlePinFile}
        onUnpinFile={p.handleUnpinFile}
        onLoadFileContent={p.handleLoadFileContent}
        includedPaths={p.includedPaths}
        scopeStatus={p.scopeStatus}
        onToggleInclude={p.handleToggleInclude}
        pathWeights={p.pathWeights}
        onWeightChange={p.handlePathWeightChange}
        onLoadChildren={p.handleLoadChildren}
        excludedPaths={excludedPaths}
        onToggleExclude={handleToggleExclude}
        alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_GLOBS}
      />
    ),
    'enterprise-admin': (
      <div className="max-w-6xl mx-auto w-full p-6 space-y-8">
        <EnterpriseAdminPanel
          tier={p.isPro ? 'enterprise' : 'free'}
          role="admin" // Hardcoded for now until role is wired up
          computeNodes={p.computeNodes}
          schedulerStatus={p.schedulerStatus}
          adminPolicy={p.adminPolicy}
          seatStatus={p.seatStatus}
          onProvisionSeat={p.onProvisionSeat}
          securityHealth={p.securityHealth}
          securityEvents={p.securityEvents}
          onExportSecurityReport={p.onExportSecurityReport}
          onExportAuditLog={p.onExportAuditLog}
        />
      </div>
    ),
    'agent-ops': (
      <AgentOpsPanel
        data={agentOpsData}
        loading={!agentOpsData}
        onHRGenerate={async () => {
          if (!p.selectedProjectId) return;
          await fetch(`/projects/${p.selectedProjectId}/agents/hr/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'auto' }),
          });
          fetch(`/projects/${p.selectedProjectId}/agents/status`)
            .then(r => r.json())
            .then(json => setAgentOpsData(mapAgentStatus(json.data ?? json)))
            .catch(() => {});
        }}
        onResearchRun={async () => {
          if (!p.selectedProjectId) return;
          await fetch(`/projects/${p.selectedProjectId}/agents/researcher/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_topics: 3 }),
          });
          fetch(`/projects/${p.selectedProjectId}/agents/status`)
            .then(r => r.json())
            .then(json => setAgentOpsData(mapAgentStatus(json.data ?? json)))
            .catch(() => {});
        }}
        onCustodianRun={async () => {
          if (!p.selectedProjectId) return;
          await fetch(`/projects/${p.selectedProjectId}/agents/custodian/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: true, max_files: 20 }),
          });
          fetch(`/projects/${p.selectedProjectId}/agents/status`)
            .then(r => r.json())
            .then(json => setAgentOpsData(mapAgentStatus(json.data ?? json)))
            .catch(() => {});
        }}
        pushSettings={pushSettings}
        onPushSettingsUpdate={setPushSettings}
      />
    ),
    architecture: (
      <ArchitectureDiagramDetail
        graph={archProps.graph}
        notes={archProps.notes}
        acrs={archProps.acrs}
        issueLinks={archProps.issueLinks}
        layerPath={archProps.layerPath}
        loading={archProps.loading}
        onDrillInto={archProps.drillInto}
        onNavigateToLayer={archProps.navigateToLayer}
        onSavePositions={archProps.savePositions}
        onCreateNote={archProps.createNote}
        onUpdateNote={archProps.updateNote}
        onDeleteNote={archProps.deleteNote}
        onSelectNode={archProps.selectNode}
        selectedNodeId={archProps.selectedNodeId}
        savedPositions={archProps.savedPositions}
        savedViewport={archProps.savedViewport}
        showOrphans={archProps.showOrphans}
        onToggleOrphans={archProps.toggleOrphans}
      />
    ),
    concepts: (
      <ConceptsDetail
        concepts={conceptsProps.concepts}
        questions={conceptsProps.questions}
        stats={conceptsProps.stats}
        loading={conceptsProps.loading}
        onApprove={conceptsProps.handleApprove}
        onArchive={conceptsProps.handleArchive}
        onDelete={conceptsProps.handleDelete}
        onMarkFresh={conceptsProps.handleMarkFresh}
        onAnswerQuestion={conceptsProps.handleAnswerQuestion}
        onRefresh={conceptsProps.handleRefresh}
      />
    ),
  }), [p, excludedPaths, handleToggleExclude, agentOpsData, archProps, conceptsProps.concepts, conceptsProps.questions, conceptsProps.stats, conceptsProps.loading])

  return { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX }
}
