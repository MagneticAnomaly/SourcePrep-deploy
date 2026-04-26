import { useEffect, useState } from 'react';
import { cn } from '../../lib/utils';
import type { ConcurrencyNode } from './ConcurrencyHealth';
import type { ProbeResult } from '../llm/ProbeButton';

// ── Types ─────────────────────────────────────────────────────────

/** A saved cloud endpoint as the user configured it. Mirrors the small
 *  subset of fields CapacityHealth actually displays. */
export interface CapacityEndpoint {
  id: string;
  name: string;
  provider: string;
  url: string;
  /** Phase 119 Phase A: plan tier label (e.g. "tier_3", "max", "auto", "custom"). */
  plan_tier?: string;
  /** Phase 119 Phase A: soft cap on concurrent calls. 0 = "auto"/unbounded. */
  cloud_concurrency?: number;
}

/** Phase 119 Phase B: most recent saturation hint per node, parsed from
 *  rate-limit headers. We don't have a direct API for this yet — when
 *  the panel can't find one, the badge falls back to "—". */
export interface SaturationSnapshot {
  /** 0..1 — 0 means lots of headroom, 1 means at saturation. */
  score: number;
  /** human-readable reason, e.g. "x-ratelimit-remaining-requests=3/100". */
  reason: string;
  /** unix seconds */
  ts: number;
}

export interface CapacityHealthProps {
  baseUrl?: string;
  /** Pre-supplied data for stories/tests (skips fetch). */
  initialEndpoints?: CapacityEndpoint[];
  initialNodes?: Record<string, ConcurrencyNode>;
  initialProbes?: Record<string, ProbeResult | null>;
  initialSaturation?: Record<string, SaturationSnapshot | null>;
  pollMs?: number;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────

function relativeTime(tsSec: number, nowMs: number): string {
  const sec = Math.max(0, Math.round(nowMs / 1000 - tsSec));
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hrs = Math.round(min / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

/** Phase 119 Phase B: 3-tier saturation traffic light.
 *  green <0.5, amber 0.5–0.8, red >0.8. */
function saturationTone(score: number): { tone: string; label: string; bg: string } {
  if (score > 0.8) return { tone: 'text-error', bg: 'bg-error/10 border-error/30', label: 'High' };
  if (score >= 0.5) return { tone: 'text-warning', bg: 'bg-warning/10 border-warning/30', label: 'Elevated' };
  return { tone: 'text-success', bg: 'bg-success/10 border-success/30', label: 'Low' };
}

/** Map a saved endpoint id to the scheduler's node id.
 *  Phase 119 convention: cloud slots live under `cloud:<endpoint_id>`. */
function nodeIdForEndpoint(ep: CapacityEndpoint): string {
  return `cloud:${ep.id}`;
}

// ── Sub-components ────────────────────────────────────────────────

function PlanTierBadge({ ep }: { ep: CapacityEndpoint }) {
  const tier = ep.plan_tier ?? '—';
  const cap = ep.cloud_concurrency ?? 0;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-text-muted">
      <span className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono">
        {tier}
      </span>
      {cap > 0 ? (
        <span className="text-text">soft cap {cap}</span>
      ) : (
        <span className="text-text-muted italic">auto</span>
      )}
    </span>
  );
}

function SaturationPill({ snap }: { snap: SaturationSnapshot | null }) {
  if (!snap) {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 text-[10px] text-text-muted">
        Saturation: —
      </span>
    );
  }
  const { tone, bg, label } = saturationTone(snap.score);
  return (
    <span
      className={cn('inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[10px]', bg, tone)}
      title={snap.reason}
    >
      Saturation: <strong>{label}</strong>
      <span className="opacity-70">({snap.score.toFixed(2)})</span>
    </span>
  );
}

function ProbeSummary({
  probe,
  nowMs,
}: {
  probe: ProbeResult | null;
  nowMs: number;
}) {
  if (!probe) {
    return (
      <p className="text-[11px] italic text-text-subtle">
        No probe yet. Click <strong>Probe Capacity</strong> on the endpoint card to measure
        actual capacity.
      </p>
    );
  }
  const ago = relativeTime(probe.probed_at, nowMs);
  return (
    <div className="text-[11px] text-text-base">
      <span className="text-text-muted">Probed {ago}</span>
      {' · '}
      {probe.saturation_point != null ? (
        <>
          saturation <strong>{probe.saturation_point}</strong>, recommended{' '}
          <strong>{probe.recommended_concurrent}</strong>
        </>
      ) : (
        <span className="italic text-text-muted">no saturation detected</span>
      )}
      <span className="ml-2 text-text-subtle tabular-nums">
        p50 {Math.round(probe.wall_clock_ms.p50)}ms · p90 {Math.round(probe.wall_clock_ms.p90)}ms
      </span>
    </div>
  );
}

function EndpointCard({
  ep,
  node,
  probe,
  saturation,
  nowMs,
}: {
  ep: CapacityEndpoint;
  node: ConcurrencyNode | null;
  probe: ProbeResult | null;
  saturation: SaturationSnapshot | null;
  nowMs: number;
}) {
  return (
    <section
      className="rounded-lg border border-border bg-surface-raised p-4 shadow-sm space-y-3"
      data-testid={`capacity-card-${ep.id}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text truncate" title={ep.id}>
            {ep.name}
            <span className="ml-2 text-[10px] uppercase tracking-wider text-text-muted">
              {ep.provider}
            </span>
          </h3>
          <p className="text-[11px] text-text-subtle font-mono truncate" title={ep.url}>
            {ep.url}
          </p>
        </div>
        <SaturationPill snap={saturation} />
      </header>

      <div className="flex items-center justify-between">
        <PlanTierBadge ep={ep} />
        {node && (
          <span className="text-[11px] text-text-muted tabular-nums">
            Live limit: <strong className="text-text">{node.current_limit}</strong>
            {' · '}
            in-flight {node.in_flight_requests}
          </span>
        )}
      </div>

      <div className="rounded border border-border/60 bg-surface px-3 py-2">
        <p className="text-[10px] uppercase tracking-wide text-text-muted mb-1">
          Last probe
        </p>
        <ProbeSummary probe={probe} nowMs={nowMs} />
      </div>
    </section>
  );
}

// ── Main panel ────────────────────────────────────────────────────

export function CapacityHealth({
  baseUrl,
  initialEndpoints,
  initialNodes,
  initialProbes,
  initialSaturation,
  pollMs = 5000,
  className,
}: CapacityHealthProps) {
  const [endpoints, setEndpoints] = useState<CapacityEndpoint[]>(initialEndpoints ?? []);
  const [nodes, setNodes] = useState<Record<string, ConcurrencyNode>>(initialNodes ?? {});
  const [probes, setProbes] = useState<Record<string, ProbeResult | null>>(initialProbes ?? {});
  const [saturation, setSaturation] = useState<Record<string, SaturationSnapshot | null>>(
    initialSaturation ?? {},
  );
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const isStoryMode = initialEndpoints !== undefined;

  // Initial load + polling.
  useEffect(() => {
    if (isStoryMode) return;
    if (!baseUrl) return;

    let cancelled = false;
    const root = baseUrl.replace(/\/$/, '');

    const tick = async () => {
      try {
        const [settingsRes, schedRes] = await Promise.all([
          fetch(`${root}/settings`).then((r) => r.json()),
          fetch(`${root}/compute/scheduler`).then((r) => r.json()),
        ]);
        if (cancelled) return;

        const settingsData = settingsRes?.data ?? settingsRes;
        const llmConfig = settingsData?.llm_config ?? {};
        const saved: CapacityEndpoint[] = (llmConfig.saved_endpoints ?? [])
          .filter((e: any) => e && typeof e === 'object')
          .map((e: any) => ({
            id: String(e.id),
            name: String(e.name ?? e.id),
            provider: String(e.provider ?? ''),
            url: String(e.url ?? ''),
            plan_tier: e.plan_tier,
            cloud_concurrency: e.cloud_concurrency,
          }));
        const cloudOnly = saved.filter((e) =>
          ['openai', 'anthropic', 'google', 'azure-openai'].includes(e.provider) ||
          (e.provider === 'ollama' && /(^|\.)ollama\.com$/i.test(safeHost(e.url))),
        );
        setEndpoints(cloudOnly);

        const schedData = schedRes?.data ?? schedRes;
        setNodes((schedData?.nodes ?? {}) as Record<string, ConcurrencyNode>);

        // Per-endpoint latest probe (best-effort, in parallel).
        const probeFetches = await Promise.all(
          cloudOnly.map(async (ep) => {
            try {
              const r = await fetch(
                `${root}/compute/endpoint-probe/history?endpoint_id=${encodeURIComponent(ep.id)}&limit=1`,
              );
              if (!r.ok) return [ep.id, null] as const;
              const body = await r.json();
              const data = body?.data ?? body;
              const arr: ProbeResult[] = data?.probes ?? [];
              return [ep.id, arr[arr.length - 1] ?? null] as const;
            } catch {
              return [ep.id, null] as const;
            }
          }),
        );
        if (cancelled) return;
        setProbes(Object.fromEntries(probeFetches));

        // Saturation snapshots aren't yet exposed via a stable API.
        // Reserve the wiring point — the panel renders "—" when missing.
        setSaturation({});

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
  }, [baseUrl, pollMs, isStoryMode]);

  // Tick the "now" clock for relative-time freshness.
  useEffect(() => {
    if (pollMs <= 0) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [pollMs]);

  return (
    <div className={cn('grid gap-4 p-4', className)} data-testid="capacity-health">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-text">Capacity Health</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Per-endpoint capacity weather report — what your plan says vs what the
            endpoint actually delivered.
          </p>
        </div>
        {error && (
          <span className="text-xs text-error" role="alert">
            {error}
          </span>
        )}
      </header>

      {endpoints.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-surface p-6 text-center text-sm text-text-muted">
          No cloud endpoints configured. Add a cloud LLM provider to see capacity
          telemetry here.
        </div>
      ) : (
        endpoints.map((ep) => (
          <EndpointCard
            key={ep.id}
            ep={ep}
            node={nodes[nodeIdForEndpoint(ep)] ?? null}
            probe={probes[ep.id] ?? null}
            saturation={saturation[ep.id] ?? null}
            nowMs={now}
          />
        ))
      )}
    </div>
  );
}

function safeHost(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return '';
  }
}

export default CapacityHealth;
