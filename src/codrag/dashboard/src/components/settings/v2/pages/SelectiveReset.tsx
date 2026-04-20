import { SettingsPage } from '../SettingsPage';

export interface SelectiveResetPageProps {
  // filled in Task 14
}

export function SelectiveResetPage(_props: SelectiveResetPageProps) {
  return (
    <SettingsPage
      title="Selective Reset"
      scope="developer"
      description="Reset individual caches without a full rebuild."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
