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
        "inline-flex rounded-full border p-0.5 text-xs font-medium select-none gap-0.5 outline-none ring-0 no-flash",
        disabled
          ? "border-border/40 bg-surface-raised/50 opacity-60 cursor-not-allowed"
          : "border-border/60 bg-surface-raised"
      )}
      style={{ WebkitTapHighlightColor: 'transparent' }}
      title={disabled ? disabledReason : undefined}
    >
      {options.map((label, i) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={() => onChange?.(i === 1)}
          style={{ WebkitTapHighlightColor: 'transparent', outline: 'none', boxShadow: 'none' }}
          className={cn(
            "rounded-full py-1 px-3.5 text-center transition-colors duration-150 min-w-[4rem] border !outline-none !ring-0 !shadow-none focus:!outline-none focus:!ring-0 focus-visible:!outline-none focus-visible:!ring-0 touch-manipulation no-flash",
            i === idx
              ? disabled
                ? "bg-border/40 text-text-subtle border-transparent"
                : "bg-primary/20 text-primary border-primary/40"
              : disabled
                ? "text-text-subtle/50 border-transparent"
                : "text-text-subtle hover:text-text-muted border-transparent"
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
        "inline-flex rounded-full border p-0.5 text-xs font-medium select-none gap-0.5 outline-none ring-0 no-flash",
        disabled
          ? "border-border/40 bg-surface-raised/50 opacity-60 cursor-not-allowed"
          : "border-border/60 bg-surface-raised"
      )}
      style={{ WebkitTapHighlightColor: 'transparent' }}
      title={disabled ? disabledReason : undefined}
    >
      {options.map((opt, i) => (
        <button
          key={opt.value}
          type="button"
          disabled={disabled}
          style={{ WebkitTapHighlightColor: 'transparent', outline: 'none', boxShadow: 'none' }}
          onClick={() => onChange?.(opt.value)}
          className={cn(
            "rounded-full py-1 px-3.5 text-center transition-colors duration-150 min-w-[3.5rem] border !outline-none !ring-0 !shadow-none focus:!outline-none focus:!ring-0 focus-visible:!outline-none focus-visible:!ring-0 touch-manipulation no-flash",
            i === idx
              ? disabled
                ? "bg-border/40 text-text-subtle border-transparent"
                : "bg-primary/20 text-primary border-primary/40"
              : disabled
                ? "text-text-subtle/50 border-transparent"
                : "text-text-subtle hover:text-text-muted border-transparent"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

