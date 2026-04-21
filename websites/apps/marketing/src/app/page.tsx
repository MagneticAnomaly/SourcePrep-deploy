"use client";

import { useState } from 'react';
import { MarketingHero, FeatureBlocks, prepFeatures, marketingFeatures, AnimatedCLI, AnimatedIDE, prepOverviewDemo, prepSearchDemo, prepImpactDemo, prepAuditDemo, prepObserveDemo, prepConceptsDemo, ideDemoScript } from '@prep/ui';
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
          <h2>What is RunPrep?</h2>
          <p>
            RunPrep is a structural codebase intelligence MCP server for AI coding agents.
            It builds a code graph using Rust and tree-sitter to map imports, call chains, and symbol hierarchies — then delivers that deep structural context directly to Claude Code, Antigravity, Cursor, VS Code, and any MCP-compatible tool.
            Connect your preferred LLM — Ollama Kimi2.5, local models, or frontier APIs.
          </p>
        </section>

        {/* Why RunPrep + Capabilities (merged) */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Why developers need this</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              If you use AI to write code, you need RunPrep
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              AI assistants are only as good as the context they receive. RunPrep makes sure they get the right context, every time — delivering <strong className="text-text font-semibold">3–20× more signal per token</strong> than dumping whole files into the prompt.
            </p>
          </div>
          <FeatureBlocks features={marketingFeatures} variant="list" />

          {/* Capabilities grid + YouTube inline */}
          <div className="mt-20">
            <div className="text-center mb-12">
              <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Capabilities</p>
              <h2 className="text-2xl font-medium tracking-tight text-text sm:text-3xl">
                Built for large codebases and sprawling doc trees
              </h2>
            </div>

            <FeatureBlocks features={prepFeatures.filter((_: any, i: number) => [0, 1, 2, 3, 4, 7, 10, 11, 12].includes(i))} variant="cards" />

            {/* Deep-dive pages */}
            <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                { href: '/claude-code', title: 'Claude Code', desc: 'Our deepest integration' },
                { href: '/paperclip', title: 'Paperclip', desc: 'Agent orchestration' },
                { href: '/graph-enrichment', title: 'Graph Enrichment', desc: 'Multi-stage pipeline' },
                { href: '/immune-system', title: 'Immune System', desc: 'Architectural guardrails' },
                { href: '/integrations', title: 'IDE Ecosystem', desc: 'One server, every editor' },
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
            </div>

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
                  title="RunPrep Demo Video"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  referrerPolicy="strict-origin-when-cross-origin"
                  allowFullScreen
                />
              </div>
            </div>
          </div>
        </section>

        {/* Live Demos — tabbed showcase replacing static tool cards */}
        <section className="rounded-2xl border border-border bg-surface p-6 md:p-10">
          <div className="text-center mb-10">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">See The Tools</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Six MCP tools. Deep codebase intelligence.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Connect RunPrep once to Claude Code, Antigravity, Cursor, or any MCP-compatible editor — and your AI gets structural awareness, semantic search, blast radius analysis, audit enrichment, persistent memory, and recorded design rationale.
            </p>
          </div>

          {/* Tab bar */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            {DEMO_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveDemo(tab.key)}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${
                  activeDemo === tab.key
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
              <AnimatedCLI script={prepOverviewDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'search' && (
              <AnimatedCLI script={prepSearchDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'impact' && (
              <AnimatedCLI script={prepImpactDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'audit' && (
              <AnimatedCLI script={prepAuditDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'observe' && (
              <AnimatedCLI script={prepObserveDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'concepts' && (
              <AnimatedCLI script={prepConceptsDemo} theme="dark" className="w-full" />
            )}
            {activeDemo === 'ide' && (
              <AnimatedIDE script={ideDemoScript} className="w-full" />
            )}
          </div>

          {/* Quick setup */}
          <div className="max-w-2xl mx-auto mt-10">
            <div className="rounded-xl border border-border bg-background p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">&#x2713;</div>
                <h3 className="font-mono font-medium text-sm text-text">Connect instantly via MCP</h3>
              </div>
              <div className="font-mono text-sm space-y-3">
                <div className="bg-surface p-2 rounded border border-border-subtle text-success text-xs">
                  $ prep serve
                </div>
                <div className="bg-surface p-2 rounded border border-border-subtle text-text-subtle text-xs">
                  <span className="text-text-muted">{`// Add to your editor's MCP config:`}</span><br/>
                  {`"prep": { "command": "prep", "args": ["mcp"] }`}
                </div>
              </div>
            </div>
            <div className="text-center mt-6">
              <a href="https://docs.runprep.io/mcp" className="text-sm text-primary hover:underline">
                View full integration guides for Claude Code, Antigravity, Cursor, and more →
              </a>
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
              <div className="text-3xl font-bold text-primary">3&ndash;20&times;</div>
              <div className="text-sm text-text-muted mt-1">More signal per token</div>
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
              <div className="text-sm text-text-muted mt-1">Ollama Kimi2.5, local models, or frontier APIs. Swarm mode for parallel enrichment.</div>
            </div>
          </div>
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            {IS_BETA_MODE ? (
              <a
                href="mailto:support@runprep.io?subject=RunPrep%20Beta%20Access%20Request"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Request Beta Access <ArrowRight className="w-4 h-4" />
              </a>
            ) : (
              <a
                href="/download"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Get RunPrep <ArrowRight className="w-4 h-4" />
              </a>
            )}
            <Link
              href="/compare"
              className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-semibold text-text hover:bg-surface transition-colors"
            >
              Compare to Alternatives <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
