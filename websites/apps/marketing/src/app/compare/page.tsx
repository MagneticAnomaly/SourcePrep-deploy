"use client";

import { CompetitorMatrix } from '@codrag/ui';
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
      </div>
    </main>
  );
}
