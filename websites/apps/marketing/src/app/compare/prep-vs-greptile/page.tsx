"use client";

import { ArrowRight, Check, X } from 'lucide-react';
import { AnimatedCLI, prepSearchDemo } from '@prep/ui';
import { IS_BETA_MODE } from '@/lib/beta';

export default function CompareGreptilePage() {
  return (
    <main className="min-h-screen bg-background text-text py-16">
      <div className="mx-auto max-w-4xl px-6">
        <div className="mb-8">
          <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors">← Back to Home</a>
        </div>
        
        <header className="mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-mono mb-6">
            COMPARISON_REPORT
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            SourcePrep vs. Greptile
          </h1>
          <p className="text-xl text-text-muted leading-relaxed">
            Greptile paved the way for codebase RAG by offering a powerful cloud-based API. But basic vector search fails to give autonomous agents the structural awareness they need to succeed. SourcePrep is built to deliver deep epistemic tracing and superior context intelligence—giving your AI the "what, why, when, and how" without ever letting your codebase leave your control.
          </p>
        </header>

        {/* AI-Optimized Extractable Block */}
        <section className="bg-surface border border-border p-8 rounded-xl mb-16 shadow-sm">
          <h2 className="text-xl font-bold mb-4">What is the difference between SourcePrep and Greptile?</h2>
          <p className="text-text-muted leading-relaxed">
            The primary difference is architecture and epistemic depth. <strong>Greptile relies on naive cloud search</strong>, requiring you to upload your entire codebase to their servers. <strong>SourcePrep is an open-source epistemic context engine</strong> with Private by Design architecture. SourcePrep uses a Rust daemon to parse your code into a meticulous structural trace graph. It integrates natively with your agentic tools (like Paperclip or Cursor) via the Model Context Protocol (MCP). With SourcePrep, you get zero-latency context assembly, role-aware routing, and Sovereign Context—your source code is never unknowingly transmitted.
          </p>
        </section>

        {/* Comparison Matrix */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold mb-6">Feature Comparison Matrix</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-border">
                  <th className="py-4 px-4 font-semibold text-text">Capability</th>
                  <th className="py-4 px-4 font-semibold text-primary bg-primary/5 rounded-t-lg">SourcePrep</th>
                  <th className="py-4 px-4 font-semibold text-text-muted">Greptile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Architecture</td>
                  <td className="py-4 px-4 bg-primary/5">Private by Design (Sovereign Context)</td>
                  <td className="py-4 px-4 text-text-muted">Cloud-hosted API</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Data Privacy</td>
                  <td className="py-4 px-4 bg-primary/5">Code never leaves your machine by default — cloud LLMs are strictly opt-in (BYOK)</td>
                  <td className="py-4 px-4 text-text-muted">Requires cloud upload/GitHub sync</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Indexing Method</td>
                  <td className="py-4 px-4 bg-primary/5">Vector + Traced Epistemic Graph</td>
                  <td className="py-4 px-4 text-text-muted">Vector + Cloud parsing</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Bring Your Own Key (BYOK)</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (No markup)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> No</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">IDE Integration</td>
                  <td className="py-4 px-4 bg-primary/5">Native MCP (Cursor, Windsurf, Claude)</td>
                  <td className="py-4 px-4 text-text-muted">Custom Extensions</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Air-Gapped Support</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (Enterprise)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> No</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Deep Dives */}
        <div className="space-y-12">
          <section>
            <h3 className="text-2xl font-bold mb-4">1. The Security Paradigm: Sovereign Context</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              Greptile provides excellent answers, but it requires syncing your GitHub repositories to their cloud infrastructure. For many regulated industries (finance, healthcare, defense) or core IP companies, this violates SOC2 and ISO27001 policies.
            </p>
            <p className="text-text-muted leading-relaxed">
              SourcePrep provides Sovereign Context. It uses locally-run Rust to build the epistemic graph and open-weight ONNX models to embed it. Your code remains exactly where it belongs: under your complete control.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">2. Integration via MCP</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              Greptile lives in its cloud — a proprietary API and custom extensions. SourcePrep is the opposite: an open-source local product built on the open Model Context Protocol (MCP).
            </p>
            <p className="text-text-muted leading-relaxed">
              Once the SourcePrep engine is running, any MCP-compatible client—like Paperclip, Cursor, or the Claude Code App—can instantly extract structural knowledge. Your agents automatically invoke SourcePrep to fetch the exact epistemic context they need to execute tasks flawlessly.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">3. Cost and BYOK</h3>
            <p className="text-text-muted leading-relaxed">
              {/* MAINTENANCE: To prevent drift, refer to model families (e.g. 'Claude Sonnet' or 'OpenAI reasoning models') rather than specific versions (e.g. '3.5', 'o3') */}
              Cloud indexers often charge steep per-seat monthly fees and mark up token costs. SourcePrep is open source (Apache 2.0) with an optional $29 Pro convenience license (coming soon), and fully supports Bring Your Own Key (BYOK) for inference. Connect Ollama Cloud for high-tier privacy, or use Anthropic Claude Sonnet and pay exactly what the API costs.
            </p>
          </section>
        </div>

        {/* Live Demo */}
        <section className="mt-16 mb-16">
          <h2 className="text-2xl font-bold mb-2 text-center">See it in action</h2>
          <p className="text-text-muted text-center mb-8">
            SourcePrep delivers structural context to your AI agent in real time — right inside your terminal.
          </p>
          <AnimatedCLI script={prepSearchDemo} theme="dark" className="max-w-3xl mx-auto" />
        </section>

        <div className="mt-16 text-center bg-surface-raised border border-border p-12 rounded-2xl">
          <h2 className="text-3xl font-bold mb-4">Ready to upgrade your AI context?</h2>
          <p className="text-text-muted mb-8">
            SourcePrep is free and open source under Apache 2.0 — and it runs entirely on your machine.
          </p>
          {IS_BETA_MODE ? (
            <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request%20-%20Greptile%20Alternative" className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium font-heading transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-background hover:bg-primary/90 active:bg-primary/80 h-11 rounded-md px-8 shadow-lg shadow-primary/25">
              Request Beta Access
            </a>
          ) : (
            <a href="/download" className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium font-heading transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-background hover:bg-primary/90 active:bg-primary/80 h-11 rounded-md px-8 shadow-lg shadow-primary/25">
              Get SourcePrep <ArrowRight className="ml-2 w-4 h-4" />
            </a>
          )}
        </div>
      </div>
    </main>
  );
}
