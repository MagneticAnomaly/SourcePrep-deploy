"use client";

import { Button } from '../../primitives/Button';
import { LayoutGrid, Lock } from 'lucide-react';

export function EnterpriseHero({ isBetaMode }: { isBetaMode: boolean }) {
  return (
    <div className="bg-surface-raised min-h-[600px] border-b border-border">
      {/* Top Bar */}
      <div className="bg-background border-b border-border px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <span className="font-mono font-bold text-lg tracking-tight flex items-center gap-2"><LayoutGrid className="w-5 h-5" /> CoDRAG</span>
          <span className="px-2 py-0.5 bg-surface-raised border border-border text-xs text-text-subtle uppercase">Enterprise</span>
        </div>
        <div className="flex gap-4 text-sm font-medium text-text-muted">
          <span>Overview</span>
          <span>Deployments</span>
          <span>Security</span>
          <span className="text-primary">Docs</span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-12 grid grid-cols-12 gap-8">
        {/* Left: Content */}
        <div className="col-span-12 md:col-span-5 flex flex-col justify-center">
          <div className="mb-6">
            <span className="text-primary font-mono text-sm font-semibold mb-2 block">PLATFORM_V1.0</span>
            <h1 className="text-4xl md:text-5xl font-sans font-semibold text-text leading-tight mb-4">
              Give every engineer AI that understands your codebase.
            </h1>
            <p className="text-text-muted text-lg leading-relaxed">
              CoDRAG Enterprise standardizes Rust-powered semantic + structural indexing across your
              organization. Shared context layers accelerate onboarding, improve AI output
              quality, and keep all code on-premise.
            </p>
          </div>

          <div className="space-y-4 mb-8">
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-primary shadow-sm">
              <span className="text-primary font-bold">01</span>
              <span className="font-medium text-text">Air-Gapped Deployment & Governance</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">02</span>
              <span className="font-medium text-text">Shared Context Across Teams</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-background border border-border border-l-4 border-l-border shadow-sm opacity-70">
              <span className="text-text-subtle font-bold">03</span>
              <span className="font-medium text-text">SSO, SCIM & Audit Logging</span>
            </div>
          </div>


          <div className="pt-8">
            {isBetaMode ? (
              <Button size="lg" className="w-fit shadow-sm" asChild>
                <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Enterprise">Contact Sales for Beta</a>
              </Button>
            ) : (
              <Button size="lg" className="w-fit shadow-sm" asChild>
                <a href="/contact">Contact Sales</a>
              </Button>
            )}
          </div>
        </div>

        {/* Right: Dashboard Preview */}
        <div className="col-span-12 md:col-span-7">
          <div className="bg-background border border-border shadow-md rounded-sm overflow-hidden h-full flex flex-col">
            <div className="bg-surface-raised border-b border-border p-3 flex justify-between items-center">
              <span className="font-mono text-xs text-text-muted flex items-center gap-2"><Lock className="w-3 h-3" /> admin_console</span>
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-border"></div>
                <div className="w-3 h-3 rounded-full bg-border"></div>
              </div>
            </div>
            <div className="p-6 grid grid-cols-2 gap-4 flex-1">
              <div className="bg-surface-raised border border-border rounded h-32"></div>
              <div className="bg-surface-raised border border-border rounded h-32"></div>
              <div className="col-span-2 bg-surface-raised border border-border rounded h-48"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
