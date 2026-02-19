"use client";

import { Button } from '@codrag/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors">
          ← Home
        </a>

        <div className="mt-12 text-center max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Simple, honest pricing
          </h1>
          <p className="mt-6 text-xl text-text-muted leading-relaxed">
            Local-first means your code stays yours. CoDRAG ships with built-in ONNX embeddings —
            semantic search works out of the box, no LLM required. Add Ollama or a cloud API if you prefer an alternative model. Pay once for Pro and own it forever.
          </p>
        </div>

        {/* Pricing grid */}
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {/* Free */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Free</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-text-muted ml-1">forever</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Try CoDRAG on a single project. See how much better your AI output gets.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>1 active project</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Semantic code search</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Context assembly for LLMs</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>MCP integration (Cursor, Windsurf, etc.)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-text-subtle mt-0.5">&#10005;</span>
                <span className="text-text-muted">Manual indexing only (no file watcher)</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href="/download">Download Free</a>
            </Button>
          </div>

          {/* Starter */}
          <div className="rounded-xl border border-border bg-surface p-6 flex flex-col">
            <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Starter</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$29</span>
              <span className="text-text-muted ml-1">/ 4 months</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              For freelancers and students who work across a few repos.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Up to 3 active projects</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Real-time file watcher (auto-rebuild)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Semantic search + context assembly</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>MCP integration</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Dashboard GUI</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-6 w-full">
              <a href="https://payments.codrag.io">Get Starter</a>
            </Button>
          </div>

          {/* Pro — highlighted */}
          <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-primary/5 to-transparent p-6 flex flex-col relative">
            <div className="absolute -top-3 right-4 bg-primary text-white text-xs font-bold px-3 py-1 rounded-full">
              Most Popular
            </div>
            <div className="text-sm font-semibold text-primary uppercase tracking-wide">Pro</div>
            <div className="mt-3">
              <span className="text-4xl font-bold">$79</span>
              <span className="text-text-muted ml-1">one-time</span>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Perpetual license. Own it forever. The full CoDRAG experience.
            </p>
            <ul className="mt-6 space-y-3 text-sm flex-1">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>Unlimited</strong> projects</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span><strong>Structural Code Graph</strong> (imports, calls, symbol graphs)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Full MCP suite</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Multi-repo agent support</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Real-time auto-rebuild</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Context compression (CLaRa)</span>
              </li>
            </ul>
            <Button asChild className="mt-6 w-full">
              <a href="https://payments.codrag.io">Buy Pro License</a>
            </Button>
          </div>
        </div>

        {/* Team + Enterprise row */}
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Team</div>
              <div>
                <span className="text-2xl font-bold">$15</span>
                <span className="text-text-muted text-sm ml-1">/ seat / month</span>
              </div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Shared configuration, centralized policy, and license management for engineering teams.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Everything in Pro, plus team management</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Centralized configuration & shared context layers</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>License management dashboard</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-4">
              <a href="https://payments.codrag.io">Start Team Trial</a>
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-text-muted uppercase tracking-wide">Enterprise</div>
              <div className="text-2xl font-bold">Custom</div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              For organizations that need air-gapped deployment, SSO/SCIM, audit logging,
              and procurement-ready terms.
            </p>
            <ul className="mt-4 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Everything in Team, plus enterprise controls</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>Air-gapped / on-premise deployment</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success mt-0.5">&#10003;</span>
                <span>SSO, SCIM, and audit logging</span>
              </li>
            </ul>
            <Button asChild variant="outline" className="mt-4">
              <a href="/contact">Contact Sales</a>
            </Button>
          </div>
        </div>

        {/* Trust strip */}
        <div className="mt-16 text-center space-y-4">
          <h2 className="text-xl font-semibold">Every plan includes</h2>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-text-muted">
            <span>100% local — no cloud upload</span>
            <span>No LLM required — built-in embeddings + Ollama &amp; cloud optional</span>
            <span>macOS & Windows</span>
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
      </div>
    </main>
  );
}
