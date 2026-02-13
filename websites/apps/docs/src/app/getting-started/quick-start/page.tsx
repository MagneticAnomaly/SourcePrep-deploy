import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/getting-started" className="text-sm text-text-muted">
          ← Getting Started
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Quick Start</h1>
        <p className="mt-4 text-lg text-text-muted">
          The fastest way to get structural context into your AI editor.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="five-minute-guide" level="h2">The 5-Minute Guide</AnchorHeading>
          
          <div className="space-y-8 mt-6">
            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">1</span>
                Launch CoDRAG
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Open the CoDRAG desktop app. It automatically starts the background daemon that manages the index and serves requests.
              </p>
              <p className="text-xs text-text-muted ml-8">
                Power users: you can also run <code>codrag serve</code> in a terminal.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">2</span>
                Index Your Repo
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Click the <strong>+</strong> button in the sidebar, select your project folder, and CoDRAG will scan and build the Code Graph immediately.
              </p>
              <p className="text-xs text-text-muted ml-8">
                Or via CLI: <code>codrag add ~/my-project</code>
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">3</span>
                Connect MCP
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Configure your editor (Cursor/Windsurf) to use the local server.
              </p>
              <div className="ml-8 grid grid-cols-2 gap-4">
                <a href="/mcp/cursor" className="block p-3 border border-border rounded hover:border-primary">
                  <strong>Cursor Guide →</strong>
                </a>
                <a href="/mcp/windsurf" className="block p-3 border border-border rounded hover:border-primary">
                  <strong>Windsurf Guide →</strong>
                </a>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">4</span>
                Ask with Context
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                In your editor&apos;s AI chat, ask a question that requires deep knowledge.
              </p>
              <blockquote className="ml-8 border-l-2 border-primary pl-4 py-1 italic text-text-muted">
                &quot;How does the authentication middleware interact with the user service? Trace the calls.&quot;
              </blockquote>
            </div>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="cli-tips" level="h2">Pro Tips</AnchorHeading>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li>
              <strong>Search via CLI:</strong> You can test retrieval without an editor using <code>codrag search &quot;query&quot;</code>.
            </li>
            <li>
              <strong>Force Rebuild:</strong> If you switched branches massively, run <code>codrag build</code> to ensure the index is fresh (though the watcher handles this mostly).
            </li>
            <li>
              <strong>Check Status:</strong> Run <code>codrag status</code> to see index stats and coverage.
            </li>
          </ul>

        </div>
      </div>
    </main>
  );
}
