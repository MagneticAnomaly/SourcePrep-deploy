import { useState, useCallback, useRef, useEffect } from 'react';
import {
  FileCode,
  Clock,
  AlertTriangle,
  EyeOff,
  Search,
  Play,
  RefreshCw,
  X,
  Plus,
  Loader2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import { ProgressIndicator } from '../status/ProgressIndicator';
import type { TraceCoverageFile, TraceCoverageSummary, TaskProgress } from '../../types';

export interface TraceCoveragePanelProps {
  /** Coverage summary stats */
  summary: TraceCoverageSummary | null;
  /** Untraced files (eligible but not yet traced) */
  untracedFiles: TraceCoverageFile[];
  /** Stale files (traced but content changed) */
  staleFiles: TraceCoverageFile[];
  /** Excluded files (excluded by user-configured patterns) */
  excludedFiles: TraceCoverageFile[];
  /** Whether trace is currently building */
  building: boolean;
  /** Progress of current build */
  progress?: TaskProgress;
  /** Whether coverage data is loading */
  loading: boolean;
  /** Trigger trace build for all untraced/stale files */
  onTraceAll: () => void;
  /** Trigger re-trace for stale files only */
  onRetraceStale: () => void;
  /** Add an exclude pattern */
  onAddExcludePattern: (pattern: string) => void;
  /** Remove an exclude pattern (un-exclude a file) */
  onRemoveExcludePattern: (pattern: string) => void;
  /** Refresh coverage data */
  onRefresh: () => void;
  /** Whether the trace graph has been initialized */
  traceExists?: boolean;
  className?: string;
  /** When true, omits the panel header (title/refresh) — PanelChrome provides chrome */
  bare?: boolean;
}

const LANG_LABELS: Record<string, string> = {
  python: 'Python',
  typescript: 'TypeScript',
  javascript: 'JavaScript',
  go: 'Go',
  rust: 'Rust',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
};

function formatTimeAgo(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return date.toLocaleDateString();
}

function CoverageBar({ summary, building }: { summary: TraceCoverageSummary; building: boolean }) {
  const { traced, stale, total } = summary;
  // Use pending_embedding from summary if available (added in backend)
  const pendingEmbedding = summary.pending_embedding || 0;
  
  if (total === 0) return null;

  // When building, treat pending items as "in-progress"
  // If we have specific pending_embedding count, include it.
  const inProgress = building 
    ? summary.untraced + stale + pendingEmbedding 
    : pendingEmbedding;
    
  const displayStale = building ? 0 : stale;
  const displayUntraced = building ? 0 : summary.untraced;
  
  // The progress bar total should reflect the sum of the components shown.
  // When building, everything not traced is "in-progress", so the numerator is traced + inProgress.
  // When not building, the numerator is just traced + pendingEmbedding.
  const displayNumerator = building ? (traced + inProgress) : (traced + pendingEmbedding);

  const tracedPct = (traced / total) * 100;
  const inProgressPct = (inProgress / total) * 100;
  const stalePct = (displayStale / total) * 100;
  const untracedPct = (displayUntraced / total) * 100;
  
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>{displayNumerator}/{total} files traced</span>
        <span className="font-mono font-semibold text-text">{building ? '99.9%' : `${summary.coverage_pct}%`}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-raised overflow-hidden flex">
        {tracedPct > 0 && (
          <div
            className="bg-success transition-all duration-500"
            style={{ width: `${tracedPct}%` }}
            title={`${traced} traced & embedded`}
          />
        )}
        {inProgressPct > 0 && (
          <div
            className="bg-primary transition-all duration-500 relative"
            style={{ width: `${inProgressPct}%` }}
            title={`${inProgress} in-progress`}
          >
            <div className="absolute inset-0 bg-white/20 animate-pulse" />
          </div>
        )}
        {stalePct > 0 && (
          <div
            className="bg-warning transition-all duration-500"
            style={{ width: `${stalePct}%` }}
            title={`${displayStale} stale`}
          />
        )}
        {untracedPct > 0 && (
          <div
            className="bg-text-subtle/20 transition-all duration-500"
            style={{ width: `${untracedPct}%` }}
            title={`${displayUntraced} untraced`}
          />
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-success" /> {traced} traced & embedded
        </span>
        {inProgress > 0 ? (
          <span className="flex items-center gap-1 font-medium text-primary">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" /> {inProgress} in-progress
          </span>
        ) : null}
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-warning" /> {displayStale} stale
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-text-subtle/30" /> {displayUntraced} untraced
        </span>
      </div>
    </div>
  );
}

/** Threshold (px) below which the language badge column is hidden */
const COMPACT_WIDTH_THRESHOLD = 380;

function FileRow({
  file,
  timeField,
  actionLabel,
  onAction,
  compact = false,
}: {
  file: TraceCoverageFile;
  timeField: 'modified' | 'created';
  actionLabel?: string;
  onAction?: (path: string) => void;
  compact?: boolean;
}) {
  const langLabel = file.language ? (LANG_LABELS[file.language] || file.language) : null;
  const timeValue = timeField === 'modified' ? file.modified : file.created;
  const timeLabel = timeField === 'modified' ? 'Modified' : 'Created';

  return (
    <div className="group flex items-center gap-2 px-3 py-1.5 hover:bg-surface-raised rounded-md transition-colors">
      <FileCode className="w-3.5 h-3.5 text-text-subtle shrink-0" />
      <span className="text-xs font-mono text-text truncate flex-1" title={file.path}>
        {file.path}
      </span>
      <span className="text-[10px] text-text-muted shrink-0 whitespace-nowrap">
        {timeLabel}: {formatTimeAgo(timeValue)}
      </span>
      {!compact && langLabel && (
        <span className="text-[10px] text-text-subtle bg-surface-raised px-1.5 py-0.5 rounded shrink-0">
          {langLabel}
        </span>
      )}
      {actionLabel && onAction && (
        <Button
          variant="ghost"
          size="sm"
          className="text-[10px] h-5 px-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
          onClick={() => onAction(file.path)}
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

function CollapsibleSection({
  title,
  count,
  icon: Icon,
  iconColor,
  action,
  children,
  defaultOpen = true,
}: {
  title: string;
  count: number;
  icon: typeof AlertTriangle;
  iconColor: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  if (count === 0) return null;

  return (
    <div>
      <button
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-surface-raised rounded-md transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-text-subtle shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-text-subtle shrink-0" />
        )}
        <Icon className={cn('w-3.5 h-3.5 shrink-0', iconColor)} />
        <span className="text-xs font-semibold text-text">{title}</span>
        <span className="text-[10px] text-text-muted font-mono">({count})</span>
        {action && <span className="ml-auto">{action}</span>}
      </button>
      {open && <div className="ml-2">{children}</div>}
    </div>
  );
}

export function TraceCoveragePanel({
  summary,
  untracedFiles,
  staleFiles,
  excludedFiles = [],
  building,
  progress,
  loading,
  onTraceAll,
  onRetraceStale: _onRetraceStale,
  onAddExcludePattern,
  onRemoveExcludePattern,
  onRefresh,
  traceExists = false,
  className,
  bare = false,
}: TraceCoveragePanelProps) {
  const [activeTab, setActiveTab] = useState<'queue' | 'excluded'>('queue');
  const [excludeInput, setExcludeInput] = useState('');
  const [compact, setCompact] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setCompact(entry.contentRect.width < COMPACT_WIDTH_THRESHOLD);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleAddExclude = useCallback(() => {
    const pattern = excludeInput.trim();
    if (pattern) {
      onAddExcludePattern(pattern);
      setExcludeInput('');
    }
  }, [excludeInput, onAddExcludePattern]);

  const handleExcludeKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleAddExclude();
      if (e.key === 'Escape') setExcludeInput('');
    },
    [handleAddExclude]
  );

  const queueCount = untracedFiles.length + staleFiles.length;

  return (
    <div ref={containerRef} className={cn('flex flex-col h-full', className)}>
      {/* Header — only shown when NOT bare (standalone mode) */}
      {!bare && (
        <div className="px-4 pt-4 pb-3 border-b border-border space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text flex items-center gap-2">
              <FileCode className="w-4 h-4" />
              Graph Status
              <InfoTooltip 
                content="Learn about the Code Graph and coverage." 
                href="https://docs.sourceprep.io/concepts/code-graph" 
              />
            </h3>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onRefresh}
              disabled={loading}
              className="h-6 w-6"
              title="Refresh coverage"
            >
              <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
            </Button>
          </div>
        </div>
      )}

      {/* Coverage summary bar */}
      <div className={cn('space-y-2', bare ? 'px-3 pt-2 pb-1' : 'px-4 py-3 border-b border-border')}>
        {loading && !summary ? (
          <div className="flex items-center gap-2 text-xs text-text-muted py-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Loading coverage data...
          </div>
        ) : summary ? (
          <CoverageBar summary={summary} building={building} />
        ) : null}

        {building && (
          <div className="bg-primary/5 px-3 py-2 rounded-md">
            {progress ? (
              <ProgressIndicator progress={progress} />
            ) : (
              <div className="flex items-center gap-2 text-xs text-primary">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {traceExists && summary && summary.untraced === 0 ? 'Updating to reflect codebase changes...' : 'Building knowledge graph...'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tabs + single Update action — see GraphStructurePanel for the
          full rationale. Both onTraceAll and onRetraceStale upstream
          resolve to the same Fast Sync call, so this surfaces one
          button covering all drift. */}
      <div className="flex items-center border-b border-border">
        <button
          className={cn(
            'text-xs font-medium py-2 px-3 transition-colors border-b-2',
            activeTab === 'queue'
              ? 'border-primary text-primary'
              : 'border-transparent text-text-muted hover:text-text'
          )}
          onClick={() => setActiveTab('queue')}
        >
          <span className="flex items-center justify-center gap-1.5">
            Queue
            {queueCount > 0 && (
              <span className="text-[10px] bg-warning/15 text-warning px-1.5 py-0.5 rounded-full font-mono">
                {queueCount}
              </span>
            )}
          </span>
        </button>
        <button
          className={cn(
            'text-xs font-medium py-2 px-3 transition-colors border-b-2',
            activeTab === 'excluded'
              ? 'border-primary text-primary'
              : 'border-transparent text-text-muted hover:text-text'
          )}
          onClick={() => setActiveTab('excluded')}
        >
          <span className="flex items-center justify-center gap-1.5">
            <EyeOff className="w-3.5 h-3.5" />
            Excluded
            {excludedFiles.length > 0 && (
              <span className="text-[10px] bg-text-subtle/15 text-text-subtle px-1.5 py-0.5 rounded-full font-mono">
                {excludedFiles.length}
              </span>
            )}
          </span>
        </button>
        {queueCount > 0 && traceExists && (
          <Button
            variant="pill"
            tone={building ? 'default' : 'success'}
            className="ml-auto mr-2"
            onClick={onTraceAll}
            disabled={building}
          >
            <Play className="w-3 h-3" />
            {building ? 'Updating…' : 'Update'}
          </Button>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        {activeTab === 'queue' && (
          <div className="p-2 space-y-1">
            {queueCount === 0 && !loading ? (
              <div className="flex flex-col items-center justify-center py-8 text-text-muted">
                <FileCode className="w-8 h-8 mb-2 opacity-30" />
                <p className="text-xs font-medium">All files traced</p>
                <p className="text-[10px] mt-1">No pending or stale files</p>
              </div>
            ) : (
              <>
                <CollapsibleSection
                  title="Untraced"
                  count={untracedFiles.length}
                  icon={Clock}
                  iconColor="text-text-subtle"
                  defaultOpen={true}
                >
                  {untracedFiles.map((f) => (
                    <FileRow key={f.path} file={f} timeField="created" compact={compact} />
                  ))}
                </CollapsibleSection>

                <CollapsibleSection
                  title="Stale"
                  count={staleFiles.length}
                  icon={AlertTriangle}
                  iconColor="text-warning"
                  defaultOpen={true}
                >
                  {staleFiles.map((f) => (
                    <FileRow key={f.path} file={f} timeField="modified" compact={compact} />
                  ))}
                </CollapsibleSection>
              </>
            )}
          </div>
        )}

        {activeTab === 'excluded' && (
          <div className="p-2 space-y-2">
            {/* Add exclude pattern input */}
            <div className="flex items-center gap-1.5 px-2">
              <div className="flex-1 flex items-center gap-1.5 bg-surface border border-border rounded-md px-2 py-1">
                <Search className="w-3.5 h-3.5 text-text-subtle shrink-0" />
                <input
                  type="text"
                  value={excludeInput}
                  onChange={(e) => setExcludeInput(e.target.value)}
                  onKeyDown={handleExcludeKeyDown}
                  placeholder="Add exclude pattern (e.g. **/tests/**)"
                  className="flex-1 text-xs bg-transparent outline-none text-text placeholder:text-text-subtle"
                />
                {excludeInput && (
                  <button
                    onClick={() => setExcludeInput('')}
                    className="text-text-subtle hover:text-text"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                className="h-7 w-7 shrink-0"
                onClick={handleAddExclude}
                disabled={!excludeInput.trim()}
                title="Add pattern"
              >
                <Plus className="w-3.5 h-3.5" />
              </Button>
            </div>

            {excludedFiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-text-muted">
                <EyeOff className="w-8 h-8 mb-2 opacity-30" />
                <p className="text-xs font-medium">No excluded files</p>
                <p className="text-[10px] mt-1">Add patterns above to exclude files from tracing</p>
              </div>
            ) : (
              <div>
                {excludedFiles.map((f) => (
                  <FileRow
                    key={f.path}
                    file={f}
                    timeField="modified"
                    actionLabel="Include"
                    onAction={(path) => onRemoveExcludePattern(path)}
                    compact={compact}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer with last build time */}
      {summary?.last_build_at && (
        <div className="px-4 py-2 border-t border-border text-[10px] text-text-muted">
          Last updated: {formatTimeAgo(summary.last_build_at)}
        </div>
      )}
    </div>
  );
}
