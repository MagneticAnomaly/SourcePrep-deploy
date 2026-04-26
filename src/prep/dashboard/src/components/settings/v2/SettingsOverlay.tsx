// src/prep/dashboard/src/components/settings/v2/SettingsOverlay.tsx
import { createPortal } from 'react-dom';
import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Button } from '@prep/ui';
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
}

export function SettingsOverlay({
  renderPage, projectName,
}: SettingsOverlayProps) {
  const { page, setPage, close } = useSettingsRoute();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (page !== null) closeRef.current?.focus();
  }, [page]);

  useEffect(() => {
    if (page === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        return;
      }
      // ⌘, (Ctrl+, on non-Mac) closes the overlay when already open.
      const mod = navigator.platform.includes('Mac') ? e.metaKey : e.ctrlKey;
      if (mod && e.key === ',') {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [page, close]);

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
      className="fixed inset-0 z-[110]"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={() => close()}
      />
      <div className="relative z-10 h-full w-full bg-background text-text flex flex-col">
        <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-lg font-semibold truncate">Settings</span>
          </div>
          <Button
            ref={closeRef}
            variant="ghost"
            size="icon-sm"
            onClick={() => close()}
            aria-label="Close settings"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col lg:flex-row lg:gap-10">
              <aside className="hidden lg:block w-64 shrink-0 py-10 sticky top-0 h-screen overflow-y-auto border-r border-border pr-6">
                <SettingsNav
                  activePage={page}
                  onNavigate={setPage}
                  projectName={projectName}
                />
              </aside>
              <main className="flex-1 py-10 min-w-0">
                {renderPage(page)}
              </main>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
