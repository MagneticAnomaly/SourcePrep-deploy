"use client";

import { useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { DocsSidebarNav, type DocNode } from './DocsSidebarNav';
import type { NavLink } from '../site/SiteHeader';

export interface MobileDocsDrawerProps {
  /** Sidebar tree (already flagged with active state by the consumer). */
  items: DocNode[];
  /** Site-level nav links shown in the sticky bottom strip. */
  siteLinks: NavLink[];
  /** Optional search submit handler. Defaults to redirecting to /search. */
  onSearch?: (query: string) => void;
  /** Called when the user dismisses the drawer (scrim tap, link tap, search submit, Esc). */
  onClose: () => void;
  /** Placeholder for the search input. */
  searchPlaceholder?: string;
}

export function MobileDocsDrawer({
  items,
  siteLinks,
  onSearch,
  onClose,
  searchPlaceholder = 'Search documentation...',
}: MobileDocsDrawerProps) {
  const searchRef = useRef<HTMLInputElement>(null);

  // Autofocus search on open
  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  const handleSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    const q = e.currentTarget.value.trim();
    if (!q) return;
    if (onSearch) onSearch(q);
    onClose();
  };

  return (
    <>
      {/* Scrim — click to close */}
      <div
        className="fixed inset-0 top-14 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
        onClick={onClose}
        aria-hidden
      />

      {/* Drawer panel */}
      <div
        className="prep-drawer-slide-in fixed top-14 left-0 z-50 flex flex-col w-[85%] max-w-[320px] h-[calc(100vh-3.5rem)] bg-background border-r border-border shadow-xl lg:hidden"
        role="dialog"
        aria-label="Documentation navigation"
      >
        {/* Search */}
        <div className="border-b border-border bg-background p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" />
            <input
              ref={searchRef}
              type="text"
              placeholder={searchPlaceholder}
              className="h-10 w-full rounded-md border border-border bg-surface-raised pl-10 pr-4 text-sm text-text placeholder:text-text-subtle focus:border-primary focus:outline-none"
              onKeyDown={handleSearchKey}
            />
          </div>
        </div>

        {/* Scrollable tree */}
        <nav className="flex-1 overflow-y-auto p-4">
          <DocsSidebarNav items={items} className="w-full" onLinkClick={onClose} />
        </nav>

        {/* Sticky site-link strip */}
        <div className="border-t border-border bg-surface-raised px-4 py-3">
          <ul className="flex items-center justify-between gap-2 text-xs text-text-muted">
            {siteLinks.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  onClick={onClose}
                  className="hover:text-primary transition-colors"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
