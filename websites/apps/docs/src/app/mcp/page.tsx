import { AnchorHeading } from '../../components/AnchorHeading';
import { StoryEmbed } from '../../components/StoryEmbed';

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
          Connect SourcePrep to your favorite AI editors using the Model Context Protocol.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <a href="/mcp/ides" className="group block space-y-3 rounded-2xl border border-border bg-surface p-6 hover:border-primary transition-colors">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold group-hover:text-primary">Agentic IDEs</h3>
              <span className="text-text-muted">→</span>
            </div>
            <p className="text-text-muted">
              Cursor, Windsurf, Antigravity, VS Code (via Copilot), and Zed — plus MCP-aware VS Code extensions (Cline, Roo, CodeGPT).
            </p>
          </a>

          <a href="/mcp/terminal" className="group block space-y-3 rounded-2xl border border-border bg-surface p-6 hover:border-primary transition-colors">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold group-hover:text-primary">CLI Agents</h3>
              <span className="text-text-muted">→</span>
            </div>
            <p className="text-text-muted">
              Claude Code (primary), OpenAI Codex, and Gemini CLI — connect any MCP-aware command-line agent directly to your local SourcePrep index.
            </p>
          </a>

          <a href="/mcp/paperclip" className="group block space-y-3 rounded-2xl border border-primary/30 bg-primary/5 p-6 hover:border-primary transition-colors sm:col-span-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold group-hover:text-primary">Paperclip Plugin</h3>
              <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">New</span>
            </div>
            <p className="text-text-muted">
              Give every Paperclip agent structural codebase intelligence. 5 tools, dashboard widgets, and event-driven context — installed as a native Paperclip plugin.
            </p>
          </a>
        </div>

        <div className="mt-16 prose  max-w-none">
          <AnchorHeading id="what-is-mcp" level="h2">What is MCP?</AnchorHeading>
          <p>
            The <a href="https://modelcontextprotocol.io" target="_blank" className="text-primary hover:underline">Model Context Protocol (MCP)</a> is an open standard that enables AI models to interact with external data and tools.
          </p>
          <p>
            SourcePrep runs a local MCP server that exposes your indexed codebase as a set of tools.
            It supports both <span className="font-semibold text-text">Stdio</span> (recommended for local editors) and <span className="font-semibold text-text">SSE</span> (for remote/containerized setups).
            When you connect a CLI agent like Claude Code or Codex, or an IDE like Cursor or Windsurf, their internal AI agents gain the ability to:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><span className="font-semibold text-text">Get Oriented:</span> Call <code>prep</code> with no arguments to get ambient context — module structures, hub files, and your selected focus areas formatted perfectly for internal understanding.</li>
            <li><span className="font-semibold text-text">Search Semantically:</span> Use <code>prep_search</code> to find code by meaning ("auth logic") rather than just keywords, expanding structurally to provide required imports automatically.</li>
            <li><span className="font-semibold text-text">Code Graph:</span> Follow import paths and function calls (Rust-powered graph) defensively. Use <code>prep_impact</code> to see exact blast radiuses before modifying a file.</li>
            <li><span className="font-semibold text-text">Persistent Memory:</span> Use <code>prep_observe</code> to write cross-session notes that get automatically flagged as `[STALE]` when the underlying files are modified.</li>
            <li><span className="font-semibold text-text">Audit Codebase:</span> Use <code>prep_audit</code> to get a health report with architecture findings, tech debt, dead code, and test coverage gaps. <a href="/guides/codebase-audit" className="text-primary hover:underline">Learn more →</a></li>
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
                  <td className="py-2 pr-4 font-mono text-xs">prep</td>
                  <td className="py-2 text-xs">Ambient context — hub files, module summaries, focus areas (no arguments needed)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep_search</td>
                  <td className="py-2 text-xs">Semantic search with trace expansion, atlas routing, LOD compression</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep_impact</td>
                  <td className="py-2 text-xs">Blast radius analysis — what depends on a file or symbol</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-xs">prep_observe</td>
                  <td className="py-2 text-xs">Save or retrieve cross-session notes about the codebase (with stale flags)</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">prep_audit</td>
                  <td className="py-2 text-xs">Run or retrieve codebase health audits (action = scan, refactor, verify, report)</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="live-preview" level="h2">Live Dashboard Preview</AnchorHeading>
          <p className="mt-2 mb-4">
            These are live, interactive previews of the SourcePrep dashboard panels your agents interact with.
          </p>

          <div className="grid gap-6 mt-6">
            <StoryEmbed
              storyId="dashboard-widgets-searchpanel--default"
              height={280}
              caption="Semantic Search Panel — find code by meaning, not keywords"
            />
            <StoryEmbed
              storyId="dashboard-widgets-indexstatuscard--loaded"
              height={220}
              caption="Index Status Card — real-time view of your codebase index"
            />
          </div>
        </div>
      </div>
    </main>
  );
}
