/**
 * MCPConnectionCard — "Enable CoDRAG for Workspace" one-click UI.
 *
 * Displays MCP server status, which runtimes have CoDRAG installed,
 * and provides the one-click install/uninstall action.
 */
import { useState, useCallback } from 'react';
import { Plug, Check, Circle, Copy, ChevronDown, ChevronUp, X } from 'lucide-react';

export interface MCPRuntimeStatus {
  installed: boolean;
  file: string;
  config?: Record<string, unknown>;
  error?: string;
}

export interface MCPStatusData {
  daemon_url: string;
  mcp_command: string;
  supported_runtimes: string[];
  workspace?: string;
  runtimes?: Record<string, MCPRuntimeStatus>;
  any_installed?: boolean;
}

export interface MCPInstallResult {
  workspace: string;
  written: string[];
  skipped: Array<{ runtime: string; reason: string }>;
  runtimes_installed: number;
}

export interface MCPConnectionCardProps {
  /** Workspace path to install MCP configs into */
  workspacePath?: string;
  /** Current status data (from GET /mcp/status) */
  status: MCPStatusData | null;
  /** Loading state */
  loading?: boolean;
  /** Call POST /mcp/install */
  onInstall?: (workspacePath: string) => Promise<MCPInstallResult>;
  /** Call POST /mcp/uninstall */
  onUninstall?: (workspacePath: string) => Promise<void>;
  /** Refresh status */
  onRefresh?: () => void;
  className?: string;
}

const RUNTIME_LABELS: Record<string, string> = {
  'claude-code': 'Claude Code',
  cursor: 'Cursor',
  vscode: 'VS Code',
  windsurf: 'Windsurf',
};

export function MCPConnectionCard({
  workspacePath,
  status,
  loading: _loading = false,
  onInstall,
  onUninstall,
  onRefresh,
  className = '',
}: MCPConnectionCardProps) {
  const [installing, setInstalling] = useState(false);
  const [uninstalling, setUninstalling] = useState(false);
  const [lastResult, setLastResult] = useState<MCPInstallResult | null>(null);
  const [showSnippet, setShowSnippet] = useState(false);
  const [copied, setCopied] = useState(false);

  const anyInstalled = status?.any_installed ?? false;
  const runtimes = status?.runtimes ?? {};

  const handleInstall = useCallback(async () => {
    if (!onInstall || !workspacePath) return;
    setInstalling(true);
    try {
      const result = await onInstall(workspacePath);
      setLastResult(result);
      onRefresh?.();
    } catch {
      // Error handled by caller
    } finally {
      setInstalling(false);
    }
  }, [onInstall, workspacePath, onRefresh]);

  const handleUninstall = useCallback(async () => {
    if (!onUninstall || !workspacePath) return;
    setUninstalling(true);
    try {
      await onUninstall(workspacePath);
      setLastResult(null);
      onRefresh?.();
    } catch {
      // Error handled by caller
    } finally {
      setUninstalling(false);
    }
  }, [onUninstall, workspacePath, onRefresh]);

  const snippet = JSON.stringify(
    {
      servers: {
        codrag: {
          command: 'codrag',
          args: ['mcp', '--auto', '--daemon', status?.daemon_url ?? 'http://127.0.0.1:8400'],
        },
      },
    },
    null,
    2
  );

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [snippet]);

  return (
    <div className={`rounded-lg border border-border bg-surface/50 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Plug size={14} className="text-primary" />
          <h4 className="font-medium text-sm">MCP Connection</h4>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              status ? 'bg-green-500 animate-pulse' : 'bg-zinc-400'
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {status ? 'Server Running' : 'Checking...'}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Workspace + install button */}
        {workspacePath ? (
          <>
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-xs text-muted-foreground mb-0.5">Workspace</div>
                <div className="text-xs font-mono text-foreground truncate" title={workspacePath}>
                  {workspacePath}
                </div>
              </div>
              {anyInstalled ? (
                <button
                  onClick={handleUninstall}
                  disabled={uninstalling}
                  className="shrink-0 text-xs px-3 py-1.5 rounded-md border border-red-500/30 text-red-500 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                >
                  {uninstalling ? 'Removing...' : 'Remove'}
                </button>
              ) : (
                <button
                  onClick={handleInstall}
                  disabled={installing || !onInstall}
                  className="shrink-0 text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 font-medium"
                >
                  {installing ? 'Installing...' : 'Enable CoDRAG'}
                </button>
              )}
            </div>

            {/* Runtime status badges */}
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(RUNTIME_LABELS).map(([key, label]) => {
                const rt = runtimes[key];
                const installed = rt?.installed ?? false;
                return (
                  <span
                    key={key}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
                      installed
                        ? 'bg-green-500/10 text-green-700 dark:text-green-400'
                        : 'bg-zinc-500/10 text-zinc-500 dark:text-zinc-400'
                    }`}
                    title={installed ? `Installed: ${rt?.file}` : 'Not installed'}
                  >
                    {installed ? (
                      <Check size={10} className="text-green-500" />
                    ) : (
                      <Circle size={10} />
                    )}
                    {label}
                  </span>
                );
              })}
            </div>
          </>
        ) : (
          <div className="text-xs text-muted-foreground italic">
            Select a project to enable MCP for its workspace
          </div>
        )}

        {/* Success feedback */}
        {lastResult && lastResult.runtimes_installed > 0 && (
          <div className="flex items-start gap-2 rounded-md bg-green-500/10 border border-green-500/20 px-3 py-2">
            <Check size={14} className="text-green-500 mt-0.5 shrink-0" />
            <div className="text-xs text-green-700 dark:text-green-400">
              CoDRAG enabled for {lastResult.runtimes_installed} runtime
              {lastResult.runtimes_installed !== 1 ? 's' : ''}. Agents will discover CoDRAG
              tools on next heartbeat.
            </div>
            <button
              onClick={() => setLastResult(null)}
              className="ml-auto shrink-0 text-green-500/50 hover:text-green-500"
            >
              <X size={12} />
            </button>
          </div>
        )}

        {/* Manual snippet toggle */}
        <button
          onClick={() => setShowSnippet(!showSnippet)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {showSnippet ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          Manual config
        </button>

        {showSnippet && (
          <div className="relative">
            <pre className="text-xs font-mono bg-muted/50 rounded-md p-3 overflow-x-auto border border-border/50">
              {snippet}
            </pre>
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 p-1 rounded bg-muted hover:bg-muted-foreground/20 transition-colors"
              title="Copy to clipboard"
            >
              {copied ? (
                <Check size={12} className="text-green-500" />
              ) : (
                <Copy size={12} className="text-muted-foreground" />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
