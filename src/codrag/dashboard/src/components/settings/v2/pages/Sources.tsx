import { SettingsPage } from '../SettingsPage';

export interface SourcesPageProps {
  // filled in Task 14
}

export function SourcesPage(_props: SourcesPageProps) {
  return (
    <SettingsPage
      title="Sources & Scope"
      scope="project"
      description="Which files are included in this project's index."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
