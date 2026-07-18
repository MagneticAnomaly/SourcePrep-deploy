"use client";

import { useState } from 'react';
import { MarketingHero, FeatureBlocks, prepFeatures, marketingFeatures, AnimatedCLI, AnimatedIDE, prepDemos, prepSearchDemos, prepImpactDemos, prepAuditDemos, prepObserveDemos, prepConceptsDemos, ideDemos } from '@prep/ui';
import { ArrowRight, Play } from 'lucide-react';
import Link from 'next/link';
import { DevMarketingHero } from './DevMarketingHero';


const IS_BETA_MODE = true;

const DEMO_TABS = [
  { key: 'overview', label: 'prep', description: 'Instant orientation' },
  { key: 'search', label: 'prep_search', description: 'Semantic search' },
  { key: 'impact', label: 'prep_impact', description: 'Blast radius' },
  { key: 'audit', label: 'prep_audit', description: 'Audit enrichment' },
  { key: 'observe', label: 'prep_observe', description: 'Agent memory' },
  { key: 'concepts', label: 'prep_concepts', description: 'Design rationale' },
  { key: 'ide', label: 'IDE Agent', description: 'Autonomous editing' },
] as const;

type DemoTab = typeof DEMO_TABS[number]['key'];

export default function Page() {
  const showDevToolbar = process.env.NODE_ENV !== 'production';
  const [activeDemo, setActiveDemo] = useState<DemoTab>('overview');

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 space-y-24">
        {/* Hero */}
        {showDevToolbar ? <DevMarketingHero /> : <MarketingHero variant="yale" />}

        {/* SEO — screen-reader only, crawlers only */}
        <section className="sr-only">
          <h2>What is SourcePrep?</h2>
          <p>
            SourcePrep is an open-source structural codebase intelligence MCP server for AI coding agents, released under the Apache 2.0 license.
            It builds a code graph using Rust and tree-sitter to map imports, call chains, and symbol hierarchies — then delivers that deep structural context directly to Claude Code, OpenAI Codex, Cursor, Windsurf, and any other MCP-compatible tool.
            Connect your preferred LLM — local or cloud models via Ollama, or frontier APIs.
          </p>
        </section>

        {/* Why SourcePrep + Capabilities (merged) */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Prep the context before the AI call</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Run prep before grep
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Your AI agent orients itself by opening files and running grep — one guess at a time. SourcePrep is the prep step that hands it a structural map of the codebase up front, so every answer starts from a full picture instead of a keyword match. The payoff: <strong className="text-text font-semibold">up to 20× structural compression</strong> — more signal per token than dumping whole files into the prompt.
            </p>
          </div>
          <FeatureBlocks features={marketingFeatures} variant="list" />
        </section>

        {/* Live Demos — tabbed showcase replacing static tool cards */}
        <section>
          <div className="text-center mb-10">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">See The Tools</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Six MCP tools. Deep codebase intelligence.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Connect SourcePrep once to Claude Code, Codex, Cursor, Windsurf, or any other MCP-compatible tool and your AI gets structural awareness, semantic search, blast radius analysis, audit enrichment, persistent memory, and recorded design rationale.
            </p>
          </div>

          {/* Tab bar */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            {DEMO_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveDemo(tab.key)}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${activeDemo === tab.key
                  ? 'bg-primary text-background font-semibold shadow-md shadow-primary/25'
                  : 'bg-surface-raised border border-border text-text-muted hover:text-text hover:border-primary/40'
                  }`}
              >
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.label.replace('prep_', '')}</span>
                <span className="hidden md:inline text-xs ml-2 opacity-70">— {tab.description}</span>
              </button>
            ))}
          </div>

          {/* Demo display */}
          <div className="max-w-5xl mx-auto">
            {activeDemo === 'overview' && (
              <AnimatedCLI scripts={prepDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'search' && (
              <AnimatedCLI scripts={prepSearchDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'impact' && (
              <AnimatedCLI scripts={prepImpactDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'audit' && (
              <AnimatedCLI scripts={prepAuditDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'observe' && (
              <AnimatedCLI scripts={prepObserveDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'concepts' && (
              <AnimatedCLI scripts={prepConceptsDemos} theme="dark" className="w-full" contentClassName="min-h-[480px]" />
            )}
            {activeDemo === 'ide' && (
              <AnimatedIDE scripts={ideDemos} className="w-full" />
            )}
          </div>


        </section>

        {/* Integrations */}
        <section>
          <div className="text-center mb-10">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Integrations</p>
            <h2 className="text-2xl font-medium tracking-tight text-text sm:text-3xl">
              Works with the editors and agents you already use
            </h2>
            <p className="mt-3 text-base text-text-muted max-w-2xl mx-auto">
              One MCP server, every client. Connect SourcePrep once and any MCP-aware tool picks it up.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {[
              // CLIs first — Claude Code primary, Codex grouped with it
              { href: '/claude-code', name: 'Claude Code', tag: 'Deepest integration', logo: '/logos/claude.svg' },
              { href: '/integrations#openai-codex', name: 'OpenAI Codex', tag: 'Native MCP + AGENTS.md', logo: null },
              { href: '/integrations#gemini-cli', name: 'Gemini CLI', tag: 'MCP-native', logo: '/logos/gemini.svg' },
              // IDEs — Cursor primary
              { href: '/integrations#cursor', name: 'Cursor', tag: 'MCP-native', logo: '/logos/cursor.svg' },
              { href: '/integrations#windsurf', name: 'Windsurf', tag: 'MCP-native', logo: '/logos/windsurf.svg' },
              { href: '/integrations#github-copilot', name: 'VS Code + Copilot', tag: 'MCP via GitHub Copilot', logo: '/logos/vscode.svg' },
              { href: '/paperclip', name: 'Paperclip', tag: 'Agent orchestration', logo: '/logos/paperclip.svg' },
              { href: '/integrations', name: 'See all', tag: 'Full ecosystem', logo: null },
            ].map((item) => (
              <Link
                key={item.href + item.name}
                href={item.href}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 hover:border-primary/40 hover:bg-surface-raised transition-all group"
              >
                {/* Logo slot — drop a square PNG/SVG into public/logos/ */}
                {item.logo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.logo} alt="" className="w-9 h-9 object-contain shrink-0" />
                ) : (
                  <div className="w-9 h-9 rounded-md bg-background border border-border-subtle flex items-center justify-center shrink-0">
                    <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-primary transition-colors" />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-text group-hover:text-primary transition-colors truncate">{item.name}</div>
                  <div className="text-xs text-text-muted truncate">{item.tag}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Capabilities */}
        <section>
          <div className="text-center mb-12">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Capabilities</p>
            <h2 className="text-2xl font-medium tracking-tight text-text sm:text-3xl">
              Built for large codebases and sprawling doc trees
            </h2>
          </div>

          <FeatureBlocks features={prepFeatures.filter((_: any, i: number) => [0, 1, 2, 3, 4, 7, 10, 11, 12].includes(i))} variant="cards" />

          {/* Deep-dive feature pages 
          <div className="mt-12 grid sm:grid-cols-2 gap-3 max-w-3xl mx-auto">
            {[
              { href: '/graph-enrichment', title: 'Graph Enrichment', desc: 'Multi-stage pipeline' },
              { href: '/immune-system', title: 'Immune System', desc: 'Architectural guardrails' },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-3 hover:border-primary/40 hover:bg-surface-raised transition-all group"
              >
                <div>
                  <span className="text-sm font-medium text-text group-hover:text-primary transition-colors">{link.title}</span>
                  <span className="text-xs text-text-muted ml-2">{link.desc}</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-primary transition-colors" />
              </Link>
            ))}
          </div>*/}

          {/* YouTube — compact inline, not a hero panel */}
          <div className="mt-12 max-w-3xl mx-auto">
            <div className="flex items-center gap-2 mb-3">
              <Play className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium text-text-muted">See it in action</span>
            </div>
            <div className="rounded-xl border border-border shadow-lg overflow-hidden aspect-video bg-black">
              <iframe
                className="w-full h-full"
                src="https://www.youtube.com/embed/bjC6DFQ8Zmw?rel=0"
                title="SourcePrep Demo Video"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                referrerPolicy="strict-origin-when-cross-origin"
                allowFullScreen
              />
            </div>
          </div>
        </section>

        {/* Trust strip + CTA */}
        <section className="text-center space-y-8">
          <h2 className="text-2xl font-medium tracking-tight text-text sm:text-3xl">
            Built for professionals who take their code seriously
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-5xl mx-auto">
            <div>
              <div className="text-3xl font-bold text-primary">Up to 20&times;</div>
              <div className="text-sm text-text-muted mt-1">Structural compression &mdash; more signal per token</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">Full Graph</div>
              <div className="text-sm text-text-muted mt-1">Imports, call chains, and symbol hierarchies</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">&lt;100ms</div>
              <div className="text-sm text-text-muted mt-1">Search latency</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">Any LLM</div>
              <div className="text-sm text-text-muted mt-1">Ollama (local or cloud), or frontier APIs</div>
            </div>
          </div>
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            {IS_BETA_MODE ? (
              <a
                href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Request Beta Access <ArrowRight className="w-4 h-4" />
              </a>
            ) : (
              <a
                href="/download"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Get SourcePrep <ArrowRight className="w-4 h-4" />
              </a>
            )}
            <Link
              href="/compare"
              className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-semibold text-text hover:bg-surface transition-colors"
            >
              Compare to Alternatives <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <p className="text-sm text-text-muted">
            Got questions?{' '}
            <Link href="/faq" className="text-primary hover:underline font-medium">
              Read the FAQ →
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
