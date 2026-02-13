import { cn } from '../../lib/utils';
import type { TeamConfigStatus as TeamConfigStatusType, TeamConfig } from '../../types';
import { Users, FileText, AlertTriangle, RefreshCw, Eye, AlertCircle } from 'lucide-react';
import { Button } from '../primitives/Button';

export interface TeamConfigStatusProps {
  status: TeamConfigStatusType;
  config?: TeamConfig;
  onViewConfig?: () => void;
  onReapply?: () => void;
  className?: string;
}

const statusConfig: Record<TeamConfigStatusType, { label: string; color: string; icon: any }> = {
  none: { 
    label: 'No Team Config', 
    color: 'bg-surface-raised text-text-muted border-border',
    icon: FileText
  },
  applied: { 
    label: 'Team Config Applied', 
    color: 'bg-success-muted/10 text-success border-success-muted/20',
    icon: Users
  },
  overridden: { 
    label: 'Local Overrides', 
    color: 'bg-warning-muted/10 text-warning border-warning-muted/20',
    icon: AlertTriangle
  },
  conflict: { 
    label: 'Config Conflict', 
    color: 'bg-error-muted/10 text-error border-error-muted/20',
    icon: AlertCircle
  },
};

export function TeamConfigStatus({
  status,
  config,
  onViewConfig,
  onReapply,
  className,
}: TeamConfigStatusProps) {
  const { label, color, icon: Icon } = statusConfig[status];
  
  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border", color)}>
          <Icon className="w-3.5 h-3.5" />
          {label}
        </span>
        
        {status !== 'none' && onViewConfig && (
          <Button 
            onClick={onViewConfig}
            variant="ghost"
            size="sm"
            icon={Eye}
            className="h-auto py-1 px-2 text-xs"
          >
            View Config
          </Button>
        )}
      </div>
      
      {status === 'overridden' && (
        <div className="rounded-md bg-warning-muted/10 p-3 border border-warning-muted/20">
          <p className="text-sm font-medium text-warning mb-1">Local Settings Differ</p>
          <p className="text-xs text-warning/90 mb-2">
            Your local project settings differ from the team configuration.
          </p>
          {onReapply && (
            <Button 
              onClick={onReapply}
              variant="outline"
              size="sm"
              icon={RefreshCw}
              className="border-warning/20 text-warning hover:bg-warning-muted/10 hover:text-warning"
            >
              Re-apply Team Config
            </Button>
          )}
        </div>
      )}
      
      {status === 'conflict' && (
        <div className="rounded-md bg-error-muted/10 p-3 border border-error-muted/20">
          <p className="text-sm font-medium text-error mb-1">Configuration Conflict</p>
          <p className="text-xs text-error/90">
            The team configuration file has conflicts. Please resolve them manually.
          </p>
        </div>
      )}
      
      {status === 'applied' && config && (
        <div className="text-xs text-text-muted space-y-1.5 bg-surface-raised p-3 rounded-md border border-border">
          <div className="flex justify-between">
            <span className="text-text-subtle">Embedding model:</span>
            <code className="bg-surface px-1 rounded border border-border text-text font-mono">{config.embedding_model}</code>
          </div>
          <div className="flex justify-between">
            <span className="text-text-subtle">Code Graph enabled:</span>
            <span className="font-medium text-text">{config.trace_enabled ? 'Yes' : 'No'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-subtle">Include patterns:</span>
            <span className="font-medium text-text">{config.include_globs.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-subtle">Exclude patterns:</span>
            <span className="font-medium text-text">{config.exclude_globs.length}</span>
          </div>
        </div>
      )}
    </div>
  );
}
