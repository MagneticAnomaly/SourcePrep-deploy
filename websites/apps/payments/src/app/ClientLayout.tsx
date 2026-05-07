"use client";

import type { ReactNode } from 'react';
import { SiteHeader, SiteFooter } from '@prep/ui';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://sourceprep.io';
const DOCS_URL = isDev ? 'http://localhost:3001' : 'https://docs.sourceprep.io';
const PRICING_URL = `${HOME_URL}/pricing`;
const DOWNLOAD_URL = `${HOME_URL}/download`;
const FAQ_URL = `${HOME_URL}/faq`;

// Canonical nav order across all sites: Home · Docs · Pricing · Download · FAQ
// (current-site item omitted). See docs/MARKETING_NAV_CANONICAL.md.
const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Docs', href: DOCS_URL },
  { label: 'Pricing', href: PRICING_URL },
  { label: 'Download', href: DOWNLOAD_URL },
  { label: 'FAQ', href: FAQ_URL },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader 
        productName="SourcePrep Payments" 
        logo={<img src="/prep-logo.png" alt="SourcePrep" className="w-6 h-6 rounded" />}
        links={navLinks}
      />
      <main className="flex-1">
        {children}
      </main>
      <SiteFooter 
        productName="SourcePrep"
        socials={{
          twitter: 'https://x.com/Prep_io',
          github: 'https://github.com/MagneticAnomaly/SourcePrep-MCP',
          email: 'support@sourceprep.io'
        }}
      />
    </>
  );
}
