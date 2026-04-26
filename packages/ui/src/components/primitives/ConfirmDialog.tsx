import { useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle } from 'lucide-react';
import { Button } from './Button';
import { cn } from '../../lib/utils';

export interface ConfirmDialogProps {
  /** Whether the dialog is currently visible */
  open: boolean;
  /** Called when the user confirms the action */
  onConfirm: () => void;
  /** Called when the user cancels (or presses Escape) */
  onCancel: () => void;
  /** Dialog title */
  title: string;
  /** Main description text */
  description: string;
  /** Optional warning line shown in error color below description */
  warning?: string;
  /** Label for the confirm button */
  confirmLabel?: string;
  /** Label for the cancel button */
  cancelLabel?: string;
  /** Variant controls the confirm button style */
  variant?: 'destructive' | 'default';
  className?: string;
  /** Optional extra UI rendered between description and action buttons (e.g. typed-confirm input) */
  children?: ReactNode;
  /** When true, disables the confirm button (e.g. while a typed-confirm gate is unmet) */
  confirmDisabled?: boolean;
  /** Test hook prefix; emits `${testId}` on the dialog container, `${testId}-confirm` on the confirm button, `${testId}-cancel` on the cancel button. */
  testId?: string;
}

export function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title,
  description,
  warning = 'This action cannot be undone.',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'destructive',
  className,
  children,
  confirmDisabled = false,
  testId,
}: ConfirmDialogProps) {
  // Close on Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        // Prevent window-level Esc listeners (e.g. SettingsOverlay) from also
        // firing and closing the parent surface in the same keystroke.
        e.stopPropagation();
        onCancel();
      }
    },
    [onCancel],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  if (!open) return null;

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm',
        className,
      )}
      onClick={(e) => {
        // Close when clicking the backdrop
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        className="mx-4 w-full max-w-md rounded-lg border border-error/30 bg-surface p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-desc"
        data-testid={testId}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 shrink-0 rounded-full bg-error/10 p-2">
            <AlertTriangle className="h-5 w-5 text-error" />
          </div>
          <div className="space-y-2">
            <h3 id="confirm-dialog-title" className="text-sm font-semibold text-text">
              {title}
            </h3>
            <p id="confirm-dialog-desc" className="text-xs text-text-muted leading-relaxed">
              {description}
            </p>
            {warning && (
              <p className="text-xs font-medium text-error">{warning}</p>
            )}
          </div>
        </div>
        {children && <div className="mt-3">{children}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
            data-testid={testId ? `${testId}-cancel` : undefined}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant}
            size="sm"
            onClick={onConfirm}
            disabled={confirmDisabled}
            data-testid={testId ? `${testId}-confirm` : undefined}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
