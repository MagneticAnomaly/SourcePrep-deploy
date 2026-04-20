import { SettingsPage } from '../SettingsPage';

export interface PipelineDefaultsPageProps {
  // filled in Task 14
}

export function PipelineDefaultsPage(_props: PipelineDefaultsPageProps) {
  return (
    <SettingsPage
      title="Pipeline Defaults"
      scope="global"
      description="Daemon-wide pipeline parameters."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
