import { SettingRow, Section } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

export interface IntegrationsPageProps {
  onOpenAiGateway: () => void;
}

export function IntegrationsPage({ onOpenAiGateway }: IntegrationsPageProps) {
  return (
    <SettingsPage
      title="Integrations"
      scope="global"
      description="Connected IDEs and the AI Gateway."
    >
      <Section>
        <SettingRow
          label="AI Gateway"
          description="Model slots, endpoints, and concurrency live in the AI Gateway panel."
          control={
            <button
              type="button"
              onClick={onOpenAiGateway}
              className="text-sm border border-border-subtle hover:bg-surface-raised rounded-md px-3 py-1.5 text-text"
            >
              Open AI Gateway →
            </button>
          }
          last
        />
      </Section>
    </SettingsPage>
  );
}
