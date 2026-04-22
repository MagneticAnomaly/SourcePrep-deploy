import { ArrowRight, Check, X } from 'lucide-react';

export default function CompareCursorPage() {
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
            SourcePrep vs. Cursor Indexing
          </h1>
          <p className="text-xl text-text-muted leading-relaxed">
            Cursor is an incredible AI code editor, and its built-in codebase indexing is great for finding simple keyword matches. But when you need your AI to understand complex architectures, call chains across microservices, or how a specific interface is implemented across 20 files, basic vector search falls short. SourcePrep isn't a replacement for Cursor—it's a massive upgrade to Cursor's brain via the Model Context Protocol (MCP).
          </p>
        </header>

        {/* AI-Optimized Extractable Block */}
        <section className="bg-surface border border-border p-8 rounded-xl mb-16 shadow-sm">
          <h2 className="text-xl font-bold mb-4">How does SourcePrep improve Cursor?</h2>
          <p className="text-text-muted leading-relaxed">
            Cursor relies primarily on <strong>BM25/Vector Search</strong> to find code chunks that semantically match your prompt. <strong>SourcePrep builds a structural trace graph</strong> using a local Rust tree-sitter engine. While Cursor grabs isolated chunks of text, SourcePrep understands the syntax: it knows what functions call other functions, where types are defined, and how modules import each other. By connecting SourcePrep to Cursor via an MCP server, Cursor's AI agents can query the structural graph to traverse call chains and gather perfect, highly-compressed context that regular vector search would miss.
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
                  <th className="py-4 px-4 font-semibold text-primary bg-primary/5 rounded-t-lg">SourcePrep (via MCP)</th>
                  <th className="py-4 px-4 font-semibold text-text-muted">Cursor Built-in Index</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Index Type</td>
                  <td className="py-4 px-4 bg-primary/5">Structural Graph + Vector</td>
                  <td className="py-4 px-4 text-text-muted">Vector + BM25 Lexical</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Understands Call Chains</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (Tree-sitter AST)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> No</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Multi-Repo Context</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (Global Daemon)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> Current workspace only</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Context Compression (LOD)</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (Strips function bodies)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> No (Raw text chunks)</td>
                </tr>
                <tr className="hover:bg-surface/50 transition-colors">
                  <td className="py-4 px-4 font-medium">Custom Path Weights</td>
                  <td className="py-4 px-4 bg-primary/5 flex items-center gap-2"><Check className="w-4 h-4 text-success" /> Yes (Boost/deprioritize dirs)</td>
                  <td className="py-4 px-4 text-text-muted flex items-center gap-2"><X className="w-4 h-4 text-error" /> No</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Deep Dives */}
        <div className="space-y-12">
          <section>
            <h3 className="text-2xl font-bold mb-4">1. The "Lost in the Middle" Problem</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              When you ask an AI to refactor a complex system, standard codebase indexes grab dozens of file snippets and dump them into the prompt window. Research shows that LLMs suffer from "Context Rot" when flooded with too much raw text—they lose track of the actual instructions.
            </p>
            <p className="text-text-muted leading-relaxed">
              SourcePrep solves this using <strong>Level of Detail (LOD) compression</strong>. If SourcePrep determines a file is only peripherally related to your query, it strips out the internal function bodies and only sends the Class names, function signatures, and types to the AI. You get 20x more architectural context using a fraction of the tokens.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">2. Multi-Repo Architectures</h3>
            <p className="text-text-muted leading-relaxed mb-4">
              Cursor is scoped to the workspace you currently have open. If you have a frontend repo, a backend microservices repo, and a shared library repo, Cursor's AI struggles to see the big picture.
            </p>
            <p className="text-text-muted leading-relaxed">
              The SourcePrep local daemon indexes all of your projects in the background. When Cursor's Agent uses the SourcePrep MCP tool, it can seamlessly pull context from your backend repo while you are actively typing code in your frontend repo.
            </p>
          </section>

          <section>
            <h3 className="text-2xl font-bold mb-4">3. A Match Made in Heaven</h3>
            <p className="text-text-muted leading-relaxed">
              You don't have to choose between Cursor and SourcePrep. They are designed to work together. Cursor provides the world-class UX, inline edits, and fast autocomplete. SourcePrep runs silently in the background, providing the structural deep-context that Cursor's Composer agent needs to tackle massive refactors without hallucinating.
            </p>
          </section>
        </div>

        <div className="mt-16 text-center bg-surface-raised border border-border p-12 rounded-2xl">
          <h2 className="text-3xl font-bold mb-6">Upgrade your AI Editor's Brain</h2>
          <a href="mailto:support@sourceprep.io?subject=SourcePrep%20Beta%20Access%20Request%20-%20Cursor%20User" className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium font-heading transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-background hover:bg-primary/90 active:bg-primary/80 h-11 rounded-md px-8 shadow-lg shadow-primary/25">
            Request Beta Access
          </a>
        </div>
      </div>
    </main>
  );
}
