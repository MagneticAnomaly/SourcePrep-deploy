import { cn } from '../../lib/utils';
import type { LicenseInfo, LicenseTier } from '../../types';
import { CreditCard, AlertCircle, Users, Calendar, ArrowUpCircle, Settings } from 'lucide-react';
import { Button } from '../primitives/Button';
import { InfoTooltip } from '../primitives/InfoTooltip';

export interface LicenseStatusCardProps {
  license: LicenseInfo;
  onUpgrade?: () => void;
  onManageLicense?: () => void;
  className?: string;
}

const tierConfig: Record<LicenseTier, { label: string; color: string }> = {
  free: { label: 'Free Plan', color: 'bg-surface-raised text-text-muted border-border' },
  pro: { label: 'Pro', color: 'bg-primary-muted/10 text-primary border-primary-muted/20' },
  team: { label: 'Team', color: 'bg-success-muted/10 text-success border-success-muted/20' },
  enterprise: { label: 'Enterprise', color: 'bg-purple-500/10 text-purple-600 border-purple-500/20 dark:text-purple-400' },
};

export function LicenseStatusCard({
  license,
  onUpgrade,
  onManageLicense,
  className,
}: LicenseStatusCardProps) {
  const { label, color } = tierConfig[license.tier];
  const showSeats = license.seats_used !== undefined && license.seats_total !== undefined;
  const seatPercent = showSeats ? (license.seats_used! / license.seats_total!) * 100 : 0;
  
  return (
    <div className={cn('rounded-lg border border-border bg-surface p-6 shadow-sm', className)}>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-text flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-primary" />
            License
            <InfoTooltip 
              content="View pricing and features." 
              href="https://sourceprep.io/pricing" 
            />
          </h3>
          <p className="text-sm text-text-muted mt-1">
            SourcePrep {label} License
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium border", color)}>
            {label}
          </span>
          {!license.valid && (
            <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-error-muted/10 text-error border border-error-muted/20">
              <AlertCircle className="w-3.5 h-3.5" />
              Invalid
            </span>
          )}
        </div>
      </div>
      
      {/* Features */}
      {license.features.length > 0 && (
        <div className="mb-6">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Features</p>
          <div className="flex flex-wrap gap-2">
            {license.features.map((feature) => (
              <span key={feature} className="inline-flex items-center px-2 py-1 rounded text-xs bg-surface-raised border border-border text-text-muted">
                {feature}
              </span>
            ))}
          </div>
        </div>
      )}
      
      {/* Seats (Team/Enterprise) */}
      {showSeats && (
        <div className="mb-6">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="flex items-center gap-1.5 text-text-muted">
              <Users className="w-3.5 h-3.5" />
              Seats Used
            </span>
            <span className="font-medium text-text">{license.seats_used} / {license.seats_total}</span>
          </div>
          <div className="w-full bg-surface-raised rounded-full h-2 overflow-hidden border border-border-subtle">
            <div 
              className={cn(
                "h-full rounded-full transition-all", 
                seatPercent > 90 ? "bg-error" : "bg-primary"
              )}
              style={{ width: `${seatPercent}%` }}
            />
          </div>
        </div>
      )}
      
      {/* Expiration */}
      {license.expires_at && (
        <div className="flex items-center gap-2 text-xs text-text-muted mb-6 bg-surface-raised/50 p-2 rounded border border-border/50">
          <Calendar className="w-3.5 h-3.5 text-text-subtle" />
          <span className={license.valid ? "text-text-muted" : "text-error"}>
            {license.valid ? 'Expires' : 'Expired'}: {license.expires_at}
          </span>
        </div>
      )}
      
      {/* Actions */}
      <div className="flex gap-2">
        {license.tier === 'free' && onUpgrade && (
          <Button 
            onClick={onUpgrade}
            size="sm"
            icon={ArrowUpCircle}
          >
            Upgrade to Pro
          </Button>
        )}
        {onManageLicense && (
          <Button 
            onClick={onManageLicense}
            variant="outline"
            size="sm"
            icon={Settings}
          >
            Manage License
          </Button>
        )}
      </div>
    </div>
  );
}
