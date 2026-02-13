import { useState } from 'react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import {
  GitBranch, Brain, ShieldCheck, Play, Pause, AlertTriangle, CheckCircle2,
  Circle, Clock, Loader2, Layers, Network, Database, Trash2
} from 'lucide-react';
import type { AugmentationStatus, DeepAnalysisRunStatus, EpistemicStatus, ModuleStatus, DeepeningStatus } from '../../types';

// ── Types ────────────────────────────────────────────────────

export interface TraceStageInfo {
  enabled: boolean;
  exists: boolean;
  building: boolean;
  counts: { nodes: number; edges: number };
  last_build_at: string | null;
}

export interface GraphEnrichmentPipelineProps {
  trace: TraceStageInfo;
  augmentation?: AugmentationStatus;
  deepAnalysis?: DeepAnalysisRunStatus;
  epistemic?: EpistemicStatus;
  modules?: ModuleStatus;
  deepening?: DeepeningStatus;
  smallModelConfigured?: boolean;
  largeModelConfigured?: boolean;
  onBuildTrace?: () => void;
  onRunAugmentation?: () => void;
  onRunDeepAnalysis?: () => void;
  onRunEpistemic?: () => void;
  onRunModuleSynthesis?: () => void;
  onRunDeepening?: () => void;
  onDestroyGraph?: () => void;
  onTogglePause?: () => void;
  augmenting?: boolean;
  deepAnalyzing?: boolean;
  epistemicRunning?: boolean;
  clusterRunning?: boolean;
  deepeningRunning?: boolean;
  paused?: boolean;
  className?: string;
}

type StageState = 'disabled' | 'waiting' | 'running' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';

interface EnrichmentStage {
  id: 'structural' | 'catalogue' | 'validation' | 'enrichment' | 'clustering' | 'deepening';
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  modelTag?: string;
  state: StageState;
  stats?: string;
  progress?: number;
  duration?: string;
}

// ── Helpers ──────────────────────────────────────────────────

function computeTraceState(trace: TraceStageInfo): StageState {
  if (!trace.enabled) return 'disabled';
  if (trace.building) return 'running';
  if (!trace.exists) return 'not_built';
  return 'complete';
}

function computeAugmentState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  augmenting?: boolean
): StageState {
  if (!trace.enabled || !trace.exists) return 'disabled';
  if (augmenting) return 'running';
  if (!aug || !aug.enabled) return 'not_built';
  if (aug.augmented_nodes === 0) return 'not_built';
  if (aug.low_confidence_count > aug.augmented_nodes * 0.3) return 'warning';
  if (aug.augmented_nodes < aug.total_nodes * 0.5) return 'stale';
  return 'complete';
}

function computeDeepState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  deep?: DeepAnalysisRunStatus,
  deepAnalyzing?: boolean
): StageState {
  if (!trace.enabled || !trace.exists) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (deepAnalyzing || deep?.running) return 'running';
  if (!deep?.last_run_at) return 'not_built';
  
  // Stale if >2 weeks since last run and queue > 0
  const diffMs = Date.now() - new Date(deep.last_run_at).getTime();
  const twoWeeks = 14 * 24 * 60 * 60 * 1000;
  if (diffMs > twoWeeks && (deep.queue_size ?? 0) > 0) return 'stale';
  
  if ((deep.queue_size ?? 0) > 0 && (deep.avg_confidence ?? 1) < 0.6) return 'warning';
  return 'complete';
}

function computeEpistemicState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  ep?: EpistemicStatus,
  running?: boolean
): StageState {
  if (!trace.enabled || !trace.exists) return 'disabled';
  if (!aug || !aug.enabled || aug.augmented_nodes === 0) return 'disabled';
  if (running || ep?.running) return 'running';
  if (!ep || !ep.enabled) return 'not_built';
  if (ep.enriched_nodes === 0) return 'not_built';
  if (ep.avg_confidence < 0.5) return 'warning';
  return 'complete';
}

function computeModuleState(
  ep?: EpistemicStatus,
  mod?: ModuleStatus,
  running?: boolean
): StageState {
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (running || mod?.running) return 'running';
  if (!mod || !mod.enabled) return 'not_built';
  if (mod.module_count === 0) return 'not_built';
  return 'complete';
}

function computeDeepeningState(
  ep?: EpistemicStatus,
  deep?: DeepeningStatus,
  running?: boolean
): StageState {
  if (!ep || !ep.enabled || ep.enriched_nodes === 0) return 'disabled';
  if (running || deep?.running) return 'running';
  if (!deep || deep.total_scored === 0) return 'not_built';
  if (deep.settled_ratio >= 0.95) return 'complete';
  if (deep.settled_ratio >= 0.5) return 'stale';
  return 'warning';
}

// ── Components ───────────────────────────────────────────────

const STATE_STYLES: Record<StageState, { bg: string; border: string; text: string; icon: string }> = {
  disabled:  { bg: 'bg-surface-raised',     border: 'border-border',        text: 'text-text-subtle',  icon: 'text-text-subtle' },
  not_built: { bg: 'bg-surface-raised',     border: 'border-border',        text: 'text-text-muted',   icon: 'text-text-muted' },
  waiting:   { bg: 'bg-amber-500/10',       border: 'border-amber-500/30',  text: 'text-amber-400',    icon: 'text-amber-400' },
  running:   { bg: 'bg-blue-500/10',        border: 'border-blue-500/30',   text: 'text-blue-400',     icon: 'text-blue-400' },
  stale:     { bg: 'bg-amber-500/10',       border: 'border-amber-500/30',  text: 'text-amber-400',    icon: 'text-amber-400' },
  complete:  { bg: 'bg-emerald-500/10',     border: 'border-emerald-500/30',text: 'text-emerald-400',  icon: 'text-emerald-400' },
  warning:   { bg: 'bg-orange-500/10',      border: 'border-orange-500/30', text: 'text-orange-400',   icon: 'text-orange-400' },
  error:     { bg: 'bg-red-500/10',         border: 'border-red-500/30',    text: 'text-red-400',      icon: 'text-red-400' },
  idle:      { bg: 'bg-surface-raised',     border: 'border-border',        text: 'text-text-muted',   icon: 'text-text-muted' },
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
    case 'running':
      return <Loader2 className={cn(cls, 'animate-spin')} />;
    case 'warning':
      return <AlertTriangle className={cls} />;
    case 'complete':
      return <CheckCircle2 className={cls} />;
    case 'error':
      return <AlertTriangle className={cls} />;
  }
}

function StageRow({ stage }: { stage: EnrichmentStage }) {
  const s = STATE_STYLES[stage.state];
  
  return (
    <div className="flex items-start gap-3 relative py-0.5 group">
      {/* Connector Line */}
      <div className="absolute left-[15px] top-6 bottom-[-6px] w-px bg-border group-last:hidden" />
      
      {/* Icon Bubble */}
      <div className={cn(
        "w-8 h-8 rounded-full border flex items-center justify-center shrink-0 z-10 transition-colors",
        s.bg, s.border, s.text
      )}>
        <stage.icon className="w-4 h-4" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 py-0.5">
        <div className="flex items-center justify-between mb-0.5">
          <div className="flex items-center gap-2">
            <span className={cn("text-xs font-semibold", s.text)}>{stage.label}</span>
            {stage.modelTag && (
              <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-surface-raised border border-border">
                {stage.modelTag}
              </span>
            )}
          </div>
          <div className={cn("flex items-center gap-1.5 text-xs", s.text)}>
             {stage.state === 'running' && stage.progress !== undefined && (
               <span className="text-[10px] opacity-80">{stage.progress}%</span>
             )}
             {stage.duration && stage.state === 'complete' && (
               <span className="text-[10px] opacity-80">{stage.duration}</span>
             )}
             <StateIcon state={stage.state} />
          </div>
        </div>
        
        {stage.stats && (
          <p className="text-[10px] text-text-muted truncate leading-tight">
            {stage.stats}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────

export function GraphEnrichmentPipeline({
  trace,
  augmentation,
  deepAnalysis,
  epistemic,
  modules,
  deepening,
  augmenting = false,
  deepAnalyzing = false,
  epistemicRunning = false,
  clusterRunning = false,
  deepeningRunning = false,
  paused = false,
  onTogglePause,
  onBuildTrace,
  onRunAugmentation,
  onRunDeepAnalysis,
  onRunEpistemic,
  onRunModuleSynthesis,
  onRunDeepening,
  onDestroyGraph,
  className,
}: GraphEnrichmentPipelineProps) {
  
  // 1. Structural Graph (Rust)
  const structuralState = computeTraceState(trace);
  const structuralStats = structuralState === 'complete' || structuralState === 'running'
    ? `${trace.counts.nodes.toLocaleString()} nodes · ${trace.counts.edges.toLocaleString()} edges`
    : structuralState === 'not_built' ? 'Not built yet'
    : 'Disabled';

  // 2. Fast Catalogue (3b)
  const catalogueState = computeAugmentState(trace, augmentation, augmenting);
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

  // 3. Relationship Validation (Rust) - mapped from deepAnalysis
  const validationState = computeDeepState(trace, augmentation, deepAnalysis, deepAnalyzing);
  const validationStats = (() => {
    if (validationState === 'running') return 'Validating...';
    if (validationState === 'disabled') return 'Waiting for catalogue';
    if (validationState === 'not_built') return 'Not validated';
    if (!deepAnalysis) return '';
    return deepAnalysis.queue_size != null 
      ? `${deepAnalysis.queue_size} items queued` 
      : 'Validation complete';
  })();

  // 4. Epistemic Enrichment (14b)
  const enrichmentState = computeEpistemicState(trace, augmentation, epistemic, epistemicRunning);
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

  // 5. Cluster Synthesis (14b)
  const clusteringState = computeModuleState(epistemic, modules, clusterRunning);
  const clusteringStats = (() => {
    if (clusteringState === 'running') return 'Synthesizing...';
    if (clusteringState === 'disabled') return 'Waiting for enrichment';
    if (clusteringState === 'not_built') return 'Ready to synthesize';
    if (!modules) return '';
    return `${modules.module_count} modules · ${modules.total_files_clustered} files`;
  })();

  // 6. Continuous Deepening
  const deepeningState = computeDeepeningState(epistemic, deepening, deepeningRunning);
  const deepeningStats = (() => {
    if (deepeningState === 'running') {
      const iter = deepening?.iteration ?? 0;
      const max = deepening?.max_iterations ?? '?';
      return `Iteration ${iter}/${max}`;
    }
    if (deepeningState === 'disabled') return 'Waiting for enrichment';
    if (deepeningState === 'not_built') return 'Not started';
    if (!deepening) return '';
    const pct = Math.round(deepening.settled_ratio * 100);
    return `${pct}% settled · avg ${Math.round(deepening.avg_score * 100)}%`;
  })();

  const stages: EnrichmentStage[] = [
    {
      id: 'structural',
      label: 'Structural Graph',
      icon: GitBranch,
      modelTag: 'Rust',
      state: structuralState,
      stats: structuralStats,
    },
    {
      id: 'catalogue',
      label: 'Fast Catalogue',
      icon: Database,
      modelTag: '3b',
      state: catalogueState,
      stats: catalogueStats,
    },
    {
      id: 'validation',
      label: 'Relationship Validation',
      icon: ShieldCheck,
      modelTag: 'Rust',
      state: validationState,
      stats: validationStats,
    },
    {
      id: 'enrichment',
      label: 'Epistemic Enrichment',
      icon: Brain,
      modelTag: '14b',
      state: enrichmentState,
      stats: enrichmentStats,
      progress: epistemic?.running && epistemic?.progress_total
        ? Math.round((epistemic.progress_current ?? 0) / epistemic.progress_total * 100)
        : undefined,
    },
    {
      id: 'clustering',
      label: 'Cluster Synthesis',
      icon: Layers,
      modelTag: '14b',
      state: clusteringState,
      stats: clusteringStats,
    },
    {
      id: 'deepening',
      label: 'Continuous Deepening',
      icon: Network,
      state: deepeningState,
      stats: deepeningStats,
    },
  ];

  // Calculate overall progress across all 6 stages
  const allStates = [structuralState, catalogueState, validationState, enrichmentState, clusteringState, deepeningState];
  const completedStages = allStates.filter(s => s === 'complete').length;
  const overallProgress = completedStages / allStates.length * 100;
  const roundedProgress = Math.round(overallProgress);
  const anyStageRunning = allStates.some(s => s === 'running');

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-border">
        <h3 className="text-xs font-semibold text-text">Graph Enrichment</h3>
        {onTogglePause && (
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={onTogglePause}
            className={cn(
              "h-6 w-6",
              paused ? "text-amber-400 hover:text-amber-500" : "text-emerald-400 hover:text-emerald-500"
            )}
            title={paused ? "Resume enrichment" : "Pause enrichment (save battery)"}
          >
            {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
          </Button>
        )}
      </div>

      {/* Pipeline Stages */}
      <div className="flex flex-col gap-1">
        {stages.map((stage) => (
          <StageRow key={stage.id} stage={stage} />
        ))}
      </div>

      {/* Footer / Summary */}
      <div className="pt-3 border-t border-border">
        <div className="flex items-center justify-between text-[10px] text-text-muted">
          <span>Overall Health</span>
          <span>{roundedProgress}% Enrichment</span>
        </div>
        {/* Simple Progress Bar */}
        <div className="h-1 w-full bg-surface-raised rounded-full mt-1.5 overflow-hidden">
          <div 
            className="h-full bg-primary/50 transition-all duration-500"
            style={{ width: `${roundedProgress}%` }}
          />
        </div>
      </div>

      {/* Primary Actions (Contextual) */}
      {structuralState === 'not_built' && onBuildTrace && (
        <Button size="sm" className="w-full" onClick={onBuildTrace}>
          Build Structural Graph
        </Button>
      )}
      {structuralState === 'complete' && catalogueState === 'not_built' && onRunAugmentation && (
        <Button size="sm" className="w-full" onClick={onRunAugmentation}>
          Run Fast Catalogue
        </Button>
      )}
      {catalogueState === 'complete' && validationState === 'not_built' && onRunDeepAnalysis && (
        <Button size="sm" className="w-full" onClick={onRunDeepAnalysis}>
          Run Validation
        </Button>
      )}
      {validationState === 'complete' && enrichmentState === 'not_built' && onRunEpistemic && (
        <Button size="sm" className="w-full" onClick={onRunEpistemic}>
          Run Epistemic Enrichment
        </Button>
      )}
      {enrichmentState === 'complete' && clusteringState === 'not_built' && onRunModuleSynthesis && (
        <Button size="sm" className="w-full" onClick={onRunModuleSynthesis}>
          Run Cluster Synthesis
        </Button>
      )}
      {clusteringState === 'complete' && deepeningState !== 'complete' && deepeningState !== 'running' && deepeningState !== 'disabled' && onRunDeepening && (
        <Button size="sm" className="w-full" onClick={onRunDeepening}>
          Run Deepening Loop
        </Button>
      )}

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

  if (confirming) {
    return (
      <div className="mt-4 p-3 rounded-md border border-red-500/30 bg-red-500/5 space-y-2">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-xs font-medium text-red-400">Destroy entire graph?</p>
            <p className="text-[11px] text-text-muted">
              This permanently deletes the structural graph, all augmentations,
              epistemic enrichment, cluster modules, and deepening data.
              You will need to rebuild from scratch.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="destructive"
            size="sm"
            className="flex-1"
            onClick={() => { setConfirming(false); onConfirm(); }}
          >
            <Trash2 className="w-3.5 h-3.5 mr-1" />
            Yes, destroy
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={() => setConfirming(false)}
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

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
    </div>
  );
}
