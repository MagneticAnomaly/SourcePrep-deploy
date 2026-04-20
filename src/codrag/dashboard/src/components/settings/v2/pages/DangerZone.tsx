import { SettingsPage } from '../SettingsPage';

export interface DangerZonePageProps {
  // filled in Task 14
}

export function DangerZonePage(_props: DangerZonePageProps) {
  return (
    <SettingsPage
      title="Danger Zone"
      scope="project"
      description="Destructive operations. Each requires typed confirmation."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
