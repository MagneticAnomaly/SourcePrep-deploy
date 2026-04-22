"use client";

import type { ReactNode } from 'react';
import { DocsLayout } from '@prep/ui';
import { docsSidebar } from '../config/docs';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://sourceprep.io';
const DOWNLOAD_URL = isDev ? 'http://localhost:3000/download' : 'https://sourceprep.io/download';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.sourceprep.io';

const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Documentation', href: '/' },
  { label: 'Download', href: DOWNLOAD_URL },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      headerProps={{
        productName: 'SourcePrep Docs',
        logo: <img src="/prep-logo.png" alt="SourcePrep" style={{ width: '3rem', height: '3rem' }} className="rounded" />,
        links: navLinks,
        searchPlaceholder: 'Search documentation...',
        onSearch: (query: string) => {
          window.location.href = `/search?q=${encodeURIComponent(query)}`;
        },
      }}
      footerProps={{
        productName: 'SourcePrep',
        socials: {
          twitter: 'https://x.com/Prep_io',
          github: 'https://github.com/MagneticAnomaly/SourcePrep-MCP',
          email: 'docs@sourceprep.io',
        },
      }}
      sidebarItems={docsSidebar}
    >
      {children}
    </DocsLayout>
  );
}
