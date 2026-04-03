import { AnchorHeading } from '../../components/AnchorHeading';
import { StoryEmbed } from '../../components/StoryEmbed';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">CLI Reference</h1>
        <p className="mt-4 text-xl text-text-muted">
          Automate your workflow with the CoDRAG command-line interface.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <a
            href="/cli/commands"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Commands</h2>
            <p className="mt-2 text-sm text-text-muted">
              Complete reference for <code>codrag serve</code>, <code>build</code>, <code>search</code>, and more.
            </p>
          </a>

          <a
            href="/cli/config"
            className="block rounded-lg border border-border bg-surface p-6 hover:border-primary transition-colors"
          >
            <h2 className="text-xl font-semibold">Configuration</h2>
            <p className="mt-2 text-sm text-text-muted">
              Global daemon settings and project-level overrides (<code>.codrag/config.json</code>).
            </p>
          </a>
        </div>

        <div className="mt-12 prose  max-w-none">
          <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>
          <p>
            The CoDRAG CLI is included with the desktop app and provides a command-line interface
            for managing the daemon and interacting with your local index.
          </p>
          
          <AnchorHeading id="common-workflows" level="h3">Common Workflows</AnchorHeading>
          <ul className="list-disc pl-5">
            <li>
              <span className="font-semibold text-text">Running the Server:</span> <code>codrag serve</code> (Required for Dashboard & MCP)
            </li>
            <li>
              <span className="font-semibold text-text">Adding Projects:</span> <code>codrag add .</code>
            </li>
            <li>
              <span className="font-semibold text-text">Debugging:</span> <code>codrag status</code> and <code>codrag search "query"</code>
            </li>
          </ul>

          <div className="not-prose my-8">
            <StoryEmbed
              storyId="console-animatedcli--semantic-search"
              height={350}
              title="CoDRAG MCP Demo — Semantic Search"
              caption="Live demo: An AI agent using CoDRAG's semantic search and structural trace expansion."
            />
          </div>
        </div>
      </div>
    </main>
  );
}
