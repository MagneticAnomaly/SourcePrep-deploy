"use client";

import { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures, CompetitorMatrix, AnimatedIDE, ideDemoScript } from '@codrag/ui';
import { Terminal, ArrowRight, HelpCircle, Lightbulb, Check, Minus } from 'lucide-react';
import Link from 'next/link';
import { DevMarketingHero } from './DevMarketingHero';


const IS_BETA_MODE = true;

export default function Page() {
  const showDevToolbar = process.env.NODE_ENV !== 'production';

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 space-y-24">
        {/* Hero Section */}
        {showDevToolbar ? <DevMarketingHero /> : <MarketingHero variant="yale" />}

        {/* What is CoDRAG? (SEO Optimized) */}
        <section className="sr-only sm:not-sr-only sm:max-w-4xl sm:mx-auto sm:text-center sm:mb-8">
          <h2 className="text-xl font-semibold text-text mb-2">What is CoDRAG?</h2>
          <p className="text-text-muted">
            CoDRAG is a local codebase indexing and context assembly engine designed for AI-assisted development. 
            It creates a structural code graph using Rust and tree-sitter to map imports, call chains, and symbol hierarchies. 
            By integrating directly via the Model Context Protocol (MCP) into tools like Cursor, Windsurf, and Claude Code, 
            CoDRAG provides highly compressed, structurally-aware context to AI models. Your code index stays perfectly secure on your machine, while you freely connect your choice of cloud APIs or local models for reasoning.
          </p>
        </section>

        {/* Why CoDRAG — Problem / Solution / Result */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Why developers need this</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              If you use AI to write code, you need CoDRAG
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              AI assistants are only as good as the context they receive. CoDRAG makes sure they get the right context, every time — delivering <strong className="text-text font-semibold">3–20× more signal per token</strong> than dumping whole files into the prompt.
            </p>
          </div>
          <FeatureBlocks features={marketingFeatures} variant="list" />
        </section>

        {/* Core Features */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Capabilities</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Built for large codebases and sprawling doc trees
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Built-in embeddings, Rust-powered structural tracing, multi-pass graph enrichment, path weights for fine-grained control, and smart compression for both code and documentation &mdash; running locally, integrated with every major AI coding tool.
            </p>
          </div>

          {/* Feature Showcase Video */}
          <div className="mb-16 w-full max-w-5xl mx-auto rounded-xl border border-border shadow-2xl overflow-hidden aspect-video relative flex items-center justify-center bg-black">
            <iframe 
              className="absolute inset-0 w-full h-full"
              src="https://www.youtube.com/embed/bjC6DFQ8Zmw?rel=0" 
              title="CoDRAG Demo Video" 
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
              referrerPolicy="strict-origin-when-cross-origin" 
              allowFullScreen
            />
          </div>

          <FeatureBlocks features={codragFeatures.filter((_, i) => [0, 1, 2, 4, 6, 7, 10].includes(i))} variant="cards" />
        </section>

        {/* Comparison Grid */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">How We Compare</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Context quality your editor can't match alone
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG adds a continuous epistemic reasoning layer on top of what every AI coding tool already does. Here's how our native architecture compares.
            </p>
          </div>
          <div className="max-w-7xl mx-auto">
            <CompetitorMatrix 
              mobileVariant="simplified"
              mobileAction={
                <Link 
                  href="/compare" 
                  className="inline-flex items-center justify-center gap-2 bg-primary/10 text-primary hover:bg-primary/20 px-6 py-3 rounded-full text-sm font-semibold transition-colors w-full sm:w-auto"
                >
                  View Detailed Comparison <ArrowRight className="w-4 h-4" />
                </Link>
              }
            />
          </div>
        </section>

        {/* Live IDE Demonstration */}
        <section className="mb-16">
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Live IDE Demo</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              See autonomous editing in action
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              This isn't just theory. Connect the CoDRAG MCP server to modern agentic IDEs, and let your AI securely traverse your codebase and edit files directly.
            </p>
          </div>
          <div className="w-full max-w-5xl mx-auto shadow-2xl">
            <AnimatedIDE script={ideDemoScript} className="w-full border-border rounded-xl" />
          </div>
        </section>

        {/* How It Works — The Three Tools */}
        <section className="rounded-2xl border border-border bg-surface p-8 md:p-12">
          <div className="text-center mb-12">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">How Developers Use It</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Three tools. Zero configuration.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG runs locally as an MCP server. Connect it once to Cursor, Windsurf, Antigravity, or Claude Code &mdash; and your AI gets ambient codebase awareness, project orientation, and architectural audits automatically.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto mb-12">
            {/* Tool 1: codrag — Ambient Context */}
            <div className="rounded-xl border border-primary/30 bg-[#0c1222] p-5 flex flex-col">
              <div className="flex items-center gap-2 mb-3">
                <span className="inline-flex items-center px-2 py-0.5 rounded bg-primary/20 text-primary text-[10px] font-bold uppercase tracking-wider">Most Used</span>
              </div>
              <h3 className="font-mono font-bold text-lg text-text mb-1">codrag</h3>
              <p className="text-sm text-text-muted mb-4">Ambient context. No query needed. Your AI calls this automatically to understand what it&apos;s working with.</p>

              {/* Chat-style panel */}
              <div className="flex-1 rounded-lg border border-border-subtle bg-[#0a0f1c] overflow-hidden">
                {/* Tool call bar */}
                <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-surface/30">
                  <Terminal className="w-3 h-3 text-primary" />
                  <span className="font-mono text-[11px] text-primary">codrag</span>
                  <span className="font-mono text-[10px] text-text-muted ml-auto">auto</span>
                </div>
                {/* Response */}
                <div className="px-3 py-3 font-mono text-xs text-text-subtle space-y-1.5">
                  <div><span className="text-primary">&#9656;</span> Hub files: <span className="text-text">api/server.ts</span>, <span className="text-text">core/index.ts</span></div>
                  <div><span className="text-primary">&#9656;</span> Module: Payment Processing (12 files)</div>
                  <div><span className="text-primary">&#9656;</span> 4 structural neighbors loaded</div>
                  <div><span className="text-primary">&#9656;</span> Understanding score: <span className="text-success">0.91</span></div>
                </div>
              </div>
              <p className="text-[11px] text-text-muted italic mt-3">Hub files, module summaries, graph neighbors &mdash; delivered before the AI writes a single line.</p>
            </div>

            {/* Tool 2: codrag_impact — Blast Radius Assessment */}
            <div className="rounded-xl border border-border bg-background p-5 flex flex-col">
              <h3 className="font-mono font-bold text-lg text-text mb-1">codrag_impact</h3>
              <p className="text-sm text-text-muted mb-4">Calculate the blast radius of a file or symbol before you change it. Know precisely what will break downstream.</p>

              {/* Chat-style panel */}
              <div className="flex-1 rounded-lg border border-border-subtle bg-[#0a0f1c] overflow-hidden">
                {/* User message */}
                <div className="px-3 py-2.5 border-b border-border-subtle">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">You</span>
                  <p className="text-sm text-text mt-0.5">What breaks if I modify UserSchema?</p>
                </div>
                {/* Tool call bar */}
                <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border-subtle bg-surface/30">
                  <Terminal className="w-3 h-3 text-primary" />
                  <span className="font-mono text-[11px] text-primary">codrag_impact</span>
                </div>
                {/* AI response */}
                <div className="px-3 py-2.5 font-mono text-xs text-text-muted space-y-1.5">
                  <div>Direct dependents: <span className="text-text font-medium">3 files</span></div>
                  <div>Transitive dependents: <span className="text-warning font-medium">7 files</span></div>
                  <div className="pt-1.5 mt-1.5 border-t border-border-subtle text-[11px]">
                    <span className="text-primary">&#9656;</span> <span className="text-text">api/login.ts</span> and <span className="text-text">db/migrations.ts</span> will require updates.
                  </div>
                </div>
              </div>
            </div>

            {/* Tool 3: codrag_audit — Architecture Audit */}
            <div className="rounded-xl border border-border bg-background p-5 flex flex-col">
              <h3 className="font-mono font-bold text-lg text-text mb-1">codrag_audit</h3>
              <p className="text-sm text-text-muted mb-4">Structural codebase audit. Finds architectural issues, tech debt, and quality gaps from the trace graph &mdash; no LLM required.</p>

              {/* Chat-style panel */}
              <div className="flex-1 rounded-lg border border-border-subtle bg-[#0a0f1c] overflow-hidden">
                {/* User message */}
                <div className="px-3 py-2.5 border-b border-border-subtle">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">You</span>
                  <p className="text-sm text-text mt-0.5">Audit my codebase</p>
                </div>
                {/* Tool call bar */}
                <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border-subtle bg-surface/30">
                  <Terminal className="w-3 h-3 text-primary" />
                  <span className="font-mono text-[11px] text-primary">codrag_audit</span>
                </div>
                {/* AI response */}
                <div className="px-3 py-2.5 font-mono text-xs text-text-muted space-y-1.5">
                  <div><span className="text-warning font-bold">ARCH-1</span> <span className="text-text-subtle">Circular dep: auth ↔ users</span></div>
                  <div><span className="text-warning font-bold">QUAL-3</span> <span className="text-text-subtle">4 files &gt;500 lines (split)</span></div>
                  <div><span className="text-success font-bold">TEST</span> <span className="text-text-subtle">89% coverage on core/</span></div>
                  <div className="pt-1.5 mt-1.5 border-t border-border-subtle text-[11px]">
                    Say <span className="text-text">&quot;fix ARCH-1&quot;</span> to get trace context + action plan.
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Setup snippet */}
          <div className="max-w-2xl mx-auto">
            <div className="rounded-xl border border-border bg-background p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">&#x2713;</div>
                <h3 className="font-mono font-medium text-sm text-text">One-time setup &mdash; 30 seconds</h3>
              </div>
              <div className="font-mono text-sm space-y-3">
                <div className="bg-surface p-2 rounded border border-border-subtle text-success text-xs">
                  $ codrag serve
                </div>
                <div className="bg-surface p-2 rounded border border-border-subtle text-text-subtle text-xs">
                  <span className="text-text-muted">{`// Add to your editor's MCP config:`}</span><br/>
                  {`"codrag": { "command": "codrag", "args": ["mcp"] }`}
                </div>
              </div>
            </div>
          </div>
          
          <div className="text-center mt-10">
             <a href="https://docs.codrag.io/mcp" className="text-sm text-primary hover:underline">View full integration guides for Agentic IDEs (Cursor/Windsurf) & Terminal CLIs (Claude Code) →</a>
          </div>
        </section>

        {/* FAQ Preview */}
        <section>
          <div className="text-center mb-12">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Common Questions</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Questions developers ask first
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              Straight answers about token budgets, context quality, and how CoDRAG compares to what&apos;s already in your editor.
            </p>
          </div>
          <div className="max-w-4xl mx-auto space-y-6">
            {[
              {
                q: "Won\u2019t this just use up my whole context window?",
                a: "No. CoDRAG\u2019s default output is ~1,500 tokens \u2014 roughly 1\u20133% of your available context window. It sends the 5 most relevant code chunks under a hard character ceiling, not your entire codebase.",
              },
              {
                q: "Doesn\u2019t my AI tool already index my codebase?",
                a: "Yes \u2014 and CoDRAG doesn\u2019t replace that. What it adds is the trace graph (call chains, imports, inheritance), user-configurable weights, cross-tool portability via MCP, and optional context compression. No AI coding tool has the trace graph natively.",
              },
              {
                q: "Does the AI remember what it learned across sessions?",
                a: "Yes. CoDRAG maintains a Persistent Agent Memory \u2014 observations about your code (decisions, bugs, patterns) linked to specific files. When those files change, linked observations are automatically flagged [STALE]. The AI gets both the updated code and a signal that its prior assumptions need re-evaluation. No other context tool does this.",
              },
              {
                q: "Does it work with multi-agent and agentic pipelines?",
                a: "Yes \u2014 and this is where CoDRAG adds the most leverage. When you run multiple AI workers in parallel (security review, UI generation, API scaffolding, etc.), each agent automatically receives a context view shaped for its job. A security agent sees auth and data access code. A UI agent sees components and design tokens. Same codebase index \u2014 no extra setup, no repeated context pasting, no agents reading each other's noise.",
              },
            ].map(({ q, a }) => (
              <div key={q} className="rounded-xl border border-border bg-surface p-8">
                <div className="flex items-start gap-3 mb-4">
                  <HelpCircle className="w-6 h-6 text-primary mt-0.5 flex-shrink-0" />
                  <h3 className="font-mono font-medium text-lg text-text leading-snug">{q}</h3>
                </div>
                <div className="flex items-start gap-3 pl-0.5">
                  <Lightbulb className="w-7 h-7 text-text-muted mt-0.5 flex-shrink-0 -ml-0.5" />
                  <p className="text-text-muted text-sm leading-relaxed">{a}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="text-center mt-8">
            <a
              href="/faq"
              className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-6 py-3 text-sm font-semibold text-text hover:bg-surface transition-colors"
            >
              View all FAQs <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </section>

        {/* Trust / social proof strip */}
        <section className="text-center space-y-8">
          <h2 className="text-2xl font-medium tracking-tight text-text sm:text-3xl">
            Built for professionals who take their code seriously
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-5xl mx-auto">
            <div>
              <div className="text-3xl font-bold text-primary">&lt;100ms</div>
              <div className="text-sm text-text-muted mt-1">Search latency</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">Local-first</div>
              <div className="text-sm text-text-muted mt-1">Your code stays on your machine</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">3&ndash;20&times;</div>
              <div className="text-sm text-text-muted mt-1">Smart compression for code &amp; docs</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">Role-aware</div>
              <div className="text-sm text-text-muted mt-1">Each agent gets its own context view</div>
            </div>
          </div>
          <div className="pt-4">
            {IS_BETA_MODE ? (
              <a
                href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Request Beta Access <ArrowRight className="w-4 h-4" />
              </a>
            ) : (
              <a
                href="/download"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
              >
                Get CoDRAG <ArrowRight className="w-4 h-4" />
              </a>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
