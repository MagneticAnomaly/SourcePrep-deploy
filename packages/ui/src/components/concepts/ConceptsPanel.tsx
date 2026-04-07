import { useState } from 'react';
import {
  Brain,
  Sparkles,
  MessageCircleQuestion,
  Tag,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ChevronRight,
  Trash2,
  Send,
  RefreshCw,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────

export interface ConceptItem {
  id: string;
  title: string;
  content: string;
  category: string;
  status: 'seed' | 'active' | 'archived';
  confidence?: number;
  anchors?: string[];
  tags?: string[];
  stale?: boolean;
  stale_reason?: string;
  created_at?: number;
}

export interface ConceptQuestionItem {
  id: string;
  question: string;
  context: string;
  suggested_category: string;
  target_module?: string;
  answered: boolean;
}

export interface ConceptStats {
  total: number;
  active: number;
  seeds: number;
  archived: number;
  stale: number;
  pending_questions: number;
  by_category: Record<string, number>;
  coverage_pct?: number;
  total_modules?: number;
  covered_modules?: number;
}

export interface ConceptsPanelProps {
  concepts: ConceptItem[];
  questions: ConceptQuestionItem[];
  stats: ConceptStats | null;
  loading: boolean;
  initializing: boolean;
  error: string | null;
  onInitialize: () => void;
  onApprove: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onMarkFresh?: (id: string) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  onRefresh?: () => void;
  onOpenDetail?: () => void;
}

// ── Category Styles ──────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  architecture: { bg: 'rgba(56, 189, 248, 0.12)',  text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' },
  domain:       { bg: 'rgba(52, 211, 153, 0.12)',  text: '#34d399', border: 'rgba(52, 211, 153, 0.3)' },
  product:      { bg: 'rgba(74, 222, 128, 0.12)',  text: '#4ade80', border: 'rgba(74, 222, 128, 0.3)' },
  epistemic:    { bg: 'rgba(192, 132, 252, 0.12)', text: '#c084fc', border: 'rgba(192, 132, 252, 0.3)' },
  process:      { bg: 'rgba(251, 191, 36, 0.12)',  text: '#fbbf24', border: 'rgba(251, 191, 36, 0.3)' },
  brand:        { bg: 'rgba(244, 114, 182, 0.12)', text: '#f472b6', border: 'rgba(244, 114, 182, 0.3)' },
  security:     { bg: 'rgba(251, 113, 133, 0.12)', text: '#fb7185', border: 'rgba(251, 113, 133, 0.3)' },
  technical:    { bg: 'rgba(96, 165, 250, 0.12)',  text: '#60a5fa', border: 'rgba(96, 165, 250, 0.3)' },
  pattern:      { bg: 'rgba(167, 139, 250, 0.12)', text: '#a78bfa', border: 'rgba(167, 139, 250, 0.3)' },
  constraint:   { bg: 'rgba(248, 113, 113, 0.12)', text: '#f87171', border: 'rgba(248, 113, 113, 0.3)' },
  decision:     { bg: 'rgba(251, 146, 60, 0.12)',  text: '#fb923c', border: 'rgba(251, 146, 60, 0.3)' },
};

function CategoryBadge({ category }: { category: string }) {
  const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.technical;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '3px',
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        padding: '2px 6px',
        borderRadius: '4px',
        background: colors.bg,
        color: colors.text,
        border: `1px solid ${colors.border}`,
      }}
    >
      <Tag size={9} />
      {category}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'seed') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', fontWeight: 500, color: '#fbbf24', opacity: 0.8 }}>
        <Sparkles size={10} />
        seed
      </span>
    );
  }
  if (status === 'active') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', fontWeight: 500, color: '#34d399', opacity: 0.8 }}>
        <CheckCircle2 size={10} />
        active
      </span>
    );
  }
  return null;
}

// ── Empty State ──────────────────────────────────────────────────

function EmptyState({ onInitialize, initializing }: { onInitialize: () => void; initializing: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '32px 16px', textAlign: 'center' }}>
      <div style={{
        width: '56px', height: '56px', borderRadius: '14px',
        background: 'linear-gradient(135deg, rgba(167, 139, 250, 0.15), rgba(96, 165, 250, 0.15))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '1px solid rgba(167, 139, 250, 0.2)',
      }}>
        <Brain size={28} style={{ color: '#a78bfa' }} />
      </div>
      <div>
        <h3 style={{ margin: '0 0 6px', fontSize: '15px', fontWeight: 600, color: '#e2e8f0' }}>
          No Concepts Yet
        </h3>
        <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: '1.5', maxWidth: '280px' }}>
          Concepts capture the <em>why</em> behind your code — business rationale, design decisions, domain knowledge.
          Initialize to seed from your pipeline data.
        </p>
      </div>
      <button
        onClick={onInitialize}
        disabled={initializing}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '8px 20px', borderRadius: '8px', border: 'none',
          background: initializing ? 'rgba(167, 139, 250, 0.2)' : 'linear-gradient(135deg, #7c3aed, #6366f1)',
          color: '#fff', fontSize: '13px', fontWeight: 600, cursor: initializing ? 'default' : 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: initializing ? 'none' : '0 2px 8px rgba(124, 58, 237, 0.3)',
        }}
      >
        {initializing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
        {initializing ? 'Generating...' : 'Initialize Concepts'}
      </button>
    </div>
  );
}

// ── Stats Bar ────────────────────────────────────────────────────

function StatsBar({ stats, onRefresh, loading }: { stats: ConceptStats; onRefresh?: () => void; loading?: boolean }) {
  const items = [
    { label: 'Active', value: stats.active, color: '#34d399' },
    { label: 'Seeds', value: stats.seeds, color: '#fbbf24' },
    { label: 'Stale', value: stats.stale, color: '#f87171' },
  ];
  return (
    <div style={{ display: 'flex', gap: '12px', padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
      {items.map((item) => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: item.color }} />
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>{item.label}</span>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0' }}>{item.value}</span>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
        {stats.pending_questions > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <MessageCircleQuestion size={12} style={{ color: '#a78bfa' }} />
            <span style={{ fontSize: '11px', color: '#a78bfa', fontWeight: 500 }}>
              {stats.pending_questions} question{stats.pending_questions !== 1 ? 's' : ''}
            </span>
          </div>
        )}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            title="Refresh concepts"
            style={{
              display: 'flex', alignItems: 'center', padding: '2px',
              borderRadius: '4px', border: 'none', background: 'transparent',
              color: '#64748b', cursor: loading ? 'default' : 'pointer',
              opacity: loading ? 0.4 : 0.6,
              transition: 'opacity 0.15s',
            }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Concept Row ──────────────────────────────────────────────────

function ConceptRow({ concept, onApprove, onArchive, onDelete, onMarkFresh }: {
  concept: ConceptItem;
  onApprove: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onMarkFresh?: (id: string) => void;
}) {
  return (
    <div style={{
      padding: '10px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex', flexDirection: 'column', gap: '4px',
      transition: 'background 0.1s ease',
      cursor: 'default',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', flex: 1 }}>
          {concept.title}
        </span>
        <CategoryBadge category={concept.category} />
        <StatusBadge status={concept.status} />
        {concept.stale && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', color: '#f87171' }}>
            <AlertTriangle size={10} /> stale
            {onMarkFresh && (
              <button
                onClick={(e) => { e.stopPropagation(); onMarkFresh(concept.id); }}
                style={{
                  fontSize: '10px', padding: '0 4px', borderRadius: '3px',
                  border: '1px solid rgba(248, 113, 113, 0.3)', background: 'rgba(248, 113, 113, 0.08)',
                  color: '#f87171', cursor: 'pointer', marginLeft: '2px',
                }}
                title={concept.stale_reason || 'Mark as reviewed'}
              >
                dismiss
              </button>
            )}
          </span>
        )}
      </div>
      <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', lineHeight: '1.5', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
        {concept.content}
      </p>
      {concept.anchors && concept.anchors.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {concept.anchors.slice(0, 3).map((a) => (
            <span key={a} style={{ fontSize: '10px', color: '#64748b', background: 'rgba(255,255,255,0.04)', padding: '1px 5px', borderRadius: '3px' }}>
              {a.split('/').pop()}
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: '6px', marginTop: '2px', alignItems: 'center' }}>
        {concept.status === 'seed' && (
          <>
            <button
              onClick={() => onApprove(concept.id)}
              style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(52, 211, 153, 0.3)', background: 'rgba(52, 211, 153, 0.1)', color: '#34d399', cursor: 'pointer' }}
            >
              Approve
            </button>
            <button
              onClick={() => onArchive(concept.id)}
              style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#64748b', cursor: 'pointer' }}
            >
              Dismiss
            </button>
          </>
        )}
        {concept.status === 'active' && (
          <button
            onClick={() => onArchive(concept.id)}
            style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#64748b', cursor: 'pointer' }}
          >
            Archive
          </button>
        )}
        <button
          onClick={() => onDelete(concept.id)}
          style={{ fontSize: '11px', padding: '2px 4px', borderRadius: '4px', border: 'none', background: 'transparent', color: '#64748b', cursor: 'pointer', marginLeft: 'auto', opacity: 0.5 }}
          title="Delete concept"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}

// ── Question Row ────────────────────────────────────────────────

function QuestionRow({ question, onAnswer }: {
  question: ConceptQuestionItem;
  onAnswer: (questionId: string, answer: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [answerText, setAnswerText] = useState('');

  return (
    <div style={{
      padding: '10px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex', flexDirection: 'column', gap: '6px',
    }}>
      <div
        style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <MessageCircleQuestion size={14} style={{ color: '#a78bfa', marginTop: '2px', flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#e2e8f0' }}>
            {question.question}
          </span>
          {question.context && (
            <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#64748b', lineHeight: '1.4' }}>
              {question.context}
            </p>
          )}
        </div>
        <CategoryBadge category={question.suggested_category} />
      </div>
      {expanded && (
        <div style={{ display: 'flex', gap: '6px', paddingLeft: '22px' }}>
          <input
            type="text"
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            placeholder="Type your answer..."
            onKeyDown={(e) => {
              if (e.key === 'Enter' && answerText.trim()) {
                onAnswer(question.id, answerText.trim());
                setAnswerText('');
                setExpanded(false);
              }
            }}
            style={{
              flex: 1, fontSize: '12px', padding: '5px 8px', borderRadius: '4px',
              border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)',
              color: '#e2e8f0', outline: 'none',
            }}
          />
          <button
            onClick={() => {
              if (answerText.trim()) {
                onAnswer(question.id, answerText.trim());
                setAnswerText('');
                setExpanded(false);
              }
            }}
            disabled={!answerText.trim()}
            style={{
              padding: '4px 8px', borderRadius: '4px', border: 'none',
              background: answerText.trim() ? 'rgba(167, 139, 250, 0.2)' : 'transparent',
              color: answerText.trim() ? '#a78bfa' : '#64748b',
              cursor: answerText.trim() ? 'pointer' : 'default',
            }}
          >
            <Send size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

// ── Coverage Bar ────────────────────────────────────────────

function CoverageBar({ stats }: { stats: ConceptStats }) {
  const pct = stats.coverage_pct ?? 0;
  const total = stats.total_modules ?? 0;
  const covered = stats.covered_modules ?? 0;
  if (total === 0) return null;

  return (
    <div style={{ padding: '6px 12px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
        <span style={{ fontSize: '10px', color: '#94a3b8' }}>
          Module coverage
        </span>
        <span style={{ fontSize: '10px', fontWeight: 600, color: '#e2e8f0' }}>
          {covered}/{total} ({pct}%)
        </span>
      </div>
      <div style={{
        height: '4px', borderRadius: '2px',
        background: 'rgba(255,255,255,0.06)', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: '2px',
          width: `${Math.min(pct, 100)}%`,
          background: pct >= 80 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171',
          transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  );
}

// ── Main Panel ───────────────────────────────────────────────────

export function ConceptsPanel({
  concepts,
  questions,
  stats,
  loading,
  initializing,
  error,
  onInitialize,
  onApprove,
  onArchive,
  onDelete,
  onAnswerQuestion,
  onMarkFresh,
  onRefresh,
  onOpenDetail,
}: ConceptsPanelProps) {
  const isEmpty = !loading && concepts.length === 0 && questions.length === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {error && (
        <div style={{ padding: '8px 12px', background: 'rgba(248, 113, 113, 0.1)', borderBottom: '1px solid rgba(248, 113, 113, 0.2)', fontSize: '12px', color: '#f87171' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '40px', color: '#64748b', fontSize: '13px' }}>
          <Loader2 size={16} className="animate-spin" />
          Loading concepts...
        </div>
      ) : isEmpty ? (
        <EmptyState onInitialize={onInitialize} initializing={initializing} />
      ) : (
        <>
          {stats && <StatsBar stats={stats} onRefresh={onRefresh} loading={loading} />}

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {concepts.slice(0, 20).map((c) => (
              <ConceptRow key={c.id} concept={c} onApprove={onApprove} onArchive={onArchive} onDelete={onDelete} onMarkFresh={onMarkFresh} />
            ))}

            {questions.length > 0 && (
              <div style={{ borderTop: '1px solid rgba(167, 139, 250, 0.15)', marginTop: '4px' }}>
                <div style={{
                  padding: '8px 12px 4px', fontSize: '11px', fontWeight: 600,
                  color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.05em',
                  display: 'flex', alignItems: 'center', gap: '5px',
                }}>
                  <MessageCircleQuestion size={12} />
                  Questions ({questions.length})
                </div>
                {questions.slice(0, 5).map((q) => (
                  <QuestionRow key={q.id} question={q} onAnswer={onAnswerQuestion} />
                ))}
              </div>
            )}
          </div>

          {stats && <CoverageBar stats={stats} />}

          {onOpenDetail && (
            <button
              onClick={onOpenDetail}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
                padding: '8px', borderTop: '1px solid rgba(255,255,255,0.06)',
                background: 'transparent', border: 'none', color: '#a78bfa',
                fontSize: '12px', fontWeight: 500, cursor: 'pointer',
              }}
            >
              {concepts.length > 20 ? `View all ${concepts.length} concepts` : 'Open detail view'} <ChevronRight size={14} />
            </button>
          )}
        </>
      )}
    </div>
  );
}
