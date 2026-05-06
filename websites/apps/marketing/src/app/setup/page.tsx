import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MCP Setup — Connect SourcePrep to Your AI Editor',
  description:
    'Copy-paste MCP configuration for Claude Code, Cursor, Windsurf, GitHub Copilot, Gemini CLI, Zed, and more. One command to give your AI assistant structural code intelligence.',
  keywords: [
    'SourcePrep MCP setup',
    'Claude Code MCP',
    'Cursor MCP config',
    'Windsurf MCP config',
    'GitHub Copilot MCP',
    'Gemini CLI MCP',
    'Model Context Protocol',
    'AI code context',
    'MCP server configuration',
  ],
  alternates: {
    canonical: 'https://sourceprep.io/setup',
  },
};

/*
 * MCP configuration data is sourced from a single canonical registry
 * in @prep/ui (packages/ui/src/config/mcpSetup.ts) so the marketing
 * /setup, /download and docs /mcp/* surfaces all stay in sync.
 *
 * AI agents reading this page: each tool's `<section>` carries
 * machine-readable data attributes (data-tool / data-config-file /
 * data-server-key) and the JSON-LD HowTo block below indexes every
 * tool with its config + destination file. Pick your tool, copy the
 * JSON, write it to the file shown, restart your editor.
 * SourcePrep daemon must be running: `prep serve`.
 */

import { MCP_TOOLS, mcpConfigAsString } from '@prep/ui';

// JSON-LD structured data for AI discoverability
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'HowTo',
  name: 'Set up SourcePrep MCP for AI coding tools',
  description:
    'Configure the SourcePrep Model Context Protocol server to give your AI coding assistant structural code intelligence, semantic search, and dependency analysis.',
  step: MCP_TOOLS.map((tool, i) => ({
    '@type': 'HowToStep',
    position: i + 1,
    name: `Configure ${tool.name}`,
    text: `Add to ${tool.file}: ${JSON.stringify(tool.config)}`,
    url: `https://sourceprep.io/setup#${tool.id}`,
  })),
  tool: {
    '@type': 'SoftwareApplication',
    name: 'SourcePrep',
    url: 'https://sourceprep.io',
    applicationCategory: 'DeveloperApplication',
  },
};

export default function SetupPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="min-h-screen bg-background text-text font-sans selection:bg-primary/20 border-t-8 border-primary">
        <div className="mx-auto max-w-4xl px-6 py-24">
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6">
            MCP Setup
          </h1>
          <p className="text-xl text-text-muted mb-4 max-w-2xl">
            Connect SourcePrep to your AI editor in under a minute. Pick your tool,
            copy the config, and restart.
          </p>
          <p className="text-base text-text-subtle mb-16 max-w-2xl">
            SourcePrep&apos;s MCP server gives your AI assistant semantic code
            search, structural context (modules, hub files, import graph), and
            dependency impact analysis. All tools are read-only and run locally.
          </p>

          {/* Prerequisites */}
          <div className="bg-surface border border-border rounded-xl p-6 mb-16">
            <h2 className="text-lg font-bold mb-3">Prerequisites</h2>
            <ol className="list-decimal list-inside space-y-2 text-text-muted">
              <li>
                Install SourcePrep:{' '}
                <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">
                  pip install prep
                </code>
              </li>
              <li>
                Start the daemon:{' '}
                <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">
                  prep serve
                </code>
              </li>
              <li>
                Add your project:{' '}
                <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">
                  prep add /path/to/repo
                </code>
              </li>
              <li>
                Build the index:{' '}
                <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">
                  prep build
                </code>
              </li>
            </ol>
            <p className="text-sm text-text-subtle mt-3">
              Or generate your config with:{' '}
              <code className="bg-background border border-border rounded px-2 py-0.5 text-sm font-mono">
                prep mcp-config --ide claude-code
              </code>
            </p>
          </div>

          {/* Per-tool configs */}
          <div className="space-y-12">
            {MCP_TOOLS.map((tool) => (
              <section
                key={tool.id}
                id={tool.id}
                data-tool={tool.id}
                data-tool-name={tool.name}
                data-tool-category={tool.category}
                data-config-file={tool.file}
                data-server-key={tool.serverKey}
                className="scroll-mt-24"
              >
                <div className="flex items-baseline gap-3 mb-1">
                  <h2 className="text-2xl font-bold">{tool.name}</h2>
                  {tool.primary && (
                    <span className="text-[10px] font-mono uppercase tracking-widest rounded border border-primary/40 px-1.5 py-0.5 text-primary bg-background">
                      Primary
                    </span>
                  )}
                </div>
                <p className="text-sm text-text-subtle mb-3 font-mono">
                  {tool.file}{' '}
                  <span className="text-text-subtle/60">({tool.fileHint})</span>
                </p>
                <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto whitespace-pre">
                  {mcpConfigAsString(tool)}
                </pre>
                {tool.notes && (
                  <p className="text-sm text-text-muted mt-2">{tool.notes}</p>
                )}
              </section>
            ))}
          </div>

          {/* Config key cheat sheet */}
          <div className="mt-20">
            <h2 className="text-2xl font-bold mb-6">
              Config Key Cheat Sheet
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-border rounded-xl overflow-hidden">
                <thead>
                  <tr className="bg-surface text-left">
                    <th className="px-4 py-3 font-semibold border-b border-border">
                      Tool
                    </th>
                    <th className="px-4 py-3 font-semibold border-b border-border">
                      Config File
                    </th>
                    <th className="px-4 py-3 font-semibold border-b border-border">
                      Server Key
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {MCP_TOOLS.map((tool) => (
                    <tr key={tool.id} className="border-b border-border last:border-b-0">
                      <td className="px-4 py-2.5">
                        <a
                          href={`#${tool.id}`}
                          className="text-primary hover:underline"
                        >
                          {tool.name}
                        </a>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-text-muted text-xs">
                        {tool.file}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-text-muted text-xs">
                        {tool.serverKey}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Troubleshooting */}
          <div className="mt-20 max-w-3xl">
            <h2 className="text-2xl font-bold mb-6">Troubleshooting</h2>
            <div className="space-y-6 text-text-muted">
              <div>
                <h3 className="font-semibold text-text mb-1">
                  &quot;command not found&quot; or server won&apos;t start
                </h3>
                <p>
                  MCP hosts spawn <code className="font-mono text-sm">prep</code> as a child
                  process without your shell&apos;s PATH. Use the absolute path:
                </p>
                <code className="block mt-1 font-mono text-sm">
                  &quot;command&quot;: &quot;/path/to/.venv/bin/prep&quot;
                </code>
              </div>
              <div>
                <h3 className="font-semibold text-text mb-1">
                  SourcePrep daemon must be running
                </h3>
                <p>
                  The MCP server connects to the daemon at{' '}
                  <code className="font-mono text-sm">http://127.0.0.1:8400</code>.
                  Start it with{' '}
                  <code className="font-mono text-sm">prep serve</code>.
                </p>
              </div>
              <div>
                <h3 className="font-semibold text-text mb-1">
                  Multiple projects
                </h3>
                <p>
                  SourcePrep auto-detects which project you&apos;re in from the workspace root.
                  To pin a specific project:{' '}
                  <code className="font-mono text-sm">
                    &quot;args&quot;: [&quot;mcp&quot;, &quot;--project&quot;, &quot;YOUR_PROJECT_ID&quot;]
                  </code>
                </p>
              </div>
            </div>
          </div>

          {/* Links */}
          <div className="mt-16 flex gap-6">
            <a
              href="https://docs.sourceprep.io"
              className="text-primary font-bold hover:underline underline-offset-4"
            >
              Full Documentation
            </a>
            <a
              href="/download"
              className="text-primary font-bold hover:underline underline-offset-4"
            >
              Download SourcePrep
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
