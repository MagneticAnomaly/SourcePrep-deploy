import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MCP Setup — Connect Prep to Your AI Editor',
  description:
    'Copy-paste MCP configuration for Claude Code, Cursor, Windsurf, GitHub Copilot, Gemini CLI, Zed, and more. One command to give your AI assistant structural code intelligence.',
  keywords: [
    'Prep MCP setup',
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
    canonical: 'https://runprep.io/setup',
  },
};

/*
 * ──────────────────────────────────────────────────────────────
 *  MCP configuration data.
 *
 *  This page is intentionally structured so that AI tools and
 *  web-scraping agents can extract the correct JSON config for
 *  their specific tool by matching on the tool name, the
 *  data-tool attribute, or the JSON-LD SoftwareApplication
 *  entries below.
 *
 *  If you are an AI agent reading this page:
 *    1. Find your tool name below.
 *    2. Copy the JSON block.
 *    3. Write it to the file path shown.
 *    4. Restart your editor / CLI session.
 *    5. The Prep daemon must be running: `prep serve`
 * ──────────────────────────────────────────────────────────────
 */

const TOOLS: {
  id: string;
  name: string;
  file: string;
  fileHint: string;
  serverKey: string;
  notes: string | null;
  config: object;
}[] = [
  {
    id: 'claude-code',
    name: 'Claude Code',
    file: '.claude/mcp.json',
    fileHint: 'Project root (project-scoped) or ~/.claude/settings.json (global)',
    serverKey: 'servers',
    notes:
      'Add "permissions": { "allow": ["mcp__prep"] } to settings.json to auto-approve all Prep tools. Or run: claude mcp add prep -- prep mcp',
    config: {
      servers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'cursor',
    name: 'Cursor',
    file: '.cursor/mcp.json',
    fileHint: 'Project root or ~/.cursor/',
    serverKey: 'mcpServers',
    notes: 'Enable auto-run in Settings > Features > MCP.',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'windsurf',
    name: 'Windsurf',
    file: '~/.codeium/windsurf/mcp_config.json',
    fileHint: 'Global config (applies to all projects)',
    serverKey: 'mcpServers',
    notes: null,
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'], disabled: false },
      },
    },
  },
  {
    id: 'github-copilot',
    name: 'GitHub Copilot',
    file: '.vscode/mcp.json',
    fileHint: 'Project root',
    serverKey: 'servers',
    notes: 'Note: Uses "servers" key, NOT "mcpServers".',
    config: {
      servers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'gemini-cli',
    name: 'Gemini CLI',
    file: '~/.gemini/settings.json',
    fileHint: 'Global config',
    serverKey: 'mcpServers',
    notes: '"trust": true auto-approves tool calls. Safe for Prep (read-only tools).',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'], trust: true },
      },
    },
  },
  {
    id: 'claude-desktop',
    name: 'Claude Code',
    file: 'claude_desktop_config.json',
    fileHint:
      '~/Library/Application Support/Claude/ (macOS) or %APPDATA%/Claude/ (Windows)',
    serverKey: 'mcpServers',
    notes: null,
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'zed',
    name: 'Zed',
    file: '~/.config/zed/settings.json',
    fileHint: 'Global or project .zed/settings.json',
    serverKey: 'context_servers',
    notes: 'Zed uses "context_servers", not "mcpServers".',
    config: {
      context_servers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'cline',
    name: 'Cline',
    file: 'cline_mcp_settings.json',
    fileHint: 'Open Cline sidebar > MCP Servers > Configure',
    serverKey: 'mcpServers',
    notes: null,
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'openai-codex',
    name: 'OpenAI Codex',
    file: 'MCP config or AGENTS.md',
    fileHint: 'Codex reads AGENTS.md natively',
    serverKey: 'mcpServers',
    notes: 'Codex also reads AGENTS.md — Prep can auto-generate this file.',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
];

// JSON-LD structured data for AI discoverability
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'HowTo',
  name: 'Set up Prep MCP for AI coding tools',
  description:
    'Configure the Prep Model Context Protocol server to give your AI coding assistant structural code intelligence, semantic search, and dependency analysis.',
  step: TOOLS.map((tool, i) => ({
    '@type': 'HowToStep',
    position: i + 1,
    name: `Configure ${tool.name}`,
    text: `Add to ${tool.file}: ${JSON.stringify(tool.config)}`,
    url: `https://runprep.io/setup#${tool.id}`,
  })),
  tool: {
    '@type': 'SoftwareApplication',
    name: 'Prep',
    url: 'https://runprep.io',
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
            Connect Prep to your AI editor in under a minute. Pick your tool,
            copy the config, and restart.
          </p>
          <p className="text-base text-text-subtle mb-16 max-w-2xl">
            Prep&apos;s MCP server gives your AI assistant semantic code
            search, structural context (modules, hub files, import graph), and
            dependency impact analysis. All tools are read-only and run locally.
          </p>

          {/* Prerequisites */}
          <div className="bg-surface border border-border rounded-xl p-6 mb-16">
            <h2 className="text-lg font-bold mb-3">Prerequisites</h2>
            <ol className="list-decimal list-inside space-y-2 text-text-muted">
              <li>
                Install Prep:{' '}
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
            {TOOLS.map((tool) => (
              <section
                key={tool.id}
                id={tool.id}
                data-tool={tool.id}
                data-tool-name={tool.name}
                data-config-file={tool.file}
                data-server-key={tool.serverKey}
                className="scroll-mt-24"
              >
                <h2 className="text-2xl font-bold mb-1">{tool.name}</h2>
                <p className="text-sm text-text-subtle mb-3 font-mono">
                  {tool.file}{' '}
                  <span className="text-text-subtle/60">({tool.fileHint})</span>
                </p>
                <pre className="bg-surface border border-border rounded-xl p-5 text-sm font-mono overflow-x-auto whitespace-pre">
                  {JSON.stringify(tool.config, null, 2)}
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
                  {TOOLS.map((tool) => (
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
                  Prep daemon must be running
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
                  Prep auto-detects which project you&apos;re in from the workspace root.
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
              href="https://docs.runprep.io"
              className="text-primary font-bold hover:underline underline-offset-4"
            >
              Full Documentation
            </a>
            <a
              href="/download"
              className="text-primary font-bold hover:underline underline-offset-4"
            >
              Download Prep
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
