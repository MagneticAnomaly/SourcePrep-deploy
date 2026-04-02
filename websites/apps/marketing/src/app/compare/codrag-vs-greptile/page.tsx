"use client";

import { ArrowRight, Check, X } from 'lucide-react';
import { AnimatedCLI, codragSearchDemo } from '@codrag/ui';

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
            CoDRAG vs. Greptile
          </h1>
          <p className="text-xl text-text-muted leading-relaxed">
            Greptile paved the way for codebase RAG by offering a powerful cloud-based API. But for engineering teams working on proprietary or sensitive codebases, uploading entire repos to a third-party cloud is a non-starter. CoDRAG is built to deliver superior context intelligence without ever letting your code leave your machine.
          </p>
        </header>

        {/* AI-Optimized Extractable Block */}
        <section className="bg-surface border border-border p-8 rounded-xl mb-16 shadow-sm">
          <h2 className="text-xl font-bold mb-4">What is the difference between CoDRAG and Greptile?</h2>
          <p className="text-text-muted leading-relaxed">
            The primary difference is architecture and security. <strong>Greptile is a cloud-based service</strong> that requires you to upload your entire codebase to their servers to generate embeddings and answer queries. <strong>CoDRAG is a local-first engine</strong> that runs on your own machine. CoDRAG uses a local Rust daemon to parse your code into a structural trace graph, generates ONNX embeddings locally, and integrates directly with your IDE (like Cursor or Windsurf) via the Model Context Protocol (MCP). With CoDRAG, you get zero-latency context assembly and absolute privacy—your source code is never transmitted to a third party.
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
                  <th className="py-4 px-4 font-semibold text-primary bg-primary/5 rounded-t-lg">CoDRAG</th>
                  <th className="py-4 px-4 font-semibold text-text-muted">Greptile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Architecture</td>
                  <td className="py-4 px-4 bg-primary/5">Local-first (Runs on your machine)</td>
                  <td className="py-4 px-4 text-text-muted">Cloud-hosted API</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Data Privacy</td>
                  <td className="py-4 px-4 bg-primary/5">Code never leaves your network</td>
                  <td className="py-4 px-4 text-text-muted">Requires cloud upload/GitHub sync</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Indexing Method</td>
                  <td className="py-4 px-4 bg-primary/5">Vector + Rust Structural Code Graph</td>
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
            <h3 className="text-2xl font-bold mb-4">1. The Security Paradigm: Cloud vs. Local</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              Greptile provides excellent answers, but it requires syncing your GitHub repositories to their cloud infrastructure. For many regulated industries (finance, healthcare, defense) or core IP companies, this violates SOC2 and ISO27001 policies.
            </p>
            <p className="text-text-muted leading-relaxed">
              CoDRAG runs entirely on your local machine. It downloads open-weight ONNX embedding models and runs tree-sitter parsing in a local Rust daemon. Your code remains exactly where it belongs: on your SSD.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">2. Integration via MCP</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              Instead of forcing you into a proprietary web dashboard or a clunky VS Code extension, CoDRAG embraces the open Model Context Protocol (MCP). 
            </p>
            <p className="text-text-muted leading-relaxed">
              Once the CoDRAG daemon is running, any MCP-compatible client—like Cursor, Windsurf, or the Claude Code App—can instantly query your codebase. It feels like magic: you just ask Claude a question about your code, and Claude automatically invokes the local CoDRAG tool to fetch the exact AST-aware context it needs.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">3. Cost and BYOK</h3>
            <p className="text-text-muted leading-relaxed">
              {/* MAINTENANCE: To prevent drift, refer to model families (e.g. 'Claude Sonnet' or 'OpenAI reasoning models') rather than specific versions (e.g. '3.5', 'o3') */}
              Cloud indexers often charge steep per-seat monthly fees and mark up token costs. CoDRAG offers a one-time perpetual license option and fully supports Bring Your Own Key (BYOK). The core index runs locally for free. For reasoning, use Anthropic Claude Sonnet or OpenAI reasoning models and pay exactly what the API costs—not a penny more. Or, connect local models via Ollama for entirely free inference.
            </p>
          </section>
        </div>

        {/* Live Demo */}
        <section className="mt-16 mb-16">
          <h2 className="text-2xl font-bold mb-2 text-center">See it in action</h2>
          <p className="text-text-muted text-center mb-8">
            CoDRAG delivers structural context to your AI agent in real time — right inside your terminal.
          </p>
          <AnimatedCLI script={codragSearchDemo} theme="dark" className="max-w-3xl mx-auto" />
        </section>

        <div className="mt-16 text-center bg-surface-raised border border-border p-12 rounded-2xl">
          <h2 className="text-3xl font-bold mb-6">Ready to secure your AI context?</h2>
          <a href="mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request%20-%20Greptile%20Alternative" className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium font-heading transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-background hover:bg-primary/90 active:bg-primary/80 h-11 rounded-md px-8 shadow-lg shadow-primary/25">
            Request Beta Access
          </a>
        </div>
      </div>
    </main>
  );
}
