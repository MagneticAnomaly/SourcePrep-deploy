"use client";

import { Button } from '@codrag/ui';
import { CreditCard, RefreshCw, Mail, HelpCircle, Repeat, Infinity, Users } from 'lucide-react';

const CHECKOUT_MONTHLY  = process.env.NEXT_PUBLIC_LS_CHECKOUT_MONTHLY  ?? '';
const CHECKOUT_PERPETUAL = process.env.NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL ?? '';
const CHECKOUT_TEAM     = process.env.NEXT_PUBLIC_LS_CHECKOUT_TEAM      ?? '';

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

        {/* Product checkout cards */}
        <div className="grid gap-6 sm:grid-cols-3 max-w-4xl mx-auto">
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center">
            <Repeat className="w-8 h-8 text-primary mb-3" />
            <h2 className="text-lg font-semibold">Monthly</h2>
            <p className="mt-1 text-sm text-text-muted">$7/mo — full features, cancel anytime.</p>
            <Button asChild variant="outline" className="mt-4 w-full">
              <a href={CHECKOUT_MONTHLY || 'https://codrag.io/pricing'}>
                {CHECKOUT_MONTHLY ? 'Subscribe' : 'View Pricing'}
              </a>
            </Button>
          </div>

          <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-primary/5 to-transparent p-6 flex flex-col items-center text-center relative">
            <div className="absolute -top-3 right-4 bg-primary text-background text-xs font-bold px-3 py-1 rounded-full">
              Best Value
            </div>
            <Infinity className="w-8 h-8 text-primary mb-3" />
            <h2 className="text-lg font-semibold">Perpetual</h2>
            <p className="mt-1 text-sm text-text-muted">$79 once — yours forever.</p>
            <Button asChild className="mt-4 w-full">
              <a href={CHECKOUT_PERPETUAL || 'https://codrag.io/pricing'}>
                {CHECKOUT_PERPETUAL ? 'Buy Now' : 'View Pricing'}
              </a>
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center">
            <Users className="w-8 h-8 text-primary mb-3" />
            <h2 className="text-lg font-semibold">Team</h2>
            <p className="mt-1 text-sm text-text-muted">$15/seat/mo — shared config + management.</p>
            <Button asChild variant="outline" className="mt-4 w-full">
              <a href={CHECKOUT_TEAM || 'https://codrag.io/pricing'}>
                {CHECKOUT_TEAM ? 'Start Team' : 'View Pricing'}
              </a>
            </Button>
          </div>
        </div>

        {/* Manage + support cards */}
        <div className="mt-12 grid gap-6 sm:grid-cols-3 max-w-4xl mx-auto">
          <a href="/recover" className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center hover:border-primary/50 transition-colors">
            <RefreshCw className="w-6 h-6 text-text-muted mb-2" />
            <h3 className="font-medium">Recover a License</h3>
            <p className="mt-1 text-xs text-text-muted">Lost your key? We'll resend it.</p>
          </a>

          <a href="mailto:support@codrag.io" className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center hover:border-primary/50 transition-colors">
            <Mail className="w-6 h-6 text-text-muted mb-2" />
            <h3 className="font-medium">Licensing Support</h3>
            <p className="mt-1 text-xs text-text-muted">support@codrag.io</p>
          </a>

          <a href="https://support.codrag.io" className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center hover:border-primary/50 transition-colors">
            <HelpCircle className="w-6 h-6 text-text-muted mb-2" />
            <h3 className="font-medium">General Support</h3>
            <p className="mt-1 text-xs text-text-muted">Bugs, questions, troubleshooting.</p>
          </a>
        </div>

        <div className="mt-16 flex justify-center gap-4">
          <Button asChild variant="outline">
            <a href="https://codrag.io/pricing">View Full Pricing</a>
          </Button>
          <Button asChild variant="outline">
            <a href="https://docs.codrag.io">Documentation</a>
          </Button>
        </div>
      </div>
    </main>
  );
}
