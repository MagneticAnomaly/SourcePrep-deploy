import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight, ChevronDown, X } from 'lucide-react';

import { Button } from '../primitives/Button';
import { cn } from '../../lib/utils';

export interface VendorCandidateView {
  rel_path: string;
  size_bytes: number;
  file_count: number;
  reason: string;
  tier: 'auto' | 'propose';
  in_gitignore: boolean;
  is_git_repo: boolean;
}

export interface InitExcludeReviewModalProps {
  open: boolean;
  proposed: VendorCandidateView[];
  /** Tier-1 items already merged into exclude_globs — shown informationally only. */
  autoExcludedSummary: VendorCandidateView[];
  /** X / Esc / backdrop. Does NOT fire Initialize. */
  onClose: () => void;
  /** Merge selected rel_paths into exclude_globs and record unchecked as dismissed, then start build. */
  onApply: (selectedRelPaths: string[], dismissedRelPaths: string[]) => void;
  /** Skip the merge step entirely and start build with no exclude changes. */
  onSkip: () => void;
  className?: string;
  /** Test hook prefix; emits `${testId}` on the dialog panel, `${testId}-close` on X, `${testId}-apply` on apply button, `${testId}-skip` on skip button, `${testId}-row-${rel_path}` on each checkbox. */
  testId?: string;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function isSizeFallbackReason(reason: string): boolean {
  return reason.startsWith('Large directory');
}

export function InitExcludeReviewModal({
  open,
  proposed,
  autoExcludedSummary,
  onClose,
  onApply,
  onSkip,
  className,
  testId,
}: InitExcludeReviewModalProps) {
  // Default-checked toward exclude (safer-from-runaway default per spec).
  // Re-initialize whenever `proposed` changes so a new scan's results
  // start with the right defaults.
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const c of proposed) init[c.rel_path] = true;
    return init;
  });
  const [autoExpanded, setAutoExpanded] = useState(false);

  useEffect(() => {
    const init: Record<string, boolean> = {};
    for (const c of proposed) init[c.rel_path] = true;
    setChecked(init);
  }, [proposed]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  const selected = proposed.filter((c) => checked[c.rel_path]).map((c) => c.rel_path);
  const dismissed = proposed.filter((c) => !checked[c.rel_path]).map((c) => c.rel_path);

  if (!open) return null;

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm',
        className,
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-lg border border-border bg-surface p-6 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="exclude-review-title"
        aria-describedby="exclude-review-desc"
        data-testid={testId}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 id="exclude-review-title" className="text-sm font-semibold text-text">
              Review what to exclude before indexing
            </h3>
            <p
              id="exclude-review-desc"
              className="mt-1 text-xs text-text-subtle leading-relaxed"
            >
              SourcePrep found directories that may not need to be indexed.
              Review the proposals and confirm before we build the index.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-text-subtle hover:bg-surface-raised hover:text-text transition-colors"
            aria-label="Close"
            data-testid={testId ? `${testId}-close` : undefined}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {autoExcludedSummary.length > 0 && (
          <div className="mt-3 border border-border rounded-md">
            <button
              onClick={() => setAutoExpanded((prev) => !prev)}
              className="w-full px-3 py-2 text-left text-xs text-text-subtle hover:bg-surface-raised flex items-center gap-2"
              aria-expanded={autoExpanded}
            >
              {autoExpanded ? (
                <ChevronDown className="h-3 w-3 shrink-0" />
              ) : (
                <ChevronRight className="h-3 w-3 shrink-0" />
              )}
              <span>
                Auto-excluded ({autoExcludedSummary.length}) — these are already added to the
                exclude list.
              </span>
            </button>
            {autoExpanded && (
              <ul className="px-3 pb-2 space-y-1 text-xs font-mono">
                {autoExcludedSummary.map((c) => (
                  <li key={c.rel_path} className="flex items-start gap-2">
                    <span className="text-success shrink-0">✓</span>
                    <span className="text-text">{c.rel_path}/</span>
                    <span className="text-text-subtle">— {c.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-4">
          <p className="text-xs text-text-subtle mb-2">Review proposals (default: exclude):</p>
          {proposed.length === 0 ? (
            <p className="text-xs text-text-subtle italic">
              No proposals — SourcePrep didn&apos;t find any ambiguous directories.
            </p>
          ) : (
            <ul className="space-y-2 max-h-72 overflow-y-auto">
              {proposed.map((c) => {
                const isChecked = checked[c.rel_path] ?? true;
                const weak = isSizeFallbackReason(c.reason);
                return (
                  <li
                    key={c.rel_path}
                    className="flex items-start gap-3 p-2 rounded-md border border-border hover:bg-surface-raised"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) =>
                        setChecked((s) => ({ ...s, [c.rel_path]: e.target.checked }))
                      }
                      className="mt-1 shrink-0"
                      aria-label={`Exclude ${c.rel_path}`}
                      data-testid={testId ? `${testId}-row-${c.rel_path}` : undefined}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-sm flex items-center gap-1">
                        <span className="text-text">{c.rel_path}/</span>
                        {weak && (
                          <span
                            title="Weak signal — based on size only"
                            className="inline-flex items-center text-text-subtle"
                            aria-label="Weak signal — based on size only"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className="h-3 w-3"
                              aria-hidden="true"
                            >
                              <circle cx="12" cy="12" r="10" />
                              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                              <path d="M12 17h.01" />
                            </svg>
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-text-subtle">
                        {formatBytes(c.size_bytes)},{' '}
                        {c.file_count.toLocaleString()} files — {c.reason}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="mt-6 flex items-center justify-between gap-2 flex-wrap">
          <span className="text-xs text-text-subtle">
            {proposed.length === 0
              ? ''
              : `Selected: ${selected.length} of ${proposed.length} proposals`}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onSkip}
              data-testid={testId ? `${testId}-skip` : undefined}
            >
              Skip Excludes &amp; Initialize
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => onApply(selected, dismissed)}
              data-testid={testId ? `${testId}-apply` : undefined}
            >
              Apply {selected.length} Exclude{selected.length === 1 ? '' : 's'} &amp; Initialize
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
