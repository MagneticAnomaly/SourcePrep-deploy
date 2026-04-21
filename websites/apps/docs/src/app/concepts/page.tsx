export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Core Concepts</h1>
        <p className="mt-4 text-xl text-text-muted">
          Understanding how Prep processes and serves code context.
        </p>

        <div className="mt-12 space-y-6">
          <a
            href="/concepts/indexing"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Local Indexing</h2>
            <p className="mt-2 text-sm text-text-muted">
              How the semantic search engine works. Embeddings, chunking strategies, and the
              real-time file watcher.
            </p>
          </a>

          <a
            href="/concepts/code-graph"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Code Graph</h2>
            <p className="mt-2 text-sm text-text-muted">
              The Rust-powered graph engine. How we map imports, function calls, and symbol
              definitions across your entire monorepo.
            </p>
          </a>

          <a
            href="/concepts/context"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Context Assembly</h2>
            <p className="mt-2 text-sm text-text-muted">
              How Prep combines search results, trace neighbors, and path weights into a
              single optimized prompt payload for LLMs.
            </p>
          </a>

          <a
            href="/concepts/graph-enrichment"
            className="block rounded-lg border border-primary/50 bg-gradient-to-br from-primary/5 to-transparent p-6 hover:border-primary transition-colors"
          >
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold">Graph Enrichment</h2>
              <span className="text-xs font-medium bg-primary/10 text-primary px-2 py-0.5 rounded-full">Pro</span>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              A 9-stage pipeline that deepens the Code Graph over time — from fast structural
              parsing to LLM-powered deep reasoning, module synthesis, and self-refining
              convergence. Rooted in epistemological principles: the graph knows what it knows,
              and knows when that knowledge has gone stale.
            </p>
          </a>
        </div>
      </div>
    </main>
  );
}
