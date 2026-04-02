export interface McpToolConfig {
  id: string;
  name: string;
  category: 'ide' | 'terminal';
  file: string;
  fileHint: string;
  serverKey: string;
  notes: string | null;
  config: object;
}

export const MCP_TOOLS: McpToolConfig[] = [
  // -- IDEs --
  {
    id: 'cursor',
    name: 'Cursor',
    category: 'ide',
    file: '.cursor/mcp.json',
    fileHint: 'Project root or ~/.cursor/',
    serverKey: 'mcpServers',
    notes: 'Enable auto-run in Settings > Features > MCP.',
    config: {
      mcpServers: {
        codrag: { command: 'codrag', args: ['mcp'] },
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
        codrag: { command: 'codrag', args: ['mcp'], disabled: false },
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
        codrag: { command: 'codrag', args: ['mcp'] },
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
        codrag: { command: 'codrag', args: ['mcp'] },
      },
    },
  },
  {
    id: 'cline',
    name: 'Cline',
    category: 'ide',
    file: 'cline_mcp_settings.json',
    fileHint: 'Open Cline sidebar > MCP Servers > Configure',
    serverKey: 'mcpServers',
    notes: null,
    config: {
      mcpServers: {
        codrag: { command: 'codrag', args: ['mcp'] },
      },
    },
  },

  // -- TERMINALS & CLIs --
  {
    id: 'claude-code',
    name: 'Claude Code',
    category: 'terminal',
    file: '.claude/mcp.json',
    fileHint: 'Project root (project-scoped) or ~/.claude/settings.json (global)',
    serverKey: 'servers',
    notes: 'Add "permissions": { "allow": ["mcp__codrag"] } to settings.json to auto-approve all CoDRAG tools. Or run: claude mcp add codrag -- codrag mcp',
    config: {
      servers: {
        codrag: { command: 'codrag', args: ['mcp'] },
      },
    },
  },
  {
    id: 'gemini-cli',
    name: 'Gemini CLI',
    category: 'terminal',
    file: '~/.gemini/settings.json',
    fileHint: 'Global config',
    serverKey: 'mcpServers',
    notes: '"trust": true auto-approves tool calls. Safe for CoDRAG (read-only tools).',
    config: {
      mcpServers: {
        codrag: { command: 'codrag', args: ['mcp'], trust: true },
      },
    },
  },
  {
    id: 'openai-codex',
    name: 'OpenAI Codex',
    category: 'terminal',
    file: 'MCP config or AGENTS.md',
    fileHint: 'Codex reads AGENTS.md natively',
    serverKey: 'mcpServers',
    notes: 'Codex also reads AGENTS.md — CoDRAG can auto-generate this file.',
    config: {
      mcpServers: {
        codrag: { command: 'codrag', args: ['mcp'] },
      },
    },
  },
];
