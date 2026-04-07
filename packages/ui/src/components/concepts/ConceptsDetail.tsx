import { useState, useMemo } from 'react';
import {
  Brain,
  Sparkles,
  MessageCircleQuestion,
  Tag,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  Send,
  Filter,
  Search,
  RefreshCw,
} from 'lucide-react';
import type { ConceptItem, ConceptQuestionItem, ConceptStats } from './ConceptsPanel';

// ── Types ────────────────────────────────────────────────────────

export interface ConceptsDetailProps {
  concepts: ConceptItem[];
  questions: ConceptQuestionItem[];
  stats: ConceptStats | null;
  loading: boolean;
  onApprove: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onMarkFresh?: (id: string) => void;
  onAnswerQuestion: (questionId: string, answer: string) => void;
  onRefresh?: () => void;
}

// ── Category Colors (shared with panel) ─────────────────────────

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

// ── Subcomponents ───────────────────────────────────────────────

function CategoryBadge({ category, onClick, active }: { category: string; onClick?: () => void; active?: boolean }) {
  const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.technical;
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '4px',
        fontSize: '11px', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase',
        padding: '3px 8px', borderRadius: '4px',
        background: active ? colors.text : colors.bg,
        color: active ? '#0f172a' : colors.text,
        border: `1px solid ${colors.border}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s ease',
      }}
    >
      <Tag size={10} />
      {category}
    </button>
  );
}

function StatusFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const options = [
    { key: 'all', label: 'All' },
    { key: 'active', label: 'Active', color: '#34d399' },
    { key: 'seed', label: 'Seeds', color: '#fbbf24' },
  ];
  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {options.map((opt) => (
        <button
          key={opt.key}
          onClick={() => onChange(opt.key)}
          style={{
            fontSize: '11px', fontWeight: 500, padding: '3px 10px', borderRadius: '4px',
            border: `1px solid ${value === opt.key ? 'rgba(167, 139, 250, 0.5)' : 'rgba(255,255,255,0.08)'}`,
            background: value === opt.key ? 'rgba(167, 139, 250, 0.15)' : 'transparent',
            color: value === opt.key ? '#a78bfa' : '#94a3b8',
            cursor: 'pointer', transition: 'all 0.15s',
          }}
        >
          {opt.color && <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: opt.color, marginRight: '4px' }} />}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function DetailConceptCard({
  concept, onApprove, onArchive, onDelete, onMarkFresh,
}: {
  concept: ConceptItem;
  onApprove: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onMarkFresh?: (id: string) => void;
}) {
  const colors = CATEGORY_COLORS[concept.category] || CATEGORY_COLORS.technical;
  return (
    <div style={{
      padding: '14px 16px', borderRadius: '8px',
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
      display: 'flex', flexDirection: 'column', gap: '8px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: '#e2e8f0', flex: 1 }}>
          {concept.title}
        </span>
        <span style={{
          fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
          padding: '2px 6px', borderRadius: '4px',
          background: colors.bg, color: colors.text, border: `1px solid ${colors.border}`,
        }}>
          <Tag size={9} style={{ display: 'inline', verticalAlign: '-1px', marginRight: '3px' }} />
          {concept.category}
        </span>
        {concept.status === 'seed' && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', color: '#fbbf24' }}>
            <Sparkles size={10} /> seed
          </span>
        )}
        {concept.status === 'active' && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', color: '#34d399' }}>
            <CheckCircle2 size={10} /> active
          </span>
        )}
        {concept.stale && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '10px', color: '#f87171' }}>
            <AlertTriangle size={10} /> stale
            {onMarkFresh && (
              <button
                onClick={() => onMarkFresh(concept.id)}
                style={{ fontSize: '10px', padding: '0 4px', borderRadius: '3px', border: '1px solid rgba(248,113,113,0.3)', background: 'rgba(248,113,113,0.08)', color: '#f87171', cursor: 'pointer', marginLeft: '2px' }}
              >
                dismiss
              </button>
            )}
          </span>
        )}
        {concept.confidence != null && concept.confidence < 1.0 && (
          <span style={{ fontSize: '10px', color: '#64748b' }}>
            {Math.round(concept.confidence * 100)}% conf
          </span>
        )}
      </div>

      {/* Content */}
      <p style={{ margin: 0, fontSize: '13px', color: '#cbd5e1', lineHeight: '1.6' }}>
        {concept.content}
      </p>

      {/* Anchors */}
      {concept.anchors && concept.anchors.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {concept.anchors.map((a) => (
            <span key={a} style={{
              fontSize: '10px', color: '#64748b',
              background: 'rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: '3px',
              fontFamily: 'monospace',
            }}>
              {a}
            </span>
          ))}
        </div>
      )}

      {/* Tags */}
      {concept.tags && concept.tags.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {concept.tags.map((t) => (
            <span key={t} style={{
              fontSize: '10px', color: '#94a3b8',
              background: 'rgba(255,255,255,0.03)', padding: '1px 5px', borderRadius: '3px',
            }}>
              #{t}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '6px', marginTop: '2px' }}>
        {concept.status === 'seed' && (
          <>
            <button onClick={() => onApprove(concept.id)} style={actionBtnStyle('#34d399')}>
              <CheckCircle2 size={11} /> Approve
            </button>
            <button onClick={() => onArchive(concept.id)} style={actionBtnStyle('#64748b')}>
              Dismiss
            </button>
          </>
        )}
        {concept.status === 'active' && (
          <button onClick={() => onArchive(concept.id)} style={actionBtnStyle('#64748b')}>
            Archive
          </button>
        )}
        <button onClick={() => onDelete(concept.id)} style={{ ...actionBtnStyle('#64748b'), marginLeft: 'auto', opacity: 0.5 }} title="Delete">
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
}

function actionBtnStyle(color: string): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: '4px',
    fontSize: '11px', padding: '3px 10px', borderRadius: '4px',
    border: `1px solid ${color}33`, background: `${color}15`,
    color, cursor: 'pointer',
  };
}

function DetailQuestionRow({ question, onAnswer }: {
  question: ConceptQuestionItem;
  onAnswer: (questionId: string, answer: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [answerText, setAnswerText] = useState('');

  return (
    <div style={{
      padding: '12px 16px', borderRadius: '8px',
      background: 'rgba(167, 139, 250, 0.04)',
      border: '1px solid rgba(167, 139, 250, 0.12)',
      display: 'flex', flexDirection: 'column', gap: '8px',
    }}>
      <div
        style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <MessageCircleQuestion size={16} style={{ color: '#a78bfa', marginTop: '2px', flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#e2e8f0' }}>
            {question.question}
          </span>
          {question.context && (
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b', lineHeight: '1.5' }}>
              {question.context}
            </p>
          )}
          {question.target_module && (
            <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'monospace', marginTop: '2px', display: 'inline-block' }}>
              Module: {question.target_module}
            </span>
          )}
        </div>
        <CategoryBadge category={question.suggested_category} />
      </div>
      {expanded && (
        <div style={{ display: 'flex', gap: '8px', paddingLeft: '26px' }}>
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
              flex: 1, fontSize: '13px', padding: '6px 10px', borderRadius: '6px',
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
              padding: '6px 12px', borderRadius: '6px', border: 'none',
              background: answerText.trim() ? 'rgba(167, 139, 250, 0.2)' : 'transparent',
              color: answerText.trim() ? '#a78bfa' : '#64748b',
              cursor: answerText.trim() ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px',
            }}
          >
            <Send size={13} /> Answer
          </button>
        </div>
      )}
    </div>
  );
}

// ── Coverage Section ────────────────────────────────────────────

function CoverageSection({ stats }: { stats: ConceptStats }) {
  const pct = stats.coverage_pct ?? 0;
  const total = stats.total_modules ?? 0;
  const covered = stats.covered_modules ?? 0;
  const uncovered = total - covered;
  if (total === 0) return null;

  return (
    <div style={{
      padding: '16px', borderRadius: '8px',
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0' }}>
          Module Coverage
        </span>
        <span style={{ fontSize: '13px', fontWeight: 700, color: pct >= 80 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171' }}>
          {pct}%
        </span>
      </div>
      <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden', marginBottom: '8px' }}>
        <div style={{
          height: '100%', borderRadius: '3px',
          width: `${Math.min(pct, 100)}%`,
          background: pct >= 80 ? '#34d399' : pct >= 50 ? '#fbbf24' : '#f87171',
          transition: 'width 0.3s ease',
        }} />
      </div>
      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
        {covered} of {total} modules have concept coverage
        {uncovered > 0 && <> — <strong style={{ color: '#e2e8f0' }}>{uncovered}</strong> uncovered</>}
      </span>
    </div>
  );
}

// ── Main Detail Component ───────────────────────────────────────

export function ConceptsDetail({
  concepts, questions, stats, loading,
  onApprove, onArchive, onDelete, onMarkFresh, onAnswerQuestion, onRefresh,
}: ConceptsDetailProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  // Derive category list from concepts
  const categories = useMemo(() => {
    const cats = new Map<string, number>();
    for (const c of concepts) {
      cats.set(c.category, (cats.get(c.category) ?? 0) + 1);
    }
    return Array.from(cats.entries()).sort((a, b) => b[1] - a[1]);
  }, [concepts]);

  // Filter concepts
  const filtered = useMemo(() => {
    let list = concepts;
    if (statusFilter !== 'all') {
      list = list.filter((c) => c.status === statusFilter);
    }
    if (categoryFilter) {
      list = list.filter((c) => c.category === categoryFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((c) =>
        c.title.toLowerCase().includes(q) ||
        c.content.toLowerCase().includes(q) ||
        c.tags?.some((t) => t.toLowerCase().includes(q))
      );
    }
    return list;
  }, [concepts, statusFilter, categoryFilter, searchQuery]);

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', width: '100%', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Brain size={24} style={{ color: '#a78bfa' }} />
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#e2e8f0' }}>
            Codebase Concepts
          </h2>
          <p style={{ margin: '2px 0 0', fontSize: '13px', color: '#94a3b8' }}>
            {stats ? `${stats.active} active · ${stats.seeds} seeds · ${stats.stale} stale` : 'Loading...'}
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 14px', borderRadius: '6px',
              border: '1px solid rgba(255,255,255,0.1)', background: 'transparent',
              color: '#94a3b8', fontSize: '12px', cursor: loading ? 'default' : 'pointer',
            }}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        )}
      </div>

      {/* Coverage */}
      {stats && <CoverageSection stats={stats} />}

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: '200px',
          padding: '5px 10px', borderRadius: '6px',
          border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)',
        }}>
          <Search size={14} style={{ color: '#64748b' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search concepts..."
            style={{
              flex: 1, fontSize: '13px', background: 'transparent', border: 'none',
              color: '#e2e8f0', outline: 'none',
            }}
          />
        </div>
        <StatusFilter value={statusFilter} onChange={setStatusFilter} />
      </div>

      {/* Category pills */}
      {categories.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <Filter size={13} style={{ color: '#64748b' }} />
          {categories.map(([cat]) => (
            <CategoryBadge
              key={cat}
              category={cat}
              active={categoryFilter === cat}
              onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
            />
          ))}
          {categoryFilter && (
            <button
              onClick={() => setCategoryFilter(null)}
              style={{ fontSize: '11px', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
            >
              clear
            </button>
          )}
        </div>
      )}

      {/* Concept list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {filtered.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
            {concepts.length === 0 ? 'No concepts yet.' : 'No concepts match your filters.'}
          </div>
        ) : (
          <>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 500 }}>
              {filtered.length} concept{filtered.length !== 1 ? 's' : ''}
              {filtered.length !== concepts.length && ` of ${concepts.length}`}
            </div>
            {filtered.map((c) => (
              <DetailConceptCard
                key={c.id}
                concept={c}
                onApprove={onApprove}
                onArchive={onArchive}
                onDelete={onDelete}
                onMarkFresh={onMarkFresh}
              />
            ))}
          </>
        )}
      </div>

      {/* Questions section */}
      {questions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '14px', fontWeight: 600, color: '#a78bfa',
          }}>
            <MessageCircleQuestion size={16} />
            Clarifying Questions ({questions.length})
          </div>
          <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
            These questions target areas where conceptual understanding is missing. Answer them to create new concepts.
          </p>
          {questions.map((q) => (
            <DetailQuestionRow key={q.id} question={q} onAnswer={onAnswerQuestion} />
          ))}
        </div>
      )}
    </div>
  );
}
