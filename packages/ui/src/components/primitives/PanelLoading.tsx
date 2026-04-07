import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

export function PanelLoading({ className, message = 'Loading...' }: { className?: string; message?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-12 px-4", className)}>
      <Loader2 className="w-6 h-6 text-text-muted/40 animate-spin" />
      <p className="text-xs text-text-muted">{message}</p>
    </div>
  );
}
