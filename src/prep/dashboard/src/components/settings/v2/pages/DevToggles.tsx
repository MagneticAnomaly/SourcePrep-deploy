import { Section, SettingRow, Toggle, Select } from '@prep/ui';
import type { LicenseTier, UserRole } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

// Lifted verbatim from SettingsDrawer.tsx:65-71
const DEV_TIER_OPTIONS = [
  { value: '', label: 'Off (use real license)' },
  { value: 'free', label: 'Free' },
  { value: 'pro', label: 'Pro' },
  { value: 'team', label: 'Team' },
  { value: 'enterprise', label: 'Enterprise' },
];

const DEV_ROLE_OPTIONS = [
  { value: '', label: 'Default (user)' },
  { value: 'user', label: 'User' },
  { value: 'admin', label: 'IT Admin' },
];

export interface DevTogglesPageProps {
  globalConfig: {
    developer_debug_mode?: boolean;
    exploratory_testing_mode?: boolean;
    developer_show_dev_panels?: boolean;
  };
  onGlobalConfigChange: (patch: Partial<{
    developer_debug_mode?: boolean;
    exploratory_testing_mode?: boolean;
    developer_show_dev_panels?: boolean;
  }>) => void;
  devTierOverride: LicenseTier | null;
  onDevTierOverrideChange: (tier: LicenseTier | null) => void;
  devRoleOverride: UserRole | null;
  onDevRoleOverrideChange: (role: UserRole | null) => void;
}

export function DevTogglesPage({
  globalConfig,
  onGlobalConfigChange,
  devTierOverride,
  onDevTierOverrideChange,
  devRoleOverride,
  onDevRoleOverrideChange,
}: DevTogglesPageProps) {
  return (
    <SettingsPage
      title="Debug Toggles"
      scope="developer"
      description="Runtime flags and tier/role overrides for local development."
    >
      <Section title="Debug tools">
        <SettingRow
          label="Verbose Telemetry"
          description="Log deep LLM analytics, raw prompts, and response timings to stdout for local testing."
          control={
            <Toggle
              checked={globalConfig?.developer_debug_mode ?? false}
              onChange={(val: boolean) => onGlobalConfigChange({ developer_debug_mode: val })}
            />
          }
        />
        <SettingRow
          label="Cloud Exploratory Testing"
          description="Activates adaptive fallback batching engine to test LLM rate limits and parsing thresholds without halting. Logs to telemetry files."
          control={
            <Toggle
              checked={globalConfig?.exploratory_testing_mode ?? false}
              onChange={(val: boolean) => onGlobalConfigChange({ exploratory_testing_mode: val })}
            />
          }
        />
        <SettingRow
          label="Show Dev Panels"
          description="Show experimental and in-progress dashboard panels (Roadmap, Agent Ops, Architecture, Concepts, etc)."
          control={
            <Toggle
              checked={globalConfig?.developer_show_dev_panels ?? false}
              onChange={(val: boolean) => onGlobalConfigChange({ developer_show_dev_panels: val })}
            />
          }
          last
        />
      </Section>

      <Section title="Tier & role overrides">
        <SettingRow
          id="dev-tier-override"
          label="Dev Tier Override"
          description="Simulate a different license tier for local testing."
          control={
            <Select
              value={devTierOverride ?? ''}
              onChange={(e) => {
                const val = e.target.value;
                onDevTierOverrideChange(val ? val as LicenseTier : null);
              }}
              aria-label="Dev Tier Override"
              size="sm"
              options={DEV_TIER_OPTIONS}
            />
          }
        />
        <SettingRow
          id="dev-role-override"
          label="Dev Role Override"
          description="Simulate user vs IT admin role."
          control={
            <Select
              value={devRoleOverride ?? ''}
              onChange={(e) => {
                const val = e.target.value;
                onDevRoleOverrideChange(val ? val as UserRole : null);
              }}
              aria-label="Dev Role Override"
              size="sm"
              options={DEV_ROLE_OPTIONS}
            />
          }
          last
        />
      </Section>

      {(devTierOverride || devRoleOverride) && (
        <div className="p-3 rounded border border-warning/30 bg-warning/5">
          <p className="text-xs text-warning font-medium">⚠ Development Mode Active</p>
          <p className="text-xs text-text-muted mt-1">
            Simulating <strong className="capitalize text-text">{devTierOverride || 'Free'}</strong> tier with <strong className="capitalize text-text">{devRoleOverride || 'User'}</strong> role.
          </p>
        </div>
      )}
    </SettingsPage>
  );
}
