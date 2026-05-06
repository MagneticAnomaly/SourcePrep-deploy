/**
 * Thin re-export shim. The canonical MCP setup registry lives in
 * `@prep/ui` (packages/ui/src/config/mcpSetup.ts) so marketing and
 * docs surfaces share one source of truth. Existing imports against
 * this path keep working.
 */

export { MCP_TOOLS, MCP_CLI_TOOLS, MCP_IDE_TOOLS, getMcpTool, mcpConfigAsString } from '@prep/ui';
export type { McpToolConfig, McpCategory } from '@prep/ui';
