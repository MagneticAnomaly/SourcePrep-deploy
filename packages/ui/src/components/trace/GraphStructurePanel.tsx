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
import { ProgressIndicator } from '../status/ProgressIndicator';
import type { TraceCoverageFile, TraceCoverageSummary, TaskProgress, EpistemicStatus, AugmentationStatus, ModuleStatus, KnowledgeEmbeddingStatus } from '../../types';

export interface GraphStructurePanelProps {
  /** Coverage summary stats */
  summary: TraceCoverageSummary | null;
  /** Epistemic status for Deep Enrichment bar */
  epistemic?: EpistemicStatus;
  /** Augmentation status for node counts */
  augmentation?: AugmentationStatus;
  /** Module status — needed to determine if deep enrichment pipeline completed */
  moduleStatus?: ModuleStatus;
  /** Knowledge status — needed to determine if Stage 8 completed */
  knowledgeStatus?: KnowledgeEmbeddingStatus;
  /** Untraced files (eligible but not yet traced) */
  untracedFiles: TraceCoverageFile[];
  /** Stale files (traced but content changed) */
  staleFiles: TraceCoverageFile[];
  /** Traced files (already in the graph). F-53: surfaced in the Queue tab
   *  empty state so the user can see what's currently in scope when there's
   *  no pending work, instead of just rendering "All files traced". */
  tracedFiles?: TraceCoverageFile[];
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
  const pendingEmbedding = summary.pending_embedding || 0;
  
  if (total === 0) return null;

  // Phase 48: pending_embedding files are traced by the parser but NOT embedded
  // by the knowledge index (docs, storybook artifacts, non-code files, etc.).
  // These will never be embedded — don't show them as permanent "in-progress".
  // When idle: count them as "traced" (they ARE traced, just not vector-embedded).
  // When building: treat untraced + stale as in-progress (actively being worked on).
  const inProgress = building 
    ? summary.untraced + stale
    : 0;
    
  const displayStale = building ? 0 : stale;
  
  // Numerator: traced + pending_embedding (both are successfully traced files)
  const displayNumerator = traced + pendingEmbedding;

  // Green bar includes traced + pendingEmbedding (both are successfully traced)
  const allTracedCount = traced + pendingEmbedding;
  // §9.3 #33 PR-F F1 — defensive clamp. Same bug class as the 5501% Fast
  // Catalogue chip PR-D fixed; the sibling TraceCoveragePanel's CoverageBar
  // has the identical fix applied in this PR.
  const tracedPct = Math.min(100, (allTracedCount / total) * 100);
  const inProgressPct = Math.min(100, (inProgress / total) * 100);
  const stalePct = Math.min(100, (displayStale / total) * 100);
  
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>{displayNumerator}/{total} files traced</span>
        <span className="font-mono font-semibold text-text">{building ? '99.9%' : `${summary.coverage_pct}%`}</span>
      </div>
      {/* When building, the bar turns blue (primary) to indicate pipeline in progress.
           When idle, it's green (success) to indicate everything is complete.
           This prevents a misleading all-green bar during active pipeline runs
           where all files are traced but Edge Discovery / Catalogue are still running. */}
      <div className="h-2 rounded-full bg-surface-raised overflow-hidden flex">
        {tracedPct > 0 && (
          <div
            className={cn(
              "transition-all duration-500",
              "bg-success"
            )}
            style={{ width: `${tracedPct}%` }}
            title={`${allTracedCount} traced`}
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
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-text-muted">
        {building ? (
          <>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-success" /> {allTracedCount} traced & embedded
            </span>
            <span className="flex items-center gap-1 font-medium text-primary">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" /> {inProgress} in-progress
            </span>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-success" /> {allTracedCount} traced & embedded
            </span>
            {inProgress > 0 ? (
              <span className="flex items-center gap-1 font-medium text-primary">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse" /> {inProgress} in-progress
              </span>
            ) : null}
          </>
        )}
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-warning" /> {displayStale} stale
        </span>
      </div>
    </div>
  );
}

function DeepCoverageBar({ 
  epistemic, 
  augmentation,
  moduleStatus,
  knowledgeStatus,
}: { 
  epistemic: EpistemicStatus; 
  augmentation?: AugmentationStatus;
  moduleStatus?: ModuleStatus;
  knowledgeStatus?: KnowledgeEmbeddingStatus;
}) {
  // Epistemic enrichment only produces file: entries — use total_file_nodes as denominator.
  // total_nodes includes sections/symbols/external_modules that are never enriched.
  const total = epistemic.total_file_nodes || augmentation?.total_nodes || epistemic.total_nodes || epistemic.enriched_nodes;
  const enriched = Math.min(epistemic.enriched_nodes, total);
  
  if (total === 0) return null;

  // Use pipeline_running (any deep stage 5-8 active) rather than running (Stage 5 only)
  const pipelineRunning = epistemic.pipeline_running || epistemic.running;

  // Full deep enrichment = modules synthesized + knowledge re-embedded (Stage 8 done)
  // We use this to gate the "Purple" completion state.
  // - Must have modules (Stage 6)
  // - Must have deep chunks (Stage 8 artifacts)
  // - Must NOT be currently running (pipeline active) -> keeps it "In Progress" (Cyan) until finished
  const deepComplete = (moduleStatus?.module_count ?? 0) > 0 && 
    (knowledgeStatus?.deep_chunks_embedded ?? 0) > 0 &&
    !pipelineRunning;

  // F-76: Two-tone bar uses the incremental baseline as the stable
  // "previously complete" count during an active rebuild. Without this,
  // pipelineRunning collapses the entire bar to the in-progress color even
  // though only a handful of new items actually need work.
  //
  // Priority for the baseline:
  //   1. epistemic.progress_baseline (live slot progress, set by scheduler)
  //   2. epistemic.incremental_baseline (persisted in manifest, survives restart)
  //   3. enriched (the current enriched count, which is the historical ceiling)
  const incBaseline = Math.min(
    total,
    epistemic.progress_baseline ??
      epistemic.incremental_baseline ??
      enriched,
  );

  let displayEnriched: number;
  let displayInProgress: number;

  if (deepComplete) {
    // Pipeline idle and fully done — show all enriched as violet, pending as zero.
    displayEnriched = enriched;
    displayInProgress = 0;
  } else if (pipelineRunning) {
    // Active rebuild — keep the previously-complete baseline as violet so the
    // bar stays mostly full, and only show the true delta as cyan/in-progress.
    displayEnriched = incBaseline;
    displayInProgress = Math.max(0, total - incBaseline);
  } else {
    // Stalled/partial (not running, not fully complete) — mark enriched items
    // as in-progress so the user sees the pipeline is incomplete.
    displayEnriched = 0;
    displayInProgress = enriched;
  }

  const enrichedPct = (displayEnriched / total) * 100;
  const inProgressPct = (displayInProgress / total) * 100;

  return (
    <div className="flex flex-col gap-1.5 mt-4 pt-4 border-t border-border/50">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          {enriched}/{total} nodes {deepComplete ? 'enriched & embedded' : 'enriched'}
        </span>
        <span className="font-mono font-semibold text-text">{Math.round((enriched / total) * 100)}%</span>
      </div>
      <div className="h-2 rounded-full bg-surface-raised overflow-hidden flex">
        {enrichedPct > 0 && (
          <div
            className="bg-violet-500 transition-all duration-500"
            style={{ width: `${enrichedPct}%` }}
            title={`${displayEnriched} enriched & embedded`}
          />
        )}
        {inProgressPct > 0 && (
          <div
            className="bg-primary transition-all duration-500 relative"
            style={{ width: `${inProgressPct}%` }}
            title={`${displayInProgress} in-progress`}
          >
            <div className="absolute inset-0 bg-white/20 animate-pulse" />
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-text-muted">
        {displayEnriched > 0 && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-violet-500" /> {displayEnriched} enriched & embedded
          </span>
        )}
        {displayInProgress > 0 && (
          <span className="flex items-center gap-1 font-medium text-primary">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" /> {displayInProgress} in-progress
          </span>
        )}
      </div>
    </div>
  );
}

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

export function GraphStructurePanel({
  summary,
  epistemic,
  augmentation,
  moduleStatus,
  knowledgeStatus,
  untracedFiles,
  staleFiles,
  tracedFiles = [],
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
}: GraphStructurePanelProps) {
  const [activeTab, setActiveTab] = useState<'queue' | 'patterns'>('queue');
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
      {/* Coverage summary bar */}
      <div className="py-3 border-b border-border space-y-2">
        {loading && !summary ? (
          <div className="flex items-center gap-2 text-xs text-text-muted py-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Loading scope data...
          </div>
        ) : summary ? (
          <>
            <CoverageBar summary={summary} building={building} />
            {epistemic && (
              <DeepCoverageBar 
                epistemic={epistemic} 
                augmentation={augmentation}
                moduleStatus={moduleStatus}
                knowledgeStatus={knowledgeStatus}
              />
            )}
          </>
        ) : null}

        {building && (
          <div className="bg-primary/5 px-3 py-2 rounded-md">
            {progress ? (
              <ProgressIndicator progress={progress} />
            ) : (
              <div className="flex items-center gap-2 text-xs text-primary">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {summary && summary.traced > 0 && summary.untraced === 0 ? 'Updating to reflect codebase changes...' : 'Building knowledge graph...'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tabs + single Update action.

          Both `onTraceAll` and `onRetraceStale` resolve to the same Fast
          Sync call upstream, so we surface one button labelled "Update"
          that fires the iterative pipeline over all drift (untraced +
          stale). Right-aligned in the tabs row so it sits next to the
          queue-count badge that motivates it. */}
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
            activeTab === 'patterns'
              ? 'border-primary text-primary'
              : 'border-transparent text-text-muted hover:text-text'
          )}
          onClick={() => setActiveTab('patterns')}
        >
          <span className="flex items-center justify-center gap-1.5">
            <EyeOff className="w-3.5 h-3.5" />
            Patterns
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
              // F-53: when nothing is pending/stale, surface the currently
              // traced files so the user can see what's actually in scope.
              // The daemon already returns this list via /trace/coverage's
              // `traced` field — the panel just wasn't displaying it.
              tracedFiles.length > 0 ? (
                <CollapsibleSection
                  title="Traced"
                  count={tracedFiles.length}
                  icon={FileCode}
                  iconColor="text-success"
                  defaultOpen={true}
                >
                  {tracedFiles.map((f) => (
                    <FileRow key={f.path} file={f} timeField="modified" compact={compact} />
                  ))}
                </CollapsibleSection>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-text-muted">
                  <FileCode className="w-8 h-8 mb-2 opacity-30" />
                  <p className="text-xs font-medium">No files in scope</p>
                  <p className="text-[10px] mt-1">Adjust include patterns or build the trace index</p>
                </div>
              )
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

        {activeTab === 'patterns' && (
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
        <div className="px-4 py-2 border-t border-border flex items-center justify-between text-[10px] text-text-muted">
          <span>Last updated: {formatTimeAgo(summary.last_build_at)}</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-5 px-2 text-[10px] gap-1"
            onClick={onRefresh}
          >
            <RefreshCw className="w-3 h-3" />
            Rescan
          </Button>
        </div>
      )}
    </div>
  );
}
