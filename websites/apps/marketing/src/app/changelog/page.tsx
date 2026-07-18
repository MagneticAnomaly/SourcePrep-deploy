"use client";

import { Button } from '@prep/ui';
import { GITHUB_REPO_URL } from '@/lib/links';
import { IS_BETA_MODE } from '@/lib/beta';

interface ChangelogEntry {
  version: string;
  date: string;
  title: string;
  highlights: string[];
  type: 'major' | 'minor' | 'patch';
}

const CHANGELOG: ChangelogEntry[] = [
  {
    version: '0.9.0-beta',
    date: 'Planned',
    title: 'Public Beta & Open-Source Launch',
    type: 'minor',
    highlights: [
      'Full SourcePrep source code released under the Apache 2.0 license',
      'Multi-project support with project registry',
      'Context assembly API for LLM prompt construction',
      'Embedded and standalone index modes',
      'CLI commands: serve, add, build, search, mcp',
      'Dashboard UI with panel-based layout',
    ],
  },
  {
    version: '0.5.0-alpha',
    date: 'In progress',
    title: 'Alpha Preview',
    type: 'minor',
    highlights: [
      'Core indexing engine with tree-sitter parsing',
      'Structural Code Graph — maps imports, calls, and symbol hierarchies',
      'Semantic code search with built-in ONNX embeddings',
      'Initial MCP integration for Cursor and Windsurf',
      'Real-time file watcher with incremental rebuild',
      'macOS and Windows support (Tauri desktop app)',
    ],
  },
  {
    version: '0.1.0-dev',
    date: 'Jan 2026',
    title: 'Internal Development',
    type: 'patch',
    highlights: [
      'Proof of concept for Rust-based trace indexing',
      'Initial UI design and component library setup',
      'Established MCP bridging capability',
    ],
  },
];

function typeBadgeColor(type: ChangelogEntry['type']) {
  switch (type) {
    case 'major': return 'bg-primary text-background border-border shadow-sm';
    case 'minor': return 'bg-warning/20 text-text border-warning/50';
    case 'patch': return 'bg-surface-raised text-text border-border-subtle';
  }
}

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text selection:bg-primary/20">
      <div className="mx-auto max-w-5xl px-6 py-24">

        {/* Nav Back */}
        <div className="mb-12">
          <a href="/" className="inline-flex items-center gap-2 text-sm font-medium text-text-muted hover:text-primary transition-colors">
            ← Return to Overview
          </a>
        </div>

        {/* Header */}
        <div className="mb-20">
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-text mb-6">
            Changelog
          </h1>
          <p className="text-xl text-text-muted max-w-2xl leading-relaxed">
            New updates and improvements to SourcePrep.
          </p>
        </div>

        {/* Timeline */}
        <div className="relative border-l border-border-subtle ml-4 md:ml-8 pl-8 md:pl-12 space-y-24 py-4">
          {CHANGELOG.map((entry) => (
            <article key={entry.version} className="relative group">
              {/* Node Marker */}
              <div className="absolute -left-[37px] md:-left-[53px] top-1.5 w-3 h-3 rounded-full bg-surface border-2 border-primary group-hover:bg-primary transition-colors"></div>

              {/* Content */}
              <div className="bg-surface border border-border rounded-xl p-8 shadow-sm transition-all hover:shadow-md">
                {/* Version Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-border-subtle">
                  <div className="flex items-center gap-4">
                    <h2 className="text-3xl font-bold text-text">
                      v{entry.version}
                    </h2>
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-md border ${typeBadgeColor(entry.type)} uppercase tracking-wider`}>
                      {entry.type}
                    </span>
                  </div>
                  <span className="text-sm font-mono text-text-subtle bg-surface-raised px-3 py-1.5 rounded-md border border-border-subtle">
                    {entry.date}
                  </span>
                </div>

                <h3 className="text-xl font-semibold text-text mb-6">
                  {entry.title}
                </h3>
                
                <ul className="space-y-4">
                  {entry.highlights.map((item, i) => (
                    <li key={i} className="flex items-start gap-3 text-text-muted">
                      <span className="text-primary mt-1 flex-shrink-0">•</span>
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>

        {/* Footer Actions */}
        <div className="mt-32 pt-12 border-t border-border flex flex-col sm:flex-row gap-4 justify-center">
          {IS_BETA_MODE ? (
            <Button size="lg" className="shadow-sm" asChild>
              <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request">Request Beta Access</a>
            </Button>
          ) : (
            <Button size="lg" className="shadow-sm" asChild>
              <a href={`${GITHUB_REPO_URL}/releases`}>Download Latest Build</a>
            </Button>
          )}
          <Button size="lg" variant="outline" asChild>
            <a href="https://docs.sourceprep.io">Read Documentation</a>
          </Button>
        </div>

      </div>
    </main>
  );
}
