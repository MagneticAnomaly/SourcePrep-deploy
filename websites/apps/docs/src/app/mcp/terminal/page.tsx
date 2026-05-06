import { MCP_TOOLS } from '../../../config/mcp-setup';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function TerminalIntegrationsPage() {
  const terminalTools = MCP_TOOLS.filter((t) => t.category === 'cli');

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/mcp" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Back to Integrations
        </a>

        <div className="mt-6 flex items-center gap-4">
          <div className="p-3 bg-primary/10 rounded-xl border border-primary/20 text-primary">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-8 h-8"><path d="M4 17l6-6-6-6M12 19h8"></path></svg>
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              CLI Agents
            </h1>
            <p className="mt-1 text-lg text-text-muted">
              Connect Claude Code, OpenAI Codex, Gemini CLI, and other MCP-aware command-line agents directly to your index.
            </p>
          </div>
        </div>

        <div className="mt-8 prose max-w-none">
          <p>
            CLI agents operate headless, but still require structural intelligence when modifying your project. Connecting SourcePrep locally allows them to execute semantic searches and assess blast radiuses without leaving the command line. Claude Code is the primary target; Codex and Gemini CLI use the same MCP server.
          </p>

          <AnchorHeading id="setup" level="h2">Integration Setup</AnchorHeading>
          <p>
            Select your Terminal AI agent below. Update the respective configuration file with the provided JSON block to register SourcePrep as an MCP tool. Ensure the SourcePrep daemon is running (<code>prep serve</code>) before starting a chat session in the terminal.
          </p>
        </div>

        <div className="mt-12 space-y-12">
          {terminalTools.map((tool) => (
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
