"use client";

import type { ReactNode } from 'react';
import { SiteHeader, SiteFooter } from '@codrag/ui';

const isDev = process.env.NODE_ENV !== 'production';

const HOME_URL = isDev ? 'http://localhost:3000' : 'https://codrag.io';
const PRICING_URL = isDev ? 'http://localhost:3000/pricing' : 'https://codrag.io/pricing';
const SUPPORT_URL = isDev ? 'http://localhost:3002' : 'https://support.codrag.io';

const navLinks = [
  { label: 'Home', href: HOME_URL },
  { label: 'Pricing', href: PRICING_URL },
  { label: 'Support', href: SUPPORT_URL },
];

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader 
        productName="CoDRAG Payments" 
        logo={<img src="/codrag-logo.png" alt="CoDRAG" className="w-6 h-6 rounded" />}
        links={navLinks}
      />
      <main className="flex-1">
        {children}
      </main>
      <SiteFooter 
        productName="CoDRAG"
        socials={{
          twitter: 'https://x.com/CoDRAG_io',
          github: 'https://github.com/MagneticAnomaly/CoDRAG-MCP',
          email: 'support@codrag.io'
        }}
      />
    </>
  );
}
