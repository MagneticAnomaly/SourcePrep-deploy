import { cn } from '../../lib/utils';
import type { TaskProgress } from '../../types';

export interface ProgressIndicatorProps {
  progress?: TaskProgress;
  className?: string;
  showStatus?: boolean;
}

export function ProgressIndicator({
  progress,
  className,
  showStatus = true,
}: ProgressIndicatorProps) {
  if (!progress) return null;

  const isComplete = progress.status === 'completed';
  const isFailed = progress.status === 'failed';
  
  return (
    <div className={cn("w-full space-y-1.5", className)}>
      <div className="h-1.5 w-full bg-surface-raised rounded-full overflow-hidden flex">
        <div 
          className={cn(
            "h-full rounded-full transition-all duration-300 ease-out",
            isComplete ? "bg-success" : isFailed ? "bg-error" : "bg-primary animate-pulse"
          )}
          style={{ width: `${Math.max(5, progress.percent)}%` }} 
        />
      </div>
      {showStatus && (
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-text-muted truncate max-w-[200px]" title={progress.message}>
            {progress.message}
          </span>
          <span className="text-text-subtle font-mono shrink-0">
            {progress.total > 0
              ? `${progress.percent}% (${progress.current}/${progress.total})`
              : progress.message === 'Starting build...' ? '' : `${progress.current} processed`}
          </span>
        </div>
      )}
    </div>
  );
}
