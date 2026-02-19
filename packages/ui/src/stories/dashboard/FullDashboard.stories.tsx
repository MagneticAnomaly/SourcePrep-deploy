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
import { WatchControlPanel } from '../../components/watch/WatchControlPanel';
import { CodeViewer } from '../../components/project/CodeViewer';
import { UsageGuidePanel } from '../../components/dashboard/UsageGuidePanel';
import { DeepAnalysisSettings } from '../../components/llm/DeepAnalysisSettings';
import { LogConsole } from '../../components/console/LogConsole';

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
  { name: 'CLaRa', status: 'disabled', type: 'clara' },
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

// Use the canonical panel registry — no extra panels needed
const STORY_PANELS: PanelDefinition[] = [
  ...PANEL_REGISTRY,
];

/** Prefix for dynamically-pinned file panel IDs */
const PINNED_PREFIX = 'pinned:';

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
      'src', 'src/codrag', 'src/codrag/server.py', 'src/codrag/cli.py', 'src/codrag/__init__.py',
      'src/codrag/core', 'src/codrag/core/registry.py', 'src/codrag/core/embedding.py',
      'src/codrag/core/trace.py', 'src/codrag/core/watcher.py',
      'src/codrag/api', 'src/codrag/api/routes.py', 'src/codrag/api/auth.py',
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
            index_dir: 'LinuxBrain',
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
      watch: (
        <WatchControlPanel
          status={{ enabled: true, state: 'idle', stale: false, pending: false }}
          onStartWatch={() => {}}
          onStopWatch={() => {}}
          onRebuildNow={() => {}}
          bare
        />
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
      'trace-pipeline': (
        <div className="h-full overflow-y-auto">
          <GraphEnrichmentPipeline
            trace={{ enabled: true, exists: true, building: false, counts: { nodes: 100, edges: 200 }, last_build_at: new Date().toISOString() }}
            augmentation={{ enabled: true, total_nodes: 100, augmented_nodes: 80, validated_nodes: 0, low_confidence_count: 5, avg_confidence: 0.85 }}
            epistemic={{ enabled: true, enriched_nodes: 60, progress_current: 60, progress_total: 100, avg_confidence: 0.9, running: false }}
            isPro={true}
          />
        </div>
      ),
      'deep-analysis': (
        <div className="h-full overflow-y-auto p-4">
          <DeepAnalysisSettings
            schedule={{
              mode: 'scheduled',
              frequency: 'daily',
              hour: 0,
              budget_enabled: true,
              budget_max_tokens: 100000,
              budget_max_minutes: 60,
              budget_max_items: 500,
              priority: 'lowest_confidence'
            }}
            onScheduleChange={() => {}}
            largeModelConfigured={true}
            fastModelConfigured={true}
          />
        </div>
      ),
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
