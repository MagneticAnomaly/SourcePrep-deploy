/**
 * GitHubStatusBadge — Shows GitHub connection state in the RoadmapPanel header.
 *
 * Displays:
 *   - Connected (green) with repo name
 *   - Disconnected (gray) with "Configure" prompt
 *   - Syncing (amber pulse) during active sync
 *   - Error (red) with error message on hover
 */
import { GitBranch, AlertCircle, Loader2, ExternalLink } from 'lucide-react';

export interface GitHubStatusBadgeProps {
  configured: boolean;
  owner?: string;
  repo?: string;
  syncing?: boolean;
  error?: string | null;
  lastSync?: string | null;
  onSync?: () => void;
  className?: string;
}

export function GitHubStatusBadge({
  configured,
  owner,
  repo,
  syncing,
  error,
  lastSync,
  onSync,
  className,
}: GitHubStatusBadgeProps) {
  if (!configured) {
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface/50 border border-border/30 text-xs text-muted-foreground ${className || ''}`}>
        <GitBranch className="w-3 h-3 opacity-50" />
        <span>GitHub not configured</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-400 cursor-help ${className || ''}`}
        title={error}
      >
        <AlertCircle className="w-3 h-3" />
        <span>Sync error</span>
      </div>
    );
  }

  if (syncing) {
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-xs text-amber-400 ${className || ''}`}>
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Syncing…</span>
      </div>
    );
  }

  const repoLabel = owner && repo ? `${owner}/${repo}` : 'Connected';

  return (
    <button
      onClick={onSync}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 hover:bg-emerald-500/20 transition-colors cursor-pointer ${className || ''}`}
      title={lastSync ? `Last sync: ${new Date(lastSync).toLocaleString()}` : 'Click to sync'}
    >
      <GitBranch className="w-3 h-3" />
      <span>{repoLabel}</span>
      <ExternalLink className="w-2.5 h-2.5 opacity-60" />
    </button>
  );
}
