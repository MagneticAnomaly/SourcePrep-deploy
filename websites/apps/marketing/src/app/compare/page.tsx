"use client";

import { CompetitorMatrix } from '@prep/ui';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function ComparePage() {
  return (
    <main className="min-h-screen bg-background text-text py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to home
          </Link>
        </div>
        
        <div className="text-center mb-12">
          <h1 className="text-3xl font-medium tracking-tight text-text sm:text-4xl mb-4">
            Detailed Comparison
          </h1>
          <p className="text-lg text-text-muted max-w-2xl mx-auto">
            A comprehensive breakdown of how CoDRAG's architecture compares to other AI coding tools and context engines.
          </p>
        </div>

        <CompetitorMatrix mobileVariant="detailed" />

        <aside className="mt-16 rounded-2xl border border-border bg-surface p-6 max-w-3xl mx-auto text-center">
          <p className="text-[11px] font-mono font-semibold uppercase tracking-widest text-primary mb-2">
            Bibliography
          </p>
          <p className="text-text-muted leading-relaxed mb-3">
            We&rsquo;ve actually read the papers and source for every tool on this page. Here&rsquo;s the working list.
          </p>
          <a
            href="/research"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            See our research →
          </a>
        </aside>
      </div>
    </main>
  );
}
