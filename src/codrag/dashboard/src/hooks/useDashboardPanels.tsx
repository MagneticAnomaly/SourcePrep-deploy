import { useMemo } from 'react'
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
  WatchControlPanel,
  FolderTreePanel,
  FileExplorerDetail,
  CopyButton,
  LogConsole,
  PANEL_REGISTRY,
  type SearchResult,
  type ContextMeta,
  type ProjectConfig,
  type ProjectStatus,
  type ProjectListItem,
  type TreeNode,
  type PinnedTextFile,
  type WatchStatus,
  type DeepAnalysisSchedule,
  type DeepAnalysisRunStatus,
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
} from '@codrag/ui'
import type { TraceStatus, TraceCoverage } from './useTraceSystem'

const PINNED_PREFIX = 'pinned:'

export interface DashboardPanelsProps {
  // Project
  projectStatus: ProjectStatus | null
  selectedProject: ProjectListItem | null
  selectedProjectId: string | null
  projectConfig: ProjectConfig
  isPro: boolean
  // Event stream
  logs: any[]
  clearLogs: () => void
  findActiveTask: (type: 'index_build' | 'trace_build') => any
  // Build
  handleBuild: () => void
  // Search
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
  // Context
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
  context: string
  contextMeta: ContextMeta | null
  handleGetContext: () => void
  handleCopyContext: () => void
  // Watch
  watchStatus: WatchStatus
  watchLoading: boolean
  handleStartWatch: () => void
  handleStopWatch: () => void
  // File tree
  fileTree: TreeNode[]
  includedPaths: Set<string>
  handleToggleInclude: (paths: string[], action: 'add' | 'remove') => void
  pathWeights: Record<string, number>
  handlePathWeightChange: (path: string, weight: number | null) => void
  handleLoadChildren: (path: string) => Promise<TreeNode[]>
  // Pinned files
  pinnedPaths: Set<string>
  pinnedFiles: PinnedTextFile[]
  handlePinFile: (path: string) => void
  handleUnpinFile: (path: string) => void
  handleLoadFileContent: (path: string) => Promise<string>
  // Trace system
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
  // Enrichment
  augmentationStatus: AugmentationStatus
  augmenting: boolean
  handleRunAugmentation: () => void
  epistemicStatus: EpistemicStatus
  epistemicRunning: boolean
  handleRunEpistemic: () => void
  moduleStatus: ModuleStatus
  clusterRunning: boolean
  handleRunModuleSynthesis: () => void
  deepeningStatus: DeepeningStatus
  deepeningRunning: boolean
  handleRunDeepening: () => void
  knowledgeStatus: KnowledgeEmbeddingStatus
  knowledgeBuilding: boolean
  handleRunKnowledgeBuild: () => void
  handleRunFastSync: () => void
  handleRunDeepEnrichment: () => void
  handleDestroyGraph: () => void
  // Deep analysis
  deepAnalysisSchedule: DeepAnalysisSchedule
  setDeepAnalysisSchedule: (s: DeepAnalysisSchedule | ((prev: DeepAnalysisSchedule) => DeepAnalysisSchedule)) => void
  deepAnalysisStatus: DeepAnalysisRunStatus
  deepAnalysisRunning: boolean
  handleRunDeepAnalysis: () => void
  handleCancelDeepAnalysis: () => void
  // LLM
  llmConfig: LLMConfig
  llmSlotsStatus: LLMSlotsStatus | null
  handleLLMConfigChange: (config: LLMConfig) => void
  handleAddEndpoint: (ep: Omit<SavedEndpoint, 'id'>) => void
  handleEditEndpoint: (ep: SavedEndpoint) => void
  handleDeleteEndpoint: (id: string) => void
  handleTestEndpoint: (ep: SavedEndpoint) => Promise<any>
  handleFetchModels: (endpointId: string) => Promise<any>
  handleTestModel: (slot: 'embedding' | 'small' | 'large' | 'clara') => Promise<any>
  availableModels: Record<string, string[]>
  loadingModels: Record<string, boolean>
  testingSlot: 'small' | 'clara' | 'embedding' | 'large' | null
  testResults: Record<string, EndpointTestResult>
}

/** Builds all dashboard panel content, detail views, and dynamic panel definitions from domain state. */
export function useDashboardPanels(p: DashboardPanelsProps) {
  const panelContent = useMemo(() => ({
    'log-console': (
      <LogConsole
        logs={p.logs}
        onClear={p.clearLogs}
        className="h-full border-none shadow-none bg-transparent"
        defaultExpanded={true}
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
        progress={p.findActiveTask('index_build')}
        lastError={p.projectStatus?.index.last_error?.message}
        onBuild={p.selectedProjectId ? p.handleBuild : undefined}
        traceChunks={p.traceStatus.counts?.nodes ?? 0}
        autoRebuild={p.indexAutoRebuild}
        onAutoRebuildChange={p.handleIndexAutoRebuildChange}
        isPro={p.isPro}
        className="h-full border-none shadow-none bg-transparent"
        bare
      />
    ),
    'llm-status': (
      <div className="h-full overflow-y-auto p-4">
        <LLMStatusWidget
          services={(() => {
            const hasEmbedding = !!(p.llmConfig.embedding.model && (p.llmConfig.embedding.source === 'endpoint' || p.llmConfig.embedding.source === 'huggingface'));
            const hasFast = !!(p.llmConfig.small_model.enabled && p.llmConfig.small_model.model);
            const hasThinking = !!(p.llmConfig.large_model.enabled && p.llmConfig.large_model.model);
            const hasCLaRa = !!(p.llmConfig.clara.enabled && (p.llmConfig.clara.remote_url || p.llmConfig.clara.endpoint_id || p.llmConfig.clara.source === 'huggingface'));
            const fastName = hasThinking ? 'Fast Model' : 'Single LLM';
            type Svc = { name: string; status: 'connected' | 'disconnected' | 'disabled' | 'not-configured'; type: 'ollama' | 'clara' | 'openai' | 'other'; model?: string };
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
              });
            }
            if (hasCLaRa) {
              items.push({
                name: 'CLaRa',
                status: p.llmConfig.clara.remote_url || p.llmConfig.clara.endpoint_id ? 'connected' : 'not-configured',
                type: 'clara',
                model: 'Context Compression',
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
    watch: (
      <WatchControlPanel
        status={p.watchStatus}
        onStartWatch={p.handleStartWatch}
        onStopWatch={p.handleStopWatch}
        onRebuildNow={() => p.selectedProjectId && void p.handleBuild()}
        loading={p.watchLoading}
        bare
      />
    ),
    'file-tree': (
      <FolderTreePanel
        data={p.fileTree}
        includedPaths={p.includedPaths}
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
      <div className="h-full overflow-y-auto p-4">
        <DeepAnalysisSettings
          schedule={p.deepAnalysisSchedule}
          onScheduleChange={p.setDeepAnalysisSchedule}
          largeModelConfigured={!!(p.llmConfig.large_model?.endpoint_id && p.llmConfig.large_model?.model)}
          fastModelConfigured={!!(p.llmConfig.small_model?.endpoint_id && p.llmConfig.small_model?.model)}
          status={p.deepAnalysisStatus}
          running={p.deepAnalysisRunning}
          onRunNow={p.handleRunDeepAnalysis}
          onCancel={p.handleCancelDeepAnalysis}
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
          augmentation={p.augmentationStatus}
          deepAnalysis={p.deepAnalysisStatus}
          epistemic={p.epistemicStatus}
          modules={p.moduleStatus}
          deepening={p.deepeningStatus}
          knowledge={p.knowledgeStatus}
          smallModelConfigured={!!(p.llmConfig.small_model?.endpoint_id && p.llmConfig.small_model?.model)}
          largeModelConfigured={!!(p.llmConfig.large_model?.endpoint_id && p.llmConfig.large_model?.model)}
          onBuildTrace={p.handleBuildTrace}
          onRunAugmentation={p.handleRunAugmentation}
          onRunDeepAnalysis={p.handleRunDeepAnalysis}
          onRunEpistemic={p.handleRunEpistemic}
          onRunModuleSynthesis={p.handleRunModuleSynthesis}
          onRunDeepening={p.handleRunDeepening}
          onRunKnowledgeBuild={p.handleRunKnowledgeBuild}
          onRunFastSync={p.handleRunFastSync}
          onRunDeepEnrichment={p.handleRunDeepEnrichment}
          onDestroyGraph={p.handleDestroyGraph}
          augmenting={p.augmenting}
          deepAnalyzing={p.deepAnalysisRunning}
          epistemicRunning={p.epistemicRunning}
          clusterRunning={p.clusterRunning}
          deepeningRunning={p.deepeningRunning}
          knowledgeBuilding={p.knowledgeBuilding}
          paused={p.projectConfig.trace.paused}
          onTogglePause={p.handleTogglePause}
          autoConfig={p.enrichmentAutoConfig}
          onAutoConfigChange={p.handleEnrichmentAutoConfigChange}
          isPro={p.isPro}
        />
      </div>
    ),
    'graph-structure': (
      <GraphStructurePanel
        summary={p.traceCoverage.summary}
        untracedFiles={p.traceCoverage.untraced}
        staleFiles={p.traceCoverage.stale}
        excludedFiles={p.traceCoverage.excluded}
        building={p.traceCoverage.building}
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
  }), [p])

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
          onHFDownload={() => {}}
          availableModels={p.availableModels}
          loadingModels={p.loadingModels}
          testingSlot={p.testingSlot}
          testResults={p.testResults}
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
        onToggleInclude={p.handleToggleInclude}
        pathWeights={p.pathWeights}
        onWeightChange={p.handlePathWeightChange}
        onLoadChildren={p.handleLoadChildren}
      />
    ),
  }), [p])

  return { panelContent, panelDetails, allPanelDefs, PINNED_PREFIX }
}
