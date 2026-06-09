/**
 * Shared toast primitive — used by the SidebarPipelineQueue cancel
 * flow (2026-06-08 design B+heuristic). Intentionally minimal: one
 * fixed-position stack, dismiss on click or timeout, optional
 * action button. Not a full notification system.
 */
import { useState, useCallback, createContext, useContext, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

export type ToastVariant = 'info' | 'warn' | 'error';

export interface ToastInput {
  id?: string;
  title: string;
  body?: string;
  variant?: ToastVariant;
  action?: { label: string; onClick: () => void };
  durationMs?: number; // default 12000; 0 = sticky
}

interface ToastEntry {
  id: string;
  title: string;
  body?: string;
  variant: ToastVariant;
  action?: ToastInput['action'];
  durationMs: number;
}

interface ToastContextValue {
  push: (t: ToastInput) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used inside <ToastProvider>');
  }
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (t: ToastInput): string => {
      const id = t.id ?? `t-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const entry: ToastEntry = {
        id,
        title: t.title,
        body: t.body,
        variant: t.variant ?? 'info',
        action: t.action,
        durationMs: t.durationMs ?? 12000,
      };
      setToasts((prev) => [...prev.filter((x) => x.id !== id), entry]);
      if (entry.durationMs > 0) {
        window.setTimeout(() => dismiss(id), entry.durationMs);
      }
      return id;
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ push, dismiss }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto rounded-md border px-3 py-2 shadow-lg backdrop-blur-sm text-sm',
              t.variant === 'error' && 'bg-red-950/90 border-red-700 text-red-100',
              t.variant === 'warn' && 'bg-amber-950/90 border-amber-700 text-amber-100',
              t.variant === 'info' && 'bg-slate-900/90 border-slate-700 text-slate-100',
            )}
            role="status"
          >
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium">{t.title}</div>
                {t.body && <div className="text-xs text-slate-300 mt-0.5">{t.body}</div>}
                {t.action && (
                  <button
                    className="text-xs font-medium underline hover:no-underline mt-1.5"
                    onClick={() => {
                      t.action!.onClick();
                      dismiss(t.id);
                    }}
                  >
                    {t.action.label}
                  </button>
                )}
              </div>
              <button
                aria-label="Dismiss"
                className="text-slate-400 hover:text-slate-100"
                onClick={() => dismiss(t.id)}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
