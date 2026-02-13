import { Folder, Database, Activity, AlertCircle, FileText, Code2, AlignLeft, RefreshCw, Play, GitBranch, BookOpen } from 'lucide-react';
import { Card, Flex, Badge, Title, Text, Divider } from '@tremor/react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
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
  className?: string;
  bare?: boolean;
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
  className,
  bare = false,
}: IndexStatusCardProps) {
  const Container = bare ? 'div' : Card;
  
  // Calculate stats
  const totalFiles = (stats.build?.files_code || 0) + (stats.build?.files_docs || 0);
  
  const linesIndexed = stats.build?.lines_indexed || 0;
  const linesTotal = stats.build?.lines_scanned || 0;
  const coveragePercent = linesTotal > 0 ? Math.round((linesIndexed / linesTotal) * 100) : 0;

  // Line-level type breakdown (fall back to file counts if line data absent)
  const hasLineBreakdown = (stats.build?.lines_docs ?? 0) + (stats.build?.lines_code ?? 0) > 0;
  const breakdownTotal = hasLineBreakdown
    ? (stats.build!.lines_docs! + stats.build!.lines_code!)
    : totalFiles;
  const codeValue = hasLineBreakdown ? (stats.build!.lines_code ?? 0) : (stats.build?.files_code || 0);
  const docsValue = hasLineBreakdown ? (stats.build!.lines_docs ?? 0) : (stats.build?.files_docs || 0);
  const codePercent = breakdownTotal > 0 ? (codeValue / breakdownTotal) * 100 : 0;
  const docsPercent = breakdownTotal > 0 ? (docsValue / breakdownTotal) * 100 : 0;
  const breakdownUnit = hasLineBreakdown ? 'lines' : 'files';

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
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          {!bare && <Folder className="w-8 h-8 text-primary shrink-0 mt-0.5" />}
          <div className="min-w-0 flex-1">
            {!bare && (
              <div className="flex items-center gap-2">
                <Title className="text-text">Knowledge Base</Title>
                <InfoTooltip 
                  content="Learn about the local indexing engine." 
                  href="https://docs.codrag.io/concepts/indexing" 
                />
              </div>
            )}
            <Text 
              className={cn("font-mono text-sm text-text-subtle break-words", bare && "text-xs")}
              title={stats.index_dir}
            >
              {stats.index_dir || 'No project loaded'}
            </Text>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-1">
          {onBuild && (
            <Button
              variant={stale ? "default" : "outline"}
              size="sm"
              onClick={onBuild}
              disabled={building || !stats.index_dir}
              className={cn(
                "h-6 px-2 text-xs gap-1.5",
                stale && "bg-amber-500/10 text-amber-500 border-amber-500/20 hover:bg-amber-500/20 hover:border-amber-500/30"
              )}
            >
              {building ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <Play className="w-3 h-3" />
              )}
              {building ? 'Building' : stale ? 'Rebuild' : 'Rebuild'}
            </Button>
          )}

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
      </div>
      
      {effectiveProgress && (
        <div className="mt-4">
          <ProgressIndicator progress={effectiveProgress} />
        </div>
      )}
      
      <Divider className="my-4" />
      
      <div className="space-y-4">
        {/* Chunk Breakdown Row */}
        <Flex className="gap-5 flex-wrap">
          <div className="flex items-center gap-1.5 text-sm text-text-muted" title="Code chunks (source files)">
            <Code2 className="w-3.5 h-3.5 text-blue-400" />
            <span className="font-medium text-text">{formatNumber(stats.build?.chunks_code ?? stats.total_documents ?? 0)}</span>
            <span className="text-xs">Code</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-text-muted" title="Instructions chunks (.md, docs, plans, research)">
            <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-medium text-text">{formatNumber(stats.build?.chunks_docs ?? 0)}</span>
            <span className="text-xs">Instructions</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-text-muted" title="Trace chunks (code graph embeddings)">
            <GitBranch className="w-3.5 h-3.5 text-purple-400" />
            <span className="font-medium text-text">{formatNumber(traceChunks)}</span>
            <span className="text-xs">Graph</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-text-subtle" title="Total chunks">
            <Database className="w-3 h-3" />
            {formatNumber(stats.total_documents ?? 0)} total
          </div>
          
          {(stats.build?.lines_indexed !== undefined) && (
            <div className="flex items-center gap-2 text-sm text-text-muted" title={`Indexed ${formatNumber(linesIndexed)} of ${formatNumber(linesTotal)} indexable lines (${coveragePercent}% coverage)`}>
              <AlignLeft className="w-4 h-4 text-primary" />
              <span className="font-medium text-text">{formatNumber(linesIndexed)}</span>
              <span className="text-text-subtle">/</span>
              <span>{formatNumber(linesTotal)}</span> lines
              <span className="text-xs text-text-subtle">({coveragePercent}%)</span>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-text-muted" title={`Embedding Model: ${stats.model}`}>
            <Activity className="w-4 h-4 text-primary" />
            <span className="truncate max-w-[150px]">{stats.model ?? 'No model'}</span>
          </div>
        </Flex>

        {/* Code vs Docs Distribution */}
        {breakdownTotal > 0 && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-text-subtle">
              <span className="flex items-center gap-1.5">
                <Code2 className="w-3 h-3" />
                Code {Math.round(codePercent)}%
                {hasLineBreakdown && <span className="opacity-60">({formatNumber(codeValue)} lines)</span>}
              </span>
              <span className="flex items-center gap-1.5">
                <FileText className="w-3 h-3" />
                Docs {Math.round(docsPercent)}%
                {hasLineBreakdown && <span className="opacity-60">({formatNumber(docsValue)} lines)</span>}
              </span>
            </div>
            <div className="h-1.5 w-full bg-surface-raised rounded-full overflow-hidden flex">
              <div 
                className="h-full bg-blue-500/70" 
                style={{ width: `${codePercent}%` }} 
              />
              <div 
                className="h-full bg-emerald-500/70" 
                style={{ width: `${docsPercent}%` }} 
              />
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
