import { useState, useEffect, useRef } from 'react';
import { ShieldAlert, RotateCcw, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { Select } from '../primitives/Select';
import { ConfirmDialog } from '../primitives/ConfirmDialog';
import type { ApiClient } from '../../api/client';
import type { StageBackup } from '../../types';

// ── Inline format helpers ─────────────────────────────────────

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function formatRelativeAgo(epochSeconds: number, nowMs: number = Date.now()): string {
  const ageS = Math.max(0, Math.floor(nowMs / 1000 - epochSeconds));
  if (ageS < 60) return `${ageS}s ago`;
  if (ageS < 3600) return `${Math.floor(ageS / 60)}m ago`;
  if (ageS < 86400) return `${Math.floor(ageS / 3600)}h ago`;
  return `${Math.floor(ageS / 86400)}d ago`;
}

function formatTimestamp(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ── Exported label helper (tested independently) ──────────────

export function formatBackupLabel(b: StageBackup): string {
  const ago = formatRelativeAgo(b.created_at);
  const size = formatBytes(b.size_bytes);
  if (b.kind === 'golden') return `Golden snapshot — ${size} • ${ago}`;
  return `${b.branch ?? 'unknown'} @ ${formatTimestamp(b.created_at)} — ${size} • ${ago}`;
}

// ── Props ─────────────────────────────────────────────────────

export interface RecoverStagePanelProps {
  projectId: string;
  stageId: string;
  /** Display name for the stage in the confirm dialog (e.g. "Atlas"). */
  stageLabel: string;
  /** API client — injected by parent so this component stays decoupled. */
  apiClient: ApiClient;
  /** Disabled when pipeline is actively running this stage. */
  disabled?: boolean;
  /** Called after a successful restore so the parent can refresh status. */
  onRestored?: (snapshotId: string) => void;
  className?: string;
}

// ── Component ─────────────────────────────────────────────────

export function RecoverStagePanel({
  projectId,
  stageId,
  stageLabel,
  apiClient,
  disabled = false,
  onRestored,
  className,
}: RecoverStagePanelProps) {
  const [open, setOpen] = useState(false);
  const [backups, setBackups] = useState<StageBackup[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  // Track the abort controller for the current fetch
  const abortRef = useRef<AbortController | null>(null);

  // Fetch backups lazily when panel opens
  useEffect(() => {
    if (!open) return;
    if (backups !== null) return; // already loaded

    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setLoadError(null);

    apiClient
      .listStageBackups(projectId, stageId, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return;
        // Sort reverse-chronological (newest first)
        const sorted = [...res.backups].sort((a, b) => b.created_at - a.created_at);
        setBackups(sorted);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const msg = err instanceof Error ? err.message : String(err);
        setLoadError(msg);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [open, projectId, stageId, apiClient, backups]);

  function handleClose() {
    abortRef.current?.abort();
    setOpen(false);
    // Reset transient state but keep backups cached
    setSelected(null);
    setConfirming(false);
    setRestoreError(null);
  }

  function handleOpenToggle() {
    if (open) {
      handleClose();
    } else {
      setOpen(true);
    }
  }

  async function handleRestore() {
    if (!selected) return;
    setRestoring(true);
    setRestoreError(null);
    try {
      await apiClient.restoreStageFromSnapshot(projectId, stageId, selected);
      setConfirming(false);
      handleClose();
      onRestored?.(selected);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Restore failed. Please try again.';
      setRestoreError(msg);
    } finally {
      setRestoring(false);
    }
  }

  const selectedBackup = backups?.find((b) => b.snapshot_id === selected) ?? null;
  const selectedLabel = selectedBackup ? formatBackupLabel(selectedBackup) : '';

  const selectOptions =
    backups && backups.length > 0
      ? backups.map((b) => ({ value: b.snapshot_id, label: formatBackupLabel(b) }))
      : [];

  const isEmpty = backups !== null && backups.length === 0;

  return (
    <div className={cn('rounded-md border border-red-800/40 bg-red-950/10', className)}>
      {/* Trigger row */}
      <button
        type="button"
        onClick={handleOpenToggle}
        disabled={disabled}
        aria-label={`Recover ${stageLabel} from snapshot`}
        aria-expanded={open}
        title={
          disabled
            ? 'Pipeline is running — wait for the active stage to finish.'
            : 'Open stage recovery options'
        }
        className={cn(
          'flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium',
          'text-red-400 hover:text-red-300 transition-colors',
          'disabled:opacity-40 disabled:cursor-not-allowed',
        )}
      >
        <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
        <span>Recover{open ? '…' : '…'}</span>
        <span className="ml-auto text-red-600/60 text-[10px]">Danger Zone</span>
      </button>

      {/* Expanded panel */}
      {open && (
        <div className="border-t border-red-800/30 px-3 pb-3 pt-2 space-y-3">
          {/* Loading */}
          {loading && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Loading available backups…</span>
            </div>
          )}

          {/* Load error */}
          {!loading && loadError && (
            <p className="text-xs text-red-400">
              Failed to load backups: {loadError}
            </p>
          )}

          {/* Empty state */}
          {!loading && isEmpty && (
            <p className="text-xs text-text-muted">
              No backups for this stage yet — run the pipeline at least once.
            </p>
          )}

          {/* Backup picker */}
          {!loading && backups !== null && backups.length > 0 && (
            <div className="space-y-2">
              <label className="text-[11px] text-text-muted font-medium">
                Select snapshot to restore from:
              </label>
              <Select
                options={selectOptions}
                placeholder="Choose a backup…"
                value={selected ?? ''}
                onChange={(e) => setSelected(e.target.value || null)}
                size={'sm' as const}
                className="w-full"
                aria-label={`Snapshot to restore for ${stageLabel}`}
              />
            </div>
          )}

          {/* Restore button */}
          {!loading && !loadError && (
            <div className="flex items-center gap-2">
              <Button
                variant={'destructive' as const}
                size={'sm' as const}
                disabled={!selected || isEmpty}
                onClick={() => setConfirming(true)}
                className="flex items-center gap-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Restore
              </Button>
            </div>
          )}

          {/* Footnote */}
          <p className="text-[10px] text-text-muted/60 leading-relaxed">
            Restoring overwrites this stage&apos;s manifest and output. Other stages are
            untouched. The reset barrier is bypassed.
          </p>
        </div>
      )}

      {/* Confirm modal */}
      <ConfirmDialog
        open={confirming && !restoring}
        title={`Restore ${stageLabel} from ${selectedLabel}?`}
        description={`This will overwrite the active manifest for the ${stageLabel} stage. Other stages keep their current state.`}
        warning={restoreError ?? undefined}
        confirmLabel={restoring ? 'Restoring…' : 'Restore'}
        cancelLabel="Cancel"
        variant="destructive"
        onConfirm={handleRestore}
        onCancel={() => {
          if (!restoring) {
            setConfirming(false);
            setRestoreError(null);
          }
        }}
      />

      {/* Restoring in-flight overlay (modal is closed, we show inline) */}
      {restoring && (
        <div className="border-t border-red-800/30 px-3 py-2">
          <div className="flex items-center gap-2 text-xs text-red-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Restoring {stageLabel}…</span>
          </div>
        </div>
      )}
    </div>
  );
}
