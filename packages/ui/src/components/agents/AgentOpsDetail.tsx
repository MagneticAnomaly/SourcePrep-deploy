/**
 * AgentOpsDetail — Full detail overlay for Agent Operations (Level 2).
 *
 * Two tabs: System Agents (3 agent configs) and Managed Employees (roster).
 * Opened when user clicks "Details" on the AgentOpsPanel.
 */
import { useState } from 'react';
import { SystemAgentsTab, type SystemAgentsData } from './SystemAgentsTab';
import { ManagedEmployeesTab, type ManagedEmployeesData } from './ManagedEmployeesTab';

export interface AgentOpsDetailProps {
  systemData: SystemAgentsData | null;
  employeeData: ManagedEmployeesData | null;
  loading?: boolean;
  onHRGenerate?: (mode: string, roleNames: string[]) => void;
  onResearchRun?: (maxTopics: number) => void;
  onCustodianRun?: (dryRun: boolean) => void;
  className?: string;
}

export function AgentOpsDetail({
  systemData,
  employeeData,
  loading = false,
  onHRGenerate,
  onResearchRun,
  onCustodianRun,
  className = '',
}: AgentOpsDetailProps) {
  const [activeTab, setActiveTab] = useState<'system' | 'employees'>('system');

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Tab Bar */}
      <div className="flex border-b border-border">
        <button
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'system'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('system')}
        >
          System Agents
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'employees'
              ? 'border-b-2 border-primary text-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('employees')}
        >
          Managed Employees
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground">
            Loading...
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
