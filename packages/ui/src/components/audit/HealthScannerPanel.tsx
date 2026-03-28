/**
 * HealthScannerPanel — Unified audit + spaghetti view (Phase 57B).
 *
 * Combines the AuditPanel's findings view with SpaghettiFinderPanel's file
 * scoring into a single panel with two main modes:
 *   - Findings: Category-filtered audit findings with selection and AI handoff
 *   - Files: File-ranked refactoring urgency scores
 *
 * Both modes share the unified action bar with Run Fix / Copy for AI / Add Notes.
 */
import { useState, useMemo, useCallback } from 'react';
import {
  ClipboardCheck,
  Copy,
  FileText,
  Play,
  Loader2,
  CheckSquare,
  Square,
  Bot,
  AlertTriangle,
  FileCode2,
  GitFork,
  Ruler,
  Bug,
  ArrowUpDown,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type {
  AuditFinding,
  AuditStatus,
  AuditReport,
  AuditCategory,
  SpaghettiFileScore,
  SpaghettiTab,
} from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface HealthScannerPanelProps {
  // Audit data
  status: AuditStatus | null;
  findings: AuditFinding[];
  reports: AuditReport[];
  onRunAudit: (synthesize?: boolean) => void;
  onViewReport: (reportName: string) => void;
  reportContent?: string | null;
  viewingReport?: string | null;
  // Spaghetti data
  files: SpaghettiFileScore[];
  fileCount: number;
  scoredCount: number;
  severityCounts: Record<string, number>;
  spaghettiLoading: boolean;
  onRefreshSpaghetti: () => void;
  className?: string;
}

// ── Top-level mode toggle ──────────────────────────────────────

type PanelMode = 'findings' | 'files';

// ── Audit sub-tabs (same as original AuditPanel) ───────────────

type FindingsTab = 'summary' | 'architecture' | 'quality' | 'coverage' | 'tech_debt';

const FINDINGS_TAB_CONFIG: { id: FindingsTab; label: string; categories: AuditCategory[] }[] = [
  { id: 'summary', label: 'Summary', categories: [] },
  { id: 'architecture', label: 'Architecture', categories: ['architecture'] },
  { id: 'quality', label: 'Quality', categories: ['quality', 'naming'] },
  { id: 'coverage', label: 'Coverage', categories: ['coverage', 'testing'] },
  { id: 'tech_debt', label: 'Tech Debt', categories: ['size'] },
];

// ── Spaghetti sort tabs ────────────────────────────────────────

const FILES_TAB_CONFIG: { id: SpaghettiTab; label: string; icon: typeof Ruler }[] = [
  { id: 'worst', label: 'Worst', icon: AlertTriangle },
  { id: 'long', label: 'Long', icon: Ruler },
  { id: 'coupling', label: 'Coupling', icon: GitFork },
  { id: 'debt', label: 'Debt', icon: Bug },
];

// ── Shared style constants ─────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400',
  warning: 'bg-amber-500/20 text-amber-400',
  info: 'bg-blue-500/20 text-blue-400',
  suggestion: 'bg-emerald-500/20 text-emerald-400',
};

const PRIORITY_COLORS: Record<string, string> = {
  P0: 'bg-red-500/20 text-red-400',
  P1: 'bg-amber-500/20 text-amber-400',
  P2: 'bg-blue-500/20 text-blue-400',
  P3: 'bg-slate-500/20 text-slate-400',
};

const EFFORT_COLORS: Record<string, string> = {
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

const PRIORITY_RANK: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3, P4: 4 };
const SEVERITY_RANK: Record<string, number> = { critical: 0, warning: 1, info: 2, suggestion: 3 };

// ── Shared sub-components ──────────────────────────────────────

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  if (!text) return null;
  return (
    <span className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide', colorClass)}>
      {text}
    </span>
  );
}

function CopyBtn({ text, label, icon: Icon = Copy, primary = false }: { text: string; label: string; icon?: any; primary?: boolean }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }, [text]);
  return (
    <Button variant={primary ? 'default' : 'ghost'} size="sm" onClick={handleCopy} className={cn("gap-1.5 text-xs", primary && "font-medium")}>
      <Icon className="h-3.5 w-3.5" />{copied ? 'Copied!' : label}
    </Button>
  );
}

function SeverityBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  if (total === 0) return null;
  const segs = (['critical', 'warning', 'info', 'suggestion'] as const)
    .filter(s => (counts[s] || 0) > 0)
    .map(s => ({ s, count: counts[s] || 0, pct: ((counts[s] || 0) / total) * 100 }));

  return (
    <div className="space-y-1.5">
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

// ── Finding helpers ────────────────────────────────────────────

function getFindingId(f: AuditFinding, idx: number): string {
  return f.finding_id || `legacy-${f.analyzer}-${idx}`;
}

// ── Finding Card ───────────────────────────────────────────────

function FindingCard({ finding, uniqueId, checked, onToggle }: {
  finding: AuditFinding; uniqueId: string; checked: boolean; onToggle: () => void;
}) {
  const priority = finding.priority || 'P2';
  const effort = finding.effort || 'medium';
  const CheckIcon = checked ? CheckSquare : Square;
  return (
    <div className={cn(
      'border-b border-border/30 px-4 py-3.5 transition-colors hover:bg-surface-raised/30',
      checked && 'bg-primary/5 hover:bg-primary/10',
    )}>
      <div className="flex items-start gap-3">
        <button onClick={onToggle} className={cn("mt-0.5 shrink-0 transition-colors", checked ? "text-primary" : "text-text-muted hover:text-primary")}>
          <CheckIcon className="h-4 w-4" />
        </button>
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <div className="flex items-start justify-between gap-4">
            <p className={cn("text-sm font-medium leading-snug", checked ? "text-primary" : "text-text")}>{finding.title}</p>
            <div className="flex shrink-0 items-center gap-1.5 opacity-90">
              <Badge text={priority} colorClass={PRIORITY_COLORS[priority] || PRIORITY_COLORS.P2} />
              <Badge text={finding.severity} colorClass={SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.info} />
              <Badge text={effort} colorClass={EFFORT_COLORS[effort] || EFFORT_COLORS.medium} />
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="font-mono text-[10px] bg-surface-raised/80 px-1.5 py-0.5 rounded text-text-muted/80">{finding.finding_id || uniqueId}</span>
            {finding.file_paths && finding.file_paths.length > 0 && (
              <span className="truncate font-mono">
                {finding.file_paths.slice(0, 3).join(', ')}
                {finding.file_paths.length > 3 && ` +${finding.file_paths.length - 3}`}
              </span>
            )}
          </div>
          {finding.suggested_action && (
            <div className="mt-1 rounded-md bg-surface-raised/40 px-3 py-2 text-xs text-text-muted border border-border/40">
              <span className="font-semibold text-text">Action:</span> {finding.suggested_action}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── File Row (from SpaghettiFinderPanel) ────────────────────────

function ScoreBar({ score, severity }: { score: number; severity: string }) {
  const pct = Math.min(100, Math.round(score * 100));
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 rounded-full bg-surface-raised overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', SEVERITY_BAR[severity] || 'bg-blue-500')} style={{ width: `${pct}%` }} />
      </div>
      <span className={cn('text-[10px] font-mono font-semibold tabular-nums w-8 text-right', severity === 'critical' ? 'text-red-400' : severity === 'warning' ? 'text-amber-400' : 'text-blue-400')}>
        {score.toFixed(2)}
      </span>
    </div>
  );
}

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

function FileRow({ file, rank }: { file: SpaghettiFileScore; rank: number }) {
  const parts = file.file_path.split('/');
  const basename = parts.pop() || file.file_path;
  const dir = parts.join('/');

  return (
    <div className="border-b border-border/30 px-4 py-3 transition-colors hover:bg-surface-raised/30">
      <div className="flex items-start gap-3">
        <span className={cn(
          'mt-0.5 shrink-0 flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold',
          file.severity === 'critical' ? 'bg-red-500/20 text-red-400'
            : file.severity === 'warning' ? 'bg-amber-500/20 text-amber-400'
            : 'bg-blue-500/20 text-blue-400',
        )}>
          {rank}
        </span>
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <FileCode2 className="h-3.5 w-3.5 shrink-0 text-text-muted" />
              <span className="text-sm font-medium text-text truncate">{basename}</span>
              <Badge text={file.severity} colorClass={SEVERITY_COLORS[file.severity] || SEVERITY_COLORS.info} />
            </div>
            <ScoreBar score={file.score} severity={file.severity} />
          </div>
          {dir && <p className="text-[10px] font-mono text-text-muted/70 truncate">{dir}/</p>}
          <div className="flex flex-wrap items-center gap-1.5">
            <Metric value={file.estimated_lines.toLocaleString()} label="ln" highlight={file.estimated_lines > 1000} />
            <Metric value={file.fan_in} label="in" highlight={file.fan_in > 15} />
            <Metric value={file.fan_out} label="out" highlight={file.fan_out > 15} />
            {file.tech_debt_count > 0 && <Metric value={file.tech_debt_count} label="debt" highlight />}
            {file.in_circular && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono bg-red-500/10 text-red-400">
                <ArrowUpDown className="h-2.5 w-2.5" /> circular
              </span>
            )}
          </div>
          {file.tech_debt_items && file.tech_debt_items.length > 0 && (
            <div className="mt-1 rounded bg-surface-raised/40 px-2.5 py-1.5 text-[11px] text-text-muted border border-border/30">
              {file.tech_debt_items.slice(0, 2).map((item, i) => (
                <p key={i} className="truncate leading-relaxed">- {item}</p>
              ))}
              {file.tech_debt_items.length > 2 && <p className="text-text-muted/50">+{file.tech_debt_items.length - 2} more</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sort helper ────────────────────────────────────────────────

function sortFiles(files: SpaghettiFileScore[], tab: SpaghettiTab): SpaghettiFileScore[] {
  const sorted = [...files];
  switch (tab) {
    case 'long': sorted.sort((a, b) => b.estimated_lines - a.estimated_lines); break;
    case 'coupling': sorted.sort((a, b) => (b.fan_in + b.fan_out) - (a.fan_in + a.fan_out)); break;
    case 'debt': sorted.sort((a, b) => b.tech_debt_count !== a.tech_debt_count ? b.tech_debt_count - a.tech_debt_count : (a.epistemic_confidence ?? 1) - (b.epistemic_confidence ?? 1)); break;
    default: sorted.sort((a, b) => b.score - a.score);
  }
  return sorted;
}

// ── Main Panel ─────────────────────────────────────────────────

export function HealthScannerPanel({
  status, findings, reports: _reports, onRunAudit, onViewReport, reportContent, viewingReport,
  files, fileCount, scoredCount, severityCounts, spaghettiLoading, onRefreshSpaghetti,
  className,
}: HealthScannerPanelProps) {
  const [mode, setMode] = useState<PanelMode>('findings');
  const [findingsTab, setFindingsTab] = useState<FindingsTab>('summary');
  const [filesTab, setFilesTab] = useState<SpaghettiTab>('worst');
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  const running = status?.running ?? false;
  const hasFindings = (status?.has_results ?? false) || findings.length > 0;
  const hasFiles = files.length > 0;

  const toggleCheck = useCallback((id: string) => {
    setCheckedIds(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }, []);

  const clearChecks = useCallback(() => setCheckedIds(new Set()), []);

  const checkedFindings = useMemo(() => findings.filter((f, i) => checkedIds.has(getFindingId(f, i))), [findings, checkedIds]);

  // MCP command for checked findings
  const mcpCommand = useMemo(() => {
    if (checkedFindings.length === 0) return 'codrag_audit';
    const ids = checkedFindings.map((f, i) => `"${getFindingId(f, i)}"`).join(', ');
    return `codrag_audit action="refactor" finding_ids=[${ids}]`;
  }, [checkedFindings]);

  // Markdown for clipboard
  const checkedMarkdown = useMemo(() => {
    if (checkedFindings.length === 0) return '';
    return checkedFindings.map((f, i) => {
      const id = getFindingId(f, i);
      return `### ${id}: ${f.title} [${f.priority || 'P2'} · ${f.severity} · ${f.effort || 'medium'}]\n` +
        `**Files:** ${(f.file_paths || []).join(', ')}\n` +
        `**Problem:** ${f.description}\n` +
        `**Action:** ${f.suggested_action}\n`;
    }).join('\n---\n\n');
  }, [checkedFindings]);

  // Sorted findings for the active tab
  const tabFindings = useCallback((tab: FindingsTab) => {
    const cfg = FINDINGS_TAB_CONFIG.find(t => t.id === tab);
    if (!cfg || cfg.categories.length === 0) return [];
    return findings.filter(f => cfg.categories.includes(f.category)).sort((a, b) => {
      const pA = PRIORITY_RANK[a.priority || 'P2'] ?? 99;
      const pB = PRIORITY_RANK[b.priority || 'P2'] ?? 99;
      return pA !== pB ? pA - pB : (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
    });
  }, [findings]);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const tab of FINDINGS_TAB_CONFIG) {
      counts[tab.id] = tab.categories.length > 0 ? findings.filter(f => tab.categories.includes(f.category)).length : 0;
    }
    return counts;
  }, [findings]);

  const sortedFiles = useMemo(() => sortFiles(files, filesTab), [files, filesTab]);
  const currentTabFindings = tabFindings(findingsTab);

  // Report viewer (full page takeover)
  if (viewingReport && reportContent) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <button className="text-sm text-primary hover:underline" onClick={() => onViewReport('')}>← Back</button>
          <CopyBtn text={reportContent} label="Copy" icon={Copy} />
        </div>
        <div className="flex-1 overflow-auto p-4">
          <pre className="whitespace-pre-wrap text-xs text-text-muted font-mono leading-relaxed">{reportContent}</pre>
        </div>
      </div>
    );
  }

  // Build severity counts for findings
  const findingSevCounts: Record<string, number> = {};
  for (const f of findings) findingSevCounts[f.severity] = (findingSevCounts[f.severity] || 0) + 1;

  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* ── Top bar: Mode toggle + Actions ───────────────────── */}
      <div className="flex items-center justify-between border-b border-border bg-surface px-3 py-2 gap-2">
        {/* Mode toggle */}
        <div className="flex items-center bg-surface-raised rounded-lg p-0.5 gap-0.5">
          <button
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              mode === 'findings' ? 'bg-primary text-white shadow-sm' : 'text-text-muted hover:text-text',
            )}
            onClick={() => setMode('findings')}
          >
            <span className="flex items-center gap-1.5">
              <ClipboardCheck className="h-3 w-3" />
              Findings
              {findings.length > 0 && <span className="text-[10px] opacity-70">{findings.length}</span>}
            </span>
          </button>
          <button
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
              mode === 'files' ? 'bg-primary text-white shadow-sm' : 'text-text-muted hover:text-text',
            )}
            onClick={() => setMode('files')}
          >
            <span className="flex items-center gap-1.5">
              <FileCode2 className="h-3 w-3" />
              Files
              {scoredCount > 0 && <span className="text-[10px] opacity-70">{scoredCount}</span>}
            </span>
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5">
          {mode === 'findings' ? (
            <>
              <Button variant="default" size="sm" onClick={() => onRunAudit(false)} disabled={running} className="gap-1 h-7 text-xs">
                {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                {running ? 'Running…' : 'Scan'}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => onRunAudit(true)} disabled={running} className="gap-1 h-7 text-xs">
                <FileText className="h-3 w-3" /> + Report
              </Button>
            </>
          ) : (
            <Button variant="ghost" size="sm" onClick={onRefreshSpaghetti} disabled={spaghettiLoading} className="gap-1 h-7 text-xs">
              {spaghettiLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              {spaghettiLoading ? 'Scanning...' : 'Refresh'}
            </Button>
          )}
        </div>
      </div>

      {/* ── Findings Mode ─────────────────────────────────── */}
      {mode === 'findings' && (
        <>
          {!hasFindings ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
              <ClipboardCheck className={cn("h-12 w-12 text-text-muted/30", running && "animate-pulse")} />
              <p className="text-sm font-medium text-text">{running ? 'Scanning...' : 'No findings yet'}</p>
              {!running && (
                <p className="text-xs text-text-muted max-w-xs">
                  Run a health scan to get architecture, quality, and tech debt findings from the trace graph.
                </p>
              )}
            </div>
          ) : (
            <>
              {/* Category sub-tabs */}
              <div className="flex overflow-x-auto hide-scrollbar border-b border-border bg-surface px-1">
                {FINDINGS_TAB_CONFIG.map(tab => (
                  <button
                    key={tab.id}
                    className={cn(
                      'shrink-0 px-3 py-2 text-xs font-medium transition-colors whitespace-nowrap border-b-2',
                      findingsTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text',
                    )}
                    onClick={() => setFindingsTab(tab.id)}
                  >
                    {tab.label}
                    {(tabCounts[tab.id] || 0) > 0 && <span className="ml-1 text-[10px] opacity-60">{tabCounts[tab.id]}</span>}
                  </button>
                ))}
              </div>

              {/* Summary tab */}
              {findingsTab === 'summary' && (
                <div className="p-4 space-y-4">
                  <div>
                    <p className="text-sm font-medium text-text">{findings.length} findings total</p>
                    <p className="text-xs text-text-muted">
                      {findingSevCounts.critical || 0} critical · {findingSevCounts.warning || 0} warning · {findingSevCounts.info || 0} info
                    </p>
                  </div>
                  <SeverityBar counts={findingSevCounts} total={findings.length} />
                </div>
              )}

              {/* Category findings */}
              {findingsTab !== 'summary' && (
                <div className="flex-1 overflow-auto">
                  {currentTabFindings.length === 0 ? (
                    <div className="p-8 text-center">
                      <CheckSquare className="h-8 w-8 text-text-muted/30 mx-auto mb-3" />
                      <p className="text-sm font-medium text-text">All clear!</p>
                      <p className="text-xs text-text-muted mt-1">No findings in this category.</p>
                    </div>
                  ) : (
                    currentTabFindings.map(f => {
                      const uid = getFindingId(f, findings.indexOf(f));
                      return (
                        <FindingCard
                          key={uid}
                          finding={f}
                          uniqueId={uid}
                          checked={checkedIds.has(uid)}
                          onToggle={() => toggleCheck(uid)}
                        />
                      );
                    })
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ── Files Mode ────────────────────────────────────── */}
      {mode === 'files' && (
        <>
          {!hasFiles && !spaghettiLoading ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
              <AlertTriangle className="h-10 w-10 text-text-muted/25" />
              <p className="text-sm font-medium text-text">Waiting for trace data</p>
              <p className="text-xs text-text-muted">Build your trace index to see file refactoring scores.</p>
            </div>
          ) : (
            <>
              {/* Sort tabs */}
              <div className="flex overflow-x-auto hide-scrollbar border-b border-border bg-surface px-1">
                {FILES_TAB_CONFIG.map(tab => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      className={cn(
                        'shrink-0 flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors whitespace-nowrap border-b-2',
                        filesTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text',
                      )}
                      onClick={() => setFilesTab(tab.id)}
                    >
                      <Icon className="h-3 w-3" />
                      {tab.label}
                    </button>
                  );
                })}
                <span className="ml-auto flex items-center px-3 text-[10px] text-text-muted">
                  {scoredCount}/{fileCount} flagged
                </span>
              </div>

              {/* Severity bar */}
              {scoredCount > 0 && (
                <div className="px-4 py-3 border-b border-border/50">
                  <SeverityBar counts={severityCounts} total={scoredCount} />
                </div>
              )}

              {/* Loading */}
              {spaghettiLoading && files.length === 0 && (
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
            </>
          )}
        </>
      )}

      {/* ── Bottom action bar ─────────────────────────────── */}
      {checkedIds.size > 0 && (
        <div className="border-t border-border bg-surface-raised/80 backdrop-blur px-4 py-3 flex items-center gap-3">
          <span className="text-sm font-semibold bg-primary/10 text-primary px-2 py-1 rounded">
            {checkedIds.size} selected
          </span>
          <div className="flex-1" />
          <Button variant="ghost" size="sm" onClick={clearChecks} className="text-xs text-text-muted hover:text-text">
            Clear
          </Button>
          <CopyBtn text={checkedMarkdown} label="Copy as Text" icon={FileText} />
          <CopyBtn text={mcpCommand} label="Copy for AI" icon={Bot} primary />
        </div>
      )}
    </div>
  );
}
