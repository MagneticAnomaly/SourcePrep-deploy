/**
 * McpSnippetCard — copy-paste MCP config JSON, picker-driven.
 *
 * Single source of truth is `mcpSetup.ts` (MCP_TOOLS). For each IDE
 * we either render the static snippet from that registry directly OR
 * fetch a daemon-resolved version (so the `command` is the actual
 * absolute path to `prep`, not the bare name).
 *
 * No auto-install. No status check. Just JSON to copy.
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Copy, Check } from 'lucide-react';
import { MCP_TOOLS, mcpConfigAsString, type McpToolConfig } from '../../config/mcpSetup';

export interface McpSnippetCardProps {
  /**
   * Optional async resolver — given an IDE id, returns the file path
   * and JSON config to render. Lets the dashboard inject a daemon-
   * resolved version (with absolute `prep` command). When omitted,
   * the static MCP_TOOLS registry is used as-is.
   */
  resolveConfig?: (
    ideId: string,
  ) => Promise<{ file: string; path_hint?: string; config: object } | null>;
  /** Pre-select an IDE by id. Defaults to the first primary entry. */
  defaultIdeId?: string;
  className?: string;
}

interface ResolvedSnippet {
  file: string;
  pathHint: string;
  json: string;
}

function buildStaticSnippet(tool: McpToolConfig): ResolvedSnippet {
  return {
    file: tool.file,
    pathHint: tool.fileHint,
    json: mcpConfigAsString(tool),
  };
}

export function McpSnippetCard({
  resolveConfig,
  defaultIdeId,
  className = '',
}: McpSnippetCardProps) {
  const initialId = useMemo(
    () =>
      defaultIdeId ??
      MCP_TOOLS.find((t) => t.primary && t.category === 'cli')?.id ??
      MCP_TOOLS[0].id,
    [defaultIdeId],
  );
  const [ideId, setIdeId] = useState(initialId);
  const [snippet, setSnippet] = useState<ResolvedSnippet>(() =>
    buildStaticSnippet(MCP_TOOLS.find((t) => t.id === initialId) ?? MCP_TOOLS[0]),
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const tool = MCP_TOOLS.find((t) => t.id === ideId);
    if (!tool) return;
    // Show the static snippet immediately so the box never flickers
    // to empty; if a resolver is provided, replace with the resolved
    // version when it arrives.
    setSnippet(buildStaticSnippet(tool));
    if (!resolveConfig) return;
    let cancelled = false;
    void resolveConfig(ideId).then((res) => {
      if (cancelled || !res) return;
      setSnippet({
        file: res.file,
        pathHint: res.path_hint ?? tool.fileHint,
        json: JSON.stringify(res.config, null, 2),
      });
    });
    return () => {
      cancelled = true;
    };
  }, [ideId, resolveConfig]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(snippet.json).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [snippet.json]);

  const cliTools = MCP_TOOLS.filter((t) => t.category === 'cli');
  const ideTools = MCP_TOOLS.filter((t) => t.category === 'ide');

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center gap-2">
        <label htmlFor="mcp-ide-select" className="text-xs text-text-muted">
          For:
        </label>
        <select
          id="mcp-ide-select"
          value={ideId}
          onChange={(e) => setIdeId(e.target.value)}
          className="text-xs px-2 py-1 rounded-md border border-border bg-background"
        >
          <optgroup label="CLI agents">
            {cliTools.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="IDEs">
            {ideTools.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      <div className="text-xs">
        <div className="font-mono text-text">{snippet.file}</div>
        <div className="text-text-muted/70 italic">{snippet.pathHint}</div>
      </div>

      <div className="relative">
        <pre className="text-xs font-mono bg-muted/50 rounded-md p-3 overflow-x-auto border border-border/50 max-h-64">
          {snippet.json}
        </pre>
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 p-1.5 rounded bg-background/80 hover:bg-background border border-border/50 transition-colors"
          title="Copy to clipboard"
        >
          {copied ? (
            <Check size={12} className="text-green-500" />
          ) : (
            <Copy size={12} className="text-text-muted" />
          )}
        </button>
      </div>
    </div>
  );
}
