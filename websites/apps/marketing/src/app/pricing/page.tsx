"use client";

import { Button } from '@prep/ui';
import { GITHUB_REPO_URL } from "@/lib/links";
import { IS_BETA_MODE } from '@/lib/beta';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors">
          ← Home
        </a>

        <div className="mt-12 text-center max-w-3xl mx-auto">
          {IS_BETA_MODE && (
            <div className="mb-6 inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <span className="relative flex h-2 w-2 mr-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              SourcePrep is currently in closed beta. Prices below indicate our upcoming structure.
            </div>
          )}
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Simple, honest pricing
          </h1>
          <p className="mt-6 text-xl text-text-muted leading-relaxed">
            The full product is free and open source under Apache 2.0. Paid tiers add
            convenience — signed installers, hosted team infrastructure, support — never
            capabilities. Indexing runs locally — your source code never leaves your
            machine unless you connect a cloud model.
          </p>
        </div>

        {/* Pricing grid */}
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {/* Open Source */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Open Source</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-text-muted ml-1">forever</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              The full product. Apache 2.0.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Full engine, daemon, CLI, MCP server, dashboard, and VS Code extension</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Unlimited projects — every capability and prompt ships open source</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Local-first — your code never leaves your machine unless you connect a cloud model</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Install with pip, brew, or build from source</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Community support on GitHub</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              {IS_BETA_MODE ? (
                <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request%20-%20Open%20Source">Request Beta Access</a>
              ) : (
                <a href={GITHUB_REPO_URL}>View on GitHub</a>
              )}
            </Button>
          </div>

          {/* Pro — highlighted */}
          <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-primary/5 to-transparent p-6 flex flex-col relative">
            <div className="absolute -top-3 right-4 bg-primary text-background text-xs font-bold px-3 py-1 rounded-full">
              Coming Soon
            </div>
            <div className="text-sm font-semibold text-primary uppercase tracking-wide">Pro</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$29</span>
              <span className="text-text-muted ml-1">one-time</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Convenience, not capability.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Signed, notarized installers for macOS and Windows</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Automatic updates — 12 months included, the app is yours forever</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Keep updates coming for ~$15/yr after that (optional)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Pay what you want above the $29 floor</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Email support (5-business-day response target)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-text-subtle mt-0.5">&#8594;</span>
                <span className="text-text-muted">Prefer to build from source? That stays free.</span>
              </li>
            </ul>
            <Button asChild className="mt-6 w-full">
              <a href="mailto:support@sourceprep.io?subject=Pro%20notify">Coming soon — get notified</a>
            </Button>
          </div>

          {/* Teams */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Teams</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$10</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">3-seat minimum</div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Coming soon.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>One shared, always-fresh index per repo</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>SSO (Google, Okta, Microsoft Entra)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Role-based access and audit logs</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Priority support channel</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Annual $144/seat/yr (20% off)</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href="mailto:support@sourceprep.io?subject=Teams%20waitlist">Join the waitlist</a>
            </Button>
          </div>

          {/* Enterprise */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Enterprise</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$30</span>
              <span className="text-text-muted ml-1">/ seat / month</span>
              <div className="mt-1 text-xs text-text-muted">Annual billing, 10-seat minimum</div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Coming soon.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>Everything in Teams</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Air-gapped deployment</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Named contact + monthly office hours</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Setup assistance available</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href="mailto:support@sourceprep.io?subject=Enterprise">Talk to us</a>
            </Button>
          </div>
        </div>

        <p className="mt-8 text-center text-sm text-text-muted">
          Teams syncs embeddings and graph metadata only — never your source code.
        </p>

        <hr className="mt-16 border-border" />

        {/* Trust strip */}
        <div className="mt-16 text-center space-y-4">
          <h2 className="text-xl font-semibold">Every plan includes</h2>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-text-muted">
            <span>Private by Design — your context index is yours to control</span>
            <span>Built-in embeddings — connect to Ollama Cloud or frontier cloud APIs for advanced reasoning</span>
            <span>macOS &amp; Windows (Linux planned)</span>
            <span>MCP integration</span>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Button asChild variant="outline">
            <a href="/security">Security &amp; Privacy</a>
          </Button>
          <Button asChild variant="outline">
            <a href="/contact">Contact</a>
          </Button>
        </div>

        <p className="mt-8 text-center text-xs text-text-muted max-w-lg mx-auto">
          All prices in USD.
        </p>
      </div>
    </main>
  );
}
