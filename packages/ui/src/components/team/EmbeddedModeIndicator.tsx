import { cn } from '../../lib/utils';
import { HardDrive, GitBranch, AlertTriangle, CheckCircle, Folder, RefreshCw } from 'lucide-react';
import { Button } from '../primitives/Button';

export interface EmbeddedModeIndicatorProps {
  isEmbedded: boolean;
  indexExists: boolean;
  hasConflicts?: boolean;
  isCommitted?: boolean;
  onRebuild?: () => void;
  className?: string;
}

export function EmbeddedModeIndicator({
  isEmbedded,
  indexExists,
  hasConflicts = false,
  isCommitted,
  onRebuild,
  className,
}: EmbeddedModeIndicatorProps) {
  if (!isEmbedded) {
    return (
      <div className={cn('flex items-center gap-2 text-sm', className)}>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-raised text-text-muted border border-border">
          <HardDrive className="w-3.5 h-3.5" />
          Standalone Mode
        </span>
        <span className="text-xs text-text-subtle">
          Index in app data
        </span>
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-info-muted/10 text-info border border-info-muted/20">
          <Folder className="w-3.5 h-3.5" />
          Embedded Mode
        </span>
        
        {indexExists ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-muted/10 text-success border border-success-muted/20">
            <CheckCircle className="w-3.5 h-3.5" />
            Index Ready
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-muted/10 text-warning border border-warning-muted/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            Not Built
          </span>
        )}
        
        {isCommitted !== undefined && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-raised text-text-muted border border-border">
            <GitBranch className="w-3.5 h-3.5" />
            {isCommitted ? 'Committed' : 'Gitignored'}
          </span>
        )}
      </div>
      
      <p className="text-xs text-text-muted">
        Index stored in <code className="bg-surface-raised px-1 py-0.5 rounded border border-border text-text font-mono">.prep/</code> directory
      </p>
      
      {hasConflicts && (
        <div className="rounded-md bg-error-muted/10 p-3 border border-error-muted/20">
          <div className="flex gap-2">
            <AlertTriangle className="w-4 h-4 text-error shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-error mb-1">Merge Conflicts Detected</p>
              <p className="text-error/90 text-xs mb-2">The embedded index has git merge conflicts and is invalid.</p>
              {onRebuild && (
                <Button 
                  onClick={onRebuild}
                  variant="destructive"
                  size="sm"
                  icon={RefreshCw}
                >
                  Rebuild Index
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {!indexExists && !hasConflicts && (
        <div className="rounded-md bg-warning-muted/10 p-3 border border-warning-muted/20">
          <div className="flex gap-2">
            <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-warning mb-1">Index Not Built</p>
              <p className="text-warning/90 text-xs mb-2">Build the index to enable search.</p>
              {onRebuild && (
                <Button 
                  onClick={onRebuild}
                  variant="outline"
                  size="sm"
                  icon={RefreshCw}
                  className="border-warning/20 text-warning hover:bg-warning-muted/10 hover:text-warning"
                >
                  Build Index
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
