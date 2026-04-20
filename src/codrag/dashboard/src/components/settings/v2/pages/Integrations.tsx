import { SettingsPage } from '../SettingsPage';

export interface IntegrationsPageProps {
  // filled in Task 14
}

export function IntegrationsPage(_props: IntegrationsPageProps) {
  return (
    <SettingsPage
      title="Integrations"
      scope="global"
      description="Connected IDEs and the AI Gateway."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
