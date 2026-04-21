"use client";

import type { ReactNode } from 'react';
import { DocsLayout } from '@prep/ui';
import { docsSidebar } from '../config/docs';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://runprep.io';
const DOWNLOAD_URL = isDev ? 'http://localhost:3000/download' : 'https://runprep.io/download';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.runprep.io';

const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Documentation', href: '/' },
  { label: 'Download', href: DOWNLOAD_URL },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      headerProps={{
        productName: 'Prep Docs',
        logo: <img src="/prep-logo.png" alt="Prep" style={{ width: '3rem', height: '3rem' }} className="rounded" />,
        links: navLinks,
        searchPlaceholder: 'Search documentation...',
        onSearch: (query: string) => {
          window.location.href = `/search?q=${encodeURIComponent(query)}`;
        },
      }}
      footerProps={{
        productName: 'Prep',
        socials: {
          twitter: 'https://x.com/Prep_io',
          github: 'https://github.com/MagneticAnomaly/RunPrep-MCP',
          email: 'docs@runprep.io',
        },
      }}
      sidebarItems={docsSidebar}
    >
      {children}
    </DocsLayout>
  );
}
