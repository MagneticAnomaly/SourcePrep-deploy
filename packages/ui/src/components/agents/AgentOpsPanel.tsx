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

  return (
    <div className={`space-y-4 ${className}`}>
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
