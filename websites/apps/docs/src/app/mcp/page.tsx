import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
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
            It supports both <span className="font-semibold text-text">Stdio</span> (recommended for local editors) and <span className="font-semibold text-text">SSE</span> (for remote/containerized setups).
            When you connect an editor like Cursor or Windsurf, their internal AI agents gain the ability to:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><span className="font-semibold text-text">Get Oriented:</span> Use <code>hi_codrag</code> to see exactly which files you&apos;ve selected — with doc previews, topic detection (&quot;authentication&quot;, &quot;UI components&quot;), hub file identification, import relationships, and tailored next-step suggestions.</li>
            <li><span className="font-semibold text-text">Search Semantically:</span> Find code by meaning (&quot;auth logic&quot;) rather than just keywords, automatically scoped to your selected files.</li>
            <li><span className="font-semibold text-text">Code Graph:</span> Follow import paths and function calls (Rust-powered graph). <code>hi_codrag</code> shows file connections and the most-imported files at a glance.</li>
            <li><span className="font-semibold text-text">Compress Context:</span> Smart compression fits more files into the same token budget &mdash; structural for code, language-aware for docs. No sidecar needed.</li>
            <li><span className="font-semibold text-text">Audit Codebase:</span> Use <code>codrag_audit</code> to get a health report with architecture findings, tech debt, dead code, and test coverage gaps. Use <code>codrag_audit_report</code> to read full generated reports. <a href="/guides/codebase-audit" className="text-primary hover:underline">Learn more →</a></li>
          </ul>

          <AnchorHeading id="tools-reference" level="h2">Tools Reference</AnchorHeading>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 text-left font-semibold">Tool</th>
                  <th className="py-2 text-left font-semibold">Purpose</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">hi_codrag</td>
                  <td className="py-2 text-xs">Project overview — health, selected files, topics, hub files, suggested prompts</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_search</td>
                  <td className="py-2 text-xs">Semantic search with trace expansion, atlas routing, LOD compression</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag</td>
                  <td className="py-2 text-xs">Ambient context — hub files, module summaries, LOD neighbors (no query needed)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_status</td>
                  <td className="py-2 text-xs">Index status, build state, daemon health</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_build</td>
                  <td className="py-2 text-xs">Trigger index build (async)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_trace_search</td>
                  <td className="py-2 text-xs">Search the code graph for symbols by name</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_trace_neighbors</td>
                  <td className="py-2 text-xs">Get neighbors for a trace node (imports, callers, etc.)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_trace_coverage</td>
                  <td className="py-2 text-xs">Trace coverage statistics (traced/untraced/stale files)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_impact</td>
                  <td className="py-2 text-xs">Blast radius analysis — what depends on a file or symbol</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_save_observation</td>
                  <td className="py-2 text-xs">Save a cross-session note about the codebase</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_get_observations</td>
                  <td className="py-2 text-xs">Retrieve previous observations (with stale flags)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">codrag_audit</td>
                  <td className="py-2 text-xs">Run or retrieve codebase health audit (11 analyzers)</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">codrag_audit_report</td>
                  <td className="py-2 text-xs">Read a specific generated audit report by name</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}
