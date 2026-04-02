/**
 * SystemAgentsTab — Per-agent config sections in the detail overlay.
 *
 * Shows readiness, last run info, and action buttons for each agent.
 */
import { Users, Search, Trash2 } from 'lucide-react';
import { StatusBadge } from '../status/StatusBadge';

export interface SystemAgentsData {
  hr: {
    readiness: { score: number; ready_for_list: boolean; ready_for_auto: boolean; missing: string[] };
    roleCount: number;
  };
  researcher: {
    runCount: number;
    latestRun: string | null;
  };
  custodian: {
    archiveCount: number;
  };
}

export interface SystemAgentsTabProps {
  data: SystemAgentsData | null;
  onResearchRun?: (maxTopics: number) => void;
  onCustodianRun?: (dryRun: boolean) => void;
  className?: string;
}

export function SystemAgentsTab({
  data,
  onResearchRun,
  onCustodianRun,
  className = '',
}: SystemAgentsTabProps) {
  if (!data) {
    return <div className="text-muted-foreground">No data available</div>;
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* HR Agent Section */}
      <section className="rounded-lg border border-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Users size={18} className="text-muted-foreground" />
          <h3 className="font-semibold">HR Agent (Staffing)</h3>
          <StatusBadge status={data.hr.roleCount > 0 ? 'fresh' : 'pending'} />
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Readiness Score:</span>
            <span className="ml-2 font-medium">{(data.hr.readiness.score * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="text-muted-foreground">Roles Generated:</span>
            <span className="ml-2 font-medium">{data.hr.roleCount}</span>
          </div>
          <div>
            <span className="text-muted-foreground">List Mode:</span>
            <span className="ml-2">{data.hr.readiness.ready_for_list ? 'Ready' : 'Not ready'}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Auto Mode:</span>
            <span className="ml-2">{data.hr.readiness.ready_for_auto ? 'Ready' : 'Not ready'}</span>
          </div>
        </div>
        {data.hr.readiness.missing.length > 0 && (
          <div className="mt-3 text-xs text-yellow-600 dark:text-yellow-400">
            Missing: {data.hr.readiness.missing.slice(0, 3).join('; ')}
          </div>
        )}
      </section>

      {/* Researcher Section */}
      <section className="rounded-lg border border-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Search size={18} className="text-muted-foreground" />
          <h3 className="font-semibold">Researcher Agent</h3>
          <StatusBadge status={data.researcher.runCount > 0 ? 'fresh' : 'pending'} />
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Research Runs:</span>
            <span className="ml-2 font-medium">{data.researcher.runCount}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Latest Run:</span>
            <span className="ml-2">{data.researcher.latestRun?.slice(0, 10) ?? 'Never'}</span>
          </div>
        </div>
        {onResearchRun && (
          <button
            onClick={() => onResearchRun(3)}
            className="mt-3 text-xs px-3 py-1.5 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
          >
            Run Research (3 topics)
          </button>
        )}
      </section>

      {/* Custodian Section */}
      <section className="rounded-lg border border-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <Trash2 size={18} className="text-muted-foreground" />
          <h3 className="font-semibold">Digital Custodian</h3>
          <StatusBadge status={data.custodian.archiveCount > 0 ? 'fresh' : 'pending'} />
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Archived Items:</span>
            <span className="ml-2 font-medium">{data.custodian.archiveCount}</span>
          </div>
        </div>
        {onCustodianRun && (
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => onCustodianRun(true)}
              className="text-xs px-3 py-1.5 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
            >
              Dry Run
            </button>
            <button
              onClick={() => onCustodianRun(false)}
              className="text-xs px-3 py-1.5 rounded bg-red-500/10 text-red-600 hover:bg-red-500/20 transition-colors"
            >
              Live Run
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
