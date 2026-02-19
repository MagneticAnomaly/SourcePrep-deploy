import { Folder, Database, AlertCircle, Code2, RefreshCw, Play, GitBranch, BookOpen } from 'lucide-react';
import { SlidingSwitch2 } from '../primitives/SlidingSwitch';
import { Card, Badge, Text, Divider } from '@tremor/react';
import { cn } from '../../lib/utils';
import { ProgressIndicator } from '../status/ProgressIndicator';
import type { TaskProgress } from '../../types';

export interface IndexBuildStats {
  mode: string;
  files_total: number;
  files_reused: number;
  files_embedded: number;
  files_deleted: number;
  chunks_total: number;
  chunks_code?: number;
  chunks_docs?: number;
  lines_scanned?: number;
  lines_indexed?: number;
  files_docs?: number;
  files_code?: number;
  lines_docs?: number;
  lines_code?: number;
}

export interface IndexStats {
  loaded: boolean;
  index_dir?: string;
  model?: string;
  built_at?: string;
  total_documents?: number;
  embedding_dim?: number;
  build?: IndexBuildStats;
}

export interface IndexStatusCardProps {
  stats: IndexStats;
  building?: boolean;
  stale?: boolean;
  progress?: TaskProgress;
  lastError?: string | null;
  onBuild?: () => void;
  traceChunks?: number;
  /** Whether auto-rebuild is enabled */
  autoRebuild?: boolean;
  /** Called when auto-rebuild toggle changes */
  onAutoRebuildChange?: (auto: boolean) => void;
  /** Whether user has pro plan (free users get manual-only) */
  isPro?: boolean;
  className?: string;
  bare?: boolean;
  /** Whether to hide the distribution chart (e.g. during transient completion state) */
  hideChart?: boolean;
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
  return num.toString();
}

/**
 * IndexStatusCard - Shows the current state of the code index.
 */
export function IndexStatusCard({
  stats,
  building = false,
  stale = false,
  progress,
  lastError,
  onBuild,
  traceChunks = 0,
  autoRebuild,
  onAutoRebuildChange,
  isPro = false,
  className,
  bare = false,
  hideChart = false,
}: IndexStatusCardProps) {
  const showAutoToggle = onAutoRebuildChange !== undefined;
  // Free users are forced to Manual regardless of stored value
  const isAuto = isPro ? (autoRebuild ?? false) : false;
  const Container = bare ? 'div' : Card;
  
  // Calculate stats
  const totalFiles = (stats.build?.files_code || 0) + (stats.build?.files_docs || 0);
  
  // Chart basis: Prefer Chunks for apples-to-apples comparison if Graph is present.
  // Otherwise fall back to lines (if available) or files.
  const codeChunks = stats.build?.chunks_code ?? 0;
  const docsChunks = stats.build?.chunks_docs ?? 0;
  const graphChunks = traceChunks;
  
  const hasLineBreakdown = (stats.build?.lines_docs ?? 0) + (stats.build?.lines_code ?? 0) > 0;
  
  // If we have graph chunks, we use chunks as the common unit for the bar
  const useChunks = graphChunks > 0 || (!hasLineBreakdown);
  
  const codeValue = useChunks ? codeChunks : (stats.build!.lines_code ?? 0);
  const docsValue = useChunks ? docsChunks : (stats.build!.lines_docs ?? 0);
  const graphValue = useChunks ? graphChunks : 0; // Graph doesn't have lines
  
  const breakdownTotal = codeValue + docsValue + graphValue;
  
  const codePercent = breakdownTotal > 0 ? (codeValue / breakdownTotal) * 100 : 0;
  const docsPercent = breakdownTotal > 0 ? (docsValue / breakdownTotal) * 100 : 0;
  const graphPercent = breakdownTotal > 0 ? (graphValue / breakdownTotal) * 100 : 0;
  
  const breakdownUnit = useChunks ? 'chunks' : (hasLineBreakdown ? 'lines' : 'files');

  // Construct effective progress for display
  // If building but no progress object yet, show indeterminate
  const effectiveProgress = progress || (building ? {
    task_id: 'pending',
    message: 'Starting build...',
    current: 0,
    total: 100,
    percent: 0,
    status: 'running'
  } as TaskProgress : undefined);

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', className)}>
      {/* Row 1: File path (full width, single line) */}
      <div className="flex items-center gap-2 min-w-0">
        {!bare && <Folder className="w-5 h-5 text-primary shrink-0" />}
        <Text 
          className={cn("font-mono text-text-subtle truncate min-w-0 flex-1", bare ? "text-[11px]" : "text-xs")}
          title={stats.index_dir}
        >
          {stats.index_dir || 'No project loaded'}
        </Text>
      </div>

      {/* Row 2: Controls — rebuild + toggle + badge */}
      <div className="flex items-center gap-2 mt-2">
        {/* Auto/Manual toggle */}
        {showAutoToggle && (
          <SlidingSwitch2
            value={isAuto}
            onChange={onAutoRebuildChange}
            disabled={!isPro}
            disabledReason="Upgrade to Pro to enable auto-rebuild"
          />
        )}

        {/* Initialize (both modes when not built) / Rebuild (manual only when built) */}
        {onBuild && (!stats.loaded || !isAuto) && (
          <button
            onClick={onBuild}
            disabled={building}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
              building
                ? "border-border bg-surface text-text-subtle cursor-wait"
                : !stats.loaded
                  ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20" // Initialize style
                  : stale
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
                    : "border-success/40 bg-success/10 text-success hover:bg-success/20"
            )}
          >
            {building ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : !stats.loaded ? (
              <Play className="w-3.5 h-3.5 fill-current" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            {building ? 'Building…' : !stats.loaded ? 'Initialize' : 'Rebuild'}
          </button>
        )}

        <div className="flex-1" />

        {/* Status badge */}
        {building ? (
          <Badge color="blue">Building</Badge>
        ) : stats.loaded && !stale ? (
          <Badge color="green">Fresh</Badge>
        ) : stats.loaded && stale ? (
          <Badge color="yellow">Stale</Badge>
        ) : (
          <Badge color="gray">Not Built</Badge>
        )}
      </div>
      
      {effectiveProgress && (
        <div className="mt-4">
          <ProgressIndicator progress={effectiveProgress} />
        </div>
      )}
      
      <Divider className="my-2.5" />
      
      <div className="space-y-3">
        {/* Chunk stats grid: 2×2 */}
        <div className="grid grid-cols-2 gap-y-3 gap-x-6 text-sm">
          <div className="flex items-center gap-2 py-1" title="Code chunks (source files)">
            <Code2 className="w-4 h-4 text-blue-400 shrink-0" />
            <span className="font-semibold text-text tabular-nums w-10 text-right">{formatNumber(stats.build?.chunks_code ?? stats.total_documents ?? 0)}</span>
            <span className="text-text-muted">Code</span>
          </div>
          <div className="flex items-center gap-2 py-1" title="Instructions chunks (.md, docs, plans, research)">
            <BookOpen className="w-4 h-4 text-success shrink-0" />
            <span className="font-semibold text-text tabular-nums w-10 text-right">{formatNumber(stats.build?.chunks_docs ?? 0)}</span>
            <span className="text-text-muted">Docs</span>
          </div>
          <div className="flex items-center gap-2 py-1" title="Trace chunks (code graph embeddings)">
            <GitBranch className="w-4 h-4 text-purple-400 shrink-0" />
            <span className="font-semibold text-text tabular-nums w-10 text-right">{formatNumber(traceChunks)}</span>
            <span className="text-text-muted">Graph</span>
          </div>
          <div className="flex items-center gap-2 py-1" title="Total chunks in knowledge base">
            <Database className="w-4 h-4 text-text-subtle shrink-0" />
            <span className="font-semibold text-text tabular-nums w-10 text-right">{formatNumber(stats.total_documents ?? 0)}</span>
            <span className="text-text-muted">Total</span>
          </div>
        </div>

        {/* Code vs Docs vs Graph Distribution */}
        {breakdownTotal > 0 && !hideChart && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-text-subtle">
              <span className="flex items-center gap-1.5">
                <Code2 className="w-3 h-3 text-blue-500" />
                Code {Math.round(codePercent)}%
                {hasLineBreakdown && !useChunks && <span className="opacity-60">({formatNumber(codeValue)} lines)</span>}
              </span>
              <span className="flex items-center gap-1.5">
                <BookOpen className="w-3 h-3 text-success" />
                Docs {Math.round(docsPercent)}%
                {hasLineBreakdown && !useChunks && <span className="opacity-60">({formatNumber(docsValue)} lines)</span>}
              </span>
              {graphValue > 0 && (
                <span className="flex items-center gap-1.5">
                  <GitBranch className="w-3 h-3 text-purple-500" />
                  Graph {Math.round(graphPercent)}%
                </span>
              )}
            </div>
            <div className="h-1.5 w-full bg-surface-raised rounded-full overflow-hidden flex">
              <div 
                className="h-full bg-blue-500/70" 
                style={{ width: `${codePercent}%` }} 
              />
              <div 
                className="h-full bg-success/70" 
                style={{ width: `${docsPercent}%` }} 
              />
              {graphValue > 0 && (
                <div 
                  className="h-full bg-purple-500/70" 
                  style={{ width: `${graphPercent}%` }} 
                />
              )}
            </div>
            {!hasLineBreakdown && totalFiles > 0 && (
              <div className="text-[10px] text-text-subtle/60 italic">by {breakdownUnit}</div>
            )}
          </div>
        )}
      </div>

      {lastError && (
        <div className="mt-4 flex gap-2 p-3 rounded-md bg-error-muted/10 border border-error-muted/20 text-error">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="text-sm font-medium break-all">
            {lastError}
          </span>
        </div>
      )}
    </Container>
  );
}
