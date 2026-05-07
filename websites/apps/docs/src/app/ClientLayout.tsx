"use client";

import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { DocsLayout, SiteHeader, SiteFooter } from '@prep/ui';
import { docsSidebar } from '../config/docs';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://sourceprep.io';
const DOWNLOAD_URL = isDev ? 'http://localhost:3000/download' : 'https://sourceprep.io/download';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.sourceprep.io';

// Canonical nav order across all sites: Home · Docs · Pricing · Download · FAQ
// (current-site item omitted; "Docs" omitted here since we are docs).
// See docs/MARKETING_NAV_CANONICAL.md.
const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Pricing', href: `${HOME_URL}/pricing` },
  { label: 'Download', href: DOWNLOAD_URL },
  { label: 'FAQ', href: `${HOME_URL}/faq` },
];

const headerProps = {
  productName: 'SourcePrep Docs',
  logo: <img src="/prep-logo.png" alt="SourcePrep" style={{ width: '3rem', height: '3rem' }} className="rounded" />,
  links: navLinks,
  searchPlaceholder: 'Search documentation...',
  onSearch: (query: string) => {
    window.location.href = `/search?q=${encodeURIComponent(query)}`;
  },
};

const footerProps = {
  productName: 'SourcePrep',
  socials: {
    twitter: 'https://x.com/Prep_io',
    github: 'https://github.com/MagneticAnomaly/SourcePrep-MCP',
    email: 'docs@sourceprep.io',
  },
};

export function ClientLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // Concept pages are designed full-width with their own internal section nav
  // (see components/ConceptPageShell). They do not use the docs left sidebar.
  const useFullWidth = pathname?.startsWith('/concepts/') ?? false;

  if (useFullWidth) {
    return (
      <div className="flex flex-col min-h-screen bg-background text-text">
        <SiteHeader
          {...headerProps}
          className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
        />
        <main className="flex-1">{children}</main>
        <SiteFooter {...footerProps} className="border-t mt-auto" />
      </div>
    );
  }

  return (
    <DocsLayout
      headerProps={headerProps}
      footerProps={footerProps}
      sidebarItems={docsSidebar}
    >
      {children}
    </DocsLayout>
  );
}
