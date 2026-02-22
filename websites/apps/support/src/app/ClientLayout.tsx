"use client";

import type { ReactNode } from 'react';
import { SiteHeader, SiteFooter } from '@codrag/ui';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://codrag.io';
const DOCS_URL = isDev ? 'http://localhost:3001' : 'https://docs.codrag.io';

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col min-h-screen bg-background text-text">
      <SiteHeader
        productName="CoDRAG Support"
        logo={<img src="/codrag-logo.png" alt="CoDRAG" className="w-6 h-6 rounded" />}
        links={[
          { label: 'Home', href: HOME_URL },
          { label: 'Docs', href: DOCS_URL },
          { label: 'Status', href: '#' },
        ]}
        searchPlaceholder="Search help..."
        onSearch={(query: string) => {
          window.location.href = `${DOCS_URL}/search?q=${encodeURIComponent(query)}`;
        }}
        className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      />
      <main className="flex-1">
        {children}
      </main>
      <SiteFooter
        productName="CoDRAG"
        socials={{
          twitter: 'https://x.com/CoDRAG_io',
          github: 'https://github.com/MagneticAnomaly/CoDRAG-MCP',
          email: 'support@codrag.io',
        }}
        className="border-t mt-auto"
      />
    </div>
  );
}
