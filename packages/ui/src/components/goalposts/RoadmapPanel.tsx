/**
 * RoadmapPanel — Main dashboard panel for the Roadmap feature (Phase 59).
 *
 * Replaces the legacy GoalpostsPanel and AdvisorPanel with a unified
 * vertical timeline view. Wraps RoadmapTimeline with:
 *   - Header bar with tier filter tabs
 *   - Generate / Scan TODO actions
 *   - App Ethos editor (evolved from Product Intent)
 *   - Node detail sidebar (on click)
 *   - Questions section (reused from AdvisorPanel pattern)
 *
 * Props are injected by useDashboardPanels via the panel registry.
 */
import { useState, useMemo, useCallback } from 'react';
import {
  Loader2,
  Sparkles,
  Search,
  AlertCircle,
  Plus,
  Map,
  Send,
  MessageSquare,
  Copy,
  Bot,
  GitBranch,
  Database,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';
import { RoadmapTimeline } from './RoadmapTimeline';
import type {
  RoadmapNode,
  RoadmapTier,
  RoadmapNorthStar,
  GoalpostQuestion,
} from '../../types';

// ── Props ──────────────────────────────────────────────────────

export interface RoadmapPanelProps {
  /** All roadmap nodes */
  nodes: RoadmapNode[];
  /** Design questions */
  questions: GoalpostQuestion[];
  /** North Star node summary */
  northStar: RoadmapNorthStar | null;
  /** App Ethos text */
  appEthos: string;
  /** Whether LLM generation is in progress */
  generating: boolean;
  /** Whether TODO scan is in progress */
  scanning: boolean;
  /** Error from last operation */
  error: string | null;
  /** Whether project has Atlas (minimum for generation) */
  ready: boolean;
  /** Last generation timestamp */
  lastGeneratedAt: string;
  /** Model used */
  modelUsed: string;
  /** Callbacks */
  onGenerate: () => void;
  onScanTodos: () => void;
  onUpdateEthos: (ethos: string) => void;
  onPromoteNode: (nodeId: string, targetTier: RoadmapTier) => void;
  onDismissNode: (nodeId: string) => void;
  onDeleteNode: (nodeId: string) => void;
  onCreateNode: (node: { title: string; description?: string; tier?: string; category?: string; priority?: string }) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  /** Phase 59D: GitHub sync */
  onSyncGitHub?: () => void;
  /** Phase 59D: Pipeline mining */
  onMineRoadmap?: () => void;
  className?: string;
}

// ── Sub-components ─────────────────────────────────────────────

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

function EthosEditor({ ethos, onUpdate }: { ethos: string; onUpdate: (text: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(ethos);

  const handleSave = useCallback(() => { onUpdate(draft.trim()); setEditing(false); }, [draft, onUpdate]);

  if (!editing) {
    return (
      <div className="rounded-lg border border-border/50 bg-surface-raised/30 px-4 py-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wide">App Ethos</span>
          <button onClick={() => { setDraft(ethos); setEditing(true); }} className="text-[10px] text-primary hover:underline">Edit</button>
        </div>
        <p className={cn('text-xs leading-relaxed', ethos ? 'text-text' : 'text-text-muted italic')}>
          {ethos || 'Describe your product vision and values to guide AI-generated roadmap proposals.'}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <span className="text-[10px] font-semibold text-primary uppercase tracking-wide">App Ethos</span>
      <textarea
        value={draft}
        onChange={e => setDraft(e.target.value)}
        rows={3}
        className="w-full mt-2 bg-surface border border-border rounded-md px-3 py-2 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
        placeholder="What does your product do? Who is it for? What's your design philosophy?"
        autoFocus
      />
      <div className="flex items-center justify-end gap-2 mt-2">
        <Button variant="ghost" size="sm" onClick={() => setEditing(false)} className="h-6 text-[10px]">Cancel</Button>
        <Button variant="default" size="sm" onClick={handleSave} className="h-6 text-[10px]">Save</Button>
      </div>
    </div>
  );
}

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

function AddNodeForm({ onSubmit, onCancel }: { onSubmit: (node: { title: string; tier: string; category: string; priority: string }) => void; onCancel: () => void }) {
  const [title, setTitle] = useState('');
  const [tier, setTier] = useState<string>('planned');
  const [category, setCategory] = useState('feature');
  const [priority, setPriority] = useState('P2');

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 space-y-2">
      <span className="text-[10px] font-semibold text-primary uppercase tracking-wide">Add Roadmap Node</span>
      <input
        type="text"
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Node title..."
        className="w-full bg-surface border border-border rounded-md px-3 py-2 text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
        autoFocus
      />
      <div className="flex gap-2">
        <select value={tier} onChange={e => setTier(e.target.value)} className="bg-surface border border-border rounded-md px-2 py-1.5 text-xs text-text">
          <option value="planned">Planned</option>
          <option value="proposed">Proposed</option>
          <option value="active">Active</option>
        </select>
        <select value={category} onChange={e => setCategory(e.target.value)} className="bg-surface border border-border rounded-md px-2 py-1.5 text-xs text-text">
          <option value="feature">Feature</option>
          <option value="architecture">Architecture</option>
          <option value="tech_debt">Tech Debt</option>
          <option value="security">Security</option>
          <option value="research">Research</option>
          <option value="product">Product/UX</option>
          <option value="market">Market</option>
        </select>
        <select value={priority} onChange={e => setPriority(e.target.value)} className="bg-surface border border-border rounded-md px-2 py-1.5 text-xs text-text">
          <option value="P0">P0 – Critical</option>
          <option value="P1">P1 – High</option>
          <option value="P2">P2 – Medium</option>
          <option value="P3">P3 – Low</option>
        </select>
      </div>
      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel} className="h-6 text-[10px]">Cancel</Button>
        <Button variant="default" size="sm" onClick={() => { if (title.trim()) { onSubmit({ title: title.trim(), tier, category, priority }); } }} disabled={!title.trim()} className="h-6 text-[10px]">
          Add
        </Button>
      </div>
    </div>
  );
}

// ── Main Panel ─────────────────────────────────────────────────

export function RoadmapPanel({
  nodes, questions, northStar, appEthos,
  generating, scanning, error, ready,
  lastGeneratedAt, modelUsed,
  onGenerate, onScanTodos, onUpdateEthos,
  onPromoteNode, onDismissNode, onDeleteNode: _onDeleteNode, onCreateNode,
  onAnswerQuestion, onSyncGitHub, onMineRoadmap,
  className,
}: RoadmapPanelProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const unanswered = useMemo(() => questions.filter(q => !q.answered), [questions]);
  const answered = useMemo(() => questions.filter(q => q.answered), [questions]);
  const hasContent = nodes.length > 0 || questions.length > 0;

  const tierCounts = useMemo(() => ({
    completed: nodes.filter(n => n.tier === 'completed').length,
    active: nodes.filter(n => n.tier === 'active').length,
    planned: nodes.filter(n => n.tier === 'planned').length,
    proposed: nodes.filter(n => n.tier === 'proposed').length,
  }), [nodes]);

  // ── Empty state ─────────────────────────────────────────────
  if (!hasContent && !generating && !scanning) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Map className="h-12 w-12 text-text-muted/30" />
          <p className="text-sm font-medium text-text">Project Roadmap</p>
          <p className="text-xs text-text-muted max-w-sm">
            A visual timeline of your project's past, present, and future.
            Start by describing your product ethos, then generate AI proposals or scan for TODOs.
          </p>
          <div className="w-full max-w-md">
            <EthosEditor ethos={appEthos} onUpdate={onUpdateEthos} />
          </div>
          <div className="flex gap-2 mt-2">
            {ready && (
              <Button variant="default" size="sm" onClick={onGenerate} disabled={generating} className="gap-1.5">
                <Sparkles className="h-3.5 w-3.5" /> Generate Proposals
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onScanTodos} disabled={scanning} className="gap-1.5">
              <Search className="h-3.5 w-3.5" /> Scan TODOs
            </Button>
          </div>
          <p className="text-[10px] text-text-muted mt-1">
            MCP: <code className="rounded bg-surface-raised px-1 py-0.5 text-primary">codrag_audit action='roadmap'</code>
          </p>
        </div>
      </div>
    );
  }

  // ── Loading state ───────────────────────────────────────────
  if ((generating || scanning) && !hasContent) {
    return (
      <div className={cn('flex h-full flex-col', className)}>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
          <Map className="h-12 w-12 text-primary animate-pulse" />
          <p className="text-sm font-medium text-text">
            {generating ? 'Generating roadmap proposals...' : 'Scanning codebase for TODOs...'}
          </p>
          <Loader2 className="h-5 w-5 text-primary animate-spin" />
        </div>
      </div>
    );
  }

  // ── Main content ────────────────────────────────────────────
  return (
    <div className={cn('flex h-full flex-col', className)}>
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between border-b border-border bg-surface px-3 py-2 gap-y-2">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-text flex items-center gap-1.5">
            <Map className="h-3.5 w-3.5" />
            Roadmap
          </span>
          <div className="flex items-center gap-1 text-[10px] text-text-muted">
            {(['completed', 'active', 'planned', 'proposed'] as const).map(t => (
              <span key={t} className={cn(
                'px-1.5 py-0.5 rounded',
                tierCounts[t] > 0 ? 'bg-surface-raised' : 'opacity-50',
              )}>
                {t === 'completed' ? '✅' : t === 'active' ? '🔥' : t === 'planned' ? '📋' : '💡'}
                {tierCounts[t]}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-auto">
          <Button variant="ghost" size="sm" onClick={() => setShowAddForm(!showAddForm)} className="gap-1 h-7 text-xs">
            <Plus className="h-3 w-3" /> Add
          </Button>
          {onMineRoadmap && (
            <Button variant="ghost" size="sm" onClick={onMineRoadmap} className="gap-1 h-7 text-xs">
              <Database className="h-3 w-3" /> Mine
            </Button>
          )}
          {onSyncGitHub && (
            <Button variant="ghost" size="sm" onClick={onSyncGitHub} className="gap-1 h-7 text-xs">
              <GitBranch className="h-3 w-3" /> GitHub
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onScanTodos} disabled={scanning} className="gap-1 h-7 text-xs">
            {scanning ? <Loader2 className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
            TODOs
          </Button>
          <Button variant="default" size="sm" onClick={onGenerate} disabled={generating || !ready} className="gap-1 h-7 text-xs">
            {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {generating ? 'Generating…' : 'Generate'}
          </Button>
        </div>
      </div>

      {/* Error bar */}
      {error && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 flex items-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {/* Ethos */}
        <div className="p-4 border-b border-border/30">
          <EthosEditor ethos={appEthos} onUpdate={onUpdateEthos} />
        </div>

        {/* Add form */}
        {showAddForm && (
          <div className="p-4 border-b border-border/30">
            <AddNodeForm
              onSubmit={(node) => { onCreateNode(node); setShowAddForm(false); }}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

        {/* Questions */}
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

        {/* Timeline */}
        <div className="p-4">
          <RoadmapTimeline
            nodes={nodes}
            northStar={northStar}
            selectedNodeId={selectedNodeId}
            onNodeClick={setSelectedNodeId}
            onPromoteNode={onPromoteNode}
            onDismissNode={onDismissNode}
          />
        </div>

        {/* Answered questions (collapsible) */}
        {answered.length > 0 && (
          <div className="px-4 pb-4">
            <details className="group">
              <summary className="text-[10px] font-semibold text-text-muted uppercase tracking-wide cursor-pointer hover:text-text transition-colors">
                Answered Questions ({answered.length})
              </summary>
              <div className="mt-2 space-y-2">
                {answered.map(q => (
                  <QuestionCard key={q.id} question={q} onAnswer={() => {}} />
                ))}
              </div>
            </details>
          </div>
        )}

        {/* MCP reference */}
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2">
            <CopyBtn text="codrag_audit action='roadmap'" label="Copy MCP command" />
          </div>
        </div>
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
