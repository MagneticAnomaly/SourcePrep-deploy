/**
 * AdvisorPanel — Forward-looking design proposals (Phase 57B).
 *
 * Evolves from GoalpostsPanel with the addition of:
 *   - Unified action bar with "Copy for AI" pattern per proposal
 *   - Updated MCP reference (codrag_audit action='advise')
 *   - User notes field for AI handoff context
 *
 * Wraps GoalpostsPanel's core UX (intent editor, proposal cards,
 * question cards) with the new branding and action patterns.
 */
import { useState, useMemo, useCallback } from 'react';
import {
  Loader2,
  Check,
  X,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Send,
  Sparkles,
  AlertCircle,
  Bot,
  Copy,
  Compass,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type { GoalpostProposal, GoalpostQuestion } from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface AdvisorPanelProps {
  productIntent: string;
  proposals: GoalpostProposal[];
  questions: GoalpostQuestion[];
  generating: boolean;
  error: string | null;
  ready: boolean;
  hasAudit: boolean;
  hasIntent: boolean;
  missing: string[];
  lastGeneratedAt: string;
  modelUsed: string;
  onGenerate: () => void;
  onUpdateIntent: (intent: string) => void;
  onApprove: (proposalId: string) => void;
  onDismiss: (proposalId: string) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  className?: string;
}

// ── Style constants ────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  architecture: 'bg-violet-500/20 text-violet-400',
  security: 'bg-red-500/20 text-red-400',
  feature: 'bg-blue-500/20 text-blue-400',
  tech_debt: 'bg-amber-500/20 text-amber-400',
  research: 'bg-emerald-500/20 text-emerald-400',
};

const CATEGORY_LABELS: Record<string, string> = {
  architecture: 'Architecture',
  security: 'Security',
  feature: 'Feature',
  tech_debt: 'Tech Debt',
  research: 'Research',
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

const STATE_COLORS: Record<string, string> = {
  proposed: 'bg-blue-500/10 border-blue-500/30',
  approved: 'bg-emerald-500/10 border-emerald-500/30',
  dismissed: 'bg-slate-500/10 border-slate-500/20 opacity-50',
};

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  if (!text) return null;
  return (
    <span className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide', colorClass)}>
      {text}
    </span>
  );
}

function CopyBtn({ text, label, primary = false }: { text: string; label: string; primary?: boolean }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }, [text]);
  return (
    <Button variant={primary ? 'default' : 'ghost'} size="sm" onClick={handleCopy} className={cn("gap-1.5 text-xs", primary && "font-medium")}>
      {primary ? <Bot className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? 'Copied!' : label}
    </Button>
  );
}

// ── Proposal Card with Copy for AI ─────────────────────────────

function ProposalCard({ proposal, onApprove, onDismiss }: {
  proposal: GoalpostProposal; onApprove: () => void; onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isActioned = proposal.state === 'approved' || proposal.state === 'dismissed';

  // Generate MCP command for this proposal
  const mcpCommand = `codrag_audit action="advise"`;

  return (
    <div className={cn('rounded-lg border px-4 py-3.5 transition-all', STATE_COLORS[proposal.state] || STATE_COLORS.proposed)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge text={proposal.priority} colorClass={PRIORITY_COLORS[proposal.priority] || PRIORITY_COLORS.P2} />
            <Badge text={CATEGORY_LABELS[proposal.category] || proposal.category} colorClass={CATEGORY_COLORS[proposal.category] || CATEGORY_COLORS.feature} />
            {proposal.state === 'approved' && (
              <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-400">
                <Check className="h-3 w-3" /> Approved
              </span>
            )}
          </div>
          <p className={cn('text-sm font-medium leading-snug', proposal.state === 'dismissed' ? 'text-text-muted line-through' : 'text-text')}>
            {proposal.title}
          </p>
          <p className="text-xs text-text-muted mt-1 leading-relaxed">{proposal.rationale}</p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {!isActioned && (
            <>
              <button onClick={onApprove} className="p-1.5 rounded-md text-emerald-400 hover:bg-emerald-500/20 transition-colors" title="Approve">
                <Check className="h-4 w-4" />
              </button>
              <button onClick={onDismiss} className="p-1.5 rounded-md text-text-muted hover:bg-red-500/20 hover:text-red-400 transition-colors" title="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Tasks (expandable) */}
      {proposal.tasks.length > 0 && (
        <div className="mt-2">
          <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1 text-[10px] font-medium text-text-muted hover:text-text transition-colors uppercase tracking-wide">
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {proposal.tasks.length} task{proposal.tasks.length !== 1 ? 's' : ''}
          </button>

          {expanded && (
            <div className="mt-2 space-y-2 pl-1">
              {proposal.tasks.map((task, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-text-muted mt-0.5 shrink-0">•</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-text">{task.description}</span>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge text={task.effort} colorClass={EFFORT_COLORS[task.effort] || EFFORT_COLORS.small} />
                      {task.file_paths.length > 0 && (
                        <span className="font-mono text-[10px] text-text-muted truncate">
                          {task.file_paths.slice(0, 2).join(', ')}
                          {task.file_paths.length > 2 && ` +${task.file_paths.length - 2}`}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Copy for AI */}
      {proposal.state === 'approved' && (
        <div className="mt-3 pt-2 border-t border-border/30 flex items-center gap-2">
          <CopyBtn text={mcpCommand} label="Copy for AI" primary />
        </div>
      )}
    </div>
  );
}

// ── Question Card ──────────────────────────────────────────────

function QuestionCard({ question, onAnswer }: { question: GoalpostQuestion; onAnswer: (answer: string) => void }) {
  const [answer, setAnswer] = useState('');

  const handleSubmit = useCallback(() => {
    if (!answer.trim()) return;
    onAnswer(answer.trim());
    setAnswer('');
  }, [answer, onAnswer]);

  if (question.answered) {
    return (
      <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
        <div className="flex items-start gap-2">
          <MessageSquare className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-text">{question.question}</p>
            <p className="text-xs text-emerald-400 mt-1">✓ {question.answer}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3">
      <div className="flex items-start gap-2">
        <MessageSquare className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text">{question.question}</p>
          {question.context && <p className="text-[10px] text-text-muted mt-1">{question.context}</p>}
          <div className="flex items-center gap-2 mt-2">
            <input
              type="text"
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="Type your answer..."
              className="flex-1 bg-surface-raised border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
            <button onClick={handleSubmit} disabled={!answer.trim()} className="p-1.5 rounded-md text-primary hover:bg-primary/20 transition-colors disabled:opacity-30">
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Intent Editor ──────────────────────────────────────────────

function IntentEditor({ intent, onUpdate }: { intent: string; onUpdate: (intent: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(intent);

  const handleSave = useCallback(() => { onUpdate(draft.trim()); setEditing(false); }, [draft, onUpdate]);

  if (!editing) {
    return (
      <div className="rounded-lg border border-border/50 bg-surface-raised/30 px-4 py-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wide">Product Intent</span>
          <button onClick={() => { setDraft(intent); setEditing(true); }} className="text-[10px] text-primary hover:underline">Edit</button>
        </div>
        <p className={cn('text-xs leading-relaxed', intent ? 'text-text' : 'text-text-muted italic')}>
          {intent || 'No product intent set. Click edit to describe your product direction.'}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <span className="text-[10px] font-semibold text-primary uppercase tracking-wide">Product Intent</span>
      <textarea
        value={draft}
        onChange={e => setDraft(e.target.value)}
        rows={3}
        className="w-full mt-2 bg-surface border border-border rounded-md px-3 py-2 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
        placeholder="Describe your product: what it does, who it's for, and where you want to take it..."
        autoFocus
      />
      <div className="flex items-center justify-end gap-2 mt-2">
        <Button variant="ghost" size="sm" onClick={() => setEditing(false)} className="h-6 text-[10px]">Cancel</Button>
        <Button variant="default" size="sm" onClick={handleSave} className="h-6 text-[10px]">Save</Button>
      </div>
    </div>
  );
}

// ── Main Panel ─────────────────────────────────────────────────

export function AdvisorPanel({
  productIntent, proposals, questions, generating, error,
  ready, missing, lastGeneratedAt, modelUsed,
  onGenerate, onUpdateIntent, onApprove, onDismiss, onAnswerQuestion,
  className,
}: AdvisorPanelProps) {
  const [activeFilter, setActiveFilter] = useState<'all' | 'proposed' | 'approved'>('all');

  const proposed = useMemo(() => proposals.filter(p => p.state === 'proposed'), [proposals]);
  const approved = useMemo(() => proposals.filter(p => p.state === 'approved'), [proposals]);
  const unanswered = useMemo(() => questions.filter(q => !q.answered), [questions]);

  const filtered = useMemo(() => {
    if (activeFilter === 'proposed') return proposals.filter(p => p.state === 'proposed');
    if (activeFilter === 'approved') return proposals.filter(p => p.state === 'approved');
    return proposals.filter(p => p.state !== 'dismissed');
  }, [proposals, activeFilter]);

  const hasResults = proposals.length > 0 || questions.length > 0;

  // Empty state
  if (!hasResults && !generating) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Compass className="h-12 w-12 text-text-muted/30" />
          <p className="text-sm font-medium text-text">No advisor proposals yet</p>
          <p className="text-xs text-text-muted max-w-sm">
            The Advisor analyzes your codebase architecture and audit findings to propose actionable design milestones.
            Set your product intent, then generate to get started.
          </p>
          <div className="w-full max-w-md">
            <IntentEditor intent={productIntent} onUpdate={onUpdateIntent} />
          </div>
          {!ready && missing.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 max-w-sm">
              <AlertCircle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
              <div className="text-xs text-text-muted">{missing.map((m, i) => <p key={i}>{m}</p>)}</div>
            </div>
          )}
          {ready && (
            <Button variant="default" size="sm" onClick={onGenerate} disabled={generating} className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5" /> Generate Proposals
            </Button>
          )}
          <p className="text-[10px] text-text-muted mt-1">
            MCP: <code className="rounded bg-surface-raised px-1 py-0.5 text-primary">codrag_audit action='advise'</code>
          </p>
        </div>
      </div>
    );
  }

  // Loading state
  if (generating && !hasResults) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Compass className="h-12 w-12 text-primary animate-pulse" />
          <p className="text-sm font-medium text-text">Generating proposals...</p>
          <p className="text-xs text-text-muted">Analyzing codebase architecture, health findings, and product intent.</p>
          <Loader2 className="h-5 w-5 text-primary animate-spin" />
        </div>
      </div>
    );
  }

  // Results
  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-border bg-surface px-3 py-2 gap-y-2">
        <div className="flex overflow-x-auto hide-scrollbar">
          {([
            { id: 'all' as const, label: 'Active', count: filtered.length },
            { id: 'proposed' as const, label: 'Proposed', count: proposed.length },
            { id: 'approved' as const, label: 'Approved', count: approved.length },
          ]).map(tab => (
            <button
              key={tab.id}
              className={cn(
                'shrink-0 px-3 py-2 text-xs font-medium transition-colors whitespace-nowrap border-b-2',
                activeFilter === tab.id ? 'border-primary text-primary' : 'border-transparent text-text-muted hover:text-text',
              )}
              onClick={() => setActiveFilter(tab.id)}
            >
              {tab.label}
              {tab.count > 0 && <span className="ml-1 text-[10px] opacity-60">{tab.count}</span>}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-auto">
          <Button variant="default" size="sm" onClick={onGenerate} disabled={generating || !ready} className="gap-1 h-7 text-xs">
            {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {generating ? 'Generating…' : 'Generate'}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 flex items-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="p-4 border-b border-border/30">
          <IntentEditor intent={productIntent} onUpdate={onUpdateIntent} />
        </div>

        {unanswered.length > 0 && (
          <div className="p-4 border-b border-border/30">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <MessageSquare className="h-3.5 w-3.5" />
              Questions for You ({unanswered.length})
            </h3>
            <div className="space-y-2">
              {unanswered.map(q => (
                <QuestionCard key={q.id} question={q} onAnswer={a => onAnswerQuestion(q.id, a)} />
              ))}
            </div>
          </div>
        )}

        <div className="p-4 space-y-3">
          {filtered.length === 0 ? (
            <div className="text-center py-8">
              <Compass className="h-8 w-8 text-text-muted/30 mx-auto mb-3" />
              <p className="text-sm font-medium text-text">No {activeFilter} proposals</p>
              <p className="text-xs text-text-muted mt-1">
                {activeFilter === 'approved' ? 'Approve proposed items to see them here.' : 'Generate to get new proposals.'}
              </p>
            </div>
          ) : (
            filtered.map(p => (
              <ProposalCard key={p.id} proposal={p} onApprove={() => onApprove(p.id)} onDismiss={() => onDismiss(p.id)} />
            ))
          )}
        </div>

        {questions.filter(q => q.answered).length > 0 && (
          <div className="px-4 pb-4">
            <details className="group">
              <summary className="text-[10px] font-semibold text-text-muted uppercase tracking-wide cursor-pointer hover:text-text transition-colors">
                Answered Questions ({questions.filter(q => q.answered).length})
              </summary>
              <div className="mt-2 space-y-2">
                {questions.filter(q => q.answered).map(q => (
                  <QuestionCard key={q.id} question={q} onAnswer={() => {}} />
                ))}
              </div>
            </details>
          </div>
        )}
      </div>

      {/* Footer */}
      {lastGeneratedAt && (
        <div className="border-t border-border/50 px-4 py-2 flex items-center justify-between text-[10px] text-text-muted">
          <span>Last generated: {new Date(lastGeneratedAt).toLocaleString()}</span>
          {modelUsed && <span className="font-mono">{modelUsed}</span>}
        </div>
      )}
    </div>
  );
}
