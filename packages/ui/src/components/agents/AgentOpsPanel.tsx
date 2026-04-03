/**
 * AgentOpsPanel — Modular dashboard panel for Agent Operations (Level 1).
 *
 * Shows 3 compact AgentCards (HR, Researcher, Custodian) plus managed employee
 * badges. This is the panel-level view; clicking "Details" opens the full overlay.
 */
import { Users, Search, Trash2 } from 'lucide-react';
import { AgentCard } from './AgentCard';
import { EmployeeBadges, type RoleBadge } from './EmployeeBadges';

export interface AgentOpsData {
  hr: {
    role_count: number;
    roles: string[];
  };
  researcher: {
    run_count: number;
    latest_run: string | null;
  };
  custodian: {
    archive_count: number;
  };
  roster?: RoleBadge[];
}

export interface AgentOpsPanelProps {
  data: AgentOpsData | null;
  loading?: boolean;
  onHRGenerate?: () => void;
  onResearchRun?: () => void;
  onCustodianRun?: () => void;
  className?: string;
}

export function AgentOpsPanel({
  data,
  loading = false,
  onHRGenerate,
  onResearchRun,
  onCustodianRun,
  className = '',
}: AgentOpsPanelProps) {
  if (loading || !data) {
    return (
      <div className={`flex items-center justify-center p-8 text-muted-foreground ${className}`}>
        {loading ? 'Loading agent status...' : 'No project selected'}
      </div>
    );
  }

  const isEmpty = data.hr.role_count === 0
    && data.researcher.run_count === 0
    && data.custodian.archive_count === 0;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Getting Started — shown when no agents have been used yet */}
      {isEmpty && (
        <div className="rounded-lg border border-dashed border-border bg-muted/30 p-4">
          <h4 className="font-medium text-sm mb-2">Get Started with Agent Operations</h4>
          <ol className="text-xs text-muted-foreground space-y-1.5 list-decimal pl-4">
            <li>Ensure an LLM is configured in the <span className="font-medium text-foreground">AI Gateway</span> panel</li>
            <li>Generate roles: <code className="bg-muted px-1 rounded">codrag hr-generate --mode auto</code></li>
            <li>Run research: <code className="bg-muted px-1 rounded">codrag research-run</code></li>
            <li>Scan for dead code: <code className="bg-muted px-1 rounded">codrag custodian-run</code></li>
          </ol>
          <p className="text-xs text-muted-foreground mt-2">
            Run <code className="bg-muted px-1 rounded">codrag agents</code> for a full command reference.
          </p>
        </div>
      )}

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <AgentCard
          name="HR Agent"
          description="Generates and manages AI agent role definitions"
          icon={<Users size={16} />}
          status={data.hr.role_count > 0 ? 'fresh' : 'pending'}
          metric={String(data.hr.role_count)}
          metricLabel="roles"
          onAction={onHRGenerate}
          actionLabel="Generate"
        />
        <AgentCard
          name="Researcher"
          description="Mines audit findings and formulates plans"
          icon={<Search size={16} />}
          status={data.researcher.run_count > 0 ? 'fresh' : 'pending'}
          metric={String(data.researcher.run_count)}
          metricLabel="research runs"
          lastRun={data.researcher.latest_run}
          onAction={onResearchRun}
          actionLabel="Run"
        />
        <AgentCard
          name="Custodian"
          description="Detects dead code and plans cleanup"
          icon={<Trash2 size={16} />}
          status={data.custodian.archive_count > 0 ? 'fresh' : 'pending'}
          metric={String(data.custodian.archive_count)}
          metricLabel="archived"
          onAction={onCustodianRun}
          actionLabel="Scan"
        />
      </div>

      {/* Employee Badges */}
      {data.roster && data.roster.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-2">
            Managed Employees
          </h4>
          <EmployeeBadges roles={data.roster} />
        </div>
      )}
    </div>
  );
}
