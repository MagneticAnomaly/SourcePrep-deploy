"use client";

import { Button } from '@prep/ui';
import { RefreshCw, Mail, HelpCircle, Zap, Users } from 'lucide-react';

const CHECKOUT_PRO  = process.env.NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL ?? '';
const CHECKOUT_TEAM = process.env.NEXT_PUBLIC_LS_CHECKOUT_TEAM      ?? '';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold tracking-tight mb-4">Payments &amp; Licensing</h1>
          <p className="text-xl text-text-muted max-w-2xl mx-auto">
            Purchase a SourcePrep license, manage your subscription, or recover an existing key.
            All licenses are verified offline after a single activation — no recurring phone-home.
          </p>
        </div>

        {/* Product checkout cards */}
        <div className="grid gap-6 sm:grid-cols-2 max-w-3xl mx-auto">
          <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-primary/5 to-transparent p-6 flex flex-col items-center text-center relative">
            <Zap className="w-8 h-8 text-primary mb-3" />
            <h2 className="text-lg font-semibold">Pro</h2>
            <p className="mt-1 text-sm text-text-muted">$79 one-time or $7/mo. Unlimited projects, all features.</p>
            <Button asChild className="mt-4 w-full">
              <a href={CHECKOUT_PRO || 'https://sourceprep.io/pricing'}>
                {CHECKOUT_PRO ? 'Get Pro' : 'View Pricing'}
              </a>
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center">
            <Users className="w-8 h-8 text-primary mb-3" />
            <h2 className="text-lg font-semibold">Team</h2>
            <p className="mt-1 text-sm text-text-muted">$15/seat/mo. Shared config + centralized management.</p>
            <Button asChild variant="outline" className="mt-4 w-full">
              <a href={CHECKOUT_TEAM || 'https://sourceprep.io/pricing'}>
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

          <a href="mailto:support@sourceprep.io" className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center hover:border-primary/50 transition-colors">
            <Mail className="w-6 h-6 text-text-muted mb-2" />
            <h3 className="font-medium">Licensing Support</h3>
            <p className="mt-1 text-xs text-text-muted">support@sourceprep.io</p>
          </a>

          <a href="https://support.sourceprep.io" className="rounded-xl border border-border bg-surface p-6 flex flex-col items-center text-center hover:border-primary/50 transition-colors">
            <HelpCircle className="w-6 h-6 text-text-muted mb-2" />
            <h3 className="font-medium">General Support</h3>
            <p className="mt-1 text-xs text-text-muted">Bugs, questions, troubleshooting.</p>
          </a>
        </div>

        <div className="mt-16 flex justify-center gap-4">
          <Button asChild variant="outline">
            <a href="https://sourceprep.io/pricing">View Full Pricing</a>
          </Button>
          <Button asChild variant="outline">
            <a href="https://docs.sourceprep.io">Documentation</a>
          </Button>
        </div>
      </div>
    </main>
  );
}
