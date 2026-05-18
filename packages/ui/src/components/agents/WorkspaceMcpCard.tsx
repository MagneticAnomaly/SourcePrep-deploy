/**
 * WorkspaceMcpCard — "Enable Prep for Workspace" one-click UI.
 *
 * Writes per-IDE MCP config files (.claude/mcp.json, .cursor/mcp.json,
 * .vscode/mcp.json, .windsurf/mcp.json) into an arbitrary workspace so
 * AI agents running there discover Prep tools without manual setup.
 *
 * Talks to POST /mcp/install, POST /mcp/uninstall, GET /mcp/status.
 */
import { useState, useCallback, useEffect } from 'react';
import { FolderPlus, Check, Circle, X } from 'lucide-react';

export interface WorkspaceRuntimeStatus {
  installed: boolean;
  file: string;
  config?: Record<string, unknown>;
  error?: string;
}

export interface WorkspaceMcpStatusData {
  daemon_url: string;
  mcp_command: string;
  supported_runtimes: string[];
  workspace?: string;
  runtimes?: Record<string, WorkspaceRuntimeStatus>;
  any_installed?: boolean;
}

export interface WorkspaceMcpInstallResult {
  workspace: string;
  written: string[];
  skipped: Array<{ runtime: string; reason: string }>;
  runtimes_installed: number;
}

export interface WorkspaceMcpCardProps {
  /** Default workspace path to pre-fill (typically the selected project root). */
  defaultWorkspacePath?: string | null;
  /** Per-workspace status from GET /mcp/status?workspace_path=... */
  status: WorkspaceMcpStatusData | null;
  /** POST /mcp/install for the given path */
  onInstall?: (workspacePath: string) => Promise<WorkspaceMcpInstallResult>;
  /** POST /mcp/uninstall for the given path */
  onUninstall?: (workspacePath: string) => Promise<void>;
  /** Refresh status for the current path */
  onRefresh?: (workspacePath: string) => void;
  className?: string;
}

export function WorkspaceMcpCard({
  defaultWorkspacePath,
  status,
  onInstall,
  onUninstall,
  onRefresh,
  className = '',
}: WorkspaceMcpCardProps) {
  const [path, setPath] = useState(defaultWorkspacePath ?? '');
  const [busy, setBusy] = useState<'install' | 'uninstall' | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Keep the input in sync if the selected project changes upstream.
  useEffect(() => {
    if (defaultWorkspacePath && !path) setPath(defaultWorkspacePath);
  }, [defaultWorkspacePath, path]);

  // Refresh status whenever the path changes to a non-empty value.
  useEffect(() => {
    if (path && onRefresh) onRefresh(path);
  }, [path, onRefresh]);

  const handleInstall = useCallback(async () => {
    if (!onInstall || !path) return;
    setBusy('install');
    setMessage(null);
    try {
      const result = await onInstall(path);
      setMessage(`Installed in ${result.runtimes_installed} runtime${result.runtimes_installed === 1 ? '' : 's'}`);
      onRefresh?.(path);
    } catch {
      setMessage('Install failed');
    } finally {
      setBusy(null);
    }
  }, [onInstall, onRefresh, path]);

  const handleUninstall = useCallback(async () => {
    if (!onUninstall || !path) return;
    setBusy('uninstall');
    setMessage(null);
    try {
      await onUninstall(path);
      setMessage('Removed from workspace');
      onRefresh?.(path);
    } catch {
      setMessage('Uninstall failed');
    } finally {
      setBusy(null);
    }
  }, [onUninstall, onRefresh, path]);

  const anyInstalled = status?.any_installed ?? false;
  const runtimeEntries = status?.runtimes ? Object.entries(status.runtimes) : [];

  return (
    <div className={`rounded-lg border border-border bg-surface/50 ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <FolderPlus size={14} className="text-primary" />
          <h4 className="font-medium text-sm">Enable Prep for Workspace</h4>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              anyInstalled ? 'bg-green-500' : status ? 'bg-amber-500' : 'bg-zinc-400'
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {anyInstalled ? 'Installed' : status ? 'Not installed' : 'Idle'}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <p className="text-xs text-muted-foreground">
          Write MCP config files into a project directory so any AI agent running
          there (Claude Code, Cursor, VS Code, Windsurf) discovers Prep tools.
        </p>

        <input
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/absolute/path/to/workspace"
          className="w-full text-xs font-mono px-2 py-1.5 rounded-md border border-border bg-background"
        />

        <div className="flex items-center gap-2">
          <button
            onClick={handleInstall}
            disabled={busy !== null || !path || !onInstall}
            className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 font-medium"
          >
            {busy === 'install' ? 'Installing…' : 'Enable in workspace'}
          </button>
          {anyInstalled && (
            <button
              onClick={handleUninstall}
              disabled={busy !== null || !path || !onUninstall}
              className="text-xs text-red-500/70 hover:text-red-500 transition-colors disabled:opacity-50"
            >
              {busy === 'uninstall' ? 'Removing…' : 'Remove'}
            </button>
          )}
        </div>

        {runtimeEntries.length > 0 && (
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            {runtimeEntries.map(([runtime, rt]) => (
              <div key={runtime} className="flex items-center gap-1.5 text-xs">
                {rt.installed ? (
                  <Check size={12} className="text-green-500 shrink-0" />
                ) : rt.error ? (
                  <X size={12} className="text-red-500/70 shrink-0" />
                ) : (
                  <Circle size={12} className="text-muted-foreground shrink-0" />
                )}
                <span className="text-muted-foreground truncate" title={rt.file}>
                  {runtime}
                </span>
              </div>
            ))}
          </div>
        )}

        {message && <div className="text-xs text-muted-foreground italic">{message}</div>}
      </div>
    </div>
  );
}
