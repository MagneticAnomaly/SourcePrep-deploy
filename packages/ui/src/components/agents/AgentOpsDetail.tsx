/**
 * AgentOpsDetail — Full detail overlay for Agent Operations.
 *
 * Three tabs:
 * - Actions: Run agent tasks (generate roles, research, cleanup)
 * - System Agents: Per-agent config sections with readiness and metrics
 * - Managed Employees: Roster table with completion status
 */
import { useState } from 'react';
import { SystemAgentsTab, type SystemAgentsData } from './SystemAgentsTab';
import { ManagedEmployeesTab, type ManagedEmployeesData } from './ManagedEmployeesTab';
import { GenerateWizard } from './GenerateWizard';
import { ResearchTopicList, type ResearchRun } from './ResearchTopicList';
import { CleanupPreview, type CleanupCandidate } from './CleanupPreview';

export interface AgentOpsDetailProps {
  systemData: SystemAgentsData | null;
  employeeData: ManagedEmployeesData | null;
  researchRuns: ResearchRun[];
  cleanupCandidates: CleanupCandidate[];
  loading?: boolean;
  generating?: boolean;
  researching?: boolean;
  scanning?: boolean;
  onHRGenerate?: (mode: string, roleNames: string[]) => void;
  onResearchRun?: (maxTopics: number) => void;
  onCustodianRun?: (dryRun: boolean) => void;
  className?: string;
}

export function AgentOpsDetail({
  systemData,
  employeeData,
  researchRuns,
  cleanupCandidates,
  loading = false,
  generating = false,
  researching = false,
  scanning = false,
  onHRGenerate,
  onResearchRun,
  onCustodianRun,
  className = '',
}: AgentOpsDetailProps) {
  const [activeTab, setActiveTab] = useState<'actions' | 'system' | 'employees'>('actions');

  const tabs = [
    { id: 'actions' as const, label: 'Actions' },
    { id: 'system' as const, label: 'System Agents' },
    { id: 'employees' as const, label: 'Managed Employees' },
  ];

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Tab Bar */}
      <div className="flex border-b border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground">
            Loading...
          </div>
        ) : activeTab === 'actions' ? (
          <div className="space-y-6 max-w-3xl">
            {/* HR Generate */}
            {onHRGenerate && systemData && (
              <GenerateWizard
                readinessScore={systemData.hr.readiness.score}
                readyForList={systemData.hr.readiness.ready_for_list}
                readyForAuto={systemData.hr.readiness.ready_for_auto}
                onGenerate={onHRGenerate}
                generating={generating}
              />
            )}

            {/* Research */}
            {onResearchRun && (
              <ResearchTopicList
                runs={researchRuns}
                onRun={onResearchRun}
                running={researching}
              />
            )}

            {/* Custodian */}
            {onCustodianRun && (
              <CleanupPreview
                candidates={cleanupCandidates}
                archiveCount={systemData?.custodian.archiveCount ?? 0}
                onScan={onCustodianRun}
                scanning={scanning}
              />
            )}
          </div>
        ) : activeTab === 'system' ? (
          <SystemAgentsTab
            data={systemData}
            onResearchRun={onResearchRun}
            onCustodianRun={onCustodianRun}
          />
        ) : (
          <ManagedEmployeesTab
            data={employeeData}
            onGenerate={onHRGenerate}
          />
        )}
      </div>
    </div>
  );
}
