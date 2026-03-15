import { useState, useMemo } from 'react';
import {
  AlertTriangle,
  ArrowUpDown,
  FileCode2,
  GitFork,
  Loader2,
  RefreshCw,
  Ruler,
  Bug,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type { SpaghettiFileScore, SpaghettiTab } from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface SpaghettiFinderPanelProps {
  files: SpaghettiFileScore[];
  fileCount: number;
  scoredCount: number;
  severityCounts: Record<string, number>;
  loading: boolean;
  onRefresh: () => void;
  className?: string;
}

// ── Tab config ─────────────────────────────────────────────────

const TAB_CONFIG: { id: SpaghettiTab; label: string; icon: typeof Ruler; sortKey: string }[] = [
  { id: 'worst', label: 'Worst Overall', icon: AlertTriangle, sortKey: 'Composite score' },
  { id: 'long', label: 'Long Files', icon: Ruler, sortKey: 'Line count' },
  { id: 'coupling', label: 'High Coupling', icon: GitFork, sortKey: 'Fan-in + Fan-out' },
  { id: 'debt', label: 'Tech Debt', icon: Bug, sortKey: 'Debt items' },
];

// ── Severity styling ───────────────────────────────────────────

const SEVERITY_BAR: Record<string, string> = {
  critical: 'bg-red-500',
  warning: 'bg-amber-500',
  info: 'bg-blue-500',
};

const SEVERITY_TEXT: Record<string, string> = {
  critical: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-blue-400',
};

const SEVERITY_BG: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400',
  warning: 'bg-amber-500/15 text-amber-400',
  info: 'bg-blue-500/15 text-blue-400',
};

// ── Score bar component ────────────────────────────────────────

function ScoreBar({ score, severity }: { score: number; severity: string }) {
  const pct = Math.min(100, Math.round(score * 100));
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 rounded-full bg-surface-raised overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', SEVERITY_BAR[severity] || 'bg-blue-500')}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn('text-[10px] font-mono font-semibold tabular-nums w-8 text-right', SEVERITY_TEXT[severity] || 'text-text-muted')}>
        {score.toFixed(2)}
      </span>
    </div>
  );
}

// ── Metric pill component ──────────────────────────────────────

function Metric({ value, label, highlight }: { value: number | string; label: string; highlight?: boolean }) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono',
      highlight ? 'bg-amber-500/10 text-amber-400' : 'bg-surface-raised/80 text-text-muted',
    )}>
      <span className="font-semibold">{value}</span>
      <span className="opacity-70">{label}</span>
    </span>
  );
}

// ── File row component ─────────────────────────────────────────

function FileRow({ file, rank }: { file: SpaghettiFileScore; rank: number }) {
  const parts = file.file_path.split('/');
  const basename = parts.pop() || file.file_path;
  const dir = parts.join('/');

  return (
    <div className="border-b border-border/30 px-4 py-3 transition-colors hover:bg-surface-raised/30">
      <div className="flex items-start gap-3">
        {/* Rank */}
        <span className={cn(
          'mt-0.5 shrink-0 flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold',
          file.severity === 'critical' ? 'bg-red-500/20 text-red-400'
            : file.severity === 'warning' ? 'bg-amber-500/20 text-amber-400'
            : 'bg-blue-500/20 text-blue-400',
        )}>
          {rank}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-1.5">
          {/* File name + score bar */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <FileCode2 className="h-3.5 w-3.5 shrink-0 text-text-muted" />
              <span className="text-sm font-medium text-text truncate">{basename}</span>
              <span className={cn(
                'shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                SEVERITY_BG[file.severity],
              )}>
                {file.severity}
              </span>
            </div>
            <ScoreBar score={file.score} severity={file.severity} />
          </div>

          {/* Directory path */}
          {dir && (
            <p className="text-[10px] font-mono text-text-muted/70 truncate">{dir}/</p>
          )}

          {/* Metrics row */}
          <div className="flex flex-wrap items-center gap-1.5">
            <Metric value={file.estimated_lines.toLocaleString()} label="ln" highlight={file.estimated_lines > 1000} />
            <Metric value={file.fan_in} label="in" highlight={file.fan_in > 15} />
            <Metric value={file.fan_out} label="out" highlight={file.fan_out > 15} />
            {file.symbol_count > 0 && <Metric value={file.symbol_count} label="sym" />}
            {file.tech_debt_count > 0 && <Metric value={file.tech_debt_count} label="debt" highlight />}
            {file.in_circular && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono bg-red-500/10 text-red-400">
                <ArrowUpDown className="h-2.5 w-2.5" /> circular
              </span>
            )}
            {file.language !== 'unknown' && (
              <span className="text-[10px] text-text-muted/50">{file.language}</span>
            )}
          </div>

          {/* Tech debt items preview */}
          {file.tech_debt_items && file.tech_debt_items.length > 0 && (
            <div className="mt-1 rounded bg-surface-raised/40 px-2.5 py-1.5 text-[11px] text-text-muted border border-border/30">
              {file.tech_debt_items.slice(0, 2).map((item, i) => (
                <p key={i} className="truncate leading-relaxed">- {item}</p>
              ))}
              {file.tech_debt_items.length > 2 && (
                <p className="text-text-muted/50">+{file.tech_debt_items.length - 2} more</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Severity overview bar ──────────────────────────────────────

function SeverityOverview({ counts, total }: { counts: Record<string, number>; total: number }) {
  if (total === 0) return null;
  const segs = (['critical', 'warning', 'info'] as const)
    .filter(s => (counts[s] || 0) > 0)
    .map(s => ({ s, count: counts[s] || 0, pct: ((counts[s] || 0) / total) * 100 }));

  return (
    <div className="space-y-1">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-raised">
        {segs.map(({ s, pct }) => (
          <div key={s} className={cn('h-full', SEVERITY_BAR[s])} style={{ width: `${pct}%` }} />
        ))}
      </div>
      <div className="flex gap-3 text-[10px] text-text-muted">
        {segs.map(({ s, count }) => (
          <span key={s} className="flex items-center gap-1">
            <span className={cn('inline-block h-1.5 w-1.5 rounded-full', SEVERITY_BAR[s])} />
            {count} {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Sort helper ────────────────────────────────────────────────

function sortFiles(files: SpaghettiFileScore[], tab: SpaghettiTab): SpaghettiFileScore[] {
  const sorted = [...files];
  switch (tab) {
    case 'long':
      sorted.sort((a, b) => b.estimated_lines - a.estimated_lines);
      break;
    case 'coupling':
      sorted.sort((a, b) => (b.fan_in + b.fan_out) - (a.fan_in + a.fan_out));
      break;
    case 'debt':
      sorted.sort((a, b) => {
        if (b.tech_debt_count !== a.tech_debt_count) return b.tech_debt_count - a.tech_debt_count;
        return (a.epistemic_confidence ?? 1) - (b.epistemic_confidence ?? 1);
      });
      break;
    default: // worst — already sorted by score from backend
      sorted.sort((a, b) => b.score - a.score);
  }
  return sorted;
}

// ── Main Panel ─────────────────────────────────────────────────

export function SpaghettiFinderPanel({
  files,
  fileCount,
  scoredCount,
  severityCounts,
  loading,
  onRefresh,
  className,
}: SpaghettiFinderPanelProps) {
  const [activeTab, setActiveTab] = useState<SpaghettiTab>('worst');

  const sortedFiles = useMemo(() => sortFiles(files, activeTab), [files, activeTab]);

  // Empty state
  if (!loading && files.length === 0) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <AlertTriangle className="h-12 w-12 text-text-muted/30" />
          <p className="text-sm font-medium text-text">No spaghetti detected</p>
          <p className="text-xs text-text-muted max-w-xs">
            Run the enrichment pipeline to build the trace graph, then refresh to scan for files that need refactoring.
          </p>
          <Button variant="default" size="sm" onClick={onRefresh} className="gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" /> Scan Files
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Header with tabs + refresh */}
      <div className="flex flex-wrap items-center justify-between border-b border-border bg-surface px-1 gap-y-2">
        <div className="flex overflow-x-auto hide-scrollbar">
          {TAB_CONFIG.map(tab => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={cn(
                  'shrink-0 flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors whitespace-nowrap border-b-2',
                  isActive ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text hover:border-border',
                )}
                onClick={() => setActiveTab(tab.id)}
                title={`Sort by: ${tab.sortKey}`}
              >
                <Icon className="h-3 w-3" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 shrink-0 ml-auto">
          <span className="text-[10px] text-text-muted">
            {scoredCount}/{fileCount} flagged
          </span>
          <Button variant="ghost" size="sm" onClick={onRefresh} disabled={loading} className="gap-1 h-7 text-xs">
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            {loading ? 'Scanning...' : 'Refresh'}
          </Button>
        </div>
      </div>

      {/* Severity overview */}
      {scoredCount > 0 && (
        <div className="px-4 py-3 border-b border-border/50">
          <SeverityOverview counts={severityCounts} total={scoredCount} />
        </div>
      )}

      {/* Loading state */}
      {loading && files.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
          <Loader2 className="h-8 w-8 text-text-muted/50 animate-spin" />
          <p className="text-xs text-text-muted">Scoring files...</p>
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-auto">
        {sortedFiles.map((file, i) => (
          <FileRow key={file.file_path} file={file} rank={i + 1} />
        ))}
      </div>

      {/* Footer summary */}
      {sortedFiles.length > 0 && (
        <div className="border-t border-border bg-surface-raised/50 px-4 py-2 flex items-center justify-between">
          <span className="text-[10px] text-text-muted">
            Showing {sortedFiles.length} of {scoredCount} flagged files
          </span>
          <span className="text-[10px] text-text-muted/50">
            Sorted by: {TAB_CONFIG.find(t => t.id === activeTab)?.sortKey}
          </span>
        </div>
      )}
    </div>
  );
}
