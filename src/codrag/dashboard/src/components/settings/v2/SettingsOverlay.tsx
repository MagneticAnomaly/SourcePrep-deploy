// src/codrag/dashboard/src/components/settings/v2/SettingsOverlay.tsx
import { createPortal } from 'react-dom';
import { useEffect, useRef } from 'react';
import { ArrowLeft, X } from 'lucide-react';
import { cn } from '@codrag/ui';
import { SettingsNav } from './SettingsNav';
import { useSettingsRoute } from './useSettingsRoute';
import type { SettingsPageId } from './routeParser';
import { DEVELOPER_PAGES } from './routeParser';
import { isDevBuild } from './devGate';

export interface SettingsOverlayProps {
  /** page body renderer — host wires this to the page registry */
  renderPage: (page: SettingsPageId) => React.ReactNode;
  /** active project name for the nav group label; null disables Project nav */
  projectName: string | null;
  /** called when user tries to close but a Project page is dirty; returns true if safe to close */
  confirmCloseIfDirty?: () => boolean;
}

export function SettingsOverlay({
  renderPage, projectName, confirmCloseIfDirty,
}: SettingsOverlayProps) {
  const { page, setPage, close } = useSettingsRoute();
  const backRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (page !== null) backRef.current?.focus();
  }, [page]);

  useEffect(() => {
    if (page === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [page, close, confirmCloseIfDirty]);

  // Developer pages are dev-build only. Defence-in-depth: if someone lands
  // on one via URL in a production build, redirect to the first global page.
  useEffect(() => {
    if (page === null) return;
    const isDeveloperPage = (DEVELOPER_PAGES as readonly string[]).includes(page);
    if (isDeveloperPage && !isDevBuild()) setPage('appearance');
  }, [page, setPage]);

  if (page === null) return null;

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-50 bg-surface',
        'flex flex-col',
        'animate-settings-overlay-in',
      )}
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <header className="h-14 border-b border-border-subtle px-4 flex items-center gap-3">
        <button
          ref={backRef}
          type="button"
          onClick={() => {
            if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
          }}
          aria-label="Close settings"
          className="p-1 rounded-md hover:bg-surface-raised text-text-muted"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h2 className="text-base font-medium text-text">Settings</h2>
        <div className="ml-auto flex items-center gap-2">
          <kbd className="text-xs text-text-muted bg-surface-raised rounded px-1.5 py-0.5">⌘,</kbd>
          <button
            type="button"
            onClick={() => {
              if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
            }}
            aria-label="Close settings"
            className="p-1 rounded-md hover:bg-surface-raised text-text-muted"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <SettingsNav
          activePage={page}
          onNavigate={setPage}
          projectName={projectName}
        />
        <main className="flex-1 overflow-y-auto">
          {renderPage(page)}
        </main>
      </div>
    </div>,
    document.body,
  );
}
