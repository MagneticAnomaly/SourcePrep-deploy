import { useEffect, useState } from 'react';
import {
  Button,
  CapacityHealth,
  ConcurrencyHealth,
  ConcurrencyResetPanel,
  RecentSwarmLogs,
  Section,
  SwarmActivityPanel,
  useApiClient,
} from '@prep/ui';
import type { LicenseStatus, LicenseTier, RunningTask } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

export interface DiagnosticsPageProps {
  licenseStatus: LicenseStatus | null;
  devTierOverride: LicenseTier | null;
}

/**
 * Settings → Diagnostics page.
 *
 * Phase 119 amendment: the developer-mode panels that previously lived
 * inside the AI Gateway sidebar's wrench popover (concurrency reset,
 * swarm activity, recent swarm logs) now live here.  The sidebar is
 * status-only — running tasks, badges, model assignments — and any
 * diagnostic / dogfooding affordance lives in Settings.
 */
export function DiagnosticsPage({
  licenseStatus,
  devTierOverride,
}: DiagnosticsPageProps) {
  const [healthResult, setHealthResult] = useState<string>('No test run yet');
  const api = useApiClient();

  // ── Live state for the swarm + concurrency panels ──────────────
  // Mirror the polling patterns the sidebar used so the panels render
  // useful data while the user is on this page. Both endpoints are
  // cheap; we only poll while mounted.
  const [runningTasks, setRunningTasks] = useState<RunningTask[]>([]);
  const [cloudNodeIds, setCloudNodeIds] = useState<string[] | null>(null);

  useEffect(() => {
    const root = api.baseUrl.replace(/\/$/, '');
    let cancelled = false;

    const tickSlots = async () => {
      try {
        const res = await fetch(`${root}/llm/slots/status`);
        if (!res.ok) return;
        const body = await res.json();
        const tasks: RunningTask[] =
          body?.data?.running_tasks ?? body?.running_tasks ?? [];
        if (!cancelled) setRunningTasks(tasks);
      } catch {
        /* swallow — panel renders empty state on its own */
      }
    };

    const tickScheduler = async () => {
      try {
        const res = await fetch(`${root}/compute/scheduler`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = await res.json();
        const nodes = body?.data?.nodes ?? body?.nodes ?? {};
        const ids = Object.keys(nodes).filter((nid) => nid.startsWith('cloud:'));
        if (!cancelled) setCloudNodeIds(ids);
      } catch {
        if (!cancelled) setCloudNodeIds([]);
      }
    };

    void tickSlots();
    void tickScheduler();
    const slotsId = window.setInterval(() => void tickSlots(), 3000);
    const schedId = window.setInterval(() => void tickScheduler(), 10000);
    return () => {
      cancelled = true;
      window.clearInterval(slotsId);
      window.clearInterval(schedId);
    };
  }, [api.baseUrl]);

  // Lifted verbatim from SettingsDrawer.tsx:228-236
  const runHealthTest = async () => {
    setHealthResult('Testing...');
    try {
      const health = await api.getHealth();
      setHealthResult(`OK: ${JSON.stringify(health)}`);
    } catch (err) {
      setHealthResult(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <SettingsPage
      title="Diagnostics"
      scope="developer"
      description="Live cloud-LLM concurrency, swarm activity, recent swarm logs, and license/connection health."
    >
      <Section title="License details">
        <div className="text-xs font-mono bg-background p-3 rounded border border-border space-y-1.5">
          <div className="grid grid-cols-[80px_1fr] gap-x-2">
            <strong className="text-text">Tier:</strong>
            <span className="text-text-muted capitalize">{licenseStatus?.license.tier ?? 'unknown'}</span>

            <strong className="text-text">Valid:</strong>
            <span className="text-text-muted">{licenseStatus?.license.valid ? 'Yes' : 'No'}</span>

            <strong className="text-text">Override:</strong>
            <span className="text-text-muted">{devTierOverride ?? 'None'}</span>

            <strong className="text-text">Effective:</strong>
            <span className="text-primary capitalize">{devTierOverride ?? licenseStatus?.license.tier ?? 'free'}</span>

            {licenseStatus?.license.email && (
              <>
                <strong className="text-text">Email:</strong>
                <span className="text-text-muted truncate">{licenseStatus.license.email}</span>
              </>
            )}
          </div>
        </div>
      </Section>

      <Section title="Connection debugger">
        <div className="space-y-3">
          <Button variant="outline" size="sm" onClick={runHealthTest} className="w-full">
            Test /health Endpoint
          </Button>
          <div className="bg-background p-3 rounded border border-border font-mono text-xs">
            <pre className="whitespace-pre-wrap break-all text-text">{healthResult}</pre>
          </div>
          <div className="grid grid-cols-[60px_1fr] gap-x-2 text-xs text-text-muted">
            <strong className="text-text">Origin:</strong> {window.location.origin}
            <strong className="text-text">API:</strong> {api.baseUrl || '(hidden)'}
          </div>
        </div>
      </Section>

      <Section title="Capacity Health">
        <p className="text-xs text-text-muted mb-2">
          Per-endpoint capacity weather report — plan tier and soft cap (what
          the docs say) vs live AIMD limit, saturation hint, and last probe
          (what the endpoint actually delivered). Phase 119 Phase C.
        </p>
        <CapacityHealth baseUrl={api.baseUrl} className="!p-0" />
      </Section>

      <Section title="Concurrency Health">
        <p className="text-xs text-text-muted mb-2">
          Live AIMD state per cloud LLM node — current limit, in-flight,
          discovered ceiling, and recent backoff/grow events. Polls every 2 s.
        </p>
        <ConcurrencyHealth baseUrl={api.baseUrl} className="!p-0" />
      </Section>

      <Section title="Active Swarms">
        <p className="text-xs text-text-muted mb-2">
          Coordinator → workers → synthesizer breakdown for currently-running
          swarm orchestrations. If you see N concurrent calls but no
          coordinator/synthesizer, the stage is parallel — not swarming.
        </p>
        <SwarmActivityPanel runningTasks={runningTasks} />
      </Section>

      <Section title="Recent Swarm Logs">
        <p className="text-xs text-text-muted mb-2">
          Per-swarm JSONL event logs written by{' '}
          <code className="font-mono text-[11px]">SwarmEventLogger</code>.
          Click any row to inspect its events inline.
        </p>
        <RecentSwarmLogs baseUrl={api.baseUrl} />
      </Section>

      <Section title="Reset Cloud Concurrency">
        <p className="text-xs text-text-muted mb-2">
          Forces SourcePrep to re-probe and rediscover the cloud-LLM
          concurrency limit. Use after a plan upgrade, endpoint swap, or when
          the limit value looks wrong.
        </p>
        <ConcurrencyResetPanel
          cloudNodeIds={cloudNodeIds ?? []}
          baseUrl={api.baseUrl}
        />
        {cloudNodeIds === null && (
          <div className="text-[10px] text-text-muted mt-2">Loading nodes…</div>
        )}
      </Section>
    </SettingsPage>
  );
}
