import type { AdvancedConfig, DeepAnalysisSchedule, LicenseStatus, LicenseTier, ProjectConfig, UserRole } from '@prep/ui';
import type { SettingsPageId } from '../routeParser';
import { SettingsPage } from '../SettingsPage';
import { SourcesPage } from './Sources';
import { TraceIndexingPage } from './TraceIndexing';
import { DeepAnalysisPage } from './DeepAnalysis';
import { DangerZonePage } from './DangerZone';
import { AppearancePage } from './Appearance';
import { ChunkingEmbeddingsPage } from './ChunkingEmbeddings';
import { PipelineDefaultsPage } from './PipelineDefaults';
import { LicensePage } from './License';
import { IntegrationsPage } from './Integrations';
import { DevTogglesPage } from './DevToggles';
import { DiagnosticsPage } from './Diagnostics';
import { SelectiveResetPage } from './SelectiveReset';

export interface PageHostProps {
  activeProjectId: string | null;

  // ── Project-scope: Sources / Trace & Indexing pages ───────────────
  // Autosave — onProjectChange persists on change via debounced useEffect
  // in App.tsx. projectSaving drives the "Saving…" indicator in the page header.
  projectName: string | null;
  projectConfigTyped: ProjectConfig | null;
  projectSaving: boolean;
  onProjectChange: (next: ProjectConfig) => void;
  onDetectStack?: () => Promise<{
    recommended_globs: string[];
    detected_presets: string[];
    all_presets: Record<string, string[]>;
  }>;

  // ── Project-scope: Deep Analysis page (Task 16) ───────────────────
  // Autosave — onDeepAnalysisScheduleChange persists immediately via
  // handleSyncedDeepAnalysisScheduleChange in App.tsx, so no Save/Discard
  // wiring is needed for this page.
  deepAnalysisSchedule: DeepAnalysisSchedule;
  onDeepAnalysisScheduleChange: (next: DeepAnalysisSchedule) => void;
  largeModelConfigured: boolean;
  fastModelConfigured: boolean;

  // ── Project-scope: Danger Zone page (Task 17) ─────────────────────
  // One-shot destructive actions — no dirty/save. Each button opens the
  // shared ConfirmDialog with a typed-confirm gate for Rebuild Pipeline
  // (Phase 114 UX preserved verbatim from the drawer).
  //
  // Phase 117b: collapsed four rows (Rebuild / Reset All / Reset
  // Enrichment / Reset Finalize) into two scoped action rows. The host
  // routes scope to the appropriate destroy/rebuild handler.
  pipelineRunning: boolean;
  onRebuildScoped: (scope: 'all' | 'sync' | 'enrichment') => void;
  onResetScoped: (scope: 'all' | 'enrichment' | 'finalize') => void;

  // ── Global-scope: Appearance page (Task 18) ───────────────────────
  // Autosave — App.tsx useEffect on [uiMode, uiTheme, bgImage] persists via
  // localStorage + llm_config API. No Save/Discard/dirty wiring.
  uiMode: 'light' | 'dark';
  onModeChange: (mode: 'light' | 'dark') => void;
  uiTheme: string;
  onThemeChange: (theme: string) => void;
  bgImage: string | null;
  onBgImageChange: (url: string | null) => void;

  // ── Global-scope: Chunking & Embeddings page (Task 19) ────────────
  // Autosave — onGlobalAdvancedChange persists immediately via App.tsx.
  // Shared state: this same object will power Pipeline Defaults (Task 20).
  globalAdvanced: AdvancedConfig;
  onGlobalAdvancedChange: (patch: Partial<AdvancedConfig>) => void;

  // ── Global-scope: Pipeline Defaults page (Task 20) ────────────────
  // Autosave — shares globalAdvanced/onGlobalAdvancedChange with Chunking &
  // Embeddings (Task 19). maxActiveProjects persists via handleMaxActiveProjectsChange.
  maxActiveProjects: number | 'infinite';
  onMaxActiveProjectsChange: (value: number | 'infinite') => void;

  // ── Global-scope: License page (Task 21) ──────────────────────────
  // Activation/deactivation are explicit button actions with their own
  // loading state. devTierOverride is read-only here — the control lives
  // in Developer Diagnostics (Task 23).
  licenseStatus: LicenseStatus | null;
  licenseKeyInput: string;
  onLicenseKeyInputChange: (value: string) => void;
  onActivateLicense: () => void | Promise<void>;
  onDeactivateLicense: () => void | Promise<void>;
  licenseLoading: boolean;
  licenseError: string | null;
  devTierOverride: LicenseTier | null;

  // ── Global-scope: Integrations page (Task 22) ─────────────────────
  // onOpenAiGateway closes the overlay (drops ?settings= from URL) and
  // dispatches 'prep:open-ai-gateway' which App.tsx routes to the
  // AI Gateway details panel. The AI Gateway itself is not moved.
  onOpenAiGateway: () => void;

  // ── Developer-scope: Debug Toggles / Diagnostics / Selective Reset (Task 23)
  // Dev-gated via devGate.filterPagesForBuild — the nav hides these in
  // production builds, and the overlay redirects away defensively.
  globalConfig: {
    developer_debug_mode?: boolean;
    exploratory_testing_mode?: boolean;
    developer_show_dev_panels?: boolean;
  };
  onGlobalConfigChange: (patch: Partial<{
    developer_debug_mode?: boolean;
    exploratory_testing_mode?: boolean;
    developer_show_dev_panels?: boolean;
  }>) => void;
  onDevTierOverrideChange: (tier: LicenseTier | null) => void;
  devRoleOverride: UserRole | null;
  onDevRoleOverrideChange: (role: UserRole | null) => void;
  onDestroyAtlas: () => void;
  onDestroyGroupReasoning: () => void;
  onDestroyDeepEnrichment: () => void;
}

export function renderSettingsPage(id: SettingsPageId, host: PageHostProps) {
  switch (id) {
    case 'sources':
      return host.projectConfigTyped ? (
        <SourcesPage
          projectName={host.projectName}
          config={host.projectConfigTyped}
          saving={host.projectSaving}
          onChange={host.onProjectChange}
          onDetectStack={host.onDetectStack}
        />
      ) : (
        <SettingsPage title="Sources & Scope" scope="project">
          <div className="text-sm text-text-muted">
            Select a project to configure sources.
          </div>
        </SettingsPage>
      );
    case 'trace-indexing':
      return host.projectConfigTyped ? (
        <TraceIndexingPage
          projectName={host.projectName}
          config={host.projectConfigTyped}
          saving={host.projectSaving}
          onChange={host.onProjectChange}
        />
      ) : (
        <SettingsPage title="Trace & Indexing" scope="project">
          <div className="text-sm text-text-muted">
            Select a project to configure trace settings.
          </div>
        </SettingsPage>
      );
    case 'deep-analysis':
      return (
        <DeepAnalysisPage
          projectName={host.projectName}
          schedule={host.deepAnalysisSchedule}
          onScheduleChange={host.onDeepAnalysisScheduleChange}
          largeModelConfigured={host.largeModelConfigured}
          fastModelConfigured={host.fastModelConfigured}
        />
      );
    case 'danger-zone':
      return (
        <DangerZonePage
          projectName={host.projectName}
          projectId={host.activeProjectId}
          pipelineRunning={host.pipelineRunning}
          onRebuildScoped={host.onRebuildScoped}
          onResetScoped={host.onResetScoped}
        />
      );
    case 'appearance':
      return (
        <AppearancePage
          uiMode={host.uiMode}
          onModeChange={host.onModeChange}
          uiTheme={host.uiTheme}
          onThemeChange={host.onThemeChange}
          bgImage={host.bgImage}
          onBgImageChange={host.onBgImageChange}
        />
      );
    case 'chunking-embeddings':
      return (
        <ChunkingEmbeddingsPage
          config={host.globalAdvanced}
          onChange={host.onGlobalAdvancedChange}
        />
      );
    case 'pipeline-defaults':
      return (
        <PipelineDefaultsPage
          maxActiveProjects={host.maxActiveProjects}
          onMaxActiveProjectsChange={host.onMaxActiveProjectsChange}
          config={host.globalAdvanced}
          onChange={host.onGlobalAdvancedChange}
        />
      );
    case 'license':
      return (
        <LicensePage
          licenseStatus={host.licenseStatus}
          licenseKeyInput={host.licenseKeyInput}
          onLicenseKeyInputChange={host.onLicenseKeyInputChange}
          onActivateLicense={host.onActivateLicense}
          onDeactivateLicense={host.onDeactivateLicense}
          licenseLoading={host.licenseLoading}
          licenseError={host.licenseError}
          devTierOverride={host.devTierOverride}
        />
      );
    case 'integrations':
      return <IntegrationsPage onOpenAiGateway={host.onOpenAiGateway} />;
    case 'developer-debug':
      return (
        <DevTogglesPage
          globalConfig={host.globalConfig}
          onGlobalConfigChange={host.onGlobalConfigChange}
          devTierOverride={host.devTierOverride}
          onDevTierOverrideChange={host.onDevTierOverrideChange}
          devRoleOverride={host.devRoleOverride}
          onDevRoleOverrideChange={host.onDevRoleOverrideChange}
        />
      );
    case 'developer-diagnostics':
      return (
        <DiagnosticsPage
          licenseStatus={host.licenseStatus}
          devTierOverride={host.devTierOverride}
        />
      );
    case 'developer-reset':
      return (
        <SelectiveResetPage
          projectName={host.projectName}
          projectId={host.activeProjectId}
          onDestroyAtlas={host.onDestroyAtlas}
          onDestroyGroupReasoning={host.onDestroyGroupReasoning}
          onDestroyDeepEnrichment={host.onDestroyDeepEnrichment}
        />
      );
  }
}
