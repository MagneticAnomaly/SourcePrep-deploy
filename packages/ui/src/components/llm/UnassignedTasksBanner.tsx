import { cn } from '../../lib/utils';
import { AlertTriangle } from 'lucide-react';
import type { CodragTaskId } from '../../types';
import { ALL_TASK_IDS, TASK_LABELS } from '../../types';

export interface UnassignedTasksBannerProps {
  assignedTasks: CodragTaskId[];
  onTaskClick?: (taskId: CodragTaskId) => void;
  className?: string;
}

export function UnassignedTasksBanner({
  assignedTasks,
  onTaskClick,
  className,
}: UnassignedTasksBannerProps) {
  const unassigned = ALL_TASK_IDS.filter((t) => !assignedTasks.includes(t));

  if (unassigned.length === 0) return null;

  return (
    <div
      className={cn(
        'rounded-lg border border-warning/40 bg-warning-muted/10 p-4',
        className,
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-warning shrink-0" />
        <span className="text-sm font-semibold text-warning">
          {unassigned.length} task{unassigned.length !== 1 ? 's' : ''} unassigned
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {unassigned.map((taskId) => (
          <button
            key={taskId}
            onClick={() => onTaskClick?.(taskId)}
            className={cn(
              'text-xs px-2 py-1 rounded-md border border-warning/30 bg-warning-muted/10',
              'text-warning hover:bg-warning-muted/20 transition-colors',
              onTaskClick ? 'cursor-pointer' : 'cursor-default',
            )}
          >
            {TASK_LABELS[taskId]}
          </button>
        ))}
      </div>
      <p className="text-xs text-text-muted">
        Pipeline stages with unassigned tasks will be skipped during execution.
      </p>
    </div>
  );
}
