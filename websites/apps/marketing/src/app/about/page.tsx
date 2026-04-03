"use client";

import { Button } from '@codrag/ui';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted hover:text-text transition-colors mb-8 inline-block">
          ← Home
        </a>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
          {/* Main Content */}
          <div className="lg:col-span-8">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-6">
              About CoDRAG
            </h1>
            <p className="text-xl text-text-muted leading-relaxed mb-12">
              CoDRAG gives your AI coding tools epistemic context. It traces your codebase deeply
              using semantic search, a Rust-powered structural code graph, and multi-pass enrichment — then
              delivers precisely the right context to Paperclip, Cursor, or any MCP-compatible editor.
            </p>

            {/* Mission */}
            <section className="space-y-6 mb-16">
              <h2 className="text-2xl font-semibold">Our Mission</h2>
              <div className="prose  max-w-none">
                <p className="text-lg text-text-muted leading-relaxed">
                  AI coding tools work best when they understand how your codebase connects —
                  not just individual files. CoDRAG provides multiple retrieval methods (semantic search,
                  structural graph tracing, configurable path weights, and optional compression) so your
                  AI assistant gets high-signal context instead of noise.
                </p>
                <p className="text-lg text-text-muted leading-relaxed mt-4">
                  The result: more relevant suggestions, fewer corrections, and faster iteration —
                  delivered in under 100&thinsp;ms, with Private by Design architecture and optional
                  cloud enrichment via BYOK.
                </p>
              </div>
            </section>
          </div>

          {/* Sidebar / Team */}
          <div className="lg:col-span-4 space-y-12">
            {/* Team */}
            <section className="rounded-2xl border border-border bg-surface p-8">
              <h2 className="text-xl font-semibold mb-4">The Team</h2>
              <p className="text-text-muted leading-relaxed mb-6">
                CoDRAG is built by a small team of engineers who believe developer tools
                should be sophisticated, secure, and honest about what they do. We&apos;re based remotely
                and ship daily.
              </p>
              <div className="flex flex-col gap-3">
                <Button asChild className="w-full">
                  <a href="/download">Download CoDRAG</a>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <a href="/careers">We&apos;re Hiring</a>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <a href="/contact">Contact Us</a>
                </Button>
              </div>
            </section>
          </div>
        </div>

        {/* What we believe - Full Width Grid */}
        <section className="mt-20">
          <h2 className="text-2xl font-semibold mb-8">What We Believe</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border bg-surface p-5">
              <div className="font-semibold text-text">Your code is yours</div>
              <div className="mt-1 text-sm text-text-muted">
                CoDRAG provides Sovereign Context. Your source code and indexes stay on your machine.
                No telemetry, no phone-home. Add a cloud LLM provider via BYOK if you choose — you&apos;re in control.
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface p-5">
              <div className="font-semibold text-text">Structure beats volume</div>
              <div className="mt-1 text-sm text-text-muted">
                AI tools already RAG your files. The gap is structural understanding —
                knowing which code matters and how it connects. That&apos;s what we add.
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface p-5">
              <div className="font-semibold text-text">Own your tools</div>
              <div className="mt-1 text-sm text-text-muted">
                Pro license — pay once, own it forever. No subscriptions required for core features.
                Your development infrastructure shouldn&apos;t depend on someone else&apos;s uptime.
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface p-5">
              <div className="font-semibold text-text">Work with everything</div>
              <div className="mt-1 text-sm text-text-muted">
                CoDRAG integrates with Cursor, Windsurf, VS Code, and Claude Code
                via MCP. We don&apos;t replace your tools — we make them better.
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
