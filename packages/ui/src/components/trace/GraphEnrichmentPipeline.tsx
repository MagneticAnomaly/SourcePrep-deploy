import { useState, useEffect, useRef } from 'react';
import { cn } from '../../lib/utils';
import { SlidingSwitch2, SlidingSwitch3 } from '../primitives/SlidingSwitch';
import {
  GitBranch, Brain, ShieldCheck, Play, AlertTriangle, CheckCircle2,
  Circle, Clock, Loader2, Layers, Network, Database, Code2, Map, Eye, Pause,
  FileText, Lightbulb, ClipboardCheck, Shield, ChevronDown, ChevronRight
} from 'lucide-react';
import { computeGroupRollup, type GroupRollup } from './pipelineRollup';
import { RecoverStagePanel } from './RecoverStagePanel';
import { BarrierIndicator } from './BarrierIndicator';
import { isPipelineRebuilding, computeOverallRebuildPercent, rebuildScope, type RebuildStageSnapshot } from './rebuildProgress';
import { RebuildingRow } from './RebuildingRow';
import { ProvenanceChip } from './ProvenanceChip';
import { HealthBadge } from '../pipeline/HealthBadge';
import type { AugmentationStatus, DeepAnalysisRunStatus, EpistemicStatus, ModuleStatus, DeepeningStatus, KnowledgeEmbeddingStatus, InferredEdgesStatus, AtlasStatus, StageProvenance, RulesStatus, ConceptsStatus, AuditPipelineStatus, AntibodiesStatus, BarrierStatus, PipelineHealth, RebuildScope, StageRebuildProvenance } from '../../types';
import type { ApiClient } from '../../api/client';

// ── Types ────────────────────────────────────────────────────

export interface TraceStageInfo {
  enabled: boolean;
  exists: boolean;
  building: boolean;
  counts: { nodes: number; edges: number };
  last_build_at: string | null;
}

export type EnrichmentStageId =
  | 'structural' | 'inferred_edges' | 'catalogue' | 'validation' | 'knowledge'
  | 'enrichment' | 'group_reasoning' | 'clustering' | 'deepening' | 'deep_knowledge'
  | 'atlas' | 'rules' | 'concepts' | 'audit' | 'antibodies';

export type DeepEnrichmentMode = 'manual' | 'auto' | 'scheduled' | 'threshold';

/** Three-group auto/manual config */
export interface EnrichmentAutoConfig {
  /** Auto-run for fast stages (Structural, Catalogue, Validation, Knowledge Embedding) */
  fastSync: boolean;
  /** Mode for deep stages (Epistemic, Clustering, Deepening, Deep Knowledge Embedding) */
  deepEnrichment: DeepEnrichmentMode;
  /** Mode for finalize stages (Atlas, Rules, Concepts, Audit, Antibodies) */
  finalize: 'manual' | 'auto';
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
  /** Phase 102: separate status payload for stage 10 (Deep Knowledge
   * Embedding). Split out from `knowledge` because the fast-sync
   * knowledge index and the deep knowledge stage are independent
   * runtimes — sharing a single prop caused fast-sync progress to
   * leak into the Deep Knowledge row. */
  deepKnowledge?: KnowledgeEmbeddingStatus;
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
  /** Group reasoning status (Stage 6b) */
  groupReasoning?: { enabled: boolean; group_count: number; analyzed: number; running?: boolean; slot_phase?: string; progress_current?: number; progress_total?: number; progress_baseline?: number };
  /** Open the settings drawer to the Deep Enrichment configuration */
  onOpenDeepSettings?: () => void;
  /** Pause the currently running pipeline group (flush partial results + stop) */
  onPausePipeline?: (group: 'fast_sync' | 'deep_enrichment' | 'finalize') => void;
  /** Resume a paused pipeline group */
  onResumePipeline?: (group: 'fast_sync' | 'deep_enrichment' | 'finalize') => void;
  /** True if the fast sync group is paused */
  fastPaused?: boolean;
  /** True if the deep enrichment group is paused */
  deepPaused?: boolean;
  /** Explicit stage ID where fast sync was paused (from backend) */
  fastPausedStage?: string;
  /** Explicit stage ID where deep enrichment was paused (from backend) */
  deepPausedStage?: string;
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
  /** Two-group auto config */
  autoConfig?: EnrichmentAutoConfig;
  /** Called when auto config changes */
  onAutoConfigChange?: (config: EnrichmentAutoConfig) => void;
  /** Whether the user has a pro/paid plan (used by ProjectList for slot management; automation is unlocked for all tiers) */
  isPro?: boolean;
  /** Whether the user is over their project limit */
  limitReached?: boolean;
  /** When true, the project is explicitly marked inactive */
  inactive?: boolean;
  /** Stale file counts for rerun visualization */
  staleCounts?: { total: number; stale: number };
  /** Phase 49: per-stage provenance data keyed by output filename or stage_id */
  provenance?: Record<string, StageProvenance>;
  // ── Finalize group (Phase 96) ──
  /** Status of rules generation stage */
  rulesStatus?: RulesStatus;
  /** Status of concept seeding stage */
  conceptsStatus?: ConceptsStatus;
  /** Status of audit pipeline stage */
  auditPipelineStatus?: AuditPipelineStatus;
  /** Status of antibody derivation stage */
  antibodiesStatus?: AntibodiesStatus;
  /** Run the Finalize group (manual trigger) */
  onRunFinalize?: () => void;
  /** True if the finalize group is paused */
  finalizePaused?: boolean;
  /** Explicit stage ID where finalize was paused */
  finalizePausedStage?: string;
  /** F-58: whether the finalize group is actively running (from SSE) */
  finalizeGroupRunning?: boolean;
  /** F-58: which finalize stage is currently running (from SSE current_stage) */
  finalizeCurrentStage?: string;
  /** True while the project is switching and initial data hasn't loaded yet */
  projectLoading?: boolean;
  /** Phase 98: per-group collapse state. Defaults to all collapsed when omitted. */
  fastCollapsed?: boolean;
  deepCollapsed?: boolean;
  finalizeCollapsed?: boolean;
  /** Phase 98: per-group collapse toggles. When omitted, the chevron still renders but is a no-op.  */
  onToggleFastCollapsed?: () => void;
  onToggleDeepCollapsed?: () => void;
  onToggleFinalizeCollapsed?: () => void;
  /** Phase 114: project ID for per-stage Recover affordance. When omitted, Recover is hidden. */
  projectId?: string;
  /** Phase 114: API client for Recover panel's listStageBackups/restoreStageFromSnapshot calls. */
  apiClient?: ApiClient;
  /** Phase 114: callback fired after a successful per-stage restore so parent can refresh status. */
  onStageRestored?: (stageId: string, snapshotId: string) => void;
  /** Phase 114: reset barrier banner above the stage groups */
  barrier?: BarrierStatus;
  onClearBarrier?: () => void;
  /** Phase 114: pipeline health snapshot rendered as badge in header */
  health?: PipelineHealth;
  /** Phase 117: trigger a scoped rebuild from ProvenanceChip drift/recovered_stub
   *  affordance. The dashboard rebuild dropdown moved to Settings → Danger Zone
   *  (Phase 117b), so this prop is now reachable only from per-stage drift chips. */
  onRebuild?: (scope: RebuildScope) => void;
  /** Phase 117: stop the currently-running rebuild (from RebuildingRow). */
  onStopRebuild: () => void;
  /** Phase 117: per-stage rebuild provenance keyed by stage_id (from /pipeline/status). */
  rebuildProvenance?: Record<string, StageRebuildProvenance>;
  className?: string;
}

type StageState = 'disabled' | 'waiting' | 'queued' | 'running' | 'rerunning' | 'rebuilding' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';

export interface EnrichmentStage {
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
  /** Phase 117: rebuild provenance (match/drift/recovered/missing) — distinct from Phase 49 provenance */
  rebuildProvenance?: StageRebuildProvenance;
}


// ── Phase 49: Provenance Helpers ─────────────────────────────────

/** Compute rerun bar segments from progress_baseline/total.
 *  Returns undefined when baseline is 0 (initial build). */
function computeRerun(baseline: number | undefined, total: number | undefined): { donePercent: number; stalePercent: number } | undefined {
  if (!baseline || !total || baseline <= 0 || total <= 0) return undefined;
  const donePct = Math.round((baseline / total) * 100);
  const stalePct = 100 - donePct;
  return { donePercent: donePct, stalePercent: stalePct };
}

/** Compute rerun for a stage using slot_progress.baseline if available.
 *  Returns undefined for initial (non-incremental) builds. */
function computeStageRerun(
  slotBaseline: number | undefined,
  slotTotal: number | undefined,
): { donePercent: number; stalePercent: number } | undefined {
  // Prefer per-stage slot baseline (most accurate)
  return computeRerun(slotBaseline, slotTotal);
}

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
  rules: null,
  concepts: null,
  audit: null,
  antibodies: null,
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

const BACKUP_TYPE_LABELS: Record<string, string> = {
  run_checkpoint: 'run checkpoint',
  golden: 'golden snapshot',
  branch_snapshot: 'branch snapshot',
};

function formatProvenanceLine(p: StageProvenance): string {
  const parts: string[] = [];

  // Recovery markers take precedence: when a manifest was reconstructed
  // (selfheal stub or crash-recovery placeholder) there is no real model
  // provenance to display, and the generic "built-in" fallback would
  // misrepresent LLM stages as deterministic.
  if (p.restored) {
    const label = p.backup_type
      ? `restored from ${BACKUP_TYPE_LABELS[p.backup_type] ?? p.backup_type}`
      : 'restored from checkpoint';
    parts.push(label);
    if (p.restored_at) parts.push(formatRelativeDate(p.restored_at));
    if (p.prep_version) parts.push(`v${p.prep_version}`);
    return parts.join(' · ');
  }
  if (p.recovered) {
    parts.push('recovered (inferred)');
    if (p.generated_at) parts.push(formatRelativeDate(p.generated_at));
    if (p.prep_version) parts.push(`v${p.prep_version}`);
    return parts.join(' · ');
  }

  if (p.model_breakdown && p.model_breakdown.length > 0) {
    // Filter out synthetic entries (path-derived summaries for empty/binary files)
    const realModels = p.model_breakdown.filter(m => !m.model.startsWith('synthetic:'));
    const syntheticCount = p.model_breakdown
      .filter(m => m.model.startsWith('synthetic:'))
      .reduce((sum, m) => sum + m.count, 0);

    // Phase 53: If p.model matches a model in the breakdown, prefer showing
    // just p.model. Multi-model breakdowns from incremental runs are misleading
    // because old entries from previous runs inflate the stale model's percentage.
    const latestModelInBreakdown = p.model && realModels.some(m => m.model === p.model);

    if (realModels.length >= 2 && !latestModelInBreakdown) {
      // Multi-model within the same run: show split
      const sorted = [...realModels].sort((a, b) => b.count - a.count);
      parts.push(`${sorted[0].model} (${sorted[0].percentage}%) + ${sorted[1].model} (${sorted[1].percentage}%)${sorted.length > 2 ? ` +${sorted.length - 2} more` : ''}`);
    } else if (p.model) {
      // Latest run model is known — show it as the primary label
      parts.push(p.provider ? `${p.model} via ${p.provider}` : p.model);
    } else if (realModels.length === 1) {
      parts.push(p.provider ? `${realModels[0].model} via ${p.provider}` : realModels[0].model);
    }

    // Show total augmented count from breakdown
    const totalItems = p.model_breakdown.reduce((sum, m) => sum + m.count, 0);
    if (totalItems > 0) parts.push(`${totalItems} aug.`);

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
  if (p.prep_version) parts.push(`v${p.prep_version}`);
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
  fastKnowledgeBuilding?: boolean,
  ie?: InferredEdgesStatus,
  aug?: AugmentationStatus
): StageState {
  // F-42: trace.enabled is the auto-build preference, not the
  // data-presence flag.  Gate on trace.exists so we don't render
  // a fully-built graph as "Disabled" just because auto-rebuild
  // happens to be off.  Same root-cause class as F-39 (which fixed
  // the daemon side; this fixes the dashboard side).
  if (!trace.exists && !trace.enabled) return 'disabled';
  // Pipeline is sequential: if any later fast stage is running,
  // Structural has definitely finished.  Show green immediately.
  // F-86: Also check API-derived signals (ie.running, aug progress
  // mid-stage) for the case where the SSE SYNC_RUNNING dispatch
  // lags behind /pipeline/status polling. Without these, Structural
  // kept its spinning icon for several seconds after Edge Discovery
  // had clearly started, because the SSE-derived flag hadn't flipped.
  if (inferredEdgesRunning || augmenting || validating || fastKnowledgeBuilding) return 'complete';
  if (ie?.running) return 'complete';
  const augInProgress = aug && aug.progress_current != null &&
    aug.progress_total != null && aug.progress_total > 0 &&
    aug.progress_current < aug.progress_total;
  if (augInProgress) return 'complete';
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
  // F-42: see computeTraceState
  if (!trace.exists && !trace.enabled) return 'disabled';
  // F-NEW-3 (Phase 118): honor THIS stage's running flag before any
  // forward-progression heuristic. A stale "later-stage-running" flag
  // from the prior run otherwise traps this stage at 'complete' for the
  // first poll cycles of a new run.
  if (running || ie?.running) return 'running';
  // Pipeline is sequential: if a later stage is running, Edge Discovery finished.
  if (augmenting || validating || fastKnowledgeBuilding) return 'complete';
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
  // F-42: gate on data presence, not the auto-build preference
  if (!trace.exists) return 'disabled';
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
  // F-42: see computeTraceState
  if (!trace.exists && !trace.enabled) return 'disabled';

  // F-NEW-3 (Phase 118): honor THIS stage's running flag before any
  // forward-progression heuristic.
  if (validating) return 'running';

  // A later stage is running → Validation must have finished.
  if (fastKnowledgeBuilding) {
    return (aug && aug.augmented_nodes > 0) ? 'complete' : 'running';
  }
  if (!trace.exists) return 'disabled';

  // "Was previously complete" signal — validated_nodes / last_validate_at
  // are persisted from the previous validation run and survive incremental
  // re-runs. Use them instead of the (mutating) augmented_nodes ratio so
  // that during a catalogue re-run the stage stays green from the prior
  // pass rather than flipping to grey at 0%..99% and back.
  const previouslyValidated = !!(aug && (aug.validated_nodes > 0 || aug.last_validate_at));

  if (augmenting) {
    if (previouslyValidated) return 'complete';
    // Fresh initial build — validation hasn't run yet at any %
    if (
      aug &&
      aug.augmented_nodes > 0 &&
      aug.total_nodes > 0 &&
      aug.augmented_nodes >= aug.total_nodes
    ) {
      return 'complete';
    }
    return 'disabled';
  }

  if (previouslyValidated) return 'complete';

  // Validation runs after catalogue (augmentation).
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';

  // Catalogue must be substantially complete before validation can run.
  if (aug.total_nodes > 0 && aug.augmented_nodes < aug.total_nodes * 0.5) return 'disabled';

  // Rust validation is a fast pass-through that runs immediately after
  // catalogue in the Fast Sync pipeline.
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
  // F-42: see computeTraceState
  if (!trace.exists && !trace.enabled) return 'disabled';
  // F-NEW-3 (Phase 118): the API's per-stage running flag for THIS stage
  // is the freshest signal we have. If `running || ep?.running` is true,
  // we MUST honor that even if a stale "later stage running" SSE flag is
  // still set from a prior run. The previous order let prior-run cluster
  // / atlas / deepening flags trap this stage at 'complete' for the first
  // few seconds of a new run.
  if (running || ep?.running) return 'running';
  // SSE flags as forward-progression hint (only when API doesn't claim this stage is running)
  if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
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
  // F-NEW-3 (Phase 118): see computeEnrichmentState — honor THIS stage's
  // running flag first.
  if (running || mod?.running) return 'running';
  if (atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete';
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
  // F-NEW-3 (Phase 118): see computeEnrichmentState — honor THIS stage's
  // running flag first.
  if (running || atlas?.running) return 'running';
  if (deepeningRunning || deepKnowledgeBuilding) return 'complete';
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
  // F-NEW-3 (Phase 118): see computeEnrichmentState — honor THIS stage's
  // running flag first.
  if (running || deep?.running) return 'running';
  if (deepKnowledgeBuilding) return 'complete';

  // F-76: If deepening itself has historical data (backend sourced this from
  // deepening_manifest.json), show complete regardless of upstream runtime
  // state. Upstream stages' runtime fields can flip to 0 during an
  // incremental re-run, but deepening's own persisted result is authoritative.
  if (deep && deep.total_scored > 0 && (deep.settled_ratio ?? 0) >= 0.50) {
    return 'complete';
  }

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
  // F-42: gate on data presence, not the auto-build preference
  if (!trace.exists) return 'disabled';
  if (building) return 'running';

  // F-76: If the knowledge index itself has embedded chunks (either from the
  // current run or from the manifest fallback), stay green. Upstream aug
  // fields can reset to 0 during a structural re-run but the existing
  // knowledge_embeddings.npy on disk is still valid.
  if (know && know.enabled && know.chunks_embedded > 0) {
    return 'complete';
  }

  // During incremental catalogue run, keep knowledge green if it was
  // previously complete (has embedded chunks already).
  if (augmenting) {
    if (know && know.chunks_embedded > 0) {
      return 'complete';  // Was complete before, stay green during incremental add
    }
    return 'disabled';  // Initial build — knowledge hasn't run yet
  }
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
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
  if (building) return 'running';

  // F-76: If deep_chunks_embedded is non-zero (including the manifest
  // fallback from the backend), stay green even if upstream runtime fields
  // are stale mid-rebuild. The embeddings on disk are still valid.
  //
  // The fast path must only fire when upstream is STABLE (not actively
  // running). During a resumed Deep Reasoning, ep.enriched_nodes climbs
  // from 0 as new records land, but `deep_chunks_embedded` still reflects
  // the prior run's 120 epistemic/module docs sitting in
  // knowledge_documents.json — those are orphaned from the current
  // enrichment state. Without this gate, Deep Knowledge Embedding paints
  // green while Deep Reasoning is still 41% of the way through.
  const deepChunks = know?.deep_chunks_embedded ?? 0;
  const upstreamStable = !!(
    ep && ep.enriched_nodes > 0 && !ep.running
    && !mod?.running
    && !deep?.running
  );
  if (deepChunks > 0 && upstreamStable) return 'complete';

  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (!mod || !mod.enabled || mod.module_count === 0) return 'disabled';
  // Deepening (Stage 7) must have run before Deep Knowledge (Stage 8) can be complete
  if (!deep || deep.total_scored === 0) return 'disabled';
  return 'not_built';
}

// ── Stage Groups ─────────────────────────────────────────────

const DEFAULT_AUTO_CONFIG: EnrichmentAutoConfig = {
  fastSync: true,
  deepEnrichment: 'manual',
  finalize: 'manual',
};

// ── Components ───────────────────────────────────────────────

const STATE_STYLES: Record<StageState, { bg: string; border: string; text: string; icon: string }> = {
  disabled: { bg: 'bg-surface-raised', border: 'border-border', text: 'text-text-subtle', icon: 'text-text-subtle' },
  not_built: { bg: 'bg-surface-raised', border: 'border-border', text: 'text-text-muted', icon: 'text-text-muted' },
  waiting: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'text-amber-400' },
  queued: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: 'text-purple-400' },
  running: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: 'text-blue-400' },
  rerunning: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: 'text-purple-400' },
  rebuilding: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: 'text-blue-400' },
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
    case 'rebuilding':
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

function ChevronButton({ collapsed, onClick }: { collapsed: boolean; onClick?: () => void }) {
  const Icon = collapsed ? ChevronRight : ChevronDown;
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-0.5 rounded hover:bg-surface-raised transition-colors text-text-subtle hover:text-text"
      aria-label={collapsed ? 'Expand group' : 'Collapse group'}
      title={collapsed ? 'Expand group' : 'Collapse group'}
    >
      <Icon className="w-3.5 h-3.5" />
    </button>
  );
}

function CondensedGroupRow({
  rollup,
  isRebuilding = false,
  groupRebuildPercent = 0,
}: {
  rollup: GroupRollup;
  isRebuilding?: boolean;
  groupRebuildPercent?: number;
}) {
  const stateToStyle: Record<GroupRollup['state'], { bg: string; border: string; text: string; icon: React.ComponentType<{ className?: string }> }> = {
    complete:  { bg: 'bg-success/10',  border: 'border-success/30',  text: 'text-success',    icon: CheckCircle2 },
    disabled:  { bg: 'bg-surface',     border: 'border-border',      text: 'text-text-subtle', icon: Circle },
    idle:      { bg: 'bg-surface-raised', border: 'border-border',   text: 'text-text-muted', icon: Clock },
    running:   { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400',   icon: Loader2 },
    error:     { bg: 'bg-red-500/10',  border: 'border-red-500/30',  text: 'text-red-400',    icon: AlertTriangle },
    mixed:     { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: AlertTriangle },
  };
  const s = stateToStyle[rollup.state];
  const IconComponent = s.icon;
  const isRunning = rollup.state === 'running';
  return (
    <div className="flex items-center gap-3 py-0.5 px-1 ml-1">
      <div className={cn('w-8 h-8 rounded-full border flex items-center justify-center shrink-0', s.bg, s.border, s.text)}>
        <IconComponent className={cn('w-4 h-4', isRunning && 'animate-spin')} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn('text-[10px] leading-tight truncate', s.text)}>{rollup.stats}</p>
        {isRebuilding ? (
          <StageProgressBar
            variant="rebuild"
            rebuildPercent={groupRebuildPercent}
            className="h-1.5 mt-1 w-full"
          />
        ) : isRunning && typeof rollup.progress === 'number' ? (
          <StageProgressBar progress={rollup.progress} className="h-1.5 mt-1 w-full" color="bg-blue-500" />
        ) : null}
      </div>
    </div>
  );
}

function StageRow({
  stage,
  isPaused,
  onPause,
  onResume,
  showDetails = false,
  isRebuilding = false,
  onRebuild,
}: {
  stage: EnrichmentStage;
  isPaused: boolean;
  onPause?: (group: "fast_sync" | "deep_enrichment" | "finalize") => void;
  onResume?: (group: "fast_sync" | "deep_enrichment" | "finalize") => void;
  showDetails?: boolean;
  isRebuilding?: boolean;
  onRebuild?: (scope: RebuildScope) => void;
}) {
  const s = STATE_STYLES[stage.state];
  const [hovered, setHovered] = useState(false);
  const isRunning = stage.state === 'running' || stage.state === 'rerunning' || stage.state === 'rebuilding' || (stage.state === 'error' && isRebuilding);
  const isRerunning = stage.state === 'rerunning';

  const group = ['structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge'].includes(stage.id)
    ? 'fast_sync'
    : ['enrichment', 'group_reasoning', 'clustering', 'deepening', 'deep_knowledge'].includes(stage.id)
    ? 'deep_enrichment'
    : 'finalize';

  return (
    <div
      data-testid={`pipeline-stage-row-${stage.id}`}
      data-stage-id={stage.id}
      data-stage-state={isPaused ? 'paused' : stage.state}
      data-stage-progress={stage.progress ?? ''}
      data-stage-group={group}
      data-stage-frozen={(stage as EnrichmentStage & { _frozen?: boolean })._frozen ? 'true' : undefined}
      className={cn(
        "flex items-start gap-3 relative py-0.5 px-1 group",
        // Phase 118 U6: visually distinguish frozen-from-prior-run stages
        // from genuinely-complete-this-run stages during a rebuild. The
        // muted opacity says "this is preserved data, not fresh result."
        (stage as EnrichmentStage & { _frozen?: boolean })._frozen && "opacity-60",
      )}
      title={(stage as EnrichmentStage & { _frozen?: boolean })._frozen
        ? 'Showing data from prior run — will refresh once this stage re-runs'
        : undefined}
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
            {showDetails && stage.modelTag && (
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
          <div className="flex flex-col gap-0.5 w-full pr-8">
            <div className="h-[13px] flex items-center w-full">
              <StageProgressBar
                progress={stage.progress}
                className="h-1.5 mt-0 w-full"
                color={isRerunning ? "bg-purple-500" : "bg-blue-500"}
                rerun={stage.rerun ? stage.rerun : undefined}
                /*
                 * Phase 118 U18: when ANY stage is currently running AND a
                 * rebuild barrier is active, force the rebuild variant
                 * (orange-on-top, green-on-bottom stacked bar). The old
                 * check only fired when the stage's computed state was
                 * exactly 'rebuilding' — but promoteForRebuild only
                 * promotes raw 'running' / 'queued' states. If a stage
                 * legitimately runs with raw state (because the
                 * compute*State function returned 'running' but the
                 * promote pass hadn't run yet, or some compute path
                 * never goes through promote), `variant` was undefined
                 * and StageProgressBar fell back to the incremental
                 * 2-tone horizontal bar — exactly what the user
                 * reported. Now: any active running state during a
                 * rebuild barrier renders the rebuild visual.
                 */
                variant={
                  isRebuilding && isRunning
                    ? 'rebuild'
                    : (stage.state === 'rebuilding' || (stage.state === 'error' && isRebuilding))
                      ? 'rebuild'
                      : undefined
                }
                rebuildPercent={
                  (isRebuilding && isRunning) || stage.state === 'rebuilding'
                    ? stage.progress
                    : undefined
                }
                rebuildStateOverlay={
                  (stage.state === 'rebuilding' || (isRebuilding && isRunning)) && isPaused
                    ? 'paused'
                    : stage.state === 'error' && isRebuilding
                      ? 'failed'
                      : undefined
                }
              />
            </div>
            {stage.stats && (
              <p className="text-[10px] text-blue-400/60 truncate leading-tight">
                {stage.stats}
              </p>
            )}
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
            {/* Phase 118 U14: during a rebuild, frozen-from-prior stages
                show their preserved counts via the `prior:` stat above.
                The "No run data" line was misleading — it implied the
                stage had never run, when in fact it had completed in a
                prior run and the new run hasn't reached it yet. Show
                "rebuilding…" instead so the meaning matches the data. */}
            {(stage as EnrichmentStage & { _frozen?: boolean })._frozen
              ? 'rebuilding…'
              : 'No run data'}
          </p>
        )}

        {/* Phase 117: rebuild provenance chip (drift / recovered_stub / recovered_soft) */}
        {stage.rebuildProvenance && (
          <div className="mt-0.5" data-testid={`provenance-chip-${stage.id}`}>
            <ProvenanceChip provenance={stage.rebuildProvenance} onRebuild={onRebuild} />
          </div>
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
  deepKnowledge,
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
  isPro: _isPro = false,
  limitReached = false,
  inactive = false,
  // Per-stage handlers kept in props interface but not used directly;
  // group-level handlers trigger the full set.
  onRunFastSync,
  onRunDeepEnrichment,
  groupReasoning,
  onOpenDeepSettings,
  onPausePipeline,
  onResumePipeline,
  fastPaused: fastPausedProp,
  deepPaused: deepPausedProp,
  fastPausedStage,
  deepPausedStage,
  rulesStatus,
  conceptsStatus,
  auditPipelineStatus,
  antibodiesStatus,
  onRunFinalize,
  finalizePaused: finalizePausedProp,
  finalizePausedStage,
  finalizeGroupRunning = false,
  finalizeCurrentStage: finalizeCurrentStageId,
  provenance,
  projectLoading,
  fastCollapsed = true,
  deepCollapsed = true,
  finalizeCollapsed = true,
  onToggleFastCollapsed,
  onToggleDeepCollapsed,
  onToggleFinalizeCollapsed,
  projectId,
  apiClient,
  onStageRestored,
  barrier,
  onClearBarrier,
  health,
  onRebuild,
  onStopRebuild,
  rebuildProvenance,
  className,
}: GraphEnrichmentPipelineProps) {
  const fastPaused = fastPausedProp ?? false;
  const deepPaused = deepPausedProp ?? false;
  const finalizePaused = finalizePausedProp ?? false;

  // ── Phase 116: rebuild detection ──────────────────────────
  // When a full /pipeline/rebuild sets barrier.reason === 'rebuild'
  // (+ barrier.active === true), promote every 'running'/'queued'
  // stage state to 'rebuilding' so the progress bar switches to
  // the rebuild variant.
  const isRebuilding = isPipelineRebuilding(barrier);
  const promoteForRebuild = (s: StageState): StageState =>
    isRebuilding && (s === 'running' || s === 'queued') ? 'rebuilding' : s;

  // Freeze pre-rebuild green: remember which stages have reached
  // 'complete' so that when a rebuild wipes their manifests (they
  // revert to not_built/disabled), we keep showing them green until
  // they actually start re-running.
  const wasCompleteRef = useRef<Record<string, boolean>>({});
  // Phase 118 Issue B: also remember the last good stats text for each
  // stage. During a rebuild the underlying status payloads (rulesStatus,
  // conceptsStatus, etc.) report `generated: false` because their manifest
  // was wiped — that flips the inline stat copy to "Not generated / Not
  // seeded / Not run / Not derived" even though the prior run produced
  // those artifacts. Holding the last good stats text and substituting it
  // back during rebuild keeps the panel honest: "this is what the prior
  // run produced; it'll be replaced when the new run finishes that stage."
  const lastGoodStatsRef = useRef<Record<string, string>>({});

  // Phase 118 U3: hold a complete snapshot of finalize status props from
  // the moment the rebuild started. While rebuild is active, substitute
  // the snapshot for any prop whose current API-derived value indicates
  // "wiped" (generated=false, exists=false, count=0). This keeps ALL of
  // the prior-run detail (counts, model labels, finding totals, atlas
  // segment counts) visible until the new run reaches that stage and
  // replaces the data for real.
  const rebuildSnapshotRef = useRef<{
    rulesStatus?: typeof rulesStatus;
    conceptsStatus?: typeof conceptsStatus;
    auditPipelineStatus?: typeof auditPipelineStatus;
    antibodiesStatus?: typeof antibodiesStatus;
    atlas?: typeof atlas;
    modules?: typeof modules;
    deepening?: typeof deepening;
    knowledge?: typeof knowledge;
    deepKnowledge?: typeof deepKnowledge;
    epistemic?: typeof epistemic;
    augmentation?: typeof augmentation;
    inferredEdges?: typeof inferredEdges;
  }>({});
  const wasRebuildingRef = useRef<boolean>(false);

  const prevProjectIdRef = useRef(projectId);
  if (prevProjectIdRef.current !== projectId) {
    wasCompleteRef.current = {};
    lastGoodStatsRef.current = {};
    rebuildSnapshotRef.current = {};
    wasRebuildingRef.current = false;
    prevProjectIdRef.current = projectId;
  }

  // Capture snapshot at the moment a rebuild begins.
  if (isRebuilding && !wasRebuildingRef.current) {
    rebuildSnapshotRef.current = {
      rulesStatus, conceptsStatus, auditPipelineStatus, antibodiesStatus,
      atlas, modules, deepening, knowledge, deepKnowledge,
      epistemic, augmentation, inferredEdges,
    };
  }
  // Clear snapshot once the rebuild ends so future runs read live values.
  if (!isRebuilding && wasRebuildingRef.current) {
    rebuildSnapshotRef.current = {};
  }
  wasRebuildingRef.current = isRebuilding;

  // Helper: pick the live value if it has data, otherwise fall back to
  // the rebuild snapshot. We only fall back for "obviously wiped"
  // signals (the same ones used to trigger "Not generated" copy) so a
  // partial / mid-run state still renders fresh data.
  const rebuildAware = <T,>(live: T | undefined, snap: T | undefined, hasData: (v: T | undefined) => boolean): T | undefined => {
    if (!isRebuilding) return live;
    if (hasData(live)) return live;
    return snap ?? live;
  };
  const effectiveRulesStatus = rebuildAware(rulesStatus, rebuildSnapshotRef.current.rulesStatus, (v) => !!v?.generated);
  const effectiveConceptsStatus = rebuildAware(conceptsStatus, rebuildSnapshotRef.current.conceptsStatus, (v) => !!v?.seeded);
  const effectiveAuditPipelineStatus = rebuildAware(auditPipelineStatus, rebuildSnapshotRef.current.auditPipelineStatus, (v) => !!v?.exists);
  const effectiveAntibodiesStatus = rebuildAware(antibodiesStatus, rebuildSnapshotRef.current.antibodiesStatus, (v) => !!v?.count);
  const effectiveAtlas = rebuildAware(atlas, rebuildSnapshotRef.current.atlas, (v) => !!v?.exists);
  const effectiveModules = rebuildAware(modules, rebuildSnapshotRef.current.modules, (v) => !!v?.module_count);
  // Snapshots for deep stages exist in the ref (captured at rebuild start)
  // but are intentionally NOT substituted into the per-stage compute
  // functions yet — the deep stages already retain their visual state via
  // the freeze-green path because their compute*State functions return
  // 'complete' once chunks_embedded / total_scored / enriched_nodes are
  // non-zero, and freeze-green will re-promote any regressed state. We
  // keep the snapshot ref shape consistent so a later iteration can plug
  // these in if the deep stages start showing the same "Not generated"
  // regression as the finalize ones.

  // ── Phase 49: Details toggle (persisted to localStorage) ──────
  const [showDetails, setShowDetails] = useState(() => {
    try { return localStorage.getItem('prep_pipeline_details') === 'true'; }
    catch { return false; }
  });
  const toggleDetails = () => {
    const next = !showDetails;
    setShowDetails(next);
    try { localStorage.setItem('prep_pipeline_details', String(next)); } catch { /* localStorage unavailable */ }
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
  // All tiers have automation — isPro only affects project slot management
  const fastAuto = cfg.fastSync;
  const deepMode = cfg.deepEnrichment;

  // ── Compute stage states ──────────────────────────────────

  // 1. Structural Graph (Rust)
  const structuralState = computeTraceState(
    trace, inferredEdgesRunning, augmenting, validating, fastKnowledgeBuilding,
    inferredEdges, augmentation,
  );
  // structuralStats text matches the state from computeTraceState:
  // - 'running' with counts=0: stage active OR API hasn't refreshed yet
  // - 'running' with counts>0: actively building (shows live counts)
  // - 'complete': API confirmed with real counts (always >0 here)
  const structuralStats = (() => {
    if (structuralState === 'not_built') return 'Not run';
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
    if (inferredEdgesState === 'not_built') return 'Not run';
    if (!inferredEdges) return '';
    return `${inferredEdges.edge_count} edges discovered`;
  })();

  // 3. Fast Catalogue (Fast)
  const catalogueState = computeAugmentState(trace, augmentation, augmenting, validating, fastKnowledgeBuilding);
  const catalogueStats = (() => {
    if (catalogueState === 'running') {
      // Show file progress so the user knows it's alive at 99%
      const cur = augmentation?.progress_current ?? 0;
      const tot = augmentation?.progress_total ?? 0;
      if (tot > 0) return `${cur.toLocaleString()} / ${tot.toLocaleString()} files`;
      return 'Augmenting...';
    }
    if (catalogueState === 'disabled') return 'Waiting for graph';
    if (catalogueState === 'not_built') return 'Not run';
    if (!augmentation) return '';
    const pct = augmentation.total_nodes > 0
      ? Math.round((augmentation.augmented_nodes / augmentation.total_nodes) * 100)
      : 0;
    const conf = augmentation.avg_confidence > 0
      ? `${Math.round(augmentation.avg_confidence * 100)}% conf`
      : '';
    return `${pct}% coverage · ${conf}`;
  })();
  const catalogueProgress = (() => {
    if (catalogueState !== 'running' || !augmentation) return undefined;
    // Prefer pipeline slot progress (accurate during incremental runs)
    if (augmentation.progress_total && augmentation.progress_total > 0) {
      return Math.min(100, Math.round(((augmentation.progress_current ?? 0) / augmentation.progress_total) * 100));
    }
    // Fallback to disk-based node counts
    if (augmentation.total_nodes > 0) {
      return Math.min(100, Math.round((augmentation.augmented_nodes / augmentation.total_nodes) * 100));
    }
    return undefined;
  })();

  // 3. Relationship Validation (Rust)
  const validationState = computeValidationState(trace, augmentation, augmenting, validating, fastKnowledgeBuilding);
  const validationStats = (() => {
    if (validationState === 'running') return 'Validating...';
    if (validationState === 'disabled') return 'Waiting for catalogue';
    if (validationState === 'not_built') return 'Not run';
    return '0 issues found'; // Placeholder until Rust validator is fully implemented
  })();

  // 4. Epistemic Enrichment (Thinking)
  const enrichmentState = computeEpistemicState(trace, augmentation, epistemic, epistemicRunning, clusterRunning, atlasRunning, deepeningRunning, deepKnowledgeBuilding);
  const enrichmentStats = (() => {
    if (enrichmentState === 'running') {
      const cur = epistemic?.progress_current ?? 0;
      const tot = epistemic?.progress_total ?? 0;
      if (tot > 0) return `${cur.toLocaleString()} / ${tot.toLocaleString()} files`;
      return 'Enriching...';
    }
    if (enrichmentState === 'disabled') return 'Waiting for catalogue';
    if (enrichmentState === 'not_built') return 'Not run';
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
    if (clusteringState === 'not_built') return 'Not run';
    if (!modules) return '';
    return `${modules.module_count} modules · ${modules.total_files_clustered} files`;
  })();

  // 6. Atlas Building (Thinking)
  const atlasState = computeAtlasState(epistemic, modules, atlas, atlasRunning, deepeningRunning, deepKnowledgeBuilding, deepening);
  const atlasStats = (() => {
    if (atlasRunning || atlasState === 'running') return 'Building atlas...';
    // Show real data whenever it exists, regardless of whatever the
    // pre-finalize-move computeAtlasState heuristics decide. This prevents
    // the icon (driven by finStageState/atlasDone) from flashing ✓ complete
    // while the stats line still says "Not run" because computeAtlasState
    // hadn't caught up yet.
    if (atlas) {
      const parts: string[] = [];
      if (atlas.module_count) parts.push(`${atlas.module_count} segments`);
      if (atlas.file_count) parts.push(`${atlas.file_count} files`);
      if (atlas.routing) parts.push('routing');
      if (parts.length) return parts.join(' · ');
      if (atlas.exists) return 'Built';
    }
    if (atlasState === 'disabled') return 'Waiting for modules';
    return 'Not run';
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
    if (deepeningState === 'not_built') return 'Not run';
    if (!deepening) return '';
    const settled = Number.isFinite(deepening.settled_ratio) ? deepening.settled_ratio : 0;
    const avg = Number.isFinite(deepening.avg_score) ? deepening.avg_score : 0;
    const pct = Math.round(settled * 100);
    return `${pct}% settled · avg ${Math.round(avg * 100)}%`;
  })();
  const deepeningProgress = (deepeningState === 'running' && deepening?.max_iterations && deepening.max_iterations > 0)
    ? Math.round(((deepening.iteration ?? 0) / deepening.max_iterations) * 100)
    : undefined;

  // 4. Knowledge Embedding (fast — after catalogue)
  const fastKnowledgeState = computeFastKnowledgeState(trace, augmentation, knowledge, fastKnowledgeBuilding, augmenting);
  const fastKnowledgeStats = (() => {
    if (fastKnowledgeState === 'running') return 'Embedding...';
    if (fastKnowledgeState === 'disabled') return 'Waiting for catalogue';
    if (fastKnowledgeState === 'not_built') return 'Not run';
    if (!knowledge) return '';
    return `${knowledge.chunks_embedded} chunks embedded`;
  })();

  // 8. Deep Knowledge Embedding (after deep enrichment + clusters + deepening)
  // Phase 102: prefer the separate deepKnowledge payload; fall back to the
  // shared knowledge prop for any caller that hasn't been updated yet.
  const deepKnowledgeSource = deepKnowledge ?? knowledge;
  const deepKnowledgeState = computeDeepKnowledgeState(epistemic, modules, deepening, deepKnowledgeSource, deepKnowledgeBuilding);
  const deepKnowledgeStats = (() => {
    if (deepKnowledgeState === 'running') return 'Re-embedding with deep data...';
    if (deepKnowledgeState === 'disabled') return 'Waiting for enrichment + clusters';
    if (deepKnowledgeState === 'not_built') return 'Not run';
    if (!deepKnowledgeSource) return '';
    return `${deepKnowledgeSource.chunks_embedded} chunks embedded`;  // Total includes deep + fast
  })();

  // ── Build stage arrays by group ────────────────────────────

  const fastStages: EnrichmentStage[] = [
    { id: 'structural', label: 'Structural Graph', icon: GitBranch, modelTag: 'Rust', state: promoteForRebuild(structuralState), stats: structuralStats },
    {
      id: 'inferred_edges', label: 'Edge Discovery', icon: Code2, modelTag: 'Code',
      state: promoteForRebuild(inferredEdgesState), stats: inferredEdgesStats,
      progress: inferredEdgesState === 'running' && inferredEdges?.slot_progress?.total
        ? Math.min(100, Math.round((inferredEdges.slot_progress.current / inferredEdges.slot_progress.total) * 100))
        : undefined,
      rerun: inferredEdgesState === 'running' ? computeStageRerun(inferredEdges?.slot_progress?.baseline, inferredEdges?.slot_progress?.total) : undefined,
    },
    {
      id: 'catalogue', label: 'Fast Catalogue', icon: Database, modelTag: 'Fast',
      state: promoteForRebuild(catalogueState), stats: catalogueStats, progress: catalogueProgress,
      rerun: catalogueState === 'running' ? computeStageRerun(augmentation?.progress_baseline, augmentation?.progress_total) : undefined,
    },
    { id: 'validation', label: 'Relationship Validation', icon: ShieldCheck, modelTag: 'Rust', state: promoteForRebuild(validationState), stats: validationStats },
    {
      id: 'knowledge', label: 'Knowledge Embedding', icon: Database,
      state: promoteForRebuild(fastKnowledgeState), stats: fastKnowledgeStats,
      progress: fastKnowledgeState === 'running'
        ? (knowledge?.progress_total ? Math.min(100, Math.round((knowledge.progress_current ?? 0) / knowledge.progress_total * 100)) : 0)
        : undefined,
      rerun: fastKnowledgeState === 'running' ? computeStageRerun((knowledge as any)?.progress_baseline, knowledge?.progress_total) : undefined,
    },
  ];

  const deepStages: EnrichmentStage[] = [
    {
      id: 'enrichment', label: 'Deep Reasoning', icon: Brain, modelTag: 'Thinking',
      state: promoteForRebuild(enrichmentState), stats: enrichmentStats,
      progress: (epistemicRunning || epistemic?.running) && epistemic?.progress_total
        ? Math.min(100, Math.round((epistemic.progress_current ?? 0) / epistemic.progress_total * 100))
        : (enrichmentState === 'running' ? 0 : undefined),
      rerun: enrichmentState === 'running' ? computeStageRerun(epistemic?.progress_baseline, epistemic?.progress_total) : undefined,
    },
    {
      id: 'group_reasoning', label: 'Group Reasoning', icon: Network, modelTag: 'Thinking',
      state: promoteForRebuild((() => {
        if (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running) return 'running' as StageState;
        if (!epistemic?.enabled || !epistemic?.enriched_nodes) return 'disabled' as StageState;
        // If a later stage is running or already complete, group_reasoning must have finished
        if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete' as StageState;
        if (clusteringState === 'complete' || atlasState === 'complete' || deepeningState === 'complete' || deepeningState === 'stale') return 'complete' as StageState;
        if (groupReasoning?.enabled && groupReasoning?.group_count > 0) return 'complete' as StageState;
        return 'not_built' as StageState;
      })()),
      stats: (() => {
        if (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running) return 'Analyzing groups...';
        if (!epistemic?.enabled || !epistemic?.enriched_nodes) return 'Waiting for enrichment';
        if (groupReasoning?.enabled && groupReasoning?.group_count > 0) return `${groupReasoning.group_count} groups analyzed`;
        return 'Analyzed';
      })(),
      progress: (() => {
        const isRunning = groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running;
        if (!isRunning) return undefined;
        const total = groupReasoning?.progress_total;
        // Phase 118 Issue A: while running, ALWAYS render a bar — even if
        // the daemon hasn't emitted progress_total yet — so the user sees
        // an indeterminate/empty bar instead of nothing. Group Reasoning
        // was the worst offender here: bar was simply missing for the
        // entire stage.
        if (!total) return 0;
        return Math.min(100, Math.round((groupReasoning.progress_current ?? 0) / total * 100));
      })(),
      rerun: (groupReasoningRunning || groupReasoning?.slot_phase === 'running' || groupReasoning?.running)
        ? computeStageRerun(groupReasoning?.progress_baseline, groupReasoning?.progress_total) : undefined,
    },
    {
      id: 'clustering', label: 'Module Synthesis', icon: Layers, modelTag: 'Thinking',
      state: promoteForRebuild(clusteringState), stats: clusteringStats,
      progress: (clusterRunning || modules?.running) && modules?.progress_total
        ? Math.min(100, Math.round((modules.progress_current ?? 0) / modules.progress_total * 100))
        : (clusteringState === 'running' ? 0 : undefined),
      rerun: clusteringState === 'running' ? computeStageRerun(modules?.progress_baseline, modules?.progress_total) : undefined,
    },
    { id: 'deepening', label: 'Continuous Deepening', icon: Network,
      state: promoteForRebuild(deepeningState), stats: deepeningStats,
      progress: deepeningState === 'running' ? (deepeningProgress ?? 0) : undefined,
      rerun: deepeningState === 'running'
        ? computeStageRerun(deepening?.progress_baseline, deepening?.progress_total)
        : undefined,
    },
    {
      id: 'deep_knowledge', label: 'Deep Knowledge Embedding', icon: Database,
      state: promoteForRebuild(deepKnowledgeState), stats: deepKnowledgeStats,
      progress: deepKnowledgeState === 'running'
        ? (deepKnowledgeSource?.progress_total ? Math.min(100, Math.round((deepKnowledgeSource.progress_current ?? 0) / deepKnowledgeSource.progress_total * 100)) : 0)
        : undefined,
      rerun: deepKnowledgeState === 'running'
        ? computeStageRerun(deepKnowledgeSource?.progress_baseline, deepKnowledgeSource?.progress_total)
        : undefined,
    },
  ];

  // F-58: helper to determine finalize stage state.  The pipeline
  // orchestrator reports which stage is currently running via SSE
  // (finalizeGroupRunning + finalizeCurrentStageId).  Previously
  // all 5 finalize stages were binary (complete or not_built) with
  // no running indicator, so the user saw "Not generated / Not seeded /
  // Not run / Not derived" the entire time the pipeline was working.
  //
  // Now: when the finalize group is running and the current stage
  // matches this stage's ID, show 'running'. Stages BEFORE the current
  // one that aren't marked complete keep 'not_built' (they haven't run
  // yet). Stages AFTER the current one that ARE complete stay 'complete'.
  const finStageState = (stageId: string, dataComplete: boolean): StageState => {
    // Phase 105b fix: check running BEFORE dataComplete. A stage that's
    // mid-regenerate on a project with existing data (the common case
    // after Phase 104 shipped) must not appear as "complete" while it's
    // actively running — the user clicked Regenerate because they wanted
    // to see it run.
    if (finalizeGroupRunning && finalizeCurrentStageId === stageId) return 'running';
    if (dataComplete) return 'complete';
    // If the group is running and we're past this stage, treat as complete
    // (the pipeline is sequential — if we're on stage 3, stages 1-2 are done)
    if (finalizeGroupRunning && finalizeCurrentStageId) {
      const order = ['atlas', 'rules', 'concepts', 'audit', 'antibodies'];
      const currentIdx = order.indexOf(finalizeCurrentStageId);
      const thisIdx = order.indexOf(stageId);
      if (thisIdx >= 0 && currentIdx >= 0 && thisIdx < currentIdx) return 'complete';
    }
    return 'not_built';
  };

  // F-77: Atlas and Rules require real upstream content to count as
  // "complete". Otherwise placeholder atlas.json / rules files from a
  // fresh project (where deep enrichment never ran) show a green check
  // with "Waiting for modules" sub-text — which is contradictory.
  // Phase 118 U3: use rebuild-aware values so the finalize stage cards
  // keep showing "X concepts / N findings / atlas built" until the
  // rebuild actually re-runs each stage, instead of flipping to the
  // empty placeholders the moment the rebuild barrier is set.
  const atlasDone = !!effectiveAtlas?.exists && (effectiveModules?.module_count ?? 0) > 0;
  const rulesDone = !!effectiveRulesStatus?.generated && (effectiveModules?.module_count ?? 0) > 0;

  // Progress for finalize stages comes from the per-stage slot_progress
  // that the orchestrator merges into each stage object on /pipeline/status.
  // Without these wirings the bars stayed empty during runs even though
  // the worker was emitting current/total ticks (e.g. concepts at 11/15
  // while the bar still rendered at 0%).
  const finalizePercent = (status: { progress_current?: number; progress_total?: number } | undefined): number | undefined => {
    if (!status) return undefined;
    const cur = status.progress_current;
    const tot = status.progress_total;
    if (typeof cur !== 'number' || typeof tot !== 'number' || tot <= 0) return undefined;
    return Math.min(100, Math.round((cur / tot) * 100));
  };

  const finalizeStages: EnrichmentStage[] = [
    { id: 'atlas', label: 'Atlas Building', icon: Map, modelTag: 'Thinking',
      state: promoteForRebuild(finStageState('atlas', atlasDone)),
      stats: atlasStats,
      progress: finStageState('atlas', atlasDone) === 'running' ? finalizePercent(effectiveAtlas) : undefined,
      rerun: finStageState('atlas', atlasDone) === 'running'
        ? computeStageRerun(effectiveAtlas?.progress_baseline, effectiveAtlas?.progress_total)
        : undefined,
    },
    {
      id: 'rules', label: 'Rules Generation', icon: FileText, modelTag: 'CPU',
      state: promoteForRebuild(finStageState('rules', rulesDone)),
      stats: effectiveRulesStatus?.generated ? 'Generated' : finStageState('rules', false) === 'running' ? 'Generating...' : 'Not run',
      progress: finStageState('rules', rulesDone) === 'running' ? finalizePercent(effectiveRulesStatus) : undefined,
      rerun: finStageState('rules', rulesDone) === 'running'
        ? computeStageRerun(effectiveRulesStatus?.progress_baseline, effectiveRulesStatus?.progress_total)
        : undefined,
    },
    {
      id: 'concepts', label: 'Concept Seeding', icon: Lightbulb, modelTag: 'Thinking',
      state: promoteForRebuild(finStageState('concepts', !!effectiveConceptsStatus?.seeded)),
      stats: effectiveConceptsStatus?.seeded ? `${effectiveConceptsStatus.count} concepts` : finStageState('concepts', false) === 'running' ? 'Seeding...' : 'Not run',
      progress: finStageState('concepts', !!effectiveConceptsStatus?.seeded) === 'running' ? finalizePercent(effectiveConceptsStatus) : undefined,
      rerun: finStageState('concepts', !!effectiveConceptsStatus?.seeded) === 'running'
        ? computeStageRerun(effectiveConceptsStatus?.progress_baseline, effectiveConceptsStatus?.progress_total)
        : undefined,
    },
    {
      id: 'audit', label: 'Structural Audit', icon: ClipboardCheck, modelTag: 'Thinking',
      state: promoteForRebuild(finStageState('audit', !!effectiveAuditPipelineStatus?.exists)),
      stats: effectiveAuditPipelineStatus?.exists ? `${effectiveAuditPipelineStatus.finding_count} findings` : finStageState('audit', false) === 'running' ? 'Auditing...' : 'Not run',
      progress: finStageState('audit', !!effectiveAuditPipelineStatus?.exists) === 'running' ? finalizePercent(effectiveAuditPipelineStatus) : undefined,
      rerun: finStageState('audit', !!effectiveAuditPipelineStatus?.exists) === 'running'
        ? computeStageRerun(effectiveAuditPipelineStatus?.progress_baseline, effectiveAuditPipelineStatus?.progress_total)
        : undefined,
    },
    {
      id: 'antibodies', label: 'Immune System', icon: Shield, modelTag: 'CPU',
      state: promoteForRebuild(finStageState('antibodies', !!(effectiveAntibodiesStatus?.count))),
      stats: effectiveAntibodiesStatus?.count ? `${effectiveAntibodiesStatus.count} antibodies` : finStageState('antibodies', false) === 'running' ? 'Deriving...' : 'Not run',
      progress: finStageState('antibodies', !!(effectiveAntibodiesStatus?.count)) === 'running' ? finalizePercent(effectiveAntibodiesStatus) : undefined,
      rerun: finStageState('antibodies', !!(effectiveAntibodiesStatus?.count)) === 'running'
        ? computeStageRerun(effectiveAntibodiesStatus?.progress_baseline, effectiveAntibodiesStatus?.progress_total)
        : undefined,
    },
  ];

  // ── Phase 49: inject provenance into each stage ─────────
  for (const stage of [...fastStages, ...deepStages, ...finalizeStages]) {
    stage.provenance = lookupProvenance(stage.id, provenance);
  }

  // ── Phase 117: inject rebuild provenance into each stage ─────────
  if (rebuildProvenance) {
    for (const stage of [...fastStages, ...deepStages, ...finalizeStages]) {
      stage.rebuildProvenance = rebuildProvenance[stage.id];
    }
  }

  // Track which stages have ever been green this session, and remember
  // the last good stats text for each stage so we can restore it during
  // a rebuild (when wiped manifests would otherwise flip the stat copy
  // to "Not generated / Not run / etc.").
  //
  // Phase 118 U14: extended to cover EVERY sentinel string that
  // compute*Stats functions can produce when the underlying status
  // payload is "wiped". Without this, fast-sync stages (catalogue,
  // validation, knowledge) and deep-enrichment stages (enrichment,
  // group_reasoning, clustering, deepening, deep_knowledge) and atlas
  // would NOT have their prior counts preserved during a rebuild —
  // the user saw all those rows flip to "Waiting for X / No run data"
  // the moment the rebuild barrier was set, instead of remaining at
  // their prior counts until the rebuild actually re-ran each stage.
  // Earlier U3 only caught the finalize-side never-generated sentinels;
  // U14 catches the rest.
  const NEVER_GENERATED_STATS = new Set([
    // Generic
    'No run data',
    // Finalize stage sentinels (Phase 118 U3)
    'Not generated', 'Not seeded', 'Not run', 'Not derived',
    // Fast-sync stage sentinels (Phase 118 U14)
    'Not built yet', 'Waiting for graph', 'Ready to discover',
    'Ready to catalogue', 'Not validated', 'Waiting for catalogue',
    'Ready to embed',
    // Deep-enrichment stage sentinels (Phase 118 U14)
    'Ready to enrich', 'Waiting for enrichment', 'Waiting for clusters',
    'Ready to synthesize', 'Not started',
    'Waiting for enrichment + clusters', 'Ready to re-embed',
    // Finalize miscellaneous (atlas) (Phase 118 U14)
    'Waiting for modules', 'Ready to build',
  ]);
  for (const stage of [...fastStages, ...deepStages, ...finalizeStages]) {
    if (stage.state === 'complete') wasCompleteRef.current[stage.id] = true;
    if (typeof stage.stats === 'string' && stage.stats && !NEVER_GENERATED_STATS.has(stage.stats)) {
      lastGoodStatsRef.current[stage.id] = stage.stats;
    }
  }
  // Freeze-green: if a stage was previously complete and is now showing a
  // "waiting"-like state because a rebuild destroy wiped its manifest,
  // keep it green until it actually starts running. Gated on isRebuilding
  // so that Reset-All (which also regresses state but without a rebuild
  // barrier) correctly reverts stages to not_built / disabled instead of
  // trapping them as stale-green.
  //
  // Phase 118 Issue B: also include 'stale' and 'warning' — these are the
  // "data exists but is from a prior run / partial" states that finalize
  // stages enter when a rebuild wipes their manifest mid-run. Without
  // these the panel shows "Not generated, No run data" for the rest of
  // the rebuild even though the prior run finished successfully.
  const regressedStates: StageState[] = [
    'not_built', 'disabled', 'queued', 'waiting', 'idle', 'stale', 'warning',
  ];
  if (isRebuilding) {
    for (const stage of [...fastStages, ...deepStages, ...finalizeStages]) {
      if (
        wasCompleteRef.current[stage.id] &&
        regressedStates.includes(stage.state)
      ) {
        stage.state = 'complete';
        stage.progress = undefined;
        // Phase 118 U6: mark this stage as "frozen from prior run" so the
        // panel can render it visually distinct from a stage that
        // genuinely completed in the current rebuild. Without this the
        // user sees a green checkmark on a stage that hasn't actually
        // re-run and assumes the rebuild is further along than it is.
        // The flag is consumed by data-stage-frozen attr on the row +
        // the stat-text decoration below.
        (stage as EnrichmentStage & { _frozen?: boolean })._frozen = true;
      }
      // Phase 118 Issue B: restore last-known-good stats so frozen stages
      // don't show "Not generated" while waiting for the rebuild to reach
      // them. Only override the "never generated" sentinels — actual
      // running/in-progress stats (e.g. "Generating...", "5/12 batches")
      // come through unchanged.
      if (
        wasCompleteRef.current[stage.id]
        && typeof stage.stats === 'string'
        && NEVER_GENERATED_STATS.has(stage.stats)
        && lastGoodStatsRef.current[stage.id]
      ) {
        // Prefix with a small marker so the user can tell this is the
        // prior-run value being preserved through the rebuild.
        stage.stats = `prior: ${lastGoodStatsRef.current[stage.id]}`;
      }
    }
  }

  // ── Group running state ──────────────────────────────────
  const fastRunning = fastStages.some(s => s.state === 'running' || s.state === 'rebuilding');
  const deepRunning = deepStages.some(s => s.state === 'running' || s.state === 'rebuilding');
  const finalizeRunning = finalizeStages.some(s => s.state === 'running' || s.state === 'rebuilding');

  // ── Toggle helpers ─────────────────────────────────────────

  const setFastSync = (v: boolean) => {
    onAutoConfigChange?.({ ...cfg, fastSync: v });
  };

  const setDeepMode = (v: DeepEnrichmentMode) => {
    onAutoConfigChange?.({ ...cfg, deepEnrichment: v });
  };

  // ── Progress ───────────────────────────────────────────────

  const allStates = [...fastStages, ...deepStages, ...finalizeStages].map(s => s.state);
  const completedStages = allStates.filter(s => s === 'complete').length;
  const overallProgress = completedStages / allStates.length * 100;
  const roundedProgress = Math.round(overallProgress);

  const rebuildStages: RebuildStageSnapshot[] = [...fastStages, ...deepStages, ...finalizeStages]
    .map((s) => ({ state: s.state, progress: s.progress }));
  const overallRebuildPercent = isRebuilding
    ? computeOverallRebuildPercent(rebuildStages)
    : 0;
  const fastRebuildPercent = isRebuilding
    ? computeOverallRebuildPercent(fastStages.map((s) => ({ state: s.state, progress: s.progress })))
    : 0;
  const deepRebuildPercent = isRebuilding
    ? computeOverallRebuildPercent(deepStages.map((s) => ({ state: s.state, progress: s.progress })))
    : 0;
  const finalizeRebuildPercent = isRebuilding
    ? computeOverallRebuildPercent(finalizeStages.map((s) => ({ state: s.state, progress: s.progress })))
    : 0;
  const isPipelinePaused = Boolean(fastPaused || deepPaused || finalizePaused);

  // A group with no stages left to run shouldn't display a Resume button — the
  // backend's paused flag can survive daemon restarts or partial resets, so we
  // need a frontend invariant: if every stage is complete or disabled, there
  // is nothing to resume, regardless of what `fastPaused` says.
  const isGroupSettled = (stages: EnrichmentStage[]) =>
    stages.every(s => s.state === 'complete' || s.state === 'disabled');
  const fastSettled = isGroupSettled(fastStages);
  const deepSettled = isGroupSettled(deepStages);
  const finalizeSettled = isGroupSettled(finalizeStages);
  const effectiveFastPaused = fastPaused && !fastSettled;
  const effectiveDeepPaused = deepPaused && !deepSettled;
  const effectiveFinalizePaused = finalizePaused && !finalizeSettled;

  // ── Hero state: trace not yet built ──────────────────────────
  // Phase 118 U1: never show the cold-start hero during an active rebuild.
  // During /pipeline/rebuild the structural manifest is briefly absent
  // between wipe and re-write — without this guard the panel flips back
  // to "Initialize Trace Graph" in the middle of a rebuild that the user
  // explicitly triggered. The barrier is the authoritative signal that a
  // rebuild is in progress; if it's active, treat trace as built so the
  // 15-stage panel keeps rendering (with freeze-green covering the gaps).
  //
  // Phase 118 U8: same root-cause class — when ANY stage is currently
  // running (e.g. user destroyed the project then clicked Run; backend
  // is happily running stages 6-10 of deep enrichment), the panel
  // STILL needs to render the live pipeline view, not the cold-start
  // hero. Without this guard, the user clicks Run, the queue shows
  // "Building", but the main panel sits on the hero — a confusing
  // backend/frontend disagreement. Detect any pipeline activity from
  // the per-stage running flags (which are already gated on group
  // active by F-NEW-6/F-NEW-7).
  const anyPipelineActive = !!(
    inferredEdgesRunning || augmenting || validating || fastKnowledgeBuilding
    || epistemicRunning || groupReasoningRunning || clusterRunning
    || atlasRunning || deepeningRunning || deepKnowledgeBuilding
    || finalizeGroupRunning
  );
  const traceNotBuilt = !trace.exists && !trace.building && !isRebuilding && !anyPipelineActive;

  // ── Loading gate: project is switching, don't show hero or stale data ──
  if (projectLoading) {
    return (
      <div className={cn("flex flex-col items-center justify-center gap-3 py-12 px-4", className)}>
        <Loader2 className="w-8 h-8 text-text-muted/40 animate-spin" />
        <p className="text-xs text-text-muted">Loading project...</p>
      </div>
    );
  }

  if (traceNotBuilt) {
    return (
      <div className={cn("flex flex-col items-center justify-center gap-4 py-8 px-4 text-center", className)}>
        {/* Phase 118 R4: surface barrier indicator even when the panel is
            in its empty/hero state. After reset-all the project has no
            data but a barrier is active; without this the user has no
            UI signal that selfheal is blocked. */}
        {barrier?.active && (
          <div className="w-full max-w-md">
            <BarrierIndicator barrier={barrier} onClear={onClearBarrier} pipelineActive={anyPipelineActive} />
          </div>
        )}
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
            data-testid="pipeline-build-trace-hero"
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

  // ── Phase 117: resolve active rebuild scope and RebuildingRow context ───
  const activeRebuildScope = rebuildScope(barrier);
  const allStages: EnrichmentStage[] = [...fastStages, ...deepStages, ...finalizeStages];
  const stagesInScope: EnrichmentStage[] =
    activeRebuildScope === 'sync'
      ? fastStages
      : activeRebuildScope === 'enrichment'
        ? deepStages
        : activeRebuildScope === 'all'
          ? allStages
          : [];
  // Phase 118 U3 follow-up: pipeline runs sequentially, so when multiple
  // stages report running/rebuilding (which happens transiently if a
  // per-stage running flag from a finished group hasn't cleared yet),
  // the LATEST running stage is the true current — earlier "running"
  // entries are stale flags. Picking the first one (findIndex) caused
  // the rebuild header to label the active stage as e.g. "Knowledge"
  // when enrichment was actually running.
  let currentStageIndex = -1;
  for (let i = stagesInScope.length - 1; i >= 0; i--) {
    const s = stagesInScope[i];
    if (s.state === 'rebuilding' || s.state === 'running') {
      currentStageIndex = i;
      break;
    }
  }
  const safeCurrentIndex = currentStageIndex >= 0 ? currentStageIndex : 0;
  const currentStageLabel = stagesInScope[safeCurrentIndex]?.label ?? '';

  return (
    <div
      data-testid="pipeline-panel"
      data-overall-progress={roundedProgress}
      data-fast-running={fastRunning || undefined}
      data-deep-running={deepRunning || undefined}
      data-finalize-running={finalizeRunning || undefined}
      className={cn("flex flex-col gap-3", fadeIn && "animate-in fade-in duration-500", className)}
    >

      {isRebuilding && (
        <div className="px-4 pt-3 pb-1" data-testid="overall-rebuild-bar">
          <StageProgressBar
            variant="rebuild"
            rebuildPercent={overallRebuildPercent}
            className="h-2"
            rebuildStateOverlay={isPipelinePaused ? 'paused' : undefined}
          />
        </div>
      )}

      {/* ── Phase 117: sticky RebuildingRow (active rebuild only) ─────── */}
      {activeRebuildScope && stagesInScope.length > 0 && (
        <div className="sticky top-0 z-20 px-1" data-testid="rebuilding-row">
          <RebuildingRow
            scope={activeRebuildScope}
            currentStageIndex={safeCurrentIndex}
            totalStagesInScope={stagesInScope.length}
            currentStageLabel={currentStageLabel}
            percent={overallRebuildPercent}
            onStop={onStopRebuild}
          />
        </div>
      )}

      {/* ── Phase 114: Reset Barrier Banner ─────────── */}
      {barrier?.active && (
        <BarrierIndicator barrier={barrier} onClear={onClearBarrier} pipelineActive={anyPipelineActive || isRebuilding} />
      )}

      {/* ── Phase 114: Pipeline Health Badge ─────────── */}
      {health && <div className="px-1"><HealthBadge health={health} /></div>}

      {/* ── Fast Sync Group ─────────────────────────── */}
      <div data-testid="pipeline-group-fast_sync" data-group-running={fastRunning || undefined} className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={fastCollapsed} onClick={onToggleFastCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Fast Sync</span>
          {fastAuto && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-success-muted/10 text-success border border-success-muted/20">
              <Eye className="w-2.5 h-2.5" />
              Watching
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!fastAuto && effectiveFastPaused && onResumePipeline && !fastRunning && (
            <button
              onClick={() => onResumePipeline('fast_sync')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {!fastAuto && onRunFastSync && !effectiveFastPaused && (
            <button
              data-testid="pipeline-run-fast_sync"
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
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {fastCollapsed ? (
        <CondensedGroupRow
          rollup={computeGroupRollup(fastStages)}
          isRebuilding={isRebuilding}
          groupRebuildPercent={fastRebuildPercent}
        />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {fastStages.map((stage, idx) => {
            // Use explicit backend stage ID if available; fall back to heuristic.
            // A stage that is itself already 'complete' or 'disabled' must never
            // be rendered as paused — otherwise a stale backend fastPausedStage
            // (e.g. persisted across a daemon restart) paints a finished stage
            // orange with a misleading "Paused · 0 issues found" label.
            const isStagePaused = fastPausedStage
              ? !!(effectiveFastPaused && !fastRunning && stage.id === fastPausedStage &&
                stage.state !== 'complete' && stage.state !== 'disabled')
              : !!(effectiveFastPaused && !fastRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                fastStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            const showRecover = projectId && apiClient &&
              (stage.state === 'error' || stage.state === 'warning' || stage.state === 'stale');
            return (
              <div key={stage.id}>
                <StageRow
                  stage={stage}
                  isPaused={isStagePaused}
                  onPause={stage.state === 'running' || stage.state === 'rerunning' || stage.state === 'rebuilding' ? onPausePipeline : undefined}
                  onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('fast_sync') : undefined}
                  showDetails={showDetails}
                  isRebuilding={isRebuilding}
                  onRebuild={onRebuild}
                />
                {showRecover && (
                  <RecoverStagePanel
                    projectId={projectId}
                    stageId={stage.id}
                    stageLabel={stage.label}
                    apiClient={apiClient}
                    disabled={fastRunning}
                    onRestored={(snapshotId) => onStageRestored?.(stage.id, snapshotId)}
                    className="ml-11 mt-0.5 mb-1"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Deep Enrichment Group ───────────────────── */}
      <div data-testid="pipeline-group-deep_enrichment" data-group-running={deepRunning || undefined} className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={deepCollapsed} onClick={onToggleDeepCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Deep Enrichment</span>
        </div>
        <div className="flex items-center gap-2">
          {effectiveDeepPaused && onResumePipeline && !deepRunning && (
            <button
              onClick={() => onResumePipeline('deep_enrichment')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {deepMode === 'manual' && onRunDeepEnrichment && !(effectiveDeepPaused && !deepRunning) && (
            <button
              data-testid="pipeline-run-deep_enrichment"
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
              {deepRunning ? 'Running…' : effectiveDeepPaused ? 'Paused' : 'Run'}
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
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {deepCollapsed ? (
        <CondensedGroupRow
          rollup={computeGroupRollup(deepStages)}
          isRebuilding={isRebuilding}
          groupRebuildPercent={deepRebuildPercent}
        />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {deepStages.map((stage, idx) => {
            // Use explicit backend stage ID if available; fall back to heuristic.
            // Never mark an already-complete or disabled stage as paused.
            const isStagePaused = deepPausedStage
              ? !!(effectiveDeepPaused && !deepRunning && stage.id === deepPausedStage &&
                stage.state !== 'complete' && stage.state !== 'disabled')
              : !!(effectiveDeepPaused && !deepRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                deepStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            const showRecover = projectId && apiClient &&
              (stage.state === 'error' || stage.state === 'warning' || stage.state === 'stale');
            return (
              <div key={stage.id}>
                <StageRow
                  stage={stage}
                  onPause={stage.state === 'running' || stage.state === 'rerunning' || stage.state === 'rebuilding' ? onPausePipeline : undefined}
                  onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('deep_enrichment') : undefined}
                  isPaused={isStagePaused}
                  showDetails={showDetails}
                  isRebuilding={isRebuilding}
                  onRebuild={onRebuild}
                />
                {showRecover && (
                  <RecoverStagePanel
                    projectId={projectId}
                    stageId={stage.id}
                    stageLabel={stage.label}
                    apiClient={apiClient}
                    disabled={deepRunning}
                    onRestored={(snapshotId) => onStageRestored?.(stage.id, snapshotId)}
                    className="ml-11 mt-0.5 mb-1"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Finalize Group ──────────────────────────── */}
      <div data-testid="pipeline-group-finalize" data-group-running={finalizeRunning || undefined} className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={finalizeCollapsed} onClick={onToggleFinalizeCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Finalize</span>
        </div>
        <div className="flex items-center gap-2">
          {effectiveFinalizePaused && onResumePipeline && !finalizeRunning && (
            <button
              onClick={() => onResumePipeline('finalize')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {/* Phase 105b: hide Run button when finalize mode is Auto, matching
              the deep-enrichment pattern. In Auto mode, finalize chains
              automatically after deep completes — manual Run is misleading. */}
          {cfg.finalize === 'manual' && onRunFinalize && !effectiveFinalizePaused && (
            <button
              data-testid="pipeline-run-finalize"
              onClick={inactive ? undefined : onRunFinalize}
              disabled={finalizeRunning || limitReached || inactive}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (finalizeRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {finalizeRunning ? 'Running\u2026' : 'Run'}
            </button>
          )}
          <SlidingSwitch2
            value={cfg.finalize === 'auto'}
            onChange={onAutoConfigChange ? (v: boolean) => onAutoConfigChange({ ...cfg, finalize: v ? 'auto' : 'manual' }) : undefined}
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {finalizeCollapsed ? (
        <CondensedGroupRow
          rollup={computeGroupRollup(finalizeStages)}
          isRebuilding={isRebuilding}
          groupRebuildPercent={finalizeRebuildPercent}
        />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {finalizeStages.map((stage, idx) => {
            // Never mark an already-complete or disabled stage as paused.
            const isStagePaused = finalizePausedStage
              ? !!(effectiveFinalizePaused && !finalizeRunning && stage.id === finalizePausedStage &&
                stage.state !== 'complete' && stage.state !== 'disabled')
              : !!(effectiveFinalizePaused && !finalizeRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                finalizeStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            const showRecover = projectId && apiClient &&
              (stage.state === 'error' || stage.state === 'warning' || stage.state === 'stale');
            return (
              <div key={stage.id}>
                <StageRow
                  stage={stage}
                  onPause={stage.state === 'running' || stage.state === 'rerunning' || stage.state === 'rebuilding' ? onPausePipeline : undefined}
                  onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('finalize') : undefined}
                  isPaused={isStagePaused}
                  showDetails={showDetails}
                  isRebuilding={isRebuilding}
                  onRebuild={onRebuild}
                />
                {showRecover && (
                  <RecoverStagePanel
                    projectId={projectId}
                    stageId={stage.id}
                    stageLabel={stage.label}
                    apiClient={apiClient}
                    disabled={finalizeRunning}
                    onRestored={(snapshotId) => onStageRestored?.(stage.id, snapshotId)}
                    className="ml-11 mt-0.5 mb-1"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

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
        />
      </div>

    </div>
  );
}
