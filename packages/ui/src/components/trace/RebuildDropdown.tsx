/**
 * RebuildDropdown — Phase 117 Rebuild Granularity
 *
 * A split-button dropdown that lets the user trigger a scoped rebuild:
 *   - Primary "Rebuild" button → triggers a full rebuild (scope = 'all')
 *   - Caret → opens a dropdown with three scope options:
 *       • Rebuild Sync (1–5)
 *       • Rebuild Enrichment (6–10)
 *       • Rebuild All (1–15)
 *
 * The PRIMARY_SCOPE and MENU_ITEMS exports are the authoritative source of
 * truth for the button's default action and the dropdown menu contents.
 * Tests exercise these pure exports; interactive behaviour (open/close,
 * outside-click, keyboard) is covered by Storybook stories.
 */
import { useState, useEffect, useRef } from 'react';
import { ChevronDown } from 'lucide-react';
import type { RebuildScope } from '../../types';

// ── Public contracts ──────────────────────────────────────────

export interface RebuildMenuItem {
  scope: RebuildScope;
  label: string;
}

/** Scope triggered by the primary "Rebuild" button (no dropdown). */
export const PRIMARY_SCOPE: RebuildScope = 'all';

/** Ordered list of dropdown menu items. */
export const MENU_ITEMS: RebuildMenuItem[] = [
  { scope: 'sync',       label: 'Rebuild Sync (1–5)' },
  { scope: 'enrichment', label: 'Rebuild Enrichment (6–10)' },
  { scope: 'all',        label: 'Rebuild All (1–15)' },
];

// ── Component props ───────────────────────────────────────────

export interface RebuildDropdownProps {
  /** Called when the user picks a scope (primary button or menu item). */
  onRebuild: (scope: RebuildScope) => void;
  /** When true, both the primary button and the caret are disabled. */
  disabled: boolean;
  /** Optional extra class names applied to the outermost wrapper. */
  className?: string;
}

// ── Component ─────────────────────────────────────────────────

export function RebuildDropdown({ onRebuild, disabled, className }: RebuildDropdownProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  /** Close the dropdown when the user clicks outside the component. */
  useEffect(() => {
    if (!open) return;

    function handleOutsideClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', handleOutsideClick);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [open]);

  function pick(scope: RebuildScope) {
    setOpen(false);
    onRebuild(scope);
  }

  return (
    <div ref={wrapperRef} className={`relative inline-flex${className ? ` ${className}` : ''}`}>
      {/* ── Primary button ── */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => pick(PRIMARY_SCOPE)}
        className={[
          'px-3 py-1.5 rounded-l text-sm font-medium transition-colors',
          'bg-blue-600 text-white hover:bg-blue-700',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'border border-blue-600',
        ].join(' ')}
      >
        Rebuild
      </button>

      {/* ── Caret / toggle ── */}
      <button
        type="button"
        disabled={disabled}
        aria-label="Open rebuild options"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={[
          'px-1.5 py-1.5 rounded-r text-sm font-medium transition-colors',
          'bg-blue-600 text-white hover:bg-blue-700',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'border border-blue-600 border-l-blue-500/50',
        ].join(' ')}
      >
        <ChevronDown
          size={14}
          className={`transition-transform${open ? ' rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {/* ── Dropdown menu ── */}
      {open && (
        <ul
          role="menu"
          className={[
            'absolute right-0 top-full mt-1 z-50 min-w-[180px]',
            'rounded-md border border-border bg-surface shadow-lg',
            'py-1 text-sm',
          ].join(' ')}
        >
          {MENU_ITEMS.map((item) => (
            <li key={item.scope} role="none">
              <button
                type="button"
                role="menuitem"
                disabled={disabled}
                onClick={() => pick(item.scope)}
                className={[
                  'w-full text-left px-3 py-1.5',
                  'text-text-primary hover:bg-hover transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                ].join(' ')}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
