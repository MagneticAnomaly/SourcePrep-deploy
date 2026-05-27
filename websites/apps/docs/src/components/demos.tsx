"use client";

// Demo wrappers — direct imports of @prep/ui components configured with the
// same fixture data used in their Storybook stories. Replaces iframe-based
// StoryEmbed for in-page component previews. Each demo mirrors how the live
// dashboard wraps the component in ModularDashboard (the `prep-panel-body p-4`
// container) so what readers see matches production output.
//
// Source-of-truth fixtures live in packages/ui/src/stories/**.stories.tsx —
// if a fixture drifts there, mirror the change here. The reverse is also true:
// if a demo here grows, consider promoting the wrapper into @prep/ui under a
// shared `demos/` module so stories can re-import.

import { useState, useCallback } from 'react';
import {
  // Dashboard
  IndexStatusCard,
  type IndexStats,
  LLMStatusWidget,
  // Project
  FolderTreePanel,
  // LLM
  AdvancedLLMSettings,
  AIModelsSettings,
  EndpointManager,
  ModelCard,
  // Search / Context
  SearchPanel,
  ContextOptionsPanel,
  ContextViewer,
  // Trace / Pipeline
  GraphEnrichmentPipeline,
  TraceCoveragePanel,
  AtlasLensPanel,
  NodeDetailPanel,
  TraceGraph,
  // Audit / Concepts / Roadmap
  AuditPanel,
  OpportunitiesPanel,
  RoadmapPanel,
  // Console / Viz
  LogConsole,
  ActivityHeatmap,
  generateSampleActivityData,
  // Agents / Team
  AgentOpsPanel,
  SyncStatusCard,
  // Layout
  PanelPicker,
} from '@prep/ui';
import type {
  TreeNode,
  ScopeSummary,
  ScopeRecord,
  SavedEndpoint,
  LLMConfig,
  EndpointTestResult,
  ModelSlotType,
  AdvancedLLMSettingsValue,
  LogEntry,
  AuditFinding,
  AuditReport,
  AtlasStatus,
  TraceCoverageFile,
  TraceCoverageSummary,
  AugmentationStatus,
  DeepAnalysisRunStatus,
  RoadmapNode,
  GoalpostQuestion,
  VelocityResponse,
  SprintSuggestion,
  TraceNode,
  TraceEdge,
  TraceGraphNode,
  TraceGraphEdge,
} from '@prep/ui';
import type { DashboardLayout, PanelDefinition } from '@prep/ui';
import { Database, Search, Settings2, FileText, FolderTree as FolderTreeIcon, Hammer, SlidersHorizontal, List } from 'lucide-react';

// ── Shared chrome ────────────────────────────────────────────────────────────

/**
 * Matches the wrapper ModularDashboard puts around every panel body before
 * PanelChrome. Without it, components with `bare={true}` render flush against
 * the page background.
 *
 * `bordered` defaults to true. Set to false for components that already render
 * their own card chrome (ModelCard, EndpointManager, SyncStatusCard,
 * AdvancedLLMSettings, ContextViewer, ActivityHeatmap) to avoid double-borders.
 */
function DemoFrame({
  children,
  height,
  bordered = true,
}: {
  children: React.ReactNode;
  height?: number | string;
  bordered?: boolean;
}) {
  const heightStyle = height
    ? { height: typeof height === 'number' ? `${height}px` : height }
    : undefined;
  const chrome = bordered
    ? 'p-4 rounded-md border border-border bg-surface'
    : 'p-0';
  return (
    <div
      className={`prep-panel-body flex flex-col ${chrome} min-h-0 overflow-hidden my-6`}
      style={heightStyle}
    >
      {children}
    </div>
  );
}

const noop = () => {};
const asyncNoop = async () => {};
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// ────────────────────────────────────────────────────────────────────────────
// Dashboard / Index Status
// ────────────────────────────────────────────────────────────────────────────

const INDEX_STATUS_LOADED: IndexStats = {
  loaded: true,
  index_dir: '~/code/sourceprep',
  model: 'nomic-embed-text',
  built_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
  embedding_dim: 768,
  total_documents: 22,
  build: {
    mode: 'incremental',
    files_total: 13,
    files_reused: 11,
    files_embedded: 2,
    files_deleted: 0,
    files_code: 6,
    files_docs: 7,
    chunks_total: 22,
    chunks_code: 10,
    chunks_docs: 12,
    lines_code: 480,
    lines_docs: 540,
  },
};

export function DemoIndexStatusLoaded() {
  return (
    <DemoFrame>
      <IndexStatusCard stats={INDEX_STATUS_LOADED} traceChunks={18} bare />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Project / FolderTreePanel
// ────────────────────────────────────────────────────────────────────────────

const KNOWLEDGE_SCOPE_TREE: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'auth',
        type: 'folder',
        children: [
          { name: 'login.py', type: 'file', status: 'indexed', chunks: 4 },
          { name: 'jwt.py', type: 'file', status: 'indexed', chunks: 6 },
          { name: 'session.py', type: 'file', status: 'pending' },
        ],
      },
      {
        name: 'middleware',
        type: 'folder',
        children: [
          { name: 'rate_limit.py', type: 'file', status: 'indexed', chunks: 3 },
          { name: 'cors.py', type: 'file', status: 'pending' },
        ],
      },
    ],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [
      { name: 'AUTH.md', type: 'file', status: 'indexed', chunks: 5 },
      { name: 'INTERNAL.md', type: 'file', status: 'ignored' },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [{ name: 'test_auth.py', type: 'file' }],
  },
];

export function DemoFolderTreeKnowledgeScope() {
  const [activeScopeId, setActiveScopeId] = useState('auth-feature');
  const [scopes, setScopes] = useState<ScopeSummary[]>([
    { id: 'global', display_name: 'Global', path_count: 13, assigned_to_role: null },
    { id: 'auth-feature', display_name: 'auth-feature', path_count: 6, assigned_to_role: null },
  ]);
  const [includedPaths, setIncludedPaths] = useState<Set<string>>(
    new Set(['src/auth', 'src/middleware', 'docs/AUTH.md'])
  );
  const [excludedPaths, setExcludedPaths] = useState<Set<string>>(
    new Set(['docs/INTERNAL.md'])
  );

  const handleToggleInclude = useCallback((paths: string[], action: 'add' | 'remove') => {
    setIncludedPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) action === 'add' ? next.add(p) : next.delete(p);
      return next;
    });
  }, []);

  const handleToggleExclude = useCallback((paths: string[], action: 'add' | 'remove') => {
    setExcludedPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) action === 'add' ? next.add(p) : next.delete(p);
      return next;
    });
  }, []);

  const handleCreateScope = useCallback(
    async (display_name: string): Promise<ScopeRecord | null> => {
      const id = `scope-${Date.now()}`;
      setScopes((s) => [...s, { id, display_name, path_count: 0, assigned_to_role: null }]);
      return { id, display_name, paths: [], assigned_to_role: null };
    },
    []
  );

  const handleRenameScope = useCallback(async (id: string, display_name: string) => {
    setScopes((s) => s.map((sc) => (sc.id === id ? { ...sc, display_name } : sc)));
  }, []);

  const handleDeleteScope = useCallback(
    async (id: string) => {
      setScopes((s) => s.filter((sc) => sc.id !== id));
      if (activeScopeId === id) setActiveScopeId('global');
    },
    [activeScopeId]
  );

  return (
    <DemoFrame height={520}>
      <FolderTreePanel
        data={KNOWLEDGE_SCOPE_TREE}
        includedPaths={includedPaths}
        excludedPaths={excludedPaths}
        onToggleInclude={handleToggleInclude}
        onToggleExclude={handleToggleExclude}
        scopes={scopes}
        activeScopeId={activeScopeId}
        onSetActiveScope={setActiveScopeId}
        onCreateScope={handleCreateScope}
        onRenameScope={handleRenameScope}
        onDeleteScope={handleDeleteScope}
        bare
      />
    </DemoFrame>
  );
}

const PATH_WEIGHTS_TREE: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'core',
        type: 'folder',
        children: [
          { name: 'auth.py', type: 'file', status: 'indexed', chunks: 6 },
          { name: 'billing.py', type: 'file', status: 'indexed', chunks: 4 },
        ],
      },
      {
        name: 'utils',
        type: 'folder',
        children: [
          { name: 'helpers.py', type: 'file', status: 'indexed', chunks: 3 },
          { name: 'logging.py', type: 'file', status: 'indexed', chunks: 2 },
        ],
      },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [{ name: 'test_auth.py', type: 'file', status: 'indexed', chunks: 5 }],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [{ name: 'README.md', type: 'file', status: 'indexed', chunks: 4 }],
  },
];

export function DemoFolderTreePathWeights() {
  return (
    <DemoFrame height={520}>
      <FolderTreePanel
        data={PATH_WEIGHTS_TREE}
        includedPaths={
          new Set([
            'src/core/auth.py',
            'src/core/billing.py',
            'src/utils/helpers.py',
            'tests/test_auth.py',
            'docs/README.md',
          ])
        }
        pathWeights={{
          'src/core': 1.5,
          'src/utils': 0.7,
          tests: 0.3,
          'docs/README.md': 1.8,
        }}
        onWeightChange={noop}
        onToggleInclude={noop}
        excludedPaths={new Set()}
        onToggleExclude={noop}
        scopes={[{ id: 'global', display_name: 'Global', path_count: 5, assigned_to_role: null }]}
        activeScopeId="global"
        onSetActiveScope={noop}
        onCreateScope={asyncNoop as never}
        onRenameScope={asyncNoop}
        onDeleteScope={asyncNoop}
        bare
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// LLM
// ────────────────────────────────────────────────────────────────────────────

const LLM_ENDPOINTS: SavedEndpoint[] = [
  { id: 'local-ollama', name: 'Local Ollama', provider: 'ollama', url: 'http://localhost:11434' },
  { id: 'gpu-ollama', name: 'GPU Server', provider: 'ollama', url: 'http://192.168.1.100:11434' },
  { id: 'openai', name: 'OpenAI', provider: 'openai', url: 'https://api.openai.com/v1', api_key: '********' },
];

const LLM_BASE_CONFIG: LLMConfig = {
  embedding: {
    source: 'endpoint',
    endpoint_id: 'local-ollama',
    model: 'nomic-embed-text',
    hf_repo_id: 'nomic-ai/nomic-embed-text-v1.5',
    hf_downloaded: false,
    hf_download_progress: undefined,
  },
  small_model: { enabled: true, endpoint_id: 'local-ollama', model: 'qwen3:4b-instruct' },
  large_model: { enabled: true, endpoint_id: 'gpu-ollama', model: 'qwen3:8b' },
  code_model: { enabled: false },
  saved_endpoints: LLM_ENDPOINTS,
};

const AVAILABLE_MODELS: Record<string, string[]> = {
  'local-ollama': ['nomic-embed-text', 'qwen3:4b', 'qwen3:1.7b', 'gemma3:4b'],
  'gpu-ollama': ['qwen3:8b', 'qwen3:14b', 'qwen3:30b', 'qwen3-coder:30b'],
  openai: ['gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4.1'],
};

export function DemoAdvancedLLMSettings() {
  const [value, setValue] = useState<AdvancedLLMSettingsValue>({
    enforce_cloud_token_safety: true,
    max_thinking_budget: 24576,
  });
  return (
    <DemoFrame bordered={false}>
      <div className="max-w-md">
        <AdvancedLLMSettings value={value} onChange={setValue} />
      </div>
    </DemoFrame>
  );
}

export function DemoAIModelsSettings() {
  const [config, setConfig] = useState<LLMConfig>(LLM_BASE_CONFIG);
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>(AVAILABLE_MODELS);
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});
  const [testingSlot, setTestingSlot] = useState<ModelSlotType | null>(null);
  const [testResults, setTestResults] = useState<Record<string, EndpointTestResult>>({});

  return (
    <DemoFrame>
      <AIModelsSettings
        config={config}
        onConfigChange={setConfig}
        availableModels={availableModels}
        loadingModels={loadingModels}
        testingSlot={testingSlot}
        testResults={testResults}
        onAddEndpoint={(ep) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: [...prev.saved_endpoints, { id: `ep-${prev.saved_endpoints.length + 1}`, ...ep }],
          }))
        }
        onEditEndpoint={(endpoint) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: prev.saved_endpoints.map((e) => (e.id === endpoint.id ? endpoint : e)),
          }))
        }
        onDeleteEndpoint={(id) =>
          setConfig((prev) => ({
            ...prev,
            saved_endpoints: prev.saved_endpoints.filter((e) => e.id !== id),
          }))
        }
        onTestEndpoint={async (endpoint) => {
          await sleep(350);
          if (endpoint.provider === 'ollama') {
            return {
              success: true,
              message: 'Connected. Models loaded.',
              models: availableModels[endpoint.id] || [],
            };
          }
          if ((endpoint.provider === 'openai' || endpoint.provider === 'anthropic') && !endpoint.api_key) {
            return { success: false, message: 'Missing API key' };
          }
          return { success: true, message: 'Connected.' };
        }}
        onFetchModels={async (endpointId) => {
          setLoadingModels((p) => ({ ...p, [endpointId]: true }));
          await sleep(400);
          setAvailableModels((p) => ({ ...p, [endpointId]: AVAILABLE_MODELS[endpointId] || [] }));
          setLoadingModels((p) => ({ ...p, [endpointId]: false }));
          return AVAILABLE_MODELS[endpointId] || [];
        }}
        onTestModel={async (slotType) => {
          setTestingSlot(slotType);
          await sleep(450);
          const result: EndpointTestResult = { success: true, message: 'Test succeeded.' };
          setTestResults((p) => ({ ...p, [slotType]: result }));
          setTestingSlot(null);
          return result;
        }}
        onHFDownload={() => {
          setConfig((prev) => ({
            ...prev,
            embedding: {
              ...prev.embedding,
              source: 'huggingface',
              hf_downloaded: false,
              hf_download_progress: 0.35,
            },
          }));
        }}
      />
    </DemoFrame>
  );
}

export function DemoEndpointManager() {
  const [endpoints, setEndpoints] = useState<SavedEndpoint[]>([
    { id: 'local-ollama', name: 'Local Ollama', provider: 'ollama', url: 'http://localhost:11434' },
    { id: 'openai', name: 'OpenAI', provider: 'openai', url: 'https://api.openai.com/v1', api_key: '********' },
  ]);
  return (
    <DemoFrame bordered={false}>
      <EndpointManager
        endpoints={endpoints}
        onAdd={(ep) =>
          setEndpoints((prev) => [...prev, { id: `ep-${prev.length + 1}`, ...ep }])
        }
        onEdit={(ep) => setEndpoints((prev) => prev.map((p) => (p.id === ep.id ? ep : p)))}
        onDelete={(id) => setEndpoints((prev) => prev.filter((p) => p.id !== id))}
        onTest={async (ep) => {
          await sleep(350);
          if (ep.provider === 'ollama' && ep.url.includes('localhost')) {
            return { success: true, message: 'Connected. Models: nomic-embed-text, mistral' };
          }
          if (ep.provider === 'openai' && !ep.api_key) {
            return { success: false, message: 'Missing API key' };
          }
          return { success: true, message: 'Connected.' };
        }}
      />
    </DemoFrame>
  );
}

export function DemoLLMStatusWidget() {
  return (
    <DemoFrame>
      <LLMStatusWidget
        bare
        services={[
          { name: 'Embedding', status: 'connected', type: 'other', url: 'nomic-embed-text' },
          { name: 'Small Model', status: 'connected', type: 'ollama', url: 'qwen2.5:3b' },
          { name: 'Large Model', status: 'disabled', type: 'ollama' },
        ]}
      />
    </DemoFrame>
  );
}

const DEFAULT_MODELCARD_ICON = (
  <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
    />
  </svg>
);

export function DemoModelCardConnected() {
  return (
    <DemoFrame bordered={false}>
      <ModelCard
        title="Large Model"
        description="Complex reasoning & summaries"
        icon={DEFAULT_MODELCARD_ICON}
        endpoints={LLM_ENDPOINTS}
        endpoint="local-ollama"
        model="mistral"
        availableModels={['mistral', 'qwen3:30b-instruct', 'deepseek-coder-v2']}
        status="connected"
        onTest={noop}
        testResult={{ success: true, message: 'Connected. 3 models available.' }}
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Search / Context
// ────────────────────────────────────────────────────────────────────────────

export function DemoSearchPanel() {
  const [query, setQuery] = useState('how does the API client handle errors');
  const [k, setK] = useState(8);
  const [minScore, setMinScore] = useState(0.15);
  const [loading, setLoading] = useState(false);
  const handleSearch = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 1500);
  };
  return (
    <DemoFrame>
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        k={k}
        onKChange={setK}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onSearch={handleSearch}
        loading={loading}
        bare
      />
    </DemoFrame>
  );
}

export function DemoSearchPanelFullDemo() {
  const [query, setQuery] = useState('');
  const [searchK, setSearchK] = useState(8);
  const [minScore, setMinScore] = useState(0.15);
  const [loading, setLoading] = useState(false);
  const [contextK, setContextK] = useState(5);
  const [maxChars, setMaxChars] = useState(6000);
  const [includeSources, setIncludeSources] = useState(true);
  const [includeScores, setIncludeScores] = useState(false);
  const [structured, setStructured] = useState(false);
  const [hasContext, setHasContext] = useState(false);

  return (
    <DemoFrame>
      <div className="space-y-4">
        <SearchPanel
          query={query}
          onQueryChange={setQuery}
          k={searchK}
          onKChange={setSearchK}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          onSearch={() => {
            setLoading(true);
            setTimeout(() => setLoading(false), 1500);
          }}
          loading={loading}
          bare
        />
        <ContextOptionsPanel
          k={contextK}
          onKChange={setContextK}
          maxChars={maxChars}
          onMaxCharsChange={setMaxChars}
          includeSources={includeSources}
          onIncludeSourcesChange={setIncludeSources}
          includeScores={includeScores}
          onIncludeScoresChange={setIncludeScores}
          structured={structured}
          onStructuredChange={setStructured}
          onGetContext={() => setHasContext(true)}
          onCopyContext={noop}
          hasContext={hasContext}
          disabled={!query.trim()}
          bare
        />
      </div>
    </DemoFrame>
  );
}

const CONTEXT_OUTPUT_TEXT = `--- Source: src/prep/core/indexer.py:45-78 ---
def build_index(project_path: str, config: IndexConfig) -> Index:
    """Build a semantic index for the given project."""
    scanner = FileScanner(project_path, config)
    files = scanner.scan()
    chunks = chunker.chunk_files(files)
    embeddings = embed_chunks(chunks, config.model)
    return Index(chunks, embeddings)

--- Source: src/prep/api/routes.py:120-145 ---
@app.post("/projects/{project_id}/search")
async def search_project(project_id: str, request: SearchRequest):
    """Semantic search in project."""
    project = registry.get(project_id)
    results = project.index.search(request.query, k=request.k)
    return {"success": True, "data": {"results": results}}`;

export function DemoContextOutput() {
  // ContextViewer renders its own bordered card, so use bordered={false}.
  return (
    <DemoFrame bordered={false}>
      <ContextViewer
        context={CONTEXT_OUTPUT_TEXT}
        chunks={[
          {
            chunk_id: 'chunk-001',
            source_path: 'src/prep/core/indexer.py',
            span: { start_line: 45, end_line: 78 },
            score: 0.92,
            truncated: false,
          },
          {
            chunk_id: 'chunk-002',
            source_path: 'src/prep/api/routes.py',
            span: { start_line: 120, end_line: 145 },
            score: 0.85,
            truncated: false,
          },
        ]}
        totalChars={1250}
        estimatedTokens={312}
        showSources
        showScores
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Trace / Pipeline
// ────────────────────────────────────────────────────────────────────────────

const COVERAGE_SUMMARY: TraceCoverageSummary = {
  total: 42,
  traced: 35,
  untraced: 5,
  stale: 2,
  excluded: 3,
  coverage_pct: 83.3,
  last_build_at: new Date(Date.now() - 3_600_000).toISOString(),
};

const COVERAGE_UNTRACED: TraceCoverageFile[] = [
  { path: 'src/api/handlers.ts', language: 'typescript', size: 4200, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
  { path: 'src/utils/logger.ts', language: 'typescript', size: 1800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'src/core/scheduler.py', language: 'python', size: 6100, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
];

const COVERAGE_STALE: TraceCoverageFile[] = [
  { path: 'src/core/index.py', language: 'python', size: 8900, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

const COVERAGE_EXCLUDED: TraceCoverageFile[] = [
  { path: 'tests/test_api.py', language: 'python', size: 3200, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'scripts/deploy.sh', language: null, size: 800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

export function DemoTraceCoverage() {
  return (
    <DemoFrame height={600}>
      <TraceCoveragePanel
        summary={COVERAGE_SUMMARY}
        untracedFiles={COVERAGE_UNTRACED}
        staleFiles={COVERAGE_STALE}
        excludedFiles={COVERAGE_EXCLUDED}
        building={false}
        loading={false}
        onTraceAll={noop}
        onRetraceStale={noop}
        onAddExcludePattern={noop}
        onRemoveExcludePattern={noop}
        onRefresh={noop}
        bare
      />
    </DemoFrame>
  );
}

const TRACE_GRAPH_NODES: TraceGraphNode[] = [
  { id: 'app', name: 'App.tsx', kind: 'file', language: 'TypeScript', inDegree: 0, outDegree: 3 },
  { id: 'button', name: 'Button.tsx', kind: 'file', language: 'TypeScript', inDegree: 2, outDegree: 1 },
  { id: 'form', name: 'LoginForm.tsx', kind: 'file', language: 'TypeScript', inDegree: 1, outDegree: 3 },
  { id: 'useAuth', name: 'useAuth', kind: 'symbol', inDegree: 2, outDegree: 1 },
  { id: 'login', name: '/api/login', kind: 'endpoint', inDegree: 2, outDegree: 0 },
];

const TRACE_GRAPH_EDGES: TraceGraphEdge[] = [
  { source: 'app', target: 'button', kind: 'imports' },
  { source: 'app', target: 'form', kind: 'imports' },
  { source: 'form', target: 'button', kind: 'imports' },
  { source: 'form', target: 'useAuth', kind: 'calls' },
  { source: 'useAuth', target: 'login', kind: 'calls' },
  { source: 'form', target: 'login', kind: 'calls' },
];

export function DemoTraceGraph() {
  return (
    <DemoFrame height={400}>
      <TraceGraph nodes={TRACE_GRAPH_NODES} edges={TRACE_GRAPH_EDGES} />
    </DemoFrame>
  );
}

export function DemoNodeDetailPanel() {
  const mockNode: TraceNode = {
    id: 'src/components/Button.tsx',
    name: 'Button',
    kind: 'file',
    file_path: 'src/components/Button.tsx',
    language: 'TypeScript',
    span: { start_line: 10, end_line: 45 },
    metadata: {
      is_public: true,
      docstring: 'A flexible button component with variants.',
      decorators: ['memo'],
    },
  };
  return (
    <DemoFrame height={520}>
      <NodeDetailPanel
        node={mockNode}
        inEdges={[
          { id: 'e1', source: 'src/App.tsx', target: 'src/components/Button.tsx', kind: 'imports', metadata: { confidence: 1 } },
          { id: 'e2', source: 'src/components/Form.tsx', target: 'src/components/Button.tsx', kind: 'imports', metadata: { confidence: 1 } },
        ]}
        outEdges={[
          { id: 'e3', source: 'src/components/Button.tsx', target: 'react', kind: 'imports', metadata: { confidence: 1 } },
        ]}
      />
    </DemoFrame>
  );
}

const ATLAS_NOW = new Date('2026-04-14T15:00:00Z').toISOString();
const ATLAS_SEGMENTS = [
  { segment_id: 'seg_src', segment_name: 'src/prep', dir_path: 'src/prep', file_count: 323, char_count: 2100, mode: 'structural' as const, generated_at: ATLAS_NOW, stale: false },
  { segment_id: 'seg_ui', segment_name: 'packages/ui', dir_path: 'packages/ui', file_count: 291, char_count: 1800, mode: 'structural' as const, generated_at: ATLAS_NOW, stale: false },
  { segment_id: 'seg_sites', segment_name: 'websites', dir_path: 'websites', file_count: 73, char_count: 800, mode: 'structural' as const, generated_at: ATLAS_NOW, stale: true },
];

const ATLAS_STATUS: AtlasStatus = {
  exists: true,
  content: 'IDENTITY: SourcePrep is a multi-segment AI coding assistant platform...\nSTACK: Python 323 files, TypeScript 334 files...',
  mode: 'structural',
  model: 'structural',
  generated_at: ATLAS_NOW,
  file_count: 687,
  module_count: 18,
  char_count: 4700,
  stale: true,
  segmented: true,
  segments: ATLAS_SEGMENTS,
};

export function DemoAtlasLensStaleSegments() {
  const [role, setRole] = useState<string | null>(null);
  return (
    <DemoFrame height={620}>
      <AtlasLensPanel
        atlas={ATLAS_STATUS}
        role={role}
        onRoleChange={setRole}
        onRegenerate={noop}
      />
    </DemoFrame>
  );
}

const AUG_FULL: AugmentationStatus = {
  enabled: true,
  total_nodes: 1245,
  augmented_nodes: 1200,
  validated_nodes: 450,
  avg_confidence: 0.85,
  low_confidence_count: 45,
  last_augment_at: new Date(Date.now() - 7_200_000).toISOString(),
  model: 'llama3.2:3b',
};

const DEEP_RAN: DeepAnalysisRunStatus = {
  last_run_at: new Date(Date.now() - 604_800_000).toISOString(),
  last_run_items: 47,
  last_run_tokens: 23_450,
  queue_size: 133,
  avg_confidence: 0.78,
  running: false,
};

export function DemoGraphEnrichmentPipelineRunning() {
  return (
    <DemoFrame height={620}>
      <GraphEnrichmentPipeline
        trace={{
          enabled: true,
          exists: true,
          building: false,
          counts: { nodes: 1245, edges: 3890 },
          last_build_at: new Date(Date.now() - 3_600_000).toISOString(),
        }}
        augmentation={AUG_FULL}
        deepAnalysis={DEEP_RAN}
        fastPaused={false}
        onRunFastSync={noop}
        onRunDeepEnrichment={noop}
        onStopRebuild={noop}
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Audit / Concepts / Roadmap
// ────────────────────────────────────────────────────────────────────────────

const AUDIT_FINDINGS: AuditFinding[] = [
  {
    analyzer: 'large_files',
    severity: 'critical',
    category: 'size',
    title: 'GraphEnrichmentPipeline.tsx exceeds 58KB — extract stage components',
    description: 'This file has grown to 1,247 lines and handles all 9 pipeline stages inline.',
    file_paths: ['packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx'],
    evidence: { lines: 1247, bytes: 58301, module: 'trace' },
    suggested_action: 'Extract each pipeline stage into its own component.',
    finding_id: 'SIZE-1',
    priority: 'P0',
    effort: 'large',
  },
  {
    analyzer: 'circular_deps',
    severity: 'warning',
    category: 'architecture',
    title: 'Circular dependency between search/ and trace/ modules',
    description: 'SearchPanel imports TraceGraph, and TraceExplorer imports SearchResultsList.',
    file_paths: ['src/components/search/SearchPanel.tsx', 'src/components/trace/TraceExplorer.tsx'],
    evidence: { cycle: ['search', 'trace'], module: 'search' },
    suggested_action: 'Create a shared results/ module for SearchResultsList.',
    finding_id: 'ARCH-1',
    priority: 'P1',
    effort: 'medium',
  },
  {
    analyzer: 'dead_code',
    severity: 'warning',
    category: 'quality',
    title: 'GoalpostsPanel is hidden but still ships in the bundle',
    description: 'The component is marked as hidden in the panel registry but is still imported and tree-shaken into the build.',
    file_paths: ['src/components/goalposts/GoalpostsPanel.tsx'],
    evidence: { hidden: true, bundle_bytes: 22000, module: 'goalposts' },
    suggested_action: 'Use React.lazy() for sunset panels, or remove the import entirely.',
    finding_id: 'QUAL-1',
    priority: 'P1',
    effort: 'small',
  },
  {
    analyzer: 'naming',
    severity: 'info',
    category: 'naming',
    title: 'Inconsistent naming: "Panel" vs "Card" vs "Widget" suffixes',
    description: '15 components use "Panel", 8 use "Card", and 3 use "Widget".',
    file_paths: ['src/components/dashboard/', 'src/components/trace/'],
    evidence: { panel_count: 15, card_count: 8, widget_count: 3, module: 'dashboard' },
    suggested_action: 'Standardize: use "Panel" for full-height, "Card" for compact.',
    finding_id: 'NAME-1',
    priority: 'P2',
    effort: 'small',
  },
  {
    analyzer: 'test_coverage',
    severity: 'info',
    category: 'coverage',
    title: 'No test coverage for FolderTreePanel scope-dropdown flow',
    description: 'The named-scopes dropdown has no integration tests covering create/rename/delete.',
    file_paths: ['src/components/project/FolderTreePanel.tsx'],
    evidence: { coverage_pct: 0, module: 'project' },
    suggested_action: 'Add integration tests with mock scope callbacks.',
    finding_id: 'COV-1',
    priority: 'P2',
    effort: 'medium',
  },
  {
    analyzer: 'coupling',
    severity: 'suggestion',
    category: 'architecture',
    title: 'email.py fans out to 12 imports',
    description: 'Possible god-module — email composition, SMTP transport, and template rendering all in one file.',
    file_paths: ['backend/services/email.py'],
    evidence: { import_count: 12 },
    suggested_action: 'Split into transport + template + composer.',
    finding_id: 'ARCH-2',
    priority: 'P3',
    effort: 'medium',
  },
];

const AUDIT_REPORTS: AuditReport[] = [
  { name: 'AUDIT_SUMMARY', filename: 'audit_summary.md', size_bytes: 4200 },
  { name: 'ARCHITECTURE_ANALYSIS', filename: 'architecture_analysis.md', size_bytes: 8500 },
  { name: 'TECH_DEBT_REPORT', filename: 'tech_debt_report.md', size_bytes: 6300 },
];

export function DemoAuditPanelWithFindings() {
  return (
    <DemoFrame height={680}>
      <AuditPanel
        status={{
          running: false,
          error: null,
          has_results: true,
          finding_count: AUDIT_FINDINGS.length,
          severity_counts: { critical: 1, warning: 2, info: 2, suggestion: 1 },
          last_run: {
            generated_at: new Date(Date.now() - 7_200_000).toISOString(),
            graph_node_count: 5085,
            graph_edge_count: 21767,
            finding_count: AUDIT_FINDINGS.length,
            document_count: 3,
            analyzers_run: ['large_files', 'circular_deps', 'dead_code', 'naming', 'test_coverage', 'coupling'],
            documents: ['AUDIT_SUMMARY', 'ARCHITECTURE_ANALYSIS', 'TECH_DEBT_REPORT'],
          },
        }}
        findings={AUDIT_FINDINGS}
        reports={AUDIT_REPORTS}
        onRunAudit={noop}
        onViewReport={noop}
      />
    </DemoFrame>
  );
}

export function DemoOpportunitiesWithItems() {
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [showDismissed, setShowDismissed] = useState(false);
  const now = new Date().toISOString();
  const items = [
    {
      id: 'OPP-001',
      title: 'Extract pipeline stage components from GraphEnrichmentPipeline',
      description: 'The 58KB monolith file handles all 9 stages inline. Splitting into individual stage components would improve maintainability and reduce coupling.',
      category: 'architecture',
      priority: 'P0',
      severity: 'critical',
      effort: 'large',
      source: 'health',
      analyzer: 'large_files',
      state: 'active' as const,
      affected_files: ['packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx'],
      suggested_action: 'Create trace/stages/ directory with one component per pipeline stage.',
      evidence: 'File size: 58,301 bytes, 1,247 lines',
      mcp_command: 'prep_audit action="refactor" finding_ids=["SIZE-1"]',
      created_at: now,
      dismissed_at: '',
    },
    {
      id: 'OPP-002',
      title: 'Break circular dependency between search and trace modules',
      description: 'SearchPanel imports TraceGraph, TraceExplorer imports SearchResultsList — bidirectional dependency creates tight coupling.',
      category: 'architecture',
      priority: 'P1',
      severity: 'warning',
      effort: 'medium',
      source: 'health',
      analyzer: 'circular_deps',
      state: 'active' as const,
      affected_files: ['src/components/search/SearchPanel.tsx', 'src/components/trace/TraceExplorer.tsx'],
      suggested_action: 'Extract SearchResultsList into a shared results/ module.',
      evidence: 'Cycle: search → trace → search',
      mcp_command: 'prep_audit action="refactor" finding_ids=["ARCH-1"]',
      created_at: now,
      dismissed_at: '',
    },
    {
      id: 'OPP-003',
      title: 'Remove dead import of GoalpostsPanel from bundle',
      description: 'Panel is marked hidden but still imported. Tree-shaking is not removing it because of the registry reference.',
      category: 'quality',
      priority: 'P1',
      severity: 'warning',
      effort: 'small',
      source: 'health',
      analyzer: 'dead_code',
      state: 'active' as const,
      affected_files: ['src/components/goalposts/GoalpostsPanel.tsx', 'src/config/panelRegistry.ts'],
      suggested_action: 'Use React.lazy() or remove from registry entirely.',
      evidence: 'Hidden panel still in bundle: 22KB',
      mcp_command: 'prep_audit action="refactor" finding_ids=["QUAL-1"]',
      created_at: now,
      dismissed_at: '',
    },
    {
      id: 'OPP-004',
      title: 'Add integration tests for FolderTreePanel scope dropdown',
      description: 'The Phase 120 named-scopes dropdown has zero test coverage.',
      category: 'coverage',
      priority: 'P2',
      severity: 'info',
      effort: 'medium',
      source: 'health',
      analyzer: 'test_coverage',
      state: 'active' as const,
      affected_files: ['src/components/project/FolderTreePanel.tsx'],
      suggested_action: 'Write tests with mock scope create/rename/delete callbacks.',
      evidence: 'Coverage: 0% for named-scopes dropdown flow',
      mcp_command: '',
      created_at: now,
      dismissed_at: '',
    },
    {
      id: 'OPP-005',
      title: 'TODO: Implement retry logic for embedding failures',
      description: 'Found in-code TODO comment indicating missing retry logic.',
      category: 'quality',
      priority: 'P2',
      severity: 'info',
      effort: 'small',
      source: 'todo_scanner',
      analyzer: 'todo_scanner',
      state: 'active' as const,
      affected_files: ['src/prep/core/embeddings.py'],
      suggested_action: 'Add exponential backoff retry with max 3 attempts.',
      evidence: 'Line 142: # TODO: add retry logic here',
      mcp_command: '',
      created_at: now,
      dismissed_at: '',
    },
    {
      id: 'OPP-006',
      title: 'Consider extracting auth middleware into shared package',
      description: 'The auth middleware pattern is duplicated across the MCP server and the dashboard API.',
      category: 'architecture',
      priority: 'P2',
      severity: 'info',
      effort: 'large',
      source: 'advisor',
      analyzer: 'advisor',
      state: 'active' as const,
      affected_files: ['src/prep/mcp/auth.py', 'src/prep/dashboard/auth.py'],
      suggested_action: 'Create a shared auth/ package with middleware and token validation.',
      evidence: 'Code similarity: 87% between the two auth files',
      mcp_command: '',
      created_at: now,
      dismissed_at: '',
    },
  ];
  return (
    <DemoFrame height={680}>
      <OpportunitiesPanel
        items={items}
        summary={{
          total: items.length,
          dismissed: 0,
          critical: 1,
          warning: 2,
          info: 3,
          actionable_count: 4,
          last_refresh: now,
          by_priority: { P0: 1, P1: 2, P2: 3 },
          by_category: { architecture: 3, quality: 2, coverage: 1 },
          by_source: { health: 4, todo_scanner: 1, advisor: 1 },
          by_analyzer: {},
          by_severity: { critical: 1, warning: 2, info: 3 },
          top_analyzers: [
            { analyzer: 'large_files', count: 1 },
            { analyzer: 'circular_deps', count: 1 },
            { analyzer: 'dead_code', count: 1 },
            { analyzer: 'test_coverage', count: 1 },
            { analyzer: 'todo_scanner', count: 1 },
            { analyzer: 'advisor', count: 1 },
          ],
        }}
        loading={false}
        refreshing={false}
        error={null}
        onRefresh={noop}
        onDismiss={noop}
        onRestore={noop}
        onExport={noop}
        categoryFilter={categoryFilter}
        onCategoryFilterChange={setCategoryFilter}
        priorityFilter={priorityFilter}
        onPriorityFilterChange={setPriorityFilter}
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
        showDismissed={showDismissed}
        onShowDismissedChange={setShowDismissed}
      />
    </DemoFrame>
  );
}

const ROADMAP_NOW = new Date().toISOString();
const ROADMAP_WEEK_AGO = new Date(Date.now() - 7 * 86400000).toISOString();
const ROADMAP_TWO_WEEKS = new Date(Date.now() - 14 * 86400000).toISOString();

const ROADMAP_NODES: RoadmapNode[] = [
  {
    id: 'rm-1', title: 'Implement MCP streaming responses',
    description: 'Add Server-Sent Events streaming for prep_search to reduce TTFB.',
    tier: 'active', position: 0, source: 'ai_proposed', source_ref: null, category: 'feature', priority: 'P0',
    tasks: [
      { description: 'Add SSE endpoint to MCP server', file_paths: ['src/prep/mcp/routes.py'], effort: 'medium' },
      { description: 'Update client to consume streaming', file_paths: ['packages/ui/src/api/client.ts'], effort: 'small' },
    ],
    state: 'active', parent_id: null, fork_label: null,
    created_at: ROADMAP_WEEK_AGO, decided_at: ROADMAP_WEEK_AGO, completed_at: null,
    ethos_alignment: 'Performance-first', business_impact: 'Reduces perceived latency by 60%',
  },
  {
    id: 'rm-2', title: 'Extract pipeline stages into individual components',
    description: 'GraphEnrichmentPipeline.tsx is 58KB. Split into 9 stage components.',
    tier: 'planned', position: 1, source: 'ai_proposed', source_ref: null, category: 'architecture', priority: 'P1',
    tasks: [{ description: 'Create trace/stages/ directory', file_paths: ['packages/ui/src/components/trace/'], effort: 'small' }],
    state: 'accepted', parent_id: null, fork_label: null,
    created_at: ROADMAP_WEEK_AGO, decided_at: null, completed_at: null,
    ethos_alignment: 'Maintainability', business_impact: 'Reduces onboarding cost',
  },
  {
    id: 'rm-3', title: 'Add retry logic for embedding failures',
    description: 'Missing exponential backoff in the embedding pipeline.',
    tier: 'planned', position: 2, source: 'todo_scan', source_ref: 'src/prep/core/embeddings.py:142', category: 'tech_debt', priority: 'P2',
    tasks: [{ description: 'Add exponential backoff with max 3 attempts', file_paths: ['src/prep/core/embeddings.py'], effort: 'small' }],
    state: 'accepted', parent_id: null, fork_label: null,
    created_at: ROADMAP_TWO_WEEKS, decided_at: null, completed_at: null,
    ethos_alignment: 'Reliability', business_impact: 'Eliminates silent indexing failures',
  },
];

const ROADMAP_QUESTIONS: GoalpostQuestion[] = [
  {
    id: 'q-1', question: 'Should federated search merge results by relevance score or by project priority?',
    context: 'Federated search across multiple projects requires a merge strategy.',
    category: 'feature', answered: false, answer: '', created_at: ROADMAP_NOW,
  },
];

const ROADMAP_VELOCITY: VelocityResponse = {
  average_velocity: 3.2,
  total_completed: 12, total_active: 3, total_planned: 5, total_proposed: 2,
  snapshots: [
    { window_start: ROADMAP_TWO_WEEKS, window_end: ROADMAP_WEEK_AGO, window_label: 'Sprint 4', duration_days: 7, completed_count: 4, completed_nodes: ['rm-5'], added_count: 2, p0_completed: 1, p1_completed: 2, categories: { feature: 2, architecture: 1, tech_debt: 1 } },
  ],
  burndown: [
    { date: ROADMAP_TWO_WEEKS, remaining: 18, completed: 10 },
    { date: ROADMAP_WEEK_AGO, remaining: 14, completed: 14 },
  ],
};

const ROADMAP_SPRINT: SprintSuggestion = {
  sprint_label: 'Sprint 6', capacity: 3, confidence: 0.82,
  rationale: 'Based on average velocity of 3.2 nodes/sprint.',
  suggested_nodes: ['rm-1', 'rm-2', 'rm-3'],
  node_details: [
    { id: 'rm-1', title: 'Implement MCP streaming responses', priority: 'P0', category: 'feature', tier: 'active' },
    { id: 'rm-2', title: 'Extract pipeline stage components', priority: 'P1', category: 'architecture', tier: 'planned' },
  ],
};

export function DemoRoadmapPanel() {
  return (
    <DemoFrame height={680}>
      <RoadmapPanel
        nodes={ROADMAP_NODES}
        questions={ROADMAP_QUESTIONS}
        northStar={{ id: 'rm-1', title: 'Implement MCP streaming responses', priority: 'P0' }}
        appEthos="SourcePrep is an epistemic intelligence engine for autonomous agents."
        generating={false} scanning={false} error={null} ready={true}
        lastGeneratedAt={ROADMAP_WEEK_AGO} modelUsed="claude-sonnet-4-20250514"
        velocityData={ROADMAP_VELOCITY} sprintSuggestion={ROADMAP_SPRINT} loadingSprint={false}
        onGenerate={noop} onScanTodos={noop} onUpdateEthos={noop}
        onPromoteNode={noop} onDismissNode={noop} onDeleteNode={noop}
        onCreateNode={noop} onAnswerQuestion={noop}
        onSuggestSprint={noop} onMineRoadmap={noop}
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Console / Viz / Agents / Team
// ────────────────────────────────────────────────────────────────────────────

export function DemoLogConsolePipeline() {
  const baseTime = Date.now() / 1000;
  const logs: LogEntry[] = [
    { timestamp: baseTime - 120, level: 'INFO', logger: 'prep.server', message: 'Prep daemon started on http://0.0.0.0:8400', created: baseTime - 120 },
    { timestamp: baseTime - 100, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Fast Sync starting: structural → inferred_edges → catalogue → validation → knowledge', created: baseTime - 100 },
    { timestamp: baseTime - 95, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 1/5: structural — scanning 1143 files', created: baseTime - 95 },
    { timestamp: baseTime - 80, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Stage 1/5: structural — traced 847 files, 5085 nodes, 21767 edges (12.4s)', created: baseTime - 80 },
    { timestamp: baseTime - 60, level: 'WARNING', logger: 'prep.core.inferred_edges', message: 'Code model slot not configured — using heuristic fallback.', created: baseTime - 60 },
    { timestamp: baseTime - 35, level: 'ERROR', logger: 'prep.core.augmenter', message: 'LLM timeout on node "GraphEnrichmentPipeline.tsx" — retrying with reduced context (attempt 2/3)', created: baseTime - 35 },
    { timestamp: baseTime - 5, level: 'INFO', logger: 'prep.services.pipeline', message: '[Prep] Fast Sync completed in 115.2s ✓', created: baseTime - 5 },
  ];
  return (
    <DemoFrame height={420}>
      <LogConsole logs={logs} onClear={noop} />
    </DemoFrame>
  );
}

// Deterministic PRNG for stable SSR/client render of the heatmap.
// Math.random() differs between server and client renders → hydration mismatch.
// Mulberry32 seeded with a constant gives the same sequence every time.
function mulberry32(seed: number) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

const HEATMAP_DENSE_DATA = (() => {
  const rng = mulberry32(0xc0de);
  const today = new Date('2026-05-17T00:00:00Z');
  const days = Array.from({ length: 84 }, (_, i) => {
    const date = new Date(today);
    date.setUTCDate(today.getUTCDate() - (83 - i));
    const isWeekend = date.getUTCDay() === 0 || date.getUTCDay() === 6;
    return {
      date: date.toISOString().split('T')[0],
      embeddings: isWeekend ? Math.floor(rng() * 20) : Math.floor(rng() * 80) + 20,
      trace: Math.floor(rng() * 50) + 10,
      builds: Math.floor(rng() * 5),
    };
  });
  return { days, totals: { embeddings: 4567, trace: 2341, builds: 156 } };
})();

export function DemoActivityHeatmapMixed() {
  // ActivityHeatmap renders its own Card chrome; use bordered={false}.
  return (
    <DemoFrame bordered={false}>
      <ActivityHeatmap data={HEATMAP_DENSE_DATA} weeks={12} showLegend showLabels />
    </DemoFrame>
  );
}

export function DemoAgentOpsActive() {
  return (
    <DemoFrame>
      <AgentOpsPanel
        data={{
          hr: { last_run: '2 hours ago', push_count: 5 },
          researcher: { last_run: '45 min ago', push_count: 3 },
          custodian: { last_run: '1 day ago', push_count: 0 },
        }}
        loading={false}
        onHRGenerate={noop}
        onResearchRun={noop}
        onCustodianRun={noop}
        pushSettings={{ auto_push: true, min_significance: 'recommended', paperclip_project: '' }}
        onPushSettingsUpdate={noop}
      />
    </DemoFrame>
  );
}

export function DemoSyncStatusUpToDate() {
  const now = Date.now() / 1000;
  return (
    <DemoFrame bordered={false}>
      <SyncStatusCard
        status={{
          enabled: true,
          is_syncing: false,
          error: null,
          last_sync_at: now - 300,
          last_sync_commit: 'a1b2c3d4e5f6789012345678',
          remote_version: 42,
          remote_timestamp: now - 300,
          behind_minutes: 0,
        }}
        onSyncNow={noop}
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Layout / PanelPicker
// ────────────────────────────────────────────────────────────────────────────

const PANEL_PICKER_DEFS: PanelDefinition[] = [
  { id: 'status', title: 'Index Status', icon: Database, minHeight: 2, defaultHeight: 2, category: 'status', closeable: true },
  { id: 'build', title: 'Build', icon: Hammer, minHeight: 2, defaultHeight: 2, category: 'status', closeable: true },
  { id: 'search', title: 'Search', icon: Search, minHeight: 2, defaultHeight: 3, category: 'search', closeable: false },
  { id: 'context-options', title: 'Context Options', icon: SlidersHorizontal, minHeight: 1, defaultHeight: 2, category: 'context', closeable: true },
  { id: 'results', title: 'Search Results', icon: List, minHeight: 2, defaultHeight: 4, category: 'search', closeable: true },
  { id: 'context-output', title: 'Context Output', icon: FileText, minHeight: 2, defaultHeight: 4, category: 'context', closeable: true },
  { id: 'roots', title: 'Index Roots', icon: FolderTreeIcon, minHeight: 2, defaultHeight: 5, category: 'config', closeable: true },
  { id: 'settings', title: 'Settings', icon: Settings2, minHeight: 2, defaultHeight: 4, category: 'config', closeable: true },
];

const createPanelLayout = (visibleIds: string[]): DashboardLayout => ({
  version: 1,
  panels: PANEL_PICKER_DEFS.map((def) => ({
    id: def.id,
    visible: visibleIds.includes(def.id),
    height: def.defaultHeight,
    collapsed: false,
  })),
});

export function DemoPanelPicker() {
  const [layout, setLayout] = useState<DashboardLayout>(
    createPanelLayout(['status', 'build', 'search', 'results'])
  );
  return (
    <DemoFrame>
      <PanelPicker
        layout={layout}
        panelDefinitions={PANEL_PICKER_DEFS}
        onTogglePanel={(panelId) =>
          setLayout((cur) => ({
            ...cur,
            panels: cur.panels.map((p) => (p.id === panelId ? { ...p, visible: !p.visible } : p)),
          }))
        }
        onResetLayout={() => setLayout(createPanelLayout(['status', 'build', 'search', 'results']))}
      />
    </DemoFrame>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Full Dashboard
// ────────────────────────────────────────────────────────────────────────────
//
// The dashboard page's hero (a full integrated ModularDashboard with ~15
// panels and complex state) is too heavy to inline into every docs route.
// The /dashboard page lazy-loads it via next/dynamic from its own file.
// See websites/apps/docs/src/components/DemoFullDashboard.tsx.
