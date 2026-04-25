import type { ReactNode } from 'react';
import { Button } from '../primitives/Button';
import { Select } from '../primitives/Select';
import { SettingRow } from './SettingRow';

/**
 * ScopedActionRow — a `SettingRow` whose control is a (Select + Button) pair.
 *
 * Used for one-shot actions where the user picks a scope, then triggers the
 * action with a single click — e.g. the consolidated Danger Zone Rebuild
 * row (scope = all / sync / enrichment) and Reset row (scope = all /
 * enrichment / finalize).
 *
 * The Button stays full-width inside SettingRow's ~260px right column;
 * Select takes the remaining space. Matches the typography and spacing of
 * the other DangerZone rows so the consolidated rows feel native.
 */
export interface ScopedActionRowProps<T extends string> {
  label: string;
  description: ReactNode;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  buttonLabel: string;
  buttonVariant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  buttonClassName?: string;
  onClick: () => void;
  disabled?: boolean;
  last?: boolean;
}

export function ScopedActionRow<T extends string>({
  label,
  description,
  options,
  value,
  onChange,
  buttonLabel,
  buttonVariant = 'default',
  buttonClassName,
  onClick,
  disabled = false,
  last = false,
}: ScopedActionRowProps<T>) {
  const control = (
    <div className="flex w-full items-center gap-2">
      <Select
        size="sm"
        className="flex-1 min-w-0"
        options={options}
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        disabled={disabled}
        aria-label={`${label} scope`}
      />
      <Button
        variant={buttonVariant}
        size="sm"
        onClick={onClick}
        disabled={disabled}
        className={buttonClassName}
      >
        {buttonLabel}
      </Button>
    </div>
  );

  return (
    <SettingRow label={label} description={description} control={control} last={last} />
  );
}
