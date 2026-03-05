import { cn } from '../../lib/utils';
import {
  Code2, Database, Brain, Layers, Map, Network, Search, ShieldCheck, Zap, AlertTriangle, Cloud, CloudOff
} from 'lucide-react';
import type { CodragTaskId, LLMAssignmentBlock } from '../../types';
import { TASK_LABELS, TASK_TAGS, TASK_CLOUD_PREF } from '../../types';
import { getTaskTokenDescription, getTaskTokenVolume } from '../../lib/token-estimates';
import type { TokenVolume } from '../../lib/token-estimates';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface LLMAssignmentsPipelineProps {
  blocks: LLMAssignmentBlock[];
  fileCount?: number;
  className?: string;
}

interface TaskInfo {
  id: CodragTaskId;
  icon: React.ComponentType<{ className?: string }>;
}

const FAST_TASKS: TaskInfo[] = [
  { id: 'inferred_edges', icon: Code2 },
  { id: 'catalogue', icon: Database },
];

const DEEP_TASKS: TaskInfo[] = [
  { id: 'enrichment', icon: Brain },
  { id: 'group_reasoning', icon: Network },
  { id: 'clustering', icon: Layers },
  { id: 'atlas', icon: Map },
  { id: 'deepening', icon: Network },
];

const OTHER_TASKS: TaskInfo[] = [
  { id: 'search_intent', icon: Search },
  { id: 'audit', icon: ShieldCheck },
  { id: 'augmentation', icon: Zap },
];

function VolumeIndicator({ volume }: { volume: TokenVolume }) {
  const bars = [1, 2, 3, 4];
  const activeCount = volume === 'Low' ? 1 : volume === 'Medium' ? 2 : volume === 'High' ? 3 : 4;
  const activeColor = 
    volume === 'Low' ? 'bg-info' : 
    volume === 'Medium' ? 'bg-warning' : 
    volume === 'High' ? 'bg-orange-500' : 
    'bg-error';

  return (
    <div className="flex items-end gap-[2px] h-3.5 ml-2" title={`${volume} token volume`}>
      {bars.map((bar, i) => (
        <div 
          key={bar} 
          className={cn(
            "w-1 rounded-sm opacity-90", 
            i < activeCount ? activeColor : "bg-border",
            bar === 1 ? "h-1.5" : bar === 2 ? "h-2" : bar === 3 ? "h-2.5" : "h-3.5"
          )} 
        />
      ))}
    </div>
  );
}

export function LLMAssignmentsPipeline({ blocks, fileCount = 0, className }: LLMAssignmentsPipelineProps) {
  // Map taskId -> assigned model name
  const taskModelMap: Record<string, string> = {};
  for (const block of blocks) {
    for (const taskId of block.tasks) {
      if (block.model) {
        taskModelMap[taskId] = block.model;
      }
    }
  }

  const buildCloudTooltip = (taskId: CodragTaskId, pref: 'cloud-preferred' | 'local-preferred' | 'neutral') => {
    const volume = getTaskTokenVolume(taskId);
    const base = pref === 'cloud-preferred' ? 'Cloud model recommended' : pref === 'local-preferred' ? 'Local model recommended' : 'Cloud or Local model (neutral)';
    if (fileCount > 0) {
      const desc = getTaskTokenDescription(taskId, fileCount);
      return `${base}\n${volume} volume · ${desc}`;
    }
    return `${base} · ${volume} volume`;
  };

  const renderGroup = (title: string, tasks: TaskInfo[]) => {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2 py-1 px-1">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">{title}</span>
        </div>
        <div className="flex flex-col">
          {tasks.map((task, idx) => {
            const isAssigned = !!taskModelMap[task.id];
            const modelName = taskModelMap[task.id];
            const isLast = idx === tasks.length - 1;
            const pref = TASK_CLOUD_PREF[task.id];

            return (
              <div key={task.id} className="flex items-center gap-3 relative py-1 px-1 group">
                {/* Connector Line */}
                {!isLast && (
                  <div className="absolute left-[19px] top-6 bottom-[-4px] w-px bg-border" />
                )}
                
                {/* Icon Bubble */}
                <div className={cn(
                  "w-8 h-8 rounded-full border flex items-center justify-center shrink-0 z-10 transition-colors",
                  isAssigned
                    ? "bg-surface-raised border-border text-text"
                    : "bg-warning-muted/10 border-warning/30 text-warning"
                )}>
                  <task.icon className="w-4 h-4" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "text-xs font-semibold",
                      isAssigned ? "text-text" : "text-warning"
                    )}>
                      {TASK_LABELS[task.id]}
                    </span>
                    {!isAssigned && (
                      <span title="Unassigned task" className="flex items-center">
                        <AlertTriangle className="w-3.5 h-3.5 text-warning shrink-0" />
                      </span>
                    )}
                    {TASK_TAGS[task.id] && (
                      <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-surface-raised border border-border">
                        {TASK_TAGS[task.id]}
                      </span>
                    )}
                    {isAssigned && (
                      <span className="text-[10px] text-text-muted px-1.5 py-0.5 rounded bg-surface-raised border border-border ml-1">
                        {modelName}
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-1.5 shrink-0">
                    <VolumeIndicator volume={getTaskTokenVolume(task.id)} />
                    {pref === 'cloud-preferred' && (
                      <span title={buildCloudTooltip(task.id, 'cloud-preferred')}><Cloud className="w-4 h-4 text-info opacity-70" /></span>
                    )}
                    {pref === 'local-preferred' && (
                      <span title={buildCloudTooltip(task.id, 'local-preferred')}><CloudOff className="w-4 h-4 text-text-muted opacity-50" /></span>
                    )}
                    {pref === 'neutral' && (
                      <span title={buildCloudTooltip(task.id, 'neutral')}><Cloud className="w-4 h-4 text-text-muted opacity-30" /></span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={cn("p-4 bg-surface rounded-lg border border-border", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text">Assignments</h3>
        <InfoTooltip 
          content={
            <div className="space-y-2">
              <p><strong>Cloud vs Local Recommendations:</strong></p>
              <ul className="list-disc pl-4 space-y-1">
                <li><Cloud className="w-3 h-3 inline mr-1 text-info" /> <strong>Cloud Preferred:</strong> High-reasoning tasks run infrequently. Best handled by large models like Claude or GPT-4o.</li>
                <li><CloudOff className="w-3 h-3 inline mr-1 text-text-muted" /> <strong>Local Preferred:</strong> High-volume, privacy-sensitive tasks that run often during fast sync. Best handled locally to save costs and reduce latency.</li>
                <li><Cloud className="w-3 h-3 inline mr-1 text-text-muted opacity-50" /> <strong>Neutral:</strong> Can be run either locally or in the cloud depending on your setup.</li>
              </ul>
            </div>
          }
        />
      </div>
      <div className="flex flex-col gap-6">
        {renderGroup('Fast Sync', FAST_TASKS)}
        {renderGroup('Deep Enrichment', DEEP_TASKS)}
        {renderGroup('Operations & Search', OTHER_TASKS)}
      </div>
    </div>
  );
}
