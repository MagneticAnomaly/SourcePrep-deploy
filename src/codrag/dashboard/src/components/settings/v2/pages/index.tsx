import type { SettingsPageId } from '../routeParser';
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
  projectConfig: unknown;
  globalConfig: unknown;
  activeProjectId: string | null;
}

export function renderSettingsPage(id: SettingsPageId, host: PageHostProps) {
  switch (id) {
    case 'sources':               return <SourcesPage {...host as any} />;
    case 'trace-indexing':        return <TraceIndexingPage {...host as any} />;
    case 'deep-analysis':         return <DeepAnalysisPage {...host as any} />;
    case 'danger-zone':           return <DangerZonePage {...host as any} />;
    case 'appearance':            return <AppearancePage {...host as any} />;
    case 'chunking-embeddings':   return <ChunkingEmbeddingsPage {...host as any} />;
    case 'pipeline-defaults':     return <PipelineDefaultsPage {...host as any} />;
    case 'license':               return <LicensePage {...host as any} />;
    case 'integrations':          return <IntegrationsPage {...host as any} />;
    case 'developer-debug':       return <DevTogglesPage {...host as any} />;
    case 'developer-diagnostics': return <DiagnosticsPage {...host as any} />;
    case 'developer-reset':       return <SelectiveResetPage {...host as any} />;
  }
}
