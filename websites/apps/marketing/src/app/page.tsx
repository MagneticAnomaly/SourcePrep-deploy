"use client";

import { MarketingHero, FeatureBlocks, codragFeatures, marketingFeatures } from '@codrag/ui';
import { Terminal, ArrowRight, HelpCircle, Lightbulb, LayoutGrid, Check, Minus } from 'lucide-react';
import { DevMarketingHero } from './DevMarketingHero';

// Shared data for the comparison grid
const comparisonData = [
  {
    title: "Remembers what it learns across sessions",
    desc: "Persistent agent memory with automatic staleness detection",
    codrag: true, ide: false, cloud: false, cli: false
  },
  {
    title: "Compresses context to fit more in the prompt",
    desc: "Structural compression for code (LOD) & language-aware for docs",
    codrag: true, ide: false, cloud: false, cli: false
  },
  {
    title: "Understands how code is structurally connected",
    desc: "Deterministic dependency graph & graph-navigated expansion",
    codrag: true, ide: false, cloud: "Partial", cli: false
  },
  {
    title: "Adapts retrieval based on what you're doing",
    desc: "Automatic intent detection (debug / architecture / implementation)",
    codrag: true, ide: false, cloud: false, cli: false
  },
  {
    title: "Total transparency into what the AI sees",
    desc: "Visible relevance scores, token counts, and exact LLM payloads",
    codrag: true, ide: false, cloud: false, cli: "Partial"
  },
  {
    title: "Fine-grained control over context assembly",
    desc: "Per-query control over k-value, max_chars, and compression level",
    codrag: true, ide: false, cloud: "Partial", cli: "Partial"
  },
  {
    title: "Finds code by meaning, not just exact keywords",
    desc: "Vector semantic search (runs locally via built-in ONNX model)",
    codrag: true, ide: "Cloud", cloud: "Cloud", cli: true
  },
  {
    title: "Works completely offline with zero data sharing",
    desc: "100% local, air-gapped, no telemetry, no data collection",
    codrag: true, ide: false, cloud: false, cli: true
  },
  {
    title: "No heavy AI models or docker containers required",
    desc: "Ships its own embedding model (no Ollama required)",
    codrag: true, ide: false, cloud: false, cli: true
  },
  {
    title: "Take your codebase knowledge to any editor",
    desc: "Editor-agnostic integration via the open MCP standard",
    codrag: true, ide: false, cloud: false, cli: "Partial"
  },
  {
    title: "Updates instantly when you save a file",
    desc: "Incremental symbol-level re-indexing with real-time file watcher",
    codrag: true, ide: "Varies", cloud: true, cli: false
  },
  {
    title: "Own the software forever, no subscription",
    desc: "One-time perpetual license ($79)",
    codrag: true, ide: false, cloud: false, cli: "N/A"
  }
];

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

          {/* Feature Showcase Placeholder */}
          <div className="mb-16 w-full max-w-5xl mx-auto rounded-xl border border-border bg-surface shadow-2xl overflow-hidden aspect-video relative flex items-center justify-center group">
            <div className="absolute inset-0 bg-gradient-to-br from-surface to-background opacity-50" />
            <div className="relative text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <LayoutGrid className="w-8 h-8 text-primary" />
              </div>
              <div>
                <p className="font-mono text-sm text-text-muted">Requires Asset:</p>
                <p className="font-medium text-text">public/images/hero-dashboard-preview.png</p>
              </div>
            </div>
            {/* Optional: Add actual image once available */}
            {/* <img src="/images/hero-dashboard-preview.png" alt="CoDRAG Dashboard" className="absolute inset-0 w-full h-full object-cover" /> */}
          </div>

          <FeatureBlocks features={codragFeatures.filter((_, i) => [0, 1, 3, 5, 6, 9].includes(i))} variant="cards" />
        </section>

        {/* Comparison Grid */}
        <section>
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">How We Compare</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Context quality your editor can&apos;t match alone
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG adds a structural reasoning layer on top of what every AI coding tool already does. Here&apos;s what that means, feature by feature.
            </p>
          </div>
          <div className="hidden md:block overflow-x-auto max-w-6xl mx-auto pb-4">
            <table className="w-full text-sm border-collapse min-w-[800px]">
              <thead>
                <tr className="border-b-2 border-border">
                  <th className="text-left py-3 pr-6 text-text font-semibold w-[44%]">Capability</th>
                  <th className="text-center py-3 px-3 w-[14%]">
                    <div className="text-primary font-bold">CoDRAG</div>
                  </th>
                  <th className="text-center py-3 px-3 w-[14%]">
                    <div className="text-text-muted font-semibold whitespace-nowrap">AI IDEs</div>
                    <div className="text-text-subtle text-xs font-normal mt-0.5">Cursor, Windsurf, Antigravity</div>
                  </th>
                  <th className="text-center py-3 px-3 w-[14%]">
                    <div className="text-text-muted font-semibold whitespace-nowrap">Cloud Indexers</div>
                    <div className="text-text-subtle text-xs font-normal mt-0.5">Augment, Cody</div>
                  </th>
                  <th className="text-center py-3 px-3 w-[14%]">
                    <div className="text-text-muted font-semibold whitespace-nowrap">AI CLIs</div>
                    <div className="text-text-subtle text-xs font-normal mt-0.5">Claude Code</div>
                  </th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                {comparisonData.map((row) => (
                  <tr key={row.title} className="border-b border-border-subtle hover:bg-surface/50 transition-colors">
                    <td className="py-4 pr-6">
                      <div className="text-text font-medium mb-1 text-base">{row.title}</div>
                      <div className="text-text-muted text-xs leading-relaxed">{row.desc}</div>
                    </td>
                    {[row.codrag, row.ide, row.cloud, row.cli].map((val, i) => (
                      <td key={i} className={`text-center py-4 px-3 ${i === 0 ? 'font-semibold' : ''}`}>
                        {val === true ? (
                          <div className="flex justify-center">
                            <Check className={`w-5 h-5 ${i === 0 ? 'text-primary' : 'text-success'}`} strokeWidth={3} />
                          </div>
                        ) : val === false ? (
                          <div className="flex justify-center">
                            <Minus className="w-5 h-5 text-text-muted/30" strokeWidth={2} />
                          </div>
                        ) : (
                          <span className="text-text-muted text-xs font-medium bg-surface-raised px-2 py-1 rounded">{val as string}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Comparison Grid (Stacked View) */}
          <div className="md:hidden border border-border rounded-xl bg-surface overflow-hidden shadow-sm">
            {/* Sticky Header */}
            <div className="sticky top-0 z-10 grid grid-cols-4 bg-background border-b-2 border-border p-3 shadow-sm">
              <div className="text-center flex flex-col items-center justify-center border-r border-border-subtle/50 pr-1">
                <div className="text-primary font-bold text-xs leading-tight">CoDRAG</div>
              </div>
              <div className="text-center flex flex-col items-center justify-center border-r border-border-subtle/50 px-1">
                <div className="text-text-muted font-semibold text-[11px] leading-tight text-balance">AI IDEs</div>
              </div>
              <div className="text-center flex flex-col items-center justify-center border-r border-border-subtle/50 px-1">
                <div className="text-text-muted font-semibold text-[11px] leading-tight text-balance">Cloud Indexers</div>
              </div>
              <div className="text-center flex flex-col items-center justify-center pl-1">
                <div className="text-text-muted font-semibold text-xs leading-tight">AI CLIs</div>
              </div>
            </div>

            {/* Rows */}
            <div className="divide-y divide-border-subtle">
              {comparisonData.map((row) => (
                <div key={row.title} className="p-4 bg-surface hover:bg-surface-raised transition-colors">
                  <div className="mb-3">
                    <div className="text-text font-medium text-sm mb-1">{row.title}</div>
                    <div className="text-text-muted text-[11px] leading-relaxed">{row.desc}</div>
                  </div>
                  <div className="grid grid-cols-4 bg-background/50 rounded-lg py-2 border border-border-subtle">
                    {[row.codrag, row.ide, row.cloud, row.cli].map((val, i) => (
                      <div key={i} className={`flex items-center justify-center ${i < 3 ? 'border-r border-border-subtle' : ''}`}>
                        {val === true ? (
                          <Check className={`w-4 h-4 ${i === 0 ? 'text-primary' : 'text-success'}`} strokeWidth={3} />
                        ) : val === false ? (
                          <Minus className="w-4 h-4 text-text-muted/30" strokeWidth={2} />
                        ) : (
                          <span className="text-text-muted text-[10px] font-medium uppercase tracking-wider">{val as string}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How It Works — Quick visual */}
        <section className="rounded-2xl border border-border bg-surface p-8 md:p-12">
          <div className="text-center mb-12">
            <p className="text-sm font-semibold uppercase tracking-widest text-primary mb-3">Seamless Integration</p>
            <h2 className="text-3xl font-medium tracking-tight text-text sm:text-4xl">
              Works where you work.
            </h2>
            <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto">
              CoDRAG runs locally as an MCP server. Connect it to Cursor, Windsurf, Antigravity, or Claude Desktop once, and it&apos;s there forever.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto mb-16">
            {/* Step 1: Setup */}
            <div className="rounded-xl border border-border bg-background p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-border pb-4">
                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold">1</div>
                <h3 className="font-mono font-medium text-lg text-text">Connect the Server</h3>
              </div>
              <div className="font-mono text-sm space-y-4">
                <div>
                  <div className="text-text-muted text-xs mb-1"># Start the local daemon</div>
                  <div className="bg-surface p-2 rounded border border-border-subtle text-success">
                    $ codrag serve
                  </div>
                </div>
                <div>
                  <div className="text-text-muted text-xs mb-1"># Add to Cursor / Windsurf / Antigravity config</div>
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
                <h3 className="font-mono font-medium text-lg text-text">Just Ask Your Editor</h3>
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

          {/* Integration Showcase Placeholder */}
          <div className="w-full max-w-5xl mx-auto rounded-xl border border-border bg-surface shadow-lg overflow-hidden aspect-[21/9] relative flex items-center justify-center group">
            <div className="absolute inset-0 bg-gradient-to-br from-surface to-background opacity-50" />
            <div className="relative text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Terminal className="w-8 h-8 text-primary" />
              </div>
              <div>
                <p className="font-mono text-sm text-text-muted">Requires Asset:</p>
                <p className="font-medium text-text">public/images/integration-cursor-windsurf.png</p>
              </div>
            </div>
          </div>
          
          <div className="text-center mt-12">
             <a href="https://docs.codrag.io/mcp" className="text-sm text-primary hover:underline">View full integration guides for Cursor, Windsurf, & Antigravity →</a>
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
              <div className="text-3xl font-bold text-primary">Pro</div>
              <div className="text-sm text-text-muted mt-1">Own it forever</div>
            </div>
          </div>
          <div className="pt-4">
            <a
              href="/download"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-background shadow-lg shadow-primary/25 hover:bg-primary-hover transition-colors"
            >
              Get CoDRAG <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </section>
      </div>
    </main>
  );
}
