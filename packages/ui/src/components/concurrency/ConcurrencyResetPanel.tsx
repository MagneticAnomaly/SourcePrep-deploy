import { useState } from 'react';
import { Wrench, Check, AlertCircle } from 'lucide-react';
import { ConfirmDialog } from '../primitives/ConfirmDialog';
import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';

/**
 * Phase 119 Task 16 — Developer-mode reset for the discovered concurrency
 * ceiling. Surfaces a small wrench icon in the AI Gateway header. Opens an
 * inline panel listing each `cloud:*` node with a single-click "Reset" that
 * POSTs `/compute/concurrency/clear?node_id=...`.
 *
 * Treated as a power-user control: the wrench icon is intentionally
 * unobtrusive, and the action is gated by a {@link ConfirmDialog} that
 * spells out the consequence (AIMD re-probes from the Phase 82 jumpstart;
 * throughput may briefly drop while it climbs back).
 */
export interface ConcurrencyResetPanelProps {
  /** Active scheduler nodes — only entries with id `cloud:*` get a reset row. */
  cloudNodeIds: string[];
  /** Base URL for the SourcePrep daemon (e.g. `http://localhost:8400`). */
  baseUrl: string;
  className?: string;
}

type ResetStatus =
  | { state: 'idle' }
  | { state: 'pending'; nodeId: string }
  | { state: 'success'; nodeId: string; at: number }
  | { state: 'error'; nodeId: string; message: string };

export function ConcurrencyResetPanel({
  cloudNodeIds,
  baseUrl,
  className,
}: ConcurrencyResetPanelProps) {
  const [open, setOpen] = useState(false);
  const [pendingNode, setPendingNode] = useState<string | null>(null);
  const [status, setStatus] = useState<ResetStatus>({ state: 'idle' });

  const root = baseUrl.replace(/\/$/, '');

  const performReset = async (nodeId: string) => {
    setStatus({ state: 'pending', nodeId });
    try {
      const res = await fetch(
        `${root}/compute/concurrency/clear?node_id=${encodeURIComponent(nodeId)}`,
        { method: 'POST' },
      );
      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}${body ? `: ${body.slice(0, 120)}` : ''}`);
      }
      setStatus({ state: 'success', nodeId, at: Date.now() });
    } catch (e: any) {
      setStatus({
        state: 'error',
        nodeId,
        message: e?.message ?? 'reset failed',
      });
    }
  };

  return (
    <div className={cn('space-y-2', className)} data-testid="concurrency-reset-panel">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'inline-flex items-center gap-1.5 text-[10px] text-text-muted hover:text-text transition-colors',
          'rounded px-1.5 py-0.5 hover:bg-surface-raised',
          open && 'text-text bg-surface-raised',
        )}
        title="Developer: reset discovered concurrency ceiling"
        data-testid="concurrency-reset-toggle"
        aria-expanded={open}
      >
        <Wrench className="w-3 h-3" />
        Developer
      </button>

      {open && (
        <div
          className="rounded-md border border-border bg-surface-raised/50 p-3 space-y-2 animate-in fade-in slide-in-from-top-1 duration-150"
          data-testid="concurrency-reset-popover"
        >
          <div className="text-[11px] text-text-muted leading-relaxed">
            <span className="font-medium text-text">Reset discovered concurrency ceiling.</span>{' '}
            Forces SourcePrep to re-probe and rediscover the cloud LLM concurrency
            limit for an endpoint. Use after upgrading an Ollama Cloud plan or
            swapping endpoints.
          </div>

          {cloudNodeIds.length === 0 ? (
            <div className="text-[11px] text-text-muted italic">
              No cloud compute nodes are currently active. Reset is only meaningful for{' '}
              <code className="text-[10px] font-mono">cloud:*</code> nodes.
            </div>
          ) : (
            <div className="space-y-1.5">
              {cloudNodeIds.map((nid) => {
                const isPending = status.state === 'pending' && status.nodeId === nid;
                const isSuccess = status.state === 'success' && status.nodeId === nid;
                const isError = status.state === 'error' && status.nodeId === nid;
                return (
                  <div
                    key={nid}
                    className="flex items-center gap-2 px-2 py-1.5 rounded border border-border bg-surface"
                  >
                    <code className="text-[11px] font-mono text-text flex-1 min-w-0 truncate">
                      {nid}
                    </code>
                    {isSuccess && (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] text-emerald-400"
                        data-testid={`concurrency-reset-success-${nid}`}
                      >
                        <Check className="w-3 h-3" />
                        Cleared. New probe on next acquire.
                      </span>
                    )}
                    {isError && (
                      <span
                        className="inline-flex items-center gap-1 text-[10px] text-error truncate"
                        title={status.state === 'error' ? status.message : undefined}
                      >
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        {status.state === 'error' ? status.message : ''}
                      </span>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPendingNode(nid)}
                      disabled={isPending}
                      data-testid={`concurrency-reset-button-${nid}`}
                    >
                      {isPending ? 'Resetting…' : 'Reset'}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          <p className="text-[10px] text-text-muted opacity-70 leading-relaxed">
            Tip: the same action is available via{' '}
            <code className="text-[10px] font-mono">
              POST /compute/concurrency/clear?node_id=&lt;id&gt;
            </code>
            . The persisted ceiling expires automatically after 24 h.
          </p>
        </div>
      )}

      <ConfirmDialog
        open={pendingNode !== null}
        title="Reset discovered concurrency ceiling?"
        description={
          `This invalidates the persisted ceiling for ${pendingNode ?? ''}. AIMD will ` +
          `re-probe from the Phase 82 jumpstart on the next acquire — your throughput ` +
          `may briefly drop while it climbs back to the safe limit.`
        }
        warning="Only do this after a plan upgrade, endpoint swap, or known capacity change."
        confirmLabel="Reset ceiling"
        cancelLabel="Cancel"
        variant="destructive"
        testId="concurrency-reset-confirm"
        onCancel={() => setPendingNode(null)}
        onConfirm={() => {
          const nid = pendingNode;
          setPendingNode(null);
          if (nid) void performReset(nid);
        }}
      />
    </div>
  );
}

export default ConcurrencyResetPanel;
