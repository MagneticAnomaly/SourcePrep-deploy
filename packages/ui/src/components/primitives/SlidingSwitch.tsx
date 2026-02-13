import { cn } from '../../lib/utils';

export interface SlidingSwitch2Props {
  value: boolean;
  onChange?: (v: boolean) => void;
  disabled?: boolean;
  disabledReason?: string;
}

/** 2-position sliding switch: Manual ↔ Auto */
export function SlidingSwitch2({
  value,
  onChange,
  disabled,
  disabledReason,
}: SlidingSwitch2Props) {
  const options = ['Manual', 'Auto'] as const;
  const idx = value ? 1 : 0;
  return (
    <div
      className={cn(
        "inline-flex rounded-full border p-0.5 text-xs font-medium select-none gap-0.5",
        disabled
          ? "border-border/40 bg-surface-raised/50 opacity-60 cursor-not-allowed"
          : "border-border/60 bg-surface-raised"
      )}
      title={disabled ? disabledReason : undefined}
    >
      {options.map((label, i) => (
        <button
          key={label}
          disabled={disabled}
          onClick={() => onChange?.(i === 1)}
          className={cn(
            "rounded-full py-1 px-3.5 text-center transition-all duration-150 min-w-[4rem]",
            i === idx
              ? disabled
                ? "bg-border/40 text-text-subtle"
                : "bg-primary/20 text-primary border border-primary/40"
              : disabled
                ? "text-text-subtle/50"
                : "text-text-subtle hover:text-text-muted"
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export interface SlidingSwitch3Props<T extends string = string> {
  value: T;
  options: { label: string; value: T }[];
  onChange?: (v: T) => void;
  disabled?: boolean;
  disabledReason?: string;
}

/** N-position sliding switch (typically 3: Manual | Auto | Scheduled) */
export function SlidingSwitch3<T extends string = string>({
  value,
  options,
  onChange,
  disabled,
  disabledReason,
}: SlidingSwitch3Props<T>) {
  const idx = options.findIndex(o => o.value === value);
  return (
    <div
      className={cn(
        "inline-flex rounded-full border p-0.5 text-xs font-medium select-none gap-0.5",
        disabled
          ? "border-border/40 bg-surface-raised/50 opacity-60 cursor-not-allowed"
          : "border-border/60 bg-surface-raised"
      )}
      title={disabled ? disabledReason : undefined}
    >
      {options.map((opt, i) => (
        <button
          key={opt.value}
          disabled={disabled}
          onClick={() => onChange?.(opt.value)}
          className={cn(
            "rounded-full py-1 px-3.5 text-center transition-all duration-150 min-w-[3.5rem]",
            i === idx
              ? disabled
                ? "bg-border/40 text-text-subtle"
                : "bg-primary/20 text-primary border border-primary/40"
              : disabled
                ? "text-text-subtle/50"
                : "text-text-subtle hover:text-text-muted"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
