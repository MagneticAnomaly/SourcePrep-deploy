import { useState, useRef, useEffect } from 'react';
import { Cloud, CloudOff, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { SyncStatus } from '../../types';
import { createPortal } from 'react-dom';

export interface TeamSyncIndicatorProps {
  status?: SyncStatus;
  className?: string;
}

export function TeamSyncIndicator({ status, className }: TeamSyncIndicatorProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setCoords({
      top: rect.bottom + 8,
      left: rect.left + rect.width / 2,
    });
  };

  useEffect(() => {
    if (!isVisible) return;
    const handleScroll = () => setIsVisible(false);
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleScroll);
    return () => {
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleScroll);
    };
  }, [isVisible]);

  if (!status || !status.enabled) {
    return null;
  }

  let icon = <Cloud className="w-4 h-4 text-text-muted" />;
  let label = 'Remote Sync Enabled';
  let colorClass = 'text-text-muted bg-surface-raised border-border';
  let tooltipText = 'Team remote sync is enabled but no status is available yet.';

  if (status.is_syncing) {
    icon = <RefreshCw className="w-4 h-4 animate-spin text-primary" />;
    label = 'Syncing...';
    colorClass = 'text-primary bg-primary/10 border-primary/20';
    tooltipText = 'Downloading latest index from team S3 bucket...';
  } else if (status.error) {
    icon = <CloudOff className="w-4 h-4 text-error" />;
    label = 'Sync Error';
    colorClass = 'text-error bg-error/10 border-error/20';
    tooltipText = status.error;
  } else if (status.behind_minutes !== null && status.behind_minutes > 0) {
    icon = <AlertCircle className="w-4 h-4 text-warning" />;
    label = 'Remote Ahead';
    colorClass = 'text-warning bg-warning/10 border-warning/20';
    const mins = Math.round(status.behind_minutes);
    tooltipText = `A newer index is available (${mins} min ahead). It will be downloaded on the next poll.`;
  } else if (status.last_sync_at) {
    icon = <CheckCircle2 className="w-4 h-4 text-success" />;
    label = 'Synced';
    colorClass = 'text-success bg-success/10 border-success/20';
    const commit = status.last_sync_commit ? status.last_sync_commit.slice(0, 8) : 'unknown';
    tooltipText = `Up to date with team index (commit: ${commit}).`;
  }

  return (
    <>
      <div 
        ref={triggerRef}
        onMouseEnter={() => { updatePosition(); setIsVisible(true); }}
        onMouseLeave={() => setIsVisible(false)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border cursor-default transition-colors",
          colorClass,
          className
        )}
      >
        {icon}
        <span>{label}</span>
      </div>

      {isVisible && typeof document !== 'undefined' && createPortal(
        <div
          className={cn(
            "fixed z-50 overflow-hidden rounded-md border border-border bg-surface-raised px-3 py-1.5 text-xs text-text shadow-md animate-in fade-in-0 zoom-in-95",
            "max-w-xs leading-relaxed pointer-events-none"
          )}
          style={{
            top: coords.top,
            left: coords.left,
            transform: 'translate(-50%, 0)'
          }}
        >
          {tooltipText}
        </div>,
        document.body
      )}
    </>
  );
}
