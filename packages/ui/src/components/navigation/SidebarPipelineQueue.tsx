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
import { useCancelToast } from '../../hooks/useCancelToast';

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
  nodes: Record<string, {
    max_concurrent: number;
    current_load: number;
    in_flight_requests: number;
    current_limit: number;
    // Phase 136 Part 15: ``dynamic_capacity`` is the slot's effective
    // ceiling.  Equals ``max_concurrent`` for no-auto-detect cloud
    // providers (Ollama Cloud, Gemini, Moonshot) and equals
    // ``current_limit`` for header-rich providers (OpenAI, Anthropic)
    // in Auto mode.  Older daemons omit it — fall back to current_limit.
    dynamic_capacity?: number;
    // Phase 119 — optional fields exposed by the latency-aware concurrency
    // manager. Older daemons omit them, so consumers must degrade gracefully.
    discovered_ceiling?: number | null;
    locked_until?: number | null;
    aimd_mode?: string | null;
    state?: 'probing' | 'locked' | 'backing_off' | 'recovering';
  }>;
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
  // F-83: 'paused' used to map to 'stale' which read as "dead" and
  // confused users into dismissing actively-resumable runs. A paused
  // pipeline is explicitly restartable — label it as such.
  switch (phase) {
    case 'running': return 'building';
    case 'queued': return 'pending';
    case 'pausing':
    case 'paused': return 'paused';
    case 'cancelled': return 'cancelled';
    case 'failed': return 'error';
    default: return 'pending';
  }
}

function groupLabel(group: string): string {
  switch (group) {
    case 'fast_sync': return 'Fast Sync';
    case 'deep_enrichment': return 'Deep Enrichment';
    case 'finalize': return 'Finalize';
    // Build threads tracked by ProgressManager (the queue is the single
    // source of truth — these have to render with friendly names).
    case 'index_build': return 'Code Index Build';
    case 'trace_build': return 'Trace Build';
    case 'knowledge_build': return 'Knowledge Build';
    case 'delta_build': return 'Delta Build';
    default: return group;
  }
}

// Mirrors the stage labels rendered in GraphEnrichmentPipeline so the queue
// entry and the pipeline panel always agree on the human-readable name.
// Keep in sync with the stage config blocks in
// packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx.
const STAGE_LABELS: Record<string, string> = {
  // Fast Sync
  structural: 'Structural Graph',
  inferred_edges: 'Edge Discovery',
  catalogue: 'Fast Catalogue',
  validation: 'Relationship Validation',
  knowledge: 'Knowledge Embedding',
  // Deep Enrichment
  enrichment: 'Deep Reasoning',
  group_reasoning: 'Group Reasoning',
  clustering: 'Module Synthesis',
  deepening: 'Continuous Deepening',
  deep_knowledge: 'Deep Knowledge Embedding',
  // Finalize
  atlas: 'Atlas Building',
  rules: 'Rules Generation',
  concepts: 'Concept Seeding',
  audit: 'Structural Audit',
  antibodies: 'Immune System',
};

function stageLabel(stageId: string | null | undefined): string | null {
  if (!stageId) return null;
  return STAGE_LABELS[stageId] ?? stageId;
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
  const [nodes, setNodes] = useState<QueueResponse['nodes']>({});
  const [collapsed, setCollapsed] = useState(() => {
    const saved = typeof window !== 'undefined'
      ? localStorage.getItem('prep_queue_collapsed')
      : null;
    return saved === 'true';
  });
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const mountedRef = useRef(true);

  const inFlightRef = useRef(false);
  const fetchQueue = useCallback(async () => {
    // F-11: in-flight guard prevents request stacking when daemon is busy
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const res = await fetch(`${baseUrl}/system/pipeline-queue`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) return;
      const json = await res.json();
      if (mountedRef.current) {
        const data: QueueResponse = json.data ?? json;
        setQueue(data.queue ?? []);
        setNodes(data.nodes ?? {});
      }
    } catch {
      // Silently fail — daemon may be down
    } finally {
      inFlightRef.current = false;
    }
  }, [baseUrl]);

  // F-11: bumped 5s -> 10s and added document.hidden pause.
  // SSE queue_changed events still trigger immediate re-fetch
  // (via the queueVersion effect below) so latency stays low.
  useEffect(() => {
    mountedRef.current = true;
    fetchQueue();
    const tick = () => {
      if (!document.hidden) fetchQueue();
    };
    pollRef.current = setInterval(tick, 10000);
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
      localStorage.setItem('prep_queue_collapsed', String(next));
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

  const cancelWithToast = useCancelToast({
    sendCancel: async (projectId, group, reason) => {
      const r = await fetch(`${baseUrl}/projects/${projectId}/pipeline/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group, reason }),
      });
      return r.ok || r.status === 409;
    },
    resolveAutoMode: async (projectId) => {
      const r = await fetch(`${baseUrl}/projects/${projectId}`);
      const j = await r.json();
      const cfg = j?.data?.project?.config ?? {};
      const auto = cfg.auto_config ?? {};
      return auto.deepEnrichment ?? auto.deep_enrichment ?? 'manual';
    },
    switchToManual: async (projectId) => {
      await fetch(`${baseUrl}/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: { auto_config: { deepEnrichment: 'manual' } },
        }),
      });
    },
    projectName: (projectId) => {
      const item = queue.find((q) => q.project_id === projectId);
      return item?.project_name ?? projectId.slice(0, 8);
    },
  });

  const handleCancel = useCallback(
    async (item: QueueItem) => {
      if (onCancel) {
        onCancel(item.project_id, item.group);
        await fetchQueue();
        return;
      }
      await cancelWithToast(item.project_id, item.group);
      await fetchQueue();
    },
    [onCancel, cancelWithToast, fetchQueue],
  );

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
    <div className={cn('px-3 py-2', className)}>
      <button
        onClick={toggleCollapsed}
        className="flex items-center justify-between w-full text-xs font-semibold text-text-muted hover:text-text transition-colors"
      >
        <span className="flex items-center gap-1.5">
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          Queue
        </span>
        {queue.length > 0 && (
          <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold rounded-full bg-primary/15 text-primary">
            {queue.length}
          </span>
        )}
      </button>

      {!collapsed && (
        <div className="mt-1 space-y-1">
          {Object.entries(nodes).length > 0 && (
            <div className="px-2 py-1 space-y-0.5">
              {Object.entries(nodes).map(([nid, n]) => {
                const ceiling = n.discovered_ceiling ?? null;
                const state = n.state ?? "probing";
                // Primary number's denominator:
                //   - locked: discovered_ceiling (the AIMD-found hard cap)
                //   - else:   dynamic_capacity (the slot's real effective
                //             ceiling; equals max_concurrent for
                //             no-auto-detect cloud, current_limit for
                //             header-rich providers in Auto mode).
                //
                // Pre-Phase-136-Part-15 the else branch used current_limit
                // directly, which on Ollama Cloud / Gemini / Kimi
                // (no-auto-detect, max_concurrent>0) floated meaninglessly
                // above max — surfacing as "10 / 19" on a slot whose real
                // ceiling was 10.  Fall back to current_limit when an
                // older daemon doesn't expose dynamic_capacity.
                const effectiveCap = n.dynamic_capacity ?? n.current_limit;
                const cap = ceiling != null && state === "locked" ? ceiling : effectiveCap;
                const stateBadge = (() => {
                  switch (state) {
                    case "locked": return { icon: "🔒", label: "locked" };
                    case "backing_off": return { icon: "🔻", label: "backing off" };
                    case "recovering": return { icon: "↗", label: "recovering" };
                    case "probing":
                    default: return { icon: "📈", label: "probing" };
                  }
                })();
                // Soft user cap (only when explicitly set below the discovered ceiling).
                const userCap =
                  n.max_concurrent > 1 && ceiling != null && n.max_concurrent < ceiling
                    ? n.max_concurrent
                    : null;
                return (
                  <div key={nid} className="flex items-center justify-between text-[10px] text-text-muted tabular-nums">
                    <span className="truncate max-w-[140px]" title={nid}>{nid}</span>
                    <span className="inline-flex items-center gap-1">
                      {n.in_flight_requests} / {cap}
                      <span title={stateBadge.label} aria-label={stateBadge.label} className="opacity-70">
                        {stateBadge.icon}
                      </span>
                      {userCap != null && (
                        <span className="ml-1 opacity-60">(cap {userCap})</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
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
                    {item.current_stage && ` · ${stageLabel(item.current_stage)}`}
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
                      className="h-5 w-5 text-amber-500 hover:text-green-500"
                      title="Resume this paused run"
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

                  {/* F-83: Always show a close/dismiss button for non-running items
                      so users have a clear out. Paused → Cancel (stops run).
                      Cancelled/failed → Dismiss (clears the stale card). */}
                  {item.phase !== 'failed' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleCancel(item)}
                      className="h-5 w-5 text-text-muted hover:text-red-500 ml-auto"
                      title={item.phase === 'paused' ? 'Cancel (discard run)' : item.phase === 'cancelled' ? 'Dismiss' : 'Cancel'}
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
