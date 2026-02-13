import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">
          MCP Integrations
        </h1>
        <p className="mt-4 text-xl text-text-muted">
          Connect CoDRAG to your favorite AI editors using the Model Context Protocol.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <a href="/mcp/cursor" className="group block space-y-3 rounded-2xl border border-border bg-surface p-6 hover:border-primary transition-colors">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold group-hover:text-primary">Cursor</h3>
              <span className="text-text-muted">→</span>
            </div>
            <p className="text-text-muted">
              Use CoDRAG as a custom MCP server in Cursor&apos;s Agent mode. Replaces generic search with structural code intelligence.
            </p>
          </a>

          <a href="/mcp/windsurf" className="group block space-y-3 rounded-2xl border border-border bg-surface p-6 hover:border-primary transition-colors">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold group-hover:text-primary">Windsurf</h3>
              <span className="text-text-muted">→</span>
            </div>
            <p className="text-text-muted">
              Give Cascade superpowers. Enable CoDRAG to provide deep context, call graphs, and compressed summaries.
            </p>
          </a>
        </div>

        <div className="mt-16 prose  max-w-none">
          <AnchorHeading id="what-is-mcp" level="h2">What is MCP?</AnchorHeading>
          <p>
            The <a href="https://modelcontextprotocol.io" target="_blank" className="text-primary hover:underline">Model Context Protocol (MCP)</a> is an open standard that enables AI models to interact with external data and tools.
          </p>
          <p>
            CoDRAG runs a local MCP server that exposes your indexed codebase as a set of tools. 
            It supports both <strong>Stdio</strong> (recommended for local editors) and <strong>SSE</strong> (for remote/containerized setups).
            When you connect an editor like Cursor or Windsurf, their internal AI agents gain the ability to:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>Search Semantically:</strong> Find code by meaning (&quot;auth logic&quot;) rather than just keywords.</li>
            <li><strong>Code Graph:</strong> Follow import paths and function calls (Rust-powered graph).</li>
            <li><strong>Compress Context:</strong> Use CLaRa to fit massive documentation into the prompt.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
