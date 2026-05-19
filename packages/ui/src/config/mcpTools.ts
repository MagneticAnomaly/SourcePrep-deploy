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
 * MUST stay aligned with the production tool registry in
 * `src/prep/mcp_tools.py` (`_CORE_TOOLS`). If you add or remove a
 * tool there, update this list to match.
 */

export type McpToolCategory = 'context' | 'impact' | 'knowledge';

export interface McpToolEntry {
  /** Tool name as called from the AI agent. */
  name: string;
  /** End-user blurb (1–2 sentences). Different audience from the
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
      'Structural overview of the codebase — modules, hub files, focus areas, immune-system alerts. Call this first at the start of any task.',
    example: '"Use prep to understand this codebase"',
    category: 'context',
    primary: true,
    badge: 'Start here',
  },
  {
    name: 'prep_search',
    description:
      'Find code by meaning, not just string match. Auto-classifies intent: "where is X" routes to symbol lookup, "why X" to concepts, "who imports X" to graph traversal.',
    example: '"Use prep_search to find authentication logic"',
    category: 'context',
    primary: true,
    badge: 'Most used',
  },

  // ── Impact & Audit ──────────────────────────────────────────────
  {
    name: 'prep_impact',
    description:
      'Show what depends on a file or symbol — the blast radius if you change it. Call before editing hub files.',
    example: '"Use prep_impact on src/auth.py before refactoring"',
    category: 'impact',
  },
  {
    name: 'prep_audit',
    description:
      'Codebase health findings — coupling hotspots, import cycles, concept violations. Also enriches external lint findings (ruff, eslint, SARIF) with structural context.',
    example: '"Use prep_audit to find coupling issues"',
    category: 'impact',
  },

  // ── Cross-Session Knowledge ─────────────────────────────────────
  {
    name: 'prep_observe',
    description:
      'Save or retrieve cross-session notes anchored to specific files. Notes mark stale when their anchors change.',
    example: '"Use prep_observe to record why we picked this approach"',
    category: 'knowledge',
  },
  {
    name: 'prep_concepts',
    description:
      'Record and query business rationale, design decisions, and architectural constraints. Concepts with constraint assertions become runtime immune-system defenses.',
    example: '"Use prep_concepts to see why auth was rewritten"',
    category: 'knowledge',
  },
];

export const MCP_TOOL_CATEGORY_LABELS: Record<McpToolCategory, string> = {
  context: 'Context & Search',
  impact: 'Impact & Audit',
  knowledge: 'Cross-Session Knowledge',
};

/** Convenience filter for the featured-card row in dashboard / docs. */
export const MCP_PRIMARY_TOOLS = MCP_TOOL_LIST.filter((t) => t.primary);
export const MCP_SECONDARY_TOOLS = MCP_TOOL_LIST.filter((t) => !t.primary);

/** Lookup helper. */
export function getMcpToolEntry(name: string): McpToolEntry | undefined {
  return MCP_TOOL_LIST.find((t) => t.name === name);
}
