/**
 * AgentOpsPanel — Config-only dashboard panel for Agent Operations.
 *
 * Shows engine control rows (Run/Generate/Scan with last-run + push count),
 * Paperclip connection status, and push settings.
 * No operational monitoring — that belongs in Paperclip.
 */
import { Users, Search, Trash2 } from 'lucide-react';
import { MCPConnectionCard, type MCPStatusData, type MCPInstallResult } from './MCPConnectionCard';
import {
  WorkspaceMcpCard,
  type WorkspaceMcpStatusData,
  type WorkspaceMcpInstallResult,
} from './WorkspaceMcpCard';
import { PushSettings, type PushSettingsData } from './PushSettings';

export interface EngineStatus {
  last_run: string | null;
  push_count: number;
}

export interface AgentOpsData {
  hr: EngineStatus;
  researcher: EngineStatus;
  custodian: EngineStatus;
}

export interface AgentOpsPanelProps {
  data: AgentOpsData | null;
  loading?: boolean;
  onHRGenerate?: () => void;
  onResearchRun?: () => void;
  onCustodianRun?: () => void;
  mcpStatus?: MCPStatusData | null;
  mcpLoading?: boolean;
  onMCPInstall?: () => Promise<MCPInstallResult>;
  onMCPUninstall?: () => Promise<void>;
  onMCPRefresh?: () => void;
  workspaceMcpStatus?: WorkspaceMcpStatusData | null;
  workspaceMcpDefaultPath?: string | null;
  onWorkspaceMcpInstall?: (workspacePath: string) => Promise<WorkspaceMcpInstallResult>;
  onWorkspaceMcpUninstall?: (workspacePath: string) => Promise<void>;
  onWorkspaceMcpRefresh?: (workspacePath: string) => void;
  pushSettings?: PushSettingsData | null;
  pushSettingsLoading?: boolean;
  onPushSettingsUpdate?: (settings: PushSettingsData) => void;
  className?: string;
}

interface EngineRowProps {
  name: string;
  description: string;
  icon: React.ReactNode;
  status: EngineStatus | null;
  onAction?: () => void;
  actionLabel: string;
}

function EngineRow({ name, description, icon, status, onAction, actionLabel }: EngineRowProps) {
  return (
    <div className="flex items-center gap-3 py-2 px-2 rounded-md hover:bg-muted/30 transition-colors">
      <div className="text-muted-foreground shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{name}</div>
        <div className="text-xs text-muted-foreground truncate">{description}</div>
      </div>
      <div className="text-right shrink-0 mr-2">
        {status?.last_run ? (
          <div className="text-[10px] text-muted-foreground">
            {status.push_count > 0 && (
              <span className="text-primary">{status.push_count} pushed</span>
            )}
            {status.push_count > 0 && ' · '}
            {status.last_run}
          </div>
        ) : (
          <div className="text-[10px] text-muted-foreground italic">Not yet run</div>
        )}
      </div>
      {onAction && (
        <button
          onClick={onAction}
          className="shrink-0 px-2.5 py-1 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function AgentOpsPanel({
  data,
  loading = false,
  onHRGenerate,
  onResearchRun,
  onCustodianRun,
  mcpStatus,
  mcpLoading = false,
  onMCPInstall,
  onMCPUninstall,
  onMCPRefresh,
  workspaceMcpStatus,
  workspaceMcpDefaultPath,
  onWorkspaceMcpInstall,
  onWorkspaceMcpUninstall,
  onWorkspaceMcpRefresh,
  pushSettings,
  pushSettingsLoading = false,
  onPushSettingsUpdate,
  className = '',
}: AgentOpsPanelProps) {
  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 text-muted-foreground ${className}`}>
        Loading agent config...
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-1">Engines</h4>
        <div className="divide-y divide-border/50">
          <EngineRow
            name="HR Agent"
            description="Generate and audit agent role definitions"
            icon={<Users size={14} />}
            status={data?.hr ?? null}
            onAction={onHRGenerate}
            actionLabel="Generate"
          />
          <EngineRow
            name="Researcher"
            description="Mine audit findings, formulate plans"
            icon={<Search size={14} />}
            status={data?.researcher ?? null}
            onAction={onResearchRun}
            actionLabel="Research"
          />
          <EngineRow
            name="Custodian"
            description="Detect dead code, plan cleanup"
            icon={<Trash2 size={14} />}
            status={data?.custodian ?? null}
            onAction={onCustodianRun}
            actionLabel="Scan"
          />
        </div>
      </div>
      <MCPConnectionCard
        status={mcpStatus ?? null}
        loading={mcpLoading}
        onInstall={onMCPInstall}
        onUninstall={onMCPUninstall}
        onRefresh={onMCPRefresh}
      />
      <WorkspaceMcpCard
        defaultWorkspacePath={workspaceMcpDefaultPath ?? null}
        status={workspaceMcpStatus ?? null}
        onInstall={onWorkspaceMcpInstall}
        onUninstall={onWorkspaceMcpUninstall}
        onRefresh={onWorkspaceMcpRefresh}
      />
      <PushSettings
        settings={pushSettings ?? null}
        loading={pushSettingsLoading}
        onUpdate={onPushSettingsUpdate}
      />
    </div>
  );
}
