import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/cli" className="text-sm text-text-muted">
          ← CLI Reference
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Commands</h1>
        <p className="mt-4 text-lg text-text-muted">
          Complete reference for the <code>prep</code> command-line interface.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="serve" level="h2">prep serve</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep serve [--port &lt;port&gt;] [--host &lt;host&gt;] [--reload]</code></pre>
          <p className="text-sm text-text-muted">
            Starts the SourcePrep daemon and API server. This is the core process that must be running for MCP and the Dashboard to work.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--port</code>: Port to listen on (default: 8400).</li>
            <li><code>--reload</code>: Enable auto-reload (for development).</li>
          </ul>
          <p className="text-sm mt-2 text-text-muted">
            <em>To enable debug logging, set <code>PREP_LOG_LEVEL=DEBUG</code> before running.</em>
          </p>

          <AnchorHeading id="add" level="h2" className="mt-8">prep add</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep add &lt;path&gt; [--name &lt;name&gt;] [--mode &lt;mode&gt;]</code></pre>
          <p className="text-sm text-text-muted">
            Registers a directory as a project and starts initial indexing.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--name</code>: Friendly name for the project.</li>
            <li><code>--mode</code>: <code>standalone</code> (default), <code>embedded</code> (stores index in repo), or <code>custom</code>.</li>
            <li><code>--index-path</code>: Required if mode is custom. Useful for scratch disks.</li>
          </ul>

          <AnchorHeading id="build" level="h2" className="mt-8">prep build</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep build [&lt;project_id&gt;] [--full]</code></pre>
          <p className="text-sm text-text-muted">
            Triggers a manual re-index for a project. Useful if the watcher was off or you want to force a clean slate.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--full</code>: Force a full rebuild, ignoring incremental cache.</li>
          </ul>

          <AnchorHeading id="search" level="h2" className="mt-8">prep search</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep search &lt;query&gt; [--project &lt;id&gt;] [--limit &lt;k&gt;] [--min-score &lt;s&gt;]</code></pre>
          <p className="text-sm text-text-muted">
            Runs a semantic search against the index and prints results. Great for testing retrieval quality.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--limit</code>: Number of results (default: 10).</li>
            <li><code>--min-score</code>: Minimum similarity score 0.0-1.0 (default: 0.15).</li>
          </ul>

          <AnchorHeading id="context" level="h2" className="mt-8">prep context</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep context &lt;query&gt; [--project &lt;id&gt;] [--limit &lt;k&gt;] [--max-chars &lt;n&gt;] [--raw]</code></pre>
          <p className="text-sm text-text-muted">
            Generates the full prompt context payload for a given query, including citations.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--limit</code>: Number of chunks (default: 5).</li>
            <li><code>--max-chars</code>: Maximum characters in output (default: 8000).</li>
            <li><code>--raw</code>: Output only the context string (no stats/formatting), useful for piping to LLMs.</li>
          </ul>

          <AnchorHeading id="status" level="h2" className="mt-8">prep status</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep status</code></pre>
          <p className="text-sm text-text-muted">
            Prints the health of the daemon, connected projects, and index statistics (file count, vector count).
          </p>

          <AnchorHeading id="mcp" level="h2" className="mt-8">prep mcp</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep mcp [--mode &lt;mode&gt;] [--auto] [--debug]</code></pre>
          <p className="text-sm text-text-muted">
            Runs the MCP server. Primary entry point for editor integration.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--mode</code>: <code>server</code> (default, connects to daemon) or <code>direct</code> (runs engine in-process).</li>
            <li><code>--daemon</code>: URL of the daemon (default: <code>http://127.0.0.1:8400</code>). Used in server mode.</li>
            <li><code>--repo-root</code>: Path to repo root. Required for direct mode if not current directory.</li>
            <li><code>--auto</code>: Auto-detect project from current working directory (server mode).</li>
            <li><code>--debug</code>: Enable verbose logging to stderr.</li>
            <li><code>--log-file</code>: Write debug logs to a specific file.</li>
            <li><code>--transport</code>: <code>stdio</code> (default) or <code>http</code> (SSE).</li>
          </ul>

          <AnchorHeading id="mcp-config" level="h2" className="mt-8">prep mcp-config</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep mcp-config [--ide &lt;ide&gt;] [--mode &lt;mode&gt;]</code></pre>
          <p className="text-sm text-text-muted">
            Generates configuration JSON for connecting various editors (Cursor, Windsurf, Claude Code) to SourcePrep.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--ide</code>: Target editor (<code>cursor</code>, <code>windsurf</code>, <code>vscode</code>, <code>claude</code>, or <code>all</code>).</li>
            <li><code>--mode</code>: <code>auto</code> (detects project from cwd), <code>project</code> (pinned to ID), or <code>direct</code> (no daemon).</li>
            <li><code>--project</code>: Project ID to pin (required if mode is <code>project</code>).</li>
          </ul>

          <AnchorHeading id="utilities" level="h2" className="mt-12 text-2xl font-bold">Utilities & Visualization</AnchorHeading>

          <AnchorHeading id="list" level="h3" className="mt-6 text-xl font-semibold">prep list</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep list</code></pre>
          <p className="text-sm text-text-muted">
            Lists all registered projects with their IDs, paths, and modes.
          </p>

          <AnchorHeading id="ui" level="h3" className="mt-6 text-xl font-semibold">prep ui</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep ui [--port &lt;port&gt;]</code></pre>
          <p className="text-sm text-text-muted">
            Opens the SourcePrep web dashboard in your default browser.
          </p>

          <AnchorHeading id="models" level="h3" className="mt-6 text-xl font-semibold">prep models</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep models</code></pre>
          <p className="text-sm text-text-muted">
            Downloads the native embedding model (nomic-embed-text-v1.5) for offline use. 
            Useful for air-gapped environments or pre-loading before the first build.
          </p>

          <AnchorHeading id="activity" level="h3" className="mt-6 text-xl font-semibold">prep activity</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep activity [--weeks &lt;n&gt;] [--json] [--no-legend] [--no-labels]</code></pre>
          <p className="text-sm text-text-muted">
            Displays a terminal-based heatmap of indexing activity (GitHub-style).
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--weeks</code>: Number of weeks to display (default: 12).</li>
            <li><code>--json</code>: Output raw JSON data instead of the visualization.</li>
            <li><code>--no-legend</code>: Hide the color legend.</li>
            <li><code>--no-labels</code>: Hide day/month labels.</li>
          </ul>

          <AnchorHeading id="coverage" level="h3" className="mt-6 text-xl font-semibold">prep coverage</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep coverage</code></pre>
          <p className="text-sm text-text-muted">
            Shows a file tree visualization indicating which files are indexed, traced, or ignored.
          </p>

          <AnchorHeading id="overview" level="h3" className="mt-6 text-xl font-semibold">prep overview</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep overview [--weeks &lt;n&gt;]</code></pre>
          <p className="text-sm text-text-muted">
            Shows a comprehensive dashboard overview in the terminal, including health stats and activity.
          </p>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li><code>--weeks</code>: Number of weeks for the activity graph (default: 12).</li>
          </ul>

          <AnchorHeading id="remove" level="h3" className="mt-6 text-xl font-semibold">prep remove</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep remove &lt;project_id&gt; [--purge]</code></pre>
          <p className="text-sm text-text-muted">
            Unregisters a project from the daemon. Use <code>--purge</code> to also delete the index files from disk.
          </p>

          <AnchorHeading id="version" level="h3" className="mt-6 text-xl font-semibold">prep version</AnchorHeading>
          <pre className="overflow-x-auto text-sm"><code>prep version</code></pre>
          <p className="text-sm text-text-muted">
            Prints the installed version of SourcePrep.
          </p>

        </div>
      </div>
    </main>
  );
}
