"use client";

import { useState } from 'react';
import { MCP_TOOLS, mcpConfigAsString } from '@prep/ui';
import { GITHUB_REPO_URL } from '../../lib/links';
import { IS_BETA_MODE } from '@/lib/beta';

const RELEASES_URL = `${GITHUB_REPO_URL}/releases`;

function MCPConfigs() {
  const [active, setActive] = useState(0);
  const tool = MCP_TOOLS[active];
  return (
    <div className="bg-background border border-border rounded-xl overflow-hidden">
      <div className="flex flex-wrap border-b border-border">
        {MCP_TOOLS.map((t, i) => (
          <button
            key={t.id}
            onClick={() => setActive(i)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              i === active
                ? 'bg-primary text-background'
                : 'text-text-muted hover:text-text hover:bg-surface'
            }`}
          >
            {t.name}
          </button>
        ))}
      </div>
      <div className="p-4">
        <div className="text-xs text-text-subtle mb-2 font-mono">{tool.file}</div>
        <pre className="text-sm font-mono text-text-muted whitespace-pre overflow-x-auto">
          {mcpConfigAsString(tool)}
        </pre>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <div className="min-h-screen bg-background text-text font-sans selection:bg-primary/20 border-t-8 border-primary">
      <div className="mx-auto max-w-7xl px-6 py-24">

        <div className="max-w-4xl">
          {IS_BETA_MODE && (
            <div className="mb-10 inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <span className="relative flex h-2 w-2 mr-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              SourcePrep is currently in closed beta &mdash; request access to try it early.
            </div>
          )}
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-text mb-8">
            Download SourcePrep.
          </h1>
          <p className="text-2xl md:text-3xl text-text-muted leading-normal mb-12 max-w-3xl">
            Local-first codebase indexing, trace graphs, and MCP integration &mdash; free and open source, with Private by Design architecture.
          </p>
        </div>

        {/* Install paths */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-24">
          <div className="flex flex-col p-10 rounded-2xl bg-primary text-background shadow-lg">
            <div className="text-lg font-bold uppercase tracking-wider opacity-70 mb-2">Open Source</div>
            <div className="text-4xl font-bold mb-4">Free forever. Apache 2.0.</div>
            <div className="opacity-80 text-lg mb-8">
              The full product &mdash; engine, daemon, CLI, MCP server, dashboard, and VS Code extension. Install with pip or Homebrew, grab a release from GitHub, or build from source.
            </div>
            {IS_BETA_MODE ? (
              <a
                href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request%20-%20Open%20Source"
                className="mt-auto flex items-center font-bold text-xl bg-background text-primary px-8 py-4 rounded-full w-fit hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-background"
              >
                Request Beta Access
              </a>
            ) : (
              <a
                href={RELEASES_URL}
                className="mt-auto flex items-center font-bold text-xl bg-background text-primary px-8 py-4 rounded-full w-fit hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-background"
              >
                Download from GitHub ↓
              </a>
            )}
          </div>

          <div className="flex flex-col p-10 rounded-2xl bg-surface text-text border border-border">
            <div className="text-lg font-bold uppercase tracking-wider text-text-muted mb-2">Pro &mdash; Coming Soon</div>
            <div className="text-4xl font-bold mb-4">Signed installers, auto-update.</div>
            <div className="text-text-muted text-lg mb-8">
              Signed, notarized <code className="font-mono text-base">.dmg</code> (macOS 11+, Apple Silicon) and <code className="font-mono text-base">.msi</code> (Windows 10+, x64) installers from sourceprep.io that keep themselves up to date. $29 one-time &mdash; the same product as open source, packaged for convenience.
            </div>
            <a
              href="mailto:support@sourceprep.io?subject=Pro%20notify"
              className="mt-auto flex items-center font-bold text-xl bg-text text-background px-8 py-4 rounded-full w-fit hover:opacity-80 transition-opacity focus:outline-none focus:ring-2 focus:ring-primary"
            >
              Coming soon &mdash; get notified
            </a>
          </div>
        </div>

        {/* Also available */}
        <div className="flex flex-wrap gap-4 mb-24 text-sm text-text-subtle">
          <span className="px-4 py-2 rounded-full border border-border bg-surface">Open source &mdash; Apache 2.0. No account, no license required.</span>
          <span className="px-4 py-2 rounded-full border border-border bg-surface">macOS &amp; Windows</span>
        </div>

        {/* Quick Start */}
        <div className="bg-surface rounded-2xl p-10 md:p-16 mb-24 border border-border">
          <h2 className="text-3xl font-bold mb-8 text-text">Get Started in 3 Steps</h2>

          <div className="space-y-8">
            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-primary text-background rounded-full flex items-center justify-center text-xl font-bold">1</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Install &amp; start the daemon</div>
                <p className="text-text-muted">
                  Install with <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">pip install prep</code> (or <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">pipx install prep</code>), then run <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">prep serve</code>.{' '}
                  {IS_BETA_MODE ? (
                    <>Full setup details are in the <a href="/setup" className="text-primary hover:underline">setup guide</a>.</>
                  ) : (
                    <>Homebrew and build-from-source instructions are in the <a href={GITHUB_REPO_URL} className="text-primary hover:underline">GitHub README</a>.</>
                  )}
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-center">
              <div className="flex-shrink-0 w-12 h-12 bg-surface-raised border border-border text-text-muted rounded-full flex items-center justify-center text-xl font-bold">2</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Add your project</div>
                <p className="text-text-muted">
                  Run <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">prep add /path/to/repo</code>, then <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">prep build</code> &mdash; or add the project from the dashboard sidebar and start a build.
                </p>
              </div>
            </div>

            <div className="flex flex-col md:flex-row gap-6 md:items-start">
              <div className="flex-shrink-0 w-12 h-12 bg-surface-raised border border-border text-text-muted rounded-full flex items-center justify-center text-xl font-bold">3</div>
              <div className="flex-1">
                <div className="text-xl font-semibold mb-2">Connect your AI editor via MCP</div>
                <p className="text-text-muted mb-4">
                  Add SourcePrep to your editor&apos;s MCP config. Your AI assistant gets structural code intelligence, semantic search, and dependency analysis.
                </p>
                <MCPConfigs />
              </div>
            </div>
          </div>
        </div>

        {/* Verification */}
        <div className="max-w-3xl">
          <h2 className="text-2xl font-bold mb-4">Security &amp; Verification</h2>
          <p className="text-lg text-text-muted leading-relaxed mb-6">
            GitHub releases ship with SHA-256 checksums so you can verify what you downloaded. Pro&apos;s macOS and Windows installers &mdash; coming soon &mdash; add code signing, notarization, and automatic updates.
          </p>
          <div className="flex flex-wrap gap-4">
            <a href="/setup" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Full MCP Setup Guide →
            </a>
            <a href="https://docs.sourceprep.io" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Read Documentation →
            </a>
            <a href="/security" className="text-primary font-bold hover:underline underline-offset-4 text-lg">
              Security Policy →
            </a>
          </div>
        </div>

      </div>
    </div>
  );
}
