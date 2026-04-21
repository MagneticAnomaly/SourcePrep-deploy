import { Shield } from 'lucide-react';
import { Button, Section, type LicenseStatus } from '@prep/ui';
import { SettingsPage } from '../SettingsPage';

export interface LicensePageProps {
  licenseStatus: LicenseStatus | null;
  licenseKeyInput: string;
  onLicenseKeyInputChange: (value: string) => void;
  onActivateLicense: () => void | Promise<void>;
  onDeactivateLicense: () => void | Promise<void>;
  licenseLoading: boolean;
  licenseError: string | null;
  devTierOverride: string | null;
}

export function LicensePage({
  licenseStatus,
  licenseKeyInput,
  onLicenseKeyInputChange,
  onActivateLicense,
  onDeactivateLicense,
  licenseLoading,
  licenseError,
  devTierOverride,
}: LicensePageProps) {
  return (
    <SettingsPage
      title="License"
      scope="global"
      description="Your Prep license tier and activation key."
    >
      <Section>
        <div className="space-y-3 p-1">
          {licenseStatus && (
            <div className="flex items-center gap-2 text-xs p-2 rounded bg-surface-raised border border-border">
              <Shield className="w-3.5 h-3.5 text-primary" />
              <span className="font-medium text-text capitalize">{licenseStatus.license.tier} Plan</span>
              {licenseStatus.license.valid && (
                <span className="text-success text-[10px] bg-success/10 px-1.5 py-0.5 rounded ml-auto">Active</span>
              )}
            </div>
          )}

          {devTierOverride && (
            <div className="text-xs text-warning bg-warning/10 px-2 py-1 rounded border border-warning/20">
              Dev override active: <strong className="capitalize">{devTierOverride}</strong> tier
            </div>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={licenseKeyInput}
              onChange={(e) => onLicenseKeyInputChange(e.target.value)}
              placeholder="Enter license key..."
              className="flex-1 text-xs px-3 py-1.5 rounded border border-border bg-background text-text placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Button
              variant="default"
              size="sm"
              onClick={onActivateLicense}
              disabled={!licenseKeyInput.trim() || licenseLoading}
            >
              {licenseLoading ? 'Activating...' : 'Activate'}
            </Button>
          </div>

          {licenseStatus?.license.tier !== 'free' && !devTierOverride && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDeactivateLicense}
              disabled={licenseLoading}
              className="w-full text-text-muted hover:text-error hover:bg-error/10"
            >
              Deactivate License
            </Button>
          )}

          {licenseError && (
            <p className="text-xs text-error">{licenseError}</p>
          )}

          <p className="text-xs text-text-muted">
            Purchase a license at{' '}
            <a
              href="https://runprep.io/pricing"
              target="_blank"
              rel="noreferrer"
              className="text-primary underline"
            >
              runprep.io/pricing
            </a>
            .
          </p>
        </div>
      </Section>
    </SettingsPage>
  );
}
