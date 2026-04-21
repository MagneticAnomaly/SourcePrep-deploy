import { useState } from 'react';
import { cn } from '../../lib/utils';
import { Shield, Activity, AlertTriangle, CheckCircle, XCircle, Lock, Server, Cpu, Cloud, Settings2, Clock, RefreshCw, DollarSign, FileDown } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import type { ComputeNode, SchedulerStatus, AdminPolicy } from '../../types';
import { AdminSection } from '../primitives/AdminSection';

export type AdminTab = 'fleet' | 'sync' | 'usage' | 'security' | 'policy';

export interface SecurityHealthResult {
  score: number;
  total: number;
  status: 'healthy' | 'warnings' | 'critical';
  checks: Array<{
    name: string;
    status: 'pass' | 'warn' | 'fail';
    issues: string[];
    details: Record<string, any>;
  }>;
}

export interface TokenUsageSummary {
  total_tokens: number;
  call_count: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  estimated_cost_usd?: number | null;
}

export interface EnterpriseAdminPanelProps {
  /** Current license tier — panel only renders for team/enterprise */
  tier: string;
  /** User role — panel only renders for admin */
  role: string;
  /** Compute nodes from the scheduler */
  computeNodes?: ComputeNode[];
  /** Live scheduler status */
  schedulerStatus?: SchedulerStatus | null;
  /** Team sync fleet status — projects with sync enabled */
  syncFleet?: SyncFleetEntry[];
  /** Usage/billing data */
  usage?: UsageData | null;
  /** Trigger a manual sync for a project */
  onSyncProject?: (projectId: string) => void;
  /** EA-H7: Token usage summary for current month */
  tokenUsage?: TokenUsageSummary | null;
  /** EA-I10: Security health check results */
  securityHealth?: SecurityHealthResult | null;
  /** EA-I10: Recent security events */
  securityEvents?: Array<{ timestamp: number; event_type: string; severity: string; message: string }>;
  /** EA-I12: Export security report */
  onExportSecurityReport?: () => void;
  /** EA-H8: Export audit log */
  onExportAuditLog?: () => void;
  /** Admin policy from team_config.json */
  adminPolicy?: AdminPolicy | null;
  /** SEAT-2: Seat management data */
  seatStatus?: {
    seats_used: number;
    seats_total: number;
    tier: string;
    email?: string;
    activation_method?: string;
    last_validated?: number | null;
    grace_days_remaining?: number | null;
    activations: Array<{ instance_id: string; machine: string; platform: string; activated_at?: number; is_current: boolean }>;
  } | null;
  /** SEAT-4: Provision a seat to a team member by email */
  onProvisionSeat?: (email: string) => Promise<{ provisioned: boolean; message: string }>;
  /** Default tab to show */
  defaultTab?: AdminTab;
  className?: string;
}

export interface SyncFleetEntry {
  projectId: string;
  projectName: string;
  lastSync: number | null;
  lastCommit: string | null;
  status: 'synced' | 'syncing' | 'stale' | 'error' | 'disabled';
  error?: string;
}

export interface UsageData {
  currentMonth: {
    indexingMinutes: number;
    indexingRuns: number;
    storageGb: number;
    activeSeats: number;
  };
  limits: {
    maxIndexingMinutes: number | null;
    maxStorageGb: number | null;
    maxSeats: number | null;
  };
}

export function EnterpriseAdminPanel({
  tier,
  role,
  computeNodes = [],
  schedulerStatus,
  syncFleet = [],
  usage,
  onSyncProject,
  tokenUsage,
  securityHealth,
  securityEvents = [],
  onExportSecurityReport,
  onExportAuditLog,
  adminPolicy,
  seatStatus,
  onProvisionSeat,
  defaultTab = 'fleet',
  className,
}: EnterpriseAdminPanelProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>(defaultTab);
  const [provisionEmail, setProvisionEmail] = useState('');
  const [provisionLoading, setProvisionLoading] = useState(false);
  const [provisionMessage, setProvisionMessage] = useState<{ text: string, type: 'success' | 'error' } | null>(null);

  const handleProvisionSeat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onProvisionSeat || !provisionEmail.trim()) return;
    setProvisionLoading(true);
    setProvisionMessage(null);
    try {
      const res = await onProvisionSeat(provisionEmail.trim());
      setProvisionMessage({ text: res.message, type: res.provisioned ? 'success' : 'error' });
      if (res.provisioned) setProvisionEmail('');
    } catch (err: any) {
      setProvisionMessage({ text: err.message || 'Failed to provision seat', type: 'error' });
    } finally {
      setProvisionLoading(false);
    }
  };

  // Gate: only visible to admin role on team/enterprise tiers
  if (role !== 'admin' || (tier !== 'team' && tier !== 'enterprise')) {
    return (
      <div className={cn('p-8 text-center', className)}>
        <Shield className="w-12 h-12 text-text-muted mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-text mb-2">Enterprise Admin</h2>
        <p className="text-sm text-text-muted max-w-md mx-auto">
          This panel is only available to IT administrators on Team or Enterprise plans.
          {tier === 'free' || tier === 'pro' ? (
            <> Upgrade to a Team plan to access fleet management and usage tracking.</>
          ) : (
            <> Contact your organization admin for access.</>
          )}
        </p>
      </div>
    );
  }

  const totalSlots = computeNodes.reduce((sum, n) => sum + n.max_concurrent, 0);
  const totalLoad = schedulerStatus
    ? Object.values(schedulerStatus.nodes).reduce((sum, n) => sum + n.current_load, 0)
    : 0;
  const totalQueued = schedulerStatus
    ? Object.values(schedulerStatus.nodes).reduce((sum, n) => sum + n.queued.length, 0)
    : 0;

  const tabs: { id: AdminTab; label: string; icon: React.ReactNode }[] = [
    { id: 'fleet', label: 'Fleet', icon: <Server className="w-3.5 h-3.5" /> },
    { id: 'sync', label: 'Sync', icon: <Cloud className="w-3.5 h-3.5" /> },
    { id: 'usage', label: 'Usage', icon: <Activity className="w-3.5 h-3.5" /> },
    { id: 'security', label: 'Security', icon: <Shield className="w-3.5 h-3.5" /> },
    { id: 'policy', label: 'Policy', icon: <Settings2 className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
          <Shield className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-text flex items-center gap-2">
            Enterprise Admin
            <InfoTooltip content="Manage compute fleet, monitor sync status, track usage, and review security posture." />
          </h2>
          <p className="text-sm text-text-muted">
            {tier === 'enterprise' ? 'Enterprise' : 'Team'} plan · {computeNodes.length} node{computeNodes.length !== 1 ? 's' : ''} · {syncFleet.length} project{syncFleet.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPICard
          icon={<Server className="w-4 h-4" />}
          label="Compute Slots"
          value={`${totalLoad}/${totalSlots}`}
          detail={totalQueued > 0 ? `${totalQueued} queued` : 'No queue'}
          color={totalLoad >= totalSlots ? 'warning' : 'success'}
        />
        <KPICard
          icon={<Cloud className="w-4 h-4" />}
          label="Sync Fleet"
          value={String(syncFleet.filter(s => s.status === 'synced').length)}
          detail={`of ${syncFleet.length} projects synced`}
          color={syncFleet.some(s => s.status === 'error') ? 'error' : 'success'}
        />
        <KPICard
          icon={<Activity className="w-4 h-4" />}
          label="Tokens This Month"
          value={tokenUsage ? `${(tokenUsage.total_tokens / 1000).toFixed(0)}K` : (usage ? `${Math.round(usage.currentMonth.indexingMinutes)} min` : '—')}
          detail={tokenUsage ? `${tokenUsage.call_count} calls` : (usage ? `${usage.currentMonth.indexingRuns} runs` : 'No data')}
          color="info"
        />
        <KPICard
          icon={<Shield className="w-4 h-4" />}
          label="Security"
          value={securityHealth ? `${securityHealth.score}/${securityHealth.total}` : '—'}
          detail={securityHealth ? securityHealth.status : 'Not checked'}
          color={securityHealth?.status === 'critical' ? 'error' : securityHealth?.status === 'warnings' ? 'warning' : 'success'}
        />
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-[1px]",
              activeTab === tab.id
                ? "text-primary border-primary"
                : "text-text-muted border-transparent hover:text-text hover:border-border"
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'fleet' && (
        <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-text">Compute Fleet</h3>
          </div>
          {computeNodes.length === 0 ? (
            <p className="text-xs text-text-muted py-4 text-center">No compute nodes configured.</p>
          ) : (
            <div className="space-y-2">
              {computeNodes.map((node) => {
                const nodeStatus = schedulerStatus?.nodes[node.id];
                return (
                  <div key={node.id} className="flex items-center gap-3 p-3 rounded border border-border bg-surface-raised">
                    <span className={cn(
                      'w-2 h-2 rounded-full shrink-0',
                      node.type === 'cloud' ? 'bg-blue-400' : node.type === 'remote' ? 'bg-amber-400' : 'bg-emerald-400'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text">{node.name}</span>
                        <span className="text-[10px] text-text-muted capitalize px-1.5 py-0.5 rounded bg-surface border border-border">{node.type}</span>
                        {node.gpu_name && (
                          <span className="text-[10px] text-text-muted">{node.gpu_name}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <div className="text-sm font-mono font-semibold text-text">
                          {nodeStatus ? nodeStatus.current_load : 0}/{node.max_concurrent}
                        </div>
                        <div className="text-[10px] text-text-muted">slots</div>
                      </div>
                      {nodeStatus && nodeStatus.queued.length > 0 && (
                        <span className="text-[10px] text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">
                          {nodeStatus.queued.length} queued
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {activeTab === 'sync' && (
        <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Cloud className="w-4 h-4 text-primary" />
            <h3 className="text-sm font-semibold text-text">Sync Fleet</h3>
          </div>
          {syncFleet.length === 0 ? (
            <div className="text-center py-6">
              <Cloud className="w-8 h-8 text-text-muted mx-auto mb-2" />
              <p className="text-xs text-text-muted">No projects with Team Sync enabled.</p>
              <p className="text-[10px] text-text-muted mt-1">
                Add a <code className="text-primary">.runprep/team_config.json</code> to a project repo to enable sync.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {syncFleet.map((entry) => (
                <div key={entry.projectId} className="flex items-center gap-3 p-3 rounded border border-border bg-surface-raised">
                  <SyncStatusDot status={entry.status} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{entry.projectName}</div>
                    <div className="text-[10px] text-text-muted flex items-center gap-2">
                      {entry.lastSync ? (
                        <>
                          <Clock className="w-3 h-3" />
                          {new Date(entry.lastSync * 1000).toLocaleString()}
                        </>
                      ) : 'Never synced'}
                      {entry.lastCommit && (
                        <span className="font-mono">{entry.lastCommit.slice(0, 8)}</span>
                      )}
                    </div>
                    {entry.error && (
                      <div className="text-[10px] text-error mt-1">{entry.error}</div>
                    )}
                  </div>
                  {onSyncProject && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSyncProject(entry.projectId)}
                      disabled={entry.status === 'syncing'}
                      className="shrink-0"
                    >
                      <RefreshCw className={cn("w-3 h-3 mr-1", entry.status === 'syncing' && "animate-spin")} />
                      Sync
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* EA-H7: Usage & Stress Tab */}
      {activeTab === 'usage' && (
        <div className="space-y-4">
          {usage && (
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Resource Usage</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <UsageMeter label="Indexing Minutes" current={usage.currentMonth.indexingMinutes} max={usage.limits.maxIndexingMinutes} />
                <UsageMeter label="Storage" current={usage.currentMonth.storageGb} max={usage.limits.maxStorageGb} unit="GB" />
                <UsageMeter label="Active Seats" current={usage.currentMonth.activeSeats} max={usage.limits.maxSeats} />
              </div>
            </section>
          )}

          {tokenUsage && (
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-text">Token Usage (Current Month)</h3>
                </div>
                {onExportAuditLog && (
                  <Button variant="outline" size="sm" onClick={onExportAuditLog} className="text-xs">
                    <FileDown className="w-3 h-3 mr-1" /> Export
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded border border-border bg-surface-raised">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Total Tokens</div>
                  <div className="text-lg font-mono font-semibold text-text">{(tokenUsage.total_tokens / 1000).toFixed(1)}K</div>
                  <div className="text-[10px] text-text-muted">{tokenUsage.call_count} API calls</div>
                </div>
                {tokenUsage.estimated_cost_usd != null && (
                  <div className="p-3 rounded border border-border bg-surface-raised">
                    <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Est. Cost</div>
                    <div className="text-lg font-mono font-semibold text-text">${tokenUsage.estimated_cost_usd.toFixed(2)}</div>
                    <div className="text-[10px] text-text-muted">this month</div>
                  </div>
                )}
              </div>
              {Object.keys(tokenUsage.by_provider).length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider">By Provider</div>
                  {Object.entries(tokenUsage.by_provider).map(([provider, tokens]) => (
                    <div key={provider} className="flex items-center justify-between text-xs">
                      <span className="text-text-muted capitalize">{provider}</span>
                      <span className="font-mono text-text">{(tokens / 1000).toFixed(1)}K tokens</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* SEAT-2: Seat Management */}
          {seatStatus && (seatStatus.tier === 'team' || seatStatus.tier === 'enterprise') && (
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Seat Management</h3>
                <span className={cn(
                  "text-xs font-mono px-2 py-0.5 rounded ml-auto",
                  seatStatus.seats_used >= seatStatus.seats_total ? 'bg-amber-500/10 text-amber-500' : 'bg-success/10 text-success'
                )}>
                  {seatStatus.seats_used}/{seatStatus.seats_total} seats
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded border border-border bg-surface-raised">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Used</div>
                  <div className="text-lg font-mono font-semibold text-text">{seatStatus.seats_used}</div>
                </div>
                <div className="p-3 rounded border border-border bg-surface-raised">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Total</div>
                  <div className="text-lg font-mono font-semibold text-text">{seatStatus.seats_total}</div>
                </div>
                <div className="p-3 rounded border border-border bg-surface-raised">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Available</div>
                  <div className={cn("text-lg font-mono font-semibold", seatStatus.seats_total - seatStatus.seats_used <= 0 ? 'text-amber-500' : 'text-success')}>
                    {Math.max(0, seatStatus.seats_total - seatStatus.seats_used)}
                  </div>
                </div>
              </div>
              {seatStatus.activations.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[10px] text-text-muted uppercase tracking-wider">Active Machines</div>
                  {seatStatus.activations.map((act, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs p-2 rounded border border-border bg-surface-raised">
                      <span className={cn("w-2 h-2 rounded-full shrink-0", act.is_current ? "bg-success" : "bg-text-muted")} />
                      <span className="text-text font-medium">{act.machine}</span>
                      <span className="text-text-muted">{act.platform}</span>
                      {act.is_current && <span className="text-[10px] text-success ml-auto">This machine</span>}
                    </div>
                  ))}
                </div>
              )}
              {seatStatus.grace_days_remaining != null && seatStatus.grace_days_remaining < 30 && (
                <div className={cn(
                  "p-2 rounded border text-xs",
                  seatStatus.grace_days_remaining <= 7 ? "border-error/30 bg-error/5 text-error" : "border-amber-500/30 bg-amber-500/5 text-amber-400"
                )}>
                  {seatStatus.grace_days_remaining <= 0
                    ? "⚠ Offline grace period expired. Connect to internet to re-validate license."
                    : `⏱ Offline grace: ${seatStatus.grace_days_remaining} days remaining until license re-validation required.`
                  }
                </div>
              )}
              {seatStatus.seats_used >= seatStatus.seats_total && (
                <div className="p-2 rounded border border-amber-500/30 bg-amber-500/5 text-xs text-amber-400">
                  All seats are in use. To activate on another machine, deactivate one first or purchase additional seats at{' '}
                  <a href="https://runprep.io/pricing" target="_blank" rel="noreferrer" className="underline hover:text-amber-300">runprep.io/pricing</a>.
                </div>
              )}
              {/* Provision Seat Form */}
              <div className="pt-3 mt-3 border-t border-border">
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-2">Provision Seat</div>
                <form onSubmit={handleProvisionSeat} className="flex gap-2">
                  <input
                    type="email"
                    placeholder="Team member email..."
                    value={provisionEmail}
                    onChange={(e) => setProvisionEmail(e.target.value)}
                    className="flex-1 px-3 py-1.5 text-xs rounded border border-border bg-background text-text focus:outline-none focus:ring-1 focus:ring-primary"
                    disabled={provisionLoading}
                  />
                  <Button type="submit" size="sm" disabled={!provisionEmail.trim() || provisionLoading || seatStatus.seats_used >= seatStatus.seats_total}>
                    {provisionLoading ? 'Sending...' : 'Invite'}
                  </Button>
                </form>
                {provisionMessage && (
                  <div className={cn("mt-2 text-xs", provisionMessage.type === 'error' ? 'text-error' : 'text-success')}>
                    {provisionMessage.text}
                  </div>
                )}
              </div>
            </section>
          )}

          {!usage && !tokenUsage && !seatStatus && (
            <div className="text-center py-8 text-sm text-text-muted">
              No usage data available yet. Usage tracking begins after the first pipeline run.
            </div>
          )}
        </div>
      )}

      {/* EA-I10: Security & Compliance Tab */}
      {activeTab === 'security' && (
        <div className="space-y-4">
          {securityHealth && (
            <>
              {/* Overall Score */}
              <section className="rounded-lg border border-border bg-surface p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Shield className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold text-text">Security Health</h3>
                      <p className="text-[10px] text-text-muted">{securityHealth.total} automated checks across 5 categories</p>
                    </div>
                    <span className={cn(
                      "text-lg font-mono font-bold px-3 py-1 rounded-lg",
                      securityHealth.status === 'healthy' ? 'bg-success/10 text-success' :
                      securityHealth.status === 'warnings' ? 'bg-amber-500/10 text-amber-500' :
                      'bg-error/10 text-error'
                    )}>
                      {securityHealth.score}/{securityHealth.total}
                    </span>
                  </div>
                  {onExportSecurityReport && (
                    <Button variant="outline" size="sm" onClick={onExportSecurityReport} className="text-xs">
                      <FileDown className="w-3 h-3 mr-1" /> Export Report
                    </Button>
                  )}
                </div>
              </section>

              {/* Grouped checks — match by name so grouping is stable across backend changes */}
              {(() => {
                const checks = securityHealth.checks;
                const byName = (names: string[]) => checks.filter(c => names.includes(c.name));
                const INFRA = ['Network Security', 'Daemon Authentication', 'CORS Configuration'];
                const COMPLIANCE = ['License Verification', 'Dev Mode Detection', 'DLP Compliance'];
                const DATA = ['Content Sanitization', 'S3 Endpoint Security', 'Index Integrity', 'API Key Hygiene', 'Secret Detection Coverage', 'Unicode Injection Scan'];
                const RUNTIME = ['MCP Rate Limiting', 'Secrets & Credentials', 'Config Drift'];
                const EXPOSURE = ['Data Exposure Summary'];
                const assigned = new Set([...INFRA, ...COMPLIANCE, ...DATA, ...RUNTIME, ...EXPOSURE]);
                const ungrouped = checks.filter(c => !assigned.has(c.name));
                const groups = [
                  { label: 'Infrastructure', icon: <Server className="w-3.5 h-3.5" />, checks: byName(INFRA) },
                  { label: 'License & Compliance', icon: <Shield className="w-3.5 h-3.5" />, checks: byName(COMPLIANCE) },
                  { label: 'Data Protection', icon: <Lock className="w-3.5 h-3.5" />, checks: byName(DATA) },
                  { label: 'Runtime', icon: <Activity className="w-3.5 h-3.5" />, checks: byName(RUNTIME) },
                  { label: 'Data Exposure', icon: <Activity className="w-3.5 h-3.5" />, checks: [...byName(EXPOSURE), ...ungrouped] },
                ].filter(g => g.checks.length > 0);
                return (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {groups.map((group) => {
                      const groupPass = group.checks.every(c => c.status === 'pass');
                      const groupFail = group.checks.some(c => c.status === 'fail');
                      return (
                        <section key={group.label} className={cn(
                          "rounded-lg border p-3 space-y-2",
                          groupFail ? "border-error/30 bg-error/5" :
                          !groupPass ? "border-amber-500/30 bg-amber-500/5" :
                          "border-border bg-surface"
                        )}>
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              groupFail ? "text-error" : !groupPass ? "text-amber-500" : "text-success"
                            )}>{group.icon}</span>
                            <span className="text-xs font-semibold text-text">{group.label}</span>
                            <span className={cn(
                              "text-[10px] font-mono ml-auto px-1.5 py-0.5 rounded",
                              groupFail ? "bg-error/10 text-error" :
                              !groupPass ? "bg-amber-500/10 text-amber-500" :
                              "bg-success/10 text-success"
                            )}>
                              {group.checks.filter(c => c.status === 'pass').length}/{group.checks.length}
                            </span>
                          </div>
                          {group.checks.map((check, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs pl-1">
                              {check.status === 'pass' ? (
                                <CheckCircle className="w-3 h-3 text-success shrink-0 mt-0.5" />
                              ) : check.status === 'warn' ? (
                                <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0 mt-0.5" />
                              ) : (
                                <XCircle className="w-3 h-3 text-error shrink-0 mt-0.5" />
                              )}
                              <div className="min-w-0">
                                <span className="text-text">{check.name}</span>
                                {check.issues.length > 0 && (
                                  <p className="text-[10px] text-text-muted mt-0.5 truncate">{check.issues[0]}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </section>
                      );
                    })}
                  </div>
                );
              })()}
            </>
          )}

          {securityEvents.length > 0 && (
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-text">Recent Security Events</h3>
                </div>
                {onExportAuditLog && (
                  <Button variant="outline" size="sm" onClick={onExportAuditLog} className="text-xs">
                    <FileDown className="w-3 h-3 mr-1" /> Export Log
                  </Button>
                )}
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {securityEvents.slice(0, 20).map((evt, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className={cn(
                      "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                      evt.severity === 'CRITICAL' ? 'bg-error' :
                      evt.severity === 'WARNING' ? 'bg-amber-400' : 'bg-primary'
                    )} />
                    <div className="min-w-0">
                      <span className="text-text-muted">{new Date(evt.timestamp * 1000).toLocaleString()}</span>
                      <span className="ml-2 text-text">{evt.message || evt.event_type}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {!securityHealth && securityEvents.length === 0 && (
            <div className="text-center py-8 text-sm text-text-muted">
              Security health data not yet available. Run a security check to see results.
            </div>
          )}
        </div>
      )}

      {/* Policy Tab — Admin Policy from team_config.json */}
      {activeTab === 'policy' && (
        <div className="space-y-4">
          {adminPolicy ? (
            <>
              {/* Provider Restrictions */}
              <AdminSection title="Provider Policy" enforcementMode={adminPolicy.enforcement_mode as 'suggest' | 'enforce'}>
                <div className="space-y-2 text-xs">
                  {adminPolicy.provider.allowed_providers.length > 0 && (
                    <div className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                      <div>
                        <span className="font-medium text-text">Allowed providers:</span>{' '}
                        <span className="text-text-muted">{adminPolicy.provider.allowed_providers.join(', ')}</span>
                      </div>
                    </div>
                  )}
                  {adminPolicy.provider.blocked_providers.length > 0 && (
                    <div className="flex items-start gap-2">
                      <XCircle className="w-3.5 h-3.5 text-error shrink-0 mt-0.5" />
                      <div>
                        <span className="font-medium text-text">Blocked providers:</span>{' '}
                        <span className="text-text-muted">{adminPolicy.provider.blocked_providers.join(', ')}</span>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    {adminPolicy.provider.allow_local_providers ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-error" />
                    )}
                    <span className="text-text-muted">Local providers (Ollama, LM Studio): {adminPolicy.provider.allow_local_providers ? 'Allowed' : 'Blocked'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {adminPolicy.provider.allow_user_endpoints ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    ) : (
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    <span className="text-text-muted">User-created endpoints: {adminPolicy.provider.allow_user_endpoints ? 'Allowed' : 'IT-managed only'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {adminPolicy.provider.allow_user_api_keys ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    ) : (
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    <span className="text-text-muted">User API keys: {adminPolicy.provider.allow_user_api_keys ? 'Allowed' : 'IT-managed via env vars'}</span>
                  </div>
                  {adminPolicy.provider.locked_endpoints.length > 0 && (
                    <div className="mt-2 p-2 rounded bg-amber-500/5 border border-amber-500/20">
                      <div className="text-[10px] font-medium text-amber-400 mb-1 flex items-center gap-1">
                        <Lock className="w-3 h-3" /> {adminPolicy.provider.locked_endpoints.length} IT-configured endpoint{adminPolicy.provider.locked_endpoints.length !== 1 ? 's' : ''}
                      </div>
                      {adminPolicy.provider.locked_endpoints.map((le, i) => (
                        <div key={i} className="text-[10px] text-text-muted">{le.name || le.provider} — {le.url}</div>
                      ))}
                    </div>
                  )}
                </div>
              </AdminSection>

              {/* Model Restrictions */}
              <AdminSection title="Model Policy" enforcementMode={adminPolicy.enforcement_mode as 'suggest' | 'enforce'}>
                <div className="space-y-2 text-xs">
                  {adminPolicy.model.allowed_models.length > 0 && (
                    <div className="flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                      <div>
                        <span className="font-medium text-text">Allowed models:</span>{' '}
                        <span className="text-text-muted">{adminPolicy.model.allowed_models.join(', ')}</span>
                      </div>
                    </div>
                  )}
                  {adminPolicy.model.blocked_models.length > 0 && (
                    <div className="flex items-start gap-2">
                      <XCircle className="w-3.5 h-3.5 text-error shrink-0 mt-0.5" />
                      <div>
                        <span className="font-medium text-text">Blocked models:</span>{' '}
                        <span className="text-text-muted">{adminPolicy.model.blocked_models.join(', ')}</span>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    {adminPolicy.model.require_approved_models ? (
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    )}
                    <span className="text-text-muted">{adminPolicy.model.require_approved_models ? 'Only approved models allowed' : 'Any model allowed'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {adminPolicy.model.allow_any_local_model ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    ) : (
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    <span className="text-text-muted">Local model freedom: {adminPolicy.model.allow_any_local_model ? 'Any model on local endpoints' : 'Allowlist applies to local too'}</span>
                  </div>
                  {adminPolicy.model.slot_overrides && Object.keys(adminPolicy.model.slot_overrides).length > 0 && (
                    <div className="mt-2 p-2 rounded bg-surface-raised border border-border">
                      <div className="text-[10px] font-medium text-text uppercase tracking-wider mb-1.5 flex items-center gap-1">
                        <Cpu className="w-3 h-3 text-primary" /> Per-Slot Overrides ({Object.keys(adminPolicy.model.slot_overrides).length})
                      </div>
                      <div className="space-y-2">
                        {Object.entries(adminPolicy.model.slot_overrides).map(([slot, override]) => (
                          <div key={slot} className="text-xs">
                            <span className="text-text font-medium capitalize">{slot} slot:</span>
                            {override.allowed_models && override.allowed_models.length > 0 && (
                              <span className="text-text-muted ml-2">Allow: {override.allowed_models.join(', ')}</span>
                            )}
                            {override.require_approved_models && (
                              <span className="text-amber-400 ml-2">(Strict)</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </AdminSection>

              {/* DLP / Data Policy */}
              {(adminPolicy.data.never_send_globs.length > 0 || adminPolicy.data.block_unapproved_cloud) && (
                <AdminSection title="Data Loss Prevention" enforcementMode={adminPolicy.enforcement_mode as 'suggest' | 'enforce'}>
                  <div className="space-y-2 text-xs">
                    {adminPolicy.data.never_send_globs.length > 0 && (
                      <div className="flex items-start gap-2">
                        <Shield className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-medium text-text">Never send to cloud:</span>{' '}
                          <span className="text-text-muted font-mono">{adminPolicy.data.never_send_globs.join(', ')}</span>
                        </div>
                      </div>
                    )}
                    {adminPolicy.data.block_unapproved_cloud && (
                      <div className="flex items-center gap-2">
                        <Lock className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-text-muted">Unapproved cloud providers blocked</span>
                        {adminPolicy.data.allowed_destinations.length > 0 && (
                          <span className="text-text-muted"> (allowed: {adminPolicy.data.allowed_destinations.join(', ')})</span>
                        )}
                      </div>
                    )}
                    {adminPolicy.data.redact_patterns.length > 0 && (
                      <div className="flex items-center gap-2">
                        <Shield className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-text-muted">{adminPolicy.data.redact_patterns.length} secret redaction pattern{adminPolicy.data.redact_patterns.length !== 1 ? 's' : ''} active</span>
                      </div>
                    )}
                  </div>
                </AdminSection>
              )}

              {/* Budget Limits */}
              {(adminPolicy.budgets.monthly_token_limit > 0 || adminPolicy.budgets.monthly_cost_limit_usd > 0) && (
                <AdminSection title="Budget Limits" enforcementMode={adminPolicy.enforcement_mode as 'suggest' | 'enforce'}>
                  <div className="space-y-2 text-xs">
                    {adminPolicy.budgets.monthly_token_limit > 0 && (
                      <div className="flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5 text-primary" />
                        <span className="text-text-muted">Monthly token limit: <strong className="text-text">{(adminPolicy.budgets.monthly_token_limit / 1000).toFixed(0)}K</strong></span>
                      </div>
                    )}
                    {adminPolicy.budgets.monthly_cost_limit_usd > 0 && (
                      <div className="flex items-center gap-2">
                        <DollarSign className="w-3.5 h-3.5 text-primary" />
                        <span className="text-text-muted">Monthly cost limit: <strong className="text-text">${adminPolicy.budgets.monthly_cost_limit_usd.toFixed(2)}</strong></span>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-text-muted">Alert at {Math.round(adminPolicy.budgets.alert_threshold_percent * 100)}% of limit</span>
                    </div>
                  </div>
                </AdminSection>
              )}
            </>
          ) : (
            <div className="text-center py-8">
              <Settings2 className="w-8 h-8 text-text-muted mx-auto mb-2" />
              <p className="text-sm text-text-muted">No admin policy configured.</p>
              <p className="text-[10px] text-text-muted mt-1">
                Add an <code className="text-primary">admin_policy</code> section to your <code className="text-primary">.runprep/team_config.json</code> to set provider locks, model restrictions, and DLP rules.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function KPICard({ icon, label, value, detail, color }: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  color: 'success' | 'warning' | 'error' | 'info';
}) {
  const colorMap = {
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-error',
    info: 'text-primary',
  };
  return (
    <div className="p-3 rounded-lg border border-border bg-surface-raised">
      <div className="flex items-center gap-1.5 text-text-muted mb-2">
        {icon}
        <span className="text-[10px] font-medium uppercase tracking-wider">{label}</span>
      </div>
      <div className={cn("text-xl font-semibold font-mono", colorMap[color])}>{value}</div>
      <div className="text-[10px] text-text-muted mt-0.5">{detail}</div>
    </div>
  );
}

function SyncStatusDot({ status }: { status: SyncFleetEntry['status'] }) {
  const styles = {
    synced: 'bg-success',
    syncing: 'bg-primary animate-pulse',
    stale: 'bg-amber-400',
    error: 'bg-error',
    disabled: 'bg-text-muted',
  };
  return <span className={cn('w-2 h-2 rounded-full shrink-0', styles[status])} />;
}

function UsageMeter({ label, current, max, unit = '' }: {
  label: string;
  current: number;
  max: number | null;
  unit?: string;
}) {
  const pct = max ? Math.min(100, (current / max) * 100) : 0;
  const isHigh = max ? pct > 80 : false;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted">{label}</span>
        <span className={cn("font-mono font-medium", isHigh ? 'text-warning' : 'text-text')}>
          {Math.round(current)}{unit}{max ? ` / ${max}${unit}` : ''}
        </span>
      </div>
      {max && (
        <div className="h-1.5 bg-surface rounded-full overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all", isHigh ? 'bg-warning' : 'bg-primary/60')}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
