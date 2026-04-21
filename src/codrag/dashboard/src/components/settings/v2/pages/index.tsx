import type { AdvancedConfig, DeepAnalysisSchedule, ProjectConfig } from '@codrag/ui';
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
  // Legacy/unknown-typed fields preserved so the other 11 pages continue to
  // compile under `{...host as any}` until their own lift tasks land.
  projectConfig: unknown;
  globalConfig: unknown;
  activeProjectId: string | null;

  // ── Project-scope: Sources page (Task 14) ─────────────────────────
  projectName: string | null;
  projectConfigTyped: ProjectConfig | null;
  projectDirty: boolean;
  projectSaving: boolean;
  onProjectChange: (next: ProjectConfig) => void;
  onProjectSave: () => void | Promise<void>;
  onProjectDiscard: () => void;
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
  pipelineRunning: boolean;
  onRebuildPipeline: () => void;
  onDestroyIndex: () => void;
  onDestroyEnrichmentFull: () => void;
  onDestroyFinalizeFull: () => void;

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
}

export function renderSettingsPage(id: SettingsPageId, host: PageHostProps) {
  switch (id) {
    case 'sources':
      return host.projectConfigTyped ? (
        <SourcesPage
          projectName={host.projectName}
          config={host.projectConfigTyped}
          dirty={host.projectDirty}
          saving={host.projectSaving}
          onChange={host.onProjectChange}
          onSave={host.onProjectSave}
          onDiscard={host.onProjectDiscard}
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
          dirty={host.projectDirty}
          saving={host.projectSaving}
          onChange={host.onProjectChange}
          onSave={host.onProjectSave}
          onDiscard={host.onProjectDiscard}
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
          onRebuildPipeline={host.onRebuildPipeline}
          onDestroyIndex={host.onDestroyIndex}
          onDestroyEnrichmentFull={host.onDestroyEnrichmentFull}
          onDestroyFinalizeFull={host.onDestroyFinalizeFull}
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
    case 'license':               return <LicensePage {...host as any} />;
    case 'integrations':          return <IntegrationsPage {...host as any} />;
    case 'developer-debug':       return <DevTogglesPage {...host as any} />;
    case 'developer-diagnostics': return <DiagnosticsPage {...host as any} />;
    case 'developer-reset':       return <SelectiveResetPage {...host as any} />;
  }
}
