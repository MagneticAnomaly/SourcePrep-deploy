import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Copy, FileText, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * Phase 119 verbose-logging — developer-popover panel that lists the
 * most-recent ``swarm_*.jsonl`` event logs written by
 * ``SwarmEventLogger`` and lets the user expand any file to inspect its
 * events inline.  Replaces the previous static path footer in the
 * AI Gateway dev popover.
 *
 * The component polls ``GET /system/swarm-events`` every ``pollIntervalMs``
 * for the file listing while it is rendered.  Per-file events are loaded
 * lazily on first expand via ``?file=<basename>``.
 */

export interface SwarmLogFile {
  name: string;
  size: number;
  mtime: number;
}

export interface SwarmLogEvent {
  ts: number;
  elapsed_s: number;
  kind: string;
  // Other fields are kind-dependent; preserve them via index signature.
  [key: string]: unknown;
}

export interface RecentSwarmLogsProps {
  baseUrl?: string;
  pollIntervalMs?: number;
  /** Test/storybook injection — render given files without polling. */
  initialFiles?: SwarmLogFile[];
  /** Test/storybook injection — pre-populated event maps keyed by filename. */
  initialEvents?: Record<string, SwarmLogEvent[]>;
  /** Soft cap on rendered rows; default 10 most-recent. */
  maxRows?: number;
  className?: string;
}

const DEFAULT_BASE_URL = 'http://localhost:8400';
const KIND_PHASE_BOUNDARY = new Set([
  'session_start',
  'session_end',
  'phase_start',
  'phase_end',
]);
const KIND_WORKER = new Set(['worker_dispatch', 'worker_complete']);
const KIND_ERROR = new Set(['parse_failure', 'session_error', 'error']);

function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 10 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}

function formatRelative(epochSeconds: number, now: number = Date.now() / 1000): string {
  const delta = Math.max(0, now - epochSeconds);
  if (delta < 5) return 'just now';
  if (delta < 60) return `${Math.floor(delta)}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} hr ago`;
  return `${Math.floor(delta / 86400)} d ago`;
}

/**
 * Parse a SwarmEventLogger filename into a friendly label.
 *
 * Filenames look like ``swarm_YYYYMMDD_HHMMSS_<stage...>_<run-id-prefix>.jsonl``.
 * ``<stage...>`` may itself contain underscores (e.g. ``concept_seeding``),
 * so we split off the trailing run-id and the leading prefix/timestamp,
 * then join the remainder back as the stage.
 */
export function parseSwarmLogName(name: string): { label: string; time: string; stage: string } {
  const stripped = name.replace(/\.jsonl$/, '');
  const parts = stripped.split('_');
  // Expect at least: swarm_YYYYMMDD_HHMMSS_<stage>_<runid>
  if (parts.length < 5 || parts[0] !== 'swarm') {
    return { label: name, time: '', stage: name };
  }
  const date = parts[1];
  const time = parts[2];
  const stageParts = parts.slice(3, -1);
  const stage = stageParts.join('_') || 'swarm';

  let prettyTime = time;
  if (/^\d{6}$/.test(time)) {
    prettyTime = `${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`;
  }
  let prettyDate = date;
  if (/^\d{8}$/.test(date)) {
    prettyDate = `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
  }

  // Title-case the stage by replacing underscores with spaces.
  const stageLabel = stage
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return {
    label: `${stageLabel} · ${prettyTime}`,
    time: `${prettyDate} ${prettyTime}`,
    stage,
  };
}

interface FetchListResponse {
  ok: boolean;
  log_dir?: string;
  files?: SwarmLogFile[];
}

interface FetchEventsResponse {
  ok: boolean;
  log_dir?: string;
  file?: string;
  events?: SwarmLogEvent[];
}

export function RecentSwarmLogs({
  baseUrl,
  pollIntervalMs = 5000,
  initialFiles,
  initialEvents,
  maxRows = 10,
  className,
}: RecentSwarmLogsProps) {
  const root = (baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '');
  const isStoryMode = initialFiles !== undefined;

  const [files, setFiles] = useState<SwarmLogFile[]>(initialFiles ?? []);
  const [logDir, setLogDir] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(() => {
    if (initialEvents) {
      const keys = Object.keys(initialEvents);
      return keys.length > 0 ? keys[0] : null;
    }
    return null;
  });
  const [eventsByFile, setEventsByFile] = useState<Record<string, SwarmLogEvent[]>>(
    initialEvents ?? {},
  );
  const [eventErrors, setEventErrors] = useState<Record<string, string>>({});
  const [loadingEventsFor, setLoadingEventsFor] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<{ name: string; ok: boolean } | null>(null);

  const loadList = useCallback(async () => {
    if (isStoryMode) return;
    try {
      const res = await fetch(`${root}/system/swarm-events`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as FetchListResponse;
      setFiles(body.files ?? []);
      setLogDir(body.log_dir ?? null);
      setListError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'fetch failed';
      setListError(msg);
    }
  }, [root, isStoryMode]);

  // Poll the list while mounted.
  useEffect(() => {
    if (isStoryMode) return;
    void loadList();
    if (pollIntervalMs <= 0) return;
    const id = window.setInterval(() => void loadList(), pollIntervalMs);
    return () => window.clearInterval(id);
  }, [loadList, pollIntervalMs, isStoryMode]);

  const loadEvents = useCallback(
    async (name: string) => {
      if (isStoryMode) return;
      if (eventsByFile[name]) return;
      setLoadingEventsFor(name);
      try {
        const res = await fetch(
          `${root}/system/swarm-events?file=${encodeURIComponent(name)}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as FetchEventsResponse;
        setEventsByFile((prev) => ({ ...prev, [name]: body.events ?? [] }));
        setEventErrors((prev) => {
          const next = { ...prev };
          delete next[name];
          return next;
        });
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'fetch failed';
        setEventErrors((prev) => ({ ...prev, [name]: msg }));
      } finally {
        setLoadingEventsFor((cur) => (cur === name ? null : cur));
      }
    },
    [root, eventsByFile, isStoryMode],
  );

  const onToggle = useCallback(
    (name: string) => {
      setExpanded((cur) => {
        const next = cur === name ? null : name;
        if (next) void loadEvents(next);
        return next;
      });
    },
    [loadEvents],
  );

  const copyTimerRef = useRef<number | null>(null);
  const onCopyPath = useCallback(
    async (name: string) => {
      const dir = logDir ?? '';
      const sep = dir.endsWith('/') || dir.endsWith('\\') ? '' : '/';
      const fullPath = dir ? `${dir}${sep}${name}` : name;
      try {
        if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(fullPath);
          setCopyState({ name, ok: true });
        } else {
          setCopyState({ name, ok: false });
        }
      } catch {
        setCopyState({ name, ok: false });
      }
      if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = window.setTimeout(() => setCopyState(null), 1800);
    },
    [logDir],
  );

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
    };
  }, []);

  const visible = useMemo(() => files.slice(0, maxRows), [files, maxRows]);

  if (visible.length === 0) {
    return (
      <div
        className={cn('text-[11px] text-text-muted italic', className)}
        data-testid="recent-swarm-logs-empty"
      >
        {listError ? (
          <span className="text-error not-italic inline-flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            Failed to load swarm logs: {listError}
          </span>
        ) : (
          'No swarm logs yet. Start a build to see verbose swarm activity here.'
        )}
      </div>
    );
  }

  return (
    <div
      className={cn('space-y-1', className)}
      data-testid="recent-swarm-logs"
    >
      {visible.map((f) => {
        const parsed = parseSwarmLogName(f.name);
        const isExpanded = expanded === f.name;
        const events = eventsByFile[f.name];
        const evError = eventErrors[f.name];
        const loading = loadingEventsFor === f.name;
        const isCopied = copyState?.name === f.name && copyState.ok;
        return (
          <div
            key={f.name}
            className="rounded border border-border bg-surface-raised/40"
            data-testid={`recent-swarm-log-row-${f.name}`}
          >
            <div className="flex items-center gap-1.5 px-2 py-1.5">
              <button
                type="button"
                className="inline-flex items-center gap-1 min-w-0 flex-1 text-left text-[11px] text-text hover:text-text"
                onClick={() => onToggle(f.name)}
                aria-expanded={isExpanded}
                data-testid={`recent-swarm-log-toggle-${f.name}`}
              >
                {isExpanded ? (
                  <ChevronDown className="w-3 h-3 shrink-0 text-text-muted" />
                ) : (
                  <ChevronRight className="w-3 h-3 shrink-0 text-text-muted" />
                )}
                <FileText className="w-3 h-3 shrink-0 text-text-muted" />
                <span className="truncate font-medium">{parsed.label}</span>
              </button>
              <span className="shrink-0 text-[10px] text-text-muted/80 tabular-nums">
                {formatBytes(f.size)}
              </span>
              <span
                className="shrink-0 text-[10px] text-text-muted/80 tabular-nums"
                title={new Date(f.mtime * 1000).toISOString()}
              >
                {formatRelative(f.mtime)}
              </span>
              <button
                type="button"
                onClick={() => void onCopyPath(f.name)}
                className={cn(
                  'shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] border border-border',
                  'text-text-muted hover:text-text hover:bg-surface',
                  isCopied && 'text-emerald-400 border-emerald-400/40',
                )}
                title="Copy absolute path to clipboard"
                data-testid={`recent-swarm-log-copy-${f.name}`}
              >
                <Copy className="w-3 h-3" />
                {isCopied ? 'Copied' : 'Open'}
              </button>
            </div>
            {isExpanded && (
              <div
                className="border-t border-border bg-surface px-2 py-1.5 max-h-64 overflow-auto font-mono"
                data-testid={`recent-swarm-log-events-${f.name}`}
              >
                {loading && (
                  <div className="text-[10px] text-text-muted italic">Loading events…</div>
                )}
                {evError && (
                  <div className="text-[10px] text-error inline-flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {evError}
                  </div>
                )}
                {!loading && !evError && events && events.length === 0 && (
                  <div className="text-[10px] text-text-muted italic">No events.</div>
                )}
                {!loading && !evError && events && events.length > 0 && (
                  <ul className="space-y-0.5 text-[10px] leading-tight">
                    {events.map((ev, idx) => (
                      <SwarmEventLine key={`${f.name}-${idx}`} ev={ev} />
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SwarmEventLine({ ev }: { ev: SwarmLogEvent }) {
  const isBoundary = KIND_PHASE_BOUNDARY.has(ev.kind);
  const isWorker = KIND_WORKER.has(ev.kind);
  const isError = KIND_ERROR.has(ev.kind);

  const elapsed = typeof ev.elapsed_s === 'number' ? `${ev.elapsed_s.toFixed(1)}s` : '—';
  const facts = summarizeFacts(ev);

  return (
    <li
      className={cn(
        'flex gap-2 whitespace-pre-wrap break-words',
        isBoundary && 'text-purple-300 font-semibold',
        isError && !isBoundary && 'text-error',
        isWorker && 'pl-3 text-text-muted',
        !isBoundary && !isError && !isWorker && 'text-text-muted',
      )}
    >
      <span className="shrink-0 tabular-nums w-12 text-text-muted/70">{elapsed}</span>
      <span className="shrink-0 w-32 truncate">{ev.kind}</span>
      <span className="min-w-0 flex-1">{facts}</span>
    </li>
  );
}

function summarizeFacts(ev: SwarmLogEvent): string {
  // Pick out a small set of fields per kind that read well in a single line.
  const skip = new Set(['ts', 'elapsed_s', 'kind']);
  const interesting: string[] = [];
  // Order by usefulness: phase, model, item_id, worker_id, success, n_*, summary fields.
  const order = [
    'phase',
    'model',
    'worker_id',
    'item_id',
    'success',
    'duration_s',
    'tokens',
    'n_items',
    'response_chars',
    'parse_ok',
    'reason',
    'where',
    'project_id',
    'stage',
    'run_id',
  ];
  for (const key of order) {
    if (key in ev && !skip.has(key)) {
      const v = (ev as Record<string, unknown>)[key];
      if (v === undefined || v === null) continue;
      interesting.push(`${key}=${formatVal(v)}`);
      skip.add(key);
    }
  }
  // Tail: any other shallow scalar fields (cap to 3).
  let tail = 0;
  for (const [k, v] of Object.entries(ev)) {
    if (skip.has(k)) continue;
    if (v === null || v === undefined) continue;
    if (typeof v === 'object') continue;
    interesting.push(`${k}=${formatVal(v)}`);
    tail += 1;
    if (tail >= 3) break;
  }
  // Special case: session_end carries a summary block.
  if (ev.kind === 'session_end' && ev.summary && typeof ev.summary === 'object') {
    const s = ev.summary as Record<string, unknown>;
    const compact = Object.entries(s)
      .slice(0, 4)
      .map(([k, v]) => `${k}=${formatVal(v)}`)
      .join(' ');
    if (compact) interesting.push(`{${compact}}`);
  }
  return interesting.join('  ');
}

function formatVal(v: unknown): string {
  if (typeof v === 'string') {
    return v.length > 40 ? `${v.slice(0, 37)}…` : v;
  }
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : v.toFixed(2);
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return String(v);
}

export default RecentSwarmLogs;
