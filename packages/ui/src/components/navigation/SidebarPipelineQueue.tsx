import { useState, useEffect, useCallback, useRef } from 'react';
import { cn } from '../../lib/utils';
import {
  ChevronDown,
  ChevronRight,
  Pause,
  Play,
  X,
  Star,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { StatusBadge } from '../status/StatusBadge';
import type { StatusState } from '../../types';

// ── Types ─────────────────────────────────────────────────────────

export interface QueueItem {
  project_id: string;
  project_name: string;
  group: string;
  phase: string;
  current_stage: string | null;
  started_at: number | null;
  elapsed_seconds: number | null;
  wait_seconds: number | null;
  priority: string;
  compute_node: string | null;
  concurrent_workers: number;
  is_swarm?: boolean;
}

interface QueueResponse {
  queue: QueueItem[];
  nodes: Record<string, { max_concurrent: number; current_load: number }>;
  ghost_locks_purged: number;
}

export interface SidebarPipelineQueueProps {
  baseUrl: string;
  /** Monotonic counter from useEventStream's queueVersion — triggers immediate re-fetch on change */
  queueVersion?: number;
  onPause?: (projectId: string, group: string) => void;
  onResume?: (projectId: string, group: string) => void;
  onCancel?: (projectId: string, group: string) => void;
  onPriorityChange?: (projectId: string, level: string) => void;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return '0s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function phaseToStatus(phase: string): StatusState {
  switch (phase) {
    case 'running': return 'building';
    case 'queued': return 'pending';
    case 'paused': return 'stale';
    case 'failed': return 'error';
    default: return 'pending';
  }
}

function groupLabel(group: string): string {
  switch (group) {
    case 'fast_sync': return 'Fast Sync';
    case 'deep_enrichment': return 'Deep Enrich';
    default: return group;
  }
}

// ── Component ─────────────────────────────────────────────────────

export function SidebarPipelineQueue({
  baseUrl,
  queueVersion,
  onPause,
  onResume,
  onCancel,
  onPriorityChange,
  className,
}: SidebarPipelineQueueProps) {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [collapsed, setCollapsed] = useState(() => {
    const saved = typeof window !== 'undefined'
      ? localStorage.getItem('codrag_queue_collapsed')
      : null;
    return saved === 'true';
  });
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const mountedRef = useRef(true);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch(`${baseUrl}/system/pipeline-queue`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) return;
      const json = await res.json();
      if (mountedRef.current) {
        const data: QueueResponse = json.data ?? json;
        setQueue(data.queue ?? []);
      }
    } catch {
      // Silently fail — daemon may be down
    }
  }, [baseUrl]);

  // Poll every 5s
  useEffect(() => {
    mountedRef.current = true;
    fetchQueue();
    pollRef.current = setInterval(fetchQueue, 5000);
    return () => {
      mountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchQueue]);

  // Immediate re-fetch when parent's SSE stream sees queue_changed
  useEffect(() => {
    if (queueVersion && queueVersion > 0) {
      fetchQueue();
    }
  }, [queueVersion, fetchQueue]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('codrag_queue_collapsed', String(next));
      return next;
    });
  }, []);

  const handlePause = useCallback(async (item: QueueItem) => {
    if (onPause) {
      onPause(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onPause, fetchQueue]);

  const handleResume = useCallback(async (item: QueueItem) => {
    if (onResume) {
      onResume(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onResume, fetchQueue]);

  const handleCancel = useCallback(async (item: QueueItem) => {
    if (onCancel) {
      onCancel(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onCancel, fetchQueue]);

  const handlePriority = useCallback(async (item: QueueItem) => {
    const nextLevel = item.priority === 'none' ? 'boost'
      : item.priority === 'boost' ? 'exclusive'
      : 'none';
    if (onPriorityChange) {
      onPriorityChange(item.project_id, nextLevel);
    } else {
      await fetch(`${baseUrl}/system/pipeline-queue/priority`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: item.project_id, level: nextLevel }),
      });
      fetchQueue();
    }
  }, [baseUrl, onPriorityChange, fetchQueue]);

  return (
    <div className={cn('px-2 py-2', className)}>
      <button
        onClick={toggleCollapsed}
        className="flex items-center justify-between w-full px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text transition-colors"
      >
        <span className="flex items-center gap-1.5">
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          Pipeline Queue
        </span>
        {queue.length > 0 && (
          <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold rounded-full bg-primary/15 text-primary">
            {queue.length}
          </span>
        )}
      </button>

      {!collapsed && (
        <div className="mt-1 space-y-1">
          {queue.length === 0 ? (
            <p className="px-2 py-2 text-xs text-text-muted italic">
              No active pipelines
            </p>
          ) : (
            queue.map((item) => (
              <div
                key={`${item.project_id}-${item.group}`}
                className="px-2 py-1.5 rounded-md bg-surface-raised/50 border border-border/50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-text truncate max-w-[140px]" title={item.project_name}>
                    {item.priority !== 'none' && (
                      <Star
                        className={cn(
                          'inline w-3 h-3 mr-1 -mt-0.5',
                          item.priority === 'exclusive' ? 'text-red-500 fill-red-500' : 'text-amber-500 fill-amber-500',
                        )}
                      />
                    )}
                    {item.project_name}
                  </span>
                  <StatusBadge
                    status={phaseToStatus(item.phase)}
                    labelOverride={item.phase === 'running' && item.is_swarm ? 'Swarming' : undefined}
                  />
                </div>

                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-[10px] text-text-muted">
                    {groupLabel(item.group)}
                    {item.current_stage && ` · ${item.current_stage}`}
                  </span>
                  <span className="text-[10px] text-text-muted tabular-nums">
                    {item.phase === 'running' && item.elapsed_seconds != null
                      ? formatDuration(item.elapsed_seconds)
                      : item.phase === 'queued' && item.wait_seconds != null
                        ? `waiting ${formatDuration(item.wait_seconds)}`
                        : ''}
                  </span>
                </div>

                <div className="flex items-center gap-0.5 mt-1">
                  {item.phase === 'running' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handlePause(item)}
                      className="h-5 w-5 text-text-muted hover:text-text"
                      title="Pause"
                    >
                      <Pause className="w-3 h-3" />
                    </Button>
                  )}
                  {item.phase === 'paused' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleResume(item)}
                      className="h-5 w-5 text-text-muted hover:text-green-500"
                      title="Resume"
                    >
                      <Play className="w-3 h-3" />
                    </Button>
                  )}

                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handlePriority(item)}
                    className={cn(
                      'h-5 w-5',
                      item.priority !== 'none' ? 'text-amber-500' : 'text-text-muted hover:text-amber-500',
                    )}
                    title={`Priority: ${item.priority} (click to cycle)`}
                  >
                    <Star className={cn('w-3 h-3', item.priority !== 'none' && 'fill-current')} />
                  </Button>

                  {item.phase !== 'failed' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleCancel(item)}
                      className="h-5 w-5 text-text-muted hover:text-red-500 ml-auto"
                      title="Cancel"
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
