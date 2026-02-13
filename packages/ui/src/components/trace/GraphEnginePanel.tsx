import { useState } from 'react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { ConfirmDialog } from '../primitives/ConfirmDialog';
import {
  GitBranch,
  Brain,
  ShieldCheck,
  Play,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  Layers,
  Network,
  Trash2,
  Zap,
  Scan,
  Power
} from 'lucide-react';
import type { GraphEngineStatus, GraphEngineConfig } from '../../types';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface GraphEnginePanelProps {
  status: GraphEngineStatus | null;
  config?: GraphEngineConfig;
  onUpdateConfig: (config: GraphEngineConfig) => void;
  onRunStage: (stage: string) => void;
  onRunAutoPilot: () => void;
  onStop: () => void;
  onDestroyGraph?: () => void;
  className?: string;
}

type StageKey = keyof GraphEngineStatus['stages'];

interface StageDefinition {
  id: StageKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  defaultAuto: boolean;
}

const STAGES: StageDefinition[] = [
  {
    id: 'trace',
    label: 'Structural Trace',
    icon: GitBranch,
    description: 'Parses code into AST nodes and edges (Rust)',
    defaultAuto: true,
  },
  {
    id: 'vector',
    label: 'Vector Indexing',
    icon: Scan,
    description: 'Embeds raw source code for search',
    defaultAuto: true,
  },
  {
    id: 'catalogue',
    label: 'Fast Catalogue',
    icon: Zap,
    description: 'Generates initial summaries (3b model)',
    defaultAuto: true,
  },
  {
    id: 'validation',
    label: 'Rel. Validation',
    icon: ShieldCheck,
    description: 'Validates edges and infers connections (Rust)',
    defaultAuto: true,
  },
  {
    id: 'epistemic',
    label: 'Epistemic Enrichment',
    icon: Brain,
    description: 'Deep understanding and domain tagging (14b)',
    defaultAuto: false,
  },
  {
    id: 'clustering',
    label: 'Cluster Synthesis',
    icon: Layers,
    description: 'Synthesizes module-level concepts',
    defaultAuto: false,
  },
  {
    id: 'knowledge',
    label: 'Knowledge Embedding',
    icon: Network,
    description: 'Embeds synthesized knowledge for semantic search',
    defaultAuto: false,
  },
];

type StageState = 'disabled' | 'waiting' | 'running' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';

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

// ── Helpers ──────────────────────────────────────────────────

function getStageState(stageId: StageKey, status: GraphEngineStatus | null): StageState {
  if (!status) return 'disabled';
  const s = status.stages[stageId];
  
  if (stageId === 'trace') {
    const t = s as GraphEngineStatus['stages']['trace'];
    if (t.building) return 'running';
    if (t.exists) return 'complete';
    return 'not_built';
  }
  
  if (stageId === 'vector') {
    const v = s as GraphEngineStatus['stages']['vector'];
    if (v.building) return 'running';
    if (v.exists) return 'complete';
    return 'not_built';
  }

  if (stageId === 'catalogue') {
    const c = s as GraphEngineStatus['stages']['catalogue'];
    // Augmentation usually runs via trace build or manually? 
    // Status struct has low_confidence_count etc.
    if (c.total_nodes === 0) return 'not_built';
    if (c.augmented_nodes < c.total_nodes * 0.1) return 'not_built';
    if (c.augmented_nodes < c.total_nodes) return 'running'; // Or partial/stale
    return 'complete';
  }

  if (stageId === 'validation') {
    const v = s as GraphEngineStatus['stages']['validation'];
    // No dedicated running flag for validation yet?
    if (v.validated_edges > 0) return 'complete';
    return 'not_built';
  }

  if (stageId === 'epistemic') {
    const e = s as GraphEngineStatus['stages']['epistemic'];
    if (e.running) return 'running';
    if (e.enriched_nodes > 0) return 'complete';
    return 'not_built';
  }

  if (stageId === 'clustering') {
    const c = s as GraphEngineStatus['stages']['clustering'];
    if (c.running) return 'running';
    if (c.module_count > 0) return 'complete';
    return 'not_built';
  }

  if (stageId === 'knowledge') {
    const k = s as GraphEngineStatus['stages']['knowledge'];
    if (k.building || k.running) return 'running';
    if (k.chunks_embedded > 0 || (k as any).count > 0) return 'complete';
    return 'not_built';
  }

  return 'idle';
}

function getStageStats(stageId: StageKey, status: GraphEngineStatus | null): string {
  if (!status) return '';
  const s = status.stages[stageId];

  if (stageId === 'trace') {
    const t = s as GraphEngineStatus['stages']['trace'];
    return `${t.counts.nodes} nodes, ${t.counts.edges} edges`;
  }
  if (stageId === 'vector') {
    const v = s as GraphEngineStatus['stages']['vector'];
    return `${v.total_chunks} chunks`;
  }
  if (stageId === 'catalogue') {
    const c = s as GraphEngineStatus['stages']['catalogue'];
    return `${c.augmented_nodes}/${c.total_nodes} augmented`;
  }
  if (stageId === 'validation') {
    const v = s as GraphEngineStatus['stages']['validation'];
    return `${v.validated_edges} val, ${v.inferred_edges} inf`;
  }
  if (stageId === 'epistemic') {
    const e = s as GraphEngineStatus['stages']['epistemic'];
    return `${e.enriched_nodes} enriched`;
  }
  if (stageId === 'clustering') {
    const c = s as GraphEngineStatus['stages']['clustering'];
    return `${c.module_count} modules`;
  }
  if (stageId === 'knowledge') {
    const k = s as GraphEngineStatus['stages']['knowledge'];
    return `${k.chunks_embedded || (k as any).count || 0} chunks`;
  }
  return '';
}

export function GraphEnginePanel({
  status,
  config,
  onUpdateConfig,
  onRunStage,
  onRunAutoPilot,
  onStop,
  onDestroyGraph,
  className,
}: GraphEnginePanelProps) {
  
  const toggleStageAuto = (stageId: StageKey) => {
    if (!config) return;
    const newConfig = { ...config };
    // Init if missing
    if (!newConfig.stages) {
        newConfig.stages = {
            trace: { auto: true },
            vector: { auto: true },
            catalogue: { auto: true },
            validation: { auto: true },
            epistemic: { auto: false },
            clustering: { auto: false },
            knowledge: { auto: false },
        };
    }
    
    const current = newConfig.stages[stageId]?.auto ?? false;
    newConfig.stages = {
      ...newConfig.stages,
      [stageId]: { ...newConfig.stages[stageId], auto: !current }
    };
    
    // Waterfall logic: if turning OFF, turn off all subsequent stages?
    // User requested: "if any is set to manual the all the autos after it are automatically set to manual too"
    if (current) { // We are turning it OFF
       let found = false;
       for (const s of STAGES) {
           if (s.id === stageId) found = true;
           if (found && s.id !== stageId) {
               newConfig.stages[s.id].auto = false;
           }
       }
    }

    onUpdateConfig(newConfig);
  };

  const isAuto = (stageId: StageKey) => {
      return config?.stages?.[stageId]?.auto ?? STAGES.find(s => s.id === stageId)?.defaultAuto ?? false;
  };

  const globalRunning = status?.global_running ?? false;

  return (
    <div className={cn('flex flex-col h-full bg-surface border border-border rounded-lg shadow-sm', className)}>
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-border space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <Network className="w-4 h-4" />
            Knowledge Pipeline
            <InfoTooltip 
              content="The 7-stage engine that turns code into knowledge." 
              href="https://docs.codrag.io/concepts/pipeline" 
            />
          </h3>
          <div className="flex items-center gap-2">
             <span className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">
                {globalRunning ? 'Running' : 'Idle'}
             </span>
             {globalRunning && <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />}
          </div>
        </div>
      </div>

      {/* Stages List */}
      <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
        <div className="flex flex-col gap-1">
          {STAGES.map((stage, idx) => {
            const stState = getStageState(stage.id, status);
            const stStats = getStageStats(stage.id, status);
            const auto = isAuto(stage.id);
            const styles = STATE_STYLES[stState];

            return (
              <div key={stage.id} className="group relative flex items-start gap-3 py-1 px-2 rounded-md hover:bg-surface-raised/50 transition-colors">
                {/* Connector Line */}
                {idx < STAGES.length - 1 && (
                  <div className="absolute left-[19px] top-8 bottom-[-4px] w-px bg-border group-last:hidden" />
                )}

                {/* Icon Bubble */}
                <div className={cn(
                  "w-8 h-8 rounded-full border flex items-center justify-center shrink-0 z-10 transition-colors mt-0.5",
                  styles.bg, styles.border, styles.text
                )}>
                  <stage.icon className="w-4 h-4" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 py-0.5">
                  <div className="flex items-center justify-between">
                    <span className={cn("text-xs font-semibold", styles.text)}>{stage.label}</span>
                    <div className="flex items-center gap-2">
                        {/* Auto Toggle */}
                        <button 
                            onClick={() => toggleStageAuto(stage.id)}
                            className={cn(
                                "text-[9px] px-1.5 py-0.5 rounded border transition-colors",
                                auto 
                                  ? "bg-primary/10 border-primary/20 text-primary"
                                  : "bg-surface border-border text-text-muted hover:text-text"
                            )}
                            title={auto ? "Auto-run enabled" : "Manual run only"}
                        >
                            {auto ? "AUTO" : "MANUAL"}
                        </button>
                        <StateIcon state={stState} />
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                      <span className="text-[10px] text-text-muted truncate pr-2" title={stage.description}>
                          {stState === 'running' ? 'Processing...' : stStats || stage.description}
                      </span>
                      {stState !== 'running' && stState !== 'disabled' && (
                          <Button 
                            variant="ghost" 
                            size="icon-sm" 
                            className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => onRunStage(stage.id)}
                            title={`Run ${stage.label}`}
                          >
                              <Play className="w-3 h-3" />
                          </Button>
                      )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border bg-surface-raised/30">
        <div className="flex gap-2">
            <Button 
                variant={globalRunning ? "destructive" : "default"}
                size="sm" 
                className="flex-1"
                onClick={globalRunning ? onStop : onRunAutoPilot}
            >
                {globalRunning ? (
                    <>
                        <Power className="w-3.5 h-3.5 mr-1.5" />
                        Stop Engine
                    </>
                ) : (
                    <>
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Run Auto-Pilot
                    </>
                )}
            </Button>
            
            {onDestroyGraph && (
                <DestroyGraphAction onConfirm={onDestroyGraph} disabled={globalRunning} />
            )}
        </div>
      </div>
    </div>
  );
}

function DestroyGraphAction({ onConfirm, disabled }: { onConfirm: () => void; disabled: boolean }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <>
      <Button 
        variant="ghost" 
        size="icon-sm" 
        className="text-text-muted hover:text-destructive hover:bg-destructive/10"
        onClick={() => setConfirming(true)}
        disabled={disabled}
        title="Destroy Graph"
      >
        <Trash2 className="w-4 h-4" />
      </Button>
      <ConfirmDialog
        open={confirming}
        onConfirm={() => { setConfirming(false); onConfirm(); }}
        onCancel={() => setConfirming(false)}
        title="Destroy entire graph?"
        description="This permanently deletes the structural graph, all augmentations, epistemic enrichment, cluster modules, and deepening data. You will need to rebuild from scratch."
        confirmLabel="Yes, destroy"
      />
    </>
  );
}
