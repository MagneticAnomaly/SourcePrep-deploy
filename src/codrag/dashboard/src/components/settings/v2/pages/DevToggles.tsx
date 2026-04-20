import { SettingsPage } from '../SettingsPage';

export interface DevTogglesPageProps {
  // filled in Task 14
}

export function DevTogglesPage(_props: DevTogglesPageProps) {
  return (
    <SettingsPage
      title="Debug Toggles"
      scope="developer"
      description="Runtime flags for developers."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
