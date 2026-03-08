import { useMemo, useState, useCallback, useEffect } from 'react'
import { FileText } from 'lucide-react'
import {
  IndexStatusCard,
  SearchPanel,
  UsageGuidePanel,
  ContextOptionsPanel,
  SearchResultsList,
  ChunkPreview,
  ContextOutput,
  LLMStatusWidget,
  AIModelsSettings,
  DeepAnalysisSettings,
  TraceExplorer,
  GraphEnrichmentPipeline,
  GraphStructurePanel,
  FolderTreePanel,
  FileExplorerDetail,
  CopyButton,
  LogConsole,
  IndexHealthPanel,
  TokenBudgetPanel,
  AtlasStatusCard,
  ActivityHeatmap,
  AuditPanel,
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
} from '@codrag/ui'
import type { TraceStatus, TraceCoverage } from './useTraceSystem'
import type { UseAuditSystemReturn } from './useAuditSystem'

const PINNED_PREFIX = 'pinned:'

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
  contextCompression: 'none' | 'lod' | 'lingua'
  setContextCompression: (v: 'none' | 'lod' | 'lingua') => void
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
  indexAutoRebuild: boolean
  handleIndexAutoRebuildChange: (auto: boolean) => void
  enrichmentAutoConfig: EnrichmentAutoConfig
  handleEnrichmentAutoConfigChange: (config: EnrichmentAutoConfig) => void
  handleSearchTrace: (query: string, kinds?: string[], limit?: number) => Promise<any>
  handleGetTraceNode: (nodeId: string) => Promise<any>
  handleGetTraceNeighbors: (nodeId: string, direction?: string) => Promise<any>
  handleBuildTrace: () => void
  handleEnableTrace: () => void
  handleTogglePause: () => void
  handleTraceAll: () => void
  handleRetraceStale: () => void
  handleAddExcludePattern: (pattern: string) => void
  handleRemoveExcludePattern: (pattern: string) => void
  fetchTraceCoverage: () => void
  handleRunFastSync: () => void
  handleDestroyGraph: () => void
}

export interface PanelEnrichmentProps {
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
  fastKnowledgeBuilding: boolean
  deepKnowledgeBuilding: boolean
  handleRunKnowledgeBuild: () => void
  handleRunDeepEnrichment: () => void
  handlePausePipeline: (group: 'fast_sync' | 'deep_enrichment') => void
  handleResumePipeline: (group: 'fast_sync' | 'deep_enrichment') => void
  fastPaused: boolean
  deepPaused: boolean
  groupReasoningStatus: { enabled: boolean; group_count: number; analyzed: number; running?: boolean; slot_phase?: string; progress_current?: number; progress_total?: number }
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
  handleTestModel: (slot: 'embedding' | 'small' | 'large' | 'code') => Promise<any>
  handleDownloadModel: (slot: 'embedding' | 'lingua') => Promise<void>
  availableModels: Record<string, string[]>
  loadingModels: Record<string, boolean>
  testingSlot: 'small' | 'embedding' | 'large' | 'code' | null
  testResults: Record<string, EndpointTestResult>
  // Compute settings (Phase 45)
  maxActiveProjects?: number | 'infinite'
  onMaxActiveProjectsChange?: (val: number | 'infinite') => void
  concurrencyFast?: number
  concurrencyCode?: number
  concurrencyDeep?: number
  onConcurrencyChange?: (key: 'fast' | 'code' | 'deep', value: number) => void
  schedulerStatus?: { nodes: Record<string, { max_concurrent: number; current_load: number; active: Record<string, string>; queued: Array<{ project_id: string; stage: string; waiting_seconds: number }> }> } | null
}

export interface PanelDeepAnalysisProps {
  deepAnalysisSchedule: DeepAnalysisSchedule
  setDeepAnalysisSchedule: (s: DeepAnalysisSchedule | ((prev: DeepAnalysisSchedule) => DeepAnalysisSchedule)) => void
  budgetUsage: TokenBudgetData | null
}

export interface PanelAtlasProps {
  atlasStatus: AtlasStatus | null
}

// ── Main interface ────────────────────────────────────────────

export interface DashboardPanelsProps {
  // Cross-cutting
  projectStatus: ProjectStatus | null
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
  // Domain groups
  search: PanelSearchProps
  files: PanelFileSystemProps
  trace: PanelTraceProps
  enrichment: PanelEnrichmentProps
  llm: PanelLLMProps
  deepAnalysis: PanelDeepAnalysisProps
  atlas: PanelAtlasProps
  audit: UseAuditSystemReturn
  activityData: ActivityHeatmapData | null
}

/** Builds all dashboard panel content, detail views, and dynamic panel definitions from domain state. */
export function useDashboardPanels(props: DashboardPanelsProps) {
  // Flatten grouped sub-objects for backward-compatible p.xxx access internally
  const { search, files, trace, enrichment, llm, deepAnalysis, atlas, audit: auditProps, ...core } = props
  const p = { ...core, ...search, ...files, ...trace, ...enrichment, ...llm, ...deepAnalysis }

  // Optimistic local state for excluded paths — updates INSTANTLY on click.
  // Seeded from trace coverage when it arrives, but local clicks are immediate.
  const [localExcludedPaths, setLocalExcludedPaths] = useState<Set<string>>(new Set())

  // Reset local state when switching projects to avoid cross-contamination
  useEffect(() => {
    setLocalExcludedPaths(new Set())
  }, [p.selectedProject?.id])

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

      // 2. Fire API calls in background (persist to backend)
      for (const rawPath of paths) {
        const cleanPath = rawPath.replace(/\/$/, '')
        if (action === 'add') {
          p.handleAddExcludePattern(cleanPath)
          p.handleAddExcludePattern(`${cleanPath}/**`)
        } else {
          p.handleRemoveExcludePattern(cleanPath)
          p.handleRemoveExcludePattern(`${cleanPath}/**`)
        }
      }
    },
    [p.handleAddExcludePattern, p.handleRemoveExcludePattern, p.fileTree]
  )

  // Use local optimistic state as the source of truth for the UI
  const excludedPaths = localExcludedPaths

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
            compression: p.llmConfig.compression ?? null,
            saved_endpoints: p.llmConfig.saved_endpoints?.map((ep: SavedEndpoint) => ({
              id: ep.id, name: ep.name, provider: ep.provider, url: ep.url,
            })),
            batch_mode: p.llmConfig.batch_mode ?? 'auto',
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
        className="h-full border-none shadow-none bg-transparent"
        bare
        hideChart={p.transientComplete}
      />
    ),
    'llm-status': (
      <div className="h-full overflow-y-auto">
        <LLMStatusWidget
          services={(() => {
            const hasEmbedding = !!(p.llmConfig.embedding.model && (p.llmConfig.embedding.source === 'endpoint' || p.llmConfig.embedding.source === 'huggingface'));
            const hasFast = !!(p.llmConfig.small_model.enabled && p.llmConfig.small_model.model);
            const hasThinking = !!(p.llmConfig.large_model.enabled && p.llmConfig.large_model.model);
            const hasCompression = !!(p.llmConfig.compression?.enabled);
            const fastName = hasThinking ? 'Fast Model' : 'Single LLM';
            
            // Map pipeline states to model activity
            const embeddingRunning = p.searchLoading || (p.projectStatus?.building ?? false) || p.fastKnowledgeBuilding || p.deepKnowledgeBuilding;
            const fastRunning = p.augmenting;
            const largeRunning = p.validating || p.epistemicRunning || p.groupReasoningRunning || p.deepeningRunning || p.clusterRunning || p.atlasRunning;
            const codeRunning = p.inferredEdgesRunning;

            type Svc = { name: string; status: 'connected' | 'disconnected' | 'disabled' | 'not-configured'; type: 'ollama' | 'openai' | 'other'; model?: string; running?: boolean };
            const items: Svc[] = [];
            if (hasEmbedding) {
              items.push({
                name: 'Embedding',
                status: p.llmSlotsStatus?.embedding
                  ? (p.llmSlotsStatus.embedding.status === 'connected' || p.llmSlotsStatus.embedding.status === 'local' ? 'connected'
                    : p.llmSlotsStatus.embedding.status === 'unreachable' ? 'disconnected'
                    : p.llmSlotsStatus.embedding.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'other',
                model: p.llmConfig.embedding.model,
                running: embeddingRunning,
              });
            }
            if (hasFast) {
              items.push({
                name: fastName,
                status: p.llmSlotsStatus?.small_model
                  ? (p.llmSlotsStatus.small_model.status === 'connected' ? 'connected'
                    : p.llmSlotsStatus.small_model.status === 'unreachable' ? 'disconnected'
                    : p.llmSlotsStatus.small_model.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'ollama',
                model: p.llmConfig.small_model.model,
                running: fastRunning,
              });
            }
            if (hasThinking) {
              items.push({
                name: 'Thinking Model',
                status: p.llmSlotsStatus?.large_model
                  ? (p.llmSlotsStatus.large_model.status === 'connected' ? 'connected'
                    : p.llmSlotsStatus.large_model.status === 'unreachable' ? 'disconnected'
                    : p.llmSlotsStatus.large_model.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'openai',
                model: p.llmConfig.large_model.model,
                running: largeRunning,
              });
            }
            const hasCode = !!(p.llmConfig.code_model?.enabled && p.llmConfig.code_model.model);
            if (hasCode) {
              items.push({
                name: 'Code Model',
                status: p.llmSlotsStatus?.code_model
                  ? (p.llmSlotsStatus.code_model.status === 'connected' ? 'connected'
                    : p.llmSlotsStatus.code_model.status === 'unreachable' ? 'disconnected'
                    : p.llmSlotsStatus.code_model.configured ? 'disconnected' : 'not-configured')
                  : 'connected',
                type: 'ollama',
                model: p.llmConfig.code_model.model,
                running: codeRunning,
              });
            }
            if (hasCompression) {
              const mode = p.llmConfig.compression.mode || 'auto';
              const level = p.llmConfig.compression.level || 'standard';
              items.push({
                name: 'Compression',
                status: 'connected',
                type: 'other',
                model: `${mode} (${level})`,
              });
            }
            if (items.length === 0) {
              items.push({ name: 'No models configured', status: 'not-configured', type: 'other' });
            }
            return items;
          })()}
          bare
        />
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
        compression={search.contextCompression}
        onCompressionChange={search.setContextCompression}
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
        includedPaths={p.includedPaths}
        scopeStatus={p.scopeStatus}
        onToggleInclude={p.handleToggleInclude}
        pathWeights={p.pathWeights}
        onWeightChange={p.handlePathWeightChange}
        onLoadChildren={p.handleLoadChildren}
        title="Knowledge Sources"
        bare
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
          onDestroyGraph={p.handleDestroyGraph}
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
          paused={p.projectConfig.trace.paused}
          onTogglePause={p.handleTogglePause}
          onPausePipeline={p.handlePausePipeline}
          onResumePipeline={p.handleResumePipeline}
          isPaused={p.deepPaused || p.fastPaused}
          autoConfig={p.enrichmentAutoConfig}
          onAutoConfigChange={p.handleEnrichmentAutoConfigChange}
          isPro={p.isPro}
          limitReached={p.limitReached}
          inactive={p.inactive}
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
        excludedFiles={p.traceCoverage.excluded}
        building={p.traceStatus.building || p.traceCoverage.building}
        progress={p.findActiveTask('trace_build')}
        loading={p.traceCoverage.loading}
        onTraceAll={p.handleTraceAll}
        onRetraceStale={p.handleRetraceStale}
        onAddExcludePattern={p.handleAddExcludePattern}
        onRemoveExcludePattern={p.handleRemoveExcludePattern}
        onRefresh={p.fetchTraceCoverage}
        traceExists={p.traceStatus.exists}
        fileTree={p.fileTree}
        excludedPaths={excludedPaths}
        onToggleExclude={handleToggleExclude}
        onLoadChildren={p.handleLoadChildren}
      />
    ),
    // graph-engine removed — consolidated into trace-pipeline (Graph Enrichment)
    'index-health': (
      <IndexHealthPanel
        data={p.projectStatus ? {
          total_chunks: p.projectStatus.index.total_chunks || p.knowledgeStatus.chunks_embedded || 0,
          total_files: p.traceStatus.counts?.nodes ?? 0,
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
      <AtlasStatusCard
        atlas={atlas.atlasStatus}
        className="h-full border-none shadow-none bg-transparent"
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
  }), [p, excludedPaths, handleToggleExclude])

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

  const allPanelDefs = useMemo(
    () => [...PANEL_REGISTRY, ...dynamicPanelDefs],
    [dynamicPanelDefs]
  )

  const panelDetails = useMemo(() => ({
    'llm-status': (
      <div className="max-w-6xl mx-auto w-full p-6 space-y-8">
        <AIModelsSettings
          config={p.llmConfig}
          onConfigChange={p.handleLLMConfigChange}
          onAddEndpoint={p.handleAddEndpoint}
          onEditEndpoint={p.handleEditEndpoint}
          onDeleteEndpoint={p.handleDeleteEndpoint}
          onTestEndpoint={p.handleTestEndpoint}
          onFetchModels={p.handleFetchModels}
          onTestModel={p.handleTestModel}
          onHFDownload={p.handleDownloadModel}
          availableModels={p.availableModels}
          loadingModels={p.loadingModels}
          testingSlot={p.testingSlot}
          testResults={p.testResults}
          maxActiveProjects={p.maxActiveProjects}
          onMaxActiveProjectsChange={p.onMaxActiveProjectsChange}
          concurrencyFast={p.concurrencyFast}
          concurrencyCode={p.concurrencyCode}
          concurrencyDeep={p.concurrencyDeep}
          onConcurrencyChange={p.onConcurrencyChange}
          schedulerStatus={p.schedulerStatus}
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
        />
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
        initialTab="knowledge"
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
        initialTab="exclude"
      />
    ),
  }), [p, excludedPaths, handleToggleExclude])

  return { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX }
}
