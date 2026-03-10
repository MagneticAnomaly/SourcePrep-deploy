// CoDRAG UI - Shared Component Library
// This package provides the design system foundation for CoDRAG app and website

// Utilities
export { cn } from './lib/utils';
export { getTaskTokenEstimate, estimateTaskTokens, getTaskTokenDescription, getTaskTokenVolume } from './lib/token-estimates';
export type { TaskTokenEstimate, TokenVolume } from './lib/token-estimates';

// Types
export type { 
  StatusState, 
  SearchResult, 
  CodeChunk, 
  ProjectSummary, 
  ProjectConfig,
  ActivityStatus,
  ProjectAdvancedConfig,
  AdvancedConfig,
  ProjectMode,
  LLMConfig,
  AssignmentMode,
  LLMAssignmentBlock,
  SavedEndpoint, 
  EndpointTestResult,
  ModelReadinessStatus,
  ModelStatusResult,
  ProjectStatus,
  WatchStatus,
  WatchState,
  ApiError,
  TraceCoverageFile,
  TraceCoverageSummary,
  TraceCoverage,
  LicenseTier,
  UserRole,
  LicenseInfo,
  LicenseStatus,
  FeatureAvailability,
  AdminPolicy,
  ProviderPolicy,
  ModelPolicy,
  DataPolicy,
  SyncPolicy,
  NetworkPolicy,
  BudgetPolicy,
  TaskProgress,
  LogEntry,
  EvidenceTier,
  DeepEnrichmentConfig,
  DeepEnrichmentRunStatus,
  DeepAnalysisScheduleConfig,
  DeepAnalysisRunStatus,
  TraceAugmentation,
  InferredEdgesStatus,
  AugmentationStatus,
  EpistemicStatus,
  ModuleStatus,
  DeepeningStatus,
  LLMSlotStatus,
  LLMBlockStatus,
  LLMSlotsStatus,
  GraphEngineStatus,
  GraphEngineConfig,
  KnowledgeEmbeddingStatus,
  AtlasStatus,
  PipelineStatus,
  PipelineGroupRun,
  CrashedPipelineRun,
  ScopeStatus,
  SyncStatus,
  ServerStatus,
  ServerMode,
  BatchMode,
  TeamConfig,
  TeamConfigStatus as TeamConfigStatusType,
} from './types';

// Components - Status
export { StatusBadge, StatusCard, BuildProgress, ProgressIndicator } from './components/status';
export type { StatusBadgeProps, StatusCardProps, BuildProgressProps, ProgressIndicatorProps } from './components/status';

// Components - Console
export { LogConsole } from './components/console';
export type { LogConsoleProps } from './components/console';

// Components - Navigation
export { Sidebar, ProjectList, ProjectTabs, AppShell } from './components/navigation';
export type { SidebarProps, ProjectListProps, ProjectTabsProps, ProjectTab, AppShellProps } from './components/navigation';

// Components - Search
export { SearchInput, SearchResultRow, ChunkViewer, SearchPanel, ContextOptionsPanel, SearchResultsList, ChunkPreview, ContextOutput } from './components/search';
export type { SearchInputProps, SearchResultRowProps, ChunkViewerProps, SearchPanelProps, ContextOptionsPanelProps, SearchResultsListProps, ChunkPreviewProps, ContextOutputProps, ContextMeta } from './components/search';

// Components - Context
export { CopyButton, CitationBlock, ContextViewer } from './components/context';
export type { CopyButtonProps, CitationBlockProps, ContextViewerProps, ContextChunk } from './components/context';

// Components - Patterns (shared states)
export { EmptyState, LoadingState, ErrorState } from './components/patterns';
export type { EmptyStateProps, LoadingStateProps, ErrorStateProps } from './components/patterns';

// Components - Dashboard
export { IndexStatusCard, IndexStatsDisplay, LLMStatusWidget, UsageGuidePanel } from './components/dashboard';
export type { IndexStatusCardProps, IndexStats, IndexStatsProps, StatItem, LLMStatusWidgetProps, LLMServiceStatus, UsageGuidePanelProps } from './components/dashboard';

// Components - LLM
export { ModelCard, EndpointManager, AIModelsSettings, DeepAnalysisSettings } from './components/llm';
export type { DeepAnalysisSchedule, DeepAnalysisStatus } from './components/llm';

// Components - Primitives
export { Button } from './components/primitives/Button';
export { ConfirmDialog } from './components/primitives/ConfirmDialog';
export type { ConfirmDialogProps } from './components/primitives/ConfirmDialog';
export { Select } from './components/primitives/Select';
export type { SelectProps, SelectOption } from './components/primitives/Select';
export { PathInput } from './components/primitives/PathInput';
export type { PathInputProps, PathPickerMode } from './components/primitives/PathInput';
export { Toggle } from './components/primitives/Toggle';
export type { ToggleProps } from './components/primitives/Toggle';
export { SlidingSwitch2, SlidingSwitch3 } from './components/primitives/SlidingSwitch';
export { SettingsSection } from './components/primitives/SettingsSection';
export type { SettingsSectionProps } from './components/primitives/SettingsSection';
export { SettingsRow } from './components/primitives/SettingsRow';
export type { SettingsRowProps } from './components/primitives/SettingsRow';
export { TagListEditor } from './components/primitives/TagListEditor';
export type { TagListEditorProps } from './components/primitives/TagListEditor';
export { BudgetPill } from './components/primitives/BudgetPill';
export type { BudgetPillProps } from './components/primitives/BudgetPill';
export { BudgetPreview } from './components/primitives/BudgetPreview';
export type { BudgetPreviewProps } from './components/primitives/BudgetPreview';
export { AdminSection } from './components/primitives/AdminSection';
export type { AdminSectionProps } from './components/primitives/AdminSection';

// Hooks - Enterprise (EA-C4)
export { useAdminPolicy } from './hooks/useAdminPolicy';

// Components - Project
export { FolderTree, sampleFileTree, ProjectSettingsPanel, FolderTreePanel, PinnedTextFilesPanel, AddProjectModal, FilePreviewPane, FileExplorerDetail, CodeViewer } from './components/project';
export type { FolderTreeProps, TreeNode, FileStatus, ProjectSettingsPanelProps, FolderTreePanelProps, PinnedTextFilesPanelProps, PinnedTextFile, AddProjectModalProps, FilePreviewPaneProps, FileExplorerDetailProps, FileExplorerTab, CodeViewerProps } from './components/project';

// Components - Watch (Phase 03)
export { WatchStatusIndicator, WatchControlPanel } from './components/watch';
export type { WatchStatusIndicatorProps, WatchControlPanelProps } from './components/watch';

// Components - Trace (Phase 04)
export { TraceStatusCard, TraceExplorer, TraceCoveragePanel, GraphEnrichmentPipeline, GraphStructurePanel, AtlasStatusCard } from './components/trace';
export type { TraceStatusCardProps, TraceExplorerProps, TraceCoveragePanelProps, GraphEnrichmentPipelineProps, TraceStageInfo, EnrichmentStageId, EnrichmentAutoConfig, DeepEnrichmentMode, GraphStructurePanelProps, AtlasStatusCardProps } from './components/trace';

// Components - Layout (Modular Dashboard - Phase 15)
export { PanelChrome, DashboardGrid, PanelPicker, ModularDashboard, useLayoutPersistence } from './components/layout';
export type { PanelChromeProps, DashboardGridProps, PanelPickerProps, ModularDashboardProps, PanelContentMap, DashboardLayoutApi } from './components/layout';

// Components - Marketing & Site (Phase 12)
export { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures, TierComparison, tierComparisonFeatures, TechStackMatrix, techStackComponents, CompetitorMatrix } from './components/marketing';
export type { MarketingHeroProps, FeatureBlocksProps, Feature, TierComparisonProps, TierFeature, TechStackMatrixProps, StackComponent, CompetitorMatrixProps } from './components/marketing';
export { SiteHeader, SiteFooter, XIcon } from './components/site';
export type { SiteHeaderProps, SiteFooterProps, NavLink, FooterSection, FooterLink } from './components/site';

// Components - Docs (Phase 12)
export { DocsLayout, DocsSidebarNav, TableOfContents } from './components/docs';
export type { DocsLayoutProps, DocsSidebarNavProps, DocNode, TableOfContentsProps, TocItem } from './components/docs';

// Components - Team (License & Server Mode)
export {
  ServerModeIndicator,
  TeamConfigStatus,
  EmbeddedModeIndicator,
  LicenseStatusCard,
  TeamSyncIndicator,
} from './components/team';

export type {
  ServerModeIndicatorProps,
  TeamConfigStatusProps,
  EmbeddedModeIndicatorProps,
  LicenseStatusCardProps,
  TeamSyncIndicatorProps,
} from './components/team';

// Components - Audit (Phase 43)
export { AuditPanel } from './components/audit';
export type { AuditPanelProps } from './components/audit';
export type { AuditConfig, AuditFinding, AuditStatus, AuditReport, AuditSeverity, AuditCategory } from './types';
export type { SchedulerStatus, SchedulerNodeStatus, ComputeNode, ComputeHardwareProfile } from './types';

// Components - Enterprise (Phase 06)
export { EnterpriseAdminPanel } from './components/enterprise';
export type { EnterpriseAdminPanelProps, SecurityHealthResult, TokenUsageSummary, SyncFleetEntry, UsageData } from './components/enterprise';

// Components - Viz
export { ActivityHeatmap, generateSampleActivityData, IndexHealthPanel, TokenBudgetPanel } from './components/viz';
export type { ActivityHeatmapProps, ActivityHeatmapData, ActivityDay, IndexHealthPanelProps, IndexHealthData, DeepHealthData, TokenBudgetPanelProps, TokenBudgetData } from './components/viz';

// Layout Types (Phase 15)
export type { 
  PanelConfig, 
  DashboardLayout, 
  PanelCategory, 
  PanelDefinition, 
  PanelProps, 
  GridLayoutItem 
} from './types/layout';
export { DEFAULT_LAYOUT, LAYOUT_STORAGE_KEY, BASE_COLS, toGridLayout, fromGridLayout, reflowLayout, computeGridCols, adjustLayoutForColChange } from './types/layout';

// Panel Registry (Phase 15)
export { PANEL_REGISTRY, getPanelDefinition, getPanelsByCategory } from './config/panelRegistry';

// Hooks
export { useEventStream } from './hooks/useEventStream';

// API (typed client + Storybook mocking helpers)
export * from './api';
export { SyncStatusCard } from './components/team/SyncStatusCard';
export type { SyncStatusCardProps } from './components/team/SyncStatusCard';
