/**
 * Canonical MCP tool registry — single source of truth for the
 * SourcePrep tool list across every public surface (dashboard
 * Quick Start, docs `/mcp`, marketing pages, AI-SEO crawl targets).
 *
 * This file describes the *tools the AI agent can call* (prep,
 * prep_search, prep_impact, …). It is distinct from `mcpSetup.ts`,
 * which describes the *IDE config snippets* (Claude Code, Cursor,
 * VS Code, …) needed to wire the MCP server into each runtime.
 *
 * Adding a tool: edit this file. Everywhere else picks it up.
 */

export type McpToolCategory = 'context' | 'index' | 'graph';

export interface McpToolEntry {
  /** Tool name as called from the AI agent. */
  name: string;
  /** End-user blurb (1 sentence). Different audience from the
   *  MCP tools/list description (which is written for the AI). */
  description: string;
  /** Suggested invocation prompt to copy/paste. */
  example: string;
  /** Surface grouping for the docs/dashboard sections. */
  category: McpToolCategory;
  /** Primary tools render as featured cards; the rest go in the list. */
  primary?: boolean;
  /** Optional badge label shown next to primary tools. */
  badge?: string;
}

export const MCP_TOOL_LIST: McpToolEntry[] = [
  // ── Context & Search ────────────────────────────────────────────
  {
    name: 'prep',
    description:
      'Get assembled context from your selected files, code graph, and atlas routing — the primary tool your AI uses.',
    example: '"Use prep to understand this codebase"',
    category: 'context',
    primary: true,
    badge: 'Most used',
  },
  {
    name: 'hi_prep',
    description:
      'See what SourcePrep knows about your selected files — design docs, code areas, connections, and suggested next steps. Best first step.',
    example: '"hi_prep" — select files in Knowledge Sources first, then ask your AI',
    category: 'context',
    primary: true,
    badge: 'Start here',
  },
  {
    name: 'prep_search',
    description: 'Semantic search across your indexed code and docs.',
    example: '"Use prep_search to find authentication logic"',
    category: 'context',
  },

  // ── Index Management ────────────────────────────────────────────
  {
    name: 'prep_status',
    description: 'Check if SourcePrep is connected and the index is ready.',
    example: '"Use prep_status to check the index"',
    category: 'index',
  },
  {
    name: 'prep_build',
    description: 'Trigger an index rebuild when your code has changed.',
    example: '"Use prep_build to re-index the project"',
    category: 'index',
  },

  // ── Code Graph ──────────────────────────────────────────────────
  {
    name: 'prep_trace_search',
    description: 'Search the structural code graph for symbols (functions, classes, modules).',
    example: '"Use prep_trace_search to find the UserService class"',
    category: 'graph',
  },
  {
    name: 'prep_trace_neighbors',
    description: 'Explore imports, callers, and callees of a symbol in the code graph.',
    example: '"Use prep_trace_neighbors to see what calls handleAuth"',
    category: 'graph',
  },
  {
    name: 'prep_trace_coverage',
    description: 'Check which files are traced, stale, or missing from the code graph.',
    example: '"Use prep_trace_coverage to check graph completeness"',
    category: 'graph',
  },
];

export const MCP_TOOL_CATEGORY_LABELS: Record<McpToolCategory, string> = {
  context: 'Context & Search',
  index: 'Index Management',
  graph: 'Code Graph',
};

/** Convenience filter for the featured-card row in dashboard / docs. */
export const MCP_PRIMARY_TOOLS = MCP_TOOL_LIST.filter((t) => t.primary);
export const MCP_SECONDARY_TOOLS = MCP_TOOL_LIST.filter((t) => !t.primary);

/** Lookup helper. */
export function getMcpToolEntry(name: string): McpToolEntry | undefined {
  return MCP_TOOL_LIST.find((t) => t.name === name);
}
