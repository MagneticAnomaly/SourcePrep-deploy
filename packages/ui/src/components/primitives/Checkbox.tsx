import { Check } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Optional id so a `<label htmlFor>` can wire up. */
  id?: string;
  /** Size variant. `sm` matches dense settings rows. */
  size?: 'sm' | 'md';
  className?: string;
  'aria-label'?: string;
}

/**
 * Checkbox — square check input with the design-system primary tint.
 *
 * Replaces native <input type="checkbox" className="accent-..."> across the
 * app so checkbox styling stays in lockstep with the token set. Uses a real
 * <button role="checkbox"> rather than a hidden native input so we can
 * paint the check icon ourselves and keep visuals identical across browsers.
 */
export function Checkbox({
  checked,
  onCheckedChange,
  disabled = false,
  id,
  size = 'md',
  className,
  ...rest
}: CheckboxProps) {
  const dim = size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4';
  const iconDim = size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3';
  return (
    <button
      type="button"
      role="checkbox"
      id={id}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onCheckedChange(!checked)}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded border transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
        dim,
        checked
          ? 'bg-primary border-primary text-background'
          : 'bg-surface border-border hover:border-primary/60',
        disabled && 'cursor-not-allowed opacity-50',
        !disabled && 'cursor-pointer',
        className,
      )}
      {...rest}
    >
      {checked && <Check className={iconDim} strokeWidth={3} />}
    </button>
  );
}
