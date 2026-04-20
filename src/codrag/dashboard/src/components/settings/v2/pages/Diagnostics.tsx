import { SettingsPage } from '../SettingsPage';

export interface DiagnosticsPageProps {
  // filled in Task 14
}

export function DiagnosticsPage(_props: DiagnosticsPageProps) {
  return (
    <SettingsPage
      title="Diagnostics"
      scope="developer"
      description="Daemon health, data directory, licence details."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
