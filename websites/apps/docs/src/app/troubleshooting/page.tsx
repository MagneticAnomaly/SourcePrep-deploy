import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">Troubleshooting</h1>
        <p className="mt-4 text-xl text-text-muted">
          Common issues and how to resolve them.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="daemon" level="h2">Daemon & Connection</AnchorHeading>
          
          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">Connection Refused (Port 8400)</h3>
              <p className="text-sm text-text-muted mb-4">
                If your editor or the CLI says it cannot connect to the server:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Ensure CoDRAG is running (open the desktop app or run <code>codrag serve</code>).</li>
                <li>Check if port 8400 is blocked by a firewall or another process.</li>
                <li>On Windows, you may need to allow CoDRAG through the firewall when prompted.</li>
              </ul>
            </div>

            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">MCP Client Disconnected</h3>
              <p className="text-sm text-text-muted mb-4">
                If Cursor or Windsurf loses connection:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Restart the CoDRAG desktop app (or the <code>codrag serve</code> process if running manually).</li>
                <li>In Cursor: Go to Settings &gt; MCP and click the &quot;Refresh&quot; icon next to codrag.</li>
                <li>In Windsurf: Restart the window (Cmd+R).</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="embeddings" level="h2" className="mt-12">Embeddings & Models</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">&quot;Ollama not found&quot; / Connection Error</h3>
              <p className="text-sm text-text-muted mb-4">
                <strong>Good news:</strong> You probably don&apos;t need Ollama.
              </p>
              <p className="text-sm mb-4">
                CoDRAG uses <strong>Native Embeddings</strong> (ONNX) by default, which run inside the CoDRAG process without any external dependencies.
              </p>
              <p className="text-sm mb-4">
                If you explicitly configured <code>embedding_source: &quot;ollama&quot;</code> in your project config:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Ensure Ollama is running (`ollama serve`).</li>
                <li>Verify the URL in your config (default: `http://localhost:11434`).</li>
                <li>Check that the model you selected (e.g. `nomic-embed-text`) is pulled (`ollama pull nomic-embed-text`).</li>
              </ul>
            </div>

            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">Model Download Stuck</h3>
              <p className="text-sm text-text-muted mb-4">
                When using Native Embeddings, CoDRAG downloads the model (~300MB) on the first run.
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Check your internet connection.</li>
                <li>The model is cached in <code>~/.cache/huggingface/hub</code>. You can try deleting this folder to force a re-download.</li>
                <li>Run <code>codrag serve --debug</code> to see detailed download progress logs.</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="search" level="h2" className="mt-12">Search Results</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">No Results Found</h3>
              <p className="text-sm text-text-muted mb-4">
                If search returns nothing for a query you expect to match:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li><strong>Check coverage:</strong> Is the file actually indexed? Run <code>codrag coverage</code> or check the dashboard.</li>
                <li><strong>Lower threshold:</strong> The default <code>min_score</code> is 0.15. Try <code>codrag search &quot;query&quot; --min-score 0.01</code> to see if it&apos;s just a ranking issue.</li>
                <li><strong>Broaden query:</strong> Semantic search works best with natural language sentences, not just keywords.</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="indexing" level="h2" className="mt-12">Indexing & Build</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">Index Stuck or &quot;Hanging&quot;</h3>
              <p className="text-sm text-text-muted mb-4">
                If indexing seems to stop:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Check the daemon logs for errors (<code>codrag serve --debug</code>).</li>
                <li>Large binary files or minified JS bundles can slow down indexing. Add them to your <code>exclude_globs</code>.</li>
                <li>Restart the daemon to clear any stuck locks.</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="mcp" level="h2" className="mt-12">MCP & Projects</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">Project Selection Ambiguous</h3>
              <p className="text-sm text-text-muted mb-4">
                If the MCP server returns <code>PROJECT_SELECTION_AMBIGUOUS</code>:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>You have multiple projects registered and are not inside a specific project directory.</li>
                <li><strong>Fix:</strong> Pin the project ID in your MCP config (<code>&quot;args&quot;: [&quot;mcp&quot;, &quot;--project&quot;, &quot;proj_xyz&quot;]</code>).</li>
                <li><strong>Fix:</strong> Or navigate to the project directory before running the tool (if using direct mode).</li>
              </ul>
            </div>

            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">Tools Not Appearing</h3>
              <p className="text-sm text-text-muted mb-4">
                If <code>codrag_search</code> and other tools don&apos;t show up in your editor:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Check if the <code>codrag</code> executable is in your PATH.</li>
                <li>Verify the config file path (e.g. <code>~/.codeium/windsurf/mcp_config.json</code>).</li>
                <li>Restart the editor to reload the MCP connection.</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="performance" level="h2" className="mt-12">Performance</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">High Memory Usage</h3>
              <p className="text-sm text-text-muted mb-4">
                If the daemon consumes too much RAM:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Reduce the number of indexed files by excluding large folders (<code>vendor/</code>, <code>node_modules/</code>) in <code>.codrag/ignore</code>.</li>
                <li>Lower the <code>max_file_bytes</code> setting in your project configuration (via Dashboard or <code>.codrag/config.json</code>).</li>
                <li>If using CLaRa locally, ensure you have enough GPU VRAM (or switch to a remote instance).</li>
              </ul>
            </div>
          </div>

          <AnchorHeading id="files" level="h2" className="mt-12">File Issues</AnchorHeading>

          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">File Not Included</h3>
              <p className="text-sm text-text-muted mb-4">
                If a specific file isn&apos;t showing up in search:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Check your <code>include_globs</code> in the Dashboard or config. Default is <code>[&quot;**/*.py&quot;, &quot;**/*.md&quot;, ...]</code>.</li>
                <li>Ensure the file extension is supported.</li>
                <li>Verify the file is not hidden or in a dot-folder (unless explicitly included).</li>
              </ul>
            </div>

            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">File Excluded</h3>
              <p className="text-sm text-text-muted mb-4">
                If a file is being ignored against your wishes:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>Check <code>exclude_globs</code> in the Dashboard.</li>
                <li>Check your project's <code>.gitignore</code> (CoDRAG respects this by default).</li>
                <li>Check for a <code>.codrag/ignore</code> file.</li>
              </ul>
            </div>

            <div className="border border-border rounded-lg p-6 bg-surface">
              <h3 className="text-lg font-semibold mt-0">File Too Large</h3>
              <p className="text-sm text-text-muted mb-4">
                If you see <code>FILE_TOO_LARGE</code> errors in the log:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>The default limit is 500KB per file to prevent choking on minified assets or data dumps.</li>
                <li>Increase the limit: <code>codrag config set max_file_bytes 1000000</code> (or via Dashboard).</li>
                <li>Or exclude the file if it&apos;s not useful for context.</li>
              </ul>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}
