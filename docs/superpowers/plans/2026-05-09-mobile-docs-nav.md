# Mobile Docs Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore full docs sidebar navigation on phones and tablets via an off-canvas left drawer, fix the latent desktop-active-highlight bug along the way, and add a compact "On this page" disclosure for mobile/tablet TOC.

**Architecture:** Three additive props on `SiteHeader` (`mobileMenuContent`, `mobileBreakpoint`, plus a new `Esc`/matchMedia cleanup `useEffect`); a new `MobileDocsDrawer` component that brings its own off-canvas chrome (scrim + fixed-left panel + slide animation) and reuses the existing `DocsSidebarNav` for the tree; a `currentPath` prop plumbed through `DocsLayout` from `usePathname()` in `ClientLayout`. `@prep/ui` stays Next.js-agnostic — pathname is supplied by the consumer, not imported by the package.

**Tech Stack:** React 18, Next.js 14 (`websites/apps/docs`), Tailwind CSS, `tailwind-merge` via `cn` helper, Storybook 7 (visual review), TypeScript strict (typecheck = primary regression gate). No unit-test runner exists in `@prep/ui` — verification uses `npm run typecheck`, `npm run lint`, `npm run build`, Storybook, and visual smoke at multiple viewports.

**Spec:** `docs/superpowers/specs/2026-05-08-mobile-docs-nav-design.md`

**Branching:** Optional. Scope is small (~7 small commits, all additive on `@prep/ui`). Direct work on `main` is acceptable; a worktree on `feat/mobile-docs-nav` is fine if you prefer review isolation.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `packages/ui/src/components/docs/DocsSidebarNav.tsx` | modify | Add `onLinkClick?: () => void` prop, call from each anchor's `onClick`. |
| `packages/ui/src/components/docs/DocsLayout.tsx` | modify | Add `currentPath?: string` prop. New `withActive(items, currentPath)` helper marks active leaves. Pass `mobileBreakpoint="lg"` and a render-prop `mobileMenuContent` to `SiteHeader`. Add inline "On this page" disclosure above `<article>` (`xl:hidden`). |
| `packages/ui/src/components/docs/MobileDocsDrawer.tsx` | **new** | Off-canvas drawer chrome: scrim, fixed-left panel, slide-in animation. Sticky search top, scrollable `DocsSidebarNav`, sticky site-link strip bottom. |
| `packages/ui/src/components/docs/index.ts` | modify | Export `MobileDocsDrawer`. |
| `packages/ui/src/components/site/SiteHeader.tsx` | modify | Add `mobileMenuContent?: ReactNode \| ((close: () => void) => ReactNode)` and `mobileBreakpoint?: 'md' \| 'lg'` props. Render slot when provided (replaces both chrome and content). Flip toggle/desktop-nav visibility classes based on `mobileBreakpoint`. Add `Escape` keydown listener + `matchMedia` cleanup `useEffect`. |
| `websites/apps/docs/src/app/ClientLayout.tsx` | modify | Pass `currentPath={usePathname() ?? undefined}` into `DocsLayout`. |
| `packages/ui/src/stories/docs/MobileDocsDrawer.stories.tsx` | **new** | Storybook story for visual review at multiple viewports. |

No changes to: `websites/apps/docs/src/config/docs.ts`; `websites/apps/{marketing,payments,support}/src/app/ClientLayout.tsx`; any non-docs consumer of `SiteHeader`.

---

## Task 1: Add `onLinkClick` prop to `DocsSidebarNav`

Standalone, backwards-compatible. Unblocks auto-close-on-navigate for the mobile drawer. Desktop usage is unaffected (prop omitted = no-op).

**Files:**
- Modify: `packages/ui/src/components/docs/DocsSidebarNav.tsx`

- [ ] **Step 1: Add the prop and wire it to anchor `onClick`**

Replace the file with:

```tsx
import { cn } from '../../lib/utils';

export interface DocNode {
  title: string;
  href: string;
  active?: boolean;
  children?: DocNode[];
  expanded?: boolean;
}

export interface DocsSidebarNavProps {
  items: DocNode[];
  className?: string;
  /** Optional callback fired when any link inside the nav is clicked. Used by the mobile drawer to auto-close on navigate. */
  onLinkClick?: () => void;
}

export function DocsSidebarNav({ items, className, onLinkClick }: DocsSidebarNavProps) {
  return (
    <nav className={cn('w-4/5', className)}>
      <ul className="space-y-4">
        {items.map((section, idx) => {
          const headerClass =
            'font-semibold text-xs uppercase tracking-wider text-primary mb-3 px-2 border-t border-border pt-4 mt-2';
          return (
            <li key={idx}>
              {section.href ? (
                <a
                  href={section.href}
                  onClick={onLinkClick}
                  className={cn(headerClass, 'block hover:text-primary-hover transition-colors')}
                >
                  {section.title}
                </a>
              ) : (
                <h4 className={headerClass}>{section.title}</h4>
              )}
              {section.children && (
                <ul className="space-y-1">
                  {section.children.map((item) => (
                    <li key={item.href}>
                      <a
                        href={item.href}
                        onClick={onLinkClick}
                        className={cn(
                          'block px-2 py-1.5 text-sm rounded-md transition-colors',
                          item.active
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-text-muted hover:text-text hover:bg-surface-raised'
                        )}
                      >
                        {item.title}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
```

- [ ] **Step 2: Run typecheck — must pass with the new prop**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS, no errors. (The prop is optional and additive, so all existing call sites remain valid.)

- [ ] **Step 3: Run lint**

Run: `cd packages/ui && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/docs/DocsSidebarNav.tsx
git commit -m "feat(ui/docs): add onLinkClick prop to DocsSidebarNav for drawer auto-close"
```

---

## Task 2: Add `currentPath` prop and `withActive` helper to `DocsLayout`

Backwards-compatible (`currentPath?: string`). No mobile drawer yet — this task only fixes the latent active-highlight bug on the existing desktop sidebar.

**Files:**
- Modify: `packages/ui/src/components/docs/DocsLayout.tsx`

- [ ] **Step 1: Add the helper and the prop, mark active items, pass to desktop sidebar**

Replace the file with:

```tsx
import { useMemo, type ReactNode } from 'react';
import { cn } from '../../lib/utils';
import { DocsSidebarNav, type DocNode } from './DocsSidebarNav';
import { TableOfContents, type TocItem } from './TableOfContents';
import { SiteHeader, type SiteHeaderProps } from '../site/SiteHeader';
import { SiteFooter, type SiteFooterProps } from '../site/SiteFooter';

export interface DocsLayoutProps {
  headerProps: SiteHeaderProps;
  footerProps: SiteFooterProps;
  sidebarItems: DocNode[];
  tocItems?: TocItem[];
  /** Current pathname from the consumer (e.g. Next.js `usePathname()`). Used to mark active sidebar items. */
  currentPath?: string;
  children: ReactNode;
  className?: string;
}

function withActive(items: DocNode[], currentPath?: string): DocNode[] {
  if (!currentPath) return items;
  return items.map((section) => ({
    ...section,
    active: section.href === currentPath,
    children: section.children?.map((child) => ({
      ...child,
      active: child.href === currentPath,
    })),
  }));
}

export function DocsLayout({
  headerProps,
  footerProps,
  sidebarItems,
  tocItems,
  currentPath,
  children,
  className,
}: DocsLayoutProps) {
  const flagged = useMemo(() => withActive(sidebarItems, currentPath), [sidebarItems, currentPath]);

  return (
    <div className={cn('flex flex-col min-h-screen bg-background text-text', className)}>
      <SiteHeader {...headerProps} className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60" />

      <div className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row lg:gap-10">
          {/* Sidebar Navigation - Sticky on Desktop */}
          <aside className="hidden lg:block w-64 shrink-0 py-10 sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto border-r border-border pr-6">
            <DocsSidebarNav items={flagged} />
          </aside>

          {/* Main Content Area */}
          <main className="flex-1 py-10 min-w-0">
            <article className="prose prose-slate dark:prose-invert max-w-none">
              {children}
            </article>
          </main>

          {/* Table of Contents - Right Rail */}
          {tocItems && tocItems.length > 0 && (
            <aside className="hidden xl:block w-64 shrink-0 py-10 sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto pl-6">
              <TableOfContents items={tocItems} />
            </aside>
          )}
        </div>
      </div>

      <SiteFooter {...footerProps} className="border-t mt-auto" />
    </div>
  );
}
```

Note: `<MobileDocsDrawer />` is **not** wired yet. That happens in Task 6. This task is purely the active-state plumbing.

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Run lint**

Run: `cd packages/ui && npm run lint`
Expected: PASS.

- [ ] **Step 4: Build the package so consumers see the new prop**

Run: `cd packages/ui && npm run build`
Expected: PASS, `dist/index.d.ts` regenerated.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/docs/DocsLayout.tsx
git commit -m "feat(ui/docs): add currentPath prop + withActive helper to DocsLayout"
```

---

## Task 3: Wire `usePathname()` in the docs app's `ClientLayout.tsx`

After this task, the desktop docs sidebar correctly highlights the current page — visible visual confirmation that the active-state plumbing works end-to-end.

**Files:**
- Modify: `websites/apps/docs/src/app/ClientLayout.tsx`

- [ ] **Step 1: Pass `currentPath` into `DocsLayout`**

The file already imports `usePathname` and reads it (`pathname` is computed for the concept-page branch). Add it as a prop to the `DocsLayout` invocation. Replace the `return (<DocsLayout ...>)` block:

```tsx
  return (
    <DocsLayout
      headerProps={headerProps}
      footerProps={footerProps}
      sidebarItems={docsSidebar}
      currentPath={pathname ?? undefined}
    >
      {children}
    </DocsLayout>
  );
```

- [ ] **Step 2: Run typecheck on the docs app**

Run: `cd websites/apps/docs && npm run typecheck` (or from repo root: `npm run typecheck` to typecheck all workspaces).
Expected: PASS.

- [ ] **Step 3: Visual smoke — desktop sidebar active highlight**

Start dev server: `cd websites/apps/docs && npm run dev` (runs on port 3001).
Open `http://localhost:3001/guides/smart-search` in a desktop-width window.
Expected: in the left sidebar, the "Smart Search" link is highlighted (background `bg-primary/10`, text `text-primary`, font-medium). Other links remain unhighlighted.

If the highlight does not appear, inspect the rendered anchor — it should have classes including `bg-primary/10 text-primary font-medium`. The most likely cause is the docs app importing a stale `dist` build of `@prep/ui`; rerun `cd packages/ui && npm run build` and restart the dev server.

- [ ] **Step 4: Commit**

```bash
git add websites/apps/docs/src/app/ClientLayout.tsx
git commit -m "feat(docs): wire usePathname through DocsLayout so the sidebar highlights the current page"
```

---

## Task 4: Add `mobileMenuContent`, `mobileBreakpoint`, Esc, and matchMedia cleanup to `SiteHeader`

Backwards-compatible — when neither prop is set, behavior is byte-identical to today's code path. This unlocks Task 6's drawer wiring without breaking marketing/payments/support.

**Files:**
- Modify: `packages/ui/src/components/site/SiteHeader.tsx`

- [ ] **Step 1: Add the props, render-prop slot, Esc handler, and matchMedia cleanup**

Replace the file with:

```tsx
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
```

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Run lint**

Run: `cd packages/ui && npm run lint`
Expected: PASS.

- [ ] **Step 4: Cross-app sanity smoke (no regression for non-docs apps)**

Start the marketing site: `cd websites/apps/marketing && npm run dev`. Open at its dev port, narrow the window to ~600px (mobile width), tap the hamburger. The default top-anchored dropdown with site links should appear exactly as before. Tap a link — it navigates. Press Esc with the menu open — it closes (this is a new behavior, not a regression).

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/site/SiteHeader.tsx
git commit -m "feat(ui/site): SiteHeader gains mobileMenuContent slot, mobileBreakpoint, Esc, matchMedia cleanup"
```

---

## Task 5: Create `MobileDocsDrawer` component + Storybook story

The drawer is responsible for its own off-canvas chrome (scrim + fixed-left panel + slide-in). It composes `DocsSidebarNav` for the tree.

**Files:**
- Create: `packages/ui/src/components/docs/MobileDocsDrawer.tsx`
- Modify: `packages/ui/src/components/docs/index.ts`
- Create: `packages/ui/src/stories/docs/MobileDocsDrawer.stories.tsx`

- [ ] **Step 1: Create the drawer component**

Create `packages/ui/src/components/docs/MobileDocsDrawer.tsx`:

```tsx
"use client";

import { useEffect, useRef, type ReactNode } from 'react';
import { Search } from 'lucide-react';
import { DocsSidebarNav, type DocNode } from './DocsSidebarNav';
import type { NavLink } from '../site/SiteHeader';

export interface MobileDocsDrawerProps {
  /** Sidebar tree (already flagged with active state by the consumer). */
  items: DocNode[];
  /** Site-level nav links shown in the sticky bottom strip. */
  siteLinks: NavLink[];
  /** Optional search submit handler. Defaults to navigating to /search. */
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
        className="fixed top-14 left-0 z-50 flex flex-col w-[85%] max-w-[320px] h-[calc(100vh-3.5rem)] bg-background border-r border-border shadow-xl lg:hidden animate-in slide-in-from-left duration-200"
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
```

Notes:
- `animate-in slide-in-from-left duration-200` is from `tailwindcss-animate`. **Verify availability before committing**: open `packages/ui/tailwind.config.js` and check whether `tailwindcss-animate` is in the `plugins` array. If it is not, replace those classes with `transition-transform duration-200 ease-out` and add a small inline keyframe via `style={{ animation: 'slideInLeft 200ms ease-out' }}` plus a `@keyframes slideInLeft { from { transform: translateX(-100%); } to { transform: translateX(0); } }` block in `packages/ui/src/styles/index.css`. If you adopt the keyframe fallback, run `cd packages/ui && npm run build` to confirm CSS picks it up.

- [ ] **Step 2: Export from the docs barrel**

Edit `packages/ui/src/components/docs/index.ts`. Add the line:

```ts
export { MobileDocsDrawer, type MobileDocsDrawerProps } from './MobileDocsDrawer';
```

- [ ] **Step 3: Create the Storybook story**

Create `packages/ui/src/stories/docs/MobileDocsDrawer.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { MobileDocsDrawer } from '../../components/docs/MobileDocsDrawer';
import type { DocNode } from '../../components/docs/DocsSidebarNav';

const sampleItems: DocNode[] = [
  {
    title: 'Getting Started',
    href: '/getting-started',
    children: [
      { title: 'Introduction', href: '/getting-started' },
      { title: 'Installation', href: '/getting-started/installation' },
      { title: 'Quick Start', href: '/getting-started/quick-start' },
    ],
  },
  {
    title: 'Core Concepts',
    href: '',
    children: [
      { title: 'Local Indexing', href: '/concepts/indexing' },
      { title: 'Code Graph', href: '/concepts/code-graph' },
      { title: 'Graph Enrichment', href: '/concepts/graph-enrichment', active: true },
      { title: 'Context Assembly', href: '/concepts/context' },
    ],
  },
  {
    title: 'Guides',
    href: '',
    children: [
      { title: 'Smart Search', href: '/guides/smart-search' },
      { title: 'Path Weights', href: '/guides/path-weights' },
      { title: 'Codebase Audit', href: '/guides/codebase-audit' },
    ],
  },
];

const sampleSiteLinks = [
  { label: 'Home', href: 'https://sourceprep.io' },
  { label: 'Pricing', href: 'https://sourceprep.io/pricing' },
  { label: 'Download', href: 'https://sourceprep.io/download' },
  { label: 'FAQ', href: 'https://sourceprep.io/faq' },
];

const meta: Meta<typeof MobileDocsDrawer> = {
  title: 'Docs/MobileDocsDrawer',
  component: MobileDocsDrawer,
  parameters: {
    layout: 'fullscreen',
    viewport: { defaultViewport: 'mobile1' },
  },
};

export default meta;
type Story = StoryObj<typeof MobileDocsDrawer>;

export const Default: Story = {
  args: {
    items: sampleItems,
    siteLinks: sampleSiteLinks,
    onClose: () => {},
    onSearch: (q) => console.log('search:', q),
  },
};

export const TabletViewport: Story = {
  args: {
    items: sampleItems,
    siteLinks: sampleSiteLinks,
    onClose: () => {},
  },
  parameters: { viewport: { defaultViewport: 'tablet' } },
};
```

- [ ] **Step 4: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Run lint**

Run: `cd packages/ui && npm run lint`
Expected: PASS.

- [ ] **Step 6: Visual review in Storybook**

Run: `cd packages/ui && npm run storybook` (Storybook on port 6006).
Open `http://localhost:6006`, navigate to `Docs / MobileDocsDrawer / Default`.
Expected:
- Scrim covers the right ~15% of the viewport.
- Drawer panel is fixed to the left, ~85% width, full height below header offset.
- Search field at top, autofocused.
- Sidebar tree below the search, "Graph Enrichment" highlighted (since the story sets `active: true` on it).
- Sticky bottom strip with the four site links, distributed across the row.
- Clicking the scrim logs nothing (no-op `onClose`) — visual layout is the focus.

If the slide-in animation classes did not work (no `tailwindcss-animate` plugin), the panel will appear instantly without a slide. Confirm whether to use the fallback noted in Step 1 before committing.

- [ ] **Step 7: Build the package**

Run: `cd packages/ui && npm run build`
Expected: PASS, `dist/index.d.ts` includes `MobileDocsDrawer` and `MobileDocsDrawerProps`.

- [ ] **Step 8: Commit**

```bash
git add packages/ui/src/components/docs/MobileDocsDrawer.tsx \
        packages/ui/src/components/docs/index.ts \
        packages/ui/src/stories/docs/MobileDocsDrawer.stories.tsx
# also commit the styles/index.css if you used the keyframe fallback
git commit -m "feat(ui/docs): add MobileDocsDrawer with off-canvas chrome and Storybook story"
```

---

## Task 6: Wire `MobileDocsDrawer` into `DocsLayout`

After this task the docs site renders the drawer on phone/tablet viewports.

**Files:**
- Modify: `packages/ui/src/components/docs/DocsLayout.tsx`

- [ ] **Step 1: Pass `mobileBreakpoint="lg"` and `mobileMenuContent` render-prop into `SiteHeader`**

Replace the `<SiteHeader ... />` line in `DocsLayout` with:

```tsx
      <SiteHeader
        {...headerProps}
        mobileBreakpoint="lg"
        mobileMenuContent={(close) => (
          <MobileDocsDrawer
            items={flagged}
            siteLinks={headerProps.links}
            onSearch={headerProps.onSearch}
            onClose={close}
            searchPlaceholder={headerProps.searchPlaceholder}
          />
        )}
        className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      />
```

Add the import at the top of the file:

```tsx
import { MobileDocsDrawer } from './MobileDocsDrawer';
```

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Build the package**

Run: `cd packages/ui && npm run build`
Expected: PASS.

- [ ] **Step 4: Visual smoke at three breakpoints**

Restart the docs dev server: `cd websites/apps/docs && npm run dev` (port 3001).
Open `http://localhost:3001/guides/smart-search`. Use browser devtools' device-toolbar to test:

| Viewport | Expected |
|---|---|
| 375px (phone) | Hamburger visible. Tap it → drawer slides in from left, scrim covers right edge. Drawer shows search top, tree (Smart Search highlighted), site-link strip bottom. Tap any link → drawer closes and page navigates. Tap scrim → drawer closes. Press Esc → drawer closes. |
| 768px (tablet, below `lg`) | Hamburger still visible (this is the `mobileBreakpoint="lg"` effect). Drawer behaves the same. |
| 1024px (`lg`) | Hamburger hidden. Desktop sidebar appears. If the drawer was open at smaller width and you resize past 1024px, the drawer auto-closes (no stuck body-scroll-lock). |
| 1280px (`xl`) | Right-rail TOC visible. |

If the hamburger does not show at 768px, check the `hamburgerClass` derivation in `SiteHeader.tsx`. If the drawer doesn't slide in, check `tailwindcss-animate` per Task 5 Step 1.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/docs/DocsLayout.tsx
git commit -m "feat(ui/docs): wire MobileDocsDrawer into DocsLayout via SiteHeader.mobileMenuContent"
```

---

## Task 7: Add inline "On this page" disclosure for mobile/tablet TOC

Optional per-spec — defer if you want to ship just the drawer in v1. If shipping now, this fills the right-rail-TOC gap below `xl` (1280px).

**Files:**
- Modify: `packages/ui/src/components/docs/DocsLayout.tsx`

- [ ] **Step 1: Add the disclosure block above `<article>`**

Inside `DocsLayout`, in the `<main>` block, render a new `<details>` element above `<article>` when `tocItems` is non-empty. Replace the `<main>` block with:

```tsx
          <main className="flex-1 py-10 min-w-0">
            {tocItems && tocItems.length > 0 && (
              <details className="xl:hidden mb-6 rounded-md border border-border bg-surface-raised">
                <summary className="cursor-pointer select-none px-4 py-2 text-sm font-medium text-text-muted hover:text-text">
                  On this page
                </summary>
                <ul className="px-4 pb-3 pt-1 space-y-1.5 text-sm">
                  {tocItems.map((item, idx) => (
                    <li key={idx} style={{ paddingLeft: `${(item.level - 1) * 12}px` }}>
                      <a
                        href={item.href}
                        className={cn(
                          'block transition-colors',
                          item.active ? 'text-primary font-medium' : 'text-text-muted hover:text-text'
                        )}
                      >
                        {item.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <article className="prose prose-slate dark:prose-invert max-w-none">
              {children}
            </article>
          </main>
```

`xl:hidden` ensures the disclosure disappears once the right-rail TOC takes over at 1280px+.

- [ ] **Step 2: Run typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 3: Visual smoke**

The current docs site does not pass `tocItems` to `DocsLayout` (verified by grepping `tocItems` in `websites/apps/docs/src/app/ClientLayout.tsx` — none found). So the disclosure renders only when `tocItems` is supplied, which is a future enhancement. Confirm absence of regression at `http://localhost:3001/guides/smart-search` — the page should render exactly as before.

For positive verification, temporarily pass test data in `ClientLayout.tsx`:

```tsx
tocItems={[
  { title: 'Overview', href: '#overview', level: 2 },
  { title: 'Examples', href: '#examples', level: 2 },
]}
```

Confirm: at <1280px the disclosure renders collapsed, expands on tap, links are clickable; at 1280px+ the disclosure is hidden and the right-rail TOC appears. **Revert this temporary test data before committing.**

- [ ] **Step 4: Build the package**

Run: `cd packages/ui && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/docs/DocsLayout.tsx
git commit -m "feat(ui/docs): add 'On this page' disclosure for mobile/tablet (xl:hidden) when tocItems supplied"
```

---

## Task 8: Final verification + cross-app sanity

End-to-end smoke. No code changes; this task is the explicit gate before reporting "done".

**Files:** none modified.

- [ ] **Step 1: Run all-workspace typecheck**

From repo root: `npm run typecheck`
Expected: PASS in all workspaces (`@prep/ui`, docs, marketing, payments, support).

- [ ] **Step 2: Run all-workspace lint**

From repo root: `npm run lint`
Expected: PASS.

- [ ] **Step 3: Build everything**

From repo root: `npm run build`
Expected: PASS. `packages/ui/dist` regenerated, all docs/marketing/payments/support sites build.

- [ ] **Step 4: Docs site smoke matrix**

Start `cd websites/apps/docs && npm run dev` (port 3001). For each viewport in `[375, 600, 768, 1023, 1024, 1280]`, verify on `http://localhost:3001/guides/smart-search`:

| Viewport | Hamburger visible | Drawer opens | Desktop sidebar | Right-rail TOC |
|---|---|---|---|---|
| 375 | yes | yes | hidden | hidden |
| 600 | yes | yes | hidden | hidden |
| 768 | yes | yes | hidden | hidden |
| 1023 | yes | yes | hidden | hidden |
| 1024 | no | n/a | visible | hidden |
| 1280 | no | n/a | visible | only if `tocItems` passed |

Also verify in the open drawer: search autofocuses; tap-link closes the drawer and navigates; tap-scrim closes; Esc closes; "Smart Search" is highlighted in the tree; site-link strip is pinned to the bottom and visible regardless of how far the tree is scrolled.

Resize from 800px → 1100px while drawer is open: drawer auto-closes, body scroll unlocks (verified by scrolling the page works after auto-close).

- [ ] **Step 5: Cross-app sanity**

For each of `marketing`, `payments`, `support`:

```bash
cd websites/apps/<app> && npm run dev
```

At <768px width, tap the hamburger. Confirm the **default** behavior: top-anchored dropdown with the four site links, no off-canvas drawer chrome. This proves `mobileMenuContent === undefined` is byte-identical to the pre-change behavior.

(New: Esc-to-close also works on these apps — that is an intentional improvement, not a regression.)

- [ ] **Step 6: Concept-page exception**

On the docs site, open `http://localhost:3001/concepts/indexing` (or any `/concepts/*` route). The `ClientLayout` `useFullWidth` branch handles these — no `DocsLayout`. Confirm at mobile width: hamburger appears (`md:hidden` default since this branch passes a plain `SiteHeader` without `mobileBreakpoint='lg'`), tapping it shows the default site-link dropdown, **not** the docs drawer. Concept pages have no docs sidebar to surface — this is correct.

- [ ] **Step 7: Tag the work as complete**

No commit needed for this task — it's verification only. Report completion to the user, listing the commits from Tasks 1–7.

---

## Self-Review

**Spec coverage:**
- Goal 1 (restore mobile sidebar) → Tasks 5–6 ✓
- Goal 2 (site links reachable but secondary) → Task 5 (sticky bottom strip) ✓
- Goal 3 (match dev-docs site patterns) → Task 5 (off-canvas left drawer with scrim) ✓
- Goal 4 (re-use existing components) → Tasks 1, 5 (DocsSidebarNav reused) ✓
- Goal 5 (no breaking changes for non-docs apps) → Task 4 (additive props), Task 8 Step 5 (cross-app sanity) ✓
- Section 1 (component boundaries / `currentPath` plumbing) → Tasks 2–3 ✓
- Section 2 (drawer anatomy: search top, tree mid, site-strip bottom) → Task 5 ✓
- Section 3 (drawer behavior: open/close/Esc/auto-close on link/matchMedia cleanup) → Tasks 1, 4, 5 ✓
- Section 4 (right-rail TOC mobile/tablet handling) → Task 7 ✓
- Section 5 (concept-page exception) → Task 8 Step 6 ✓
- Section 6 (drawer markup sketch) → Task 5 ✓
- Section 7 (auto-close-on-navigate via `onLinkClick`) → Tasks 1, 5 ✓

No spec section is uncovered.

**Placeholder scan:** No "TBD", "TODO", or "implement appropriately" — every step has concrete code or commands. The one conditional ("if `tailwindcss-animate` is not in the plugin list, use the keyframe fallback") is a fully-specified branch with both paths written out, not a placeholder.

**Type consistency:** `MobileDocsDrawerProps`, `onClose`, `onLinkClick`, `currentPath`, `withActive`, `mobileMenuContent`, `mobileBreakpoint`, `close()` — all names used consistently across tasks. `DocNode` import path is consistent. `NavLink` re-imported from `SiteHeader` is consistent with where it's defined.

---

## Files Created / Modified Summary

| File | Tasks |
|---|---|
| `packages/ui/src/components/docs/DocsSidebarNav.tsx` | 1 |
| `packages/ui/src/components/docs/DocsLayout.tsx` | 2, 6, 7 |
| `packages/ui/src/components/docs/MobileDocsDrawer.tsx` (new) | 5 |
| `packages/ui/src/components/docs/index.ts` | 5 |
| `packages/ui/src/components/site/SiteHeader.tsx` | 4 |
| `packages/ui/src/stories/docs/MobileDocsDrawer.stories.tsx` (new) | 5 |
| `websites/apps/docs/src/app/ClientLayout.tsx` | 3 |

7 commits, all on `@prep/ui` and the docs app, no breaking changes for non-docs consumers.
