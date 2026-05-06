/**
 * Canonical MCP setup registry — single source of truth for
 * SourcePrep's MCP integration JSON across every public surface
 * (marketing /setup, marketing /download, docs /mcp/ides, docs /mcp/terminal).
 *
 * Ordering reflects the proposed integration taxonomy:
 *   CLIs — Claude Code primary, then Codex, then Gemini CLI
 *   IDEs — Cursor primary, then Windsurf, Antigravity, GitHub Copilot, Zed, Cline
 *
 * If you're adding a new integration, this is the only place to edit.
 */

export type McpCategory = 'cli' | 'ide';

export interface McpToolConfig {
  /** URL/anchor slug. Stable; used as the per-tool fragment id on /setup. */
  id: string;
  /** Human-readable display name. */
  name: string;
  /** CLI agent vs IDE — drives which list/tab a tool appears in. */
  category: McpCategory;
  /** Where the user puts the JSON. */
  file: string;
  /** Extra hint about what `file` actually means (project root vs global, etc.). */
  fileHint: string;
  /** Top-level key inside the JSON file (mcpServers / servers / context_servers). */
  serverKey: string;
  /** Optional caveat or permission/auto-approve note shown next to the config. */
  notes: string | null;
  /** True if this is the primary target for its category — drives "Primary" badge. */
  primary?: boolean;
  /** The actual JSON snippet, as a real object so callers can JSON.stringify with their preferred indent. */
  config: object;
}

export const MCP_TOOLS: McpToolConfig[] = [
  // ── CLI agents ────────────────────────────────────────────────────────
  {
    id: 'claude-code',
    name: 'Claude Code',
    category: 'cli',
    primary: true,
    file: '.claude/mcp.json',
    fileHint: 'Project root (project-scoped) or ~/.claude/settings.json (global)',
    serverKey: 'servers',
    notes:
      'Add "permissions": { "allow": ["mcp__prep"] } to settings.json to auto-approve all SourcePrep tools. Or run: claude mcp add prep -- prep mcp. Same JSON works for Claude Desktop — drop it into ~/Library/Application Support/Claude/claude_desktop_config.json (macOS) or %APPDATA%/Claude/ (Windows) under "mcpServers" instead of "servers".',
    config: {
      servers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'openai-codex',
    name: 'OpenAI Codex',
    category: 'cli',
    file: 'MCP config or AGENTS.md',
    fileHint: 'Codex reads AGENTS.md natively',
    serverKey: 'mcpServers',
    notes: 'Codex also reads AGENTS.md — SourcePrep can auto-generate this file.',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'gemini-cli',
    name: 'Gemini CLI',
    category: 'cli',
    file: '~/.gemini/settings.json',
    fileHint: 'Global config',
    serverKey: 'mcpServers',
    notes: '"trust": true auto-approves tool calls. Safe for SourcePrep (read-only tools).',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'], trust: true },
      },
    },
  },

  // ── Agentic IDEs ──────────────────────────────────────────────────────
  {
    id: 'cursor',
    name: 'Cursor',
    category: 'ide',
    primary: true,
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
    category: 'ide',
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
    id: 'antigravity',
    name: 'Antigravity',
    category: 'ide',
    file: '~/.gemini/antigravity/mcp_config.json',
    fileHint: 'Global Antigravity config (Google)',
    serverKey: 'mcpServers',
    notes: 'Google Antigravity uses a Gemini-style nested config under ~/.gemini/antigravity/.',
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
  {
    id: 'github-copilot',
    name: 'GitHub Copilot',
    category: 'ide',
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
    id: 'zed',
    name: 'Zed',
    category: 'ide',
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
    category: 'ide',
    file: 'cline_mcp_settings.json',
    fileHint: 'Open Cline sidebar > MCP Servers > Configure (VS Code extension)',
    serverKey: 'mcpServers',
    notes: null,
    config: {
      mcpServers: {
        prep: { command: 'prep', args: ['mcp'] },
      },
    },
  },
];

/** Convenience filters used by docs/mcp pages and marketing surfaces. */
export const MCP_CLI_TOOLS = MCP_TOOLS.filter((t) => t.category === 'cli');
export const MCP_IDE_TOOLS = MCP_TOOLS.filter((t) => t.category === 'ide');

/** Lookup helper. */
export function getMcpTool(id: string): McpToolConfig | undefined {
  return MCP_TOOLS.find((t) => t.id === id);
}

/** Format a tool's `config` object as a pretty-printed JSON string for display. */
export function mcpConfigAsString(tool: McpToolConfig, indent = 2): string {
  return JSON.stringify(tool.config, null, indent);
}
