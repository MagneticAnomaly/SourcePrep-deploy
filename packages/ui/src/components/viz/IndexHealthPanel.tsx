import { useMemo } from 'react';
import { cn } from '../../lib/utils';

// ── Data interfaces ──────────────────────────────────────────────

export interface IndexHealthData {
  // Fast Sync (Embedded)
  total_chunks: number;
  total_files: number;
  stale_count: number;
  error_count: number;
  last_build_at: string | null;
  embedding_dim: number;
  trace_nodes: number;
  trace_edges: number;
  coverage_pct: number;
  // Fast Catalogue (part of Fast Sync)
  catalogued_nodes: number;
  catalogued_total: number;
  // Deep Enrichment
  deep?: DeepHealthData | null;
}

export interface DeepHealthData {
  enriched_nodes: number;
  enriched_total: number;
  avg_confidence: number;
  module_count: number;
  files_clustered: number;
  deepening_settled_ratio: number;
  deepening_iteration: number;
  knowledge_chunks: number;
  deep_running: boolean;
  last_deep_at: string | null;
}

export interface IndexHealthPanelProps {
  data: IndexHealthData | null;
  className?: string;
}

// ── Scoring ──────────────────────────────────────────────────────

interface ScoreResult { score: number; label: string; color: string }

function embeddedScore(data: IndexHealthData): ScoreResult {
  if (data.total_chunks === 0 && data.trace_nodes === 0 && data.catalogued_total === 0)
    return { score: 0, label: 'No Index', color: 'text-gray-400' };

  // Trace exists but no chunks and no catalogue → very early
  if (data.trace_nodes > 0 && data.total_chunks === 0 && data.catalogued_nodes === 0)
    return { score: 10, label: 'Trace Only', color: 'text-orange-400' };

  let score = 100;
  // Catalogue completeness (Fast Catalogue stage)
  if (data.catalogued_total > 0) {
    const catPct = data.catalogued_nodes / data.catalogued_total;
    score -= Math.max(0, (1 - catPct) * 25);
  }
  // Embedding completeness: chunks should cover files
  if (data.total_files > 0 && data.total_chunks > 0) {
    const ratio = Math.min(1, data.total_chunks / (data.total_files * 3));
    score -= Math.max(0, (1 - ratio) * 25);
  } else if (data.trace_nodes > 0 && data.total_chunks === 0) {
    score -= 30; // trace built but no embeddings yet
  }
  if (data.total_chunks > 0) {
    const stalePct = (data.stale_count / data.total_chunks) * 100;
    score -= Math.min(20, stalePct * 2);
  }
  score -= Math.min(15, data.error_count * 10);
  return classify(score);
}

function augmentedScore(deep: DeepHealthData): ScoreResult {
  if (deep.enriched_total === 0 && deep.module_count === 0)
    return { score: 0, label: 'Not Started', color: 'text-gray-400' };

  let score = 100;
  // Epistemic enrichment coverage
  if (deep.enriched_total > 0) {
    const enrPct = (deep.enriched_nodes / deep.enriched_total) * 100;
    score -= Math.max(0, (100 - enrPct) * 0.4);
  }
  // Confidence penalty
  if (deep.avg_confidence < 0.7) score -= 15;
  else if (deep.avg_confidence < 0.85) score -= 5;
  // Deepening convergence
  if (deep.deepening_settled_ratio < 0.5) score -= 10;
  return classify(score);
}

function classify(raw: number): ScoreResult {
  const score = Math.max(0, Math.round(raw));
  if (score >= 80) return { score, label: 'Healthy', color: 'text-green-400' };
  if (score >= 60) return { score, label: 'Fair', color: 'text-yellow-400' };
  if (score >= 40) return { score, label: 'Degraded', color: 'text-orange-400' };
  if (score > 0) return { score, label: 'Critical', color: 'text-red-400' };
  return { score: 0, label: 'Not Started', color: 'text-gray-400' };
}

// ── Component ────────────────────────────────────────────────────

export function IndexHealthPanel({ data, className }: IndexHealthPanelProps) {
  const fastHealth = useMemo(() => data ? embeddedScore(data) : null, [data]);
  const deepHealth = useMemo(() => data?.deep ? augmentedScore(data.deep) : null, [data?.deep]);

  if (!data) {
    return (
      <div className={cn('text-center text-text-muted text-sm', className)}>
        No index data available.
      </div>
    );
  }

  return (
    <div className={cn('h-full overflow-y-auto', className)}>
      {/* Flex container: stacks vertically in portrait, side-by-side in landscape */}
      <div className="flex flex-wrap gap-3">
        {/* ── Fast Sync (Embedded) ────────────────────── */}
        <div className="flex-1 basis-[220px] min-w-0 space-y-2.5">
          <SectionHeader label="Embedded" sublabel="Fast Sync" health={fastHealth} />
          <div className="grid grid-cols-2 gap-1.5">
            <Metric label="Chunks" value={data.total_chunks.toLocaleString()} />
            <Metric label="Files" value={data.total_files.toLocaleString()} />
            <Metric label="Nodes" value={data.trace_nodes.toLocaleString()} />
            <Metric label="Edges" value={data.trace_edges.toLocaleString()} />
            <Metric label="Catalogued"
              value={data.catalogued_total > 0 ? `${data.catalogued_nodes}/${data.catalogued_total}` : '0'}
              accent={data.catalogued_total > 0 && data.catalogued_nodes < data.catalogued_total ? 'yellow' : undefined} />
            <Metric label="Stale" value={data.stale_count.toLocaleString()}
              accent={data.stale_count > 0 ? 'yellow' : undefined} />
          </div>
          <div className="text-[11px] text-text-muted flex items-center gap-2">
            <Freshness ts={data.last_build_at} />
            {data.embedding_dim > 0 && <span>· {data.embedding_dim}-dim</span>}
          </div>
        </div>

        {/* ── Deep Enrichment (Augmented) ─────────────── */}
        <div className="flex-1 basis-[220px] min-w-0 space-y-2.5">
          <SectionHeader label="Augmented" sublabel="Deep Enrichment"
            health={deepHealth} running={data.deep?.deep_running} />

          {data.deep ? (
            <>
              <div className="grid grid-cols-2 gap-1.5">
                <Metric label="Enriched"
                  value={`${data.deep.enriched_nodes}/${data.deep.enriched_total}`}
                  accent={data.deep.enriched_total > 0 && data.deep.enriched_nodes < data.deep.enriched_total ? 'yellow' : undefined} />
                <Metric label="Understanding"
                  value={`${Math.round(data.deep.avg_confidence * 100)}%`}
                  accent={data.deep.avg_confidence < 0.7 ? 'orange' : undefined} />
                <Metric label="Modules" value={data.deep.module_count.toLocaleString()} />
                <Metric label="Converge"
                  value={`${Math.round(data.deep.deepening_settled_ratio * 100)}%`}
                  accent={data.deep.deepening_settled_ratio < 0.5 ? 'orange' : undefined} />
                <Metric label="Knowledge" value={data.deep.knowledge_chunks.toLocaleString()} />
                <Metric label="In Modules" value={data.deep.files_clustered.toLocaleString()} />
              </div>
              <div className="text-[11px] text-text-muted flex items-center gap-2">
                <Freshness ts={data.deep.last_deep_at} />
                {data.deep.deepening_iteration > 0 && <span>· iter {data.deep.deepening_iteration}</span>}
              </div>
            </>
          ) : (
            <div className="text-xs text-text-muted py-1">
              Not started yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Subcomponents ────────────────────────────────────────────────

function SectionHeader({ label, sublabel, health, running }: {
  label: string; sublabel: string; health: ScoreResult | null; running?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <ScoreRing score={health?.score ?? 0} color={health?.color ?? 'text-gray-400'} />
      <div className="min-w-0">
        <div className="flex items-baseline gap-1.5">
          <span className="text-xs font-bold uppercase tracking-wider text-text-muted">{label}</span>
          <span className="text-[10px] text-text-muted/60">{sublabel}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className={cn('text-sm font-semibold leading-tight', health?.color)}>{health?.label ?? 'N/A'}</span>
          {running && <span className="text-[10px] text-accent animate-pulse">Running</span>}
        </div>
      </div>
    </div>
  );
}

function ScoreRing({ score, color }: { score: number; color: string }) {
  return (
    <div className="relative w-11 h-11 flex-shrink-0">
      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
        <circle cx="18" cy="18" r="14" fill="none" stroke="currentColor"
          className="text-surface-raised" strokeWidth="3" />
        <circle cx="18" cy="18" r="14" fill="none"
          className={color}
          strokeWidth="3" strokeLinecap="round"
          strokeDasharray={`${score * 0.88} 88`} />
      </svg>
      <span className={cn('absolute inset-0 flex items-center justify-center text-xs font-bold', color)}>
        {score}
      </span>
    </div>
  );
}

function Freshness({ ts }: { ts: string | null }) {
  if (!ts) return <>Never built</>;
  const mins = Math.round((Date.now() - new Date(ts).getTime()) / 60000);
  if (mins < 1) return <>Just now</>;
  if (mins < 60) return <>{mins}m ago</>;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return <>{hrs}h ago</>;
  return <>{Math.round(hrs / 24)}d ago</>;
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  const accentColor = accent === 'red' ? 'text-red-400'
    : accent === 'yellow' ? 'text-yellow-400'
    : accent === 'orange' ? 'text-orange-400'
    : 'text-text';
  return (
    <div className="bg-surface-raised rounded-lg px-2.5 py-1.5">
      <div className="text-[10px] text-text-muted uppercase tracking-wider leading-tight">{label}</div>
      <div className={cn('text-sm font-semibold leading-tight', accentColor)}>{value}</div>
    </div>
  );
}
