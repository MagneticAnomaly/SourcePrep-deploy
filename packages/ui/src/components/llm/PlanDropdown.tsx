import { useEffect, useState } from 'react';

export interface PlanLimitTier {
  tier_key: string;
  tier_label: string;
  concurrent: number;
  source_url: string;
}

export interface PlanLimitProvider {
  label: string;
  auto_detect: boolean;
  auto_detect_reason?: string;
  tiers: PlanLimitTier[];
}

export interface PlanLimitsTable {
  version: number;
  providers: Record<string, PlanLimitProvider>;
}

export interface PlanDropdownProps {
  /** Provider key in the limits table — e.g. "ollama_cloud", "openai". */
  providerKey: string;
  /** Current selection. Either a tier_key, "auto", "custom", or undefined. */
  value: string | undefined;
  /** Custom override value (used when value === "custom"). */
  customConcurrent: number;
  /** Pre-fetched limits table. Required for storybook; in production the
   * EndpointManager fetches once and passes down. */
  limits: PlanLimitsTable;
  /** Called when the user picks a tier OR types a custom number. */
  onChange: (next: { plan_tier: string; cloud_concurrency: number }) => void;
}

const SENTINEL_AUTO = 'auto';
const SENTINEL_CUSTOM = 'custom';

export function PlanDropdown(props: PlanDropdownProps) {
  const { providerKey, value, customConcurrent, limits, onChange } = props;
  const provider = limits.providers[providerKey];

  // Local state for "Custom..." input.
  const [customInput, setCustomInput] = useState<number>(customConcurrent || 1);
  useEffect(() => {
    setCustomInput(customConcurrent || 1);
  }, [customConcurrent]);

  if (!provider) {
    return (
      <div className="text-xs text-amber-400">
        No plan options for provider <code>{providerKey}</code>.
      </div>
    );
  }

  // Compute the active concurrent based on selection.
  const activeConcurrent =
    value === SENTINEL_AUTO ? 0 :  // 0 = "auto" sentinel for backend
    value === SENTINEL_CUSTOM ? customInput :
    (provider.tiers.find((t) => t.tier_key === value)?.concurrent ?? 0);

  const sourceUrl =
    (provider.tiers.find((t) => t.tier_key === value)?.source_url) ??
    (provider.tiers[0]?.source_url ?? '');

  let sourceHost = '';
  if (sourceUrl) {
    try {
      sourceHost = new URL(sourceUrl).host;
    } catch {
      sourceHost = '';
    }
  }

  return (
    <div className="space-y-1.5">
      <label className="text-[11px] uppercase tracking-wider text-text-muted">Plan</label>
      <select
        className="w-full bg-surface-raised border border-border rounded px-2 py-1 text-sm"
        value={value ?? ''}
        onChange={(e) => {
          const next = e.target.value;
          if (next === '') {
            onChange({ plan_tier: '', cloud_concurrency: 0 });
          } else if (next === SENTINEL_AUTO) {
            onChange({ plan_tier: SENTINEL_AUTO, cloud_concurrency: 0 });
          } else if (next === SENTINEL_CUSTOM) {
            onChange({ plan_tier: SENTINEL_CUSTOM, cloud_concurrency: customInput });
          } else {
            const tier = provider.tiers.find((t) => t.tier_key === next);
            onChange({ plan_tier: next, cloud_concurrency: tier?.concurrent ?? 0 });
          }
        }}
      >
        <option value="" disabled>— pick a plan —</option>
        {provider.auto_detect && (
          <option value={SENTINEL_AUTO}>Auto-detect from headers (recommended)</option>
        )}
        {provider.tiers.map((t) => (
          <option key={t.tier_key} value={t.tier_key}>
            {t.tier_label} ({t.concurrent} concurrent)
          </option>
        ))}
        <option value={SENTINEL_CUSTOM}>Custom…</option>
      </select>

      {value === SENTINEL_CUSTOM && (
        <input
          type="number"
          min={1}
          max={1000}
          value={customInput}
          onChange={(e) => {
            const n = Math.max(1, Math.min(1000, parseInt(e.target.value || '1', 10)));
            setCustomInput(n);
            onChange({ plan_tier: SENTINEL_CUSTOM, cloud_concurrency: n });
          }}
          className="w-full bg-surface-raised border border-border rounded px-2 py-1 text-sm"
        />
      )}

      {sourceHost && (
        <p className="text-[10px] text-text-muted">
          ⓘ From{' '}
          <a href={sourceUrl} target="_blank" rel="noreferrer" className="underline">
            {sourceHost}
          </a>
        </p>
      )}

      <div className="text-[11px] text-text-base mt-2 pt-2 border-t border-border">
        Active: <strong>{activeConcurrent === 0 ? 'auto' : `${activeConcurrent} concurrent`}</strong>
        {value === SENTINEL_AUTO && provider.auto_detect_reason && (
          <span className="ml-1 text-text-muted">({provider.auto_detect_reason})</span>
        )}
      </div>
    </div>
  );
}
