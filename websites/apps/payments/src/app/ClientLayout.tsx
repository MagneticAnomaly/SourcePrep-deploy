"use client";

import type { ReactNode } from 'react';
import { SiteHeader, SiteFooter } from '@prep/ui';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://sourceprep.io';
const PRICING_URL = isDev ? 'http://localhost:3000/pricing' : 'https://sourceprep.io/pricing';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.sourceprep.io';

const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Pricing', href: PRICING_URL },
  { label: 'Support', href: SUPPORT_URL },
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
