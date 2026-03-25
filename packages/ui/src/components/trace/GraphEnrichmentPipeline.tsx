import { useState, useEffect, useRef } from 'react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { ConfirmDialog } from '../primitives/ConfirmDialog';
import { SlidingSwitch2, SlidingSwitch3 } from '../primitives/SlidingSwitch';
import {
  GitBranch, Brain, ShieldCheck, Play, AlertTriangle, CheckCircle2,
  Circle, Clock, Loader2, Layers, Network, Database, Trash2, Code2, Map, Eye, Pause
} from 'lucide-react';
import type { AugmentationStatus, DeepAnalysisRunStatus, EpistemicStatus, ModuleStatus, DeepeningStatus, KnowledgeEmbeddingStatus, InferredEdgesStatus, AtlasStatus, StageProvenance } from '../../types';

// ── Types ────────────────────────────────────────────────────

export interface TraceStageInfo {
  enabled: boolean;
  exists: boolean;
  building: boolean;
  counts: { nodes: number; edges: number };
  last_build_at: string | null;
}

export type EnrichmentStageId = 'structural' | 'inferred_edges' | 'catalogue' | 'validation' | 'knowledge' | 'enrichment' | 'group_reasoning' | 'clustering' | 'atlas' | 'deepening' | 'deep_knowledge';

export type DeepEnrichmentMode = 'manual' | 'auto' | 'scheduled' | 'threshold';

/** Two-group auto/manual config */
export interface EnrichmentAutoConfig {
  /** Auto-run for fast stages (Structural, Catalogue, Validation, Knowledge Embedding) */
  fastSync: boolean;
  /** Mode for deep stages (Epistemic, Clustering, Deepening, Deep Knowledge Embedding) */
  deepEnrichment: DeepEnrichmentMode;
}

export interface GraphEnrichmentPipelineProps {
  trace: TraceStageInfo;
  inferredEdges?: InferredEdgesStatus;
  augmentation?: AugmentationStatus;
  deepAnalysis?: DeepAnalysisRunStatus;
  epistemic?: EpistemicStatus;
  modules?: ModuleStatus;
  deepening?: DeepeningStatus;
  knowledge?: KnowledgeEmbeddingStatus;
  atlas?: AtlasStatus;
  smallModelConfigured?: boolean;
  largeModelConfigured?: boolean;
  codeModelConfigured?: boolean;
  onBuildTrace?: () => void;
  onRunAugmentation?: () => void;
  onRunDeepAnalysis?: () => void;
  onRunEpistemic?: () => void;
  onRunModuleSynthesis?: () => void;
  onRunDeepening?: () => void;
  onRunKnowledgeBuild?: () => void;
  /** Run the entire Fast Sync set (manual trigger) */
  onRunFastSync?: () => void;
  /** Run the entire Deep Enrichment set (manual trigger) */
  onRunDeepEnrichment?: () => void;
  onDestroyGraph?: () => void;
  /** Group reasoning status (Stage 6b) */
  groupReasoning?: { enabled: boolean; group_count: number; analyzed: number; running?: boolean; slot_phase?: string; progress_current?: number; progress_total?: number };
  /** Open the settings drawer to the Deep Enrichment configuration */
  onOpenDeepSettings?: () => void;
  onTogglePause?: () => void;
  /** Pause the currently running pipeline group (flush partial results + stop) */
  onPausePipeline?: (group: 'fast_sync' | 'deep_enrichment') => void;
  /** Resume a paused pipeline group */
  onResumePipeline?: (group: 'fast_sync' | 'deep_enrichment') => void;
  /** @deprecated Use fastPaused/deepPaused instead */
  isPaused?: boolean;
  /** True if the fast sync group is paused */
  fastPaused?: boolean;
  /** True if the deep enrichment group is paused */
  deepPaused?: boolean;
  augmenting?: boolean;
  validating?: boolean;
  deepAnalyzing?: boolean;
  inferredEdgesRunning?: boolean;
  epistemicRunning?: boolean;
  clusterRunning?: boolean;
  atlasRunning?: boolean;
  deepeningRunning?: boolean;
  groupReasoningRunning?: boolean;
  fastKnowledgeBuilding?: boolean;
  deepKnowledgeBuilding?: boolean;
  paused?: boolean;
  /** Two-group auto config */
  autoConfig?: EnrichmentAutoConfig;
  /** Called when auto config changes */
  onAutoConfigChange?: (config: EnrichmentAutoConfig) => void;
  /** Whether the user has a pro/paid plan (controls toggle availability) */
  isPro?: boolean;
  /** Whether the user is over their project limit */
  limitReached?: boolean;
  /** When true, the project is explicitly marked inactive */
  inactive?: boolean;
  /** Stale file counts for rerun visualization */
  staleCounts?: { total: number; stale: number };
  /** Phase 49: per-stage provenance data keyed by output filename or stage_id */
  provenance?: Record<string, StageProvenance>;
  className?: string;
}

type StageState = 'disabled' | 'waiting' | 'queued' | 'running' | 'rerunning' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';

interface EnrichmentStage {
  id: EnrichmentStageId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  modelTag?: string;
  state: StageState;
  stats?: string;
  progress?: number;
  duration?: string;
  /** For rerunning state: ratio of done vs stale files (0-100 each) */
  rerun?: { donePercent: number; stalePercent: number };
  /** Phase 49: provenance metadata for this stage */
  provenance?: StageProvenance;
}

// ── Phase 49: Provenance Helpers ─────────────────────────────────

const STAGE_OUTPUT_KEY: Record<EnrichmentStageId, string | null> = {
  structural: 'trace_nodes.jsonl',
  inferred_edges: 'trace_inferred_edges.jsonl',
  catalogue: 'trace_augmented.jsonl',
  validation: null,
  knowledge: null,
  enrichment: 'trace_epistemic.jsonl',
  group_reasoning: 'trace_group_reasoning.jsonl',
  clustering: 'trace_modules.jsonl',
  atlas: null,
  deepening: 'trace_epistemic.jsonl',
  deep_knowledge: null,
};

function lookupProvenance(
  stageId: EnrichmentStageId,
  data?: Record<string, StageProvenance>,
): StageProvenance | undefined {
  if (!data) return undefined;
  // Primary: API keys by stage_id (e.g. "catalogue", "enrichment")
  if (data[stageId]) return data[stageId];
  // Fallback: try output file key (backward compat with older API responses)
  const fileKey = STAGE_OUTPUT_KEY[stageId];
  if (fileKey && data[fileKey]) return data[fileKey];
  // Last resort: match by stage_id field inside any entry
  for (const v of Object.values(data)) {
    if (v.stage_id === stageId) return v;
  }
  return undefined;
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const days = (now - d.getTime()) / 86400000;
  if (days < 1) return 'today';
  if (days < 2) return 'yesterday';
  if (days < 7) return `${Math.round(days)}d ago`;
  if (days < 30) return `${Math.round(days / 7)}w ago`;
  if (days < 365) return `${Math.round(days / 30)}mo ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const EMBEDDING_STAGES: Set<EnrichmentStageId> = new Set(['knowledge', 'deep_knowledge']);
const RUST_STAGES: Set<EnrichmentStageId> = new Set(['structural', 'validation']);

function formatProvenanceLine(p: StageProvenance): string {
  const parts: string[] = [];
  if (p.model_breakdown && p.model_breakdown.length > 0) {
    // Filter out synthetic entries (path-derived summaries for empty/binary files)
    const realModels = p.model_breakdown.filter(m => !m.model.startsWith('synthetic:'));
    const syntheticCount = p.model_breakdown
      .filter(m => m.model.startsWith('synthetic:'))
      .reduce((sum, m) => sum + m.count, 0);

    if (realModels.length >= 2) {
      // Multi-model: show split (e.g. "qwen3:14b (60%) + qwen3:8b (40%)")
      const sorted = [...realModels].sort((a, b) => b.count - a.count);
      parts.push(`${sorted[0].model} (${sorted[0].percentage}%) + ${sorted[1].model} (${sorted[1].percentage}%)${sorted.length > 2 ? ` +${sorted.length - 2} more` : ''}`);
    } else if (realModels.length === 1) {
      // Single real model (+ some synthetic) — show just the model name
      parts.push(p.provider ? `${realModels[0].model} via ${p.provider}` : realModels[0].model);
    } else if (p.model) {
      // All synthetic but p.model exists
      parts.push(p.provider ? `${p.model} via ${p.provider}` : p.model);
    }

    if (syntheticCount > 0) {
      parts.push(`${syntheticCount} auto-filled`);
    }
  } else if (p.model) {
    parts.push(p.provider ? `${p.model} via ${p.provider}` : p.model);
  } else {
    // Pick the right label based on stage type
    const sid = p.stage_id as EnrichmentStageId;
    if (EMBEDDING_STAGES.has(sid)) {
      parts.push('embedder');
    } else if (RUST_STAGES.has(sid)) {
      parts.push('rust engine');
    } else {
      parts.push('built-in');
    }
  }
  if (p.elapsed_seconds != null) parts.push(formatDuration(p.elapsed_seconds));
  if (p.generated_at) parts.push(formatRelativeDate(p.generated_at));
  if (p.codrag_version) parts.push(`v${p.codrag_version}`);
  return parts.join(' · ') || 'No run data';
}

function isStaleAge(ageDays?: number): 'none' | 'warn' | 'old' {
  if (!ageDays) return 'none';
  if (ageDays > 90) return 'old';
  if (ageDays > 30) return 'warn';
  return 'none';
}

// ── Stage State Helpers ──────────────────────────────────────
//
// CONTRACT: Each compute*State function determines the visual state
// (icon color + text) for one pipeline stage.
//
// The pipeline is SEQUENTIAL.  If a later stage's SSE running flag is
// true, the earlier stage has definitely finished.  We return 'complete'
// immediately in that case — do NOT gate on API data (node counts, etc.)
// because the status API polls on intervals and may lag behind SSE.
//
// Gating on stale API data (e.g. trace.counts.nodes > 0) causes the
// stage to show blue/running AFTER it has finished, which is worse
// than briefly showing green before stats text updates.
//
// The stats text below each stage handles the brief period where the
// stage is green but counts haven't loaded yet (shows "Completing...").
//
// See docs/Phase48_fix-pipeline/README.md for the full state diagram.

function computeTraceState(
  trace: TraceStageInfo,
  inferredEdgesRunning?: boolean,
  augmenting?: boolean,
  validating?: boolean,
  fastKnowledgeBuilding?: boolean
): StageState {
  if (!trace.enabled) return 'disabled';
  // Pipeline is sequential: if any later fast stage is running,
  // Structural has definitely finished.  Show green immediately.
  if (inferredEdgesRunning || augmenting || validating || fastKnowledgeBuilding) return 'complete';
  if (trace.building) return 'running';
  if (!trace.exists) return 'not_built';
  return 'complete';
}

function computeInferredEdgesState(
  trace: TraceStageInfo,
  ie?: InferredEdgesStatus,
  running?: boolean,
  augmenting?: boolean,
  validating?: boolean,
  fastKnowledgeBuilding?: boolean
): StageState {
  if (!trace.enabled) return 'disabled';
  // Pipeline is sequential: if a later stage is running, Edge Discovery finished.
  if (augmenting || validating || fastKnowledgeBuilding) return 'complete';
  // SSE running flags are always fresh — check before stale API data.
  if (running || ie?.running) return 'running';
  // Cold state: trace.exists may be stale during pipeline but correct when idle.
  if (!trace.exists) return 'disabled';
  if (!ie) return 'not_built';
  // ie.exists is false when 0 edges were discovered — but the stage still ran
  // successfully.  Treat enabled + edge_count===0 as complete (not grey).
  if (!ie.exists && !ie.enabled) return 'not_built';
  return 'complete';
}

function computeAugmentState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  augmenting?: boolean,
  validating?: boolean,
  fastKnowledgeBuilding?: boolean
): StageState {
  if (augmenting) return 'running';
  if (!trace.enabled || !trace.exists) return 'disabled';
  // Pipeline is sequential: if a later stage is running, Catalogue finished.
  if (validating || fastKnowledgeBuilding) return 'complete';
  if (!aug || !aug.enabled) return 'not_built';
  if (aug.augmented_nodes === 0) return 'not_built';
  if (aug.low_confidence_count > aug.augmented_nodes * 0.3) return 'warning';
  if (aug.augmented_nodes < aug.total_nodes * 0.5) return 'stale';
  return 'complete';
}

function computeValidationState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  augmenting?: boolean,
  validating?: boolean,
  fastKnowledgeBuilding?: boolean
): StageState {
  if (!trace.enabled) return 'disabled';

  // A later stage is running → Validation must have finished.
  // Validation is a fast Rust pass-through so data confirmation isn't critical,
  // but guard against stale state anyway.
  if (fastKnowledgeBuilding) {
    return (aug && aug.augmented_nodes > 0) ? 'complete' : 'running';
  }

  if (validating) return 'running';
  if (!trace.exists) return 'disabled';
  // Catalogue must finish before validation can be considered.
  if (augmenting) return 'disabled';

  // Validation runs after catalogue (augmentation).
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';

  // Catalogue must be substantially complete before validation can run.
  // If less than 50% of nodes are augmented, catalogue is still in progress
  // (possibly paused with partial checkpoint data).
  if (aug.total_nodes > 0 && aug.augmented_nodes < aug.total_nodes * 0.5) return 'disabled';

  // Rust validation is a fast pass-through that runs immediately after
  // catalogue in the Fast Sync pipeline.  If catalogue is done (we passed
  // all checks above), validation is effectively complete.
  return 'complete';
}

function computeEpistemicState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  ep?: EpistemicStatus,
  running?: boolean,
  clusterRunning?: boolean,
  atlasRunning?: boolean,
  deepeningRunning?: boolean,
  deepKnowledgeBuilding?: boolean
): StageState {
  if (!trace.enabled) return 'disabled';
  // SSE flags are always fresh — check them before stale status data
  if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
  if (running || ep?.running) return 'running';
  // Cold state checks
  if (!trace.exists) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (!ep || !ep.enabled) return 'not_built';
  if (ep.enriched_nodes === 0) return 'not_built';
  if (ep.avg_confidence < 0.5) return 'warning';
  return 'complete';
}

function computeModuleState(
  ep?: EpistemicStatus,
  mod?: ModuleStatus,
  running?: boolean,
  atlasRunning?: boolean,
  deepeningRunning?: boolean,
  deepKnowledgeBuilding?: boolean
): StageState {
  // SSE flags are always fresh — check them before stale status data
  if (atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
  if (running || mod?.running) return 'running';
  // Cold state checks
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (!mod || !mod.enabled) return 'not_built';
  if (mod.module_count === 0) return 'not_built';
  return 'complete';
}

function computeAtlasState(
  ep?: EpistemicStatus,
  mod?: ModuleStatus,
  atlas?: AtlasStatus,
  running?: boolean,
  deepeningRunning?: boolean,
  deepKnowledgeBuilding?: boolean,
  deep?: DeepeningStatus
): StageState {
  // SSE flags are always fresh — check them before stale status data
  if (deepeningRunning || deepKnowledgeBuilding) return 'complete';
  if (running || atlas?.running) return 'running';
  // Cold state checks
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (!mod || !mod.enabled || mod.module_count === 0) return 'disabled';
  if (!atlas || !atlas.exists) return 'not_built';
  // If deepening has run (stage AFTER atlas), atlas was built in this pipeline run.
  // Deepening updates epistemic data which changes module fingerprints, causing
  // atlas.is_stale() to return true even though atlas was just generated.
  // Treat as complete if a later stage has already produced data.
  if (deep && deep.total_scored > 0) return 'complete';
  if (atlas.stale) return 'stale';
  return 'complete';
}

function computeDeepeningState(
  ep?: EpistemicStatus,
  deep?: DeepeningStatus,
  running?: boolean,
  mod?: ModuleStatus,
  deepKnowledgeBuilding?: boolean
): StageState {
  // SSE flags are always fresh — check them before stale status data
  if (deepKnowledgeBuilding) return 'complete';
  if (running || deep?.running) return 'running';
  // Cold state checks
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (!mod || !mod.enabled || mod.module_count === 0) return 'disabled';
  if (!deep || deep.total_scored === 0) return 'not_built';

  // The deepening loop runs in batches (max 10 iterations × 20 nodes = 200 max per run).
  // For large repos, hitting 90% is impossible in one pass.
  // 50% is a reasonable "complete" state for a single pipeline pass.
  if (deep.settled_ratio >= 0.50) return 'complete';
  if (deep.settled_ratio >= 0.20) return 'stale';
  return 'warning';
}

function computeFastKnowledgeState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  know?: KnowledgeEmbeddingStatus,
  building?: boolean,
  augmenting?: boolean
): StageState {
  if (!trace.enabled || !trace.exists) return 'disabled';
  // Catalogue and validation must finish before knowledge embedding
  if (augmenting) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (building) return 'running';
  // Don't show as running just because know?.running is true — that could be the deep build
  if (!know || !know.enabled) return 'not_built';
  if (know.chunks_embedded === 0) return 'not_built';
  return 'complete';
}

function computeDeepKnowledgeState(
  ep?: EpistemicStatus,
  mod?: ModuleStatus,
  deep?: DeepeningStatus,
  know?: KnowledgeEmbeddingStatus,
  building?: boolean
): StageState {
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (!mod || !mod.enabled || mod.module_count === 0) return 'disabled';
  // Deepening (Stage 7) must have run before Deep Knowledge (Stage 8) can be complete
  if (!deep || deep.total_scored === 0) return 'disabled';
  if (building) return 'running';
  // Use deep_chunks_embedded to distinguish Stage 8 from Stage 4 (Fast Sync)
  const deepChunks = know?.deep_chunks_embedded ?? 0;
  if (!know || deepChunks === 0) return 'not_built';
  return 'complete';
}

// ── Stage Groups ─────────────────────────────────────────────

const DEFAULT_AUTO_CONFIG: EnrichmentAutoConfig = {
  fastSync: true,
  deepEnrichment: 'manual',
};

// ── Components ───────────────────────────────────────────────

const STATE_STYLES: Record<StageState, { bg: string; border: string; text: string; icon: string }> = {
  disabled: { bg: 'bg-surface-raised', border: 'border-border', text: 'text-text-subtle', icon: 'text-text-subtle' },
  not_built: { bg: 'bg-surface-raised', border: 'border-border', text: 'text-text-muted', icon: 'text-text-muted' },
  waiting: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'text-amber-400' },
  queued: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: 'text-purple-400' },
  running: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: 'text-blue-400' },
  rerunning: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: 'text-purple-400' },
  stale: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'text-amber-400' },
  complete: { bg: 'bg-success/10', border: 'border-success/30', text: 'text-success', icon: 'text-success' },
  warning: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', icon: 'text-orange-400' },
  error: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: 'text-red-400' },
  idle: { bg: 'bg-surface-raised', border: 'border-border', text: 'text-text-muted', icon: 'text-text-muted' },
};

function StateIcon({ state }: { state: StageState }) {
  const cls = 'w-3.5 h-3.5';
  switch (state) {
    case 'disabled':
    case 'idle':
    case 'not_built':
      return <Circle className={cls} />;
    case 'waiting':
    case 'stale':
      return <Clock className={cls} />;
    case 'queued':
      return <Clock className={cn(cls, 'animate-pulse')} />;
    case 'running':
    case 'rerunning':
      return <Loader2 className={cn(cls, 'animate-spin')} />;
    case 'warning':
      return <AlertTriangle className={cls} />;
    case 'complete':
      return <CheckCircle2 className={cls} />;
    case 'error':
      return <AlertTriangle className={cls} />;
  }
}

import { StageProgressBar } from './StageProgressBar';

function StageRow({
  stage,
  isPaused,
  onPause,
  onResume,
  showDetails = false,
}: {
  stage: EnrichmentStage;
  isPaused: boolean;
  onPause?: (group: "fast_sync" | "deep_enrichment") => void;
  onResume?: (group: "fast_sync" | "deep_enrichment") => void;
  showDetails?: boolean;
}) {
  const s = STATE_STYLES[stage.state];
  const [hovered, setHovered] = useState(false);
  const isRunning = stage.state === 'running' || stage.state === 'rerunning';
  const isRerunning = stage.state === 'rerunning';

  const group = ['structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge'].includes(stage.id)
    ? 'fast_sync'
    : 'deep_enrichment';

  return (
    <div
      className="flex items-start gap-3 relative py-0.5 px-1 group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Connector Line */}
      <div className="absolute left-[19px] top-7 bottom-[-4px] w-px bg-border group-last:hidden" />

      {/* Icon Bubble */}
      <div className={cn(
        "w-8 h-8 rounded-full border flex items-center justify-center shrink-0 z-10 transition-colors",
        isPaused ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' : s.bg,
        isPaused ? '' : s.border,
        isPaused ? '' : s.text,
      )}>
        <stage.icon className="w-4 h-4" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 py-0.5">
        <div className="flex items-center justify-between mb-0.5">
          <div className="flex items-center gap-2">
            <span className={cn("text-xs font-semibold", isPaused ? 'text-amber-400' : s.text)}>{stage.label}</span>
            {stage.modelTag && (
              <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-surface-raised border border-border">
                {stage.modelTag}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {isRunning && stage.progress !== undefined && (
              <span className="text-[10px] text-blue-400 opacity-80">{stage.progress}%</span>
            )}
            {isPaused && stage.progress !== undefined && (
              <span className="text-[10px] text-amber-400 opacity-80">{stage.progress}%</span>
            )}
            {/* Fixed-size container for spinner/pause/play to prevent layout shift */}
            <div className="w-5 h-5 flex items-center justify-center shrink-0">
              {isPaused && onResume ? (
                <button
                  onClick={(e) => { e.stopPropagation(); onResume(group); }}
                  className="p-0.5 rounded hover:bg-green-500/20 transition-colors"
                  title="Resume pipeline from where it paused"
                >
                  <Play className="w-3.5 h-3.5 text-green-400" />
                </button>
              ) : isRunning && hovered && onPause ? (
                <button
                  onClick={(e) => { e.stopPropagation(); onPause(group); }}
                  className="p-0.5 rounded hover:bg-amber-500/20 transition-colors"
                  title="Pause pipeline (saves progress)"
                >
                  <Pause className="w-3.5 h-3.5 text-amber-400" />
                </button>
              ) : isPaused ? (
                <Pause className="w-3.5 h-3.5 text-amber-400" />
              ) : (
                <StateIcon state={stage.state} />
              )}
            </div>
          </div>
        </div>

        {/* Stats Text OR Active Progress Bar */}
        {isRunning ? (
          <div className="h-[13px] flex items-center w-full pr-8">
            <StageProgressBar
              progress={stage.progress}
              className="h-1.5 mt-0 w-full"
              color={isRerunning ? "bg-purple-500" : "bg-blue-500"}
              rerun={isRerunning && stage.rerun ? stage.rerun : undefined}
            />
          </div>
        ) : isPaused ? (
          <p className="text-[10px] text-amber-400/70 truncate leading-tight">
            Paused {stage.stats ? `· ${stage.stats}` : ''}
          </p>
        ) : stage.state === 'queued' ? (
          <p className="text-[10px] text-purple-400/70 truncate leading-tight">
            Waiting for compute capacity…
          </p>
        ) : (
          stage.stats && (
            <p className="text-[10px] text-text-muted truncate leading-tight">
              {stage.stats}
            </p>
          )
        )}

        {/* Phase 49: Detail line — provenance metadata */}
        {/* Only show for stages that have actually completed (not disabled/waiting/not_built/running) */}
        {showDetails && stage.provenance && (stage.state === 'complete' || stage.state === 'stale' || stage.state === 'warning') && (
          <p className={cn(
            "text-[9px] truncate leading-tight mt-0.5",
            isStaleAge(stage.provenance.age_days) === 'old' ? 'text-red-400/70' :
              isStaleAge(stage.provenance.age_days) === 'warn' ? 'text-amber-400/70' :
                'text-text-subtle'
          )}>
            {formatProvenanceLine(stage.provenance)}
          </p>
        )}
        {showDetails && !stage.provenance && (stage.state === 'complete' || stage.state === 'stale' || stage.state === 'warning') && (
          <p className="text-[9px] text-text-subtle/50 truncate leading-tight mt-0.5">
            No run data
          </p>
        )}
      </div>
    </div>
  );
}

// Deep enrichment mode options for SlidingSwitch3
const DEEP_MODE_OPTIONS: { label: string; value: DeepEnrichmentMode }[] = [
  { label: 'Manual', value: 'manual' },
  { label: 'Auto', value: 'auto' },
  { label: 'Sched', value: 'scheduled' },
];

// ── Main Component ───────────────────────────────────────────

export function GraphEnrichmentPipeline({
  trace,
  inferredEdges,
  augmentation,
  epistemic,
  modules,
  deepening,
  knowledge,
  atlas,
  augmenting = false,
  validating = false,
  inferredEdgesRunning = false,
  epistemicRunning = false,
  clusterRunning = false,
  atlasRunning = false,
  deepeningRunning = false,
  groupReasoningRunning = false,
  fastKnowledgeBuilding = false,
  deepKnowledgeBuilding = false,
  autoConfig,
  onAutoConfigChange,
  isPro = false,
  limitReached = false,
  inactive = false,
  // Per-stage handlers kept in props interface but not used directly;
  // group-level handlers trigger the full set.
  onRunFastSync,
  onRunDeepEnrichment,
  onDestroyGraph,
  groupReasoning,
  onOpenDeepSettings,
  onPausePipeline,
  onResumePipeline,
  isPaused = false,
  fastPaused: fastPausedProp,
  deepPaused: deepPausedProp,
  provenance,
  className,
}: GraphEnrichmentPipelineProps) {
  // Per-group paused flags (fall back to legacy isPaused for backward compat)
  const fastPaused = fastPausedProp ?? isPaused;
  const deepPaused = deepPausedProp ?? isPaused;

  // ── Phase 49: Details toggle (persisted to localStorage) ──────
  const [showDetails, setShowDetails] = useState(() => {
    try { return localStorage.getItem('codrag_pipeline_details') === 'true'; }
    catch { return false; }
  });
  const toggleDetails = () => {
    const next = !showDetails;
    setShowDetails(next);
    try { localStorage.setItem('codrag_pipeline_details', String(next)); } catch { }
  };

  // ── Fade-in when transitioning from hero/building → pipeline ──
  const [fadeIn, setFadeIn] = useState(false);
  const prevExistsRef = useRef(trace.exists);
  useEffect(() => {
    if (trace.exists && !prevExistsRef.current) {
      // Just transitioned from not-exists → exists
      setFadeIn(true);
      const timer = setTimeout(() => setFadeIn(false), 600);
      return () => clearTimeout(timer);
    }
    prevExistsRef.current = trace.exists;
  }, [trace.exists]);

  // ── Resolve auto config ───────────────────────────────────
  const cfg = autoConfig ?? DEFAULT_AUTO_CONFIG;
  // Free users are forced to Manual regardless of stored config
  const fastAuto = isPro ? cfg.fastSync : false;
  const deepMode = isPro ? cfg.deepEnrichment : 'manual' as DeepEnrichmentMode;

  // ── Compute stage states ──────────────────────────────────

  // 1. Structural Graph (Rust)
  const structuralState = computeTraceState(trace, inferredEdgesRunning, augmenting, validating, fastKnowledgeBuilding);
  // structuralStats text matches the state from computeTraceState:
  // - 'running' with counts=0: stage active OR API hasn't refreshed yet
  // - 'running' with counts>0: actively building (shows live counts)
  // - 'complete': API confirmed with real counts (always >0 here)
  const structuralStats = (() => {
    if (structuralState === 'not_built') return 'Not built yet';
    if (structuralState === 'disabled') return 'Disabled';
    if (structuralState === 'running') return trace.counts.nodes > 0
      ? `${trace.counts.nodes.toLocaleString()} nodes · ${trace.counts.edges.toLocaleString()} edges`
      : 'Building...';
    // State is 'complete' — if counts are still 0 but a later stage is running,
    // the API hasn't refreshed yet. Show "Completing..." briefly until it does.
    if (trace.counts.nodes === 0 && (inferredEdgesRunning || augmenting || validating || fastKnowledgeBuilding))
      return 'Completing...';
    return `${trace.counts.nodes.toLocaleString()} nodes · ${trace.counts.edges.toLocaleString()} edges`;
  })();

  // 2. Inferred Edges (Code Model)
  const inferredEdgesState = computeInferredEdgesState(trace, inferredEdges, inferredEdgesRunning, augmenting, validating, fastKnowledgeBuilding);
  const inferredEdgesStats = (() => {
    if (inferredEdgesState === 'running') {
      const sp = inferredEdges?.slot_progress;
      if (sp && sp.total > 0) return `${sp.current}/${sp.total} files · ${sp.message || 'Discovering...'}`;
      return 'Discovering edges...';
    }
    if (inferredEdgesState === 'disabled') return 'Waiting for graph';
    if (inferredEdgesState === 'not_built') return 'Ready to discover';
    if (!inferredEdges) return '';
    return `${inferredEdges.edge_count} edges discovered`;
  })();

  // 3. Fast Catalogue (Fast)
  const catalogueState = computeAugmentState(trace, augmentation, augmenting, validating, fastKnowledgeBuilding);
  const catalogueStats = (() => {
    if (catalogueState === 'running') return 'Augmenting...';
    if (catalogueState === 'disabled') return 'Waiting for graph';
    if (catalogueState === 'not_built') return 'Ready to catalogue';
    if (!augmentation) return '';
    const pct = augmentation.total_nodes > 0
      ? Math.round((augmentation.augmented_nodes / augmentation.total_nodes) * 100)
      : 0;
    const conf = augmentation.avg_confidence > 0
      ? `${Math.round(augmentation.avg_confidence * 100)}% conf`
      : '';
    return `${pct}% coverage · ${conf}`;
  })();
  const catalogueProgress = (catalogueState === 'running' && augmentation && augmentation.total_nodes > 0)
    ? Math.round((augmentation.augmented_nodes / augmentation.total_nodes) * 100)
    : undefined;

  // 3. Relationship Validation (Rust)
  const validationState = computeValidationState(trace, augmentation, augmenting, validating, fastKnowledgeBuilding);
  const validationStats = (() => {
    if (validationState === 'running') return 'Validating...';
    if (validationState === 'disabled') return 'Waiting for catalogue';
    if (validationState === 'not_built') return 'Not validated';
    return '0 issues found'; // Placeholder until Rust validator is fully implemented
  })();

  // 4. Epistemic Enrichment (Thinking)
  const enrichmentState = computeEpistemicState(trace, augmentation, epistemic, epistemicRunning, clusterRunning, atlasRunning, deepeningRunning, deepKnowledgeBuilding);
  const enrichmentStats = (() => {
    if (enrichmentState === 'running') return 'Enriching...';
    if (enrichmentState === 'disabled') return 'Waiting for catalogue';
    if (enrichmentState === 'not_built') return 'Ready to enrich';
    if (!epistemic) return '';
    const conf = epistemic.avg_confidence > 0
      ? `${Math.round(epistemic.avg_confidence * 100)}% conf`
      : '';
    return `${epistemic.enriched_nodes} enriched · ${conf}`;
  })();

  // 5. Cluster Synthesis (Thinking)
  const clusteringState = computeModuleState(epistemic, modules, clusterRunning, atlasRunning, deepeningRunning, deepKnowledgeBuilding);
  const clusteringStats = (() => {
    if (clusteringState === 'running') return 'Synthesizing...';
    if (clusteringState === 'disabled') return 'Waiting for enrichment';
    if (clusteringState === 'not_built') return 'Ready to synthesize';
    if (!modules) return '';
    return `${modules.module_count} modules · ${modules.total_files_clustered} files`;
  })();

  // 6. Atlas Building (Thinking)
  const atlasState = computeAtlasState(epistemic, modules, atlas, atlasRunning, deepeningRunning, deepKnowledgeBuilding, deepening);
  const atlasStats = (() => {
    if (atlasState === 'running') return 'Building atlas...';
    if (atlasState === 'disabled') return 'Waiting for modules';
    if (atlasState === 'not_built') return 'Ready to build';
    if (!atlas) return '';
    const parts: string[] = [];
    if (atlas.module_count) parts.push(`${atlas.module_count} segments`);
    if (atlas.file_count) parts.push(`${atlas.file_count} files`);
    if (atlas.routing) parts.push('routing');
    return parts.join(' · ') || 'Built';
  })();

  // 7. Continuous Deepening
  const deepeningState = computeDeepeningState(epistemic, deepening, deepeningRunning, modules, deepKnowledgeBuilding);
  const deepeningStats = (() => {
    if (deepeningState === 'running') {
      const iter = deepening?.iteration ?? 0;
      const max = deepening?.max_iterations ?? '?';
      return `Iteration ${iter}/${max}`;
    }
    if (deepeningState === 'disabled') {
      if (epistemic && epistemic.enabled && epistemic.enriched_nodes > 0) return 'Waiting for clusters';
      return 'Waiting for enrichment';
    }
    if (deepeningState === 'not_built') return 'Not started';
    if (!deepening) return '';
    const pct = Math.round(deepening.settled_ratio * 100);
    return `${pct}% settled · avg ${Math.round(deepening.avg_score * 100)}%`;
  })();
  const deepeningProgress = (deepeningState === 'running' && deepening?.max_iterations && deepening.max_iterations > 0)
    ? Math.round(((deepening.iteration ?? 0) / deepening.max_iterations) * 100)
    : undefined;

  // 4. Knowledge Embedding (fast — after catalogue)
  const fastKnowledgeState = computeFastKnowledgeState(trace, augmentation, knowledge, fastKnowledgeBuilding, augmenting);
  const fastKnowledgeStats = (() => {
    if (fastKnowledgeState === 'running') return 'Embedding...';
    if (fastKnowledgeState === 'disabled') return 'Waiting for catalogue';
    if (fastKnowledgeState === 'not_built') return 'Ready to embed';
    if (!knowledge) return '';
    return `${knowledge.chunks_embedded} chunks embedded`;
  })();

  // 8. Deep Knowledge Embedding (after deep enrichment + clusters + deepening)
  const deepKnowledgeState = computeDeepKnowledgeState(epistemic, modules, deepening, knowledge, deepKnowledgeBuilding);
  const deepKnowledgeStats = (() => {
    if (deepKnowledgeState === 'running') return 'Re-embedding with deep data...';
    if (deepKnowledgeState === 'disabled') return 'Waiting for enrichment + clusters';
    if (deepKnowledgeState === 'not_built') return 'Ready to re-embed';
    if (!knowledge) return '';
    return `${knowledge.chunks_embedded} chunks embedded`;  // Total includes deep + fast
  })();

  // ── Build stage arrays by group ────────────────────────────

  const fastStages: EnrichmentStage[] = [
    { id: 'structural', label: 'Structural Graph', icon: GitBranch, modelTag: 'Rust', state: structuralState, stats: structuralStats },
    {
      id: 'inferred_edges', label: 'Edge Discovery', icon: Code2, modelTag: 'Code',
      state: inferredEdgesState, stats: inferredEdgesStats,
      progress: inferredEdgesState === 'running' && inferredEdges?.slot_progress?.total
        ? Math.round((inferredEdges.slot_progress.current / inferredEdges.slot_progress.total) * 100)
        : undefined,
    },
    { id: 'catalogue', label: 'Fast Catalogue', icon: Database, modelTag: 'Fast', state: catalogueState, stats: catalogueStats, progress: catalogueProgress },
    { id: 'validation', label: 'Relationship Validation', icon: ShieldCheck, modelTag: 'Rust', state: validationState, stats: validationStats },
    {
      id: 'knowledge', label: 'Knowledge Embedding', icon: Database,
      state: fastKnowledgeState, stats: fastKnowledgeStats,
      progress: fastKnowledgeState === 'running'
        ? (knowledge?.progress_total ? Math.round((knowledge.progress_current ?? 0) / knowledge.progress_total * 100) : 0)
        : undefined,
    },
  ];

  const deepStages: EnrichmentStage[] = [
    {
      id: 'enrichment', label: 'Deep Reasoning', icon: Brain, modelTag: 'Thinking',
      state: enrichmentState, stats: enrichmentStats,
      progress: (epistemicRunning || epistemic?.running) && epistemic?.progress_total
        ? Math.round((epistemic.progress_current ?? 0) / epistemic.progress_total * 100)
        : (enrichmentState === 'running' ? 0 : undefined),
    },
    {
      id: 'group_reasoning', label: 'Group Reasoning', icon: Network, modelTag: 'Thinking',
      state: (() => {
        if (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running) return 'running' as StageState;
        if (!epistemic?.enabled || !epistemic?.enriched_nodes) return 'disabled' as StageState;
        // If a later stage is running or already complete, group_reasoning must have finished
        if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete' as StageState;
        if (clusteringState === 'complete' || atlasState === 'complete' || deepeningState === 'complete' || deepeningState === 'stale') return 'complete' as StageState;
        if (groupReasoning?.enabled && groupReasoning?.group_count > 0) return 'complete' as StageState;
        return 'not_built' as StageState;
      })(),
      stats: (() => {
        if (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running) return 'Analyzing groups...';
        if (!epistemic?.enabled || !epistemic?.enriched_nodes) return 'Waiting for enrichment';
        if (groupReasoning?.enabled && groupReasoning?.group_count > 0) return `${groupReasoning.group_count} groups analyzed`;
        return 'Analyzed';
      })(),
      progress: (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running) && groupReasoning?.progress_total
        ? Math.round((groupReasoning.progress_current ?? 0) / groupReasoning.progress_total * 100)
        : undefined,
    },
    {
      id: 'clustering', label: 'Module Synthesis', icon: Layers, modelTag: 'Thinking',
      state: clusteringState, stats: clusteringStats,
      progress: (clusterRunning || modules?.running) && modules?.progress_total
        ? Math.round((modules.progress_current ?? 0) / modules.progress_total * 100)
        : (clusteringState === 'running' ? 0 : undefined),
    },
    { id: 'atlas', label: 'Atlas Building', icon: Map, modelTag: 'Thinking', state: atlasState, stats: atlasStats },
    { id: 'deepening', label: 'Continuous Deepening', icon: Network, state: deepeningState, stats: deepeningStats, progress: deepeningState === 'running' ? (deepeningProgress ?? 0) : undefined },
    {
      id: 'deep_knowledge', label: 'Deep Knowledge Embedding', icon: Database,
      state: deepKnowledgeState, stats: deepKnowledgeStats,
      progress: deepKnowledgeState === 'running'
        ? (knowledge?.progress_total ? Math.round((knowledge.progress_current ?? 0) / knowledge.progress_total * 100) : 0)
        : undefined,
    },
  ];

  // ── Phase 49: inject provenance into each stage ─────────
  for (const stage of [...fastStages, ...deepStages]) {
    stage.provenance = lookupProvenance(stage.id, provenance);
  }

  // ── Group running state ──────────────────────────────────
  const fastRunning = fastStages.some(s => s.state === 'running');
  const deepRunning = deepStages.some(s => s.state === 'running');

  // ── Toggle helpers ─────────────────────────────────────────

  const setFastSync = (v: boolean) => {
    onAutoConfigChange?.({ ...cfg, fastSync: v });
  };

  const setDeepMode = (v: DeepEnrichmentMode) => {
    onAutoConfigChange?.({ ...cfg, deepEnrichment: v });
  };

  // ── Progress ───────────────────────────────────────────────

  const allStates = [...fastStages, ...deepStages].map(s => s.state);
  const completedStages = allStates.filter(s => s === 'complete').length;
  const overallProgress = completedStages / allStates.length * 100;
  const roundedProgress = Math.round(overallProgress);
  const anyStageRunning = allStates.some(s => s === 'running');

  // ── Hero state: trace not yet built ──────────────────────────
  const traceNotBuilt = !trace.exists && !trace.building;

  if (traceNotBuilt) {
    return (
      <div className={cn("flex flex-col items-center justify-center gap-4 py-8 px-4 text-center", className)}>
        <div className="w-14 h-14 rounded-full border-2 border-primary/30 bg-primary/10 flex items-center justify-center">
          <GitBranch className="w-7 h-7 text-primary" />
        </div>
        <div className="space-y-1.5">
          <h3 className="text-sm font-semibold text-text">Initialize Trace Graph</h3>
          <p className="text-xs text-text-muted max-w-[260px] leading-relaxed">
            Build a structural graph of your codebase to enable enrichment, search, and AI-powered analysis.
          </p>
        </div>
        {onRunFastSync ? (
          <button
            onClick={inactive ? undefined : onRunFastSync}
            disabled={inactive || limitReached}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-5 py-2 text-sm font-semibold transition-colors",
              (inactive || limitReached)
                ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                : "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20"
            )}
            title={inactive ? "Activate this project to run pipelines" : undefined}
          >
            <Play className="w-4 h-4" />
            Build Trace Graph
          </button>
        ) : (
          <p className="text-[10px] text-text-subtle">No project selected</p>
        )}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-3", fadeIn && "animate-in fade-in duration-500", className)}>

      {/* ── Fast Sync Group ─────────────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Fast Sync</span>
          {fastAuto && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-success-muted/10 text-success border border-success-muted/20">
              <Eye className="w-2.5 h-2.5" />
              Watching
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {fastPaused && onResumePipeline && !fastRunning && (
            <button
              onClick={() => onResumePipeline('fast_sync')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {!fastAuto && onRunFastSync && !fastPaused && (
            <button
              onClick={inactive ? undefined : onRunFastSync}
              disabled={fastRunning || limitReached || inactive}
              title={
                inactive ? "Activate this project to run pipelines." :
                  limitReached ? "Project limit reached. Upgrade to resume syncing." : undefined
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (fastRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {fastRunning ? 'Running…' : 'Run'}
            </button>
          )}
          <SlidingSwitch2
            value={fastAuto}
            onChange={onAutoConfigChange ? setFastSync : undefined}
            disabled={!isPro || inactive}
            disabledReason={inactive ? "Project is inactive" : "Upgrade to Pro to enable auto-sync"}
          />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 ml-1">
        {fastStages.map((stage, idx) => {
          // When paused, only the first non-complete stage is the paused one
          const isStagePaused = !!(fastPaused && !fastRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
            fastStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
          return (
            <StageRow
              key={stage.id}
              stage={stage}
              isPaused={isStagePaused}
              onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
              onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('fast_sync') : undefined}
              showDetails={showDetails}
            />
          );
        })}
      </div>

      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Deep Enrichment Group ───────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Deep Enrichment</span>
        <div className="flex items-center gap-2">
          {deepPaused && onResumePipeline && !deepRunning && (
            <button
              onClick={() => onResumePipeline('deep_enrichment')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {deepMode === 'manual' && onRunDeepEnrichment && !(deepPaused && !deepRunning) && (
            <button
              onClick={inactive ? undefined : onRunDeepEnrichment}
              disabled={deepRunning || limitReached || inactive}
              title={
                inactive ? "Activate this project to run pipelines." :
                  limitReached ? "Project limit reached. Upgrade to resume syncing." : undefined
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (deepRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {deepRunning ? 'Running…' : deepPaused ? 'Paused' : 'Run'}
            </button>
          )}
          {onOpenDeepSettings && deepMode === 'scheduled' && (
            <button
              onClick={onOpenDeepSettings}
              className="p-1 rounded hover:bg-surface-raised transition-colors text-text-subtle hover:text-text"
              title="Deep Enrichment settings"
            >
              <Clock className="w-3.5 h-3.5" />
            </button>
          )}
          <SlidingSwitch3
            value={deepMode}
            options={DEEP_MODE_OPTIONS}
            onChange={onAutoConfigChange ? setDeepMode : undefined}
            disabled={!isPro || inactive}
            disabledReason={inactive ? "Project is inactive" : "Upgrade to Pro to enable deep enrichment"}
          />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 ml-1">
        {deepStages.map((stage, idx) => {
          // When paused, the paused stage is the first non-complete stage after completed ones
          const isStagePaused = !!(deepPaused && !deepRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
            deepStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
          return (
            <StageRow
              key={stage.id}
              stage={stage}
              onPause={onPausePipeline ? () => onPausePipeline('deep_enrichment') : undefined}
              onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('deep_enrichment') : undefined}
              isPaused={isStagePaused}
              showDetails={showDetails}
            />
          );
        })}
      </div>

      {/* Footer / Summary */}
      <div className="pt-3 border-t border-border">
        <div className="flex items-center justify-between text-[10px] text-text-muted">
          <span>Overall Health</span>
          <div className="flex items-center gap-2">
            <span>{roundedProgress}% ({completedStages}/{allStates.length})</span>
            <button
              onClick={toggleDetails}
              className={cn(
                "text-[9px] px-1.5 py-0.5 rounded border transition-colors",
                showDetails
                  ? "bg-primary/10 border-primary/30 text-primary"
                  : "bg-surface-raised border-border text-text-subtle hover:text-text"
              )}
            >
              Details
            </button>
          </div>
        </div>
        <StageProgressBar
          progress={roundedProgress}
          rerun={{ donePercent: 50, stalePercent: 20 }}
        />
      </div>

      {/* Destroy Graph */}
      {onDestroyGraph && structuralState !== 'disabled' && structuralState !== 'not_built' && (
        <DestroyGraphAction
          onConfirm={onDestroyGraph}
          anyRunning={anyStageRunning}
        />
      )}
    </div>
  );
}

// ── Destroy Graph Confirmation ──────────────────────────────

function DestroyGraphAction({ onConfirm, anyRunning }: { onConfirm: () => void; anyRunning: boolean }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="mt-4 pt-3 border-t border-border">
      <Button
        variant="ghost"
        size="sm"
        className="w-full text-text-subtle hover:text-red-400 hover:bg-red-500/10"
        onClick={() => setConfirming(true)}
        disabled={anyRunning}
      >
        <Trash2 className="w-3.5 h-3.5 mr-1.5" />
        Destroy Graph
      </Button>
      <ConfirmDialog
        open={confirming}
        onConfirm={() => { setConfirming(false); onConfirm(); }}
        onCancel={() => setConfirming(false)}
        title="Destroy entire graph?"
        description="This permanently deletes the structural graph, all augmentations, epistemic enrichment, cluster modules, and deepening data. You will need to rebuild from scratch."
        confirmLabel="Yes, destroy"
      />
    </div>
  );
}
