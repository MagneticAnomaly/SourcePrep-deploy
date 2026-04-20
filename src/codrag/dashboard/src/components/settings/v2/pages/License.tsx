import { SettingsPage } from '../SettingsPage';

export interface LicensePageProps {
  // filled in Task 14
}

export function LicensePage(_props: LicensePageProps) {
  return (
    <SettingsPage
      title="License"
      scope="global"
      description="Subscription tier and activation."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
