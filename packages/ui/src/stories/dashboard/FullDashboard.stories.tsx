import type { Meta, StoryObj } from '@storybook/react';
import { useState, useMemo, useCallback, useRef } from 'react';
import { Settings, FileText } from 'lucide-react';
import { IndexStatusCard } from '../../components/dashboard/IndexStatusCard';
import { LLMStatusWidget, type LLMServiceStatus } from '../../components/dashboard/index';
import { SearchPanel } from '../../components/search/SearchPanel';
import { ContextOptionsPanel } from '../../components/search/ContextOptionsPanel';
import { SearchResultsList } from '../../components/search/SearchResultsList';
import type { SearchResult } from '../../types';
import { ChunkPreview } from '../../components/search/ChunkPreview';
import { ContextOutput } from '../../components/search/ContextOutput';
import { sampleFileTree } from '../../components/project/index';
import { FolderTreePanel } from '../../components/project/FolderTreePanel';
import { FileExplorerDetail } from '../../components/project/FileExplorerDetail';
import type { PinnedTextFile } from '../../components/project/PinnedTextFilesPanel';
import { TraceGraph, SymbolSearchInput, type TraceNode } from '../../components/trace/index';
import { GraphStructurePanel } from '../../components/trace/GraphStructurePanel';
import { GraphEnrichmentPipeline } from '../../components/trace/GraphEnrichmentPipeline';
import type { TraceCoverageFile, TraceCoverageSummary } from '../../types';
import { ModularDashboard, type DashboardLayoutApi } from '../../components/layout/ModularDashboard';
import type { PanelDefinition } from '../../types/layout';
import { CodeViewer } from '../../components/project/CodeViewer';
import { UsageGuidePanel } from '../../components/dashboard/UsageGuidePanel';
import { DeepAnalysisSettings, type DeepAnalysisSchedule } from '../../components/llm/DeepAnalysisSettings';
import { LogConsole } from '../../components/console/LogConsole';
import { ActivityHeatmap, generateSampleActivityData } from '../../components/viz/ActivityHeatmap';
import { AgentOpsPanel } from '../../components/agents/AgentOpsPanel';
import { AuditPanel } from '../../components/audit/AuditPanel';
import { OpportunitiesPanel } from '../../components/audit/OpportunitiesPanel';
import { RoadmapPanel } from '../../components/goalposts/RoadmapPanel';
import { ConceptsPanel } from '../../components/concepts/ConceptsPanel';
import type { ConceptItem, ConceptQuestionItem, ConceptStats } from '../../components/concepts/ConceptsPanel';
import { AtlasLensPanel } from '../../components/trace/AtlasLensPanel/AtlasLensPanel';
import type { AuditFinding, AuditReport, AtlasStatus } from '../../types';

const noop = () => {};

const meta: Meta = {
  title: 'Dashboard/Layouts/FullDashboard',
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
};

export default meta;

const sampleTraceNodes: TraceNode[] = [
  { id: '1', name: 'build_project', kind: 'symbol', language: 'Python', inDegree: 3, outDegree: 5 },
  { id: '2', name: 'IndexManager', kind: 'symbol', language: 'Python', inDegree: 8, outDegree: 12 },
  { id: '3', name: '/api/build', kind: 'endpoint', inDegree: 1, outDegree: 2 },
  { id: '4', name: 'server.py', kind: 'file', inDegree: 0, outDegree: 15 },
];

const sampleLLMServices: LLMServiceStatus[] = [
  { name: 'Ollama', url: 'localhost:11434', status: 'connected', type: 'ollama' },
  { name: 'Compression', status: 'connected', type: 'other' },
  { name: 'OpenAI', status: 'disconnected', type: 'openai' },
];

const mockResults: SearchResult[] = [
  {
    chunk_id: '1',
    source_path: 'src/api/client.ts',
    section: 'ApiClient.fetch',
    content: `export class ApiClient {
  private baseUrl: string;
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }
  
  async fetch<T>(endpoint: string): Promise<T> {
    const res = await fetch(\`\${this.baseUrl}\${endpoint}\`);
    if (!res.ok) throw new Error(\`HTTP \${res.status}\`);
    return res.json();
  }
}`,
    preview: 'export class ApiClient { ... }',
    span: { start_line: 1, end_line: 15 },
    score: 0.892,
  },
  {
    chunk_id: '2',
    source_path: 'src/api/errors.ts',
    section: 'handleApiError',
    content: `export function handleApiError(error: unknown): never {
  if (error instanceof ApiError) {
    console.error('API Error:', error.message);
    throw error;
  }
  throw new ApiError('Unknown error', 500);
}`,
    preview: 'export function handleApiError(error: unknown): never { ... }',
    span: { start_line: 1, end_line: 10 },
    score: 0.756,
  },
];

const mockUntracedFiles: TraceCoverageFile[] = [
  { path: 'src/api/handlers.ts', language: 'typescript', size: 4200, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
  { path: 'src/utils/logger.ts', language: 'typescript', size: 1800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'src/core/scheduler.py', language: 'python', size: 6100, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 86_400_000).toISOString() },
];

const mockStaleFiles: TraceCoverageFile[] = [
  { path: 'src/core/index.py', language: 'python', size: 8900, modified: new Date(Date.now() - 3_600_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

const mockExcludedFiles: TraceCoverageFile[] = [
  { path: 'tests/test_api.py', language: 'python', size: 3200, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
  { path: 'scripts/deploy.sh', language: null, size: 800, modified: new Date(Date.now() - 86_400_000).toISOString(), created: new Date(Date.now() - 604_800_000).toISOString() },
];

const mockCoverageSummary: TraceCoverageSummary = {
  total: 42,
  traced: 38,
  untraced: 3,
  stale: 1,
  excluded: 2,
  coverage_pct: 90.5,
  last_build_at: new Date(Date.now() - 3_600_000).toISOString(),
};

import { PANEL_REGISTRY } from '../../config/panelRegistry';

// Phase 131: filter PANEL_REGISTRY for the storybook demo.
//
// 1. Always exclude the legacy "AI Gateway" summary card (`llm-status`).
//    Phase 74 sunsetted this panel — manually-constructed state drifted from
//    real pipeline status; the sidebar AI Gateway widget is now the canonical
//    live view. Keeping it out of the demo means it never appears in either
//    private or public storybook.
//
// 2. In public mode (STORYBOOK_PUBLIC=true), additionally drop every panel
//    flagged `devOnly: true` in the registry — Spaghetti Finder, Goalposts,
//    Health Scanner, Advisor, Roadmap, Opportunities. The local developer
//    storybook keeps showing them so internal work isn't blocked.
const IS_PUBLIC = typeof process !== 'undefined' && process.env.STORYBOOK_PUBLIC === 'true';

const STORY_PANELS: PanelDefinition[] = PANEL_REGISTRY.filter((p) => {
  if (p.id === 'llm-status') return false; // deprecated
  if (IS_PUBLIC && p.devOnly) return false;
  return true;
});

/** Prefix for dynamically-pinned file panel IDs */
const PINNED_PREFIX = 'pinned:';

// ────────────────────────────────────────────────────────────────────────────
// Demo dummy data — kept generic ("Acme Search") so the showcase doesn't
// expose internal project names. The audit/atlas/concepts panels render
// healthy steady-state content (no critical findings, atlas exists, concepts
// curated).
// ────────────────────────────────────────────────────────────────────────────

const mockAuditFindings: AuditFinding[] = [
  {
    finding_id: 'a1',
    analyzer: 'doc-coverage',
    severity: 'info',
    category: 'coverage',
    title: 'README missing usage section',
    description: 'The repo README has install steps but no usage examples.',
    file_paths: ['README.md'],
    evidence: {},
    suggested_action: 'Add a "Usage" section with two or three short examples.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a2',
    analyzer: 'todo-scanner',
    severity: 'info',
    category: 'quality',
    title: '3 TODOs in core/',
    description: 'Outstanding TODO comments tracked for the next sprint.',
    file_paths: ['src/core/embedder.py', 'src/core/cache.py'],
    evidence: { todo_count: 3 },
    suggested_action: 'Triage and convert to issues or close.',
    priority: 'P3',
    effort: 'small',
  },
  {
    finding_id: 'a3',
    analyzer: 'oversized-files',
    severity: 'warning',
    category: 'size',
    title: 'cache.ts is 22KB',
    description: 'Approaching the 25KB soft ceiling we use as a refactor signal.',
    file_paths: ['src/core/cache.ts'],
    evidence: { size_bytes: 22_400 },
    suggested_action: 'Split caching policy into its own module.',
    priority: 'P2',
    effort: 'medium',
  },
  {
    finding_id: 'a4',
    analyzer: 'stale-docs',
    severity: 'suggestion',
    category: 'coverage',
    title: 'CHANGELOG.md last touched 6 months ago',
    description: 'No entries since the v0.4 release.',
    file_paths: ['CHANGELOG.md'],
    evidence: {},
    suggested_action: 'Backfill recent feature work or auto-generate from PR titles.',
    priority: 'P3',
    effort: 'small',
  },
];

const mockAuditReports: AuditReport[] = [
  { name: 'Audit · 2026-04-29', filename: 'audit_20260429.md', size_bytes: 18_240 },
  { name: 'Audit · 2026-04-15', filename: 'audit_20260415.md', size_bytes: 17_760 },
];

const mockConcepts: ConceptItem[] = [
  {
    id: 'c1',
    title: 'Local-first by default',
    content: 'All indexing and inference run locally. Cloud endpoints are opt-in via BYOK.',
    category: 'architecture',
    status: 'active',
    confidence: 0.95,
    anchors: ['src/core/indexer.py', 'src/llm/router.py'],
    tags: ['privacy', 'principle'],
    created_at: Date.now() / 1000 - 86_400 * 14,
  },
  {
    id: 'c2',
    title: 'Structural retrieval over vector-only',
    content: 'Search blends vector similarity with structural graph traversal so results stay grounded in import/dependency edges.',
    category: 'architecture',
    status: 'active',
    confidence: 0.92,
    anchors: ['src/search/router.ts', 'src/graph/walker.py'],
    tags: ['search', 'differentiator'],
    created_at: Date.now() / 1000 - 86_400 * 7,
  },
  {
    id: 'c3',
    title: 'Auto-rebuild is debounced + storm-protected',
    content: 'File-watcher coalesces bursts and applies a per-project storm cap so a vendored dependency drop does not thrash the indexer.',
    category: 'constraint',
    status: 'active',
    confidence: 0.89,
    anchors: ['src/watch/coalescer.ts'],
    tags: ['watch', 'reliability'],
    created_at: Date.now() / 1000 - 86_400 * 4,
  },
  {
    id: 'c4',
    title: 'Token budget caps every LLM call',
    content: 'Every cloud or local LLM invocation is bounded by an explicit per-call token budget. No unbounded prompts ship.',
    category: 'constraint',
    status: 'active',
    confidence: 0.97,
    anchors: ['src/llm/budget.ts'],
    tags: ['safety', 'cost'],
    created_at: Date.now() / 1000 - 86_400 * 2,
  },
  {
    id: 'c5',
    title: 'Sample seed concept — adjust me',
    content: 'Newly seeded concept awaiting human review.',
    category: 'general',
    status: 'seed',
    confidence: 0.6,
    anchors: [],
    tags: [],
    created_at: Date.now() / 1000 - 3_600,
  },
];

const mockConceptQuestions: ConceptQuestionItem[] = [
  {
    id: 'q1',
    question: 'Should the cache layer expose a hit-rate metric?',
    context: 'Several call sites read from src/core/cache without observability.',
    suggested_category: 'observability',
    target_module: 'core/cache',
    answered: false,
  },
];

const mockConceptStats: ConceptStats = {
  total: 5,
  active: 4,
  seeds: 1,
  archived: 0,
  stale: 0,
  pending_questions: 1,
  by_category: { architecture: 2, constraint: 2, general: 1 },
  coverage_pct: 78,
  total_modules: 14,
  covered_modules: 11,
  concepts_count: 5,
};

const mockAtlas: AtlasStatus = {
  exists: true,
  content: null,
  mode: 'structural',
  module_count: 12,
  file_count: 1100,
  routing: true,
  stale: false,
};

/**
 * Pipeline panel for the storybook demo. Renders the GraphEnrichmentPipeline
 * in a "healthy / fully-built" state with all 10 stages complete, and wires
 * local React state for the three group-collapse toggles AND the
 * fast/deep/finalize Manual/Auto switches. The component itself is purely
 * controlled — without a state-bearing wrapper its chevrons and switches
 * are no-ops.
 */
function PipelinePanelDemo() {
  const [fastCollapsed, setFastCollapsed] = useState(true);
  const [deepCollapsed, setDeepCollapsed] = useState(true);
  const [finalizeCollapsed, setFinalizeCollapsed] = useState(true);
  const [autoConfig, setAutoConfig] = useState<{
    fastSync: boolean;
    deepEnrichment: 'manual' | 'auto' | 'scheduled' | 'threshold';
    finalize: 'manual' | 'auto';
  }>({ fastSync: true, deepEnrichment: 'auto', finalize: 'manual' });

  const TOTAL = 1245;
  const built = new Date(Date.now() - 7_200_000).toISOString(); // 2h ago

  return (
    <div className="h-full overflow-y-auto">
      <GraphEnrichmentPipeline
        trace={{
          enabled: true,
          exists: true,
          building: false,
          counts: { nodes: TOTAL, edges: 3890 },
          last_build_at: built,
        }}
        inferredEdges={{ enabled: true, exists: true, edge_count: 42 }}
        augmentation={{
          enabled: true,
          total_nodes: TOTAL,
          augmented_nodes: TOTAL,
          validated_nodes: TOTAL,
          avg_confidence: 0.88,
          low_confidence_count: 0,
          last_augment_at: built,
          model: 'qwen2.5:3b',
        }}
        epistemic={{
          enabled: true,
          enriched_nodes: TOTAL,
          progress_current: TOTAL,
          progress_total: TOTAL,
          avg_confidence: 0.92,
          running: false,
        }}
        modules={{
          enabled: true,
          module_count: 12,
          total_files_clustered: 1100,
          running: false,
        }}
        atlas={{
          exists: true,
          content: null,
          mode: 'structural',
          module_count: 12,
          file_count: 1100,
          routing: true,
          stale: false,
        }}
        deepening={{
          running: false,
          total_scored: TOTAL,
          settled_count: TOTAL,
          settled_ratio: 1.0,
          avg_score: 0.91,
        }}
        knowledge={{
          enabled: true,
          running: false,
          chunks_embedded: 3200,
          deep_chunks_embedded: 3200,
          last_run_at: built,
        }}
        autoConfig={autoConfig}
        onAutoConfigChange={setAutoConfig}
        fastCollapsed={fastCollapsed}
        deepCollapsed={deepCollapsed}
        finalizeCollapsed={finalizeCollapsed}
        onToggleFastCollapsed={() => setFastCollapsed((c) => !c)}
        onToggleDeepCollapsed={() => setDeepCollapsed((c) => !c)}
        onToggleFinalizeCollapsed={() => setFinalizeCollapsed((c) => !c)}
        isPro={true}
        onRebuild={(scope) => console.log('[Story] onRebuild', scope)}
        onStopRebuild={() => console.log('[Story] onStopRebuild')}
        onRunFastSync={() => console.log('[Story] onRunFastSync')}
        onRunDeepEnrichment={() => console.log('[Story] onRunDeepEnrichment')}
        onRunFinalize={() => console.log('[Story] onRunFinalize')}
      />
    </div>
  );
}

/**
 * Stateful demo wrapper for DeepAnalysisSettings — without it the mode/
 * frequency/hour selects feel stuck when clicked.
 */
function DeepAnalysisDemo() {
  const [schedule, setSchedule] = useState<DeepAnalysisSchedule>({
    mode: 'scheduled',
    frequency: 'daily',
    hour: 0,
    budget_enabled: true,
    budget_max_tokens: 100000,
    budget_max_minutes: 60,
    budget_max_items: 500,
    priority: 'lowest_confidence',
  });
  return (
    <div className="h-full overflow-y-auto p-4">
      <DeepAnalysisSettings
        schedule={schedule}
        onScheduleChange={setSchedule}
        largeModelConfigured={true}
        fastModelConfigured={true}
      />
    </div>
  );
}

/** Stateful demo wrapper for AtlasLensPanel role picker. */
function AtlasPanelDemo() {
  const [role, setRole] = useState<string | null>(null);
  return (
    <AtlasLensPanel
      atlas={mockAtlas}
      role={role}
      onRoleChange={setRole}
      regenerating={false}
      onRegenerate={() => console.log('[Story] onRegenerate atlas')}
    />
  );
}

/** Stateful demo wrapper for OpportunitiesPanel filter dropdowns + show-dismissed toggle. */
function OpportunitiesPanelDemo() {
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [showDismissed, setShowDismissed] = useState(false);
  return (
    <OpportunitiesPanel
      items={[]}
      summary={null}
      loading={false}
      refreshing={false}
      error={null}
      onRefresh={() => console.log('[Story] onRefresh opportunities')}
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
  );
}

/** Stateful demo wrapper for ConceptsPanel — approve/archive/delete remove rows visually. */
function ConceptsPanelDemo() {
  const [concepts, setConcepts] = useState<ConceptItem[]>(mockConcepts);
  const [questions, setQuestions] = useState<ConceptQuestionItem[]>(mockConceptQuestions);
  const handleApprove = (id: string) =>
    setConcepts((cs) => cs.map((c) => (c.id === id ? { ...c, status: 'active' } : c)));
  const handleArchive = (id: string) =>
    setConcepts((cs) => cs.map((c) => (c.id === id ? { ...c, status: 'archived' } : c)));
  const handleDelete = (id: string) =>
    setConcepts((cs) => cs.filter((c) => c.id !== id));
  const handleAnswer = (questionId: string) =>
    setQuestions((qs) => qs.map((q) => (q.id === questionId ? { ...q, answered: true } : q)));
  return (
    <ConceptsPanel
      concepts={concepts}
      questions={questions}
      stats={mockConceptStats}
      loading={false}
      initializing={false}
      error={null}
      onInitialize={noop}
      onApprove={handleApprove}
      onArchive={handleArchive}
      onDelete={handleDelete}
      onAnswerQuestion={handleAnswer}
    />
  );
}

/** Generate mock file content for Storybook */
function mockFileContent(path: string): string {
  const name = path.split('/').pop() ?? path;
  if (name.endsWith('.md')) {
    return `# ${name}\n\nThis is the content of \`${path}\`.\n\n## Overview\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit.\nSed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n`;
  }
  return `# ${path}\n# Auto-generated mock content\n\ndef example():\n    """Example function from ${name}."""\n    print("Hello from ${name}")\n    return True\n`;
}

export const FullDashboard: StoryObj = {
  render: () => {
    // Phase 131: every visit to the storybook demo should boot from the
    // canonical DEFAULT_LAYOUT in packages/ui/src/types/layout.ts (the same
    // config the dashboard app ships with). Clear any saved customisation
    // BEFORE useLayoutPersistence reads from localStorage on mount.
    useState(() => {
      try {
        window.localStorage.removeItem('storybook_fulldashboard_layout');
      } catch {
        // localStorage may be blocked in some sandboxed iframes; that's fine.
      }
      return null;
    });

    const [building, setBuilding] = useState(false);

    const [query, setQuery] = useState('');
    const [searchK, setSearchK] = useState(8);
    const [minScore, setMinScore] = useState(0.15);
    const [searchLoading, setSearchLoading] = useState(false);
    const [results, setResults] = useState<SearchResult[]>([]);
    const [selectedChunk, setSelectedChunk] = useState<SearchResult | null>(null);
    const [selectedTraceNode, setSelectedTraceNode] = useState<string>('1');
    const [symbolQuery, setSymbolQuery] = useState('');
    
    const [contextK, setContextK] = useState(5);
    const [maxChars, setMaxChars] = useState(6000);
    const [includeSources, setIncludeSources] = useState(true);
    const [includeScores, setIncludeScores] = useState(false);
    const [structured, setStructured] = useState(false);
    const [context, setContext] = useState('');

    // RAG inclusion state (primary functionality)
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(new Set([
      'src', 'src/prep', 'src/prep/server.py', 'src/prep/cli.py', 'src/prep/__init__.py',
      'src/prep/core', 'src/prep/core/registry.py', 'src/prep/core/embedding.py',
      'src/prep/core/trace.py', 'src/prep/core/watcher.py',
      'src/prep/api', 'src/prep/api/routes.py', 'src/prep/api/auth.py',
      'docs', 'docs/ARCHITECTURE.md', 'docs/API.md', 'docs/ROADMAP.md',
      // Note: docs/CHANGELOG.md is NOT included — it has status 'indexed' so it will show "Removing"
    ]));

    const handleToggleInclude = useCallback((paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const path of paths) {
          if (action === 'remove') {
            next.delete(path);
          } else {
            next.add(path);
          }
        }
        return next;
      });
    }, []);

    // Path weights state
    const [pathWeights, setPathWeights] = useState<Record<string, number>>({});

    const handleWeightChange = useCallback((path: string, weight: number | null) => {
      setPathWeights((prev) => {
        const next = { ...prev };
        if (weight === null) {
          delete next[path];
        } else {
          next[path] = weight;
        }
        return next;
      });
    }, []);

    // Pinned files state — each pinned file becomes its own dashboard panel
    const [pinnedFiles, setPinnedFiles] = useState<PinnedTextFile[]>([]);
    const layoutApiRef = useRef<DashboardLayoutApi | null>(null);

    const handlePinFile = useCallback((path: string) => {
      const name = path.split('/').pop() || 'unknown';
      const content = mockFileContent(path);
      const panelId = `${PINNED_PREFIX}${path}`;

      setPinnedFiles((prev) => {
        if (prev.some((f) => f.id === path)) return prev;
        return [...prev, { id: path, path, name, content }];
      });

      // Add a visible panel to the grid
      layoutApiRef.current?.addPanel(panelId, { height: 8, w: 6 });
    }, []);

    const handleUnpinFile = useCallback((pathOrPanelId: string) => {
      // Accept either a raw path or a "pinned:path" panel ID
      const path = pathOrPanelId.startsWith(PINNED_PREFIX)
        ? pathOrPanelId.slice(PINNED_PREFIX.length)
        : pathOrPanelId;
      const panelId = `${PINNED_PREFIX}${path}`;

      setPinnedFiles((prev) => prev.filter((f) => f.id !== path));
      layoutApiRef.current?.removePanel(panelId);
    }, []);

    const handlePanelClose = useCallback((panelId: string) => {
      if (panelId.startsWith(PINNED_PREFIX)) {
        handleUnpinFile(panelId);
      }
    }, [handleUnpinFile]);

    const pinnedPathsSet = useMemo(() => new Set(pinnedFiles.map((f) => f.id)), [pinnedFiles]);

    const handleBuild = () => {
      setBuilding(true);
      setTimeout(() => setBuilding(false), 2000);
    };

    const handleSearch = () => {
      setSearchLoading(true);
      setTimeout(() => {
        setResults(mockResults);
        setSearchLoading(false);
      }, 800);
    };

    const handleGetContext = () => {
      setContext('# Source: src/api/client.ts ...');
    };

    const panelContent = useMemo(() => ({
      'usage-guide': (
        <UsageGuidePanel bare />
      ),
      status: (
        <IndexStatusCard
          stats={{
            loaded: true,
            total_documents: 1234,
            model: 'nomic-embed-text',
            built_at: new Date().toISOString(),
            index_dir: 'acme-search',
          }}
          building={building}
          onBuild={handleBuild}
          bare
        />
      ),
      'llm-status': (
        <LLMStatusWidget services={sampleLLMServices} bare />
      ),
      search: (
        <SearchPanel
          query={query}
          onQueryChange={setQuery}
          k={searchK}
          onKChange={setSearchK}
          minScore={minScore}
          onMinScoreChange={setMinScore}
          onSearch={handleSearch}
          loading={searchLoading}
          bare
        />
      ),
      'context-options': (
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
          onGetContext={handleGetContext}
          onCopyContext={() => navigator.clipboard.writeText(context)}
          hasContext={!!context}
          disabled={!query.trim()}
          bare
        />
      ),
      results: (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full overflow-hidden">
          <div className="h-full overflow-y-auto min-h-0">
            <SearchResultsList
              results={results}
              selectedId={selectedChunk?.chunk_id}
              onSelect={setSelectedChunk}
            />
          </div>
          <div className="h-full overflow-y-auto min-h-0 border-l border-border pl-4">
            <ChunkPreview
              content={selectedChunk?.content}
              sourcePath={selectedChunk?.source_path}
              section={selectedChunk?.section}
              bare
            />
          </div>
        </div>
      ),
      'context-output': (
        <ContextOutput
          context={context}
          meta={context ? { chunks: [], total_chars: context.length, estimated_tokens: 100 } : null}
          bare
        />
      ),
      'file-tree': (
        <FolderTreePanel
          data={sampleFileTree}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
          className="h-full border-0 shadow-none"
          title="Index Scope"
          bare
        />
      ),
      // Dynamic per-file pinned panels
      ...Object.fromEntries(
        pinnedFiles.map((f) => [
          `${PINNED_PREFIX}${f.path}`,
          <div key={f.path} className="h-full flex flex-col overflow-hidden">
            <CodeViewer 
              content={f.content} 
              path={f.path}
              className="h-full border-0 rounded-none"
            />
          </div>,
        ])
      ),
      trace: (
        <div className="h-full flex flex-col">
          <div className="mb-4">
            <SymbolSearchInput 
              value={symbolQuery}
              onChange={setSymbolQuery}
            />
          </div>
          <div className="flex-1 min-h-0">
            <TraceGraph 
              nodes={sampleTraceNodes} 
              edges={[]} 
              selectedNode={selectedTraceNode}
              onSelectNode={setSelectedTraceNode}
            />
          </div>
        </div>
      ),
      'graph-structure': (
        <GraphStructurePanel
          summary={mockCoverageSummary}
          epistemic={{ enabled: true, enriched_nodes: 569, avg_confidence: 0.9, running: false }}
          augmentation={{ enabled: true, total_nodes: 670, augmented_nodes: 670, validated_nodes: 600, avg_confidence: 0.95, low_confidence_count: 0 }}
          untracedFiles={mockUntracedFiles}
          staleFiles={mockStaleFiles}
          excludedFiles={mockExcludedFiles}
          building={false}
          loading={false}
          onTraceAll={() => console.log('[Story] Trace All')}
          onRetraceStale={() => console.log('[Story] Re-trace Stale')}
          onAddExcludePattern={(p: string) => console.log('[Story] Add exclude:', p)}
          onRemoveExcludePattern={(p: string) => console.log('[Story] Remove exclude:', p)}
          onRefresh={() => console.log('[Story] Refresh')}
          traceExists={true}
        />
      ),
      'trace-pipeline': <PipelinePanelDemo />,
      'deep-analysis': <DeepAnalysisDemo />,
      'log-console': (
        <LogConsole
          logs={[
            { timestamp: Date.now() / 1000, level: 'INFO', logger: 'daemon', message: 'Daemon started', created: Date.now() / 1000 },
            { timestamp: Date.now() / 1000, level: 'INFO', logger: 'project', message: 'Project loaded', created: Date.now() / 1000 },
          ]}
          onClear={() => {}}
          defaultExpanded={true}
          className="h-full border-none shadow-none bg-transparent"
        />
      ),
      'activity-heatmap': (
        <ActivityHeatmap
          data={generateSampleActivityData(12)}
          weeks={12}
          showLegend={true}
          showLabels={true}
          className="h-full border-none shadow-none bg-transparent"
        />
      ),
      'agent-ops': (
        <AgentOpsPanel 
          data={{ hr: { last_run: '2h ago', push_count: 5 }, researcher: { last_run: null, push_count: 0 }, custodian: { last_run: '1d ago', push_count: 0 } }}
          loading={false} 
        />
      ),
      'audit': (
        <AuditPanel
          status={{
            running: false,
            error: null,
            has_results: true,
            finding_count: mockAuditFindings.length,
            severity_counts: { critical: 0, warning: 1, info: 2, suggestion: 1 },
            last_run: {
              generated_at: new Date(Date.now() - 1_800_000).toISOString(),
              graph_node_count: 1245,
              graph_edge_count: 3890,
              finding_count: mockAuditFindings.length,
              document_count: 0,
              analyzers_run: ['stale-docs', 'todo-scanner', 'oversized-files', 'doc-coverage'],
              documents: [],
            },
          }}
          findings={mockAuditFindings}
          reports={mockAuditReports}
          onRunAudit={noop}
          onViewReport={noop}
        />
      ),
      'concepts': <ConceptsPanelDemo />,
      'atlas': <AtlasPanelDemo />,
      'opportunities': <OpportunitiesPanelDemo />,
      'roadmap': (
        <RoadmapPanel 
          nodes={[]} 
          questions={[]} 
          northStar={null} 
          appEthos="SourcePrep Ethos" 
          generating={false} 
          scanning={false} 
          error={null} 
          ready={true} 
          lastGeneratedAt="" 
          modelUsed=""
          onGenerate={noop}
          onScanTodos={noop}
          onUpdateEthos={noop}
          onPromoteNode={noop}
          onDismissNode={noop}
          onDeleteNode={noop}
          onCreateNode={noop}
          onAnswerQuestion={noop}
          onSuggestSprint={noop}
          onMineRoadmap={noop}
        />
      ),
    }), [building, query, searchK, minScore, searchLoading, results, selectedChunk, contextK, maxChars, includeSources, includeScores, structured, context, symbolQuery, selectedTraceNode, includedPaths, pinnedFiles, handleToggleInclude, pathWeights, handleWeightChange]);

    // Dynamic panel definitions for pinned files
    const dynamicPanelDefs = useMemo<PanelDefinition[]>(() =>
      pinnedFiles.map((f) => ({
        id: `${PINNED_PREFIX}${f.path}`,
        title: f.name,
        icon: FileText,
        minHeight: 4,
        defaultHeight: 8,
        category: 'projects' as const,
        closeable: true,
        resizable: true,
      })),
      [pinnedFiles]
    );

    const allPanelDefs = useMemo(
      () => [...STORY_PANELS, ...dynamicPanelDefs],
      [dynamicPanelDefs]
    );

    const panelDetails = useMemo(() => ({
      'llm-status': (
        <div className="p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Settings className="w-6 h-6" />
            LLM Settings
          </h2>
          <div className="p-4 bg-surface-raised rounded-lg border border-border">
            Mock AIModelsSettings content would go here.
          </div>
        </div>
      ),
      'file-tree': (
        <FileExplorerDetail
          treeData={sampleFileTree}
          pinnedPaths={pinnedPathsSet}
          onPinFile={handlePinFile}
          onUnpinFile={handleUnpinFile}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
        />
      ),
    }), [includedPaths, pinnedPathsSet, handleToggleInclude, handlePinFile, handleUnpinFile, pathWeights, handleWeightChange]);

    return (
      <div className="min-h-screen bg-background p-6">
        <ModularDashboard
          panelDefinitions={allPanelDefs}
          panelContent={panelContent}
          panelDetails={panelDetails}
          storageKey="storybook_fulldashboard_layout"
          onPanelClose={handlePanelClose}
          onLayoutReady={(api) => { layoutApiRef.current = api; }}
          hidePanelPicker
        />
      </div>
    );
  },
};

export const EmptyState: StoryObj = {
  render: () => {
    const panelContent = {
      status: (
        <div className="p-4">
          <IndexStatusCard stats={{ loaded: false }} bare />
        </div>
      ),
      search: (
        <div className="p-4">
          <SearchPanel
            query=""
            onQueryChange={() => {}}
            k={8}
            onKChange={() => {}}
            minScore={0.15}
            onMinScoreChange={() => {}}
            onSearch={() => {}}
            disabled
            bare
          />
        </div>
      ),
    };

    return (
      <div className="min-h-screen bg-background p-6">
        <ModularDashboard
          panelDefinitions={STORY_PANELS}
          panelContent={panelContent}
          storageKey="storybook_emptystate_layout"
        />
      </div>
    );
  },
};
