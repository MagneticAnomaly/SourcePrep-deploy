"use client";

import { FeatureBlocks } from '@codrag/ui';
import { CreditCard, RefreshCw, Mail, HelpCircle } from 'lucide-react';

const CHECKOUT_URL =
  process.env.NEXT_PUBLIC_CODRAG_CHECKOUT_URL ?? 'https://codrag.io';

const paymentOptions = [
  {
    icon: <CreditCard className="w-8 h-8" />,
    title: 'Buy a license',
    description: 'Checkout and receive your license details by email.',
    href: CHECKOUT_URL,
    external: true,
  },
  {
    icon: <RefreshCw className="w-8 h-8" />,
    title: 'Recover a license',
    description: 'Resend license info using your purchase email.',
    href: '/recover',
  },
  {
    icon: <Mail className="w-8 h-8" />,
    title: 'Licensing support',
    description: 'support@codrag.io',
    href: 'mailto:support@codrag.io',
    external: true,
  },
  {
    icon: <HelpCircle className="w-8 h-8" />,
    title: 'General support',
    description: 'Bugs, questions, and troubleshooting.',
    href: 'https://codrag.io/support',
    external: true,
  },
];

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold tracking-tight mb-4">Payments &amp; Licensing</h1>
          <p className="text-xl text-text-muted max-w-2xl mx-auto">
            Purchase a CoDRAG license, manage your subscription, or recover an existing key.
            All licenses are verified offline after a single activation — no recurring phone-home.
          </p>
        </div>

        <FeatureBlocks features={paymentOptions} variant="cards" />

        <div className="mt-16 flex justify-center gap-4">
          <a
            href="https://codrag.io/pricing"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text hover:bg-surface transition-colors"
          >
            View Pricing
          </a>
          <a
            href="https://docs.codrag.io"
            className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text hover:bg-surface transition-colors"
          >
            Documentation
          </a>
        </div>
      </div>
    </main>
  );
}
