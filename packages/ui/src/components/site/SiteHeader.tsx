"use client";

import { Badge } from '@tremor/react';
import { Box, Menu, Search, X } from 'lucide-react';
import { useState, useEffect, type ReactNode } from 'react';
import { Button } from '../primitives/Button';

export interface NavLink {
  label: string;
  href: string;
  active?: boolean;
}

export interface SiteHeaderProps {
  productName?: string;
  productBadge?: string;
  logo?: ReactNode;
  links: NavLink[];
  actions?: ReactNode;
  searchPlaceholder?: string;
  onSearch?: (query: string) => void;
  className?: string;
  /**
   * Optional content to render in place of the default mobile menu when
   * the hamburger is open. Replaces both the chrome and the content — the
   * provided node is responsible for its own positioning, scrim, and
   * animation. SiteHeader continues to own the toggle button, open/close
   * state, body-scroll-lock, and Esc-to-close.
   *
   * Pass a function `(close) => ReactNode` to receive a programmatic
   * close handler (used by the docs drawer to auto-close on link tap).
   */
  mobileMenuContent?: ReactNode | ((close: () => void) => ReactNode);
  /**
   * Breakpoint at which the mobile hamburger gives way to the inline
   * desktop nav. Defaults to 'md' (768px). Pass 'lg' (1024px) when the
   * consumer needs the hamburger visible at tablet widths (e.g. docs
   * pages where the desktop sidebar is hidden until 1024px).
   */
  mobileBreakpoint?: 'md' | 'lg';
}

export function SiteHeader({
  productName = 'SourcePrep',
  productBadge,
  logo = <Box className="w-5 h-5" />,
  links,
  actions,
  searchPlaceholder = 'Search docs...',
  onSearch,
  className = '',
  mobileMenuContent,
  mobileBreakpoint = 'md',
}: SiteHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const close = () => setMobileMenuOpen(false);

  // Body scroll lock while menu open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  // Esc to close
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileMenuOpen]);

  // Force-close when viewport crosses the desktop breakpoint while open
  // (prevents body-scroll-lock from sticking and orphaning the menu state)
  useEffect(() => {
    const query = mobileBreakpoint === 'lg' ? '(min-width: 1024px)' : '(min-width: 768px)';
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) close();
    };
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [mobileBreakpoint]);

  const handleSearch = (query: string) => {
    if (onSearch) {
      onSearch(query);
    } else {
      window.location.href = `https://docs.sourceprep.io?q=${encodeURIComponent(query)}`;
    }
  };

  // Visibility classes derived from breakpoint
  const hamburgerClass = mobileBreakpoint === 'lg' ? 'lg:hidden' : 'md:hidden';
  const desktopNavClass = mobileBreakpoint === 'lg' ? 'hidden lg:flex' : 'hidden md:flex';
  const desktopActionsClass = mobileBreakpoint === 'lg' ? 'hidden lg:flex' : 'hidden md:flex';

  const renderedSlot =
    typeof mobileMenuContent === 'function' ? mobileMenuContent(close) : mobileMenuContent;

  return (
    <header className={`sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md ${className}`}>
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left: Logo & Desktop Nav */}
        <div className="flex items-center gap-8">
          <a href="/" className="flex items-center font-mono font-bold text-lg tracking-tight text-text hover:text-primary transition-colors">
            <span className="text-primary">{logo}</span>
            {productName}
            {productBadge && (
              <Badge size="xs" color="blue" className="ml-1 px-1.5 py-0">
                {productBadge}
              </Badge>
            )}
          </a>

          <nav className={`${desktopNavClass} items-center gap-6`}>
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors hover:text-primary ${
                  link.active ? 'text-primary' : 'text-text-muted'
                }`}
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>

        {/* Right: Actions & Mobile Toggle */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:block relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" />
            <input
              type="text"
              placeholder={searchPlaceholder}
              className="h-9 w-64 rounded-md border border-border bg-surface-raised pl-9 pr-4 text-sm text-text placeholder:text-text-subtle focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-all"
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(e.currentTarget.value)}
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <kbd className="hidden rounded border border-border bg-surface px-1.5 font-mono text-[10px] font-medium text-text-subtle sm:inline-block">
                ⌘K
              </kbd>
            </div>
          </div>

          <div className={`${desktopActionsClass} items-center gap-3`}>
            {actions}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className={hamburgerClass}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        renderedSlot !== undefined ? (
          // Custom slot — caller provides full chrome (positioning, scrim, animation)
          renderedSlot
        ) : (
          // Default: top-anchored dropdown with site links
          <div
            className={`absolute top-full left-0 w-full ${hamburgerClass} border-b border-border bg-background p-4 space-y-4 shadow-lg overflow-y-auto`}
            style={{ maxHeight: 'calc(100vh - 3.5rem)' }}
          >
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" />
              <input
                type="text"
                placeholder={searchPlaceholder}
                className="h-10 w-full rounded-md border border-border bg-surface-raised pl-10 pr-4 text-sm text-text placeholder:text-text-subtle focus:border-primary focus:outline-none"
                onKeyDown={(e) => e.key === 'Enter' && handleSearch(e.currentTarget.value)}
              />
            </div>

            <nav className="flex flex-col space-y-3">
              {links.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className={`text-base font-medium px-2 py-1.5 rounded-md hover:bg-surface-raised ${
                    link.active ? 'text-primary bg-surface-raised' : 'text-text-muted'
                  }`}
                >
                  {link.label}
                </a>
              ))}
            </nav>

            <div className="pt-4 border-t border-border flex flex-col gap-3">
              {actions}
            </div>
          </div>
        )
      )}
    </header>
  );
}
