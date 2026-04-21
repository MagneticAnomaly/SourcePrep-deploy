"use client";

import type { ReactNode } from 'react';
import { SiteHeader, SiteFooter } from '@prep/ui';
import { DevToolbar } from './DevToolbar';

const isDev = process.env.NODE_ENV !== 'production';

// Dev mode: point to local dev servers instead of production domains
const DOCS_URL  = isDev ? 'http://localhost:3001' : 'https://docs.runprep.io';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.runprep.io';
// const PAYMENTS_URL = isDev ? 'http://localhost:3003' : 'https://payments.runprep.io';

const navLinks = [
  { label: 'Download', href: '/download' },
  { label: 'Docs', href: DOCS_URL },
  { label: 'Pricing', href: '/pricing' },
  { label: 'FAQ', href: '/faq' },
];

const footerSections = [
  {
    title: 'Product',
    links: [
      { label: 'Download', href: '/download' },
      { label: 'Pricing', href: '/pricing' },
      { label: 'Changelog', href: '/changelog' },
      { label: 'Documentation', href: DOCS_URL },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'FAQ', href: '/faq' },
      { label: 'Research', href: '/research' },
      { label: 'Support', href: SUPPORT_URL },
    ],
  },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader 
        productName="RunPrep" 
        productBadge=""
        logo={<img src="/prep-logo.png" alt="RunPrep" style={{ width: '3rem', height: '3rem' }} className="rounded" />}
        links={navLinks} 
        actions={
          <a 
            href="/download" 
            className="px-4 py-2 bg-primary text-background rounded-md text-sm font-medium hover:bg-primary-hover transition-colors shadow-sm"
          >
            Get Started
          </a>
        }
        onSearch={(query: string) => {
          window.location.href = `${DOCS_URL}/search?q=${encodeURIComponent(query)}`;
        }}
      />
      <main className="flex-1">
        {children}
      </main>
      <SiteFooter 
        productName="RunPrep"
        logo={<img src="/prep-logo.png" alt="RunPrep" style={{ width: '2.5rem', height: '2.5rem' }} className="rounded" />}
        sections={footerSections}
        socials={{
          twitter: 'https://x.com/Prep_io',
          github: 'https://github.com/MagneticAnomaly/RunPrep-MCP',
          email: 'hello@runprep.io'
        }}
        copyright="© 2026 Magnetic Anomaly llc. All rights reserved."
      />
      <DevToolbar />
    </>
  );
}
