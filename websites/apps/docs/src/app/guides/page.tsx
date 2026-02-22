export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Docs home
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Guides</h1>
        <p className="mt-4 text-lg text-text-muted">
          Step-by-step guides for CoDRAG&apos;s advanced features.
        </p>

        <div className="mt-8 space-y-6">
          <a
            href="/guides/embeddings"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Built-in Embeddings</h2>
            <p className="mt-2 text-sm text-text-muted">
              CoDRAG ships with a built-in embedding model (nomic-embed-text). No Ollama required.
              Learn how to use it, switch providers, and pre-download the model.
            </p>
          </a>

          <a
            href="/guides/models"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Model Configuration</h2>
            <p className="mt-2 text-sm text-text-muted">
              Configure local LLMs for analysis, reasoning, and compression. Learn about the
              recommended Ministral 3 stack and model slots.
            </p>
          </a>

          <a
            href="/guides/compression"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Smart Context Compression</h2>
            <p className="mt-2 text-sm text-text-muted">
              Two built-in engines: structural compression for code (3–20×) and language-aware
              compression for docs. No GPU or sidecar needed.
            </p>
          </a>

          <a
            href="/guides/path-weights"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Path Weights</h2>
            <p className="mt-2 text-sm text-text-muted">
              Boost or suppress specific files and folders in search results.
              Hierarchical weights let you tune relevance without rebuilding.
            </p>
          </a>

          <a
            href="/guides/model-advisor"
            className="block rounded-lg border border-primary/30 bg-primary/5 p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Model Setup Advisor</h2>
            <p className="mt-2 text-sm text-text-muted">
              Interactive tool: pick your GPU, choose Local / Hybrid / Cloud,
              and get personalized model recommendations with VRAM calculations.
            </p>
          </a>
        </div>
      </div>
    </main>
  );
}
