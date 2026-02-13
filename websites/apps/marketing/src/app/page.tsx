"use client";

import { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures, TierComparison, TechStackMatrix } from '@codrag/ui';
import { Terminal, ArrowRight } from 'lucide-react';
import { DevMarketingHero } from './DevMarketingHero';

export default function Page() {
  const showDevToolbar = process.env.NODE_ENV !== 'production';

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 space-y-24">
        {/* Hero Section */}
        {showDevToolbar ? <DevMarketingHero /> : <MarketingHero variant="yale" />}

        {/* Why CoDRAG — Problem / Solution / Result */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Why developers need this</p>
            <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
              If you use AI to write code, you need CoDRAG
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              AI assistants are only as good as the context they receive. CoDRAG makes sure they get the right context, every time.
            </p>
          </div>
          <FeatureBlocks features={marketingFeatures} variant="list" />
        </section>

        {/* Core Features */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Capabilities</p>
            <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
              Built for large codebases and sprawling doc trees
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Built-in embeddings, Rust-powered structural tracing, multi-pass graph enrichment, path weights for fine-grained control, and optional 10&ndash;16&times; compression &mdash; running locally, integrated with every major AI coding tool.
            </p>
          </div>
          <FeatureBlocks features={codragFeatures} variant="cards" />
        </section>

        {/* How It Works — Quick visual */}
        <section className="rounded-2xl border border-border bg-surface p-8 md:p-12">
          <div className="text-center mb-12">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Seamless Integration</p>
            <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
              Works where you work.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG runs locally as an MCP server. Connect it to Cursor, Windsurf, or Claude Desktop once, and it&apos;s there forever.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {/* Step 1: Setup */}
            <div className="rounded-xl border border-border bg-background p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-border pb-4">
                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">1</div>
                <h3 className="font-semibold text-text">Connect the Server</h3>
              </div>
              <div className="font-mono text-sm space-y-4">
                <div>
                  <div className="text-text-muted text-xs mb-1"># Start the local daemon</div>
                  <div className="bg-surface p-2 rounded border border-border-subtle text-success">
                    $ codrag serve
                  </div>
                </div>
                <div>
                  <div className="text-text-muted text-xs mb-1"># Add to Cursor / Windsurf config</div>
                  <div className="bg-surface p-2 rounded border border-border-subtle text-text-subtle">
                    {`"codrag": {`} <br/>
                    &nbsp;&nbsp;{`"command": "codrag",`} <br/>
                    &nbsp;&nbsp;{`"args": ["mcp"]`} <br/>
                    {`}`}
                  </div>
                </div>
              </div>
            </div>

            {/* Step 2: Usage */}
            <div className="rounded-xl border border-border bg-background p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-border pb-4">
                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">2</div>
                <h3 className="font-semibold text-text">Just Ask Your Editor</h3>
              </div>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="mt-1 w-6 h-6 rounded bg-primary/20 flex-shrink-0" />
                  <div className="text-sm bg-primary/5 p-3 rounded-lg text-text">
                    <span className="font-bold block mb-1 text-primary">You</span>
                    &quot;Trace the calls to <code className="bg-primary/10 px-1 rounded">processRefund</code> and check for missing error handlers.&quot;
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="mt-1 w-6 h-6 rounded bg-info/20 flex-shrink-0" />
                  <div className="text-sm bg-surface border border-border-subtle p-3 rounded-lg text-text-muted font-mono text-xs">
                    <div className="flex items-center gap-2 mb-2 text-info">
                      <Terminal className="w-3 h-3" />
                      <span>Running codrag(trace_expand=true)...</span>
                    </div>
                    <div>&gt; Found definition in src/payments/refunds.ts</div>
                    <div>&gt; Traced 4 call sites in src/api/* (Rust Graph)</div>
                    <div>&gt; Found 1 unhandled Promise rejection</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="text-center mt-8">
             <a href="https://docs.codrag.io/mcp" className="text-sm text-primary hover:underline">View full integration guides for Cursor & Windsurf →</a>
          </div>
        </section>

        {/* What You Need — Tech Stack */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">What you need</p>
            <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
              One install. Batteries included.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG ships with built-in embeddings &mdash; semantic search, structural tracing, graph enrichment, and context assembly work from a single install. Add CLaRa when you need to compress massive context payloads.
            </p>
          </div>
          <TechStackMatrix />
        </section>

        {/* Free vs Pro */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Plans</p>
            <h2 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
              Free to start. Pro when you&apos;re ready.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Start with one project for free. Upgrade to Pro for unlimited projects, the structural Code Graph with multi-pass enrichment, and a perpetual license.
            </p>
          </div>
          <TierComparison />
        </section>

        {/* Trust / social proof strip */}
        <section className="text-center space-y-8">
          <h2 className="text-2xl font-bold tracking-tight text-text sm:text-3xl">
            Built for professionals who take their code seriously
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-3xl mx-auto">
            <div>
              <div className="text-3xl font-bold text-primary">&lt;100ms</div>
              <div className="text-sm text-text-muted mt-1">Search latency</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">0 bytes</div>
              <div className="text-sm text-text-muted mt-1">Sent to the cloud</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">10&ndash;16&times;</div>
              <div className="text-sm text-text-muted mt-1">Context compression with CLaRa</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">Perpetual</div>
              <div className="text-sm text-text-muted mt-1">License available</div>
            </div>
          </div>
          <div className="pt-4">
            <a
              href="/download"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
            >
              Get CoDRAG <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </section>
      </div>
    </main>
  );
}
