/**
 * MCPConnectionCard — Paperclip Skill integration status.
 *
 * Shows whether the CoDRAG skill is installed globally in
 * ~/.claude/skills/codrag so Paperclip agents can use it.
 * Provides one-click install/uninstall and a manual snippet.
 */
import { useState, useCallback } from 'react';
import { Plug, Check, Copy, ChevronDown, ChevronUp } from 'lucide-react';

export interface MCPRuntimeStatus {
  installed: boolean;
  file: string;
  config?: Record<string, unknown>;
  error?: string;
}

export interface MCPStatusData {
  daemon_url: string;
  installed: boolean;
  path: string;
  skills_home: string;
  mode?: 'symlink' | 'copy';
  source?: string;
}

export interface MCPInstallResult {
  installed: boolean;
  path: string;
  mode: string;
  message: string;
}

export interface MCPConnectionCardProps {
  /** Skill status data (from GET /paperclip/skill-status) */
  status: MCPStatusData | null;
  /** Loading state */
  loading?: boolean;
  /** Call POST /paperclip/install-skill */
  onInstall?: () => Promise<MCPInstallResult>;
  /** Call POST /paperclip/uninstall-skill */
  onUninstall?: () => Promise<void>;
  /** Refresh status */
  onRefresh?: () => void;
  className?: string;
}

export function MCPConnectionCard({
  status,
  loading: _loading = false,
  onInstall,
  onUninstall,
  onRefresh,
  className = '',
}: MCPConnectionCardProps) {
  const [installing, setInstalling] = useState(false);
  const [uninstalling, setUninstalling] = useState(false);
  const [showSnippet, setShowSnippet] = useState(false);
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const installed = status?.installed ?? false;

  const handleInstall = useCallback(async () => {
    if (!onInstall) return;
    setInstalling(true);
    setMessage(null);
    try {
      const result = await onInstall();
      setMessage(result.message);
      onRefresh?.();
    } catch {
      setMessage('Installation failed');
    } finally {
      setInstalling(false);
    }
  }, [onInstall, onRefresh]);

  const handleUninstall = useCallback(async () => {
    if (!onUninstall) return;
    setUninstalling(true);
    setMessage(null);
    try {
      await onUninstall();
      setMessage('Skill removed');
      onRefresh?.();
    } catch {
      setMessage('Removal failed');
    } finally {
      setUninstalling(false);
    }
  }, [onUninstall, onRefresh]);

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
    2,
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
          <h4 className="font-medium text-sm">Paperclip Integration</h4>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              installed
                ? 'bg-green-500'
                : status
                  ? 'bg-amber-500'
                  : 'bg-zinc-400'
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {installed ? 'Skill Installed' : status ? 'Not Installed' : 'Checking...'}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {installed ? (
          /* ── Installed state ── */
          <>
            <div className="flex items-start gap-2 rounded-md bg-green-500/10 border border-green-500/20 px-3 py-2.5">
              <Check size={14} className="text-green-500 mt-0.5 shrink-0" />
              <div className="text-xs text-green-700 dark:text-green-400 space-y-1">
                <p className="font-medium">
                  CoDRAG skill is installed globally
                </p>
                <p>
                  Enable the <code className="bg-green-500/10 px-1 rounded">codrag</code> skill
                  on any agent in Paperclip → Agent → Skills tab.
                </p>
              </div>
            </div>

            {status?.mode && (
              <div className="text-xs text-muted-foreground">
                <span className="font-medium">Mode:</span>{' '}
                {status.mode === 'symlink' ? 'Linked to repo (auto-updates)' : 'Standalone copy'}
                {status.path && (
                  <>
                    {' · '}
                    <span className="font-mono">{status.path}</span>
                  </>
                )}
              </div>
            )}

            <button
              onClick={handleUninstall}
              disabled={uninstalling}
              className="text-xs text-red-500/70 hover:text-red-500 transition-colors disabled:opacity-50"
            >
              {uninstalling ? 'Removing...' : 'Remove skill'}
            </button>
          </>
        ) : (
          /* ── Not installed state ── */
          <>
            <p className="text-xs text-muted-foreground">
              Install the CoDRAG skill so Paperclip agents can use structural
              codebase intelligence tools (<code className="bg-muted px-1 rounded">codrag</code>,{' '}
              <code className="bg-muted px-1 rounded">codrag_search</code>,{' '}
              <code className="bg-muted px-1 rounded">codrag_impact</code>).
            </p>

            <button
              onClick={handleInstall}
              disabled={installing || !onInstall}
              className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 font-medium"
            >
              {installing ? 'Installing...' : 'Install Paperclip Skill'}
            </button>
          </>
        )}

        {/* Feedback message */}
        {message && (
          <div className="text-xs text-muted-foreground italic">
            {message}
          </div>
        )}

        {/* Manual MCP snippet toggle */}
        <div className="border-t border-border/50 pt-2">
          <button
            onClick={() => setShowSnippet(!showSnippet)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showSnippet ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            Manual MCP config
          </button>

          {showSnippet && (
            <div className="relative mt-2">
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
    </div>
  );
}
