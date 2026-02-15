import { cn } from '../../lib/utils';

export interface StageProgressBarProps {
  progress: number; // 0 to 100
  className?: string;
  color?: string; // Tailwind text color class for the bar (e.g. "bg-blue-500")
}

export function StageProgressBar({ 
  progress, 
  className,
  color = "bg-blue-500" 
}: StageProgressBarProps) {
  // Clamp progress between 0 and 100
  const clamped = Math.min(100, Math.max(0, progress));
  
  return (
    <div className={cn("h-1 w-full bg-surface-raised rounded-full overflow-hidden mt-1.5", className)}>
      <div 
        className={cn("h-full transition-all duration-500 ease-out", color)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
