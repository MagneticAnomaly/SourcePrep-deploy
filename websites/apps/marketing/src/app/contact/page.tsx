"use client";

import { Button } from '@codrag/ui';
import { Users, Mail } from 'lucide-react';

const GITHUB_URL =
  process.env.NEXT_PUBLIC_CODRAG_GITHUB_URL ??
  'https://github.com/EricBintner/CoDRAG';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors">
          ← Home
        </a>

        <div className="mt-12 mb-16 text-center max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-6">Get in Touch</h1>
          <p className="text-xl text-text-muted leading-relaxed">
            We are a small, dedicated team building in the open. 
            For the fastest help, join our community. For sensitive matters, send us an email.
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-2 max-w-4xl mx-auto">
          {/* Community Path */}
          <div className="rounded-2xl border border-border bg-surface p-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6 text-primary">
              <Users className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-text mb-4">Community Support</h2>
            <p className="text-text-muted mb-8 leading-relaxed">
              Have a question about usage, setup, or workflows? 
              Our GitHub Discussions board is the best place to get answers from the team and other users.
            </p>
            <Button asChild size="lg" className="w-full sm:w-auto">
              <a href={`${GITHUB_URL}/discussions`} target="_blank" rel="noopener noreferrer">
                Ask the Community
              </a>
            </Button>
            <p className="mt-4 text-xs text-text-muted uppercase tracking-wider font-semibold">
              Recommended for Technical Help
            </p>
          </div>

          {/* Private Path */}
          <div className="rounded-2xl border border-border bg-surface p-10 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center mb-6 text-text">
              <Mail className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-text mb-4">Private Inquiries</h2>
            <p className="text-text-muted mb-8 leading-relaxed">
              For billing issues, licensing questions, enterprise contracts, 
              or security vulnerability reports.
            </p>
            <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
              <a href="mailto:support@codrag.io">
                Email support@codrag.io
              </a>
            </Button>
            <p className="mt-4 text-xs text-text-muted uppercase tracking-wider font-semibold">
              For Account & Business
            </p>
          </div>
        </div>

        {/* Self Service Section */}
        <div className="mt-20 pt-10 border-t border-border text-center">
          <h3 className="text-lg font-semibold mb-6">Looking for something else?</h3>
          <div className="flex flex-wrap justify-center gap-4">
            <Button asChild variant="ghost">
              <a href="https://docs.codrag.io">Read Documentation</a>
            </Button>
            <Button asChild variant="ghost">
              <a href="/pricing">View Pricing</a>
            </Button>
            <Button asChild variant="ghost">
              <a href="/privacy">Privacy Policy</a>
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
