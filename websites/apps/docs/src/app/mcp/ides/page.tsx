import { MCP_TOOLS } from '../../../config/mcp-setup';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function IdeIntegrationsPage() {
  const ideTools = MCP_TOOLS.filter((t) => t.category === 'ide');

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/mcp" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Back to Integrations
        </a>

        <div className="mt-6">
          <h1 className="text-3xl font-bold tracking-tight">
            Agentic IDEs
          </h1>
          <p className="mt-4 text-lg text-text-muted">
            Give Cursor, Windsurf, Copilot, and other agentic editors deep structural codebase awareness.
          </p>
        </div>

        <div className="mt-8 prose max-w-none">
          <p>
            When an editor supports the Model Context Protocol (MCP), it means the AI can defer complex codebase searches to a specialized indexer like CoDRAG. The AI agent explicitly calls CoDRAG's tools (like <code>codrag</code>, <code>codrag_search</code>, or <code>codrag_impact</code>) behind the scenes, reading the results before composing an answer for you.
          </p>

          <AnchorHeading id="setup" level="h2">Integration Setup</AnchorHeading>
          <p>
            Choose your preferred editor below and copy-paste the configuration. Then restart the window. Ensure the CoDRAG backend is running locally (<code>codrag serve</code>) before making requests in the IDE.
          </p>
        </div>

        <div className="mt-12 space-y-12">
          {ideTools.map((tool) => (
            <section
              key={tool.id}
              id={tool.id}
              className="scroll-mt-24 border border-border bg-surface p-6 rounded-2xl"
            >
              <h3 className="text-2xl font-bold mb-1 group flex items-center gap-2">
                {tool.name}
              </h3>
              <p className="text-sm text-text-subtle mb-4 font-mono">
                {tool.file} <span className="text-text-subtle/60">({tool.fileHint})</span>
              </p>
              <pre className="bg-background border border-border-subtle rounded-xl p-5 text-sm font-mono overflow-x-auto whitespace-pre">
                {JSON.stringify(tool.config, null, 2)}
              </pre>
              {tool.notes && (
                <p className="text-sm text-text-muted mt-4 border-l-2 border-primary/50 pl-3">
                  {tool.notes}
                </p>
              )}
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
