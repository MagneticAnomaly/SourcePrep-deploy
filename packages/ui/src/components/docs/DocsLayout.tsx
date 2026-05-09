import { useMemo, type ReactNode } from 'react';
import { cn } from '../../lib/utils';
import { DocsSidebarNav, type DocNode } from './DocsSidebarNav';
import { TableOfContents, type TocItem } from './TableOfContents';
import { SiteHeader, type SiteHeaderProps } from '../site/SiteHeader';
import { SiteFooter, type SiteFooterProps } from '../site/SiteFooter';
import { MobileDocsDrawer } from './MobileDocsDrawer';

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
