import { SettingsPage } from '../SettingsPage';

export interface AppearancePageProps {
  // filled in Task 14
}

export function AppearancePage(_props: AppearancePageProps) {
  return (
    <SettingsPage
      title="Appearance"
      scope="global"
      description="Theme, colour mode, and background."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
