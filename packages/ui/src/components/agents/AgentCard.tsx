/**
 * AgentCard — Compact card showing one agent's status.
 *
 * Displays: agent name, status badge, key metric, last run time.
 * Used in AgentOpsPanel to show all three agents in a grid.
 */
import type { ReactNode } from 'react';
import { StatusBadge } from '../status/StatusBadge';

export interface AgentCardProps {
  name: string;
  description: string;
  icon: ReactNode;
  status: 'fresh' | 'stale' | 'building' | 'pending' | 'error' | 'disabled';
  metric: string;
  metricLabel: string;
  lastRun?: string | null;
  onAction?: () => void;
  actionLabel?: string;
  className?: string;
}

export function AgentCard({
  name,
  description,
  icon,
  status,
  metric,
  metricLabel,
  lastRun,
  onAction,
  actionLabel,
  className = '',
}: AgentCardProps) {
  return (
    <div className={`rounded-lg border border-border bg-surface p-4 ${className}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">{icon}</span>
          <h3 className="font-medium text-sm">{name}</h3>
        </div>
        <StatusBadge status={status} />
      </div>
      <p className="text-xs text-muted-foreground mb-3">{description}</p>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-bold">{metric}</div>
          <div className="text-xs text-muted-foreground">{metricLabel}</div>
        </div>
        <div className="text-right">
          {lastRun && (
            <div className="text-xs text-muted-foreground mb-1">
              Last: {lastRun.slice(0, 10)}
            </div>
          )}
          {onAction && actionLabel && (
            <button
              onClick={onAction}
              className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
            >
              {actionLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
