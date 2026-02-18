import { cn } from '../../lib/utils';

export interface StageProgressBarProps {
  progress?: number; // 0 to 100, undefined = indeterminate
  className?: string;
  color?: string; // Tailwind bg color class for the bar (e.g. "bg-blue-500")
}

export function StageProgressBar({ 
  progress, 
  className,
  color = "bg-blue-500" 
}: StageProgressBarProps) {
  // Default to 0% when no progress data yet — avoids a ~40% flash
  // from the old indeterminate animation before real data arrives.
  const clamped = progress !== undefined ? Math.min(100, Math.max(0, progress)) : 0;
  
  return (
    <div className={cn("h-1 w-full bg-surface-raised rounded-full overflow-hidden mt-1.5", className)}>
      <div 
        className={cn("h-full transition-all duration-500 ease-out", color)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
