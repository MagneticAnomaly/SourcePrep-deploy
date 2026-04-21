import { useState, useMemo, useCallback } from 'react';
import {
  ClipboardCheck,
  Copy,
  FileText,
  Play,
  Loader2,
  ExternalLink,
  CheckSquare,
  Square,
  Bot,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type { AuditFinding, AuditStatus, AuditReport, AuditSeverity, AuditCategory } from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface AuditPanelProps {
  status: AuditStatus | null;
  findings: AuditFinding[];
  reports: AuditReport[];
  onRunAudit: (synthesize?: boolean) => void;
  onViewReport: (reportName: string) => void;
  reportContent?: string | null;
  viewingReport?: string | null;
  className?: string;
}

// ── Tab definitions ────────────────────────────────────────────

type AuditTab = 'summary' | 'architecture' | 'quality' | 'coverage' | 'tech_debt';

// Map tab to the report name it should display
const TAB_REPORT_MAP: Record<string, string> = {
  architecture: 'ARCHITECTURE_ANALYSIS',
  quality: 'GAP_ANALYSIS',
  tech_debt: 'TECH_DEBT_REPORT',
  summary: 'AUDIT_SUMMARY',
};

const TAB_CONFIG: { id: AuditTab; label: string; categories: AuditCategory[] }[] = [
  { id: 'summary', label: 'Summary', categories: [] },
  { id: 'architecture', label: 'Architecture', categories: ['architecture'] },
  { id: 'quality', label: 'Quality', categories: ['quality', 'naming'] },
  { id: 'coverage', label: 'Coverage', categories: ['coverage', 'testing'] },
  { id: 'tech_debt', label: 'Tech Debt', categories: ['size'] },
];

// ── Badge helpers ──────────────────────────────────────────────

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
  P4: 'bg-slate-500/10 text-slate-500',
};

const EFFORT_COLORS: Record<string, string> = {
  small: 'bg-emerald-500/15 text-emerald-400',
  medium: 'bg-amber-500/15 text-amber-400',
  large: 'bg-red-500/15 text-red-400',
};

// Sort priorities (P0 is highest)
const PRIORITY_RANK: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3, P4: 4 };
// Sort severities (critical is highest)
const SEVERITY_RANK: Record<string, number> = { critical: 0, warning: 1, info: 2, suggestion: 3 };

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  if (!text) return null;
  return (
    <span className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide', colorClass)}>
      {text}
    </span>
  );
}

// ── Helpers ────────────────────────────────────────────────────

function getFindingId(f: AuditFinding, idx: number): string {
  return f.finding_id || `legacy-${f.analyzer}-${idx}`;
}

// ── Severity Bar ──────────────────────────────────────────────

function SeverityBar({ findings }: { findings: AuditFinding[] }) {
  const total = findings.length;
  if (total === 0) return null;
  const counts: Record<string, number> = {};
  for (const f of findings) counts[f.severity] = (counts[f.severity] || 0) + 1;
  const barColors: Record<string, string> = { critical: 'bg-red-500', warning: 'bg-amber-500', info: 'bg-blue-500', suggestion: 'bg-emerald-500' };
  const segs = (['critical', 'warning', 'info', 'suggestion'] as AuditSeverity[])
    .filter(s => (counts[s] || 0) > 0)
    .map(s => ({ s, count: counts[s] || 0, pct: ((counts[s] || 0) / total) * 100 }));

  return (
    <div className="space-y-1.5">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-raised">
        {segs.map(({ s, pct }) => (
          <div key={s} className={cn('h-full', barColors[s])} style={{ width: `${pct}%` }} />
        ))}
      </div>
      <div className="flex gap-3 text-[10px] text-text-muted">
        {segs.map(({ s, count }) => (
          <span key={s} className="flex items-center gap-1">
            <span className={cn('inline-block h-1.5 w-1.5 rounded-full', barColors[s])} />
            {count} {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Finding Card (flat, always visible) ───────────────────────

function FindingCard({
  finding,
  uniqueId,
  checked,
  onToggle,
}: {
  finding: AuditFinding;
  uniqueId: string;
  checked: boolean;
  onToggle: () => void;
}) {
  const CheckIcon = checked ? CheckSquare : Square;
  const priority = finding.priority || 'P2';
  const effort = finding.effort || 'medium';
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
          {/* Header Row: Title & Badges */}
          <div className="flex items-start justify-between gap-4">
            <p className={cn("text-sm font-medium leading-snug", checked ? "text-primary" : "text-text")}>
              {finding.title}
            </p>
            <div className="flex shrink-0 items-center gap-1.5 opacity-90">
              <Badge text={priority} colorClass={PRIORITY_COLORS[priority] || PRIORITY_COLORS.P2} />
              <Badge text={finding.severity} colorClass={SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.info} />
              <Badge text={effort} colorClass={EFFORT_COLORS[effort] || EFFORT_COLORS.medium} />
            </div>
          </div>
          
          {/* Sub Row: ID + Files */}
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="font-mono text-[10px] bg-surface-raised/80 px-1.5 py-0.5 rounded text-text-muted/80">{finding.finding_id || uniqueId}</span>
            {finding.file_paths && finding.file_paths.length > 0 && (
              <span className="truncate font-mono">
                {finding.file_paths.slice(0, 3).join(', ')}
                {finding.file_paths.length > 3 && ` +${finding.file_paths.length - 3}`}
              </span>
            )}
          </div>

          {/* Action Box */}
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

// ── Copy helper ───────────────────────────────────────────────

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

// ── Summary Tab Content ───────────────────────────────────────

function SummaryTab({ findings, status, reports, onViewReport }: { findings: AuditFinding[]; status: AuditStatus | null; reports: AuditReport[]; onViewReport: (name: string) => void }) {
  const critical = findings.filter(f => f.severity === 'critical');
  const top5 = [...findings].sort((a, b) => {
    const pA = PRIORITY_RANK[a.priority || 'P2'] ?? 99;
    const pB = PRIORITY_RANK[b.priority || 'P2'] ?? 99;
    if (pA !== pB) return pA - pB;
    return (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
  }).slice(0, 5);

  // Module-level summary from evidence
  const modules = new Map<string, { count: number; worst: string }>();
  for (const f of findings) {
    const mod = (f.evidence as any)?.module || (f.evidence as any)?.source_module || '';
    if (mod) {
      const existing = modules.get(mod);
      if (existing) { existing.count++; } else { modules.set(mod, { count: 1, worst: f.severity }); }
    }
  }

  const summaryReport = reports.find(r => r.name === 'AUDIT_SUMMARY');

  return (
    <div className="space-y-6 p-4">
      {/* Overview stats without the big letter grade */}
      <div className="flex items-center gap-4">
        <div>
          <p className="text-sm font-medium text-text">{findings.length} findings total</p>
          <p className="text-xs text-text-muted">
            {critical.length} critical · {findings.filter(f => f.severity === 'warning').length} warning · {findings.filter(f => f.severity === 'info').length} info
          </p>
          {status?.last_run?.generated_at && (
            <p className="text-[10px] text-text-muted mt-0.5">
              Last run: {new Date(status.last_run.generated_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      <SeverityBar findings={findings} />

      {/* Synthesis report link if available */}
      {summaryReport && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-text">AI Synthesis Available</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => onViewReport(summaryReport.name)} className="h-6 text-[10px]">
            Read Summary
          </Button>
        </div>
      )}

      {/* Top findings */}
      {top5.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">Top Findings</h3>
          <div className="space-y-3">
            {top5.map((f, i) => {
              const uid = getFindingId(f, i);
              const priority = f.priority || 'P2';
              return (
                <div key={uid} className="flex flex-col gap-1.5 text-xs">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-text leading-snug">{f.title}</span>
                    <Badge text={priority} colorClass={PRIORITY_COLORS[priority] || PRIORITY_COLORS.P2} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] bg-surface-raised/80 px-1.5 py-0.5 rounded text-text-muted/80">{f.finding_id || uid}</span>
                  </div>
                  {f.suggested_action && (
                    <div className="mt-0.5 rounded-md bg-surface-raised/40 px-3 py-2 text-xs text-text-muted border border-border/40">
                      <span className="font-semibold text-text">Action:</span> {f.suggested_action}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Module status */}
      {modules.size > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">By Module</h3>
          <div className="space-y-1">
            {[...modules.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 10).map(([name, data]) => (
              <div key={name} className="flex items-center justify-between text-xs">
                <span className="font-mono text-text truncate">{name}</span>
                <span className="text-text-muted">{data.count} findings</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Panel ────────────────────────────────────────────────

export function AuditPanel({
  status,
  findings,
  reports,
  onRunAudit,
  onViewReport,
  reportContent,
  viewingReport,
  className,
}: AuditPanelProps) {
  const [activeTab, setActiveTab] = useState<AuditTab>('summary');
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  const running = status?.running ?? false;
  const hasResults = (status?.has_results ?? false) || findings.length > 0;

  const toggleCheck = useCallback((id: string) => {
    setCheckedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const clearChecks = useCallback(() => setCheckedIds(new Set()), []);

  const checkedFindings = useMemo(
    () => findings.filter((f, i) => checkedIds.has(getFindingId(f, i))),
    [findings, checkedIds],
  );

  // Build the MCP command for selected findings
  const mcpCommand = useMemo(() => {
    if (checkedFindings.length === 0) return 'prep_audit';
    const ids = checkedFindings.map((f, i) => `"${getFindingId(f, i)}"`).join(', ');
    return `prep_audit_refactor finding_ids=[${ids}]`;
  }, [checkedFindings]);

  // Markdown for clipboard copy
  const checkedMarkdown = useMemo(() => {
    if (checkedFindings.length === 0) return '';
    return checkedFindings.map((f, i) => {
      const id = getFindingId(f, i);
      const prio = f.priority || 'P2';
      const eff = f.effort || 'medium';
      return `### ${id}: ${f.title} [${prio} · ${f.severity} · ${eff}]\n` +
      `**Files:** ${(f.file_paths || []).join(', ')}\n` +
      `**Problem:** ${f.description}\n` +
      `**Action:** ${f.suggested_action}\n`
    }).join('\n---\n\n');
  }, [checkedFindings]);

  // Get and sort findings for a tab
  const tabFindings = useCallback((tab: AuditTab) => {
    const cfg = TAB_CONFIG.find(t => t.id === tab);
    if (!cfg || cfg.categories.length === 0) return [];
    const unsorted = findings.filter(f => cfg.categories.includes(f.category));
    return unsorted.sort((a, b) => {
      const pA = PRIORITY_RANK[a.priority || 'P2'] ?? 99;
      const pB = PRIORITY_RANK[b.priority || 'P2'] ?? 99;
      if (pA !== pB) return pA - pB;
      return (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99);
    });
  }, [findings]);

  // Handle "Select All" for current tab
  const handleSelectAllTab = useCallback((tab: AuditTab) => {
    const currentFindings = tabFindings(tab);
    const allIds = currentFindings.map(f => getFindingId(f, findings.indexOf(f)));
    
    // Check if all are currently selected
    const allSelected = allIds.every(id => checkedIds.has(id));
    
    if (allSelected) {
      // Deselect all
      setCheckedIds(prev => {
        const next = new Set(prev);
        allIds.forEach(id => next.delete(id));
        return next;
      });
    } else {
      // Select all
      setCheckedIds(prev => {
        const next = new Set(prev);
        allIds.forEach(id => next.add(id));
        return next;
      });
    }
  }, [tabFindings, checkedIds, findings]);

  // Tab counts
  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const tab of TAB_CONFIG) {
      counts[tab.id] = tab.categories.length > 0
        ? findings.filter(f => tab.categories.includes(f.category)).length
        : 0;
    }
    return counts;
  }, [findings]);

  // Report viewer (full screen takeover)
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

  const currentTabFindings = tabFindings(activeTab);
  const currentTabIds = currentTabFindings.map(f => getFindingId(f, findings.indexOf(f)));
  const isAllSelected = currentTabIds.length > 0 && currentTabIds.every(id => checkedIds.has(id));
  const SelectAllIcon = isAllSelected ? CheckSquare : Square;

  // See if current tab has a related report
  const relatedReportName = TAB_REPORT_MAP[activeTab];
  const relatedReport = relatedReportName ? reports.find(r => r.name === relatedReportName) : null;

  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Empty state & Loading state (No Results) */}
      {!hasResults && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <ClipboardCheck className={cn("h-12 w-12 text-text-muted/30", running && "animate-pulse")} />
          <p className="text-sm font-medium text-text">
            {running ? 'Audit in progress...' : 'No audit results yet'}
          </p>
          
          {!running && (
            <>
              <p className="text-xs text-text-muted max-w-xs">
                Run an audit to get architecture findings, gap analysis, tech debt, and test coverage — all from the trace graph.
              </p>
              <div className="flex gap-2">
                <Button variant="default" size="sm" onClick={() => onRunAudit(false)} className="gap-1.5">
                  <Play className="h-3.5 w-3.5" /> Quick Audit
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onRunAudit(true)} className="gap-1.5">
                  <FileText className="h-3.5 w-3.5" /> Full Report
                </Button>
              </div>
              <p className="text-[10px] text-text-muted mt-2">
                MCP: <code className="rounded bg-surface-raised px-1 py-0.5 text-primary">prep_audit</code>
              </p>
            </>
          )}

          {running && (
            <p className="text-xs text-text-muted">
              Analyzing codebase architecture and quality...
            </p>
          )}
        </div>
      )}

      {/* Results */}
      {hasResults && (
        <>
          {/* Responsive Header: Tabs and Actions share the same row, wrapping to a new line on narrow screens */}
          <div className="flex flex-wrap items-center justify-between border-b border-border bg-surface px-1 gap-y-2">
            {/* Flat tab bar */}
            <div className="flex overflow-x-auto hide-scrollbar">
              {TAB_CONFIG.map(tab => {
                const count = tabCounts[tab.id] || 0;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    className={cn(
                      'shrink-0 px-3 py-2.5 text-xs font-medium transition-colors whitespace-nowrap border-b-2',
                      isActive ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text hover:border-border',
                    )}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                    {count > 0 && <span className="ml-1 text-[10px] opacity-60">{count}</span>}
                  </button>
                );
              })}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 shrink-0 ml-auto">
              <CopyBtn text="prep_audit" label="MCP" icon={Bot} />
              <Button variant="default" size="sm" onClick={() => onRunAudit(false)} disabled={running} className="gap-1 h-7 text-xs">
                {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                {running ? 'Running…' : 'Audit'}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => onRunAudit(true)} disabled={running} className="gap-1 h-7 text-xs">
                <FileText className="h-3 w-3" /> + Report
              </Button>
            </div>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-auto">
            {activeTab === 'summary' && (
              <SummaryTab findings={findings} status={status} reports={reports} onViewReport={onViewReport} />
            )}

            {/* Category findings tabs */}
            {activeTab !== 'summary' && (
              <>
                {/* Inline Report if available */}
                {relatedReport && (
                  <div className="border-b border-border/50 bg-primary/5 px-4 py-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Bot className="h-4 w-4 text-primary" />
                        <span className="text-xs font-semibold text-text uppercase tracking-wide">AI Synthesis Report</span>
                      </div>
                      <Button variant="secondary" size="sm" onClick={() => onViewReport(relatedReport.name)} className="h-6 text-[10px] gap-1">
                        <ExternalLink className="h-3 w-3" /> Read Full
                      </Button>
                    </div>
                    <p className="text-xs text-text-muted">
                      A deep-dive synthesis report was generated for {activeTab}. Click "Read Full" to view the detailed analysis.
                    </p>
                  </div>
                )}

                {/* Select All Bar */}
                {currentTabFindings.length > 0 && (
                  <div className="flex items-center justify-between border-b border-border/50 bg-surface-raised/30 px-4 py-2 sticky top-0 backdrop-blur z-10">
                    <button onClick={() => handleSelectAllTab(activeTab)} className="flex items-center gap-2 text-xs font-medium text-text-muted hover:text-text transition-colors">
                      <SelectAllIcon className="h-4 w-4" />
                      Select All ({currentTabFindings.length})
                    </button>
                    <span className="text-[10px] text-text-muted uppercase tracking-wide">Sorted by Priority</span>
                  </div>
                )}

                {/* Findings List */}
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
              </>
            )}
          </div>

          {/* Bottom action bar — visible when items are checked */}
          {checkedIds.size > 0 && (
            <div className="border-t border-border bg-surface-raised/80 backdrop-blur px-4 py-3 flex items-center gap-3">
              <span className="text-sm font-semibold text-text bg-primary/10 text-primary px-2 py-1 rounded">
                {checkedIds.size} selected
              </span>
              <div className="flex-1" />
              <Button variant="ghost" size="sm" onClick={clearChecks} className="text-xs text-text-muted hover:text-text">
                Clear
              </Button>
              <CopyBtn text={checkedMarkdown} label="Copy as Text" icon={FileText} />
              <CopyBtn text={mcpCommand} label="Copy AI Command" icon={Bot} primary />
            </div>
          )}
        </>
      )}
    </div>
  );
}
