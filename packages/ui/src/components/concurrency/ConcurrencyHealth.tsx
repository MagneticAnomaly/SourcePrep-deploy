import { useEffect, useState } from 'react';
import { cn } from '../../lib/utils';

// ── Types ─────────────────────────────────────────────────────────

export type ConcurrencyState = 'probing' | 'locked' | 'backing_off' | 'recovering';

export interface ConcurrencyEvent {
  ts: number;
  node_id: string;
  before: number;
  after: number;
  reason:
    | 'demand_recovery'
    | 'additive_increase'
    | 'jumpstart'
    | 'backoff'
    | 'hydrate'
    | 'edge_lock';
  in_flight: number;
  mode: string;
}

export interface ConcurrencyNode {
  max_concurrent: number;
  current_load: number;
  in_flight_requests: number;
  current_limit: number;
  discovered_ceiling?: number | null;
  locked_until?: number | null;
  aimd_mode?: string | null;
  state?: ConcurrencyState;
}

export interface ConcurrencyHealthProps {
  /** Base URL for the daemon, e.g. http://127.0.0.1:8400. */
  baseUrl?: string;
  /** Pre-supplied data (used in stories/tests instead of fetch). */
  initialNodes?: Record<string, ConcurrencyNode>;
  initialHistory?: Record<string, ConcurrencyEvent[]>;
  /** Polling interval in ms (default 2000). Set ≤ 0 to disable polling. */
  pollMs?: number;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────

const STATE_BADGES: Record<ConcurrencyState, { icon: string; label: string; tone: string }> = {
  probing: { icon: '📈', label: 'Probing', tone: 'text-info' },
  locked: { icon: '🔒', label: 'Locked', tone: 'text-success' },
  backing_off: { icon: '🔻', label: 'Backing off', tone: 'text-error' },
  recovering: { icon: '↗', label: 'Recovering', tone: 'text-warning' },
};

const REASON_TONE: Record<ConcurrencyEvent['reason'], string> = {
  demand_recovery: 'text-warning',
  additive_increase: 'text-info',
  jumpstart: 'text-info',
  backoff: 'text-error',
  hydrate: 'text-text-muted',
  edge_lock: 'text-success',
};

const REASON_ARROW: Record<ConcurrencyEvent['reason'], string> = {
  demand_recovery: '↗',
  additive_increase: '↗',
  jumpstart: '⇈',
  backoff: '↘',
  hydrate: '⟲',
  edge_lock: '🔒',
};

function relativeTime(ts: number, now: number): string {
  const sec = Math.max(0, Math.round(now / 1000 - ts));
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hrs = Math.round(min / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

function lockCountdown(lockedUntil: number | null | undefined, nowMs: number): string | null {
  if (!lockedUntil) return null;
  const remainingS = Math.round(lockedUntil - nowMs / 1000);
  if (remainingS <= 0) return null;
  if (remainingS < 60) return `${remainingS}s`;
  const min = Math.round(remainingS / 60);
  if (min < 60) return `${min}m`;
  const hrs = Math.floor(min / 60);
  const mm = min % 60;
  return mm > 0 ? `${hrs}h ${mm}m` : `${hrs}h`;
}

// ── Sub-components ────────────────────────────────────────────────

function StatePill({ state }: { state: ConcurrencyState }) {
  const badge = STATE_BADGES[state];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium',
        badge.tone,
      )}
    >
      <span aria-hidden="true">{badge.icon}</span>
      <span>{badge.label}</span>
    </span>
  );
}

function MiniSparkline({ events }: { events: ConcurrencyEvent[] }) {
  if (events.length < 2) {
    return (
      <div className="h-10 w-full flex items-center justify-center text-[10px] text-text-muted italic">
        Not enough data yet
      </div>
    );
  }
  const points = events.map((e) => e.after);
  const minVal = Math.min(...points);
  const maxVal = Math.max(...points);
  const range = Math.max(1, maxVal - minVal);
  const w = 200;
  const h = 40;
  const stepX = w / Math.max(1, points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * stepX;
      const y = h - ((p - minVal) / range) * (h - 4) - 2;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="h-10 w-full overflow-visible"
      role="img"
      aria-label={`current_limit sparkline; min ${minVal}, max ${maxVal}`}
    >
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-info" />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={i * stepX}
          cy={h - ((p - minVal) / range) * (h - 4) - 2}
          r={1.5}
          className="fill-info"
        />
      ))}
    </svg>
  );
}

function EventTimeline({ events, now }: { events: ConcurrencyEvent[]; now: number }) {
  if (!events.length) {
    return (
      <p className="px-3 py-4 text-xs italic text-text-muted">No recent events</p>
    );
  }
  // Show the most recent first, up to 20.
  const ordered = [...events].slice(-20).reverse();
  return (
    <ul className="divide-y divide-border/60 text-xs">
      {ordered.map((ev, i) => (
        <li key={`${ev.ts}-${i}`} className="flex items-center justify-between gap-2 py-1.5 px-3">
          <span className={cn('inline-flex items-center gap-1.5 font-medium', REASON_TONE[ev.reason])}>
            <span aria-hidden="true" className="w-3 text-center">
              {REASON_ARROW[ev.reason]}
            </span>
            <span className="capitalize">{ev.reason.replace(/_/g, ' ')}</span>
          </span>
          <span className="tabular-nums text-text-muted">
            {ev.before} → <span className="text-text font-medium">{ev.after}</span>
            <span className="ml-2 opacity-70">in-flight {ev.in_flight}</span>
          </span>
          <span className="text-right text-text-muted shrink-0 w-20 truncate" title={new Date(ev.ts * 1000).toLocaleString()}>
            {relativeTime(ev.ts, now)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function NodeCard({
  nid,
  node,
  events,
  now,
}: {
  nid: string;
  node: ConcurrencyNode;
  events: ConcurrencyEvent[];
  now: number;
}) {
  const state = (node.state ?? 'probing') as ConcurrencyState;
  const ceiling = node.discovered_ceiling ?? null;
  const countdown = state === 'locked' ? lockCountdown(node.locked_until ?? null, now) : null;
  const userCap =
    ceiling != null && node.max_concurrent > 1 && node.max_concurrent < ceiling
      ? node.max_concurrent
      : null;

  return (
    <section
      className="rounded-lg border border-border bg-surface-raised p-4 shadow-sm"
      data-testid={`concurrency-card-${nid}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text truncate" title={nid}>
            {nid}
          </h3>
          <p className="text-[11px] text-text-muted mt-0.5">
            Mode: <span className="font-medium">{node.aimd_mode ?? '—'}</span>
            {userCap != null && (
              <>
                {' · '}
                <span className="text-warning">soft cap {userCap}</span>
              </>
            )}
          </p>
        </div>
        <StatePill state={state} />
      </header>

      <dl className="mt-3 grid grid-cols-3 gap-3 text-xs">
        <div>
          <dt className="text-text-muted">Current limit</dt>
          <dd className="text-2xl font-semibold tabular-nums text-text">{node.current_limit}</dd>
        </div>
        <div>
          <dt className="text-text-muted">In-flight</dt>
          <dd className="text-2xl font-semibold tabular-nums text-text">
            {node.in_flight_requests}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Discovered ceiling</dt>
          <dd className="text-2xl font-semibold tabular-nums text-text">
            {ceiling ?? <span className="text-text-muted">—</span>}
            {countdown && (
              <span className="ml-1 text-[10px] font-normal text-success">
                lock {countdown}
              </span>
            )}
          </dd>
        </div>
      </dl>

      <div className="mt-3 rounded border border-border/60 bg-surface p-2">
        <p className="text-[10px] uppercase tracking-wide text-text-muted mb-1">
          current_limit over recent events
        </p>
        <MiniSparkline events={events} />
      </div>

      <div className="mt-3 rounded border border-border/60 bg-surface">
        <p className="text-[10px] uppercase tracking-wide text-text-muted px-3 pt-2">
          Recent AIMD events
        </p>
        <EventTimeline events={events} now={now} />
      </div>
    </section>
  );
}

// ── Main panel ────────────────────────────────────────────────────

export function ConcurrencyHealth({
  baseUrl,
  initialNodes,
  initialHistory,
  pollMs = 2000,
  className,
}: ConcurrencyHealthProps) {
  const [nodes, setNodes] = useState<Record<string, ConcurrencyNode>>(initialNodes ?? {});
  const [history, setHistory] = useState<Record<string, ConcurrencyEvent[]>>(
    initialHistory ?? {},
  );
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    if (initialNodes !== undefined && initialHistory !== undefined) {
      // Story / test mode — don't poll.
      return;
    }
    if (!baseUrl) return;

    let cancelled = false;
    const root = baseUrl.replace(/\/$/, '');

    const tick = async () => {
      try {
        const [sRes, hRes] = await Promise.all([
          fetch(`${root}/compute/scheduler`).then((r) => r.json()),
          fetch(`${root}/compute/concurrency/history`).then((r) => r.json()),
        ]);
        if (cancelled) return;
        // /compute/scheduler is wrapped in the standard ok() envelope.
        const data = sRes?.data ?? sRes;
        setNodes((data?.nodes ?? {}) as Record<string, ConcurrencyNode>);
        setHistory((hRes?.history ?? {}) as Record<string, ConcurrencyEvent[]>);
        setNow(Date.now());
        setError(null);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? 'failed to fetch');
      }
    };

    void tick();
    if (pollMs <= 0) return () => { cancelled = true; };
    const id = window.setInterval(tick, pollMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [baseUrl, pollMs, initialNodes, initialHistory]);

  // Tick the "now" clock once per second so relative timestamps refresh.
  useEffect(() => {
    if (pollMs <= 0) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [pollMs]);

  const cloudEntries = Object.entries(nodes).filter(([nid]) => nid.startsWith('cloud:'));
  const showEmpty = cloudEntries.length === 0;

  return (
    <div className={cn('grid gap-4 p-4', className)} data-testid="concurrency-health">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text">Concurrency Health</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Live AIMD state for each cloud LLM node — Phase 119 weather report.
          </p>
        </div>
        {error && (
          <span className="text-xs text-error" role="alert">
            {error}
          </span>
        )}
      </header>

      {showEmpty ? (
        <div className="rounded-lg border border-dashed border-border bg-surface p-6 text-center text-sm text-text-muted">
          No cloud compute nodes registered. Configure an endpoint to see concurrency
          telemetry here.
        </div>
      ) : (
        cloudEntries.map(([nid, node]) => (
          <NodeCard
            key={nid}
            nid={nid}
            node={node}
            events={history[nid] ?? []}
            now={now}
          />
        ))
      )}
    </div>
  );
}

export default ConcurrencyHealth;
