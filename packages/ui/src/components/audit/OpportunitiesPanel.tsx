/**
 * OpportunitiesPanel — Unified opportunity console (Phase 63).
 *
 * Shows all codebase improvement opportunities from the OpportunityManager:
 * health findings, spaghetti scores, advisor proposals, TODO items.
 *
 * Features:
 * - Priority, category, and source filters
 * - Dismiss / restore with optimistic updates
 * - Multi-format export (SARIF, JSON, CSV, Markdown, AI Prompt)
 * - Summary stats bar
 * - MCP-ready "Copy for AI" handoff
 */
import { useState, useMemo, useCallback } from 'react';
import {
  Lightbulb,
  RefreshCw,
  Loader2,
  Download,
  Copy,
  Bot,
  X,
  Eye,
  EyeOff,
  RotateCcw,
  FileText,
  Filter,
  ChevronDown,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';

// ── Types ──────────────────────────────────────────────────────

export interface OpportunityItem {
  id: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  severity: string;
  effort: string;
  source: string;
  analyzer: string;
  state: string;
  affected_files: string[];
  suggested_action: string;
  evidence: string;
  mcp_command: string;
  created_at: string;
  dismissed_at: string;
}

export interface OpportunitiesSummary {
  total: number;
  dismissed: number;
  critical: number;
  warning: number;
  info: number;
  last_refresh: string | null;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
}

export interface OpportunitiesPanelProps {
  items: OpportunityItem[];
  summary: OpportunitiesSummary | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRefresh: () => void;
  onDismiss: (itemId: string) => void;
  onRestore: (itemId: string) => void;
  onExport: (format: string) => void;
  categoryFilter: string | null;
  onCategoryFilterChange: (c: string | null) => void;
  priorityFilter: string | null;
  onPriorityFilterChange: (p: string | null) => void;
  sourceFilter: string | null;
  onSourceFilterChange: (s: string | null) => void;
  showDismissed: boolean;
  onShowDismissedChange: (b: boolean) => void;
  className?: string;
}

// ── Style constants ────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  P0: 'bg-red-500/20 text-red-400',
  P1: 'bg-amber-500/20 text-amber-400',
  P2: 'bg-blue-500/20 text-blue-400',
  P3: 'bg-slate-500/20 text-slate-400',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400',
  warning: 'bg-amber-500/20 text-amber-400',
  info: 'bg-blue-500/20 text-blue-400',
  suggestion: 'bg-emerald-500/20 text-emerald-400',
};

const EFFORT_COLORS: Record<string, string> = {
  trivial: 'bg-emerald-500/15 text-emerald-400',
  small: 'bg-emerald-500/15 text-emerald-400',
  medium: 'bg-amber-500/15 text-amber-400',
  large: 'bg-red-500/15 text-red-400',
};

const SEVERITY_BAR: Record<string, string> = {
  critical: 'bg-red-500',
  warning: 'bg-amber-500',
  info: 'bg-blue-500',
  suggestion: 'bg-emerald-500',
};

const PRIO_RANK: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };
const SEV_RANK: Record<string, number> = { critical: 0, warning: 1, info: 2, suggestion: 3 };

const SOURCE_LABELS: Record<string, string> = {
  health: 'Health Scanner',
  spaghetti: 'Spaghetti',
  advisor: 'Advisor',
  todo_scanner: 'TODOs',
  roadmap: 'Roadmap',
};

const EXPORT_FORMATS = [
  { id: 'ai_prompt', label: 'AI Prompt', icon: Bot },
  { id: 'sarif', label: 'SARIF', icon: FileText },
  { id: 'json', label: 'JSON', icon: Download },
  { id: 'csv', label: 'CSV', icon: Download },
  { id: 'md', label: 'Markdown', icon: FileText },
];

// ── Sub-components ─────────────────────────────────────────────

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  if (!text) return null;
  return (
    <span className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide', colorClass)}>
      {text}
    </span>
  );
}

function CopyBtn({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }, [text]);
  return (
    <Button variant="ghost" size="sm" onClick={handleCopy} className="gap-1.5 text-xs">
      <Copy className="h-3.5 w-3.5" />{copied ? 'Copied!' : label}
    </Button>
  );
}

function SummaryBar({ summary }: { summary: OpportunitiesSummary }) {
  const total = summary.total;
  if (total === 0) return null;

  const segs = [
    { key: 'critical', count: summary.critical, color: SEVERITY_BAR.critical },
    { key: 'warning', count: summary.warning, color: SEVERITY_BAR.warning },
    { key: 'info', count: summary.info, color: SEVERITY_BAR.info },
  ].filter(s => s.count > 0);

  return (
    <div className="space-y-1.5">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-raised">
        {segs.map(({ key, count, color }) => (
          <div key={key} className={cn('h-full', color)} style={{ width: `${(count / total) * 100}%` }} />
        ))}
      </div>
      <div className="flex gap-3 text-[10px] text-text-muted">
        {segs.map(({ key, count, color }) => (
          <span key={key} className="flex items-center gap-1">
            <span className={cn('inline-block h-1.5 w-1.5 rounded-full', color)} />
            {count} {key}
          </span>
        ))}
        {summary.dismissed > 0 && (
          <span className="flex items-center gap-1 opacity-50">
            <EyeOff className="h-2.5 w-2.5" />
            {summary.dismissed} dismissed
          </span>
        )}
      </div>
    </div>
  );
}

function OpportunityCard({
  item,
  onDismiss,
  onRestore,
}: {
  item: OpportunityItem;
  onDismiss: (id: string) => void;
  onRestore: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDismissed = item.state === 'dismissed';

  return (
    <div
      className={cn(
        'border-b border-border/30 px-4 py-3.5 transition-colors',
        isDismissed ? 'opacity-40' : 'hover:bg-surface-raised/30',
      )}
    >
      <div className="flex items-start gap-3">
        {/* Severity indicator */}
        <div
          className={cn(
            'mt-1 shrink-0 w-1 h-8 rounded-full',
            SEVERITY_BAR[item.severity] || SEVERITY_BAR.info,
          )}
        />

        <div className="flex-1 min-w-0 flex flex-col gap-2">
          {/* Title row */}
          <div className="flex items-start justify-between gap-3">
            <button
              className="text-left text-sm font-medium leading-snug text-text hover:text-primary transition-colors"
              onClick={() => setExpanded(!expanded)}
            >
              {item.title}
            </button>
            <div className="flex shrink-0 items-center gap-1.5 opacity-90">
              <Badge text={item.priority} colorClass={PRIORITY_COLORS[item.priority] || PRIORITY_COLORS.P2} />
              <Badge text={item.severity} colorClass={SEVERITY_COLORS[item.severity] || SEVERITY_COLORS.info} />
              <Badge text={item.effort} colorClass={EFFORT_COLORS[item.effort] || EFFORT_COLORS.medium} />
            </div>
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="font-mono text-[10px] bg-surface-raised/80 px-1.5 py-0.5 rounded text-text-muted/80">
              {item.id}
            </span>
            <span className="text-[10px] opacity-60">
              {SOURCE_LABELS[item.source] || item.source}
            </span>
            {item.affected_files.length > 0 && (
              <span className="truncate font-mono text-[10px]">
                {item.affected_files.length} file{item.affected_files.length > 1 ? 's' : ''}
              </span>
            )}
          </div>

          {/* Suggested action */}
          {item.suggested_action && !expanded && (
            <div className="rounded-md bg-surface-raised/40 px-3 py-2 text-xs text-text-muted border border-border/40">
              <span className="font-semibold text-text">Action:</span> {item.suggested_action}
            </div>
          )}

          {/* Expanded details */}
          {expanded && (
            <div className="space-y-2 mt-1">
              {item.description && (
                <p className="text-xs text-text-muted leading-relaxed">{item.description}</p>
              )}
              {item.suggested_action && (
                <div className="rounded-md bg-surface-raised/40 px-3 py-2 text-xs text-text-muted border border-border/40">
                  <span className="font-semibold text-text">Action:</span> {item.suggested_action}
                </div>
              )}
              {item.affected_files.length > 0 && (
                <div className="rounded-md bg-surface-raised/40 px-3 py-2 text-xs font-mono text-text-muted/80 border border-border/40">
                  {item.affected_files.slice(0, 5).map(f => (
                    <div key={f} className="truncate">{f}</div>
                  ))}
                  {item.affected_files.length > 5 && (
                    <div className="text-text-muted/50">+{item.affected_files.length - 5} more</div>
                  )}
                </div>
              )}
              {item.mcp_command && (
                <div className="flex items-center gap-2">
                  <CopyBtn text={item.mcp_command} label="Copy MCP Command" />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Dismiss/Restore button */}
        <button
          className={cn(
            'mt-0.5 shrink-0 p-1 rounded transition-colors',
            isDismissed
              ? 'text-text-muted hover:text-emerald-400 hover:bg-emerald-500/10'
              : 'text-text-muted/50 hover:text-red-400 hover:bg-red-500/10',
          )}
          onClick={() => isDismissed ? onRestore(item.id) : onDismiss(item.id)}
          title={isDismissed ? 'Restore' : 'Dismiss'}
        >
          {isDismissed ? <RotateCcw className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

// ── Filter dropdown ────────────────────────────────────────────

function FilterDropdown({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | null;
  options: { id: string; label: string; count?: number }[];
  onChange: (v: string | null) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        className={cn(
          'flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md transition-colors border',
          value
            ? 'border-primary/50 bg-primary/10 text-primary'
            : 'border-border/50 bg-surface-raised/60 text-text-muted hover:text-text',
        )}
        onClick={() => setOpen(!open)}
      >
        {value ? `${label}: ${value}` : label}
        <ChevronDown className="h-2.5 w-2.5" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-50 min-w-[120px] rounded-md border border-border bg-surface shadow-lg overflow-hidden">
            <button
              className="w-full px-3 py-1.5 text-xs text-left text-text-muted hover:bg-surface-raised transition-colors"
              onClick={() => { onChange(null); setOpen(false); }}
            >
              All
            </button>
            {options.map(opt => (
              <button
                key={opt.id}
                className={cn(
                  'w-full px-3 py-1.5 text-xs text-left hover:bg-surface-raised transition-colors flex justify-between',
                  value === opt.id ? 'text-primary font-medium' : 'text-text',
                )}
                onClick={() => { onChange(opt.id); setOpen(false); }}
              >
                <span>{opt.label}</span>
                {opt.count != null && <span className="text-text-muted">{opt.count}</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Main Panel ─────────────────────────────────────────────────

export function OpportunitiesPanel({
  items,
  summary,
  loading,
  refreshing,
  error,
  onRefresh,
  onDismiss,
  onRestore,
  onExport,
  categoryFilter,
  onCategoryFilterChange,
  priorityFilter,
  onPriorityFilterChange,
  sourceFilter,
  onSourceFilterChange,
  showDismissed,
  onShowDismissedChange,
  className,
}: OpportunitiesPanelProps) {
  const [exportOpen, setExportOpen] = useState(false);

  // Apply client-side filters
  const filteredItems = useMemo(() => {
    let result = items;

    if (!showDismissed) {
      result = result.filter(i => i.state !== 'dismissed');
    }
    if (categoryFilter) {
      result = result.filter(i => i.category === categoryFilter);
    }
    if (priorityFilter) {
      const maxPrio = PRIO_RANK[priorityFilter] ?? 9;
      result = result.filter(i => (PRIO_RANK[i.priority] ?? 9) <= maxPrio);
    }
    if (sourceFilter) {
      result = result.filter(i => i.source === sourceFilter);
    }

    // Sort: priority → severity
    result.sort((a, b) => {
      const pa = PRIO_RANK[a.priority] ?? 9;
      const pb = PRIO_RANK[b.priority] ?? 9;
      if (pa !== pb) return pa - pb;
      return (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9);
    });

    return result;
  }, [items, showDismissed, categoryFilter, priorityFilter, sourceFilter]);

  // Build filter options from data
  const categoryOptions = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const i of items) counts[i.category] = (counts[i.category] || 0) + 1;
    return Object.entries(counts).map(([id, count]) => ({ id, label: id, count })).sort((a, b) => b.count - a.count);
  }, [items]);

  const sourceOptions = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const i of items) counts[i.source] = (counts[i.source] || 0) + 1;
    return Object.entries(counts).map(([id, count]) => ({ id, label: SOURCE_LABELS[id] || id, count })).sort((a, b) => b.count - a.count);
  }, [items]);

  const prioOptions = [
    { id: 'P0', label: 'P0 — Critical' },
    { id: 'P1', label: 'P1 — Warning' },
    { id: 'P2', label: 'P2 — Info' },
    { id: 'P3', label: 'P3 — All' },
  ];

  const hasFilters = !!(categoryFilter || priorityFilter || sourceFilter);

  // Empty state
  if (!loading && items.length === 0 && !error) {
    return (
      <div className={cn('flex h-full flex-col items-center justify-center gap-4 p-8 text-center', className)}>
        <Lightbulb className={cn('h-12 w-12 text-text-muted/30', refreshing && 'animate-pulse')} />
        <p className="text-sm font-medium text-text">
          {refreshing ? 'Scanning for opportunities...' : 'No opportunities yet'}
        </p>
        {!refreshing && (
          <>
            <p className="text-xs text-text-muted max-w-xs">
              Run a health scan to discover architecture issues, tech debt, naming problems, and more.
            </p>
            <Button variant="default" size="sm" onClick={onRefresh} className="gap-1.5 mt-2">
              <RefreshCw className="h-3.5 w-3.5" />
              Scan Now
            </Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* ── Top bar: Actions ──────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-3 py-2 gap-2">
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={onRefresh}
            disabled={refreshing}
            className="gap-1 h-7 text-xs"
          >
            {refreshing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            {refreshing ? 'Scanning...' : 'Refresh'}
          </Button>

          {/* Filter buttons */}
          <div className="flex items-center gap-1">
            <Filter className="h-3 w-3 text-text-muted" />
            <FilterDropdown
              label="Priority"
              value={priorityFilter}
              options={prioOptions}
              onChange={onPriorityFilterChange}
            />
            <FilterDropdown
              label="Category"
              value={categoryFilter}
              options={categoryOptions}
              onChange={onCategoryFilterChange}
            />
            <FilterDropdown
              label="Source"
              value={sourceFilter}
              options={sourceOptions}
              onChange={onSourceFilterChange}
            />
          </div>

          {hasFilters && (
            <button
              className="text-[10px] text-text-muted hover:text-primary transition-colors"
              onClick={() => {
                onCategoryFilterChange(null);
                onPriorityFilterChange(null);
                onSourceFilterChange(null);
              }}
            >
              Clear filters
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {/* Dismissed toggle */}
          <button
            className={cn(
              'flex items-center gap-1 px-2 py-1 text-[10px] rounded-md transition-colors',
              showDismissed ? 'text-text-muted bg-surface-raised' : 'text-text-muted/50 hover:text-text-muted',
            )}
            onClick={() => onShowDismissedChange(!showDismissed)}
            title={showDismissed ? 'Hide dismissed' : 'Show dismissed'}
          >
            {showDismissed ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
            {summary?.dismissed || 0}
          </button>

          {/* Export dropdown */}
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExportOpen(!exportOpen)}
              className="gap-1 h-7 text-xs"
            >
              <Download className="h-3 w-3" />
              Export
              <ChevronDown className="h-2.5 w-2.5" />
            </Button>
            {exportOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setExportOpen(false)} />
                <div className="absolute top-full right-0 mt-1 z-50 min-w-[140px] rounded-md border border-border bg-surface shadow-lg overflow-hidden">
                  {EXPORT_FORMATS.map(fmt => {
                    const Icon = fmt.icon;
                    return (
                      <button
                        key={fmt.id}
                        className="w-full px-3 py-2 text-xs text-left text-text hover:bg-surface-raised transition-colors flex items-center gap-2"
                        onClick={() => { onExport(fmt.id); setExportOpen(false); }}
                      >
                        <Icon className="h-3 w-3 text-text-muted" />
                        {fmt.label}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Summary bar ──────────────────────────────────────── */}
      {summary && summary.total > 0 && (
        <div className="px-4 py-3 border-b border-border/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">
              <span className="font-semibold text-text">{filteredItems.length}</span>
              {filteredItems.length !== summary.total && ` of ${summary.total}`} opportunities
            </span>
            {summary.last_refresh && (
              <span className="text-[10px] text-text-muted/60">
                Last: {new Date(summary.last_refresh).toLocaleString()}
              </span>
            )}
          </div>
          <SummaryBar summary={summary} />
        </div>
      )}

      {/* ── Error bar ────────────────────────────────────────── */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 text-red-400 text-xs border-b border-red-500/20">
          {error}
        </div>
      )}

      {/* ── Loading state ────────────────────────────────────── */}
      {loading && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8">
          <Loader2 className="h-8 w-8 text-text-muted/50 animate-spin" />
          <p className="text-xs text-text-muted">Loading opportunities...</p>
        </div>
      )}

      {/* ── Item list ────────────────────────────────────────── */}
      {filteredItems.length > 0 && (
        <div className="flex-1 overflow-auto">
          {filteredItems.map(item => (
            <OpportunityCard
              key={item.id}
              item={item}
              onDismiss={onDismiss}
              onRestore={onRestore}
            />
          ))}
        </div>
      )}

      {/* ── Empty after filter ───────────────────────────────── */}
      {!loading && filteredItems.length === 0 && items.length > 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <Filter className="h-8 w-8 text-text-muted/30" />
          <p className="text-sm font-medium text-text">No matches</p>
          <p className="text-xs text-text-muted">
            {hasFilters
              ? 'Try adjusting filters or clearing them.'
              : 'All items are dismissed. Toggle dismiss visibility above.'}
          </p>
        </div>
      )}

      {/* ── Bottom helper ────────────────────────────────────── */}
      {filteredItems.length > 0 && (
        <div className="border-t border-border bg-surface-raised/60 px-4 py-2 flex items-center justify-between text-[10px] text-text-muted">
          <span>
            Export: <code>codrag opportunities --format sarif | json | csv | ai_prompt</code>
          </span>
          <span>
            MCP: <code>codrag_audit</code>
          </span>
        </div>
      )}
    </div>
  );
}
