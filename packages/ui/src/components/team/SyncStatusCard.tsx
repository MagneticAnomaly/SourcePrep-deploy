import { cn } from '../../lib/utils';
import type { SyncStatus } from '../../types';
import { Cloud, CloudOff, RefreshCw, AlertCircle, CheckCircle2, Clock, GitCommit } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface SyncStatusCardProps {
  status: SyncStatus;
  onSyncNow?: () => void;
  className?: string;
}

export function SyncStatusCard({
  status,
  onSyncNow,
  className,
}: SyncStatusCardProps) {
  if (!status.enabled) {
    return null;
  }

  let icon = <Cloud className="w-5 h-5 text-text-muted" />;
  let title = 'Remote Sync';
  let description = 'Team index sync is enabled but no status is available.';
  let stateColor = 'text-text-muted bg-surface-raised';

  if (status.is_syncing) {
    icon = <RefreshCw className="w-5 h-5 animate-spin text-primary" />;
    title = 'Syncing...';
    description = 'Downloading latest index from team S3 bucket.';
    stateColor = 'text-primary bg-primary/10';
  } else if (status.error) {
    icon = <CloudOff className="w-5 h-5 text-error" />;
    title = 'Sync Error';
    description = status.error;
    stateColor = 'text-error bg-error/10';
  } else if (status.behind_minutes !== null && status.behind_minutes > 0) {
    icon = <AlertCircle className="w-5 h-5 text-warning" />;
    title = 'Remote Index Ahead';
    const mins = Math.round(status.behind_minutes);
    const hours = Math.floor(mins / 60);
    const timeStr = hours > 0 ? `${hours} hr ${mins % 60} min` : `${mins} min`;
    description = `A newer index is available (${timeStr} ahead).`;
    stateColor = 'text-warning bg-warning/10';
  } else if (status.last_sync_at) {
    icon = <CheckCircle2 className="w-5 h-5 text-success" />;
    title = 'Up to Date';
    description = 'Your local index is synchronized with the team index.';
    stateColor = 'text-success bg-success/10';
  }

  const formatTime = (epoch: number | null) => {
    if (!epoch) return 'Never';
    return new Date(epoch * 1000).toLocaleString();
  };

  return (
    <div className={cn('p-4 border border-border rounded-lg bg-surface flex flex-col gap-4', className)}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={cn("p-2 rounded-md", stateColor)}>
            {icon}
          </div>
          <div>
            <h3 className="text-sm font-medium text-text flex items-center gap-2">
              {title}
              <InfoTooltip content="Team Sync automatically downloads pre-built trace graphs from your team's S3 bucket, saving local compute time." />
            </h3>
            <p className="text-xs text-text-muted mt-1">{description}</p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onSyncNow}
          disabled={status.is_syncing}
          className="shrink-0"
        >
          <RefreshCw className={cn("w-3.5 h-3.5 mr-2", status.is_syncing && "animate-spin")} />
          Sync Now
        </Button>
      </div>

      {(status.last_sync_at || status.remote_timestamp) && (
        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-border/50">
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
              <Clock className="w-3.5 h-3.5" />
              Last Synced
            </div>
            <div className="text-xs text-text">
              {formatTime(status.last_sync_at)}
            </div>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
              <GitCommit className="w-3.5 h-3.5" />
              Remote Commit
            </div>
            <div className="text-xs text-text font-mono">
              {status.last_sync_commit ? status.last_sync_commit.slice(0, 8) : 'unknown'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
