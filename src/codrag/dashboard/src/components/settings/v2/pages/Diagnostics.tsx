import { useState } from 'react';
import { Button, Section, useApiClient } from '@codrag/ui';
import type { LicenseStatus, LicenseTier } from '@codrag/ui';
import { SettingsPage } from '../SettingsPage';

export interface DiagnosticsPageProps {
  licenseStatus: LicenseStatus | null;
  devTierOverride: LicenseTier | null;
}

export function DiagnosticsPage({
  licenseStatus,
  devTierOverride,
}: DiagnosticsPageProps) {
  const [healthResult, setHealthResult] = useState<string>('No test run yet');
  const api = useApiClient();

  // Lifted verbatim from SettingsDrawer.tsx:228-236
  const runHealthTest = async () => {
    setHealthResult('Testing...');
    try {
      const health = await api.getHealth();
      setHealthResult(`OK: ${JSON.stringify(health)}`);
    } catch (err) {
      setHealthResult(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <SettingsPage
      title="Diagnostics"
      scope="developer"
      description="Health checks and effective license state."
    >
      <Section title="License details">
        <div className="text-xs font-mono bg-background p-3 rounded border border-border space-y-1.5">
          <div className="grid grid-cols-[80px_1fr] gap-x-2">
            <strong className="text-text">Tier:</strong>
            <span className="text-text-muted capitalize">{licenseStatus?.license.tier ?? 'unknown'}</span>

            <strong className="text-text">Valid:</strong>
            <span className="text-text-muted">{licenseStatus?.license.valid ? 'Yes' : 'No'}</span>

            <strong className="text-text">Override:</strong>
            <span className="text-text-muted">{devTierOverride ?? 'None'}</span>

            <strong className="text-text">Effective:</strong>
            <span className="text-primary capitalize">{devTierOverride ?? licenseStatus?.license.tier ?? 'free'}</span>

            {licenseStatus?.license.email && (
              <>
                <strong className="text-text">Email:</strong>
                <span className="text-text-muted truncate">{licenseStatus.license.email}</span>
              </>
            )}
          </div>
        </div>
      </Section>

      <Section title="Connection debugger">
        <div className="space-y-3">
          <Button variant="outline" size="sm" onClick={runHealthTest} className="w-full">
            Test /health Endpoint
          </Button>
          <div className="bg-background p-3 rounded border border-border font-mono text-xs">
            <pre className="whitespace-pre-wrap break-all text-text">{healthResult}</pre>
          </div>
          <div className="grid grid-cols-[60px_1fr] gap-x-2 text-xs text-text-muted">
            <strong className="text-text">Origin:</strong> {window.location.origin}
            <strong className="text-text">API:</strong> {api.baseUrl || '(hidden)'}
          </div>
        </div>
      </Section>
    </SettingsPage>
  );
}
