import { useState, useMemo, useCallback } from 'react';
import {
  Target,
  Loader2,
  Check,
  X,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Send,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import type {
  GoalpostProposal,
  GoalpostQuestion,
} from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface GoalpostsPanelProps {
  /** Current product intent text */
  productIntent: string;
  /** All proposals from LLM */
  proposals: GoalpostProposal[];
  /** All design questions from LLM */
  questions: GoalpostQuestion[];
  /** Whether generation is in progress */
  generating: boolean;
  /** Error message from last generation */
  error: string | null;
  /** Whether the project has Atlas data (minimum for generation) */
  ready: boolean;
  /** Whether audit data is available */
  hasAudit: boolean;
  /** Whether user has set product intent */
  hasIntent: boolean;
  /** What's missing before generation can run */
  missing: string[];
  /** Last generation timestamp */
  lastGeneratedAt: string;
  /** Model used for last generation */
  modelUsed: string;
  /** Callbacks */
  onGenerate: () => void;
  onUpdateIntent: (intent: string) => void;
  onApprove: (proposalId: string) => void;
  onDismiss: (proposalId: string) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  className?: string;
}

// ── Badge helpers ──────────────────────────────────────────────

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

// ── Proposal Card ─────────────────────────────────────────────

function ProposalCard({
  proposal,
  onApprove,
  onDismiss,
}: {
  proposal: GoalpostProposal;
  onApprove: () => void;
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isActioned = proposal.state === 'approved' || proposal.state === 'dismissed';

  return (
    <div className={cn(
      'rounded-lg border px-4 py-3.5 transition-all',
      STATE_COLORS[proposal.state] || STATE_COLORS.proposed,
    )}>
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
          <p className={cn(
            'text-sm font-medium leading-snug',
            proposal.state === 'dismissed' ? 'text-text-muted line-through' : 'text-text',
          )}>
            {proposal.title}
          </p>
          <p className="text-xs text-text-muted mt-1 leading-relaxed">
            {proposal.rationale}
          </p>
        </div>

        {/* Actions */}
        {!isActioned && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={onApprove}
              className="p-1.5 rounded-md text-emerald-400 hover:bg-emerald-500/20 transition-colors"
              title="Approve this goalpost"
            >
              <Check className="h-4 w-4" />
            </button>
            <button
              onClick={onDismiss}
              className="p-1.5 rounded-md text-text-muted hover:bg-red-500/20 hover:text-red-400 transition-colors"
              title="Dismiss this goalpost"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Tasks (expandable) */}
      {proposal.tasks.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[10px] font-medium text-text-muted hover:text-text transition-colors uppercase tracking-wide"
          >
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
    </div>
  );
}

// ── Question Card ─────────────────────────────────────────────

function QuestionCard({
  question,
  onAnswer,
}: {
  question: GoalpostQuestion;
  onAnswer: (answer: string) => void;
}) {
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(() => {
    if (!answer.trim()) return;
    setSubmitting(true);
    onAnswer(answer.trim());
    setAnswer('');
    setTimeout(() => setSubmitting(false), 300);
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
          {question.context && (
            <p className="text-[10px] text-text-muted mt-1">{question.context}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <input
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="Type your answer..."
              className="flex-1 bg-surface-raised border border-border rounded-md px-2.5 py-1.5 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
            <button
              onClick={handleSubmit}
              disabled={!answer.trim() || submitting}
              className="p-1.5 rounded-md text-primary hover:bg-primary/20 transition-colors disabled:opacity-30"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Intent Editor ─────────────────────────────────────────────

function IntentEditor({
  intent,
  onUpdate,
}: {
  intent: string;
  onUpdate: (intent: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(intent);

  const handleSave = useCallback(() => {
    onUpdate(draft.trim());
    setEditing(false);
  }, [draft, onUpdate]);

  if (!editing) {
    return (
      <div className="rounded-lg border border-border/50 bg-surface-raised/30 px-4 py-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wide">Product Intent</span>
          <button
            onClick={() => { setDraft(intent); setEditing(true); }}
            className="text-[10px] text-primary hover:underline"
          >
            Edit
          </button>
        </div>
        <p className={cn('text-xs leading-relaxed', intent ? 'text-text' : 'text-text-muted italic')}>
          {intent || 'No product intent set. Click edit to describe your product direction.'}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold text-primary uppercase tracking-wide">Product Intent</span>
      </div>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        className="w-full bg-surface border border-border rounded-md px-3 py-2 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
        placeholder="Describe your product: what it does, who it's for, and where you want to take it..."
        autoFocus
      />
      <div className="flex items-center justify-end gap-2 mt-2">
        <Button variant="ghost" size="sm" onClick={() => setEditing(false)} className="h-6 text-[10px]">
          Cancel
        </Button>
        <Button variant="default" size="sm" onClick={handleSave} className="h-6 text-[10px]">
          Save
        </Button>
      </div>
    </div>
  );
}

// ── Category Stats ────────────────────────────────────────────

function CategoryStats({ proposals }: { proposals: GoalpostProposal[] }) {
  const stats = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of proposals) {
      if (p.state !== 'dismissed') {
        counts[p.category] = (counts[p.category] || 0) + 1;
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [proposals]);

  if (stats.length === 0) return null;

  return (
    <div className="flex gap-2 flex-wrap">
      {stats.map(([cat, count]) => (
        <div key={cat} className="flex items-center gap-1.5">
          <Badge text={CATEGORY_LABELS[cat] || cat} colorClass={CATEGORY_COLORS[cat] || CATEGORY_COLORS.feature} />
          <span className="text-[10px] text-text-muted">{count}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Panel ────────────────────────────────────────────────

export function GoalpostsPanel({
  productIntent,
  proposals,
  questions,
  generating,
  error,
  ready,
  missing,
  lastGeneratedAt,
  modelUsed,
  onGenerate,
  onUpdateIntent,
  onApprove,
  onDismiss,
  onAnswerQuestion,
  className,
}: GoalpostsPanelProps) {
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

  // ── Empty state ─────────────────────────────────────────────
  if (!hasResults && !generating) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Target className="h-12 w-12 text-text-muted/30" />
          <p className="text-sm font-medium text-text">No goalposts yet</p>
          <p className="text-xs text-text-muted max-w-sm">
            Goalposts analyzes your codebase Atlas and audit findings to propose actionable milestones.
            Set your product intent, then generate to get started.
          </p>

          {/* Intent editor */}
          <div className="w-full max-w-md">
            <IntentEditor intent={productIntent} onUpdate={onUpdateIntent} />
          </div>

          {/* Readiness */}
          {!ready && missing.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 max-w-sm">
              <AlertCircle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
              <div className="text-xs text-text-muted">
                {missing.map((m, i) => <p key={i}>{m}</p>)}
              </div>
            </div>
          )}

          {ready && (
            <Button variant="default" size="sm" onClick={onGenerate} disabled={generating} className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5" /> Generate Goalposts
            </Button>
          )}

          <p className="text-[10px] text-text-muted mt-1">
            MCP: <code className="rounded bg-surface-raised px-1 py-0.5 text-primary">codrag_goalposts</code>
          </p>
        </div>
      </div>
    );
  }

  // ── Loading state ───────────────────────────────────────────
  if (generating && !hasResults) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Target className="h-12 w-12 text-primary animate-pulse" />
          <p className="text-sm font-medium text-text">Generating goalposts...</p>
          <p className="text-xs text-text-muted">Analyzing codebase architecture, audit findings, and product intent.</p>
          <Loader2 className="h-5 w-5 text-primary animate-spin" />
        </div>
      </div>
    );
  }

  // ── Results ─────────────────────────────────────────────────
  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between border-b border-border bg-surface px-3 py-2 gap-y-2">
        {/* Filter tabs */}
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
                activeFilter === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-text-muted hover:text-text hover:border-border',
              )}
              onClick={() => setActiveFilter(tab.id)}
            >
              {tab.label}
              {tab.count > 0 && <span className="ml-1 text-[10px] opacity-60">{tab.count}</span>}
            </button>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 shrink-0 ml-auto">
          <Button
            variant="default"
            size="sm"
            onClick={onGenerate}
            disabled={generating || !ready}
            className="gap-1 h-7 text-xs"
          >
            {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {generating ? 'Generating…' : 'Generate'}
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 flex items-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {/* Intent editor */}
        <div className="p-4 border-b border-border/30">
          <IntentEditor intent={productIntent} onUpdate={onUpdateIntent} />
        </div>

        {/* Questions section */}
        {unanswered.length > 0 && (
          <div className="p-4 border-b border-border/30">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <MessageSquare className="h-3.5 w-3.5" />
              Questions for You ({unanswered.length})
            </h3>
            <div className="space-y-2">
              {unanswered.map(q => (
                <QuestionCard key={q.id} question={q} onAnswer={(a) => onAnswerQuestion(q.id, a)} />
              ))}
            </div>
          </div>
        )}

        {/* Category stats */}
        {filtered.length > 0 && (
          <div className="px-4 pt-4 pb-2">
            <CategoryStats proposals={filtered} />
          </div>
        )}

        {/* Proposals */}
        <div className="p-4 space-y-3">
          {filtered.length === 0 ? (
            <div className="text-center py-8">
              <Target className="h-8 w-8 text-text-muted/30 mx-auto mb-3" />
              <p className="text-sm font-medium text-text">No {activeFilter} goalposts</p>
              <p className="text-xs text-text-muted mt-1">
                {activeFilter === 'approved'
                  ? 'Approve proposed goalposts to see them here.'
                  : 'Generate goalposts to get new proposals.'}
              </p>
            </div>
          ) : (
            filtered.map(p => (
              <ProposalCard
                key={p.id}
                proposal={p}
                onApprove={() => onApprove(p.id)}
                onDismiss={() => onDismiss(p.id)}
              />
            ))
          )}
        </div>

        {/* Answered questions (collapsed section) */}
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

      {/* Footer metadata */}
      {lastGeneratedAt && (
        <div className="border-t border-border/50 px-4 py-2 flex items-center justify-between text-[10px] text-text-muted">
          <span>Last generated: {new Date(lastGeneratedAt).toLocaleString()}</span>
          {modelUsed && <span className="font-mono">{modelUsed}</span>}
        </div>
      )}
    </div>
  );
}
