import { useState } from 'react';
import { cn } from '../../lib/utils';
import { Shield, Server, Activity, DollarSign, Cloud, RefreshCw, Clock, CheckCircle, AlertTriangle, XCircle, FileDown } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';
import type { ComputeNode, SchedulerStatus } from '../../types';

export type AdminTab = 'fleet' | 'sync' | 'usage' | 'security';

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
  defaultTab = 'fleet',
  className,
}: EnterpriseAdminPanelProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>(defaultTab);

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
                Add a <code className="text-primary">.codrag/team_config.json</code> to a project repo to enable sync.
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

          {!usage && !tokenUsage && (
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
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold text-text">Security Health</h3>
                  <span className={cn(
                    "text-xs font-mono px-2 py-0.5 rounded",
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
              <div className="space-y-2">
                {securityHealth.checks.map((check, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    {check.status === 'pass' ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success shrink-0" />
                    ) : check.status === 'warn' ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-error shrink-0" />
                    )}
                    <span className="text-text">{check.name}</span>
                    {check.issues.length > 0 && (
                      <span className="text-text-muted truncate">{check.issues[0]}</span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {securityEvents.length > 0 && (
            <section className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-text">Recent Security Events</h3>
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
