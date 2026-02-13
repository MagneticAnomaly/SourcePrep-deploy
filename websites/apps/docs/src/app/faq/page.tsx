import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">FAQ</h1>
        <p className="mt-4 text-xl text-text-muted">
          Frequently asked questions about CoDRAG.
        </p>

        <div className="mt-12 space-y-8">
          
          <div>
            <AnchorHeading id="cloud-upload" level="h2" className="text-xl font-semibold text-text">Is my code uploaded to the cloud?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <strong>No.</strong> CoDRAG is local-first software. All indexing, vector storage, and processing happens on your machine. 
              The only time data leaves your machine is if you explicitly configure a cloud LLM (BYOK) or during the one-time license activation check.
            </p>
          </div>

          <div>
            <AnchorHeading id="editor-support" level="h2" className="text-xl font-semibold text-text">Does it work with any editor?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              CoDRAG works best with editors that support the <strong>Model Context Protocol (MCP)</strong>, such as Cursor, Windsurf, and Claude Desktop. 
              There is also a VS Code extension in development. For other editors, you can copy-paste context from the Dashboard or CLI.
            </p>
          </div>

          <div>
            <AnchorHeading id="gpu-requirement" level="h2" className="text-xl font-semibold text-text">Do I need a GPU?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <strong>No.</strong> The core features (indexing, trace graph, search) run efficiently on CPU. 
              The built-in embedding model is quantized and optimized for CPU inference. 
              However, if you enable the CLaRa compression model locally, a GPU (NVIDIA or Apple Silicon) is highly recommended for reasonable latency.
            </p>
          </div>

          <div>
            <AnchorHeading id="cursor-diff" level="h2" className="text-xl font-semibold text-text">How is this different from Cursor&apos;s built-in index?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              Cursor&apos;s index is great, but CoDRAG adds a <strong>Structural Code Graph layer</strong> (understanding imports, definitions, and calls across the project) which reduces hallucinations. 
              CoDRAG also gives you explicit control over context via <strong>Path Weights</strong> and <strong>Compression</strong>, allowing you to fit much more relevant code into the context window than a standard RAG approach.
            </p>
          </div>

          <div>
            <AnchorHeading id="free-tier" level="h2" className="text-xl font-semibold text-text">Is there a free tier?</AnchorHeading>
            <p className="mt-2 text-text-muted leading-relaxed">
              <strong>Yes.</strong> The Free tier allows you to use CoDRAG with 1 active project and manual indexing. 
              Upgrading to Starter or Pro unlocks unlimited projects, the real-time file watcher, and advanced features like CLaRa compression.
            </p>
          </div>

        </div>
      </div>
    </main>
  );
}
