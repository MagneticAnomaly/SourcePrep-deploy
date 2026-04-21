import { DeepAnalysisSettings, type DeepAnalysisSchedule } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

export interface DeepAnalysisPageProps {
  /** Name of the active project — used in the description copy. */
  projectName: string | null;
  schedule: DeepAnalysisSchedule;
  /** Applies a full replacement schedule — matches DeepAnalysisSettings prop shape. */
  onScheduleChange: (next: DeepAnalysisSchedule) => void;
  largeModelConfigured: boolean;
  fastModelConfigured: boolean;
}

/**
 * Deep Analysis settings page (Project scope).
 *
 * Thin pass-through to the existing `DeepAnalysisSettings` component, which
 * owns the mode/budget/priority internals and already organises its own
 * sub-sections (Trigger Mode, Budget Per Session, Priority). This page just
 * provides the SettingsPage chrome (title, scope chip, description).
 *
 * Autosave: `handleSyncedDeepAnalysisScheduleChange` in App.tsx persists every
 * change immediately — no dirty-staging, so Save/Discard would be inert. We
 * intentionally omit those buttons here (matching the plan's "one or two
 * Sections" flexibility).
 */
export function DeepAnalysisPage({
  projectName,
  schedule,
  onScheduleChange,
  largeModelConfigured,
  fastModelConfigured,
}: DeepAnalysisPageProps) {
  const description = projectName
    ? `Schedule and budget for ${projectName} deep enrichment.`
    : 'Schedule and budget for deep enrichment.';

  return (
    <SettingsPage title="Deep Analysis" scope="project" description={description}>
      <DeepAnalysisSettings
        schedule={schedule}
        onScheduleChange={onScheduleChange}
        largeModelConfigured={largeModelConfigured}
        fastModelConfigured={fastModelConfigured}
      />
    </SettingsPage>
  );
}
