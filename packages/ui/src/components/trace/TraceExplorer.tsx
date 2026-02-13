import { useState, useCallback } from 'react';
import { Search, GitBranch, FileCode, Box, ArrowRight, ArrowLeft, Loader2, AlertCircle, Info } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { ProgressIndicator } from '../status/ProgressIndicator';
import type { TaskProgress } from '../../types';

export interface TraceExplorerProps {
  /** Whether trace is enabled for this project */
  traceEnabled: boolean;
  /** Whether trace index exists */
  traceExists: boolean;
  /** Whether trace is currently building */
  traceBuilding: boolean;
  /** Progress of current build */
  progress?: TaskProgress;
  /** Node/edge counts */
  traceCounts: { nodes: number; edges: number };
  /** Search for symbols */
  onSearchTrace: (query: string, kinds?: string[], limit?: number) => Promise<{ nodes: any[] }>;
  /** Get node details */
  onGetNode: (nodeId: string) => Promise<{ node: any; in_degree: number; out_degree: number }>;
  /** Get node neighbors */
  onGetNeighbors: (nodeId: string, direction?: string) => Promise<{ nodes: any[]; edges: any[] }>;
  /** Trigger trace build */
  onBuildTrace: () => void;
  /** Enable trace */
  onEnableTrace?: () => void;
  /** Which engine is active: 'rust' or 'python' */
  engine?: string;
  className?: string;
}

const KIND_ICONS: Record<string, typeof Box> = {
  file: FileCode,
  symbol: Box,
  external_module: GitBranch,
};

const KIND_COLORS: Record<string, string> = {
  file: 'text-blue-500',
  symbol: 'text-amber-500',
  external_module: 'text-purple-500',
};

function SymbolTypeTag({ type }: { type?: string }) {
  if (!type) return null;
  const colors: Record<string, string> = {
    function: 'bg-green-500/10 text-green-600 border-green-500/20',
    async_function: 'bg-green-500/10 text-green-600 border-green-500/20',
    class: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    method: 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20',
    async_method: 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20',
    struct: 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20',
    enum: 'bg-violet-500/10 text-violet-600 border-violet-500/20',
    trait: 'bg-pink-500/10 text-pink-600 border-pink-500/20',
    interface: 'bg-pink-500/10 text-pink-600 border-pink-500/20',
    namespace: 'bg-slate-500/10 text-slate-600 border-slate-500/20',
    module: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
    import: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
    variable: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
  };
  return (
    <span className={cn(
      'text-[10px] font-medium px-1.5 py-0.5 rounded border',
      colors[type] ?? 'bg-text-subtle/10 text-text-muted border-border'
    )}>
      {type}
    </span>
  );
}

export function TraceExplorer({
  traceEnabled,
  traceExists,
  traceBuilding,
  traceCounts,
  progress,
  onSearchTrace,
  onGetNode,
  onGetNeighbors,
  onBuildTrace: _onBuildTrace,
  onEnableTrace,
  engine,
  className,
}: TraceExplorerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [nodeDetail, setNodeDetail] = useState<{ node: any; in_degree: number; out_degree: number } | null>(null);
  const [neighbors, setNeighbors] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setError(null);
    setSelectedNode(null);
    setNodeDetail(null);
    setNeighbors(null);
    try {
      const data = await onSearchTrace(searchQuery.trim(), undefined, 30);
      setSearchResults(data.nodes ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed');
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [searchQuery, onSearchTrace]);

  const handleSelectNode = useCallback(async (node: any) => {
    setSelectedNode(node);
    setLoadingDetail(true);
    setError(null);
    try {
      const [detail, nbrs] = await Promise.all([
        onGetNode(node.id),
        onGetNeighbors(node.id, 'both'),
      ]);
      setNodeDetail(detail);
      setNeighbors(nbrs);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load node details');
    } finally {
      setLoadingDetail(false);
    }
  }, [onGetNode, onGetNeighbors]);

  const handleNavigateToNode = useCallback(async (nodeId: string) => {
    setLoadingDetail(true);
    setError(null);
    try {
      const [detail, nbrs] = await Promise.all([
        onGetNode(nodeId),
        onGetNeighbors(nodeId, 'both'),
      ]);
      setSelectedNode(detail.node);
      setNodeDetail(detail);
      setNeighbors(nbrs);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to navigate to node');
    } finally {
      setLoadingDetail(false);
    }
  }, [onGetNode, onGetNeighbors]);

  // Not enabled state
  if (!traceEnabled) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full text-center p-8', className)}>
        <GitBranch className="w-10 h-10 text-text-muted opacity-40 mb-4" />
        <h3 className="text-sm font-semibold text-text mb-2">Code Graph Disabled</h3>
        <p className="text-xs text-text-muted mb-4 max-w-xs">
          Enable the code graph to browse symbols, imports, and call relationships in your codebase.
        </p>
        {onEnableTrace && (
          <Button size="sm" onClick={onEnableTrace}>Enable Map</Button>
        )}
      </div>
    );
  }

  // Not built state
  if (!traceExists && !traceBuilding) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full text-center p-8', className)}>
        <GitBranch className="w-10 h-10 text-text-muted opacity-40 mb-4" />
        <h3 className="text-sm font-semibold text-text mb-2">Code Graph Not Built</h3>
        <p className="text-xs text-text-muted max-w-xs">
          Use the Graph Enrichment panel to build the trace graph.
        </p>
      </div>
    );
  }

  // Building state
  if (traceBuilding) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full text-center p-8', className)}>
        {progress ? (
          <div className="w-full max-w-xs space-y-4">
            <ProgressIndicator progress={progress} />
            <p className="text-xs text-text-muted">Parsing symbols and resolving relationships</p>
          </div>
        ) : (
          <>
            <Loader2 className="w-8 h-8 text-primary animate-spin mb-4" />
            <h3 className="text-sm font-semibold text-text mb-1">Building Code Graph...</h3>
            <p className="text-xs text-text-muted">Parsing symbols and resolving relationships</p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header stats */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border shrink-0 text-xs text-text-muted">
        <span>{traceCounts.nodes.toLocaleString()} symbols</span>
        <span className="text-border">•</span>
        <span>{traceCounts.edges.toLocaleString()} relationships</span>
        {engine && (
          <span className={cn(
            'ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium',
            engine === 'rust'
              ? 'bg-green-500/10 text-green-600 border border-green-500/20'
              : 'bg-amber-500/10 text-amber-600 border border-amber-500/20'
          )}>
            {engine === 'rust' ? 'Rust Engine' : 'Python (limited)'}
          </span>
        )}
      </div>

      {/* Degraded graph warning */}
      {traceCounts.nodes > 0 && traceCounts.edges === 0 && (
        <div className="px-4 py-2 text-xs flex items-start gap-2 border-b border-border bg-amber-500/5 text-amber-700">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <div>
            <span className="font-medium">No relationships found.</span>{' '}
            {engine === 'python'
              ? 'The Python fallback engine only extracts relationships for .py files. Install the Rust engine for full cross-language support.'
              : 'Try rebuilding the code graph — relationships are extracted from imports, calls, and containment.'}
          </div>
        </div>
      )}

      {/* Search bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
        <div className="flex-1 relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search symbols, functions, classes..."
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary/50 text-text placeholder:text-text-muted"
          />
        </div>
        <Button size="sm" onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
          {searching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Search'}
        </Button>
      </div>

      {error && (
        <div className="px-4 py-2 text-xs text-error flex items-center gap-1.5 border-b border-border bg-error/5">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Main content: results list + detail pane */}
      <div className="flex-1 min-h-0 flex">
        {/* Results list */}
        <div className="w-1/2 border-r border-border overflow-y-auto custom-scrollbar">
          {searchResults.length === 0 && !searching && (
            <div className="flex flex-col items-center justify-center h-full text-text-muted text-xs p-6 text-center">
              <Search className="w-6 h-6 opacity-30 mb-2" />
              <p>Search for symbols to explore the code graph</p>
            </div>
          )}
          {searchResults.map((node) => {
            const Icon = KIND_ICONS[node.kind] ?? Box;
            const color = KIND_COLORS[node.kind] ?? 'text-text-muted';
            const isSelected = selectedNode?.id === node.id;
            return (
              <button
                key={node.id}
                onClick={() => handleSelectNode(node)}
                className={cn(
                  'w-full text-left px-3 py-2 border-b border-border/50 hover:bg-surface-raised transition-colors',
                  isSelected && 'bg-primary/5 border-l-2 border-l-primary'
                )}
              >
                <div className="flex items-center gap-2">
                  <Icon className={cn('w-3.5 h-3.5 shrink-0', color)} />
                  <span className="text-sm font-mono text-text truncate">{node.name}</span>
                  <SymbolTypeTag type={node.metadata?.symbol_type} />
                </div>
                <div className="text-[10px] text-text-muted mt-0.5 truncate pl-5">
                  {node.file_path}
                  {node.span ? `:${node.span.start_line}` : ''}
                </div>
              </button>
            );
          })}
        </div>

        {/* Detail pane */}
        <div className="w-1/2 overflow-y-auto custom-scrollbar">
          {loadingDetail ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
            </div>
          ) : nodeDetail ? (
            <div className="p-4 space-y-4">
              {/* Node header */}
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-base font-mono font-semibold text-text">{nodeDetail.node.name}</span>
                  <SymbolTypeTag type={nodeDetail.node.metadata?.symbol_type} />
                </div>
                <div className="text-xs text-text-muted font-mono">
                  {nodeDetail.node.file_path}
                  {nodeDetail.node.span ? `:${nodeDetail.node.span.start_line}-${nodeDetail.node.span.end_line}` : ''}
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
                  <span className="flex items-center gap-1" title="Number of other symbols that reference this one (callers, importers)">
                    <ArrowLeft className="w-3 h-3" /> {nodeDetail.in_degree} {nodeDetail.in_degree === 1 ? 'reference' : 'references'} in
                  </span>
                  <span className="flex items-center gap-1" title="Number of symbols this one depends on (calls, imports)">
                    <ArrowRight className="w-3 h-3" /> {nodeDetail.out_degree} {nodeDetail.out_degree === 1 ? 'dependency' : 'dependencies'} out
                  </span>
                  {nodeDetail.node.language && (
                    <span className="text-text-subtle">{nodeDetail.node.language}</span>
                  )}
                </div>
              </div>

              {/* Docstring */}
              {nodeDetail.node.metadata?.docstring && (
                <div className="text-xs text-text-muted bg-surface rounded-md p-2 border border-border">
                  {nodeDetail.node.metadata.docstring}
                </div>
              )}

              {/* Neighbors */}
              {neighbors && (neighbors.nodes.length > 1 || neighbors.edges.length > 0) && (
                <div>
                  <h4 className="text-xs font-semibold text-text mb-2">Connections</h4>
                  <div className="space-y-1">
                    {neighbors.edges.map((edge: any, i: number) => {
                      const isOutgoing = edge.source === nodeDetail.node.id;
                      const targetId = isOutgoing ? edge.target : edge.source;
                      const targetNode = neighbors.nodes.find((n: any) => n.id === targetId);
                      if (!targetNode || targetNode.id === nodeDetail.node.id) return null;
                      const Icon = KIND_ICONS[targetNode.kind] ?? Box;
                      const color = KIND_COLORS[targetNode.kind] ?? 'text-text-muted';
                      return (
                        <button
                          key={edge.id || i}
                          onClick={() => handleNavigateToNode(targetNode.id)}
                          className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-raised transition-colors group"
                        >
                          {isOutgoing ? (
                            <ArrowRight className="w-3 h-3 text-text-subtle shrink-0" />
                          ) : (
                            <ArrowLeft className="w-3 h-3 text-text-subtle shrink-0" />
                          )}
                          <Icon className={cn('w-3 h-3 shrink-0', color)} />
                          <span className="text-xs font-mono text-text truncate group-hover:text-primary transition-colors">
                            {targetNode.name}
                          </span>
                          <span className="text-[10px] text-text-subtle ml-auto shrink-0">
                            {edge.kind}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-text-muted text-xs p-6 text-center">
              <Box className="w-6 h-6 opacity-30 mb-2" />
              <p>Select a symbol to view details and connections</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
