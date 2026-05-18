// MCP Connection (Phase 67 — Paperclip Integration)
export { MCPConnectionCard } from './MCPConnectionCard';
export type {
  MCPConnectionCardProps,
  MCPStatusData,
  MCPRuntimeStatus,
  MCPInstallResult,
} from './MCPConnectionCard';

// Workspace MCP Installer ("Enable Prep for Workspace")
export { WorkspaceMcpCard } from './WorkspaceMcpCard';
export type {
  WorkspaceMcpCardProps,
  WorkspaceMcpStatusData,
  WorkspaceRuntimeStatus,
  WorkspaceMcpInstallResult,
} from './WorkspaceMcpCard';

// Agent Operations — Config-Only (Unified Surfaces)
export { AgentOpsPanel } from './AgentOpsPanel';
export type { AgentOpsData, AgentOpsPanelProps, EngineStatus } from './AgentOpsPanel';

// Push Settings (Unified Surfaces)
export { PushSettings } from './PushSettings';
export type { PushSettingsData, PushSettingsProps } from './PushSettings';

// ── Components kept for Storybook / future use but NOT rendered in dashboard ──
// AgentCard, AgentOpsDetail, EmployeeBadges, SystemAgentsTab,
// ManagedEmployeesTab, GenerateWizard, ResearchTopicList, CleanupPreview
// Import these directly from their files if needed outside the dashboard.
