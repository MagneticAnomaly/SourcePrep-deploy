"use client";

import type { ReactNode } from 'react';
import { DocsLayout } from '@prep/ui';
import { docsSidebar } from '../config/docs';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://codrag.io';
const DOWNLOAD_URL = isDev ? 'http://localhost:3000/download' : 'https://codrag.io/download';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.codrag.io';

const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Documentation', href: '/' },
  { label: 'Download', href: DOWNLOAD_URL },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      headerProps={{
        productName: 'CoDRAG Docs',
        logo: <img src="/codrag-logo.png" alt="CoDRAG" style={{ width: '3rem', height: '3rem' }} className="rounded" />,
        links: navLinks,
        searchPlaceholder: 'Search documentation...',
        onSearch: (query: string) => {
          window.location.href = `/search?q=${encodeURIComponent(query)}`;
        },
      }}
      footerProps={{
        productName: 'CoDRAG',
        socials: {
          twitter: 'https://x.com/CoDRAG_io',
          github: 'https://github.com/MagneticAnomaly/CoDRAG-MCP',
          email: 'docs@codrag.io',
        },
      }}
      sidebarItems={docsSidebar}
    >
      {children}
    </DocsLayout>
  );
}
